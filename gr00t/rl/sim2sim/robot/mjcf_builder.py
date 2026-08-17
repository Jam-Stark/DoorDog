"""Build and compile the floating-base A2+Piper MuJoCo realization."""

from __future__ import annotations

import json
import math
import os
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Mapping

import mujoco
import yaml

from .contract import resolved_a2_piper_contract


WORLD_TO_OPENGL_WXYZ = (0.5, 0.5, -0.5, -0.5)


def _values(values: tuple[float, ...] | list[float]) -> str:
    return " ".join(f"{float(value):.12g}" for value in values)


def _quat_multiply(left: list[float], right: tuple[float, ...]) -> list[float]:
    lw, lx, ly, lz = left
    rw, rx, ry, rz = right
    result = [
        lw * rw - lx * rx - ly * ry - lz * rz,
        lw * rx + lx * rw + ly * rz - lz * ry,
        lw * ry - lx * rz + ly * rw + lz * rx,
        lw * rz + lx * ry - ly * rx + lz * rw,
    ]
    norm = math.sqrt(sum(value * value for value in result))
    return [value / norm for value in result]


def _camera_optics(config: Mapping[str, Any], name: str) -> tuple[float, float, list[float]]:
    cameras = config["simulator"]["config"]["cameras"]
    if name == "left":
        source = cameras
    elif name == "right":
        source = cameras["policy_multiview"]["right"]
    else:
        source = cameras["policy_multiview"]["context"]
    focal = float(source["camera_focal_length"] if name == "left" else source["focal_length"])
    vertical = float(
        source["camera_vertical_aperture"] if name == "left" else source["vertical_aperture"]
    )
    clipping = list(source["camera_clipping_range"] if name == "left" else source["clipping_range"])
    fovy_deg = math.degrees(2.0 * math.atan(vertical / (2.0 * focal)))
    return focal, fovy_deg, clipping


def _id_map(model: mujoco.MjModel, object_type: mujoco.mjtObj, count: int) -> dict[str, int]:
    return {
        mujoco.mj_id2name(model, object_type, index): index
        for index in range(count)
        if mujoco.mj_id2name(model, object_type, index) is not None
    }


