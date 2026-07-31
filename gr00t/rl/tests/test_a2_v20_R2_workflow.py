"""Single CPU/static binding gate for the Phase-IV R2 workflow."""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest
from hydra.core.override_parser.overrides_parser import OverridesParser

from scriptsFORhuman.v20_R2 import _r2_common as common
from scriptsFORhuman.v20_R2 import _r2_workflow as workflow
from scriptsFORhuman.v20_R2._r2_workflow import (
    CONFIG_FILENAMES,
    GROUPS,
    M22_STEPS,
    _eval_run_uuid,
    _hydra_mapping,
    r2_config_path,
    runtime_command,
)
from scriptsFORhuman.v20_R2.a2_piper_v20_R2_forced_runner import build_forced_command
from scriptsFORhuman.v20_R2.a2_piper_v20_R2_smoke_launcher import build_smoke_commands
from gr00t.rl.envs.door.a2_v20_r2_forced_semantics import FORCED_CASES


ROOT = Path(__file__).resolve().parents[3]
R2_ROOT = ROOT / "scriptsFORhuman/v20_R2"
CONFIG_ROOT = ROOT / "gr00t/rl/config/ablation/wbmanip"
SCHEMA_ROOT = R2_ROOT / "schemas"


SCRIPT_NAMES = tuple(sorted(path.stem for path in R2_ROOT.glob("a2_piper_v20_R2_*.py")))


def test_workflow_imports_and_cli_entrypoints_are_complete() -> None:
    assert len(SCRIPT_NAMES) >= 26
    for stem in SCRIPT_NAMES:
        module = importlib.import_module(f"scriptsFORhuman.v20_R2.{stem}")
        assert callable(getattr(module, "main", None)), stem
    required = {"a2_piper_v20_R2_source_freeze", "a2_piper_v20_R2_p0_runner", "a2_piper_v20_R2_p0_adjudicator", "a2_piper_v20_R2_formal_launcher", "a2_piper_v20_R2_m22_manifest", "a2_piper_v20_R2_m22_adjudicator", "a2_piper_v20_R2_pooled_adjudicator", "a2_piper_v20_R2_holdout_adjudicator", "a2_piper_v20_R2_render_qa", "a2_piper_v20_R2_final_analysis"}
    assert required <= set(SCRIPT_NAMES)


def test_workflow_device_config_and_group_ownership_contracts() -> None:
    with pytest.raises(common.R2Error):
        runtime_command(module="gr00t.rl.eval_agent_trl", repo_root=ROOT, gpu=7)
    argv, env = build_forced_command(repo_root=ROOT, physical_gpu=3)
    assert env == {"ACCELERATE_TORCH_DEVICE": "cuda:3"}
    assert "cuda:7" not in " ".join(argv)
    configs = {group: r2_config_path(CONFIG_ROOT, group) for group in GROUPS}
    rows = build_smoke_commands(repo_root=ROOT, configs=configs, physical_gpus=tuple(range(7)))
    assert [(row["group"], row["physical_gpu"]) for row in rows] == list(zip(GROUPS, range(7)))
    assert len({row["config_sha256"] for row in rows}) == 7
    for group in GROUPS:
        text = configs[group].read_text(encoding="utf-8")
        assert "scientific_plan_id: base_v20_R1_policy_behavior_v1" in text
        assert "admission_plan_id: base_v20_R2_admission_execution_v1" in text
        assert "a2_v20_R2_evidence_enabled: true" in text
    assert set(CONFIG_FILENAMES) == set(GROUPS)


def test_schema_store_registers_file_resolved_ids() -> None:
    episode_schema = json.loads(
        (SCHEMA_ROOT / "episode_record_v1.schema.json").read_text(encoding="utf-8")
    )
    resolved_id = (SCHEMA_ROOT / episode_schema["$id"]).as_uri()
    assert workflow._schema_store()[resolved_id] == episode_schema


def test_canonical_json_accepts_only_finite_floats() -> None:
    assert common.canonical_json_bytes({"scale": 0.85}) == b'{"scale":0.85}'
    with pytest.raises(common.R2Error, match="NaN or Infinity"):
        common.canonical_json_bytes({"scale": float("nan")})


