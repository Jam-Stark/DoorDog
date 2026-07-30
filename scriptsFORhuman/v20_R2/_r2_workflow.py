"""Strict, dependency-light helpers shared by executable R2 workflow tools."""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from ._r2_common import (
    ADJUDICATOR_STATES,
    ADMISSION_PLAN_ID,
    PRODUCER_STATES,
    R2Error,
    canonical_json,
    device_env,
    hash_command_env,
    load_json,
    require_adjudicator_state,
    require_producer_state,
    sha256_file,
    validate_device_contract,
    validate_raw_producer_payload,
    validate_regular_file,
    validate_gpu,
    write_json_exclusive,
)

R2_SOURCE = "scriptsFORhuman/v20_R2"
SCHEMA_DIR = Path(__file__).with_name("schemas")
GROUPS = tuple(f"G{i}" for i in range(1, 8))
M22_STEPS = (250, 500, 750, 1000, 1250, 1500, 1750, 2000, 2250, 2500)
CONFIG_FILENAMES = {
    "G1": "base_v20_R2_G1_g2_continuation.yaml",
    "G2": "base_v20_R2_G2_economics_only.yaml",
    "G3": "base_v20_R2_G3_send_curriculum_only.yaml",
    "G4": "base_v20_R2_G4_send_curriculum_economics.yaml",
    "G5": "base_v20_R2_G5_send_curriculum_arm_tie.yaml",
    "G6": "base_v20_R2_G6_full.yaml",
    "G7": "base_v20_R2_G7_full_seed1.yaml",
}


def r2_config_path(config_root: Path | str, group: str) -> Path:
    ensure_group(group)
    return Path(config_root) / CONFIG_FILENAMES[group]


def root_path(repo_root: Path | str, value: Path | str) -> Path:
    root = Path(repo_root).resolve()
    target = Path(value)
    if not target.is_absolute():
        target = root / target
    target = target.resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise R2Error(f"path escapes repository root: {value}") from exc
    return target


def artifact_hash(path: Path | str) -> str:
    return sha256_file(validate_regular_file(path, label="R2 artifact"))


def read_artifact(path: Path | str, *, schema: str | None = None,
                  producer_state: str | None = None,
                  adjudicator_state: str | None = None) -> dict[str, Any]:
    payload = load_json(validate_regular_file(path, label="R2 artifact"))
    if not isinstance(payload, Mapping):
        raise R2Error(f"R2 artifact must be an object: {path}")
    if schema is not None and payload.get("schema") != schema:
        raise R2Error(f"R2 artifact schema mismatch: expected {schema}, got {payload.get('schema')}")
    if producer_state is not None:
        require_producer_state(payload, producer_state)
    elif "producer_state" in payload:
        validate_raw_producer_payload(payload)
    if adjudicator_state is not None:
        require_adjudicator_state(payload, adjudicator_state)
    return dict(payload)


def write_raw(path: Path | str, payload: Mapping[str, Any], *, producer_state: str | None = None) -> str:
    validate_raw_producer_payload(payload, producer_state=producer_state)
    return write_json_exclusive(path, payload)


def write_adjudication(path: Path | str, payload: Mapping[str, Any], state: str) -> str:
    if state not in ADJUDICATOR_STATES:
        raise R2Error(f"unknown adjudicator state: {state}")
    if payload.get("adjudicator_state") != state:
        raise R2Error("adjudication payload must carry the computed state")
    require_adjudicator_state(payload, state)
    return write_json_exclusive(path, payload)


def parse_gpus(value: str | Sequence[int | str], *, expected: int | None = None) -> tuple[int, ...]:
    if isinstance(value, str):
        tokens = [item.strip() for item in value.split(",") if item.strip()]
    else:
        tokens = list(value)
    if not tokens:
        raise R2Error("at least one physical GPU is required")
    result = tuple(validate_gpu(item) for item in tokens)
    if len(set(result)) != len(result):
        raise R2Error("physical GPU list contains duplicates")
    if expected is not None and len(result) != expected:
        raise R2Error(f"expected exactly {expected} physical GPUs, got {len(result)}")
    return result


