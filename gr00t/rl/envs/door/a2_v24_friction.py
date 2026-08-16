"""Native v24 door-hinge friction backend.

The backend is intentionally small: it owns the v24 friction contract and
binds it to the public IsaacLab :class:`Articulation` API.  The door task
decides when the backend is enabled; this module never changes observations,
actions, rewards, or transitions.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from numbers import Real
from typing import Any, Mapping

import torch


NATIVE_BACKEND = "native_joint_friction_v1"
HINGE_PATTERN = ".*hinge.*"


def _finite_nonnegative(value: Any, *, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{label} must be a finite non-negative real number")
    number = float(value)
    if not math.isfinite(number) or number < 0.0:
        raise ValueError(f"{label} must be a finite non-negative real number")
    return number


@dataclass(frozen=True)
class V24FrictionConfig:
    """Resolved v24 native friction configuration.

    Coefficients stay ``None`` while the feature is disabled.  This is useful
    for keeping the legacy path a genuine no-write path instead of silently
    manufacturing a zero-valued profile.
    """

    enabled: bool
    backend: str
    static_effort: float | None
    dynamic_effort: float | None
    viscous_coefficient: float | None

    @classmethod
    def from_mapping(cls, config: Mapping[str, Any]) -> "V24FrictionConfig":
        enabled = config.get("a2_v24_friction_enabled", False)
        if not isinstance(enabled, bool):
            raise TypeError("env.config.a2_v24_friction_enabled must be bool")

        backend = config.get("a2_v24_friction_backend", NATIVE_BACKEND)
        if not isinstance(backend, str) or not backend:
            raise TypeError("env.config.a2_v24_friction_backend must be a non-empty string")
        if enabled and backend != NATIVE_BACKEND:
            raise ValueError(
                "enabled v24 friction requires the native backend "
                f"{NATIVE_BACKEND!r}; got {backend!r}"
            )

        static_value = config.get("a2_v24_friction_static_effort")
        dynamic_value = config.get("a2_v24_friction_dynamic_effort")
        viscous_value = config.get("a2_v24_friction_viscous_coefficient")
        if not enabled:
            return cls(
                enabled=False,
                backend=backend,
                static_effort=None,
                dynamic_effort=None,
                viscous_coefficient=None,
            )

        if static_value is None or dynamic_value is None or viscous_value is None:
            raise ValueError(
                "enabled v24 friction requires static, dynamic, and viscous coefficients"
            )
        static_effort = _finite_nonnegative(
            static_value, label="env.config.a2_v24_friction_static_effort"
        )
        dynamic_effort = _finite_nonnegative(
            dynamic_value, label="env.config.a2_v24_friction_dynamic_effort"
        )
        viscous_coefficient = _finite_nonnegative(
            viscous_value, label="env.config.a2_v24_friction_viscous_coefficient"
        )
        if dynamic_effort > static_effort:
            raise ValueError(
                "env.config.a2_v24_friction_dynamic_effort must be <= "
                "a2_v24_friction_static_effort"
            )
        return cls(
            enabled=True,
            backend=backend,
            static_effort=static_effort,
            dynamic_effort=dynamic_effort,
            viscous_coefficient=viscous_coefficient,
        )


class A2V24DoorFrictionBackend:
    """Apply and read back native per-environment door-hinge profiles.

    ``articulation`` is intentionally duck-typed so this module can be parsed
    and imported without importing IsaacSim.  At runtime it must be an
    IsaacLab ``Articulation`` exposing ``find_joints``, ``data``, and
    ``write_joint_friction_coefficient_to_sim``.
    """

    _READBACK_FIELDS = (
        "joint_friction_coeff",
        "joint_dynamic_friction_coeff",
        "joint_viscous_friction_coeff",
    )

    def __init__(self, articulation: Any, config: V24FrictionConfig, *, device: str | torch.device):
        if not config.enabled:
            raise ValueError("A2V24DoorFrictionBackend requires an enabled v24 friction config")
        if config.backend != NATIVE_BACKEND:
            raise ValueError(f"unsupported v24 friction backend: {config.backend!r}")
        if not hasattr(articulation, "find_joints"):
            raise TypeError("door articulation must expose the public find_joints API")
        if not hasattr(articulation, "write_joint_friction_coefficient_to_sim"):
            raise TypeError(
                "door articulation must expose the public "
                "write_joint_friction_coefficient_to_sim API"
            )

        hinge_ids, hinge_names = articulation.find_joints(HINGE_PATTERN, preserve_order=True)
        if len(hinge_ids) != 1 or len(hinge_names) != 1:
            raise RuntimeError(
                "v24 native friction requires exactly one door hinge joint; "
                f"got ids={hinge_ids!r}, names={hinge_names!r}"
            )
        self.articulation = articulation
        self.config = config
        self.device = torch.device(device)
        self.hinge_joint_id = int(hinge_ids[0])
        self.hinge_joint_name = str(hinge_names[0])

        joint_pos = getattr(getattr(articulation, "data", None), "joint_pos", None)
        if not torch.is_tensor(joint_pos) or joint_pos.ndim != 2:
            raise TypeError("door articulation data.joint_pos must be a runtime (N,J) torch tensor")
        if joint_pos.device != self.device:
            raise TypeError(
                f"door articulation device mismatch: expected {self.device}, got {joint_pos.device}"
            )
        self.dtype = joint_pos.dtype
        self.num_envs = int(joint_pos.shape[0])
        self.static_profile = torch.full(
            (self.num_envs, 1), config.static_effort, dtype=self.dtype, device=self.device
        )
        self.dynamic_profile = torch.full(
            (self.num_envs, 1), config.dynamic_effort, dtype=self.dtype, device=self.device
        )
        self.viscous_profile = torch.full(
            (self.num_envs, 1), config.viscous_coefficient, dtype=self.dtype, device=self.device
        )

    def _validate_env_ids(self, env_ids: torch.Tensor) -> None:
        if (
            not torch.is_tensor(env_ids)
            or env_ids.ndim != 1
            or env_ids.dtype != torch.long
            or env_ids.device != self.device
            or env_ids.numel() == 0
            or torch.any(env_ids < 0)
            or torch.any(env_ids >= self.num_envs)
        ):
            raise TypeError(
                "v24 friction env_ids must be a device-local torch.long vector within the scene; "
                f"got shape={getattr(env_ids, 'shape', None)}, dtype={getattr(env_ids, 'dtype', None)}, "
                f"device={getattr(env_ids, 'device', None)}"
            )

    def _validate_profile_rows(self, rows: torch.Tensor, env_ids: torch.Tensor, *, label: str) -> None:
        if (
            not torch.is_tensor(rows)
            or rows.shape != (env_ids.numel(), 1)
            or rows.device != self.device
            or rows.dtype != self.dtype
            or not torch.isfinite(rows).all()
            or (rows < 0.0).any()
        ):
            raise TypeError(
                f"{label} must be finite, non-negative, device-local, dtype={self.dtype}, "
                f"and shape ({env_ids.numel()}, 1); got shape={getattr(rows, 'shape', None)}, "
                f"dtype={getattr(rows, 'dtype', None)}, device={getattr(rows, 'device', None)}"
            )

    def install_profile_rows(
        self,
        env_ids: torch.Tensor,
        static_profile: torch.Tensor,
        dynamic_profile: torch.Tensor,
        viscous_profile: torch.Tensor,
    ) -> None:
        """Install exact device-local per-environment profile rows."""

        self._validate_env_ids(env_ids)
        self._validate_profile_rows(static_profile, env_ids, label="static_profile")
        self._validate_profile_rows(dynamic_profile, env_ids, label="dynamic_profile")
        self._validate_profile_rows(viscous_profile, env_ids, label="viscous_profile")
        if torch.any(dynamic_profile > static_profile):
            raise ValueError("dynamic_profile must be <= static_profile for every environment")
        self.static_profile[env_ids] = static_profile
        self.dynamic_profile[env_ids] = dynamic_profile
        self.viscous_profile[env_ids] = viscous_profile

    def _readback(self, env_ids: torch.Tensor) -> dict[str, torch.Tensor]:
        self._validate_env_ids(env_ids)
        values: dict[str, torch.Tensor] = {}
        for field in self._READBACK_FIELDS:
            data = getattr(self.articulation.data, field, None)
            if not torch.is_tensor(data) or data.ndim != 2 or data.shape[1] <= self.hinge_joint_id:
                raise RuntimeError(f"Articulation.data.{field} is unavailable for friction readback")
            selected = data[env_ids][:, [self.hinge_joint_id]]
            if selected.shape != (env_ids.numel(), 1) or selected.device != self.device:
                raise RuntimeError(f"Articulation.data.{field} readback shape/device mismatch")
            values[field] = selected.clone()
        return values

    def apply(self, env_ids: torch.Tensor) -> dict[str, Any]:
        """Write stored rows for selected environments and verify readback."""

        self._validate_env_ids(env_ids)
        requested = {
            "joint_friction_coeff": self.static_profile[env_ids].clone(),
            "joint_dynamic_friction_coeff": self.dynamic_profile[env_ids].clone(),
            "joint_viscous_friction_coeff": self.viscous_profile[env_ids].clone(),
        }
        self.articulation.write_joint_friction_coefficient_to_sim(
            requested["joint_friction_coeff"],
            requested["joint_dynamic_friction_coeff"],
            requested["joint_viscous_friction_coeff"],
            joint_ids=[self.hinge_joint_id],
            env_ids=env_ids,
        )
        readback = self._readback(env_ids)
        matches = {
            field: bool(torch.allclose(requested[field], readback[field], atol=1.0e-6, rtol=0.0))
            for field in self._READBACK_FIELDS
        }
        if not all(matches.values()):
            raise RuntimeError(
                "v24 native friction readback mismatch: "
                f"requested={self._as_lists(requested)!r}, readback={self._as_lists(readback)!r}"
            )
        return {
            "env_ids": env_ids.detach().cpu().tolist(),
            "requested": self._as_lists(requested),
            "readback": self._as_lists(readback),
            "matches": matches,
        }

    @staticmethod
    def _as_lists(values: Mapping[str, torch.Tensor]) -> dict[str, list[list[float]]]:
        return {name: value.detach().cpu().tolist() for name, value in values.items()}

    def receipt_fragment(self) -> dict[str, Any]:
        """Return source-backed identity/units for runtime receipts."""

        return {
            "backend": NATIVE_BACKEND,
            "hinge_joint_name": self.hinge_joint_name,
            "hinge_joint_id": self.hinge_joint_id,
            "num_envs": self.num_envs,
            "static_profile_shape": list(self.static_profile.shape),
            "dynamic_profile_shape": list(self.dynamic_profile.shape),
            "viscous_profile_shape": list(self.viscous_profile.shape),
            "authority": "REQUESTED_NATIVE_JOINT_FRICTION_COEFFICIENT_WITH_BUFFER_READBACK",
        }


__all__ = [
    "HINGE_PATTERN",
    "NATIVE_BACKEND",
    "A2V24DoorFrictionBackend",
    "V24FrictionConfig",
]
