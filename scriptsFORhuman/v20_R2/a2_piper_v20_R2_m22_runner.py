"""Executable M22 runner with one-to-one manifest entry ownership."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from ._r2_common import R2Error, canonical_json
from ._r2_workflow import GROUPS, M22_STEPS, artifact_hash, eval_command, parse_gpus, read_artifact, spawn_once, write_raw
from .a2_piper_v20_R2_eval_runner import _complete_record_set, validate_record_set


def build_m22_commands(*, manifest: Path, repo_root: Path, physical_gpus: tuple[int, ...], output_root: Path) -> list[dict[str, object]]:
    payload = read_artifact(manifest, schema="a2_piper_base_v20_R2_m22_manifest_v1", producer_state="LAUNCH_PLAN_COMPLETE")
    if len(payload.get("rows", [])) != 70 or tuple(physical_gpus) != tuple(range(7)):
        raise R2Error("M22 requires exact 70 rows and physical GPUs 0-6")
    rows: list[dict[str, object]] = []
    for entry in payload["rows"]:
        group = entry["group"]
        if group not in GROUPS or entry["checkpoint_step"] not in M22_STEPS:
            raise R2Error("M22 manifest row identity is invalid")
        gpu = int(group[1:]) - 1
        entry_id = entry.get("entry_id")
        if not isinstance(entry_id, str) or len(entry_id) != 64:
            raise R2Error("M22 row lacks canonical entry_id")
        checkpoint = Path(str(entry["checkpoint_path"]))
        config = Path(str(entry["training_run_config_path"]))
        entry_root = output_root / group / f"step_{int(entry['checkpoint_step']):06d}_{entry_id[:12]}"
        argv, env, binding = eval_command(repo_root=repo_root, checkpoint=checkpoint, config=config, gpu=gpu,
                                          seed=0, num_envs=16, output_root=entry_root, mode="m22", group=group)
        argv.append(f"+r2_m22_entry_id={entry_id}")
        rows.append({"entry_id": entry_id, "group": group, "checkpoint_step": entry["checkpoint_step"],
                     "physical_gpu": gpu, "argv": argv, "env": env, "device": binding,
                     "manifest_sha256": artifact_hash(manifest), "output_root": str(entry_root),
                     "checkpoint_sha256": entry["checkpoint_sha256"], "config_sha256": entry["resolved_config_sha256"]})
    identities = {(row["group"], row["checkpoint_step"]) for row in rows}
    expected = {(group, step) for group in GROUPS for step in M22_STEPS}
    if len(rows) != 70 or identities != expected:
        raise R2Error("M22 command set is not exact G1-G7 x ten checkpoints")
    return rows


def run_m22(*, manifest: Path, repo_root: Path, physical_gpus: tuple[int, ...], output_root: Path,
            attempt_marker: Path | None = None) -> dict[str, object]:
    rows = build_m22_commands(manifest=manifest, repo_root=repo_root, physical_gpus=physical_gpus, output_root=output_root)
    marker = attempt_marker or output_root / "M22_ATTEMPT_CONSUMED.json"
    marker_payload = {"schema": "a2_piper_base_v20_R2_training_attempt_v1", "producer_state": "ATTEMPT_CONSUMED",
                      "attempt_id": "m22-wave", "group": "G1", "command": rows[0]["argv"], "env": rows[0]["env"],
                      "source_lock_sha256": read_artifact(manifest)["source_lock_sha256"],
                      "config_sha256": rows[0]["config_sha256"], "checkpoint_sha256": rows[0]["checkpoint_sha256"],
                      "manifest_sha256": artifact_hash(manifest), "groups": rows}
    write_raw(marker, marker_payload, producer_state="ATTEMPT_CONSUMED")
    receipts: list[dict[str, object]] = []
    for row in rows:
        entry_root = Path(str(row["output_root"]))
        receipt = spawn_once(argv=row["argv"], repo_root=repo_root, output_root=entry_root, env=row["env"],
                             name=f"m22_{row['group']}_step{row['checkpoint_step']}",
                             physical_gpu=int(row["physical_gpu"]), attempt_marker=marker,
                             parents={"manifest": manifest}, marker_payload={"entry_id": row["entry_id"]})
        record_set = _complete_record_set(entry_root, run_uuid=f"m22-{row['entry_id']}")
        validate_record_set(record_set)
        receipts.append({"entry_id": row["entry_id"], "group": row["group"], "checkpoint_step": row["checkpoint_step"],
                         "process_receipt_path": str(entry_root / "process_receipt.json"),
                         "process_receipt_sha256": artifact_hash(entry_root / "process_receipt.json"),
                         "record_set_path": str(record_set), "record_set_sha256": artifact_hash(record_set),
                         "exit_code": receipt["exit_code"]})
    return {"schema": "a2_piper_base_v20_R2_training_attempt_v1", "producer_state": "PROCESS_COMPLETED",
            "attempt_id": "m22-wave", "group": "G1", "command": rows[0]["argv"], "env": rows[0]["env"],
            "source_lock_sha256": marker_payload["source_lock_sha256"], "config_sha256": rows[0]["config_sha256"],
            "checkpoint_sha256": rows[0]["checkpoint_sha256"], "manifest_sha256": artifact_hash(manifest),
            "groups": receipts, "attempt_marker_sha256": artifact_hash(marker)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True); parser.add_argument("--physical-gpus", required=True)
    parser.add_argument("--output-root", type=Path, required=True); parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--attempt-marker", type=Path)
    args = parser.parse_args(argv)
    result = run_m22(manifest=args.manifest, repo_root=args.repo_root, physical_gpus=parse_gpus(args.physical_gpus),
                     output_root=args.output_root, attempt_marker=args.attempt_marker)
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
