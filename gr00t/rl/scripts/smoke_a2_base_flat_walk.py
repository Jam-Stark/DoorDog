# Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import argparse
import gc
import json
import math
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_USD_PATH = REPO_ROOT / "gr00t/rl/data/robots/A2_Piper/a2_piper.usd"
DEFAULT_POLICY_PATH = REPO_ROOT / "gr00t/rl/data/policies/A2_Base/policy.pt"
DEFAULT_METADATA_PATH = REPO_ROOT / "gr00t/rl/data/policies/A2_Base/policy_metadata.json"
ISAACLAB_PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
ISAACLAB_SH = Path("/home/baoquanc/workspace/IsaacLab/isaaclab.sh")
BASE_COMMAND_DIM = 5
BASE_COMMAND_SCALE = (0.25, 0.25, 0.25, 0.4, 0.4)
BASE_COMMAND_OBS_MULTIPLIERS = (2.0, 2.0, 0.25, 1.0, 1.0)
ARM_JOINT_NAMES = ("arm_j1", "arm_j2", "arm_j3", "arm_j4", "arm_j5", "arm_j6")


def import_app_launcher():
    try:
        from isaaclab.app import AppLauncher
    except ModuleNotFoundError as exc:
        if exc.name != "isaaclab":
            raise
        return None
    return AppLauncher


def add_fallback_app_launcher_args(parser: argparse.ArgumentParser) -> None:
    app_group = parser.add_argument_group(
        "app_launcher arguments",
        description="Accepted when running under IsaacLab Python or isaaclab.sh.",
    )
    app_group.add_argument("--headless", action="store_true", default=False)
    app_group.add_argument("--livestream", type=int, default=-1, choices={0, 1, 2})
    app_group.add_argument("--enable_cameras", action="store_true", default=False)
    app_group.add_argument("--xr", action="store_true", default=False)
    app_group.add_argument("--device", type=str, default="cuda:0")
    app_group.add_argument("--verbose", action="store_true")
    app_group.add_argument("--info", action="store_true")
    app_group.add_argument("--experience", type=str, default="")
    app_group.add_argument("--rendering_mode", type=str, choices={"performance", "balanced", "quality"})
    app_group.add_argument("--kit_args", type=str, default="")
    app_group.add_argument("--anim_recording_enabled", action="store_true")
    app_group.add_argument("--anim_recording_start_time", type=float, default=0)
    app_group.add_argument("--anim_recording_stop_time", type=float, default=10)


def require_app_launcher():
    AppLauncher = import_app_launcher()
    if AppLauncher is not None:
        return AppLauncher
    raise RuntimeError(
        "IsaacLab is required to launch the A2_Base flat walk smoke.\n"
        "This command was run with a Python environment that cannot import `isaaclab`.\n"
        "Use the validated conda IsaacLab Python, for example:\n"
        f"  CUDA_VISIBLE_DEVICES=2 {ISAACLAB_PYTHON} {Path(__file__).resolve()} "
        "--device cuda:0 --num-envs 1 --base-command-raw 1.0 0.0 0.0 0.0 0.0\n"
        "Alternatively, use the IsaacLab wrapper if this shell has the expected Python PATH:\n"
        f"  CUDA_VISIBLE_DEVICES=2 {ISAACLAB_SH} -p {Path(__file__).resolve()} "
        "--device cuda:0 --num-envs 1 --base-command-raw 1.0 0.0 0.0 0.0 0.0\n"
        "Plain `python3 ... --help` is supported for argument inspection only."
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a standalone Isaac Sim A2_Base flat-ground locomotion smoke. "
            "This loads only the frozen A2_Base policy and A2_Piper robot; it does not start "
            "PPO, DAgger, DoorPregrasp, or door-task checkpoints."
        )
    )
    parser.add_argument("--num-envs", "--num_envs", dest="num_envs", type=int, default=1)
    parser.add_argument("--env-spacing", "--env_spacing", dest="env_spacing", type=float, default=3.0)
    parser.add_argument("--usd-file", type=Path, default=DEFAULT_USD_PATH)
    parser.add_argument("--policy-path", type=Path, default=DEFAULT_POLICY_PATH)
    parser.add_argument("--metadata-path", type=Path, default=DEFAULT_METADATA_PATH)
    parser.add_argument("--root-x", type=float, default=0.0)
    parser.add_argument("--root-y", type=float, default=0.0)
    parser.add_argument("--root-z", type=float, default=0.55)
    parser.add_argument("--root-yaw", type=float, default=0.0)
    parser.add_argument(
        "--base-command-raw",
        type=float,
        nargs=BASE_COMMAND_DIM,
        metavar=("VX_RAW", "VY_RAW", "YAW_RAW", "PITCH_RAW", "ROLL_RAW"),
        default=(1.0, 0.0, 0.0, 0.0, 0.0),
        help=(
            "Raw 5D A2_Base command [vx, vy, yaw_rate, pitch, roll]. Physical velocity "
            "components are raw * 0.25 and pitch/roll components are raw * 0.4."
        ),
    )
    parser.add_argument(
        "--base-command-physical",
        type=float,
        nargs=BASE_COMMAND_DIM,
        metavar=("VX_MPS", "VY_MPS", "YAW_RADPS", "PITCH_RAD", "ROLL_RAD"),
        default=None,
        help="Physical 5D A2_Base command. Raw command is physical / per-component scale.",
    )
    parser.add_argument(
        "--command",
        type=float,
        nargs=BASE_COMMAND_DIM,
        metavar=("VX_MPS", "VY_MPS", "YAW_RADPS", "PITCH_RAD", "ROLL_RAD"),
        default=None,
        help=(
            "Compatibility alias for --base-command-physical. Prefer the explicit flag "
            "in new commands."
        ),
    )
    parser.add_argument(
        "--arm-posture",
        type=float,
        nargs=len(ARM_JOINT_NAMES),
        metavar=tuple(name.upper() for name in ARM_JOINT_NAMES),
        default=None,
        help=(
            "Fixed arm PD target in radians for arm_j1 through arm_j6. If omitted, "
            "the USD default arm posture is held."
        ),
    )
    parser.add_argument(
        "--command-script",
        type=Path,
        default=None,
        help=(
            "JSON command script with schema a2_base_flat_walk_command_script_v1. "
            "Its blocks hold static physical 5D commands or replay one trace env step by step."
        ),
    )
    parser.add_argument(
        "--metrics-json",
        type=Path,
        default=None,
        help="Write the measured per-block locomotion metrics to this JSON path.",
    )
    parser.add_argument("--seed", type=int, default=280001, help="Fixed Torch seed recorded in metrics.")
    parser.add_argument(
        "--max-steps",
        type=int,
        default=-1,
        help="Maximum physics steps to run. -1 runs until the GUI is closed.",
    )
    parser.add_argument(
        "--warmup-steps",
        type=int,
        default=30,
        help="Physics steps to hold the default pose before the first policy inference.",
    )
    parser.add_argument(
        "--reset-interval",
        type=int,
        default=0,
        help="Physics steps between resets. Set <=0 to disable periodic resets.",
    )
    parser.add_argument(
        "--control-decimation",
        type=int,
        default=4,
        help="Physics steps per policy step. With sim dt 0.005, default policy dt is 0.02.",
    )
    parser.add_argument(
        "--log-interval",
        type=int,
        default=50,
        help="Policy steps between concise locomotion monitor logs. Set <=0 to disable.",
    )
    AppLauncher = import_app_launcher()
    if AppLauncher is None:
        add_fallback_app_launcher_args(parser)
    else:
        AppLauncher.add_app_launcher_args(parser)
    return parser.parse_args()


