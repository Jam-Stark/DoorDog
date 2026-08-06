from __future__ import annotations

import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
import threading
import time
from copy import deepcopy

import pytest
import torch

from gr00t.rl.scripts import run_a2_cb2h_pro_long as long
from gr00t.rl.scripts import run_a2_cb2h_pro_p2 as p2
import gr00t.rl.train_agent_trl as train_entrypoint
from gr00t.rl.trl.trainer.distill_trainer_a2_base_api import (
    build_cyclic_teacher_mask,
    resolve_mixed_rollout_phase,
    validate_mixed_rollout_schedule,
)


def _long_step0_contract() -> tuple[dict, dict, dict]:
    """Build a small but production-shaped step0/final checkpoint contract."""
    policy_keys = ["p0", "p1", "core.std", "p3"]
    value_keys = ["v0", "v1"]

    def schema(name: str, keys: list[str]) -> dict:
        identities = [
            {"key": key, "shape": [1], "dtype": "torch.float32", "sha256": long.sha256_bytes(b"step0")}
            for key in keys
        ]
        structural = [{"key": item["key"], "shape": item["shape"], "dtype": item["dtype"]} for item in identities]
        digest = long.sha256_bytes(long.canonical_json(identities).encode("utf-8"))
        return {
            "schema": p2.P2_MODEL_STATE_SCHEMA,
            "role": name,
            "key_count": len(keys),
            "keys": keys,
            "identities": identities,
            "schema_sha256": digest,
            "aggregate_sha256": digest,
            "parameter_keys": keys,
            "parameter_identities": structural,
        }

    policy_schema = schema("policy", policy_keys)
    value_schema = schema("value", value_keys)
    ordered = [
        {"id": index, "name": f"policy.{key}", "shape": [1], "dtype": "torch.float32"}
        for index, key in enumerate(policy_keys)
    ] + [
        {"id": index + len(policy_keys), "name": f"value_model.{key}", "shape": [1], "dtype": "torch.float32"}
        for index, key in enumerate(value_keys)
    ]
    hyperparameters = {
        "lr": 1.0e-4,
        "betas": [0.9, 0.999],
        "eps": 1.0e-8,
        "weight_decay": 0.0,
        "amsgrad": False,
        "maximize": False,
        "foreach": None,
        "capturable": False,
        "differentiable": False,
        "fused": None,
        "decoupled_weight_decay": True,
        "initial_lr": 1.0e-4,
    }
    groups = [
        {
            "index": 0,
            "parameter_ids": [0, 1, 2, 3],
            "parameter_names": [item["name"] for item in ordered[:4]],
            "hyperparameters": deepcopy(hyperparameters),
        },
        {
            "index": 1,
            "parameter_ids": [4, 5],
            "parameter_names": [item["name"] for item in ordered[4:]],
            "hyperparameters": deepcopy(hyperparameters),
        },
    ]
    optimizer_schema = {
        "schema": p2.P2_OPTIMIZER_SCHEMA,
        "optimizer_wrapper_class": "accelerate.optimizer.AcceleratedOptimizer",
        "optimizer_class": "torch.optim.adamw.AdamW",
        "parameter_count": len(ordered),
        "ordered_parameters": ordered,
        "param_groups": groups,
        "state_parameter_ids": [],
    }
    scheduler_schema = {
        "schema": p2.P2_SCHEDULER_SCHEMA,
        "scheduler_class": "torch.optim.lr_scheduler.LambdaLR",
        "state_dict": {
            "base_lrs": [1.0e-4, 1.0e-4],
            "last_epoch": 0,
            "_step_count": 1,
            "_get_lr_called_within_step": False,
            "_last_lr": [1.0e-4, 1.0e-4],
            "lr_lambdas": [None, None],
        },
    }
    active_ordered = [ordered[index] for index in (0, 1, 3)]
    active_schema = {
        "schema": "a2_cb2h_pro_p2_active_parameter_schema_v1",
        "parameter_count": len(active_ordered),
        "ordered_parameters": active_ordered,
        "parameter_ids": [0, 1, 3],
        "parameter_names": [item["name"] for item in active_ordered],
        "schema_sha256": long.sha256_bytes(long.canonical_json(active_ordered).encode("utf-8")),
    }
    step0 = {
        "policy_state_schema": policy_schema,
        "value_state_schema": value_schema,
        "optimizer_parameter_schema": optimizer_schema,
        "scheduler_schema": scheduler_schema,
    }
    policy_state = {key: torch.ones(1) for key in policy_keys}
    value_state = {key: torch.ones(1) for key in value_keys}
    optimizer_state = {
        "state": {
            parameter_id: {
                "step": torch.tensor(32000.0),
                "exp_avg": torch.ones(1),
                "exp_avg_sq": torch.ones(1),
            }
            for parameter_id in active_schema["parameter_ids"]
        },
        "param_groups": [
            {"params": list(group["parameter_ids"]), **deepcopy(group["hyperparameters"])} for group in groups
        ],
    }
    final = {
        "policy_state_dict": policy_state,
        "value_state_dict": value_state,
        "optimizer_state_dict": optimizer_state,
        "lr_scheduler_state_dict": {
            "base_lrs": [1.0e-4, 1.0e-4],
            "last_epoch": 8000,
            "_step_count": 8001,
            "_get_lr_called_within_step": False,
            "_last_lr": [1.0e-4, 1.0e-4],
            "lr_lambdas": [None, None],
        },
        "state": {"global_step": 8000},
    }
    return step0, active_schema, final


