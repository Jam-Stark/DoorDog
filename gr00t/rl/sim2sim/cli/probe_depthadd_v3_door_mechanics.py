#!/usr/bin/env python3
"""Physics-only probe for the three realized DepthADD latch topologies."""

from __future__ import annotations

import argparse
import json
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import mujoco
import numpy as np


_DEFAULT_ROOT = Path("logs_eval/sim2sim/depthadd_v3_20260825/source_geometry_empirical_appearance_base000_r1")
_DEFAULT_CASE_DIR = _DEFAULT_ROOT / "episodes" / "seed41001_base000__fixed"


def _id(model: mujoco.MjModel, object_type: mujoco.mjtObj, name: str) -> int:
    value = mujoco.mj_name2id(model, object_type, name)
    if value < 0:
        raise ValueError(f"required {object_type.name} {name!r} is absent from the scene")
    return int(value)


def _maybe_id(model: mujoco.MjModel, object_type: mujoco.mjtObj, name: str) -> int:
    return int(mujoco.mj_name2id(model, object_type, name))


def _load_exact_initial_state(receipt_path: Path) -> dict[str, Any]:
    receipt = json.loads(receipt_path.resolve(strict=True).read_text(encoding="utf-8"))
    state = receipt.get("initial_state_realization")
    if not isinstance(state, Mapping):
        raise TypeError("episode receipt lacks initial_state_realization")
    if state.get("schema") != "a2_depthadd_v3_mujoco_initial_state_v1":
        raise ValueError("episode receipt initial state is not the DepthADD v3 reset realization")
    values = {
        "root_qpos": np.asarray(state["root_qpos_mujoco_wxyz"], dtype=np.float64),
        "root_qvel": np.asarray(state["root_qvel"], dtype=np.float64),
        "joint_qpos": np.asarray(state["joint_qpos"], dtype=np.float64),
        "joint_qvel": np.asarray(state["joint_qvel"], dtype=np.float64),
    }
    expected = {"root_qpos": (7,), "root_qvel": (6,), "joint_qpos": (20,), "joint_qvel": (20,)}
    for name, shape in expected.items():
        if values[name].shape != shape or not np.isfinite(values[name]).all():
            raise ValueError(f"receipt {name} reset span must be finite with shape {shape}")
    values["receipt"] = receipt
    return values


@dataclass(frozen=True)
class _LatchTopology:
    mode: str
    gate_eq_id: int
    mimic_eq_id: int
    latch_slide_qpos: int | None
    latch_slide_dof: int | None
    latch_collision_geom_id: int | None
    broad_frame_geom_ids: tuple[int, ...]

    def gate_active(self, data: mujoco.MjData) -> bool | None:
        return None if self.gate_eq_id < 0 else bool(data.eq_active[self.gate_eq_id])

    def mimic_active(self, data: mujoco.MjData) -> bool | None:
        return None if self.mimic_eq_id < 0 else bool(data.eq_active[self.mimic_eq_id])

    def update(self, data: mujoco.MjData, handle_qpos: int, release_handle_rad: float) -> bool:
        if self.mode == "constraint_gate" and self.gate_active(data) and data.qpos[handle_qpos] >= release_handle_rad:
            data.eq_active[self.gate_eq_id] = 0
            return True
        return False


