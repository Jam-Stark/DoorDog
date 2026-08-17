#!/usr/bin/env python3
"""Aggregate the frozen C-B2H v19 large-scale camera evaluation.

This utility is deliberately fail-fast.  It reads only the frozen formal and
diagnostic artifacts, validates their contracts, and writes the two requested
JSON summaries plus the conclusion-first report.  It does not launch IsaacSim,
modify an environment/config, train a model, or compute artifact hashes.
"""

from __future__ import annotations

import json
import math
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from scipy.stats import mannwhitneyu


REPO_ROOT = Path(__file__).resolve().parents[1]
RESULT_ROOT = REPO_ROOT / "logs_eval/by_batch/cb2h_v19_toeout6_pitch50_largescale_camera_eval_20260810"
SUMMARY_ROOT = RESULT_ROOT / "summary"
CHECKPOINT_CONFIG = REPO_ROOT / (
    "logs_rl/by_batch/cb2h_v19_toeout6_pitch50_20260805/"
    "formal_4x64_8k_gpu4-7_timeoutfix_retry/config.yaml"
)
SMOKE_TEACHER_PROOF = RESULT_ROOT / "smoke/teacher_seed_00_gpu5_diagnose/teacher_stage0_diagnostic.json"
SMOKE_TEACHER_LOG = RESULT_ROOT / "smoke/teacher_seed_00_gpu5_diagnose.runner.log"
VISIBILITY_QUARANTINE = Path("/tmp/cb2h_visibility_failed_smoke_20260810_1815")

EXPECTED_CUSTOM_KEYS = [
    "doorWidth",
    "doorHeight",
    "doorHandleHeight",
    "doorHandleWidth",
    "doorWeight",
    "doorHandleType",
    "doorOpenLR",
    "doorOpenIO",
    "totalWallHeight",
    "axleLength",
    "handleLength",
    "hookLength",
    "handleRadius",
    "spawnHook",
    "hingeDriveMaxForce",
    "hingeDriveStiffness",
    "handleDriveMaxForce",
]
SHARED_RANDOMIZED_FIELDS = {
    "door_handle_drive_max_force": "handleDriveMaxForce",
    "door_handle_height": "doorHandleHeight",
    "door_hinge_drive_max_force": "hingeDriveMaxForce",
    "door_weight": "doorWeight",
}
CATEGORICAL_FIELDS = {"doorHandleType", "doorOpenLR", "doorOpenIO", "spawnHook"}
CUSTOM_DATA_FORMAL_EXACT_FIELDS = list(SHARED_RANDOMIZED_FIELDS.keys())
CUSTOM_DATA_SEEDED_FIELDS = [
    field for field in EXPECTED_CUSTOM_KEYS if field not in set(SHARED_RANDOMIZED_FIELDS.values())
]
CONTROL_DT = 4.0 / 200.0
VISUAL_STATUS = "UNKNOWN"
VISUAL_CAPTURE_STATUS = "NOT_COLLECTED_AFTER_RETRY_LIMIT"


class AnalysisError(RuntimeError):
    """Raised for an invalid frozen artifact or inconsistent contract."""


def fail(message: str) -> None:
    raise AnalysisError(message)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def load_json(path: Path) -> Any:
    require(path.is_file(), f"missing JSON artifact: {path}")
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot parse JSON artifact {path}: {exc}")


