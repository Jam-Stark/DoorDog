"""CPU-only tests for the v20 launcher generator contract."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "scriptsFORhuman/v20/a2_piper_v20_launcher.py"


def _load():
    spec = importlib.util.spec_from_file_location("a2_piper_v20_launcher_test", SOURCE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def fixture(tmp_path: Path):
    module = _load()
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    checkpoint = tmp_path / "model_step_002000.pt"
    checkpoint.write_bytes(b"v20 launcher fixture checkpoint")
    checkpoint_sha256 = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    template = """checkpoint: logs_rl/a2_piper_full_stage_a2_base/base_v19/base_v19_G2_norm_control-20260727_012027/model_step_002000.pt
checkpoint_load_mode: policy_only
auto_load_latest: false
seed: {seed}
num_envs: 4096
headless: true
algo:
  trl:
    num_total_batches: 2500
callbacks:
  model_save:
    save_frequency: 250
env:
  config:
    a2_v20_formal_launch: false
    a2_v20_formal_values_frozen: false
    a2_v20_calibration_label: non_formal_calibration_only
"""
    config_paths = {}
    for spec in module.GROUPS:
        path = config_dir / spec.config_filename
        path.write_text(template.format(seed=spec.seed), encoding="utf-8")
        config_paths[spec.group] = path
    accelerate = tmp_path / "accelerate"
    accelerate.write_text("#!/usr/bin/env bash\\nexit 0\\n", encoding="utf-8")
    accelerate.chmod(0o755)
    return {
        "module": module,
        "tmp_path": tmp_path,
        "config_paths": config_paths,
        "config_dir": config_dir,
        "checkpoint": checkpoint,
        "checkpoint_sha256": checkpoint_sha256,
        "accelerate": accelerate,
    }


def _generate(fixture, *, timestamp: str = "20260728_180000", **overrides):
    module = fixture["module"]
    args = {
        "timestamp": timestamp,
        "wandb_mode": "offline",
        "repo_root": ROOT,
        "config_dir": fixture["config_dir"],
        "config_paths": fixture["config_paths"],
        "checkpoint_path": fixture["checkpoint"],
        "expected_checkpoint_sha256": fixture["checkpoint_sha256"],
        "source_path": ROOT / "gr00t/rl/train_agent_trl.py",
        "accelerate_path": fixture["accelerate"],
        "launcher_parent": fixture["tmp_path"] / "launchers",
        "artifact_root": fixture["tmp_path"] / "training",
        "branch": "A2_Piper",
        "source_commit": "a" * 40,
        "require_formal_bundle": False,
    }
    args.update(overrides)
    return module.generate_launcher(**args)


def test_matrix_is_exact_and_g7_seed_is_config_owned(fixture):
    module = fixture["module"]
    assert [(row.group, row.gpu, row.seed, row.config_name, row.experiment_name) for row in module.GROUPS] == [
        ("G1", 0, 0, "base_v20_G1_g2_continuation", "base_v20_G1_g2_continuation"),
        ("G2", 1, 0, "base_v20_G2_economics_only", "base_v20_G2_economics_only"),
        ("G3", 2, 0, "base_v20_G3_send_institution_only", "base_v20_G3_send_institution_only"),
        ("G4", 3, 0, "base_v20_G4_send_economics", "base_v20_G4_send_economics"),
        ("G5", 4, 0, "base_v20_G5_send_arm_tie", "base_v20_G5_send_arm_tie"),
        ("G6", 5, 0, "base_v20_G6_full", "base_v20_G6_full"),
        ("G7", 6, 1, "base_v20_G7_full_seed1", "base_v20_G7_full_seed1"),
    ]
    command = module.build_training_command(
        repo_root=ROOT,
        spec=module.GROUPS[-1],
        accelerate_path=fixture["accelerate"],
        artifact_root=fixture["tmp_path"] / "training",
        timestamp="20260728_180000",
        wandb_mode="offline",
    )
    assert "seed=1" not in command["shell"]
    assert "num_envs" not in command["shell"]
    assert command["num_envs_source"] == "config"


def test_commands_bind_one_physical_gpu_and_unique_ports(fixture):
    module = fixture["module"]
    commands = [
        module.build_training_command(
            repo_root=ROOT,
            spec=spec,
            accelerate_path=fixture["accelerate"],
            artifact_root=fixture["tmp_path"] / "training",
            timestamp="20260728_180000",
            wandb_mode="online",
        )
        for spec in module.GROUPS
    ]
    assert [command["port"] for command in commands] == list(range(29620, 29627))
    assert len({command["port"] for command in commands}) == 7
    for spec, command in zip(module.GROUPS, commands):
        assert f"env CUDA_VISIBLE_DEVICES={spec.gpu} ACCELERATE_TORCH_DEVICE=cuda:0" in command["shell"]
        assert "WANDB_MODE=online" in command["shell"]
        assert "launch --num_processes 1" in command["shell"]
        assert f"--main_process_port {command['port']}" in command["shell"]
        assert "num_envs" not in command["shell"]
        assert command["env"] == {
            "CUDA_VISIBLE_DEVICES": str(spec.gpu),
            "ACCELERATE_TORCH_DEVICE": "cuda:0",
            "WANDB_MODE": "online",
        }


def test_manifest_binds_hashes_outputs_and_runtime_evidence(fixture):
    module = fixture["module"]
    launcher = _generate(fixture)
    manifest = json.loads((launcher / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema"] == module.SCHEMA
    assert manifest["wandb_mode"] == "offline"
    assert manifest["topology"] == {
        "envs_per_group": 4096,
        "one_process_per_group": True,
        "ports": list(range(29620, 29627)),
        "reserved_gpu": 7,
        "training_gpus": list(range(7)),
        "training_groups": 7,
    }
    assert manifest["checkpoint"]["sha256"] == fixture["checkpoint_sha256"]
    assert manifest["checkpoint"]["expected_sha256"] == fixture["checkpoint_sha256"]
    assert manifest["checkpoint_sha256"] == fixture["checkpoint_sha256"]
    assert manifest["branch"] == "A2_Piper"
    assert manifest["source_sha256"] == module.sha256_file(ROOT / "gr00t/rl/train_agent_trl.py")
    assert len(manifest["groups"]) == 7
    for row in manifest["groups"]:
        paths = row["files"]
        assert row["num_envs"] == 4096
        assert row["num_processes"] == 1
        assert Path(paths["command"]).is_file()
        assert Path(paths["wrapper"]).is_file()
        assert Path(paths["stdout_stderr_log"]).is_file()
        assert Path(paths["start_timestamp"]).exists() is False
        assert Path(paths["end_timestamp"]).exists() is False
        assert Path(paths["pid"]).exists() is False
        assert Path(paths["exit_code"]).exists() is False
        assert Path(paths["natural_exit_marker"]).exists() is False
        assert row["command_shell"].count("num_envs") == 0
        assert json.loads(Path(paths["wandb_metadata"]).read_text(encoding="utf-8"))["mode"] == "offline"


def test_tmux_entrypoint_has_one_session_seven_windows_and_guards(fixture):
    launcher = _generate(fixture)
    script = (launcher / "launch_tmux.sh").read_text(encoding="utf-8")
    assert script.count("tmux new-session") == 1
    assert script.count("tmux new-window") == 6
    for group in ("G1", "G2", "G3", "G4", "G5", "G6", "G7"):
        assert f"/{group}/wrapper.sh" in script
    assert "tmux session already exists" in script
    assert "artifact root already exists" in script
    assert "session disappeared before launch was verified" in script
    assert "expected_windows='G1,G2,G3,G4,G5,G6,G7'" in script
    assert "tmux attach" not in script
    subprocess.run(["bash", "-n", str(launcher / "launch_tmux.sh")], check=True)
    for path in sorted(launcher.glob("G*/*.sh")):
        subprocess.run(["bash", "-n", str(path)], check=True)


def test_no_overwrite_and_checkpoint_config_fail_fast(fixture):
    module = fixture["module"]
    launcher = _generate(fixture)
    with pytest.raises(module.LauncherError, match="launcher artifact root already exists"):
        _generate(fixture)
    collision = fixture["tmp_path"] / "collision"
    collision.mkdir()
    with pytest.raises(module.LauncherError, match="training artifact root already exists"):
        _generate(fixture, timestamp="20260728_180001", artifact_root=collision)
    broken = fixture["config_paths"]["G1"]
    broken.write_text(broken.read_text(encoding="utf-8").replace("num_envs: 4096", "num_envs: 2048"), encoding="utf-8")
    with pytest.raises(module.LauncherError, match="num_envs=4096"):
        _generate(fixture, timestamp="20260728_180002", launcher_parent=fixture["tmp_path"] / "other")
    assert launcher.is_dir()


def test_wandb_mode_is_explicit_and_no_silent_fallback(fixture):
    module = fixture["module"]
    with pytest.raises(module.LauncherError, match="WANDB_MODE"):
        module._validate_wandb_mode("auto")
    with pytest.raises(SystemExit):
        module._parser().parse_args(["--timestamp", "20260728_180000"])
