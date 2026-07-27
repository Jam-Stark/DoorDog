"""Build the objective v19 gate matrix and pre-registered ablation comparisons."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


SCHEMA = "a2_piper_v19_final_analysis_v1"
POST_SCHEMA = "a2_piper_v19_post_m22_endpoint_runner_v1"
ENDPOINT_SCHEMA = "a2_piper_v19_endpoint_report_v1"
WANDB_SCHEMA = "a2_piper_v19_wandb_sync_v1"
RENDER_QA_SCHEMA = "a2_piper_v19_render_qa_v1"
GROUPS = ("G1", "G2", "G3", "G4", "G5", "G6", "G7")
CARRY_TARGET_GROUPS = {"G1", "G2", "G6"}


class V19FinalAnalysisError(ValueError):
    """Raised when final v19 evidence is incomplete or inconsistent."""


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise V19FinalAnalysisError(f"cannot load JSON {path}: {exc}") from exc


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise V19FinalAnalysisError(f"{name} must be a mapping")
    return value


def _finite(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise V19FinalAnalysisError(f"{name} must be finite; got {value!r}")
    return float(value)


def _integer(value: Any, name: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise V19FinalAnalysisError(f"{name} must be an integer >= {minimum}; got {value!r}")
    return value


def _count(value: Any, name: str, total: int) -> int:
    row = _mapping(value, name)
    count = _integer(row.get("count"), f"{name}.count")
    actual_total = _integer(row.get("total"), f"{name}.total")
    if actual_total != total or count > total:
        raise V19FinalAnalysisError(f"{name} must be an exact count out of {total}")
    return count


def _nested(payload: Mapping[str, Any], name: str, *keys: str) -> Any:
    value: Any = payload
    for key in keys:
        if not isinstance(value, Mapping) or key not in value:
            raise V19FinalAnalysisError(f"{name} is missing {'.'.join(keys)}")
        value = value[key]
    return value


def _validate_wandb(payload: Any, source: Path) -> dict[str, Any]:
    root = _mapping(payload, "W&B sync report")
    if root.get("schema") != WANDB_SCHEMA:
        raise V19FinalAnalysisError("W&B sync schema is invalid")
    if root.get("sync_cli_exit_code") != 0 or root.get("verified_via_api") is not True:
        raise V19FinalAnalysisError("W&B sync is not CLI/API verified")
    rows = root.get("runs")
    if not isinstance(rows, list) or len(rows) != len(GROUPS):
        raise V19FinalAnalysisError("W&B sync must contain exactly seven runs")
    indexed: dict[str, Any] = {}
    for row_value in rows:
        row = _mapping(row_value, "W&B run")
        group = row.get("group")
        if group not in GROUPS or group in indexed:
            raise V19FinalAnalysisError("W&B groups must be unique G1..G7")
        if row.get("state") != "finished":
            raise V19FinalAnalysisError(f"W&B {group} state must be finished")
        url = row.get("url")
        run_id = row.get("id")
        if not isinstance(url, str) or not url.startswith("https://wandb.ai/"):
            raise V19FinalAnalysisError(f"W&B {group} URL is invalid")
        if not isinstance(run_id, str) or not run_id or not url.endswith("/" + run_id):
            raise V19FinalAnalysisError(f"W&B {group} id/URL binding is invalid")
        indexed[str(group)] = dict(row)
    if set(indexed) != set(GROUPS):
        raise V19FinalAnalysisError("W&B sync is missing groups")
    return {"source": str(source.resolve()), "project": root.get("project"), "runs": indexed}


def _endpoint_metrics(payload: Any, expected_group: str, source: Path) -> dict[str, Any]:
    root = _mapping(payload, f"{expected_group} endpoint report")
    if root.get("schema") != ENDPOINT_SCHEMA or root.get("group") != expected_group:
        raise V19FinalAnalysisError(f"{expected_group} endpoint schema/group is invalid")
    checkpoint_value = root.get("checkpoint")
    if not isinstance(checkpoint_value, str) or not Path(checkpoint_value).expanduser().resolve().is_file():
        raise V19FinalAnalysisError(f"{expected_group} checkpoint does not exist")
    artifacts = _mapping(root.get("source_artifacts"), f"{expected_group}.source_artifacts")
    if set(artifacts) != {"seed0", "seed1", "seed2"}:
        raise V19FinalAnalysisError(f"{expected_group} requires seed0/1/2 source artifacts")
    for seed, artifact in artifacts.items():
        if not isinstance(artifact, str) or not Path(artifact).expanduser().resolve().is_dir():
            raise V19FinalAnalysisError(f"{expected_group} {seed} artifact does not exist")

    goal_canonical = _count(_nested(root, expected_group, "goal", "canonical"), f"{expected_group}.goal.canonical", 16)
    goal_pooled = _count(_nested(root, expected_group, "goal", "pooled"), f"{expected_group}.goal.pooled", 48)
    crossing_pooled = _count(
        _nested(root, expected_group, "crossing_while_holding", "pooled"),
        f"{expected_group}.crossing_while_holding.pooled",
        48,
    )
    held = _mapping(root.get("held_carry"), f"{expected_group}.held_carry")
    held_hinge = _mapping(held.get("hinge_rad"), f"{expected_group}.held_carry.hinge_rad")
    held_denominator = _integer(held.get("denominator"), f"{expected_group}.held_carry.denominator", minimum=1)
    if _integer(held_hinge.get("n"), f"{expected_group}.held_carry.hinge_rad.n", minimum=1) != held_denominator:
        raise V19FinalAnalysisError(f"{expected_group} held-carry denominator mismatch")
    arm_j1 = _mapping(held.get("arm_j1_delta_rad"), f"{expected_group}.held_carry.arm_j1_delta_rad")
    if _integer(arm_j1.get("n"), f"{expected_group}.arm_j1_delta_rad.n", minimum=1) != held_denominator:
        raise V19FinalAnalysisError(f"{expected_group} arm-j1 denominator mismatch")

    overspeed = _mapping(root.get("overspeed_terminations"), f"{expected_group}.overspeed")
    overspeed_count = _integer(overspeed.get("count"), f"{expected_group}.overspeed.count")
    if overspeed.get("total") != 48 or overspeed_count > 48:
        raise V19FinalAnalysisError(f"{expected_group} overspeed total must equal 48")
    opening = _mapping(root.get("opening_slip"), f"{expected_group}.opening_slip")
    release = _mapping(root.get("release"), f"{expected_group}.release")
    release_hinge = _mapping(release.get("hinge_rad"), f"{expected_group}.release.hinge_rad")
    release_force = _mapping(release.get("post_release_body_force_n"), f"{expected_group}.release.force")
    release_denominator = _integer(release.get("denominator"), f"{expected_group}.release.denominator", minimum=1)
    if release_hinge.get("n") != release_denominator or release_force.get("n") != release_denominator:
        raise V19FinalAnalysisError(f"{expected_group} release denominator mismatch")
    release_contact = _integer(
        release.get("post_release_body_contact_count"),
        f"{expected_group}.release.post_release_body_contact_count",
    )
    if release_contact > release_denominator:
        raise V19FinalAnalysisError(f"{expected_group} release contact count exceeds denominator")
    pre = _mapping(root.get("pre_crossing_stage3_stage4"), f"{expected_group}.pre_crossing")
    _integer(pre.get("denominator"), f"{expected_group}.pre_crossing.denominator", minimum=1)

    metrics = {
        "goal_canonical_count": goal_canonical,
        "goal_pooled_count": goal_pooled,
        "crossing_while_holding_pooled_count": crossing_pooled,
        "held_denominator": held_denominator,
        "held_hinge_p50_rad": _finite(held_hinge.get("p50"), f"{expected_group}.held_hinge.p50"),
        "held_hinge_p95_rad": _finite(held_hinge.get("p95"), f"{expected_group}.held_hinge.p95"),
        "held_hinge_max_rad": _finite(held_hinge.get("max"), f"{expected_group}.held_hinge.max"),
        "arm_j1_delta_p50_rad": _finite(arm_j1.get("p50"), f"{expected_group}.arm_j1_delta.p50"),
        "arm_j1_delta_p95_rad": _finite(arm_j1.get("p95"), f"{expected_group}.arm_j1_delta.p95"),
        "arm_j1_delta_gt_0_3_count": _integer(
            held.get("arm_j1_delta_gt_0_3"), f"{expected_group}.arm_j1_delta_gt_0_3"
        ),
        "overspeed_termination_count": overspeed_count,
        "opening_slip_p95_cm": _finite(opening.get("p95_cm"), f"{expected_group}.opening_slip.p95_cm"),
        "release_denominator": release_denominator,
        "hinge_at_release_p50_rad": _finite(release_hinge.get("p50"), f"{expected_group}.release.hinge.p50"),
        "post_release_body_contact_count": release_contact,
        "post_release_body_force_p95_n": _finite(release_force.get("p95"), f"{expected_group}.release.force.p95"),
        "pre_crossing_bilateral_rate": _finite(pre.get("bilateral_rate"), f"{expected_group}.bilateral_rate"),
        "pre_crossing_coasting_rate": _finite(pre.get("coasting_rate"), f"{expected_group}.coasting_rate"),
        "pre_crossing_over_force_rate": _finite(pre.get("over_force_rate"), f"{expected_group}.over_force_rate"),
    }
    for name in ("pre_crossing_bilateral_rate", "pre_crossing_coasting_rate", "pre_crossing_over_force_rate"):
        if not 0.0 <= metrics[name] <= 1.0:
            raise V19FinalAnalysisError(f"{expected_group}.{name} must be within [0,1]")
    if metrics["opening_slip_p95_cm"] < 0.0 or metrics["post_release_body_force_p95_n"] < 0.0:
        raise V19FinalAnalysisError(f"{expected_group} slip/force must be non-negative")
    return {
        "source": str(source.resolve()),
        "checkpoint": str(Path(checkpoint_value).expanduser().resolve()),
        "checkpoint_sha256": root.get("checkpoint_sha256"),
        "source_artifacts": dict(artifacts),
        "metrics": metrics,
    }


def _gate(observed: Any, operator: str, target: Any, passed: bool) -> dict[str, Any]:
    return {"observed": observed, "operator": operator, "target": target, "pass": bool(passed)}


def _gates(group: str, metrics: Mapping[str, Any]) -> dict[str, Any]:
    gates: dict[str, Any] = {
        "goal_canonical": _gate(metrics["goal_canonical_count"], ">=", 15, metrics["goal_canonical_count"] >= 15),
        "goal_pooled": _gate(metrics["goal_pooled_count"], ">=", 46, metrics["goal_pooled_count"] >= 46),
        "overspeed_terminations": _gate(metrics["overspeed_termination_count"], "==", 0, metrics["overspeed_termination_count"] == 0),
        "opening_slip_p95_cm": _gate(metrics["opening_slip_p95_cm"], "<=", 3.0, metrics["opening_slip_p95_cm"] <= 3.0),
        "post_release_body_contact_count": _gate(metrics["post_release_body_contact_count"], "<=", 2, metrics["post_release_body_contact_count"] <= 2),
        "post_release_body_force_p95_n": _gate(metrics["post_release_body_force_p95_n"], "<", 80.0, metrics["post_release_body_force_p95_n"] < 80.0),
        "pre_crossing_bilateral_rate": _gate(metrics["pre_crossing_bilateral_rate"], ">=", 0.99, metrics["pre_crossing_bilateral_rate"] >= 0.99),
        "pre_crossing_coasting_rate": _gate(metrics["pre_crossing_coasting_rate"], "<", 0.02, metrics["pre_crossing_coasting_rate"] < 0.02),
        "pre_crossing_over_force_rate": _gate(metrics["pre_crossing_over_force_rate"], "<", 0.02, metrics["pre_crossing_over_force_rate"] < 0.02),
        "crossing_while_holding_pooled": _gate(metrics["crossing_while_holding_pooled_count"], ">=", 46, metrics["crossing_while_holding_pooled_count"] >= 46),
    }
    required = list(gates)
    if group in CARRY_TARGET_GROUPS:
        gates["held_hinge_p50_rad"] = _gate(metrics["held_hinge_p50_rad"], ">=", 1.45, metrics["held_hinge_p50_rad"] >= 1.45)
        required.append("held_hinge_p50_rad")
    else:
        gates["held_hinge_p50_rad"] = {
            "observed": metrics["held_hinge_p50_rad"],
            "operator": "observability-only",
            "target": None,
            "pass": None,
        }
    if group == "G1":
        gates["hinge_at_release_p50_rad"] = _gate(metrics["hinge_at_release_p50_rad"], ">=", 1.55, metrics["hinge_at_release_p50_rad"] >= 1.55)
        required.append("hinge_at_release_p50_rad")
    else:
        gates["hinge_at_release_p50_rad"] = {
            "observed": metrics["hinge_at_release_p50_rad"],
            "operator": "observability-only",
            "target": None,
            "pass": None,
        }
    return {
        "gates": gates,
        "required_gate_names": required,
        "numeric_gate_status_excluding_render": "PASS" if all(gates[name]["pass"] for name in required) else "FAIL",
    }


def _metric_deltas(left: Mapping[str, Any], right: Mapping[str, Any]) -> dict[str, float]:
    names = (
        "goal_pooled_count",
        "crossing_while_holding_pooled_count",
        "held_hinge_p50_rad",
        "held_hinge_p95_rad",
        "hinge_at_release_p50_rad",
        "arm_j1_delta_p50_rad",
        "overspeed_termination_count",
        "opening_slip_p95_cm",
    )
    return {name: float(left[name]) - float(right[name]) for name in names}


def _comparison(groups: Mapping[str, Any], left: str, right: str) -> dict[str, Any]:
    if groups[left].get("endpoint_status") != "COMPLETED" or groups[right].get("endpoint_status") != "COMPLETED":
        return {"status": "UNEVALUABLE", "left": left, "right": right}
    return {
        "status": "EVALUATED",
        "left": left,
        "right": right,
        "delta_left_minus_right": _metric_deltas(groups[left]["metrics"], groups[right]["metrics"]),
    }



def _release_decision(groups: Mapping[str, Any]) -> dict[str, Any]:
    required = ("G1", "G2", "G3", "G6", "G7")
    if any(groups[group].get("endpoint_status") != "COMPLETED" for group in required):
        return {"status": "UNEVALUABLE", "required_groups": list(required)}
    carry_pass = {
        group: bool(groups[group]["gates"]["held_hinge_p50_rad"]["pass"])
        for group in ("G1", "G2", "G6")
    }
    g7_metrics = groups["G7"]["metrics"]
    g7_plateau_ge_1_5 = g7_metrics["held_hinge_p50_rad"] >= 1.5
    if not any(carry_pass.values()) and not g7_plateau_ge_1_5:
        return {
            "status": "SELECTED",
            "selected_release_group": "G3",
            "reason": "PRE_REGISTERED_NO_CARRY_FALLBACK",
            "carry_p50_gate_pass": carry_pass,
            "g7_plateau_ge_1_5": False,
            "g7_held_hinge_p50_rad": g7_metrics["held_hinge_p50_rad"],
            "g7_held_hinge_p95_rad": g7_metrics["held_hinge_p95_rad"],
        }
    return {
        "status": "CARRY_CANDIDATE_AVAILABLE_OR_CEILING_CONTINGENCY",
        "selected_release_group": None,
        "carry_p50_gate_pass": carry_pass,
        "g7_plateau_ge_1_5": g7_plateau_ge_1_5,
        "g7_held_hinge_p50_rad": g7_metrics["held_hinge_p50_rad"],
        "g7_held_hinge_p95_rad": g7_metrics["held_hinge_p95_rad"],
    }

def build_analysis(post: Any, wandb: Any, post_source: Path, wandb_source: Path) -> dict[str, Any]:
    post_root = _mapping(post, "post-M22 state")
    if post_root.get("schema") != POST_SCHEMA:
        raise V19FinalAnalysisError("post-M22 state schema is invalid")
    if post_root.get("status") not in {"COMPLETED", "COMPLETED_WITH_FAILURES"}:
        raise V19FinalAnalysisError("post-M22 state is not terminal")
    group_rows = post_root.get("groups")
    if not isinstance(group_rows, list) or len(group_rows) != len(GROUPS):
        raise V19FinalAnalysisError("post-M22 state must contain exactly seven groups")
    indexed: dict[str, Mapping[str, Any]] = {}
    for value in group_rows:
        row = _mapping(value, "post-M22 group")
        group = row.get("group")
        if group not in GROUPS or group in indexed:
            raise V19FinalAnalysisError("post-M22 groups must be unique G1..G7")
        indexed[str(group)] = row
    if set(indexed) != set(GROUPS):
        raise V19FinalAnalysisError("post-M22 state is missing groups")

    group_results: dict[str, Any] = {}
    for group in GROUPS:
        row = indexed[group]
        endpoint_status = row.get("status")
        result: dict[str, Any] = {
            "endpoint_status": endpoint_status,
            "m22_root": row.get("m22_root"),
            "adjudication_json": row.get("adjudication_json"),
            "adjudication_md": row.get("adjudication_md"),
        }
        if endpoint_status == "COMPLETED":
            report_value = row.get("endpoint_report_json")
            if not isinstance(report_value, str):
                raise V19FinalAnalysisError(f"{group} completed without endpoint report path")
            report_path = Path(report_value).expanduser().resolve()
            endpoint = _endpoint_metrics(_load_json(report_path), group, report_path)
            result.update(endpoint)
            result.update(_gates(group, endpoint["metrics"]))
        else:
            result["numeric_gate_status_excluding_render"] = "UNEVALUABLE"
            result["failure"] = {key: row.get(key) for key in ("status", "error", "evidence_step", "adjudication_step", "endpoint_evals", "report_step") if key in row}
        group_results[group] = result

    comparisons = {
        "G1_vs_G2_norm_raise": _comparison(group_results, "G1", "G2"),
        "G1_vs_G3_carry_institution": _comparison(group_results, "G1", "G3"),
        "G1_vs_G4_warmstart": _comparison(group_results, "G1", "G4"),
        "G1_vs_G5_overspeed_fix": _comparison(group_results, "G1", "G5"),
        "G1_vs_G6_replication": _comparison(group_results, "G1", "G6"),
    }
    if comparisons["G1_vs_G2_norm_raise"]["status"] == "EVALUATED":
        g1_pass = group_results["G1"]["gates"]["held_hinge_p50_rad"]["pass"]
        g2_pass = group_results["G2"]["gates"]["held_hinge_p50_rad"]["pass"]
        comparisons["G1_vs_G2_norm_raise"]["carry_gate_read"] = (
            "NORM_RAISE_REQUIRED_IN_THIS_PAIR"
            if g1_pass and not g2_pass
            else "NORM_RAISE_CONTRADICTED_IN_THIS_PAIR"
            if g2_pass and not g1_pass
            else "NORM_RAISE_NOT_DISTINGUISHED_BY_CARRY_GATE"
        )
    if comparisons["G1_vs_G5_overspeed_fix"]["status"] == "EVALUATED" and group_results["G6"].get("endpoint_status") == "COMPLETED":
        fixed = (group_results["G1"]["metrics"]["overspeed_termination_count"], group_results["G6"]["metrics"]["overspeed_termination_count"])
        no_fix = group_results["G5"]["metrics"]["overspeed_termination_count"]
        comparisons["G1_vs_G5_overspeed_fix"]["overspeed_gate_read"] = (
            "FIX_NECESSITY_SUPPORTED"
            if max(fixed) == 0 and no_fix > 0
            else "FIX_NOT_DISTINGUISHED_BY_OVERSPEED"
            if max(fixed) == 0 and no_fix == 0
            else "FIX_DID_NOT_CLEAR_OVERSPEED_IN_BOTH_FIXED_RUNS"
            if min(fixed) > 0
            else "MIXED_FIXED_REPLICATION"
        )
    if comparisons["G1_vs_G4_warmstart"]["status"] == "EVALUATED":
        comparisons["G1_vs_G4_warmstart"]["drifted_warmstart_common_numeric_gate_read"] = (
            "DRIFTED_WARMSTART_COMMON_NUMERIC_GATES_PASS"
            if group_results["G4"]["numeric_gate_status_excluding_render"] == "PASS"
            else "DRIFTED_WARMSTART_COMMON_NUMERIC_GATES_FAIL"
        )
    if group_results["G7"].get("endpoint_status") == "COMPLETED":
        metrics = group_results["G7"]["metrics"]
        comparisons["G7_geometric_plateau"] = {
            "status": "EVALUATED",
            "held_hinge_p50_rad": metrics["held_hinge_p50_rad"],
            "held_hinge_p95_rad": metrics["held_hinge_p95_rad"],
            "held_hinge_max_rad": metrics["held_hinge_max_rad"],
            "held_denominator": metrics["held_denominator"],
        }
    else:
        comparisons["G7_geometric_plateau"] = {"status": "UNEVALUABLE"}

    return {
        "schema": SCHEMA,
        "post_m22_source": str(post_source.resolve()),
        "wandb": _validate_wandb(wandb, wandb_source),
        "groups": group_results,
        "comparisons": comparisons,
        "release_decision": _release_decision(group_results),
        "render_gate_status": "SEPARATE_PLAN_REQUIRED_EVIDENCE",
    }


def attach_render_qa(report: dict[str, Any], render_value: Any, render_source: Path) -> dict[str, Any]:
    render = _mapping(render_value, "render QA")
    if render.get("schema") != RENDER_QA_SCHEMA or render.get("status") != "PASS":
        raise V19FinalAnalysisError("render QA schema/status is invalid")
    artifacts = render.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != 2:
        raise V19FinalAnalysisError("render QA must contain exactly winner and G7 artifacts")
    winner = _mapping(artifacts[0], "winner render artifact")
    g7 = _mapping(artifacts[1], "G7 render artifact")
    if winner.get("role") != "winner" or g7.get("role") != "g7_probe" or g7.get("group") != "G7":
        raise V19FinalAnalysisError("render QA roles/groups are invalid")
    winner_group = winner.get("group")
    if winner_group not in GROUPS or winner_group == "G7":
        raise V19FinalAnalysisError("render winner group must be G1..G6")
    selected_release_group = report["release_decision"].get("selected_release_group")
    if selected_release_group is not None and winner_group != selected_release_group:
        raise V19FinalAnalysisError(
            "render winner does not match the pre-registered release decision"
        )
    for group, artifact in ((str(winner_group), winner), ("G7", g7)):
        endpoint = report["groups"][group]
        if endpoint.get("endpoint_status") != "COMPLETED":
            raise V19FinalAnalysisError(f"render {group} lacks a completed endpoint")
        render_checkpoint = Path(str(artifact.get("checkpoint", ""))).expanduser().resolve()
        endpoint_checkpoint = Path(str(endpoint.get("checkpoint", ""))).expanduser().resolve()
        if render_checkpoint != endpoint_checkpoint or not render_checkpoint.is_file():
            raise V19FinalAnalysisError(f"render {group} checkpoint does not match endpoint")
        output_dir = Path(str(artifact.get("output_dir", ""))).expanduser().resolve()
        if not output_dir.is_dir():
            raise V19FinalAnalysisError(f"render {group} output directory does not exist")
    winner_gate = _mapping(render.get("winner_render_gate"), "winner render gate")
    if not isinstance(winner_gate.get("pass"), bool):
        raise V19FinalAnalysisError("winner render gate pass must be boolean")
    if winner.get("winner_render_gate") != winner_gate:
        raise V19FinalAnalysisError("winner render gate provenance is inconsistent")
    winner_numeric = report["groups"][str(winner_group)]["numeric_gate_status_excluding_render"]
    report["render"] = {
        "source": str(render_source.resolve()),
        "winner_group": winner_group,
        "winner_checkpoint": winner["checkpoint"],
        "g7_checkpoint": g7["checkpoint"],
        "winner_arm_j1_gate": dict(winner_gate),
        "winner_arm_j1_sweep": winner.get("arm_j1_sweep"),
        "g7_arm_j1_observability": render.get("g7_render_observability"),
        "artifacts": artifacts,
    }
    report["render_gate_status"] = "PASS" if winner_gate["pass"] else "FAIL"
    report["winner_full_judgement_status"] = (
        "PASS" if winner_numeric == "PASS" and winner_gate["pass"] else "FAIL"
    )
    return report


def write_outputs(report: Mapping[str, Any], output_json: Path, output_md: Path) -> None:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# A2 Piper v19 final analysis",
        "",
        f"Winner full judgement: {report.get('winner_full_judgement_status', 'RENDER_PENDING')}",
        f"Render gate: {report['render_gate_status']}",
        f"Release decision: {report['release_decision']['status']}",
        f"Selected release group: {report['release_decision'].get('selected_release_group')}",
        "",
        "| Group | Endpoint | Goal | Crossing-held | Held p50/p95 rad | Overspeed | Opening slip p95 cm | Release p50 rad | Numeric gates* |",
        "|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for group in GROUPS:
        row = report["groups"][group]
        if row["endpoint_status"] != "COMPLETED":
            lines.append(f"| {group} | {row['endpoint_status']} | — | — | — | — | — | — | UNEVALUABLE |")
            continue
        metrics = row["metrics"]
        lines.append(
            f"| {group} | COMPLETED | {metrics['goal_canonical_count']}/16; {metrics['goal_pooled_count']}/48 | "
            f"{metrics['crossing_while_holding_pooled_count']}/48 | {metrics['held_hinge_p50_rad']:.6f}/{metrics['held_hinge_p95_rad']:.6f} | "
            f"{metrics['overspeed_termination_count']}/48 | {metrics['opening_slip_p95_cm']:.6f} | "
            f"{metrics['hinge_at_release_p50_rad']:.6f} | {row['numeric_gate_status_excluding_render']} |"
        )
    lines.extend(
        [
            "",
            "\\* Numeric gates exclude the separate render-form gate.",
            "",
            "## Pre-registered comparisons",
            "",
            "~~~json",
            json.dumps(report["comparisons"], indent=2, sort_keys=True),
            "~~~",
        ]
    )
    output_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--post-state", type=Path, required=True)
    parser.add_argument("--wandb-sync-report", type=Path, required=True)
    parser.add_argument("--render-qa", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-md", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    report = attach_render_qa(
        build_analysis(
            _load_json(args.post_state),
            _load_json(args.wandb_sync_report),
            args.post_state,
            args.wandb_sync_report,
        ),
        _load_json(args.render_qa),
        args.render_qa,
    )
    write_outputs(report, args.output_json, args.output_md)
    print(f"v19 final analysis JSON: {args.output_json}")
    print(f"v19 final analysis Markdown: {args.output_md}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except V19FinalAnalysisError as exc:
        print(f"v19 FINAL ANALYSIS FAIL: {exc}", file=sys.stderr)
        raise SystemExit(2)
