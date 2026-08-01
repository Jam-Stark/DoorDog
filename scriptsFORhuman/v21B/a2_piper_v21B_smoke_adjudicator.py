"""Strict adjudication for the one B4 smoke attempt."""

from __future__ import annotations

import math
import hashlib
from typing import Any, Mapping

from ._v21b_common import V21BError, V21B_PLAN_ID, canonical_json_bytes
from .a2_piper_v21B_schemas import artifact_payload, schema, validate_artifact
from gr00t.rl.envs.door.a2_v21b_evidence import a2_v21b_validate_terminal_record


def adjudicate_b4_smoke(plan: Mapping[str, Any], result: Mapping[str, Any]) -> dict[str, Any]:
    validate_artifact(plan, expected_schema=schema("smoke_plan"), expected_cell="B4")
    if plan.get("num_envs") != 64 or plan.get("batches") != 10 or plan.get("save_frequency") != 10 or plan.get("one_cell_only") is not True:
        raise V21BError("smoke plan dimensions are not exactly B4/64/10/save10")
    if not isinstance(result, Mapping) or result.get("cell") != "B4":
        raise V21BError("smoke result must bind B4")
    unsigned_plan = dict(plan)
    unsigned_plan.pop("plan_sha256", None)
    expected_plan_sha = hashlib.sha256(canonical_json_bytes(unsigned_plan)).hexdigest()
    if plan.get("plan_sha256") != expected_plan_sha:
        raise V21BError("smoke plan digest is invalid")
    for key in ("exit_code", "process_natural_exit", "completed_batches", "batch_indices", "finite_data", "decomposition_sanity", "checkpoint_path", "checkpoint_sha256", "telemetry", "plan_sha256", "command_sha256", "materialization_sha256", "materialized_config_sha256", "source_checkpoint_sha256", "source_lock_sha256", "source_config_sha256"):
        if key not in result:
            raise V21BError(f"smoke result missing {key}")
    if result["exit_code"] != 0 or result["process_natural_exit"] is not True or result["completed_batches"] != 10 or result["batch_indices"] != list(range(1, 11)) or result["finite_data"] is not True or result["decomposition_sanity"] is not True:
        raise V21BError("B4 smoke did not complete the exact finite 10-batch contract")
    if not isinstance(result["checkpoint_path"], str) or not result["checkpoint_path"]:
        raise V21BError("B4 smoke did not report a checkpoint path")
    if not isinstance(result["checkpoint_sha256"], str) or len(result["checkpoint_sha256"]) != 64:
        raise V21BError("B4 smoke checkpoint digest is missing")
    telemetry = result["telemetry"]
    if not isinstance(telemetry, Mapping):
        raise V21BError("B4 smoke telemetry export is missing")
    a2_v21b_validate_terminal_record(telemetry)
    if telemetry.get("plan_id") != V21B_PLAN_ID or telemetry.get("cell") != "B4" or telemetry.get("group") != "B4" or telemetry.get("seed") != 0:
        raise V21BError("B4 smoke telemetry is not bound to v21-B B4 seed0")
    if telemetry.get("source_checkpoint_sha256") != plan.get("source_checkpoint_sha256") or telemetry.get("adaptation_bundle_sha256") != plan.get("adaptation_bundle_sha256") or telemetry.get("materialization_phase") != "FORMAL_PROMOTED":
        raise V21BError("B4 smoke telemetry source/adaptation/phase binding is invalid")
    provenance = telemetry.get("provenance")
    if not isinstance(provenance, Mapping) or provenance.get("source_checkpoint_sha256") != plan.get("source_checkpoint_sha256") or provenance.get("source_lock_sha256") != plan.get("source_lock_sha256") or provenance.get("materialization_sha256") != plan.get("materialization_sha256") or provenance.get("materialized_config_sha256") != plan.get("materialized_config_sha256") or provenance.get("source_config_sha256") != plan.get("source_config_sha256"):
        raise V21BError("B4 smoke telemetry is not bound to the exact materialized receipt/config")
    if result["plan_sha256"] != plan["plan_sha256"] or result["command_sha256"] != plan["command_sha256"]:
        raise V21BError("B4 smoke result-to-plan/command hash binding is invalid")
    if result["materialization_sha256"] != plan["materialization_sha256"] or result["materialized_config_sha256"] != plan["materialized_config_sha256"] or result["source_checkpoint_sha256"] != plan["source_checkpoint_sha256"] or result["source_lock_sha256"] != plan["source_lock_sha256"] or result["source_config_sha256"] != plan["source_config_sha256"]:
        raise V21BError("B4 smoke result provenance is not bound to plan")
    for key, value in result.items():
        if isinstance(value, float) and not math.isfinite(value):
            raise V21BError(f"smoke metric {key} is non-finite")
    return artifact_payload("smoke_adjudication", status="SMOKE_PASS", cell="B4", plan_sha256=plan["plan_sha256"], command_sha256=plan["command_sha256"], materialization_sha256=plan["materialization_sha256"], materialized_config_sha256=plan["materialized_config_sha256"], source_checkpoint_sha256=plan["source_checkpoint_sha256"], source_lock_sha256=plan["source_lock_sha256"], source_config_sha256=plan["source_config_sha256"], result=dict(result), runtime_level="RUNTIME_SMOKE_PASS")


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["adjudicate_b4_smoke", "main"]
