"""CPU/no-sim tests for the pull-only environment and Hydra namespace."""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from hydra import compose, initialize_config_dir
import pytest

from scriptsFORhuman.pull_v0 import build_p1_anchor_stop_receipts as anchor_receipts
from scriptsFORhuman.pull_v0 import build_pull_v0_repair_r7_receipt as repair_r7
from scriptsFORhuman.pull_v0 import build_pull_v0_repair_r8_receipt as repair_r8
from scriptsFORhuman.pull_v0 import build_pull_v0_repair_r9_receipt as repair_r9
from scriptsFORhuman.pull_v0 import build_pull_v0_repair_r10_receipt as repair_r10
from scriptsFORhuman.pull_v0 import build_pull_v0_repair_r11_receipt as repair_r11
from scriptsFORhuman.pull_v0 import build_pull_v0_repair_r12_receipt as repair_r12
from scriptsFORhuman.pull_v0 import build_pull_v0_repair_r13_receipt as repair_r13
from scriptsFORhuman.pull_v0 import build_pull_v0_repair_r14_receipt as repair_r14
from scriptsFORhuman.pull_v0 import build_pull_v0_repair_r15_receipt as repair_r15
from scriptsFORhuman.pull_v0 import build_pull_v0_repair_r16_receipt as repair_r16
from scriptsFORhuman.pull_v0 import capture_p1_anchor_gpu_evidence as attempt19_gpu_evidence
from scriptsFORhuman.pull_v0 import build_pull_v0_gpu_lease_amendment_receipt as gpu_lease_amendment
from scriptsFORhuman.pull_v0 import build_pull_v0_attempt18_prelaunch_infra_r15e_receipts as r15e_receipts
from scriptsFORhuman.pull_v0 import build_pull_v0_r15f_receipt as r15f_receipts
from scriptsFORhuman.pull_v0 import run_p1_push_anchor as anchor_runner
from gr00t.rl import eval_agent_trl as eval_agent


ROOT = Path(__file__).resolve().parents[3]
CONFIG_ROOT = ROOT / "gr00t/rl/config"
PULL_ENV_SOURCE = ROOT / "gr00t/rl/envs/door/door_open_a2_pull.py"
PUSH_ENV_SOURCE = ROOT / "gr00t/rl/envs/door/door_open_a2_base.py"
SCENARIO_SOURCE = ROOT / "gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py"


def _pull_class() -> ast.ClassDef:
    tree = ast.parse(PULL_ENV_SOURCE.read_text(encoding="utf-8"))
    return next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "DoorOpenA2Pull"
    )


def _method_source(name: str) -> str:
    method = next(
        node for node in _pull_class().body if isinstance(node, ast.FunctionDef) and node.name == name
    )
    return ast.unparse(method)


def test_pull_namespace_composes_without_mutating_push_config_choices():
    with initialize_config_dir(version_base="1.1", config_dir=str(CONFIG_ROOT.resolve())):
        config = compose(
            config_name="base",
            overrides=[
                "+exp=wbmanip/door_open_a2_pull_lstm",
                "+ablation=wbmanip/pull_v0_p0_architecture_smoke",
            ],
        )

    assert config.env._target_ == "gr00t.rl.envs.door.door_open_a2_pull.DoorOpenA2Pull"
    assert config.project_name == "a2_piper_full_stage_a2_pull"
    assert config.env.config.a2_pull_door_open_io == "in"
    assert config.env.config.a2_pull_door_open_lr == "right"
    assert config.env.config.a2_pull_target_orientation_wxyz == [-0.5, -0.5, 0.5, 0.5]
    assert config.env.config.target_root_pos == [-2.0, 0.0, 0.5]
    assert config.env.config.a2_v20_send_latch_enabled is False
    assert config.env.config.a2_v20_pre_send_crossing_mode == "disabled"
    assert config.env.config.a2_corridor_enabled is False
    assert config.rewards.reward_scales.pull_door_hinge == 6.0
    assert config.rewards.reward_scales.push_door_hinge == 0.0
    assert config.robot.dof_effort_limit_list[-2:] == [45.0, 45.0]
    assert config.robot.control.stiffness.arm_j7 == 1300.0
    assert config.robot.control.damping.arm_j8 == 32.0


def test_pull_p0g_canonical_smoke_composes_as_exact_64_by_50_topology():
    with initialize_config_dir(version_base="1.1", config_dir=str(CONFIG_ROOT.resolve())):
        config = compose(
            config_name="base",
            overrides=[
                "+exp=wbmanip/door_open_a2_pull_lstm",
                "+ablation=wbmanip/pull_v0_p0_canonical_smoke",
            ],
        )

    assert config.num_envs == 64
    assert config.algo.trl.num_total_batches == 50
    assert config.callbacks.model_save.save_frequency == 25
    assert config.algo.config.num_learning_epochs == 5
    assert config.algo.config.num_mini_batches == 4
    assert config.checkpoint_load_mode == "policy_only"
    assert config.auto_load_latest is False
    assert config.use_wandb is False
    assert config.env.config.a2_pull_threshold_mode == "report_only"
    assert config.env.config.a2_pull_effort_provenance == "ESTIMATE_ONLY"
    assert config.env.config.a2_pull_finger_profile == "V20_G4_45N_KP1300_KD32"
    assert config.robot.dof_effort_limit_list[-2:] == [45.0, 45.0]


def test_pull_p1_push_anchor_composes_with_the_amended_fixture_and_probe_gate():
    with initialize_config_dir(version_base="1.1", config_dir=str(CONFIG_ROOT.resolve())):
        config = compose(
            config_name="base",
            overrides=[
                "+exp=wbmanip/door_open_a2_base_lstm",
                "+ablation=wbmanip/pull_v0_p1_push_anchor",
            ],
        )

    assert config.num_envs == 1
    assert config.env.config.a2_pull_door_open_io == "out"
    assert config.env.config.a2_pull_p1_central_fixture_enabled is True
    assert config.env.config.max_stage_time == [400, 100, 100, 100, 100, 200]
    assert config.env.config.a2_v20_R1_plan_id == "disabled"
    assert config.env.config.a2_door_weight_range == [80.0, 160.0]
    assert config.env.config.a2_pull_hook_profile == "P1_PRESENT_0P050M"
    assert config.env.config.a2_hold_diagnostic_max_contact_data_count_per_prim == 64
    assert config.algo.config.eval.a2_hold_oracle_enabled is True
    assert config.algo.config.eval.a2_pull_p1_probe_enabled is True
    assert config.algo.config.eval.a2_pull_p1_probe_mode == "push_anchor"
    assert config.algo.config.eval.a2_pull_p1_proof_offset_m == 0.006
    assert config.algo.config.eval.a2_v20_arc_probe_enabled is False
    assert config.algo.config.eval.a2_v20_arc_probe_mode == "F1"
    assert config.algo.config.eval.a2_v20_arc_probe_target_hinge_rad == 0.25
    assert config.robot.dof_effort_limit_list[-2:] == [45.0, 45.0]
    assert config.robot.control.stiffness.arm_j7 == 1300.0
    assert config.robot.control.damping.arm_j8 == 32.0


def test_shared_contact_sensor_default_remains_eight_while_anchor_override_is_sixty_four():
    shared = (CONFIG_ROOT / "env/door_open_a2_base.yaml").read_text(encoding="utf-8")
    anchor = (CONFIG_ROOT / "ablation/wbmanip/pull_v0_p1_push_anchor.yaml").read_text(
        encoding="utf-8"
    )
    assert "a2_hold_diagnostic_max_contact_data_count_per_prim: 8" in shared
    assert "a2_hold_diagnostic_max_contact_data_count_per_prim: 64" in anchor


def test_pull_p1_central_fixture_is_exact_and_uses_high_level_cfg_replacement():
    source = SCENARIO_SOURCE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    assignment = next(
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name)
            and target.id == "_PULL_P1_CENTRAL_FIXTURE"
            for target in node.targets
        )
    )
    fixture = ast.literal_eval(assignment.value)
    assert fixture == {
        "rand_door_width": 0.95,
        "rand_door_height": 2.05,
        "rand_door_handle_height": 0.95,
        "rand_door_handle_width": 0.115,
        "rand_door_weight": 120.0,
        "rand_axle_length": 0.195,
        "rand_handle_length": 0.125,
        "rand_hook_length": 0.05,
        "rand_handle_radius": 0.013,
        "rand_spawn_hook": True,
        "rand_hinge_drive_max_force": 7.25,
        "rand_hinge_drive_stiffness": 5.5,
        "rand_handle_drive_max_force": 2.0,
    }
    selector_start = source.index("def _apply_pull_p1_central_fixture")
    selector_end = source.index("\ndef ", selector_start + 5)
    selector = source[selector_start:selector_end]
    assert "base_asset.replace(**_PULL_P1_CENTRAL_FIXTURE)" in selector
    assert "spawn_cfg.replace(assets_cfg=[central_asset], random_choice=False)" in selector
    for forbidden in ("pxr.", "stage.DefinePrim", "omni.usd"):
        assert forbidden not in selector


def test_pull_reset_and_staging_are_signed_and_final_travel_is_negative_x():
    reset = _method_source("_reset_root_states")
    transition = _method_source("_stage_0_to_1_advance_condition")
    stage4 = _method_source("_stage_4_to_5_advance_condition")
    completion = _method_source("_stage_5_to_complete_condition")
    assert "self._pull_direction.approach_side_x" in reset
    assert "a2_pull_robot_initial_yaw_rad" in reset
    assert "a2_signed_stage0_staging_band_mask" in transition
    assert "signed_crossing_progress" in stage4
    assert "_get_a2_pull_whole_body_clear_mask" in completion


def test_pull_stage_transitions_are_event_and_contact_conditioned():
    stage2 = _method_source("_stage_2_to_3_advance_condition")
    stage3 = _method_source("_stage_3_to_4_advance_condition")
    stage4 = _method_source("_stage_4_to_5_advance_condition")
    completion = _method_source("_stage_5_to_complete_condition")
    assert "E2_TENSILE_CAPTURE" in stage2 and "both_contact" in stage2
    assert "E4_POSITIVE_HINGE_RETAINED" in stage3 and "panel" in stage3
    assert "E6_PATH_REVERSAL_ENTRY" in stage4 and "signed_crossing_progress" in stage4
    assert "E7_WHOLE_BODY_CLEAR" in completion and "_get_a2_pull_whole_body_clear_mask" in completion


def test_pull_p1_acquisition_is_explicit_and_stage2_gate_free():
    base_source = PUSH_ENV_SOURCE.read_text(encoding="utf-8")
    assert "PULL_P1_ACQUIRE" in base_source
    assert "stage2_grasp_gate_required" in base_source
    assert "first_episode_active_mask" in base_source


def test_push_anchor_stage0_admission_is_signed_high_level_and_dls_is_not_discarded():
    base_source = PUSH_ENV_SOURCE.read_text(encoding="utf-8")
    assert "a2_pull_p1_stage0_base_command" in base_source
    assert "a2_signed_stage0_staging_band_mask" in base_source
    assert "a2_signed_stage0_nearest_staging_target" in base_source
    assert "a2_hold_base_relief_command" in base_source
    assert "a2_pull_p1_stage0_staging_speed_mps" in base_source
    assert "a2_pull_p1_stage0_settle_steps" in base_source
    assert "a2_pull_p1_stage0_timeout_steps" in base_source
    assert "dls_finally_applied" in base_source
    assert "stage0_timeout" in base_source
    assert "self.stage_buf[" not in base_source[base_source.index("def a2_pull_p1_stage0_base_command"):base_source.index("def a2_pull_p1_stage0_base_command") + 1800]


def test_push_anchor_stage0_callsite_uses_canonical_wxyz_quaternion_for_command_and_trace():
    source = PUSH_ENV_SOURCE.read_text(encoding="utf-8")
    stage0_start = source.index("if pull_p1_acquisition and torch.any(active):")
    trace_start = source.index("if pull_p1_acquisition:\n            trace_mask", stage0_start)
    stage0_region = source[stage0_start:]
    trace_region = source[trace_start:]
    assert 'self.simulator.scene.articulations["robot"].data.root_quat_w' in stage0_region
    assert "stage0_root_quat_w" in stage0_region[: trace_start - stage0_start]
    assert "stage0_root_quat_w[env_id : env_id + 1]" in trace_region
    assert "root_states[:, 3:7]" not in stage0_region
    assert "root_states[env_id : env_id + 1, 3:7]" not in trace_region
    assert "root_states[env_id, 3:7]" not in trace_region


def test_push_anchor_terminal_schema_is_base_owned_and_pull_keeps_e0_e7_namespace_separate():
    base_source = PUSH_ENV_SOURCE.read_text(encoding="utf-8")
    pull_source = PULL_ENV_SOURCE.read_text(encoding="utf-8")
    assert "push_anchor_admission" in base_source
    assert "pull_only_events" in base_source
    assert "push_anchor_admission" not in pull_source[pull_source.index("def _get_a2_terminal_diagnostics"):]


def test_pull_target_orientation_is_overlay_selected_and_pregrasp_is_on_positive_x():
    class_source = ast.unparse(_pull_class())
    orientation = _method_source("_get_a2_grasp_target_orientation_wxyz")
    assert "A2_PREGRASP_OFFSET = (0.1, 0.0, 0.0)" in class_source
    assert "A2_PULL_V0_TARGET_ORIENTATION_WXYZ" in orientation
    push_source = PUSH_ENV_SOURCE.read_text(encoding="utf-8")
    assert push_source.count("rot=self._get_a2_grasp_target_orientation_wxyz()") == 2


def test_pull_scenario_selector_is_config_only_and_does_not_mutate_shared_asset_objects():
    source = SCENARIO_SOURCE.read_text(encoding="utf-8")
    selector_start = source.index("def _apply_door_open_io")
    selector_end = source.index("\ndef ", selector_start + 5)
    selector = source[selector_start:selector_end]
    assert "asset_cfg.replace(" in selector
    assert "rand_door_open_io=door_open_io" in selector
    assert "spawn_cfg.replace(assets_cfg=variants, random_choice=False)" in selector
    for forbidden in ("pxr.", "stage.DefinePrim", "omni.usd"):
        assert forbidden not in selector


def test_pull_reward_registry_uses_pull_names_and_keeps_direct_force_disabled():
    with initialize_config_dir(version_base="1.1", config_dir=str(CONFIG_ROOT.resolve())):
        config = compose(
            config_name="base",
            overrides=[
                "+exp=wbmanip/door_open_a2_pull_lstm",
                "+ablation=wbmanip/pull_v0_p0_architecture_smoke",
            ],
        )
    scales = config.rewards.reward_scales
    assert scales.pull_door_handle == 0.0
    assert scales.pull_door_hinge == 6.0
    assert scales.push_door_handle == 0.0
    assert scales.push_door_hinge == 0.0
    assert scales.push_door_force == 0.0


def test_pull_disables_v20_behavior_and_ports_route_crossing_by_signed_coordinate():
    selector_guard = _method_source("_update_a2_v20_state")
    crossing_hook = _method_source("_get_a2_route_crossing_coordinate")
    assert "a2_v20_R1_send_curriculum_enabled" in selector_guard
    assert "a2_v20_send_latch_enabled" in selector_guard
    assert "a2_v20_telemetry_enabled" in selector_guard
    assert "a2_v20_traversal_economics_enabled" in selector_guard
    assert "a2_corridor_enabled" in selector_guard
    assert 'crossing_mode != \'disabled\'' in selector_guard
    assert "signed_crossing_progress" in crossing_hook


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _post_r1_summary(
    *, capture: bool, latch: bool, hinge: float | None, body_force: float
) -> dict:
    events = {
        event_name: False
        for event_name in (
            "E0_RESET_VALID",
            "E1_OUTSIDE_FACE_PREGRASP",
            "E2_TENSILE_CAPTURE",
            "E3_LATCH_RELEASE",
            "E4_POSITIVE_HINGE_RETAINED",
            "E5_CLEARANCE_DECISION",
            "E6_PATH_REVERSAL_ENTRY",
            "E7_WHOLE_BODY_CLEAR",
        )
    }
    events.update(
        {
            "E0_RESET_VALID": True,
            "E1_OUTSIDE_FACE_PREGRASP": True,
            "E2_TENSILE_CAPTURE": capture,
            "E3_LATCH_RELEASE": latch,
            "E4_POSITIVE_HINGE_RETAINED": capture and latch,
            "E5_CLEARANCE_DECISION": capture and latch,
            "E6_PATH_REVERSAL_ENTRY": capture and latch,
            "E7_WHOLE_BODY_CLEAR": capture and latch,
        }
    )
    return {
        "schema": "a2_piper_pull_v0_p1_scripted_probe_runtime_v1",
        "probe_mode": "push_anchor",
        "status": "PASS" if capture and latch else "FAIL",
        "command_contract": {
            "commandable_dofs_only": True,
            "arm": "Cartesian DLS",
            "gripper": "high-level gripper primitive",
            "base": "bounded planar velocity",
            "low_level_usd_runtime_writes": False,
        },
        "acquisition_contract": {
            "enabled": True,
            "admission_gate": "first_episode_active_only_for_push_anchor",
            "stage2_grasp_gate_required": False,
            "stage0_predicates_reported_separately": True,
            "proof_world_direction": "+X",
        },
        "per_env_outcome": ["RETAINED" if capture and latch else "NO_GATE"],
        "per_env_pass": [
            capture
            and latch
            and hinge is not None
            and hinge >= 0.25
            and body_force <= 1.0
        ],
        "per_env_proof_completed": [capture],
        "per_env_latch_released": [latch],
        "per_env_max_hinge_rad": [hinge],
        "per_env_max_body_force_n": [body_force],
        "per_env_proof_samples": [[]],
        "per_env_arc_samples": [[]],
        "finalize_called": True,
        "episode_events": events,
    }


def _post_r1_metrics(summary: dict) -> dict:
    return {
        "completed_episodes": 1,
        "episode_terminal_reasons": ["stage_overtime"],
        "episode_max_stage_reached": [0],
        "episode_terminal_diagnostics": [
            {
                "pull_v0_stage0_predicates": {
                    "staging_band": False,
                    "arm_default": False,
                    "base_still": True,
                    "event_admission": "report_only",
                },
                "pull_v0_scripted_activation": {
                    "first_control_step": "N/A",
                    "admission_stage2_grasp_gate": False,
                    "proof_world_direction": "+X",
                },
                "pull_v0_episode": {"event_reached": summary["episode_events"]},
            }
        ],
    }


def _post_r1_process_receipt(*, attempt: int, plan: Path, log: Path, summary: Path, metrics: Path) -> dict:
    plan_sha256 = json.loads(plan.read_text(encoding="utf-8")).get("plan_sha256")
    return {
        "schema_version": "pull_v0_p1_push_anchor_process_v1",
        "attempt": attempt,
        "returncode": 0,
        "natural_exit": True,
        "application_success": True,
        "plan_path": str(plan),
        "plan_sha256": plan_sha256,
        "stdout_stderr_path": str(log),
        "stdout_stderr_sha256": _sha256(log),
        "summary_path": str(summary),
        "summary_sha256": _sha256(summary),
        "metrics_path": str(metrics),
        "metrics_sha256": _sha256(metrics),
        "repair_receipt_sha256": anchor_receipts.EXPECTED_REPAIR_RECEIPT_SHA256,
    }


def test_post_r1_attempt_helpers_accept_three_and_preserve_historical_paths():
    assert anchor_runner._validate_attempt_index(3) == 3
    assert anchor_receipts._post_r1_attempt_arg("3") == 3
    assert anchor_runner._attempt_output_root(3) != anchor_runner._attempt_output_root(2)
    assert anchor_runner._attempt_plan_path(3).name == "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT3_PLAN.json"
    with pytest.raises(RuntimeError, match="immutable"):
        anchor_runner._require_post_r1_attempt(1)
    with pytest.raises(RuntimeError, match="immutable"):
        anchor_runner._require_post_r1_attempt(2)
    for invalid in (0, -1, True, "3"):
        with pytest.raises((ValueError, RuntimeError)):
            anchor_runner._validate_attempt_index(invalid)
    with pytest.raises(Exception, match=">= 3"):
        anchor_receipts._post_r1_attempt_arg("2")


def test_post_r1_receipt_classifier_requires_every_hard_gate():
    process = {"application_success": True, "natural_exit": True, "returncode": 0}
    blocked_summary = _post_r1_summary(capture=False, latch=False, hinge=None, body_force=0.0)
    blocked = anchor_receipts.classify_post_r1_attempt(
        process_receipt=process,
        summary=blocked_summary,
        metrics=_post_r1_metrics(blocked_summary),
    )
    assert blocked == {
        "status": "BLOCKED",
        "probe_validity": "PROBE_INVALID",
        "admission_blocker": "NO_STABLE_BILATERAL_CAPTURE",
        "pull_mechanism_verdict": "NOT_ASSESSED",
    }
    passing_summary = _post_r1_summary(capture=True, latch=True, hinge=0.25, body_force=0.0)
    passing = anchor_receipts.classify_post_r1_attempt(
        process_receipt=process,
        summary=passing_summary,
        metrics=_post_r1_metrics(passing_summary),
    )
    assert passing["status"] == "PASS"
    assert passing["probe_validity"] == "PROBE_VALID"
    assert passing["pull_mechanism_verdict"] == "NOT_ASSESSED"
    no_hinge_summary = _post_r1_summary(capture=True, latch=True, hinge=None, body_force=0.0)
    no_hinge = anchor_receipts.classify_post_r1_attempt(
        process_receipt=process,
        summary=no_hinge_summary,
        metrics=_post_r1_metrics(no_hinge_summary),
    )
    assert no_hinge["status"] == "BLOCKED"
    assert no_hinge["admission_blocker"] == "HINGE_PROGRESS_BELOW_0P25_RAD"
    assert no_hinge["pull_mechanism_verdict"] == "NOT_ASSESSED"


def test_post_r1_receipt_builder_validates_artifact_hash_chain_without_runtime_outputs(tmp_path):
    attempt = 3
    plan = tmp_path / "attempt3_plan.json"
    process_path = tmp_path / "process_receipt.json"
    log = tmp_path / "stdout_stderr.log"
    summary_path = tmp_path / "summary.json"
    metrics_path = tmp_path / "metrics.json"
    plan.write_text(
        json.dumps(
            {
                "attempt": attempt,
                "implementation_repair_used": True,
                "plan_sha256": "synthetic-plan",
                "repair_receipt": {
                    "path": "scriptsFORhuman/pull_v0/PULL_V0_REPAIR_R1_RECEIPT.json",
                    "sha256": anchor_receipts.EXPECTED_REPAIR_RECEIPT_SHA256,
                    "revision": "R1",
                    "stale_candidate_id": anchor_receipts.EXPECTED_STALE_CANDIDATE_ID,
                },
            }
        ),
        encoding="utf-8",
    )
    log.write_text("synthetic post-R1 log", encoding="utf-8")
    summary = _post_r1_summary(capture=False, latch=False, hinge=0.0, body_force=0.0)
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    metrics = _post_r1_metrics(summary)
    metrics_path.write_text(json.dumps(metrics), encoding="utf-8")
    process_path.write_text(
        json.dumps(
            _post_r1_process_receipt(
                attempt=attempt,
                plan=plan,
                log=log,
                summary=summary_path,
                metrics=metrics_path,
            )
        ),
        encoding="utf-8",
    )
    receipt = anchor_receipts.build_post_r1_attempt_receipt(
        attempt,
        plan_path=plan,
        process_receipt_path=process_path,
        log_path=log,
        summary_path=summary_path,
        metrics_path=metrics_path,
    )
    assert receipt["attempt"] == 3
    assert receipt["probe_validity"] == "PROBE_INVALID"
    assert receipt["admission_blocker"] == "NO_STABLE_BILATERAL_CAPTURE"


def test_attempt3_receipt_records_contract_failure_before_probe_without_pull_verdict():
    attempt_root = anchor_receipts.LOG_ROOT / "attempt3"
    receipt = anchor_receipts.build_post_r1_attempt_receipt(
        3,
        plan_path=anchor_receipts.EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT3_PLAN.json",
        process_receipt_path=attempt_root / "process_receipt.json",
        log_path=attempt_root / "stdout_stderr.log",
        summary_path=attempt_root / "eval" / "a2_hold_oracle_summary.json",
        metrics_path=attempt_root / "eval" / "metrics_eval.json",
    )
    assert receipt["status"] == "BLOCKED"
    assert receipt["probe_validity"] == "PROBE_INVALID"
    assert receipt["admission_blocker"] == "APPLICATION_CONTRACT_ERROR_BEFORE_PROBE"
    assert receipt["pull_mechanism_verdict"] == "NOT_ASSESSED"
    assert receipt["application_contract_error"]["signature"] == (
        "TypeError: device must be torch.device; got str."
    )
    assert receipt["hard_gate"]["observed_max_hinge_rad"] == "N/A"
    assert receipt["hard_gate"]["observed_max_body_force_n"] == "N/A"
    assert receipt["artifacts"]["summary"] is None
    assert receipt["artifacts"]["metrics"] is None


