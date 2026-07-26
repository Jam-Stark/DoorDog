"""Adversarial CPU tests for the v19 M22 queue and adjudicator."""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path
from typing import Mapping

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[3]
QUEUE_SOURCE = ROOT / "scriptsFORhuman/v19/a2_piper_v19_m22_queue.py"
ADJ_SOURCE = ROOT / "scriptsFORhuman/v19/a2_piper_v19_m22_adjudicator.py"
P0_TERMS = (
    "gripper_handle_orientation",
    "grasp_target_distance",
    "grasp",
    "penalty_not_standing_still",
    "a2_stage3_unlatch_hold",
    "a2_stage3_stage4_hold_and_drive",
    "push_door_hinge",
    "dont_push_door_handle",
    "target_root_distance",
    "penalty_standing_still",
    "stage",
    "penalty_door_frame_contact",
    "penalty_door_panel_contact",
    "penalty_a2_door_body_contact",
    "penalty_undesired_contact",
    "penalty_base_roll_pitch_l2",
    "a2_corridor_door_wide",
    "a2_corridor_clean_passage",
    "penalty_a2_posture_command_l1",
    "complete",
)


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _artifact(
    tmp_path: Path,
    checkpoint: Mapping[str, object],
    *,
    seed: int = 0,
    num_envs: int = 16,
    episodes: int = 16,
    name: str,
) -> Path:
    artifact = tmp_path / name
    hydra = artifact / ".hydra"
    hydra.mkdir(parents=True)
    config = {
        "checkpoint": str(checkpoint["path"]),
        "checkpoint_load_mode": "full",
        "seed": seed,
        "num_envs": num_envs,
        "env": {"config": {"a2_eval_door_handle_height_linspace": [0.80, 1.10]}},
        "algo": {
            "config": {
                "eval": {
                    "num_eval_episodes": episodes,
                    "eval_num_envs_episodes": True,
                    "save_goal_reached_only": False,
                    "save_videos": False,
                    "save_trajectories": False,
                    "a2_eval_m41_strict_telemetry": True,
                    "a2_diagnostic_trace_enabled": True,
                    "a2_eval_p2_posture_axis": "none",
                    "a2_forced_gripper_close_enabled": False,
                    "a2_hold_oracle_enabled": False,
                    "a2_diagnostic_reward_terms": list(P0_TERMS),
                }
            }
        },
    }
    (hydra / "config.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")
    return artifact


def _manifest(tmp_path: Path) -> tuple[dict, dict[str, Path]]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    candidates = []
    artifacts = {}
    for step in (1000, 1500, 2500):
        path = tmp_path / f"model_step_{step:06d}.pt"
        path.write_bytes(f"checkpoint-{step}".encode())
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        candidate = {
            "candidate_id": path.name,
            "step": step,
            "path": str(path),
            "sha256": sha,
        }
        candidates.append(candidate)
        artifacts[path.name] = _artifact(
            tmp_path,
            candidate,
            seed=0,
            name=f"artifact_{step}_seed0",
        )
    return {"schema": "a2_piper_v19_m22_candidate_manifest_v1", "candidates": candidates}, artifacts


def _evidence(
    candidate: dict,
    artifact: Path,
    *,
    status: str = "STRICT_VALID",
    goal: int = 16,
) -> dict:
    return {
        "candidate_id": candidate["candidate_id"],
        "strict_status": status,
        "artifact": str(artifact),
        "checkpoint_path": candidate["path"],
        "checkpoint_sha256": candidate["sha256"],
        "evaluation_topology": "canonical16",
        "evaluation_seed": 0,
        "goal": {"count": goal, "total": 16},
        "complete": {"count": goal, "total": 16},
        "crossing_while_holding": {"count": goal, "total": 16},
        "bilateral_rate": 0.997,
        "coasting_rate": 0.002,
        "over_force_rate": 0.001,
        "hinge_velocity_p95": 2.0,
    }


def _report(tmp_path: Path, name: str) -> Path:
    report = tmp_path / name
    report.write_text("{}\n", encoding="utf-8")
    return report


