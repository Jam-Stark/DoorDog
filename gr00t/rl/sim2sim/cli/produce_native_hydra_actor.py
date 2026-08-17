#!/usr/bin/env python3
"""Thin producer run from a read-only distillation checkout.

This script intentionally imports the actor and Hydra config from the checkout
on ``PYTHONPATH``.  It never imports Isaac or MuJoCo and only exports the
deployable Student actor surface plus deterministic policy I/O.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import hydra
import numpy as np
import torch
from omegaconf import OmegaConf


RECEIPT_SCHEMA = "doordog.sim2sim.native_loader_receipt.v1"
GOLDEN_SCHEMA = "doordog.sim2sim.policy_golden_io.v1"


def _hidden(actor: torch.nn.Module, layers: int, hidden_dim: int) -> tuple[np.ndarray, np.ndarray]:
    states = actor.get_hidden_states()
    if states is None:
        zeros = np.zeros((layers, 1, hidden_dim), dtype=np.float32)
        return zeros.copy(), zeros.copy()
    hidden_h, hidden_c = states
    return hidden_h.detach().cpu().numpy().copy(), hidden_c.detach().cpu().numpy().copy()


def _inputs(actor_dim: int, d435_hw: tuple[int, int], head_hw: tuple[int, int]) -> list[dict[str, torch.Tensor]]:
    standing = np.zeros(actor_dim, dtype=np.float32)
    standing[5] = -1.0
    intermediate = np.linspace(-0.05, 0.05, actor_dim, dtype=np.float32)
    meta = (
        np.array([0.0, 0.0, 0.0, 1.0, 1.0, 1.0], dtype=np.float32),
        np.array([0.1, 0.1, 0.05, 1.0, 1.0, 1.0], dtype=np.float32),
        np.array([0.2, 0.2, 0.1, 1.0, 1.0, 1.0], dtype=np.float32),
    )
    actor_rows = (np.zeros(actor_dim, dtype=np.float32), standing, intermediate)
    rows = []
    for actor_row, meta_row in zip(actor_rows, meta, strict=True):
        rows.append(
            {
                "actor_obs": torch.from_numpy(actor_row).unsqueeze(0),
                "vision_obs": torch.zeros((1, d435_hw[0], d435_hw[1], 6), dtype=torch.float32),
                "context_vision_obs": torch.zeros((1, head_hw[0], head_hw[1], 3), dtype=torch.float32),
                "camera_meta": torch.from_numpy(meta_row).unsqueeze(0),
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--resolved-config", required=True, type=Path)
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    config = OmegaConf.load(args.resolved_config.resolve(strict=True))
    checkpoint = torch.load(args.checkpoint.resolve(strict=True), map_location="cpu", weights_only=False)
    actor_config = config.algo.config.actor
    actor = hydra.utils.instantiate(
        actor_config,
        env_config=config.env.config,
        algo_config=config.algo.config,
        module_dim_dict=config.algo.config.module_dim,
        _recursive_=False,
    ).cpu()
    incompat = actor.load_state_dict(checkpoint["policy_state_dict"], strict=True)
    if incompat.missing_keys or incompat.unexpected_keys:
        raise RuntimeError(f"strict policy load mismatch: {incompat}")
    actor.eval()
    actor.init_rollout()
    actor.reset()

    actor_dim = int(config.env.config.robot.algo_obs_dim_dict.actor_obs)
    action_dim = int(config.algo.config.student_action_dim)
    d435_hw = tuple(int(value) for value in config.simulator.config.cameras.policy_multiview.primary_resolution)
    head_hw = tuple(int(value) for value in config.simulator.config.cameras.policy_multiview.context.resolution)
    layers = int(actor_config.rnn_num_layers)
    hidden_dim = int(actor_config.rnn_hidden_dim)
    captures: dict[str, list[np.ndarray]] = {
        "actor_obs": [],
        "vision_obs": [],
        "context_vision_obs": [],
        "camera_meta": [],
        "hidden_h_before": [],
        "hidden_c_before": [],
        "action_mean": [],
        "hidden_h_after": [],
        "hidden_c_after": [],
        "done": [],
    }
    with torch.inference_mode():
        for obs in _inputs(actor_dim, d435_hw, head_hw):
            hidden_h, hidden_c = _hidden(actor, layers, hidden_dim)
            action = actor.act_inference(obs)
            if tuple(action.shape) != (1, action_dim) or not bool(torch.isfinite(action).all()):
                raise RuntimeError(f"native actor returned invalid action {tuple(action.shape)}")
            after_h, after_c = _hidden(actor, layers, hidden_dim)
            for name in ("actor_obs", "vision_obs", "context_vision_obs", "camera_meta"):
                captures[name].append(obs[name].cpu().numpy())
            captures["hidden_h_before"].append(hidden_h)
            captures["hidden_c_before"].append(hidden_c)
            captures["action_mean"].append(action.cpu().numpy())
            captures["hidden_h_after"].append(after_h)
            captures["hidden_c_after"].append(after_c)
            captures["done"].append(np.array([False], dtype=np.bool_))

    actor_path = output_dir / "actor_state_dict.pt"
    torch.save(actor.state_dict(), actor_path)
    golden_dir = output_dir / "golden"
    golden_dir.mkdir()
    arrays = {
        name: (
            np.stack(values, axis=0)
            if name in {"hidden_h_before", "hidden_c_before", "hidden_h_after", "hidden_c_after"}
            else np.concatenate(values, axis=0)
        )
        for name, values in captures.items()
    }
    np.savez_compressed(golden_dir / "golden_io.npz", **arrays)
    golden_manifest = {
        "schema": GOLDEN_SCHEMA,
        "status": "CAPTURED_POLICY_ONLY_NATIVE_HYDRA",
        "input_authority": "DETERMINISTIC_CONTRACT_FIXTURES_NOT_ISAAC_STATE_TRACE",
        "row_order": ["reset_contract", "standing_contract", "intermediate_contract"],
        "arrays": {
            name: {"shape": list(value.shape), "dtype": str(value.dtype)}
            for name, value in arrays.items()
        },
    }
    (golden_dir / "golden_manifest.json").write_text(
        json.dumps(golden_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "status": "NATIVE_LOADER_READY",
        "loader_scope": "POLICY_ONLY_NATIVE_HYDRA_NO_ISAAC_ENV",
        "source_commit": args.source_commit,
        "source_config_path": str(args.resolved_config.resolve()),
        "source_checkpoint_path": str(args.checkpoint.resolve()),
        "checkpoint_payload_key": "policy_state_dict",
        "strict_state_dict_load": True,
        "policy_tensor_count": len(actor.state_dict()),
        "actor_obs_dim": actor_dim,
        "action_dim": action_dim,
        "recurrent_hidden_shape": [layers, 1, hidden_dim],
        "golden": "golden/golden_manifest.json",
        "golden_input_authority": golden_manifest["input_authority"],
        "device": "cpu",
    }
    (output_dir / "native_loader_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
