"""CPU/static contracts for the R14 same-step camera transform probe."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gr00t.rl.scripts.probe_a2_student_camera_transform import (
    LIVE_ORIENTATION_METRICS,
    LIVE_POSITION_METRICS,
    classify_transform_probe,
    compose_probe_config,
    seal_probe_evidence,
)


def _closed_live_metrics(*, cached_position_error: float) -> dict[str, float]:
    metrics = {name: 1.0e-6 for name in LIVE_POSITION_METRICS}
    metrics.update({name: 2.0e-6 for name in LIVE_ORIENTATION_METRICS})
    metrics["camera_cached_data_prim_position_max_m"] = cached_position_error
    metrics["camera_cached_data_prim_orientation_max_rad"] = 0.1
    return metrics


def _classify(metrics: dict[str, float], *, update_latest: bool = False):
    return classify_transform_probe(
        metrics,
        update_latest_camera_pose_before=update_latest,
        position_tolerance_m=1.0e-4,
        orientation_tolerance_rad=5.0e-4,
        stale_position_threshold_m=1.0e-2,
    )


def test_r14_probe_confirms_stale_initialization_pose_only_when_live_chain_closes():
    verdict = _classify(_closed_live_metrics(cached_position_error=0.85))
    assert verdict == {
        "status": "PASS",
        "resolution": "R14_STALE_INITIALIZATION_POSE_CONFIRMED",
        "checks": {
            "default_pose_cache_disabled": True,
            "live_positions_close": True,
            "live_orientations_close": True,
            "cached_pose_materially_stale": True,
        },
    }


def test_r14_probe_is_inconclusive_when_stale_pose_is_not_reproduced():
    verdict = _classify(_closed_live_metrics(cached_position_error=2.0e-4))
    assert verdict["status"] == "INCONCLUSIVE"
    assert verdict["resolution"] == "R14_NOT_REPRODUCED_IN_CURRENT_RESET"


@pytest.mark.parametrize(
    ("mutation", "update_latest"),
    [
        ({"parent_robot_xform_position_max_m": 1.0e-2}, False),
        ({"camera_prim_expected_orientation_max_rad": 1.0e-2}, False),
        ({}, True),
    ],
)
def test_r14_probe_fails_when_live_transform_contract_does_not_close(
    mutation, update_latest
):
    metrics = _closed_live_metrics(cached_position_error=0.85)
    metrics.update(mutation)
    verdict = _classify(metrics, update_latest=update_latest)
    assert verdict["status"] == "FAIL"
    assert verdict["resolution"] == "R14_LIVE_TRANSFORM_CONTRACT_MISMATCH"


def test_r14_probe_rejects_metric_schema_drift():
    metrics = _closed_live_metrics(cached_position_error=0.85)
    metrics["unexpected"] = 0.0
    with pytest.raises(ValueError, match="exact probe schema"):
        _classify(metrics)


def test_r14_probe_rejects_non_finite_metric():
    metrics = _closed_live_metrics(cached_position_error=float("nan"))
    with pytest.raises(ValueError, match="must be finite"):
        _classify(metrics)


def test_r14_probe_standalone_composition_registers_project_resolvers(tmp_path):
    config = compose_probe_config(tmp_path / "r14.json")
    assert config.num_envs == 1
    assert config.headless is True
    assert config.simulator.config.cameras.enable_cameras is True
    assert config.robot.algo_obs_dim_dict["vision_obs"] == 216 * 384 * 3
    assert config.env.config.experiment_dir.endswith("r14_probe_runtime")


def test_r14_evidence_is_serialized_before_close_and_never_overwritten(tmp_path):
    output = tmp_path / "r14.json"
    evidence = {
        "schema_version": 1,
        "status": "PASS",
        "runtime": {"torch_version": "2.7.0"},
    }
    seal_probe_evidence(output, evidence)
    assert json.loads(output.read_text(encoding="utf-8")) == evidence
    with pytest.raises(FileExistsError, match="refuses to overwrite"):
        seal_probe_evidence(output, evidence)

    invalid_output = tmp_path / "invalid.json"
    with pytest.raises(TypeError):
        seal_probe_evidence(invalid_output, {"invalid": object()})
    assert not invalid_output.exists()
    assert not (tmp_path / ".invalid.json.tmp").exists()

    source = Path(
        "gr00t/rl/scripts/probe_a2_student_camera_transform.py"
    ).read_text(encoding="utf-8")
    main_source = source[source.index("def main()") :]
    assert main_source.index("seal_probe_evidence(") < main_source.index(
        "simulation_app.close("
    )
    collect_source = source[
        source.index("def collect_same_step_transform_evidence")
        : source.index("def seal_probe_evidence")
    ]
    assert collect_source.index("initial_trunk_prim_pos") < collect_source.index(
        "env.reset()"
    )
    assert collect_source.index("camera.update(dt=0.0, force_recompute=True)") < (
        collect_source.index("trunk_prim_pos, trunk_prim_quat = trunk_view.get_world_poses()")
    )
    assert "camera_view = camera._view" in collect_source
    assert "XformPrimView(CAMERA_PRIM_PATH" not in collect_source
    assert "camera.update(dt=0.0, force_recompute=True)" in source
    assert "physics_step_after_force != physics_step_before_force" in source
    assert "camera.cfg.update_latest_camera_pose = update_latest_camera_pose_before" in source
