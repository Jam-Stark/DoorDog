"""CPU-only post-formal v21-B contract tests."""

from __future__ import annotations

import hashlib
import json
import ast
import shutil
from copy import deepcopy
from pathlib import Path

import pytest

from gr00t.rl.envs.door.a2_v21b_evidence import (
    V21B_ARM_JOINT_NAMES,
    V21B_AUTHORITY_LABEL,
    V21B_EVIDENCE_SCHEMA,
    V21B_TASK_RECORD_SCHEMA,
    a2_v21b_build_task_record,
    a2_v21b_build_terminal_record,
    a2_v21b_export_episode_bundle,
)
from scriptsFORhuman.v21B.a2_piper_v21B_postformal_eval import (
    DV_NA_CENSUS_REASON,
    DV_NA_F3_REASON,
    PostformalEvalError,
    V21B_EVAL_GPUS,
    V21B_EVAL_GPU_BY_CELL,
    adjudicate_route_b,
    freeze_release_candidate,
    build_route_a_queue,
    build_route_a_metrics,
    build_route_b_queue,
    build_render_queue,
    build_route_a_manifest,
    f3_dv_readout,
    select_mechanism_release,
    validate_formal_completion,
    validate_f3_promotion,
    validate_render_qa,
    validate_render_queue,
    validate_route_a_process_completion,
    validate_route_b_process_completion,
    write_route_a_process_completion,
    write_route_b_process_completion,
)
import scriptsFORhuman.v21B.a2_piper_v21B_postformal_eval as postformal_eval
from scriptsFORhuman.v21B._v21b_common import (
    V21B_CELL_ORDER,
    V21B_FORMAL_CHECKPOINT_STEPS,
    V21B_PLAN_ID,
    V21B_WARM_START_PATH,
    V21B_WARM_START_SHA256,
    canonical_json_bytes,
)


