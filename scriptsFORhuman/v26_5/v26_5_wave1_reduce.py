#!/usr/bin/env python3
"""Reduce v26-5 Wave1 exact64 natural evaluations without altering evidence."""

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
FORMAL = (("O1A0", 0), ("O1A0", 1), ("O1A1", 0), ("O1A1", 1))


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def finite(value: Any, label: str) -> float:
    require(isinstance(value, (int, float)) and not isinstance(value, bool), f"{label} must be numeric")
    result = float(value)
    require(math.isfinite(result), f"{label} must be finite")
    return result


def load(path: Path) -> Any:
    require(path.is_file(), f"missing evidence artifact: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def terminal_by_env(metrics: dict[str, Any], records: list[Any], path: Path) -> tuple[dict[int, dict[str, Any]], dict[int, dict[str, Any]], dict[int, int]]:
    terminal = metrics.get("episode_terminal_diagnostics")
    max_stage = metrics.get("episode_max_stage_reached")
    require(isinstance(terminal, list) and len(terminal) == EPISODES, f"{path}: missing exact64 terminal diagnostics")
    require(isinstance(max_stage, list) and len(max_stage) == EPISODES, f"{path}: missing exact64 max-stage rows")
    require(isinstance(records, list) and len(records) == EPISODES, f"{path}: missing exact64 per-env records")
    by_terminal: dict[int, dict[str, Any]] = {}
    by_record: dict[int, dict[str, Any]] = {}
    stages: dict[int, int] = {}
    for row, stage in zip(terminal, max_stage, strict=True):
        require(isinstance(row, dict) and isinstance(stage, int) and not isinstance(stage, bool), f"{path}: invalid terminal/max-stage row")
        env_id = row.get("env_id")
        require(isinstance(env_id, int) and 0 <= env_id < EPISODES and env_id not in by_terminal, f"{path}: invalid terminal env id")
        by_terminal[env_id] = row; stages[env_id] = stage
    for row in records:
        require(isinstance(row, dict), f"{path}: invalid per-env record")
        env_id = row.get("env_id")
        require(isinstance(env_id, int) and 0 <= env_id < EPISODES and env_id not in by_record, f"{path}: invalid record env id")
        require(row.get("max_stage") == stages[env_id], f"{path}: record/max-stage disagreement env{env_id}")
        by_record[env_id] = row
    require(set(by_terminal) == set(range(EPISODES)) == set(by_record), f"{path}: exact64 env coverage failed")
    return by_terminal, by_record, stages


def load_side(path: Path, side: str, seed: int, factor: str) -> dict[str, Any]:
    metrics = load(path / "metrics_eval.json")
    records = load(path / "a2_v14_per_env_records.json")
    trace = load(path / "stage2_5_step_trace.json")
    metadata = load(path / "a2_eval_diagnostic_metadata.json")
    config = OmegaConf.to_container(
        OmegaConf.load(path / ".hydra/runtime_config.yaml"), resolve=False
    )
    require(isinstance(metrics, dict) and isinstance(trace, list) and isinstance(metadata, dict) and isinstance(config, dict), f"{path}: invalid eval payload")
    env_cfg = config.get("env", {}).get("config", {})
    eval_cfg = config.get("algo", {}).get("config", {}).get("eval", {})
    require(config.get("checkpoint_load_mode") == "full" and config.get("auto_load_latest") is False, f"{path}: eval checkpoint contract failed")
    require(config.get("num_envs") == EPISODES and config.get("seed") == seed, f"{path}: exact64/seed contract failed")
    require(eval_cfg.get("num_eval_episodes") == EPISODES and eval_cfg.get("eval_num_envs_episodes") is True, f"{path}: first-episode contract failed")
    require(env_cfg.get("enable_staged_reset") is False and env_cfg.get("a2_v26_door_open_lr") == side, f"{path}: natural side contract failed")
    require(env_cfg.get("a2_v26_side_permutation_seed") == seed, f"{path}: side permutation seed mismatch")
    require(env_cfg.get("a2_v26_4_side_canonicalization_enabled") is False, f"{path}: canonicalization must be off")
    expected_geometry = factor.startswith("O1")
    expected_rebase = factor.endswith("A1")
    require(env_cfg.get("a2_v26_5_geometry_target_enabled") is expected_geometry, f"{path}: geometry factor mismatch")
    require(env_cfg.get("a2_v26_5_stage3_delta_rebase_enabled") is expected_rebase, f"{path}: rebase factor mismatch")
    require(metadata.get("forced_gripper_close_enabled") is False and metadata.get("stage2_close_gate_forced_gripper_close_enabled") is False, f"{path}: intervention contaminates natural eval")
    terminal, records_by_env, max_stage = terminal_by_env(metrics, records, path)
    traces: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for index, row in enumerate(trace):
        require(isinstance(row, dict) and row.get("first_episode_active") is True and row.get("episode_index") == 0, f"{path}: trace row {index} is not a first-episode mapping")
        env_id = row.get("env_id")
        require(isinstance(env_id, int) and 0 <= env_id < EPISODES, f"{path}: trace env id invalid")
        traces[env_id].append(row)
    require(set(traces) == set(range(EPISODES)), f"{path}: trace does not cover exact64 episodes")
    k5_episodes = 0; stage3_admission = 0; contact_steps = 0; stable_steps = 0; integrity = 0
    highwater: list[float] = []; sustained: dict[int, float] = {}; hinge_01 = 0; hinge_025 = 0
    stage4 = 0; stage5 = 0; goal = 0
    for env_id in range(EPISODES):
        term = terminal[env_id]; v2 = term.get("v26_2"); v3 = term.get("v26_3")
        require(isinstance(v2, dict) and isinstance(v3, dict), f"{path}: v26 telemetry missing env{env_id}")
        highwater.append(finite(v3.get("handle_highwater"), f"{path}: highwater env{env_id}"))
        k5_episodes += int(int(v2.get("k5_steps", -1)) >= 5)
        stage3_admission += int(max_stage[env_id] >= 3)
        integrity += int(finite(v2.get("integrity_violations"), f"{path}: v2 integrity")) + int(finite(v3.get("integrity_violations"), f"{path}: v3 integrity"))
        stage4 += int(max_stage[env_id] >= 4); stage5 += int(max_stage[env_id] >= 5); goal += int(records_by_env[env_id].get("goal_reached") is True)
        rows = sorted(traces[env_id], key=lambda row: row.get("step_index", -1))
        previous = None; run = 0; sustained_event = None; first_stage3_strict_k5 = None; max_hinge = -math.inf
        for row in rows:
            step = row.get("step_index")
            require(isinstance(step, int) and step >= 0 and (previous is None or step == previous + 1), f"{path}: trace step topology invalid env{env_id}")
            previous = step
            v2_trace = row.get("v26_2")
            require(isinstance(v2_trace, dict), f"{path}: trace v26_2 missing env{env_id}")
            handle = finite(row.get("door_handle_joint_pos"), f"{path}: handle env{env_id}")
            hinge = finite(row.get("door_hinge_joint_pos"), f"{path}: hinge env{env_id}")
            max_hinge = max(max_hinge, hinge)
            if row.get("stage_buf") == 3:
                stability = row.get("contact_stability")
                require(isinstance(stability, bool), f"{path}: contact stability invalid env{env_id}")
                contact_steps += 1; stable_steps += int(stability)
            qualifying = row.get("stage_buf") == 3 and handle >= 0.1 and v2_trace.get("strict_k5") is True
            if row.get("stage_buf") == 3 and v2_trace.get("strict_k5") is True and first_stage3_strict_k5 is None:
                first_stage3_strict_k5 = step
            run = run + 1 if qualifying else 0
            if run >= 5 and sustained_event is None:
                if first_stage3_strict_k5 is None:
                    raise RuntimeError(f"{path}: sustained Stage3 event lacks its strict-K5 start env{env_id}")
                control_steps = step - first_stage3_strict_k5 + 1
                control_dt = finite(row.get("control_dt"), f"{path}: control dt env{env_id}")
                sustained_event = {"first_stage3_strict_k5_step_index": first_stage3_strict_k5, "first_sustained_event_step_index": step, "control_steps": control_steps, "seconds": control_steps * control_dt}
        if sustained_event is not None:
            sustained[env_id] = sustained_event
        hinge_01 += int(max_hinge >= 0.1); hinge_025 += int(max_hinge >= 0.25)
    return {
        "episodes": EPISODES, "Stage3_admission_count": stage3_admission, "Stage3_admission_rate": stage3_admission / EPISODES, "K5_episode_count": k5_episodes, "K5_episode_rate": k5_episodes / EPISODES,
        "contact_stability_steps": {"numerator": stable_steps, "denominator": contact_steps, "rate": None if contact_steps == 0 else stable_steps / contact_steps},
        "handle_highwater_rad": max(highwater), "sustained_handle_ge_0_1_current_K5_ge_5": {"predicate": "stage_buf==3 and door_handle_joint_pos>=0.1 and v26_2.strict_k5 for five contiguous control steps", "episode_count": len(sustained), "episode_rate": len(sustained) / EPISODES, "TTE_from_first_stage3_strict_K5": None if not sustained else {"control_steps": {"min": min(value["control_steps"] for value in sustained.values()), "mean": sum(value["control_steps"] for value in sustained.values()) / len(sustained)}, "seconds": {"min": min(value["seconds"] for value in sustained.values()), "mean": sum(value["seconds"] for value in sustained.values()) / len(sustained)}, "per_env": sustained}},
        "hinge_episode_rate": {"ge_0_1": hinge_01 / EPISODES, "ge_0_25": hinge_025 / EPISODES},
        "stage_episode_count": {"stage4": stage4, "stage5": stage5, "goal": goal}, "integrity_violations": integrity,
        "provenance": {"checkpoint": config.get("checkpoint"), "trace_filename": "stage2_5_step_trace.json", "matched_prefix_not_snapshot_clone": factor == "O0A1"},
    }


def bilateral(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    require(left["integrity_violations"] == right["integrity_violations"] == 0, "integrity violations prevent Wave1 claim")
    return {
        "K5_rate_gap": abs(left["K5_episode_rate"] - right["K5_episode_rate"]),
        "contact_rate_gap": None if left["contact_stability_steps"]["rate"] is None or right["contact_stability_steps"]["rate"] is None else abs(left["contact_stability_steps"]["rate"] - right["contact_stability_steps"]["rate"]),
        "handle_highwater_ratio": None if right["handle_highwater_rad"] == 0.0 else left["handle_highwater_rad"] / right["handle_highwater_rad"],
        "sustained_rate_gap": abs(left["sustained_handle_ge_0_1_current_K5_ge_5"]["episode_rate"] - right["sustained_handle_ge_0_1_current_K5_ge_5"]["episode_rate"]),
        "stage4_bilateral_episodes": min(left["stage_episode_count"]["stage4"], right["stage_episode_count"]["stage4"]),
        "stage5_bilateral_episodes": min(left["stage_episode_count"]["stage5"], right["stage_episode_count"]["stage5"]),
        "goal_bilateral_episodes": min(left["stage_episode_count"]["goal"], right["stage_episode_count"]["goal"]),
    }


def typed(formal: dict[str, dict[str, dict[str, Any]]], factor: str) -> str:
    pairs = [formal[factor][f"seed{seed}"]["bilateral"] for seed in (0, 1)]
    if all(pair["goal_bilateral_episodes"] > 0 for pair in pairs):
        return "PROMOTE_BILATERAL_POLICY_GOAL"
    if all(pair["stage5_bilateral_episodes"] > 0 for pair in pairs):
        return "PROMOTE_BILATERAL_STAGE5_CONTINUE_TO_GOAL"
    if all(pair["stage4_bilateral_episodes"] > 0 for pair in pairs):
        return "PROMOTE_BILATERAL_STAGE4_CONTINUE"
    seeds = [formal[factor][f"seed{seed}"] for seed in (0, 1)]
    if any(side["Stage3_admission_count"] < 16 for seed in seeds for side in (seed["left"], seed["right"])):
        return "ACQUISITION_INCONCLUSIVE"
    if all(
        side["sustained_handle_ge_0_1_current_K5_ge_5"]["episode_count"] >= 2
        and side["contact_stability_steps"]["rate"] is not None
        and side["contact_stability_steps"]["rate"] >= 0.90
        and side["integrity_violations"] == 0
        for seed in seeds for side in (seed["left"], seed["right"])
    ):
        return "PROMOTE_BILATERAL_SUSTAINED_DEPRESSION_RELAY"
    return "KILL_NO_BILATERAL_STAGE4_CONTACT_ALONE_INSUFFICIENT"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--formal-eval-root", type=Path, required=True)
    parser.add_argument("--diagnostic-eval-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), f"refusing to overwrite Wave1 reducer: {args.output}")
    formal: dict[str, dict[str, dict[str, Any]]] = {"O1A0": {}, "O1A1": {}}
    for factor, seed in FORMAL:
        label = f"{factor}_S{seed}_STEP0750"
        sides = {side: load_side(args.formal_eval_root / label / side, side, seed, factor) for side in SIDES}
        formal[factor][f"seed{seed}"] = {**sides, "bilateral": bilateral(sides["left"], sides["right"])}
    diagnostic: dict[str, Any] = {}
    for seed in (0, 1):
        label = f"O0A1_DIAG_R2_C0_S{seed}_STEP0750"
        sides = {side: load_side(args.diagnostic_eval_root / label / side, side, seed, "O0A1") for side in SIDES}
        diagnostic[f"seed{seed}"] = {**sides, "bilateral": bilateral(sides["left"], sides["right"]), "typed": "DIAGNOSTIC_MATCHED_PREFIX_NOT_SNAPSHOT_CLONE"}
    payload = {"schema": "a2_piper_base_v26_5_wave1_reducer_v1", "status": "EXPERIMENT_COMPLETE", "episodes_per_side": EPISODES, "formal": formal, "O0A1_diagnostic": diagnostic, "typed_outcome": {"O1A0": typed(formal, "O1A0"), "O1A1": typed(formal, "O1A1")}, "promotion_rule": "policy-generated bilateral Stage4/5/goal only; contact alone cannot promote"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
