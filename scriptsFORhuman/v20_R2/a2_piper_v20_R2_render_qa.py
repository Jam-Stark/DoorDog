"""Mechanical media QA: ffprobe plus full PyAV decode and sidecar binding."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path
from typing import Any

from ._r2_common import R2Error, canonical_json
from ._r2_workflow import artifact_hash, read_artifact, write_adjudication


def check_media_capabilities() -> None:
    try:
        import av  # noqa: F401
    except ImportError as exc:
        raise R2Error("render QA requires PyAV capability (python package av)") from exc
    if shutil.which("ffprobe") is None:
        raise R2Error("render QA requires ffprobe capability")


def _ffprobe(video: Path) -> dict[str, Any]:
    command = ["ffprobe", "-v", "error", "-show_entries",
               "stream=index,codec_name,width,height,r_frame_rate,nb_frames,duration:format=duration",
               "-of", "json", str(video)]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise R2Error(f"ffprobe failed for {video}: {result.stderr.strip()}")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise R2Error(f"ffprobe output is invalid JSON: {video}") from exc
    streams = payload.get("streams")
    if not isinstance(streams, list) or len(streams) != 1:
        raise R2Error(f"render video must contain exactly one stream: {video}")
    stream = streams[0]
    if stream.get("codec_name") != "h264" or stream.get("width") != 1280 or stream.get("height") != 720:
        raise R2Error(f"render video format mismatch: {video}")
    try:
        fps = float(Fraction(str(stream.get("r_frame_rate"))))
        duration = float(payload.get("format", {}).get("duration", stream.get("duration", 0)))
    except (TypeError, ValueError, ZeroDivisionError) as exc:
        raise R2Error(f"render video has invalid fps/duration: {video}") from exc
    if abs(fps - 20.0) > 1e-6 or duration <= 0.0:
        raise R2Error(f"render video fps/duration mismatch: {video}")
    return {"ffprobe": payload, "fps": fps, "duration_s": duration}


def _decode(video: Path) -> int:
    try:
        import av
        container = av.open(str(video))
    except Exception as exc:
        raise R2Error(f"PyAV cannot open render video: {video}") from exc
    count = 0
    try:
        stream = container.streams.video[0]
        for frame in container.decode(stream):
            count += 1
            if frame.width != 1280 or frame.height != 720:
                raise R2Error(f"decoded frame resolution mismatch: {video}")
    except Exception as exc:
        if isinstance(exc, R2Error):
            raise
        raise R2Error(f"PyAV full decode failed: {video}") from exc
    finally:
        container.close()
    if count <= 0:
        raise R2Error(f"render video decoded zero frames: {video}")
    return count


def _sidecar(video: Path, *, expected_checkpoint: str, expected_config: str) -> dict[str, Any]:
    candidates = [video.with_suffix(".jsonl"), video.with_suffix(".sidecar.jsonl")]
    path = next((candidate for candidate in candidates if candidate.is_file() and not candidate.is_symlink()), None)
    if path is None:
        raise R2Error(f"render sidecar is missing: {video}")
    rows = []
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise R2Error(f"render sidecar line {index} is invalid") from exc
        if not isinstance(row, dict):
            raise R2Error("render sidecar row must be an object")
        if row.get("checkpoint_sha256") != expected_checkpoint or row.get("config_sha256") != expected_config:
            raise R2Error("render sidecar checkpoint/config binding mismatch")
        if row.get("trace_sha256") in (None, "0" * 64):
            raise R2Error("render sidecar lacks production trace binding")
        rows.append(row)
    if not rows:
        raise R2Error("render sidecar is empty")
    return {"path": str(path), "sha256": artifact_hash(path), "row_count": len(rows)}


def qa_render(root: Path) -> dict[str, object]:
    check_media_capabilities()
    execution_files = sorted(root.rglob("render_execution.json"))
    if not execution_files:
        raise R2Error("render QA requires a child render_execution.json")
    execution = read_artifact(execution_files[0], schema="a2_piper_base_v20_R2_render_execution_v1", producer_state="PROCESS_COMPLETED")
    receipt_path = Path(str(execution.get("process_receipt", root / "process_receipt.json")))
    receipt = read_artifact(receipt_path, schema="a2_piper_base_v20_R2_process_receipt_v1", producer_state="PROCESS_COMPLETED")
    if receipt.get("exit_code") != 0 or receipt.get("natural_exit") is not True:
        raise R2Error("render process receipt is not a natural exit-zero receipt")
    videos = execution.get("videos")
    if not isinstance(videos, list) or not videos:
        raise R2Error("render execution has no produced videos")
    rows: list[dict[str, Any]] = []
    for item in videos:
        video = Path(str(item.get("path")))
        if not video.is_file() or video.is_symlink() or video.name.endswith(".writing"):
            raise R2Error(f"render media is missing/temporary: {video}")
        if item.get("sha256") != artifact_hash(video):
            raise R2Error(f"render media hash mismatch: {video}")
        probe = _ffprobe(video); frame_count = _decode(video)
        sidecar = _sidecar(video, expected_checkpoint=execution["checkpoint_sha256"], expected_config=execution["config_sha256"])
        if frame_count != sidecar["row_count"]:
            raise R2Error(f"render frame/sidecar row count mismatch: {video}")
        rows.append({"path": str(video), "sha256": item["sha256"], "frame_count": frame_count,
                     "width": 1280, "height": 720, "fps": probe["fps"], "duration_s": probe["duration_s"],
                     "ffprobe": probe["ffprobe"], "sidecar": sidecar})
    return {"schema": "a2_piper_base_v20_R2_semantic_adjudication_v1", "adjudicator_state": "RENDER_QA_PASS",
            "mode": "render-review", "raw_sha256": artifact_hash(execution_files[0]),
            "process_receipt_sha256": artifact_hash(receipt_path), "source_lock_sha256": receipt.get("active_source_lock_sha256"),
            "expectations": {"video_count": len(videos), "resolution": "1280x720", "fps": 20.0},
            "observed": {"video_count": len(rows), "videos": rows},
            "recomputed": {"all_media_valid": True, "full_decode": True, "sidecars_bound": True},
            "parents": {"execution": artifact_hash(execution_files[0]), "process_receipt": artifact_hash(receipt_path)}}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True); parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = qa_render(args.root)
    write_adjudication(args.output, result, "RENDER_QA_PASS")
    print(canonical_json(result)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
