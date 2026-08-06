from __future__ import annotations

import hashlib
import json
from pathlib import Path
import uuid

import numpy as np
import pytest
import torch

from gr00t.rl.scripts import run_a2_cb2h_pro_n4 as n4


def _raw_step():
    left = torch.zeros((16, 384, 216, 3), dtype=torch.uint8)
    right = torch.zeros_like(left)
    head = torch.zeros((16, 136, 384, 3), dtype=torch.uint8)
    left[:, 0, 0, 0] = torch.arange(16, dtype=torch.uint8) + 1
    right[:, 0, 0, 0] = torch.arange(16, dtype=torch.uint8) + 20
    head[:, 0, 0, 0] = torch.arange(16, dtype=torch.uint8) + 40
    index = torch.arange(16, dtype=torch.float32)
    meta = torch.stack(
        (
            index + 0.10,
            index + 10.20,
            index + 20.30,
            index.remainder(2.0),
            (index + 1.0).remainder(2.0),
            torch.ones_like(index),
        ),
        dim=1,
    )
    return left, right, head, meta


def test_variant_contract_changes_only_declared_inputs():
    left, right, head, meta = _raw_step()
    for variant in ("HEAD_INVALID", "LEFT_INVALID", "RIGHT_INVALID"):
        out_left, out_right, out_head, out_meta = n4.transform_variant(
            left, right, head, meta, variant
        )
        assert torch.equal(out_left, left)
        assert torch.equal(out_right, right)
        assert torch.equal(out_head, head)
        expected = meta.clone()
        expected[:, {"HEAD_INVALID": 5, "LEFT_INVALID": 3, "RIGHT_INVALID": 4}[variant]] = 0.0
        assert torch.equal(out_meta, expected)

    out_left, out_right, out_head, out_meta = n4.transform_variant(
        left, right, head, meta, "LEFT_RIGHT_SWAP"
    )
    assert torch.equal(out_left, right)
    assert torch.equal(out_right, left)
    assert torch.equal(out_head, head)
    expected_meta = meta.clone()
    expected_meta[:, [0, 1]] = meta[:, [1, 0]]
    expected_meta[:, [3, 4]] = meta[:, [4, 3]]
    assert torch.equal(out_meta, expected_meta)
    assert n4.variant_contract("LEFT_RIGHT_SWAP") == {
        "variant": "LEFT_RIGHT_SWAP",
        "image_content_changed": False,
        "input_order_swapped": True,
        "validity_only": False,
        "metadata_swapped_with_images": True,
    }


def test_transition_window_is_explicit_pm5_active_frames():
    active = np.ones(12, dtype=bool)
    env_id = np.zeros(12, dtype=np.int16)
    stage = np.array([0] * 5 + [1] * 7, dtype=np.int16)
    mask = n4.build_transition_window_mask(active, env_id, stage)
    # The transition is the first frame at stage 1 (index 5); ±5 active
    # frames therefore cover indices 0..10, while index 11 remains outside
    # the explicit window.
    assert mask.tolist() == [True] * 11 + [False]

    active[10:] = False
    mask = n4.build_transition_window_mask(active, env_id, stage)
    assert mask[10:].tolist() == [False, False]


def test_metric_threshold_classification_and_variant_delta():
    target = np.zeros((8, 12), dtype=np.float64)
    pred = np.zeros_like(target)
    active = np.ones(8, dtype=bool)
    stage = np.zeros(8, dtype=np.int16)
    transition = np.zeros(8, dtype=bool)
    metrics = {
        "full_open_loop": n4._grouped_metric_stats(pred, target, active, stage, transition)
    }
    assert n4.classify_h3(metrics) == "PASS_REFERENCE_FIT"
    pred[:, 0] = 1.0
    metrics["full_open_loop"] = n4._grouped_metric_stats(pred, target, active, stage, transition)
    assert n4.classify_h3(metrics) == "INSUFFICIENT_OPEN_LOOP_FIT"
    stage = np.array([0, 0, 1, 1, 2, 2, 2, 2], dtype=np.int16)
    transition = np.array([False, True, True, True, False, False, False, False])
    delta = n4.summarize_variant_deltas(
        pred,
        target,
        active,
        stage=stage,
        transition_window=transition,
    )
    assert delta["count"] == 8
    assert delta["delta_norm_mean"] > 0.0
    assert delta["all_active"]["count"] == 8
    assert set(delta["by_stage"]) == {"0", "1", "2"}
    assert delta["by_stage"]["1"]["count"] == 2
    assert delta["transition_window_pm5_active"]["count"] == 3
    assert len(delta["transition_window_pm5_active"]["per_action_delta_rmse"]) == 12


