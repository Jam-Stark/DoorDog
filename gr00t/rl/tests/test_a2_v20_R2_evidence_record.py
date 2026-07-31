"""CPU-only Phase III evidence-record tests."""

from __future__ import annotations

import hashlib
import json
import importlib.abc
import importlib.machinery
import sys
import types
from pathlib import Path

import torch

import pytest

from gr00t.rl.envs.door.a2_v20_r2_evidence import (
    a2_v20_r2_canonical_json_bytes,
    a2_v20_r2_finalize_record_id,
    a2_v20_r2_trace_jsonl_bytes,
    a2_v20_r2_validate_trace_rows,
)
from scriptsFORhuman.v20_R2.a2_piper_v20_R2_record_adjudicator import (
    R2RecordAdjudicationError,
    adjudicate_record_set,
)

def row(run_uuid, env_id, step, terminal=False):
    return {
        "schema": "a2_piper_v20_R2_step_trace_v1", "run_uuid": run_uuid, "env_id": env_id,
        "episode_ordinal": 0, "step_index": step, "batch_index": step, "stage": 3, "curriculum_phase": "soft",
        "root_se2": [0.0, 0.0, 0.0], "door_hinge_position_rad": 0.2, "door_hinge_velocity_radps": 0.1,
        "hold_valid": True, "bilateral": True, "coasting": False, "over_force": False, "send_ready": False,
        "pre_send_crossing_event": False, "root_crossing_event": False, "release_event": False, "root_x_rel_m": -0.01,
        "arm_raw_action_6d": [0.0] * 6, "taskspace_active": True, "positive_arm_tangent_mps": 0.1,
        "positive_base_tangent_mps": 0.2, "arm_tangent_share": 1.0 / 3.0, "arc_position_error_m": 0.001,
        "arc_orientation_error_rad": 0.002, "along_handle_slip_m": 0.003, "orthogonal_arc_residual_m": 0.004,
        "reward_components_scaled": {"r": 0.1}, "terminal": terminal, "terminal_reason": "complete" if terminal else "NON_TERMINAL",
    }

def metric():
    return {"state": "DEFINED", "sample_count": 1, "value": 1.0}

def distribution():
    return {"state": "DEFINED", "sample_count": 1, "p10": 1.0, "p50": 1.0, "p95": 1.0, "max": 1.0}

def record(tmp_path, run_uuid="run-a", env_id=0, rows=None):
    rows = [row(run_uuid, env_id, 0), row(run_uuid, env_id, 1, True)] if rows is None else rows
    trace = tmp_path / f"{run_uuid}-{env_id}.jsonl"
    trace.write_bytes(a2_v20_r2_trace_jsonl_bytes(rows))
    provenance = {
        "scientific_plan_id": "base_v20_R1_policy_behavior_v1", "admission_plan_id": "base_v20_R2_admission_execution_v1",
        "source_lock_sha256": "a" * 64, "plan_sha256": "b" * 64, "r1_plan_sha256": "c" * 64,
        "b0_json_sha256": "d" * 64, "b0_csv_sha256": "e" * 64, "urdf_path": "robot.urdf", "urdf_sha256": "f" * 64,
        "checkpoint_path": "checkpoint.pt", "checkpoint_sha256": "1" * 64, "checkpoint_step": 2000,
        "source_config_path": "source.yaml", "source_config_sha256": "2" * 64, "resolved_config_sha256": "3" * 64,
        "runtime_config_sha256": "4" * 64, "command_sha256": "5" * 64, "git_commit": "6" * 40,
        "run_uuid": run_uuid, "seed": 16, "env_id": env_id, "episode_ordinal": 0,
    }
    without_id = {
        "schema": "a2_piper_v20_R2_episode_record_v1", "provenance": provenance,
        "topology": {"first_episode_only": True, "single_process": True, "physical_gpu": 0},
        "scenario": {}, "factor": {}, "phase": {}, "task": {"terminal_reason": "complete"}, "safety": {}, "send": {},
        "task_space": {"arc": distribution()}, "smoothness": {"jerk": distribution()}, "income": {"reward_component_sums": {"r": metric()}}, "release": {},
        "trace": {"path": trace.name, "sha256": hashlib.sha256(trace.read_bytes()).hexdigest(), "row_count": len(rows), "first_step": 0, "last_step": len(rows) - 1, "terminal_row_index": len(rows) - 1},
        "accumulator_audit": {"reward_steps": len(rows)},
    }
    out = dict(without_id)
    out["record_id"] = a2_v20_r2_finalize_record_id(without_id)
    return out

