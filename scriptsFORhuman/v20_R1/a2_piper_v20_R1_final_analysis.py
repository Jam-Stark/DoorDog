"""Produce one explicit R1 release/no-release decision from bound artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _r1_common import (  # noqa: E402
    NO_RELEASE,
    PLAN_ID,
    POLICY_PASS,
    R1Error,
    exact_digest,
    load_json,
    write_json_no_overwrite,
)

SCHEMA = "a2_piper_v20_R1_final_analysis_v3"


def _artifact_pass(value: Any, name: str) -> Mapping[str, Any]:
    if isinstance(value, bool) or value is None:
        raise R1Error(f"{name} must be an explicit typed artifact")
    if isinstance(value, Path):
        payload = load_json(value)
    elif isinstance(value, Mapping):
        payload = value
    else:
        raise R1Error(f"{name} must be an artifact mapping/path")
    if payload.get("plan_id") != PLAN_ID:
        raise R1Error(f"{name} plan binding mismatch")
    if payload.get("status") not in {"RUNTIME PASS", "RUNTIME SEMANTIC PASS", "STRICT_VALID"}:
        raise R1Error(f"{name} does not have a strict runtime status")
    binding = payload.get("binding") or payload.get("selected_binding")
    if not isinstance(binding, Mapping):
        raise R1Error(f"{name} lacks exact checkpoint/config binding")
    exact_digest(binding.get("checkpoint_sha256"), name=name + ".checkpoint_sha256", length=64)
    exact_digest(binding.get("config_sha256"), name=name + ".config_sha256", length=64)
    return payload


def _selected_binding(result: Mapping[str, Any], group: str) -> Mapping[str, Any]:
    if result.get("selection_status") != POLICY_PASS:
        raise R1Error(f"{group} has no POLICY PASS selected checkpoint")
    selected = result.get("selected_checkpoint")
    if not isinstance(selected, Mapping):
        raise R1Error(f"{group} selection is unbound")
    candidate = selected.get("candidate")
    if not isinstance(candidate, Mapping):
        raise R1Error(f"{group} selected candidate is unbound")
    binding = selected.get("binding") or result.get("binding")
    if not isinstance(binding, Mapping):
        raise R1Error(f"{group} selected binding is missing")
    exact_digest(binding.get("checkpoint_sha256"), name=group + ".checkpoint_sha256", length=64)
    exact_digest(binding.get("config_sha256"), name=group + ".config_sha256", length=64)
    return binding


def finalize(
    *,
    adjudications: Mapping[str, Mapping[str, Any]],
    holdout_pass: Any,
    render_pass: Any,
    output_dir: Path | None = None,
    release_candidate: str | None = None,
) -> dict[str, Any]:
    expected = {"G1", "G2", "G3", "G4", "G5", "G6", "G7"}
    if set(adjudications) != expected:
        raise R1Error("final analysis requires exactly seven group adjudications")
    selected_bindings = {}
    for group in sorted(expected):
        selected_bindings[group] = _selected_binding(adjudications[group], group)
    passing = sorted(selected_bindings)
    if release_candidate is None:
        raise R1Error("final analysis requires explicit release_candidate after strict selection")
    if release_candidate not in passing:
        raise R1Error("release_candidate is not a selected strict-valid group")
    winner = selected_bindings[release_candidate]
    holdout = _artifact_pass(holdout_pass, "holdout")
    render = _artifact_pass(render_pass, "render")
    holdout_binding = holdout.get("binding") or holdout.get("selected_binding")
    render_binding = render.get("binding") or render.get("selected_binding")
    if not isinstance(holdout_binding, Mapping) or not isinstance(render_binding, Mapping):
        raise R1Error("holdout/render exact bindings are required")
    for label, binding in (("holdout", holdout_binding), ("render", render_binding)):
        if binding.get("checkpoint_sha256") != winner["checkpoint_sha256"] or binding.get("config_sha256") != winner["config_sha256"]:
            raise R1Error(label + " binding does not match selected winner")
    result = {
        "schema": SCHEMA,
        "plan_id": PLAN_ID,
        "status": POLICY_PASS,
        "selected_groups": [release_candidate],
        "selected_binding": dict(winner),
        "holdout_pass": True,
        "render_pass": True,
        "prior_reference": "G2 step2000",
        "claim": "learned policy shifts pre-crossing opening",
        "formal_training_ready": True,
        "single_winner": True,
        "unbound_candidates_rejected": True,
    }
    if output_dir is not None:
        write_json_no_overwrite(output_dir / "a2_piper_v20_R1_final_analysis.json", result)
        (output_dir / "a2_piper_v20_R1_final_analysis.md").write_text(
            "# base_v20_R1" + chr(10) + chr(10)
            + "Status: " + result["status"] + chr(10) + chr(10)
            + "Selected group: " + release_candidate + chr(10),
            encoding="utf-8",
        )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("adjudications", type=Path)
    parser.add_argument("--holdout-artifact", type=Path, required=True)
    parser.add_argument("--render-artifact", type=Path, required=True)
    parser.add_argument("--release-candidate", required=True)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    finalize(
        adjudications=json.loads(args.adjudications.read_text(encoding="utf-8")),
        holdout_pass=args.holdout_artifact,
        render_pass=args.render_artifact,
        output_dir=args.output_dir,
        release_candidate=args.release_candidate,
    )