def resolve_repo_path(path: Path) -> Path:
    path = Path(path).expanduser()
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path


def require_existing_file(path: Path, label: str) -> Path:
    path = resolve_repo_path(path)
    if not path.is_file():
        raise FileNotFoundError(f"A2_Base flat walk smoke requires {label}: {path}")
    return path


def validate_flat_walk_cuda_device(args_cli: argparse.Namespace) -> None:
    device = str(getattr(args_cli, "device", "")).strip().lower()
    if not device.startswith("cuda:"):
        return

    device_index = device.removeprefix("cuda:")
    if not device_index.isdigit() or int(device_index) == 0:
        return

    raise ValueError(
        "A2_Base flat walk smoke requires IsaacSim logical cuda:0 in this workflow.\n"
        f"To use physical GPU {device_index}, expose it as logical GPU 0 and pass --device cuda:0:\n"
        f"  CUDA_VISIBLE_DEVICES={device_index} ... --device cuda:0"
    )


def normalize_smoke_args(args_cli: argparse.Namespace) -> None:
    if args_cli.num_envs <= 0:
        raise ValueError(f"--num-envs must be positive, got {args_cli.num_envs}")
    if args_cli.env_spacing <= 0.0:
        raise ValueError(f"--env-spacing must be positive, got {args_cli.env_spacing}")
    if args_cli.root_z <= 0.0:
        raise ValueError(f"--root-z must be positive, got {args_cli.root_z}")
    if args_cli.warmup_steps < 0:
        raise ValueError(f"--warmup-steps must be non-negative, got {args_cli.warmup_steps}")
    if args_cli.control_decimation <= 0:
        raise ValueError(
            f"--control-decimation must be positive, got {args_cli.control_decimation}"
        )

    args_cli.usd_file = require_existing_file(args_cli.usd_file, "A2_Piper USD")
    args_cli.policy_path = require_existing_file(args_cli.policy_path, "A2_Base TorchScript policy")
    args_cli.metadata_path = require_existing_file(args_cli.metadata_path, "A2_Base metadata")
    if args_cli.command_script is not None:
        args_cli.command_script = require_existing_file(args_cli.command_script, "command script")
    if args_cli.metrics_json is not None:
        args_cli.metrics_json = resolve_repo_path(args_cli.metrics_json)
        if not args_cli.metrics_json.parent.is_dir():
            raise FileNotFoundError(
                "A2_Base flat walk metrics output parent does not exist: "
                f"{args_cli.metrics_json.parent}"
            )
    if not isinstance(args_cli.seed, int):
        raise ValueError(f"--seed must be an integer, got {args_cli.seed!r}")


def resolve_base_command(
    args_cli: argparse.Namespace,
) -> tuple[tuple[float, float, float, float, float], tuple[float, float, float, float, float], str]:
    if args_cli.command is not None and args_cli.base_command_physical is not None:
        raise ValueError("Use only one of --command or --base-command-physical.")

    if args_cli.command is not None:
        physical = tuple(float(v) for v in args_cli.command)
        raw = tuple(v / scale for v, scale in zip(physical, BASE_COMMAND_SCALE, strict=True))
        source = "--command physical alias"
    elif args_cli.base_command_physical is not None:
        physical = tuple(float(v) for v in args_cli.base_command_physical)
        raw = tuple(v / scale for v, scale in zip(physical, BASE_COMMAND_SCALE, strict=True))
        source = "--base-command-physical"
    else:
        raw = tuple(float(v) for v in args_cli.base_command_raw)
        physical = tuple(v * scale for v, scale in zip(raw, BASE_COMMAND_SCALE, strict=True))
        source = "--base-command-raw"
    if not all(math.isfinite(value) for value in (*raw, *physical)):
        raise ValueError(f"A2_Base command must be finite, got raw={raw} physical={physical}")
    return raw, physical, source


