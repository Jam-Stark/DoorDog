"""Strict M22 release adjudication for every numbered v19 checkpoint.

The adjudicator consumes a queue manifest and explicit evidence rows.  A
missing evidence row is a hard failure; an explicitly ``STRICT_INVALID`` row
is retained in the report and excluded from selection. Valid candidates must
pass every redline. The endpoint is selected by a fixed lexicographic redline
vector; an exact full-vector tie fails fast. No scalar reward, filename, or
checkpoint-step tie-break is used.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml


SCHEMA = "a2_piper_v19_m22_adjudication_v1"
MANIFEST_SCHEMA = "a2_piper_v19_m22_candidate_manifest_v1"
VALID_STATUSES = {"STRICT_VALID", "STRICT_INVALID"}
TOPOLOGY_COUNTS = {"canonical16": 16, "pooled48": 48}
CANONICAL_TOPOLOGY = "canonical16"
CANONICAL_EPISODES = 16
POOLED_EPISODES = 48
EXPECTED_HEIGHT_BOUNDS = (0.80, 1.10)
P0_DIAGNOSTIC_REWARD_TERMS = (
    "gripper_handle_orientation",
    "grasp_target_distance",
    "grasp",
    "penalty_not_standing_still",
    "a2_stage3_unlatch_hold",
    "a2_stage3_stage4_hold_and_drive",
    "push_door_hinge",
    "dont_push_door_handle",
    "target_root_distance",
    "penalty_standing_still",
    "stage",
    "penalty_door_frame_contact",
    "penalty_door_panel_contact",
    "penalty_a2_door_body_contact",
    "penalty_undesired_contact",
    "penalty_base_roll_pitch_l2",
    "a2_corridor_door_wide",
    "a2_corridor_clean_passage",
    "penalty_a2_posture_command_l1",
    "complete",
)
CHECKPOINT_RE = re.compile(r"^model_step_(?P<step>[0-9]+)\.pt$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class M22AdjudicationError(ValueError):
    """Raised when M22 evidence or selection is incomplete/ambiguous."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with Path(path).open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise M22AdjudicationError(f"cannot read checkpoint artifact {path}") from exc
    return digest.hexdigest()