def _pooled_evidence(
    tmp_path: Path, candidate: dict, *, goal: int = 48
) -> tuple[dict, list[Path]]:
    sources = [
        _artifact(
            tmp_path,
            candidate,
            seed=seed,
            name=f"{candidate['candidate_id']}_source_seed{seed}",
        )
        for seed in (0, 1, 2)
    ]
    row = {
        "candidate_id": candidate["candidate_id"],
        "strict_status": "STRICT_VALID",
        "artifact": str(_report(tmp_path, f"{candidate['candidate_id']}_pooled_report.json")),
        "checkpoint_path": candidate["path"],
        "checkpoint_sha256": candidate["sha256"],
        "evaluation_topology": "pooled48",
        "evaluation_seeds": [0, 1, 2],
        "source_artifacts": [str(source) for source in sources],
        "goal": {"count": goal, "total": 48},
        "complete": {"count": goal, "total": 48},
        "crossing_while_holding": {"count": goal, "total": 48},
        "bilateral_rate": 0.997,
        "coasting_rate": 0.002,
        "over_force_rate": 0.001,
        "hinge_velocity_p95": 2.0,
    }
    return row, sources


def _config_path(artifact: Path) -> Path:
    return artifact / ".hydra" / "config.yaml"


def test_queue_discovers_numeric_steps_and_emits_canonical16_command(tmp_path):
    queue = _load(QUEUE_SOURCE, "v19_queue_test")
    (tmp_path / "model_step_001500.pt").write_bytes(b"1500")
    (tmp_path / "model_step_000250.pt").write_bytes(b"250")
    (tmp_path / "last.pt").write_bytes(b"alias")
    rows = queue.discover_checkpoints(tmp_path)
    assert [row["step"] for row in rows] == [250, 1500]
    command = queue.build_eval_command(rows[-1], tmp_path / "eval", seed=0, gpu="7")
    assert command["argv"][0:3] == [sys.executable, "-m", "gr00t.rl.eval_agent_trl"]
    assert "++num_envs=16" in command["argv"]
    assert "++algo.config.eval.num_eval_episodes=16" in command["argv"]
    assert not any("num_envs=48" in arg or "num_eval_episodes=48" in arg for arg in command["argv"])
    assert "++checkpoint_load_mode=full" in command["argv"]
    assert "++algo.config.eval.a2_eval_p2_posture_axis=none" in command["argv"]
    assert command["argv"][3:5] == ["--device", "cuda:7"]
    assert "CUDA_VISIBLE_DEVICES" not in command["env"]
    assert command["env"] == {
        "ACCELERATE_TORCH_DEVICE": "cuda:7",
        "VK_ICD_FILENAMES": "/usr/share/vulkan/icd.d/nvidia_icd.json",
    }
    with pytest.raises(queue.M22QueueError, match="canonical16"):
        queue.build_eval_command(rows[-1], tmp_path / "pooled", topology="pooled48")


@pytest.mark.parametrize("gpu", ["", "-1", "+1", "01", "7.0", 7, True])
def test_queue_rejects_noncanonical_physical_gpu_id(tmp_path, gpu):
    queue = _load(QUEUE_SOURCE, f"v19_queue_gpu_validation_{repr(gpu)}")
    (tmp_path / "model_step_001500.pt").write_bytes(b"1500")
    rows = queue.discover_checkpoints(tmp_path)
    with pytest.raises(queue.M22QueueError, match="exact non-negative decimal physical id"):
        queue.build_eval_command(rows[0], tmp_path / "eval", gpu=gpu)


def test_queue_missing_artifact_requires_canonical_topology_and_requested_seed(tmp_path):
    queue = _load(QUEUE_SOURCE, "v19_queue_missing_test")
    manifest, _ = _manifest(tmp_path)
    candidate = manifest["candidates"][0]
    mapping = {
        candidate["candidate_id"]: {
            "candidate_id": candidate["candidate_id"],
            "artifact": str(tmp_path / "missing_artifact"),
            "checkpoint_path": candidate["path"],
            "checkpoint_sha256": candidate["sha256"],
            "evaluation_topology": "canonical16",
            "evaluation_seed": 3,
        }
    }
    built = queue.build_queue(manifest, mapping, tmp_path / "outputs", seed=3)
    row = built["rows"][0]
    assert row["artifact_state"] == "MISSING_ARTIFACT"
    assert "++num_envs=16" in row["eval_command"]["argv"]
    assert "++seed=3" in row["eval_command"]["argv"]
    with pytest.raises(queue.M22QueueError, match="canonical16"):
        queue.build_queue(
            manifest,
            {candidate["candidate_id"]: dict(mapping[candidate["candidate_id"]], evaluation_topology="pooled48")},
            tmp_path / "outputs",
            seed=3,
        )
    with pytest.raises(queue.M22QueueError, match="equal requested seed"):
        queue.build_queue(manifest, mapping, tmp_path / "outputs", seed=0)


