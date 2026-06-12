# Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import argparse
import gc
import os
import shutil
import sys
import traceback
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
DEFAULT_URDF_PATH = REPO_ROOT / "gr00t/rl/data/robots/A2_Piper/a2_piper.urdf"
DEFAULT_USD_PATH = REPO_ROOT / "gr00t/rl/data/robots/A2_Piper/a2_piper.usd"
ISAACLAB_ROOT = Path("/home/baoquanc/workspace/IsaacLab")
ISAACLAB_SH = ISAACLAB_ROOT / "isaaclab.sh"
ISAACLAB_PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
ISAACLAB_CONVERT_URDF = ISAACLAB_ROOT / "scripts/tools/convert_urdf.py"


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
        "IsaacLab is required to launch the A2_Piper door scene preview.\n"
        "This command was run with a Python environment that cannot import `isaaclab`.\n"
        "Use the validated conda IsaacLab Python, for example:\n"
        f"  CUDA_VISIBLE_DEVICES=2 PUBLIC_IP=10.120.16.39 LIVESTREAM=1 ENABLE_CAMERAS=1 "
        f"{ISAACLAB_PYTHON} {Path(__file__).resolve()} --num-envs 1 --device cuda:0\n"
        "Alternatively, use the IsaacLab wrapper if this shell has the expected Python PATH:\n"
        f"  CUDA_VISIBLE_DEVICES=2 PUBLIC_IP=10.120.16.39 LIVESTREAM=1 ENABLE_CAMERAS=1 "
        f"{ISAACLAB_SH} -p {Path(__file__).resolve()} --num-envs 1 --device cuda:0\n"
        "Plain `python3 ... --help` is supported for argument inspection only."
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preview the Doorman door scene with the A2_Piper robot in Isaac Sim."
    )
    parser.add_argument("--num-envs", "--num_envs", dest="num_envs", type=int, default=1)
    parser.add_argument("--env-spacing", "--env_spacing", dest="env_spacing", type=float, default=3.0)
    parser.add_argument("--root-x", "--stage0-x", dest="root_x", type=float, default=-0.9)
    parser.add_argument("--root-y", "--stage0-y", dest="root_y", type=float, default=0.0)
    parser.add_argument("--root-z", "--stage0-z", dest="root_z", type=float, default=0.55)
    parser.add_argument("--root-yaw", "--stage0-yaw", dest="root_yaw", type=float, default=0.0)
    parser.add_argument(
        "--placement-preview",
        choices=("none", "corners"),
        default="none",
        help="Preview robot placement bounds. `corners` shows four robots at the XY bound vertices.",
    )
    parser.add_argument(
        "--placement-bounds",
        choices=("doorman-stage0", "root-centered"),
        default="doorman-stage0",
        help="Bounds source for --placement-preview corners.",
    )
    parser.add_argument(
        "--show-placement-corners",
        action="store_true",
        help="Alias for --placement-preview corners.",
    )
    parser.add_argument(
        "--placement-x-half-range",
        type=float,
        default=0.35,
        help="Root-centered preview-only X half range around --root-x.",
    )
    parser.add_argument(
        "--placement-y-half-range",
        type=float,
        default=0.35,
        help="Root-centered preview-only Y half range around --root-y.",
    )
    parser.add_argument(
        "--placement-yaw-half-range",
        type=float,
        default=0.25,
        help="Root-centered preview-only yaw half range around --root-yaw when corner yaws use bounds.",
    )
    parser.add_argument(
        "--placement-corner-yaws",
        choices=("bounds", "uniform"),
        default="bounds",
        help="Use yaw min/max across placement corners, or keep all corner yaws at --root-yaw.",
    )
    parser.add_argument("--urdf-file", type=Path, default=DEFAULT_URDF_PATH)
    parser.add_argument("--usd-file", type=Path, default=DEFAULT_USD_PATH)
    parser.add_argument(
        "--generate-usd",
        action="store_true",
        help="Generate A2_Piper/a2_piper.usd from the URDF before opening the preview.",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=-1,
        help="Maximum sim steps to run. Use a small value for smoke tests; -1 runs until closed.",
    )
    parser.add_argument(
        "--reset-interval",
        type=int,
        default=500,
        help="Sim steps between preview resets. Set <=0 to disable periodic resets.",
    )
    AppLauncher = import_app_launcher()
    if AppLauncher is None:
        add_fallback_app_launcher_args(parser)
    else:
        AppLauncher.add_app_launcher_args(parser)
    return parser.parse_args()


