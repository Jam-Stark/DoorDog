#!/usr/bin/env python3
"""Run the bounded same-step A2 student camera transform probe for R14."""

from __future__ import annotations

import argparse
import gc
import json
import math
import os
import random
import sys
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

CONFIG_DIR = REPO_ROOT / "gr00t/rl/config"
HEADLESS_CAMERA_EXPERIENCE = (
    REPO_ROOT / "gr00t/rl/apps/phc.isaaclab.python.headless.rendering.kit"
)
ISAACLAB_PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
DEFAULT_OUTPUT = Path("/tmp/a2_student_camera_transform_probe.json")
TRUNK_PRIM_PATH = "/World/envs/env_.*/Robot/trunk"
CAMERA_PRIM_PATH = "/World/envs/env_.*/Robot/trunk/ego_camera"

LIVE_POSITION_METRICS = (
    "parent_robot_xform_position_max_m",
    "camera_local_config_position_max_m",
    "camera_prim_expected_position_max_m",
    "camera_forced_data_prim_position_max_m",
)
LIVE_ORIENTATION_METRICS = (
    "parent_robot_xform_orientation_max_rad",
    "camera_local_config_orientation_max_rad",
    "camera_prim_expected_orientation_max_rad",
    "camera_forced_data_prim_orientation_max_rad",
)


def import_app_launcher():
    try:
        from isaaclab.app import AppLauncher
    except ModuleNotFoundError as exc:
        if exc.name != "isaaclab":
            raise
        return None
    return AppLauncher


def add_fallback_app_launcher_args(parser: argparse.ArgumentParser) -> None:
    group = parser.add_argument_group("IsaacLab AppLauncher arguments")
    group.add_argument("--headless", action="store_true", default=False)
    group.add_argument("--enable_cameras", action="store_true", default=False)
    group.add_argument("--device", type=str, default="cuda:0")
    group.add_argument("--livestream", type=int, default=-1)
    group.add_argument("--experience", type=str, default="")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--settle-steps", type=int, default=2)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--position-tolerance-m", type=float, default=1.0e-4)
    parser.add_argument("--orientation-tolerance-rad", type=float, default=5.0e-4)
    parser.add_argument("--stale-position-threshold-m", type=float, default=1.0e-2)
    AppLauncher = import_app_launcher()
    if AppLauncher is None:
        add_fallback_app_launcher_args(parser)
    else:
        AppLauncher.add_app_launcher_args(parser)
    return parser.parse_args()


def normalize_args(args_cli: argparse.Namespace) -> None:
    if args_cli.settle_steps <= 0:
        raise ValueError(f"--settle-steps must be positive, got {args_cli.settle_steps}")
    if args_cli.position_tolerance_m <= 0.0:
        raise ValueError(
            "--position-tolerance-m must be positive, "
            f"got {args_cli.position_tolerance_m}"
        )
    if args_cli.orientation_tolerance_rad <= 0.0:
        raise ValueError(
            "--orientation-tolerance-rad must be positive, "
            f"got {args_cli.orientation_tolerance_rad}"
        )
    if args_cli.stale_position_threshold_m <= args_cli.position_tolerance_m:
        raise ValueError(
            "--stale-position-threshold-m must exceed --position-tolerance-m; "
            f"got {args_cli.stale_position_threshold_m} <= {args_cli.position_tolerance_m}"
        )
    if str(args_cli.device).lower() != "cuda:0":
        raise ValueError(
            "The R14 camera probe requires logical cuda:0. Map a physical GPU with "
            "CUDA_VISIBLE_DEVICES=N instead of passing another logical device."
        )
    if not HEADLESS_CAMERA_EXPERIENCE.is_file():
        raise FileNotFoundError(
            "The R14 camera probe requires the repository headless camera experience: "
            f"{HEADLESS_CAMERA_EXPERIENCE}"
        )

    args_cli.output = args_cli.output.expanduser().resolve()
    args_cli.headless = True
    args_cli.enable_cameras = True
    args_cli.livestream = 0
    args_cli.experience = str(HEADLESS_CAMERA_EXPERIENCE)


def require_app_launcher():
    AppLauncher = import_app_launcher()
    if AppLauncher is not None:
        return AppLauncher
    raise RuntimeError(
        "IsaacLab is required for the R14 transform probe. Run:\n"
        f"  CUDA_VISIBLE_DEVICES=0 {ISAACLAB_PYTHON} {Path(__file__).resolve()} "
        "--device cuda:0"
    )


