"""CPU/static contract tests for the A2+Piper Phase 2 student route."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch
import yaml
from hydra import compose, initialize_config_dir
from omegaconf import OmegaConf

from gr00t.rl.scripts.smoke_a2_student_camera import (
    parse_camera_clipping_range,
    validate_camera_config,
    validate_rgb_frame,
)
from gr00t.rl.scripts.validate_a2_teacher_checkpoint import (
    A2_ROBOT_DOF_NAMES,
    TEACHER_OBS_DIMS,
    TEACHER_OBS_SCALES,
    TEACHER_OBS_TERMS,
    _TEACHER_ACTION_DIM_EXPRESSION,
    _TEACHER_OBS_DIM_EXPRESSIONS,
    _TEACHER_STATE_SHAPES,
    build_teacher_manifest,
    validate_teacher_artifact,
    validate_teacher_config,
)
from gr00t.rl.trl.callbacks.model_save_callback import ModelSaveCallback
from gr00t.rl.trl.trainer.distill_trainer_a2_base_api import compose_a2_rollout_action
import gr00t.rl.trl.trainer.distill_trainer_a2_base_api as distill_module
from gr00t.rl.trl.modules.memory import Memory
from gr00t.rl.trl.modules.vision_actor_critic_modules_recurrent import VisionRecurrentActor
from gr00t.rl.train_agent_trl import process_output_dim_in_config
from gr00t.rl.utils.helpers import pre_process_config
from gr00t.rl.utils.running_mean_std import RunningMeanStd


ROOT = Path(__file__).resolve().parents[3]
EXP = ROOT / "gr00t/rl/config/exp/wbmanip/door_open_a2_base_dagger-lstm.yaml"
OBS = ROOT / "gr00t/rl/config/obs/wbmanip/door_open_a2_base_dagger.yaml"
CANONICAL_A2_OBS = ROOT / "gr00t/rl/config/obs/wbmanip/door_open_a2_base.yaml"


def _load(path):
    with path.open("r", encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def _term_dims(obs, terms):
    dims = obs["obs"]["obs_dims"]
    dim_map = {next(iter(entry)): next(iter(entry.values())) for entry in dims}
    result = []
    for term in terms:
        value = dim_map[term]
        result.append(6 if isinstance(value, str) and "max_stage_time" in value else int(value))
    return result


def _minimal_teacher_config():
    dims = {
        term: dim for term, dim in zip(TEACHER_OBS_TERMS, TEACHER_OBS_DIMS)
    }
    dims.update(_TEACHER_OBS_DIM_EXPRESSIONS)
    return {
        "defaults": [
            {"/env": "door_open_a2_base"},
            {"/robot": "A2_Piper/a2_piper"},
            {"/obs": "wbmanip/door_open_a2_base"},
        ],
        "env": {
            "config": {
                "max_stage_time": [1, 2, 3, 4, 5, 6],
                "a2_base": {"leg_action_dim": 12},
                "delta_action_indices": [5, 6, 7, 8, 9, 10],
                "warped_action": {"indices": [0, 1, 2, 3, 4]},
            }
        },
        "robot": {"dof_names": list(A2_ROBOT_DOF_NAMES), "dof_obs_size": 20},
        "algo": {
            "config": {
                "use_a2_base": True,
                "a2_base": {"enabled": True, "obs_dim": 1620, "action_dim": 12},
                "base_command_dim": 5,
                "manipulation_action_dim": 7,
                "actor": {
                    "_target_": "gr00t.rl.trl.modules.actor_critic_modules_recurrent.RecurrentActor",
                    "input_key": "actor_obs",
                    "running_mean_std": True,
                    "rnn_type": "lstm",
                    "rnn_hidden_dim": 256,
                    "rnn_num_layers": 2,
                    "backbone": {
                        "module_config_dict": {
                            "input_dim": ["actor_obs"],
                            "output_dim": [_TEACHER_ACTION_DIM_EXPRESSION],
                            "layer_config": {
                                "type": "MLP",
                                "hidden_dims": [512, 256, 128],
                                "activation": "SiLU",
                            },
                        }
                    },
                },
            }
        },
        "obs": {
            "obs_dict": {"actor_obs": list(TEACHER_OBS_TERMS)},
            "obs_scales": dict(TEACHER_OBS_SCALES),
            "obs_dims": [{term: dim} for term, dim in dims.items()],
        },
    }


def _full_teacher_state():
    return {
        key: torch.ones(shape, dtype=torch.float32)
        for key, shape in _TEACHER_STATE_SHAPES.items()
    }


def test_a2_student_and_teacher_dimensions_and_privilege_boundary():
    obs = _load(OBS)
    views = obs["obs"]["obs_dict"]
    actor_dims = _term_dims(obs, views["actor_obs"])
    teacher_dims = _term_dims(obs, views["teacher_obs"])
    critic_dims = _term_dims(obs, views["critic_obs"])
    assert actor_dims == [3, 3, 20, 20, 19, 6, 5, 5]
    assert sum(actor_dims) == 81
    assert sum(teacher_dims) == 133
    assert sum(critic_dims) == 138
    assert _term_dims(obs, views["a2_base_obs"]) == [1620]
    forbidden = {
        "stage",
        "complete",
        "door_dof_pos",
        "privileged_door_info",
        "relative_to_door",
        "gripper_handle_transform",
        "head_target_frame_transformer",
        "head_link",
    }
    assert not forbidden.intersection(views["actor_obs"])


def test_a2_student_noise_curriculum_schema_matches_canonical_a2_config():
    required = {
        "add_noise_currculum": False,
        "noise_initial_value": 0.05,
        "noise_value_max": 1.00,
        "noise_value_min": 0.00001,
        "soft_dof_pos_curriculum_degree": 0.00001,
        "soft_dof_pos_curriculum_level_down_threshold": 100,
        "soft_dof_pos_curriculum_level_up_threshold": 900,
    }
    student_obs = _load(OBS)["obs"]
    canonical_obs = _load(CANONICAL_A2_OBS)["obs"]
    assert {key: student_obs[key] for key in required} == required
    assert {key: student_obs[key] for key in required} == {
        key: canonical_obs[key] for key in required
    }
    assert student_obs["add_noise_currculum"] is False


def test_a2_student_exp_route_and_vision_architecture():
    exp = _load(EXP)
    defaults = exp["defaults"]
    assert {"/env": "door_open_a2_base"} in defaults
    assert {"/robot": "A2_Piper/a2_piper"} in defaults
    assert {"/obs": "wbmanip/door_open_a2_base_dagger"} in defaults
    assert {"override /trainer": "trl_distill_a2_base_api"} in defaults
    assert exp["teacher_actor_path"].endswith("REQUIRED_A2_TEACHER_CHECKPOINT.pt")
    assert exp["teacher_config_path"].endswith("REQUIRED_A2_TEACHER_CONFIG.yaml")
    assert exp["teacher_manifest_path"].endswith("REQUIRED_A2_TEACHER_MANIFEST.json")
    actor = exp["algo"]["config"]["actor"]
    assert actor["_target_"].endswith("vision_actor_critic_modules_recurrent.VisionRecurrentActor")
    assert actor["rnn_type"] == "lstm"
    assert actor["rnn_hidden_dim"] == 256
    assert actor["rnn_num_layers"] == 2
    assert actor["backbone"]["mlp_module"]["module_config_dict"]["output_dim"] == ["${algo.config.student_action_dim}"]
    assert "obj_pred_mlp" not in actor["backbone"]
    cameras = exp["simulator"]["config"]["cameras"]
    assert cameras["camera_parent"] == "trunk"
    assert cameras["camera_prim_suffix"] == "ego_camera"
    assert cameras["camera_pos"] == [0.25, 0.0, 0.14]
    assert cameras["camera_rot_wxyz"] == [0.315631686, 0.134503192, -0.390177116, -0.854428083]
    assert cameras["camera_resolutions"] == [216, 384]
    assert "camera_yaw_only" not in cameras
    assert exp["algo"]["config"]["enforce_teacher_rollout"] is True
    assert exp["algo"]["config"]["ratio_teacher_rollout"] == 1.0
    assert exp["simulator"]["config"]["randomize_dome_light"] is False
    assert exp["defaults"][3] == {"/domain_rand": "domain_rand_visual_ImageRand"}
    assert exp["domain_rand"]["image_augmentation"]["enabled"] is False


def test_a2_production_composition_predeclares_recurrent_module_slots():
    config_dir = (ROOT / "gr00t/rl/config").resolve()
    with initialize_config_dir(version_base="1.1", config_dir=str(config_dir)):
        composed = compose(
            config_name="base",
            overrides=["+exp=wbmanip/door_open_a2_base_dagger-lstm"],
        )

    # Exercise the same preprocessing and output-dimension path used before
    # train_agent_trl instantiates the actor, teacher, and critic modules.
    pre_process_config(composed)
    process_output_dim_in_config(composed)

    assert composed.robot.algo_obs_dim_dict == {
        "actor_obs": 81,
        "vision_obs": 248832,
        "teacher_obs": 133,
        "critic_obs": 138,
        "a2_base_obs": 1620,
    }
    module_dim = composed.algo.config.module_dim
    assert dict(module_dim) == {
        "actor_obs": -1,
        "teacher_obs": -1,
        "critic_obs": -1,
        "vision_feature_dim": 128,
    }
    assert OmegaConf.is_struct(module_dim) is True

    for recurrent_key in ("actor_obs", "teacher_obs", "critic_obs"):
        recurrent_mapping = module_dim.copy()
        recurrent_mapping[recurrent_key] = 256
        assert recurrent_mapping[recurrent_key] == 256
        assert module_dim[recurrent_key] == -1


def test_a2_one_update_save_override_writes_strict_checkpoint(tmp_path):
    config_dir = (ROOT / "gr00t/rl/config").resolve()
    with initialize_config_dir(version_base="1.1", config_dir=str(config_dir)):
        composed = compose(
            config_name="base",
            overrides=[
                "+exp=wbmanip/door_open_a2_base_dagger-lstm",
                "num_envs=4",
                "algo.config.num_steps_per_env=1",
                "algo.config.num_mini_batches=1",
                "algo.trl.num_total_batches=1",
                "algo.trl.per_device_train_batch_size=4",
                "callbacks.model_save.save_frequency=1",
            ],
        )

    assert int(composed.num_envs) == 4
    assert int(composed.algo.config.num_steps_per_env) == 1
    assert int(composed.algo.config.num_mini_batches) == 1
    assert int(composed.algo.trl.num_total_batches) == 1
    assert int(composed.algo.trl.per_device_train_batch_size) == 4
    assert int(composed.callbacks.model_save.save_frequency) == 1

    torch.manual_seed(0)
    policy = torch.nn.Linear(2, 1)
    model = SimpleNamespace(policy=policy, value_model=None)
    optimizer = torch.optim.Adam(policy.parameters(), lr=1.0e-2)
    loss = policy(torch.ones(4, 2)).square().mean()
    loss.backward()
    optimizer.step()

    class _CPUEnv:
        is_evaluating = False

        @staticmethod
        def get_env_state_dict():
            return {}

    state = SimpleNamespace(is_world_process_zero=True, global_step=1, log_history=[])
    callback = ModelSaveCallback(
        save_dir=tmp_path,
        save_frequency=int(composed.callbacks.model_save.save_frequency),
    )
    callback.on_step_end(
        args=SimpleNamespace(),
        state=state,
        control=SimpleNamespace(),
        model=model,
        optimizer=optimizer,
        lr_scheduler=None,
        env=_CPUEnv(),
    )

    checkpoint_path = tmp_path / "model_step_000001.pt"
    assert checkpoint_path.is_file()
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    restored_policy = torch.nn.Linear(2, 1)
    restored_policy.load_state_dict(checkpoint["policy_state_dict"], strict=True)
    assert checkpoint["optimizer_state_dict"]["state"]
    assert checkpoint["state"].global_step == 1


def test_a2_action_composition_is_12_plus_12_boundary():
    high = torch.arange(24, dtype=torch.float32).reshape(2, 12)
    legs = torch.ones(2, 12)
    result = compose_a2_rollout_action(high, legs)
    assert result.shape == (2, 24)
    assert torch.equal(result[:, :12], high)
    assert torch.equal(result[:, 12:], legs)
    with pytest.raises(ValueError, match="last dimension 12"):
        compose_a2_rollout_action(torch.zeros(2, 11), legs)


def test_teacher_manifest_generation_and_rejection(tmp_path):
    checkpoint = tmp_path / "teacher_step_010000.pt"
    config = tmp_path / "teacher_config.yaml"
    manifest = tmp_path / "teacher_manifest.json"
    torch.save(
        {
            "actor_model_state_dict": _full_teacher_state()
        },
        checkpoint,
    )
    config.write_text(yaml.safe_dump(_minimal_teacher_config()), encoding="utf-8")
    assert validate_teacher_config(config)["stage_count"] == 6
    build_teacher_manifest(checkpoint, config, "frozen-test-commit", manifest)
    result = validate_teacher_artifact(checkpoint, config, manifest)
    assert result["teacher"]["obs"]["input_dim"] == 133
    with pytest.raises(FileExistsError, match="overwrite"):
        build_teacher_manifest(checkpoint, config, "frozen-test-commit", manifest)

    drifted_config = tmp_path / "wrong_teacher_config.yaml"
    drifted = _minimal_teacher_config()
    drifted["robot"]["dof_names"][0] = "pelvis"
    drifted_config.write_text(yaml.safe_dump(drifted), encoding="utf-8")
    with pytest.raises(ValueError, match="A2_Piper 20-DOF"):
        validate_teacher_config(drifted_config)

    bad = json.loads(manifest.read_text(encoding="utf-8"))
    bad["teacher"]["obs"]["input_dim"] = 130
    manifest.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ValueError, match="input_dim must be 133"):
        validate_teacher_artifact(checkpoint, config, manifest)

    bad = json.loads(manifest.read_text(encoding="utf-8"))
    bad["teacher"]["obs"]["input_dim"] = 133
    bad["checkpoint"]["sha256"] = "0" * 64
    manifest.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ValueError, match="SHA256"):
        validate_teacher_artifact(checkpoint, config, manifest)

    incomplete = tmp_path / "teacher_incomplete.pt"
    torch.save(
        {
            "actor_model_state_dict": {
                "running_mean_std.running_mean": torch.zeros(133),
                "running_mean_std.running_var": torch.ones(133),
            }
        },
        incomplete,
    )
    with pytest.raises(ValueError, match="exact 20-key"):
        build_teacher_manifest(incomplete, config, "frozen-test-commit", tmp_path / "incomplete.json")

    wrong_std = _full_teacher_state()
    wrong_std["std"] = torch.ones(11)
    wrong_std_path = tmp_path / "teacher_wrong_std.pt"
    torch.save({"policy_state_dict": wrong_std}, wrong_std_path)
    with pytest.raises(ValueError, match="std.*shape"):
        build_teacher_manifest(wrong_std_path, config, "frozen-test-commit", tmp_path / "wrong_std.json")

    wrong_lstm = _full_teacher_state()
    wrong_lstm["memory.rnn.weight_ih_l1"] = torch.ones(1024, 255)
    wrong_lstm_path = tmp_path / "teacher_wrong_lstm.pt"
    torch.save({"policy_state_dict": wrong_lstm}, wrong_lstm_path)
    with pytest.raises(ValueError, match="weight_ih_l1.*shape"):
        build_teacher_manifest(wrong_lstm_path, config, "frozen-test-commit", tmp_path / "wrong_lstm.json")

    nonfinite = _full_teacher_state()
    nonfinite["actor_module.module.0.weight"][0, 0] = float("nan")
    nonfinite_path = tmp_path / "teacher_nonfinite.pt"
    torch.save({"policy_state_dict": nonfinite}, nonfinite_path)
    with pytest.raises(ValueError, match="non-finite"):
        build_teacher_manifest(nonfinite_path, config, "frozen-test-commit", tmp_path / "nonfinite.json")

    mutable = tmp_path / "last.pt"
    torch.save({"policy_state_dict": _full_teacher_state()}, mutable)
    with pytest.raises(ValueError, match="Mutable checkpoint"):
        build_teacher_manifest(mutable, config, "frozen-test-commit", tmp_path / "mutable.json")


def test_hermetic_production_teacher_sidecar_accepts_unresolved_shape(tmp_path):
    config_dir = (ROOT / "gr00t/rl/config").resolve()
    with initialize_config_dir(version_base="1.1", config_dir=str(config_dir)):
        composed = compose(
            config_name="base",
            overrides=["+exp=wbmanip/door_open_a2_base_lstm"],
        )
    sidecar = tmp_path / "teacher_config.yaml"
    OmegaConf.save(composed, sidecar, resolve=False)
    saved = _load(sidecar)
    assert saved["obs"]["obs_dims"][0]["dof_pos"] == "${robot.dof_obs_size}"
    semantic = validate_teacher_config(sidecar)
    assert semantic["obs_dims"] == list(TEACHER_OBS_DIMS)
    assert semantic["action_drivers"]["total_dim"] == 12


def test_teacher_config_rejects_duplicate_observation_terms(tmp_path):
    config = _minimal_teacher_config()
    config["obs"]["obs_dims"].append({"dof_pos": 20})
    path = tmp_path / "duplicate.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    with pytest.raises(ValueError, match="repeats 'dof_pos'"):
        validate_teacher_config(path)


def _checkpoint_loader_stub():
    class Policy:
        def __init__(self):
            self.calls = []

        def load_state_dict(self, state_dict, strict=False):
            self.calls.append((state_dict, strict))

    policy = Policy()
    wrapper = SimpleNamespace(policy=policy, value_model=None)
    trainer = distill_module.TRLDistillTrainerA2BaseAPI.__new__(
        distill_module.TRLDistillTrainerA2BaseAPI
    )
    trainer.accelerator = SimpleNamespace(
        device=torch.device("cpu"), unwrap_model=lambda model: model
    )
    trainer.model = wrapper
    trainer.state = SimpleNamespace(global_step=0)
    return trainer, policy


@pytest.mark.parametrize("actor_key", ["policy_state_dict", "actor_model_state_dict"])
def test_student_checkpoint_loader_accepts_one_actor_key_strictly(tmp_path, actor_key):
    trainer, policy = _checkpoint_loader_stub()
    checkpoint_path = tmp_path / f"{actor_key}.pt"
    actor_state = {"actor.weight": torch.ones(1)}
    torch.save({actor_key: actor_state}, checkpoint_path)
    loaded = trainer.load_checkpoint(checkpoint_path)
    assert actor_key in loaded
    assert policy.calls == [(actor_state, True)]


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (["not", "a", "mapping"], "must be a mapping"),
        ({"other_state": {}}, "exactly one actor state dict key"),
        (
            {"policy_state_dict": {}, "actor_model_state_dict": {}},
            "exactly one actor state dict key",
        ),
    ],
)
def test_student_checkpoint_loader_rejects_invalid_actor_key_contract(
    tmp_path, payload, message
):
    trainer, policy = _checkpoint_loader_stub()
    checkpoint_path = tmp_path / "invalid.pt"
    torch.save(payload, checkpoint_path)
    with pytest.raises(ValueError, match=message):
        trainer.load_checkpoint(checkpoint_path)
    assert policy.calls == []


def test_camera_config_parser_and_zero_frame_fail_fast():
    list_config = OmegaConf.create({"clipping": [0.1, 20.0]}).clipping
    assert parse_camera_clipping_range(list_config) == (0.1, 20.0)
    with pytest.raises(ValueError):
        parse_camera_clipping_range("(0.1, 20.0)")
    assert validate_camera_config(EXP)["parent"] == "trunk"
    frame = torch.zeros(1, 2, 2, 3, dtype=torch.uint8)
    with pytest.raises(ValueError, match="all-zero"):
        validate_rgb_frame(frame, (1, 2, 2, 3))
    frame[0, 0, 0, 0] = 1
    assert validate_rgb_frame(frame, (1, 2, 2, 3)).shape == (1, 2, 2, 3)
    for dtype in (torch.float16, torch.float32, torch.float64):
        with pytest.raises(TypeError, match="torch.uint8"):
            validate_rgb_frame(torch.ones(1, 2, 2, 3, dtype=dtype), (1, 2, 2, 3))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("camera_parent", ""),
        ("camera_prim_suffix", ""),
        ("camera_pos", [0.0, float("nan"), 0.0]),
        ("camera_rot_wxyz", [2.0, 0.0, 0.0, 0.0]),
        ("camera_types", [{"depth": True}]),
        ("camera_resolutions", [216, 384.5]),
        ("camera_update_period", -1.0),
    ],
)
def test_camera_smoke_rejects_invalid_structured_schema(tmp_path, field, value):
    config = copy.deepcopy(_load(EXP))
    config["simulator"]["config"]["cameras"][field] = value
    path = tmp_path / "camera_config.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    with pytest.raises(ValueError):
        validate_camera_config(path)


def test_a2_teacher_rollout_dispatch_is_singular(monkeypatch):
    calls = []

    def fake_process(self, rewards, dones, infos):
        calls.append(("ppo_process", rewards, dones, infos))

    def fake_rollout(self, model, obs_dict):
        calls.append(("ppo_rollout", model, obs_dict))
        return "rollout-result"

    monkeypatch.setattr(distill_module.A2TRLPPOTrainer, "_process_env_step", fake_process)
    monkeypatch.setattr(distill_module.A2TRLPPOTrainer, "_rollout_step", fake_rollout)

    class Teacher:
        def reset(self, dones):
            calls.append(("teacher_reset", dones))

        def init_rollout(self):
            calls.append(("teacher_init",))

        def clear_rollout(self):
            calls.append(("teacher_clear",))

    trainer = distill_module.TRLDistillTrainerA2BaseAPI.__new__(
        distill_module.TRLDistillTrainerA2BaseAPI
    )
    trainer.ref_model = Teacher()
    trainer._process_env_step("rewards", "dones", "infos")
    assert [entry[0] for entry in calls] == ["ppo_process", "teacher_reset"]
    calls.clear()
    assert trainer._rollout_step("model", "obs") == "rollout-result"
    assert [entry[0] for entry in calls] == ["teacher_init", "ppo_rollout", "teacher_clear"]


def test_recurrent_vision_forward_uses_batched_memory_shape_and_valid_padding_only():
    actor = VisionRecurrentActor.__new__(VisionRecurrentActor)
    torch.nn.Module.__init__(actor)
    actor.input_key = "actor_obs"
    actor.running_mean_std = RunningMeanStd((3,), per_channel=True)
    actor.vision_module_config_dict = type(
        "VisionConfig", (), {"layer_config": type("LayerConfig", (), {"type": "MLP"})()}
    )()
    actor.vision_module = torch.nn.Sequential(torch.nn.Flatten(), torch.nn.Linear(4, 2))
    actor.memory = Memory(input_size=5, type="lstm", num_layers=1, hidden_size=4)
    actor.mlp_module = torch.nn.Linear(4, 2)
    actor.train()
    batch, time = 2, 3
    actor_obs = torch.arange(batch * time * 3, dtype=torch.float32).reshape(batch, time, 3)
    vision = torch.ones(batch, time, 2, 2, 1)
    masks = torch.tensor([[True, True, False], [True, False, True]])
    obs_dict = {"actor_obs": actor_obs.clone(), "vision_obs": vision.clone()}
    output = actor.forward(obs_dict, masks=masks)
    assert output.shape == (batch, time, 2)
    assert torch.equal(obs_dict["actor_obs"], actor_obs)
    assert actor.running_mean_std.count.item() == pytest.approx(5.0)
    normalized = actor._normalize_actor_obs(actor_obs, masks)
    assert torch.equal(normalized[~masks], torch.zeros_like(normalized[~masks]))
    with pytest.raises(ValueError, match="boolean"):
        actor.forward(obs_dict, masks=masks.to(torch.int64))
    with pytest.raises(ValueError, match=r"require a \[B,T\]"):
        actor.forward(obs_dict)
    with pytest.raises(ValueError, match="at least one"):
        actor.forward(obs_dict, masks=torch.zeros(batch, time, dtype=torch.bool))


def test_dagger_bc_loss_masks_padded_recurrent_rows():
    trainer = distill_module.TRLDistillTrainerA2BaseAPI.__new__(
        distill_module.TRLDistillTrainerA2BaseAPI
    )
    trainer.bc_loss_fn = torch.nn.MSELoss()
    predicted = torch.zeros(2, 3, 12)
    target = torch.zeros(2, 3, 12)
    target[0, 0] = 2.0
    target[1, 2] = 4.0
    masks = torch.tensor([[True, False, False], [False, False, True]])
    losses = trainer._compute_dagger_bc_loss(
        {"policy_results": {"action_mean": predicted}},
        {"mb_gt_actions": target, "mb_masks": masks},
    )
    assert losses["dagger_bc_loss"].item() == pytest.approx((48.0 + 192.0) / 2.0 / 12.0)
    with pytest.raises(ValueError, match="requires mb_masks"):
        trainer._compute_dagger_bc_loss(
            {"policy_results": {"action_mean": predicted}}, {"mb_gt_actions": target}
        )
    with pytest.raises(ValueError, match="boolean"):
        trainer._compute_dagger_bc_loss(
            {"policy_results": {"action_mean": predicted}},
            {"mb_gt_actions": target, "mb_masks": masks.to(torch.int64)},
        )
