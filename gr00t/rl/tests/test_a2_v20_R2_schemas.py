"""Schema-shape and raw-producer negative checks for R2 Phase I."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scriptsFORhuman.v20_R2 import _r2_common as common


ROOT = Path(__file__).resolve().parents[3]
SCHEMA_ROOT = ROOT / "scriptsFORhuman/v20_R2/schemas"


def _walk_objects(value, path="$", found=None):
    found = [] if found is None else found
    if isinstance(value, dict):
        if value.get("type") == "object":
            found.append((path, value.get("additionalProperties")))
        for key, child in value.items():
            _walk_objects(child, f"{path}.{key}", found)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _walk_objects(child, f"{path}[{index}]", found)
    return found


def test_all_phase_i_schemas_are_draft_2020_12_and_closed_objects():
    names = {path.name for path in SCHEMA_ROOT.glob("*.schema.json")}
    assert "forced_trace_v1.schema.json" in names
    assert "config_promotion_artifact_v1.schema.json" in names
    expected = {
        "source_lock_v1.schema.json", "process_receipt_v1.schema.json", "step_trace_v1.schema.json",
        "episode_record_v1.schema.json", "record_set_v1.schema.json", "endpoint_report_v1.schema.json",
        "p0_raw_v1.schema.json", "p0_adjudication_v1.schema.json", "semantic_adjudication_v1.schema.json",
        "training_attempt_v1.schema.json", "formal_completion_v1.schema.json", "m22_manifest_v1.schema.json",
        "m22_adjudication_v1.schema.json", "release_freeze_v1.schema.json", "render_execution_v1.schema.json",
        "final_decision_v1.schema.json", "forced_trace_v1.schema.json", "config_promotion_artifact_v1.schema.json",
    }
    assert names == expected
    for path in sorted(SCHEMA_ROOT.glob("*.schema.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert all(value is False for _, value in _walk_objects(payload))


def test_raw_producer_schema_vocabulary_rejects_status_and_pass_fields():
    for payload in (
        {"producer_state": "PROCESS_COMPLETED", "status": "PASS"},
        {"producer_state": "PROCESS_COMPLETED", "nested": {"checks_passed": True}},
        {"producer_state": "PROCESS_COMPLETED", "verdict": "STATIC_PASS"},
    ):
        with pytest.raises(common.R2Error):
            common.validate_raw_producer_payload(payload)


def test_adjudicator_vocabulary_is_distinct_from_raw_producer():
    common.require_adjudicator_state({"adjudicator_state": "STATIC_PASS"}, "STATIC_PASS")
    with pytest.raises(common.R2Error):
        common.require_adjudicator_state({"producer_state": "PROCESS_COMPLETED"}, "STATIC_PASS")