def normalize_placement_preview_args(args_cli: argparse.Namespace) -> None:
    if args_cli.show_placement_corners:
        args_cli.placement_preview = "corners"

    for attr_name in (
        "placement_x_half_range",
        "placement_y_half_range",
        "placement_yaw_half_range",
    ):
        if getattr(args_cli, attr_name) < 0.0:
            raise ValueError(f"--{attr_name.replace('_', '-')} must be non-negative.")

    if args_cli.placement_preview == "corners" and args_cli.num_envs != 4:
        print(
            "[INFO]: Placement corner preview uses four envs; "
            f"overriding --num-envs {args_cli.num_envs} -> 4."
        )
        args_cli.num_envs = 4


def validate_preview_cuda_device(args_cli: argparse.Namespace) -> None:
    device = str(getattr(args_cli, "device", "")).strip().lower()
    if not device.startswith("cuda:"):
        return

    device_index = device.removeprefix("cuda:")
    if not device_index.isdigit() or int(device_index) == 0:
        return

    raise ValueError(
        "A2_Piper door scene preview uses IsaacSim/UsdRT camera/livestream preview, "
        "which currently supports only logical cuda:0.\n"
        f"To use physical GPU {device_index}, expose it as logical GPU 0 and pass --device cuda:0:\n"
        f"  CUDA_VISIBLE_DEVICES={device_index} ... --device cuda:0"
    )


def env_flag_enabled(name: str) -> bool:
    return os.environ.get(name, "0") in {"1", "true", "True", "YES", "yes"}


def maybe_use_repo_rendering_experience(args_cli: argparse.Namespace) -> None:
    cameras_requested = args_cli.enable_cameras or env_flag_enabled("ENABLE_CAMERAS")
    headless_requested = (
        args_cli.headless
        or env_flag_enabled("HEADLESS")
        or os.environ.get("LIVESTREAM", "0") in {"1", "2"}
    )
    if not (cameras_requested and headless_requested):
        return

    isaaclab_rendering_kit = ISAACLAB_ROOT / "apps/isaaclab.python.headless.rendering.kit"
    if isaaclab_rendering_kit.is_file():
        args_cli.experience = str(isaaclab_rendering_kit)
        return

    repo_rendering_kit = REPO_ROOT / "gr00t/rl/apps/phc.isaaclab.python.headless.rendering.kit"
    if repo_rendering_kit.is_file():
        args_cli.experience = str(repo_rendering_kit)


def conversion_command(urdf_path: Path, usd_path: Path, device: str) -> str:
    conversion_args = (
        f"{ISAACLAB_CONVERT_URDF} "
        f"{urdf_path} {usd_path} --joint-stiffness 0.0 "
        f"--joint-damping 0.0 --joint-target-type position --headless --device {device}"
    )
    if ISAACLAB_PYTHON.is_file():
        return f"{ISAACLAB_PYTHON} {conversion_args}"
    return f"{ISAACLAB_SH} -p {conversion_args}"