def test_actor_per_sample_observability_is_detached_and_not_state_dict(monkeypatch):
    from gr00t.rl.tests.test_a2_cb2h_triview_student import _build_fake_actor, _make_actor_obs

    actor, _ = _build_fake_actor(monkeypatch, d435i_forward_mode="packed")
    before = set(actor.state_dict())
    actor.forward(_make_actor_obs(batch=2))
    snapshot = actor.get_observability_snapshot(per_sample=True)
    assert set(snapshot) == set(n4.OBSERVABILITY_KEYS)
    assert all(tuple(value.shape) == (2,) for value in snapshot.values())
    assert all(value.grad_fn is None for value in snapshot.values())
    assert set(actor.state_dict()) == before
    with pytest.raises(TypeError, match="per_sample"):
        actor.get_observability_snapshot(per_sample="yes")


def test_n4_rejects_wrong_root_and_cpu_gpu_binding(tmp_path: Path):
    wrong_root = tmp_path / "not-the-sealed-n3-root"
    wrong_root.mkdir()
    with pytest.raises(RuntimeError, match="exact sealed N3 root name"):
        n4.validate_n3_inputs(wrong_root)
    with pytest.raises(RuntimeError, match="logical device cuda:0"):
        n4.validate_gpu_binding(device="cpu")


def test_n4_cuda_uuid_normalizer_uses_exact_bytes_not_noncanonical_str():
    expected = n4.EXPECTED_GPU_UUID

    class FakeCudaUuid:
        bytes = list(uuid.UUID(expected.removeprefix("GPU-")).bytes)

        def __str__(self):
            return "<noncanonical CUDA UUID repr>"

    assert n4._canonicalize_a2_cuda_uuid(FakeCudaUuid()) == expected

    for value in (
        object(),
        type("WrongLength", (), {"bytes": b"\\x00" * 15})(),
        type("WrongType", (), {"bytes": "not-bytes"})(),
    ):
        with pytest.raises(RuntimeError, match="A2 CUDA UUID"):
            n4._canonicalize_a2_cuda_uuid(value)


class _FakeH5:
    def __init__(self, data=None):
        self.data = {} if data is None else data

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def __getitem__(self, key):
        return self.data[key]


def _write_three_step_contract_h5(path: Path, *, reactivate_env0: bool):
    import h5py

    rows = 3 * n4.EXPECTED_ENV_COUNT
    env_id = np.tile(np.arange(n4.EXPECTED_ENV_COUNT, dtype=np.int16), 3)
    active = np.ones(rows, dtype=bool)
    if reactivate_env0:
        active[n4.EXPECTED_ENV_COUNT] = False
    done = np.zeros(rows, dtype=bool)
    for env in range(n4.EXPECTED_ENV_COUNT):
        env_rows = np.flatnonzero(env_id == env)
        done[env_rows[np.flatnonzero(active[env_rows])[-1]]] = True
    case_values = np.asarray([f"{env:064x}".encode("ascii") for env in range(16)], dtype="S64")
    with h5py.File(path, "w") as handle:
        handle.create_dataset("actor_obs", data=np.zeros((rows, 81), dtype=np.float32))
        handle.create_dataset("left_rgb", data=np.zeros((rows, 384, 216, 3), dtype=np.uint8))
        handle.create_dataset("right_rgb", data=np.zeros((rows, 384, 216, 3), dtype=np.uint8))
        handle.create_dataset("head_rgb", data=np.zeros((rows, 136, 384, 3), dtype=np.uint8))
        handle.create_dataset("camera_meta", data=np.zeros((rows, 6), dtype=np.float32))
        handle.create_dataset("teacher_action", data=np.zeros((rows, 12), dtype=np.float32))
        handle.create_dataset("pre_action_stage", data=np.zeros(rows, dtype=np.int16))
        handle.create_dataset("done", data=done)
        handle.create_dataset("active_mask", data=active)
        handle.create_dataset("env_id", data=env_id)
        handle.create_dataset("frame_id", data=np.repeat(np.arange(3, dtype=np.int64), 16))
        handle.create_dataset("episode_index", data=np.zeros(rows, dtype=np.int16))
        handle.create_dataset("case_id", data=np.tile(case_values, 3))
        handle.attrs["schema"] = n4.EXPECTED_N3_SCHEMA
        handle.attrs["expected_envs"] = 16
        handle.attrs["episode_count"] = 16
        handle.attrs["active_frame_count"] = int(active.sum())


def test_n4_rejects_three_step_active_mask_reactivation(tmp_path: Path):
    path = tmp_path / "reactivated.h5"
    _write_three_step_contract_h5(path, reactivate_env0=True)
    import h5py

    with h5py.File(path, "r") as handle:
        n4._validate_h5_dataset_contract(handle, 48)
        with pytest.raises(RuntimeError, match="True prefix"):
            n4._validate_step_major_rows(handle, 48)