def _resolve_topology(model: mujoco.MjModel, requested_mode: str) -> _LatchTopology:
    gate_eq = _maybe_id(model, mujoco.mjtObj.mjOBJ_EQUALITY, "door_constraint_gate")
    mimic_eq = _maybe_id(model, mujoco.mjtObj.mjOBJ_EQUALITY, "handle_latch_mimic")
    slide_joint = _maybe_id(model, mujoco.mjtObj.mjOBJ_JOINT, "latch_slide")
    latch_geom = _maybe_id(model, mujoco.mjtObj.mjOBJ_GEOM, "latch_collision")
    if (slide_joint >= 0) != (mimic_eq >= 0):
        raise ValueError("physical latch topology requires both latch_slide and handle_latch_mimic")
    if gate_eq >= 0 and (slide_joint >= 0 or mimic_eq >= 0):
        raise ValueError("scene contains mutually exclusive gate and physical latch topologies")
    inferred = "constraint_gate" if gate_eq >= 0 else "physical_collision" if slide_joint >= 0 else "no_latch"
    mode = inferred if requested_mode == "auto" else requested_mode
    if mode != inferred:
        raise ValueError(f"requested latch mode {mode!r} disagrees with scene topology {inferred!r}")
    if mode == "physical_collision" and latch_geom < 0:
        raise ValueError("physical_collision scene lacks latch_collision geom")
    names = {
        str(mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, index))
        for index in range(model.ngeom)
        if mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, index) is not None
    }
    broad_ids = tuple(
        _id(model, mujoco.mjtObj.mjOBJ_GEOM, name)
        for name in sorted(names)
        if name.startswith("door_source_frame_") or name.startswith("door_frame_")
    )
    return _LatchTopology(
        mode=mode, gate_eq_id=gate_eq, mimic_eq_id=mimic_eq,
        latch_slide_qpos=None if slide_joint < 0 else int(model.jnt_qposadr[slide_joint]),
        latch_slide_dof=None if slide_joint < 0 else int(model.jnt_dofadr[slide_joint]),
        latch_collision_geom_id=None if latch_geom < 0 else latch_geom,
        broad_frame_geom_ids=broad_ids,
    )


def _reset_exact_state(
    model: mujoco.MjModel, data: mujoco.MjData, *, home_key: int, initial: Mapping[str, np.ndarray],
    topology: _LatchTopology, door_qpos: int, handle_qpos: int,
) -> None:
    mujoco.mj_resetDataKeyframe(model, data, home_key)
    data.qpos[0:7] = initial["root_qpos"]
    data.qvel[0:6] = initial["root_qvel"]
    data.qpos[7:27] = initial["joint_qpos"]
    data.qvel[6:26] = initial["joint_qvel"]
    mujoco.mj_forward(model, data)
    if abs(float(data.qpos[door_qpos])) > 1e-12 or abs(float(data.qpos[handle_qpos])) > 1e-12:
        raise RuntimeError("scene_home does not restore the closed door and handle")
    if topology.gate_eq_id >= 0 and not bool(data.eq_active[topology.gate_eq_id]):
        raise RuntimeError("constraint gate is inactive immediately after exact reset")
    if topology.latch_slide_qpos is not None and abs(float(data.qpos[topology.latch_slide_qpos])) > 1e-12:
        raise RuntimeError("scene_home does not restore the physical latch slide")


def _contacts(model: mujoco.MjModel, data: mujoco.MjData) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index in range(data.ncon):
        contact = data.contact[index]
        wrench = np.zeros(6, dtype=np.float64)
        mujoco.mj_contactForce(model, data, index, wrench)
        ids = (int(contact.geom1), int(contact.geom2))
        names = [mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, value) for value in ids]
        rows.append({
            "geom1_id": ids[0], "geom2_id": ids[1], "geom1": names[0] or f"geom_{ids[0]}",
            "geom2": names[1] or f"geom_{ids[1]}", "normal_force_n": float(wrench[0]),
            "force_torque_contact_frame": wrench.tolist(),
        })
    return rows


