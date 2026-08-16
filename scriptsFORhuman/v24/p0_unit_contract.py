"""Canonical mechanics-unit conversion for base-v24 P0.

All cross-artifact comparisons use the radian surface returned by this module.
USD angular-drive readbacks are explicitly marked as degree-surface values and
converted exactly once.  Mass and effort are pass-through quantities with
source authority retained in the normalized record.
"""

from __future__ import annotations

import math
from typing import Any, Mapping

from ._v24_common import V24Error, finite_number


CONTRACT_SCHEMA = "a2_piper_v24_door_mechanics_unit_contract_v1"
CONTRACT_NAME = "DoorMechanicsUnitContractV1"
CANONICAL_SURFACE = "RAD"
DEG_PER_RAD = 180.0 / math.pi
RAD_PER_DEG = math.pi / 180.0

TRACE_CONFIG_SURFACE = "TRACE_CONFIG_RAD"
USD_DEGREE_SURFACE = "USD_DEGREE_READBACK"
CANONICAL_SURFACE_LABEL = "CANONICAL_RAD"


def _angular(value: Any, *, field: str, surface: str, authority: str) -> dict[str, Any]:
    source = finite_number(value, label=field)
    if surface in {TRACE_CONFIG_SURFACE, CANONICAL_SURFACE_LABEL, CANONICAL_SURFACE}:
        canonical = source
        conversion = "identity_on_rad_surface"
    elif surface == USD_DEGREE_SURFACE:
        canonical = source * RAD_PER_DEG
        conversion = "usd_degree_surface_times_pi_over_180"
    else:
        raise V24Error(f"unsupported angular surface {surface!r} for {field}")
    return {
        "value_rad": canonical,
        "source_value": source,
        "source_surface": surface,
        "canonical_surface": CANONICAL_SURFACE,
        "conversion": conversion,
        "authority": authority,
    }


def _pass_through(value: Any, *, field: str, unit: str, authority: str) -> dict[str, Any]:
    return {
        "value": finite_number(value, label=field),
        "unit": unit,
        "source_field": field,
        "authority": authority,
        "conversion": "pass_through",
    }


def normalize_realized_dynamics(
    values: Mapping[str, Any],
    *,
    angular_surface: str,
    authority_prefix: str,
) -> dict[str, Any]:
    """Normalize one realized mechanics tuple to the canonical rad surface."""

    required = {
        "door_weight_kg",
        "hinge_damping_native",
        "hinge_stiffness_native",
        "hinge_effort_limit_nm",
    }
    if not isinstance(values, Mapping) or not required <= set(values):
        raise V24Error(f"realized dynamics lacks required fields: {sorted(required)}")
    damping = _angular(
        values["hinge_damping_native"],
        field="hinge_damping_native",
        surface=angular_surface,
        authority=f"{authority_prefix}:HINGE_DAMPING",
    )
    stiffness = _angular(
        values["hinge_stiffness_native"],
        field="hinge_stiffness_native",
        surface=angular_surface,
        authority=f"{authority_prefix}:HINGE_STIFFNESS",
    )
    effort = _pass_through(
        values["hinge_effort_limit_nm"],
        field="hinge_effort_limit_nm",
        unit="N*m",
        authority=f"{authority_prefix}:HINGE_EFFORT",
    )
    mass = _pass_through(
        values["door_weight_kg"],
        field="door_weight_kg",
        unit="kg",
        authority=f"{authority_prefix}:DOOR_MASS",
    )
    return {
        "canonical_surface": CANONICAL_SURFACE,
        "damping_rad": damping["value_rad"],
        "stiffness_rad": stiffness["value_rad"],
        "effort_limit_nm": effort["value"],
        "door_mass_kg": mass["value"],
        "fields": {
            "damping": damping,
            "stiffness": stiffness,
            "effort": effort,
            "mass": mass,
        },
    }


def mechanics_vector(normalized: Mapping[str, Any]) -> tuple[float, float, float, float]:
    required = ("damping_rad", "stiffness_rad", "effort_limit_nm", "door_mass_kg")
    values = [finite_number(normalized[key], label=key) for key in required]
    return (values[0], values[1], values[2], values[3])


def scaled_distance(
    observed: Mapping[str, Any],
    reference: Mapping[str, Any],
    *,
    scales: Mapping[str, float] | None = None,
) -> float:
    """Return a continuous dimensionless distance; never an exact tuple match."""

    names = ("damping_rad", "stiffness_rad", "effort_limit_nm", "door_mass_kg")
    default_scales = {
        "damping_rad": 50.0,
        "stiffness_rad": 30.0,
        "effort_limit_nm": 20.0,
        "door_mass_kg": 40.0,
    }
    scale_map = default_scales if scales is None else dict(scales)
    squared = 0.0
    for name in names:
        left = finite_number(observed[name], label=f"observed.{name}")
        right = finite_number(reference[name], label=f"reference.{name}")
        scale = finite_number(scale_map[name], label=f"scale.{name}")
        if scale <= 0.0:
            raise V24Error(f"distance scale must be positive: {name}")
        squared += ((left - right) / scale) ** 2
    return math.sqrt(squared)


def contract_metadata() -> dict[str, Any]:
    return {
        "schema": CONTRACT_SCHEMA,
        "name": CONTRACT_NAME,
        "canonical_surface": CANONICAL_SURFACE,
        "angular_unit": "rad",
        "degree_surface_conversion": "value_rad = usd_degree_value * pi / 180",
        "degree_per_rad": DEG_PER_RAD,
        "effort_unit": "N*m",
        "mass_unit": "kg",
        "effort_authority": "PASS_THROUGH_FROM_SOURCE_WITH_AUTHORITY",
        "mass_authority": "PASS_THROUGH_FROM_SOURCE_WITH_AUTHORITY",
        "comparison_rule": "CONTINUOUS_SCALED_DISTANCE_ONLY;NO_EXACT_TUPLE_EQUALITY",
    }


__all__ = [
    "CANONICAL_SURFACE",
    "CONTRACT_NAME",
    "CONTRACT_SCHEMA",
    "DEG_PER_RAD",
    "RAD_PER_DEG",
    "TRACE_CONFIG_SURFACE",
    "USD_DEGREE_SURFACE",
    "contract_metadata",
    "mechanics_vector",
    "normalize_realized_dynamics",
    "scaled_distance",
]
