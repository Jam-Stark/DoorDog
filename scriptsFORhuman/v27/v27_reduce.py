#!/usr/bin/env python3
"""Reduce one manifest of exact-N bilateral base_v27 evaluation lanes.

The reducer is deliberately an artifact reader.  It never amends evaluator
artifacts, and marks only the affected cell ``V27_INVALID`` when a lane's
contract or telemetry is invalid.
"""
from __future__ import annotations

import argparse
import collections
import json
import math
from pathlib import Path
from typing import Any

import yaml


SCHEMA = "a2_piper_base_v27_reducer_v1"
MANIFEST_SCHEMA = "a2_piper_base_v27_eval_manifest_v1"
SIDES = ("left", "right")
HOLD_STEPS = 25
DURABLE_RAD = 0.6
OPEN_HOLD_RAD = 0.25
CROSSING_HINGE_RAD = 1.0472


class ReducerError(RuntimeError):
    """A declared evaluation artifact or contract is invalid."""


def require(value: bool, message: str) -> None:
    if not value:
        raise ReducerError(message)


def load_json(path: Path) -> Any:
    require(path.is_file(), f"missing artifact: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def iter_json_array(path: Path):
    """Yield a JSON array without materializing an exact-N step trace."""
    decoder = json.JSONDecoder()
    buffer = ""
    started = False
    finished = False
    with path.open(encoding="utf-8") as handle:
        while not finished:
            chunk = handle.read(1 << 20)
            if chunk:
                buffer += chunk
            elif not buffer.strip():
                break
            while True:
                buffer = buffer.lstrip()
                if not started:
                    if not buffer:
                        break
                    require(buffer.startswith("["), f"trace array: {path}")
                    started = True
                    buffer = buffer[1:]
                    continue
                if not buffer:
                    break
                if buffer.startswith("]"):
                    finished = True
                    buffer = buffer[1:].strip()
                    require(not buffer or not chunk, f"trailing trace payload: {path}")
                    break
                try:
                    value, offset = decoder.raw_decode(buffer)
                except json.JSONDecodeError:
                    require(bool(chunk), f"invalid trace JSON: {path}")
                    break
                yield value
                buffer = buffer[offset:].lstrip()
                if buffer.startswith(","):
                    buffer = buffer[1:]
                elif buffer.startswith("]"):
                    continue
                elif buffer:
                    raise ReducerError(f"trace delimiter: {path}")
            if not chunk:
                break
    require(started and finished, f"incomplete trace array: {path}")


def trace_reach_counts(path: Path, expected_n: int) -> dict[str, Any]:
    durable_run = [0] * expected_n
    durable_best = [0] * expected_n
    open_run = [0] * expected_n
    open_best = [0] * expected_n
    previous_steps: list[int | None] = [None] * expected_n
    seen = [False] * expected_n
    stage3_seen = [False] * expected_n
    stage3_body_force_max: list[float | None] = [None] * expected_n
    first_crossing_hinge: list[float | None] = [None] * expected_n
    crossing_while_holding: list[bool | None] = [None] * expected_n
    arm_j4_limit_steps = 0
    trace_steps = 0
    for index, row in enumerate(iter_json_array(path)):
        require(isinstance(row, dict), f"trace row {index}")
        require(row.get("first_episode_active") is True and row.get("episode_index") == 0, f"trace first-episode contract row {index}")
        env_id = row.get("env_id")
        require(isinstance(env_id, int) and 0 <= env_id < expected_n, f"trace env id row {index}")
        step = row.get("step_index")
        require(isinstance(step, int) and step >= 0 and (previous_steps[env_id] is None or step == previous_steps[env_id] + 1), f"trace step order env{env_id}")
        previous_steps[env_id] = step
        seen[env_id] = True
        durable_active = finite_number(row.get("door_handle_joint_pos"), f"trace handle env{env_id}") >= DURABLE_RAD
        open_active = finite_number(row.get("door_hinge_joint_pos"), f"trace hinge env{env_id}") >= OPEN_HOLD_RAD and row.get("both_contact") is True
        durable_run[env_id] = durable_run[env_id] + 1 if durable_active else 0
        open_run[env_id] = open_run[env_id] + 1 if open_active else 0
        durable_best[env_id] = max(durable_best[env_id], durable_run[env_id])
        open_best[env_id] = max(open_best[env_id], open_run[env_id])
        if nonnegative_int(row.get("stage_buf"), f"trace stage env{env_id}") >= 3:
            stage3_seen[env_id] = True
        if stage3_seen[env_id]:
            body_force = finite_number(row.get("door_body_panel_normal_force_total"), f"trace body force env{env_id}")
            stage3_body_force_max[env_id] = body_force if stage3_body_force_max[env_id] is None else max(stage3_body_force_max[env_id], body_force)
        crossed = row.get("root_x_ever_crossed")
        require(isinstance(crossed, bool), f"trace crossing flag env{env_id}")
        if crossed and first_crossing_hinge[env_id] is None:
            first_crossing_hinge[env_id] = finite_number(row.get("door_hinge_joint_pos"), f"trace first crossing hinge env{env_id}")
            holding = row.get("crossing_while_holding")
            require(isinstance(holding, bool), f"trace crossing holding env{env_id}")
            crossing_while_holding[env_id] = holding
        names, positions = row.get("arm_joint_names"), row.get("arm_joint_pos")
        require(names == ["arm_j1", "arm_j2", "arm_j3", "arm_j4", "arm_j5", "arm_j6"] and isinstance(positions, list) and len(positions) == 6, f"trace arm_j4 contract env{env_id}")
        arm_j4_limit_steps += int(abs(1.745 - finite_number(positions[3], f"trace arm_j4 env{env_id}")) < 1e-3)
        trace_steps += 1
    return {
        "trace_seen": seen,
        "D": sum(value >= HOLD_STEPS for value in durable_best),
        "open_hold": sum(value >= HOLD_STEPS for value in open_best),
        "first_crossing_hinge": first_crossing_hinge,
        "crossing_while_holding": crossing_while_holding,
        "stage3_body_force_max": stage3_body_force_max,
        "arm_j4_limit_residence_step_share": None if trace_steps == 0 else arm_j4_limit_steps / trace_steps,
    }


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[math.ceil(fraction * len(ordered)) - 1]


def finite_number(value: Any, name: str) -> float:
    require(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)), name)
    return float(value)


