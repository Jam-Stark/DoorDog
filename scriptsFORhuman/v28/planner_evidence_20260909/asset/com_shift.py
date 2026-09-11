"""Whole-robot mass/COM at default posture, old vs new URDF (STATIC; trunk frame, legs at default)."""
import os, sys, json
import numpy as np
sys.path.insert(0, "/tmp/v28_team/asset")
from mount_clearance_check import parse, fk, T, OLD, NEW, ARM_JOINTS
import xml.etree.ElementTree as ET


def inertials(urdf):
    r = ET.parse(urdf).getroot()
    out = {}
    for l in r.findall("link"):
        i = l.find("inertial")
        if i is None:
            continue
        o = i.find("origin")
        xyz = [float(x) for x in (o.get("xyz") if o is not None else "0 0 0").split()]
        out[l.get("name")] = (float(i.find("mass").get("value")), np.array(xyz))
    return out


legs = {"FL_hip_joint": 0.0, "FL_thigh_joint": 0.5, "FL_calf_joint": -1.0, "RL_hip_joint": 0.0, "RL_thigh_joint": 0.5, "RL_calf_joint": -1.0,
        "FR_hip_joint": 0.0, "FR_thigh_joint": 0.5, "FR_calf_joint": -1.0, "RR_hip_joint": 0.0, "RR_thigh_joint": 0.5, "RR_calf_joint": -1.0}
res = {}
for label, path, q_arm in [("old_asset_q_old", os.path.join(OLD, "a2_piper.urdf"), [0, 0, 0, 0.25, 0.5, 1.57]),
                           ("new_asset_q_old", os.path.join(NEW, "a2_piper.urdf"), [0, 0, 0, 0.25, 0.5, 1.57]),
                           ("new_asset_q_new", os.path.join(NEW, "a2_piper.urdf"), [0, 0, 0, 0, -0.44, 1.57]),
                           ("old_asset_q_new", os.path.join(OLD, "a2_piper.urdf"), [0, 0, 0, 0, -0.44, 1.57])]:
    links, joints, base = parse(path)
    q = dict(legs)
    q.update(dict(zip(ARM_JOINTS, q_arm)))
    Tw = fk(joints, q)
    inr = inertials(path)
    M = 0.0
    c = np.zeros(3)
    arm_M = 0.0
    arm_c = np.zeros(3)
    for n, (m, com) in inr.items():
        pw = Tw[n] @ np.append(com, 1.0)
        M += m
        c += m * pw[:3]
        if n.startswith("arm_") or n in ("vpiper_main", "vpiper_support", "metal_plate_5mm"):
            arm_M += m
            arm_c += m * pw[:3]
    res[label] = dict(total_mass=round(M, 6), com_trunk_frame=(c / M).round(5).tolist(),
                      upper_mass=round(arm_M, 6), upper_com_trunk_frame=(arm_c / arm_M).round(5).tolist(),
                      tcp_trunk_frame=Tw["arm_body6_to_gripper"][:3, 3].round(4).tolist())
    # foot heights for standing height estimate
    res[label]["foot_z_trunk_frame"] = {f: round(float(Tw[f][2, 3]), 4) for f in ("FL_foot", "FR_foot", "RL_foot", "RR_foot")}
print(json.dumps(res, indent=1))
json.dump(res, open("/tmp/v28_team/asset/com_shift.json", "w"), indent=1)