def record_set(tmp_path, records):
    path = tmp_path / "record-set.json"
    run_uuid = records[0]["provenance"]["run_uuid"] if records else "run-a"
    path.write_bytes(a2_v20_r2_canonical_json_bytes({"schema": "a2_piper_base_v20_R2_record_set_v1", "producer_state": "RECORD_SET_COMPLETE", "run_uuid": run_uuid, "records": records, "record_count": len(records)}))
    return path

def _actual_finalizer_record(
    tmp_path, run_uuid="actual-run", env_id=0, *, runtime_context=False
):
    tmp_path.mkdir(parents=True, exist_ok=True)
    class _DummyMeta(type):
        def __getattr__(cls, name):
            return cls

    class _Dummy(metaclass=_DummyMeta):
        def __init__(self, *args, **kwargs):
            pass
        def __call__(self, *args, **kwargs):
            return _Dummy()
        def __getattr__(self, name):
            return _Dummy
        def __mro_entries__(self, bases):
            return (object,)
        def __iter__(self):
            return iter(())
        def __bool__(self):
            return False

    class _Loader(importlib.abc.Loader):
        def create_module(self, spec):
            module = types.ModuleType(spec.name)
            module.__file__ = "/tmp/r2_cpu_stub.py"
            module.__path__ = []
            module.__getattr__ = lambda name: (_Dummy if not name.startswith("__") else (_ for _ in ()).throw(AttributeError(name)))
            return module
        def exec_module(self, module):
            return None

    class _Finder(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path, target=None):
            if fullname.startswith(("isaaclab.", "omni.", "isaacsim.", "pxr.")) or fullname in {"isaaclab", "omni", "isaacsim", "pxr"}:
                return importlib.machinery.ModuleSpec(fullname, _Loader(), is_package=True)
            return None

    finder = _Finder()
    sys.meta_path.insert(0, finder)
    try:
        from gr00t.rl.envs.door.door_open_a2_base import DoorPregrasp
    except Exception as exc:
        raise AssertionError(f"actual Door class import blocker under primary interpreter: {type(exc).__name__}: {exc}") from exc
    finally:
        sys.meta_path.remove(finder)

    obj = DoorPregrasp.__new__(DoorPregrasp)
    device = torch.device("cpu")
    obj._a2_v20_r2_evidence_enabled = True
    obj.num_envs = 1
    obj.device = device
    obj.dt = 0.02
    obj.common_step_counter = 2
    obj.num_stages = 6
    obj.stage_buf = torch.tensor([3], dtype=torch.long)
    obj.actual_time_in_stage_buf = torch.tensor([2], dtype=torch.long)
    obj._a2_v20_r2_reset_origin_stage = torch.tensor([-1], dtype=torch.long)
    obj._a2_v20_r2_reset_snapshot_index = torch.tensor([-1], dtype=torch.long)
    obj._a2_v20_r1_schedule_last_step = -1
    obj._r2_trace_rows = [[row(run_uuid, env_id, 0), row(run_uuid, env_id, 1, True)]]
    obj._r2_terminal_reason = ["complete"]
    obj._r2_terminal_step = torch.tensor([1], dtype=torch.long)
    obj._r2_episode_ordinal = torch.tensor([0], dtype=torch.long)
    obj._r2_trace_path_by_env = [str(tmp_path / "actual-trace.jsonl")]
    obj._a2_v20_r2_record_set_staging_path = str(tmp_path / "actual-records.jsonl")
    obj._a2_v20_r2_trace_root = None
    obj._a2_v20_r2_provenance = {
        "run_uuid": run_uuid, "scientific_plan_id": "base_v20_R1_policy_behavior_v1", "admission_plan_id": "base_v20_R2_admission_execution_v1",
        "source_lock_sha256": "a" * 64, "plan_sha256": "b" * 64, "r1_plan_sha256": "c" * 64, "b0_json_sha256": "d" * 64, "b0_csv_sha256": "e" * 64,
        "urdf_path": "robot.urdf", "urdf_sha256": "f" * 64, "checkpoint_path": "checkpoint.pt", "checkpoint_sha256": "1" * 64, "checkpoint_step": 2000,
        "source_config_path": "source.yaml", "source_config_sha256": "2" * 64, "resolved_config_sha256": "3" * 64, "runtime_config_sha256": "4" * 64, "command_sha256": "5" * 64,
        "git_commit": "6" * 40, "seed": 16, "env_id": env_id, "episode_ordinal": 0,
        "topology": {"name": "canonical16", "environment_count": 1, "expected_episode_count": 1, "first_episode_only": True, "single_process": True, "physical_gpu": 0, "render": False},
        "scenario": {"scenario_id": "canonical", "door_open_lr": 1, "door_width_m": 0.9, "door_height_m": 2.0, "handle_height_m": 1.0, "handle_edge_distance_m": 0.1, "door_mass_kg": 10.0, "hinge_damping": 0.1, "hinge_stiffness": 0.0, "hinge_max_force_nm": 20.0, "handle_damping": 0.1, "handle_stiffness": 1.0, "handle_max_force_nm": 20.0, "initial_root_pose_se2": [0.0, 0.0, 0.0]},
        "factor": {"group": "G1", "send_curriculum": False, "economics": True, "arm_tie": True, "curriculum_phase": "soft", "theta_send_rad": 0.9, "root_x_margin_m": 0.03, "arm_tangent_scale": 3.5, "arc_tracking_scale": 0.85},
        "phase": {"opening_start_step": 0, "opening_start_batch": 0, "terminal_step": 1, "terminal_batch": 2, "max_stage": 5, "stage_at_terminal": 3, "time_in_terminal_stage": 0.04, "reset_origin": "initial", "reset_stage": None, "reset_snapshot_index": None, "schedule_transition_observed": False},
    }
    if runtime_context:
        obj._a2_v20_r2_provenance.pop("scenario")
        obj._a2_v20_r2_provenance.pop("factor")
        obj._a2_v20_r2_provenance.pop("phase")
        obj.config = {"a2_v20_R2_group": "G5"}
        obj._a2_v20_r1_curriculum_phase = "soft"
        obj._get_a2_v20_r1_send_curriculum_enabled = lambda: True
        obj._get_a2_v20_traversal_economics_enabled = lambda: True
        obj._get_a2_v20_arm_tie_enabled = lambda: True
        obj._get_a2_v20_send_hinge_threshold = lambda: 0.9
        obj._get_a2_v20_pre_send_root_x_margin = lambda: 0.03
        obj._get_a2_v20_arm_tangent_carry_scale = lambda: 3.5
        obj._get_a2_v20_handle_arc_tracking_scale = lambda: 0.85
        obj.door_open_lr = torch.tensor([1.0])
        obj.door_width = torch.tensor([0.9])
        obj.door_height = torch.tensor([2.0])
        obj.door_handle_height = torch.tensor([1.0])
        obj.door_handle_width = torch.tensor([0.1])
        obj.door_weight = torch.tensor([10.0])
        obj.door_hinge_drive_damping = torch.tensor([50.0])
        obj.door_hinge_drive_stiffness = torch.tensor([0.0])
        obj.door_hinge_drive_max_force = torch.tensor([20.0])
        obj.door_handle_drive_damping = torch.tensor([0.5])
        obj.door_handle_drive_stiffness = torch.tensor([50.0])
        obj.door_handle_drive_max_force = torch.tensor([20.0])
        obj.target_robot_root_states = torch.tensor(
            [[0.0, 0.0, 0.8, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]]
        )
        obj.env_origins = torch.zeros((1, 3))
    full_names = ("_r2_hinge_velocity_samples", "_r2_hinge_accel_samples", "_r2_hinge_jerk_samples", "_r2_arm_action_rate_samples", "_r2_arm_action_jerk_samples", "_r2_arm_share_samples", "_r2_positive_arm_samples", "_r2_positive_base_samples", "_r2_arc_position_samples", "_r2_arc_orientation_samples", "_r2_along_slip_samples", "_r2_orthogonal_residual_samples")
    mask_names = ("_r2_hinge_velocity_mask", "_r2_hinge_accel_mask", "_r2_hinge_jerk_mask", "_r2_arm_action_rate_mask", "_r2_arm_action_jerk_mask", "_r2_arm_share_mask", "_r2_positive_arm_mask", "_r2_positive_base_mask", "_r2_arc_position_mask", "_r2_arc_orientation_mask", "_r2_along_slip_mask", "_r2_orthogonal_residual_mask")
    for name in full_names:
        setattr(obj, name, torch.ones((1, 2), dtype=torch.float32))
    for name in mask_names:
        setattr(obj, name, torch.ones((1, 2), dtype=torch.bool))
    for name in ("_r2_positive_arm_integral", "_r2_positive_base_integral", "_r2_positive_total_income", "_r2_positive_a_income", "_r2_body_contact_force_max", "_r2_held_hinge_max", "_r2_opening_slip_max"):
        setattr(obj, name, torch.ones(1, dtype=torch.float32))
    obj._r2_reward_component_sums = {"r": torch.ones(1, dtype=torch.float32)}
    obj._r2_reward_steps = torch.tensor([2], dtype=torch.long)
    obj._r2_warmup_exclusions = torch.zeros(1, dtype=torch.long)
    obj._a2_v20_first_send_ready_step = torch.tensor([-1], dtype=torch.long)
    obj._a2_v20_first_root_crossing_step = torch.tensor([0], dtype=torch.long)
    obj._a2_v20_first_pre_send_crossing_step = torch.tensor([-1], dtype=torch.long)
    obj._a2_v20_send_ready = torch.tensor([False])
    obj._a2_crossing_while_holding = torch.tensor([True])
    obj._a2_release_event_valid = torch.tensor([False])
    obj._a2_post_release_body_contact = torch.tensor([False])
    obj._a2_post_release_body_force_max = torch.zeros(1)
    obj._a2_door_body_contact_event_emitted = torch.zeros(1)
    obj._a2_v20_hinge_at_first_root_crossing = torch.tensor([0.2])
    obj._a2_v20_root_x_at_first_crossing = torch.tensor([0.01])
    obj._a2_v20_max_pre_send_displacement_se2 = torch.zeros((1, 3))
    obj._a2_hinge_at_release = torch.full((1,), float("nan"))
    obj._a2_root_x_at_release = torch.full((1,), float("nan"))
    obj._a2_v20_r2_snapshot_rejection_counts = torch.zeros(14, dtype=torch.long)
    obj._r2_pre_cross_step_count = torch.ones(1, dtype=torch.long)
    obj._r2_bilateral_count = torch.ones(1, dtype=torch.long)
    obj._r2_coasting_count = torch.zeros(1, dtype=torch.long)
    obj._r2_over_force_count = torch.zeros(1, dtype=torch.long)
    obj._r2_finalized = torch.zeros(1, dtype=torch.bool)
    if runtime_context:
        terminal_ids = torch.tensor([0], dtype=torch.long)
        obj._finalize_a2_v20_r2_terminal_episodes(terminal_ids)
        trace_rows = obj._r2_trace_rows[0]
        trace_path = obj._r2_trace_path_by_env[0]
        obj._reset_a2_v20_r2_evidence_buffers(terminal_ids)
        assert obj._r2_finalized.tolist() == [True]
        assert obj._r2_trace_rows[0] is trace_rows
        assert obj._r2_trace_path_by_env[0] == trace_path
        obj._capture_a2_v20_r2_step_trace()
        obj._finalize_a2_v20_r2_terminal_episodes(terminal_ids)
        staging_lines = (tmp_path / "actual-records.jsonl").read_text().splitlines()
        assert len(staging_lines) == 1
        record = json.loads(staging_lines[0])
    else:
        record = obj.finalize_a2_v20_r2_episode_record(0)
    staged = json.loads((tmp_path / "actual-records.jsonl").read_text().splitlines()[0])
    assert staged["record_id"] == record["record_id"]
    return record

