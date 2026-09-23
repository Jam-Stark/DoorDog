"""Plan legal reference-bench arm seeds from the actual v29 URDF and readback."""
import argparse
import json
from pathlib import Path

import numpy as np
import pinocchio as pin
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-readback", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--urdf", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    runtime = json.loads(args.runtime_readback.read_text())
    cases = json.loads(args.manifest.read_text())["cases"]
    model = pin.buildModelFromUrdf(str(args.urdf))
    data = model.createData()
    frame_id = model.getFrameId("arm_body6_to_gripper")
    arm_names = [f"arm_j{i}" for i in range(1, 7)]
    arm_ids = np.array([model.joints[model.getJointId(name)].idx_q for name in arm_names])
    q = pin.neutral(model)
    for name, value in zip(runtime["robot"]["joint_names"], runtime["robot"]["joint_pos"]["values"][0]):
        q[model.joints[model.getJointId(name)].idx_q] = value
    initial = q[arm_ids].copy()

    def fk(arm):
        q[arm_ids] = arm
        pin.forwardKinematics(model, data, q)
        pin.updateFramePlacements(model, data)
        frame = data.oMf[frame_id]
        return frame.translation + frame.rotation @ np.array([0., 0., .085]), frame.rotation.copy()

    # Bind the offline chain to a real imported body/TCP pose, not merely a name.
    roots = np.array(runtime["robot"]["root_state_w"]["values"])
    tcp_positions = np.array(runtime["gripper_frames"]["source_pos_w"]["values"])
    tcp_quats = np.array(runtime["gripper_frames"]["source_quat_w"]["values"])
    initial_fk, initial_rotation = fk(initial)
    frame_errors = []
    for root, position, quat in zip(roots, tcp_positions, tcp_quats):
        root_rotation = Rotation.from_quat(root[[4, 5, 6, 3]]).as_matrix()
        actual_position = root_rotation.T @ (position - root[:3])
        actual_rotation = root_rotation.T @ Rotation.from_quat(quat[[1, 2, 3, 0]]).as_matrix()
        frame_errors.append({"position_m": float(np.linalg.norm(initial_fk - actual_position)),
                             "orientation_rad": float(np.linalg.norm(pin.log3(initial_rotation.T @ actual_rotation)))})
    plans = []
    for index, case in enumerate(cases):
        metadata = runtime["door_metadata"][index]["custom_data"]
        handle = metadata["v29Handle"]
        if handle["family"] != case["handle"]["family"] or bool(handle["return_present"]) != case["handle"]["return_present"]:
            raise ValueError(f"Readback and explicit reference case disagree at {index}")
        quat = np.array(handle["grasp_quaternion_wxyz"])
        target_rotation = Rotation.from_quat(quat[[1, 2, 3, 0]]).as_matrix()
        target_position = np.array([.50, 0., case["handle_height_m"] + handle["grasp_position_local_m"][2] - .50])
        seed = initial.copy()
        # Explicit legal branch seed for the mirrored proper target frame.
        seed[-1] = -1.57 if case["side"] == "left" else 1.57

        def residual(arm):
            position, rotation = fk(arm)
            return np.r_[position - target_position, pin.log3(rotation.T @ target_rotation)]

        path = []
        for distance in np.linspace(.50, .60, 11):
            target_position[0] = distance
            result = least_squares(residual, seed,
                                   bounds=(model.lowerPositionLimit[arm_ids], model.upperPositionLimit[arm_ids]),
                                   xtol=1.e-10, ftol=1.e-10, gtol=1.e-10, max_nfev=300)
            error = residual(result.x)
            if not result.success or np.linalg.norm(error[:3]) > 1.e-5 or np.linalg.norm(error[3:]) > 1.e-5:
                raise RuntimeError(f"Reference path not established: {case['label']} x={distance}, residual={error}")
            path.append({"target_x_m": float(distance), "q_rad": result.x.tolist(),
                         "position_error_m": float(np.linalg.norm(error[:3])),
                         "orientation_error_rad": float(np.linalg.norm(error[3:]))})
            seed = result.x
        plans.append({"label": case["label"], "pregrasp_arm_q": path[0]["q_rad"], "path": path})
    args.output.write_text(json.dumps({
        "claim": "URDF kinematic plan only; real drive/contact still required",
        "runtime_readback": str(args.runtime_readback.resolve()), "manifest": str(args.manifest.resolve()),
        "urdf": str(args.urdf.resolve()), "pinocchio_version": pin.__version__,
        "arm_joint_names": arm_names, "root_standoff_m": .60, "root_height_m": .50,
        "native_urdf_joint_limits": np.stack((model.lowerPositionLimit[arm_ids], model.upperPositionLimit[arm_ids]), axis=-1).tolist(),
        "initial_fk_vs_runtime": frame_errors, "cases": plans,
    }, indent=2) + "\n")
    print(f"Planned {len(plans)} legal pregrasp seeds and 11-point approach paths; no GPU/contact claim")


if __name__ == "__main__":
    main()
