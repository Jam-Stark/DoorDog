"""Deterministic r13 behavioral F3-prime training assignments."""

from __future__ import annotations

import random
from dataclasses import dataclass
from numbers import Integral
from typing import Any, Mapping


R13_F3_SAMPLER_SCHEMA = "a2_piper_v24_r13_f3_behavioral_sampler_v1"
R13_F3_BUCKETS = ("E0_SHAM", "E1_BOUNDARY", "NEAR_E2")
R13_F3_BUCKET_TO_FRICTION = {
    "E0_SHAM": "F00",
    "E1_BOUNDARY": "P10",
    "NEAR_E2": "P20",
}
R13_F3_BUCKET_TO_CAP_NM = {
    "E0_SHAM": 40.0,
    "E1_BOUNDARY": 20.0,
    "NEAR_E2": 20.0,
}
R13_F3_TRAINING_BUCKET_SEEDS = {0: 24050, 1: 24051}
R13_F3_PHASE_ENDS = {500: (100, 250, 500), 10: (2, 5, 10)}
R13_F3_PHASE_COUNTS = {
    500: ((4096, 0, 0), (2458, 1638, 0), (1229, 2458, 409)),
    10: ((64, 0, 0), (38, 26, 0), (19, 39, 6)),
}
R13_F3_TOPOLOGIES = {500: 4096, 10: 64}


def _integer(value: Any, *, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError(f"{name} must be an integer; got {value!r}.")
    return int(value)


@dataclass(frozen=True)
class R13F3Assignment:
    global_batch: int
    phase: int
    env_index: int
    intended_bucket: str
    friction_profile: str
    cap_nm: float

    def __post_init__(self) -> None:
        if self.intended_bucket not in R13_F3_BUCKETS:
            raise ValueError(f"unsupported r13 F3 bucket: {self.intended_bucket!r}")
        if self.friction_profile != R13_F3_BUCKET_TO_FRICTION[self.intended_bucket]:
            raise ValueError("r13 F3 bucket/profile mapping changed.")
        if float(self.cap_nm) != R13_F3_BUCKET_TO_CAP_NM[self.intended_bucket]:
            raise ValueError("r13 F3 bucket/cap mapping changed.")
        if _integer(self.global_batch, name="global_batch") < 0:
            raise ValueError("global_batch must be non-negative.")
        if _integer(self.phase, name="phase") < 0 or _integer(self.env_index, name="env_index") < 0:
            raise ValueError("phase and env_index must be non-negative.")

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


class R13F3Sampler:
    """Absolute-batch sampler for the Owner-approved behavioral E-region."""

    def __init__(self, *, training_seed: int, total_batches: int, num_envs: int, bucket_seed: int) -> None:
        self.training_seed = _integer(training_seed, name="training_seed")
        self.total_batches = _integer(total_batches, name="total_batches")
        self.num_envs = _integer(num_envs, name="num_envs")
        self.bucket_seed = _integer(bucket_seed, name="bucket_seed")
        if self.training_seed not in R13_F3_TRAINING_BUCKET_SEEDS:
            raise ValueError("r13 F3 training_seed must be 0 or 1.")
        if self.total_batches not in R13_F3_TOPOLOGIES:
            raise ValueError("r13 F3 total_batches must be 10 or 500.")
        if self.num_envs != R13_F3_TOPOLOGIES[self.total_batches]:
            raise ValueError("r13 F3 num_envs does not match its registered batch topology.")
        if self.bucket_seed != R13_F3_TRAINING_BUCKET_SEEDS[self.training_seed]:
            raise ValueError("r13 F3 bucket_seed does not match training_seed.")
        self._phase_cache: dict[int, tuple[R13F3Assignment, ...]] = {}

    @classmethod
    def from_config(cls, config: Mapping[str, Any]) -> "R13F3Sampler":
        if config.get("a2_v24_f3_marginal_e1_enabled") is not True:
            raise ValueError("r13 F3 sampler requires its runtime gate.")
        if config.get("a2_v24_f3_semantics_revision") != "R13_BEHAVIORAL":
            raise ValueError("r13 F3 sampler requires R13_BEHAVIORAL semantics.")
        return cls(
            training_seed=config.get("a2_v24_f3_marginal_e1_training_seed"),
            total_batches=config.get("a2_v24_f3_marginal_e1_total_batches"),
            num_envs=config.get("a2_v24_f3_marginal_e1_num_envs"),
            bucket_seed=config.get("a2_v24_f3_marginal_e1_bucket_seed"),
        )

    @property
    def phase_ends(self) -> tuple[int, ...]:
        return R13_F3_PHASE_ENDS[self.total_batches]

    def phase_index(self, global_batch: int) -> int:
        batch = _integer(global_batch, name="global_batch")
        if not 0 <= batch < self.total_batches:
            raise ValueError("r13 F3 global_batch is outside the registered range.")
        return next(index for index, end in enumerate(self.phase_ends) if batch < end)

    def bucket_counts(self, global_batch: int) -> dict[str, int]:
        return dict(zip(R13_F3_BUCKETS, R13_F3_PHASE_COUNTS[self.total_batches][self.phase_index(global_batch)]))

    def _phase_assignments(self, phase: int) -> tuple[R13F3Assignment, ...]:
        if phase in self._phase_cache:
            return self._phase_cache[phase]
        buckets: list[str] = []
        for bucket, count in zip(R13_F3_BUCKETS, R13_F3_PHASE_COUNTS[self.total_batches][phase]):
            buckets.extend([bucket] * count)
        if len(buckets) != self.num_envs:
            raise RuntimeError("r13 F3 phase counts do not equal num_envs.")
        order = list(range(self.num_envs))
        random.Random(self.bucket_seed + phase).shuffle(order)
        assignments = tuple(
            R13F3Assignment(
                global_batch=0,
                phase=phase,
                env_index=env_index,
                intended_bucket=buckets[source_index],
                friction_profile=R13_F3_BUCKET_TO_FRICTION[buckets[source_index]],
                cap_nm=R13_F3_BUCKET_TO_CAP_NM[buckets[source_index]],
            )
            for env_index, source_index in enumerate(order)
        )
        self._phase_cache[phase] = assignments
        return assignments

    def assignments(self, global_batch: int) -> tuple[R13F3Assignment, ...]:
        batch = _integer(global_batch, name="global_batch")
        phase = self.phase_index(batch)
        return tuple(
            R13F3Assignment(
                global_batch=batch,
                phase=phase,
                env_index=item.env_index,
                intended_bucket=item.intended_bucket,
                friction_profile=item.friction_profile,
                cap_nm=item.cap_nm,
            )
            for item in self._phase_assignments(phase)
        )

    def telemetry(self, global_batch: int) -> list[dict[str, Any]]:
        return [item.as_dict() for item in self.assignments(global_batch)]


__all__ = [
    "R13F3Assignment",
    "R13F3Sampler",
    "R13_F3_BUCKETS",
    "R13_F3_BUCKET_TO_CAP_NM",
    "R13_F3_BUCKET_TO_FRICTION",
    "R13_F3_SAMPLER_SCHEMA",
]
