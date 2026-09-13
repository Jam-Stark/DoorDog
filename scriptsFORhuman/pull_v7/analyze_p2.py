#!/usr/bin/env python3
"""Pull-v7 P2 mediator reducer. CPU-only, one streaming pass per trace.

Consumes one frozen milestone directory produced by eval_p2_cell.sh:

    <eval_root>/<cell>_STEP<step>/<side>/{metrics_eval.json,
        a2_v14_per_env_records.json, stage2_5_step_trace.json,
        .hydra/runtime_config.yaml}

Reuses analyze_p0's streaming reader, row compaction, threshold table and
window bookkeeping so the margin and condition definitions are literally the
P0 ones.  Adds the D2-specific columns: per-joint commanded-target overshoot,
the runtime `reward_raw`/`reward_scaled` value of
`a2_pull_v7_arm_target_overshoot_penalty`, and the 4A/4B retention indicators.

Each trace is read exactly once; the per-episode tables it writes are small and
the markdown report is regenerated from them with --report-only.

Run: python scriptsFORhuman/pull_v7/analyze_p2.py --eval-root <milestone> \
         --step 9500 --cells T_S1 C_S2
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_p0 import (  # noqa: E402
    EVENTS,
    THRESHOLDS,
    all_known,
    compact,
    finish_windows,
    number,
    stream,
    window_update,
)

ROOT = Path(__file__).resolve().parents[2]
JOINTS = [f"arm_j{j}" for j in range(1, 7)]
D2_KEY = "a2_pull_v7_arm_target_overshoot_penalty"
# door_open_a2_pull.py:648-651
PHASE_B, PHASE_C = 1, 2
# scriptsFORhuman/pull_v26_8/REDUCER_CONTRACT.md: D and open_hold definitions.
DURABLE_RAD, HOLD_STEPS = 0.6, 25
TANGENT_SHARE_MIN = 0.6
SIDES = ("left", "right")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(f"PULL_V7_P2_INVALID: {message}")


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(fraction * (len(ordered) - 1) + 0.5))]


def distribution(values: list[float]) -> dict:
    if not values:
        return {"n": 0, "median": None, "p90": None, "max": None}
    return {
        "n": len(values),
        "median": statistics.median(values),
        "p90": percentile(values, 0.9),
        "max": max(values),
    }


def arm_hard_limits(cfg) -> dict[str, tuple[float, float]]:
    robot = cfg["robot"]
    limits = {}
    for joint in JOINTS:
        index = robot["dof_names"].index(joint)
        limits[joint] = (
            float(robot["dof_pos_lower_limit_list"][index]),
            float(robot["dof_pos_upper_limit_list"][index]),
        )
    return limits


def analyze_side(cell: str, side: str, directory: Path) -> dict:
    cfg = yaml.load((directory / ".hydra/runtime_config.yaml").read_text(), Loader=yaml.BaseLoader)
    metrics = json.loads((directory / "metrics_eval.json").read_text())
    records = json.loads((directory / "a2_v14_per_env_records.json").read_text())
    terminals = {row["env_id"]: row for row in metrics["episode_terminal_diagnostics"]}
    require(
        len(terminals) == len(records) == metrics["completed_episodes"] == 64,
        f"{directory}: exact64 first-episode contract",
    )
    limits = arm_hard_limits(cfg)
    margin_threshold = float(cfg["env"]["config"][THRESHOLDS["margin"][0]])
    share_source = float(cfg["env"]["config"][THRESHOLDS["share"][0]])
    require(
        abs(share_source - TANGENT_SHARE_MIN) < 1e-9,
        f"{directory}: 4B tangent-share indicator assumes {TANGENT_SHARE_MIN}, config says {share_source}",
    )

    births = 0
    episodes: dict[int, dict] = {}
    # Overshoot samples are pooled per side; 64 episodes of a natural eval are
    # on the order of 1e5 control steps, which stays small in memory.
    overshoot_all: dict[str, list[float]] = {joint: [] for joint in JOINTS}
    overshoot_all["sum"] = []
    overshoot_post_e5: dict[str, list[float]] = {joint: [] for joint in JOINTS}
    overshoot_post_e5["sum"] = []
    d2_raw: list[float] = []
    d2_scaled: list[float] = []
    d2_key_present = None
    margin_recompute_error = 0.0

    for row in stream(directory / "stage2_5_step_trace.json"):
        if row.get("record_type") == "episode_start":
            require(
                row["stage_buf"] == 0
                and row["step_index"] == -1
                and row["episode_index"] == 0
                and row["first_episode_active"] is True
                and row["a2_v26_episode_start_stage"] == 0
                and row["door_handle_side"] == side,
                f"{directory}: birth row violates the natural Stage0 protocol",
            )
            births += 1
            continue
        if row["episode_index"] != 0 or not row["first_episode_active"]:
            continue
        require(row["door_handle_side"] == side, f"{directory}: trace side contamination")
        env = row["env_id"]
        step = row["episode_length_buf"]
        c, conditions = compact(row, cell, side, cfg)
        margin_recompute_error = max(margin_recompute_error, abs(c["margin"] - c["margin_recomputed"]))
        state = episodes.get(env)
        if state is None:
            state = episodes[env] = {
                "env": env,
                "rows": 0,
                "first_counter": step,
                "last_counter": None,
                "event_steps": {},
                "max_release_margin": c["margin"],
                "high_margin_b_steps": 0,
                "high_margin_e5_entry": False,
                "ready_steps": 0,
                "clean_steps": 0,
                "handoff_reached": False,
                "handle_crossed": False,
                "tangent_share_ge_min": False,
                "durable_run": 0,
                "durable_best": 0,
                "squeeze_streak_max": int(row["a2_stage2_squeeze_streak"]),
                "leave_limit_age": {joint: None for joint in ("arm_j3", "arm_j5")},
                "windows": {},
                "post_e5_windows": {},
            }
        state["rows"] += 1
        if state["last_counter"] is not None:
            require(step > state["last_counter"], f"{directory}: env{env} non-monotonic episode counter")
        state["last_counter"] = step
        state["max_release_margin"] = max(state["max_release_margin"], c["margin"])
        state["squeeze_streak_max"] = max(state["squeeze_streak_max"], int(row["a2_stage2_squeeze_streak"]))

        v6 = row["pull_v0"]["pull_v6"]
        state["handoff_reached"] |= v6["handoff_reached"] is True
        state["handle_crossed"] |= v6["handle_crossed"] is True
        share = number(v6["arm_tangent_share"])
        if share is not None and float(share) >= TANGENT_SHARE_MIN:
            state["tangent_share_ge_min"] = True
        if c["release_ready"]:
            state["ready_steps"] += 1
        if c["clean"]:
            state["clean_steps"] += 1
        if float(row["door_handle_joint_pos"]) >= DURABLE_RAD:
            state["durable_run"] += 1
            state["durable_best"] = max(state["durable_best"], state["durable_run"])
        else:
            state["durable_run"] = 0

        names = row["arm_joint_names"]
        require(names == JOINTS, f"{directory}: env{env} arm joint-name contract {names}")
        targets = row["arm_joint_pos_target"]
        require(isinstance(targets, list) and len(targets) == 6, f"{directory}: env{env} arm target contract")
        per_joint = {}
        for joint, target in zip(names, targets, strict=True):
            low, high = limits[joint]
            per_joint[joint] = max(0.0, float(target) - high) + max(0.0, low - float(target))
        total = sum(per_joint.values())
        # Stage0 zeroes the cumulative arm state, so Stage0 rows carry no D2
        # signal; the term's own domain is Stage1-4 plus Stage5.
        if row["stage_buf"] >= 1:
            for joint, value in per_joint.items():
                overshoot_all[joint].append(value)
            overshoot_all["sum"].append(total)

        for joint in ("arm_j3", "arm_j5"):
            if state["leave_limit_age"][joint] is None and c[f"{joint}_release_margin"] >= margin_threshold:
                state["leave_limit_age"][joint] = step

        raw = row["reward_raw"]
        scaled = row["reward_scaled"]
        present = D2_KEY in raw
        if d2_key_present is None:
            d2_key_present = present
        require(present == d2_key_present, f"{directory}: env{env} inconsistent {D2_KEY} presence in reward_raw")
        if present:
            d2_raw.append(float(raw[D2_KEY]))
            d2_scaled.append(float(scaled[D2_KEY]))

        for event, value in row["pull_v0_episode"]["first_event_step"].items():
            if event in EVENTS and number(value) is not None:
                state["event_steps"][event[:2]] = value
        e5 = state["event_steps"].get("E5")
        post = e5 is not None and step >= e5
        if post:
            for joint, value in per_joint.items():
                overshoot_post_e5[joint].append(value)
            overshoot_post_e5["sum"].append(total)
        if c["margin"] >= margin_threshold:
            if c["phase"] == PHASE_B:
                state["high_margin_b_steps"] += 1
            if e5 is not None and step == e5:
                state["high_margin_e5_entry"] = True

        scopes = [state["windows"]] + ([state["post_e5_windows"]] if post else [])
        for stats in scopes:
            for key, value in conditions.items():
                window_update(stats, key, value, step)
            window_update(stats, "joint", c["geometric_joint_ready"], step)
            window_update(stats, "actual_ready", c["release_ready"], step)
            window_update(
                stats,
                "all_except_margin",
                all_known([x for k, x in conditions.items() if k != "margin"]),
                step,
            )
            for key in conditions:
                window_update(stats, "only_missing_" + key, c["only_missing"] == key, step)

    require(births == 64, f"{directory}: expected 64 natural birth rows, got {births}")
    for state in episodes.values():
        finish_windows(state["windows"])
        finish_windows(state["post_e5_windows"])

    reached = {label: 0 for label in ("E2", "E3", "E4", "E5", "E6", "E7")}
    for row in terminals.values():
        for event in EVENTS:
            reached[event[:2]] += int(row["pull_v0_episode"]["event_reached"][event])
    pass_counts = Counter()
    for state in episodes.values():
        if not state["post_e5_windows"]:
            continue
        edges = Counter()
        for key in ["pivot_valid", "bilateral", "panel_clear", *THRESHOLDS]:
            for low, high in state["post_e5_windows"][key]["windows"]:
                edges[low] += 1
                edges[high + 1] -= 1
        edges[state["event_steps"]["E5"]] += 0
        edges[state["last_counter"] + 1] += 0
        count = 0
        points = sorted(edges)
        for low, high in zip(points, points[1:], strict=False):
            count += edges[low]
            pass_counts[str(count)] += high - low

    return {
        "cell": cell,
        "side": side,
        "directory": str(directory),
        "denominator": 64,
        "trace_bytes": (directory / "stage2_5_step_trace.json").stat().st_size,
        "births": births,
        "episodes_with_trace": len(episodes),
        "margin_threshold": margin_threshold,
        "margin_recompute_max_abs_error": margin_recompute_error,
        "d2_term_present": bool(d2_key_present),
        "d2_reward_raw": distribution(d2_raw),
        "d2_reward_scaled": distribution(d2_scaled),
        "overshoot_stage1plus": {key: distribution(values) for key, values in overshoot_all.items()},
        "overshoot_post_e5": {key: distribution(values) for key, values in overshoot_post_e5.items()},
        "release_margin_episode_max": distribution([s["max_release_margin"] for s in episodes.values()]),
        "high_margin_b_steps_total": sum(s["high_margin_b_steps"] for s in episodes.values()),
        "high_margin_b_episodes": sum(s["high_margin_b_steps"] > 0 for s in episodes.values()),
        "high_margin_e5_entries": sum(s["high_margin_e5_entry"] for s in episodes.values()),
        "leave_limit": {
            joint: {
                "episodes": sum(s["leave_limit_age"][joint] is not None for s in episodes.values()),
                "first_age_median": percentile(
                    sorted(s["leave_limit_age"][joint] for s in episodes.values() if s["leave_limit_age"][joint] is not None),
                    0.5,
                ),
            }
            for joint in ("arm_j3", "arm_j5")
        },
        "pass_count_histogram_post_e5": dict(sorted(pass_counts.items(), key=lambda item: int(item[0]))),
        "only_missing_one_post_e5": {
            key: {
                "episodes": sum(s["post_e5_windows"].get("only_missing_" + key, {}).get("steps", 0) > 0 for s in episodes.values()),
                "steps": sum(s["post_e5_windows"].get("only_missing_" + key, {}).get("steps", 0) for s in episodes.values()),
                "longest": max([s["post_e5_windows"].get("only_missing_" + key, {}).get("longest", 0) for s in episodes.values()] or [0]),
            }
            for key in ["pivot_valid", "bilateral", "panel_clear", *THRESHOLDS]
        },
        "ready": {
            "episodes": sum(s["ready_steps"] > 0 for s in episodes.values()),
            "steps": sum(s["ready_steps"] for s in episodes.values()),
            "longest": max([s["windows"].get("actual_ready", {}).get("longest", 0) for s in episodes.values()] or [0]),
        },
        "clean_release_episodes": sum(s["clean_steps"] > 0 for s in episodes.values()),
        "retention": {
            "K5": sum(
                max(s["squeeze_streak_max"], int(terminals[s["env"]]["a2_stage2_squeeze_streak"])) >= 5
                for s in episodes.values()
            ),
            "D": sum(s["durable_best"] >= HOLD_STEPS for s in episodes.values()),
            "E4": reached["E4"],
            "E5": reached["E5"],
        },
        "events": reached,
        "complete": sum(row.get("terminal_reasons") == "complete" for row in terminals.values()),
        "retained_4a_4b": {
            "handoff_reached": sum(s["handoff_reached"] for s in episodes.values()),
            "tangent_share_ge_0_6": sum(s["tangent_share_ge_min"] for s in episodes.values()),
            "handle_crossed": sum(s["handle_crossed"] for s in episodes.values()),
        },
        "terminal_reasons": dict(sorted(Counter(row["terminal_reasons"] for row in terminals.values()).items())),
    }


def markdown(payload: dict) -> str:
    def table(headers, body):
        return "\n".join(
            ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
            + ["| " + " | ".join(str(value) for value in row) + " |" for row in body]
        )

    def fmt(value):
        return "n/a" if value is None else f"{value:.6g}"

    groups = payload["groups"]
    label = [f"{g['cell']} {g['side'].upper()}" for g in groups]
    overshoot = table(
        ["cell/side", "D2 项在 reward 中", "Stage1+ sum 中位/p90/max", "E5 后 sum 中位/p90/max", "j3 中位", "j5 中位", "runtime raw 中位"],
        [
            [
                label[i],
                g["d2_term_present"],
                "/".join(fmt(g["overshoot_stage1plus"]["sum"][k]) for k in ("median", "p90", "max")),
                "/".join(fmt(g["overshoot_post_e5"]["sum"][k]) for k in ("median", "p90", "max")),
                fmt(g["overshoot_stage1plus"]["arm_j3"]["median"]),
                fmt(g["overshoot_stage1plus"]["arm_j5"]["median"]),
                fmt(g["d2_reward_raw"]["median"]),
            ]
            for i, g in enumerate(groups)
        ],
    )
    mediators = table(
        ["cell/side", "每episode最大margin 中位/p90/max", "有余量B步/episode", "有余量新E5入口", "j3离开限位 episode", "j5离开限位 episode", "ready episode/步/最长", "clean episode"],
        [
            [
                label[i],
                "/".join(fmt(g["release_margin_episode_max"][k]) for k in ("median", "p90", "max")),
                f"{g['high_margin_b_steps_total']}/{g['high_margin_b_episodes']}",
                g["high_margin_e5_entries"],
                g["leave_limit"]["arm_j3"]["episodes"],
                g["leave_limit"]["arm_j5"]["episodes"],
                f"{g['ready']['episodes']}/{g['ready']['steps']}/{g['ready']['longest']}",
                g["clean_release_episodes"],
            ]
            for i, g in enumerate(groups)
        ],
    )
    retention = table(
        ["cell/side", "K5", "D", "E4", "E5", "E6", "E7", "complete", "handoff_reached", "tangent≥0.6", "handle_crossed"],
        [
            [
                label[i],
                g["retention"]["K5"],
                g["retention"]["D"],
                g["retention"]["E4"],
                g["retention"]["E5"],
                g["events"]["E6"],
                g["events"]["E7"],
                g["complete"],
                g["retained_4a_4b"]["handoff_reached"],
                g["retained_4a_4b"]["tangent_share_ge_0_6"],
                g["retained_4a_4b"]["handle_crossed"],
            ]
            for i, g in enumerate(groups)
        ],
    )
    passes = table(
        ["cell/side", "E5后同一步通过条件数: 控制步数", "仅缺 margin episode/步/最长"],
        [
            [
                label[i],
                json.dumps(g["pass_count_histogram_post_e5"]),
                "/".join(str(g["only_missing_one_post_e5"]["margin"][k]) for k in ("episodes", "steps", "longest")),
            ]
            for i, g in enumerate(groups)
        ],
    )
    return f"""# Pull v7 P2 中介读数：milestone step{payload['step']}

