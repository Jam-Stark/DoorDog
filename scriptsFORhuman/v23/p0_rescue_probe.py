"""Forward-only P0.5 rescue producer and launch-plan contract.

The module has a CPU-only planning path.  A RUN plan is deliberately
non-launchable until a measured effort freeze, an atlas manifest, and the
explicit P0.5 bands are supplied.  The optional execution path only launches
the normal evaluator with the frozen step-1250 warm checkpoint; it never
clones simulator state or fabricates provenance.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from ._v23_common import (
        REPO_ROOT,
        V23_WARM_START_CONFIG,
        V23_WARM_START_PATH,
        V23_EFFORT_RUNGS,
        V23Error,
        artifact_payload,
        emit_payload,
        finite_number,
        read_json,
        require_file,
    )
except ImportError:  # direct script invocation
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from scriptsFORhuman.v23._v23_common import (
        REPO_ROOT,
        V23_WARM_START_CONFIG,
        V23_WARM_START_PATH,
        V23_EFFORT_RUNGS,
        V23Error,
        artifact_payload,
        emit_payload,
        finite_number,
        read_json,
        require_file,
    )

from gr00t.rl.envs.door.a2_v23_evidence import (
    V23_P05_PURPOSES,
    V23_P05_MODES,
    a2_v23_validate_p05_bands,
    a2_v23_validate_p05_prefix,
)
try:
    from .effort_ladder import EFFORT_FREEZE_SCHEMA, EFFORT_FREEZE_SELECTION_OUTCOMES
    from .p0_door_atlas_probe import validate_canonical_geometry_record
    from .capability_binding import (
        CAPABILITY_SOURCE_BASIS,
        CAPABILITY_SOURCE_CELL_ID,
        CAPABILITY_SOURCE_FREEZE_SCHEMA,
        CAPABILITY_SOURCE_NATIVE_PARAMS,
        CAPABILITY_SOURCE_REQUESTED_PARAMS,
        D1_CAPABILITY_SOURCE,
        P05_CERTIFICATE,
        SELECTED_CELL_FREEZE_SCHEMA,
        SELECTED_CELL_ID,
        _external_rows,
        validate_capability_source_freeze,
        validate_selected_cell_freeze,
    )
except ImportError:  # direct script invocation
    from scriptsFORhuman.v23.effort_ladder import EFFORT_FREEZE_SCHEMA, EFFORT_FREEZE_SELECTION_OUTCOMES
    from scriptsFORhuman.v23.p0_door_atlas_probe import validate_canonical_geometry_record
    from scriptsFORhuman.v23.capability_binding import (
        CAPABILITY_SOURCE_BASIS,
        CAPABILITY_SOURCE_CELL_ID,
        CAPABILITY_SOURCE_FREEZE_SCHEMA,
        CAPABILITY_SOURCE_NATIVE_PARAMS,
        CAPABILITY_SOURCE_REQUESTED_PARAMS,
        D1_CAPABILITY_SOURCE,
        P05_CERTIFICATE,
        SELECTED_CELL_FREEZE_SCHEMA,
        SELECTED_CELL_ID,
        _external_rows,
        validate_capability_source_freeze,
        validate_selected_cell_freeze,
    )
try:
    from .p0_runtime_eval import build_effort_limit_list
except ImportError:  # direct script invocation
    from scriptsFORhuman.v23.p0_runtime_eval import build_effort_limit_list


P05_PLAN_SCHEMA = "a2_piper_v23_p05_rescue_probe_plan_v1"
P05_TOPOLOGIES = ("canonical16", "heavy16")
P05_WARM_CHECKPOINT = V23_WARM_START_PATH
P05_PLAIN_MANIFEST_SCHEMA = "a2_piper_base_v23_p0_plain_scenario_manifest_v1"
P05_BOUND_PLAIN_MANIFEST_SCHEMA = "a2_piper_base_v23_p0_bound_plain16_manifest_v1"
P05_BOUND_PLAIN_SELECTOR_MODE = "v23_bound_plain16"
P05_BOUND_CANONICAL_GEOMETRY_SCHEMA = "a2_piper_v23_canonical_geometry_v1"
P05_BOUND_PLAIN_MANIFEST_FILENAME = "p05_bound_plain_scenario_manifest.json"
P05_PLAIN_SOURCE_FIELDS = {
    "scenario_id",
    "handle_height_m",
    "door_weight_kg",
    "hinge_force_nm",
}

P05_EPISODE_EXPORT_SCHEMA = "a2_piper_v23_episode_records_export_v1"
P05_BUNDLE_SCHEMA = "a2_piper_v23_p05_producer_bundle_v3"
P05_PAIR_EXPORT_SCHEMA = "a2_piper_v23_p05_pair_export_v3"
P05_REQUESTED_PARAMS_FIELDS = frozenset(
    {
        "hinge_damping_native",
        "hinge_stiffness_native",
        "hinge_max_force_nm",
        "door_weight_kg",
    }
)
P05_REALIZED_PARAMS_FIELDS = frozenset(
    {
        "hinge_damping_native",
        "hinge_stiffness_native",
        "hinge_effort_limit_nm",
        "door_weight_kg",
    }
)
P05_A8_REQUESTED_PARAMS = {
    "hinge_damping_native": 200.0,
    "hinge_stiffness_native": 30.0,
    "hinge_max_force_nm": 24.0,
    "door_weight_kg": 160.0,
}
P05_A8_REALIZED_PARAMS = {
    "hinge_damping_native": 11459.15625,
    "hinge_stiffness_native": 1718.8734130859375,
    "hinge_effort_limit_nm": 24.0,
    "door_weight_kg": 160.0,
}
P05_D1_BOUND_MANIFEST_SCHEMA = "a2_piper_base_v23_d1_capability_bound_plain16_manifest_v1"
P05_D1_BOUND_SELECTOR_MODE = "v23_d1_capability_source_plain16"
P05_D1_BOUND_MANIFEST_FILENAME = "d1_capability_bound_plain_scenario_manifest.json"
P05_D1_BOUND_CANONICAL_GEOMETRY_SCHEMA = "a2_piper_v23_canonical_geometry_v1"


def _hydra_string(value: str) -> str:
    """Serialize one Hydra string override and verify its exact round-trip."""

    if not isinstance(value, str) or not value:
        raise V23Error("Hydra string override requires a non-empty string")
    from hydra.core.override_parser.overrides_parser import OverridesParser
    from hydra.core.override_parser.types import Quote, QuotedString

    serialized = QuotedString(value, Quote.single).with_quotes()
    parsed = OverridesParser.create().parse_overrides([f"++__v23_geometry_id={serialized}"])
    if len(parsed) != 1 or parsed[0].value() != value:
        raise V23Error("Hydra geometry_id override failed the exact round-trip check")
    return serialized


def _validate_p05_a8_geometry_params(
    selected_geometry: Mapping[str, Any],
) -> tuple[dict[str, float], dict[str, float]]:
    requested = selected_geometry.get("requested_params")
    realized = selected_geometry.get("realized_params")
    if not isinstance(requested, Mapping) or set(requested) != P05_REQUESTED_PARAMS_FIELDS:
        raise V23Error("P0.5 A8 selected geometry requires exact requested spawn parameters")
    if not isinstance(realized, Mapping) or set(realized) != P05_REALIZED_PARAMS_FIELDS:
        raise V23Error("P0.5 A8 selected geometry requires exact native realized parameters")
    if dict(requested) != P05_A8_REQUESTED_PARAMS:
        raise V23Error("P0.5 A8 requested spawn parameters disagree with the measured selector")
    if dict(realized) != P05_A8_REALIZED_PARAMS:
        raise V23Error("P0.5 A8 native realized parameters disagree with the measured receipt")
    return dict(requested), dict(realized)


def _validate_p05_a0_geometry_params(
    selected_geometry: Mapping[str, Any],
) -> tuple[dict[str, float], dict[str, float]]:
    requested = selected_geometry.get("requested_params")
    realized = selected_geometry.get("realized_params")
    if not isinstance(requested, Mapping) or dict(requested) != CAPABILITY_SOURCE_REQUESTED_PARAMS:
        raise V23Error("D1 capability-source A0 geometry requires exact requested spawn parameters")
    if not isinstance(realized, Mapping) or dict(realized) != CAPABILITY_SOURCE_NATIVE_PARAMS:
        raise V23Error("D1 capability-source A0 geometry requires exact native realized parameters")
    return dict(requested), dict(realized)


def _episode_identity_key(record: Mapping[str, Any]) -> tuple[Any, ...]:
    required = (
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
    )
    missing = [key for key in required if key not in record]
    if missing:
        raise V23Error(f"episode identity is missing {missing!r}")
    if isinstance(record["seed"], bool) or not isinstance(record["seed"], int):
        raise V23Error("episode identity seed must be an integer")
    if record["checkpoint_load_mode"] != "policy_only":
        raise V23Error("episode checkpoint_load_mode must be policy_only")
    if any(
        not isinstance(record[key], str) or not record[key]
        for key in required
        if key != "seed"
    ):
        raise V23Error("episode identity fields must be non-empty strings")
    return tuple(record[key] for key in required)


def _episode_provenance(record: Mapping[str, Any]) -> tuple[int, int]:
    """Return the immutable env/episode coordinates carried by every row."""

    step_rows = record.get("step_rows")
    if not isinstance(step_rows, list) or not step_rows:
        raise V23Error("episode step_rows must be a non-empty list")
    first = step_rows[0]
    if not isinstance(first, Mapping):
        raise V23Error("episode first step row must be an object")
    env_id = first.get("env_id")
    episode_index = first.get("episode_index")
    if isinstance(env_id, bool) or not isinstance(env_id, int) or not 0 <= env_id < 16:
        raise V23Error("episode env_id must be within 0..15")
    if isinstance(episode_index, bool) or not isinstance(episode_index, int) or episode_index < 0:
        raise V23Error("episode episode_index must be a non-negative integer")
    for row_index, row in enumerate(step_rows):
        if not isinstance(row, Mapping):
            raise V23Error(f"episode step_rows[{row_index}] must be an object")
        row_env_id = row.get("env_id")
        row_episode_index = row.get("episode_index")
        if isinstance(row_env_id, bool) or not isinstance(row_env_id, int) or not 0 <= row_env_id < 16:
            raise V23Error(f"episode step_rows[{row_index}] env_id must be within 0..15")
        if isinstance(row_episode_index, bool) or not isinstance(row_episode_index, int) or row_episode_index < 0:
            raise V23Error(f"episode step_rows[{row_index}] episode_index must be a non-negative integer")
        if row_env_id != env_id or row_episode_index != episode_index:
            raise V23Error(
                "episode step rows must preserve immutable env_id and episode_index"
            )
    return env_id, episode_index


def _validate_episode_export_records(
    records: Sequence[Mapping[str, Any]], *, expected_mode: str
) -> list[Mapping[str, Any]]:
    """Validate one exact 16-record trainer export before any identity map is built."""

    if isinstance(records, (str, bytes)) or not isinstance(records, Sequence):
        raise V23Error(f"{expected_mode} input records must be a sequence")
    records = list(records)
    if len(records) != 16:
        raise V23Error(f"{expected_mode} input must contain exactly 16 episode records")
    env_ids: list[int] = []
    identities: set[tuple[Any, ...]] = set()
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            raise V23Error(f"{expected_mode} record {index} must be an object")
        if record.get("schema") != "a2_piper_v23_episode_record_v1":
            raise V23Error(f"{expected_mode} record {index} has an unsupported episode schema")
        if record.get("mode") != expected_mode:
            raise V23Error(f"{expected_mode} record {index} mode does not match its source file")
        identity = _episode_identity_key(record)
        if (
            record.get("checkpoint_load_mode") != "policy_only"
            or not isinstance(record.get("cell_id"), str)
            or not isinstance(record.get("geometry_id"), str)
            or not isinstance(record.get("canonical_geometry"), Mapping)
        ):
            raise V23Error(f"{expected_mode} record {index} lacks exact load-mode/canonical geometry identity")
        try:
            canonical_identity_geometry = validate_canonical_geometry_record(
                record["canonical_geometry"],
                cell_id=record["cell_id"],
                realized_params=record["canonical_geometry"].get("realized_params"),
            )
        except (V23Error, ValueError) as exc:
            raise V23Error(f"{expected_mode} record {index} canonical geometry is invalid") from exc
        if canonical_identity_geometry["geometry_id"] != record["geometry_id"]:
            raise V23Error(f"{expected_mode} record {index} geometry_id does not match canonical identity")
        prefix_id = record.get("plain_prefix_id")
        if not isinstance(prefix_id, str) or not prefix_id:
            raise V23Error(f"{expected_mode} record {index} plain_prefix_id is required")
        step_rows = record.get("step_rows")
        if not isinstance(step_rows, list) or not step_rows:
            raise V23Error(f"{expected_mode} record {index} must contain non-empty step_rows")
        env_id, _episode_index = _episode_provenance(record)
        control_steps: list[int] = []
        for row_index, row in enumerate(step_rows):
            if row.get("schema") != "a2_piper_v23_step_trace_v1":
                raise V23Error(f"{expected_mode} record {index} step_rows[{row_index}] has an unsupported schema")
            if row.get("mode") != expected_mode or row.get("plain_prefix_id") != prefix_id:
                raise V23Error(f"{expected_mode} record {index} step row mode/prefix does not match")
            if _episode_identity_key(row) != identity:
                raise V23Error(f"{expected_mode} record {index} step row identity does not match")
            if row.get("state_clone_supported") is not False or row.get("forward_only") is not True:
                raise V23Error(f"{expected_mode} record {index} violates forward-only provenance")
            capability = row.get("capability_sample")
            if (
                not isinstance(capability, Mapping)
                or capability.get("schema") != "a2_piper_v23_capability_sample_v1"
                or not isinstance(capability.get("cell_id"), str)
                or not isinstance(capability.get("geometry_id"), str)
                or not isinstance(capability.get("canonical_geometry"), Mapping)
                or not isinstance(capability.get("realized_params"), Mapping)
                or capability.get("checkpoint_load_mode") != "policy_only"
                or capability.get("status") not in ("VALID", "INFEASIBLE", "UNBOUNDED")
            ):
                raise V23Error(f"{expected_mode} record {index} step capability sample is not a registered cell/geometry sample")
            try:
                capability_geometry = validate_canonical_geometry_record(
                    capability["canonical_geometry"],
                    cell_id=capability["cell_id"],
                    realized_params=capability["realized_params"],
                )
            except (V23Error, ValueError) as exc:
                raise V23Error(f"{expected_mode} record {index} step capability canonical geometry is invalid") from exc
            if (
                capability["geometry_id"] != capability_geometry["geometry_id"]
                or capability["cell_id"] != record["cell_id"]
                or capability["geometry_id"] != record["geometry_id"]
            ):
                raise V23Error(f"{expected_mode} record {index} capability geometry does not match episode identity")
            control_step = row.get("control_step")
            if isinstance(control_step, bool) or not isinstance(control_step, int) or control_step < 0:
                raise V23Error(f"{expected_mode} record {index} control_step is malformed")
            control_steps.append(control_step)
        if control_steps != list(range(control_steps[0], control_steps[0] + len(control_steps))) or control_steps[0] != 0:
            raise V23Error(f"{expected_mode} record {index} step_rows must be contiguous from control_step 0")
        if identity in identities:
            raise V23Error(f"duplicate {expected_mode} experimental identity")
        identities.add(identity)
        env_ids.append(env_id)
    if sorted(env_ids) != list(range(16)) or len(set(env_ids)) != 16:
        raise V23Error(f"{expected_mode} input env ids must be exactly 0..15 once each")
    return records


def _episode_export_records(
    payload: Mapping[str, Any], *, expected_mode: str
) -> list[Mapping[str, Any]]:
    if not isinstance(payload, Mapping) or payload.get("schema") != P05_EPISODE_EXPORT_SCHEMA:
        raise V23Error(
            f"{expected_mode} input must use {P05_EPISODE_EXPORT_SCHEMA}"
        )
    records = payload.get("records")
    return _validate_episode_export_records(records, expected_mode=expected_mode)


def _group_episode_records(
    records_by_mode: Mapping[str, Sequence[Mapping[str, Any]]],
) -> list[dict[str, Any]]:
    expected_modes = tuple(V23_P05_MODES)
    if set(records_by_mode) != set(expected_modes):
        raise V23Error("FULL, ACUTE_RP0, and rescue source records are required exactly once")
    mode_keys: dict[str, set[tuple[Any, ...]]] = {}
    mode_by_key: dict[str, dict[tuple[Any, ...], Mapping[str, Any]]] = {}
    provenance_by_mode: dict[str, dict[tuple[Any, ...], tuple[int, int]]] = {}
    for mode in expected_modes:
        records = records_by_mode.get(mode)
        if not isinstance(records, Sequence) or isinstance(records, (str, bytes)):
            raise V23Error(f"{mode} source records are required")
        records = _validate_episode_export_records(records, expected_mode=mode)
        mode_by_key[mode] = {}
        mode_keys[mode] = set()
        provenance_by_mode[mode] = {}
        for record in records:
            key = _episode_identity_key(record)
            if key in mode_keys[mode]:
                raise V23Error(f"duplicate {mode} experimental identity")
            mode_keys[mode].add(key)
            mode_by_key[mode][key] = record
            provenance_by_mode[mode][key] = _episode_provenance(record)
    reference = mode_keys["FULL"]
    if any(mode_keys[mode] != reference for mode in expected_modes[1:]):
        raise V23Error("FULL, ACUTE_RP0, and HIGHER_EFFORT_RESCUE identity sets must match exactly")
    groups = []
    for key in sorted(reference, key=str):
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
        )
        identity = dict(zip(identity_fields, key))
        env_id, episode_index = provenance_by_mode["FULL"][key]
        for mode in expected_modes[1:]:
            if provenance_by_mode[mode][key] != (env_id, episode_index):
                raise V23Error(
                    "FULL, ACUTE_RP0, and rescue records must share exact env_id and episode_index"
                )
            full_cap = mode_by_key["FULL"][key]["step_rows"][0]["capability_sample"]
            mode_cap = mode_by_key[mode][key]["step_rows"][0]["capability_sample"]
            if (
                full_cap.get("cell_id") != mode_cap.get("cell_id")
                or full_cap.get("geometry_id") != mode_cap.get("geometry_id")
                or full_cap.get("realized_params") != mode_cap.get("realized_params")
                or full_cap.get("canonical_geometry") != mode_cap.get("canonical_geometry")
                or full_cap.get("checkpoint_load_mode") != mode_cap.get("checkpoint_load_mode")
            ):
                raise V23Error("cross-mode capability cell/geometry/realized_params joins must match exactly")
        groups.append(
            {
                "identity": identity,
                "plain_prefix_id": identity["plain_prefix_id"],
                "env_id": env_id,
                "episode_index": episode_index,
                "modes": {mode: mode_by_key[mode][key] for mode in expected_modes},
            }
        )
    group_env_ids = [group["env_id"] for group in groups]
    if sorted(group_env_ids) != list(range(16)) or len(set(group_env_ids)) != 16:
        raise V23Error("cross-mode groups must cover env ids exactly 0..15 once each")
    return groups


def build_three_mode_bundle(
    full_payload: Mapping[str, Any],
    acute_payload: Mapping[str, Any],
    rescue_payload: Mapping[str, Any],
    *,
    bands: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Bind the three actual 16-record trainer exports without subsetting."""

    records_by_mode = {
        "FULL": _episode_export_records(full_payload, expected_mode="FULL"),
        "ACUTE_RP0": _episode_export_records(acute_payload, expected_mode="ACUTE_RP0"),
        "HIGHER_EFFORT_RESCUE": _episode_export_records(
            rescue_payload, expected_mode="HIGHER_EFFORT_RESCUE"
        ),
    }
    groups = _group_episode_records(records_by_mode)
    pairs = pair_forward_record_set(
        records_by_mode["FULL"], records_by_mode["HIGHER_EFFORT_RESCUE"]
    )
    episodes = [
        record
        for mode in V23_P05_MODES
        for record in records_by_mode[mode]
    ]
    result: dict[str, Any] = {
        "schema": P05_BUNDLE_SCHEMA,
        "status": "READY_FOR_CERTIFICATE",
        "topology": groups[0]["identity"]["topology"] if groups else None,
        "record_count": len(episodes),
        "episodes": episodes,
        "source_records": {mode: list(records_by_mode[mode]) for mode in V23_P05_MODES},
        "groups": groups,
        "pairs": pairs["pairs"],
    }
    if bands is not None:
        result["bands"] = {"values": a2_v23_validate_p05_bands(bands)}
    return result
