from __future__ import annotations

import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap
from types import SimpleNamespace

import pytest
from omegaconf import OmegaConf

from gr00t.rl.scripts import run_a2_student_eval_v19 as eval_v19


def _diagnostic(env_id: int, offset: float = 0.0) -> dict:
    return {
        "env_id": env_id,
        "stage_buf": 5 if env_id == 3 else 2,
        "terminal_reasons": "complete" if env_id == 3 else "timeout",
        "door_hinge_drive_max_force": 10.0 + offset,
        "door_handle_drive_max_force": 20.0 + offset,
        "door_handle_height": 0.31 + offset,
        "door_weight": 100.0 + offset,
    }


def _metrics() -> dict:
    diagnostics = [_diagnostic(env_id) for env_id in range(16)]
    return {
        "episode_lengths": [100 + env_id for env_id in range(16)],
        "episode_rewards": [float(env_id) for env_id in range(16)],
        "episode_goal_reached": [env_id == 3 for env_id in range(16)],
        "episode_max_stage_reached": [5 if env_id == 3 else 2 for env_id in range(16)],
        "episode_terminal_reasons": [diag["terminal_reasons"] for diag in diagnostics],
        "episode_terminal_diagnostics": diagnostics,
    }


def test_checkpoint_artifact_identity_and_cpu_safe_import():
    info = eval_v19.validate_checkpoint_artifacts()
    assert info["sha256"] == eval_v19.CHECKPOINT_SHA256
    assert info["config_sha256"] == eval_v19.CHECKPOINT_CONFIG_SHA256


def test_experience_source_is_controller_specific_overlay_and_single_gpu():
    student = eval_v19.resolve_experience_source(eval_v19.REPO_ROOT, "student")
    teacher = eval_v19.resolve_experience_source(eval_v19.REPO_ROOT, "teacher")
    expected_settings = {
        "renderer.multiGpu.enabled": "false",
        "renderer.multiGpu.autoEnable": "false",
        "renderer.multiGpu.maxGpuCount": "1",
    }
    assert student["camera_mode"] == "cameras"
    assert student["relative_path"] == str(
        eval_v19.EXPERIENCE_RELATIVE_PATHS["student"]
    )
    assert student["path"].endswith(
        "gr00t/rl/apps/phc.isaaclab.python.headless.rendering.kit"
    )
    assert teacher["camera_mode"] == "no_cameras"
    assert teacher["relative_path"] == str(
        eval_v19.EXPERIENCE_RELATIVE_PATHS["teacher"]
    )
    assert teacher["path"].endswith("gr00t/rl/apps/isaaclab.python.headless.kit")
    assert student["settings"] == expected_settings
    assert teacher["settings"] == expected_settings
    assert "/workspace/IsaacLab/apps/" not in student["path"]
    assert "/workspace/IsaacLab/apps/" not in teacher["path"]


def test_experience_source_missing_or_wrong_settings_fails_fast(tmp_path: Path):
    overlay = tmp_path / "overlay"
    apps = overlay / "gr00t/rl/apps"
    apps.mkdir(parents=True)
    source = apps / "phc.isaaclab.python.headless.rendering.kit"
    with pytest.raises(FileNotFoundError):
        eval_v19.resolve_experience_source(overlay, "student")
    source.write_text(
        "renderer.multiGpu.enabled=false\n"
        "renderer.multiGpu.autoEnable=true\n"
        "renderer.multiGpu.maxGpuCount=1\n",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="invalid single-GPU setting"):
        eval_v19.resolve_experience_source(overlay, "student")
    source.write_text(
        "renderer.multiGpu.enabled=false\n"
        "renderer.multiGpu.autoEnable=false\n",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="exactly one single-GPU setting"):
        eval_v19.resolve_experience_source(overlay, "student")


