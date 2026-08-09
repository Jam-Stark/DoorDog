"""P0.4 arm/door force binding and provisional E-zone classification.

The runtime adapter uses only IsaacLab's public Articulation/PhysX tensors.  The
result is an estimate-only, geometry-conditioned capacity; it is not a PhysX
force truth readback and rollout success is never used as a classifier.
"""

from __future__ import annotations

import math
import argparse
import json
import sys
from pathlib import Path
from collections.abc import Mapping, Sequence
from typing import Any

import torch

if __package__ in (None, ""):
    _repo_root = Path(__file__).resolve().parents[2]
    if str(_repo_root) not in sys.path:
        sys.path.insert(0, str(_repo_root))


ARM_BODY_NAME = "arm_body6_to_gripper"
ARM_JOINT_NAMES = tuple(f"arm_j{i}" for i in range(1, 7))
CAPABILITY_AUTHORITY = "ESTIMATE_ONLY_GEOMETRY_CONDITIONED_NOT_PHYSX_FORCE_TRUTH"
CAPABILITY_MODES = ("FULL", "ACUTE_RP0")
P05_CERTIFICATE = "P05_CERTIFICATE"
D1_CAPABILITY_SOURCE = "D1_CAPABILITY_SOURCE"
EFFORT_FREEZE_SCHEMA = "a2_piper_v23_effort_freeze_v1"
EFFORT_FREEZE_SELECTION_OUTCOMES = (
    "NORMAL_BOUNDARY_SELECTED",
    "LADDER_INCONCLUSIVE",
    "F2_100_SELECTED",
)


def _finite_tensor(value: Any, *, name: str, ndim: int | None = None) -> torch.Tensor:
    if not torch.is_tensor(value) or (ndim is not None and value.ndim != ndim):
        shape = None if not torch.is_tensor(value) else tuple(value.shape)
        raise ValueError(f"{name} must be a tensor with ndim={ndim}; got {shape}.")
    if not value.is_floating_point() or not torch.all(torch.isfinite(value)):
        raise ValueError(f"{name} must contain finite floating values.")
    return value


def _skew(vector: torch.Tensor) -> torch.Tensor:
    x, y, z = vector.unbind(dim=-1)
    zeros = torch.zeros_like(x)
    return torch.stack(
        (
            torch.stack((zeros, -z, y), dim=-1),
            torch.stack((z, zeros, -x), dim=-1),
            torch.stack((-y, x, zeros), dim=-1),
        ),
        dim=-2,
    )


def validate_floating_base_articulation_signature(robot: Any) -> dict[str, Any]:
    """Resolve and fail fast on the exact floating-base Piper topology."""

    if getattr(robot, "is_fixed_base", None) is not False:
        raise RuntimeError("P0.4 capability binding requires a floating-base articulation.")
    body_ids, body_names = robot.find_bodies(ARM_BODY_NAME, preserve_order=True)
    if list(body_names) != [ARM_BODY_NAME] or len(body_ids) != 1:
        raise RuntimeError(f"P0.4 requires exactly one {ARM_BODY_NAME!r} body; got {body_names!r}.")
    joint_ids, joint_names = robot.find_joints(list(ARM_JOINT_NAMES), preserve_order=True)
    if list(joint_names) != list(ARM_JOINT_NAMES) or len(joint_ids) != len(ARM_JOINT_NAMES):
        raise RuntimeError(f"P0.4 arm joint order/signature mismatch: {joint_names!r}.")
    return {
        "body_id": int(body_ids[0]),
        "body_name": ARM_BODY_NAME,
        "arm_joint_ids": [int(item) for item in joint_ids],
        "arm_joint_names": list(ARM_JOINT_NAMES),
        "jacobian_joint_ids": [int(item) + 6 for item in joint_ids],
        "floating_base": True,
    }


def solve_force_binding(
    jacobian_w: torch.Tensor,
    gravity_nm: torch.Tensor,
    effort_limit_nm: torch.Tensor,
    hinge_axis_w: torch.Tensor,
    hinge_position_w: torch.Tensor,
    handle_position_w: torch.Tensor,
    *,
    body_position_w: torch.Tensor | None = None,
    arm_joint_ids: Sequence[int],
    floating_base: bool = True,
) -> dict[str, Any]:
    """Intersect per-joint force intervals for a unit hinge tangent.

    ``jacobian_w`` is the direct floating-base body Jacobian from
    ``robot.root_physx_view.get_jacobians()``.  The first six columns are the
    floating base, therefore caller-supplied arm joint ids must be the direct
    articulation ids and this function adds six exactly once.
    ``gravity_nm`` is DOF-only gravity compensation from
    ``get_gravity_compensation_forces()[:, arm_joint_ids]``.
    """

    if floating_base is not True:
        raise RuntimeError("P0.4 capability binding is defined only for floating-base robots.")
    jac = _finite_tensor(jacobian_w, name="jacobian_w", ndim=3)
    gravity = _finite_tensor(gravity_nm, name="gravity_nm", ndim=2)
    limits = _finite_tensor(effort_limit_nm, name="effort_limit_nm", ndim=2)
    axis = _finite_tensor(hinge_axis_w, name="hinge_axis_w", ndim=2)
    hinge = _finite_tensor(hinge_position_w, name="hinge_position_w", ndim=2)
    handle = _finite_tensor(handle_position_w, name="handle_position_w", ndim=2)
    if body_position_w is None:
        raise ValueError("body_position_w is required for the body-origin Jacobian correction.")
    body = _finite_tensor(body_position_w, name="body_position_w", ndim=2)
    if len(arm_joint_ids) != 6 or any(isinstance(item, bool) or not isinstance(item, int) or item < 0 for item in arm_joint_ids):
        raise ValueError("arm_joint_ids must contain six non-negative articulation indices.")
    batch = jac.shape[0]
    if any(tuple(value.shape) != (batch, 3) for value in (axis, hinge, handle, body)):
        raise ValueError("body, hinge axis/position, and handle position must have shape (N,3).")
    if tuple(gravity.shape) != (batch, 6) or tuple(limits.shape) != (batch, 6):
        raise ValueError("gravity_nm and effort_limit_nm must have shape (N,6).")
    if jac.shape[1] != 6 or any(item + 6 >= jac.shape[2] for item in arm_joint_ids):
        raise ValueError("floating-base Jacobian must have 6 rows and arm articulation columns +6.")
    if torch.any(limits <= 0.0):
        raise ValueError("effort limits must be positive.")
    axis_norm = torch.linalg.vector_norm(axis, dim=-1, keepdim=True)
    radius_vec = handle - hinge
    axis_unit = axis / axis_norm
    d_perp = radius_vec - axis_unit * torch.sum(axis_unit * radius_vec, dim=-1, keepdim=True)
    rho = torch.linalg.vector_norm(d_perp, dim=-1, keepdim=True)
    if torch.any(axis_norm <= 0.0) or torch.any(rho <= 0.0):
        raise ValueError("hinge axis and projected hinge-to-handle radius must be non-zero.")
    tangent_raw = torch.cross(axis_unit, d_perp / rho, dim=-1)
    tangent_norm = torch.linalg.vector_norm(tangent_raw, dim=-1, keepdim=True)
    if torch.any(tangent_norm <= 0.0) or not torch.all(torch.isfinite(tangent_norm)):
        raise ValueError("hinge_axis_w x hinge_to_handle_radius must be finite and non-zero.")
    tangent = tangent_raw / tangent_norm
    selected = torch.tensor([item + 6 for item in arm_joint_ids], dtype=torch.long, device=jac.device)
    selected_jac = jac.index_select(2, selected)
    r_bh = handle - body
    corrected_linear = selected_jac[:, :3, :] - torch.bmm(_skew(r_bh), selected_jac[:, 3:, :])
    d = torch.einsum("ni,nij->nj", tangent, corrected_linear)
    lower = torch.zeros(batch, dtype=jac.dtype, device=jac.device)
    upper = torch.full((batch,), float("inf"), dtype=jac.dtype, device=jac.device)
    infeasible = torch.zeros(batch, dtype=torch.bool, device=jac.device)
    unbounded_joint = torch.zeros((batch, 6), dtype=torch.bool, device=jac.device)
    for joint in range(6):
        coefficient = d[:, joint]
        gravity_value = gravity[:, joint]
        limit = limits[:, joint]
        positive = coefficient > 0.0
        negative = coefficient < 0.0
        zero = coefficient == 0.0
        infeasible |= zero & (gravity_value.abs() > limit)
        unbounded_joint[:, joint] = zero & ~infeasible
        pos_lower = (-limit - gravity_value) / coefficient
        pos_upper = (limit - gravity_value) / coefficient
        neg_lower = (limit - gravity_value) / coefficient
        neg_upper = (-limit - gravity_value) / coefficient
        lower = torch.where(positive, torch.maximum(lower, pos_lower), lower)
        upper = torch.where(positive, torch.minimum(upper, pos_upper), upper)
        lower = torch.where(negative, torch.maximum(lower, neg_lower), lower)
        upper = torch.where(negative, torch.minimum(upper, neg_upper), upper)
    infeasible |= upper < lower
    if torch.any(infeasible):
        status = "INFEASIBLE"
    elif torch.any(~torch.isfinite(upper)):
        status = "UNBOUNDED"
    else:
        status = "VALID"
    radius_m = rho.squeeze(-1)
    capacity_nm = upper * radius_m
    return {
        "status": status,
        "status_by_sample": [
            "INFEASIBLE" if bool(infeasible[i]) else "UNBOUNDED" if not bool(torch.isfinite(upper[i])) else "VALID"
            for i in range(batch)
        ],
        "lower_nm": lower * radius_m,
        "upper_nm": upper * radius_m,
        "capacities_nm": capacity_nm,
        "lower_n": lower,
        "upper_n": upper,
        "force_capacity_n": upper,
        "capacity_nm": capacity_nm,
        "d_i": d,
        "gravity_nm": gravity,
        "effort_limit_nm": limits,
        "tangent_w": tangent,
        "d_perp_w": d_perp,
        "rho_m": radius_m,
        "radius_m": radius_m,
        "r_bh_w": r_bh,
        "unbounded_joint": unbounded_joint,
        "authority": CAPABILITY_AUTHORITY,
        "units": {"force": "N", "radius": "m", "capacity": "N*m"},
    }


