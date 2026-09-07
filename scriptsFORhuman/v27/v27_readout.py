"""Render source-backed v27 milestone tables without changing reducer outcomes."""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from v27_contract import ROOT, HERE, RUNTIME, TRAIN, METRICS, read_json, require, write_json, train_checkpoint


def cell_pairs(cells):
    pairs = []
    for cell in cells:
        arm, seed = cell.rsplit("_S", 1)
        if arm in ("Q1","Q2"): control = f"C_S{seed}"
        elif arm == "L1": control = "L0_S31"
        elif arm in ("R1","R2"): control = "R0_S41"
        elif arm == "SK": control = f"SC_S{int(seed)-10}"
        else: continue
        if control in cells: pairs.append((cell,control))
    return pairs


def deltas(cells):
    result = {}
    for cell,control in cell_pairs(cells):
        result[f"{cell}−{control}"] = {
            stratum: {side: {metric: cells[cell][stratum][side][metric] - cells[control][stratum][side][metric]
                            for metric in METRICS}
                      for side in ("left","right")}
            for stratum in cells[cell] if stratum in cells[control]}
    return result


def k_trace(path, step):
    source = ROOT / "scriptsFORhuman/v26_8/v26_8_reduce.py"
    spec = importlib.util.spec_from_file_location("v26_8_k_trace_reader", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.trace_summary(path, step)


def training_telemetry(path, step):
    iteration_pattern = re.compile(r"Learning iteration\s+(\d+)")
    metric_pattern = re.compile(r"Env/(a2_v27_[a-z0-9_]+):\s+([-+0-9.eE]+)")
    iteration, recorded_iteration, values = 0, None, {}
    with path.open() as stream:
        for line in stream:
            matched = iteration_pattern.search(line)
            if matched:
                iteration = int(matched.group(1))
                if iteration > step:
                    break
            matched = metric_pattern.search(line)
            if matched:
                recorded_iteration = iteration
                values[matched.group(1)] = float(matched.group(2))
    return {"source":str(path.resolve()),"iteration":recorded_iteration,"metrics":values,
            "aggregation":"Trainer means across the PPO batch; cumulative counters are batch-averaged snapshots, not exact end-of-batch totals."}


def supplemental_quality(manifest):
    result = {}
    for lane in manifest["lanes"]:
        path = Path(lane["artifact_path"]) / "metrics_eval.json"
        if not path.is_file(): continue
        metrics = read_json(path)
        rows = metrics["episode_terminal_diagnostics"]
        reasons = {"complete_with_crossing_hinge_below_threshold": 0,
                   "complete_with_body_contact_above_5N": 0,
                   "complete_without_crossing_measurement": 0}
        for row in rows:
            if row["terminal_reasons"] != "complete": continue
            record = row["a2_v27"]
            hinge = record["first_crossing_hinge_rad"]
            reasons["complete_without_crossing_measurement"] += int(hinge is None)
            reasons["complete_with_crossing_hinge_below_threshold"] += int(hinge is not None and hinge < 1.0472)
            reasons["complete_with_body_contact_above_5N"] += int(record["body_panel_force_max_from_stage3_n"] > 5.0)
        result[f"{lane['cell']}/{lane['stratum']}/{lane['side']}"] = reasons
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reducer", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--train-root", type=Path)
    parser.add_argument("--previous", type=Path)
    args = parser.parse_args()
    payload, manifest = read_json(args.reducer), read_json(args.manifest)
    require(not args.output.exists(), "readout output exists")
    cells, step = payload["cells"], payload["step"]
    pairs = deltas(cells)
    gpu = subprocess.check_output(["nvidia-smi", "--query-gpu=index,memory.used,memory.total,utilization.gpu", "--format=csv,noheader"], text=True).splitlines()
    processes = subprocess.check_output(["ps", "-eo", "pid,ppid,etime,args"], text=True).splitlines()
    processes = [line for line in processes if ("v27_" in line or "base_v27/" in line) and "ps -eo" not in line]
    receipts = {}
    for path in sorted((ROOT / ".ai/runtime/runs").glob("v27_*/RUN_RECEIPT.json")):
        row = read_json(path)
        exit_path = path.parent / "exit_code.txt"
        receipts[row["name"]] = {"state": row["state"], "returncode": int(exit_path.read_text()) if exit_path.exists() else None,
                                  "path": str(path)}
    traces, training = {}, {}
    if args.train_root:
        for cell in cells:
            directory = args.train_root / cell
            if args.train_root.resolve() == TRAIN.resolve():
                directory = train_checkpoint(cell, step).parent
            path = directory / "a2_v26_8_penalty_curriculum_trace.jsonl"
            if path.is_file(): traces[cell] = k_trace(path, step)
            path = directory / "runtime.log"
            if path.is_file(): training[cell] = training_telemetry(path, step)
    reversals = []
    for pair,strata in pairs.items():
        for stratum,sides in strata.items():
            for side,values in sides.items():
                negative = {key:value for key,value in values.items() if value < 0}
                if negative: reversals.append({"reference":pair,"stratum":stratum,"side":side,"negative_deltas":negative})
    if args.previous:
        previous = read_json(args.previous)["cells"]
        for cell,strata in cells.items():
            for stratum,sides in strata.items():
                for side,values in sides.items():
                    if cell in previous and stratum in previous[cell] and side in previous[cell][stratum]:
                        negative = {key:values[key]-previous[cell][stratum][side][key] for key in METRICS
                                    if values[key] < previous[cell][stratum][side][key]}
                        if negative: reversals.append({"reference":f"{cell}−previous","stratum":stratum,"side":side,"negative_deltas":negative})
    supplement = {"paired_deltas":pairs,"negative_deltas":reversals,"k_trace":traces,"training_telemetry":training,
                  "quality_failure_components":supplemental_quality(manifest),"receipts":receipts,"gpu":gpu,"processes":processes}
    write_json(args.output.with_suffix(".json"), supplement)
    lines = [f"# base_v27 {manifest['name']} readout", "", datetime.now(ZoneInfo("Asia/Hong_Kong")).strftime("%Y-%m-%d %H:%M HKT"), "",
             f"状态：`{payload['status']}`；step={step}；exact N={payload['expected_n']}。", "",
             "计数顺序：D / S3+ / S4+ / open_hold / S5+ / complete / clean_complete。", "",
             "| Cell | 层 | 侧 | 计数 | 握门穿过 | 松手后身体力 p95 (N) | 首次 crossing hinge p50 (rad) | 集长 p50 | arm_j4 限位占比 | 终止原因 | integrity |",
             "|---|---|---|---|---:|---:|---:|---:|---:|---|---:|"]
    for cell,strata in cells.items():
        for stratum,sides in strata.items():
            for side,row in sides.items():
                values = [cell,stratum,side,"/".join(str(row[key]) for key in METRICS),row["hold_through"],row["post_release_body_force_p95"],
                          row["first_crossing_hinge_p50"],row["episode_length_p50"],row["arm_j4_limit_residence_step_share"],
                          json.dumps(row["terminal_reasons"],ensure_ascii=False),row["integrity_violations"]]
                lines.append("| " + " | ".join(map(str,values)) + " |")
    lines += ["", "## 配对差与反向读数", "", "L1_S32 对 L0_S31、SK 对相同序号 SC 使用预注册配对；PPO seed 数值不同，不宣称同随机轨迹的因果对照。", "",
              "```json",json.dumps({"paired_deltas":pairs,"negative_deltas":reversals},ensure_ascii=False,indent=2),"```", "",
              "## Typed outcomes", "", "```json",json.dumps(payload["typed_outcomes"],ensure_ascii=False,indent=2),"```", "",
              "## 质量失败成分、K 与恢复 telemetry", "", "```json",json.dumps({"quality":supplement["quality_failure_components"],"k":traces,"training":training,
                  "recovery":{f"{cell}/{stratum}/{side}":row["recovery_itt"] for cell,strata in cells.items() for stratum,sides in strata.items() for side,row in sides.items() if "recovery_itt" in row}},ensure_ascii=False,indent=2),"```", "",
              "## Receipt 与资源", "", "```json",json.dumps({"invalid_cells":payload["invalid_cells"],"receipts":receipts,"gpu":gpu,"processes":processes},ensure_ascii=False,indent=2),"```", "",
              f"来源：[reducer]({args.reducer.resolve()})；[eval manifest]({args.manifest.resolve()})。", "",
              "证据：真实模拟评估/注册条件下的计数；不构成硬件或部署证据。"]
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
