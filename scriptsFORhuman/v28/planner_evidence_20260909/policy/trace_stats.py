#!/usr/bin/env python3
"""Stream the v27 q0_dev stage2-5 step trace and compute per-stage income / motion stats.

READ-ONLY on the repo; writes JSON summary under /tmp/v28_team/policy/.
Usage: python3 trace_stats.py <stage2_5_step_trace.json> <out.json>
"""
import json
import math
import sys
from collections import defaultdict

DEFAULT_ARM = [0.0, 0.0, 0.0, 0.25, 0.5, 1.57]  # v27 default_joint_angles arm_j1..j6
HARD_FLOOR = 3.0


def pct(xs, q):
    if not xs:
        return None
    xs = sorted(xs)
    k = (len(xs) - 1) * q
    f = math.floor(k)
    c = min(f + 1, len(xs) - 1)
    return xs[f] + (xs[c] - xs[f]) * (k - f)


def stream_records(path, chunk=8_000_000):
    dec = json.JSONDecoder()
    with open(path) as fh:
        buf = fh.read(chunk)
        i = buf.index("[") + 1
        while True:
            while i < len(buf) and buf[i] in " \n\r\t,":
                i += 1
            if i >= len(buf) or buf[i] == "]":
                more = fh.read(chunk)
                if not more:
                    return
                buf = buf[i:] + more
                i = 0
                continue
            try:
                obj, end = dec.raw_decode(buf, i)
            except json.JSONDecodeError:
                more = fh.read(chunk)
                if not more:
                    raise
                buf = buf[i:] + more
                i = 0
                continue
            i = end
            yield obj
            if i > chunk:
                buf = buf[i:]
                i = 0