def nonnegative_int(value: Any, name: str) -> int:
    require(isinstance(value, int) and not isinstance(value, bool) and value >= 0, name)
    return value


def resolve_dot(mapping: dict[str, Any], dotted: str) -> Any:
    value: Any = mapping
    for part in dotted.split("."):
        require(isinstance(value, dict) and part in value, f"runtime contract missing {dotted}")
        value = value[part]
    return value


def lane_runtime_contract(lane: dict[str, Any], artifact_path: Path) -> dict[str, Any]:
    path_value = lane.get("runtime_config_path")
    runtime_path = Path(path_value) if path_value is not None else artifact_path / ".hydra" / "runtime_config.yaml"
    require(runtime_path.is_file(), f"missing runtime config: {runtime_path}")
    runtime = yaml.load(runtime_path.read_text(encoding="utf-8"), Loader=yaml.UnsafeLoader)
    require(isinstance(runtime, dict), f"runtime config mapping: {runtime_path}")
    return runtime


def validate_runtime_contract(lane: dict[str, Any], artifact_path: Path) -> dict[str, Any]:
    """Validate the universal natural-evaluation contract and caller additions."""
    if lane.get("historical") is True:
        return {"historical": True}
    runtime = lane_runtime_contract(lane, artifact_path)
    episodes = lane["episodes"]
    expected = {
        "seed": lane["seed"],
        "checkpoint": lane["checkpoint"],
        "checkpoint_load_mode": "full",
        "auto_load_latest": False,
        "num_envs": episodes,
        "algo.config.eval.num_eval_episodes": episodes,
        "algo.config.eval.eval_num_envs_episodes": True,
        "env.config.a2_v26_door_open_lr": lane["side"],
        "env.config.enable_staged_reset": False,
        "rewards.reward_penalty_curriculum": False,
        "env.config.a2_v26_8_penalty_driver": None,
    }
    supplied = lane.get("expected_contract", {})
    require(isinstance(supplied, dict), "expected_contract mapping")
    expected.update(supplied)
    for key, wanted in expected.items():
        actual = resolve_dot(runtime, key)
        require(actual == wanted, f"runtime contract {key}: {actual!r} != {wanted!r}")
    return expected


