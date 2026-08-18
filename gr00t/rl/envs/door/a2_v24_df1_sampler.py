"""Deterministic DF1 marginal-E1 training assignments for the r12 pilot.

The sampler owns the intervention labels used by the frozen 500-batch pilot.
Every training bucket uses the registered 20 N*m arm cap; the 25 N*m rescue
cap is a post-training evaluation reference and is never emitted here.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from numbers import Integral
from typing import Any, Mapping, Sequence


F3_SAMPLER_SCHEMA = "a2_piper_v24_df1_sampler_v1"
F3_BUCKETS = ("F00", "F05", "F10")
F3_BUCKET_TO_FRICTION = {"F00": "F00", "F05": "F05", "F10": "F10"}
F3_BUCKET_TO_CAP_NM = {"F00": 20.0, "F05": 20.0, "F10": 20.0}
F3_FRICTION_PARAMETERS = {
    "F00": (0.0, 0.0, 0.0),
    "F05": (0.5, 0.375, 0.0),
    "F10": (1.0, 0.75, 0.0),
}
F3_TRAINING_BUCKET_SEEDS = {0: 24030, 1: 24031}
F3_PHASE_ENDS = {
    500: (100, 250, 500),
    10: (2, 5, 10),
}
F3_PHASE_COUNTS = {
    500: (
        (4096, 0, 0),
        (2458, 1638, 0),
        (1229, 2458, 409),
    ),
    10: (
        (64, 0, 0),
        (38, 26, 0),
        (19, 39, 6),
    ),
}
F3_TOPOLOGIES = {500: 4096, 10: 64}
F3_ALLOWED_CAPS_NM = frozenset({20.0})
F3_RESCUE_CAP_NM = 25.0
F3_CONFIRMED_E2_SHARE = 0.0


def _require_int(value: Any, *, name: str, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError(f"{name} must be an integer; got {value!r}.")
    result = int(value)
    if minimum is not None and result < minimum:
        raise ValueError(f"{name} must be >= {minimum}; got {value!r}.")
    return result


@dataclass(frozen=True)
class F3Assignment:
    global_batch: int
    phase: int
    env_index: int
    intended_bucket: str
    friction_profile: str
    cap_nm: float

    def __post_init__(self) -> None:
        if self.intended_bucket not in F3_BUCKETS:
            raise ValueError(f"unsupported F3 intended bucket: {self.intended_bucket!r}")
        if self.friction_profile != F3_BUCKET_TO_FRICTION[self.intended_bucket]:
            raise ValueError("F3 assignment bucket/profile mapping is inconsistent.")
        if float(self.cap_nm) != F3_BUCKET_TO_CAP_NM[self.intended_bucket]:
            raise ValueError("F3 assignment bucket/cap mapping is inconsistent.")
        if float(self.cap_nm) not in F3_ALLOWED_CAPS_NM:
            raise ValueError("F3 assignment cap is outside the registered training cap set.")
        _require_int(self.global_batch, name="global_batch", minimum=0)
        _require_int(self.phase, name="phase", minimum=0)
        _require_int(self.env_index, name="env_index", minimum=0)

    @property
    def confirmed_e2(self) -> bool:
        return False

    def as_dict(self) -> dict[str, Any]:
        return {
            "global_batch": self.global_batch,
            "phase": self.phase,
            "env_index": self.env_index,
            "intended_bucket": self.intended_bucket,
            "friction_profile": self.friction_profile,
            "cap_nm": self.cap_nm,
            "confirmed_e2": False,
        }


@dataclass(frozen=True)
class F3Transition:
    previous_global_batch: int | None
    global_batch: int
    previous_phase: int | None
    phase: int
    full_reset_boundary: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "previous_global_batch": self.previous_global_batch,
            "global_batch": self.global_batch,
            "previous_phase": self.previous_phase,
            "phase": self.phase,
            "full_reset_boundary": self.full_reset_boundary,
            "reset_scope": "full_environment" if self.full_reset_boundary else "none",
        }


class F3Sampler:
    """Absolute-global-batch sampler with deterministic phase shuffles."""

    def __init__(
        self,
        *,
        training_seed: int = 0,
        total_batches: int = 500,
        num_envs: int | None = None,
        bucket_seed: int | None = None,
    ) -> None:
        self.training_seed = _require_int(training_seed, name="training_seed", minimum=0)
        if self.training_seed not in F3_TRAINING_BUCKET_SEEDS:
            raise ValueError("F3 training_seed must be 0 or 1.")
        self.total_batches = _require_int(total_batches, name="total_batches", minimum=1)
        if self.total_batches not in F3_TOPOLOGIES:
            raise ValueError(f"F3 total_batches must be one of {tuple(F3_TOPOLOGIES)}.")
        expected_envs = F3_TOPOLOGIES[self.total_batches]
        self.num_envs = expected_envs if num_envs is None else _require_int(num_envs, name="num_envs", minimum=1)
        if self.num_envs != expected_envs:
            raise ValueError(
                f"F3 topology requires num_envs={expected_envs} for total_batches={self.total_batches}; "
                f"got {self.num_envs}."
            )
        expected_seed = F3_TRAINING_BUCKET_SEEDS[self.training_seed]
        self.bucket_seed = expected_seed if bucket_seed is None else _require_int(bucket_seed, name="bucket_seed", minimum=0)
        if self.bucket_seed != expected_seed:
            raise ValueError(
                f"F3 training_seed={self.training_seed} requires bucket_seed={expected_seed}; got {self.bucket_seed}."
            )
        self._assignments: dict[int, tuple[F3Assignment, ...]] = {}

    @classmethod
    def from_config(cls, config: Mapping[str, Any]) -> "F3Sampler":
        if config.get("a2_v24_f3_marginal_e1_enabled") is not True:
            raise ValueError("F3 sampler requires a2_v24_f3_marginal_e1_enabled=true.")
        return cls(
            training_seed=_require_int(config.get("a2_v24_f3_marginal_e1_training_seed"), name="a2_v24_f3_marginal_e1_training_seed", minimum=0),
            total_batches=_require_int(config.get("a2_v24_f3_marginal_e1_total_batches"), name="a2_v24_f3_marginal_e1_total_batches", minimum=1),
            num_envs=_require_int(config.get("a2_v24_f3_marginal_e1_num_envs"), name="a2_v24_f3_marginal_e1_num_envs", minimum=1),
            bucket_seed=_require_int(config.get("a2_v24_f3_marginal_e1_bucket_seed"), name="a2_v24_f3_marginal_e1_bucket_seed", minimum=0),
        )

    @property
    def phase_ends(self) -> tuple[int, ...]:
        return F3_PHASE_ENDS[self.total_batches]

    @property
    def phase_boundaries(self) -> tuple[int, ...]:
        return self.phase_ends

    def phase_index(self, global_batch: int) -> int:
        batch = _require_int(global_batch, name="global_batch", minimum=0)
        if batch >= self.total_batches:
            raise ValueError(f"global_batch must be in [0, {self.total_batches}); got {global_batch!r}.")
        for phase, end in enumerate(self.phase_ends):
            if batch < end:
                return phase
        raise RuntimeError("F3 phase table does not cover total_batches.")

    def phase_counts(self, global_batch: int) -> tuple[int, int, int]:
        return F3_PHASE_COUNTS[self.total_batches][self.phase_index(global_batch)]

    def bucket_counts(self, global_batch: int) -> dict[str, int]:
        return dict(zip(F3_BUCKETS, self.phase_counts(global_batch)))

    def transition(self, previous_global_batch: int | None, global_batch: int) -> F3Transition:
        current = self.phase_index(global_batch)
        previous_phase = None
        if previous_global_batch is not None:
            previous = _require_int(previous_global_batch, name="previous_global_batch", minimum=0)
            if global_batch < previous:
                raise ValueError("F3 global batches must be monotonic.")
            previous_phase = self.phase_index(previous)
        return F3Transition(
            previous_global_batch=previous_global_batch,
            global_batch=int(global_batch),
            previous_phase=previous_phase,
            phase=current,
            full_reset_boundary=previous_phase is None or previous_phase != current,
        )

    def _phase_assignments(self, phase: int) -> tuple[F3Assignment, ...]:
        if phase in self._assignments:
            return self._assignments[phase]
        bucket_names: list[str] = []
        for bucket, count in zip(F3_BUCKETS, F3_PHASE_COUNTS[self.total_batches][phase]):
            if count < 0:
                raise RuntimeError("F3 phase counts cannot be negative.")
            bucket_names.extend([bucket] * count)
        if len(bucket_names) != self.num_envs:
            raise RuntimeError("F3 phase counts do not equal the configured environment count.")
        order = list(range(self.num_envs))
        random.Random(self.bucket_seed + phase).shuffle(order)
        assignments = [
            F3Assignment(
                global_batch=0,
                phase=phase,
                env_index=env_index,
                intended_bucket=bucket_names[source_index],
                friction_profile=F3_BUCKET_TO_FRICTION[bucket_names[source_index]],
                cap_nm=F3_BUCKET_TO_CAP_NM[bucket_names[source_index]],
            )
            for env_index, source_index in enumerate(order)
        ]
        self._assignments[phase] = tuple(assignments)
        return self._assignments[phase]

    def assignments(self, global_batch: int) -> tuple[F3Assignment, ...]:
        batch = _require_int(global_batch, name="global_batch", minimum=0)
        phase = self.phase_index(batch)
        return tuple(
            F3Assignment(
                global_batch=batch,
                phase=assignment.phase,
                env_index=assignment.env_index,
                intended_bucket=assignment.intended_bucket,
                friction_profile=assignment.friction_profile,
                cap_nm=assignment.cap_nm,
            )
            for assignment in self._phase_assignments(phase)
        )

    def assignment(self, global_batch: int, env_index: int) -> F3Assignment:
        index = _require_int(env_index, name="env_index", minimum=0)
        if index >= self.num_envs:
            raise ValueError(f"env_index must be in [0, {self.num_envs}); got {env_index!r}.")
        return self.assignments(global_batch)[index]

    def sample(self, global_batch: int, *, num_envs: int | None = None) -> tuple[F3Assignment, ...]:
        if num_envs is not None and num_envs != self.num_envs:
            raise ValueError(f"F3 sampler requires num_envs={self.num_envs}; got {num_envs}.")
        return self.assignments(global_batch)

    def telemetry(self, global_batch: int) -> list[dict[str, Any]]:
        return [assignment.as_dict() for assignment in self.assignments(global_batch)]

    def build_assignment_receipt(
        self,
        global_batch: int,
        *,
        applied_parameter_readbacks: Sequence[Mapping[str, Any]],
        full_reset_boundary: bool,
    ) -> dict[str, Any]:
        assignments = self.assignments(global_batch)
        if len(applied_parameter_readbacks) != self.num_envs:
            raise ValueError("F3 assignment readbacks must contain exactly one row per environment.")
        readbacks: list[dict[str, Any]] = []
        for env_index, (assignment, readback) in enumerate(zip(assignments, applied_parameter_readbacks)):
            if not isinstance(readback, Mapping):
                raise TypeError(f"F3 assignment readback env{env_index} must be a mapping.")
            if readback.get("env_index", env_index) != env_index:
                raise RuntimeError("F3 assignment readback env ordering changed.")
            if assignment.cap_nm not in F3_ALLOWED_CAPS_NM:
                raise RuntimeError("F3 assignment used an unregistered training cap.")
            readbacks.append(dict(readback))
        return {
            "schema": F3_SAMPLER_SCHEMA + ".assignment_receipt",
            "global_batch": int(global_batch),
            "phase": self.phase_index(global_batch),
            "full_reset_boundary": bool(full_reset_boundary),
            "bucket_seed": self.bucket_seed,
            "training_seed": self.training_seed,
            "intended_bucket_counts": self.bucket_counts(global_batch),
            "intended_assignments": [assignment.as_dict() for assignment in assignments],
            "applied_parameter_readbacks": readbacks,
            "confirmed_e2": False,
            "training_cap_nm": 20.0,
            "rescue_cap_nm": F3_RESCUE_CAP_NM,
        }


__all__ = [
    "F3_ALLOWED_CAPS_NM",
    "F3Assignment",
    "F3_BUCKETS",
    "F3_BUCKET_TO_CAP_NM",
    "F3_BUCKET_TO_FRICTION",
    "F3_FRICTION_PARAMETERS",
    "F3_PHASE_COUNTS",
    "F3_PHASE_ENDS",
    "F3_RESCUE_CAP_NM",
    "F3_CONFIRMED_E2_SHARE",
    "F3Sampler",
    "F3Transition",
    "F3_SAMPLER_SCHEMA",
    "F3_TOPOLOGIES",
    "F3_TRAINING_BUCKET_SEEDS",
]
