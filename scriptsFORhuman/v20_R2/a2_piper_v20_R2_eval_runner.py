"""Executable B0/canonical16 R2 evaluation producer.

The environment process owns trace and record construction.  This producer
only starts that process, verifies its receipt, then atomically wraps the
append-only staging rows into a strict RECORD_SET_COMPLETE artifact.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Sequence

from ._r2_common import R2Error, canonical_json, sha256_file, validate_regular_file
from ._r2_workflow import (
    GROUPS,
    artifact_hash,
    config_identity,
    eval_command,
    parse_gpus,
    read_artifact,
    r2_config_path,
    root_path,
    spawn_once,
    write_raw,
)

RECORD_SCHEMA = "a2_piper_base_v20_R2_record_set_v1"
TRAINING_SCHEMA = "a2_piper_base_v20_R2_training_attempt_v1"


def build_eval_command(
    mode: str,
    *,
    repo_root: Path,
    checkpoint: Path,
    config: Path,
    physical_gpu: int,
    seed: int = 0,
    group: str | None = None,
    output_root: Path | None = None,
    num_envs: int | None = None,
) -> tuple[list[str], dict[str, str]]:
    """Return only flags accepted by the Hydra eval entrypoint.

    ``--config`` and ``--r2-*`` argparse flags were rev0 inventions; the
    sibling entrypoint accepts Hydra ``+key=value`` overrides instead.
    """

    if mode not in {"b0", "zero-shot", "canonical16", "forced", "pooled", "holdout", "m22"}:
        raise R2Error("evaluation mode is not in the R2 command contract")
    root = Path(repo_root).resolve()
    output = output_root or root / "logs_eval" / "base_v20_R2" / "_unbound_eval"
    if num_envs is None:
        num_envs = 16 if mode in {"b0", "zero-shot", "canonical16"} else 1
    argv, env, _ = eval_command(
        repo_root=root, checkpoint=checkpoint, config=config, gpu=physical_gpu,
        seed=seed, num_envs=num_envs, output_root=output, mode=mode, group=group,
    )
    return argv, env


def _load_staging(path: Path, *, run_uuid: str) -> tuple[list[dict[str, Any]], list[str]]:
    target = validate_regular_file(path, label="R2 record staging")
    records: list[dict[str, Any]] = []
    trace_paths: list[str] = []
    for index, line in enumerate(target.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise R2Error(f"record staging line {index} is not JSON") from exc
        if not isinstance(row, dict):
            raise R2Error(f"record staging line {index} must be an object")
        if row.get("schema") != "a2_piper_v20_R2_episode_record_v1":
            raise R2Error("record staging contains a non-production record")
        if "producer_state" in row or "status" in row or "adjudicator_state" in row:
            raise R2Error("record staging may not self-attest status")
        provenance = row.get("provenance")
        if not isinstance(provenance, dict) or provenance.get("run_uuid") != run_uuid:
            raise R2Error("record provenance run_uuid does not match executed attempt")
        trace = row.get("trace")
        if isinstance(trace, dict) and isinstance(trace.get("path"), str):
            trace_paths.append(trace["path"])
        records.append(row)
    if not records:
        raise R2Error("executed evaluation produced no staged production records")
    return records, trace_paths


def _complete_record_set(output_root: Path, *, run_uuid: str) -> Path:
    staging = output_root / "record_set.staging.jsonl"
    records, trace_paths = _load_staging(staging, run_uuid=run_uuid)
    payload = {
        "schema": RECORD_SCHEMA,
        "producer_state": "RECORD_SET_COMPLETE",
        "run_uuid": run_uuid,
        "records": records,
        "record_count": len(records),
        "trace_paths": trace_paths,
    }
    target = output_root / "record_set.json"
    write_raw(target, payload, producer_state="RECORD_SET_COMPLETE")
    return target


def validate_record_set(path: Path) -> dict[str, Any]:
    payload = read_artifact(path, schema=RECORD_SCHEMA, producer_state="RECORD_SET_COMPLETE")
    records = payload.get("records")
    if not isinstance(records, list) or payload.get("record_count") != len(records):
        raise R2Error("record set record_count mismatch")
    if not isinstance(payload.get("run_uuid"), str) or not payload["run_uuid"]:
        raise R2Error("record set run_uuid is required")
    return payload


def _parent_state(mode: str) -> tuple[str, str]:
    if mode == "b0":
        return "STATIC_PASS", "a2_piper_base_v20_R2_p0_adjudication_v1"
    if mode == "zero-shot":
        return "FORCED_RUNTIME_SEMANTIC_PASS", "a2_piper_base_v20_R2_semantic_adjudication_v1"
    raise R2Error(f"unsupported parent mode: {mode}")


def run_eval(
    *, mode: str, repo_root: Path, checkpoint: Path, config: Path | None = None,
    physical_gpus: Sequence[int], output_root: Path, seed: int = 0,
    group: str | None = None, source_lock: Path | None = None,
    parent_pass: Path | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    gpus = parse_gpus(physical_gpus)
    if source_lock is None:
        raise R2Error("evaluation requires ACTIVE_SOURCE_LOCK")
    read_artifact(source_lock, schema="a2_piper_base_v20_R2_source_lock_v1", producer_state="SOURCE_FROZEN")
    if parent_pass is None:
        raise R2Error("evaluation requires exact upstream adjudication")
    parent_state, parent_schema = _parent_state(mode)
    read_artifact(parent_pass, schema=parent_schema, adjudicator_state=parent_state)
    checkpoint = validate_regular_file(checkpoint, label="evaluation checkpoint")
    config_root = root / "gr00t/rl/config/ablation/wbmanip"
    if mode == "b0":
        if gpus != (0, 1, 2):
            raise R2Error("B0 requires physical GPUs 0,1,2 exactly")
        if config is None:
            config = r2_config_path(config_root, "G2")
        jobs = [(f"seed{s}", s, gpus[s], config, "B0", 16) for s in (0, 1, 2)]
    elif mode == "zero-shot":
        if gpus != tuple(range(7)):
            raise R2Error("zero-shot requires physical GPUs 0-6 exactly")
        if group is not None:
            raise R2Error("zero-shot executes all seven groups; group is reconstructed internally")
        jobs = [(group_name, 0, gpu, r2_config_path(config_root, group_name), group_name, 16)
                for group_name, gpu in zip(GROUPS, gpus)]
    else:
        raise R2Error("run_eval mode must be b0 or zero-shot")
    source_hash = artifact_hash(source_lock)
    outputs: list[dict[str, Any]] = []
    for name, job_seed, gpu, job_config, job_group, envs in jobs:
        job_root = output_root / name
        run_uuid = f"{mode}-{job_group}-seed{job_seed}"
        argv, env, binding = eval_command(
            repo_root=root, checkpoint=checkpoint, config=job_config, gpu=gpu,
            seed=job_seed, num_envs=envs, output_root=job_root, mode=mode,
            group=job_group if mode == "zero-shot" else None,
        )
        receipt = spawn_once(
            argv=argv, repo_root=root, output_root=job_root, env=env,
            name=f"{mode}_{job_group}_seed{job_seed}", physical_gpu=gpu,
            active_source_lock=source_lock, parents={"parent_pass": parent_pass},
            marker_payload={"source_lock_sha256": source_hash, "run_uuid": run_uuid,
                            "group": job_group, "seed": job_seed,
                            "config_sha256": artifact_hash(job_config),
                            "checkpoint_sha256": artifact_hash(checkpoint)},
        )
        record_set = _complete_record_set(job_root, run_uuid=run_uuid)
        validate_record_set(record_set)
        outputs.append({"name": name, "group": job_group, "seed": job_seed,
                        "argv": argv, "env": env,
                        "physical_gpu": gpu, "config_sha256": artifact_hash(job_config),
                        "checkpoint_sha256": artifact_hash(checkpoint),
                        "process_receipt": str(job_root / "process_receipt.json"),
                        "record_set": str(record_set), "binding": binding,
                        "receipt_sha256": artifact_hash(job_root / "process_receipt.json")})
    payload = {
        "schema": TRAINING_SCHEMA, "producer_state": "PROCESS_COMPLETED",
        "attempt_id": f"{mode}-seed{seed}", "group": group or ("B0" if mode == "b0" else "G1"),
        "command": outputs[0]["argv"],
        "env": outputs[0]["env"], "source_lock_sha256": source_hash,
        "config_sha256": outputs[0]["config_sha256"],
        "checkpoint_sha256": outputs[0]["checkpoint_sha256"],
        "groups": outputs, "process_receipts": [row["process_receipt"] for row in outputs],
    }
    write_raw(output_root / "evaluation_execution.json", payload, producer_state="PROCESS_COMPLETED")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("b0", "zero-shot"))
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--source-lock", type=Path, required=True)
    parser.add_argument("--p0-pass", "--parent-pass", dest="parent_pass", type=Path)
    parser.add_argument("--forced-pass", dest="forced_pass", type=Path)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--physical-gpus", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--group")
    args = parser.parse_args(argv)
    parent = args.forced_pass or args.parent_pass
    run_eval(mode=args.mode, repo_root=args.repo_root, checkpoint=args.checkpoint,
             config=args.config, physical_gpus=parse_gpus(args.physical_gpus),
             output_root=args.output_root, seed=args.seed, group=args.group,
             source_lock=args.source_lock, parent_pass=parent)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
