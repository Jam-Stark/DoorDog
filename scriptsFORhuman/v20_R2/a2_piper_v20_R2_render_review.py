"""Fixed-checklist human render review with no caller-declared PASS."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Mapping

from ._r2_common import R2Error, canonical_json
from ._r2_workflow import artifact_hash, read_artifact, write_adjudication, write_raw

CHECKLIST = ("no_pre_send_root_crossing", "arm_sustains_send", "base_follows_after_send",
             "no_fling", "no_grasp_loss", "no_body_collision", "controlled_release")
REVIEWERS = {"reviewer_A", "reviewer_B"}


def review_render(render_qa: Path, reviewer_id: str, answers: Mapping[str, bool] | None = None) -> dict[str, object]:
    if reviewer_id not in REVIEWERS:
        raise R2Error("reviewer identity must be reviewer_A or reviewer_B")
    qa = read_artifact(render_qa, schema="a2_piper_base_v20_R2_semantic_adjudication_v1", adjudicator_state="RENDER_QA_PASS")
    if answers is None:
        raise R2Error("human review requires explicit independent checklist inputs")
    if set(answers) != set(CHECKLIST) or any(type(value) is not bool for value in answers.values()):
        raise R2Error("human review checklist must answer every fixed item with a boolean")
    verdict = all(answers.values())
    return {"schema": "a2_piper_base_v20_R2_semantic_adjudication_v1",
            "adjudicator_state": "RENDER_QA_PASS" if verdict else "STRICT_INVALID",
            "mode": "render-review", "raw_sha256": artifact_hash(render_qa),
            "process_receipt_sha256": qa["process_receipt_sha256"],
            "expectations": {"reviewer": reviewer_id, "checklist": list(CHECKLIST)},
            "observed": {"reviewer": reviewer_id, "answers": dict(answers)},
            "recomputed": {"computed_verdict": verdict, "video_binding_sha256": qa["raw_sha256"]}}


def adjudicate_reviews(render_qa: Path, review_a: Path, review_b: Path) -> dict[str, object]:
    qa = read_artifact(render_qa, schema="a2_piper_base_v20_R2_semantic_adjudication_v1", adjudicator_state="RENDER_QA_PASS")
    first = read_artifact(review_a, schema="a2_piper_base_v20_R2_semantic_adjudication_v1", adjudicator_state="RENDER_QA_PASS")
    second = read_artifact(review_b, schema="a2_piper_base_v20_R2_semantic_adjudication_v1", adjudicator_state="RENDER_QA_PASS")
    reviewer_ids = {first.get("observed", {}).get("reviewer"), second.get("observed", {}).get("reviewer")}
    if reviewer_ids != REVIEWERS or first.get("raw_sha256") != second.get("raw_sha256") or first.get("raw_sha256") != artifact_hash(render_qa):
        raise R2Error("render reviews must be independent and bind the same QA/video hashes")
    answers_a = first.get("observed", {}).get("answers")
    answers_b = second.get("observed", {}).get("answers")
    if answers_a != answers_b or first.get("recomputed", {}).get("computed_verdict") is not True or second.get("recomputed", {}).get("computed_verdict") is not True:
        raise R2Error("reviewer disagreement or failed checklist prevents RENDER_QA_PASS")
    return {"schema": "a2_piper_base_v20_R2_semantic_adjudication_v1", "adjudicator_state": "RENDER_QA_PASS",
            "mode": "render-review", "raw_sha256": artifact_hash(render_qa),
            "process_receipt_sha256": qa["process_receipt_sha256"],
            "expectations": {"reviewers": sorted(REVIEWERS)},
            "observed": {"review_a": artifact_hash(review_a), "review_b": artifact_hash(review_b), "answers": answers_a},
            "recomputed": {"two_independent_agree": True, "computed_verdict": True},
            "parents": {"render_qa": artifact_hash(render_qa), "review_a": artifact_hash(review_a), "review_b": artifact_hash(review_b)}}


def _parse_answers(values: list[str]) -> dict[str, bool]:
    answers: dict[str, bool] = {}
    for value in values:
        if "=" not in value:
            raise R2Error("review answer must be checklist_name=true|false")
        key, raw = value.split("=", 1)
        if key in answers or raw.lower() not in {"true", "false"}:
            raise R2Error("review answers must be unique booleans")
        answers[key] = raw.lower() == "true"
    return answers


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--render-qa", type=Path, required=True); parser.add_argument("--reviewer-id", required=True)
    parser.add_argument("--answer", action="append", default=[]); parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = review_render(args.render_qa, args.reviewer_id, _parse_answers(args.answer))
    write_adjudication(args.output, result, result["adjudicator_state"])
    print(canonical_json(result)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
