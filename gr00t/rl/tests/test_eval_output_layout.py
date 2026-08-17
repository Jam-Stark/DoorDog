"""No-simulation tests for the canonical Hydra evaluation output layout."""

from pathlib import Path

import yaml
from hydra import compose, initialize_config_dir
from omegaconf import OmegaConf


ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = ROOT / "gr00t/rl/config"
BASE_EVAL = CONFIG_DIR / "base_eval.yaml"


def _compose_eval(overrides):
    with initialize_config_dir(version_base="1.1", config_dir=str(CONFIG_DIR)):
        return compose(
            config_name="base_eval",
            overrides=["checkpoint=dummy.pt", *overrides],
            return_hydra_config=True,
        )


def _compose_representative_eval(overrides):
    """Mirror eval_agent_trl's saved-training-config merge without IsaacSim."""

    with initialize_config_dir(version_base="1.1", config_dir=str(CONFIG_DIR)):
        training_config = compose(
            config_name="base",
            overrides=["+exp=wbmanip/door_open_a2_base_lstm"],
        )
        eval_config = compose(
            config_name="base_eval",
            overrides=["checkpoint=dummy.pt", *overrides],
            return_hydra_config=True,
        )

    # compose() returns a structured config; eval_agent_trl merges the loaded
    # training YAML with its override config, so reproduce that merge contract.
    OmegaConf.set_struct(training_config, False)
    OmegaConf.set_struct(eval_config, False)
    return OmegaConf.merge(training_config, eval_config)


def _resolved(config, path):
    value = OmegaConf.select(config, path, throw_on_missing=True)
    return str(value)


def test_base_eval_yaml_declares_canonical_output_interpolations():
    parsed = yaml.safe_load(BASE_EVAL.read_text(encoding="utf-8"))
    assert parsed["eval_output_dir"] == "${eval_base_dir}/${eval_timestamp}-${eval_name}"
    assert parsed["eval_log_dir"] == "${eval_output_dir}"
    assert (
        parsed["env"]["config"]["save_rendering_dir"]
        == "${eval_output_dir}/renderings"
    )
    assert parsed["hydra"]["run"]["dir"] == "${eval_log_dir}"


def test_default_layout_resolves_through_representative_exp_merge():
    config = _compose_representative_eval(
        ["eval_timestamp='20260715_203000'", "eval_name=layout_smoke"]
    )

    expected = "logs_eval/20260715_203000-layout_smoke"
    assert _resolved(config, "eval_output_dir") == expected
    assert _resolved(config, "eval_log_dir") == expected
    assert _resolved(config, "hydra.run.dir") == expected
    assert _resolved(config, "env.config.save_rendering_dir") == f"{expected}/renderings"


def test_cli_eval_output_override_drives_all_result_paths():
    config = _compose_eval(
        [
            "eval_timestamp='20260715_203000'",
            "eval_name=layout_smoke",
            "++eval_output_dir=logs_eval/base_v11/layout_smoke",
        ]
    )

    expected = "logs_eval/base_v11/layout_smoke"
    assert _resolved(config, "eval_output_dir") == expected
    assert _resolved(config, "eval_log_dir") == expected
    assert _resolved(config, "hydra.run.dir") == expected
    assert _resolved(config, "env.config.save_rendering_dir") == f"{expected}/renderings"
