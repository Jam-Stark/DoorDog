"""P0.1/P0.3 phase-aligned torque telemetry adjudicator.

The producer is an exact sixteen-environment A0/D0/FULL diagnostic run from
the G1 step-1250 policy anchor.  PLAN is CPU-only and does not create either
the canonical output root or launcher files.  RUN_EVAL is an explicit,
single-attempt IsaacLab launch.  REDUCE is CPU-only and accepts only raw
phase-aligned telemetry; missing or malformed frames are typed INCONCLUSIVE.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from ._v23_common import REPO_ROOT, V23Error, emit_payload, require_file
except ImportError:
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from scriptsFORhuman.v23._v23_common import REPO_ROOT, V23Error, emit_payload, require_file


V23_PHASE_SNAPSHOT_SCHEMA = "a2_piper_base_v23_p0_phase_snapshot_v2"
V23_PHASE_FRAME_SCHEMA = "a2_piper_base_v23_p0_phase_aligned_frame_v2"
V23_PHASE_PRE_ACTUATOR_COMPUTE = "PRE_ACTUATOR_COMPUTE"
V23_PHASE_POST_PHYSICS = "POST_PHYSICS"
V23_PHASE_AUTHORITY_NOMINAL_PD = "NOMINAL_PD"
V23_PHASE_AUTHORITY_CLIPPED_COMMAND = "CLIPPED_COMMAND_TORQUE"
V23_PHASE_AUTHORITY_ESTIMATE_ONLY = "ESTIMATE_ONLY"
V23_PHASE_AUTHORITY_POST_ESTIMATE = "POST_ACTUATOR_ESTIMATE_DERIVED_FROM_PRE_STATE"
V23_PHASE_AUTHORITY_PRE_ESTIMATE = "NOT_CAPTURED_PRE_WRITE"
V23_PHASE_AUTHORITY_ACTUAL_PHYSX = "UNKNOWN/ACTUAL_PHYSX_DRIVE_FORCE_UNAVAILABLE"
V23_PHASE_ARM_JOINT_NAMES = ("arm_j1", "arm_j2", "arm_j3", "arm_j4", "arm_j5", "arm_j6")
V23_PHASE_VECTOR_FIELDS = (
    "q_6d", "qdot_6d", "q_target_6d", "qdot_target_6d", "effort_target_6d",
    "joint_velocity_limit_6d", "action_after_delay_6d", "action_scale_6d", "action_clip_6d",
    "default_dof_pos_6d", "stiffness_6d", "damping_6d", "execution_effort_limit_6d",
    "nominal_pd_torque_6d", "clipped_execution_command_6d",
    "isaaclab_computed_torque_estimate_6d", "isaaclab_applied_torque_estimate_6d",
)
V23_PHASE_PRE_VECTOR_FIELDS = tuple(
    field
    for field in V23_PHASE_VECTOR_FIELDS
    if field
    not in {
        "isaaclab_computed_torque_estimate_6d",
        "isaaclab_applied_torque_estimate_6d",
    }
)
V23_PHASE_POST_VECTOR_FIELDS = V23_PHASE_VECTOR_FIELDS


TASK_ID = "V23-P01-P03-DIAGNOSTIC-TERM-FIX-R170"
REVISION = "R170-R1"
PLAN_SCHEMA = "a2_piper_base_v23_p01_p03_runtime_plan_v2"
REDUCTION_SCHEMA = "a2_piper_base_v23_p01_p03_typed_adjudication_v2"
P01_RESULT_SCHEMA = "a2_piper_base_v23_p01_torque_telemetry_result_v2"
P03_RESULT_SCHEMA = "a2_piper_base_v23_p03_kp_action_clip_result_v2"
NUM_ENVS = 16
DECIMATION = 4
SEED = 0
EFFORT_NM = 40.0
CHECKPOINT_STEP = 1250
CELL = "G1"
SOURCE_CELL = "A0"
TOPOLOGY = "canonical16"
DOOR_REGIME = "D0"
POSTURE_MODE = "FULL"
PHYSICAL_GPU = 1
LOGICAL_DEVICE = "cuda:0"
DIAGNOSTICS_VERSION = "v2"
CANONICAL_ROOT = REPO_ROOT / "logs_eval/base_v23/p0/r170_p01_p03_runtime_20260810"
LAUNCHER_ROOT = REPO_ROOT / "logs_rl/launchers/base_v23/r170_p01_p03_runtime_20260810"
EVAL_NAME = "p01_p03_runtime_r170_20260810"
CONFIGURED_CAMERA_TYPES = [{"rgb": True}, {"depth": False}]
CHECKPOINT_PATH = REPO_ROOT / "logs_rl/a2_piper_full_stage_a2_base/base_v22/G1/model_step_001250.pt"
CONFIG_PATH = REPO_ROOT / "logs_rl/a2_piper_full_stage_a2_base/base_v22/G1/config.yaml"
PLAN_DOCUMENT = REPO_ROOT / "scriptsFORhuman/v23/a2_piper_base_v23_plan_R1_20260809.md"
PLAIN_MANIFEST_PATH = REPO_ROOT / (
    "logs_eval/base_v23/p0/r31_p02_temporal_runtime_20260809/torque/effort_40/"
    "canonical16/v23_p0_plain_scenario_manifest.json"
)
LEGACY_PRIOR_PATHS = {
    "r31_temporal": str(REPO_ROOT / "logs_eval/base_v23/p0/r31_p02_temporal_runtime_20260809"),
    "r33_effort_freeze": str(
        REPO_ROOT / "logs_eval/base_v23/p0/r33_p02_effort_freeze_20260809/effort_freeze.json"
    ),
}
ARM_EFFORT_LIMITS = [40.0] * 6
DOF_EFFORT_LIMITS = [120.0, 120.0, 180.0] * 4 + ARM_EFFORT_LIMITS + [45.0, 45.0]
PRIOR_F8_FAILURES = [
    {
        "task_id": "V23-P01-P03-F8-HYDRA-FIX-R161",
        "status": "FAILED_PRE_APP_HYDRA_COMPOSITION",
        "eval_root": str(REPO_ROOT / "logs_eval/base_v23/p0/r133_p01_p03_runtime_20260810"),
        "launcher_root": str(REPO_ROOT / "logs_rl/launchers/base_v23/r150_p01_p03_runtime_20260810"),
    },
    {
        "task_id": "V23-P01-P03-F8-HYDRA-FIX-R164",
        "status": "FAILED_ACTION_DOF_IDENTITY_GUARD",
        "returncode": 1,
        "actual_valid_permutation": True,
        "eval_root": str(REPO_ROOT / "logs_eval/base_v23/p0/r162_p01_p03_runtime_20260810"),
        "launcher_root": str(REPO_ROOT / "logs_rl/launchers/base_v23/r162_p01_p03_runtime_20260810"),
    },
    {
        "task_id": "V23-P01-P03-DIAGNOSTIC-TERM-FIX-R169",
        "status": "FAILED_INACTIVE_DIAGNOSTIC_REWARD_TERM",
        "returncode": 1,
        "diagnostic_reward_terms": ["push_door_handle"],
        "missing_reward_terms": ["push_door_handle"],
        "active_reward_terms": ["push_door_hinge"],
        "eval_root": str(REPO_ROOT / "logs_eval/base_v23/p0/r166_p01_p03_runtime_20260810"),
        "launcher_root": str(REPO_ROOT / "logs_rl/launchers/base_v23/r166_p01_p03_runtime_20260810"),
    },
]
PRE_AUTHORITY_LABELS = {
    "nominal_pd": V23_PHASE_AUTHORITY_NOMINAL_PD,
    "clipped_execution_command": V23_PHASE_AUTHORITY_CLIPPED_COMMAND,
    "isaaclab_computed_torque": V23_PHASE_AUTHORITY_PRE_ESTIMATE,
    "isaaclab_applied_torque": V23_PHASE_AUTHORITY_PRE_ESTIMATE,
    "isaaclab_estimate_authority": V23_PHASE_AUTHORITY_PRE_ESTIMATE,
    "actual_physx_drive_torque": V23_PHASE_AUTHORITY_ACTUAL_PHYSX,
}
POST_AUTHORITY_LABELS = {
    "nominal_pd": V23_PHASE_AUTHORITY_NOMINAL_PD,
    "clipped_execution_command": V23_PHASE_AUTHORITY_CLIPPED_COMMAND,
    "isaaclab_computed_torque": V23_PHASE_AUTHORITY_POST_ESTIMATE,
    "isaaclab_applied_torque": V23_PHASE_AUTHORITY_POST_ESTIMATE,
    "isaaclab_estimate_authority": V23_PHASE_AUTHORITY_POST_ESTIMATE,
    "actual_physx_drive_torque": V23_PHASE_AUTHORITY_ACTUAL_PHYSX,
}


def _finite_number(value: Any, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise V23Error(f"{name} must be a finite number; got {value!r}")
    return float(value)


def _finite_vector(value: Any, *, name: str) -> list[float]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) != 6:
        raise V23Error(f"{name} requires a finite six-value vector")
    return [_finite_number(item, name=f"{name}[{index}]") for index, item in enumerate(value)]


def _same_vector(left: Sequence[float], right: Sequence[float], *, name: str) -> None:
    if len(left) != len(right) or any(
        not math.isclose(float(a), float(b), rel_tol=2e-5, abs_tol=1e-6)
        for a, b in zip(left, right)
    ):
        raise V23Error(f"{name} disagrees with its source-backed equation")


def _validate_phase_frame_sequence_cpu(
    frames: Sequence[Mapping[str, Any]],
    *,
    expected_decimation: int,
    env_id: int,
    episode_id: str,
    control_step: int,
) -> None:
    if not isinstance(frames, list) or len(frames) != expected_decimation:
        raise V23Error(
            "phase frame sequence must contain exactly one PRE/POST pair per real substep; "
            f"expected={expected_decimation}"
        )
    seen: set[int] = set()
    for expected_index, frame in enumerate(frames):
        if not isinstance(frame, Mapping) or frame.get("schema") != V23_PHASE_FRAME_SCHEMA:
            raise V23Error(f"phase frame {expected_index} schema is malformed")
        identity = tuple(frame.get(key) for key in ("env_id", "episode_index", "episode_id", "control_step", "physics_frame_index"))
        if identity[0] != env_id or identity[2] != episode_id or identity[3] != control_step or identity[4] != expected_index:
            raise V23Error(f"phase frame {expected_index} key is missing/misaligned: {identity!r}")
        if expected_index in seen:
            raise V23Error(f"phase frame {expected_index} is duplicated")
        seen.add(expected_index)
        pre = frame.get("pre_actuator_compute")
        post = frame.get("post_physics")
        if not isinstance(pre, Mapping) or not isinstance(post, Mapping):
            raise V23Error(f"phase frame {expected_index} lacks both PRE and POST snapshots")
        if pre.get("phase") != V23_PHASE_PRE_ACTUATOR_COMPUTE or post.get("phase") != V23_PHASE_POST_PHYSICS:
            raise V23Error(f"phase frame {expected_index} has incorrect phase labels")
        pre_identity = tuple(pre.get(key) for key in ("env_id", "episode_index", "episode_id", "control_step", "physics_frame_index"))
        post_identity = tuple(post.get(key) for key in ("env_id", "episode_index", "episode_id", "control_step", "physics_frame_index"))
        if pre_identity != identity or post_identity != identity:
            raise V23Error(f"phase frame {expected_index} PRE/POST identities disagree")
        for mapping_key in (
            "arm_joint_names",
            "action_joint_names",
            "articulation_joint_names",
            "simulator_action_dof_ids",
            "action_slot_indices",
            "articulation_joint_indices",
        ):
            if frame.get(mapping_key) != pre.get(mapping_key) or pre.get(mapping_key) != post.get(mapping_key):
                raise V23Error(f"phase frame {expected_index} mapping {mapping_key} disagrees")
        if pre.get("authority") != PRE_AUTHORITY_LABELS or post.get("authority") != POST_AUTHORITY_LABELS:
            raise V23Error(f"phase frame {expected_index} authority labels are malformed")
        if pre.get("tensor_contract") != post.get("tensor_contract"):
            raise V23Error(f"phase frame {expected_index} tensor contracts disagree")
        frame_authority = frame.get("authority")
        if frame_authority != {"pre_actuator_compute": PRE_AUTHORITY_LABELS, "post_physics": POST_AUTHORITY_LABELS}:
            raise V23Error(f"phase frame {expected_index} joined authority labels are malformed")
        for snapshot, expected_fields in (
            (pre, V23_PHASE_PRE_VECTOR_FIELDS),
            (post, V23_PHASE_POST_VECTOR_FIELDS),
        ):
            fields = snapshot.get("fields")
            if not isinstance(fields, Mapping) or set(fields) != set(expected_fields):
                raise V23Error(f"phase frame {expected_index} vector schema is incomplete")


def _require_paths() -> dict[str, str]:
    checkpoint = require_file(CHECKPOINT_PATH, label="P0.1/P0.3 G1 step-1250 checkpoint")
    saved_config = require_file(checkpoint.parent / "config.yaml", label="P0.1/P0.3 checkpoint-adjacent saved config")
    declared_config = require_file(CONFIG_PATH, label="P0.1/P0.3 declared source config")
    if saved_config.resolve() != declared_config.resolve():
        raise V23Error(
            "P0.1/P0.3 declared source config must be the checkpoint-adjacent config.yaml; "
            f"saved={saved_config.resolve()}, declared={declared_config.resolve()}"
        )
    paths = {
        "checkpoint": checkpoint,
        "config": saved_config,
        "plan_document": PLAN_DOCUMENT,
        "plain_manifest": PLAIN_MANIFEST_PATH,
    }
    return {name: str(require_file(path, label=f"P0.1/P0.3 {name}").resolve()) for name, path in paths.items()}


def _build_eval_command() -> tuple[list[str], dict[str, str]]:
    paths = _require_paths()
    limits = "[" + ",".join(f"{value:g}" for value in DOF_EFFORT_LIMITS) + "]"
    argv = [
        sys.executable,
        "-m",
        "gr00t.rl.eval_agent_trl",
        f"++checkpoint={paths['checkpoint']}",
        "++checkpoint_load_mode=full",
        "++auto_load_latest=false",
        "++num_envs=16",
        "++num_gpus=1",
        "++multi_gpu=false",
        "++seed=0",
        "++headless=true",
        "++use_wandb=false",
        "++algo.trl.report_to=none",
        "++algo.config.eval.num_eval_episodes=16",
        "++algo.config.eval.eval_num_envs_episodes=true",
        "++algo.config.eval.a2_v23_p0_runtime_export=true",
        "++algo.config.eval.a2_diagnostic_trace_enabled=true",
        "++algo.config.eval.a2_diagnostic_reward_terms=[push_door_hinge]",
        "++algo.config.eval.a2_eval_m41_strict_telemetry=false",
        "++algo.config.eval.a2_eval_v20_strict_telemetry=false",
        "++algo.config.eval.save_videos=false",
        "++algo.config.eval.save_trajectories=false",
        "++env.config.a2_v20_R2_evidence_enabled=false",
        "++env.config.a2_v23_evidence_enabled=true",
        "++env.config.a2_v23_torque_telemetry_enabled=true",
        "++env.config.a2_v23_p0_temporal_evidence_enabled=true",
        "++env.config.a2_v23_p0_phase_diagnostics_v2_enabled=true",
        "++env.config.a2_v23_p0_checkpoint_load_mode=full",
        f"++env.config.a2_v23_effort_profile_nm={EFFORT_NM:g}",
        f"++env.config.a2_v23_p0_checkpoint={paths['checkpoint']}",
        f"++env.config.a2_v23_p0_config_id={paths['config']}",
        "++env.config.a2_v23_p0_scenario_id=A0_D0_FULL_G1_STEP1250",
        "++env.config.a2_v23_p0_source_cell=A0",
        "++env.config.a2_v23_p0_door_regime=D0",
        "++env.config.a2_v23_p0_seed=0",
        "++env.config.a2_v23_p0_plain_prefix_id=A0_D0_FULL_G1_STEP1250",
        f"++robot.dof_effort_limit_list={limits}",
        "++env.config.a2_v23_p0_plain_scenario_enabled=true",
        f"++env.config.a2_v23_p0_scenario_topology={TOPOLOGY}",
        f"++env.config.a2_v23_p0_scenario_manifest_path={paths['plain_manifest']}",
        f"++eval_name={EVAL_NAME}",
        f"++eval_output_dir={CANONICAL_ROOT.resolve()}",
        "++simulator.config.cameras.enable_cameras=false",
        "++simulator.config.render_results=false",
    ]
    env = {
        "CUDA_DEVICE_ORDER": "PCI_BUS_ID",
        "CUDA_VISIBLE_DEVICES": str(PHYSICAL_GPU),
        "ACCELERATE_TORCH_DEVICE": LOGICAL_DEVICE,
        "WANDB_MODE": "disabled",
        "PYTHONPATH": str(REPO_ROOT),
    }
    return argv, env


def build_plan() -> dict[str, Any]:
    paths = _require_paths()
    argv, env = _build_eval_command()
    return {
        "schema": PLAN_SCHEMA,
        "task_id": TASK_ID,
        "revision": REVISION,
        "mode": "PLAN",
        "cell": CELL,
        "source_cell": SOURCE_CELL,
        "checkpoint_step": CHECKPOINT_STEP,
        "checkpoint_load_mode": "full",
        "topology": TOPOLOGY,
        "door_regime": DOOR_REGIME,
        "posture_mode": POSTURE_MODE,
        "effort_nm": EFFORT_NM,
        "num_envs": NUM_ENVS,
        "decimation": DECIMATION,
        "diagnostics": {
            "version": DIAGNOSTICS_VERSION,
            "phase_schema": V23_PHASE_FRAME_SCHEMA,
            "enabled": True,
            "reward_terms": ["push_door_hinge"],
        },
        "physical_gpu": PHYSICAL_GPU,
        "logical_device": LOGICAL_DEVICE,
        "outputs": {
            "canonical_root": str(CANONICAL_ROOT.resolve()),
            "launcher_root": str(LAUNCHER_ROOT.resolve()),
            "eval_name": EVAL_NAME,
            "fresh_root_required": True,
            "disabled": ["wandb", "render", "video", "cameras"],
            "camera_configuration": {
                "configured_camera_types": [dict(item) for item in CONFIGURED_CAMERA_TYPES],
                "enable_cameras": False,
                "render_results": False,
                "construction_branch": "SKIPPED_RENDER_RESULTS_FALSE",
            },
        },
        "prior_f8_failures": [dict(item) for item in PRIOR_F8_FAILURES],
        "source_paths": paths,
        "legacy_prior_paths": LEGACY_PRIOR_PATHS,
        "legacy_prior_admission": "R31/R33_LEGACY_INSUFFICIENT_NOT_UPGRADED",
        "attempt_policy": "ONE_ATTEMPT_NO_RETRY",
        "argv": argv,
        "command": shlex.join(argv),
        "environment": dict(sorted(env.items())),
    }


def _assert_fresh_root(path: Path) -> None:
    if path.exists() and (not path.is_dir() or any(path.iterdir())):
        raise V23Error(f"fresh canonical output root is not empty: {path}")


def run_eval(plan: Mapping[str, Any]) -> dict[str, Any]:
    root = CANONICAL_ROOT.resolve()
    launcher = LAUNCHER_ROOT.resolve()
    _assert_fresh_root(root)
    launcher.mkdir(parents=True, exist_ok=True)
    root.mkdir(parents=True, exist_ok=True)
    stdout_path = launcher / "stdout.log"
    stderr_path = launcher / "stderr.log"
    command_path = launcher / "command.txt"
    command_path.write_text(str(plan["command"]) + "\n", encoding="utf-8")
    env = os.environ.copy()
    env.update({str(key): str(value) for key, value in plan["environment"].items()})
    with stdout_path.open("x", encoding="utf-8") as stdout, stderr_path.open("x", encoding="utf-8") as stderr:
        process = subprocess.run(
            list(plan["argv"]),
            cwd=REPO_ROOT,
            env=env,
            stdout=stdout,
            stderr=stderr,
            check=False,
        )
    receipt = {
        "schema": "a2_piper_base_v23_p01_p03_process_receipt_v2",
        "task_id": TASK_ID,
        "revision": REVISION,
        "returncode": int(process.returncode),
        "natural_exit": process.returncode == 0,
        "attempt_count": 1,
        "retry_policy": "none",
        "physical_gpu": PHYSICAL_GPU,
        "logical_device": LOGICAL_DEVICE,
        "checkpoint_load_mode": "full",
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "canonical_root": str(root),
        "prior_f8_failures": [dict(item) for item in PRIOR_F8_FAILURES],
    }
    (launcher / "process_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if process.returncode != 0:
        raise V23Error(f"P0.1/P0.3 RUN_EVAL failed with returncode={process.returncode}")
    return {**dict(plan), "mode": "RUN_EVAL", "process_receipt": receipt}


def _validate_snapshot(
    snapshot: Mapping[str, Any],
    *,
    expected_phase: str,
    identity: tuple[int, int, str, int, int],
) -> dict[str, list[float]]:
    if not isinstance(snapshot, Mapping) or snapshot.get("schema") != V23_PHASE_SNAPSHOT_SCHEMA:
        raise V23Error("phase snapshot schema is missing or malformed")
    if snapshot.get("phase") != expected_phase:
        raise V23Error(f"phase snapshot expected {expected_phase}, got {snapshot.get('phase')!r}")
    actual_identity = tuple(snapshot.get(key) for key in ("env_id", "episode_index", "episode_id", "control_step", "physics_frame_index"))
    if actual_identity != identity:
        raise V23Error(f"phase snapshot identity mismatch: expected={identity!r}, got={actual_identity!r}")
    if snapshot.get("arm_joint_names") != list(V23_PHASE_ARM_JOINT_NAMES):
        raise V23Error("phase snapshot arm joint identity is not arm_j1..arm_j6")
    action_names = snapshot.get("action_joint_names")
    articulation_names = snapshot.get("articulation_joint_names")
    simulator_dof_ids = snapshot.get("simulator_action_dof_ids")
    action_slots = snapshot.get("action_slot_indices")
    articulation_ids = snapshot.get("articulation_joint_indices")
    if (
        not isinstance(action_names, list)
        or len(action_names) != 20
        or any(not isinstance(name, str) or not name for name in action_names)
        or len(set(action_names)) != 20
        or not isinstance(articulation_names, list)
        or len(articulation_names) != 20
        or any(not isinstance(name, str) or not name for name in articulation_names)
        or len(set(articulation_names)) != 20
        or not isinstance(simulator_dof_ids, list)
        or len(simulator_dof_ids) != 20
        or any(isinstance(item, bool) or not isinstance(item, int) or not 0 <= item < 20 for item in simulator_dof_ids)
        or len(set(simulator_dof_ids)) != 20
        or sorted(simulator_dof_ids) != list(range(20))
    ):
        raise V23Error("phase snapshot action/articulation name lists are malformed")
    if (
        not isinstance(action_slots, list)
        or len(action_slots) != 6
        or any(isinstance(item, bool) or not isinstance(item, int) or not 0 <= item < 20 for item in action_slots)
        or len(set(action_slots)) != 6
        or not isinstance(articulation_ids, list)
        or len(articulation_ids) != 6
        or any(isinstance(item, bool) or not isinstance(item, int) or not 0 <= item < 20 for item in articulation_ids)
        or len(set(articulation_ids)) != 6
    ):
        raise V23Error("phase snapshot action/articulation index mapping is malformed")
    if [action_names[index] for index in action_slots] != list(V23_PHASE_ARM_JOINT_NAMES):
        raise V23Error("phase action slots do not resolve arm_j1..arm_j6 by name")
    if action_slots != list(range(12, 18)):
        raise V23Error("phase arm action slots must resolve to config slots 12..17")
    if [action_names[slot] for slot in range(20)] != [articulation_names[index] for index in simulator_dof_ids]:
        raise V23Error("phase action/articulation names disagree with simulator_action_dof_ids")
    if [simulator_dof_ids[index] for index in action_slots] != articulation_ids:
        raise V23Error("phase articulation indices do not derive from simulator_action_dof_ids")
    if [articulation_names[index] for index in articulation_ids] != list(V23_PHASE_ARM_JOINT_NAMES):
        raise V23Error("phase articulation indices do not resolve arm_j1..arm_j6 by name")
    expected_authority = PRE_AUTHORITY_LABELS if expected_phase == V23_PHASE_PRE_ACTUATOR_COMPUTE else POST_AUTHORITY_LABELS
    if snapshot.get("authority") != expected_authority:
        raise V23Error("phase snapshot authority labels are not the registered phase contract")
    tensor_contract = snapshot.get("tensor_contract")
    if (
        not isinstance(tensor_contract, Mapping)
        or tensor_contract.get("shape") != [6]
        or not isinstance(tensor_contract.get("dtype"), str)
        or not isinstance(tensor_contract.get("device"), str)
        or tensor_contract.get("source") != "ISAACLAB_ARTICULATION_DATA_RUNTIME_TENSOR"
    ):
        raise V23Error("phase snapshot tensor contract is missing runtime source/device/dtype provenance")
    fields = snapshot.get("fields")
    expected_fields = V23_PHASE_PRE_VECTOR_FIELDS if expected_phase == V23_PHASE_PRE_ACTUATOR_COMPUTE else V23_PHASE_POST_VECTOR_FIELDS
    if not isinstance(fields, Mapping) or set(fields) != set(expected_fields):
        raise V23Error("phase snapshot does not contain the exact six-joint vector schema")
    vectors = {field: _finite_vector(fields[field], name=f"{expected_phase}.{field}") for field in expected_fields}
    if any(not math.isclose(limit, EFFORT_NM, rel_tol=0.0, abs_tol=1e-6) for limit in vectors["execution_effort_limit_6d"]):
        raise V23Error("phase snapshot execution effort limits must be exactly 40 N*m")
    if any(
        abs(action) > clip + 1e-6
        for action, clip in zip(vectors["action_after_delay_6d"], vectors["action_clip_6d"])
    ):
        raise V23Error("phase snapshot action_after_delay exceeds action_clip")
    expected_target = [
        action * scale + default
        for action, scale, default in zip(
            vectors["action_after_delay_6d"], vectors["action_scale_6d"], vectors["default_dof_pos_6d"]
        )
    ]
    _same_vector(vectors["q_target_6d"], expected_target, name="q_target")
    expected_nominal = [
        kp * (target - q) + kd * (qdot_target - qdot) + effort_target
        for kp, target, q, kd, qdot_target, qdot, effort_target in zip(
            vectors["stiffness_6d"],
            vectors["q_target_6d"],
            vectors["q_6d"],
            vectors["damping_6d"],
            vectors["qdot_target_6d"],
            vectors["qdot_6d"],
            vectors["effort_target_6d"],
        )
    ]
    _same_vector(vectors["nominal_pd_torque_6d"], expected_nominal, name="nominal_pd")
    expected_clipped = [
        max(-limit, min(limit, nominal))
        for nominal, limit in zip(expected_nominal, vectors["execution_effort_limit_6d"])
    ]
    _same_vector(vectors["clipped_execution_command_6d"], expected_clipped, name="clipped_command")
    return vectors


def _controller_identity_check(
    provenance: Mapping[str, Any],
    first_vectors: Mapping[str, Sequence[float]],
    *,
    action_joint_names: Sequence[str],
    articulation_joint_names: Sequence[str],
    simulator_action_dof_ids: Sequence[int],
    action_slot_indices: Sequence[int],
    articulation_joint_indices: Sequence[int],
    decimation: int,
) -> None:
    identity = provenance.get("controller_identity")
    if not isinstance(identity, Mapping):
        raise V23Error("temporal source provenance lacks runtime controller_identity")
    if identity.get("decimation") != decimation or identity.get("arm_joint_names") != list(V23_PHASE_ARM_JOINT_NAMES):
        raise V23Error("runtime controller identity decimation/arm names disagree")
    if (
        identity.get("action_joint_names") != list(action_joint_names)
        or identity.get("articulation_joint_names") != list(articulation_joint_names)
        or identity.get("simulator_action_dof_ids") != list(simulator_action_dof_ids)
    ):
        raise V23Error("runtime controller identity full action/articulation mapping disagrees")
    if identity.get("action_slot_indices") != list(action_slot_indices) or identity.get("articulation_joint_indices") != list(articulation_joint_indices):
        raise V23Error("runtime controller identity action/articulation mapping disagrees")
    for field in (
        "action_scale_6d",
        "action_clip_6d",
        "default_dof_pos_6d",
        "stiffness_6d",
        "damping_6d",
        "execution_effort_limit_6d",
    ):
        expected = _finite_vector(identity.get(field), name=f"controller_identity.{field}")
        _same_vector(first_vectors[field], expected, name=f"controller_identity.{field}")
    if any(not math.isclose(value, EFFORT_NM, rel_tol=0.0, abs_tol=1e-6) for value in _finite_vector(identity.get("execution_effort_limit_6d"), name="controller_identity.execution_effort_limit_6d")):
        raise V23Error("controller identity effort limits must be exactly 40 N*m")
    if identity.get("source") != "PHASE_FRAME_RUNTIME_TENSORS":
        raise V23Error("controller identity source is not runtime phase tensors")


def reduce_raw(raw_path: Path) -> dict[str, Any]:
    target = require_file(raw_path, label="P0.1/P0.3 raw telemetry")
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise V23Error(f"invalid raw telemetry JSON: {target}") from exc
    if not isinstance(payload, Mapping) or payload.get("schema") != "a2_piper_base_v23_p0_torque_terminal_records_v1":
        raise V23Error("raw telemetry schema is not the v23 terminal-record producer schema")
    if payload.get("effort_nm") != EFFORT_NM:
        raise V23Error("raw telemetry effort is not the selected 40 N*m rung")
    terminal_contract = payload.get("terminal_identity_contract")
    if (
        not isinstance(terminal_contract, Mapping)
        or terminal_contract.get("fields") != ["env_id", "episode_index", "episode_id"]
        or terminal_contract.get("episode_id_authority") != "EVALUATOR_ASSIGNED_ENV_EPISODE_ID"
    ):
        raise V23Error("raw telemetry terminal_identity_contract is missing or malformed")
    terminal_records = payload.get("records")
    if not isinstance(terminal_records, list) or len(terminal_records) != NUM_ENVS:
        raise V23Error("raw telemetry must contain exactly sixteen terminal records")
    terminal_by_key: dict[tuple[int, int], Mapping[str, Any]] = {}
    for record_index, terminal in enumerate(terminal_records):
        if not isinstance(terminal, Mapping):
            raise V23Error(f"terminal record {record_index} is not a mapping")
        identity = terminal.get("terminal_identity")
        if not isinstance(identity, Mapping):
            raise V23Error(f"terminal record {record_index} lacks terminal_identity")
        terminal_env = identity.get("env_id")
        terminal_episode_index = identity.get("episode_index")
        terminal_episode_id = identity.get("episode_id")
        if (
            isinstance(terminal_env, bool)
            or not isinstance(terminal_env, int)
            or not 0 <= terminal_env < NUM_ENVS
            or isinstance(terminal_episode_index, bool)
            or not isinstance(terminal_episode_index, int)
            or terminal_episode_index < 0
            or terminal_episode_id != f"a2-v23-eval-env{terminal_env}-episode{terminal_episode_index}"
            or identity.get("authority") != "EVALUATOR_ASSIGNED_ENV_EPISODE_ID"
        ):
            raise V23Error(f"terminal record {record_index} terminal_identity is malformed")
        key = (terminal_env, terminal_episode_index)
        if key in terminal_by_key:
            raise V23Error(f"terminal identity is duplicated for env/episode {key!r}")
        terminal_by_key[key] = terminal
    if {env_id for env_id, _ in terminal_by_key} != set(range(NUM_ENVS)):
        raise V23Error("terminal identity records must cover every environment exactly once")
    temporal_payload = payload.get("temporal_records")
    if (
        not isinstance(temporal_payload, Mapping)
        or temporal_payload.get("schema") != "a2_piper_base_v23_p0_temporal_records_v1"
        or temporal_payload.get("status") != "RAW_TEMPORAL_PRESERVED"
        or temporal_payload.get("aggregate_fallback") is not False
    ):
        raise V23Error("raw telemetry does not preserve phase-aligned temporal records without fallback")
    episodes = temporal_payload.get("records")
    if not isinstance(episodes, list) or len(episodes) != NUM_ENVS:
        raise V23Error("raw telemetry must contain exactly sixteen temporal episode records")
    env_ids = [episode.get("env_id") if isinstance(episode, Mapping) else None for episode in episodes]
    if any(isinstance(env_id, bool) or not isinstance(env_id, int) for env_id in env_ids):
        raise V23Error(f"raw telemetry env ids must be integer values, got {env_ids!r}")
    if set(env_ids) != set(range(NUM_ENVS)):
        raise V23Error(f"raw telemetry env ids must cover 0..15 exactly, got {env_ids!r}")
    checked_frames = 0
    controller_identities: list[Mapping[str, Any]] = []
    reference_controller_identity: Mapping[str, Any] | None = None
    temporal_keys: set[tuple[int, int]] = set()
    for episode_index, episode in enumerate(sorted(episodes, key=lambda item: int(item["env_id"]))):
        if episode.get("schema") != "a2_piper_base_v23_p0_temporal_episode_v1":
            raise V23Error(f"temporal episode {episode_index} schema is malformed")
        env_id = episode.get("env_id")
        episode_number = episode.get("episode_index")
        episode_id = episode.get("episode_id")
        if (
            isinstance(env_id, bool)
            or not isinstance(env_id, int)
            or not 0 <= env_id < NUM_ENVS
            or isinstance(episode_number, bool)
            or not isinstance(episode_number, int)
            or episode_number < 0
            or not isinstance(episode_id, str)
            or episode_id != f"a2-v23-temporal-env{env_id}-episode{episode_number}"
            or episode.get("effort_nm") != EFFORT_NM
            or episode.get("topology") != TOPOLOGY
        ):
            raise V23Error(f"temporal episode {episode_index} identity is malformed")
        temporal_key = (env_id, episode_number)
        if temporal_key in temporal_keys:
            raise V23Error(f"temporal episode identity is duplicated for env/episode {temporal_key!r}")
        temporal_keys.add(temporal_key)
        terminal = terminal_by_key.get(temporal_key)
        if terminal is None:
            raise V23Error(f"temporal episode env{env_id} has no matching terminal identity record")
        outer_temporal = terminal.get("temporal_episode")
        if not isinstance(outer_temporal, Mapping):
            raise V23Error(f"terminal record env{env_id} lacks its bound temporal_episode")
        if (
            outer_temporal.get("schema") != "a2_piper_base_v23_p0_temporal_episode_v1"
            or outer_temporal.get("env_id") != env_id
            or outer_temporal.get("episode_index") != episode_number
            or outer_temporal.get("episode_id") != episode_id
        ):
            raise V23Error(f"terminal record env{env_id} temporal identity is not bound 1:1")
        if outer_temporal != episode:
            raise V23Error(f"terminal record env{env_id} temporal payload is not the preserved temporal record")
        provenance = episode.get("source_provenance")
        if not isinstance(provenance, Mapping):
            raise V23Error(f"temporal episode env{env_id} lacks source provenance")
        required = {
            "checkpoint": str(CHECKPOINT_PATH.resolve()),
            "config": str(CONFIG_PATH.resolve()),
            "scenario": "A0_D0_FULL_G1_STEP1250",
            "topology": TOPOLOGY,
            "seed": SEED,
            "plain_prefix_id": "A0_D0_FULL_G1_STEP1250",
            "effort_nm": EFFORT_NM,
            "checkpoint_load_mode": "full",
        }
        for key, expected in required.items():
            if provenance.get(key) != expected:
                raise V23Error(f"temporal episode env{env_id} provenance.{key} disagrees with the planned source")
        if (
            provenance.get("env_id") != env_id
            or provenance.get("episode_index") != episode_number
            or provenance.get("episode_id") != episode_id
        ):
            raise V23Error(f"temporal episode env{env_id} provenance identity is not terminal-bound")
        rows = episode.get("step_rows")
        if not isinstance(rows, list) or not rows:
            raise V23Error(f"temporal episode env{env_id} has no raw control-step rows")
        steps = [row.get("control_step") if isinstance(row, Mapping) else None for row in rows]
        if any(isinstance(step, bool) or not isinstance(step, int) or step < 0 for step in steps) or steps != sorted(set(steps)):
            raise V23Error(f"temporal episode env{env_id} control steps are not ordered and unique")
        first_vectors: Mapping[str, Sequence[float]] | None = None
        first_mapping: dict[str, Any] | None = None
        for row_index, row in enumerate(rows):
            if not isinstance(row, Mapping) or row.get("schema") != "a2_piper_base_v23_p0_temporal_step_v1":
                raise V23Error(f"temporal episode env{env_id} control row {row_index} is malformed")
            if row.get("env_id") != env_id or row.get("episode_index") != episode_number or row.get("episode_id") != episode_id:
                raise V23Error(f"temporal episode env{env_id} row {row_index} identity disagrees")
            phase_frames = row.get("phase_frames")
            if not isinstance(phase_frames, list):
                raise V23Error(f"temporal episode env{env_id} row {row_index} is missing phase_frames")
            try:
                _validate_phase_frame_sequence_cpu(
                    phase_frames,
                    expected_decimation=DECIMATION,
                    env_id=env_id,
                    episode_id=episode_id,
                    control_step=int(row["control_step"]),
                )
            except (TypeError, ValueError) as exc:
                raise V23Error(f"temporal episode env{env_id} row {row_index} phase ordering is invalid: {exc}") from exc
            for frame_index, frame in enumerate(phase_frames):
                frame_identity = (env_id, episode_number, episode_id, int(row["control_step"]), frame_index)
                pre = frame["pre_actuator_compute"]
                post = frame["post_physics"]
                pre_vectors = _validate_snapshot(pre, expected_phase=V23_PHASE_PRE_ACTUATOR_COMPUTE, identity=frame_identity)
                post_vectors = _validate_snapshot(post, expected_phase=V23_PHASE_POST_PHYSICS, identity=frame_identity)
                mapping = {
                    key: frame.get(key)
                    for key in (
                        "arm_joint_names",
                        "action_joint_names",
                        "articulation_joint_names",
                        "simulator_action_dof_ids",
                        "action_slot_indices",
                        "articulation_joint_indices",
                    )
                }
                if first_mapping is None:
                    first_mapping = mapping
                elif mapping != first_mapping:
                    raise V23Error(f"env{env_id}.frame{frame_index} controller mapping disagrees with first frame")
                for field in (
                    "action_after_delay_6d",
                    "action_scale_6d",
                    "action_clip_6d",
                    "default_dof_pos_6d",
                    "stiffness_6d",
                    "damping_6d",
                    "execution_effort_limit_6d",
                ):
                    _same_vector(
                        pre_vectors[field],
                        post_vectors[field],
                        name=f"env{env_id}.frame{frame_index}.{field}",
                    )
                if first_vectors is None:
                    first_vectors = pre_vectors
                else:
                    for field in (
                        "action_scale_6d",
                        "action_clip_6d",
                        "default_dof_pos_6d",
                        "stiffness_6d",
                        "damping_6d",
                        "execution_effort_limit_6d",
                    ):
                        _same_vector(
                            first_vectors[field],
                            pre_vectors[field],
                            name=f"env{env_id}.controller_identity.{field}",
                        )
                checked_frames += 1
        if first_vectors is None:
            raise V23Error(f"temporal episode env{env_id} has no phase frames")
        if first_mapping is None:
            raise V23Error(f"temporal episode env{env_id} has no controller mapping")
        _controller_identity_check(
            provenance,
            first_vectors,
            action_joint_names=first_mapping["action_joint_names"],
            articulation_joint_names=first_mapping["articulation_joint_names"],
            simulator_action_dof_ids=first_mapping["simulator_action_dof_ids"],
            action_slot_indices=first_mapping["action_slot_indices"],
            articulation_joint_indices=first_mapping["articulation_joint_indices"],
            decimation=DECIMATION,
        )
        current_controller_identity = provenance["controller_identity"]
        if reference_controller_identity is None:
            reference_controller_identity = current_controller_identity
        else:
            for key in (
                "decimation",
                "arm_joint_names",
                "action_joint_names",
                "articulation_joint_names",
                "simulator_action_dof_ids",
                "action_slot_indices",
                "articulation_joint_indices",
                "source",
            ):
                if current_controller_identity.get(key) != reference_controller_identity.get(key):
                    raise V23Error(f"controller identity {key} is inconsistent across exact16 environments")
            for field in (
                "action_scale_6d",
                "action_clip_6d",
                "default_dof_pos_6d",
                "stiffness_6d",
                "damping_6d",
                "execution_effort_limit_6d",
            ):
                _same_vector(
                    _finite_vector(current_controller_identity.get(field), name=f"controller_identity.{field}"),
                    _finite_vector(reference_controller_identity.get(field), name=f"controller_identity.{field}"),
                    name=f"controller_identity.{field}.exact16",
                )
        controller_identities.append(current_controller_identity)
    if temporal_keys != set(terminal_by_key):
        raise V23Error("terminal and temporal records are not a one-to-one exact16 binding")
    if len(controller_identities) != NUM_ENVS:
        raise V23Error("runtime controller identity coverage is not exact16")
    return {
        "schema": REDUCTION_SCHEMA,
        "task_id": TASK_ID,
        "revision": REVISION,
        "status": "P0_1_P0_3_RUNTIME_TYPED_ADJUDICATION",
        "source_raw_path": str(target.resolve()),
        "evaluation_root": str(CANONICAL_ROOT.resolve()),
        "launcher_root": str(LAUNCHER_ROOT.resolve()),
        "prior_f8_failures": [dict(item) for item in PRIOR_F8_FAILURES],
        "checkpoint_load_mode": "full",
        "source_paths": {
            "checkpoint": str(CHECKPOINT_PATH.resolve()),
            "config": str(CONFIG_PATH.resolve()),
            "plain_manifest": str(PLAIN_MANIFEST_PATH.resolve()),
        },
        "legacy_prior": {
            "paths": LEGACY_PRIOR_PATHS,
            "status": "R31_R33_LEGACY_INSUFFICIENT_NOT_UPGRADED",
        },
        "p01": {
            "schema": P01_RESULT_SCHEMA,
            "status": "RUNTIME_TYPED",
            "env_count": NUM_ENVS,
            "phase_frame_count": checked_frames,
            "authority": {
                "isaaclab_computed": V23_PHASE_AUTHORITY_POST_ESTIMATE,
                "isaaclab_applied": V23_PHASE_AUTHORITY_POST_ESTIMATE,
                "actual_physx_drive_torque": V23_PHASE_AUTHORITY_ACTUAL_PHYSX,
            },
        },
        "p03": {
            "schema": P03_RESULT_SCHEMA,
            "status": "RUNTIME_TYPED",
            "env_count": NUM_ENVS,
            "target_equation": "q_target == action_after_delay * action_scale + default_dof_pos",
            "nominal_equation": "Kp * (q_target - qpre) + Kd * (qdot_target - qdotpre) + effort_target",
            "clipped_equation": "clamp(nominal, +/- execution_effort_limit)",
            "controller_identity_env_count": len(controller_identities),
        },
        "admission": {
            "d1": False,
            "formal": False,
            "release": False,
            "claim_boundary": "P0.1_P0.3_ONLY",
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("PLAN", "RUN_EVAL", "REDUCE"), required=True)
    parser.add_argument("--raw", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if args.mode == "PLAN":
        payload = build_plan()
    elif args.mode == "RUN_EVAL":
        if not args.execute:
            raise V23Error("RUN_EVAL requires explicit --execute; no runtime was started")
        payload = run_eval(build_plan())
    else:
        if args.raw is None:
            raise V23Error("REDUCE requires --raw pointing to a producer JSON")
        payload = reduce_raw(args.raw)
    emit_payload(payload, args.out)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except V23Error as exc:
        raise SystemExit(f"P0.1/P0.3 ADJUDICATION FAIL: {exc}")
