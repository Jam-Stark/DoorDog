"""Versioned v21-B artifact schemas; v20 artifacts are intentionally rejected."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ._v21b_common import V21B_ARTIFACT_SCHEMA_PREFIX, V21B_EXECUTION_ID, V21B_PLAN_ID, V21BError, canonical_json_bytes


SCHEMAS = {
    "p0_admission": "a2_piper_base_v21B_p0_admission_v1",
    "source_lock": "a2_piper_base_v21B_source_lock_v1",
    "heavy_manifest": "a2_piper_base_v21B_heavy16_manifest_v1",
    "census": "a2_piper_base_v21B_torque_census_v1",
    "zero_shot": "a2_piper_base_v21B_zero_shot_v1",
    "arm_tie": "a2_piper_base_v21B_arm_tie_calibration_v1",
    "pilot": "a2_piper_base_v21B_B4_pilot_v1",
    "adaptation": "a2_piper_base_v21B_adaptation_freeze_v1",
    "materialization": "a2_piper_base_v21B_runtime_config_materialization_v1",
    "smoke_plan": "a2_piper_base_v21B_B4_smoke_plan_v1",
    "smoke_adjudication": "a2_piper_base_v21B_B4_smoke_adjudication_v1",
    "smoke_cleanup": "a2_piper_base_v21B_smoke_cleanup_manifest_v1",
    "formal_plan": "a2_piper_base_v21B_formal_launch_plan_v1",
    "startup_monitor": "a2_piper_base_v21B_iteration50_monitor_v1",
}

STATUSES = frozenset({
    "STATIC_PASS", "PENDING_CENSUS", "CENSUS_PASS", "CENSUS_RIGHT_CENSORED",
    "BOUNDARY_NOT_SEPARABLE", "ZERO_SHOT_COMPLETE", "CALIBRATION_PASS", "CALIBRATION_DEFERRED",
    "PILOT_COMPLETE", "ADAPTATION_FROZEN", "SMOKE_PLAN_COMPLETE", "SMOKE_PASS",
    "FORMAL_PLAN_COMPLETE", "MATERIALIZATION_PASS", "CLEANUP_PASS", "STARTUP_50_PASS", "MONITOR_DETACHED", "INCONCLUSIVE",
})


def schema(name: str) -> str:
    if name not in SCHEMAS:
        raise V21BError(f"unknown v21-B schema name: {name!r}")
    return SCHEMAS[name]


def validate_artifact(value: Mapping[str, Any], *, expected_schema: str | None = None, expected_cell: str | None = None, require_source_hash: str | None = None) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise V21BError("v21-B artifact must be a mapping")
    actual_schema = value.get("schema")
    if not isinstance(actual_schema, str) or not actual_schema.startswith(V21B_ARTIFACT_SCHEMA_PREFIX):
        raise V21BError("artifact is not in the v21-B schema namespace; v20 artifacts are rejected")
    if expected_schema is not None and actual_schema != expected_schema:
        raise V21BError(f"artifact schema mismatch: expected {expected_schema!r}, got {actual_schema!r}")
    if value.get("plan_id") != V21B_PLAN_ID or value.get("execution_id") != V21B_EXECUTION_ID:
        raise V21BError("artifact plan/execution binding is not v21-B")
    if expected_cell is not None and value.get("cell") != expected_cell:
        raise V21BError(f"artifact cell mismatch: expected {expected_cell!r}")
    if "status" in value and value["status"] not in STATUSES:
        raise V21BError(f"unsupported v21-B artifact status: {value['status']!r}")
    if require_source_hash is not None and value.get("source_checkpoint_sha256") != require_source_hash:
        raise V21BError("artifact warm-start source hash mismatch")
    if "authority" in value and value["authority"] != "ESTIMATE_ONLY_ACTUAL_PHYSX_DRIVE_FORCE_UNAVAILABLE":
        raise V21BError("arm artifact authority is not estimate-only")
    return dict(value)


def artifact_payload(name: str, *, status: str, cell: str | None = None, **fields: Any) -> dict[str, Any]:
    if status not in STATUSES:
        raise V21BError(f"unsupported status {status!r}")
    result: dict[str, Any] = {
        "schema": schema(name), "plan_id": V21B_PLAN_ID, "execution_id": V21B_EXECUTION_ID, "status": status,
    }
    if cell is not None:
        result["cell"] = cell
    result.update(fields)
    validate_artifact(result, expected_schema=schema(name), expected_cell=cell)
    return result


def artifact_bytes(value: Mapping[str, Any]) -> bytes:
    validate_artifact(value)
    return canonical_json_bytes(value) + b"\n"


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["SCHEMAS", "STATUSES", "schema", "validate_artifact", "artifact_payload", "artifact_bytes", "main"]
