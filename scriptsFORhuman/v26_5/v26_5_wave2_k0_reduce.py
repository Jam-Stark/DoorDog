#!/usr/bin/env python3
"""Reduce preregistered Wave2 K0 exact64 source-control evaluations."""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

from omegaconf import OmegaConf


EPISODES = 64
SIDES = ("left", "right")
SOURCE = "/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v26_acquisition_supplement_20260823/continuation/V26A_LR_S1_POLICY800/model_step_002000.pt"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def finite(value: Any, label: str) -> float:
    require(isinstance(value, (int, float)) and not isinstance(value, bool), f"{label} must be numeric")
    value = float(value)
    require(math.isfinite(value), f"{label} must be finite")
    return value


def load(path: Path) -> Any:
    require(path.is_file(), f"missing evidence artifact: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_side(path: Path, side: str, seed: int) -> dict[str, Any]:
    metrics = load(path / "metrics_eval.json")
    records = load(path / "a2_v14_per_env_records.json")
    trace = load(path / "stage2_5_step_trace.json")
    metadata = load(path / "a2_eval_diagnostic_metadata.json")
    config = OmegaConf.to_container(OmegaConf.load(path / ".hydra/runtime_config.yaml"), resolve=False)
    require(isinstance(metrics, dict) and isinstance(records, list) and isinstance(trace, list) and isinstance(metadata, dict) and isinstance(config, dict), f"{path}: invalid eval payload")
    env_cfg = config.get("env", {}).get("config", {})
    eval_cfg = config.get("algo", {}).get("config", {}).get("eval", {})
    require(config.get("checkpoint") == SOURCE and config.get("checkpoint_load_mode") == "full" and config.get("auto_load_latest") is False, f"{path}: CONT_STEP2000 full-load contract failed")
    require(config.get("num_envs") == EPISODES and config.get("seed") == seed, f"{path}: exact64/seed contract failed")
    require(eval_cfg.get("num_eval_episodes") == EPISODES and eval_cfg.get("eval_num_envs_episodes") is True, f"{path}: natural first-episode contract failed")
    require(env_cfg.get("a2_v26_door_open_lr") == side and env_cfg.get("a2_v26_side_permutation_seed") == seed and env_cfg.get("enable_staged_reset") is False, f"{path}: natural side contract failed")
    require(env_cfg.get("a2_v26_4_side_canonicalization_enabled") is False and env_cfg.get("a2_v26_5_geometry_target_enabled") is False and env_cfg.get("a2_v26_5_stage3_delta_rebase_enabled") is False, f"{path}: O0A0 contract failed")
    require(metadata.get("forced_gripper_close_enabled") is False and metadata.get("stage2_close_gate_forced_gripper_close_enabled") is False, f"{path}: intervention contaminates K0")
    terminal = metrics.get("episode_terminal_diagnostics")
    max_stage = metrics.get("episode_max_stage_reached")
    require(isinstance(terminal, list) and len(terminal) == EPISODES and isinstance(max_stage, list) and len(max_stage) == EPISODES and len(records) == EPISODES, f"{path}: exact64 evidence missing")
    terminal_by_env: dict[int, dict[str, Any]] = {}
    stage_by_env: dict[int, int] = {}
    records_by_env: dict[int, dict[str, Any]] = {}
    for row, stage in zip(terminal, max_stage, strict=True):
        require(isinstance(row, dict) and isinstance(stage, int) and not isinstance(stage, bool), f"{path}: invalid terminal row")
        env_id = row.get("env_id")
        require(isinstance(env_id, int) and 0 <= env_id < EPISODES and env_id not in terminal_by_env, f"{path}: invalid terminal env id")
        terminal_by_env[env_id] = row
        stage_by_env[env_id] = stage
    for row in records:
        require(isinstance(row, dict), f"{path}: invalid per-env record")
        env_id = row.get("env_id")
        require(isinstance(env_id, int) and 0 <= env_id < EPISODES and env_id not in records_by_env, f"{path}: invalid record env id")
        require(row.get("max_stage") == stage_by_env[env_id], f"{path}: record/max-stage disagreement env{env_id}")
        records_by_env[env_id] = row
    require(set(terminal_by_env) == set(records_by_env) == set(range(EPISODES)), f"{path}: exact64 env coverage failed")
    traces: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for index, row in enumerate(trace):
        require(isinstance(row, dict) and row.get("first_episode_active") is True and row.get("episode_index") == 0, f"{path}: trace row {index} is not a first episode")
        env_id = row.get("env_id")
        require(isinstance(env_id, int) and 0 <= env_id < EPISODES, f"{path}: trace env id invalid")
        traces[env_id].append(row)
    require(set(traces) == set(range(EPISODES)), f"{path}: trace does not cover exact64")
    stage3 = k5 = integrity = stage4 = stage5 = goal = contact_steps = stable_steps = 0
    for env_id in range(EPISODES):
        term = terminal_by_env[env_id]
        v2, v3 = term.get("v26_2"), term.get("v26_3")
        require(isinstance(v2, dict) and isinstance(v3, dict), f"{path}: v26 telemetry missing env{env_id}")
        stage = stage_by_env[env_id]
        stage3 += int(stage >= 3)
        k5 += int(int(v2.get("k5_steps", -1)) >= 5)
        integrity += int(finite(v2.get("integrity_violations"), f"{path}: v2 integrity")) + int(finite(v3.get("integrity_violations"), f"{path}: v3 integrity"))
        stage4 += int(stage >= 4); stage5 += int(stage >= 5); goal += int(records_by_env[env_id].get("goal_reached") is True)
        previous = None
        for row in sorted(traces[env_id], key=lambda item: item.get("step_index", -1)):
            step = row.get("step_index")
            require(isinstance(step, int) and step >= 0 and (previous is None or step == previous + 1), f"{path}: trace topology invalid env{env_id}")
            previous = step
            if row.get("stage_buf") == 3:
                stability = row.get("contact_stability")
                require(isinstance(stability, bool), f"{path}: contact stability invalid env{env_id}")
                contact_steps += 1
                stable_steps += int(stability)
    return {
        "episodes": EPISODES,
        "Stage3_admission_count": stage3,
        "K5_episode_count": k5,
        "contact_stability_steps": {"numerator": stable_steps, "denominator": contact_steps, "rate": None if contact_steps == 0 else stable_steps / contact_steps},
        "integrity_violations": integrity,
        "stage_episode_count": {"stage4": stage4, "stage5": stage5, "goal": goal},
    }


def admitted(row: dict[str, Any]) -> bool:
    return row["Stage3_admission_count"] >= 16 and row["K5_episode_count"] >= 16 and row["contact_stability_steps"]["rate"] is not None and row["contact_stability_steps"]["rate"] >= 0.90 and row["integrity_violations"] == 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eval-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), f"refusing to overwrite Wave2 K0 reducer: {args.output}")
    formal: dict[str, dict[str, Any]] = {}
    for seed in (0, 1):
        label = f"K0_CONT_STEP2000_O0A0_S{seed}"
        formal[f"seed{seed}"] = {side: load_side(args.eval_root / label / side, side, seed) for side in SIDES}
    rows = [formal[f"seed{seed}"][side] for seed in (0, 1) for side in SIDES]
    payload = {
        "schema": "a2_piper_base_v26_5_wave2_k0_reducer_v1",
        "status": "EXPERIMENT_COMPLETE",
        "episodes_per_side": EPISODES,
        "source_control": formal,
        "admission_gate": {"all_four_strata_pass": all(admitted(row) for row in rows), "typed_outcome": "K0_SOURCE_CONTROL_ADMITTED" if all(admitted(row) for row in rows) else "K0_SOURCE_CONTROL_NOT_ADMITTED"},
        "downstream": {"stage4_stage5_goal": "reported_only", "dual_view_identity": {"status": "NOT_RUN", "reason": "K0 defines no dual-view actor implementation or view mapping."}},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
