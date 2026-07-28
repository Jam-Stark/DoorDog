"""Contracts for base_v16_B Student distillation with the current C-B cameras."""

from __future__ import annotations

from pathlib import Path

import pytest
import torch
import yaml
from hydra import compose, initialize_config_dir

from gr00t.rl.scripts.run_a2_student_distillation_v16 import (
    EXPECTED_RUNTIME_COMMIT,
    V16_RUNTIME_MODULES,
)
from gr00t.rl.train_agent_trl import process_output_dim_in_config
from gr00t.rl.trl.trainer.ppo_trainer_a2_base_api import (
    _A2_GLOBAL_ENV_QUANTILE_SPECS,
    _A2_EVAL_OPTIONAL_RATIO_SPECS,
    _finalize_a2_conditional_ratios,
    _prepare_a2_env_metrics_for_aggregation,
)
from gr00t.rl.utils.a2_policy_camera import compose_horizontal_letterboxed_rgb
from gr00t.rl.utils.helpers import pre_process_config


ROOT = Path(__file__).resolve().parents[3]
DISTILL_EXP = (
    ROOT / "gr00t/rl/config/exp/wbmanip/door_open_a2_base_v16_cb_dagger-lstm.yaml"
)
CB_EVAL = ROOT / "gr00t/rl/config/camera_pose_sweep/d435i_landscape_up60_a2_head.yaml"
SIMULATOR = ROOT / "gr00t/rl/simulator/isaacsim/isaacsim.py"
BOOTSTRAP = ROOT / "gr00t/rl/scripts/run_a2_student_distillation_v16.py"