def test_trace_contiguous_terminal_last():
    rows = [row("run", 0, 0), row("run", 0, 1, True)]
    assert a2_v20_r2_validate_trace_rows(rows, run_uuid="run", env_id=0, terminal_reason="complete")["row_count"] == 2
    rows[1]["step_index"] = 3
    with pytest.raises(ValueError, match="contiguous"):
        a2_v20_r2_validate_trace_rows(rows, run_uuid="run", env_id=0, terminal_reason="complete")

def test_trace_rejects_scalar_step_and_early_terminal():
    rows = [row("run", 0, 0, True), row("run", 0, 1, True)]
    with pytest.raises(ValueError):
        a2_v20_r2_validate_trace_rows(rows, run_uuid="run", env_id=0, terminal_reason="complete")
    rows = [row("run", 0, 0), row("run", 0, 1, True)]
    rows[0]["step_index"] = 0.0
    with pytest.raises(ValueError):
        a2_v20_r2_validate_trace_rows(rows, run_uuid="run", env_id=0, terminal_reason="complete")

def test_under_specified_handcrafted_record_is_rejected(tmp_path):
    rec = record(tmp_path)
    with pytest.raises(R2RecordAdjudicationError, match="schema"):
        adjudicate_record_set(record_set(tmp_path, [rec]))