def load_a2_base_contract(metadata_path: Path) -> dict:
    with metadata_path.open("r", encoding="utf-8") as f:
        metadata = json.load(f)

    obs_contract = metadata["contracts"]["obs"]
    action_contract = metadata["contracts"]["action"]
    contract = {
        "obs_dim": int(obs_contract["flattened_dim"]),
        "history_length": int(obs_contract["history_length"]),
        "frame_dim": int(obs_contract["dog_frame_dim"]),
        "action_dim": int(action_contract["dim"]),
        "leg_joint_names": list(action_contract["leg_joint_names"]),
        "leg_action_scale": float(action_contract["leg_action_scale"]),
        "use_default_offset": bool(action_contract["use_default_offset"]),
    }

    expected = {
        "obs_dim": 1620,
        "history_length": 30,
        "frame_dim": 54,
        "action_dim": 12,
        "leg_action_scale": 0.25,
        "use_default_offset": True,
    }
    for key, expected_value in expected.items():
        actual_value = contract[key]
        if actual_value != expected_value:
            raise ValueError(
                "A2_Base metadata contract mismatch for "
                f"{key}: got {actual_value}, expected {expected_value}"
            )
    if contract["obs_dim"] != contract["history_length"] * contract["frame_dim"]:
        raise ValueError(f"A2_Base metadata obs contract is inconsistent: {contract}")
    if len(contract["leg_joint_names"]) != contract["action_dim"]:
        raise ValueError(
            "A2_Base metadata leg_joint_names length must match action dim: "
            f"{len(contract['leg_joint_names'])} != {contract['action_dim']}"
        )
    if len(set(contract["leg_joint_names"])) != len(contract["leg_joint_names"]):
        raise ValueError(f"A2_Base metadata leg_joint_names contains duplicates: {contract}")
    return contract


@dataclass(frozen=True)
class CommandBlock:
    name: str
    commands: tuple[tuple[float, float, float, float, float], ...]


class CommandProgram:
    def __init__(self, blocks: tuple[CommandBlock, ...]):
        self.blocks = blocks
        self.block_index = 0
        self.step_index = 0

    @property
    def is_complete(self) -> bool:
        return self.block_index == len(self.blocks)

    def next(self) -> tuple[str, tuple[float, float, float, float, float]]:
        if self.is_complete:
            raise RuntimeError("A2_Base command program is exhausted.")
        block = self.blocks[self.block_index]
        command = block.commands[self.step_index]
        self.step_index += 1
        if self.step_index == len(block.commands):
            self.block_index += 1
            self.step_index = 0
        return block.name, command


def _require_finite_physical_command(value: object, label: str) -> tuple[float, float, float, float, float]:
    if not isinstance(value, list) or len(value) != BASE_COMMAND_DIM:
        raise ValueError(f"{label} must be a JSON list of {BASE_COMMAND_DIM} physical command values.")
    command = tuple(float(item) for item in value)
    if not all(math.isfinite(item) for item in command):
        raise ValueError(f"{label} must contain only finite values, got {command}")
    return command


def _duration_to_policy_steps(duration_s: object, policy_dt: float, label: str) -> int:
    if not isinstance(duration_s, (int, float)) or not math.isfinite(float(duration_s)):
        raise ValueError(f"{label} must be a finite duration in seconds.")
    raw_steps = float(duration_s) / policy_dt
    steps = round(raw_steps)
    if steps <= 0 or not math.isclose(raw_steps, steps, rel_tol=0.0, abs_tol=1.0e-9):
        raise ValueError(
            f"{label} must be a positive integer multiple of policy_dt={policy_dt:.9f}, got {duration_s}"
        )
    return steps


def _load_trace_replay(replay: object, label: str, policy_dt: float) -> tuple[tuple[float, float, float, float, float], ...]:
    if not isinstance(replay, dict):
        raise ValueError(f"{label}.replay must be an object.")
    required = {"trace_path", "env_id", "stages", "steps"}
    if set(replay) != required:
        raise ValueError(f"{label}.replay keys must be exactly {sorted(required)}, got {sorted(replay)}")
    trace_path = require_existing_file(Path(replay["trace_path"]), f"{label}.replay trace")
    if not isinstance(replay["env_id"], int):
        raise ValueError(f"{label}.replay.env_id must be an integer.")
    if (
        not isinstance(replay["stages"], list)
        or not replay["stages"]
        or not all(isinstance(stage, int) for stage in replay["stages"])
    ):
        raise ValueError(f"{label}.replay.stages must be a non-empty integer list.")
    if not isinstance(replay["steps"], int) or replay["steps"] <= 0:
        raise ValueError(f"{label}.replay.steps must be a positive integer.")
    with trace_path.open("r", encoding="utf-8") as file:
        trace_rows = json.load(file)
    if not isinstance(trace_rows, list):
        raise ValueError(f"{label}.replay trace must be a JSON array: {trace_path}")

    commands: list[tuple[float, float, float, float, float]] = []
    requested_stages = set(replay["stages"])
    for row in trace_rows:
        if not isinstance(row, dict):
            raise ValueError(f"{label}.replay trace contains a non-object row: {trace_path}")
        if row.get("env_id") != replay["env_id"] or row.get("stage_buf") not in requested_stages:
            continue
        if row.get("first_episode_active") is not True or row.get("episode_index") != 0:
            continue
        row_dt = row.get("control_dt")
        if not isinstance(row_dt, (int, float)) or not math.isclose(
            float(row_dt), policy_dt, rel_tol=0.0, abs_tol=1.0e-9
        ):
            raise ValueError(
                f"{label}.replay control_dt must equal policy_dt={policy_dt:.9f}, got {row_dt!r}"
            )
        commands.append(_require_finite_physical_command(row.get("physical_base_command"), label))
        if len(commands) == replay["steps"]:
            return tuple(commands)
    raise ValueError(
        f"{label}.replay found {len(commands)} first-episode rows for env_id={replay['env_id']} "
        f"and stages={sorted(requested_stages)}, requires {replay['steps']}"
    )