FORMAL_ROOT = Path("logs_rl/a2_piper_full_stage_a2_base/base_v21B/formal")
F3_ROOT = Path("logs_eval/base_v21B/f3_promotion_20260802_r3")
EXPECTED_ACTIVE_DIAGNOSTIC_TERMS = (
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


def _trace_row(run_uuid: str, env_id: int, step: int, *, terminal: bool) -> dict[str, object]:
    return {
        "schema": "a2_piper_v20_R2_step_trace_v1",
        "run_uuid": run_uuid,
        "env_id": env_id,
        "episode_ordinal": 0,
        "step_index": step,
        "batch_index": step,
        "stage": 3,
        "curriculum_phase": "soft",
        "root_se2": [0.0, 0.0, 0.0],
        "door_hinge_position_rad": 1.2,
        "door_hinge_velocity_radps": 0.1,
        "hold_valid": True,
        "bilateral": True,
        "coasting": False,
        "over_force": False,
        "send_ready": True,
        "pre_send_crossing_event": False,
        "root_crossing_event": terminal,
        "release_event": terminal,
        "root_x_rel_m": -0.01,
        "arm_raw_action_6d": [0.0] * 6,
        "taskspace_active": True,
        "positive_arm_tangent_mps": 0.1,
        "positive_base_tangent_mps": 0.2,
        "arm_tangent_share": 1.0 / 3.0,
        "arc_position_error_m": 0.001,
        "arc_orientation_error_rad": 0.002,
        "along_handle_slip_m": 0.003,
        "orthogonal_arc_residual_m": 0.004,
        "reward_components_scaled": {"r": 0.1},
        "terminal": terminal,
        "terminal_reason": "complete" if terminal else "NON_TERMINAL",
    }


def _task_record(seed: int, env_id: int, *, topology: str = "pooled_seed16", queue_row: dict[str, object] | None = None) -> dict[str, object]:
    if queue_row is None:
        raise AssertionError("producer records must be derived from a declared queue row")

    def _override_value(key: str) -> str:
        argv = queue_row["argv"]
        matches = [
            token.split("=", 1)[1].strip("'\"")
            for token in argv
            if isinstance(token, str) and "=" in token and token.split("=", 1)[0].lstrip("+") == key
        ]
        assert len(matches) == 1, (key, matches)
        return matches[0]

    run_uuid = str(queue_row["run_uuid"])
    source = _override_value("env.config.a2_v21B_source_checkpoint_path")
    source_sha = _override_value("env.config.a2_v21B_source_checkpoint_sha256")
    evaluated = _override_value("checkpoint")
    trace = [
        _trace_row(run_uuid, env_id, 0, terminal=False),
        _trace_row(run_uuid, env_id, 1, terminal=True),
    ]
    digest = source_sha
    queue_identity = queue_row["candidate_identity"]
    provenance = {
        "cell": "B1",
        "seed": seed,
        "source_lock_sha256": queue_identity["source_lock_sha256"],
        "source_config_sha256": queue_identity["source_config_sha256"],
        "materialization_sha256": queue_identity["materialization_sha256"],
        "materialized_config_sha256": queue_identity["materialized_config_sha256"],
        "adaptation_bundle_sha256": queue_identity["adaptation_bundle_sha256"],
        "queue_row_id": queue_row["row_id"],
        "evaluation_root": queue_row["evaluation_root"],
        "runtime_scenario_topology": queue_row["runtime_scenario_topology"],
        "evidence_aggregation_topology": queue_row["evidence_aggregation_topology"],
    }
    candidate = queue_identity
    return a2_v21b_build_task_record(
        trace,
        run_uuid=run_uuid,
        env_id=env_id,
        terminal_reason="complete",
        topology=topology,
        seed=seed,
        source_checkpoint_path=source,
        source_checkpoint_sha256=digest,
        evaluated_checkpoint_path=evaluated,
        evaluated_checkpoint_sha256=str(candidate["evaluated_checkpoint_sha256"]),
        evaluation_command_sha256=str(queue_row["evaluation_command_sha256"]),
        trace_path=f"{run_uuid}-{env_id}.jsonl",
        task={
            "goal": True,
            "held_crossing": True,
            "hinge_at_crossing_rad": 1.2,
            "opening_slip_max_m": 0.01,
            "pre_send_planar_p95_m": 0.2,
            "pre_send_yaw_p95_rad": 0.2,
            "task_time_p95_s": 10.0,
            "stage_overtime": False,
            "upper_dof_overspeed": False,
        },
        provenance=provenance,
        runtime_scenario_topology="canonical16",
        evidence_aggregation_topology=topology,
        queue_row_id=str(queue_row["row_id"]),
        evaluation_root=str(queue_row["evaluation_root"]),
    )


def _canonical_records(tmp_path: Path, seed: int) -> list[dict[str, object]]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    checkpoint = tmp_path / "candidate.pt"
    config = tmp_path / "config.yaml"
    checkpoint.write_bytes(b"candidate")
    config.write_text("seed: 0\n", encoding="utf-8")
    candidate = {
        "step": 250,
        "evaluated_checkpoint_path": str(checkpoint),
        "evaluated_checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        "config_path": str(config),
        "config_sha256": hashlib.sha256(config.read_bytes()).hexdigest(),
        "source_lock_sha256": "c5cfd505ed206f87c480f88b5faa95c5f1e9e99ba9679609621ce1aa3b5f0c40",
        "source_config_sha256": "c" * 64,
        "materialization_sha256": "d" * 64,
        "materialized_config_sha256": "e" * 64,
        "adaptation_bundle_sha256": "f" * 64,
    }
    queue = build_route_b_queue(
        candidate,
        cell="B1",
        topology="pooled_seed16",
        output_root=tmp_path / "queue",
    )
    queue_row = dict(queue["rows"][0])
    queue_row["topology"] = "canonical16"
    queue_row["evidence_aggregation_topology"] = "canonical16"
    return [_task_record(seed, env_id, topology="canonical16", queue_row=queue_row) for env_id in range(16)]


def test_formal_and_f3_contracts_bind_route_a_queue():
    f3 = validate_f3_promotion(F3_ROOT)
    completion = validate_formal_completion(FORMAL_ROOT, f3_context=f3)
    manifest = build_route_a_manifest(completion, f3_context=f3)
    queue = build_route_a_queue(manifest)
    assert manifest["row_count"] == 70
    assert tuple(manifest["eval_allowed_gpus"]) == V21B_EVAL_GPUS == (0, 1, 2, 3)
    assert manifest["eval_gpu_by_cell"] == V21B_EVAL_GPU_BY_CELL
    assert tuple(queue["eval_allowed_gpus"]) == V21B_EVAL_GPUS
    assert all(row["physical_gpu"] in V21B_EVAL_GPUS for row in manifest["rows"])
    assert all(row["training_gpu"] != row["physical_gpu"] or row["training_gpu"] < 4 for row in manifest["rows"])
    assert all(int(row["env"]["CUDA_VISIBLE_DEVICES"]) in V21B_EVAL_GPUS for row in manifest["rows"])
    assert len({(row["cell"], row["step"]) for row in manifest["rows"]}) == 70
    assert all("model_step_" in row["evaluated_checkpoint_path"] for row in manifest["rows"])
    assert all(row["evaluation_command_sha256"] in row["argv"][-1] for row in manifest["rows"])
    readout = f3_dv_readout(f3)
    assert readout["dv2"] == {"status": "N/A", "reason": DV_NA_CENSUS_REASON, "denominator": 0}
    assert readout["dv3"] == {"status": "N/A", "reason": DV_NA_F3_REASON, "denominator": 0}
    assert readout["dv4"]["dv4_tested"] is False


def test_route_a_command_uses_exact_active_diagnostic_reward_terms():
    f3 = validate_f3_promotion(F3_ROOT)
    completion = validate_formal_completion(FORMAL_ROOT, f3_context=f3)
    manifest = build_route_a_manifest(completion, f3_context=f3)
    expected = "[" + ",".join(EXPECTED_ACTIVE_DIAGNOSTIC_TERMS) + "]"
    for row in manifest["rows"]:
        overrides = [
            token
            for token in row["argv"]
            if "=" in token and token.split("=", 1)[0].lstrip("+") == "algo.config.eval.a2_diagnostic_reward_terms"
        ]
        assert len(overrides) == 1
        assert overrides[0].split("=", 1)[1] == expected
        terms = tuple(overrides[0].split("=", 1)[1].strip("[]").split(","))
        assert terms == EXPECTED_ACTIVE_DIAGNOSTIC_TERMS
        assert "push_door_handle" not in terms
        assert "dont_push_door_handle" in terms
        assert row["evaluation_command_sha256"] == postformal_eval._declared_command_identity(row["argv"], row["env"])


def test_route_a_eval_command_disables_legacy_strict_exporters_without_disabling_evidence(tmp_path: Path):
    config_path = tmp_path / "route_a.yaml"
    config_path.write_text("algo:\n  config:\n    eval: {}\n", encoding="utf-8")
    digest = "a" * 64
    scenario_manifest = {
        "path": str(tmp_path / "scenario-manifest.json"),
        "file_sha256": digest,
        "manifest_sha256": digest,
        "canonical_manifest_sha256": digest,
        "manifest_json": "{}",
        "manifest_json_sha256": digest,
        "materialization_sha256": digest,
        "manifest": {
            "source_checkpoint_sha256": digest,
            "source_lock_sha256": digest,
            "source_config_sha256": digest,
        },
    }
    command_kwargs = {
        "checkpoint_path": tmp_path / "model_step_000250.pt",
        "config_path": config_path,
        "output_root": tmp_path / "route-a-output",
        "cell": "B1",
        "seed": 0,
        "gpu": 0,
        "evaluated_checkpoint_sha256": digest,
        "source_lock_sha256": digest,
        "source_config_sha256": digest,
        "materialization_sha256": digest,
        "materialized_config_sha256": digest,
        "adaptation_bundle_sha256": digest,
        "legacy_strict_telemetry": False,
        "queue_row_id": "B1:step0250",
        "evaluation_root": tmp_path / "route-a-output",
        "run_uuid": "r16-route-a-test",
        "scenario_manifest": scenario_manifest,
    }
    argv, env = postformal_eval._eval_command(**command_kwargs)
    with pytest.raises(PostformalEvalError, match="legacy_strict_telemetry"):
        postformal_eval._eval_command(**{**command_kwargs, "legacy_strict_telemetry": 1})

    def values_for(key: str) -> list[str]:
        return [
            token.split("=", 1)[1]
            for token in argv
            if "=" in token and token.split("=", 1)[0].lstrip("+") == key
        ]

    for key in (
        "algo.config.eval.a2_eval_v20_strict_telemetry",
        "algo.config.eval.a2_eval_m41_strict_telemetry",
    ):
        assert values_for(key) == ["false"]
    for key in (
        "algo.config.eval.a2_diagnostic_trace_enabled",
        "env.config.a2_v20_R2_full_evidence",
        "env.config.a2_v20_R2_evidence_enabled",
        "env.config.a2_v21B_evidence_enabled",
    ):
        assert values_for(key) == ["true"]
    assert postformal_eval._declared_command_identity(argv, env) == argv[-1].split("=", 1)[1]


def test_formal_completion_rejects_forged_or_nonexistent_f3_receipt(tmp_path: Path):
    forged = {"status": "F3_VALIDATED", "root": str(tmp_path / "missing-f3-root")}
    with pytest.raises(PostformalEvalError, match="F3"):
        validate_formal_completion(FORMAL_ROOT, f3_context=forged)

    authenticated = validate_f3_promotion(F3_ROOT)
    forged = dict(authenticated)
    forged["adaptation_sha256"] = "0" * 64
    with pytest.raises(PostformalEvalError, match="receipt field adaptation_sha256"):
        validate_formal_completion(FORMAL_ROOT, f3_context=forged)


def test_f3_promotion_does_not_read_mutable_source_config_templates(monkeypatch):
    adaptation = json.loads((F3_ROOT / "V21B_F3_ADAPTATION_FROZEN.json").read_text(encoding="utf-8"))
    source_paths = {
        str((Path(__file__).resolve().parents[3] / row["config_path"]).resolve())
        for row in adaptation["source_artifacts"]["p0_admission"]["cells"]
    }
    original_sha256_file = postformal_eval.sha256_file

    def guarded_sha256_file(path):
        if str(Path(path).resolve()) in source_paths:
            raise AssertionError("mutable source template was read")
        return original_sha256_file(path)

    monkeypatch.setattr(postformal_eval, "sha256_file", guarded_sha256_file)
    assert validate_f3_promotion(F3_ROOT)["status"] == "F3_VALIDATED"


def _copy_f3_receipts(tmp_path: Path) -> Path:
    root = tmp_path / "f3"
    root.mkdir(parents=True)
    for name in ("V21B_F3_ADAPTATION_FROZEN.json", "V21B_FORMAL_PROMOTION_MATERIALIZATION.json"):
        shutil.copy2(F3_ROOT / name, root / name)
    return root


def test_authenticated_f3_adaptation_and_materialization_mutations_fail(tmp_path: Path):
    root = _copy_f3_receipts(tmp_path)
    adaptation_path = root / "V21B_F3_ADAPTATION_FROZEN.json"
    adaptation = json.loads(adaptation_path.read_text(encoding="utf-8"))
    adaptation["enabled_cells"] = list(adaptation["enabled_cells"]) + ["B8"]
    adaptation_path.write_text(json.dumps(adaptation, sort_keys=True), encoding="utf-8")
    with pytest.raises(PostformalEvalError, match="adaptation bundle"):
        validate_f3_promotion(root)

    root = _copy_f3_receipts(tmp_path / "materialization")
    materialization_path = root / "V21B_FORMAL_PROMOTION_MATERIALIZATION.json"
    materialization = json.loads(materialization_path.read_text(encoding="utf-8"))
    materialization["immutable_after_write"] = False
    materialization_path.write_text(json.dumps(materialization, sort_keys=True), encoding="utf-8")
    with pytest.raises(PostformalEvalError, match="immutable FORMAL_PROMOTED|self-hash"):
        validate_f3_promotion(root)


def test_f3_b1_to_b7_collections_require_exact_unique_rows(tmp_path: Path):
    root = _copy_f3_receipts(tmp_path)
    materialization_path = root / "V21B_FORMAL_PROMOTION_MATERIALIZATION.json"
    materialization = json.loads(materialization_path.read_text(encoding="utf-8"))
    materialization["configs"][1]["cell"] = materialization["configs"][0]["cell"]
    unsigned = dict(materialization)
    unsigned.pop("materialization_sha256", None)
    materialization["materialization_sha256"] = hashlib.sha256(canonical_json_bytes(unsigned)).hexdigest()
    materialization_path.write_text(json.dumps(materialization, sort_keys=True), encoding="utf-8")
    with pytest.raises(PostformalEvalError, match="exactly B1..B7 configs"):
        validate_f3_promotion(root)

    root = _copy_f3_receipts(tmp_path / "p0")
    adaptation_path = root / "V21B_F3_ADAPTATION_FROZEN.json"
    materialization_path = root / "V21B_FORMAL_PROMOTION_MATERIALIZATION.json"
    adaptation = json.loads(adaptation_path.read_text(encoding="utf-8"))
    adaptation["source_artifacts"]["p0_admission"]["cells"][1]["cell"] = adaptation["source_artifacts"]["p0_admission"]["cells"][0]["cell"]
    adaptation_sha = hashlib.sha256(canonical_json_bytes(adaptation)).hexdigest()
    adaptation_path.write_text(json.dumps(adaptation, sort_keys=True), encoding="utf-8")
    materialization = json.loads(materialization_path.read_text(encoding="utf-8"))
    materialization["adaptation_bundle_sha256"] = adaptation_sha
    unsigned = dict(materialization)
    unsigned.pop("materialization_sha256", None)
    materialization["materialization_sha256"] = hashlib.sha256(canonical_json_bytes(unsigned)).hexdigest()
    materialization_path.write_text(json.dumps(materialization, sort_keys=True), encoding="utf-8")
    with pytest.raises(PostformalEvalError, match="exact per-cell source configs"):
        validate_f3_promotion(root)


def _admission_probe_function():
    source = Path(__file__).resolve().parents[3] / "gr00t/rl/envs/door/door_open_a2_base.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    method = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "_validate_a2_v21b_admission"
    )
    module = ast.Module(body=[method], type_ignores=[])
    namespace = {"A2_V21B_PLAN_ID": V21B_PLAN_ID}
    exec(compile(ast.fix_missing_locations(module), str(source), "exec"), namespace)
    return namespace["_validate_a2_v21b_admission"]