def test_long_schedule_boundaries_ratios_and_terminal_rejection():
    expected = {
        0: ("L0", 1.0),
        999: ("L0", 1.0),
        1000: ("L1", 0.75),
        1999: ("L1", 0.75),
        2000: ("L2", 0.5),
        3999: ("L2", 0.5),
        4000: ("L3", 0.25),
        7999: ("L3", 0.25),
    }
    for step, (phase, ratio) in expected.items():
        resolved = resolve_mixed_rollout_phase(long.LONG_ROLLOUT_SCHEDULE, step)
        assert (resolved["phase"], resolved["ratio"]) == (phase, ratio)
    with pytest.raises(ValueError, match="terminal/not selectable"):
        resolve_mixed_rollout_phase(long.LONG_ROLLOUT_SCHEDULE, 8000)
    with pytest.raises(ValueError, match="contiguous"):
        validate_mixed_rollout_schedule(
            [{"phase": "L0", "start_step": 1, "end_step": 2, "ratio": 1.0}]
        )
    with pytest.raises(ValueError, match="end at target"):
        validate_mixed_rollout_schedule(long.LONG_ROLLOUT_SCHEDULE[:-1], target_global_step=8000)


@pytest.mark.parametrize("ratio, expected_teacher, expected_student", [(1.0, 64, 0), (0.75, 48, 16), (0.5, 32, 32), (0.25, 16, 48)])
def test_long_rollout_mask_exact_counts_and_64_window_fairness(ratio, expected_teacher, expected_student):
    masks = [build_cyclic_teacher_mask(64, ratio, step) for step in range(64)]
    assert all(int(mask.sum().item()) == expected_teacher for mask in masks)
    student_counts = torch.stack([~mask for mask in masks]).to(torch.int64).sum(dim=0)
    assert torch.equal(student_counts, torch.full((64,), expected_student, dtype=torch.int64))
    assert torch.equal(masks[1], torch.roll(masks[0], shifts=1, dims=0))


def test_long_lifecycle_guard_supports_target_8000_without_changing_500_contract(monkeypatch, tmp_path: Path):
    branch_root = tmp_path / "b1"
    common_root = tmp_path / "common_init"
    branch_root.mkdir()
    common_root.mkdir()
    (branch_root / "config.yaml").write_text("config\n", encoding="utf-8")
    (common_root / "b1_common_init.pt").write_bytes(b"artifact")
    (common_root / "b1_step0_manifest.json").write_text("{}\n", encoding="utf-8")

    class State:
        global_step = 0
        max_steps = 8000

    class Args:
        num_total_batches = 8000

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
            self.lr_scheduler = Scheduler()
            self.callback_handler = CallbackHandler()
            self.optimizer = object()

        def train(self):
            control = object()
            self.callback_handler.on_train_begin(self.args, self.state, control)
            for step in range(1, 8001):
                self.lr_scheduler.step()
                self.state.global_step = step
                self.callback_handler.on_step_end(self.args, self.state, control)
            (branch_root / "model_step_008000.pt").write_bytes(b"checkpoint")

    trainer = Trainer()
    tracker = SimpleNamespace(
        snapshot=lambda optimizer: {"schema": "fake", "parameter_count": 1},
        backward_call_count=lambda: 32000,
        native_optimizer_step_count=lambda optimizer, schema: 32000,
        remove=lambda: None,
    )
    monkeypatch.setattr(train_entrypoint.os, "_exit", lambda code: (_ for _ in ()).throw(SystemExit(code)))
    train_entrypoint._install_p2_lifecycle_guard(
        trainer,
        branch="b1",
        branch_root=branch_root,
        common_artifact_path=common_root / "b1_common_init.pt",
        step0_manifest_path=common_root / "b1_step0_manifest.json",
        runtime_identity={"runtime_repository": str(p2.RUNTIME_REPOSITORY), "runtime_commit": p2.EXPECTED_RUNTIME_COMMIT},
        target_global_step=8000,
        expected_optimizer_state_step=32000,
        active_parameter_tracker=tracker,
    )
    with pytest.raises(SystemExit):
        trainer.train()
    proof = json.loads((branch_root / "pre_teardown_completion_proof.json").read_text(encoding="utf-8"))
    assert proof["target_global_step"] == 8000
    assert proof["scheduler_step_count_after"] == 8001
    assert proof["scheduler_last_epoch_after"] == 8000
    assert proof["backward_call_count"] == 32000
    assert proof["final_checkpoint"]["global_step"] == 8000


