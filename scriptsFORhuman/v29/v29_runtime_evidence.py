"""Read-only C001 runtime receipts, attached through the trainer callback config."""

import json
import time
from collections.abc import Mapping
from pathlib import Path

import numpy as np
import torch
from transformers import TrainerCallback


def _json_value(value):
    """Preserve numeric USD values; unsupported data must not become strings."""
    from pxr import Gf, Sdf

    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, torch.Tensor):
        return value.detach().cpu().tolist()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Mapping):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, Sdf.AssetPath):
        return {"asset_path": value.path, "resolved_path": value.resolvedPath}
    if isinstance(value, Sdf.Path):
        return value.pathString
    if isinstance(value, (Gf.Quatd, Gf.Quatf, Gf.Quath)):
        return [value.GetReal(), *_json_value(value.GetImaginary())]
    if isinstance(value, (list, tuple)) or type(value).__module__ in ("pxr.Gf", "pxr.Vt"):
        return [_json_value(item) for item in value]
    raise TypeError(f"Unsupported runtime evidence value: {type(value)}")


def _tensor(value, indices=None):
    return {
        "shape": list(value.shape), "dtype": str(value.dtype), "device": str(value.device),
        "values": _json_value(value if indices is None else value[indices]),
    }


class V29RuntimeEvidence(TrainerCallback):
    """Export metadata for every door; detailed robot/frame samples are bounded.

    `begin` precedes the trainer's initial reset. `after_first_batch` is after
    policy actions and is deliberately not labelled an initial-reset sample.
    USD files preserve authored asset data; PhysX poses are in the JSON receipt.
    """

    def __init__(self, output_dir):
        self.output_dir = Path(output_dir)
        self._started = None
        self._first_batch_written = False

    def on_train_begin(self, args, state, control, **kwargs):
        self._started = time.monotonic()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.capture(kwargs["env"], "begin", state.global_step)

    def on_step_end(self, args, state, control, **kwargs):
        if not self._first_batch_written:
            self.capture(kwargs["env"], "after_first_batch", state.global_step, export_assets=False)
            self._first_batch_written = True
        # This trainer returns before on_train_end when DefaultFlowCallback
        # stops at the batch budget. It runs before this callback in the list.
        if control.should_training_stop:
            self.capture(kwargs["env"], "end", state.global_step)

    def capture(self, env, phase, global_step, *, export_assets=True):
        """Read one state; independent probes may call this after their reset."""
        import omni.usd
        from isaaclab.sim import export_prim_to_file

        if self._started is None:
            self._started = time.monotonic()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        stage = omni.usd.get_context().get_stage()
        scene = env.simulator.scene
        door = scene.articulations["door"]
        robot = scene.articulations["robot"]
        metadata = []
        representatives = {}
        for env_id in range(env.num_envs):
            prim_path = f"/World/envs/env_{env_id}/door"
            data = stage.GetPrimAtPath(prim_path).GetCustomData()
            # Required v29 keys fail visibly if the wrong asset was loaded.
            dynamics, handle = data["v29Dynamics"], data["v29Handle"]
            key = (data["doorOpenLR"], handle["family"], handle["return_present"])
            representatives.setdefault(key, env_id)
            metadata.append({"env_id": env_id, "prim_path": prim_path, "custom_data": data})
        selected = set(representatives.values())
        for parameter in ("mass_kg", "max_opening_deg", "torque_cap_nm"):
            selected.add(min(range(env.num_envs), key=lambda i: metadata[i]["custom_data"]["v29Dynamics"][parameter]))
            selected.add(max(range(env.num_envs), key=lambda i: metadata[i]["custom_data"]["v29Dynamics"][parameter]))
        selected = sorted(selected)
        indices = torch.tensor(selected, dtype=torch.long, device=env.device)
        view = door.root_physx_view
        physical = {
            "masses_kg": _tensor(view.get_masses()),
            "coms": _tensor(view.get_coms()),
            "inertias_kg_m2": _tensor(view.get_inertias()),
            "dof_limits_rad": _tensor(view.get_dof_limits()),
            "friction_static_dynamic_viscous": _tensor(view.get_dof_friction_properties()),
        }
        fields = (
            "joint_pos", "joint_vel", "joint_stiffness", "joint_damping",
            "joint_effort_limits", "joint_pos_target", "joint_vel_target",
            "joint_effort_target", "joint_pos_limits", "soft_joint_pos_limits",
            "applied_torque",
        )
        frame = env._get_a2_gripper_handle_frame_transformer().data
        frame_fields = (
            "source_pos_w", "source_quat_w", "target_pos_w", "target_quat_w",
            "target_pos_source", "target_quat_source",
        )
        receipt = {
            "phase": phase,
            "global_step": int(global_step),
            "elapsed_wall_seconds": time.monotonic() - self._started,
            "num_envs": env.num_envs,
            "control_dt_seconds": float(env.dt),
            "selected_env_ids": selected,
            "door_metadata": metadata,
            "door_body_names": door.body_names,
            "door_joint_names": door.joint_names,
            "door_physx": physical,
            "door_articulation_data": {name: _tensor(getattr(door.data, name)) for name in fields},
            "door_root_state_w": _tensor(door.data.root_state_w, indices),
            "robot": {
                "usd_path": robot.cfg.spawn.usd_path,
                "joint_names": robot.joint_names,
                "joint_pos": _tensor(robot.data.joint_pos, indices),
                "joint_pos_target": _tensor(robot.data.joint_pos_target, indices),
                "joint_stiffness": _tensor(robot.data.joint_stiffness, indices),
                "joint_damping": _tensor(robot.data.joint_damping, indices),
                "joint_effort_limits": _tensor(robot.data.joint_effort_limits, indices),
                "default_joint_pos": _tensor(robot.data.default_joint_pos, indices),
                "root_state_w": _tensor(robot.data.root_state_w, indices),
            },
            "frame_target_order": ["handle", "pregrasp"],
            "gripper_frames": {name: _tensor(getattr(frame, name), indices) for name in frame_fields},
            "closed_grasp_pos_door": _tensor(env._a2_closed_grasp_pos_door, indices),
            "observations": {name: {"shape": list(value.shape), "dtype": str(value.dtype),
                                     "device": str(value.device)}
                             for name, value in env.obs_buf_dict.items()},
            "stage": _tensor(env.stage_buf, indices),
            "episode_length": _tensor(env.episode_length_buf, indices),
            "reward": _tensor(env.rew_buf, indices),
            "reward_scales": env.reward_scales,
            "reward_episode_sums": {name: _tensor(value, indices) for name, value in env.episode_sums.items()},
            "cuda_peak_allocated_bytes": torch.cuda.max_memory_allocated(env.device),
            "cuda_peak_reserved_bytes": torch.cuda.max_memory_reserved(env.device),
            "asset_exports": [],
        }
        if export_assets:
            asset_dir = self.output_dir / f"{phase}_doors"
            asset_dir.mkdir(exist_ok=True)
            for env_id in selected:
                destination = asset_dir / f"env_{env_id:04d}.usd"
                export_prim_to_file(
                    str(destination), f"/World/envs/env_{env_id}/door", "/door", stage=stage
                )
                receipt["asset_exports"].append({"env_id": env_id, "path": str(destination)})
        with (self.output_dir / f"{phase}.json").open("w") as stream:
            json.dump(_json_value(receipt), stream, indent=2, allow_nan=False)
            stream.write("\n")
