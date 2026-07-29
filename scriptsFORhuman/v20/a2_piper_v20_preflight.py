"""CPU-only v20 provenance and v19 evidence-baseline preflight.

The preflight is deliberately strict.  It binds the v20 round to the single
G2 step-2000 checkpoint, the checkpoint-adjacent saved config, and the
authoritative v19 M22 evidence package.  It does not run Isaac Sim, rewrite
source evidence, or accept ``last.pt``/stale-path substitutions.

The command writes four deterministic files into a caller-owned result
directory.  The result directory must not already exist; an interrupted or
failed validation therefore cannot overwrite an earlier evidence unit.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import yaml


ROOT = Path(__file__).resolve().parents[2]
EXPECTED_CHECKPOINT_RELATIVE = Path(
    "logs_rl/a2_piper_full_stage_a2_base/base_v19/"
    "base_v19_G2_norm_control-20260727_012027/model_step_002000.pt"
)
EXPECTED_CHECKPOINT_SHA256 = (
    "b331c9a343c71dccf6cce31f71c1727a24298d72808c25763a0f702c369a866d"
)
EXPECTED_PLAN_RELATIVE = Path(
    "scriptsFORhuman/a2_piper_base_v20_optimization_plan_20260728.md"
)
EXPECTED_VALID_STATUSES = {"STRICT_VALID", "STRICT_INVALID"}
EXPECTED_GROUPS = tuple(f"G{index}" for index in range(1, 8))
EXPECTED_ROWS_PER_GROUP = 10
EXPECTED_VALID_ROWS = 55
EXPECTED_INVALID_ROWS = 15
EXPECTED_V20_CONFIG_NAMES = (
    "base_v20_G1_g2_continuation.yaml",
    "base_v20_G2_economics_only.yaml",
    "base_v20_G3_send_institution_only.yaml",
    "base_v20_G4_send_economics.yaml",
    "base_v20_G5_send_arm_tie.yaml",
    "base_v20_G6_full.yaml",
    "base_v20_G7_full_seed1.yaml",
)
EXPECTED_F1 = {
    "hinge_at_crossing_p50_max_rad": 0.7868818641,
    "hinge_at_crossing_p50_ge_0_9_count": 0,
    "hinge_at_crossing_p95_ge_1_0_count": 1,
    "root_x_at_release_p50_median_m": 0.686123848,
}
EXPECTED_F2 = {
    "G2": {
        "goal_pooled_count": 48,
        "crossing_while_holding_pooled_count": 48,
        "held_hinge_p50_rad": 1.4336078763008118,
        "held_hinge_p95_rad": 1.5430807173252106,
        "opening_slip_p95_cm": 2.908446555957198,
        "hinge_at_release_p50_rad": 1.6054893732070923,
        "overspeed_termination_count": 0,
        "post_release_body_contact_count": 0,
    },
    "G3": {
        "goal_pooled_count": 48,
        "crossing_while_holding_pooled_count": 48,
        "held_hinge_p50_rad": 1.2314069867134094,
        "held_hinge_p95_rad": 1.3122012257575988,
        "opening_slip_p95_cm": 3.5947084985673423,
        "hinge_at_release_p50_rad": 1.402049958705902,
        "overspeed_termination_count": 0,
        "post_release_body_contact_count": 0,
    },
}
CHECKPOINT_NAME_RE = re.compile(r"^model_step_002000\.pt$")
GROUP_RE = re.compile(r"(?:^|[/_])G([1-7])(?:_m22|[/_])")


class PreflightError(ValueError):
    """Raised when provenance, baseline, or output contracts are invalid."""


def _canonical_path(value: str | os.PathLike[str] | Path, name: str) -> Path:
    if not isinstance(value, (str, os.PathLike, Path)):
        raise PreflightError(f"{name} must be a path")
    path = Path(value).expanduser().resolve()
    if not path.exists():
        raise PreflightError(f"{name} does not exist: {path}")
    return path


def _resolve_reference(value: Any, *, repo_root: Path, name: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise PreflightError(f"{name} must be a non-empty path string")
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = repo_root / path
    return path.resolve()


def sha256_file(path: Path) -> str:
    """Hash one immutable input file in bounded chunks."""

    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise PreflightError(f"cannot read input file {path}: {exc}") from exc
    return digest.hexdigest()


def _reject_nonfinite(value: Any, location: str = "payload") -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise PreflightError(f"non-finite value at {location}")
    if isinstance(value, Mapping):
        for key, child in value.items():
            _reject_nonfinite(child, f"{location}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _reject_nonfinite(child, f"{location}[{index}]")


def _load_json(path: Path) -> Any:
    try:
        payload = json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=lambda token: (_ for _ in ()).throw(
                PreflightError(f"non-finite JSON constant {token!r} in {path}")
            ),
        )
    except PreflightError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PreflightError(f"cannot parse JSON {path}: {exc}") from exc
    _reject_nonfinite(payload, str(path))
    return payload


def _load_yaml(path: Path) -> Mapping[str, Any]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise PreflightError(f"cannot parse saved config {path}: {exc}") from exc
    _reject_nonfinite(payload, str(path))
    if not isinstance(payload, Mapping):
        raise PreflightError(f"saved config must be a mapping: {path}")
    return payload


def _finite_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PreflightError(f"{name} must be a finite number; got {value!r}")
    number = float(value)
    if not math.isfinite(number):
        raise PreflightError(f"{name} must be a finite number; got {value!r}")
    return number


def _exact_number(actual: Any, expected: float, name: str) -> None:
    if not math.isclose(_finite_number(actual, name), expected, rel_tol=0.0, abs_tol=1e-9):
        raise PreflightError(f"{name} must equal {expected!r}; got {actual!r}")


def _nested(mapping: Mapping[str, Any], *keys: str) -> Any:
    value: Any = mapping
    for key in keys:
        if not isinstance(value, Mapping) or key not in value:
            raise PreflightError(f"saved config is missing {'.'.join(keys)}")
        value = value[key]
    return value


def capture_git_state(repo_root: Path = ROOT) -> dict[str, Any]:
    """Record branch/head/worktree state without changing the worktree."""

    def run(*args: str) -> str:
        try:
            return subprocess.check_output(
                ["git", *args], cwd=repo_root, text=True, stderr=subprocess.STDOUT
            ).strip()
        except (OSError, subprocess.CalledProcessError) as exc:
            raise PreflightError(f"cannot capture git {' '.join(args)}: {exc}") from exc

    status = run("status", "--short", "--branch")
    return {
        "head": run("rev-parse", "HEAD"),
        "branch": run("branch", "--show-current"),
        "status_porcelain_branch": status,
        "status_lines": status.splitlines(),
    }


def validate_checkpoint(
    checkpoint_path: Path,
    *,
    repo_root: Path = ROOT,
    expected_path: Path | None = None,
    expected_sha256: str = EXPECTED_CHECKPOINT_SHA256,
) -> dict[str, Any]:
    """Require the immutable G2 step-2000 checkpoint and exact digest."""

    checkpoint = _canonical_path(checkpoint_path, "checkpoint")
    required = (repo_root / EXPECTED_CHECKPOINT_RELATIVE).resolve() if expected_path is None else Path(expected_path).expanduser().resolve()
    if checkpoint != required:
        raise PreflightError(
            "checkpoint path must be the exact G2 step-2000 path: "
            f"expected {required}, got {checkpoint}"
        )
    if not CHECKPOINT_NAME_RE.fullmatch(checkpoint.name):
        raise PreflightError("checkpoint basename must be model_step_002000.pt; last.pt is forbidden")
    actual_sha256 = sha256_file(checkpoint)
    if actual_sha256 != expected_sha256:
        raise PreflightError(
            f"checkpoint SHA-256 mismatch: expected {expected_sha256}, got {actual_sha256}"
        )
    return {
        "path": str(checkpoint),
        "relative_path": str(checkpoint.relative_to(repo_root))
        if checkpoint.is_relative_to(repo_root)
        else str(checkpoint),
        "sha256": actual_sha256,
        "load_contract": {"checkpoint_load_mode": "policy_only", "auto_load_latest": False},
    }


def validate_saved_config(
    config_path: Path,
    checkpoint: Mapping[str, Any],
    *,
    repo_root: Path = ROOT,
) -> dict[str, Any]:
    """Validate the checkpoint-adjacent v19 config without guessing values."""

    config_file = _canonical_path(config_path, "saved config")
    expected_config = Path(str(checkpoint["path"])).resolve().parent / "config.yaml"
    if config_file != expected_config:
        raise PreflightError(
            f"saved config must be adjacent to checkpoint: expected {expected_config}, got {config_file}"
        )
    config = _load_yaml(config_file)
    configured_checkpoint = _resolve_reference(
        config.get("checkpoint"), repo_root=repo_root, name="saved config checkpoint"
    )
    if not configured_checkpoint.is_file():
        raise PreflightError(
            f"historical saved-config source checkpoint does not exist: {configured_checkpoint}"
        )
    if configured_checkpoint.name == "last.pt" or not re.fullmatch(
        r"model_step_[0-9]{6}\.pt", configured_checkpoint.name
    ):
        raise PreflightError(
            "historical saved-config source must be an immutable numeric checkpoint; "
            f"got {configured_checkpoint}"
        )
    if config.get("checkpoint_load_mode") != "policy_only":
        raise PreflightError("saved config checkpoint_load_mode must be policy_only")
    if config.get("auto_load_latest") is not False:
        raise PreflightError("saved config auto_load_latest must be false")
    if config.get("num_envs") != 4096:
        raise PreflightError("saved config num_envs must equal historical 4096")

    env_config = _nested(config, "env", "config")
    if not isinstance(env_config, Mapping):
        raise PreflightError("saved config env.config must be a mapping")
    _exact_number(env_config.get("a2_stage4_release_hinge_threshold"), 1.60, "release threshold")
    _exact_number(env_config.get("a2_corridor_door_wide_hinge_norm"), 1.50, "wide norm")
    if env_config.get("a2_m39_gripper_material_enabled") is not True:
        raise PreflightError("saved config must enable M39 gripper material")
    if env_config.get("a2_arm_dof_overspeed_soft_margin_enabled") is not True:
        raise PreflightError("saved config must enable F2 soft margin")
    _exact_number(env_config.get("a2_arm_dof_overspeed_soft_margin_width"), 0.50, "F2 soft margin width")

    control = _nested(config, "robot", "control")
    stiffness = _nested(control, "stiffness")
    damping = _nested(control, "damping")
    _exact_number(stiffness.get("arm_j7"), 1300.0, "arm_j7 stiffness")
    _exact_number(stiffness.get("arm_j8"), 1300.0, "arm_j8 stiffness")
    _exact_number(damping.get("arm_j7"), 32.0, "arm_j7 damping")
    _exact_number(damping.get("arm_j8"), 32.0, "arm_j8 damping")
    effort_limits = _nested(config, "robot", "dof_effort_limit_list")
    if (
        not isinstance(effort_limits, list)
        or len(effort_limits) < 2
        or any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in effort_limits[-2:])
        or [float(item) for item in effort_limits[-2:]] != [45.0, 45.0]
    ):
        raise PreflightError("saved config gripper effort limits must end with [45, 45]")

    return {
        "path": str(config_file),
        "sha256": sha256_file(config_file),
        "validated_values": {
            "historical_source_checkpoint": str(configured_checkpoint),
            "historical_source_checkpoint_sha256": sha256_file(configured_checkpoint),
            "checkpoint_load_mode": config["checkpoint_load_mode"],
            "auto_load_latest": config["auto_load_latest"],
            "num_envs": config["num_envs"],
            "release_threshold_rad": 1.60,
            "wide_norm_rad": 1.50,
            "m39_gripper_material_enabled": True,
            "f2_soft_margin_enabled": True,
            "f2_soft_margin_width": 0.50,
            "gripper_effort_limits": [45.0, 45.0],
            "arm_j7_j8_stiffness": [1300.0, 1300.0],
            "arm_j7_j8_damping": [32.0, 32.0],
        },
    }


def validate_v20_configs(
    config_paths: Sequence[Path | str],
    *,
    checkpoint: Mapping[str, Any],
    repo_root: Path = ROOT,
    require_formal_frozen: bool = False,
) -> list[dict[str, Any]]:
    """Validate the seven v20 configs separately from historical G2 provenance."""

    paths = [_canonical_path(value, "v20 config") for value in config_paths]
    if len(paths) != len(EXPECTED_V20_CONFIG_NAMES):
        raise PreflightError(f"exactly seven v20 configs are required; got {len(paths)}")
    if len(set(paths)) != len(paths):
        raise PreflightError("v20 config paths must be unique")
    names = {path.name for path in paths}
    if names != set(EXPECTED_V20_CONFIG_NAMES):
        missing = sorted(set(EXPECTED_V20_CONFIG_NAMES) - names)
        extra = sorted(names - set(EXPECTED_V20_CONFIG_NAMES))
        raise PreflightError(f"v20 config filename matrix mismatch: missing={missing}, extra={extra}")

    expected_checkpoint = Path(str(checkpoint["path"])).resolve()
    records: list[dict[str, Any]] = []
    for path in sorted(paths, key=lambda item: EXPECTED_V20_CONFIG_NAMES.index(item.name)):
        config = _load_yaml(path)
        configured_checkpoint = _resolve_reference(
            config.get("checkpoint"), repo_root=repo_root, name=f"{path.name} checkpoint"
        )
        if configured_checkpoint != expected_checkpoint:
            raise PreflightError(
                f"{path.name} must warm-start from exact G2 step2000: "
                f"expected {expected_checkpoint}, got {configured_checkpoint}"
            )
        if config.get("checkpoint_load_mode") != "policy_only":
            raise PreflightError(f"{path.name} checkpoint_load_mode must be policy_only")
        if config.get("auto_load_latest") is not False:
            raise PreflightError(f"{path.name} auto_load_latest must be false")
        if config.get("num_envs") != 4096:
            raise PreflightError(f"{path.name} num_envs must equal 4096")
        group_index = EXPECTED_V20_CONFIG_NAMES.index(path.name) + 1
        expected_seed = 1 if group_index == 7 else 0
        if config.get("seed") != expected_seed:
            raise PreflightError(f"{path.name} seed must equal {expected_seed}")
        env_config = _nested(config, "env", "config")
        frozen = env_config.get("a2_v20_formal_values_frozen")
        if not isinstance(frozen, bool):
            raise PreflightError(
                f"{path.name} env.config.a2_v20_formal_values_frozen must be boolean"
            )
        formal_launch = env_config.get("a2_v20_formal_launch")
        calibration_label = env_config.get("a2_v20_calibration_label")
        if not isinstance(formal_launch, bool):
            raise PreflightError(
                f"{path.name} env.config.a2_v20_formal_launch must be boolean"
            )
        if not isinstance(calibration_label, str) or not calibration_label:
            raise PreflightError(
                f"{path.name} env.config.a2_v20_calibration_label must be non-empty"
            )
        if require_formal_frozen:
            if formal_launch is not True or frozen is not True or calibration_label == "non_formal_calibration_only":
                raise PreflightError(
                    f"{path.name} formal bundle requires formal_launch=true, "
                    "formal_values_frozen=true, and a non-calibration-only label"
                )
        elif (formal_launch, frozen, calibration_label) != (
            False,
            False,
            "non_formal_calibration_only",
        ):
            raise PreflightError(
                f"{path.name} non-formal provenance must be "
                "(formal_launch=false, formal_values_frozen=false, "
                "calibration_label=non_formal_calibration_only)"
            )
        records.append(
            {
                "group": f"G{group_index}",
                "path": str(path),
                "sha256": sha256_file(path),
                "seed": expected_seed,
                "formal_values_frozen": frozen,
                "formal_launch": formal_launch,
                "calibration_label": calibration_label,
                "checkpoint": str(configured_checkpoint),
            }
        )
    provenance = {
        (record["formal_launch"], record["formal_values_frozen"], record["calibration_label"])
        for record in records
    }
    if require_formal_frozen and len(provenance) != 1:
        raise PreflightError(
            f"formal bundle provenance triple must match across all seven configs; got {sorted(provenance)!r}"
        )
    return records


def _parse_csv_scalar(value: str) -> Any:
    text = value.strip()
    if text == "":
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _load_rows_file(path: Path) -> list[Mapping[str, Any]]:
    if path.suffix.lower() == ".csv":
        try:
            with path.open(newline="", encoding="utf-8") as handle:
                rows = [
                    {key: _parse_csv_scalar(value) for key, value in row.items()}
                    for row in csv.DictReader(handle)
                ]
        except (OSError, UnicodeError, csv.Error) as exc:
            raise PreflightError(f"cannot parse baseline CSV {path}: {exc}") from exc
        return rows
    payload = _load_json(path)
    if isinstance(payload, Mapping) and isinstance(payload.get("rows"), list):
        rows = payload["rows"]
    elif isinstance(payload, list):
        rows = payload
    elif isinstance(payload, Mapping):
        rows = [payload]
    else:
        raise PreflightError(f"baseline source must contain a row list: {path}")
    if any(not isinstance(row, Mapping) for row in rows):
        raise PreflightError(f"baseline rows must be mappings: {path}")
    return rows


def _derive_group(path: Path, row: Mapping[str, Any]) -> str | None:
    supplied = row.get("group") or row.get("group_id")
    if isinstance(supplied, str) and supplied in EXPECTED_GROUPS:
        return supplied
    for value in (str(path), str(row.get("checkpoint_path", "")), str(row.get("candidate_id", ""))):
        match = GROUP_RE.search(value)
        if match:
            return f"G{match.group(1)}"
    return None


def _normalize_baseline_row(raw: Mapping[str, Any], source_path: Path, *, repo_root: Path) -> dict[str, Any]:
    candidate = raw.get("candidate")
    nested_candidate = candidate if isinstance(candidate, Mapping) else {}
    candidate_id = raw.get("candidate_id") or nested_candidate.get("candidate_id")
    if not isinstance(candidate_id, str) or not candidate_id.strip():
        raise PreflightError(f"baseline row candidate_id is missing: {source_path}")
    status = raw.get("strict_status") or raw.get("status")
    if status not in EXPECTED_VALID_STATUSES:
        raise PreflightError(f"baseline row strict_status is invalid for {candidate_id}: {status!r}")
    group = _derive_group(source_path, raw)
    if group not in EXPECTED_GROUPS:
        raise PreflightError(f"baseline row group is missing or invalid for {candidate_id}")
    reason = raw.get("reason") or raw.get("exclusion_reason")
    if status == "STRICT_INVALID" and (not isinstance(reason, str) or not reason.strip()):
        raise PreflightError(f"STRICT_INVALID row requires an explicit reason: {candidate_id}")
    metrics = raw.get("metrics")
    if metrics is not None and not isinstance(metrics, Mapping):
        raise PreflightError(f"baseline row metrics must be a mapping or null: {candidate_id}")
    artifact_value = raw.get("artifact") or raw.get("evidence_provenance")
    artifact: Path | None = None
    if artifact_value is not None:
        artifact = _canonical_path(
            _resolve_reference(artifact_value, repo_root=repo_root, name=f"artifact for {candidate_id}"),
            f"artifact for {candidate_id}",
        )
    normalized = {
        "group": group,
        "candidate_id": candidate_id,
        "strict_status": status,
        "reason": reason if isinstance(reason, str) else None,
        "artifact": str(artifact) if artifact else None,
        "metrics": dict(metrics) if isinstance(metrics, Mapping) else None,
        "source_file": str(source_path),
        "source_row": dict(raw),
    }
    return normalized


def ingest_baseline_sources(
    sources: Sequence[Path | str], *, repo_root: Path = ROOT
) -> list[dict[str, Any]]:
    """Ingest and validate exactly seven 10-row v19 checkpoint packages."""

    if not sources:
        raise PreflightError("at least one v19 70-row baseline source is required")
    normalized: list[dict[str, Any]] = []
    seen_sources: set[Path] = set()
    for value in sources:
        path = _canonical_path(value, "baseline source")
        if path in seen_sources:
            raise PreflightError(f"duplicate baseline source: {path}")
        seen_sources.add(path)
        for raw in _load_rows_file(path):
            normalized.append(_normalize_baseline_row(raw, path, repo_root=repo_root))
    if len(normalized) != 70:
        raise PreflightError(f"v19 baseline must contain exactly 70 rows; got {len(normalized)}")
    counts = {group: 0 for group in EXPECTED_GROUPS}
    status_counts = {status: 0 for status in EXPECTED_VALID_STATUSES}
    identities: set[tuple[str, str]] = set()
    for row in normalized:
        identity = (row["group"], row["candidate_id"])
        if identity in identities:
            raise PreflightError(f"duplicate v19 baseline row identity: {identity}")
        identities.add(identity)
        counts[row["group"]] += 1
        status_counts[row["strict_status"]] += 1
    if any(counts[group] != EXPECTED_ROWS_PER_GROUP for group in EXPECTED_GROUPS):
        raise PreflightError(f"v19 baseline group coverage must be 10 rows each; got {counts}")
    if status_counts != {"STRICT_VALID": EXPECTED_VALID_ROWS, "STRICT_INVALID": EXPECTED_INVALID_ROWS}:
        raise PreflightError(
            "v19 baseline status coverage must be exactly 55 STRICT_VALID/15 STRICT_INVALID; "
            f"got {status_counts}"
        )
    return normalized


def _stats(values: Sequence[float | int | None]) -> dict[str, Any]:
    defined: list[float] = []
    for value in values:
        if value is None:
            continue
        defined.append(_finite_number(value, "baseline metric"))
    if not defined:
        return {"n": 0, "p50": None, "p95": None, "status": "N/A", "reason": "no_defined_values"}
    ordered = sorted(defined)
    p50 = statistics.quantiles(ordered, n=100, method="inclusive")[49] if len(ordered) > 1 else ordered[0]
    p95 = statistics.quantiles(ordered, n=100, method="inclusive")[94] if len(ordered) > 1 else ordered[0]
    return {"n": len(ordered), "p50": p50, "p95": p95, "status": "DEFINED", "reason": None}


def _record_metric_stats(artifact: Path, field: str) -> dict[str, Any] | None:
    records_path = artifact / "a2_v14_per_env_records.json"
    if not records_path.exists():
        return None
    payload = _load_json(records_path)
    if not isinstance(payload, list) or any(not isinstance(item, Mapping) for item in payload):
        raise PreflightError(f"records payload must be a list of mappings: {records_path}")
    return _stats([item.get(field) for item in payload])


def _direct_metric_stats(row: Mapping[str, Any], field: str) -> dict[str, Any] | None:
    metrics = row.get("metrics")
    if not isinstance(metrics, Mapping):
        return None
    direct = metrics.get(field)
    if isinstance(direct, Mapping):
        if "p50" in direct or "p95" in direct:
            p50 = direct.get("p50")
            p95 = direct.get("p95")
            if p50 is not None:
                _finite_number(p50, f"{field}.p50")
            if p95 is not None:
                _finite_number(p95, f"{field}.p95")
            if p50 is None and p95 is None:
                return {"n": 0, "p50": None, "p95": None, "status": "N/A", "reason": "source_metric_N/A"}
            return {"n": direct.get("n"), "p50": p50, "p95": p95, "status": "DEFINED", "reason": None}
    p50_key = f"{field}_p50"
    p95_key = f"{field}_p95"
    if p50_key in metrics or p95_key in metrics:
        p50 = metrics.get(p50_key)
        p95 = metrics.get(p95_key)
        if p50 is not None:
            _finite_number(p50, p50_key)
        if p95 is not None:
            _finite_number(p95, p95_key)
        return {"n": metrics.get(f"{field}_n"), "p50": p50, "p95": p95, "status": "DEFINED", "reason": None}
    return None


def reproduce_f1(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Reproduce the F1 boundary aggregates when per-env records are present."""

    row_metrics: list[dict[str, Any]] = []
    for row in rows:
        if row.get("strict_status") != "STRICT_VALID":
            continue
        values: dict[str, dict[str, Any] | None] = {}
        for field in ("hinge_at_crossing", "root_x_at_release"):
            stats = _direct_metric_stats(row, field)
            if stats is None and row.get("artifact"):
                stats = _record_metric_stats(Path(str(row["artifact"])), field)
            values[field] = stats
        row_metrics.append({
            "group": row.get("group"),
            "candidate_id": row.get("candidate_id"),
            "hinge_at_crossing": values["hinge_at_crossing"],
            "root_x_at_release": values["root_x_at_release"],
        })
    hinge_rows = [item for item in row_metrics if item["hinge_at_crossing"] and item["hinge_at_crossing"].get("p50") is not None]
    root_rows = [item for item in row_metrics if item["root_x_at_release"] and item["root_x_at_release"].get("p50") is not None]
    result: dict[str, Any] = {"row_metrics": row_metrics, "status": "DEFINED"}
    if len(hinge_rows) != EXPECTED_VALID_ROWS or len(root_rows) != EXPECTED_VALID_ROWS:
        result["status"] = "N/A_SCHEMA_UNSUPPORTED"
        result["reason"] = (
            "F1 boundary fields are unavailable for all strict-valid rows; "
            f"hinge rows={len(hinge_rows)}, root-release rows={len(root_rows)}"
        )
        result["aggregates"] = {
            key: None for key in EXPECTED_F1
        }
        return result
    hinge_p50_values = [float(item["hinge_at_crossing"]["p50"]) for item in hinge_rows]
    hinge_p95_values = [float(item["hinge_at_crossing"]["p95"]) for item in hinge_rows]
    root_p50_values = [float(item["root_x_at_release"]["p50"]) for item in root_rows]
    max_item = max(hinge_rows, key=lambda item: float(item["hinge_at_crossing"]["p50"]))
    aggregates = {
        "hinge_at_crossing_p50_max_rad": max(hinge_p50_values),
        "hinge_at_crossing_p50_max_row": {
            "group": max_item["group"],
            "candidate_id": max_item["candidate_id"],
        },
        "hinge_at_crossing_p50_ge_0_9_count": sum(value >= 0.9 for value in hinge_p50_values),
        "hinge_at_crossing_p95_ge_1_0_count": sum(value >= 1.0 for value in hinge_p95_values),
        "root_x_at_release_p50_median_m": statistics.median(root_p50_values),
        "denominators": {
            "strict_valid_rows": EXPECTED_VALID_ROWS,
            "hinge_at_crossing_rows": len(hinge_rows),
            "root_x_at_release_rows": len(root_rows),
        },
    }
    mismatches = []
    for key, expected in EXPECTED_F1.items():
        actual = aggregates[key]
        if isinstance(expected, int):
            if actual != expected:
                mismatches.append(f"{key}: expected {expected}, got {actual}")
        elif not math.isclose(float(actual), expected, rel_tol=0.0, abs_tol=1e-9):
            mismatches.append(f"{key}: expected {expected}, got {actual}")
    if mismatches:
        raise PreflightError("F1 aggregate mismatch: " + "; ".join(mismatches))
    result["aggregates"] = aggregates
    result["plan_boundary_match"] = True
    return result


