"""Focused CPU-only v27 per-environment native friction contracts."""

from pathlib import Path
from types import SimpleNamespace

import torch

from gr00t.rl.envs.door.a2_v24_friction import A2V24DoorFrictionBackend, V24FrictionConfig


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "gr00t/rl/envs/door/door_open_a2_base.py"


class _Door:
    def __init__(self):
        self.data = SimpleNamespace(
            joint_pos=torch.zeros(3, 2),
            joint_friction_coeff=torch.zeros(3, 2),
            joint_dynamic_friction_coeff=torch.zeros(3, 2),
            joint_viscous_friction_coeff=torch.zeros(3, 2),
        )

    def find_joints(self, _pattern, preserve_order=True):
        assert preserve_order is True
        return [1], ["hinge"]

    def write_joint_friction_coefficient_to_sim(self, static, dynamic, viscous, *, joint_ids, env_ids):
        assert joint_ids == [1]
        self.data.joint_friction_coeff[env_ids[:, None], joint_ids] = static
        self.data.joint_dynamic_friction_coeff[env_ids[:, None], joint_ids] = dynamic
        self.data.joint_viscous_friction_coeff[env_ids[:, None], joint_ids] = viscous


def test_v24_backend_accepts_exact_v27_bucket_rows_and_readback():
    door = _Door()
    backend = A2V24DoorFrictionBackend(
        door,
        V24FrictionConfig(True, "native_joint_friction_v1", 0.0, 0.0, 0.0),
        device="cpu",
    )
    env_ids = torch.tensor([0, 2], dtype=torch.long)
    static = torch.tensor([[0.0], [5.0]])
    dynamic = static * 0.75
    backend.install_profile_rows(env_ids, static, dynamic, torch.zeros_like(static))
    receipt = backend.apply(env_ids)
    assert receipt["matches"] == {
        "joint_friction_coeff": True,
        "joint_dynamic_friction_coeff": True,
        "joint_viscous_friction_coeff": True,
    }
    assert door.data.joint_friction_coeff[:, 1].tolist() == [0.0, 0.0, 5.0]
    assert door.data.joint_dynamic_friction_coeff[:, 1].tolist() == [0.0, 0.0, 3.75]


def test_v27_bucket_contract_is_exact_and_legacy_path_has_no_selector():
    source = SOURCE.read_text(encoding="utf-8")
    start = source.index("    def _parse_a2_v27_friction_bucket_config")
    end = source.index("    def _init_a2_v27_runtime", start)
    parser = source[start:end]
    assert 'resolved != (0.0, 2.0, 5.0)' in parser
    assert 'if not enabled:\n            return None' in parser
    apply = source[source.index("    def _apply_a2_v27_friction_bucket"):source.index("    def _init_a2_v24_force_boundary_runtime")]
    assert "backend.install_profile_rows(env_ids, static, dynamic, viscous)" in apply
    assert "backend.apply(env_ids)" in apply
    assert "_a2_v27_friction_static_readback" in apply
    assert "joint_dynamic_friction_coeff" in apply
