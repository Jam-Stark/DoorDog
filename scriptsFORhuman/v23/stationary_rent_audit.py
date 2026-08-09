"""Build, run, and reduce the six independent v23 stationary-rent passes."""

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
    from ._v23_common import (
        REPO_ROOT,
        V23_ARTIFACT_PATHS,
        V23_LEGAL_PHYSICAL_GPUS,
        V23_WARM_START_PATH,
        V23Error,
        emit_payload,
        finite_number,
        read_json,
        require_file,
        write_json,
    )
except ImportError:
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from scriptsFORhuman.v23._v23_common import (
        REPO_ROOT,
        V23_ARTIFACT_PATHS,
        V23_LEGAL_PHYSICAL_GPUS,
        V23_WARM_START_PATH,
        V23Error,
        emit_payload,
        finite_number,
        read_json,
        require_file,
        write_json,
    )


PASS_SCHEMA = "a2_piper_v23_stationary_rent_pass_v1"
AUDIT_SCHEMA = "a2_piper_v23_stationary_rent_audit_v1"
CONFIG_OVERRIDE = "wbmanip/base_v23_p06_warm_full_d0_smoke"
TARGET_STAGES = tuple(range(6))
NUM_ENVS = 16
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "logs_eval/base_v23/p0/reward/stationary_rent_passes"
DEFAULT_OUTPUT = REPO_ROOT / V23_ARTIFACT_PATHS["reward"]


