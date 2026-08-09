import ast
import json
import math
from collections.abc import Sequence
from numbers import Real
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch
from omegaconf import OmegaConf

from gr00t.rl.envs.base_task.a2_base import A2Base
from gr00t.rl.envs.door.a2_v23_evidence import (
    V23_TORQUE_AUTHORITY_CLIPPED_COMMAND,
    V23_TORQUE_AUTHORITY_NOMINAL_PD,
    V23_TORQUE_SOURCE_AUTHORITY,
    a2_v23_accumulate_torque_step,
    a2_v23_apply_forward_intervention,
    a2_v23_build_torque_step_telemetry,
    a2_v23_finalize_torque_episode,
    a2_v23_init_torque_accumulator,
    a2_v23_reset_torque_accumulator,
)
from scriptsFORhuman.v23.posture_intervention import (
    A2_V23_ORACLE_OVERRIDE_FIELDS,
    V23Error,
    build_forward_intervention_actor_state,
)
from scriptsFORhuman.v23.p0_runtime_eval import (
    build_effort_limit_list,
    build_runtime_plan,
)


ROOT = Path(__file__).resolve().parents[3]
SCENARIO_SOURCE = ROOT / "gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py"
SIMULATOR_SOURCE = ROOT / "gr00t/rl/simulator/isaacsim/isaacsim.py"


class _FakeV23DoorSpawnerCfg:
    def __init__(
        self,
        door_handle_tblr,
        rand_door_handle_height=None,
        rand_door_weight=None,
        rand_hinge_drive_max_force=None,
    ):
        self.door_handle_tblr = door_handle_tblr
        self.rand_door_handle_height = rand_door_handle_height
        self.rand_door_weight = rand_door_weight
        self.rand_hinge_drive_max_force = rand_hinge_drive_max_force

    def replace(self, **kwargs):
        return _FakeV23DoorSpawnerCfg(
            kwargs.get("door_handle_tblr", self.door_handle_tblr),
            kwargs.get("rand_door_handle_height", self.rand_door_handle_height),
            kwargs.get("rand_door_weight", self.rand_door_weight),
            kwargs.get("rand_hinge_drive_max_force", self.rand_hinge_drive_max_force),
        )


class _FakeV23MultiAssetSpawnerCfg:
    def __init__(self, assets_cfg, random_choice):
        self.assets_cfg = assets_cfg
        self.random_choice = random_choice

    def replace(self, **kwargs):
        return _FakeV23MultiAssetSpawnerCfg(
            kwargs.get("assets_cfg", self.assets_cfg),
            kwargs.get("random_choice", self.random_choice),
        )


class _FakeV23DoorCfg:
    def __init__(self, spawn):
        self.spawn = spawn

    def replace(self, **kwargs):
        return _FakeV23DoorCfg(kwargs.get("spawn", self.spawn))


def _v23_scenario_helpers():
    tree = ast.parse(SCENARIO_SOURCE.read_text(encoding="utf-8"))
    names = {
        "_v23_p0_reject_integrity_fields",
        "_v23_p0_plain_manifest_payload",
        "get_TaskObjCfgDict_for_v23_p0_plain_scenario_manifest",
        "get_TaskObjCfgDict_for_door_config",
    }
    nodes = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    namespace = {
        "DoorSpawnerCfg": _FakeV23DoorSpawnerCfg,
        "Path": Path,
        "Real": Real,
        "Sequence": Sequence,
        "json": json,
        "math": math,
        "sim_utils": SimpleNamespace(
            MultiAssetSpawnerCfg=_FakeV23MultiAssetSpawnerCfg
        ),
        "_V21B_SIGNED_PROBE_FLAG": "a2_v21B_signed_probe_scenarios_enabled",
        "_V22_MANIFEST_FLAG": "a2_v22_scenario_manifest_enabled",
        "_V22_BUCKET_MIXTURE_KEY": "a2_v22_hinge_bucket_mixture",
        "_V23_P0_PLAIN_MANIFEST_SCHEMA": "a2_piper_base_v23_p0_plain_scenario_manifest_v1",
        "_V23_P0_PLAIN_MANIFEST_FLAG": "a2_v23_p0_plain_scenario_enabled",
        "_V23_P0_PLAIN_MANIFEST_PATH_KEY": "a2_v23_p0_scenario_manifest_path",
        "_V23_P0_PLAIN_TOPOLOGY_KEY": "a2_v23_p0_scenario_topology",
        "_V23_P0_PLAIN_SOURCE_FIELDS": {
            "scenario_id",
            "handle_height_m",
            "door_weight_kg",
            "hinge_force_nm",
        },
        "_V23_P0_PLAIN_TOPOLOGIES": ("canonical16", "heavy16"),
    }
    exec(
        compile(ast.Module(body=nodes, type_ignores=[]), str(SCENARIO_SOURCE), "exec"),
        namespace,
    )
    return namespace


