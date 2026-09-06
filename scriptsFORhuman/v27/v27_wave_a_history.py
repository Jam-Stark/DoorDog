"""Append descriptive parent-policy comparisons to a Wave A readout."""
from __future__ import annotations

import argparse
from pathlib import Path

from v27_contract import EVAL, RUNTIME, METRICS, read_json, write_json
from v27_reduce import passes_gate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--step", type=int, required=True)
    parser.add_argument("--readout", type=Path, required=True)
    args = parser.parse_args()
    current = read_json(EVAL / "wave_a" / f"step{args.step}" / "reducer.json")
    reference_path = EVAL / "q0_dev_cpu_adjudicated" / "reducer.json"
    parent = read_json(reference_path)["cells"]["C_S2"]["DEV"]
    differences, gates = {}, {}
    for cell, strata in current["cells"].items():
        for side, row in strata["nominal"].items():
            label = f"{cell}/{side}"
            reference = parent[side]
            differences[label] = {
                metric: 100 * (row[metric] / row["episodes"] - reference[metric] / reference["episodes"])
                for metric in METRICS
            }
            gates[label] = passes_gate(row)
    record = {
        "reference": str(reference_path), "reference_cell": "C_S2",
        "reference_episodes_per_side": 128, "current_episodes_per_side": 64,
        "comparison": "Descriptive percentage-point differences; different N, not paired episode trajectories.",
        "all_metric_deltas_pp": differences, "current_side_gates": gates,
    }
    write_json(RUNTIME / f"wave_a_step{args.step}_historical_deltas.json", record)
    supplement = read_json(args.readout.with_suffix(".json"))
    supplement["historical_reference"] = record
    write_json(args.readout.with_suffix(".json"), supplement, replace=True)
    with args.readout.open("a") as stream:
        stream.write("\n## 父策略历史比较\n\n")
        stream.write("参考 C_S2 的 Q0 DEV（每侧128）；以下为百分点差，N128与N64不视为逐episode配对。\n\n")
        stream.write("| Cell/侧 | D Δpp | S3+ Δpp | S4+ Δpp | open_hold Δpp | S5+ Δpp | complete Δpp | clean Δpp |\n")
        stream.write("|---|---:|---:|---:|---:|---:|---:|---:|\n")
        for label, values in differences.items():
            stream.write("| " + label + " | " + " | ".join(f"{values[metric]:+.2f}" for metric in METRICS) + " |\n")
        passing = [label for label, passed in gates.items() if passed]
        stream.write("\n本次通过完整64样本门的侧：" + ("、".join(passing) if passing else "无") + "。非endpoint不结算配方。\n")
        stream.write("\n松手后身体力无读数不能当作0 N；clean判据使用首次Stage3至终止的身体力峰值。Wave A不启用K或恢复环。\n")
    print(record)


if __name__ == "__main__":
    main()
