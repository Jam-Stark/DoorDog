#!/usr/bin/env python3
"""Rank successful and timeout reward sequences from identical V6.1 late-state anchors."""

from __future__ import annotations

import argparse
import gzip
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
EQUAL_HORIZON_STEPS = 570
CONTROL_DT_S = 0.02
REPAIR_EVENT_RAW_SCALE = 36280.126953125
REPAIR_EVENT_SCALED_CREDIT = REPAIR_EVENT_RAW_SCALE * CONTROL_DT_S
SOURCE_TRACE = ROOT / "logs_eval/a2_piper_pull_v6_1/q4_env14_late_bank_capture_retry1/eval/stage2_5_step_trace.json.gz"
QI_TRAIN_CONFIG = ROOT / "logs_rl/a2_piper_pull_v6_1/pull_v6_1_QI_r6an_integrated_seed1/config.yaml"
DEFAULT_OUTPUT = ROOT / "scriptsFORhuman/pull_v6_1/PULL_V6_1_LATE_REWARD_REPAIR_PROJECTION_FLOAT32.json"
PAIRS = (
    {
        "anchor": "post_release_d25",
        "source": {"label": "q4_success_source_env14", "path": SOURCE_TRACE, "env_id": 14},
        "candidate": {
            "label": "qi_seed1_retry2_d25_env0_timeout",
            "path": ROOT / "logs_eval/a2_piper_pull_v6_1/q5_qi_seed1_step25_d25_retry2/eval/stage2_5_step_trace.json.gz",
            "env_id": 0,
        },
    },
    {
        "anchor": "frame_passage",
        "source": {"label": "q4_success_source_env14", "path": SOURCE_TRACE, "env_id": 14},
        "candidate": {
            "label": "qi_seed1_retry2_frame_env0_timeout",
            "path": ROOT / "logs_eval/a2_piper_pull_v6_1/q5_qi_seed1_step25_frame_retry2/eval/stage2_5_step_trace.json.gz",
            "env_id": 0,
        },
    },
    {
        "anchor": "e6_stage5_entry",
        "source": {"label": "q4_success_source_env14", "path": SOURCE_TRACE, "env_id": 14},
        "candidate": {
            "label": "qi_seed1_retry2_e6_env0_timeout",
            "path": ROOT / "logs_eval/a2_piper_pull_v6_1/q5_qi_seed1_step25_e6_retry2/eval/stage2_5_step_trace.json.gz",
            "env_id": 0,
        },
    },
)


def _required(mapping: dict[str, Any], key: str, where: str) -> Any:
    if key not in mapping:
        raise KeyError(f"missing {where}.{key}")
    return mapping[key]


def _nested(mapping: dict[str, Any], *keys: str) -> Any:
    value: Any = mapping
    for index, key in enumerate(keys):
        if not isinstance(value, dict):
            raise TypeError(f"{'.'.join(keys[:index])} must be a mapping")
        value = _required(value, key, ".".join(keys[:index]) or "row")
    return value


def _load_rows(path: Path, env_id: int) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        trace = json.load(stream)
    if not isinstance(trace, list):
        raise TypeError(f"trace must be a list: {path}")
    rows = [
        row for row in trace
        if isinstance(row, dict)
        and _required(row, "env_id", "row") == env_id
        and _required(row, "episode_index", "row") == 0
        and _required(row, "first_episode_active", "row") is True
    ]
    if not rows:
        raise ValueError(f"no first-episode rows for env_id={env_id}: {path}")
    rows.sort(key=lambda row: _required(row, "step_index", "row"))
    steps = [_required(row, "step_index", "row") for row in rows]
    if steps != list(range(steps[0], steps[0] + len(steps))):
        raise ValueError(f"first-episode step_index is not contiguous: {path}")
    return rows


def _anchor_index(rows: list[dict[str, Any]], anchor: str) -> int:
    for index, row in enumerate(rows):
        if anchor == "post_release_d25":
            if int(_nested(row, "pull_v0", "pull_v6", "release_persistence_steps")) >= 25:
                return index
        elif anchor == "frame_passage":
            if bool(_nested(row, "pull_v3_traversal", "frame_passage")):
                return index
        elif anchor == "e6_stage5_entry":
            e6 = bool(_nested(row, "pull_v0_episode", "event_reached", "E6_PATH_REVERSAL_ENTRY"))
            if e6 and _required(row, "stage_buf", "row") == 5:
                return index
        else:
            raise ValueError(f"unsupported anchor: {anchor}")
    raise ValueError(f"anchor {anchor} is absent")