def ensure_a2_piper_usd(urdf_path: Path, usd_path: Path, generate_usd: bool, device: str) -> None:
    if usd_path.is_file():
        return

    if not generate_usd:
        raise FileNotFoundError(
            "A2_Piper USD is required for preview and no G1 fallback is allowed.\n"
            f"Missing: {usd_path}\n"
            "Generate it with either:\n"
            f"  {conversion_command(urdf_path, usd_path, device)}\n"
            "or rerun this preview with --generate-usd."
        )

    if not urdf_path.is_file():
        raise FileNotFoundError(f"A2_Piper URDF not found: {urdf_path}")

    from isaaclab.sim.converters import UrdfConverter, UrdfConverterCfg

    usd_path.parent.mkdir(parents=True, exist_ok=True)
    converter_cfg = UrdfConverterCfg(
        asset_path=str(urdf_path.resolve()),
        usd_dir=str(usd_path.parent.resolve()),
        usd_file_name=usd_path.name,
        fix_base=False,
        merge_fixed_joints=False,
        force_usd_conversion=True,
        joint_drive=UrdfConverterCfg.JointDriveCfg(
            gains=UrdfConverterCfg.JointDriveCfg.PDGainsCfg(stiffness=0.0, damping=0.0),
            target_type="position",
        ),
        self_collision=False,
        replace_cylinders_with_capsules=False,
    )
    print(f"[INFO]: Generating A2_Piper USD from URDF: {urdf_path}")
    converter = UrdfConverter(converter_cfg)
    generated_path = Path(converter.usd_path)
    if generated_path.resolve() != usd_path.resolve() and generated_path.is_file():
        shutil.copy(generated_path, usd_path)
    if not usd_path.is_file():
        raise RuntimeError(
            "URDF conversion completed but expected USD was not created.\n"
            f"Expected: {usd_path}\n"
            f"Standalone command: {conversion_command(urdf_path, usd_path, device)}"
        )
    print(f"[INFO]: Generated A2_Piper USD: {usd_path}")


def _run_cleanup_method(obj: object | None, method_name: str) -> BaseException | None:
    if obj is None:
        print(f"[INFO]: Preview cleanup skipped `{method_name}`; object is not available.", flush=True)
        return None
    method = getattr(obj, method_name, None)
    if method is None:
        print(f"[INFO]: Preview cleanup skipped `{method_name}`; method is not available.", flush=True)
        return None

    try:
        print(f"[INFO]: Preview cleanup starting `{method_name}`.", flush=True)
        method()
        print(f"[INFO]: Preview cleanup finished `{method_name}`.", flush=True)
    except Exception as exc:
        print(f"[WARN]: Preview cleanup `{method_name}` failed: {exc}", file=sys.stderr, flush=True)
        traceback.print_exception(exc, file=sys.stderr)
        return exc
    return None


def cleanup_preview_before_app_close(sim: object | None, had_scene: bool) -> list[BaseException]:
    """Run public IsaacLab cleanup hooks before SimulationApp.close()."""
    cleanup_errors: list[BaseException] = []

    if had_scene:
        print("[INFO]: Preview cleanup released scene reference; running gc.", flush=True)
    else:
        print("[INFO]: Preview cleanup has no scene reference to release; running gc.", flush=True)
    gc.collect()
    print("[INFO]: Preview cleanup finished scene gc.", flush=True)

    for method_name in ("clear", "clear_all_callbacks", "clear_instance"):
        cleanup_error = _run_cleanup_method(sim, method_name)
        if cleanup_error is not None:
            cleanup_errors.append(cleanup_error)

    sim = None
    print("[INFO]: Preview cleanup released sim reference; running gc.", flush=True)
    gc.collect()
    print("[INFO]: Preview cleanup finished sim gc.", flush=True)
    return cleanup_errors


def patch_app_launcher_toolbar_hiding(AppLauncher: type) -> None:
    """Skip optional IsaacLab toolbar hiding when this Kit lacks the toolbar widget."""
    if getattr(AppLauncher, "_a2_piper_toolbar_hiding_patch_applied", False):
        return

    missing_module = "omni.kit.widget.toolbar"

    def is_missing_toolbar_module(exc: ModuleNotFoundError) -> bool:
        return exc.name == missing_module

    def make_wrapper(method_name: str, original_method):
        def wrapped(self, *args, **kwargs):
            try:
                return original_method(self, *args, **kwargs)
            except ModuleNotFoundError as exc:
                if not is_missing_toolbar_module(exc):
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
    setattr(AppLauncher, "_a2_piper_toolbar_hiding_patch_applied", True)