def _step_row(
    model: mujoco.MjModel, data: mujoco.MjData, *, topology: _LatchTopology, lane: str, step: int,
    released_now: bool, door_qpos: int, door_dof: int, handle_qpos: int, handle_dof: int,
    door_actuator: int, handle_actuator: int,
) -> dict[str, Any]:
    contacts = _contacts(model, data)
    latch_frame = [
        item for item in contacts if "latch_collision" in (item["geom1"], item["geom2"])
        and any(item[f"geom{side}_id"] in topology.broad_frame_geom_ids for side in (1, 2))
    ]
    return {
        "lane": lane, "latch_mode": topology.mode, "physics_step": step, "time_s": float(data.time),
        "door_hinge_qpos_rad": float(data.qpos[door_qpos]), "door_hinge_qvel_rad_s": float(data.qvel[door_dof]),
        "handle_hinge_qpos_rad": float(data.qpos[handle_qpos]), "handle_hinge_qvel_rad_s": float(data.qvel[handle_dof]),
        "constraint_gate_active": topology.gate_active(data), "handle_latch_mimic_active": topology.mimic_active(data),
        "latch_slide_qpos_m": None if topology.latch_slide_qpos is None else float(data.qpos[topology.latch_slide_qpos]),
        "latch_slide_qvel_m_s": None if topology.latch_slide_dof is None else float(data.qvel[topology.latch_slide_dof]),
        "gate_released_this_step": released_now, "door_qfrc_applied_nm": float(data.qfrc_applied[door_dof]),
        "handle_qfrc_applied_nm": float(data.qfrc_applied[handle_dof]), "door_actuator_force_nm": float(data.actuator_force[door_actuator]),
        "handle_actuator_force_nm": float(data.actuator_force[handle_actuator]), "door_constraint_reaction_nm": float(data.qfrc_constraint[door_dof]),
        "handle_constraint_reaction_nm": float(data.qfrc_constraint[handle_dof]), "contact_count": int(data.ncon),
        "contacts": contacts, "latch_collision_broad_frame_contact": bool(latch_frame),
        "latch_collision_broad_frame_contact_count": len(latch_frame),
    }


def _write_trace(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True) + "\n")


def _finite(data: mujoco.MjData) -> bool:
    return bool(np.isfinite(data.qpos).all() and np.isfinite(data.qvel).all())


def _summary(rows: list[dict[str, Any]], *, initial_hinge_rad: float, release_step: int | None) -> dict[str, Any]:
    if not rows:
        raise RuntimeError("mechanics lane emitted no physics rows")
    hinge = np.asarray([row["door_hinge_qpos_rad"] for row in rows], dtype=np.float64)
    gate_values = [row["constraint_gate_active"] for row in rows]
    slide = [row["latch_slide_qpos_m"] for row in rows if row["latch_slide_qpos_m"] is not None]
    return {
        "physics_steps": len(rows), "duration_s": float(rows[-1]["time_s"] - rows[0]["time_s"] + 0.005),
        "initial_hinge_rad": initial_hinge_rad, "final_hinge_rad": float(hinge[-1]),
        "max_abs_hinge_displacement_rad": float(np.max(np.abs(hinge - initial_hinge_rad))),
        "max_hinge_displacement_rad": float(np.max(hinge - initial_hinge_rad)), "final_handle_rad": float(rows[-1]["handle_hinge_qpos_rad"]),
        "final_latch_slide_m": None if not slide else float(slide[-1]),
        "gate_active_all_steps": None if not gate_values or gate_values[0] is None else bool(all(gate_values)),
        "gate_active_final": gate_values[-1], "release_step": release_step,
        "peak_abs_door_constraint_reaction_nm": float(max(abs(row["door_constraint_reaction_nm"]) for row in rows)),
        "door_contact_steps": int(sum(any(item["geom1"].startswith("door_") or item["geom2"].startswith("door_") for item in row["contacts"]) for row in rows)),
        "latch_collision_broad_frame_contact_steps": int(sum(row["latch_collision_broad_frame_contact"] for row in rows)),
        "all_state_finite": bool(np.isfinite(hinge).all() and all(math.isfinite(row["handle_hinge_qpos_rad"]) for row in rows)),
    }


