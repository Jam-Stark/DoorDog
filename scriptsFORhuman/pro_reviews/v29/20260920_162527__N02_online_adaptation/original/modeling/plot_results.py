#!/usr/bin/env python3
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

root = Path(__file__).resolve().parents[1]
results = root / "results"
df = pd.read_csv(results / "directional_force.csv")
poses = ["neutral", "roll+8", "roll-8", "pitch+8", "pitch-8"]
mid = df[(df.workpoint == "mid105") &
         (df.direction == "opening_normal_tangent")].set_index("pose").loc[poses]
plt.close("all")

fig, ax = plt.subplots(figsize=(10, 5.8))
x = np.arange(len(poses))
ax.bar(x - 0.19, mid.arm_force_N, 0.38, label="Arm torque bound")
ax.bar(x + 0.19, mid.whole_force_N, 0.38, label="With foot support and leg limits", hatch="//")
ax.set_xticks(x, poses)
ax.set_ylabel("Robot-on-door force at TCP (N)")
ax.set_title("Matched TCP pose: arm capacity versus supported capacity\n"
             "mid105; fixed base position and feet; simulation torque caps")
ax.legend()
ax.set_ylim(0, 610)
for i, (arm, whole) in enumerate(zip(mid.arm_force_N, mid.whole_force_N)):
    ax.text(i - 0.19, arm + 9, f"{arm:.1f}", ha="center", fontsize=10)
    ax.text(i + 0.19, whole + 9, f"{whole:.1f}", ha="center", fontsize=10)
fig.text(0.5, 0.015, "Static model only; grasp, collision and controller feasibility are not certified.",
         ha="center", fontsize=10)
fig.tight_layout(rect=(0, 0.04, 1, 1))
fig.savefig(results / "01_arm_vs_supported_capacity.png", dpi=180)
plt.show()

fig, ax = plt.subplots(figsize=(10, 5.6))
vals = mid.arm_peak_abs_tau_at20N_Nm.to_numpy()
ax.bar(poses, vals)
ax.set_ylim(0, 6.5)
ax.set_ylabel("Peak absolute arm joint torque (N m)")
ax.set_title("Actual operating-load comparison: the same 20 N opening force\n"
             "mid105; gravity included; lower is better")
for i, value in enumerate(vals):
    ax.text(i, value + 0.08, f"{value:.3f}", ha="center")
fig.text(0.5, 0.015, "roll+8 raises the maximum arm bound, but slightly increases torque at this 20 N load.",
         ha="center", fontsize=10)
fig.tight_layout(rect=(0, 0.04, 1, 1))
fig.savefig(results / "02_torque_at_same_20N.png", dpi=180)
plt.show()

move = pd.read_csv(results / "separate_base_translation.csv")
fig, ax = plt.subplots(figsize=(10, 5.6))
labels = ["Base -5 cm\nneutral", "Fixed base\nneutral", "Base +5 cm\nneutral", "Fixed base\npitch+8"]
values = list(move.whole_force_N) + [mid.loc["pitch+8", "whole_force_N"]]
ax.bar(labels, values)
ax.set_ylim(0, 170)
ax.set_ylabel("Supported static TCP force (N)")
ax.set_title("Separate diagnostic: base translation versus pitch\n"
             "Same TCP pose and foot locations; not a fixed-base posture comparison")
for i, value in enumerate(values):
    ax.text(i, value + 2, f"{value:.1f}", ha="center")
fig.text(0.5, 0.015, "No collision/clearance check: this is not a command to move closer to the door.",
         ha="center", fontsize=10)
fig.tight_layout(rect=(0, 0.04, 1, 1))
fig.savefig(results / "03_separate_base_translation.png", dpi=180)
plt.show()

