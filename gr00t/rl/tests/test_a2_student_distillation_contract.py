"""CPU/static contract tests for the A2+Piper Phase 2 student route."""

from __future__ import annotations

import ast
import copy
import inspect
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch
import yaml
from hydra import compose, initialize_config_dir
from omegaconf import OmegaConf

from gr00t.rl.scripts.seal_a2_student_distillation_artifact import (
    generate_artifact_ledger,
    main as seal_artifact_main,
    verify_artifact_ledger,
)
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
import gr00t.rl.train_agent_trl as train_module
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
    assert exp["algo"]["config"]["init_at_random_ep_len"] is False
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
    assert composed.simulator.config.render_results is False
    assert composed.simulator.config.cameras.enable_cameras is True

    for recurrent_key in ("actor_obs", "teacher_obs", "critic_obs"):
        recurrent_mapping = module_dim.copy()
        recurrent_mapping[recurrent_key] = 256
        assert recurrent_mapping[recurrent_key] == 256
        assert module_dim[recurrent_key] == -1


class _FakeSimulationApp:
    def __init__(self, events=None, close_error=None):
        self.events = events
        self.close_error = close_error
        self.calls = []

    def close(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if self.events is not None:
            self.events.append(("close", args, kwargs))
        if self.close_error is not None:
            raise self.close_error


def test_a2_simulation_app_close_false_uses_nonblocking_replicator_and_flushed_markers(
    monkeypatch,
):
    events = []

    def record_print(*args, **kwargs):
        events.append(("print", " ".join(str(arg) for arg in args), kwargs))

    monkeypatch.setattr("builtins.print", record_print)
    app = _FakeSimulationApp(events=events)
    train_module._close_simulation_app(app, False)
    assert app.calls == [((), {"wait_for_replicator": False})]
    assert events == [
        (
            "print",
            "[A2_LIFECYCLE] simulation_app_close_start "
            "render_results=false wait_for_replicator=false",
            {"flush": True},
        ),
        ("close", (), {"wait_for_replicator": False}),
        (
            "print",
            "[A2_LIFECYCLE] simulation_app_close_complete "
            "render_results=false wait_for_replicator=false",
            {"flush": True},
        ),
    ]


def test_a2_simulation_app_close_true_uses_default_writer_drain(capsys):
    app = _FakeSimulationApp()
    train_module._close_simulation_app(app, True)
    assert app.calls == [((), {})]
    assert capsys.readouterr().out.splitlines() == [
        "[A2_LIFECYCLE] simulation_app_close_start "
        "render_results=true wait_for_replicator=true",
        "[A2_LIFECYCLE] simulation_app_close_complete "
        "render_results=true wait_for_replicator=true",
    ]


@pytest.mark.parametrize("invalid_render_results", [None, 0, "false"])
def test_a2_simulation_app_close_rejects_non_bool_before_marker_or_close(
    capsys, invalid_render_results
):
    app = _FakeSimulationApp()
    with pytest.raises(TypeError, match="exact bool"):
        train_module._close_simulation_app(app, invalid_render_results)
    assert app.calls == []
    assert capsys.readouterr().out == ""


def test_a2_simulation_app_close_missing_render_route_fails_before_app_invocation(capsys):
    app = _FakeSimulationApp()
    config = SimpleNamespace(simulator=SimpleNamespace(config=SimpleNamespace()))
    with pytest.raises(AttributeError):
        train_module._close_simulation_app(
            app,
            config.simulator.config.render_results,
        )
    assert app.calls == []
    assert capsys.readouterr().out == ""


def test_a2_simulation_app_close_propagates_error_without_complete_marker(capsys):
    error = RuntimeError("close failed")
    app = _FakeSimulationApp(close_error=error)
    with pytest.raises(RuntimeError, match="close failed") as exc_info:
        train_module._close_simulation_app(app, False)
    assert exc_info.value is error
    assert app.calls == [((), {"wait_for_replicator": False})]
    output = capsys.readouterr().out
    assert "simulation_app_close_start" in output
    assert "simulation_app_close_complete" not in output


def test_a2_simulation_app_close_source_order_and_single_main_ownership():
    source = Path(train_module.__file__).read_text(encoding="utf-8")
    main_source = source[source.index("@hydra.main") : source.index('if __name__ == "__main__"')]
    post_train = main_source.split("trainer.train()", 1)[1]
    assert post_train.count("_close_simulation_app(") == 1
    assert "simulation_app.close(" not in post_train
    assert "config.simulator.config.render_results" in post_train
    assert source.count("simulation_app.close(wait_for_replicator=False)") == 1
    assert source.count("simulation_app.close()") == 1


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



def _student_sealer_inputs(tmp_path, step=7, serialized_step=None):
    tmp_path.mkdir(parents=True, exist_ok=True)
    if serialized_step is None:
        serialized_step = step
    checkpoint = tmp_path / f"model_step_{step:06d}.pt"
    torch.save(
        {
            "policy_state_dict": {
                "layer.weight": torch.ones(2, dtype=torch.float32),
                "layer.bias": torch.zeros(2, dtype=torch.float32),
            },
            "optimizer_state_dict": {
                "state": {0: {"step": torch.tensor(float(step))}},
                "param_groups": [{"lr": 1.0e-3}],
            },
            "state": {"global_step": serialized_step},
        },
        checkpoint,
    )
    resolved_config = tmp_path / "resolved_config.yaml"
    teacher_checkpoint = tmp_path / "teacher_model_step_001000.pt"
    teacher_config = tmp_path / "teacher_config.yaml"
    teacher_manifest = tmp_path / "teacher_manifest.json"
    rank_logs = [tmp_path / "rank0.log", tmp_path / "rank1.log"]
    training_logs = [tmp_path / "training.log", tmp_path / "training_metrics.log"]
    for path, contents in (
        (resolved_config, "resolved: true\n"),
        (teacher_checkpoint, "teacher bytes\n"),
        (teacher_config, "teacher: config\n"),
        (teacher_manifest, "{\"schema_version\": \"test\"}\n"),
        (rank_logs[0], "rank=0\n"),
        (rank_logs[1], "rank=1\n"),
        (training_logs[0], "step=7\n"),
        (training_logs[1], "loss=0.1\n"),
    ):
        path.write_text(contents, encoding="utf-8")
    return {
        "checkpoint_path": checkpoint,
        "expected_global_step": step,
        "resolved_config_path": resolved_config,
        "teacher_checkpoint_path": teacher_checkpoint,
        "teacher_config_path": teacher_config,
        "teacher_manifest_path": teacher_manifest,
        "rank_logs": rank_logs,
        "training_logs": training_logs,
        "base_sha": "4b29411101a1de4949f42140b61f1ccb4c2e67e7",
        "candidate_id": "candidate-a2-v13-test",
        "source_root": tmp_path,
        "output_path": tmp_path / "student_artifact_ledger.json",
    }


def test_a2_source_identity_and_headless_experience_are_worktree_bound(tmp_path, monkeypatch):
    assert train_module.SOURCE_ROOT == ROOT
    experience = train_module._headless_rendering_experience_path()
    assert experience.is_absolute()
    assert experience == (ROOT / "gr00t/rl/apps/phc.isaaclab.python.headless.rendering.kit").resolve()
    assert "/IsaacLab/apps/" not in str(experience)

    missing_root = tmp_path / "missing-source"
    missing_root.mkdir()
    monkeypatch.setattr(train_module, "SOURCE_ROOT", missing_root)
    with pytest.raises(FileNotFoundError, match="experience file is missing"):
        train_module._headless_rendering_experience_path()

    wrong_package = tmp_path / "wrong" / "gr00t"
    wrong_package.mkdir(parents=True)
    wrong_init = wrong_package / "__init__.py"
    wrong_init.write_text("# wrong package\n", encoding="utf-8")
    monkeypatch.setattr(train_module.gr00t, "__file__", str(wrong_init))
    with pytest.raises(RuntimeError, match="source identity mismatch"):
        train_module._verify_source_identity()


def test_a2_student_artifact_ledger_generate_verify_and_cli(tmp_path, capsys):
    kwargs = _student_sealer_inputs(tmp_path)
    ledger = generate_artifact_ledger(**kwargs)
    assert ledger["schema_version"] == "a2_student_distillation_artifact_ledger.v1"
    final = ledger["artifacts"]["final_checkpoint"]
    assert final["global_step"] == 7
    assert final["policy_tensor_count"] == 2
    assert final["policy_element_count"] == 4
    assert final["optimizer_state_entries"] == 1
    assert {"sha256", "size", "mtime_ns"}.issubset(final)
    assert verify_artifact_ledger(kwargs["output_path"])["candidate_id"] == kwargs["candidate_id"]

    with pytest.raises(FileExistsError, match="overwrite"):
        generate_artifact_ledger(**kwargs)
    symlink_output = tmp_path / "ledger-symlink.json"
    symlink_output.symlink_to(kwargs["output_path"])
    kwargs["output_path"] = symlink_output
    with pytest.raises(FileExistsError, match="symlink"):
        generate_artifact_ledger(**kwargs)

    cli_kwargs = _student_sealer_inputs(tmp_path / "cli")
    cli_output = cli_kwargs["output_path"]
    seal_artifact_main(
        [
            "generate",
            "--checkpoint",
            str(cli_kwargs["checkpoint_path"]),
            "--expected-global-step",
            str(cli_kwargs["expected_global_step"]),
            "--resolved-config",
            str(cli_kwargs["resolved_config_path"]),
            "--teacher-checkpoint",
            str(cli_kwargs["teacher_checkpoint_path"]),
            "--teacher-config",
            str(cli_kwargs["teacher_config_path"]),
            "--teacher-manifest",
            str(cli_kwargs["teacher_manifest_path"]),
            "--rank-log",
            str(cli_kwargs["rank_logs"][0]),
            "--rank-log",
            str(cli_kwargs["rank_logs"][1]),
            "--training-log",
            str(cli_kwargs["training_logs"][0]),
            "--training-log",
            str(cli_kwargs["training_logs"][1]),
            "--base-sha",
            cli_kwargs["base_sha"],
            "--candidate-id",
            cli_kwargs["candidate_id"],
            "--source-root",
            str(cli_kwargs["source_root"]),
            "--output",
            str(cli_output),
        ]
    )
    assert cli_output.is_file()
    seal_artifact_main(["verify", "--ledger", str(cli_output)])
    assert "a2_student_distillation_artifact_ledger.v1" in capsys.readouterr().out


def test_a2_student_artifact_ledger_accepts_real_checkpoint_state_attribute(tmp_path):
    kwargs = _student_sealer_inputs(tmp_path)
    payload = torch.load(kwargs["checkpoint_path"], map_location="cpu", weights_only=False)
    payload["state"] = SimpleNamespace(global_step=7)
    torch.save(payload, kwargs["checkpoint_path"])
    generate_artifact_ledger(**kwargs)
    assert verify_artifact_ledger(kwargs["output_path"])["expected_global_step"] == 7


def test_a2_student_artifact_ledger_rejects_mutated_log_and_missing_artifact(tmp_path):
    kwargs = _student_sealer_inputs(tmp_path)
    generate_artifact_ledger(**kwargs)
    kwargs["rank_logs"][0].write_text("mutated\n", encoding="utf-8")
    with pytest.raises(ValueError, match="identity mismatch"):
        verify_artifact_ledger(kwargs["output_path"])

    missing_kwargs = _student_sealer_inputs(tmp_path / "missing")
    missing_kwargs["teacher_manifest_path"].unlink()
    with pytest.raises(FileNotFoundError, match="Teacher manifest"):
        generate_artifact_ledger(**missing_kwargs)


@pytest.mark.parametrize(
    "case",
    ["last", "wrong_filename_step", "wrong_serialized_step", "nonfinite", "empty_optimizer"],
)
def test_a2_student_artifact_ledger_rejects_invalid_final_checkpoint(tmp_path, case):
    kwargs = _student_sealer_inputs(tmp_path, serialized_step=8 if case == "wrong_serialized_step" else 7)
    checkpoint = kwargs["checkpoint_path"]
    if case == "last":
        mutable = checkpoint.with_name("last.pt")
        checkpoint.rename(mutable)
        kwargs["checkpoint_path"] = mutable
    elif case == "wrong_filename_step":
        wrong = checkpoint.with_name("model_step_000008.pt")
        checkpoint.rename(wrong)
        kwargs["checkpoint_path"] = wrong
    elif case == "nonfinite":
        payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
        payload["policy_state_dict"]["layer.weight"][0] = float("nan")
        torch.save(payload, checkpoint)
    elif case == "empty_optimizer":
        payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
        payload["optimizer_state_dict"]["state"] = {}
        torch.save(payload, checkpoint)

    with pytest.raises(ValueError):
        generate_artifact_ledger(**kwargs)


def test_a2_student_artifact_ledger_rejects_zero_element_policy_on_generate_and_verify(tmp_path):
    kwargs = _student_sealer_inputs(tmp_path / "generate")
    payload = torch.load(kwargs["checkpoint_path"], map_location="cpu", weights_only=False)
    payload["policy_state_dict"]["empty"] = torch.empty(0, dtype=torch.float32)
    torch.save(payload, kwargs["checkpoint_path"])
    with pytest.raises(ValueError, match="non-empty"):
        generate_artifact_ledger(**kwargs)

    kwargs = _student_sealer_inputs(tmp_path / "verify")
    generate_artifact_ledger(**kwargs)
    ledger = json.loads(kwargs["output_path"].read_text(encoding="utf-8"))
    ledger["artifacts"]["final_checkpoint"]["policy_element_count"] = 0
    kwargs["output_path"].write_text(json.dumps(ledger), encoding="utf-8")
    with pytest.raises(ValueError, match="policy_element_count"):
        verify_artifact_ledger(kwargs["output_path"])


def test_a2_student_artifact_ledger_rejects_zero_byte_logs_and_symlink_inputs(tmp_path):
    kwargs = _student_sealer_inputs(tmp_path)
    kwargs["rank_logs"][0].write_bytes(b"")
    with pytest.raises(ValueError, match="non-empty"):
        generate_artifact_ledger(**kwargs)

    kwargs = _student_sealer_inputs(tmp_path / "verify")
    generate_artifact_ledger(**kwargs)
    kwargs["training_logs"][0].write_bytes(b"")
    with pytest.raises(ValueError, match="recorded size|non-empty"):
        verify_artifact_ledger(kwargs["output_path"])

    kwargs = _student_sealer_inputs(tmp_path / "recorded")
    generate_artifact_ledger(**kwargs)
    ledger = json.loads(kwargs["output_path"].read_text(encoding="utf-8"))
    ledger["logs"]["rank"][0]["size"] = 0
    kwargs["output_path"].write_text(json.dumps(ledger), encoding="utf-8")
    with pytest.raises(ValueError, match="recorded size"):
        verify_artifact_ledger(kwargs["output_path"])

    kwargs = _student_sealer_inputs(tmp_path / "input-symlink")
    symlink = kwargs["teacher_config_path"].with_name("teacher_config_link.yaml")
    symlink.symlink_to(kwargs["teacher_config_path"])
    kwargs["teacher_config_path"] = symlink
    with pytest.raises(ValueError, match="symlink"):
        generate_artifact_ledger(**kwargs)


def test_a2_student_artifact_ledger_rejects_unexpected_identity_and_log_keys(tmp_path):
    kwargs = _student_sealer_inputs(tmp_path)
    generate_artifact_ledger(**kwargs)
    ledger = json.loads(kwargs["output_path"].read_text(encoding="utf-8"))
    ledger["artifacts"]["resolved_config"]["unexpected"] = "reject"
    kwargs["output_path"].write_text(json.dumps(ledger), encoding="utf-8")
    with pytest.raises(ValueError, match="unexpected keys"):
        verify_artifact_ledger(kwargs["output_path"])

    kwargs = _student_sealer_inputs(tmp_path / "category")
    generate_artifact_ledger(**kwargs)
    ledger = json.loads(kwargs["output_path"].read_text(encoding="utf-8"))
    ledger["logs"]["extra"] = []
    kwargs["output_path"].write_text(json.dumps(ledger), encoding="utf-8")
    with pytest.raises(ValueError, match="unexpected log categories"):
        verify_artifact_ledger(kwargs["output_path"])

    kwargs = _student_sealer_inputs(tmp_path / "ledger-link")
    generate_artifact_ledger(**kwargs)
    symlink = tmp_path / "ledger-link.json"
    symlink.symlink_to(kwargs["output_path"])
    with pytest.raises(ValueError, match="symlink"):
        verify_artifact_ledger(symlink)


def test_a2_student_artifact_ledger_rejects_symlinked_parent_components(tmp_path):
    kwargs = _student_sealer_inputs(tmp_path / "artifact")
    artifact_parent = tmp_path / "artifact-parent"
    artifact_parent.symlink_to(kwargs["teacher_config_path"].parent, target_is_directory=True)
    kwargs["teacher_config_path"] = artifact_parent / kwargs["teacher_config_path"].name
    with pytest.raises(ValueError, match="symlink component"):
        generate_artifact_ledger(**kwargs)

    kwargs = _student_sealer_inputs(tmp_path / "source")
    source_parent = tmp_path / "source-parent"
    source_parent.symlink_to(kwargs["source_root"], target_is_directory=True)
    kwargs["source_root"] = source_parent
    with pytest.raises(ValueError, match="symlink component"):
        generate_artifact_ledger(**kwargs)

    kwargs = _student_sealer_inputs(tmp_path / "ledger")
    generate_artifact_ledger(**kwargs)
    ledger_parent = tmp_path / "ledger-parent"
    ledger_parent.symlink_to(kwargs["output_path"].parent, target_is_directory=True)
    linked_ledger = ledger_parent / kwargs["output_path"].name
    with pytest.raises(ValueError, match="symlink component"):
        verify_artifact_ledger(linked_ledger)

    kwargs = _student_sealer_inputs(tmp_path / "output")
    output_parent = tmp_path / "output-parent"
    output_parent.symlink_to(kwargs["output_path"].parent, target_is_directory=True)
    kwargs["output_path"] = output_parent / "new-ledger.json"
    with pytest.raises(ValueError, match="symlink component"):
        generate_artifact_ledger(**kwargs)


def test_a2_student_artifact_ledger_rejects_dotdot_symlink_bypass_and_allows_missing_parent(
    tmp_path, monkeypatch
):
    kwargs = _student_sealer_inputs(tmp_path / "absolute-dotdot")
    alias = tmp_path / "absolute-alias"
    alias.symlink_to(kwargs["output_path"].parent, target_is_directory=True)
    kwargs["output_path"] = tmp_path / "missing" / ".." / "absolute-alias" / "ledger.json"
    with pytest.raises(ValueError, match="parent component"):
        generate_artifact_ledger(**kwargs)
    assert not (kwargs["output_path"].parent.resolve() / "ledger.json").exists()

    pre_dotdot = _student_sealer_inputs(tmp_path / "pre-dotdot")
    redirect = pre_dotdot["source_root"] / "redirect" / "deep"
    redirect.mkdir(parents=True)
    pre_alias = pre_dotdot["source_root"] / "alias"
    pre_alias.symlink_to(redirect, target_is_directory=True)
    pre_dotdot["output_path"] = pre_dotdot["source_root"] / "alias" / ".." / "escaped" / "ledger.json"
    with pytest.raises(ValueError, match="parent component"):
        generate_artifact_ledger(**pre_dotdot)
    assert not (redirect / "ledger.json").exists()
    assert not (pre_dotdot["source_root"] / "escaped" / "ledger.json").exists()

    relative = _student_sealer_inputs(tmp_path / "relative-dotdot")
    monkeypatch.chdir(relative["source_root"])
    relative_alias = relative["source_root"] / "relative-alias"
    relative_alias.symlink_to(relative["source_root"], target_is_directory=True)
    relative["output_path"] = Path("missing/../relative-alias/ledger.json")
    with pytest.raises(ValueError, match="parent component"):
        generate_artifact_ledger(**relative)
    assert not (relative["source_root"] / "ledger.json").exists()

    missing_parent = _student_sealer_inputs(tmp_path / "ordinary-missing")
    monkeypatch.chdir(missing_parent["source_root"])
    missing_parent["output_path"] = Path("ordinary-missing-parent/ledger.json")
    assert not Path("ordinary-missing-parent").exists()
    generate_artifact_ledger(**missing_parent)
    assert Path("ordinary-missing-parent/ledger.json").is_file()
    assert verify_artifact_ledger(missing_parent["output_path"])["expected_global_step"] == 7


def test_a2_student_artifact_ledger_accepts_relative_non_symlink_paths(tmp_path, monkeypatch):
    kwargs = _student_sealer_inputs(tmp_path / "relative")
    root = kwargs["source_root"]
    monkeypatch.chdir(root)
    relative = dict(kwargs)
    for key in (
        "checkpoint_path",
        "resolved_config_path",
        "teacher_checkpoint_path",
        "teacher_config_path",
        "teacher_manifest_path",
    ):
        relative[key] = Path(relative[key]).relative_to(root)
    relative["rank_logs"] = [Path(path).relative_to(root) for path in relative["rank_logs"]]
    relative["training_logs"] = [Path(path).relative_to(root) for path in relative["training_logs"]]
    relative["source_root"] = Path(".")
    relative["output_path"] = Path("relative-ledger.json")
    generate_artifact_ledger(**relative)
    assert verify_artifact_ledger(relative["output_path"])["expected_global_step"] == 7


def test_a2_student_artifact_ledger_rejects_top_level_schema_drift(tmp_path):
    kwargs = _student_sealer_inputs(tmp_path)
    generate_artifact_ledger(**kwargs)
    ledger = json.loads(kwargs["output_path"].read_text(encoding="utf-8"))
    ledger["unverified_identity"] = {"path": "/definitely/missing/unverified"}
    del ledger["source_root"]
    kwargs["output_path"].write_text(json.dumps(ledger), encoding="utf-8")
    with pytest.raises(ValueError, match="top-level schema"):
        verify_artifact_ledger(kwargs["output_path"])


def _parse_kit_extension_folders(path):
    """Narrow native-Kit parser for the extension folder list we own."""
    text = Path(path).read_text(encoding="utf-8")
    blocks = list(
        re.finditer(
            r"(?ms)^\[settings\.app\.exts\]\s*^folders\s*=\s*\[(.*?)^\]",
            text,
        )
    )
    if len(blocks) != 1:
        raise ValueError(f"expected exactly one native Kit extension folder block in {path}")
    body = blocks[0].group(1)
    if re.search(r"^\[", body, re.MULTILINE):
        raise ValueError(f"unexpected Kit table inside extension folder block: {path}")
    folders = re.findall(r'"([^"\n]*)"', body)
    if not folders:
        raise ValueError(f"native Kit extension folder block is empty: {path}")
    return text, folders


def test_candidate_local_kit_dependency_closure_and_native_parse():
    primary = ROOT / "gr00t/rl/apps/phc.isaaclab.python.headless.rendering.kit"
    base = ROOT / "gr00t/rl/apps/isaaclab.python.headless.kit"
    canonical_source = "/home/baoquanc/workspace/IsaacLab/source"
    assert primary.is_file()
    assert base.is_file()
    assert Path(canonical_source).is_dir()
    primary_text, primary_folders = _parse_kit_extension_folders(primary)
    base_text, base_folders = _parse_kit_extension_folders(base)
    assert "${app}" in primary_folders
    assert "${app}" in base_folders
    for text in (primary_text, base_text):
        assert '"${app}"' in text
        assert canonical_source in text
        assert '"${app}/../source"' not in text
    assert '"isaaclab.python.headless" = {}' in primary_text


def _single_visible_env(**overrides):
    env = {
        "A2_GPU_BINDING_MODE": "single-visible-cuda0-v2",
        "CUDA_VISIBLE_DEVICES": "0",
        "CUDA_DEVICE_ORDER": "PCI_BUS_ID",
        "A2_EXPECTED_WORLD_SIZE": "1",
        "A2_EXPECTED_HOST_GPU_INDEX": "0",
        "A2_EXPECTED_LOGICAL_GPU_INDEX": "0",
        "A2_EXPECTED_GPU_UUID": train_module._A2_GPU_UUID,
    }
    env.update(overrides)
    return env


def _a2_identity():
    return {
        "mode": train_module._A2_GPU_BINDING_MODE,
        "world_size": 1,
        "rank": 0,
        "local_rank": 0,
        "host_gpu_index": 0,
        "logical_gpu_index": 0,
        "pinned_uuid": train_module._A2_GPU_UUID,
    }


def test_a2_single_visible_binding_maps_exact_identity_and_marker(capsys):
    identity = train_module._validate_a2_gpu_binding(_single_visible_env())
    assert identity == _a2_identity()
    output = capsys.readouterr().out
    assert "[A2_GPU_BINDING_ENV]" in output
    assert "mode=single-visible-cuda0-v2" in output
    assert "CVD=0 host_gpu_index=0 logical_gpu_index=0" in output
    assert f"pinned_uuid={train_module._A2_GPU_UUID}" in output
    assert "world_size=1" in output


def test_a2_binding_absence_preserves_generic_route():
    assert train_module._validate_a2_gpu_binding({}) is None


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("A2_GPU_BINDING_MODE", "host-physical-v1"),
        ("CUDA_VISIBLE_DEVICES", ""),
        ("CUDA_VISIBLE_DEVICES", "1"),
        ("CUDA_DEVICE_ORDER", "FASTEST_FIRST"),
        ("A2_EXPECTED_WORLD_SIZE", "2"),
        ("A2_EXPECTED_HOST_GPU_INDEX", "1"),
        ("A2_EXPECTED_LOGICAL_GPU_INDEX", "1"),
        ("A2_EXPECTED_GPU_UUID", "GPU-wrong"),
    ],
)
def test_a2_single_visible_binding_rejects_wrong_schema_fields(field, value):
    with pytest.raises(RuntimeError, match="A2"):
        train_module._validate_a2_gpu_binding(_single_visible_env(**{field: value}))


