#!/usr/bin/env python3
"""COMPUTED calibration arithmetic for the v28 wrist-motion penalty (writes calibration.json)."""
import json
import math

DT = 0.02
V150 = math.radians(150.0)  # 2.618 rad/s
S = 0.4  # |scale| of penalty_a2_wrist_motion_l2
VEL_W = {  # stage -> (j4, j5, j6)
    0: (0.35, 0.35, 0.35),
    1: (0.5, 0.5, 0.5),
    2: (0.75, 0.75, 0.75),
    3: (0.5, 0.5, 0.0),
    4: (1.0, 1.0, 1.0),
    5: (1.25, 1.25, 1.25),
}
REV_W = {0: (0.5, 0.5, 0.5), 1: (0.5, 0.5, 0.5), 2: (0.5, 0.5, 0.5), 3: (0.5, 0.5, 0.25), 4: (0.5, 0.5, 0.5), 5: (0.5, 0.5, 0.5)}
# positive income per control step (scaled); stage2-5 COMPUTED from C_S2 DEV trace (mean of L/R), stage0/1 formula estimate
INCOME = {0: 0.08, 1: 0.12, 2: 0.288, 3: 0.565, 4: 0.552, 5: 0.331}
INCOME_SRC = {0: "formula est. (walk_to_door 5*~0.75 + stage 1*~1)*dt", 1: "formula est. (pregrasp_target_distance 6*~0.7 + gripper_handle_orientation 3*~0.5)*dt",
              2: "COMPUTED C_S2 DEV L/R 0.2998/0.2764", 3: "COMPUTED 0.5677/0.5621", 4: "COMPUTED 0.5379/0.5661", 5: "COMPUTED 0.3034/0.3580"}

rows = {}
for s in range(6):
    w4, w5, w6 = VEL_W[s]
    cost_single = S * w4 * DT * V150**2  # one wrist joint (j4) at 150 deg/s sustained
    cost_j6 = S * w6 * DT * V150**2
    rows[s] = {
        "vel_weights_j4_j5_j6": VEL_W[s],
        "reversal_weights_j4_j5_j6": REV_W[s],
        "income_per_step": INCOME[s],
        "income_source": INCOME_SRC[s],
        "cost_j4_at_150dps_per_step": round(cost_single, 5),
        "cost_j4_fraction_of_income": round(cost_single / INCOME[s], 3),
        "cost_j6_at_150dps_per_step": round(cost_j6, 5),
        "cost_j6_fraction_of_income": round(cost_j6 / INCOME[s], 3),
        "cost_full_reversal_2rads_j4_once": round(S * REV_W[s][0] * DT * 4.0, 5),
    }
# Stage3 depression arithmetic (j6 saturated at the 3.0 rad/s joint velocity limit, COMPUTED p50 2.95-3.0)
dep = {
    "j6_speed_rad_s": 3.0,
    "new_term_cost": 0.0,
    "existing_penalty_dof_vel_cost": round(0.001 * DT * 9.0, 6),
    "existing_penalty_dof_vel_fraction": round(0.001 * DT * 9.0 / INCOME[3], 5),
    "existing_penalty_dof_acc_measured_per_step_LR": (-0.00955, -0.00639),
    "j4_tail_4p1_rad_s_new_term_cost": round(S * VEL_W[3][0] * DT * 4.1**2, 5),
    "j4_tail_fraction": round(S * VEL_W[3][0] * DT * 4.1**2 / INCOME[3], 3),
    "one_reversal_j6_at_3rad_s_cost_once": round(S * REV_W[3][2] * DT * 9.0, 5),
}
# Stage4 post-release posture term
post = {}
for scale in (0.5, 1.0):
    for l1 in (7.1, 8.4):
        post[f"scale{scale}_L1_{l1}"] = round(scale * DT * l1, 4)
post["released_income_per_step_LR"] = (0.20, 0.31)
# warm-start shift arithmetic
shift = {
    "delta_default_j4_j5": (0.0 - 0.25, -0.44 - 0.5),
    "obs_dof_pos_shift_j4_j5_rad": (0.25, 0.94),
    "cumulative_delta_action_shift_units": ((0.25) / 0.25, (0.94) / 0.25),
    "per_step_target_increment_rad_per_unit_action": 0.3 * 0.25,
    "commanded_velocity_rad_s_per_unit_action": 0.3 * 0.25 / DT,
}
gpu = {"iteration_time_s_measured": (22.05, 22.96), "batches": 500, "train_hours": round(500 * 22.5 / 3600, 2), "eval_exact64_per_side_min_est": (6, 8)}
out = {"scale": -S, "dt": DT, "v150_rad_s": V150, "rows": rows, "stage3_depression": dep, "stage4_post_release_posture": post, "warm_start_shift": shift, "g1_probe_gpu": gpu}
json.dump(out, open("/tmp/v28_team/policy/calibration.json", "w"), indent=1)
for s, r in rows.items():
    print(s, r["vel_weights_j4_j5_j6"], r["income_per_step"], r["cost_j4_at_150dps_per_step"], r["cost_j4_fraction_of_income"], r["cost_j6_fraction_of_income"], r["cost_full_reversal_2rads_j4_once"])
print(dep)
print(post)
print(shift)
print(gpu)
