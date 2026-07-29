from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[3]


def _load(filename: str, name: str):
    path = ROOT / "scriptsFORhuman/v20" / filename
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


QUEUE = _load("a2_piper_v20_render_queue.py", "v20_render_queue_test")
QA = _load("a2_piper_v20_render_qa.py", "v20_render_qa_test")


def _queue(tmp_path: Path) -> dict:
    checkpoints = {}
    for group in QUEUE.DEFAULT_RENDER_GROUPS:
        path = tmp_path / group / "model_step_001000.pt"
        path.parent.mkdir()
        path.write_bytes(group.encode())
        checkpoints[group] = path
    return QUEUE.build_queue(checkpoints, tmp_path / "outputs")


def _artifact(tmp_path: Path, row: dict, *, behavior_pass: bool = True) -> Path:
    artifact = tmp_path / "artifacts" / row["group"]
    (artifact / ".hydra").mkdir(parents=True)
    (artifact / ".hydra" / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "checkpoint": row["checkpoint"],
                "checkpoint_load_mode": "full",
                "auto_load_latest": False,
                "num_envs": 3,
                "seed": row["seed"],
                "algo": {
                    "config": {
                        "eval": {
                            "num_eval_episodes": 3,
                            "a2_eval_v20_strict_telemetry": True,
                            "a2_eval_m41_strict_telemetry": True,
                        }
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    rows = []
    for door_id in ("low_light_weak", "high_heavy_strong", "median"):
        for camera in row["expected_camera_names"]:
            relative = Path("videos") / f"{door_id}_{camera}.mp4"
            path = artifact / relative
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(b"fake")
            rows.append(
                {
                    "door_id": door_id,
                    "camera": camera,
                    "path": str(relative),
                    "width": 1280,
                    "height": 720,
                    "fps": 20.0,
                }
            )
    (artifact / "a2_piper_v20_media_manifest.json").write_text(
        json.dumps(
            {
                "schema": QA.MEDIA_SCHEMA,
                "group": row["group"],
                "checkpoint": row["checkpoint"],
                "checkpoint_sha256": row["checkpoint_sha256"],
                "rows": rows,
            }
        ),
        encoding="utf-8",
    )
    sheets = artifact / "contact_sheets"
    sheets.mkdir()
    for door_id in ("low_light_weak", "high_heavy_strong", "median"):
        (sheets / f"{door_id}.png").write_bytes(b"png")
    gates = {name: True for name in QA.BEHAVIOR_GATES}
    if not behavior_pass:
        gates["base_follows_only_after_send"] = False
    (artifact / "a2_piper_v20_behavior_review.json").write_text(
        json.dumps(
            {
                "schema": QA.BEHAVIOR_SCHEMA,
                "group": row["group"],
                "gates": gates,
            }
        ),
        encoding="utf-8",
    )
    return artifact


def test_render_qa_requires_exact_media_and_behavior(tmp_path: Path) -> None:
    queue = _queue(tmp_path)
    artifacts = {
        row["group"]: _artifact(
            tmp_path, row, behavior_pass=row["group"] != "G6"
        )
        for row in queue["rows"]
    }
    probe = lambda _path: {"width": 1280, "height": 720, "fps": 20.0, "duration_s": 5.0}
    report = QA.build_render_qa(queue, artifacts, probe_fn=probe)
    assert report["media_status"] == "PASS"
    assert report["behavior_status"] == "FAIL"
    assert report["groups"]["G6"]["failed_behavior_gates"] == [
        "base_follows_only_after_send"
    ]

    missing = artifacts["G1"] / "videos" / "median_handle_top.mp4"
    missing.unlink()
    with pytest.raises(QA.V20RenderQAError, match="missing/outside"):
        QA.build_render_qa(queue, artifacts, probe_fn=probe)


def test_render_queue_defaults_only_for_exact_g1_g3_g6_g7(tmp_path: Path) -> None:
    queue = _queue(tmp_path)
    assert queue["physical_gpu"] == "6"
    assert queue["selected_institution_group"] == "G3"
    checkpoints = {}
    for group in ("G1", "G4", "G6", "G7"):
        path = tmp_path / f"alt_{group}" / "model_step_001000.pt"
        path.parent.mkdir()
        path.write_bytes(group.encode())
        checkpoints[group] = path
    with pytest.raises(QUEUE.V20RenderQueueError, match="selected_group is required"):
        QUEUE.build_queue(checkpoints, tmp_path / "alt")
    assert QUEUE.build_queue(
        checkpoints, tmp_path / "alt", selected_group="G4"
    )["selected_institution_group"] == "G4"


@pytest.mark.parametrize("gpu", ["7", "-1", "01", "", 6, True])
def test_render_queue_rejects_devices_outside_physical_gpu0_to_gpu6(tmp_path: Path, gpu) -> None:
    checkpoints = {}
    for group in QUEUE.DEFAULT_RENDER_GROUPS:
        path = tmp_path / f"invalid_{group}" / "model_step_001000.pt"
        path.parent.mkdir()
        path.write_bytes(group.encode())
        checkpoints[group] = path
    with pytest.raises(QUEUE.V20RenderQueueError, match="GPU7 is reserved"):
        QUEUE.build_queue(checkpoints, tmp_path / "invalid_outputs", gpu=gpu)
