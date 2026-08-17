# Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import argparse
import gc
import json
import sys
import traceback
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_USD_PATH = REPO_ROOT / "gr00t/rl/data/robots/A2_Piper/a2_piper.usd"
DEFAULT_POLICY_PATH = REPO_ROOT / "gr00t/rl/data/policies/A2_Base/policy.pt"
DEFAULT_METADATA_PATH = REPO_ROOT / "gr00t/rl/data/policies/A2_Base/policy_metadata.json"
ISAACLAB_PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
ISAACLAB_SH = Path("/home/baoquanc/workspace/IsaacLab/isaaclab.sh")


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
        "--device cuda:0 --num-envs 1 --base-command-raw 1.0 0.0 0.0\n"
        "Alternatively, use the IsaacLab wrapper if this shell has the expected Python PATH:\n"
        f"  CUDA_VISIBLE_DEVICES=2 {ISAACLAB_SH} -p {Path(__file__).resolve()} "
        "--device cuda:0 --num-envs 1 --base-command-raw 1.0 0.0 0.0\n"
        "Plain `python3 ... --help` is supported for argument inspection only."
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a standalone full-GUI Isaac Sim A2_Base flat-ground locomotion smoke. "
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
        nargs=3,
        metavar=("VX_RAW", "VY_RAW", "YAW_RAW"),
        default=(1.0, 0.0, 0.0),
        help=(
            "Raw 3D high-level base command. Physical command is raw * 0.25, so the "
            "default yields vx=0.25 m/s."
        ),
    )
    parser.add_argument(
        "--base-command-physical",
        type=float,
        nargs=3,
        metavar=("VX_MPS", "VY_MPS", "YAW_RADPS"),
        default=None,
        help="Physical 3D base command. If set, raw command is physical / 0.25.",
    )
    parser.add_argument(
        "--command",
        type=float,
        nargs=3,
        metavar=("VX_MPS", "VY_MPS", "YAW_RADPS"),
        default=None,
        help=(
            "Compatibility alias for --base-command-physical. Prefer the explicit flag "
            "in new commands."
        ),
    )
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
        "A2_Base flat walk smoke uses IsaacSim/UsdRT full-GUI rendering, which currently "
        "supports only logical cuda:0 in this workflow.\n"
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


def resolve_base_command(args_cli: argparse.Namespace) -> tuple[tuple[float, float, float], tuple[float, float, float], str]:
    if args_cli.command is not None and args_cli.base_command_physical is not None:
        raise ValueError("Use only one of --command or --base-command-physical.")

    command_scale = 0.25
    if args_cli.command is not None:
        physical = tuple(float(v) for v in args_cli.command)
        raw = tuple(v / command_scale for v in physical)
        source = "--command physical alias"
    elif args_cli.base_command_physical is not None:
        physical = tuple(float(v) for v in args_cli.base_command_physical)
        raw = tuple(v / command_scale for v in physical)
        source = "--base-command-physical"
    else:
        raw = tuple(float(v) for v in args_cli.base_command_raw)
        physical = tuple(v * command_scale for v in raw)
        source = "--base-command-raw"
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
        raw_command: tuple[float, float, float],
        physical_command: tuple[float, float, float],
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

        self.command_obs_multipliers = torch.tensor(
            [2.0, 2.0, 0.25],
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
        self.phase = torch.zeros(self.num_envs, device=self.device, dtype=self.dtype, requires_grad=False)
        self.episode_policy_steps = 0
        self.total_policy_steps = 0
        self.default_joint_pos = None
        self.default_leg_pos = None
        self.current_joint_targets = None
        self.reset_buffers_from_robot()

    def reset_buffers_from_robot(self) -> None:
        self.default_joint_pos = self.robot.data.default_joint_pos.clone()
        self.default_leg_pos = self.default_joint_pos[:, self.leg_joint_indices].clone()
        self.current_joint_targets = self.default_joint_pos.clone()
        self.history.zero_()
        self.history_initialized.zero_()
        self.last_leg_action.zero_()
        self.phase.zero_()
        self.episode_policy_steps = 0

    def _update_phase_for_current_obs(self) -> None:
        torch = self.torch
        standing = (torch.abs(self.physical_command) < self.standing_thresholds[None, :]).all(dim=1)
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
        frame[:, 39:42] = self.physical_command * self.command_obs_multipliers[None, :]
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
        self.last_leg_action = action
        self.current_joint_targets = self.default_joint_pos.clone()
        self.current_joint_targets[:, self.leg_joint_indices] = (
            self.default_leg_pos + action * self.contract["leg_action_scale"]
        )
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
            f"raw_cmd=({raw_command[0]:+.3f},{raw_command[1]:+.3f},{raw_command[2]:+.3f}) "
            "physical_cmd="
            f"({physical_command[0]:+.3f},{physical_command[1]:+.3f},{physical_command[2]:+.3f}) "
            f"phase={phase:.3f} action_norm={action_norm:.3f}",
            flush=True,
        )


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
    raw_command: tuple[float, float, float],
    physical_command: tuple[float, float, float],
) -> None:
    robot = scene["robot"]
    sim_dt = float(sim.get_physics_dt())
    policy_dt = sim_dt * float(args_cli.control_decimation)
    reset_flat_walk_scene(scene)

    policy = load_policy(args_cli.policy_path, args_cli.device)
    controller = A2BaseFlatWalkController(
        robot=robot,
        policy=policy,
        contract=contract,
        raw_command=raw_command,
        physical_command=physical_command,
        policy_dt=policy_dt,
    )

    count = 0
    next_policy_step = args_cli.warmup_steps
    print("[INFO]: A2_Base flat walk smoke reset complete.")
    print(f"[INFO]: Robot joint count={len(robot.joint_names)} names={robot.joint_names}")
    print(f"[INFO]: Robot body count={len(robot.body_names)}")
    print(
        "[INFO]: Timing "
        f"sim_dt={sim_dt:.4f} control_decimation={args_cli.control_decimation} "
        f"policy_dt={policy_dt:.4f} warmup_steps={args_cli.warmup_steps}"
    )

    while simulation_app.is_running():
        if args_cli.max_steps >= 0 and count >= args_cli.max_steps:
            break
        if args_cli.reset_interval > 0 and count > 0 and count % args_cli.reset_interval == 0:
            reset_flat_walk_scene(scene)
            controller.reset_buffers_from_robot()
            next_policy_step = count + args_cli.warmup_steps
            print("[INFO]: Periodic flat walk reset.", flush=True)

        if count >= next_policy_step and (count - next_policy_step) % args_cli.control_decimation == 0:
            action = controller.infer_policy_and_update_targets()
            if controller.should_log(args_cli.log_interval):
                controller.log_status(action)

        controller.write_targets()
        scene.write_data_to_sim()
        sim.step()
        scene.update(sim_dt)
        count += 1


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
