"""CPU-only, report-only interaction-history identifiability probe for v27 L lanes.

The model uses proprioceptive/command/contact estimates. Door parameters and
hinge state are excluded from inputs. No artifact is fed back to training.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

import numpy as np

from v27_contract import read_json, require, write_json
from v27_reduce import iter_json_array

WINDOW = 64
SPLIT_SEED = 270202
RIDGE = 1.0
FEATURES = {
    "arm_joint_pos": 6, "arm_joint_vel": 6, "arm_joint_pos_target": 6,
    "arm_implicit_applied_effort_estimate": 6, "base_projected_gravity": 3,
    "base_lin_vel": 3, "base_ang_vel": 3, "physical_base_command": 5,
    "handle_contact_force_norm": 2,
}


def vector(row):
    chunks = []
    for key, size in FEATURES.items():
        value = np.asarray(row[key], dtype=np.float64)
        require(value.shape == (size,) and np.isfinite(value).all(), f"invalid shadow input {key}")
        chunks.append(value)
    return np.concatenate(chunks)


def collect(manifest):
    features, targets, groups, episodes, excluded = [], [], [], [], []
    for lane in manifest["lanes"]:
        require(lane["cell"].startswith("L"), "shadow estimator only accepts L evaluation lanes")
        artifact = Path(lane["artifact_path"])
        metrics = read_json(artifact / "metrics_eval.json")
        require(metrics["completed_episodes"] == lane["episodes"], "shadow exact-N source")
        terminal = {row["env_id"]: row for row in metrics["episode_terminal_diagnostics"]}
        windows = defaultdict(list)
        window_counts = defaultdict(int)
        for row in iter_json_array(artifact / "stage2_5_step_trace.json"):
            env_id = row["env_id"]
            require(row["first_episode_active"] and row["episode_index"] == 0, "shadow first episode source")
            windows[env_id].append(vector(row))
            if len(windows[env_id]) < WINDOW:
                continue
            block = np.stack(windows[env_id])
            features.append(np.concatenate((block.mean(0), block.std(0), block[-1], block[-1] - block[0])))
            item = terminal[env_id]
            if lane["stratum"] == "nominal":
                require(lane["expected_contract"]["env.config.a2_v24_friction_enabled"] is False, "nominal friction contract")
                friction = 0.0
            else:
                friction = item["a2_v27"]["friction_readback"]["static_effort"]
            targets.append([friction, item["door_weight"]])
            # Keep the same deterministic door slot out of training across all policies.
            groups.append(f"{lane['seed']}/{lane['stratum']}/{lane['side']}/{env_id}")
            episodes.append(f"{lane['cell']}/{lane['stratum']}/{lane['side']}/{env_id}")
            windows[env_id].clear()
            window_counts[env_id] += 1
        excluded.extend(f"{lane['cell']}/{lane['stratum']}/{lane['side']}/{env_id}"
                        for env_id in terminal if not window_counts[env_id])
    require(features, "no complete 64-step history windows")
    x, y = np.stack(features), np.asarray(targets, dtype=np.float64)
    require(np.isfinite(x).all() and np.isfinite(y).all(), "shadow finite observations/targets")
    return x, y, np.asarray(groups), np.asarray(episodes), excluded


def score(y, prediction):
    error = ((prediction - y) ** 2).sum(0)
    total = ((y - y.mean(0)) ** 2).sum(0)
    return {name: {"r2": None if total[i] == 0 else float(1 - error[i] / total[i]),
                   "rmse": float(np.sqrt(error[i] / len(y)))}
            for i,name in enumerate(("static_friction_nm", "mass_kg"))}


def run(manifest):
    x, y, groups, episodes, excluded = collect(manifest)
    unique = np.unique(groups)
    require(len(unique) >= 4, "insufficient independent episode groups for heldout estimation")
    ordered = np.random.default_rng(SPLIT_SEED).permutation(unique)
    held_groups = ordered[:max(1, len(ordered) // 4)]
    held = np.isin(groups, held_groups)
    train_x, train_y = x[~held], y[~held]
    mean, std = train_x.mean(0), train_x.std(0)
    retained = std > 0
    train_z = (train_x[:,retained] - mean[retained]) / std[retained]
    held_z = (x[held][:,retained] - mean[retained]) / std[retained]
    target_mean = train_y.mean(0)
    # NumPy's established least-squares solver fits a fixed ridge objective.
    design = np.concatenate((train_z, np.sqrt(RIDGE) * np.eye(train_z.shape[1])), axis=0)
    response = np.concatenate((train_y - target_mean, np.zeros((train_z.shape[1],2))), axis=0)
    coefficients = np.linalg.lstsq(design, response, rcond=None)[0]
    prediction = held_z @ coefficients + target_mean
    baseline = np.broadcast_to(target_mean, prediction.shape)
    episode_predictions, episode_targets = [], []
    held_episodes = episodes[held]
    for episode in np.unique(held_episodes):
        selected = held_episodes == episode
        episode_predictions.append(prediction[selected].mean(0))
        episode_targets.append(y[held][selected][0])
    return {
        "schema": "a2_piper_base_v27_shadow_estimator_v1", "status": "SHADOW_ESTIMATOR_REPORTED",
        "model": "ridge_linear_history_summary", "ridge": RIDGE, "window_control_steps": WINDOW,
        "stride_control_steps": WINDOW, "split_seed": SPLIT_SEED, "heldout_share_rule": "floor(groups/4)",
        "features": FEATURES, "history_summaries": ["mean","standard_deviation","last","last_minus_first"],
        "train_windows": int((~held).sum()), "heldout_windows": int(held.sum()),
        "train_episode_groups": int(len(unique) - len(held_groups)), "heldout_episode_groups": len(held_groups),
        "heldout_groups": held_groups.tolist(), "heldout_episode_count": len(episode_targets),
        "excluded_episodes_without_complete_window": excluded,
        "constant_training_columns_removed": int((~retained).sum()),
        "heldout_window_metrics": score(y[held], prediction),
        "heldout_train_mean_baseline": score(y[held], baseline),
        "heldout_equal_episode_metrics": score(np.stack(episode_targets), np.stack(episode_predictions)),
        "claim_boundary": "Offline identifiability in observed simulations only; no actor change, no real-time adaptation claim, no hardware evidence. Contact and effort inputs are simulator estimates; deployable sensor contract is not established.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(read_json(args.manifest))
    result["source_manifest"] = str(args.manifest.resolve())
    write_json(args.output, result)


if __name__ == "__main__":
    main()
