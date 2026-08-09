import pytest
import torch
from torch.distributions import Normal
from types import SimpleNamespace

from gr00t.rl.trl.modules.actor_critic_modules import (
    Actor,
    _resolve_rp0_action_contract,
)
from gr00t.rl.trl.trainer.ppo_trainer_a2_base_api import TRLPPOTrainer


def _make_actor(*, enabled=True, indices=(3, 4), neutral=0.0, num_actions=6):
    actor = Actor.__new__(Actor)
    torch.nn.Module.__init__(actor)
    actor.num_actions = num_actions
    actor.std = torch.nn.Parameter(torch.full((num_actions,), 0.7))
    actor.rp0_enabled = enabled
    actor.rp0_mask_indices = tuple(indices)
    actor.rp0_neutral_value = float(neutral)
    mask = torch.ones(num_actions, dtype=torch.bool)
    if enabled and indices:
        mask[list(indices)] = False
    actor.rp0_action_mask = mask
    actor.rp0_neutral_action = torch.full((num_actions,), float(neutral))
    actor.distribution = None
    return actor


def test_rp0_masks_sample_and_logprob_entropy_at_distribution_level():
    actor = _make_actor()
    mean = torch.tensor([[1.0, -2.0, 3.0, 4.0, -5.0, 6.0]])
    actor.distribution = actor._build_distribution(mean)

    assert torch.equal(actor.action_mean, torch.tensor([[1.0, -2.0, 3.0, 0.0, 0.0, 6.0]]))
    sampled = actor._sample_actions()
    assert torch.equal(sampled[:, 3:5], torch.zeros(1, 2))

    action_a = torch.tensor([[0.2, -1.0, 2.5, 100.0, -100.0, 5.5]])
    action_b = action_a.clone()
    action_b[:, 3:5] = -action_b[:, 3:5]
    assert torch.allclose(actor.get_actions_log_prob(action_a), actor.get_actions_log_prob(action_b))
    expected = Normal(actor.action_mean, actor.action_std).log_prob(action_a)[:, [0, 1, 2, 5]].sum(-1)
    assert torch.allclose(actor.get_actions_log_prob(action_a), expected)
    expected_entropy = Normal(actor.action_mean, actor.action_std).entropy()[:, [0, 1, 2, 5]].sum(-1)
    assert torch.allclose(actor.entropy, expected_entropy)


def test_rp0_disabled_preserves_full_distribution_semantics():
    actor = _make_actor(enabled=False, indices=(3, 4))
    mean = torch.tensor([[1.0, -2.0, 3.0, 4.0, -5.0, 6.0]])
    actor.distribution = actor._build_distribution(mean)
    assert torch.equal(actor.action_mean, mean)
    action = torch.tensor([[0.2, -1.0, 2.5, 4.0, -3.0, 5.5]])
    expected = Normal(mean, actor.action_std).log_prob(action).sum(-1)
    assert torch.allclose(actor.get_actions_log_prob(action), expected)


def test_rp0_contract_rejects_unsupported_shape_or_neutral_value():
    with pytest.raises(ValueError, match="raw base posture indices"):
        _resolve_rp0_action_contract(
            {"rp0_enabled": True, "rp0_mask_indices": [3], "rp0_neutral_value": 0.0},
            6,
        )
    with pytest.raises(ValueError, match="neutral raw value"):
        _resolve_rp0_action_contract(
            {"rp0_enabled": True, "rp0_mask_indices": [3, 4], "rp0_neutral_value": 1.0},
            6,
        )
    enabled, indices, neutral = _resolve_rp0_action_contract(
        {"rp0_enabled": False, "rp0_mask_indices": [3, 4], "rp0_neutral_value": 0.0},
        6,
    )
    assert enabled is False
    assert indices == (3, 4)
    assert neutral == 0.0


def test_rp0_runtime_contract_is_not_persistent_checkpoint_state():
    source = _make_actor(enabled=True)
    source.std.data.copy_(torch.arange(6, dtype=torch.float32) + 1.0)
    assert "rp0_action_mask" not in source.state_dict()
    assert "rp0_neutral_action" not in source.state_dict()
    restored = _make_actor(enabled=False, indices=(3, 4))
    restored.load_state_dict({"std": source.std.detach().clone()}, strict=True)
    assert torch.equal(restored.rp0_action_mask, torch.ones(6, dtype=torch.bool))
    assert torch.equal(restored.rp0_neutral_action, torch.zeros(6))
    assert torch.equal(restored.std, source.std)


def test_specialized_a2_ppo_kl_excludes_masked_posture_dimensions():
    trainer = TRLPPOTrainer.__new__(TRLPPOTrainer)
    trainer.args = SimpleNamespace(vf_coef=0.0, cliprange_value=0.2, cliprange=0.2)
    trainer.config = {"opt_homie": False}
    trainer.policy_model = SimpleNamespace(num_actions=4)
    trainer.optimizer = None
    trainer.entropy_coef = 0.0
    trainer.desired_kl = None
    trainer.accelerator = SimpleNamespace(
        gather=lambda value: value,
    )
    trainer._adjust_learning_rate_based_on_kl = lambda *_args: None

    forward_results = {
        "policy_results": {
            "logprobs": torch.zeros(1),
            "action_mean": torch.tensor([[0.0, 0.0, 100.0, -100.0]]),
            "action_std": torch.ones(1, 4),
            "entropy": torch.zeros(1),
            "action_mask": torch.tensor([True, True, False, False]),
        },
        "value_results": torch.zeros(1, 1),
    }
    rollout = {
        "mb_old_mu": torch.zeros(1, 4),
        "mb_old_sigma": torch.ones(1, 4),
        "mb_values": torch.zeros(1),
        "mb_return": torch.zeros(1),
        "mb_logprobs": torch.zeros(1),
        "mb_advantage": torch.ones(1),
        "mb_padding_mask": torch.zeros(1, dtype=torch.bool),
        "mb_padding_mask_p1": torch.zeros(1, dtype=torch.bool),
        "micro_batch_inds": torch.zeros(1, dtype=torch.long),
    }
    result = trainer._compute_ppo_loss(forward_results, rollout)
    assert result["local_kl_mean"] < 1.0e-3
