"""Write v28 milestone readouts from registered reducer and evaluation artifacts."""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from v28_contract import METRICS, read_json, require, write_json


def camera_assessment(camera: dict) -> dict:
    """Report the existing camera targets; absent events stay unassessed."""
    checks = {}

    def at_most(name, value, limit):
        checks[name] = {"value": value, "limit": limit,
                        "pass": None if value is None else value <= limit}

    for stage, limit in ((2, 105), (3, 250), (4, 150), (5, 90)):
        block = camera["stages"].get(str(stage))
        at_most(f"stage{stage}_wrist_speed_p95_deg_s",
                None if block is None else block["wrist_cam_ang_speed_deg_s"]["p95"], limit)
    for stage, limit in ((0, 1.5), (5, 1.5), (2, 2.5), (4, 2.5)):
        block = camera["stages"].get(str(stage))
        at_most(f"stage{stage}_j6_reversals_per_s",
                None if block is None else block["arm_j6_reversals"]["per_s"], limit)
    fields = camera["plan_fields"]
    at_most("stage0_5_arm_posture_l1_p95_rad", fields["arm_posture_l1_p95_rad"], 0.5)
    # The registered five-percent frame threshold needs a count, not a p95 surrogate.
    raw = read_json(Path(camera["trace"]))
    posture_rows = [row for row in raw if row["first_episode_active"] is True
                    and row["episode_index"] == 0 and row["stage_buf"] in (0, 5)]
    q6_share = (None if not posture_rows else
                sum(abs(row["arm_joint_pos"][5] - 1.57) > 0.3 for row in posture_rows) / len(posture_rows))
    at_most("stage0_5_j6_deviation_gt_0p3_frame_share", q6_share, 0.05)
    at_most("post_release_return_p50_s", fields["post_release_return_time_p50_s"], 2.0)
    at_most("post_release_return_p95_s", fields["post_release_return_time_p95_s"], 4.0)
    values = [check["pass"] for check in checks.values()]
    outcome = "CAMERA_UNMET" if False in values else "CAMERA_PARTIAL" if None in values else "CAMERA_MET"
    return {"outcome": outcome, "report_only": True, "checks": checks,
            "classification": "Any measured target failure: UNMET; no measured failure but missing events: PARTIAL; all targets measured and passed: MET.",
            "posture_frame_denominator": len(posture_rows),
            "release_censoring": camera["overall"]["post_release_return_time_s"]}


def driver_trace(path: Path, step: int) -> dict:
    rows = [json.loads(line) for line in path.read_text().splitlines() if line]
    rows = [row for row in rows if row["common_step"] <= step * 64]
    return {"source": str(path), "through_batch": step, "updates": len(rows),
            "first": rows[0] if rows else None, "last": rows[-1] if rows else None,
            "scale_min": min((row["scale_after"] for row in rows), default=None),
            "scale_max": max((row["scale_after"] for row in rows), default=None),
            "scope": "Observed training curriculum updates through the requested batch; not an independent causal comparison."}


def display(value):
    if value is None:
        return "null"
    if isinstance(value, float):
        return f"{value:.5g}"
    return str(value)


