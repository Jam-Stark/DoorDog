from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest
import torch


ROOT = Path(__file__).parents[3]
REDUCER_PATH = ROOT / "scriptsFORhuman/v26_8/v26_8_g1_reduce.py"
SPEC = importlib.util.spec_from_file_location("v26_8_g1_reduce", REDUCER_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
VALIDATE_TRACE = MODULE.validate_trace

REWARDS = {
    "reward_initial_penalty_scale": 1.0,
    "reward_min_penalty_scale": 0.2,
    "reward_max_penalty_scale": 1.0,
    "reward_penalty_degree": -0.0001,
}
ENV = {
    "a2_v26_8_penalty_driver_level_down_rate": 0.5,
    "a2_v26_8_penalty_driver_level_up_rate": 0.7,
}


def _rows() -> list[dict]:
    decayed = torch.tensor(1.0, dtype=torch.float32)
    decayed *= 0.9999
    return [
        {
            "update_index": 0,
            "common_step": 7,
            "scale_before": 1.0,
            "scale_after": 1.0,
            "driver_left": 0.0,
            "driver_right": None,
            "natural_sample_left": 1,
            "natural_sample_right": 0,
            "natural_reached_left": 0,
            "natural_reached_right": 0,
            "consumed": False,
            "skipped": True,
        },
        {
            "update_index": 1,
            "common_step": 19,
            "scale_before": 1.0,
            "scale_after": 1.0,
            "driver_left": 0.0,
            "driver_right": 0.0,
            "natural_sample_left": 1,
            "natural_sample_right": 1,
            "natural_reached_left": 0,
            "natural_reached_right": 0,
            "consumed": True,
            "skipped": False,
        },
        {
            "update_index": 2,
            "common_step": 31,
            "scale_before": 1.0,
            "scale_after": float(decayed.item()),
            "driver_left": 1.0,
            "driver_right": 1.0,
            "natural_sample_left": 1,
            "natural_sample_right": 1,
            "natural_reached_left": 1,
            "natural_reached_right": 1,
            "consumed": True,
            "skipped": False,
        },
    ]


def test_v26_8_g1_accepts_exact_frozen_scale_transitions():
    summary = VALIDATE_TRACE(_rows(), REWARDS, ENV)
    assert summary["rows"] == 3
    assert summary["consumed_rows"] == 2
    assert summary["skipped_rows"] == 1
    assert summary["scale_min"] == pytest.approx(0.9999)
    assert summary["scale_max"] == 1.0
    assert summary["final_scale"] == summary["scale_min"]
    assert summary["first_bilateral_consumption"] == {
        "update_index": 1,
        "common_step": 19,
    }
    assert summary["first_scale_change"] == {
        "update_index": 2,
        "common_step": 31,
        "scale_before": 1.0,
        "scale_after": summary["scale_min"],
    }
    assert summary["float_transition_check"] == "exact_torch_float32"


def test_v26_8_g1_rejects_a_stale_all_one_scale_claim():
    rows = copy.deepcopy(_rows())
    rows[-1]["scale_after"] = 1.0
    with pytest.raises(RuntimeError, match="scale transition"):
        VALIDATE_TRACE(rows, REWARDS, ENV)


def test_v26_8_g1_rejects_pending_evidence_loss_after_skip():
    rows = _rows()
    rows[1]["natural_sample_left"] = 0
    rows[1]["natural_reached_left"] = 0
    rows[1]["driver_left"] = None
    rows[1]["consumed"] = False
    rows[1]["skipped"] = True
    with pytest.raises(RuntimeError, match="discarded pending left evidence"):
        VALIDATE_TRACE(rows, REWARDS, ENV)