def _door_eval_dispatcher():
    tree = ast.parse(SIMULATOR_SOURCE.read_text(encoding="utf-8"))
    node = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_get_task_obj_cfg_dict_for_door_eval"
    )
    namespace = {}
    exec(
        compile(ast.Module(body=[node], type_ignores=[]), str(SIMULATOR_SOURCE), "exec"),
        namespace,
    )
    return namespace["_get_task_obj_cfg_dict_for_door_eval"]


def _torque_inputs(rows=2, joints=2):
    shape = (rows, joints)
    zeros = torch.zeros(shape)
    return dict(
        joint_pos=zeros,
        joint_vel=zeros,
        joint_pos_target=torch.full(shape, 2.0),
        stiffness=torch.full(shape, 3.0),
        damping=torch.ones(shape),
        effort_limit=torch.full(shape, 4.0),
        implicit_computed_torque=torch.full(shape, 6.0),
        implicit_applied_torque=torch.full(shape, 4.0),
        joint_names=("j1", "j2"),
        valid_mask=torch.tensor([True, False]),
        step_index=torch.tensor([0, 0], dtype=torch.long),
    )


def test_v23_torque_step_and_episode_telemetry_are_estimate_only():
    step = a2_v23_build_torque_step_telemetry(**_torque_inputs())
    assert torch.equal(step["nominal_pd_torque_estimate"], torch.full((2, 2), 6.0))
    assert torch.equal(step["clipped_command_torque_estimate"], torch.full((2, 2), 4.0))
    assert torch.equal(step["estimated_saturation"], torch.ones((2, 2), dtype=torch.bool))
    assert step["authority_nominal_pd"] == V23_TORQUE_AUTHORITY_NOMINAL_PD
    assert step["authority_clipped_command"] == V23_TORQUE_AUTHORITY_CLIPPED_COMMAND
    assert step["isaaclab_torque_source_authority"] == V23_TORQUE_SOURCE_AUTHORITY

    state = a2_v23_init_torque_accumulator(2, 2)
    a2_v23_accumulate_torque_step(state, step)
    record = a2_v23_finalize_torque_episode(state, 0, joint_names=("j1", "j2"))
    assert record["valid_frame_count"] == 1
    assert record["nominal_pd_torque_abs_mean"] == [6.0, 6.0]
    assert record["clipped_command_torque_abs_max"] == [4.0, 4.0]
    assert record["estimated_saturation_fraction"] == [1.0, 1.0]
    assert step["arm_joint_position_error_6d"].equal(torch.full((2, 2), 2.0))
    assert record["arm_joint_position_error_abs_mean_6d"] == [2.0, 2.0]
    assert record["arm_joint_position_error_abs_max_6d"] == [2.0, 2.0]
    assert record["arm_joint_velocity_abs_mean_6d"] == [0.0, 0.0]
    assert record["tracking_error_formula"] == "v21B: joint_pos_target - joint_pos"


def test_v23_torque_reset_is_row_scoped():
    step = a2_v23_build_torque_step_telemetry(**_torque_inputs())
    state = a2_v23_init_torque_accumulator(2, 2)
    a2_v23_accumulate_torque_step(state, step)
    a2_v23_reset_torque_accumulator(state, torch.tensor([0], dtype=torch.long))
    assert int(state["valid_frames"][0]) == 0
    assert int(state["valid_frames"][1]) == 0
    assert torch.equal(state["nominal_pd_abs_max"], torch.zeros(2, 2))