def bind_articulation_capability(
    robot: Any,
    door: Any,
    hinge_axis_w: torch.Tensor,
    hinge_position_w: torch.Tensor,
) -> dict[str, Any]:
    """Read the approved high-level runtime tensors and solve the binding."""

    signature = validate_floating_base_articulation_signature(robot)
    handle_ids, handle_names = door.find_bodies("door_handle", preserve_order=True)
    if len(handle_ids) != 1 or list(handle_names) != ["door_handle"]:
        raise RuntimeError(f"P0.4 requires exactly one door_handle body; got {handle_names!r}.")
    robot_body_pos_w = robot.data.body_pos_w[:, signature["body_id"]]
    handle_position_w = door.data.body_pos_w[:, int(handle_ids[0])]
    jacobians = robot.root_physx_view.get_jacobians()
    jacobian = jacobians[:, signature["body_id"], :, :]
    gravity_all = robot.root_physx_view.get_gravity_compensation_forces()
    gravity = gravity_all[:, signature["arm_joint_ids"]]
    limits = robot.data.joint_effort_limits[:, signature["arm_joint_ids"]]
    return {
        "signature": signature,
        "binding": solve_force_binding(
            jacobian,
            gravity,
            limits,
            hinge_axis_w,
            hinge_position_w,
            handle_position_w,
            body_position_w=robot_body_pos_w,
            arm_joint_ids=signature["arm_joint_ids"],
            floating_base=True,
        ),
        "source_api": {
            "jacobian": "Articulation.root_physx_view.get_jacobians()[:, body_id, :, :]",
            "gravity": "Articulation.root_physx_view.get_gravity_compensation_forces()[:, arm_joint_ids]",
            "effort_limits": "Articulation.data.joint_effort_limits[:, arm_joint_ids]",
            "body_position": "robot.data.body_pos_w[:, body_id]",
            "handle_position": "door.data.body_pos_w[:, handle_id]",
        },
        "body_name": ARM_BODY_NAME,
        "handle_name": "door_handle",
    }


def stable_capacity_minimum(samples: Sequence[Mapping[str, Any]], *, mode: str) -> dict[str, Any]:
    if mode not in CAPABILITY_MODES:
        raise ValueError(f"capability mode must be one of {CAPABILITY_MODES}; got {mode!r}.")
    if not samples:
        raise ValueError("stable geometry window requires at least one capability sample.")
    capacities = []
    for index, sample in enumerate(samples):
        if not isinstance(sample, Mapping) or sample.get("status") != "VALID":
            raise ValueError(f"stable {mode} geometry sample {index} is not VALID.")
        capacity = sample.get("capacities_nm", sample.get("capacity_nm"))
        if isinstance(capacity, bool) or not isinstance(capacity, (int, float)) or not math.isfinite(float(capacity)):
            raise ValueError(f"stable {mode} geometry sample {index} capacity is missing/non-finite.")
        capacities.append(float(capacity))
    return {
        "mode": mode,
        "capacities_nm": min(capacities),
        "capacity_nm": min(capacities),
        "sample_count": len(capacities),
        "geometry_conditioned": True,
        "authority": CAPABILITY_AUTHORITY,
        "rollout_success_not_classifier": True,
    }


def classify_e_zone(
    *,
    lower_nm: float,
    upper_nm: float,
    capacity_rp0_nm: float,
    capacity_full_nm: float,
    capacity_best_nm: float,
) -> dict[str, Any]:
    """Assign only the provisional physics-first zone; confirmed E2 is false."""

    values = {
        "lower_nm": lower_nm,
        "upper_nm": upper_nm,
        "capacity_rp0_nm": capacity_rp0_nm,
        "capacity_full_nm": capacity_full_nm,
        "capacity_best_nm": capacity_best_nm,
    }
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) for value in values.values()):
        return {"zone": "INCONCLUSIVE", "confirmed_E2": False, "reason": "INVALID_NONFINITE_CAPABILITY_INPUT", "authority": CAPABILITY_AUTHORITY}
    lower = float(lower_nm)
    upper = float(upper_nm)
    if not (lower < upper):
        return {"zone": "INCONCLUSIVE", "confirmed_E2": False, "reason": "INVALID_FORCE_BRACKET", "authority": CAPABILITY_AUTHORITY}
    rp0 = float(capacity_rp0_nm)
    full = float(capacity_full_nm)
    best = float(capacity_best_nm)
    if rp0 >= upper:
        zone = "E0"
    elif rp0 < upper <= full:
        zone = "E1"
    elif lower < best < upper:
        zone = "nearE2"
    elif best <= lower:
        zone = "E2_CANDIDATE_UNCONFIRMED"
    else:
        zone = "INCONCLUSIVE"
    return {
        "zone": zone,
        "confirmed_E2": False,
        "authority": CAPABILITY_AUTHORITY,
        "lower_nm": lower,
        "upper_nm": upper,
        "capacity_rp0_nm": rp0,
        "capacity_full_nm": full,
        "capacity_best_nm": best,
    }


def capacity_from_force(force_n: float, radius_m: float) -> float:
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)) for value in (force_n, radius_m)):
        raise ValueError("force_n and radius_m must be finite numbers.")
    if float(force_n) < 0.0 or float(radius_m) <= 0.0:
        raise ValueError("force_n must be non-negative and radius_m positive.")
    return float(force_n) * float(radius_m)


CAPABILITY_SAMPLE_SCHEMA = "a2_piper_v23_capability_sample_v1"
D1_FREEZE_SCHEMA = "a2_piper_v23_d1_freeze_v2"
D1_INCOMPLETE_SCHEMA = "a2_piper_v23_d1_capability_source_incomplete_v1"
SELECTED_CELL_FREEZE_SCHEMA = "a2_piper_v23_p05_selected_cell_freeze_v1"
CAPABILITY_SOURCE_FREEZE_SCHEMA = "a2_piper_v23_capability_source_freeze_v1"
SELECTED_CELL_ID = "A8"
CAPABILITY_SOURCE_CELL_ID = "A0"
SELECTED_EFFORT_NM = 40.0
CAPABILITY_SOURCE_EFFORT_NM = 40.0
CAPABILITY_SOURCE_BASIS = "CURRENT_EASY_A0_STABLE_REFERENCE"
CAPABILITY_SOURCE_REQUESTED_PARAMS = {
    "hinge_damping_native": 50.0,
    "hinge_stiffness_native": 2.0,
    "hinge_max_force_nm": 4.5,
    "door_weight_kg": 120.0,
}
CAPABILITY_SOURCE_NATIVE_PARAMS = {
    "hinge_damping_native": 2864.7890625,
    "hinge_stiffness_native": 114.59156036376953,
    "hinge_effort_limit_nm": 4.5,
    "door_weight_kg": 119.99999237060547,
}
CAPACITY_TRANSFER_BASIS = "EXACT_SHARED_CANONICAL_LOCAL_KINEMATIC_FACTS"
SHARED_LOCAL_KINEMATIC_FIELDS = (
    "door_width_m",
    "door_height_m",
    "handle_height_m",
    "handle_width_m",
    "handle_type",
    "door_open_lr",
    "door_open_io",
    "door_open_lr_sign",
    "door_open_io_sign",
    "hinge_axis_local",
    "hinge_anchor_local",
)
ATLAS_CELLS = tuple(f"A{index}" for index in range(9))
P05_EXPORT_SCHEMA = "a2_piper_v23_episode_records_export_v1"
P05_EPISODE_SCHEMA = "a2_piper_v23_episode_record_v1"
P05_STEP_SCHEMA = "a2_piper_v23_step_trace_v1"


def _read_json(path: Path) -> Mapping[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"input must be an existing regular file: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid JSON input: {path}") from exc
    if not isinstance(payload, Mapping):
        raise ValueError(f"JSON input must be an object: {path}")
    return payload


def _validate_effort_freeze_payload(effort_freeze: Mapping[str, Any]) -> float:
    selected_effort = effort_freeze.get("selected_effort_nm")
    if (
        effort_freeze.get("schema") != EFFORT_FREEZE_SCHEMA
        or effort_freeze.get("status") != "MEASURED_FREEZE"
        or effort_freeze.get("selection_outcome") not in EFFORT_FREEZE_SELECTION_OUTCOMES
        or isinstance(selected_effort, bool)
        or not isinstance(selected_effort, (int, float))
        or float(selected_effort) not in (20.0, 25.0, 30.0, 40.0, 60.0, 100.0)
        or not isinstance(effort_freeze.get("effort_profile"), Mapping)
        or effort_freeze["effort_profile"].get("effort_nm") != float(selected_effort)
        or effort_freeze["effort_profile"].get("name") != f"base_v23_p0_effort_{float(selected_effort):g}"
        or not isinstance(effort_freeze.get("source_provenance"), Mapping)
        or effort_freeze["source_provenance"].get("complete") is not True
        or not isinstance(effort_freeze.get("authorities"), Mapping)
        or effort_freeze["authorities"].get("checkpoint_load_mode") != "policy_only"
    ):
        raise ValueError("effort freeze must preserve the exact measured v1 freeze artifact")
    return float(selected_effort)


