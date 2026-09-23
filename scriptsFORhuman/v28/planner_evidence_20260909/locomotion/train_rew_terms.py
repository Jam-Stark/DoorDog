#!/usr/bin/env python3
import re, collections, sys

TERMS = [
    "penalty_not_standing_still", "penalty_base_command_limit", "orientation_control",
    "penalty_base_roll_pitch_l2", "penalty_standing_still", "penalty_face_door",
    "penalty_a2_stage1_stage2_base_forward_creep", "ref_dof_legs", "walk_to_door",
    "target_root_distance", "stage", "complete", "success_save_time", "termination",
]
BASE_PEN = ["penalty_not_standing_still", "penalty_base_command_limit", "orientation_control",
            "penalty_base_roll_pitch_l2", "penalty_standing_still", "penalty_face_door",
            "penalty_a2_stage1_stage2_base_forward_creep"]

for path in sys.argv[1:]:
    txt = open(path, errors="replace").read()
    starts = [m.start() for m in re.finditer(r"Learning iteration\s+(\d+)", txt)]
    iters = [int(m.group(1)) for m in re.finditer(r"Learning iteration\s+(\d+)", txt)]
    print(f"=== {path}: blocks={len(starts)} first_iter={iters[0] if iters else None} last_iter={iters[-1] if iters else None}")
    def parse(block):
        d = {k: float(v) for k, v in re.findall(r"Mean episode rew_([A-Za-z0-9_]+):\s*([-+0-9.eE]+)", block)}
        m = re.search(r"Mean rewards:\s*([-+0-9.eE]+)", block)
        d["__mean_rewards"] = float(m.group(1)) if m else float("nan")
        m = re.search(r"Mean length:\s*([-+0-9.eE]+)", block)
        d["__mean_length"] = float(m.group(1)) if m else float("nan")
        m = re.search(r"Env/average_goal_reached:\s*([-+0-9.eE]+)", block)
        d["__goal"] = float(m.group(1)) if m else float("nan")
        m = re.search(r"Env/average_stage_reached:\s*([-+0-9.eE]+)", block)
        d["__stage_reached"] = float(m.group(1)) if m else float("nan")
        return d
    for label, sel in (("last-50-iters", starts[-50:]), ("iters~2950-3000", None)):
        if sel is None:
            sel = [s for s, it in zip(starts, iters) if 2950 <= it <= 3000]
            if not sel:
                continue
        acc = collections.defaultdict(list)
        for i, s in enumerate(sel):
            e = txt.find("Learning iteration", s + 20)
            blk = txt[s:e if e > 0 else s + 300000]
            for k, v in parse(blk).items():
                acc[k].append(v)
        mean = {k: sum(v) / len(v) for k, v in acc.items() if v}
        n_blocks = len(sel)
        print(f"--- window {label}: n_blocks={n_blocks} mean_rewards={mean.get('__mean_rewards'):.3f} mean_length={mean.get('__mean_length'):.1f} goal={mean.get('__goal'):.3f} stage_reached={mean.get('__stage_reached'):.3f}")
        pos = sum(v for k, v in mean.items() if not k.startswith("__") and v > 0)
        neg = sum(v for k, v in mean.items() if not k.startswith("__") and v < 0)
        print(f"    sum(all rew_* means) = {pos+neg:.4f}   positive={pos:.4f}   negative={neg:.4f}")
        for t in TERMS:
            if t in mean:
                share = (mean[t] / neg * 100) if (neg and mean[t] < 0) else float("nan")
                print(f"    rew_{t:45s} {mean[t]:+.4f}" + (f"   ({share:.1f}% of negative)" if mean[t] < 0 else ""))
        bp = sum(mean.get(t, 0.0) for t in BASE_PEN)
        print(f"    base-behaviour penalties sum = {bp:+.4f}  = {bp/neg*100 if neg else float('nan'):.1f}% of all negative, {abs(bp)/pos*100 if pos else float('nan'):.1f}% of positive income")
        top_neg = sorted(((v, k) for k, v in mean.items() if not k.startswith("__") and v < 0))[:8]
        print("    top negative terms: " + ", ".join(f"{k}={v:+.4f}" for v, k in top_neg))
