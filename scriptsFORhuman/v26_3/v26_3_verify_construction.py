#!/usr/bin/env python3
"""Validate v26-3 natural, staged-reset, and post-diagnostic PPO construction evidence."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import yaml


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--natural-root", type=Path, required=True)
    parser.add_argument("--staged-root", type=Path, required=True)
    parser.add_argument("--post-smoke-root", type=Path, required=True)
    parser.add_argument("--post-smoke-log", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    args = parse_args()
    natural = {}
    for side in ("left", "right"):
        side_root = args.natural_root / side
        for filename in (
            "metrics_eval.json",
            "a2_v14_per_env_records.json",
            "stage2_5_step_trace.json",
            "a2_eval_diagnostic_metadata.json",
        ):
            require((side_root / filename).is_file(), f"natural {side} missing {filename}")
        metrics = json.loads((side_root / "metrics_eval.json").read_text(encoding="utf-8"))
        terminal = metrics.get("episode_terminal_diagnostics")
        require(isinstance(terminal, list) and len(terminal) == 1, f"natural {side} is not exact1")
        v3 = terminal[0].get("v26_3")
        require(isinstance(v3, dict) and v3.get("state_initialized") is True, f"natural {side} creation state invalid")
        require(v3.get("integrity_violations") == 0, f"natural {side} integrity failed")
        natural[side] = {
            "trace_rows": len(json.loads((side_root / "stage2_5_step_trace.json").read_text(encoding="utf-8"))),
            "creation_integrity_violations": 0,
            "state_initialized": True,
        }

    staged_checkpoint = args.staged_root / "model_step_000012.pt"
    require(staged_checkpoint.is_file(), "staged-reset retry checkpoint is missing")
    staged_cfg = yaml.safe_load((args.staged_root / "resolved_config.yaml").read_text(encoding="utf-8"))
    require(staged_cfg.get("num_envs") == 64, "staged-reset smoke is not 64 env")
    require(staged_cfg["env"]["config"].get("a2_v26_3_telemetry_enabled") is True, "staged-reset v26-3 telemetry is disabled")

    post_checkpoint = args.post_smoke_root / "model_step_000012.pt"
    require(post_checkpoint.is_file(), "post-diagnostic M1 PPO checkpoint is missing")
    post_cfg = yaml.safe_load((args.post_smoke_root / "resolved_config.yaml").read_text(encoding="utf-8"))
    require(post_cfg.get("num_envs") == 64, "post-diagnostic smoke is not 64 env")
    require(post_cfg["rewards"]["reward_scales"].get("a2_stage3_handle_depression") == 0.0, "post-diagnostic smoke retained old reward")
    require(post_cfg["rewards"]["reward_scales"].get("a2_stage3_handle_creation") == 6.0, "post-diagnostic smoke creation reward is not scale6")
    log = args.post_smoke_log.read_text(encoding="utf-8", errors="replace")
    require("Saved model checkpoint" in log, "post-diagnostic smoke log has no checkpoint save")
    require("Learning iteration" in log, "post-diagnostic smoke log has no PPO update")
    counters = {}
    for name in (
        "a2_v26_3_staged_store_count_total",
        "a2_v26_3_staged_load_count_total",
        "a2_v26_3_staged_restore_cache_clear_count_total",
    ):
        values = [float(value) for value in re.findall(rf"{name}:\s*([0-9]+(?:\.[0-9]+)?)", log)]
        counters[name] = max(values) if values else None
    require(counters["a2_v26_3_staged_store_count_total"] not in (None, 0.0), "post smoke did not observe staged stores")
    require(counters["a2_v26_3_staged_load_count_total"] not in (None, 0.0), "post smoke did not observe staged loads")
    require(counters["a2_v26_3_staged_restore_cache_clear_count_total"] not in (None, 0.0), "post smoke did not observe restore cache clears")

    payload = {
        "schema": "a2_piper_base_v26_3_construction_v1",
        "status": "RUNTIME_PASS",
        "natural_exact1": natural,
        "staged_reset": {
            "checkpoint": str(staged_checkpoint),
            "snapshot_state_registered": True,
            "restore_cache_clear_contract": True,
            "telemetry_counters_observed_in_post_smoke_log": counters,
        },
        "post_diagnostic_m1_smoke": {
            "num_envs": 64,
            "ppo_update": True,
            "checkpoint": str(post_checkpoint),
            "old_reward_scale": 0.0,
            "creation_reward_scale": 6.0,
        },
        "preserved_failed_attempts": [
            "construction/natural_1env",
            "construction/staged_smoke",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
