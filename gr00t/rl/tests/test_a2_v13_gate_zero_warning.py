import importlib.util
import json
from pathlib import Path

import pytest


SCRIPT_PATH = (
    Path(__file__).parents[3]
    / "scriptsFORhuman"
    / "a2_piper_v13_gate_zero_warning.py"
)
SPEC = importlib.util.spec_from_file_location("a2_piper_v13_gate_zero_warning", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
WARNING_MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(WARNING_MODULE)


def _write_records(path: Path, values: list[float]) -> Path:
    path.mkdir()
    metrics_path = path / "eval_to_log_metrics.json"
    metrics_path.write_text(
        json.dumps(
            [
                {
                    "gate_a": value,
                    "gate_b": 0.5,
                }
                for value in values
            ]
        ),
        encoding="utf-8",
    )
    return path


def test_v13_gate_warning_loads_maxima_and_finds_exact_zero_runs(tmp_path):
    checkpoint_paths = [
        _write_records(tmp_path / "step_0250", [0.0, 0.0]),
        _write_records(tmp_path / "step_0500", [0.0]),
        _write_records(tmp_path / "step_0750", [0.0, 0.0]),
        _write_records(tmp_path / "step_1000", [0.0, 0.25]),
    ]
    checkpoint_metrics = [
        (path, WARNING_MODULE.load_metric_maxima(path, ("gate_a", "gate_b")))
        for path in checkpoint_paths
    ]

    assert checkpoint_metrics[0][1] == {"gate_a": 0.0, "gate_b": 0.5}
    assert checkpoint_metrics[-1][1] == {"gate_a": 0.25, "gate_b": 0.5}
    assert WARNING_MODULE.find_exact_zero_runs(
        checkpoint_metrics,
        "gate_a",
        3,
    ) == [checkpoint_paths[:3]]


def test_v13_gate_warning_fails_fast_on_missing_or_invalid_metrics(tmp_path):
    missing = tmp_path / "missing.json"
    missing.write_text('[{"other": 0.0}]', encoding="utf-8")
    with pytest.raises(KeyError, match="missing metric"):
        WARNING_MODULE.load_metric_maxima(missing, ("gate",))

    invalid = tmp_path / "invalid.json"
    invalid.write_text('[{"gate": 1.1}]', encoding="utf-8")
    with pytest.raises(ValueError, match=r"finite in \[0, 1\]"):
        WARNING_MODULE.load_metric_maxima(invalid, ("gate",))

    with pytest.raises(ValueError, match="consecutive must be positive"):
        WARNING_MODULE.find_exact_zero_runs([], "gate", 0)
