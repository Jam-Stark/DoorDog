"""base_v22 §15 Route B for a Route-A selected checkpoint.

pooled48 (seeds 1,2; seed 0 reuses the Route A row), Dynamics80 (E0_CORE16 /
E1_DAMPING16 / E2_REBOUND16 built from the frozen H0/H1/H2 ranges; H3/H4
unrealized per V22_HINGE_RANGE_FREEZE.json so E3/E4 are omitted and documented),
holdout64 (seeds 3,4,5,6).  All canonical16-runs use the signed v21-B manifest
selector (the canonical16 contract); Dynamics runs use the v22 scenario manifest
selector.  One invocation runs one route-seed/manifest on one GPU; the lead
drives the nine runs across the assigned GPUs with the shared kit-copy startup
lock.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from scriptsFORhuman.v22._v22_common import (  # noqa: E402
    PYTHON_BIN,
    V22_ARTIFACT_ROOT,
    V22Error,
    digest,
    read_json,
    write_json,
)
from scriptsFORhuman.v22.m22 import (  # noqa: E402
    load_scenario_manifest,
)

CHECKPOINT = REPO / "logs_rl/a2_piper_full_stage_a2_base/base_v22/G1/model_step_001250.pt"
SELECTION_PATH = REPO / V22_ARTIFACT_ROOT / "postformal_20260806_route_a" / "V22_ROUTE_A_SELECTION.json"
ROUTE_B_ROOT = REPO / V22_ARTIFACT_ROOT / "route_b_20260806_g1_step1250"
CANDIDATE_TAG = "g1_step1250"
LOCK_PATH = Path("/tmp/doordog-a2-piper-headless-kit-copy.lock")
LOCK_MARKER = b"[INFO][AppLauncher]: Loading experience file:"
RENDER_GPUS = (0, 1, 2, 3)
BUCKET_TABLE = (
    "[{bucket: H0, damping: [50.0, 150.0], stiffness: [6.0, 20.0], max_force_nm: [10.0, 24.0]},"
    "{bucket: H1, damping: [30.0, 120.0], stiffness: [2.0, 6.0], max_force_nm: [5.0, 12.0]},"
    "{bucket: H2, damping: [15.0, 50.0], stiffness: [6.0, 20.0], max_force_nm: [10.0, 18.0]}]"
)
DIAGNOSTIC_TERMS = (
    "[push_door_hinge,a2_stage3_unlatch_hold,a2_stage3_stage4_hold_and_drive,"
    "a2_corridor_door_wide,a2_corridor_clean_passage,penalty_a2_door_body_contact,complete]"
)

# frozen ranges from V22_HINGE_RANGE_FREEZE.json
FROZEN = {
    "E0_CORE16": {"bucket": "H0", "damping": (50.0, 150.0), "stiffness": (6.0, 20.0), "maxforce": (10.0, 24.0), "mass": (80.0, 160.0), "height": (0.85, 1.10)},
    "E1_DAMPING16": {"bucket": "H1", "damping": (30.0, 120.0), "stiffness": (2.0, 6.0), "maxforce": (5.0, 12.0), "mass": (80.0, 160.0), "height": (0.85, 1.10)},
    "E2_REBOUND16": {"bucket": "H2", "damping": (15.0, 50.0), "stiffness": (6.0, 20.0), "maxforce": (10.0, 18.0), "mass": (80.0, 160.0), "height": (0.85, 1.10)},
}


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _linspace(lo: float, hi: float, n: int) -> list[float]:
    return [round(lo + (hi - lo) * i / (n - 1), 6) for i in range(n)]


def build_dynamics_manifest(name: str, target: Path) -> str:
    f = FROZEN[name]
    d = _linspace(*f["damping"], 4)
    s = _linspace(*f["stiffness"], 4)
    mf = _linspace(*f["maxforce"], 4)
    m = _linspace(*f["mass"], 4)
    h = _linspace(*f["height"], 4)
    rows = []
    for i in range(16):
        rows.append({
            "scenario_id": f"{name}_r{i:02d}",
            "handle_height_m": h[i % 4],
            "door_weight_kg": m[(i // 4) % 4],
            "hinge_max_force_nm": mf[(i // 2) % 4],
            "hinge_damping_native": d[i % 4],
            "hinge_stiffness_native": s[(i // 4) % 4],
            "bucket": f["bucket"],
        })
    return write_json(target, {
        "schema": "a2_piper_base_v22_scenario_manifest_v1",
        "manifest_name": f"v22_routeB_{name}",
        "plan_id": "base_v22_posture_clearance_force_routing_v3",
        "execution_id": "base_v22_execution_v3",
        "purpose": "route_b_dynamics80_eval_scenario",
        "rows": rows,
    })


def _canonical16_overrides(scenario: dict) -> list[str]:
    m = scenario["manifest"]
    return [
        "++env.config.a2_v21B_signed_probe_scenarios_enabled=true",
        "++env.config.a2_v21B_census_topology=canonical16",
        f"++env.config.a2_v21B_scenario_manifest_path={scenario['path']}",
        f"++env.config.a2_v21B_scenario_manifest_sha256={scenario['manifest_sha256']}",
        f"++env.config.a2_v21B_scenario_manifest_file_sha256={scenario['file_sha256']}",
        f"++env.config.a2_v21B_canonical_manifest_sha256={scenario['canonical_manifest_sha256']}",
        f"++env.config.a2_v21B_scenario_manifest_source_checkpoint_sha256={m['source_checkpoint_sha256']}",
        f"++env.config.a2_v21B_scenario_manifest_source_lock_sha256={m['source_lock_sha256']}",
        f"++env.config.a2_v21B_scenario_manifest_source_config_sha256={m['source_config_sha256']}",
        f"++env.config.a2_v21B_scenario_manifest_materialization_sha256={scenario['materialization_sha256']}",
        f"++env.config.a2_v21B_scenario_manifest_json_sha256={scenario['manifest_json_sha256']}",
        f"++env.config.a2_v21B_scenario_manifest_json={scenario['manifest_json']!r}",
    ]


def _v22_manifest_overrides(path: Path, sha: str, name: str) -> list[str]:
    return [
        "++env.config.a2_v22_hinge_bucket_mixture=null",
        "++env.config.a2_v22_scenario_manifest_enabled=true",
        f"++env.config.a2_v22_scenario_manifest_path='{path}'",
        f"++env.config.a2_v22_scenario_manifest_sha256={sha}",
        f"++env.config.a2_v22_scenario_manifest_name='v22_routeB_{name}'",
    ]


def build_argv(checkpoint: Path, seed: int, output_root: Path, extra_selector: list[str], run_uuid: str, eval_name: str) -> tuple[list[str], dict[str, str]]:
    argv = [
        str(PYTHON_BIN), "-m", "gr00t.rl.eval_agent_trl",
        f"++checkpoint={checkpoint}",
        "++checkpoint_load_mode=full", "++auto_load_latest=false", "++headless=true",
        "++num_envs=16", f"++seed={seed}", "++use_wandb=false",
        "++simulator.config.cameras.enable_cameras=false", "++simulator.config.render_results=false",
        "++algo.config.eval.num_eval_episodes=16", "++algo.config.eval.eval_num_envs_episodes=true",
        "++algo.config.eval.a2_diagnostic_trace_enabled=true",
        f"++algo.config.eval.a2_diagnostic_reward_terms={DIAGNOSTIC_TERMS}",
        "++algo.config.eval.a2_eval_v20_strict_telemetry=false",
        "++algo.config.eval.a2_eval_m41_strict_telemetry=false",
        "++algo.config.eval.save_videos=false", "++algo.config.eval.save_trajectories=false",
        "++env.config.a2_v20_R1_plan_id=base_v22_posture_clearance_force_routing_v3",
        "++env.config.a2_v20_send_hinge_threshold=0.9",
        "++env.config.a2_v20_R2_evidence_enabled=false",
        "++env.config.a2_v21B_evidence_enabled=false",
        "++env.config.a2_v22_evidence_enabled=true",
        f"++env.config.a2_v22_hinge_bucket_table={BUCKET_TABLE}",
        *extra_selector,
        f"++env.config.a2_v22_run_uuid={run_uuid!r}",
        f"++eval_name={eval_name}", f"++eval_output_dir={output_root}",
    ]
    return argv, {"ACCELERATE_TORCH_DEVICE": "cuda:0", "WANDB_MODE": "disabled", "PYTHONPATH": str(REPO)}


def run_one(name: str, gpu: int, seed: int, selector: list[str], output_root: Path) -> int:
    if gpu not in RENDER_GPUS:
        raise V22Error(f"GPU {gpu} not in assigned set {RENDER_GPUS}")
    output_root.parent.mkdir(parents=True, exist_ok=True)
    if output_root.exists():
        raise V22Error(f"output root must be fresh: {output_root}")
    output_root.mkdir()
    run_uuid = f"v22-routeB-{CANDIDATE_TAG}-{name}-seed{seed}"
    argv, base_env = build_argv(
        CHECKPOINT,
        seed,
        output_root,
        selector,
        run_uuid,
        f"v22_routeB_{CANDIDATE_TAG}_{name}_seed{seed}",
    )
    env = os.environ.copy()
    env.pop("CUDA_VISIBLE_DEVICES", None)
    env.update(base_env)
    env["ACCELERATE_TORCH_DEVICE"] = f"cuda:{gpu}"
    write_json(output_root / "run_command.json", {"argv": argv, "env": base_env, "command_sha256": digest(argv)})
    stdout_path = output_root / "runtime_stdout.log"
    stderr_path = output_root / "runtime_stderr.log"
    started = _utc(); mono = time.monotonic(); marker = False
    with LOCK_PATH.open("a+") as lock, stdout_path.open("xb") as out, stderr_path.open("xb") as err:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            proc = subprocess.Popen(argv, cwd=REPO, env=env, stdout=out, stderr=err)
            print(f"LAUNCHED {name} gpu={gpu} pid={proc.pid}", flush=True)
            while True:
                try:
                    if LOCK_MARKER in stdout_path.read_bytes():
                        marker = True; break
                except OSError:
                    pass
                if proc.poll() is not None:
                    break
                time.sleep(0.2)
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        code = proc.wait()
    dur = time.monotonic() - mono
    receipt = {"schema": "a2_piper_base_v22_route_b_receipt_v1", "run": name, "seed": seed, "physical_gpu": gpu, "started_utc": started, "ended_utc": _utc(), "duration_seconds": round(dur, 1), "exit_code": code, "natural_exit": code == 0, "startup_marker_seen": marker, "command_sha256": digest(argv)}
    if code != 0:
        write_json(output_root / "run_receipt.json", receipt)
        raise V22Error(f"route B {name} exited {code}; see {stderr_path}")
    write_json(output_root / "run_receipt.json", receipt)
    print(f"DONE {name} gpu={gpu} dur={dur:.1f}s exit=0", flush=True)
    return 0


def configure_candidate(selection_path: Path, output_root: Path) -> None:
    global CHECKPOINT, SELECTION_PATH, ROUTE_B_ROOT, CANDIDATE_TAG
    selection = read_json(selection_path)
    selected = selection["selected"]
    CHECKPOINT = Path(selected["checkpoint_path"])
    SELECTION_PATH = selection_path
    ROUTE_B_ROOT = output_root
    CANDIDATE_TAG = f"{selected['cell'].lower()}_step{int(selected['step']):04d}"


def _job_root(output_root: Path, job: str) -> Path:
    if job.startswith("pooled:"):
        return output_root / "pooled48" / f"seed{int(job.split(':')[1])}" / "canonical16"
    if job.startswith("holdout:"):
        return output_root / "holdout64" / f"seed{int(job.split(':')[1])}" / "canonical16"
    return output_root / "dynamics80" / job / "canonical16"


def run_all(selection_path: Path, output_root: Path, gpus: list[int], *, resume: bool) -> int:
    selection = read_json(selection_path)
    selected = selection["selected"]
    reused_seed = int(selected["seed"])
    route_a_root = Path(selection["inputs"]["evidence_index_path"]).parent
    reused_root = (
        route_a_root
        / selected["cell"]
        / f"step{int(selected['step']):04d}"
        / "canonical16"
        / f"seed{reused_seed}"
    )
    jobs = [f"pooled:{seed}" for seed in (0, 1, 2) if seed != reused_seed]
    jobs.extend(("E0_CORE16", "E1_DAMPING16", "E2_REBOUND16"))
    jobs.extend(f"holdout:{seed}" for seed in (3, 4, 5, 6))

    output_root.mkdir(parents=True, exist_ok=resume)
    if resume and not (output_root / "V22_ROUTE_B_RUNTIME_PLAN.json").is_file():
        raise V22Error("--resume requires an existing Route-B runtime plan")
    completed = []
    if resume:
        for job in jobs:
            receipt_path = _job_root(output_root, job) / "run_receipt.json"
            if not receipt_path.is_file():
                continue
            receipt = read_json(receipt_path)
            if receipt.get("natural_exit") is True and receipt.get("exit_code") == 0:
                completed.append(
                    {
                        "run": job,
                        "gpu": receipt["physical_gpu"],
                        "exit_code": 0,
                        "reused_existing": True,
                    }
                )
    write_json(
        output_root / ("V22_ROUTE_B_RUNTIME_PLAN_RESUME.json" if resume else "V22_ROUTE_B_RUNTIME_PLAN.json"),
        {
            "schema": "a2_piper_base_v22_route_b_runtime_plan_v1",
            "selection_path": str(selection_path),
            "candidate": CANDIDATE_TAG,
            "gpus": gpus,
            "fresh_runs": [job for job in jobs if job not in {row["run"] for row in completed}],
            "pooled_reuse": {"seed": reused_seed, "route_a_row_root": str(reused_root)},
            "scheduling": "one live run per GPU; shared startup flock; stop new launches on first failure",
        },
    )

    pending = [job for job in jobs if job not in {row["run"] for row in completed}]
    active: dict[int, tuple[str, subprocess.Popen]] = {}
    failed = False
    while active or (pending and not failed):
        if not failed:
            for gpu in gpus:
                if gpu in active or not pending:
                    continue
                job = pending.pop(0)
                command = [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--run",
                    job,
                    "--gpu",
                    str(gpu),
                    "--selection",
                    str(selection_path),
                    "--output-root",
                    str(output_root),
                ]
                process = subprocess.Popen(command, cwd=REPO)
                active[gpu] = (job, process)
                print(f"ROUTE_B_ALL LAUNCHED {job} gpu={gpu} pid={process.pid}", flush=True)
        for gpu, (job, process) in list(active.items()):
            code = process.poll()
            if code is None:
                continue
            completed.append({"run": job, "gpu": gpu, "exit_code": code})
            del active[gpu]
            if code != 0:
                failed = True
                print(f"ROUTE_B_ALL FAIL {job} gpu={gpu} exit={code}; no new runs will launch", flush=True)
        if active:
            time.sleep(2.0)

    status = "PASS" if not failed and not pending else "FAIL"
    write_json(
        output_root / "V22_ROUTE_B_TERMINAL_STATUS.json",
        {
            "schema": "a2_piper_base_v22_route_b_terminal_status_v1",
            "status": status,
            "candidate": CANDIDATE_TAG,
            "completed": completed,
            "pending": pending,
            "pooled_reuse": {"seed": reused_seed, "route_a_row_root": str(reused_root)},
        },
    )
    print(f"ROUTE_B_ALL {status} completed={len(completed)}/{len(jobs)}", flush=True)
    return 0 if status == "PASS" else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--run", help="pooled:seedN | E0_CORE16 | E1_DAMPING16 | E2_REBOUND16 | holdout:seedN")
    mode.add_argument("--all", action="store_true", help="run every fresh Route-B row and reuse the selected Route-A seed")
    parser.add_argument("--gpu", type=int)
    parser.add_argument("--gpus", type=int, nargs="+")
    parser.add_argument("--selection", type=Path, default=SELECTION_PATH)
    parser.add_argument("--output-root", type=Path, default=ROUTE_B_ROOT)
    parser.add_argument("--resume", action="store_true")
    a = parser.parse_args()
    configure_candidate(a.selection, a.output_root)
    if a.all:
        if not a.gpus:
            raise V22Error("--all requires --gpus")
        return run_all(a.selection, a.output_root, a.gpus, resume=a.resume)
    if a.gpu is None:
        raise V22Error("--run requires --gpu")
    canonical = load_scenario_manifest()
    if a.run.startswith("pooled:"):
        seed = int(a.run.split(":")[1])
        root = ROUTE_B_ROOT / "pooled48" / f"seed{seed}" / "canonical16"
        return run_one(f"pooled_seed{seed}", a.gpu, seed, _canonical16_overrides(canonical), root)
    if a.run.startswith("holdout:"):
        seed = int(a.run.split(":")[1])
        root = ROUTE_B_ROOT / "holdout64" / f"seed{seed}" / "canonical16"
        return run_one(f"holdout_seed{seed}", a.gpu, seed, _canonical16_overrides(canonical), root)
    if a.run in FROZEN:
        manifest_path = ROUTE_B_ROOT / "dynamics80" / a.run / "scenario_manifest.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        sha = build_dynamics_manifest(a.run, manifest_path)
        root = ROUTE_B_ROOT / "dynamics80" / a.run / "canonical16"
        return run_one(a.run, a.gpu, 0, _v22_manifest_overrides(manifest_path, sha, a.run), root)
    raise V22Error(f"unknown --run {a.run!r}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except V22Error as exc:
        print(f"V22 ROUTE_B FAIL: {exc}", file=sys.stderr)
        raise SystemExit(2)
