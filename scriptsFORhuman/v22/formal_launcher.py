"""base_v22 formal launcher — Wave 1/2/3 cells in one dedicated tmux session.

Building a plan validates the whole admission chain; launching it starts the
processes.  The two are separate so a plan can be inspected without scheduling a
GPU, and so an incomplete admission chain fails before any process exists.

Refusals that are structural here, not advisory:
  * a physical GPU other than 0 or 1;
  * a missing V22_HINGE_RANGE_FREEZE.json (negative test 24);
  * a missing V22_POSTURE_GATE_FREEZE.json without a signed POSTURE_GATES_REPORT_ONLY
    waiver (negative test 25);
  * a config still carrying a2_v22_calibration_probe=true.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from ._v22_common import (
    PYTHON_BIN,
    REPO_ROOT,
    V22_CELL_CONFIGS,
    V22_CELL_GPU,
    V22_CELL_SEED,
    V22_EXP_NAME,
    V22_PROJECT_NAME,
    V22_FORMAL_BATCHES,
    V22_FORMAL_ENVS,
    V22_FORMAL_SAVE_FREQUENCY,
    V22_LAUNCHER_ROOT,
    V22_LOCK_ROOT,
    V22_PLAN_ID,
    V22_SMOKE_ROOT,
    V22_TRAINING_ROOT,
    V22_WARM_START_PATH,
    V22_WARM_START_SHA256,
    V22_WAVE1_CELLS,
    V22_WAVE2_CELLS,
    V22_WAVE3_CELLS,
    V22Error,
    artifact_payload,
    digest,
    git_identity,
    read_json,
    read_yaml,
    require_gpu,
    sha256_file,
    write_json,
)

FORMAL_SESSION = "base_v22_formal_v3"
SMOKE_SESSION = "base_v22_smoke_v3"
SMOKE_ENVS = 64
SMOKE_BATCHES = 10
SMOKE_SAVE_FREQUENCY = 5

REQUIRED_LOCKS = (
    "V22_SOURCE_LOCK.json",
    "V22_ACTION_SEMANTICS.json",
    "V22_POSTURE_ATLAS.json",
    "V22_HINGE_RUNTIME_BASELINE.json",
    "V22_HINGE_DYNAMICS_PROBE.json",
    "V22_HINGE_RANGE_FREEZE.json",
    "V22_POSTURE_BASELINE.json",
    "V22_POSTURE_DENOMINATOR_ADJUDICATION.json",
    "V22_POSTURE_GATE_FREEZE.json",
)


def load_admission(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    lock_root = Path(repo_root) / V22_LOCK_ROOT
    locks = {}
    for name in REQUIRED_LOCKS:
        path = lock_root / name
        if not path.is_file():
            raise V22Error(
                f"v22 formal admission is incomplete: {path} does not exist. "
                "Formal configs may not be materialized before the freeze artifacts exist."
            )
        locks[name] = {"payload": read_json(path), "path": path, "file_sha256": sha256_file(path)}

    source_lock_sha = locks["V22_SOURCE_LOCK.json"]["payload"]["source_lock_sha256"]
    for name in ("V22_ACTION_SEMANTICS.json", "V22_POSTURE_ATLAS.json", "V22_HINGE_RANGE_FREEZE.json",
                 "V22_POSTURE_BASELINE.json", "V22_POSTURE_GATE_FREEZE.json"):
        bound = locks[name]["payload"].get("source_lock_sha256")
        if bound != source_lock_sha:
            raise V22Error(f"{name} is bound to source lock {bound}, not {source_lock_sha}")

    freeze = locks["V22_POSTURE_GATE_FREEZE.json"]["payload"]
    gate_state = freeze["posture_gate_state"]
    waiver = None
    if gate_state != "BINDING":
        waiver_path = Path(repo_root) / V22_LOCK_ROOT / "V22_GATE_WAIVER_POSTURE_GATES_REPORT_ONLY.json"
        if not waiver_path.is_file():
            raise V22Error(
                f"posture_gate_state={gate_state!r} requires a signed POSTURE_GATES_REPORT_ONLY "
                f"waiver at {waiver_path} before any formal config may be promoted."
            )
        waiver = read_json(waiver_path)
        if waiver.get("decision") != "SUSPEND" or waiver.get("original_gate") != "posture_gates":
            raise V22Error("the posture-gate waiver must SUSPEND the posture_gates gate")
    if locks["V22_HINGE_RANGE_FREEZE.json"]["payload"]["hinge_randomization_state"] != "P0_D_FROZEN":
        raise V22Error("hinge randomization is not frozen; formal materialization is blocked")
    return {"locks": locks, "source_lock_sha256": source_lock_sha, "posture_waiver": waiver}


def _cell_overrides(cell: str, admission: Mapping[str, Any], *, formal: bool) -> list[str]:
    atlas = admission["locks"]["V22_POSTURE_ATLAS.json"]["payload"]
    freeze = admission["locks"]["V22_POSTURE_GATE_FREEZE.json"]["payload"]
    hinge = admission["locks"]["V22_HINGE_RANGE_FREEZE.json"]["payload"]
    semantics = admission["locks"]["V22_ACTION_SEMANTICS.json"]["payload"]

    def _list(values: Sequence[float]) -> str:
        return "[" + ",".join(f"{float(value):.6g}" for value in values) + "]"

    overrides = [
        # Measured constants are injected from the frozen artifacts so the config
        # file never becomes a second, drift-prone source of truth for them.
        f"+env.config.a2_v22_nominal_heights_m={_list(atlas['nominal_heights_m'])}",
        f"+env.config.a2_v22_nominal_pitch_rad={_list(atlas['nominal_pitch_rad'])}",
        f"+env.config.a2_v22_nominal_roll_rad={_list(atlas['nominal_roll_rad'])}",
        f"+env.config.a2_v22_directional_wrench_threshold_n={atlas['directional_wrench_threshold_n']:.6g}",
        f"+env.config.a2_v22_arm_tracking_error_p90={atlas['arm_tracking_error_p90_rad']:.6g}",
        f"+env.config.a2_v22_workspace_margin_threshold={atlas['workspace_margin_threshold']:.6g}",
        f"+env.config.a2_v22_source_lock_sha256={admission['source_lock_sha256']}",
        f"+env.config.a2_v22_action_semantics_sha256={semantics['action_semantics_sha256']}",
        f"+env.config.a2_v22_posture_gate_freeze_sha256={freeze['posture_gate_freeze_sha256']}",
        f"+env.config.a2_v22_hinge_range_freeze_sha256={hinge['hinge_range_freeze_sha256']}",
        f"+env.config.a2_v22_posture_gate_state={freeze['posture_gate_state']}",
    ]
    if formal:
        overrides.append("env.config.a2_v22_formal_launch=true")
    return overrides


def build_launch_plan(
    cells: Sequence[str],
    *,
    repo_root: Path = REPO_ROOT,
    smoke: bool = False,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    admission = load_admission(root)
    identity = git_identity(root)
    num_envs = SMOKE_ENVS if smoke else V22_FORMAL_ENVS
    batches = SMOKE_BATCHES if smoke else V22_FORMAL_BATCHES
    save_frequency = SMOKE_SAVE_FREQUENCY if smoke else V22_FORMAL_SAVE_FREQUENCY
    session = SMOKE_SESSION if smoke else FORMAL_SESSION
    output_root = root / (V22_SMOKE_ROOT if smoke else V22_TRAINING_ROOT)
    warm_start = root / V22_WARM_START_PATH
    if sha256_file(warm_start) != V22_WARM_START_SHA256:
        raise V22Error("v22 warm-start checkpoint hash does not match the frozen identity")

    rows = []
    for cell in cells:
        if cell not in V22_CELL_CONFIGS:
            raise V22Error(f"unknown v22 cell {cell!r}")
        gpu = require_gpu(V22_CELL_GPU[cell])
        config = root / V22_CELL_CONFIGS[cell]
        loaded = read_yaml(config)
        if loaded.get("scientific_plan_id") != V22_PLAN_ID:
            raise V22Error(f"{cell} config is not a v22 plan config")
        env_config = loaded.get("env", {}).get("config", {})
        if env_config.get("a2_v22_calibration_probe"):
            raise V22Error(f"{cell} config still carries a2_v22_calibration_probe=true")
        if env_config.get("a2_v20_R1_plan_id") != V22_PLAN_ID:
            raise V22Error(f"{cell} config does not declare the v22 plan id")
        if int(loaded.get("seed", -1)) != V22_CELL_SEED[cell]:
            raise V22Error(f"{cell} config seed does not match the frozen matrix")
        output = output_root / cell
        training_metrics_path = output / "r2_training_metrics.jsonl"
        # Ablation files are `# @package _global_` overlays, so they must be composed
        # onto base.yaml through the canonical +exp/+ablation groups rather than used
        # as a standalone primary config.
        argv = [
            "env",
            "-u",
            "CUDA_VISIBLE_DEVICES",
            f"ACCELERATE_TORCH_DEVICE=cuda:{gpu}",
            "WANDB_MODE=" + ("offline" if smoke else "online"),
            f"PYTHONPATH={root}",
            PYTHON_BIN,
            "-m",
            "gr00t.rl.train_agent_trl",
            f"+exp={V22_EXP_NAME}",
            f"+ablation=wbmanip/{config.stem}",
            f"project_name={V22_PROJECT_NAME}",
            f"experiment_name={cell}",
            f"experiment_dir={output}",
            f"checkpoint={V22_WARM_START_PATH}",
            "checkpoint_load_mode=policy_only",
            "auto_load_latest=false",
            "headless=true",
            f"use_wandb={'false' if smoke else 'true'}",
            f"num_envs={num_envs}",
            f"seed={V22_CELL_SEED[cell]}",
            f"algo.trl.num_total_batches={batches}",
            f"callbacks.model_save.save_frequency={save_frequency}",
            "+r2_evidence_enabled=true",
            f"+r2_source_lock_path={root / V22_LOCK_ROOT / 'V22_SOURCE_LOCK.json'}",
            f"+r2_training_metrics_path={training_metrics_path}",
            *_cell_overrides(cell, admission, formal=not smoke),
        ]
        rows.append(
            {
                "cell": cell,
                "physical_gpu": gpu,
                "seed": V22_CELL_SEED[cell],
                "config": str(config),
                "config_sha256": sha256_file(config),
                "output_root": str(output),
                "training_metrics_path": str(training_metrics_path),
                "argv": argv,
                "command_sha256": digest(argv),
                "tmux_window_argv": ["tmux", "new-window", "-d", "-t", session, "-n", cell, "--", *argv],
            }
        )

    initial = ["tmux", "new-session", "-d", "-s", session, "-n", rows[0]["cell"], "--", *rows[0]["argv"]]
    return artifact_payload(
        "smoke_plan" if smoke else "formal_plan",
        status="SMOKE_PLAN_COMPLETE" if smoke else "FORMAL_PLAN_COMPLETE",
        timestamp_utc=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        session=session,
        physical_gpus=sorted({row["physical_gpu"] for row in rows}),
        forbidden_physical_gpus=[2, 3, 4, 5, 6, 7],
        cells=list(cells),
        num_envs=num_envs,
        batches=batches,
        save_frequency=save_frequency,
        checkpoint=V22_WARM_START_PATH,
        checkpoint_sha256=V22_WARM_START_SHA256,
        checkpoint_load_mode="policy_only",
        source_lock_sha256=admission["source_lock_sha256"],
        admission_artifacts={
            name: entry["file_sha256"] for name, entry in admission["locks"].items()
        },
        posture_gate_state=admission["locks"]["V22_POSTURE_GATE_FREEZE.json"]["payload"][
            "posture_gate_state"
        ],
        posture_waiver_applied=admission["posture_waiver"] is not None,
        repo_commit=identity["commit"],
        repo_tree=identity["tree"],
        initial_session_argv=initial,
        rows=rows,
    )


def launch(plan: Mapping[str, Any], *, tmux_binary: str = "tmux") -> None:
    """Start a previously validated plan.  Resources are never silently downgraded."""
    for gpu in plan["physical_gpus"]:
        require_gpu(gpu)
    existing = subprocess.run(
        [tmux_binary, "has-session", "-t", plan["session"]], capture_output=True
    )
    if existing.returncode == 0:
        raise V22Error(f"tmux session {plan['session']!r} already exists; refusing to overlay it")
    subprocess.run([tmux_binary, *plan["initial_session_argv"][1:]], check=True)
    for row in plan["rows"][1:]:
        subprocess.run([tmux_binary, *row["tmux_window_argv"][1:]], check=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wave", type=int, choices=(1, 2, 3), default=1)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--launch", action="store_true")
    args = parser.parse_args(argv)

    cells = {1: V22_WAVE1_CELLS, 2: V22_WAVE2_CELLS, 3: V22_WAVE3_CELLS}[args.wave]
    plan = build_launch_plan(cells, smoke=args.smoke)
    name = f"V22_{'SMOKE' if args.smoke else 'FORMAL'}_WAVE{args.wave}_PLAN.json"
    target = REPO_ROOT / V22_LAUNCHER_ROOT / name
    write_json(target, plan)
    print(f"wrote {target}")
    for row in plan["rows"]:
        print(f"  {row['cell']} gpu={row['physical_gpu']} seed={row['seed']} -> {row['output_root']}")
    if args.launch:
        launch(plan)
        print(f"launched tmux session {plan['session']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
