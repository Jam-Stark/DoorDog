"""Selected-checkpoint Route-B forward-intervention evaluator.

Five modes are executed through the existing generic v23 forward kernel.  The
records explicitly remain forward-only: this module does not claim exact
PhysX state cloning, recurrent-state restoration, causal effects, or physical
torque changes.  A runtime job is complete only when its raw canonical16
evidence is complete; outcome adjudication remains a typed pending field.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from ._v23_common import (
        REPO_ROOT,
        V23_FORMAL_CELL_CONFIGS,
        V23_FORMAL_CELL_GPU,
        V23_INTERVENTION_MODES,
        V23_LEGAL_PHYSICAL_GPUS,
        V23_PLAN_ID,
        V23Error,
        write_json,
    )
    from .pooled48 import (
        POOLED48_RECEIPT_PATH,
        POOLED48_SCHEMA,
        POOLED48_STATUS,
        SUBWAVE_ORDER,
        _absolute as _pooled_absolute,
        _job_plan as _pooled_job_plan,
        load_selected_candidates,
        validate_selected_candidates,
    )
    from .stratified_eval import STRATIFIED_RECEIPT_PATH, STRATIFIED_SCHEMA, STRATIFIED_STATUS
except ImportError:  # direct ``python scriptsFORhuman/v23/intervention_eval.py``
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from scriptsFORhuman.v23._v23_common import (
        REPO_ROOT,
        V23_FORMAL_CELL_CONFIGS,
        V23_FORMAL_CELL_GPU,
        V23_INTERVENTION_MODES,
        V23_LEGAL_PHYSICAL_GPUS,
        V23_PLAN_ID,
        V23Error,
        write_json,
    )
    from scriptsFORhuman.v23.pooled48 import (
        POOLED48_RECEIPT_PATH,
        POOLED48_SCHEMA,
        POOLED48_STATUS,
        SUBWAVE_ORDER,
        _absolute as _pooled_absolute,
        _job_plan as _pooled_job_plan,
        load_selected_candidates,
        validate_selected_candidates,
    )
    from scriptsFORhuman.v23.stratified_eval import STRATIFIED_RECEIPT_PATH, STRATIFIED_SCHEMA, STRATIFIED_STATUS


PROJECT_PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
EVAL_EXPERIMENT = "wbmanip/door_open_a2_base_lstm"
INTERVENTION_SCHEMA = "a2_piper_v23_intervention_record_v1"
INTERVENTION_JOB_SCHEMA = "a2_piper_v23_intervention_job_receipt_v1"
INTERVENTION_JOB_STATUS = "V23_INTERVENTION_JOB_COMPLETE"
INTERVENTION_PLAN_SCHEMA = "a2_piper_v23_intervention_plan_v1"
INTERVENTION_RECEIPT_SCHEMA = "a2_piper_v23_intervention_eval_receipt_v1"
INTERVENTION_RECEIPT_STATUS = "V23_INTERVENTION_EVAL_COMPLETE"
INTERVENTION_ROOT = REPO_ROOT / "logs_eval/base_v23/interventions"
INTERVENTION_RECEIPT_PATH = INTERVENTION_ROOT / "V23_INTERVENTION_EVAL.json"
INTERVENTION_PLAN_PATH = INTERVENTION_ROOT / "V23_INTERVENTION_EVAL_PLAN.json"
INTERVENTION_TOPOLOGY = "canonical16"
INTERVENTION_NUM_ENVS = 16
INTERVENTION_EPISODES = 16

SWITCH_RULES = {
    "FULL": {"switch_event": "none", "posture_policy": "trained_policy"},
    "ACUTE_RP0": {"switch_event": "episode_start", "posture_policy": "rp0_distribution_mask"},
    "BASE0_AT_GRASP": {"switch_event": "stable_grasp_latch", "posture_policy": "base0_neutral"},
    "HIGHER_EFFORT_RESCUE": {"switch_event": "typed_failure_latch", "posture_policy": "higher_effort_forward_only"},
    "ORACLE_TANGENTIAL_ASSIST": {"switch_event": "typed_failure_latch", "posture_policy": "oracle_eval_only"},
}
ORACLE_DELTA_ROW = [0.0, 0.0, 0.0, 0.05, 0.05]


class InterventionEvalError(V23Error):
    """An intervention source, command, or receipt contract is invalid."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _absolute(path: str | Path) -> Path:
    return _pooled_absolute(path)