def test_actual_finalizer_output_passes_real_adjudicator(tmp_path):
    rec = _actual_finalizer_record(tmp_path)
    result = adjudicate_record_set(record_set(tmp_path, [rec]))
    assert result["adjudicator_state"] == "STRICT_VALID"
    changed = dict(rec)
    changed["task"] = dict(rec["task"])
    changed["task"]["terminal_reason"] = "episode_timeout"
    assert rec["record_id"] != a2_v20_r2_finalize_record_id({k: v for k, v in changed.items() if k != "record_id"})


def test_terminal_finalizer_derives_runtime_context(tmp_path):
    rec = _actual_finalizer_record(tmp_path, runtime_context=True)
    assert rec["scenario"]["door_open_lr"] == 1
    scenario_without_id = {
        key: value for key, value in rec["scenario"].items() if key != "scenario_id"
    }
    assert rec["scenario"]["scenario_id"] == hashlib.sha256(
        a2_v20_r2_canonical_json_bytes(scenario_without_id)
    ).hexdigest()
    assert rec["factor"] == {
        "group": "G5",
        "send_curriculum": True,
        "economics": True,
        "arm_tie": True,
        "curriculum_phase": "soft",
        "theta_send_rad": 0.9,
        "root_x_margin_m": 0.03,
        "arm_tangent_scale": 3.5,
        "arc_tracking_scale": 0.85,
    }
    assert adjudicate_record_set(record_set(tmp_path, [rec]))["adjudicator_state"] == "STRICT_VALID"


