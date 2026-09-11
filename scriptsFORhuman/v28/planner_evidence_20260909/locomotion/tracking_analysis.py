#!/usr/bin/env python3
"""Per-stage base-command tracking error from DoorDog v27 eval step traces (stdlib only).

Fields used (per record in stage2_5_step_trace.json):
  stage_buf, physical_base_command[5] = [vx, vy, wz, pitch, roll] (physical, post-clip),
  base_lin_vel[3] (body frame), base_ang_vel[3] (body frame), root_roll/root_pitch (rad),
  post_delta_post_warp_base_action[5] (raw Teacher action fed to env, pre-scale/pre-clip).
Clip limits (door_open_a2_base.yaml): linvel x/y 0.5, angvel 0.5; pitch/roll raw clamp(-1,1)*0.4.
"""
import json
import math
import sys


def pct(values, p):
    if not values:
        return float("nan")
    s = sorted(values)
    k = (len(s) - 1) * p
    f = math.floor(k)
    c = min(f + 1, len(s) - 1)
    return s[f] + (s[c] - s[f]) * (k - f)


def analyse(path, label):
    with open(path) as f:
        recs = json.load(f)
    print(f"\n##### {label}: {path}")
    print(f"records={len(recs)}")
    per_stage = {}
    def quat_rot_inv(q, v):
        # q = [w,x,y,z] (IsaacLab wxyz); returns R(q)^T v
        w, x, y, z = q
        # rotate by conjugate
        cx, cy, cz = -x, -y, -z
        # t = 2 * cross(qv, v)
        tx = 2.0 * (cy * v[2] - cz * v[1])
        ty = 2.0 * (cz * v[0] - cx * v[2])
        tz = 2.0 * (cx * v[1] - cy * v[0])
        return [
            v[0] + w * tx + (cy * tz - cz * ty),
            v[1] + w * ty + (cz * tx - cx * tz),
            v[2] + w * tz + (cx * ty - cy * tx),
        ]

    for r in recs:
        st = int(r["stage_buf"])
        cmd = r["physical_base_command"]
        if "base_lin_vel" in r:
            lv = r["base_lin_vel"]
            av = r["base_ang_vel"]
        else:
            lv = quat_rot_inv(r["root_quat_w"], r["root_lin_vel_w"])
            av = quat_rot_inv(r["root_quat_w"], r["root_ang_vel_w"])
        raw = r.get("post_delta_post_warp_base_action")
        d = per_stage.setdefault(
            st,
            dict(
                n=0,
                evx=[], evy=[], ewz=[], epitch=[], eroll=[],
                cvx=[], cvy=[], cwz=[], cpitch=[], croll=[],
                rvx=[], rvy=[], rwz=[],
                clip_vx=0, clip_vy=0, clip_wz=0, clip_pitch=0, clip_roll=0, clip_any=0,
                raw_sat_vx=0, raw_sat_vy=0, raw_sat_wz=0, raw_sat_pr=0,
                standing_cmd=0,
            ),
        )
        d["n"] += 1
        d["evx"].append(lv[0] - cmd[0])
        d["evy"].append(lv[1] - cmd[1])
        d["ewz"].append(av[2] - cmd[2])
        # LMP/RoboDuet desired_body_pitch_roll_quat builds quat from (-pitch_cmd, -roll_cmd):
        # a positive command produces a NEGATIVE Euler angle, so the tracked target is -cmd.
        d["epitch"].append(r["root_pitch"] + cmd[3])
        d["eroll"].append(r["root_roll"] + cmd[4])
        d.setdefault("rpitch", []).append(r["root_pitch"])
        d.setdefault("rroll", []).append(r["root_roll"])
        d["cvx"].append(cmd[0]); d["cvy"].append(cmd[1]); d["cwz"].append(cmd[2])
        d["cpitch"].append(cmd[3]); d["croll"].append(cmd[4])
        d["rvx"].append(lv[0]); d["rvy"].append(lv[1]); d["rwz"].append(av[2])
        tol = 1e-4
        cx = abs(cmd[0]) >= 0.5 - tol
        cy = abs(cmd[1]) >= 0.5 - tol
        cz = abs(cmd[2]) >= 0.5 - tol
        cp = abs(cmd[3]) >= 0.4 - tol
        cr = abs(cmd[4]) >= 0.4 - tol
        d["clip_vx"] += cx; d["clip_vy"] += cy; d["clip_wz"] += cz
        d["clip_pitch"] += cp; d["clip_roll"] += cr
        d["clip_any"] += (cx or cy or cz or cp or cr)
        if raw is not None:
            # raw*0.25 vs 0.5 limit -> |raw|>2 ; pitch/roll raw clamp at |raw|>1
            d["raw_sat_vx"] += abs(raw[0]) > 2.0
            d["raw_sat_vy"] += abs(raw[1]) > 2.0
            d["raw_sat_wz"] += abs(raw[2]) > 2.0
            d["raw_sat_pr"] += (abs(raw[3]) > 1.0 or abs(raw[4]) > 1.0)
        if abs(cmd[0]) < 0.1 and abs(cmd[1]) < 0.1 and abs(cmd[2]) < 0.2:
            d["standing_cmd"] += 1

    print("stage | n | |e_vx| p50/p95 | |e_vy| p50/p95 | |e_wz| p50/p95 | |e_pitch| p50/p95 | |e_roll| p50/p95")
    for st in sorted(per_stage):
        d = per_stage[st]
        row = [f"{st}", f"{d['n']}"]
        for k in ("evx", "evy", "ewz", "epitch", "eroll"):
            a = [abs(v) for v in d[k]]
            row.append(f"{pct(a,0.5):.3f}/{pct(a,0.95):.3f}")
        print(" | ".join(row))
    print("\nstage | cmd vx p50/p95(|.|) | cmd vy p50/p95(|.|) | cmd wz p50/p95(|.|) | cmd pitch p50/p95(|.|) | cmd roll p50/p95(|.|) | mean cmd vx | mean cmd vy | mean cmd wz | mean cmd pitch | mean cmd roll")
    for st in sorted(per_stage):
        d = per_stage[st]
        row = [f"{st}"]
        for k in ("cvx", "cvy", "cwz", "cpitch", "croll"):
            a = [abs(v) for v in d[k]]
            row.append(f"{pct(a,0.5):.3f}/{pct(a,0.95):.3f}")
        for k in ("cvx", "cvy", "cwz", "cpitch", "croll"):
            row.append(f"{sum(d[k])/len(d[k]):+.3f}")
        print(" | ".join(row))
    print("\nstage | clip share vx | vy | wz | pitch | roll | any | raw-sat share vx | vy | wz | pitch/roll | standing-cmd share")
    for st in sorted(per_stage):
        d = per_stage[st]
        n = d["n"]
        print(
            f"{st} | {d['clip_vx']/n:.3f} | {d['clip_vy']/n:.3f} | {d['clip_wz']/n:.3f} | {d['clip_pitch']/n:.3f} | {d['clip_roll']/n:.3f} | {d['clip_any']/n:.3f} | "
            f"{d['raw_sat_vx']/n:.3f} | {d['raw_sat_vy']/n:.3f} | {d['raw_sat_wz']/n:.3f} | {d['raw_sat_pr']/n:.3f} | {d['standing_cmd']/n:.3f}"
        )
    # realized-vs-commanded regression slope (through origin) for vx, vy, wz, moving steps only
    print("\nstage | slope realized/cmd vx | vy | wz | pitch(Euler) | roll(Euler)  (least squares through origin, |cmd|>0.05; negative pitch/roll slope = LMP sign convention)")
    for st in sorted(per_stage):
        d = per_stage[st]
        out = [f"{st}"]
        for ck, rk in (("cvx", "rvx"), ("cvy", "rvy"), ("cwz", "rwz"), ("cpitch", "rpitch"), ("croll", "rroll")):
            num = den = 0.0
            for c, r in zip(d[ck], d[rk]):
                if abs(c) > 0.05:
                    num += c * r
                    den += c * c
            out.append(f"{num/den:.3f}" if den > 0 else "n/a")
        print(" | ".join(out))
    # pooled all stages
    allk = {k: [] for k in ("evx", "evy", "ewz", "epitch", "eroll")}
    n = 0
    for d in per_stage.values():
        n += d["n"]
        for k in allk:
            allk[k].extend(abs(v) for v in d[k])
    print(f"\nALL stages n={n} | " + " | ".join(f"{k} p50/p95 {pct(v,0.5):.3f}/{pct(v,0.95):.3f}" for k, v in allk.items()))
    return per_stage


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        label, path = arg.split("=", 1)
        analyse(path, label)
