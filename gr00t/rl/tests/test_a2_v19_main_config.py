"""CPU-only v19 seven-cell matrix/config tests."""

from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = ROOT / "gr00t/rl/config/ablation/wbmanip"


MATRIX = {
    "G1": (1.60, 1.8, True, 1500),
    "G2": (1.60, 1.5, True, 1500),
    "G3": (1.40, 1.5, True, 1500),
    "G4": (1.60, 1.8, True, 2500),
    "G5": (1.60, 1.8, False, 1500),
    "G6": (1.60, 1.8, True, 1500),
    "G7": (1.80, 2.0, True, 1500),
}
FILES = {
    "G1": "base_v19_G1_full.yaml",
    "G2": "base_v19_G2_norm_control.yaml",
    "G3": "base_v19_G3_no_carry_control.yaml",
    "G4": "base_v19_G4_drifted_warmstart.yaml",
    "G5": "base_v19_G5_no_overspeed_fix.yaml",
    "G6": "base_v19_G6_full_replicate.yaml",
    "G7": "base_v19_G7_ceiling_probe.yaml",
}
CKPT_ROOT = "logs_rl/a2_piper_full_stage_a2_base/base_v18_main-20260724_063738/model_step_"


def _load(group: str) -> dict:
    return yaml.safe_load((CONFIG_DIR / FILES[group]).read_text(encoding="utf-8"))


def test_v19_matrix_is_exact_and_training_ready():
    for group, (threshold, norm, enabled, step) in MATRIX.items():
        config = _load(group)
        assert config["checkpoint"] == CKPT_ROOT + f"{step:06d}.pt"
        assert config["checkpoint_load_mode"] == "policy_only"
        assert config["auto_load_latest"] is False
        assert config["seed"] == 0
        assert config["num_envs"] == 4096
        assert config["headless"] is True
        assert config["algo"]["trl"]["num_total_batches"] == 2500
        assert config["callbacks"]["model_save"]["save_frequency"] == 250
        env = config["env"]["config"]
        assert env["a2_stage4_release_hinge_threshold"] == threshold
        assert env["a2_stage4_to5_door_hinge_threshold"] == 1.25
        assert env["a2_corridor_door_wide_hinge_norm"] == norm
        assert env["a2_arm_dof_overspeed_soft_margin_enabled"] is enabled
        assert env["a2_arm_dof_overspeed_soft_margin_width"] == 0.5
        assert config["rewards"]["reward_scales"]["penalty_a2_posture_command_l1"] == -0.3
        assert config["robot"]["control"]["stiffness"] == {"arm_j7": 1300.0, "arm_j8": 1300.0}
        assert config["robot"]["control"]["damping"] == {"arm_j7": 32.0, "arm_j8": 32.0}


def test_g1_g6_semantics_are_identical_except_filename():
    g1 = _load("G1")
    g6 = _load("G6")
    assert g1 == g6


def test_v19_headers_match_roles_and_single_gpu_topology():
    expected = {
        "G1": "full carry institution",
        "G2": "normalization control",
        "G3": "no-carry control",
        "G4": "drifted checkpoint 2500",
        "G5": "without the F2 overspeed fix",
        "G6": "full G1 replicate",
        "G7": "geometric hold-ceiling probe",
    }
    for group, phrase in expected.items():
        header = "\n".join((CONFIG_DIR / FILES[group]).read_text(encoding="utf-8").splitlines()[:4])
        assert phrase in header
        assert "one process / one GPU / 4096 envs per group" in header
        assert "four processes" not in header