def terminal_rows(metrics: dict[str, Any], expected_n: int, side: str) -> dict[int, dict[str, Any]]:
    diagnostics = metrics.get("episode_terminal_diagnostics")
    terminal_reasons = metrics.get("episode_terminal_reasons")
    stages = metrics.get("episode_max_stage_reached")
    require(metrics.get("completed_episodes") == expected_n, "completed_episodes exact N")
    require(isinstance(diagnostics, list) and isinstance(terminal_reasons, list) and isinstance(stages, list), "terminal arrays")
    require(len(diagnostics) == len(terminal_reasons) == len(stages) == expected_n, "terminal arrays exact N")
    terminals: dict[int, dict[str, Any]] = {}
    for diagnostic, reason, stage in zip(diagnostics, terminal_reasons, stages, strict=True):
        require(isinstance(diagnostic, dict) and isinstance(reason, str) and isinstance(stage, int), "terminal row schema")
        env_id = diagnostic.get("env_id")
        require(isinstance(env_id, int) and 0 <= env_id < expected_n and env_id not in terminals, "terminal env-id coverage")
        require(diagnostic.get("door_handle_side") == side, f"terminal {env_id} side")
        row = dict(diagnostic)
        row["terminal_reasons"] = reason
        row["max_stage"] = stage
        terminals[env_id] = row
    require(set(terminals) == set(range(expected_n)), "terminal complete env-id coverage")
    return terminals


def v26_integrity(row: dict[str, Any], *, require_both: bool) -> int:
    total = 0
    for key in ("v26_2", "v26_3"):
        value = row.get(key)
        if value is None:
            require(not require_both, f"{key} terminal telemetry")
            continue
        require(isinstance(value, dict), f"{key} telemetry")
        total += nonnegative_int(value.get("integrity_violations"), f"{key}.integrity_violations")
    return total


