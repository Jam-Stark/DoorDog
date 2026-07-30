"""CPU tests for isolated R1 smoke/formal launch topology and strict chain gates."""

from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]


def _module(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_smoke_launcher_has_seven_disjoint_groups_and_forbids_gpu7(tmp_path):
    module = _module("r1_smoke_launcher_test", "scriptsFORhuman/v20_R1/a2_piper_v20_R1_smoke_launcher.py")
    repo = tmp_path / "repo"
    for spec in module.GROUPS:
        source = ROOT / "gr00t/rl/config/ablation/wbmanip" / spec["config"]
        destination = repo / "gr00t/rl/config/ablation/wbmanip" / spec["config"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    chain = {
        "preflight": repo / "logs_eval/base_v20_R1/preflight/R1_SCIENTIFIC_MANIFEST.json",
        "semantic": repo / "logs_eval/base_v20_R1/semantic/semantic_admission.json",
        "pilot": repo / "logs_eval/base_v20_R1/pilot/pilot_adjudication.json",
    }
    payloads = {
        "preflight": {"plan_id": module.PLAN_ID, "status": "STATIC PASS"},
        "semantic": {"plan_id": module.PLAN_ID, "status": "RUNTIME SEMANTIC PASS"},
        "pilot": {"plan_id": module.PLAN_ID, "status": "POLICY LEARNABILITY PASS", "formal_training_ready": False},
    }
    for name, path in chain.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payloads[name]) + chr(10), encoding="utf-8")
    timestamp = "20260729T000000Z"
    result = module.generate_launcher(
        repo_root=repo,
        launcher_root=repo / "logs_rl/launchers/base_v20_R1" / timestamp,
        artifact_root=repo / "logs_rl/a2_piper_full_stage_a2_base_smoke/base_v20_R1" / timestamp,
        timestamp=timestamp,
        chain_artifacts=chain,
    )
    assert [row["group"] for row in result["groups"]] == [f"G{i}" for i in range(1, 8)]
    assert [row["gpu"] for row in result["groups"]] == list(range(7))
    assert all(row["num_envs"] == 64 and row["num_processes"] == 1 for row in result["groups"])
    assert result["status"] == "RUNTIME PASS"
    with pytest.raises(module.R1Error):
        module.build_training_command(
            repo_root=repo,
            spec={"group": "G1", "gpu": 7, "config": module.GROUPS[0]["config"]},
            artifact_root=repo / "logs_rl/a2_piper_full_stage_a2_base_smoke/base_v20_R1" / timestamp / "G1",
            timestamp=timestamp,
        )


def test_smoke_adjudicator_rejects_policy_pass_label():
    module = _module("r1_smoke_adjudicator_test", "scriptsFORhuman/v20_R1/a2_piper_v20_R1_smoke_adjudicator.py")
    with pytest.raises(module.R1Error):
        module._validate_payload(
            {"plan_id": module.PLAN_ID, "group": "G1", "status": "POLICY PASS", "policy_status": "POLICY PASS"},
            group="G1",
            artifact=Path("smoke_result.json"),
        )


def test_formal_launcher_accepts_only_hydra_frozen_group_configs(tmp_path, monkeypatch):
    module = _module("r1_formal_launcher_test", "scriptsFORhuman/v20_R1/a2_piper_v20_R1_launcher.py")
    repo = tmp_path / "repo"
    formal = repo / "scriptsFORhuman/v20_R1/frozen_formal/ablation" / module.FROZEN_GROUP
    formal.mkdir(parents=True)
    admission_sha = "a" * 64
    config_text = (
        "checkpoint_load_mode: policy_only" + chr(10)
        + "auto_load_latest: false" + chr(10)
        + "headless: true" + chr(10)
        + "env:" + chr(10)
        + "  config:" + chr(10)
        + "    a2_v20_formal_launch: true" + chr(10)
        + "    a2_v20_R1_admission_manifest_sha256: " + admission_sha + chr(10)
    )
    for row in module.GROUPS:
        (formal / row["config"]).write_text(config_text, encoding="utf-8")
    monkeypatch.setattr(
        module,
        "validate_clean_expected_git",
        lambda repo_root, expected_branch: {"commit": "b" * 40, "branch": expected_branch, "dirty": False},
    )
    timestamp = "20260729T000000Z"
    artifact_root = repo / module.R1_FORMAL_ROOT / timestamp / "G1"
    row = module.build_training_command(
        repo_root=repo,
        spec=module.GROUPS[0],
        artifact_root=artifact_root,
        timestamp=timestamp,
        admission_manifest_sha256=admission_sha,
    )
    assert row["num_envs"] == 4096
    assert row["num_processes"] == 1
    assert "+ablation=" + module.FROZEN_GROUP + "/" + module.GROUPS[0]["config"].removesuffix(".yaml") in row["command"]
    assert all("CUDA_VISIBLE_DEVICES" not in key for key in row["env"])
    with pytest.raises(module.R1Error):
        module.build_training_command(
            repo_root=repo,
            spec={**module.GROUPS[0], "gpu": 7},
            artifact_root=artifact_root,
            timestamp=timestamp,
            admission_manifest_sha256=admission_sha,
        )
