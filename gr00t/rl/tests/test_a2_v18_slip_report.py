"""No-simulation tests for the strict v18 P1 slip reporter."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
REPORT_SOURCE = ROOT / "scriptsFORhuman/v18/a2_piper_v18_slip_report.py"


def _reporter():
    spec = importlib.util.spec_from_file_location("a2_piper_v18_slip_report_test", REPORT_SOURCE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _rows(seed: int = 0):
    rows = []
    for env_id in range(16):
        # stage2 -> stage3 -> stage4 -> stage5; the stage4->5 pair must count
        # toward the corridor sum even though the stage id changes.
        ys = (0.00, 0.01, 0.03, 0.05, 0.08)
        stages = (2, 3, 4, 4, 5)
        for step, (stage, y) in enumerate(zip(stages, ys)):
            rows.append(
                {
                    "seed": seed,
                    "env_id": env_id,
                    "episode_index": 0,
                    "first_episode_active": True,
                    "stage_buf": stage,
                    "step_index": step,
                    "episode_length_buf": step + 1,
                    "control_dt": 0.02,
                    "target_pos_source_handle": [0.0, y, 0.0],
                    "both_contact": True,
                    "terminal_reasons": "complete" if step == len(stages) - 1 else "unknown_reset",
                }
            )
    return rows


def _write_trace(tmp_path: Path, rows, seed: int = 0) -> Path:
    directory = tmp_path / f"seed{seed}_trace"
    directory.mkdir(parents=True)
    path = directory / "stage2_5_step_trace.json"
    path.write_text(json.dumps(rows), encoding="utf-8")
    return directory


def test_stage4_to_stage5_corridor_pair_is_accumulated_and_outputs_are_written(tmp_path):
    module = _reporter()
    directory = _write_trace(tmp_path, _rows())
    records = module.load_trace(directory, expected_seed=0)
    # One stage3 row has no within-opening pair; corridor stages4/5: .02 + .03m = 5cm.
    assert records[0]["opening_slip_cm"] == pytest.approx(0.0)
    assert records[0]["corridor_slip_cm"] == pytest.approx(5.0)
    report = module.build_report({0: list(records.values())})
    assert report["pooled"]["opening_stage3"]["p50_cm"] == pytest.approx(0.0)
    assert report["pooled"]["corridor_stages4_5"]["p95_cm"] == pytest.approx(5.0)
    paths = module.write_outputs(report, tmp_path / "out" / "slip")
    assert all(path.is_file() for path in paths)
    assert json.loads(paths[0].read_text(encoding="utf-8"))["schema"] == module.SCHEMA


@pytest.mark.parametrize("mutation", ("missing", "duplicate", "nonfinite", "terminal"))
def test_topology_and_finite_evidence_fail_fast(tmp_path, mutation):
    module = _reporter()
    rows = _rows()
    env0 = [row for row in rows if row["env_id"] == 0]
    if mutation == "missing":
        env0.pop(2)
    elif mutation == "duplicate":
        env0.insert(2, dict(env0[1]))
    elif mutation == "nonfinite":
        env0[1]["target_pos_source_handle"][1] = float("nan")
    else:
        env0[-1]["terminal_reasons"] = "unknown_reset"
    other = [row for row in rows if row["env_id"] != 0]
    directory = _write_trace(tmp_path, env0 + other)
    with pytest.raises(module.SlipReportError):
        module.load_trace(directory, expected_seed=0)


def test_duplicate_seed_provenance_fails_fast(tmp_path):
    module = _reporter()
    first = _write_trace(tmp_path / "a", _rows(), seed=0)
    second = _write_trace(tmp_path / "b", _rows(), seed=0)
    with pytest.raises(module.SlipReportError, match="duplicate seed"):
        module.main(
            [
                "--trace-dir",
                str(first),
                str(second),
                "--output-prefix",
                str(tmp_path / "out"),
            ]
        )
