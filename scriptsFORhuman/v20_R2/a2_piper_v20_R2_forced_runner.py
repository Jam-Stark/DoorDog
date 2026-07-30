"""Executable one-process forced-semantic producer."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from ._r2_common import R2Error, canonical_json, device_env, validate_device_contract, validate_gpu
from ._r2_workflow import (
    GROUPS,
    artifact_hash,
    eval_command,
    read_artifact,
    r2_config_path,
    spawn_once,
    write_raw,
)
from gr00t.rl.envs.door.a2_v20_r2_forced_semantics import FORCED_CASES

FORCED_SCHEMA = "a2_piper_base_v20_R2_forced_trace_v1"


def build_forced_command(*, repo_root: Path, physical_gpu: int) -> tuple[list[str], dict[str, str]]:
    """Build the actual eval entrypoint command; no private argparse flags."""

    gpu = validate_gpu(physical_gpu)
    argv = [sys.executable, "-B", "-m", "gr00t.rl.eval_agent_trl",
            "+r2_forced=true", "+num_envs=1", "+seed=0", "+headless=true"]
    env = device_env(gpu, render=False)
    validate_device_contract(gpu=gpu, render=False, argv=argv, env=env,
                             app_launcher_device=f"cuda:{gpu}", accelerator_device=f"cuda:{gpu}")
    return argv, env


def _raw_rows(path: Path) -> list[dict[str, Any]]:
    if not path.is_file() or path.is_symlink():
        raise R2Error(f"forced trace is missing or symlinked: {path}")
    text = path.read_text(encoding="utf-8")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        if parsed.get("schema") != FORCED_SCHEMA:
            raise R2Error("forced trace schema mismatch")
        rows = parsed.get("cases")
        if not isinstance(rows, list):
            raise R2Error("forced trace cases must be a list")
    elif isinstance(parsed, list):
        rows = parsed
    else:
        rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    if not rows or not all(isinstance(row, dict) for row in rows):
        raise R2Error("forced trace rows must be objects")
    for row in rows:
        for forbidden in ("expected", "status", "verdict", "checks_passed", "adjudication"):
            if forbidden in row:
                raise R2Error("forced raw trace may not self-attest expected results")
        if row.get("schema") not in (None, FORCED_SCHEMA):
            raise R2Error("forced trace row schema mismatch")
    return rows


def validate_forced_trace(path: Path) -> list[dict[str, Any]]:
    rows = _raw_rows(path)
    seen: set[str] = set()
    for row in rows:
        case = row.get("case")
        if case not in FORCED_CASES or case in seen:
            raise R2Error("forced trace case set is not unique")
        seen.add(case)
    if tuple(sorted(seen, key=FORCED_CASES.index)) != tuple(FORCED_CASES):
        raise R2Error("forced trace must contain every exact R2 case")
    return rows


def _write_completed_trace(output_root: Path, *, run_uuid: str) -> Path:
    candidate = output_root / "forced_trace.staging.jsonl"
    if not candidate.exists():
        candidate = output_root / "forced_trace.jsonl"
    if not candidate.exists():
        candidate = output_root / "forced_trace.json"
    rows = _raw_rows(candidate)
    # Normalize rows to one canonical raw object while retaining measured values.
    payload = {"schema": FORCED_SCHEMA, "producer_state": "PROCESS_COMPLETED",
               "run_uuid": run_uuid, "cases": rows, "case_count": len(rows),
               "process_receipt_sha256": artifact_hash(output_root / "process_receipt.json")}
    target = output_root / "forced_trace.json"
    write_raw(target, payload, producer_state="PROCESS_COMPLETED")
    validate_forced_trace(target)
    return target


def run_forced(*, repo_root: Path, source_lock: Path, b0_pass: Path,
               physical_gpu: int, output_root: Path, checkpoint: Path | None = None,
               config: Path | None = None) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    read_artifact(source_lock, schema="a2_piper_base_v20_R2_source_lock_v1", producer_state="SOURCE_FROZEN")
    read_artifact(b0_pass, schema="a2_piper_base_v20_R2_endpoint_report_v1", adjudicator_state="B0_RUNTIME_PASS")
    checkpoint = checkpoint or root / "logs_rl/a2_piper_full_stage_a2_base/base_v19/base_v19_G2_norm_control-20260727_012027/model_step_002000.pt"
    config = config or r2_config_path(root / "gr00t/rl/config/ablation/wbmanip", "G2")
    argv, env, _ = eval_command(repo_root=root, checkpoint=checkpoint, config=config,
                                gpu=physical_gpu, seed=0, num_envs=1,
                                output_root=output_root, mode="forced")
    # The forced case selector is a supported Hydra override, not an argparse flag.
    argv.append("+r2_forced=true")
    receipt = spawn_once(argv=argv, repo_root=root, output_root=output_root,
                         env=env, name="forced", physical_gpu=physical_gpu,
                         active_source_lock=source_lock, parents={"b0_pass": b0_pass},
                         marker_payload={"run_uuid": "forced-seed0", "cases": list(FORCED_CASES),
                                         "checkpoint_sha256": artifact_hash(checkpoint),
                                         "config_sha256": artifact_hash(config)})
    trace = _write_completed_trace(output_root, run_uuid="forced-seed0")
    return {"process_receipt": str(output_root / "process_receipt.json"),
            "trace": str(trace), "receipt_sha256": artifact_hash(output_root / "process_receipt.json"),
            "trace_sha256": artifact_hash(trace), "producer_state": "PROCESS_COMPLETED"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--source-lock", type=Path, required=True)
    parser.add_argument("--b0-pass", type=Path, required=True)
    parser.add_argument("--physical-gpu", type=int, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--config", type=Path)
    args = parser.parse_args(argv)
    run_forced(repo_root=args.repo_root, source_lock=args.source_lock, b0_pass=args.b0_pass,
               physical_gpu=args.physical_gpu, output_root=args.output_root,
               checkpoint=args.checkpoint, config=args.config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
