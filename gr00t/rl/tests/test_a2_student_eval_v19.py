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
        assert "+algo.config.eval.eval_num_envs_episodes=true" in overrides
        assert "algo.config.eval.num_eval_episodes=16" in overrides
        assert f"+simulator.config.render_results={'true' if mode == 'render' else 'false'}" in overrides
        assert f"eval_output_dir={bundle_root}" in overrides
        assert f"eval_log_dir={eval_v19.eval_runtime_log_root(mode, output_root)}" in overrides
    assert "env.config.save_rendering_dir=" not in formal
    assert any(item.startswith("env.config.save_rendering_dir=") for item in render)
    render_output = next(item for item in render if item.startswith("eval_output_dir="))
    assert Path(render_output.split("=", 1)[1]) == eval_v19.render_staging_root(tmp_path / "render")


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
    with pytest.raises(RuntimeError, match="required final artifact"):
        eval_v19.run_eval_entry_with_artifact_guard("formal", tmp_path)


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