def test_v23_terminal_snapshot_is_readable_after_live_reset_and_missing_is_typed():
    step = a2_v23_build_torque_step_telemetry(**_torque_inputs())
    state = a2_v23_init_torque_accumulator(2, 2)
    a2_v23_accumulate_torque_step(state, step)
    terminal_snapshot = a2_v23_finalize_torque_episode(
        state, 0, joint_names=("j1", "j2")
    )
    a2_v23_reset_torque_accumulator(state, torch.tensor([0], dtype=torch.long))
    assert terminal_snapshot["valid_frame_count"] == 1
    assert terminal_snapshot["nominal_pd_torque_abs_mean"] == [6.0, 6.0]
    missing = a2_v23_finalize_torque_episode(state, 0, joint_names=("j1", "j2"))
    assert missing["nominal_pd_torque_abs_mean"]["status"] == "N/A"
    assert missing["nominal_pd_torque_abs_mean"]["reason"] == "NO_VALID_TORQUE_TELEMETRY"
    assert missing["arm_joint_position_error_abs_mean_6d"]["status"] == "N/A"


def test_v23_torque_contract_rejects_wrong_shape():
    inputs = _torque_inputs()
    inputs["implicit_applied_torque"] = torch.zeros(2, 3)
    with pytest.raises(ValueError, match="shape"):
        a2_v23_build_torque_step_telemetry(**inputs)


def test_v23_forward_interventions_are_explicit_and_state_clone_free():
    action = torch.tensor([[1.0, 2.0, 3.0, 0.5, -0.5], [1.0, 2.0, 3.0, 0.25, -0.25]])
    acute, metadata = a2_v23_apply_forward_intervention(action, mode="ACUTE_RP0")
    assert torch.equal(acute[:, 3:5], torch.zeros(2, 2))
    assert metadata["forward_only"] is True
    assert metadata["state_clone_supported"] is False

    grasp, _ = a2_v23_apply_forward_intervention(
        action,
        mode="BASE0_AT_GRASP",
        stable_grasp_mask=torch.tensor([True, False]),
    )
    assert torch.equal(grasp[0, 3:5], torch.zeros(2))
    assert torch.equal(grasp[1, 3:5], action[1, 3:5])

    with pytest.raises(ValueError, match="requires both"):
        a2_v23_apply_forward_intervention(action, mode="ORACLE_TANGENTIAL_ASSIST")

    with pytest.raises(RuntimeError, match="applied effort-profile proof"):
        a2_v23_apply_forward_intervention(action, mode="HIGHER_EFFORT_RESCUE")
    rescued, metadata = a2_v23_apply_forward_intervention(
        action,
        mode="HIGHER_EFFORT_RESCUE",
        higher_effort_profile_applied=True,
    )
    assert torch.equal(rescued, action)
    assert metadata["effort_profile_applied"] is True


def test_v23_eval_intervention_precedes_low_level_and_marker_prevents_double_apply():
    env = object.__new__(A2Base)
    env._use_a2_base = True
    env._a2_high_level_action_dim = 12
    env._a2_arm_dof_indices = torch.zeros(6, dtype=torch.long)
    env._a2_gripper_dof_indices = torch.zeros(2, dtype=torch.long)
    env.config = {"a2_v23_forward_intervention_mode": "ACUTE_RP0"}
    env.is_evaluating = True
    high_level = torch.tensor(
        [[1.0, 2.0, 3.0, 0.5, -0.5, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 1.0]]
    )
    pre_low_level = env.apply_a2_v23_high_level_intervention(high_level)
    assert torch.equal(pre_low_level[:, 3:5], torch.zeros(1, 2))
    assert torch.equal(pre_low_level[:, 5:], high_level[:, 5:])
    raw_after_low_level = pre_low_level[:, :5].clone()
    no_double = env.apply_a2_v23_forward_intervention(
        raw_after_low_level,
        actor_state={"a2_v23_pre_low_level_applied": True},
    )
    assert torch.equal(no_double, raw_after_low_level)


def _v23_eval_stub(mode, **extra_config):
    env = object.__new__(A2Base)
    env._use_a2_base = True
    env._a2_high_level_action_dim = 12
    env._a2_arm_dof_indices = torch.zeros(6, dtype=torch.long)
    env._a2_gripper_dof_indices = torch.zeros(2, dtype=torch.long)
    env.num_envs = 2
    env.device = torch.device("cpu")
    env.is_evaluating = True
    env.config = {"a2_v23_forward_intervention_mode": mode, **extra_config}
    env._a2_stage3_grasp_streak_highwater = torch.tensor([True, False])
    env._a2_stage3_stage4_both_contact_streak = torch.tensor([0, 99], dtype=torch.long)
    return env


