"""Runtime evidence for the registered r12 post-F3 checkpoint evaluation."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from gr00t.rl.envs.door.a2_v24_force_boundary import (
    FORCE_WINDOW_SELECTION_ALPHA_FALLBACK,
    FORCE_WINDOW_SELECTION_STABLE_OPENING,
    FORCE_WINDOW_TRANSITIONS,
    P2RuntimeExporter,
    aggregate_p2_force_window,
)


R12_EVIDENCE_SCHEMA = "a2_piper_v24_r12_f3_post_training_evidence_v1"
R12_CONDITION = "R12_PILOT_CELL"
R12_NUM_ENVS = 16
R12_GLOBAL_STEP = 500
R12_CHECKPOINT_ID = "model_step_000500"
R12_CONTINUITY_ID = "F3_POST_TRAIN_EVAL"
R12_SCENARIOS = tuple(f"S{index:02d}" for index in range(R12_NUM_ENVS))


def _env_ids(values: Sequence[int], *, num_envs: int) -> tuple[int, ...]:
    if hasattr(values, "detach") and hasattr(values, "cpu") and hasattr(values, "tolist"):
        result = tuple(int(value) for value in values.detach().cpu().tolist())
    else:
        result = tuple(values)
    if not result or len(set(result)) != len(result):
        raise ValueError("r12 F3 evidence env ids must be non-empty and unique.")
    if any(isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < num_envs for value in result):
        raise ValueError(f"r12 F3 evidence env ids must be integers in [0, {num_envs}).")
    return result


@dataclass(frozen=True)
class R12F3EvidenceMetadata:
    cell: str
    posture: str
    seed: int
    checkpoint_path: str
    checkpoint_id: str
    global_step: int
    scenario_id: str
    evidence_path: str

    def __post_init__(self) -> None:
        if self.posture not in ("FULL", "RP0") or self.seed not in (0, 1):
            raise ValueError("r12 F3 evidence posture/seed must be FULL|RP0 and 0|1.")
        if self.cell != f"DF1_{self.posture}_SEED{self.seed}":
            raise ValueError("r12 F3 evidence cell must match its registered posture and seed.")
        if self.global_step != R12_GLOBAL_STEP or self.checkpoint_id != R12_CHECKPOINT_ID:
            raise ValueError("r12 F3 evidence requires the registered final step500 checkpoint.")
        checkpoint = Path(self.checkpoint_path)
        if checkpoint.name != f"{R12_CHECKPOINT_ID}.pt" or self.cell not in checkpoint.parts:
            raise ValueError("r12 F3 checkpoint path must identify the cell final model_step_000500.pt.")
        if self.scenario_id not in R12_SCENARIOS:
            raise ValueError("r12 F3 evidence scenario id must be S00..S15.")
        if not isinstance(self.evidence_path, str) or not self.evidence_path:
            raise ValueError("r12 F3 evidence requires its runtime output path.")

    def as_dict(self) -> dict[str, Any]:
        return {
            "cell": self.cell,
            "posture": self.posture,
            "seed": self.seed,
            "training_seed": self.seed,
            "checkpoint_path": self.checkpoint_path,
            "checkpoint_id": self.checkpoint_id,
            "global_step": self.global_step,
            "condition": R12_CONDITION,
            "scenario": self.scenario_id,
            "scenario_id": self.scenario_id,
            "continuity_id": R12_CONTINUITY_ID,
            "evidence_path": self.evidence_path,
        }


class R12F3EvidenceExporter:
    """Collect one runtime-selected 25-transition window from each of 16 envs."""

    def __init__(
        self,
        *,
        num_envs: int,
        metadata_by_env: Sequence[R12F3EvidenceMetadata],
        output_path: str | Path,
    ) -> None:
        if num_envs != R12_NUM_ENVS or len(metadata_by_env) != R12_NUM_ENVS:
            raise ValueError("r12 F3 post-training evidence requires exactly 16 environments.")
        if tuple(metadata.scenario_id for metadata in metadata_by_env) != R12_SCENARIOS:
            raise ValueError("r12 F3 metadata must map env0..15 exactly to S00..S15.")
        output = Path(output_path).expanduser()
        if output.exists() or output.is_symlink():
            raise RuntimeError(f"r12 F3 evidence refuses to overwrite existing path: {output}")
        self.num_envs = num_envs
        self.metadata_by_env = tuple(metadata_by_env)
        self.output_path = output
        self._windows: list[list[dict[str, Any]]] = [[] for _ in range(num_envs)]
        self._fallback: list[list[dict[str, Any]] | None] = [None] * num_envs
        self._source_valid_fallback: list[list[dict[str, Any]] | None] = [None] * num_envs
        self._stable_fallback: list[list[dict[str, Any]] | None] = [None] * num_envs
        self._selected: list[list[dict[str, Any]] | None] = [None] * num_envs
        self._records: list[dict[str, Any] | None] = [None] * num_envs
        self._completed = [False] * num_envs
        self._published = False

    def record(self, rows: Sequence[Mapping[str, Any]]) -> None:
        if self._published or len(rows) != self.num_envs:
            raise RuntimeError("r12 F3 evidence record requires one live row per env before publication.")
        for env_id, row in enumerate(rows):
            if self._completed[env_id] or self._records[env_id] is not None:
                continue
            if not isinstance(row, Mapping) or row.get("env_id") != env_id or row.get("episode_index") != 0:
                raise RuntimeError(f"r12 F3 evidence env{env_id} requires first-episode typed telemetry.")
            if row.get("scenario_id") != R12_SCENARIOS[env_id] or row.get("continuity_id") != R12_CONTINUITY_ID:
                raise RuntimeError(f"r12 F3 evidence env{env_id} scenario/continuity provenance changed.")
            if row.get("profile") != "F05" or row.get("cap_nm") != 20.0:
                raise RuntimeError("r12 F3 evidence requires the registered F05/cap20 evaluation face.")
            if row.get("alpha_valid") is not True:
                self._windows[env_id] = []
                continue
            step = row.get("episode_step")
            if isinstance(step, bool) or not isinstance(step, int):
                raise RuntimeError("r12 F3 evidence requires integer episode steps.")
            if self._windows[env_id] and step != self._windows[env_id][-1]["episode_step"] + 1:
                self._windows[env_id] = []
            self._windows[env_id].append(dict(row))
            self._windows[env_id] = self._windows[env_id][-FORCE_WINDOW_TRANSITIONS:]
            if len(self._windows[env_id]) != FORCE_WINDOW_TRANSITIONS:
                continue
            candidate = [dict(item) for item in self._windows[env_id]]
            if self._fallback[env_id] is None:
                self._fallback[env_id] = candidate
            measurement_valid = all(
                row.get("valid") is True
                and row.get("foot_slip_valid") is True
                and row.get("source_unavailable") is None
                and row.get("grasp_source_unavailable") is False
                and row.get("model_source_unavailable") is False
                for row in candidate
            )
            if measurement_valid and self._source_valid_fallback[env_id] is None:
                self._source_valid_fallback[env_id] = candidate
            if P2RuntimeExporter._qualifies_stable_opening(candidate):
                if self._stable_fallback[env_id] is None:
                    self._stable_fallback[env_id] = candidate
                if self._selected[env_id] is None and measurement_valid:
                    self._selected[env_id] = candidate

    def mark_completed(self, env_ids: Sequence[int], episode_lengths: Sequence[int]) -> tuple[dict[str, Any], ...]:
        ids = _env_ids(env_ids, num_envs=self.num_envs)
        if len(ids) != len(episode_lengths):
            raise ValueError("r12 F3 completion lengths must match completed env ids.")
        produced = []
        for env_id, episode_length in zip(ids, episode_lengths):
            if self._completed[env_id]:
                continue
            if isinstance(episode_length, bool) or not isinstance(episode_length, int) or episode_length <= 0:
                raise RuntimeError("r12 F3 evidence requires a positive completed episode length.")
            window = (
                self._selected[env_id]
                or self._source_valid_fallback[env_id]
                or self._stable_fallback[env_id]
                or self._fallback[env_id]
            )
            if window is None:
                raise RuntimeError(f"r12 F3 env{env_id} completed without a full alpha-valid window.")
            selection = (
                FORCE_WINDOW_SELECTION_STABLE_OPENING
                if self._selected[env_id] is not None
                else FORCE_WINDOW_SELECTION_ALPHA_FALLBACK
            )
            aggregate = aggregate_p2_force_window(window, selection_status=selection)
            metadata = self.metadata_by_env[env_id]
            record = dict(aggregate)
            record.update(metadata.as_dict())
            record.update(
                {
                    "schema": f"{R12_EVIDENCE_SCHEMA}.window",
                    "candidate_bucket": "F05",
                    "confirmed_e2": False,
                    "env_id": env_id,
                    "episode_ordinal": 0,
                    "episode_complete": True,
                    "completed": True,
                    "completed_episode_length": episode_length,
                    "runtime_generated": True,
                    "runtime_producer": "R12F3EvidenceExporter",
                    "window_id": f"{metadata.cell}-{metadata.checkpoint_id}-{metadata.scenario_id}-window0",
                    "window_rows": [copy.deepcopy(dict(row)) for row in window],
                }
            )
            self._records[env_id] = record
            self._completed[env_id] = True
            produced.append(record)
        return tuple(produced)

    def reset_envs(self, env_ids: Sequence[int]) -> None:
        for env_id in _env_ids(env_ids, num_envs=self.num_envs):
            if not self._completed[env_id]:
                raise RuntimeError(f"r12 F3 env{env_id} reset before evidence completion.")

    def publish(self) -> dict[str, Any]:
        if self._published or not all(self._completed) or any(row is None for row in self._records):
            raise RuntimeError("r12 F3 evidence publication requires exactly 16 completed runtime rows.")
        records = [record for record in self._records if record is not None]
        if len({record["window_id"] for record in records}) != R12_NUM_ENVS:
            raise RuntimeError("r12 F3 evidence window identities are not unique.")
        payload = {
            "schema": R12_EVIDENCE_SCHEMA,
            "condition": R12_CONDITION,
            "num_envs": R12_NUM_ENVS,
            "global_step": R12_GLOBAL_STEP,
            "expected_cardinality": R12_NUM_ENVS,
            "records": records,
        }
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with self.output_path.open("x", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
        self._published = True
        return payload


__all__ = [
    "R12_CHECKPOINT_ID",
    "R12_CONDITION",
    "R12_CONTINUITY_ID",
    "R12F3EvidenceExporter",
    "R12F3EvidenceMetadata",
]
