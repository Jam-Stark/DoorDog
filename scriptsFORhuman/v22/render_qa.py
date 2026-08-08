"""Build compact three-camera contact sheets for one completed v22 render root."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np


CAMERAS = ("overview", "handle_top", "handle_side")
FRAME_FRACTIONS = (0.15, 0.45, 0.70, 0.95)


def _env_score(trace: list[dict], env_id: int, goal: bool) -> tuple:
    rows = [row for row in trace if int(row["env_id"]) == env_id]
    eligible = any(bool(row.get("body_assist_eligible", False)) for row in rows)
    body_force = max(
        (float(row.get("door_body_panel_normal_force_total", 0.0)) for row in rows),
        default=0.0,
    )
    return (eligible, body_force, goal, -env_id)


def _select_env(scenario_root: Path) -> int:
    records = json.loads(
        (scenario_root / "a2_v14_per_env_records.json").read_text(encoding="utf-8")
    )
    trace = json.loads(
        (scenario_root / "stage2_step_trace.json").read_text(encoding="utf-8")
    )
    goals = {
        int(row.get("env_id", index)): bool(row.get("goal_reached", False))
        for index, row in enumerate(records)
    }
    return max(range(16), key=lambda env_id: _env_score(trace, env_id, goals[env_id]))


def _video_for(scenario_root: Path, env_id: int, camera: str) -> Path:
    marker = "" if camera == "overview" else f"_{camera}"
    matches = sorted(
        (scenario_root / "renderings").glob(
            f"*_env{env_id:04d}_episode0000{marker}_len*.mp4"
        )
    )
    if len(matches) != 1:
        raise RuntimeError(
            f"expected one {camera} episode-0 video for env {env_id} in {scenario_root}; got {matches}"
        )
    return matches[0]


def _frames(video: Path) -> list[np.ndarray]:
    capture = cv2.VideoCapture(str(video))
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    if frame_count < 4:
        raise RuntimeError(f"video has too few frames: {video}")
    output = []
    for fraction in FRAME_FRACTIONS:
        capture.set(cv2.CAP_PROP_POS_FRAMES, round((frame_count - 1) * fraction))
        ok, frame = capture.read()
        if not ok:
            raise RuntimeError(f"cannot decode {video} at fraction {fraction}")
        frame = cv2.resize(frame, (480, 270), interpolation=cv2.INTER_AREA)
        cv2.putText(
            frame,
            f"{fraction:.0%}",
            (12, 28),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.75,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        output.append(frame)
    capture.release()
    return output


def _sheet(scenario: str, env_id: int, videos: dict[str, Path], target: Path) -> None:
    rows = []
    for camera in CAMERAS:
        frames = _frames(videos[camera])
        cv2.putText(
            frames[0],
            camera,
            (12, 258),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (0, 255, 255),
            2,
            cv2.LINE_AA,
        )
        rows.append(np.concatenate(frames, axis=1))
    canvas = np.concatenate(rows, axis=0)
    header = np.zeros((55, canvas.shape[1], 3), dtype=np.uint8)
    cv2.putText(
        header,
        f"v22 render QA | {scenario} | env {env_id:04d}",
        (18, 37),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(target), np.concatenate((header, canvas), axis=0)):
        raise RuntimeError(f"failed to write contact sheet {target}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--render-root", type=Path, required=True)
    args = parser.parse_args()
    summary = json.loads(
        (args.render_root / "V22_RENDER_SUMMARY.json").read_text(encoding="utf-8")
    )
    if summary["status"] != "RENDER_PASS":
        raise RuntimeError("render summary is not RENDER_PASS")

    manifest = {
        "schema": "a2_piper_base_v22_render_qa_manifest_v1",
        "render_root": str(args.render_root),
        "selection_path": summary["selection_path"],
        "selection_rule": (
            "prefer an env with body-assist eligibility/contact force, then goal success, then lowest env id"
        ),
        "frame_fractions": list(FRAME_FRACTIONS),
        "sheets": [],
    }
    for scenario in summary["scenarios"]:
        scenario_root = args.render_root / scenario
        env_id = _select_env(scenario_root)
        videos = {camera: _video_for(scenario_root, env_id, camera) for camera in CAMERAS}
        target = args.render_root / "qa" / f"{scenario}__env{env_id:04d}.png"
        _sheet(scenario, env_id, videos, target)
        manifest["sheets"].append(
            {
                "scenario": scenario,
                "env_id": env_id,
                "contact_sheet": str(target),
                "videos": {camera: str(path) for camera, path in videos.items()},
            }
        )
        print(f"WROTE {target}")
    target = args.render_root / "qa" / "qa_manifest.json"
    target.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"WROTE {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
