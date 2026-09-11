#!/usr/bin/env python3
"""Read-only wrist-camera tilt sweep on top of scriptsFORhuman/v28/v28_u3f0_geometry_precheck.py.

Rotates the U3_F0 wrist depth optical frame in place about its image-x axis (down toward the
gripper) by theta and reports, at the v28 reference posture [0,0,0,0,0,1.57]:
  * TCP (F+Z 0.085) and distal fingertips (F+Z 0.1358, y +-0.035 open) in wrist RGB / depth, with row position
  * on-axis entry distance, optical-axis world pitch, ground-hit distance
  * synthetic Stage0/1 approach coverage (arm at the reference posture, not the old default)
Optionally reruns the per-stage dynamic replay for a few tilts.  Nothing is written into the repo.
"""
import importlib.util, json, math, sys, time
from pathlib import Path
import numpy as np

SRC = Path("/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/v28_u3f0_geometry_precheck.py")
spec = importlib.util.spec_from_file_location("pc", SRC)
pc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pc)

OUT = Path("/tmp/v28_tilt_sweep")
OUT.mkdir(exist_ok=True)


def make_streams(theta_deg):
    cfg = json.load(open(pc.CAM_JSON))
    sdk = json.load(open(pc.SDK_JSON))
    streams = {}
    for cam in cfg["cameras"]:
        name = cam["name"]
        T_parent_depth = np.array(cam["streams"]["depth"]["T_parent_optical"], dtype=float)
        if name == "wrist" and theta_deg:
            T_parent_depth = T_parent_depth @ pc.tf(pc.rx(-math.radians(theta_deg)))
        T_depth_rgb = np.array(sdk["cameras"][name]["inter_stream_extrinsics"]["rgb__to__depth"]["T_target_source"], dtype=float)
        T_parent_rgb = T_parent_depth @ T_depth_rgb
        for stream_name, T_parent in (("rgb", T_parent_rgb), ("depth", T_parent_depth)):
            st = sdk["cameras"][name]["streams"][stream_name]
            K = np.array(st["K"], dtype=float)
            min_z = float(cam["depth_min_z_m"]) if stream_name == "depth" else 0.0
            streams[(name, stream_name)] = pc.Stream(name, stream_name, T_parent, K, st["width"], st["height"], min_z)
        streams[(name, "parent")] = cam["parent"]
    return streams


def static_report(theta, streams):
    fk = pc.piper_fk(pc.REFERENCE_ARM_Q)
    rec = {"theta_deg": theta}
    pts_F = {
        "tcp": np.array([0.0, 0.0, 0.085]),
        "finger_mid_0.0976": np.array([0.0, 0.0, 0.09755]),
        "fingertip_open_-y": np.array([0.0, -0.035, 0.1358]),
        "fingertip_open_+y": np.array([0.0, 0.035, 0.1358]),
        "fingertip_closed": np.array([0.0, 0.0, 0.1358]),
    }
    for stream in ("rgb", "depth"):
        st = streams[("wrist", stream)]
        for name, p in pts_F.items():
            ok, u, v, z = st.project(p)
            rec[f"{stream}/{name}"] = {"in": bool(ok), "v_frac": None if v is None else round(float(v) / st.height, 3),
                                        "u_frac": None if u is None else round(float(u) / st.width, 3), "z_m": round(float(z), 3)}
        d_enter = None
        for d in np.arange(0.05, 1.5, 0.005):
            if st.project(np.array([0.0, 0.0, d]))[0]:
                d_enter = float(round(d, 3)); break
        rec[f"{stream}/on_axis_enter_m"] = d_enter
        T_B_cam = fk["F"] @ st.T_parent_opt
        axis = T_B_cam[:3, :3] @ np.array([0.0, 0.0, 1.0])
        pitch = math.degrees(math.asin(max(-1, min(1, axis[2]))))
        rec[f"{stream}/axis_pitch_deg_at_reference"] = round(pitch, 2)
        cam_z_B = float(T_B_cam[2, 3])
        for trunk_z in (0.48, 0.55):
            h = cam_z_B + trunk_z
            rec[f"{stream}/cam_world_height_trunk{trunk_z}"] = round(h, 3)
            rec[f"{stream}/ground_hit_m_trunk{trunk_z}"] = None if pitch >= -0.5 else round(h / math.tan(math.radians(-pitch)), 2)
        # upper FOV edge elevation (handle search reach): pitch + half vertical FOV
        half_v = math.degrees(math.atan(st.height / 2.0 / st.K[1, 1]))
        rec[f"{stream}/half_vfov_deg"] = round(half_v, 2)
        rec[f"{stream}/upper_edge_elev_deg"] = round(pitch + half_v, 2)
        rec[f"{stream}/lower_edge_elev_deg"] = round(pitch - half_v, 2)
    return rec