def test_n4_phase_trajectory_artifact_binding_rejects_tamper_missing_duplicate(tmp_path: Path):
    trajectory_path = tmp_path / "n3_teacher_trajectory_manifest.json"
    trajectory_path.write_bytes(b"sealed trajectory manifest")
    artifact = {
        "path": "n3_teacher_trajectories/replicate_01/n3_teacher_trajectory_manifest.json",
        "sha256": n4.sha256_file(trajectory_path),
        "size_bytes": trajectory_path.stat().st_size,
    }
    n4._require_phase_trajectory_artifact(
        [artifact],
        expected_relative_path=artifact["path"],
        actual_sha256=artifact["sha256"],
        actual_size_bytes=artifact["size_bytes"],
        replicate_id="replicate_01",
    )
    for artifacts in (
        [{**artifact, "sha256": "0" * 64}],
        [{**artifact, "size_bytes": artifact["size_bytes"] + 1}],
        [],
        [artifact, artifact],
    ):
        with pytest.raises(RuntimeError):
            n4._require_phase_trajectory_artifact(
                artifacts,
                expected_relative_path=artifact["path"],
                actual_sha256=artifact["sha256"],
                actual_size_bytes=artifact["size_bytes"],
                replicate_id="replicate_01",
            )


class _FakeModel:
    def __init__(self):
        self.reset_calls = []
        self.init_calls = 0
        self.clear_calls = 0

    def init_rollout(self):
        self.init_calls += 1

    def reset(self, dones):
        self.reset_calls.append(dones.detach().cpu().clone())

    def act_inference(self, obs):
        assert tuple(obs["actor_obs"].shape) == (16, 81)
        return torch.zeros((16, 12), dtype=torch.float32)

    def get_observability_snapshot(self, *, per_sample=False):
        assert per_sample is True
        return {key: torch.zeros(16) for key in n4.OBSERVABILITY_KEYS}

    def clear_rollout(self):
        self.clear_calls += 1


def test_evaluate_variant_resets_from_recorded_done_and_uses_full_batch(monkeypatch):
    raw_left, raw_right, raw_head, raw_meta = _raw_step()
    raw = {
        "actor_obs": torch.zeros((16, 81), dtype=torch.float32),
        "left_rgb": raw_left,
        "right_rgb": raw_right,
        "head_rgb": raw_head,
        "camera_meta": raw_meta,
        "teacher_action": torch.zeros((16, 12), dtype=torch.float32),
        "pre_action_stage": np.zeros(16, dtype=np.int16),
        "done": np.array([True] + [False] * 15),
        "active_mask": np.ones(16, dtype=bool),
        "env_id": np.arange(16, dtype=np.int16),
        "frame_id": np.zeros(16, dtype=np.int64),
        "case_id": np.asarray([b"0" * 64] * 16, dtype="S64"),
    }
    monkeypatch.setattr(n4, "_open_h5", lambda path: _FakeH5())
    monkeypatch.setattr(n4, "_read_step", lambda handle, offset: dict(raw))
    model = _FakeModel()
    replicate = n4.N3Replicate(
        "replicate_01", Path("unused.h5"), Path("unused.json"), "a" * 64, "b" * 64, 16, 16, ("0" * 64,) * 16
    )
    result = n4.evaluate_variant(model, replicate, "FULL", "cpu")
    assert result.actions.shape == (16, 12)
    assert model.init_calls == 1 and model.clear_calls == 1
    assert len(model.reset_calls) == 2
    assert model.reset_calls[1].tolist() == raw["done"].tolist()


class _MemoryBackedFakeModel:
    def __init__(self):
        from gr00t.rl.trl.modules.memory import Memory

        self.memory = Memory(input_size=4, type="lstm", num_layers=1, hidden_size=4)
        self.reset_hidden_states = []

    def init_rollout(self):
        self.memory.reset()

    def reset(self, dones):
        self.memory.reset(dones)
        if self.memory.hidden_states is not None:
            self.reset_hidden_states.append(
                tuple(hidden.detach().clone() for hidden in self.memory.hidden_states)
            )

    def act_inference(self, obs):
        hidden = self.memory(obs["actor_obs"][:, :4])
        assert not hidden.is_inference()
        return torch.zeros((16, 12), dtype=torch.float32)

    def get_observability_snapshot(self, *, per_sample=False):
        assert per_sample is True
        return {key: torch.zeros(16) for key in n4.OBSERVABILITY_KEYS}

    def clear_rollout(self):
        self.memory.detach_hidden_states()


