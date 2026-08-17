#!/usr/bin/env python3
"""Replay a StudentPolicyBundle golden trace through its native Hydra actor."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import hydra
import numpy as np
import torch
from omegaconf import OmegaConf


ARRAY_INPUTS = ("actor_obs", "vision_obs", "context_vision_obs", "camera_meta")


def _hidden(actor: torch.nn.Module, layers: int, hidden_dim: int) -> tuple[np.ndarray, np.ndarray]:
    states = actor.get_hidden_states()
    if states is None:
        zeros = np.zeros((layers, 1, hidden_dim), dtype=np.float32)
        return zeros.copy(), zeros.copy()
    hidden_h, hidden_c = states
    return hidden_h.detach().cpu().numpy(), hidden_c.detach().cpu().numpy()


def _assert_close(name: str, actual: np.ndarray, expected: np.ndarray, atol: float) -> float:
    maximum = float(np.max(np.abs(actual - expected)))
    if maximum > atol:
        raise AssertionError(f"{name} max_abs_diff={maximum:.9g} exceeds atol={atol:.9g}")
    return maximum


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle-dir", required=True, type=Path)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output-receipt", required=True, type=Path)
    parser.add_argument("--atol", type=float, default=1.0e-6)
    args = parser.parse_args()

    bundle = args.bundle_dir.resolve(strict=True)
    config = OmegaConf.load(bundle / "config_snapshot.yaml")
    actor_config = config.algo.config.actor
    actor = hydra.utils.instantiate(
        actor_config,
        env_config=config.env.config,
        algo_config=config.algo.config,
        module_dim_dict=config.algo.config.module_dim,
        _recursive_=False,
    ).cpu()
    state = torch.load(bundle / "actor_state_dict.pt", map_location="cpu", weights_only=False)
    incompat = actor.load_state_dict(state, strict=True)
    if incompat.missing_keys or incompat.unexpected_keys:
        raise RuntimeError(f"strict bundle actor load mismatch: {incompat}")
    actor.eval()
    actor.init_rollout()
    actor.reset()

    layers = int(actor_config.rnn_num_layers)
    hidden_dim = int(actor_config.rnn_hidden_dim)
    maxima: dict[str, float] = {}
    with np.load(bundle / "golden" / "golden_io.npz", allow_pickle=False) as golden:
        rows = int(golden["action_mean"].shape[0])
        with torch.inference_mode():
            for row in range(rows):
                before_h, before_c = _hidden(actor, layers, hidden_dim)
                maxima[f"row_{row}.hidden_h_before"] = _assert_close(
                    "hidden_h_before", before_h, golden["hidden_h_before"][row], args.atol
                )
                maxima[f"row_{row}.hidden_c_before"] = _assert_close(
                    "hidden_c_before", before_c, golden["hidden_c_before"][row], args.atol
                )
                obs = {name: torch.from_numpy(golden[name][row : row + 1]) for name in ARRAY_INPUTS}
                action = actor.act_inference(obs).cpu().numpy()
                after_h, after_c = _hidden(actor, layers, hidden_dim)
                maxima[f"row_{row}.action_mean"] = _assert_close(
                    "action_mean", action, golden["action_mean"][row : row + 1], args.atol
                )
                maxima[f"row_{row}.hidden_h_after"] = _assert_close(
                    "hidden_h_after", after_h, golden["hidden_h_after"][row], args.atol
                )
                maxima[f"row_{row}.hidden_c_after"] = _assert_close(
                    "hidden_c_after", after_c, golden["hidden_c_after"][row], args.atol
                )
                if bool(golden["done"][row]):
                    actor.reset()

    receipt = {
        "schema": "doordog.sim2sim.policy_golden_replay_receipt.v1",
        "result_classification": "VALID_COMPARABLE",
        "source_commit": args.source_commit,
        "bundle": str(bundle),
        "device": "cpu",
        "rows": rows,
        "atol": args.atol,
        "max_abs_diff": max(maxima.values()),
        "per_field_max_abs_diff": maxima,
        "input_authority": "DETERMINISTIC_CONTRACT_FIXTURES_NOT_ISAAC_STATE_TRACE",
    }
    args.output_receipt.parent.mkdir(parents=True, exist_ok=True)
    args.output_receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