def main():
    thetas = [0, 15, 25, 30, 35, 40, 45, 50]
    statics = []
    synth = {}
    pc.DEFAULT_ARM_Q = pc.REFERENCE_ARM_Q.copy()  # Stage0/1 synthetic sweep at the v28 reference posture
    for th in thetas:
        streams = make_streams(th)
        statics.append(static_report(th, streams))
        synth[th] = pc.synthetic_approach(streams)
    (OUT / "static.json").write_text(json.dumps(statics, indent=1))
    (OUT / "synthetic.json").write_text(json.dumps(synth, indent=1))
    # compact tables
    print("theta | RGB tcp in (v) | D tcp in (v) | RGB ftip_open in (v) | D ftip_open in (v) | RGB enter m | D enter m | RGB pitch@ref | RGB upper/lower edge elev | ground hit(0.48/0.55)")
    for r in statics:
        print(f"{r['theta_deg']:>5} | {r['rgb/tcp']['in']} ({r['rgb/tcp']['v_frac']}) | {r['depth/tcp']['in']} ({r['depth/tcp']['v_frac']}) | "
              f"{r['rgb/fingertip_open_-y']['in']} ({r['rgb/fingertip_open_-y']['v_frac']}) | {r['depth/fingertip_open_-y']['in']} ({r['depth/fingertip_open_-y']['v_frac']}) | "
              f"{r['rgb/on_axis_enter_m']} | {r['depth/on_axis_enter_m']} | {r['rgb/axis_pitch_deg_at_reference']} | "
              f"{r['rgb/upper_edge_elev_deg']}/{r['rgb/lower_edge_elev_deg']} | {r['rgb/ground_hit_m_trunk0.48']}/{r['rgb/ground_hit_m_trunk0.55']}")
    print()
    keys = ["wrist/rgb/handle", "wrist/depth/handle", "wrist/rgb/frame_handle_side_z1.0", "wrist/rgb/panel_mid_z1.0", "wrist/rgb/doorway_floor_centre", "wrist/depth/doorway_floor_centre", "wrist/rgb/lintel_centre"]
    print("Synthetic Stage0/1 (reference posture, trunk z 0.48): share over 9 poses per distance")
    print("theta | dist | " + " | ".join(k.replace("wrist/", "") for k in keys))
    for th in thetas:
        for d, kv in synth[th].items():
            print(f"{th:>5} | {d} | " + " | ".join(f"{100*kv[k]:.0f}%" for k in keys))
    if len(sys.argv) > 1 and sys.argv[1] == "--dynamic":
        for th in [40, 45]:
            t0 = time.time()
            pc.load_streams = lambda th=th: make_streams(th)
            rep = pc.run(["C_S2", "C_S21"], OUT / f"dyn_theta{th}")
            print(f"dynamic theta={th} done in {time.time()-t0:.0f}s")
            for lane, stages in rep["lanes"].items():
                for st, e in stages.items():
                    v = e["in_frustum_share"]
                    el = e["axis_elev_world_deg"]["wrist"]
                    print(f"  th{th} {lane} {st}: W-RGB handle {100*v['wrist/rgb/handle']:.0f}% W-D handle {100*v['wrist/depth/handle']:.0f}% "
                          f"W-RGB tcp {100*v['wrist/rgb/tcp']:.0f}% W-D tcp {100*v['wrist/depth/tcp']:.0f}% W-RGB panel {100*v['wrist/rgb/panel_mid_z1.0']:.0f}% "
                          f"W-RGB frame(handle) {100*v['wrist/rgb/frame_handle_side_z1.0']:.0f}% W-RGB floor+1m {100*v['wrist/rgb/floor_1m_beyond']:.0f}% "
                          f"axis elev p50 {el['p50']:.0f}")


if __name__ == "__main__":
    main()
