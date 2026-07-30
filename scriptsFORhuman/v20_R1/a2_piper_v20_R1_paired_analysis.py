"""Compute preregistered paired factor directions without metric imputation."""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Any, Mapping

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _r1_common import (  # noqa: E402
    PLAN_ID,
    R1Error,
    RUNTIME_SEMANTIC_PASS,
    exact_digest,
    write_json_no_overwrite,
)

SCHEMA = "a2_piper_v20_R1_paired_analysis_v3"
PAIRS = (
    ("G1", "G2", "E_without_S"),
    ("G1", "G3", "S_without_E"),
    ("G3", "G4", "incremental_E"),
    ("G3", "G5", "incremental_A_without_E"),
    ("G4", "G6", "incremental_A_under_SE"),
    ("G6", "G7", "seed_replication"),
)


def _finite(value: Any, name: str) -> float:
    if isinstance(value, Mapping) or isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise R1Error(f"paired metric {name} is missing/non-finite; no zero imputation")
    return float(value)


def _report_metrics(report: Mapping[str, Any], group: str) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    if report.get("plan_id") != PLAN_ID or report.get("status") != "STRICT_VALID":
        raise R1Error(f"paired report {group} is not STRICT_VALID and plan-bound")
    binding = report.get("binding")
    if not isinstance(binding, Mapping) or binding.get("group") != group:
        raise R1Error(f"paired report {group} lacks exact group binding")
    exact_digest(binding.get("checkpoint_sha256"), name=f"{group}.checkpoint_sha256", length=64)
    exact_digest(binding.get("config_sha256"), name=f"{group}.config_sha256", length=64)
    if not isinstance(binding.get("config"), str) or not binding["config"]:
        raise R1Error(f"paired report {group} lacks config binding")
    metrics = report.get("metrics") or report.get("aggregate")
    if not isinstance(metrics, Mapping):
        raise R1Error(f"paired report {group} has no metrics")
    return metrics, binding


def paired_analysis(
    reports: Mapping[str, Mapping[str, Any]],
    *,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    expected_groups = {group for pair in PAIRS for group in pair[:2]}
    if set(reports) != expected_groups:
        raise R1Error("paired R1 analysis requires exactly G1-G7 reports")
    rows = []
    for left, right, label in PAIRS:
        left_metrics, left_binding = _report_metrics(reports[left], left)
        right_metrics, right_binding = _report_metrics(reports[right], right)
        rows.append(
            {
                "left": left,
                "right": right,
                "label": label,
                "status": "COMPARABLE",
                "left_binding": dict(left_binding),
                "right_binding": dict(right_binding),
                "delta_arm_share_p50": _finite(
                    right_metrics.get("arm_tangent_share_p50"),
                    f"{right}.arm_tangent_share_p50",
                )
                - _finite(
                    left_metrics.get("arm_tangent_share_p50"),
                    f"{left}.arm_tangent_share_p50",
                ),
                "delta_crossing_hinge_p50": _finite(
                    right_metrics.get("hinge_at_first_crossing_p50"),
                    f"{right}.hinge_at_first_crossing_p50",
                )
                - _finite(
                    left_metrics.get("hinge_at_first_crossing_p50"),
                    f"{left}.hinge_at_first_crossing_p50",
                ),
            }
        )
    result = {
        "schema": SCHEMA,
        "plan_id": PLAN_ID,
        "status": RUNTIME_SEMANTIC_PASS,
        "pairs": rows,
        "zero_imputation": False,
    }
    if output_dir is not None:
        write_json_no_overwrite(output_dir / "paired_analysis.json", result)
    return result


def _require_blocked_r1_cli_opt_in() -> None:
    if "BASE_V20_ALLOW_BLOCKED_R1_EXECUTION" not in __import__("os").environ:
        print(
            "R1 execution is blocked by default; set BASE_V20_ALLOW_BLOCKED_R1_EXECUTION explicitly to run historical tooling",
            file=__import__("sys").stderr,
        )
        raise SystemExit(2)


if __name__ == "__main__":
    _require_blocked_r1_cli_opt_in()
    parser = argparse.ArgumentParser()
    parser.add_argument("reports", type=Path)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    import json

    paired_analysis(
        json.loads(args.reports.read_text(encoding="utf-8")),
        output_dir=args.output_dir,
    )