def load_command_program(command_script: Path, policy_dt: float) -> CommandProgram:
    with command_script.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, dict) or set(payload) != {"schema", "blocks"}:
        raise ValueError("Command script must contain exactly schema and blocks.")
    if payload["schema"] != "a2_base_flat_walk_command_script_v1":
        raise ValueError(f"Unsupported command script schema: {payload['schema']!r}")
    if not isinstance(payload["blocks"], list) or not payload["blocks"]:
        raise ValueError("Command script blocks must be a non-empty list.")

    blocks: list[CommandBlock] = []
    names: set[str] = set()
    for index, block in enumerate(payload["blocks"]):
        label = f"command script blocks[{index}]"
        if not isinstance(block, dict) or "name" not in block:
            raise ValueError(f"{label} must be an object with a name.")
        name = block["name"]
        if not isinstance(name, str) or not name or name in names:
            raise ValueError(f"{label}.name must be a unique non-empty string.")
        names.add(name)
        has_static = "physical_base_command" in block
        has_replay = "replay" in block
        if has_static == has_replay:
            raise ValueError(f"{label} must contain exactly one of physical_base_command or replay.")
        if has_static:
            if set(block) != {"name", "duration_s", "physical_base_command"}:
                raise ValueError(f"{label} static block keys must be name, duration_s, physical_base_command.")
            command = _require_finite_physical_command(block["physical_base_command"], label)
            commands = (command,) * _duration_to_policy_steps(block["duration_s"], policy_dt, label)
        else:
            if set(block) != {"name", "replay"}:
                raise ValueError(f"{label} replay block keys must be name and replay.")
            commands = _load_trace_replay(block["replay"], label, policy_dt)
        blocks.append(CommandBlock(name=name, commands=commands))
    return CommandProgram(tuple(blocks))


def _run_cleanup_method(obj: object | None, method_name: str) -> BaseException | None:
    if obj is None:
        print(f"[INFO]: Flat walk cleanup skipped `{method_name}`; object is not available.", flush=True)
        return None
    method = getattr(obj, method_name, None)
    if method is None:
        print(f"[INFO]: Flat walk cleanup skipped `{method_name}`; method is not available.", flush=True)
        return None

    try:
        print(f"[INFO]: Flat walk cleanup starting `{method_name}`.", flush=True)
        method()
        print(f"[INFO]: Flat walk cleanup finished `{method_name}`.", flush=True)
    except Exception as exc:
        print(f"[WARN]: Flat walk cleanup `{method_name}` failed: {exc}", file=sys.stderr, flush=True)
        traceback.print_exception(exc, file=sys.stderr)
        return exc
    return None


def cleanup_flat_walk_before_app_close(sim: object | None, had_scene: bool) -> list[BaseException]:
    cleanup_errors: list[BaseException] = []

    if had_scene:
        print("[INFO]: Flat walk cleanup released scene reference; running gc.", flush=True)
    else:
        print("[INFO]: Flat walk cleanup has no scene reference to release; running gc.", flush=True)
    gc.collect()
    print("[INFO]: Flat walk cleanup finished scene gc.", flush=True)

    for method_name in ("clear", "clear_all_callbacks", "clear_instance"):
        cleanup_error = _run_cleanup_method(sim, method_name)
        if cleanup_error is not None:
            cleanup_errors.append(cleanup_error)

    sim = None
    print("[INFO]: Flat walk cleanup released sim reference; running gc.", flush=True)
    gc.collect()
    print("[INFO]: Flat walk cleanup finished sim gc.", flush=True)
    return cleanup_errors


def patch_app_launcher_toolbar_hiding(AppLauncher: type) -> None:
    """Skip optional IsaacLab toolbar hiding when this Kit lacks the toolbar widget."""
    if getattr(AppLauncher, "_a2_base_flat_walk_toolbar_hiding_patch_applied", False):
        return

    missing_module = "omni.kit.widget.toolbar"

    def make_wrapper(method_name: str, original_method):
        def wrapped(self, *args, **kwargs):
            try:
                return original_method(self, *args, **kwargs)
            except ModuleNotFoundError as exc:
                if exc.name != missing_module:
                    raise
                print(
                    "[WARN]: IsaacLab AppLauncher "
                    f"`{method_name}` skipped because `{missing_module}` is unavailable "
                    "in this Kit runtime.",
                    file=sys.stderr,
                    flush=True,
                )
                return None

        return wrapped

    for method_name in ("_hide_stop_button", "_hide_play_button"):
        original_method = getattr(AppLauncher, method_name, None)
        if original_method is not None:
            setattr(AppLauncher, method_name, make_wrapper(method_name, original_method))
    setattr(AppLauncher, "_a2_base_flat_walk_toolbar_hiding_patch_applied", True)


def create_flat_walk_scene(
    *,
    usd_path: Path,
    num_envs: int,
    env_spacing: float,
    device: str,
    root_x: float,
    root_y: float,
    root_z: float,
    root_yaw: float,
    arm_posture=None,
):
    import isaaclab.sim as sim_utils
    from isaaclab.assets import ArticulationCfg, AssetBaseCfg
    from isaaclab.scene import InteractiveScene, InteractiveSceneCfg
    from isaaclab.utils import configclass

    from gr00t.rl.envs.door.a2_piper_door_scene_preview import build_a2_piper_robot_cfg

    robot_cfg = build_a2_piper_robot_cfg(
        usd_path=usd_path,
        root_x=root_x,
        root_y=root_y,
        root_z=root_z,
        root_yaw=root_yaw,
    )
    if arm_posture is not None:
        robot_cfg.init_state.joint_pos = dict(robot_cfg.init_state.joint_pos)
        robot_cfg.init_state.joint_pos.update(zip(ARM_JOINT_NAMES, arm_posture, strict=True))

    @configclass
    class A2BaseFlatWalkSceneCfg(InteractiveSceneCfg):
        ground = AssetBaseCfg(
            prim_path="/World/defaultGroundPlane",
            spawn=sim_utils.GroundPlaneCfg(
                physics_material=sim_utils.RigidBodyMaterialCfg(
                    static_friction=1.0,
                    dynamic_friction=1.0,
                    restitution=0.0,
                )
            ),
        )
        dome_light = AssetBaseCfg(
            prim_path="/World/DomeLight",
            spawn=sim_utils.DomeLightCfg(intensity=2000.0, color=(0.98, 0.95, 0.88)),
        )
        robot: ArticulationCfg = robot_cfg.replace(prim_path="{ENV_REGEX_NS}/Robot")

    scene_cfg = A2BaseFlatWalkSceneCfg(
        num_envs=num_envs,
        env_spacing=env_spacing,
        replicate_physics=False,
    )
    sim = sim_utils.SimulationContext(sim_utils.SimulationCfg(dt=0.005, device=device))
    sim.set_camera_view([2.2, -2.2, 1.4], [0.0, 0.0, 0.55])
    scene = InteractiveScene(scene_cfg)
    sim.reset()
    return sim, scene