def runtime_command(*, module: str, repo_root: Path | str, gpu: int,
                    render: bool = False, extra: Sequence[str] = ()) -> tuple[list[str], dict[str, str], dict[str, Any]]:
    physical = validate_gpu(gpu)
    argv = [sys.executable, "-B", "-m", module, *map(str, extra)]
    env = device_env(physical, render=render)
    binding = validate_device_contract(
        gpu=physical,
        render=render,
        argv=argv,
        env=env,
        app_launcher_device=env["ACCELERATE_TORCH_DEVICE"],
        accelerator_device=env["ACCELERATE_TORCH_DEVICE"],
    )
    return argv, env, binding


def parent_sha(path: Path | str, *, schema: str | None = None,
               adjudicator_state: str | None = None,
               producer_state: str | None = None) -> tuple[dict[str, Any], str]:
    payload = read_artifact(path, schema=schema, producer_state=producer_state, adjudicator_state=adjudicator_state)
    return payload, artifact_hash(path)


def require_parents(paths: Mapping[str, Path | str], *, schema: str | None = None,
                    state: str | None = None) -> dict[str, str]:
    result: dict[str, str] = {}
    for name, path in paths.items():
        if state in ADJUDICATOR_STATES:
            read_artifact(path, schema=schema, adjudicator_state=state)
        else:
            read_artifact(path, schema=schema, producer_state=state)
        result[name] = artifact_hash(path)
    return result


def config_identity(path: Path | str) -> dict[str, Any]:
    target = validate_regular_file(path, label="R2 config")
    text = target.read_text(encoding="utf-8")
    if "base_v20_R1_" in target.name or "scriptsFORhuman.v20_R1" in text:
        raise R2Error("R2 executable config may not point to an R1 config/tool")
    required = ("scientific_plan_id", "admission_plan_id")
    if not all(key in text for key in required):
        raise R2Error(f"R2 config is missing dual identity fields: {target}")
    return {"path": str(target), "sha256": artifact_hash(target), "text": text}


def ensure_group(group: str) -> str:
    if group not in GROUPS:
        raise R2Error(f"group must be one of {GROUPS}, got {group!r}")
    return group


def ensure_r2_ids(payload: Mapping[str, Any]) -> None:
    if payload.get("scientific_plan_id") != "base_v20_R1_policy_behavior_v1":
        raise R2Error("scientific_plan_id mismatch")
    if payload.get("admission_plan_id") != ADMISSION_PLAN_ID:
        raise R2Error("admission_plan_id mismatch")


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def spawn_once(*, argv: Sequence[str], repo_root: Path, output_root: Path,
               env: Mapping[str, str], name: str, render: bool = False,
               physical_gpu: int | None = None) -> dict[str, Any]:
    """Run one explicitly requested process and retain immutable receipts."""
    if output_root.exists():
        raise R2Error(f"output root already exists: {output_root}")
    output_root.mkdir(parents=True)
    stdout_path = output_root / f"{name}.stdout.log"
    stderr_path = output_root / f"{name}.stderr.log"
    process_env = os.environ.copy()
    process_env.update(env)
    with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
        process = subprocess.run(list(argv), cwd=repo_root, env=process_env, stdout=stdout, stderr=stderr, check=False)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    receipt = {
        "schema": "a2_piper_base_v20_R2_process_receipt_v1",
        "producer_state": "PROCESS_COMPLETED",
        "name": name,
        "argv": list(argv),
        "env": dict(sorted(env.items())),
        "pid": os.getpid(),
        "started_at_utc": now,
        "ended_at_utc": now,
        "exit_code": int(process.returncode),
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "stdout_sha256": artifact_hash(stdout_path),
        "stderr_sha256": artifact_hash(stderr_path),
        "command_sha256": hash_command_env(argv, env),
        "observed_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_root, text=True).strip(),
        "physical_gpu": physical_gpu,
        "render": render,
    }
    write_raw(output_root / "process_receipt.json", receipt, producer_state="PROCESS_COMPLETED")
    if process.returncode != 0:
        raise R2Error(f"R2 process {name} exited nonzero: {process.returncode}")
    return receipt


def require_exact_set(actual: Sequence[Any], expected: Sequence[Any], *, label: str) -> None:
    if set(actual) != set(expected) or len(actual) != len(expected):
        raise R2Error(f"{label} is not an exact set")