def _run_torque_lane(
    *, name: str, model: mujoco.MjModel, data: mujoco.MjData, reset: Callable[[], None], topology: _LatchTopology,
    door_qpos: int, door_dof: int, handle_qpos: int, handle_dof: int, door_actuator: int, handle_actuator: int,
    torque_nm: float, steps: int, release_handle_first: bool, hold_handle: bool, handle_release_steps: int, release_handle_rad: float,
) -> tuple[list[dict[str, Any]], int | None]:
    reset(); rows: list[dict[str, Any]] = []; release_step: int | None = None; data.ctrl[:] = 0.0
    if release_handle_first:
        data.ctrl[handle_actuator] = float(model.actuator_ctrlrange[handle_actuator, 1])
        for step in range(handle_release_steps):
            released_now = topology.update(data, handle_qpos, release_handle_rad)
            if released_now and release_step is None: release_step = step
            data.qfrc_applied[:] = 0.0; mujoco.mj_step(model, data)
            rows.append(_step_row(model, data, topology=topology, lane=name, step=step, released_now=released_now, door_qpos=door_qpos, door_dof=door_dof, handle_qpos=handle_qpos, handle_dof=handle_dof, door_actuator=door_actuator, handle_actuator=handle_actuator))
            if topology.mode == "constraint_gate" and release_step is not None: break
        if topology.mode == "constraint_gate" and release_step is None:
            raise RuntimeError(f"{name}: handle actuator did not release the constraint gate")
    start = len(rows); data.ctrl[handle_actuator] = float(model.actuator_ctrlrange[handle_actuator, 1]) if hold_handle else 0.0
    for local_step in range(steps):
        released_now = topology.update(data, handle_qpos, release_handle_rad)
        if released_now and release_step is None: release_step = start + local_step
        data.qfrc_applied[:] = 0.0; data.qfrc_applied[door_dof] = torque_nm; mujoco.mj_step(model, data)
        rows.append(_step_row(model, data, topology=topology, lane=name, step=start + local_step, released_now=released_now, door_qpos=door_qpos, door_dof=door_dof, handle_qpos=handle_qpos, handle_dof=handle_dof, door_actuator=door_actuator, handle_actuator=handle_actuator))
    if not _finite(data): raise FloatingPointError(f"{name}: MuJoCo produced a non-finite state")
    return rows, release_step


