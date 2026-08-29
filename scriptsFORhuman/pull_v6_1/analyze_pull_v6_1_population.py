#!/usr/bin/env python3
"""Aggregate only admitted strict-natural V6.1P evaluation traces."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

from trace_utils import first_episode_rows, load_trace, required, summary_from_rows


def _input(value: str) -> tuple[str, Path]:
    label, separator, path = value.partition("=")
    if separator != "=" or not label or not path:
        raise ValueError("input must be candidate_label=/path")
    return label, Path(path)


def _mapping(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.suffix == ".json":
        value = json.loads(path.read_text(encoding="utf-8"))
    else:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{label} must be a mapping: {path}")
    return value


def _nested(mapping: dict[str, Any], *keys: str) -> Any:
    value: Any = mapping
    for key in keys:
        if not isinstance(value, dict):
            raise TypeError(f"{'.'.join(keys)} parent must be a mapping")
        value = required(value, key, ".".join(keys[:-1]) or "mapping")
    return value


def _disabled(value: Any, name: str) -> None:
    if value is not False:
        raise ValueError(f"{name} must be false for strict-natural population evaluation")


def _admit(config_path: Path, metadata_path: Path) -> dict[str, Any]:
    config = _mapping(config_path, "resolved config")
    metadata = _mapping(metadata_path, "diagnostic metadata")
    if required(config, "num_envs", "resolved config") != 16:
        raise ValueError("strict-natural population evaluation requires num_envs=16")
    seed = required(config, "seed", "resolved config")
    if isinstance(seed, bool) or not isinstance(seed, int) or seed not in (0, 1, 2, 3):
        raise ValueError("formal population evaluation seed must be one of 0/1/2/3")
    checkpoint = required(config, "checkpoint", "resolved config")
    if not isinstance(checkpoint, str) or not checkpoint or checkpoint.startswith("REQUIRED_"):
        raise ValueError("resolved config must contain the actual selected checkpoint")
    env = _nested(config, "env", "config")
    if not isinstance(env, dict):
        raise TypeError("resolved config.env.config must be a mapping")
    if required(env, "staged_reset_ratios", "env.config") != [1.0, 0.0, 0.0, 0.0, 0.0, 0.0]:
        raise ValueError("strict-natural population evaluation requires Stage0-only reset ratios")
    for key in ("a2_pull_v6_stage4_bank_enabled", "a2_pull_v61_late_state_bank_enabled"):
        _disabled(required(env, key, "env.config"), f"env.config.{key}")
    evaluation = _nested(config, "algo", "config", "eval")
    if not isinstance(evaluation, dict):
        raise TypeError("resolved config.algo.config.eval must be a mapping")
    for key in (
        "a2_forced_gripper_close_enabled", "a2_hold_oracle_enabled",
        "a2_pull_v6_passage_lateral_counterfactual_enabled",
        "a2_pull_p2_intervention_enabled", "a2_pull_v61_post_release_intervention_enabled",
    ):
        _disabled(required(evaluation, key, "algo.config.eval"), f"algo.config.eval.{key}")
    _disabled(required(metadata, "forced_gripper_close_enabled", "diagnostic metadata"), "metadata.forced_gripper_close_enabled")
    _disabled(_nested(metadata, "p2_intervention", "enabled"), "metadata.p2_intervention.enabled")
    _disabled(_nested(metadata, "v61_post_release_intervention", "enabled"), "metadata.v61_post_release_intervention.enabled")
    return {"checkpoint": checkpoint, "eval_seed": seed, "resolved_config": str(config_path), "metadata": str(metadata_path)}


def _load_terminal_records(path: Path, eval_seed: int) -> dict[int, dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list) or len(value) != 16 or not all(isinstance(row, dict) for row in value):
        raise TypeError(f"terminal records must be a 16-row JSON list: {path}")
    records = {int(required(row, "env_id", "terminal record")): row for row in value}
    if sorted(records) != list(range(16)):
        raise ValueError(f"terminal records must contain env0..15 exactly: {path}")
    if any(required(row, "seed", "terminal record") != eval_seed for row in value):
        raise ValueError(f"terminal record seed must match resolved eval seed={eval_seed}: {path}")
    return records


def _terminal_only_summary(record: dict[str, Any]) -> dict[str, Any]:
    max_stage = int(required(record, "max_stage", "terminal record"))
    goal_reached = bool(required(record, "goal_reached", "terminal record"))
    return {
        "env_id": int(required(record, "env_id", "terminal record")),
        "trace_coverage": False,
        "max_stage": max_stage,
        "goal_reached": goal_reached,
        "e5_step": None,
        "clean_release_step": None,
        "release_persistence_k25_step": None,
        "frame_passage_step": None,
        "e6_step": None,
        "e7_step": None,
        "terminal_record_e5_reached": max_stage >= 4,
        "terminal_record_e6_reached": max_stage >= 5,
        "terminal_record_e7_reached": goal_reached,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace", action="append", type=_input, required=True)
    parser.add_argument("--resolved-config", action="append", type=_input, required=True)
    parser.add_argument("--metadata", action="append", type=_input, required=True)
    parser.add_argument("--records", action="append", type=_input, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    traces, configs, metadata, terminal_records = map(
        dict, (args.trace, args.resolved_config, args.metadata, args.records)
    )
    if not (set(traces) == set(configs) == set(metadata) == set(terminal_records)):
        raise ValueError("trace, records, resolved-config, and metadata labels must match exactly")
    candidates = {}
    for label, path in sorted(traces.items()):
        provenance = _admit(configs[label], metadata[label])
        rows = load_trace(path)
        records = _load_terminal_records(terminal_records[label], provenance["eval_seed"])
        traced_env_ids = sorted({
            int(row["env_id"])
            for row in rows
            if row["episode_index"] == 0 and row["first_episode_active"] is True
        })
        episodes = []
        for env_id in range(16):
            if env_id in traced_env_ids:
                episode = summary_from_rows(first_episode_rows(rows, env_id))
                episode["trace_coverage"] = True
                episode["max_stage"] = int(required(records[env_id], "max_stage", "terminal record"))
                episode["goal_reached"] = bool(required(records[env_id], "goal_reached", "terminal record"))
                if episode["goal_reached"] != (episode["e7_step"] is not None):
                    raise ValueError(f"{label} env{env_id} trace E7 and terminal goal_reached disagree")
            else:
                episode = _terminal_only_summary(records[env_id])
            episodes.append(episode)
        candidates[label] = {
            "trace": str(path), "terminal_records": str(terminal_records[label]),
            "trace_coverage": len(traced_env_ids), "denominator": 16,
            "provenance": provenance, "episodes": episodes,
            "funnel": {
                "e5": sum(item["max_stage"] >= 4 for item in episodes),
                "clean_release": sum(item["clean_release_step"] is not None for item in episodes),
                "frame_passage": sum(item["frame_passage_step"] is not None for item in episodes),
                "e6": sum(item["max_stage"] >= 5 for item in episodes),
                "e7": sum(item["goal_reached"] for item in episodes),
            },
        }
    report = {
        "schema": "a2_piper_pull_v61_population_report_v1",
        "claim_scope": "admitted 16-env strict-natural evaluations with bank and all evaluator interventions disabled.",
        "candidates": candidates,
    }
    if args.output.exists():
        raise FileExistsError(args.output)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
