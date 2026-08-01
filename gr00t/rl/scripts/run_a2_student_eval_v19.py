#!/usr/bin/env python3
"""Fail-fast v19 C-B2H Student evaluation and selected-case render bootstrap.

The formal lane evaluates exactly one first episode in each of sixteen envs and
seals a deterministic ranking artifact.  The render lane consumes that sealed
artifact; it never discovers or hard-codes a selected environment.  Heavy
IsaacLab/IsaacSim imports are intentionally kept behind ``main`` so contract
helpers and tests remain CPU-safe.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import runpy
import shutil
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
EVAL_ENTRY = (REPO_ROOT / "gr00t/rl/eval_agent_trl.py").resolve(strict=True)
RUNTIME_BOOTSTRAP_PATH = (
    REPO_ROOT / "gr00t/rl/scripts/run_a2_student_distillation_v19.py"
).resolve(strict=True)
RUNTIME_BOOTSTRAP_MODULE_NAME = "_a2_student_distillation_v19_runtime"
CHECKPOINT = (
    REPO_ROOT
    / "logs_rl/cb2h_v19_distill/"
    "cb2h_v19_g2s2000_gpu7_64e_10k_fix0f9c11e_retry1/"
    "model_step_010000.pt"
).resolve()
CHECKPOINT_CONFIG = CHECKPOINT.with_name("config.yaml")
CHECKPOINT_SHA256 = "005705dc033605a24bc231b18fbfaabe3288a699130a7ce2e423eac736963a45"
CHECKPOINT_CONFIG_SHA256 = "24f94faeca0270928c9c3ff33568e50371dc4f2f3feb767f6fe0607bb084351f"
RUNTIME_REPOSITORY = Path("/tmp/cb2h_v19_runtime.waPJHftX/c18")
EXPECTED_RUNTIME_COMMIT = "c18aea8bdc1c76ce850b5223663d0ad8a7474c0a"
EXPECTED_GPU_INDEX = "7"
EXPECTED_LOGICAL_GPU_INDEX = "0"
EXPECTED_GPU_UUID = "GPU-7c8cb1d2-4ebf-e2e3-35ad-fa0f6f72924d"
EXPECTED_GPU_BINDING_MODE = "single-visible-logical-cuda0-v3"
EXPECTED_CUDA_DEVICE_ORDER = "PCI_BUS_ID"
EXPECTED_SEED = 0
EXPECTED_NUM_ENVS = 16
EXPECTED_EPISODES = 16
VIDEO_FPS = 20
SELECTION_SCHEMA = "a2_student_v19_selection_v1"
METRICS_SCHEMA = "a2_student_v19_metrics_v1"

# c18 terminal diagnostics expose these four exact randomized door-case values.
# They are the replay identity; target/source poses are dynamics outputs and are
# deliberately not used as a substitute.
RANDOMIZED_CASE_KEYS = (
    "door_hinge_drive_max_force",
    "door_handle_drive_max_force",
    "door_handle_height",
    "door_weight",
)
SEMANTIC_KEYS = ("goal_reached", "max_stage", "terminal_reason")
OUTCOME_KEYS = (*SEMANTIC_KEYS, "reward")
FORMAL_RANKING_ORDER = "goal_reached_desc,max_stage_desc,reward_desc,env_id_asc"
RENDER_TRIAL_RANKING_ORDER = (
    "replay_outcome.goal_reached_desc",
    "replay_outcome.max_stage_desc",
    "replay_outcome.reward_desc",
    "trial_id_asc",
)


def render_staging_root(output_root: Path) -> Path:
    """Return the sibling staging bundle used by the selected render lane."""
    output_root = output_root.expanduser().resolve()
    return output_root.with_name(f".{output_root.name}.writing")


def eval_runtime_log_root(mode: str, output_root: Path) -> Path:
    """Return the Hydra runtime-log directory without colliding with eval outputs."""
    if mode not in {"formal", "render"}:
        raise ValueError(f"unknown eval mode {mode!r}")
    output_root = output_root.expanduser().resolve()
    if mode == "render":
        return output_root.with_name(f".{output_root.name}.runtime")
    return output_root / "hydra"


def temporary_policy_video_path(final_path: Path) -> Path:
    """Keep the final ``.mp4`` suffix so ImageIO selects its FFMPEG writer."""
    final_path = final_path.expanduser().resolve()
    if final_path.suffix.lower() != ".mp4":
        raise ValueError(f"policy video final path must end in .mp4: {final_path}")
    return final_path.with_name(f".{final_path.stem}.writing{final_path.suffix}")


def publish_render_bundle(staging_root: Path, output_root: Path) -> None:
    """Atomically publish a fully validated staging directory without overwrite."""
    staging_root = staging_root.expanduser().resolve()
    output_root = output_root.expanduser().resolve()
    if output_root.exists():
        raise FileExistsError(f"refusing to overwrite final render bundle: {output_root}")
    if not staging_root.is_dir():
        raise FileNotFoundError(f"render staging bundle is unavailable: {staging_root}")
    os.replace(staging_root, output_root)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def atomic_json_write(path: Path, value: Any) -> None:
    path = path.expanduser().resolve()
    if path.exists():
        raise FileExistsError(f"refusing to overwrite sealed output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.writing")
    if tmp.exists():
        raise FileExistsError(f"temporary output already exists: {tmp}")
    try:
        with tmp.open("x", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    except BaseException:
        if tmp.exists():
            tmp.unlink()
        raise


def json_safe(value: Any) -> Any:
    """Convert runtime metric containers without importing torch or numpy."""
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    tolist = getattr(value, "tolist", None)
    if callable(tolist):
        return json_safe(tolist())
    item = getattr(value, "item", None)
    if callable(item):
        return json_safe(item())
    raise TypeError(f"metric value is not JSON serializable: {type(value).__name__}")


def validate_checkpoint_artifacts(
    checkpoint: Path = CHECKPOINT, config_path: Path = CHECKPOINT_CONFIG
) -> dict[str, Any]:
    checkpoint = checkpoint.expanduser().resolve(strict=True)
    config_path = config_path.expanduser().resolve(strict=True)
    if checkpoint != CHECKPOINT:
        raise ValueError(f"v19 Student checkpoint is pinned to {CHECKPOINT}; got {checkpoint}")
    if config_path != CHECKPOINT_CONFIG:
        raise ValueError(f"v19 Student config is pinned to {CHECKPOINT_CONFIG}; got {config_path}")
    checkpoint_sha = sha256_file(checkpoint)
    config_sha = sha256_file(config_path)
    if checkpoint_sha != CHECKPOINT_SHA256:
        raise RuntimeError(f"Student checkpoint SHA256 drift: expected {CHECKPOINT_SHA256}, got {checkpoint_sha}")
    if config_sha != CHECKPOINT_CONFIG_SHA256:
        raise RuntimeError(f"Student config SHA256 drift: expected {CHECKPOINT_CONFIG_SHA256}, got {config_sha}")
    return {
        "path": str(checkpoint),
        "sha256": checkpoint_sha,
        "config_path": str(config_path),
        "config_sha256": config_sha,
    }


def load_runtime_bootstrap_module():
    """Load the v19 bootstrap from this worktree before any ``gr00t`` import."""
    source_path = RUNTIME_BOOTSTRAP_PATH.expanduser().resolve(strict=True)
    expected_path = (
        REPO_ROOT / "gr00t/rl/scripts/run_a2_student_distillation_v19.py"
    ).resolve(strict=True)
    if source_path != expected_path:
        raise RuntimeError(
            "v19 runtime bootstrap source identity mismatch: "
            f"source={source_path} expected={expected_path}"
        )
    preloaded_gr00t = sorted(
        name for name in sys.modules if name == "gr00t" or name.startswith("gr00t.")
    )
    if preloaded_gr00t:
        raise RuntimeError(
            "v19 runtime bootstrap must load before any gr00t package import: "
            f"preloaded={preloaded_gr00t}"
        )
    if RUNTIME_BOOTSTRAP_MODULE_NAME in sys.modules:
        raise RuntimeError(
            f"v19 runtime bootstrap module is already loaded: {RUNTIME_BOOTSTRAP_MODULE_NAME}"
        )
    spec = importlib.util.spec_from_file_location(
        RUNTIME_BOOTSTRAP_MODULE_NAME,
        source_path,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"unable to load v19 runtime bootstrap: {source_path}")
    if spec.origin is None or Path(spec.origin).resolve(strict=True) != source_path:
        raise RuntimeError(
            "v19 runtime bootstrap spec source identity mismatch: "
            f"origin={spec.origin!r} expected={source_path}"
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[RUNTIME_BOOTSTRAP_MODULE_NAME] = module
    try:
        spec.loader.exec_module(module)
        loaded_path = Path(getattr(module, "__file__", "")).expanduser().resolve(strict=True)
        if loaded_path != source_path:
            raise RuntimeError(
                "v19 runtime bootstrap loaded from an unexpected source: "
                f"loaded={loaded_path} expected={source_path}"
            )
        if getattr(module, "EXPECTED_RUNTIME_COMMIT", None) != EXPECTED_RUNTIME_COMMIT:
            raise RuntimeError(
                "v19 runtime bootstrap commit identity mismatch: "
                f"module={getattr(module, 'EXPECTED_RUNTIME_COMMIT', None)!r} "
                f"expected={EXPECTED_RUNTIME_COMMIT!r}"
            )
        return module
    except BaseException:
        if sys.modules.get(RUNTIME_BOOTSTRAP_MODULE_NAME) is module:
            del sys.modules[RUNTIME_BOOTSTRAP_MODULE_NAME]
        raise


def build_hydra_overrides(
    mode: str, output_root: Path, checkpoint: Path = CHECKPOINT
) -> list[str]:
    """Build one explicit Student-only eval contract for ``eval_agent_trl``."""
    if mode not in {"formal", "render"}:
        raise ValueError(f"unknown eval mode {mode!r}")
    output_root = output_root.expanduser().resolve()
    render = mode == "render"
    bundle_root = render_staging_root(output_root) if render else output_root
    external_root = bundle_root / "external_debug_videos"
    runtime_log_root = eval_runtime_log_root(mode, output_root)
    overrides = [
        f"checkpoint={checkpoint.resolve()}",
        "+seed=0",
        "+num_envs=16",
        "+headless=true",
        "+use_wandb=false",
        "+algo.config.enforce_teacher_rollout=false",
        "+algo.config.ratio_teacher_rollout=0.0",
        "+algo.config.use_a2_base=true",
        "+algo.config.eval.eval_num_envs_episodes=true",
        "algo.config.eval.num_eval_episodes=16",
        "+simulator.config.render_results=" + ("true" if render else "false"),
        f"eval_output_dir={bundle_root}",
        f"eval_log_dir={runtime_log_root}",
    ]
    if render:
        overrides.append(f"env.config.save_rendering_dir={external_root}")
    _require_one_override(overrides, "seed", "0")
    _require_one_override(overrides, "num_envs", "16")
    _require_one_override(overrides, "algo.config.enforce_teacher_rollout", "false")
    _require_one_override(overrides, "algo.config.ratio_teacher_rollout", "0.0")
    _require_one_override(overrides, "algo.config.eval.eval_num_envs_episodes", "true")
    _require_one_override(overrides, "algo.config.eval.num_eval_episodes", "16")
    _require_one_override(overrides, "eval_output_dir", str(bundle_root))
    _require_one_override(overrides, "eval_log_dir", str(runtime_log_root))
    return overrides


def _require_one_override(overrides: Sequence[str], key: str, expected: str) -> None:
    matches = []
    for argument in overrides:
        normalized = argument[1:] if argument.startswith("+") else argument
        if normalized.startswith(f"{key}="):
            matches.append(normalized.split("=", 1)[1])
    if matches != [expected]:
        raise ValueError(f"expected exactly one {key}={expected} override; got {matches!r}")


def validate_student_contract(config: Mapping[str, Any]) -> None:
    """Validate the effective trainer/env contract at runtime, fail-fast."""
    if config.get("enforce_teacher_rollout") is not False:
        raise RuntimeError("Student eval requires enforce_teacher_rollout=false")
    if float(config.get("ratio_teacher_rollout", -1.0)) != 0.0:
        raise RuntimeError("Student eval requires ratio_teacher_rollout=0.0")
    if config.get("use_a2_base") is not True:
        raise RuntimeError("Student eval requires the frozen A2_Base leg controller")
    eval_config = config.get("eval", {})
    if not isinstance(eval_config, Mapping):
        raise TypeError("Student eval config.eval must be a mapping")
    if eval_config.get("eval_num_envs_episodes") is not True:
        raise RuntimeError("Student eval requires exactly one first episode per env")
    if int(eval_config.get("num_eval_episodes", EXPECTED_EPISODES)) != EXPECTED_EPISODES:
        raise RuntimeError("Student eval requires num_eval_episodes=16")


def extract_randomized_case(diagnostic: Mapping[str, Any]) -> dict[str, Any]:
    """Extract exact reset-case fields from a terminal diagnostic."""
    for key in ("randomized_case", "randomization_case", "randomization"):
        nested = diagnostic.get(key)
        if isinstance(nested, Mapping):
            missing = [name for name in RANDOMIZED_CASE_KEYS if name not in nested]
            if missing:
                raise KeyError(f"terminal randomized_case is missing required c18 fields: {missing}")
            return {name: json_safe(nested[name]) for name in RANDOMIZED_CASE_KEYS}
    missing = [key for key in RANDOMIZED_CASE_KEYS if key not in diagnostic]
    if missing:
        raise KeyError(
            "terminal diagnostic is missing required c18 randomized-case fields: "
            f"{missing}"
        )
    return {key: json_safe(diagnostic[key]) for key in RANDOMIZED_CASE_KEYS}


def _diagnostic_semantics(
    record: Mapping[str, Any], diagnostic: Mapping[str, Any]
) -> dict[str, Any]:
    terminal_reason = record.get("terminal_reason", diagnostic.get("terminal_reasons"))
    max_stage = record.get("max_stage", diagnostic.get("stage_buf"))
    goal_reached = record.get("goal_reached")
    if goal_reached is None:
        goal_reached = bool(
            terminal_reason == "complete" or int(max_stage) >= 5
        )
    if not isinstance(goal_reached, bool):
        raise TypeError(f"goal_reached must be bool, got {goal_reached!r}")
    if not isinstance(max_stage, int):
        max_stage = int(max_stage)
    if not isinstance(terminal_reason, str) or not terminal_reason:
        raise ValueError(f"terminal_reason must be a non-empty string, got {terminal_reason!r}")
    return {
        "goal_reached": goal_reached,
        "max_stage": max_stage,
        "terminal_reason": terminal_reason,
    }


def episode_records(metrics: Mapping[str, Any]) -> list[dict[str, Any]]:
    required = (
        "episode_rewards",
        "episode_goal_reached",
        "episode_max_stage_reached",
        "episode_terminal_reasons",
        "episode_terminal_diagnostics",
    )
    missing = [key for key in required if key not in metrics]
    if missing:
        raise KeyError(f"formal eval metrics missing required fields: {missing}")
    lengths = [len(metrics[key]) for key in required]
    if len(set(lengths)) != 1 or lengths[0] != EXPECTED_EPISODES:
        raise RuntimeError(f"expected 16 aligned first-episode metric entries; lengths={lengths}")
    records = []
    seen = set()
    for idx in range(EXPECTED_EPISODES):
        diagnostic = metrics["episode_terminal_diagnostics"][idx]
        if not isinstance(diagnostic, Mapping):
            raise TypeError(f"terminal diagnostic {idx} is not a mapping")
        diagnostic = json_safe(diagnostic)
        if "env_id" not in diagnostic:
            raise KeyError(f"terminal diagnostic {idx} is missing required env_id")
        env_id = diagnostic["env_id"]
        if isinstance(env_id, bool) or not isinstance(env_id, int):
            raise TypeError(
                f"terminal diagnostic {idx} env_id must be an integer; got {env_id!r}"
            )
        if env_id in seen or not 0 <= env_id < EXPECTED_NUM_ENVS:
            raise RuntimeError(f"terminal diagnostic env_id is not unique/in range: {env_id}")
        seen.add(env_id)
        semantics = _diagnostic_semantics(
            {
                "goal_reached": bool(metrics["episode_goal_reached"][idx]),
                "max_stage": int(metrics["episode_max_stage_reached"][idx]),
                "terminal_reason": metrics["episode_terminal_reasons"][idx],
            },
            diagnostic,
        )
        records.append(
            {
                "env_id": env_id,
                # eval_num_envs_episodes=true is the protocol authority: every
                # record is the first episode, independent of completion order.
                "episode_index": 0,
                "reward": float(metrics["episode_rewards"][idx]),
                **semantics,
                "randomized_case": extract_randomized_case(diagnostic),
                "terminal_diagnostic": diagnostic,
            }
        )
    if seen != set(range(EXPECTED_NUM_ENVS)):
        raise RuntimeError(f"formal eval did not return one entry for every env: {sorted(seen)}")
    return records


def rank_episode_records(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    if len(records) != EXPECTED_EPISODES:
        raise ValueError(f"ranking requires exactly 16 records; got {len(records)}")
    ranked = sorted(
        (dict(record) for record in records),
        key=lambda record: (
            -int(bool(record["goal_reached"])),
            -int(record["max_stage"]),
            -float(record["reward"]),
            int(record["env_id"]),
        ),
    )
    for rank, record in enumerate(ranked):
        record["rank"] = rank
    return ranked


def seal_formal_selection(
    metrics: Mapping[str, Any], output_root: Path, checkpoint_info: Mapping[str, Any]
) -> dict[str, Any]:
    output_root = output_root.expanduser().resolve()
    if output_root.exists() and not output_root.is_dir():
        raise FileExistsError(f"formal output root is not a directory: {output_root}")
    records = episode_records(json_safe(metrics))
    ranked = rank_episode_records(records)
    source_metrics = {
        "schema": METRICS_SCHEMA,
        "contract": {
            "seed": EXPECTED_SEED,
            "num_envs": EXPECTED_NUM_ENVS,
            "one_episode_per_env": True,
            "pure_student": True,
            "teacher_rollout_ratio": 0.0,
            "use_a2_base": True,
        },
        "episodes": records,
    }
    metrics_path = output_root / "formal_student_metrics.json"
    atomic_json_write(metrics_path, source_metrics)
    selected = ranked[0]
    selection = {
        "schema": SELECTION_SCHEMA,
        "checkpoint": dict(checkpoint_info),
        "contract": source_metrics["contract"],
        "ranking": {
            "order": FORMAL_RANKING_ORDER,
            "records": ranked,
        },
        "selected": {
            "env_id": selected["env_id"],
            "episode_index": selected["episode_index"],
            "reward": selected["reward"],
            "goal_reached": selected["goal_reached"],
            "max_stage": selected["max_stage"],
            "terminal_reason": selected["terminal_reason"],
            "randomized_case": selected["randomized_case"],
        },
        "source_metrics": {
            "path": str(metrics_path),
            "sha256": sha256_file(metrics_path),
        },
    }
    selection_path = output_root / "student_selection.json"
    atomic_json_write(selection_path, selection)
    return selection


def load_sealed_selection(selection_path: Path, source_metrics_path: Path | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    selection_path = selection_path.expanduser().resolve(strict=True)
    with selection_path.open(encoding="utf-8") as stream:
        selection = json.load(stream)
    if selection.get("schema") != SELECTION_SCHEMA:
        raise ValueError(f"unsupported selection schema: {selection.get('schema')!r}")
    contract = selection.get("contract")
    expected_contract = {
        "seed": EXPECTED_SEED,
        "num_envs": EXPECTED_NUM_ENVS,
        "one_episode_per_env": True,
        "pure_student": True,
        "teacher_rollout_ratio": 0.0,
        "use_a2_base": True,
    }
    if contract != expected_contract:
        raise ValueError(f"sealed selection contract drift: expected {expected_contract}, got {contract}")
    checkpoint = selection.get("checkpoint", {})
    if checkpoint.get("path") != str(CHECKPOINT) or checkpoint.get("sha256") != CHECKPOINT_SHA256:
        raise ValueError("sealed selection does not identify the pinned v19 checkpoint")
    source_spec = selection.get("source_metrics")
    if not isinstance(source_spec, Mapping):
        raise KeyError("sealed selection is missing source_metrics path/hash")
    embedded_source = Path(source_spec.get("path", "")).expanduser().resolve()
    if source_metrics_path is not None and embedded_source != source_metrics_path.expanduser().resolve():
        raise ValueError("explicit source metrics path differs from sealed selection")
    if not embedded_source.is_file() or sha256_file(embedded_source) != source_spec.get("sha256"):
        raise RuntimeError("sealed source metrics path/hash validation failed")
    with embedded_source.open(encoding="utf-8") as stream:
        metrics = json.load(stream)
    if metrics.get("schema") != METRICS_SCHEMA or metrics.get("contract") != expected_contract:
        raise ValueError("source metrics schema/contract drift")
    source_records = metrics.get("episodes")
    if not isinstance(source_records, list) or len(source_records) != EXPECTED_EPISODES:
        raise ValueError("source metrics must seal exactly 16 episode records")
    if any(not isinstance(record, Mapping) for record in source_records):
        raise ValueError("source metrics episode records must be mappings")
    if any(record.get("episode_index") != 0 for record in source_records):
        raise ValueError("source metrics must seal episode_index=0 for every first episode")
    ranked_source = rank_episode_records(source_records)
    ranking = selection.get("ranking")
    if not isinstance(ranking, Mapping):
        raise KeyError("sealed selection is missing frozen ranking")
    if ranking.get("order") != FORMAL_RANKING_ORDER:
        raise ValueError("sealed selection ranking order drifted")
    ranked_records = ranking.get("records")
    if not isinstance(ranked_records, list) or len(ranked_records) != EXPECTED_EPISODES:
        raise ValueError("sealed selection ranking must contain exactly 16 records")
    if any(not isinstance(record, Mapping) for record in ranked_records):
        raise TypeError("sealed selection ranking records must be mappings")
    if canonical_json(ranked_records) != canonical_json(ranked_source):
        raise RuntimeError(
            "sealed selection ranking records are not provenance-consistent with "
            "hash-validated source metrics"
        )
    selected = selection.get("selected")
    if not isinstance(selected, Mapping):
        raise KeyError("sealed selection is missing selected case")
    selected_env = selected.get("env_id")
    if isinstance(selected_env, bool) or not isinstance(selected_env, int):
        raise TypeError(f"sealed selected env_id must be an integer; got {selected_env!r}")
    if not 0 <= selected_env < EXPECTED_NUM_ENVS:
        raise ValueError("selected env id is outside the formal 16-env range")
    if selected.get("episode_index") != 0:
        raise ValueError("sealed selected case must identify episode_index=0")
    randomized_case = selected.get("randomized_case")
    if not isinstance(randomized_case, Mapping):
        raise KeyError("sealed selection is missing exact randomized_case fields")
    if set(randomized_case) != set(RANDOMIZED_CASE_KEYS):
        raise ValueError(
            "sealed selected case randomized_case keys drifted: "
            f"expected={list(RANDOMIZED_CASE_KEYS)} got={sorted(randomized_case)}"
        )
    top = ranked_source[0]
    for key in (
        "env_id",
        "episode_index",
        "goal_reached",
        "max_stage",
        "terminal_reason",
        "randomized_case",
    ):
        if selected.get(key) != top.get(key):
            raise ValueError(f"sealed selected case does not match frozen ranking for {key}")
    if "reward" in selected and selected["reward"] != top["reward"]:
        raise ValueError("sealed selected case does not match frozen ranking for reward")
    # Older v1 selection files did not duplicate reward in `selected`; derive it
    # from the sealed ranked record without changing the on-disk provenance.
    if "reward" not in selected and isinstance(selected, dict):
        selected["reward"] = top["reward"]
    return selection, metrics


def _selected_formal_record(selection: Mapping[str, Any]) -> dict[str, Any]:
    selected = selection.get("selected")
    if not isinstance(selected, Mapping):
        raise KeyError("sealed selection is missing selected case")
    ranking = selection.get("ranking")
    ranked_records = ranking.get("records") if isinstance(ranking, Mapping) else None
    if not isinstance(ranked_records, list):
        raise KeyError("sealed selection is missing frozen ranking records")
    matches = [
        record
        for record in ranked_records
        if isinstance(record, Mapping)
        and record.get("env_id") == selected.get("env_id")
        and record.get("episode_index") == selected.get("episode_index")
        and record.get("randomized_case") == selected.get("randomized_case")
    ]
    if len(matches) != 1:
        raise RuntimeError(
            "sealed selection must contain exactly one frozen record for the selected case; "
            f"matches={len(matches)}"
        )
    source = dict(matches[0])
    if any(key not in source for key in OUTCOME_KEYS):
        raise KeyError(f"sealed selected formal record is missing outcome fields: {OUTCOME_KEYS}")
    return source


def _outcome_fields(record: Mapping[str, Any]) -> dict[str, Any]:
    return {key: record[key] for key in OUTCOME_KEYS}


def _outcome_drift(
    source: Mapping[str, Any], replay: Mapping[str, Any]
) -> dict[str, dict[str, Any]]:
    return {
        key: {
            "source": source[key],
            "replay": replay[key],
            "changed": source[key] != replay[key],
        }
        for key in OUTCOME_KEYS
    }


def validate_replay_selected_case(
    selection: Mapping[str, Any], replay_metrics: Mapping[str, Any]
) -> dict[str, Any]:
    source = _selected_formal_record(selection)
    env_id = source.get("env_id")
    if isinstance(env_id, bool) or not isinstance(env_id, int):
        raise TypeError(f"selected formal env_id must be an integer; got {env_id!r}")
    if not 0 <= env_id < EXPECTED_NUM_ENVS:
        raise ValueError(f"selected formal env_id is outside range: {env_id}")
    episode_index = source.get("episode_index")
    if isinstance(episode_index, bool) or not isinstance(episode_index, int):
        raise TypeError(
            f"selected formal episode_index must be an integer; got {episode_index!r}"
        )
    records = episode_records(json_safe(replay_metrics))
    replay = next((record for record in records if record["env_id"] == env_id), None)
    if replay is None:
        raise RuntimeError(f"replay did not return selected env {env_id}")
    if replay["episode_index"] != episode_index:
        raise RuntimeError(
            "selected replay episode_index drift: "
            f"source={episode_index!r}, replay={replay['episode_index']!r}"
        )
    source_case = source.get("randomized_case")
    replay_case = replay.get("randomized_case")
    if not isinstance(source_case, Mapping) or set(source_case) != set(RANDOMIZED_CASE_KEYS):
        raise ValueError("sealed selected formal randomized_case identity is incomplete")
    if not isinstance(replay_case, Mapping) or set(replay_case) != set(RANDOMIZED_CASE_KEYS):
        raise RuntimeError("replay randomized_case identity is incomplete")
    if replay_case != source_case:
        raise RuntimeError("selected replay randomized-case fields differ from source terminal diagnostics")
    source_outcome = _outcome_fields(source)
    replay_outcome = _outcome_fields(replay)
    validated = dict(replay)
    validated["case_identity"] = {
        "env_id": env_id,
        "episode_index": episode_index,
        "randomized_case": dict(source_case),
    }
    validated["source_formal_outcome"] = source_outcome
    validated["replay_outcome"] = replay_outcome
    validated["outcome_drift"] = _outcome_drift(source_outcome, replay_outcome)
    return validated


def validate_policy_camera_contract(
    left: Any,
    right: Any,
    head: Any,
    vision_obs: Any,
    context_vision_obs: Any,
    camera_meta: Any,
    cameras_config: Mapping[str, Any],
    env_count: int = EXPECTED_NUM_ENVS,
) -> None:
    """Prove raw C-B2H tri-view frames recompute the policy observation tensors."""
    import torch

    expected = {
        "left": (env_count, 384, 216, 3),
        "right": (env_count, 384, 216, 3),
        "head": (env_count, 136, 384, 3),
        "vision_obs": (env_count, 384, 216, 6),
        "context_vision_obs": (env_count, 136, 384, 3),
        "camera_meta": (env_count, 6),
    }
    values = {"left": left, "right": right, "head": head, "vision_obs": vision_obs, "context_vision_obs": context_vision_obs, "camera_meta": camera_meta}
    for name, value in values.items():
        if not torch.is_tensor(value) or tuple(value.shape) != expected[name]:
            raise RuntimeError(f"{name} contract drift: expected {expected[name]}, got {getattr(value, 'shape', None)}")
        if name in {"left", "right", "head"} and value.dtype != torch.uint8:
            raise RuntimeError(f"raw {name} camera must remain uint8; got {value.dtype}")
        if name not in {"left", "right", "head"} and (not torch.is_floating_point(value) or not bool(torch.all(torch.isfinite(value)).item())):
            raise RuntimeError(f"policy {name} must be finite floating-point")
    from gr00t.rl.utils.a2_policy_camera import (
        compose_channel_stacked_dual_rgb,
        normalize_head_context_rgb,
    )

    mean = list(cameras_config["image_mean"])
    std = list(cameras_config["image_std"])
    recomposed = compose_channel_stacked_dual_rgb(
        left,
        right,
        resolution=(384, 216),
        image_mean=mean,
        image_std=std,
    )
    normalized_head = normalize_head_context_rgb(
        head,
        resolution=(136, 384),
        image_mean=mean,
        image_std=std,
    )
    if not torch.equal(recomposed, vision_obs):
        raise RuntimeError("raw left/right frames do not exactly recompose vision_obs")
    if not torch.equal(normalized_head, context_vision_obs):
        raise RuntimeError("raw OEM head frame does not exactly recompose context_vision_obs")
    if not bool(torch.all(torch.isfinite(camera_meta)).item()):
        raise RuntimeError("camera_meta contains non-finite values")


def _inverse_normalize_policy_rgb(
    normalized: Any,
    *,
    image_mean: Sequence[float],
    image_std: Sequence[float],
    name: str,
) -> Any:
    """Recover raw uint8 RGB while proving an integer normalization round-trip."""
    import torch

    if not torch.is_tensor(normalized) or normalized.dtype != torch.float32:
        raise RuntimeError(
            f"{name} must be float32 policy input for exact raw-frame recovery; "
            f"got dtype={getattr(normalized, 'dtype', None)}"
        )
    if not bool(torch.all(torch.isfinite(normalized)).item()):
        raise RuntimeError(f"{name} contains non-finite normalized pixels")
    mean = torch.as_tensor(list(image_mean), device=normalized.device, dtype=torch.float32)
    std = torch.as_tensor(list(image_std), device=normalized.device, dtype=torch.float32)
    if tuple(mean.shape) != (3,) or tuple(std.shape) != (3,):
        raise RuntimeError(f"{name} image mean/std must each have three values")
    if not bool(torch.all(torch.isfinite(mean)).item()) or not bool(torch.all(torch.isfinite(std)).item()):
        raise RuntimeError(f"{name} image mean/std must be finite")
    if bool(torch.any(std <= 0.0).item()):
        raise RuntimeError(f"{name} image_std must be strictly positive")
    raw_float = (normalized * std + mean) * 255.0
    if not bool(torch.all(torch.isfinite(raw_float)).item()):
        raise RuntimeError(f"{name} inverse normalization produced non-finite RGB")
    tolerance = 2.0e-3
    if bool(torch.any(raw_float < -tolerance).item()) or bool(torch.any(raw_float > 255.0 + tolerance).item()):
        raise RuntimeError(f"{name} inverse normalization escaped uint8 range")
    rounded = torch.round(raw_float)
    if bool(torch.any(torch.abs(raw_float - rounded) > tolerance).item()):
        raise RuntimeError(f"{name} normalized pixels do not have an integer uint8 round-trip")
    raw = rounded.clamp(0.0, 255.0).to(torch.uint8)
    if tuple(raw.shape[:-1]) != tuple(normalized.shape[:-1]) or raw.shape[-1] != 3:
        raise RuntimeError(f"{name} recovered raw frame shape drifted: {tuple(raw.shape)}")
    return raw


def derive_raw_policy_frames_from_observations(
    vision_obs: Any,
    context_vision_obs: Any,
    *,
    image_mean: Sequence[float],
    image_std: Sequence[float],
    env_count: int = EXPECTED_NUM_ENVS,
) -> tuple[Any, Any, Any]:
    """Derive left/right/head uint8 frames only from the Student policy inputs."""
    import torch

    expected_vision = (env_count, 384, 216, 6)
    expected_context = (env_count, 136, 384, 3)
    if not torch.is_tensor(vision_obs) or tuple(vision_obs.shape) != expected_vision:
        raise RuntimeError(
            f"vision_obs contract drift: expected {expected_vision}, got {getattr(vision_obs, 'shape', None)}"
        )
    if not torch.is_tensor(context_vision_obs) or tuple(context_vision_obs.shape) != expected_context:
        raise RuntimeError(
            "context_vision_obs contract drift: "
            f"expected {expected_context}, got {getattr(context_vision_obs, 'shape', None)}"
        )
    if vision_obs.dtype != torch.float32 or context_vision_obs.dtype != torch.float32:
        raise RuntimeError("Student tri-view policy inputs must be float32")
    left = _inverse_normalize_policy_rgb(
        vision_obs[..., :3], image_mean=image_mean, image_std=image_std, name="vision_obs.left"
    )
    right = _inverse_normalize_policy_rgb(
        vision_obs[..., 3:6], image_mean=image_mean, image_std=image_std, name="vision_obs.right"
    )
    head = _inverse_normalize_policy_rgb(
        context_vision_obs, image_mean=image_mean, image_std=image_std, name="context_vision_obs.head"
    )
    from gr00t.rl.utils.a2_policy_camera import (
        compose_channel_stacked_dual_rgb,
        normalize_head_context_rgb,
    )

    recomposed = compose_channel_stacked_dual_rgb(
        left,
        right,
        resolution=(384, 216),
        image_mean=image_mean,
        image_std=image_std,
    )
    if not torch.equal(recomposed, vision_obs):
        raise RuntimeError("derived left/right raw frames do not bitwise recompose vision_obs")
    normalized_head = normalize_head_context_rgb(
        head,
        resolution=(136, 384),
        image_mean=image_mean,
        image_std=image_std,
    )
    if not torch.equal(normalized_head, context_vision_obs):
        raise RuntimeError("derived raw head frame does not bitwise recompose context_vision_obs")
    return left, right, head


def validate_external_debug_videos(paths: Sequence[Path], env_id: int) -> None:
    if len(paths) != 3:
        raise RuntimeError(f"selected render requires exactly three external debug videos; got {len(paths)}")
    env_pattern = re.compile(r"env[_-]?(\d+)", re.IGNORECASE)
    for path in paths:
        if path.stat().st_size <= 0:
            raise RuntimeError(f"external debug video is empty: {path}")
        ids = [int(match.group(1)) for match in env_pattern.finditer(path.name)]
        if not ids:
            raise RuntimeError(f"external debug video has no env identity: {path.name}")
        if any(item != env_id for item in ids):
            raise RuntimeError(f"external debug video is not selected-env-only: {path.name}")
    names = {path.name for path in paths}
    top = [name for name in names if "handle_top" in name]
    side = [name for name in names if "handle_side" in name]
    main = [name for name in names if "handle_top" not in name and "handle_side" not in name]
    if len(top) != 1 or len(side) != 1 or len(main) != 1:
        raise RuntimeError("external debug videos must include handle_top and handle_side cameras")


def _bind_a2_eval_methods():
    from gr00t.rl.trl.trainer.distill_trainer_a2_base_api import TRLDistillTrainerA2BaseAPI
    from gr00t.rl.trl.trainer.ppo_trainer import TRLPPOTrainer as GenericTRLPPOTrainer
    from gr00t.rl.trl.trainer.ppo_trainer_a2_base_api import TRLPPOTrainer as A2TRLPPOTrainer

    if TRLDistillTrainerA2BaseAPI.eval is not GenericTRLPPOTrainer.eval:
        raise RuntimeError("Student eval expected generic PPO eval before A2 correction")
    TRLDistillTrainerA2BaseAPI.eval = A2TRLPPOTrainer.eval
    if TRLDistillTrainerA2BaseAPI.eval is not A2TRLPPOTrainer.eval:
        raise RuntimeError("A2 Student eval method binding did not take effect")
    return TRLDistillTrainerA2BaseAPI, A2TRLPPOTrainer.eval


def _make_formal_eval(base_eval, output_root: Path, checkpoint_info: Mapping[str, Any]):
    def formal_eval(self):
        validate_student_contract(self.config)
        if self.env.num_envs != EXPECTED_NUM_ENVS:
            raise RuntimeError(f"formal Student eval requires 16 envs; got {self.env.num_envs}")
        result = base_eval(self)
        metrics = result if isinstance(result, Mapping) else self.env.get_eval_metrics_summary()
        selection = seal_formal_selection(metrics, output_root, checkpoint_info)
        print(f"[A2_STUDENT_FORMAL_PASS] selected_env={selection['selected']['env_id']} selection={output_root / 'student_selection.json'}", flush=True)
        return result

    formal_eval.__name__ = "formal_student_eval"
    formal_eval.__qualname__ = "formal_student_eval"
    formal_eval._a2_eval_base = base_eval
    return formal_eval


def _make_render_eval(
    base_eval,
    output_root: Path,
    selection: Mapping[str, Any],
    selection_path: Path,
):
    output_root = output_root.expanduser().resolve()
    staging_root = render_staging_root(output_root)
    selected_env = int(selection["selected"]["env_id"])
    selection_path = selection_path.expanduser().resolve(strict=True)

    def render_eval(self):
        import imageio.v2 as imageio
        import torch

        validate_student_contract(self.config)
        if self.env.num_envs != EXPECTED_NUM_ENVS:
            raise RuntimeError(f"selected render requires 16 envs; got {self.env.num_envs}")
        if not bool(self.env.config.simulator.config.get("render_results", False)):
            raise RuntimeError("selected render requires simulator.config.render_results=true")

        # The sibling staging directory is owned only after our mkdir succeeds;
        # all work after that point is inside this try/finally so injected setup
        # failures cannot leave a partial bundle behind.
        staging_owned = False
        committed = False
        policy_model = None
        original_rollout = None
        original_render_results = None
        writers: dict[str, Any] = {}
        first_frames: dict[str, Any] = {}
        frame_diversity: dict[str, bool] = {}
        frame_count = 0
        policy_input_checks = 0
        rollout_patched = False
        render_patched = False
        writers_closed = False

        def close_writers():
            nonlocal writers_closed
            if writers_closed:
                return
            close_error = None
            for writer in writers.values():
                try:
                    writer.close()
                except BaseException as exc:  # preserve cleanup while surfacing writer failure
                    close_error = close_error or exc
            writers_closed = True
            if close_error is not None:
                raise close_error

        try:
            policy_video_dir = staging_root / "policy_camera_videos"
            external_dir = staging_root / "external_debug_videos"
            configured_external = Path(self.env.config.save_rendering_dir).expanduser().resolve()
            if configured_external != external_dir.resolve():
                raise RuntimeError(f"external rendering directory drift: {configured_external}")
            if output_root.exists() or staging_root.exists():
                raise FileExistsError(
                    f"selected render refuses to overwrite final/staging bundle: "
                    f"final={output_root} staging={staging_root}"
                )
            try:
                staging_root.mkdir(parents=True)
            except BaseException:
                # The target was proven absent immediately before mkdir; if a
                # failed mkdir nevertheless materialized it, it is ours to clean.
                staging_owned = staging_root.exists()
                raise
            staging_owned = True
            policy_video_dir.mkdir()
            external_dir.mkdir()

            stage_final_paths = {
                "left_d435": policy_video_dir / f"d435_left_env{selected_env:04d}.mp4",
                "right_d435": policy_video_dir / f"d435_right_env{selected_env:04d}.mp4",
                "head_oem": policy_video_dir / f"oem_head_env{selected_env:04d}.mp4",
            }
            temporary_paths = {
                name: temporary_policy_video_path(path)
                for name, path in stage_final_paths.items()
            }
            if any(
                path.exists()
                for path in (*stage_final_paths.values(), *temporary_paths.values())
            ):
                raise FileExistsError("selected policy video staging output already exists")
            frame_diversity = {name: False for name in stage_final_paths}

            selection_sha256 = sha256_file(selection_path)
            unwrapped = self.accelerator.unwrap_model(self.model)
            if unwrapped.policy is not self.policy_model:
                raise RuntimeError("Student policy identity differs from unwrapped eval policy")
            policy_model = self.policy_model
            original_rollout = policy_model.rollout
            original_render_results = self.env.render_results

            def writer_for(name):
                writer = writers.get(name)
                if writer is None:
                    writer = imageio.get_writer(
                        str(temporary_paths[name]),
                        fps=VIDEO_FPS,
                        codec="libx264",
                        macro_block_size=2,
                    )
                    writers[name] = writer
                return writer

            def selected_external_render(env_ids=None, frame_type="step"):
                ids = torch.tensor([selected_env], device=self.env.device, dtype=torch.long)
                if env_ids is not None:
                    normalized = self.env._normalize_render_env_ids(env_ids)
                    ids = normalized[normalized == selected_env]
                return original_render_results(env_ids=ids, frame_type=frame_type)

            def captured_rollout(*args, **kwargs):
                nonlocal frame_count, policy_input_checks
                obs_dict = kwargs.get("obs_dict")
                if obs_dict is None and args:
                    obs_dict = args[0]
                if not isinstance(obs_dict, Mapping):
                    raise TypeError("Student rollout capture requires an obs_dict mapping")
                if not hasattr(self, "env_episode_completed"):
                    raise RuntimeError("first-episode mask was not initialized before Student rollout")
                if not bool(self.env_episode_completed[selected_env].item()):
                    cameras_cfg = self.env.config.simulator.config.cameras
                    left, right, head = derive_raw_policy_frames_from_observations(
                        obs_dict.get("vision_obs"),
                        obs_dict.get("context_vision_obs"),
                        image_mean=cameras_cfg.image_mean,
                        image_std=cameras_cfg.image_std,
                        env_count=EXPECTED_NUM_ENVS,
                    )
                    validate_policy_camera_contract(
                        left,
                        right,
                        head,
                        obs_dict.get("vision_obs"),
                        obs_dict.get("context_vision_obs"),
                        obs_dict.get("camera_meta"),
                        cameras_cfg,
                        env_count=EXPECTED_NUM_ENVS,
                    )
                    policy_input_checks += 1
                    frames = {
                        "left_d435": left[selected_env].detach().contiguous(),
                        "right_d435": right[selected_env].detach().contiguous(),
                        "head_oem": head[selected_env].detach().contiguous(),
                    }
                    for name, frame in frames.items():
                        if int(frame.max().item()) <= int(frame.min().item()):
                            raise RuntimeError(f"selected {name} frame is constant")
                        previous = first_frames.get(name)
                        if previous is not None and not torch.equal(previous, frame):
                            frame_diversity[name] = True
                        if previous is None:
                            first_frames[name] = frame.detach().clone()
                        writer_for(name).append_data(frame.cpu().numpy())
                    frame_count += 1
                return original_rollout(*args, **kwargs)

            if policy_model is None or original_rollout is None or original_render_results is None:
                raise RuntimeError("selected render policy hooks were not initialized")
            self.env.render_results = selected_external_render
            render_patched = True
            policy_model.rollout = captured_rollout
            rollout_patched = True
            result = base_eval(self)
            replay_metrics = result if isinstance(result, Mapping) else self.env.get_eval_metrics_summary()
            replay_validation = validate_replay_selected_case(selection, replay_metrics)
            if int(replay_metrics.get("completed_episodes", EXPECTED_EPISODES)) != EXPECTED_EPISODES:
                raise RuntimeError("selected render did not complete one episode in each env")
            if frame_count <= 0 or policy_input_checks != frame_count:
                raise RuntimeError(
                    f"policy input/frame mismatch: checks={policy_input_checks}, frames={frame_count}"
                )
            if not all(frame_diversity.values()):
                raise RuntimeError(f"selected policy videos lack frame diversity: {frame_diversity}")
            policy_model.rollout = original_rollout
            rollout_patched = False
            self.env.render_results = original_render_results
            render_patched = False
            close_writers()

            for name, temporary in temporary_paths.items():
                if not temporary.is_file() or temporary.stat().st_size <= 0:
                    raise RuntimeError(f"selected policy video was not written: {temporary}")
                os.replace(temporary, stage_final_paths[name])
            external_videos = sorted(external_dir.glob("*.mp4"))
            validate_external_debug_videos(external_videos, selected_env)
            stage_videos = [*stage_final_paths.values(), *external_videos]
            published_videos = [
                output_root / path.relative_to(staging_root) for path in stage_videos
            ]
            metadata = {
                "schema": "a2_student_v19_render_v2",
                "trial_id": output_root.name,
                "ranking": {
                    "order": list(RENDER_TRIAL_RANKING_ORDER),
                    "replay_outcome": replay_validation["replay_outcome"],
                    "trial_id": output_root.name,
                },
                "selection": {
                    "path": str(selection_path),
                    "sha256": selection_sha256,
                    "case_identity": replay_validation["case_identity"],
                },
                "source_formal_outcome": replay_validation["source_formal_outcome"],
                "replay_outcome": replay_validation["replay_outcome"],
                "outcome_drift": replay_validation["outcome_drift"],
                "source_formal_metrics": {
                    "path": str(Path(selection["source_metrics"]["path"]).resolve()),
                    "sha256": selection["source_metrics"]["sha256"],
                },
                "source_metrics": {
                    "path": str(Path(selection["source_metrics"]["path"]).resolve()),
                    "sha256": selection["source_metrics"]["sha256"],
                },
                "student_policy": {
                    "teacher_rollout": False,
                    "high_level_action_source": "student_policy_action_mean",
                    "leg_action_source": "frozen_a2_base",
                    "policy_input_checks": policy_input_checks,
                },
                "policy_cameras": {
                    "fps": VIDEO_FPS,
                    "frame_count": frame_count,
                    "camera_names": ["ego_camera", "policy_secondary_camera", "policy_context_camera"],
                    "frame_shapes": {name: list(first_frames[name].shape) for name in stage_final_paths},
                    "frame_diversity": frame_diversity,
                    "recomposition": "left/right channel-stacked vision_obs + head context_vision_obs",
                    "camera_meta_dim": 6,
                },
                "external_debug_cameras": {
                    "selected_env_only": True,
                    "video_count": len(external_videos),
                },
                "videos": [
                    {
                        "path": str(path),
                        "size_bytes": stage_path.stat().st_size,
                        "sha256": sha256_file(stage_path),
                    }
                    for path, stage_path in zip(published_videos, stage_videos)
                ],
            }
            atomic_json_write(staging_root / "selected_render_metadata.json", metadata)
            publish_render_bundle(staging_root, output_root)
            staging_owned = False
            committed = True
            print(
                f"[A2_STUDENT_SELECTED_RENDER_PASS] env_id={selected_env} "
                f"frames={frame_count} videos={len(stage_videos)} bundle={output_root}",
                flush=True,
            )
            return result
        finally:
            try:
                if rollout_patched:
                    policy_model.rollout = original_rollout
                if render_patched:
                    self.env.render_results = original_render_results
            finally:
                try:
                    close_writers()
                finally:
                    if staging_owned and not committed and staging_root.exists():
                        shutil.rmtree(staging_root)

    render_eval.__name__ = "selected_student_render_eval"
    render_eval.__qualname__ = "selected_student_render_eval"
    render_eval._a2_eval_base = base_eval
    return render_eval


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("formal", "render"), required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--selection-json", type=Path)
    parser.add_argument("--source-metrics", type=Path)
    parser.add_argument("--overlay-repository", type=Path, default=REPO_ROOT)
    parser.add_argument("--runtime-repository", type=Path, default=RUNTIME_REPOSITORY)
    args = parser.parse_args()
    if args.mode == "render" and args.selection_json is None:
        parser.error("--selection-json is required for render mode")
    if args.mode == "formal" and (args.selection_json is not None or args.source_metrics is not None):
        parser.error("formal mode does not accept a pre-existing selection/source metrics artifact")
    return args


def validate_output_root_preflight(mode: str, output_root: Path) -> None:
    output_root = output_root.expanduser().resolve()
    roots = (output_root, render_staging_root(output_root)) if mode == "render" else (output_root,)
    for root in roots:
        if root.exists():
            if not root.is_dir():
                raise FileExistsError(f"eval output root is not a directory: {root}")
            if mode == "render":
                raise FileExistsError(f"{mode} eval refuses existing final/staging target: {root}")
            existing = sorted(path.name for path in root.iterdir())
            if existing:
                raise FileExistsError(
                    f"{mode} eval refuses to overwrite non-empty output root {root}: {existing}"
                )
    runtime_log_root = eval_runtime_log_root(mode, output_root)
    if runtime_log_root.exists():
        raise FileExistsError(
            f"{mode} eval refuses existing Hydra runtime-log root: {runtime_log_root}"
        )


def required_final_artifact_path(mode: str, output_root: Path) -> Path:
    if mode not in {"formal", "render"}:
        raise ValueError(f"unknown eval mode {mode!r}")
    output_root = output_root.expanduser().resolve()
    filename = "student_selection.json" if mode == "formal" else "selected_render_metadata.json"
    return output_root / filename


def validate_final_artifact(mode: str, output_root: Path) -> Path:
    artifact = required_final_artifact_path(mode, output_root)
    if not artifact.is_file():
        raise RuntimeError(
            f"{mode} eval returned without required final artifact: {artifact}"
        )
    return artifact


def run_eval_entry_with_artifact_guard(mode: str, output_root: Path) -> None:
    """Run the evaluation entry while guarding its successful hard exit."""
    original_exit = os._exit

    def guarded_exit(status: int) -> None:
        if status == 0:
            validate_final_artifact(mode, output_root)
        original_exit(status)

    os._exit = guarded_exit
    try:
        runpy.run_path(str(EVAL_ENTRY), run_name="__main__")
    finally:
        os._exit = original_exit


def main() -> int:
    args = parse_args()
    output_root = args.output_root.expanduser().resolve()
    validate_output_root_preflight(args.mode, output_root)
    checkpoint_info = validate_checkpoint_artifacts()
    runtime = load_runtime_bootstrap_module()

    overlay = runtime.prepare_overlay_import(args.overlay_repository)
    runtime.validate_gpu7_environment()
    module_sources = runtime.validate_runtime_repository(args.runtime_repository)
    already_loaded = sorted(set(module_sources).intersection(sys.modules))
    if already_loaded:
        raise RuntimeError(f"v19 runtime modules imported before AppLauncher: {already_loaded}")
    runtime.install_v19_runtime_scenario_file_pin(module_sources)
    sys.meta_path.insert(0, runtime.V19RuntimeFinder(module_sources))
    os.chdir(overlay)

    selection = None
    if args.mode == "render":
        selection, _ = load_sealed_selection(args.selection_json, args.source_metrics)
    overrides = build_hydra_overrides(args.mode, output_root)
    from gr00t.rl.trl.trainer.ppo_trainer_a2_base_api import TRLPPOTrainer as A2TRLPPOTrainer

    trainer_cls, a2_eval = _bind_a2_eval_methods()
    if args.mode == "formal":
        trainer_cls.eval = _make_formal_eval(a2_eval, output_root, checkpoint_info)
    else:
        trainer_cls.eval = _make_render_eval(
            a2_eval,
            output_root,
            selection,
            args.selection_json.expanduser().resolve(strict=True),
        )

    import argparse as _argparse
    import isaaclab.app as isaaclab_app
    from gr00t.rl import train_agent_trl as gpu_binding

    identity = gpu_binding.A2_GPU_BINDING
    if identity is None:
        raise RuntimeError("A2 GPU binding environment is required for Student eval")
    launcher_holder: dict[str, Any] = {}
    bound = gpu_binding._make_a2_bound_app_launcher_type(isaaclab_app.AppLauncher, identity)

    class VerifiedAppLauncher(bound):
        def __init__(self, *positional, **keyword):
            if len(positional) != 1 or keyword or not isinstance(positional[0], _argparse.Namespace):
                raise TypeError("A2 eval AppLauncher requires one argparse.Namespace")
            cli = positional[0]
            cli.multi_gpu = False
            cli.distributed = False
            cli.device = "cuda:0"
            super().__init__(*positional, **keyword)
            launcher_holder["instance"] = self

    isaaclab_app.AppLauncher = VerifiedAppLauncher
    import accelerate

    original_accelerator = accelerate.Accelerator

    class VerifiedAccelerator(original_accelerator):
        def __init__(self, *positional, **keyword):
            super().__init__(*positional, **keyword)
            gpu_binding._validate_a2_accelerator_binding(self, identity)
            launcher = launcher_holder.get("instance")
            if launcher is None:
                raise RuntimeError("A2 eval Accelerator initialized before AppLauncher")
            gpu_binding._validate_a2_app_launcher_binding(launcher, self, identity)

    accelerate.Accelerator = VerifiedAccelerator
    sys.argv = [str(EVAL_ENTRY), *overrides]
    run_eval_entry_with_artifact_guard(args.mode, output_root)
    validate_final_artifact(args.mode, output_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
