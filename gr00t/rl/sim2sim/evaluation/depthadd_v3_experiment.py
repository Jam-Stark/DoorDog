"""DepthADD v3 MuJoCo randomized-experiment materialization.

The handoff YAML is the experiment authority.  This module turns it into
independent, JSON-serializable episode rows; it deliberately does not run a
policy or construct MuJoCo models.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import yaml


PRIMARY_LANES = ("fixed", "visual_only", "door_only", "combined")
VISUAL_STREAMS = ("surface_material", "lighting", "camera", "rgb_noise", "depth_noise")
DOOR_STREAMS = ("door_geometry", "door_dynamics_cell")
SEED_STREAMS = (
    "initial_state",
    "command",
    "door_geometry",
    "door_dynamics_cell",
    "surface_material",
    "lighting",
    "camera",
    "rgb_noise",
    "depth_noise",
)
_STREAM_INDEX = {name: index + 1 for index, name in enumerate(SEED_STREAMS)}
_UINT32_PERIOD = 2**32 - 1


@dataclass(frozen=True)
class DepthAddV3ExperimentSpec:
    """Validated handoff experiment specification."""

    source_path: Path
    document: dict[str, Any]

    @property
    def formal_design(self) -> Mapping[str, Any]:
        return self.document["formal_design"]


def _require_mapping(value: object, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{path} must be a mapping, got {type(value).__name__}")
    return value


def _require_sequence(value: object, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise TypeError(f"{path} must be a list, got {type(value).__name__}")
    return value


def load_depthadd_v3_experiment(path: Path) -> DepthAddV3ExperimentSpec:
    """Parse and validate the machine-readable DepthADD v3 handoff YAML."""
    source_path = path.resolve(strict=True)
    document = yaml.safe_load(source_path.read_text(encoding="utf-8"))
    root = _require_mapping(document, "experiment")
    if root.get("schema") != "a2_depthadd_v3_mujoco_randomized_experiment_v1":
        raise ValueError(f"unsupported DepthADD v3 schema: {root.get('schema')!r}")
    formal = _require_mapping(root.get("formal_design"), "formal_design")
    lanes = tuple(_require_sequence(formal.get("lanes"), "formal_design.lanes"))
    if lanes != PRIMARY_LANES:
        raise ValueError(f"primary lanes must be {PRIMARY_LANES}, got {lanes}")
    if int(formal.get("base_cases_per_seed")) != 128:
        raise ValueError("DepthADD v3 primary design requires 128 base cases per seed")
    seeds = _require_sequence(formal.get("seeds"), "formal_design.seeds")
    if len(seeds) != 3 or any(not isinstance(seed, int) for seed in seeds):
        raise ValueError("DepthADD v3 primary design requires exactly three integer seeds")
    expected_total = 128 * len(seeds) * len(PRIMARY_LANES)
    if int(formal.get("total_primary_episodes")) != expected_total:
        raise ValueError(
            "formal_design.total_primary_episodes does not match base cases, seeds, and lanes"
        )
    cells = _require_mapping(root.get("door_dynamics_cells"), "door_dynamics_cells")
    primary_cells = tuple(_require_sequence(cells.get("narrowed_primary_cells"), "door_dynamics_cells.narrowed_primary_cells"))
    if primary_cells != ("A0", "A1", "A4", "A6"):
        raise ValueError(f"DepthADD v3 primary cells must be A0/A1/A4/A6, got {primary_cells}")
    all_cells = _require_mapping(cells.get("cells"), "door_dynamics_cells.cells")
    if any(cell not in all_cells for cell in primary_cells):
        raise ValueError("primary D1 cells are absent from door_dynamics_cells.cells")
    stress = _require_mapping(root.get("stress_suite"), "stress_suite")
    profiles = _require_sequence(stress.get("matched_profiles"), "stress_suite.matched_profiles")
    if len(profiles) != 4 or int(stress.get("repetitions_per_profile")) != 32:
        raise ValueError("DepthADD v3 stress suite requires four profiles with 32 repetitions each")
    return DepthAddV3ExperimentSpec(source_path=source_path, document=dict(root))


def stream_seed(experiment_seed: int, base_case_index: int, stream: str) -> int:
    """Return a stable, stream-separated uint32 seed without shared RNG state."""
    if stream not in _STREAM_INDEX:
        raise KeyError(f"unknown DepthADD v3 seed stream {stream!r}")
    if base_case_index < 0:
        raise ValueError("base_case_index must be non-negative")
    return int(
        (int(experiment_seed) * 1_000_003 + base_case_index * 9_176 + _STREAM_INDEX[stream] * 104_729)
        % _UINT32_PERIOD
    )


def _seed_streams(experiment_seed: int, base_case_index: int) -> dict[str, int]:
    return {
        stream: stream_seed(experiment_seed, base_case_index, stream)
        for stream in SEED_STREAMS
    }


def _uniform(rng: np.random.Generator, interval: object, field: str) -> float:
    values = _require_sequence(interval, field)
    if len(values) != 2:
        raise ValueError(f"{field} must have exactly two endpoints")
    low, high = (float(value) for value in values)
    if low > high:
        raise ValueError(f"{field} is inverted: {low} > {high}")
    return float(rng.uniform(low, high))


def _sample_narrowed_geometry(spec: DepthAddV3ExperimentSpec, seed: int) -> dict[str, Any]:
    geometry = _require_mapping(spec.document["narrowed_door_geometry"], "narrowed_door_geometry")
    rng = np.random.default_rng(seed)
    result: dict[str, Any] = {}
    for field, interval in geometry.items():
        if field in {"hook_probability", "keyhole_probability", "handle_type", "hinge_side", "opening_direction"}:
            continue
        result[field] = _uniform(rng, interval, f"narrowed_door_geometry.{field}")
    result["hook_enabled"] = bool(rng.random() < float(geometry["hook_probability"]))
    result["keyhole_enabled"] = bool(rng.random() < float(geometry["keyhole_probability"]))
    result["handle_type"] = _require_sequence(geometry["handle_type"], "narrowed_door_geometry.handle_type")[0]
    result["hinge_side"] = _require_sequence(geometry["hinge_side"], "narrowed_door_geometry.hinge_side")[0]
    result["opening_direction"] = _require_sequence(geometry["opening_direction"], "narrowed_door_geometry.opening_direction")[0]
    return result


def _sample_primary_cell(spec: DepthAddV3ExperimentSpec, seed: int) -> tuple[str, dict[str, Any]]:
    cells = _require_mapping(spec.document["door_dynamics_cells"], "door_dynamics_cells")
    primary = _require_sequence(cells["narrowed_primary_cells"], "door_dynamics_cells.narrowed_primary_cells")
    chosen = str(primary[int(np.random.default_rng(seed).integers(len(primary)))])
    values = _require_mapping(cells["cells"], "door_dynamics_cells.cells")[chosen]
    return chosen, dict(_require_mapping(values, f"door_dynamics_cells.cells.{chosen}"))


def _nominal_door(spec: DepthAddV3ExperimentSpec) -> dict[str, Any]:
    return dict(_require_mapping(spec.document["nominal_door"], "nominal_door"))


def _realized_visual(
    spec: DepthAddV3ExperimentSpec,
    streams: Mapping[str, int],
    enabled: bool,
    stress_overrides: Mapping[str, Any] | None = None,
    *,
    regime: str,
) -> dict[str, Any]:
    visual_streams = {name: int(streams[name]) for name in VISUAL_STREAMS}
    if not enabled:
        return {
            "mode": "nominal",
            "regime": regime,
            "seed_streams": visual_streams,
            "receipt_requirement": "record actual MuJoCo texture/rgba/specular/shininess/reflectance/texrepeat at episode realization",
        }
    # Keep the experiment package independent from MuJoCo at import time.  The
    # visual sampler is imported only when the runner materializes randomized rows.
    from gr00t.rl.sim2sim.mujoco.depthadd_visual import (
        apply_stress_visual_overrides,
        sample_visual_realization,
    )

    realization = sample_visual_realization(
        _require_mapping(spec.document["narrowed_visual_randomization"], "narrowed_visual_randomization"),
        visual_streams,
        regime=regime,
    )
    if stress_overrides is not None:
        realization = apply_stress_visual_overrides(realization, stress_overrides)

    return {
        "mode": "narrowed_random",
        "regime": regime,
        "seed_streams": visual_streams,
        "realization": realization,
    }


def _common_case(spec: DepthAddV3ExperimentSpec, experiment_seed: int, base_case_index: int) -> dict[str, Any]:
    streams = _seed_streams(experiment_seed, base_case_index)
    cell_name, cell = _sample_primary_cell(spec, streams["door_dynamics_cell"])
    return {
        "experiment_seed": experiment_seed,
        "base_case_index": base_case_index,
        "base_case_id": f"seed{experiment_seed}_base{base_case_index:03d}",
        "seed_streams": streams,
        "common_across_lanes": {
            "initial_state_seed": streams["initial_state"],
            "command_seed": streams["command"],
            "policy_hidden_reset": "RESET_ZERO",
            "episode_horizon_s": 20.0,
        },
        "sampled_door": {
            "geometry": _sample_narrowed_geometry(spec, streams["door_geometry"]),
            "dynamics_cell": cell_name,
            "dynamics": cell,
        },
    }


def materialize_primary_cases(spec: DepthAddV3ExperimentSpec) -> list[dict[str, Any]]:
    """Materialize the exact 128 base × 3 seed × 4 lane primary design."""
    formal = spec.formal_design
    rows: list[dict[str, Any]] = []
    for experiment_seed in _require_sequence(formal["seeds"], "formal_design.seeds"):
        for base_case_index in range(int(formal["base_cases_per_seed"])):
            common = _common_case(spec, int(experiment_seed), base_case_index)
            for lane in PRIMARY_LANES:
                uses_visual = lane in {"visual_only", "combined"}
                uses_door = lane in {"door_only", "combined"}
                realized_door = common["sampled_door"] if uses_door else {
                    "geometry": _nominal_door(spec),
                    "dynamics_cell": "A0",
                    "dynamics": dict(spec.document["door_dynamics_cells"]["cells"]["A0"]),
                }
                row = {
                        "suite": "primary",
                        "episode_id": f"{common['base_case_id']}__{lane}",
                        "lane": lane,
                        **common,
                        "active_randomizations": {
                            "visual": uses_visual,
                            "door_geometry": uses_door,
                            "door_dynamics_cell": uses_door,
                        },
                        "realized_door": realized_door,
                        "realized_visual_seed_streams": {
                            name: common["seed_streams"][name] for name in VISUAL_STREAMS
                        },
                        "realized_visual": _realized_visual(
                            spec,
                            common["seed_streams"],
                            uses_visual,
                            regime="primary_training_equivalent",
                        ),
                    }
                row["case_id"] = row["episode_id"]
                row["door_geometry"] = realized_door["geometry"]
                row["door_dynamics_cell_id"] = realized_door["dynamics_cell"]
                row["door_dynamics_cell"] = realized_door["dynamics"]
                rows.append(row)
    if len(rows) != int(formal["total_primary_episodes"]):
        raise RuntimeError(f"materialized {len(rows)} primary rows, expected {formal['total_primary_episodes']}")
    return rows


def _stress_door(spec: DepthAddV3ExperimentSpec, profile: str, seed: int) -> dict[str, Any]:
    nominal = _nominal_door(spec)
    cells = spec.document["door_dynamics_cells"]["cells"]
    if profile == "only_dark_material_and_light":
        return {"geometry": nominal, "dynamics_cell": "A0", "dynamics": dict(cells["A0"])}
    if profile == "only_heavy_low_handle_mechanics":
        geometry = dict(nominal)
        geometry.update({"panel_mass_kg": 160.0, "handle_height_m": 0.85, "handle_edge_offset_m": 0.15})
        return {"geometry": geometry, "dynamics_cell": "A8", "dynamics": dict(cells["A8"])}
    if profile == "full_dark_heavy_low_handle":
        geometry = dict(nominal)
        geometry.update({"width_m": 1.1, "height_m": 2.2, "panel_mass_kg": 160.0, "handle_height_m": 0.85, "handle_edge_offset_m": 0.15})
        return {"geometry": geometry, "dynamics_cell": "A8", "dynamics": dict(cells["A8"])}
    if profile == "bright_light_high_handle":
        geometry = dict(nominal)
        geometry.update({"width_m": 0.85, "height_m": 1.95, "panel_mass_kg": 90.0, "handle_height_m": 0.925, "handle_edge_offset_m": 0.09})
        return {"geometry": geometry, "dynamics_cell": "A5", "dynamics": dict(cells["A5"])}
    raise ValueError(f"unsupported stress profile {profile!r}")


def _stress_visual_overrides(profile: str) -> dict[str, Any]:
    if profile in {"only_dark_material_and_light", "full_dark_heavy_low_handle"}:
        return {
            "surface_tint": 0.005,
            "dome_or_ambient_intensity_equivalent": 500.0,
            "environment_yaw_rad": -float(np.pi / 2.0),
            "camera_endpoint": {"translation_m": [-0.005, -0.005, -0.005], "rotation_deg": [-1.5, -1.5, -1.5], "focal_scale": 0.98},
        }
    if profile == "bright_light_high_handle":
        return {
            "dome_or_ambient_intensity_equivalent": 3000.0,
            "environment_yaw_rad": float(np.pi / 2.0),
            "camera_endpoint": {"translation_m": [0.005, 0.005, 0.005], "rotation_deg": [1.5, 1.5, 1.5], "focal_scale": 1.02},
        }
    if profile == "only_heavy_low_handle_mechanics":
        return {"mode": "nominal_visual"}
    raise ValueError(f"unsupported stress profile {profile!r}")


def materialize_stress_cases(spec: DepthAddV3ExperimentSpec) -> list[dict[str, Any]]:
    """Materialize the four separate 32-repetition stress profiles."""
    stress = _require_mapping(spec.document["stress_suite"], "stress_suite")
    profiles = _require_sequence(stress["matched_profiles"], "stress_suite.matched_profiles")
    repetitions = int(stress["repetitions_per_profile"])
    rows: list[dict[str, Any]] = []
    for profile_index, profile_value in enumerate(profiles):
        profile = str(profile_value)
        for repetition in range(repetitions):
            experiment_seed = 90_001 + profile_index * 1_000 + repetition
            common = _common_case(spec, experiment_seed, repetition)
            realized_door = _stress_door(spec, profile, experiment_seed)
            stress_visual_overrides = _stress_visual_overrides(profile)
            row = {
                    "suite": "stress",
                    "episode_id": f"stress_{profile}_{repetition:02d}",
                    "stress_profile": profile,
                    "stress_repetition": repetition,
                    **common,
                    "active_randomizations": {"visual": profile != "only_heavy_low_handle_mechanics", "door_geometry": profile != "only_dark_material_and_light", "door_dynamics_cell": profile != "only_dark_material_and_light"},
                    "realized_door": realized_door,
                    "realized_visual_seed_streams": {name: common["seed_streams"][name] for name in VISUAL_STREAMS},
                    "realized_visual": _realized_visual(
                        spec,
                        common["seed_streams"],
                        profile != "only_heavy_low_handle_mechanics",
                        stress_visual_overrides,
                        regime="ood_stress",
                    ),
                    "stress_visual_overrides": stress_visual_overrides,
                }
            row["case_id"] = row["episode_id"]
            row["door_geometry"] = realized_door["geometry"]
            row["door_dynamics_cell_id"] = realized_door["dynamics_cell"]
            row["door_dynamics_cell"] = realized_door["dynamics"]
            rows.append(row)
    if len(rows) != 4 * 32:
        raise RuntimeError(f"materialized {len(rows)} stress rows, expected 128")
    return rows


def materialize_depthadd_v3_experiment(path: Path) -> dict[str, Any]:
    """Load the handoff YAML and return runner-ready primary and stress rows."""
    spec = load_depthadd_v3_experiment(path)
    primary = materialize_primary_cases(spec)
    stress = materialize_stress_cases(spec)
    return {
        "schema": "doordog.sim2sim.depthadd_v3_materialized_experiment.v1",
        "source_experiment": str(spec.source_path),
        "primary_rows": primary,
        "stress_rows": stress,
        "counts": {"primary": len(primary), "stress": len(stress)},
        "primary_policy": {
            "allowed_d1_cells": ["A0", "A1", "A4", "A6"],
            "stress_cells_excluded_from_primary": ["A2", "A3", "A5", "A7", "A8"],
            "matched_lane_contract": "fixed/visual_only share nominal door; door_only/combined share sampled geometry+D1 cell",
            "visual_contract": "primary visual rows use source-authority RGB/depth/camera/lighting ranges, exclude MuJoCo procedural_checker, use reset-only robot material and door-only 0.9-1.1s redraw, and explicitly disable non-equivalent MuJoCo image-space motion blur; HDRI remains an explicit MuJoCo render limitation",
        },
    }
