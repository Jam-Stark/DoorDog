"""Acyclic producer for the exact 7x10 M22 checkpoint manifest."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from ._r2_common import R2Error, canonical_json, SCIENTIFIC_PLAN_ID
from ._r2_workflow import GROUPS, M22_STEPS, artifact_hash, read_artifact, write_raw, canonical_digest

MANIFEST_SCHEMA = "a2_piper_base_v20_R2_m22_manifest_v1"


def build_manifest(*, formal_completion: Path, training_root: Path,
                   source_lock_sha256: str, output: Path | None = None) -> dict[str, object]:
    completion = read_artifact(formal_completion, schema="a2_piper_base_v20_R2_formal_completion_v1",
                               adjudicator_state="FORMAL_COMPLETION_PASS")
    if completion.get("source_lock_sha256") not in (None, source_lock_sha256):
        raise R2Error("formal completion source-lock hash mismatch")
    groups = completion.get("groups")
    if not isinstance(groups, list) or [row.get("group") for row in groups] != list(GROUPS):
        raise R2Error("formal completion does not bind exact G1-G7 groups")
    rows: list[dict[str, object]] = []
    completion_hash = artifact_hash(formal_completion)
    for group_row in groups:
        group = str(group_row["group"])
        group_root = Path(str(group_row.get("output_root", training_root / group)))
        if not group_root.is_absolute():
            group_root = training_root / group_root
        checkpoint_rows = group_row.get("checkpoint_rows")
        if not isinstance(checkpoint_rows, list) or len(checkpoint_rows) != 10:
            raise R2Error(f"formal completion must expose ten checkpoints for {group}")
        by_step = {item.get("step"): item for item in checkpoint_rows}
        if set(by_step) != set(M22_STEPS):
            raise R2Error(f"formal completion checkpoint set is not exact for {group}")
        for step in M22_STEPS:
            item = by_step[step]
            checkpoint_path = Path(str(item["path"]))
            if not checkpoint_path.is_file() or checkpoint_path.is_symlink():
                raise R2Error(f"M22 checkpoint missing: {checkpoint_path}")
            checkpoint_hash = artifact_hash(checkpoint_path)
            if checkpoint_hash != item.get("sha256"):
                raise R2Error(f"formal completion checkpoint hash mismatch: {group} step {step}")
            config_hash = item.get("config_sha256")
            if not isinstance(config_hash, str) or len(config_hash) != 64:
                raise R2Error(f"M22 {group} step {step} lacks config hash")
            entry = {
                "group": group, "checkpoint_step": step,
                "checkpoint_path": str(checkpoint_path), "checkpoint_sha256": checkpoint_hash,
                "training_run_config_path": str(item.get("config_path", group_root / "config.yaml")),
                "training_run_config_sha256": str(item.get("training_run_config_sha256", config_hash)),
                "frozen_source_config_sha256": config_hash,
                "resolved_config_sha256": str(item.get("resolved_config_sha256", config_hash)),
                "scientific_plan_id": SCIENTIFIC_PLAN_ID,
                "admission_plan_id": "base_v20_R2_admission_execution_v1",
                "formal_completion_sha256": completion_hash,
            }
            entry["entry_id"] = canonical_digest(entry)
            rows.append(entry)
    if len(rows) != 70 or len({row["entry_id"] for row in rows}) != 70:
        raise R2Error("M22 manifest must contain exactly 70 unique entries")
    payload = {"schema": MANIFEST_SCHEMA, "producer_state": "LAUNCH_PLAN_COMPLETE",
               "source_lock_sha256": source_lock_sha256, "scientific_plan_id": SCIENTIFIC_PLAN_ID,
               "admission_plan_id": "base_v20_R2_admission_execution_v1", "group": "G1", "rows": rows}
    if output is not None:
        write_raw(output, payload, producer_state="LAUNCH_PLAN_COMPLETE")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--formal-completion", type=Path, required=True); parser.add_argument("--training-root", type=Path, required=True)
    parser.add_argument("--source-lock-sha256", required=True); parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = build_manifest(formal_completion=args.formal_completion, training_root=args.training_root,
                            source_lock_sha256=args.source_lock_sha256, output=args.output)
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
