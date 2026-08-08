"""base_v22 §15.4 render — five scenarios x three cameras for a Route-A selection.

One invocation renders exactly one scenario (``--scenario``) on one physical GPU
(``--gpu``); the lead drives the five scenarios across the currently assigned
GPUs.  Each scenario runs at num_envs=16 with a 16-row replicated v22 scenario
manifest (same door tuple in every env): the num_envs=1 eval path stalls
deterministically after env creation on the v22 config (observed 2026-08-06,
4/4 identical stalls before ONNX export), while v22 evidence at 16 envs
(Route A) and 16-env rendering (v21B) are both proven.  Concurrent headless
Isaac Sim startups race on the shared rendering-kit copy inside eval_agent_trl,
so startup is serialized through a host-global flock until the AppLauncher
experience marker appears (same protocol as the v21B multickpt render).

Fail-fast: no overwrites, no retries, illegal GPU or missing artifact raises.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
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
    sha256_file,
    write_json,
)

RENDER_GPUS = (0, 1, 2, 3)  # assigned by the lead at launch; scheduling fact, not a plan freeze
LOCK_PATH = Path("/tmp/doordog-a2-piper-headless-kit-copy.lock")
LOCK_MARKER = b"[INFO][AppLauncher]: Loading experience file:"

CHECKPOINT = REPO / "logs_rl/a2_piper_full_stage_a2_base/base_v22/G1/model_step_001250.pt"
SELECTION_PATH = REPO / V22_ARTIFACT_ROOT / "postformal_20260806_route_a" / "V22_ROUTE_A_SELECTION.json"
RENDER_ROOT = REPO / V22_ARTIFACT_ROOT / "render_20260806_g1_step1250"
CANDIDATE_TAG = "g1_step1250"
BUCKET_TABLE = (
    "[{bucket: H0, damping: [50.0, 150.0], stiffness: [6.0, 20.0], max_force_nm: [10.0, 24.0]},"
    "{bucket: H1, damping: [30.0, 120.0], stiffness: [2.0, 6.0], max_force_nm: [5.0, 12.0]},"
    "{bucket: H2, damping: [15.0, 50.0], stiffness: [6.0, 20.0], max_force_nm: [10.0, 18.0]}]"
)
DIAGNOSTIC_TERMS = (
    "[push_door_hinge,a2_stage3_unlatch_hold,a2_stage3_stage4_hold_and_drive,"
    "a2_corridor_door_wide,a2_corridor_clean_passage,penalty_a2_door_body_contact,complete]"
)

# (name, handle_height_m, door_weight_kg, hinge_max_force_nm, damping_native, stiffness_native, bucket, label)
SCENARIOS = (
    ("ordinary_mid_handle", 0.975, 120.0, 10.0, 50.0, 6.0, "H0", "ordinary middle-height door, measured CORE reference tuple T03"),
    ("low_handle", 0.85, 120.0, 10.0, 50.0, 6.0, "H0", "low handle, measured CORE reference tuple T03 hinge"),
    ("high_handle", 1.10, 120.0, 10.0, 50.0, 6.0, "H0", "high handle, measured CORE reference tuple T03 hinge"),
    ("fast_rebound", 0.975, 120.0, 16.0, 25.0, 18.0, "H2", "measured FAST_REBOUND tuple T11 (free-return half time 1.65 s, peak closing 0.60 rad/s)"),
    ("high_damping", 0.975, 120.0, 12.0, 120.0, 6.0, "H1", "measured HIGH_DAMPING tuple T08 (never reached half return, peak closing 0.06 rad/s); H3/H4 unrealized per V22_HINGE_RANGE_FREEZE.json"),
)

PRIMARY_MP4_RE = re.compile(
    r"^.+_env(?P<env>[0-9]{4})_episode(?P<episode>[0-9]{4})"
    r"(?P<camera>_handle_side|_handle_top)?_len(?P<length>[0-9]+)_reason-(?P<reason>.+)\.mp4$"
)
EXPECTED_CAMERAS = (None, "_handle_top", "_handle_side")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def build_manifest(scenario: tuple, target: Path) -> str:
    name, height, mass, maxforce, damping, stiffness, bucket, label = scenario
    payload = {
        "schema": "a2_piper_base_v22_scenario_manifest_v1",
        "manifest_name": f"v22_render_{name}",
        "plan_id": "base_v22_posture_clearance_force_routing_v3",
        "execution_id": "base_v22_execution_v3",
        "purpose": "route_a_selected_checkpoint_render_scenario",
        "scenario_label": label,
        "rows": [
            {
                "scenario_id": f"{name}_e{index:02d}",
                "handle_height_m": height,
                "door_weight_kg": mass,
                "hinge_max_force_nm": maxforce,
                "hinge_damping_native": damping,
                "hinge_stiffness_native": stiffness,
                "bucket": bucket,
            }
            for index in range(16)
        ],
    }
    return write_json(target, payload)


def build_argv(scenario: tuple, manifest_path: Path, manifest_sha: str, output_root: Path, gpu: int) -> tuple[list[str], dict[str, str]]:
    name = scenario[0]
    argv = [
        str(PYTHON_BIN),
        "-m",
        "gr00t.rl.eval_agent_trl",
        f"++checkpoint={CHECKPOINT}",
        "++checkpoint_load_mode=full",
        "++auto_load_latest=false",
        "++headless=true",
        "++num_envs=16",
        "++seed=0",
        "++use_wandb=false",
        "++simulator.config.cameras.enable_cameras=false",
        "++simulator.config.render_results=true",
        "++algo.config.eval.num_eval_episodes=16",
        "++algo.config.eval.eval_num_envs_episodes=true",
        "++algo.config.eval.a2_diagnostic_trace_enabled=true",
        f"++algo.config.eval.a2_diagnostic_reward_terms={DIAGNOSTIC_TERMS}",
        "++algo.config.eval.a2_eval_v20_strict_telemetry=false",
        "++algo.config.eval.a2_eval_m41_strict_telemetry=false",
        "++algo.config.eval.save_videos=false",
        "++algo.config.eval.save_trajectories=false",
        "++env.config.a2_v20_R1_plan_id=base_v22_posture_clearance_force_routing_v3",
        "++env.config.a2_v20_send_hinge_threshold=0.9",
        "++env.config.a2_v20_R2_evidence_enabled=false",
        "++env.config.a2_v21B_evidence_enabled=false",
        "++env.config.a2_v22_evidence_enabled=true",
        f"++env.config.a2_v22_hinge_bucket_table={BUCKET_TABLE}",
        "++env.config.a2_v22_hinge_bucket_mixture=null",
        "++env.config.a2_v22_scenario_manifest_enabled=true",
        f"++env.config.a2_v22_scenario_manifest_path='{manifest_path}'",
        f"++env.config.a2_v22_scenario_manifest_sha256={manifest_sha}",
        f"++env.config.a2_v22_scenario_manifest_name='v22_render_{name}'",
        f"++env.config.save_rendering_dir={output_root / 'renderings'}",
        f"++eval_name=v22_render_{CANDIDATE_TAG}_{name}_seed0",
        f"++eval_output_dir={output_root}",
    ]
    env = {
        "CUDA_VISIBLE_DEVICES": str(gpu),
        "ACCELERATE_TORCH_DEVICE": "cuda:0",
        "VK_ICD_FILENAMES": "/usr/share/vulkan/icd.d/nvidia_icd.json",
        "WANDB_MODE": "disabled",
    }
    return argv, env


def media_gate(output_root: Path) -> dict:
    renderings = output_root / "renderings"
    if not renderings.is_dir() or renderings.is_symlink():
        raise V22Error(f"renderings directory missing: {renderings}")
    finalized = []
    writing = []
    for path in renderings.iterdir():
        if path.is_symlink() or not path.is_file():
            raise V22Error(f"non-regular media file: {path}")
        if path.name.lower().endswith(".writing.mp4"):
            writing.append(path.name)
        elif path.suffix.lower() == ".mp4":
            finalized.append(path.name)
    if writing:
        raise V22Error(f"unfinalized .writing.mp4 leftovers: {writing}")
    expected = {(env, 0, camera) for env in range(16) for camera in EXPECTED_CAMERAS}
    primary = []
    auxiliary = []
    for name in finalized:
        match = PRIMARY_MP4_RE.fullmatch(name)
        if match is None:
            auxiliary.append(name)
            continue
        key = (int(match.group("env")), int(match.group("episode")), match.group("camera"))
        if key in expected:
            primary.append(name)
        else:
            auxiliary.append(name)
    primary_keys = {
        (int(m.group("env")), int(m.group("episode")), m.group("camera"))
        for n in primary
        if (m := PRIMARY_MP4_RE.fullmatch(n)) is not None
    }
    if len(primary) != 48 or primary_keys != expected:
        missing = sorted(expected - primary_keys)
        raise V22Error(
            f"media gate expects 48 primary mp4 (16 envs x 3 cameras, episode 0); "
            f"got {len(primary)}, missing {len(missing)}: {missing[:4]}"
        )
    return {"finalized_mp4": sorted(finalized), "primary_count": len(primary), "auxiliary_mp4": sorted(auxiliary)}


def _require_render_gpu(gpu: int) -> int:
    if isinstance(gpu, bool) or not isinstance(gpu, int) or gpu not in RENDER_GPUS:
        raise V22Error(f"render GPU must be one of {list(RENDER_GPUS)} as assigned at launch; got {gpu!r}")
    return gpu


def run_scenario(scenario_name: str, gpu: int) -> int:
    _require_render_gpu(gpu)
    scenario = next((s for s in SCENARIOS if s[0] == scenario_name), None)
    if scenario is None:
        raise V22Error(f"unknown render scenario {scenario_name!r}; registered: {[s[0] for s in SCENARIOS]}")
    if not SELECTION_PATH.is_file():
        raise V22Error(f"selection artifact missing: {SELECTION_PATH}")
    RENDER_ROOT.mkdir(parents=True, exist_ok=True)
    root = RENDER_ROOT / scenario[0]
    if root.exists():
        raise V22Error(f"scenario root must be fresh: {root}")
    root.mkdir()
    manifest_sha = build_manifest(scenario, root / "scenario_manifest.json")
    argv, env_add = build_argv(scenario, root / "scenario_manifest.json", manifest_sha, root, gpu)
    command = {"argv": argv, "env": env_add, "command_sha256": digest(argv)}
    write_json(root / "render_command.json", command)

    stdout_path = root / "runtime_stdout.log"
    stderr_path = root / "runtime_stderr.log"
    env = os.environ.copy()
    env.update(env_add)
    started = _utc_now()
    monotonic = time.monotonic()
    marker_seen = False
    with LOCK_PATH.open("a+") as lock_handle, stdout_path.open("xb") as out, stderr_path.open("xb") as err:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        try:
            proc = subprocess.Popen(argv, cwd=REPO, env=env, stdout=out, stderr=err)
            print(f"LAUNCHED {scenario[0]} gpu={gpu} pid={proc.pid}", flush=True)
            while True:
                try:
                    if LOCK_MARKER in stdout_path.read_bytes():
                        marker_seen = True
                        break
                except OSError:
                    pass
                if proc.poll() is not None:
                    break
                time.sleep(0.2)
        finally:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
        code = proc.wait()
    duration = time.monotonic() - monotonic
    receipt = {
        "schema": "a2_piper_base_v22_render_receipt_v1",
        "scenario": scenario[0],
        "physical_gpu": gpu,
        "started_utc": started,
        "ended_utc": _utc_now(),
        "duration_seconds": duration,
        "exit_code": code,
        "natural_exit": code == 0,
        "startup_marker_seen": marker_seen,
        "command_sha256": command["command_sha256"],
        "manifest_sha256": manifest_sha,
        "stdout_sha256": sha256_file(stdout_path),
        "stderr_sha256": sha256_file(stderr_path),
    }
    if code != 0:
        write_json(root / "render_receipt.json", receipt)
        raise V22Error(f"render {scenario[0]} exited {code}; see {stderr_path}")
    receipt["media_gate"] = media_gate(root)
    write_json(root / "render_receipt.json", receipt)
    print(f"DONE {scenario[0]} gpu={gpu} duration={duration:.1f}s media=48/48", flush=True)
    return 0


def configure_candidate(selection_path: Path, output_root: Path) -> None:
    global CHECKPOINT, SELECTION_PATH, RENDER_ROOT, CANDIDATE_TAG
    selection = read_json(selection_path)
    selected = selection["selected"]
    CHECKPOINT = Path(selected["checkpoint_path"])
    SELECTION_PATH = selection_path
    RENDER_ROOT = output_root
    CANDIDATE_TAG = f"{selected['cell'].lower()}_step{int(selected['step']):04d}"


def summarize(selection_path: Path, output_root: Path) -> None:
    selection = read_json(selection_path)
    scenarios = {}
    for scenario in SCENARIOS:
        name = scenario[0]
        root = output_root / name
        receipt = read_json(root / "render_receipt.json")
        metrics = read_json(root / "metrics_eval.json")
        records = read_json(root / "a2_v14_per_env_records.json")
        scenarios[name] = {
            "exit_code": receipt["exit_code"],
            "duration_seconds": receipt["duration_seconds"],
            "primary_mp4": receipt["media_gate"]["primary_count"],
            "auxiliary_mp4": len(receipt["media_gate"]["auxiliary_mp4"]),
            "goal_of_16": sum(1 for value in metrics["episode_goal_reached"] if value is True),
            "supported_crossing_of_16": sum(
                1 for record in records if record.get("crossing_while_holding") is True
            ),
            "post_release_body_contact_of_16": sum(
                1 for record in records if record.get("post_release_body_contact") is True
            ),
        }
    write_json(
        output_root / "V22_RENDER_SUMMARY.json",
        {
            "schema": "a2_piper_base_v22_render_summary_v1",
            "status": "RENDER_PASS",
            "plan_id": "base_v22_posture_clearance_force_routing_v3",
            "execution_id": "base_v22_execution_v3",
            "selection_path": str(selection_path),
            "candidate": {
                key: selection["selected"][key]
                for key in ("row_id", "cell", "step", "seed", "checkpoint_path")
            },
            "render_mode": "num_envs=16, one replicated manifest per scenario, three cameras",
            "media_files_primary_total": sum(item["primary_mp4"] for item in scenarios.values()),
            "scenarios": scenarios,
        },
    )


def run_all(selection_path: Path, output_root: Path, gpus: list[int]) -> int:
    output_root.mkdir(parents=True, exist_ok=False)
    jobs = [scenario[0] for scenario in SCENARIOS]
    write_json(
        output_root / "V22_RENDER_RUNTIME_PLAN.json",
        {
            "schema": "a2_piper_base_v22_render_runtime_plan_v1",
            "selection_path": str(selection_path),
            "candidate": CANDIDATE_TAG,
            "gpus": gpus,
            "scenarios": jobs,
            "scheduling": "one live render per GPU; shared startup flock; stop new launches on first failure",
        },
    )
    pending = list(jobs)
    active: dict[int, tuple[str, subprocess.Popen]] = {}
    completed: list[dict] = []
    failed = False
    while active or (pending and not failed):
        if not failed:
            for gpu in gpus:
                if gpu in active or not pending:
                    continue
                scenario = pending.pop(0)
                command = [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--scenario",
                    scenario,
                    "--gpu",
                    str(gpu),
                    "--selection",
                    str(selection_path),
                    "--output-root",
                    str(output_root),
                ]
                process = subprocess.Popen(command, cwd=REPO)
                active[gpu] = (scenario, process)
                print(f"RENDER_ALL LAUNCHED {scenario} gpu={gpu} pid={process.pid}", flush=True)
        for gpu, (scenario, process) in list(active.items()):
            code = process.poll()
            if code is None:
                continue
            completed.append({"scenario": scenario, "gpu": gpu, "exit_code": code})
            del active[gpu]
            if code != 0:
                failed = True
                print(f"RENDER_ALL FAIL {scenario} gpu={gpu} exit={code}; no new renders will launch", flush=True)
        if active:
            time.sleep(2.0)
    status = "PASS" if not failed and not pending else "FAIL"
    write_json(
        output_root / "V22_RENDER_TERMINAL_STATUS.json",
        {
            "schema": "a2_piper_base_v22_render_terminal_status_v1",
            "status": status,
            "candidate": CANDIDATE_TAG,
            "completed": completed,
            "pending": pending,
        },
    )
    if status == "PASS":
        summarize(selection_path, output_root)
    print(f"RENDER_ALL {status} completed={len(completed)}/{len(jobs)}", flush=True)
    return 0 if status == "PASS" else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--scenario", choices=[s[0] for s in SCENARIOS])
    mode.add_argument("--all", action="store_true")
    parser.add_argument("--gpu", type=int)
    parser.add_argument("--gpus", type=int, nargs="+")
    parser.add_argument("--selection", type=Path, default=SELECTION_PATH)
    parser.add_argument("--output-root", type=Path, default=RENDER_ROOT)
    args = parser.parse_args()
    configure_candidate(args.selection, args.output_root)
    if args.all:
        if not args.gpus:
            raise V22Error("--all requires --gpus")
        return run_all(args.selection, args.output_root, args.gpus)
    if args.gpu is None:
        raise V22Error("--scenario requires --gpu")
    return run_scenario(args.scenario, args.gpu)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except V22Error as exc:
        print(f"V22 RENDER FAIL: {exc}", file=sys.stderr)
        raise SystemExit(2)
