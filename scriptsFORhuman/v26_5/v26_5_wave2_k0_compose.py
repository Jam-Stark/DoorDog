#!/usr/bin/env python3
"""Resolve Wave2 K0 O0A0 eval selector configs without importing Isaac Sim."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
CONFIG_ROOT = ROOT / "gr00t/rl/config"
CELLS = (("K0_CONT_STEP2000_O0A0_S0", 0), ("K0_CONT_STEP2000_O0A0_S1", 1))
SELECTOR = "ablation/wbmanip/base_v26_5_wave2_K0_eval_O0A0"


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
        if not isinstance(entry, str) or not entry.startswith("/"):
            raise RuntimeError(f"unsupported default in Wave2 K0 compose: {entry!r}")
        result = merge(result, compose(CONFIG_ROOT / f"{entry.removeprefix('/')}.yaml"))
    value.pop("defaults", None)
    return merge(result, value)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise RuntimeError(f"refusing to overwrite Wave2 K0 static compose root: {args.output_dir}")
    args.output_dir.mkdir(parents=True)
    for label, seed in CELLS:
        resolved = compose(CONFIG_ROOT / f"{SELECTOR}.yaml")
        resolved["seed"] = seed
        resolved.setdefault("env", {}).setdefault("config", {})["a2_v26_side_permutation_seed"] = seed
        resolved["v26_cell"] = f"V26_5_WAVE2_{label}"
        (args.output_dir / f"{label}.yaml").write_text(yaml.safe_dump(resolved, sort_keys=True), encoding="utf-8")
    print(args.output_dir)


if __name__ == "__main__":
    main()