def test_attempt4_requires_explicit_r2_binding_and_validates_the_canonical_receipt():
    with pytest.raises(RuntimeError, match="explicit --repair-receipt"):
        anchor_runner._read_repair_receipt(attempt=4)
    receipt, receipt_sha256 = anchor_runner._read_repair_receipt(
        anchor_receipts.REPAIR_R2_RECEIPT_PATH,
        attempt=4,
    )
    assert receipt["schema_version"] == "pull_v0_repair_r2_receipt_v1"
    assert receipt["repair_revision"] == "R2"
    assert receipt["parent_receipt"]["sha256"] == anchor_runner.EXPECTED_REPAIR_RECEIPT_SHA256
    assert receipt["trigger"]["attempt"] == 3
    assert receipt["supersedes"]["reason"] == "PRE_BIND_VALIDATION_COUNT_CORRECTION"
    assert receipt_sha256 != anchor_runner.EXPECTED_SUPERSEDED_R2_RECEIPT_SHA256
    assert receipt_sha256 == _sha256(anchor_receipts.REPAIR_R2_RECEIPT_PATH)


def test_attempt5_builder_consumes_actual_base_push_anchor_schema_without_pull_namespace():
    receipt = anchor_receipts.build_post_r1_attempt_receipt(
        5,
        plan_path=anchor_receipts.EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT5_PLAN.json",
        process_receipt_path=anchor_receipts.LOG_ROOT / "attempt5/process_receipt.json",
        log_path=anchor_receipts.LOG_ROOT / "attempt5/stdout_stderr.log",
        summary_path=anchor_receipts.LOG_ROOT / "attempt5/eval/a2_hold_oracle_summary.json",
        metrics_path=anchor_receipts.LOG_ROOT / "attempt5/eval/metrics_eval.json",
        repair_receipt_path=anchor_receipts.REPAIR_R3_RECEIPT_PATH,
    )
    assert receipt["status"] == "BLOCKED"
    assert receipt["probe_validity"] == "PROBE_INVALID"
    assert receipt["admission_blocker"] == (
        "RESET_BOUNDARY_CONTACT_UNQUALIFIED_BEFORE_STAGING"
    )
    assert receipt["pull_mechanism_verdict"] == "NOT_ASSESSED"
    assert receipt["hard_gate"]["pass"] is False
    assert receipt["hard_gate"]["observed_max_body_force_n"] == "N/A"
    assert receipt["reset_boundary"]["persistence"] == "INCONCLUSIVE"
    assert receipt["reset_boundary"]["causality"] == "INCONCLUSIVE"
    metrics = json.loads(
        (anchor_receipts.LOG_ROOT / "attempt5/eval/metrics_eval.json").read_text()
    )
    summary = json.loads(
        (anchor_receipts.LOG_ROOT / "attempt5/eval/a2_hold_oracle_summary.json").read_text()
    )
    admission = anchor_receipts._validate_actual_push_anchor_schema(
        summary=summary, metrics=metrics
    )
    assert admission["schema"] == (
        "a2_piper_pull_v0_push_anchor_admission_terminal_v1"
    )
    assert not any(key.startswith("pull_v0_") for key in admission)


def test_attempt5_remains_r3_bound_and_attempt6_requires_canonical_r4():
    receipt, receipt_sha256 = anchor_runner._read_repair_receipt(
        anchor_runner.REPAIR_R3_RECEIPT_PATH, attempt=5
    )
    assert receipt["repair_revision"] == "R3"
    assert receipt_sha256 == anchor_runner.EXPECTED_R3_RECEIPT_SHA256
    source = anchor_runner.Path(anchor_runner.__file__).read_text(encoding="utf-8")
    assert "REPAIR_R4_RECEIPT_PATH" in source
    assert "ATTEMPT5_RECEIPT_PATH" in source
    assert "attempt >= 6" in source
    r4 = anchor_runner.REPAIR_R4_RECEIPT_PATH
    r4_sha256 = _sha256(r4)
    with pytest.raises(RuntimeError, match="explicit --repair-receipt-sha256"):
        anchor_runner._read_repair_receipt(r4, attempt=6)
    with pytest.raises(RuntimeError):
        anchor_runner._read_repair_receipt(
            r4,
            attempt=6,
            repair_receipt_sha256="0" * 64,
        )
    validated, validated_sha256 = anchor_runner._read_repair_receipt(
        r4,
        attempt=6,
        repair_receipt_sha256=r4_sha256,
    )
    assert validated["repair_revision"] == "R4"
    assert validated_sha256 == r4_sha256


def test_attempt6_receipt_uses_actual_schema_and_classifies_watchdog_cross_talk():
    receipt = anchor_receipts.build_post_r1_attempt_receipt(
        6,
        plan_path=anchor_receipts.EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT6_PLAN.json",
        process_receipt_path=anchor_receipts.LOG_ROOT / "attempt6/process_receipt.json",
        log_path=anchor_receipts.LOG_ROOT / "attempt6/stdout_stderr.log",
        summary_path=anchor_receipts.LOG_ROOT / "attempt6/eval/a2_hold_oracle_summary.json",
        metrics_path=anchor_receipts.LOG_ROOT / "attempt6/eval/metrics_eval.json",
        repair_receipt_path=anchor_receipts.REPAIR_R4_RECEIPT_PATH,
    )
    assert receipt["schema_version"] == "pull_v0_p1_push_anchor_attempt_receipt_v6"
    assert receipt["status"] == "BLOCKED"
    assert receipt["probe_validity"] == "PROBE_INVALID"
    assert receipt["admission_blocker"] == "GENERIC_BASE_RELIEF_WATCHDOG_CROSS_TALK"
    assert receipt["pull_mechanism_verdict"] == "NOT_ASSESSED"
    assert receipt["reset_boundary"]["window_complete"] is True
    assert receipt["reset_boundary"]["transient_observed"] is True
    assert receipt["watchdog_cross_talk"]["stage0_timeout_independent"] is True


def test_attempt7_requires_exact_r5_sha_and_r5_attempt6_r4_ancestry(tmp_path, monkeypatch):
    r5 = anchor_runner.REPAIR_R5_RECEIPT_PATH
    r5_sha256 = _sha256(r5)
    with pytest.raises(RuntimeError, match="explicit --repair-receipt-sha256"):
        anchor_runner._read_repair_receipt(r5, attempt=7)
    with pytest.raises(RuntimeError):
        anchor_runner._read_repair_receipt(r5, attempt=7, repair_receipt_sha256="0" * 64)
    validated, validated_sha256 = anchor_runner._read_repair_receipt(
        r5,
        attempt=7,
        repair_receipt_sha256=r5_sha256,
    )
    assert validated["repair_revision"] == "R5"
    assert validated_sha256 == r5_sha256

    bad_path = tmp_path / "bad_r5.json"
    bad = json.loads(r5.read_text(encoding="utf-8"))
    bad["parent_receipt"]["sha256"] = "0" * 64
    bad_path.write_text(json.dumps(bad), encoding="utf-8")
    monkeypatch.setattr(anchor_runner, "REPAIR_R5_RECEIPT_PATH", bad_path)
    with pytest.raises(RuntimeError, match="R5 receipt identity"):
        anchor_runner._read_repair_receipt(
            bad_path,
            attempt=7,
            repair_receipt_sha256=_sha256(bad_path),
        )


def test_stage0_command_response_telemetry_is_report_only_and_post_executor_sourced():
    source = PUSH_ENV_SOURCE.read_text(encoding="utf-8")
    for field in (
        "stage0_command_response",
        "high_level_base_action_raw",
        "expected_scaled_body_command",
        "physical_base_command",
        "desired_world_xy_velocity",
        "downstream_lower_body_command",
        "observed_root_pos_w_post_executor",
        "observed_world_xy_velocity",
        "observed_world_xy_displacement",
        "progress_velocity_dot",
        "progress_velocity_cosine",
        "progress_displacement_dot",
        "progress_displacement_cosine",
        "observed_root_roll_rad",
        "observed_root_pitch_rad",
        "observed_root_height_m",
    ):
        assert f'"{field}"' in source
    assert "A2Base._get_a2_dog_actions" in source
    assert '"threshold_mode": "report_only"' in source
    assert "stage0_timeout = acquisition_wait & (" in source
    assert "self._set_a2_hold_outcome(stage0_timeout, \"PULL_P1_STAGE0_TIMEOUT\")" in source


def test_stage0_response_is_latched_before_terminal_admission_without_reconstruction():
    source = PUSH_ENV_SOURCE.read_text(encoding="utf-8")
    terminal_start = source.index("def _get_a2_push_anchor_admission_terminal_record")
    outcome_read = source.index("outcome_id =", terminal_start)
    admission_trace = source.index('"trace": list(self._a2_pull_p1_trace_records', terminal_start)
    assert terminal_start < outcome_read < admission_trace
    assert "_attach_a2_pull_p1_stage0_command_response" not in source
    callback = source.index("def _a2_base_pre_physics_command_callback")
    completion = source.index("def _complete_a2_pull_p1_stage0_command_response")
    assert callback < completion
    assert "self._a2_pull_p1_pending_response" in source[callback:completion]
    assert "self._a2_pull_p1_completed_response_latch" in source[completion:]


def _r7_valid_response_fixture():
    summary = json.loads(
        (anchor_receipts.LOG_ROOT / "attempt8/eval/a2_hold_oracle_summary.json").read_text(
            encoding="utf-8"
        )
    )
    metrics = json.loads(
        (anchor_receipts.LOG_ROOT / "attempt8/eval/metrics_eval.json").read_text(
            encoding="utf-8"
        )
    )
    admission = metrics["episode_terminal_diagnostics"][0]["push_anchor_admission"]
    responses = []
    for row_index, row in enumerate(admission["trace"]):
        if "stage0_predicates" not in row:
            continue
        row["episode_generation"] = 0
        raw = list(row["base_applied_action"])
        expected = [0.25 * value for value in raw[:3]] + [0.4 * max(-1.0, min(1.0, value)) for value in raw[3:]]
        responses.append(
            {
                "schema": "a2_piper_pull_v0_stage0_command_response_v2",
                "threshold_mode": "report_only",
                "episode_generation": 0,
                "trace_row_index": row_index,
                "control_step": row["step"],
                "response_control_step": row["step"] + 1,
                "base_command_scale": 0.25,
                "body_pitch_roll_scale": 0.4,
                "high_level_base_action_raw": raw,
                "base_action_raw_trace": raw,
                "expected_scaled_body_command": expected,
                "physical_base_command": expected,
                "physical_command_clipped": False,
                "downstream_lower_body_command": [0.0] * 12,
                "observed_world_xy_velocity": [0.0, 0.0],
                "observed_world_xy_displacement": [0.0, 0.0],
            }
        )
    response_summary = {
        "schema": "a2_piper_pull_v0_stage0_command_response_summary_v2",
        "status": "CAPTURED",
        "threshold_mode": "report_only",
        "response_count": len(responses),
        "responses": responses,
        "first_response": responses[0],
        "last_response": responses[-1],
        "anti_alignment_count": 0,
        "max_observed_world_xy_speed_mps": 0.0,
        "max_observed_world_xy_displacement_m": 0.0,
        "min_progress_velocity_cosine": None,
        "min_progress_displacement_cosine": None,
        "terminal_response": responses[-1],
    }
    summary["per_env_stage0_command_response"] = [response_summary]
    admission["stage0_command_response"] = response_summary
    return summary, metrics


def test_r7_plus_response_validator_accepts_120_identity_bound_rows():
    summary, metrics = _r7_valid_response_fixture()
    admission = repair_r7.validate_r7_plus_actual_telemetry(summary, metrics)
    assert admission["stage0_command_response"]["response_count"] == 120


@pytest.mark.parametrize("mutation", ("unavailable", "terminal_mismatch", "raw_mismatch", "missing_identity"))
def test_r7_plus_response_validator_rejects_noncausal_or_unavailable_rows(mutation):
    summary, metrics = _r7_valid_response_fixture()
    response_summary = summary["per_env_stage0_command_response"][0]
    if mutation == "unavailable":
        response_summary["status"] = "UNAVAILABLE"
    elif mutation == "terminal_mismatch":
        metrics["episode_terminal_diagnostics"][0]["push_anchor_admission"]["stage0_command_response"] = {
            **response_summary,
            "response_count": 0,
        }
    elif mutation == "raw_mismatch":
        response_summary["responses"][0]["high_level_base_action_raw"][0] += 1.0
    else:
        del response_summary["responses"][0]["episode_generation"]
    with pytest.raises(RuntimeError):
        repair_r7.validate_r7_plus_actual_telemetry(summary, metrics)


def test_attempt9_runner_requires_exact_r7_receipt_sha_and_ancestry():
    r7_path = anchor_runner.REPAIR_R7_RECEIPT_PATH
    r7_sha = _sha256(r7_path)
    assert r7_sha == anchor_runner.EXPECTED_R7_RECEIPT_SHA256
    receipt, validated_sha = anchor_runner._read_repair_receipt(
        r7_path, attempt=9, repair_receipt_sha256=r7_sha
    )
    assert receipt["repair_revision"] == "R7"
    assert validated_sha == r7_sha
    with pytest.raises(RuntimeError, match="Repair R7"):
        anchor_runner._read_repair_receipt(
            r7_path, attempt=9, repair_receipt_sha256="0" * 64
        )


def test_attempt9_normalized_response_preserves_runtime_identity_and_aggregates():
    normalized_path = repair_r8.ATTEMPT9_RESPONSE_TELEMETRY_PATH
    assert _sha256(normalized_path) == repair_r8.ATTEMPT9_RESPONSE_TELEMETRY_SHA256
    normalized = json.loads(normalized_path.read_text(encoding="utf-8"))
    assert normalized["status"] == "VALIDATED_ACTUAL_R7_PLUS_RESPONSE_TELEMETRY"
    assert normalized["runtime_validation"] == "VALIDATED_ACTUAL_R7_PLUS_RESPONSE_TELEMETRY"
    assert normalized["mechanism_verdict"] == "NOT_ASSESSED"
    assert normalized["response_summary"]["response_count"] == 120
    assert normalized["response_summary"]["anti_alignment_count"] == 33
    assert normalized["first_response_identity"] == {
        "episode_generation": 0,
        "trace_row_index": 3,
        "control_step": 3,
        "response_control_step": 4,
    }
    assert normalized["terminal_response_identity"] == {
        "episode_generation": 0,
        "trace_row_index": 122,
        "control_step": 122,
        "response_control_step": 123,
    }


def test_attempt9_invalidation_preserves_flawed_receipt_and_three_normalization_reasons():
    invalidation_path = repair_r8.ATTEMPT9_INVALIDATION_PATH
    assert _sha256(invalidation_path) == repair_r8.ATTEMPT9_INVALIDATION_SHA256
    invalidation = json.loads(invalidation_path.read_text(encoding="utf-8"))
    assert invalidation["status"] == "SUPERSEDED_INVALID"
    assert invalidation["receipt"]["sha256"] == repair_r8.ATTEMPT9_RECEIPT_SHA256
    assert {reason["code"] for reason in invalidation["reasons"]} == {
        "NULL_NORMALIZED_RESPONSE",
        "STATIC_ONLY_RUNTIME_WORDING_AFTER_VALIDATED_RUNTIME",
        "DROPPED_RUNTIME_IDENTITY_AND_AGGREGATE_EVIDENCE",
    }


def test_attempt10_runner_requires_exact_r8_receipt_sha_and_full_attempt9_ancestry():
    r8_path = anchor_runner.REPAIR_R8_RECEIPT_PATH
    r8_sha = _sha256(r8_path)
    assert r8_sha == anchor_runner.EXPECTED_R8_RECEIPT_SHA256
    receipt, validated_sha = anchor_runner._read_repair_receipt(
        r8_path, attempt=10, repair_receipt_sha256=r8_sha
    )
    assert receipt["repair_revision"] == "R8"
    assert validated_sha == r8_sha
    with pytest.raises(RuntimeError, match="Repair R8"):
        anchor_runner._read_repair_receipt(
            r8_path, attempt=10, repair_receipt_sha256="0" * 64
        )


def test_attempt10_receipt_is_exact_r8_bound_and_timeout_capacity_is_explicit():
    receipt_path = anchor_receipts.ATTEMPT10_RECEIPT_PATH
    assert _sha256(receipt_path) == anchor_receipts.EXPECTED_ATTEMPT10_RECEIPT_SHA256
    receipt = anchor_receipts.build_post_r1_attempt_receipt(
        10,
        plan_path=anchor_receipts.EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT10_PLAN.json",
        process_receipt_path=anchor_receipts.LOG_ROOT / "attempt10/process_receipt.json",
        log_path=anchor_receipts.LOG_ROOT / "attempt10/stdout_stderr.log",
        summary_path=anchor_receipts.LOG_ROOT / "attempt10/eval/a2_hold_oracle_summary.json",
        metrics_path=anchor_receipts.LOG_ROOT / "attempt10/eval/metrics_eval.json",
        repair_receipt_path=anchor_receipts.REPAIR_R8_RECEIPT_PATH,
    )
    assert receipt["schema_version"] == "pull_v0_p1_push_anchor_attempt_receipt_v10"
    assert receipt["admission_blocker"] == "STAGE0_TIMEOUT_BELOW_KINEMATIC_CAPACITY"
    assert receipt["repair_r8"]["artifact"]["sha256"] == anchor_runner.EXPECTED_R8_RECEIPT_SHA256
    assert receipt["budget_analysis"] == {
        "initial_stage0_horizontal_m": 0.9215447306632996,
        "terminal_stage0_horizontal_m": 0.5063455700874329,
        "residual_monotonic_nonincreasing": True,
        "residual_increase_count": 0,
        "physical_speed_mps": 0.15,
        "control_dt_s": 0.02,
        "distance_per_control_step_m": 0.003,
        "kinematic_lower_bound_steps": 308,
        "settle_steps": 5,
        "minimum_steps_including_settle": 313,
        "configured_timeout_steps": 120,
        "timeout_shortfall_vs_kinematic_lower_bound_steps": 188,
        "r9_timeout_steps": 360,
        "r9_nominal_horizon_s": 7.2,
        "r9_nominal_travel_m": 1.08,
        "budget_role": "P1_STAGE0_ADMISSION_WATCHDOG_ONLY",
        "mechanism_threshold": False,
    }
    assert receipt["quaternion_contract_closure"] == {
        "source": "canonical ArticulationData.root_quat_w WXYZ",
        "response_rows": 120,
        "anti_alignment_count": 0,
        "residual_monotonic_nonincreasing": True,
        "runtime_validation": "VALIDATED_ACTUAL_R7_PLUS_RESPONSE_TELEMETRY",
    }


def test_attempt10_receipt_rejects_wrong_r7_binding():
    with pytest.raises(RuntimeError, match="canonical Repair R8"):
        anchor_receipts.build_post_r1_attempt_receipt(
            10,
            plan_path=anchor_receipts.EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT10_PLAN.json",
            process_receipt_path=anchor_receipts.LOG_ROOT / "attempt10/process_receipt.json",
            log_path=anchor_receipts.LOG_ROOT / "attempt10/stdout_stderr.log",
            summary_path=anchor_receipts.LOG_ROOT / "attempt10/eval/a2_hold_oracle_summary.json",
            metrics_path=anchor_receipts.LOG_ROOT / "attempt10/eval/metrics_eval.json",
            repair_receipt_path=anchor_receipts.REPAIR_R7_RECEIPT_PATH,
        )


def test_attempt11_runner_requires_exact_r9_sha_and_full_attempt10_ancestry():
    r9_path = anchor_runner.REPAIR_R9_RECEIPT_PATH
    r9_sha = _sha256(r9_path)
    assert r9_sha == anchor_runner.EXPECTED_R9_RECEIPT_SHA256
    receipt, validated_sha = anchor_runner._read_repair_receipt(
        r9_path, attempt=11, repair_receipt_sha256=r9_sha
    )
    assert receipt["repair_revision"] == "R9"
    assert receipt["parent_receipt"]["sha256"] == anchor_runner.EXPECTED_R8_RECEIPT_SHA256
    assert receipt["trigger"]["attempt"] == 10
    assert validated_sha == r9_sha
    with pytest.raises(RuntimeError, match="Repair R9"):
        anchor_runner._read_repair_receipt(
            r9_path, attempt=11, repair_receipt_sha256="0" * 64
        )
    with pytest.raises(RuntimeError, match="canonical Repair R9"):
        anchor_runner._read_repair_receipt(
            anchor_runner.REPAIR_R8_RECEIPT_PATH,
            attempt=11,
            repair_receipt_sha256=anchor_runner.EXPECTED_R8_RECEIPT_SHA256,
        )
    runtime_artifacts = receipt["trigger"]["immutable_runtime_artifacts"]
    assert set(runtime_artifacts) == {"plan", "process_receipt", "log", "summary", "metrics"}
    assert runtime_artifacts["plan"]["sha256"] == anchor_runner.EXPECTED_ATTEMPT10_PLAN_SHA256
    assert runtime_artifacts["metrics"]["sha256"] == anchor_runner.EXPECTED_ATTEMPT10_METRICS_SHA256


def test_pull_anchor_timeout_360_is_confined_to_config_and_runner():
    config_path = CONFIG_ROOT / "ablation/wbmanip/pull_v0_p1_push_anchor.yaml"
    config_source = config_path.read_text(encoding="utf-8")
    assert "a2_pull_p1_stage0_timeout_steps: 360" in config_source
    assert "a2_pull_p1_stage0_timeout_steps: 120" not in config_source
    runner_source = anchor_runner.Path(anchor_runner.__file__).read_text(encoding="utf-8")
    assert runner_source.count("algo.config.eval.a2_pull_p1_stage0_timeout_steps=360") == 1
    assert "algo.config.eval.a2_pull_p1_stage0_timeout_steps=120" not in runner_source


def test_attempt9_receipt_builder_keeps_validated_runtime_wording_and_no_null_response():
    receipt = anchor_receipts.build_post_r1_attempt_receipt(
        9,
        plan_path=anchor_receipts.EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT9_PLAN.json",
        process_receipt_path=anchor_receipts.LOG_ROOT / "attempt9/process_receipt.json",
        log_path=anchor_receipts.LOG_ROOT / "attempt9/stdout_stderr.log",
        summary_path=anchor_receipts.LOG_ROOT / "attempt9/eval/a2_hold_oracle_summary.json",
        metrics_path=anchor_receipts.LOG_ROOT / "attempt9/eval/metrics_eval.json",
        repair_receipt_path=anchor_receipts.REPAIR_R7_RECEIPT_PATH,
    )
    assert receipt["runtime_validation"] == "VALIDATED_ACTUAL_R7_PLUS_RESPONSE_TELEMETRY"
    assert receipt["command_to_plant_response"]["response_count"] == 120
    assert receipt["command_to_plant_response"]["first_response_identity"]["trace_row_index"] == 3
    assert receipt["command_to_plant_response"]["terminal_response_identity"]["trace_row_index"] == 122
    assert "reason" not in receipt["command_to_plant_response"]
    assert all("static-only" not in claim.lower() for claim in receipt["unverified_claims"])


def test_attempt8_flawed_receipt_is_byte_identical_and_explicitly_invalidated():
    receipt_path = anchor_runner.ATTEMPT8_RECEIPT_PATH
    invalidation_path = anchor_runner.ATTEMPT8_INVALIDATION_PATH
    assert _sha256(receipt_path) == anchor_runner.EXPECTED_ATTEMPT8_RECEIPT_SHA256
    assert _sha256(invalidation_path) == anchor_runner.EXPECTED_ATTEMPT8_INVALIDATION_SHA256
    invalidation = json.loads(invalidation_path.read_text(encoding="utf-8"))
    assert invalidation["status"] == "SUPERSEDED_INVALID"
    assert invalidation["receipt"]["sha256"] == anchor_runner.EXPECTED_ATTEMPT8_RECEIPT_SHA256
    assert {reason["code"] for reason in invalidation["reasons"]} == {
        "STALE_TERMINAL_RESPONSE_ROW",
        "SUMMARY_TERMINAL_STATUS_MISMATCH",
        "EXECUTOR_ACTION_MISMATCH",
        "HARD_CODED_OTHER_ATTEMPT_WORDING",
    }


