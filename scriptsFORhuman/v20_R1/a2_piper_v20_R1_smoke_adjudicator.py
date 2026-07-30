"""Strict seven-group 64x50 smoke artifact adjudicator."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _r1_common import (  # noqa: E402
    GROUPS,
    NO_RELEASE,
    PLAN_ID,
    RUNTIME_PASS,
    POLICY_LEARNABILITY_PASS,
    R1Error,
    exact_digest,
    load_json,
    write_json_no_overwrite,
)

SCHEMA = "a2_piper_v20_R1_smoke_adjudication_v2"


def _validate_payload(payload: Mapping[str, Any], *, group: str, artifact: Path) -> None:
    if payload.get("plan_id") != PLAN_ID or payload.get("group") != group:
        raise R1Error(f"smoke artifact provenance mismatch for {group}")
    if payload.get("status") != RUNTIME_PASS or payload.get("policy_status") != RUNTIME_PASS:
        raise R1Error(f"smoke artifact requires RUNTIME PASS for {group}")
    if payload.get("exit_code") != 0 or payload.get("batches_completed") != 50 or payload.get("num_envs") != 64:
        raise R1Error(f"smoke topology/exit gate failed for {group}")
    if payload.get("partial") is not False:
        raise R1Error(f"smoke artifact is partial for {group}")
    for key in ("checkpoint_sha256", "config_sha256", "git_commit"):
        exact_digest(payload.get(key), name=f"{artifact}.{key}", length=40 if key == "git_commit" else 64)
    for key in (
        "optimizer_state_finite",
        "telemetry_schema_valid",
        "safety_gates_valid",
        "factor_binding_valid",
        "occupancy_valid",
    ):
        if payload.get(key) is not True:
            raise R1Error(f"smoke artifact missing gate {key} for {group}")
    output_root = payload.get("output_root")
    if not isinstance(output_root, str) or "logs_rl/a2_piper_full_stage_a2_base_smoke/base_v20_R1" not in output_root:
        raise R1Error(f"smoke artifact output root is not canonical for {group}")


def adjudicate_smoke(
    *,
    manifest: Mapping[str, Any] | Path,
    evidence_dir: Path,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    manifest = load_json(manifest) if isinstance(manifest, Path) else manifest
    if not isinstance(manifest, Mapping) or manifest.get("plan_id") != PLAN_ID:
        raise R1Error("smoke requires a plan-bound launcher")
    if manifest.get("status") != RUNTIME_PASS:
        raise R1Error("smoke launcher status must be RUNTIME PASS")
    chain = manifest.get("chain_artifacts")
    if not isinstance(chain, Mapping):
        raise R1Error("smoke manifest lacks exact P0/P1/pilot chain")
    if chain.get("pilot", {}).get("status") != POLICY_LEARNABILITY_PASS:
        raise R1Error("smoke requires POLICY LEARNABILITY PASS pilot")
    rows = manifest.get("groups")
    expected_groups = {spec["group"] for spec in GROUPS}
    if not isinstance(rows, list) or {row.get("group") for row in rows} != expected_groups:
        raise R1Error("smoke launcher must contain exactly G1-G7")
    if manifest.get("topology", {}).get("envs_per_group") != 64 or manifest.get("topology", {}).get("batches") != 50:
        raise R1Error("smoke manifest topology must be exactly 64x50")
    evidence_dir = evidence_dir.resolve()
    if not evidence_dir.is_dir() or evidence_dir.is_symlink():
        raise R1Error("smoke evidence directory must be a real directory")
    adjudicated = []
    bindings = None
    for spec in GROUPS:
        group = spec["group"]
        artifact = evidence_dir / group / "smoke_result.json"
        payload = load_json(artifact)
        if not isinstance(payload, Mapping):
            raise R1Error(f"smoke artifact must be a mapping for {group}")
        _validate_payload(payload, group=group, artifact=artifact)
        current = (
            payload["checkpoint_sha256"],
            payload["config_sha256"],
            payload["git_commit"],
        )
        if bindings is None:
            bindings = current
        elif current != bindings[:]:
            raise R1Error("smoke artifacts disagree on exact checkpoint/config/git bindings")
        adjudicated.append(
            {
                "group": group,
                "status": RUNTIME_PASS,
                "artifact": str(artifact),
                "checkpoint_sha256": payload["checkpoint_sha256"],
                "config_sha256": payload["config_sha256"],
            }
        )
    result = {
        "schema": SCHEMA,
        "plan_id": PLAN_ID,
        "status": RUNTIME_PASS,
        "groups": adjudicated,
        "formal_training_ready": False,
        "promotion_required": True,
        "all_seven_groups": True,
    }
    if output_dir is not None:
        write_json_no_overwrite(output_dir / "smoke_adjudication.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("evidence_dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    adjudicate_smoke(
        manifest=args.manifest,
        evidence_dir=args.evidence_dir,
        output_dir=args.output_dir,
    )
