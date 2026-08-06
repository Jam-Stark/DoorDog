#!/usr/bin/env python3
"""Current-worktree C-B2H ToeOut6 Student eval and selected render runner.

The runner has three explicit modes:

``formal``
    Evaluate exactly one Student-controlled episode in each of 16 environments,
    then seal ``formal_student_metrics.json`` and ``student_selection.json``.

``render``
    Consume a hash-validated sealed selection and replay only that case while
    writing the selected Student policy's left D435, right D435, OEM Head and
    D435 left/right side-by-side videos.

``full``
    Run ``formal`` and ``render`` in fresh child processes below one fresh root.

The wrapper deliberately resolves the current worktree before importing
``gr00t``.  It does not install a runtime import redirect: the three
IsaacLab-sensitive source modules are pinned by absolute path and SHA-256 and
their loaded module identities are checked again before artifacts are sealed.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import hashlib
import importlib
import importlib.util
import json
import math
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
EVAL_ENTRY = (REPO_ROOT / "gr00t/rl/eval_agent_trl.py").resolve(strict=True)
KIT_SOURCE = (REPO_ROOT / "gr00t/rl/apps/phc.isaaclab.python.headless.rendering.kit").resolve(strict=True)

EXPECTED_GLOBAL_STEP = 8000
EXPECTED_SEED = 0
EXPECTED_NUM_ENVS = 16
EXPECTED_EPISODES = 16
ARCHITECTURE_ID = "C-B2H-DUALRAW-SHAREDENC-TOEOUT6-V19-P2"
ACTOR_TARGET_SUFFIX = "DualD435HeadVisionRecurrentToeOut6Actor"
FORMAL_RANKING_ORDER = "goal_reached_desc,max_stage_desc,reward_desc,env_id_asc"
VIDEO_FPS = 20

RUNTIME_MODULES = {
    "gr00t.rl.envs.door.door_open_a2_base": REPO_ROOT / "gr00t/rl/envs/door/door_open_a2_base.py",
    "gr00t.rl.data.tasks.door.scenario_cfg.isaacsim": REPO_ROOT / "gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py",
    "gr00t.rl.isaac_utils.playground.env_rand.door": REPO_ROOT / "gr00t/rl/isaac_utils/playground/env_rand/door.py",
}
RANDOMIZED_CASE_KEYS = (
    "door_hinge_drive_max_force",
    "door_handle_drive_max_force",
    "door_handle_height",
    "door_weight",
)
OUTCOME_KEYS = ("goal_reached", "max_stage", "terminal_reason", "reward")
METRICS_SCHEMA = "a2_toeout6_student_metrics_v1"
SELECTION_SCHEMA = "a2_toeout6_student_selection_v1"
RENDER_SCHEMA = "a2_toeout6_student_render_v1"
SOURCE_SHA256 = {
    str(path.relative_to(REPO_ROOT)): None for path in RUNTIME_MODULES.values()
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError(f"non-finite value cannot be serialized: {value!r}")
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    item = getattr(value, "item", None)
    if callable(item):
        return json_safe(item())
    tolist = getattr(value, "tolist", None)
    if callable(tolist):
        return json_safe(tolist())
    raise TypeError(f"unsupported JSON value type: {type(value).__name__}")


def atomic_json_write(path: Path, value: Mapping[str, Any]) -> None:
    path = path.expanduser().resolve()
    if path.exists():
        raise FileExistsError(f"refusing to overwrite sealed artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.writing")
    if temporary.exists():
        raise FileExistsError(f"temporary artifact already exists: {temporary}")
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            json.dump(json_safe(value), stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        if temporary.exists():
            temporary.unlink()
        raise


def _workspace_path(value: Path, *, must_exist: bool = False) -> Path:
    path = value.expanduser().resolve(strict=must_exist)
    if not path.is_relative_to(REPO_ROOT):
        raise ValueError(f"path must remain inside the current worktree: {path}")
    return path


def _runtime_source_identity() -> dict[str, dict[str, str]]:
    identity: dict[str, dict[str, str]] = {}
    for module_name, path in RUNTIME_MODULES.items():
        source = path.resolve(strict=True)
        if not source.is_relative_to(REPO_ROOT) or not source.is_file():
            raise FileNotFoundError(f"required worktree module is unavailable: {source}")
        identity[module_name] = {
            "path": str(source),
            "relative_path": str(source.relative_to(REPO_ROOT)),
            "sha256": sha256_file(source),
        }
    return identity


def _module_locations(module_name: str, module: Any) -> list[Path]:
    locations: list[Path] = []
    module_file = getattr(module, "__file__", None)
    if module_file:
        locations.append(Path(module_file).expanduser().resolve(strict=True))
    module_path = getattr(module, "__path__", None)
    if module_path is not None:
        locations.extend(Path(item).expanduser().resolve(strict=True) for item in module_path)
    if not locations:
        raise RuntimeError(f"loaded module has no verifiable source path: {module_name}")
    return locations


def validate_worktree_import_preflight() -> dict[str, dict[str, str]]:
    """Reject preloaded/alternate package sources before importing ``gr00t``."""
    expected_root = (REPO_ROOT / "gr00t").resolve(strict=True)
    preloaded = sorted(
        name for name in sys.modules if name == "gr00t" or name.startswith("gr00t.")
    )
    if preloaded:
        raise RuntimeError(
            "current-worktree eval requires gr00t to be unloaded before import; "
            f"preloaded={preloaded}"
        )
    alternate_entries: list[str] = []
    for entry in sys.path:
        candidate_root = Path.cwd() if entry in ("", None) else Path(entry).expanduser()
        try:
            candidate = (candidate_root / "gr00t").resolve()
        except OSError:
            continue
        if candidate.is_dir() and candidate != expected_root:
            alternate_entries.append(str(candidate))
    if alternate_entries:
        raise RuntimeError(
            "alternate gr00t package roots are visible before current-worktree import: "
            f"{sorted(set(alternate_entries))}"
        )
    spec = importlib.util.find_spec("gr00t")
    if spec is None or spec.origin in (None, "built-in"):
        raise ImportError("current-worktree gr00t package cannot be resolved")
    origin = Path(spec.origin).resolve(strict=True)
    if not origin.is_relative_to(expected_root):
        raise RuntimeError(
            "gr00t package resolves outside the current worktree: "
            f"origin={origin} expected_under={expected_root}"
        )
    sys.path.insert(0, str(REPO_ROOT))
    return _runtime_source_identity()


def verify_loaded_runtime_sources(identity: Mapping[str, Mapping[str, str]]) -> None:
    """Import and verify the exact three current-worktree runtime modules."""
    for module_name, expected in identity.items():
        module = importlib.import_module(module_name)
        locations = _module_locations(module_name, module)
        expected_path = Path(str(expected["path"])).resolve(strict=True)
        if locations != [expected_path]:
            raise RuntimeError(
                f"runtime module source identity mismatch for {module_name}: "
                f"loaded={locations} expected={[expected_path]}"
            )
        actual_sha = sha256_file(expected_path)
        if actual_sha != expected["sha256"]:
            raise RuntimeError(
                f"runtime module changed after preflight for {module_name}: "
                f"expected={expected['sha256']} got={actual_sha}"
            )


def _read_yaml(path: Path) -> Mapping[str, Any]:
    import yaml

    with path.open(encoding="utf-8") as stream:
        value = yaml.safe_load(stream)
    if not isinstance(value, Mapping):
        raise TypeError(f"checkpoint config must be a YAML mapping: {path}")
    return value


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping; got {type(value).__name__}")
    return value


def validate_checkpoint_and_config(
    checkpoint: Path,
    expected_global_step: int,
    config_override: Path | None = None,
    expected_checkpoint_sha256: str | None = None,
    expected_config_sha256: str | None = None,
) -> dict[str, Any]:
    if isinstance(expected_global_step, bool) or expected_global_step != EXPECTED_GLOBAL_STEP:
        raise ValueError(
            f"expected global step must be exactly {EXPECTED_GLOBAL_STEP}; got {expected_global_step!r}"
        )
    checkpoint = _workspace_path(checkpoint, must_exist=True)
    if checkpoint.name != f"model_step_{EXPECTED_GLOBAL_STEP:06d}.pt":
        raise ValueError(
            "checkpoint filename must encode the required global step: "
            f"model_step_{EXPECTED_GLOBAL_STEP:06d}.pt; got {checkpoint.name!r}"
        )
    config_path = checkpoint.with_name("config.yaml")
    if config_override is not None:
        requested = _workspace_path(config_override, must_exist=True)
        if requested != config_path:
            raise ValueError(
                "checkpoint config must be the adjacent config.yaml: "
                f"expected={config_path} got={requested}"
            )
    checkpoint_sha = sha256_file(checkpoint)
    config_sha = sha256_file(config_path)
    for name, value in (
        ("checkpoint", expected_checkpoint_sha256),
        ("config", expected_config_sha256),
    ):
        if value is not None:
            if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
                raise ValueError(f"{name} SHA256 must be lowercase hexadecimal")
            actual = checkpoint_sha if name == "checkpoint" else config_sha
            if actual != value:
                raise RuntimeError(f"{name} SHA256 mismatch: expected={value} got={actual}")

    import torch

    payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
    if not isinstance(payload, Mapping):
        raise TypeError("Student checkpoint payload must be a mapping")
    policy = payload.get("policy_state_dict")
    if not isinstance(policy, Mapping) or not policy:
        raise KeyError("Student checkpoint must contain a non-empty policy_state_dict")
    tensor_count = 0
    for name, tensor in policy.items():
        if not torch.is_tensor(tensor):
            raise TypeError(f"Student policy tensor {name!r} is not a torch.Tensor")
        tensor_count += 1
        if (tensor.is_floating_point() or tensor.is_complex()) and not bool(
            torch.all(torch.isfinite(tensor)).item()
        ):
            raise RuntimeError(f"Student policy tensor {name!r} contains non-finite values")
    state = payload.get("state")
    global_step = getattr(state, "global_step", None)
    if global_step is None and isinstance(state, Mapping):
        global_step = state.get("global_step")
    if isinstance(global_step, bool) or not isinstance(global_step, int):
        raise RuntimeError("Student checkpoint state.global_step is missing or non-integer")
    if global_step != expected_global_step:
        raise RuntimeError(
            f"Student checkpoint state.global_step mismatch: expected={expected_global_step} got={global_step}"
        )

    config = _read_yaml(config_path)
    algo = _mapping(config.get("algo"), "algo")
    algo_config = _mapping(algo.get("config"), "algo.config")
    actor = _mapping(algo_config.get("actor"), "algo.config.actor")
    actor_target = actor.get("_target_")
    if not isinstance(actor_target, str) or not actor_target.endswith(ACTOR_TARGET_SUFFIX):
        raise RuntimeError(
            "checkpoint architecture must be ToeOut6: "
            f"expected suffix={ACTOR_TARGET_SUFFIX!r} got={actor_target!r}"
        )
    view_contract = _mapping(actor.get("view_contract"), "algo.config.actor.view_contract")
    if view_contract.get("d435i_forward_mode") != "packed":
        raise RuntimeError("ToeOut6 Student checkpoint requires packed D435 forwarding")
    if int(view_contract.get("camera_meta_dim", -1)) != 6:
        raise RuntimeError("ToeOut6 Student checkpoint requires camera_meta_dim=6")
    if algo_config.get("use_a2_base") is not True:
        raise RuntimeError("ToeOut6 Student checkpoint requires the frozen A2_Base controller")
    if int(algo_config.get("student_action_dim", -1)) != 12:
        raise RuntimeError("ToeOut6 Student checkpoint requires a 12D high-level action")
    if int(algo_config.get("rollout_action_dim", -1)) != 24:
        raise RuntimeError("ToeOut6 Student checkpoint requires a 24D rollout action")

    simulator = _mapping(config.get("simulator"), "simulator")
    simulator_config = _mapping(simulator.get("config"), "simulator.config")
    cameras = _mapping(simulator_config.get("cameras"), "simulator.config.cameras")
    if cameras.get("architecture_id") != ARCHITECTURE_ID:
        raise RuntimeError("ToeOut6 camera architecture identity drifted")
    multiview = _mapping(cameras.get("policy_multiview"), "simulator.config.cameras.policy_multiview")
    if multiview.get("enabled") is not True or multiview.get("architecture_id") != ARCHITECTURE_ID:
        raise RuntimeError("ToeOut6 packed D435 policy_multiview contract is missing")
    if multiview.get("layout") != "channel_stacked_raw_rgb":
        raise RuntimeError("ToeOut6 policy_multiview layout must be channel_stacked_raw_rgb")
    if list(multiview.get("output_shape", ())) != [384, 216, 6]:
        raise RuntimeError("ToeOut6 policy_multiview output_shape must be [384,216,6]")
    if list(multiview.get("view_order", ())) != ["left", "right"]:
        raise RuntimeError("ToeOut6 policy_multiview view order must be left,right")
    context = _mapping(multiview.get("context"), "policy_multiview.context")
    if list(context.get("resolution", ())) != [136, 384]:
        raise RuntimeError("ToeOut6 OEM Head context resolution must be [136,384]")
    camera_meta = _mapping(multiview.get("camera_meta"), "policy_multiview.camera_meta")
    if camera_meta.get("enabled") is not True or list(camera_meta.get("order", ())) != [
        "left_age_normalized",
        "right_age_normalized",
        "head_age_normalized",
        "left_valid",
        "right_valid",
        "head_valid",
    ]:
        raise RuntimeError("ToeOut6 camera_meta order/enable contract drifted")

    obs = _mapping(config.get("obs"), "obs")
    obs_dict = _mapping(obs.get("obs_dict"), "obs.obs_dict")
    if list(obs_dict.get("vision_obs", ())) != ["rgb_image"]:
        raise RuntimeError("ToeOut6 vision_obs contract drifted")
    if list(obs_dict.get("context_vision_obs", ())) != ["context_rgb_image"]:
        raise RuntimeError("ToeOut6 context_vision_obs contract drifted")
    if list(obs_dict.get("camera_meta", ())) != ["camera_meta"]:
        raise RuntimeError("ToeOut6 camera_meta observation contract drifted")
    return {
        "path": str(checkpoint),
        "sha256": checkpoint_sha,
        "config_path": str(config_path),
        "config_sha256": config_sha,
        "global_step": int(global_step),
        "policy_tensor_count": tensor_count,
        "architecture_id": ARCHITECTURE_ID,
        "actor_target": actor_target,
        "camera_contract": {
            "d435i_forward_mode": "packed",
            "d435_shape": [384, 216, 3],
            "packed_policy_shape": [384, 216, 6],
            "head_shape": [136, 384, 3],
            "camera_meta_dim": 6,
        },
    }


def _contract() -> dict[str, Any]:
    return {
        "controller": "student",
        "seed": EXPECTED_SEED,
        "num_envs": EXPECTED_NUM_ENVS,
        "one_episode_per_env": True,
        "enforce_teacher_rollout": False,
        "ratio_teacher_rollout": 0.0,
        "pure_student": True,
        "use_a2_base": True,
        "architecture_id": ARCHITECTURE_ID,
        "d435i_forward_mode": "packed",
        "ranking_order": FORMAL_RANKING_ORDER,
    }


def _validate_effective_eval_contract(config: Mapping[str, Any], policy_model: Any) -> None:
    if config.get("enforce_teacher_rollout") is not False:
        raise RuntimeError("formal Student eval requires enforce_teacher_rollout=false")
    if float(config.get("ratio_teacher_rollout", -1.0)) != 0.0:
        raise RuntimeError("formal Student eval requires ratio_teacher_rollout=0.0")
    if config.get("use_a2_base") is not True:
        raise RuntimeError("formal Student eval requires frozen A2_Base")
    eval_config = _mapping(config.get("eval"), "effective Student eval config")
    if eval_config.get("eval_num_envs_episodes") is not True:
        raise RuntimeError("formal Student eval requires one first episode per environment")
    if int(eval_config.get("num_eval_episodes", -1)) != EXPECTED_EPISODES:
        raise RuntimeError("formal Student eval requires num_eval_episodes=16")
    if eval_config.get("a2_diagnostic_trace_enabled", False) is not False:
        raise RuntimeError("formal Student eval forbids diagnostic action interventions")
    if eval_config.get("a2_forced_gripper_close_enabled", False) is not False:
        raise RuntimeError("formal Student eval forbids forced gripper-close intervention")
    actor_mode = getattr(policy_model, "d435i_forward_mode", None)
    if actor_mode != "packed":
        raise RuntimeError(f"instantiated ToeOut6 policy mode drifted: {actor_mode!r}")


def build_overrides(mode: str, output_root: Path, checkpoint: Path) -> list[str]:
    if mode not in {"formal", "render"}:
        raise ValueError(f"child eval mode must be formal or render; got {mode!r}")
    output_root = output_root.resolve()
    runtime_root = output_root.with_name(f".{output_root.name}.runtime")
    overrides = [
        f"checkpoint={checkpoint.resolve()}",
        "+seed=0",
        "+num_envs=16",
        "+headless=true",
        "+use_wandb=false",
        "+auto_load_latest=false",
        "+checkpoint_load_mode=full",
        "+algo.config.enforce_teacher_rollout=false",
        "+algo.config.ratio_teacher_rollout=0.0",
        "+algo.config.use_a2_base=true",
        "+algo.config.actor.view_contract.d435i_forward_mode=packed",
        "+algo.config.eval.eval_num_envs_episodes=true",
        "algo.config.eval.num_eval_episodes=16",
        "+algo.config.eval.a2_diagnostic_trace_enabled=false",
        "+algo.config.eval.a2_forced_gripper_close_enabled=false",
        "+algo.config.eval.dump_to_log_metrics=false",
        "+algo.config.eval.save_videos=false",
        "+algo.config.eval.save_trajectories=false",
        "+simulator.config.render_results=false",
        f"eval_output_dir={output_root}",
        f"eval_log_dir={runtime_root}",
    ]
    required = {
        "seed": "0",
        "num_envs": "16",
        "algo.config.enforce_teacher_rollout": "false",
        "algo.config.ratio_teacher_rollout": "0.0",
        "algo.config.actor.view_contract.d435i_forward_mode": "packed",
        "algo.config.eval.eval_num_envs_episodes": "true",
        "algo.config.eval.num_eval_episodes": "16",
        "simulator.config.render_results": "false",
        "eval_output_dir": str(output_root),
        "eval_log_dir": str(runtime_root),
    }
    for key, expected in required.items():
        values = [
            (token[1:] if token.startswith("+") else token).split("=", 1)[1]
            for token in overrides
            if (token[1:] if token.startswith("+") else token).startswith(f"{key}=")
        ]
        if values != [expected]:
            raise RuntimeError(f"override contract drift for {key}: {values!r}")
    return overrides


def capture_reset_case_table(env: Any) -> dict[int, dict[str, Any]]:
    """Read the exact spawn metadata used by the current DoorPregrasp env.

    The two drive-force values are authored only in the door prim's custom
    metadata; no high-level env accessor exposes them.  This is a read-only
    diagnostic identity read, not scene construction or mutation.
    """
    if int(getattr(env, "num_envs", -1)) != EXPECTED_NUM_ENVS:
        raise RuntimeError("reset case table requires exactly 16 environments")
    import omni.usd

    stage = omni.usd.get_context().get_stage()
    table: dict[int, dict[str, Any]] = {}
    metadata_map = {
        "door_hinge_drive_max_force": "hingeDriveMaxForce",
        "door_handle_drive_max_force": "handleDriveMaxForce",
        "door_handle_height": "doorHandleHeight",
        "door_weight": "doorWeight",
    }
    for env_id in range(EXPECTED_NUM_ENVS):
        prim = stage.GetPrimAtPath(f"/World/envs/env_{env_id}/door")
        if not prim or not prim.IsValid():
            raise RuntimeError(f"current env door prim is missing for env_id={env_id}")
        metadata = prim.GetMetadata("customData")
        if not isinstance(metadata, Mapping):
            raise RuntimeError(f"door customData is unavailable for env_id={env_id}")
        case: dict[str, Any] = {}
        for key, metadata_key in metadata_map.items():
            if metadata_key not in metadata:
                raise KeyError(
                    f"door customData missing reset identity field {metadata_key!r} for env_id={env_id}"
                )
            value = json_safe(metadata[metadata_key])
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"reset identity {key} must be numeric; got {value!r}")
            if not math.isfinite(float(value)):
                raise ValueError(f"reset identity {key} must be finite; got {value!r}")
            case[key] = float(value)
        table[env_id] = case
    return table


def _diagnostic_semantics(goal: Any, stage: Any, reason: Any) -> dict[str, Any]:
    if not isinstance(goal, bool):
        raise TypeError(f"goal_reached must be bool; got {goal!r}")
    if isinstance(stage, bool) or not isinstance(stage, int):
        stage = int(stage)
    if not isinstance(reason, str) or not reason:
        raise ValueError(f"terminal_reason must be a non-empty string; got {reason!r}")
    return {"goal_reached": goal, "max_stage": int(stage), "terminal_reason": reason}


def episode_records(metrics: Mapping[str, Any], case_table: Mapping[int, Mapping[str, Any]]) -> list[dict[str, Any]]:
    required = (
        "episode_rewards",
        "episode_goal_reached",
        "episode_max_stage_reached",
        "episode_terminal_reasons",
        "episode_terminal_diagnostics",
    )
    missing = [key for key in required if key not in metrics]
    if missing:
        raise KeyError(f"eval metrics missing required fields: {missing}")
    lengths = [len(metrics[key]) for key in required]
    if len(set(lengths)) != 1 or lengths[0] != EXPECTED_EPISODES:
        raise RuntimeError(f"expected 16 aligned first-episode entries; lengths={lengths}")
    records: list[dict[str, Any]] = []
    seen: set[int] = set()
    for index in range(EXPECTED_EPISODES):
        diagnostic = json_safe(metrics["episode_terminal_diagnostics"][index])
        diagnostic = _mapping(diagnostic, f"episode_terminal_diagnostics[{index}]")
        env_id = diagnostic.get("env_id")
        if isinstance(env_id, bool) or not isinstance(env_id, int):
            raise TypeError(f"terminal diagnostic env_id must be an integer; got {env_id!r}")
        if env_id in seen or env_id not in range(EXPECTED_NUM_ENVS):
            raise RuntimeError(f"terminal diagnostic env_id is not unique/in-range: {env_id}")
        seen.add(env_id)
        if env_id not in case_table:
            raise KeyError(f"reset case table has no env_id={env_id}")
        semantics = _diagnostic_semantics(
            bool(metrics["episode_goal_reached"][index]),
            int(metrics["episode_max_stage_reached"][index]),
            metrics["episode_terminal_reasons"][index],
        )
        reward = float(metrics["episode_rewards"][index])
        if not math.isfinite(reward):
            raise ValueError(f"episode reward must be finite; got {reward!r}")
        records.append(
            {
                "env_id": env_id,
                "episode_index": 0,
                "reward": reward,
                **semantics,
                "randomized_case": json_safe(case_table[env_id]),
                "terminal_diagnostic": dict(diagnostic),
            }
        )
    if seen != set(range(EXPECTED_NUM_ENVS)):
        raise RuntimeError(f"eval did not return one record per env: {sorted(seen)}")
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


def seal_formal_artifacts(
    output_root: Path,
    checkpoint_info: Mapping[str, Any],
    source_identity: Mapping[str, Mapping[str, str]],
    metrics: Mapping[str, Any],
    case_table: Mapping[int, Mapping[str, Any]],
) -> dict[str, Any]:
    records = episode_records(json_safe(metrics), case_table)
    ranked = rank_episode_records(records)
    contract = _contract()
    safe_checkpoint = json_safe(checkpoint_info)
    safe_sources = json_safe(source_identity)
    metrics_payload = {
        "schema": METRICS_SCHEMA,
        "controller": "student",
        "training_performed": False,
        "optimizer_step_count": 0,
        "checkpoint": safe_checkpoint,
        "worktree_sources": safe_sources,
        "case_seed": EXPECTED_SEED,
        "contract": contract,
        "case_table": [
            {"env_id": env_id, "randomized_case": json_safe(case_table[env_id])}
            for env_id in sorted(case_table)
        ],
        "episodes": records,
    }
    metrics_path = output_root / "formal_student_metrics.json"
    atomic_json_write(metrics_path, metrics_payload)
    selected = ranked[0]
    selection = {
        "schema": SELECTION_SCHEMA,
        "controller": "student",
        "training_performed": False,
        "checkpoint": safe_checkpoint,
        "worktree_sources": safe_sources,
        "case_seed": EXPECTED_SEED,
        "contract": contract,
        "ranking": {"order": FORMAL_RANKING_ORDER, "records": ranked},
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
            "path": str(metrics_path.resolve()),
            "sha256": sha256_file(metrics_path),
        },
    }
    selection_path = output_root / "student_selection.json"
    atomic_json_write(selection_path, selection)
    return selection


def _require_source_identity(selection: Mapping[str, Any], current: Mapping[str, Mapping[str, str]]) -> None:
    expected = selection.get("worktree_sources")
    if not isinstance(expected, Mapping) or canonical_json(expected) != canonical_json(current):
        raise RuntimeError("sealed selection worktree module identity differs from current sources")


def load_sealed_selection(
    selection_path: Path,
    checkpoint_info: Mapping[str, Any],
    source_identity: Mapping[str, Mapping[str, str]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    selection_path = _workspace_path(selection_path, must_exist=True)
    with selection_path.open(encoding="utf-8") as stream:
        selection = json.load(stream)
    if not isinstance(selection, Mapping) or selection.get("schema") != SELECTION_SCHEMA:
        raise ValueError("unsupported or malformed Student selection schema")
    if selection.get("controller") != "student" or selection.get("case_seed") != EXPECTED_SEED:
        raise RuntimeError("sealed selection Student/seed contract drifted")
    if selection.get("contract") != _contract():
        raise RuntimeError("sealed selection formal Student contract drifted")
    if selection.get("checkpoint") != json_safe(checkpoint_info):
        raise RuntimeError("sealed selection checkpoint identity differs from supplied checkpoint")
    _require_source_identity(selection, source_identity)
    source = _mapping(selection.get("source_metrics"), "selection.source_metrics")
    source_path = _workspace_path(Path(str(source.get("path", ""))), must_exist=True)
    if sha256_file(source_path) != source.get("sha256"):
        raise RuntimeError("sealed source metrics hash validation failed")
    with source_path.open(encoding="utf-8") as stream:
        metrics = json.load(stream)
    if not isinstance(metrics, Mapping) or metrics.get("schema") != METRICS_SCHEMA:
        raise RuntimeError("sealed source metrics schema drifted")
    if metrics.get("checkpoint") != selection.get("checkpoint"):
        raise RuntimeError("sealed source metrics checkpoint identity drifted")
    _require_source_identity(metrics, source_identity)
    ranking = _mapping(selection.get("ranking"), "selection.ranking")
    if ranking.get("order") != FORMAL_RANKING_ORDER:
        raise RuntimeError("sealed selection ranking order drifted")
    records = ranking.get("records")
    if not isinstance(records, list) or len(records) != EXPECTED_EPISODES:
        raise RuntimeError("sealed selection ranking must contain exactly 16 records")
    source_records = metrics.get("episodes")
    if not isinstance(source_records, list) or canonical_json(rank_episode_records(source_records)) != canonical_json(records):
        raise RuntimeError("sealed selection ranking does not match source metrics")
    selected = _mapping(selection.get("selected"), "selection.selected")
    top = records[0]
    for key in ("env_id", "episode_index", "goal_reached", "max_stage", "terminal_reason", "randomized_case"):
        if selected.get(key) != top.get(key):
            raise RuntimeError(f"sealed selected case does not match canonical ranking for {key}")
    if selected.get("reward") != top.get("reward"):
        raise RuntimeError("sealed selected case reward does not match canonical ranking")
    return dict(selection), dict(metrics)


def _selected_record(selection: Mapping[str, Any]) -> dict[str, Any]:
    selected = _mapping(selection.get("selected"), "selection.selected")
    ranking = _mapping(selection.get("ranking"), "selection.ranking")
    records = ranking.get("records")
    matches = [
        record
        for record in records
        if isinstance(record, Mapping)
        and record.get("env_id") == selected.get("env_id")
        and record.get("episode_index") == selected.get("episode_index")
        and record.get("randomized_case") == selected.get("randomized_case")
    ]
    if len(matches) != 1:
        raise RuntimeError(f"sealed selection must identify exactly one selected record; got {len(matches)}")
    return dict(matches[0])


def validate_replay_case(
    selection: Mapping[str, Any],
    replay_metrics: Mapping[str, Any],
    replay_case_table: Mapping[int, Mapping[str, Any]],
) -> dict[str, Any]:
    source = _selected_record(selection)
    records = episode_records(json_safe(replay_metrics), replay_case_table)
    replay = next((record for record in records if record["env_id"] == source["env_id"]), None)
    if replay is None or replay["episode_index"] != source["episode_index"]:
        raise RuntimeError("selected replay did not return the sealed env/episode")
    if replay["randomized_case"] != source["randomized_case"]:
        raise RuntimeError(
            "selected replay reset identity differs from formal selection: "
            f"source={source['randomized_case']!r} replay={replay['randomized_case']!r}"
        )
    source_outcome = {key: source[key] for key in OUTCOME_KEYS}
    replay_outcome = {key: replay[key] for key in OUTCOME_KEYS}
    return {
        "case_identity": {
            "env_id": source["env_id"],
            "episode_index": source["episode_index"],
            "randomized_case": source["randomized_case"],
        },
        "source_formal_outcome": source_outcome,
        "replay_outcome": replay_outcome,
        "outcome_drift": {
            key: {
                "source": source_outcome[key],
                "replay": replay_outcome[key],
                "changed": source_outcome[key] != replay_outcome[key],
            }
            for key in OUTCOME_KEYS
        },
    }


def _inverse_normalize(normalized: Any, image_mean: Sequence[float], image_std: Sequence[float], name: str):
    import torch

    if not torch.is_tensor(normalized) or normalized.dtype != torch.float32:
        raise RuntimeError(f"{name} must be float32; got {getattr(normalized, 'dtype', None)}")
    if not bool(torch.all(torch.isfinite(normalized)).item()):
        raise RuntimeError(f"{name} contains non-finite values")
    mean = torch.as_tensor(list(image_mean), dtype=torch.float32, device=normalized.device)
    std = torch.as_tensor(list(image_std), dtype=torch.float32, device=normalized.device)
    if tuple(mean.shape) != (3,) or tuple(std.shape) != (3,) or bool(torch.any(std <= 0).item()):
        raise RuntimeError("camera image mean/std contract is invalid")
    raw_float = (normalized * std + mean) * 255.0
    rounded = torch.round(raw_float)
    if bool(torch.any(torch.abs(raw_float - rounded) > 2.0e-3).item()):
        raise RuntimeError(f"{name} does not have an integer uint8 normalization round-trip")
    if bool(torch.any(rounded < 0).item()) or bool(torch.any(rounded > 255).item()):
        raise RuntimeError(f"{name} escaped uint8 range")
    return rounded.to(torch.uint8)


def derive_raw_policy_frames(obs_dict: Mapping[str, Any], cameras_config: Mapping[str, Any]):
    import torch
    from gr00t.rl.utils.a2_policy_camera import (
        compose_channel_stacked_dual_rgb,
        normalize_head_context_rgb,
    )

    vision = obs_dict.get("vision_obs")
    context = obs_dict.get("context_vision_obs")
    meta = obs_dict.get("camera_meta")
    expected = {
        "vision_obs": (EXPECTED_NUM_ENVS, 384, 216, 6),
        "context_vision_obs": (EXPECTED_NUM_ENVS, 136, 384, 3),
        "camera_meta": (EXPECTED_NUM_ENVS, 6),
    }
    for name, value in (("vision_obs", vision), ("context_vision_obs", context), ("camera_meta", meta)):
        if not torch.is_tensor(value) or tuple(value.shape) != expected[name] or value.dtype != torch.float32:
            raise RuntimeError(f"{name} contract drift: expected {expected[name]} float32")
        if not bool(torch.all(torch.isfinite(value)).item()):
            raise RuntimeError(f"{name} contains non-finite values")
    mean = list(cameras_config["image_mean"])
    std = list(cameras_config["image_std"])
    left = _inverse_normalize(vision[..., :3], mean, std, "vision_obs.left")
    right = _inverse_normalize(vision[..., 3:6], mean, std, "vision_obs.right")
    head = _inverse_normalize(context, mean, std, "context_vision_obs.head")
    recomposed = compose_channel_stacked_dual_rgb(
        left, right, resolution=(384, 216), image_mean=mean, image_std=std
    )
    if not torch.equal(recomposed, vision):
        raise RuntimeError("raw left/right frames do not recompose packed vision_obs")
    if not torch.equal(
        normalize_head_context_rgb(head, resolution=(136, 384), image_mean=mean, image_std=std),
        context,
    ):
        raise RuntimeError("raw Head frame does not recompose context_vision_obs")
    return left, right, head, meta


def _render_staging_root(output_root: Path) -> Path:
    return output_root.with_name(f".{output_root.name}.writing")


def _temporary_video_path(path: Path) -> Path:
    return path.with_name(f".{path.stem}.writing{path.suffix}")


def _validate_video(path: Path, frame_count: int, shape: Sequence[int]) -> dict[str, Any]:
    if not path.is_file() or path.stat().st_size <= 0:
        raise RuntimeError(f"rendered video is missing or empty: {path}")
    if frame_count <= 0:
        raise RuntimeError(f"rendered video has no frames: {path}")
    return {
        "path": str(path),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "frame_count": frame_count,
        "shape": list(shape),
        "fps": VIDEO_FPS,
    }


def make_formal_eval(
    base_eval: Any,
    output_root: Path,
    checkpoint_info: Mapping[str, Any],
    source_identity: Mapping[str, Mapping[str, str]],
):
    def formal_eval(self):
        _validate_effective_eval_contract(self.config, self.policy_model)
        if int(self.env.num_envs) != EXPECTED_NUM_ENVS:
            raise RuntimeError("formal Student eval requires exactly 16 environments")
        case_table = capture_reset_case_table(self.env)
        result = base_eval(self)
        metrics = result if isinstance(result, Mapping) else self.env.get_eval_metrics_summary()
        verify_loaded_runtime_sources(source_identity)
        selection = seal_formal_artifacts(
            output_root,
            checkpoint_info,
            source_identity,
            metrics,
            case_table,
        )
        print(
            "[A2_TOEOUT6_STUDENT_FORMAL_PASS] "
            f"selected_env={selection['selected']['env_id']} output={output_root}",
            flush=True,
        )
        return result

    formal_eval.__name__ = "toeout6_student_formal_eval"
    formal_eval.__qualname__ = "toeout6_student_formal_eval"
    formal_eval._a2_eval_base = base_eval
    return formal_eval


def make_render_eval(
    base_eval: Any,
    output_root: Path,
    selection: Mapping[str, Any],
    selection_path: Path,
    checkpoint_info: Mapping[str, Any],
    source_identity: Mapping[str, Mapping[str, str]],
):
    import imageio.v2 as imageio

    output_root = output_root.resolve()
    staging_root = _render_staging_root(output_root)
    selected_env = int(_mapping(selection.get("selected"), "selection.selected")["env_id"])

    def render_eval(self):
        import torch

        _validate_effective_eval_contract(self.config, self.policy_model)
        if int(self.env.num_envs) != EXPECTED_NUM_ENVS:
            raise RuntimeError("selected Student render requires exactly 16 environments")
        if output_root.exists() or staging_root.exists():
            raise FileExistsError(
                f"selected render refuses existing final/staging roots: final={output_root} staging={staging_root}"
            )
        staging_root.parent.mkdir(parents=True, exist_ok=True)
        staging_root.mkdir()
        staging_owned = True
        writers: dict[str, Any] = {}
        temporary_paths: dict[str, Path] = {}
        final_paths: dict[str, Path] = {}
        frame_counts = {"left_d435": 0, "right_d435": 0, "head_oem": 0, "d435_left_right_side_by_side": 0}
        first_frames: dict[str, Any] = {}
        diverse = {name: False for name in frame_counts}
        policy_checks = 0
        original_rollout = None
        policy_model = None
        rollout_patched = False
        committed = False

        def close_writers() -> None:
            errors: list[BaseException] = []
            for writer in writers.values():
                try:
                    writer.close()
                except BaseException as exc:
                    errors.append(exc)
            if errors:
                raise errors[0]

        try:
            video_dir = staging_root / "policy_camera_videos"
            video_dir.mkdir()
            names = {
                "left_d435": video_dir / f"d435_left_env{selected_env:04d}.mp4",
                "right_d435": video_dir / f"d435_right_env{selected_env:04d}.mp4",
                "head_oem": video_dir / f"oem_head_env{selected_env:04d}.mp4",
                "d435_left_right_side_by_side": video_dir / f"d435_left_right_side_by_side_env{selected_env:04d}.mp4",
            }
            final_paths = names
            temporary_paths = {name: _temporary_video_path(path) for name, path in names.items()}
            if any(path.exists() for path in (*final_paths.values(), *temporary_paths.values())):
                raise FileExistsError("selected render video staging path already exists")

            selection_sha = sha256_file(selection_path)
            unwrapped = self.accelerator.unwrap_model(self.model)
            if getattr(unwrapped, "policy", None) is not self.policy_model:
                raise RuntimeError("Student policy identity differs from unwrapped eval policy")
            policy_model = self.policy_model
            original_rollout = policy_model.rollout
            case_table = capture_reset_case_table(self.env)

            def writer_for(name: str):
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

            def captured_rollout(*args: Any, **kwargs: Any):
                nonlocal policy_checks
                obs_dict = kwargs.get("obs_dict")
                if obs_dict is None and args:
                    obs_dict = args[0]
                if not isinstance(obs_dict, Mapping):
                    raise TypeError("Student rollout capture requires obs_dict mapping")
                completed = getattr(self, "env_episode_completed", None)
                if not torch.is_tensor(completed) or tuple(completed.shape) != (EXPECTED_NUM_ENVS,):
                    raise RuntimeError("first-episode completion mask was not initialized")
                if not bool(completed[selected_env].item()):
                    cameras_cfg = self.env.config.simulator.config.cameras
                    left, right, head, _ = derive_raw_policy_frames(obs_dict, cameras_cfg)
                    policy_checks += 1
                    frames = {
                        "left_d435": left[selected_env].detach().contiguous(),
                        "right_d435": right[selected_env].detach().contiguous(),
                        "head_oem": head[selected_env].detach().contiguous(),
                    }
                    frames["d435_left_right_side_by_side"] = torch.cat(
                        (frames["left_d435"], frames["right_d435"]), dim=1
                    )
                    expected_shapes = {
                        "left_d435": (384, 216, 3),
                        "right_d435": (384, 216, 3),
                        "head_oem": (136, 384, 3),
                        "d435_left_right_side_by_side": (384, 432, 3),
                    }
                    for name, frame in frames.items():
                        if tuple(frame.shape) != expected_shapes[name] or frame.dtype != torch.uint8:
                            raise RuntimeError(f"render frame shape/dtype drift for {name}: {tuple(frame.shape)} {frame.dtype}")
                        if int(frame.max().item()) <= int(frame.min().item()):
                            raise RuntimeError(f"selected {name} frame is constant")
                        previous = first_frames.get(name)
                        if previous is not None and not torch.equal(previous, frame):
                            diverse[name] = True
                        if previous is None:
                            first_frames[name] = frame.clone()
                        writer_for(name).append_data(frame.cpu().numpy())
                        frame_counts[name] += 1
                return original_rollout(*args, **kwargs)

            policy_model.rollout = captured_rollout
            rollout_patched = True
            result = base_eval(self)
            replay_metrics = result if isinstance(result, Mapping) else self.env.get_eval_metrics_summary()
            verify_loaded_runtime_sources(source_identity)
            replay_validation = validate_replay_case(selection, replay_metrics, case_table)
            if int(replay_metrics.get("completed_episodes", -1)) != EXPECTED_EPISODES:
                raise RuntimeError("selected render did not complete one episode per env")
            if policy_checks <= 0 or any(count != policy_checks for count in frame_counts.values()):
                raise RuntimeError(f"policy frame count mismatch: checks={policy_checks} frames={frame_counts}")
            if not all(diverse.values()):
                raise RuntimeError(f"selected policy videos lack frame diversity: {diverse}")
            policy_model.rollout = original_rollout
            rollout_patched = False
            close_writers()
            for name, temporary in temporary_paths.items():
                if not temporary.is_file():
                    raise RuntimeError(f"selected render temporary video was not written: {temporary}")
                os.replace(temporary, final_paths[name])
            video_metadata = [
                _validate_video(final_paths[name], frame_counts[name], tuple(first_frames[name].shape))
                for name in ("left_d435", "right_d435", "head_oem", "d435_left_right_side_by_side")
            ]
            metadata = {
                "schema": RENDER_SCHEMA,
                "training_performed": False,
                "selection": {
                    "path": str(selection_path.resolve()),
                    "sha256": selection_sha,
                    "case_identity": replay_validation["case_identity"],
                },
                "checkpoint": json_safe(checkpoint_info),
                "worktree_sources": json_safe(source_identity),
                "ranking": {
                    "order": FORMAL_RANKING_ORDER,
                    "selected_env_id": selected_env,
                },
                "source_formal_outcome": replay_validation["source_formal_outcome"],
                "replay_outcome": replay_validation["replay_outcome"],
                "outcome_drift": replay_validation["outcome_drift"],
                "student_policy": {
                    "teacher_rollout": False,
                    "teacher_rollout_ratio": 0.0,
                    "high_level_action_source": "student_policy_action_mean",
                    "leg_action_source": "frozen_a2_base",
                    "policy_input_checks": policy_checks,
                },
                "videos": video_metadata,
            }
            atomic_json_write(staging_root / "selected_render_metadata.json", metadata)
            if output_root.exists():
                raise FileExistsError(f"selected render final root appeared before publish: {output_root}")
            os.replace(staging_root, output_root)
            staging_owned = False
            committed = True
            print(
                "[A2_TOEOUT6_STUDENT_RENDER_PASS] "
                f"selected_env={selected_env} frames={policy_checks} videos=4 output={output_root}",
                flush=True,
            )
            return result
        finally:
            try:
                if rollout_patched and policy_model is not None:
                    policy_model.rollout = original_rollout
            finally:
                try:
                    close_writers()
                finally:
                    if staging_owned and not committed and staging_root.exists():
                        shutil.rmtree(staging_root)

    render_eval.__name__ = "toeout6_student_selected_render_eval"
    render_eval.__qualname__ = "toeout6_student_selected_render_eval"
    render_eval._a2_eval_base = base_eval
    return render_eval


def _direct_load_teacher_actor(self: Any) -> None:
    """Load the reference actor weights without changing the current env source."""
    import torch

    artifact = _mapping(self.config.get("teacher_artifact"), "algo.config.teacher_artifact")
    # The immutable Teacher provenance may live in the separately sealed
    # reference workspace.  It is accepted only as an explicit, hash-validated
    # artifact; all Student checkpoint/output/runtime sources remain worktree
    # pinned above.
    artifact_paths = {
        name: Path(str(artifact.get(name, ""))).expanduser().resolve(strict=True)
        for name in ("checkpoint_path", "config_path", "manifest_path")
    }
    checkpoint_path = artifact_paths["checkpoint_path"]
    config_path = artifact_paths["config_path"]
    manifest_path = artifact_paths["manifest_path"]
    expected = {
        "checkpoint_sha256": artifact.get("checkpoint_sha256"),
        "config_sha256": artifact.get("config_sha256"),
        "manifest_sha256": artifact.get("manifest_sha256"),
    }
    for name, value in expected.items():
        if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
            raise RuntimeError(f"Teacher artifact {name} must be pinned lowercase SHA256")
    actual = {
        "checkpoint_sha256": sha256_file(checkpoint_path),
        "config_sha256": sha256_file(config_path),
        "manifest_sha256": sha256_file(manifest_path),
    }
    if actual != expected:
        raise RuntimeError(f"Teacher artifact identity mismatch: expected={expected!r} actual={actual!r}")
    with manifest_path.open(encoding="utf-8") as stream:
        manifest = json.load(stream)
    checkpoint_manifest = _mapping(manifest.get("checkpoint"), "Teacher manifest checkpoint")
    state_key = checkpoint_manifest.get("state_dict_key")
    if not isinstance(state_key, str) or not state_key:
        raise RuntimeError("Teacher manifest state_dict_key is missing")
    if self.ref_model is None or int(getattr(self.ref_model, "num_actions", -1)) != 12:
        raise RuntimeError("Student eval requires a 12D recurrent Teacher reference model")
    payload = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    if not isinstance(payload, Mapping) or not isinstance(payload.get(state_key), Mapping):
        raise RuntimeError(f"Teacher checkpoint does not contain manifest state key {state_key!r}")
    self.ref_model.load_state_dict(payload[state_key], strict=True)
    self.ref_model.eval()
    self.teacher_manifest = manifest


def _prepare_runtime(
    mode: str,
    output_root: Path,
    checkpoint_info: Mapping[str, Any],
    source_identity: Mapping[str, Mapping[str, str]],
    selection: Mapping[str, Any] | None,
    selection_path: Path | None,
) -> None:
    """Patch only current-worktree Student hooks before executing eval_agent_trl."""
    import isaaclab.app as isaaclab_app

    from gr00t.rl.trl.trainer.distill_trainer_a2_base_api import TRLDistillTrainerA2BaseAPI
    from gr00t.rl.trl.trainer.ppo_trainer import TRLPPOTrainer as GenericTRLPPOTrainer
    from gr00t.rl.trl.trainer.ppo_trainer_a2_base_api import TRLPPOTrainer as A2TRLPPOTrainer

    if TRLDistillTrainerA2BaseAPI.eval is not GenericTRLPPOTrainer.eval:
        # The current Student class may already carry a prior binding in an
        # embedding process; only the canonical current-worktree A2 method is
        # accepted, never an alternate runtime implementation.
        if TRLDistillTrainerA2BaseAPI.eval is not A2TRLPPOTrainer.eval:
            raise RuntimeError("current Student trainer eval method binding is unexpected")
    else:
        TRLDistillTrainerA2BaseAPI.eval = A2TRLPPOTrainer.eval
    TRLDistillTrainerA2BaseAPI.load_teacher_actor = _direct_load_teacher_actor
    base_eval = A2TRLPPOTrainer.eval
    if mode == "formal":
        TRLDistillTrainerA2BaseAPI.eval = make_formal_eval(
            base_eval, output_root, checkpoint_info, source_identity
        )
    elif mode == "render":
        if selection is None or selection_path is None:
            raise ValueError("render runtime requires sealed selection and path")
        TRLDistillTrainerA2BaseAPI.eval = make_render_eval(
            base_eval,
            output_root,
            selection,
            selection_path,
            checkpoint_info,
            source_identity,
        )
    else:
        raise ValueError(f"unsupported runtime mode {mode!r}")

    original_launcher = isaaclab_app.AppLauncher

    class VerifiedAppLauncher(original_launcher):
        def __init__(self, *args: Any, **kwargs: Any):
            if len(args) != 1 or kwargs or not isinstance(args[0], argparse.Namespace):
                raise TypeError("Student eval AppLauncher requires one argparse.Namespace")
            cli = args[0]
            cli.experience = str(KIT_SOURCE)
            super().__init__(*args, **kwargs)

    isaaclab_app.AppLauncher = VerifiedAppLauncher
    overrides = build_overrides(mode, output_root, Path(str(checkpoint_info["path"])))
    sys.argv = [str(EVAL_ENTRY), *overrides]
    original_exit = os._exit

    def guarded_exit(status: int) -> None:
        if status == 0:
            artifact = (
                output_root / "student_selection.json"
                if mode == "formal"
                else output_root / "selected_render_metadata.json"
            )
            if not artifact.is_file():
                raise RuntimeError(f"eval returned success without required artifact: {artifact}")
        original_exit(status)

    os._exit = guarded_exit
    try:
        runpy.run_path(str(EVAL_ENTRY), run_name="__main__")
    finally:
        os._exit = original_exit


def _preflight_output_root(output_root: Path) -> Path:
    output_root = _workspace_path(output_root)
    staging = _render_staging_root(output_root)
    runtime = output_root.with_name(f".{output_root.name}.runtime")
    for path in (output_root, staging, runtime):
        if path.exists():
            if not path.is_dir():
                raise FileExistsError(f"output target is not a directory: {path}")
            if any(path.iterdir()):
                raise FileExistsError(f"fresh output target is not empty: {path}")
    return output_root


def _run_child(args: argparse.Namespace, mode: str, output_root: Path, selection_path: Path | None = None) -> None:
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--mode",
        mode,
        "--checkpoint",
        str(args.checkpoint),
        "--expected-global-step",
        str(args.expected_global_step),
        "--output-root",
        str(output_root),
    ]
    if args.checkpoint_sha256 is not None:
        command.extend(("--checkpoint-sha256", args.checkpoint_sha256))
    if args.checkpoint_config is not None:
        command.extend(("--checkpoint-config", str(args.checkpoint_config)))
    if args.checkpoint_config_sha256 is not None:
        command.extend(("--checkpoint-config-sha256", args.checkpoint_config_sha256))
    if selection_path is not None:
        command.extend(("--selection-json", str(selection_path)))
    subprocess.run(command, cwd=REPO_ROOT, check=True)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("formal", "render", "full"), required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--expected-global-step", type=int, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--checkpoint-sha256")
    parser.add_argument("--checkpoint-config", type=Path)
    parser.add_argument("--checkpoint-config-sha256")
    parser.add_argument("--selection-json", type=Path)
    args = parser.parse_args(argv)
    if (args.checkpoint_config is None) != (args.checkpoint_config_sha256 is None):
        parser.error("--checkpoint-config and --checkpoint-config-sha256 must be supplied together")
    if args.mode == "render" and args.selection_json is None:
        parser.error("render mode requires --selection-json from a formal run")
    if args.mode != "render" and args.selection_json is not None:
        parser.error("--selection-json is only valid for render mode")
    if args.mode == "full" and args.selection_json is not None:
        parser.error("full mode creates and consumes its own formal selection")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    checkpoint_info = validate_checkpoint_and_config(
        args.checkpoint,
        args.expected_global_step,
        args.checkpoint_config,
        args.checkpoint_sha256,
        args.checkpoint_config_sha256,
    )
    if args.mode == "full":
        root = _workspace_path(args.output_root)
        if root.exists():
            if not root.is_dir() or any(root.iterdir()):
                raise FileExistsError(f"full output root must be fresh and empty: {root}")
        root.mkdir(parents=True, exist_ok=False)
        formal_root = root / "formal"
        render_root = root / "render"
        _run_child(args, "formal", formal_root)
        _run_child(args, "render", render_root, formal_root / "student_selection.json")
        manifest = {
            "schema": "a2_toeout6_student_full_v1",
            "checkpoint": checkpoint_info,
            "formal_root": str(formal_root),
            "render_root": str(render_root),
            "selection": str(formal_root / "student_selection.json"),
            "render_metadata": str(render_root / "selected_render_metadata.json"),
        }
        atomic_json_write(root / "full_manifest.json", manifest)
        return 0

    output_root = _preflight_output_root(args.output_root)
    source_identity = validate_worktree_import_preflight()
    selection = None
    selection_path = None
    if args.mode == "render":
        selection_path = _workspace_path(args.selection_json, must_exist=True)
        selection, _ = load_sealed_selection(selection_path, checkpoint_info, source_identity)
    _prepare_runtime(
        args.mode,
        output_root,
        checkpoint_info,
        source_identity,
        selection,
        selection_path,
    )
    required = (
        output_root / "student_selection.json"
        if args.mode == "formal"
        else output_root / "selected_render_metadata.json"
    )
    if not required.is_file():
        raise RuntimeError(f"eval exited without required artifact: {required}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