def test_attempt6_and_attempt7_use_one_actual_schema_route_and_attempt7_is_sealed():
    attempt6 = anchor_receipts.build_post_r1_attempt_receipt(
        6,
        plan_path=anchor_receipts.EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT6_PLAN.json",
        process_receipt_path=anchor_receipts.LOG_ROOT / "attempt6/process_receipt.json",
        log_path=anchor_receipts.LOG_ROOT / "attempt6/stdout_stderr.log",
        summary_path=anchor_receipts.LOG_ROOT / "attempt6/eval/a2_hold_oracle_summary.json",
        metrics_path=anchor_receipts.LOG_ROOT / "attempt6/eval/metrics_eval.json",
        repair_receipt_path=anchor_receipts.REPAIR_R4_RECEIPT_PATH,
    )
    attempt7 = anchor_receipts.build_post_r1_attempt_receipt(
        7,
        plan_path=anchor_receipts.EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT7_PLAN.json",
        process_receipt_path=anchor_receipts.LOG_ROOT / "attempt7/process_receipt.json",
        log_path=anchor_receipts.LOG_ROOT / "attempt7/stdout_stderr.log",
        summary_path=anchor_receipts.LOG_ROOT / "attempt7/eval/a2_hold_oracle_summary.json",
        metrics_path=anchor_receipts.LOG_ROOT / "attempt7/eval/metrics_eval.json",
        repair_receipt_path=anchor_receipts.REPAIR_R5_RECEIPT_PATH,
    )
    assert attempt6["schema_version"] == "pull_v0_p1_push_anchor_attempt_receipt_v6"
    assert attempt6["admission_blocker"] == "GENERIC_BASE_RELIEF_WATCHDOG_CROSS_TALK"
    assert attempt7["schema_version"] == "pull_v0_p1_push_anchor_attempt_receipt_v7"
    assert attempt7["admission_blocker"] == "STAGE0_COMMAND_TO_PLANT_RESPONSE_UNRESOLVED"
    assert attempt7["command_to_plant_response"]["status"] == "UNAVAILABLE"
    assert attempt7["command_to_plant_response"]["threshold_mode"] == "report_only"
    for attempt, metrics_path in (
        (6, anchor_receipts.LOG_ROOT / "attempt6/eval/metrics_eval.json"),
        (7, anchor_receipts.LOG_ROOT / "attempt7/eval/metrics_eval.json"),
    ):
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        admission = metrics["episode_terminal_diagnostics"][0]["push_anchor_admission"]
        assert not any(key.startswith("pull_v0_") for key in admission), attempt


def test_actual_schema_unknown_outcome_fails_fast(monkeypatch):
    monkeypatch.setattr(
        anchor_receipts,
        "_validate_actual_push_anchor_schema",
        lambda **_kwargs: {},
    )
    with pytest.raises(RuntimeError, match="Unknown actual push-anchor outcome"):
        anchor_receipts._build_actual_push_anchor_attempt_receipt(
            attempt=7,
            repair_receipt={"repair_revision": "R5", "stale_candidate_id": "x"},
            repair_artifact={},
            plan_artifact={},
            process_artifact={},
            log_artifact={},
            summary_artifact={},
            metrics_artifact={},
            process_receipt={},
            summary={"per_env_outcome": ["UNEXPECTED_OUTCOME"]},
            metrics={},
        )


def test_attempt8_requires_exact_r6_sha_and_r6_attempt7_r5_r4_ancestry(tmp_path, monkeypatch):
    r6 = anchor_runner.REPAIR_R6_RECEIPT_PATH
    r6_sha256 = _sha256(r6)
    with pytest.raises(RuntimeError, match="explicit --repair-receipt-sha256"):
        anchor_runner._read_repair_receipt(r6, attempt=8)
    with pytest.raises(RuntimeError):
        anchor_runner._read_repair_receipt(r6, attempt=8, repair_receipt_sha256="0" * 64)
    validated, validated_sha256 = anchor_runner._read_repair_receipt(
        r6,
        attempt=8,
        repair_receipt_sha256=r6_sha256,
    )
    assert validated["repair_revision"] == "R6"
    assert validated_sha256 == r6_sha256
    bad_path = tmp_path / "bad_r6.json"
    bad = json.loads(r6.read_text(encoding="utf-8"))
    bad["parent_receipt"]["sha256"] = "0" * 64
    bad_path.write_text(json.dumps(bad), encoding="utf-8")
    monkeypatch.setattr(anchor_runner, "REPAIR_R6_RECEIPT_PATH", bad_path)
    with pytest.raises(RuntimeError, match="R6 receipt identity"):
        anchor_runner._read_repair_receipt(
            bad_path,
            attempt=8,
            repair_receipt_sha256=_sha256(bad_path),
        )


def test_pull_outcome_ids_preserve_history_and_append_host_stage_overtime():
    tree = ast.parse(PUSH_ENV_SOURCE.read_text(encoding="utf-8"))
    assignment = next(
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "A2_HOLD_OUTCOME_NAMES"
            for target in node.targets
        )
    )
    names = ast.literal_eval(assignment.value)
    assert names[-1] == "PULL_P1_STAGE0_HOST_STAGE_OVERTIME"
    assert names[:-1] == (
        "PENDING",
        "NO_GATE",
        "CENTER_NO_BILATERAL",
        "UNILATERAL_WEDGE",
        "IK_TRACKING_FAILURE",
        "IK_INVALID",
        "JOINT_LIMIT",
        "BASE_RELIEF_WRONG_SIGN",
        "BASE_RELIEF_TIMEOUT",
        "BASE_RELIEF_DISPLACEMENT_LIMIT",
        "DEPRESS_WRONG_SIGN",
        "DEPRESS_TIMEOUT",
        "CONTACT_SLIP",
        "PUSH_WRONG_SIGN",
        "PUSH_PROGRESS",
        "PUSH_NO_PROGRESS",
        "PUSH_TIMEOUT",
        "RETAINED",
        "STATIC_CLAMP_COMPLETE",
        "STATIC_CLAMP_INCOMPLETE",
        "PLACEMENT_INCOMPLETE",
        "PLACEMENT_NOT_CONVERGED",
        "OFFSET_PLACEMENT_COMPLETE_EPISODE_ENDED",
        "STABILIZATION_CONTACT_CONTAMINATED",
        "STABILIZATION_GATE_LOST",
        "STABILIZATION_INCOMPLETE",
        "STABILIZATION_READY",
        "STABILIZATION_NOT_SETTLED",
        "MATCHED_CLEAN_NO_GATE",
        "MATCHED_CLEAN_RETREAT_IK_INVALID",
        "MATCHED_CLEAN_RETREAT_JOINT_LIMIT",
        "MATCHED_CLEAN_RETREAT_ACTION_INVALID",
        "MATCHED_CLEAN_RETREAT_TIMEOUT",
        "MATCHED_CLEAN_RETREAT_INCOMPLETE",
        "MATCHED_CLEAN_STABILIZE_CONTACT_CONTAMINATED",
        "MATCHED_CLEAN_STABILIZE_INCOMPLETE",
        "MATCHED_CLEAN_READY",
        "MATCHED_CLEAN_NOT_SETTLED",
        "ARC_PROBE_REACHED",
        "ARC_PROBE_TIMEOUT",
        "ARC_PROBE_ROOT_BOUND",
        "ARC_PROBE_ROOT_CROSSING",
        "ARC_PROBE_BODY_COLLISION",
        "ARC_PROBE_OVERSPEED",
        "PULL_P1_PROOF_CONTACT_LOSS",
        "PULL_P1_PROOF_TIMEOUT",
        "PULL_P1_BODY_COLLISION",
        "PULL_P1_LATCH_NOT_RELEASED",
        "PULL_P1_STAGE0_TIMEOUT",
        "PULL_P1_RESET_STATE_INVALID",
    )


def test_pull_summary_classifies_host_overtime_only_from_pending_acquire_and_device_local_timer():
    source = PUSH_ENV_SOURCE.read_text(encoding="utf-8")
    summary = source[source.index("def get_a2_hold_oracle_summary"):]
    assert "pending = self._a2_hold_oracle_outcome == A2_HOLD_OUTCOME_TO_ID[\"PENDING\"]" in summary
    assert "self._a2_hold_oracle_phase == A2_HOLD_PHASE_PULL_P1_ACQUIRE" in summary
    assert "self.actual_time_in_stage_buf" in summary
    assert "self.max_stage_time[self.stage_buf]" in summary
    assert '"PULL_P1_STAGE0_HOST_STAGE_OVERTIME"' in summary
    assert summary.index('"PULL_P1_STAGE0_HOST_STAGE_OVERTIME"') < summary.index('"ARC_PROBE_TIMEOUT"')


def test_attempt11_receipt_is_exact_r9_bound_host_overtime_probe_invalid():
    path = anchor_runner.ATTEMPT11_RECEIPT_PATH
    assert _sha256(path) == anchor_runner.EXPECTED_ATTEMPT11_RECEIPT_SHA256
    receipt = json.loads(path.read_text(encoding="utf-8"))
    assert receipt["schema_version"] == "pull_v0_p1_push_anchor_attempt_receipt_v11"
    assert receipt["status"] == "BLOCKED"
    assert receipt["probe_validity"] == "PROBE_INVALID"
    assert receipt["admission_blocker"] == anchor_runner.EXPECTED_R10_ROOT_CAUSE
    assert receipt["raw_summary_outcome"] if "raw_summary_outcome" in receipt else True
    assert receipt["observed"]["raw_summary_outcome"] == "ARC_PROBE_TIMEOUT"
    assert receipt["observed"]["classified_outcome"] == "PULL_P1_STAGE0_HOST_STAGE_OVERTIME"
    assert receipt["host_stage_timer"] == {
        "actual_device_local_stage_timer_steps": 250,
        "configured_host_stage_budget_steps": 250,
        "reset_qualification_steps": 3,
        "local_stage0_watchdog_steps": 360,
        "host_budget_less_than_reset_plus_local_watchdog": True,
        "terminal_reason": "stage_overtime",
        "classification_basis": (
            "terminal stage-0 host stage_overtime at the configured host-stage budget; "
            "local stage0 predicate remained untimed_out"
        ),
    }
    assert receipt["command_to_plant_response"]["response_count"] == 247
    assert receipt["command_to_plant_response"]["aggregates"]["anti_alignment_count"] == 0


def test_attempt12_runner_requires_exact_r10_sha_and_rejects_r9_or_wrong_hash(tmp_path):
    r10 = anchor_runner.REPAIR_R10_RECEIPT_PATH
    validated, validated_sha = anchor_runner._read_repair_receipt(
        r10, attempt=12, repair_receipt_sha256=anchor_runner.EXPECTED_R10_RECEIPT_SHA256
    )
    assert validated["repair_revision"] == "R10"
    assert validated["parent_receipt"]["sha256"] == anchor_runner.EXPECTED_R9_RECEIPT_SHA256
    assert validated["trigger"]["attempt"] == 11
    assert validated_sha == anchor_runner.EXPECTED_R10_RECEIPT_SHA256
    with pytest.raises(RuntimeError, match="Repair R10"):
        anchor_runner._read_repair_receipt(
            r10, attempt=12, repair_receipt_sha256="0" * 64
        )
    with pytest.raises(RuntimeError, match="canonical Repair R10"):
        anchor_runner._read_repair_receipt(
            anchor_runner.REPAIR_R9_RECEIPT_PATH,
            attempt=12,
            repair_receipt_sha256=anchor_runner.EXPECTED_R9_RECEIPT_SHA256,
        )


def test_pull_anchor_host_budget_is_anchor_only_and_relation_is_fail_fast():
    anchor_text = (
        CONFIG_ROOT / "ablation/wbmanip/pull_v0_p1_push_anchor.yaml"
    ).read_text(encoding="utf-8")
    shared_text = (CONFIG_ROOT / "env/door_open_a2_pull.yaml").read_text(encoding="utf-8")
    assert "max_stage_time: [400, 100, 100, 100, 100, 200]" in anchor_text
    assert "max_stage_time: [250, 100, 100, 100, 100, 200]" in shared_text
    assert "max_episode_length_s: 120" in anchor_text
    assert anchor_runner._validate_pull_anchor_stage_time_contract([400, 100, 100, 100, 100, 200]) == [
        400,
        100,
        100,
        100,
        100,
        200,
    ]
    with pytest.raises(RuntimeError, match="exceed reset qualification plus local watchdog"):
        anchor_runner._validate_pull_anchor_stage_time_contract([363, 100, 100, 100, 100, 200])
    argv = anchor_runner._argv(Path("/tmp/checkpoint.pt"), Path("/tmp/attempt12"))
    assert argv.count("+env.config.max_stage_time=[400,100,100,100,100,200]") == 1
    assert "env.config.max_stage_time=[400,100,100,100,100,200]" not in argv
    assert argv.count("algo.config.eval.a2_pull_p1_stage0_timeout_steps=360") == 1


def test_r10_receipt_builder_revalidates_exact_attempt11_evidence():
    receipt = repair_r10.build_r10_receipt()
    assert receipt["schema_version"] == repair_r10.R10_SCHEMA
    assert receipt["repair_revision"] == "R10"
    assert receipt["status"] == "APPROVED_FOR_ATTEMPT12_PREPARATION_ONLY"
    assert receipt["parent_receipt"]["sha256"] == repair_r10.R9_RECEIPT_SHA256
    assert receipt["trigger"]["attempt"] == 11
    assert receipt["attempt11_evidence"]["response_count"] == 247
    assert receipt["attempt11_evidence"]["anti_alignment_count"] == 0
    assert receipt["attempt11_evidence"]["residual_monotonic_nonincreasing"] is True
    assert receipt["host_stage_time_contract"]["pull_anchor_max_stage_time_steps"] == [
        400,
        100,
        100,
        100,
        100,
        200,
    ]
    assert receipt["scope"]["attempt12_prepared"] is False


def test_attempt12_preparation_invalidation_preserves_flawed_plan_inputs_and_no_runtime():
    plan_path = anchor_runner.EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT12_PLAN.json"
    assert _sha256(plan_path) == anchor_runner.EXPECTED_ATTEMPT12_PLAN_SHA256
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    assert plan["attempt"] == 12
    assert plan["repair_receipt"] == {
        "path": "scriptsFORhuman/pull_v0/PULL_V0_REPAIR_R9_RECEIPT.json",
        "sha256": anchor_runner.EXPECTED_R10_RECEIPT_SHA256,
        "expected_sha256": anchor_runner.EXPECTED_R10_RECEIPT_SHA256,
        "revision": "R10",
        "stale_candidate_id": anchor_runner.EXPECTED_STALE_CANDIDATE_ID,
        "parent_receipt_sha256": anchor_runner.EXPECTED_R9_RECEIPT_SHA256,
    }
    invalidation_path = anchor_runner.ATTEMPT12_INVALIDATION_PATH
    assert _sha256(invalidation_path) == anchor_runner.EXPECTED_ATTEMPT12_INVALIDATION_SHA256
    invalidation = json.loads(invalidation_path.read_text(encoding="utf-8"))
    assert invalidation["preparation_validity"] == "PREPARATION_INVALID"
    assert invalidation["probe_validity"] == "NOT_RUN"
    assert invalidation["runtime_validation"] == "NOT_RUN"
    assert invalidation["pull_mechanism_verdict"] == "NOT_ASSESSED"
    assert invalidation["plan"]["sha256"] == anchor_runner.EXPECTED_ATTEMPT12_PLAN_SHA256
    assert invalidation["plan"]["plan_sha256"] == anchor_runner.EXPECTED_ATTEMPT12_PLAN_IDENTITY_SHA256
    assert invalidation["preserved_inputs"]["config"]["sha256"] == (
        "c9e2bd493a2d20a89fc8f7414b18225f14aeb902d37b6c638a1a72fc77d1ee89"
    )
    assert invalidation["preserved_inputs"]["checkpoint"]["sha256"] == anchor_runner.EXPECTED_CHECKPOINT_SHA256
    for name, path_key in (
        ("process_receipt", "process_receipt_path"),
        ("log", "log_path"),
        ("summary", "summary_path"),
        ("metrics", "metrics_path"),
    ):
        assert invalidation["absence_of_runtime_artifacts"][name] is False
        assert not (ROOT / invalidation["absence_of_runtime_artifacts"][path_key]).exists()


def test_runner_plan_serialization_uses_exact_validated_r9_r10_r11_paths():
    r9 = json.loads(anchor_runner.REPAIR_R9_RECEIPT_PATH.read_text(encoding="utf-8"))
    r10 = json.loads(anchor_runner.REPAIR_R10_RECEIPT_PATH.read_text(encoding="utf-8"))
    r11 = {
        "repair_revision": "R11",
        "stale_candidate_id": anchor_runner.EXPECTED_STALE_CANDIDATE_ID,
        "parent_receipt": {"sha256": anchor_runner.EXPECTED_R10_RECEIPT_SHA256},
    }
    for path, receipt, sha, revision, parent_sha in (
        (
            anchor_runner.REPAIR_R9_RECEIPT_PATH,
            r9,
            anchor_runner.EXPECTED_R9_RECEIPT_SHA256,
            "R9",
            anchor_runner.EXPECTED_R8_RECEIPT_SHA256,
        ),
        (
            anchor_runner.REPAIR_R10_RECEIPT_PATH,
            r10,
            anchor_runner.EXPECTED_R10_RECEIPT_SHA256,
            "R10",
            anchor_runner.EXPECTED_R9_RECEIPT_SHA256,
        ),
        (
            anchor_runner.REPAIR_R11_RECEIPT_PATH,
            r11,
            anchor_runner.EXPECTED_R11_RECEIPT_SHA256,
            "R11",
            anchor_runner.EXPECTED_R10_RECEIPT_SHA256,
        ),
    ):
        entry = anchor_runner._repair_receipt_plan_entry(
            path.resolve(), repair_receipt=receipt, repair_receipt_sha256=sha
        )
        assert entry["path"] == str(path.relative_to(ROOT))
        assert entry["sha256"] == sha
        assert entry["expected_sha256"] == sha
        assert entry["revision"] == revision
        assert entry["stale_candidate_id"] == anchor_runner.EXPECTED_STALE_CANDIDATE_ID
        assert entry["parent_receipt_sha256"] == parent_sha


def test_attempt13_runner_and_builder_require_exact_r11_with_attempt12_invalidation():
    receipt, receipt_sha = anchor_runner._read_repair_receipt(
        anchor_runner.REPAIR_R11_RECEIPT_PATH,
        attempt=13,
        repair_receipt_sha256=anchor_runner.EXPECTED_R11_RECEIPT_SHA256,
    )
    assert receipt["repair_revision"] == "R11"
    assert receipt["parent_receipt"]["sha256"] == anchor_runner.EXPECTED_R10_RECEIPT_SHA256
    assert receipt["trigger"]["attempt"] == 12
    assert receipt["trigger"]["invalidation_manifest"]["sha256"] == (
        anchor_runner.EXPECTED_ATTEMPT12_INVALIDATION_SHA256
    )
    assert receipt_sha == anchor_runner.EXPECTED_R11_RECEIPT_SHA256
    validated, artifact = anchor_receipts._validate_repair_receipt(
        anchor_runner.REPAIR_R11_RECEIPT_PATH, attempt=13
    )
    assert validated["repair_revision"] == "R11"
    assert artifact["sha256"] == anchor_runner.EXPECTED_R11_RECEIPT_SHA256
    built = repair_r11.build_r11_receipt()
    assert built["schema_version"] == repair_r11.R11_SCHEMA
    assert built["repair_revision"] == "R11"
    assert built["status"] == "APPROVED_FOR_ATTEMPT13_PREPARATION_ONLY"
    assert built["scope"]["attempt12_preparation_invalid"] is True
    assert built["scope"]["attempt13_prepared"] is False
    assert built["scope"]["attempt13_runtime_executed"] is False
    with pytest.raises(RuntimeError, match="Repair R11"):
        anchor_runner._read_repair_receipt(
            anchor_runner.REPAIR_R11_RECEIPT_PATH,
            attempt=13,
            repair_receipt_sha256="0" * 64,
        )
    with pytest.raises(RuntimeError, match="canonical Repair R11"):
        anchor_runner._read_repair_receipt(
            anchor_runner.REPAIR_R10_RECEIPT_PATH,
            attempt=13,
            repair_receipt_sha256=anchor_runner.EXPECTED_R10_RECEIPT_SHA256,
        )


def test_attempt13_application_config_error_receipt_preserves_exact_missing_plus_failure():
    path = anchor_runner.ATTEMPT13_RECEIPT_PATH
    assert _sha256(path) == anchor_runner.EXPECTED_ATTEMPT13_RECEIPT_SHA256
    receipt = json.loads(path.read_text(encoding="utf-8"))
    assert receipt["schema_version"] == "pull_v0_p1_push_anchor_attempt_receipt_v13"
    assert receipt["attempt"] == 13
    assert receipt["status"] == "APPLICATION_CONFIG_ERROR_BEFORE_PROBE"
    assert receipt["probe_validity"] == "NOT_RUN"
    assert receipt["runtime_validation"] == "NOT_RUN"
    assert receipt["pull_mechanism_verdict"] == "NOT_ASSESSED"
    assert receipt["application_success"] is False
    assert receipt["natural_exit"] is False
    error = receipt["application_contract_error"]
    assert error["exception_type"] == anchor_runner.EXPECTED_ATTEMPT13_ERROR_TYPE
    assert error["root_cause"] == anchor_runner.EXPECTED_R12_ROOT_CAUSE
    assert error["attempted_override"] == anchor_runner.EXPECTED_ATTEMPT13_BAD_OVERRIDE
    assert error["missing_plus_override"] == anchor_runner.EXPECTED_ATTEMPT13_MISSING_PLUS_OVERRIDE
    assert receipt["artifacts"]["summary"] is None
    assert receipt["artifacts"]["metrics"] is None
    plan = json.loads(
        (anchor_runner.EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT13_PLAN.json").read_text(
            encoding="utf-8"
        )
    )
    assert anchor_runner.EXPECTED_ATTEMPT13_BAD_OVERRIDE in plan["argv"]
    assert anchor_runner.EXPECTED_ATTEMPT13_MISSING_PLUS_OVERRIDE not in plan["argv"]
    log_text = (
        anchor_runner._attempt_output_root(13) / "stdout_stderr.log"
    ).read_text(encoding="utf-8", errors="replace")
    assert f"hydra.errors.{anchor_runner.EXPECTED_ATTEMPT13_ERROR_TYPE}" in log_text
    assert f"To append to your config use {anchor_runner.EXPECTED_ATTEMPT13_MISSING_PLUS_OVERRIDE}" in log_text


def test_attempt14_runner_and_builder_require_exact_r12_with_attempt13_ancestry():
    receipt, receipt_sha = anchor_runner._read_repair_receipt(
        anchor_runner.REPAIR_R12_RECEIPT_PATH,
        attempt=14,
        repair_receipt_sha256=anchor_runner.EXPECTED_R12_RECEIPT_SHA256,
    )
    assert receipt["repair_revision"] == "R12"
    assert receipt["parent_receipt"]["sha256"] == anchor_runner.EXPECTED_R11_RECEIPT_SHA256
    assert receipt["trigger"]["attempt"] == 13
    assert receipt["trigger"]["attempt_receipt"]["sha256"] == (
        anchor_runner.EXPECTED_ATTEMPT13_RECEIPT_SHA256
    )
    assert receipt_sha == anchor_runner.EXPECTED_R12_RECEIPT_SHA256
    validated, artifact = anchor_receipts._validate_repair_receipt(
        anchor_runner.REPAIR_R12_RECEIPT_PATH, attempt=14
    )
    assert validated["repair_revision"] == "R12"
    assert artifact["sha256"] == anchor_runner.EXPECTED_R12_RECEIPT_SHA256
    built = repair_r12.build_r12_receipt()
    assert built["schema_version"] == repair_r12.R12_SCHEMA
    assert built["repair_revision"] == "R12"
    assert built["status"] == "APPROVED_FOR_ATTEMPT14_PREPARATION_ONLY"
    assert built["root_cause"]["exception_type"] == repair_r12.ATTEMPT13_ERROR_TYPE
    assert built["scope"]["attempt14_prepared"] is False
    assert built["scope"]["attempt14_runtime_executed"] is False
    with pytest.raises(RuntimeError, match="Repair R12"):
        anchor_runner._read_repair_receipt(
            anchor_runner.REPAIR_R12_RECEIPT_PATH,
            attempt=14,
            repair_receipt_sha256="0" * 64,
        )
    with pytest.raises(RuntimeError, match="canonical Repair R12"):
        anchor_runner._read_repair_receipt(
            anchor_runner.REPAIR_R11_RECEIPT_PATH,
            attempt=14,
            repair_receipt_sha256=anchor_runner.EXPECTED_R11_RECEIPT_SHA256,
        )