class A2PiperMjcfBuilder:
    def __init__(self, urdf_path: Path, bundle_dir: Path):
        self.urdf_path = urdf_path.resolve(strict=True)
        self.bundle_dir = bundle_dir.resolve(strict=True)
        self.bundle = json.loads((self.bundle_dir / "manifest.json").read_text(encoding="utf-8"))
        self.config = yaml.safe_load((self.bundle_dir / "config_snapshot.yaml").read_text(encoding="utf-8"))
        self.contract = resolved_a2_piper_contract()

    def _xml_tree(self, output_xml: Path) -> tuple[ET.Element, list[dict[str, Any]]]:
        source_spec = mujoco.MjSpec.from_file(str(self.urdf_path))
        root = ET.fromstring(source_spec.to_xml())
        root.set("model", "a2_piper_shadow")
        compiler = root.find("compiler")
        assert compiler is not None
        compiler.set("angle", "radian")
        compiler.set("meshdir", os.path.relpath(self.urdf_path.parent, output_xml.parent))
        ET.SubElement(root, "option", {"timestep": "0.005", "gravity": "0 0 -9.81"})

        world = root.find("worldbody")
        assert world is not None
        source_children = list(world)
        for child in source_children:
            world.remove(child)

        ET.SubElement(world, "light", {"name": "key_light", "pos": "0 0 3", "dir": "0 0 -1"})
        ET.SubElement(
            world,
            "geom",
            {"name": "floor", "type": "plane", "size": "4 4 0.1", "rgba": "0.28 0.29 0.31 1"},
        )
        ET.SubElement(
            world,
            "camera",
            {"name": "axis_overview", "pos": "1.7 -1.7 1.25", "xyaxes": "0.707 0.707 0 -0.35 0.35 0.87", "fovy": "55"},
        )
        trunk = ET.SubElement(world, "body", {"name": "trunk"})
        ET.SubElement(trunk, "freejoint", {"name": "floating_base"})
        ET.SubElement(
            trunk,
            "inertial",
            {
                "pos": "0.0069826 -0.0007129 0.0128895",
                "mass": "19.651",
                "fullinertia": "0.1417753 0.4077246 0.472248 0.0004005 -0.0069965 -0.0003619",
            },
        )
        arm_base = ET.Element("body", {"name": "arm_body0", "pos": "0.145 0 0.154"})
        ET.SubElement(
            arm_base,
            "inertial",
            {
                "pos": "-0.004736411642 0.00002568291346 0.04145151804",
                "mass": "1.02",
                "fullinertia": "0.00267433 0.00282612 0.00089624 -0.00000073 -0.00017389 0.0000004",
            },
        )
        for child in source_children:
            if child.tag == "geom" and child.get("mesh") == "base_link":
                child.set("pos", "0 0 0")
                arm_base.append(child)
            elif child.tag == "body" and child.get("name") == "arm_body1":
                child.set("pos", "0 0 0.123")
                arm_base.append(child)
            else:
                trunk.append(child)
        trunk.append(arm_base)

        for joint_name, torque_limit in zip(
            self.contract.sim_joint_names, self.contract.torque_limit, strict=True
        ):
            joint = root.find(f".//joint[@name='{joint_name}']")
            if joint is None:
                raise KeyError(f"converted URDF lacks joint {joint_name}")
            joint.set("actuatorfrcrange", _values([-torque_limit, torque_limit]))

        camera_receipts = []
        for stream in self.bundle["camera_rig"]["streams"]:
            name = stream["name"]
            source_quat = [float(value) for value in stream["rotation_wxyz"]]
            mujoco_quat = _quat_multiply(source_quat, WORLD_TO_OPENGL_WXYZ)
            _, fovy_deg, clipping = _camera_optics(self.config, name)
            camera_frame = ET.SubElement(
                trunk,
                "body",
                {
                    "name": f"{name}_camera_frame",
                    "pos": _values(stream["position_m"]),
                    "quat": _values(mujoco_quat),
                },
            )
            ET.SubElement(
                camera_frame,
                "camera",
                {"name": f"{name}_policy", "fovy": f"{fovy_deg:.12g}", "resolution": _values(stream["resolution_hw"][::-1])},
            )
            for axis, endpoint, color in (
                ("x", "0.08 0 0", "1 0 0 1"),
                ("y", "0 0.08 0", "0 1 0 1"),
                ("z", "0 0 0.08", "0 0 1 1"),
            ):
                ET.SubElement(
                    camera_frame,
                    "site",
                    {
                        "name": f"{name}_camera_axis_{axis}",
                        "type": "capsule",
                        "fromto": f"0 0 0 {endpoint}",
                        "size": "0.004",
                        "rgba": color,
                    },
                )
            camera_receipts.append(
                {
                    "name": name,
                    "parent": "trunk",
                    "position_m": stream["position_m"],
                    "source_convention": "world:+X_forward,+Z_up",
                    "source_rotation_wxyz": source_quat,
                    "mujoco_convention": "opengl:-Z_forward,+Y_up",
                    "mujoco_rotation_wxyz": mujoco_quat,
                    "fixed_right_multiplier_wxyz": list(WORLD_TO_OPENGL_WXYZ),
                    "fovy_deg": fovy_deg,
                    "clipping_range_m": clipping,
                    "resolution_hw": stream["resolution_hw"],
                }
            )

        marker = ET.SubElement(world, "body", {"name": "world_axis_marker", "pos": "0.9 0 0.5"})
        for axis, endpoint, color in (
            ("x", "0.25 0 0", "1 0 0 1"),
            ("y", "0 0.25 0", "0 1 0 1"),
            ("z", "0 0 0.25", "0 0 1 1"),
        ):
            ET.SubElement(
                marker,
                "site",
                {"name": f"world_axis_{axis}", "type": "capsule", "fromto": f"0 0 0 {endpoint}", "size": "0.012", "rgba": color},
            )

        actuator = ET.SubElement(root, "actuator")
        for joint_name, torque_limit in zip(
            self.contract.sim_joint_names, self.contract.torque_limit, strict=True
        ):
            ET.SubElement(
                actuator,
                "motor",
                {
                    "name": f"{joint_name}_motor",
                    "joint": joint_name,
                    "gear": "1",
                    "ctrllimited": "true",
                    "ctrlrange": _values([-torque_limit, torque_limit]),
                },
            )

        keyframe = ET.SubElement(root, "keyframe")
        home_qpos = [0.0, 0.0, 0.62, 1.0, 0.0, 0.0, 0.0, *self.contract.default_dof_pos]
        ET.SubElement(keyframe, "key", {"name": "home", "qpos": _values(home_qpos)})
        return root, camera_receipts

    def write(self, output_xml: Path, output_contract: Path, output_report: Path) -> None:
        output_xml = output_xml.resolve()
        output_xml.parent.mkdir(parents=True, exist_ok=True)
        output_contract.parent.mkdir(parents=True, exist_ok=True)
        output_report.parent.mkdir(parents=True, exist_ok=True)
        root, camera_receipts = self._xml_tree(output_xml)
        ET.indent(root, space="  ")
        output_xml.write_text(ET.tostring(root, encoding="unicode") + "\n", encoding="utf-8")
        model = mujoco.MjModel.from_xml_path(str(output_xml))
        joint_ids = _id_map(model, mujoco.mjtObj.mjOBJ_JOINT, model.njnt)
        actuator_ids = _id_map(model, mujoco.mjtObj.mjOBJ_ACTUATOR, model.nu)
        camera_ids = _id_map(model, mujoco.mjtObj.mjOBJ_CAMERA, model.ncam)
        expected_actuators = [f"{name}_motor" for name in self.contract.sim_joint_names]
        if list(joint_ids)[1:] != list(self.contract.sim_joint_names):
            raise ValueError(f"compiled joint order mismatch: {list(joint_ids)}")
        if list(actuator_ids) != expected_actuators:
            raise ValueError(f"compiled actuator order mismatch: {list(actuator_ids)}")
        if (model.nq, model.nv, model.nu) != (27, 26, 20):
            raise ValueError(f"compiled model dimensions are {(model.nq, model.nv, model.nu)}")

        contract = self.contract.as_dict()
        contract.update(
            {
                "robot_xml": str(output_xml),
                "source_urdf": str(self.urdf_path),
                "floating_base_joint": "floating_base",
                "qpos_layout": {"floating_base": [0, 7], "actuated": [7, 27]},
                "qvel_layout": {"floating_base": [0, 6], "actuated": [6, 26]},
                "actuator_names": expected_actuators,
                "external_pd": {
                    "formula": "clip(kp*(q_target-q)-kd*qvel,-torque_limit,+torque_limit)",
                    "clip_cadence": "EVERY_PHYSICS_STEP",
                    "physics_hz": 200,
                    "gripper_evaluated_face": {"stiffness": 1300.0, "damping": 32.0, "torque_limit": 45.0},
                },
                "camera_receipts": camera_receipts,
                "policy_bundle_identity": {
                    "source_commit": self.bundle["native_loader"]["source_commit"],
                    "path": str(self.bundle_dir),
                },
            }
        )
        report = {
            "schema": "doordog.sim2sim.a2_piper_mjcf_build_report.v1",
            "evidence_level": "E1",
            "result_classification": "VALID_WITH_WARNINGS",
            "mujoco_version": mujoco.__version__,
            "compiled": {
                "nq": model.nq,
                "nv": model.nv,
                "nu": model.nu,
                "nbody": model.nbody,
                "njnt": model.njnt,
                "ngeom": model.ngeom,
                "ncam": model.ncam,
                "total_body_mass_kg": float(model.body_mass.sum()),
            },
            "joint_ids": joint_ids,
            "actuator_ids": actuator_ids,
            "camera_ids": camera_ids,
            "home_keyframe_qpos_dim": int(model.nq),
            "warnings": [
                "Camera convention is transformed from the IsaacLab-defined world basis to OpenGL algebraically; runtime image parity still requires the axis-marker probe.",
                "The checkpoint-adjacent config gripper 80/3/10 face is not used for E1; owner audit R4 fixes the evaluated controller face at 1300/32/45.",
            ],
        }
        output_contract.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        output_report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
