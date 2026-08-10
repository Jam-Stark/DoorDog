"""P0.8 preformal-v2 forward-intervention PLAN/RUN/REDUCE orchestration.

The runner executes four short, forward-only trigger checks.  It owns only the
fresh mode roots below ``logs_eval/base_v23/p0/interventions/preformal_v2``;
historical R78 state-bank evidence is read and never rewritten.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from ._v23_common import REPO_ROOT, V23Error, emit_payload, require_file, write_json
except ImportError:  # direct script invocation
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from scriptsFORhuman.v23._v23_common import (
        REPO_ROOT,
        V23Error,
        emit_payload,
        require_file,
        write_json,
    )


SCHEMA = "a2_piper_v23_p08_preformal_v2_plan_v1"
RAW_SCHEMA = "a2_piper_v23_p08_preformal_v2_raw_v1"
RECEIPT_SCHEMA = "a2_piper_v23_p08_preformal_v2_receipt_v1"
CONFIG_OVERRIDE = "wbmanip/base_v23_p08_preformal_v2"
PROJECT_PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
RAW_FILENAME = "a2_v23_p08_v2_raw.json"
RECEIPT_FILENAME = "p08_preformal_v2_receipt.json"
R78_PATH = REPO_ROOT / "logs_eval/base_v23/p0/state_bank/state_bank_plan.json"
DEFAULT_ROOT = (
    REPO_ROOT / "logs_eval/base_v23/p0/interventions/preformal_v2"
)
MODES = (
    "ACUTE_RP0",
    "BASE0_AT_GRASP",
    "HIGHER_EFFORT_RESCUE",
    "ORACLE_TANGENTIAL_ASSIST",
)
PHYSICAL_GPU = {
    "ACUTE_RP0": 0,
    "BASE0_AT_GRASP": 0,
    "HIGHER_EFFORT_RESCUE": 1,
    "ORACLE_TANGENTIAL_ASSIST": 1,
}
EXCLUDED_CLAIMS = (
    "NO_CAUSAL_EFFECT_CLAIM",
    "NO_POLICY_QUALITY_CLAIM",
    "NO_EXACT_STATE_CLONE",
    "NO_RECURRENT_STATE_RESTORE",
    "NO_ACTUAL_PHYSX_TORQUE_CLAIM",
    "NO_ROUTE_B_SUITE_EXECUTION",
)


def _number(value: Any, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise V23Error(f"{name} must be numeric")
    value = float(value)
    if not math.isfinite(value):
        raise V23Error(f"{name} must be finite")
    return value


def _require_r78() -> dict[str, Any]:
    path = require_file(R78_PATH, label="unchanged R78 state-bank receipt")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise V23Error(f"R78 state-bank receipt is invalid JSON: {path}") from exc
    if (
        payload.get("schema") != "a2_piper_v23_p08_partial_a0_d0_receipt_v1"
        or payload.get("status") != "PARTIAL_A0_D0_PLUMBING_RUNTIME_VERIFIED"
        or payload.get("p08_overall_status") != "PARTIAL_INCOMPLETE"
        or payload.get("formal_admission") is not False
        or payload.get("release_receipt") is not False
    ):
        raise V23Error("R78 state-bank receipt is not the unchanged partial A0/D0 record")
    if payload.get("binding_count") != 15 or payload.get("captured_stages") != [2, 3, 4]:
        raise V23Error("R78 state-bank receipt does not preserve the 3-stage/15-binding plumbing")
    return payload


def _run_root(root: Path, mode: str) -> Path:
    root = Path(root).resolve()
    if root != DEFAULT_ROOT and DEFAULT_ROOT not in root.parents:
        raise V23Error(
            "P0.8 preformal-v2 output root must remain under "
            f"{DEFAULT_ROOT}"
        )
    if mode not in MODES:
        raise V23Error(f"unsupported P0.8 preformal-v2 mode: {mode!r}")
    return root / mode.lower()


def build_run_command(*, mode: str, output_root: Path) -> tuple[list[str], dict[str, str]]:
    if mode not in MODES:
        raise V23Error(f"unsupported P0.8 preformal-v2 mode: {mode!r}")
    output_root = _run_root(output_root, mode)
    checkpoint = require_file(
        REPO_ROOT / "logs_rl/a2_piper_full_stage_a2_base/base_v22/G1/model_step_001250.pt",
        label="P0.8 preformal-v2 warm checkpoint",
    )
    warm_config = require_file(
        REPO_ROOT / "logs_rl/a2_piper_full_stage_a2_base/base_v22/G1/config.yaml",
        label="P0.8 preformal-v2 warm config",
    )
    project_python = require_file(
        PROJECT_PYTHON.resolve(), label="approved IsaacLab Python"
    )
    common = [
        str(PROJECT_PYTHON),
        "-m",
        "gr00t.rl.eval_agent_trl",
        f"+ablation={CONFIG_OVERRIDE}",
        f"++checkpoint={checkpoint}",
        f"++checkpoint_load_mode=policy_only",
        "++auto_load_latest=false",
        "++num_envs=1",
        "++num_gpus=1",
        "++multi_gpu=false",
        "++seed=0",
        "++headless=true",
        "++use_wandb=false",
        "++algo.trl.report_to=none",
        "++algo.config.num_mini_batches=1",
        "++algo.config.eval.eval_num_envs_episodes=true",
        "++algo.config.eval.num_eval_episodes=1",
        "++algo.config.eval.a2_v23_p05_runtime_export=false",
        "++algo.config.eval.a2_v23_p08_state_bank_export=false",
        "++algo.config.eval.a2_v23_p08_v2_export=true",
        "++algo.config.eval.a2_v23_p08_v2_record_env_id=0",
        f"++algo.config.eval.a2_v23_p08_v2_raw_filename={RAW_FILENAME}",
        "++env.config.a2_v20_R2_evidence_enabled=false",
        "++env.config.a2_v23_p05_runtime_enabled=false",
        "++env.config.a2_v23_forward_intervention_mode=null",
        "++env.config.a2_v23_p08_v2_enabled=true",
        f"++env.config.a2_v23_p08_v2_mode={mode}",
        f"++env.config.a2_v23_p08_v2_checkpoint={checkpoint}",
        f"++env.config.a2_v23_p08_v2_config_id={warm_config}",
        "++env.config.a2_v23_p08_v2_scenario_id=A0_preformal_v2",
        "++env.config.a2_v23_p08_v2_seed=0",
        "++env.config.a2_v23_p08_v2_low_progress_min_rad=0.02",
        "++env.config.a2_v23_p08_v2_low_progress_max_rad=0.04",
        "++env.config.a2_v23_p08_v2_low_progress_window_min_steps=25",
        "++env.config.a2_v23_p08_v2_low_progress_window_max_steps=40",
        "++env.config.a2_v23_p08_v2_stable_grasp_min_steps=20",
        "++env.config.a2_v23_p08_v2_clipped_utilization_min=0.9",
        "++env.config.a2_v23_p08_v2_clipped_fraction_min=0.3",
        "++env.config.a2_v23_p08_v2_rescue_effort_limit_nm=100.0",
        "++simulator.config.cameras.enable_cameras=false",
        "++simulator.config.render_results=false",
        f"++eval_output_dir={output_root}",
    ]
    if mode == "ORACLE_TANGENTIAL_ASSIST":
        common.extend(
            [
                "++env.config.a2_v23_p08_v2_oracle_tangential_delta_raw=[[0.0,0.0,0.0,0.05,0.05]]",
            ]
        )
    else:
        common.extend(
            [
                "++env.config.a2_v23_p08_v2_oracle_tangential_delta_raw=null",
            ]
        )
    return common, {
        "CUDA_VISIBLE_DEVICES": str(PHYSICAL_GPU[mode]),
        "ACCELERATE_TORCH_DEVICE": "cuda:0",
        "WANDB_MODE": "disabled",
        "PYTHONPATH": str(REPO_ROOT),
    }


def build_plan(*, output_root: Path = DEFAULT_ROOT) -> dict[str, Any]:
    """Build all four fresh sequential runs without launching Isaac Sim."""

    root = Path(output_root).resolve()
    _require_r78()
    runs = []
    for index, mode in enumerate(MODES):
        run_root = _run_root(root, mode)
        command, env = build_run_command(mode=mode, output_root=root)
        runs.append(
            {
                "mode": mode,
                "run_index": index,
                "physical_gpu": PHYSICAL_GPU[mode],
                "logical_gpu": "cuda:0",
                "num_envs": 1,
                "num_gpus": 1,
                "multi_gpu": False,
                "single_process": True,
                "output_root": str(run_root),
                "raw_path": str(run_root / RAW_FILENAME),
                "argv": command,
                "command": shlex.join(command),
                "environment": env,
                "retry_policy": "none",
            }
        )
    return {
        "schema": SCHEMA,
        "status": "PLAN_ONLY",
        "plan_id": "base_v23_force_feasibility_initialization_posture_R1",
        "r78_path": str(R78_PATH),
        "r78_required_status": "PARTIAL_A0_D0_PLUMBING_RUNTIME_VERIFIED",
        "root": str(root),
        "modes": list(MODES),
        "gpu_serial_order": {
            "GPU0": ["ACUTE_RP0", "BASE0_AT_GRASP"],
            "GPU1": ["HIGHER_EFFORT_RESCUE", "ORACLE_TANGENTIAL_ASSIST"],
        },
        "runs": runs,
        "excluded_claims": list(EXCLUDED_CLAIMS),
        "route_b_suite_status": "DEFERRED_TO_SELECTED_CHECKPOINTS",
        "state_clone_supported": False,
        "recurrent_state_restore_supported": False,
    }


def execute_plan(*, output_root: Path = DEFAULT_ROOT) -> dict[str, Any]:
    """Run each mode once in the fixed two-GPU serial order, without retries."""

    root = Path(output_root).resolve()
    plan = build_plan(output_root=root)
    # build_plan validates R78 and command identity.  RUN now creates each
    # fresh mode directory exactly once; no mode may reuse a prior artifact.
    completed = []
    for run in plan["runs"]:
        mode = run["mode"]
        run_root = Path(run["output_root"])
        if run_root.exists():
            raise V23Error(f"refusing to reuse non-empty preformal-v2 run root: {run_root}")
        run_root.mkdir(parents=True, exist_ok=False)
        command, env = build_run_command(mode=mode, output_root=root)
        result = subprocess.run(
            command,
            cwd=REPO_ROOT,
            env={**os.environ, **env},
            check=False,
        )
        if result.returncode != 0:
            raise V23Error(
                f"P0.8 preformal-v2 {mode} evaluator failed with returncode={result.returncode}"
            )
        raw_path = run_root / RAW_FILENAME
        if not raw_path.is_file():
            raise V23Error(f"{mode} evaluator exited without its raw record: {raw_path}")
        completed.append(
            {
                "mode": mode,
                "physical_gpu": PHYSICAL_GPU[mode],
                "logical_gpu": "cuda:0",
                "returncode": int(result.returncode),
                "raw_path": str(raw_path),
                "command": shlex.join(command),
            }
        )
    return {**plan, "status": "RUN_COMPLETED", "completed_runs": completed}


def _raw_path_map(root: Path) -> dict[str, Path]:
    root = Path(root).resolve()
    return {mode: _run_root(root, mode) / RAW_FILENAME for mode in MODES}


def _action_values(record: Mapping[str, Any]) -> tuple[list[float], list[float]]:
    proof = record.get("action_proof")
    if not isinstance(proof, Mapping):
        raise V23Error("raw record is missing action_proof")
    pre = proof.get("pre_action_5d")
    post = proof.get("post_action_5d")
    if not isinstance(pre, list) or not isinstance(post, list) or len(pre) != 5 or len(post) != 5:
        raise V23Error("raw action proof must contain finite five-dimensional pre/post actions")
    pre = [_number(value, name="pre_action_5d") for value in pre]
    post = [_number(value, name="post_action_5d") for value in post]
    return pre, post


def _validate_raw(mode: str, path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.is_file():
        return None, "MISSING_RECORD"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None, "RUNTIME_FAILURE"
    if not isinstance(payload, Mapping) or payload.get("schema") != RAW_SCHEMA:
        return None, "MISSING_RECORD"
    if payload.get("mode") != mode:
        return None, "MISSING_RECORD"
    if payload.get("state_clone_supported") is not False or payload.get("recurrent_state_restore_supported") is not False:
        return None, "MISSING_RECORD"
    if (
        payload.get("logical_gpu") != "cuda:0"
        or payload.get("process_count") != 1
        or payload.get("env_count") != 1
        or payload.get("num_envs") != 1
    ):
        return None, "RUNTIME_FAILURE"
    if payload.get("status") == "RUNTIME_FAILURE":
        return dict(payload), "RUNTIME_FAILURE"
    if payload.get("status") != "TRIGGERED" or not isinstance(payload.get("switch_step"), int) or payload["switch_step"] < 0:
        return dict(payload), "NOT_TRIGGERED"
    latch = payload.get("observed_latch")
    if not isinstance(latch, Mapping) or latch.get("observed") is not True:
        return dict(payload), "NOT_TRIGGERED"
    try:
        pre, post = _action_values(payload)
    except V23Error:
        return dict(payload), "ACTION_READBACK_MISMATCH"
    if mode in ("ACUTE_RP0", "BASE0_AT_GRASP"):
        if post[3:] != [0.0, 0.0]:
            return dict(payload), "ACTION_READBACK_MISMATCH"
        expected_event = "EPISODE_START" if mode == "ACUTE_RP0" else "STABLE_GRASP_LATCH"
        if latch.get("event") != expected_event:
            return dict(payload), "NOT_TRIGGERED"
    elif mode == "HIGHER_EFFORT_RESCUE":
        if latch.get("event") != "TYPED_FAILURE_LATCH":
            return dict(payload), "NOT_TRIGGERED"
        readback = payload.get("mode_readback")
        if not isinstance(readback, Mapping):
            return dict(payload), "EFFORT_READBACK_MISMATCH"
        applied = readback.get("applied_profile")
        requested = readback.get("requested_profile")
        if (
            not isinstance(applied, Mapping)
            or not isinstance(requested, Mapping)
            or applied.get("status") != "APPLIED"
            or requested.get("status") != "REQUESTED"
        ):
            return dict(payload), "EFFORT_READBACK_MISMATCH"
        requested_values = requested.get("effort_limit_nm")
        readback_values = applied.get("readback_effort_limit_nm")
        if (
            not isinstance(requested_values, (int, float))
            or not isinstance(readback_values, list)
            or len(readback_values) != 6
            or any(abs(_number(value, name="effort_readback") - float(requested_values)) > 1.0e-5 for value in readback_values)
        ):
            return dict(payload), "EFFORT_READBACK_MISMATCH"
    else:
        if latch.get("event") != "TYPED_FAILURE_LATCH":
            return dict(payload), "NOT_TRIGGERED"
        readback = payload.get("mode_readback")
        if not isinstance(readback, Mapping):
            return dict(payload), "ACTION_READBACK_MISMATCH"
        delta = readback.get("delta_raw")
        if not isinstance(delta, list) or len(delta) != 1 or not isinstance(delta[0], list) or len(delta[0]) != 5:
            return dict(payload), "ACTION_READBACK_MISMATCH"
        if any(abs(post[index] - (pre[index] + _number(delta[0][index], name="oracle_delta"))) > 1.0e-5 for index in range(5)):
            return dict(payload), "ACTION_READBACK_MISMATCH"
    return dict(payload), None


def reduce_raw_records(
    *, raw_paths: Mapping[str, Path] | None = None, output: Path, output_root: Path = DEFAULT_ROOT
) -> tuple[dict[str, Any], int]:
    """Consume exactly four raw mode records and write the P0.8-only receipt."""

    _require_r78()
    paths = dict(raw_paths) if raw_paths is not None else _raw_path_map(Path(output_root))
    if set(paths) != set(MODES):
        raise V23Error("P0.8 preformal-v2 REDUCE requires exactly four named mode paths")
    records = []
    incomplete = []
    for mode in MODES:
        record, reason = _validate_raw(mode, Path(paths[mode]))
        if record is None:
            incomplete.append({"mode": mode, "reason": reason or "MISSING_RECORD"})
            continue
        records.append(record)
        if reason is not None:
            incomplete.append({"mode": mode, "reason": reason})
    complete = not incomplete and len(records) == 4
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "status": "P0_8_PREFORMAL_COMPLETE" if complete else "P0_8_PREFORMAL_INCOMPLETE",
        "p08_preformal_gate": bool(complete),
        "route_b_suite_status": "DEFERRED_TO_SELECTED_CHECKPOINTS",
        "r78_path": str(R78_PATH),
        "r78_unchanged_required": True,
        "raw_record_count": len(records),
        "records": records,
        "incomplete_reasons": incomplete,
        "state_clone_supported": False,
        "recurrent_state_restore_supported": False,
        "formal_admission": False,
        "release_receipt": False,
        "excluded_claims": list(EXCLUDED_CLAIMS)
        + ["NO_GLOBAL_FORMAL_ADMISSION_FLAG_FROM_P08_ALONE"],
    }
    output = Path(output).resolve()
    write_json(output, receipt)
    return receipt, (0 if complete else 2)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("PLAN", "RUN", "REDUCE"), required=True)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)
    output_root = Path(args.output_root).resolve()
    if args.mode == "PLAN":
        payload = build_plan(output_root=output_root)
        if args.output is None:
            emit_payload(payload)
        else:
            emit_payload(payload, args.output)
        return 0
    if args.mode == "RUN":
        payload = execute_plan(output_root=output_root)
        emit_payload(payload, args.output)
        return 0
    output = (
        Path(args.output).resolve()
        if args.output is not None
        else output_root / RECEIPT_FILENAME
    )
    receipt, exit_code = reduce_raw_records(output=output, output_root=output_root)
    emit_payload(receipt)
    return exit_code


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except V23Error as exc:
        raise SystemExit(f"V23 P0.8 PREFORMAL-V2 FAIL: {exc}")