def standard_v27(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("a2_v27")
    require(isinstance(value, dict), "a2_v27 terminal telemetry")
    body_force = finite_number(value.get("body_panel_force_max_from_stage3_n"), "a2_v27.body_panel_force_max_from_stage3_n")
    limit_steps = nonnegative_int(value.get("arm_j4_limit_residence_steps"), "a2_v27.arm_j4_limit_residence_steps")
    total_steps = nonnegative_int(value.get("first_episode_control_steps"), "a2_v27.first_episode_control_steps")
    require(total_steps > 0 and limit_steps <= total_steps, "a2_v27 arm_j4 residence denominator")
    integrity = nonnegative_int(value.get("integrity_violations"), "a2_v27.integrity_violations")
    crossing = value.get("crossing_while_holding", row.get("crossing_while_holding"))
    require(crossing is None or isinstance(crossing, bool), "crossing_while_holding bool|null")
    hinge = value.get("first_crossing_hinge_rad", row.get("hinge_at_crossing"))
    require(hinge is None or (isinstance(hinge, (int, float)) and not isinstance(hinge, bool) and math.isfinite(float(hinge))), "first_crossing_hinge_rad finite|null")
    return {
        "body_panel_force_max_from_stage3_n": body_force,
        "arm_j4_limit_residence_steps": limit_steps,
        "first_episode_control_steps": total_steps,
        "integrity_violations": integrity,
        "crossing_while_holding": crossing,
        "first_crossing_hinge_rad": None if hinge is None else float(hinge),
    }


def recovery_telemetry(row: dict[str, Any]) -> dict[str, Any]:
    telemetry = row["a2_v27"]
    status = telemetry.get("injection_status")
    require(status in {"TRIGGERED", "NOT_TRIGGERED"}, "a2_v27.injection_status")
    values: dict[str, Any] = {"injection_status": status}
    for key in ("loss_event", "regrasp_success", "recovered_complete", "recovered_clean_complete"):
        value = telemetry.get(key)
        require(isinstance(value, bool), f"a2_v27.{key} bool")
        values[key] = value
    return values


def summary_for_lane(lane: dict[str, Any], expected_n: int) -> dict[str, Any]:
    artifact_path = Path(lane["artifact_path"])
    require(artifact_path.is_dir(), f"artifact path: {artifact_path}")
    historical = lane.get("historical") is True
    runtime_contract = validate_runtime_contract(lane, artifact_path)
    metrics = load_json(artifact_path / "metrics_eval.json")
    require(isinstance(metrics, dict), "metrics_eval mapping")
    trace_path = artifact_path / "stage2_5_step_trace.json"
    require(trace_path.is_file() and trace_path.stat().st_size > 0, f"trace artifact: {trace_path}")
    trace_counts = trace_reach_counts(trace_path, expected_n)
    terminals = terminal_rows(metrics, expected_n, lane["side"])
    require(all(trace_counts["trace_seen"][env_id] or row["max_stage"] < 2
                for env_id, row in terminals.items()), "missing trace for episode that reached Stage2")
    rows = list(terminals.values())
    for row in rows:
        v26_integrity(row, require_both=not historical)

    for row in rows:
        v26_2 = row.get("v26_2")
        require(isinstance(v26_2, dict), "v26_2 terminal telemetry")

    complete_rows = [row for row in rows if row["terminal_reasons"] == "complete"]
    terminal_reason_counts = dict(collections.Counter(row["terminal_reasons"] for row in rows))
    summary: dict[str, Any] = {
        "episodes": expected_n,
        "D": trace_counts["D"],
        "S3+": sum(row["max_stage"] >= 3 for row in rows),
        "S4+": sum(row["max_stage"] >= 4 for row in rows),
        "open_hold": trace_counts["open_hold"],
        "S5+": sum(row["max_stage"] >= 5 for row in rows),
        "complete": len(complete_rows),
        "clean_complete": None,
        "hold_through": None,
        "crossing_while_holding": None,
        "post_release_body_force_p95": percentile([
            finite_number(row["post_release_body_force_max"], "post_release_body_force_max")
            for row in rows
            if row.get("post_release_body_force_max") is not None
        ], .95),
        "first_crossing_hinge_p50": None,
        "episode_length_p50": percentile([
            finite_number(row.get("episode_length_buf"), "episode_length_buf") for row in rows
        ], .5),
        "arm_j4_limit_residence_step_share": None,
        "terminal_reasons": terminal_reason_counts,
        "integrity_violations": sum(v26_integrity(row, require_both=not historical) for row in rows),
        "runtime_contract": runtime_contract,
    }
    if historical:
        clean_complete = 0
        crossing_hinges: list[float] = []
        hold_through = 0
        for env_id, row in terminals.items():
            hinge = trace_counts["first_crossing_hinge"][env_id]
            holding = trace_counts["crossing_while_holding"][env_id]
            if hinge is not None:
                crossing_hinges.append(hinge)
            hold_through += int(holding is True)
            if row["terminal_reasons"] == "complete":
                body_force = trace_counts["stage3_body_force_max"][env_id]
                require(hinge is not None and body_force is not None, f"historical clean telemetry env{env_id}")
                clean_complete += int(
                    hinge >= CROSSING_HINGE_RAD
                    and body_force <= 5.0
                    and row["terminal_reasons"] not in {"low_height", "upper_dof_overspeed"}
                )
        summary.update({
            "clean_complete": clean_complete,
            "clean_complete_available": True,
            "hold_through": hold_through,
            "crossing_while_holding": hold_through,
            "first_crossing_hinge_p50": percentile(crossing_hinges, .5),
            "arm_j4_limit_residence_step_share": trace_counts["arm_j4_limit_residence_step_share"],
        })
        require(summary["integrity_violations"] == 0, "integrity_violations")
        return summary

    v27_rows = {env_id: standard_v27(row) for env_id, row in terminals.items()}
    clean_complete = 0
    hold_through = 0
    crossing_hinges: list[float] = []
    limit_steps = 0
    total_steps = 0
    for env_id, row in terminals.items():
        v27 = v27_rows[env_id]
        limit_steps += v27["arm_j4_limit_residence_steps"]
        total_steps += v27["first_episode_control_steps"]
        summary["integrity_violations"] += v27["integrity_violations"]
        if v27["crossing_while_holding"] is True:
            hold_through += 1
        if v27["first_crossing_hinge_rad"] is not None:
            crossing_hinges.append(v27["first_crossing_hinge_rad"])
        if row["terminal_reasons"] == "complete":
            clean = (
                v27["first_crossing_hinge_rad"] is not None
                and v27["first_crossing_hinge_rad"] >= CROSSING_HINGE_RAD
                and v27["body_panel_force_max_from_stage3_n"] <= 5.0
                and row["terminal_reasons"] not in {"low_height", "upper_dof_overspeed"}
            )
            clean_complete += int(clean)
    summary.update({
        "clean_complete": clean_complete,
        "clean_complete_available": True,
        "hold_through": hold_through,
        "crossing_while_holding": hold_through,
        "first_crossing_hinge_p50": percentile(crossing_hinges, .5),
        "arm_j4_limit_residence_step_share": limit_steps / total_steps,
    })
    if lane.get("recovery_itt") is True:
        recovery_rows = [recovery_telemetry(row) for row in rows]
        require(all(row["a2_v27"].get("recovery_itt") is True for row in rows), "a2_v27.recovery_itt")
        recovery_summary = {
            "denominator": expected_n,
            "loss_events": sum(item["loss_event"] for item in recovery_rows),
            "not_triggered": sum(item["injection_status"] == "NOT_TRIGGERED" for item in recovery_rows),
            "regrasp_success": sum(item["regrasp_success"] for item in recovery_rows),
            "recovered_complete": sum(item["recovered_complete"] for item in recovery_rows),
            "recovered_clean_complete": sum(item["recovered_clean_complete"] for item in recovery_rows),
        }
        summary["recovery_itt"] = recovery_summary
        summary.update({
            "itt_denominator": recovery_summary["denominator"],
            "loss_events": recovery_summary["loss_events"],
            "not_triggered": recovery_summary["not_triggered"],
            "regrasp_success": recovery_summary["regrasp_success"],
            "recovered_complete": recovery_summary["recovered_complete"],
            "recovered_clean_complete": recovery_summary["recovered_clean_complete"],
        })
    require(summary["integrity_violations"] == 0, "integrity_violations")
    return summary


def passes_gate(summary: dict[str, Any]) -> bool:
    n = summary["episodes"]
    if summary.get("clean_complete") is None:
        return False
    if n == 64:
        return summary["complete"] >= 60 and summary["clean_complete"] >= 56 and sum(summary["terminal_reasons"].get(key, 0) for key in ("low_height", "upper_dof_overspeed")) <= 2
    if n == 128:
        return summary["complete"] >= 120 and summary["clean_complete"] >= 112 and sum(summary["terminal_reasons"].get(key, 0) for key in ("low_height", "upper_dof_overspeed")) <= 4
    raise ReducerError(f"no preregistered engineering gate for N={n}")


def no_regress(candidate: dict[str, dict[str, Any]], control: dict[str, dict[str, Any]]) -> bool:
    return all(candidate[side]["complete"] >= control[side]["complete"] - 4 and candidate[side]["D"] >= control[side]["D"] - 8 and candidate[side]["S4+"] >= control[side]["S4+"] - 8 for side in SIDES)


def _cell_sides(cells: dict[str, Any], cell: str, stratum: str | None = None) -> dict[str, dict[str, Any]] | None:
    source = cells.get(cell)
    if not isinstance(source, dict):
        return None
    if stratum is not None:
        source = source.get(stratum)
    elif len(source) == 1:
        source = next(iter(source.values()))
    else:
        return None
    if not isinstance(source, dict) or set(source) != set(SIDES):
        return None
    return source


def qualification_outcome(cells: dict[str, Any]) -> dict[str, Any]:
    candidates = {name: _cell_sides(cells, f"{name}_S2", "DEV") for name in ("C", "W", "K")}
    if any(value is None for value in candidates.values()):
        return {"outcome": "UNRESOLVED", "selected_candidate": None}
    selected = next((name for name in ("C", "W", "K") if all(passes_gate(candidates[name][side]) for side in SIDES)), None)
    if selected is None:
        return {"outcome": "NO_QUALIFIED_CANDIDATE", "selected_candidate": None}
    confirm = _cell_sides(cells, f"{selected}_S2", "CONF")
    if confirm is None:
        return {"outcome": "DEV_SELECTED", "selected_candidate": selected}
    return {"outcome": "BILATERAL_TEACHER_QUALIFIED_SIM" if all(passes_gate(confirm[side]) for side in SIDES) else "QUALIFICATION_NOT_CONFIRMED", "selected_candidate": selected}


def wave_a_outcome(cells: dict[str, Any]) -> dict[str, Any]:
    controls = [_cell_sides(cells, f"C_S2{seed}", "nominal") for seed in (1, 2)]
    arms = {arm: [_cell_sides(cells, f"{arm}_S2{seed}", "nominal") for seed in (1, 2)] for arm in ("Q1", "Q2")}
    if any(value is None for value in controls) or any(value is None for values in arms.values() for value in values):
        return {"outcome": "UNRESOLVED", "recipe_a": None, "labels": []}
    if all(all(passes_gate(side) for side in control.values()) for control in controls):
        outcome, recipe = "QUALITY_ALREADY_PASS", "C"
    else:
        recipe = "C"
        outcome = "QUALITY_UNRESOLVED"
        for arm in ("Q1", "Q2"):
            mean_left_clean_delta = sum(candidate["left"]["clean_complete"] - control["left"]["clean_complete"] for candidate, control in zip(arms[arm], controls, strict=True)) / 2
            if all(all(passes_gate(side) for side in candidate.values()) and no_regress(candidate, control) for candidate, control in zip(arms[arm], controls, strict=True)) and mean_left_clean_delta >= 8:
                outcome, recipe = f"QUALITY_ALIGNED({arm})", arm
                break
    labels = ["Q_HARMFUL_RIGHT" for arm in ("Q1", "Q2") if any(candidate["right"]["complete"] <= control["right"]["complete"] - 8 for candidate, control in zip(arms[arm], controls, strict=True))]
    return {"outcome": outcome, "recipe_a": recipe, "carrier_a": f"{recipe}_S21", "labels": labels}


def wave_b_domain_outcome(cells: dict[str, Any]) -> dict[str, Any]:
    l0 = _cell_sides(cells, "L0_S31", "nominal")
    l1 = [{stratum: _cell_sides(cells, f"L1_S3{seed}", stratum) for stratum in ("nominal", "P02", "P05")} for seed in (1, 2)]
    if l0 is None or any(value is None for seed in l1 for value in seed.values()):
        return {"outcome": "UNRESOLVED", "recipe_b": None}
    all_layers = all(all(passes_gate(side) for side in seed[stratum].values()) for seed in l1 for stratum in ("nominal", "P02", "P05"))
    nominal_no_regress = all(seed["nominal"][side]["complete"] >= l0[side]["complete"] - 4 for seed in l1 for side in SIDES)
    if all_layers and nominal_no_regress:
        return {"outcome": "DOMAIN_CONVERGED", "recipe_b": "L1"}
    partial = all(all(passes_gate(side) for side in seed[stratum].values()) for seed in l1 for stratum in ("nominal", "P02")) and nominal_no_regress and not all(all(passes_gate(side) for side in seed["P05"].values()) for seed in l1)
    return {"outcome": "DOMAIN_PARTIAL" if partial else "DOMAIN_NOT_CONVERGED", "recipe_b": "L1" if partial else "CURRENT_DOMAIN"}


def recovery_outcome(cells: dict[str, Any]) -> dict[str, Any]:
    nominal = {arm: _cell_sides(cells, f"{arm}_S41", "nominal") for arm in ("R0", "R1", "R2")}
    injected = {arm: _cell_sides(cells, f"{arm}_S41", "injected") for arm in ("R1", "R2")}
    if any(value is None for value in nominal.values()) or any(value is None for value in injected.values()):
        return {"outcome": "UNRESOLVED"}
    def itts(arm: str, side: str) -> dict[str, Any]:
        value = injected[arm][side].get("recovery_itt")
        require(isinstance(value, dict) and value.get("denominator") == injected[arm][side]["episodes"], f"{arm}/{side} recovery ITT")
        return value
    if any(nominal[arm][side]["complete"] <= nominal["R0"][side]["complete"] - 8 for arm in ("R1", "R2") for side in SIDES):
        return {"outcome": "RECOVERY_HARMFUL"}
    r2_promising = all(itts("R2", side)["regrasp_success"] >= 32 and itts("R2", side)["recovered_clean_complete"] >= 16 and itts("R2", side)["regrasp_success"] - itts("R1", side)["regrasp_success"] >= 8 and nominal["R2"][side]["complete"] >= nominal["R0"][side]["complete"] - 4 for side in SIDES)
    if r2_promising:
        return {"outcome": "RECOVERY_PILOT_PROMISING"}
    r1_runtime = all(itts("R1", side)["regrasp_success"] >= 32 and itts("R1", side)["recovered_clean_complete"] >= 16 and itts("R2", side)["regrasp_success"] - itts("R1", side)["regrasp_success"] < 8 for side in SIDES)
    if r1_runtime:
        return {"outcome": "RECOVERY_RUNTIME_ONLY"}
    if all(itts(arm, side)["regrasp_success"] < 32 for arm in ("R1", "R2") for side in SIDES):
        return {"outcome": "RECOVERY_NO_BENEFIT"}
    return {"outcome": "UNRESOLVED"}


def _all_strata_pass(cells: dict[str, Any], cell: str) -> bool | None:
    strata = cells.get(cell)
    if not isinstance(strata, dict) or not strata:
        return None
    for side_summaries in strata.values():
        if not isinstance(side_summaries, dict) or set(side_summaries) != set(SIDES):
            return None
        if not all(passes_gate(side_summaries[side]) for side in SIDES):
            return False
    return True


def _wave_c_guard(cells: dict[str, Any], sk_cell: str, sc_cell: str) -> bool:
    sk_strata, sc_strata = cells[sk_cell], cells[sc_cell]
    if set(sk_strata) != set(sc_strata):
        return False
    return all(sk_strata[stratum][side][metric] >= sc_strata[stratum][side][metric] - 8 for stratum in sc_strata for side in SIDES for metric in ("S4+", "open_hold"))


def _first_wave_c_gate(history: list[dict[str, Any]], cell: str) -> int | None:
    for payload in history:
        if not isinstance(payload, dict):
            raise ReducerError("wave-c history entry")
        step = payload.get("step")
        historical_cells = payload.get("cells")
        require(isinstance(historical_cells, dict), "wave-c history cells")
        if isinstance(step, int) and _all_strata_pass(historical_cells, cell) is True:
            return step
    return None


def wave_c_outcome(cells: dict[str, Any], history: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    sc_cells = [f"SC_S{seed}" for seed in (201, 202, 203)]
    sk_cells = [f"SK_S{seed}" for seed in (211, 212, 213)]
    sc = [_all_strata_pass(cells, cell) for cell in sc_cells]
    sk = [_all_strata_pass(cells, cell) for cell in sk_cells]
    if any(value is None for value in sc) or any(value is None for value in sk):
        return {"sc_outcome": "UNRESOLVED", "sk_outcome": "UNRESOLVED"}
    sc_passes = sum(sc)
    sc_outcome = "SCRATCH_3SEED_ESTABLISHED" if sc_passes == 3 else "SCRATCH_SEED_UNSTABLE" if sc_passes else "SCRATCH_NOT_ESTABLISHED"
    sk_passes = sum(sk)
    paired_guard = all(_wave_c_guard(cells, sk_cell, sc_cell) for sk_cell, sc_cell in zip(sk_cells, sc_cells, strict=True))
    if sk_passes > sc_passes and paired_guard:
        sk_outcome = "K_SCRATCH_SUPERIOR"
    elif sk_passes == sc_passes and paired_guard and history is not None and sum(
        _first_wave_c_gate(history, sc_cell) is not None
        and _first_wave_c_gate(history, sk_cell) is not None
        and _first_wave_c_gate(history, sc_cell) - _first_wave_c_gate(history, sk_cell) >= 1000
        for sk_cell, sc_cell in zip(sk_cells, sc_cells, strict=True)
    ) >= 2:
        sk_outcome = "K_SCRATCH_SUPERIOR"
    elif sk_passes == sc_passes and paired_guard:
        sk_outcome = "K_SCRATCH_NONINFERIOR"
    else:
        sk_outcome = "K_SCRATCH_INFERIOR"
    return {"sc_outcome": sc_outcome, "sk_outcome": sk_outcome, "sc_passed_seeds": sc_passes, "sk_passed_seeds": sk_passes}


def typed_outcomes(cells: dict[str, Any], wave_c_history: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "qualification": qualification_outcome(cells),
        "wave_a": wave_a_outcome(cells),
        "wave_b_domain": wave_b_domain_outcome(cells),
        "recovery": recovery_outcome(cells),
        "wave_c": wave_c_outcome(cells, wave_c_history),
    }


def validate_lane_identity(lane: dict[str, Any], expected_n: int) -> tuple[str, str, str]:
    required = {"cell", "stratum", "side", "seed", "episodes", "checkpoint", "artifact_path"}
    require(required <= set(lane), f"lane required keys: {sorted(required - set(lane))}")
    require(isinstance(lane["cell"], str) and lane["cell"], "cell")
    require(isinstance(lane["stratum"], str) and lane["stratum"], "stratum")
    require(lane["side"] in SIDES, "side")
    require(isinstance(lane["seed"], int) and not isinstance(lane["seed"], bool), "seed")
    require(isinstance(lane["episodes"], int) and lane["episodes"] == expected_n, f"exact N: expected {expected_n}")
    require(isinstance(lane["checkpoint"], str) and lane["checkpoint"], "checkpoint")
    require(isinstance(lane["artifact_path"], str) and lane["artifact_path"], "artifact_path")
    return lane["cell"], lane["stratum"], lane["side"]


def reduce_manifest(manifest: dict[str, Any], expected_n: int) -> dict[str, Any]:
    require(manifest.get("schema") == MANIFEST_SCHEMA, "manifest schema")
    step = manifest.get("step")
    endpoint = manifest.get("endpoint", False)
    require(isinstance(step, int) and step >= 0, "manifest step")
    require(isinstance(endpoint, bool), "manifest endpoint bool")
    lanes = manifest.get("lanes")
    require(isinstance(lanes, list) and lanes, "manifest lanes")
    cells: dict[str, dict[str, dict[str, dict[str, Any]]]] = {}
    invalid: dict[str, list[str]] = collections.defaultdict(list)
    seen: set[tuple[str, str, str]] = set()
    lane_outputs: list[dict[str, Any]] = []
    for raw_lane in lanes:
        require(isinstance(raw_lane, dict), "lane mapping")
        cell = raw_lane.get("cell")
        require(isinstance(cell, str) and cell, "lane cell")
        try:
            cell, stratum, side = validate_lane_identity(raw_lane, expected_n)
            identity = (cell, stratum, side)
            require(identity not in seen, f"duplicate lane: {identity}")
            seen.add(identity)
            summary = summary_for_lane(raw_lane, expected_n)
        except ReducerError as error:
            stratum = raw_lane.get("stratum", "<missing>")
            side = raw_lane.get("side", "<missing>")
            invalid[cell].append(f"{stratum}/{side}: {error}")
            lane_outputs.append({"cell": cell, "stratum": stratum, "side": side, "status": "V27_INVALID", "failure": str(error)})
            continue
        cells.setdefault(cell, {}).setdefault(stratum, {})[side] = summary
        lane_outputs.append({"cell": cell, "stratum": stratum, "side": side, "status": "COMPLETE"})
    for cell in invalid:
        cells.pop(cell, None)
    wave_c_history = manifest.get("wave_c_history")
    if wave_c_history is not None:
        wave_c_history = [*wave_c_history, {"step": step, "cells": cells}]
    return {
        "schema": SCHEMA,
        "status": "V27_INVALID" if invalid else "V27_COMPLETE",
        "expected_n": expected_n,
        "step": step,
        "endpoint": endpoint,
        "cells": cells,
        "lanes": lane_outputs,
        "invalid_cells": dict(invalid),
        "typed_outcomes": typed_outcomes(cells, wave_c_history) if endpoint and not invalid else ({
            "qualification": {"outcome": "UNRESOLVED"},
            "wave_a": {"outcome": "UNRESOLVED"},
            "wave_b_domain": {"outcome": "UNRESOLVED"},
            "recovery": {"outcome": "UNRESOLVED"},
            "wave_c": {"sc_outcome": "UNRESOLVED", "sk_outcome": "UNRESOLVED"},
        } if endpoint else None),
        "route": "V27_INVALID" if invalid else "V27_REDUCED",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--expected-n", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(args.expected_n > 0, "expected-n positive")
    require(not args.output.exists(), f"refusing to overwrite reducer output: {args.output}")
    manifest = load_json(args.manifest)
    require(isinstance(manifest, dict), "manifest mapping")
    payload = reduce_manifest(manifest, args.expected_n)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"route": payload["route"], "output": str(args.output), "invalid_cells": sorted(payload["invalid_cells"])}))
    return 2 if payload["status"] == "V27_INVALID" else 0


if __name__ == "__main__":
    raise SystemExit(main())
