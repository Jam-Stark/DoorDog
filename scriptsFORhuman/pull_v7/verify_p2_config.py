#!/usr/bin/env python3
"""Validate one pull-v7 P2 cell's resolved config against its step9000 source.

Treatment cells must differ from the source-resolved `rewards.reward_scales`
by exactly one added key, `a2_pull_v7_arm_target_overshoot_penalty = -1.0`.
Control cells must be identical, which keeps their reward path bit-identical to
the 9000 source (zero/absent scales are removed in
legged_robot_base.py:525-531).

Run: python scriptsFORhuman/pull_v7/verify_p2_config.py RESOLVED_CONFIG CELL
     [--smoke] [--output PATH]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scriptsFORhuman/pull_v26_8"))

# Reuse the migration contract's config reader, actor/observation contract and
# fixed staged-reset ratios rather than restating them here.
from verify import ACTOR, ACTOR_OBS, CRITIC_OBS, RATIOS, read_config, require  # noqa: E402

WAVE = "logs_rl/a2_piper_pull_v26_8_backbone/pull_v26_8_backbone_20260905_natural1_r2/wave2"
D2_KEY = "a2_pull_v7_arm_target_overshoot_penalty"
D2_SCALE = -1.0
BATCHES = 10500
CELLS = {
    "T_S1": ("P_S1", 1, True),
    "T_S2": ("P_S2", 2, True),
    "C_S1": ("P_S1", 1, False),
    "C_S2": ("P_S2", 2, False),
}


def scales(cfg) -> dict[str, float]:
    return {str(key): float(scale) for key, scale in cfg["rewards"]["reward_scales"].items()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("cell", choices=sorted(CELLS))
    parser.add_argument("--smoke", action="store_true", help="256-env, <=5-batch runtime smoke budget")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    source_cell, seed, treatment = CELLS[args.cell]
    source_config = ROOT / WAVE / "train" / source_cell / "resolved_config.yaml"
    source_checkpoint = ROOT / WAVE / "train" / source_cell / "model_step_009000.pt"
    require(source_config.is_file(), f"missing source resolved config {source_config}")
    require(source_checkpoint.is_file(), f"missing source checkpoint {source_checkpoint}")

    cfg = read_config(args.config)
    source = read_config(source_config)

    cell_scales, source_scales = scales(cfg), scales(source)
    added = {key: value for key, value in cell_scales.items() if key not in source_scales}
    removed = sorted(set(source_scales) - set(cell_scales))
    changed = {
        key: (source_scales[key], cell_scales[key])
        for key in set(cell_scales) & set(source_scales)
        if cell_scales[key] != source_scales[key]
    }
    require(not removed, f"{args.cell} removed source reward scales {removed}")
    require(not changed, f"{args.cell} changed source reward scales {changed}")
    if treatment:
        require(added == {D2_KEY: D2_SCALE}, f"{args.cell} must add exactly {{{D2_KEY}: {D2_SCALE}}}, got {added}")
    else:
        require(not added, f"{args.cell} must not add reward scales, got {added}")

    require(
        Path(str(cfg["checkpoint"])).resolve() == source_checkpoint.resolve(),
        f"{args.cell} checkpoint must be {source_checkpoint}, got {cfg['checkpoint']}",
    )
    require(cfg["checkpoint_load_mode"] == "full", "checkpoint_load_mode must be full")
    require(cfg["auto_load_latest"] is False, "auto_load_latest must be false")
    require(cfg["seed"] == seed, f"{args.cell} seed must be {seed}, got {cfg['seed']}")
    require(cfg["experiment_name"] == args.cell, f"experiment_name must be {args.cell}")
    require(cfg["project_name"] == "a2_piper_pull_v7", "project_name must be a2_piper_pull_v7")

    batches = cfg["algo"]["trl"]["num_total_batches"]
    if args.smoke:
        require(cfg["num_envs"] == 256, f"smoke must use 256 envs, got {cfg['num_envs']}")
        # Full resume rejects a ceiling at or below the loaded global step, so
        # the 5-new-batch smoke ceiling is 9005.
        require(batches == 9005, f"smoke must use 5 new batches (ceiling 9005), got {batches}")
    else:
        require(cfg["num_envs"] == 1024, f"num_envs must be 1024, got {cfg['num_envs']}")
        require(batches == BATCHES, f"num_total_batches must be {BATCHES}, got {batches}")
        require(cfg["callbacks"]["model_save"]["save_frequency"] == 250, "save_frequency must be 250")
    require(cfg["algo"]["config"]["num_steps_per_env"] == 64, "64 control steps per batch")

    env = cfg["env"]["config"]
    require(env["enable_staged_reset"] is True, "enable_staged_reset must be true")
    require(env["staged_reset_ratios"] == RATIOS, f"staged_reset_ratios must be {RATIOS}, got {env['staged_reset_ratios']}")
    require(env["a2_pull_v6_stage4_bank_enabled"] is False, "v6 stage4 bank must stay off")
    require(env["a2_pull_v61_late_state_bank_enabled"] is False, "v6.1 late-state bank must stay off")
    require(env["a2_door_open_lr_distribution"] == "bilateral", "bilateral training selector")
    require(env["a2_door_open_lr_permutation_seed"] == seed, "side permutation seed")
    require(env["a2_v26_6_side_mirrored_handle_offset_enabled"] is True, "mirror switch")

    actor = cfg["algo"]["config"]["actor"]
    require(actor["_target_"] == ACTOR, "plain RecurrentActor required")
    require(actor["running_mean_std"] is True, "native updating actor RMS required")
    obs = env["obs"]
    require(obs["obs_dict"]["actor_obs"] == ACTOR_OBS, "actor observation list")
    require(obs["obs_dict"]["critic_obs"] == CRITIC_OBS, "critic observation list")
    declared = obs["obs_dims"]
    dims = declared if isinstance(declared, Mapping) else {k: v for item in declared for k, v in item.items()}
    dimensions = {
        group: sum(dims[key.removesuffix("_raw")] for key in obs["obs_dict"][group])
        for group in ("actor_obs", "critic_obs")
    }
    require(dimensions == {"actor_obs": 133, "critic_obs": 138}, f"observation dimensions {dimensions}")

    # Any other semantic drift from the source is a launch blocker; report it
    # before the run rather than discovering it in the trace.
    payload = {
        "schema": "pull_v7_p2_config_check_v1",
        "status": "CONFIG_PASS",
        "cell": args.cell,
        "source_cell": source_cell,
        "source_config": str(source_config.relative_to(ROOT)),
        "source_checkpoint": str(source_checkpoint.relative_to(ROOT)),
        "treatment": treatment,
        "added_reward_scales": added,
        "reward_scale_count": {"source": len(source_scales), "cell": len(cell_scales)},
        "num_envs": cfg["num_envs"],
        "num_total_batches": batches,
        "seed": seed,
        "dimensions": dimensions,
        "staged_reset_ratios": list(RATIOS),
        "smoke": bool(args.smoke),
    }
    output = args.output or args.config.parent / "config_check.json"
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