def test_runtime_bootstrap_uses_absolute_worktree_source_before_gr00t_import(tmp_path: Path):
    external_root = tmp_path / "external_editable"
    external_scripts = external_root / "gr00t/rl/scripts"
    external_scripts.mkdir(parents=True)
    for package_dir in (
        external_root / "gr00t",
        external_root / "gr00t/rl",
        external_scripts,
    ):
        (package_dir / "__init__.py").write_text("\n", encoding="utf-8")
    (external_scripts / "run_a2_student_distillation_v19.py").write_text(
        "raise AssertionError('external editable runtime helper was imported')\n",
        encoding="utf-8",
    )
    runner_path = Path(eval_v19.__file__).resolve()
    expected_runtime_path = eval_v19.RUNTIME_BOOTSTRAP_PATH
    probe = tmp_path / "probe_runtime_bootstrap.py"
    probe.write_text(
        textwrap.dedent(
            f"""
            import importlib.util
            from pathlib import Path
            import sys

            sys.path.insert(0, {str(external_root)!r})
            assert 'gr00t' not in sys.modules
            runner_spec = importlib.util.spec_from_file_location(
                '_a2_student_eval_probe', {str(runner_path)!r}
            )
            assert runner_spec is not None and runner_spec.loader is not None
            runner = importlib.util.module_from_spec(runner_spec)
            runner_spec.loader.exec_module(runner)
            assert 'gr00t' not in sys.modules
            runtime = runner.load_runtime_bootstrap_module()
            assert 'gr00t' not in sys.modules
            assert Path(runtime.__file__).resolve() == Path({str(expected_runtime_path)!r}).resolve()
            assert runtime.EXPECTED_RUNTIME_COMMIT == {eval_v19.EXPECTED_RUNTIME_COMMIT!r}
            print('RUNTIME_BOOTSTRAP_SOURCE', runtime.__file__)
            print('RUNTIME_BOOTSTRAP_GR00T_PRELOADED', 'gr00t' in sys.modules)
            """
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(probe)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"RUNTIME_BOOTSTRAP_SOURCE {expected_runtime_path}" in result.stdout
    assert "RUNTIME_BOOTSTRAP_GR00T_PRELOADED False" in result.stdout


def test_runtime_bootstrap_cleans_private_entry_after_identity_failure(tmp_path: Path):
    runner_path = Path(eval_v19.__file__).resolve()
    probe = tmp_path / "probe_runtime_bootstrap_cleanup.py"
    probe.write_text(
        textwrap.dedent(
            f"""
            import importlib.util
            from pathlib import Path
            import sys

            runner_spec = importlib.util.spec_from_file_location(
                '_a2_student_eval_cleanup_probe', {str(runner_path)!r}
            )
            assert runner_spec is not None and runner_spec.loader is not None
            runner = importlib.util.module_from_spec(runner_spec)
            runner_spec.loader.exec_module(runner)
            assert 'gr00t' not in sys.modules
            original_commit = runner.EXPECTED_RUNTIME_COMMIT
            runner.EXPECTED_RUNTIME_COMMIT = 'injected-post-load-mismatch'
            try:
                runner.load_runtime_bootstrap_module()
            except RuntimeError as exc:
                assert 'commit identity mismatch' in str(exc)
            else:
                raise AssertionError('injected post-load identity failure was not raised')
            assert runner.RUNTIME_BOOTSTRAP_MODULE_NAME not in sys.modules
            runner.EXPECTED_RUNTIME_COMMIT = original_commit
            runtime = runner.load_runtime_bootstrap_module()
            assert sys.modules[runner.RUNTIME_BOOTSTRAP_MODULE_NAME] is runtime
            assert Path(runtime.__file__).resolve() == runner.RUNTIME_BOOTSTRAP_PATH
            print('RUNTIME_BOOTSTRAP_CLEANUP PASS')
            """
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(probe)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "RUNTIME_BOOTSTRAP_CLEANUP PASS" in result.stdout


def test_hydra_overrides_are_pure_student_and_exact_dimensions(tmp_path: Path):
    formal = eval_v19.build_hydra_overrides("formal", tmp_path / "formal")
    render = eval_v19.build_hydra_overrides("render", tmp_path / "render")
    for mode, overrides in (("formal", formal), ("render", render)):
        output_root = (tmp_path / mode).resolve()
        bundle_root = eval_v19.render_staging_root(output_root) if mode == "render" else output_root
        assert f"checkpoint={eval_v19.CHECKPOINT}" in overrides
        assert "+seed=0" in overrides
        assert "+num_envs=16" in overrides
        assert "+headless=true" in overrides
        assert "+use_wandb=false" in overrides
        assert "+algo.config.enforce_teacher_rollout=false" in overrides
        assert "+algo.config.ratio_teacher_rollout=0.0" in overrides
        assert "+algo.config.use_a2_base=true" in overrides
        assert "+algo.config.actor.view_contract.d435i_forward_mode=sequential" in overrides
        assert "+algo.config.eval.eval_num_envs_episodes=true" in overrides
        assert "algo.config.eval.num_eval_episodes=16" in overrides
        assert f"+simulator.config.render_results={'true' if mode == 'render' else 'false'}" in overrides
        assert f"eval_output_dir={bundle_root}" in overrides
        assert f"eval_log_dir={eval_v19.eval_runtime_log_root(mode, output_root)}" in overrides
    assert "env.config.save_rendering_dir=" not in formal
    assert any(item.startswith("env.config.save_rendering_dir=") for item in render)
    render_output = next(item for item in render if item.startswith("eval_output_dir="))
    assert Path(render_output.split("=", 1)[1]) == eval_v19.render_staging_root(tmp_path / "render")


def test_n3_hydra_overrides_are_passive_student_with_teacher_rollout(tmp_path: Path):
    output_root = (tmp_path / "n3").resolve()
    overrides = eval_v19.build_hydra_overrides("n3", output_root, controller="student")
    assert f"checkpoint={eval_v19.CHECKPOINT}" in overrides
    assert "+algo.config.enforce_teacher_rollout=true" in overrides
    assert "+algo.config.ratio_teacher_rollout=1.0" in overrides
    assert "+algo.config.use_a2_base=true" in overrides
    assert "+algo.config.actor.view_contract.d435i_forward_mode=sequential" in overrides
    assert "+simulator.config.render_results=false" in overrides
    assert f"eval_output_dir={output_root}" in overrides
    assert f"eval_log_dir={eval_v19.eval_runtime_log_root('n3', output_root)}" in overrides
    assert not any(item.startswith("env.config.save_rendering_dir=") for item in overrides)
    with pytest.raises(ValueError, match="passive Student"):
        eval_v19.build_hydra_overrides("n3", output_root, controller="teacher")


def test_packed_student_mode_is_explicit_formal_only_and_sealed_in_contract(tmp_path: Path):
    overrides = eval_v19.build_hydra_overrides(
        "formal",
        tmp_path / "packed",
        controller="student",
        student_d435i_forward_mode="packed",
    )
    assert "+algo.config.actor.view_contract.d435i_forward_mode=packed" in overrides
    with pytest.raises(ValueError, match="formal Student eval"):
        eval_v19.build_hydra_overrides(
            "n3",
            tmp_path / "n3",
            controller="student",
            student_d435i_forward_mode="packed",
        )
    with pytest.raises(ValueError, match="Student controller"):
        eval_v19.build_hydra_overrides(
            "formal",
            tmp_path / "teacher",
            controller="teacher",
            student_d435i_forward_mode="packed",
        )
    contract = eval_v19._formal_contract(
        "student",
        {"path": "checkpoint", "sha256": "a" * 64},
        {"runtime_commit": eval_v19.EXPECTED_RUNTIME_COMMIT},
        {"controller": "student", "camera_mode": "cameras", "path": "experience", "sha256": "b" * 64},
        case_seed=0,
        replicate_id="replicate01",
        student_d435i_forward_mode="packed",
    )
    assert contract["student_d435i_forward_mode"] == "packed"


def _formal_runtime_config(mode: str) -> dict:
    return {
        "enforce_teacher_rollout": False,
        "ratio_teacher_rollout": 0.0,
        "use_a2_base": True,
        "eval": {"eval_num_envs_episodes": True, "num_eval_episodes": 16},
        "actor": {"view_contract": {"d435i_forward_mode": mode}},
    }


@pytest.mark.parametrize("mode", ["sequential", "packed"])
def test_formal_student_mode_matches_effective_config_and_policy_before_base_eval(
    tmp_path: Path, mode: str
):
    experience = eval_v19.resolve_experience_source(eval_v19.REPO_ROOT, "student")
    base_calls: list[bool] = []

    def base_eval(_trainer):
        base_calls.append(True)
        return _metrics()

    formal = eval_v19._make_formal_eval(
        base_eval,
        tmp_path / mode,
        {},
        controller="student",
        teacher_info={},
        case_seed=0,
        replicate_id="replicate01",
        experience_info=experience,
        student_d435i_forward_mode=mode,
    )
    trainer = SimpleNamespace(
        config=_formal_runtime_config(mode),
        policy_model=SimpleNamespace(d435i_forward_mode=mode),
        env=SimpleNamespace(num_envs=16),
    )
    formal(trainer)
    assert base_calls == [True]


@pytest.mark.parametrize(
    ("config_mode", "policy_mode"),
    [("packed", "sequential"), ("sequential", "packed")],
)
def test_formal_student_mode_mismatch_rejects_before_base_eval(
    tmp_path: Path, config_mode: str, policy_mode: str
):
    base_calls: list[bool] = []

    def base_eval(_trainer):
        base_calls.append(True)
        return _metrics()

    formal = eval_v19._make_formal_eval(
        base_eval,
        tmp_path / f"{config_mode}_{policy_mode}",
        {},
        controller="student",
        teacher_info={},
        case_seed=0,
        replicate_id="replicate01",
        experience_info=eval_v19.resolve_experience_source(eval_v19.REPO_ROOT, "student"),
        student_d435i_forward_mode="packed",
    )
    trainer = SimpleNamespace(
        config=_formal_runtime_config(config_mode),
        policy_model=SimpleNamespace(d435i_forward_mode=policy_mode),
        env=SimpleNamespace(num_envs=16),
    )
    with pytest.raises(RuntimeError, match="D435 mode mismatch"):
        formal(trainer)
    assert base_calls == []


def test_n3_hydra_runtime_root_is_sibling_and_preflight_owned(tmp_path: Path):
    output_root = (tmp_path / "n3").resolve()
    runtime_root = eval_v19.eval_runtime_log_root("n3", output_root)
    assert runtime_root == tmp_path / ".n3.runtime"
    assert runtime_root != output_root
    assert runtime_root != eval_v19.n3_staging_root(output_root)
    overrides = eval_v19.build_hydra_overrides("n3", output_root)
    assert f"eval_log_dir={runtime_root}" in overrides
    runtime_root.mkdir()
    with pytest.raises(FileExistsError, match="runtime-log root"):
        eval_v19.validate_output_root_preflight("n3", output_root)
    assert not output_root.exists()


def test_n3_parser_requires_exact_teacher_identity_flags(monkeypatch, tmp_path: Path):
    argv = [
        "eval",
        "--mode",
        "n3",
        "--output-root",
        str(tmp_path / "n3"),
        "--controller",
        "student",
        "--checkpoint",
        str(eval_v19.CHECKPOINT),
        "--checkpoint-sha256",
        eval_v19.CHECKPOINT_SHA256,
        "--checkpoint-config",
        str(eval_v19.CHECKPOINT_CONFIG),
        "--checkpoint-config-sha256",
        eval_v19.CHECKPOINT_CONFIG_SHA256,
        "--expected-global-step",
        "10000",
    ]
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit):
        eval_v19.parse_args()
    argv.extend(
        [
            "--n3-control-controller",
            "teacher",
            "--n3-teacher-checkpoint",
            str(eval_v19.TEACHER_CHECKPOINT),
            "--n3-teacher-sha256",
            eval_v19.TEACHER_CHECKPOINT_SHA256,
            "--n3-teacher-config",
            str(eval_v19.TEACHER_CONFIG),
            "--n3-teacher-config-sha256",
            eval_v19.TEACHER_CONFIG_SHA256,
            "--n3-teacher-manifest",
            str(eval_v19.TEACHER_MANIFEST),
            "--n3-teacher-manifest-sha256",
            eval_v19.TEACHER_MANIFEST_SHA256,
        ]
    )
    args = eval_v19.parse_args()
    assert args.mode == "n3"
    assert args.n3_control_controller == "teacher"


def test_n3_hdf5_stream_is_lossless_and_tamper_checked(tmp_path: Path, monkeypatch):
    np = pytest.importorskip("numpy")
    pytest.importorskip("h5py")
    path = tmp_path / "teacher_trajectory.h5"
    writer = eval_v19.N3TrajectoryWriter(path, expected_envs=2)
    batch = {
        "actor_obs": np.zeros((2, 81), dtype="float32"),
        "left_rgb": np.zeros((2, 384, 216, 3), dtype="uint8"),
        "right_rgb": np.zeros((2, 384, 216, 3), dtype="uint8"),
        "head_rgb": np.zeros((2, 136, 384, 3), dtype="uint8"),
        "camera_meta": np.zeros((2, 6), dtype="float32"),
        "teacher_action": np.zeros((2, 12), dtype="float32"),
        "pre_action_stage": np.zeros((2,), dtype="int16"),
        "done": np.ones((2,), dtype="bool"),
        "active_mask": np.ones((2,), dtype="bool"),
        "env_id": np.arange(2, dtype="int16"),
        "frame_id": np.zeros((2,), dtype="int64"),
        "episode_index": np.zeros((2,), dtype="int16"),
        "case_id": np.asarray([b"", b""], dtype="S64"),
    }
    monkeypatch.setattr(eval_v19, "N3_VALIDATION_ROW_CHUNK", 2)
    batch["done"] = np.zeros((2,), dtype="bool")
    writer.append(batch)
    for frame_id in (1, 2):
        batch["frame_id"] = np.full((2,), frame_id, dtype="int64")
        batch["done"] = np.full((2,), frame_id == 2, dtype="bool")
        writer.append(batch)
    summary = writer.finalize(
        {
            0: {"env_id": 0, "case_id": "a" * 64},
            1: {"env_id": 1, "case_id": "b" * 64},
        }
    )
    assert summary["episode_count"] == 2
    assert summary["row_count"] == 6
    assert summary["dataset_dtypes"]["teacher_action"] == "float32"
    import h5py

    with h5py.File(path, "r") as stream:
        assert stream["teacher_action"].compression == "gzip"
        assert stream.attrs["lossless_compression"] == "gzip"
    real_file = h5py.File
    image_slices = []

    class TrackingDataset:
        def __init__(self, dataset):
            self._dataset = dataset
            self.shape = dataset.shape
            self.dtype = dataset.dtype
            self.compression = dataset.compression

        def __getitem__(self, item):
            image_slices.append(item)
            if isinstance(item, slice):
                if item.start is None or item.stop is None:
                    raise AssertionError("validation attempted an unbounded HDF5 slice")
                if item.stop - item.start > eval_v19.N3_VALIDATION_ROW_CHUNK:
                    raise AssertionError("validation exceeded its bounded row chunk")
            return self._dataset[item]

    class TrackingFile:
        def __init__(self, *args, **kwargs):
            self._file = real_file(*args, **kwargs)
            self.attrs = self._file.attrs

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return self._file.__exit__(*args)

        def keys(self):
            return self._file.keys()

        def __getitem__(self, name):
            return TrackingDataset(self._file[name])

    monkeypatch.setattr(h5py, "File", TrackingFile)
    eval_v19.validate_n3_hdf5(
        path,
        {
            0: {"env_id": 0, "case_id": "a" * 64},
            1: {"env_id": 1, "case_id": "b" * 64},
        },
        expected_envs=2,
    )
    assert len(image_slices) >= 3
    assert all(isinstance(item, slice) for item in image_slices)
    monkeypatch.setattr(h5py, "File", real_file)
    with h5py.File(path, "r+") as stream:
        stream["case_id"][0] = b"tampered"
    with pytest.raises(RuntimeError, match="case_id mismatch"):
        eval_v19.validate_n3_hdf5(
            path,
            {
                0: {"env_id": 0, "case_id": "a" * 64},
                1: {"env_id": 1, "case_id": "b" * 64},
            },
            expected_envs=2,
        )


def test_n3_completed_bundle_load_and_tamper_detection(tmp_path: Path):
    np = pytest.importorskip("numpy")
    pytest.importorskip("h5py")
    metrics = _metrics()
    staging_root = tmp_path / ".n3.writing"
    output_root = tmp_path / "n3"
    staging_root.mkdir()
    writer = eval_v19.N3TrajectoryWriter(staging_root / eval_v19.N3_DATASET_FILENAME)
    writer.append(
        {
            "actor_obs": np.zeros((16, 81), dtype="float32"),
            "left_rgb": np.zeros((16, 384, 216, 3), dtype="uint8"),
            "right_rgb": np.zeros((16, 384, 216, 3), dtype="uint8"),
            "head_rgb": np.zeros((16, 136, 384, 3), dtype="uint8"),
            "camera_meta": np.zeros((16, 6), dtype="float32"),
            "teacher_action": np.zeros((16, 12), dtype="float32"),
            "pre_action_stage": np.zeros((16,), dtype="int16"),
            "done": np.ones((16,), dtype="bool"),
            "active_mask": np.ones((16,), dtype="bool"),
            "env_id": np.arange(16, dtype="int16"),
            "frame_id": np.zeros((16,), dtype="int64"),
            "episode_index": np.zeros((16,), dtype="int16"),
            "case_id": np.asarray([b""] * 16, dtype="S64"),
        }
    )
    case_table = eval_v19.n3_case_table_from_metrics(metrics)
    writer.finalize(case_table)
    passive = {
        "path": str(eval_v19.CHECKPOINT),
        "sha256": eval_v19.CHECKPOINT_SHA256,
        "config_path": str(eval_v19.CHECKPOINT_CONFIG),
        "config_sha256": eval_v19.CHECKPOINT_CONFIG_SHA256,
        "global_step": 10000,
        "controller": "student",
    }
    teacher = {
        "checkpoint": {
            "path": str(eval_v19.TEACHER_CHECKPOINT),
            "sha256": eval_v19.TEACHER_CHECKPOINT_SHA256,
            "config_path": str(eval_v19.TEACHER_CONFIG),
            "config_sha256": eval_v19.TEACHER_CONFIG_SHA256,
            "global_step": 2000,
            "controller": "teacher",
        },
        "manifest": {
            "path": str(eval_v19.TEACHER_MANIFEST),
            "sha256": eval_v19.TEACHER_MANIFEST_SHA256,
        },
        "runtime_commit": eval_v19.EXPECTED_RUNTIME_COMMIT,
    }
    experience = eval_v19.resolve_experience_source(eval_v19.REPO_ROOT, "student")
    manifest = eval_v19.seal_n3_capture_bundle(
        staging_root=staging_root,
        output_root=output_root,
        metrics=metrics,
        passive_student_info=passive,
        teacher_info=teacher,
        experience_info=experience,
        replicate_id="n3_rep01",
    )
    os.replace(staging_root, output_root)
    loaded_manifest, loaded_metrics = eval_v19.load_n3_capture_bundle(output_root)
    assert loaded_manifest["schema"] == eval_v19.N3_MANIFEST_SCHEMA
    assert loaded_metrics["schema"] == eval_v19.N3_METRICS_SCHEMA
    assert loaded_manifest["dataset"]["episode_count"] == 16
    (output_root / eval_v19.N3_SELECTION_FILENAME).write_text("tampered\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="artifact hash/size"):
        eval_v19.load_n3_capture_bundle(output_root)


def test_n3_capture_ignores_inactive_auto_reset_done_and_resets_teacher(
    tmp_path: Path, monkeypatch
):
    torch = pytest.importorskip("torch")
    np = pytest.importorskip("numpy")

    class FakeWriter:
        instances = []

        def __init__(self, path):
            self.path = Path(path)
            self.frames = [0] * 16
            self.batches = []
            self.closed = False
            FakeWriter.instances.append(self)

        @property
        def next_frame_ids(self):
            return tuple(self.frames)

        def append(self, batch):
            self.batches.append({key: np.array(value, copy=True) for key, value in batch.items()})
            active = np.asarray(batch["active_mask"])
            for env_id in range(16):
                if bool(active[env_id]):
                    self.frames[env_id] += 1

        def finalize(self, case_table):
            return {"episode_count": 16}

        def close(self):
            self.closed = True

    class FakeRef:
        num_actions = 12

        def __init__(self):
            self.reset_calls = []
            self.clear_calls = 0

        def eval(self):
            return self

        def init_rollout(self):
            return None

        def act_inference(self, obs_dict):
            return torch.zeros((16, 12), dtype=torch.float32)

        def reset(self, dones):
            self.reset_calls.append(dones.detach().cpu().clone())

        def clear_rollout(self):
            self.clear_calls += 1

    class FakeEnv:
        num_envs = 16
        _use_a2_base = True

        def __init__(self):
            camera_config = SimpleNamespace(image_mean=(0.0, 0.0, 0.0), image_std=(1.0, 1.0, 1.0))
            self.config = SimpleNamespace(
                simulator=SimpleNamespace(
                    config=SimpleNamespace(cameras=camera_config, render_results=False)
                )
            )
            self.stage_buf = torch.zeros((16,), dtype=torch.int16)
            self.step_index = 0
            self.step_calls = 0
            self.is_evaluating = False
            self.lifecycle_calls = []
            self.process_ids = []
            self.reset_ids = []

        def _obs(self):
            return {
                "vision_obs": torch.zeros((16, 384, 216, 6), dtype=torch.float32),
                "context_vision_obs": torch.zeros((16, 136, 384, 3), dtype=torch.float32),
                "actor_obs": torch.zeros((16, 81), dtype=torch.float32),
                "camera_meta": torch.zeros((16, 6), dtype=torch.float32),
            }

        def reset_all(self):
            return self._obs()

        def step(self, actor_state):
            assert self.lifecycle_calls[:4] == [
                "set_is_evaluating",
                "metrics",
                "trace",
                "oracle",
            ]
            self.step_calls += 1
            self.step_index += 1
            dones = torch.zeros((16,), dtype=torch.bool)
            if self.step_index == 1:
                dones[0] = True
            elif self.step_index == 2:
                dones[0] = True
            elif self.step_index == 3:
                dones[1:] = True
            return self._obs(), torch.zeros((16,), dtype=torch.float32), dones, {}

        def set_is_evaluating(self):
            self.lifecycle_calls.append("set_is_evaluating")
            self.is_evaluating = True

        def init_eval_metrics_tracking(self, device):
            self.lifecycle_calls.append("metrics")

        def init_a2_eval_stage2_step_trace(self, *, diagnostic_enabled, diagnostic_reward_terms):
            assert diagnostic_enabled is False
            assert diagnostic_reward_terms == ()
            self.lifecycle_calls.append("trace")

        def init_a2_eval_hold_oracle(self, eval_config, *, diagnostic_enabled):
            assert diagnostic_enabled is False
            self.lifecycle_calls.append("oracle")
            return {"enabled": False}

        def _get_a2_hold_contact_detail_enabled(self):
            self.lifecycle_calls.append("hold_detail")
            return False

        def get_a2_high_level_action_layout(self):
            self.lifecycle_calls.append("layout")
            return {
                "dim": 12,
                "base_start": 0,
                "base_end": 5,
                "arm_start": 5,
                "arm_end": 11,
                "gripper_index": 11,
            }

        def update_eval_metrics_per_step(self, infos):
            return None

        def process_eval_episode_completions(self, ids, rewards, lengths):
            self.process_ids.append(ids.detach().cpu().tolist())

        def reset_eval_episode_tracking(self, ids):
            self.reset_ids.append(ids.detach().cpu().tolist())

        def get_eval_metrics_summary(self):
            return _metrics()

    class FakeUnwrapped:
        def _a2_base_actions(self, obs_dict, high_level_actions):
            return torch.zeros((16, 12), dtype=torch.float32)

    fake_ref = FakeRef()
    fake_env = FakeEnv()
    teacher_action_calls = []
    composed_action_calls = []
    student_rollout_calls = []

    def teacher_actions(obs_dict):
        teacher_action_calls.append(obs_dict)
        return torch.zeros((16, 12), dtype=torch.float32)

    def compose_actions(high_level_actions, a2_actions):
        composed_action_calls.append((high_level_actions.clone(), a2_actions.clone()))
        return torch.cat((high_level_actions, a2_actions), dim=-1)

    trainer = SimpleNamespace(
        config={
            "enforce_teacher_rollout": True,
            "ratio_teacher_rollout": 1.0,
            "use_a2_base": True,
            "eval": {
                "eval_num_envs_episodes": True,
                "num_eval_episodes": 16,
                "save_videos": False,
                "a2_eval_p2_posture_axis": "none",
                "a2_eval_m41_strict_telemetry": False,
                "dump_to_log_metrics": False,
            },
        },
        env=fake_env,
        ref_model=fake_ref,
        unwrapped_model=FakeUnwrapped(),
        policy_model=SimpleNamespace(
            eval_mode=lambda: None,
            rollout=lambda *args, **kwargs: student_rollout_calls.append((args, kwargs)),
        ),
        accelerator=SimpleNamespace(device=torch.device("cpu")),
        _eval_mode=lambda: None,
        _teacher_actions=teacher_actions,
    )
    monkeypatch.setattr(eval_v19, "N3TrajectoryWriter", FakeWriter)
    monkeypatch.setattr(eval_v19, "validate_n3_capture_contract", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        eval_v19,
        "_N3_RUNTIME_A2_DIAGNOSTIC_CONFIG_READER",
        lambda eval_config: {
            "diagnostic_enabled": False,
            "forced_close_enabled": False,
            "reward_terms": (),
        },
    )
    monkeypatch.setattr(eval_v19, "_N3_RUNTIME_A2_ROLLOUT_ACTION_COMPOSER", compose_actions)
    monkeypatch.setattr(
        eval_v19,
        "derive_raw_policy_frames_from_observations",
        lambda *args, **kwargs: (
            torch.zeros((16, 384, 216, 3), dtype=torch.uint8),
            torch.zeros((16, 384, 216, 3), dtype=torch.uint8),
            torch.zeros((16, 136, 384, 3), dtype=torch.uint8),
        ),
    )
    monkeypatch.setattr(eval_v19, "validate_policy_camera_contract", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        eval_v19,
        "n3_case_table_from_metrics",
        lambda metrics: {
            env_id: {"env_id": env_id, "case_id": f"{env_id:064d}", "randomized_case": {}}
            for env_id in range(16)
        },
    )
    monkeypatch.setattr(
        eval_v19,
        "seal_n3_capture_bundle",
        lambda **kwargs: {"dataset": {"episode_count": 16}},
    )
    output_root = tmp_path / "n3_capture"
    capture = eval_v19._make_n3_capture_eval(
        output_root,
        {},
        {},
        {},
        overlay_repository=eval_v19.REPO_ROOT,
        case_seed=0,
        replicate_id="n3_rep01",
    )
    capture(trainer)
    writer = FakeWriter.instances[0]
    assert len(writer.batches) == 3
    assert bool(writer.batches[0]["done"][0]) is True
    assert bool(writer.batches[1]["active_mask"][0]) is False
    assert bool(writer.batches[1]["done"][0]) is False
    assert bool(fake_ref.reset_calls[1][0]) is True
    assert fake_env.process_ids == [[0], list(range(1, 16))]
    assert fake_env.reset_ids[1] == [0]
    assert fake_env.lifecycle_calls[:4] == [
        "set_is_evaluating",
        "metrics",
        "trace",
        "oracle",
    ]
    assert fake_env.lifecycle_calls.count("metrics") == 1
    assert fake_env.lifecycle_calls.count("trace") == 1
    assert fake_env.lifecycle_calls.count("oracle") == 1
    assert len(teacher_action_calls) == 3
    assert len(composed_action_calls) == 3
    assert student_rollout_calls == []
    assert fake_env.step_calls == 3
    assert output_root.is_dir()


@pytest.mark.parametrize(
    ("drift", "expected_message"),
    [
        ("diagnostic", "diagnostic trace disabled"),
        ("forced_close", "(diagnostic trace disabled|forced-close intervention disabled)"),
        ("p2_posture", "p2_posture_axis='none'"),
        ("strict_telemetry", "strict A2 M41 telemetry disabled"),
        ("dump_to_log", "dump_to_log_metrics disabled"),
        ("hold_oracle", "hold oracle disabled"),
        ("hold_detail", "detailed A2 hold diagnostics disabled"),
        ("render_results", "render_results=false"),
    ],
)
def test_n3_capture_rejects_a2_eval_lifecycle_drift_before_step(
    tmp_path: Path, monkeypatch, drift: str, expected_message: str
):
    torch = pytest.importorskip("torch")

    class FakeWriter:
        instance = None

        def __init__(self, path):
            self.path = Path(path)
            self.closed = False
            FakeWriter.instance = self

        @property
        def next_frame_ids(self):
            return (0,) * 16

        def close(self):
            self.closed = True

    class FakeRef:
        num_actions = 12

        def __init__(self):
            self.clear_called = False

        def eval(self):
            return self

        def init_rollout(self):
            return None

        def act_inference(self, obs_dict):
            raise AssertionError("N3 must use Trainer._teacher_actions")

        def clear_rollout(self):
            self.clear_called = True

        def reset(self, dones):
            return None

    class FakeEnv:
        num_envs = 16
        _use_a2_base = True

        def __init__(self):
            self.is_evaluating = False
            self.step_calls = 0
            self.lifecycle_calls = []
            self.config = SimpleNamespace(
                simulator=SimpleNamespace(
                    config=SimpleNamespace(
                        cameras=SimpleNamespace(
                            image_mean=(0.0, 0.0, 0.0), image_std=(1.0, 1.0, 1.0)
                        ),
                        render_results=drift == "render_results",
                    )
                )
            )

        def set_is_evaluating(self):
            self.is_evaluating = True
            self.lifecycle_calls.append("set_is_evaluating")

        def reset_all(self):
            return {}

        def init_eval_metrics_tracking(self, device):
            self.lifecycle_calls.append("metrics")

        def init_a2_eval_stage2_step_trace(self, *, diagnostic_enabled, diagnostic_reward_terms):
            self.lifecycle_calls.append("trace")

        def init_a2_eval_hold_oracle(self, eval_config, *, diagnostic_enabled):
            self.lifecycle_calls.append("oracle")
            return {"enabled": drift == "hold_oracle"}

        def _get_a2_hold_contact_detail_enabled(self):
            self.lifecycle_calls.append("hold_detail")
            return drift == "hold_detail"

        def get_a2_high_level_action_layout(self):
            self.lifecycle_calls.append("layout")
            return {
                "dim": 12,
                "base_start": 0,
                "base_end": 5,
                "arm_start": 5,
                "arm_end": 11,
                "gripper_index": 11,
            }

        def step(self, actor_state):
            self.step_calls += 1
            raise AssertionError("N3 A2 config drift must fail before env.step")

    eval_config = {
        "eval_num_envs_episodes": True,
        "num_eval_episodes": 16,
        "save_videos": False,
        "a2_diagnostic_trace_enabled": drift == "diagnostic" or drift == "forced_close",
        "a2_forced_gripper_close_enabled": drift == "forced_close",
        "a2_diagnostic_reward_terms": ["stage"],
        "a2_eval_p2_posture_axis": "pitch_zero" if drift == "p2_posture" else "none",
        "a2_eval_m41_strict_telemetry": drift == "strict_telemetry",
        "dump_to_log_metrics": drift == "dump_to_log",
    }
    fake_env = FakeEnv()
    fake_ref = FakeRef()
    trainer = SimpleNamespace(
        config={
            "enforce_teacher_rollout": True,
            "ratio_teacher_rollout": 1.0,
            "use_a2_base": True,
            "eval": eval_config,
        },
        env=fake_env,
        ref_model=fake_ref,
        unwrapped_model=SimpleNamespace(
            _a2_base_actions=lambda *args: torch.zeros((16, 12), dtype=torch.float32)
        ),
        policy_model=SimpleNamespace(eval_mode=lambda: None),
        accelerator=SimpleNamespace(device=torch.device("cpu")),
        _eval_mode=lambda: None,
        _teacher_actions=lambda obs_dict: torch.zeros((16, 12), dtype=torch.float32),
    )

    def diagnostic_reader(config):
        return {
            "diagnostic_enabled": config["a2_diagnostic_trace_enabled"],
            "forced_close_enabled": config["a2_forced_gripper_close_enabled"],
            "reward_terms": tuple(config["a2_diagnostic_reward_terms"]),
        }

    monkeypatch.setattr(eval_v19, "N3TrajectoryWriter", FakeWriter)
    monkeypatch.setattr(eval_v19, "validate_n3_capture_contract", lambda *args, **kwargs: None)
    monkeypatch.setattr(eval_v19, "_N3_RUNTIME_A2_DIAGNOSTIC_CONFIG_READER", diagnostic_reader)
    monkeypatch.setattr(
        eval_v19,
        "_N3_RUNTIME_A2_ROLLOUT_ACTION_COMPOSER",
        lambda high_level, a2_base: torch.cat((high_level, a2_base), dim=-1),
    )
    capture = eval_v19._make_n3_capture_eval(
        tmp_path / f"n3_{drift}",
        {},
        {},
        {},
        overlay_repository=eval_v19.REPO_ROOT,
        case_seed=0,
        replicate_id="n3_rep01",
    )
    with pytest.raises(RuntimeError, match=expected_message):
        capture(trainer)
    assert fake_env.step_calls == 0
    assert fake_ref.clear_called is True
    assert FakeWriter.instance is not None and FakeWriter.instance.closed is True
    assert not (tmp_path / f"n3_{drift}").exists()
    assert not (tmp_path / f".n3_{drift}.writing").exists()


def test_n3_hdf5_constructor_closes_handle_when_dataset_creation_fails(tmp_path: Path, monkeypatch):
    h5py = pytest.importorskip("h5py")

    class FailingFile:
        def __init__(self):
            self.attrs = {}
            self.closed = False

        def create_dataset(self, *args, **kwargs):
            raise RuntimeError("injected dataset creation failure")

        def close(self):
            self.closed = True

    handle = FailingFile()
    monkeypatch.setattr(h5py, "File", lambda *args, **kwargs: handle)
    with pytest.raises(RuntimeError, match="dataset creation failure"):
        eval_v19.N3TrajectoryWriter(tmp_path / "trajectory.h5", expected_envs=2)
    assert handle.closed is True


def test_n3_hdf5_close_surfaces_flush_failure_and_marks_closed():
    class FailingFile:
        def __init__(self):
            self.closed = False

        def flush(self):
            raise RuntimeError("injected flush failure")

        def close(self):
            self.closed = True

    writer = object.__new__(eval_v19.N3TrajectoryWriter)
    writer._closed = False
    writer._file = FailingFile()
    with pytest.raises(RuntimeError, match="flush failure"):
        writer.close()
    assert writer._closed is True
    assert writer._file.closed is True


def test_n3_capture_cleanup_attempts_clear_close_and_staging_removal_on_body_failure(
    tmp_path: Path, monkeypatch
):
    torch = pytest.importorskip("torch")

    class FailingWriter:
        def __init__(self, path):
            self.path = Path(path)
            self.closed = False

        def close(self):
            self.closed = True
            raise RuntimeError("injected writer close failure")

    class FailingRef:
        num_actions = 12

        def __init__(self):
            self.clear_called = False

        def eval(self):
            return self

        def init_rollout(self):
            return None

        def act_inference(self, obs_dict):
            return torch.zeros((16, 12), dtype=torch.float32)

        def clear_rollout(self):
            self.clear_called = True
            raise RuntimeError("injected Teacher clear failure")

    class FailingEnv:
        num_envs = 16

        def set_is_evaluating(self):
            return None

        def reset_all(self):
            raise RuntimeError("injected capture body failure")

    ref = FailingRef()
    writer = None

    def writer_factory(path):
        nonlocal writer
        writer = FailingWriter(path)
        return writer

    trainer = SimpleNamespace(
        config={},
        env=FailingEnv(),
        ref_model=ref,
        unwrapped_model=SimpleNamespace(_a2_base_actions=lambda *args: torch.zeros((16, 12))),
        policy_model=SimpleNamespace(eval_mode=lambda: None),
        accelerator=SimpleNamespace(device=torch.device("cpu")),
        _eval_mode=lambda: None,
    )
    monkeypatch.setattr(eval_v19, "N3TrajectoryWriter", writer_factory)
    monkeypatch.setattr(eval_v19, "validate_n3_capture_contract", lambda *args, **kwargs: None)
    capture = eval_v19._make_n3_capture_eval(
        tmp_path / "n3_cleanup",
        {},
        {},
        {},
        overlay_repository=eval_v19.REPO_ROOT,
        case_seed=0,
        replicate_id="n3_rep01",
    )
    with pytest.raises(RuntimeError, match="capture body failure"):
        capture(trainer)
    assert ref.clear_called is True
    assert writer is not None and writer.closed is True
    assert not (tmp_path / "n3_cleanup").exists()
    assert not (tmp_path / ".n3_cleanup.writing").exists()


def test_historical_saved_config_receives_explicit_sequential_forward_override():
    saved = OmegaConf.load(eval_v19.CHECKPOINT_CONFIG)
    override = next(
        item
        for item in eval_v19.build_hydra_overrides("formal", Path("/tmp/cb2h_eval_probe"))
        if item.startswith("+algo.config.actor.view_contract.d435i_forward_mode=")
    )
    key, value = override[1:].split("=", 1)
    effective = OmegaConf.create(saved)
    OmegaConf.update(effective, key, value, merge=True)
    assert effective.algo.config.actor.view_contract.d435i_forward_mode == "sequential"


def _compose_base_eval(overrides: list[str]):
    from hydra import compose, initialize_config_dir

    config_dir = (eval_v19.REPO_ROOT / "gr00t/rl/config").resolve()
    with initialize_config_dir(version_base=None, config_dir=str(config_dir)):
        config = compose(config_name="base_eval", overrides=overrides, return_hydra_config=True)
        return {
            "checkpoint": str(config.checkpoint),
            "seed": int(config.seed),
            "num_envs": int(config.num_envs),
            "headless": bool(config.headless),
            "use_wandb": bool(config.use_wandb),
            "enforce_teacher_rollout": bool(config.algo.config.enforce_teacher_rollout),
            "ratio_teacher_rollout": float(config.algo.config.ratio_teacher_rollout),
            "use_a2_base": bool(config.algo.config.use_a2_base),
            "d435i_forward_mode": str(
                config.algo.config.actor.view_contract.d435i_forward_mode
            ),
            "eval_num_envs_episodes": bool(config.algo.config.eval.eval_num_envs_episodes),
            "num_eval_episodes": int(config.algo.config.eval.num_eval_episodes),
            "render_results": bool(config.simulator.config.render_results),
            "eval_output_dir": str(config.eval_output_dir),
            "eval_log_dir": str(config.eval_log_dir),
            "hydra_run_dir": str(config.hydra.run.dir),
            "save_rendering_dir": str(config.env.config.save_rendering_dir),
        }


def test_real_base_eval_hydra_composition_has_exact_formal_and_render_paths(tmp_path: Path):
    for mode in ("formal", "render"):
        output_root = (tmp_path / mode).resolve()
        overrides = eval_v19.build_hydra_overrides(mode, output_root)
        config = _compose_base_eval(overrides)
        bundle_root = eval_v19.render_staging_root(output_root) if mode == "render" else output_root
        runtime_log_root = eval_v19.eval_runtime_log_root(mode, output_root)

        assert config["checkpoint"] == str(eval_v19.CHECKPOINT)
        assert config["seed"] == 0
        assert config["num_envs"] == 16
        assert config["headless"] is True
        assert config["use_wandb"] is False
        assert config["enforce_teacher_rollout"] is False
        assert config["ratio_teacher_rollout"] == 0.0
        assert config["use_a2_base"] is True
        assert config["d435i_forward_mode"] == "sequential"
        assert config["eval_num_envs_episodes"] is True
        assert config["num_eval_episodes"] == 16
        assert config["render_results"] is (mode == "render")
        assert Path(config["eval_output_dir"]) == bundle_root
        assert Path(config["eval_log_dir"]) == runtime_log_root
        assert Path(config["hydra_run_dir"]) == runtime_log_root
        if mode == "render":
            assert Path(config["save_rendering_dir"]) == bundle_root / "external_debug_videos"
            assert Path(config["hydra_run_dir"]) not in {bundle_root, output_root}
        else:
            assert Path(config["save_rendering_dir"]) == output_root / "renderings"


def test_imageio_temp_suffix_selects_ffmpeg_and_bundle_paths_are_distinct(tmp_path: Path):
    import imageio.v2 as imageio
    from imageio.core import Request

    final = tmp_path / "policy.mp4"
    temporary = eval_v19.temporary_policy_video_path(final)
    assert temporary.name == ".policy.writing.mp4"
    assert temporary.suffix == ".mp4"
    request = Request(str(temporary), "w")
    try:
        fmt = imageio.formats.search_write_format(request)
        assert fmt is not None and fmt.name == "FFMPEG"
    finally:
        request.finish()
    assert eval_v19.render_staging_root(tmp_path / "bundle") == tmp_path / ".bundle.writing"


def test_render_bundle_publish_is_atomic_and_non_overwriting(tmp_path: Path):
    final = tmp_path / "render_bundle"
    staging = eval_v19.render_staging_root(final)
    staging.mkdir()
    (staging / "selected_render_metadata.json").write_text("{}\n", encoding="utf-8")
    eval_v19.publish_render_bundle(staging, final)
    assert final.is_dir()
    assert not staging.exists()

    other_staging = eval_v19.render_staging_root(tmp_path / "other_bundle")
    other_staging.mkdir()
    with pytest.raises(FileExistsError, match="overwrite"):
        eval_v19.publish_render_bundle(other_staging, final)
    assert other_staging.is_dir()


def test_render_preflight_rejects_even_empty_final_or_staging_target(tmp_path: Path):
    final = tmp_path / "render_bundle"
    final.mkdir()
    with pytest.raises(FileExistsError, match="existing final/staging"):
        eval_v19.validate_output_root_preflight("render", final)
    final.rmdir()
    staging = eval_v19.render_staging_root(final)
    staging.mkdir()
    with pytest.raises(FileExistsError, match="existing final/staging"):
        eval_v19.validate_output_root_preflight("render", final)


def test_render_preflight_rejects_existing_runtime_log_root(tmp_path: Path):
    output_root = tmp_path / "render_bundle"
    runtime_root = eval_v19.eval_runtime_log_root("render", output_root)
    runtime_root.mkdir()
    with pytest.raises(FileExistsError, match="runtime-log root"):
        eval_v19.validate_output_root_preflight("render", output_root)


def test_final_artifact_validation_requires_formal_or_render_output(tmp_path: Path):
    for mode, filename in (
        ("formal", "student_selection.json"),
        ("render", "selected_render_metadata.json"),
        ("n3", eval_v19.N3_MANIFEST_FILENAME),
    ):
        output_root = tmp_path / mode
        with pytest.raises(RuntimeError, match="required final artifact"):
            eval_v19.validate_final_artifact(mode, output_root)
        artifact = output_root / filename
        artifact.parent.mkdir(parents=True)
        artifact.write_text("{}\n", encoding="utf-8")
        assert eval_v19.validate_final_artifact(mode, output_root) == artifact.resolve()


def test_successful_inner_hard_exit_without_final_artifact_is_rejected(
    tmp_path: Path, monkeypatch
):
    def fake_run_path(path, run_name):
        assert Path(path).resolve() == eval_v19.EVAL_ENTRY
        assert run_name == "__main__"
        os._exit(0)

    monkeypatch.setattr(eval_v19.runpy, "run_path", fake_run_path)
    for mode in ("formal", "n3"):
        with pytest.raises(RuntimeError, match="required final artifact"):
            eval_v19.run_eval_entry_with_artifact_guard(mode, tmp_path / mode)


def test_render_cleans_owned_staging_after_injected_post_mkdir_failure(tmp_path: Path, monkeypatch):
    output_root = tmp_path / "render_bundle"
    staging_root = eval_v19.render_staging_root(output_root)
    selection_path = tmp_path / "student_selection.json"
    selection_path.write_text("{}\n", encoding="utf-8")
    selection = {"selected": {"env_id": 0}}
    env_config = SimpleNamespace(
        simulator=SimpleNamespace(config={"render_results": True}),
        save_rendering_dir=str(staging_root / "external_debug_videos"),
    )
    trainer = SimpleNamespace(
        config={
            "enforce_teacher_rollout": False,
            "ratio_teacher_rollout": 0.0,
            "use_a2_base": True,
            "eval": {"eval_num_envs_episodes": True, "num_eval_episodes": 16},
        },
        env=SimpleNamespace(num_envs=16, config=env_config),
    )
    original_mkdir = Path.mkdir

    def injected_mkdir(path, *args, **kwargs):
        if path == staging_root / "policy_camera_videos":
            raise OSError("injected policy directory failure")
        return original_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", injected_mkdir)
    render_eval = eval_v19._make_render_eval(
        lambda _self: pytest.fail("base eval must not run after setup failure"),
        output_root,
        selection,
        selection_path,
    )
    with pytest.raises(OSError, match="injected policy directory failure"):
        render_eval(trainer)
    assert not staging_root.exists()
    assert not output_root.exists()


def test_formal_ranking_uses_goal_stage_reward_then_env_id():
    records = [
        {
            "env_id": 4,
            "goal_reached": False,
            "max_stage": 5,
            "reward": 99.0,
            "terminal_reason": "timeout",
            "randomized_case": {},
        },
        {
            "env_id": 2,
            "goal_reached": True,
            "max_stage": 5,
            "reward": 1.0,
            "terminal_reason": "complete",
            "randomized_case": {},
        },
        {
            "env_id": 1,
            "goal_reached": True,
            "max_stage": 5,
            "reward": 1.0,
            "terminal_reason": "complete",
            "randomized_case": {},
        },
        *[
            {
                "env_id": env_id,
                "goal_reached": False,
                "max_stage": 0,
                "reward": -float(env_id),
                "terminal_reason": "timeout",
                "randomized_case": {},
            }
            for env_id in range(16)
            if env_id not in {1, 2, 4}
        ],
    ]
    ranked = eval_v19.rank_episode_records(records)
    assert [item["env_id"] for item in ranked[:3]] == [1, 2, 4]
    assert [item["rank"] for item in ranked] == list(range(16))


def test_seal_and_load_selection_round_trip_and_replay_semantics(tmp_path: Path):
    checkpoint_info = eval_v19.validate_checkpoint_artifacts()
    selection = eval_v19.seal_formal_selection(_metrics(), tmp_path / "formal", checkpoint_info)
    selection_path = tmp_path / "formal" / "student_selection.json"
    loaded, source = eval_v19.load_sealed_selection(selection_path)
    assert loaded == selection
    assert source["schema"] == eval_v19.METRICS_SCHEMA
    expected_experience = eval_v19.resolve_experience_source(eval_v19.REPO_ROOT, "student")
    assert loaded["experience"] == expected_experience
    assert source["experience"] == expected_experience
    assert loaded["contract"]["experience_identity"] == expected_experience

    replay_metrics = _metrics()
    replay = eval_v19.validate_replay_selected_case(loaded, replay_metrics)
    assert replay["env_id"] == loaded["selected"]["env_id"]
    assert replay["source_formal_outcome"] == {
        "goal_reached": loaded["selected"]["goal_reached"],
        "max_stage": loaded["selected"]["max_stage"],
        "terminal_reason": loaded["selected"]["terminal_reason"],
        "reward": loaded["selected"]["reward"],
    }
    assert all(not field["changed"] for field in replay["outcome_drift"].values())

    # Replay outcomes are measurements rather than case identity.  A
    # nondeterministic trajectory may drift semantically and in reward while
    # preserving the selected env/episode/randomized-case identity.
    semantic_drift = _metrics()
    semantic_drift["episode_goal_reached"][loaded["selected"]["env_id"]] = False
    semantic_drift["episode_max_stage_reached"][loaded["selected"]["env_id"]] = 1
    semantic_drift["episode_terminal_reasons"][loaded["selected"]["env_id"]] = "stage_overtime"
    semantic_drift["episode_rewards"][loaded["selected"]["env_id"]] = -214.9512
    drifted = eval_v19.validate_replay_selected_case(loaded, semantic_drift)
    assert drifted["source_formal_outcome"] == replay["source_formal_outcome"]
    assert drifted["replay_outcome"] == {
        "goal_reached": False,
        "max_stage": 1,
        "terminal_reason": "stage_overtime",
        "reward": -214.9512,
    }
    assert all(field["changed"] for field in drifted["outcome_drift"].values())

    # Completion-list order is intentionally permuted; every authoritative
    # first-episode index remains zero and selected consistency still holds.
    permuted = _metrics()
    order = list(reversed(range(16)))
    for key in (
        "episode_lengths",
        "episode_rewards",
        "episode_goal_reached",
        "episode_max_stage_reached",
        "episode_terminal_reasons",
        "episode_terminal_diagnostics",
    ):
        permuted[key] = [permuted[key][idx] for idx in order]
    records = eval_v19.episode_records(permuted)
    assert {record["episode_index"] for record in records} == {0}
    # The runtime diagnostic has no episode_index field; even an unrelated
    # extra field cannot override the first-episode protocol invariant.
    permuted["episode_terminal_diagnostics"][0]["episode_index"] = 99
    assert {record["episode_index"] for record in eval_v19.episode_records(permuted)} == {0}

    changed = _metrics()
    selected_env = int(loaded["selected"]["env_id"])
    changed["episode_terminal_diagnostics"][selected_env]["door_weight"] += 1.0
    with pytest.raises(RuntimeError, match="randomized-case"):
        eval_v19.validate_replay_selected_case(loaded, changed)


def test_sealed_ranking_records_are_bound_to_hash_validated_source(tmp_path: Path):
    checkpoint_info = eval_v19.validate_checkpoint_artifacts()
    selection = eval_v19.seal_formal_selection(
        _metrics(), tmp_path / "formal", checkpoint_info
    )
    selection_path = tmp_path / "formal" / "student_selection.json"
    mutations = {
        "outcome": lambda record: record.update(goal_reached=not record["goal_reached"]),
        "reward": lambda record: record.update(reward=record["reward"] + 1.0),
        "identity": lambda record: record.update(env_id=99),
    }
    for name, mutate in mutations.items():
        tampered = json.loads(json.dumps(selection))
        mutate(tampered["ranking"]["records"][0])
        selection_path.write_text(json.dumps(tampered) + "\n", encoding="utf-8")
        with pytest.raises(RuntimeError, match="provenance-consistent"):
            eval_v19.load_sealed_selection(selection_path)


def test_terminal_diagnostics_require_strict_integer_env_id():
    invalid_values = ("3", True, 16, -1)
    for invalid in invalid_values:
        metrics = _metrics()
        metrics["episode_terminal_diagnostics"][0]["env_id"] = invalid
        with pytest.raises((KeyError, TypeError, RuntimeError), match="env_id"):
            eval_v19.episode_records(metrics)
    metrics = _metrics()
    del metrics["episode_terminal_diagnostics"][0]["env_id"]
    with pytest.raises(KeyError, match="env_id"):
        eval_v19.episode_records(metrics)


def test_randomized_case_requires_the_four_c18_fields():
    with pytest.raises(KeyError, match="door_weight"):
        eval_v19.extract_randomized_case({"env_id": 0})
    nested = {
        "randomized_case": {
            "door_hinge_drive_max_force": 1,
            "door_handle_drive_max_force": 2,
            "door_handle_height": 3,
            "door_weight": 4,
            "unsealed_extra": "ignored",
        }
    }
    assert eval_v19.extract_randomized_case(nested) == {
        "door_hinge_drive_max_force": 1,
        "door_handle_drive_max_force": 2,
        "door_handle_height": 3,
        "door_weight": 4,
    }


def test_external_debug_video_contract(tmp_path: Path):
    paths = []
    for name in (
        "run_env0003_episode0000.mp4",
        "run_env0003_episode0000_handle_top.mp4",
        "run_env0003_episode0000_handle_side.mp4",
    ):
        path = tmp_path / name
        path.write_bytes(b"video")
        paths.append(path)
    eval_v19.validate_external_debug_videos(paths, 3)
    (tmp_path / "run_env0004_episode0000_handle_side.mp4").write_bytes(b"video")
    with pytest.raises(RuntimeError, match="exactly three"):
        eval_v19.validate_external_debug_videos(sorted(tmp_path.glob("*.mp4")), 3)


def test_raw_policy_frames_are_recovered_from_policy_observations():
    import torch

    from gr00t.rl.utils.a2_policy_camera import (
        compose_channel_stacked_dual_rgb,
        normalize_head_context_rgb,
    )

    left = (torch.arange(16 * 384 * 216 * 3, dtype=torch.int64).reshape(16, 384, 216, 3) % 255).to(torch.uint8)
    right = (torch.arange(16 * 384 * 216 * 3, dtype=torch.int64).reshape(16, 384, 216, 3).add(17) % 255).to(torch.uint8)
    head = (torch.arange(16 * 136 * 384 * 3, dtype=torch.int64).reshape(16, 136, 384, 3).add(29) % 255).to(torch.uint8)
    mean = [0.485, 0.456, 0.406]
    std = [0.229, 0.224, 0.225]
    vision_obs = compose_channel_stacked_dual_rgb(left, right, resolution=(384, 216), image_mean=mean, image_std=std)
    context_obs = normalize_head_context_rgb(head, resolution=(136, 384), image_mean=mean, image_std=std)
    recovered = eval_v19.derive_raw_policy_frames_from_observations(
        vision_obs,
        context_obs,
        image_mean=mean,
        image_std=std,
    )
    assert torch.equal(recovered[0], left)
    assert torch.equal(recovered[1], right)
    assert torch.equal(recovered[2], head)


def test_selected_capture_has_no_public_sensor_output_dependency():
    source = inspect.getsource(eval_v19._make_render_eval)
    assert ".data.output" not in source


def test_selection_metadata_provenance_uses_selection_json_path(tmp_path: Path):
    selection_path = tmp_path / "student_selection.json"
    selection_path.write_text('{"sealed": true}\n', encoding="utf-8")
    source = inspect.getsource(eval_v19._make_render_eval)
    assert "selection_sha256 = sha256_file(selection_path)" in source
    assert '"path": str(selection_path)' in source
    assert '"sha256": selection_sha256' in source


def test_render_metadata_seals_outcome_provenance_and_trial_ranking():
    source = inspect.getsource(eval_v19._make_render_eval)
    for field in (
        '"schema": "a2_student_v19_render_v2"',
        '"trial_id": output_root.name',
        '"source_formal_outcome"',
        '"replay_outcome"',
        '"outcome_drift"',
        'RENDER_TRIAL_RANKING_ORDER',
    ):
        assert field in source


def test_bootstrap_does_not_embed_a_selected_env_id_before_ranking():
    source = Path(eval_v19.__file__).read_text(encoding="utf-8")
    assert "selected_env = int(selection[\"selected\"][\"env_id\"])" in source
    assert "VIDEO_ENV_ID = 13" not in source