class _AdmissionProbe:
    A2_V21B_ARM_PROFILE_CONFIG_KEY = "a2_v21B_arm_profile"
    A2_V21B_MATERIALIZATION_PHASE_CONFIG_KEY = "a2_v21B_materialization_phase"
    A2_V21B_SOURCE_CHECKPOINT_SHA256_CONFIG_KEY = "a2_v21B_source_checkpoint_sha256"
    A2_V21B_SOURCE_LOCK_SHA256_CONFIG_KEY = "a2_v21B_source_lock_sha256"
    A2_V21B_ADAPTATION_SHA256_CONFIG_KEY = "a2_v21B_adaptation_bundle_sha256"
    A2_V21B_SCENARIO_TOPOLOGY_CONFIG_KEY = "a2_v21B_census_topology"
    A2_V21B_EVIDENCE_AGGREGATION_TOPOLOGY_CONFIG_KEY = "a2_v21B_evidence_aggregation_topology"
    A2_V21B_SIGNED_PROBE_SCENARIOS_ENABLED_CONFIG_KEY = "a2_v21B_signed_probe_scenarios_enabled"
    A2_V21B_RUN_UUID_CONFIG_KEY = "a2_v21B_run_uuid"
    A2_V21B_SCENARIO_MANIFEST_PATH_CONFIG_KEY = "a2_v21B_scenario_manifest_path"
    A2_V21B_SCENARIO_MANIFEST_SHA256_CONFIG_KEY = "a2_v21B_scenario_manifest_sha256"
    A2_V21B_SCENARIO_MANIFEST_FILE_SHA256_CONFIG_KEY = "a2_v21B_scenario_manifest_file_sha256"
    A2_V21B_SCENARIO_MANIFEST_CANONICAL_SHA256_CONFIG_KEY = "a2_v21B_canonical_manifest_sha256"
    A2_V21B_SCENARIO_MANIFEST_SOURCE_CHECKPOINT_SHA256_CONFIG_KEY = "a2_v21B_scenario_manifest_source_checkpoint_sha256"
    A2_V21B_SCENARIO_MANIFEST_SOURCE_LOCK_SHA256_CONFIG_KEY = "a2_v21B_scenario_manifest_source_lock_sha256"
    A2_V21B_SCENARIO_MANIFEST_SOURCE_CONFIG_SHA256_CONFIG_KEY = "a2_v21B_scenario_manifest_source_config_sha256"
    A2_V21B_SCENARIO_MANIFEST_MATERIALIZATION_SHA256_CONFIG_KEY = "a2_v21B_scenario_manifest_materialization_sha256"
    A2_V21B_SCENARIO_MANIFEST_JSON_SHA256_CONFIG_KEY = "a2_v21B_scenario_manifest_json_sha256"
    A2_V21B_TERMINAL_EXPORT_ROOT_CONFIG_KEY = "a2_v21B_terminal_export_root"

    def __init__(self, config):
        self.config = config
        self.num_envs = 16

    def _get_a2_v20_r1_plan_id(self):
        return V21B_PLAN_ID

    def _get_a2_v20_formal_launch(self):
        return False


def _signed_preformal_admission_config() -> dict[str, object]:
    digest = "a" * 64
    return {
        "a2_v21B_evidence_enabled": True,
        "a2_v20_R2_evidence_enabled": True,
        "a2_v20_R2_formal_launch": False,
        "a2_v21B_arm_profile": "ARM_V20",
        "a2_v21B_materialization_phase": "CENSUS_PRE_K",
        "a2_v21B_source_checkpoint_sha256": digest,
        "a2_v21B_source_lock_sha256": digest,
        "a2_v21B_source_config_sha256": digest,
        "a2_v21B_materialization_sha256": digest,
        "a2_v21B_materialized_config_sha256": digest,
        "a2_v21B_signed_probe_scenarios_enabled": True,
        "a2_v21B_census_topology": "canonical16",
        "a2_v21B_scenario_manifest_path": "/tmp/signed-manifest.json",
        "a2_v21B_scenario_manifest_sha256": digest,
        "a2_v21B_scenario_manifest_file_sha256": digest,
        "a2_v21B_canonical_manifest_sha256": digest,
        "a2_v21B_scenario_manifest_source_checkpoint_sha256": digest,
        "a2_v21B_scenario_manifest_source_lock_sha256": digest,
        "a2_v21B_scenario_manifest_source_config_sha256": digest,
        "a2_v21B_scenario_manifest_materialization_sha256": digest,
        "a2_v21B_scenario_manifest_json_sha256": digest,
        "a2_v21B_scenario_manifest_json": "{}",
        "a2_v21B_run_uuid": "legacy-preformal-run",
    }


def test_signed_preformal_and_postformal_evaluated_admission_bind_queue_identity():
    validate = _admission_probe_function()
    legacy = _AdmissionProbe(_signed_preformal_admission_config())
    validate(legacy)

    partial = _AdmissionProbe(dict(legacy.config, a2_v21B_evaluated_checkpoint_path="candidate.pt"))
    with pytest.raises(RuntimeError, match="partial"):
        validate(partial)

    digest = "b" * 64
    complete_values = {
        "a2_v21B_evaluated_checkpoint_path": "candidate.pt",
        "a2_v21B_evaluated_checkpoint_sha256": digest,
        "a2_v21B_evaluation_command_sha256": digest,
        "a2_v21B_evidence_aggregation_topology": "canonical16",
    }
    complete_without_queue = _AdmissionProbe(dict(legacy.config, **complete_values))
    with pytest.raises(RuntimeError, match="queue_row_id"):
        validate(complete_without_queue)

    complete_with_queue = _AdmissionProbe(
        dict(
            legacy.config,
            **complete_values,
            a2_v21B_queue_row_id="B1:step0250",
            a2_v21B_evaluation_root="/tmp/eval-root",
        )
    )
    validate(complete_with_queue)


