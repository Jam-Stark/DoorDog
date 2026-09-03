#!/usr/bin/env python3
"""Adjudicate the bounded v26-8 K_S1 wiring smoke without inferring decay."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import yaml


SOURCE = "logs_rl/by_batch/base_v26/v26_7_bilateral_native_unlatch_20260902/train/Q05_S1/model_step_003000.pt"

def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), f"refusing to overwrite G1 result: {args.output}")
    output = args.root / "K_S1_smoke"
    trace_path = output / "a2_v26_8_penalty_curriculum_trace.jsonl"
    receipt_path = output / "v26_8_policy_load_receipt.json"
    config_path = output / "resolved_config.yaml"
    for path in (trace_path, receipt_path, config_path):
        require(path.is_file(), f"missing G1 artifact: {path}")
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    env, rewards = config["env"]["config"], config["rewards"]
    require(config.get("checkpoint") == SOURCE and config.get("checkpoint_load_mode") == "policy_only" and config.get("policy_only_load_actor_rms") is True and config.get("auto_load_latest") is False, "G1 source/load contract")
    require(config.get("num_envs") == 64 and config["algo"]["trl"]["num_total_batches"] == 5 and env.get("enable_staged_reset") is True, "G1 bounded staged-reset contract")
    require(rewards.get("reward_penalty_curriculum") is True and env.get("a2_v26_8_penalty_driver") == "side_min_natural_stage_reach_rate", "G1 K driver contract")
    rows = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines() if line]
    require(rows, "G1 curriculum trace is empty")
    required = {"update_index", "common_step", "scale_before", "scale_after", "driver_left", "driver_right", "natural_sample_left", "natural_sample_right", "skipped"}
    first_natural = False
    for index, row in enumerate(rows):
        require(isinstance(row, dict) and required <= set(row), f"trace row {index} schema")
        require(isinstance(row["update_index"], int) and isinstance(row["common_step"], int), f"trace row {index} indexes")
        for key in ("scale_before", "scale_after"):
            require(isinstance(row[key], (int, float)) and math.isfinite(float(row[key])), f"trace row {index} {key}")
        for key in ("driver_left", "driver_right"):
            require(row[key] is None or (isinstance(row[key], (int, float)) and math.isfinite(float(row[key]))), f"trace row {index} {key}")
        for key in ("natural_sample_left", "natural_sample_right"):
            require(isinstance(row[key], int) and row[key] >= 0, f"trace row {index} {key}")
        require(isinstance(row["skipped"], bool), f"trace row {index} skipped")
        require(float(row["scale_after"]) == 1.0, f"G1 scale changed at trace row {index}")
        first_natural |= row["natural_sample_left"] > 0 and row["natural_sample_right"] > 0
    require(first_natural, "G1 never observed natural samples on both sides")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    require(receipt.get("status") == "POLICY_LOAD_CONFIRMED" and receipt.get("checkpoint_load_mode") == "policy_only" and receipt.get("actor_rms_loaded") is True and receipt.get("strict") is True and receipt.get("state_key") == "policy_state_dict", "G1 policy-only runtime receipt")
    train_log = output / "train_runtime.log"
    require(train_log.is_file(), f"missing G1 train log: {train_log}")
    log_text = train_log.read_text(encoding="utf-8")
    for key in ("reward_penalty_scale", "a2_v26_8_penalty_driver_left", "a2_v26_8_penalty_driver_right", "a2_v26_8_penalty_driver_min"):
        require(key in log_text, f"G1 train log missing Env telemetry: {key}")
    payload = {"schema": "a2_piper_base_v26_8_g1_wiring_v1", "status": "G1_PASS", "contract": {"num_envs": 64, "max_train_batches": 5, "cell": "K_S1", "scale_after": 1.0}, "trace": {"path": str(trace_path), "rows": len(rows), "natural_both_sides_observed": first_natural}, "load_receipt": str(receipt_path)}
    args.output.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], "output": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