def main():
    path, out = sys.argv[1], sys.argv[2]
    prev = {}  # env_id -> last record
    stages = (2, 3, 4, 5)
    n = defaultdict(int)
    rew = {s: defaultdict(float) for s in stages}
    dq = {s: {j: [] for j in range(6)} for s in stages}
    a_raw = {s: {j: [] for j in range(6)} for s in stages}
    sum_dq2_all = defaultdict(float)
    sum_dq2_wrist = defaultdict(float)
    sum_a2_all = defaultdict(float)
    sum_a2_wrist = defaultdict(float)
    sum_overspeed = defaultdict(float)
    sum_l1_dev = defaultdict(float)
    l1_dev_list = {s: [] for s in stages}
    flips_wrist = defaultdict(int)  # sign flips of dq (|dq|>0.3 both sides) for j4..j6
    flip_denom = defaultdict(int)
    # stage3 depression-specific
    dep_dq6 = []
    dep_dq6_creation = []
    dep_handle_vel = []
    stage3_dq6_all = []
    # stage4 released & no contact
    rel_n = 0
    rel_l1 = []
    rel_dq_wrist2 = 0.0
    rel_rew = defaultdict(float)
    hold_n = 0
    hold_rew = defaultdict(float)
    total = 0
    for r in stream_records(path):
        total += 1
        s = r["stage_buf"]
        env = r["env_id"]
        p = prev.get(env)
        consecutive = (
            p is not None
            and p["episode_index"] == r["episode_index"]
            and r["episode_length_buf"] == p["episode_length_buf"] + 1
        )
        prev[env] = r
        if s not in stages:
            continue
        n[s] += 1
        v = r["arm_joint_vel"]
        a = r["policy_arm_action_raw"]
        q = r["arm_joint_pos"]
        for j in range(6):
            dq[s][j].append(abs(v[j]))
            a_raw[s][j].append(a[j])
        sum_dq2_all[s] += sum(x * x for x in v)
        sum_dq2_wrist[s] += sum(v[j] * v[j] for j in (3, 4, 5))
        sum_a2_all[s] += sum(x * x for x in a)
        sum_a2_wrist[s] += sum(a[j] * a[j] for j in (3, 4, 5))
        sum_overspeed[s] += sum(max(abs(x) - HARD_FLOOR, 0.0) ** 2 for x in v)
        l1 = sum(abs(q[j] - DEFAULT_ARM[j]) for j in range(6))
        sum_l1_dev[s] += l1
        l1_dev_list[s].append(l1)
        if consecutive:
            pv = p["arm_joint_vel"]
            for j in (3, 4, 5):
                flip_denom[s] += 1
                if abs(v[j]) > 0.3 and abs(pv[j]) > 0.3 and (v[j] > 0) != (pv[j] > 0):
                    flips_wrist[s] += 1
            # per-step scaled reward = diff of episode sums
            cur = r["reward_episode_sums"]
            old = p["reward_episode_sums"]
            for k, val in cur.items():
                rew[s][k] += val - old.get(k, 0.0)
            if s == 3:
                hd = r["door_handle_joint_pos"] - p["door_handle_joint_pos"]
                stage3_dq6_all.append(abs(v[5]))
                if hd > 1e-4:
                    dep_dq6.append(abs(v[5]))
                    dep_handle_vel.append(hd / 0.02)
                if r["v26_3"].get("creation_active_cached") and r["v26_3"].get("creation_raw_cached", 0.0) > 0:
                    dep_dq6_creation.append(abs(v[5]))
            if s == 4:
                released = r["door_hinge_joint_pos"] >= 1.2 and not r["both_contact"]
                if released:
                    rel_n += 1
                    rel_l1.append(l1)
                    rel_dq_wrist2 += sum(v[j] * v[j] for j in (3, 4, 5))
                    for k, val in cur.items():
                        rel_rew[k] += val - old.get(k, 0.0)
                elif r["both_contact"]:
                    hold_n += 1
                    for k, val in cur.items():
                        hold_rew[k] += val - old.get(k, 0.0)

    res = {"total_records": total, "stages": {}}
    for s in stages:
        if n[s] == 0:
            continue
        per_step = {k: val / max(n[s] - 0, 1) for k, val in rew[s].items()}
        pos = sum(x for x in per_step.values() if x > 0)
        neg = sum(x for x in per_step.values() if x < 0)
        res["stages"][str(s)] = {
            "steps": n[s],
            "per_step_scaled_reward_by_term": {k: round(x, 6) for k, x in sorted(per_step.items(), key=lambda kv: -abs(kv[1]))},
            "per_step_positive_income": pos,
            "per_step_negative_income": neg,
            "abs_dq_p50": {f"j{j+1}": pct(dq[s][j], 0.5) for j in range(6)},
            "abs_dq_p95": {f"j{j+1}": pct(dq[s][j], 0.95) for j in range(6)},
            "a_raw_rms": {f"j{j+1}": math.sqrt(sum(x * x for x in a_raw[s][j]) / len(a_raw[s][j])) for j in range(6)},
            "mean_sum_dq2_j1_6": sum_dq2_all[s] / n[s],
            "mean_sum_dq2_j4_6": sum_dq2_wrist[s] / n[s],
            "mean_sum_a2_j1_6": sum_a2_all[s] / n[s],
            "mean_sum_a2_j4_6": sum_a2_wrist[s] / n[s],
            "mean_overspeed_raw": sum_overspeed[s] / n[s],
            "mean_l1_dev_from_default_j1_6": sum_l1_dev[s] / n[s],
            "l1_dev_p50": pct(l1_dev_list[s], 0.5),
            "l1_dev_p95": pct(l1_dev_list[s], 0.95),
            "wrist_sign_flip_rate_per_s": (flips_wrist[s] / flip_denom[s]) * 3 / 0.02 if flip_denom[s] else None,
        }
    res["stage3_depression"] = {
        "steps_handle_increasing": len(dep_dq6),
        "abs_dq6_p50": pct(dep_dq6, 0.5),
        "abs_dq6_p95": pct(dep_dq6, 0.95),
        "handle_vel_p50": pct(dep_handle_vel, 0.5),
        "handle_vel_p95": pct(dep_handle_vel, 0.95),
        "steps_creation_active": len(dep_dq6_creation),
        "creation_abs_dq6_p50": pct(dep_dq6_creation, 0.5),
        "creation_abs_dq6_p95": pct(dep_dq6_creation, 0.95),
        "stage3_all_abs_dq6_p50": pct(stage3_dq6_all, 0.5),
        "stage3_all_abs_dq6_p95": pct(stage3_dq6_all, 0.95),
    }
    res["stage4_released_no_contact"] = {
        "steps": rel_n,
        "l1_dev_p50": pct(rel_l1, 0.5),
        "l1_dev_p95": pct(rel_l1, 0.95),
        "mean_sum_dq2_j4_6": rel_dq_wrist2 / rel_n if rel_n else None,
        "per_step_scaled_reward_by_term": {k: round(x / rel_n, 6) for k, x in sorted(rel_rew.items(), key=lambda kv: -abs(kv[1])) if rel_n and abs(x / rel_n) > 1e-6},
    }
    res["stage4_holding"] = {
        "steps": hold_n,
        "per_step_scaled_reward_by_term": {k: round(x / hold_n, 6) for k, x in sorted(hold_rew.items(), key=lambda kv: -abs(kv[1])) if hold_n and abs(x / hold_n) > 1e-6},
    }
    with open(out, "w") as fh:
        json.dump(res, fh, indent=1)
    print(json.dumps({"total": total, "steps_by_stage": dict(n)}))


if __name__ == "__main__":
    main()