def test_long_selection_manifest_winner_and_tamper_rejection(tmp_path: Path):
    snapshot = long.validate_selection_manifest()
    assert snapshot.payload["adjudication"]["selected_branch"] == "b1"
    assert snapshot.payload["adjudication"]["winner"] == "b1"
    assert snapshot.payload["adjudication"]["zero_goals_or_poor_quality_visible"] is True
    tampered = tmp_path / "selection.json"
    tampered.write_bytes(long.SELECTION_MANIFEST.read_bytes() + b"\n")
    with pytest.raises(long.LongTrainingBlocked, match="file SHA drifted"):
        long.validate_selection_manifest(tampered)


def test_long_plan_is_fresh_common_init_and_exact_8000_command(tmp_path: Path):
    output_root = tmp_path / "long"
    plan = long.build_long_plan(output_root)
    assert not output_root.exists()
    assert plan.branch_root == output_root / "b1"
    assert plan.common_root == output_root / "common_init"
    assert "checkpoint=null" in plan.overrides
    assert "algo.config.p2_common_init.mode=create" in plan.overrides
    assert "algo.trl.num_total_batches=8000" in plan.overrides
    assert "callbacks.model_save.save_frequency=500" in plan.overrides
    assert long._schedule_override() in plan.overrides
    assert all(str(output_root) in item for item in plan.command if "branch-root" in item or "common-root" in item)
    assert not any("model_step_000500.pt" in item for item in plan.command)


