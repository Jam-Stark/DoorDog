#!/usr/bin/env python3
"""Read one live full-A2 OrderedTargetFrameTransformer case at neutral reset."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BASE_CONFIG = ROOT / "logs_rl/by_batch/base_v26_4_r2_bilateral_grasp_foundation_20260828/main/C0_CANONICAL_OFF_S0/config.yaml"


def args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--factor", choices=("O0", "O1"), required=True)
    parser.add_argument("--side", choices=("left", "right"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    from isaaclab.app import AppLauncher
    AppLauncher.add_app_launcher_args(parser)
    return parser.parse_args()


def oracle(scene, sensor, torch) -> tuple[object, list[dict[str, object]]]:
    from isaaclab.utils.math import quat_from_matrix
    from omni.usd import get_context
    from pxr import Gf, UsdGeom
    stage, cache = get_context().get_stage(), UsdGeom.XformCache()
    rows = []
    matrices = []
    for env_id in range(sensor.data.target_quat_w.shape[0]):
        base = f"/World/envs/env_{env_id}/door"
        panel = stage.GetPrimAtPath(f"{base}/door_panel")
        joint = stage.GetPrimAtPath(f"{base}/door_panel/handle_joint")
        grasp = stage.GetPrimAtPath(f"{base}/grasp_target")
        if not panel.IsValid() or not joint.IsValid() or not grasp.IsValid():
            raise RuntimeError(f"runtime target oracle missing authored geometry in env_{env_id}")
        local_rot = joint.GetAttribute("physics:localRot0").Get()
        local_pos = joint.GetAttribute("physics:localPos0").Get()
        if local_rot is None or local_pos is None:
            raise RuntimeError(f"runtime target oracle missing LocalRot0/LocalPos0 env_{env_id}")
        panel_xf = cache.GetLocalToWorldTransform(panel)
        axis = panel_xf.TransformDir(Gf.Rotation(Gf.Quatd(local_rot)).TransformDir(Gf.Vec3d(1.0, 0.0, 0.0)))
        origin = panel_xf.Transform(Gf.Vec3d(local_pos)); grasp_pos = cache.GetLocalToWorldTransform(grasp).ExtractTranslation()
        def unit(values: list[float]) -> list[float]:
            norm = math.sqrt(sum(value * value for value in values))
            if not math.isfinite(norm) or norm <= 0.0:
                raise RuntimeError(f"runtime target oracle degenerate basis env_{env_id}")
            return [value / norm for value in values]
        def cross(a: list[float], b: list[float]) -> list[float]:
            return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]
        axis_world = unit([float(axis[index]) for index in range(3)])
        opening = 1.0 if float(Gf.Rotation(Gf.Quatd(local_rot)).TransformDir(Gf.Vec3d(1.0, 0.0, 0.0))[0]) > 0.0 else -1.0
        x = unit([float(origin[index]) - float(grasp_pos[index]) - sum((float(origin[j]) - float(grasp_pos[j])) * axis_world[j] for j in range(3)) * axis_world[index] for index in range(3)])
        z = [opening * value for value in axis_world]; y = unit(cross(z, x))
        if max(abs(sum(a*b for a,b in zip(left,right,strict=True))) for left,right in ((x,y),(y,z),(z,x))) > 1e-6:
            raise RuntimeError(f"runtime target oracle not orthogonal env_{env_id}")
        matrices.append([[x[0],y[0],z[0]],[x[1],y[1],z[1]],[x[2],y[2],z[2]]])
        rows.append({"env_id": env_id, "local_rot0_wxyz": [float(local_rot.GetReal()), *[float(v) for v in local_rot.GetImaginary()]], "local_pos0_m": [float(v) for v in local_pos]})
    return quat_from_matrix(torch.tensor(matrices, device=sensor.device, dtype=sensor.data.target_quat_w.dtype)), rows


def main(a: argparse.Namespace) -> None:
    if a.output.exists():
        raise RuntimeError(f"refusing to overwrite runtime contract case: {a.output}")
    from isaaclab.app import AppLauncher
    app = AppLauncher(a).app
    try:
        from hydra.utils import instantiate
        from omegaconf import OmegaConf
        from gr00t.rl.utils.helpers import pre_process_config
        import torch
        cfg = OmegaConf.load(BASE_CONFIG)
        cfg.num_envs = 2; cfg.seed = 0; cfg.headless = True
        cfg.env.config.a2_v26_door_open_lr = a.side
        cfg.env.config.a2_v26_side_permutation_seed = 0
        cfg.env.config.a2_v26_4_side_canonicalization_enabled = False
        cfg.env.config.a2_v26_5_geometry_target_enabled = a.factor == "O1"
        cfg.env.config.a2_v26_5_stage3_delta_rebase_enabled = False
        cfg.simulator.config.render_results = False; cfg.simulator.config.cameras.enable_cameras = False
        pre_process_config(cfg)
        env = instantiate(config=cfg.env, device=a.device)
        env.reset()
        sensor = env.simulator.scene.sensors[env.A2_GRIPPER_HANDLE_FRAME_TRANSFORMER]
        data = sensor.data
        names = list(data.target_frame_names)
        if names != ["handle", "pregrasp"]:
            raise RuntimeError(f"live target frame order mismatch: {names!r}")
        for name, value, shape in (("target_pos_w", data.target_pos_w, (2, 2, 3)), ("target_quat_w", data.target_quat_w, (2, 2, 4))):
            if not torch.is_tensor(value) or tuple(value.shape) != shape or not torch.all(torch.isfinite(value)):
                raise RuntimeError(f"live sensor {name} invalid: {getattr(value, 'shape', None)}")
        desired, geometry = oracle(env.simulator.scene, sensor, torch)
        observed = data.target_quat_w[:, 0, :]
        raw = torch.max(torch.abs(observed - desired), dim=-1).values
        neg = torch.max(torch.abs(observed + desired), dim=-1).values
        errors = torch.minimum(raw, neg)
        door = env.simulator.scene["door"]
        a.output.parent.mkdir(parents=True, exist_ok=True)
        a.output.write_text(json.dumps({"schema": "a2_piper_base_v26_5_live_target_case_v1", "status": "RUNTIME_COMPLETE", "factor": a.factor, "side": a.side, "num_envs": 2, "target_frame_names": names, "active_sensor_target_pos_w": data.target_pos_w.detach().cpu().tolist(), "active_sensor_target_quat_wxyz": data.target_quat_w.detach().cpu().tolist(), "geometry_oracle_target_quat_wxyz": desired.detach().cpu().tolist(), "O1_oracle_double_cover_component_error": errors.detach().cpu().tolist(), "authored_handle_geometry": geometry, "neutral_door_joint_pos": door.data.joint_pos.detach().cpu().tolist()}, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    finally:
        app.close()


if __name__ == "__main__":
    main(args())
