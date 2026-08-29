#!/usr/bin/env python3
"""Resolve the four Wave1 training configs without importing Isaac Sim."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
CONFIG_ROOT = ROOT / "gr00t/rl/config"
CELLS = (("O1A0_S0", "base_v26_5_O1A0_geometry", 0), ("O1A0_S1", "base_v26_5_O1A0_geometry", 1), ("O1A1_S0", "base_v26_5_O1A1_geometry_rebase", 0), ("O1A1_S1", "base_v26_5_O1A1_geometry_rebase", 1))


def merge(base: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in update.items():
        result[key] = merge(result[key], value) if isinstance(value, dict) and isinstance(result.get(key), dict) else value
    return result


def compose(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"config is not mapping: {path}")
    result: dict[str, Any] = {}
    for entry in value.get("defaults", []):
        if entry == "_self_":
            continue
        if isinstance(entry, str):
            if not entry.startswith("/"):
                raise RuntimeError(f"unsupported string default in Wave1 compose: {entry!r}")
            reference = entry.removeprefix("/")
        elif isinstance(entry, dict) and len(entry) == 1:
            group, reference = next(iter(entry.items()))
            if not isinstance(group, str) or not isinstance(reference, str):
                raise RuntimeError(f"unsupported group default in Wave1 compose: {entry!r}")
            reference = f"{group.removeprefix('override ').strip().removeprefix('/')}/{reference}"
        else:
            raise RuntimeError(f"unsupported default in Wave1 compose: {entry!r}")
        result = merge(result, compose(CONFIG_ROOT / f"{reference}.yaml"))
    value.pop("defaults", None)
    return merge(result, value)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise RuntimeError(f"refusing to overwrite static compose root: {args.output_dir}")
    args.output_dir.mkdir(parents=True)
    for label, config, seed in CELLS:
        resolved = compose(CONFIG_ROOT / f"ablation/wbmanip/{config}.yaml")
        resolved["seed"] = seed
        resolved.setdefault("env", {}).setdefault("config", {})["a2_v26_side_permutation_seed"] = seed
        resolved["v26_cell"] = f"V26_5_{label}"
        (args.output_dir / f"{label}.yaml").write_text(yaml.safe_dump(resolved, sort_keys=True), encoding="utf-8")
    print(args.output_dir)


if __name__ == "__main__":
    main()
