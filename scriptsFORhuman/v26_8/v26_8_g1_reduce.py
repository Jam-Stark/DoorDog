#!/usr/bin/env python3
"""Adjudicate the bounded v26-8 K_S1 wiring smoke without inferring decay."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import torch
import yaml


SOURCE = "logs_rl/by_batch/base_v26/v26_7_bilateral_native_unlatch_20260902/train/Q05_S1/model_step_003000.pt"
PLAN = Path(__file__).with_name(
    "a2_piper_base_v26_8_bilateral_opening_scaffold_decay_plan_20260903.md"
)

def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def validate_trace(rows: list[dict], rewards: dict, env: dict) -> dict:
    required = {
        "update_index",
        "common_step",
        "scale_before",
        "scale_after",
        "driver_left",
        "driver_right",
        "natural_sample_left",
        "natural_sample_right",
        "natural_reached_left",
        "natural_reached_right",
        "consumed",
        "skipped",
    }
    degree = float(rewards["reward_penalty_degree"])
    minimum = float(rewards["reward_min_penalty_scale"])
    maximum = float(rewards["reward_max_penalty_scale"])
    level_down = float(env["a2_v26_8_penalty_driver_level_down_rate"])
    level_up = float(env["a2_v26_8_penalty_driver_level_up_rate"])
    previous_after = float(rewards["reward_initial_penalty_scale"])
    previous_common_step = -1
    previous_counts: list[int] | None = None
    previous_reached: list[int] | None = None
    previous_consumed = False
    consumed_rows = 0
    scales: list[float] = []
    first_bilateral_consumption = None
    first_scale_change = None

    for index, row in enumerate(rows):
        require(isinstance(row, dict) and required <= set(row), f"trace row {index} schema")
        require(
            isinstance(row["update_index"], int)
            and not isinstance(row["update_index"], bool)
            and row["update_index"] == index,
            f"trace row {index} update index",
        )
        require(
            isinstance(row["common_step"], int)
            and not isinstance(row["common_step"], bool)
            and row["common_step"] >= 0
            and row["common_step"] >= previous_common_step,
            f"trace row {index} common step",
        )
        previous_common_step = row["common_step"]
        for key in ("scale_before", "scale_after"):
            require(
                isinstance(row[key], (int, float)) and math.isfinite(float(row[key])),
                f"trace row {index} {key}",
            )
        before = float(row["scale_before"])
        after = float(row["scale_after"])
        require(before == previous_after, f"trace row {index} scale continuity")

        counts = [row["natural_sample_left"], row["natural_sample_right"]]
        reached = [row["natural_reached_left"], row["natural_reached_right"]]
        rates: list[float | None] = []
        for side_index, side_name in enumerate(("left", "right")):
            require(
                isinstance(counts[side_index], int)
                and not isinstance(counts[side_index], bool)
                and counts[side_index] >= 0,
                f"trace row {index} natural_sample_{side_name}",
            )
            require(
                isinstance(reached[side_index], int)
                and not isinstance(reached[side_index], bool)
                and 0 <= reached[side_index] <= counts[side_index],
                f"trace row {index} natural_reached_{side_name}",
            )
            rate = None if counts[side_index] == 0 else reached[side_index] / counts[side_index]
            rates.append(rate)
            require(
                row[f"driver_{side_name}"] == rate,
                f"trace row {index} driver_{side_name}",
            )

        if previous_counts is not None and not previous_consumed:
            for side_index, side_name in enumerate(("left", "right")):
                require(
                    counts[side_index] >= previous_counts[side_index]
                    and reached[side_index] >= previous_reached[side_index],
                    f"trace row {index} discarded pending {side_name} evidence after skip",
                )

        skipped = any(rate is None for rate in rates)
        require(row["skipped"] is skipped, f"trace row {index} skipped semantics")
        require(row["consumed"] is (not skipped), f"trace row {index} consumed semantics")
        expected = torch.tensor(before, dtype=torch.float32)
        if not skipped:
            driver = min(rates)
            if driver > level_up:
                expected *= 1.0 + degree
            elif driver < level_down:
                expected *= 1.0 - degree
            expected = torch.clip(expected, minimum, maximum)
            consumed_rows += 1
            if first_bilateral_consumption is None:
                first_bilateral_consumption = {
                    "update_index": index,
                    "common_step": row["common_step"],
                }
        require(after == float(expected.item()), f"trace row {index} scale transition")
        require(minimum <= after <= maximum, f"trace row {index} clipped scale")
        if after != before and first_scale_change is None:
            first_scale_change = {
                "update_index": index,
                "common_step": row["common_step"],
                "scale_before": before,
                "scale_after": after,
            }
        previous_after = after
        previous_counts = counts
        previous_reached = reached
        previous_consumed = not skipped
        scales.append(after)

    require(consumed_rows > 0, "G1 never consumed a bilateral pending window")
    return {
        "rows": len(rows),
        "consumed_rows": consumed_rows,
        "skipped_rows": len(rows) - consumed_rows,
        "scale_min": min(scales),
        "scale_max": max(scales),
        "final_scale": scales[-1],
        "first_bilateral_consumption": first_bilateral_consumption,
        "first_scale_change": first_scale_change,
        "float_transition_check": "exact_torch_float32",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--readjudication", action="store_true")
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
    require(
        rewards.get("reward_initial_penalty_scale") == 1.0
        and rewards.get("reward_min_penalty_scale") == 0.2
        and rewards.get("reward_max_penalty_scale") == 1.0
        and rewards.get("reward_penalty_degree") == -0.0001
        and env.get("a2_v26_8_penalty_driver_level_down_rate") == 0.5
        and env.get("a2_v26_8_penalty_driver_level_up_rate") == 0.7,
        "G1 scale transition contract",
    )
    require(env.get("a2_v26_8_penalty_driver_target_stage") == 4, "G1 driver target stage")
    rows = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines() if line]
    require(rows, "G1 curriculum trace is empty")
    trace_summary = validate_trace(rows, rewards, env)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    require(receipt.get("status") == "POLICY_LOAD_CONFIRMED" and receipt.get("checkpoint_load_mode") == "policy_only" and receipt.get("actor_rms_loaded") is True and receipt.get("strict") is True and receipt.get("state_key") == "policy_state_dict", "G1 policy-only runtime receipt")
    train_log = output / "train_runtime.log"
    require(train_log.is_file(), f"missing G1 train log: {train_log}")
    log_text = train_log.read_text(encoding="utf-8")
    for key in ("reward_penalty_scale", "a2_v26_8_penalty_driver_left", "a2_v26_8_penalty_driver_right", "a2_v26_8_penalty_driver_min"):
        require(key in log_text, f"G1 train log missing Env telemetry: {key}")
    payload = {
        "schema": "a2_piper_base_v26_8_g1_wiring_v2",
        "status": "G1_READJUDICATION_PASS" if args.readjudication else "G1_PASS",
        "contract": {
            "num_envs": 64,
            "max_train_batches": 5,
            "cell": "K_S1",
            "scale_transition": "exact frozen driver/hysteresis/float32/clip",
        },
        "trace": {"path": str(trace_path), **trace_summary},
        "load_receipt": str(receipt_path),
        "runtime_plan_sha256": receipt.get("plan_sha256"),
        "adjudication_plan_sha256": hashlib.sha256(PLAN.read_bytes()).hexdigest(),
        "adjudication": (
            "immutable G1 r3 artifact; plan section 15 reducer-only readjudication"
            if args.readjudication
            else "direct G1 wiring adjudication"
        ),
    }
    args.output.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], "output": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