def _parse_count(value: Any, name: str) -> int | None:
    if isinstance(value, Mapping):
        value = value.get("count")
    elif isinstance(value, str):
        match = re.match(r"^\s*([0-9]+)\s*/\s*([0-9]+)\s*$", value)
        if match:
            return int(match.group(1))
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise PreflightError(f"{name} count must be an integer or count/total text")
    return value


def _parse_final_markdown(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise PreflightError(f"cannot read final Markdown {path}: {exc}") from exc
    groups: dict[str, dict[str, Any]] = {}
    for line in text.splitlines():
        if not line.lstrip().startswith("| G"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 9 or cells[0] not in {"G2", "G3"}:
            continue
        held_parts = cells[4].split("/")
        if len(held_parts) != 2:
            raise PreflightError(f"final Markdown held p50/p95 is malformed: {line}")
        goal_parts = cells[2].split(";")
        goal_pooled = _parse_count(goal_parts[-1].strip(), f"{cells[0]} goal")
        crossing = _parse_count(cells[3], f"{cells[0]} crossing")
        overspeed = _parse_count(cells[5], f"{cells[0]} overspeed")
        groups[cells[0]] = {
            "metrics": {
                "goal_pooled_count": goal_pooled,
                "crossing_while_holding_pooled_count": crossing,
                "held_hinge_p50_rad": float(held_parts[0]),
                "held_hinge_p95_rad": float(held_parts[1]),
                "opening_slip_p95_cm": float(cells[6]),
                "hinge_at_release_p50_rad": float(cells[7]),
                "overspeed_termination_count": overspeed,
                "post_release_body_contact_count": None,
            }
        }
    if set(groups) != {"G2", "G3"}:
        raise PreflightError(f"final Markdown must contain G2 and G3 endpoint rows: {path}")
    return {"groups": groups, "format": "markdown"}


def _load_final_analysis(path: Path) -> dict[str, Any]:
    if path.suffix.lower() == ".md":
        return _parse_final_markdown(path)
    payload = _load_json(path)
    if not isinstance(payload, Mapping):
        raise PreflightError("final analysis must be a JSON mapping")
    groups = payload.get("groups")
    if not isinstance(groups, Mapping):
        raise PreflightError("final analysis JSON is missing groups")
    for group in ("G2", "G3"):
        if not isinstance(groups.get(group), Mapping):
            raise PreflightError(f"final analysis JSON is missing {group}")
    return dict(payload)


def _iter_payload_rows(payload: Any) -> Iterable[Mapping[str, Any]]:
    if isinstance(payload, Mapping):
        rows = payload.get("rows")
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, Mapping):
                    yield row
        if payload.get("candidate_id") or isinstance(payload.get("candidate"), Mapping):
            yield payload
        for key in ("selected_checkpoint",):
            value = payload.get(key)
            if isinstance(value, Mapping):
                yield value
    elif isinstance(payload, list):
        for row in payload:
            if isinstance(row, Mapping):
                yield row


def _row_checkpoint(row: Mapping[str, Any]) -> tuple[str | None, str | None]:
    candidate = row.get("candidate") if isinstance(row.get("candidate"), Mapping) else {}
    checkpoint = row.get("checkpoint_path") or candidate.get("path") or row.get("path")
    digest = row.get("checkpoint_sha256") or candidate.get("sha256") or row.get("sha256")
    return (str(checkpoint) if checkpoint is not None else None, str(digest) if digest is not None else None)


def _final_group_metrics(group: Mapping[str, Any]) -> dict[str, Any]:
    metrics = group.get("metrics")
    if not isinstance(metrics, Mapping):
        metrics = {}
    gates = group.get("gates") if isinstance(group.get("gates"), Mapping) else {}

    def value(key: str, gate_key: str | None = None) -> Any:
        if key in metrics:
            return metrics[key]
        if gate_key and isinstance(gates.get(gate_key), Mapping):
            return gates[gate_key].get("observed")
        return None

    return {
        "goal_pooled_count": value("goal_pooled_count", "goal_pooled"),
        "crossing_while_holding_pooled_count": value(
            "crossing_while_holding_pooled_count", "crossing_while_holding_pooled"
        ),
        "held_hinge_p50_rad": value("held_hinge_p50_rad"),
        "held_hinge_p95_rad": value("held_hinge_p95_rad"),
        "opening_slip_p95_cm": value("opening_slip_p95_cm"),
        "hinge_at_release_p50_rad": value("hinge_at_release_p50_rad"),
        "overspeed_termination_count": value("overspeed_termination_count", "overspeed_terminations"),
        "post_release_body_contact_count": value("post_release_body_contact_count", "post_release_body_contact_count"),
    }


def reproduce_f2(
    pooled_sources: Sequence[Path | str],
    final_analysis_path: Path | str,
    *,
    repo_root: Path = ROOT,
) -> dict[str, Any]:
    """Bind selected G2/G3 pooled rows to final endpoint boundary metrics."""

    if not pooled_sources:
        raise PreflightError("at least one selected pooled source is required")
    pooled_payloads: list[tuple[Path, Any]] = []
    for value in pooled_sources:
        path = _canonical_path(value, "selected pooled source")
        payload = _load_json(path) if path.suffix.lower() == ".json" else _parse_final_markdown(path)
        pooled_payloads.append((path, payload))
    final_path = _canonical_path(final_analysis_path, "final analysis")
    final = _load_final_analysis(final_path)
    groups = final["groups"]
    result: dict[str, Any] = {"status": "DEFINED", "groups": {}}
    for group_name in ("G2", "G3"):
        group = groups[group_name]
        final_metrics = _final_group_metrics(group)
        checkpoint_value = group.get("checkpoint") if isinstance(group, Mapping) else None
        digest_value = group.get("checkpoint_sha256") if isinstance(group, Mapping) else None
        matches: list[dict[str, Any]] = []
        for source_path, payload in pooled_payloads:
            source_group_match = f"/{group_name}/" in source_path.as_posix() or f"{group_name}_m22" in source_path.as_posix()
            for row in _iter_payload_rows(payload):
                row_status = row.get("strict_status") or row.get("status")
                row_checkpoint, row_digest = _row_checkpoint(row)
                if row_status != "STRICT_VALID":
                    continue
                if checkpoint_value is not None:
                    candidate_path = _resolve_reference(checkpoint_value, repo_root=repo_root, name=f"{group_name} checkpoint")
                    if row_checkpoint is not None and _resolve_reference(row_checkpoint, repo_root=repo_root, name=f"{group_name} pooled checkpoint") != candidate_path:
                        continue
                elif not source_group_match:
                    continue
                if digest_value is not None and row_digest is not None and row_digest != digest_value:
                    continue
                matches.append({"source_file": str(source_path), "row": dict(row)})
        if not matches:
            raise PreflightError(f"selected pooled sources do not bind a STRICT_VALID {group_name} row")
        observed = dict(final_metrics)
        expected = EXPECTED_F2[group_name]
        available = all(observed.get(key) is not None for key in expected)
        if not available:
            result["status"] = "N/A_SCHEMA_UNSUPPORTED"
            result["groups"][group_name] = {
                "selected_sources": matches,
                "metrics": observed,
                "status": "N/A_SCHEMA_UNSUPPORTED",
                "reason": "F2 boundary fields are absent from final analysis schema",
            }
            continue
        mismatches = []
        for key, expected_value in expected.items():
            actual = observed[key]
            if isinstance(expected_value, int):
                if actual != expected_value:
                    mismatches.append(f"{group_name}.{key}: expected {expected_value}, got {actual}")
            elif not math.isclose(float(actual), expected_value, rel_tol=0.0, abs_tol=1e-6):
                mismatches.append(f"{group_name}.{key}: expected {expected_value}, got {actual}")
        if mismatches:
            raise PreflightError("F2 aggregate mismatch: " + "; ".join(mismatches))
        result["groups"][group_name] = {
            "selected_sources": matches,
            "checkpoint": checkpoint_value,
            "checkpoint_sha256": digest_value,
            "metrics": observed,
            "status": "DEFINED",
            "plan_boundary_match": True,
        }
    return result


def _input_hashes(paths: Iterable[Path]) -> list[dict[str, str]]:
    unique = sorted({path.resolve() for path in paths}, key=lambda item: str(item))
    return [{"path": str(path), "sha256": sha256_file(path)} for path in unique]


def _jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _jsonable(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(child) for child in value]
    return value


def build_preflight(
    *,
    output_dir: Path | str,
    baseline_sources: Sequence[Path | str],
    pooled_sources: Sequence[Path | str],
    final_analysis: Path | str,
    plan: Path | str | None = None,
    checkpoint: Path | str | None = None,
    config: Path | str | None = None,
    v20_files: Sequence[Path | str] = (),
    v20_configs: Sequence[Path | str] = (),
    require_formal_frozen: bool = False,
    repo_root: Path = ROOT,
    expected_checkpoint_path: Path | None = None,
    expected_checkpoint_sha256: str = EXPECTED_CHECKPOINT_SHA256,
) -> dict[str, Any]:
    """Validate all P0 inputs and atomically write the canonical artifacts."""

    repo_root = Path(repo_root).expanduser().resolve()
    plan_path = _canonical_path(plan or repo_root / EXPECTED_PLAN_RELATIVE, "v20 plan")
    checkpoint_path = _canonical_path(
        checkpoint or repo_root / EXPECTED_CHECKPOINT_RELATIVE, "checkpoint"
    )
    checkpoint_info = validate_checkpoint(
        checkpoint_path,
        repo_root=repo_root,
        expected_path=expected_checkpoint_path,
        expected_sha256=expected_checkpoint_sha256,
    )
    config_path = _canonical_path(
        config or Path(checkpoint_info["path"]).parent / "config.yaml", "saved config"
    )
    config_info = validate_saved_config(config_path, checkpoint_info, repo_root=repo_root)
    v20_config_info = validate_v20_configs(
        v20_configs,
        checkpoint=checkpoint_info,
        repo_root=repo_root,
        require_formal_frozen=require_formal_frozen,
    )
    baseline_rows = ingest_baseline_sources(baseline_sources, repo_root=repo_root)
    f1 = reproduce_f1(baseline_rows)
    f2 = reproduce_f2(pooled_sources, final_analysis, repo_root=repo_root)

    input_paths = [plan_path, Path(checkpoint_info["path"]), config_path]
    input_paths += [_canonical_path(value, "v20 input") for value in v20_files]
    input_paths += [_canonical_path(value, "v20 config") for value in v20_configs]
    input_paths += [_canonical_path(value, "baseline source") for value in baseline_sources]
    input_paths += [_canonical_path(value, "selected pooled source") for value in pooled_sources]
    input_paths += [_canonical_path(final_analysis, "final analysis")]
    hashes = _input_hashes(input_paths)
    payload = {
        "schema": "a2_piper_v20_preflight_v1",
        "status": "PASS",
        "provenance": {
            "git": capture_git_state(repo_root),
            "checkpoint": checkpoint_info,
            "saved_config": config_info,
            "plan": {"path": str(plan_path), "sha256": sha256_file(plan_path)},
            "v20_files": [str(_canonical_path(value, "v20 input")) for value in v20_files],
            "v20_configs": v20_config_info,
            "formal_values_required_frozen": require_formal_frozen,
        },
        "baseline_coverage": {
            "total_rows": len(baseline_rows),
            "strict_valid": sum(row["strict_status"] == "STRICT_VALID" for row in baseline_rows),
            "strict_invalid": sum(row["strict_status"] == "STRICT_INVALID" for row in baseline_rows),
            "groups": {group: sum(row["group"] == group for row in baseline_rows) for group in EXPECTED_GROUPS},
        },
        "baseline_rows": baseline_rows,
        "f1": f1,
        "f2": f2,
        "input_hashes": hashes,
    }
    _reject_nonfinite(payload)
    write_preflight_outputs(payload, Path(output_dir))
    return payload


def _csv_rows(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in payload["baseline_rows"]:
        f1_row = next(
            (
                item
                for item in payload["f1"].get("row_metrics", [])
                if item["group"] == row["group"] and item["candidate_id"] == row["candidate_id"]
            ),
            {},
        )
        hinge = f1_row.get("hinge_at_crossing") or {}
        root = f1_row.get("root_x_at_release") or {}
        rows.append(
            {
                "group": row["group"],
                "candidate_id": row["candidate_id"],
                "strict_status": row["strict_status"],
                "reason": row.get("reason"),
                "artifact": row.get("artifact"),
                "hinge_at_crossing_p50_rad": hinge.get("p50"),
                "hinge_at_crossing_p95_rad": hinge.get("p95"),
                "root_x_at_release_p50_m": root.get("p50"),
                "root_x_at_release_p95_m": root.get("p95"),
            }
        )
    return rows


def _markdown(payload: Mapping[str, Any]) -> str:
    coverage = payload["baseline_coverage"]
    lines = [
        "# A2 Piper v20 preflight",
        "",
        "Status: **PASS**",
        "",
        "## Provenance",
        "",
        f"- HEAD: `{payload['provenance']['git']['head']}`",
        f"- Checkpoint: `{payload['provenance']['checkpoint']['path']}`",
        f"- Checkpoint SHA-256: `{payload['provenance']['checkpoint']['sha256']}`",
        f"- Saved config: `{payload['provenance']['saved_config']['path']}`",
        "- Load contract: `policy_only`, `auto_load_latest=false`",
        "",
        "## v19 baseline coverage",
        "",
        f"- Rows: `{coverage['total_rows']}` (STRICT_VALID `{coverage['strict_valid']}`, STRICT_INVALID `{coverage['strict_invalid']}`)",
        "- Group coverage: " + ", ".join(f"{group}={coverage['groups'][group]}" for group in EXPECTED_GROUPS),
        "",
        "## F1 boundary aggregates",
        "",
    ]
    f1 = payload["f1"]
    if f1.get("status") == "DEFINED":
        agg = f1["aggregates"]
        lines.extend(
            [
                f"- max hinge-at-crossing p50: `{agg['hinge_at_crossing_p50_max_rad']:.10f} rad`",
                f"- hinge-at-crossing p50 >= 0.9 rad: `{agg['hinge_at_crossing_p50_ge_0_9_count']}/55`",
                f"- hinge-at-crossing p95 >= 1.0 rad: `{agg['hinge_at_crossing_p95_ge_1_0_count']}/55`",
                f"- median root-x-at-release p50: `{agg['root_x_at_release_p50_median_m']:.10f} m`",
            ]
        )
    else:
        lines.append(f"- `{f1.get('status')}`: {f1.get('reason')}")
    lines.extend(["", "## F2 selected pooled boundary", "", "| Group | Goal | Crossing-held | Held p50/p95 rad | Opening slip p95 cm | Release p50 rad | Overspeed | Body contact |", "|---|---:|---:|---:|---:|---:|---:|---:|"])
    for group in ("G2", "G3"):
        metrics = payload["f2"]["groups"][group]["metrics"]
        held = f"{metrics['held_hinge_p50_rad']:.6f}/{metrics['held_hinge_p95_rad']:.6f}" if metrics.get("held_hinge_p50_rad") is not None else "N/A"
        lines.append(
            f"| {group} | {metrics.get('goal_pooled_count', 'N/A')}/48 | {metrics.get('crossing_while_holding_pooled_count', 'N/A')}/48 | {held} | {metrics.get('opening_slip_p95_cm', 'N/A')} | {metrics.get('hinge_at_release_p50_rad', 'N/A')} | {metrics.get('overspeed_termination_count', 'N/A')} | {metrics.get('post_release_body_contact_count', 'N/A')} |"
        )
    lines.extend(["", "STRICT_INVALID rows and source N/A values are retained verbatim; no fallback checkpoint or fabricated zero is used.", ""])
    return "\n".join(lines)


def write_preflight_outputs(payload: Mapping[str, Any], output_dir: Path) -> None:
    """Write JSON/CSV/Markdown/hash files with no-overwrite reservation."""

    output_dir = output_dir.expanduser().resolve()
    parent = output_dir.parent
    parent.mkdir(parents=True, exist_ok=True)
    if output_dir.exists():
        raise PreflightError(f"refusing to overwrite existing output directory: {output_dir}")
    temporary = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.", dir=str(parent)))
    try:
        json_path = temporary / "a2_piper_v20_preflight.json"
        csv_path = temporary / "a2_piper_v20_preflight.csv"
        markdown_path = temporary / "a2_piper_v20_preflight.md"
        manifest_path = temporary / "file_hashes.sha256"
        json_path.write_text(
            json.dumps(_jsonable(payload), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        rows = _csv_rows(payload)
        fieldnames = list(rows[0]) if rows else []
        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="raise")
            writer.writeheader()
            writer.writerows(rows)
        markdown_path.write_text(_markdown(payload), encoding="utf-8")
        manifest_path.write_text(
            "".join(f"{item['sha256']}  {item['path']}\n" for item in payload["input_hashes"]),
            encoding="utf-8",
        )
        if output_dir.exists():
            raise PreflightError(f"refusing to overwrite output directory created concurrently: {output_dir}")
        os.replace(temporary, output_dir)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--plan", type=Path, default=None)
    parser.add_argument("--checkpoint", type=Path, default=None)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--baseline-70", type=Path, action="append", required=True)
    parser.add_argument("--selected-pooled", type=Path, action="append", required=True)
    parser.add_argument("--final-analysis", type=Path, required=True)
    parser.add_argument("--v20-file", type=Path, action="append", default=[])
    parser.add_argument("--v20-config", type=Path, action="append", required=True)
    parser.add_argument("--require-formal-frozen", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        build_preflight(
            output_dir=args.output_dir,
            baseline_sources=args.baseline_70,
            pooled_sources=args.selected_pooled,
            final_analysis=args.final_analysis,
            plan=args.plan,
            checkpoint=args.checkpoint,
            config=args.config,
            v20_files=args.v20_file,
            v20_configs=args.v20_config,
            require_formal_frozen=args.require_formal_frozen,
        )
    except PreflightError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2
    print(f"PASS: wrote {args.output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