def test_standard_evaluator_state_assembly_covers_all_v23_modes():
    high_level = torch.tensor(
        [
            [1.0, 2.0, 3.0, 0.5, -0.5, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 1.0],
            [1.0, 2.0, 3.0, 0.25, -0.25, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 1.0],
        ]
    )
    full = _v23_eval_stub("FULL")
    assert full.build_a2_v23_forward_intervention_actor_state(
        device=high_level.device, dtype=high_level.dtype
    ) == {}
    assert torch.equal(full.apply_a2_v23_high_level_intervention(high_level), high_level)

    acute = _v23_eval_stub("ACUTE_RP0")
    assert acute.build_a2_v23_forward_intervention_actor_state(
        device=high_level.device, dtype=high_level.dtype
    ) == {}
    assert torch.equal(
        acute.apply_a2_v23_high_level_intervention(high_level)[:, 3:5],
        torch.zeros(2, 2),
    )

    base0 = _v23_eval_stub("BASE0_AT_GRASP")
    base0_state = base0.build_a2_v23_forward_intervention_actor_state(
        device=high_level.device, dtype=high_level.dtype
    )
    assert base0_state == {}
    base0_action = base0.apply_a2_v23_high_level_intervention(high_level)
    assert torch.equal(base0_action[0, 3:5], torch.zeros(2))
    assert torch.equal(base0_action[1, 3:5], high_level[1, 3:5])

    rescue = _v23_eval_stub(
        "HIGHER_EFFORT_RESCUE", a2_v23_effort_profile_applied=True
    )
    rescue_state = rescue.build_a2_v23_forward_intervention_actor_state(
        device=high_level.device, dtype=high_level.dtype
    )
    assert rescue_state["a2_v23_effort_profile_applied"] is True
    assert torch.equal(rescue.apply_a2_v23_high_level_intervention(high_level, actor_state=rescue_state), high_level)

    oracle_delta = torch.tensor(
        [[0.1, 0.2, 0.3, 0.4, 0.5], [0.5, 0.4, 0.3, 0.2, 0.1]]
    )
    oracle = _v23_eval_stub(
        "ORACLE_TANGENTIAL_ASSIST",
        a2_v23_oracle_tangential_delta_raw=oracle_delta,
        a2_v23_oracle_active_mask=torch.tensor([True, False]),
    )
    oracle_state = oracle.build_a2_v23_forward_intervention_actor_state(
        device=high_level.device, dtype=high_level.dtype
    )
    assert set(oracle_state) == set(A2_V23_ORACLE_OVERRIDE_FIELDS)
    oracle_action = oracle.apply_a2_v23_high_level_intervention(
        high_level, actor_state=oracle_state
    )
    assert torch.equal(oracle_action[0, :5], high_level[0, :5] + oracle_delta[0])
    assert torch.equal(oracle_action[1, :5], high_level[1, :5])

    with pytest.raises(RuntimeError, match="explicit env.config"):
        _v23_eval_stub("ORACLE_TANGENTIAL_ASSIST").build_a2_v23_forward_intervention_actor_state(
            device=high_level.device, dtype=high_level.dtype
        )
    with pytest.raises(ValueError, match="shape"):
        _v23_eval_stub(
            "ORACLE_TANGENTIAL_ASSIST",
            a2_v23_oracle_tangential_delta_raw=torch.zeros(2, 4),
            a2_v23_oracle_active_mask=torch.tensor([True, False]),
        ).build_a2_v23_forward_intervention_actor_state(
            device=high_level.device, dtype=high_level.dtype
        )


def test_posture_runner_exposes_explicit_oracle_fields_without_defaults():
    state = build_forward_intervention_actor_state(
        "ORACLE_TANGENTIAL_ASSIST",
        oracle_tangential_delta_raw=[[0.0] * 5, [0.0] * 5],
        oracle_active_mask=[True, False],
    )
    assert set(state) == set(A2_V23_ORACLE_OVERRIDE_FIELDS)
    with pytest.raises(V23Error, match="both explicit oracle"):
        build_forward_intervention_actor_state("ORACLE_TANGENTIAL_ASSIST")


def test_v23_common_config_activates_the_consumed_torque_flag():
    config_path = (
        __import__("pathlib").Path(__file__).parents[2]
        / "rl/config/ablation/wbmanip/base_v23_common.yaml"
    )
    config = OmegaConf.load(config_path)
    assert config.env.config.a2_v23_evidence_enabled is True
    assert config.env.config.a2_v23_torque_telemetry_enabled is True
    assert config.algo.trl.num_total_batches == 2500
    assert "num_total_batches" not in config.algo.config


