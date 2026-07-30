"""Executable holdout64 producer for one frozen release candidate."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Sequence

from ._r2_common import R2Error, canonical_json
from ._r2_workflow import artifact_hash, eval_command, parse_gpus, read_artifact, spawn_once, write_raw
from .a2_piper_v20_R2_eval_runner import _complete_record_set, validate_record_set

HOLDOUT_SEEDS = (3, 4, 5, 6)


def build_holdout_commands(*, release_freeze: Path, repo_root: Path, physical_gpus: tuple[int, ...],
                           output_root: Path | None = None, seeds: Sequence[int] = HOLDOUT_SEEDS) -> list[dict[str, object]]:
    freeze = read_artifact(release_freeze, schema="a2_piper_base_v20_R2_release_freeze_v1", adjudicator_state="POLICY_PASS")
    if freeze.get("holdout_allowed") is not True or freeze.get("selected_group") is None:
        raise R2Error("holdout is forbidden for a NO_RELEASE freeze")
    if tuple(seeds) != HOLDOUT_SEEDS or tuple(physical_gpus) != (0, 1, 2, 3):
        raise R2Error("holdout requires seeds3-6 on physical GPUs0-3 exactly")
    checkpoint_path = freeze.get("selected_checkpoint_path")
    config_path = freeze.get("selected_config_path")
    if not isinstance(checkpoint_path, str) or not isinstance(config_path, str):
        raise R2Error("release freeze must bind selected checkpoint and config paths")
    root = Path(repo_root).resolve(); base = output_root or root / "logs_eval/base_v20_R2/holdout"
    rows: list[dict[str, object]] = []
    for seed, gpu in zip(HOLDOUT_SEEDS, physical_gpus):
        job_root = base / f"seed{seed}"
        argv, env, binding = eval_command(repo_root=root, checkpoint=Path(checkpoint_path), config=Path(config_path),
                                          gpu=gpu, seed=seed, num_envs=16, output_root=job_root,
                                          mode="holdout", group=str(freeze["selected_group"]))
        rows.append({"seed": seed, "physical_gpu": gpu, "argv": argv, "env": env, "device": binding,
                     "output_root": str(job_root), "release_freeze_sha256": artifact_hash(release_freeze),
                     "checkpoint_sha256": freeze.get("selected_checkpoint_sha256"), "group": freeze["selected_group"]})
    return rows


def run_holdout(*, release_freeze: Path, repo_root: Path, physical_gpus: tuple[int, ...], output_root: Path,
                attempt_marker: Path | None = None) -> dict[str, object]:
    rows = build_holdout_commands(release_freeze=release_freeze, repo_root=repo_root,
                                  physical_gpus=physical_gpus, output_root=output_root)
    marker = attempt_marker or output_root / "HOLDOUT_ATTEMPT_CONSUMED.json"
    marker_payload = {"schema": "a2_piper_base_v20_R2_training_attempt_v1", "producer_state": "ATTEMPT_CONSUMED",
                      "attempt_id": "holdout", "group": rows[0]["group"], "command": rows[0]["argv"], "env": rows[0]["env"],
                      "source_lock_sha256": "0" * 64, "config_sha256": "0" * 64,
                      "checkpoint_sha256": rows[0]["checkpoint_sha256"], "release_freeze_sha256": artifact_hash(release_freeze),
                      "seeds": rows}
    write_raw(marker, marker_payload, producer_state="ATTEMPT_CONSUMED")
    receipts: list[dict[str, object]] = []
    for row in rows:
        job_root = Path(str(row["output_root"]))
        receipt = spawn_once(argv=row["argv"], repo_root=repo_root, output_root=job_root, env=row["env"],
                             name=f"holdout_seed{row['seed']}", physical_gpu=int(row["physical_gpu"]),
                             attempt_marker=marker, parents={"release_freeze": release_freeze},
                             marker_payload={"seed": row["seed"], "group": row["group"]})
        record_set = _complete_record_set(job_root, run_uuid=f"holdout-seed{row['seed']}")
        validate_record_set(record_set)
        receipts.append({"seed": row["seed"], "record_set_path": str(record_set), "record_set_sha256": artifact_hash(record_set),
                         "process_receipt_sha256": artifact_hash(job_root / "process_receipt.json"), "exit_code": receipt["exit_code"]})
    return {"schema": "a2_piper_base_v20_R2_training_attempt_v1", "producer_state": "PROCESS_COMPLETED",
            "attempt_id": "holdout", "group": rows[0]["group"], "command": rows[0]["argv"], "env": rows[0]["env"],
            "source_lock_sha256": marker_payload["source_lock_sha256"], "config_sha256": marker_payload["config_sha256"],
            "checkpoint_sha256": rows[0]["checkpoint_sha256"], "release_freeze_sha256": artifact_hash(release_freeze),
            "seeds": receipts}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-freeze", type=Path, required=True); parser.add_argument("--physical-gpus", required=True)
    parser.add_argument("--seeds", default=",".join(map(str, HOLDOUT_SEEDS))); parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True); parser.add_argument("--attempt-marker", type=Path)
    args = parser.parse_args(argv)
    seeds = tuple(int(item) for item in args.seeds.split(",") if item)
    # The contract fixes seeds; parsing is retained only to fail fast on substitutions.
    if seeds != HOLDOUT_SEEDS:
        raise R2Error("holdout seeds must be exactly 3,4,5,6")
    result = run_holdout(release_freeze=args.release_freeze, repo_root=args.repo_root,
                         physical_gpus=parse_gpus(args.physical_gpus), output_root=args.output_root,
                         attempt_marker=args.attempt_marker)
    print(canonical_json(result)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