def test_pooled_route_b_requires_exact_seed16_and_strict_identity(tmp_path: Path):
    checkpoint = tmp_path / "candidate.pt"
    config = tmp_path / "config.yaml"
    checkpoint.write_bytes(b"candidate")
    config.write_text("seed: 0\n", encoding="utf-8")
    candidate = {
        "step": 250,
        "evaluated_checkpoint_path": str(checkpoint),
        "evaluated_checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        "config_path": str(config),
        "config_sha256": hashlib.sha256(config.read_bytes()).hexdigest(),
        "source_lock_sha256": "c5cfd505ed206f87c480f88b5faa95c5f1e9e99ba9679609621ce1aa3b5f0c40",
        "source_config_sha256": "c" * 64,
        "materialization_sha256": "d" * 64,
        "materialized_config_sha256": "e" * 64,
        "adaptation_bundle_sha256": "f" * 64,
    }
    queue = build_route_b_queue(candidate, cell="B1", topology="pooled_seed16", output_root=tmp_path / "queue")
    for row in queue["rows"]:
        for key in (
            "algo.config.eval.a2_eval_v20_strict_telemetry",
            "algo.config.eval.a2_eval_m41_strict_telemetry",
        ):
            values = [
                token.split("=", 1)[1]
                for token in row["argv"]
                if "=" in token and token.split("=", 1)[0].lstrip("+") == key
            ]
            assert values == ["true"]
        for key in (
            "algo.config.eval.a2_diagnostic_trace_enabled",
            "env.config.a2_v20_R2_full_evidence",
            "env.config.a2_v20_R2_evidence_enabled",
            "env.config.a2_v21B_evidence_enabled",
        ):
            values = [
                token.split("=", 1)[1]
                for token in row["argv"]
                if "=" in token and token.split("=", 1)[0].lstrip("+") == key
            ]
            assert values == ["true"]
        assert row["evaluation_command_sha256"] == postformal_eval._declared_command_identity(row["argv"], row["env"])
    records = [_task_record(row["seed"], env_id, queue_row=row) for row in queue["rows"] for env_id in range(16)]
    report = adjudicate_route_b(records, topology="pooled_seed16", theta_send_rad=1.2, queue=queue)
    assert report["status"] == "PASS"
    assert report["seed_counts"] == {0: 16, 1: 16, 2: 16}
    with pytest.raises(PostformalEvalError, match="does not accept expected_seed"):
        adjudicate_route_b(records, topology="pooled_seed16", theta_send_rad=1.2, queue=queue, expected_seed=0)
    tampered = list(records)
    tampered[0] = dict(tampered[0])
    tampered[0]["provenance"] = dict(tampered[0]["provenance"])
    tampered[0]["provenance"]["source_lock_sha256"] = "0" * 64
    tampered[0]["record_id"] = hashlib.sha256(
        json.dumps({key: value for key, value in tampered[0].items() if key != "record_id"}, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    with pytest.raises(PostformalEvalError, match="candidate identity|frozen checkpoint/materialization"):
        adjudicate_route_b(tampered, topology="pooled_seed16", theta_send_rad=1.2, queue=queue)


def test_pooled_b1_self_baseline_uses_finite_report_even_when_absolute_task_gate_fails(tmp_path: Path):
    checkpoint = tmp_path / "candidate.pt"
    config = tmp_path / "config.yaml"
    checkpoint.write_bytes(b"candidate")
    config.write_text("seed: 0\n", encoding="utf-8")
    candidate = {
        "step": 250,
        "evaluated_checkpoint_path": str(checkpoint),
        "evaluated_checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        "config_path": str(config),
        "config_sha256": hashlib.sha256(config.read_bytes()).hexdigest(),
        "source_lock_sha256": "c5cfd505ed206f87c480f88b5faa95c5f1e9e99ba9679609621ce1aa3b5f0c40",
        "source_config_sha256": "c" * 64,
        "materialization_sha256": "d" * 64,
        "materialized_config_sha256": "e" * 64,
        "adaptation_bundle_sha256": "f" * 64,
    }
    queue = build_route_b_queue(candidate, cell="B1", topology="pooled_seed16", output_root=tmp_path / "queue")
    records = [_task_record(row["seed"], env_id, queue_row=row) for row in queue["rows"] for env_id in range(16)]
    for record in records:
        record["task"] = dict(record["task"])
        record["task"]["task_time_p95_s"] = 25.0
        unsigned = dict(record)
        unsigned.pop("record_id", None)
        record["record_id"] = hashlib.sha256(canonical_json_bytes(unsigned)).hexdigest()
    first = adjudicate_route_b(records, topology="pooled_seed16", theta_send_rad=1.2, queue=queue)
    assert first["status"] == "FAIL"
    assert first["metrics"]["task_time_p95"] == 25.0
    assert first["gates"]["task_time_p95"] is False
    baseline = {
        "goal_rate": first["metrics"]["goal_rate"],
        "overspeed_rate": first["metrics"]["overspeed_rate"],
        "task_time_p95": first["metrics"]["task_time_p95"],
    }
    second = adjudicate_route_b(records, topology="pooled_seed16", theta_send_rad=1.2, baseline=baseline, queue=queue)
    assert second["status"] == "FAIL"
    assert second["gates"]["non_regression_goal"] is True
    assert second["gates"]["non_regression_overspeed"] is True
    assert second["gates"]["non_regression_task_time"] is True
    invalid = deepcopy(records[0])
    invalid["task"] = dict(invalid["task"])
    invalid["task"]["task_time_p95_s"] = "nan"
    unsigned = dict(invalid)
    unsigned.pop("record_id", None)
    invalid["record_id"] = hashlib.sha256(canonical_json_bytes(unsigned)).hexdigest()
    with pytest.raises(PostformalEvalError, match="task_time_p95_s must be a finite number"):
        adjudicate_route_b([invalid, *records[1:]], topology="pooled_seed16", theta_send_rad=1.2, baseline=baseline, queue=queue)


def test_canonical_expected_seed_admission_is_explicit_and_type_checked(tmp_path: Path):
    seed1_records = _canonical_records(tmp_path / "seed1", 1)
    assert adjudicate_route_b(
        seed1_records,
        topology="canonical16",
        theta_send_rad=1.2,
        expected_seed=1,
    )["status"] == "PASS"
    with pytest.raises(PostformalEvalError, match="record seed is not admitted"):
        adjudicate_route_b(seed1_records, topology="canonical16", theta_send_rad=1.2)
    with pytest.raises(PostformalEvalError, match="record seed is not admitted"):
        adjudicate_route_b(seed1_records, topology="canonical16", theta_send_rad=1.2, expected_seed=0)
    for invalid_seed in (True, False, 0.0, -1, 7):
        with pytest.raises(PostformalEvalError, match="canonical16 expected_seed"):
            adjudicate_route_b(
                seed1_records,
                topology="canonical16",
                theta_send_rad=1.2,
                expected_seed=invalid_seed,
            )
    seed0_records = _canonical_records(tmp_path / "seed0", 0)
    assert adjudicate_route_b(seed0_records, topology="canonical16", theta_send_rad=1.2)["status"] == "PASS"


@pytest.mark.parametrize("malformed_seed", [True, 1.0])
def test_route_a_metrics_rejects_non_integer_seed_before_adjudication(malformed_seed: object):
    evidence_rows = [{"manifest_row": {"seed": malformed_seed}} for _ in range(70)]
    with pytest.raises(PostformalEvalError, match="Route-A metrics row seed must be an int in 0..6"):
        build_route_a_metrics(evidence_rows)


def _selection_rows(*, eligible_cells: set[str]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for cell in V21B_CELL_ORDER:
        for step in V21B_FORMAL_CHECKPOINT_STEPS:
            rows.append(
                {
                    "row_id": f"{cell}:step{step:04d}",
                    "cell": cell,
                    "step": step,
                    "strict_status": "STRICT_VALID",
                    "release_gate_status": "PASS" if cell in eligible_cells else "FAIL",
                    "metrics": {
                        "hinge_at_crossing_p50": 2.0 if step == 500 else 1.0,
                        "task_time_p95": 10.0 + step / 1000.0,
                    },
                }
            )
    return rows


def test_selection_partial_release_preserves_ineligible_mechanism_and_order():
    eligible = {cell for cell in V21B_CELL_ORDER if cell != "B5"}
    selection = select_mechanism_release(_selection_rows(eligible_cells=eligible))
    assert selection["schema"] == "a2_piper_base_v21B_selection_v1"
    assert selection["status"] == "SELECTION_PASS"
    assert selection["eligible_release_cells"] == ["B1", "B2", "B3", "B4", "B6", "B7"]
    assert selection["ineligible_release_cells"] == ["B5"]
    assert selection["no_release_reasons"] == {"B5": "NO_PROMOTABLE_ROUTE_A_CHECKPOINT"}
    assert selection["cells"]["B5"]["status"] == "NO_RELEASE"
    assert selection["cells"]["B5"]["mechanism"]["row_id"] == "B5:step0500"
    assert selection["cells"]["B5"]["release"] is None
    assert selection["cells"]["B5"]["reason"] == "NO_PROMOTABLE_ROUTE_A_CHECKPOINT"
    assert selection["cells"]["B1"]["status"] == "RELEASE_ELIGIBLE"
    assert selection["cells"]["B1"]["mechanism"]["row_id"] == "B1:step0500"
    assert selection["cells"]["B1"]["release"]["row_id"] == "B1:step0250"


def test_selection_zero_eligible_is_terminal_no_release():
    selection = select_mechanism_release(_selection_rows(eligible_cells=set()))
    assert selection["schema"] == "a2_piper_base_v21B_selection_v1"
    assert selection["status"] == "NO_RELEASE"
    assert selection["reason"] == "NO_RELEASE_ELIGIBLE_CELL"
    assert selection["eligible_release_cells"] == []
    assert selection["ineligible_release_cells"] == list(V21B_CELL_ORDER)
    assert set(selection["no_release_reasons"]) == set(V21B_CELL_ORDER)
    assert all(item["status"] == "NO_RELEASE" for item in selection["cells"].values())


def test_selection_all_eligible_and_mechanism_release_distinctness_remain_pass():
    selection = select_mechanism_release(_selection_rows(eligible_cells=set(V21B_CELL_ORDER)))
    assert selection["status"] == "SELECTION_PASS"
    assert selection["eligible_release_cells"] == list(V21B_CELL_ORDER)
    assert selection["ineligible_release_cells"] == []
    assert selection["no_release_reasons"] == {}
    assert all(item["status"] == "RELEASE_ELIGIBLE" and item["distinct"] is True for item in selection["cells"].values())


def _freeze_fixture(tmp_path: Path) -> tuple[dict[str, object], dict[str, object], dict[str, object], dict[str, object]]:
    checkpoint = tmp_path / "candidate.pt"
    config = tmp_path / "config.yaml"
    checkpoint.write_bytes(b"candidate")
    config.write_text("seed: 0\n", encoding="utf-8")
    candidate = {
        "step": 250,
        "evaluated_checkpoint_path": str(checkpoint),
        "evaluated_checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        "config_path": str(config),
        "config_sha256": hashlib.sha256(config.read_bytes()).hexdigest(),
        "source_lock_sha256": "c5cfd505ed206f87c480f88b5faa95c5f1e9e99ba9679609621ce1aa3b5f0c40",
        "source_config_sha256": "c" * 64,
        "materialization_sha256": "d" * 64,
        "materialized_config_sha256": "e" * 64,
        "adaptation_bundle_sha256": "f" * 64,
    }
    queue = build_route_b_queue(candidate, cell="B1", topology="pooled_seed16", output_root=tmp_path / "queue")
    release = {
        **candidate,
        "source_checkpoint_path": V21B_WARM_START_PATH,
        "source_checkpoint_sha256": V21B_WARM_START_SHA256,
        "evaluation_command_sha256": queue["rows"][0]["evaluation_command_sha256"],
        "row_id": "B1:step0250",
        "cell": "B1",
        "step": 250,
        "strict_status": "STRICT_VALID",
        "release_gate_status": "PASS",
    }
    mechanism = dict(release)
    mechanism.update({"row_id": "B1:step0500", "step": 500, "release_gate_status": "FAIL"})
    selection = select_mechanism_release(_selection_rows(eligible_cells={"B1"}))
    selection["cells"]["B1"]["mechanism"] = mechanism
    selection["cells"]["B1"]["release"] = release
    pooled_report = {
        "schema": "a2_piper_base_v21B_route_b_adjudication_v1",
        "status": "PASS",
        "topology": "pooled_seed16",
        "episode_count": 48,
        "seed_counts": {0: 16, 1: 16, 2: 16},
        "cell": "B1",
        "selected_release_row_id": release["row_id"],
        "queue_receipt_sha256": queue["receipt_sha256"],
        "baseline_cell": "B1",
        "gates": {
            "goal": True,
            "held_crossing": True,
            "crossing_p50_absolute": True,
            "crossing_p50_theta_shortfall": True,
            "crossing_p10_theta_shortfall": True,
            "opening_slip_p95": True,
            "pre_send_planar_p95": True,
            "pre_send_yaw_p95": True,
            "task_time_p95": True,
            "stage_overtime": True,
            "upper_dof_overspeed": True,
            "non_regression_goal": True,
            "non_regression_overspeed": True,
            "non_regression_task_time": True,
        },
        "metrics": {
            "goal_rate": 1.0,
            "held_crossing_rate": 1.0,
            "overspeed_rate": 0.0,
            "hinge_at_crossing_p10": 1.2,
            "hinge_at_crossing_p50": 1.2,
            "opening_slip_p95": 0.01,
            "pre_send_planar_p95": 0.2,
            "pre_send_yaw_p95": 0.2,
            "task_time_p95": 10.0,
        },
        "failed_gates": [],
        "candidate_identity": {
            key: release[key]
            for key in postformal_eval.RECORD_CANDIDATE_KEYS
        },
    }
    return selection, queue, pooled_report, {"profile": "STANDARD"}


def test_freeze_release_accepts_only_bound_eligible_b1_candidate(tmp_path: Path):
    selection, queue, pooled_report, acceptance = _freeze_fixture(tmp_path)
    frozen = freeze_release_candidate(
        selection,
        cell="B1",
        pooled_report=pooled_report,
        pooled_queue=queue,
        acceptance_profile=acceptance,
    )
    assert frozen["status"] == "RELEASE_FROZEN"
    postformal_eval.validate_release_freeze(frozen)


@pytest.mark.parametrize("case", [
    "ineligible_b5",
    "cross_cell_rows",
    "non_strict_release",
    "non_pass_release",
    "non_distinct",
    "pooled_queue_wrong_cell",
    "pooled_report_wrong_cell",
    "pooled_candidate_wrong",
    "wrong_baseline",
    "non_regression_false",
    "selection_completed_false",
    "selection_overlap",
    "selection_missing_cell",
    "selection_extra_cell",
    "selection_reason_mismatch",
    "selection_list_mismatch",
    "selection_status_mismatch",
    "pooled_report_schema",
])
def test_freeze_release_rejects_unbound_or_ineligible_candidate(tmp_path: Path, case: str):
    selection, queue, pooled_report, acceptance = _freeze_fixture(tmp_path)
    if case == "ineligible_b5":
        selection = select_mechanism_release(_selection_rows(eligible_cells={cell for cell in V21B_CELL_ORDER if cell != "B5"}))
        cell = "B5"
    else:
        cell = "B1"
    if case == "cross_cell_rows":
        selection["cells"]["B1"]["release"]["cell"] = "B2"
    elif case == "non_strict_release":
        selection["cells"]["B1"]["release"]["strict_status"] = "FAIL"
    elif case == "non_pass_release":
        selection["cells"]["B1"]["release"]["release_gate_status"] = "FAIL"
    elif case == "non_distinct":
        selection["cells"]["B1"]["release"]["row_id"] = selection["cells"]["B1"]["mechanism"]["row_id"]
    elif case == "pooled_queue_wrong_cell":
        queue["cell"] = "B2"
    elif case == "pooled_report_wrong_cell":
        pooled_report["cell"] = "B2"
    elif case == "pooled_candidate_wrong":
        pooled_report["candidate_identity"]["evaluated_checkpoint_sha256"] = "0" * 64
    elif case == "wrong_baseline":
        pooled_report["baseline_cell"] = "B2"
    elif case == "non_regression_false":
        pooled_report["gates"]["non_regression_task_time"] = False
    elif case == "selection_completed_false":
        selection["completed"] = False
    elif case == "selection_overlap":
        selection["ineligible_release_cells"].append("B1")
    elif case == "selection_missing_cell":
        selection["cells"].pop("B7")
    elif case == "selection_extra_cell":
        selection["cells"]["B8"] = dict(selection["cells"]["B1"])
    elif case == "selection_reason_mismatch":
        selection["no_release_reasons"]["B2"] = "WRONG_REASON"
    elif case == "selection_list_mismatch":
        selection["ineligible_release_cells"] = list(reversed(selection["ineligible_release_cells"]))
    elif case == "selection_status_mismatch":
        selection["cells"]["B1"]["status"] = "NO_RELEASE"
    elif case == "pooled_report_schema":
        pooled_report["schema"] = "malformed"
    with pytest.raises(PostformalEvalError):
        freeze_release_candidate(
            selection,
            cell=cell,
            pooled_report=pooled_report,
            pooled_queue=queue,
            acceptance_profile=acceptance,
        )


def test_validate_release_freeze_rejects_rehashed_malformed_snapshots(tmp_path: Path):
    selection, queue, pooled_report, acceptance = _freeze_fixture(tmp_path)
    frozen = freeze_release_candidate(
        selection,
        cell="B1",
        pooled_report=pooled_report,
        pooled_queue=queue,
        acceptance_profile=acceptance,
    )
    malformed_selection = deepcopy(frozen)
    malformed_selection["selection_snapshot"]["completed"] = False
    malformed_selection["selection_sha256"] = hashlib.sha256(
        canonical_json_bytes(malformed_selection["selection_snapshot"])
    ).hexdigest()
    malformed_selection.pop("freeze_sha256")
    malformed_selection["freeze_sha256"] = hashlib.sha256(canonical_json_bytes(malformed_selection)).hexdigest()
    with pytest.raises(PostformalEvalError, match="selection"):
        postformal_eval.validate_release_freeze(malformed_selection)

    malformed_report = deepcopy(frozen)
    malformed_report["pooled_report_snapshot"]["schema"] = "malformed"
    malformed_report["pooled_report_sha256"] = hashlib.sha256(
        canonical_json_bytes(malformed_report["pooled_report_snapshot"])
    ).hexdigest()
    malformed_report.pop("freeze_sha256")
    malformed_report["freeze_sha256"] = hashlib.sha256(canonical_json_bytes(malformed_report)).hexdigest()
    with pytest.raises(PostformalEvalError, match="pooled freeze report schema"):
        postformal_eval.validate_release_freeze(malformed_report)

    forged_plan = deepcopy(frozen)
    forged_plan["plan_id"] = "forged-plan"
    forged_plan.pop("freeze_sha256")
    forged_plan["freeze_sha256"] = hashlib.sha256(canonical_json_bytes(forged_plan)).hexdigest()
    with pytest.raises(PostformalEvalError, match="plan_id"):
        postformal_eval.validate_release_freeze(forged_plan)

    unknown_field = deepcopy(frozen)
    unknown_field["unknown_field"] = True
    unknown_field.pop("freeze_sha256")
    unknown_field["freeze_sha256"] = hashlib.sha256(canonical_json_bytes(unknown_field)).hexdigest()
    with pytest.raises(PostformalEvalError, match="top-level keys"):
        postformal_eval.validate_release_freeze(unknown_field)


def test_route_b_rejects_out_of_policy_gpu(tmp_path: Path):
    with pytest.raises(PostformalEvalError, match=r"physical GPUs \(0, 1, 2, 3\)"):
        build_route_b_queue({}, cell="B1", topology="pooled_seed16", output_root=tmp_path, gpu=4)


def test_render_queue_is_exact_case_camera_and_command_bound(tmp_path: Path):
    checkpoint = tmp_path / "model_step_000250.pt"
    config = tmp_path / "config.yaml"
    checkpoint.write_bytes(b"checkpoint")
    config.write_text("seed: 0\n", encoding="utf-8")
    cases = [
        {
            "case_id": f"case-{index}",
            "selected_env_id": index,
            "evaluated_checkpoint_path": str(checkpoint),
            "evaluated_checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
            "config_path": str(config),
            "config_sha256": hashlib.sha256(config.read_bytes()).hexdigest(),
            "source_lock_sha256": "c5cfd505ed206f87c480f88b5faa95c5f1e9e99ba9679609621ce1aa3b5f0c40",
            "source_config_sha256": "c" * 64,
            "materialization_sha256": "d" * 64,
            "materialized_config_sha256": "e" * 64,
            "adaptation_bundle_sha256": "f" * 64,
        }
        for index in range(5)
    ]
    with pytest.raises(PostformalEvalError, match=r"physical GPUs \(0, 1, 2, 3\)"):
        build_render_queue(cases, output_root=tmp_path / "render-rejected", gpu=4)
    queue = build_render_queue(cases, output_root=tmp_path / "render")
    validate_render_queue(queue)
    assert queue["eval_gpu"] == 3
    assert tuple(queue["eval_allowed_gpus"]) == V21B_EVAL_GPUS
    assert all(row["env"]["CUDA_VISIBLE_DEVICES"] == "3" for row in queue["rows"])
    expected = "[" + ",".join(EXPECTED_ACTIVE_DIAGNOSTIC_TERMS) + "]"
    for row in queue["rows"]:
        overrides = [
            token
            for token in row["argv"]
            if "=" in token and token.split("=", 1)[0].lstrip("+") == "algo.config.eval.a2_diagnostic_reward_terms"
        ]
        assert len(overrides) == 1
        assert overrides[0].split("=", 1)[1] == expected
        terms = tuple(overrides[0].split("=", 1)[1].strip("[]").split(","))
        assert terms == EXPECTED_ACTIVE_DIAGNOSTIC_TERMS
        assert "push_door_handle" not in terms
        assert "dont_push_door_handle" in terms
        for key in (
            "algo.config.eval.a2_eval_v20_strict_telemetry",
            "algo.config.eval.a2_eval_m41_strict_telemetry",
        ):
            values = [
                token.split("=", 1)[1]
                for token in row["argv"]
                if "=" in token and token.split("=", 1)[0].lstrip("+") == key
            ]
            assert values == ["true"]
        assert row["evaluation_command_sha256"] == postformal_eval._declared_command_identity(row["argv"], row["env"])
    assert all(
        not any(
            token.startswith(("env.config.a2_v21B_eval_gpu=", "+env.config.a2_v21B_eval_gpu="))
            and token.rsplit("=", 1)[-1] in {"4", "5", "6", "7"}
            for token in row["argv"]
        )
        for row in queue["rows"]
    )
    assert queue["row_count"] == 5
    assert queue["camera_expectation_count"] == 15
    assert all(len(row["camera_expectation_ids"]) == 3 for row in queue["rows"])
    assert all(row["argv"][-1].startswith("+env.config.a2_v21B_evaluation_command_sha256=") for row in queue["rows"])
    qa_rows = [
        {
            "expectation_id": item["expectation_id"],
            "case_id": item["case_id"],
            "camera": item["camera"],
            "run_uuid": item["run_uuid"],
            "selected_env_id": item["selected_env_id"],
            "evaluation_command_sha256": item["evaluation_command_sha256"],
            "candidate_identity": item["candidate_identity"],
            "artifact_path": str(
                Path(item["renderings_dir"])
                / (
                    f"{item['case_id']}_env{item['selected_env_id']:04d}_episode0000"
                    f"{'' if item['camera'] == 'main' else '_' + item['camera']}"
                    "_len02_reason-complete.mp4"
                )
            ),
            "artifact_env_id": item["selected_env_id"],
            "artifact_camera": item["camera"],
            "artifact_sha256": "",
            "decode_status": "PASS",
            "contact_sheet_status": "PASS",
            "strict_task_record_status": "PASS",
            "strict_trace_status": "PASS",
        }
        for item in queue["camera_artifact_expectations"]
    ]
    for row in qa_rows:
        artifact = Path(row["artifact_path"])
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_bytes(f"{row['case_id']}:{row['camera']}".encode())
        row["artifact_sha256"] = hashlib.sha256(artifact.read_bytes()).hexdigest()
    assert validate_render_qa(queue, {"schema": "a2_piper_base_v21B_render_qa_v1", "rows": qa_rows})["status"] == "PASS"


def _empty_formal_arm_evidence() -> dict[str, object]:
    no_valid = {"status": "N/A", "reason": "no valid arm telemetry frames", "denominator": 0}
    return {
        "schema": V21B_EVIDENCE_SCHEMA,
        "joint_names": list(V21B_ARM_JOINT_NAMES),
        "authority": V21B_AUTHORITY_LABEL,
        "valid_frame_count": 0,
        "isaaclab_implicit_computed_effort_estimate_6d": dict(no_valid),
        "isaaclab_implicit_applied_effort_estimate_6d": dict(no_valid),
        "isaaclab_implicit_effort_estimate_crosscheck_error_6d": dict(no_valid),
    }


def _process_contract_fixture(tmp_path: Path) -> tuple[dict[str, object], str, list[Path], Path, Path]:
    root = tmp_path / "route-a-row"
    root.mkdir(parents=True)
    source = root / "source.pt"
    evaluated = root / "evaluated.pt"
    config = root / "config.yaml"
    source.write_bytes(b"source")
    evaluated.write_bytes(b"evaluated")
    config.write_text("seed: 0\n", encoding="utf-8")
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    evaluated_sha = hashlib.sha256(evaluated.read_bytes()).hexdigest()
    config_sha = hashlib.sha256(config.read_bytes()).hexdigest()
    identity = {
        "source_lock_sha256": "1" * 64,
        "source_config_sha256": "2" * 64,
        "materialization_sha256": "3" * 64,
        "materialized_config_sha256": "4" * 64,
        "adaptation_bundle_sha256": "5" * 64,
    }
    base_argv = ["python", "-m", "synthetic_route_a"]
    env = {"CUDA_VISIBLE_DEVICES": "0"}
    command_sha = postformal_eval.command_sha256(base_argv, env)
    row: dict[str, object] = {
        "row_id": "B1:step0250",
        "queue_row_id": "B1:step0250",
        "cell": "B1",
        "step": 250,
        "topology": "canonical16",
        "runtime_scenario_topology": "canonical16",
        "evidence_aggregation_topology": "canonical16",
        "seed": 0,
        "episodes": 16,
        "first_episode_only": True,
        "run_uuid": "synthetic-route-a-run",
        "evaluation_root": str(root),
        "source_checkpoint_path": str(source),
        "source_checkpoint_sha256": source_sha,
        "evaluated_checkpoint_path": str(evaluated),
        "evaluated_checkpoint_sha256": evaluated_sha,
        "config_path": str(config),
        "config_sha256": config_sha,
        "evaluation_command_sha256": command_sha,
        **identity,
    }
    row["argv"] = base_argv + [postformal_eval.COMMAND_IDENTITY_OVERRIDE + command_sha]
    row["env"] = env
    stdout = root / "stdout.log"
    stderr = root / "stderr.log"
    stdout.write_text("synthetic stdout\n", encoding="utf-8")
    stderr.write_text("synthetic stderr\n", encoding="utf-8")
    marker_paths: list[Path] = []
    for env_id in range(16):
        trace_path = root / f"trace_env{env_id:02d}.jsonl"
        task_path = root / f"task_env{env_id:02d}.json"
        arm_path = root / f"arm_env{env_id:02d}.json"
        trace = [_trace_row(row["run_uuid"], env_id, 0, terminal=False), _trace_row(row["run_uuid"], env_id, 1, terminal=True)]
        provenance = {
            "cell": "B1",
            "seed": 0,
            "run_uuid": row["run_uuid"],
            "env_id": env_id,
            "topology": "canonical16",
            "runtime_scenario_topology": "canonical16",
            "evidence_aggregation_topology": "canonical16",
            "queue_row_id": row["row_id"],
            "evaluation_root": str(root),
            **identity,
        }
        task = a2_v21b_build_task_record(
            trace,
            run_uuid=row["run_uuid"],
            env_id=env_id,
            terminal_reason="complete",
            topology="canonical16",
            seed=0,
            source_checkpoint_path=str(source),
            source_checkpoint_sha256=source_sha,
            evaluated_checkpoint_path=str(evaluated),
            evaluated_checkpoint_sha256=evaluated_sha,
            evaluation_command_sha256=command_sha,
            trace_path=str(trace_path),
            task={"goal": True, "held_crossing": True},
            provenance=provenance,
            runtime_scenario_topology="canonical16",
            evidence_aggregation_topology="canonical16",
            queue_row_id=row["row_id"],
            evaluation_root=str(root),
        )
        arm = a2_v21b_build_terminal_record(
            _empty_formal_arm_evidence(),
            plan_id=V21B_PLAN_ID,
            cell="B1",
            group="B1",
            seed=0,
            source_checkpoint_sha256=source_sha,
            adaptation_bundle_sha256=identity["adaptation_bundle_sha256"],
            provenance={
                "materialization_phase": "FORMAL_PROMOTED",
                "scenario_id": f"synthetic:{env_id}",
                "episode_id": f"synthetic:{env_id}:episode0",
                **provenance,
                "source_checkpoint_sha256": source_sha,
                "materialization_phase": "FORMAL_PROMOTED",
            },
            source_checkpoint_path=str(source),
            evaluated_checkpoint_path=str(evaluated),
            evaluated_checkpoint_sha256=evaluated_sha,
            evaluation_command_sha256=command_sha,
        )
        arm["task_record"] = {
            "schema": V21B_TASK_RECORD_SCHEMA,
            "path": str(task_path),
            "record_id": task["record_id"],
            "trace_path": task["trace"]["path"],
            "trace_sha256": task["trace"]["sha256"],
            "arm_record_path": str(arm_path),
        }
        arm_unsigned = dict(arm)
        arm_unsigned.pop("record_id", None)
        arm["record_id"] = hashlib.sha256(canonical_json_bytes(arm_unsigned)).hexdigest()
        bundle = a2_v21b_export_episode_bundle(
            trace_path=trace_path,
            task_record_path=task_path,
            arm_record_path=arm_path,
            rows=trace,
            task_record=task,
            arm_record=arm,
        )
        marker_paths.append(trace_path.parent / f".{row['run_uuid']}_env{env_id}.bundle.complete.json")
        assert bundle["task_record_id"] == task["record_id"]
    return row, "a" * 64, marker_paths, stdout, stderr


def _route_b_process_contract_fixture(
    tmp_path: Path, *, checkpoint_name: str = "model_step_000250.pt", candidate_step: int = 250
) -> tuple[dict[str, object], str, list[Path], Path, Path]:
    """Build one pooled Route-B queue row and its 16 synthetic bundles."""

    tmp_path.mkdir(parents=True, exist_ok=True)
    checkpoint = tmp_path / checkpoint_name
    config = tmp_path / "config.yaml"
    checkpoint.write_bytes(b"route-b-candidate")
    config.write_text("seed: 0\n", encoding="utf-8")
    candidate = {
        "step": candidate_step,
        "evaluated_checkpoint_path": str(checkpoint),
        "evaluated_checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        "config_path": str(config),
        "config_sha256": hashlib.sha256(config.read_bytes()).hexdigest(),
        "source_lock_sha256": "c5cfd505ed206f87c480f88b5faa95c5f1e9e99ba9679609621ce1aa3b5f0c40",
        "source_config_sha256": "c" * 64,
        "materialization_sha256": "d" * 64,
        "materialized_config_sha256": "e" * 64,
        "adaptation_bundle_sha256": "f" * 64,
    }
    queue = build_route_b_queue(candidate, cell="B1", topology="pooled_seed16", output_root=tmp_path / "queue")
    row = dict(queue["rows"][0])
    root = Path(row["evaluation_root"])
    root.mkdir(parents=True, exist_ok=True)
    stdout = root / "stdout.log"
    stderr = root / "stderr.log"
    stdout.write_text("route-b stdout\n", encoding="utf-8")
    stderr.write_text("route-b stderr\n", encoding="utf-8")
    marker_paths: list[Path] = []
    for env_id in range(16):
        trace_path = root / f"trace_env{env_id:02d}.jsonl"
        task_path = root / f"task_env{env_id:02d}.json"
        arm_path = root / f"arm_env{env_id:02d}.json"
        trace = [_trace_row(row["run_uuid"], env_id, 0, terminal=False), _trace_row(row["run_uuid"], env_id, 1, terminal=True)]
        provenance = {
            "cell": row["cell"],
            "seed": row["seed"],
            "run_uuid": row["run_uuid"],
            "env_id": env_id,
            "topology": row["topology"],
            "runtime_scenario_topology": row["runtime_scenario_topology"],
            "evidence_aggregation_topology": row["evidence_aggregation_topology"],
            "queue_row_id": row["queue_row_id"],
            "evaluation_root": row["evaluation_root"],
            "source_lock_sha256": row["source_lock_sha256"],
            "source_config_sha256": row["source_config_sha256"],
            "materialization_sha256": row["materialization_sha256"],
            "materialized_config_sha256": row["materialized_config_sha256"],
            "adaptation_bundle_sha256": row["adaptation_bundle_sha256"],
        }
        task = a2_v21b_build_task_record(
            trace,
            run_uuid=row["run_uuid"],
            env_id=env_id,
            terminal_reason="complete",
            topology=row["topology"],
            seed=row["seed"],
            source_checkpoint_path=row["source_checkpoint_path"],
            source_checkpoint_sha256=row["source_checkpoint_sha256"],
            evaluated_checkpoint_path=row["evaluated_checkpoint_path"],
            evaluated_checkpoint_sha256=row["evaluated_checkpoint_sha256"],
            evaluation_command_sha256=row["evaluation_command_sha256"],
            trace_path=str(trace_path),
            task={"goal": True, "held_crossing": True},
            provenance=provenance,
            runtime_scenario_topology="canonical16",
            evidence_aggregation_topology=row["topology"],
            queue_row_id=row["queue_row_id"],
            evaluation_root=row["evaluation_root"],
        )
        arm = a2_v21b_build_terminal_record(
            _empty_formal_arm_evidence(),
            plan_id=V21B_PLAN_ID,
            cell=row["cell"],
            group=row["cell"],
            seed=row["seed"],
            source_checkpoint_sha256=row["source_checkpoint_sha256"],
            adaptation_bundle_sha256=row["adaptation_bundle_sha256"],
            provenance={
                "materialization_phase": "FORMAL_PROMOTED",
                "scenario_id": f"route-b:{env_id}",
                "episode_id": f"route-b:{env_id}:episode0",
                **provenance,
            },
            source_checkpoint_path=row["source_checkpoint_path"],
            evaluated_checkpoint_path=row["evaluated_checkpoint_path"],
            evaluated_checkpoint_sha256=row["evaluated_checkpoint_sha256"],
            evaluation_command_sha256=row["evaluation_command_sha256"],
        )
        arm["task_record"] = {
            "schema": V21B_TASK_RECORD_SCHEMA,
            "path": str(task_path),
            "record_id": task["record_id"],
            "trace_path": task["trace"]["path"],
            "trace_sha256": task["trace"]["sha256"],
            "arm_record_path": str(arm_path),
        }
        arm_unsigned = dict(arm)
        arm_unsigned.pop("record_id", None)
        arm["record_id"] = hashlib.sha256(canonical_json_bytes(arm_unsigned)).hexdigest()
        a2_v21b_export_episode_bundle(
            trace_path=trace_path,
            task_record_path=task_path,
            arm_record_path=arm_path,
            rows=trace,
            task_record=task,
            arm_record=arm,
        )
        marker_paths.append(root / f".{row['run_uuid']}_env{env_id}.bundle.complete.json")
    return row, "b" * 64, marker_paths, stdout, stderr


def _successful_process_result() -> dict[str, object]:
    return {
        "pid": 1234,
        "started_at": "2026-08-03T10:00:00+08:00",
        "ended_at": "2026-08-03T10:00:01+08:00",
        "natural_exit": True,
        "exit_code": 0,
    }


def test_route_a_process_completion_synthetic_sixteen_bundle_success_and_idempotence(tmp_path: Path):
    row, candidate_id, marker_paths, stdout, stderr = _process_contract_fixture(tmp_path)
    result = write_route_a_process_completion(
        row,
        candidate_id=candidate_id,
        process_result=_successful_process_result(),
        stdout_path=stdout,
        stderr_path=stderr,
        episode_bundle_marker_paths=marker_paths,
    )
    assert result["status"] == "PROCESS_COMPLETED_SEALED"
    validated = validate_route_a_process_completion(row, candidate_id=candidate_id)
    assert validated["status"] == "PROCESS_COMPLETED_SEALED"
    again = write_route_a_process_completion(
        row,
        candidate_id=candidate_id,
        process_result=_successful_process_result(),
        stdout_path=stdout,
        stderr_path=stderr,
        episode_bundle_marker_paths=marker_paths,
    )
    assert again["receipt"]["receipt_sha256"] == result["receipt"]["receipt_sha256"]
    assert again["seal"]["seal_sha256"] == result["seal"]["seal_sha256"]


def test_route_b_pooled_process_completion_synthetic_sixteen_bundle_success_idempotence_and_revalidation(tmp_path: Path):
    row, candidate_id, marker_paths, stdout, stderr = _route_b_process_contract_fixture(tmp_path)
    result = write_route_b_process_completion(
        row,
        candidate_id=candidate_id,
        process_result=_successful_process_result(),
        stdout_path=stdout,
        stderr_path=stderr,
        episode_bundle_marker_paths=marker_paths,
    )
    assert result["status"] == "PROCESS_COMPLETED_SEALED"
    validated = validate_route_b_process_completion(row, candidate_id=candidate_id)
    assert validated["status"] == "PROCESS_COMPLETED_SEALED"
    again = write_route_b_process_completion(
        row,
        candidate_id=candidate_id,
        process_result=_successful_process_result(),
        stdout_path=stdout,
        stderr_path=stderr,
        episode_bundle_marker_paths=marker_paths,
    )
    assert again["receipt"]["receipt_sha256"] == result["receipt"]["receipt_sha256"]
    assert again["seal"]["seal_sha256"] == result["seal"]["seal_sha256"]

    topology_tampered = dict(row)
    topology_tampered["evidence_aggregation_topology"] = "canonical16"
    with pytest.raises(PostformalEvalError, match="topology"):
        validate_route_b_process_completion(topology_tampered, candidate_id=candidate_id)

    identity_tampered = dict(row)
    identity_tampered["source_config_sha256"] = "0" * 64
    with pytest.raises(PostformalEvalError, match="row receipt|candidate identity|source/evaluated/F3"):
        validate_route_b_process_completion(identity_tampered, candidate_id=candidate_id)

    first_episode_tampered = dict(row)
    first_episode_tampered["first_episode_only"] = False
    with pytest.raises(PostformalEvalError, match="first episode|first-episode"):
        validate_route_b_process_completion(first_episode_tampered, candidate_id=candidate_id)


def test_route_b_builder_renamed_checkpoint_step_is_completion_compatible(tmp_path: Path):
    row, candidate_id, marker_paths, stdout, stderr = _route_b_process_contract_fixture(
        tmp_path, checkpoint_name="candidate.pt", candidate_step=250
    )
    result = write_route_b_process_completion(
        row,
        candidate_id=candidate_id,
        process_result=_successful_process_result(),
        stdout_path=stdout,
        stderr_path=stderr,
        episode_bundle_marker_paths=marker_paths,
    )
    assert result["status"] == "PROCESS_COMPLETED_SEALED"
    assert validate_route_b_process_completion(row, candidate_id=candidate_id)["status"] == "PROCESS_COMPLETED_SEALED"


def test_route_b_builder_rejects_unnamed_checkpoint_without_candidate_step(tmp_path: Path):
    checkpoint = tmp_path / "candidate.pt"
    config = tmp_path / "config.yaml"
    checkpoint.write_bytes(b"candidate")
    config.write_text("seed: 0\n", encoding="utf-8")
    candidate = {
        "evaluated_checkpoint_path": str(checkpoint),
        "evaluated_checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        "config_path": str(config),
        "config_sha256": hashlib.sha256(config.read_bytes()).hexdigest(),
        "source_lock_sha256": "c5cfd505ed206f87c480f88b5faa95c5f1e9e99ba9679609621ce1aa3b5f0c40",
        "source_config_sha256": "c" * 64,
        "materialization_sha256": "d" * 64,
        "materialized_config_sha256": "e" * 64,
        "adaptation_bundle_sha256": "f" * 64,
    }
    with pytest.raises(PostformalEvalError, match="step is not derivable"):
        build_route_b_queue(candidate, cell="B1", topology="pooled_seed16", output_root=tmp_path / "queue")


@pytest.mark.parametrize("tamper", ["missing_receipt", "stale_step", "rehashed_step", "identity_divergence"])
def test_route_b_process_completion_rejects_untrusted_queue_row_receipt_and_step(
    tmp_path: Path, tamper: str
):
    row, candidate_id, marker_paths, stdout, stderr = _route_b_process_contract_fixture(tmp_path / tamper)
    tampered = dict(row)
    if tamper == "missing_receipt":
        tampered.pop("row_receipt_sha256")
    elif tamper == "stale_step":
        tampered["step"] = 251
    elif tamper == "rehashed_step":
        tampered["step"] = 251
        unsigned = dict(tampered)
        unsigned.pop("row_receipt_sha256", None)
        tampered["row_receipt_sha256"] = postformal_eval._queue_row_receipt(unsigned)
    else:
        tampered["config_path"] = str(Path(row["config_path"]).with_name("tampered.yaml"))
        unsigned = dict(tampered)
        unsigned.pop("row_receipt_sha256", None)
        tampered["row_receipt_sha256"] = postformal_eval._queue_row_receipt(unsigned)

    expected_error = {
        "missing_receipt": "row receipt",
        "stale_step": "row receipt",
        "rehashed_step": "top-level step|candidate step",
        "identity_divergence": "top-level/nested identity",
    }[tamper]
    with pytest.raises(PostformalEvalError, match=expected_error):
        write_route_b_process_completion(
            tampered,
            candidate_id=candidate_id,
            process_result=_successful_process_result(),
            stdout_path=stdout,
            stderr_path=stderr,
            episode_bundle_marker_paths=marker_paths,
        )
    root = Path(row["evaluation_root"])
    assert not (root / "process_receipt.json").exists()
    assert not (root / "PROCESS_COMPLETED.seal.json").exists()


def test_route_a_process_completion_failure_and_mutations_never_admit(tmp_path: Path):
    row, candidate_id, marker_paths, stdout, stderr = _process_contract_fixture(tmp_path)
    with pytest.raises(PostformalEvalError, match="exit_code=0"):
        write_route_a_process_completion(
            row,
            candidate_id=candidate_id,
            process_result={**_successful_process_result(), "exit_code": 7},
            stdout_path=stdout,
            stderr_path=stderr,
            episode_bundle_marker_paths=marker_paths,
        )
    assert not (Path(row["evaluation_root"]) / "process_receipt.json").exists()
    marker_paths[0].write_text(marker_paths[0].read_text(encoding="utf-8").replace('"env_id":0', '"env_id":15'), encoding="utf-8")
    with pytest.raises(PostformalEvalError, match="marker env coverage|identity"):
        write_route_a_process_completion(
            row,
            candidate_id=candidate_id,
            process_result=_successful_process_result(),
            stdout_path=stdout,
            stderr_path=stderr,
            episode_bundle_marker_paths=marker_paths,
        )
    assert not (Path(row["evaluation_root"]) / "process_receipt.json").exists()


def _rewrite_marker_arm_identity(marker_path: Path, *, top_level_env_id: object) -> None:
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    arm_path = Path(marker["arm_record_path"])
    arm = json.loads(arm_path.read_text(encoding="utf-8"))
    arm["env_id"] = top_level_env_id
    unsigned = dict(arm)
    unsigned.pop("record_id", None)
    arm["record_id"] = hashlib.sha256(canonical_json_bytes(unsigned)).hexdigest()
    arm_bytes = canonical_json_bytes(arm) + b"\n"
    arm_path.write_bytes(arm_bytes)
    marker["arm_record_sha256"] = hashlib.sha256(arm_bytes).hexdigest()
    marker["arm_record_id"] = arm["record_id"]
    marker_path.write_bytes(canonical_json_bytes(marker) + b"\n")


def test_route_a_process_completion_rejects_missing_bundle_and_arm_identity_mutations(tmp_path: Path):
    row, candidate_id, marker_paths, stdout, stderr = _process_contract_fixture(tmp_path / "missing")
    with pytest.raises(PostformalEvalError, match="exactly 16 episode bundle"):
        write_route_a_process_completion(
            row,
            candidate_id=candidate_id,
            process_result=_successful_process_result(),
            stdout_path=stdout,
            stderr_path=stderr,
            episode_bundle_marker_paths=marker_paths[:-1],
        )
    assert not (Path(row["evaluation_root"]) / "process_receipt.json").exists()

    row, candidate_id, marker_paths, stdout, stderr = _process_contract_fixture(tmp_path / "arm")
    _rewrite_marker_arm_identity(marker_paths[0], top_level_env_id=99)
    with pytest.raises(PostformalEvalError, match="provenance env_id|identity"):
        write_route_a_process_completion(
            row,
            candidate_id=candidate_id,
            process_result=_successful_process_result(),
            stdout_path=stdout,
            stderr_path=stderr,
            episode_bundle_marker_paths=marker_paths,
        )
    assert not (Path(row["evaluation_root"]) / "process_receipt.json").exists()


def test_route_a_process_completion_accepts_matching_optional_arm_env_id(tmp_path: Path):
    row, candidate_id, marker_paths, stdout, stderr = _process_contract_fixture(tmp_path / "matching-int")
    _rewrite_marker_arm_identity(marker_paths[0], top_level_env_id=0)
    result = write_route_a_process_completion(
        row,
        candidate_id=candidate_id,
        process_result=_successful_process_result(),
        stdout_path=stdout,
        stderr_path=stderr,
        episode_bundle_marker_paths=marker_paths,
    )
    assert result["status"] == "PROCESS_COMPLETED_SEALED"


@pytest.mark.parametrize("malformed_env_id", [False, 0.0])
def test_route_a_process_completion_rejects_malformed_optional_arm_env_id(tmp_path: Path, malformed_env_id: object):
    row, candidate_id, marker_paths, stdout, stderr = _process_contract_fixture(
        tmp_path / ("malformed-bool" if malformed_env_id is False else "malformed-float")
    )
    _rewrite_marker_arm_identity(marker_paths[0], top_level_env_id=malformed_env_id)
    with pytest.raises(PostformalEvalError, match="top-level env_id"):
        write_route_a_process_completion(
            row,
            candidate_id=candidate_id,
            process_result=_successful_process_result(),
            stdout_path=stdout,
            stderr_path=stderr,
            episode_bundle_marker_paths=marker_paths,
        )
    root = Path(row["evaluation_root"])
    assert not (root / "process_receipt.json").exists()
    assert not (root / "PROCESS_COMPLETED.seal.json").exists()


def test_route_a_process_completion_rejects_log_receipt_seal_and_artifact_mutations(tmp_path: Path):
    row, candidate_id, marker_paths, stdout, stderr = _process_contract_fixture(tmp_path / "logs")
    write_route_a_process_completion(
        row,
        candidate_id=candidate_id,
        process_result=_successful_process_result(),
        stdout_path=stdout,
        stderr_path=stderr,
        episode_bundle_marker_paths=marker_paths,
    )
    stdout.write_text("mutated stdout\n", encoding="utf-8")
    with pytest.raises(PostformalEvalError, match="stdout log changed"):
        validate_route_a_process_completion(row, candidate_id=candidate_id)

    row, candidate_id, marker_paths, stdout, stderr = _process_contract_fixture(tmp_path / "receipt")
    write_route_a_process_completion(
        row,
        candidate_id=candidate_id,
        process_result=_successful_process_result(),
        stdout_path=stdout,
        stderr_path=stderr,
        episode_bundle_marker_paths=marker_paths,
    )
    receipt_path = Path(row["evaluation_root"]) / "process_receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["candidate_id"] = "b" * 64
    receipt_path.write_bytes(canonical_json_bytes(receipt) + b"\n")
    with pytest.raises(PostformalEvalError, match="self digest"):
        validate_route_a_process_completion(row, candidate_id=candidate_id)

    row, candidate_id, marker_paths, stdout, stderr = _process_contract_fixture(tmp_path / "seal")
    write_route_a_process_completion(
        row,
        candidate_id=candidate_id,
        process_result=_successful_process_result(),
        stdout_path=stdout,
        stderr_path=stderr,
        episode_bundle_marker_paths=marker_paths,
    )
    seal_path = Path(row["evaluation_root"]) / "PROCESS_COMPLETED.seal.json"
    seal = json.loads(seal_path.read_text(encoding="utf-8"))
    seal["candidate_id"] = "b" * 64
    seal_path.write_bytes(canonical_json_bytes(seal) + b"\n")
    with pytest.raises(PostformalEvalError, match="self digest"):
        validate_route_a_process_completion(row, candidate_id=candidate_id)

    row, candidate_id, marker_paths, stdout, stderr = _process_contract_fixture(tmp_path / "artifact")
    task_path = Path(json.loads(marker_paths[0].read_text(encoding="utf-8"))["task_record_path"])
    task_path.write_text(task_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(PostformalEvalError, match="artifact digest"):
        write_route_a_process_completion(
            row,
            candidate_id=candidate_id,
            process_result=_successful_process_result(),
            stdout_path=stdout,
            stderr_path=stderr,
            episode_bundle_marker_paths=marker_paths,
        )
    assert not (Path(row["evaluation_root"]) / "process_receipt.json").exists()
