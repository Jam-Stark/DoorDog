"""CPU-only tests for the v21-B trainer metric producer contract."""

from __future__ import annotations

import pytest
from omegaconf import OmegaConf

from gr00t.rl.train_agent_trl import (
    _A2_BASE_API_TRAINER_TARGET,
    _trainer_runtime_kwargs,
)
from gr00t.rl.trl.trainer.ppo_trainer_a2_base_api import (
    TRLPPOTrainer,
    build_v21b_training_metric_row,
    normalize_v21b_training_metrics,
)


def _actual_metrics() -> dict[str, float]:
    return {
        "Env/a2_v21B_send_latch_fire_rate": 0.4,
        "Env/a2_v21B_hinge_at_send_latch_rad": 0.9,
        "Env/a2_v21B_hinge_at_crossing_rad": 1.1,
        "Env/a2_v21B_send_to_cross_steps": 12.0,
        "Env/a2_v21B_stage_overtime_rate": 0.02,
        "Env/a2_v21B_upper_dof_overspeed_rate": 0.01,
        "Env/a2_v21B_arm_clipped_utilization": 0.23,
        "Env/a2_v21B_arm_clipped_utilization_valid_rate": 1.0,
        "Env/a2_v21B_finite_data": 1.0,
        "Env/a2_v21B_decomposition_sanity": 1.0,
        "Env/a2_v21B_decomposition_sanity_valid_rate": 1.0,
    }


_IDENTITY = {
    "cell": "B4",
    "seed": 0,
    "source_config_sha256": "e" * 64,
    "materialization_sha256": "f" * 64,
    "materialized_config_sha256": "1" * 64,
    "materialization_phase": "FORMAL_PROMOTED",
    "adaptation_bundle_sha256": "2" * 64,
}


def test_v21b_producer_maps_exact_env_keys_to_normalized_row():
    metrics = _actual_metrics()
    normalized = normalize_v21b_training_metrics(metrics)
    assert normalized["send_latch_fire_rate"] == 0.4
    assert normalized["hinge_at_crossing_rad"] == 1.1
    row = build_v21b_training_metric_row(
        metrics,
        batch_index=7,
        **_IDENTITY,
        source_lock_sha256="a" * 64,
        source_lock_file_sha256="b" * 64,
        git_commit="c" * 40,
        git_tree="d" * 40,
    )
    assert row["schema"] == "a2_piper_base_v21B_training_metric_v1"
    assert row["metrics"] == normalized
    assert row["metric_sources"]["send_latch_fire_rate"] == "a2_v21B_send_latch_fire_rate"


def test_v21b_producer_rejects_synthetic_or_missing_sources():
    metrics = _actual_metrics()
    metrics.pop("Env/a2_v21B_send_latch_fire_rate")
    with pytest.raises(ValueError, match="source key is missing"):
        normalize_v21b_training_metrics(metrics)
    with pytest.raises(ValueError, match="source key is missing"):
        build_v21b_training_metric_row(
            {"send_latch_fire_rate": 1.0},
            batch_index=1,
            **_IDENTITY,
            source_lock_sha256="a" * 64,
            source_lock_file_sha256="b" * 64,
            git_commit="c" * 40,
            git_tree="d" * 40,
        )


@pytest.mark.parametrize(
    "key",
    (
        "Env/a2_v21B_arm_clipped_utilization_valid_rate",
        "Env/a2_v21B_decomposition_sanity_valid_rate",
    ),
)
def test_v21b_producer_rejects_incomplete_coverage(key):
    metrics = _actual_metrics()
    metrics[key] = 0.5
    with pytest.raises(ValueError, match="coverage"):
        normalize_v21b_training_metrics(metrics)


