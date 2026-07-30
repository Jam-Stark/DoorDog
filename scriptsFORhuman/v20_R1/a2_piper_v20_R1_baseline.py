"""Validate the immutable, plan-bound no-learning B0 reference."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _r1_common import (  # noqa: E402
    B0_COMPANION_SCHEMA,
    B0_CSV_NAME,
    B0_CSV_SHA256,
    B0_POOLED48_EXPECTED,
    B0_SOURCE_BINDINGS,
    B0_TASKSPACE_DIAGNOSTIC_EXPECTED,
    B0_JSON_NAME,
    B0_JSON_SHA256,
    CHECKPOINT_CONFIG_PATH,
    CHECKPOINT_PATH,
    CHECKPOINT_SHA256,
    PLAN_ID,
    RUNTIME_SEMANTIC_PASS,
    device_env,
    validate_gpu,
    R1Error,
    resolve_repo_path,
    sha256_file,
    validate_exact_hash,
    write_json_no_overwrite,
)


SCHEMA = B0_COMPANION_SCHEMA
BASELINE_MANIFEST_SCHEMA = "a2_piper_v20_R1_B0_baseline_manifest_v2"


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise R1Error(f"B0 {name} must be a mapping")
    return value


def _required(mapping: Mapping[str, Any], key: str, name: str) -> Any:
    if key not in mapping:
        raise R1Error(f"B0 {name} missing required field {key}")
    return mapping[key]


def _finite(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise R1Error(f"B0 {name} must be finite")
    return float(value)


def _close(actual: Any, expected: float, tolerance: float, name: str) -> None:
    value = _finite(actual, name)
    if abs(value - expected) > tolerance:
        raise R1Error(f"B0 {name} outside frozen tolerance {tolerance}: expected {expected}, got {value}")


def _exact(actual: Any, expected: Any, name: str) -> None:
    if actual != expected or isinstance(actual, bool) != isinstance(expected, bool):
        raise R1Error(f"B0 {name} mismatch: expected {expected!r}, got {actual!r}")


def _validate_metric_group(actual: Mapping[str, Any], expected: Mapping[str, Any], name: str, tolerance: float = 1e-6) -> None:
    for key, target in expected.items():
        value = _required(actual, key, name)
        if isinstance(target, Mapping):
            _validate_metric_group(_mapping(value, f"{name}.{key}"), target, f"{name}.{key}", tolerance)
        else:
            _close(value, float(target), tolerance, f"{name}.{key}")


def _validate_pooled48(payload: Mapping[str, Any]) -> None:
    pooled = _mapping(_required(payload, "pooled48_frozen", "companion"), "pooled48_frozen")
    expected = B0_POOLED48_EXPECTED
    for key in ("episodes", "goal_count", "crossing_while_holding_count", "overspeed_termination_count", "post_release_body_contact_count"):
        _exact(_required(pooled, key, "pooled48_frozen"), expected[key], f"pooled48_frozen.{key}")
    _exact(_required(pooled, "seeds", "pooled48_frozen"), expected["seeds"], "pooled48_frozen.seeds")
    for key in ("post_release_body_force_p95_n", "pre_crossing_bilateral_rate", "pre_crossing_coasting_rate", "pre_crossing_over_force_rate"):
        _close(_required(pooled, key, "pooled48_frozen"), expected[key], 1e-6, f"pooled48_frozen.{key}")
    for key in ("hinge_at_first_root_crossing_rad", "held_hinge_rad", "opening_slip_cm", "release_hinge_rad", "pre_crossing_hinge_velocity_radps", "root_x_at_release_m", "task_time_s"):
        group = _mapping(_required(pooled, key, "pooled48_frozen"), f"pooled48_frozen.{key}")
        for field in expected[key]:
            _close(_required(group, field, f"pooled48_frozen.{key}"), expected[key][field], 1e-6, f"pooled48_frozen.{key}.{field}")
        n = group.get("n")
        if n is not None and (isinstance(n, bool) or not isinstance(n, int) or n <= 0):
            raise R1Error(f"pooled48_frozen.{key}.n must be a positive integer")


def _validate_taskspace(payload: Mapping[str, Any]) -> None:
    diagnostic = _mapping(_required(payload, "taskspace_trace_diagnostic", "companion"), "taskspace_trace_diagnostic")
    expected = B0_TASKSPACE_DIAGNOSTIC_EXPECTED
    _exact(_required(diagnostic, "classification", "taskspace_trace_diagnostic"), expected["classification"], "taskspace_trace_diagnostic.classification")
    _validate_metric_group(_mapping(_required(diagnostic, "combined_step_distribution", "taskspace_trace_diagnostic"), "combined_step_distribution"), expected["combined_step_distribution"], "taskspace_trace_diagnostic.combined_step_distribution", 1e-6)
    _close(_required(diagnostic, "median_of_episode_arm_share_p50", "taskspace_trace_diagnostic"), expected["median_of_episode_arm_share_p50"], 1e-6, "taskspace_trace_diagnostic.median_of_episode_arm_share_p50")
    _validate_metric_group(_mapping(_required(diagnostic, "worst_episode_p95", "taskspace_trace_diagnostic"), "worst_episode_p95"), expected["worst_episode_p95"], "taskspace_trace_diagnostic.worst_episode_p95", 1e-6)
    for key in ("aggregation",):
        value = _required(diagnostic, key, "taskspace_trace_diagnostic")
        if not isinstance(value, str) or not value:
            raise R1Error(f"taskspace_trace_diagnostic.{key} must be concrete")
    per_env = _required(diagnostic, "per_env", "taskspace_trace_diagnostic")
    if not isinstance(per_env, list) or len(per_env) != 2:
        raise R1Error("taskspace_trace_diagnostic.per_env must contain exactly two episodes")


def _validate_companion(payload: Mapping[str, Any]) -> dict[str, Any]:
    if _required(payload, "schema", "companion") != B0_COMPANION_SCHEMA:
        raise R1Error("B0 companion schema mismatch")
    for key in ("created_at", "checkpoint", "pooled48_frozen", "source_files", "taskspace_trace_diagnostic", "usage_contract"):
        _required(payload, key, "companion")
    checkpoint = _mapping(payload["checkpoint"], "checkpoint")
    _exact(_required(checkpoint, "path", "checkpoint"), CHECKPOINT_PATH, "checkpoint.path")
    _exact(_required(checkpoint, "sha256", "checkpoint"), CHECKPOINT_SHA256, "checkpoint.sha256")
    source_files = _mapping(payload["source_files"], "source_files")
    expected_sources = {relative: digest for _, relative, digest in B0_SOURCE_BINDINGS}
    if dict(source_files) != expected_sources:
        raise R1Error("B0 source_files do not exactly match the authoritative six bindings")
    usage = _mapping(payload["usage_contract"], "usage_contract")
    _exact(_required(usage, "no_posthoc_threshold_change", "usage_contract"), True, "usage_contract.no_posthoc_threshold_change")
    _exact(_required(usage, "pooled48_frozen", "usage_contract"), "authoritative B0 for task/safety/crossing", "usage_contract.pooled48_frozen")
    _exact(_required(usage, "taskspace_trace_diagnostic", "usage_contract"), "numeric prior and parity target only; formal R1 task-space B0 must be regenerated by a no-learning pooled48 v20 telemetry evaluation before pilot", "usage_contract.taskspace_trace_diagnostic")
    _validate_pooled48(payload)
    _validate_taskspace(payload)
    return dict(payload)


def _validate_csv(path: Path) -> None:
    validate_exact_hash(path, B0_CSV_SHA256, "B0 CSV companion")
    data = path.read_bytes()
    if b"\r\n" not in data or b"\n" in data.replace(b"\r\n", b""):
        raise R1Error("B0 CSV must preserve CRLF bytes")
    rows = list(csv.reader(data.decode("utf-8").splitlines()))
    if not rows or rows[0] != ["section", "metric", "value", "unit", "classification"]:
        raise R1Error("B0 CSV header mismatch")
    if len(rows) != 16:
        raise R1Error(f"B0 CSV row count mismatch: expected 16, got {len(rows)}")
    if any(len(row) != 5 or row[4] not in {"AUTHORITATIVE", "DIAGNOSTIC_ONLY"} for row in rows[1:]):
        raise R1Error("B0 CSV contains malformed classification rows")


def _source_rows(repo_root: Path, source_artifacts: Sequence[Path] | None) -> list[dict[str, str]]:
    expected_paths = [resolve_repo_path(repo_root, relative) for _, relative, _ in B0_SOURCE_BINDINGS]
    if source_artifacts is not None and [Path(path).resolve() for path in source_artifacts] != expected_paths:
        raise R1Error("B0 source_artifacts must match the six exact authoritative paths in order")
    rows = []
    for name, relative, expected_sha in B0_SOURCE_BINDINGS:
        path = resolve_repo_path(repo_root, relative)
        validate_exact_hash(path, expected_sha, f"B0 {name}")
        rows.append({"name": name, "relative_path": relative, "sha256": expected_sha})
    return rows


def _load_authoritative(repo_root: Path) -> dict[str, Any]:
    companion = resolve_repo_path(repo_root, "scriptsFORhuman/v20_R1/" + B0_JSON_NAME)
    validate_exact_hash(companion, B0_JSON_SHA256, "B0 JSON companion")
    try:
        payload = json.loads(companion.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise R1Error("B0 JSON companion is not valid JSON") from exc
    return _validate_companion(_mapping(payload, "companion"))


def build_b0_companion(*, repo_root: Path, output_dir: Path | None = None) -> dict[str, Any]:
    root = repo_root.resolve()
    payload = _load_authoritative(root)
    source_rows = _source_rows(root, None)
    checkpoint = resolve_repo_path(root, CHECKPOINT_PATH)
    validate_exact_hash(checkpoint, CHECKPOINT_SHA256, "B0 checkpoint")
    config = resolve_repo_path(root, CHECKPOINT_CONFIG_PATH)
    if not config.is_file() or config.is_symlink():
        raise R1Error("B0 adjacent checkpoint config is missing or symlinked")
    csv_path = resolve_repo_path(root, "scriptsFORhuman/v20_R1/" + B0_CSV_NAME)
    _validate_csv(csv_path)
    if output_dir is not None:
        manifest = {"schema": BASELINE_MANIFEST_SCHEMA, "companion": {"path": "scriptsFORhuman/v20_R1/" + B0_JSON_NAME, "sha256": B0_JSON_SHA256}, "checkpoint": {"path": CHECKPOINT_PATH, "sha256": CHECKPOINT_SHA256}, "source_files": source_rows}
        write_json_no_overwrite(output_dir / "B0_G2_step2000_pooled48.json", manifest)
    return payload


def build_baseline_manifest(*, source_artifacts: list[Path] | None = None, repo_root: Path | None = None, output_dir: Path | None = None) -> dict[str, Any]:
    root = (repo_root or Path(__file__).resolve().parents[2]).resolve()
    payload = build_b0_companion(repo_root=root)
    source_rows = _source_rows(root, source_artifacts)
    checkpoint = resolve_repo_path(root, CHECKPOINT_PATH)
    config = resolve_repo_path(root, CHECKPOINT_CONFIG_PATH)
    manifest: dict[str, Any] = {
        "schema": BASELINE_MANIFEST_SCHEMA,
        "companion": {"path": "scriptsFORhuman/v20_R1/" + B0_JSON_NAME, "sha256": B0_JSON_SHA256, "schema": B0_COMPANION_SCHEMA},
        "csv": {"path": "scriptsFORhuman/v20_R1/" + B0_CSV_NAME, "sha256": B0_CSV_SHA256},
        "checkpoint": {"path": CHECKPOINT_PATH, "sha256": sha256_file(checkpoint), "config_path": CHECKPOINT_CONFIG_PATH, "config_sha256": sha256_file(config), "load_mode": "policy_only", "auto_load_latest": False},
        "source_files": source_rows,
        "pooled48_frozen": payload["pooled48_frozen"],
        "taskspace_trace_diagnostic": payload["taskspace_trace_diagnostic"],
        "usage_contract": payload["usage_contract"],
        "no_learning": {"seeds": [0, 1, 2], "num_envs": 16, "send_curriculum": False, "economics": False, "arm_tie": False, "telemetry": True},
    }
    if output_dir is not None:
        write_json_no_overwrite(output_dir / "B0_G2_step2000_pooled48.json", manifest)
    return manifest


def build_eval_commands(
    *,
    repo_root: Path,
    output_root: Path,
    gpus: Sequence[int] = (0, 1, 2),
) -> list[dict[str, Any]]:
    root = repo_root.resolve()
    if tuple(gpus) != (0, 1, 2):
        raise R1Error("B0 no-learning commands require legal GPUs 0,1,2 exactly")
    expected_root = root / "logs_eval/base_v20_R1/baseline"
    if output_root.resolve() != expected_root:
        raise R1Error(
            "B0 output root must be the canonical logs_eval/base_v20_R1/baseline path"
        )
    commands = []
    for seed, gpu in zip((0, 1, 2), gpus):
        gpu = validate_gpu(gpu)
        output_dir = expected_root / ("seed" + str(seed))
        command = [
            sys.executable,
            "-m",
            "gr00t.rl.eval_agent_trl",
            "--device",
            "cuda:" + str(gpu),
            "checkpoint=" + CHECKPOINT_PATH,
            "seed=" + str(seed),
            "num_envs=16",
            "env.config.a2_v20_R1_send_curriculum_enabled=false",
            "env.config.a2_v20_traversal_economics_enabled=false",
            "env.config.a2_v20_arm_tie_enabled=false",
            "env.config.a2_v20_telemetry_enabled=true",
            "eval_output_dir=" + str(output_dir),
        ]
        env = device_env(gpu)
        if "CUDA_VISIBLE_DEVICES" in env:
            raise R1Error("non-render baseline must not set CUDA_VISIBLE_DEVICES")
        commands.append(
            {
                "seed": seed,
                "gpu": gpu,
                "num_envs": 16,
                "output_dir": str(output_dir),
                "env": env,
                "command": command,
            }
        )
    return commands


def admit_baseline_records(
    *,
    repo_root: Path,
    record_paths: Sequence[Path],
    output_path: Path | None = None,
) -> dict[str, Any]:
    root = repo_root.resolve()
    if len(record_paths) != 3:
        raise R1Error("B0 admission requires exactly three seed record artifacts")
    endpoint_path = Path(__file__).resolve().parent / "a2_piper_v20_R1_endpoint_report.py"
    import importlib.util

    spec = importlib.util.spec_from_file_location("_r1_endpoint_baseline", endpoint_path)
    if spec is None or spec.loader is None:
        raise R1Error("cannot load strict endpoint adjudicator")
    endpoint = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(endpoint)
    rows = []
    for seed, path in enumerate(record_paths):
        target = Path(path).resolve()
        if not target.is_file() or root not in target.parents:
            raise R1Error("B0 record path must be an existing repository artifact")
        seed_rows = endpoint.load_typed_records(target)
        if len(seed_rows) != 16:
            raise R1Error("each B0 seed artifact must contain exactly 16 records")
        if any(row["provenance"]["seed"] != seed for row in seed_rows):
            raise R1Error("B0 record seed provenance mismatch")
        rows.extend(seed_rows)
    aggregate = endpoint.aggregate_records(rows, topology="pooled48")
    result = {
        "schema": "a2_piper_v20_R1_B0_runtime_admission_v1",
        "status": RUNTIME_SEMANTIC_PASS,
        "plan_id": PLAN_ID,
        "checkpoint_sha256": CHECKPOINT_SHA256,
        "records": {"count": len(rows), "seeds": [0, 1, 2]},
        "aggregate": aggregate,
        "commands": build_eval_commands(
            repo_root=root,
            output_root=root / "logs_eval/base_v20_R1/baseline",
        ),
        "no_learning": True,
    }
    if output_path is not None:
        write_json_no_overwrite(output_path, result)
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("sources", nargs="*", type=Path)
    return parser


if __name__ == "__main__":
    args = _parser().parse_args()
    build_baseline_manifest(repo_root=args.repo_root, source_artifacts=args.sources or None, output_dir=args.output_dir)
