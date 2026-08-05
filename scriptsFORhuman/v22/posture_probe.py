"""v22 posture probes: P0-A action semantics, P0-C live-grasp atlas, and the
P0-POSTURE-BASELINE same-denominator warm-start baseline.

All three run the frozen ``B1@500`` warm start through the ordinary evaluation
path and read the standard ``stage2_5_step_trace.json``.  The only difference
between them is which declared posture intervention is active.

Command-side and achieved-side posture are never interchanged here: the command
comes from ``v22_posture_command_*`` and the achieved angle from ``root_*``.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Iterable, Sequence

from ._v22_common import (
    PYTHON_BIN,
    REPO_ROOT,
    V22_ARTIFACT_ROOT,
    V22_PLAN_ID,
    V22_WARM_START_PATH,
    V22_WARM_START_SHA256,
    V22Error,
    require_gpu,
)


# §7.2 registered posture grid.
PITCH_GRID_RAD = (-0.25, -0.10, 0.00, 0.10, 0.25)
ROLL_GRID_RAD = (-0.15, 0.00, 0.15)
HANDLE_HEIGHT_BOUNDS = (0.85, 1.10)
PROBE_NUM_ENVS = 16

# Bootstrap constants for calibration probes.  They only enter posture-need
# classification, which every calibration probe discards; the measured
# telemetry (wrench, margin, tracking error) does not depend on them.  Any config
# carrying a2_v22_calibration_probe=true is refused by the formal launcher.
BOOTSTRAP_NOMINAL_HEIGHTS = (0.85, 1.10)
BOOTSTRAP_NOMINAL_PITCH = (0.0, 0.0)
BOOTSTRAP_NOMINAL_ROLL = (0.0, 0.0)
BOOTSTRAP_WRENCH_THRESHOLD_N = 1.0
BOOTSTRAP_TRACKING_P90_RAD = 1.0
BOOTSTRAP_MARGIN_THRESHOLD = 0.15

DIAGNOSTIC_REWARD_TERMS = (
    "push_door_hinge",
    "a2_stage3_unlatch_hold",
    "a2_stage3_stage4_hold_and_drive",
    "a2_corridor_door_wide",
    "a2_corridor_clean_passage",
    "penalty_a2_door_body_contact",
    "complete",
)


def _list_override(values: Iterable[float]) -> str:
    return "[" + ",".join(f"{float(value):.6g}" for value in values) + "]"


def build_probe_argv(
    *,
    output_dir: Path,
    eval_name: str,
    seed: int,
    intervention: str,
    fixed_rad: tuple[float, float] | None = None,
    clamp_rad: tuple[float, float] | None = None,
    nominal_heights: Sequence[float] = BOOTSTRAP_NOMINAL_HEIGHTS,
    nominal_pitch: Sequence[float] = BOOTSTRAP_NOMINAL_PITCH,
    nominal_roll: Sequence[float] = BOOTSTRAP_NOMINAL_ROLL,
    wrench_threshold_n: float = BOOTSTRAP_WRENCH_THRESHOLD_N,
    tracking_p90_rad: float = BOOTSTRAP_TRACKING_P90_RAD,
    workspace_margin_threshold: float = BOOTSTRAP_MARGIN_THRESHOLD,
    calibration_probe: bool = True,
    repo_root: Path = REPO_ROOT,
) -> list[str]:
    """Build the exact evaluation command for one v22 posture probe."""
    checkpoint = (Path(repo_root) / V22_WARM_START_PATH).resolve()
    if not checkpoint.is_file():
        raise V22Error(f"v22 warm start is missing: {checkpoint}")
    argv = [
        PYTHON_BIN,
        "-m",
        "gr00t.rl.eval_agent_trl",
        f"+checkpoint={checkpoint}",
        "++checkpoint_load_mode=full",
        "++auto_load_latest=false",
        "++headless=true",
        f"++num_envs={PROBE_NUM_ENVS}",
        f"++seed={seed}",
        "++use_wandb=false",
        "++simulator.config.cameras.enable_cameras=false",
        "++simulator.config.render_results=false",
        f"++algo.config.eval.num_eval_episodes={PROBE_NUM_ENVS}",
        "++algo.config.eval.eval_num_envs_episodes=true",
        "++algo.config.eval.a2_diagnostic_trace_enabled=true",
        "++algo.config.eval.a2_diagnostic_reward_terms=[" + ",".join(DIAGNOSTIC_REWARD_TERMS) + "]",
        "++algo.config.eval.a2_eval_v20_strict_telemetry=false",
        "++algo.config.eval.a2_eval_m41_strict_telemetry=false",
        "++algo.config.eval.save_videos=false",
        "++algo.config.eval.save_trajectories=false",
        "++env.config.a2_eval_door_handle_height_linspace="
        + _list_override(HANDLE_HEIGHT_BOUNDS),
        # v22 identity: switching the plan id takes this run off the v21-B
        # materialization chain and onto the v22 telemetry path.
        f"++env.config.a2_v20_R1_plan_id={V22_PLAN_ID}",
        "++env.config.a2_v20_send_hinge_threshold=0.90",
        "++env.config.a2_v20_R2_evidence_enabled=false",
        "++env.config.a2_v21B_evidence_enabled=false",
        "++env.config.a2_v22_evidence_enabled=true",
        "++env.config.a2_v22_posture_enabled=true",
        "++env.config.a2_v22_posture_telemetry_only=true",
        "++env.config.a2_v22_clearance_enabled=true",
        "++env.config.a2_v22_body_assist_enabled=false",
        f"++env.config.a2_v22_calibration_probe={str(bool(calibration_probe)).lower()}",
        "++env.config.a2_v22_nominal_heights_m=" + _list_override(nominal_heights),
        "++env.config.a2_v22_nominal_pitch_rad=" + _list_override(nominal_pitch),
        "++env.config.a2_v22_nominal_roll_rad=" + _list_override(nominal_roll),
        f"++env.config.a2_v22_directional_wrench_threshold_n={float(wrench_threshold_n):.6g}",
        f"++env.config.a2_v22_arm_tracking_error_p90={float(tracking_p90_rad):.6g}",
        f"++env.config.a2_v22_workspace_margin_threshold={float(workspace_margin_threshold):.6g}",
        f"++eval_name={eval_name}",
        f"++eval_output_dir={Path(output_dir).resolve()}",
    ]
    if intervention != "legacy":
        argv.append("++env.config.a2_v22_posture_intervention_probe=true")
        argv.append(f"++env.config.a2_v22_posture_intervention={intervention}")
        if intervention == "fixed":
            if fixed_rad is None:
                raise V22Error("a fixed posture intervention requires fixed_rad")
            argv.append(
                "++env.config.a2_v22_posture_intervention_fixed_rad=" + _list_override(fixed_rad)
            )
        if intervention == "clamp":
            if clamp_rad is None:
                raise V22Error("a clamp posture intervention requires clamp_rad")
            argv.append(
                "++env.config.a2_v22_posture_intervention_clamp_rad=" + _list_override(clamp_rad)
            )
    return argv


def run_probe(argv: Sequence[str], *, gpu: int, output_dir: Path) -> Path:
    """Run one probe to completion; a non-zero child is terminal."""
    require_gpu(gpu)
    target = Path(output_dir).resolve()
    target.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.update(
        {
            "CUDA_VISIBLE_DEVICES": str(gpu),
            "ACCELERATE_TORCH_DEVICE": "cuda:0",
            "PYTHONPATH": str(REPO_ROOT),
            "VK_ICD_FILENAMES": "/usr/share/vulkan/icd.d/nvidia_icd.json",
        }
    )
    (target / "probe_command.json").write_text(
        json.dumps({"argv": list(argv), "gpu": gpu}, indent=1), encoding="utf-8"
    )
    with (target / "probe_stdout.log").open("wb") as out:
        result = subprocess.run(argv, cwd=REPO_ROOT, env=env, stdout=out, stderr=subprocess.STDOUT)
    if result.returncode != 0:
        raise V22Error(f"v22 probe exited {result.returncode}; see {target / 'probe_stdout.log'}")
    trace = _find_trace(target)
    if trace is None:
        raise V22Error(f"v22 probe produced no stage2_5_step_trace.json under {target}")
    return trace


def _find_trace(root: Path) -> Path | None:
    matches = sorted(Path(root).rglob("stage2_5_step_trace.json"))
    return matches[-1] if matches else None


def load_trace(path: Path) -> list[dict[str, Any]]:
    rows = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(rows, list) or not rows:
        raise V22Error(f"v22 probe trace is empty: {path}")
    missing = [key for key in ("v22_schema", "root_pitch", "root_roll") if key not in rows[0]]
    if missing:
        raise V22Error(f"v22 probe trace is missing required fields {missing}: {path}")
    return rows


def live_grasp_rows(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """§7.2 valid live-grasp states, using only criteria this trace can support.

    Enforced per frame: opening/swing stage, bilateral hold, no door-frame contact.
    The §7.2 joint-position margin floor is a property of a *posture cell*, not of an
    individual frame, and is applied at selection time — the warm start spends most
    of a valid hold below 0.10 margin, so filtering frames on it would discard 95% of
    the live-grasp evidence rather than screen postures.  The support-margin and
    TCP-error criteria are absent from this trace schema and are recorded as
    unenforced rather than silently assumed satisfied.
    """
    selected = []
    for row in rows:
        if int(row["stage_buf"]) not in (3, 4):
            continue
        if not bool(row.get("both_contact")):
            continue
        if float(row.get("doorframe_contact_force", 0.0)) > 0.0:
            continue
        selected.append(row)
    return selected


LIVE_GRASP_CRITERIA = {
    "enforced_per_frame": [
        "stage in {OPEN, SWING}",
        "bilateral hold (both_contact)",
        "no door-frame contact",
    ],
    "enforced_per_posture_cell": ["median arm joint-position margin >= 0.10 (hard limits)"],
    "not_enforced_absent_from_trace_schema": [
        "support margin >= 0.03 m",
        "TCP error <= 0.03 m",
    ],
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gpu", type=int, required=True)
    parser.add_argument("--intervention", default="legacy", choices=("legacy", "zero", "clamp", "fixed"))
    parser.add_argument("--fixed-pitch", type=float, default=None)
    parser.add_argument("--fixed-roll", type=float, default=None)
    parser.add_argument("--clamp-pitch", type=float, default=None)
    parser.add_argument("--clamp-roll", type=float, default=None)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--name", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    fixed = None
    if args.intervention == "fixed":
        if args.fixed_pitch is None or args.fixed_roll is None:
            raise V22Error("fixed intervention requires --fixed-pitch and --fixed-roll")
        fixed = (args.fixed_pitch, args.fixed_roll)
    clamp = None
    if args.intervention == "clamp":
        if args.clamp_pitch is None or args.clamp_roll is None:
            raise V22Error("clamp intervention requires --clamp-pitch and --clamp-roll")
        clamp = (args.clamp_pitch, args.clamp_roll)

    command = build_probe_argv(
        output_dir=args.out,
        eval_name=args.name,
        seed=args.seed,
        intervention=args.intervention,
        fixed_rad=fixed,
        clamp_rad=clamp,
    )
    trace = run_probe(command, gpu=args.gpu, output_dir=args.out)
    print(f"trace={trace}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
