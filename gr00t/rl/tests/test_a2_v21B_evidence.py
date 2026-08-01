"""CPU-only v21-B arm telemetry contracts."""

from __future__ import annotations

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
