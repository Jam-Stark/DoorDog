from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap

import numpy as np
import pytest

from gr00t.rl.scripts import run_a2_cb2h_pro_p1 as p1


def _write(path: Path, payload: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def _source_fixture(tmp_path: Path) -> tuple[Path, Path, str, str]:
    checkpoint = tmp_path / "model_step_010000.pt"
    config = tmp_path / "config.yaml"
    checkpoint_sha = _write(checkpoint, b"source-step-10000")
    config_sha = _write(
        config,
        b"checkpoint_load_mode: full\nauto_load_latest: false\n",
    )
    return checkpoint, config, checkpoint_sha, config_sha


def _teacher_fixture(tmp_path: Path) -> tuple[Path, Path, Path, dict[str, str]]:
    checkpoint = tmp_path / "teacher" / "model_step_002000.pt"
    config = checkpoint.with_name("config.yaml")
    manifest = checkpoint.with_name("teacher_manifest.json")
    checkpoint_sha = _write(checkpoint, b"teacher-step-2000")
    config_sha = _write(config, b"teacher config\n")
    manifest_payload = {
        "checkpoint": {"filename": checkpoint.name, "sha256": checkpoint_sha},
        "source": {"commit": p1.EXPECTED_RUNTIME_COMMIT, "config_sha256": config_sha},
        "teacher": {"action_dim": 12},
    }
    manifest_sha = _write(
        manifest,
        (json.dumps(manifest_payload, sort_keys=True) + "\n").encode(),
    )
    return checkpoint, config, manifest, {
        "checkpoint": checkpoint_sha,
        "config": config_sha,
        "manifest": manifest_sha,
    }


def _branch(mode: str, root: Path, overrides: tuple[str, ...]) -> p1.P1BranchSpec:
    return p1.P1BranchSpec(
        mode=mode,
        root=root,
        checkpoint=p1.SOURCE_CHECKPOINT,
        checkpoint_sha256=p1.SOURCE_CHECKPOINT_SHA256,
        checkpoint_config=p1.SOURCE_CONFIG,
        checkpoint_config_sha256=p1.SOURCE_CONFIG_SHA256,
        start_global_step=10000,
        requested_iterations=200,
        run_iterations=200,
        target_global_step=10200,
        overrides=overrides,
        command=(),
    )


def test_source_and_teacher_fixture_sha_binding(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    source_checkpoint, source_config, source_sha, source_config_sha = _source_fixture(tmp_path)
    teacher_checkpoint, teacher_config, teacher_manifest, teacher_hashes = _teacher_fixture(tmp_path)
    monkeypatch.setattr(p1, "SOURCE_CHECKPOINT", source_checkpoint)
    monkeypatch.setattr(p1, "SOURCE_CONFIG", source_config)
    monkeypatch.setattr(p1, "TEACHER_CHECKPOINT", teacher_checkpoint)
    monkeypatch.setattr(p1, "TEACHER_CONFIG", teacher_config)
    monkeypatch.setattr(p1, "TEACHER_MANIFEST", teacher_manifest)
    source = p1.validate_source_checkpoint(
        source_checkpoint,
        source_config,
        expected_checkpoint_sha256=source_sha,
        expected_config_sha256=source_config_sha,
    )
    teacher = p1.validate_teacher_triplet(
        teacher_checkpoint,
        teacher_config,
        teacher_manifest,
        expected_checkpoint_sha256=teacher_hashes["checkpoint"],
        expected_config_sha256=teacher_hashes["config"],
        expected_manifest_sha256=teacher_hashes["manifest"],
    )
    assert source["global_step"] == 10000
    assert source["checkpoint_load_mode"] == "full"
    assert teacher["global_step"] == 2000
    source_checkpoint.write_bytes(b"tampered")
    with pytest.raises(RuntimeError, match="source checkpoint SHA256 drifted"):
        p1.validate_source_checkpoint(
            source_checkpoint,
            source_config,
            expected_checkpoint_sha256=source_sha,
            expected_config_sha256=source_config_sha,
        )


def test_runtime_and_gpu_contract_fail_fast(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    runtime = tmp_path / "c18"
    (runtime / "gr00t/rl/data/tasks/door/scenario_cfg").mkdir(parents=True)
    (runtime / "gr00t/rl/train_agent_trl.py").write_text("# fixture\n")
    (runtime / "gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py").write_text("# fixture\n")
    responses = {("rev-parse", "HEAD"): p1.EXPECTED_RUNTIME_COMMIT, ("status", "--short", "--", "gr00t"): ""}

    def fake_git(_repository: Path, *args: str) -> str:
        return responses[args]

    monkeypatch.setattr(p1, "_git", fake_git)
    runtime_info = p1.validate_runtime_contract(runtime)
    assert runtime_info["commit"] == p1.EXPECTED_RUNTIME_COMMIT
    environment = p1.build_gpu_binding_environment({"WORLD_SIZE": "4", "ACCELERATE_USE_CPU": "1"})
    assert p1.validate_gpu_binding_environment(environment)["logical_device"] == "cuda:0"
    with pytest.raises(RuntimeError, match="distributed launch variables"):
        p1.validate_gpu_binding_environment({**environment, "WORLD_SIZE": "1"})
    with pytest.raises(RuntimeError, match="binding-v3"):
        p1.validate_gpu_binding_environment({**environment, "A2_EXPECTED_GPU_UUID": "GPU-wrong"})


def test_n2_manifest_fixture_binds_exact_source_and_artifact_sha(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    root = tmp_path / p1.N2_INPUT_ROOT.name
    artifact = root / "step_010000" / "formal.json"
    artifact_sha = _write(artifact, b"sealed n2 artifact")
    manifest = {
        "schema": "a2_cb2h_pro_phase_a_v1",
        "operation": "n2",
        "controller": "student",
        "case_identity_mapping_equal": True,
        "required_steps": [1000, 2500, 5000, 7500, 10000],
        "artifacts": [{"path": "step_010000/formal.json", "sha256": artifact_sha}],
        "selection": {
            "checkpoint": {
                "global_step": 10000,
                "sha256": p1.SOURCE_CHECKPOINT_SHA256,
                "config_sha256": p1.SOURCE_CONFIG_SHA256,
            }
        },
    }
    manifest_path = root / "phase_a_manifest.json"
    manifest_sha = _write(manifest_path, (json.dumps(manifest, sort_keys=True) + "\n").encode())
    monkeypatch.setattr(p1, "N2_PHASE_MANIFEST_SHA256", manifest_sha)
    result = p1.validate_n2_contract(root)
    assert result["artifact_count"] == 1
    manifest["selection"]["checkpoint"]["sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(RuntimeError, match="N2 phase manifest SHA256 drifted"):
        p1.validate_n2_contract(root)


def test_n3_fixture_binds_three_replicates_and_case_identity(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    class FakeReplicate:
        active_frame_count = 10206
        case_ids = tuple(f"case-{index}" for index in range(16))

    class FakeInputs:
        root = tmp_path / p1.N3_INPUT_ROOT.name
        phase_manifest_path = root / "phase_a_manifest.json"
        phase_manifest_sha256 = p1.N3_PHASE_MANIFEST_SHA256
        replicates = (FakeReplicate(), FakeReplicate(), FakeReplicate())

    from gr00t.rl.scripts import run_a2_cb2h_pro_n4 as n4

    monkeypatch.setattr(n4, "validate_n3_inputs", lambda _root: FakeInputs())
    result = p1.validate_n3_contract(tmp_path / p1.N3_INPUT_ROOT.name)
    assert result["replicate_count"] == 3
    assert result["active_frame_count"] == [10206, 10206, 10206]
    assert result["case_map_sha256"]


def test_override_contract_and_pair_only_mode_diff(tmp_path: Path):
    teacher = {
        "teacher_actor_path": p1.TEACHER_CHECKPOINT,
        "teacher_config_path": p1.TEACHER_CONFIG,
        "teacher_manifest_path": p1.TEACHER_MANIFEST,
    }
    seq_root = tmp_path / "sequential"
    packed_root = tmp_path / "packed"
    seq = p1.build_training_overrides(
        mode="sequential",
        branch_root=seq_root,
        checkpoint=p1.SOURCE_CHECKPOINT,
        teacher_checkpoint=teacher["teacher_actor_path"],
        teacher_config=teacher["teacher_config_path"],
        teacher_manifest=teacher["teacher_manifest_path"],
    )
    packed = p1.build_training_overrides(
        mode="packed",
        branch_root=packed_root,
        checkpoint=p1.SOURCE_CHECKPOINT,
        teacher_checkpoint=teacher["teacher_actor_path"],
        teacher_config=teacher["teacher_config_path"],
        teacher_manifest=teacher["teacher_manifest_path"],
    )
    p1.validate_training_override_contract(
        seq, mode="sequential", branch_root=seq_root, checkpoint=p1.SOURCE_CHECKPOINT, teacher=teacher, iterations=200
    )
    p1.validate_training_override_contract(
        packed, mode="packed", branch_root=packed_root, checkpoint=p1.SOURCE_CHECKPOINT, teacher=teacher, iterations=200
    )
    assert p1.canonical_branch_contract(seq) == p1.canonical_branch_contract(packed)
    with pytest.raises(ValueError, match="duplicate Hydra override"):
        p1.validate_branch_pair(
            _branch("sequential", seq_root, seq),
            _branch("packed", packed_root, packed + ("num_envs=128",)),
            requested_iterations=200,
        )


def test_plan_is_two_branch_fresh_and_dry_run_has_no_side_effect(monkeypatch, tmp_path: Path):
    source_checkpoint, source_config, source_sha, source_config_sha = _source_fixture(tmp_path)
    teacher_checkpoint, teacher_config, teacher_manifest, teacher_hashes = _teacher_fixture(tmp_path)
    monkeypatch.setattr(p1, "SOURCE_CHECKPOINT", source_checkpoint)
    monkeypatch.setattr(p1, "SOURCE_CONFIG", source_config)
    monkeypatch.setattr(p1, "TEACHER_CHECKPOINT", teacher_checkpoint)
    monkeypatch.setattr(p1, "TEACHER_CONFIG", teacher_config)
    monkeypatch.setattr(p1, "TEACHER_MANIFEST", teacher_manifest)
    monkeypatch.setattr(p1, "TARGET_CONFIG", _write_target_fixture(tmp_path))
    monkeypatch.setattr(p1, "validate_runtime_contract", lambda _path: {"repository": "fixture", "commit": p1.EXPECTED_RUNTIME_COMMIT})
    monkeypatch.setattr(p1, "validate_gpu_binding_environment", lambda env: {"logical_device": "cuda:0"})
    monkeypatch.setattr(p1, "build_gpu_binding_environment", lambda: {})
    monkeypatch.setattr(p1, "validate_n3_contract", lambda _path: {"replicate_count": 3})
    monkeypatch.setattr(p1, "validate_n2_contract", lambda _path: {"required_steps": [1000, 2500, 5000, 7500, 10000]})
    monkeypatch.setattr(
        p1,
        "compose_training_config",
        lambda overrides: {
            "num_envs": 64,
            "headless": True,
            "enable_cameras": True,
            "checkpoint_load_mode": "full",
            "auto_load_latest": False,
            "algo": {
                "trl": {"num_total_batches": 10200},
                "config": {
                    "num_steps_per_env": 8,
                    "num_mini_batches": 4,
                    "actor_learning_rate": 1.0e-4,
                    "use_a2_base": True,
                    "enforce_teacher_rollout": True,
                    "ratio_teacher_rollout": 1.0,
                    "actor": {"view_contract": {"d435i_forward_mode": dict(
                        item.split("=", 1) for item in overrides if item.startswith("algo.config.actor.view_contract.d435i_forward_mode=")
                    )["algo.config.actor.view_contract.d435i_forward_mode"]}},
                },
            },
            "callbacks": {"model_save": {"save_frequency": 10200}},
        },
    )
    monkeypatch.setattr(
        p1,
        "validate_source_checkpoint",
        lambda checkpoint, config: {
            "path": str(checkpoint),
            "sha256": source_sha,
            "config_path": str(config),
            "config_sha256": source_config_sha,
            "global_step": 10000,
        },
    )
    monkeypatch.setattr(
        p1,
        "validate_teacher_triplet",
        lambda *_args: {
            "checkpoint": {"path": str(teacher_checkpoint)},
            "config": {"path": str(teacher_config)},
            "manifest": {"path": str(teacher_manifest)},
        },
    )
    root = tmp_path / "fresh-p1"
    plan = p1.build_p1_plan(root, script_path=tmp_path / "runner.py")
    assert not root.exists()
    assert [branch.mode for branch in plan.branches] == ["sequential", "packed"]
    assert [branch.target_global_step for branch in plan.branches] == [10200, 10200]
    assert plan.paired_extension is False
    assert all("checkpoint_load_mode=full" in branch.overrides for branch in plan.branches)


def _write_target_fixture(tmp_path: Path) -> Path:
    path = tmp_path / "target.yaml"
    path.write_text("target fixture\n")
    return path


def test_paired_extension_requires_both_checkpoints_and_new_retry_root(tmp_path: Path):
    seq = tmp_path / "seq"
    packed = tmp_path / "packed"
    seq.mkdir()
    packed.mkdir()
    (seq / "model_step_010200.pt").write_bytes(b"seq")
    with pytest.raises(p1.P1Blocked, match="both 200-step"):
        p1.validate_paired_extension(seq, packed)
    (packed / "model_step_010200.pt").write_bytes(b"packed")
    assert p1.validate_paired_extension(seq, packed)[0].name == "model_step_010200.pt"
    retry = tmp_path / "retry"
    with pytest.raises(RuntimeError, match="previous failed evidence"):
        p1.validate_retry_root(tmp_path / "missing", retry)
    assert p1.validate_retry_root(seq, retry)[1] == retry.resolve()
    with pytest.raises(RuntimeError, match="new output root"):
        p1.validate_retry_root(seq, seq)


def test_formal_eval_command_is_fixed16_seed0_and_hash_bound(tmp_path: Path):
    branch_root = tmp_path / "sequential"
    branch_root.mkdir()
    checkpoint = branch_root / "model_step_010200.pt"
    config = branch_root / "config.yaml"
    checkpoint_sha = _write(checkpoint, b"final-step-10200")
    config_sha = _write(config, b"effective config\n")
    overrides = p1.build_training_overrides(
        mode="sequential",
        branch_root=branch_root,
        checkpoint=p1.SOURCE_CHECKPOINT,
    )
    spec = p1.P1BranchSpec(
        mode="sequential",
        root=branch_root,
        checkpoint=p1.SOURCE_CHECKPOINT,
        checkpoint_sha256=p1.SOURCE_CHECKPOINT_SHA256,
        checkpoint_config=p1.SOURCE_CONFIG,
        checkpoint_config_sha256=p1.SOURCE_CONFIG_SHA256,
        start_global_step=10000,
        requested_iterations=200,
        run_iterations=200,
        target_global_step=10200,
        overrides=overrides,
        command=(),
    )
    eval_script = tmp_path / "eval.py"
    eval_script.write_text("#\n")
    command = p1.build_formal_eval_command(
        spec,
        tmp_path / "formal-replicate-01",
        replicate_id="replicate_01",
        eval_script=eval_script,
    )
    command_text = " ".join(command)
    assert "--student-d435i-forward-mode sequential" in command_text
    assert "--case-seed 0" in command_text
    assert "--expected-global-step 10200" in command_text
    assert checkpoint_sha in command_text and config_sha in command_text


def test_vram_gate_and_exact_nrmse_formula():
    with pytest.raises(p1.P1Blocked, match="<46 GiB"):
        p1.validate_peak_vram_mib(47104)
    assert p1.validate_peak_vram_mib(47000)["passed"] is True
    target = np.tile(np.arange(12, dtype=np.float64), (4, 1))
    prediction = target.copy()
    prediction[:, 0] += 0.5
    metrics = p1.nrmse_stats(prediction, target)
    expected = 0.5 / (np.std(target[:, 0]) + 1e-6)
    assert metrics["count"] == 4
    assert metrics["per_action_nrmse"][0] == pytest.approx(expected)
    open_loop = p1.n3_open_loop_nrmse(
        prediction,
        target,
        stage=np.array([0, 0, 1, 1]),
    )
    assert open_loop["schema"] == "a2_cb2h_pro_p1_open_loop_nrmse_v1"
    assert set(open_loop["by_stage"]) == {"0", "1"}


def _formal_records(*, packed: bool, replicate_count: int = 3, goals: bool = False):
    records = []
    for replicate in range(replicate_count):
        for env_id in range(16):
            records.append(
                {
                    "replicate_index": replicate,
                    "episode_index": 0,
                    "env_id": env_id,
                    "randomized_case": {"case": env_id},
                    "goal_reached": goals and packed,
                    "max_stage": 2 if packed else (0 if env_id < 2 else 1),
                }
            )
    return records


def test_fixed16x3_case_identity_gates_and_zero_goal_quality_guard():
    seq = _formal_records(packed=False)
    packed = _formal_records(packed=True)
    outcomes = p1.compare_formal_outcomes(seq, packed)
    assert outcomes["case_map_sha256"]
    assert outcomes["stage0_count_reduction_per_16"] == pytest.approx(2.0)
    with pytest.raises(p1.P1Blocked, match="raw P1 adjudication"):
        p1.adjudicate_p1(
            sequential_nrmse={"nrmse_median_12d": "nan"},
            packed_nrmse={"nrmse_median_12d": 0.17},
            sequential_formal=seq,
            packed_formal=packed,
        )
    packed[0]["randomized_case"] = {"case": "drift"}
    with pytest.raises(p1.P1Blocked, match="case identity"):
        p1.compare_formal_outcomes(seq, packed)


def test_seal_json_never_overwrites_and_keeps_content_hash(tmp_path: Path):
    path = tmp_path / "manifest.json"
    payload = p1.seal_json(path, {"schema": p1.P1_SCHEMA, "status": "dry"})
    assert path.is_file()
    assert payload["manifest_content_sha256"]
    with pytest.raises(RuntimeError, match="refusing overwrite"):
        p1.seal_json(path, {"schema": p1.P1_SCHEMA})


def test_absolute_target_contract_rejects_direct_500_and_proves_progression(tmp_path: Path):
    with pytest.raises(ValueError, match="direct 500-step launch is forbidden"):
        p1.build_training_overrides(
            mode="sequential",
            branch_root=tmp_path / "direct500",
            checkpoint=p1.SOURCE_CHECKPOINT,
            iterations=500,
        )
    initial = p1.validate_global_step_progression(10000, 10200, list(range(10001, 10201)))
    extension = p1.validate_global_step_progression(10200, 10500, list(range(10201, 10501)))
    assert (initial["executed_iterations"], extension["executed_iterations"]) == (200, 300)
    with pytest.raises(RuntimeError, match="progression drifted"):
        p1.validate_global_step_progression(10200, 10500, list(range(10202, 10501)))


@pytest.mark.parametrize("mode", p1.P1_FORWARD_MODES)
def test_real_hydra_composition_binds_existing_keys_and_absolute_target(mode: str, tmp_path: Path):
    pytest.importorskip("hydra")
    overrides = p1.build_training_overrides(
        mode=mode,
        branch_root=tmp_path / mode,
        checkpoint=p1.SOURCE_CHECKPOINT,
    )
    config = p1.compose_training_config(overrides)
    effective = p1.validate_effective_training_config(config, mode=mode, target_global_step=10200)
    assert effective["num_envs"] == 64
    assert effective["num_total_batches"] == 10200
    assert effective["d435i_forward_mode"] == mode


def test_effective_training_config_rejects_rollout_minibatch_lr_drift():
    good = {
        "num_envs": 64,
        "headless": True,
        "enable_cameras": True,
        "checkpoint_load_mode": "full",
        "auto_load_latest": False,
        "algo": {
            "trl": {"num_total_batches": 10200},
            "config": {
                "num_steps_per_env": 8,
                "num_mini_batches": 4,
                "actor_learning_rate": 1.0e-4,
                "use_a2_base": True,
                "enforce_teacher_rollout": True,
                "ratio_teacher_rollout": 1.0,
                "actor": {"view_contract": {"d435i_forward_mode": "sequential"}},
            },
        },
        "callbacks": {"model_save": {"save_frequency": 10200}},
    }
    assert p1.validate_effective_training_config(good, mode="sequential", target_global_step=10200)["num_envs"] == 64
    for key, value in (("num_steps_per_env", 4), ("num_mini_batches", 8), ("actor_learning_rate", 2.0e-4)):
        drifted = json.loads(json.dumps(good))
        drifted["algo"]["config"][key] = value
        with pytest.raises(RuntimeError):
            p1.validate_effective_training_config(drifted, mode="sequential", target_global_step=10200)


def test_runtime_telemetry_requires_gpu_identity_and_strict_vram(tmp_path: Path):
    telemetry = tmp_path / "gpu.json"
    telemetry.write_text(json.dumps({
        "schema": p1.P1_GPU_TELEMETRY_SCHEMA,
        "physical_gpu_index": "7",
        "logical_device": "cuda:0",
        "uuid": p1.EXPECTED_GPU_UUID,
        "cuda_visible_devices": "7",
        "world_size": 1,
        "started_at_epoch_s": 1.0,
        "ended_at_epoch_s": 2.0,
        "samples": [{
            "physical_gpu_index": "7",
            "logical_device": "cuda:0",
            "uuid": p1.EXPECTED_GPU_UUID,
            "cuda_visible_devices": "7",
            "world_size": 1,
            "peak_vram_mib": 47000,
            "sample_epoch_s": 1.5,
        }],
        "peak_vram_mib": 47000,
    }))
    loaded = p1.load_gpu_telemetry_peak_vram(telemetry)
    assert loaded["passed"] is True
    telemetry.write_text(json.dumps({
        "schema": p1.P1_GPU_TELEMETRY_SCHEMA,
        "physical_gpu_index": "7", "logical_device": "cuda:0", "uuid": p1.EXPECTED_GPU_UUID,
        "cuda_visible_devices": "7", "world_size": 1, "started_at_epoch_s": 1.0, "ended_at_epoch_s": 2.0,
        "samples": [{"physical_gpu_index": "7", "logical_device": "cuda:0", "uuid": p1.EXPECTED_GPU_UUID,
                      "cuda_visible_devices": "7", "world_size": 1, "peak_vram_mib": 47104, "sample_epoch_s": 1.5}],
        "peak_vram_mib": 47104,
    }))
    with pytest.raises(p1.P1Blocked):
        p1.load_gpu_telemetry_peak_vram(telemetry)
    telemetry.write_text(json.dumps({
        "schema": p1.P1_GPU_TELEMETRY_SCHEMA,
        "physical_gpu_index": "6", "logical_device": "cuda:0", "uuid": p1.EXPECTED_GPU_UUID,
        "cuda_visible_devices": "7", "world_size": 1, "started_at_epoch_s": 1.0, "ended_at_epoch_s": 2.0,
        "samples": [{"physical_gpu_index": "6", "logical_device": "cuda:0", "uuid": p1.EXPECTED_GPU_UUID,
                      "cuda_visible_devices": "7", "world_size": 1, "peak_vram_mib": 47000, "sample_epoch_s": 1.5}],
        "peak_vram_mib": 47000,
    }))
    with pytest.raises(RuntimeError, match="physical GPU identity"):
        p1.load_gpu_telemetry_peak_vram(telemetry)


@pytest.mark.parametrize(("start_global_step", "target_global_step"), ((10000, 10200), (10200, 10500)))
def test_absolute_train_guard_uses_remaining_batches_and_restores_target(start_global_step: int, target_global_step: int):
    class State:
        global_step = 10200

    class Args:
        num_total_batches = 10500
        num_mini_batches = 4
        num_ppo_epochs = 1
        num_micro_batches = 1

    class CallbackHandler:
        def on_train_begin(self, callback_args, callback_state, callback_control, **kwargs):
            return callback_control

        def on_step_end(self, callback_args, callback_state, callback_control, **kwargs):
            return callback_control

    class Accelerator:
        def __init__(self):
            self.backward_calls = 0

        def backward(self, loss):
            self.backward_calls += 1

    class Optimizer:
        def __init__(self):
            self.step_calls = 0

        def step(self):
            self.step_calls += 1

    class Scheduler:
        def __init__(self):
            self.step_calls = 0
            self._step_count = start_global_step + 1
            self.last_epoch = start_global_step

        def step(self):
            self.step_calls += 1
            self._step_count += 1
            self.last_epoch += 1

        def state_dict(self):
            return {"_step_count": self._step_count, "last_epoch": self.last_epoch}

    class Trainer:
        def __init__(self):
            self.state = State()
            self.args = Args()
            self.state.global_step = start_global_step
            self.args.num_total_batches = target_global_step
            self.state.max_steps = target_global_step
            self.callback_handler = CallbackHandler()
            self.accelerator = Accelerator()
            self.optimizer = Optimizer()
            self.lr_scheduler = Scheduler()
            self.inner_iterations = 0

        def train(self):
            args = self.args
            control = self.callback_handler.on_train_begin(args, self.state, object())
            for _ in range(1, args.num_total_batches + 1):
                for _inner in range(8):
                    self.inner_iterations += 1
                for _mini_batch in range(4):
                    self.accelerator.backward(1.0)
                    self.optimizer.step()
                self.state.global_step += 1
                self.lr_scheduler.step()
                self.callback_handler.on_step_end(args, self.state, control)

    p1.install_absolute_target_train_guard(
        Trainer,
        start_global_step=start_global_step,
        target_global_step=target_global_step,
    )
    trainer = Trainer()
    trainer.train()
    expected_additional = target_global_step - start_global_step
    assert trainer.args.num_total_batches == target_global_step
    assert trainer.state.max_steps == target_global_step
    assert trainer.state.global_step == target_global_step
    assert trainer.accelerator.backward_calls == expected_additional * 4
    assert trainer.optimizer.step_calls == expected_additional * 4
    assert trainer.lr_scheduler.step_calls == expected_additional
    assert trainer.lr_scheduler._step_count == target_global_step + 1
    assert trainer.lr_scheduler.last_epoch == target_global_step
    assert trainer.lr_scheduler.step.__func__ is Scheduler.step
    assert trainer.inner_iterations == expected_additional * 8
    assert list(range(3)) == [0, 1, 2]
    assert list(range(2, 8, 2)) == [2, 4, 6]


def test_scheduler_native_snapshot_binds_exact_source_checkpoint_state():
    class KnownSourceScheduler:
        _step_count = 10001
        last_epoch = 10000

        def step(self):
            self._step_count += 1
            self.last_epoch += 1

        def state_dict(self):
            return {"_step_count": self._step_count, "last_epoch": self.last_epoch}

    scheduler = KnownSourceScheduler()
    snapshot = p1._scheduler_native_snapshot(
        scheduler,
        name="known source scheduler",
        expected_last_epoch=10000,
    )
    assert snapshot["step_count"] == 10001
    assert snapshot["last_epoch"] == 10000
    with pytest.raises(RuntimeError, match="expected absolute step"):
        p1._scheduler_native_snapshot(
            scheduler,
            name="known source scheduler",
            expected_last_epoch=9999,
        )


def _sealed_branch_fixture(tmp_path: Path, mode: str):
    root = tmp_path / mode
    root.mkdir()
    final = root / "model_step_010200.pt"
    config = root / "config.yaml"
    _write(final, f"final-{mode}".encode())
    _write(config, b"checkpoint_load_mode: full\nauto_load_latest: false\n")
    spec = p1.P1BranchSpec(
        mode=mode,
        root=root,
        checkpoint=p1.SOURCE_CHECKPOINT,
        checkpoint_sha256=p1.SOURCE_CHECKPOINT_SHA256,
        checkpoint_config=p1.SOURCE_CONFIG,
        checkpoint_config_sha256=p1.SOURCE_CONFIG_SHA256,
        start_global_step=10000,
        requested_iterations=200,
        run_iterations=200,
        target_global_step=10200,
        overrides=(),
        command=(),
    )
    telemetry_path = root / p1.P1_GPU_TELEMETRY_FILENAME
    telemetry_path.write_text(json.dumps({
        "schema": p1.P1_GPU_TELEMETRY_SCHEMA,
        "physical_gpu_index": "7", "logical_device": "cuda:0", "uuid": p1.EXPECTED_GPU_UUID,
        "cuda_visible_devices": "7", "world_size": 1, "started_at_epoch_s": 1.0, "ended_at_epoch_s": 2.0,
        "samples": [{"physical_gpu_index": "7", "logical_device": "cuda:0", "uuid": p1.EXPECTED_GPU_UUID,
                      "cuda_visible_devices": "7", "world_size": 1, "peak_vram_mib": 47000, "sample_epoch_s": 1.5}],
        "peak_vram_mib": 47000,
    }))
    metrics_path = root / p1.P1_RUNTIME_METRICS_FILENAME
    metrics_path.write_text(json.dumps({
        "schema": p1.P1_RUNTIME_METRICS_SCHEMA,
        "training_performed": True,
        "start_global_step": 10000,
        "target_global_step": 10200,
        "num_mini_batches": 4,
        "num_ppo_epochs": 1,
        "num_micro_batches": 1,
        "completed_iterations": 200,
        "additional_iterations": 200,
        "backward_call_count": 800,
        "optimizer_step_count": 800,
        "scheduler_step_count": 200,
        "scheduler_step_count_before": 10001,
        "scheduler_step_count_after": 10201,
        "scheduler_last_epoch_before": 10000,
        "scheduler_last_epoch_after": 10200,
        "observed_global_steps": list(range(10001, 10201)),
        "peak_vram_mib": 47000,
        "iteration_time_s": 1.0,
        "final_checkpoint": {"path": str(final.resolve()), "global_step": 10200, "sha256": p1.sha256_file(final)},
        "gpu_identity": {"physical_gpu_index": "7", "logical_device": "cuda:0", "uuid": p1.EXPECTED_GPU_UUID,
                          "cuda_visible_devices": "7", "world_size": 1},
        "callback_train_begin_seen": True,
        "callback_step_end_count": 200,
        "callback_max_steps": 10200,
    }))
    runtime_evidence = p1.load_runtime_evidence(
        metrics_path, telemetry_path, start_global_step=10000, target_global_step=10200, expected_iterations=200
    )
    manifest = p1.build_branch_manifest(
        spec,
        runtime={"commit": p1.EXPECTED_RUNTIME_COMMIT},
        teacher={},
        final_checkpoint=final,
        final_config=config,
        backward_call_count=800,
        optimizer_step_count=800,
        scheduler_step_count=200,
        scheduler_step_count_before=10001,
        scheduler_step_count_after=10201,
        scheduler_last_epoch_before=10000,
        scheduler_last_epoch_after=10200,
        peak_vram_mib=47000,
        runtime_evidence=runtime_evidence,
    )
    p1.seal_json(root / p1.P1_BRANCH_MANIFEST_FILENAME, manifest)
    return root, p1.sha256_file(root / p1.P1_BRANCH_MANIFEST_FILENAME)


def test_sealed_branch_loader_rejects_tamper_and_swapped_mode(tmp_path: Path):
    seq, seq_sha = _sealed_branch_fixture(tmp_path, "sequential")
    packed, packed_sha = _sealed_branch_fixture(tmp_path, "packed")
    assert p1.load_sealed_branch_manifest(seq, expected_sha256=seq_sha, expected_mode="sequential")["branch"] == "sequential"
    with pytest.raises(RuntimeError, match="mode"):
        p1.load_sealed_branch_manifest(seq, expected_sha256=seq_sha, expected_mode="packed")
    (packed / "model_step_010200.pt").write_bytes(b"tampered")
    with pytest.raises(RuntimeError, match="SHA256"):
        p1.load_sealed_branch_manifest(packed, expected_sha256=packed_sha, expected_mode="packed")


def _write_formal_v2_fixture(
    root: Path,
    *,
    branch: str,
    replicate_id: str,
    checkpoint: dict[str, str],
    config: dict[str, str],
    experience: dict[str, object],
) -> tuple[Path, Path]:
    from gr00t.rl.scripts import run_a2_student_eval_v19 as evaluator

    episodes = [
        {
            "env_id": env_id,
            "episode_index": 0,
            "goal_reached": False,
            "max_stage": 2 if branch == "packed" else (0 if env_id < 2 else 1),
            "randomized_case": {
                "door_hinge_drive_max_force": float(env_id + 1),
                "door_handle_drive_max_force": float(env_id + 2),
                "door_handle_height": float(env_id + 3),
                "door_weight": float(env_id + 4),
            },
            "reward": float(env_id),
            "terminal_reason": "fixture",
        }
        for env_id in range(16)
    ]
    teacher = {"controller": "teacher"}
    contract = {
        "case_seed": 0,
        "checkpoint_identity": checkpoint,
        "controller": "student",
        "enforce_teacher_rollout": False,
        "experience_identity": experience,
        "num_envs": 16,
        "one_episode_per_env": True,
        "pure_student": True,
        "ratio_teacher_rollout": 0.0,
        "replicate_id": replicate_id,
        "student_d435i_forward_mode": branch,
        "teacher_identity": teacher,
        "use_a2_base": True,
    }
    metrics = {
        "case_seed": 0,
        "checkpoint": checkpoint,
        "contract": contract,
        "controller": "student",
        "episodes": episodes,
        "experience": experience,
        "replicate_id": replicate_id,
        "schema": "a2_student_v19_metrics_v2",
        "teacher": teacher,
    }
    ranked = evaluator.rank_episode_records(episodes)
    selected = {
        key: ranked[0][key]
        for key in (
            "env_id",
            "episode_index",
            "goal_reached",
            "max_stage",
            "randomized_case",
            "reward",
            "terminal_reason",
        )
    }
    metrics_path = root / "formal_student_metrics.json"
    selection_path = root / "student_selection.json"
    _write(metrics_path, (json.dumps(metrics, sort_keys=True) + "\n").encode())
    selection = {
        "case_seed": 0,
        "checkpoint": checkpoint,
        "contract": contract,
        "controller": "student",
        "experience": experience,
        "ranking": {"order": evaluator.FORMAL_RANKING_ORDER, "records": ranked},
        "replicate_id": replicate_id,
        "schema": "a2_student_v19_selection_v2",
        "selected": selected,
        "source_metrics": {"path": str(metrics_path.resolve()), "sha256": p1.sha256_file(metrics_path)},
        "teacher": teacher,
    }
    _write(selection_path, (json.dumps(selection, sort_keys=True) + "\n").encode())
    return metrics_path, selection_path


def _write_action_v2_fixture(
    root: Path,
    *,
    branch: str,
    replicate_id: str,
    branch_manifest: dict[str, object],
    n3_contract: dict[str, object],
) -> Path:
    import h5py

    replicate = next(item for item in n3_contract["replicates"] if item["replicate_id"] == replicate_id)
    with h5py.File(replicate["h5"]["path"], "r") as handle:
        active = handle["active_mask"][:].astype(bool)
        active_identity = {
            "env_id": handle["env_id"][:][active].astype(int).tolist(),
            "frame_id": handle["frame_id"][:][active].astype(int).tolist(),
            "case_id": [bytes(value).decode("ascii") for value, flag in zip(handle["case_id"][:], active) if flag],
            "pre_action_stage": handle["pre_action_stage"][:][active].astype(int).tolist(),
        }
    actions = np.zeros((p1.EXPECTED_ACTIVE_FRAME_COUNT, p1.EXPECTED_ACTION_DIM), dtype=np.float32).tolist()
    manifest = {
        "schema": p1.P1_N3_ACTION_SCHEMA,
        "operation": "p1_n3_inference",
        "branch": branch,
        "forward_mode": branch,
        "replicate_id": replicate_id,
        "recurrent_reset_per_replicate": True,
        "checkpoint": branch_manifest["final_checkpoint"],
        "config": branch_manifest["final_config"],
        "n3_phase_manifest": n3_contract["phase_manifest"],
        "n3_h5": replicate["h5"],
        "n3_trajectory_manifest": replicate["trajectory_manifest"],
        "experience": n3_contract["experience_identity"],
        "active_frame_count": p1.EXPECTED_ACTIVE_FRAME_COUNT,
        "active_mask_sha256": replicate["active_mask_sha256"],
        "active_identity_sha256": p1.sha256_bytes(p1.canonical_json(active_identity).encode()),
        "active_identity": active_identity,
        "actions": actions,
        "teacher_action": actions,
        "prediction_contract": {"shape": [p1.EXPECTED_ACTIVE_FRAME_COUNT, p1.EXPECTED_ACTION_DIM], "dtype": "float32", "finite": True, "active_rows_only": True},
    }
    path = root / p1.P1_N3_ACTION_MANIFEST_FILENAME
    p1.seal_json(path, manifest)
    return path


def test_adjudicate_from_sealed_paths_derives_all_identities_and_aligns_replicates(tmp_path: Path):
    seq_root, seq_sha = _sealed_branch_fixture(tmp_path, "sequential")
    packed_root, packed_sha = _sealed_branch_fixture(tmp_path, "packed")
    n3_contract = p1.validate_n3_contract()
    expected_experience = n3_contract["experience_identity"]
    branch_manifests = {
        "sequential": p1.load_sealed_branch_manifest(seq_root, expected_sha256=seq_sha, expected_mode="sequential"),
        "packed": p1.load_sealed_branch_manifest(packed_root, expected_sha256=packed_sha, expected_mode="packed"),
    }
    formal_artifacts = {mode: [] for mode in p1.P1_BRANCHES}
    action_artifacts = {mode: [] for mode in p1.P1_BRANCHES}
    for mode, branch_root in (("sequential", seq_root), ("packed", packed_root)):
        for replicate_id in sorted(item["replicate_id"] for item in n3_contract["replicates"]):
            formal_dir = tmp_path / "formal" / mode / replicate_id
            metrics_path, selection_path = _write_formal_v2_fixture(
                formal_dir,
                branch=mode,
                replicate_id=replicate_id,
                checkpoint={
                    **branch_manifests[mode]["final_checkpoint"],
                    "config_path": branch_manifests[mode]["final_config"]["path"],
                    "config_sha256": branch_manifests[mode]["final_config"]["sha256"],
                },
                config=branch_manifests[mode]["final_config"],
                experience=expected_experience,
            )
            action_path = _write_action_v2_fixture(
                tmp_path / "actions" / mode / replicate_id,
                branch=mode,
                replicate_id=replicate_id,
                branch_manifest=branch_manifests[mode],
                n3_contract=n3_contract,
            )
            formal_artifacts[mode].append({
                "replicate_id": replicate_id,
                "metrics_path": str(metrics_path),
                "selection_path": str(selection_path),
                "metrics_sha256": p1.sha256_file(metrics_path),
                "selection_sha256": p1.sha256_file(selection_path),
            })
            action_artifacts[mode].append({
                "replicate_id": replicate_id,
                "path": str(action_path),
                "sha256": p1.sha256_file(action_path),
            })
    decision = p1.adjudicate_p1_from_paths(
        branch_roots={"sequential": seq_root, "packed": packed_root},
        branch_manifest_shas={"sequential": seq_sha, "packed": packed_sha},
        n3_root=p1.N3_INPUT_ROOT,
        n3_phase_manifest_sha256=p1.N3_PHASE_MANIFEST_SHA256,
        formal_artifacts=formal_artifacts,
        action_artifacts=action_artifacts,
    )
    assert decision["schema"] == p1.P1_ADJUDICATION_SCHEMA
    duplicate = {mode: list(items) for mode, items in formal_artifacts.items()}
    duplicate["packed"][1] = {**duplicate["packed"][0]}
    with pytest.raises(p1.P1Blocked, match="replicate IDs"):
        p1.adjudicate_p1_from_paths(
            branch_roots={"sequential": seq_root, "packed": packed_root},
            branch_manifest_shas={"sequential": seq_sha, "packed": packed_sha},
            n3_root=p1.N3_INPUT_ROOT,
            n3_phase_manifest_sha256=p1.N3_PHASE_MANIFEST_SHA256,
            formal_artifacts=duplicate,
            action_artifacts=action_artifacts,
        )


def test_adjudication_path_root_hash_and_raw_bypass_fail_closed(tmp_path: Path):
    seq_root, seq_sha = _sealed_branch_fixture(tmp_path, "sequential")
    packed_root, packed_sha = _sealed_branch_fixture(tmp_path, "packed")
    with pytest.raises(RuntimeError, match="SHA256"):
        p1.adjudicate_p1_from_paths(
            branch_roots={"sequential": seq_root, "packed": packed_root},
            branch_manifest_shas={"sequential": "0" * 64, "packed": packed_sha},
            n3_root=p1.N3_INPUT_ROOT,
            n3_phase_manifest_sha256=p1.N3_PHASE_MANIFEST_SHA256,
            formal_artifacts={"sequential": [], "packed": []},
            action_artifacts={"sequential": [], "packed": []},
        )
    with pytest.raises(FileNotFoundError):
        p1.adjudicate_p1_from_paths(
            branch_roots={"sequential": seq_root, "packed": packed_root},
            branch_manifest_shas={"sequential": seq_sha, "packed": packed_sha},
            n3_root=tmp_path / "not-n3",
            n3_phase_manifest_sha256=p1.N3_PHASE_MANIFEST_SHA256,
            formal_artifacts={"sequential": [], "packed": []},
            action_artifacts={"sequential": [], "packed": []},
        )
    with pytest.raises(p1.P1Blocked, match="raw P1 adjudication"):
        p1.adjudicate_p1(
            sequential_nrmse={"nrmse_median_12d": "nan"},
            packed_nrmse={"nrmse_median_12d": 0.1},
            sequential_formal=[{"env_id": "0"}],
            packed_formal=[{"env_id": "0"}],
        )


def test_runtime_evidence_reloads_metrics_and_rejects_inline_file_mismatch(tmp_path: Path):
    root, _ = _sealed_branch_fixture(tmp_path, "sequential")
    metrics_path = root / p1.P1_RUNTIME_METRICS_FILENAME
    telemetry_path = root / p1.P1_GPU_TELEMETRY_FILENAME
    evidence = p1.load_runtime_evidence(
        metrics_path,
        telemetry_path,
        start_global_step=10000,
        target_global_step=10200,
        expected_iterations=200,
    )
    metrics = json.loads(metrics_path.read_text())
    metrics["observability"] = {"tampered": True}
    metrics_path.write_text(json.dumps(metrics), encoding="utf-8")
    evidence["metrics_artifact"]["sha256"] = p1.sha256_file(metrics_path)
    with pytest.raises(RuntimeError, match="inline metrics"):
        p1.validate_runtime_evidence(
            evidence,
            start_global_step=10000,
            target_global_step=10200,
            expected_iterations=200,
        )


def test_n3_command_contract_requires_recurrent_reset_and_exact_paths(tmp_path: Path):
    root = tmp_path / "branch"
    root.mkdir()
    final = root / "model_step_010200.pt"
    config = root / "config.yaml"
    _write(final, b"final")
    _write(config, b"config")
    spec = p1.P1BranchSpec("sequential", root, p1.SOURCE_CHECKPOINT, p1.SOURCE_CHECKPOINT_SHA256, p1.SOURCE_CONFIG, p1.SOURCE_CONFIG_SHA256, 10000, 200, 200, 10200, (), ())
    phase = tmp_path / "phase.json"; h5 = tmp_path / "trajectory.h5"; trajectory = tmp_path / "trajectory.json"
    _write(phase, b"phase"); _write(h5, b"h5"); _write(trajectory, b"trajectory")
    contract = {"root": str(tmp_path), "phase_manifest": {"path": str(phase), "sha256": p1.sha256_file(phase)}, "replicates": [{"replicate_id": "replicate_01", "h5": {"path": str(h5), "sha256": p1.sha256_file(h5)}, "trajectory_manifest": {"path": str(trajectory), "sha256": p1.sha256_file(trajectory)}}]}
    command = p1.build_n3_inference_command(spec, tmp_path, tmp_path / "n3-out", replicate_id="replicate_01", n3_contract=contract)
    text = " ".join(command)
    assert "--recurrent-reset-per-replicate" in text
    assert p1.sha256_file(final) in text and p1.sha256_file(h5) in text


def _run_pre_teardown_child(
    tmp_path: Path,
    mode: str,
    *,
    start_global_step: int = 10000,
    target_global_step: int = 10200,
) -> tuple[subprocess.CompletedProcess[str], Path, Path, Path]:
    """Run the absolute-target guard in a fresh interpreter, including os._exit(0)."""
    root = tmp_path / f"branch-{mode}"
    root.mkdir()
    source = tmp_path / f"source-{mode}.pt"
    source_config = tmp_path / f"source-{mode}.yaml"
    _write(source, b"source checkpoint")
    _write(source_config, b"source config")
    _write(root / f"model_step_{target_global_step:06d}.pt", b"final checkpoint")
    _write(root / "config.yaml", b"effective config")
    child = tmp_path / f"pre_teardown_child_{mode}.py"
    child.write_text(
        textwrap.dedent(
            """
            import os
            import sys
            from pathlib import Path
            from types import SimpleNamespace

            import torch
            from gr00t.rl.scripts import run_a2_cb2h_pro_p1 as p1

            root = Path(sys.argv[1])
            source = Path(sys.argv[2])
            source_config = Path(sys.argv[3])
            start_global_step = int(sys.argv[4])
            target_global_step = int(sys.argv[5])
            mode = os.environ["P1_CHILD_MODE"]
            environment = {
                "CUDA_VISIBLE_DEVICES": "7",
                "CUDA_DEVICE_ORDER": "PCI_BUS_ID",
                "A2_GPU_BINDING_MODE": "single-visible-logical-cuda0-v3",
                "A2_EXPECTED_WORLD_SIZE": "1",
                "A2_EXPECTED_HOST_GPU_INDEX": "7",
                "A2_EXPECTED_LOGICAL_GPU_INDEX": "0",
                "A2_EXPECTED_GPU_UUID": p1.EXPECTED_GPU_UUID,
            }

            class CallbackHandler:
                def on_train_begin(self, callback_args, callback_state, callback_control, **kwargs):
                    return callback_control

                def on_step_end(self, callback_args, callback_state, callback_control, **kwargs):
                    return callback_control

            class Accelerator:
                def backward(self, loss):
                    if mode == "error":
                        raise RuntimeError("intentional child training error")

            class Optimizer:
                def step(self):
                    return None

            class Scheduler:
                def __init__(self):
                    offset = 0
                    if mode == "fixed_offset":
                        offset = 5
                    elif mode == "before":
                        offset = 1
                    self._step_count = start_global_step + 1 + offset
                    self.last_epoch = start_global_step + offset
                    if mode == "inconsistent_pair":
                        self.last_epoch += 1

                def step(self):
                    self._step_count += 1
                    self.last_epoch += 1
                    if mode == "after" and self.last_epoch == target_global_step:
                        self._step_count += 1
                        self.last_epoch += 1

                def state_dict(self):
                    return {"_step_count": self._step_count, "last_epoch": self.last_epoch}

            class Trainer:
                def __init__(self):
                    self.state = SimpleNamespace(global_step=start_global_step - 1 if mode == "pretarget" else start_global_step,
                                                 max_steps=target_global_step)
                    self.args = SimpleNamespace(num_total_batches=target_global_step,
                                                num_mini_batches=4,
                                                num_ppo_epochs=1,
                                                num_micro_batches=1)
                    self.callback_handler = CallbackHandler()
                    self.accelerator = Accelerator()
                    self.optimizer = Optimizer()
                    if mode != "no_scheduler":
                        self.lr_scheduler = Scheduler()
                        if mode == "no_counters":
                            del self.lr_scheduler._step_count
                            del self.lr_scheduler.last_epoch

                def train(self):
                    args = self.args
                    control = self.callback_handler.on_train_begin(args, self.state, object())
                    for _ in range(1, args.num_total_batches + 1):
                        for _inner in range(2):
                            pass
                        mini_batches = 3 if mode == "skip_minibatch" else 4
                        for _mini_batch in range(mini_batches):
                            self.accelerator.backward(1.0)
                            self.optimizer.step()
                        self.state.global_step += 1
                        if mode not in ("skip_scheduler", "no_scheduler"):
                            self.lr_scheduler.step()
                            if mode == "excess":
                                self.lr_scheduler.step()
                            if self.state.global_step in (start_global_step + 50, target_global_step):
                                checkpoint_path = root / f"scheduler_step_{self.state.global_step:06d}.pt"
                                torch.save(self.lr_scheduler, checkpoint_path)
                                restored = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
                                if restored.state_dict() != self.lr_scheduler.state_dict():
                                    raise RuntimeError("scheduler native state failed torch.save/torch.load roundtrip")
                        self.callback_handler.on_step_end(args, self.state, control)

            trainer = Trainer()
            p1.install_absolute_target_train_guard(
                Trainer,
                start_global_step=start_global_step,
                target_global_step=target_global_step,
                branch_root=root,
                branch="sequential",
                source={
                    "path": str(source),
                    "sha256": p1.sha256_file(source),
                    "config_path": str(source_config),
                    "config_sha256": p1.sha256_file(source_config),
                    "global_step": start_global_step,
                    "checkpoint_load_mode": "full",
                },
                runtime={"commit": p1.EXPECTED_RUNTIME_COMMIT},
                environment=environment,
                controlled_post_training_exit=True,
            )
            trainer.train()
            (root / "teardown_marker").write_text("natural teardown reached", encoding="utf-8")
            """
        ),
        encoding="utf-8",
    )
    environment = {**os.environ, "PYTHONPATH": str(p1.REPO_ROOT), "P1_CHILD_MODE": mode}
    result = subprocess.run(
        [
            sys.executable,
            str(child),
            str(root),
            str(source),
            str(source_config),
            str(start_global_step),
            str(target_global_step),
        ],
        env=environment,
        capture_output=True,
        text=True,
    )
    return result, root, source, source_config


def _seal_extension_manifest_fixture(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    label: str,
) -> tuple[Path, Path]:
    result, root, source, source_config = _run_pre_teardown_child(
        tmp_path,
        label,
        start_global_step=10200,
        target_global_step=10500,
    )
    assert result.returncode == 0, result.stderr
    target_config = tmp_path / f"{label}-target.yaml"
    target_config.write_text("target config\n", encoding="utf-8")
    expected_contract = {
        "num_envs": 64,
        "num_total_batches": 10500,
        "save_frequency": 10500,
        "num_steps_per_env": 8,
        "num_mini_batches": 4,
        "actor_learning_rate": 1.0e-4,
        "use_a2_base": True,
        "enforce_teacher_rollout": True,
        "ratio_teacher_rollout": 1.0,
        "d435i_forward_mode": "sequential",
    }
    monkeypatch.setattr(p1, "TARGET_CONFIG", target_config)
    monkeypatch.setattr(p1, "compose_training_config", lambda _overrides: {})
    monkeypatch.setattr(
        p1,
        "validate_effective_training_config",
        lambda *_args, **_kwargs: expected_contract,
    )
    telemetry = {
        "schema": p1.P1_GPU_TELEMETRY_SCHEMA,
        "physical_gpu_index": "7",
        "logical_device": "cuda:0",
        "uuid": p1.EXPECTED_GPU_UUID,
        "cuda_visible_devices": "7",
        "world_size": 1,
        "started_at_epoch_s": 1.0,
        "ended_at_epoch_s": 2.0,
        "samples": [{
            "physical_gpu_index": "7",
            "logical_device": "cuda:0",
            "uuid": p1.EXPECTED_GPU_UUID,
            "cuda_visible_devices": "7",
            "world_size": 1,
            "peak_vram_mib": 47000,
            "sample_epoch_s": 1.5,
        }],
        "peak_vram_mib": 47000,
    }
    spec = p1.P1BranchSpec(
        mode="sequential",
        root=root,
        checkpoint=source,
        checkpoint_sha256=p1.sha256_file(source),
        checkpoint_config=source_config,
        checkpoint_config_sha256=p1.sha256_file(source_config),
        start_global_step=10200,
        requested_iterations=500,
        run_iterations=300,
        target_global_step=10500,
        overrides=(),
        command=(),
    )
    finalized = p1._finalize_branch_evidence(
        spec,
        runtime={"commit": p1.EXPECTED_RUNTIME_COMMIT},
        teacher={},
        target_config=target_config,
        telemetry=telemetry,
    )
    return root, root / p1.P1_BRANCH_MANIFEST_FILENAME


def _rewrite_manifest(path: Path, mutate) -> str:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    mutate(manifest)
    unsigned = dict(manifest)
    unsigned.pop("manifest_content_sha256")
    manifest["manifest_content_sha256"] = p1.sha256_bytes(
        p1.canonical_json(unsigned).encode("utf-8")
    )
    path.write_text(p1.canonical_json(manifest) + "\n", encoding="utf-8")
    return p1.sha256_file(path)


def test_pre_teardown_proof_exits_before_teardown_and_parent_seals_unresolved_manifest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    result, root, source, source_config = _run_pre_teardown_child(tmp_path, "success")
    assert result.returncode == 0, result.stderr
    proof_path = root / p1.P1_PRE_TEARDOWN_PROOF_FILENAME
    assert proof_path.is_file()
    assert not (root / "teardown_marker").exists()
    spec = p1.P1BranchSpec(
        mode="sequential",
        root=root,
        checkpoint=source,
        checkpoint_sha256=p1.sha256_file(source),
        checkpoint_config=source_config,
        checkpoint_config_sha256=p1.sha256_file(source_config),
        start_global_step=10000,
        requested_iterations=200,
        run_iterations=200,
        target_global_step=10200,
        overrides=(),
        command=(),
    )
    proof = p1._load_runtime_lifecycle(proof_path, spec=spec)
    assert proof["natural_kit_lifecycle_pass"] is False
    assert proof["lifecycle_status"] == "UNRESOLVED"
    assert proof["controlled_post_training_exit"] is True
    assert (root / "scheduler_step_010050.pt").is_file()
    assert (root / "scheduler_step_010200.pt").is_file()
    assert proof["scheduler_step_count"] == 200
    assert proof["scheduler_step_count_before"] == 10001
    assert proof["scheduler_step_count_after"] == 10201
    assert proof["scheduler_last_epoch_before"] == 10000
    assert proof["scheduler_last_epoch_after"] == 10200

    target_config = tmp_path / "target.yaml"
    _write(target_config, b"target config")
    expected_contract = {
        "num_envs": 64,
        "num_total_batches": 10200,
        "save_frequency": 10200,
        "num_steps_per_env": 8,
        "num_mini_batches": 4,
        "actor_learning_rate": 1.0e-4,
        "use_a2_base": True,
        "enforce_teacher_rollout": True,
        "ratio_teacher_rollout": 1.0,
        "d435i_forward_mode": "sequential",
    }
    monkeypatch.setattr(p1, "compose_training_config", lambda _overrides: {})
    monkeypatch.setattr(p1, "validate_effective_training_config", lambda *_args, **_kwargs: expected_contract)
    telemetry = {
        "schema": p1.P1_GPU_TELEMETRY_SCHEMA,
        "physical_gpu_index": "7",
        "logical_device": "cuda:0",
        "uuid": p1.EXPECTED_GPU_UUID,
        "cuda_visible_devices": "7",
        "world_size": 1,
        "started_at_epoch_s": 1.0,
        "ended_at_epoch_s": 2.0,
        "samples": [{
            "physical_gpu_index": "7",
            "logical_device": "cuda:0",
            "uuid": p1.EXPECTED_GPU_UUID,
            "cuda_visible_devices": "7",
            "world_size": 1,
            "peak_vram_mib": 47000,
            "sample_epoch_s": 1.5,
        }],
        "peak_vram_mib": 47000,
    }
    finalized = p1._finalize_branch_evidence(
        spec,
        runtime={"repository": "fixture", "commit": p1.EXPECTED_RUNTIME_COMMIT},
        teacher={},
        target_config=target_config,
        telemetry=telemetry,
    )
    manifest = finalized["manifest"]
    assert manifest["lifecycle"]["lifecycle_status"] == "UNRESOLVED"
    assert manifest["lifecycle"]["natural_kit_lifecycle_pass"] is False
    assert (root / p1.P1_GPU_TELEMETRY_FILENAME).is_file()
    assert not any("telemetry" in path.name.lower() for path in tmp_path.iterdir() if path != root)


def test_pre_teardown_extension_scheduler_serialization_and_exact_native_delta(tmp_path: Path):
    result, root, source, source_config = _run_pre_teardown_child(
        tmp_path,
        "extension-success",
        start_global_step=10200,
        target_global_step=10500,
    )
    assert result.returncode == 0, result.stderr
    assert (root / "scheduler_step_010250.pt").is_file()
    assert (root / "scheduler_step_010500.pt").is_file()
    spec = p1.P1BranchSpec(
        mode="sequential",
        root=root,
        checkpoint=source,
        checkpoint_sha256=p1.sha256_file(source),
        checkpoint_config=source_config,
        checkpoint_config_sha256=p1.sha256_file(source_config),
        start_global_step=10200,
        requested_iterations=500,
        run_iterations=300,
        target_global_step=10500,
        overrides=(),
        command=(),
    )
    proof = p1._load_runtime_lifecycle(root / p1.P1_PRE_TEARDOWN_PROOF_FILENAME, spec=spec)
    assert proof["scheduler_step_count"] == 300
    assert proof["scheduler_step_count_before"] == 10201
    assert proof["scheduler_step_count_after"] == 10501
    assert proof["scheduler_last_epoch_before"] == 10200
    assert proof["scheduler_last_epoch_after"] == 10500


def test_extension_manifest_seals_and_reloads_with_total_vs_additional_counts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    root, manifest_path = _seal_extension_manifest_fixture(monkeypatch, tmp_path, "extension-manifest")
    result_fields = json.loads(manifest_path.read_text(encoding="utf-8"))["result"]
    assert result_fields["requested_iterations"] == 500
    assert result_fields["completed_iterations"] == 500
    assert result_fields["total_completed_iterations"] == 500
    assert result_fields["additional_iterations"] == 300
    assert result_fields["run_iterations"] == 300
    loaded = p1.load_sealed_branch_manifest(
        root,
        expected_sha256=p1.sha256_file(manifest_path),
        expected_mode="sequential",
        expected_target_global_step=10500,
    )
    assert loaded["result"]["total_completed_iterations"] == 500
    assert loaded["result"]["additional_iterations"] == 300


def test_extension_runtime_evidence_and_failed_json_use_additional_count():
    root = Path("logs_rl/cb2h_pro_p1_pair500_gpu7-20260803/sequential")
    evidence = p1.load_runtime_evidence(
        root / p1.P1_RUNTIME_METRICS_FILENAME,
        root / p1.P1_GPU_TELEMETRY_FILENAME,
        start_global_step=10200,
        target_global_step=10500,
        expected_iterations=300,
    )
    assert evidence["metrics"]["completed_iterations"] == 300
    assert evidence["metrics"]["additional_iterations"] == 300
    assert evidence["metrics"]["observed_global_steps"] == list(range(10201, 10501))


def test_loader_rejects_total_or_additional_iteration_mismatch(tmp_path: Path):
    sequential, sequential_sha = _sealed_branch_fixture(tmp_path, "sequential")
    manifest_path = sequential / p1.P1_BRANCH_MANIFEST_FILENAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["result"]["total_completed_iterations"] = 199
    unsigned = dict(manifest)
    unsigned.pop("manifest_content_sha256")
    manifest["manifest_content_sha256"] = p1.sha256_bytes(
        p1.canonical_json(unsigned).encode("utf-8")
    )
    manifest_path.write_text(p1.canonical_json(manifest) + "\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="exact stage-grid"):
        p1.load_sealed_branch_manifest(
            sequential,
            expected_sha256=p1.sha256_file(manifest_path),
            expected_mode="sequential",
        )

    packed, _packed_sha = _sealed_branch_fixture(tmp_path, "packed")
    packed_manifest_path = packed / p1.P1_BRANCH_MANIFEST_FILENAME
    packed_manifest = json.loads(packed_manifest_path.read_text(encoding="utf-8"))
    packed_manifest["result"]["additional_iterations"] = 199
    unsigned = dict(packed_manifest)
    unsigned.pop("manifest_content_sha256")
    packed_manifest["manifest_content_sha256"] = p1.sha256_bytes(
        p1.canonical_json(unsigned).encode("utf-8")
    )
    packed_manifest_path.write_text(p1.canonical_json(packed_manifest) + "\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="exact stage-grid"):
        p1.load_sealed_branch_manifest(
            packed,
            expected_sha256=p1.sha256_file(packed_manifest_path),
            expected_mode="packed",
        )


def test_loader_rejects_correlated_extension_stage_relabel(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    root, manifest_path = _seal_extension_manifest_fixture(
        monkeypatch, tmp_path, "extension-grid-relabeled"
    )
    manifest_sha = _rewrite_manifest(
        manifest_path,
        lambda manifest: manifest["result"].update(
            requested_iterations=200,
            completed_iterations=200,
            total_completed_iterations=200,
        ),
    )
    with pytest.raises(RuntimeError, match="exact stage-grid"):
        p1.load_sealed_branch_manifest(
            root,
            expected_sha256=manifest_sha,
            expected_mode="sequential",
            expected_target_global_step=10500,
        )


def test_loader_rejects_extension_stage_relabel_without_split_fields(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    root, manifest_path = _seal_extension_manifest_fixture(
        monkeypatch, tmp_path, "extension-grid-missing-split"
    )

    def remove_split_fields(manifest):
        manifest["result"].update(requested_iterations=200, completed_iterations=200)
        manifest["result"].pop("total_completed_iterations")
        manifest["result"].pop("additional_iterations")

    manifest_sha = _rewrite_manifest(manifest_path, remove_split_fields)
    with pytest.raises(RuntimeError, match="explicitly separate total and additional"):
        p1.load_sealed_branch_manifest(
            root,
            expected_sha256=manifest_sha,
            expected_mode="sequential",
            expected_target_global_step=10500,
        )


def test_loader_rejects_initial_stage_relabelled_as_500(tmp_path: Path):
    root, _manifest_sha = _sealed_branch_fixture(tmp_path, "sequential")
    manifest_path = root / p1.P1_BRANCH_MANIFEST_FILENAME
    manifest_sha = _rewrite_manifest(
        manifest_path,
        lambda manifest: manifest["result"].update(
            requested_iterations=500,
            completed_iterations=500,
            total_completed_iterations=500,
        ),
    )
    with pytest.raises(RuntimeError, match="exact stage-grid"):
        p1.load_sealed_branch_manifest(
            root,
            expected_sha256=manifest_sha,
            expected_mode="sequential",
        )


def test_loader_accepts_legacy_pair200_without_split_fields(tmp_path: Path):
    root, _manifest_sha = _sealed_branch_fixture(tmp_path, "sequential")
    manifest_path = root / p1.P1_BRANCH_MANIFEST_FILENAME

    def remove_split_fields(manifest):
        manifest["result"].pop("total_completed_iterations")
        manifest["result"].pop("additional_iterations")

    manifest_sha = _rewrite_manifest(
        manifest_path,
        remove_split_fields,
    )
    loaded = p1.load_sealed_branch_manifest(
        root,
        expected_sha256=manifest_sha,
        expected_mode="sequential",
    )
    assert loaded["result"]["requested_iterations"] == 200
    assert loaded["result"]["completed_iterations"] == 200
    assert loaded["result"]["run_iterations"] == 200
    assert loaded["runtime_evidence"]["metrics"]["additional_iterations"] == 200


def test_manifest_builder_rejects_inverse_initial_stage_grid(tmp_path: Path):
    spec = p1.P1BranchSpec(
        mode="sequential",
        root=tmp_path / "invalid-initial-grid",
        checkpoint=p1.SOURCE_CHECKPOINT,
        checkpoint_sha256=p1.SOURCE_CHECKPOINT_SHA256,
        checkpoint_config=p1.SOURCE_CONFIG,
        checkpoint_config_sha256=p1.SOURCE_CONFIG_SHA256,
        start_global_step=10000,
        requested_iterations=500,
        run_iterations=200,
        target_global_step=10200,
        overrides=(),
        command=(),
    )
    with pytest.raises(RuntimeError, match="exact stage-grid"):
        p1.build_branch_manifest(
            spec,
            runtime={},
            teacher={},
            training_performed=False,
        )


@pytest.mark.parametrize(
    "mode",
    (
        "pretarget",
        "error",
        "no_scheduler",
        "no_counters",
        "skip_scheduler",
        "skip_minibatch",
        "excess",
        "fixed_offset",
        "inconsistent_pair",
        "before",
        "after",
    ),
)
def test_pre_teardown_failure_cannot_promote_exit_zero_or_seal_proof(tmp_path: Path, mode: str):
    result, root, _source, _source_config = _run_pre_teardown_child(tmp_path, mode)
    assert result.returncode != 0
    assert not (root / p1.P1_PRE_TEARDOWN_PROOF_FILENAME).exists()
    assert not (root / "teardown_marker").exists()
