#!/usr/bin/env python3
"""Read only the small pull v28 decision, never reparse its source trace."""
from __future__ import annotations
import argparse
import json
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--decision",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    if a.output.exists():
        raise FileExistsError(a.output)
    d=json.loads(a.decision.read_text())
    lines=[f"# Pull v28 milestone {d['step']}","",f"Route: `{d['route']}`.","",
        "| Cell | Side | K5 | D | E4 | E5 | E6 | E7 | Tower >5N | Margin | Camera |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |"]
    for cell,sides in d["cells"].items():
        for side,r in sides.items():
            if r["status"] != "VALID":
                lines += [f"| {cell} | {side} | INVALID | — | — | — | — | — | — | — | — |",
                          "",f"{cell}/{side}: `{r['error']}`.",""]
                continue
            counts=" | ".join(f"{r[key]}/64" for key in ("K5","D","E4","E5","E6","E7","tower_contact_episode_gt5N"))
            lines.append(f"| {cell} | {side} | {counts} | {r['margin']['status']} | {r['camera']['status']} |")
    if d["endpoint"]:
        lines += ["",f"原三 seed 6000 endpoint：**{d['k_of_3']['passing']}/3**。"]
    else:
        lines += ["","这是按已就绪格形成的 milestone；没有发布原三 seed 6000 opening 终点。",
                  f"尚缺有效原格：{', '.join(d['endpoint_pending_original_cells']) or '当前非6000里程碑'}。"]
    for cell,sides in d["cells"].items():
        for side,r in sides.items():
            if r["status"] != "VALID":
                continue
            m=r["margin"]; ready=r["release_ready"]; camera=r["camera"]
            lines += ["",f"**{cell}/{side} 中介**：E5={m['e5_episodes']}/64，E5后样本={m['post_e5_samples']}，margin≥.07步份额={m['margin_ge_0_07_step_fraction']}；六关节target overshoot中位数={m['joint_target_overshoot_median']}。",
                f"Ready={ready['episodes']}/64（{ready['steps']}步），clean release={ready['clean_release_episodes']}/64；4A/4B={r['retained_4a_4b']}。",
                f"Camera可判项={camera['available_checks']}/{camera['total_checks']}，事件/阶段样本={camera['sample_counts']}。回位右删失episode={camera['overall']['post_release_return_time_s']['right_censored_episodes']}。"]
    if d["history"]:
        lines += ["","历史checkpoint单列（不替代6000 endpoint）："]
        for h in d["history"]:
            lines.append(f"- Step {h['step']}: {h['per_seed_opening']} ({h['path']})")
    lines += ["","Camera阈值仅报告；投影/min-Z不代表无遮挡或有效深度，采样clearance不代表硬件精确间隙。crossing yaw绑定pull E6；无事件=null。Opening不授予Teacher/Student资格。"]
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text("\n".join(lines)+"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
