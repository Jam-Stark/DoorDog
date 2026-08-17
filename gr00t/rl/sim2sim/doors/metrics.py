"""Door-state-only task metrics for shadow evaluation."""

from __future__ import annotations


class DoorStateMetrics:
    def __init__(self, *, open_threshold_rad: float):
        self.open_threshold_rad = float(open_threshold_rad)
        self.max_hinge_rad = float("-inf")
        self.max_handle_rad = float("-inf")
        self.first_open_time_s: float | None = None

    def update(self, *, time_s: float, hinge_rad: float, handle_rad: float) -> None:
        self.max_hinge_rad = max(self.max_hinge_rad, float(hinge_rad))
        self.max_handle_rad = max(self.max_handle_rad, float(handle_rad))
        if self.first_open_time_s is None and hinge_rad >= self.open_threshold_rad:
            self.first_open_time_s = float(time_s)

    def receipt(self) -> dict[str, object]:
        return {
            "source": "DIRECT_MUJOCO_DOOR_STATE",
            "open_threshold_rad": self.open_threshold_rad,
            "max_hinge_rad": self.max_hinge_rad,
            "max_handle_rad": self.max_handle_rad,
            "opened": self.first_open_time_s is not None,
            "first_open_time_s": self.first_open_time_s,
        }
