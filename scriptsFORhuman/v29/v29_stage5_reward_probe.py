"""Bounded live-environment probe for the v29 Stage5 reward terms.

This is reward evidence only.  It consumes one ordinary natural-reset step,
then installs a process-local pose/stage fixture and invokes the production
reward registry.  It does not advance stages, write staged-reset samples, or
run a policy.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


TERM_NAMES = (
    "penalty_base_roll_pitch_l2",
    "penalty_a2_stage5_goal_heading_l2",
    "penalty_a2_stage5_upright_l2",
)


def _tolist(value):
    if hasattr(value, "detach"):
        return value.detach().cpu().tolist()
    return value


def _state_snapshot(env):
    root = env.simulator.robot_root_states.detach().clone()
    return {
        "root_state": _tolist(root),
        "root_position_relative_to_env_origin": _tolist(
            root[:, :3] - env.env_origins.detach()
        ),
        "goal_root_position": _tolist(env.target_root_pos),
        "rpy": _tolist(env.rpy),
        "stage": _tolist(env.stage_buf),
    }


def _capture_registered_rewards(env):
    captured = {}
    original_after_reward_components = env._after_reward_components

    def capture_after_reward_components(raw_components, scaled_components):
        original_after_reward_components(raw_components, scaled_components)
        for name in TERM_NAMES:
            if name not in raw_components or name not in scaled_components:
                raise RuntimeError(f"registered reward term missing from live registry: {name}")
            captured[name] = {
                "raw": _tolist(raw_components[name]),
                "scaled_after_registered_path": _tolist(scaled_components[name]),
            }

    env._after_reward_components = capture_after_reward_components
    env._compute_reward()
    env._after_reward_components = original_after_reward_components
    return captured


def _fixture_case(name):
    cases = {
        "stage5_aligned": {
            "stage": 5,
            "roll": 0.0,
            "pitch": 0.0,
            "yaw": 0.0,
        },
        "stage5_heading_only": {
            "stage": 5,
            "roll": 0.0,
            "pitch": 0.0,
            "yaw": 0.35,
        },
        "stage5_roll_pitch": {
            "stage": 5,
            "roll": 0.10,
            "pitch": 0.08,
            "yaw": 0.0,
        },
        "stage4_same_roll_pitch_pose": {
            "stage": 4,
            "roll": 0.10,
            "pitch": 0.08,
            "yaw": 0.0,
        },
    }
    try:
        return cases[name]
    except KeyError as exc:
        raise RuntimeError(f"unknown Stage5 reward fixture {name!r}") from exc


def run_probe(config, args):
    import torch
    from isaaclab.app import AppLauncher

    from gr00t.rl.train_agent_trl import patch_app_launcher_toolbar_hiding
    from gr00t.rl.trl.utils.common import custom_instantiate
    from gr00t.rl.utils.config_utils import register_rl_resolvers
    from gr00t.rl.utils.helpers import pre_process_config
    from gr00t.rl.utils.torch_utils import quat_from_euler_xyz
    from gr00t.rl.isaac_utils.rotations import get_euler_xyz_in_tensor

    patch_app_launcher_toolbar_hiding(AppLauncher)
    app = AppLauncher(
        headless=True,
        device=args.device,
        enable_cameras=False,
    ).app
    try:
        pre_process_config(config)
        env = custom_instantiate(config.env, device=args.device, _resolve=False)
        env.reset_all()

        # Consume the pending natural reset through the real action path.  The
        # action is zero only to provide one ordinary post-reset environment step.
        actions = torch.zeros(
            (env.num_envs, 24), device=env.device, dtype=torch.float32
        )
        env.step({"actions": actions})
        natural_step = _state_snapshot(env)

        if env.num_envs != 2:
            raise RuntimeError(f"Stage5 reward probe requires exactly 2 envs, got {env.num_envs}")

        reward_penalty_names = tuple(config.rewards.reward_penalty_reward_names)
        penalty_scale = env.reward_penalty_scale
        if torch.is_tensor(penalty_scale):
            penalty_scale_value = float(penalty_scale.detach().cpu().item())
        else:
            penalty_scale_value = float(penalty_scale)
        dt = float(env.dt)
        if any(name in reward_penalty_names for name in TERM_NAMES):
            raise RuntimeError("Stage5 terms unexpectedly entered the K penalty list")

        cases = {}
        for case_name in (
            "stage5_aligned",
            "stage5_heading_only",
            "stage5_roll_pitch",
            "stage4_same_roll_pitch_pose",
        ):
            case = _fixture_case(case_name)
            robot = env.simulator.scene.articulations["robot"]
            root_fixture = robot.data.root_state_w.clone()
            fixture_roll = torch.full(
                (env.num_envs,), case["roll"], device=env.device
            )
            fixture_pitch = torch.full(
                (env.num_envs,), case["pitch"], device=env.device
            )
            fixture_yaw = torch.full(
                (env.num_envs,), case["yaw"], device=env.device
            )
            # target_root_pos is [2, 0, 0.5] in the robot-local environment
            # frame.  Root [0, 0, 0.5] therefore has goal bearing zero.
            root_fixture[:, :3] = env.env_origins + root_fixture.new_tensor(
                [0.0, 0.0, 0.5]
            )
            fixture_quat_xyzw = quat_from_euler_xyz(
                fixture_roll, fixture_pitch, fixture_yaw
            )
            root_fixture[:, 3:7] = fixture_quat_xyzw[:, [3, 0, 1, 2]]
            root_fixture[:, 7:] = 0.0
            robot.write_root_state_to_sim(root_fixture)
            env.simulator.scene.write_data_to_sim()
            env._refresh_sim_tensors()

            # Derive RPY from actual refreshed simulator quaternion using the
            # same conversion as LeggedRobotBase. The full observation callback
            # also updates per-step contact streaks and must not run twice.
            env.base_quat[:] = env.simulator.base_quat[:]
            env.rpy[:] = get_euler_xyz_in_tensor(env.base_quat[:])
            env.stage_buf[:] = case["stage"]
            fixture = _state_snapshot(env)
            reward_components = _capture_registered_rewards(env)
            registered = {}
            for name in TERM_NAMES:
                registered[name] = {
                    **reward_components[name],
                    "registered_scale_after_dt": float(env.reward_scales[name]),
                    "dt": dt,
                    "K": penalty_scale_value,
                    "in_reward_penalty_K_list": name in reward_penalty_names,
                    "K_applied_by_registered_path": (
                        penalty_scale_value if name in reward_penalty_names else 1.0
                    ),
                }
            old_roll_pitch = registered["penalty_base_roll_pitch_l2"]
            new_upright = registered["penalty_a2_stage5_upright_l2"]
            cases[case_name] = {
                "requested_stage": case["stage"],
                "requested_rpy": [case["roll"], case["pitch"], case["yaw"]],
                "fixture": fixture,
                "terms": registered,
                "roll_pitch_combined_existing_minus2_plus_new_minus8": {
                    "raw_sum": [
                        old + new
                        for old, new in zip(
                            old_roll_pitch["raw"], new_upright["raw"]
                        )
                    ],
                    "scaled_registered_sum": [
                        old + new
                        for old, new in zip(
                            old_roll_pitch["scaled_after_registered_path"],
                            new_upright["scaled_after_registered_path"],
                        )
                    ],
                },
            }

            heading_raw = torch.as_tensor(
                reward_components["penalty_a2_stage5_goal_heading_l2"]["raw"],
                device=env.device,
            )
            upright_raw = torch.as_tensor(
                reward_components["penalty_a2_stage5_upright_l2"]["raw"],
                device=env.device,
            )
            zero_heading = torch.allclose(heading_raw, torch.zeros_like(heading_raw), atol=1e-8)
            zero_upright = torch.allclose(upright_raw, torch.zeros_like(upright_raw), atol=1e-8)
            if case_name == "stage5_aligned":
                if not zero_heading or not zero_upright:
                    raise RuntimeError("aligned Stage5 fixture produced nonzero new terms")
            elif case_name == "stage5_heading_only":
                if not bool((heading_raw > 0).all().item()) or not zero_upright:
                    raise RuntimeError("heading-only Stage5 fixture did not isolate heading term")
            elif case_name == "stage5_roll_pitch":
                if not zero_heading or not bool((upright_raw > 0).all().item()):
                    raise RuntimeError("roll/pitch Stage5 fixture did not isolate upright term")
            else:
                if not zero_heading or not zero_upright:
                    raise RuntimeError("Stage4 fixture did not zero the new Stage5 terms")

        output = {
            "claim": "live registered reward fixture only; no stage transition or policy claim",
            "num_envs": env.num_envs,
            "device": str(env.device),
            "natural_reset_step": natural_step,
            "cases": cases,
            "reward_registry_names": list(env.reward_names),
            "reward_penalty_K_names": list(reward_penalty_names),
            "production_config": {
                "reward_penalty_curriculum": bool(config.rewards.reward_penalty_curriculum),
                "reward_initial_penalty_scale": float(config.rewards.reward_initial_penalty_scale),
                "target_root_pos": _tolist(env.target_root_pos),
            },
        }
        args.output.write_text(json.dumps(output, indent=2, allow_nan=False) + "\n")
    except Exception:
        raise
    else:
        app.close(skip_cleanup=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--num-envs", type=int, default=2)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "scriptsFORhuman/v29/candidates/C002/stage5_reward_a1/reward_probe.json",
    )
    args = parser.parse_args()
    if args.num_envs != 2:
        raise ValueError("D056 Stage5 reward probe is fixed to exactly two environments")
    args.output.parent.mkdir(parents=True, exist_ok=False)

    from hydra import compose, initialize_config_dir
    from omegaconf import OmegaConf
    from gr00t.rl.utils.config_utils import register_rl_resolvers

    register_rl_resolvers()
    with initialize_config_dir(config_dir=str(ROOT / "gr00t/rl/config"), version_base="1.1"):
        config = compose(
            config_name="base",
            overrides=[
                "+exp=wbmanip/door_open_a2_base_lstm",
                "+ablation=wbmanip/base_v29_baseline",
                "exp_base=wbmanip/door_open_a2_base_lstm",
                f"experiment_dir={args.output.parent.resolve()}",
                f"++env.config.experiment_dir={args.output.parent.resolve()}",
                f"++env.config.save_rendering_dir={args.output.parent.resolve()}/renderings",
                f"output_dir={args.output.parent.resolve()}/output",
                "num_envs=2",
                "seed=291",
                "headless=true",
                "use_wandb=false",
                "project_name=base_v29_owner_baseline",
                "experiment_name=C002_STAGE5_REWARD_PROBE",
                "env.config.enable_staged_reset=false",
                "simulator.config.render_results=false",
                "simulator.config.cameras.enable_cameras=false",
            ],
        )
    OmegaConf.save(config, args.output.parent / "resolved_config.yaml", resolve=True)
    try:
        run_probe(config, args)
    except Exception:
        import traceback

        traceback.print_exc()
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(1)


if __name__ == "__main__":
    main()
