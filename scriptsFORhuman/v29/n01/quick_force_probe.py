"""Finite palm-force diagnostic using the real checkpoint evaluator unchanged.

Run with --source-root V28_SOURCE --checkpoint PATH --output FRESH_DIR --side LEFT --doses
'0:70,90:40,-90:40,45:70,-45:70,0:0,90:0,-90:0'. Each entry is
theta_deg:total_newtons and binds one environment before simulation starts.
GPU visibility/device must be set by the authorized caller. No training.
"""

import argparse
import csv
import json
import math
from pathlib import Path
import sys
from types import MethodType


class ForceProbe:
    def __init__(self, env, args, doses):
        import torch
        from isaaclab.utils.math import quat_apply, quat_apply_inverse

        self.torch = torch
        self.rotate = quat_apply
        self.inverse_rotate = quat_apply_inverse
        self.env, self.args, self.doses = env, args, doses
        self.robot = env.simulator._robot
        self.body_ids, names = self.robot.find_bodies("arm_body6_to_gripper")
        if names != ["arm_body6_to_gripper"]:
            raise RuntimeError(f"Palm binding failed: {names}")
        self.joint_ids, joint_names = self.robot.find_joints("arm_j[78]", preserve_order=True)
        if joint_names != ["arm_j7", "arm_j8"]:
            raise RuntimeError(f"Gripper binding failed: {joint_names}")
        self.physics_dt = 1.0 / env.config.simulator.config.sim.fps
        self.decimation = env.config.simulator.config.sim.control_decimation
        self.pulse_steps = round(args.duration / self.physics_dt)
        if not math.isclose(self.pulse_steps * self.physics_dt, args.duration, abs_tol=1e-9):
            raise ValueError("duration must be an integer number of physics steps")
        self.n = env.num_envs
        if self.n != len(doses):
            raise ValueError("One preassigned dose is required per environment")
        self.control_step, self.physics_step = 0, 0
        self.finished = torch.zeros(self.n, dtype=torch.bool, device=env.device)
        self.triggered = self.finished.clone()
        self.remaining = torch.zeros(self.n, dtype=torch.int64, device=env.device)
        self.count = self.remaining.clone()
        self.qualify = self.remaining.clone()
        self.loss_streak = self.remaining.clone()
        self.loss = self.finished.clone()
        self.normal_release = self.finished.clone()
        self.force = torch.zeros((self.n, 1, 3), dtype=torch.float32, device=env.device)
        self.reference_rel = torch.zeros((self.n, 3), dtype=torch.float32, device=env.device)
        self.reference_q = torch.zeros((self.n, 2), dtype=torch.float32, device=env.device)
        self.events = [None] * self.n
        self.actions = None
        self.applied = self.finished.clone()
        self.csv_file = (args.output / "control.csv").open("w", newline="")
        self.csv = csv.DictWriter(self.csv_file, fieldnames=[
            "env", "control_step", "stage", "theta_deg", "newtons", "triggered",
            "physics_requests", "both_contact", "opposite_squeeze", "sufficient_squeeze",
            "close_gate", "close_intent", "release_gate", "gripper_q", "contact_force_w",
            "tcp_in_G", "relative_displacement_m", "q_change_m", "loss_confirmed",
            "normal_release", "door_q", "door_qd", "base_pos_w", "base_vel_w",
            "issued_actor_actions", "executed_actions_after_delay", "done", "timeout",
        ])
        self.csv.writeheader()
        self.physics_file = (args.output / "physics.jsonl").open("w")
        metadata = {
            "checkpoint": str(args.checkpoint), "source_config": str(args.checkpoint.parent / "config.yaml"),
            "source_root": str(args.source_root),
            "render_enabled": args.render,
            "side": args.side, "seed": args.seed, "doses": doses,
            "physics_dt": self.physics_dt, "decimation": self.decimation,
            "pulse_physics_steps": self.pulse_steps, "body": names[0], "gripper_joints": joint_names,
            "force_frame": "world; t0 direction sin(theta)*X_G-cos(theta)*Z_G held fixed",
            "application": "palm CoM, positions=None, no added torque",
            "admission": "5 consecutive control ticks of bilateral sufficient opposing squeeze, close gate, close intent; stage2/3/4 before release intent",
            "loss_rule": "3 control ticks constraint failure plus >=0.02m TCP/G relative displacement or >=0.005m actual gripper q change, excluding qualified open intent",
            "interpretation": "diagnostic thresholds; raw evidence retained; no matched-prefix causal claim",
        }
        (args.output / "probe_config.json").write_text(json.dumps(metadata, indent=2))
        self.install()

    def snapshot(self):
        env, torch = self.env, self.torch
        frame = env._get_a2_gripper_handle_frame_transformer().data
        contact = env._get_a2_gripper_handle_contact_forces()
        masks = env._get_a2_stage2_contact_squeeze_masks(contact, "finite force probe")
        rel = self.inverse_rotate(frame.target_quat_w[:, 0], frame.source_pos_w - frame.target_pos_w[:, 0])
        return dict(
            G_pos=frame.target_pos_w[:, 0], G_quat=frame.target_quat_w[:, 0],
            tcp_pos=frame.source_pos_w, tcp_quat=frame.source_quat_w, rel=rel,
            q=self.robot.data.joint_pos[:, self.joint_ids], contact=contact, masks=masks,
            palm_pos=self.robot.data.body_com_pos_w[:, self.body_ids[0]],
            base_pos=self.robot.data.root_pos_w, base_vel=self.robot.data.root_vel_w,
            door_q=env._get_door_joint_pos("finite force probe", 2),
            door_qd=env._get_door_joint_vel("finite force probe", 2),
        )

    def install(self):
        env = self.env
        original_force = env._apply_force_in_physics_step
        original_post = env._post_physics_substep
        original_terminal = env._capture_terminal_diagnostics
        original_step = env.step

        def force(_env):
            result = original_force()
            self.applied = (self.remaining > 0) & ~self.finished
            ids = self.applied.nonzero(as_tuple=False).flatten()
            if ids.numel():
                self.robot.instantaneous_wrench_composer.add_forces_and_torques(
                    forces=self.force[ids], body_ids=self.body_ids, env_ids=ids,
                    positions=None, is_global=True,
                )
                self.remaining[ids] -= 1
                self.count[ids] += 1
            return result

        def post(_env, substep):
            original_post(substep)
            self.physics_step += 1
            # All first-episode physics samples retain the pre-trigger baseline.
            self.write_physics(substep)

        def terminal(_env, ids):
            original_terminal(ids)
            self.control_step += 1
            self.record_control(ids)

        def step(_env, actor_state):
            self.actions = actor_state["actions"].detach().clone()
            return original_step(actor_state)

        env._apply_force_in_physics_step = MethodType(force, env)
        env._post_physics_substep = MethodType(post, env)
        env._capture_terminal_diagnostics = MethodType(terminal, env)
        env.step = MethodType(step, env)

    def write_physics(self, substep):
        s = self.snapshot()
        ids = (~self.finished).nonzero(as_tuple=False).flatten()
        payload = {"physics_step": self.physics_step, "control_step": self.control_step,
                   "substep": substep, "env_ids": ids.tolist(),
                   "requested": self.applied[ids].tolist(), "request_count": self.count[ids].tolist(),
                   "force_w": (self.force[:, 0] * self.applied[:, None])[ids].tolist()}
        for key in ("G_pos", "G_quat", "tcp_pos", "tcp_quat", "rel", "q", "contact", "palm_pos", "base_pos", "base_vel", "door_q", "door_qd"):
            payload[key] = s[key][ids].detach().cpu().tolist()
        self.physics_file.write(json.dumps(payload, separators=(",", ":"), allow_nan=False) + "\n")

    def record_control(self, done_ids):
        env, torch = self.env, self.torch
        s = self.snapshot()
        m = s["masks"]
        constraints = m["both_contact"] & m["opposite_squeeze"] & m["sufficient_squeeze"]
        # The production close gate includes stage==2. Its geometry remains
        # meaningful after a real grasp advances to stage3; do not disqualify
        # the fifth stable sample just because the task advanced this tick.
        frame = env._get_a2_gripper_handle_frame_transformer().data
        local_handle = frame.target_pos_source[:, 0]
        opening_alignment, approach_alignment = env._get_a2_gripper_handle_orientation_metrics()
        close_gate = (
            (local_handle[:, 0].abs() < env.config.stage2_close_gate_x_tol)
            & (local_handle[:, 1].abs() < env.config.stage2_close_gate_y_tol)
            & (local_handle[:, 2].abs() < env.config.stage2_close_gate_z_tol)
            & (opening_alignment >= 0.9) & (approach_alignment >= 0.9)
        )
        primitive = env._get_a2_gripper_primitive_raw_column("finite force probe")
        close = primitive < env._get_a2_stage2_completion_close_command_threshold()
        allowed_open = env._a2_stage4_release_gate & (primitive > 0.0)
        eligible = constraints & close_gate & close & ~allowed_open & (env.stage_buf >= 2) & (env.stage_buf <= 4) & ~self.finished
        self.qualify = torch.where(eligible, self.qualify + 1, 0)
        start = (self.qualify >= 5) & ~self.triggered & ~env.reset_buf.bool()
        for i in start.nonzero(as_tuple=False).flatten().tolist():
            theta, magnitude = self.doses[i]
            local = torch.tensor([[math.sin(math.radians(theta)), 0., -math.cos(math.radians(theta))]], device=env.device, dtype=torch.float32)
            self.force[i, 0] = self.rotate(s["G_quat"][i:i+1], local)[0] * magnitude
            self.reference_rel[i] = s["rel"][i]
            self.reference_q[i] = s["q"][i]
            self.events[i] = {"trigger_control_step": self.control_step, "trigger_physics_step": self.physics_step,
                              "force_w": self.force[i, 0].tolist(), "G_quat_t0": s["G_quat"][i].tolist()}
        self.triggered |= start
        self.remaining[start] = self.pulse_steps
        displacement = torch.linalg.vector_norm(s["rel"] - self.reference_rel, dim=-1)
        q_change = (s["q"] - self.reference_q).abs().amax(dim=-1)
        physical_change = (displacement >= 0.02) | (q_change >= 0.005)
        normal = self.triggered & allowed_open & physical_change & ~constraints
        self.normal_release |= normal & ~self.finished
        loss_now = self.triggered & ~constraints & physical_change & ~allowed_open & ~self.normal_release & ~self.finished
        self.loss_streak = torch.where(loss_now, self.loss_streak + 1, 0)
        self.loss |= self.loss_streak >= 3
        for i in (~self.finished).nonzero(as_tuple=False).flatten().tolist():
            row = dict(env=i, control_step=self.control_step, stage=int(env.stage_buf[i]),
                       theta_deg=self.doses[i][0], newtons=self.doses[i][1], triggered=bool(self.triggered[i]),
                       physics_requests=int(self.count[i]), both_contact=bool(m["both_contact"][i]),
                       opposite_squeeze=bool(m["opposite_squeeze"][i]), sufficient_squeeze=bool(m["sufficient_squeeze"][i]),
                       close_gate=bool(close_gate[i]), close_intent=bool(close[i]), release_gate=bool(env._a2_stage4_release_gate[i]),
                       relative_displacement_m=float(displacement[i]) if self.triggered[i] else None,
                       q_change_m=float(q_change[i]) if self.triggered[i] else None,
                       loss_confirmed=bool(self.loss[i]), normal_release=bool(self.normal_release[i]),
                       done=bool(env.reset_buf[i]), timeout=bool(env.time_out_buf[i]))
            for label, value in (("gripper_q", s["q"]), ("contact_force_w", s["contact"]), ("tcp_in_G", s["rel"]),
                                 ("door_q", s["door_q"]), ("door_qd", s["door_qd"]), ("base_pos_w", s["base_pos"]),
                                 ("base_vel_w", s["base_vel"]), ("issued_actor_actions", self.actions),
                                 ("executed_actions_after_delay", env.actions_after_delay)):
                row[label] = json.dumps(value[i].detach().cpu().tolist(), separators=(",", ":"), allow_nan=False)
            self.csv.writerow(row)
        self.finished[done_ids] = True
        self.remaining[done_ids] = 0  # Real task termination cancels the remainder; never force a reset episode.
        if bool(self.finished.all()):
            self.csv_file.close()
            self.physics_file.close()
            rows = []
            for i, (theta, magnitude) in enumerate(self.doses):
                rows.append(dict(env=i, theta_deg=theta, newtons=magnitude, admitted=bool(self.triggered[i]),
                                 request_count=int(self.count[i]), planned_count=self.pulse_steps,
                                 pulse_complete=int(self.count[i]) == self.pulse_steps,
                                 loss_confirmed=bool(self.loss[i]), normal_release=bool(self.normal_release[i]), event=self.events[i]))
            (self.args.output / "probe_summary.json").write_text(json.dumps({"status": "FIRST_EPISODES_COMPLETED", "envs": rows}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--side", choices=("LEFT", "RIGHT"), required=True)
    parser.add_argument("--seed", type=int, default=2921)
    parser.add_argument("--duration", type=float, default=0.35)
    parser.add_argument("--render", action="store_true", help="Use native evaluator main/handle cameras")
    parser.add_argument("--doses", required=True)
    args = parser.parse_args()
    args.source_root = args.source_root.resolve()
    args.checkpoint = args.checkpoint.resolve()
    args.output = args.output.resolve()
    doses = [tuple(map(float, entry.split(":"))) for entry in args.doses.split(",")]
    if not 8 <= len(doses) <= 16 or any(len(d) != 2 or not all(map(math.isfinite, d)) or d[1] < 0 for d in doses):
        raise ValueError("Require 8–16 finite theta:nonnegative_total_newtons doses")
    if not math.isfinite(args.duration) or args.duration <= 0:
        raise ValueError("duration must be positive and finite")
    if not args.checkpoint.is_file() or not (args.checkpoint.parent / "config.yaml").is_file():
        raise FileNotFoundError("Checkpoint and adjacent config.yaml are required")
    args.output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(args.source_root))
    from gr00t.rl import eval_agent_trl as evaluator
    if Path(evaluator.__file__).resolve() != args.source_root / "gr00t/rl/eval_agent_trl.py":
        raise RuntimeError(f"Requested evaluator source was not imported: {evaluator.__file__}")

    original_instantiate = evaluator.instantiate

    def instantiate(*positional, **kwargs):
        obj = original_instantiate(*positional, **kwargs)
        if "config" in kwargs and "device" in kwargs:
            ForceProbe(obj, args, doses)
        return obj

    evaluator.instantiate = instantiate
    overrides = {
        "checkpoint": str(args.checkpoint), "checkpoint_load_mode": "full", "auto_load_latest": False,
        "seed": args.seed, "num_envs": len(doses), "headless": True, "algo.config.num_mini_batches": 1,
        "algo.config.eval.num_eval_episodes": len(doses), "algo.config.eval.eval_num_envs_episodes": True,
        "algo.config.eval.dump_to_log_metrics": True, "algo.config.eval.a2_diagnostic_trace_enabled": False,
        "algo.config.eval.a2_forced_gripper_close_enabled": False,
        "algo.config.eval.a2_stage2_close_gate_forced_gripper_close_enabled": False,
        "env.config.a2_v26_door_open_lr": args.side.lower(), "env.config.a2_v26_side_permutation_seed": args.seed,
        "env.config.enable_staged_reset": False, "rewards.reward_penalty_curriculum": False,
        "env.config.a2_v26_8_penalty_driver": None,
        "simulator.config.render_results": args.render, "simulator.config.cameras.enable_cameras": False,
        "simulator.config.cameras.eval_camera_resolutions": [720, 1280],
        "experiment_dir": str(args.output), "env.config.experiment_dir": str(args.output),
        "env.config.save_rendering_dir": str(args.output / "renderings"), "output_dir": str(args.output / "output"),
        "eval_name": "V28_N01_FINITE_FORCE_PROBE", "eval_output_dir": str(args.output),
        "hydra.run.dir": str(args.output),
    }
    sys.argv = [sys.argv[0], "+ablation=wbmanip/base_v28_eval_natural_start"] + [
        f"++{key}=" + json.dumps(value, separators=(",", ":")) for key, value in overrides.items()]
    # Bind Hydra's filesystem config directly. A CLI --config-path would leak
    # through this evaluator's AppLauncher parse_known_args into native Kit.
    import hydra
    run_eval = hydra.main(config_path=str(Path(evaluator.__file__).parent / "config"),
                          config_name="base_eval", version_base="1.1")(evaluator.main.__wrapped__)
    run_eval()


if __name__ == "__main__":
    main()
