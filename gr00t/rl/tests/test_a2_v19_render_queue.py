"""CPU-only tests for the v19 winner/G7 render queue."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "scriptsFORhuman/v19/a2_piper_v19_render_queue.py"
M22_SOURCE = ROOT / "scriptsFORhuman/v19/a2_piper_v19_m22_queue.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _checkpoints(tmp_path: Path) -> tuple[Path, Path]:
    winner = tmp_path / "model_step_001750.pt"
    g7 = tmp_path / "model_step_002000.pt"
    winner.write_bytes(b"winner")
    g7.write_bytes(b"g7")
    return winner, g7


def test_exact_winner_and_g7_render_topology(tmp_path):
    module = _load(SOURCE, "v19_render_queue_topology_test")
    m22 = _load(M22_SOURCE, "v19_render_queue_m22_terms_test")
    winner, g7 = _checkpoints(tmp_path)
    queue = module.build_queue("G1", winner, g7, tmp_path / "render", gpu="7")

    assert queue["schema"] == "a2_piper_v19_render_queue_v1"
    assert queue["serial"] is True
    assert queue["row_count"] == 2
    assert tuple(module.P0_DIAGNOSTIC_REWARD_TERMS) == tuple(m22.P0_DIAGNOSTIC_REWARD_TERMS)
    winner_row, g7_row = queue["rows"]
    assert (winner_row["role"], winner_row["group"], winner_row["num_envs"]) == ("winner", "G1", 2)
    assert (g7_row["role"], g7_row["group"], g7_row["num_envs"]) == ("g7_probe", "G7", 1)
    assert winner_row["expected_video_count"] == 6
    assert g7_row["expected_video_count"] == 3
    assert winner_row["expected_camera_names"] == ["default", "handle_side", "handle_top"]
    assert "++algo.config.num_mini_batches=2" in winner_row["argv"]
    assert "++algo.config.eval.num_eval_episodes=2" in winner_row["argv"]
    assert "++env.config.a2_eval_door_handle_height_linspace=[0.80,1.10]" in winner_row["argv"]
    assert "++algo.config.num_mini_batches=1" in g7_row["argv"]
    assert "++env.config.a2_eval_door_handle_height_weight_pairs=[[1.10,120.0]]" in g7_row["argv"]
    assert not any("a2_eval_door_handle_height_linspace" in arg for arg in g7_row["argv"])
    for row in queue["rows"]:
        assert row["argv"][:3] == [sys.executable, "-m", "gr00t.rl.eval_agent_trl"]
        assert "--device" not in row["argv"]
        assert "++simulator.config.render_results=true" in row["argv"]
        assert "++algo.config.eval.a2_eval_m41_strict_telemetry=true" in row["argv"]
        assert row["env"]["CUDA_VISIBLE_DEVICES"] == "7"
        assert row["env"]["ACCELERATE_TORCH_DEVICE"] == "cuda:0"


@pytest.mark.parametrize(
    ("winner_group", "gpu"),
    (("G7", "7"), ("G0", "7"), ("G1", ""), ("G1", "-1"), ("G1", "07"), ("G1", "7.0")),
)
def test_rejects_invalid_winner_or_physical_gpu(tmp_path, winner_group, gpu):
    module = _load(SOURCE, f"v19_render_queue_invalid_{winner_group}_{repr(gpu)}")
    winner, g7 = _checkpoints(tmp_path)
    with pytest.raises(module.V19RenderQueueError):
        module.build_queue(winner_group, winner, g7, tmp_path / "render", gpu=gpu)


def test_rejects_non_numbered_or_shared_checkpoint(tmp_path):
    module = _load(SOURCE, "v19_render_queue_checkpoint_test")
    winner, g7 = _checkpoints(tmp_path)
    wrong = tmp_path / "last.pt"
    wrong.write_bytes(b"alias")
    with pytest.raises(module.V19RenderQueueError, match="numbered"):
        module.build_queue("G1", wrong, g7, tmp_path / "render")
    with pytest.raises(module.V19RenderQueueError, match="distinct"):
        module.build_queue("G1", winner, winner, tmp_path / "render")


def test_immutable_outputs_allow_exact_revalidation_and_reject_change(tmp_path):
    module = _load(SOURCE, "v19_render_queue_immutable_test")
    winner, g7 = _checkpoints(tmp_path)
    output = tmp_path / "render"
    queue = module.build_queue("G1", winner, g7, output)
    first = module.write_immutable_outputs(queue, output)
    second = module.write_immutable_outputs(queue, output)
    assert first == second
    changed = dict(queue)
    changed["physical_gpu"] = "6"
    with pytest.raises(module.V19RenderQueueError, match="differ"):
        module.write_immutable_outputs(changed, output)