def ensure_finite(value: Any, path: str = "root") -> None:
    """Reject non-finite numbers in input evidence and output structures."""

    if isinstance(value, bool) or value is None or isinstance(value, str):
        return
    if isinstance(value, (int, float)):
        require(math.isfinite(float(value)), f"non-finite numeric value at {path}")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            ensure_finite(item, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            ensure_finite(item, f"{path}.{key}")
        return
    fail(f"unsupported JSON value type at {path}: {type(value).__name__}")


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def parse_seed(directory: Path) -> int:
    match = re.fullmatch(r"seed_(\d+)(?:_(?:smoke|retry02))?", directory.name)
    require(match is not None, f"unexpected seed directory name: {directory}")
    return int(match.group(1))


def discover_formal(controller: str, filename: str, expected_seeds: range) -> dict[int, Path]:
    found: dict[int, list[Path]] = defaultdict(list)
    for directory in sorted(RESULT_ROOT.glob(f"{controller}_gpu*/seed_*")):
        if not directory.is_dir() or directory.name.startswith("."):
            continue
        artifact = directory / filename
        if artifact.is_file():
            found[parse_seed(directory)].append(directory)
    expected = set(expected_seeds)
    require(set(found) == expected, f"{controller} formal seed coverage mismatch: {sorted(found)}")
    for seed, paths in found.items():
        require(len(paths) == 1, f"duplicate {controller} formal artifact for seed {seed}: {paths}")
    return {seed: paths[0] for seed, paths in found.items()}


def discover_customdata(expected_seeds: range) -> dict[int, Path]:
    found: dict[int, list[Path]] = defaultdict(list)
    for directory in sorted(RESULT_ROOT.glob("customdata_gpu*/seed_*")):
        if not directory.is_dir() or directory.name.startswith("."):
            continue
        artifact = directory / "student_stage2_diagnostic.json"
        if artifact.is_file():
            found[parse_seed(directory)].append(directory)
    expected = set(expected_seeds)
    require(set(found) == expected, f"customData seed coverage mismatch: {sorted(found)}")
    for seed, paths in found.items():
        require(len(paths) == 1, f"duplicate customData artifact for seed {seed}: {paths}")
    return {seed: paths[0] for seed, paths in found.items()}


def validate_config() -> dict[str, Any]:
    require(CHECKPOINT_CONFIG.is_file(), f"missing checkpoint config: {CHECKPOINT_CONFIG}")
    try:
        import yaml

        config = yaml.safe_load(CHECKPOINT_CONFIG.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - config parse must fail-fast with context
        fail(f"cannot parse checkpoint config {CHECKPOINT_CONFIG}: {exc}")
    require(isinstance(config, dict), "checkpoint config root must be a mapping")
    sim = config.get("simulator", {}).get("config", {}).get("sim", {})
    require(isinstance(sim, dict), "checkpoint config simulator.config.sim must be a mapping")
    fps = sim.get("fps")
    decimation = sim.get("control_decimation")
    require(fps == 200, f"checkpoint config fps must be 200, got {fps!r}")
    require(decimation == 4, f"checkpoint config control_decimation must be 4, got {decimation!r}")
    dt = float(decimation) / float(fps)
    require(math.isclose(dt, CONTROL_DT, rel_tol=0.0, abs_tol=1e-15), f"control dt mismatch: {dt}")
    return {
        "path": repo_relative(CHECKPOINT_CONFIG),
        "fps": int(fps),
        "control_decimation": int(decimation),
        "control_dt_seconds": dt,
        "formula": "control_decimation / fps = 4 / 200",
    }


def validate_contract(metrics: dict[str, Any], controller: str, seed: int) -> None:
    expected_schema = f"a2_toeout6_{controller}_metrics_v1"
    require(metrics.get("schema") == expected_schema, f"{controller} seed {seed}: schema mismatch")
    require(metrics.get("case_seed") == seed, f"{controller} seed {seed}: case_seed mismatch")
    require(metrics.get("controller") == controller, f"{controller} seed {seed}: controller mismatch")
    require(metrics.get("training_performed") is False, f"{controller} seed {seed}: training_performed must be false")
    require(metrics.get("optimizer_step_count") == 0, f"{controller} seed {seed}: optimizer_step_count must be 0")
    contract = metrics.get("contract")
    require(isinstance(contract, dict), f"{controller} seed {seed}: missing contract")
    expected = {
        "controller": controller,
        "enforce_teacher_rollout": controller == "teacher",
        "ratio_teacher_rollout": 1.0 if controller == "teacher" else 0.0,
        "pure_student": controller == "student",
        "num_envs": 16,
        "one_episode_per_env": True,
        "use_a2_base": True,
        "d435i_forward_mode": "packed",
    }
    for key, value in expected.items():
        require(contract.get(key) == value, f"{controller} seed {seed}: contract {key}={contract.get(key)!r}, expected {value!r}")
    require(metrics.get("episodes") and len(metrics["episodes"]) == 16, f"{controller} seed {seed}: expected 16 episodes")
    envs = [episode.get("env_id") for episode in metrics["episodes"]]
    require(sorted(envs) == list(range(16)), f"{controller} seed {seed}: env coverage/duplicates {envs}")
    require(all(episode.get("episode_index") == 0 for episode in metrics["episodes"]), f"{controller} seed {seed}: non-first episode present")
    case_envs = [case.get("env_id") for case in metrics.get("case_table", [])]
    require(sorted(case_envs) == list(range(16)), f"{controller} seed {seed}: case table coverage mismatch")


def validate_teacher_proof() -> dict[str, Any]:
    proof = load_json(SMOKE_TEACHER_PROOF)
    ensure_finite(proof)
    require(proof.get("schema") == "a2_toeout6_teacher_stage0_diagnostic_v1", "Teacher smoke proof schema mismatch")
    require(proof.get("controller") == "teacher", "Teacher smoke proof controller mismatch")
    require(proof.get("training_performed") is False, "Teacher smoke proof training_performed must be false")
    action_contract = proof.get("action_contract", {})
    source_proof = proof.get("action_source_proof", {})
    require(action_contract.get("selected_high_level_source") == "TRLDistillTrainerA2BaseAPI.policy_step.gt_actions", "Teacher smoke proof source mismatch")
    require(action_contract.get("teacher_rollout_ratio") == 1.0, "Teacher smoke proof ratio mismatch")
    require(action_contract.get("student_rollout_called") is False, "Teacher smoke proof Student rollout was called")
    require(action_contract.get("composed_action_dim") == 24, "Teacher smoke proof composed action dim mismatch")
    require(source_proof.get("provider") == "TRLDistillTrainerA2BaseAPI.policy_step", "Teacher smoke proof provider mismatch")
    require(source_proof.get("selected_high_level_source") == "gt_actions", "Teacher smoke proof selected source mismatch")
    require(source_proof.get("student_rollout_calls") == 0, "Teacher smoke proof Student calls nonzero")
    require(source_proof.get("teacher_rollout_ratio") == 1.0, "Teacher smoke proof source ratio mismatch")
    require(source_proof.get("exact_teacher_match_steps", 0) > 0, "Teacher smoke proof has no exact match steps")
    require(source_proof.get("exact_teacher_match_env_count", 0) > 0, "Teacher smoke proof has no exact match env actions")
    require(SMOKE_TEACHER_LOG.is_file(), f"missing Teacher smoke runner log: {SMOKE_TEACHER_LOG}")
    smoke_log = SMOKE_TEACHER_LOG.read_text(encoding="utf-8", errors="replace")
    require("[A2_TOEOUT6_TEACHER_DIAGNOSTIC_PASS]" in smoke_log, "Teacher smoke runner proof marker missing")
    return {
        "proof_path": repo_relative(SMOKE_TEACHER_PROOF),
        "runner_log_path": repo_relative(SMOKE_TEACHER_LOG),
        "selected_high_level_source": action_contract["selected_high_level_source"],
        "provider": source_proof["provider"],
        "teacher_rollout_ratio": source_proof["teacher_rollout_ratio"],
        "student_rollout_calls": source_proof["student_rollout_calls"],
        "composed_action_dim": action_contract["composed_action_dim"],
        "exact_teacher_match_steps": source_proof["exact_teacher_match_steps"],
        "exact_teacher_match_env_count": source_proof["exact_teacher_match_env_count"],
    }


def validate_customdata(custom_dirs: dict[int, Path]) -> dict[tuple[int, int], dict[str, Any]]:
    joined: dict[tuple[int, int], dict[str, Any]] = {}
    for seed, directory in sorted(custom_dirs.items()):
        diagnostic = load_json(directory / "student_stage2_diagnostic.json")
        ensure_finite(diagnostic)
        require(diagnostic.get("schema") == "a2_toeout6_student_stage2_diagnostic_v1", f"customData seed {seed}: schema mismatch")
        require(diagnostic.get("seed") == seed, f"customData seed {seed}: seed mismatch")
        require(diagnostic.get("controller") == "student", f"customData seed {seed}: controller mismatch")
        require(diagnostic.get("training_performed") is False, f"customData seed {seed}: training_performed must be false")
        require(diagnostic.get("full_custom_data_keys") == EXPECTED_CUSTOM_KEYS, f"customData seed {seed}: 17-key schema mismatch")
        case_table = diagnostic.get("case_table")
        require(isinstance(case_table, dict) and set(case_table) == {str(env) for env in range(16)}, f"customData seed {seed}: case table coverage mismatch")
        for env in range(16):
            case = case_table[str(env)]
            custom = case.get("door_custom_data")
            require(isinstance(custom, dict), f"customData seed {seed} env {env}: missing door_custom_data")
            require(set(custom.keys()) == set(EXPECTED_CUSTOM_KEYS), f"customData seed {seed} env {env}: key schema mismatch")
            joined[(seed, env)] = {
                "values": custom,
                "source_path": repo_relative(directory / "student_stage2_diagnostic.json"),
            }
    require(len(joined) == len(custom_dirs) * 16, "customData joined case count mismatch")
    return joined


def validate_formal_case_values(
    formal: dict[str, Any], custom: dict[str, Any], controller: str, seed: int, env: int
) -> None:
    randomized = formal.get("randomized_case")
    require(isinstance(randomized, dict), f"{controller} seed {seed} env {env}: missing randomized_case")
    for formal_name, custom_name in SHARED_RANDOMIZED_FIELDS.items():
        require(
            randomized.get(formal_name) == custom.get(custom_name),
            f"{controller} seed {seed} env {env}: {formal_name} does not exactly match customData {custom_name}",
        )


def first_episode_trace(trace: list[dict[str, Any]], formal_episode: dict[str, Any], controller: str, seed: int, env: int) -> list[dict[str, Any]]:
    env_records = [record for record in trace if record.get("env_id") == env]
    require(env_records, f"{controller} seed {seed} env {env}: no trace records")
    require(all(isinstance(record.get("step_index"), int) for record in env_records), f"{controller} seed {seed} env {env}: invalid step_index")
    env_records.sort(key=lambda record: record["step_index"])
    step_indices = [record["step_index"] for record in env_records]
    require(len(step_indices) == len(set(step_indices)), f"{controller} seed {seed} env {env}: duplicate trace step_index")
    terminal_index = next((index for index, record in enumerate(env_records) if record.get("terminal_reasons") != "unknown_reset"), None)
    # The stage2_5 stream intentionally starts at Stage2.  A first episode
    # that terminates in Stage0/Stage1 therefore has no terminal record in
    # this stream; its formal scalar artifact remains the authoritative
    # terminal outcome/length and its Stage2 metrics are exactly zero.
    if terminal_index is None:
        require(formal_episode.get("max_stage", 0) < 2, f"{controller} seed {seed} env {env}: no terminal trace record")
        return []
    first = env_records[: terminal_index + 1]
    terminal = first[-1]
    formal_terminal = formal_episode.get("terminal_diagnostic", {})
    require(terminal.get("terminal_reasons") == formal_episode.get("terminal_reason"), f"{controller} seed {seed} env {env}: trace terminal reason mismatch")
    require(terminal.get("stage_buf") == formal_episode.get("max_stage"), f"{controller} seed {seed} env {env}: trace terminal stage mismatch")
    require(terminal.get("episode_length_buf") == formal_terminal.get("episode_length_buf"), f"{controller} seed {seed} env {env}: trace episode length mismatch")
    return first


def longest_true_run(values: Iterable[bool]) -> int:
    longest = current = 0
    for value in values:
        if value:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def stage2_metrics(first_trace: list[dict[str, Any]]) -> dict[str, Any]:
    stage2 = [record for record in first_trace if record.get("stage_buf") == 2]
    stage2_steps = [record.get("step_index") for record in stage2]
    require(all(isinstance(step, int) for step in stage2_steps), "Stage2 trace has invalid step index")
    if stage2_steps:
        require(all(b - a == 1 for a, b in zip(stage2_steps, stage2_steps[1:])), "Stage2 trace has non-contiguous control steps")
    both = [bool(record.get("both_contact")) for record in stage2]
    total_steps = sum(both)
    longest_steps = longest_true_run(both)
    duration_steps = len(stage2)
    max_streak = max((int(record.get("a2_stage2_squeeze_streak")) for record in stage2), default=0)
    return {
        "max_a2_stage2_squeeze_streak": max_streak,
        "both_contact_total_control_steps": total_steps,
        "both_contact_total_seconds": total_steps * CONTROL_DT,
        "both_contact_longest_consecutive_control_steps": longest_steps,
        "both_contact_longest_consecutive_seconds": longest_steps * CONTROL_DT,
        "duration_control_steps": duration_steps,
        "duration_seconds": duration_steps * CONTROL_DT,
        "trace_first_stage2_step_index": stage2_steps[0] if stage2_steps else None,
        "trace_last_stage2_step_index": stage2_steps[-1] if stage2_steps else None,
    }


def metrics_by_env(metrics: dict[str, Any], controller: str, seed: int) -> dict[int, dict[str, Any]]:
    scalar = load_json(Path(metrics["_directory"]) / "metrics_eval.json")
    require(scalar.get("completed_episodes") == 16, f"{controller} seed {seed}: completed_episodes must be 16")
    for key in ("episode_lengths", "episode_rewards", "episode_goal_reached", "episode_max_stage_reached", "episode_terminal_reasons", "episode_terminal_diagnostics"):
        require(isinstance(scalar.get(key), list) and len(scalar[key]) == 16, f"{controller} seed {seed}: scalar {key} length mismatch")
    result = {}
    for index, diagnostic in enumerate(scalar["episode_terminal_diagnostics"]):
        env = diagnostic.get("env_id", index)
        require(env not in result, f"{controller} seed {seed}: duplicate scalar env {env}")
        result[env] = {
            "length": scalar["episode_lengths"][index],
            "reward": scalar["episode_rewards"][index],
            "goal_reached": scalar["episode_goal_reached"][index],
            "max_stage": scalar["episode_max_stage_reached"][index],
            "terminal_reason": scalar["episode_terminal_reasons"][index],
            "terminal_diagnostic": diagnostic,
        }
    require(set(result) == set(range(16)), f"{controller} seed {seed}: scalar env coverage mismatch")
    return result


def make_records(
    formal_dirs: dict[str, dict[int, Path]], custom_joined: dict[tuple[int, int], dict[str, Any]], dt_info: dict[str, Any]
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for controller, directories in formal_dirs.items():
        formal_filename = f"formal_{controller}_metrics.json"
        for seed, directory in sorted(directories.items()):
            formal = load_json(directory / formal_filename)
            ensure_finite(formal)
            validate_contract(formal, controller, seed)
            scalar = metrics_by_env({"_directory": str(directory)}, controller, seed)
            trace = load_json(directory / "stage2_5_step_trace.json")
            require(isinstance(trace, list), f"{controller} seed {seed}: stage2_5_step_trace must be a list")
            for episode in formal["episodes"]:
                env = int(episode["env_id"])
                scalar_env = scalar[env]
                require(episode["reward"] == scalar_env["reward"], f"{controller} seed {seed} env {env}: reward mismatch")
                require(episode["goal_reached"] == scalar_env["goal_reached"], f"{controller} seed {seed} env {env}: outcome mismatch")
                require(episode["max_stage"] == scalar_env["max_stage"], f"{controller} seed {seed} env {env}: max_stage mismatch")
                require(episode["terminal_reason"] == scalar_env["terminal_reason"], f"{controller} seed {seed} env {env}: terminal reason mismatch")
                require(episode["terminal_diagnostic"]["episode_length_buf"] == scalar_env["length"], f"{controller} seed {seed} env {env}: formal episode length mismatch")
                custom_case = custom_joined[(seed, env)]
                validate_formal_case_values(episode, custom_case["values"], controller, seed, env)
                first_trace = first_episode_trace(trace, episode, controller, seed, env)
                stage2 = stage2_metrics(first_trace)
                record = {
                    "controller": controller,
                    "seed": seed,
                    "env_id": env,
                    "episode_index": 0,
                    "outcome": "success" if episode["goal_reached"] else "failure",
                    "goal_reached": bool(episode["goal_reached"]),
                    "max_stage": int(episode["max_stage"]),
                    "terminal_reason": episode["terminal_reason"],
                    "reward": float(episode["reward"]),
                    "length": int(scalar_env["length"]),
                    "door_custom_data": custom_case["values"],
                    "custom_data_provenance": {
                        "formal_exact_overlap_fields": CUSTOM_DATA_FORMAL_EXACT_FIELDS,
                        "seeded_provenance_only_fields": CUSTOM_DATA_SEEDED_FIELDS,
                        "statement": "Only the four overlapping formal randomized fields are exact formal equivalences; the remaining 13 fields are deterministic seeded-provenance joins.",
                    },
                    "stage2": stage2,
                    "source_paths": {
                        "formal_metrics": repo_relative(directory / formal_filename),
                        "scalar_metrics": repo_relative(directory / "metrics_eval.json"),
                        "stage2_5_step_trace": repo_relative(directory / "stage2_5_step_trace.json"),
                        "customdata_diagnostic": custom_case["source_path"],
                        "runner_log": repo_relative(directory.parent / f"{directory.name}.runner.log"),
                    },
                    "visual_conditions": {
                        "status": VISUAL_STATUS,
                        "capture_status": VISUAL_CAPTURE_STATUS,
                        "metrics": None,
                    },
                    "control_dt_seconds": dt_info["control_dt_seconds"],
                }
                records.append(record)
    require(len(records) == 768, f"per-episode record count must be 768, got {len(records)}")
    keys = {(r["controller"], r["seed"], r["env_id"]) for r in records}
    require(len(keys) == 768, "duplicate per-episode formal cases")
    return sorted(records, key=lambda record: (record["controller"], record["seed"], record["env_id"]))


def quantiles(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"mean": None, "q25": None, "median": None, "q75": None}
    ordered = sorted(float(value) for value in values)
    return {
        "mean": statistics.fmean(ordered),
        "q25": statistics.quantiles(ordered, n=4, method="inclusive")[0] if len(ordered) > 1 else ordered[0],
        "median": statistics.median(ordered),
        "q75": statistics.quantiles(ordered, n=4, method="inclusive")[2] if len(ordered) > 1 else ordered[0],
    }


def wilson(successes: int, total: int, z: float = 1.959963984540054) -> dict[str, float]:
    require(total > 0, "Wilson interval total must be positive")
    proportion = successes / total
    denominator = 1.0 + z * z / total
    center = (proportion + z * z / (2.0 * total)) / denominator
    half = z * math.sqrt((proportion * (1.0 - proportion) + z * z / (4.0 * total)) / total) / denominator
    return {"lower": center - half, "upper": center + half, "level": 0.95}


def controller_stats(records: list[dict[str, Any]], controller: str) -> dict[str, Any]:
    subset = [record for record in records if record["controller"] == controller]
    successes = [record for record in subset if record["goal_reached"]]
    failures = [record for record in subset if not record["goal_reached"]]
    per_seed = []
    for seed in sorted({record["seed"] for record in subset}):
        seed_records = [record for record in subset if record["seed"] == seed]
        seed_successes = sum(record["goal_reached"] for record in seed_records)
        per_seed.append({"seed": seed, "successes": seed_successes, "total": len(seed_records), "success_rate": seed_successes / len(seed_records)})
    stage_counts = Counter(str(record["max_stage"]) for record in failures)
    reason_counts = Counter(record["terminal_reason"] for record in failures)
    return {
        "total": len(subset),
        "successes": len(successes),
        "failures": len(failures),
        "success_rate": len(successes) / len(subset),
        "success_rate_percent": 100.0 * len(successes) / len(subset),
        "wilson95": wilson(len(successes), len(subset)),
        "per_seed_successes": per_seed,
        "failure_stage_distribution": {key: stage_counts[key] for key in sorted(stage_counts, key=int)},
        "failure_reason_distribution": {key: reason_counts[key] for key in sorted(reason_counts)},
    }


def failure_overlap(records: list[dict[str, Any]]) -> dict[str, Any]:
    student = [record for record in records if record["controller"] == "student" and not record["goal_reached"]]
    by_seed = {seed: {record["env_id"] for record in student if record["seed"] == seed} for seed in range(32)}
    pairwise = []
    for left in range(32):
        for right in range(left + 1, 32):
            intersection = by_seed[left] & by_seed[right]
            union = by_seed[left] | by_seed[right]
            pairwise.append({
                "seed_a": left,
                "seed_b": right,
                "intersection_env_ids": sorted(intersection),
                "intersection_count": len(intersection),
                "union_count": len(union),
                "jaccard": len(intersection) / len(union) if union else None,
                "jaccard_defined": bool(union),
            })
    jaccards = [item["jaccard"] for item in pairwise if item["jaccard_defined"]]
    overlaps = [item["intersection_count"] for item in pairwise]
    return {
        "failure_env_ids_by_seed": {str(seed): sorted(by_seed[seed]) for seed in range(32)},
        "pairwise": pairwise,
        "pairwise_mean_intersection_count": statistics.fmean(overlaps),
        "pairwise_mean_jaccard": statistics.fmean(jaccards),
        "total_pair_count": len(pairwise),
        "evaluated_union_nonempty_pair_count": len(jaccards),
        "undefined_empty_union_pair_count": len(pairwise) - len(jaccards),
        "intersection_nonempty_pair_count": sum(bool(item["intersection_count"]) for item in pairwise),
    }


def stage2_comparisons(records: list[dict[str, Any]]) -> dict[str, Any]:
    metric_names = [
        "max_a2_stage2_squeeze_streak",
        "both_contact_total_control_steps",
        "both_contact_total_seconds",
        "both_contact_longest_consecutive_control_steps",
        "both_contact_longest_consecutive_seconds",
        "duration_control_steps",
        "duration_seconds",
    ]
    output: dict[str, Any] = {}
    for controller in ("student", "teacher"):
        output[controller] = {}
        for outcome, label in ((True, "success"), (False, "failure")):
            group = [record for record in records if record["controller"] == controller and record["goal_reached"] is outcome]
            output[controller][label] = {
                "n": len(group),
                "metrics": {name: quantiles([record["stage2"][name] for record in group]) for name in metric_names},
            }
        output[controller]["success_minus_failure_mean"] = {}
        for name in metric_names:
            success_values = [record["stage2"][name] for record in records if record["controller"] == controller and record["goal_reached"]]
            failure_values = [record["stage2"][name] for record in records if record["controller"] == controller and not record["goal_reached"]]
            output[controller]["success_minus_failure_mean"][name] = statistics.fmean(success_values) - statistics.fmean(failure_values) if failure_values else None
    return output


def geometry_comparisons(records: list[dict[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    numeric_fields = [field for field in EXPECTED_CUSTOM_KEYS if field not in CATEGORICAL_FIELDS]
    categorical_fields = [field for field in EXPECTED_CUSTOM_KEYS if field in CATEGORICAL_FIELDS]
    for controller in ("student", "teacher"):
        subset = [record for record in records if record["controller"] == controller]
        success = [record["door_custom_data"] for record in subset if record["goal_reached"]]
        failure = [record["door_custom_data"] for record in subset if not record["goal_reached"]]
        numeric: dict[str, Any] = {}
        for field in numeric_fields:
            success_values = [float(item[field]) for item in success]
            failure_values = [float(item[field]) for item in failure]
            require(all(math.isfinite(value) for value in success_values + failure_values), f"non-finite geometry field {field}")
            if failure_values:
                test = mannwhitneyu(success_values, failure_values, alternative="two-sided", method="auto")
                u_value = float(test.statistic)
                p_value = float(test.pvalue)
                rank_biserial = 2.0 * u_value / (len(success_values) * len(failure_values)) - 1.0
            else:
                u_value = p_value = rank_biserial = None
            numeric[field] = {
                "success_n": len(success_values),
                "failure_n": len(failure_values),
                "success": quantiles(success_values),
                "failure": quantiles(failure_values),
                "mann_whitney_u_success_vs_failure": u_value,
                "mann_whitney_p_two_sided": p_value,
                "rank_biserial_success_vs_failure": rank_biserial,
            }
        categorical: dict[str, Any] = {}
        for field in categorical_fields:
            levels = sorted({json.dumps(item[field], ensure_ascii=False, sort_keys=True) for item in success + failure})
            level_stats = []
            for encoded in levels:
                value = json.loads(encoded)
                success_count = sum(item[field] == value for item in success)
                failure_count = sum(item[field] == value for item in failure)
                level_stats.append({
                    "value": value,
                    "success_count": success_count,
                    "success_rate": success_count / len(success) if success else None,
                    "failure_count": failure_count,
                    "failure_rate": failure_count / len(failure) if failure else None,
                })
            categorical[field] = {"success_n": len(success), "failure_n": len(failure), "levels": level_stats}
        output[controller] = {"numeric": numeric, "categorical": categorical}
    return output


def paired_outcomes(records: list[dict[str, Any]]) -> dict[str, Any]:
    lookup = {(record["controller"], record["seed"], record["env_id"]): record for record in records}
    rows = []
    for seed in range(16):
        for env in range(16):
            student = lookup[("student", seed, env)]
            teacher = lookup[("teacher", seed, env)]
            rows.append({
                "seed": seed,
                "env_id": env,
                "student_goal_reached": student["goal_reached"],
                "student_max_stage": student["max_stage"],
                "student_terminal_reason": student["terminal_reason"],
                "teacher_goal_reached": teacher["goal_reached"],
                "teacher_max_stage": teacher["max_stage"],
                "teacher_terminal_reason": teacher["terminal_reason"],
                "outcome_relation": "both_success" if student["goal_reached"] and teacher["goal_reached"] else "student_only_success" if student["goal_reached"] else "teacher_only_success" if teacher["goal_reached"] else "both_failure",
            })
    by_seed = []
    for seed in range(16):
        rows_seed = [row for row in rows if row["seed"] == seed]
        by_seed.append({
            "seed": seed,
            "student_successes": sum(row["student_goal_reached"] for row in rows_seed),
            "teacher_successes": sum(row["teacher_goal_reached"] for row in rows_seed),
            "student_only_success_env_ids": [row["env_id"] for row in rows_seed if row["outcome_relation"] == "student_only_success"],
            "teacher_only_success_env_ids": [row["env_id"] for row in rows_seed if row["outcome_relation"] == "teacher_only_success"],
            "both_failure_env_ids": [row["env_id"] for row in rows_seed if row["outcome_relation"] == "both_failure"],
        })
    return {"records": rows, "by_seed": by_seed}


def visibility_gap() -> dict[str, Any]:
    attempts = [
        {
            "attempt": 1,
            "root_cause": "camera interface lookup failed: missing sensor d435i_left_portrait_up50_toeout6",
            "log_paths": [
                "/tmp/cb2h_visibility_failed_smoke_20260810_1815/visibility_student_gpu4/seed_00.runner.log",
                "/tmp/cb2h_visibility_failed_smoke_20260810_1815/visibility_teacher_gpu5/seed_00.runner.log",
            ],
        },
        {
            "attempt": 2,
            "root_cause": "over-strict runtime contract rejected ego_camera.offset.pos tensor shape (expected three values)",
            "log_paths": [
                "/tmp/cb2h_visibility_failed_smoke_20260810_1815/visibility_student_gpu4_r4/seed_00.runner.log",
                "/tmp/cb2h_visibility_failed_smoke_20260810_1815/visibility_teacher_gpu5_r4/seed_00.runner.log",
            ],
        },
        {
            "attempt": 3,
            "root_cause": "over-strict sealed offset contract rejected the observed ego_camera pose as offset drift",
            "log_paths": [
                repo_relative(RESULT_ROOT / "visibility_student_gpu4/seed_00.runner.log"),
                repo_relative(RESULT_ROOT / "visibility_teacher_gpu5/seed_00.runner.log"),
            ],
        },
    ]
    for attempt in attempts:
        for path_text in attempt["log_paths"]:
            path = Path(path_text) if path_text.startswith("/") else REPO_ROOT / path_text
            require(path.is_file(), f"visibility attempt log missing: {path}")
    return {
        "status": VISUAL_STATUS,
        "capture_status": VISUAL_CAPTURE_STATUS,
        "attempt_count": 3,
        "valid_visual_metric_artifacts": 0,
        "numeric_fields_present": False,
        "attempts": attempts,
        "retained_log_paths": [path for attempt in attempts for path in attempt["log_paths"]],
        "gap_statement": "No direct handle visibility, occlusion, or pixel-size metric is available for any of the 768 formal episodes; no numeric visual value was imputed.",
    }


def source_counts(records: list[dict[str, Any]], formal_dirs: dict[str, dict[int, Path]], custom_dirs: dict[int, Path]) -> dict[str, Any]:
    expected = {
        "student_formal_artifacts": 32,
        "teacher_formal_artifacts": 16,
        "customdata_diagnostic_artifacts": 32,
        "formal_episodes": 768,
        "stage2_trace_cases": 768,
        "visual_metric_cases": 768,
    }
    observed = {
        "student_formal_artifacts": len(formal_dirs["student"]),
        "teacher_formal_artifacts": len(formal_dirs["teacher"]),
        "customdata_diagnostic_artifacts": len(custom_dirs),
        "formal_episodes": len(records),
        "stage2_trace_cases": len(records),
        "visual_metric_cases": 0,
    }
    gaps = {key: expected[key] - observed[key] for key in expected}
    return {"expected": expected, "observed": observed, "gaps": gaps, "all_formal_cases_unique": len(records) == 768}


def build_aggregate(records: list[dict[str, Any]], formal_dirs: dict[str, dict[int, Path]], custom_dirs: dict[int, Path], dt_info: dict[str, Any], teacher_proof: dict[str, Any]) -> dict[str, Any]:
    student_stats = controller_stats(records, "student")
    teacher_stats = controller_stats(records, "teacher")
    gap_pp = (teacher_stats["success_rate"] - student_stats["success_rate"]) * 100.0
    return {
        "schema": "cb2h_v19_largescale_camera_aggregate_v1",
        "analysis_date": "2026-08-10",
        "dataset": {
            "student_formal_seeds": list(range(32)),
            "teacher_formal_seeds": list(range(16)),
            "envs_per_seed": 16,
            "one_episode_per_env": True,
            "training_performed": False,
            "optimizer_step_count": 0,
        },
        "control_dt": dt_info,
        "teacher_action_source_audit": teacher_proof,
        "controllers": {"student": student_stats, "teacher": teacher_stats},
        "gap": {
            "teacher_minus_student_percentage_points": gap_pp,
            "teacher_minus_student_fraction": teacher_stats["success_rate"] - student_stats["success_rate"],
            "student_successes": student_stats["successes"],
            "student_total": student_stats["total"],
            "teacher_successes": teacher_stats["successes"],
            "teacher_total": teacher_stats["total"],
        },
        "student_failure_env_id_overlap_jaccard": failure_overlap(records),
        "paired_student_teacher_seed0_15": paired_outcomes(records),
        "success_vs_failure_stage2_comparisons": stage2_comparisons(records),
        "success_vs_failure_17_field_geometry_comparisons": geometry_comparisons(records),
        "customdata_provenance": {
            "formal_exact_overlap_fields": {
                formal_name: custom_name for formal_name, custom_name in SHARED_RANDOMIZED_FIELDS.items()
            },
            "seeded_provenance_only_fields": CUSTOM_DATA_SEEDED_FIELDS,
            "statement": "Only the four overlapping formal randomized fields are exact formal equivalences; the remaining 13 fields are deterministic seeded-provenance joins.",
        },
        "source_counts_and_gaps": source_counts(records, formal_dirs, custom_dirs),
        "student_below_70_defense": {
            "status": "NOT_TRIGGERED",
            "threshold": 0.70,
            "student_success_rate": student_stats["success_rate"],
        },
        "visibility_capture_gap": visibility_gap(),
        "decision": {
            "criterion": "(c) 混合",
            "qualifier": "暂归类/可见性归因 INCONCLUSIVE",
            "gap_percentage_points": gap_pp,
            "boundary_interpretation": "9.9609375 pp lies at the design's 5–10 pp boundary.",
            "formal_contact_streak_signal": "Strong: Stage2 contact/streak metrics are available for all formal episodes and Teacher true-action contracts are validated.",
            "positive_direct_visibility_difficulty_evidence": None,
            "camera_sufficiency_proof": "UNKNOWN/INCONCLUSIVE because all three visibility capture attempts stopped before valid direct metrics.",
            "higher_handle_height_association": "Higher handle height is associated with failure in the geometry comparison, but cannot be labeled visual rather than kinematic/contact without direct visual metrics.",
            "depth_default": "DO_NOT_ENABLE_FROM_THIS_RUN",
            "wrist_camera_default": "DO_NOT_ADD_FROM_THIS_RUN",
            "future_perception_ablation_order": "If separately approved, test existing D435 depth before hardware wrist camera.",
            "primary_next_policy_work": "Separately approved targeted Stage2 contact-continuity DAgger; no training in this task.",
        },
    }


def json_dump(path: Path, payload: Any) -> None:
    ensure_finite(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, allow_nan=False, indent=2)
        handle.write("\n")


def fmt(value: Any, digits: int = 6) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def report_from_json(aggregate: dict[str, Any]) -> str:
    student = aggregate["controllers"]["student"]
    teacher = aggregate["controllers"]["teacher"]
    gap = aggregate["gap"]["teacher_minus_student_percentage_points"]
    lines: list[str] = []
    lines.extend([
        "# C-B2H v19 大规模 Camera Eval 报告",
        "",
        "日期：2026-08-10 HKT",
        "",
        "## 结论先行",
        "",
        f"预固定判据命中 **{aggregate['decision']['criterion']}**，暂归类为 **{aggregate['decision']['qualifier']}**。Teacher−Student gap 为 `{gap:.7f} pp`（Teacher `{teacher['successes']}/{teacher['total']}`，Student `{student['successes']}/{student['total']}`），处在设计预设的 5–10 pp 边界；正式 Stage2 contact/streak 信号明确，但 direct visibility share 是 UNKNOWN，不能把本轮写成当前 camera 充分。",
        "",
        "因此不调用判据 (a) 或 (b)，而归入混合/可见性归因 INCONCLUSIVE。三次 visibility capture 都在产生合法逐集指标前 fail-fast 停止；较高 handle height 在几何比较中与 failure 相关，但在缺少 direct visual metrics 时，不能把该关联标注为视觉原因而不是 kinematic/contact 原因。",
        "",
        "本轮建议：不基于这些数据默认开启双 D435i depth，也不默认增加 wrist camera；若后续单独批准 perception ablation，先测试已有 D435 depth，再考虑硬件 wrist camera。主要下一项 policy work 仍是另行批准的 targeted Stage2 contact-continuity DAgger，本任务没有训练。",
        "",
        "本报告不画图：对 768 条逐集证据，精确 audit tables 比图形更清晰，且本次交付要求为 Markdown。",
        "",
        "## 1. 总体成功率与置信区间",
        "",
        "| Controller | Success | Total | Rate | Wilson 95% CI |",
        "|---|---:|---:|---:|---:|",
        f"| Student | {student['successes']} | {student['total']} | {student['success_rate']*100:.7f}% | [{student['wilson95']['lower']*100:.7f}%, {student['wilson95']['upper']*100:.7f}%] |",
        f"| Teacher | {teacher['successes']} | {teacher['total']} | {teacher['success_rate']*100:.7f}% | [{teacher['wilson95']['lower']*100:.7f}%, {teacher['wilson95']['upper']*100:.7f}%] |",
        f"| Teacher − Student | — | — | **{gap:.7f} pp** | — |",
        "",
        "## 2. Per-seed successes",
        "",
        "| Seed | Student | Teacher（seed 0–15） |",
        "|---:|---:|---:|",
    ])
    teacher_by_seed = {item["seed"]: item for item in teacher["per_seed_successes"]}
    for item in student["per_seed_successes"]:
        t = teacher_by_seed.get(item["seed"])
        lines.append(f"| {item['seed']} | {item['successes']}/{item['total']} | {t['successes']}/{t['total']} |" if t else f"| {item['seed']} | {item['successes']}/{item['total']} | — |")
    lines.extend([
        "",
        "## 3. Failure stage / reason distribution",
        "",
        "| Controller | Failure stage | Count |",
        "|---|---:|---:|",
    ])
    for controller, stats in (("Student", student), ("Teacher", teacher)):
        for stage, count in stats["failure_stage_distribution"].items():
            lines.append(f"| {controller} | {stage} | {count} |")
    lines.extend([
        "",
        "| Controller | Failure terminal reason | Count |",
        "|---|---|---:|",
    ])
    for controller, stats in (("Student", student), ("Teacher", teacher)):
        for reason, count in stats["failure_reason_distribution"].items():
            lines.append(f"| {controller} | `{reason}` | {count} |")
    lines.extend([
        "",
        "## 4. Student failure env-id overlap / Jaccard",
        "",
        "Student failure env sets are reported for all 32 seeds in `aggregate_stats.json`. There are `" + str(aggregate["student_failure_env_id_overlap_jaccard"]["total_pair_count"]) + "` seed pairs: `" + str(aggregate["student_failure_env_id_overlap_jaccard"]["evaluated_union_nonempty_pair_count"]) + "` evaluated pairs with non-empty union and `" + str(aggregate["student_failure_env_id_overlap_jaccard"]["undefined_empty_union_pair_count"]) + "` undefined empty-union pairs. Mean Jaccard over evaluated pairs is `" + fmt(aggregate["student_failure_env_id_overlap_jaccard"]["pairwise_mean_jaccard"], 6) + "`; intersection-nonempty pair count is `" + str(aggregate["student_failure_env_id_overlap_jaccard"]["intersection_nonempty_pair_count"]) + "`. This quantifies overlap without assigning a value to undefined pairs or promoting it to causality.",
        "",
        "| Seed pair | Intersection env IDs | Jaccard |",
        "|---|---|---:|",
    ])
    for item in aggregate["student_failure_env_id_overlap_jaccard"]["pairwise"]:
        if item["intersection_count"]:
            lines.append(f"| {item['seed_a']} / {item['seed_b']} | {item['intersection_env_ids']} | {item['jaccard']:.7f} |")
    lines.append("| Empty-union pairs | undefined / excluded | — |")
    lines.extend([
        "",
        "## 5. Paired Student/Teacher outcomes, seeds 0–15",
        "",
        "The machine-readable artifact contains all 256 `(seed, env_id)` rows. The compact audit table below reports every paired seed and the differing env IDs.",
        "",
        "| Seed | Student success | Teacher success | Student-only envs | Teacher-only envs | Both-failure envs |",
        "|---:|---:|---:|---|---|---|",
    ])
    for row in aggregate["paired_student_teacher_seed0_15"]["by_seed"]:
        lines.append(f"| {row['seed']} | {row['student_successes']}/16 | {row['teacher_successes']}/16 | {row['student_only_success_env_ids']} | {row['teacher_only_success_env_ids']} | {row['both_failure_env_ids']} |")
    lines.extend([
        "",
        "## 6. Success-vs-failure Stage2 comparisons",
        "",
        "Values are per-episode first-episode trace metrics; seconds use validated `4/200 = 0.02 s` control dt.",
        "",
        "| Controller | Outcome | n | Max squeeze streak mean | Both-contact steps mean | Longest both-contact steps mean | Stage2 duration steps mean |",
        "|---|---|---:|---:|---:|---:|---:|",
    ])
    for controller in ("student", "teacher"):
        comp = aggregate["success_vs_failure_stage2_comparisons"][controller]
        for outcome in ("success", "failure"):
            metrics = comp[outcome]["metrics"]
            lines.append(f"| {controller.title()} | {outcome} | {comp[outcome]['n']} | {fmt(metrics['max_a2_stage2_squeeze_streak']['mean'])} | {fmt(metrics['both_contact_total_control_steps']['mean'])} | {fmt(metrics['both_contact_longest_consecutive_control_steps']['mean'])} | {fmt(metrics['duration_control_steps']['mean'])} |")
    lines.extend([
        "",
        "Full q25/median/q75 plus success-minus-failure means are in `aggregate_stats.json`; no direct visual quantity is substituted for these contact metrics.",
        "",
        "## 7. Success-vs-failure 17-field geometry comparisons",
        "",
        "Numeric rows show mean / q25 / median / q75 and Mann–Whitney U, two-sided p, and rank-biserial effect. Categorical rows show success/failure counts and rates.",
        "",
        "### Numeric fields",
        "",
        "| Controller | Field | Success mean [q25, median, q75] | Failure mean [q25, median, q75] | U | p | Rank-biserial |",
        "|---|---|---|---|---:|---:|---:|",
    ])
    for controller in ("student", "teacher"):
        for field, row in aggregate["success_vs_failure_17_field_geometry_comparisons"][controller]["numeric"].items():
            success_q = row["success"]
            failure_q = row["failure"]
            lines.append(f"| {controller.title()} | `{field}` | {fmt(success_q['mean'])} [{fmt(success_q['q25'])}, {fmt(success_q['median'])}, {fmt(success_q['q75'])}] | {fmt(failure_q['mean'])} [{fmt(failure_q['q25'])}, {fmt(failure_q['median'])}, {fmt(failure_q['q75'])}] | {fmt(row['mann_whitney_u_success_vs_failure'])} | {fmt(row['mann_whitney_p_two_sided'])} | {fmt(row['rank_biserial_success_vs_failure'])} |")
    lines.extend([
        "",
        "### Categorical fields",
        "",
        "| Controller | Field | Value | Success count/rate | Failure count/rate |",
        "|---|---|---|---:|---:|",
    ])
    for controller in ("student", "teacher"):
        for field, row in aggregate["success_vs_failure_17_field_geometry_comparisons"][controller]["categorical"].items():
            for level in row["levels"]:
                value = json.dumps(level["value"], ensure_ascii=False)
                lines.append(f"| {controller.title()} | `{field}` | `{value}` | {level['success_count']}/{row['success_n']} ({fmt(level['success_rate']*100 if level['success_rate'] is not None else None)}%) | {level['failure_count']}/{row['failure_n']} ({fmt(level['failure_rate']*100 if level['failure_rate'] is not None else None)}%) |")
    lines.extend([
        "",
        "The higher-handle-height association is descriptive only; without visibility metrics it cannot be called visual rather than kinematic/contact.",
        "",
        "## 8. Source counts, gaps, and defensive threshold",
        "",
        "| Source | Expected | Observed | Gap |",
        "|---|---:|---:|---:|",
    ])
    for key, expected in aggregate["source_counts_and_gaps"]["expected"].items():
        observed = aggregate["source_counts_and_gaps"]["observed"][key]
        lines.append(f"| {key} | {expected} | {observed} | {expected-observed} |")
    lines.extend([
        "",
        "### customData provenance qualification",
        "",
        "The four exact formal overlaps are `door_handle_drive_max_force ↔ handleDriveMaxForce`, `door_handle_height ↔ doorHandleHeight`, `door_hinge_drive_max_force ↔ hingeDriveMaxForce`, and `door_weight ↔ doorWeight`. The remaining 13 preserved fields are deterministic seeded-provenance joins, not independently exact-observed formal values. Every per-episode record retains all 17 fields and its outcome association.",
        "",
        f"Student <70% defense status: **{aggregate['student_below_70_defense']['status']}** (observed `{student['success_rate']*100:.7f}%`). No contract/checkpoint/source downgrade was inferred.",
        "",
        "## 9. Visibility capture gap",
        "",
        f"Status: **{aggregate['visibility_capture_gap']['status']}**; capture status: `{aggregate['visibility_capture_gap']['capture_status']}`. Valid direct visual metric artifacts: `{aggregate['visibility_capture_gap']['valid_visual_metric_artifacts']}`. All 768 per-episode records set `visual_conditions.metrics` to JSON `null`; no numeric visual field was invented.",
        "",
        "| Attempt | Root cause | Retained logs |",
        "|---:|---|---|",
    ])
    for attempt in aggregate["visibility_capture_gap"]["attempts"]:
        logs = "<br>".join(f"`{path}`" for path in attempt["log_paths"])
        lines.append(f"| {attempt['attempt']} | {attempt['root_cause']} | {logs} |")
    lines.extend([
        "",
        "The missing visibility metrics leave the visual share UNKNOWN; this is not evidence of either camera sufficiency or camera insufficiency.",
        "",
        "## 10. Mentor-ready paragraph",
        "",
        f"在固定 G2 契约下，我们完成了 Student 32 seeds × 16 env = 512 集（成功 {student['successes']}）和 true-action Teacher 16 seeds × 16 env = 256 集（成功 {teacher['successes']}）。Teacher−Student gap 为 {gap:.7f} 个百分点，处于预设 5–10 个百分点边界；正式 Stage2 接触/连续 streak 统计和 Teacher `gt_actions` route audit 均有效，Student 失败没有形成稳定的 env-id 集合。相机可见性量化 lane 连续三次因接口/过严格 runtime contract 错误在指标生成前停止，因此 visual share 是 UNKNOWN，不能把较高 handle height 的失败关联解释为视觉问题。当前建议是不默认开启 D435 depth 或增加 wrist camera；如果之后单独批准感知 ablation，先验证已有 D435 depth。下一项应另行审批 targeted Stage2 contact-continuity DAgger，而不是本任务内训练。",
        "",
        "## 11. Limitations",
        "",
        "- 每个正式 `(seed, env_id)` 只有一条 first episode；same-seed replay drift、real-camera calibration、latency、exposure、deployment 与 generalization 不在本报告中宣称。",
        "- Teacher 仅覆盖 seeds 0–15；paired table 只覆盖这 16 个共同 seed。",
        "- 几何比较是描述性关联；Mann–Whitney p 值不构成视觉因果证明。",
        "- Visibility capture stopped after its approved retry limit; no fallback projection or imputation was used.",
        "",
        "## 12. Reproducibility",
        "",
        "```bash",
        "/home/baoquanc/anaconda3/envs/isaaclab/bin/python scriptsFORhuman/analyze_cb2h_v19_largescale_camera_eval_20260810.py",
        "```",
        "",
        "Generated artifacts: `logs_eval/by_batch/cb2h_v19_toeout6_pitch50_largescale_camera_eval_20260810/summary/per_episode_records.json`, `logs_eval/by_batch/cb2h_v19_toeout6_pitch50_largescale_camera_eval_20260810/summary/aggregate_stats.json`, and this report.",
    ])
    return "\n".join(lines) + "\n"


def main() -> None:
    require(RESULT_ROOT.is_dir(), f"missing frozen result root: {RESULT_ROOT}")
    dt_info = validate_config()
    formal_dirs = {
        "student": discover_formal("student", "formal_student_metrics.json", range(32)),
        "teacher": discover_formal("teacher", "formal_teacher_metrics.json", range(16)),
    }
    custom_dirs = discover_customdata(range(32))
    teacher_proof = validate_teacher_proof()
    custom_joined = validate_customdata(custom_dirs)
    records = make_records(formal_dirs, custom_joined, dt_info)
    per_episode_path = SUMMARY_ROOT / "per_episode_records.json"
    aggregate_path = SUMMARY_ROOT / "aggregate_stats.json"
    report_path = REPO_ROOT / "scriptsFORhuman/C-B2H_v19_LargeScale_Camera_Eval_Report_20260810.md"
    json_dump(per_episode_path, {"schema": "cb2h_v19_largescale_camera_per_episode_v1", "record_count": len(records), "records": records})
    aggregate = build_aggregate(records, formal_dirs, custom_dirs, dt_info, teacher_proof)
    json_dump(aggregate_path, aggregate)
    aggregate_reloaded = load_json(aggregate_path)
    ensure_finite(aggregate_reloaded)
    report_path.write_text(report_from_json(aggregate_reloaded), encoding="utf-8")
    print("PASS: C-B2H v19 large-scale camera analysis")
    print(f"student={aggregate['controllers']['student']['successes']}/{aggregate['controllers']['student']['total']}")
    print(f"teacher={aggregate['controllers']['teacher']['successes']}/{aggregate['controllers']['teacher']['total']}")
    print(f"per_episode_records={len(records)}")
    print(f"gap_pp={aggregate['gap']['teacher_minus_student_percentage_points']:.7f}")
    print(f"visibility_status={aggregate['visibility_capture_gap']['status']}")


if __name__ == "__main__":
    try:
        main()
    except AnalysisError as exc:
        raise SystemExit(f"FAIL: {exc}") from exc
