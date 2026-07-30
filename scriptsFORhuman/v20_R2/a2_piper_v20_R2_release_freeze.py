"""Deterministic simplest-passing-group release freeze consumer."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from ._r2_common import R2Error, canonical_json
from ._r2_workflow import GROUPS, artifact_hash, read_artifact, write_adjudication


def freeze_release(*, pooled: Path, source_lock_sha256: str | None = None) -> dict[str, object]:
    payload = read_artifact(pooled, schema="a2_piper_base_v20_R2_endpoint_report_v1", adjudicator_state="POOLED7_PASS")
    pooled_source = payload.get("source_lock_sha256")
    source_hash = source_lock_sha256 or pooled_source
    if source_hash != pooled_source:
        raise R2Error("release freeze source-lock hash mismatch")
    reports = payload.get("metrics", {}).get("groups", {})
    if not isinstance(reports, dict) or set(reports) != set(GROUPS):
        raise R2Error("pooled report must contain exact G1-G7 group metrics")
    eligible = {group: reports[group].get("eligible") is True for group in GROUPS}
    selected: str | None = None
    if eligible["G1"]:
        selected = "G1"
    elif eligible["G2"]:
        selected = "G2"
    elif eligible["G3"]:
        selected = "G3"
    elif eligible["G4"]:
        selected = "G4"
    elif eligible["G5"]:
        selected = "G5"
    elif eligible["G6"] and eligible["G7"]:
        # Replicated full-method pair only; choose lower pooled median time,
        # then earlier checkpoint step, then G6.
        def key(group: str) -> tuple[float, int, int]:
            report = reports[group]
            median = report.get("median_task_time")
            if not isinstance(median, (int, float)):
                median = float("inf")
            return (float(median), int(report.get("selected_checkpoint_step", 10**9)), 0 if group == "G6" else 1)
        selected = min(("G6", "G7"), key=key)
    state = "POLICY_PASS" if selected is not None else "NO_RELEASE"
    selected_report = reports[selected] if selected else None
    return {"schema": "a2_piper_base_v20_R2_release_freeze_v1", "adjudicator_state": state,
            "source_lock_sha256": source_hash, "selected_group": selected,
            "selected_checkpoint_step": selected_report.get("selected_checkpoint_step") if selected_report else None,
            "selected_checkpoint_path": selected_report.get("selected_checkpoint_path") if selected_report else None,
            "selected_config_path": selected_report.get("selected_config_path") if selected_report else None,
            "selected_checkpoint_sha256": selected_report.get("selected_checkpoint_sha256") if selected_report else None,
            "selection_basis": "simplest_passing_group" if selected else "no_group_passed",
            "pooled_sha256": artifact_hash(pooled), "holdout_allowed": selected is not None,
            "eligible_groups": [group for group in GROUPS if eligible[group]],
            "failed_gates": {group: reports[group].get("gates", {}) for group in GROUPS if not eligible[group]}}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pooled", type=Path, required=True); parser.add_argument("--source-lock-sha256")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = freeze_release(pooled=args.pooled, source_lock_sha256=args.source_lock_sha256)
    write_adjudication(args.output, result, result["adjudicator_state"])
    print(canonical_json(result)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