本文件由 `scriptsFORhuman/pull_v7/analyze_p2.py` 从冻结的 exact64 natural
milestone 目录一次流式生成，分母固定 64，未重复解析大 trace。reducer 只报告
数值，门限判定由 Main 按 plan §4.4 决定。

- eval root：`{payload['eval_root']}`
- margin 门限：{groups[0]['margin_threshold']}（来自各自 runtime config）
- margin 重算与 trace 原值最大绝对误差：{max(g['margin_recompute_max_abs_error'] for g in groups):.3g}

## 0. D2 直接作用量：commanded target overshoot（rad）

{overshoot}

`runtime raw 中位` 是 trace 内 `reward_raw.{D2_KEY}` 的中位数；它与同一行按
硬限位离线重算的 overshoot 属同一定义，两列不一致即为实现缺陷。C 格没有该
reward key，`d2_term_present` 为 false。

## 1-3. margin 中介与限位脱离

{mediators}

## 4. 同一步通过条件数与"仅缺一项"

{passes}

## 5. 保留能力与 4A/4B

{retention}
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eval-root", type=Path, required=True)
    parser.add_argument("--step", type=int, required=True, choices=(9500, 10000, 10500))
    parser.add_argument("--cells", nargs="+", required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--report-only", action="store_true", help="regenerate markdown from the existing small JSON")
    args = parser.parse_args()

    output = args.output or args.eval_root / f"P2_MEDIATOR_step{args.step}.json"
    if args.report_only:
        payload = json.loads(output.read_text())
    else:
        groups = []
        for cell in args.cells:
            for side in SIDES:
                directory = args.eval_root / f"{cell}_STEP{args.step}" / side
                require(directory.is_dir(), f"missing milestone directory {directory}")
                groups.append(analyze_side(cell, side, directory))
                print(f"reduced {cell} {side}", flush=True)
        payload = {
            "schema": "pull_v7_p2_mediator_v1",
            "step": args.step,
            "eval_root": str(args.eval_root),
            "cells": list(args.cells),
            "gate_reference": "scriptsFORhuman/pull_task/a2_piper_pull_v7_stage_plan_20260909.md §4.4",
            "groups": groups,
        }
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = output.with_suffix(".md")
    report.write_text(markdown(payload), encoding="utf-8")
    print(f"wrote {output} and {report}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
