#!/usr/bin/env python3
"""Reference exporter for a checkpoint-adjacent StudentPolicyBundle."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from gr00t.rl.sim2sim.contracts.policy_bundle import export_reference_bundle, validate_bundle


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--resolved-config", required=True, type=Path)
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--actor-state-dict", type=Path)
    parser.add_argument("--native-loader-receipt", type=Path)
    parser.add_argument("--golden-dir", type=Path)
    args = parser.parse_args()
    receipt = export_reference_bundle(
        config_path=args.resolved_config,
        checkpoint_path=args.checkpoint,
        output_dir=args.output_dir,
        actor_state_dict=args.actor_state_dict,
        native_loader_receipt=args.native_loader_receipt,
        golden_dir=args.golden_dir,
    )
    validation = validate_bundle(args.output_dir, mode="compatible")
    print(json.dumps({"export_receipt": receipt, "validation": validation}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
