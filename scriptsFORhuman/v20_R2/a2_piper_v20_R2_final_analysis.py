"""Final strict decision consumer with explicit no-release branch."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from ._r2_common import R2Error, canonical_json
from ._r2_workflow import GROUPS, artifact_hash, read_artifact, write_adjudication


def _parents(source_lock: Path, m22: Path, pooled: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], str]:
    source = read_artifact(source_lock, schema="a2_piper_base_v20_R2_source_lock_v1", producer_state="SOURCE_FROZEN")
    source_hash = artifact_hash(source_lock)
    m22_payload = read_artifact(m22, schema="a2_piper_base_v20_R2_m22_adjudication_v1", adjudicator_state="M22_70ROW_PASS")
    pooled_payload = read_artifact(pooled, schema="a2_piper_base_v20_R2_endpoint_report_v1", adjudicator_state="POOLED7_PASS")
    for name, payload in (("M22", m22_payload), ("pooled", pooled_payload)):
        if payload.get("source_lock_sha256") != source_hash:
            raise R2Error(f"{name} source-lock parent mismatch")
    return source, m22_payload, pooled_payload, source_hash


def _recompute_selection(pooled: dict[str, Any]) -> str | None:
    reports = pooled.get("metrics", {}).get("groups", {})
    if not isinstance(reports, dict) or set(reports) != set(GROUPS):
        raise R2Error("final analysis requires exact pooled G1-G7 reports")
    eligible = {group: reports[group].get("eligible") is True for group in GROUPS}
    for group in ("G1", "G2", "G3", "G4", "G5"):
        if eligible[group]:
            return group
    if eligible["G6"] and eligible["G7"]:
        def key(group: str) -> tuple[float, int, int]:
            report = reports[group]
            median = report.get("median_task_time")
            if not isinstance(median, (int, float)):
                median = float("inf")
            return float(median), int(report.get("selected_checkpoint_step", 10**9)), 0 if group == "G6" else 1
        return min(("G6", "G7"), key=key)
    return None


def final_decision(*, mode: str, source_lock: Path, m22: Path, pooled: Path, release_freeze: Path,
                   holdout: Path | None = None, render: Path | None = None) -> dict[str, object]:
    _, m22_payload, pooled_payload, source_hash = _parents(source_lock, m22, pooled)
    freeze_state = "POLICY_PASS" if mode == "release" else "NO_RELEASE"
    freeze = read_artifact(release_freeze, schema="a2_piper_base_v20_R2_release_freeze_v1", adjudicator_state=freeze_state)
    if freeze.get("source_lock_sha256") != source_hash or freeze.get("pooled_sha256") != artifact_hash(pooled):
        raise R2Error("release freeze parent hashes do not match current strict parents")
    selected = _recompute_selection(pooled_payload)
    if mode == "no-release":
        if freeze.get("selected_group") is not None or selected is not None or holdout is not None or render is not None:
            raise R2Error("no-release branch requires mechanically recomputed NO_RELEASE and no release-only artifacts")
        reports = pooled_payload["metrics"]["groups"]
        failures = {group: reports[group].get("gates", {}) for group in GROUPS if reports[group].get("eligible") is not True}
        return {"schema": "a2_piper_base_v20_R2_final_decision_v1", "adjudicator_state": "NO_RELEASE",
                "source_lock_sha256": source_hash, "release_freeze_sha256": artifact_hash(release_freeze),
                "decision": "NO_RELEASE", "reason": "no group passed mechanically recomputed pooled gates",
                "selected_group": None, "failed_gates": failures,
                "parents": {"m22": artifact_hash(m22), "pooled": artifact_hash(pooled)}}
    if mode != "release":
        raise R2Error("mode must be release or no-release")
    if freeze.get("selected_group") != selected or holdout is None or render is None:
        raise R2Error("release branch requires exact recomputed selection plus holdout/render")
    holdout_payload = read_artifact(holdout, schema="a2_piper_base_v20_R2_endpoint_report_v1", adjudicator_state="HOLDOUT64_PASS")
    render_payload = read_artifact(render, schema="a2_piper_base_v20_R2_semantic_adjudication_v1", adjudicator_state="RENDER_QA_PASS")
    if holdout_payload.get("source_lock_sha256") != source_hash or render_payload.get("source_lock_sha256") not in (None, source_hash):
        raise R2Error("release child source-lock binding mismatch")
    selected_report = pooled_payload["metrics"]["groups"][selected]
    if freeze.get("selected_checkpoint_sha256") not in (None, selected_report.get("selected_checkpoint_sha256")):
        raise R2Error("release freeze checkpoint differs from pooled selected checkpoint")
    return {"schema": "a2_piper_base_v20_R2_final_decision_v1", "adjudicator_state": "POLICY_PASS",
            "source_lock_sha256": source_hash, "release_freeze_sha256": artifact_hash(release_freeze),
            "decision": "POLICY_PASS", "reason": "all strict release parents and independent recomputation pass",
            "selected_group": selected, "selected_checkpoint_sha256": selected_report.get("selected_checkpoint_sha256"),
            "parents": {"m22": artifact_hash(m22), "pooled": artifact_hash(pooled), "holdout": artifact_hash(holdout), "render": artifact_hash(render)}}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    for mode in ("release", "no-release"):
        command = sub.add_parser(mode); command.add_argument("--source-lock", type=Path, required=True); command.add_argument("--m22", type=Path, required=True)
        command.add_argument("--pooled", type=Path, required=True); command.add_argument("--release-freeze", type=Path, required=True)
        command.add_argument("--holdout", type=Path); command.add_argument("--render", type=Path); command.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = final_decision(mode=args.mode, source_lock=args.source_lock, m22=args.m22, pooled=args.pooled,
                            release_freeze=args.release_freeze, holdout=args.holdout, render=args.render)
    write_adjudication(args.output, result, result["adjudicator_state"])
    print(canonical_json(result)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
