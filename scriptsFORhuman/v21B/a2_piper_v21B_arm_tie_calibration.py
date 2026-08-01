"""Offline, pre-registered arm-tie multiplier calibration."""

from __future__ import annotations

import argparse
import math
from typing import Any, Mapping, Sequence

from ._v21b_common import V21BError
from .a2_piper_v21B_schemas import artifact_payload, schema, validate_artifact


MULTIPLIERS = (1, 2, 4, 8, 12, 16, 24)
ARM_TO_ARC_RATIO = (3.5, 0.85)


def calibrate_arm_tie(rows: Sequence[Mapping[str, Any]], *, multipliers: Sequence[int] = MULTIPLIERS, source_checkpoint_sha256: str | None = None, source_lock_sha256: str | None = None, source_config_sha256: str | None = None) -> dict[str, Any]:
    if not rows:
        raise V21BError("arm-tie calibration requires one fixed telemetry-complete evaluation")
    values: list[tuple[float, float, float]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise V21BError("arm-tie calibration rows must be mappings")
        fields = tuple(row.get(key) for key in ("raw_arm_tangent", "raw_arc_tracking", "positive_income"))
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) for value in fields):
            raise V21BError("arm-tie calibration rows require finite raw components and positive income")
        if float(fields[2]) < 0.0:
            raise V21BError("arm-tie calibration positive_income cannot be negative")
        values.append(tuple(float(value) for value in fields))
    grid = tuple(int(value) for value in multipliers)
    if grid != tuple(sorted(set(grid))) or any(value <= 0 or value > 24 for value in grid):
        raise V21BError("arm-tie multiplier grid must be sorted, unique, positive, and <=24")
    sweep = []
    for multiplier in grid:
        shares = []
        for raw_arm, raw_arc, positive_income in values:
            if positive_income <= 0.0:
                continue
            weighted = multiplier * (ARM_TO_ARC_RATIO[0] * raw_arm + ARM_TO_ARC_RATIO[1] * raw_arc)
            shares.append(weighted / positive_income)
        if not shares:
            share = None
            engaged_fraction = None
            satisfies = False
        else:
            share = sum(shares) / len(shares)
            engaged_fraction = sum(value > 0.0 for value in shares) / len(shares)
            satisfies = 0.05 <= share <= 0.15
        sweep.append({"multiplier": multiplier, "mean_positive_income_share": share, "engaged_fraction": engaged_fraction, "satisfies": satisfies})
    selected = next((row["multiplier"] for row in sweep if row["satisfies"]), None)
    status = "CALIBRATION_PASS" if selected is not None else "CALIBRATION_DEFERRED"
    fields = {key: value for key, value in (("source_checkpoint_sha256", source_checkpoint_sha256), ("source_lock_sha256", source_lock_sha256), ("source_config_sha256", source_config_sha256)) if value is not None}
    payload = artifact_payload(
        "arm_tie", status=status,
        selection_algorithm="choose smallest preregistered multiplier with mean positive-income share in [0.05,0.15]; no zero imputation",
        ratio={"arm_tangent": ARM_TO_ARC_RATIO[0], "arc_tracking": ARM_TO_ARC_RATIO[1]},
        multipliers=list(grid), sweep=sweep, selected_multiplier=selected,
        fallback_b7_arm_tie=(selected is None),
        **fields,
    )
    return validate_artifact(payload, expected_schema=schema("arm_tie"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", required=True)
    args = parser.parse_args(argv)
    import json
    rows = json.loads(open(args.rows, encoding="utf-8").read())
    print(json.dumps(calibrate_arm_tie(rows), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["MULTIPLIERS", "ARM_TO_ARC_RATIO", "calibrate_arm_tie"]
