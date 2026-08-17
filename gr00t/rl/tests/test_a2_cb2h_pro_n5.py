from __future__ import annotations

import copy
from pathlib import Path

import numpy as np
import pytest
import torch

from gr00t.rl.scripts import run_a2_cb2h_pro_n4 as n4
from gr00t.rl.scripts import run_a2_cb2h_pro_n5 as n5


def _raw_step(active_rows: int = 2) -> dict[str, np.ndarray]:
    active = np.zeros((16,), dtype=bool)
    active[:active_rows] = True
    left = np.zeros((16, 384, 216, 3), dtype=np.uint8)
    right = np.zeros((16, 384, 216, 3), dtype=np.uint8)
    head = np.zeros((16, 136, 384, 3), dtype=np.uint8)
    left[:, 0, 0, 0] = np.arange(1, 17, dtype=np.uint8)
    right[:, 0, 0, 0] = np.arange(1, 17, dtype=np.uint8)
    head[:, 0, 0, 0] = np.arange(1, 17, dtype=np.uint8)
    return {
        "left_rgb": left,
        "right_rgb": right,
        "head_rgb": head,
        "camera_meta": np.ones((16, 6), dtype=np.float32),
        "active_mask": active,
    }


class _FakeActor(torch.nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.d435i_forward_mode = "packed"
        self.d435i_vision_module = torch.nn.Sequential(
            torch.nn.SyncBatchNorm(3),
            torch.nn.AdaptiveAvgPool2d((1, 1)),
            torch.nn.Flatten(),
            torch.nn.Linear(3, 128),
        )
        self.head = torch.nn.Linear(1, 1)


def _fake_replicate(tmp_path: Path, active_rows: int = 2) -> n4.N3Replicate:
    h5py = pytest.importorskip("h5py")
    path = tmp_path / "teacher_trajectory.h5"
    with h5py.File(path, "w") as handle:
        raw = _raw_step(active_rows)
        handle.create_dataset("actor_obs", data=np.zeros((16, 81), dtype=np.float32))
        handle.create_dataset("left_rgb", data=raw["left_rgb"])
        handle.create_dataset("right_rgb", data=raw["right_rgb"])
        handle.create_dataset("head_rgb", data=raw["head_rgb"])
        handle.create_dataset("camera_meta", data=raw["camera_meta"])
        handle.create_dataset("active_mask", data=raw["active_mask"])
        handle.create_dataset("teacher_action", data=np.zeros((16, 12), dtype=np.float32))
        handle.create_dataset("pre_action_stage", data=np.zeros((16,), dtype=np.int16))
        handle.create_dataset("done", data=np.zeros((16,), dtype=bool))
        handle.create_dataset("env_id", data=np.arange(16, dtype=np.int16))
        handle.create_dataset("frame_id", data=np.zeros((16,), dtype=np.int64))
        handle.create_dataset("episode_index", data=np.zeros((16,), dtype=np.int16))
        handle.create_dataset("case_id", data=np.asarray([b"0" * 64] * 16, dtype="S64"))
    return n4.N3Replicate(
        replicate_id="replicate_01",
        h5_path=path,
        trajectory_manifest_path=tmp_path / "trajectory.json",
        h5_sha256=n5.sha256_file(path),
        trajectory_manifest_sha256="0" * 64,
        row_count=16,
        active_frame_count=active_rows,
        case_ids=("0" * 64,),
    )


def test_packed_input_filters_active_rows_and_contract_shape():
    raw = _raw_step(active_rows=3)
    packed, count = n5._packed_active_input(raw, "cpu")
    assert count == 3
    assert tuple(packed.shape) == (6, 3, 384, 216)


def test_bn_calibration_freezes_parameters_updates_only_bn_and_counts(tmp_path: Path):
    replicate = _fake_replicate(tmp_path, active_rows=2)
    inputs = n4.N3Inputs(
        root=tmp_path,
        phase_manifest_path=tmp_path / "phase.json",
        phase_manifest_sha256="0" * 64,
        replicates=(replicate,),
    )
    model = _FakeActor()
    before = copy.deepcopy(model.state_dict())
    summary = n5.calibrate_d435_bn(model, inputs, "cpu")
    assert summary.forward_call_count == 1
    assert summary.active_frame_count == 2
    assert summary.packed_sample_count == 4
    assert summary.bn_state_deltas["d435i_vision_module.0.num_batches_tracked"] == 1
    assert any(key.endswith("running_mean") for key in summary.changed_running_stat_keys)
    assert all(not parameter.requires_grad for parameter in model.parameters())
    after = model.state_dict()
    allowed = set(summary.allowed_policy_state_keys)
    for key in before:
        if key not in allowed:
            assert torch.equal(before[key], after[key])


def test_checkpoint_save_preserves_non_bn_payload_fields(tmp_path: Path):
    model = _FakeActor()
    source = tmp_path / "model_step_010000.pt"
    destination = tmp_path / "out.pt"
    payload = {
        "policy_state_dict": copy.deepcopy(model.state_dict()),
        "state": {"global_step": 10000, "optimizer": {"step": 0}},
        "metadata": {"tag": "exact"},
    }
    torch.save(payload, source)
    before = torch.load(source, map_location="cpu", weights_only=False)
    # Mutate one permitted running buffer as a stand-in for the completed pass.
    model.d435i_vision_module[0].running_mean.add_(1.0)
    allowed = n5._allowed_d435_bn_state_keys(before["policy_state_dict"])
    result = n5._save_recalibrated_checkpoint(source, destination, model, allowed)
    after = torch.load(destination, map_location="cpu", weights_only=False)
    assert result["changed_policy_state_keys"]
    assert after["state"] == before["state"]
    assert after["metadata"] == before["metadata"]
    for key in before["policy_state_dict"]:
        if key not in allowed:
            assert torch.equal(before["policy_state_dict"][key], after["policy_state_dict"][key])


def test_n4_baseline_wrong_root_fails_fast(tmp_path: Path):
    with pytest.raises(RuntimeError, match="exact sealed N4 root name"):
        n5.validate_n4_baseline(tmp_path)


def test_gpu_identity_requires_exact_gpu7_logical_cuda0_contract():
    identity = dict(n5.EXPECTED_GPU_IDENTITY)
    identity["name"] = "test-gpu"
    assert n5.validate_gpu_identity(identity) == identity
    for key, value in (
        ("physical_gpu_index", "6"),
        ("logical_device", "cpu"),
        ("uuid", "0" * 32),
        ("cuda_visible_devices", "0"),
        ("training_performed", True),
        ("backward_call_count", 1),
        ("optimizer_step_count", 1),
    ):
        tampered = dict(identity)
        tampered[key] = value
        with pytest.raises(RuntimeError, match="GPU identity drift"):
            n5.validate_gpu_identity(tampered)


def test_failed_n5_run_retains_staging_and_blocks_same_root_retry(tmp_path: Path, monkeypatch):
    source_checkpoint = tmp_path / "source.pt"
    source_config = tmp_path / "config.yaml"
    actor = _FakeActor()
    torch.save({"policy_state_dict": copy.deepcopy(actor.state_dict())}, source_checkpoint)
    source_config.write_text("checkpoint_load_mode: full\n", encoding="utf-8")
    checkpoint_sha = n5.sha256_file(source_checkpoint)
    config_sha = n5.sha256_file(source_config)
    monkeypatch.setattr(n5, "CHECKPOINT", source_checkpoint.resolve())
    monkeypatch.setattr(n5, "CHECKPOINT_CONFIG", source_config.resolve())
    monkeypatch.setattr(n5, "CHECKPOINT_SHA256", checkpoint_sha)
    monkeypatch.setattr(n5, "CHECKPOINT_CONFIG_SHA256", config_sha)

    n4_root = tmp_path / "n4"
    n4_root.mkdir()
    monkeypatch.setattr(n5, "N4_BASELINE_ROOT", n4_root.resolve())
    input_root = tmp_path / "inputs"
    input_root.mkdir()
    replicate = _fake_replicate(input_root, active_rows=2)
    inputs = n4.N3Inputs(
        root=input_root,
        phase_manifest_path=input_root / "phase.json",
        phase_manifest_sha256="0" * 64,
        replicates=(replicate, replicate, replicate),
    )
    baseline = n5.N4Baseline(
        root=n4_root,
        manifest_path=n4_root / "manifest.json",
        manifest_sha256="0" * 64,
        metrics_path=n4_root / "metrics.json",
        metrics_sha256="0" * 64,
        active_frames_path=n4_root / "active.npz",
        active_frames_sha256="0" * 64,
        manifest={},
        metrics={},
    )

    def injected_failure(*_args, **_kwargs):
        raise RuntimeError("injected N5 failure")

    monkeypatch.setattr(n5, "_evaluate_open_loop", injected_failure)
    output_root = (tmp_path / "n5_output").resolve()
    kwargs = {
        "model": actor,
        "inputs": inputs,
        "n4_baseline": baseline,
        "source_checkpoint": source_checkpoint,
        "source_config": source_config,
        "output_root": output_root,
        "gpu_identity": dict(n5.EXPECTED_GPU_IDENTITY),
    }
    with pytest.raises(RuntimeError, match="injected N5 failure"):
        n5.run_n5_recalibration(**kwargs)
    staging = output_root.with_name(f".{output_root.name}.writing")
    assert not output_root.exists()
    assert staging.is_dir()
    with pytest.raises(FileExistsError, match="existing output/staging roots"):
        n5.run_n5_recalibration(**kwargs)
    assert staging.is_dir()


def test_n5_classification_thresholds_and_no_policy_quality_claim():
    baseline = {"episodes": 48, "stage0_count": 10, "mean_max_stage": 1.0}
    candidate = {"episodes": 48, "stage0_count": 5, "mean_max_stage": 1.0}
    result = __import__("gr00t.rl.scripts.run_a2_cb2h_pro_phase_a", fromlist=["classify_n5"]).classify_n5(
        baseline, candidate
    )
    assert result["verdict"] == "SUPPORT_N5_STRONG_STAGE0"
    assert result["policy_quality_evidence"] is False
