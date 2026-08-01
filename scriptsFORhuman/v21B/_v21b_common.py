"""Strict shared contracts for v21-B pre-formal tools."""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

import yaml


V21B_PLAN_ID = "base_v21B_theta_arm_ablation_v1"
V21B_EXECUTION_ID = "base_v21B_execution_v1"
V21B_SCHEMA = "a2_piper_base_v21B_config_v1"
V21B_ARTIFACT_SCHEMA_PREFIX = "a2_piper_base_v21B_"
V21B_CELL_ORDER = ("B1", "B2", "B3", "B4", "B5", "B6", "B7")
V21B_FORMAL_GPUS = (0, 1, 2, 3, 4, 5, 6)
V21B_FORBIDDEN_GPU = 7
V21B_WARM_START_PATH = "logs_rl/a2_piper_full_stage_a2_base/base_v20_R3_G4-20260731_004712/model_step_002500.pt"
V21B_WARM_START_SHA256 = "f000f13e817309f7b73e33c5c4d95076397debb992713e5613dce567bfda806d"
V21B_CONFIG_PATHS = {
    "B1": "gr00t/rl/config/ablation/wbmanip/base_v21B_B1_theta090_arm_v20.yaml",
    "B2": "gr00t/rl/config/ablation/wbmanip/base_v21B_B2_theta120_arm_v20.yaml",
    "B3": "gr00t/rl/config/ablation/wbmanip/base_v21B_B3_theta090_arm_realistic.yaml",
    "B4": "gr00t/rl/config/ablation/wbmanip/base_v21B_B4_theta120_arm_realistic.yaml",
    "B5": "gr00t/rl/config/ablation/wbmanip/base_v21B_B5_theta120_arm_realistic_seed1.yaml",
    "B6": "gr00t/rl/config/ablation/wbmanip/base_v21B_B6_theta120_arm_v20_seed1.yaml",
    "B7": "gr00t/rl/config/ablation/wbmanip/base_v21B_B7_theta120_arm_realistic_arm_tie.yaml",
}
V21B_CELL_FACTORS = {
    "B1": {"theta_send_rad": 0.90, "arm_profile": "ARM_V20", "arm_tie": False, "seed": 0, "gpu": 0},
    "B2": {"theta_send_rad": 1.20, "arm_profile": "ARM_V20", "arm_tie": False, "seed": 0, "gpu": 1},
    "B3": {"theta_send_rad": 0.90, "arm_profile": "ARM_REALISTIC", "arm_tie": False, "seed": 0, "gpu": 2},
    "B4": {"theta_send_rad": 1.20, "arm_profile": "ARM_REALISTIC", "arm_tie": False, "seed": 0, "gpu": 3},
    "B5": {"theta_send_rad": 1.20, "arm_profile": "ARM_REALISTIC", "arm_tie": False, "seed": 1, "gpu": 4},
    "B6": {"theta_send_rad": 1.20, "arm_profile": "ARM_V20", "arm_tie": False, "seed": 1, "gpu": 5},
    "B7": {"theta_send_rad": 1.20, "arm_profile": "ARM_REALISTIC", "arm_tie": True, "seed": 0, "gpu": 6},
}
V21B_F3_THETA_LADDER = {
    "B1": 0.90,
    "B2": 1.20,
    "B3": 1.05,
    "B4": 1.15,
    "B5": 1.25,
    "B6": 1.20,
    "B7": 1.25,
}

# Resolved Hydra parity is deliberately narrower than raw-YAML equality.  These
# are the only values a v21-B cell may change relative to B1's frozen v20-R3-G4
# control; all other resolved paths remain byte/value-identical.
V21B_RESOLVED_ALLOWLIST = frozenset({
    "v21b_cell", "v21b_arm_profile", "v21b_arm_profile_version",
    "v21b_arm_profile_selection_state", "v21b_arm_realistic_selection_required",
    "v21b_arm_realistic_effort_limit_nm", "v21b_arm_tie_calibration_required",
    "seed", "env.config.a2_v21B_cell", "env.config.a2_v21B_arm_profile",
    "env.config.a2_v21B_arm_profile_version", "env.config.a2_v21B_R2_group",
    "env.config.a2_v20_R2_group", "env.config.a2_v20_R2_seed",
    "env.config.a2_v20_send_hinge_threshold", "env.config.a2_v21B_target_root_ramp_theta_rad",
    "env.config.a2_v20_calibration_label", "env.config.a2_v20_arm_tie_enabled",
    "env.config.a2_v20_arm_tangent_carry_scale", "env.config.a2_v20_handle_arc_tracking_scale",
    "rewards.reward_scales.a2_v20_arm_tangent_carry", "rewards.reward_scales.a2_v20_handle_arc_tracking",
})