def _category(term: str) -> str:
    if term.startswith(("a2_stage3_stage4_", "a2_stage4_")):
        return "legacy_stage4_hold_income"
    if any(token in term for token in ("contact", "force", "push", "recontact")):
        return "contact_safety"
    if any(token in term for token in (
        "arm_default", "arm_tuck", "upper_body", "dof", "roll_pitch", "orientation",
        "face_door", "standing_still", "gripper", "delta_action_rate", "ref_dof",
    )):
        return "posture_arm_compactness"
    if term in {"termination", "success_save_time"}:
        return "time_termination"
    return "progress_one_shot"


def _window(rows: list[dict[str, Any]], start: int, stop: int, gamma: float) -> dict[str, Any]:
    per_term: dict[str, float] = defaultdict(float)
    expected_reward_terms: set[str] | None = None
    prior_termination = 0.0
    if start > 0:
        prior_sums = _required(rows[start - 1], "reward_episode_sums", "pre-anchor row")
        if not isinstance(prior_sums, dict):
            raise TypeError("pre-anchor reward_episode_sums must be a mapping")
        prior_termination = float(_required(prior_sums, "termination", "pre-anchor reward_episode_sums"))
    for row_index, row in enumerate(rows[start:stop], start):
        reward = _required(row, "reward_scaled", "row")
        if not isinstance(reward, dict):
            raise TypeError("reward_scaled must be a mapping")
        reward_terms = set(reward)
        if expected_reward_terms is None:
            expected_reward_terms = reward_terms
        elif reward_terms != expected_reward_terms:
            raise ValueError("active reward term set changes inside the ranked window")
        episode_sums = _required(row, "reward_episode_sums", "row")
        if not isinstance(episode_sums, dict):
            raise TypeError("reward_episode_sums must be a mapping")
        termination = float(_required(episode_sums, "termination", "reward_episode_sums"))
        discount = gamma ** (row_index - start)
        for term, value in reward.items():
            per_term[term] += discount * float(value)
        per_term["termination"] += discount * (termination - prior_termination)
        prior_termination = termination
    category_totals: dict[str, float] = defaultdict(float)
    for term, value in per_term.items():
        category_totals[_category(term)] += value
    ordered_terms = dict(sorted(per_term.items()))
    return {
        "steps": stop - start,
        "total": sum(ordered_terms.values()),
        "per_term": ordered_terms,
        "categories": dict(sorted(category_totals.items())),
        "active_reward_terms": sorted(expected_reward_terms or ()),
    }


def _gamma(path: Path) -> float:
    if not path.is_file():
        raise FileNotFoundError(path)
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise TypeError("QI resolved config must be a mapping")
    value = _nested(config, "algo", "config", "gamma")
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0.0 < float(value) <= 1.0:
        raise ValueError(f"invalid algo.config.gamma: {value!r}")
    return float(value)


def _outcome(rows: list[dict[str, Any]], expected: str) -> None:
    last = rows[-1]
    complete = bool(_nested(last, "pull_v0_episode", "whole_body_clear"))
    terminal = _required(last, "terminal_reasons", "terminal row")
    if expected == "complete":
        if terminal != "complete" or not complete:
            raise ValueError(f"source outcome must be complete; got terminal={terminal!r}, complete={complete!r}")
    elif expected == "timeout":
        if terminal != "stage_overtime" or complete:
            raise ValueError(f"candidate outcome must be stage_overtime timeout; got terminal={terminal!r}, complete={complete!r}")
    else:
        raise ValueError(f"unsupported outcome requirement: {expected}")