def reset_flat_walk_scene(scene) -> None:
    import torch

    robot = scene["robot"]
    root_state = robot.data.default_root_state.clone()
    root_state[:, :3] += scene.env_origins
    robot.write_root_pose_to_sim(root_state[:, :7])
    robot.write_root_velocity_to_sim(root_state[:, 7:])

    joint_pos = robot.data.default_joint_pos.clone()
    joint_vel = torch.zeros_like(robot.data.default_joint_vel)
    robot.write_joint_state_to_sim(joint_pos, joint_vel)
    robot.set_joint_position_target(joint_pos)
    scene.reset()


class A2BaseFlatWalkController:
    def __init__(
        self,
        *,
        robot,
        policy,
        contract: dict,
        raw_command: tuple[float, float, float, float, float],
        physical_command: tuple[float, float, float, float, float],
        arm_posture: tuple[float, float, float, float, float, float] | None,
        policy_dt: float,
    ):
        import torch
        from isaaclab.utils.math import euler_xyz_from_quat

        self.torch = torch
        self.euler_xyz_from_quat = euler_xyz_from_quat
        self.robot = robot
        self.policy = policy
        self.contract = contract
        self.device = robot.data.default_joint_pos.device
        self.dtype = robot.data.default_joint_pos.dtype
        self.num_envs = int(robot.data.default_joint_pos.shape[0])
        self.policy_dt = float(policy_dt)
        self.gait_frequency = 2.0

        name_to_index = {joint_name: index for index, joint_name in enumerate(robot.joint_names)}
        missing = [name for name in contract["leg_joint_names"] if name not in name_to_index]
        if missing:
            raise ValueError(
                "A2_Base metadata leg_joint_names are missing from A2_Piper robot joints: "
                f"{missing}\nRobot joints: {robot.joint_names}"
            )
        self.leg_joint_indices = torch.tensor(
            [name_to_index[name] for name in contract["leg_joint_names"]],
            device=self.device,
            dtype=torch.long,
        )
        missing_arm_joints = [name for name in ARM_JOINT_NAMES if name not in name_to_index]
        if missing_arm_joints:
            raise ValueError(
                "A2_Base arm posture joints are missing from A2_Piper robot joints: "
                f"{missing_arm_joints}\nRobot joints: {robot.joint_names}"
            )
        self.arm_joint_indices = torch.tensor(
            [name_to_index[name] for name in ARM_JOINT_NAMES],
            device=self.device,
            dtype=torch.long,
        )

        self.command_obs_multipliers = torch.tensor(
            BASE_COMMAND_OBS_MULTIPLIERS,
            device=self.device,
            dtype=self.dtype,
            requires_grad=False,
        )
        self.standing_thresholds = torch.tensor(
            [0.1, 0.1, 0.2],
            device=self.device,
            dtype=self.dtype,
            requires_grad=False,
        )
        self.raw_command = torch.tensor(
            raw_command,
            device=self.device,
            dtype=self.dtype,
            requires_grad=False,
        ).repeat(self.num_envs, 1)
        self.physical_command = torch.tensor(
            physical_command,
            device=self.device,
            dtype=self.dtype,
            requires_grad=False,
        ).repeat(self.num_envs, 1)
        self.history = torch.zeros(
            self.num_envs,
            contract["history_length"],
            contract["frame_dim"],
            device=self.device,
            dtype=self.dtype,
            requires_grad=False,
        )
        self.history_initialized = torch.zeros(
            self.num_envs,
            device=self.device,
            dtype=torch.bool,
            requires_grad=False,
        )
        self.last_leg_action = torch.zeros(
            self.num_envs,
            contract["action_dim"],
            device=self.device,
            dtype=self.dtype,
            requires_grad=False,
        )
        self.previous_leg_action = torch.zeros_like(self.last_leg_action)
        self.phase = torch.zeros(self.num_envs, device=self.device, dtype=self.dtype, requires_grad=False)
        self.episode_policy_steps = 0
        self.total_policy_steps = 0
        self.default_joint_pos = None
        self.default_leg_pos = None
        self.current_joint_targets = None
        self.arm_posture = None
        self.reset_buffers_from_robot()
        self.set_arm_posture(arm_posture)

    def reset_buffers_from_robot(self) -> None:
        self.default_joint_pos = self.robot.data.default_joint_pos.clone()
        self.default_leg_pos = self.default_joint_pos[:, self.leg_joint_indices].clone()
        self.current_joint_targets = self.default_joint_pos.clone()
        self.history.zero_()
        self.history_initialized.zero_()
        self.last_leg_action.zero_()
        self.previous_leg_action.zero_()
        self.phase.zero_()
        self.episode_policy_steps = 0
        if self.arm_posture is not None:
            self.current_joint_targets[:, self.arm_joint_indices] = self.arm_posture

    def set_arm_posture(self, arm_posture: tuple[float, float, float, float, float, float] | None) -> None:
        torch = self.torch
        if arm_posture is None:
            posture = self.default_joint_pos[:, self.arm_joint_indices].clone()
        else:
            if len(arm_posture) != len(ARM_JOINT_NAMES) or not all(math.isfinite(value) for value in arm_posture):
                raise ValueError(
                    f"--arm-posture must contain {len(ARM_JOINT_NAMES)} finite radians, got {arm_posture}"
                )
            posture = torch.tensor(arm_posture, device=self.device, dtype=self.dtype).repeat(self.num_envs, 1)
        joint_limits = self.robot.data.joint_pos_limits[:, self.arm_joint_indices, :]
        out_of_limits = (posture < joint_limits[:, :, 0]) | (posture > joint_limits[:, :, 1])
        if out_of_limits.any():
            raise ValueError(
                "A2_Base arm posture is outside the robot joint limits: "
                f"posture={posture[0].detach().cpu().tolist()} limits="
                f"{joint_limits[0].detach().cpu().tolist()}"
            )
        self.arm_posture = posture
        self.current_joint_targets[:, self.arm_joint_indices] = self.arm_posture

    def set_physical_command(self, physical_command: tuple[float, float, float, float, float]) -> None:
        if len(physical_command) != BASE_COMMAND_DIM or not all(math.isfinite(value) for value in physical_command):
            raise ValueError(f"A2_Base physical command must be {BASE_COMMAND_DIM} finite values, got {physical_command}")
        self.physical_command[:] = self.torch.tensor(
            physical_command,
            device=self.device,
            dtype=self.dtype,
        )
        self.raw_command[:] = self.physical_command / self.torch.tensor(
            BASE_COMMAND_SCALE,
            device=self.device,
            dtype=self.dtype,
        )

    def _update_phase_for_current_obs(self) -> None:
        torch = self.torch
        standing = (torch.abs(self.physical_command[:, :3]) < self.standing_thresholds[None, :]).all(dim=1)
        if self.episode_policy_steps > 0:
            moving = ~standing
            if moving.any():
                phase_inc = self.policy_dt * self.gait_frequency
                self.phase[moving] = torch.remainder(self.phase[moving] + phase_inc, 1.0)
        if standing.any():
            self.phase[standing] = 0.0

    def _build_obs_frame(self):
        torch = self.torch
        self._update_phase_for_current_obs()
        frame = torch.zeros(
            self.num_envs,
            self.contract["frame_dim"],
            device=self.device,
            dtype=self.dtype,
            requires_grad=False,
        )
        frame[:, 0:3] = self.robot.data.projected_gravity_b
        frame[:, 3:15] = self.robot.data.joint_pos[:, self.leg_joint_indices] - self.default_leg_pos
        frame[:, 15:27] = self.robot.data.joint_vel[:, self.leg_joint_indices] * 0.05
        frame[:, 27:39] = self.last_leg_action
        frame[:, 39:44] = self.physical_command * self.command_obs_multipliers[None, :]
        roll, pitch, _ = self.euler_xyz_from_quat(self.robot.data.root_quat_w)
        frame[:, 50] = roll
        frame[:, 51] = pitch
        frame[:, 52] = torch.sin(2.0 * torch.pi * self.phase)
        frame[:, 53] = torch.cos(2.0 * torch.pi * self.phase)
        return frame

    def _append_history(self, frame):
        initialized = self.history_initialized
        uninitialized = ~initialized
        if initialized.any():
            self.history[initialized, :-1, :] = self.history[initialized, 1:, :].clone()
            self.history[initialized, -1, :] = frame[initialized]
        if uninitialized.any():
            self.history[uninitialized, :, :] = frame[uninitialized].unsqueeze(1).expand(
                -1,
                self.contract["history_length"],
                -1,
            )
            self.history_initialized[uninitialized] = True
        obs = self.history.reshape(self.num_envs, -1)
        if obs.shape != (self.num_envs, self.contract["obs_dim"]):
            raise ValueError(
                "A2_Base smoke obs shape mismatch: "
                f"got {tuple(obs.shape)}, expected {(self.num_envs, self.contract['obs_dim'])}"
            )
        return obs

    def infer_policy_and_update_targets(self):
        torch = self.torch
        frame = self._build_obs_frame()
        obs = self._append_history(frame)
        with torch.inference_mode():
            action = self.policy(obs)
        if isinstance(action, (tuple, list)):
            action = action[0]
        if action.shape != (self.num_envs, self.contract["action_dim"]):
            raise ValueError(
                "A2_Base policy output shape mismatch: "
                f"got {tuple(action.shape)}, expected {(self.num_envs, self.contract['action_dim'])}"
            )
        action = action.to(device=self.device, dtype=self.dtype)
        self.previous_leg_action.copy_(self.last_leg_action)
        self.last_leg_action = action
        self.current_joint_targets = self.default_joint_pos.clone()
        self.current_joint_targets[:, self.leg_joint_indices] = (
            self.default_leg_pos + action * self.contract["leg_action_scale"]
        )
        self.current_joint_targets[:, self.arm_joint_indices] = self.arm_posture
        self.episode_policy_steps += 1
        self.total_policy_steps += 1
        return action

    def write_targets(self) -> None:
        self.robot.set_joint_position_target(self.current_joint_targets)

    def should_log(self, log_interval: int) -> bool:
        return log_interval > 0 and (
            self.total_policy_steps == 1 or self.total_policy_steps % log_interval == 0
        )

    def log_status(self, action) -> None:
        root_pos = self.robot.data.root_pos_w[0].detach().cpu().tolist()
        root_vel_b = self.robot.data.root_lin_vel_b[0].detach().cpu().tolist()
        raw_command = self.raw_command[0].detach().cpu().tolist()
        physical_command = self.physical_command[0].detach().cpu().tolist()
        phase = float(self.phase[0].detach().cpu().item())
        action_norm = float(self.torch.linalg.norm(action, dim=1).mean().detach().cpu().item())
        print(
            "[INFO]: policy_step="
            f"{self.total_policy_steps} "
            f"root_pos=({root_pos[0]:+.3f},{root_pos[1]:+.3f},{root_pos[2]:+.3f}) "
            f"root_vel_b=({root_vel_b[0]:+.3f},{root_vel_b[1]:+.3f},{root_vel_b[2]:+.3f}) "
            f"raw_cmd=({raw_command[0]:+.3f},{raw_command[1]:+.3f},{raw_command[2]:+.3f},"
            f"{raw_command[3]:+.3f},{raw_command[4]:+.3f}) "
            "physical_cmd="
            f"({physical_command[0]:+.3f},{physical_command[1]:+.3f},{physical_command[2]:+.3f},"
            f"{physical_command[3]:+.3f},{physical_command[4]:+.3f}) "
            f"phase={phase:.3f} action_norm={action_norm:.3f}",
            flush=True,
        )


