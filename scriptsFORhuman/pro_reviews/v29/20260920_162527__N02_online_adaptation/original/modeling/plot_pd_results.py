#!/usr/bin/env python3
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

root = Path(__file__).resolve().parents[1]
poses = ["neutral", "roll+8", "roll-8", "pitch+8", "pitch-8"]
raw = pd.read_csv(root / "results/directional_force.csv")
pdlim = pd.read_csv(root / "results/pd_target_limited_force.csv")
sel = raw.merge(pdlim, on=["workpoint", "pose", "direction"])
sel = sel[(sel.workpoint == "low90") & (sel.direction == "press_down")].set_index("pose").loc[poses]

fig, ax = plt.subplots(figsize=(10, 5.8))
x = np.arange(len(poses))
ax.bar(x - 0.18, sel.whole_force_N, 0.36, label="Support + torque caps")
ax.bar(x + 0.18, sel.whole_PD_force_N, 0.36,
       label="Also enforce arm PD target limits", hatch="//")
ax.set_xticks(x, poses)
ax.set_ylim(0, 210)
ax.set_ylabel("Downward robot-on-door TCP force (N)")
ax.set_title("Control constraints can reverse the posture ranking\n"
             "low90; matched TCP pose, fixed base and feet")
ax.legend()
for i, (a, b) in enumerate(zip(sel.whole_force_N, sel.whole_PD_force_N)):
    ax.text(i - 0.18, a + 3, f"{a:.1f}", ha="center")
    ax.text(i + 0.18, b + 3, f"{b:.1f}", ha="center")
fig.text(0.5, 0.015, "Nominal static PD model; grasp and actual command tracking remain unverified.",
         ha="center", fontsize=10)
fig.tight_layout(rect=(0, 0.04, 1, 1))
fig.savefig(root / "results/04_pd_constraint_reverses_ranking.png", dpi=180)
plt.show()

