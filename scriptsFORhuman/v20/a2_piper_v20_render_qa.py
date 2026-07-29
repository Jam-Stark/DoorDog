"""Strict media/provenance/behavior QA for v20 matched render artifacts."""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import yaml


SCHEMA = "a2_piper_v20_render_qa_v1"
QUEUE_SCHEMA = "a2_piper_v20_render_queue_v1"
MEDIA_SCHEMA = "a2_piper_v20_media_manifest_v1"
BEHAVIOR_SCHEMA = "a2_piper_v20_behavior_review_v1"
BEHAVIOR_GATES = (
    "no_premature_root_crossing",
    "arm_visibly_initiates_and_sustains_send",
    "base_follows_only_after_send",
    "no_abrupt_fling",
    "no_visible_grasp_loss",
    "no_body_or_leg_door_collision",
    "controlled_release_and_passage",
)


class V20RenderQAError(ValueError):
    pass


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise V20RenderQAError(f"cannot read {path}: {exc}") from exc


def probe_video(path: Path) -> dict[str, Any]:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "stream=codec_type,width,height,r_frame_rate,duration",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(path),
    ]
    try:
        completed = subprocess.run(command, check=False, text=True, capture_output=True)
    except OSError as exc:
        raise V20RenderQAError(f"cannot execute ffprobe for {path}: {exc}") from exc
    if completed.returncode != 0:
        raise V20RenderQAError(f"ffprobe failed for {path}: {completed.stderr.strip()}")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise V20RenderQAError(f"ffprobe returned invalid JSON for {path}") from exc
    streams = [
        stream for stream in payload.get("streams", []) if stream.get("codec_type") == "video"
    ]
    if len(streams) != 1:
        raise V20RenderQAError(f"{path} must contain exactly one decodable video stream")
    stream = streams[0]
    try:
        numerator, denominator = (int(value) for value in stream["r_frame_rate"].split("/", 1))
        fps = numerator / denominator
        duration = float(stream.get("duration") or payload["format"]["duration"])
        width, height = int(stream["width"]), int(stream["height"])
    except (KeyError, TypeError, ValueError, ZeroDivisionError) as exc:
        raise V20RenderQAError(f"ffprobe metadata is malformed for {path}") from exc
    if width <= 0 or height <= 0 or not math.isfinite(fps) or fps <= 0 or not math.isfinite(duration) or duration <= 0:
        raise V20RenderQAError(f"ffprobe metadata is invalid for {path}")
    return {"width": width, "height": height, "fps": fps, "duration_s": duration}


def _validate_hydra(artifact: Path, queue_row: Mapping[str, Any]) -> None:
    config_path = artifact / ".hydra" / "config.yaml"
    try:
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise V20RenderQAError(f"cannot read render Hydra config {config_path}") from exc
    if not isinstance(config, Mapping):
        raise V20RenderQAError(f"render Hydra config must be a mapping: {config_path}")
    checkpoint = Path(str(config.get("checkpoint", ""))).expanduser().resolve()
    if checkpoint != Path(queue_row["checkpoint"]).resolve():
        raise V20RenderQAError(f"{queue_row['group']} checkpoint/Hydra mismatch")
    if config.get("checkpoint_load_mode") != "full" or config.get("auto_load_latest") is not False:
        raise V20RenderQAError(f"{queue_row['group']} render checkpoint load contract mismatch")
    if config.get("num_envs") != 3 or config.get("seed") != queue_row["seed"]:
        raise V20RenderQAError(f"{queue_row['group']} render topology mismatch")
    evaluation = config.get("algo", {}).get("config", {}).get("eval", {})
    if (
        not isinstance(evaluation, Mapping)
        or evaluation.get("num_eval_episodes") != 3
        or evaluation.get("a2_eval_v20_strict_telemetry") is not True
        or evaluation.get("a2_eval_m41_strict_telemetry") is not True
    ):
        raise V20RenderQAError(f"{queue_row['group']} strict telemetry config mismatch")


