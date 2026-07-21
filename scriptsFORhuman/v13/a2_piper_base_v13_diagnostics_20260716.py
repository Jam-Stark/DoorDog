"""v13 前置诊断:
T1  A step3000 env14/15 stage3 timeline
T2  repair-B500 深抓握力学标定 (squeeze 分布 / jaw 位置 / control-step streak)
T3  v10_D 训练日志: stage2 stability & advance 趋势 (gate 可过性)
T4  C step3000 counterfactual: 去抖 gate 的首次通过步
"""
import json, re, sys, glob

BASE = "/home/baoquanc/workspace/DoorDog-A2_Piper"


def load_first_episode(path):
    recs = json.load(open(path))
    envs = {}
    for r in recs:
        if not r.get("first_episode_active", True):
            continue
        envs.setdefault(r["env_id"], []).append(r)
    for e in envs:
        envs[e].sort(key=lambda r: r["step_index"])
    return envs


def squeeze3(r):
    f = r["handle_contact_force_norm"]
    sy = r["squeeze_y"]
    both = f[0] > 1.0 and f[1] > 1.0
    suff = abs(sy[0]) > 0.5 and abs(sy[1]) > 0.5
    opp = sy[0] * sy[1] < 0
    return both and suff and opp


def t1_a_stage3_timeline():
    print("=" * 20, "T1: v12_A step3000 stage3 timelines", "=" * 20)
    envs = load_first_episode(
        f"{BASE}/logs_eval/base_v12/base_v12_A_ckpt3000_matched_scalar_trace_16env_seed0_20260716/stage2_5_step_trace.json"
    )
    for e in sorted(envs):
        rows = [r for r in envs[e] if r["stage_buf"] >= 3]
        if not rows:
            continue
        n = len(rows)
        both = sum(1 for r in rows if r["both_contact"]) / n
        stab = sum(1 for r in rows if r["contact_stability"]) / n
        sq3 = sum(1 for r in rows if squeeze3(r)) / n
        hmax = max(r["door_hinge_joint_pos"] for r in rows)
        handle_max = max(r["door_handle_joint_pos"] for r in rows)
        close_cmd = sum(1 for r in rows if r["gripper_primitive_raw"][0] < -0.2) / n
        j8_open = sum(1 for r in rows if r["arm_j7_j8_pos"][1] < -0.030) / n
        tcp = sorted(r["target_pos_source_handle_distance"] for r in rows)
        print(
            f"env{e}: n={n} both%={100*both:.1f} sq3%={100*sq3:.1f} stab%={100*stab:.1f} "
            f"closecmd%={100*close_cmd:.1f} hinge_max={hmax:.5f} handle_max={handle_max:.4f} "
            f"j8_open%={100*j8_open:.1f} tcp_med={tcp[n//2]:.4f}"
        )
        for i, r in enumerate(rows):
            if i % 10 == 0 or i == n - 1:
                bc = r.get("physical_base_command")
                bc = [round(x, 2) for x in bc[:3]] if bc else None
                print(
                    f"   t={r['step_index']:4d} st={r['stage_buf']} hinge={r['door_hinge_joint_pos']:.4f} "
                    f"handle={r['door_handle_joint_pos']:.3f} f={[round(x,1) for x in r['handle_contact_force_norm']]} "
                    f"sy={[round(x,2) for x in r['squeeze_y']]} "
                    f"j78=[{r['arm_j7_j8_pos'][0]:.3f},{r['arm_j7_j8_pos'][1]:.3f}] "
                    f"prim={r['gripper_primitive_raw'][0]:.2f} tcp={r['target_pos_source_handle_distance']:.3f} base={bc}"
                )


