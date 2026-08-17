"""Runtime operations for the selected door latch realization."""

from __future__ import annotations

import mujoco


class ConstraintGate:
    def __init__(self, model: mujoco.MjModel, *, release_handle_rad: float):
        self.eq_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_EQUALITY, "door_constraint_gate")
        handle_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "handle_hinge")
        self.handle_qpos_address = int(model.jnt_qposadr[handle_id])
        self.release_handle_rad = float(release_handle_rad)

    def update(self, data: mujoco.MjData) -> bool:
        if data.eq_active[self.eq_id] and data.qpos[self.handle_qpos_address] >= self.release_handle_rad:
            data.eq_active[self.eq_id] = 0
            return True
        return False