@pytest.mark.parametrize(
    "missing",
    [
        "A2_GPU_BINDING_MODE",
        "CUDA_VISIBLE_DEVICES",
        "CUDA_DEVICE_ORDER",
        "A2_EXPECTED_WORLD_SIZE",
        "A2_EXPECTED_HOST_GPU_INDEX",
        "A2_EXPECTED_LOGICAL_GPU_INDEX",
        "A2_EXPECTED_GPU_UUID",
    ],
)
def test_a2_single_visible_binding_rejects_partial_schema(missing):
    env = _single_visible_env()
    del env[missing]
    with pytest.raises(RuntimeError, match="A2"):
        train_module._validate_a2_gpu_binding(env)


@pytest.mark.parametrize(
    "field",
    [
        "WORLD_SIZE",
        "RANK",
        "LOCAL_RANK",
        "LOCAL_WORLD_SIZE",
        "MASTER_ADDR",
        "MASTER_PORT",
        "ACCELERATE_TORCH_DEVICE",
        "ACCELERATE_BYPASS_DEVICE_MAP",
    ],
)
def test_a2_single_visible_binding_rejects_external_distributed_or_accelerate_env(field):
    with pytest.raises(RuntimeError, match="A2"):
        train_module._validate_a2_gpu_binding(_single_visible_env(**{field: "1"}))


