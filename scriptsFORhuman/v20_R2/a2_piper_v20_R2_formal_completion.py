"""Strict formal completion consumer for the one launched wave."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ._r2_common import R2Error, canonical_json
from ._r2_workflow import GROUPS, M22_STEPS, artifact_hash, read_artifact, write_adjudication


def _batch_metrics(path: Path, target: int) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise R2Error(f"formal training metrics are missing: {path}")
    rows = []
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise R2Error(f"formal metric line {index} is invalid") from exc
        if not isinstance(row, dict):
            raise R2Error("formal metric row must be an object")
        if any(key in row for key in ("status", "pass", "passed", "verdict", "checks_passed", "adjudication")):
            raise R2Error("formal raw metrics may not self-attest")
        rows.append(row)
    batches = sorted({row.get("batch_index") for row in rows if isinstance(row.get("batch_index"), int)})
    if batches != list(range(min(batches), target + 1)) or not batches:
        raise R2Error(f"formal batch evidence is not contiguous through {target}")
    return {"batch_count": len(batches), "last_batch": batches[-1], "metrics_sha256": artifact_hash(path)}


def adjudicate_completion(attempt: Path, training_root: Path, *, source_lock: Path | None = None) -> dict[str, object]:
    payload = read_artifact(attempt, schema="a2_piper_base_v20_R2_training_attempt_v1")
    if payload.get("producer_state") not in {"ATTEMPT_CONSUMED", "LAUNCH_PLAN_COMPLETE", "PROCESS_COMPLETED"}:
        raise R2Error("formal completion requires the consumed formal-wave marker")
    groups = payload.get("groups")
    if not isinstance(groups, list) or [row.get("group") for row in groups] != list(GROUPS):
        raise R2Error("formal attempt group set/order is not exact G1-G7")
    if source_lock is not None and payload.get("source_lock_sha256") != artifact_hash(source_lock):
        raise R2Error("formal attempt source-lock hash mismatch")
    rows: list[dict[str, Any]] = []
    for row in groups:
        group = row["group"]
        seed = 1 if group == "G7" else 0
        if row.get("seed") != seed:
            raise R2Error(f"formal {group} seed contract mismatch")
        group_root = Path(str(row.get("output_root")))
        if not group_root.is_absolute():
            group_root = training_root / group_root
        receipt_path = group_root / "process_receipt.json"
        receipt = read_artifact(receipt_path, schema="a2_piper_base_v20_R2_process_receipt_v1", producer_state="PROCESS_COMPLETED")
        if receipt.get("exit_code") != 0 or receipt.get("natural_exit") is not True:
            raise R2Error(f"formal {group} process did not naturally exit zero")
        metrics = _batch_metrics(group_root / "r2_training_batch_metrics.jsonl", 2500)
        checkpoints: list[dict[str, Any]] = []
        for step in M22_STEPS:
            path = group_root / f"model_step_{step:06d}.pt"
            if not path.is_file() or path.is_symlink():
                raise R2Error(f"formal {group} checkpoint {step} is missing")
            if (group_root / f"model_step_{step:06d}.pt.writing").exists():
                raise R2Error(f"formal {group} checkpoint {step} is still writing")
            checkpoints.append({"group": group, "step": step, "path": str(path),
                                "sha256": artifact_hash(path), "config_sha256": row.get("config_sha256")})
        offline = group_root / "offline_completion.json"
        wandb_finished = group_root / "wandb_finished.json"
        if not offline.is_file() and not wandb_finished.is_file():
            raise R2Error(f"formal {group} lacks W&B finished/offline completion evidence")
        rows.append({"group": group, "seed": seed, "process_receipt_sha256": artifact_hash(receipt_path),
                     "metrics": metrics, "checkpoint_rows": checkpoints,
                     "offline_evidence_sha256": artifact_hash(offline) if offline.is_file() else None,
                     "wandb_finished_sha256": artifact_hash(wandb_finished) if wandb_finished.is_file() else None})
    return {"schema": "a2_piper_base_v20_R2_formal_completion_v1", "adjudicator_state": "FORMAL_COMPLETION_PASS",
            "group": "G1", "attempt_sha256": artifact_hash(attempt),
            "source_lock_sha256": payload.get("source_lock_sha256"), "checkpoint_rows": [checkpoint for row in rows for checkpoint in row["checkpoint_rows"]],
            "groups": rows, "completion": {"natural_exit": True, "target_batch": 2500, "observed_batch": 2500,
                                             "checkpoint_count_per_group": 10, "process_tree_closed": True}}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", type=Path, required=True); parser.add_argument("--training-root", type=Path, required=True)
    parser.add_argument("--source-lock", type=Path); parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = adjudicate_completion(args.attempt, args.training_root, source_lock=args.source_lock)
    write_adjudication(args.output, result, "FORMAL_COMPLETION_PASS")
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
