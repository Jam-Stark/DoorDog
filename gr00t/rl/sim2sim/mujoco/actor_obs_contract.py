"""Executable 81D DepthADD v3 actor-observation contract.

The field order is the deployed Isaac policy-ready order, not the stale order
written in early handoff prose.  Runtime composition and the serialized
contract intentionally share this one authority.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping

import torch


@dataclass(frozen=True)
class ActorObservationField:
    name: str
    start: int
    end: int
    unit: str
    frame: str
    scale: float
    update_clock: str
    latency_control_steps: int
    reset_semantics: str
    source: str

    @property
    def width(self) -> int:
        return self.end - self.start

    def as_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["slice"] = [self.start, self.end]
        value["shape"] = [self.width]
        return value


DEPTHADD_V3_ACTOR_OBS_FIELDS = (
    ActorObservationField(
        "scaled_base_command",
        0,
        5,
        "normalized_command",
        "robot_base",
        1.0,
        "control_50hz",
        1,
        "zeros",
        "previous physical base command after observation scaling",
    ),
    ActorObservationField(
        "scaled_base_command_duplicate",
        5,
        10,
        "normalized_command",
        "robot_base",
        1.0,
        "control_50hz",
        1,
        "zeros",
        "deployed sorted-term alias of scaled_base_command",
    ),
    ActorObservationField(
        "q_minus_default",
        10,
        30,
        "rad",
        "joint",
        1.0,
        "control_50hz_post_physics",
        0,
        "current reset joint position minus default",
        "robot joint position in production joint order",
    ),
    ActorObservationField(
        "dof_velocity_x0p05",
        30,
        50,
        "rad_per_s_scaled",
        "joint",
        0.05,
        "control_50hz_post_physics",
        0,
        "current reset joint velocity",
        "robot joint velocity in production joint order",
    ),
    ActorObservationField(
        "previous_actions19",
        50,
        69,
        "normalized_action",
        "policy_action",
        1.0,
        "control_50hz",
        1,
        "zeros",
        "previous logical 19D action after adapter composition",
    ),
    ActorObservationField(
        "base_angular_velocity_x0p5",
        69,
        72,
        "rad_per_s_scaled",
        "robot_base_local",
        0.5,
        "control_50hz_post_physics",
        0,
        "current reset base angular velocity",
        "MuJoCo local body angular velocity",
    ),
    ActorObservationField(
        "previous_arm_delta6",
        72,
        78,
        "normalized_action",
        "policy_action",
        1.0,
        "control_50hz",
        1,
        "zeros",
        "previous raw Student arm delta before stage accumulation",
    ),
    ActorObservationField(
        "projected_gravity",
        78,
        81,
        "unit_vector",
        "robot_base_local",
        1.0,
        "control_50hz_post_physics",
        0,
        "gravity projected from reset pose",
        "world gravity rotated into robot base frame",
    ),
)


def depthadd_v3_actor_obs_contract() -> dict[str, object]:
    """Return the JSON-ready contract consumed by ``prepare`` receipts."""

    return {
        "schema": "doordog.sim2sim.depthadd_v3.actor_obs_runtime_contract.v1",
        "dtype": "float32",
        "total_dim": 81,
        "control_hz": 50,
        "composition_authority": "this field table and compose_depthadd_v3_actor_obs",
        "deployed_alias_semantics": (
            "Isaac sorted observation terms then stripped the _raw suffix; "
            "a2_base_command_raw therefore resolves to a duplicate a2_base_command block"
        ),
        "fields": [field.as_dict() for field in DEPTHADD_V3_ACTOR_OBS_FIELDS],
    }


def compose_depthadd_v3_actor_obs(blocks: Mapping[str, torch.Tensor]) -> torch.Tensor:
    """Validate and concatenate one batch of policy-ready actor blocks."""

    expected = tuple(field.name for field in DEPTHADD_V3_ACTOR_OBS_FIELDS)
    if set(blocks) != set(expected):
        missing = sorted(set(expected) - set(blocks))
        extra = sorted(set(blocks) - set(expected))
        raise ValueError(f"DepthADD actor observation block mismatch: missing={missing}, extra={extra}")

    batch_size: int | None = None
    device: torch.device | None = None
    values: list[torch.Tensor] = []
    for field in DEPTHADD_V3_ACTOR_OBS_FIELDS:
        value = blocks[field.name]
        if not torch.is_tensor(value) or value.ndim != 2 or value.shape[1] != field.width:
            shape = None if not torch.is_tensor(value) else tuple(value.shape)
            raise ValueError(
                f"{field.name} must have shape (batch, {field.width}); received {shape}"
            )
        if value.dtype != torch.float32 or not bool(torch.all(torch.isfinite(value))):
            raise ValueError(f"{field.name} must be finite torch.float32")
        if batch_size is None:
            batch_size = value.shape[0]
            device = value.device
        elif value.shape[0] != batch_size or value.device != device:
            raise ValueError(f"{field.name} batch/device does not match the first block")
        values.append(value)

    actor_obs = torch.cat(values, dim=1)
    if actor_obs.shape[1] != 81:
        raise RuntimeError(f"DepthADD actor observation has invalid shape {tuple(actor_obs.shape)}")
    return actor_obs
