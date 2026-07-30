"""Strict render evidence adjudicator for the R1 render queue."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _r1_common import (  # noqa: E402
    PLAN_ID,
    R1Error,
    RUNTIME_PASS,
    exact_digest,
    load_json,
    sha256_file,
    write_json_no_overwrite,
)


SCHEMA = "a2_piper_v20_R1_render_adjudication_v1"


def adjudicate_render(
    *,
    checkpoint: Path,
    checkpoint_sha256: str,
    config: Path,
    config_sha256: str,
    output_dir: Path,
    doors: tuple[str, ...],
    cameras: tuple[str, ...],
) -> dict[str, Any]:
    if not checkpoint.is_file() or checkpoint.is_symlink():
        raise R1Error("render checkpoint is missing or symlinked")
    if not config.is_file() or config.is_symlink():
        raise R1Error("render config is missing or symlinked")
    exact_digest(checkpoint_sha256, name="render checkpoint_sha256", length=64)
    exact_digest(config_sha256, name="render config_sha256", length=64)
    if sha256_file(checkpoint) != checkpoint_sha256:
        raise R1Error("render checkpoint hash mismatch")
    if sha256_file(config) != config_sha256:
        raise R1Error("render config hash mismatch")
    if not doors or not cameras:
        raise R1Error("render requires non-empty fixed door/camera sets")
    artifact = output_dir / "render_result.json"
    payload = load_json(artifact)
    if not isinstance(payload, Mapping):
        raise R1Error("render result must be a mapping")
    if payload.get("plan_id") != PLAN_ID or payload.get("status") != RUNTIME_PASS:
        raise R1Error("render result must be plan-bound RUNTIME PASS")
    if payload.get("checkpoint_sha256") != checkpoint_sha256 or payload.get("config_sha256") != config_sha256:
        raise R1Error("render result binding mismatch")
    if payload.get("doors") != list(doors) or payload.get("cameras") != list(cameras):
        raise R1Error("render result door/camera topology mismatch")
    result = {
        "schema": SCHEMA,
        "plan_id": PLAN_ID,
        "status": RUNTIME_PASS,
        "checkpoint_sha256": checkpoint_sha256,
        "config_sha256": config_sha256,
        "binding": {
            "checkpoint_sha256": checkpoint_sha256,
            "config_sha256": config_sha256,
        },
        "doors": list(doors),
        "cameras": list(cameras),
        "artifact": str(artifact),
        "render_complete": True,
    }
    write_json_no_overwrite(output_dir / "render_adjudication.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--checkpoint-sha256", required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--config-sha256", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--doors", required=True)
    parser.add_argument("--cameras", required=True)
    parser.add_argument("--device", required=True)
    args = parser.parse_args()
    if args.device != "cuda:0":
        raise SystemExit("render adjudicator requires logical cuda:0")
    adjudicate_render(
        checkpoint=args.checkpoint,
        checkpoint_sha256=args.checkpoint_sha256,
        config=args.config,
        config_sha256=args.config_sha256,
        output_dir=args.output_dir,
        doors=tuple(args.doors.split(",")),
        cameras=tuple(args.cameras.split(",")),
    )