def test_adjudicator_rejects_hash_duplicate_and_forbidden(tmp_path):
    first = _actual_finalizer_record(tmp_path, "run-a", 0)
    with pytest.raises(R2RecordAdjudicationError, match="duplicate"):
        adjudicate_record_set(record_set(tmp_path, [first, first]))
    trace = Path(first["trace"]["path"])
    trace.write_bytes(trace.read_bytes() + b"\n")
    with pytest.raises(R2RecordAdjudicationError, match="SHA-256"):
        adjudicate_record_set(record_set(tmp_path, [first]))
    forbidden = _actual_finalizer_record(tmp_path / "forbidden", "run-b", 0)
    forbidden["status"] = "PASS"
    with pytest.raises(R2RecordAdjudicationError, match="schema|forbidden"):
        adjudicate_record_set(record_set(tmp_path / "forbidden", [forbidden]))


def test_adjudicator_rejects_missing_audit_denominator_and_generic_na(tmp_path):
    rec = _actual_finalizer_record(tmp_path, "run-c", 0)
    missing = dict(rec)
    missing["accumulator_audit"] = dict(rec["accumulator_audit"])
    missing["accumulator_audit"].pop("pre_cross_steps")
    missing["record_id"] = a2_v20_r2_finalize_record_id({k: v for k, v in missing.items() if k != "record_id"})
    with pytest.raises(R2RecordAdjudicationError, match="schema"):
        adjudicate_record_set(record_set(tmp_path, [missing]))
    generic = _actual_finalizer_record(tmp_path / "na", "run-d", 0)
    generic["task_space"] = dict(generic["task_space"])
    generic["task_space"]["arm_tangent_share"] = dict(generic["task_space"]["arm_tangent_share"])
    generic["task_space"]["arm_tangent_share"]["state"] = "N/A"
    generic["record_id"] = a2_v20_r2_finalize_record_id({k: v for k, v in generic.items() if k != "record_id"})
    with pytest.raises(R2RecordAdjudicationError, match="schema"):
        adjudicate_record_set(record_set(tmp_path / "na", [generic]))
