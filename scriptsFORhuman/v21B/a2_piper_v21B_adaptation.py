"""One-shot v21-B adaptation decision and immutable freeze."""

from __future__ import annotations

import argparse
import copy
import hashlib
import math
from pathlib import Path
from typing import Any, Mapping

import yaml

from ._v21b_common import V21B_CELL_FACTORS, V21B_CELL_ORDER, V21B_CONFIG_PATHS, V21B_EVAL_CONTRACT_PATH, V21B_F3_THETA_LADDER, V21B_PLAN_ID, V21BError, canonical_json_bytes, read_yaml, require_digest, sha256_file, validate_v21b_config
from .a2_piper_v21B_schemas import artifact_payload, schema, validate_artifact
from .a2_piper_v21B_source_freeze import validate_source_lock


ARM_TIE_PREREGISTERED_FALLBACK = 8
V21B_EVAL_CONTRACT_DIAGNOSTIC_KEYS = frozenset(
    {
        "a2_diagnostic_trace_enabled",
        "a2_diagnostic_reward_terms",
        "a2_forced_gripper_close_enabled",
        "a2_forced_gripper_close_value",
        "a2_forced_gripper_close_stages",
    }
)
V21B_EVAL_CONTRACT_DISABLED_FLAGS = frozenset(
    {
        "a2_hold_oracle_enabled",
        "a2_v20_arc_probe_enabled",
        "a2_forced_gripper_close_enabled",
        "a2_hold_oracle_static_clamp_enabled",
        "a2_hold_oracle_static_clamp_offset_probe_enabled",
        "a2_hold_oracle_open_stabilization_preflight_enabled",
        "a2_hold_oracle_matched_clean_reacquisition_preflight_enabled",
        "a2_eval_m41_strict_telemetry",
        "a2_eval_v20_strict_telemetry",
        "a2_diagnostic_trace_enabled",
    }
)