def patch_app_launcher_toolbar_hiding(AppLauncher: type) -> None:
    """Skip optional toolbar hiding when the headless Kit omits that widget."""
    if getattr(AppLauncher, "_a2_r14_toolbar_hiding_patch_applied", False):
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
                    f"[WARN]: AppLauncher `{method_name}` skipped because "
                    f"`{missing_module}` is unavailable.",
                    file=sys.stderr,
                    flush=True,
                )
                return None

        return wrapped

    for method_name in ("_hide_stop_button", "_hide_play_button"):
        original_method = getattr(AppLauncher, method_name, None)
        if original_method is not None:
            setattr(AppLauncher, method_name, make_wrapper(method_name, original_method))
    setattr(AppLauncher, "_a2_r14_toolbar_hiding_patch_applied", True)


def classify_transform_probe(
    metrics: dict[str, float],
    *,
    update_latest_camera_pose_before: bool,
    position_tolerance_m: float,
    orientation_tolerance_rad: float,
    stale_position_threshold_m: float,
) -> dict[str, object]:
    expected_keys = set(LIVE_POSITION_METRICS + LIVE_ORIENTATION_METRICS) | {
        "camera_cached_data_prim_position_max_m",
        "camera_cached_data_prim_orientation_max_rad",
    }
    if set(metrics) != expected_keys:
        raise ValueError(
            "R14 transform metrics must match the exact probe schema; "
            f"missing={sorted(expected_keys - set(metrics))} "
            f"unexpected={sorted(set(metrics) - expected_keys)}"
        )
    if type(update_latest_camera_pose_before) is not bool:
        raise TypeError("update_latest_camera_pose_before must be an exact bool")
    non_finite = sorted(name for name, value in metrics.items() if not math.isfinite(value))
    if non_finite:
        raise ValueError(f"R14 transform metrics must be finite; non_finite={non_finite}")

    checks = {
        "default_pose_cache_disabled": update_latest_camera_pose_before is False,
        "live_positions_close": all(
            metrics[name] <= position_tolerance_m for name in LIVE_POSITION_METRICS
        ),
        "live_orientations_close": all(
            metrics[name] <= orientation_tolerance_rad
            for name in LIVE_ORIENTATION_METRICS
        ),
        "cached_pose_materially_stale": (
            metrics["camera_cached_data_prim_position_max_m"]
            >= stale_position_threshold_m
        ),
    }
    live_contract_closed = (
        checks["default_pose_cache_disabled"]
        and checks["live_positions_close"]
        and checks["live_orientations_close"]
    )
    if live_contract_closed and checks["cached_pose_materially_stale"]:
        status = "PASS"
        resolution = "R14_STALE_INITIALIZATION_POSE_CONFIRMED"
    elif live_contract_closed:
        status = "INCONCLUSIVE"
        resolution = "R14_NOT_REPRODUCED_IN_CURRENT_RESET"
    else:
        status = "FAIL"
        resolution = "R14_LIVE_TRANSFORM_CONTRACT_MISMATCH"
    return {"status": status, "resolution": resolution, "checks": checks}


def _max_position_error(lhs: "torch.Tensor", rhs: "torch.Tensor") -> float:
    import torch

    return float(torch.linalg.vector_norm(lhs - rhs, dim=-1).max().detach().cpu().item())


def _max_orientation_error(
    quat_error_magnitude, lhs: "torch.Tensor", rhs: "torch.Tensor"
) -> float:
    return float(quat_error_magnitude(lhs, rhs).max().detach().cpu().item())


def _tensor_list(value: "torch.Tensor") -> list:
    return value.detach().cpu().tolist()


def compose_probe_config(output_path: Path):
    from hydra import compose, initialize_config_dir

    from gr00t.rl.utils.config_utils import register_rl_resolvers
    from gr00t.rl.utils.helpers import pre_process_config

    register_rl_resolvers()
    with initialize_config_dir(version_base="1.1", config_dir=str(CONFIG_DIR.resolve())):
        config = compose(
            config_name="base",
            overrides=[
                "+exp=wbmanip/door_open_a2_base_dagger-lstm",
                "num_envs=1",
                "headless=true",
                "use_wandb=false",
            ],
        )
    config.experiment_name = "r14_same_step_camera_transform_probe"
    config.experiment_dir = str(output_path.parent / "r14_probe_runtime")
    config.env.config.save_rendering_dir = str(output_path.parent / "r14_probe_renderings")
    config.env.config.experiment_dir = config.experiment_dir
    pre_process_config(config)
    return config


