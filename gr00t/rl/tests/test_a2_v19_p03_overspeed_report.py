"""Synthetic CPU tests for strict v19 P0.3 overspeed diagnosis."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "scriptsFORhuman/v19/a2_piper_v19_p03_overspeed_report.py"


def _reporter():
    spec = importlib.util.spec_from_file_location("v19_p03_test", SOURCE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _row(env_id: int, *, names=None):
    return {
        "env_id": env_id,
        "stage_buf": 2 + (env_id % 2),
        "terminal_reasons": "upper_dof_overspeed",
        "arm_joint_names": names or [f"arm_j{index}" for index in range(1, 7)],
        "arm_joint_vel": [0.1, -0.2, 0.3, 0.4, 0.5, 3.0001 + env_id * 0.0001],
    }


def test_p03_reports_four_j6_terminal_rows_and_selects_f2(tmp_path):
    module = _reporter()
    path = tmp_path / "endpoint_seed0.json"
    path.write_text(json.dumps([_row(env_id) for env_id in range(4)]), encoding="utf-8")
    report = module.build_report([path])
    assert report["terminal_row_count"] == 4
    assert report["f2_selection"] == "F2"
    assert report["overspeed_dof_counts"]["arm_j6"] == 4
    paths = module.write_outputs(report, tmp_path / "out")
    assert all(path.exists() for path in paths)


def test_p03_wrong_arm_names_and_malformed_terminal_evidence_fail(tmp_path):
    module = _reporter()
    wrong = tmp_path / "wrong.json"
    wrong.write_text(json.dumps([_row(0, names=["arm_j1", "arm_j2", "arm_j3", "arm_j4", "arm_j5", "j6"])]), encoding="utf-8")
    with pytest.raises(module.P03ReportError, match="exact arm names"):
        module.build_report([wrong])
    malformed = tmp_path / "malformed.json"
    row = _row(0)
    row.pop("arm_joint_vel")
    malformed.write_text(json.dumps([row]), encoding="utf-8")
    with pytest.raises(module.P03ReportError, match="arm_joint_vel"):
        module.build_report([malformed])


def test_p03_nonterminal_rows_do_not_hide_missing_terminal_evidence(tmp_path):
    module = _reporter()
    path = tmp_path / "none.json"
    row = _row(0)
    row["terminal_reasons"] = "complete"
    path.write_text(json.dumps([row]), encoding="utf-8")
    with pytest.raises(module.P03ReportError, match="no upper_dof_overspeed"):
        module.build_report([path])
