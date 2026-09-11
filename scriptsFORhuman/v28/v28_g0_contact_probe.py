"""G0 R1/R2/R3/R5 on the real door environment with zero high-level command."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=False)

from hydra import compose, initialize_config_dir
from omegaconf import OmegaConf
from gr00t.rl.utils.config_utils import register_rl_resolvers
register_rl_resolvers()
with initialize_config_dir(config_dir=str(ROOT / "gr00t/rl/config"), version_base="1.1"):
    config = compose(config_name="base", overrides=[
        "+exp=wbmanip/door_open_a2_base_lstm", "+ablation=wbmanip/base_v28_A_S281",
        "num_envs=64", "headless=true", "use_wandb=false",
        "project_name=base_v28_camera_aware_rebaseline", "experiment_name=V28_G0_CONTACT",
        "exp_base=wbmanip/door_open_a2_base_lstm",
        "env.config.enable_staged_reset=false",
        f"experiment_dir={args.output.resolve()}",
        f"output_dir={args.output.resolve()}/output",
    ])
OmegaConf.save(config, args.output / "resolved_config.yaml", resolve=True)

from isaaclab.app import AppLauncher
from gr00t.rl.train_agent_trl import patch_app_launcher_toolbar_hiding
patch_app_launcher_toolbar_hiding(AppLauncher)
app = AppLauncher(headless=True, device="cuda:0", enable_cameras=False).app

import torch
from gr00t.rl.trl.utils.common import custom_instantiate
from gr00t.rl.utils.helpers import pre_process_config

try:
    torch.manual_seed(281)
    pre_process_config(config)
    config.env.config.save_rendering_dir = str(args.output / "renderings")
    config.env.config.experiment_dir = str(args.output)
    env = custom_instantiate(config.env, device="cuda:0", _resolve=False)
    obs = env.reset_all()
    simulator = env.simulator
    names = list(simulator.body_names)
    r1 = (simulator.num_bodies == 28 and names == list(config.robot.body_names)
          and simulator.contact_sensor.num_bodies == 28
          and list(simulator.dof_names) == list(config.robot.dof_names))
    if not r1:
        raise ValueError("G0 R1 body/contact/joint ordering failed")
    policy = torch.jit.load(str(ROOT / "gr00t/rl/data/policies/A2_Base/policy.pt"), map_location="cuda:0").eval()
    monitored = ["trunk","arm_body0",*[f"arm_body{i}" for i in range(1,7)],"wrist_camera_tower"]
    indices = [names.index(name) for name in monitored]
    flange_index = names.index("arm_body6_to_gripper")
    initial_height = (simulator._rigid_body_pos[:,flange_index,2] - simulator.robot_root_states[:,2]).clone()
    records = []
    camera_trace = []
    camera_episode_index = 0
    settle_steps = round(1.0 / float(env.dt))
    with torch.no_grad():
        for step in range(settle_steps + 50):
            actions = torch.zeros(64,24,device="cuda:0")
            actions[:,-12:] = policy(obs["a2_base_obs"])
            obs, reward, done, extras = env.step({"actions":actions})
            camera_episode_index += int(done[0].item())
            camera = env._get_a2_v28_camera_trace_fields(torch.tensor([0],device="cuda:0"))[0]
            camera.update(env_id=0,step_index=step,control_dt=float(env.dt),
                          stage_buf=int(env.stage_buf[0].item()),first_episode_active=camera_episode_index == 0,
                          episode_index=camera_episode_index,
                          arm_joint_pos=simulator.dof_pos[0,env._upper_non_gripper_dof_idx].cpu().tolist(),
                          arm_joint_vel=simulator.dof_vel[0,env._upper_non_gripper_dof_idx].cpu().tolist())
            camera_trace.append(camera)
            records.append({
                "step":step,
                "force_max_by_body_N":dict(zip(monitored,simulator.contact_forces[:,indices,:].norm(dim=-1).amax(dim=0).cpu().tolist())),
                "arm_abs_dq_max_rad_s":float(simulator.dof_vel[:,env._upper_non_gripper_dof_idx].abs().max().item()),
                "root_z_min_m":float(simulator.robot_root_states[:,2].min().item()),
                "root_z_max_m":float(simulator.robot_root_states[:,2].max().item()),
                "stage_counts":torch.bincount(env.stage_buf,minlength=6).cpu().tolist(),
                "undesired_contact_raw_mean":float(env._reward_penalty_undesired_contact().mean().item()),
                "tower_contact_raw_mean":float(env._reward_penalty_a2_wrist_tower_contact().mean().item()),
                "reward_mean":float(reward.mean().item()),"done_count":int(done.sum().item()),
            })
    r2 = all(max(row["force_max_by_body_N"].values()) < 1. and
             row["undesired_contact_raw_mean"] == 0. and row["tower_contact_raw_mean"] == 0. for row in records[:50])
    r3 = all(row["arm_abs_dq_max_rad_s"] < .5 and .45 <= row["root_z_min_m"] and row["root_z_max_m"] <= .51 for row in records[settle_steps:])
    r5 = bool(((initial_height >= .414514) & (initial_height <= .434514)).all().item())
    report = {"schema":"a2_piper_v28_g0_contact_v1", "evidence_level":"RUNTIME",
              "status":"PASS" if r1 and r2 and r3 and r5 else "FAIL",
              "gates":{"R1":r1,"R2":r2,"R3":r3,"R5_height":r5},
              "body_names":names,"contact_body_names":list(simulator.contact_sensor.body_names),
              "dof_names":list(simulator.dof_names),
              "initial_flange_height_above_root_m":{"min":float(initial_height.min().item()),"max":float(initial_height.max().item())},
              "records":records,
              "R3_window":"Owner-approved: settle first 1 s, then measure 50 control steps",
              "control_dt_s":float(env.dt),"R3_settle_steps":settle_steps,
              "R5_expected_flange_height_m":.424514,
              "scope":"zero high-level command and frozen A2_Base; no Teacher quality inference"}
    (args.output / "contact_probe.json").write_text(json.dumps(report,indent=2)+"\n")
    (args.output / "camera_trace.json").write_text(json.dumps(camera_trace,indent=2)+"\n")
    print(json.dumps({"status":report["status"],"gates":report["gates"]}),flush=True)
    if report["status"] != "PASS":
        raise SystemExit(2)
finally:
    app.close(skip_cleanup=True)
