"""Ordered-row paired trace comparison following the v24 P0 harness contract."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def compare_ordered_rows(
    reference: Sequence[Mapping[str, Any]],
    candidate: Sequence[Mapping[str, Any]],
    *,
    float_fields: Sequence[str],
    discrete_fields: Sequence[str],
    atol: float,
) -> dict[str, Any]:
    if len(reference) != len(candidate):
        raise ValueError(f"paired trace row counts differ: {len(reference)} vs {len(candidate)}")
    field_max = {field: 0.0 for field in float_fields}
    for row_index, (expected, actual) in enumerate(zip(reference, candidate, strict=True)):
        for field in discrete_fields:
            if expected[field] != actual[field]:
                raise AssertionError(
                    f"paired discrete mismatch row={row_index} field={field}: "
                    f"{expected[field]!r} != {actual[field]!r}"
                )
        for field in float_fields:
            difference = abs(float(expected[field]) - float(actual[field]))
            field_max[field] = max(field_max[field], difference)
            if difference > atol:
                raise AssertionError(
                    f"paired float mismatch row={row_index} field={field}: diff={difference} > {atol}"
                )
    return {
        "status": "PASS",
        "compared_rows": len(reference),
        "atol": atol,
        "float_fields": list(float_fields),
        "discrete_fields": list(discrete_fields),
        "field_max_abs_diff": field_max,
        "max_abs_diff": max(field_max.values(), default=0.0),
    }