def _yaml(path: Path):
    with path.open("r", encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def test_distillation_cameras_match_current_cb_configuration_exactly():
    distill = _yaml(DISTILL_EXP)
    cb = _yaml(CB_EVAL)
    cameras = distill["simulator"]["config"]["cameras"]
    cb_cameras = cb["simulator"]["config"]["cameras"]
    for key in (
        "camera_parent",
        "camera_prim_suffix",
        "camera_pos",
        "camera_rot_wxyz",
        "camera_convention",
        "camera_focal_length",
        "camera_focus_distance",
        "camera_horizontal_aperture",
        "camera_vertical_aperture",
        "camera_clipping_range",
        "camera_update_period",
    ):
        assert cameras[key] == cb_cameras[key]

    multiview = cameras["policy_multiview"]
    head = cb["env"]["config"]["a2_camera_scheme_c"]["head_camera"]
    secondary = multiview["secondary"]
    assert multiview["architecture_id"] == "C-B"
    assert multiview["primary_resolution"] == cb_cameras["camera_resolutions"]
    assert multiview["output_resolution"] == cameras["camera_resolutions"] == [216, 768]
    assert secondary["sensor_name"] == head["sensor_name"]
    assert secondary["parent"] == head["parent"]
    assert secondary["prim_suffix"] == head["prim_suffix"]
    assert secondary["position_m"] == head["position_m"]
    assert secondary["rotation_wxyz"] == head["rotation_wxyz"]
    assert secondary["resolution"] == [head["height"], head["width"]]
    assert secondary["horizontal_aperture"] == head["horizontal_aperture"]
    assert secondary["vertical_aperture"] == head["vertical_aperture"]


def test_v16_teacher_task_overrides_match_the_sealed_run():
    exp = _yaml(DISTILL_EXP)
    env = exp["env"]["config"]
    assert {
        "a2_stage0_staging_x_min": env["a2_stage0_staging_x_min"],
        "a2_stage0_staging_x_max": env["a2_stage0_staging_x_max"],
        "a2_stage0_staging_y_tol": env["a2_stage0_staging_y_tol"],
        "a2_stage3_to4_requires_grasp_streak": env[
            "a2_stage3_to4_requires_grasp_streak"
        ],
        "a2_stage3_to4_streak_highwater": env["a2_stage3_to4_streak_highwater"],
        "a2_corridor_enabled": env["a2_corridor_enabled"],
        "a2_stage3_stage4_hold_and_drive_velocity_norm_in_corridor": env[
            "a2_stage3_stage4_hold_and_drive_velocity_norm_in_corridor"
        ],
        "a2_door_body_contact_penalty_mode": env["a2_door_body_contact_penalty_mode"],
        "a2_stage2_squeeze_force_min": env["a2_stage2_squeeze_force_min"],
        "a2_stage3_to4_door_hinge_threshold": env[
            "a2_stage3_to4_door_hinge_threshold"
        ],
        "a2_stage3_base_unlocked": env["a2_stage3_base_unlocked"],
        "a2_stage4_release_hinge_threshold": env["a2_stage4_release_hinge_threshold"],
        "a2_stage35_door_panel_contact_scale": env[
            "a2_stage35_door_panel_contact_scale"
        ],
    } == {
        "a2_stage0_staging_x_min": 0.5,
        "a2_stage0_staging_x_max": 0.8,
        "a2_stage0_staging_y_tol": 0.15,
        "a2_stage3_to4_requires_grasp_streak": True,
        "a2_stage3_to4_streak_highwater": False,
        "a2_corridor_enabled": True,
        "a2_stage3_stage4_hold_and_drive_velocity_norm_in_corridor": 0.4,
        "a2_door_body_contact_penalty_mode": "quadratic_v16",
        "a2_stage2_squeeze_force_min": 2.0,
        "a2_stage3_to4_door_hinge_threshold": 0.25,
        "a2_stage3_base_unlocked": True,
        "a2_stage4_release_hinge_threshold": 1.04,
        "a2_stage35_door_panel_contact_scale": 0.0,
    }
    assert exp["rewards"]["reward_scales"] == {
        "push_door_handle": 0.0,
        "a2_stage3_unlatch_hold": 3.0,
        "a2_stage3_stage4_hold_and_drive": 8.0,
        "a2_corridor_door_wide": 2.0,
        "penalty_a2_door_body_contact": -2.0,
        "penalty_a2_posture_command_l1": -0.15,
    }


def test_cb_policy_rgb_is_one_finite_216_by_768_tensor():
    primary = torch.arange(2 * 216 * 384 * 3, dtype=torch.int64).remainder(256)
    primary = primary.to(torch.uint8).reshape(2, 216, 384, 3)
    secondary = torch.arange(2 * 136 * 384 * 3, dtype=torch.int64).remainder(251)
    secondary = secondary.to(torch.uint8).reshape(2, 136, 384, 3)
    output = compose_horizontal_letterboxed_rgb(
        primary,
        secondary,
        primary_resolution=[216, 384],
        secondary_resolution=[136, 384],
        output_resolution=[216, 768],
        image_mean=[0.0, 0.0, 0.0],
        image_std=[1.0, 1.0, 1.0],
    )
    assert tuple(output.shape) == (2, 216, 768, 3)
    assert torch.allclose(output[:, :, :384], primary.float() / 255.0)
    assert torch.count_nonzero(output[:, :40, 384:]) == 0
    assert torch.count_nonzero(output[:, 176:, 384:]) == 0
    assert torch.allclose(output[:, 40:176, 384:], secondary.float() / 255.0)
    assert torch.all(torch.isfinite(output))


def test_cb_policy_rgb_rejects_a_constant_secondary_frame():
    primary = torch.arange(216 * 384 * 3, dtype=torch.int64).remainder(256)
    primary = primary.to(torch.uint8).reshape(1, 216, 384, 3)
    secondary = torch.zeros((1, 136, 384, 3), dtype=torch.uint8)
    with pytest.raises(ValueError, match="secondary policy camera contains a constant"):
        compose_horizontal_letterboxed_rgb(
            primary,
            secondary,
            primary_resolution=[216, 384],
            secondary_resolution=[136, 384],
            output_resolution=[216, 768],
            image_mean=[0.485, 0.456, 0.406],
            image_std=[0.229, 0.224, 0.225],
        )


def test_composed_hydra_contract_updates_only_the_student_vision_dimension():
    config_dir = (ROOT / "gr00t/rl/config").resolve()
    with initialize_config_dir(version_base="1.1", config_dir=str(config_dir)):
        config = compose(
            config_name="base",
            overrides=["+exp=wbmanip/door_open_a2_base_v16_cb_dagger-lstm"],
        )
    pre_process_config(config)
    process_output_dim_in_config(config)
    assert config.robot.algo_obs_dim_dict == {
        "actor_obs": 81,
        "vision_obs": 216 * 768 * 3,
        "teacher_obs": 133,
        "critic_obs": 138,
        "a2_base_obs": 1620,
    }
    assert config.algo.config.student_action_dim == 12
    assert config.algo.config.rollout_action_dim == 24
    assert config.algo.config.ratio_teacher_rollout == 1.0


def test_v16_bootstrap_has_a_narrow_pinned_lazy_overlay():
    assert EXPECTED_RUNTIME_COMMIT == "815b367f5de2a52b26a4b872d0457af8817d01bd"
    assert set(V16_RUNTIME_MODULES) == {
        "gr00t.rl.envs.door.door_open_a2_base",
        "gr00t.rl.data.tasks.door.scenario_cfg.isaacsim",
        "gr00t.rl.isaac_utils.playground.env_rand.door",
    }
    source = BOOTSTRAP.read_text(encoding="utf-8")
    assert "runpy.run_path(str(train_entrypoint), run_name=\"__main__\")" in source
    assert '"status", "--short", "--", "gr00t"' in source
    assert "if already_loaded:" in source


def test_simulator_uses_two_high_level_scene_sensors_without_extra_step_or_render():
    source = SIMULATOR.read_text(encoding="utf-8")
    assert 'self.scene.sensors[secondary_name] = self.policy_secondary_camera' in source
    assert "secondary_config = TiledCameraCfg(" in source
    assert "compose_horizontal_letterboxed_rgb(" in source
    get_rgb = source[source.index("    def get_rgb_image(self):") : source.index(
        "    def get_depth_image(self):"
    )]
    assert ".render(" not in get_rgb
    assert ".step(" not in get_rgb
    assert ".update(" not in get_rgb
    assert "UsdGeom" not in get_rgb


class _IdentityGatherAccelerator:
    def gather(self, value):
        return value


def test_v16_quantile_masks_are_consumed_and_new_quantiles_are_finite():
    metrics = {}
    expected_p50 = {}
    expected_p95 = {}
    for offset, (
        metric_name,
        (samples_key, mask_key, p50_key, p95_key),
    ) in enumerate(_A2_GLOBAL_ENV_QUANTILE_SPECS.items()):
        samples = torch.tensor(
            [1.0 + offset, 2.0 + offset, 3.0 + offset, 4.0 + offset],
            dtype=torch.float32,
        )
        mask = torch.tensor([True, False, True, False], dtype=torch.bool)
        metrics[samples_key] = samples
        metrics[mask_key] = mask
        active = samples[mask]
        expected_p50[metric_name] = torch.quantile(active, 0.50)
        expected_p95[metric_name] = torch.quantile(active, 0.95)

    prepared = _prepare_a2_env_metrics_for_aggregation(
        metrics,
        _IdentityGatherAccelerator(),
        torch.device("cpu"),
    )

    for metric_name, (
        samples_key,
        mask_key,
        p50_key,
        p95_key,
    ) in _A2_GLOBAL_ENV_QUANTILE_SPECS.items():
        assert samples_key not in prepared
        assert mask_key not in prepared
        assert torch.isfinite(prepared[p50_key])
        assert torch.isfinite(prepared[p95_key])
        assert torch.equal(prepared[p50_key], expected_p50[metric_name])
        assert torch.equal(prepared[p95_key], expected_p95[metric_name])


def test_v16_all_false_quantile_masks_emit_finite_zero_percentiles():
    samples_key, mask_key, p50_key, p95_key = _A2_GLOBAL_ENV_QUANTILE_SPECS[
        "a2_hinge_at_crossing"
    ]
    prepared = _prepare_a2_env_metrics_for_aggregation(
        {
            samples_key: torch.tensor([2.0, 8.0], dtype=torch.float32),
            mask_key: torch.tensor([False, False], dtype=torch.bool),
        },
        _IdentityGatherAccelerator(),
        torch.device("cpu"),
    )
    assert samples_key not in prepared
    assert mask_key not in prepared
    assert prepared[p50_key].item() == 0.0
    assert prepared[p95_key].item() == 0.0
    assert torch.isfinite(prepared[p50_key])
    assert torch.isfinite(prepared[p95_key])


def test_v16_crossing_and_over_force_ratios_strip_and_reconstruct():
    assert _A2_EVAL_OPTIONAL_RATIO_SPECS[
        "a2_stage3_stage4_over_force_frac"
    ] == (
        "a2_stage3_stage4_over_force_numerator_frac",
        "a2_stage3_stage4_over_force_denominator_frac",
    )
    metrics = {
        "a2_crossing_while_holding_frac": torch.tensor(0.5),
        "a2_crossing_while_holding_numerator_frac": torch.tensor(2.0),
        "a2_crossing_while_holding_denominator_frac": torch.tensor(4.0),
        "a2_stage3_stage4_over_force_frac": torch.tensor(0.25),
        "a2_stage3_stage4_over_force_numerator_frac": torch.tensor(1.0),
        "a2_stage3_stage4_over_force_denominator_frac": torch.tensor(4.0),
    }
    prepared = _prepare_a2_env_metrics_for_aggregation(
        metrics,
        _IdentityGatherAccelerator(),
        torch.device("cpu"),
    )
    assert "a2_crossing_while_holding_frac" not in prepared
    assert "a2_stage3_stage4_over_force_frac" not in prepared
    finalized = _finalize_a2_conditional_ratios(prepared)
    assert finalized["a2_crossing_while_holding_frac"].item() == 0.5
    assert finalized["a2_stage3_stage4_over_force_frac"].item() == 0.25


def test_v16_unknown_bool_and_integer_telemetry_remain_uncoerced():
    unknown_bool = torch.tensor(True, dtype=torch.bool)
    unknown_integer = torch.tensor(7, dtype=torch.int64)
    prepared = _prepare_a2_env_metrics_for_aggregation(
        {"unknown_bool": unknown_bool, "unknown_integer": unknown_integer},
        _IdentityGatherAccelerator(),
        torch.device("cpu"),
    )
    assert prepared["unknown_bool"] is unknown_bool
    assert prepared["unknown_bool"].dtype is torch.bool
    assert prepared["unknown_integer"] is unknown_integer
    assert prepared["unknown_integer"].dtype is torch.int64