def test_v23_p0_effort_ladder_expands_exact_dof_order():
    for effort in (100.0, 60.0, 40.0, 30.0, 25.0, 20.0):
        limits = build_effort_limit_list(effort)
        assert len(limits) == 20
        assert limits[:12] == [120.0, 120.0, 180.0] * 4
        assert limits[12:18] == [effort] * 6
        assert limits[18:] == [45.0, 45.0]


def test_v23_p0_runtime_plan_reuses_source_selectors_across_rungs(tmp_path):
    plan = build_runtime_plan(
        efforts=(100.0, 60.0),
        topologies=("canonical16", "heavy16"),
        output_root=tmp_path / "p0",
    )
    assert plan["selection_state"] == "DEFERRED_TO_EFFORT_LADDER"
    assert plan["checkpoint_load_mode"] == "full"
    assert plan["checkpoint_load_mode_effective"] == "full"
    assert len(plan["runs"]) == 4
    source_paths = {
        run["topology"]: next(
            token.split("=", 1)[1]
            for token in run["argv"]
            if token.startswith("++env.config.a2_v23_p0_scenario_manifest_path=")
        )
        for run in plan["runs"]
    }
    assert source_paths["canonical16"] != source_paths["heavy16"]
    for run in plan["runs"]:
        argv_text = " ".join(run["argv"])
        assert "robot.dof_effort_limit_list=" in argv_text
        assert "++checkpoint_load_mode=full" in run["argv"]
        assert run["argv"].count("++env.config.a2_v20_R2_evidence_enabled=false") == 1
        assert [
            token for token in run["argv"]
            if token.startswith("++env.config.a2_v20_R2_")
        ] == ["++env.config.a2_v20_R2_evidence_enabled=false"]
        assert "++env.config.a2_v23_p0_plain_scenario_enabled=true" in run["argv"]
        assert "a2_v21B_signed_probe_scenarios_enabled" not in argv_text
        assert Path(run["plain_manifest_path"]).is_absolute()
        assert run["plain_manifest"]["topology"] == run["topology"]
        assert run["checkpoint_load_mode_effective"] == "full"
        assert run["env"]["ACCELERATE_TORCH_DEVICE"] in {"cuda:0", "cuda:1", "cuda:2", "cuda:3"}
        assert "CUDA_VISIBLE_DEVICES" not in run["env"]
        assert run["retry_policy"] == "none"