def _canonical_path(value: Any, name: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise M22AdjudicationError(f"{name} must be a non-empty path string")
    return Path(value).expanduser().resolve()


def _validate_manifest(manifest: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    if not isinstance(manifest, Mapping) or manifest.get("schema") != MANIFEST_SCHEMA:
        raise M22AdjudicationError("candidate manifest schema is invalid")
    candidates = manifest.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise M22AdjudicationError("manifest candidates must be a non-empty list")
    seen_ids: set[str] = set()
    seen_steps: set[int] = set()
    seen_paths: set[str] = set()
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            raise M22AdjudicationError("manifest candidate must be a mapping")
        candidate_id = candidate.get("candidate_id")
        step = candidate.get("step")
        path_value = candidate.get("path")
        sha = candidate.get("sha256")
        if not isinstance(candidate_id, str) or not candidate_id:
            raise M22AdjudicationError("manifest candidate_id must be non-empty")
        if isinstance(step, bool) or not isinstance(step, int) or step < 0:
            raise M22AdjudicationError(f"manifest step is invalid for {candidate_id!r}")
        match = CHECKPOINT_RE.fullmatch(candidate_id)
        if match is None or int(match.group("step")) != step:
            raise M22AdjudicationError(f"manifest candidate_id/step mismatch for {candidate_id!r}")
        path = _canonical_path(path_value, f"manifest {candidate_id} path")
        if path.name != candidate_id:
            raise M22AdjudicationError(f"manifest path basename mismatch for {candidate_id!r}")
        if not isinstance(sha, str) or SHA256_RE.fullmatch(sha) is None:
            raise M22AdjudicationError(f"manifest SHA-256 is invalid for {candidate_id!r}")
        if candidate_id in seen_ids or step in seen_steps or str(path) in seen_paths:
            raise M22AdjudicationError("manifest candidate identity topology contains duplicates")
        if not path.is_file():
            raise M22AdjudicationError(f"manifest checkpoint does not exist: {path}")
        actual_sha = _sha256(path)
        if actual_sha != sha:
            raise M22AdjudicationError(
                f"manifest checkpoint SHA-256 mismatch for {candidate_id}: expected {sha}, got {actual_sha}"
            )
        seen_ids.add(candidate_id)
        seen_steps.add(step)
        seen_paths.add(str(path))
    return candidates


def _nested(mapping: Mapping[str, Any], *keys: str) -> Any:
    value: Any = mapping
    for key in keys:
        if not isinstance(value, Mapping) or key not in value:
            raise M22AdjudicationError(f"artifact config is missing {'.'.join(keys)}")
        value = value[key]
    return value


def _validate_exact_height_bounds(config: Mapping[str, Any]) -> None:
    try:
        env_config = config["env"]["config"]
    except (KeyError, TypeError):
        raise M22AdjudicationError("artifact config is missing env.config")
    if not isinstance(env_config, Mapping):
        raise M22AdjudicationError("artifact config env.config must be a mapping")
    bounds = env_config.get("a2_eval_door_handle_height_linspace")
    if (
        not isinstance(bounds, (list, tuple))
        or len(bounds) != 2
        or any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in bounds)
        or tuple(float(value) for value in bounds) != EXPECTED_HEIGHT_BOUNDS
    ):
        raise M22AdjudicationError("artifact config height linspace must be exactly [0.80,1.10]")


def _validate_source_artifact(
    candidate: Mapping[str, Any], artifact_value: Any, expected_seed: int
) -> Path:
    artifact = _canonical_path(artifact_value, "source artifact")
    if not artifact.is_dir():
        raise M22AdjudicationError(f"source artifact directory does not exist: {artifact}")
    config_path = artifact / ".hydra" / "config.yaml"
    if not config_path.is_file():
        raise M22AdjudicationError(f"source artifact lacks .hydra/config.yaml: {config_path}")
    try:
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise M22AdjudicationError(f"cannot read artifact config {config_path}") from exc
    if not isinstance(config, Mapping):
        raise M22AdjudicationError("artifact config must be a mapping")
    checkpoint = _canonical_path(config.get("checkpoint"), "artifact config checkpoint")
    candidate_path = _canonical_path(candidate.get("path"), "manifest checkpoint path")
    if checkpoint != candidate_path:
        raise M22AdjudicationError(
            f"artifact config checkpoint mismatch: expected {candidate_path}, got {checkpoint}"
        )
    if config.get("checkpoint_load_mode") != "full":
        raise M22AdjudicationError("artifact config checkpoint_load_mode must be full")
    config_seed = config.get("seed")
    if isinstance(config_seed, bool) or not isinstance(config_seed, int) or config_seed != expected_seed:
        raise M22AdjudicationError(
            f"artifact config seed must equal evaluation seed {expected_seed}"
        )
    if config.get("num_envs") != CANONICAL_EPISODES:
        raise M22AdjudicationError("source artifact config num_envs must be 16")
    evaluation = _nested(config, "algo", "config", "eval")
    if evaluation.get("num_eval_episodes") != CANONICAL_EPISODES:
        raise M22AdjudicationError("source artifact config eval.num_eval_episodes must be 16")
    if evaluation.get("eval_num_envs_episodes") is not True:
        raise M22AdjudicationError("artifact config eval_num_envs_episodes must be true")
    for key in ("save_goal_reached_only", "save_videos", "save_trajectories"):
        if evaluation.get(key) is not False:
            raise M22AdjudicationError(f"artifact config eval.{key} must be false")
    if evaluation.get("a2_eval_m41_strict_telemetry") is not True:
        raise M22AdjudicationError("artifact config must enable M41 strict telemetry")
    if evaluation.get("a2_diagnostic_trace_enabled") is not True:
        raise M22AdjudicationError("artifact config must enable diagnostic tracing")
    if evaluation.get("a2_eval_p2_posture_axis") != "none":
        raise M22AdjudicationError("artifact config P2 posture axis must be none")
    if evaluation.get("a2_forced_gripper_close_enabled") is not False:
        raise M22AdjudicationError("artifact config forced gripper close must be false")
    if evaluation.get("a2_hold_oracle_enabled") is not False:
        raise M22AdjudicationError("artifact config hold oracle must be false")
    if evaluation.get("a2_diagnostic_reward_terms") != list(P0_DIAGNOSTIC_REWARD_TERMS):
        raise M22AdjudicationError("artifact config diagnostic reward terms do not match exact P0 list")
    _validate_exact_height_bounds(config)
    return artifact


def _validate_evidence_binding(candidate: Mapping[str, Any], row: Mapping[str, Any]) -> str:
    required = ("candidate_id", "artifact", "checkpoint_path", "checkpoint_sha256", "evaluation_topology")
    missing = [name for name in required if name not in row]
    if missing:
        raise M22AdjudicationError(f"evidence row is missing provenance fields {missing}")
    if row.get("candidate_id") != candidate.get("candidate_id"):
        raise M22AdjudicationError("evidence candidate_id conflicts with manifest")
    for alias in ("path", "checkpoint", "candidate_path"):
        if alias in row:
            raise M22AdjudicationError(f"evidence contains unsupported candidate identity alias {alias!r}")
    if "step" in row and row["step"] != candidate.get("step"):
        raise M22AdjudicationError("evidence step conflicts with manifest")
    evidence_path = _canonical_path(row["checkpoint_path"], "evidence checkpoint_path")
    manifest_path = _canonical_path(candidate.get("path"), "manifest checkpoint_path")
    if evidence_path != manifest_path:
        raise M22AdjudicationError("evidence checkpoint_path conflicts with manifest")
    if row["checkpoint_sha256"] != candidate.get("sha256"):
        raise M22AdjudicationError("evidence checkpoint_sha256 conflicts with manifest")
    topology = row["evaluation_topology"]
    if topology not in TOPOLOGY_COUNTS:
        raise M22AdjudicationError("evaluation_topology must be canonical16 or pooled48")

    if topology == CANONICAL_TOPOLOGY:
        evaluation_seed = row.get("evaluation_seed")
        if isinstance(evaluation_seed, bool) or not isinstance(evaluation_seed, int) or evaluation_seed != 0:
            raise M22AdjudicationError("canonical16 evidence requires evaluation_seed=0")
        if "evaluation_seeds" in row or "source_artifacts" in row:
            raise M22AdjudicationError("canonical16 evidence cannot include pooled source provenance")
        _validate_source_artifact(candidate, row["artifact"], 0)
        return topology

    if "evaluation_seed" in row:
        raise M22AdjudicationError("pooled48 evidence requires evaluation_seeds, not evaluation_seed")
    evaluation_seeds = row.get("evaluation_seeds")
    if (
        not isinstance(evaluation_seeds, list)
        or any(isinstance(seed, bool) or not isinstance(seed, int) for seed in evaluation_seeds)
        or evaluation_seeds != [0, 1, 2]
    ):
        raise M22AdjudicationError("pooled48 evidence requires evaluation_seeds=[0,1,2]")
    source_values = row.get("source_artifacts")
    if not isinstance(source_values, list) or len(source_values) != 3:
        raise M22AdjudicationError("pooled48 evidence requires exactly three source_artifacts")
    source_paths = [_canonical_path(value, "source artifact") for value in source_values]
    if len(set(source_paths)) != 3:
        raise M22AdjudicationError("pooled48 source_artifacts must be unique")
    pooled_artifact = _canonical_path(row["artifact"], "pooled evidence artifact")
    if not pooled_artifact.exists():
        raise M22AdjudicationError(f"pooled evidence artifact does not exist: {pooled_artifact}")
    if pooled_artifact in source_paths:
        raise M22AdjudicationError("pooled evidence artifact cannot substitute for source_artifacts")
    for seed, source_path in zip((0, 1, 2), source_paths):
        _validate_source_artifact(candidate, str(source_path), seed)
    return topology


def _finite(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise M22AdjudicationError(f"{name} must be a finite number; got {value!r}")
    return float(value)


def _count_total(value: Any, name: str, expected_total: int) -> float:
    if not isinstance(value, Mapping) or "count" not in value or "total" not in value:
        raise M22AdjudicationError(
            f"{name} must be an explicit count/total mapping for {expected_total} episodes"
        )
    if any(key in value for key in ("rate", "numerator", "denominator")):
        raise M22AdjudicationError(f"{name} has ambiguous count/rate fields")
    count = value["count"]
    total = value["total"]
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise M22AdjudicationError(f"{name}.count must be a non-negative integer")
    if isinstance(total, bool) or not isinstance(total, int) or total != expected_total:
        raise M22AdjudicationError(f"{name}.total must equal {expected_total}")
    if count > total:
        raise M22AdjudicationError(f"{name}.count cannot exceed total")
    return count / total


def _rate_scalar(value: Any, name: str) -> float:
    if isinstance(value, Mapping):
        if "rate" not in value or any(
            key in value for key in ("count", "total", "numerator", "denominator")
        ):
            raise M22AdjudicationError(f"{name} must contain one unambiguous rate field")
        value = value["rate"]
    rate = _finite(value, name)
    if not 0.0 <= rate <= 1.0:
        raise M22AdjudicationError(f"{name} must be within [0,1]")
    return rate


def _lookup(payload: Mapping[str, Any], aliases: Sequence[str], name: str) -> Any:
    scopes: list[Mapping[str, Any]] = [payload]
    for key in ("metrics", "redlines", "m22", "gates", "pre_crossing_stage3_stage4"):
        value = payload.get(key)
        if isinstance(value, Mapping):
            scopes.append(value)
    for scope in scopes:
        for alias in aliases:
            if alias in scope:
                return scope[alias]
    raise M22AdjudicationError(f"evidence row is missing finite metric {name}")


def _hinge_velocity_p95(payload: Mapping[str, Any]) -> float:
    direct = (
        "hinge_velocity_p95",
        "hinge_vel_p95",
        "hinge_velocity_p95_rad_s",
    )
    direct_scopes: list[Mapping[str, Any]] = [payload]
    for key in ("metrics", "redlines", "m22", "gates", "pre_crossing_stage3_stage4"):
        value = payload.get(key)
        if isinstance(value, Mapping):
            direct_scopes.append(value)
    for scope in direct_scopes:
        for alias in direct:
            if alias in scope:
                value = _finite(scope[alias], "hinge_velocity_p95")
                if value < 0.0:
                    raise M22AdjudicationError("hinge_velocity_p95 must be non-negative")
                return value
    scopes: list[Mapping[str, Any]] = []
    for key in ("metrics", "redlines", "m22", "pre_crossing_stage3_stage4"):
        value = payload.get(key)
        if isinstance(value, Mapping):
            scopes.append(value)
    for scope in scopes:
        nested = scope.get("hinge_velocity", scope.get("door_hinge_joint_vel"))
        if isinstance(nested, Mapping) and "p95" in nested:
            value = _finite(nested["p95"], "hinge_velocity.p95")
            if value < 0.0:
                raise M22AdjudicationError("hinge_velocity.p95 must be non-negative")
            return value
    raise M22AdjudicationError("evidence row is missing finite hinge-velocity p95")


def normalize_metrics(row: Mapping[str, Any], topology: str) -> dict[str, float]:
    expected_total = TOPOLOGY_COUNTS[topology]
    return {
        "goal_rate": _count_total(
            _lookup(row, ("goal", "goal_reached", "goal_pooled"), "goal"),
            "goal",
            expected_total,
        ),
        "complete_rate": _count_total(
            _lookup(row, ("complete", "completion", "complete_pooled"), "complete"),
            "complete",
            expected_total,
        ),
        "crossing_rate": _count_total(
            _lookup(
                row,
                ("crossing_while_holding", "crossing_held", "crossing_pooled"),
                "crossing",
            ),
            "crossing",
            expected_total,
        ),
        "bilateral_rate": _rate_scalar(
            _lookup(row, ("bilateral", "bilateral_rate", "pre_crossing_bilateral_rate"), "bilateral"),
            "bilateral",
        ),
        "coasting_rate": _rate_scalar(
            _lookup(row, ("coasting", "coasting_rate", "pre_crossing_coasting_rate"), "coasting"),
            "coasting",
        ),
        "over_force_rate": _rate_scalar(
            _lookup(row, ("over_force", "over_force_rate", "pre_crossing_over_force_rate"), "over_force"),
            "over_force",
        ),
        "hinge_velocity_p95": _hinge_velocity_p95(row),
    }


def _evidence_rows(evidence: Any) -> list[Mapping[str, Any]]:
    if isinstance(evidence, Mapping):
        value = evidence.get("rows", evidence.get("candidates"))
        if value is None:
            raise M22AdjudicationError("evidence mapping must contain rows or candidates")
        if isinstance(value, Mapping):
            rows: list[Mapping[str, Any]] = []
            for key, item in value.items():
                if not isinstance(item, Mapping):
                    raise M22AdjudicationError("every evidence row must be a mapping")
                if item.get("candidate_id") != key:
                    raise M22AdjudicationError("evidence mapping key conflicts with candidate_id")
                rows.append(item)
            return rows
        if isinstance(value, list):
            return value
    if isinstance(evidence, list):
        return evidence
    raise M22AdjudicationError("evidence must be a row list or mapping")


def _evidence_index(evidence: Any) -> dict[str, Mapping[str, Any]]:
    index: dict[str, Mapping[str, Any]] = {}
    for row in _evidence_rows(evidence):
        if not isinstance(row, Mapping):
            raise M22AdjudicationError("every evidence row must be a mapping")
        candidate_id = row.get("candidate_id")
        if not isinstance(candidate_id, str) or not candidate_id:
            raise M22AdjudicationError("every evidence row requires candidate_id")
        if candidate_id in index:
            raise M22AdjudicationError(f"duplicate evidence candidate_id {candidate_id!r}")
        index[candidate_id] = row
    return index


def _strict_status(row: Mapping[str, Any]) -> str:
    status = row.get("strict_status")
    if status is None and isinstance(row.get("admission"), Mapping):
        status = row["admission"].get("strict_status")
    if status not in VALID_STATUSES:
        raise M22AdjudicationError(
            "every candidate requires explicit strict_status STRICT_VALID or STRICT_INVALID"
        )
    return str(status)


def _passes(metrics: Mapping[str, float], topology: str = CANONICAL_TOPOLOGY) -> bool:
    if topology not in TOPOLOGY_COUNTS:
        raise M22AdjudicationError(f"unsupported evaluation topology {topology!r}")
    required_success = 15.0 / 16.0 if topology == CANONICAL_TOPOLOGY else 46.0 / 48.0
    return (
        metrics["goal_rate"] >= required_success
        and metrics["complete_rate"] >= required_success
        and metrics["crossing_rate"] >= required_success
        and metrics["bilateral_rate"] >= 0.99
        and metrics["coasting_rate"] < 0.02
        and metrics["over_force_rate"] < 0.02
    )


def _dominates(left: Mapping[str, float], right: Mapping[str, float]) -> bool:
    maximize = ("goal_rate", "complete_rate", "crossing_rate", "bilateral_rate")
    minimize = ("coasting_rate", "hinge_velocity_p95", "over_force_rate")
    comparisons = [left[key] >= right[key] for key in maximize] + [
        left[key] <= right[key] for key in minimize
    ]
    strict = [left[key] > right[key] for key in maximize] + [
        left[key] < right[key] for key in minimize
    ]
    return all(comparisons) and any(strict)


M22_LEXICOGRAPHIC_MAXIMIZE = (
    "goal_rate",
    "complete_rate",
    "crossing_rate",
    "bilateral_rate",
)
M22_LEXICOGRAPHIC_MINIMIZE = (
    "coasting_rate",
    "over_force_rate",
    "hinge_velocity_p95",
)


def _mechanical_rank(metrics: Mapping[str, float]) -> tuple[float, ...]:
    return tuple(metrics[key] for key in M22_LEXICOGRAPHIC_MAXIMIZE) + tuple(
        -metrics[key] for key in M22_LEXICOGRAPHIC_MINIMIZE
    )


def select_unique_mechanical_candidate(
    candidates: Sequence[Mapping[str, Any]],
) -> Mapping[str, Any]:
    if not candidates:
        raise M22AdjudicationError("no strict-valid candidate passes every M22 redline")
    best_rank = max(_mechanical_rank(candidate["metrics"]) for candidate in candidates)
    selected = [
        candidate
        for candidate in candidates
        if _mechanical_rank(candidate["metrics"]) == best_rank
    ]
    if len(selected) != 1:
        raise M22AdjudicationError(
            "M22 selection is ambiguous: the complete lexicographic redline vector "
            f"is tied for {len(selected)} candidates"
        )
    return selected[0]


def adjudicate(manifest: Mapping[str, Any], evidence: Any) -> dict[str, Any]:
    candidates = _validate_manifest(manifest)
    index = _evidence_index(evidence)
    candidate_ids = {str(candidate["candidate_id"]) for candidate in candidates}
    evidence_ids = set(index)
    extra = evidence_ids - candidate_ids
    missing = candidate_ids - evidence_ids
    if extra:
        raise M22AdjudicationError(f"evidence contains extra candidate identities: {sorted(extra)}")
    if missing:
        raise M22AdjudicationError(f"missing explicit evidence rows: {sorted(missing)}")

    rows: list[dict[str, Any]] = []
    passing: list[dict[str, Any]] = []
    for candidate in candidates:
        candidate_id = str(candidate["candidate_id"])
        evidence_row = index[candidate_id]
        topology = _validate_evidence_binding(candidate, evidence_row)
        status = _strict_status(evidence_row)
        row: dict[str, Any] = {
            "candidate": dict(candidate),
            "strict_status": status,
            "evaluation_topology": topology,
            "artifact": evidence_row["artifact"],
            "checkpoint_path": evidence_row["checkpoint_path"],
            "checkpoint_sha256": evidence_row["checkpoint_sha256"],
            "evidence_provenance": evidence_row["artifact"],
        }
        if topology == CANONICAL_TOPOLOGY:
            row["evaluation_seed"] = evidence_row["evaluation_seed"]
        else:
            row["evaluation_seeds"] = list(evidence_row["evaluation_seeds"])
            row["source_artifacts"] = list(evidence_row["source_artifacts"])
        if status == "STRICT_VALID":
            metrics = normalize_metrics(evidence_row, topology)
            row["metrics"] = metrics
            row["passes_redlines"] = _passes(metrics, topology)
            if row["passes_redlines"]:
                passing.append(row)
        else:
            row["passes_redlines"] = False
            row["exclusion_reason"] = evidence_row.get("reason", "explicit STRICT_INVALID")
        rows.append(row)
    admitted_topologies = {row["evaluation_topology"] for row in rows}
    if len(admitted_topologies) != 1:
        raise M22AdjudicationError(
            "M22 adjudication cannot mix evaluation_topology values: "
            f"{sorted(admitted_topologies)}"
        )
    admitted_topology = next(iter(admitted_topologies))
    if admitted_topology == CANONICAL_TOPOLOGY and any(
        row.get("evaluation_seed") != 0 for row in rows
    ):
        raise M22AdjudicationError("canonical16 adjudication requires a common evaluation_seed=0")
    selected = select_unique_mechanical_candidate(passing)
    return {
        "schema": SCHEMA,
        "status": "PASS",
        "candidate_count": len(rows),
        "strict_invalid_count": sum(row["strict_status"] == "STRICT_INVALID" for row in rows),
        "rows": rows,
        "passing_candidates": [row["candidate"]["candidate_id"] for row in passing],
        "selection_policy": {
            "method": "fixed_lexicographic_redline_vector",
            "maximize": list(M22_LEXICOGRAPHIC_MAXIMIZE),
            "minimize": list(M22_LEXICOGRAPHIC_MINIMIZE),
            "exact_vector_tie": "FAIL",
            "forbidden_tie_breaks": ["scalar_reward", "filename", "checkpoint_step"],
        },
        "selected_checkpoint": selected["candidate"],
        "selected_metrics": selected["metrics"],
    }


def write_outputs(report: Mapping[str, Any], output_json: Path, output_md: Path) -> None:
    Path(output_json).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# A2 Piper v19 M22 adjudication",
        "",
        f"Status: **{report['status']}**",
        "",
        "| Candidate | Strict evidence | Redlines |",
        "|---|---|---|",
    ]
    for row in report["rows"]:
        candidate = row["candidate"]
        lines.append(
            f"| `{candidate['candidate_id']}` | {row['strict_status']} | "
            f"{'PASS' if row['passes_redlines'] else 'EXCLUDED'} |"
        )
    selected = report["selected_checkpoint"]
    lines.extend(["", f"Selected checkpoint: `{selected['path']}`", f"SHA-256: `{selected['sha256']}`"])
    Path(output_md).write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-md", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
    report = adjudicate(manifest, evidence)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    write_outputs(report, args.output_json, args.output_md)
    print(f"selected checkpoint: {report['selected_checkpoint']['path']}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except M22AdjudicationError as exc:
        print(f"M22 FAIL: {exc}", file=sys.stderr)
        sys.exit(2)