def _run_handle_only_lane(
    *, model: mujoco.MjModel, data: mujoco.MjData, reset: Callable[[], None], topology: _LatchTopology,
    door_qpos: int, door_dof: int, handle_qpos: int, handle_dof: int, door_actuator: int, handle_actuator: int,
    release_max_steps: int, settle_steps: int, release_handle_rad: float,
) -> tuple[list[dict[str, Any]], int | None]:
    reset(); rows: list[dict[str, Any]] = []; release_step: int | None = None; data.ctrl[:] = 0.0
    data.ctrl[handle_actuator] = float(model.actuator_ctrlrange[handle_actuator, 1])
    for step in range(release_max_steps):
        released_now = topology.update(data, handle_qpos, release_handle_rad)
        if released_now and release_step is None: release_step = step
        data.qfrc_applied[:] = 0.0; mujoco.mj_step(model, data)
        rows.append(_step_row(model, data, topology=topology, lane="handle_only", step=step, released_now=released_now, door_qpos=door_qpos, door_dof=door_dof, handle_qpos=handle_qpos, handle_dof=handle_dof, door_actuator=door_actuator, handle_actuator=handle_actuator))
        if topology.mode == "constraint_gate" and release_step is not None: break
    if topology.mode == "constraint_gate" and release_step is None:
        raise RuntimeError("handle_only: handle actuator did not release the constraint gate")
    for _ in range(settle_steps):
        data.qfrc_applied[:] = 0.0; mujoco.mj_step(model, data)
        rows.append(_step_row(model, data, topology=topology, lane="handle_only", step=len(rows), released_now=False, door_qpos=door_qpos, door_dof=door_dof, handle_qpos=handle_qpos, handle_dof=handle_dof, door_actuator=door_actuator, handle_actuator=handle_actuator))
    if not _finite(data): raise FloatingPointError("handle_only: MuJoCo produced a non-finite state")
    return rows, release_step


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", type=Path, default=_DEFAULT_CASE_DIR / "model" / "scene.xml")
    parser.add_argument("--episode-receipt", type=Path, default=_DEFAULT_CASE_DIR / "receipt.json")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--mode", choices=("auto", "constraint_gate", "physical_collision", "no_latch"), default="auto")
    parser.add_argument("--release-handle-rad", type=float, default=math.pi / 6.0)
    parser.add_argument("--external-door-torque-nm", type=float, default=10.0)
    parser.add_argument("--force-steps", type=int, default=200)
    parser.add_argument("--handle-release-max-steps", type=int, default=400)
    parser.add_argument("--release-only-settle-steps", type=int, default=200)
    parser.add_argument("--locked-max-hinge-rad", type=float, default=1.0e-3)
    parser.add_argument("--unlocked-min-hinge-rad", type=float, default=5.0e-2)
    args = parser.parse_args()
    if args.force_steps <= 0 or args.handle_release_max_steps <= 0 or args.release_only_settle_steps < 0:
        raise ValueError("physics-step arguments must be positive (settle may be zero)")
    if args.external_door_torque_nm <= 0 or not 0 < args.release_handle_rad <= math.pi / 4:
        raise ValueError("torque must be positive and release_handle_rad must be in (0, pi/4]")
    scene = args.scene.resolve(strict=True); receipt_path = args.episode_receipt.resolve(strict=True); output = args.output_dir.resolve(); output.mkdir(parents=True, exist_ok=False)
    initial = _load_exact_initial_state(receipt_path); model = mujoco.MjModel.from_xml_path(str(scene)); data = mujoco.MjData(model); topology = _resolve_topology(model, args.mode)
    expected = (30, 29) if topology.mode == "physical_collision" else (29, 28)
    if (model.nq, model.nv) != expected: raise ValueError(f"{topology.mode} dimensions {(model.nq, model.nv)} != {expected}")
    home_key = _id(model, mujoco.mjtObj.mjOBJ_KEY, "scene_home"); door_joint = _id(model, mujoco.mjtObj.mjOBJ_JOINT, "door_hinge"); handle_joint = _id(model, mujoco.mjtObj.mjOBJ_JOINT, "handle_hinge")
    door_actuator = _id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, "door_hinge_capped_position"); handle_actuator = _id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, "handle_capped_position")
    door_qpos, door_dof = int(model.jnt_qposadr[door_joint]), int(model.jnt_dofadr[door_joint]); handle_qpos, handle_dof = int(model.jnt_qposadr[handle_joint]), int(model.jnt_dofadr[handle_joint])
    def reset() -> None:
        _reset_exact_state(model, data, home_key=home_key, initial=initial, topology=topology, door_qpos=door_qpos, handle_qpos=handle_qpos)
    reset(); initial_hinge = float(data.qpos[door_qpos]); lanes: dict[str, tuple[list[dict[str, Any]], int | None]] = {}
    lane_args = dict(model=model, data=data, reset=reset, topology=topology, door_qpos=door_qpos, door_dof=door_dof, handle_qpos=handle_qpos, handle_dof=handle_dof, door_actuator=door_actuator, handle_actuator=handle_actuator, torque_nm=args.external_door_torque_nm, release_handle_rad=args.release_handle_rad)
    lanes["locked_unpressed_external_torque"] = _run_torque_lane(name="locked_unpressed_external_torque", release_handle_first=False, hold_handle=False, handle_release_steps=0, steps=args.force_steps, **lane_args)
    lanes["handle_only"] = _run_handle_only_lane(release_max_steps=args.handle_release_max_steps, settle_steps=args.release_only_settle_steps, **{key: lane_args[key] for key in ("model", "data", "reset", "topology", "door_qpos", "door_dof", "handle_qpos", "handle_dof", "door_actuator", "handle_actuator", "release_handle_rad")})
    lanes["pressed_external_torque"] = _run_torque_lane(name="pressed_external_torque", release_handle_first=True, hold_handle=True, handle_release_steps=args.handle_release_max_steps, steps=args.force_steps, **lane_args)
    traces: dict[str, str] = {}; summaries: dict[str, dict[str, Any]] = {}
    for name, (rows, release_step) in lanes.items():
        path = output / f"{name}_trace.jsonl"; _write_trace(path, rows); traces[name] = str(path); summaries[name] = _summary(rows, initial_hinge_rad=initial_hinge, release_step=release_step)
    locked = summaries["locked_unpressed_external_torque"]; handle_only = summaries["handle_only"]; pressed = summaries["pressed_external_torque"]
    locked_ok = locked["max_abs_hinge_displacement_rad"] <= args.locked_max_hinge_rad; handle_pressed = handle_only["final_handle_rad"] >= args.release_handle_rad; pressed_open = pressed["max_hinge_displacement_rad"] >= args.unlocked_min_hinge_rad
    if topology.mode == "constraint_gate":
        release_ok = bool(handle_only["release_step"] is not None and handle_only["gate_active_final"] is False and handle_pressed); pressed_open = bool(pressed_open and pressed["gate_active_final"] is False); overall = "SUPPORTED" if locked_ok and release_ok and pressed_open else "NOT_SUPPORTED"; latch_verdict = "CONSTRAINT_GATE_SUPPORTED" if overall == "SUPPORTED" else "CONSTRAINT_GATE_NOT_SUPPORTED"
    elif topology.mode == "physical_collision":
        release_ok = handle_pressed or handle_only["final_latch_slide_m"] is not None; overall = "MUJOCO_CANDIDATE_DIAGNOSTIC"; latch_verdict = "PHYSICAL_COLLISION_CANDIDATE_OPEN_RESPONSE" if pressed_open else "PHYSICAL_COLLISION_CANDIDATE_NOT_OPENING"
    else:
        release_ok = handle_pressed; overall = "NO_LATCH_UPPER_BOUND_ONLY"; latch_verdict = "NO_LATCH_IS_NOT_A_LATCH"
    report = {
        "schema": "doordog.sim2sim.depthadd_v3_door_mechanics_probe.v2", "result": overall, "evidence_level": "RUNTIME_PASS", "scope": "NO_POLICY; EXACT_EPISODE_RESET; NO_20M_ROOM_WALL_PROBE", "scene": str(scene), "episode_receipt": str(receipt_path), "mujoco_version": mujoco.__version__,
        "physics": {"timestep_s": float(model.opt.timestep), "physics_hz": 1.0 / float(model.opt.timestep)}, "exact_reset": {"receipt_schema": initial["receipt"]["initial_state_realization"]["schema"], "case_id": initial["receipt"].get("case_id"), "robot_root_and_20_joint_state": "APPLIED_FROM_EPISODE_RECEIPT", "door_and_handle": "scene_home closed state"},
        "latch_topology": {"mode_requested": args.mode, "mode_realized": topology.mode, "door_constraint_gate_eq_id": topology.gate_eq_id, "handle_latch_mimic_eq_id": topology.mimic_eq_id, "latch_slide_qpos": topology.latch_slide_qpos, "latch_slide_dof": topology.latch_slide_dof, "latch_collision_geom_id": topology.latch_collision_geom_id, "broad_frame_geom_ids": list(topology.broad_frame_geom_ids), "physical_collision_equivalence": "NOT_CLAIMED; MUJOCO_CANDIDATE_ONLY"},
        "intervention": {"external_door_torque_nm": args.external_door_torque_nm, "force_steps": args.force_steps, "handle_release_max_steps": args.handle_release_max_steps, "release_only_settle_steps": args.release_only_settle_steps, "applied_generalized_force": "data.qfrc_applied[door_hinge_dof]", "lane_contract": "unpressed+torque; handle-only; pressed+same-torque"}, "thresholds": {"release_handle_rad": args.release_handle_rad, "locked_max_hinge_rad": args.locked_max_hinge_rad, "unlocked_min_hinge_rad": args.unlocked_min_hinge_rad},
        "lanes": {name: {"trace": traces[name], **summaries[name]} for name in summaries}, "typed_verdicts": {"locked_unpressed_response": "LOCKED" if locked_ok else "UNPRESSED_TORQUE_OPENED", "handle_only_press": "HANDLE_PRESSED" if handle_pressed else "HANDLE_PRESS_NOT_REACHED", "pressed_same_torque_response": "OPENED_UNDER_MATCHED_TORQUE" if pressed_open else "PRESSED_TORQUE_NOT_OPENING", "latch": latch_verdict, "cross_engine": "PHYSICAL_COLLISION_IS_MUJOCO_CANDIDATE_NOT_PHYSX_EQUIVALENCE" if topology.mode == "physical_collision" else "NOT_APPLICABLE"},
        "limitations": ["No policy, action replay, camera capture, or 20m room-wall probe.", "The external generalized torque is a mechanics diagnostic, not a training or hardware result.", "The physical_collision lane records latch_collision contact against broad frame geoms when present; it does not establish Isaac PhysX equivalence."],
    }
    (output / "door_mechanics_probe_receipt.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"); print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
