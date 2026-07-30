"""Focused CPU contracts for the R2 Phase-I common helper."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from scriptsFORhuman.v20_R2 import _r2_common as common


def test_canonical_json_rejects_nonfinite_and_hash_is_deterministic():
    assert common.canonical_json({"z": 1, "a": [True, 2]}) == '{"a":[true,2],"z":1}'
    with pytest.raises(common.R2Error):
        common.canonical_json({"x": float("nan")})
    assert common.hash_command_env(["python", "-c", "pass"], {"B": "2", "A": "1"}) == common.hash_command_env(["python", "-c", "pass"], {"A": "1", "B": "2"})


def test_regular_path_rejects_symlink_and_escape(tmp_path: Path):
    source = tmp_path / "source.txt"
    source.write_text("source", encoding="utf-8")
    link = tmp_path / "link.txt"
    link.symlink_to(source)
    with pytest.raises(common.R2Error):
        common.validate_regular_file(link)
    with pytest.raises(common.R2Error):
        common.resolve_repo_path(tmp_path, "../outside.txt")


def test_exclusive_marker_is_fsyncd_readonly_and_non_overwriting(tmp_path: Path):
    target = tmp_path / "locks" / "marker.json"
    digest = common.write_json_exclusive(target, {"producer_state": "SOURCE_FROZEN"})
    assert digest == common.sha256_file(target)
    assert stat.S_IMODE(target.stat().st_mode) == 0o444
    with pytest.raises(common.R2Error):
        common.write_json_exclusive(target, {"producer_state": "SOURCE_FROZEN"})


def test_raw_status_bypass_and_device_contract():
    with pytest.raises(common.R2Error):
        common.validate_raw_producer_payload({"producer_state": "PROCESS_COMPLETED", "status": "PASS"})
    assert common.validate_device_contract(
        gpu=3,
        render=False,
        argv=["python", "train.py", "device=cuda:3"],
        env={"ACCELERATE_TORCH_DEVICE": "cuda:3"},
        app_launcher_device="cuda:3",
        accelerator_device="cuda:3",
    )["physical_gpu"] == 3
    assert common.validate_device_contract(
        gpu=3,
        render=True,
        argv=["python", "render.py", "device=cuda:0"],
        env={"CUDA_VISIBLE_DEVICES": "3", "ACCELERATE_TORCH_DEVICE": "cuda:0"},
        app_launcher_device="cuda:0",
        accelerator_device="cuda:0",
    )["logical_device"] == "cuda:0"
    for kwargs in (
        {"gpu": 7, "render": False, "argv": [], "env": {}},
        {"gpu": 3, "render": False, "argv": [], "env": {"CUDA_VISIBLE_DEVICES": "3", "ACCELERATE_TORCH_DEVICE": "cuda:3"}},
        {"gpu": 3, "render": True, "argv": [], "env": {"ACCELERATE_TORCH_DEVICE": "cuda:0"}},
        {"gpu": 3, "render": False, "argv": ["device=cuda:7"], "env": {"ACCELERATE_TORCH_DEVICE": "cuda:3"}},
    ):
        with pytest.raises(common.R2Error):
            common.validate_device_contract(**kwargs)