def _effort_limit_vector(effort_nm: float) -> list[float]:
    return build_effort_limit_list(effort_nm)


def _typed_file_input(path: str | Path | None, *, label: str) -> tuple[dict[str, Any] | None, str]:
    if path is None:
        return None, f"{label}_INPUT_REQUIRED"
    try:
        payload = read_json(path)
    except V23Error as exc:
        return None, f"{label}_INVALID:{exc}"
    return payload, "READY"


def _effort_freeze(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    if payload is None:
        return {"status": "INPUT_REQUIRED"}
    if not isinstance(payload, Mapping) or payload.get("schema") != EFFORT_FREEZE_SCHEMA:
        return {"status": "FREEZE_SCHEMA_INVALID", "source_status": payload.get("status") if isinstance(payload, Mapping) else None}
    status = payload.get("status")
    if status != "MEASURED_FREEZE":
        return {"status": "NOT_MEASURED", "source_status": status}
    selection_outcome = payload.get("selection_outcome")
    if selection_outcome not in EFFORT_FREEZE_SELECTION_OUTCOMES:
        return {"status": "FREEZE_SELECTION_INVALID", "source_status": status}
    source_provenance = payload.get("source_provenance")
    authorities = payload.get("authorities")
    profile = payload.get("effort_profile")
    if (
        not isinstance(source_provenance, Mapping)
        or source_provenance.get("complete") is not True
        or not isinstance(source_provenance.get("required_fields"), list)
        or not isinstance(source_provenance.get("runs"), list)
        or source_provenance.get("record_count") != 192
        or len(source_provenance["runs"]) != 12
        or not isinstance(authorities, Mapping)
        or authorities.get("checkpoint_load_mode") != "policy_only"
        or not isinstance(profile, Mapping)
    ):
        return {"status": "FREEZE_PROVENANCE_INVALID", "source_status": status}
    if any(
        not isinstance(run, Mapping)
        or run.get("record_count") != 16
        or run.get("topology") not in ("canonical16", "heavy16")
        or run.get("checkpoint_load_mode") != "policy_only"
        for run in source_provenance["runs"]
    ):
        return {"status": "FREEZE_PROVENANCE_INVALID", "source_status": status}
    selected = payload.get("selected_effort_nm")
    if isinstance(selected, bool) or not isinstance(selected, (int, float)):
        return {"status": "SELECTED_EFFORT_REQUIRED", "source_status": status}
    try:
        selected_value = finite_number(selected, name="selected_effort_nm")
    except V23Error:
        return {"status": "SELECTED_EFFORT_INVALID", "source_status": status}
    if selected_value <= 0.0 or selected_value > 100.0:
        return {"status": "SELECTED_EFFORT_OUT_OF_RANGE", "selected_effort_nm": selected_value}
    if selected_value not in V23_EFFORT_RUNGS:
        return {
            "status": "SELECTED_EFFORT_NOT_REGISTERED",
            "selected_effort_nm": selected_value,
            "registered_effort_rungs": list(V23_EFFORT_RUNGS),
        }
    expected_profile = f"base_v23_p0_effort_{selected_value:g}"
    if profile.get("effort_nm") != selected_value or profile.get("name") != expected_profile:
        return {"status": "FREEZE_PROFILE_INVALID", "selected_effort_nm": selected_value}
    return {
        "schema": EFFORT_FREEZE_SCHEMA,
        "status": "MEASURED_FREEZE",
        "source_status": status,
        "selection_outcome": selection_outcome,
        "selected_effort_nm": selected_value,
        "effort_profile": dict(profile),
        "source_provenance": dict(source_provenance),
        "authorities": dict(authorities),
        "authority": "REAL_EFFORT_FREEZE_INPUT",
    }


def _d1_effort_source_join(
    *,
    effort_input: str | Path | None,
    effort_payload: Mapping[str, Any] | None,
    source_freeze: Mapping[str, Any],
) -> dict[str, Any]:
    if effort_input is None or not isinstance(effort_payload, Mapping):
        raise V23Error("D1 capability-source plans require a readable effort freeze input")
    effort_path = Path(effort_input).expanduser().resolve()
    effort = _effort_freeze(effort_payload)
    source_effort_path = source_freeze.get("source_paths", {}).get("effort_freeze")
    if source_effort_path != str(effort_path):
        raise V23Error("D1 capability-source effort input path does not match the A0 source freeze")
    if (
        effort.get("status") != "MEASURED_FREEZE"
        or effort.get("selected_effort_nm") != 40.0
        or source_freeze.get("selected_effort_nm") != 40.0
        or effort.get("selected_effort_nm") != source_freeze.get("selected_effort_nm")
    ):
        raise V23Error("D1 capability-source effort join requires selected_effort_nm=40.0 in both artifacts")
    return {
        "status": "READY",
        "effort_input_path": str(effort_path),
        "source_freeze_effort_path": str(source_effort_path),
        "effort_selected_effort_nm": float(effort["selected_effort_nm"]),
        "source_selected_effort_nm": float(source_freeze["selected_effort_nm"]),
    }


def _atlas_manifest(payload: Mapping[str, Any] | None, *, topology: str) -> dict[str, Any]:
    if payload is None:
        return {"status": "INPUT_REQUIRED", "topology": topology}
    if not isinstance(payload, Mapping):
        return {"status": "ATLAS_SCHEMA_INVALID", "topology": topology}
    status = payload.get("status")
    if status in ("NOT_RUN_PENDING", "PENDING", "PENDING_MEASURED_RUN", "NONLAUNCHABLE_INPUTS_REQUIRED"):
        return {"status": "NOT_MEASURED", "source_status": status, "topology": topology}
    if payload.get("schema") != "a2_piper_v23_door_atlas_raw_v1" or status != "MEASURED_RAW":
        return {"status": "ATLAS_SCHEMA_INVALID", "topology": topology, "source_status": status}
    rows = payload.get("rows")
    if not isinstance(rows, list) or len(rows) != 9:
        return {"status": "ATLAS_ROWS_REQUIRED", "topology": topology, "source_status": status}
    identities = []
    geometry_ids = []
    normalized_rows = []
    for row in rows:
        if not isinstance(row, Mapping):
            return {"status": "ATLAS_ROW_INVALID", "topology": topology}
        cell_id = row.get("cell_id")
        geometry_id = row.get("geometry_id")
        requested = row.get("requested_params")
        realized = row.get("realized_params")
        canonical = row.get("canonical_geometry")
        if (
            not isinstance(cell_id, str)
            or not cell_id
            or not isinstance(geometry_id, str)
            or not geometry_id
            or not isinstance(canonical, Mapping)
        ):
            return {"status": "ATLAS_CELL_GEOMETRY_REQUIRED", "topology": topology}
        if not isinstance(requested, Mapping) or set(requested) != P05_REQUESTED_PARAMS_FIELDS or not isinstance(realized, Mapping):
            return {"status": "ATLAS_REALIZED_PARAMS_REQUIRED", "topology": topology}
        if any(key not in realized for key in ("hinge_damping_native", "hinge_stiffness_native", "hinge_effort_limit_nm")):
            return {"status": "ATLAS_REALIZED_PARAMS_INCOMPLETE", "topology": topology}
        try:
            canonical = validate_canonical_geometry_record(
                canonical, cell_id=cell_id, realized_params=realized
            )
        except (V23Error, ValueError) as exc:
            return {"status": "ATLAS_CANONICAL_GEOMETRY_INVALID", "topology": topology, "reason": str(exc)}
        if geometry_id != canonical["geometry_id"]:
            return {"status": "ATLAS_CANONICAL_GEOMETRY_INVALID", "topology": topology}
        if cell_id == SELECTED_CELL_ID and (
            dict(requested) != P05_A8_REQUESTED_PARAMS
            or dict(canonical["realized_params"]) != P05_A8_REALIZED_PARAMS
        ):
            return {"status": "ATLAS_A8_PARAMETER_IDENTITY_INVALID", "topology": topology}
        identities.append(cell_id)
        geometry_ids.append(geometry_id)
        normalized_rows.append({"cell_id": cell_id, "geometry_id": geometry_id, "canonical_geometry": canonical, "requested_params": dict(requested), "realized_params": dict(canonical["realized_params"])})
    if set(identities) != {f"A{index}" for index in range(9)} or len(set(identities)) != len(identities) or len(set(geometry_ids)) != len(geometry_ids):
        return {"status": "ATLAS_ID_DUPLICATE", "topology": topology}
    return {
        "status": "MEASURED_ATLAS",
        "source_status": status,
        "topology": topology,
        "row_count": len(rows),
        "cell_ids": identities,
        "geometry_ids": geometry_ids,
        "rows": normalized_rows,
        "authority": "REAL_ATLAS_MANIFEST_INPUT",
    }


def _plain_manifest(payload: Mapping[str, Any] | None, *, topology: str) -> dict[str, Any]:
    """Validate the exact plain selector payload consumed by IsaacLab."""

    if payload is None:
        return {"status": "INPUT_REQUIRED", "topology": topology}
    if not isinstance(payload, Mapping):
        return {"status": "PLAIN_SCHEMA_INVALID", "topology": topology}
    expected_keys = {
        "schema",
        "status",
        "topology",
        "source_manifest_path",
        "source_role",
        "rows",
    }
    if set(payload) != expected_keys:
        return {"status": "PLAIN_SCHEMA_INVALID", "topology": topology}
    if payload.get("schema") != P05_PLAIN_MANIFEST_SCHEMA or payload.get("status") != "STATIC_PLAIN":
        return {"status": "PLAIN_SCHEMA_INVALID", "topology": topology}
    if payload.get("topology") != topology:
        return {"status": "PLAIN_TOPOLOGY_MISMATCH", "topology": topology}
    source_path_value = payload.get("source_manifest_path")
    if not isinstance(source_path_value, str) or not source_path_value:
        return {"status": "PLAIN_SOURCE_REQUIRED", "topology": topology}
    source_path = Path(source_path_value)
    if not source_path.is_absolute() or source_path.is_symlink() or not source_path.is_file():
        return {"status": "PLAIN_SOURCE_INVALID", "topology": topology}
    if payload.get("source_role") != "historical_prior_only":
        return {"status": "PLAIN_SOURCE_ROLE_INVALID", "topology": topology}
    rows = payload.get("rows")
    if not isinstance(rows, list) or len(rows) != 16:
        return {"status": "PLAIN_ROWS_INVALID", "topology": topology}
    scenario_ids = []
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping) or set(row) != P05_PLAIN_SOURCE_FIELDS:
            return {"status": f"PLAIN_ROW_{index}_INVALID", "topology": topology}
        scenario_id = row["scenario_id"]
        if not isinstance(scenario_id, str) or not scenario_id or scenario_id in scenario_ids:
            return {"status": f"PLAIN_ROW_{index}_IDENTITY_INVALID", "topology": topology}
        scenario_ids.append(scenario_id)
        for field in ("handle_height_m", "door_weight_kg", "hinge_force_nm"):
            value = row[field]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return {"status": f"PLAIN_ROW_{index}_{field}_INVALID", "topology": topology}
            try:
                numeric = finite_number(value, name=f"plain row {index} {field}")
            except V23Error:
                return {"status": f"PLAIN_ROW_{index}_{field}_INVALID", "topology": topology}
            if numeric <= 0.0:
                return {"status": f"PLAIN_ROW_{index}_{field}_INVALID", "topology": topology}
    return {
        "status": "STATIC_PLAIN",
        "topology": topology,
        "row_count": len(rows),
        "scenario_ids": scenario_ids,
        "authority": "PLAIN_SELECTOR_MANIFEST",
    }