def test_queue_explicit_artifact_requires_seed_and_exact_config(tmp_path):
    queue = _load(QUEUE_SOURCE, "v19_queue_artifact_test")
    manifest, artifacts = _manifest(tmp_path)
    candidate = manifest["candidates"][0]
    mapping = {
        candidate["candidate_id"]: {
            "candidate_id": candidate["candidate_id"],
            "artifact": str(artifacts[candidate["candidate_id"]]),
            "checkpoint_path": candidate["path"],
            "checkpoint_sha256": candidate["sha256"],
            "evaluation_topology": "canonical16",
            "evaluation_seed": 0,
        }
    }
    assert queue.build_queue(manifest, mapping, tmp_path / "outputs")["rows"][0]["artifact_state"] == "EXPLICIT_ARTIFACT"
    config_path = _config_path(artifacts[candidate["candidate_id"]])
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["seed"] = 1
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    with pytest.raises(queue.M22QueueError, match="seed"):
        queue.build_queue(manifest, mapping, tmp_path / "outputs")
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["seed"] = 0
    config["checkpoint"] = str(tmp_path / "wrong.pt")
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    with pytest.raises(queue.M22QueueError, match="checkpoint"):
        queue.build_queue(manifest, mapping, tmp_path / "outputs")


def test_queue_rejects_wrong_p0_height_and_diagnostics(tmp_path):
    queue = _load(QUEUE_SOURCE, "v19_queue_p0_test")
    manifest, artifacts = _manifest(tmp_path)
    candidate = manifest["candidates"][0]
    mapping = {
        candidate["candidate_id"]: {
            "artifact": str(artifacts[candidate["candidate_id"]]),
            "checkpoint_path": candidate["path"],
            "checkpoint_sha256": candidate["sha256"],
            "evaluation_topology": "canonical16",
            "evaluation_seed": 0,
        }
    }
    config_path = _config_path(artifacts[candidate["candidate_id"]])
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["env"]["config"]["a2_eval_door_handle_height_linspace"] = [0.80, 1.05]
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    with pytest.raises(queue.M22QueueError, match="height"):
        queue.build_queue(manifest, mapping, tmp_path / "outputs")


def test_adjudicator_valid_canonical16_and_pooled48(tmp_path):
    adj = _load(ADJ_SOURCE, "v19_adjudicator_valid_test")
    manifest, artifacts = _manifest(tmp_path / "canonical")
    evidence = [
        _evidence(candidate, artifacts[candidate["candidate_id"]], goal=15 + (index == 1))
        for index, candidate in enumerate(manifest["candidates"])
    ]
    report = adj.adjudicate(manifest, evidence)
    assert report["status"] == "PASS"
    assert report["selected_checkpoint"]["step"] == 1500

    pooled_manifest, _ = _manifest(tmp_path / "pooled")
    pooled_evidence = []
    for index, candidate in enumerate(pooled_manifest["candidates"]):
        row, _ = _pooled_evidence(tmp_path / "pooled_sources", candidate, goal=46 + (index == 1))
        pooled_evidence.append(row)
    pooled_report = adj.adjudicate(pooled_manifest, pooled_evidence)
    assert pooled_report["status"] == "PASS"
    assert pooled_report["selected_checkpoint"]["step"] == 1500


def test_adjudicator_rejects_mixed_evaluation_topology(tmp_path):
    adj = _load(ADJ_SOURCE, "v19_adjudicator_mixed_topology_test")
    manifest, artifacts = _manifest(tmp_path)
    rows = [_evidence(candidate, artifacts[candidate["candidate_id"]]) for candidate in manifest["candidates"]]
    pooled_row, _ = _pooled_evidence(tmp_path / "pooled_sources", manifest["candidates"][0])
    rows[0] = pooled_row
    with pytest.raises(adj.M22AdjudicationError, match="cannot mix evaluation_topology"):
        adj.adjudicate(manifest, rows)


def test_adjudicator_canonical_requires_seed_zero(tmp_path):
    adj = _load(ADJ_SOURCE, "v19_adjudicator_seed_test")
    manifest, artifacts = _manifest(tmp_path)
    rows = [_evidence(candidate, artifacts[candidate["candidate_id"]]) for candidate in manifest["candidates"]]
    rows[0]["evaluation_seed"] = 1
    with pytest.raises(adj.M22AdjudicationError, match="evaluation_seed=0"):
        adj.adjudicate(manifest, rows)