def _load_any(path: str | Path) -> Any:
    target = _absolute(path)
    if target.is_symlink() or not target.is_file():
        raise InterventionEvalError(f"required intervention input is missing: {target}")
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise InterventionEvalError(f"intervention input is not valid JSON: {target}") from exc


def _load_object(path: str | Path) -> dict[str, Any]:
    value = _load_any(path)
    if not isinstance(value, dict):
        raise InterventionEvalError(f"intervention input must be an object: {_absolute(path)}")
    return value


def _load_upstream(
    *,
    pooled_receipt: str | Path = POOLED48_RECEIPT_PATH,
    stratified_receipt: str | Path = STRATIFIED_RECEIPT_PATH,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    pooled = _load_object(pooled_receipt)
    stratified = _load_object(stratified_receipt)
    if pooled.get("schema") != POOLED48_SCHEMA or pooled.get("status") != POOLED48_STATUS:
        raise InterventionEvalError(f"pooled48 upstream receipt is not complete: {_absolute(pooled_receipt)}")
    if stratified.get("schema") != STRATIFIED_SCHEMA or stratified.get("status") != STRATIFIED_STATUS:
        raise InterventionEvalError(f"stratified upstream receipt is not complete: {_absolute(stratified_receipt)}")
    pooled_selected = validate_selected_candidates(pooled.get("selected_candidates"), require_sources=False)
    stratified_selected = validate_selected_candidates(stratified.get("selected_candidates"), require_sources=False)
    if pooled_selected != stratified_selected:
        raise InterventionEvalError("stratified selected_candidates do not exactly match pooled48")
    return pooled, stratified, pooled_selected


def _candidate_root(candidate: Mapping[str, Any], mode: str) -> Path:
    return (
        INTERVENTION_ROOT
        / f"seed{candidate['seed']}"
        / str(candidate["cell"])
        / f"step{int(candidate['step']):04d}"
        / mode
        / INTERVENTION_TOPOLOGY
    )


def _oracle_matrix() -> list[list[float]]:
    return [list(ORACLE_DELTA_ROW) for _ in range(INTERVENTION_NUM_ENVS)]


def _command(candidate: Mapping[str, Any], mode: str, output: Path) -> list[str]:
    if mode not in V23_INTERVENTION_MODES:
        raise InterventionEvalError(f"unsupported v23 intervention mode: {mode!r}")
    gpu = int(V23_FORMAL_CELL_GPU[candidate["cell"]])
    if gpu not in V23_LEGAL_PHYSICAL_GPUS:
        raise InterventionEvalError(f"selected cell maps to illegal physical GPU {gpu}")
    config = Path(str(candidate["config_path"]))
    command = [
        str(PROJECT_PYTHON),
        "-m",
        "gr00t.rl.eval_agent_trl",
        f"+exp={EVAL_EXPERIMENT}",
        f"+ablation=wbmanip/{config.stem}",
        f"++checkpoint={candidate['checkpoint_path']}",
        "++checkpoint_load_mode=policy_only",
        "++auto_load_latest=false",
        "++headless=true",
        f"++num_envs={INTERVENTION_NUM_ENVS}",
        "++num_gpus=1",
        "++multi_gpu=false",
        f"++seed={candidate['seed']}",
        "++use_wandb=false",
        "++simulator.config.cameras.enable_cameras=false",
        "++simulator.config.render_results=false",
        f"++algo.config.eval.num_eval_episodes={INTERVENTION_EPISODES}",
        "++algo.config.eval.eval_num_envs_episodes=true",
        "++algo.config.eval.a2_diagnostic_trace_enabled=true",
        "++algo.config.num_mini_batches=1",
        "++env.config.a2_v23_route_a_unsafe_contact_enabled=false",
        "++algo.config.eval.a2_v23_route_a_unsafe_contact_export=false",
        "++algo.config.eval.save_videos=false",
        "++algo.config.eval.save_trajectories=false",
        f"++env.config.a2_v23_forward_intervention_mode={mode}",
        f"++eval_output_dir={output}",
        "++v23_route_b_topology=canonical16_intervention",
        f"++v23_route_b_candidate_subwave={candidate['subwave']}",
        f"++v23_route_b_candidate_cell={candidate['cell']}",
        f"++v23_route_b_candidate_step={candidate['step']}",
        f"++v23_route_b_intervention_mode={mode}",
        f"++v23_route_b_scenario_path={candidate['scenario_path']}",
        "++env.config.a2_v23_warm_head_reset_enabled=false",
        "++env.config.a2_v23_formal_launch=false",
    ]
    if mode == "HIGHER_EFFORT_RESCUE":
        command.append("++env.config.a2_v23_effort_profile_applied=true")
    elif mode == "ORACLE_TANGENTIAL_ASSIST":
        command.append(
            "++env.config.a2_v23_oracle_tangential_delta_raw="
            + json.dumps(_oracle_matrix(), separators=(",", ":"))
        )
        command.append(
            "++env.config.a2_v23_oracle_active_mask="
            + json.dumps([True] * INTERVENTION_NUM_ENVS, separators=(",", ":"))
        )
    return command


def _job_plan(candidate: Mapping[str, Any], mode: str) -> dict[str, Any]:
    output = _candidate_root(candidate, mode)
    gpu = int(V23_FORMAL_CELL_GPU[candidate["cell"]])
    return {
        "job_id": f"{candidate['subwave']}:{candidate['cell']}:step{candidate['step']:04d}:{mode}",
        "schema": INTERVENTION_JOB_SCHEMA,
        "source_branch": candidate["source_branch"],
        "plan_id": candidate["plan_id"],
        "identity_policy": candidate["identity_policy"],
        "selected_candidate": dict(candidate),
        "mode": mode,
        "switch_rule": dict(SWITCH_RULES[mode]),
        "topology": INTERVENTION_TOPOLOGY,
        "num_envs": INTERVENTION_NUM_ENVS,
        "episodes": INTERVENTION_EPISODES,
        "physical_gpu": gpu,
        "logical_gpu": "cuda:0",
        "num_mini_batches": 1,
        "retry_count": 0,
        "no_retry": True,
        "forward_only": True,
        "state_clone_supported": False,
        "recurrent_state_restore_supported": False,
        "actual_torque_claim": False,
        "effort_profile_configured": mode == "HIGHER_EFFORT_RESCUE",
        "oracle_delta_configured": mode == "ORACLE_TANGENTIAL_ASSIST",
        "evaluation_root": str(output),
        "records_path": str(output / "a2_v14_per_env_records.json"),
        "raw_trace_path": str(output / "stage2_step_trace.json"),
        "metrics_path": str(output / "metrics_eval.json"),
        "run_receipt_path": str(output / "run_receipt.json"),
        "intervention_records_path": str(output / "intervention_records.json"),
        "contact_evidence": "NOT_EXPORTED_UNSUPPORTED_FOR_ROUTE_B_INTERVENTION",
        "command": _command(candidate, mode, output),
        "environment": {
            "CUDA_DEVICE_ORDER": "PCI_BUS_ID",
            "CUDA_VISIBLE_DEVICES": str(gpu),
            "ACCELERATE_TORCH_DEVICE": "cuda:0",
            "WANDB_MODE": "disabled",
        },
    }


def build_plan(
    *,
    pooled_receipt: str | Path = POOLED48_RECEIPT_PATH,
    stratified_receipt: str | Path = STRATIFIED_RECEIPT_PATH,
    output: str | Path | None = None,
) -> dict[str, Any]:
    _pooled, _stratified, selected = _load_upstream(
        pooled_receipt=pooled_receipt,
        stratified_receipt=stratified_receipt,
    )
    jobs = [_job_plan(candidate, mode) for candidate in selected for mode in V23_INTERVENTION_MODES]
    if len(jobs) != 80:
        raise InterventionEvalError("intervention plan must contain exactly 16*5=80 jobs")
    payload = {
        "schema": INTERVENTION_PLAN_SCHEMA,
        "status": "BUILT",
        "recorded_at_utc": _now(),
        "source_branch": "A2_Piper",
        "plan_id": V23_PLAN_ID,
        "identity_policy": "OWNER_NO_HASH_PATH_IDENTITY",
        "route": "B",
        "stage": "INTERVENTIONS",
        "selected_candidates": selected,
        "selected_candidate_count": len(selected),
        "modes": list(V23_INTERVENTION_MODES),
        "topology": INTERVENTION_TOPOLOGY,
        "num_envs": INTERVENTION_NUM_ENVS,
        "episodes_per_job": INTERVENTION_EPISODES,
        "physical_gpus": list(V23_LEGAL_PHYSICAL_GPUS),
        "logical_gpu": "cuda:0",
        "num_mini_batches": 1,
        "jobs": jobs,
        "pooled_receipt_path": str(_absolute(pooled_receipt)),
        "stratified_receipt_path": str(_absolute(stratified_receipt)),
        "forward_only": True,
        "state_clone_supported": False,
        "actual_torque_claim": False,
        "outcome_status": "PENDING_RUNTIME_FORWARD_ADJUDICATION",
        "no_retry": True,
    }
    if output is not None:
        write_json(_absolute(output), payload)
    return payload


def _validate_runtime_files(job: Mapping[str, Any]) -> tuple[list[Any], list[Any], dict[str, Any]]:
    root = _absolute(job["evaluation_root"])
    records = _load_any(job["records_path"])
    trace = _load_any(job["raw_trace_path"])
    metrics = _load_any(job["metrics_path"])
    if not isinstance(records, list) or len(records) != INTERVENTION_NUM_ENVS:
        raise InterventionEvalError(f"intervention records must contain exactly 16 rows: {root}")
    ids = sorted(row.get("env_id") for row in records if isinstance(row, Mapping))
    if ids != list(range(INTERVENTION_NUM_ENVS)):
        raise InterventionEvalError(f"intervention records must cover env ids 0..15: {root}")
    if not isinstance(trace, list) or not trace:
        raise InterventionEvalError(f"intervention raw trace is empty: {root}")
    trace_ids = {row.get("env_id") for row in trace if isinstance(row, Mapping)}
    if trace_ids != set(range(INTERVENTION_NUM_ENVS)):
        raise InterventionEvalError(f"intervention raw trace must cover env ids 0..15: {root}")
    if not isinstance(metrics, Mapping) or metrics.get("completed_episodes") != INTERVENTION_EPISODES:
        raise InterventionEvalError(f"intervention metrics must report completed_episodes=16: {root}")
    return records, trace, dict(metrics)


def _records_for_job(job: Mapping[str, Any], records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    mode = job["mode"]
    required_fields = (
        ["a2_v23_effort_profile_applied"]
        if mode == "HIGHER_EFFORT_RESCUE"
        else ["a2_v23_oracle_tangential_delta_raw", "a2_v23_oracle_active_mask"]
        if mode == "ORACLE_TANGENTIAL_ASSIST"
        else []
    )
    result = []
    for row in records:
        env_id = row["env_id"]
        result.append(
            {
                "schema": INTERVENTION_SCHEMA,
                "source_branch": job["source_branch"],
                "plan_id": job["plan_id"],
                "identity_policy": job["identity_policy"],
                "selected_candidate": dict(job["selected_candidate"]),
                "mode": mode,
                "switch_rule": dict(job["switch_rule"]),
                "env_id": env_id,
                "required_actor_state_fields": required_fields,
                "forward_only": True,
                "state_clone_supported": False,
                "recurrent_state_restore_supported": False,
                "actual_torque_claim": False,
                "configured_effort_profile_proof": job["effort_profile_configured"],
                "configured_oracle_override": job["oracle_delta_configured"],
                "outcome": "PENDING_RUNTIME_FORWARD_ADJUDICATION",
                "missing_evidence": ["outcome_adjudication_deferred"],
            }
        )
    return result


def _run_one(job: Mapping[str, Any]) -> dict[str, Any]:
    root = _absolute(job["evaluation_root"])
    receipt_path = root / "run_receipt.json"
    if root.exists():
        if receipt_path.is_file() and not receipt_path.is_symlink():
            raise InterventionEvalError(f"intervention output already exists; refusing resume: {root}")
        raise InterventionEvalError(f"intervention output exists without sealed receipt: {root}")
    root.mkdir(parents=True, exist_ok=False)
    stdout_path = root / "runtime_stdout.log"
    stderr_path = root / "runtime_stderr.log"
    env = os.environ.copy()
    env.update(job["environment"])
    started = _now()
    with stdout_path.open("x", encoding="utf-8") as stdout, stderr_path.open("x", encoding="utf-8") as stderr:
        process = subprocess.Popen(job["command"], cwd=REPO_ROOT, env=env, stdout=stdout, stderr=stderr)
        return_code = process.wait()
    ended = _now()
    if return_code != 0:
        raise InterventionEvalError(f"intervention job {job['job_id']} exited {return_code}; no retry")
    records, trace, metrics = _validate_runtime_files(job)
    intervention_records = _records_for_job(job, records)
    write_json(_absolute(job["intervention_records_path"]), {"schema": INTERVENTION_SCHEMA, "records": intervention_records})
    receipt = {
        "schema": INTERVENTION_JOB_SCHEMA,
        "status": INTERVENTION_JOB_STATUS,
        "recorded_at_utc": _now(),
        "job_id": job["job_id"],
        "source_branch": job["source_branch"],
        "plan_id": job["plan_id"],
        "identity_policy": job["identity_policy"],
        "selected_candidate": dict(job["selected_candidate"]),
        "mode": job["mode"],
        "switch_rule": dict(job["switch_rule"]),
        "topology": INTERVENTION_TOPOLOGY,
        "num_envs": INTERVENTION_NUM_ENVS,
        "episode_record_count": len(records),
        "trace_row_count": len(trace),
        "trace_env_ids": sorted({row["env_id"] for row in trace if isinstance(row, Mapping)}),
        "metrics_completed_episodes": metrics["completed_episodes"],
        "physical_gpu": job["physical_gpu"],
        "logical_gpu": "cuda:0",
        "num_mini_batches": 1,
        "retry_count": 0,
        "natural_completion": True,
        "forward_only": True,
        "state_clone_supported": False,
        "recurrent_state_restore_supported": False,
        "actual_torque_claim": False,
        "effort_profile_configured": job["effort_profile_configured"],
        "oracle_delta_configured": job["oracle_delta_configured"],
        "contact_evidence": job["contact_evidence"],
        "outcome_status": "PENDING_RUNTIME_FORWARD_ADJUDICATION",
        "missing_evidence": ["outcome_adjudication_deferred", "unsafe_contacts_not_exported_for_route_b_intervention"],
        "process": {
            "pid": process.pid,
            "started_at_utc": started,
            "ended_at_utc": ended,
            "return_code": return_code,
        },
        "records_path": job["records_path"],
        "raw_trace_path": job["raw_trace_path"],
        "metrics_path": job["metrics_path"],
        "intervention_records_path": job["intervention_records_path"],
    }
    write_json(receipt_path, receipt)
    return receipt


def run(
    *,
    pooled_receipt: str | Path = POOLED48_RECEIPT_PATH,
    stratified_receipt: str | Path = STRATIFIED_RECEIPT_PATH,
    only_job: str | None = None,
) -> dict[str, Any]:
    _pooled, _stratified, selected = _load_upstream(
        pooled_receipt=pooled_receipt,
        stratified_receipt=stratified_receipt,
    )
    jobs = []
    for candidate in selected:
        for mode in V23_INTERVENTION_MODES:
            job = _job_plan(candidate, mode)
            if only_job is not None and job["job_id"] != only_job:
                continue
            _run_one(job)
            jobs.append(job["job_id"])
    if only_job is not None and not jobs:
        raise InterventionEvalError(f"unknown intervention job: {only_job}")
    return {
        "schema": "a2_piper_v23_intervention_run_result_v1",
        "status": "PASS",
        "recorded_at_utc": _now(),
        "job_count": len(jobs),
        "completed_jobs": jobs,
        "modes": list(V23_INTERVENTION_MODES),
        "no_retry": True,
    }


def _load_job_receipt(path: Path, *, candidate: Mapping[str, Any], mode: str) -> dict[str, Any]:
    receipt = _load_object(path)
    if receipt.get("schema") != INTERVENTION_JOB_SCHEMA or receipt.get("status") != INTERVENTION_JOB_STATUS:
        raise InterventionEvalError(f"intervention job receipt is incomplete: {path}")
    if receipt.get("selected_candidate") != dict(candidate) or receipt.get("mode") != mode:
        raise InterventionEvalError(f"intervention job identity disagrees: {path}")
    for field, expected in (
        ("topology", INTERVENTION_TOPOLOGY),
        ("num_envs", INTERVENTION_NUM_ENVS),
        ("episode_record_count", INTERVENTION_NUM_ENVS),
        ("metrics_completed_episodes", INTERVENTION_EPISODES),
        ("physical_gpu", V23_FORMAL_CELL_GPU[candidate["cell"]]),
        ("logical_gpu", "cuda:0"),
        ("num_mini_batches", 1),
        ("retry_count", 0),
        ("natural_completion", True),
        ("forward_only", True),
        ("state_clone_supported", False),
        ("recurrent_state_restore_supported", False),
        ("actual_torque_claim", False),
    ):
        if receipt.get(field) != expected:
            raise InterventionEvalError(f"intervention job receipt {path} field {field} disagrees")
    return receipt


def reduce(
    *,
    pooled_receipt: str | Path = POOLED48_RECEIPT_PATH,
    stratified_receipt: str | Path = STRATIFIED_RECEIPT_PATH,
    output: str | Path = INTERVENTION_RECEIPT_PATH,
) -> dict[str, Any]:
    _pooled, _stratified, selected = _load_upstream(
        pooled_receipt=pooled_receipt,
        stratified_receipt=stratified_receipt,
    )
    jobs: list[dict[str, Any]] = []
    for candidate in selected:
        for mode in V23_INTERVENTION_MODES:
            plan = _job_plan(candidate, mode)
            receipt_path = _absolute(plan["run_receipt_path"])
            receipt = _load_job_receipt(receipt_path, candidate=candidate, mode=mode)
            jobs.append(
                {
                    "job_id": receipt["job_id"],
                    "selected_candidate": dict(candidate),
                    "mode": mode,
                    "receipt_path": str(receipt_path),
                    "topology": receipt["topology"],
                    "episode_record_count": receipt["episode_record_count"],
                    "outcome_status": receipt["outcome_status"],
                    "forward_only": receipt["forward_only"],
                    "state_clone_supported": receipt["state_clone_supported"],
                    "actual_torque_claim": receipt["actual_torque_claim"],
                    "missing_evidence": list(receipt["missing_evidence"]),
                }
            )
    if len(jobs) != 80:
        raise InterventionEvalError("intervention reduction requires exactly 80 complete jobs")
    if {job["mode"] for job in jobs} != set(V23_INTERVENTION_MODES):
        raise InterventionEvalError("intervention reduction did not cover all five modes")
    payload = {
        "schema": INTERVENTION_RECEIPT_SCHEMA,
        "status": INTERVENTION_RECEIPT_STATUS,
        "recorded_at_utc": _now(),
        "source_branch": "A2_Piper",
        "plan_id": V23_PLAN_ID,
        "identity_policy": "OWNER_NO_HASH_PATH_IDENTITY",
        "route": "B",
        "stage": "INTERVENTIONS",
        "topology": INTERVENTION_TOPOLOGY,
        "physical_gpus": list(V23_LEGAL_PHYSICAL_GPUS),
        "logical_gpu": "cuda:0",
        "num_mini_batches": 1,
        "modes": list(V23_INTERVENTION_MODES),
        "selected_candidates": selected,
        "candidate_count": len(selected),
        "job_count": len(jobs),
        "episode_record_count": len(jobs) * INTERVENTION_NUM_ENVS,
        "forward_only": True,
        "state_clone_supported": False,
        "recurrent_state_restore_supported": False,
        "actual_torque_claim": False,
        "outcome_status": "PENDING_RUNTIME_FORWARD_ADJUDICATION",
        "jobs": jobs,
        "missing_evidence": ["outcome_adjudication_deferred", "unsafe_contacts_not_exported_for_route_b_intervention"],
        "no_retry": True,
    }
    write_json(_absolute(output), payload)
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("PLAN", "BUILD", "RUN", "REDUCE"), required=True)
    parser.add_argument("--pooled48", type=Path, default=POOLED48_RECEIPT_PATH)
    parser.add_argument("--stratified", type=Path, default=STRATIFIED_RECEIPT_PATH)
    parser.add_argument("--job", default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        if args.mode in {"PLAN", "BUILD"}:
            payload = build_plan(
                pooled_receipt=args.pooled48,
                stratified_receipt=args.stratified,
                output=args.output if args.mode == "BUILD" else None,
            )
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
        elif args.mode == "RUN":
            payload = run(
                pooled_receipt=args.pooled48,
                stratified_receipt=args.stratified,
                only_job=args.job,
            )
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
        else:
            payload = reduce(
                pooled_receipt=args.pooled48,
                stratified_receipt=args.stratified,
                output=args.output or INTERVENTION_RECEIPT_PATH,
            )
            print(json.dumps({"status": "WRITTEN", "path": str(_absolute(args.output or INTERVENTION_RECEIPT_PATH))}, indent=2))
    except (OSError, TypeError, ValueError, V23Error) as exc:
        print(f"V23 INTERVENTION_EVAL {args.mode} FAIL: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
