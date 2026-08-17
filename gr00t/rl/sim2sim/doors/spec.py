"""DoorInstanceSpec v1 and the v24 canonical mechanics-unit contract."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


TRACE_CONFIG_RAD = "TRACE_CONFIG_RAD"
USD_DEGREE_READBACK = "USD_DEGREE_READBACK"
CANONICAL_RAD = "RAD"


def _finite(value: Any, name: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


class DoorMechanicsUnitContractV1:
    """Normalize requested and USD-readback mechanics to the canonical rad face."""

    schema = "a2_piper_v24_door_mechanics_unit_contract_v1"
    name = "DoorMechanicsUnitContractV1"
    canonical_surface = CANONICAL_RAD

    @classmethod
    def normalize(
        cls,
        values: Mapping[str, Any],
        *,
        angular_surface: str,
        authority: str,
    ) -> dict[str, Any]:
        required = {
            "door_weight_kg",
            "hinge_damping_native",
            "hinge_stiffness_native",
            "hinge_effort_limit_nm",
        }
        if required - set(values):
            raise ValueError(f"mechanics face lacks {sorted(required - set(values))}")
        if angular_surface == TRACE_CONFIG_RAD:
            multiplier = 1.0
            conversion = "identity_on_rad_surface"
        elif angular_surface == USD_DEGREE_READBACK:
            multiplier = math.pi / 180.0
            conversion = "usd_degree_surface_times_pi_over_180"
        else:
            raise ValueError(f"unsupported angular surface {angular_surface!r}")
        damping_source = _finite(values["hinge_damping_native"], "hinge_damping_native")
        stiffness_source = _finite(values["hinge_stiffness_native"], "hinge_stiffness_native")
        normalized = {
            "canonical_surface": cls.canonical_surface,
            "damping_rad": damping_source * multiplier,
            "stiffness_rad": stiffness_source * multiplier,
            "effort_limit_nm": _finite(values["hinge_effort_limit_nm"], "hinge_effort_limit_nm"),
            "door_mass_kg": _finite(values["door_weight_kg"], "door_weight_kg"),
        }
        normalized["fields"] = {
            "damping": {
                "source_value": damping_source,
                "source_surface": angular_surface,
                "value_rad": normalized["damping_rad"],
                "conversion": conversion,
                "authority": f"{authority}:HINGE_DAMPING",
            },
            "stiffness": {
                "source_value": stiffness_source,
                "source_surface": angular_surface,
                "value_rad": normalized["stiffness_rad"],
                "conversion": conversion,
                "authority": f"{authority}:HINGE_STIFFNESS",
            },
            "effort": {
                "value": normalized["effort_limit_nm"],
                "unit": "N*m",
                "conversion": "pass_through",
                "authority": f"{authority}:HINGE_EFFORT",
            },
            "mass": {
                "value": normalized["door_mass_kg"],
                "unit": "kg",
                "conversion": "pass_through",
                "authority": f"{authority}:DOOR_MASS",
            },
        }
        return normalized

    @classmethod
    def receipt(
        cls,
        requested: Mapping[str, Any],
        usd_readback: Mapping[str, Any],
    ) -> dict[str, Any]:
        requested_normalized = cls.normalize(
            requested,
            angular_surface=TRACE_CONFIG_RAD,
            authority="TRACE_CONFIG",
        )
        realized_normalized = cls.normalize(
            usd_readback,
            angular_surface=USD_DEGREE_READBACK,
            authority="USD_READBACK",
        )
        return {
            "unit_contract": cls.name,
            "unit_contract_schema": cls.schema,
            "canonical_surface": cls.canonical_surface,
            "requested_angular_surface": TRACE_CONFIG_RAD,
            "realized_angular_surface": USD_DEGREE_READBACK,
            "requested": dict(requested),
            "usd_readback": dict(usd_readback),
            "requested_normalized": requested_normalized,
            "realized_normalized": realized_normalized,
            "conversion_metadata": realized_normalized["fields"],
            "degree_per_rad": 180.0 / math.pi,
        }


@dataclass(frozen=True)
class DoorInstanceSpec:
    """One materialized door instance shared by Isaac and MuJoCo builders."""

    payload: Mapping[str, Any]

    @classmethod
    def from_path(cls, path: str | Path) -> "DoorInstanceSpec":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def validate(self) -> None:
        if self.payload.get("schema_version") != "doordog.door_instance.v1":
            raise ValueError("schema_version must be doordog.door_instance.v1")
        for section in ("identity", "geometry", "kinematics", "dynamics", "contact", "named_sites"):
            if section not in self.payload:
                raise ValueError(f"DoorInstanceSpec lacks {section}")
        geometry = self.payload["geometry"]
        for field in ("panel_width_m", "panel_height_m", "panel_thickness_m", "frame_width_m"):
            if _finite(geometry[field], f"geometry.{field}") <= 0.0:
                raise ValueError(f"geometry.{field} must be positive")
        hinge = self.payload["dynamics"]["hinge"]
        for field in (
            "equilibrium_rad",
            "stiffness_nm_per_rad",
            "damping_nms_per_rad",
            "effort_cap_nm",
            "static_friction_effort",
            "dynamic_friction_effort",
            "viscous_friction_coefficient",
        ):
            _finite(hinge[field], f"dynamics.hinge.{field}")
        if hinge["static_friction_effort"] < hinge["dynamic_friction_effort"]:
            raise ValueError("static_friction_effort must be >= dynamic_friction_effort")
        if self.payload["kinematics"]["latch_mode"] not in {
            "no_latch",
            "constraint_gate",
            "physical_collision",
        }:
            raise ValueError("unsupported latch_mode")

    @property
    def hinge(self) -> Mapping[str, Any]:
        return self.payload["dynamics"]["hinge"]

    @property
    def friction_classification(self) -> str:
        static = _finite(self.hinge["static_friction_effort"], "static friction")
        dynamic = _finite(self.hinge["dynamic_friction_effort"], "dynamic friction")
        return "FRICTION_SEMANTIC_GAP" if static != dynamic else "FRICTION_SEMANTICS_ALIGNED"

    def mechanics_receipt(self) -> dict[str, Any]:
        mechanics = self.payload["backend_overrides"]["isaac_physx"]["mechanics_faces"]
        return DoorMechanicsUnitContractV1.receipt(
            mechanics["requested_trace_config_rad"],
            mechanics["usd_degree_readback"],
        )