def test_v21b_identity_is_hashed_once_and_config_or_path_mutation_fails(tmp_path, monkeypatch):
    import hashlib
    import json

    checkpoint = tmp_path / "checkpoint.pt"
    checkpoint.write_bytes(b"checkpoint")
    source_lock = tmp_path / "source_lock.json"
    source_lock.write_text(
        json.dumps(
            {
                "schema": "a2_piper_base_v21B_source_lock_v1",
                "source_lock_sha256": "b" * 64,
                "source_checkpoint_sha256": hashlib.sha256(b"checkpoint").hexdigest(),
            }
        ),
        encoding="utf-8",
    )
    calls = {"validate": 0, "hash": []}

    def fake_validate(lock, repo_root, *, require_current):
        calls["validate"] += 1
        assert require_current is True

    monkeypatch.setattr(
        "scriptsFORhuman.v21B.a2_piper_v21B_source_freeze.validate_source_lock",
        fake_validate,
    )
    original_hash = TRLPPOTrainer._v21b_sha256_file

    def counted_hash(path, *, label):
        calls["hash"].append(label)
        return original_hash(path, label=label)

    monkeypatch.setattr(TRLPPOTrainer, "_v21b_sha256_file", staticmethod(counted_hash))
    trainer = object.__new__(TRLPPOTrainer)
    trainer.config = OmegaConf.create({"unrelated_ppo_key": 1})
    trainer.workflow_config = OmegaConf.create({
        "r2_source_lock_path": str(source_lock),
        "v21b_source_checkpoint_sha256": hashlib.sha256(b"checkpoint").hexdigest(),
        "v21b_source_lock_sha256": "b" * 64,
        "v21b_cell": "B4",
        "v21b_materialized_from_config_sha256": _IDENTITY["source_config_sha256"],
        "v21b_materialization_sha256": _IDENTITY["materialization_sha256"],
        "v21b_materialized_config_sha256": _IDENTITY["materialized_config_sha256"],
        "v21b_adaptation_bundle_sha256": _IDENTITY["adaptation_bundle_sha256"],
        "v21b_materialization_phase": _IDENTITY["materialization_phase"],
        "seed": 0,
        "env": {"config": {
            "a2_v21B_source_checkpoint_sha256": hashlib.sha256(b"checkpoint").hexdigest(),
            "a2_v21B_source_lock_sha256": "b" * 64,
            "a2_v21B_cell": "B4",
            "a2_v20_R2_seed": 0,
            "a2_v21B_source_config_sha256": _IDENTITY["source_config_sha256"],
            "a2_v21B_materialization_sha256": _IDENTITY["materialization_sha256"],
            "a2_v21B_materialized_config_sha256": _IDENTITY["materialized_config_sha256"],
            "a2_v21B_adaptation_bundle_sha256": _IDENTITY["adaptation_bundle_sha256"],
            "a2_v21B_materialization_phase": _IDENTITY["materialization_phase"],
        }},
    })
    trainer.checkpoint_path = str(checkpoint)

    first = trainer._get_v21b_training_identity()
    second = trainer._get_v21b_training_identity()
    assert first is second
    assert calls["validate"] == 1
    assert calls["hash"] == ["source lock", "checkpoint"]

    trainer.workflow_config["env"]["config"]["a2_v21B_source_checkpoint_sha256"] = "c" * 64
    with pytest.raises(RuntimeError, match="configured source checkpoint"):
        trainer._get_v21b_training_identity()

    trainer.workflow_config["env"]["config"]["a2_v21B_source_checkpoint_sha256"] = first["source_checkpoint_sha256"]
    trainer.checkpoint_path = str(tmp_path / "other.pt")
    with pytest.raises(RuntimeError, match="checkpoint path changed"):
        trainer._get_v21b_training_identity()