@pytest.mark.parametrize(
    "field",
    ["A2_EXPECTED_RANK", "A2_EXPECTED_MASTER_PORT", "A2_GPU_BINDING_EXTRA"],
)
def test_a2_single_visible_binding_rejects_unknown_a2_fields(field):
    with pytest.raises(RuntimeError, match="unexpected"):
        train_module._validate_a2_gpu_binding(_single_visible_env(**{field: "0"}))


def test_a2_gpu_binding_nvidia_smi_parser_is_strict_and_non_shell(monkeypatch):
    calls = []

    def fake_run(*args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(stdout=f"0, {train_module._A2_GPU_UUID}\n", stderr="")

    monkeypatch.setattr(train_module.subprocess, "run", fake_run)
    assert train_module._query_nvidia_smi_gpu_uuids() == {0: train_module._A2_GPU_UUID}
    assert calls[0][0][0] == [
        "/usr/bin/nvidia-smi",
        "--query-gpu=index,uuid",
        "--format=csv,noheader,nounits",
    ]
    assert calls[0][1]["shell"] is False
    monkeypatch.setattr(
        train_module.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(stdout="malformed", stderr=""),
    )
    with pytest.raises(RuntimeError, match="malformed"):
        train_module._query_nvidia_smi_gpu_uuids()


def test_a2_gpu_binding_nvidia_smi_rejects_host_uuid_mismatch(monkeypatch):
    monkeypatch.setattr(train_module, "_query_nvidia_smi_gpu_uuids", lambda: {0: "GPU-wrong"})
    with pytest.raises(RuntimeError, match="UUID mismatch"):
        train_module._validate_a2_nvidia_smi_uuid(_a2_identity())


def test_a2_gpu_binding_accelerator_app_launcher_and_order_contracts():
    source = Path(train_module.__file__).read_text(encoding="utf-8")
    assert 'A2_GPU_BINDING_MODE = "single-visible-cuda0-v2"' in source
    assert '"CUDA_VISIBLE_DEVICES"' in source
    assert "A2_EXPECTED_HOST_GPU_INDEX" in source
    assert "A2_EXPECTED_LOGICAL_GPU_INDEX" in source
    assert "args_cli.multi_gpu = False" in source
    assert "args_cli.distributed = False" in source
    assert 'args_cli.device = "cuda:0"' in source
    assert "app_launcher.device_id" in source
    assert '("/renderer/activeGpu", int, "get_as_int")' in source
    assert '("/physics/cudaDevice", int, "get_as_int")' in source
    assert '("/renderer/multiGpu/enabled", bool, "get_as_bool")' in source
    assert '("/renderer/multiGpu/autoEnable", bool, "get_as_bool")' in source
    assert '("/renderer/multiGpu/maxGpuCount", int, "get_as_int")' in source
    assert "_read_a2_carbonite_settings(settings)" in source
    assert "host-physical-v1" not in source
    assert "_A2_GPU2_UUID" not in source
    assert "_A2_GPU3_UUID" not in source
    assert "A2_EXPECTED_PHYSICAL_GPU_MAP" not in source
    assert "A2_EXPECTED_GPU_UUID_MAP" not in source


class _FakeCarboniteSettings:
    def __init__(self, raw_values, typed_values=None):
        self.raw_values = dict(raw_values)
        self.typed_values = dict(typed_values or {})
        self.raw_calls = []
        self.typed_calls = []

    def get(self, path):
        self.raw_calls.append(path)
        return self.raw_values.get(path)

    def get_as_int(self, path):
        self.typed_calls.append(("int", path))
        return self.typed_values.get(path, 0)

    def get_as_bool(self, path):
        self.typed_calls.append(("bool", path))
        return self.typed_values.get(path, False)


def _fake_carbonite(raw_values, typed_values=None):
    settings = _FakeCarboniteSettings(raw_values, typed_values)
    carb_module = SimpleNamespace(
        settings=SimpleNamespace(get_settings=lambda: settings)
    )
    return carb_module, settings


def _valid_carbonite_values():
    return {
        "/renderer/activeGpu": 0,
        "/physics/cudaDevice": 0,
        "/renderer/multiGpu/enabled": False,
        "/renderer/multiGpu/autoEnable": False,
        "/renderer/multiGpu/maxGpuCount": 1,
    }


@pytest.mark.parametrize("missing_path", sorted(_valid_carbonite_values()))
def test_a2_kit_binding_rejects_missing_carbonite_keys_before_typed_defaults(
    monkeypatch, capsys, missing_path
):
    raw_values = _valid_carbonite_values()
    del raw_values[missing_path]
    carb_module, settings = _fake_carbonite(raw_values)
    monkeypatch.setitem(sys.modules, "carb", carb_module)
    monkeypatch.setattr(train_module, "_A2_KIT_BINDING_EMITTED", False)
    with pytest.raises(RuntimeError, match="setting is missing"):
        train_module._validate_a2_app_launcher_binding(
            SimpleNamespace(device_id=0),
            SimpleNamespace(device=torch.device("cuda:0")),
            _a2_identity(),
        )
    assert ("int", missing_path) not in settings.typed_calls
    assert ("bool", missing_path) not in settings.typed_calls
    assert "[A2_GPU_BINDING_KIT]" not in capsys.readouterr().out


@pytest.mark.parametrize(
    ("wrong_path", "wrong_value"),
    [
        ("/renderer/activeGpu", False),
        ("/physics/cudaDevice", True),
        ("/renderer/multiGpu/enabled", 0),
        ("/renderer/multiGpu/autoEnable", 1),
        ("/renderer/multiGpu/maxGpuCount", 1.0),
    ],
)
def test_a2_kit_binding_rejects_wrong_carbonite_python_types(
    monkeypatch, wrong_path, wrong_value
):
    raw_values = _valid_carbonite_values()
    raw_values[wrong_path] = wrong_value
    carb_module, _ = _fake_carbonite(raw_values)
    monkeypatch.setitem(sys.modules, "carb", carb_module)
    monkeypatch.setattr(train_module, "_A2_KIT_BINDING_EMITTED", False)
    with pytest.raises(RuntimeError, match="wrong Python type"):
        train_module._validate_a2_app_launcher_binding(
            SimpleNamespace(device_id=0),
            SimpleNamespace(device=torch.device("cuda:0")),
            _a2_identity(),
        )


def test_a2_kit_binding_reads_typed_values_only_after_presence_and_emits_marker_once(
    monkeypatch, capsys
):
    raw_values = _valid_carbonite_values()
    typed_values = _valid_carbonite_values()
    carb_module, settings = _fake_carbonite(raw_values, typed_values)
    monkeypatch.setitem(sys.modules, "carb", carb_module)
    monkeypatch.setattr(train_module, "_A2_KIT_BINDING_EMITTED", False)
    app_launcher = SimpleNamespace(device_id=0)
    accelerator = SimpleNamespace(device=torch.device("cuda:0"))
    identity = _a2_identity()
    train_module._validate_a2_app_launcher_binding(app_launcher, accelerator, identity)
    train_module._validate_a2_app_launcher_binding(app_launcher, accelerator, identity)
    output = capsys.readouterr().out
    assert output.count("[A2_GPU_BINDING_KIT]") == 1
    assert settings.raw_calls == list(_valid_carbonite_values()) * 2
    assert len(settings.typed_calls) == len(_valid_carbonite_values()) * 2


def test_a2_gpu_binding_validation_order_precedes_imports_and_standard_parser():
    source = Path(train_module.__file__).read_text(encoding="utf-8")
    binding = source.index("_validate_a2_nvidia_smi_uuid(A2_GPU_BINDING)")
    torch_bind = source.index("_prepare_a2_torch_device(A2_GPU_BINDING)")
    accelerate_state = source.index("_validate_a2_preinitialized_accelerate_state(A2_GPU_BINDING)")
    package_import = source.index("import gr00t")
    parser = source.index("HfArgumentParser((ScriptArguments, PPOConfig, ModelConfig))")
    post_parse = source.index("_validate_a2_ppo_config(training_args, A2_GPU_BINDING)")
    assert binding < torch_bind < accelerate_state < package_import < parser < post_parse
    assert "_make_a2_partial_state" not in source
    assert "_a2_ppo_config_device_patch" not in source
    assert "_configure_a2_ppo_devices" not in source


def test_a2_gpu_binding_seed_scope_and_post_prepare_contracts():
    train_source = Path(train_module.__file__).read_text(encoding="utf-8")
    ppo_source = Path(ROOT / "gr00t/rl/trl/trainer/ppo_trainer_a2_base_api.py").read_text(encoding="utf-8")
    train_tree, ppo_tree = ast.parse(train_source), ast.parse(ppo_source)
    train_seed = next(n for n in train_tree.body if isinstance(n, ast.FunctionDef) and n.name == "_seed_a2_local_generators")
    ppo_seed = next(n for n in ppo_tree.body if isinstance(n, ast.FunctionDef) and n.name == "_seed_a2_local_generators")
    for source, node in ((train_source, train_seed), (ppo_source, ppo_seed)):
        segment = ast.get_source_segment(source, node)
        assert "torch.manual_seed(" not in segment
        assert "torch.manual_seed_all(" not in segment
        assert "torch.default_generator.manual_seed(" in segment
        assert "torch.cuda.manual_seed(" in segment
    assert "_validate_a2_single_gpu_binding" in ppo_source
    assert "[A2_SINGLE_CUDA_BINDING]" in ppo_source
    assert "_validate_a2_ddp_binding" not in ppo_source
    assert "[A2_DDP_BINDING]" not in ppo_source
    assert "from torch.nn.parallel import DistributedDataParallel" not in ppo_source
    assert 'getattr(model, "device_ids", None) is not None' in ppo_source


def test_a2_cuda_uuid_normalizer_uses_bytes_payload_not_string(monkeypatch):
    import uuid

    expected = train_module._A2_GPU_UUID

    class FakeCUuuid:
        bytes = list(uuid.UUID(expected.removeprefix("GPU-")).bytes)

        def __str__(self):
            return "<torch._C._CUuuid repr that must not be parsed>"

    assert train_module._canonicalize_a2_cuda_uuid(FakeCUuuid()) == expected


@pytest.mark.parametrize(
    "value",
    [
        SimpleNamespace(),
        SimpleNamespace(bytes=b"\x00" * 15),
        SimpleNamespace(bytes=b"\x00" * 17),
        SimpleNamespace(bytes="not-bytes"),
        SimpleNamespace(bytes=16),
        SimpleNamespace(bytes=object()),
    ],
)
def test_a2_cuda_uuid_normalizer_rejects_missing_invalid_or_wrong_length_payload(value):
    with pytest.raises(RuntimeError, match="A2 CUDA UUID"):
        train_module._canonicalize_a2_cuda_uuid(value)


def test_a2_prepare_torch_device_compares_canonical_uuid_and_emits_marker(monkeypatch, capsys):
    import uuid

    expected = _a2_identity()["pinned_uuid"]

    class FakeCUuuid:
        bytes = list(uuid.UUID(expected.removeprefix("GPU-")).bytes)

        def __str__(self):
            return "<repr-only UUID>"

    calls = []
    monkeypatch.delenv("ACCELERATE_TORCH_DEVICE", raising=False)
    monkeypatch.delenv("ACCELERATE_BYPASS_DEVICE_MAP", raising=False)
    monkeypatch.setattr(torch.cuda, "device_count", lambda: 1)
    monkeypatch.setattr(torch.cuda, "set_device", lambda device: calls.append(device))
    monkeypatch.setattr(torch.cuda, "current_device", lambda: 0)
    monkeypatch.setattr(torch.cuda, "get_device_properties", lambda logical_id: SimpleNamespace(uuid=FakeCUuuid()))
    assert train_module._prepare_a2_torch_device(_a2_identity()) == torch.device("cuda", 0)
    assert calls == [0]
    output = capsys.readouterr().out
    assert "CVD=0 host_gpu_index=0 logical_gpu_index=0" in output
    assert f"pinned_uuid={expected}" in output


def test_a2_prepare_torch_device_requires_one_visible_cuda(monkeypatch):
    monkeypatch.setattr(torch.cuda, "device_count", lambda: 2)
    with pytest.raises(RuntimeError, match="exactly one visible"):
        train_module._prepare_a2_torch_device(_a2_identity())


def test_a2_standard_ppo_config_uses_real_partial_state_without_descriptor_patch(monkeypatch, tmp_path):
    pytest.importorskip("trl")
    from accelerate.state import AcceleratorState, PartialState
    from trl import PPOConfig

    monkeypatch.delenv("ACCELERATE_TORCH_DEVICE", raising=False)
    monkeypatch.delenv("ACCELERATE_BYPASS_DEVICE_MAP", raising=False)
    monkeypatch.setenv("ACCELERATE_TORCH_DEVICE", "cuda:0")
    monkeypatch.setenv("ACCELERATE_BYPASS_DEVICE_MAP", "true")
    for name in train_module._A2_ACTUAL_DISTRIBUTED_ENV:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(torch.cuda, "device_count", lambda: 1)
    monkeypatch.setattr(torch.cuda, "current_device", lambda: 0)
    calls = []
    monkeypatch.setattr(torch.cuda, "set_device", lambda device: calls.append(device))
    monkeypatch.setattr(AcceleratorState, "_shared_state", {})
    monkeypatch.setattr(PartialState, "_shared_state", {})
    original_descriptor = PPOConfig.__dict__.get("_setup_devices")
    config = PPOConfig(output_dir=str(tmp_path))
    assert type(config) is PPOConfig
    assert PPOConfig.__dict__.get("_setup_devices") is original_descriptor
    train_module._validate_a2_ppo_config(config, _a2_identity())
    assert config.device == torch.device("cuda:0")
    assert config.world_size == 1
    assert config.parallel_mode.name == "NOT_PARALLEL"
    payload = __import__("pickle").dumps(config)
    restored = __import__("pickle").loads(payload)
    assert type(restored) is PPOConfig
    assert restored.device == config.device
    assert calls


def test_a2_ppo_config_validation_rejects_non_single_partial_state():
    from transformers.training_args import ParallelMode
    from accelerate.state import DistributedType

    args = SimpleNamespace(
        distributed_state=SimpleNamespace(
            device=torch.device("cuda:0"),
            distributed_type=DistributedType.MULTI_GPU,
            backend="nccl",
            num_processes=2,
            process_index=1,
            local_process_index=1,
        ),
        device=torch.device("cuda:0"),
        local_rank=1,
        _n_gpu=2,
        parallel_mode=ParallelMode.DISTRIBUTED,
        world_size=2,
    )
    with pytest.raises(RuntimeError, match="DistributedType.NO"):
        train_module._validate_a2_ppo_config(args, _a2_identity())


def test_a2_ppo_config_rejects_any_preinitialized_accelerate_shared_state(monkeypatch):
    from accelerate.state import AcceleratorState, PartialState

    identity = _a2_identity()
    matching_state = {"device": torch.device("cuda:0"), "num_processes": 1, "process_index": 0, "local_process_index": 0}
    monkeypatch.setattr(AcceleratorState, "_shared_state", matching_state)
    monkeypatch.setattr(PartialState, "_shared_state", {})
    with pytest.raises(RuntimeError, match="preinitialized Accelerate shared state"):
        train_module._validate_a2_preinitialized_accelerate_state(identity)
    assert AcceleratorState._shared_state is matching_state


def test_a2_main_uses_a2_barrier_helper_and_no_distributed_barrier():
    source = Path(train_module.__file__).read_text(encoding="utf-8")
    assert "_a2_wait_for_everyone(accelerator, A2_GPU_BINDING)" in source
    assert source.count("accelerator.wait_for_everyone()") == 1
    assert "torch.distributed.barrier" not in source
    assert "world_size == 2" not in source


def test_a2_barrier_world1_validated_noop_and_non_a2_delegates(monkeypatch, capsys):
    identity = _a2_identity()
    monkeypatch.setattr(train_module, "_A2_GPU_BINDING_BARRIER_EMITTED", False)
    monkeypatch.setattr(torch.cuda, "current_device", lambda: 0)
    monkeypatch.setattr(torch.distributed, "is_available", lambda: True)
    monkeypatch.setattr(torch.distributed, "is_initialized", lambda: False)
    delegated = []
    accelerator = SimpleNamespace(num_processes=1, process_index=0, device=torch.device("cuda:0"), wait_for_everyone=lambda: delegated.append("generic"))
    train_module._a2_wait_for_everyone(accelerator, identity)
    train_module._a2_wait_for_everyone(accelerator, None)
    assert delegated == ["generic"]
    assert capsys.readouterr().out.count("[A2_GPU_BINDING_BARRIER]") == 1


def test_a2_barrier_rejects_wrong_world_or_distributed_state(monkeypatch):
    identity = _a2_identity()
    monkeypatch.setattr(torch.cuda, "current_device", lambda: 0)
    accelerator = SimpleNamespace(num_processes=2, process_index=0, device=torch.device("cuda:0"))
    with pytest.raises(RuntimeError, match="one Accelerator"):
        train_module._a2_wait_for_everyone(accelerator, identity)
    accelerator.num_processes = 1
    monkeypatch.setattr(torch.distributed, "is_available", lambda: True)
    monkeypatch.setattr(torch.distributed, "is_initialized", lambda: True)
    with pytest.raises(RuntimeError, match="must not initialize"):
        train_module._a2_wait_for_everyone(accelerator, identity)


def test_a2_ppo_post_prepare_accepts_single_cuda_model_and_rejects_ddp(monkeypatch):
    from accelerate.state import DistributedType

    monkeypatch.setattr(torch.cuda, "current_device", lambda: 0)
    accelerator = SimpleNamespace(
        num_processes=1,
        process_index=0,
        state=SimpleNamespace(distributed_type=DistributedType.NO, backend=None),
        device=torch.device("cuda:0"),
    )
    parameter = SimpleNamespace(device=torch.device("cuda:0"))
    model = SimpleNamespace(named_parameters=lambda: [("weight", parameter)])
    ppo_module = __import__("gr00t.rl.trl.trainer.ppo_trainer_a2_base_api", fromlist=["_validate_a2_single_gpu_binding"])
    ppo_module._validate_a2_single_gpu_binding(accelerator, model, _a2_identity())
    ddp_model = SimpleNamespace(device_ids=[0], named_parameters=lambda: [("weight", parameter)])
    with pytest.raises(RuntimeError, match="distributed model wrappers"):
        ppo_module._validate_a2_single_gpu_binding(accelerator, ddp_model, _a2_identity())


def _a2_rgb_test_trainer():
    trainer = distill_module.TRLDistillTrainerA2BaseAPI.__new__(
        distill_module.TRLDistillTrainerA2BaseAPI
    )
    trainer.camera_resolution = (2, 2, 3)
    trainer.value_model = None
    trainer._a2_rgb_frame_validated = False
    return trainer


def _a2_rgb_rollout_obs(vision):
    env_count = vision.shape[0]
    return {
        "actor_obs": torch.zeros(env_count, 81, dtype=torch.float32, device=vision.device),
        "teacher_obs": torch.zeros(
            env_count, distill_module.A2_TEACHER_OBS_DIM, dtype=torch.float32, device=vision.device
        ),
        "a2_base_obs": torch.zeros(
            env_count, distill_module.A2_BASE_OBS_DIM, dtype=torch.float32, device=vision.device
        ),
        "vision_obs": vision,
    }


def test_a2_rgb_first_frame_nonconstant_validation_emits_one_marker(capsys):
    vision = torch.zeros(2, 2, 2, 3, dtype=torch.float32)
    vision[0, 0, 0, 0] = 1.0
    vision[1, 1, 1, 2] = 2.0
    trainer = _a2_rgb_test_trainer()
    obs_dict = _a2_rgb_rollout_obs(vision)
    trainer._validate_rollout_obs(obs_dict)
    trainer._validate_rollout_obs(obs_dict)
    output = capsys.readouterr().out
    assert trainer._a2_rgb_frame_validated is True
    assert output.count("[A2_RGB_FRAME]") == 1
    assert "shape=(2, 2, 2, 3)" in output
    assert "dtype=torch.float32" in output
    assert "device=cpu" in output
    assert "finite=true" in output
    assert "per_env_nonconstant=true" in output
    assert "global_min=0" in output
    assert "global_max=2" in output


def test_a2_rgb_first_frame_rejects_all_zero_before_student_rollout():
    trainer = _a2_rgb_test_trainer()
    with pytest.raises(ValueError, match="constant/uninitialized RGB"):
        trainer._validate_rollout_obs(_a2_rgb_rollout_obs(torch.zeros(2, 2, 2, 3)))


def test_a2_rgb_first_frame_rejects_constant_environment_with_index():
    vision = torch.zeros(2, 2, 2, 3, dtype=torch.float32)
    vision[0, 0, 0, 0] = 1.0
    vision[1].fill_(0.5)
    trainer = _a2_rgb_test_trainer()
    with pytest.raises(
        ValueError,
        match=r"constant/uninitialized RGB.*invalid_count=1.*first_invalid_environment_index=1",
    ):
        trainer._validate_rollout_obs(_a2_rgb_rollout_obs(vision))
    assert trainer._a2_rgb_frame_validated is False


def test_a2_rgb_first_frame_validation_is_before_student_rollout_source():
    source = Path(distill_module.__file__).read_text(encoding="utf-8")
    assert "self._a2_rgb_frame_validated = False" in source
    assert source.index("constant/uninitialized RGB") < source.index(
        "student_state = policy_model.rollout"
    )


def test_a2_distill_constructor_stores_identity_without_forwarding_unsupported_kwarg(monkeypatch):
    captured = {}

    def fake_parent_init(self, **kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(distill_module.TRLDistillTrainer, "__init__", fake_parent_init)
    identity = _a2_identity()
    obj = object.__new__(distill_module.TRLDistillTrainerA2BaseAPI)
    signature = inspect.signature(distill_module.TRLDistillTrainerA2BaseAPI.__init__)
    assert "a2_gpu_identity" in signature.parameters
    distill_module.TRLDistillTrainerA2BaseAPI.__init__(
        obj,
        args=None,
        config=None,
        env=None,
        model=None,
        a2_gpu_identity=identity,
    )
    assert obj.a2_gpu_identity is identity
    assert obj._a2_rgb_frame_validated is False
    assert "a2_gpu_identity" not in captured


def test_a2_distill_mro_retains_subclass_init_and_a2_prepare_path():
    source = Path(distill_module.__file__).read_text(encoding="utf-8")
    assert "def __init__(" in source
    assert "self.a2_gpu_identity = a2_gpu_identity" in source
    assert "A2TRLPPOTrainer._init_trl(" in source
    assert "_validate_a2_ddp_binding" not in source
    assert "a2_gpu_identity=a2_gpu_identity" not in source.split("super().__init__(", 1)[1].split(")", 1)[0]


def test_a2_resolved_config_snapshot_preserves_unresolved_compatibility_file(tmp_path):
    config = OmegaConf.create({"base": "resolved-value", "value": "${base}"})
    unresolved = OmegaConf.to_container(config, resolve=False)
    unresolved_path, resolved_path = train_module.save_training_config_snapshots(
        config, tmp_path, unresolved
    )
    unresolved_text = unresolved_path.read_text(encoding="utf-8")
    resolved_text = resolved_path.read_text(encoding="utf-8")
    assert "${base}" in unresolved_text
    assert "resolved-value" in resolved_text
    assert yaml.safe_load(unresolved_text)["value"] == "${base}"
    assert yaml.safe_load(resolved_text)["value"] == "resolved-value"


def test_a2_identity_markers_are_one_shot_after_success(tmp_path, monkeypatch, capsys):
    checkpoint = tmp_path / "teacher.pt"
    checkpoint.write_bytes(b"teacher")
    monkeypatch.setattr(distill_module, "_A2_TEACHER_IDENTITY_EMITTED", False)
    distill_module._emit_teacher_identity(checkpoint)
    distill_module._emit_teacher_identity(checkpoint)
    teacher_output = capsys.readouterr().out
    assert teacher_output.count("[A2_TEACHER_IDENTITY]") == 1
    assert "obs_dim=133 action_dim=12" in teacher_output

    monkeypatch.setattr(distill_module, "_A2_ACTION_CHAIN_EMITTED", False)
    distill_module._emit_action_chain_identity(1.0)
    distill_module._emit_action_chain_identity(1.0)
    action_output = capsys.readouterr().out
    assert action_output.count("[A2_ACTION_CHAIN]") == 1
    assert "high_level_dim=12 a2_base_dim=12 rollout_dim=24" in action_output
