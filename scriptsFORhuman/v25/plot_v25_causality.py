#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


PAIR_SPECS = (
    ("Posture", "P0_M1", "P1_M1", "planar active"),
    ("Planar", "P1_M0", "P1_M1", "posture active"),
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    summary = json.loads(args.summary.read_text())
    records = summary["causality"]["paired_records"]

    ink = "#202124"
    grid = "#DADCE0"
    off_color = "#9AA0A6"
    on_color = "#1A73E8"
    median_color = "#E6A700"

    fig, axes = plt.subplots(2, 2, figsize=(11.5, 8.2), sharey=True)
    all_values: list[float] = []

    for row, side in enumerate(("left", "right")):
        side_records = [record for record in records if record["side"] == side]
        for col, (channel, off_branch, on_branch, context) in enumerate(PAIR_SPECS):
            ax = axes[row, col]
            off = np.array(
                [record["hinge_delta_rad"][off_branch] for record in side_records]
            )
            on = np.array(
                [record["hinge_delta_rad"][on_branch] for record in side_records]
            )
            effect = on - off
            all_values.extend(off.tolist())
            all_values.extend(on.tolist())

            for off_value, on_value in zip(off, on, strict=True):
                ax.plot((0, 1), (off_value, on_value), color=off_color, alpha=0.34, linewidth=0.8)
            ax.scatter(np.zeros_like(off), off, s=15, color=off_color, alpha=0.75, zorder=2)
            ax.scatter(np.ones_like(on), on, s=17, color=on_color, alpha=0.8, zorder=2)

            median_off = float(np.median(off))
            median_on = float(np.median(on))
            ax.plot((0, 1), (median_off, median_on), color=median_color, linewidth=3.2, zorder=3)
            ax.scatter((0, 1), (median_off, median_on), s=58, color=median_color, edgecolor=ink, linewidth=0.7, zorder=4)

            ax.set_title(
                f"{side.upper()} — {channel} OFF vs ON\n"
                f"{context} · n={len(effect)}\n"
                f"median Δ={np.median(effect):+.3f} · mean Δ={np.mean(effect):+.3f} rad",
                loc="left",
                color=ink,
                fontsize=9.5,
                fontweight="bold",
                pad=8,
            )
            ax.set_xticks((0, 1), ("OFF", "ON"))
            ax.grid(axis="y", color=grid, linewidth=0.7)
            ax.axhline(0.0, color=ink, linewidth=0.8)
            ax.spines[["top", "right"]].set_visible(False)
            ax.spines[["left", "bottom"]].set_color("#80868B")
            ax.tick_params(colors=ink)

    lower = min(0.0, min(all_values)) - 0.02
    upper = max(all_values) + 0.03
    for ax in axes.flat:
        ax.set_ylim(lower, upper)
    for ax in axes[:, 0]:
        ax.set_ylabel("Hinge-angle change over 50 control steps (rad)", color=ink)

    fig.suptitle(
        "Matched-prefix hinge progress by command channel",
        x=0.07,
        y=0.985,
        ha="left",
        color=ink,
        fontsize=16,
        fontweight="bold",
    )
    fig.text(
        0.07,
        0.947,
        "FULL S0 step500 · native P10 friction · same per-state prefix across four branches · gold line connects medians",
        ha="left",
        color="#5F6368",
        fontsize=9.5,
    )
    fig.text(
        0.07,
        0.015,
        f"Source: {args.summary}",
        ha="left",
        color="#5F6368",
        fontsize=8,
    )
    fig.patch.set_facecolor("white")
    fig.tight_layout(rect=(0.04, 0.05, 0.99, 0.925), h_pad=2.2, w_pad=2.0)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    main()