def _validate_event_inclusion(
    rows: list[dict[str, Any]], start: int, anchor: str, source: bool
) -> dict[str, Any]:
    window = rows[start:start + EQUAL_HORIZON_STEPS]
    if len(window) != EQUAL_HORIZON_STEPS:
        raise ValueError("equal-horizon event validation requires a complete window")
    e6_indices = [
        index for index, row in enumerate(window)
        if bool(_nested(row, "pull_v0_episode", "event_reached", "E6_PATH_REVERSAL_ENTRY"))
    ]
    e7_indices = [
        index for index, row in enumerate(window)
        if bool(_nested(row, "pull_v0_episode", "event_reached", "E7_WHOLE_BODY_CLEAR"))
    ]
    if source and anchor == "e6_stage5_entry":
        last = window[-1]
        if not bool(_nested(last, "pull_v0_episode", "event_reached", "E7_WHOLE_BODY_CLEAR")) or not bool(
            _nested(last, "pull_v0_episode", "whole_body_clear")
        ):
            raise ValueError("source E6 equal-horizon endpoint must be E7/whole_body_clear")
    if source and anchor in {"post_release_d25", "frame_passage"} and not e6_indices:
        raise ValueError(f"source {anchor} equal-horizon window must include E6")
    return {
        "window_last_step": _required(window[-1], "step_index", "equal-horizon endpoint"),
        "e6_included": bool(e6_indices),
        "e7_included": bool(e7_indices),
        "endpoint_whole_body_clear": bool(_nested(window[-1], "pull_v0_episode", "whole_body_clear")),
    }


def _future_event_edges(rows: list[dict[str, Any]], start: int) -> dict[str, int]:
    stop = start + EQUAL_HORIZON_STEPS
    edges = {"e6": 0, "e7": 0}
    for row_index in range(start + 1, stop):
        previous = rows[row_index - 1]
        current = rows[row_index]
        for label, event_name in (("e6", "E6_PATH_REVERSAL_ENTRY"), ("e7", "E7_WHOLE_BODY_CLEAR")):
            if not bool(_nested(previous, "pull_v0_episode", "event_reached", event_name)) and bool(
                _nested(current, "pull_v0_episode", "event_reached", event_name)
            ):
                edges[label] += 1
    return edges


def _cell(spec: dict[str, Any], anchor: str, gamma: float, expected_outcome: str) -> dict[str, Any]:
    path = spec["path"]
    env_id = spec["env_id"]
    rows = _load_rows(path, env_id)
    _outcome(rows, expected_outcome)
    start = _anchor_index(rows, anchor)
    if len(rows) - start < EQUAL_HORIZON_STEPS:
        raise ValueError(
            f"{spec['label']} tail is shorter than equal horizon: {len(rows) - start} < {EQUAL_HORIZON_STEPS}"
        )
    return {
        "label": spec["label"],
        "path": str(path.relative_to(ROOT)),
        "env_id": env_id,
        "anchor": anchor,
        "anchor_step": _required(rows[start], "step_index", "anchor row"),
        "equal_horizon_event_inclusion": _validate_event_inclusion(
            rows, start, anchor, source=expected_outcome == "complete"
        ),
        "equal_horizon_future_event_edges": _future_event_edges(rows, start),
        "available_tail": _window(rows, start, len(rows), 1.0),
        "equal_horizon": _window(rows, start, start + EQUAL_HORIZON_STEPS, 1.0),
        "discounted_equal_horizon": _window(rows, start, start + EQUAL_HORIZON_STEPS, gamma),
    }


def _delta(candidate: dict[str, Any], source: dict[str, Any], metric: str) -> dict[str, Any]:
    candidate_values = candidate[metric]
    source_values = source[metric]
    if candidate_values["active_reward_terms"] != source_values["active_reward_terms"]:
        raise ValueError(f"source/candidate active reward term sets differ at {metric}")
    terms = {
        name: candidate_values["per_term"][name] - source_values["per_term"][name]
        for name in candidate_values["per_term"]
    }
    categories = {
        name: candidate_values["categories"].get(name, 0.0) - source_values["categories"].get(name, 0.0)
        for name in sorted(set(candidate_values["categories"]) | set(source_values["categories"]))
    }
    return {
        "candidate_minus_source_total": candidate_values["total"] - source_values["total"],
        "per_term": terms,
        "categories": categories,
    }