@pytest.mark.parametrize("mutation", ("one_48_env_source", "missing_source", "duplicate_source", "wrong_seed_source"))
def test_adjudicator_rejects_invalid_pooled_sources(tmp_path, mutation):
    adj = _load(ADJ_SOURCE, f"v19_adjudicator_pooled_{mutation}")
    manifest, _ = _manifest(tmp_path)
    rows = []
    first_sources = None
    for candidate in manifest["candidates"]:
        row, sources = _pooled_evidence(tmp_path / "sources", candidate)
        rows.append(row)
        if first_sources is None:
            first_sources = sources
    if mutation == "one_48_env_source":
        config_path = _config_path(first_sources[0])
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        config["num_envs"] = 48
        config["algo"]["config"]["eval"]["num_eval_episodes"] = 48
        config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    elif mutation == "missing_source":
        rows[0].pop("source_artifacts")
    elif mutation == "duplicate_source":
        rows[0]["source_artifacts"][1] = rows[0]["source_artifacts"][0]
    else:
        rows[0]["evaluation_seeds"] = [0, 1, 3]
    with pytest.raises(adj.M22AdjudicationError):
        adj.adjudicate(manifest, rows)


def test_adjudicator_pooled_artifact_cannot_substitute_source_config(tmp_path):
    adj = _load(ADJ_SOURCE, "v19_adjudicator_pooled_substitution_test")
    manifest, _ = _manifest(tmp_path)
    rows = []
    for candidate in manifest["candidates"]:
        row, sources = _pooled_evidence(tmp_path / "sources", candidate)
        if not rows:
            row["artifact"] = str(sources[0])
        rows.append(row)
    with pytest.raises(adj.M22AdjudicationError, match="substitute"):
        adj.adjudicate(manifest, rows)


def test_adjudicator_pooled_45_of_48_fails_redline(tmp_path):
    adj = _load(ADJ_SOURCE, "v19_adjudicator_pooled_threshold_test")
    manifest, _ = _manifest(tmp_path)
    rows = [_pooled_evidence(tmp_path / "sources", candidate, goal=45)[0] for candidate in manifest["candidates"]]
    with pytest.raises(adj.M22AdjudicationError, match="no strict-valid"):
        adj.adjudicate(manifest, rows)


@pytest.mark.parametrize("mutation", ("height", "terms"))
def test_adjudicator_rejects_wrong_p0_config(tmp_path, mutation):
    adj = _load(ADJ_SOURCE, f"v19_adjudicator_p0_{mutation}")
    manifest, artifacts = _manifest(tmp_path)
    config_path = _config_path(artifacts[manifest["candidates"][0]["candidate_id"]])
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if mutation == "height":
        config["env"]["config"]["a2_eval_door_handle_height_linspace"] = [0.80, 1.05]
    else:
        config["algo"]["config"]["eval"]["a2_diagnostic_reward_terms"] = list(P0_TERMS[:-1])
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    rows = [_evidence(candidate, artifacts[candidate["candidate_id"]]) for candidate in manifest["candidates"]]
    with pytest.raises(adj.M22AdjudicationError):
        adj.adjudicate(manifest, rows)


def test_adjudicator_requires_provenance_for_strict_invalid(tmp_path):
    adj = _load(ADJ_SOURCE, "v19_adjudicator_invalid_provenance_test")
    manifest, artifacts = _manifest(tmp_path)
    rows = [
        _evidence(candidate, artifacts[candidate["candidate_id"]], status="STRICT_INVALID")
        for candidate in manifest["candidates"]
    ]
    rows[0].pop("artifact")
    with pytest.raises(adj.M22AdjudicationError, match="provenance"):
        adj.adjudicate(manifest, rows)