def _summary(values) -> dict[str, float | None]:
    if values.numel() == 0:
        return {"p50": None, "p95": None, "max": None}
    quantiles = values.quantile(values.new_tensor((0.5, 0.95)))
    return {
        "p50": float(quantiles[0].item()),
        "p95": float(quantiles[1].item()),
        "max": float(values.max().item()),
    }


class FlatWalkMetrics:
    def __init__(self, controller: A2BaseFlatWalkController):
        self.torch = controller.torch
        self.controller = controller
        self.samples: dict[str, dict[str, list]] = {}

    def _block_samples(self, block_name: str) -> dict[str, list]:
        if block_name not in self.samples:
            self.samples[block_name] = {
                "tracking_error_abs": [],
                "command": [],
                "realized": [],
                "fallen": [],
                "root_height_m": [],
                "root_linear_speed_mps": [],
                "arm_joint_velocity_abs_radps": [],
                "arm_posture_error_l1_rad": [],
                "leg_action_rate_l2_per_s": [],
                "standing": [],
            }
        return self.samples[block_name]

    def observe(self, block_name: str) -> None:
        torch = self.torch
        robot = self.controller.robot
        values = self._block_samples(block_name)
        roll, pitch, _ = self.controller.euler_xyz_from_quat(robot.data.root_quat_w)
        realized = torch.cat(
            (
                robot.data.root_lin_vel_b[:, :2],
                robot.data.root_ang_vel_b[:, 2:3],
                pitch.unsqueeze(1),
                roll.unsqueeze(1),
            ),
            dim=1,
        )
        desired = self.controller.physical_command.clone()
        desired[:, 3:5] = -desired[:, 3:5]
        values["tracking_error_abs"].append(torch.abs(realized - desired))
        values["command"].append(desired)
        values["realized"].append(realized)
        fallen = (
            (robot.data.root_pos_w[:, 2] < 0.3)
            | (torch.abs(roll) > 0.9)
            | (torch.abs(pitch) > 0.9)
        )
        values["fallen"].append(fallen)
        values["root_height_m"].append(robot.data.root_pos_w[:, 2].clone())
        values["root_linear_speed_mps"].append(torch.linalg.vector_norm(robot.data.root_lin_vel_b, dim=1))
        arm_velocity_abs = torch.abs(robot.data.joint_vel[:, self.controller.arm_joint_indices]).amax(dim=1)
        values["arm_joint_velocity_abs_radps"].append(arm_velocity_abs)
        arm_pos_error = torch.abs(
            robot.data.joint_pos[:, self.controller.arm_joint_indices] - self.controller.arm_posture
        ).sum(dim=1)
        values["arm_posture_error_l1_rad"].append(arm_pos_error)
        action_rate = torch.linalg.vector_norm(
            self.controller.last_leg_action - self.controller.previous_leg_action,
            dim=1,
        ) / self.controller.policy_dt
        values["leg_action_rate_l2_per_s"].append(action_rate)
        standing = (torch.abs(self.controller.physical_command[:, :3]) < self.controller.standing_thresholds).all(dim=1)
        values["standing"].append(standing)

    def _reduce_block(self, values: dict[str, list]) -> dict:
        torch = self.torch
        tracking_error = torch.cat(values["tracking_error_abs"], dim=0)
        command = torch.cat(values["command"], dim=0)
        realized = torch.cat(values["realized"], dim=0)
        fallen = torch.stack(values["fallen"], dim=0)
        standing = torch.cat(values["standing"], dim=0)
        tracking = {
            name: _summary(tracking_error[:, index])
            for index, name in enumerate(("vx_mps", "vy_mps", "yaw_radps", "pitch_rad", "roll_rad"))
        }
        slopes: dict[str, float | None] = {}
        for index, name in enumerate(("vx", "vy", "yaw", "pitch", "roll")):
            nonzero = torch.abs(command[:, index]) > 1.0e-6
            if not nonzero.any():
                slopes[name] = None
                continue
            denominator = torch.sum(torch.square(command[nonzero, index]))
            slopes[name] = float(
                (torch.sum(command[nonzero, index] * realized[nonzero, index]) / denominator).item()
            )
        standing_root_speed = torch.cat(values["root_linear_speed_mps"], dim=0)[standing]
        standing_arm_speed = torch.cat(values["arm_joint_velocity_abs_radps"], dim=0)[standing]
        return {
            "control_samples": len(values["fallen"]),
            "tracking_error_abs": tracking,
            "tracking_slope_realized_over_command": slopes,
            "falls": {
                "unique_envs": int(fallen.any(dim=0).sum().item()),
                "sample_count": int(fallen.sum().item()),
                "criterion": "root_z_m < 0.3 or abs(root_roll_rad) > 0.9 or abs(root_pitch_rad) > 0.9",
            },
            "root_height_m": _summary(torch.cat(values["root_height_m"], dim=0)),
            "root_linear_speed_mps": _summary(torch.cat(values["root_linear_speed_mps"], dim=0)),
            "arm_joint_velocity_abs_radps": _summary(torch.cat(values["arm_joint_velocity_abs_radps"], dim=0)),
            "arm_posture_error_l1_rad": _summary(torch.cat(values["arm_posture_error_l1_rad"], dim=0)),
            "leg_action_rate_l2_per_s": _summary(torch.cat(values["leg_action_rate_l2_per_s"], dim=0)),
            "standing_root_linear_speed_mps": _summary(standing_root_speed),
            "standing_arm_joint_velocity_abs_radps": _summary(standing_arm_speed),
        }

    def write(self, path: Path, *, args_cli: argparse.Namespace, policy_dt: float) -> None:
        if not self.samples:
            raise RuntimeError("A2_Base metrics requested but no policy-step samples were recorded.")
        result = {
            "schema": "a2_base_flat_walk_metrics_v1",
            "seed": args_cli.seed,
            "num_envs": self.controller.num_envs,
            "sim_dt_s": policy_dt / args_cli.control_decimation,
            "policy_dt_s": policy_dt,
            "usd_file": str(args_cli.usd_file),
            "policy_path": str(args_cli.policy_path),
            "arm_joint_names": list(ARM_JOINT_NAMES),
            "arm_posture_rad": self.controller.arm_posture[0].detach().cpu().tolist(),
            "blocks": {name: self._reduce_block(values) for name, values in self.samples.items()},
        }
        with path.open("w", encoding="utf-8") as file:
            json.dump(result, file, indent=2, sort_keys=True)
            file.write("\n")
        print(f"[INFO]: Wrote A2_Base flat-walk metrics to {path}", flush=True)


