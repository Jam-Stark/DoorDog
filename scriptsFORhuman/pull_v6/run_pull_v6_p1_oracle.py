#!/usr/bin/env python3
"""Print or launch one deterministic v6 P1 oracle grid cell."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]
PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
WINNER = ROOT / "logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/pull_v4_B_wave1_seed1/model_step_000750.pt"
ANGLES = {65: 1.1344640138, 75: 1.3089969390, 85: 1.4835298642}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--angle-deg", type=int, choices=ANGLES, required=True)
    parser.add_argument("--velocity", type=float, choices=(0.15, 0.20, 0.25), required=True)
    parser.add_argument("--relief", type=float, choices=(0.05, 0.10, 0.15), required=True)
    parser.add_argument("--orientation-axis", choices=("x", "z"), default="x")
    parser.add_argument("--gpu", type=int, choices=(0, 1, 2, 3), required=True)
    parser.add_argument("--attempt", type=int, default=1)
    parser.add_argument("--capture-bank", action="store_true")
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    if args.attempt <= 0:
        raise ValueError("--attempt must be positive.")
    if not WINNER.is_file():
        raise FileNotFoundError(WINNER)
    target = ANGLES[args.angle_deg]
    cell = (
        f"angle_{args.angle_deg:02d}_vel_{args.velocity:.2f}_"
        f"relief_{args.relief:.2f}_axis_{args.orientation_axis}"
    )
    output = ROOT / "logs_eval/a2_piper_pull_v6/p1_oracle_v1" / f"{cell}_attempt{args.attempt}"
    if output.exists():
        raise FileExistsError(f"refusing to overwrite oracle output: {output}")
    bank_path = ROOT / "logs_rl/a2_piper_pull_v6/pre_release_bank/pull_v6_F0_state_bank_v3.pt"
    if args.capture_bank and bank_path.exists():
        raise FileExistsError(f"refusing to overwrite v6 state bank: {bank_path}")
    port = (
        32000
        + (args.angle_deg - 65) * 10
        + int(args.velocity * 100)
        + int(args.relief * 100)
        + (0 if args.orientation_axis == "x" else 500)
        + args.attempt
    )
    command = [
        str(PYTHON), "-B", "-m", "gr00t.rl.eval_agent_trl",
        "+ablation=wbmanip/pull_v6_P1_oracle",
        f"checkpoint={WINNER}", "checkpoint_load_mode=full", "auto_load_latest=false",
        "num_envs=1", "+algo.config.num_mini_batches=1",
        "algo.config.eval.eval_num_envs_episodes=true",
        "algo.config.eval.num_eval_episodes=1",
        "algo.config.eval.a2_diagnostic_trace_enabled=true",
        "algo.config.eval.a2_hold_oracle_enabled=true",
        "algo.config.eval.a2_pull_v6_p1_oracle_enabled=true",
        f"algo.config.eval.a2_pull_v6_p1_orientation_axis={args.orientation_axis}",
        "algo.config.eval.a2_v20_arc_probe_target_hinge_rad=2.0943951024",
        "algo.config.eval.a2_pull_v6_p1_target_hinge_velocity_radps=0.30",
        f"algo.config.eval.a2_pull_v6_p1_xy_relief_m={args.relief}",
        f"env.config.a2_pull_v6_release_hinge_rad={target}",
        f"env.config.a2_pull_v6_release_min_hinge_velocity_radps={args.velocity}",
        f"env.config.a2_pull_v6_base_relief_radius_m={args.relief}",
        "algo.config.eval.a2_diagnostic_reward_terms=[dont_push_door_handle,target_root_distance,pull_door_handle,pull_door_hinge,a2_corridor_clean_passage,a2_pull_frame_approach,a2_pull_v6_arm_tangent_progress,a2_pull_v6_handle_side_progress,a2_pull_v6_handle_side_bonus,a2_pull_v6_arc_tracking,a2_pull_v6_pivot_excess_penalty,a2_pull_v6_hinge_momentum,a2_pull_v6_clean_release_quality,a2_pull_v6_premature_release_penalty]",
        f"eval_output_dir={output / 'eval'}", f"hydra.run.dir={output / 'hydra'}",
        "+device=cuda:0", f"+main_process_port={port}",
    ]
    if args.capture_bank:
        command.append(
            "+env.config.a2_pull_v6_bank_capture_path="
            + str(bank_path.relative_to(ROOT))
        )
    print(" ".join(command))
    if not args.run:
        return
    output.mkdir(parents=True)
    env = os.environ.copy()
    env.update({"CUDA_VISIBLE_DEVICES": str(args.gpu), "MASTER_PORT": str(port)})
    subprocess.run(command, check=True, cwd=ROOT, env=env)


if __name__ == "__main__":
    main()