def main() -> int:
    args_cli = parse_args()
    normalize_placement_preview_args(args_cli)
    validate_preview_cuda_device(args_cli)
    AppLauncher = require_app_launcher()
    patch_app_launcher_toolbar_hiding(AppLauncher)
    if not args_cli.generate_usd:
        ensure_a2_piper_usd(
            urdf_path=args_cli.urdf_file,
            usd_path=args_cli.usd_file,
            generate_usd=False,
            device=args_cli.device,
        )
    maybe_use_repo_rendering_experience(args_cli)

    sim = None
    scene = None
    simulation_app = None
    run_error = None
    app_launcher = AppLauncher(args_cli)
    simulation_app = app_launcher.app

    try:
        if args_cli.generate_usd:
            ensure_a2_piper_usd(
                urdf_path=args_cli.urdf_file,
                usd_path=args_cli.usd_file,
                generate_usd=True,
                device=args_cli.device,
            )

        from gr00t.rl.envs.door.a2_piper_door_scene_preview import (
            build_corner_root_poses,
            create_preview_scene,
            run_zero_action_hold,
        )

        enable_camera = args_cli.enable_cameras or env_flag_enabled("ENABLE_CAMERAS")
        robot_root_poses = None
        if args_cli.placement_preview == "corners":
            robot_root_poses = build_corner_root_poses(
                bounds_mode=args_cli.placement_bounds,
                center_x=args_cli.root_x,
                center_y=args_cli.root_y,
                center_z=args_cli.root_z,
                center_yaw=args_cli.root_yaw,
                x_half_range=args_cli.placement_x_half_range,
                y_half_range=args_cli.placement_y_half_range,
                yaw_half_range=args_cli.placement_yaw_half_range,
                yaw_mode=args_cli.placement_corner_yaws,
            )

        sim, scene = create_preview_scene(
            usd_path=args_cli.usd_file,
            num_envs=args_cli.num_envs,
            env_spacing=args_cli.env_spacing,
            device=args_cli.device,
            root_x=args_cli.root_x,
            root_y=args_cli.root_y,
            root_z=args_cli.root_z,
            root_yaw=args_cli.root_yaw,
            enable_camera=enable_camera,
        )
        print(
            "[INFO]: Preview pose "
            f"x={args_cli.root_x} y={args_cli.root_y} z={args_cli.root_z} yaw={args_cli.root_yaw}"
        )
        if robot_root_poses is not None:
            xs = [pose[0] for pose in robot_root_poses]
            ys = [pose[1] for pose in robot_root_poses]
            zs = [pose[2] for pose in robot_root_poses]
            yaws = [pose[3] for pose in robot_root_poses]
            print(
                "[INFO]: Placement preview corners "
                f"bounds={args_cli.placement_bounds} "
                f"x=[{min(xs)}, {max(xs)}] "
                f"y=[{min(ys)}, {max(ys)}] "
                f"z={zs[0]} "
                f"yaw=[{min(yaws)}, {max(yaws)}] "
                f"corner_yaws={args_cli.placement_corner_yaws}"
            )
        run_zero_action_hold(
            sim,
            scene,
            simulation_app,
            max_steps=args_cli.max_steps,
            reset_interval=args_cli.reset_interval,
            robot_root_poses=robot_root_poses,
        )
    except BaseException as exc:
        run_error = exc
        traceback.print_exception(exc, file=sys.stderr)
    finally:
        had_scene = scene is not None
        scene = None
        cleanup_errors = cleanup_preview_before_app_close(sim=sim, had_scene=had_scene)
        if cleanup_errors and run_error is None:
            run_error = cleanup_errors[0]
        sim = None
        gc.collect()
        if simulation_app is not None:
            try:
                print("[INFO]: Preview cleanup starting `SimulationApp.close`.", flush=True)
                simulation_app.close()
                print("[INFO]: Preview cleanup finished `SimulationApp.close`.", flush=True)
            except BaseException as exc:
                if run_error is None:
                    run_error = exc
                    traceback.print_exception(exc, file=sys.stderr)
                else:
                    print(
                        "[WARN]: SimulationApp.close() failed after an earlier preview error:",
                        file=sys.stderr,
                        flush=True,
                    )
                    traceback.print_exception(exc, file=sys.stderr)
        if run_error is not None:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
