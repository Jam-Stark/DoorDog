"""CPU-only contract tests for v19 render QA helpers."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest
import yaml


SOURCE = Path(__file__).resolve().parents[3] / "scriptsFORhuman/v19/a2_piper_v19_render_qa.py"


def _load():
    spec = importlib.util.spec_from_file_location("a2_piper_v19_render_qa_test", SOURCE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_parse_canonical_video_names():
    module = _load()
    rows = [
        module._parse_video(Path("2026_env0000_episode0000_len500_reason-complete.mp4")),
        module._parse_video(Path("2026_env0001_episode0000_handle_side_len501_reason-complete.mp4")),
        module._parse_video(Path("2026_env0001_episode0002_handle_top_len1_reason-stage_overtime.mp4")),
    ]
    assert [row["camera"] for row in rows] == ["default", "handle_side", "handle_top"]
    assert [row["episode_id"] for row in rows] == [0, 0, 2]


def test_j1_sweep_uses_held_stage_last_minus_first(tmp_path):
    module = _load()
    rows = []
    for env_id, delta in ((0, 0.4), (1, 0.2)):
        rows.extend(
            [
                {"env_id": env_id, "stage_buf": 2, "both_contact": False},
                {"env_id": env_id, "stage_buf": 3, "both_contact": True, "arm_joint_names": ["arm_j1"], "arm_joint_pos": [0.1]},
                {"env_id": env_id, "stage_buf": 5, "both_contact": True, "arm_joint_names": ["arm_j1"], "arm_joint_pos": [0.1 + delta], "terminal_reasons": "complete"},
            ]
        )
    (tmp_path / "stage2_5_step_trace.json").write_text(json.dumps(rows), encoding="utf-8")
    result = module._j1_sweep(tmp_path, 2)
    assert result[0]["arm_j1_delta_rad"] == pytest.approx(0.4)
    assert result[0]["arm_j1_delta_gt_0_3"] is True
    assert result[1]["arm_j1_delta_rad"] == pytest.approx(0.2)
    assert result[1]["arm_j1_delta_gt_0_3"] is False


def test_j1_sweep_requires_held_rows(tmp_path):
    module = _load()
    (tmp_path / "stage2_5_step_trace.json").write_text(
        json.dumps([{"env_id": 0, "stage_buf": 2, "both_contact": False}]), encoding="utf-8"
    )
    with pytest.raises(module.V19RenderQAError, match="lacks held"):
        module._j1_sweep(tmp_path, 1)


def test_render_config_requires_exact_queue_topology(tmp_path):
    module = _load()
    output = tmp_path / "render"
    hydra = output / ".hydra"
    hydra.mkdir(parents=True)
    checkpoint = tmp_path / "model_step_001750.pt"
    checkpoint.write_bytes(b"checkpoint")
    config = {
        "checkpoint": str(checkpoint), "checkpoint_load_mode": "full", "seed": 0, "num_envs": 2,
        "simulator": {"config": {"render_results": True}},
        "algo": {"config": {"num_mini_batches": 2, "eval": {
            "num_eval_episodes": 2, "eval_num_envs_episodes": True,
            "a2_eval_m41_strict_telemetry": True, "a2_diagnostic_trace_enabled": True,
        }}},
        "env": {"config": {
            "save_rendering_dir": str(output / "renderings"),
            "a2_eval_door_handle_height_linspace": [0.80, 1.10],
        }},
    }
    config_path = hydra / "config.yaml"
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    row = {"checkpoint": str(checkpoint), "num_envs": 2, "role": "winner"}
    assert module._config(row, output)["num_envs"] == 2
    config["algo"]["config"]["num_mini_batches"] = 1
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    with pytest.raises(module.V19RenderQAError, match="num_mini_batches"):
        module._config(row, output)



def test_g7_render_config_requires_exact_single_pair(tmp_path):
    module = _load()
    output = tmp_path / "g7_render"
    hydra = output / ".hydra"
    hydra.mkdir(parents=True)
    checkpoint = tmp_path / "model_step_001750.pt"
    checkpoint.write_bytes(b"checkpoint")
    config = {
        "checkpoint": str(checkpoint),
        "checkpoint_load_mode": "full",
        "seed": 0,
        "num_envs": 1,
        "simulator": {"config": {"render_results": True}},
        "algo": {
            "config": {
                "num_mini_batches": 1,
                "eval": {
                    "num_eval_episodes": 1,
                    "eval_num_envs_episodes": True,
                    "a2_eval_m41_strict_telemetry": True,
                    "a2_diagnostic_trace_enabled": True,
                },
            }
        },
        "env": {
            "config": {
                "save_rendering_dir": str(output / "renderings"),
                "a2_eval_door_handle_height_weight_pairs": [[1.10, 120.0]],
            }
        },
    }
    config_path = hydra / "config.yaml"
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    row = {"checkpoint": str(checkpoint), "num_envs": 1, "role": "g7_probe"}
    assert module._config(row, output)["num_envs"] == 1

    config["env"]["config"].pop("a2_eval_door_handle_height_weight_pairs")
    config["env"]["config"]["a2_eval_door_handle_height_linspace"] = [1.10, 1.10]
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    with pytest.raises(module.V19RenderQAError, match="single height-weight pair"):
        module._config(row, output)

def test_contact_sheet_and_invalid_queue(tmp_path):
    module = _load()
    frames = [np.full((720, 1280, 3), index * 20, dtype=np.uint8) for index in range(6)]
    sheet = tmp_path / "sheet.jpg"
    module._write_contact_sheet(frames, sheet, "env0 default")
    image = cv2.imread(str(sheet))
    assert image is not None and image.shape == (360, 960, 3)
    with pytest.raises(module.V19RenderQAError, match="schema"):
        module.build_report({"schema": "wrong", "serial": True, "row_count": 2, "rows": []}, tmp_path / "q.json")
