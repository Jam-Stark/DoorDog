"""Summarize real reference traces, including contact locations on authored cells."""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

from gr00t.rl.isaac_utils.playground.env_rand.handle_v29 import build_handle_geometry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    summary = json.loads((args.run / "reference_summary.json").read_text())
    cases = summary["cases"]
    shapes = []
    for case in cases:
        _, cells, axle = build_handle_geometry(case["handle"], 1 if case["side"] == "left" else -1)
        main_count = {"F0": 1, "F1": 1, "F2": 1, "F3": 8, "F4": 16, "F5": 18, "F6": 8}[case["handle"]["family"]]
        named = []
        for name, hull in cells:
            component = name.split("/")[1]
            if component.startswith("segment_"):
                region = "main" if int(component.split("_")[1]) < main_count else "return"
            else:
                region = component
            named.append((region, hull.equations))
        named.append(("axle", axle.equations))
        shapes.append(named)
    stats = [{"label": case["label"], "phase_end": {}, "closest_authored_contact_regions": {},
              "contact_surface_plane_residual_max_m": 0., "bilateral_normal_force_steps_over_0p5N": 0,
              "finger_panel_normal_force_max_n": 0., "arm_panel_normal_force_max_n": 0.}
             for case in cases]
    trace_steps = 0
    with (args.run / "reference_trace.jsonl").open() as stream:
        for line in stream:
            row = json.loads(line)
            trace_steps += 1
            finger_forces = np.linalg.norm(np.asarray(row["finger_handle_normal_force_w_n"])[:, 0], axis=-1)
            finger_panel = np.linalg.norm(np.asarray(row["finger_panel_including_rose_normal_force_w_n"])[:, 0], axis=-1)
            arm_panel = np.linalg.norm(np.asarray(row["arm_panel_including_rose_normal_force_w_n"])[:, 0], axis=-1)
            for i, stat in enumerate(stats):
                stat["phase_end"][row["phase"]] = {
                    "step": row["step"], "position_error_m": row["position_error_m"][i],
                    "orientation_error_rad": row["orientation_error_rad"][i],
                    "finger_normal_force_n": finger_forces[i].tolist(),
                    "finger_q_m": row["finger_q_m"][i],
                }
                stat["bilateral_normal_force_steps_over_0p5N"] += int(np.all(finger_forces[i] > .5))
                stat["finger_panel_normal_force_max_n"] = max(stat["finger_panel_normal_force_max_n"], float(finger_panel[i].max()))
                stat["arm_panel_normal_force_max_n"] = max(stat["arm_panel_normal_force_max_n"], float(arm_panel[i].max()))
            for pair in row["handle_contact_points"]:
                i = pair["env_id"]
                quat = np.array(row["door_handle_quat_wxyz"][i])
                rotation = Rotation.from_quat(quat[[1, 2, 3, 0]]).as_matrix()
                points = (np.asarray(pair["points_w"]) - np.asarray(row["door_handle_pos_w"][i])) @ rotation
                # PhysX gives pair contact points, not the collider prim identity.
                # Match to the authored local convex surfaces and retain residuals.
                distances = np.column_stack([np.abs((points @ planes[:, :3].T + planes[:, 3]).max(axis=1))
                                             for _, planes in shapes[i]])
                closest = distances.argmin(axis=1)
                stat = stats[i]
                for point_index, cell_index in enumerate(closest):
                    region = shapes[i][cell_index][0]
                    stat["closest_authored_contact_regions"][region] = stat["closest_authored_contact_regions"].get(region, 0) + 1
                    stat["contact_surface_plane_residual_max_m"] = max(stat["contact_surface_plane_residual_max_m"], float(distances[point_index, cell_index]))
    responses = json.loads((args.run / "dynamics_response.json").read_text())
    dynamics = {}
    for phase in ("release", "native_upper_limit"):
        rows = [row for row in responses if row["phase"] == phase]
        q = np.array([row["q_rad"] for row in rows])
        velocity = np.array([row["qdot_rad_s"] for row in rows])
        limits = np.array(rows[0]["native_limits_rad"])
        dynamics[phase] = {"steps": len(rows), "first_sample_q_rad": q[0].tolist(),
                           "last_q_rad": q[-1].tolist(), "min_q_rad": q.min(axis=0).tolist(),
                           "max_q_rad": q.max(axis=0).tolist(), "last_qdot_rad_s": velocity[-1].tolist(),
                           "native_limits_rad": limits.tolist(),
                           "max_q_minus_upper_rad": (q.max(axis=0) - limits[:, 1]).tolist()}
    args.output.write_text(json.dumps({"run": str(args.run.resolve()), "trace_steps": trace_steps,
                                      "scope": "Measured reference fixture behavior, not policy success",
                                      "contact_localization": "Closest authored convex surface by plane residual; native capsule is represented by the generator's recorded discretization. Raw moving-body contact points remain authoritative.",
                                      "cases": stats, "dynamics": dynamics}, indent=2) + "\n")
    print(f"Summarized {trace_steps} reference steps for {len(stats)} cases")


if __name__ == "__main__":
    main()
