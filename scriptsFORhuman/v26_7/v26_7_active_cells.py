#!/usr/bin/env python3
"""Read frozen v26-7 early-success endpoints before a later milestone."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

STEPS = (1000, 2000, 3000, 4000, 5000, 6000)
CONFIGS = ("Q05", "Q20")


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--milestones-root", type=Path, required=True)
    parser.add_argument("--next-step", type=int, choices=STEPS, required=True)
    args = parser.parse_args()
    endpoints = {config: None for config in CONFIGS}
    stop_all = False
    for step in STEPS:
        if step >= args.next_step:
            break
        path = args.milestones_root / f"step{step}" / "reducer.json"
        require(path.is_file(), f"missing required preceding milestone reducer: {path}")
        reducer = json.loads(path.read_text(encoding="utf-8"))
        require(reducer.get("schema") == "a2_piper_base_v26_7_milestone_reducer_v1" and reducer.get("step") == step, f"invalid preceding reducer: {path}")
        require(reducer.get("status") == "EXPERIMENT_COMPLETE", f"preceding milestone is not complete: {path}")
        stop_all |= reducer.get("stop_all_training") is True
        stored = reducer.get("config_endpoints")
        require(isinstance(stored, dict) and set(stored) == set(CONFIGS), f"preceding endpoint state missing: {path}")
        for config in CONFIGS:
            endpoint = stored[config]
            if endpoint is None:
                continue
            require(isinstance(endpoint, dict) and endpoint.get("config") == config and endpoint.get("outcome") == "BILATERAL_UNLATCH_SUPPORTED" and endpoint.get("step") in STEPS and endpoint["step"] <= step, f"invalid frozen endpoint: {path} {config}")
            if endpoints[config] is None:
                endpoints[config] = endpoint
            else:
                require(endpoints[config] == endpoint, f"endpoint changed after freeze: {config}")
    active = [] if stop_all else [f"{config}_S{seed}" for config in CONFIGS if endpoints[config] is None for seed in range(3)]
    payload = {"schema": "a2_piper_base_v26_7_active_cells_v1", "next_step": args.next_step, "stop_all_training": stop_all, "config_endpoints": endpoints, "active_cells": active, "status": "NO_ACTIVE" if not active else "ACTIVE"}
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