def validate_render_artifact(
    queue_row: Mapping[str, Any],
    artifact: Path,
    *,
    probe_fn: Callable[[Path], Mapping[str, Any]] = probe_video,
) -> dict[str, Any]:
    artifact = Path(artifact).expanduser().resolve()
    if not artifact.is_dir():
        raise V20RenderQAError(f"render artifact directory is missing: {artifact}")
    writing = [path for path in artifact.rglob("*") if path.name.endswith(".writing")]
    if writing:
        raise V20RenderQAError(f"render artifact contains .writing remnants: {writing}")
    _validate_hydra(artifact, queue_row)
    media = _load_json(artifact / "a2_piper_v20_media_manifest.json")
    if media.get("schema") != MEDIA_SCHEMA or media.get("group") != queue_row["group"]:
        raise V20RenderQAError(f"{queue_row['group']} media manifest binding mismatch")
    if media.get("checkpoint") != queue_row["checkpoint"] or media.get("checkpoint_sha256") != queue_row["checkpoint_sha256"]:
        raise V20RenderQAError(f"{queue_row['group']} media checkpoint binding mismatch")
    rows = media.get("rows")
    if not isinstance(rows, list) or len(rows) != queue_row["expected_video_count"]:
        raise V20RenderQAError(f"{queue_row['group']} media manifest must contain 9 rows")
    expected = {
        (door["door_id"], camera)
        for door in (
            {"door_id": "low_light_weak"},
            {"door_id": "high_heavy_strong"},
            {"door_id": "median"},
        )
        for camera in queue_row["expected_camera_names"]
    }
    observed = set()
    probes = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise V20RenderQAError("media rows must be mappings")
        key = (row.get("door_id"), row.get("camera"))
        if key in observed or key not in expected:
            raise V20RenderQAError(f"media door/camera topology mismatch: {key}")
        observed.add(key)
        path = (artifact / str(row.get("path", ""))).resolve()
        if not path.is_file() or not path.is_relative_to(artifact):
            raise V20RenderQAError(f"media path is missing/outside artifact: {path}")
        measured = dict(probe_fn(path))
        for field in ("width", "height", "fps"):
            expected_value = row.get(field)
            if field == "fps":
                if not math.isclose(float(measured[field]), float(expected_value), rel_tol=0, abs_tol=1e-6):
                    raise V20RenderQAError(f"{path} fps mismatch")
            elif measured[field] != expected_value:
                raise V20RenderQAError(f"{path} {field} mismatch")
        probes.append({"door_id": key[0], "camera": key[1], "path": str(path), **measured})
    if observed != expected:
        raise V20RenderQAError(f"{queue_row['group']} media coverage is incomplete")
    contact_sheets = []
    for door_id in ("low_light_weak", "high_heavy_strong", "median"):
        path = artifact / "contact_sheets" / f"{door_id}.png"
        if not path.is_file() or path.stat().st_size <= 0:
            raise V20RenderQAError(f"contact sheet is missing/empty: {path}")
        contact_sheets.append(str(path))
    behavior = _load_json(artifact / "a2_piper_v20_behavior_review.json")
    if behavior.get("schema") != BEHAVIOR_SCHEMA or behavior.get("group") != queue_row["group"]:
        raise V20RenderQAError(f"{queue_row['group']} behavior review binding mismatch")
    gates = behavior.get("gates")
    if not isinstance(gates, Mapping) or set(gates) != set(BEHAVIOR_GATES):
        raise V20RenderQAError(f"{queue_row['group']} behavior gate topology mismatch")
    if any(not isinstance(gates[name], bool) for name in BEHAVIOR_GATES):
        raise V20RenderQAError(f"{queue_row['group']} behavior gates must be bool")
    failed = [name for name in BEHAVIOR_GATES if not gates[name]]
    return {
        "group": queue_row["group"],
        "checkpoint": queue_row["checkpoint"],
        "checkpoint_sha256": queue_row["checkpoint_sha256"],
        "media_status": "PASS",
        "behavior_status": "PASS" if not failed else "FAIL",
        "failed_behavior_gates": failed,
        "videos": probes,
        "contact_sheets": contact_sheets,
    }


def build_render_qa(
    queue: Mapping[str, Any],
    artifacts: Mapping[str, Path],
    *,
    probe_fn: Callable[[Path], Mapping[str, Any]] = probe_video,
) -> dict[str, Any]:
    physical_gpu = queue.get("physical_gpu")
    if queue.get("schema") != QUEUE_SCHEMA or physical_gpu not in {str(index) for index in range(7)} or queue.get("serial") is not True:
        raise V20RenderQAError("render queue schema/GPU0-6/serial contract mismatch")
    rows = queue.get("rows")
    if not isinstance(rows, list) or set(artifacts) != {row.get("group") for row in rows}:
        raise V20RenderQAError("render artifact mapping must exactly match queue groups")
    results = [
        validate_render_artifact(row, Path(artifacts[row["group"]]), probe_fn=probe_fn)
        for row in rows
    ]
    return {
        "schema": SCHEMA,
        "queue_core_schema_id": queue.get("core_schema_id"),
        "groups": {row["group"]: row for row in results},
        "media_status": "PASS",
        "behavior_status": "PASS"
        if all(row["behavior_status"] == "PASS" for row in results)
        else "FAIL",
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--artifact", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    artifacts = {}
    for token in args.artifact:
        if "=" not in token:
            raise V20RenderQAError("--artifact must be GROUP=PATH")
        group, path = token.split("=", 1)
        if group in artifacts:
            raise V20RenderQAError(f"duplicate artifact group {group}")
        artifacts[group] = Path(path)
    if args.output.exists():
        raise V20RenderQAError(f"refusing to overwrite {args.output}")
    report = build_render_qa(_load_json(args.queue), artifacts)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"render media={report['media_status']} behavior={report['behavior_status']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except V20RenderQAError as exc:
        print(f"v20 RENDER QA FAIL: {exc}", file=sys.stderr)
        raise SystemExit(2)