def collect_same_step_transform_evidence(env, args_cli: argparse.Namespace) -> dict:
    import torch

    from isaaclab.sim.views import XformPrimView
    from isaaclab.utils.math import (
        combine_frame_transforms,
        convert_camera_frame_orientation_convention,
        quat_error_magnitude,
    )

    simulator = env.simulator
    camera = simulator.ego_camera
    if camera is None:
        raise RuntimeError("R14 transform probe requires simulator.ego_camera")
    if int(env.num_envs) != 1:
        raise RuntimeError(f"R14 transform probe requires exactly one env, got {env.num_envs}")

    if camera.cfg.prim_path != CAMERA_PRIM_PATH:
        raise RuntimeError(
            "R14 transform probe camera prim path mismatch; "
            f"configured={camera.cfg.prim_path!r} expected={CAMERA_PRIM_PATH!r}"
        )
    camera_view = camera._view
    if not isinstance(camera_view, XformPrimView):
        raise RuntimeError(
            "R14 transform probe requires TiledCamera._view to be an initialized "
            f"XformPrimView; got {type(camera_view).__name__}"
        )
    trunk_view = XformPrimView(TRUNK_PRIM_PATH, device=str(simulator.sim_device))
    if trunk_view.count != 1 or camera_view.count != 1:
        raise RuntimeError(
            "R14 transform probe requires one trunk and one camera prim; "
            f"trunk_count={trunk_view.count} camera_count={camera_view.count}"
        )

    # XformPrimView performs a one-time USD-to-Fabric sync on its first world-pose read.
    # Prime the parent view before reset. Reuse TiledCamera's already initialized camera
    # view: creating a second view for the same camera path can resync the shared Fabric
    # matrix from authored USD and contaminate the live diagnostic.
    initial_trunk_prim_pos, initial_trunk_prim_quat = trunk_view.get_world_poses()
    initial_camera_prim_pos, initial_camera_prim_quat_opengl = camera_view.get_world_poses()
    initial_trunk_prim_pos = initial_trunk_prim_pos.clone()
    initial_trunk_prim_quat = initial_trunk_prim_quat.clone()
    initial_camera_prim_pos = initial_camera_prim_pos.clone()
    initial_camera_prim_quat_opengl = initial_camera_prim_quat_opengl.clone()
    camera_local_pos, camera_local_quat_opengl = camera_view.get_local_poses()
    initial_camera_prim_quat_world = convert_camera_frame_orientation_convention(
        initial_camera_prim_quat_opengl, origin="opengl", target="world"
    )
    camera_local_quat_world = convert_camera_frame_orientation_convention(
        camera_local_quat_opengl, origin="opengl", target="world"
    )

    env.reset()
    for _ in range(args_cli.settle_steps):
        simulator.simulate_at_each_physics_step()
    env._refresh_sim_tensors()

    update_latest_camera_pose_before = camera.cfg.update_latest_camera_pose
    cached_camera_pos = camera.data.pos_w.clone()
    cached_camera_quat = camera.data.quat_w_world.clone()
    cached_frame = camera.frame.clone()
    physics_step_before_force = int(simulator._sim_step_counter)
    camera.cfg.update_latest_camera_pose = True
    try:
        camera.update(dt=0.0, force_recompute=True)
        forced_frame = camera.frame.clone()
        forced_camera_pos = camera.data.pos_w.clone()
        forced_camera_quat = camera.data.quat_w_world.clone()
    finally:
        camera.cfg.update_latest_camera_pose = update_latest_camera_pose_before
    physics_step_after_force = int(simulator._sim_step_counter)
    if physics_step_after_force != physics_step_before_force:
        raise RuntimeError(
            "R14 forced camera refresh advanced the physics step counter: "
            f"{physics_step_before_force} -> {physics_step_after_force}"
        )
    if not torch.equal(forced_frame, cached_frame + 1):
        raise RuntimeError(
            "R14 forced camera refresh must advance exactly one sensor frame; "
            f"cached={_tensor_list(cached_frame)} forced={_tensor_list(forced_frame)}"
        )

    robot_parent_pos = simulator._robot.data.body_pos_w[
        :, simulator.camera_body_id, :
    ].clone()
    robot_parent_quat = simulator._robot.data.body_quat_w[
        :, simulator.camera_body_id, :
    ].clone()
    trunk_prim_pos, trunk_prim_quat = trunk_view.get_world_poses()
    camera_prim_pos, camera_prim_quat_opengl = camera_view.get_world_poses()
    trunk_prim_pos = trunk_prim_pos.clone()
    trunk_prim_quat = trunk_prim_quat.clone()
    camera_prim_pos = camera_prim_pos.clone()
    camera_prim_quat_opengl = camera_prim_quat_opengl.clone()
    camera_prim_quat_world = convert_camera_frame_orientation_convention(
        camera_prim_quat_opengl, origin="opengl", target="world"
    )

    cameras_cfg = simulator.simulator_config.cameras
    configured_pos = torch.tensor(
        cameras_cfg.camera_pos,
        device=trunk_prim_pos.device,
        dtype=trunk_prim_pos.dtype,
    ).reshape(1, 3)
    configured_quat = torch.tensor(
        cameras_cfg.camera_rot_wxyz,
        device=trunk_prim_quat.device,
        dtype=trunk_prim_quat.dtype,
    ).reshape(1, 4)
    expected_camera_pos, expected_camera_quat = combine_frame_transforms(
        trunk_prim_pos,
        trunk_prim_quat,
        configured_pos,
        configured_quat,
    )

    metrics = {
        "parent_robot_xform_position_max_m": _max_position_error(
            robot_parent_pos, trunk_prim_pos
        ),
        "parent_robot_xform_orientation_max_rad": _max_orientation_error(
            quat_error_magnitude, robot_parent_quat, trunk_prim_quat
        ),
        "camera_local_config_position_max_m": _max_position_error(
            camera_local_pos, configured_pos
        ),
        "camera_local_config_orientation_max_rad": _max_orientation_error(
            quat_error_magnitude, camera_local_quat_world, configured_quat
        ),
        "camera_prim_expected_position_max_m": _max_position_error(
            camera_prim_pos, expected_camera_pos
        ),
        "camera_prim_expected_orientation_max_rad": _max_orientation_error(
            quat_error_magnitude, camera_prim_quat_world, expected_camera_quat
        ),
        "camera_cached_data_prim_position_max_m": _max_position_error(
            cached_camera_pos, camera_prim_pos
        ),
        "camera_cached_data_prim_orientation_max_rad": _max_orientation_error(
            quat_error_magnitude, cached_camera_quat, camera_prim_quat_world
        ),
        "camera_forced_data_prim_position_max_m": _max_position_error(
            forced_camera_pos, camera_prim_pos
        ),
        "camera_forced_data_prim_orientation_max_rad": _max_orientation_error(
            quat_error_magnitude, forced_camera_quat, camera_prim_quat_world
        ),
    }
    verdict = classify_transform_probe(
        metrics,
        update_latest_camera_pose_before=update_latest_camera_pose_before,
        position_tolerance_m=args_cli.position_tolerance_m,
        orientation_tolerance_rad=args_cli.orientation_tolerance_rad,
        stale_position_threshold_m=args_cli.stale_position_threshold_m,
    )
    return {
        "schema_version": 1,
        "probe": "a2_student_camera_same_step_transform_r14",
        **verdict,
        "runtime": {
            "torch_version": str(torch.__version__),
            "device": str(simulator.sim_device),
            "seed": int(args_cli.seed),
            "settle_steps": int(args_cli.settle_steps),
        },
        "prim_paths": {"parent": TRUNK_PRIM_PATH, "camera": CAMERA_PRIM_PATH},
        "camera_contract": {
            "update_latest_camera_pose_before": update_latest_camera_pose_before,
            "update_latest_camera_pose_restored": camera.cfg.update_latest_camera_pose,
            "configured_pos": _tensor_list(configured_pos),
            "configured_quat_wxyz_world": _tensor_list(configured_quat),
        },
        "frames": {
            "cached": _tensor_list(cached_frame),
            "forced_same_step": _tensor_list(forced_frame),
            "physics_step_before_force": physics_step_before_force,
            "physics_step_after_force": physics_step_after_force,
        },
        "samples": {
            "initial_trunk_prim_pos_w": _tensor_list(initial_trunk_prim_pos),
            "initial_trunk_prim_quat_wxyz": _tensor_list(initial_trunk_prim_quat),
            "initial_camera_prim_pos_w": _tensor_list(initial_camera_prim_pos),
            "initial_camera_prim_quat_wxyz_world": _tensor_list(
                initial_camera_prim_quat_world
            ),
            "robot_parent_pos_w": _tensor_list(robot_parent_pos),
            "robot_parent_quat_wxyz": _tensor_list(robot_parent_quat),
            "trunk_prim_pos_w": _tensor_list(trunk_prim_pos),
            "trunk_prim_quat_wxyz": _tensor_list(trunk_prim_quat),
            "camera_local_pos": _tensor_list(camera_local_pos),
            "camera_local_quat_wxyz_world": _tensor_list(camera_local_quat_world),
            "expected_camera_pos_w": _tensor_list(expected_camera_pos),
            "expected_camera_quat_wxyz_world": _tensor_list(expected_camera_quat),
            "camera_prim_pos_w": _tensor_list(camera_prim_pos),
            "camera_prim_quat_wxyz_world": _tensor_list(camera_prim_quat_world),
            "cached_camera_data_pos_w": _tensor_list(cached_camera_pos),
            "cached_camera_data_quat_wxyz_world": _tensor_list(cached_camera_quat),
            "forced_camera_data_pos_w": _tensor_list(forced_camera_pos),
            "forced_camera_data_quat_wxyz_world": _tensor_list(forced_camera_quat),
        },
        "thresholds": {
            "position_tolerance_m": float(args_cli.position_tolerance_m),
            "orientation_tolerance_rad": float(args_cli.orientation_tolerance_rad),
            "stale_position_threshold_m": float(args_cli.stale_position_threshold_m),
        },
        "metrics": metrics,
    }


