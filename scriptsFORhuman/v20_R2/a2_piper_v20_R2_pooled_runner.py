"""Executable pooled48 producer for the seven mechanically selected M22 rows."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from ._r2_common import R2Error, canonical_json
from ._r2_workflow import GROUPS, artifact_hash, eval_command, parse_gpus, read_artifact, spawn_once, write_raw
from .a2_piper_v20_R2_eval_runner import _complete_record_set, validate_record_set


def _selected_rows(m22: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    payload = read_artifact(m22, schema="a2_piper_base_v20_R2_m22_adjudication_v1", adjudicator_state="M22_70ROW_PASS")
    rows = payload.get("rows")
    if not isinstance(rows, list) or len(rows) != 70:
        raise R2Error("pooled runner requires complete M22 row evidence")
    selected: dict[str, dict[str, Any]] = {}
    for group in GROUPS:
        candidates = [row for row in rows if row.get("group") == group and row.get("state") == "STRICT_VALID"]
        if not candidates:
            raise R2Error(f"M22 has no strict-valid checkpoint for {group}")
        # Within-group selection is deterministic: an adjudicator may provide
        # selected=true; otherwise use the highest strict-valid checkpoint as a
        # diagnostic selection and preserve that fact in the pooled binding.
        marked = [row for row in candidates if row.get("selected") is True]
        selected[group] = sorted(marked or candidates, key=lambda row: int(row["checkpoint_step"]))[-1]
    return payload, selected


def build_pooled_commands(*, m22: Path, repo_root: Path, physical_gpus: tuple[int, ...],
                          output_root: Path | None = None) -> list[dict[str, object]]:
    payload, selected = _selected_rows(m22)
    if tuple(physical_gpus) != tuple(range(7)):
        raise R2Error("pooled runner requires physical GPUs 0-6 exactly")
    root = Path(repo_root).resolve(); base = output_root or root / "logs_eval/base_v20_R2/pooled"
    result: list[dict[str, object]] = []
    for group, gpu in zip(GROUPS, physical_gpus):
        row = selected[group]
        checkpoint = Path(str(row.get("checkpoint_path")))
        config = Path(str(row.get("config_path", row.get("training_run_config_path", ""))))
        if not checkpoint.is_file() or not config.is_file():
            raise R2Error(f"selected M22 {group} row lacks checkpoint/config paths")
        for seed in (0, 1, 2):
            job_root = base / group / f"seed{seed}"
            argv, env, binding = eval_command(repo_root=root, checkpoint=checkpoint, config=config,
                                              gpu=gpu, seed=seed, num_envs=16,
                                              output_root=job_root, mode="pooled", group=group)
            argv.append(f"+r2_selected_checkpoint_step={row['checkpoint_step']}")
            result.append({"group": group, "seed": seed, "physical_gpu": gpu, "argv": argv, "env": env,
                           "device": binding, "output_root": str(job_root), "checkpoint_step": row["checkpoint_step"],
                           "checkpoint_sha256": row["checkpoint_sha256"], "config_sha256": row.get("config_sha256", row.get("resolved_config_sha256")),
                           "m22_sha256": artifact_hash(m22)})
    if len(result) != 21 or {(row["group"], row["seed"]) for row in result} != {(group, seed) for group in GROUPS for seed in (0, 1, 2)}:
        raise R2Error("pooled command set is not exact seven groups x seeds0,1,2")
    return result


def run_pooled(*, m22: Path, repo_root: Path, physical_gpus: tuple[int, ...], output_root: Path,
               attempt_marker: Path | None = None) -> dict[str, object]:
    m22_payload, _ = _selected_rows(m22)
    rows = build_pooled_commands(m22=m22, repo_root=repo_root, physical_gpus=physical_gpus, output_root=output_root)
    source_hash = m22_payload.get("source_lock_sha256")
    if not isinstance(source_hash, str) or len(source_hash) != 64 or set(source_hash) == {"0"}:
        raise R2Error("M22 adjudication lacks a non-zero source-lock hash")
    marker = attempt_marker or output_root / "POOLED_ATTEMPT_CONSUMED.json"
    marker_payload = {"schema": "a2_piper_base_v20_R2_training_attempt_v1", "producer_state": "ATTEMPT_CONSUMED",
                      "attempt_id": "pooled-wave", "group": "G1", "command": rows[0]["argv"], "env": rows[0]["env"],
                      "source_lock_sha256": source_hash, "config_sha256": rows[0]["config_sha256"],
                      "checkpoint_sha256": rows[0]["checkpoint_sha256"], "m22_sha256": artifact_hash(m22), "groups": rows}
    write_raw(marker, marker_payload, producer_state="ATTEMPT_CONSUMED")
    receipts: list[dict[str, object]] = []
    for row in rows:
        job_root = Path(str(row["output_root"]))
        receipt = spawn_once(argv=row["argv"], repo_root=repo_root, output_root=job_root, env=row["env"],
                             name=f"pooled_{row['group']}_seed{row['seed']}", physical_gpu=int(row["physical_gpu"]),
                             attempt_marker=marker, parents={"m22": m22}, marker_payload={"group": row["group"], "seed": row["seed"]})
        record_set = _complete_record_set(job_root, run_uuid=f"pooled-{row['group']}-seed{row['seed']}")
        validate_record_set(record_set)
        receipts.append({"group": row["group"], "seed": row["seed"], "record_set_path": str(record_set),
                         "record_set_sha256": artifact_hash(record_set), "process_receipt_sha256": artifact_hash(job_root / "process_receipt.json"),
                         "exit_code": receipt["exit_code"]})
    return {"schema": "a2_piper_base_v20_R2_training_attempt_v1", "producer_state": "PROCESS_COMPLETED",
            "attempt_id": "pooled-wave", "group": "G1", "command": rows[0]["argv"], "env": rows[0]["env"],
            "source_lock_sha256": marker_payload["source_lock_sha256"], "config_sha256": rows[0]["config_sha256"],
            "checkpoint_sha256": rows[0]["checkpoint_sha256"], "m22_sha256": artifact_hash(m22), "groups": receipts}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--m22", type=Path, required=True); parser.add_argument("--physical-gpus", required=True)
    parser.add_argument("--output-root", type=Path, required=True); parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--attempt-marker", type=Path)
    args = parser.parse_args(argv)
    result = run_pooled(m22=args.m22, repo_root=args.repo_root, physical_gpus=parse_gpus(args.physical_gpus),
                         output_root=args.output_root, attempt_marker=args.attempt_marker)
    print(canonical_json(result)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
