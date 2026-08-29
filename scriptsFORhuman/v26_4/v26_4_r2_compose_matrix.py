#!/usr/bin/env python3
"""Compose the four R2 training configs without importing Isaac Sim."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
CONFIG_ROOT = ROOT / "gr00t/rl/config"
CELLS = (("C0S0", "base_v26_4_C0_CANONICAL_OFF", 0), ("C0S1", "base_v26_4_C0_CANONICAL_OFF", 1), ("C1S0", "base_v26_4_C1_CANONICAL_ON", 0), ("C1S1", "base_v26_4_C1_CANONICAL_ON", 1))


def merge(base: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge(result[key], value)
        else:
            result[key] = value
    return result


def compose(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"config must be mapping: {path}")
    result: dict[str, Any] = {}
    for entry in payload.get("defaults", []):
        if not isinstance(entry, str) or entry == "_self_":
            continue
        reference = entry.removeprefix("override ").strip()
        if reference.startswith("/ablation/"):
            result = merge(result, compose(CONFIG_ROOT / f"{reference.removeprefix('/')}.yaml"))
    payload.pop("defaults", None)
    return merge(result, payload)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise RuntimeError(f"refusing to overwrite R2 static compose root: {args.output_dir}")
    args.output_dir.mkdir(parents=True)
    for name, config, seed in CELLS:
        resolved = compose(CONFIG_ROOT / f"ablation/wbmanip/{config}.yaml")
        resolved["seed"] = seed
        resolved.setdefault("env", {}).setdefault("config", {})["a2_v26_side_permutation_seed"] = seed
        resolved["v26_cell"] = f"V26_4_R2_{name}"
        (args.output_dir / f"{name}.yaml").write_text(yaml.safe_dump(resolved, sort_keys=True), encoding="utf-8")
    print(args.output_dir)


if __name__ == "__main__":
    main()