def test_workflow_nested_hydra_provenance_round_trips() -> None:
    provenance = {
        "run_uuid": "m22-G1-seed16",
        "physical_path": "/tmp/a:path/checkpoint.pt",
        "topology": {
            "name": "canonical16",
            "environment_count": 16,
            "expected_episode_count": 16,
            "first_episode_only": True,
            "single_process": True,
            "physical_gpu": 0,
            "render": False,
        },
    }
    encoded = _hydra_mapping(provenance)
    parsed = OverridesParser.create().parse_override(
        f"+provenance={encoded}"
    ).value()
    assert parsed == provenance


def test_m22_run_uuid_is_group_bound() -> None:
    assert _eval_run_uuid(mode="m22", group="G1", seed=0) == "m22-G1-seed0"
    with pytest.raises(common.R2Error, match="group-bound"):
        _eval_run_uuid(mode="m22", group=None, seed=0)


def test_eval_command_binds_offline_first_episode_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    checkpoint = tmp_path / "model_step_002500.pt"
    checkpoint.write_bytes(b"checkpoint")
    config = tmp_path / "base_v20_R2_G1_g2_continuation.yaml"
    config.write_text(
        "scientific_plan_id: base_v20_R1_policy_behavior_v1\n"
        "admission_plan_id: base_v20_R2_admission_execution_v1\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        workflow,
        "_source_lock_provenance",
        lambda *_: {
            "source_lock_sha256": "a" * 64,
            "plan_sha256": "b" * 64,
            "r1_plan_sha256": "c" * 64,
            "b0_json_sha256": "d" * 64,
            "b0_csv_sha256": "e" * 64,
            "urdf_path": workflow.R1_URDF_PATH,
            "urdf_sha256": "f" * 64,
            "git_commit": "1" * 40,
        },
    )

    argv, env, _ = workflow.eval_command(
        repo_root=tmp_path, checkpoint=checkpoint, config=config, gpu=0, seed=0,
        num_envs=16, output_root=tmp_path / "eval", mode="m22", group="G1",
    )

    assert "+algo.config.eval.eval_num_envs_episodes=true" in argv
    assert env == {
        "ACCELERATE_TORCH_DEVICE": "cuda:0",
        "WANDB_MODE": "offline",
    }
    assert argv[-1] == (
        f"+r2_command_sha256={workflow.hash_command_env(argv[:-1], env)}"
    )


def test_workflow_dag_schema_and_postformal_counts_are_explicit() -> None:
    forced_schema = json.loads((SCHEMA_ROOT / "forced_trace_v1.schema.json").read_text(encoding="utf-8"))
    manifest_schema = json.loads((SCHEMA_ROOT / "m22_manifest_v1.schema.json").read_text(encoding="utf-8"))
    training_schema = json.loads((SCHEMA_ROOT / "training_attempt_v1.schema.json").read_text(encoding="utf-8"))
    assert "oneOf" in forced_schema and "case" in forced_schema["properties"]
    assert manifest_schema["properties"]["rows"]["minItems"] == 70 == manifest_schema["properties"]["rows"]["maxItems"]
    assert "group" in manifest_schema["properties"]["rows"]["items"]["required"]
    assert "LAUNCH_PLAN_COMPLETE" in training_schema["properties"]["producer_state"]["enum"]
    assert len(GROUPS) == 7 and len(M22_STEPS) == 10 and len(GROUPS) * len(M22_STEPS) == 70
    assert len(FORCED_CASES) == 17 and len(set(FORCED_CASES)) == 17
    allowed_legacy_identity = {
        "a2_piper_v20_R2_p0_adjudicator.py": ("base_v20_R1_policy_behavior_v1",),
    }
    legacy_context = {"__init__.py", "_r2_common.py", "_r2_workflow.py",
                      "a2_piper_v20_R2_record_adjudicator.py", "a2_piper_v20_R2_source_freeze.py"}
    for path in R2_ROOT.glob("*.py"):
        original = path.read_text(encoding="utf-8")
        text = original
        for literal in allowed_legacy_identity.get(path.name, ()):
            text = text.replace(literal, "")
        assert "v20_R1" not in text or path.name in legacy_context
        for marker in ("from scriptsFORhuman.v20_R1", "import scriptsFORhuman.v20_R1",
                       "python -m scriptsFORhuman.v20_R1", "python3 -m scriptsFORhuman.v20_R1"):
            assert marker not in original


def test_forced_semantics_remains_high_level_and_cpu_only() -> None:
    source = (ROOT / "gr00t/rl/envs/door/a2_v20_r2_forced_semantics.py").read_text(encoding="utf-8")
    assert "pxr.Usd" not in source
    assert "UsdGeom" not in source
    assert "stage.DefinePrim" not in source