def test_evaluate_variant_memory_reset_is_no_grad_and_done_scoped(monkeypatch):
    raw_left, raw_right, raw_head, raw_meta = _raw_step()
    actor_obs = torch.zeros((16, 81), dtype=torch.float32)
    actor_obs[1, 0] = 1.0
    raw_first = {
        "actor_obs": actor_obs,
        "left_rgb": raw_left,
        "right_rgb": raw_right,
        "head_rgb": raw_head,
        "camera_meta": raw_meta,
        "teacher_action": torch.zeros((16, 12), dtype=torch.float32),
        "pre_action_stage": np.zeros(16, dtype=np.int16),
        "done": np.array([True] + [False] * 15),
        "active_mask": np.ones(16, dtype=bool),
        "env_id": np.arange(16, dtype=np.int16),
        "frame_id": np.zeros(16, dtype=np.int64),
        "case_id": np.asarray([b"0" * 64] * 16, dtype="S64"),
    }
    raw_second = dict(raw_first)
    raw_second["done"] = np.zeros(16, dtype=bool)
    monkeypatch.setattr(n4, "_open_h5", lambda path: _FakeH5())
    monkeypatch.setattr(
        n4,
        "_read_step",
        lambda handle, offset: dict(raw_first if offset == 0 else raw_second),
    )
    model = _MemoryBackedFakeModel()
    replicate = n4.N3Replicate(
        "replicate_01",
        Path("unused.h5"),
        Path("unused.json"),
        "a" * 64,
        "b" * 64,
        32,
        32,
        ("0" * 64,) * 16,
    )
    result = n4.evaluate_variant(model, replicate, "FULL", "cpu")
    assert result.actions.shape == (32, 12)
    assert len(model.reset_hidden_states) == 2
    first_reset = model.reset_hidden_states[0]
    assert all(torch.equal(hidden[..., 0, :], torch.zeros_like(hidden[..., 0, :])) for hidden in first_reset)
    assert any(bool(torch.any(hidden[..., 1, :] != 0.0).item()) for hidden in first_reset)


def test_run_n4_seals_actual_manifest_path_and_source_hashes(monkeypatch, tmp_path: Path):
    raw_left, raw_right, raw_head, raw_meta = _raw_step()
    raw = {
        "actor_obs": torch.zeros((16, 81), dtype=torch.float32),
        "left_rgb": raw_left,
        "right_rgb": raw_right,
        "head_rgb": raw_head,
        "camera_meta": raw_meta,
        "teacher_action": torch.zeros((16, 12), dtype=torch.float32),
        "pre_action_stage": np.zeros(16, dtype=np.int16),
        "done": np.array([True] + [False] * 15),
        "active_mask": np.ones(16, dtype=bool),
        "env_id": np.arange(16, dtype=np.int16),
        "frame_id": np.zeros(16, dtype=np.int64),
        "case_id": np.asarray([b"0" * 64] * 16, dtype="S64"),
    }
    h5_data = {
        key: value.detach().cpu().numpy() if torch.is_tensor(value) else value
        for key, value in raw.items()
    }
    monkeypatch.setattr(n4, "_open_h5", lambda path: _FakeH5(h5_data))
    monkeypatch.setattr(n4, "_read_step", lambda handle, offset: dict(raw))
    replicate = n4.N3Replicate(
        "replicate_01",
        Path("unused.h5"),
        Path("unused.json"),
        "a" * 64,
        "b" * 64,
        16,
        16,
        ("0" * 64,) * 16,
    )
    inputs = n4.N3Inputs(
        tmp_path / "sealed-n3",
        tmp_path / "phase_a_manifest.json",
        "c" * 64,
        (replicate,),
    )
    output_root = tmp_path / "n4-output"
    returned = n4.run_n4_diagnostic(
        _FakeModel(),
        inputs,
        output_root,
        device="cpu",
    )

    manifest_path = output_root / "n4_provenance_manifest.json"
    staging_path = output_root.with_name(f".{output_root.name}.writing")
    assert output_root.is_dir()
    assert not staging_path.exists()
    assert returned["manifest_file_sha256"] == n4.sha256_file(manifest_path)
    on_disk = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert "manifest_file_sha256" not in on_disk
    assert on_disk["source"]["n4_runner"] == {
        "path": str(Path(n4.__file__).resolve()),
        "sha256": n4.sha256_file(Path(n4.__file__).resolve()),
    }
    assert on_disk["source"]["triview_actor"] == {
        "path": str(n4.TRIVIEW_ACTOR_SOURCE),
        "sha256": n4.sha256_file(n4.TRIVIEW_ACTOR_SOURCE),
    }
    content_without_hash = dict(on_disk)
    content_hash = content_without_hash.pop("manifest_content_sha256")
    expected_content_hash = hashlib.sha256(
        n4._canonical_json(content_without_hash).encode("utf-8")
    ).hexdigest()
    assert content_hash == expected_content_hash