def t2_deep_grasp(trace_path, label):
    print("=" * 20, f"T2: {label} deep-grasp calibration", "=" * 20)
    envs = load_first_episode(trace_path)
    lo, hi, j7p, j8p = [], [], [], []
    streaks = []
    stab_frames = tot = 0
    for e in envs:
        rows = [r for r in envs[e] if r["stage_buf"] >= 3]
        cur = 0
        for r in rows:
            tot += 1
            if r["contact_stability"]:
                stab_frames += 1
            if r["both_contact"]:
                a, b = sorted([abs(r["squeeze_y"][0]), abs(r["squeeze_y"][1])])
                lo.append(a)
                hi.append(b)
                j7p.append(r["arm_j7_j8_pos"][0])
                j8p.append(r["arm_j7_j8_pos"][1])
            cur = cur + 1 if squeeze3(r) else (streaks.append(cur) or 0) if cur else 0
        if cur:
            streaks.append(cur)
    if not lo:
        print("  (no bilateral frames in stage>=3)")
        return
    lo.sort(); hi.sort(); j7p.sort(); j8p.sort()
    q = lambda a, p: a[int(p * (len(a) - 1))]
    print(f"  stage>=3 frames={tot}  env-frame contact_stability%={100*stab_frames/max(tot,1):.1f}")
    print(f"  weaker |sy| p10/50/90 = {q(lo,.1):.2f}/{q(lo,.5):.2f}/{q(lo,.9):.2f} N")
    print(f"  stronger |sy| p10/50/90 = {q(hi,.1):.2f}/{q(hi,.5):.2f}/{q(hi,.9):.2f} N")
    print(f"  j7 pos p10/50/90 = {q(j7p,.1):.4f}/{q(j7p,.5):.4f}/{q(j7p,.9):.4f} m")
    print(f"  j8 pos p10/50/90 = {q(j8p,.1):.4f}/{q(j8p,.5):.4f}/{q(j8p,.9):.4f} m")
    if streaks:
        streaks.sort()
        print(f"  control-step squeeze3 streaks: n={len(streaks)} p50={streaks[len(streaks)//2]} max={streaks[-1]}")


def t3_v10d_trend():
    print("=" * 20, "T3: v10_D training trend (gate passability @Kp160)", "=" * 20)
    logs = glob.glob(
        f"{BASE}/logs_rl/a2_piper_full_stage_a2_base/base_v10_D_scratch_hold_reward_kp160_base-*/.wandb/wandb/run-*/files/output.log"
    )
    keys = [
        "Env/average_stage_reached",
        "Env/a2_stage2_to3_advance_frac",
        "Env/a2_stage2_both_contact_frac",
        "Env/a2_stage2_contact_stability_frac",
        "Env/a2_stage3_active_frac",
        "Env/a2_stage4_active_frac",
        "Env/a2_door_hinge_joint_pos_mean",
    ]
    it_re = re.compile(r"Learning iteration (\d+)")
    kv_re = re.compile(r"(Env/[A-Za-z0-9_]+):\s*(-?[\d.e+-]+)")
    rows = {}
    cur = None
    for line in open(logs[0], errors="ignore"):
        m = it_re.search(line)
        if m:
            cur = int(m.group(1))
            rows.setdefault(cur, {})
            continue
        if cur is None:
            continue
        m = kv_re.search(line)
        if m and m.group(1) in keys:
            rows[cur][m.group(1)] = float(m.group(2))
    its = sorted(rows)
    sel = [i for i in its if i % 100 == 0 or i == its[-1]]
    print("iter\tstage\tadv2to3\ts2both\ts2stab\ts3act\ts4act\thinge")
    for i in sel:
        r = rows[i]
        print(
            "\t".join(
                [str(i)]
                + [f"{r.get(k, float('nan')):.4f}" for k in keys]
            )
        )


def t4_c_counterfactual():
    print("=" * 20, "T4: v12_C step3000 counterfactual debounced gate", "=" * 20)
    envs = load_first_episode(
        f"{BASE}/logs_eval/base_v12/base_v12_C_ckpt3000_matched_scalar_trace_16env_seed0_20260716/stage2_step_trace.json"
    )
    for K in (3, 5, 8):
        firsts = []
        for e in sorted(envs):
            rows = [r for r in envs[e] if r["stage_buf"] == 2]
            cur = 0
            first = None
            for idx, r in enumerate(rows):
                cur = cur + 1 if squeeze3(r) else 0
                if cur >= K:
                    first = idx
                    break
            firsts.append((e, first))
        passed = [f for _, f in firsts if f is not None]
        print(
            f"  K={K} control-steps: pass {len(passed)}/16, first-pass stage2-step "
            f"min/med/max = {min(passed) if passed else '-'} / "
            f"{sorted(passed)[len(passed)//2] if passed else '-'} / {max(passed) if passed else '-'}"
        )


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("all", "t1"):
        t1_a_stage3_timeline()
    if which in ("all", "t4"):
        t4_c_counterfactual()
    if which in ("all", "t3"):
        t3_v10d_trend()
    if which in ("all", "t2"):
        for p in sys.argv[2:]:
            t2_deep_grasp(p, p.split("/")[-2])