def build_bound_plain_manifest_payload(
    payload: Mapping[str, Any],
    *,
    topology: str,
    selected_geometry: Mapping[str, Any],
) -> dict[str, Any]:
    """Bind plain16 CRN identities to one canonical measured atlas cell.

    The historical plain manifest remains source-only.  The returned payload
    is the dedicated strict v23 bound selector consumed before asset creation.
    Scenario IDs/source rows and the fixed policy identity are immutable CRN
    provenance; every canonical spawn field is explicit in every row.
    """

    validated_plain = _plain_manifest(payload, topology=topology)
    if validated_plain.get("status") != "STATIC_PLAIN":
        raise V23Error("bound plain materialization requires a validated STATIC_PLAIN source")
    if not isinstance(selected_geometry, Mapping):
        raise V23Error("bound plain materialization requires the selected atlas geometry")
    cell_id = selected_geometry.get("cell_id")
    realized_params = selected_geometry.get("realized_params")
    canonical_geometry = selected_geometry.get("canonical_geometry")
    if not isinstance(cell_id, str) or not cell_id:
        raise V23Error("bound plain materialization requires a canonical cell_id")
    if cell_id != SELECTED_CELL_ID:
        raise V23Error("bound plain materialization requires the selected A8 geometry")
    if not isinstance(realized_params, Mapping) or not isinstance(canonical_geometry, Mapping):
        raise V23Error("bound plain materialization requires canonical and realized geometry")
    requested, expected_realized = _validate_p05_a8_geometry_params(selected_geometry)
    canonical_geometry = validate_canonical_geometry_record(
        canonical_geometry,
        cell_id=cell_id,
        realized_params=realized_params,
    )
    if selected_geometry.get("geometry_id") != canonical_geometry["geometry_id"]:
        raise V23Error("bound plain materialization geometry_id disagrees with canonical geometry")
    facts = canonical_geometry["local_facts"]
    realized = canonical_geometry["realized_params"]
    if realized != expected_realized:
        raise V23Error("bound plain materialization native realized parameters changed during canonical validation")
    source_rows = payload["rows"]
    rows = [
        {
            "source_identity": {
                "source_manifest_path": str(payload["source_manifest_path"]),
                "source_role": "historical_prior_only",
                "source_row": dict(row),
            },
            "scenario_id": row["scenario_id"],
            "env_id": index,
            "episode_index": 0,
            "plain_prefix_id": f"{row['scenario_id']}:{topology}:env{index}:episode0",
            "checkpoint": P05_WARM_CHECKPOINT,
            "config": V23_WARM_START_CONFIG,
            "seed": 0,
            "topology": topology,
            "cell_id": cell_id,
            "geometry_id": canonical_geometry["geometry_id"],
            "canonical_geometry": dict(canonical_geometry),
            "requested_params": dict(requested),
            "realized_params": dict(realized),
            "door_width_m": float(facts["door_width_m"]),
            "door_height_m": float(facts["door_height_m"]),
            "handle_height_m": float(facts["handle_height_m"]),
            "handle_width_m": float(facts["handle_width_m"]),
            "handle_type": facts["handle_type"],
            "door_open_lr": facts["door_open_lr"],
            "door_open_io": facts["door_open_io"],
            "hinge_axis_local": list(facts["hinge_axis_local"]),
            "hinge_anchor_local": list(facts["hinge_anchor_local"]),
        }
        for index, row in enumerate(source_rows)
    ]
    bound = {
        "schema": P05_BOUND_PLAIN_MANIFEST_SCHEMA,
        "status": "BOUND_PLAIN16",
        "selector_mode": P05_BOUND_PLAIN_SELECTOR_MODE,
        "topology": topology,
        "source_manifest_path": str(payload["source_manifest_path"]),
        "source_role": "historical_prior_only",
        "canonical_geometry_schema": P05_BOUND_CANONICAL_GEOMETRY_SCHEMA,
        "rows": rows,
    }
    return bound


