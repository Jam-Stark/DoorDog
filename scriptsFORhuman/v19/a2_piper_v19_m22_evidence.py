"""Build explicit strict M22 evidence rows from completed canonical16 eval artifacts."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Mapping, Sequence


SCHEMA = "a2_piper_v19_m22_evidence_v1"
MANIFEST_SCHEMA = "a2_piper_v19_m22_candidate_manifest_v1"
QUEUE_SCHEMA = "a2_piper_v19_m22_queue_v1"
POOLED_SOURCES_SCHEMA = "a2_piper_v19_m22_pooled_sources_v1"
RESULT_FILENAME = "a2_v14_per_env_records.json"
TRACE_FILENAME = "stage2_5_step_trace.json"
METRICS_FILENAME = "metrics_eval.json"
EXIT_FILENAME = "eval_exit_code.txt"
EXPECTED_EPISODES = 16
EXPECTED_SEEDS = (0, 1, 2)
COASTING_THRESHOLD = 0.1


class M22EvidenceError(ValueError):
    """Raised when queue execution evidence is incomplete or inconsistent."""


def _load_v17_reporter() -> ModuleType:
    source = Path(__file__).parents[1] / "v17" / "a2_piper_v17_bucket_report.py"
    spec = importlib.util.spec_from_file_location("a2_piper_v17_reporter_for_v19_m22", source)
    if spec is None or spec.loader is None:
        raise M22EvidenceError(f"cannot load strict reporter from {source}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


V17 = _load_v17_reporter()


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise M22EvidenceError(f"cannot load JSON {path}: {exc}") from exc


def _candidate_index(manifest: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise M22EvidenceError("candidate manifest schema is invalid")
    candidates = manifest.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise M22EvidenceError("candidate manifest must contain candidates")
    index: dict[str, Mapping[str, Any]] = {}
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            raise M22EvidenceError("candidate rows must be mappings")
        candidate_id = candidate.get("candidate_id")
        if not isinstance(candidate_id, str) or not candidate_id or candidate_id in index:
            raise M22EvidenceError("candidate identities must be unique non-empty strings")
        index[candidate_id] = candidate
    return index


def _queue_index(queue: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    if queue.get("schema") != QUEUE_SCHEMA or queue.get("serial") is not True:
        raise M22EvidenceError("queue schema/serial contract is invalid")
    rows = queue.get("rows")
    if not isinstance(rows, list) or len(rows) != queue.get("candidate_count"):
        raise M22EvidenceError("queue candidate topology is invalid")
    index: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping) or not isinstance(row.get("candidate"), Mapping):
            raise M22EvidenceError("queue rows require candidate mappings")
        candidate_id = row["candidate"].get("candidate_id")
        if not isinstance(candidate_id, str) or candidate_id in index:
            raise M22EvidenceError("queue candidate identities must be unique")
        index[candidate_id] = row
    return index


def _exit_code(artifact: Path) -> int:
    path = artifact / EXIT_FILENAME
    try:
        text = path.read_text(encoding="utf-8").strip()
        value = int(text)
    except (OSError, ValueError) as exc:
        raise M22EvidenceError(f"missing or invalid eval exit code: {path}") from exc
    if text != str(value) or value < 0:
        raise M22EvidenceError(f"eval exit code is not canonical: {path}")
    return value


def _artifact_components(artifact: Path, expected_seed: int) -> tuple[Any, Any, list[str]]:
    result_path = artifact / RESULT_FILENAME
    trace_path = artifact / TRACE_FILENAME
    metrics_path = artifact / METRICS_FILENAME
    records = V17.load_result(result_path, expected_seed=expected_seed)
    traces = V17.load_trace(
        trace_path,
        expected_seed=expected_seed,
        result_records=records,
    )
    if len(records) != EXPECTED_EPISODES:
        raise M22EvidenceError(f"seed{expected_seed} result count must equal {EXPECTED_EPISODES}")

    metrics_payload = _load_json(metrics_path)
    goal_flags = metrics_payload.get("episode_goal_reached")
    terminal_reasons = metrics_payload.get("episode_terminal_reasons")
    if (
        not isinstance(goal_flags, list)
        or len(goal_flags) != EXPECTED_EPISODES
        or any(not isinstance(value, bool) for value in goal_flags)
    ):
        raise M22EvidenceError(
            f"seed{expected_seed} metrics_eval episode_goal_reached must contain 16 bools"
        )
    if (
        not isinstance(terminal_reasons, list)
        or len(terminal_reasons) != EXPECTED_EPISODES
        or any(not isinstance(value, str) or not value for value in terminal_reasons)
    ):
        raise M22EvidenceError(
            f"seed{expected_seed} metrics_eval episode_terminal_reasons must contain 16 strings"
        )

    goal_count = sum(record.goal_reached for record in records)
    if goal_count != sum(goal_flags):
        raise M22EvidenceError(f"seed{expected_seed} result/metrics goal count mismatch")
    return records, traces, terminal_reasons


def _metrics_for_valid_artifacts(artifacts: Mapping[int, Path]) -> dict[str, Any]:
    if not artifacts or set(artifacts) not in ({0}, set(EXPECTED_SEEDS)):
        raise M22EvidenceError("metrics require either seed0 or exact seeds 0,1,2")

    records_by_seed: dict[int, Any] = {}
    traces_by_seed: dict[int, Any] = {}
    terminal_reasons: list[str] = []
    for seed in sorted(artifacts):
        records, traces, reasons = _artifact_components(artifacts[seed], seed)
        records_by_seed[seed] = records
        traces_by_seed[seed] = traces
        terminal_reasons.extend(reasons)

    all_records = [
        record
        for seed in sorted(records_by_seed)
        for record in records_by_seed[seed]
    ]
    pre_crossing = [
        trace
        for seed in sorted(traces_by_seed)
        for rows in traces_by_seed[seed].values()
        for trace in rows
        if trace.stage in (3, 4) and not trace.root_x_ever_crossed
    ]
    if not pre_crossing:
        raise M22EvidenceError("pre-crossing stage3/4 denominator is empty")
    denominator = len(pre_crossing)
    bilateral = sum(trace.both_contact for trace in pre_crossing) / denominator
    coasting = sum(
        trace.door_hinge_joint_vel > COASTING_THRESHOLD and not trace.both_contact
        for trace in pre_crossing
    ) / denominator
    over_force = sum(trace.over_force for trace in pre_crossing) / denominator
    hinge_stats = V17.V16._stats([trace.door_hinge_joint_vel for trace in pre_crossing])

    return {
        "goal": {
            "count": sum(record.goal_reached for record in all_records),
            "total": len(all_records),
        },
        "complete": {
            "count": sum(reason == "complete" for reason in terminal_reasons),
            "total": len(all_records),
        },
        "crossing_while_holding": {
            "count": sum(record.crossing_while_holding is True for record in all_records),
            "total": len(all_records),
        },
        "bilateral": bilateral,
        "coasting": coasting,
        "over_force": over_force,
        "hinge_velocity_p95": hinge_stats["p95"],
    }


def _metrics_for_valid_artifact(artifact: Path) -> dict[str, Any]:
    return _metrics_for_valid_artifacts({0: artifact})


def _pooled_source_index(payload: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    if payload.get("schema") != POOLED_SOURCES_SCHEMA:
        raise M22EvidenceError("pooled sources schema is invalid")
    rows = payload.get("rows")
    if not isinstance(rows, list) or not rows:
        raise M22EvidenceError("pooled sources must contain rows")
    index: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise M22EvidenceError("pooled source rows must be mappings")
        candidate_id = row.get("candidate_id")
        if not isinstance(candidate_id, str) or not candidate_id or candidate_id in index:
            raise M22EvidenceError("pooled source candidate identities must be unique")
        sources = row.get("source_artifacts")
        if not isinstance(sources, Mapping) or set(sources) != {"seed0", "seed1", "seed2"}:
            raise M22EvidenceError(
                "pooled source rows require exact seed0/seed1/seed2 artifacts"
            )
        index[candidate_id] = row
    return index


def build_pooled_evidence(
    manifest: Mapping[str, Any],
    pooled_sources: Mapping[str, Any],
    pooled_artifact: Path,
) -> dict[str, Any]:
    candidates = _candidate_index(manifest)
    sources = _pooled_source_index(pooled_sources)
    if set(candidates) != set(sources):
        raise M22EvidenceError("manifest and pooled source candidate identities differ")

    evidence_rows: list[dict[str, Any]] = []
    for candidate_id, candidate in candidates.items():
        source_row = sources[candidate_id]
        if source_row.get("checkpoint_path") != candidate["path"]:
            raise M22EvidenceError(
                f"pooled source checkpoint path mismatch for {candidate_id}"
            )
        if source_row.get("checkpoint_sha256") != candidate["sha256"]:
            raise M22EvidenceError(
                f"pooled source checkpoint SHA-256 mismatch for {candidate_id}"
            )
        source_values = source_row["source_artifacts"]
        artifacts = {
            seed: Path(str(source_values[f"seed{seed}"])).expanduser().resolve()
            for seed in EXPECTED_SEEDS
        }
        if any(not artifact.is_dir() for artifact in artifacts.values()):
            raise M22EvidenceError(
                f"pooled source artifact directory is missing for {candidate_id}"
            )
        exit_codes = {seed: _exit_code(artifact) for seed, artifact in artifacts.items()}
        row: dict[str, Any] = {
            "candidate_id": candidate_id,
            "artifact": str(pooled_artifact.expanduser().resolve()),
            "checkpoint_path": candidate["path"],
            "checkpoint_sha256": candidate["sha256"],
            "evaluation_topology": "pooled48",
            "evaluation_seeds": list(EXPECTED_SEEDS),
            "source_artifacts": [str(artifacts[seed]) for seed in EXPECTED_SEEDS],
        }
        nonzero = {seed: code for seed, code in exit_codes.items() if code != 0}
        if nonzero:
            row["strict_status"] = "STRICT_INVALID"
            row["reason"] = f"nonzero eval exits: {nonzero}"
        else:
            try:
                row["metrics"] = _metrics_for_valid_artifacts(artifacts)
            except (M22EvidenceError, V17.V17ReportError) as exc:
                row["strict_status"] = "STRICT_INVALID"
                row["reason"] = f"{type(exc).__name__}: {exc}"
            else:
                row["strict_status"] = "STRICT_VALID"
        evidence_rows.append(row)
    return {"schema": SCHEMA, "rows": evidence_rows}


def build_evidence(manifest: Mapping[str, Any], queue: Mapping[str, Any]) -> dict[str, Any]:
    candidates = _candidate_index(manifest)
    queue_rows = _queue_index(queue)
    if set(candidates) != set(queue_rows):
        raise M22EvidenceError("manifest and queue candidate identities differ")

    evidence_rows: list[dict[str, Any]] = []
    for candidate_id, candidate in candidates.items():
        queue_row = queue_rows[candidate_id]
        if dict(queue_row["candidate"]) != dict(candidate):
            raise M22EvidenceError(f"queue candidate binding mismatch for {candidate_id}")
        artifact = Path(str(queue_row.get("artifact", ""))).expanduser().resolve()
        if not artifact.is_dir():
            raise M22EvidenceError(f"artifact directory does not exist: {artifact}")
        exit_code = _exit_code(artifact)
        row: dict[str, Any] = {
            "candidate_id": candidate_id,
            "artifact": str(artifact),
            "checkpoint_path": candidate["path"],
            "checkpoint_sha256": candidate["sha256"],
            "evaluation_topology": "canonical16",
            "evaluation_seed": 0,
        }
        if exit_code != 0:
            row["strict_status"] = "STRICT_INVALID"
            row["reason"] = f"eval exit code {exit_code}; see {artifact / 'runner.log'}"
        else:
            try:
                row["metrics"] = _metrics_for_valid_artifact(artifact)
            except (M22EvidenceError, V17.V17ReportError) as exc:
                row["strict_status"] = "STRICT_INVALID"
                row["reason"] = f"{type(exc).__name__}: {exc}"
            else:
                row["strict_status"] = "STRICT_VALID"
        evidence_rows.append(row)
    return {"schema": SCHEMA, "rows": evidence_rows}


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--queue", type=Path)
    source.add_argument("--pooled-sources", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.queue is not None:
        evidence = build_evidence(_load_json(args.manifest), _load_json(args.queue))
    else:
        evidence = build_pooled_evidence(
            _load_json(args.manifest),
            _load_json(args.pooled_sources),
            args.output,
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    valid = sum(row["strict_status"] == "STRICT_VALID" for row in evidence["rows"])
    print(f"M22 evidence: {args.output}; strict-valid={valid}/{len(evidence['rows'])}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except M22EvidenceError as exc:
        print(f"M22 EVIDENCE FAIL: {exc}", file=sys.stderr)
        raise SystemExit(2)