def build_readout(reducer_path: Path, manifest_path: Path, output: Path, train_root: Path | None = None):
    payload, manifest = read_json(reducer_path), read_json(manifest_path)
    require(not output.exists(), f"readout exists: {output}")
    require(output.suffix == ".md", "readout --output must end in .md")
    lanes = {(row["cell"], row["stratum"], row["side"]): row for row in manifest["lanes"]}
    stamp = datetime.now(ZoneInfo("Asia/Hong_Kong")).strftime("%Y-%m-%d %H:%M HKT")
    rows, traces = [], {}
    for cell, strata in payload["cells"].items():
        for stratum, sides in strata.items():
            for side, summary in sides.items():
                lane = lanes[(cell, stratum, side)]
                rows.append({"cell": cell, "stratum": stratum, "side": side,
                             "checkpoint": lane["checkpoint"], "seed": lane["seed"],
                             "artifact_path": lane["artifact_path"], "summary": summary,
                             "camera_assessment": camera_assessment(summary["camera_telemetry"])})
                train_dir = Path(lane["checkpoint"]).parent if train_root is None else train_root / cell
                trace = train_dir / "a2_v26_8_penalty_curriculum_trace.jsonl"
                if cell not in traces and trace.is_file():
                    traces[cell] = driver_trace(trace, payload["step"])
    report = {"schema": "a2_piper_v28_readout_v1", "recorded_at": stamp,
              "status": payload["status"], "evidence_level": "RUNTIME_OBSERVATION",
              "source_reducer": str(reducer_path.resolve()), "source_manifest": str(manifest_path.resolve()),
              "step": payload["step"], "expected_n": payload["expected_n"], "rows": rows,
              "typed_outcomes": payload["typed_outcomes"], "invalid_cells": payload["invalid_cells"],
              "k_driver_trace": traces,
              "limitations": ["Counts describe the evaluated checkpoints and first episodes only.",
                              "Absent events are null; camera targets are report-only.",
                              "Projection is a pinhole geometric proxy without occlusion or stereo reconstruction.",
                              "Sampled clearance is an upper bound, not exact clearance or hardware evidence.",
                              "A284 changes seed and driver and is not a driver causal comparison."]}
    lines = [f"# base_v28 step{payload['step']} readout", "", stamp, "",
             f"状态：`{payload['status']}`；每侧 exact {payload['expected_n']}。证据：实际模拟评估观测；资格结论以权威 decision 为准。", "",
             "| Cell | 侧/层 | D / S3+ / S4+ / open_hold / S5+ / complete / clean | 塔架 >5N 集数 | 塔架 >1N 步占比 | 松手后身体力 p95 N | crossing hinge p50 rad | 相机标签 |",
             "|---|---|---|---:|---:|---:|---:|---|"]
    for row in rows:
        summary = row["summary"]
        values = [row["cell"], f"{row['side']}/{row['stratum']}",
                  " / ".join(str(summary[key]) for key in METRICS),
                  summary["wrist_tower_contact_episodes_gt_5N"], summary["wrist_tower_contact_step_share"],
                  summary["post_release_body_force_p95"], summary["first_crossing_hinge_p50"],
                  row["camera_assessment"]["outcome"]]
        lines.append("| " + " | ".join(display(value) for value in values) + " |")
    lines += ["", "## 质量分量与阶段/相机事件", "",
              "无事件保留 null；相机标签仅报告，不改变 reach 或资格门。回位分位数仅基于已观察到回位的集，未回位集单列为右删失。", ""]
    for row in rows:
        summary = row["summary"]
        lines += [f"### {row['cell']} / {row['side']} / {row['stratum']}", "",
                  "```json", json.dumps({"quality_components": summary["clean_complete_components"],
                  "terminal_reasons": summary["terminal_reasons"],
                  "camera_plan_fields": summary["camera_telemetry"]["plan_fields"],
                  "camera_targets": row["camera_assessment"],
                  "event_counts": summary["camera_telemetry"]["sample_counts"]}, ensure_ascii=False, indent=2), "```", ""]
    lines += ["## 决策与 K trace", "", "```json", json.dumps({"typed_outcomes": payload["typed_outcomes"],
              "invalid_cells": payload["invalid_cells"], "k_driver_trace": traces}, ensure_ascii=False, indent=2), "```", "",
              "针孔投影未建模遮挡或双目重建；采样间隙为几何代理。学习失败伴随塔架接触不能证明几何无解；A284 结果不计入原三 seed 终点分母。", "",
              f"来源：[reducer]({reducer_path.resolve()})；[manifest]({manifest_path.resolve()})；完整逐阶段指标见相邻 JSON。"]
    write_json(output.with_suffix(".json"), report)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reducer", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--train-root", type=Path)
    args = parser.parse_args()
    report = build_readout(args.reducer, args.manifest, args.output, args.train_root)
    print(json.dumps({"status": report["status"], "readout": str(args.output.resolve())}))


if __name__ == "__main__":
    main()