def _atlas_rows(payload: Mapping[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if payload.get("schema") != "a2_piper_v23_door_atlas_raw_v1" or payload.get("status") != "MEASURED_RAW":
        raise ValueError("atlas input must be the measured A0-A8 raw schema")
    rows = payload.get("rows")
    if not isinstance(rows, list) or len(rows) != len(ATLAS_CELLS):
        raise ValueError("atlas input must contain exactly nine measured rows")
    try:
        from .p0_door_atlas_probe import validate_canonical_geometry_record
    except ImportError:
        from scriptsFORhuman.v23.p0_door_atlas_probe import validate_canonical_geometry_record
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise ValueError(f"atlas row {index} must be an object")
        cell_id = row.get("cell_id")
        canonical = row.get("canonical_geometry")
        realized = row.get("realized_params")
        requested = row.get("requested_params")
        geometry_id = row.get("geometry_id")
        if (
            cell_id not in ATLAS_CELLS
            or cell_id in seen
            or not isinstance(canonical, Mapping)
            or not isinstance(realized, Mapping)
            or not isinstance(requested, Mapping)
            or not isinstance(geometry_id, str)
            or not geometry_id
        ):
            raise ValueError(f"atlas row {index} lacks exact cell/geometry identity")
        canonical_expected = validate_canonical_geometry_record(
            canonical, cell_id=cell_id, realized_params=realized
        )
        if geometry_id != canonical_expected["geometry_id"]:
            raise ValueError(f"atlas row {index} geometry_id disagrees with canonical geometry")
        normalized.append(
            {
                "cell_id": cell_id,
                "geometry_id": geometry_id,
                "canonical_geometry": canonical_expected,
                "requested_params": dict(requested),
                "realized_params": dict(canonical_expected["realized_params"]),
            }
        )
        seen.add(cell_id)
    if set(seen) != set(ATLAS_CELLS):
        raise ValueError("atlas input must cover A0-A8 exactly once")
    return dict(payload), normalized


def _local_kinematic_signature(canonical_geometry: Mapping[str, Any]) -> dict[str, Any]:
    facts = canonical_geometry.get("local_facts")
    if not isinstance(facts, Mapping):
        raise ValueError("canonical geometry is missing local_facts")
    missing = [field for field in SHARED_LOCAL_KINEMATIC_FIELDS if field not in facts]
    if missing:
        raise ValueError(f"canonical local kinematic facts are incomplete: {missing}")
    signature = {
        field: list(facts[field]) if isinstance(facts[field], list) else facts[field]
        for field in SHARED_LOCAL_KINEMATIC_FIELDS
    }
    expected = {
        "handle_type": "lever",
        "door_open_lr": "right",
        "door_open_io": "out",
        "door_open_lr_sign": -1,
        "door_open_io_sign": -1,
        "hinge_axis_local": [0.0, 0.0, 1.0],
        "hinge_anchor_local": [0.02, 0.475, 0.0],
    }
    for field, value in expected.items():
        if signature[field] != value:
            raise ValueError(f"canonical local kinematic fact {field} is not the registered right/out contract")
    return signature


def _validate_shared_local_kinematics(atlas_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    signatures = [_local_kinematic_signature(row["canonical_geometry"]) for row in atlas_rows]
    if not signatures:
        raise ValueError("shared local kinematic validation requires A0-A8 rows")
    if any(signature != signatures[0] for signature in signatures[1:]):
        raise ValueError("A0-A8 canonical local hinge/handle/right-out facts must match exactly")
    return signatures[0]


def _external_by_cell(external_rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for cell_id in ATLAS_CELLS:
        rows = [row for row in external_rows if row.get("cell_id") == cell_id]
        if len(rows) != 20:
            raise ValueError(f"external input must contain exactly 20 rows for {cell_id}")
        first = rows[0]
        if any(
            row.get("geometry_id") != first.get("geometry_id")
            or row.get("canonical_geometry") != first.get("canonical_geometry")
            or row.get("realized_params") != first.get("realized_params")
            for row in rows[1:]
        ):
            raise ValueError(f"external cell {cell_id} geometry/realized parameters are not stable")
        result[cell_id] = {
            "cell_id": cell_id,
            "geometry_id": first["geometry_id"],
            "canonical_geometry": first["canonical_geometry"],
            "realized_params": first["realized_params"],
            "rows": rows,
        }
    return result


def build_selected_cell_freeze(
    *,
    atlas_input: Mapping[str, Any],
    external_threshold: Mapping[str, Any],
    effort_freeze: Mapping[str, Any],
    selected_cell: str,
    source_paths: Mapping[str, str],
) -> dict[str, Any]:
    """Freeze the explicit A8 directional opening cell before P0.5 capability."""

    if selected_cell != SELECTED_CELL_ID:
        raise ValueError("selected-cell freeze requires explicit selected-cell A8")
    effort = _validate_effort_freeze_payload(effort_freeze)
    if effort != SELECTED_EFFORT_NM:
        raise ValueError("selected-cell freeze requires the measured selected effort of 40 N*m")
    atlas, atlas_rows = _atlas_rows(atlas_input)
    external, external_rows = _external_rows(external_threshold)
    external_cells = _external_by_cell(external_rows)
    for atlas_row in atlas_rows:
        external_cell = external_cells[atlas_row["cell_id"]]
        if (
            external_cell["geometry_id"] != atlas_row["geometry_id"]
            or external_cell["canonical_geometry"] != atlas_row["canonical_geometry"]
            or external_cell["realized_params"] != atlas_row["realized_params"]
        ):
            raise ValueError(f"external cell {atlas_row['cell_id']} does not join its atlas geometry exactly")
    shared_facts = _validate_shared_local_kinematics(atlas_rows)
    try:
        from .p0_door_atlas_probe import classify_directional_opening_bracket
    except ImportError:
        from scriptsFORhuman.v23.p0_door_atlas_probe import classify_directional_opening_bracket
    directional = classify_directional_opening_bracket(external_rows)
    if set(directional.get("cells", {})) != set(ATLAS_CELLS):
        raise ValueError("directional opening brackets must cover A0-A8 exactly")
    uppers = {
        cell_id: float(directional["cells"][cell_id]["opening_bracket"]["upper_nm"])
        for cell_id in ATLAS_CELLS
    }
    if uppers[SELECTED_CELL_ID] != max(uppers.values()) or list(uppers.values()).count(uppers[SELECTED_CELL_ID]) != 1:
        raise ValueError("A8 must be the unique maximum positive-opening upper bracket")
    selected_bracket = directional["cells"][SELECTED_CELL_ID]["opening_bracket"]
    if selected_bracket.get("first_pass_nm") != effort or not (30.0 < effort <= 40.0):
        raise ValueError("selected A8 opening bracket must be (30,40] with first pass at effort 40")
    for cell_id, cell_bracket in directional["cells"].items():
        if cell_bracket.get("typed_state") != "UNIDIRECTIONAL_OPENING_BRACKET":
            raise ValueError(f"{cell_id} directional opening state is not typed")
        if cell_bracket.get("negative_censor", {}).get("status") != "RIGHT_CENSORED":
            raise ValueError(f"{cell_id} negative sign must remain RIGHT_CENSORED")
        if "midpoint_nm" in cell_bracket or "midpoint_nm" in cell_bracket.get("opening_bracket", {}):
            raise ValueError(f"{cell_id} directional bracket must not contain a midpoint")
    selected_geometry = next(row for row in atlas_rows if row["cell_id"] == SELECTED_CELL_ID)
    return {
        "schema": SELECTED_CELL_FREEZE_SCHEMA,
        "status": "SELECTED_CELL_FROZEN",
        "selected_cell_id": SELECTED_CELL_ID,
        "selected_effort_nm": effort,
        "effort_profile": dict(effort_freeze["effort_profile"]),
        "zone_state": "PENDING_CAPABILITY",
        "confirmed_E2": False,
        "authority": "MEASURED_DIRECTIONAL_OPENING_AND_EXACT_GEOMETRY_PROVENANCE",
        "directional_contract": dict(directional["contract"]),
        "directional_brackets": directional["cells"],
        "selected_opening_bracket": dict(selected_bracket),
        "atlas_rows": atlas_rows,
        "selected_geometry": selected_geometry,
        "shared_local_kinematic_facts": shared_facts,
        "source_paths": {str(key): str(value) for key, value in source_paths.items()},
        "source_provenance": {
            "atlas": {
                "schema": atlas.get("schema"),
                "status": atlas.get("status"),
                "source_identity": atlas.get("source_identity"),
                "row_count": len(atlas_rows),
            },
            "external_threshold": {
                "schema": external.get("schema"),
                "status": external.get("status"),
                "source_identity": external.get("source_identity"),
                "row_count": len(external_rows),
            },
            "effort_freeze": {
                "schema": effort_freeze.get("schema"),
                "status": effort_freeze.get("status"),
                "selection_outcome": effort_freeze.get("selection_outcome"),
                "source_provenance": effort_freeze.get("source_provenance"),
            },
        },
        "preserved_bilateral_bracket": external.get("bracket"),
    }


def validate_selected_cell_freeze(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping) or payload.get("schema") != SELECTED_CELL_FREEZE_SCHEMA:
        raise ValueError("selected-cell freeze must use the registered v1 schema")
    expected_top_level = {
        "atlas_rows",
        "authority",
        "confirmed_E2",
        "directional_brackets",
        "directional_contract",
        "effort_profile",
        "preserved_bilateral_bracket",
        "schema",
        "selected_cell_id",
        "selected_effort_nm",
        "selected_geometry",
        "selected_opening_bracket",
        "shared_local_kinematic_facts",
        "source_paths",
        "source_provenance",
        "status",
        "zone_state",
    }
    if set(payload) != expected_top_level:
        raise ValueError("selected-cell freeze fields do not match the emitted artifact contract")
    if (
        payload.get("status") != "SELECTED_CELL_FROZEN"
        or payload.get("selected_cell_id") != SELECTED_CELL_ID
        or payload.get("selected_effort_nm") != SELECTED_EFFORT_NM
        or payload.get("zone_state") != "PENDING_CAPABILITY"
        or payload.get("confirmed_E2") is not False
        or payload.get("authority") != "MEASURED_DIRECTIONAL_OPENING_AND_EXACT_GEOMETRY_PROVENANCE"
    ):
        raise ValueError("selected-cell freeze status/selection state is invalid")

    def require_exact_keys(value: Any, expected: set[str], *, name: str) -> Mapping[str, Any]:
        if not isinstance(value, Mapping) or set(value) != expected:
            raise ValueError(f"{name} fields do not match the emitted artifact contract")
        return value

    effort_profile = require_exact_keys(payload["effort_profile"], {"effort_nm", "name"}, name="effort profile")
    if effort_profile["effort_nm"] != SELECTED_EFFORT_NM or effort_profile["name"] != "base_v23_p0_effort_40":
        raise ValueError("selected-cell freeze effort profile does not match selected 40 N*m")

    directional_contract = require_exact_keys(
        payload["directional_contract"],
        {"basis", "hinge_coordinate", "torque_sign"},
        name="directional contract",
    )
    if dict(directional_contract) != {
        "basis": "TORQUE_SIGN_TIMES_RESOLVED_HINGE_AXIS; TASK_OPENING_IS_POSITIVE_HINGE_POSITION",
        "hinge_coordinate": "POSITIVE_OPENING",
        "torque_sign": 1,
    }:
        raise ValueError("selected-cell freeze directional contract is invalid")

    source_paths = require_exact_keys(
        payload["source_paths"],
        {"atlas", "external_threshold", "effort_freeze"},
        name="selected-cell freeze source paths",
    )
    if any(not isinstance(source_paths[key], str) or not source_paths[key] for key in source_paths):
        raise ValueError("selected-cell freeze source paths must be non-empty strings")

    source_provenance = require_exact_keys(
        payload["source_provenance"],
        {"atlas", "external_threshold", "effort_freeze"},
        name="selected-cell freeze source provenance",
    )
    atlas_provenance = require_exact_keys(
        source_provenance["atlas"],
        {"schema", "status", "source_identity", "row_count"},
        name="atlas source provenance",
    )
    external_provenance = require_exact_keys(
        source_provenance["external_threshold"],
        {"schema", "status", "source_identity", "row_count"},
        name="external source provenance",
    )
    effort_provenance = require_exact_keys(
        source_provenance["effort_freeze"],
        {"schema", "status", "selection_outcome", "source_provenance"},
        name="effort source provenance",
    )
    if (
        atlas_provenance["schema"] != "a2_piper_v23_door_atlas_raw_v1"
        or atlas_provenance["status"] != "MEASURED_RAW"
        or atlas_provenance["row_count"] != len(ATLAS_CELLS)
        or not isinstance(atlas_provenance["source_identity"], Mapping)
        or external_provenance["schema"] != "a2_piper_v23_door_external_torque_threshold_v1"
        or external_provenance["status"] != "MEASURED_RAW"
        or external_provenance["row_count"] != len(ATLAS_CELLS) * 2 * 10
        or not isinstance(external_provenance["source_identity"], Mapping)
        or effort_provenance["schema"] != EFFORT_FREEZE_SCHEMA
        or effort_provenance["status"] != "MEASURED_FREEZE"
        or effort_provenance["selection_outcome"] not in EFFORT_FREEZE_SELECTION_OUTCOMES
        or not isinstance(effort_provenance["source_provenance"], Mapping)
        or effort_provenance["source_provenance"].get("complete") is not True
    ):
        raise ValueError("selected-cell freeze source provenance is incomplete or inconsistent")

    atlas_rows = payload.get("atlas_rows")
    if not isinstance(atlas_rows, list) or len(atlas_rows) != len(ATLAS_CELLS):
        raise ValueError("selected-cell freeze must carry all nine atlas rows")
    try:
        from .p0_door_atlas_probe import validate_canonical_geometry_record
    except ImportError:
        from scriptsFORhuman.v23.p0_door_atlas_probe import validate_canonical_geometry_record
    atlas_by_cell: dict[str, Mapping[str, Any]] = {}
    for index, atlas_row in enumerate(atlas_rows):
        if not isinstance(atlas_row, Mapping) or atlas_row.get("cell_id") not in ATLAS_CELLS or atlas_row["cell_id"] in atlas_by_cell:
            raise ValueError(f"selected-cell freeze atlas row {index} has an invalid cell identity")
        require_exact_keys(
            atlas_row,
            {"canonical_geometry", "cell_id", "geometry_id", "realized_params", "requested_params"},
            name=f"selected-cell freeze atlas row {index}",
        )
        canonical = atlas_row.get("canonical_geometry")
        realized = atlas_row.get("realized_params")
        if not isinstance(canonical, Mapping) or not isinstance(realized, Mapping) or not isinstance(atlas_row.get("requested_params"), Mapping):
            raise ValueError(f"selected-cell freeze atlas row {index} lacks canonical realized geometry")
        expected = validate_canonical_geometry_record(canonical, cell_id=atlas_row["cell_id"], realized_params=realized)
        if atlas_row.get("geometry_id") != expected["geometry_id"]:
            raise ValueError(f"selected-cell freeze atlas row {index} geometry identity is invalid")
        atlas_by_cell[atlas_row["cell_id"]] = atlas_row
    if set(atlas_by_cell) != set(ATLAS_CELLS):
        raise ValueError("selected-cell freeze atlas rows must cover A0-A8 exactly")
    _validate_shared_local_kinematics(atlas_rows)
    directional = payload.get("directional_brackets")
    if not isinstance(directional, Mapping) or set(directional) != set(ATLAS_CELLS):
        raise ValueError("selected-cell freeze directional brackets must cover A0-A8")
    for cell_id in ATLAS_CELLS:
        row = directional[cell_id]
        require_exact_keys(
            row,
            {"basis", "cell_id", "hinge_coordinate", "negative_censor", "opening_bracket", "status", "torque_sign", "typed_state"},
            name=f"selected-cell freeze directional row {cell_id}",
        )
        negative_censor = require_exact_keys(
            row["negative_censor"],
            {"first_pass_nm", "last_fail_nm", "status"},
            name=f"{cell_id} negative censor",
        )
        opening = require_exact_keys(
            row["opening_bracket"],
            {"first_pass_nm", "last_fail_nm", "lower_nm", "status", "upper_nm"},
            name=f"{cell_id} opening bracket",
        )
        if (
            row["cell_id"] != cell_id
            or row["status"] != "UNIDIRECTIONAL_OPENING_BRACKET"
            or row["typed_state"] != "UNIDIRECTIONAL_OPENING_BRACKET"
            or row["torque_sign"] != 1
            or row["hinge_coordinate"] != "POSITIVE_OPENING"
            or row["basis"] != "TORQUE_SIGN_TIMES_RESOLVED_HINGE_AXIS; TASK_OPENING_IS_POSITIVE_HINGE_POSITION"
            or negative_censor != {"first_pass_nm": None, "last_fail_nm": 100.0, "status": "RIGHT_CENSORED"}
            or opening["status"] != "VALID_BRACKET"
            or any(
                isinstance(opening[field], bool)
                or not isinstance(opening[field], (int, float))
                or not math.isfinite(float(opening[field]))
                for field in ("first_pass_nm", "last_fail_nm", "lower_nm", "upper_nm")
            )
            or opening["last_fail_nm"] != opening["lower_nm"]
            or opening["first_pass_nm"] != opening["upper_nm"]
            or not (float(opening["lower_nm"]) < float(opening["upper_nm"]))
        ):
            raise ValueError(f"selected-cell freeze directional row {cell_id} is invalid")
        if cell_id == SELECTED_CELL_ID and opening != {
            "first_pass_nm": 40.0,
            "last_fail_nm": 30.0,
            "lower_nm": 30.0,
            "status": "VALID_BRACKET",
            "upper_nm": 40.0,
        }:
            raise ValueError("selected-cell freeze A8 opening bracket does not match the measured 30-40 N*m bracket")

    preserved_bilateral = require_exact_keys(
        payload["preserved_bilateral_bracket"],
        {"cells", "status", "threshold_rad"},
        name="preserved bilateral bracket",
    )
    if (
        preserved_bilateral["status"] != "RIGHT_CENSORED"
        or preserved_bilateral["threshold_rad"] != 0.02
        or not isinstance(preserved_bilateral["cells"], Mapping)
        or set(preserved_bilateral["cells"]) != set(ATLAS_CELLS)
    ):
        raise ValueError("selected-cell freeze preserved bilateral bracket is incomplete")

    selected_geometry = payload.get("selected_geometry")
    if not isinstance(selected_geometry, Mapping) or selected_geometry.get("cell_id") != SELECTED_CELL_ID:
        raise ValueError("selected-cell freeze must carry selected A8 geometry")
    if selected_geometry != atlas_by_cell[SELECTED_CELL_ID]:
        raise ValueError("selected-cell freeze selected geometry must match its atlas A8 row")
    if selected_geometry.get("geometry_id") != selected_geometry.get("canonical_geometry", {}).get("geometry_id"):
        raise ValueError("selected-cell freeze selected geometry identity is invalid")

    shared_local_facts = require_exact_keys(
        payload["shared_local_kinematic_facts"],
        set(SHARED_LOCAL_KINEMATIC_FIELDS),
        name="selected-cell freeze shared local kinematic facts",
    )
    expected_shared_facts = _validate_shared_local_kinematics(atlas_rows)
    if dict(shared_local_facts) != expected_shared_facts:
        raise ValueError("selected-cell freeze shared local kinematic facts disagree with atlas rows")

    uppers = {cell_id: float(directional[cell_id]["opening_bracket"]["upper_nm"]) for cell_id in ATLAS_CELLS}
    if uppers[SELECTED_CELL_ID] != max(uppers.values()) or list(uppers.values()).count(uppers[SELECTED_CELL_ID]) != 1:
        raise ValueError("selected-cell freeze must preserve A8 as the unique maximum opening upper")
    selected_opening = payload.get("selected_opening_bracket")
    if (
        not isinstance(selected_opening, Mapping)
        or set(selected_opening) != {"first_pass_nm", "last_fail_nm", "lower_nm", "status", "upper_nm"}
        or dict(selected_opening) != dict(directional[SELECTED_CELL_ID]["opening_bracket"])
        or selected_opening.get("first_pass_nm") != SELECTED_EFFORT_NM
        or selected_opening.get("lower_nm") != 30.0
        or selected_opening.get("last_fail_nm") != 30.0
        or selected_opening.get("upper_nm") != SELECTED_EFFORT_NM
        or selected_opening.get("status") != "VALID_BRACKET"
        or not (30.0 < SELECTED_EFFORT_NM <= 40.0)
    ):
        raise ValueError("selected-cell freeze selected A8 opening bracket must equal its measured directional bracket")
    return dict(payload)


def build_capability_source_freeze(
    *,
    atlas_input: Mapping[str, Any],
    external_threshold: Mapping[str, Any],
    effort_freeze: Mapping[str, Any],
    source_cell: str,
    source_paths: Mapping[str, str],
) -> dict[str, Any]:
    """Freeze the exact current-easy A0 source used by the D1 reducer."""

    if source_cell != CAPABILITY_SOURCE_CELL_ID:
        raise ValueError("capability-source freeze source cell must be exactly A0")
    selected_effort = _validate_effort_freeze_payload(effort_freeze)
    if selected_effort != CAPABILITY_SOURCE_EFFORT_NM:
        raise ValueError("capability-source freeze requires the measured effort-40 freeze")
    atlas, atlas_rows = _atlas_rows(atlas_input)
    atlas_by_cell = {row["cell_id"]: row for row in atlas_rows}
    source_row = atlas_by_cell.get(CAPABILITY_SOURCE_CELL_ID)
    if not isinstance(source_row, Mapping):
        raise ValueError("capability-source freeze requires the measured A0 atlas row")
    requested = source_row.get("requested_params")
    realized = source_row.get("realized_params")
    if requested != CAPABILITY_SOURCE_REQUESTED_PARAMS:
        raise ValueError("A0 capability-source requested parameters disagree with the registered reference")
    if realized != CAPABILITY_SOURCE_NATIVE_PARAMS:
        raise ValueError("A0 capability-source native parameters disagree with the registered reference")
    external, external_rows = _external_rows(external_threshold)
    external_by_cell = _external_by_cell(external_rows)
    external_source = external_by_cell.get(CAPABILITY_SOURCE_CELL_ID)
    if not isinstance(external_source, Mapping):
        raise ValueError("capability-source freeze requires measured A0 external threshold evidence")
    if (
        external_source.get("geometry_id") != source_row["geometry_id"]
        or external_source.get("canonical_geometry") != source_row["canonical_geometry"]
        or external_source.get("realized_params") != source_row["realized_params"]
    ):
        raise ValueError("A0 capability-source atlas and external geometry identities disagree")
    shared_facts = _validate_shared_local_kinematics(atlas_rows)
    if not isinstance(source_paths, Mapping) or set(source_paths) != {"atlas", "external_threshold", "effort_freeze"}:
        raise ValueError("capability-source freeze requires exact atlas/external/effort source paths")
    if any(not isinstance(value, str) or not value for value in source_paths.values()):
        raise ValueError("capability-source freeze source paths must be non-empty strings")
    return {
        "schema": CAPABILITY_SOURCE_FREEZE_SCHEMA,
        "status": "CAPABILITY_SOURCE_FROZEN",
        "purpose": D1_CAPABILITY_SOURCE,
        "source_cell_id": CAPABILITY_SOURCE_CELL_ID,
        "source_geometry_id": source_row["geometry_id"],
        "selection_basis": CAPABILITY_SOURCE_BASIS,
        "selected_effort_nm": CAPABILITY_SOURCE_EFFORT_NM,
        "effort_profile": dict(effort_freeze["effort_profile"]),
        "confirmed_E2": False,
        "requested_params": dict(requested),
        "native_params": dict(realized),
        "canonical_geometry": dict(source_row["canonical_geometry"]),
        "shared_local_kinematic_facts": shared_facts,
        "source_paths": {str(key): str(value) for key, value in source_paths.items()},
        "source_provenance": {
            "atlas": {
                "schema": atlas.get("schema"),
                "status": atlas.get("status"),
                "source_identity": atlas.get("source_identity"),
                "row_count": len(atlas_rows),
            },
            "external_threshold": {
                "schema": external.get("schema"),
                "status": external.get("status"),
                "source_identity": external.get("source_identity"),
                "probe_contract": external.get("probe_contract"),
                "row_count": len(external_rows),
            },
            "effort_freeze": {
                "schema": effort_freeze.get("schema"),
                "status": effort_freeze.get("status"),
                "selection_outcome": effort_freeze.get("selection_outcome"),
                "source_provenance": effort_freeze.get("source_provenance"),
            },
        },
    }


def validate_capability_source_freeze(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping) or payload.get("schema") != CAPABILITY_SOURCE_FREEZE_SCHEMA:
        raise ValueError("capability-source freeze must use the registered v1 schema")
    expected_keys = {
        "schema",
        "status",
        "purpose",
        "source_cell_id",
        "source_geometry_id",
        "selection_basis",
        "selected_effort_nm",
        "effort_profile",
        "confirmed_E2",
        "requested_params",
        "native_params",
        "canonical_geometry",
        "shared_local_kinematic_facts",
        "source_paths",
        "source_provenance",
    }
    if set(payload) != expected_keys:
        raise ValueError("capability-source freeze fields do not match the emitted artifact contract")
    if (
        payload.get("status") != "CAPABILITY_SOURCE_FROZEN"
        or payload.get("purpose") != D1_CAPABILITY_SOURCE
        or payload.get("source_cell_id") != CAPABILITY_SOURCE_CELL_ID
        or payload.get("selection_basis") != CAPABILITY_SOURCE_BASIS
        or payload.get("selected_effort_nm") != CAPABILITY_SOURCE_EFFORT_NM
        or payload.get("confirmed_E2") is not False
    ):
        raise ValueError("capability-source freeze status/source identity is invalid")
    if payload.get("effort_profile") != {"effort_nm": 40.0, "name": "base_v23_p0_effort_40"}:
        raise ValueError("capability-source freeze effort profile is invalid")
    if payload.get("requested_params") != CAPABILITY_SOURCE_REQUESTED_PARAMS:
        raise ValueError("capability-source freeze requested parameters are invalid")
    if payload.get("native_params") != CAPABILITY_SOURCE_NATIVE_PARAMS:
        raise ValueError("capability-source freeze native parameters are invalid")
    canonical = payload.get("canonical_geometry")
    if not isinstance(canonical, Mapping):
        raise ValueError("capability-source freeze canonical geometry is missing")
    try:
        from .p0_door_atlas_probe import validate_canonical_geometry_record
    except ImportError:
        from scriptsFORhuman.v23.p0_door_atlas_probe import validate_canonical_geometry_record
    canonical_expected = validate_canonical_geometry_record(
        canonical,
        cell_id=CAPABILITY_SOURCE_CELL_ID,
        realized_params={
            "hinge_damping_native": CAPABILITY_SOURCE_NATIVE_PARAMS["hinge_damping_native"],
            "hinge_stiffness_native": CAPABILITY_SOURCE_NATIVE_PARAMS["hinge_stiffness_native"],
            "hinge_effort_limit_nm": CAPABILITY_SOURCE_NATIVE_PARAMS["hinge_effort_limit_nm"],
            "door_weight_kg": CAPABILITY_SOURCE_NATIVE_PARAMS["door_weight_kg"],
        },
    )
    if canonical != canonical_expected or payload.get("source_geometry_id") != canonical_expected["geometry_id"]:
        raise ValueError("capability-source freeze canonical geometry identity is invalid")
    shared = payload.get("shared_local_kinematic_facts")
    if not isinstance(shared, Mapping) or dict(shared) != _local_kinematic_signature(canonical_expected):
        raise ValueError("capability-source freeze shared local kinematic facts are invalid")
    source_paths = payload.get("source_paths")
    if not isinstance(source_paths, Mapping) or set(source_paths) != {"atlas", "external_threshold", "effort_freeze"}:
        raise ValueError("capability-source freeze source paths are invalid")
    if any(not isinstance(value, str) or not value for value in source_paths.values()):
        raise ValueError("capability-source freeze source paths must be non-empty strings")
    provenance = payload.get("source_provenance")
    if not isinstance(provenance, Mapping) or set(provenance) != {"atlas", "external_threshold", "effort_freeze"}:
        raise ValueError("capability-source freeze source provenance is invalid")
    external_provenance = provenance.get("external_threshold")
    if (
        not isinstance(external_provenance, Mapping)
        or external_provenance.get("schema") != "a2_piper_v23_door_external_torque_threshold_v1"
        or external_provenance.get("status") != "MEASURED_RAW"
        or external_provenance.get("row_count") != len(ATLAS_CELLS) * 2 * 10
        or not isinstance(external_provenance.get("probe_contract"), Mapping)
    ):
        raise ValueError("capability-source freeze external provenance is invalid")
    return dict(payload)


def _external_rows(payload: Mapping[str, Any]) -> tuple[dict[str, Any], list[Mapping[str, Any]]]:
    if not isinstance(payload, Mapping):
        raise ValueError("external threshold input must be an object")
    if payload.get("schema") != "a2_piper_v23_door_external_torque_threshold_v1" or payload.get("status") != "MEASURED_RAW":
        raise ValueError("external threshold input must be the measured A0-A8 raw schema")
    contract = payload.get("probe_contract")
    if (
        not isinstance(contract, Mapping)
        or contract.get("physics_steps_per_trial") != 100
        or contract.get("dt_s") != 0.005
        or contract.get("door_joint_effort_target") != 0.0
        or contract.get("settle_steps") != 1
        or contract.get("composer") != "Articulation.permanent_wrench_composer"
        or contract.get("wrench_frame") != "GLOBAL"
    ):
        raise ValueError("external input must preserve dt=.005, 100 frames, zero hinge effort target")
    rows = payload.get("rows")
    if not isinstance(rows, list) or len(rows) != 9 * 2 * 10:
        raise ValueError("external input must contain exactly 9 cells x 2 signs x 10 magnitudes")
    try:
        from .p0_door_atlas_probe import validate_canonical_geometry_record
    except ImportError:
        from scriptsFORhuman.v23.p0_door_atlas_probe import validate_canonical_geometry_record
    normalized_rows: list[Mapping[str, Any]] = []
    required_row_fields = {
        "cell_id",
        "geometry_id",
        "canonical_geometry",
        "realized_params",
        "sign",
        "magnitude_nm",
        "q0_rad",
        "q_trace_rad",
        "raw_q_trace_rad",
        "signed_progress_trace_rad",
        "max_progress_rad",
        "reset_closed",
        "settle_steps",
        "composer_reset_before_trial",
        "physics_frames",
        "dt_s",
        "door_joint_effort_target",
    }
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise ValueError(f"external row {index} is not an object")
        if not required_row_fields.issubset(set(row)):
            raise ValueError(f"external row {index} fields do not match the exact trial schema")
        if row.get("cell_id") not in ATLAS_CELLS or not isinstance(row.get("geometry_id"), str) or not row.get("geometry_id"):
            raise ValueError(f"external row {index} lacks registered cell_id/geometry_id")
        if (
            row.get("physics_frames") != 100
            or row.get("dt_s") != 0.005
            or row.get("door_joint_effort_target") != 0.0
            or row.get("sign") not in (-1, 1)
            or row.get("reset_closed") is not True
            or row.get("settle_steps") != 1
            or row.get("composer_reset_before_trial") is not True
        ):
            raise ValueError(f"external row {index} violates the exact trial contract")
        canonical = row.get("canonical_geometry")
        realized = row.get("realized_params")
        if not isinstance(canonical, Mapping) or not isinstance(realized, Mapping):
            raise ValueError(f"external row {index} lacks canonical realized geometry")
        try:
            canonical_expected = validate_canonical_geometry_record(
                canonical, cell_id=row["cell_id"], realized_params=realized
            )
        except (ValueError, RuntimeError) as exc:
            raise ValueError(f"external row {index} canonical geometry is invalid") from exc
        if row["geometry_id"] != canonical_expected["geometry_id"]:
            raise ValueError(f"external row {index} geometry_id does not match canonical geometry")
        q0 = row.get("q0_rad")
        q_trace = row.get("q_trace_rad")
        raw_q = row.get("raw_q_trace_rad")
        signed = row.get("signed_progress_trace_rad")
        max_progress = row.get("max_progress_rad")
        if (
            isinstance(q0, bool)
            or not isinstance(q0, (int, float))
            or not isinstance(q_trace, list)
            or not isinstance(raw_q, list)
            or q_trace != raw_q
            or len(q_trace) != 100
            or not isinstance(signed, list)
            or len(signed) != 100
            or isinstance(max_progress, bool)
            or not isinstance(max_progress, (int, float))
        ):
            raise ValueError(f"external row {index} must preserve q0 and exactly 100 raw/signed samples")
        if any(
            isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value))
            for value in [q0, max_progress, *q_trace, *signed]
        ):
            raise ValueError(f"external row {index} contains non-finite traces")
        recomputed_signed = [float(row["sign"]) * (float(value) - float(q0)) for value in q_trace]
        recomputed_max = max(0.0, *recomputed_signed)
        if any(
            not math.isclose(float(stored), float(expected), rel_tol=1.0e-9, abs_tol=1.0e-9)
            for stored, expected in zip(signed, recomputed_signed)
        ) or not math.isclose(float(max_progress), recomputed_max, rel_tol=1.0e-9, abs_tol=1.0e-9):
            raise ValueError(f"external row {index} stored progress disagrees with recomputed q0/sign trace")
        normalized_rows.append(
            {
                **dict(row),
                "canonical_geometry": canonical_expected,
                "realized_params": dict(canonical_expected["realized_params"]),
                "q_trace_rad": [float(value) for value in q_trace],
                "raw_q_trace_rad": [float(value) for value in q_trace],
                "signed_progress_trace_rad": recomputed_signed,
                "max_progress_rad": recomputed_max,
            }
        )
    return dict(payload), normalized_rows


def _stable_p05_window(rows: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)) or len(rows) < 25:
        raise ValueError("P0.5 raw rows require at least 25 control steps")
    ordered = sorted(rows, key=lambda row: row.get("control_step", -1))
    for start in range(len(ordered) - 24):
        window = ordered[start : start + 25]
        steps = [row.get("control_step") for row in window]
        if steps != list(range(steps[0], steps[0] + 25)):
            continue
        if not all(bool(row.get("stable_grasp")) for row in window):
            continue
        if any(any(bool(flag) for flag in (row.get("failure_flags") or {}).values()) for row in window):
            continue
        return window
    raise ValueError("no stable failure-free 25-control-step P0.5 window")


def _mode_records(
    payload: Mapping[str, Any],
    *,
    mode: str,
    allow_incomplete: bool = False,
) -> tuple[list[Mapping[str, Any]], dict[tuple[Any, ...], Mapping[str, Any]]]:
    if not isinstance(payload, Mapping):
        raise ValueError(f"{mode} input must be an object")
    if payload.get("schema") != P05_EXPORT_SCHEMA:
        raise ValueError(f"{mode} input must use the registered P0.5 episode export schema")
    records = payload.get("records")
    if not isinstance(records, list) or (len(records) > 16) or (not allow_incomplete and len(records) != 16):
        raise ValueError(
            f"{mode} input must contain exactly 16 episode records"
            if not allow_incomplete
            else f"{mode} input must contain at most 16 episode records"
        )
    by_identity: dict[tuple[Any, ...], Mapping[str, Any]] = {}
    env_ids = []
    for index, record in enumerate(records):
        if not isinstance(record, Mapping) or record.get("schema") != P05_EPISODE_SCHEMA or record.get("mode") != mode:
            raise ValueError(f"{mode} record {index} schema/mode mismatch")
        rows = record.get("step_rows")
        if not isinstance(rows, list) or not rows:
            raise ValueError(f"{mode} record {index} has no raw step_rows")
        first = rows[0]
        identity_fields = (
            "checkpoint",
            "config",
            "scenario",
            "topology",
            "seed",
            "episode_id",
            "plain_prefix_id",
            "checkpoint_load_mode",
            "cell_id",
            "geometry_id",
            "env_id",
            "episode_index",
        )
        if any(key not in first for key in identity_fields):
            raise ValueError(f"{mode} record {index} identity/provenance is incomplete")
        if (
            first.get("checkpoint_load_mode") != "policy_only"
            or not isinstance(first.get("canonical_geometry"), Mapping)
            or not isinstance(record.get("canonical_geometry"), Mapping)
        ):
            raise ValueError(f"{mode} record {index} requires exact policy_only/canonical geometry provenance")
        identity = tuple(first[key] for key in identity_fields)
        if identity in by_identity:
            raise ValueError(f"duplicate {mode} provenance identity")
        for row in rows:
            if not isinstance(row, Mapping) or row.get("schema") != P05_STEP_SCHEMA or tuple(row.get(key) for key in identity_fields) != identity:
                raise ValueError(f"{mode} record {index} step provenance/schema mismatch")
        env_id = first["env_id"]
        if isinstance(env_id, bool) or not isinstance(env_id, int) or env_id in env_ids or not 0 <= env_id < 16:
            raise ValueError(f"{mode} env ids must be exactly 0..15 once each")
        env_ids.append(env_id)
        by_identity[identity] = record
    if not allow_incomplete and set(env_ids) != set(range(16)):
        raise ValueError(f"{mode} env ids must be exactly 0..15 once each")
    return records, by_identity


class _D1CapabilitySourceIncomplete(Exception):
    """Typed stop state for valid-but-incomplete D1 source evidence."""

    def __init__(self, receipt: Mapping[str, Any]):
        super().__init__("D1 capability-source evidence is incomplete")
        self.receipt = dict(receipt)


def _d1_record_env_id(record: Mapping[str, Any]) -> int:
    rows = record.get("step_rows")
    if not isinstance(rows, list) or not rows or not isinstance(rows[0], Mapping):
        raise ValueError("D1 record step_rows must expose a first provenance row")
    env_id = rows[0].get("env_id")
    if isinstance(env_id, bool) or not isinstance(env_id, int) or not 0 <= env_id < 16:
        raise ValueError("D1 record env_id must be within 0..15")
    return env_id


def _d1_record_identity(record: Mapping[str, Any]) -> tuple[Any, ...]:
    rows = record.get("step_rows")
    if not isinstance(rows, list) or not rows or not isinstance(rows[0], Mapping):
        raise ValueError("D1 record step_rows must expose a first provenance row")
    first = rows[0]
    fields = (
        "checkpoint",
        "config",
        "scenario",
        "topology",
        "seed",
        "episode_id",
        "plain_prefix_id",
        "checkpoint_load_mode",
        "cell_id",
        "geometry_id",
        "env_id",
        "episode_index",
    )
    return tuple(first[field] for field in fields)


def _d1_validate_mode_records(
    payload: Mapping[str, Any],
    *,
    mode: str,
    source_freeze: Mapping[str, Any],
) -> tuple[
    list[Mapping[str, Any]],
    dict[tuple[Any, ...], Mapping[str, Any]],
    dict[str, Any],
    dict[int, list[Mapping[str, Any]]],
]:
    """Validate D1 provenance, retaining only a typed incomplete diagnostic."""

    records, by_identity = _mode_records(payload, mode=mode, allow_incomplete=True)
    source_geometry = source_freeze["canonical_geometry"]
    source_realized = {
        "hinge_damping_native": source_freeze["native_params"]["hinge_damping_native"],
        "hinge_stiffness_native": source_freeze["native_params"]["hinge_stiffness_native"],
        "hinge_effort_limit_nm": source_freeze["native_params"]["hinge_effort_limit_nm"],
        "door_weight_kg": source_freeze["native_params"]["door_weight_kg"],
    }
    provided_env_ids: list[int] = []
    valid_env_ids: list[int] = []
    no_window_env_ids: list[int] = []
    windows_by_env: dict[int, list[Mapping[str, Any]]] = {}
    for index, record in enumerate(records):
        if record.get("purpose") != D1_CAPABILITY_SOURCE:
            raise ValueError(f"{mode} record {index} requires purpose={D1_CAPABILITY_SOURCE}")
        if (
            record.get("cell_id") != CAPABILITY_SOURCE_CELL_ID
            or record.get("geometry_id") != source_freeze["source_geometry_id"]
            or record.get("canonical_geometry") != source_geometry
            or record.get("state_clone_supported") is not False
            or record.get("forward_only") is not True
        ):
            raise ValueError(f"{mode} record {index} must use the exact A0 forward-only provenance")
        env_id = _d1_record_env_id(record)
        provided_env_ids.append(env_id)
        rows = record["step_rows"]
        for row_index, row in enumerate(rows):
            if row.get("purpose") != D1_CAPABILITY_SOURCE:
                raise ValueError(f"{mode} record {index} step row {row_index} purpose is invalid")
            if row.get("state_clone_supported") is not False or row.get("forward_only") is not True:
                raise ValueError(f"{mode} record {index} step row {row_index} violates forward-only provenance")
            capability = row.get("capability_sample")
            if (
                not isinstance(capability, Mapping)
                or capability.get("schema") != CAPABILITY_SAMPLE_SCHEMA
                or capability.get("cell_id") != CAPABILITY_SOURCE_CELL_ID
                or capability.get("geometry_id") != source_freeze["source_geometry_id"]
                or capability.get("canonical_geometry") != source_geometry
                or capability.get("realized_params") != source_realized
                or capability.get("checkpoint_load_mode") != "policy_only"
                or capability.get("status") not in ("VALID", "INFEASIBLE", "UNBOUNDED")
            ):
                raise ValueError(f"{mode} record {index} step row {row_index} capability provenance is invalid")
            capacity = capability.get("capacity_nm")
            if capacity is not None and (
                isinstance(capacity, bool)
                or not isinstance(capacity, (int, float))
                or not math.isfinite(float(capacity))
            ):
                raise ValueError(f"{mode} record {index} step row {row_index} capacity is non-finite")
            if capability.get("status") == "VALID" and capacity is None:
                raise ValueError(f"{mode} record {index} step row {row_index} VALID capacity is missing")
        try:
            window = _stable_p05_window(rows)
        except ValueError:
            no_window_env_ids.append(env_id)
            continue
        if any(row["capability_sample"].get("status") != "VALID" for row in window):
            no_window_env_ids.append(env_id)
            continue
        valid_env_ids.append(env_id)
        windows_by_env[env_id] = window
    provided_env_ids.sort()
    valid_env_ids.sort()
    no_window_env_ids.sort()
    missing_env_ids = sorted(set(range(16)) - set(provided_env_ids))
    reasons: list[str] = []
    if missing_env_ids:
        reasons.append("MISSING_REQUIRED_ENV_COVERAGE")
    if no_window_env_ids:
        reasons.append("NO_STABLE_FAILURE_FREE_25_STEP_WINDOW")
    diagnostic = {
        "provided_env_ids": provided_env_ids,
        "valid_env_ids": valid_env_ids,
        "missing_env_ids": missing_env_ids,
        "no_window_env_ids": no_window_env_ids,
        "reasons": reasons,
    }
    return records, by_identity, diagnostic, windows_by_env


def _d1_incomplete_receipt(
    *,
    source_freeze: Mapping[str, Any],
    selected_freeze: Mapping[str, Any],
    effort_freeze: Mapping[str, Any],
    external: Mapping[str, Any],
    mode_diagnostics: Mapping[str, Any],
    input_paths: Mapping[str, str] | None,
) -> dict[str, Any]:
    reasons = [
        f"{mode}:{reason}"
        for mode, diagnostic in mode_diagnostics.items()
        for reason in diagnostic.get("reasons", [])
    ]
    fallback_paths = {
        "atlas": source_freeze["source_paths"].get("atlas"),
        "external_threshold": source_freeze["source_paths"].get("external_threshold"),
        "effort_freeze": source_freeze["source_paths"].get("effort_freeze"),
        "selected_cell_freeze": None,
        "capability_source_freeze": None,
    }
    resolved_paths = dict(fallback_paths)
    if input_paths is not None:
        resolved_paths.update({str(key): str(value) for key, value in input_paths.items()})
    return {
        "schema": D1_INCOMPLETE_SCHEMA,
        "status": "D1_CAPABILITY_SOURCE_INCOMPLETE",
        "purpose": D1_CAPABILITY_SOURCE,
        "source_cell_id": CAPABILITY_SOURCE_CELL_ID,
        "selected_effort_nm": CAPABILITY_SOURCE_EFFORT_NM,
        "required_env_count": 16,
        "mode_diagnostics": {str(mode): dict(diagnostic) for mode, diagnostic in mode_diagnostics.items()},
        "reasons": reasons,
        "source_freeze": dict(source_freeze),
        "selected_cell_freeze": dict(selected_freeze),
        "input_paths": resolved_paths,
        "source_provenance": {
            "capability_source_freeze": source_freeze.get("source_provenance"),
            "selected_cell_freeze": selected_freeze.get("source_provenance"),
            "effort_freeze": {
                "schema": effort_freeze.get("schema"),
                "status": effort_freeze.get("status"),
                "selection_outcome": effort_freeze.get("selection_outcome"),
                "source_provenance": effort_freeze.get("source_provenance"),
            },
            "external_threshold": {
                "schema": external.get("schema"),
                "status": external.get("status"),
                "source_identity": external.get("source_identity"),
                "probe_contract": external.get("probe_contract"),
                "row_count": len(external.get("rows", [])) if isinstance(external.get("rows"), list) else None,
            },
        },
        "d1_freeze_written": False,
    }


def reduce_d1_freeze(
    *,
    external_threshold: Mapping[str, Any],
    full_input: Mapping[str, Any],
    acute_input: Mapping[str, Any],
    effort_freeze: Mapping[str, Any],
    selected_cell_freeze: Mapping[str, Any],
    capability_source_freeze: Mapping[str, Any],
    input_paths: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Reduce exact16 A0 FULL-primary/ACUTE-auxiliary capability records."""
    external, external_rows = _external_rows(external_threshold)
    selected_effort = _validate_effort_freeze_payload(effort_freeze)
    selected_freeze = validate_selected_cell_freeze(selected_cell_freeze)
    source_freeze = validate_capability_source_freeze(capability_source_freeze)
    if selected_freeze.get("selected_effort_nm") != selected_effort:
        raise ValueError("selected-cell freeze and effort freeze selected efforts must match exactly")
    if source_freeze.get("selected_effort_nm") != selected_effort:
        raise ValueError("capability-source freeze and effort freeze selected efforts must match exactly")
    full_records, full_by_identity, full_diagnostic, full_windows = _d1_validate_mode_records(
        full_input,
        mode="FULL",
        source_freeze=source_freeze,
    )
    acute_records, acute_by_identity, acute_diagnostic, acute_windows = _d1_validate_mode_records(
        acute_input,
        mode="ACUTE_RP0",
        source_freeze=source_freeze,
    )
    full_by_env = {_d1_record_env_id(record): record for record in full_records}
    acute_by_env = {_d1_record_env_id(record): record for record in acute_records}
    for env_id in sorted(set(full_by_env) & set(acute_by_env)):
        if _d1_record_identity(full_by_env[env_id]) != _d1_record_identity(acute_by_env[env_id]):
            raise ValueError(f"FULL and ACUTE_RP0 provenance identity mismatch for env{env_id}")
    mode_diagnostics = {"FULL": full_diagnostic, "ACUTE_RP0": acute_diagnostic}
    if any(
        diagnostic["missing_env_ids"] or diagnostic["no_window_env_ids"]
        for diagnostic in mode_diagnostics.values()
    ):
        raise _D1CapabilitySourceIncomplete(
            _d1_incomplete_receipt(
                source_freeze=source_freeze,
                selected_freeze=selected_freeze,
                effort_freeze=effort_freeze,
                external=external,
                mode_diagnostics=mode_diagnostics,
                input_paths=input_paths,
            )
        )
    atlas_rows = selected_freeze["atlas_rows"]
    atlas_by_cell = {row["cell_id"]: row for row in atlas_rows}
    external_by_cell = _external_by_cell(external_rows)
    for cell_id in ATLAS_CELLS:
        atlas_row = atlas_by_cell[cell_id]
        external_cell = external_by_cell[cell_id]
        if (
            atlas_row["geometry_id"] != external_cell["geometry_id"]
            or atlas_row["canonical_geometry"] != external_cell["canonical_geometry"]
            or atlas_row["realized_params"] != external_cell["realized_params"]
        ):
            raise ValueError(f"selected freeze and external cell {cell_id} geometry identities disagree")
    source_geometry = source_freeze["canonical_geometry"]
    source_realized = {
        "hinge_damping_native": source_freeze["native_params"]["hinge_damping_native"],
        "hinge_stiffness_native": source_freeze["native_params"]["hinge_stiffness_native"],
        "hinge_effort_limit_nm": source_freeze["native_params"]["hinge_effort_limit_nm"],
        "door_weight_kg": source_freeze["native_params"]["door_weight_kg"],
    }
    mode_capacity_by_mode: dict[str, float] = {}
    mode_windows = {"FULL": full_windows, "ACUTE_RP0": acute_windows}
    for mode, records in (("FULL", full_records), ("ACUTE_RP0", acute_records)):
        env_capacity_mins: list[float] = []
        for record in records:
            env_id = _d1_record_env_id(record)
            window = mode_windows[mode][env_id]
            samples = [row.get("capability_sample") for row in window]
            capacities = []
            for sample in samples:
                if sample.get("status") != "VALID":
                    raise ValueError(f"{mode} capability window contains non-VALID capacity")
                capacities.append(float(sample["capacity_nm"]))
            env_capacity_mins.append(min(capacities))
        if len(env_capacity_mins) != 16:
            raise ValueError(f"{mode} D1 reduction requires exactly 16 valid env windows")
        mode_capacity_by_mode[mode] = min(env_capacity_mins)
    try:
        from .p0_door_atlas_probe import classify_directional_opening_bracket
    except ImportError:
        from scriptsFORhuman.v23.p0_door_atlas_probe import classify_directional_opening_bracket
    directional = classify_directional_opening_bracket(external_rows)
    by_cell_external: dict[str, dict[str, Any]] = {}
    for cell_id in ATLAS_CELLS:
        cell_bracket = directional["cells"][cell_id]
        by_cell_external[cell_id] = {
            **cell_bracket,
            "cell_id": cell_id,
            "geometry_id": external_by_cell[cell_id]["geometry_id"],
            "canonical_geometry": external_by_cell[cell_id]["canonical_geometry"],
            "realized_params": external_by_cell[cell_id]["realized_params"],
        }
    full_capacity = mode_capacity_by_mode["FULL"]
    acute_capacity = mode_capacity_by_mode["ACUTE_RP0"]
    zones = []
    for cell_id in ATLAS_CELLS:
        external_cell = by_cell_external.get(cell_id)
        target_identity = {
            "cell_id": cell_id,
            "geometry_id": None if not external_cell else external_cell.get("geometry_id"),
            "canonical_geometry": None if not external_cell else external_cell.get("canonical_geometry"),
            "realized_params": None if not external_cell else external_cell.get("realized_params"),
            "opening_bracket": None if not external_cell else external_cell.get("opening_bracket"),
            "negative_censor": None if not external_cell else external_cell.get("negative_censor"),
        }
        transfer = {
            "capacity_source_cell_id": CAPABILITY_SOURCE_CELL_ID,
            "capacity_source_geometry_id": source_freeze["source_geometry_id"],
            "capacity_transfer_basis": CAPACITY_TRANSFER_BASIS,
            "shared_local_kinematic_facts": source_freeze["shared_local_kinematic_facts"],
            "authority": CAPABILITY_AUTHORITY,
        }
        if not external_cell:
            raise ValueError(f"D1 reduction requires external directional evidence for {cell_id}")
        opening = external_cell.get("opening_bracket")
        if not isinstance(opening, Mapping) or opening.get("status") != "VALID_BRACKET":
            raise ValueError(f"D1 reduction requires a valid directional opening bracket for {cell_id}")
        lower = float(opening["lower_nm"])
        upper = float(opening["upper_nm"])
        if not lower < upper:
            raise ValueError(f"D1 reduction requires a finite ordered bracket for {cell_id}")
        if full_capacity >= upper:
            zone_name = "E0" if acute_capacity >= upper else "E1"
        elif lower < full_capacity < upper:
            zone_name = "nearE2"
        elif full_capacity <= lower:
            zone_name = "E2_CANDIDATE_UNCONFIRMED"
        else:
            raise ValueError(f"D1 reduction capacity classification is undefined for {cell_id}")
        zones.append({
            "cell_id": cell_id,
            "geometry_id": external_cell["geometry_id"],
            "status": "OBSERVED",
            "target_external_identity": target_identity,
            **transfer,
            "zone": zone_name,
            "confirmed_E2": False,
            "lower_nm": lower,
            "upper_nm": upper,
            "capacity_full_nm": full_capacity,
            "capacity_acute_rp0_nm": acute_capacity,
            "capacity_best_nm": full_capacity,
            "authority": CAPABILITY_AUTHORITY,
        })
    valid_cells = [row for row in zones if row.get("status") == "OBSERVED" and row.get("zone") in ("E0", "E1", "nearE2")]
    f2_candidates = [
        row for row in zones
        if row.get("status") == "OBSERVED"
        and float(row["upper_nm"]) <= min(float(row["capacity_full_nm"]), float(row["capacity_acute_rp0_nm"]))
    ]
    if not f2_candidates:
        d1_status = "NO_D1"
        no_d1_reason = "H4"
        f2 = {"status": "NO_D1", "reason": "H4", "S": [], "U_star_nm": None, "M": [], "premark": "H4"}
        d1_lite_cells: list[str] = []
    else:
        u_star = max(float(row["upper_nm"]) for row in f2_candidates)
        tied = [row["cell_id"] for row in f2_candidates if float(row["upper_nm"]) == u_star]
        f2 = {"status": "F2_100", "S": [row["cell_id"] for row in f2_candidates], "U_star_nm": u_star, "M": tied, "sample_rule": "uniform_all_tied_max_U", "premark": "H4"}
        d1_status = "READY"
        no_d1_reason = None
        d1_lite_cells = list(tied)
    if f2.get("status") != "F2_100":
        d1_lite_cells = [row["cell_id"] for row in valid_cells]
    return {
        "schema": D1_FREEZE_SCHEMA,
        "status": d1_status,
        "purpose": D1_CAPABILITY_SOURCE,
        "selected_effort_nm": float(selected_effort),
        "selected_cell_freeze": {
            "schema": selected_freeze["schema"],
            "status": selected_freeze["status"],
            "selected_cell_id": selected_freeze["selected_cell_id"],
            "source_paths": selected_freeze.get("source_paths"),
        },
        "zones": zones,
        "confirmed_E2": False,
        "capacity_sources": {
            "source_cell_id": CAPABILITY_SOURCE_CELL_ID,
            "source_geometry_id": source_freeze["source_geometry_id"],
            "FULL": {"env_count": 16, "capacity_nm": full_capacity, "window_steps": 25, "primary": True},
            "ACUTE_RP0": {"env_count": 16, "capacity_nm": acute_capacity, "window_steps": 25, "primary": False},
        },
        "classification_hierarchy": {
            "primary": "FULL",
            "auxiliary": "ACUTE_RP0",
            "rule": "FULL>=U and ACUTE>=U -> E0; FULL>=U and ACUTE<U -> E1; L<FULL<U -> nearE2; FULL<=L -> E2_CANDIDATE_UNCONFIRMED",
            "acute_never_promotes": True,
            "confirmed_E2": False,
        },
        "f2_100": f2,
        "d1": {"status": d1_status, "schedule": "100/0/0 -> 60/40/0 -> 30/60/10", "uniform_zones": True, "zones": ([row["cell_id"] for row in valid_cells] if d1_status == "READY" else []), "reason": no_d1_reason},
        "d1_lite": {"status": d1_status if d1_status == "READY" else "NO_D1", "schedule": "100/0/0 -> 65/35/0 -> 40/55/5", "uniform_zones": True, "zones": d1_lite_cells, "reason": no_d1_reason, "candidate_rule": "F2_100_M_MAX_U_TIES_ONLY" if f2.get("status") == "F2_100" else "NORMAL_VALID_E_ZONES"},
        "external_bracket": directional,
        "preserved_bilateral_bracket": external.get("bracket"),
        "capacity_source_cell_id": CAPABILITY_SOURCE_CELL_ID,
        "capacity_source_geometry_id": source_freeze["source_geometry_id"],
        "capacity_transfer_basis": CAPACITY_TRANSFER_BASIS,
        "shared_local_kinematic_facts": source_freeze["shared_local_kinematic_facts"],
        "capability_authority": CAPABILITY_AUTHORITY,
        "rollout_success_not_classifier": True,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    select_parser = subparsers.add_parser("select-cell", help="freeze the explicit directional A8 opening cell")
    select_parser.add_argument("--atlas-input", type=Path, required=True)
    select_parser.add_argument("--external-threshold", type=Path, required=True)
    select_parser.add_argument("--effort-freeze", type=Path, required=True)
    select_parser.add_argument("--selected-cell", required=True)
    select_parser.add_argument("--out", type=Path, required=True)
    source_parser = subparsers.add_parser(
        "select-capability-source", help="freeze the exact current-easy A0 D1 capability source"
    )
    source_parser.add_argument("--atlas-input", type=Path, required=True)
    source_parser.add_argument("--external-threshold", type=Path, required=True)
    source_parser.add_argument("--effort-freeze", type=Path, required=True)
    source_parser.add_argument("--source-cell", required=True)
    source_parser.add_argument("--out", type=Path, required=True)
    reduce_parser = subparsers.add_parser("reduce", help="join registered external/FULL/ACUTE raw artifacts")
    reduce_parser.add_argument("--external-threshold", type=Path, required=True)
    reduce_parser.add_argument("--full-input", type=Path, required=True)
    reduce_parser.add_argument("--acute-input", type=Path, required=True)
    reduce_parser.add_argument("--effort-freeze", type=Path, required=True)
    reduce_parser.add_argument("--selected-cell-freeze", type=Path, required=True)
    reduce_parser.add_argument("--capability-source-freeze", type=Path, required=True)
    reduce_parser.add_argument("--out", type=Path, required=True)
    reduce_parser.add_argument("--incomplete-out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "select-cell":
        payload = build_selected_cell_freeze(
            atlas_input=_read_json(args.atlas_input),
            external_threshold=_read_json(args.external_threshold),
            effort_freeze=_read_json(args.effort_freeze),
            selected_cell=args.selected_cell,
            source_paths={
                "atlas": str(args.atlas_input.expanduser().resolve()),
                "external_threshold": str(args.external_threshold.expanduser().resolve()),
                "effort_freeze": str(args.effort_freeze.expanduser().resolve()),
            },
        )
    elif args.command == "select-capability-source":
        payload = build_capability_source_freeze(
            atlas_input=_read_json(args.atlas_input),
            external_threshold=_read_json(args.external_threshold),
            effort_freeze=_read_json(args.effort_freeze),
            source_cell=args.source_cell,
            source_paths={
                "atlas": str(args.atlas_input.expanduser().resolve()),
                "external_threshold": str(args.external_threshold.expanduser().resolve()),
                "effort_freeze": str(args.effort_freeze.expanduser().resolve()),
            },
        )
    elif args.command == "reduce":
        if args.out.expanduser().resolve() == args.incomplete_out.expanduser().resolve():
            raise ValueError("--out and --incomplete-out must be distinct paths")
        if args.out.exists() or args.incomplete_out.exists():
            raise ValueError("reduce output paths must not pre-exist")
        try:
            payload = reduce_d1_freeze(
                external_threshold=_read_json(args.external_threshold),
                full_input=_read_json(args.full_input),
                acute_input=_read_json(args.acute_input),
                effort_freeze=_read_json(args.effort_freeze),
                selected_cell_freeze=_read_json(args.selected_cell_freeze),
                capability_source_freeze=_read_json(args.capability_source_freeze),
                input_paths={
                    "external_threshold": str(args.external_threshold.expanduser().resolve()),
                    "full_input": str(args.full_input.expanduser().resolve()),
                    "acute_input": str(args.acute_input.expanduser().resolve()),
                    "effort_freeze": str(args.effort_freeze.expanduser().resolve()),
                    "selected_cell_freeze": str(args.selected_cell_freeze.expanduser().resolve()),
                    "capability_source_freeze": str(args.capability_source_freeze.expanduser().resolve()),
                },
            )
        except _D1CapabilitySourceIncomplete as incomplete:
            args.incomplete_out.parent.mkdir(parents=True, exist_ok=True)
            args.incomplete_out.write_text(
                json.dumps(incomplete.receipt, indent=2, sort_keys=True, allow_nan=False) + "\n",
                encoding="utf-8",
            )
            return 2
        args.out.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
        return 0
    else:
        raise ValueError("unsupported capability command")
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, RuntimeError) as exc:
        raise SystemExit(f"V23 CAPABILITY REDUCE FAIL: {exc}")