def materialize_bound_plain_manifest(
    output_path: str | Path,
    *,
    source_payload: Mapping[str, Any],
    topology: str,
    selected_geometry: Mapping[str, Any],
) -> dict[str, Any]:
    """Write the deterministic bound selector only immediately before RUN."""

    bound = build_bound_plain_manifest_payload(
        source_payload,
        topology=topology,
        selected_geometry=selected_geometry,
    )
    path = Path(output_path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(bound, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return bound


def build_d1_capability_bound_plain_manifest_payload(
    payload: Mapping[str, Any],
    *,
    topology: str,
    capability_source_freeze: Mapping[str, Any],
    capability_source_freeze_path: str | Path,
) -> dict[str, Any]:
    """Bind plain16 identities to the exact A0 D1 capability source."""

    validated_plain = _plain_manifest(payload, topology=topology)
    if validated_plain.get("status") != "STATIC_PLAIN":
        raise V23Error("D1 bound plain materialization requires a validated STATIC_PLAIN source")
    source_freeze = validate_capability_source_freeze(capability_source_freeze)
    source_geometry = {
        "cell_id": source_freeze["source_cell_id"],
        "geometry_id": source_freeze["source_geometry_id"],
        "canonical_geometry": source_freeze["canonical_geometry"],
        "requested_params": source_freeze["requested_params"],
        "realized_params": {
            "hinge_damping_native": source_freeze["native_params"]["hinge_damping_native"],
            "hinge_stiffness_native": source_freeze["native_params"]["hinge_stiffness_native"],
            "hinge_effort_limit_nm": source_freeze["native_params"]["hinge_effort_limit_nm"],
            "door_weight_kg": source_freeze["native_params"]["door_weight_kg"],
        },
    }
    if source_geometry["cell_id"] != CAPABILITY_SOURCE_CELL_ID:
        raise V23Error("D1 bound plain materialization requires source cell A0")
    requested, expected_realized = _validate_p05_a0_geometry_params(source_geometry)
    canonical_geometry = validate_canonical_geometry_record(
        source_geometry["canonical_geometry"],
        cell_id=CAPABILITY_SOURCE_CELL_ID,
        realized_params=expected_realized,
    )
    if source_geometry["geometry_id"] != canonical_geometry["geometry_id"]:
        raise V23Error("D1 bound plain materialization geometry_id disagrees with canonical geometry")
    facts = canonical_geometry["local_facts"]
    source_freeze_path = str(Path(capability_source_freeze_path).expanduser().resolve())
    rows = [
        {
            "purpose": D1_CAPABILITY_SOURCE,
            "source_identity": {
                "source_manifest_path": str(payload["source_manifest_path"]),
                "source_role": "historical_prior_only",
                "source_row": dict(row),
            },
            "scenario_id": row["scenario_id"],
            "env_id": index,
            "episode_index": 0,
            "plain_prefix_id": f"{row['scenario_id']}:{topology}:env{index}:episode0",
            "checkpoint": P05_WARM_CHECKPOINT,
            "config": V23_WARM_START_CONFIG,
            "seed": 0,
            "topology": topology,
            "cell_id": CAPABILITY_SOURCE_CELL_ID,
            "geometry_id": canonical_geometry["geometry_id"],
            "canonical_geometry": dict(canonical_geometry),
            "requested_params": dict(requested),
            "realized_params": dict(expected_realized),
            "door_width_m": float(facts["door_width_m"]),
            "door_height_m": float(facts["door_height_m"]),
            "handle_height_m": float(facts["handle_height_m"]),
            "handle_width_m": float(facts["handle_width_m"]),
            "handle_type": facts["handle_type"],
            "door_open_lr": facts["door_open_lr"],
            "door_open_io": facts["door_open_io"],
            "hinge_axis_local": list(facts["hinge_axis_local"]),
            "hinge_anchor_local": list(facts["hinge_anchor_local"]),
        }
        for index, row in enumerate(payload["rows"])
    ]
    return {
        "schema": P05_D1_BOUND_MANIFEST_SCHEMA,
        "status": "BOUND_D1_CAPABILITY_SOURCE",
        "purpose": D1_CAPABILITY_SOURCE,
        "selector_mode": P05_D1_BOUND_SELECTOR_MODE,
        "topology": topology,
        "source_manifest_path": str(payload["source_manifest_path"]),
        "source_role": "historical_prior_only",
        "capability_source_freeze_schema": CAPABILITY_SOURCE_FREEZE_SCHEMA,
        "capability_source_freeze_path": source_freeze_path,
        "canonical_geometry_schema": P05_D1_BOUND_CANONICAL_GEOMETRY_SCHEMA,
        "rows": rows,
    }


def materialize_d1_capability_bound_plain_manifest(
    output_path: str | Path,
    *,
    source_payload: Mapping[str, Any],
    topology: str,
    capability_source_freeze: Mapping[str, Any],
    capability_source_freeze_path: str | Path,
) -> dict[str, Any]:
    bound = build_d1_capability_bound_plain_manifest_payload(
        source_payload,
        topology=topology,
        capability_source_freeze=capability_source_freeze,
        capability_source_freeze_path=capability_source_freeze_path,
    )
    path = Path(output_path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(bound, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return bound


def build_d1_probe_plan(
    *,
    mode: str,
    topology: str,
    effort_input: str | Path | None,
    atlas_input: str | Path | None,
    external_input: str | Path | None,
    plain_manifest: str | Path | None,
    output_dir: str | Path,
    capability_source_freeze: str | Path,
) -> dict[str, Any]:
    if mode not in ("FULL", "ACUTE_RP0"):
        raise V23Error("D1 capability-source plans allow only FULL or ACUTE_RP0")
    if topology not in P05_TOPOLOGIES:
        raise V23Error(f"D1 topology must be one of {P05_TOPOLOGIES}")
    source_freeze_path = Path(capability_source_freeze).expanduser().resolve()
    source_freeze = validate_capability_source_freeze(read_json(source_freeze_path))
    effort_payload, effort_input_status = _typed_file_input(effort_input, label="EFFORT_FREEZE")
    external_payload, external_input_status = _typed_file_input(external_input, label="EXTERNAL_THRESHOLD")
    plain_payload, plain_input_status = _typed_file_input(plain_manifest, label="PLAIN_SCENARIO_MANIFEST")
    effort = _effort_freeze(effort_payload)
    effort_source_join = _d1_effort_source_join(
        effort_input=effort_input,
        effort_payload=effort_payload,
        source_freeze=source_freeze,
    )
    if not isinstance(external_payload, Mapping):
        raise V23Error("D1 capability-source plans require the measured external threshold input")
    _external_payload, _external_threshold_rows = _external_rows(external_payload)
    plain = _plain_manifest(plain_payload, topology=topology)
    atlas_input_status = "NOT_REQUIRED"
    if atlas_input is not None:
        _atlas_payload, atlas_input_status = _typed_file_input(atlas_input, label="ATLAS_MANIFEST")
    if (
        atlas_input is not None
        and source_freeze["source_paths"].get("atlas")
        != str(Path(atlas_input).expanduser().resolve())
    ):
        raise V23Error("D1 capability-source freeze atlas path does not match the supplied atlas input")
    if source_freeze["source_paths"].get("external_threshold") != str(Path(external_input).expanduser().resolve()):
        raise V23Error("D1 capability-source freeze external path does not match the supplied threshold input")
    checkpoint = REPO_ROOT / P05_WARM_CHECKPOINT
    warm_start = {
        "checkpoint": P05_WARM_CHECKPOINT,
        "config": V23_WARM_START_CONFIG,
        "required": True,
        "available": checkpoint.is_file() and not checkpoint.is_symlink(),
        "policy": "fixed_v22_G1_step1250_policy_only",
    }
    selected_geometry = {
        "cell_id": source_freeze["source_cell_id"],
        "geometry_id": source_freeze["source_geometry_id"],
        "canonical_geometry": source_freeze["canonical_geometry"],
        "requested_params": source_freeze["requested_params"],
        "realized_params": {
            "hinge_damping_native": source_freeze["native_params"]["hinge_damping_native"],
            "hinge_stiffness_native": source_freeze["native_params"]["hinge_stiffness_native"],
            "hinge_effort_limit_nm": source_freeze["native_params"]["hinge_effort_limit_nm"],
            "door_weight_kg": source_freeze["native_params"]["door_weight_kg"],
        },
    }
    bound_plain_manifest = None
    if isinstance(plain_payload, Mapping):
        bound_plain_manifest = build_d1_capability_bound_plain_manifest_payload(
            plain_payload,
            topology=topology,
            capability_source_freeze=source_freeze,
            capability_source_freeze_path=source_freeze_path,
        )
    bound_plain_manifest_path = Path(output_dir).expanduser().resolve() / P05_D1_BOUND_MANIFEST_FILENAME
    launchable = (
        effort.get("status") == "MEASURED_FREEZE"
        and effort.get("selection_outcome") in EFFORT_FREEZE_SELECTION_OUTCOMES
        and plain.get("status") == "STATIC_PLAIN"
        and warm_start["available"]
        and source_freeze.get("status") == "CAPABILITY_SOURCE_FROZEN"
        and source_freeze.get("purpose") == D1_CAPABILITY_SOURCE
        and source_freeze.get("source_cell_id") == CAPABILITY_SOURCE_CELL_ID
        and effort_source_join.get("status") == "READY"
    )
    return artifact_payload(
        "p05_rescue_probe_plan",
        status="READY_TO_LAUNCH" if launchable else "NONLAUNCHABLE_INPUTS_REQUIRED",
        launchable=launchable,
        purpose=D1_CAPABILITY_SOURCE,
        mode=mode,
        topology=topology,
        effort_freeze=effort,
        capability_source_freeze=source_freeze,
        effort_source_join=effort_source_join,
        plain_manifest=plain,
        input_paths={
            "effort_freeze": None if effort_input is None else str(Path(effort_input).expanduser().resolve()),
            "atlas_manifest": None if atlas_input is None else str(Path(atlas_input)),
            "external_threshold": str(Path(external_input)),
            "capability_source_freeze": str(source_freeze_path),
            "plain_manifest": None if plain_manifest is None else str(Path(plain_manifest)),
        },
        input_statuses={
            "effort_freeze": effort_input_status,
            "effort_source_join": "READY",
            "atlas_manifest": atlas_input_status,
            "external_threshold": external_input_status,
            "capability_source_freeze": "READY",
            "plain_manifest": plain_input_status,
        },
        warm_start=warm_start,
        checkpoint_load_mode="policy_only",
        seed=0,
        num_envs=16,
        episodes_per_env=1,
        state_clone_supported=False,
        intervention_contract={
            "forward_only": True,
            "modes": ["FULL", "ACUTE_RP0"],
            "rescue_forbidden": True,
        },
        cell_id=CAPABILITY_SOURCE_CELL_ID,
        selected_geometry=selected_geometry,
        requested_params=dict(source_freeze["requested_params"]),
        native_params=dict(source_freeze["native_params"]),
        bound_plain_manifest=bound_plain_manifest,
        bound_plain_manifest_path=str(bound_plain_manifest_path),
    )


def build_probe_plan(
    *,
    mode: str,
    topology: str,
    effort_input: str | Path | None,
    atlas_input: str | Path | None,
    external_input: str | Path | None,
    bands: Mapping[str, Any] | None,
    output_dir: str | Path,
    plain_manifest: str | Path | None = None,
    selected_cell_freeze: str | Path | Mapping[str, Any] | None = None,
    purpose: str = P05_CERTIFICATE,
    capability_source_freeze: str | Path | None = None,
) -> dict[str, Any]:
    if purpose not in (P05_CERTIFICATE, D1_CAPABILITY_SOURCE):
        raise V23Error(f"P0.5 purpose must be one of {(P05_CERTIFICATE, D1_CAPABILITY_SOURCE)}")
    if purpose == D1_CAPABILITY_SOURCE:
        if selected_cell_freeze is not None or bands is not None:
            raise V23Error("D1 capability-source plans forbid selected A8 freeze and rescue bands")
        if external_input is None:
            raise V23Error("D1 capability-source plans require --external-threshold")
        if capability_source_freeze is None:
            raise V23Error("D1 capability-source plans require --capability-source-freeze")
        if not isinstance(capability_source_freeze, (str, Path)):
            raise V23Error("D1 capability-source freeze must be an explicit file path")
        return build_d1_probe_plan(
            mode=mode,
            topology=topology,
            effort_input=effort_input,
            atlas_input=atlas_input,
            external_input=external_input,
            plain_manifest=plain_manifest,
            output_dir=output_dir,
            capability_source_freeze=capability_source_freeze,
        )
    if capability_source_freeze is not None:
        raise V23Error("P0.5 certificate plans forbid a mixed D1 capability-source freeze")
    if mode not in V23_P05_MODES:
        raise V23Error(f"P0.5 producer mode must be one of {V23_P05_MODES}; got {mode!r}")
    if topology not in P05_TOPOLOGIES:
        raise V23Error(f"P0.5 topology must be one of {P05_TOPOLOGIES}; got {topology!r}")
    if selected_cell_freeze is None:
        raise V23Error("P0.5 PLAN/RUN requires --selected-cell-freeze; no free cell selection is allowed")
    if external_input is None:
        raise V23Error("P0.5 PLAN/RUN requires --external-threshold for exact selected-cell provenance")
    if isinstance(selected_cell_freeze, Mapping):
        selected_freeze = validate_selected_cell_freeze(selected_cell_freeze)
        selected_freeze_path = None
    else:
        selected_freeze_path = Path(selected_cell_freeze).expanduser().resolve()
        selected_freeze = validate_selected_cell_freeze(read_json(selected_freeze_path))
    effort_payload, effort_input_status = _typed_file_input(effort_input, label="EFFORT_FREEZE")
    atlas_payload, atlas_input_status = _typed_file_input(atlas_input, label="ATLAS_MANIFEST")
    external_payload, external_input_status = _typed_file_input(external_input, label="EXTERNAL_THRESHOLD")
    plain_payload, plain_input_status = _typed_file_input(plain_manifest, label="PLAIN_SCENARIO_MANIFEST")
    effort = _effort_freeze(effort_payload)
    atlas = _atlas_manifest(atlas_payload, topology=topology)
    if not isinstance(external_payload, Mapping):
        raise V23Error("P0.5 exact selected-cell provenance requires a measured external threshold input")
    _external_payload, external_rows = _external_rows(external_payload)
    plain = _plain_manifest(plain_payload, topology=topology)
    band_result: dict[str, Any]
    if bands is None:
        band_result = {"status": "BANDS_INPUT_REQUIRED"}
    else:
        band_result = {"status": "SELECTED", "values": a2_v23_validate_p05_bands(bands)}
    cell_id = selected_freeze["selected_cell_id"]
    if cell_id != SELECTED_CELL_ID or cell_id not in set(atlas.get("cell_ids", [])):
        raise V23Error("P0.5 selected-cell freeze must derive the measured A8 atlas row")
    source_paths = selected_freeze.get("source_paths")
    expected_paths = {
        "atlas": atlas_input,
        "external_threshold": external_input,
        "effort_freeze": effort_input,
    }
    if not isinstance(source_paths, Mapping):
        raise V23Error("selected-cell freeze must preserve atlas/external/effort source paths")
    for key, supplied in expected_paths.items():
        if supplied is None or Path(source_paths.get(key, "")).expanduser().resolve() != Path(supplied).expanduser().resolve():
            raise V23Error(f"selected-cell freeze source path does not join supplied {key} input")
    atlas_selected = next(row for row in atlas.get("rows", []) if row.get("cell_id") == SELECTED_CELL_ID)
    if selected_freeze.get("selected_geometry") != atlas_selected:
        raise V23Error("selected-cell freeze selected geometry must match the supplied atlas row exactly")
    external_a8 = next(row for row in external_rows if row.get("cell_id") == SELECTED_CELL_ID)
    if (
        external_a8.get("geometry_id") != atlas_selected.get("geometry_id")
        or external_a8.get("canonical_geometry") != atlas_selected.get("canonical_geometry")
        or external_a8.get("realized_params") != atlas_selected.get("realized_params")
    ):
        raise V23Error("selected-cell freeze A8 geometry does not join the supplied external threshold")
    checkpoint = REPO_ROOT / P05_WARM_CHECKPOINT
    warm_start = {
        "checkpoint": P05_WARM_CHECKPOINT,
        "config": V23_WARM_START_CONFIG,
        "required": True,
        "available": checkpoint.is_file() and not checkpoint.is_symlink(),
        "policy": "fixed_v22_G1_step1250_policy_only",
    }
    launchable = (
        effort.get("status") == "MEASURED_FREEZE"
        and effort.get("selection_outcome") in EFFORT_FREEZE_SELECTION_OUTCOMES
        and atlas.get("status") == "MEASURED_ATLAS"
        and plain.get("status") == "STATIC_PLAIN"
        and band_result.get("status") == "SELECTED"
        and warm_start["available"]
        and isinstance(cell_id, str)
        and selected_freeze.get("status") == "SELECTED_CELL_FROZEN"
    )
    selected_atlas_row = next(
        (row for row in atlas.get("rows", []) if isinstance(row, Mapping) and row.get("cell_id") == cell_id),
        None,
    )
    if launchable and not isinstance(selected_atlas_row, Mapping):
        raise V23Error("P0.5 launchable plan must carry the selected canonical atlas row.")
    bound_plain_manifest = None
    if isinstance(plain_payload, Mapping) and isinstance(selected_atlas_row, Mapping):
        bound_plain_manifest = build_bound_plain_manifest_payload(
            plain_payload,
            topology=topology,
            selected_geometry=selected_atlas_row,
        )
    bound_plain_manifest_path = (
        Path(output_dir).expanduser().resolve() / P05_BOUND_PLAIN_MANIFEST_FILENAME
    )
    return artifact_payload(
        "p05_rescue_probe_plan",
        status="READY_TO_LAUNCH" if launchable else "NONLAUNCHABLE_INPUTS_REQUIRED",
        launchable=launchable,
        purpose=P05_CERTIFICATE,
        mode=mode,
        topology=topology,
        effort_freeze=effort,
        atlas_manifest=atlas,
        plain_manifest=plain,
        bands=band_result,
        input_paths={
            "effort_freeze": None if effort_input is None else str(Path(effort_input)),
            "atlas_manifest": None if atlas_input is None else str(Path(atlas_input)),
            "external_threshold": str(Path(external_input)),
            "selected_cell_freeze": None if selected_freeze_path is None else str(selected_freeze_path),
            "plain_manifest": None if plain_manifest is None else str(Path(plain_manifest)),
        },
        input_statuses={
            "effort_freeze": effort_input_status,
            "atlas_manifest": atlas_input_status,
            "external_threshold": external_input_status,
            "selected_cell_freeze": "READY",
            "plain_manifest": plain_input_status,
        },
        warm_start=warm_start,
        checkpoint_load_mode="policy_only",
        seed=0,
        num_envs=16,
        episodes_per_env=1,
        state_clone_supported=False,
        intervention_contract={
            "forward_only": True,
            "modes": list(V23_P05_MODES),
            "acute_rp0_neutral_raw_indices": [3, 4],
            "rescue_effort_cap_nm": 100.0,
        },
        cell_id=cell_id,
        selected_cell_freeze=selected_freeze,
        selected_geometry=(None if selected_atlas_row is None else dict(selected_atlas_row)),
        bound_plain_manifest=bound_plain_manifest,
        bound_plain_manifest_path=str(bound_plain_manifest_path),
    )


def build_probe_argv(
    plan: Mapping[str, Any],
    *,
    output_dir: str | Path,
    effort_input: str | Path,
    atlas_input: str | Path | None,
    external_input: str | Path | None,
    selected_cell_freeze_input: str | Path | None,
    bands_input: str | Path | None,
    plain_manifest: str | Path,
    purpose: str = P05_CERTIFICATE,
    capability_source_freeze_input: str | Path | None = None,
) -> tuple[list[str], dict[str, str]]:
    if purpose == D1_CAPABILITY_SOURCE:
        if capability_source_freeze_input is None:
            raise V23Error("D1 capability-source launch requires --capability-source-freeze")
        return build_d1_probe_argv(
            plan,
            output_dir=output_dir,
            effort_input=effort_input,
            external_input=external_input,
            atlas_input=atlas_input,
            plain_manifest=plain_manifest,
            capability_source_freeze_input=capability_source_freeze_input,
        )
    if purpose != P05_CERTIFICATE:
        raise V23Error("unsupported P0.5 launch purpose")
    if not isinstance(plan, Mapping) or plan.get("launchable") is not True:
        raise V23Error("P0.5 launch requires a READY_TO_LAUNCH plan with real effort and atlas inputs.")
    if plan.get("checkpoint_load_mode") != "policy_only":
        raise V23Error("P0.5 launch requires checkpoint_load_mode=policy_only.")
    checkpoint = require_file(REPO_ROOT / P05_WARM_CHECKPOINT, label="v22 G1 step1250 warm checkpoint")
    require_file(effort_input, label="real effort freeze")
    require_file(atlas_input, label="real atlas manifest")
    require_file(external_input, label="real external threshold")
    require_file(selected_cell_freeze_input, label="selected-cell freeze")
    require_file(bands_input, label="selected P0.5 bands")
    require_file(plain_manifest, label="plain scenario manifest")
    mode = plan.get("mode")
    topology = plan.get("topology")
    cell_id = plan.get("cell_id")
    effort = plan.get("effort_freeze", {}).get("selected_effort_nm")
    selected_freeze = validate_selected_cell_freeze(read_json(selected_cell_freeze_input))
    selected_geometry = plan.get("selected_geometry")
    if mode not in V23_P05_MODES or topology not in P05_TOPOLOGIES or cell_id != SELECTED_CELL_ID:
        raise V23Error("launch plan has an invalid strict mode or topology")
    if selected_freeze.get("selected_cell_id") != cell_id or selected_freeze.get("selected_effort_nm") != effort:
        raise V23Error("launch plan selected-cell freeze does not match the derived A8 plan identity")
    if isinstance(effort, bool) or not isinstance(effort, (int, float)):
        raise V23Error("launch plan has no measured selected effort")
    if not isinstance(selected_geometry, Mapping) or selected_geometry.get("cell_id") != cell_id:
        raise V23Error("launch plan has no selected canonical geometry row")
    canonical_geometry = selected_geometry.get("canonical_geometry")
    realized_params = selected_geometry.get("realized_params")
    if not isinstance(canonical_geometry, Mapping) or not isinstance(realized_params, Mapping):
        raise V23Error("launch plan selected geometry lacks canonical/realized parameters")
    canonical_geometry = validate_canonical_geometry_record(
        canonical_geometry, cell_id=cell_id, realized_params=realized_params
    )
    if selected_geometry.get("geometry_id") != canonical_geometry["geometry_id"]:
        raise V23Error("launch plan selected geometry_id does not match canonical geometry")
    geometry_id_override = _hydra_string(canonical_geometry["geometry_id"])
    effort_vector = _effort_limit_vector(effort)
    checkpoint = checkpoint.resolve()
    effort_input = Path(effort_input).expanduser().resolve()
    atlas_input = Path(atlas_input).expanduser().resolve()
    external_input = Path(external_input).expanduser().resolve()
    selected_cell_freeze_input = Path(selected_cell_freeze_input).expanduser().resolve()
    bands_input = Path(bands_input).expanduser().resolve()
    plain_manifest = Path(plain_manifest).expanduser().resolve()
    output_dir = Path(output_dir).expanduser().resolve()
    bound_plain_manifest_path = output_dir / P05_BOUND_PLAIN_MANIFEST_FILENAME
    bound_plain_manifest = build_bound_plain_manifest_payload(
        read_json(plain_manifest),
        topology=topology,
        selected_geometry=selected_geometry,
    )
    argv = [
        sys.executable,
        "-m",
        "gr00t.rl.eval_agent_trl",
        f"++checkpoint={checkpoint}",
        "++checkpoint_load_mode=policy_only",
        "++auto_load_latest=false",
        "++headless=true",
        "++num_envs=16",
        "++seed=0",
        "++use_wandb=false",
        "++algo.trl.report_to=none",
        "++simulator.config.cameras.enable_cameras=false",
        "++simulator.config.render_results=false",
        "++algo.config.eval.eval_num_envs_episodes=true",
        "++algo.config.eval.num_eval_episodes=16",
        "++algo.config.eval.a2_hold_oracle_enabled=false",
        "++env.config.a2_v20_R2_evidence_enabled=false",
        "++env.config.a2_v23_p0_plain_scenario_enabled=true",
        "++env.config.a2_v23_p0_bound_plain_scenario_enabled=true",
        "++env.config.a2_v23_p05_checkpoint_load_mode=policy_only",
        f"++env.config.a2_v23_p0_scenario_topology={topology}",
        f"++env.config.a2_v23_p0_scenario_manifest_path={bound_plain_manifest_path}",
        f"++env.config.a2_v23_p0_bound_plain_scenario_manifest_path={bound_plain_manifest_path}",
        f"++robot.dof_effort_limit_list=[{','.join(f'{float(value):.6g}' for value in effort_vector)}]",
        "++algo.config.eval.a2_v23_p05_runtime_export=true",
        "++env.config.a2_v23_p05_runtime_enabled=true",
        f"++env.config.a2_v23_p05_purpose={P05_CERTIFICATE}",
        f"++env.config.a2_v23_p05_mode={mode}",
        f"++env.config.a2_v23_p05_topology={topology}",
        f"++env.config.a2_v23_p05_cell_id={cell_id}",
        f"++env.config.a2_v23_p05_geometry_id={geometry_id_override}",
        f"++env.config.a2_v23_p05_hinge_damping_native={repr(float(realized_params['hinge_damping_native']))}",
        f"++env.config.a2_v23_p05_hinge_stiffness_native={repr(float(realized_params['hinge_stiffness_native']))}",
        f"++env.config.a2_v23_p05_hinge_effort_limit_nm={repr(float(realized_params['hinge_effort_limit_nm']))}",
        f"++env.config.a2_v23_p05_door_weight_kg={repr(float(realized_params['door_weight_kg']))}",
        "++env.config.a2_v23_p05_seed=0",
        "++env.config.a2_v23_p05_rescue_effort_nm=100",
        f"++env.config.a2_v23_p05_effort_freeze_path={Path(effort_input)}",
        f"++env.config.a2_v23_p05_atlas_manifest_path={Path(atlas_input)}",
        f"++env.config.a2_v23_p05_external_threshold_path={Path(external_input)}",
        f"++env.config.a2_v23_p05_selected_cell_freeze_path={Path(selected_cell_freeze_input)}",
        f"++env.config.a2_v23_p05_bands_path={Path(bands_input)}",
        f"++env.config.a2_v23_p05_plain_manifest_path={Path(plain_manifest)}",
        f"++env.config.a2_v23_p05_bound_plain_manifest_path={bound_plain_manifest_path}",
        f"++env.config.a2_v23_p05_effort_profile_nm={float(effort):.6g}",
        f"++env.config.a2_v23_p05_checkpoint={P05_WARM_CHECKPOINT}",
        f"++env.config.a2_v23_p05_config_id={V23_WARM_START_CONFIG}",
        f"++eval_output_dir={output_dir}",
    ]
    return argv, {"PYTHONPATH": str(REPO_ROOT), "WANDB_MODE": "disabled"}


def build_d1_probe_argv(
    plan: Mapping[str, Any],
    *,
    output_dir: str | Path,
    effort_input: str | Path,
    external_input: str | Path,
    atlas_input: str | Path | None,
    plain_manifest: str | Path,
    capability_source_freeze_input: str | Path,
) -> tuple[list[str], dict[str, str]]:
    if not isinstance(plan, Mapping) or plan.get("launchable") is not True:
        raise V23Error("D1 capability-source launch requires a READY_TO_LAUNCH plan")
    if plan.get("purpose") != D1_CAPABILITY_SOURCE or plan.get("mode") not in ("FULL", "ACUTE_RP0"):
        raise V23Error("D1 capability-source launch purpose/mode is invalid")
    if plan.get("intervention_contract", {}).get("rescue_forbidden") is not True:
        raise V23Error("D1 capability-source launch must forbid rescue")
    checkpoint = require_file(REPO_ROOT / P05_WARM_CHECKPOINT, label="v22 G1 step1250 warm checkpoint")
    require_file(effort_input, label="real effort freeze")
    require_file(external_input, label="external threshold")
    require_file(plain_manifest, label="plain scenario manifest")
    source_path = Path(capability_source_freeze_input).expanduser().resolve()
    source_freeze = validate_capability_source_freeze(read_json(source_path))
    effort_input = Path(effort_input).expanduser().resolve()
    effort_source_join = _d1_effort_source_join(
        effort_input=effort_input,
        effort_payload=read_json(effort_input),
        source_freeze=source_freeze,
    )
    if plan.get("effort_source_join") != effort_source_join:
        raise V23Error("D1 capability-source launch plan effort join disagrees with supplied inputs")
    if plan.get("effort_freeze", {}).get("selected_effort_nm") != effort_source_join["effort_selected_effort_nm"]:
        raise V23Error("D1 capability-source launch plan selected effort disagrees with supplied effort freeze")
    external_input = Path(external_input).expanduser().resolve()
    if source_freeze["source_paths"].get("external_threshold") != str(external_input):
        raise V23Error("D1 capability-source freeze external path does not match the supplied threshold input")
    output_dir = Path(output_dir).expanduser().resolve()
    bound_plain_manifest_path = output_dir / P05_D1_BOUND_MANIFEST_FILENAME
    bound_plain_manifest = build_d1_capability_bound_plain_manifest_payload(
        read_json(plain_manifest),
        topology=plan["topology"],
        capability_source_freeze=source_freeze,
        capability_source_freeze_path=source_path,
    )
    selected_geometry = plan["selected_geometry"]
    geometry_id_override = _hydra_string(selected_geometry["geometry_id"])
    requested = selected_geometry["requested_params"]
    native = selected_geometry["realized_params"]
    effort_vector = _effort_limit_vector(plan["effort_freeze"]["selected_effort_nm"])
    argv = [
        sys.executable,
        "-m",
        "gr00t.rl.eval_agent_trl",
        f"++checkpoint={checkpoint}",
        "++checkpoint_load_mode=policy_only",
        "++auto_load_latest=false",
        "++headless=true",
        "++num_envs=16",
        "++seed=0",
        "++use_wandb=false",
        "++algo.trl.report_to=none",
        "++simulator.config.cameras.enable_cameras=false",
        "++simulator.config.render_results=false",
        "++algo.config.eval.eval_num_envs_episodes=true",
        "++algo.config.eval.num_eval_episodes=16",
        "++env.config.a2_v20_R2_evidence_enabled=false",
        "++env.config.a2_v23_p0_plain_scenario_enabled=true",
        "++env.config.a2_v23_p0_bound_plain_scenario_enabled=true",
        "++env.config.a2_v23_p05_checkpoint_load_mode=policy_only",
        f"++env.config.a2_v23_p0_scenario_topology={plan['topology']}",
        f"++env.config.a2_v23_p0_scenario_manifest_path={bound_plain_manifest_path}",
        f"++env.config.a2_v23_p0_bound_plain_scenario_manifest_path={bound_plain_manifest_path}",
        f"++robot.dof_effort_limit_list=[{','.join(f'{float(value):.6g}' for value in effort_vector)}]",
        "++algo.config.eval.a2_v23_p05_runtime_export=true",
        "++env.config.a2_v23_p05_runtime_enabled=true",
        "++env.config.a2_v23_p05_seed=0",
        f"++env.config.a2_v23_p05_purpose={D1_CAPABILITY_SOURCE}",
        f"++env.config.a2_v23_p05_mode={plan['mode']}",
        f"++env.config.a2_v23_p05_topology={plan['topology']}",
        "++env.config.a2_v23_p05_cell_id=A0",
        f"++env.config.a2_v23_p05_geometry_id={geometry_id_override}",
        f"++env.config.a2_v23_p05_requested_hinge_damping_native={repr(float(requested['hinge_damping_native']))}",
        f"++env.config.a2_v23_p05_requested_hinge_stiffness_native={repr(float(requested['hinge_stiffness_native']))}",
        f"++env.config.a2_v23_p05_requested_hinge_max_force_nm={repr(float(requested['hinge_max_force_nm']))}",
        f"++env.config.a2_v23_p05_requested_door_weight_kg={repr(float(requested['door_weight_kg']))}",
        f"++env.config.a2_v23_p05_hinge_damping_native={repr(float(native['hinge_damping_native']))}",
        f"++env.config.a2_v23_p05_hinge_stiffness_native={repr(float(native['hinge_stiffness_native']))}",
        f"++env.config.a2_v23_p05_hinge_effort_limit_nm={repr(float(native['hinge_effort_limit_nm']))}",
        f"++env.config.a2_v23_p05_door_weight_kg={repr(float(native['door_weight_kg']))}",
        f"++env.config.a2_v23_p05_effort_freeze_path={Path(effort_input).expanduser().resolve()}",
        f"++env.config.a2_v23_p05_external_threshold_path={external_input}",
        f"++env.config.a2_v23_p05_atlas_manifest_path={Path(atlas_input).expanduser().resolve() if atlas_input is not None else source_freeze['source_paths']['atlas']}",
        f"++env.config.a2_v23_p05_plain_manifest_path={Path(plain_manifest).expanduser().resolve()}",
        f"++env.config.a2_v23_p05_bound_plain_manifest_path={bound_plain_manifest_path}",
        f"++env.config.a2_v23_p05_capability_source_freeze_path={source_path}",
        f"++env.config.a2_v23_p05_effort_profile_nm={float(plan['effort_freeze']['selected_effort_nm']):.6g}",
        f"++env.config.a2_v23_p05_checkpoint={P05_WARM_CHECKPOINT}",
        f"++env.config.a2_v23_p05_config_id={V23_WARM_START_CONFIG}",
        f"++eval_output_dir={output_dir}",
    ]
    return argv, {"PYTHONPATH": str(REPO_ROOT), "WANDB_MODE": "disabled"}


def pair_forward_records(full_record: Mapping[str, Any], rescue_record: Mapping[str, Any]) -> dict[str, Any]:
    """Pair two independently produced episodes using direct prefix equality."""

    full_key = _episode_identity_key(full_record)
    rescue_key = _episode_identity_key(rescue_record)
    if full_key != rescue_key:
        raise V23Error("FULL/rescue pair identity sets must match exactly")
    full_env_id, full_episode_index = _episode_provenance(full_record)
    rescue_env_id, rescue_episode_index = _episode_provenance(rescue_record)
    if (full_env_id, full_episode_index) != (rescue_env_id, rescue_episode_index):
        raise V23Error("FULL/rescue pair must share exact env_id and episode_index")
    result = a2_v23_validate_p05_prefix(full_record, rescue_record)
    result["env_id"] = full_env_id
    result["episode_index"] = full_episode_index
    result["plain_prefix_id"] = full_record["plain_prefix_id"]
    result["source_runs"] = {
        "full": full_record.get("run_id", "UNREGISTERED_RUN_ID"),
        "rescue": rescue_record.get("run_id", "UNREGISTERED_RUN_ID"),
    }
    result["filename_equality_used"] = False
    result["state_clone_used"] = False
    result["source_records"] = {
        "full": dict(full_record),
        "rescue": dict(rescue_record),
    }
    return result


def pair_forward_record_set(
    full_records: Sequence[Mapping[str, Any]],
    rescue_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Recompute every FULL/rescue pair in an identity-complete export."""

    full_records = _validate_episode_export_records(full_records, expected_mode="FULL")
    rescue_records = _validate_episode_export_records(
        rescue_records, expected_mode="HIGHER_EFFORT_RESCUE"
    )
    full_by_key: dict[tuple[Any, ...], Mapping[str, Any]] = {}
    rescue_by_key: dict[tuple[Any, ...], Mapping[str, Any]] = {}
    for record in full_records:
        key = _episode_identity_key(record)
        if key in full_by_key:
            raise V23Error("duplicate FULL experimental identity")
        full_by_key[key] = record
    for record in rescue_records:
        key = _episode_identity_key(record)
        if key in rescue_by_key:
            raise V23Error("duplicate HIGHER_EFFORT_RESCUE experimental identity")
        rescue_by_key[key] = record
    if set(full_by_key) != set(rescue_by_key):
        raise V23Error("FULL/rescue pair identity sets must match exactly")
    pairs = []
    source_full = []
    source_rescue = []
    for key in sorted(full_by_key, key=str):
        full_record = full_by_key[key]
        rescue_record = rescue_by_key[key]
        pair = pair_forward_records(full_record, rescue_record)
        pair.pop("source_records", None)
        pairs.append(pair)
        source_full.append(dict(full_record))
        source_rescue.append(dict(rescue_record))
    return {
        "schema": P05_PAIR_EXPORT_SCHEMA,
        "status": "PASS",
        "record_count": len(pairs),
        "pairs": pairs,
        "source_records": {
            "FULL": source_full,
            "HIGHER_EFFORT_RESCUE": source_rescue,
        },
    }


def _records_from_payload(
    payload: Mapping[str, Any], *, expected_mode: str
) -> list[Mapping[str, Any]]:
    return _episode_export_records(payload, expected_mode=expected_mode)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("PLAN", "RUN", "PAIR", "BUNDLE"), default="PLAN")
    parser.add_argument("--purpose", choices=(P05_CERTIFICATE, D1_CAPABILITY_SOURCE), default=P05_CERTIFICATE)
    parser.add_argument("--probe-mode", choices=V23_P05_MODES, default="FULL")
    parser.add_argument("--topology", choices=P05_TOPOLOGIES, default="canonical16")
    parser.add_argument("--effort-input", type=Path, default=None)
    parser.add_argument("--atlas-input", type=Path, default=None)
    parser.add_argument("--external-threshold", type=Path, default=None)
    parser.add_argument("--selected-cell-freeze", type=Path, default=None)
    parser.add_argument("--capability-source-freeze", type=Path, default=None)
    parser.add_argument("--bands", type=Path, default=None)
    parser.add_argument("--plain-manifest", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=Path("/tmp/v23_p05_impl_r1/run"))
    parser.add_argument("--full-input", type=Path, default=None)
    parser.add_argument("--acute-input", type=Path, default=None)
    parser.add_argument("--rescue-input", type=Path, default=None)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    if args.mode == "PAIR":
        if args.purpose != P05_CERTIFICATE:
            raise V23Error("PAIR is available only for P05_CERTIFICATE")
        if args.full_input is None or args.rescue_input is None:
            raise V23Error("PAIR requires --full-input and --rescue-input episode artifacts.")
        full_records = _records_from_payload(read_json(args.full_input), expected_mode="FULL")
        rescue_records = _records_from_payload(
            read_json(args.rescue_input), expected_mode="HIGHER_EFFORT_RESCUE"
        )
        pair = pair_forward_record_set(full_records, rescue_records)
        emit_payload(
            pair,
            args.out,
        )
        return 0

    if args.mode == "BUNDLE":
        if args.purpose != P05_CERTIFICATE:
            raise V23Error("BUNDLE is available only for P05_CERTIFICATE")
        if args.full_input is None or args.acute_input is None or args.rescue_input is None:
            raise V23Error("BUNDLE requires --full-input, --acute-input, and --rescue-input exports.")
        bands = read_json(args.bands) if args.bands is not None else None
        bundle = build_three_mode_bundle(
            read_json(args.full_input),
            read_json(args.acute_input),
            read_json(args.rescue_input),
            bands=bands,
        )
        emit_payload(bundle, args.out)
        return 0

    bands = read_json(args.bands) if args.bands is not None else None
    plan = build_probe_plan(
        mode=args.probe_mode,
        topology=args.topology,
        effort_input=args.effort_input,
        atlas_input=args.atlas_input,
        external_input=args.external_threshold,
        bands=bands,
        output_dir=args.output_dir,
        plain_manifest=args.plain_manifest,
        selected_cell_freeze=args.selected_cell_freeze,
        purpose=args.purpose,
        capability_source_freeze=args.capability_source_freeze,
    )
    if args.mode == "RUN":
        if not args.execute:
            plan["status"] = "PLAN_ONLY_EXECUTE_FLAG_REQUIRED"
        elif not plan.get("launchable"):
            raise V23Error("RUN is nonlaunchable until real effort/atlas/bands/plain inputs are supplied.")
        else:
            required_certificate_inputs = (
                args.atlas_input is not None
                and args.bands is not None
                and args.external_threshold is not None
                and args.selected_cell_freeze is not None
            )
            required_d1_inputs = (
                args.purpose == D1_CAPABILITY_SOURCE
                and args.external_threshold is not None
                and args.capability_source_freeze is not None
            )
            if (
                args.plain_manifest is None
                or args.effort_input is None
                or (args.purpose == P05_CERTIFICATE and not required_certificate_inputs)
                or (args.purpose == D1_CAPABILITY_SOURCE and not required_d1_inputs)
            ):
                raise V23Error("RUN requires the exact purpose-specific freeze and manifest inputs.")
            argv_run, env = build_probe_argv(
                plan,
                output_dir=args.output_dir,
                effort_input=args.effort_input,
                atlas_input=args.atlas_input,
                external_input=args.external_threshold,
                selected_cell_freeze_input=args.selected_cell_freeze,
                bands_input=args.bands,
                plain_manifest=args.plain_manifest,
                purpose=args.purpose,
                capability_source_freeze_input=args.capability_source_freeze,
            )
            args.output_dir.mkdir(parents=True, exist_ok=True)
            if args.purpose == P05_CERTIFICATE:
                materialize_bound_plain_manifest(
                    args.output_dir / P05_BOUND_PLAIN_MANIFEST_FILENAME,
                    source_payload=read_json(args.plain_manifest),
                    topology=args.topology,
                    selected_geometry=plan["selected_geometry"],
                )
            else:
                materialize_d1_capability_bound_plain_manifest(
                    args.output_dir / P05_D1_BOUND_MANIFEST_FILENAME,
                    source_payload=read_json(args.plain_manifest),
                    topology=args.topology,
                    capability_source_freeze=read_json(args.capability_source_freeze),
                    capability_source_freeze_path=args.capability_source_freeze,
                )
            completed = subprocess.run(argv_run, cwd=REPO_ROOT, env={**os.environ, **env}, check=False)
            plan["run_returncode"] = int(completed.returncode)
            plan["status"] = "RUN_COMPLETED" if completed.returncode == 0 else "RUN_FAILED"
    emit_payload(plan, args.out)
    if args.mode == "RUN" and "run_returncode" in plan:
        return int(plan["run_returncode"])
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except V23Error as exc:
        raise SystemExit(f"V23 P0.5 RESCUE PROBE FAIL: {exc}")