def _repair_projection(pairs: list[dict[str, Any]]) -> dict[str, Any]:
    if abs(REPAIR_EVENT_SCALED_CREDIT - 725.6025390625) > 1.0e-12:
        raise ValueError("raw repair scale and control dt do not resolve to the registered scaled credit")
    expected_source_edges = {
        "post_release_d25": {"e6": 1, "e7": 0},
        "frame_passage": {"e6": 1, "e7": 0},
        "e6_stage5_entry": {"e6": 0, "e7": 1},
    }
    projections = []
    for pair in pairs:
        anchor = pair["anchor"]
        source_edges = pair["source"]["equal_horizon_future_event_edges"]
        candidate_edges = pair["candidate"]["equal_horizon_future_event_edges"]
        if source_edges != expected_source_edges[anchor]:
            raise ValueError(f"source future event edges mismatch at {anchor}: {source_edges}")
        if candidate_edges != {"e6": 0, "e7": 0}:
            raise ValueError(f"candidate must have no future E6/E7 edges at {anchor}: {candidate_edges}")
        base_delta = pair["equal_horizon_candidate_minus_source"]["candidate_minus_source_total"]
        source_credit_edges = source_edges["e6"] + source_edges["e7"]
        candidate_credit_edges = candidate_edges["e6"] + candidate_edges["e7"]
        projected_delta = base_delta + (candidate_credit_edges - source_credit_edges) * REPAIR_EVENT_SCALED_CREDIT
        if projected_delta >= 0.0:
            raise ValueError(f"repair projection must rank source above candidate at {anchor}: {projected_delta}")
        projections.append({
            "anchor": anchor,
            "base_candidate_minus_source": base_delta,
            "source_future_credit_edges": source_edges,
            "candidate_future_credit_edges": candidate_edges,
            "projected_candidate_minus_source": projected_delta,
        })
    frame = next(item for item in projections if item["anchor"] == "frame_passage")
    expected_frame_margin = -1.0000458246890958
    if abs(frame["projected_candidate_minus_source"] - expected_frame_margin) > 1.0e-6:
        raise ValueError(
            "frame repair margin must exceed source by at least 1.0 scaled reward unit; "
            f"got {frame['projected_candidate_minus_source']}"
        )
    return {
        "raw_one_shot_scale": REPAIR_EVENT_RAW_SCALE,
        "control_dt_s": CONTROL_DT_S,
        "scaled_one_shot_credit": REPAIR_EVENT_SCALED_CREDIT,
        "pairs": projections,
        "validation": {
            "all_projected_candidate_minus_source_negative": True,
            "worst_case_anchor": "frame_passage",
            "worst_case_projected_candidate_minus_source": frame["projected_candidate_minus_source"],
            "worst_case_expected": expected_frame_margin,
            "atol": 1.0e-6,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    gamma = _gamma(QI_TRAIN_CONFIG)
    pairs = []
    for pair in PAIRS:
        source = _cell(pair["source"], pair["anchor"], gamma, expected_outcome="complete")
        candidate = _cell(pair["candidate"], pair["anchor"], gamma, expected_outcome="timeout")
        pairs.append({
            "anchor": pair["anchor"],
            "source": source,
            "candidate": candidate,
            "ranking": {
                "equal_horizon_high_to_low": (
                    ["source", "candidate"]
                    if source["equal_horizon"]["total"] >= candidate["equal_horizon"]["total"]
                    else ["candidate", "source"]
                ),
                "discounted_equal_horizon_high_to_low": (
                    ["source", "candidate"]
                    if source["discounted_equal_horizon"]["total"] >= candidate["discounted_equal_horizon"]["total"]
                    else ["candidate", "source"]
                ),
            },
            "equal_horizon_candidate_minus_source": _delta(candidate, source, "equal_horizon"),
            "discounted_equal_horizon_candidate_minus_source": _delta(candidate, source, "discounted_equal_horizon"),
        })
    report = {
        "schema": "a2_piper_pull_v61_late_reward_ranking_v1",
        "equal_horizon_steps": EQUAL_HORIZON_STEPS,
        "gamma": gamma,
        "gamma_provenance": f"{QI_TRAIN_CONFIG.relative_to(ROOT)}:algo.config.gamma",
        "pairs": pairs,
        "repair_projection": _repair_projection(pairs),
        "claim_boundary": (
            "This is an event-aligned reward-sequence comparison from common late-state anchors. "
            "It makes no PPO preference claim."
        ),
    }
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite report: {args.output}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