def _validate_eval_contract_mapping(value: Any, *, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise V21BError(f"{label} must be a mapping")
    result = dict(value)
    if any(not isinstance(key, str) or not key for key in result):
        raise V21BError(f"{label} keys must be non-empty strings")
    if any(item is None for item in result.values()):
        raise V21BError(f"{label} cannot contain null values")
    for key, item in result.items():
        if key.endswith("_steps"):
            if isinstance(item, bool) or not isinstance(item, int) or item <= 0:
                raise V21BError(f"{label}.{key} must be a positive int")
        elif key.startswith("a2_hold_oracle_") and key not in V21B_EVAL_CONTRACT_DISABLED_FLAGS:
            if isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(float(item)):
                raise V21BError(f"{label}.{key} must be a finite number")
            if key != "a2_hold_oracle_static_clamp_offset_m" and float(item) <= 0.0:
                raise V21BError(f"{label}.{key} must be positive")
    for key in V21B_EVAL_CONTRACT_DISABLED_FLAGS:
        if key in result and result[key] is not False:
            raise V21BError(f"{label}.{key} must remain exactly false for v21-B runtime")
    if "a2_diagnostic_reward_terms" in result:
        terms = result["a2_diagnostic_reward_terms"]
        if not isinstance(terms, list) or any(not isinstance(term, str) or not term for term in terms):
            raise V21BError(f"{label}.a2_diagnostic_reward_terms must be a list of strings")
    if "a2_forced_gripper_close_stages" in result:
        stages = result["a2_forced_gripper_close_stages"]
        if not isinstance(stages, list) or any(isinstance(stage, bool) or not isinstance(stage, int) for stage in stages):
            raise V21BError(f"{label}.a2_forced_gripper_close_stages must be a list of ints")
    if "a2_v20_arc_probe_mode" in result and result["a2_v20_arc_probe_mode"] not in ("F0", "F1"):
        raise V21BError(f"{label}.a2_v20_arc_probe_mode must be exactly F0 or F1")
    if "a2_eval_p2_posture_axis" in result and result["a2_eval_p2_posture_axis"] not in ("none", "pitch_zero", "roll_zero"):
        raise V21BError(f"{label}.a2_eval_p2_posture_axis is unsupported")
    return result


def _load_source_locked_eval_contract(root: Path, source_lock: Mapping[str, Any]) -> tuple[dict[str, Any], str]:
    validate_source_lock(dict(source_lock), root, require_current=True)
    path = root / V21B_EVAL_CONTRACT_PATH
    source_digest = sha256_file(path)
    rows = source_lock.get("source_paths")
    if not isinstance(rows, list):
        raise V21BError("source lock lacks source_paths for eval contract")
    row = next((item for item in rows if isinstance(item, Mapping) and item.get("path") == V21B_EVAL_CONTRACT_PATH), None)
    if not isinstance(row, Mapping) or row.get("sha256") != source_digest:
        raise V21BError("source lock does not bind the current base_eval.yaml digest")
    source = read_yaml(path)
    algo = source.get("algo")
    if not isinstance(algo, Mapping) or not isinstance(algo.get("config"), Mapping):
        raise V21BError("base_eval.yaml must contain algo.config mapping")
    eval_contract = _validate_eval_contract_mapping(algo["config"].get("eval"), label="base_eval.yaml algo.config.eval")
    required = [key for key in eval_contract if key.startswith("a2_hold_oracle_") or key.startswith("a2_v20_arc_probe_") or key in V21B_EVAL_CONTRACT_DIAGNOSTIC_KEYS]
    if not required:
        raise V21BError("base_eval.yaml eval contract lacks required A2 diagnostic/oracle keys")
    return eval_contract, source_digest


def _merge_eval_contract(config: dict[str, Any], eval_contract: Mapping[str, Any]) -> list[str]:
    algo = config.get("algo")
    if not isinstance(algo, Mapping) or not isinstance(algo.get("config"), Mapping):
        raise V21BError("materialized config must contain algo.config mapping")
    target_config = algo["config"]
    target_eval = target_config.get("eval")
    if not isinstance(target_eval, Mapping):
        raise V21BError("materialized config must contain algo.config.eval mapping")
    copied: list[str] = []
    for key, value in eval_contract.items():
        if key not in target_eval:
            target_eval[key] = copy.deepcopy(value)
            copied.append(key)
    for key in eval_contract:
        if key.startswith("a2_hold_oracle_") or key.startswith("a2_v20_arc_probe_") or key in V21B_EVAL_CONTRACT_DIAGNOSTIC_KEYS:
            if target_eval.get(key) != eval_contract[key]:
                raise V21BError(f"materialized eval contract key {key} conflicts with base_eval.yaml")
    return copied


def validate_preformal_bindings(
    *,
    p0_admission: Mapping[str, Any],
    source_lock: Mapping[str, Any],
    census: Mapping[str, Any] | None = None,
    zero_shot: Mapping[str, Any] | None = None,
    pilot: Mapping[str, Any] | None = None,
    arm_tie: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Require all completed signed artifacts and exact cross-bindings."""

    validate_artifact(p0_admission, expected_schema=schema("p0_admission"))
    validate_artifact(source_lock, expected_schema=schema("source_lock"))
    if census is None:
        raise V21BError("pre-formal binding requires a census artifact")
    validate_artifact(census, expected_schema=schema("census"))
    census_status = census.get("status")
    if census_status not in {"CENSUS_PASS", "CENSUS_RIGHT_CENSORED", "BOUNDARY_NOT_SEPARABLE"}:
        raise V21BError(f"census artifact is not a signed terminal census result: {census_status!r}")
    f3_fallback = census_status in {"CENSUS_RIGHT_CENSORED", "BOUNDARY_NOT_SEPARABLE"}
    if f3_fallback and census.get("selection") not in ("N/A", None):
        raise V21BError("F3 census status must not carry a numeric or arbitrary selected k")
    expected_statuses = {
        "census": {census_status},
        "zero_shot": {"ZERO_SHOT_COMPLETE"},
        "pilot": {"PILOT_COMPLETE"},
        "arm_tie": {"CALIBRATION_PASS", "CALIBRATION_DEFERRED"},
    }
    artifacts = {"census": census, "zero_shot": zero_shot, "pilot": pilot, "arm_tie": arm_tie}
    validate_artifact(census, expected_schema=schema("census"))
    if not f3_fallback:
        for name in ("zero_shot", "pilot", "arm_tie"):
            value = artifacts[name]
            if value is None:
                raise V21BError(f"{name} artifact is required for CENSUS_PASS")
            validate_artifact(value, expected_schema=schema(name))
            if value.get("status") not in expected_statuses[name]:
                raise V21BError(f"{name} artifact is not complete: {value.get('status')!r}")
    source_hash = p0_admission.get("source_checkpoint_sha256")
    source_lock_hash = source_lock.get("source_lock_sha256")
    try:
        require_digest(source_hash, name="P0 source checkpoint")
    except V21BError as exc:
        raise V21BError("P0 admission lacks the signed source checkpoint hash") from exc
    if source_lock.get("source_checkpoint_sha256") != source_hash:
        raise V21BError("source lock and P0 source checkpoint hashes disagree")
    try:
        require_digest(source_lock_hash, name="source lock")
    except V21BError as exc:
        raise V21BError("source lock lacks its signed digest") from exc
    for name, value in artifacts.items():
        if value is None:
            continue
        if value.get("source_checkpoint_sha256") != source_hash:
            raise V21BError(f"{name} source checkpoint hash is not bound to P0")
        if value.get("source_lock_sha256") != source_lock_hash:
            raise V21BError(f"{name} source lock hash is not bound to the frozen source")
    config_hashes = p0_admission.get("config_sha256_by_cell")
    if not isinstance(config_hashes, Mapping) or set(config_hashes) != set(V21B_CELL_ORDER):
        raise V21BError("P0 admission lacks exact seven-cell config hashes")
    source_rows = source_lock.get("source_paths")
    if not isinstance(source_rows, list):
        raise V21BError("source lock lacks source_paths")
    source_map = {row.get("path"): row.get("sha256") for row in source_rows if isinstance(row, Mapping)}
    for cell, relative in V21B_CONFIG_PATHS.items():
        if source_map.get(relative) != config_hashes[cell]:
            raise V21BError(f"source lock config hash mismatch for {cell}")
    required_config_bindings = {"census": "B1", "zero_shot": "B4", "pilot": "B4", "arm_tie": "B7"}
    for name, cell in required_config_bindings.items():
        if f3_fallback and name != "census":
            continue
        if artifacts[name].get("source_config_sha256") != config_hashes[cell]:
            raise V21BError(f"{name} artifact is not bound to the expected {cell} config")
    for name in ("zero_shot", "pilot"):
        if f3_fallback:
            continue
        value = artifacts[name]
        if value.get("materialization_phase") != "POST_CENSUS":
            raise V21BError(f"{name} artifact must be bound to POST_CENSUS materialization")
        for key in ("materialization_sha256", "materialized_config_sha256"):
            digest = value.get(key)
            if not isinstance(digest, str) or len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
                raise V21BError(f"{name} artifact lacks a signed {key}")
        vector = value.get("effort_limit_vector_6d")
        if not isinstance(vector, list) or len(vector) != 6 or any(isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(float(item)) or float(item) <= 0.0 for item in vector):
            raise V21BError(f"{name} artifact lacks the selected six-joint effort vector")
        if value.get("arm_realistic_limit_nm") != float(census.get("selection")) or vector != [float(census.get("selection"))] * 6:
            raise V21BError(f"{name} artifact selected k/vector is not bound to the signed census selection")
        command_hash = value.get("command_sha256")
        command_hashes = command_hash if isinstance(command_hash, list) else [command_hash]
        if not isinstance(value.get("plan_sha256"), str) or len(value["plan_sha256"]) != 64 or any(char not in "0123456789abcdef" for char in value["plan_sha256"]) or any(not isinstance(item, str) or len(item) != 64 or any(char not in "0123456789abcdef" for char in item) for item in command_hashes):
            raise V21BError(f"{name} artifact lacks its signed plan/command hash")
    if not f3_fallback:
        for key in ("materialization_sha256", "materialized_config_sha256", "effort_limit_vector_6d"):
            if zero_shot.get(key) != pilot.get(key):
                raise V21BError("zero-shot and pilot are not bound to the exact same POST_CENSUS receipt/vector")
    return {"source_checkpoint_sha256": source_hash, "source_lock_sha256": source_lock_hash, "config_sha256_by_cell": dict(config_hashes), "census_status": census_status, "f3_fallback": f3_fallback}


def freeze_adaptation(*, p0_admission: Mapping[str, Any], source_lock: Mapping[str, Any], census: Mapping[str, Any], zero_shot: Mapping[str, Any] | None = None, pilot: Mapping[str, Any] | None = None, arm_tie: Mapping[str, Any] | None = None) -> dict[str, Any]:
    bindings = validate_preformal_bindings(p0_admission=p0_admission, source_lock=source_lock, census=census, zero_shot=zero_shot, pilot=pilot, arm_tie=arm_tie)
    if bindings["f3_fallback"]:
        decision = {
            "mode": "THETA_ONLY_FALLBACK_F3",
            "census_status": bindings["census_status"],
            "theta_ladder": dict(V21B_F3_THETA_LADDER),
            "theta_high_rad": None,
            "theta_reason": "census boundary is censored or not separable; arm profile remains ARM_V20",
            "arm_realistic_limit_nm": None,
            "arm_tie_multiplier": None,
            "b7_arm_tie_enabled": False,
            "arm_tie_fallback_used": True,
            "b7_replicate_of": None,
            "dv4_tested": False,
            "immutable_after_freeze": True,
        }
        return artifact_payload("adaptation", status="ADAPTATION_FROZEN", decision=decision, enabled_cells=list(V21B_CELL_ORDER), source_checkpoint_sha256=bindings["source_checkpoint_sha256"], source_lock_sha256=bindings["source_lock_sha256"], config_sha256_by_cell=bindings["config_sha256_by_cell"], source_artifacts={"p0_admission": p0_admission, "source_lock": source_lock, "census": census, "zero_shot": None, "pilot": None, "arm_tie": None})
    selected_limit = census.get("selection")
    if not isinstance(selected_limit, (int, float)) or isinstance(selected_limit, bool):
        raise V21BError("adaptation cannot freeze without a numeric ARM_REALISTIC census selection")
    if pilot.get("fork_f4_theta_downgrade") is True:
        theta_high = 1.10
        theta_reason = "F4 pilot send-latch rate below 60%"
    else:
        theta_high = 1.20
        theta_reason = "B4 pilot retained pre-registered theta=1.20"
    arm_tie_multiplier = arm_tie.get("selected_multiplier")
    b7_arm_tie = isinstance(arm_tie_multiplier, int) and not isinstance(arm_tie_multiplier, bool) and arm_tie_multiplier > 0 and arm_tie.get("status") == "CALIBRATION_PASS"
    if zero_shot.get("fork_f2_arm_axis_collapse") is True:
        raise V21BError("F2 arm-axis collapse requires a new theta-ladder plan; formal freeze is blocked")
    decision = {
        "theta_high_rad": theta_high,
        "theta_reason": theta_reason,
        "arm_realistic_limit_nm": float(selected_limit),
        "arm_tie_multiplier": arm_tie_multiplier if b7_arm_tie else None,
        "b7_arm_tie_enabled": b7_arm_tie,
        "arm_tie_fallback_used": not b7_arm_tie,
        "b7_replicate_of": None if b7_arm_tie else "B4",
        "dv4_tested": b7_arm_tie,
        "immutable_after_freeze": True,
    }
    return artifact_payload("adaptation", status="ADAPTATION_FROZEN", decision=decision, enabled_cells=list(V21B_CELL_ORDER), source_checkpoint_sha256=bindings["source_checkpoint_sha256"], source_lock_sha256=bindings["source_lock_sha256"], config_sha256_by_cell=bindings["config_sha256_by_cell"], source_artifacts={"p0_admission": p0_admission, "source_lock": source_lock, "census": census, "zero_shot": zero_shot, "pilot": pilot, "arm_tie": arm_tie})


def materialized_profile_overrides(adaptation: Mapping[str, Any]) -> dict[str, Any]:
    validate_artifact(adaptation, expected_schema=schema("adaptation"))
    if adaptation.get("status") != "ADAPTATION_FROZEN" or adaptation.get("decision", {}).get("immutable_after_freeze") is not True:
        raise V21BError("only an immutable ADAPTATION_FROZEN artifact can materialize profiles")
    decision = adaptation["decision"]
    if decision.get("mode") == "THETA_ONLY_FALLBACK_F3":
        return {"arm_j1..arm_j6_effort_limit_nm": None, "theta_high_rad": None, "b7_arm_tie_enabled": False, "b7_arm_tie_multiplier": None, "f3_fallback": True}
    limit = decision.get("arm_realistic_limit_nm")
    if not isinstance(limit, (int, float)) or isinstance(limit, bool) or not math.isfinite(float(limit)) or limit <= 0:
        raise V21BError("adaptation has no positive ARM_REALISTIC limit")
    multiplier = decision.get("arm_tie_multiplier")
    if decision.get("b7_arm_tie_enabled") is True and (isinstance(multiplier, bool) or not isinstance(multiplier, int) or multiplier <= 0):
        raise V21BError("enabled B7 arm-tie adaptation requires a positive integer multiplier")
    overrides = {"arm_j1..arm_j6_effort_limit_nm": float(limit), "theta_high_rad": float(decision["theta_high_rad"]), "b7_arm_tie_enabled": bool(decision["b7_arm_tie_enabled"]), "b7_arm_tie_multiplier": multiplier}
    return overrides


def validate_materialized_config_receipt(
    materialization: Mapping[str, Any],
    materialized_config: Path,
    *,
    cell: str,
    phase: str,
) -> dict[str, Any]:
    """Validate one standalone config against its signed materialization row.

    The pre-formal probes must consume the exact POST_CENSUS B4 file emitted by
    ``materialize_v21b_configs``.  A template with an injected limit is not a
    materialization receipt and is rejected before any command is planned.
    """

    validate_artifact(materialization, expected_schema=schema("materialization"))
    if materialization.get("status") != "MATERIALIZATION_PASS" or materialization.get("phase") != phase:
        raise V21BError(f"{cell} requires a signed {phase} materialization")
    receipt_without_hash = dict(materialization)
    declared_receipt_hash = receipt_without_hash.pop("materialization_sha256", None)
    if not isinstance(declared_receipt_hash, str) or len(declared_receipt_hash) != 64 or any(char not in "0123456789abcdef" for char in declared_receipt_hash):
        raise V21BError("materialization receipt requires a declared lowercase sha256 digest")
    expected_receipt_hash = hashlib.sha256(canonical_json_bytes(receipt_without_hash)).hexdigest()
    if declared_receipt_hash is not None and declared_receipt_hash != expected_receipt_hash:
        raise V21BError("materialization receipt digest does not bind its immutable payload")
    path = Path(materialized_config).resolve()
    if not path.is_file() or path.is_symlink():
        raise V21BError(f"{cell} materialized config must be a regular file")
    row = next((item for item in materialization.get("configs", []) if isinstance(item, Mapping) and item.get("cell") == cell), None)
    if not isinstance(row, Mapping):
        raise V21BError(f"materialization receipt has no {cell} config row")
    digest = sha256_file(path)
    if row.get("sha256") != digest:
        raise V21BError(f"{cell} materialized config hash is not bound to the receipt")
    eval_contract_source_sha256 = require_digest(
        materialization.get("v21b_eval_contract_source_sha256"),
        name="materialized eval contract source",
    )
    repo_root = Path(__file__).resolve().parents[2]
    eval_contract_path = repo_root / V21B_EVAL_CONTRACT_PATH
    if sha256_file(eval_contract_path) != eval_contract_source_sha256:
        raise V21BError("materialized eval contract source is stale")
    eval_source = read_yaml(eval_contract_path)
    eval_algo = eval_source.get("algo")
    if not isinstance(eval_algo, Mapping) or not isinstance(eval_algo.get("config"), Mapping):
        raise V21BError("base_eval.yaml must contain algo.config mapping")
    eval_contract = _validate_eval_contract_mapping(eval_algo["config"].get("eval"), label="base_eval.yaml algo.config.eval")
    config = read_yaml(path)
    validate_v21b_config(config, cell=cell, require_launchable=phase == "FORMAL_PROMOTED")
    if config.get("v21b_eval_contract_source_sha256") != eval_contract_source_sha256:
        raise V21BError(f"{cell} config does not bind the eval contract source digest")
    env_eval_digest = config.get("env", {}).get("config", {}).get("a2_v21B_eval_contract_source_sha256")
    if env_eval_digest != eval_contract_source_sha256:
        raise V21BError(f"{cell} env metadata does not bind the eval contract source digest")
    eval_values = config.get("algo", {}).get("config", {}).get("eval")
    if not isinstance(eval_values, Mapping):
        raise V21BError(f"{cell} config lacks algo.config.eval mapping")
    for key, expected in eval_contract.items():
        if key.startswith("a2_hold_oracle_") or key.startswith("a2_v20_arc_probe_") or key in V21B_EVAL_CONTRACT_DIAGNOSTIC_KEYS:
            if eval_values.get(key) != expected:
                raise V21BError(f"{cell} config eval contract key {key} is not source-locked")
    copied_keys = row.get("v21b_eval_contract_missing_keys")
    if not isinstance(copied_keys, list) or any(key not in eval_contract for key in copied_keys):
        raise V21BError(f"{cell} config row has invalid eval contract merge record")
    if row.get("v21b_eval_contract_source_sha256") != eval_contract_source_sha256:
        raise V21BError(f"{cell} config row does not bind the eval contract source digest")
    if config.get("v21b_eval_contract_missing_keys") != list(copied_keys):
        raise V21BError(f"{cell} config eval contract merge record is not receipt-bound")
    if config.get("v21b_materialization_phase") != phase or config.get("v21b_formal_launchable") is not (phase == "FORMAL_PROMOTED"):
        raise V21BError(f"{cell} config materialization phase/launchability is inconsistent")
    if row.get("phase") != phase or row.get("template_sha256") != config.get("v21b_materialized_from_config_sha256"):
        raise V21BError(f"{cell} config row does not bind its phase/template digest")
    vector = config.get("robot", {}).get("dof_effort_limit_list")
    if row.get("effort_limit_vector") != vector or not isinstance(vector, list) or len(vector) != 20:
        raise V21BError(f"{cell} config row does not bind its exact 20-entry effort vector")
    if phase == "POST_CENSUS":
        limit = config.get("v21b_arm_realistic_effort_limit_nm")
        if cell != "B4" or config.get("v21b_arm_profile") != "ARM_REALISTIC" or not isinstance(limit, (int, float)) or isinstance(limit, bool) or not math.isfinite(float(limit)) or float(limit) <= 0.0 or vector[12:18] != [float(limit)] * 6:
            raise V21BError("POST_CENSUS probe materialization must be B4 with the selected six-joint limit")
        if materialization.get("census_selection") != float(limit) or row.get("selected_limit_nm") != float(limit):
            raise V21BError("POST_CENSUS B4 receipt does not bind the signed census selection")
    return {
        "cell": cell,
        "phase": phase,
        "path": str(path),
        "config": config,
        "row": dict(row),
        "materialized_config_sha256": digest,
        "materialization_sha256": declared_receipt_hash,
        "v21b_eval_contract_source_sha256": eval_contract_source_sha256,
        "v21b_eval_contract_missing_keys": list(copied_keys),
        "effort_limit_vector_20": list(vector),
        "effort_limit_vector_6d": list(vector[12:18]),
        "source_config_sha256": config.get("v21b_materialized_from_config_sha256"),
    }


def _materialized_effort_vector(template: list[float], *, realistic: bool, limit: float | None) -> list[float]:
    if not isinstance(template, list) or len(template) != 20:
        raise V21BError("materialized robot effort vector must contain exactly 20 entries")
    vector = [float(value) for value in template]
    if vector[18:20] != [45.0, 45.0]:
        raise V21BError("materialized finger effort limits must remain exactly 45/45")
    if realistic:
        if limit is None or not math.isfinite(float(limit)) or float(limit) <= 0.0:
            raise V21BError("ARM_REALISTIC materialization requires a positive selected limit")
        vector[12:18] = [float(limit)] * 6
    return vector


def _compose_materialization_base(root: Path, cell: str) -> dict[str, Any]:
    """Compose the signed ablation into a standalone Hydra config.

    A materialized file must be consumable by the trainer without relying on
    the mutable template search path.  Keep unresolved Hydra interpolations
    intact; Hydra resolves them again when the standalone config is loaded.
    """

    try:
        from hydra import compose
        from hydra.initialize import initialize_config_dir
        from omegaconf import OmegaConf
    except ImportError as exc:
        raise V21BError("v21-B config materialization requires Hydra/OmegaConf") from exc
    config_dir = root / "gr00t/rl/config"
    template_path = Path(V21B_CONFIG_PATHS[cell])
    with initialize_config_dir(config_dir=str(config_dir), version_base=None):
        composed = compose(
            config_name="base",
            overrides=[
                "+exp=wbmanip/door_open_a2_base_lstm",
                f"+ablation=wbmanip/{template_path.stem}",
            ],
        )
        value = OmegaConf.to_container(composed, resolve=False)
    if not isinstance(value, dict):
        raise V21BError(f"composed v21-B {cell} materialization is not a mapping")
    return value


def materialize_v21b_configs(
    repo_root: Path,
    *,
    phase: str,
    p0_admission: Mapping[str, Any],
    source_lock: Mapping[str, Any],
    census: Mapping[str, Any] | None = None,
    zero_shot: Mapping[str, Any] | None = None,
    pilot: Mapping[str, Any] | None = None,
    arm_tie: Mapping[str, Any] | None = None,
    adaptation: Mapping[str, Any] | None = None,
    output_root: Path | None = None,
) -> dict[str, Any]:
    """Write signed phase-specific Hydra YAML configs without mutating templates."""

    root = repo_root.resolve()
    if output_root is None:
        raise V21BError("phase materialization requires an output_root")
    output = output_root.resolve()
    validate_artifact(p0_admission, expected_schema=schema("p0_admission"))
    validate_artifact(source_lock, expected_schema=schema("source_lock"))
    eval_contract, eval_contract_source_sha256 = _load_source_locked_eval_contract(root, source_lock)
    if p0_admission.get("source_checkpoint_sha256") != source_lock.get("source_checkpoint_sha256"):
        raise V21BError("phase materialization P0/source checkpoint hashes disagree")
    if phase not in ("CENSUS_PRE_K", "POST_CENSUS", "FORMAL_PROMOTED"):
        raise V21BError("materialization phase must be CENSUS_PRE_K, POST_CENSUS, or FORMAL_PROMOTED")
    f3_fallback = False
    if phase == "CENSUS_PRE_K":
        if zero_shot is not None or pilot is not None or arm_tie is not None or adaptation is not None:
            raise V21BError("pre-census materialization accepts only P0/source artifacts")
        source_hash = p0_admission.get("source_checkpoint_sha256")
        source_lock_hash = source_lock.get("source_lock_sha256")
        if census is not None:
            validate_artifact(census, expected_schema=schema("census"))
            if census.get("status") != "CENSUS_PASS":
                raise V21BError("pre-census materialization can only bind a completed census artifact")
            if census.get("source_checkpoint_sha256") != source_hash or census.get("source_lock_sha256") != source_lock_hash:
                raise V21BError("census is not bound to P0/source for pre-census materialization")
        cells = ("B1",)
        selected_limit = None
        adaptation_hash = None
    elif phase == "POST_CENSUS":
        if zero_shot is not None or pilot is not None or arm_tie is not None or adaptation is not None:
            raise V21BError("post-census materialization accepts only P0/source/census artifacts")
        if census is None:
            raise V21BError("post-census materialization requires a completed census artifact")
        validate_artifact(census, expected_schema=schema("census"))
        if census.get("status") != "CENSUS_PASS" or not isinstance(census.get("selection"), (int, float)) or isinstance(census.get("selection"), bool):
            raise V21BError("post-census materialization requires a numeric CENSUS_PASS selection")
        source_hash = p0_admission.get("source_checkpoint_sha256")
        source_lock_hash = source_lock.get("source_lock_sha256")
        if census.get("source_checkpoint_sha256") != source_hash or census.get("source_lock_sha256") != source_lock_hash:
            raise V21BError("census is not bound to P0/source for post-census materialization")
        cells = ("B4",)
        selected_limit = float(census["selection"])
        adaptation_hash = None
    else:
        if adaptation is None or census is None:
            raise V21BError("formal materialization requires a census result and frozen adaptation")
        validate_artifact(census, expected_schema=schema("census"))
        f3_fallback = census.get("status") in {"CENSUS_RIGHT_CENSORED", "BOUNDARY_NOT_SEPARABLE"}
        if not f3_fallback and (zero_shot is None or pilot is None or arm_tie is None):
            raise V21BError("formal materialization requires all completed probes and frozen adaptation")
        validate_preformal_bindings(p0_admission=p0_admission, source_lock=source_lock, census=census, zero_shot=zero_shot, pilot=pilot, arm_tie=arm_tie)
        validate_artifact(adaptation, expected_schema=schema("adaptation"))
        if adaptation.get("status") != "ADAPTATION_FROZEN":
            raise V21BError("formal materialization requires ADAPTATION_FROZEN")
        if adaptation.get("decision", {}).get("mode") == "THETA_ONLY_FALLBACK_F3":
            f3_fallback = True
        selected_limit = None if f3_fallback else float(adaptation["decision"]["arm_realistic_limit_nm"])
        adaptation_hash = hashlib.sha256(canonical_json_bytes(dict(adaptation))).hexdigest()
        source_hash = adaptation["source_checkpoint_sha256"]
        source_lock_hash = adaptation["source_lock_sha256"]
        cells = V21B_CELL_ORDER
    output.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for cell in cells:
        template_path = root / V21B_CONFIG_PATHS[cell]
        # Compose the full base/experiment/ablation config so the resulting
        # standalone YAML can be passed with --config-dir/--config-name.
        config = copy.deepcopy(_compose_materialization_base(root, cell))
        eval_contract_missing_keys = _merge_eval_contract(config, eval_contract)
        config["v21b_eval_contract_source_sha256"] = eval_contract_source_sha256
        config["v21b_eval_contract_missing_keys"] = list(eval_contract_missing_keys)
        realistic = config.get("v21b_arm_profile") == "ARM_REALISTIC"
        config["v21b_materialization_phase"] = phase
        config["v21b_materialized_from_config_sha256"] = sha256_file(template_path)
        config["v21b_source_lock_sha256"] = source_lock_hash
        config["v21b_source_checkpoint_sha256"] = source_hash
        config["v21b_formal_launchable"] = phase == "FORMAL_PROMOTED"
        config["v21b_promoted"] = phase == "FORMAL_PROMOTED"
        config["v21b_arm_realistic_effort_limit_nm"] = selected_limit if realistic and not f3_fallback else None
        config["v21b_f3_fallback"] = bool(f3_fallback)
        config["v21b_f3_status"] = census.get("status") if f3_fallback else None
        config["v21b_adapted_theta_high_rad"] = None
        if f3_fallback and phase == "FORMAL_PROMOTED":
            config["v21b_arm_profile"] = "ARM_V20"
            config["v21b_arm_profile_version"] = "ARM_V20_v1"
            config["v21b_arm_profile_selection_state"] = "THETA_ONLY_FALLBACK_F3"
            config["v21b_arm_realistic_selection_required"] = False
        elif realistic and phase == "FORMAL_PROMOTED":
            config["v21b_arm_profile_selection_state"] = "PROMOTED_BY_SIGNED_CENSUS"
            config["v21b_arm_profile_version"] = "ARM_REALISTIC_v1_PROMOTED"
        elif realistic and phase == "POST_CENSUS":
            config["v21b_arm_profile_selection_state"] = "CENSUS_SELECTED_UNPROMOTED"
            config["v21b_arm_profile_version"] = "ARM_REALISTIC_v1_SELECTED"
        env = config.setdefault("env", {}).setdefault("config", {})
        if env.get("a2_v21B_evidence_enabled") is not True:
            raise V21BError(f"{cell} materialization requires a2_v21B_evidence_enabled=true")
        if env.get("a2_v20_R2_evidence_enabled") is not True:
            raise V21BError(
                f"{cell} materialization requires shared a2_v20_R2_evidence_enabled=true"
            )
        if env.get("a2_v20_R2_formal_launch") is not False:
            raise V21BError(
                f"{cell} materialization requires legacy a2_v20_R2_formal_launch=false"
            )
        theta = float(V21B_F3_THETA_LADDER[cell]) if f3_fallback else (float(adaptation["decision"]["theta_high_rad"]) if phase == "FORMAL_PROMOTED" and cell in ("B2", "B4", "B5", "B6", "B7") else float(V21B_CELL_FACTORS[cell]["theta_send_rad"]))
        if phase == "FORMAL_PROMOTED" and cell in ("B2", "B4", "B5", "B6", "B7"):
            config["v21b_adapted_theta_high_rad"] = theta
        env["a2_v20_send_hinge_threshold"] = theta
        env["a2_v21B_target_root_ramp_theta_rad"] = theta
        env["a2_v21B_source_lock_sha256"] = source_lock_hash
        env["a2_v21B_source_config_sha256"] = config["v21b_materialized_from_config_sha256"]
        env["a2_v21B_source_checkpoint_sha256"] = source_hash
        env["a2_v21B_adaptation_bundle_sha256"] = adaptation_hash
        env["a2_v21B_materialization_phase"] = phase
        env["a2_v21B_arm_profile"] = config.get("v21b_arm_profile")
        env["a2_v21B_arm_profile_version"] = config.get("v21b_arm_profile_version")
        env["a2_v21B_formal_launch"] = phase == "FORMAL_PROMOTED"
        env["a2_v21B_eval_contract_source_sha256"] = eval_contract_source_sha256
        env["a2_v20_formal_launch"] = phase == "FORMAL_PROMOTED"
        env["a2_v21B_terminal_export_root"] = str(output / "terminal_exports")
        if f3_fallback and phase == "FORMAL_PROMOTED":
            config["v21b_arm_tie_enabled"] = False
            config["v21b_arm_tie_multiplier"] = None
            config["v21b_dv4_tested"] = False
            env["a2_v20_arm_tie_enabled"] = False
            env["a2_v20_arm_tie_multiplier"] = None
            env["a2_v20_arm_tangent_carry_scale"] = 0.0
            env["a2_v20_handle_arc_tracking_scale"] = 0.0
            reward_scales = config.setdefault("rewards", {}).setdefault("reward_scales", {})
            reward_scales["a2_v20_arm_tangent_carry"] = 0.0
            reward_scales["a2_v20_handle_arc_tracking"] = 0.0
        if phase == "FORMAL_PROMOTED" and cell == "B7":
            tie_enabled = False if f3_fallback else bool(adaptation["decision"]["b7_arm_tie_enabled"])
            multiplier = adaptation["decision"].get("arm_tie_multiplier")
            config["v21b_arm_tie_enabled"] = tie_enabled
            config["v21b_arm_tie_multiplier"] = multiplier
            config["v21b_dv4_tested"] = tie_enabled
            env["a2_v20_arm_tie_enabled"] = tie_enabled
            env["a2_v20_arm_tie_multiplier"] = multiplier
            carry_scale = 3.5 * multiplier if tie_enabled else 0.0
            arc_scale = 0.85 * multiplier if tie_enabled else 0.0
            env["a2_v20_arm_tangent_carry_scale"] = carry_scale
            env["a2_v20_handle_arc_tracking_scale"] = arc_scale
            reward_scales = config.setdefault("rewards", {}).setdefault("reward_scales", {})
            reward_scales["a2_v20_arm_tangent_carry"] = carry_scale
            reward_scales["a2_v20_handle_arc_tracking"] = arc_scale
        robot = config.setdefault("robot", {})
        robot["dof_effort_limit_list"] = _materialized_effort_vector(robot.get("dof_effort_limit_list"), realistic=realistic and not f3_fallback and phase in ("POST_CENSUS", "FORMAL_PROMOTED"), limit=selected_limit)
        validate_v21b_config(config, cell=cell, require_launchable=phase == "FORMAL_PROMOTED")
        target = output / f"{cell}.yaml"
        if target.exists() or target.is_symlink():
            raise V21BError(f"refusing to overwrite materialized config: {target}")
        target.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
        rows.append({"cell": cell, "path": str(target), "sha256": sha256_file(target), "template_sha256": config["v21b_materialized_from_config_sha256"], "effort_limit_vector": robot["dof_effort_limit_list"], "theta_send_rad": theta, "phase": phase, "selected_limit_nm": selected_limit if realistic and not f3_fallback else None, "f3_fallback": bool(f3_fallback), "f3_status": census.get("status") if f3_fallback and census is not None else None, "v21b_eval_contract_source_sha256": eval_contract_source_sha256, "v21b_eval_contract_missing_keys": list(eval_contract_missing_keys)})
    receipt = artifact_payload("materialization", status="MATERIALIZATION_PASS", phase=phase, configs=rows, source_checkpoint_sha256=source_hash, source_lock_sha256=source_lock_hash, adaptation_bundle_sha256=adaptation_hash, census_selection="N/A" if f3_fallback else selected_limit, census_status=census.get("status") if census is not None else None, f3_fallback=bool(f3_fallback), v21b_eval_contract_source_sha256=eval_contract_source_sha256, immutable_after_write=True)
    receipt["materialization_sha256"] = hashlib.sha256(canonical_json_bytes(receipt)).hexdigest()
    return validate_artifact(receipt, expected_schema=schema("materialization"))


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["ARM_TIE_PREREGISTERED_FALLBACK", "validate_preformal_bindings", "freeze_adaptation", "materialized_profile_overrides", "validate_materialized_config_receipt", "materialize_v21b_configs", "main"]