def test_v21b_emission_uses_root_workflow_config_at_trainer_boundary(tmp_path, monkeypatch):
    import hashlib
    import json

    checkpoint = tmp_path / "checkpoint.pt"
    checkpoint.write_bytes(b"checkpoint")
    checkpoint_sha256 = hashlib.sha256(b"checkpoint").hexdigest()
    source_lock = tmp_path / "source_lock.json"
    source_lock.write_text(
        json.dumps(
            {
                "schema": "a2_piper_base_v21B_source_lock_v1",
                "source_lock_sha256": "b" * 64,
                "source_checkpoint_sha256": checkpoint_sha256,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "scriptsFORhuman.v21B.a2_piper_v21B_source_freeze.validate_source_lock",
        lambda lock, repo_root, *, require_current: None,
    )
    output = tmp_path / "canonical" / "r2_training_metrics.jsonl"
    workflow_config = OmegaConf.create(
        {
            "r2_evidence_enabled": True,
            "r2_source_lock_path": str(source_lock),
            "r2_training_metrics_path": str(output),
            "scientific_plan_id": "base_v21B_theta_arm_ablation_v1",
            "v21b_source_checkpoint_sha256": checkpoint_sha256,
            "v21b_source_lock_sha256": "b" * 64,
            "v21b_cell": "B4",
            "v21b_materialized_from_config_sha256": _IDENTITY["source_config_sha256"],
            "v21b_materialization_sha256": _IDENTITY["materialization_sha256"],
            "v21b_materialized_config_sha256": _IDENTITY["materialized_config_sha256"],
            "v21b_adaptation_bundle_sha256": _IDENTITY["adaptation_bundle_sha256"],
            "v21b_materialization_phase": _IDENTITY["materialization_phase"],
            "seed": 0,
            "env": {
                "config": {
                    "a2_v21B_source_checkpoint_sha256": checkpoint_sha256,
                    "a2_v21B_source_lock_sha256": "b" * 64,
                    "a2_v21B_cell": "B4",
                    "a2_v20_R2_seed": 0,
                    "a2_v21B_source_config_sha256": _IDENTITY["source_config_sha256"],
                    "a2_v21B_materialization_sha256": _IDENTITY["materialization_sha256"],
                    "a2_v21B_materialized_config_sha256": _IDENTITY["materialized_config_sha256"],
                    "a2_v21B_adaptation_bundle_sha256": _IDENTITY["adaptation_bundle_sha256"],
                    "a2_v21B_materialization_phase": _IDENTITY["materialization_phase"],
                }
            },
        }
    )
    trainer = object.__new__(TRLPPOTrainer)
    trainer.config = OmegaConf.create({"num_steps_per_env": 1})
    trainer.workflow_config = workflow_config
    trainer.checkpoint_path = str(checkpoint)

    trainer._write_r2_training_metric_if_enabled(_actual_metrics(), batch_index=1)

    rows = output.read_text(encoding="utf-8").splitlines()
    assert len(rows) == 1
    row = json.loads(rows[0])
    assert row["schema"] == "a2_piper_base_v21B_training_metric_v1"
    assert row["cell"] == "B4"
    assert row["batch_index"] == 1
    assert row["metrics"] == normalize_v21b_training_metrics(_actual_metrics())
    assert not trainer.config.get("r2_evidence_enabled", False)


def test_missing_workflow_config_fails_at_metric_emission():
    trainer = object.__new__(TRLPPOTrainer)
    trainer.config = OmegaConf.create({"unrelated_ppo_key": 1})

    with pytest.raises(RuntimeError, match="explicit workflow_config"):
        trainer._write_r2_training_metric_if_enabled({}, batch_index=1)


def test_disabled_root_workflow_config_skips_metric_emission(tmp_path):
    trainer = object.__new__(TRLPPOTrainer)
    trainer.config = OmegaConf.create({"unrelated_ppo_key": 1})
    trainer.workflow_config = OmegaConf.create(
        {
            "r2_evidence_enabled": False,
            "r2_training_metrics_path": str(tmp_path / "metrics.jsonl"),
        }
    )

    trainer._write_r2_training_metric_if_enabled({}, batch_index=1)

    assert not (tmp_path / "metrics.jsonl").exists()


def test_a2_runtime_kwargs_bind_workflow_config_only_for_a2_trainer():
    workflow_config = OmegaConf.create({"r2_evidence_enabled": True})
    kwargs = _trainer_runtime_kwargs(
        trainer_target=_A2_BASE_API_TRAINER_TARGET,
        workflow_config=workflow_config,
        checkpoint_load_mode="policy_only",
    )
    assert kwargs["workflow_config"] is workflow_config
    assert kwargs["checkpoint_load_mode"] == "policy_only"

    assert _trainer_runtime_kwargs(
        trainer_target="gr00t.rl.trl.trainer.ppo_trainer.TRLPPOTrainer",
        workflow_config=workflow_config,
        checkpoint_load_mode="policy_only",
    ) == {}
