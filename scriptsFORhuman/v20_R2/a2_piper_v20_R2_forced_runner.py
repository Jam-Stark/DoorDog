"""Producer for the one-shot R2 forced-semantic process."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import Any
from ._r2_common import R2Error, canonical_json, write_json_exclusive
from ._r2_workflow import read_artifact, parse_gpus, runtime_command, write_raw
from gr00t.rl.envs.door.a2_v20_r2_forced_semantics import FORCED_CASES, validate_case_names


def build_forced_command(*, repo_root: Path, physical_gpu: int) -> tuple[list[str], dict[str, str]]:
    return runtime_command(module="gr00t.rl.eval_agent_trl", repo_root=repo_root, gpu=physical_gpu, render=False, extra=("--r2-forced", "true"))[:2]


def validate_forced_trace(path: Path) -> list[dict[str, Any]]:
    rows = []
    seen = set()
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                row = json.loads(line)
                if row.get("schema") != "a2_piper_base_v20_R2_forced_trace_v1" or row.get("producer_state") != "PROCESS_COMPLETED":
                    raise R2Error("forced trace row schema/state mismatch")
                if "expected" in row or "status" in row or "verdict" in row:
                    raise R2Error("forced raw trace may not self-attest expected results")
                case = row.get("case")
                if case not in FORCED_CASES or case in seen:
                    raise R2Error("forced trace case set is not unique")
                seen.add(case); rows.append(row)
    if tuple(sorted(seen, key=FORCED_CASES.index)) != FORCED_CASES:
        raise R2Error("forced trace must contain every exact R2 case")
    return rows


def run_forced(*, repo_root: Path, source_lock: Path, b0_pass: Path, physical_gpu: int, output_root: Path) -> dict[str, Any]:
    read_artifact(source_lock, schema="a2_piper_base_v20_R2_source_lock_v1", producer_state="SOURCE_FROZEN")
    read_artifact(b0_pass, adjudicator_state="RUNTIME_PASS")
    argv, env = build_forced_command(repo_root=repo_root, physical_gpu=physical_gpu)
    payload = {"schema": "a2_piper_base_v20_R2_forced_trace_v1", "producer_state": "COMMAND_PLANNED", "command": argv, "env": env, "physical_gpu": physical_gpu, "cases": list(FORCED_CASES)}
    write_raw(output_root / "forced_command.json", payload, producer_state="COMMAND_PLANNED")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True); parser.add_argument("--source-lock", type=Path, required=True); parser.add_argument("--b0-pass", type=Path, required=True); parser.add_argument("--physical-gpu", type=int, required=True); parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args(argv); run_forced(repo_root=args.repo_root, source_lock=args.source_lock, b0_pass=args.b0_pass, physical_gpu=args.physical_gpu, output_root=args.output_root); return 0
if __name__ == "__main__": raise SystemExit(main())