def test_long_dry_run_is_nonmutating_and_prints_exact_schedule(tmp_path: Path):
    output_root = tmp_path / "dry-run"
    completed = subprocess.run(
        [
            long.sys.executable,
            str(Path(long.__file__).resolve()),
            "--dry-run",
            "--output-root",
            str(output_root),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert not output_root.exists()
    assert "algo.trl.num_total_batches=8000" in completed.stdout
    assert "algo.config.p2_lifecycle.target_global_step=8000" in completed.stdout
    assert "phase:L0" in completed.stdout and "phase:L3" in completed.stdout
    assert "checkpoint=null" in completed.stdout
    assert "deferred_boundary_eval_scope" in completed.stdout


def test_long_initial_sampler_failure_seals_failure_only(monkeypatch, tmp_path: Path):
    output_root = tmp_path / "failure"
    plan = long.build_long_plan(output_root)

    class FailingSampler:
        def __init__(self, _env, _stream, _path):
            pass

        def sample_once(self):
            raise RuntimeError("initial GPU sample failed")

    monkeypatch.setattr(long.p2, "build_child_environment", lambda: {"CUDA_VISIBLE_DEVICES": "7"})
    monkeypatch.setattr(long, "BoundedGpuTelemetrySampler", FailingSampler)
    with pytest.raises(RuntimeError, match="initial GPU sample failed"):
        long.execute_long_plan(plan)
    assert (output_root / long.PLAN_FILENAME).is_file()
    assert (output_root / long.FAILURE_FILENAME).is_file()
    assert "initial GPU sample failed" in (output_root / long.STDERR_FILENAME).read_text(encoding="utf-8")
    assert not (output_root / long.FINAL_MANIFEST_FILENAME).exists()


def test_long_terminal_evidence_validates_checkpoint_boundaries_and_hashes(tmp_path: Path):
    output_root = tmp_path / "terminal"
    plan = long.build_long_plan(output_root)
    output_root.mkdir()
    plan.branch_root.mkdir()
    plan.common_root.mkdir()
    (plan.branch_root / "config.yaml").write_text("config\n", encoding="utf-8")
    (plan.common_root / "b1_common_init.pt").write_bytes(b"artifact")
    step0_contract, active_parameter_schema, final_payload = _long_step0_contract()
    (plan.common_root / "b1_step0_manifest.json").write_text(long.canonical_json(step0_contract), encoding="utf-8")
    for step in range(500, 8001, 500):
        payload = deepcopy(final_payload) if step == 8000 else {"state": SimpleNamespace(global_step=step)}
        torch.save(payload, plan.branch_root / f"model_step_{step:06d}.pt")
    telemetry = {
        "schema": p2.P2_TELEMETRY_SCHEMA,
        "record_count": 2,
        "records": [
            {
                "physical_gpu_index": p2.EXPECTED_GPU_INDEX,
                "logical_gpu_index": 0,
                "logical_device": "cuda:0",
                "uuid": p2.EXPECTED_GPU_UUID,
                "cuda_visible_devices": p2.EXPECTED_GPU_INDEX,
                "cuda_device_order": p2.EXPECTED_CUDA_DEVICE_ORDER,
                "binding_mode": p2.EXPECTED_GPU_BINDING_MODE,
                "world_size": 1,
                "memory_used_mib": 100.0,
                "memory_total_mib": 48000.0,
                "utilization_gpu_pct": 10.0,
                "power_draw_w": 100.0,
                "temperature_c": 40.0,
                "sample_time_ns": 1_000_000_000,
            },
            {
                "physical_gpu_index": p2.EXPECTED_GPU_INDEX,
                "logical_gpu_index": 0,
                "logical_device": "cuda:0",
                "uuid": p2.EXPECTED_GPU_UUID,
                "cuda_visible_devices": p2.EXPECTED_GPU_INDEX,
                "cuda_device_order": p2.EXPECTED_CUDA_DEVICE_ORDER,
                "binding_mode": p2.EXPECTED_GPU_BINDING_MODE,
                "world_size": 1,
                "memory_used_mib": 101.0,
                "memory_total_mib": 48000.0,
                "utilization_gpu_pct": 10.0,
                "power_draw_w": 100.0,
                "temperature_c": 40.0,
                "sample_time_ns": 2_000_000_000,
            },
        ],
        "peak_vram_mib": 101.0,
        "process_started_ns": 1_100_000_000,
        "process_ended_ns": 1_900_000_000,
        "sample_interval_s": 5.0,
        "max_adjacent_gap_s": 15.0,
        "gpu_identity": {
            "physical_gpu_index": p2.EXPECTED_GPU_INDEX,
            "logical_gpu_index": 0,
            "logical_device": "cuda:0",
            "uuid": p2.EXPECTED_GPU_UUID,
            "cuda_visible_devices": p2.EXPECTED_GPU_INDEX,
            "cuda_device_order": p2.EXPECTED_CUDA_DEVICE_ORDER,
            "binding_mode": p2.EXPECTED_GPU_BINDING_MODE,
            "world_size": 1,
        },
    }
    telemetry = p2.validate_gpu_telemetry(telemetry)
    final_checkpoint = long._artifact_ref(plan.branch_root / "model_step_008000.pt", output_root, "final checkpoint")
    final_config = long._artifact_ref(plan.branch_root / "config.yaml", output_root, "final config")
    common_init = long._artifact_ref(plan.common_root / "b1_common_init.pt", output_root, "common init")
    step0 = long._artifact_ref(plan.common_root / "b1_step0_manifest.json", output_root, "step0")
    proof = {
        "schema": "a2_cb2h_pro_p2_pre_teardown_completion_v1",
        "target_global_step": 8000,
        "completed_iterations": 8000,
        "lifecycle_status": "UNRESOLVED",
        "controlled_post_training_exit": True,
        "runtime": {"runtime_repository": str(long.RUNTIME_REPOSITORY), "runtime_commit": long.EXPECTED_RUNTIME_COMMIT},
        "callback_step_end_count": 8000,
        "observed_global_steps": list(range(1, 8001)),
        "backward_call_count": 32000,
        "optimizer_step_count": 32000,
        "final_checkpoint": {**final_checkpoint, "global_step": 8000},
        "final_config": final_config,
        "common_init_artifact": common_init,
        "step0_manifest": step0,
        "active_parameter_schema": active_parameter_schema,
    }
    proof["manifest_content_sha256"] = long.sha256_bytes(long.canonical_json(proof).encode("utf-8"))
    (plan.branch_root / long.PROOF_FILENAME).write_text(long.canonical_json(proof), encoding="utf-8")
    metrics = {
        "schema": p2.P2_RUNTIME_METRICS_SCHEMA,
        "target_global_step": 8000,
        "completed_iterations": 8000,
        "lifecycle": {"natural": False, "status": "UNRESOLVED", "controlled": True},
        "runtime": {"runtime_repository": str(long.RUNTIME_REPOSITORY), "runtime_commit": long.EXPECTED_RUNTIME_COMMIT},
        "callback_step_end_count": 8000,
        "backward_call_count": 32000,
        "optimizer_step_count": 32000,
        "scheduler": {"step_count": 8001, "last_epoch": 8000},
        "active_parameter_schema": active_parameter_schema,
    }
    metrics["content_sha256"] = long.sha256_bytes(long.canonical_json(metrics).encode("utf-8"))
    (plan.branch_root / long.METRICS_FILENAME).write_text(long.canonical_json(metrics), encoding="utf-8")
    evidence = long._validate_long_evidence(plan, telemetry)
    assert evidence["checkpoints"]["8000"]["global_step"] == 8000
    assert set(evidence["checkpoints"]) == {str(step) for step in range(500, 8001, 500)}
    assert evidence["telemetry"]["record_count"] == 2
    (plan.branch_root / long.PROOF_FILENAME).write_text(
        (plan.branch_root / long.PROOF_FILENAME).read_text(encoding="utf-8").replace("8000", "7999", 1),
        encoding="utf-8",
    )
    with pytest.raises(long.LongTrainingBlocked, match="content hash drifted"):
        long._validate_long_evidence(plan, telemetry)


def test_long_immutable_seal_refuses_overwrite_and_live_replace_is_distinct(tmp_path: Path):
    seal = tmp_path / "seal.json"
    first = long._atomic_json(seal, {"value": 1})
    assert json.loads(seal.read_text(encoding="utf-8"))["value"] == 1
    with pytest.raises(FileExistsError):
        long._atomic_json(seal, {"value": 2})
    assert json.loads(seal.read_text(encoding="utf-8"))["value"] == 1
    replaced = long._replace_json(seal, {"value": 3})
    assert replaced["path"] == first["path"]
    assert json.loads(seal.read_text(encoding="utf-8"))["value"] == 3
    existing_log = tmp_path / long.STDOUT_FILENAME
    existing_log.write_text("pre-existing\n", encoding="utf-8")
    with pytest.raises(FileExistsError):
        long._open_exclusive_binary(existing_log)


def test_long_checkpoint_validation_rejects_missing_corrupt_and_outside_symlink(tmp_path: Path):
    root = tmp_path / "branch"
    outside = tmp_path / "outside.pt"
    root.mkdir()
    payload = {"state": SimpleNamespace(global_step=1500)}
    torch.save(payload, root / "model_step_001500.pt")
    with pytest.raises((FileNotFoundError, long.LongTrainingBlocked)):
        long._validate_checkpoint(root / "model_step_002000.pt", 2000, final=False, root=root)
    (root / "model_step_002000.pt").write_bytes(b"not a checkpoint")
    with pytest.raises(long.LongTrainingBlocked, match="could not be loaded"):
        long._validate_checkpoint(root / "model_step_002000.pt", 2000, final=False, root=root)
    torch.save(payload, outside)
    (root / "model_step_002000.pt").unlink()
    (root / "model_step_002000.pt").symlink_to(outside)
    with pytest.raises(long.LongTrainingBlocked, match="symlink is forbidden"):
        long._validate_checkpoint(root / "model_step_002000.pt", 2000, final=False, root=root)


def test_long_final_checkpoint_is_single_snapshot_and_strictly_cross_bound(tmp_path: Path, monkeypatch):
    root = tmp_path / "branch"
    root.mkdir()
    step0, active_parameter_schema, payload = _long_step0_contract()
    checkpoint = root / "model_step_008000.pt"
    torch.save(payload, checkpoint)
    reads = {"count": 0}
    original_snapshot = long.p2.read_immutable_snapshot

    def counted_snapshot(path):
        reads["count"] += 1
        return original_snapshot(path)

    monkeypatch.setattr(long.p2, "read_immutable_snapshot", counted_snapshot)
    result = long._validate_checkpoint(
        checkpoint,
        8000,
        final=True,
        root=root,
        step0_manifest=step0,
        active_parameter_schema=active_parameter_schema,
    )
    assert reads["count"] == 1
    assert result["global_step"] == 8000
    assert result["size"] == checkpoint.stat().st_size
    assert len(result["sha256"]) == 64

    mutations = []
    empty_policy = deepcopy(payload)
    empty_policy["policy_state_dict"] = {}
    mutations.append(("empty policy state", empty_policy))
    empty_value = deepcopy(payload)
    empty_value["value_state_dict"] = {}
    mutations.append(("empty value state", empty_value))
    reordered = deepcopy(payload)
    reordered["policy_state_dict"] = dict(reversed(list(reordered["policy_state_dict"].items())))
    mutations.append(("policy key reorder", reordered))
    shape_drift = deepcopy(payload)
    shape_drift["value_state_dict"]["v0"] = torch.ones(2)
    mutations.append(("value shape drift", shape_drift))
    dtype_drift = deepcopy(payload)
    dtype_drift["policy_state_dict"]["p0"] = torch.ones(1, dtype=torch.float64)
    mutations.append(("policy dtype drift", dtype_drift))
    optimizer_membership = deepcopy(payload)
    optimizer_membership["optimizer_state_dict"]["param_groups"][0]["params"] = [0, 1, 2, 4]
    mutations.append(("optimizer membership drift", optimizer_membership))
    optimizer_order = deepcopy(payload)
    optimizer_order["optimizer_state_dict"]["param_groups"][0]["params"] = [1, 0, 2, 3]
    mutations.append(("optimizer parameter order drift", optimizer_order))
    optimizer_decoy = deepcopy(payload)
    optimizer_decoy["optimizer_state_dict"]["state"][0]["decoy"] = torch.ones(1)
    mutations.append(("optimizer state decoy", optimizer_decoy))
    optimizer_step = deepcopy(payload)
    optimizer_step["optimizer_state_dict"]["state"][1]["step"] = torch.tensor(31999.0)
    mutations.append(("optimizer step drift", optimizer_step))
    scheduler_decoy = deepcopy(payload)
    scheduler_decoy["lr_scheduler_state_dict"]["decoy"] = 1
    mutations.append(("scheduler decoy", scheduler_decoy))
    scheduler_missing = deepcopy(payload)
    del scheduler_missing["lr_scheduler_state_dict"]["_last_lr"]
    mutations.append(("scheduler missing", scheduler_missing))
    scheduler_step = deepcopy(payload)
    scheduler_step["lr_scheduler_state_dict"]["last_epoch"] = 7999
    mutations.append(("scheduler step drift", scheduler_step))
    for label, mutated in mutations:
        torch.save(mutated, checkpoint)
        with pytest.raises(long.LongTrainingBlocked):
            long._validate_checkpoint(
                checkpoint,
                8000,
                final=True,
                root=root,
                step0_manifest=step0,
                active_parameter_schema=active_parameter_schema,
            )
    torch.save(payload, checkpoint)


def test_long_final_checkpoint_accepts_serialized_optimizer_state_reordering(tmp_path: Path):
    root = tmp_path / "branch"
    root.mkdir()
    step0, active_parameter_schema, payload = _long_step0_contract()
    serialized_states = payload["optimizer_state_dict"]["state"]
    payload["optimizer_state_dict"]["state"] = {
        parameter_id: serialized_states[parameter_id] for parameter_id in (3, 0, 1)
    }
    checkpoint = root / "model_step_008000.pt"
    torch.save(payload, checkpoint)
    result = long._validate_checkpoint(
        checkpoint,
        8000,
        final=True,
        root=root,
        step0_manifest=step0,
        active_parameter_schema=active_parameter_schema,
    )
    assert result["optimizer_state_count"] == len(active_parameter_schema["parameter_ids"])


def test_long_source_snapshot_changes_are_detectable(monkeypatch, tmp_path: Path):
    required_labels = {
        "trainer",
        "train_entry",
        "p2_actor",
        "b1_config",
        "p2_runner",
        "v19_bootstrap",
        "long_runner",
    }
    snapshot = long.capture_source_snapshot()
    assert set(snapshot["files"]) == required_labels
    assert snapshot["files"]["p2_runner"]["path"] == str(
        (long.REPO_ROOT / "gr00t/rl/scripts/run_a2_cb2h_pro_p2.py").resolve()
    )
    assert snapshot["files"]["v19_bootstrap"]["path"] == str(
        (long.REPO_ROOT / "gr00t/rl/scripts/run_a2_student_distillation_v19.py").resolve()
    )
    source = tmp_path / "candidate.py"
    source.write_text("v1\n", encoding="utf-8")
    monkeypatch.setattr(long, "SOURCE_CANDIDATE_PATHS", {"candidate": source})
    before = long.capture_source_snapshot()
    source.write_text("v2\n", encoding="utf-8")
    after = long.capture_source_snapshot()
    assert before["files"]["candidate"]["sha256"] != after["files"]["candidate"]["sha256"]
    assert before["files"]["candidate"]["size"] == after["files"]["candidate"]["size"]


def test_long_telemetry_sampler_surfaces_background_errors_and_joins(monkeypatch, tmp_path: Path):
    stream, stream_path = long._open_exclusive_binary(tmp_path / long.TELEMETRY_STREAM_FILENAME)
    calls = {"count": 0}

    def failing_sample(_environment):
        calls["count"] += 1
        if calls["count"] > 1:
            raise RuntimeError("synthetic telemetry failure")
        return {
            "physical_gpu_index": p2.EXPECTED_GPU_INDEX,
            "logical_gpu_index": 0,
            "logical_device": "cuda:0",
            "uuid": p2.EXPECTED_GPU_UUID,
            "cuda_visible_devices": p2.EXPECTED_GPU_INDEX,
            "cuda_device_order": p2.EXPECTED_CUDA_DEVICE_ORDER,
            "binding_mode": p2.EXPECTED_GPU_BINDING_MODE,
            "world_size": 1,
            "memory_used_mib": 100.0,
            "memory_total_mib": 48000.0,
            "utilization_gpu_pct": 10.0,
            "power_draw_w": 100.0,
            "temperature_c": 40.0,
            "sample_time_ns": time.time_ns(),
        }

    monkeypatch.setattr(long.p2, "sample_gpu_telemetry", failing_sample)
    sampler = long.BoundedGpuTelemetrySampler({"CUDA_VISIBLE_DEVICES": "7"}, stream, stream_path)
    sampler.sample_once()
    sampler.start()
    time.sleep(0.05)
    with pytest.raises(RuntimeError, match="telemetry sampler failed"):
        sampler.stop(process_started_ns=1, process_ended_ns=2)
    assert sampler._thread is not None and not sampler._thread.is_alive()
    sampler.close()


def test_long_slow_child_streams_logs_state_and_telemetry_without_capture_or_parent_lists(
    monkeypatch, tmp_path: Path
):
    output_root = tmp_path / "slow-child"
    plan = long.build_long_plan(output_root)
    real_popen = long.subprocess.Popen
    observed_kwargs: dict[str, object] = {}

    def fake_gpu_sample(_environment):
        now = time.time_ns()
        return {
            "physical_gpu_index": p2.EXPECTED_GPU_INDEX,
            "logical_gpu_index": 0,
            "logical_device": "cuda:0",
            "uuid": p2.EXPECTED_GPU_UUID,
            "cuda_visible_devices": p2.EXPECTED_GPU_INDEX,
            "cuda_device_order": p2.EXPECTED_CUDA_DEVICE_ORDER,
            "binding_mode": p2.EXPECTED_GPU_BINDING_MODE,
            "world_size": 1,
            "memory_used_mib": 100.0,
            "memory_total_mib": 48000.0,
            "utilization_gpu_pct": 10.0,
            "power_draw_w": 100.0,
            "temperature_c": 40.0,
            "sample_time_ns": now,
        }

    child_code = (
        "import sys,time\n"
        "for step in (1,2,3):\n"
        " print(f'[A2_ROLLOUT_PHASE] transition=START->L0 global_step={step} ratio=1.0', flush=True)\n"
        " print(f'[A2_ROLLOUT_MASK] phase=L0 ratio=1.0 global_step={step} teacher_count=64 student_count=0 mask_hash=0000000000000000000000000000000000000000000000000000000000000000', flush=True)\n"
        " time.sleep(0.25)\n"
        "print('child stderr', file=sys.stderr, flush=True)\n"
        "raise SystemExit(7)\n"
    )

    def fake_popen(_command, **kwargs):
        observed_kwargs.update(kwargs)
        return real_popen(
            [long.sys.executable, "-u", "-c", child_code],
            **kwargs,
        )

    monkeypatch.setattr(long.p2, "build_child_environment", lambda: {"CUDA_VISIBLE_DEVICES": "7"})
    monkeypatch.setattr(long.p2, "sample_gpu_telemetry", fake_gpu_sample)
    monkeypatch.setattr(long.subprocess, "Popen", fake_popen)

    outcome: dict[str, BaseException | None] = {"error": None}

    def run():
        try:
            long.execute_long_plan(plan)
        except BaseException as exc:
            outcome["error"] = exc

    worker = threading.Thread(target=run)
    worker.start()
    observed_live = False
    deadline = time.monotonic() + 8.0
    while time.monotonic() < deadline and worker.is_alive():
        state_path = output_root / long.LIVE_STATE_FILENAME
        telemetry_path = output_root / long.TELEMETRY_STREAM_FILENAME
        stdout_path = output_root / long.STDOUT_FILENAME
        if state_path.is_file() and telemetry_path.is_file() and stdout_path.is_file():
            state = json.loads(state_path.read_text(encoding="utf-8"))
            telemetry_lines = telemetry_path.read_text(encoding="utf-8").splitlines()
            stdout_text = stdout_path.read_text(encoding="utf-8")
            if (
                state["status"] == "RUNNING"
                and state["last_observed"]["marker_count"] >= 2
                and telemetry_lines
                and "A2_ROLLOUT_MASK" in stdout_text
            ):
                observed_live = True
                break
        time.sleep(0.05)
    worker.join(timeout=8.0)
    assert not worker.is_alive()
    assert observed_live, "live state/log/telemetry were not observable before child exit"
    assert isinstance(outcome["error"], long.LongTrainingBlocked)
    assert observed_kwargs.get("start_new_session") is True
    assert "capture_output" not in observed_kwargs
    assert observed_kwargs.get("stdout") is not None and observed_kwargs.get("stderr") is not None
    assert "records" not in long.BoundedGpuTelemetrySampler.__dict__
    final_state = json.loads((output_root / long.LIVE_STATE_FILENAME).read_text(encoding="utf-8"))
    assert final_state["status"] == "EXITED"
    assert final_state["returncode"] == 7
    assert final_state["child_pid"] == final_state["child_pgid"] == final_state["child_session_id"]
    assert final_state["last_observed"]["marker_count"] == 3
    assert len((output_root / long.TELEMETRY_STREAM_FILENAME).read_text(encoding="utf-8").splitlines()) >= 2
    assert "child stderr" in (output_root / long.STDERR_FILENAME).read_text(encoding="utf-8")
    assert not (output_root / long.FINAL_MANIFEST_FILENAME).exists()
    assert (output_root / long.FAILURE_FILENAME).is_file()
    assert not [path for path in output_root.iterdir() if path.name.startswith(".")]


def test_long_monitor_error_is_visible_while_child_is_alive(monkeypatch, tmp_path: Path):
    output_root = tmp_path / "monitor-error-child"
    plan = long.build_long_plan(output_root)
    real_popen = long.subprocess.Popen

    def fake_gpu_sample(_environment):
        now = time.time_ns()
        return {
            "physical_gpu_index": p2.EXPECTED_GPU_INDEX,
            "logical_gpu_index": 0,
            "logical_device": "cuda:0",
            "uuid": p2.EXPECTED_GPU_UUID,
            "cuda_visible_devices": p2.EXPECTED_GPU_INDEX,
            "cuda_device_order": p2.EXPECTED_CUDA_DEVICE_ORDER,
            "binding_mode": p2.EXPECTED_GPU_BINDING_MODE,
            "world_size": 1,
            "memory_used_mib": 100.0,
            "memory_total_mib": 48000.0,
            "utilization_gpu_pct": 10.0,
            "power_draw_w": 100.0,
            "temperature_c": 40.0,
            "sample_time_ns": now,
        }

    child_code = (
        "import sys,time\n"
        "print('[A2_ROLLOUT_MASK] malformed', flush=True)\n"
        "time.sleep(2.0)\n"
        "print('child still exited naturally', file=sys.stderr, flush=True)\n"
        "raise SystemExit(7)\n"
    )

    def fake_popen(_command, **kwargs):
        return real_popen([long.sys.executable, "-u", "-c", child_code], **kwargs)

    monkeypatch.setattr(long.p2, "build_child_environment", lambda: {"CUDA_VISIBLE_DEVICES": "7"})
    monkeypatch.setattr(long.p2, "sample_gpu_telemetry", fake_gpu_sample)
    monkeypatch.setattr(long.subprocess, "Popen", fake_popen)
    outcome: dict[str, BaseException | None] = {"error": None}

    def run():
        try:
            long.execute_long_plan(plan)
        except BaseException as exc:
            outcome["error"] = exc

    worker = threading.Thread(target=run)
    worker.start()
    observed_error_state = False
    child_alive_during_error = False
    deadline = time.monotonic() + 8.0
    while time.monotonic() < deadline and worker.is_alive():
        state_path = output_root / long.LIVE_STATE_FILENAME
        if state_path.is_file():
            state = json.loads(state_path.read_text(encoding="utf-8"))
            if state["status"] == "MONITOR_ERROR_WAITING_CHILD":
                observed_error_state = True
                child_alive_during_error = Path(f"/proc/{state['child_pid']}").exists()
                assert state["child_pgid"] == state["child_session_id"] == state["child_pid"]
                assert state["logs"]["stdout"]
                assert state["telemetry"]["stream_path"]
                assert state["monitor_error"]["type"] == "LongTrainingBlocked"
                assert "canonical marker" in state["monitor_error"]["message"]
                break
        time.sleep(0.05)
    worker.join(timeout=8.0)
    assert not worker.is_alive()
    assert observed_error_state and child_alive_during_error
    assert isinstance(outcome["error"], long.LongTrainingBlocked)
    final_state = json.loads((output_root / long.LIVE_STATE_FILENAME).read_text(encoding="utf-8"))
    assert final_state["status"] == "EXITED"
    assert final_state["returncode"] == 7
    assert not (output_root / long.FINAL_MANIFEST_FILENAME).exists()
    assert (output_root / long.FAILURE_FILENAME).is_file()
