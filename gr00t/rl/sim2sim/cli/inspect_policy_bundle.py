#!/usr/bin/env python3
"""Inspect one StudentPolicyBundle without loading Isaac, MuJoCo, or a GPU."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from gr00t.rl.sim2sim.contracts.policy_bundle import validate_bundle


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle_dir", type=Path)
    parser.add_argument("--mode", choices=("compatible", "strict"), default="compatible")
    args = parser.parse_args()
    print(json.dumps(validate_bundle(args.bundle_dir, mode=args.mode), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