def seal_probe_evidence(output_path: Path, evidence: dict) -> None:
    if output_path.exists():
        raise FileExistsError(f"R14 probe refuses to overwrite existing evidence: {output_path}")
    serialized = json.dumps(evidence, indent=2, sort_keys=True, allow_nan=False) + "\n"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(f".{output_path.name}.tmp")
    if temporary_path.exists():
        raise FileExistsError(f"R14 probe temporary evidence path already exists: {temporary_path}")
    with temporary_path.open("x", encoding="utf-8") as stream:
        stream.write(serialized)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary_path, output_path)


def main() -> int:
    args_cli = parse_args()
    try:
        normalize_args(args_cli)
        AppLauncher = require_app_launcher()
        patch_app_launcher_toolbar_hiding(AppLauncher)
    except BaseException as exc:
        traceback.print_exception(exc, file=sys.stderr)
        return 1

    random.seed(args_cli.seed)
    env = None
    simulation_app = None
    exit_code = 1
    app_launcher = AppLauncher(args_cli)
    simulation_app = app_launcher.app
    try:
        import torch

        torch.manual_seed(args_cli.seed)
        from gr00t.rl.trl.utils.common import custom_instantiate

        config = compose_probe_config(args_cli.output)
        env = custom_instantiate(config.env, device=args_cli.device, _resolve=False)
        evidence = collect_same_step_transform_evidence(env, args_cli)
        seal_probe_evidence(args_cli.output, evidence)
        print(
            json.dumps(
                {
                    "status": evidence["status"],
                    "resolution": evidence["resolution"],
                    "metrics": evidence["metrics"],
                },
                sort_keys=True,
            ),
            flush=True,
        )
        print(f"[R14_EVIDENCE_SEALED] {args_cli.output}", flush=True)
        exit_code = 0 if evidence["status"] == "PASS" else 2
    except BaseException as exc:
        traceback.print_exception(exc, file=sys.stderr)
        exit_code = 1
    finally:
        env = None
        gc.collect()
        if simulation_app is not None:
            try:
                print("[R14_LIFECYCLE] simulation_app_close_start", flush=True)
                simulation_app.close(wait_for_replicator=False)
                print("[R14_LIFECYCLE] simulation_app_close_complete", flush=True)
            except BaseException as exc:
                traceback.print_exception(exc, file=sys.stderr)
                exit_code = 1
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