@pytest.mark.parametrize("mutation", ("bare_rate", "wrong_total", "negative_rate", "negative_hinge", "over_rate"))
def test_adjudicator_rejects_invalid_metric_units(tmp_path, mutation):
    adj = _load(ADJ_SOURCE, f"v19_adjudicator_metric_{mutation}")
    manifest, artifacts = _manifest(tmp_path)
    rows = [_evidence(candidate, artifacts[candidate["candidate_id"]]) for candidate in manifest["candidates"]]
    if mutation == "bare_rate":
        rows[0]["goal"] = 0.99
    elif mutation == "wrong_total":
        rows[0]["goal"] = {"count": 15, "total": 15}
    elif mutation == "negative_rate":
        rows[0]["bilateral_rate"] = -0.1
    elif mutation == "negative_hinge":
        rows[0]["hinge_velocity_p95"] = -1.0
    else:
        rows[0]["over_force_rate"] = 1.1
    with pytest.raises(adj.M22AdjudicationError):
        adj.adjudicate(manifest, rows)


@pytest.mark.parametrize("mutation", ("wrong_path", "missing_sha"))
def test_adjudicator_rejects_missing_or_wrong_checkpoint_path(tmp_path, mutation):
    adj = _load(ADJ_SOURCE, f"v19_adjudicator_path_{mutation}")
    manifest, artifacts = _manifest(tmp_path)
    rows = [_evidence(candidate, artifacts[candidate["candidate_id"]]) for candidate in manifest["candidates"]]
    if mutation == "wrong_path":
        rows[0]["checkpoint_path"] = str(tmp_path / "wrong.pt")
    else:
        rows[0].pop("checkpoint_sha256")
    with pytest.raises(adj.M22AdjudicationError):
        adj.adjudicate(manifest, rows)


def test_adjudicator_recomputes_actual_checkpoint_hash(tmp_path):
    adj = _load(ADJ_SOURCE, "v19_adjudicator_hash_test")
    manifest, artifacts = _manifest(tmp_path)
    path = Path(manifest["candidates"][0]["path"])
    path.write_bytes(b"tampered")
    rows = [_evidence(candidate, artifacts[candidate["candidate_id"]]) for candidate in manifest["candidates"]]
    with pytest.raises(adj.M22AdjudicationError, match="SHA-256"):
        adj.adjudicate(manifest, rows)


def test_adjudicator_duplicate_sha_surfaces_as_selection_ambiguity(tmp_path):
    adj = _load(ADJ_SOURCE, "v19_adjudicator_duplicate_sha_test")
    manifest, artifacts = _manifest(tmp_path)
    first = Path(manifest["candidates"][0]["path"])
    second = Path(manifest["candidates"][1]["path"])
    second.write_bytes(first.read_bytes())
    manifest["candidates"][1]["sha256"] = hashlib.sha256(second.read_bytes()).hexdigest()
    rows = [_evidence(candidate, artifacts[candidate["candidate_id"]]) for candidate in manifest["candidates"]]
    with pytest.raises(adj.M22AdjudicationError, match="ambiguous"):
        adj.adjudicate(manifest, rows)


def test_adjudicator_rejects_duplicate_or_extra_identity(tmp_path):
    adj = _load(ADJ_SOURCE, "v19_adjudicator_identity_test")
    manifest, artifacts = _manifest(tmp_path)
    rows = [_evidence(candidate, artifacts[candidate["candidate_id"]]) for candidate in manifest["candidates"]]
    with pytest.raises(adj.M22AdjudicationError, match="duplicate"):
        adj.adjudicate(manifest, rows + [dict(rows[0])])
    extra = dict(rows[0], candidate_id="model_step_999999.pt")
    with pytest.raises(adj.M22AdjudicationError, match="extra"):
        adj.adjudicate(manifest, rows[:2] + [extra])


def test_adjudicator_wrong_checkpoint_binding_fails_fast(tmp_path):
    adj = _load(ADJ_SOURCE, "v19_adjudicator_binding_test")
    manifest, artifacts = _manifest(tmp_path)
    rows = [_evidence(candidate, artifacts[candidate["candidate_id"]]) for candidate in manifest["candidates"]]
    rows[0]["checkpoint_sha256"] = "0" * 64
    with pytest.raises(adj.M22AdjudicationError):
        adj.adjudicate(manifest, rows)


def test_adjudicator_ambiguous_pareto_front_fails_fast(tmp_path):
    adj = _load(ADJ_SOURCE, "v19_adjudicator_ambiguous_test")
    manifest, artifacts = _manifest(tmp_path)
    rows = [_evidence(candidate, artifacts[candidate["candidate_id"]]) for candidate in manifest["candidates"]]
    with pytest.raises(adj.M22AdjudicationError, match="ambiguous"):
        adj.adjudicate(manifest, rows)