def _physical_gpu(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value not in V23_LEGAL_PHYSICAL_GPUS:
        raise V23Error(
            f"physical GPU must be one of {V23_LEGAL_PHYSICAL_GPUS}; got {value!r}"
        )
    return value


def _absolute_path(value: Path, *, name: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.resolve()


def _pass_output_dir(output_root: Path, stage: int) -> Path:
    if stage not in TARGET_STAGES:
        raise V23Error(f"stationary-rent target stage must be one of {TARGET_STAGES}; got {stage!r}")
    return output_root / f"stage_{stage}"


def build_pass_plan(*, output_root: Path, gpu: int) -> dict[str, Any]:
    """Build exactly six source-locked eval-only commands in stage order."""

    physical_gpu = _physical_gpu(gpu)
    output_root = _absolute_path(output_root, name="output-root")
    checkpoint = require_file(REPO_ROOT / V23_WARM_START_PATH, label="v22 step1250 warm checkpoint")
    passes = []
    runtime_env = {
        "CUDA_VISIBLE_DEVICES": str(physical_gpu),
        "ACCELERATE_TORCH_DEVICE": "cuda:0",
        "WANDB_MODE": "disabled",
        "PYTHONPATH": str(REPO_ROOT),
    }
    for stage in TARGET_STAGES:
        output_dir = _pass_output_dir(output_root, stage).resolve()
        argv = [
            sys.executable,
            "-m",
            "gr00t.rl.eval_agent_trl",
            f"+ablation={CONFIG_OVERRIDE}",
            f"++checkpoint={checkpoint}",
            "++checkpoint_load_mode=policy_only",
            "++auto_load_latest=false",
            "++num_envs=16",
            "++num_gpus=1",
            "++multi_gpu=false",
            "++seed=0",
            "++headless=true",
            "++use_wandb=false",
            "++algo.trl.report_to=none",
            "++algo.config.eval.eval_num_envs_episodes=true",
            "++algo.config.eval.num_eval_episodes=16",
            "++algo.config.eval.a2_v23_stationary_rent_export=true",
            f"++algo.config.eval.a2_v23_stationary_rent_target_stage={stage}",
            "++env.config.a2_v20_R2_evidence_enabled=false",
            "++env.config.a2_v23_stationary_rent_runtime_enabled=true",
            "++simulator.config.cameras.enable_cameras=false",
            "++simulator.config.render_results=false",
            f"++eval_output_dir={output_dir}",
        ]
        passes.append(
            {
                "target_stage": stage,
                "output_dir": str(output_dir),
                "receipt_path": str(output_dir / "a2_v23_stationary_rent_pass.json"),
                "physical_gpu": physical_gpu,
                "logical_device": "cuda:0",
                "argv": argv,
                "command": shlex.join(argv),
                "env": dict(runtime_env),
            }
        )
    return {
        "schema": "a2_piper_v23_stationary_rent_plan_v1",
        "config": CONFIG_OVERRIDE,
        "checkpoint": str(checkpoint),
        "checkpoint_step": 1250,
        "checkpoint_load_mode": "policy_only",
        "num_envs": NUM_ENVS,
        "seed": 0,
        "target_stages": list(TARGET_STAGES),
        "physical_gpu": physical_gpu,
        "logical_device": "cuda:0",
        "passes": passes,
        "retry_policy": "none",
        "process_topology": "six fresh independent sequential processes",
    }


def _validate_pass_payload(payload: Mapping[str, Any], *, expected_stage: int) -> dict[str, Any]:
    if payload.get("schema") != PASS_SCHEMA:
        raise V23Error(f"stage {expected_stage} receipt schema is not {PASS_SCHEMA}")
    if payload.get("target_stage") != expected_stage:
        raise V23Error(
            f"stage {expected_stage} receipt target_stage disagrees: {payload.get('target_stage')!r}"
        )
    if payload.get("forward_only") is not True:
        raise V23Error(f"stage {expected_stage} receipt must set forward_only=true")
    if payload.get("state_clone_supported") is not False:
        raise V23Error(f"stage {expected_stage} receipt must set state_clone_supported=false")
    if payload.get("checkpoint_load_mode") != "policy_only":
        raise V23Error(f"stage {expected_stage} receipt must use policy_only checkpoint loading")
    if payload.get("num_envs") != NUM_ENVS:
        raise V23Error(f"stage {expected_stage} receipt must use exactly {NUM_ENVS} envs")
    status = payload.get("status")
    if status not in {"COMPLETE", "INCOMPLETE_MISSING_STAGE"}:
        raise V23Error(f"stage {expected_stage} receipt has unsupported status {status!r}")
    semantics = payload.get("reward_semantics")
    if not isinstance(semantics, Mapping):
        raise V23Error(f"stage {expected_stage} receipt is missing reward_semantics")
    if semantics.get("raw") != "reward-function output":
        raise V23Error(f"stage {expected_stage} raw reward semantics are not authoritative")
    if semantics.get("scaled") != (
        "raw * configured scale in this project custom engine; no IsaacLab manager dt factor"
    ):
        raise V23Error(f"stage {expected_stage} scaled reward semantics are not authoritative")
    records = payload.get("records")
    if not isinstance(records, list):
        raise V23Error(f"stage {expected_stage} receipt records must be a list")
    if status == "COMPLETE" and not records:
        raise V23Error(f"stage {expected_stage} COMPLETE receipt has no zero-action records")
    env_ids: set[int] = set()
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            raise V23Error(f"stage {expected_stage} record {index} must be an object")
        required = {
            "env_id",
            "episode_index",
            "episode_id",
            "target_stage",
            "pre_stage",
            "post_stage",
            "policy_raw_action",
            "applied_high_level_action",
            "zero_action_verified",
            "done",
            "reward_raw",
            "reward_scaled",
        }
        missing = sorted(required - set(record))
        if missing:
            raise V23Error(f"stage {expected_stage} record {index} is missing {missing}")
        env_id = record["env_id"]
        if isinstance(env_id, bool) or not isinstance(env_id, int) or not 0 <= env_id < NUM_ENVS:
            raise V23Error(f"stage {expected_stage} record {index} has invalid env_id={env_id!r}")
        if env_id in env_ids:
            raise V23Error(f"stage {expected_stage} receipt duplicates env_id={env_id}")
        env_ids.add(env_id)
        if record["target_stage"] != expected_stage or record["pre_stage"] != expected_stage:
            raise V23Error(f"stage {expected_stage} record {index} does not preserve target/pre stage identity")
        if isinstance(record["episode_index"], bool) or not isinstance(record["episode_index"], int) or record["episode_index"] < 0:
            raise V23Error(f"stage {expected_stage} record {index} has invalid episode_index")
        if not isinstance(record["episode_id"], str) or not record["episode_id"]:
            raise V23Error(f"stage {expected_stage} record {index} has invalid episode_id")
        if record["zero_action_verified"] is not True or not isinstance(record["done"], bool):
            raise V23Error(f"stage {expected_stage} record {index} has invalid zero-action/done flags")
        for action_name in ("policy_raw_action", "applied_high_level_action"):
            action = record[action_name]
            if not isinstance(action, list) or len(action) != 12:
                raise V23Error(f"stage {expected_stage} record {index} {action_name} must be a 12-D list")
            values = [finite_number(value, name=f"{action_name}[{i}]") for i, value in enumerate(action)]
            if action_name == "applied_high_level_action" and any(value != 0.0 for value in values):
                raise V23Error(f"stage {expected_stage} record {index} applied action is not all zero")
        raw = record["reward_raw"]
        scaled = record["reward_scaled"]
        if not isinstance(raw, Mapping) or not isinstance(scaled, Mapping) or set(raw) != set(scaled) or not raw:
            raise V23Error(f"stage {expected_stage} record {index} reward raw/scaled coverage is not exact")
        for name in raw:
            if not isinstance(name, str) or not name:
                raise V23Error(f"stage {expected_stage} record {index} has an invalid reward name")
            finite_number(raw[name], name=f"reward_raw.{name}")
            finite_number(scaled[name], name=f"reward_scaled.{name}")
    return dict(payload)


def reduce_pass_receipts(*, output_root: Path, output: Path) -> dict[str, Any]:
    """Reduce exactly six typed pass receipts without substituting stages."""

    output_root = _absolute_path(output_root, name="output-root")
    output = _absolute_path(output, name="output")
    passes = []
    missing_stages = []
    semantics = None
    for stage in TARGET_STAGES:
        receipt_path = _pass_output_dir(output_root, stage) / "a2_v23_stationary_rent_pass.json"
        if not receipt_path.is_file():
            raise V23Error(f"missing required stage {stage} receipt: {receipt_path}")
        payload = _validate_pass_payload(read_json(receipt_path), expected_stage=stage)
        if semantics is None:
            semantics = dict(payload["reward_semantics"])
        elif dict(payload["reward_semantics"]) != semantics:
            raise V23Error(f"stage {stage} reward semantics disagree with earlier passes")
        if payload["status"] != "COMPLETE":
            missing_stages.append(stage)
        passes.append(payload)
    status = "COMPLETE" if not missing_stages else "INCOMPLETE_MISSING_STAGE"
    return {
        "schema": AUDIT_SCHEMA,
        "status": status,
        "target_stages": list(TARGET_STAGES),
        "missing_stages": missing_stages,
        "forward_only": True,
        "state_clone_supported": False,
        "checkpoint_load_mode": "policy_only",
        "num_envs": NUM_ENVS,
        "reward_semantics": semantics,
        "passes": passes,
    }


def execute_pass_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    """Execute six fresh passes sequentially; any process failure aborts."""

    pass_specs = plan.get("passes")
    if not isinstance(pass_specs, list) or len(pass_specs) != len(TARGET_STAGES):
        raise V23Error("stationary-rent run plan must contain exactly six passes")
    completed = []
    for spec in pass_specs:
        output_dir = Path(spec["output_dir"])
        if output_dir.exists() and any(output_dir.iterdir()):
            raise V23Error(f"refusing to reuse non-empty stationary-rent output directory: {output_dir}")
        output_dir.mkdir(parents=True, exist_ok=True)
        argv = spec["argv"]
        env = {**os.environ, **dict(spec["env"])}
        result = subprocess.run(argv, cwd=REPO_ROOT, env=env, check=False)
        if result.returncode != 0:
            raise V23Error(
                f"stationary-rent stage {spec['target_stage']} process failed with returncode={result.returncode}"
            )
        receipt_path = Path(spec["receipt_path"])
        if not receipt_path.is_file():
            raise V23Error(
                f"stationary-rent stage {spec['target_stage']} exited successfully without its pass receipt"
            )
        completed.append(
            {
                "target_stage": spec["target_stage"],
                "returncode": int(result.returncode),
                "receipt_path": str(receipt_path),
            }
        )
    return {**dict(plan), "execution_state": "COMPLETED", "completed": completed}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("BUILD", "RUN", "REDUCE"), required=True)
    parser.add_argument("--gpu", type=int, default=None, help="selected physical GPU (0..3) for RUN/BUILD")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    if args.mode == "REDUCE":
        payload = reduce_pass_receipts(output_root=args.output_root, output=args.output)
        emit_payload(payload, args.output)
        return 0

    gpu = 0 if args.gpu is None else _physical_gpu(args.gpu)
    plan = build_pass_plan(output_root=args.output_root, gpu=gpu)
    if args.mode == "RUN":
        if args.gpu is None:
            raise V23Error("RUN requires an explicitly selected physical GPU via --gpu 0..3")
        payload = execute_pass_plan(plan)
    else:
        payload = plan
    emit_payload(payload)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except V23Error as exc:
        raise SystemExit(f"V23 STATIONARY-RENT AUDIT FAIL: {exc}")