def load_policy(policy_path: Path, device: str):
    import torch

    policy = torch.jit.load(str(policy_path), map_location=device)
    policy.eval()
    policy.to(device)
    for parameter in policy.parameters():
        parameter.requires_grad = False
    return policy


def run_flat_walk_smoke(
    *,
    sim,
    scene,
    simulation_app,
    args_cli: argparse.Namespace,
    contract: dict,
    raw_command: tuple[float, float, float, float, float],
    physical_command: tuple[float, float, float, float, float],
) -> None:
    import torch

    robot = scene["robot"]
    sim_dt = float(sim.get_physics_dt())
    policy_dt = sim_dt * float(args_cli.control_decimation)
    reset_flat_walk_scene(scene)
    torch.manual_seed(args_cli.seed)

    policy = load_policy(args_cli.policy_path, args_cli.device)
    controller = A2BaseFlatWalkController(
        robot=robot,
        policy=policy,
        contract=contract,
        raw_command=raw_command,
        physical_command=physical_command,
        arm_posture=None if args_cli.arm_posture is None else tuple(args_cli.arm_posture),
        policy_dt=policy_dt,
    )
    command_program = (
        None if args_cli.command_script is None else load_command_program(args_cli.command_script, policy_dt)
    )
    metrics = None if args_cli.metrics_json is None else FlatWalkMetrics(controller)

    count = 0
    next_policy_step = args_cli.warmup_steps
    active_block_name = None
    active_policy_step = False
    print("[INFO]: A2_Base flat walk smoke reset complete.")
    print(f"[INFO]: Robot joint count={len(robot.joint_names)} names={robot.joint_names}")
    print(f"[INFO]: Robot body count={len(robot.body_names)}")
    print(
        "[INFO]: Timing "
        f"sim_dt={sim_dt:.4f} control_decimation={args_cli.control_decimation} "
        f"policy_dt={policy_dt:.4f} warmup_steps={args_cli.warmup_steps} seed={args_cli.seed}"
    )
    if command_program is not None:
        print(
            "[INFO]: Command script "
            f"path={args_cli.command_script} blocks={[block.name for block in command_program.blocks]}",
            flush=True,
        )
    print(
        "[INFO]: Arm posture "
        f"{controller.arm_posture[0].detach().cpu().tolist()} for {list(ARM_JOINT_NAMES)}",
        flush=True,
    )

    while simulation_app.is_running():
        if args_cli.max_steps >= 0 and count >= args_cli.max_steps:
            break
        if args_cli.reset_interval > 0 and count > 0 and count % args_cli.reset_interval == 0:
            reset_flat_walk_scene(scene)
            controller.reset_buffers_from_robot()
            next_policy_step = count + args_cli.warmup_steps
            active_block_name = None
            active_policy_step = False
            print("[INFO]: Periodic flat walk reset.", flush=True)

        if count >= next_policy_step and (count - next_policy_step) % args_cli.control_decimation == 0:
            if active_policy_step and metrics is not None:
                metrics.observe(active_block_name)
            if command_program is not None:
                if command_program.is_complete:
                    break
                active_block_name, command = command_program.next()
                controller.set_physical_command(command)
            else:
                active_block_name = "cli"
            action = controller.infer_policy_and_update_targets()
            active_policy_step = True
            if controller.should_log(args_cli.log_interval):
                controller.log_status(action)

        controller.write_targets()
        scene.write_data_to_sim()
        sim.step()
        scene.update(sim_dt)
        count += 1

    if metrics is not None:
        metrics.write(args_cli.metrics_json, args_cli=args_cli, policy_dt=policy_dt)