def test_v23_p0_plain_manifest_runner_rows_bind_to_real_selector(tmp_path):
    helpers = _v23_scenario_helpers()
    plan = build_runtime_plan(
        efforts=(100.0,),
        topologies=("canonical16", "heavy16"),
        output_root=tmp_path / "p0",
    )
    for run in plan["runs"]:
        plain_manifest = run["plain_manifest"]
        manifest_path = tmp_path / f"{run['topology']}.json"
        manifest_path.write_text(
            json.dumps(plain_manifest, sort_keys=True), encoding="utf-8"
        )
        base = _FakeV23DoorSpawnerCfg((1.10, 0.80, 0.08, 0.15))
        task = {
            "door": _FakeV23DoorCfg(
                _FakeV23MultiAssetSpawnerCfg([base] * 16, True)
            )
        }
        helpers["TaskObjCfgDict"] = task
        env_config = {
            "a2_v23_p0_plain_scenario_enabled": True,
            "a2_v23_p0_scenario_topology": run["topology"],
            "a2_v23_p0_scenario_manifest_path": str(manifest_path.resolve()),
        }
        result = helpers["get_TaskObjCfgDict_for_door_config"](16, env_config)
        assets = result["door"].spawn.assets_cfg
        assert result["door"].spawn.random_choice is False
        assert len(assets) == 16
        assert [asset.rand_door_handle_height for asset in assets] == [
            row["handle_height_m"] for row in plain_manifest["rows"]
        ]
        assert [asset.rand_door_weight for asset in assets] == [
            row["door_weight_kg"] for row in plain_manifest["rows"]
        ]
        assert [asset.rand_hinge_drive_max_force for asset in assets] == [
            row["hinge_force_nm"] for row in plain_manifest["rows"]
        ]
        assert all(
            "sha" not in key.lower()
            and "hash" not in key.lower()
            and "digest" not in key.lower()
            for key in plain_manifest
        )
        assert all(
            all(
                "sha" not in key.lower()
                and "hash" not in key.lower()
                and "digest" not in key.lower()
                for key in row
            )
            for row in plain_manifest["rows"]
        )

        duplicate = json.loads(json.dumps(plain_manifest))
        duplicate["rows"][1]["scenario_id"] = duplicate["rows"][0]["scenario_id"]
        manifest_path.write_text(json.dumps(duplicate), encoding="utf-8")
        with pytest.raises(ValueError, match="duplicate"):
            helpers["get_TaskObjCfgDict_for_door_config"](16, env_config)

        invalid_topology = json.loads(json.dumps(plain_manifest))
        invalid_topology["topology"] = (
            "heavy16" if run["topology"] == "canonical16" else "canonical16"
        )
        manifest_path.write_text(json.dumps(invalid_topology), encoding="utf-8")
        with pytest.raises(ValueError, match="disagrees"):
            helpers["get_TaskObjCfgDict_for_door_config"](16, env_config)

        missing_field = json.loads(json.dumps(plain_manifest))
        missing_field["rows"][0].pop("hinge_force_nm")
        manifest_path.write_text(json.dumps(missing_field), encoding="utf-8")
        with pytest.raises(ValueError, match="fields must be exactly"):
            helpers["get_TaskObjCfgDict_for_door_config"](16, env_config)

        invalid_value = json.loads(json.dumps(plain_manifest))
        invalid_value["rows"][0]["door_weight_kg"] = -1.0
        manifest_path.write_text(json.dumps(invalid_value), encoding="utf-8")
        with pytest.raises(ValueError, match="finite and positive"):
            helpers["get_TaskObjCfgDict_for_door_config"](16, env_config)

        integrity_field = json.loads(json.dumps(plain_manifest))
        integrity_field["legacy_sha256"] = "not-consumed"
        manifest_path.write_text(json.dumps(integrity_field), encoding="utf-8")
        with pytest.raises(ValueError, match="forbids integrity field"):
            helpers["get_TaskObjCfgDict_for_door_config"](16, env_config)


def test_v23_p0_dispatcher_uses_explicit_selector_fields_and_preserves_default():
    dispatcher = _door_eval_dispatcher()
    default_task = {"default": object()}
    selected_task = {"selected": object()}
    calls = []

    def select_v23(num_envs, env_config):
        calls.append((num_envs, env_config))
        return selected_task

    task_module = SimpleNamespace(
        TaskObjCfgDict=default_task,
        get_TaskObjCfgDict_for_door_config=select_v23,
    )
    plain_config = {
        "a2_v23_p0_plain_scenario_enabled": True,
        "a2_v23_p0_scenario_manifest_path": "/tmp/v23-plain-manifest.json",
        "a2_v23_p0_scenario_topology": "canonical16",
    }
    assert dispatcher(task_module, plain_config, 16) is selected_task
    assert calls == [(16, plain_config)]
    assert dispatcher(task_module, {}, 16) is default_task
    assert dispatcher(
        task_module,
        {"a2_v23_p0_plain_scenario_enabled": False},
        16,
    ) is default_task

    incomplete_configs = (
        {"a2_v23_p0_plain_scenario_enabled": True},
        {
            "a2_v23_p0_plain_scenario_enabled": True,
            "a2_v23_p0_scenario_manifest_path": "/tmp/v23-plain-manifest.json",
        },
    )
    for config in incomplete_configs:
        with pytest.raises(ValueError, match="requires all explicit fields"):
            dispatcher(task_module, config, 16)

    disabled_with_extra_fields = (
        {
            "a2_v23_p0_plain_scenario_enabled": False,
            "a2_v23_p0_scenario_manifest_path": "/tmp/v23-plain-manifest.json",
        },
        {
            "a2_v23_p0_plain_scenario_enabled": False,
            "a2_v23_p0_scenario_topology": "canonical16",
        },
        {
            "a2_v23_p0_plain_scenario_enabled": False,
            "a2_v23_p0_scenario_manifest_path": "/tmp/v23-plain-manifest.json",
            "a2_v23_p0_scenario_topology": "canonical16",
        },
    )
    for config in disabled_with_extra_fields:
        with pytest.raises(ValueError, match="disabled v23 P0 plain selector"):
            dispatcher(task_module, config, 16)
