"""CPU/static contract tests for the P2 fresh-common-init foundation."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest


torch = pytest.importorskip("torch")
pytest.importorskip("hydra")

from gr00t.rl.scripts import run_a2_cb2h_pro_p2 as runner
from gr00t.rl.trl.modules import vision_actor_critic_modules_p2_recurrent as p2
from gr00t.rl.agents.modules.modules import BaseModule
from omegaconf import OmegaConf


class _Config(dict):
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError as exc:
            raise AttributeError(key) from exc


class _ParameterizedResNet(BaseModule):
    """Real BaseModule ResNet18/SyncBN state schema with cheap test forward."""

    def __init__(self, config, *, env_config, algo_config, obs_dim_dict, module_dim_dict):
        config = OmegaConf.create(OmegaConf.to_container(config, resolve=True))
        config.module_config_dict.layer_config.pretrained = False
        super().__init__(
            module_config_dict=config.module_config_dict,
            env_config=env_config,
            algo_config=algo_config,
            obs_dim_dict=obs_dim_dict,
            module_dim_dict=module_dim_dict,
            process_output_dim=bool(config.get("process_output_dim", False)),
        )
        self.calls = 0

    def forward(self, value):
        self.calls += 1
        return value.mean(dim=(1, 2, 3), keepdim=False).unsqueeze(-1).repeat(1, self.output_dim)


class _ParameterizedHead(torch.nn.Module):
    output_dim = 128

    def __init__(self):
        super().__init__()
        self.projection = torch.nn.Linear(3, 128)
        self.module_config_dict = _Config(layer_config=_Config(type="ResNet"))
        self.calls = 0

    def forward(self, value):
        self.calls += 1
        return self.projection(value.mean(dim=(2, 3)))


class _FakeMLP(torch.nn.Module):
    output_dim = 12

    def __init__(self):
        super().__init__()
        self.module = torch.nn.Sequential(
            torch.nn.Linear(256, 512),
            torch.nn.SiLU(),
            torch.nn.Linear(512, 256),
            torch.nn.SiLU(),
            torch.nn.Linear(256, 128),
            torch.nn.SiLU(),
            torch.nn.Linear(128, 12),
        )

    def forward(self, value):
        return self.module(value)


def _fake_instantiate(config, **kwargs):
    kwargs.pop("_recursive_", None)
    def plain(value):
        if isinstance(value, dict):
            return {key: plain(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [plain(item) for item in value]
        return value

    config = OmegaConf.create(plain(config))
    if isinstance(config, str):
        raise TypeError(config)
    layer_type = config.get("module_config_dict", {}).get("layer_config", {}).get("type")
    inputs = list(config.get("module_config_dict", {}).get("input_dim", []))
    if layer_type == "ResNet" and inputs == ["vision_obs"]:
        return _ParameterizedResNet(config, **kwargs)
    if layer_type == "ResNet":
        return _ParameterizedHead()
    return _FakeMLP()


def _configs():
    obs_dim_dict = {
        "actor_obs": 81,
        "vision_obs": 384 * 216 * 6,
        "context_vision_obs": 136 * 384 * 3,
        "camera_meta": 6,
    }
    env_config = SimpleNamespace(
        robot=SimpleNamespace(algo_obs_dim_dict=obs_dim_dict, actions_dim=12),
        simulator=SimpleNamespace(
            config=SimpleNamespace(
                cameras=SimpleNamespace(camera_resolutions=[384, 216], camera_types=[{"rgb": True}])
            )
        ),
    )
    algo_config = _Config(init_noise_std=0.001, freeze_noise_std=False, clamp_noise_std=True, max_noise_std=0.001)
    backbone = SimpleNamespace(
        d435i_vision_module=_Config(
            _target_="fake",
            process_output_dim=True,
            module_config_dict=_Config(
                input_dim=["vision_obs"],
                output_dim=[128],
                layer_config=_Config(type="ResNet", resnet_type="resnet18", pretrained=False, trainable=True),
            ),
        ),
        head_vision_module=_Config(
            _target_="fake",
            process_output_dim=True,
            module_config_dict=_Config(
                input_dim=["context_vision_obs"],
                output_dim=[128],
                layer_config=_Config(type="ResNet", resnet_type="resnet18", pretrained=False, trainable=True),
            ),
        ),
        mlp_module=_Config(
            _target_="fake",
            process_output_dim=True,
            module_config_dict=_Config(
                input_dim=["actor_obs"],
                output_dim=[12],
                layer_config=_Config(type="MLP", hidden_dims=[512, 256, 128], activation="SiLU"),
            ),
        ),
    )
    return env_config, algo_config, backbone


def _b1_actor(monkeypatch):
    monkeypatch.setattr(p2, "instantiate", _fake_instantiate)
    env_config, algo_config, backbone = _configs()
    env_config.robot.algo_obs_dim_dict.pop("context_vision_obs")
    env_config.robot.algo_obs_dim_dict["camera_meta"] = 4
    return p2.DualD435VisionRecurrentActor(
        env_config,
        algo_config,
        backbone,
        module_dim_dict={"actor_obs": -1},
        view_contract={"camera_meta_dim": 4, "d435i_forward_mode": "packed"},
        running_mean_std=True,
    )


def _b2_actor(monkeypatch):
    monkeypatch.setattr(p2, "instantiate", _fake_instantiate)
    env_config, algo_config, backbone = _configs()
    return p2.DualD435HeadVisionRecurrentActor(
        env_config,
        algo_config,
        backbone,
        module_dim_dict={"actor_obs": -1},
        view_contract={"camera_meta_dim": 6, "d435i_forward_mode": "packed"},
        running_mean_std=True,
    )


def _obs(batch=1, *, head=False):
    data = {
        "actor_obs": torch.zeros(batch, 81),
        "vision_obs": torch.ones(batch, 384, 216, 6),
        "camera_meta": torch.tensor([[0.0, 0.0, 1.0, 1.0]] * batch),
    }
    if head:
        data["camera_meta"] = torch.tensor([[0.0, 0.0, 0.0, 1.0, 1.0, 1.0]] * batch)
        data["context_vision_obs"] = torch.ones(batch, 136, 384, 3)
    return data


def test_b1_b2_cpu_forward_and_packed_encoder_contract(monkeypatch):
    b1 = _b1_actor(monkeypatch)
    result_b1 = b1(_obs(batch=2))
    assert result_b1.shape == (2, 12)
    assert b1.core.d435i_vision_module.calls == 1
    assert not hasattr(b1, "head_vision_module")

    b2 = _b2_actor(monkeypatch)
    result_b2 = b2(_obs(batch=2, head=True))
    assert result_b2.shape == (2, 12)
    assert b2.core.d435i_vision_module.calls == 1
    assert b2.head_vision_module.calls == 1
    b1_snapshot = b1.get_observability_snapshot(per_sample=True)
    assert tuple(b1_snapshot["feature/d435_norm"].shape) == (2,)
    assert bool(torch.isfinite(b1_snapshot["feature/d435_norm"]).all().item())
    assert torch.equal(b1_snapshot["feature/d435_norm"], b1.core._diagnostic_per_sample_cache["feature/d435_norm"])
    assert all(key.startswith("core.") for key in p2.common_core_state(b1)[0])
    assert all(key.startswith("core.") for key in p2.common_core_state(b2)[0])


def test_b1_b2_rollout_step_counter_advances_once(monkeypatch):
    b1 = _b1_actor(monkeypatch)
    b2 = _b2_actor(monkeypatch)
    b1.rollout(_obs(batch=2))
    b2.rollout(_obs(batch=2, head=True))
    assert b1.steps == 1
    assert b2.steps == 1
    b1.rollout(_obs(batch=2))
    b2.rollout(_obs(batch=2, head=True))
    assert b1.steps == 2
    assert b2.steps == 2


def test_b2_asymmetric_meta_projection_uses_d435_0143_and_head_25(monkeypatch):
    b2 = _b2_actor(monkeypatch)
    obs = _obs(batch=2, head=True)
    obs["camera_meta"] = torch.tensor(
        [
            [0.0, 0.0, 0.0, 1.0, 0.0, 1.0],
            [1.0, 0.5, 1.0, 0.0, 1.0, 0.0],
        ]
    )
    result = b2(obs)
    assert result.shape == (2, 12)
    snapshot = b2.get_observability_snapshot(per_sample=True)
    assert snapshot["feature/head_fixed_contribution_norm"][0] > 0.0
    assert snapshot["feature/head_fixed_contribution_norm"][1] == 0.0
    assert torch.isfinite(snapshot["feature/d435_norm"]).all()


def test_common_init_consumers_decode_one_snapshot_without_rehash_reopen(monkeypatch, tmp_path):
    torch.manual_seed(0)
    before = p2.capture_rng_state()
    source = _b1_actor(monkeypatch)
    downstream = p2.capture_rng_state()
    artifact = tmp_path / "common_init.pt"
    runtime = {"runtime_repository": "/tmp/c18", "runtime_commit": runner.EXPECTED_RUNTIME_COMMIT}
    p2.create_common_init_artifact(
        source,
        artifact,
        branch="b1",
        architecture=p2.P2_B1_ARCHITECTURE,
        seed=0,
        config_sha256=runner.P2_COMMON_CONFIG_SHA256,
        runtime_identity=runtime,
        rng_before_policy=before,
        rng_downstream=downstream,
    )
    trusted = p2.sha256_file(artifact)
    original_snapshot = p2.read_immutable_snapshot

    def race_after_snapshot(path):
        payload, digest = original_snapshot(path)
        Path(path).write_bytes(b"tampered-after-snapshot")
        return payload, digest

    monkeypatch.setattr(p2, "read_immutable_snapshot", race_after_snapshot)
    target = _b2_actor(monkeypatch)
    loaded, _ = p2.load_common_init_artifact(
        target,
        artifact,
        branch="b2",
        architecture=p2.P2_B2_ARCHITECTURE,
        seed=0,
        config_sha256=runner.P2_COMMON_CONFIG_SHA256,
        runtime_identity=runtime,
        rng_before_policy=before,
        trusted_artifact_sha256=trusted,
    )
    assert loaded["schema"] == p2.P2_COMMON_INIT_SCHEMA


def test_runner_json_snapshot_decodes_hashed_bytes_after_path_race(monkeypatch, tmp_path):
    path = tmp_path / "step0.json"
    original = {"schema": "immutable-step0", "global_step": 0}
    path.write_text(json.dumps(original), encoding="utf-8")
    original_snapshot = runner.read_immutable_snapshot

    def race_after_snapshot(snapshot_path):
        payload, digest = original_snapshot(snapshot_path)
        Path(snapshot_path).write_text('{"schema":"tampered-after-snapshot"}', encoding="utf-8")
        return payload, digest

    monkeypatch.setattr(runner, "read_immutable_snapshot", race_after_snapshot)
    decoded, digest, size = runner.load_json_snapshot(path)
    assert decoded == original
    assert digest == runner.sha256_bytes(json.dumps(original).encode("utf-8"))
    assert size == len(json.dumps(original).encode("utf-8"))


def test_common_init_artifact_exact_core_hash_and_rng_restore(monkeypatch, tmp_path):
    torch.manual_seed(0)
    before = p2.capture_rng_state()
    source = _b1_actor(monkeypatch)
    downstream = p2.capture_rng_state()
    artifact = tmp_path / "common_init.pt"
    runtime = {"runtime_repository": "/tmp/c18", "runtime_commit": runner.EXPECTED_RUNTIME_COMMIT}
    manifest = p2.create_common_init_artifact(
        source,
        artifact,
        branch="b1",
        architecture=p2.P2_B1_ARCHITECTURE,
        seed=0,
        config_sha256=runner.P2_COMMON_CONFIG_SHA256,
        runtime_identity=runtime,
        rng_before_policy=before,
        rng_downstream=downstream,
    )

    torch.manual_seed(0)
    before_target = p2.capture_rng_state()
    target = _b2_actor(monkeypatch)
    loaded_manifest, loaded_rng = p2.load_common_init_artifact(
        target,
        artifact,
        branch="b2",
        architecture=p2.P2_B2_ARCHITECTURE,
        seed=0,
        config_sha256=runner.P2_COMMON_CONFIG_SHA256,
        runtime_identity=runtime,
        rng_before_policy=before_target,
        trusted_artifact_sha256=p2.sha256_file(artifact),
    )
    assert loaded_manifest["aggregate_sha256"] == manifest["aggregate_sha256"]
    assert p2.common_core_state(target)[2] == manifest["aggregate_sha256"]
    p2.restore_rng_state(loaded_rng)
    assert p2.capture_rng_state()["identity"] == loaded_rng["identity"]


def test_common_init_rejects_tampered_state(monkeypatch, tmp_path):
    source = _b1_actor(monkeypatch)
    runtime = {"runtime_repository": "/tmp/c18", "runtime_commit": runner.EXPECTED_RUNTIME_COMMIT}
    before = p2.capture_rng_state()
    downstream = p2.capture_rng_state()
    artifact = tmp_path / "common_init.pt"
    p2.create_common_init_artifact(
        source,
        artifact,
        branch="b1",
        architecture=p2.P2_B1_ARCHITECTURE,
        seed=0,
        config_sha256=runner.P2_COMMON_CONFIG_SHA256,
        runtime_identity=runtime,
        rng_before_policy=before,
        rng_downstream=downstream,
    )
    payload = torch.load(artifact, map_location="cpu", weights_only=False)
    first_key = sorted(payload["state_dict"])[0]
    payload["state_dict"][first_key] = payload["state_dict"][first_key].clone()
    payload["state_dict"][first_key].view(-1)[0] += 1.0
    tampered = tmp_path / "tampered.pt"
    torch.save(payload, tampered)
    target = _b2_actor(monkeypatch)
    with pytest.raises(RuntimeError):
        p2.load_common_init_artifact(
            target,
            tampered,
            branch="b2",
            architecture=p2.P2_B2_ARCHITECTURE,
            seed=0,
            config_sha256=runner.P2_COMMON_CONFIG_SHA256,
            runtime_identity=runtime,
            trusted_artifact_sha256="0" * 64,
        )


def test_common_init_external_digest_rejects_correlated_state_manifest_tamper(monkeypatch, tmp_path):
    source = _b1_actor(monkeypatch)
    runtime = {"runtime_repository": "/tmp/c18", "runtime_commit": runner.EXPECTED_RUNTIME_COMMIT}
    before = p2.capture_rng_state()
    downstream = p2.capture_rng_state()
    artifact = tmp_path / "common_init.pt"
    p2.create_common_init_artifact(
        source,
        artifact,
        branch="b1",
        architecture=p2.P2_B1_ARCHITECTURE,
        seed=0,
        config_sha256=runner.P2_COMMON_CONFIG_SHA256,
        runtime_identity=runtime,
        rng_before_policy=before,
        rng_downstream=downstream,
    )
    payload = torch.load(artifact, map_location="cpu", weights_only=False)
    first_key = next(iter(payload["state_dict"]))
    payload["state_dict"][first_key] = payload["state_dict"][first_key].clone()
    payload["state_dict"][first_key].view(-1)[0] += 1.0
    payload["manifest"]["keys"][0]["sha256"] = "0" * 64
    tampered = tmp_path / "correlated_tamper.pt"
    torch.save(payload, tampered)
    target = _b2_actor(monkeypatch)
    with pytest.raises(RuntimeError, match="external artifact digest"):
        p2.load_common_init_artifact(
            target,
            tampered,
            branch="b2",
            architecture=p2.P2_B2_ARCHITECTURE,
            seed=0,
            config_sha256=runner.P2_COMMON_CONFIG_SHA256,
            runtime_identity=runtime,
            trusted_artifact_sha256=p2.sha256_file(artifact),
        )


def test_common_core_schema_is_explicit_and_ordered():
    assert p2.P2_COMMON_KEY_SCHEMA_SHA256 == runner.P2_COMMON_INIT_CONTRACT["common_key_schema_sha256"]
    assert tuple(p2.P2_COMMON_COMPONENTS) == tuple(runner.P2_COMMON_INIT_CONTRACT["common_components"])
    assert len(p2.P2_COMMON_KEY_SCHEMA) == 156
    assert p2.P2_COMMON_KEY_SCHEMA[0] == "core.left_view_embedding"
    assert p2.P2_COMMON_KEY_SCHEMA[-1] == "core.running_mean_std.count"


def test_train_entrypoint_common_init_hook_restores_b2_downstream_rng(monkeypatch, tmp_path):
    import gr00t.rl.train_agent_trl as train_entrypoint

    monkeypatch.setattr(p2, "instantiate", _fake_instantiate)
    runtime = {"runtime_repository": "/tmp/c18", "runtime_commit": runner.EXPECTED_RUNTIME_COMMIT}
    torch.manual_seed(0)
    before = p2.capture_rng_state()
    b1 = _b1_actor(monkeypatch)
    common_root = tmp_path / "common_init"
    b1_cfg = {
        "enabled": True,
        "branch": "b1",
        "mode": "create",
        "architecture": p2.P2_B1_ARCHITECTURE,
        "seed": 0,
        "config_sha256": runner.P2_COMMON_CONFIG_SHA256,
        "artifact_path": str(common_root / "b1_common_init.pt"),
        "step0_manifest_path": str(common_root / "b1_step0_manifest.json"),
    }
    train_entrypoint._initialize_p2_common_init(
        b1,
        None,
        branch_config=b1_cfg,
        rng_before_policy=before,
        device="cpu",
        runtime_identity=runtime,
    )
    torch.manual_seed(0)
    before_b2 = p2.capture_rng_state()
    b2 = _b2_actor(monkeypatch)
    b2_cfg = dict(b1_cfg)
    b2_cfg.update(
        branch="b2",
        mode="load",
        architecture=p2.P2_B2_ARCHITECTURE,
        step0_manifest_path=str(common_root / "b2_step0_manifest.json"),
        trusted_artifact_sha256=p2.sha256_file(common_root / "b1_common_init.pt"),
        source_step0_manifest_path=str(common_root / "b1_step0_manifest.json"),
        trusted_source_step0_manifest_sha256=p2.sha256_file(common_root / "b1_step0_manifest.json"),
    )
    train_entrypoint._initialize_p2_common_init(
        b2,
        None,
        branch_config=b2_cfg,
        rng_before_policy=before_b2,
        device="cpu",
        runtime_identity=runtime,
    )
    assert (common_root / "b1_common_init.pt").is_file()
    assert (common_root / "b1_step0_manifest.json").is_file()
    assert (common_root / "b2_step0_manifest.json").is_file()


def test_p2_dry_run_contract_does_not_create_output_root(tmp_path):
    output_root = tmp_path / "p2"
    overrides = runner.build_training_overrides("b1", output_root / "b1", output_root / "common_init")
    assert not output_root.exists()
    assert "+exp=wbmanip/door_open_a2_base_v19_p2_b1" in overrides
    assert "num_envs=64" in overrides
    assert "algo.trl.num_total_batches=500" in overrides
    assert "checkpoint=null" in overrides
    command = runner.build_branch_command("b2", output_root / "b2", output_root / "common_init")
    assert command[0] == runner.sys.executable
    assert "+exp=wbmanip/door_open_a2_base_v19_p2_b2" in command
    assert not output_root.exists()


def test_b1_simulator_capture_emits_dual_rgb_and_meta4_without_head():
    import ast
    from types import SimpleNamespace

    from gr00t.rl.utils.a2_policy_camera import compose_channel_stacked_dual_rgb

    simulator_path = Path(__file__).resolve().parents[1] / "simulator/isaacsim/isaacsim.py"
    tree = ast.parse(simulator_path.read_text(encoding="utf-8"))
    namespace = {"torch": torch, "compose_channel_stacked_dual_rgb": compose_channel_stacked_dual_rgb}
    for function_name in ("validate_camera_rgb_output", "_capture_p2_b1_camera_cache", "_capture_c_b2h_camera_cache", "_refresh_c_b2h_camera_meta_cache"):
        node = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == function_name)
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(simulator_path), "exec"), namespace)

    class Sensor:
        def __init__(self, value):
            self.frame = torch.ones(2, dtype=torch.int64)
            rgb = torch.full((2, 384, 216, 3), value, dtype=torch.uint8)
            rgb[..., 1] = value + 1
            self.data = SimpleNamespace(output={"rgb": rgb})

        def reset(self, env_ids):
            self.frame[env_ids] = 1

    sim = SimpleNamespace(
        sim_device="cpu",
        num_envs=2,
        simulator_config=SimpleNamespace(
            cameras=SimpleNamespace(image_mean=[0.0, 0.0, 0.0], image_std=[1.0, 1.0, 1.0]),
            sim=SimpleNamespace(fps=200),
        ),
        _policy_multiview={
            "architecture_id": "C-B1-DUALRAW-SHAREDENC-TOEIN20-V19-P2",
            "fast_period_s": 1.0 / 30.0,
        },
        ego_camera=Sensor(1),
        policy_secondary_camera=Sensor(2),
        policy_context_camera=None,
        _cb2h_vision_obs_cache=None,
        _cb2h_context_vision_obs_cache=None,
        _cb2h_camera_meta_cache=None,
        _cb2h_elapsed_s=0.0,
        _cb2h_last_capture_s={"left": None, "right": None},
        _cb2h_last_frame_s={name: torch.full((2,), -1.0) for name in ("left", "right")},
        _cb2h_last_frame_id={name: torch.full((2,), -1, dtype=torch.int64) for name in ("left", "right")},
        _cb2h_ever_captured={name: torch.zeros(2, dtype=torch.bool) for name in ("left", "right")},
        _cb2h_cache_valid=torch.zeros(2, dtype=torch.bool),
    )
    for function_name in ("_capture_p2_b1_camera_cache", "_capture_c_b2h_camera_cache", "_refresh_c_b2h_camera_meta_cache"):
        setattr(sim, function_name, namespace[function_name].__get__(sim, type(sim)))
    sim._capture_c_b2h_camera_cache()
    assert tuple(sim._cb2h_vision_obs_cache.shape) == (2, 384, 216, 6)
    assert tuple(sim._cb2h_camera_meta_cache.shape) == (2, 4)
    assert sim._cb2h_context_vision_obs_cache is None
    assert bool(torch.all(sim._cb2h_camera_meta_cache[:, 2:] == 1.0).item())


def test_p2_config_files_keep_b1_headless_and_b2_context_contract():
    import yaml

    root = Path(__file__).resolve().parents[1] / "config/exp/wbmanip"
    b1 = yaml.safe_load((root / "door_open_a2_base_v19_p2_b1.yaml").read_text())
    b2 = yaml.safe_load((root / "door_open_a2_base_v19_p2_b2.yaml").read_text())
    assert "context_vision_obs" not in b1["obs"]["obs_dict"]
    assert "head_vision_module" not in b1["algo"]["config"]["actor"]["backbone"]
    b1_dims = {next(iter(item)): next(iter(item.values())) for item in b1["obs"]["obs_dims"]}
    assert b1_dims["camera_meta"] == 4
    assert b1["algo"]["config"]["p2_common_init"]["config_sha256"] == runner.P2_COMMON_CONFIG_SHA256
    assert b2["algo"]["config"]["p2_common_init"]["config_sha256"] == runner.P2_COMMON_CONFIG_SHA256
    assert b2["algo"]["config"]["actor"]["backbone"]["head_vision_module"]["module_config_dict"]["input_dim"] == ["context_vision_obs"]
    assert b2["algo"]["config"]["actor"]["backbone"]["head_vision_module"]


def test_teacher_rollout_disable_is_all_student_including_ratio_one():
    from gr00t.rl.trl.trainer.distill_trainer_a2_base_api import build_cyclic_teacher_mask

    for ratio in (0.0, 0.5, 1.0):
        mask = build_cyclic_teacher_mask(8, ratio, 3, enforce_teacher_rollout=False)
        assert int(mask.sum().item()) == 0


def test_p2_b1_b2_effective_hydra_contract_and_bootstrap(tmp_path):
    import yaml

    baseline = yaml.safe_load(
        (Path(__file__).resolve().parents[1] / "config/exp/wbmanip/door_open_a2_base_v19_cb2h_dualraw_dagger-lstm.yaml").read_text()
    )
    baseline_algo = baseline["algo"]["config"]
    for key, expected in {
        "gamma": 0.9966,
        "lam": 0.983,
        "desired_kl": 0.005,
        "init_at_random_ep_len": False,
        "use_obj_pred": False,
        "obj_pred_loss_coef": 0.0,
    }.items():
        assert baseline_algo[key] == expected
    for branch in ("b1", "b2"):
        output_root = tmp_path / branch
        overrides = runner.build_training_overrides(branch, output_root / branch, output_root / "common_init")
        config = runner.compose_training_config(overrides)
        runner.validate_composed_config(config, branch)
        assert float(config.algo.config.gamma) == pytest.approx(0.9966)
        assert float(config.algo.config.lam) == pytest.approx(0.983)
        assert float(config.algo.config.desired_kl) == pytest.approx(0.005)
        assert config.algo.config.init_at_random_ep_len is False
        assert config.algo.config.use_obj_pred is False
        assert float(config.algo.config.obj_pred_loss_coef) == 0.0
        assert config.num_envs == 64
        assert config.algo.trl.num_total_batches == 500
        assert config.algo.config.num_steps_per_env == 8
        assert config.algo.config.num_mini_batches == 4
        assert config.algo.trl.num_ppo_epochs == 1
        assert config.algo.trl.gradient_accumulation_steps == 1
        assert float(config.algo.config.actor_learning_rate) == pytest.approx(1e-4)
        assert config.checkpoint is None
        command = runner.build_branch_command(branch, output_root / branch, output_root / "common_init")
        assert command[1] == str(Path(runner.__file__).resolve())
        assert "--execute-branch" in command
        assert any(item.startswith("--runtime-repository=") for item in command)
        assert any(item.startswith("--overlay-repository=") for item in command)
        assert "--" in command
    bootstrap_source = runner.BOOTSTRAP_SCRIPT.read_text(encoding="utf-8")
    for marker in (
        "validate_runtime_repository",
        "install_v19_runtime_scenario_file_pin",
        "V19RuntimeFinder",
        "prepare_overlay_import",
    ):
        assert marker in bootstrap_source


def test_real_default_dry_run_validates_present_c18_and_never_creates_output(tmp_path):
    output_root = tmp_path / "fresh-default-output"
    completed = subprocess.run(
        [sys.executable, str(Path(runner.__file__).resolve()), "--dry-run", "--output-root", str(output_root)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert not output_root.exists()
    plan = json.loads(completed.stdout)
    assert plan["runtime"]["repository"] == "/tmp/cb2h_v19_runtime.waPJHftX/c18"
    assert plan["runtime"]["commit"] == runner.EXPECTED_RUNTIME_COMMIT
    assert plan["runtime"]["bootstrap_main_invoked"] is False
    assert plan["runtime"]["runtime_finder"] == "V19RuntimeFinder"
    assert plan["runtime"]["scenario_file_pin"] is True
    assert all("--execute-branch" in branch["command"] for branch in plan["branches"])


def test_branch_subcommand_imports_bootstrap_as_library_and_never_calls_main(monkeypatch, tmp_path):
    import gr00t.rl.scripts.run_a2_student_distillation_v19 as bootstrap

    branch_root = tmp_path / "b1"
    common_root = tmp_path / "common_init"
    command = runner.build_branch_command("b1", branch_root, common_root)
    args = runner.parse_args(list(command[2:]))
    assert args.execute_branch is True
    assert args.hydra_overrides[-1] == "~obs.obs_dict.context_vision_obs"
    monkeypatch.setattr(bootstrap, "main", lambda: (_ for _ in ()).throw(AssertionError("10k bootstrap main called")))
    monkeypatch.setattr(runner, "build_child_environment", lambda: {"CUDA_VISIBLE_DEVICES": "7", "CUDA_DEVICE_ORDER": "PCI_BUS_ID", "A2_GPU_BINDING_MODE": runner.EXPECTED_GPU_BINDING_MODE, "A2_EXPECTED_WORLD_SIZE": "1", "A2_EXPECTED_HOST_GPU_INDEX": "7", "A2_EXPECTED_LOGICAL_GPU_INDEX": "0", "A2_EXPECTED_GPU_UUID": runner.EXPECTED_GPU_UUID})
    monkeypatch.setattr(bootstrap, "prepare_overlay_import", lambda path: Path(path).resolve())
    monkeypatch.setattr(bootstrap, "validate_runtime_repository", lambda path: {})
    monkeypatch.setattr(bootstrap, "validate_gpu7_environment", lambda env: {"mode": runner.EXPECTED_GPU_BINDING_MODE})
    monkeypatch.setattr(bootstrap, "validate_teacher_triplet", lambda *paths: {})
    monkeypatch.setattr(bootstrap, "install_v19_runtime_scenario_file_pin", lambda sources: Path("sealed-scenario.py"))
    original_cwd = Path.cwd()

    def fake_run_path(path, *, run_name):
        assert Path(path).name == "train_agent_trl.py"
        assert run_name == "__main__"
        branch_root.mkdir(parents=True)
        (branch_root / "pre_teardown_completion_proof.json").write_text("{}\n")

    monkeypatch.setattr(runner.runpy, "run_path", fake_run_path)
    original_environment = dict(os.environ)
    try:
        with pytest.raises(RuntimeError, match="controlled branch returned"):
            runner._execute_branch_impl(args)
    finally:
        os.chdir(original_cwd)
        os.environ.clear()
        os.environ.update(original_environment)


def test_branch_evidence_rejects_literal_checkpoint_config_or_minimal_telemetry(tmp_path):
    branch_root = tmp_path / "b1"
    common_root = tmp_path / "common_init"
    telemetry = _write_realistic_branch_artifacts("b1", branch_root, common_root)
    branch = runner.P2Branch("b1", branch_root, (), ())
    (branch_root / "model_step_000500.pt").write_bytes(b"literal-checkpoint")
    with pytest.raises(RuntimeError, match="checkpoint"):
        runner.validate_branch_evidence(branch, telemetry=telemetry)
    telemetry = _write_realistic_branch_artifacts("b1", branch_root, common_root)
    with pytest.raises(RuntimeError, match="telemetry"):
        runner.validate_branch_evidence(branch, telemetry={"schema": runner.P2_RUNTIME_METRICS_SCHEMA})
    telemetry = _write_realistic_branch_artifacts("b1", branch_root, common_root)
    config_path = branch_root / "config.yaml"
    config_text = config_path.read_text()
    config_path.write_text(config_text.replace(runner.ARCHITECTURES["b1"], "WRONG", 1))
    with pytest.raises(RuntimeError, match="config"):
        runner.validate_branch_evidence(branch, telemetry=telemetry)


def test_child_environment_removes_inherited_distributed_accelerate_and_a2_state(monkeypatch):
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(stdout="", stderr="", returncode=0),
    )
    inherited = {
        "WORLD_SIZE": "8",
        "RANK": "4",
        "LOCAL_RANK": "2",
        "MASTER_ADDR": "127.0.0.1",
        "MASTER_PORT": "1234",
        "ACCELERATE_TORCH_DEVICE": "cuda:3",
        "ACCELERATE_USE_CPU": "true",
        "A2_EXPECTED_GPU_UUID": "wrong",
        "A2_STALE_FIELD": "bad",
    }
    env = runner.build_child_environment(inherited)
    for name in ("WORLD_SIZE", "RANK", "LOCAL_RANK", "MASTER_ADDR", "MASTER_PORT", "ACCELERATE_TORCH_DEVICE", "ACCELERATE_USE_CPU", "A2_STALE_FIELD"):
        assert name not in env
    assert env["CUDA_VISIBLE_DEVICES"] == "7"
    assert env["A2_EXPECTED_LOGICAL_GPU_INDEX"] == "0"
    assert env["A2_EXPECTED_GPU_UUID"] == runner.EXPECTED_GPU_UUID


def test_p2_sample_gpu_telemetry_targets_gpu7_and_rejects_decoys(monkeypatch):
    valid_row = (
        f"{runner.EXPECTED_GPU_INDEX}, {runner.EXPECTED_GPU_UUID}, "
        "100, 46080, 20, 100, 40"
    )
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(stdout=valid_row + "\n", stderr="")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    sample = runner.sample_gpu_telemetry({"CUDA_VISIBLE_DEVICES": "0"})
    assert sample["physical_gpu_index"] == runner.EXPECTED_GPU_INDEX
    assert calls[0][0] == [
        "nvidia-smi",
        "-i",
        runner.EXPECTED_GPU_INDEX,
        "--query-gpu=index,uuid,memory.used,memory.total,utilization.gpu,power.draw,temperature.gpu",
        "--format=csv,noheader,nounits",
    ]
    assert calls[0][1]["check"] is True
    assert calls[0][1]["capture_output"] is True
    assert calls[0][1]["text"] is True
    assert calls[0][1]["env"] == {"CUDA_VISIBLE_DEVICES": "0"}

    for stdout, message in (
        ("", "exactly one"),
        (valid_row + "\n6, GPU-other, 100, 46080, 20, 100, 40\n", "exactly one"),
        ("6, GPU-other, 100, 46080, 20, 100, 40\n", "unexpected physical GPU index"),
        ("7, GPU-other, 100, 46080, 20, 100, 40\n", "UUID drifted"),
        ("7, , 100, 46080, 20, 100, 40\n", "non-empty UUID"),
        ("7, GPU-7c8cb1d2-4ebf-e2e3-35ad-fa0f6f72924d, nan, 46080, 20, 100, 40\n", "non-finite"),
        ("7, GPU-7c8cb1d2-4ebf-e2e3-35ad-fa0f6f72924d, 47104, 46080, 20, 100, 40\n", "VRAM"),
    ):
        monkeypatch.setattr(
            runner.subprocess,
            "run",
            lambda command, stdout=stdout, **kwargs: SimpleNamespace(stdout=stdout, stderr=""),
        )
        with pytest.raises(RuntimeError, match=message):
            runner.sample_gpu_telemetry({"CUDA_VISIBLE_DEVICES": "7"})


def test_p2_gpu_telemetry_sampler_start_stop_keeps_gpu7_records_and_final_sample(monkeypatch):
    import threading

    calls = []
    first_sample_seen = threading.Event()

    def fake_sample(environment):
        calls.append(dict(environment))
        first_sample_seen.set()
        return {
            "physical_gpu_index": runner.EXPECTED_GPU_INDEX,
            "logical_gpu_index": int(runner.EXPECTED_LOGICAL_GPU_INDEX),
            "logical_device": "cuda:0",
            "uuid": runner.EXPECTED_GPU_UUID,
            "cuda_visible_devices": runner.EXPECTED_GPU_INDEX,
            "cuda_device_order": runner.EXPECTED_CUDA_DEVICE_ORDER,
            "binding_mode": runner.EXPECTED_GPU_BINDING_MODE,
            "world_size": 1,
            "memory_used_mib": 100.0 + len(calls),
            "memory_total_mib": 46080.0,
            "utilization_gpu_pct": 20.0,
            "power_draw_w": 100.0,
            "temperature_c": 40.0,
            "sample_time_ns": len(calls),
        }

    monkeypatch.setattr(runner, "sample_gpu_telemetry", fake_sample)
    environment = {"CUDA_VISIBLE_DEVICES": runner.EXPECTED_GPU_INDEX}
    sampler = runner.GpuTelemetrySampler(environment)
    sampler.start()
    assert first_sample_seen.wait(timeout=2.0)
    telemetry = sampler.stop(process_started_ns=1, process_ended_ns=4)

    assert len(calls) >= 2
    assert all(call == environment for call in calls)
    assert telemetry["record_count"] == len(calls)
    assert telemetry["records"][-1]["sample_time_ns"] == len(calls)
    assert all(
        record["physical_gpu_index"] == runner.EXPECTED_GPU_INDEX
        and record["uuid"] == runner.EXPECTED_GPU_UUID
        for record in telemetry["records"]
    )
    assert telemetry["sample_interval_s"] == runner.P2_TELEMETRY_SAMPLE_INTERVAL_S
    assert telemetry["max_adjacent_gap_s"] == runner.P2_TELEMETRY_MAX_ADJACENT_GAP_S


def test_p2_lifecycle_guard_seals_exact_counts_before_controlled_exit(monkeypatch, tmp_path):
    import gr00t.rl.train_agent_trl as train_entrypoint

    branch_root = tmp_path / "b1"
    common_root = tmp_path / "common_init"
    branch_root.mkdir()
    common_root.mkdir()
    (branch_root / "model_step_000500.pt").write_bytes(b"checkpoint")
    (branch_root / "config.yaml").write_text("config\n")
    artifact = common_root / "b1_common_init.pt"
    artifact.write_bytes(b"artifact")
    step0 = common_root / "b1_step0_manifest.json"
    step0.write_text("{}\n")

    class State:
        global_step = 0
        max_steps = 500

    class Args:
        num_total_batches = 500

    class Accelerator:
        def backward(self, value):
            del value

    class Optimizer:
        def step(self):
            return None

    class Scheduler:
        _step_count = 1
        last_epoch = 0

        def step(self):
            self._step_count += 1
            self.last_epoch += 1

    class CallbackHandler:
        def __init__(self):
            self.callbacks = []

        def add_callback(self, callback):
            self.callbacks.append(callback)

        def remove_callback(self, callback):
            self.callbacks.remove(callback)

        def on_train_begin(self, args, state, control, **kwargs):
            for callback in list(self.callbacks):
                control = callback.on_train_begin(args, state, control, **kwargs)
            return control

        def on_step_end(self, args, state, control, **kwargs):
            for callback in list(self.callbacks):
                control = callback.on_step_end(args, state, control, **kwargs)
            return control

    class Trainer:
        def __init__(self):
            self.state = State()
            self.args = Args()
            self.accelerator = Accelerator()
            self.optimizer = Optimizer()
            self.lr_scheduler = Scheduler()
            self.callback_handler = CallbackHandler()

        def train(self):
            control = object()
            self.callback_handler.on_train_begin(self.args, self.state, control)
            for step in range(1, 501):
                for _ in range(4):
                    self.accelerator.backward(torch.tensor(1.0))
                    self.optimizer.step()
                self.lr_scheduler.step()
                self.state.global_step = step
                self.callback_handler.on_step_end(self.args, self.state, control)

    trainer = Trainer()
    original_exit = train_entrypoint.os._exit
    monkeypatch.setattr(train_entrypoint.os, "_exit", lambda code: (_ for _ in ()).throw(SystemExit(code)))
    train_entrypoint._install_p2_lifecycle_guard(
        trainer,
        branch="b1",
        branch_root=branch_root,
        common_artifact_path=artifact,
        step0_manifest_path=step0,
        runtime_identity={"runtime_repository": str(runner.RUNTIME_REPOSITORY), "runtime_commit": runner.EXPECTED_RUNTIME_COMMIT},
        active_parameter_tracker=SimpleNamespace(
            snapshot=lambda optimizer: {
                "schema": "a2_cb2h_pro_p2_active_parameter_schema_v1",
                "parameter_count": 1,
                "ordered_parameters": [{"id": 0, "name": "policy.fake", "shape": [1], "dtype": "torch.float32"}],
                "parameter_ids": [0],
                "parameter_names": ["policy.fake"],
                "schema_sha256": runner.sha256_bytes(runner.canonical_json([{"id": 0, "name": "policy.fake", "shape": [1], "dtype": "torch.float32"}]).encode()),
            },
            backward_call_count=lambda: 2000,
            native_optimizer_step_count=lambda optimizer, active_parameter_schema: 2000,
            remove=lambda: None,
        ),
    )
    with pytest.raises(SystemExit):
        trainer.train()
    proof = json.loads((branch_root / "pre_teardown_completion_proof.json").read_text())
    assert proof["callback_step_end_count"] == 500
    assert proof["backward_call_count"] == 2000
    assert proof["optimizer_step_count"] == 2000
    assert proof["scheduler_step_count_after"] == 501
    assert proof["natural_kit_lifecycle_pass"] is False
    assert proof["controlled_post_training_exit"] is True
    monkeypatch.setattr(train_entrypoint.os, "_exit", original_exit)


def test_p2_lifecycle_guard_periodic_checkpoint_is_serialization_safe(monkeypatch, tmp_path):
    import pickle

    from accelerate import Accelerator
    from transformers.optimization import get_constant_schedule

    from gr00t.rl.trl.callbacks.model_save_callback import ModelSaveCallback
    import gr00t.rl.train_agent_trl as train_entrypoint

    branch_root = tmp_path / "b1"
    common_root = tmp_path / "common_init"
    branch_root.mkdir()
    common_root.mkdir()
    artifact = common_root / "b1_common_init.pt"
    artifact.write_bytes(b"artifact")
    step0 = common_root / "b1_step0_manifest.json"
    step0.write_text("{}\n")
    (branch_root / "config.yaml").write_text("config\n")

    class Core(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.std = torch.nn.Parameter(torch.ones(3))
            self.linear = torch.nn.Linear(3, 3)
            self.norm = torch.nn.LayerNorm(3)
            self.proj = torch.nn.Linear(3, 2)

    class Policy(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.core = Core()

    class Value(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.linear = torch.nn.Linear(3, 1)

    class PolicyAndValueWrapper(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.policy = Policy()
            self.value_model = Value()

    wrapper = PolicyAndValueWrapper()
    expected_order = train_entrypoint._p2_trainable_parameter_order(wrapper.policy, wrapper.value_model)
    active_tracker = train_entrypoint._p2_register_gradient_activity(expected_order)
    optimizer = torch.optim.AdamW(
        [
            {"params": list(wrapper.policy.parameters())},
            {"params": list(wrapper.value_model.parameters())},
        ],
        lr=runner.EXPECTED_ACTOR_LEARNING_RATE,
        weight_decay=0.0,
    )
    scheduler = get_constant_schedule(optimizer)
    accelerator = Accelerator(cpu=True)
    wrapper, optimizer = accelerator.prepare(wrapper, optimizer)
    optimizer_schema, _ = train_entrypoint._p2_optimizer_parameter_schema(
        wrapper,
        optimizer,
        scheduler,
        expected_order,
    )
    active_tracker.bind_optimizer_schema(optimizer_schema)

    class Env:
        is_evaluating = False

        def get_env_state_dict(self):
            return {"cpu_checkpoint_probe": True}

    class CallbackHandler:
        def __init__(self, callbacks, trainer):
            self.callbacks = list(callbacks)
            self.trainer = trainer

        def add_callback(self, callback):
            self.callbacks.append(callback)

        def remove_callback(self, callback):
            self.callbacks.remove(callback)

        def _call(self, event, args, state, control):
            for callback in list(self.callbacks):
                control = getattr(callback, event)(
                    args,
                    state,
                    control,
                    model=self.trainer.model,
                    optimizer=self.trainer.optimizer,
                    lr_scheduler=self.trainer.lr_scheduler,
                    env=self.trainer.env,
                )
            return control

        def on_train_begin(self, args, state, control):
            return self._call("on_train_begin", args, state, control)

        def on_step_end(self, args, state, control):
            return self._call("on_step_end", args, state, control)

        def on_train_end(self, args, state, control):
            return self._call("on_train_end", args, state, control)

        def on_save(self, args, state, control):
            return self._call("on_save", args, state, control)

        def on_log(self, args, state, control, logs):
            for callback in list(self.callbacks):
                control = callback.on_log(
                    args,
                    state,
                    control,
                    logs=logs,
                    model=self.trainer.model,
                    optimizer=self.trainer.optimizer,
                    lr_scheduler=self.trainer.lr_scheduler,
                    env=self.trainer.env,
                )
            return control

    class Trainer:
        def __init__(self):
            self.model = wrapper
            self.optimizer = optimizer
            self.lr_scheduler = scheduler
            self.accelerator = accelerator
            self.args = SimpleNamespace(num_total_batches=500, output_dir=str(branch_root))
            self.state = SimpleNamespace(
                global_step=0,
                max_steps=500,
                is_world_process_zero=True,
                log_history=[],
            )
            self.env = Env()
            self.callback_handler = CallbackHandler(
                [ModelSaveCallback(branch_root, save_frequency=50)],
                self,
            )

        def train(self):
            control = SimpleNamespace()
            self.callback_handler.on_train_begin(self.args, self.state, control)
            for step in range(1, 501):
                for _ in range(4):
                    self.optimizer.zero_grad(set_to_none=True)
                    loss = sum(
                        parameter.sum()
                        for name, parameter in expected_order
                        if name.startswith("policy.") and name != "policy.core.std"
                    )
                    self.accelerator.backward(loss)
                    self.optimizer.step()
                self.lr_scheduler.step()
                self.state.global_step = step
                self.callback_handler.on_step_end(self.args, self.state, control)
            self.callback_handler.on_log(self.args, self.state, control, {"step": self.state.global_step})
            self.callback_handler.on_train_end(self.args, self.state, control)
            self.callback_handler.on_save(self.args, self.state, control)

    trainer = Trainer()
    original_exit = train_entrypoint.os._exit
    monkeypatch.setattr(train_entrypoint.os, "_exit", lambda code: (_ for _ in ()).throw(SystemExit(code)))
    train_entrypoint._install_p2_lifecycle_guard(
        trainer,
        branch="b1",
        branch_root=branch_root,
        common_artifact_path=artifact,
        step0_manifest_path=step0,
        runtime_identity={"runtime_repository": str(runner.RUNTIME_REPOSITORY), "runtime_commit": runner.EXPECTED_RUNTIME_COMMIT},
        active_parameter_tracker=active_tracker,
    )
    with pytest.raises(SystemExit):
        trainer.train()
    monkeypatch.setattr(train_entrypoint.os, "_exit", original_exit)

    periodic_path = branch_root / "model_step_000050.pt"
    final_path = branch_root / "model_step_000500.pt"
    assert periodic_path.is_file()
    assert final_path.is_file()
    periodic = torch.load(periodic_path, map_location="cpu", weights_only=False)
    final = torch.load(final_path, map_location="cpu", weights_only=False)
    proof = json.loads((branch_root / "pre_teardown_completion_proof.json").read_text())
    metrics = json.loads((branch_root / "runtime_metrics.json").read_text())
    assert set(periodic) >= {"policy_state_dict", "value_state_dict", "optimizer_state_dict", "lr_scheduler_state_dict", "state"}
    assert final["state"].global_step == 500
    assert final["lr_scheduler_state_dict"]["last_epoch"] == 500
    assert final["lr_scheduler_state_dict"]["_step_count"] == 501
    assert all(
        state["step"].item() == runner.EXPECTED_OPTIMIZER_STATE_STEP
        for state in final["optimizer_state_dict"]["state"].values()
    )
    assert "step" not in trainer.optimizer.__dict__
    assert "step" not in trainer.lr_scheduler.__dict__
    assert "train" not in trainer.__dict__
    assert "_a2_p2_lifecycle_runtime_id" not in trainer.__dict__
    assert proof["backward_call_count"] == 2000
    assert proof["optimizer_step_count"] == 2000
    assert proof["scheduler_step_count"] == 500
    assert metrics["common_init"] == proof["common_init_artifact"]
    pickle.dumps(trainer.optimizer.state_dict())
    pickle.dumps(trainer.lr_scheduler.state_dict())
    assert not train_entrypoint._P2_LIFECYCLE_RUNTIMES

    bad_scheduler = get_constant_schedule(torch.optim.AdamW([torch.nn.Parameter(torch.ones(1))], lr=1.0))

    def old_local_scheduler_step():
        return None

    bad_scheduler.step = old_local_scheduler_step
    with pytest.raises(AttributeError, match="Can't pickle local object"):
        torch.save({"scheduler": bad_scheduler}, tmp_path / "old-local-scheduler.pt")

def _write_realistic_branch_artifacts(branch, root, common_root, *, artifact_sha256=None):
    """Build evidence fixtures from actual P2 actor/critic implementations."""
    import copy
    import hashlib
    import torch
    from accelerate import Accelerator
    from transformers.optimization import get_constant_schedule
    import yaml
    import gr00t.rl.train_agent_trl as train_entrypoint

    root.mkdir(parents=True, exist_ok=True)
    common_root.mkdir(parents=True, exist_ok=True)

    class SchemaModule(torch.nn.Module):
        def __init__(self, identities):
            super().__init__()
            self._items = list(identities)
            self._parameters_flat = torch.nn.ParameterList(
                [torch.nn.Parameter(torch.zeros(tuple(item["shape"]), dtype=torch.float32)) for item in self._items]
            )

        def named_parameters(self, prefix="", recurse=True, remove_duplicate=True):
            del recurse, remove_duplicate
            for item, parameter in zip(self._items, self._parameters_flat, strict=True):
                yield f"{prefix}.{item['key']}" if prefix else item["key"], parameter

    class SchemaWrapper(torch.nn.Module):
        def __init__(self, policy_identities, value_identities):
            super().__init__()
            self.policy = SchemaModule(policy_identities)
            self.value_model = SchemaModule(value_identities)

        def named_parameters(self, prefix="", recurse=True, remove_duplicate=True):
            del recurse, remove_duplicate
            for module_prefix, module in (("policy", self.policy), ("value_model", self.value_model)):
                for name, parameter in module.named_parameters():
                    yield f"{prefix}.{module_prefix}.{name}" if prefix else f"{module_prefix}.{name}", parameter

    def actual_models(actual_branch):
        env_config, algo_config, backbone = _configs()
        for key in ("d435i_vision_module", "head_vision_module", "mlp_module"):
            module_config = getattr(backbone, key)
            module_config["_target_"] = "gr00t.rl.agents.modules.modules.BaseModule"
            module_config.module_config_dict.layer_config.pretrained = False
        if actual_branch == "b1":
            env_config.robot.algo_obs_dim_dict.pop("context_vision_obs", None)
            env_config.robot.algo_obs_dim_dict["camera_meta"] = 4
            policy = p2.DualD435VisionRecurrentActor(
                env_config,
                algo_config,
                backbone,
                module_dim_dict={"actor_obs": -1},
                view_contract={"camera_meta_dim": 4, "d435i_forward_mode": "packed"},
                running_mean_std=True,
            )
        else:
            policy = p2.DualD435HeadVisionRecurrentActor(
                env_config,
                algo_config,
                backbone,
                module_dim_dict={"actor_obs": -1},
                view_contract={"camera_meta_dim": 6, "d435i_forward_mode": "packed"},
                running_mean_std=True,
            )
        env_config.robot.algo_obs_dim_dict["critic_obs"] = 138
        critic_backbone = _Config(
            _target_="gr00t.rl.agents.modules.modules.BaseModule",
            process_output_dim=True,
            module_config_dict=_Config(
                input_dim=["critic_obs"],
                output_dim=[1],
                layer_config=_Config(type="MLP", hidden_dims=[512, 256, 128], activation="SiLU"),
            ),
        )
        value_model = __import__(
            "gr00t.rl.trl.modules.actor_critic_modules_recurrent",
            fromlist=["RecurrentCritic"],
        ).RecurrentCritic(
            env_config,
            algo_config,
            critic_backbone,
            module_dim_dict={"critic_obs": -1},
            running_mean_std=True,
            rnn_type="lstm",
            rnn_hidden_dim=256,
            rnn_num_layers=2,
        )
        return policy, value_model

    policy, value_model = actual_models(branch)
    policy_state = {key: tensor.detach().cpu().clone() for key, tensor in policy.state_dict().items()}
    value_state = {key: tensor.detach().cpu().clone() for key, tensor in value_model.state_dict().items()}
    policy_schema = train_entrypoint._p2_model_state_schema(
        policy_state,
        name="policy",
        branch=branch,
        architecture=runner.ARCHITECTURES[branch],
        implementation=type(policy).__module__ + "." + type(policy).__name__,
        module=policy,
    )
    value_schema = train_entrypoint._p2_model_state_schema(
        value_state,
        name="value",
        branch=branch,
        architecture="RecurrentCritic",
        implementation=type(value_model).__module__ + "." + type(value_model).__name__,
        module=value_model,
    )

    artifact = common_root / "b1_common_init.pt"
    if not artifact.exists():
        rng_before = p2.capture_rng_state()
        rng_downstream = p2.capture_rng_state()
        common_state, common_identities, common_aggregate = p2.common_core_state(policy)
        artifact_manifest = {
            "schema": "a2_cb2h_pro_p2_common_init_v1",
            "branch": "b1",
            "architecture": runner.ARCHITECTURES["b1"],
            "seed": 0,
            "config_sha256": runner.P2_COMMON_CONFIG_SHA256,
            "runtime_identity": {"runtime_repository": str(runner.RUNTIME_REPOSITORY), "runtime_commit": runner.EXPECTED_RUNTIME_COMMIT},
            "common_prefix": "core.",
            "common_components": list(runner.P2_COMMON_INIT_CONTRACT["common_components"]),
            "common_core_key_schema_sha256": runner.P2_COMMON_INIT_CONTRACT["common_key_schema_sha256"],
            "key_count": len(common_identities),
            "keys": common_identities,
            "aggregate_sha256": common_aggregate,
            "rng_before_policy_identity": rng_before["identity"],
            "rng_downstream_identity": rng_downstream["identity"],
        }
        torch.save({"manifest": artifact_manifest, "state_dict": common_state, "rng_downstream": rng_downstream}, artifact)
    artifact_sha256 = artifact_sha256 or runner.sha256_file(artifact)
    artifact_payload = torch.load(artifact, map_location="cpu", weights_only=False)
    common_identities = list(artifact_payload["manifest"]["keys"])
    common_core_sha = artifact_payload["manifest"]["aggregate_sha256"]
    if branch in {"b1", "b2"}:
        for key, tensor in artifact_payload["state_dict"].items():
            policy_state[key] = tensor.detach().cpu().clone()
        policy_schema = train_entrypoint._p2_model_state_schema(
            policy_state,
            name="policy",
            branch=branch,
            architecture=runner.ARCHITECTURES[branch],
            implementation=type(policy).__module__ + "." + type(policy).__name__,
            module=policy,
        )

    policy_identities = policy_schema["parameter_identities"]
    value_identities = value_schema["parameter_identities"]
    wrapper = SchemaWrapper(policy_identities, value_identities)
    expected_order = [
        (f"policy.{item['key']}", parameter)
        for item, parameter in zip(policy_identities, wrapper.policy._parameters_flat, strict=True)
    ] + [
        (f"value_model.{item['key']}", parameter)
        for item, parameter in zip(value_identities, wrapper.value_model._parameters_flat, strict=True)
    ]
    optimizer = torch.optim.AdamW(
        [{"params": list(wrapper.policy._parameters_flat)}, {"params": list(wrapper.value_model._parameters_flat)}],
        lr=runner.EXPECTED_ACTOR_LEARNING_RATE,
        betas=(0.9, 0.999),
        eps=1.0e-8,
        weight_decay=0.0,
    )
    scheduler = get_constant_schedule(optimizer)
    accelerator = Accelerator(cpu=True)
    wrapper, optimizer = accelerator.prepare(wrapper, optimizer)
    optimizer_schema, scheduler_schema = train_entrypoint._p2_optimizer_parameter_schema(
        wrapper, optimizer, scheduler, expected_order
    )
    runner._validate_p2_optimizer_schema(
        optimizer_schema,
        scheduler_schema,
        policy_schema=policy_schema,
        value_schema=value_schema,
    )
    # BC-only activity: exercise a real optimizer step for policy parameters,
    # leaving value/core.std lazy state absent exactly as production does.
    active_names = [
        name for name, _ in expected_order
        if name.startswith("policy.") and name != "policy.core.std"
    ]
    active_set = set(active_names)
    for name, parameter in expected_order:
        if name in active_set:
            parameter.grad = torch.ones_like(parameter)
    optimizer.step()
    for state in optimizer.state.values():
        state["step"] = torch.tensor(float(runner.EXPECTED_OPTIMIZER_STATE_STEP))
    for _ in range(runner.EXPECTED_FINAL_GLOBAL_STEP):
        scheduler.step()
    final_optimizer_state = optimizer.state_dict()
    id_by_name = {}
    for group_state, group_runtime in zip(final_optimizer_state["param_groups"], optimizer.param_groups, strict=True):
        for parameter_id, parameter in zip(group_state["params"], group_runtime["params"], strict=True):
            name = next(name for name, item in expected_order if item is parameter)
            id_by_name[name] = int(parameter_id)
    active_entries = [
        {"id": id_by_name[name], "name": name, "shape": list(parameter.shape), "dtype": str(parameter.dtype)}
        for name, parameter in expected_order
        if name in active_set
    ]
    active_parameter_schema = {
        "schema": "a2_cb2h_pro_p2_active_parameter_schema_v1",
        "parameter_count": len(active_entries),
        "ordered_parameters": active_entries,
        "parameter_ids": [item["id"] for item in active_entries],
        "parameter_names": [item["name"] for item in active_entries],
        "schema_sha256": runner.sha256_bytes(runner.canonical_json(active_entries).encode()),
    }
    expected_active = runner._expected_p2_bc_active_parameters(optimizer_schema)
    assert active_parameter_schema["ordered_parameters"] == expected_active
    assert active_parameter_schema["parameter_count"] == policy_schema["parameter_count"] - 1

    step0_path = common_root / f"{branch}_step0_manifest.json"
    step0 = {
        "schema": "a2_cb2h_pro_p2_step0_manifest_v1", "global_step": 0, "optimizer": None,
        "branch": branch, "architecture": runner.ARCHITECTURES[branch], "seed": 0,
        "config_sha256": runner.P2_COMMON_CONFIG_SHA256,
        "runtime_identity": {"runtime_repository": str(runner.RUNTIME_REPOSITORY), "runtime_commit": runner.EXPECTED_RUNTIME_COMMIT},
        "common_core_sha256": common_core_sha, "common_core_key_schema_sha256": runner.P2_COMMON_INIT_CONTRACT["common_key_schema_sha256"],
        "common_core_keys": list(p2.P2_COMMON_KEY_SCHEMA), "common_core_key_identities": common_identities,
        "artifact_sha256": artifact_sha256, "common_init_manifest_sha256": runner.sha256_bytes(runner.canonical_json(artifact_payload["manifest"]).encode()),
        "common_init_artifact": str(artifact.resolve()), "rng_before_policy_identity": artifact_payload["manifest"]["rng_before_policy_identity"], "rng_downstream_identity": artifact_payload["manifest"]["rng_downstream_identity"],
        "device": "cuda:0", "policy_state_schema": policy_schema, "value_state_schema": value_schema,
        "policy_state_schema_sha256": policy_schema["schema_sha256"], "value_state_schema_sha256": value_schema["schema_sha256"],
        "optimizer_parameter_schema": optimizer_schema, "scheduler_schema": scheduler_schema,
    }
    runner._atomic_json(step0_path, step0)
    if branch == "b2" and not (common_root / "b1_step0_manifest.json").exists():
        _write_realistic_branch_artifacts("b1", root.parent / "fixture-b1", common_root, artifact_sha256=artifact_sha256)

    config_source = Path(__file__).resolve().parents[1] / "config/exp/wbmanip" / f"door_open_a2_base_v19_p2_{branch}.yaml"
    config = copy.deepcopy(yaml.safe_load(config_source.read_text()))
    if "obs" not in config:
        b1_source = yaml.safe_load((config_source.parent / "door_open_a2_base_v19_p2_b1.yaml").read_text())
        config["obs"] = copy.deepcopy(b1_source["obs"])
        config["simulator"] = copy.deepcopy(b1_source["simulator"])
        config["obs"]["obs_dict"]["context_vision_obs"] = ["context_rgb_image"]
    config.update({"experiment_dir": str(root), "checkpoint": None, "checkpoint_load_mode": "full", "auto_load_latest": False})
    config["algo"]["trl"].update({"num_total_batches": 500, "num_ppo_epochs": 1, "gradient_accumulation_steps": 1})
    config["callbacks"]["model_save"]["save_frequency"] = 500
    config["simulator"]["config"]["cameras"]["architecture_id"] = runner.ARCHITECTURES[branch]
    config["simulator"]["config"]["cameras"]["policy_multiview"]["architecture_id"] = runner.ARCHITECTURES[branch]
    common = config["algo"]["config"]["p2_common_init"]
    common.update({
        "artifact_path": str(artifact),
        "step0_manifest_path": str(step0_path),
        "source_step0_manifest_path": str(common_root / "b1_step0_manifest.json"),
        "trusted_artifact_sha256": artifact_sha256 if branch == "b2" else "REQUIRED_AFTER_B1_STEP0_SEAL",
        "trusted_source_step0_manifest_sha256": runner.sha256_file(common_root / "b1_step0_manifest.json") if branch == "b2" else "REQUIRED_AFTER_B1_STEP0_SEAL",
        "runtime_identity": {"runtime_repository": str(runner.RUNTIME_REPOSITORY), "runtime_commit": runner.EXPECTED_RUNTIME_COMMIT},
    })
    config_path = root / "config.yaml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False))

    checkpoint_path = root / "model_step_000500.pt"
    torch.save({"policy_state_dict": policy_state, "value_state_dict": value_state, "optimizer_state_dict": final_optimizer_state, "lr_scheduler_state_dict": scheduler.state_dict(), "state": {"global_step": 500}}, checkpoint_path)
    runtime = {"runtime_repository": str(runner.RUNTIME_REPOSITORY), "runtime_commit": runner.EXPECTED_RUNTIME_COMMIT}
    checkpoint_ref = {"path": str(checkpoint_path), "sha256": runner.sha256_file(checkpoint_path), "size": checkpoint_path.stat().st_size, "global_step": 500}
    config_ref = {"path": str(config_path), "sha256": runner.sha256_file(config_path), "size": config_path.stat().st_size, "architecture": runner.ARCHITECTURES[branch], "branch": branch, "common_init": common, "effective_training_contract": dict(runner.P2_COMMON_INIT_CONTRACT["effective_training"])}
    proof = {
        "schema": "a2_cb2h_pro_p2_pre_teardown_completion_v1", "operation": "p2_pre_teardown_completion", "proof_stage": "PRE_TEARDOWN", "branch": branch, "root": str(root.resolve()),
        "start_global_step": 0, "target_global_step": 500, "expected_additional_iterations": 500, "completed_iterations": 500, "callback_train_begin_seen": True, "callback_step_end_count": 500, "callback_max_steps": 500,
        "backward_call_count": 2000, "optimizer_step_count": 2000, "scheduler_step_count": 500, "scheduler_step_count_before": 1, "scheduler_step_count_after": 501, "scheduler_last_epoch_before": 0, "scheduler_last_epoch_after": 500, "observed_global_steps": list(range(1, 501)),
        "final_checkpoint": checkpoint_ref, "final_config": config_ref,
        "common_init_artifact": {"path": str(artifact), "sha256": artifact_sha256}, "step0_manifest": {"path": str(step0_path), "sha256": runner.sha256_file(step0_path)}, "runtime": runtime,
        "natural_kit_lifecycle_pass": False, "lifecycle_status": "UNRESOLVED", "controlled_post_training_exit": True,
        "active_parameter_schema": active_parameter_schema,
    }
    proof["manifest_content_sha256"] = runner.sha256_bytes(runner.canonical_json(proof).encode())
    runner._atomic_json(root / "pre_teardown_completion_proof.json", proof)
    metrics = {
        "schema": runner.P2_RUNTIME_METRICS_SCHEMA, "branch": branch, "training_performed": True, "global_step_start": 0, "global_step_final": 500, "target_global_step": 500, "completed_iterations": 500, "callbacks": 500, "callback_train_begin_seen": True, "callback_step_end_count": 500, "callback_max_steps": 500,
        "backward_calls": 2000, "optimizer_steps": 2000, "backward_call_count": 2000, "optimizer_step_count": 2000, "scheduler_step_count": 500, "scheduler_step_count_before": 1, "scheduler_step_count_after": 501, "scheduler_last_epoch_before": 0, "scheduler_last_epoch_after": 500, "observed_global_steps": list(range(1, 501)), "scheduler": {"step_count": 501, "last_epoch": 500}, "lifecycle": {"natural": False, "status": "UNRESOLVED", "controlled": True}, "runtime": runtime,
        "final_checkpoint": checkpoint_ref, "final_config": config_ref, "common_init": proof["common_init_artifact"], "step0_manifest": proof["step0_manifest"], "active_parameter_schema": active_parameter_schema, "peak_vram_mib": 100.0,
    }
    metrics["content_sha256"] = runner.sha256_bytes(runner.canonical_json(metrics).encode())
    runner._atomic_json(root / "runtime_metrics.json", metrics)
    telemetry = {
        "schema": "a2_cb2h_pro_p2_gpu_telemetry_v1", "record_count": 3, "sample_interval_s": 5.0, "max_adjacent_gap_s": 15.0,
        "records": [
            {"physical_gpu_index": "7", "logical_gpu_index": 0, "logical_device": "cuda:0", "uuid": runner.EXPECTED_GPU_UUID, "cuda_visible_devices": "7", "cuda_device_order": "PCI_BUS_ID", "binding_mode": "single-visible-logical-cuda0-v3", "world_size": 1, "memory_used_mib": 100.0, "memory_total_mib": 46080.0, "utilization_gpu_pct": 10.0, "power_draw_w": 20.0, "temperature_c": 40.0, "sample_time_ns": 1_000_000_000},
            {"physical_gpu_index": "7", "logical_gpu_index": 0, "logical_device": "cuda:0", "uuid": runner.EXPECTED_GPU_UUID, "cuda_visible_devices": "7", "cuda_device_order": "PCI_BUS_ID", "binding_mode": "single-visible-logical-cuda0-v3", "world_size": 1, "memory_used_mib": 120.0, "memory_total_mib": 46080.0, "utilization_gpu_pct": 20.0, "power_draw_w": 25.0, "temperature_c": 41.0, "sample_time_ns": 2_000_000_000},
            {"physical_gpu_index": "7", "logical_gpu_index": 0, "logical_device": "cuda:0", "uuid": runner.EXPECTED_GPU_UUID, "cuda_visible_devices": "7", "cuda_device_order": "PCI_BUS_ID", "binding_mode": runner.EXPECTED_GPU_BINDING_MODE, "world_size": 1, "memory_used_mib": 110.0, "memory_total_mib": 46080.0, "utilization_gpu_pct": 15.0, "power_draw_w": 22.0, "temperature_c": 40.5, "sample_time_ns": 4_000_000_000},
        ],
        "peak_vram_mib": 120.0, "process_started_ns": 1_500_000_000, "process_ended_ns": 3_500_000_000,
        "gpu_identity": {"physical_gpu_index": "7", "logical_gpu_index": 0, "logical_device": "cuda:0", "uuid": runner.EXPECTED_GPU_UUID, "cuda_visible_devices": "7", "cuda_device_order": "PCI_BUS_ID", "binding_mode": "single-visible-logical-cuda0-v3", "world_size": 1},
    }
    return telemetry


def test_p2_optimizer_requires_accelerate_wrapper_and_adamw_inner():
    import gr00t.rl.train_agent_trl as train_entrypoint
    from accelerate import Accelerator
    from transformers.optimization import get_constant_schedule

    class TinyBranch(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.parameters_flat = torch.nn.ParameterList(
                [torch.nn.Parameter(torch.ones(2)) for _ in range(3)]
            )

    class TinyWrapper(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.policy = TinyBranch()
            self.value_model = TinyBranch()

    wrapper = TinyWrapper()
    expected_order = train_entrypoint._p2_trainable_parameter_order(wrapper.policy, wrapper.value_model)
    optimizer = torch.optim.AdamW(
        [{"params": list(wrapper.policy.parameters())}, {"params": list(wrapper.value_model.parameters())}],
        lr=runner.EXPECTED_ACTOR_LEARNING_RATE,
        betas=(0.9, 0.999),
        eps=1.0e-8,
        weight_decay=0.0,
    )
    scheduler = get_constant_schedule(optimizer)
    prepared_wrapper, prepared_optimizer = Accelerator(cpu=True).prepare(wrapper, optimizer)
    schema, _ = train_entrypoint._p2_optimizer_parameter_schema(
        prepared_wrapper,
        prepared_optimizer,
        scheduler,
        expected_order,
    )
    assert schema["optimizer_wrapper_class"] == "accelerate.optimizer.AcceleratedOptimizer"
    assert schema["optimizer_class"] == "torch.optim.adamw.AdamW"

    raw_wrapper = TinyWrapper()
    raw_optimizer = torch.optim.AdamW(
        [{"params": list(raw_wrapper.policy.parameters())}, {"params": list(raw_wrapper.value_model.parameters())}],
        lr=runner.EXPECTED_ACTOR_LEARNING_RATE,
    )
    with pytest.raises(RuntimeError, match="prepared AcceleratedOptimizer"):
        train_entrypoint._p2_optimizer_parameter_schema(
            raw_wrapper,
            raw_optimizer,
            get_constant_schedule(raw_optimizer),
            train_entrypoint._p2_trainable_parameter_order(raw_wrapper.policy, raw_wrapper.value_model),
        )

    decoy_wrapper = TinyWrapper()
    decoy_optimizer = torch.optim.SGD(
        [{"params": list(decoy_wrapper.policy.parameters())}, {"params": list(decoy_wrapper.value_model.parameters())}],
        lr=runner.EXPECTED_ACTOR_LEARNING_RATE,
    )
    decoy_wrapper, decoy_optimizer = Accelerator(cpu=True).prepare(decoy_wrapper, decoy_optimizer)
    with pytest.raises(RuntimeError, match="torch.optim.adamw.AdamW"):
        train_entrypoint._p2_optimizer_parameter_schema(
            decoy_wrapper,
            decoy_optimizer,
            get_constant_schedule(decoy_optimizer.optimizer),
            train_entrypoint._p2_trainable_parameter_order(decoy_wrapper.policy, decoy_wrapper.value_model),
        )


def test_p2_hf_decay_group_state_order_does_not_define_active_membership():
    import torch
    from accelerate import Accelerator
    from transformers import Trainer
    from transformers.optimization import get_constant_schedule
    import gr00t.rl.train_agent_trl as train_entrypoint

    class Core(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.std = torch.nn.Parameter(torch.ones(3))
            self.linear = torch.nn.Linear(3, 3)
            self.norm = torch.nn.LayerNorm(3)
            self.proj = torch.nn.Linear(3, 2)

    class Policy(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.core = Core()

    class Value(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.linear = torch.nn.Linear(3, 1)

    class PolicyAndValueWrapper(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.policy = Policy()
            self.value_model = Value()

    wrapper = PolicyAndValueWrapper()
    expected_order = train_entrypoint._p2_trainable_parameter_order(wrapper.policy, wrapper.value_model)
    tracker = train_entrypoint._p2_register_gradient_activity(expected_order)
    try:
        decay_names = Trainer.get_decay_parameter_names(None, wrapper)
        grouped_parameters = [
            {
                "params": [parameter for name, parameter in wrapper.named_parameters() if name in decay_names],
                "weight_decay": 0.1,
            },
            {
                "params": [parameter for name, parameter in wrapper.named_parameters() if name not in decay_names],
                "weight_decay": 0.0,
            },
        ]
        optimizer = torch.optim.AdamW(grouped_parameters, lr=runner.EXPECTED_ACTOR_LEARNING_RATE)
        scheduler = get_constant_schedule(optimizer)
        wrapper, optimizer = Accelerator(cpu=True).prepare(wrapper, optimizer)
        optimizer_schema, _ = train_entrypoint._p2_optimizer_parameter_schema(
            wrapper,
            optimizer,
            scheduler,
            expected_order,
        )
        tracker.bind_optimizer_schema(optimizer_schema)

        loss = sum(
            parameter.sum()
            for name, parameter in expected_order
            if name.startswith("policy.") and name != "policy.core.std"
        )
        loss.backward()
        optimizer.step()
        active = tracker.snapshot(optimizer)
        validated = runner._validate_active_parameter_schema(
            active,
            step0_optimizer_schema=optimizer_schema,
        )
        assert validated == active
        assert tracker.hook_order() != [
            item["name"]
            for item in optimizer_schema["ordered_parameters"]
            if item["name"] in active["parameter_names"]
        ]
        serialized_state_names = [
            next(
                item["name"]
                for item in optimizer_schema["ordered_parameters"]
                if item["id"] == parameter_id
            )
            for parameter_id in optimizer.state_dict()["state"]
        ]
        assert serialized_state_names != active["parameter_names"]
        assert active["parameter_names"] == [item["name"] for item in runner._expected_p2_bc_active_parameters(optimizer_schema)]
        assert all(not name.startswith("value_model.") and name != "policy.core.std" for name in active["parameter_names"])
    finally:
        tracker.remove()


def test_runner_execute_mocked_subprocess_seals_b1_b2_pair_and_no_retry(monkeypatch, tmp_path):
    output_root = tmp_path / "output"
    common_root = output_root / "common_init"
    b1_root = output_root / "b1"
    b2_root = output_root / "b2"
    plan = runner.P2Plan(output_root, common_root, output_root / "serial", (runner.P2Branch("b1", b1_root, ("branch=b1",), ("fake", "b1")), runner.P2Branch("b2", b2_root, ("branch=b2",), ("fake", "b2"))), {})
    monkeypatch.setattr(runner, "validate_overlay_repository", lambda path: Path(path).resolve())
    monkeypatch.setattr(runner, "validate_runtime_repository", lambda path: {"repository": str(path), "commit": runner.EXPECTED_RUNTIME_COMMIT})
    monkeypatch.setattr(runner, "validate_teacher_triplet", lambda: {})
    telemetry_by_branch = {}
    current_branch = {"value": None}

    class FakeSampler:
        def __init__(self, environment):
            self.environment = environment
            self._thread = None
        def sample_once(self):
            return None
        def start(self):
            self._thread = SimpleNamespace(is_alive=lambda: False)
        def stop(self, **kwargs):
            assert kwargs["process_ended_ns"] > kwargs["process_started_ns"]
            return telemetry_by_branch[current_branch["value"]]

    monkeypatch.setattr(runner, "GpuTelemetrySampler", FakeSampler)

    def fake_run(command, **kwargs):
        del kwargs
        branch = "b2" if any("p2_common_init.branch=b2" in item for item in command) else "b1"
        current_branch["value"] = branch
        root = b2_root if branch == "b2" else b1_root
        artifact_sha = runner.sha256_file(common_root / "b1_common_init.pt") if (common_root / "b1_common_init.pt").exists() else None
        telemetry_by_branch[branch] = _write_realistic_branch_artifacts(branch, root, common_root, artifact_sha256=artifact_sha)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    assert runner._execute_plan(plan) == 0
    assert (output_root / "serial" / "pair_manifest.json").is_file()
    assert (b1_root / "p2_branch_manifest.json").is_file()
    assert (b2_root / "p2_branch_manifest.json").is_file()


def test_p2_step0_checkpoint_optimizer_and_telemetry_reject_terminal_decoys(tmp_path):
    import copy

    branch_root = tmp_path / "b1"
    common_root = tmp_path / "common_init"
    telemetry = _write_realistic_branch_artifacts("b1", branch_root, common_root)
    step0_path = common_root / "b1_step0_manifest.json"
    artifact_sha256 = runner.sha256_file(common_root / "b1_common_init.pt")
    step0, _, _ = runner.load_json_snapshot(step0_path)
    proof_active = json.loads((branch_root / "pre_teardown_completion_proof.json").read_text())["active_parameter_schema"]
    expected_active = runner._expected_p2_bc_active_parameters(step0["optimizer_parameter_schema"])
    assert proof_active["ordered_parameters"] == expected_active
    assert proof_active["parameter_count"] == len(expected_active)
    assert proof_active["parameter_count"] == sum(
        item["name"].startswith("policy.") and item["name"] != "policy.core.std"
        for item in step0["optimizer_parameter_schema"]["ordered_parameters"]
    )

    for mutation in (
        lambda candidate: candidate["ordered_parameters"].pop(),
        lambda candidate: candidate["ordered_parameters"].append(
            next(item for item in expected_active if item["name"].startswith("policy."))
        ),
        lambda candidate: candidate["ordered_parameters"].__setitem__(
            slice(0, 2),
            [candidate["ordered_parameters"][1], candidate["ordered_parameters"][0]],
        ),
        lambda candidate: candidate["ordered_parameters"][0].update(
            {"id": candidate["ordered_parameters"][0]["id"] + 1}
        ),
        lambda candidate: candidate["ordered_parameters"][0].update({"shape": [2]}),
        lambda candidate: candidate["ordered_parameters"][0].update({"dtype": "torch.float64"}),
    ):
        candidate = copy.deepcopy(proof_active)
        mutation(candidate)
        candidate["parameter_count"] = len(candidate["ordered_parameters"])
        candidate["parameter_ids"] = [item["id"] for item in candidate["ordered_parameters"]]
        candidate["parameter_names"] = [item["name"] for item in candidate["ordered_parameters"]]
        candidate["schema_sha256"] = runner.sha256_bytes(
            runner.canonical_json(candidate["ordered_parameters"]).encode()
        )
        with pytest.raises(RuntimeError, match="active parameter|BC-active|unused|trusted"):
            runner._validate_active_parameter_schema(
                candidate,
                step0_optimizer_schema=step0["optimizer_parameter_schema"],
            )

    truncated = copy.deepcopy(step0)
    truncated["common_core_key_identities"] = truncated["common_core_key_identities"][:-1]
    with pytest.raises(RuntimeError, match="156|identities"):
        runner._validate_step0_manifest_value(truncated, expected_branch="b1", artifact_sha256=artifact_sha256, expected_artifact_path=common_root / "b1_common_init.pt")

    correlated = copy.deepcopy(step0)
    correlated["common_core_sha256"] = "f" * 64
    with pytest.raises(RuntimeError, match="aggregate|common core"):
        runner._validate_step0_manifest_value(correlated, expected_branch="b1", artifact_sha256=artifact_sha256, expected_artifact_path=common_root / "b1_common_init.pt")

    outside = tmp_path / "outside" / "b1_common_init.pt"
    outside.parent.mkdir()
    outside.write_bytes((common_root / "b1_common_init.pt").read_bytes())
    relocated = copy.deepcopy(step0)
    relocated["common_init_artifact"] = str(outside)
    with pytest.raises(RuntimeError, match="exact path"):
        runner._validate_step0_manifest_value(
            relocated,
            expected_branch="b1",
            artifact_sha256=artifact_sha256,
            expected_artifact_path=common_root / "b1_common_init.pt",
        )

    wrong_shape = copy.deepcopy(step0)
    wrong_shape["policy_state_schema"]["identities"][0]["shape"] = [1]
    with pytest.raises(RuntimeError, match="schema|shape/dtype"):
        runner._validate_step0_manifest_value(
            wrong_shape,
            expected_branch="b1",
            artifact_sha256=artifact_sha256,
            expected_artifact_path=common_root / "b1_common_init.pt",
        )

    checkpoint = torch.load(branch_root / "model_step_000500.pt", map_location="cpu", weights_only=False)
    reordered_state_checkpoint = copy.deepcopy(checkpoint)
    reordered_state_checkpoint["optimizer_state_dict"]["state"] = dict(
        reversed(list(reordered_state_checkpoint["optimizer_state_dict"]["state"].items()))
    )
    reordered_state_path = tmp_path / "checkpoint-state-map-reordered.pt"
    torch.save(reordered_state_checkpoint, reordered_state_path)
    reordered_validation = runner.validate_checkpoint_artifact(
        reordered_state_path,
        step0_manifest=step0,
        active_parameter_schema=proof_active,
    )
    assert reordered_validation["optimizer_state_count"] == proof_active["parameter_count"]

    for mutation, message in (
        (lambda payload: payload["policy_state_dict"].update({next(iter(payload["policy_state_dict"])): "not-a-tensor"}), "tensor"),
        (lambda payload: payload["value_state_dict"].update({next(iter(payload["value_state_dict"])): torch.empty(0)}), "non-empty"),
        (lambda payload: payload["optimizer_state_dict"].update({"state": {}}), "non-empty"),
        (lambda payload: payload["optimizer_state_dict"]["state"].update({max(payload["optimizer_state_dict"]["state"]) + 1: {"step": torch.tensor(1.0), "exp_avg": torch.ones(1), "exp_avg_sq": torch.ones(1)}}), "parameter IDs"),
        (lambda payload: payload["optimizer_state_dict"]["state"][next(iter(payload["optimizer_state_dict"]["state"]))].update({"exp_avg": torch.ones(1)}), "shape"),
        (lambda payload: payload["optimizer_state_dict"]["state"][next(iter(payload["optimizer_state_dict"]["state"]))].update({"step": torch.tensor(1.0)}), "step"),
    ):
        candidate = copy.deepcopy(checkpoint)
        mutation(candidate)
        candidate_path = tmp_path / f"candidate-{message.replace(' ', '-').replace('/', '-')}.pt"
        torch.save(candidate, candidate_path)
        with pytest.raises(RuntimeError, match=message):
            runner.validate_checkpoint_artifact(
                candidate_path,
                step0_manifest=step0,
                active_parameter_schema=json.loads((branch_root / "pre_teardown_completion_proof.json").read_text())["active_parameter_schema"],
            )

    with pytest.raises(RuntimeError, match="at least two"):
        runner.validate_gpu_telemetry({**telemetry, "records": telemetry["records"][:1], "record_count": 1})
    stale = copy.deepcopy(telemetry)
    stale["records"][0]["sample_time_ns"] = stale["process_started_ns"] + 1
    with pytest.raises(RuntimeError, match="bracket"):
        runner.validate_gpu_telemetry(stale)
    bounded = copy.deepcopy(telemetry)
    bounded["records"][1]["memory_used_mib"] = runner.VRAM_LIMIT_MIB
    with pytest.raises(RuntimeError, match="VRAM"):
        runner.validate_gpu_telemetry(bounded)
    missing_cadence = copy.deepcopy(telemetry)
    missing_cadence.pop("sample_interval_s")
    with pytest.raises(RuntimeError, match="top-level"):
        runner.validate_gpu_telemetry(missing_cadence)
    interior_stripped = copy.deepcopy(telemetry)
    interior_stripped["records"] = [interior_stripped["records"][0], interior_stripped["records"][2]]
    interior_stripped["record_count"] = 2
    interior_stripped["records"][1]["sample_time_ns"] = interior_stripped["records"][0]["sample_time_ns"] + 10_000_000_000
    interior_stripped["peak_vram_mib"] = max(record["memory_used_mib"] for record in interior_stripped["records"])
    with pytest.raises(RuntimeError, match="cadence"):
        runner.validate_gpu_telemetry(interior_stripped)
    huge_gap = copy.deepcopy(telemetry)
    huge_gap["records"][1]["sample_time_ns"] = huge_gap["records"][0]["sample_time_ns"] + 16_000_000_000
    huge_gap["records"][2]["sample_time_ns"] = huge_gap["records"][1]["sample_time_ns"] + 1_000_000_000
    with pytest.raises(RuntimeError, match="cadence"):
        runner.validate_gpu_telemetry(huge_gap)


def test_p2_gpu_telemetry_duration_count_and_strict_gap_boundaries():
    import copy
    import math

    identity = {
        "physical_gpu_index": runner.EXPECTED_GPU_INDEX,
        "logical_gpu_index": int(runner.EXPECTED_LOGICAL_GPU_INDEX),
        "logical_device": "cuda:0",
        "uuid": runner.EXPECTED_GPU_UUID,
        "cuda_visible_devices": runner.EXPECTED_GPU_INDEX,
        "cuda_device_order": runner.EXPECTED_CUDA_DEVICE_ORDER,
        "binding_mode": runner.EXPECTED_GPU_BINDING_MODE,
        "world_size": 1,
    }

    def make_telemetry(timestamps, process_started_ns, process_ended_ns):
        records = [
            {
                **identity,
                "memory_used_mib": 100.0 + (index % 3),
                "memory_total_mib": 46080.0,
                "utilization_gpu_pct": 10.0,
                "power_draw_w": 20.0,
                "temperature_c": 40.0,
                "sample_time_ns": timestamp,
            }
            for index, timestamp in enumerate(timestamps)
        ]
        return {
            "schema": runner.P2_TELEMETRY_SCHEMA,
            "record_count": len(records),
            "records": records,
            "peak_vram_mib": max(record["memory_used_mib"] for record in records),
            "process_started_ns": process_started_ns,
            "process_ended_ns": process_ended_ns,
            "sample_interval_s": runner.P2_TELEMETRY_SAMPLE_INTERVAL_S,
            "max_adjacent_gap_s": runner.P2_TELEMETRY_MAX_ADJACENT_GAP_S,
            "gpu_identity": dict(identity),
        }

    # The real retry1 sampler spent query latency in addition to its 5.0 s
    # wait.  This long fixture has 5.1/5.2 s start-to-start intervals, 761
    # records, and a 3910 s child interval: count < ceil(duration / 5.0).
    first_timestamp_ns = 1_000_000_000_000
    timestamps = [first_timestamp_ns]
    for index in range(760):
        interval_ns = 5_100_000_000 if index % 2 == 0 else 5_200_000_000
        timestamps.append(timestamps[-1] + interval_ns)
    long_telemetry = make_telemetry(
        timestamps,
        process_started_ns=timestamps[0] + 2_000_000_000,
        process_ended_ns=timestamps[-1] - 2_000_000_000,
    )
    process_duration_s = (
        long_telemetry["process_ended_ns"] - long_telemetry["process_started_ns"]
    ) / 1.0e9
    assert len(timestamps) == 761
    assert process_duration_s == 3910.0
    assert len(timestamps) < math.ceil(
        process_duration_s / runner.P2_TELEMETRY_SAMPLE_INTERVAL_S
    )
    assert runner.validate_gpu_telemetry(long_telemetry) == long_telemetry

    # The sealed metadata cannot be caller-adjusted to make a different
    # cadence/count contract acceptable.
    for field, value in (("sample_interval_s", 5.1), ("max_adjacent_gap_s", 10.0)):
        tampered_metadata = copy.deepcopy(long_telemetry)
        tampered_metadata[field] = value
        with pytest.raises(RuntimeError, match="drifted"):
            runner.validate_gpu_telemetry(tampered_metadata)

    # The stronger actual bound is strict: just below 10 s is accepted, while
    # exactly 10 s is rejected even though both are below the nominal 15 s.
    just_under_bound = copy.deepcopy(long_telemetry)
    just_under_bound["records"][1]["sample_time_ns"] = (
        just_under_bound["records"][0]["sample_time_ns"] + 9_999_999_999
    )
    assert runner.validate_gpu_telemetry(just_under_bound) == just_under_bound
    exact_bound = copy.deepcopy(long_telemetry)
    exact_bound["records"][1]["sample_time_ns"] = (
        exact_bound["records"][0]["sample_time_ns"] + 10_000_000_000
    )
    with pytest.raises(RuntimeError, match="cadence"):
        runner.validate_gpu_telemetry(exact_bound)

    # Two endpoint samples cannot cover a long process, and removing an
    # interior sample must fail after record_count/timestamp updates.
    two_boundary_samples = copy.deepcopy(long_telemetry)
    two_boundary_samples["records"] = [
        two_boundary_samples["records"][0],
        two_boundary_samples["records"][-1],
    ]
    two_boundary_samples["record_count"] = 2
    two_boundary_samples["peak_vram_mib"] = max(
        record["memory_used_mib"] for record in two_boundary_samples["records"]
    )
    with pytest.raises(RuntimeError, match="cadence"):
        runner.validate_gpu_telemetry(two_boundary_samples)

    missing_interior = copy.deepcopy(long_telemetry)
    missing_interior["records"].pop(1)
    missing_interior["record_count"] = len(missing_interior["records"])
    missing_interior["peak_vram_mib"] = max(
        record["memory_used_mib"] for record in missing_interior["records"]
    )
    with pytest.raises(RuntimeError, match="cadence"):
        runner.validate_gpu_telemetry(missing_interior)

    # Exact count-boundary coverage: three records with two gaps just below
    # 10 s are sufficient for a duration just below 20 s; exact 10 s remains
    # rejected by the strict gap rule.
    boundary_timestamps = [
        first_timestamp_ns,
        first_timestamp_ns + 9_999_999_999,
        first_timestamp_ns + 19_999_999_998,
    ]
    just_under_count_boundary = make_telemetry(
        boundary_timestamps,
        process_started_ns=boundary_timestamps[0],
        process_ended_ns=boundary_timestamps[-1],
    )
    assert runner.validate_gpu_telemetry(just_under_count_boundary) == just_under_count_boundary


def test_p2_pair_consumer_validates_manifest_snapshot_and_handles_race(monkeypatch, tmp_path):
    output_root = tmp_path / "output"
    common_root = output_root / "common_init"
    b1_root = output_root / "b1"
    b2_root = output_root / "b2"
    plan = runner.P2Plan(
        output_root,
        common_root,
        output_root / "serial",
        (runner.P2Branch("b1", b1_root, ("branch=b1",), ("fake", "b1")), runner.P2Branch("b2", b2_root, ("branch=b2",), ("fake", "b2"))),
        {},
    )
    monkeypatch.setattr(runner, "validate_overlay_repository", lambda path: Path(path).resolve())
    monkeypatch.setattr(runner, "validate_runtime_repository", lambda path: {"repository": str(path), "commit": runner.EXPECTED_RUNTIME_COMMIT})
    monkeypatch.setattr(runner, "validate_teacher_triplet", lambda: {})
    current_branch = {"value": None}
    telemetry_by_branch = {}

    class FakeSampler:
        def __init__(self, environment):
            self._thread = None
        def sample_once(self):
            return None
        def start(self):
            self._thread = SimpleNamespace(is_alive=lambda: False)
        def stop(self, **kwargs):
            return telemetry_by_branch[current_branch["value"]]

    monkeypatch.setattr(runner, "GpuTelemetrySampler", FakeSampler)

    def fake_run(command, **kwargs):
        del kwargs
        branch = "b2" if any("p2_common_init.branch=b2" in item for item in command) else "b1"
        current_branch["value"] = branch
        root = b2_root if branch == "b2" else b1_root
        artifact_sha = runner.sha256_file(common_root / "b1_common_init.pt") if (common_root / "b1_common_init.pt").exists() else None
        telemetry_by_branch[branch] = _write_realistic_branch_artifacts(branch, root, common_root, artifact_sha256=artifact_sha)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    assert runner._execute_plan(plan) == 0
    b1_seal, _, _ = runner.load_json_snapshot(common_root / "b1_common_init_seal.json")
    manifest_path = b1_root / "p2_branch_manifest.json"
    original = manifest_path.read_bytes()
    minimal = {"schema": runner.P2_BRANCH_SCHEMA, "branch": "b1"}
    runner._atomic_json(manifest_path, minimal)
    with pytest.raises(RuntimeError, match="incomplete|content"):
        runner.validate_pair_and_seal(plan, b1_seal)
    manifest_path.write_bytes(original)
    replaced, _, _ = runner.load_json_snapshot(manifest_path)
    replaced["final_config"]["sha256"] = "0" * 64
    replaced.pop("content_sha256")
    replaced["content_sha256"] = runner.sha256_bytes(runner.canonical_json(replaced).encode())
    runner._atomic_json(manifest_path, replaced)
    with pytest.raises(RuntimeError, match="config"):
        runner.validate_pair_and_seal(plan, b1_seal)
    manifest_path.write_bytes(original)

    replaced, _, _ = runner.load_json_snapshot(manifest_path)
    replaced["teacher"] = {"checkpoint": {"path": "tampered", "sha256": "0" * 64}}
    replaced.pop("content_sha256")
    replaced["content_sha256"] = runner.sha256_bytes(runner.canonical_json(replaced).encode())
    runner._atomic_json(manifest_path, replaced)
    with pytest.raises(RuntimeError, match="teacher"):
        runner.validate_pair_and_seal(plan, b1_seal)
    manifest_path.write_bytes(original)

    replaced, _, _ = runner.load_json_snapshot(manifest_path)
    replaced["command"] = ["tampered-command"]
    replaced["command_sha256"] = runner.sha256_bytes(runner.canonical_json(replaced["command"]).encode())
    replaced.pop("content_sha256")
    replaced["content_sha256"] = runner.sha256_bytes(runner.canonical_json(replaced).encode())
    runner._atomic_json(manifest_path, replaced)
    with pytest.raises(RuntimeError, match="command"):
        runner.validate_pair_and_seal(plan, b1_seal)
    manifest_path.write_bytes(original)

    original_loader = runner.load_json_snapshot
    def race_loader(path, **kwargs):
        snapshot = original_loader(path, **kwargs)
        if Path(path).name == "p2_branch_manifest.json":
            Path(path).write_text("{}\n", encoding="utf-8")
        return snapshot

    monkeypatch.setattr(runner, "load_json_snapshot", race_loader)
    pair = runner.validate_pair_and_seal(plan, b1_seal)
    assert pair["branch_manifests"]["b1"]["sha256"] == runner.sha256_bytes(original)
