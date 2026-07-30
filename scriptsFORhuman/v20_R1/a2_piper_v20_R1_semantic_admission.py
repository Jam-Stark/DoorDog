"""Strict CPU/static semantic admission for the R1 chain."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _r1_common import (  # noqa: E402
    PLAN_ID,
    R1Error,
    RUNTIME_SEMANTIC_PASS,
    exact_digest,
    load_json,
    write_json_no_overwrite,
)

SCHEMA = "a2_piper_v20_R1_semantic_admission_v3"
REQUIRED_EVIDENCE = (
    "unit_semantics.json",
    "snapshot_ring.json",
    "schedule_callbacks.json",
    "telemetry_schema.json",
)
CANONICAL_GROUPS = ("G1", "G2", "G3", "G4", "G5", "G6", "G7")


def build_semantic_commands(*, repo_root: Path, evidence_dir: Path) -> list[list[str]]:
    if evidence_dir.exists() and evidence_dir.is_symlink():
        raise R1Error("semantic evidence directory may not be a symlink")
    root = repo_root.resolve()
    return [
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "gr00t/rl/tests/test_a2_v20_R1_curriculum.py",
            "gr00t/rl/tests/test_a2_v20_R1_staged_reset_guard.py",
        ],
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "gr00t/rl/tests/test_a2_v20_R1_strict_schema.py",
        ],
        [
            sys.executable,
            "-m",
            "py_compile",
            "gr00t/rl/envs/door/door_open_a2_base.py",
        ],
        [
            sys.executable,
            "-m",
            "scriptsFORhuman.v20_R1.a2_piper_v20_R1_baseline",
            "--repo-root",
            str(root),
            "--output-dir",
            str(root / "logs_eval/base_v20_R1/semantic"),
        ],
    ]


def _validate_evidence(path: Path, *, expected_schema: str | None = None) -> Mapping[str, Any]:
    payload = load_json(path)
    if not isinstance(payload, Mapping):
        raise R1Error(f"semantic evidence must be a mapping: {path}")
    if payload.get("plan_id") != PLAN_ID:
        raise R1Error(f"semantic evidence plan binding mismatch: {path}")
    if expected_schema is not None and payload.get("schema") != expected_schema:
        raise R1Error(f"semantic evidence schema mismatch: {path}")
    status = payload.get("status")
    if status not in {RUNTIME_SEMANTIC_PASS, "STRICT_VALID"}:
        raise R1Error(f"semantic evidence has no typed semantic status: {path}")
    if payload.get("all_true") is True:
        raise R1Error(f"semantic evidence cannot use caller-provided all_true: {path}")
    command = payload.get("command")
    exit_code = payload.get("exit_code")
    if command is not None:
        if not isinstance(command, list) or not command or any(not isinstance(part, str) for part in command):
            raise R1Error(f"semantic evidence command is malformed: {path}")
        if exit_code != 0:
            raise R1Error(f"semantic evidence command did not exit zero: {path}")
    artifact_hash = payload.get("artifact_sha256")
    if artifact_hash is not None:
        exact_digest(artifact_hash, name=f"{path}.artifact_sha256", length=64)
    return payload


def _validate_check_artifact(path: Path, expected_keys: Sequence[str]) -> Mapping[str, Any]:
    payload = _validate_evidence(path)
    checks = payload.get("checks")
    if not isinstance(checks, Mapping):
        raise R1Error(f"semantic check artifact requires explicit checks: {path}")
    missing = [key for key in expected_keys if checks.get(key) is not True]
    if missing:
        raise R1Error(f"semantic check artifact failed required checks {missing}: {path}")
    if len(checks) < len(expected_keys):
        raise R1Error(f"semantic check artifact omits required checks: {path}")
    return payload


def _validate_runtime_artifact(path: Path, *, name: str, minimum_records: int) -> Mapping[str, Any]:
    payload = _validate_evidence(path)
    if payload.get("artifact_name") != name:
        raise R1Error(f"semantic artifact name mismatch: {path}")
    count = payload.get("record_count")
    if isinstance(count, bool) or not isinstance(count, int) or count < minimum_records:
        raise R1Error(f"semantic artifact {name} has insufficient records: {path}")
    provenance = payload.get("provenance")
    if not isinstance(provenance, Mapping) or provenance.get("plan_id") != PLAN_ID:
        raise R1Error(f"semantic artifact {name} has incomplete provenance: {path}")
    return payload


def run_semantic_assertions(
    *,
    output_dir: Path | None = None,
    evidence_dir: Path | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    if evidence_dir is None:
        raise R1Error("semantic admission requires externally produced evidence_dir")
    root = (repo_root or Path(__file__).resolve().parents[2]).resolve()
    evidence_dir = evidence_dir.resolve()
    if not evidence_dir.is_dir() or evidence_dir.is_symlink():
        raise R1Error("semantic evidence_dir must be an existing non-symlink directory")
    evidence: dict[str, Mapping[str, Any]] = {}
    for name in REQUIRED_EVIDENCE:
        evidence[name] = _validate_check_artifact(
            evidence_dir / name,
            (
                "taskspace_mask_contract",
                "release_order_contract",
                "snapshot_stage4_contract",
                "snapshot_stage5_contract",
            ),
        )
    b0 = _validate_runtime_artifact(
        evidence_dir / "b0_admission.json",
        name="b0_pooled48",
        minimum_records=48,
    )
    forced = _validate_runtime_artifact(
        evidence_dir / "forced_one_env.json",
        name="forced_one_env",
        minimum_records=1,
    )
    canonical: dict[str, Mapping[str, Any]] = {}
    for group in CANONICAL_GROUPS:
        canonical[group] = _validate_runtime_artifact(
            evidence_dir / ("canonical16_" + group + ".json"),
            name="canonical16_" + group,
            minimum_records=16,
        )
        if canonical[group].get("record_count") != 16:
            raise R1Error("each canonical16 artifact must contain exactly 16 records")
        if canonical[group].get("config_group") != group:
            raise R1Error("canonical16 artifact group binding mismatch")
    command = build_semantic_commands(repo_root=root, evidence_dir=evidence_dir)
    assertions = {
        "b0_schema_and_runtime_admitted": b0.get("status") == RUNTIME_SEMANTIC_PASS,
        "forced_one_env_runtime_admitted": forced.get("status") == RUNTIME_SEMANTIC_PASS,
        "seven_canonical16_runtime_artifacts": len(canonical) == 7,
        "all_canonical16_have_16_records": all(
            row.get("record_count") == 16 for row in canonical.values()
        ),
        "all_evidence_commands_exit_zero": all(
            row.get("exit_code") == 0
            for row in [*evidence.values(), b0, forced, *canonical.values()]
            if row.get("command") is not None
        ),
    }
    if not all(assertions.values()):
        raise R1Error("semantic admission assertions failed")
    result = {
        "schema": SCHEMA,
        "plan_id": PLAN_ID,
        "status": RUNTIME_SEMANTIC_PASS,
        "assertions": assertions,
        "evidence": {
            "unit": {name: str(evidence_dir / name) for name in REQUIRED_EVIDENCE},
            "b0": str(evidence_dir / "b0_admission.json"),
            "forced_one_env": str(evidence_dir / "forced_one_env.json"),
            "canonical16": {
                group: str(evidence_dir / ("canonical16_" + group + ".json"))
                for group in CANONICAL_GROUPS
            },
        },
        "commands": command,
        "caller_all_true_rejected": True,
    }
    if output_dir is not None:
        output_dir = output_dir.resolve()
        expected_output = root / "logs_eval/base_v20_R1/semantic"
        if output_dir != expected_output:
            raise R1Error("semantic output must use canonical logs_eval/base_v20_R1/semantic")
        write_json_no_overwrite(output_dir / "semantic_admission.json", result)
    return result


def _require_blocked_r1_cli_opt_in() -> None:
    if "BASE_V20_ALLOW_BLOCKED_R1_EXECUTION" not in __import__("os").environ:
        print(
            "R1 execution is blocked by default; set BASE_V20_ALLOW_BLOCKED_R1_EXECUTION explicitly to run historical tooling",
            file=__import__("sys").stderr,
        )
        raise SystemExit(2)


if __name__ == "__main__":
    _require_blocked_r1_cli_opt_in()
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    run_semantic_assertions(
        output_dir=args.output_dir,
        evidence_dir=args.evidence_dir,
        repo_root=args.repo_root,
    )
