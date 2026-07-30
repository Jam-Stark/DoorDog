"""One-shot G4 policy learnability pilot producer."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from ._r2_common import R2Error, canonical_json, write_json_exclusive
from ._r2_workflow import (
    artifact_hash,
    config_identity,
    read_artifact,
    spawn_once,
    train_command,
    write_raw,
)

ATTEMPT_SCHEMA = "a2_piper_base_v20_R2_training_attempt_v1"
ATTEMPT_MARKER = "logs_eval/base_v20_R2/locks/PILOT_ATTEMPT_CONSUMED.json"


def build_pilot_command(*, repo_root: Path, config: Path, physical_gpu: int,
                        output_root: Path | None = None, checkpoint: Path | None = None) -> tuple[list[str], dict[str, str]]:
    root = Path(repo_root).resolve()
    output = output_root or root / "logs_rl/a2_piper_full_stage_a2_base/base_v20_R2/pilot/G4_seed0_256x750"
    if checkpoint is None:
        checkpoint = root / "logs_rl/a2_piper_full_stage_a2_base/base_v19/base_v19_G2_norm_control-20260727_012027/model_step_002000.pt"
    argv, env, _ = train_command(repo_root=root, config=config, gpu=physical_gpu, group="G4", seed=0,
                                 num_envs=256, batches=750, save_frequency=250,
                                 output_root=output, checkpoint=checkpoint, formal=False)
    return argv, env


def consume_pilot_parents(source_lock: Path, semantic_pass: Path, config: Path) -> dict[str, str]:
    source = read_artifact(source_lock, schema="a2_piper_base_v20_R2_source_lock_v1", producer_state="SOURCE_FROZEN")
    semantic = read_artifact(semantic_pass, schema="a2_piper_base_v20_R2_semantic_adjudication_v1", adjudicator_state="R2_P1_RUNTIME_SEMANTIC_PASS")
    if semantic.get("source_lock_sha256") not in (None, artifact_hash(source_lock)):
        raise R2Error("pilot semantic parent has a mismatched source lock")
    identity = config_identity(config)
    return {"source_lock_sha256": artifact_hash(source_lock), "semantic_pass_sha256": artifact_hash(semantic_pass), "config_sha256": identity["sha256"]}


def _attempt_payload(*, source_lock: Path, semantic_pass: Path, config: Path, checkpoint: Path,
                     command: list[str], env: dict[str, str], output_root: Path) -> dict[str, Any]:
    parents = consume_pilot_parents(source_lock, semantic_pass, config)
    return {
        "schema": ATTEMPT_SCHEMA, "producer_state": "ATTEMPT_CONSUMED",
        "attempt_id": "pilot-G4-seed0", "group": "G4", "command": command,
        "env": env, "source_lock_sha256": parents["source_lock_sha256"],
        "config_sha256": parents["config_sha256"], "checkpoint_sha256": artifact_hash(checkpoint),
        "semantic_pass_sha256": parents["semantic_pass_sha256"],
        "output_root": str(output_root), "num_envs": 256, "batches": 750,
        "save_frequency": 250,
    }


def consume_attempt(*, repo_root: Path, source_lock: Path, semantic_pass: Path,
                    config: Path, physical_gpu: int, output_root: Path,
                    checkpoint: Path | None = None, attempt_marker: Path | None = None,
                    launcher_root: Path | None = None) -> dict[str, object]:
    root = Path(repo_root).resolve()
    checkpoint = checkpoint or root / "logs_rl/a2_piper_full_stage_a2_base/base_v19/base_v19_G2_norm_control-20260727_012027/model_step_002000.pt"
    command, env = build_pilot_command(repo_root=root, config=config, physical_gpu=physical_gpu,
                                       output_root=output_root, checkpoint=checkpoint)
    payload = _attempt_payload(source_lock=source_lock, semantic_pass=semantic_pass, config=config,
                               checkpoint=checkpoint, command=command, env=env, output_root=output_root)
    marker = attempt_marker or root / ATTEMPT_MARKER
    write_raw(marker, payload, producer_state="ATTEMPT_CONSUMED")
    return payload


def run_pilot(*, repo_root: Path, source_lock: Path, semantic_pass: Path, config: Path,
              physical_gpu: int, output_root: Path, launcher_root: Path | None = None,
              checkpoint: Path | None = None, attempt_marker: Path | None = None) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    checkpoint = checkpoint or root / "logs_rl/a2_piper_full_stage_a2_base/base_v19/base_v19_G2_norm_control-20260727_012027/model_step_002000.pt"
    command, env = build_pilot_command(repo_root=root, config=config, physical_gpu=physical_gpu,
                                       output_root=output_root, checkpoint=checkpoint)
    payload = consume_attempt(repo_root=root, source_lock=source_lock, semantic_pass=semantic_pass,
                              config=config, physical_gpu=physical_gpu, output_root=output_root,
                              checkpoint=checkpoint, attempt_marker=attempt_marker,
                              launcher_root=launcher_root)
    marker = attempt_marker or root / ATTEMPT_MARKER
    receipt = spawn_once(argv=command, repo_root=root, output_root=output_root, env=env,
                         name="pilot_G4_seed0", physical_gpu=physical_gpu,
                         attempt_marker=marker, active_source_lock=source_lock,
                         parents={"semantic_pass": semantic_pass},
                         marker_payload={"attempt_sha256": artifact_hash(marker),
                                         "config_sha256": artifact_hash(config),
                                         "checkpoint_sha256": artifact_hash(checkpoint)})
    return {"attempt": str(marker), "attempt_sha256": artifact_hash(marker),
            "process_receipt": str(output_root / "process_receipt.json"),
            "receipt_sha256": artifact_hash(output_root / "process_receipt.json"),
            "producer_state": "PROCESS_COMPLETED", "payload": payload}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True); parser.add_argument("--source-lock", type=Path, required=True)
    parser.add_argument("--semantic-pass", type=Path, required=True); parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--physical-gpu", type=int, required=True); parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--launcher-root", type=Path); parser.add_argument("--checkpoint", type=Path); parser.add_argument("--attempt-marker", type=Path)
    args = parser.parse_args(argv)
    run_pilot(repo_root=args.repo_root, source_lock=args.source_lock, semantic_pass=args.semantic_pass,
              config=args.config, physical_gpu=args.physical_gpu, output_root=args.output_root,
              launcher_root=args.launcher_root, checkpoint=args.checkpoint, attempt_marker=args.attempt_marker)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
