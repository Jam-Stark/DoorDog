"""Build strict pooled v19 endpoint metrics and companion bucket/slip reports."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Mapping, Sequence

import yaml


SCHEMA = "a2_piper_v19_endpoint_report_v1"
EXPECTED_SEEDS = (0, 1, 2)
EXPECTED_ENVS = 16
REWARD_TERMS = (
    "a2_stage3_stage4_hold_and_drive",
    "a2_corridor_door_wide",
    "a2_corridor_clean_passage",
    "penalty_a2_posture_command_l1",
)


class V19EndpointReportError(ValueError):
    """Raised when endpoint provenance or telemetry is incomplete."""


def _load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise V19EndpointReportError(f"cannot load reporter module {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


V17 = _load_module(
    "a2_piper_v17_reporter_for_v19_endpoint",
    Path(__file__).parents[1] / "v17" / "a2_piper_v17_bucket_report.py",
)
SLIP = _load_module(
    "a2_piper_v18_slip_for_v19_endpoint",
    Path(__file__).parents[1] / "v18" / "a2_piper_v18_slip_report.py",
)


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise V19EndpointReportError(f"cannot load JSON {path}: {exc}") from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _quantile(values: Sequence[float], q: float) -> float:
    if not values:
        raise V19EndpointReportError("cannot summarize an empty metric")
    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _stats(values: Sequence[float]) -> dict[str, Any]:
    return {
        "n": len(values),
        "p50": _quantile(values, 0.50),
        "p95": _quantile(values, 0.95),
        "min": min(values),
        "max": max(values),
    }


def _validate_artifact(artifact: Path, checkpoint: Path, seed: int) -> None:
    config_path = artifact / ".hydra" / "config.yaml"
    if not config_path.is_file():
        raise V19EndpointReportError(f"artifact lacks config: {config_path}")
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(config, Mapping):
        raise V19EndpointReportError(f"artifact config is not a mapping: {config_path}")
    configured_checkpoint = Path(str(config.get("checkpoint", ""))).expanduser().resolve()
    if configured_checkpoint != checkpoint:
        raise V19EndpointReportError(
            f"artifact checkpoint mismatch for seed{seed}: {configured_checkpoint} != {checkpoint}"
        )
    if config.get("seed") != seed or config.get("num_envs") != EXPECTED_ENVS:
        raise V19EndpointReportError(f"artifact seed/num_envs mismatch for seed{seed}")
    exit_path = artifact / "eval_exit_code.txt"
    try:
        exit_code = int(exit_path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError) as exc:
        raise V19EndpointReportError(f"missing eval exit code for seed{seed}") from exc
    if exit_code != 0:
        raise V19EndpointReportError(f"seed{seed} eval exit code is {exit_code}")


def _raw_trace_by_env(artifact: Path, seed: int) -> dict[int, list[Mapping[str, Any]]]:
    path = artifact / "stage2_5_step_trace.json"
    payload = _load_json(path)
    if not isinstance(payload, list):
        raise V19EndpointReportError(f"trace must be a list: {path}")
    grouped: dict[int, list[Mapping[str, Any]]] = {env_id: [] for env_id in range(EXPECTED_ENVS)}
    for row in payload:
        if not isinstance(row, Mapping):
            raise V19EndpointReportError(f"trace row must be a mapping: {path}")
        if row.get("seed", seed) != seed:
            raise V19EndpointReportError(f"trace seed mismatch in {path}")
        env_id = row.get("env_id")
        if isinstance(env_id, bool) or not isinstance(env_id, int) or env_id not in grouped:
            raise V19EndpointReportError(f"invalid trace env_id in {path}")
        grouped[env_id].append(row)
    if any(not rows for rows in grouped.values()):
        raise V19EndpointReportError(f"trace must contain every env0..15: {path}")
    return grouped


def build_report(
    group: str,
    checkpoint: Path,
    artifacts: Mapping[int, Path],
    output_dir: Path,
) -> dict[str, Any]:
    checkpoint = checkpoint.expanduser().resolve()
    if not checkpoint.is_file():
        raise V19EndpointReportError(f"checkpoint does not exist: {checkpoint}")
    if set(artifacts) != set(EXPECTED_SEEDS):
        raise V19EndpointReportError("endpoint requires exactly seed0, seed1, seed2 artifacts")

    result_sets: dict[int, Any] = {}
    trace_sets: dict[int, Any] = {}
    raw_traces: dict[int, dict[int, list[Mapping[str, Any]]]] = {}
    slip_sets: dict[int, Any] = {}
    input_paths: dict[str, Path] = {}
    for seed in EXPECTED_SEEDS:
        artifact = artifacts[seed].expanduser().resolve()
        _validate_artifact(artifact, checkpoint, seed)
        result_path = artifact / "a2_v14_per_env_records.json"
        trace_path = artifact / "stage2_5_step_trace.json"
        result_sets[seed] = V17.load_result(result_path, expected_seed=seed)
        trace_sets[seed] = V17.load_trace(
            trace_path,
            expected_seed=seed,
            result_records=result_sets[seed],
        )
        slip_sets[seed] = list(SLIP.load_trace(artifact, expected_seed=seed).values())
        raw_traces[seed] = _raw_trace_by_env(artifact, seed)
        input_paths[f"seed{seed}_result"] = result_path
        input_paths[f"seed{seed}_trace"] = trace_path

    output_dir.mkdir(parents=True, exist_ok=True)
    bucket = V17.build_report(result_sets, trace_sets, group=group)
    bucket_paths = V17.write_outputs(bucket, output_dir, input_paths)
    slip = SLIP.build_report(slip_sets)
    slip_paths = SLIP.write_outputs(slip, output_dir / "a2_piper_v19_slip")

    all_records = [
        record
        for seed in EXPECTED_SEEDS
        for record in result_sets[seed]
    ]
    canonical = result_sets[0]
    final_rows: dict[tuple[int, int], Mapping[str, Any]] = {}
    held_hinge: list[float] = []
    arm_j1_delta: list[float] = []
    for seed in EXPECTED_SEEDS:
        for env_id in range(EXPECTED_ENVS):
            rows = raw_traces[seed][env_id]
            final_rows[(seed, env_id)] = rows[-1]
            held_rows = [
                row
                for row in rows
                if row["stage_buf"] in (3, 4, 5) and row["both_contact"] is True
            ]
            if not held_rows:
                continue
            held_hinge.append(max(float(row["door_hinge_joint_pos"]) for row in held_rows))
            names = held_rows[0].get("arm_joint_names")
            if not isinstance(names, list) or "arm_j1" not in names:
                raise V19EndpointReportError(f"seed{seed} env{env_id} lacks arm_j1 telemetry")
            j1 = names.index("arm_j1")
            if any(row.get("arm_joint_names") != names for row in held_rows):
                raise V19EndpointReportError(f"seed{seed} env{env_id} arm joint order changed")
            arm_j1_delta.append(
                float(held_rows[-1]["arm_joint_pos"][j1])
                - float(held_rows[0]["arm_joint_pos"][j1])
            )

    release_records = [record for record in all_records if record.hinge_at_release is not None]
    release_hinge = [float(record.hinge_at_release) for record in release_records]
    release_force = [float(record.post_release_body_force_max) for record in release_records]
    pre_crossing = [
        trace
        for seed in EXPECTED_SEEDS
        for rows in trace_sets[seed].values()
        for trace in rows
        if trace.stage in (3, 4) and not trace.root_x_ever_crossed
    ]
    if not pre_crossing:
        raise V19EndpointReportError("pre-crossing stage3/4 denominator is empty")
    pre_denominator = len(pre_crossing)

    reward_means: dict[str, float] = {}
    for term in REWARD_TERMS:
        values = []
        for record in all_records:
            if term not in record.reward_episode_sums:
                raise V19EndpointReportError(f"missing reward term {term}")
            values.append(float(record.reward_episode_sums[term]))
        reward_means[term] = sum(values) / len(values)

    report = {
        "schema": SCHEMA,
        "group": group,
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": _sha256(checkpoint),
        "source_artifacts": {f"seed{seed}": str(artifacts[seed].resolve()) for seed in EXPECTED_SEEDS},
        "goal": {
            "canonical": {"count": sum(record.goal_reached for record in canonical), "total": 16},
            "pooled": {"count": sum(record.goal_reached for record in all_records), "total": 48},
            "by_seed": {
                f"seed{seed}": {
                    "count": sum(record.goal_reached for record in result_sets[seed]),
                    "total": 16,
                }
                for seed in EXPECTED_SEEDS
            },
        },
        "complete": {
            "canonical": {
                "count": sum(final_rows[(0, env)]["terminal_reasons"] == "complete" for env in range(16)),
                "total": 16,
            },
            "pooled": {
                "count": sum(row["terminal_reasons"] == "complete" for row in final_rows.values()),
                "total": 48,
            },
        },
        "crossing_while_holding": {
            "canonical": {
                "count": sum(record.crossing_while_holding is True for record in canonical),
                "total": 16,
            },
            "pooled": {
                "count": sum(record.crossing_while_holding is True for record in all_records),
                "total": 48,
            },
        },
        "held_carry": {
            "denominator": len(held_hinge),
            "hinge_rad": _stats(held_hinge),
            "hinge_at_least_1_45": sum(value >= 1.45 for value in held_hinge),
            "hinge_at_least_1_50": sum(value >= 1.50 for value in held_hinge),
            "arm_j1_delta_rad": _stats(arm_j1_delta),
            "arm_j1_delta_gt_0_3": sum(value > 0.3 for value in arm_j1_delta),
        },
        "overspeed_terminations": {
            "count": sum(
                row["terminal_reasons"] == "upper_dof_overspeed"
                for row in final_rows.values()
            ),
            "total": 48,
        },
        "opening_slip": slip["pooled"]["opening_stage3"],
        "corridor_slip_observability": slip["pooled"]["corridor_stages4_5"],
        "release": {
            "denominator": len(release_records),
            "hinge_rad": _stats(release_hinge),
            "post_release_body_contact_count": sum(
                record.post_release_body_contact is True for record in release_records
            ),
            "post_release_body_force_n": _stats(release_force),
        },
        "pre_crossing_stage3_stage4": {
            "denominator": pre_denominator,
            "bilateral_rate": sum(trace.both_contact for trace in pre_crossing) / pre_denominator,
            "coasting_rate": sum(
                trace.door_hinge_joint_vel > 0.1 and not trace.both_contact
                for trace in pre_crossing
            )
            / pre_denominator,
            "over_force_rate": sum(trace.over_force for trace in pre_crossing) / pre_denominator,
        },
        "reward_episode_sums_unit": "episode-sum",
        "reward_episode_sums_mean": reward_means,
        "terminal_reason_counts": {
            reason: sum(row["terminal_reasons"] == reason for row in final_rows.values())
            for reason in sorted({row["terminal_reasons"] for row in final_rows.values()})
        },
        "companion_outputs": {
            "bucket_json": str(bucket_paths[0]),
            "bucket_csv": str(bucket_paths[1]),
            "bucket_md": str(bucket_paths[2]),
            "slip_json": str(slip_paths[0]),
            "slip_csv": str(slip_paths[1]),
            "slip_md": str(slip_paths[2]),
        },
    }
    return report


def write_outputs(report: Mapping[str, Any], output_dir: Path) -> tuple[Path, Path]:
    json_path = output_dir / "a2_piper_v19_endpoint_report.json"
    md_path = output_dir / "a2_piper_v19_endpoint_report.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# A2 Piper v19 endpoint report",
        "",
        f"Group: {report['group']}",
        f"Checkpoint: {report['checkpoint']}",
        "",
        "## Metrics",
        "",
        "~~~json",
        json.dumps(
            {
                key: report[key]
                for key in (
                    "goal",
                    "complete",
                    "crossing_while_holding",
                    "held_carry",
                    "overspeed_terminations",
                    "opening_slip",
                    "release",
                    "pre_crossing_stage3_stage4",
                    "reward_episode_sums_unit",
                    "reward_episode_sums_mean",
                    "terminal_reason_counts",
                )
            },
            indent=2,
            sort_keys=True,
        ),
        "~~~",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group", required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    for seed in EXPECTED_SEEDS:
        parser.add_argument(f"--seed{seed}-artifact", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    artifacts = {
        seed: getattr(args, f"seed{seed}_artifact")
        for seed in EXPECTED_SEEDS
    }
    report = build_report(args.group, args.checkpoint, artifacts, args.output_dir)
    paths = write_outputs(report, args.output_dir)
    print(f"v19 endpoint JSON: {paths[0]}")
    print(f"v19 endpoint Markdown: {paths[1]}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (V19EndpointReportError, V17.V17ReportError, SLIP.SlipReportError) as exc:
        print(f"v19 ENDPOINT FAIL: {exc}", file=sys.stderr)
        raise SystemExit(2)
