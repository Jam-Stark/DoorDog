"""CPU-only v21-B arm telemetry contracts."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
import torch

from gr00t.rl.envs.door.a2_v21b_evidence import (
    V21B_AUTHORITY_LABEL,
    V21B_BOUNDARY_CREATED,
    V21B_BOUNDARY_ESTIMATE_ONLY_UNCORROBORATED,
    V21B_BOUNDARY_SATURATED_EVERYWHERE,
    V21B_CENSUS_RIGHT_CENSORED,
    a2_v21b_accumulate_arm_step,
    a2_v21b_adjudicate_dv2,
    a2_v21b_arm_pd_effort_estimates,
    a2_v21b_arm_tracking_error,
    a2_v21b_build_step_evidence,
    a2_v21b_build_census_frames_from_episode,
    a2_v21b_export_census_frames,
    a2_v21b_census_from_unclipped,
    a2_v21b_finalize_arm_episode,
    a2_v21b_init_arm_episode_accumulator,
    a2_v21b_reset_arm_episode_accumulator,
    a2_v21b_validate_evidence_record,
)
from scriptsFORhuman.v21B._v21b_common import (
    V21BError,
    V21B_PLAN_ID,
    resolve_v21b_trace_run_uuid,
)
try:
    from gr00t.rl.envs.door.door_open_a2_base import DoorPregrasp
except ModuleNotFoundError:
    DoorPregrasp = None


def _step(n=2, *, effort_limit=100.0):
    dtype = torch.float32
    q = torch.zeros((n, 6), dtype=dtype)
    qdot = torch.full((n, 6), 0.1, dtype=dtype)
    qtarget = torch.full((n, 6), 1.0, dtype=dtype)
    kp = torch.full((n, 6), 100.0, dtype=dtype)
    kd = torch.full((n, 6), 1.0, dtype=dtype)
    limit = torch.full((n, 6), effort_limit, dtype=dtype)
    pd = a2_v21b_arm_pd_effort_estimates(q, qdot, qtarget, kp, kd, limit)
    tracking = a2_v21b_arm_tracking_error(qtarget, q, qdot)
    return a2_v21b_build_step_evidence(pd_estimates=pd, tracking=tracking, valid_mask=torch.ones(n, dtype=torch.bool))


def _lifecycle_env(num_envs=2, *, max_episode_length=3):
    if DoorPregrasp is None:
        pytest.skip("DoorPregrasp lifecycle harness requires IsaacLab pxr bindings")
    env = object.__new__(DoorPregrasp)
    env.device = torch.device("cpu")
    env.num_envs = num_envs
    env.max_episode_length = max_episode_length
    env.episode_length_buf = torch.ones(num_envs, dtype=torch.long)
    env._r2_finalized = torch.zeros(num_envs, dtype=torch.bool)
    env._a2_v21b_arm_evidence_enabled = True
    env._a2_v21b_arm_joint_ids = torch.arange(6, dtype=torch.long)
    env._a2_v21b_arm_evidence = a2_v21b_init_arm_episode_accumulator(
        num_envs, max_episode_length=max_episode_length
    )
    env._a2_v21b_arm_effort_limit_6d = torch.full((num_envs, 6), 100.0)
    env._a2_v21b_arm_first_joint_ge_098 = torch.full(
        (num_envs,), -1, dtype=torch.long
    )
    env._a2_v21b_last_implicit_computed_effort_6d = torch.zeros(num_envs, 6)
    env._a2_v21b_last_implicit_applied_effort_6d = torch.zeros(num_envs, 6)
    env._a2_v21b_last_implicit_crosscheck_error_6d = torch.zeros(num_envs, 6)
    env._a2_v21b_last_clipped_utilization = torch.zeros(num_envs)
    env._a2_v21b_last_clipped_utilization_valid = torch.zeros(num_envs, dtype=torch.bool)
    env._a2_v21b_last_decomposition_sanity = torch.zeros(num_envs, dtype=torch.bool)
    env._a2_v21b_last_decomposition_sanity_valid = torch.zeros(num_envs, dtype=torch.bool)
    env._a2_v21b_hinge_at_send_latch = torch.full((num_envs,), float("nan"))
    env._a2_v21b_hinge_at_send_latch_valid = torch.zeros(num_envs, dtype=torch.bool)
    env._a2_v20_send_ready = torch.zeros(num_envs, dtype=torch.bool)
    env._a2_v20_first_send_ready_step = torch.full((num_envs,), -1, dtype=torch.long)
    env._a2_v20_first_root_crossing_step = torch.full((num_envs,), -1, dtype=torch.long)
    env._a2_v20_hinge_at_first_root_crossing = torch.full((num_envs,), float("nan"))
    env._a2_v21b_completed_telemetry_valid = torch.zeros(num_envs, dtype=torch.bool)
    env._a2_v21b_completed_send_ready = torch.zeros(num_envs, dtype=torch.bool)
    env._a2_v21b_completed_first_send_ready_step = torch.full(
        (num_envs,), -1, dtype=torch.long
    )
    env._a2_v21b_completed_first_root_crossing_step = torch.full(
        (num_envs,), -1, dtype=torch.long
    )
    env._a2_v21b_completed_hinge_at_send_latch = torch.full(
        (num_envs,), float("nan")
    )
    env._a2_v21b_completed_hinge_at_send_latch_valid = torch.zeros(
        num_envs, dtype=torch.bool
    )
    env._a2_v21b_completed_hinge_at_crossing = torch.full(
        (num_envs,), float("nan")
    )
    env._a2_v21b_completed_hinge_at_crossing_valid = torch.zeros(
        num_envs, dtype=torch.bool
    )
    env._a2_v21b_completed_clipped_utilization = torch.zeros(num_envs)
    env._a2_v21b_completed_clipped_utilization_valid = torch.zeros(
        num_envs, dtype=torch.bool
    )
    env._a2_v21b_completed_decomposition_sanity = torch.zeros(
        num_envs, dtype=torch.bool
    )
    env._a2_v21b_completed_decomposition_sanity_valid = torch.zeros(
        num_envs, dtype=torch.bool
    )
    env._a2_v21b_completed_stage_overtime = torch.zeros(num_envs, dtype=torch.bool)
    env._a2_v21b_completed_upper_dof_overspeed = torch.zeros(
        num_envs, dtype=torch.bool
    )
    env._a2_v21b_stage_overtime = torch.zeros(num_envs, dtype=torch.bool)
    env._a2_v21b_upper_dof_overspeed = torch.zeros(num_envs, dtype=torch.bool)
    env.simulator = SimpleNamespace(
        scene=SimpleNamespace(
            articulations={"robot": SimpleNamespace(data=None)},
        )
    )
    return env


def _set_lifecycle_arm_data(env, *, target: float, computed: float, applied: float):
    shape = (env.num_envs, 6)
    env.simulator.scene.articulations["robot"].data = SimpleNamespace(
        joint_pos=torch.zeros(shape),
        joint_vel=torch.full(shape, 0.1),
        joint_pos_target=torch.full(shape, target),
        joint_stiffness=torch.full(shape, 100.0),
        joint_damping=torch.ones(shape),
        joint_effort_limits=torch.full(shape, 100.0),
        computed_torque=torch.full(shape, computed),
        applied_torque=torch.full(shape, applied),
    )


def test_estimate_authority_and_strict_shape():
    step = _step()
    assert tuple(step["arm_pd_effort_estimate_unclipped_6d"].shape) == (2, 6)
    assert step["isaaclab_implicit_effort_estimate_authority"] == V21B_AUTHORITY_LABEL
    with pytest.raises(ValueError):
        a2_v21b_arm_pd_effort_estimates(torch.zeros((2, 5)), torch.zeros((2, 5)), torch.zeros((2, 5)), torch.ones((2, 5)), torch.ones((2, 5)), torch.ones((2, 5)))


def test_reset_safe_accumulation_and_typed_na():
    state = a2_v21b_init_arm_episode_accumulator(2)
    a2_v21b_accumulate_arm_step(state, _step())
    assert state["valid_frames"].tolist() == [1, 1]
    a2_v21b_reset_arm_episode_accumulator(state, torch.tensor([1], dtype=torch.long))
    assert state["valid_frames"].tolist() == [1, 0]
    assert a2_v21b_finalize_arm_episode(state, 1)["valid_frame_count"] == 0
    assert a2_v21b_finalize_arm_episode(state, 1)["arm_pd_effort_estimate_unclipped_p50_6d"]["status"] == "N/A"


def test_finalizer_outputs_validate_in_base_mode_but_not_strict_terminal_mode():
    zero_state = a2_v21b_init_arm_episode_accumulator(1, max_episode_length=1)
    zero_record = a2_v21b_finalize_arm_episode(zero_state, 0)
    a2_v21b_validate_evidence_record(zero_record)
    with pytest.raises(ValueError, match="all three implicit effort estimate fields"):
        a2_v21b_validate_evidence_record(
            zero_record,
            require_implicit_effort_estimates=True,
        )

    positive_state = a2_v21b_init_arm_episode_accumulator(1, max_episode_length=1)
    positive_step = _step(1)
    positive_step["step_index"] = torch.zeros(1, dtype=torch.long)
    a2_v21b_accumulate_arm_step(positive_state, positive_step)
    positive_record = a2_v21b_finalize_arm_episode(positive_state, 0)
    a2_v21b_validate_evidence_record(positive_record)
    with pytest.raises(ValueError, match="all three implicit effort estimate fields"):
        a2_v21b_validate_evidence_record(
            positive_record,
            require_implicit_effort_estimates=True,
        )


def test_evidence_validator_binds_implicit_vectors_to_valid_frame_count():
    fields = (
        "isaaclab_implicit_computed_effort_estimate_6d",
        "isaaclab_implicit_applied_effort_estimate_6d",
        "isaaclab_implicit_effort_estimate_crosscheck_error_6d",
    )
    no_valid = {"status": "N/A", "reason": "no valid arm telemetry frames", "denominator": 0}
    record = {
        "schema": "a2_piper_base_v21B_arm_evidence_v1",
        "joint_names": ["arm_j1", "arm_j2", "arm_j3", "arm_j4", "arm_j5", "arm_j6"],
        "authority": V21B_AUTHORITY_LABEL,
        "valid_frame_count": 0,
        **{field: dict(no_valid) for field in fields},
    }
    a2_v21b_validate_evidence_record(record)
    a2_v21b_validate_evidence_record(record, require_implicit_effort_estimates=True)
    for field in fields:
        for malformed in (
            [0.0] * 6,
            {"status": "N/A", "reason": "no valid arm telemetry frames", "denominator": 1},
            {"status": "N/A", "reason": "no valid arm telemetry frames", "denominator": False},
            {**no_valid, "value": None},
        ):
            record[field] = malformed
            with pytest.raises(ValueError, match="typed N/A"):
                a2_v21b_validate_evidence_record(record)
        record[field] = dict(no_valid)

    record["valid_frame_count"] = 1
    for field in fields:
        record[field] = [0.0] * 6
    a2_v21b_validate_evidence_record(record)
    a2_v21b_validate_evidence_record(record, require_implicit_effort_estimates=True)
    for malformed in ([0.0] * 5, [float("nan")] * 6, [True] * 6, dict(no_valid)):
        record[fields[0]] = malformed
        with pytest.raises(ValueError, match="finite numeric six-joint vector"):
            a2_v21b_validate_evidence_record(record)
    record[fields[0]] = [0.0] * 6

    partial = dict(record)
    partial.pop(fields[-1])
    with pytest.raises(ValueError, match="all three implicit effort estimate fields"):
        a2_v21b_validate_evidence_record(partial)
    with pytest.raises(ValueError, match="all three implicit effort estimate fields"):
        a2_v21b_validate_evidence_record(partial, require_implicit_effort_estimates=True)
    with pytest.raises(ValueError, match="strict selector"):
        a2_v21b_validate_evidence_record(record, require_implicit_effort_estimates=1)


def test_live_history_derives_episode_quantiles_and_utilization():
    state = a2_v21b_init_arm_episode_accumulator(1, max_episode_length=3)
    first = _step(1)
    first["arm_pd_effort_estimate_unclipped_6d"][:] = 1.0
    first["arm_pd_effort_estimate_clipped_6d"][:] = 1.0
    first["step_index"] = torch.tensor([0], dtype=torch.long)
    a2_v21b_accumulate_arm_step(state, first)
    second = _step(1)
    second["arm_pd_effort_estimate_unclipped_6d"][:] = 3.0
    second["arm_pd_effort_estimate_clipped_6d"][:] = 3.0
    second["step_index"] = torch.tensor([1], dtype=torch.long)
    a2_v21b_accumulate_arm_step(state, second)
    record = a2_v21b_finalize_arm_episode(
        state,
        0,
        effort_limit_6d=torch.full((1, 6), 10.0),
    )
    assert record["arm_pd_effort_estimate_unclipped_p50_6d"] == [2.0] * 6
    assert record["arm_pd_effort_estimate_unclipped_p95_6d"] == pytest.approx([2.9] * 6)
    assert record["arm_pd_effort_estimate_unclipped_utilization_p50_6d"] == pytest.approx([0.2] * 6)
    assert record["fraction_of_valid_frames_max_utilization_ge_0.90"] == 0.0
    assert record["fraction_of_valid_frames_max_utilization_ge_0.98"] == 0.0


def test_utilization_thresholds_are_dimensionless_effort_fractions():
    state = a2_v21b_init_arm_episode_accumulator(1, max_episode_length=1)
    step = _step(1, effort_limit=100.0)
    step["arm_pd_effort_estimate_unclipped_6d"][:] = 2.0
    step["arm_pd_effort_estimate_clipped_6d"][:] = 2.0
    step["step_index"] = torch.zeros(1, dtype=torch.long)
    a2_v21b_accumulate_arm_step(state, step)
    record = a2_v21b_finalize_arm_episode(state, 0, effort_limit_6d=torch.full((1, 6), 100.0))
    assert record["fraction_of_valid_frames_ge_0.90_6d"] == [0.0] * 6
    assert record["fraction_of_valid_frames_ge_0.98_6d"] == [0.0] * 6
    assert record["fraction_of_valid_frames_max_utilization_ge_0.90"] == 0.0


def test_census_uses_unclipped_and_right_censors_at_100():
    effort = torch.full((4, 6), 110.0)
    with torch.no_grad():
        result = a2_v21b_census_from_unclipped(effort, torch.tensor([True, True, False, False]))
    assert result["status"] == V21B_CENSUS_RIGHT_CENSORED
    effort = torch.tensor([[35.0] * 6, [55.0] * 6, [15.0] * 6, [16.0] * 6])
    result = a2_v21b_census_from_unclipped(effort, torch.tensor([True, True, False, False]), candidate_limits_nm=(40.0, 30.0, 25.0, 20.0))
    assert result["selection"] in (40.0, 30.0, 25.0, 20.0, "N/A")


def test_census_separates_episode_selection_from_raw_frame_censoring():
    # Candidate selection sees two heavy episode peaks (30, 10), while the
    # raw telemetry stream had ten heavy frames.  The 0.5 selection fraction
    # must not be replaced by a frame-weighted 0.1 statistic.
    episode_peaks = torch.tensor([[30.0] * 6, [10.0] * 6, [10.0] * 6, [10.0] * 6])
    heavy = torch.tensor([True, True, False, False])
    result = a2_v21b_census_from_unclipped(
        episode_peaks,
        heavy,
        candidate_limits_nm=(20.0,),
        raw_heavy_valid_frame_count=10,
        right_censored_heavy_frame_count_at_100Nm=0,
    )
    assert result["status"] == "CENSUS_PASS"
    assert result["heavy_episode_count"] == 2
    assert result["light_episode_count"] == 2
    assert result["candidates"][0]["heavy_episode_peak_ge_limit_fraction"] == pytest.approx(0.5)
    assert result["raw_heavy_valid_frame_count"] == 10
    assert result["right_censored_heavy_frame_fraction_at_100Nm"] == 0.0
    assert "heavy_frame_count" not in result


def test_census_raw_right_censor_guard_is_strictly_above_five_percent():
    episode_peaks = torch.tensor([[30.0] * 6, [10.0] * 6, [10.0] * 6, [10.0] * 6])
    heavy = torch.tensor([True, True, False, False])
    at_threshold = a2_v21b_census_from_unclipped(
        episode_peaks,
        heavy,
        candidate_limits_nm=(20.0,),
        raw_heavy_valid_frame_count=20,
        right_censored_heavy_frame_count_at_100Nm=1,
    )
    above_threshold = a2_v21b_census_from_unclipped(
        episode_peaks,
        heavy,
        candidate_limits_nm=(20.0,),
        raw_heavy_valid_frame_count=20,
        right_censored_heavy_frame_count_at_100Nm=2,
    )
    assert at_threshold["status"] == "CENSUS_PASS"
    assert at_threshold["right_censored_heavy_frame_fraction_at_100Nm"] == pytest.approx(0.05)
    assert above_threshold["status"] == V21B_CENSUS_RIGHT_CENSORED
    assert above_threshold["right_censored_heavy_frame_fraction_at_100Nm"] == pytest.approx(0.10)


def test_dv2_requires_tracking_error_corroboration():
    clipped = torch.full((4, 6), 25.0)
    heavy = torch.tensor([True, True, False, False])
    result = a2_v21b_adjudicate_dv2(clipped, heavy, None, torch.ones((4, 6)), effort_limit_nm=25.0)
    assert result["label"] == V21B_BOUNDARY_ESTIMATE_ONLY_UNCORROBORATED
    result = a2_v21b_adjudicate_dv2(clipped, heavy, torch.ones((4, 6)), torch.full((4, 6), 2.0), effort_limit_nm=25.0)
    assert result["label"] == V21B_BOUNDARY_SATURATED_EVERYWHERE


def test_dv2_created_requires_heavy_only_saturation_and_tracking_corroboration():
    clipped = torch.tensor([[25.0] * 6, [25.0] * 6, [10.0] * 6, [10.0] * 6])
    heavy = torch.tensor([True, True, False, False])
    result = a2_v21b_adjudicate_dv2(clipped, heavy, torch.ones((4, 6)), torch.full((4, 6), 2.0), effort_limit_nm=25.0)
    assert result["label"] == V21B_BOUNDARY_CREATED


def test_census_raw_export_retains_real_frame_identity_and_provenance(tmp_path):
    state = a2_v21b_init_arm_episode_accumulator(1, max_episode_length=1)
    step = _step(1)
    step["step_index"] = torch.zeros(1, dtype=torch.long)
    a2_v21b_accumulate_arm_step(state, step)
    digests = {"source_checkpoint_sha256": "a" * 64, "source_lock_sha256": "b" * 64, "source_config_sha256": "c" * 64, "materialization_sha256": "d" * 64, "materialized_config_sha256": "e" * 64}
    frames = a2_v21b_build_census_frames_from_episode(state, 0, scenario_id="heavy-0", topology="heavy16", episode_id="episode-0", door_weight_kg=140.0, hinge_force_nm=10.0, phase="CENSUS_PRE_K", **digests)
    assert frames[0]["frame_id"] == "episode-0:env0:step0"
    assert frames[0]["heavy_bucket"] is True
    assert frames[0]["arm_pd_effort_estimate_unclipped_6d"] == pytest.approx([99.9] * 6)
    receipt = a2_v21b_export_census_frames(tmp_path / "frames.json", frames)
    assert receipt["frame_count"] == 1
    with pytest.raises(FileExistsError):
        a2_v21b_export_census_frames(tmp_path / "frames.json", frames)


def test_shared_trace_run_uuid_is_plan_aware_and_fail_fast():
    legacy_calls = []

    def legacy_provenance():
        legacy_calls.append(True)
        raise AssertionError("v21-B trace resolution must not request legacy R2 provenance")

    assert resolve_v21b_trace_run_uuid(
        {"a2_v21B_run_uuid": "v21B-census-canonical16"},
        plan_id=V21B_PLAN_ID,
        legacy_provenance=legacy_provenance,
    ) == "v21B-census-canonical16"
    assert legacy_calls == []

    assert resolve_v21b_trace_run_uuid(
        {},
        plan_id="base_v20_R1_policy_behavior_v1",
        legacy_provenance=lambda: {"run_uuid": "v20-r2-run"},
    ) == "v20-r2-run"

    for invalid in (None, "", 1, True):
        with pytest.raises(V21BError, match="a2_v21B_run_uuid"):
            resolve_v21b_trace_run_uuid(
                {"a2_v21B_run_uuid": invalid},
                plan_id=V21B_PLAN_ID,
                legacy_provenance=legacy_provenance,
            )


def test_overflow_step_is_excluded_from_arm_accumulator():
    state = a2_v21b_init_arm_episode_accumulator(1, max_episode_length=2)
    valid = _step(1)
    valid["step_index"] = torch.tensor([1], dtype=torch.long)
    a2_v21b_accumulate_arm_step(state, valid)
    overflow = _step(1)
    overflow["step_index"] = torch.tensor([2], dtype=torch.long)
    overflow["valid_mask"][:] = False
    a2_v21b_accumulate_arm_step(state, overflow)
    assert state["valid_frames"].tolist() == [1]


def test_overflow_handoff_preserves_previous_valid_telemetry():
    env = _lifecycle_env()
    _set_lifecycle_arm_data(env, target=1.0, computed=7.0, applied=8.0)
    env._update_a2_v21b_arm_evidence_accumulators()
    first_implicit_computed = env._a2_v21b_last_implicit_computed_effort_6d.clone()
    first_implicit_applied = env._a2_v21b_last_implicit_applied_effort_6d.clone()
    first_crosscheck = env._a2_v21b_last_implicit_crosscheck_error_6d.clone()
    first_utilization = env._a2_v21b_last_clipped_utilization.clone()
    first_sanity = env._a2_v21b_last_decomposition_sanity.clone()

    env.episode_length_buf = torch.tensor([4, 2], dtype=torch.long)
    _set_lifecycle_arm_data(env, target=0.5, computed=17.0, applied=18.0)
    env._update_a2_v21b_arm_evidence_accumulators()

    assert env._a2_v21b_arm_evidence["valid_frames"].tolist() == [1, 2]
    assert torch.equal(
        env._a2_v21b_last_implicit_computed_effort_6d[0], first_implicit_computed[0]
    )
    assert torch.equal(
        env._a2_v21b_last_implicit_applied_effort_6d[0], first_implicit_applied[0]
    )
    assert torch.equal(env._a2_v21b_last_implicit_crosscheck_error_6d[0], first_crosscheck[0])
    assert env._a2_v21b_last_clipped_utilization[0].item() == pytest.approx(
        first_utilization[0].item()
    )
    assert env._a2_v21b_last_decomposition_sanity[0].item() == first_sanity[0].item()
    assert env._a2_v21b_last_clipped_utilization_valid.tolist() == [True, True]
    assert env._a2_v21b_last_decomposition_sanity_valid.tolist() == [True, True]
    assert env._a2_v21b_last_clipped_utilization[1].item() != pytest.approx(
        first_utilization[1].item()
    )

    env._capture_a2_v21b_completed_telemetry(torch.tensor([0, 1], dtype=torch.long))
    assert env._a2_v21b_completed_clipped_utilization.tolist() == pytest.approx(
        env._a2_v21b_last_clipped_utilization.tolist()
    )
    assert env._a2_v21b_completed_clipped_utilization_valid.tolist() == [True, True]
    assert env._a2_v21b_completed_decomposition_sanity_valid.tolist() == [True, True]
    assert env.get_a2_v21b_arm_episode_evidence(0)["valid_frame_count"] == 1
    assert env.get_a2_v21b_arm_episode_evidence(0)[
        "isaaclab_implicit_computed_effort_estimate_6d"
    ] == pytest.approx(first_implicit_computed[0].tolist())


def test_overflow_without_prior_valid_sample_remains_invalid():
    env = _lifecycle_env(num_envs=1)
    env.episode_length_buf[:] = 4
    _set_lifecycle_arm_data(env, target=0.5, computed=17.0, applied=18.0)
    env._update_a2_v21b_arm_evidence_accumulators()

    assert env._a2_v21b_arm_evidence["valid_frames"].tolist() == [0]
    assert env._a2_v21b_last_clipped_utilization_valid.tolist() == [False]
    assert env._a2_v21b_last_decomposition_sanity_valid.tolist() == [False]
    env._capture_a2_v21b_completed_telemetry(torch.tensor([0], dtype=torch.long))
    assert env._a2_v21b_completed_clipped_utilization_valid.tolist() == [False]
    assert env._a2_v21b_completed_decomposition_sanity_valid.tolist() == [False]
    record = env.get_a2_v21b_arm_episode_evidence(0)
    assert record["valid_frame_count"] == 0
    expected_na = {"status": "N/A", "reason": "no valid arm telemetry frames", "denominator": 0}
    for field in (
        "isaaclab_implicit_computed_effort_estimate_6d",
        "isaaclab_implicit_applied_effort_estimate_6d",
        "isaaclab_implicit_effort_estimate_crosscheck_error_6d",
    ):
        assert record[field] == expected_na


def test_reset_callback_clears_current_last_validity_after_terminal_snapshot(monkeypatch):
    env = _lifecycle_env(num_envs=2)
    env._use_a2_base = False
    env._a2_v21b_completed_telemetry_valid[:] = True
    env._a2_v21b_last_clipped_utilization[:] = torch.tensor([0.8, 0.9])
    env._a2_v21b_last_clipped_utilization_valid[:] = True
    env._a2_v21b_last_decomposition_sanity[:] = True
    env._a2_v21b_last_decomposition_sanity_valid[:] = True
    env._reset_a2_v20_r2_evidence_buffers = lambda env_ids: None
    parent = next(
        cls
        for cls in DoorPregrasp.__mro__[1:]
        if "_reset_buffers_callback" in cls.__dict__
    )
    monkeypatch.setattr(
        parent,
        "_reset_buffers_callback",
        lambda self, env_ids, target_buf=None: target_buf,
    )

    env._reset_buffers_callback(torch.tensor([0], dtype=torch.long))

    assert env._a2_v21b_last_clipped_utilization_valid.tolist() == [False, True]
    assert env._a2_v21b_last_decomposition_sanity_valid.tolist() == [False, True]
    assert env._a2_v21b_last_clipped_utilization.tolist() == pytest.approx([0.0, 0.9])
    assert env._a2_v21b_completed_telemetry_valid.tolist() == [True, True]


def test_terminal_telemetry_survives_reset_and_preserves_no_sample_validity():
    if DoorPregrasp is None:
        pytest.skip("DoorPregrasp lifecycle harness requires IsaacLab pxr bindings")
    env = object.__new__(DoorPregrasp)
    env.device = torch.device("cpu")
    env.num_envs = 1
    env._a2_v20_send_ready = torch.tensor([True])
    env._a2_v20_first_send_ready_step = torch.tensor([3], dtype=torch.long)
    env._a2_v20_first_root_crossing_step = torch.tensor([6], dtype=torch.long)
    env._a2_v20_hinge_at_first_root_crossing = torch.tensor([1.3])
    env._a2_v21b_hinge_at_send_latch = torch.tensor([1.2])
    env._a2_v21b_hinge_at_send_latch_valid = torch.tensor([True])
    env._a2_v21b_last_clipped_utilization = torch.tensor([0.87])
    env._a2_v21b_last_clipped_utilization_valid = torch.tensor([True])
    env._a2_v21b_last_decomposition_sanity = torch.tensor([True])
    env._a2_v21b_last_decomposition_sanity_valid = torch.tensor([True])
    env._a2_v21b_stage_overtime = torch.tensor([True])
    env._a2_v21b_upper_dof_overspeed = torch.tensor([False])
    env._a2_v21b_completed_telemetry_valid = torch.zeros(1, dtype=torch.bool)
    env._a2_v21b_completed_send_ready = torch.zeros(1, dtype=torch.bool)
    env._a2_v21b_completed_first_send_ready_step = torch.full((1,), -1, dtype=torch.long)
    env._a2_v21b_completed_first_root_crossing_step = torch.full((1,), -1, dtype=torch.long)
    env._a2_v21b_completed_hinge_at_send_latch = torch.full((1,), float("nan"))
    env._a2_v21b_completed_hinge_at_send_latch_valid = torch.zeros(1, dtype=torch.bool)
    env._a2_v21b_completed_hinge_at_crossing = torch.full((1,), float("nan"))
    env._a2_v21b_completed_hinge_at_crossing_valid = torch.zeros(1, dtype=torch.bool)
    env._a2_v21b_completed_clipped_utilization = torch.zeros(1)
    env._a2_v21b_completed_clipped_utilization_valid = torch.zeros(1, dtype=torch.bool)
    env._a2_v21b_completed_decomposition_sanity = torch.zeros(1, dtype=torch.bool)
    env._a2_v21b_completed_decomposition_sanity_valid = torch.zeros(1, dtype=torch.bool)
    env._a2_v21b_completed_stage_overtime = torch.zeros(1, dtype=torch.bool)
    env._a2_v21b_completed_upper_dof_overspeed = torch.zeros(1, dtype=torch.bool)

    env._capture_a2_v21b_completed_telemetry(torch.tensor([0], dtype=torch.long))
    env._a2_v20_send_ready[:] = False
    env._a2_v20_first_send_ready_step[:] = -1
    env._a2_v20_first_root_crossing_step[:] = -1
    env._a2_v20_hinge_at_first_root_crossing[:] = float("nan")
    env._a2_v21b_hinge_at_send_latch[:] = float("nan")
    env._a2_v21b_hinge_at_send_latch_valid[:] = False
    env._a2_v21b_last_clipped_utilization[:] = 0.0
    env._a2_v21b_last_clipped_utilization_valid[:] = False
    env._a2_v21b_last_decomposition_sanity[:] = False
    env._a2_v21b_last_decomposition_sanity_valid[:] = False
    env._a2_v21b_stage_overtime[:] = False

    effective = env._get_a2_v21b_effective_telemetry()
    assert effective["send_ready"].tolist() == [True]
    assert effective["first_root_crossing_step"].tolist() == [6]
    assert effective["clipped_utilization"].item() == pytest.approx(0.87)
    assert effective["stage_overtime"].tolist() == [True]
    assert effective["clipped_utilization_valid"].tolist() == [True]

    env._a2_v21b_completed_telemetry_valid[:] = False
    effective = env._get_a2_v21b_effective_telemetry()
    assert effective["send_ready"].tolist() == [False]
    assert effective["clipped_utilization_valid"].tolist() == [False]
