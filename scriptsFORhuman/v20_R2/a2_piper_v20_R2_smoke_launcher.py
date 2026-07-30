"""Executable one-shot seven-cell 64x50 smoke wave producer."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from ._r2_common import R2Error, canonical_json, write_json_exclusive
from ._r2_workflow import (
    GROUPS,
    artifact_hash,
    config_identity,
    parse_gpus,
    read_artifact,
    r2_config_path,
    spawn_once,
    train_command,
    write_raw,
)

ATTEMPT_SCHEMA = "a2_piper_base_v20_R2_training_attempt_v1"
ATTEMPT_MARKER = "logs_eval/base_v20_R2/locks/SMOKE_WAVE_ATTEMPT_CONSUMED.json"


def build_smoke_commands(*, repo_root: Path, configs: dict[str, Path], physical_gpus: tuple[int, ...],
                         training_root: Path | None = None) -> list[dict[str, object]]:
    if tuple(configs) != GROUPS or tuple(physical_gpus) != tuple(range(7)):
        raise R2Error("smoke requires exact G1-G7 config map and physical GPUs 0-6")
    root = Path(repo_root).resolve()
    base = training_root or root / "logs_rl/a2_piper_full_stage_a2_base_smoke/base_v20_R2"
    result: list[dict[str, object]] = []
    for group, gpu in zip(GROUPS, physical_gpus):
        group_root = base / group
        argv, env, binding = train_command(repo_root=root, config=configs[group], gpu=gpu, group=group,
                                           seed=0, num_envs=64, batches=50, save_frequency=50,
                                           output_root=group_root, formal=False)
        result.append({"group": group, "physical_gpu": gpu, "argv": argv, "env": env,
                       "device": binding, "config_sha256": config_identity(configs[group])["sha256"],
                       "output_root": str(group_root), "seed": 0, "batches": 50})
    if len({row["config_sha256"] for row in result}) != 7:
        raise R2Error("smoke configs must have distinct hashes")
    return result


def _attempt_payload(*, source_lock: Path, pilot_pass: Path, rows: list[dict[str, object]]) -> dict[str, object]:
    return {"schema": ATTEMPT_SCHEMA, "producer_state": "ATTEMPT_CONSUMED",
            "attempt_id": "smoke-wave-seed0", "group": "G1",
            "command": rows[0]["argv"], "env": rows[0]["env"],
            "source_lock_sha256": artifact_hash(source_lock),
            "config_sha256": rows[0]["config_sha256"], "pilot_pass_sha256": artifact_hash(pilot_pass),
            "groups": rows}


def consume_smoke(*, repo_root: Path, source_lock: Path, pilot_pass: Path,
                   configs: dict[str, Path], physical_gpus: tuple[int, ...], output_root: Path,
                   attempt_marker: Path | None = None, training_root: Path | None = None) -> dict[str, object]:
    source = read_artifact(source_lock, schema="a2_piper_base_v20_R2_source_lock_v1", producer_state="SOURCE_FROZEN")
    pilot = read_artifact(pilot_pass, schema="a2_piper_base_v20_R2_endpoint_report_v1", adjudicator_state="POLICY_LEARNABILITY_PASS")
    if pilot.get("source_lock_sha256") != artifact_hash(source_lock):
        raise R2Error("pilot parent source-lock mismatch")
    rows = build_smoke_commands(repo_root=repo_root, configs=configs, physical_gpus=physical_gpus,
                                training_root=training_root or output_root)
    payload = _attempt_payload(source_lock=source_lock, pilot_pass=pilot_pass, rows=rows)
    marker = attempt_marker or Path(repo_root).resolve() / ATTEMPT_MARKER
    write_raw(marker, payload, producer_state="ATTEMPT_CONSUMED")
    return payload


def run_smoke(*, repo_root: Path, source_lock: Path, pilot_pass: Path,
              configs: dict[str, Path], physical_gpus: tuple[int, ...], output_root: Path,
              attempt_marker: Path | None = None, launcher_root: Path | None = None) -> dict[str, object]:
    root = Path(repo_root).resolve()
    rows = build_smoke_commands(repo_root=root, configs=configs, physical_gpus=physical_gpus,
                                training_root=output_root)
    payload = consume_smoke(repo_root=root, source_lock=source_lock, pilot_pass=pilot_pass,
                            configs=configs, physical_gpus=physical_gpus, output_root=output_root,
                            attempt_marker=attempt_marker, training_root=output_root)
    marker = attempt_marker or root / ATTEMPT_MARKER
    receipts: list[dict[str, object]] = []
    for row in rows:
        group_root = Path(str(row["output_root"]))
        receipt = spawn_once(argv=row["argv"], repo_root=root, output_root=group_root,
                             env=row["env"], name=f"smoke_{row['group']}",
                             physical_gpu=int(row["physical_gpu"]), attempt_marker=marker,
                             active_source_lock=source_lock, parents={"pilot_pass": pilot_pass},
                             marker_payload={"group": row["group"], "config_sha256": row["config_sha256"]})
        receipts.append({"group": row["group"], "path": str(group_root / "process_receipt.json"),
                         "sha256": artifact_hash(group_root / "process_receipt.json"),
                         "exit_code": receipt["exit_code"]})
    return {"attempt": str(marker), "attempt_sha256": artifact_hash(marker),
            "producer_state": "PROCESS_COMPLETED", "groups": receipts, "payload": payload}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True); parser.add_argument("--source-lock", type=Path, required=True)
    parser.add_argument("--pilot-pass", type=Path, required=True); parser.add_argument("--configs", type=Path, required=False)
    parser.add_argument("--physical-gpus", required=True); parser.add_argument("--launcher-root", type=Path)
    parser.add_argument("--training-root", type=Path, required=True); parser.add_argument("--output-root", type=Path)
    parser.add_argument("--attempt-marker", type=Path)
    args = parser.parse_args(argv)
    config_root = args.configs or args.repo_root / "gr00t/rl/config/ablation/wbmanip"
    config_map = {group: r2_config_path(config_root, group) for group in GROUPS}
    output_root = args.output_root or args.training_root
    run_smoke(repo_root=args.repo_root, source_lock=args.source_lock, pilot_pass=args.pilot_pass,
              configs=config_map, physical_gpus=parse_gpus(args.physical_gpus), output_root=output_root,
              attempt_marker=args.attempt_marker, launcher_root=args.launcher_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