def test_attempt14_invalidation_is_canonical_and_attempt17_runtime_is_preserved():
    assert anchor_runner._attempt_output_root(13).is_dir()
    assert anchor_runner._attempt_output_root(14).is_dir()
    assert anchor_runner._attempt_output_root(15).is_dir()
    assert (anchor_runner.EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT14_PLAN.json").is_file()
    assert (anchor_runner.EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT15_PLAN.json").is_file()
    assert anchor_runner._attempt_output_root(16).is_dir()
    assert (anchor_runner.EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT16_PLAN.json").is_file()
    assert anchor_runner._attempt_output_root(17).is_dir()
    assert (anchor_runner.EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT17_PLAN.json").is_file()
    # Attempt18 has an immutable runtime failure receipt; no scientific verdict was consumed.
    assert anchor_runner._attempt_output_root(18).is_dir()
    assert (anchor_runner.EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT18_PLAN.json").is_file()
    attempt18_receipt = json.loads(anchor_runner.ATTEMPT18_RECEIPT_PATH.read_text(encoding="utf-8"))
    assert attempt18_receipt["status"] == "PROBE_INVALID"
    assert attempt18_receipt["scientific_verdict_consumed"] is False
    assert not (anchor_runner._attempt_output_root(18) / "process.json").exists()


def test_attempt14_resource_stop_receipt_is_exact_and_scientifically_invalidated():
    path = anchor_runner.ATTEMPT14_RECEIPT_PATH
    assert _sha256(path) == anchor_runner.EXPECTED_ATTEMPT14_RECEIPT_SHA256
    receipt = json.loads(path.read_text(encoding="utf-8"))
    assert receipt["schema_version"] == "pull_v0_p1_push_anchor_attempt_receipt_v14"
    assert receipt["attempt"] == 14
    assert receipt["status"] == "PROBE_INVALID"
    assert receipt["probe_validity"] == "PROBE_INVALID"
    assert receipt["runtime_validation"] == "INVALIDATED_BY_RESOURCE_STOP"
    assert receipt["pull_mechanism_verdict"] == "NOT_ASSESSED"
    assert receipt["scientific_verdict_consumed"] is False
    assert receipt["evidence"]["plan"] == {
        "path": "scriptsFORhuman/pull_v0/PULL_V0_P1_PUSH_ANCHOR_ATTEMPT14_PLAN.json",
        "sha256": anchor_runner.EXPECTED_ATTEMPT14_PLAN_SHA256,
        "plan_sha256": anchor_runner.EXPECTED_ATTEMPT14_PLAN_IDENTITY_SHA256,
    }
    assert receipt["evidence"]["stdout"]["sha256"] == anchor_runner.EXPECTED_ATTEMPT14_STDOUT_SHA256
    assert receipt["evidence"]["kit_log"]["sha256"] == anchor_runner.EXPECTED_ATTEMPT14_KIT_LOG_SHA256
    trace = receipt["evidence"]["interrupted_trace_tmp"]
    assert trace["bytes"] == anchor_runner.EXPECTED_ATTEMPT14_TRACE_TMP_BYTES
    assert trace["sha256"] is None
    assert receipt["resource_stop"] == {
        "triggered": True,
        "stop_condition": "Physical GPU lease violation: renderer opened compute contexts on unauthorized GPUs.",
        "main_action": "SIGINT_SENT_BY_MAIN",
        "child_pid": 1711000,
        "child_state": "DEFUNCT_AFTER_SIGINT",
        "selected_physical_gpu": 4,
        "authorized_physical_gpus": [4, 5, 6],
        "observed_gpu_indices": [0, 1, 2, 3, 4, 5, 6, 7],
        "unauthorized_gpu_indices": [0, 1, 2, 3, 7],
        "gpu7_compute_authorized": False,
        "contexts_remaining_after_stop": False,
    }
    assert receipt["canonical_outputs"]["process_receipt_present"] is False
    assert receipt["canonical_outputs"]["summary_verdict_consumed"] is False
    assert receipt["canonical_outputs"]["metrics_verdict_consumed"] is False


def test_attempt15_runner_requires_exact_r13_receipt_and_single_gpu_kit_args(tmp_path):
    r13_path = anchor_runner.REPAIR_R13_RECEIPT_PATH
    r13_sha = _sha256(r13_path)
    assert r13_sha == anchor_runner.EXPECTED_R13_RECEIPT_SHA256
    receipt, validated_sha = anchor_runner._read_repair_receipt(
        r13_path, attempt=15, repair_receipt_sha256=r13_sha
    )
    assert receipt["repair_revision"] == "R13"
    assert receipt["parent_receipt"]["sha256"] == anchor_runner.EXPECTED_R12_RECEIPT_SHA256
    assert receipt["trigger"]["attempt"] == 14
    assert validated_sha == r13_sha
    with pytest.raises(RuntimeError, match="Repair R13"):
        anchor_runner._read_repair_receipt(
            r13_path, attempt=15, repair_receipt_sha256="0" * 64
        )
    with pytest.raises(RuntimeError, match="canonical Repair R13"):
        anchor_runner._read_repair_receipt(
            anchor_runner.REPAIR_R12_RECEIPT_PATH,
            attempt=15,
            repair_receipt_sha256=anchor_runner.EXPECTED_R12_RECEIPT_SHA256,
        )
    argv = anchor_runner._argv(
        Path("/tmp/checkpoint.pt"), Path("/tmp/attempt15"), physical_gpu=4
    )
    assert argv.count("--kit_args") == 1
    kit_index = argv.index("--kit_args")
    assert argv[kit_index + 1] == anchor_runner.SINGLE_GPU_KIT_ARGS
    for setting in (
        "--/renderer/multiGpu/enabled=False",
        "--/renderer/multiGpu/autoEnable=False",
        "--/renderer/multiGpu/maxGpuCount=1",
    ):
        assert setting in argv[kit_index + 1].split()
    assert argv.count("+device=cuda:4") == 1
    assert argv.count("+env.config.max_stage_time=[400,100,100,100,100,200]") == 1
    assert "--/renderer/multiGpu/enabled=True" not in argv[kit_index + 1]
    assert "--/renderer/multiGpu/autoEnable=True" not in argv[kit_index + 1]
    assert "--/renderer/multiGpu/maxGpuCount=None" not in argv[kit_index + 1]
    assert anchor_runner._attempt_plan_path(15).is_file()
    assert not (tmp_path / "unused").exists()


def test_attempt15_builder_revalidates_r12_parent_attempt14_stop_and_contract():
    receipt = repair_r13.build_r13_receipt()
    assert receipt["schema_version"] == repair_r13.R13_SCHEMA
    assert receipt["repair_revision"] == repair_r13.R13_REVISION
    assert receipt["status"] == "APPROVED_FOR_ATTEMPT15_PREPARATION_ONLY"
    assert receipt["runtime_validation"] == "NOT_RUN"
    assert receipt["parent_receipt"]["sha256"] == repair_r13.R12_RECEIPT_SHA256
    assert receipt["trigger"]["attempt"] == 14
    assert receipt["trigger"]["attempt_receipt"]["sha256"] == repair_r13.ATTEMPT14_RECEIPT_SHA256
    assert receipt["scope"]["attempt15_prepared"] is False
    assert receipt["scope"]["attempt15_runtime_executed"] is False
    validated, artifact = anchor_receipts._validate_repair_receipt(
        anchor_receipts.REPAIR_R13_RECEIPT_PATH, attempt=15
    )
    assert validated["repair_revision"] == "R13"
    assert artifact["sha256"] == anchor_runner.EXPECTED_R13_RECEIPT_SHA256
    assert receipt["renderer_single_gpu_contract"] == {
        "kit_args": repair_r13.SINGLE_GPU_KIT_ARGS,
        "renderer_multi_gpu_enabled": False,
        "renderer_multi_gpu_auto_enable": False,
        "renderer_multi_gpu_max_gpu_count": 1,
        "active_gpu_index": 4,
        "physics_cuda_device": 4,
        "tensor_device": "cuda:4",
        "cuda_visible_devices": "UNSET",
        "physical_gpu_lease": [4, 5, 6],
        "gpu7_compute_authorized": False,
    }
    assert receipt["acceptance"]["product_mechanics_unchanged"] is True
    assert receipt["acceptance"]["thresholds_and_timeouts_unchanged"] is True
    assert receipt["changed_files"][
        "scriptsFORhuman/pull_v0/run_p1_push_anchor.py"
    ]["hash_binding"] == "EXCLUDED_TO_AVOID_R13_RECEIPT_SHA_SELF_CYCLE"


def test_pull_v0_renderer_transport_helper_absent_and_false_leave_defaults_unchanged():
    for config_value in (None, False):
        args_cli = SimpleNamespace(multi_gpu=True, kit_args="")
        eval_agent._configure_pull_v0_renderer_single_gpu(args_cli, config_value)
        assert args_cli == SimpleNamespace(multi_gpu=True, kit_args="")


def test_pull_v0_renderer_transport_helper_true_sets_exact_applauncher_contract():
    args_cli = SimpleNamespace(multi_gpu=True, kit_args="")
    eval_agent._configure_pull_v0_renderer_single_gpu(args_cli, True)
    assert args_cli.multi_gpu is False
    assert args_cli.kit_args == eval_agent._PULL_V0_RENDERER_SINGLE_GPU_KIT_ARGS
    assert args_cli.kit_args == anchor_runner.SINGLE_GPU_KIT_ARGS


@pytest.mark.parametrize("config_value", ("true", 1, 0, [], {}))
def test_pull_v0_renderer_transport_helper_rejects_non_bool(config_value):
    args_cli = SimpleNamespace(multi_gpu=True, kit_args="")
    with pytest.raises(TypeError, match="must be a boolean"):
        eval_agent._configure_pull_v0_renderer_single_gpu(args_cli, config_value)


@pytest.mark.parametrize("existing_kit_args", ("--other-kit-arg=true", ["--other-kit-arg=true"]))
def test_pull_v0_renderer_transport_helper_rejects_conflicting_preexisting_kit_args(existing_kit_args):
    args_cli = SimpleNamespace(multi_gpu=True, kit_args=existing_kit_args)
    with pytest.raises(ValueError, match="refuses to overwrite"):
        eval_agent._configure_pull_v0_renderer_single_gpu(args_cli, True)
    assert args_cli.multi_gpu is True
    assert args_cli.kit_args == existing_kit_args


def test_attempt16_argv_uses_only_pull_v0_hydra_boolean_and_preserves_device_budget():
    argv = anchor_runner._argv(
        Path("/tmp/checkpoint.pt"),
        Path("/tmp/attempt16"),
        use_hydra_renderer_transport=True,
        physical_gpu=4,
    )
    assert argv.count(anchor_runner.PULL_V0_RENDERER_SINGLE_GPU_OVERRIDE) == 1
    assert "--kit_args" not in argv
    assert not any(token.startswith("--/renderer/multiGpu/") for token in argv)
    assert argv.count("+device=cuda:4") == 1
    assert argv.count("+env.config.max_stage_time=[400,100,100,100,100,200]") == 1


def test_attempt15_receipt_is_exact_hydra_transport_failure_without_science_or_gpu_context():
    path = anchor_runner.ATTEMPT15_RECEIPT_PATH
    assert _sha256(path) == anchor_runner.EXPECTED_ATTEMPT15_RECEIPT_SHA256
    receipt = json.loads(path.read_text(encoding="utf-8"))
    assert receipt["schema_version"] == "pull_v0_p1_push_anchor_attempt_receipt_v15"
    assert receipt["attempt"] == 15
    assert receipt["status"] == "PROBE_INVALID"
    assert receipt["probe_validity"] == "PROBE_INVALID"
    assert receipt["runtime_validation"] == "INVALIDATED_BEFORE_APPLAUNCHER"
    assert receipt["pull_mechanism_verdict"] == "NOT_ASSESSED"
    assert receipt["scientific_verdict_consumed"] is False
    assert receipt["application_success"] is False
    assert receipt["returncode"] == 2
    assert receipt["application_contract_error"]["root_cause"] == anchor_runner.EXPECTED_R14_ROOT_CAUSE
    assert receipt["application_contract_error"]["unrecognized_arguments"] == [
        "--kit_args",
        anchor_runner.SINGLE_GPU_KIT_ARGS,
    ]
    assert receipt["evidence"]["plan"]["sha256"] == anchor_runner.EXPECTED_ATTEMPT15_PLAN_SHA256
    assert receipt["evidence"]["plan"]["plan_sha256"] == anchor_runner.EXPECTED_ATTEMPT15_PLAN_IDENTITY_SHA256
    assert receipt["evidence"]["process_receipt"]["sha256"] == anchor_runner.EXPECTED_ATTEMPT15_PROCESS_SHA256
    assert receipt["evidence"]["stdout"]["sha256"] == anchor_runner.EXPECTED_ATTEMPT15_STDOUT_SHA256
    assert receipt["evidence"]["summary"] is None
    assert receipt["evidence"]["metrics"] is None
    assert receipt["gpu_resource_observation"] == {
        "applauncher_started": False,
        "isaacsim_started": False,
        "gpu_process_opened": False,
        "gpu_context_opened": False,
        "cuda_visible_devices": "UNSET",
        "selected_physical_gpu": 4,
        "authorized_physical_gpus": [4, 5, 6],
        "gpu_memory_mib_by_index": {str(index): 1 for index in range(8)},
        "gpu7_compute_authorized": False,
    }


def test_attempt16_runner_and_builder_require_exact_r14_attempt15_r13_ancestry():
    r14_path = anchor_runner.REPAIR_R14_RECEIPT_PATH
    r14_sha = _sha256(r14_path)
    assert r14_sha == anchor_runner.EXPECTED_R14_RECEIPT_SHA256
    receipt, validated_sha = anchor_runner._read_repair_receipt(
        r14_path, attempt=16, repair_receipt_sha256=r14_sha
    )
    assert receipt["repair_revision"] == "R14"
    assert receipt["parent_receipt"]["sha256"] == anchor_runner.EXPECTED_R13_RECEIPT_SHA256
    assert receipt["trigger"]["attempt"] == 15
    assert validated_sha == r14_sha
    validated, artifact = anchor_receipts._validate_repair_receipt(r14_path, attempt=16)
    assert validated["repair_revision"] == "R14"
    assert artifact["sha256"] == r14_sha
    built = repair_r14.build_r14_receipt()
    assert built["schema_version"] == repair_r14.R14_SCHEMA
    assert built["repair_revision"] == repair_r14.R14_REVISION
    assert built["status"] == "APPROVED_FOR_ATTEMPT16_PREPARATION_ONLY"
    assert built["scope"]["attempt16_prepared"] is False
    assert built["scope"]["attempt16_runtime_executed"] is False
    assert built["renderer_single_gpu_transport"] == {
        "mode": "Hydra boolean -> args_cli.multi_gpu/kit_args",
        "hydra_config_key": "a2_pull_v0_renderer_single_gpu",
        "hydra_override": anchor_runner.PULL_V0_RENDERER_SINGLE_GPU_OVERRIDE,
        "args_cli_multi_gpu": False,
        "args_cli_kit_args": anchor_runner.SINGLE_GPU_KIT_ARGS,
        "raw_kit_args_in_argv": False,
        "absent_or_false_semantics": "Leave AppLauncher Namespace defaults unchanged.",
        "invalid_type_behavior": "Raise TypeError.",
        "conflicting_kit_args_behavior": "Raise ValueError without overwrite.",
    }
    with pytest.raises(RuntimeError, match="Repair R14"):
        anchor_runner._read_repair_receipt(r14_path, attempt=16, repair_receipt_sha256="0" * 64)
    with pytest.raises(RuntimeError, match="canonical Repair R14"):
        anchor_runner._read_repair_receipt(
            anchor_runner.REPAIR_R13_RECEIPT_PATH,
            attempt=16,
            repair_receipt_sha256=anchor_runner.EXPECTED_R13_RECEIPT_SHA256,
        )
    assert anchor_runner._attempt_plan_path(16).is_file()
    assert anchor_runner._attempt_output_root(16).is_dir()
    assert anchor_runner._attempt_plan_path(17).is_file()
    assert anchor_runner._attempt_output_root(17).is_dir()
    assert anchor_runner._attempt_plan_path(18).is_file()
    assert (anchor_runner._attempt_output_root(18) / "process_receipt.json").is_file()


def test_a4_a6_authority_footprint_and_infrastructure_reclassification_are_exact():
    assert _sha256(gpu_lease_amendment.AUTHORITY_PATH) == gpu_lease_amendment.AUTHORITY_SHA256
    footprint_path = gpu_lease_amendment.VULKAN_RECEIPT_PATH
    footprint = json.loads(footprint_path.read_text(encoding="utf-8"))
    assert _sha256(footprint_path) == gpu_lease_amendment.VULKAN_RECEIPT_SHA256
    assert footprint["status"] == "MEASURED_INFRASTRUCTURE_CONTEXT"
    assert footprint["scientific_verdict_consumed"] is False
    evidence = footprint["attempt16_evidence"]
    assert evidence["prelaunch_baseline_mib_by_physical_index"] == [1] * 8
    assert evidence["total_mib_by_physical_index"] == [168, 136, 136, 140, 236, 136, 136, 136]
    assert evidence["created_delta_mib_by_physical_index"] == [167, 135, 135, 139, 235, 135, 135, 135]
    assert evidence["utilization_percent_by_physical_index"] == [0] * 8
    assert evidence["historical_leased_device_by_physical_index"] == [False, False, False, False, True, False, False, False]
    assert evidence["kit_active_by_physical_index"] == [False, False, False, False, True, False, False, False]
    assert footprint["interpretation"]["max_non_leased_delta_mib"] == 167
    assert footprint["interpretation"]["non_leased_stop_threshold_mib"] == 1024
    assert footprint["interpretation"]["max_non_leased_delta_below_one_gib"] is True
    infra_path = gpu_lease_amendment.INFRA_RECEIPT_PATH
    infra = json.loads(infra_path.read_text(encoding="utf-8"))
    assert _sha256(infra_path) == gpu_lease_amendment.INFRA_RECEIPT_SHA256
    assert infra["status"] == "INFRASTRUCTURE_RECLASSIFICATION_COMPLETE"
    assert infra["scientific_verdict_consumed"] is False
    assert [entry["infra_id"] for entry in infra["mapping"]] == [
        "INFRA_001_HYDRA_KIT_ARGS_TRANSPORT",
        "INFRA_002_VULKAN_ENUMERATION_AUTHORIZATION",
    ]
    assert [entry["original_attempt"] for entry in infra["mapping"]] == [15, 16]
    assert all(entry["failure_boundary"] == "BEFORE_FIRST_SIMULATION_STEP" for entry in infra["mapping"])
    assert all(entry["scientific_verdict_consumed"] is False for entry in infra["mapping"])
    assert all(entry["anchor_attempt_consumed"] is False for entry in infra["mapping"])
    assert infra["retry_accounting"]["next_scientific_anchor_attempt"] == 17


def test_a4_a6_amendment_builder_preserves_r14_and_authorizes_only_attempt17_preparation():
    receipt = gpu_lease_amendment.build_amendment_receipt()
    assert receipt["schema_version"] == gpu_lease_amendment.AMENDMENT_SCHEMA
    assert receipt["amendment_revision"] == "A4_A6"
    assert receipt["repair_revision"] == "A4_A6"
    assert receipt["status"] == "APPROVED_FOR_ATTEMPT17_PREPARATION_ONLY"
    assert receipt["runtime_validation"] == "NOT_RUN"
    assert receipt["parent_receipt"] == {
        "path": "scriptsFORhuman/pull_v0/PULL_V0_REPAIR_R14_RECEIPT.json",
        "sha256": gpu_lease_amendment.R14_RECEIPT_SHA256,
        "repair_revision": "R14",
    }
    assert receipt["authority"]["sha256"] == gpu_lease_amendment.AUTHORITY_SHA256
    assert receipt["amendments"]["amendment4_compute_authorized_physical_devices"] == [2, 3]
    assert receipt["amendments"]["amendment4_selected_physical_device"] == 2
    assert receipt["amendments"]["amendment4_revoked_physical_devices"] == [4, 5, 6]
    assert receipt["amendments"]["amendment5_incidental_vulkan_enumeration_authorized_on_visible_devices"] is True
    assert receipt["amendments"]["amendment5_no_compute_on_non_leased_devices"] is True
    assert receipt["amendments"]["amendment5_container_isolation_authorized"] is False
    assert receipt["amendments"]["amendment5_container_isolation_required"] is False
    assert receipt["amendments"]["amendment6_next_scientific_attempt"] == 17
    assert receipt["scope"]["attempt15_and_16_receipts_preserved"] is True
    assert receipt["scope"]["attempt15_and_16_anchor_attempts_consumed"] is False
    assert receipt["scope"]["attempt17_prepared"] is False
    assert receipt["scope"]["attempt17_runtime_executed"] is False
    assert receipt["scope"]["product_mechanics_changed"] is False
    assert receipt["scope"]["fixture_changed"] is False
    assert receipt["scope"]["thresholds_or_timeouts_changed"] is False
    assert receipt["scope"]["p1_p2_gates_changed"] is False
    contract = receipt["attempt17_preparation_contract"]
    assert contract["authorized_compute_physical_devices"] == [2, 3]
    assert contract["selected_physical_device"] == 2
    assert contract["unauthorized_compute_physical_devices"] == [0, 1, 4, 5, 6, 7]
    assert contract["cuda_device"] == "cuda:2"
    assert contract["cuda_visible_devices"] == "UNSET"
    assert contract["renderer_multi_gpu_enabled"] is False
    assert contract["renderer_multi_gpu_auto_enable"] is False
    assert contract["renderer_multi_gpu_max_gpu_count"] == 1
    assert contract["hydra_override"] == anchor_runner.PULL_V0_RENDERER_SINGLE_GPU_OVERRIDE
    assert contract["incidental_vulkan_contexts_authorized_on_all_visible_devices"] is True
    assert contract["no_compute_on_non_leased_devices"] is True
    assert contract["container_isolation_authorized"] is False
    assert contract["container_isolation_required"] is False
    assert contract["per_run_launch_occupancy_receipt_required"] is True
    assert contract["steady_state_footprint_receipt_required"] is True
    assert contract["infrastructure_to_anchor_transition"] == "first_simulation_step"
    assert contract["anchor_verdict_required_after_transition"] is True


def test_attempt17_runner_and_builder_bind_a4_a6_gpu2_hydra_contract_without_runtime_artifacts():
    amendment_path = anchor_runner.GPU_LEASE_AMENDMENT_RECEIPT_PATH
    amendment_sha = _sha256(amendment_path)
    assert amendment_sha == anchor_runner.EXPECTED_GPU_LEASE_AMENDMENT_SHA256
    receipt, validated_sha = anchor_runner._read_repair_receipt(
        amendment_path, attempt=17, repair_receipt_sha256=amendment_sha
    )
    assert receipt["repair_revision"] == "A4_A6"
    assert receipt["parent_receipt"]["sha256"] == anchor_runner.EXPECTED_R14_RECEIPT_SHA256
    assert receipt["trigger"]["attempt16"]["receipt"]["sha256"] == anchor_runner.EXPECTED_ATTEMPT16_RECEIPT_SHA256
    assert validated_sha == amendment_sha
    validated, artifact = anchor_receipts._validate_repair_receipt(amendment_path, attempt=17)
    assert validated["amendment_revision"] == "A4_A6"
    assert artifact["sha256"] == amendment_sha
    argv = anchor_runner._argv(
        Path("/tmp/checkpoint.pt"),
        Path("/tmp/attempt17"),
        use_hydra_renderer_transport=True,
        physical_gpu=2,
    )
    assert argv.count(anchor_runner.PULL_V0_RENDERER_SINGLE_GPU_OVERRIDE) == 1
    assert "--kit_args" not in argv
    assert not any(token.startswith("--/renderer/multiGpu/") for token in argv)
    assert argv.count("+device=cuda:2") == 1
    assert "+device=cuda:4" not in argv
    assert argv.count("+env.config.max_stage_time=[400,100,100,100,100,200]") == 1
    assert anchor_runner.PHYSICAL_GPU == 2
    assert anchor_runner.AUTHORIZED_GPUS == (2, 3)
    assert anchor_runner._attempt_plan_path(17).is_file()
    assert anchor_runner._attempt_output_root(17).is_dir()
    assert anchor_runner._attempt_plan_path(18).is_file()
    assert (anchor_runner._attempt_output_root(18) / "process_receipt.json").is_file()


def test_attempt18_runner_and_stop_builder_bind_sealed_r15_without_current_artifacts():
    r15_path = anchor_runner.R15_RECEIPT_PATH
    r15_sha = _sha256(r15_path)
    assert r15_sha == anchor_runner.EXPECTED_R15_RECEIPT_SHA256
    with pytest.raises(RuntimeError, match="pre-existing scientific artifact"):
        anchor_runner._read_repair_receipt(
            r15_path,
            attempt=18,
            repair_receipt_sha256=r15_sha,
            allow_attempt18_runtime=True,
        )
    receipt = json.loads(r15_path.read_text(encoding="utf-8"))
    validated_sha = r15_sha
    assert validated_sha == r15_sha
    assert receipt["schema_version"] == anchor_runner.EXPECTED_R15_SCHEMA
    assert receipt["repair_revision"] == anchor_runner.EXPECTED_R15_REVISION
    assert receipt["status"] == "APPROVED_FOR_ATTEMPT18_PREPARATION_ONLY"
    assert receipt["runtime_validation"] == "NOT_RUN"
    assert receipt["trigger"]["attempt"] == 17
    assert receipt["trigger"]["root_cause"] == "CENTER_CLOSE_HANDOFF_OUTSIDE_RELIEF_BUDGET"
    assert receipt["scope"]["attempt18_prepared"] is False
    assert receipt["scope"]["attempt18_runtime_executed"] is False
    assert receipt["scope"]["attempt18_artifacts_created"] is False
    assert receipt["source_repair"]["reachability_helper"] == (
        "a2_pull_p1_center_handoff_reachable_mask"
    )
    validated, artifact = anchor_receipts._validate_repair_receipt(
        r15_path, attempt=18, allow_attempt18_runtime=True
    )
    assert validated["repair_revision"] == "R15"
    assert artifact["sha256"] == r15_sha
    built = repair_r15.build_r15_receipt()
    assert built["schema_version"] == repair_r15.R15_SCHEMA
    assert built["repair_revision"] == repair_r15.R15_REVISION
    assert built["status"] == "APPROVED_FOR_ATTEMPT18_PREPARATION_ONLY"
    assert built["root_cause"]["code"] == repair_r15.R15_ROOT_CAUSE
    assert built["acceptance"]["attempt18_not_prepared_or_run"] is True
    assert built["acceptance"]["runtime_pass_asserted"] is False
    argv = anchor_runner._argv(
        Path("/tmp/checkpoint.pt"),
        Path("/tmp/attempt18"),
        use_hydra_renderer_transport=True,
        physical_gpu=2,
    )
    assert argv.count(anchor_runner.PULL_V0_RENDERER_SINGLE_GPU_OVERRIDE) == 1
    assert "--kit_args" not in argv
    assert argv.count("+device=cuda:2") == 1
    assert argv.count("+env.config.max_stage_time=[400,100,100,100,100,200]") == 1
    assert anchor_runner._attempt_plan_path(18).is_file()
    assert (anchor_runner._attempt_output_root(18) / "process_receipt.json").is_file()


def test_attempt18_contact_capacity_failure_is_canonical_and_r16_binds_attempt19_preparation_only():
    attempt18 = json.loads(anchor_runner.ATTEMPT18_RECEIPT_PATH.read_text(encoding="utf-8"))
    assert _sha256(anchor_runner.ATTEMPT18_RECEIPT_PATH) == repair_r16.ATTEMPT18_RECEIPT_SHA256
    assert attempt18["status"] == "PROBE_INVALID"
    assert attempt18["runtime_failure"]["root_cause_code"] == "CONTACT_SENSOR_CAPACITY_OVERFLOW"
    assert attempt18["runtime_failure"]["configured_max_contact_data_count_per_prim"] == 8
    assert attempt18["runtime_failure"]["required_anchor_only_detailed_contact_capacity"] == 64
    assert attempt18["runtime_failure"]["first_simulation_step_boundary_crossed"] is True
    assert attempt18["scientific_verdict_consumed"] is False
    assert attempt18["pull_mechanism_verdict"] == "NOT_ASSESSED"
    assert attempt18["termination"]["sigterm"]["timestamp_hkt"] is None
    assert attempt18["termination"]["sigterm"]["timestamp_status"] == "NOT_RECORDED"
    assert attempt18["artifacts"]["summary"] is None
    assert attempt18["artifacts"]["metrics"] is None

    r16 = repair_r16.build_r16_receipt()
    assert r16["schema_version"] == "pull_v0_repair_r16_receipt_v1"
    assert r16["repair_revision"] == "R16"
    assert r16["revision_detail"] == "R16.4"
    assert r16["status"] == "APPROVED_FOR_ATTEMPT19_PREPARATION_ONLY"
    assert r16["runtime_validation"] == "NOT_RUN"
    assert r16["scientific_verdict_consumed"] is False
    assert r16["parent_receipt"]["sha256"] == _sha256(anchor_runner.ATTEMPT18_RECEIPT_PATH)
    assert _sha256(repair_r16.R16_RECEIPT_PATH) == repair_r16.R16_RECEIPT_SHA256
    assert r16["source_repair"]["anchor_only_detailed_contact_capacity"] == 64
    assert r16["source_repair"]["shared_default_detailed_contact_capacity"] == 8
    assert r16["source_repair"]["observed_total_collision_shape_count"] == 7
    assert r16["source_repair"]["candidate_sensor_filter_shape_pair_count"] == 10
    assert "minimum_contact_data_capacity" not in r16["source_repair"]
    assert r16["historical_attempt2_no_gate"]["result"] == "NO_GATE"
    assert r16["historical_attempt2_no_gate"]["proof_samples"] == 0
    assert r16["historical_attempt2_no_gate"]["physical_plant_cause"] == "INCONCLUSIVE_NO_PROOF_SAMPLES"
    r16_4 = r16["r16_4_evidence_derivation"]
    assert r16_4["runtime_scope"] == "PREPARATION_ONLY"
    assert r16_4["runtime_validation"] == "NOT_RUN"
    assert r16_4["scientific_verdict_consumed"] is False
    assert r16_4["installed_driver"] == "NVIDIA 580.173.02"
    assert r16_4["observed_rows"]["gpu3"]["sm"] == "-"
    assert r16_4["observed_rows"]["gpu4"]["type"] == "C+G"
    assert r16_4["observed_rows"]["gpu4"]["sm"] == 11
    assert r16_4["observed_rows"]["gpu4"]["mem"] == 5
    contract = r16["attempt19_preparation_contract"]
    assert contract["evidence_derivation_revision"] == "R16.4"
    assert contract["runtime_log_contract"]["validator_independent_derivation"] is True
    assert contract["pmon_contract"]["source_authoritative_for_attempt_pid"] is True
    assert contract["pmon_contract"]["accepted_types"] == ["C", "G", "C+G"]
    assert "null" in contract["pmon_contract"]["not_reported_metric_policy"]
    assert contract["process_identity_contract"]["module"] == "gr00t.rl.eval_agent_trl"
    assert contract["lifecycle_contract"]["launch_capture_strictly_before_process_started_at"] is True

    validated, artifact = anchor_receipts._validate_repair_receipt(
        repair_r16.R16_RECEIPT_PATH, attempt=19
    )
    assert validated["repair_revision"] == "R16"
    assert artifact["sha256"] == _sha256(repair_r16.R16_RECEIPT_PATH)
    bound, bound_sha = anchor_runner._read_repair_receipt(
        anchor_runner.R16_RECEIPT_PATH,
        attempt=19,
        repair_receipt_sha256=_sha256(anchor_runner.R16_RECEIPT_PATH),
    )
    assert bound["repair_revision"] == "R16"
    assert bound_sha == _sha256(anchor_runner.R16_RECEIPT_PATH)
    argv = anchor_runner._argv(
        Path("/tmp/checkpoint.pt"),
        Path("/tmp/attempt19"),
        use_hydra_renderer_transport=True,
        physical_gpu=2,
        detailed_contact_capacity=64,
    )
    assert argv.count("+env.config.a2_hold_diagnostic_max_contact_data_count_per_prim=64") == 1
    attempt19_plan = anchor_runner.EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT19_PLAN.json"
    assert attempt19_plan.is_file()
    assert _sha256(attempt19_plan) == (
        "cf23ee03ec0c40e77582ec724d8c6d8855cebcd40791edb7c8d11e75d9800748"
    )


def _write_attempt19_resource_fixture(tmp_path, monkeypatch):
    root = tmp_path / "attempt19_root"
    root.mkdir()
    plan = root / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT19_PLAN.json"
    launch = root / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT19_LAUNCH_OCCUPANCY.json"
    steady = root / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT19_STEADY_STATE_FOOTPRINT.json"
    log = root / "stdout_stderr.log"
    plan_json = {
        "schema_version": "pull_v0_p1_push_anchor_plan_v1",
        "attempt": 19,
        "status": "READY",
        "payload": "fixture",
    }
    plan_json["plan_sha256"] = attempt19_gpu_evidence._canonical_sha256(
        attempt19_gpu_evidence._plan_identity(plan_json)
    )
    plan.write_text(json.dumps(plan_json), encoding="utf-8")
    monkeypatch.setattr(attempt19_gpu_evidence, "ROOT", root)
    monkeypatch.setattr(attempt19_gpu_evidence, "EVIDENCE_ROOT", root)
    monkeypatch.setattr(attempt19_gpu_evidence, "ATTEMPT19_PLAN_PATH", plan)
    monkeypatch.setattr(attempt19_gpu_evidence, "ATTEMPT19_LAUNCH_OCCUPANCY_PATH", launch)
    monkeypatch.setattr(attempt19_gpu_evidence, "ATTEMPT19_STEADY_STATE_FOOTPRINT_PATH", steady)
    runner_pid = 100
    process_pid = 12345
    expected_eval_dir = root / attempt19_gpu_evidence.EXPECTED_ATTEMPT19_EVAL_OUTPUT_DIR
    proc_snapshots = {
        runner_pid: {
            "pid": runner_pid,
            "ppid": 1,
            "cmdline": ["runner"],
            "cwd": str(root),
        },
        process_pid: {
            "pid": process_pid,
            "ppid": runner_pid,
            "cmdline": [
                "/synthetic/python",
                "-B",
                "-m",
                "gr00t.rl.eval_agent_trl",
                f"eval_output_dir={expected_eval_dir}",
            ],
            "cwd": str(root),
        },
    }

    def proc_reader(pid):
        if pid not in proc_snapshots:
            raise RuntimeError(f"missing synthetic pid {pid}")
        return proc_snapshots[pid]

    def _kit_table():
        lines = [
            "| Driver Version: synthetic | Graphics API: Vulkan",
            "|=============================================================================================|",
            "| GPU | Name                             | Active | LDA | GPU Memory | Vendor-ID | LUID       |",
            "|     |                                  |        |     |            | Device-ID | UUID       |",
            "|     |                                  |        |     |            | Bus-ID    |            |",
            "|---------------------------------------------------------------------------------------------|",
        ]
        for index in range(8):
            active = "Yes: 0" if index == 2 else ""
            lines.extend(
                [
                    f"| {index:<3} | NVIDIA Synthetic                  | {active:<6} |     | 49386 MB | 10de      | UUID-{index} |",
                    "|     |                                  |        |     |            | 2230      |            |",
                    "|     |                                  |        |     |            | 1         |            |",
                    "|---------------------------------------------------------------------------------------------|",
                ]
            )
        return lines

    log.write_text(
        "\n".join(
            [
                "[INFO][AppLauncher]: Using device: cuda:2",
                *_kit_table(),
                "2026-08-04 12:00:01 | INFO | Environment device    : cuda:2",
                *_kit_table(),
                "Starting evaluation with one episode per environment",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    query_calls = []
    now = datetime.now(ZoneInfo("Asia/Hong_Kong")).replace(microsecond=0)
    launch_timestamp = (now - timedelta(seconds=2)).strftime("%Y-%m-%d %H:%M:%S HKT")
    steady_timestamp = now.strftime("%Y-%m-%d %H:%M:%S HKT")

    def query_runner(argv):
        query_calls.append(tuple(argv))
        is_gpu_query = any(token.startswith("--query-gpu") for token in argv)
        is_compute_query = any(token.startswith("--query-compute-apps") for token in argv)
        is_pmon_query = len(argv) > 1 and argv[1] == "pmon"
        if is_gpu_query:
            stdout = "\n".join(f"{index}, GPU-{index}, 2, 0" for index in range(8)) + "\n"
        elif is_pmon_query and len(query_calls) <= 3:
            stdout = "\n".join(
                [
                    "# gpu         pid   type     sm    mem    enc    dec    jpg    ofa     fb   ccpm    command",
                    "# Idx           #    C/G      %      %      %      %      %      %     MB     MB    name",
                    *[
                        f"    {index}          -     -      -      -      -      -      -      -      -      -    -"
                        for index in range(8)
                    ],
                ]
            ) + "\n"
        elif is_compute_query and len(query_calls) <= 2:
            stdout = ""
        elif is_pmon_query:
            rows = [
                "# gpu         pid   type     sm    mem    enc    dec    jpg    ofa     fb   ccpm    command",
                "# Idx           #    C/G      %      %      %      %      %      %     MB     MB    name",
            ]
            for index in range(8):
                if index == 2:
                    rows.append(f"    {index}      {process_pid}     C      1      0      -      -      -      -    3115      -    attempt19")
                else:
                    rows.append(f"    {index}      {process_pid}     G      0      0      -      -      -      -     136      -    kit")
            stdout = "\n".join(rows) + "\n"
        elif is_compute_query:
            stdout = f"GPU-2, {process_pid}, /synthetic/attempt19, 64\n"
        else:
            raise AssertionError(f"unexpected query {argv!r}")
        return SimpleNamespace(returncode=0, stdout=stdout, stderr="")

    launch_evidence = attempt19_gpu_evidence.capture_launch_evidence(
        plan,
        output_path=launch,
        query_runner=query_runner,
        captured_at_hkt=launch_timestamp,
    )
    steady_evidence = attempt19_gpu_evidence.capture_steady_state_evidence(
        plan,
        process_pid=process_pid,
        runner_pid=runner_pid,
        log_path=log,
        output_path=steady,
        query_runner=query_runner,
        proc_reader=proc_reader,
        captured_at_hkt=steady_timestamp,
    )
    monkeypatch.setattr(anchor_runner, "ROOT", root)
    monkeypatch.setattr(anchor_runner, "ATTEMPT19_LAUNCH_OCCUPANCY_PATH", launch)
    monkeypatch.setattr(anchor_runner, "_attempt_plan_path", lambda attempt: plan)
    monkeypatch.setattr(anchor_receipts, "ROOT", root)
    monkeypatch.setattr(anchor_receipts, "ATTEMPT19_LAUNCH_OCCUPANCY_PATH", launch)
    monkeypatch.setattr(anchor_receipts, "ATTEMPT19_STEADY_STATE_FOOTPRINT_PATH", steady)
    return {
        "root": root,
        "plan": plan,
        "launch": launch,
        "steady": steady,
        "log": log,
        "plan_json": json.loads(plan.read_text(encoding="utf-8")),
        "process_receipt": {
            "schema_version": "pull_v0_p1_push_anchor_process_v1",
            "attempt": 19,
            "started_at_hkt": (now - timedelta(seconds=1)).strftime("%Y-%m-%d %H:%M:%S HKT"),
            "finished_at_hkt": (now + timedelta(seconds=1)).strftime("%Y-%m-%d %H:%M:%S HKT"),
            "eval_pid": process_pid,
            "runner_pid": runner_pid,
            "eval_cmdline": list(proc_snapshots[process_pid]["cmdline"]),
            "eval_output_dir": str(expected_eval_dir.resolve()),
        },
        "proc_snapshots": proc_snapshots,
        "runner_pid": runner_pid,
        "process_pid": process_pid,
        "launch_json": launch_evidence,
        "steady_json": steady_evidence,
    }


def test_attempt19_gpu_capture_parses_mocked_nvidia_smi_and_validates_exact_receipts(
    tmp_path, monkeypatch
):
    fixture = _write_attempt19_resource_fixture(tmp_path, monkeypatch)
    assert fixture["launch_json"]["per_device"][2]["leased"] is True
    assert fixture["steady_json"]["process"]["pid"] == 12345
    closure = anchor_receipts._validate_attempt19_resource_evidence(
        plan=fixture["plan_json"],
        plan_artifact=anchor_receipts._artifact(fixture["plan"]),
        process_receipt=fixture["process_receipt"],
        log_path=fixture["log"],
        launch_occupancy_path=fixture["launch"],
        steady_state_footprint_path=fixture["steady"],
    )
    assert closure["selected_compute_physical_device"] == 2
    assert closure["first_simulation_step_boundary_crossed"] is True


@pytest.mark.parametrize(
    "mutation,match",
    (
        ("missing", "missing or not a regular"),
        ("wrong_gpu", "selected GPU must be GPU2"),
        ("stale", "capture is stale"),
    ),
)
def test_attempt19_runner_rejects_missing_wrong_or_stale_launch_occupancy(
    tmp_path, monkeypatch, mutation, match
):
    fixture = _write_attempt19_resource_fixture(tmp_path, monkeypatch)
    if mutation == "missing":
        fixture["launch"].unlink()
    elif mutation == "wrong_gpu":
        launch = json.loads(fixture["launch"].read_text(encoding="utf-8"))
        launch["selected_compute_physical_device"] = 3
        fixture["launch"].write_text(json.dumps(launch), encoding="utf-8")
    else:
        launch = json.loads(fixture["launch"].read_text(encoding="utf-8"))
        launch["captured_at_hkt"] = "2000-01-01 00:00:00 HKT"
        fixture["launch"].write_text(json.dumps(launch), encoding="utf-8")
    with pytest.raises(RuntimeError, match=match):
        anchor_runner._validate_attempt19_launch_occupancy(fixture["plan_json"])


def test_attempt19_capture_rejects_noncanonical_output_before_gpu_query(tmp_path, monkeypatch):
    fixture = _write_attempt19_resource_fixture(tmp_path, monkeypatch)
    wrong_output = fixture["root"] / "wrong_launch.json"
    with pytest.raises(RuntimeError, match="canonical path"):
        attempt19_gpu_evidence.capture_launch_evidence(
            fixture["plan"], output_path=wrong_output, query_runner=lambda _: pytest.fail("query must not run")
        )


def test_attempt19_closure_rejects_missing_or_wrong_steady_evidence(tmp_path, monkeypatch):
    fixture = _write_attempt19_resource_fixture(tmp_path, monkeypatch)
    fixture["steady"].unlink()
    with pytest.raises(RuntimeError, match="steady-state footprint is missing"):
        anchor_receipts._validate_attempt19_resource_evidence(
            plan=fixture["plan_json"],
            plan_artifact=anchor_receipts._artifact(fixture["plan"]),
            process_receipt=fixture["process_receipt"],
            log_path=fixture["log"],
            launch_occupancy_path=fixture["launch"],
            steady_state_footprint_path=fixture["steady"],
        )


def _validate_attempt19_fixture_steady(fixture, evidence=None, **kwargs):
    return attempt19_gpu_evidence.validate_steady_evidence(
        fixture["steady_json"] if evidence is None else evidence,
        plan=fixture["plan_json"],
        plan_artifact={
            **anchor_receipts._artifact(fixture["plan"]),
            "plan_sha256": fixture["plan_json"]["plan_sha256"],
        },
        log_text=fixture["log"].read_text(encoding="utf-8"),
        required_pid=fixture["process_pid"],
        **kwargs,
    )


def _validate_attempt19_fixture_launch(fixture, evidence=None, **kwargs):
    return attempt19_gpu_evidence.validate_launch_evidence(
        fixture["launch_json"] if evidence is None else evidence,
        plan=fixture["plan_json"],
        plan_artifact={
            **anchor_receipts._artifact(fixture["plan"]),
            "plan_sha256": fixture["plan_json"]["plan_sha256"],
        },
        **kwargs,
    )


def _attempt19_pmon_text(process_rows=None):
    process_rows = {} if process_rows is None else dict(process_rows)
    lines = [
        "# gpu         pid   type     sm    mem    enc    dec    jpg    ofa     fb   ccpm    command",
        "# Idx           #    C/G      %      %      %      %      %      %     MB     MB    name",
    ]
    for index in range(8):
        lines.append(process_rows.get(index, f"{index} - - - - - - - - - - -"))
    return "\n".join(lines) + "\n"


def test_attempt19_runtime_log_contract_is_exact_and_persists_source_tables(tmp_path, monkeypatch):
    fixture = _write_attempt19_resource_fixture(tmp_path, monkeypatch)
    contract = attempt19_gpu_evidence.parse_runtime_log_contract(
        fixture["log"].read_text(encoding="utf-8")
    )
    assert contract["app_launcher"] == {
        "line_number": 1,
        "source_line": "[INFO][AppLauncher]: Using device: cuda:2",
        "device": "cuda:2",
    }
    assert contract["environment"]["device"] == "cuda:2"
    assert contract["first_simulation_step_boundary"]["exact_text"] == (
        "Starting evaluation with one episode per environment"
    )
    tables = contract["kit_vulkan_tables_after_app_launcher"]
    assert len(tables) == 2
    assert [table["active_physical_devices"] for table in tables] == [[2], [2]]
    assert all(len(table["rows"]) == 8 for table in tables)
    assert all(table["rows"][2]["source_line"].strip().startswith("| 2") for table in tables)

    bad_app = fixture["log"].read_text(encoding="utf-8").replace(
        "[INFO][AppLauncher]: Using device: cuda:2",
        "[DEBUG][AppLauncher]: Using device: cuda:2",
        1,
    )
    with pytest.raises(RuntimeError, match="AppLauncher"):
        attempt19_gpu_evidence.parse_runtime_log_contract(bad_app)
    bad_environment = fixture["log"].read_text(encoding="utf-8").replace(
        "Environment device    : cuda:2", "Environment device: cuda:2", 1
    )
    with pytest.raises(RuntimeError, match="Environment device"):
        attempt19_gpu_evidence.parse_runtime_log_contract(bad_environment)
    bad_boundary = fixture["log"].read_text(encoding="utf-8").replace(
        "Starting evaluation with one episode per environment",
        "Starting evaluation with one episode",
        1,
    )
    with pytest.raises(RuntimeError, match="first simulation boundary"):
        attempt19_gpu_evidence.parse_runtime_log_contract(bad_boundary)


def test_attempt19_plan_identity_is_recomputed_before_any_query_or_write(tmp_path, monkeypatch):
    fixture = _write_attempt19_resource_fixture(tmp_path, monkeypatch)
    plan = json.loads(fixture["plan"].read_text(encoding="utf-8"))
    plan["plan_sha256"] = "0" * 64
    fixture["plan"].write_text(json.dumps(plan), encoding="utf-8")
    with pytest.raises(RuntimeError, match="plan_sha256"):
        attempt19_gpu_evidence._load_plan(fixture["plan"])


def test_attempt19_pmon_parser_requires_all_devices_and_known_context_fields():
    parsed = attempt19_gpu_evidence.parse_pmon_output(
        _attempt19_pmon_text(
            {2: "2 12345 C 1 2 - - - - 3115 - gr00t.rl.eval_agent_trl"}
        )
    )
    assert set(parsed) == set(range(8))
    assert parsed[2][0]["pid"] == 12345
    assert parsed[2][0]["type"] == "C"
    assert parsed[2][0]["fb_memory_mib"] == 3115.0
    with pytest.raises(RuntimeError, match="cover physical GPU indices"):
        attempt19_gpu_evidence.parse_pmon_output(
            "\n".join(_attempt19_pmon_text().splitlines()[:-1]) + "\n"
        )
    with pytest.raises(RuntimeError, match="unknown PID/type"):
        attempt19_gpu_evidence.parse_pmon_output(
            _attempt19_pmon_text({2: "2 12345 X 1 0 - - - - 3115 - bad"})
        )
    with pytest.raises(RuntimeError, match="GPU2 PID12345 SM"):
        attempt19_gpu_evidence.parse_pmon_output(
            _attempt19_pmon_text({2: "2 12345 C ? 0 - - - - 3115 - bad"})
        )
    assert attempt19_gpu_evidence.PMON_QUERY == (
        "nvidia-smi",
        "pmon",
        "-i",
        "0,1,2,3,4,5,6,7",
        "-c",
        "1",
        "-s",
        "um",
    )


def test_attempt19_pmon_parser_preserves_installed_driver_not_reported_metrics_and_combined_contexts():
    parsed = attempt19_gpu_evidence.parse_pmon_output(
        _attempt19_pmon_text(
            {
                3: "3 2198197 G - - - - - - 4 0 python",
                4: "4 2198197 C+G 11 5 - - - - 5050 0 python",
            }
        )
    )
    gpu3 = parsed[3][0]
    gpu4 = parsed[4][0]
    assert gpu3["type"] == "G"
    assert gpu3["sm_util_percent"] is None
    assert gpu3["memory_util_percent"] is None
    assert gpu3["sm_util_percent_state"] == "NOT_REPORTED"
    assert gpu3["memory_util_percent_state"] == "NOT_REPORTED"
    assert gpu3["fb_memory_mib"] == 4.0
    assert gpu3["source"] == attempt19_gpu_evidence.PMON_SOURCE
    assert gpu4["type"] == "C+G"
    assert gpu4["sm_util_percent"] == 11.0
    assert gpu4["memory_util_percent"] == 5.0
    assert gpu4["sm_util_percent_state"] == "REPORTED"
    assert gpu4["memory_util_percent_state"] == "REPORTED"
    assert gpu4["fb_memory_mib"] == 5050.0


def test_attempt19_steady_accepts_selected_combined_compute_and_not_reported_graphics_metrics(
    tmp_path, monkeypatch
):
    fixture = _write_attempt19_resource_fixture(tmp_path, monkeypatch)
    evidence = copy.deepcopy(fixture["steady_json"])
    selected = next(device for device in evidence["per_device"] if device["index"] == 2)
    selected_context = next(
        item for item in selected["pmon_processes"] if item["pid"] == fixture["process_pid"]
    )
    selected_context["type"] = "C+G"
    selected_context["sm_util_percent"] = None
    selected_context["sm_util_percent_state"] = "NOT_REPORTED"
    selected_context["memory_util_percent"] = None
    selected_context["memory_util_percent_state"] = "NOT_REPORTED"
    for index in (0, 1, 3, 4, 5, 6, 7):
        device = next(item for item in evidence["per_device"] if item["index"] == index)
        context = next(item for item in device["pmon_processes"] if item["pid"] == fixture["process_pid"])
        context["sm_util_percent"] = None
        context["sm_util_percent_state"] = "NOT_REPORTED"
        context["memory_util_percent"] = None
        context["memory_util_percent_state"] = "NOT_REPORTED"
    result = _validate_attempt19_fixture_steady(fixture, evidence)
    assert result["selected_compute_physical_device"] == 2
    assert result["attempt_process_memory_by_device"][0] == 136.0


@pytest.mark.parametrize("mutation", ("combined_compute", "nonzero", "unknown", "threshold"))
def test_attempt19_steady_rejects_nonselected_same_pid_combined_compute_or_active_contexts(
    tmp_path, monkeypatch, mutation
):
    fixture = _write_attempt19_resource_fixture(tmp_path, monkeypatch)
    evidence = copy.deepcopy(fixture["steady_json"])
    gpu0 = next(device for device in evidence["per_device"] if device["index"] == 0)
    context = next(item for item in gpu0["pmon_processes"] if item["pid"] == fixture["process_pid"])
    if mutation == "combined_compute":
        context["type"] = "C+G"
    elif mutation == "nonzero":
        context["sm_util_percent"] = 1.0
        context["sm_util_percent_state"] = "REPORTED"
    elif mutation == "unknown":
        context["memory_util_percent"] = None
        context["memory_util_percent_state"] = "UNKNOWN"
    else:
        context["fb_memory_mib"] = 1025.0
    with pytest.raises(RuntimeError):
        _validate_attempt19_fixture_steady(fixture, evidence)


def _attempt19_other_tenant_pmon(*, gpu_index: int, pid: int, pmon_type: str = "G"):
    return {
        "gpu_index": gpu_index,
        "pid": pid,
        "type": pmon_type,
        "sm_util_percent": None,
        "sm_util_percent_state": "NOT_REPORTED",
        "memory_util_percent": None,
        "memory_util_percent_state": "NOT_REPORTED",
        "fb_memory_mib": 4.0,
        "fb_memory_mib_state": "REPORTED",
        "command": "python",
        "source": attempt19_gpu_evidence.PMON_SOURCE,
    }


def test_attempt19_steady_accepts_gpu3_inactive_other_tenant_graphics_context(
    tmp_path, monkeypatch
):
    fixture = _write_attempt19_resource_fixture(tmp_path, monkeypatch)
    evidence = copy.deepcopy(fixture["steady_json"])
    gpu3 = next(device for device in evidence["per_device"] if device["index"] == 3)
    tenant_pmon = _attempt19_other_tenant_pmon(gpu_index=3, pid=2198197)
    gpu3["pmon_processes"].append(tenant_pmon)
    gpu3["other_tenant_context_classification"] = "OTHER_TENANT_INACTIVE_VULKAN_ENUMERATION"
    evidence["authorized_alternate_tenant_occupancy_at_steady_state"] = [
        {
            "device_index": 3,
            "attribution": "OTHER_TENANT",
            "utilization_gpu_percent": gpu3["utilization_gpu_percent"],
            "processes": [],
            "pmon_processes": [tenant_pmon],
        }
    ]
    result = _validate_attempt19_fixture_steady(fixture, evidence)
    assert result["tenant_devices_at_steady_state"] == []


def test_attempt19_steady_rejects_gpu3_other_tenant_compute_context(
    tmp_path, monkeypatch
):
    fixture = _write_attempt19_resource_fixture(tmp_path, monkeypatch)
    evidence = copy.deepcopy(fixture["steady_json"])
    gpu3 = next(device for device in evidence["per_device"] if device["index"] == 3)
    tenant_pid = 2198197
    tenant_pmon = _attempt19_other_tenant_pmon(gpu_index=3, pid=tenant_pid, pmon_type="C+G")
    gpu3["pmon_processes"].append(tenant_pmon)
    gpu3["compute_processes"].append(
        {"pid": tenant_pid, "name": "tenant", "memory_used_mib": 5050.0}
    )
    evidence["authorized_alternate_tenant_occupancy_at_steady_state"] = [
        {
            "device_index": 3,
            "attribution": "OTHER_TENANT",
            "utilization_gpu_percent": gpu3["utilization_gpu_percent"],
            "processes": gpu3["compute_processes"],
            "pmon_processes": [tenant_pmon],
        }
    ]
    with pytest.raises(RuntimeError):
        _validate_attempt19_fixture_steady(fixture, evidence)


def test_attempt19_cross_source_compute_presence_is_required_on_selected_and_absent_on_nonselected(
    tmp_path, monkeypatch
):
    fixture = _write_attempt19_resource_fixture(tmp_path, monkeypatch)
    selected_missing = copy.deepcopy(fixture["steady_json"])
    selected = next(device for device in selected_missing["per_device"] if device["index"] == 2)
    selected["compute_processes"] = []
    with pytest.raises(RuntimeError, match="compute-apps"):
        _validate_attempt19_fixture_steady(fixture, selected_missing)
    nonselected_present = copy.deepcopy(fixture["steady_json"])
    gpu0 = next(device for device in nonselected_present["per_device"] if device["index"] == 0)
    gpu0["compute_processes"].append(
        {"pid": fixture["process_pid"], "name": "attempt19", "memory_used_mib": 136.0}
    )
    with pytest.raises(RuntimeError, match="compute-apps"):
        _validate_attempt19_fixture_steady(fixture, nonselected_present)


def test_attempt19_launch_accepts_gpu3_inactive_other_tenant_graphics_context(
    tmp_path, monkeypatch
):
    fixture = _write_attempt19_resource_fixture(tmp_path, monkeypatch)
    evidence = copy.deepcopy(fixture["launch_json"])
    gpu3 = next(device for device in evidence["per_device"] if device["index"] == 3)
    tenant_pmon = _attempt19_other_tenant_pmon(gpu_index=3, pid=2198197)
    gpu3["pmon_processes"] = [tenant_pmon]
    gpu3["context_classification"] = "OTHER_TENANT_INACTIVE_VULKAN_ENUMERATION"
    evidence["authorized_alternate_tenant_occupancy_at_launch"] = [
        {
            "device_index": 3,
            "attribution": "OTHER_TENANT",
            "utilization_gpu_percent": 0.0,
            "processes": [],
            "pmon_processes": [tenant_pmon],
        }
    ]
    result = _validate_attempt19_fixture_launch(fixture, evidence)
    assert result["tenant_devices_at_launch"] == []


def test_attempt19_launch_rejects_gpu3_compute_or_combined_context(
    tmp_path, monkeypatch
):
    fixture = _write_attempt19_resource_fixture(tmp_path, monkeypatch)
    evidence = copy.deepcopy(fixture["launch_json"])
    gpu3 = next(device for device in evidence["per_device"] if device["index"] == 3)
    tenant_pid = 2198197
    tenant_pmon = _attempt19_other_tenant_pmon(gpu_index=3, pid=tenant_pid, pmon_type="C+G")
    gpu3["pmon_processes"] = [tenant_pmon]
    gpu3["compute_processes"] = [
        {"pid": tenant_pid, "name": "tenant", "memory_used_mib": 5050.0}
    ]
    gpu3["context_classification"] = "OTHER_TENANT"
    evidence["authorized_alternate_tenant_occupancy_at_launch"] = [
        {
            "device_index": 3,
            "attribution": "OTHER_TENANT",
            "utilization_gpu_percent": 0.0,
            "processes": gpu3["compute_processes"],
            "pmon_processes": [tenant_pmon],
        }
    ]
    with pytest.raises(RuntimeError):
        _validate_attempt19_fixture_launch(fixture, evidence)


@pytest.mark.parametrize("mutation", ("missing", "module", "output", "ancestry"))
def test_attempt19_process_identity_rejects_dead_wrong_or_unverified_eval_process(
    tmp_path, monkeypatch, mutation
):
    fixture = _write_attempt19_resource_fixture(tmp_path, monkeypatch)
    snapshots = copy.deepcopy(fixture["proc_snapshots"])
    if mutation == "missing":
        snapshots.pop(fixture["process_pid"])
    elif mutation == "module":
        snapshots[fixture["process_pid"]]["cmdline"][3] = "gr00t.rl.other_eval"
    elif mutation == "output":
        snapshots[fixture["process_pid"]]["cmdline"][-1] = "eval_output_dir=/tmp/other"
    else:
        snapshots[fixture["process_pid"]]["ppid"] = 999

    def reader(pid):
        if pid not in snapshots:
            raise RuntimeError(f"synthetic PID{pid} is not live")
        return snapshots[pid]

    with pytest.raises(RuntimeError):
        attempt19_gpu_evidence.derive_process_identity(
            runner_pid=fixture["runner_pid"],
            process_pid=fixture["process_pid"],
            proc_reader=reader,
        )


def test_attempt19_process_identity_accepts_verified_descendant_and_rejects_static_chain_shape(
    tmp_path, monkeypatch
):
    fixture = _write_attempt19_resource_fixture(tmp_path, monkeypatch)
    snapshots = copy.deepcopy(fixture["proc_snapshots"])
    shim_pid = 456
    snapshots[shim_pid] = {
        "pid": shim_pid,
        "ppid": fixture["runner_pid"],
        "cmdline": ["shim"],
        "cwd": str(fixture["root"]),
    }
    snapshots[fixture["process_pid"]]["ppid"] = shim_pid
    identity = attempt19_gpu_evidence.derive_process_identity(
        runner_pid=fixture["runner_pid"],
        process_pid=fixture["process_pid"],
        proc_reader=lambda pid: snapshots[pid],
    )
    assert [item["pid"] for item in identity["ancestry_chain"]] == [
        fixture["process_pid"],
        shim_pid,
        fixture["runner_pid"],
    ]
    malformed = copy.deepcopy(identity)
    malformed["ancestry_chain"][1] = None
    with pytest.raises(RuntimeError, match="malformed snapshot"):
        attempt19_gpu_evidence._validate_process_identity_evidence(
            malformed, process_pid=fixture["process_pid"]
        )


@pytest.mark.parametrize("mutation", ("compute", "nonzero", "unknown", "threshold"))
def test_attempt19_steady_rejects_nonselected_same_pid_compute_or_active_contexts(
    tmp_path, monkeypatch, mutation
):
    fixture = _write_attempt19_resource_fixture(tmp_path, monkeypatch)
    evidence = copy.deepcopy(fixture["steady_json"])
    gpu0 = next(device for device in evidence["per_device"] if device["index"] == 0)
    context = next(item for item in gpu0["pmon_processes"] if item["pid"] == fixture["process_pid"])
    if mutation == "compute":
        context["type"] = "C"
    elif mutation == "nonzero":
        context["sm_util_percent"] = 1.0
    elif mutation == "unknown":
        context["memory_util_percent"] = None
    else:
        context["fb_memory_mib"] = 1025.0
    with pytest.raises(RuntimeError):
        _validate_attempt19_fixture_steady(fixture, evidence)


def test_attempt19_steady_rejects_other_pid_on_authorized_alternate_gpu(tmp_path, monkeypatch):
    fixture = _write_attempt19_resource_fixture(tmp_path, monkeypatch)
    evidence = copy.deepcopy(fixture["steady_json"])
    gpu3 = next(device for device in evidence["per_device"] if device["index"] == 3)
    gpu3["pmon_processes"].append(
        {
            "gpu_index": 3,
            "pid": 999,
            "type": "G",
            "sm_util_percent": 0.0,
            "memory_util_percent": 0.0,
            "fb_memory_mib": 10.0,
            "command": "other",
        }
    )
    with pytest.raises(RuntimeError, match="GPU3"):
        _validate_attempt19_fixture_steady(fixture, evidence)


def test_attempt19_steady_preserves_inactive_vulkan_fb_and_other_tenant_contexts(
    tmp_path, monkeypatch
):
    fixture = _write_attempt19_resource_fixture(tmp_path, monkeypatch)
    evidence = copy.deepcopy(fixture["steady_json"])
    for index in (0, 1, 3, 4, 5, 6, 7):
        device = next(item for item in evidence["per_device"] if item["index"] == index)
        assert device["context_classification"] == (
            "AUTHORIZED_INACTIVE_VULKAN_ENUMERATION"
        )
        assert device["attempt_process_memory_mib"] == 136.0
    gpu0 = next(device for device in evidence["per_device"] if device["index"] == 0)
    tenant_compute = {
        "pid": 888,
        "name": "tenant",
        "memory_used_mib": 22.0,
    }
    tenant_pmon = {
        "gpu_index": 0,
        "pid": 888,
        "type": "C",
        "sm_util_percent": 2.0,
        "sm_util_percent_state": "REPORTED",
        "memory_util_percent": 3.0,
        "memory_util_percent_state": "REPORTED",
        "fb_memory_mib": 22.0,
        "fb_memory_mib_state": "REPORTED",
        "command": "tenant",
        "source": attempt19_gpu_evidence.PMON_SOURCE,
    }
    gpu0["compute_processes"].append(tenant_compute)
    gpu0["pmon_processes"].append(tenant_pmon)
    evidence["per_device"][0]["utilization_gpu_percent"] = 17.0
    evidence["non_leased_observed_utilization_gpu_percent"] = 17.0
    evidence["non_leased_tenant_occupancy_at_steady_state"].append(
        {
            "device_index": 0,
            "attribution": "OTHER_TENANT",
            "utilization_gpu_percent": 17.0,
            "processes": [tenant_compute],
            "pmon_processes": [tenant_pmon],
        }
    )
    result = _validate_attempt19_fixture_steady(fixture, evidence)
    assert 0 in result["tenant_devices_at_steady_state"]
    assert result["attempt_process_memory_by_device"][0] == 136.0


@pytest.mark.parametrize("kind", ("stale", "future"))
def test_attempt19_steady_capture_timestamp_must_be_fresh(tmp_path, monkeypatch, kind):
    fixture = _write_attempt19_resource_fixture(tmp_path, monkeypatch)
    evidence = copy.deepcopy(fixture["steady_json"])
    now = datetime.now(ZoneInfo("Asia/Hong_Kong")).replace(microsecond=0)
    captured = now - timedelta(seconds=301) if kind == "stale" else now + timedelta(seconds=31)
    evidence["captured_at_hkt"] = captured.strftime("%Y-%m-%d %H:%M:%S HKT")
    with pytest.raises(RuntimeError, match="capture|future"):
        _validate_attempt19_fixture_steady(
            fixture,
            evidence,
            now=now,
            require_fresh=True,
        )


@pytest.mark.parametrize("mutation,match", (("launch_equal_start", "before process start"), ("steady_after_finish", "within the process lifecycle"), ("reversed", "timestamps are reversed")))
def test_attempt19_closure_enforces_process_lifecycle_ordering(
    tmp_path, monkeypatch, mutation, match
):
    fixture = _write_attempt19_resource_fixture(tmp_path, monkeypatch)
    process_receipt = copy.deepcopy(fixture["process_receipt"])
    if mutation == "launch_equal_start":
        launch = json.loads(fixture["launch"].read_text(encoding="utf-8"))
        launch["captured_at_hkt"] = process_receipt["started_at_hkt"]
        fixture["launch"].write_text(json.dumps(launch), encoding="utf-8")
    elif mutation == "steady_after_finish":
        steady = json.loads(fixture["steady"].read_text(encoding="utf-8"))
        steady["captured_at_hkt"] = "2099-01-01 00:00:00 HKT"
        fixture["steady"].write_text(json.dumps(steady), encoding="utf-8")
    else:
        process_receipt["finished_at_hkt"] = process_receipt["started_at_hkt"]
        process_receipt["started_at_hkt"] = "2099-01-01 00:00:01 HKT"
    with pytest.raises(RuntimeError, match=match):
        anchor_receipts._validate_attempt19_resource_evidence(
            plan=fixture["plan_json"],
            plan_artifact=anchor_receipts._artifact(fixture["plan"]),
            process_receipt=process_receipt,
            log_path=fixture["log"],
            launch_occupancy_path=fixture["launch"],
            steady_state_footprint_path=fixture["steady"],
        )


def test_attempt19_closure_binds_process_receipt_identity_to_static_steady_evidence(
    tmp_path, monkeypatch
):
    fixture = _write_attempt19_resource_fixture(tmp_path, monkeypatch)
    process_receipt = copy.deepcopy(fixture["process_receipt"])
    process_receipt["runner_pid"] = 999
    with pytest.raises(RuntimeError, match="runner_pid"):
        anchor_receipts._validate_attempt19_resource_evidence(
            plan=fixture["plan_json"],
            plan_artifact=anchor_receipts._artifact(fixture["plan"]),
            process_receipt=process_receipt,
            log_path=fixture["log"],
            launch_occupancy_path=fixture["launch"],
            steady_state_footprint_path=fixture["steady"],
        )


def _attempt18_summary_fixture(*, outcome: str = "ARC_PROBE_REACHED", passed: bool = True):
    raw = [0.0, 0.0, 0.0, 0.0, 0.0]
    final_action = raw + [0.0] * 7
    response = {
        "schema": "a2_piper_pull_v0_stage0_command_response_v2",
        "threshold_mode": "report_only",
        "episode_generation": 0,
        "trace_row_index": 0,
        "control_step": 0,
        "response_control_step": 1,
        "base_command_scale": 0.25,
        "body_pitch_roll_scale": 0.4,
        "high_level_base_action_raw": raw,
        "base_action_raw_trace": raw,
        "expected_scaled_body_command": raw,
        "physical_base_command": raw,
        "physical_command_clipped": False,
        "downstream_lower_body_command": [0.0] * 12,
        "observed_world_xy_velocity": [0.0, 0.0],
        "observed_world_xy_displacement": [0.0, 0.0],
    }
    response_summary = {
        "schema": "a2_piper_pull_v0_stage0_command_response_summary_v2",
        "status": "CAPTURED",
        "threshold_mode": "report_only",
        "response_count": 1,
        "responses": [response],
        "terminal_response": response,
        "anti_alignment_count": 0,
        "max_observed_world_xy_speed_mps": 0.0,
        "max_observed_world_xy_displacement_m": 0.0,
        "min_progress_velocity_cosine": 1.0,
        "min_progress_displacement_cosine": 1.0,
    }
    trace_row = {
        "episode_generation": 0,
        "step": 0,
        "stage0_predicates": {"staging_band": True, "settle_count": 5, "timed_out": False},
        "base_applied_action": raw,
        "final_action": final_action,
    }
    terminal_snapshot = {
        "stage": 4,
        "phase": "DONE",
        "outcome": outcome,
        "terminal_body_panel_contact_total_n": 0.0,
    }
    admission = {
        "schema": "a2_piper_pull_v0_push_anchor_admission_terminal_v1",
        "trace_step_count": 1,
        "trace_budget_steps": 6000,
        "trace": [trace_row],
        "stage0_predicates": {"staging_band": True, "settle_count": 5, "timed_out": False},
        "scripted_activation": {"first_control_step": 3},
        "dls_candidate_mask": False,
        "dls_finally_applied": False,
        "body_panel_contact_per_filter_max_n": [0.0] * 13,
        "body_panel_contact_total_max_n": 0.0,
        "first_contact_step": None,
        "first_contact_phase": None,
        "first_contact_filter": None,
        "max_contact_step": None,
        "max_contact_phase": None,
        "max_contact_filter": None,
        "terminal_snapshot": terminal_snapshot,
        "stage0_command_response": response_summary,
    }
    summary = {
        "schema": "a2_piper_pull_v0_p1_scripted_probe_runtime_v1",
        "probe_mode": "push_anchor",
        "status": "PASS" if passed else "FAIL",
        "threshold_mode": "report_only",
        "command_contract": {
            "commandable_dofs_only": True,
            "arm": "DifferentialIKController Cartesian DLS to arm_j1..arm_j6",
            "gripper": "high-level gripper primitive under resolved actuator profile",
            "base": "bounded high-level planar velocity commands",
            "low_level_usd_runtime_writes": False,
        },
        "acquisition_contract": {
            "enabled": True,
            "admission_gate": "first_episode_active_only_for_push_anchor",
            "stage2_grasp_gate_required": False,
            "stage0_predicates_reported_separately": True,
            "proof_world_direction": "+X",
        },
        "config": {
            "v20_arc_probe_target_hinge_rad": 0.25,
            "v20_arc_probe_terminal_window_steps": 10,
            "pull_p1_body_contact_threshold_n": 1.0,
        },
        "per_env_outcome": [outcome],
        "per_env_pass": [passed],
        "per_env_proof_completed": [passed],
        "per_env_latch_released": [passed],
        "per_env_max_handle_rad": [0.5],
        "per_env_max_hinge_rad": [0.3 if passed else 0.1],
        "per_env_terminal_bilateral_streak": [10 if passed else 1],
        "per_env_max_body_force_n": [0.0 if passed else 2.0],
        "per_env_reset_contact_qualification_complete": [True],
        "per_env_reset_transient_observed": [True],
        "per_env_host_stage_time_elapsed_steps": [100],
        "per_env_host_stage_time_budget_steps": [100],
        "per_env_host_stage_overtime_observed": [False],
        "per_env_stage0_command_response": [response_summary],
        "per_env_proof_samples": [10 if passed else 1],
        "per_env_arc_samples": [10 if passed else 1],
        "finalize_called": True,
    }
    metrics = {
        "completed_episodes": 1,
        "episode_max_stage_reached": [4],
        "episode_terminal_reasons": ["stage_overtime"],
        "episode_terminal_diagnostics": [{"push_anchor_admission": admission}],
    }
    return summary, metrics, admission


def _patch_attempt18_temp_paths(monkeypatch, tmp_path):
    r15_path = tmp_path / "PULL_V0_REPAIR_R15_RECEIPT.json"
    r15_path.write_bytes(anchor_receipts.R15_RECEIPT_PATH.read_bytes())
    output_root = tmp_path / "attempt18"
    paths = {
        "r15": r15_path,
        "receipt": tmp_path / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT18_RECEIPT.json",
        "plan": tmp_path / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT18_PLAN.json",
        "output_root": output_root,
        "process": output_root / "process_receipt.json",
        "log": output_root / "stdout_stderr.log",
        "summary": output_root / "eval" / "a2_hold_oracle_summary.json",
        "metrics": output_root / "eval" / "metrics_eval.json",
        "launch_occupancy": tmp_path
        / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT18_LAUNCH_OCCUPANCY.json",
        "retry1_launch_occupancy": tmp_path
        / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT18_RETRY1_LAUNCH_OCCUPANCY.json",
        "steady_state_footprint": tmp_path
        / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT18_RETRY1_STEADY_STATE_FOOTPRINT.json",
        "prelaunch_infra": tmp_path
        / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT18_PRELAUNCH_INFRA1_RECEIPT.json",
        "r15e": tmp_path / "PULL_V0_REPAIR_R15E_RECEIPT.json",
        "r15f": tmp_path / "PULL_V0_REPAIR_R15F_RECEIPT.json",
    }
    monkeypatch.setattr(anchor_receipts, "R15_RECEIPT_PATH", paths["r15"])
    monkeypatch.setattr(anchor_receipts, "ATTEMPT18_RECEIPT_PATH", paths["receipt"])
    monkeypatch.setattr(anchor_receipts, "ATTEMPT18_PLAN_PATH", paths["plan"])
    monkeypatch.setattr(anchor_receipts, "ATTEMPT18_OUTPUT_ROOT", paths["output_root"])
    monkeypatch.setattr(anchor_receipts, "ATTEMPT18_PROCESS_PATH", paths["process"])
    monkeypatch.setattr(anchor_receipts, "ATTEMPT18_LOG_PATH", paths["log"])
    monkeypatch.setattr(anchor_receipts, "ATTEMPT18_SUMMARY_PATH", paths["summary"])
    monkeypatch.setattr(anchor_receipts, "ATTEMPT18_METRICS_PATH", paths["metrics"])
    monkeypatch.setattr(
        anchor_receipts,
        "ATTEMPT18_LAUNCH_OCCUPANCY_PATH",
        paths["launch_occupancy"],
    )
    monkeypatch.setattr(
        anchor_receipts,
        "ATTEMPT18_STEADY_STATE_FOOTPRINT_PATH",
        paths["steady_state_footprint"],
    )
    monkeypatch.setattr(
        anchor_receipts,
        "ATTEMPT18_RETRY1_LAUNCH_OCCUPANCY_PATH",
        paths["retry1_launch_occupancy"],
    )
    monkeypatch.setattr(
        anchor_receipts,
        "ATTEMPT18_RETRY1_STEADY_STATE_FOOTPRINT_PATH",
        paths["steady_state_footprint"],
    )
    monkeypatch.setattr(
        anchor_receipts,
        "ATTEMPT18_PRELAUNCH_INFRA_RECEIPT_PATH",
        paths["prelaunch_infra"],
    )
    monkeypatch.setattr(anchor_receipts, "ATTEMPT18_R15E_RECEIPT_PATH", paths["r15e"])
    monkeypatch.setattr(anchor_receipts, "ATTEMPT18_R15F_RECEIPT_PATH", paths["r15f"])
    return paths


def _write_attempt18_runtime_fixture(
    paths,
    summary=None,
    metrics=None,
    *,
    lifecycle_success=True,
    first_simulation_step_boundary_crossed=True,
):
    paths["output_root"].mkdir(parents=True, exist_ok=True)
    paths["log"].write_text("synthetic Attempt18 runtime log\n", encoding="utf-8")
    repair_artifact = anchor_receipts._artifact(paths["r15"])
    plan = {
        "schema_version": "pull_v0_p1_push_anchor_plan_v1",
        "status": "READY",
        "attempt": 18,
        "base_sha": anchor_runner.EXPECTED_BASE_SHA,
        "implementation_repair_used": True,
        "plan_sha256": "synthetic-attempt18-plan",
        "gpu_resource_lease": {
            "authorized_physical_devices": [2, 3],
            "selected_physical_device": 2,
            "gpu7_compute_authorized": False,
        },
        "repair_receipt": {
            "path": repair_artifact["path"],
            "sha256": repair_artifact["sha256"],
            "revision": "R15",
            "stale_candidate_id": anchor_receipts.EXPECTED_STALE_CANDIDATE_ID,
            "parent_receipt_sha256": anchor_receipts.EXPECTED_GPU_LEASE_AMENDMENT_SHA256,
        },
    }
    paths["plan"].write_text(json.dumps(plan), encoding="utf-8")
    plan_binding = {
        "path": anchor_receipts._artifact(paths["plan"])["path"],
        "sha256": anchor_receipts._artifact(paths["plan"])["sha256"],
        "plan_sha256": plan["plan_sha256"],
    }
    leased_devices = {2, 3}
    non_leased_devices = {0, 1, 4, 5, 6, 7}
    launch_devices = [
        {
            "index": index,
            "uuid": f"GPU-{index}",
            "leased": index in leased_devices,
            "memory_used_mib": 1,
            "utilization_gpu_percent": 0,
            "compute_processes": [],
        }
        for index in range(8)
    ]
    footprint_devices = []
    for index in range(8):
        non_leased = index in non_leased_devices
        selected = index == 2
        footprint_devices.append(
            {
                "index": index,
                "uuid": f"GPU-{index}",
                "leased": index in leased_devices,
                **({"selected": True} if selected else {}),
                "total_memory_used_mib": 148 if non_leased else (3147 if selected else 161),
                "attempt_process_memory_mib": 136
                if non_leased
                else (3087 if selected else 140),
                "utilization_gpu_percent": 0
                if non_leased or not first_simulation_step_boundary_crossed
                else (18 if selected else 0),
                "context_classification": (
                    "AUTHORIZED_INACTIVE_VULKAN_ENUMERATION"
                    if non_leased or not first_simulation_step_boundary_crossed or not selected
                    else "AUTHORIZED_COMPUTE"
                ),
            }
        )
    launch = {
        "schema_version": "pull_v0_p1_attempt18_launch_occupancy_v1",
        "captured_at_hkt": "2026-08-04 19:00:00 HKT",
        "attempt": 18,
        "phase": "IMMEDIATELY_BEFORE_LAUNCH",
        "status": "PASS",
        "plan": plan_binding,
        "selected_compute_physical_device": 2,
        "authorized_compute_physical_devices": [2, 3],
        "unauthorized_compute_physical_devices": [0, 1, 4, 5, 6, 7],
        "per_device": launch_devices,
        "non_leased_tenant_occupancy_at_launch": [],
        "cuda_visible_devices": "UNSET",
        "incidental_vulkan_enumeration_contexts_authorized": True,
        "container_isolation_used": False,
        "runtime_started": False,
        "scientific_attempt_started": False,
    }
    footprint = {
        "schema_version": "pull_v0_p1_attempt18_steady_state_footprint_v1",
        "captured_at_hkt": "2026-08-04 19:01:00 HKT",
        "attempt": 18,
        "phase": (
            "EVALUATION_STEPPING"
            if first_simulation_step_boundary_crossed
            else "PRE_FIRST_SIMULATION_STEP"
        ),
        "status": "PASS",
        "plan": plan_binding,
        "process": {"pid": 12345, "name": "/synthetic/attempt18"},
        "selected_compute_physical_device": 2,
        "authorized_compute_physical_devices": [2, 3],
        "unauthorized_compute_physical_devices": [0, 1, 4, 5, 6, 7],
        "per_device": footprint_devices,
        "max_non_leased_attempt_process_memory_mib": 136,
        "non_leased_stop_threshold_mib": 1024,
        "non_leased_threshold_pass": True,
        "non_leased_observed_utilization_gpu_percent": 0,
        "kit_active_physical_devices": [2],
        "app_launcher_device": "cuda:2",
        "environment_device": "cuda:2",
        "cuda_visible_devices": "UNSET",
        "container_isolation_used": False,
        "first_simulation_step_boundary_crossed": first_simulation_step_boundary_crossed,
        "first_simulation_step_evidence": (
            "Synthetic evidence records the requested first-step boundary state."
        ),
        "scientific_attempt_started": first_simulation_step_boundary_crossed,
    }
    paths["launch_occupancy"].write_text(json.dumps(launch), encoding="utf-8")
    paths["retry1_launch_occupancy"].write_text(json.dumps(launch), encoding="utf-8")
    paths["steady_state_footprint"].write_text(json.dumps(footprint), encoding="utf-8")
    prelaunch = {
        "schema_version": "pull_v0_p1_push_anchor_attempt18_prelaunch_infra_receipt_v1",
        "attempt": 18,
        "status": "INFRA_PRELAUNCH_RUNNER_VALIDATION",
        "runtime_validation": "INVALIDATED_BEFORE_LAUNCH",
        "scientific_verdict_consumed": False,
        "first_simulation_step_boundary_crossed": False,
        "scientific_attempt_started": False,
        "parent_receipt": {
            "path": repair_artifact["path"],
            "sha256": repair_artifact["sha256"],
            "repair_revision": "R15",
        },
        "error": {"signature": r15e_receipts.ERROR_SIGNATURE},
        "artifacts": {
            "plan": anchor_receipts._artifact(paths["plan"]),
            "initial_launch_occupancy": anchor_receipts._artifact(paths["launch_occupancy"]),
            "input_config": {"path": "synthetic/config.yaml", "sha256": "synthetic-config"},
            "checkpoint": {"path": "synthetic/checkpoint.pt", "sha256": "synthetic-checkpoint"},
        },
    }
    paths["prelaunch_infra"].write_text(json.dumps(prelaunch), encoding="utf-8")
    prelaunch_artifact = anchor_receipts._artifact(paths["prelaunch_infra"])
    r15e = {
        "schema_version": "pull_v0_repair_r15e_receipt_v1",
        "repair_revision": "R15E",
        "status": "APPROVED_FOR_ATTEMPT18_RETRY1_PREPARATION_ONLY",
        "runtime_validation": "NOT_RUN",
        "scientific_verdict_consumed": False,
        "parent_receipt": {
            "path": repair_artifact["path"],
            "sha256": repair_artifact["sha256"],
            "repair_revision": "R15",
        },
        "trigger": {
            "prelaunch_infra_receipt": prelaunch_artifact,
            "exact_error_signature": r15e_receipts.ERROR_SIGNATURE,
        },
        "preserved_artifacts": {
            "plan": anchor_receipts._artifact(paths["plan"]),
            "initial_launch_occupancy": anchor_receipts._artifact(paths["launch_occupancy"]),
        },
    }
    paths["r15e"].write_text(json.dumps(r15e), encoding="utf-8")
    r15e_artifact = anchor_receipts._artifact(paths["r15e"])
    r15f = {
        "schema_version": "pull_v0_repair_r15f_receipt_v1",
        "repair_revision": "R15F",
        "status": "APPROVED_FOR_ATTEMPT18_RETRY1_LAUNCH_ADMISSION_ONLY",
        "runtime_validation": "NOT_RUN",
        "scientific_verdict_consumed": False,
        "stale_candidate_id": anchor_receipts.EXPECTED_STALE_CANDIDATE_ID,
        "parent_receipt": {
            "path": r15e_artifact["path"],
            "sha256": r15e_artifact["sha256"],
            "repair_revision": "R15E",
        },
        "trigger": {
            "attempt": 18,
            "root_cause": "ATTEMPT18_RETRY1_LAUNCH_OCCUPANCY_ADMISSION_CONTRADICTION",
            "r15e_receipt": r15e_artifact,
            "required_retry1_launch_occupancy": {
                "path": anchor_receipts._artifact(paths["retry1_launch_occupancy"])["path"],
                "schema_version": "pull_v0_p1_attempt18_launch_occupancy_v1",
                "phase": "IMMEDIATELY_BEFORE_LAUNCH",
                "selected_compute_physical_device": 2,
                "authorized_compute_physical_devices": [2, 3],
                "cuda_visible_devices": "UNSET",
                "container_isolation_used": False,
            },
        },
        "preserved_artifacts": {
            "r15e": r15e_artifact,
            "prelaunch_infra": prelaunch_artifact,
            "plan": anchor_receipts._artifact(paths["plan"]),
            "initial_launch_occupancy": anchor_receipts._artifact(paths["launch_occupancy"]),
        },
    }
    paths["r15f"].write_text(json.dumps(r15f), encoding="utf-8")
    summary_artifact = metrics_artifact = None
    if summary is not None:
        paths["summary"].parent.mkdir(parents=True, exist_ok=True)
        paths["summary"].write_text(json.dumps(summary), encoding="utf-8")
        paths["metrics"].write_text(json.dumps(metrics), encoding="utf-8")
        summary_artifact = anchor_receipts._artifact(paths["summary"])
        metrics_artifact = anchor_receipts._artifact(paths["metrics"])
    process = {
        "schema_version": "pull_v0_p1_push_anchor_process_v1",
        "attempt": 18,
        "returncode": 0 if lifecycle_success else 1,
        "natural_exit": lifecycle_success,
        "application_success": lifecycle_success,
        "plan_path": anchor_receipts._artifact(paths["plan"])["path"],
        "plan_sha256": plan["plan_sha256"],
        "stdout_stderr_path": anchor_receipts._artifact(paths["log"])["path"],
        "stdout_stderr_sha256": anchor_receipts._artifact(paths["log"])["sha256"],
        "repair_receipt_sha256": repair_artifact["sha256"],
        "summary_path": None if summary_artifact is None else summary_artifact["path"],
        "summary_sha256": None if summary_artifact is None else summary_artifact["sha256"],
        "metrics_path": None if metrics_artifact is None else metrics_artifact["path"],
        "metrics_sha256": None if metrics_artifact is None else metrics_artifact["sha256"],
    }
    paths["process"].write_text(json.dumps(process), encoding="utf-8")


def test_attempt18_preparation_validation_rejects_preexisting_temp_artifact(tmp_path, monkeypatch):
    paths = _patch_attempt18_temp_paths(monkeypatch, tmp_path)
    paths["plan"].write_text("pre-existing plan", encoding="utf-8")
    with pytest.raises(RuntimeError, match="pre-existing Attempt18 artifact"):
        anchor_receipts._validate_repair_receipt(paths["r15"], attempt=18)
    paths["plan"].unlink()
    paths["launch_occupancy"].write_text("pre-existing occupancy", encoding="utf-8")
    with pytest.raises(RuntimeError, match="pre-existing Attempt18 artifact"):
        anchor_receipts._validate_repair_receipt(paths["r15"], attempt=18)
    paths["launch_occupancy"].unlink()
    paths["steady_state_footprint"].write_text("pre-existing footprint", encoding="utf-8")
    with pytest.raises(RuntimeError, match="pre-existing Attempt18 artifact"):
        anchor_receipts._validate_repair_receipt(paths["r15"], attempt=18)


def test_attempt18_prepare_only_plan_can_reenter_exact_run_preparation_without_launch(
    monkeypatch,
):
    plan_path = anchor_runner._attempt_plan_path(18)
    before = plan_path.read_bytes()

    def fail_if_launched(*args, **kwargs):
        raise AssertionError("R15E re-entry preparation must not launch a subprocess")

    monkeypatch.setattr(anchor_runner.subprocess, "run", fail_if_launched)
    with pytest.raises(RuntimeError, match="pre-existing scientific artifact"):
        anchor_runner.prepare(
            18,
            anchor_runner.R15_RECEIPT_PATH,
            anchor_runner.EXPECTED_R15_RECEIPT_SHA256,
            allow_existing_plan=True,
        )
    assert plan_path.read_bytes() == before


def test_attempt18_cli_ready_state_accepts_preserved_prelaunch_chain_without_runtime(
    tmp_path, monkeypatch
):
    paths = _patch_attempt18_temp_paths(monkeypatch, tmp_path)
    _write_attempt18_runtime_fixture(paths)
    for key in (
        "process",
        "log",
        "summary",
        "metrics",
        "retry1_launch_occupancy",
        "steady_state_footprint",
    ):
        paths[key].unlink(missing_ok=True)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_p1_anchor_stop_receipts.py",
            "--attempt",
            "18",
            "--repair-receipt",
            str(paths["r15"]),
        ],
    )
    assert anchor_receipts.main() == 0
    assert not paths["receipt"].exists()


def test_attempt18_cli_rejects_partial_prelaunch_chain_before_retry_admission(
    tmp_path, monkeypatch
):
    paths = _patch_attempt18_temp_paths(monkeypatch, tmp_path)
    _write_attempt18_runtime_fixture(paths)
    paths["prelaunch_infra"].unlink()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_p1_anchor_stop_receipts.py",
            "--attempt",
            "18",
            "--repair-receipt",
            str(paths["r15"]),
        ],
    )
    with pytest.raises(RuntimeError, match="prelaunch infrastructure chain is incomplete"):
        anchor_receipts.main()
    assert not paths["receipt"].exists()


def test_attempt18_reentry_rejects_tampered_temp_plan_without_launch(tmp_path, monkeypatch):
    plan_path = tmp_path / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT18_PLAN.json"
    plan = json.loads(anchor_runner._attempt_plan_path(18).read_text(encoding="utf-8"))
    plan["command_sha256"] = "0" * 64
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    expected = json.loads(anchor_runner._attempt_plan_path(18).read_text(encoding="utf-8"))
    with pytest.raises(RuntimeError, match="semantic identity differs"):
        anchor_runner._assert_existing_plan_matches(plan, expected, plan_path)


def _runner_attempt18_plan():
    return json.loads(anchor_runner._attempt_plan_path(18).read_text(encoding="utf-8"))


def _write_runner_retry1_occupancy(path, *, mutation=None):
    occupancy = json.loads(
        (
            ROOT
            / "scriptsFORhuman/pull_v0/PULL_V0_P1_PUSH_ANCHOR_ATTEMPT18_LAUNCH_OCCUPANCY.json"
        ).read_text(encoding="utf-8")
    )
    if mutation == "plan":
        occupancy["plan"]["sha256"] = "0" * 64
    elif mutation == "gpu":
        occupancy["selected_compute_physical_device"] = 3
    elif mutation == "tenant":
        occupancy["per_device"][4]["compute_processes"] = [
            {"pid": 44004, "name": "foreign", "memory_used_mib": 64}
        ]
    path.write_text(json.dumps(occupancy), encoding="utf-8")


def test_attempt18_runner_requires_retry1_occupancy_before_subprocess(tmp_path, monkeypatch):
    occupancy_path = tmp_path / "retry1_launch_occupancy.json"
    output_root = tmp_path / "attempt18"
    monkeypatch.setattr(anchor_runner, "ATTEMPT18_RETRY1_LAUNCH_OCCUPANCY_PATH", occupancy_path)
    monkeypatch.setattr(anchor_runner, "_attempt_output_root", lambda attempt: output_root)
    monkeypatch.setattr(anchor_runner, "prepare", lambda *args, **kwargs: _runner_attempt18_plan())
    launched = []
    monkeypatch.setattr(anchor_runner.subprocess, "run", lambda *args, **kwargs: launched.append(args))
    with pytest.raises(RuntimeError, match="retry1 launch occupancy is missing"):
        anchor_runner.run(
            18,
            anchor_runner.R15_RECEIPT_PATH,
            anchor_runner.EXPECTED_R15_RECEIPT_SHA256,
        )
    assert launched == []


def test_attempt18_runner_valid_retry1_occupancy_reaches_mocked_subprocess(tmp_path, monkeypatch):
    occupancy_path = tmp_path / "retry1_launch_occupancy.json"
    _write_runner_retry1_occupancy(occupancy_path)
    runner_root = tmp_path / "runner_root"
    plan_path = runner_root / "scriptsFORhuman/pull_v0/PULL_V0_P1_PUSH_ANCHOR_ATTEMPT18_PLAN.json"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_bytes(anchor_runner._attempt_plan_path(18).read_bytes())
    monkeypatch.setattr(anchor_runner, "ROOT", runner_root)
    monkeypatch.setattr(anchor_runner, "_attempt_plan_path", lambda attempt: plan_path)
    output_root = runner_root / "logs_eval/a2_piper_pull_v0/p1_push_anchor/attempt18"
    monkeypatch.setattr(anchor_runner, "ATTEMPT18_RETRY1_LAUNCH_OCCUPANCY_PATH", occupancy_path)
    monkeypatch.setattr(anchor_runner, "_attempt_output_root", lambda attempt: output_root)
    monkeypatch.setattr(anchor_runner, "prepare", lambda *args, **kwargs: _runner_attempt18_plan())
    launched = []

    def fake_run(*args, **kwargs):
        launched.append((args, kwargs))
        return SimpleNamespace(returncode=1)

    monkeypatch.setattr(anchor_runner.subprocess, "run", fake_run)
    assert (
        anchor_runner.run(
            18,
            anchor_runner.R15_RECEIPT_PATH,
            anchor_runner.EXPECTED_R15_RECEIPT_SHA256,
        )
        == 1
    )
    assert len(launched) == 1
    assert (ROOT / "scriptsFORhuman/pull_v0/PULL_V0_P1_PUSH_ANCHOR_ATTEMPT18_RECEIPT.json").is_file()


@pytest.mark.parametrize(
    "mutation,match",
    (
        ("plan", "does not bind the exact prepared plan"),
        ("gpu", "GPU2/\[2, 3\] lease contract"),
        ("tenant", "unrecorded non-leased occupancy"),
    ),
)
def test_attempt18_runner_rejects_tampered_retry1_occupancy_before_subprocess(
    tmp_path, monkeypatch, mutation, match
):
    occupancy_path = tmp_path / "retry1_launch_occupancy.json"
    _write_runner_retry1_occupancy(occupancy_path, mutation=mutation)
    output_root = tmp_path / "attempt18"
    monkeypatch.setattr(anchor_runner, "ATTEMPT18_RETRY1_LAUNCH_OCCUPANCY_PATH", occupancy_path)
    monkeypatch.setattr(anchor_runner, "_attempt_output_root", lambda attempt: output_root)
    monkeypatch.setattr(anchor_runner, "prepare", lambda *args, **kwargs: _runner_attempt18_plan())
    launched = []
    monkeypatch.setattr(anchor_runner.subprocess, "run", lambda *args, **kwargs: launched.append(args))
    with pytest.raises(RuntimeError, match=match):
        anchor_runner.run(
            18,
            anchor_runner.R15_RECEIPT_PATH,
            anchor_runner.EXPECTED_R15_RECEIPT_SHA256,
        )
    assert launched == []


def test_attempt18_runner_still_rejects_retry1_steady_state_reuse(tmp_path, monkeypatch):
    steady_path = tmp_path / "retry1_steady_state_footprint.json"
    steady_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(anchor_runner, "ATTEMPT18_RETRY1_STEADY_STATE_FOOTPRINT_PATH", steady_path)
    with pytest.raises(RuntimeError, match="pre-existing scientific artifact"):
        anchor_runner._read_repair_receipt(
            anchor_runner.R15_RECEIPT_PATH,
            attempt=18,
            repair_receipt_sha256=anchor_runner.EXPECTED_R15_RECEIPT_SHA256,
            allow_attempt18_runtime=True,
        )


def test_attempt18_cli_builds_pass_receipt_from_exact_temp_runtime_chain(tmp_path, monkeypatch):
    paths = _patch_attempt18_temp_paths(monkeypatch, tmp_path)
    summary, metrics, _ = _attempt18_summary_fixture()
    _write_attempt18_runtime_fixture(paths, summary, metrics)
    with pytest.raises(RuntimeError, match="canonical plan path"):
        anchor_receipts.build_post_r1_attempt_receipt(
            18,
            plan_path=tmp_path / "wrong_attempt18_plan.json",
            process_receipt_path=paths["process"],
            log_path=paths["log"],
            summary_path=paths["summary"],
            metrics_path=paths["metrics"],
            repair_receipt_path=paths["r15"],
            prelaunch_infra_receipt_path=paths["prelaunch_infra"],
            r15e_receipt_path=paths["r15e"],
            retry1_launch_occupancy_path=paths["retry1_launch_occupancy"],
            retry1_steady_state_footprint_path=paths["steady_state_footprint"],
        )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_p1_anchor_stop_receipts.py",
            "--attempt",
            "18",
            "--repair-receipt",
            str(paths["r15"]),
        ],
    )
    assert anchor_receipts.main() == 0
    receipt = json.loads(paths["receipt"].read_text(encoding="utf-8"))
    assert receipt["status"] == "ANCHOR_PASS"
    assert receipt["probe_validity"] == "PROBE_VALID"
    assert receipt["scientific_verdict_consumed"] is True
    assert receipt["pull_mechanism_verdict"] == "NOT_ASSESSED"
    assert receipt["outcome"]["outcome_code"] == "ARC_PROBE_REACHED"
    assert receipt["outcome"]["named_finding"] == "ARC_PROBE_REACHED"
    assert receipt["repair_r15f"]["revision"] == "R15F"
    assert receipt["repair_r15f"]["artifact"]["sha256"] == _sha256(paths["r15f"])
    assert receipt["runtime_evidence"] == {
        "first_simulation_step_boundary_crossed": True,
        "scientific_attempt_started": True,
        "selected_compute_physical_device": 2,
        "authorized_compute_physical_devices": [2, 3],
        "non_leased_compute_observed": False,
        "tenant_devices_at_launch": [],
    }
    launch_evidence = json.loads(paths["launch_occupancy"].read_text(encoding="utf-8"))
    footprint_evidence = json.loads(
        paths["steady_state_footprint"].read_text(encoding="utf-8")
    )
    assert launch_evidence["non_leased_tenant_occupancy_at_launch"] == []
    assert footprint_evidence["non_leased_observed_utilization_gpu_percent"] == 0
    assert receipt["artifacts"]["initial_launch_occupancy"]["sha256"] == _sha256(
        paths["launch_occupancy"]
    )
    assert receipt["artifacts"]["launch_occupancy"]["sha256"] == _sha256(
        paths["retry1_launch_occupancy"]
    )
    assert receipt["artifacts"]["steady_state_footprint"]["sha256"] == _sha256(
        paths["steady_state_footprint"]
    )
    assert paths["plan"].is_file()
    assert paths["process"].is_file()


def test_attempt18_scientific_failure_is_named_and_unknown_or_legacy_pass_fails_fast():
    summary, metrics, admission = _attempt18_summary_fixture(
        outcome="PULL_P1_BODY_COLLISION", passed=False
    )
    classified = anchor_receipts._classify_attempt18_scientific_outcome(
        summary=summary, admission=admission
    )
    assert classified["status"] == "ANCHOR_FAIL_PHYSICS"
    assert classified["scientific_verdict_consumed"] is True
    assert classified["finding"]["named_finding"] == "PULL_P1_BODY_COLLISION"
    assert classified["finding"]["lineage"] == "NEW_NAMED_SCIENTIFIC_FINDING"
    assert classified["observed"]["terminal_outcome"] == "PULL_P1_BODY_COLLISION"
    failure_receipt = anchor_receipts._build_attempt18_scientific_receipt(
        admission=admission,
        repair_receipt={"repair_revision": "R15", "stale_candidate_id": "synthetic"},
        repair_artifact={},
        plan_artifact={},
        process_artifact={},
        log_artifact={},
        launch_occupancy_artifact={},
        steady_state_footprint_artifact={},
        summary_artifact={},
        metrics_artifact={},
        process_receipt={},
        summary=summary,
        resource_evidence={
            "first_simulation_step_boundary_crossed": True,
            "scientific_attempt_started": True,
            "non_leased_compute_observed": False,
        },
    )
    assert failure_receipt["status"] == "ANCHOR_FAIL_PHYSICS"
    assert failure_receipt["scientific_verdict_consumed"] is True
    assert failure_receipt["pull_mechanism_verdict"] == "NOT_ASSESSED"
    unknown_summary = copy.deepcopy(summary)
    unknown_summary["per_env_outcome"] = ["UNKNOWN_OUTCOME"]
    unknown_admission = copy.deepcopy(admission)
    unknown_admission["terminal_snapshot"]["outcome"] = "UNKNOWN_OUTCOME"
    with pytest.raises(RuntimeError, match="Unknown Attempt18 scientific outcome"):
        anchor_receipts._classify_attempt18_scientific_outcome(
            summary=unknown_summary, admission=unknown_admission
        )
    legacy_summary, _, legacy_admission = _attempt18_summary_fixture(
        outcome="RETAINED", passed=True
    )
    with pytest.raises(RuntimeError, match="ARC_PROBE_REACHED hard gate"):
        anchor_receipts._classify_attempt18_scientific_outcome(
            summary=legacy_summary, admission=legacy_admission
        )


def test_attempt18_lifecycle_failure_is_infra_without_scientific_verdict(tmp_path, monkeypatch):
    paths = _patch_attempt18_temp_paths(monkeypatch, tmp_path)
    _write_attempt18_runtime_fixture(
        paths,
        lifecycle_success=False,
        first_simulation_step_boundary_crossed=False,
    )
    receipt = anchor_receipts.build_post_r1_attempt_receipt(
        18,
        plan_path=paths["plan"],
        process_receipt_path=paths["process"],
        log_path=paths["log"],
        summary_path=paths["summary"],
        metrics_path=paths["metrics"],
        repair_receipt_path=paths["r15"],
        prelaunch_infra_receipt_path=paths["prelaunch_infra"],
        r15e_receipt_path=paths["r15e"],
        retry1_launch_occupancy_path=paths["retry1_launch_occupancy"],
        retry1_steady_state_footprint_path=paths["steady_state_footprint"],
    )
    assert receipt["status"] == "INFRA_PRE_FIRST_SIMULATION_STEP"
    assert receipt["scientific_verdict_consumed"] is False
    assert receipt["pull_mechanism_verdict"] == "NOT_ASSESSED"
    assert receipt["infrastructure_failure"]["first_simulation_step_boundary_crossed"] is False
    assert receipt["infrastructure_failure"]["scientific_attempt_started"] is False
    assert receipt["artifacts"]["initial_launch_occupancy"]["sha256"] == _sha256(
        paths["launch_occupancy"]
    )
    assert receipt["artifacts"]["launch_occupancy"]["sha256"] == _sha256(
        paths["retry1_launch_occupancy"]
    )
    assert receipt["artifacts"]["steady_state_footprint"]["sha256"] == _sha256(
        paths["steady_state_footprint"]
    )
    assert receipt["artifacts"]["summary"] is None
    assert receipt["artifacts"]["metrics"] is None


@pytest.mark.parametrize(
    "mutation,match",
    (
        ("missing_footprint", "regular file"),
        ("wrong_plan", "plan binding mismatch"),
        ("wrong_gpu", "authorized GPU contract"),
        ("non_leased_compute", "compute on non-leased"),
        ("footprint_non_leased_compute", "unrecorded non-leased"),
        ("inconsistent_boundary", "inconsistent first-step"),
    ),
)
def test_attempt18_resource_evidence_is_mandatory_and_fail_fast(
    tmp_path, monkeypatch, mutation, match
):
    paths = _patch_attempt18_temp_paths(monkeypatch, tmp_path)
    summary, metrics, _ = _attempt18_summary_fixture()
    _write_attempt18_runtime_fixture(paths, summary, metrics)
    if mutation == "missing_footprint":
        paths["steady_state_footprint"].unlink()
    elif mutation == "wrong_plan":
        footprint = json.loads(paths["steady_state_footprint"].read_text(encoding="utf-8"))
        footprint["plan"]["sha256"] = "0" * 64
        paths["steady_state_footprint"].write_text(json.dumps(footprint), encoding="utf-8")
    elif mutation == "wrong_gpu":
        occupancy = json.loads(paths["retry1_launch_occupancy"].read_text(encoding="utf-8"))
        occupancy["selected_compute_physical_device"] = 3
        paths["retry1_launch_occupancy"].write_text(json.dumps(occupancy), encoding="utf-8")
    elif mutation == "non_leased_compute":
        occupancy = json.loads(paths["retry1_launch_occupancy"].read_text(encoding="utf-8"))
        occupancy["per_device"][0]["compute_processes"] = [{"pid": 99}]
        paths["retry1_launch_occupancy"].write_text(json.dumps(occupancy), encoding="utf-8")
    elif mutation == "footprint_non_leased_compute":
        footprint = json.loads(paths["steady_state_footprint"].read_text(encoding="utf-8"))
        footprint["per_device"][0]["utilization_gpu_percent"] = 1
        paths["steady_state_footprint"].write_text(json.dumps(footprint), encoding="utf-8")
    else:
        footprint = json.loads(paths["steady_state_footprint"].read_text(encoding="utf-8"))
        footprint["scientific_attempt_started"] = False
        paths["steady_state_footprint"].write_text(json.dumps(footprint), encoding="utf-8")
    with pytest.raises(RuntimeError, match=match):
        anchor_receipts.build_post_r1_attempt_receipt(
            18,
            plan_path=paths["plan"],
            process_receipt_path=paths["process"],
            log_path=paths["log"],
            summary_path=paths["summary"],
            metrics_path=paths["metrics"],
            repair_receipt_path=paths["r15"],
            prelaunch_infra_receipt_path=paths["prelaunch_infra"],
            r15e_receipt_path=paths["r15e"],
            retry1_launch_occupancy_path=paths["retry1_launch_occupancy"],
            retry1_steady_state_footprint_path=paths["steady_state_footprint"],
        )


def test_attempt18_post_step_lifecycle_failure_is_not_downgraded_to_infra(
    tmp_path, monkeypatch
):
    paths = _patch_attempt18_temp_paths(monkeypatch, tmp_path)
    _write_attempt18_runtime_fixture(
        paths,
        lifecycle_success=False,
        first_simulation_step_boundary_crossed=True,
    )
    with pytest.raises(RuntimeError, match="scientific attempt is unsealable"):
        anchor_receipts.build_post_r1_attempt_receipt(
            18,
            plan_path=paths["plan"],
            process_receipt_path=paths["process"],
            log_path=paths["log"],
            summary_path=paths["summary"],
            metrics_path=paths["metrics"],
            repair_receipt_path=paths["r15"],
            prelaunch_infra_receipt_path=paths["prelaunch_infra"],
            r15e_receipt_path=paths["r15e"],
            retry1_launch_occupancy_path=paths["retry1_launch_occupancy"],
            retry1_steady_state_footprint_path=paths["steady_state_footprint"],
        )


def test_attempt18_successful_lifecycle_before_first_step_cannot_be_scientific(
    tmp_path, monkeypatch
):
    paths = _patch_attempt18_temp_paths(monkeypatch, tmp_path)
    summary, metrics, _ = _attempt18_summary_fixture()
    _write_attempt18_runtime_fixture(
        paths,
        summary,
        metrics,
        lifecycle_success=True,
        first_simulation_step_boundary_crossed=False,
    )
    with pytest.raises(RuntimeError, match="requires exact steady-state evidence after"):
        anchor_receipts.build_post_r1_attempt_receipt(
            18,
            plan_path=paths["plan"],
            process_receipt_path=paths["process"],
            log_path=paths["log"],
            summary_path=paths["summary"],
            metrics_path=paths["metrics"],
            repair_receipt_path=paths["r15"],
            prelaunch_infra_receipt_path=paths["prelaunch_infra"],
            r15e_receipt_path=paths["r15e"],
            retry1_launch_occupancy_path=paths["retry1_launch_occupancy"],
            retry1_steady_state_footprint_path=paths["steady_state_footprint"],
        )


def test_attempt18_recorded_non_leased_tenant_is_not_attempt18_compute(
    tmp_path, monkeypatch
):
    paths = _patch_attempt18_temp_paths(monkeypatch, tmp_path)
    summary, metrics, _ = _attempt18_summary_fixture()
    _write_attempt18_runtime_fixture(paths, summary, metrics)
    tenant_process = {
        "pid": 9001,
        "name": "tenant-job",
        "memory_used_mib": 512,
    }
    launch = json.loads(paths["retry1_launch_occupancy"].read_text(encoding="utf-8"))
    launch["per_device"][0]["utilization_gpu_percent"] = 12
    launch["per_device"][0]["compute_processes"] = [tenant_process]
    launch["non_leased_tenant_occupancy_at_launch"] = [
        {
            "device_index": 0,
            "attribution": "OTHER_TENANT",
            "utilization_gpu_percent": 12,
            "processes": [tenant_process],
        }
    ]
    paths["retry1_launch_occupancy"].write_text(json.dumps(launch), encoding="utf-8")
    footprint = json.loads(paths["steady_state_footprint"].read_text(encoding="utf-8"))
    footprint["per_device"][0]["utilization_gpu_percent"] = 27
    footprint["non_leased_observed_utilization_gpu_percent"] = 27
    paths["steady_state_footprint"].write_text(json.dumps(footprint), encoding="utf-8")
    receipt = anchor_receipts.build_post_r1_attempt_receipt(
        18,
        plan_path=paths["plan"],
        process_receipt_path=paths["process"],
        log_path=paths["log"],
        summary_path=paths["summary"],
        metrics_path=paths["metrics"],
        repair_receipt_path=paths["r15"],
        prelaunch_infra_receipt_path=paths["prelaunch_infra"],
        r15e_receipt_path=paths["r15e"],
        retry1_launch_occupancy_path=paths["retry1_launch_occupancy"],
        retry1_steady_state_footprint_path=paths["steady_state_footprint"],
    )
    assert receipt["status"] == "ANCHOR_PASS"
    assert receipt["runtime_evidence"]["non_leased_compute_observed"] is False
    assert receipt["runtime_evidence"]["tenant_devices_at_launch"] == [0]


@pytest.mark.parametrize(
    "mutation,match",
    (
        ("unrecorded_launch", "unrecorded compute"),
        ("tenant_process_mismatch", "tenant attribution"),
        ("tenant_leased_device", "leased device index"),
        ("unrecorded_steady_utilization", "unrecorded non-leased"),
    ),
)
def test_attempt18_tenant_attribution_is_explicit_and_consistent(
    tmp_path, monkeypatch, mutation, match
):
    paths = _patch_attempt18_temp_paths(monkeypatch, tmp_path)
    summary, metrics, _ = _attempt18_summary_fixture()
    _write_attempt18_runtime_fixture(paths, summary, metrics)
    tenant_process = {
        "pid": 9002,
        "name": "tenant-job",
        "memory_used_mib": 256,
    }
    launch = json.loads(paths["retry1_launch_occupancy"].read_text(encoding="utf-8"))
    launch["per_device"][0]["utilization_gpu_percent"] = 9
    launch["per_device"][0]["compute_processes"] = [tenant_process]
    launch["non_leased_tenant_occupancy_at_launch"] = [
        {
            "device_index": 0,
            "attribution": "OTHER_TENANT",
            "utilization_gpu_percent": 9,
            "processes": [tenant_process],
        }
    ]
    footprint = json.loads(paths["steady_state_footprint"].read_text(encoding="utf-8"))
    if mutation == "unrecorded_launch":
        launch["non_leased_tenant_occupancy_at_launch"] = []
    elif mutation == "tenant_process_mismatch":
        launch["per_device"][0]["compute_processes"] = [
            {**tenant_process, "pid": 9003}
        ]
    elif mutation == "tenant_leased_device":
        launch["non_leased_tenant_occupancy_at_launch"][0]["device_index"] = 2
    else:
        launch["per_device"][0]["utilization_gpu_percent"] = 0
        launch["per_device"][0]["compute_processes"] = []
        footprint["per_device"][0]["utilization_gpu_percent"] = 8
        footprint["non_leased_observed_utilization_gpu_percent"] = 8
        launch["non_leased_tenant_occupancy_at_launch"] = []
    paths["retry1_launch_occupancy"].write_text(json.dumps(launch), encoding="utf-8")
    paths["steady_state_footprint"].write_text(json.dumps(footprint), encoding="utf-8")
    with pytest.raises(RuntimeError, match=match):
        anchor_receipts.build_post_r1_attempt_receipt(
            18,
            plan_path=paths["plan"],
            process_receipt_path=paths["process"],
            log_path=paths["log"],
            summary_path=paths["summary"],
            metrics_path=paths["metrics"],
            repair_receipt_path=paths["r15"],
            prelaunch_infra_receipt_path=paths["prelaunch_infra"],
            r15e_receipt_path=paths["r15e"],
            retry1_launch_occupancy_path=paths["retry1_launch_occupancy"],
            retry1_steady_state_footprint_path=paths["steady_state_footprint"],
        )


@pytest.mark.parametrize(
    "mutation,match",
    (
        ("kit_active_non_leased", "Kit activity"),
        ("oversized_context", "exceeds the non-leased footprint threshold"),
    ),
)
def test_attempt18_non_leased_kit_and_context_limits_fail_fast(
    tmp_path, monkeypatch, mutation, match
):
    paths = _patch_attempt18_temp_paths(monkeypatch, tmp_path)
    summary, metrics, _ = _attempt18_summary_fixture()
    _write_attempt18_runtime_fixture(paths, summary, metrics)
    footprint = json.loads(paths["steady_state_footprint"].read_text(encoding="utf-8"))
    if mutation == "kit_active_non_leased":
        footprint["kit_active_physical_devices"] = [0, 2]
    else:
        footprint["per_device"][0]["attempt_process_memory_mib"] = 1025
        footprint["max_non_leased_attempt_process_memory_mib"] = 1025
    paths["steady_state_footprint"].write_text(json.dumps(footprint), encoding="utf-8")
    with pytest.raises(RuntimeError, match=match):
        anchor_receipts.build_post_r1_attempt_receipt(
            18,
            plan_path=paths["plan"],
            process_receipt_path=paths["process"],
            log_path=paths["log"],
            summary_path=paths["summary"],
            metrics_path=paths["metrics"],
            repair_receipt_path=paths["r15"],
            prelaunch_infra_receipt_path=paths["prelaunch_infra"],
            r15e_receipt_path=paths["r15e"],
            retry1_launch_occupancy_path=paths["retry1_launch_occupancy"],
            retry1_steady_state_footprint_path=paths["steady_state_footprint"],
        )


def test_attempt19_probe_invalid_receipt_binds_immutable_artifacts_and_honest_absence():
    receipt_path = anchor_runner.EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT19_RECEIPT.json"
    capture_failure_path = (
        anchor_runner.EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT19_CAPTURE_FAILURE.json"
    )
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

    assert receipt["status"] == "PROBE_INVALID"
    assert _sha256(receipt_path) == "4f92eba02f157158803f3df7b031e865bdefccc6a5d9ea969e1cf43eaaa536cd"
    assert _sha256(capture_failure_path) == "6fab55d01f9e0763167121c48fb54a16e5e4cf4c0eb970bed1a40c837f0b70bc"
    for artifact_name, expected_sha256 in (
        ("plan", "cf23ee03ec0c40e77582ec724d8c6d8855cebcd40791edb7c8d11e75d9800748"),
        ("launch_occupancy", "035303242c307856a54bb3eabe09c391d75cca936f9a437946af4f938e2d08b8"),
        ("log", "2614844d86965bf648874d06360100e4997f8ecc49bf6d1a730dc7f0272bcbdc"),
    ):
        artifact = receipt["artifacts"][artifact_name]
        assert _sha256(ROOT / artifact["path"]) == expected_sha256
        assert artifact["sha256"] == expected_sha256
    assert receipt["artifacts"].get("process_receipt") is None
    assert receipt["artifacts"].get("summary") is None
    assert receipt["artifacts"].get("metrics") is None
    assert receipt["artifacts"].get("steady_state_footprint") is None
    assert receipt["termination"]["stop_signal_timestamp_hkt"] is None
    assert receipt["termination"]["stop_signal_timestamp_status"] == "NOT_RECORDED"


def _attempt20_replay_steady_evidence(fixture):
    plan = {"attempt": 20, "status": "READY", "plan_sha256": "attempt20-test-plan"}
    plan_artifact = {
        "path": "scriptsFORhuman/pull_v0/PULL_V0_P1_PUSH_ANCHOR_ATTEMPT20_PLAN.json",
        "sha256": "attempt20-test-artifact",
        "plan_sha256": plan["plan_sha256"],
    }
    evidence = copy.deepcopy(fixture["steady_json"])
    evidence["schema_version"] = "pull_v0_p1_attempt20_steady_state_footprint_v1"
    evidence["attempt"] = 20
    evidence["plan"] = plan_artifact
    evidence["non_leased_observed_utilization_gpu_percent"] = 0.0
    attempt20_eval_dir = (
        attempt19_gpu_evidence.ROOT
        / "logs_eval/a2_piper_pull_v0/p1_push_anchor/attempt20/eval"
    )
    process_identity = evidence["process_identity"]
    process_identity["output_namespace"] = str(attempt20_eval_dir.parent)
    process_identity["eval_output_dir"] = str(attempt20_eval_dir)
    for snapshot in (process_identity["eval"], process_identity["ancestry_chain"][0]):
        snapshot["cmdline"][-1] = f"eval_output_dir={attempt20_eval_dir}"
    for device in evidence["per_device"]:
        index = device["index"]
        context = next(item for item in device["pmon_processes"] if item["pid"] == fixture["process_pid"])
        device["utilization_gpu_percent"] = 17.0 if index == 2 else 0.0
        device["compute_processes"] = (
            [{"pid": fixture["process_pid"], "name": "attempt20", "memory_used_mib": 3083.0}]
            if index == 2
            else []
        )
        context.update(
            {
                "type": "C+G" if index in (2, 3) else "C",
                "fb_memory_mib": 3083.0 if index == 2 else (168.0 if index == 0 else (140.0 if index == 3 else 136.0)),
                "sm_util_percent": 16.0 if index == 2 else None,
                "sm_util_percent_state": "REPORTED" if index == 2 else "NOT_REPORTED",
                "memory_util_percent": 0.0 if index == 2 else None,
                "memory_util_percent_state": "REPORTED" if index == 2 else "NOT_REPORTED",
            }
        )
        device["attempt_process_memory_mib"] = context["fb_memory_mib"]
        device["context_classification"] = (
            "AUTHORIZED_COMPUTE"
            if index == 2
            else "AUTHORIZED_INACTIVE_VULKAN_ENUMERATION"
        )
    evidence["max_non_leased_attempt_process_memory_mib"] = 168.0
    return plan, plan_artifact, evidence


def _validate_attempt20_replay(fixture, evidence):
    plan, plan_artifact, _ = _attempt20_replay_steady_evidence(fixture)
    return attempt19_gpu_evidence.validate_steady_evidence(
        evidence,
        plan=plan,
        plan_artifact=plan_artifact,
        log_text=fixture["log"].read_text(encoding="utf-8"),
        required_pid=fixture["process_pid"],
        attempt=20,
    )


def test_attempt20_replays_attempt19_low_memory_contexts_without_rewriting_source_metrics(
    tmp_path, monkeypatch
):
    fixture = _write_attempt19_resource_fixture(tmp_path, monkeypatch)
    _, _, evidence = _attempt20_replay_steady_evidence(fixture)

    result = _validate_attempt20_replay(fixture, evidence)

    assert result["selected_compute_physical_device"] == 2
    for device in evidence["per_device"]:
        context = next(item for item in device["pmon_processes"] if item["pid"] == fixture["process_pid"])
        if device["index"] == 2:
            assert device["context_classification"] == "AUTHORIZED_COMPUTE"
            assert context["type"] == "C+G"
            assert context["fb_memory_mib"] == 3083.0
            assert device["compute_processes"][0]["pid"] == fixture["process_pid"]
            assert device["utilization_gpu_percent"] == 17.0
        else:
            assert device["context_classification"] == "AUTHORIZED_INACTIVE_VULKAN_ENUMERATION"
            assert context["sm_util_percent"] is None
            assert context["sm_util_percent_state"] == "NOT_REPORTED"
            assert context["memory_util_percent"] is None
            assert context["memory_util_percent_state"] == "NOT_REPORTED"
            assert device["utilization_gpu_percent"] == 0.0


@pytest.mark.parametrize("mutation", ("sm", "memory", "utilization", "framebuffer"))
def test_attempt20_rejects_nonselected_attempt_activity_without_other_tenant_attribution(
    tmp_path, monkeypatch, mutation
):
    fixture = _write_attempt19_resource_fixture(tmp_path, monkeypatch)
    _, _, evidence = _attempt20_replay_steady_evidence(fixture)
    gpu0 = next(device for device in evidence["per_device"] if device["index"] == 0)
    context = next(item for item in gpu0["pmon_processes"] if item["pid"] == fixture["process_pid"])
    if mutation == "sm":
        context["sm_util_percent"] = 1.0
        context["sm_util_percent_state"] = "REPORTED"
    elif mutation == "memory":
        context["memory_util_percent"] = 1.0
        context["memory_util_percent_state"] = "REPORTED"
    elif mutation == "utilization":
        gpu0["utilization_gpu_percent"] = 1.0
        evidence["non_leased_observed_utilization_gpu_percent"] = 1.0
    else:
        context["fb_memory_mib"] = 1025.0
        gpu0["attempt_process_memory_mib"] = 1025.0
        evidence["max_non_leased_attempt_process_memory_mib"] = 1025.0
    with pytest.raises(RuntimeError):
        _validate_attempt20_replay(fixture, evidence)


def test_attempt20_allows_nonselected_utilization_only_for_separate_other_tenant(
    tmp_path, monkeypatch
):
    fixture = _write_attempt19_resource_fixture(tmp_path, monkeypatch)
    _, _, evidence = _attempt20_replay_steady_evidence(fixture)
    gpu0 = next(device for device in evidence["per_device"] if device["index"] == 0)
    tenant_pid = 9876
    tenant_process = {"pid": tenant_pid, "name": "other-tenant", "memory_used_mib": 32.0}
    tenant_context = {
        "gpu_index": 0,
        "pid": tenant_pid,
        "type": "C",
        "sm_util_percent": 1.0,
        "sm_util_percent_state": "REPORTED",
        "memory_util_percent": 1.0,
        "memory_util_percent_state": "REPORTED",
        "fb_memory_mib": 32.0,
        "fb_memory_mib_state": "REPORTED",
        "command": "other-tenant",
        "source": attempt19_gpu_evidence.PMON_SOURCE,
    }
    gpu0["utilization_gpu_percent"] = 1.0
    gpu0["compute_processes"].append(tenant_process)
    gpu0["pmon_processes"].append(tenant_context)
    evidence["non_leased_observed_utilization_gpu_percent"] = 1.0
    evidence["non_leased_tenant_occupancy_at_steady_state"] = [
        {
            "device_index": 0,
            "attribution": "OTHER_TENANT",
            "utilization_gpu_percent": 1.0,
            "processes": [tenant_process],
            "pmon_processes": [tenant_context],
        }
    ]

    result = _validate_attempt20_replay(fixture, evidence)

    assert result["tenant_devices_at_steady_state"] == [0]
    assert tenant_pid != evidence["attempt_pid"]
    assert evidence["per_device"][0]["context_classification"] == "AUTHORIZED_INACTIVE_VULKAN_ENUMERATION"


def test_attempt20_paths_and_freeze_guard_cannot_reuse_attempt19_plan(monkeypatch):
    attempt19_path = anchor_runner._attempt_plan_path(19)
    attempt20_path = anchor_runner._attempt_plan_path(20)

    assert attempt19_path.name.endswith("ATTEMPT19_PLAN.json")
    assert attempt20_path.name.endswith("ATTEMPT20_PLAN.json")
    assert anchor_runner._attempt_output_root(20).name == "attempt20"
    assert anchor_runner._launch_occupancy_path(20) == anchor_runner.ATTEMPT20_LAUNCH_OCCUPANCY_PATH
    monkeypatch.setattr(anchor_runner, "_attempt20_preparation_artifact_paths", lambda: (attempt19_path,))
    with pytest.raises(RuntimeError, match="refuses to reuse or overwrite"):
        anchor_runner._assert_attempt20_preparation_namespace_clear()


def test_gpu_evidence_refuses_to_overwrite_existing_canonical_output(tmp_path):
    existing = tmp_path / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT20_LAUNCH_OCCUPANCY.json"
    existing.write_text("immutable", encoding="utf-8")

    with pytest.raises(RuntimeError, match="Refusing to overwrite"):
        attempt19_gpu_evidence._require_output_path(
            existing,
            existing,
            "launch occupancy",
            attempt=20,
        )


def test_attempt20_signal_lifecycle_seals_process_receipt_without_fabricated_sigkill_timestamp(
    tmp_path, monkeypatch
):
    sent_signals = []
    child = SimpleNamespace(
        poll=lambda: None,
        send_signal=lambda signum: sent_signals.append(signum),
        wait=lambda timeout=None: -int(anchor_runner.signal.SIGINT),
    )
    signal_event = anchor_runner._LifecycleSignal(
        int(anchor_runner.signal.SIGINT), source="TEST_SYNTHETIC_SIGINT"
    )
    returncode, lifecycle = anchor_runner._stop_child_after_lifecycle_signal(child, signal_event)
    plan = {
        "env": {},
        "argv": ["synthetic-eval"],
        "plan_sha256": "attempt20-signal-plan",
        "repair_receipt": {
            "path": "scriptsFORhuman/pull_v0/PULL_V0_REPAIR_R17_RECEIPT.json",
            "sha256": "r17-test-sha",
            "stale_candidate_id": "r17-test-candidate",
        },
    }
    monkeypatch.setattr(anchor_runner, "ROOT", tmp_path)
    monkeypatch.setattr(
        anchor_runner,
        "_attempt_plan_path",
        lambda _attempt: tmp_path / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT20_PLAN.json",
    )
    monkeypatch.setattr(anchor_runner, "prepare", lambda *_args, **_kwargs: plan)
    monkeypatch.setattr(anchor_runner, "_validate_attempt_launch_occupancy", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        anchor_runner,
        "_popen_run_with_lifecycle",
        lambda *_args, **_kwargs: (4321, returncode, lifecycle),
    )

    result = anchor_runner.run(20, Path("r17.json"), "r17-test-sha")
    receipt = json.loads(
        (anchor_runner._attempt_output_root(20) / "process_receipt.json").read_text(encoding="utf-8")
    )

    assert result == 128 + int(anchor_runner.signal.SIGINT)
    assert sent_signals == [int(anchor_runner.signal.SIGINT)]
    assert receipt["lifecycle_signal"]["received"] is True
    assert receipt["lifecycle_signal"]["timestamp_status"] == "RECORDED"
    assert receipt["lifecycle_signal"]["sigkill_sent"] is False
    assert receipt["lifecycle_signal"]["sigkill_timestamp_hkt"] is None
    assert receipt["lifecycle_signal"]["child_wait_timeout_seconds"] == 600.0