def main() -> int:
    args_cli = parse_args()
    try:
        normalize_smoke_args(args_cli)
        validate_flat_walk_cuda_device(args_cli)
        contract = load_a2_base_contract(args_cli.metadata_path)
        raw_command, physical_command, command_source = resolve_base_command(args_cli)
        print(
            "[INFO]: A2_Base command source="
            f"{command_source} raw={raw_command} physical={physical_command}"
        )

        AppLauncher = require_app_launcher()
        patch_app_launcher_toolbar_hiding(AppLauncher)
    except BaseException as exc:
        traceback.print_exception(exc, file=sys.stderr)
        return 1

    sim = None
    scene = None
    simulation_app = None
    run_error = None
    app_launcher = AppLauncher(args_cli)
    simulation_app = app_launcher.app

    try:
        sim, scene = create_flat_walk_scene(
            usd_path=args_cli.usd_file,
            num_envs=args_cli.num_envs,
            env_spacing=args_cli.env_spacing,
            device=args_cli.device,
            root_x=args_cli.root_x,
            root_y=args_cli.root_y,
            root_z=args_cli.root_z,
            root_yaw=args_cli.root_yaw,
            arm_posture=args_cli.arm_posture,
        )
        print(
            "[INFO]: Flat walk root pose "
            f"x={args_cli.root_x} y={args_cli.root_y} z={args_cli.root_z} yaw={args_cli.root_yaw}"
        )
        run_flat_walk_smoke(
            sim=sim,
            scene=scene,
            simulation_app=simulation_app,
            args_cli=args_cli,
            contract=contract,
            raw_command=raw_command,
            physical_command=physical_command,
        )
    except BaseException as exc:
        run_error = exc
        traceback.print_exception(exc, file=sys.stderr)
    finally:
        had_scene = scene is not None
        scene = None
        cleanup_errors = cleanup_flat_walk_before_app_close(sim=sim, had_scene=had_scene)
        if cleanup_errors and run_error is None:
            run_error = cleanup_errors[0]
        sim = None
        gc.collect()
        if simulation_app is not None:
            try:
                print("[INFO]: Flat walk cleanup starting `SimulationApp.close`.", flush=True)
                simulation_app.close()
                print("[INFO]: Flat walk cleanup finished `SimulationApp.close`.", flush=True)
            except BaseException as exc:
                if run_error is None:
                    run_error = exc
                    traceback.print_exception(exc, file=sys.stderr)
                else:
                    print(
                        "[WARN]: SimulationApp.close() failed after an earlier flat walk error:",
                        file=sys.stderr,
                        flush=True,
                    )
                    traceback.print_exception(exc, file=sys.stderr)
        if run_error is not None:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