class V21BError(ValueError):
    """Fail-fast v21-B contract violation."""


def canonical_json_bytes(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise V21BError("value cannot be represented as finite canonical JSON") from exc


def canonical_json(value: Any) -> str:
    return canonical_json_bytes(value).decode("utf-8")


def hydra_string_value(value: str) -> str:
    """Serialize a string as a Hydra override value without mapping coercion.

    Hydra's override parser treats an unquoted JSON object as an override
    expression.  The signed scenario manifest is intentionally a JSON string.
    Use Hydra's own single-quoted serializer so backslashes that are ordinary
    string content are preserved while quote-adjacent backslashes receive the
    parser's exact escaping.
    """

    if not isinstance(value, str):
        raise V21BError("Hydra override value must be a string")
    try:
        from hydra.core.override_parser.overrides_parser import OverridesParser
        from hydra.core.override_parser.types import Quote, QuotedString
    except ImportError as exc:
        raise V21BError("Hydra override serializer requires the installed Hydra parser") from exc
    serialized = QuotedString(value, Quote.single).with_quotes()
    parsed = OverridesParser.create().parse_overrides([f"+__v21b_string={serialized}"])
    if len(parsed) != 1 or parsed[0].value() != value:
        raise V21BError("Hydra override serializer failed exact string round-trip")
    return serialized


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    if not path.is_file() or path.is_symlink():
        raise V21BError(f"expected regular file: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise V21BError(f"config is not a regular file: {path}")
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise V21BError(f"invalid YAML: {path}") from exc
    if not isinstance(value, dict):
        raise V21BError(f"YAML root must be a mapping: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    if path.exists() or path.is_symlink():
        raise V21BError(f"refusing to overwrite existing v21-B artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value) + b"\n")


def validate_v21b_config(config: dict[str, Any], *, cell: str | None = None, require_launchable: bool = False) -> dict[str, Any]:
    if not isinstance(config, dict) or config.get("v21b_schema") != V21B_SCHEMA:
        raise V21BError("config is not a v21-B schema-bound mapping")
    if config.get("scientific_plan_id") != V21B_PLAN_ID:
        raise V21BError("config plan id is not v21-B")
    actual_cell = config.get("v21b_cell")
    if actual_cell not in V21B_CELL_ORDER or (cell is not None and actual_cell != cell):
        raise V21BError(f"unsupported v21-B cell: {actual_cell!r}")
    factors = V21B_CELL_FACTORS[actual_cell]
    f3_fallback = config.get("v21b_f3_fallback") is True and config.get("v21b_materialization_phase") == "FORMAL_PROMOTED"
    expected_profile = "ARM_V20" if f3_fallback else factors["arm_profile"]
    if config.get("seed") != factors["seed"] or config.get("v21b_arm_profile") != expected_profile:
        raise V21BError(f"{actual_cell} seed/profile does not match the pre-registered factor matrix")
    env = config.get("env", {}).get("config", {})
    if not isinstance(env, dict):
        raise V21BError("v21-B env.config is required")
    if env.get("a2_v21B_cell") != actual_cell or env.get("a2_v21B_arm_profile") != expected_profile:
        raise V21BError(f"{actual_cell} env profile/cell metadata is not bound to the top-level factor")
    expected_profile_version = (
        "ARM_V20_v1"
        if f3_fallback
        else
        "ARM_REALISTIC_v1_PROMOTED"
        if factors["arm_profile"] == "ARM_REALISTIC" and config.get("v21b_promoted") is True
        else "ARM_REALISTIC_v1_SELECTED"
        if factors["arm_profile"] == "ARM_REALISTIC" and config.get("v21b_materialization_phase") == "POST_CENSUS"
        else "ARM_REALISTIC_v1_PRE_CENSUS"
        if factors["arm_profile"] == "ARM_REALISTIC"
        else "ARM_V20_v1"
    )
    if env.get("a2_v21B_arm_profile_version") != expected_profile_version:
        raise V21BError(f"{actual_cell} env arm profile version is not bound to the factor")
    if env.get("a2_v20_R1_plan_id") != V21B_PLAN_ID:
        raise V21BError("v21-B env guard plan id is not bound")
    theta = env.get("a2_v20_send_hinge_threshold")
    if isinstance(theta, bool) or not isinstance(theta, (int, float)) or not math.isfinite(float(theta)) or not 0.90 <= float(theta) <= 1.30:
        raise V21BError(f"{actual_cell} theta is outside the closed v21-B interval")
    if f3_fallback:
        if float(theta) != V21B_F3_THETA_LADDER[actual_cell] or config.get("v21b_f3_status") not in ("CENSUS_RIGHT_CENSORED", "BOUNDARY_NOT_SEPARABLE"):
            raise V21BError(f"{actual_cell} F3 theta/profile is not bound to the signed fallback ladder")
    elif float(theta) != factors["theta_send_rad"]:
        adapted_theta = config.get("v21b_adapted_theta_high_rad")
        high_cell = actual_cell in ("B2", "B4", "B5", "B6", "B7")
        if not (config.get("v21b_materialization_phase") == "FORMAL_PROMOTED" and high_cell and adapted_theta == theta and theta in (1.10, 1.20)):
            raise V21BError(f"{actual_cell} theta does not match the declared factor")
    elif config.get("v21b_adapted_theta_high_rad") is not None and config.get("v21b_materialization_phase") != "FORMAL_PROMOTED":
        raise V21BError(f"{actual_cell} carries adapted theta outside FORMAL_PROMOTED materialization")
    if env.get("a2_corridor_latch_mode") != "send_ready_v20":
        raise V21BError(f"{actual_cell} must use send_ready_v20 corridor latch")
    if env.get("a2_v21B_target_root_ramp_theta_rad") != theta:
        raise V21BError(f"{actual_cell} target-root ramp theta is not bound to send theta")
    for key, expected in (("a2_v20_send_hinge_tolerance", 0.05), ("a2_v20_pre_send_root_x_margin", 0.03), ("a2_v20_R1_soft_phase_end_batch", 500), ("a2_v20_R1_crossing_base_component", 1.0), ("a2_v20_R1_crossing_shortfall_gain", 1.0)):
        if env.get(key) != expected:
            raise V21BError(f"{actual_cell} frozen control {key} must remain {expected!r}")
    if env.get("a2_v20_R1_send_curriculum_enabled") is not True or env.get("a2_v20_R1_snapshot_guard_enabled") is not True:
        raise V21BError(f"{actual_cell} R1 send curriculum/snapshot guard must be enabled")
    if config.get("checkpoint") != V21B_WARM_START_PATH or config.get("checkpoint_load_mode") != "policy_only" or config.get("auto_load_latest") is not False:
        raise V21BError(f"{actual_cell} warm-start binding is not policy_only v20 G4 step2500")
    if config.get("v21b_source_checkpoint_sha256") != V21B_WARM_START_SHA256:
        raise V21BError(f"{actual_cell} warm-start hash binding is incorrect")
    if config.get("num_envs") != 4096 or config.get("algo", {}).get("trl", {}).get("num_total_batches") != 2500 or config.get("callbacks", {}).get("model_save", {}).get("save_frequency") != 250:
        raise V21BError(f"{actual_cell} formal trainer dimensions are not 4096/2500/save250")
    limits = config.get("robot", {}).get("dof_effort_limit_list")
    if not isinstance(limits, list) or len(limits) != 20 or limits[18:20] != [45.0, 45.0]:
        raise V21BError(f"{actual_cell} arm/finger effort profile is not versioned v20 plumbing")
    if f3_fallback:
        if config.get("v21b_arm_profile") != "ARM_V20" or config.get("v21b_arm_profile_selection_state") != "THETA_ONLY_FALLBACK_F3" or config.get("v21b_arm_realistic_effort_limit_nm") is not None or limits[12:18] != [100.0] * 6:
            raise V21BError(f"{actual_cell} F3 fallback must use ARM_V20/100 without realistic limit")
        if config.get("v21b_formal_launchable") is not True or config.get("v21b_promoted") is not True:
            raise V21BError(f"{actual_cell} F3 fallback must be formal-launchable")
    elif actual_cell in ("B3", "B4", "B5", "B7"):
        promoted = config.get("v21b_promoted") is True
        if promoted:
            limit = config.get("v21b_arm_realistic_effort_limit_nm")
            if config.get("v21b_arm_profile_selection_state") != "PROMOTED_BY_SIGNED_CENSUS" or not isinstance(limit, (int, float)) or isinstance(limit, bool) or not math.isfinite(float(limit)) or float(limit) <= 0.0:
                raise V21BError(f"{actual_cell} promoted ARM_REALISTIC config lacks signed census limit")
            if config.get("v21b_formal_launchable") is not True:
                raise V21BError(f"{actual_cell} promoted ARM_REALISTIC config must be launchable")
            if limits[12:18] != [float(limit)] * 6:
                raise V21BError(f"{actual_cell} promoted ARM_REALISTIC effort vector is not exactly six selected limits")
        elif config.get("v21b_materialization_phase") == "POST_CENSUS":
            limit = config.get("v21b_arm_realistic_effort_limit_nm")
            if config.get("v21b_arm_profile_selection_state") != "CENSUS_SELECTED_UNPROMOTED" or not isinstance(limit, (int, float)) or isinstance(limit, bool) or not math.isfinite(float(limit)) or float(limit) <= 0.0 or limits[12:18] != [float(limit)] * 6:
                raise V21BError(f"{actual_cell} POST_CENSUS ARM_REALISTIC config lacks the exact selected effort vector")
            if config.get("v21b_formal_launchable") is not False:
                raise V21BError(f"{actual_cell} POST_CENSUS materialization must remain non-launchable")
        elif config.get("v21b_arm_profile_selection_state") != "PRE_CENSUS_UNPROMOTED" or config.get("v21b_arm_realistic_effort_limit_nm") is not None:
            raise V21BError(f"{actual_cell} ARM_REALISTIC must remain selection-bound before census")
        elif limits[12:18] != [100.0] * 6:
            raise V21BError(f"{actual_cell} pre-census ARM_REALISTIC template must retain v20 effort plumbing")
    elif limits[12:18] != [100.0] * 6:
        raise V21BError(f"{actual_cell} ARM_V20 effort profile must retain v20 limits")
    if actual_cell == "B7" and config.get("v21b_materialization_phase") == "FORMAL_PROMOTED":
        if f3_fallback:
            if config.get("v21b_arm_tie_enabled") is not False or config.get("v21b_dv4_tested") is not False or env.get("a2_v20_arm_tie_enabled") is not False:
                raise V21BError("F3 B7 must tie off arm-tie/DV4")
        else:
            tie_enabled = config.get("v21b_arm_tie_enabled")
            env_tie = env.get("a2_v20_arm_tie_enabled")
            if not isinstance(tie_enabled, bool) or env_tie is not tie_enabled:
                raise V21BError("B7 arm-tie admission is not bound to the signed adaptation")
            carry = env.get("a2_v20_arm_tangent_carry_scale")
            arc = env.get("a2_v20_handle_arc_tracking_scale")
            reward_scales = config.get("rewards", {}).get("reward_scales", {})
            if reward_scales.get("a2_v20_arm_tangent_carry") != carry or reward_scales.get("a2_v20_handle_arc_tracking") != arc:
                raise V21BError("B7 arm-tie reward scales are not consumed consistently")
            if tie_enabled:
                multiplier = config.get("v21b_arm_tie_multiplier")
                if isinstance(multiplier, bool) or not isinstance(multiplier, int) or multiplier <= 0 or carry != 3.5 * multiplier or arc != 0.85 * multiplier:
                    raise V21BError("B7 calibrated arm-tie scales do not preserve the 3.5:0.85 ratio")
            elif carry != 0.0 or arc != 0.0 or config.get("v21b_dv4_tested") is not False:
                raise V21BError("B7 deferred arm-tie fallback must be an untested B4 replicate")
    if require_launchable and config.get("v21b_formal_launchable") is not True:
        raise V21BError(f"{actual_cell} is pre-census/non-launchable")
    return factors


def config_for_cell(repo_root: Path, cell: str) -> Path:
    if cell not in V21B_CONFIG_PATHS:
        raise V21BError(f"unknown v21-B cell {cell!r}")
    path = repo_root / V21B_CONFIG_PATHS[cell]
    validate_v21b_config(read_yaml(path), cell=cell)
    return path


def _resolved_hydra_configs(repo_root: Path) -> dict[str, dict[str, Any]]:
    """Compose every template with Hydra before parity validation."""

    try:
        from hydra import compose
        from hydra.initialize import initialize_config_dir
        from omegaconf import OmegaConf
    except ImportError as exc:
        raise V21BError("resolved v21-B parity requires Hydra/OmegaConf") from exc
    root = repo_root.resolve()
    config_dir = root / "gr00t/rl/config"
    if not config_dir.is_dir():
        raise V21BError(f"v21-B Hydra config directory is missing: {config_dir}")
    result: dict[str, dict[str, Any]] = {}
    with initialize_config_dir(config_dir=str(config_dir), version_base=None):
        for cell in V21B_CELL_ORDER:
            path = Path(V21B_CONFIG_PATHS[cell])
            stem = path.stem
            composed = compose(
                config_name="base",
                overrides=["+exp=wbmanip/door_open_a2_base_lstm", f"+ablation=wbmanip/{stem}"],
            )
            value = OmegaConf.to_container(composed, resolve=False)
            if not isinstance(value, dict):
                raise V21BError(f"resolved Hydra config for {cell} is not a mapping")
            result[cell] = value
    return result


def _flatten_mapping(value: Any, prefix: str = "") -> dict[str, Any]:
    if not isinstance(value, dict):
        return {prefix: value}
    flattened: dict[str, Any] = {}
    for key, item in value.items():
        child = f"{prefix}.{key}" if prefix else str(key)
        flattened.update(_flatten_mapping(item, child))
    return flattened


def validate_resolved_v21b_parity(repo_root: Path, *, reference_cell: str = "B1") -> dict[str, dict[str, Any]]:
    """Fail fast if a resolved cell drifts outside the approved allowlist."""

    if reference_cell not in V21B_CELL_ORDER:
        raise V21BError(f"unknown v21-B parity reference cell: {reference_cell!r}")
    resolved = _resolved_hydra_configs(repo_root)
    reference = _flatten_mapping(resolved[reference_cell])
    for cell, value in resolved.items():
        if cell == reference_cell:
            continue
        current = _flatten_mapping(value)
        differences = {
            path: (reference.get(path), current.get(path))
            for path in sorted(set(reference) | set(current))
            if reference.get(path) != current.get(path)
        }
        unexpected = sorted(path for path in differences if path not in V21B_RESOLVED_ALLOWLIST)
        if unexpected:
            raise V21BError(
                f"resolved {cell} drifts from {reference_cell} outside allowlist: {unexpected}"
            )
    return resolved


assert_resolved_v21b_parity = validate_resolved_v21b_parity


def parse_gpus(value: str | tuple[int, ...] | list[int], *, formal: bool = False) -> tuple[int, ...]:
    if isinstance(value, str):
        try:
            result = tuple(int(part.strip()) for part in value.split(",") if part.strip())
        except ValueError as exc:
            raise V21BError(f"invalid GPU list: {value!r}") from exc
    else:
        result = tuple(value)
    if any(isinstance(gpu, bool) or not isinstance(gpu, int) for gpu in result) or len(set(result)) != len(result):
        raise V21BError("GPU list must contain unique integers")
    if any(gpu == V21B_FORBIDDEN_GPU for gpu in result) or any(gpu not in V21B_FORMAL_GPUS for gpu in result):
        raise V21BError("GPU7 is forbidden and legal physical GPUs are 0-6")
    if formal and result != V21B_FORMAL_GPUS:
        raise V21BError("formal v21-B launch requires physical GPUs 0-6 exactly")
    return result


def require_digest(value: str, *, name: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise V21BError(f"{name} must be a lowercase sha256 digest")
    return value


__all__ = [
    "V21BError", "V21B_PLAN_ID", "V21B_EXECUTION_ID", "V21B_SCHEMA", "V21B_CELL_ORDER",
    "V21B_FORMAL_GPUS", "V21B_FORBIDDEN_GPU", "V21B_WARM_START_PATH", "V21B_WARM_START_SHA256",
    "V21B_CONFIG_PATHS", "V21B_CELL_FACTORS", "V21B_F3_THETA_LADDER", "V21B_RESOLVED_ALLOWLIST", "canonical_json", "canonical_json_bytes", "sha256_file",
    "read_yaml", "write_json", "validate_v21b_config", "config_for_cell", "validate_resolved_v21b_parity", "assert_resolved_v21b_parity", "parse_gpus", "require_digest",
]
