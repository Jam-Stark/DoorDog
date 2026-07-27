"""Validate v19 winner/G7 render artifacts and quantify the arm-j1 carry sweep."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import cv2
import numpy as np
import yaml


SCHEMA = "a2_piper_v19_render_qa_v1"
QUEUE_SCHEMA = "a2_piper_v19_render_queue_v1"
VIDEO_RE = re.compile(
    r"^.+_env(?P<env>[0-9]{4})_episode(?P<episode>[0-9]{4})"
    r"(?P<camera>_handle_side|_handle_top)?_len(?P<length>[0-9]+)_reason-(?P<reason>.+)\.mp4$"
)
CAMERAS = ("default", "handle_side", "handle_top")


class V19RenderQAError(ValueError):
    """Raised when render provenance, video topology, or trace evidence is invalid."""


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise V19RenderQAError(f"cannot load JSON {path}: {exc}") from exc


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise V19RenderQAError(f"{name} must be a mapping")
    return value


def _nested(payload: Mapping[str, Any], name: str, *keys: str) -> Any:
    value: Any = payload
    for key in keys:
        if not isinstance(value, Mapping) or key not in value:
            raise V19RenderQAError(f"{name} is missing {'.'.join(keys)}")
        value = value[key]
    return value


def _exact_exit(path: Path) -> int:
    try:
        text = path.read_text(encoding="utf-8").strip()
        value = int(text)
    except (OSError, ValueError) as exc:
        raise V19RenderQAError(f"missing or invalid render exit code: {path}") from exc
    if text != str(value) or value != 0:
        raise V19RenderQAError(f"render exit code must be exact zero: {path}")
    return value


def _parse_video(path: Path) -> dict[str, Any]:
    match = VIDEO_RE.fullmatch(path.name)
    if match is None:
        raise V19RenderQAError(f"render filename is not canonical: {path.name}")
    camera_token = match.group("camera")
    camera = "default" if camera_token is None else camera_token.removeprefix("_")
    return {
        "path": str(path.resolve()),
        "env_id": int(match.group("env")),
        "episode_id": int(match.group("episode")),
        "camera": camera,
        "filename_length": int(match.group("length")),
        "terminal_reason": match.group("reason"),
    }


def _decode(path: Path) -> tuple[dict[str, Any], list[np.ndarray]]:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise V19RenderQAError(f"cannot open video: {path}")
    advertised = int(round(capture.get(cv2.CAP_PROP_FRAME_COUNT)))
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    frames: list[np.ndarray] = []
    decoded = 0
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            if frame.ndim != 3 or frame.shape[:2] != (720, 1280) or frame.shape[2] != 3:
                raise V19RenderQAError(f"video frame resolution must be 1280x720x3: {path}")
            frames.append(frame) if decoded == 0 else None
            decoded += 1
    finally:
        capture.release()
    if decoded <= 0:
        raise V19RenderQAError(f"video contains no decodable frames: {path}")
    if advertised > 0 and decoded != advertised:
        raise V19RenderQAError(f"video advertised/decoded frame mismatch: {path}: {advertised}!={decoded}")
    if not math.isfinite(fps) or abs(fps - 20.0) > 0.01:
        raise V19RenderQAError(f"video fps must equal 20: {path}: {fps}")

    sample_indices = sorted({round(index * (decoded - 1) / 5) for index in range(6)})
    sampled: list[np.ndarray] = []
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise V19RenderQAError(f"cannot reopen video for contact sheet: {path}")
    try:
        for index in sample_indices:
            if not capture.set(cv2.CAP_PROP_POS_FRAMES, index):
                raise V19RenderQAError(f"cannot seek video frame {index}: {path}")
            ok, frame = capture.read()
            if not ok:
                raise V19RenderQAError(f"cannot decode sampled frame {index}: {path}")
            sampled.append(frame)
    finally:
        capture.release()
    return {
        "decoded_frames": decoded,
        "advertised_frames": advertised,
        "width": 1280,
        "height": 720,
        "fps": fps,
        "sampled_frame_indices": sample_indices,
    }, sampled


def _write_contact_sheet(frames: Sequence[np.ndarray], path: Path, label: str) -> None:
    if not frames:
        raise V19RenderQAError("contact sheet requires sampled frames")
    cells = []
    for index, frame in enumerate(frames):
        cell = cv2.resize(frame, (320, 180), interpolation=cv2.INTER_AREA)
        cv2.putText(
            cell,
            f"{label} sample{index}",
            (8, 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
        cells.append(cell)
    while len(cells) < 6:
        cells.append(cells[-1].copy())
    sheet = np.vstack((np.hstack(cells[:3]), np.hstack(cells[3:6])))
    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), sheet):
        raise V19RenderQAError(f"cannot write contact sheet: {path}")


def _config(row: Mapping[str, Any], output_dir: Path) -> dict[str, Any]:
    config_path = output_dir / ".hydra/config.yaml"
    try:
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise V19RenderQAError(f"cannot read Hydra config: {config_path}") from exc
    config = _mapping(config, "render Hydra config")
    checkpoint = Path(str(config.get("checkpoint", ""))).expanduser().resolve()
    expected_checkpoint = Path(str(row.get("checkpoint", ""))).expanduser().resolve()
    if checkpoint != expected_checkpoint or not checkpoint.is_file():
        raise V19RenderQAError("render checkpoint does not match queue")
    num_envs = row.get("num_envs")
    if config.get("checkpoint_load_mode") != "full" or config.get("seed") != 0 or config.get("num_envs") != num_envs:
        raise V19RenderQAError("render checkpoint-load/seed/num-env contract is invalid")
    if _nested(config, "render config", "simulator", "config", "render_results") is not True:
        raise V19RenderQAError("render_results must be true")
    if _nested(config, "render config", "algo", "config", "num_mini_batches") != num_envs:
        raise V19RenderQAError("render num_mini_batches must equal num_envs")
    evaluation = _mapping(_nested(config, "render config", "algo", "config", "eval"), "render eval config")
    if evaluation.get("num_eval_episodes") != num_envs or evaluation.get("eval_num_envs_episodes") is not True:
        raise V19RenderQAError("render eval episode topology is invalid")
    if evaluation.get("a2_eval_m41_strict_telemetry") is not True or evaluation.get("a2_diagnostic_trace_enabled") is not True:
        raise V19RenderQAError("render strict telemetry/trace must be enabled")
    rendering_dir = Path(
        str(_nested(config, "render config", "env", "config", "save_rendering_dir"))
    ).expanduser().resolve()
    if rendering_dir != (output_dir / "renderings").resolve():
        raise V19RenderQAError("rendering directory does not match queue output")
    env_config = _mapping(
        _nested(config, "render config", "env", "config"), "render env config"
    )
    bounds_key = "a2_eval_door_handle_height_linspace"
    pairs_key = "a2_eval_door_handle_height_weight_pairs"
    if row.get("role") == "winner":
        if pairs_key in env_config or env_config.get(bounds_key) != [0.80, 1.10]:
            raise V19RenderQAError(
                "winner render height topology must be the exact endpoint grid"
            )
    else:
        if bounds_key in env_config or env_config.get(pairs_key) != [[1.10, 120.0]]:
            raise V19RenderQAError(
                "G7 render topology must be the exact single height-weight pair"
            )
    return {"path": str(config_path.resolve()), "checkpoint": str(checkpoint), "num_envs": num_envs}


def _j1_sweep(output_dir: Path, num_envs: int) -> list[dict[str, Any]]:
    trace_path = output_dir / "stage2_5_step_trace.json"
    payload = _load_json(trace_path)
    if not isinstance(payload, list):
        raise V19RenderQAError(f"render trace must be a list: {trace_path}")
    results = []
    for env_id in range(num_envs):
        rows = [row for row in payload if isinstance(row, Mapping) and row.get("env_id") == env_id]
        if not rows:
            raise V19RenderQAError(f"render trace lacks env{env_id}")
        held = [
            row
            for row in rows
            if row.get("stage_buf") in (3, 4, 5) and row.get("both_contact") is True
        ]
        if not held:
            raise V19RenderQAError(f"render trace env{env_id} lacks held stage3/4/5 rows")
        names = held[0].get("arm_joint_names")
        if not isinstance(names, list) or "arm_j1" not in names:
            raise V19RenderQAError(f"render trace env{env_id} lacks arm_j1 names")
        if any(row.get("arm_joint_names") != names for row in held):
            raise V19RenderQAError(f"render trace env{env_id} arm joint order changed")
        joint_index = names.index("arm_j1")
        values = []
        for row in held:
            positions = row.get("arm_joint_pos")
            if not isinstance(positions, list) or len(positions) != len(names):
                raise V19RenderQAError(f"render trace env{env_id} arm position shape is invalid")
            value = positions[joint_index]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                raise V19RenderQAError(f"render trace env{env_id} arm_j1 is not finite")
            values.append(float(value))
        delta = values[-1] - values[0]
        terminal = rows[-1].get("terminal_reasons")
        results.append(
            {
                "env_id": env_id,
                "held_row_count": len(held),
                "arm_j1_first_rad": values[0],
                "arm_j1_last_rad": values[-1],
                "arm_j1_delta_rad": delta,
                "arm_j1_delta_gt_0_3": delta > 0.3,
                "terminal_reason": terminal,
            }
        )
    return results


def _artifact(row_value: Any) -> dict[str, Any]:
    row = _mapping(row_value, "render queue row")
    output_dir = Path(str(row.get("output_dir", ""))).expanduser().resolve()
    if not output_dir.is_dir():
        raise V19RenderQAError(f"render output does not exist: {output_dir}")
    _exact_exit(output_dir / "eval_exit_code.txt")
    config = _config(row, output_dir)
    renderings = output_dir / "renderings"
    if not renderings.is_dir():
        raise V19RenderQAError(f"renderings directory does not exist: {renderings}")
    writing = [path for path in renderings.rglob("*") if ".writing" in path.name]
    if writing:
        raise V19RenderQAError(f"render artifact contains unfinished files: {writing}")
    videos = sorted(renderings.glob("*.mp4"))
    if not videos:
        raise V19RenderQAError(f"render artifact has no MP4 files: {renderings}")
    parsed = [_parse_video(path) for path in videos]
    num_envs = row.get("num_envs")
    if isinstance(num_envs, bool) or not isinstance(num_envs, int) or num_envs <= 0:
        raise V19RenderQAError("render queue num_envs is invalid")
    primary = [video for video in parsed if video["episode_id"] == 0]
    topology = {(video["env_id"], video["camera"]) for video in primary}
    expected = {(env_id, camera) for env_id in range(num_envs) for camera in CAMERAS}
    if topology != expected or len(primary) != len(expected):
        raise V19RenderQAError(f"primary render topology mismatch: expected {sorted(expected)}, got {sorted(topology)}")
    if any(video["env_id"] not in range(num_envs) for video in parsed):
        raise V19RenderQAError("render contains an out-of-range env id")

    qa_dir = output_dir / "video_qa"
    decoded_rows = []
    for video in parsed:
        path = Path(video["path"])
        decoded, sampled = _decode(path)
        video.update(decoded)
        decoded_rows.append(video)
        if video["episode_id"] == 0:
            sheet = qa_dir / f"env{video['env_id']:02d}_{video['camera']}_episode0_contact_sheet.jpg"
            _write_contact_sheet(sampled, sheet, f"env{video['env_id']} {video['camera']}")
            video["contact_sheet"] = str(sheet.resolve())
    sweep = _j1_sweep(output_dir, num_envs)
    winner_gate = None
    if row.get("role") == "winner":
        winner_gate = {
            "target": "arm_j1 held-phase last-first delta > 0.3 rad for every rendered winner env",
            "pass": all(item["arm_j1_delta_gt_0_3"] for item in sweep),
        }
    return {
        "role": row.get("role"),
        "group": row.get("group"),
        "output_dir": str(output_dir),
        "checkpoint": row.get("checkpoint"),
        "config": config,
        "video_count": len(decoded_rows),
        "primary_video_count": len(primary),
        "auxiliary_video_count": len(decoded_rows) - len(primary),
        "videos": decoded_rows,
        "arm_j1_sweep": sweep,
        "winner_render_gate": winner_gate,
    }


def build_report(queue_value: Any, queue_path: Path) -> dict[str, Any]:
    queue = _mapping(queue_value, "render queue")
    rows = queue.get("rows")
    if queue.get("schema") != QUEUE_SCHEMA or queue.get("serial") is not True:
        raise V19RenderQAError("render queue schema/serial contract is invalid")
    if not isinstance(rows, list) or len(rows) != 2 or queue.get("row_count") != 2:
        raise V19RenderQAError("render queue must contain exactly winner and G7 rows")
    roles = [row.get("role") if isinstance(row, Mapping) else None for row in rows]
    if roles != ["winner", "g7_probe"]:
        raise V19RenderQAError("render queue role order must be winner then g7_probe")
    artifacts = [_artifact(row) for row in rows]
    return {
        "schema": SCHEMA,
        "status": "PASS",
        "queue": str(queue_path.resolve()),
        "artifacts": artifacts,
        "winner_render_gate": artifacts[0]["winner_render_gate"],
        "g7_render_observability": artifacts[1]["arm_j1_sweep"],
    }


def write_outputs(report: Mapping[str, Any], output_json: Path, output_md: Path) -> None:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# A2 Piper v19 render QA",
        "",
        f"Status: {report['status']}",
        f"Winner arm-j1 gate: {'PASS' if report['winner_render_gate']['pass'] else 'FAIL'}",
        "",
        "| Role | Group | Primary/Aux videos | arm_j1 deltas rad |",
        "|---|---|---:|---|",
    ]
    for row in report["artifacts"]:
        deltas = ", ".join(f"env{item['env_id']}={item['arm_j1_delta_rad']:.6f}" for item in row["arm_j1_sweep"])
        lines.append(
            f"| {row['role']} | {row['group']} | {row['primary_video_count']}/{row['auxiliary_video_count']} | {deltas} |"
        )
    output_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-md", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_report(_load_json(args.queue), args.queue)
    write_outputs(report, args.output_json, args.output_md)
    print(f"v19 render QA JSON: {args.output_json}")
    print(f"v19 render QA Markdown: {args.output_md}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except V19RenderQAError as exc:
        print(f"v19 RENDER QA FAIL: {exc}", file=sys.stderr)
        raise SystemExit(2)
