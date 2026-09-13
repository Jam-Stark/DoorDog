#!/usr/bin/env python3
"""Reduce G0 STEP5 natural64 evaluations through the shared pull parser.

This reports evaluator/bundle/camera wiring only. It never enters the original
PA seed population or applies the opening endpoint criterion.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import yaml

from reduce import SIDES, side_summary, DEFAULT_RIG, DEFAULT_NATIVE


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eval-root", type=Path, required=True,
                        help="G0 cell root containing G0_STEP5/{left,right}")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--readout", type=Path,
                        help="defaults to the decision path with .md suffix")
    parser.add_argument("--rig", type=Path, default=DEFAULT_RIG)
    parser.add_argument("--native-camera", type=Path, default=DEFAULT_NATIVE)
    args = parser.parse_args()
    readout = args.readout or args.output.with_suffix(".md")
    for path in (args.output, readout):
        if path.exists():
            raise FileExistsError(path)
    sides = {}
    for side in SIDES:
        directory = args.eval_root / "G0_STEP5" / side
        try:
            result = side_summary(directory, side, seed=0,
                                  rig=args.rig, native=args.native_camera)
            runtime = yaml.safe_load((directory / ".hydra/runtime_config.yaml").read_text())
            cfg = runtime["env"]["config"]
            result["bundle_runtime_config"] = {
                "delta_action_clamp_to_dof_limits": cfg["delta_action_clamp_to_dof_limits"],
                "a2_v28_camera_telemetry_enabled": cfg["a2_v28_camera_telemetry_enabled"],
                "a2_wrist_motion_vel_weights": cfg["a2_wrist_motion_vel_weights"],
                "a2_wrist_motion_reversal_weights": cfg["a2_wrist_motion_reversal_weights"],
                "reward_scales": {name: cfg["rewards"]["reward_scales"][name] for name in (
                    "penalty_a2_wrist_motion_l2", "penalty_a2_wrist_tower_contact",
                    "penalty_a2_stage4_arm_default_pose_l1")},
                "checkpoint": runtime["checkpoint"],
                "checkpoint_load_mode": runtime["checkpoint_load_mode"],
            }
            sides[side] = result
        except (ValueError, RuntimeError, KeyError, FileNotFoundError, AssertionError) as error:
            sides[side] = {"status": "INVALID", "directory": str(directory),
                           "error": f"{type(error).__name__}: {error}"}
    valid = all(result["status"] == "VALID" for result in sides.values())
    payload = {
        "schema": "a2_piper_pull_v28_g0_eval_wiring_v1",
        "status": "G0_EVAL_WIRING_PASS" if valid else "G0_EVAL_WIRING_INVALID",
        "cell": "G0", "seed": 0, "step": 5,
        "eval_root": str(args.eval_root), "sides": sides,
        "claim": "STEP5 checkpoint natural64 per side, pull integrity and bundle/camera telemetry wiring",
        "limits": "Not full G0 acceptance, opening, Teacher/Student, hardware, or PA endpoint evidence. Camera thresholds are report-only; absent late events remain null.",
        "opening_assessment": "NOT_EVALUATED", "pa_endpoint": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    lines = ["# Pull v28 G0 STEP5 evaluator wiring", "", f"Status: `{payload['status']}`.", "",
             "本结果仅说明双侧 natural64 与 telemetry 接线；不判 opening 或原三 seed 终点。", "",
             "| Side | Integrity | K5 | D | E4 | E5 | E6 | E7 | Tower >5N | Camera | Margin |",
             "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |"]
    details = []
    for side, result in sides.items():
        if result["status"] != "VALID":
            lines.append(f"| {side} | INVALID | — | — | — | — | — | — | — | — | — |")
            details.append(f"{side}: `{result['error']}`.")
            continue
        counts = " | ".join(f"{result[key]}/64" for key in (
            "K5", "D", "E4", "E5", "E6", "E7", "tower_contact_episode_gt5N"))
        camera = result["camera"]
        lines.append(f"| {side} | VALID | {counts} | {camera['status']} | {result['margin']['status']} |")
        details += [f"**{side}**：natural births={result['births']}，原trace读取={result['trace_read_passes']}遍；camera字段={len(camera['plan_fields'])}，样本={camera['sample_counts']}。",
                    f"Ready={result['release_ready']['episodes']}/64，4A/4B={result['retained_4a_4b']}；E5后样本={result['margin']['post_e5_samples']}，margin≥.07份额={result['margin']['margin_ge_0_07_step_fraction']}。",
                    f"Bundle/runtime checkpoint 字段保存在 decision 的 `{side}.bundle_runtime_config`；camera完整字段与null保存在 `{side}.camera`。"]
    lines += ["", *[line + "\n" for line in details],
              "相机投影/min-Z是几何代理；E6 yaw沿pull事件，缺少晚阶段样本不证明释放回位或opening能力。"]
    readout.parent.mkdir(parents=True, exist_ok=True)
    readout.write_text("\n".join(lines) + "\n")
    print(json.dumps({"status": payload["status"], "decision": str(args.output), "readout": str(readout)}), flush=True)
    return 0 if valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
