"""Runtime evidence exporter for the r13 behavioral F3-prime population."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from gr00t.rl.envs.door.a2_v24_force_boundary import (
    FORCE_WINDOW_SELECTION_STABLE_OPENING,
    FORCE_WINDOW_TRANSITIONS,
    P2RuntimeExporter,
    aggregate_p2_force_window,
)


R13_F3_EVIDENCE_SCHEMA = "a2_piper_v24_r13_f3_behavioral_evidence_v1"
R13_F3_CONDITION = "R13_F3_PRIME_BEHAVIORAL"
R13_F3_NUM_ENVS = 32
R13_F3_GLOBAL_STEP = 500
R13_F3_CHECKPOINT_ID = "model_step_000500"
R13_F3_CONTINUITY_ID = "R13_F3_POST_TRAIN_BOUNDARY_EVAL"


@dataclass(frozen=True)
class R13F3EvidenceMetadata:
    cell: str
    posture: str
    seed: int
    checkpoint_path: str
    checkpoint_id: str
    global_step: int
    scenario_id: str
    episode_ordinal: int
    evidence_path: str

    def __post_init__(self) -> None:
        if self.posture not in ("FULL", "RP0") or self.seed not in (0, 1):
            raise ValueError("r13 F3 posture/seed must be FULL|RP0 and 0|1.")
        if self.cell != f"DF1_{self.posture}_SEED{self.seed}":
            raise ValueError("r13 F3 cell does not match posture/seed.")
        if self.global_step != R13_F3_GLOBAL_STEP or self.checkpoint_id != R13_F3_CHECKPOINT_ID:
            raise ValueError("r13 F3 evidence requires the final step500 checkpoint.")
        checkpoint = Path(self.checkpoint_path)
        if checkpoint.name != "model_step_000500.pt" or self.cell not in checkpoint.parts:
            raise ValueError("r13 F3 checkpoint path does not identify its cell.")
        if self.scenario_id not in {f"S{index:02d}" for index in range(16)}:
            raise ValueError("r13 F3 scenario must be canonical S00..S15.")
        if self.episode_ordinal not in (0, 1):
            raise ValueError("r13 F3 episode ordinal must be 0 or 1.")
        if not self.evidence_path:
            raise ValueError("r13 F3 evidence requires an output path.")

    def as_dict(self) -> dict[str, Any]:
        return {
            "cell": self.cell,
            "posture": self.posture,
            "seed": self.seed,
            "training_seed": self.seed,
            "checkpoint_path": self.checkpoint_path,
            "checkpoint_id": self.checkpoint_id,
            "global_step": self.global_step,
            "condition": R13_F3_CONDITION,
            "scenario": self.scenario_id,
            "scenario_id": self.scenario_id,
            "episode_ordinal": self.episode_ordinal,
            "continuity_id": R13_F3_CONTINUITY_ID,
            "evidence_path": self.evidence_path,
        }


class R13F3EvidenceExporter:
    """Collect 32 source-valid stable-grasp windows without using capacity admission."""

    def __init__(self, *, num_envs: int, metadata_by_env: Sequence[R13F3EvidenceMetadata], output_path: str | Path) -> None:
        if num_envs != R13_F3_NUM_ENVS or len(metadata_by_env) != R13_F3_NUM_ENVS:
            raise ValueError("r13 F3 evidence requires exactly 32 environments.")
        expected = tuple((f"S{index % 16:02d}", index // 16) for index in range(32))
        actual = tuple((item.scenario_id, item.episode_ordinal) for item in metadata_by_env)
        if actual != expected:
            raise ValueError("r13 F3 evidence topology must be two canonical16 episode ordinals.")
        self.output_path = Path(output_path).expanduser()
        if self.output_path.exists() or self.output_path.is_symlink():
            raise RuntimeError(f"r13 F3 evidence refuses to overwrite: {self.output_path}")
        self.num_envs = num_envs
        self.metadata_by_env = tuple(metadata_by_env)
        self._windows: list[list[dict[str, Any]]] = [[] for _ in range(num_envs)]
        self._selected: list[list[dict[str, Any]] | None] = [None] * num_envs
        self._records: list[dict[str, Any] | None] = [None] * num_envs
        self._completed = [False] * num_envs
        self._published = False

    @staticmethod
    def _source_valid(window: Sequence[Mapping[str, Any]]) -> bool:
        return all(
            row.get("alpha_valid") is True
            and row.get("foot_slip_valid") is True
            and row.get("source_unavailable") is None
            and row.get("grasp_source_unavailable") is False
            and row.get("model_source_unavailable") is False
            for row in window
        )

    def record(self, rows: Sequence[Mapping[str, Any]]) -> None:
        if self._published or len(rows) != self.num_envs:
            raise RuntimeError("r13 F3 evidence requires one live row per environment.")
        for env_id, row in enumerate(rows):
            if self._completed[env_id] or self._records[env_id] is not None or self._selected[env_id] is not None:
                continue
            metadata = self.metadata_by_env[env_id]
            if row.get("env_id") != env_id or row.get("episode_index") != 0:
                raise RuntimeError(f"r13 F3 env{env_id} requires first-episode telemetry.")
            if row.get("scenario_id") != metadata.scenario_id or row.get("continuity_id") != R13_F3_CONTINUITY_ID:
                raise RuntimeError(f"r13 F3 env{env_id} scenario/continuity changed.")
            if row.get("profile") != "P10" or row.get("cap_nm") != 20.0:
                raise RuntimeError("r13 F3 evidence requires the P10/cap20 boundary face.")
            if row.get("alpha_valid") is not True:
                self._windows[env_id] = []
                continue
            step = row.get("episode_step")
            if isinstance(step, bool) or not isinstance(step, int):
                raise RuntimeError("r13 F3 telemetry requires integer episode_step.")
            if self._windows[env_id] and step != self._windows[env_id][-1]["episode_step"] + 1:
                self._windows[env_id] = []
            self._windows[env_id].append(dict(row))
            self._windows[env_id] = self._windows[env_id][-FORCE_WINDOW_TRANSITIONS:]
            if len(self._windows[env_id]) == FORCE_WINDOW_TRANSITIONS:
                candidate = [dict(item) for item in self._windows[env_id]]
                if P2RuntimeExporter._qualifies_stable_opening(candidate) and self._source_valid(candidate):
                    self._selected[env_id] = candidate

    def mark_completed(self, env_ids: Sequence[int], episode_lengths: Sequence[int]) -> tuple[dict[str, Any], ...]:
        ids = tuple(int(value) for value in env_ids.detach().cpu().tolist()) if hasattr(env_ids, "detach") else tuple(env_ids)
        if len(ids) != len(episode_lengths) or len(ids) != len(set(ids)):
            raise ValueError("r13 F3 completed env ids/lengths are invalid.")
        produced = []
        for env_id, episode_length in zip(ids, episode_lengths):
            if self._completed[env_id]:
                continue
            window = self._selected[env_id]
            if window is None:
                raise RuntimeError(f"r13 F3 env{env_id} completed without a source-valid stable-grasp opening window.")
            aggregate = aggregate_p2_force_window(window, selection_status=FORCE_WINDOW_SELECTION_STABLE_OPENING)
            metadata = self.metadata_by_env[env_id]
            record = dict(aggregate)
            record.update(metadata.as_dict())
            record.update(
                {
                    "schema": f"{R13_F3_EVIDENCE_SCHEMA}.window",
                    "candidate_bucket": "E1_BOUNDARY",
                    "confirmed_e2": False,
                    "env_id": env_id,
                    "episode_complete": True,
                    "completed": True,
                    "completed_episode_length": int(episode_length),
                    "runtime_generated": True,
                    "runtime_producer": "R13F3EvidenceExporter",
                    "window_id": f"{metadata.cell}-{metadata.checkpoint_id}-{metadata.scenario_id}-ord{metadata.episode_ordinal}",
                    "window_rows": [copy.deepcopy(item) for item in window],
                }
            )
            self._records[env_id] = record
            self._completed[env_id] = True
            produced.append(record)
        return tuple(produced)

    def reset_envs(self, env_ids: Sequence[int]) -> None:
        ids = tuple(int(value) for value in env_ids.detach().cpu().tolist()) if hasattr(env_ids, "detach") else tuple(env_ids)
        for env_id in ids:
            if not self._completed[env_id]:
                raise RuntimeError(f"r13 F3 env{env_id} reset before evidence completion.")

    def publish(self) -> dict[str, Any]:
        if self._published or not all(self._completed) or any(item is None for item in self._records):
            raise RuntimeError("r13 F3 publication requires 32 completed rows.")
        records = [item for item in self._records if item is not None]
        if len({item["window_id"] for item in records}) != 32:
            raise RuntimeError("r13 F3 window identities are not unique.")
        payload = {
            "schema": R13_F3_EVIDENCE_SCHEMA,
            "condition": R13_F3_CONDITION,
            "num_envs": 32,
            "global_step": 500,
            "expected_cardinality": 32,
            "records": records,
        }
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with self.output_path.open("x", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
        self._published = True
        return payload


__all__ = [
    "R13_F3_CHECKPOINT_ID",
    "R13_F3_CONDITION",
    "R13_F3_CONTINUITY_ID",
    "R13F3EvidenceExporter",
    "R13F3EvidenceMetadata",
]
