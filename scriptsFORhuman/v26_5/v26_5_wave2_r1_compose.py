#!/usr/bin/env python3
"""Resolve R1 selectors with the same limited static composer as Wave1."""
from __future__ import annotations
import argparse
from pathlib import Path
from typing import Any
import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_ROOT = ROOT / "gr00t/rl/config"

def merge(base: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in update.items():
        result[key] = merge(result[key], value) if isinstance(value, dict) and isinstance(result.get(key), dict) else value
    return result

def compose(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict): raise RuntimeError(f"config is not mapping: {path}")
    result: dict[str, Any] = {}
    for entry in value.get("defaults", []):
        if entry == "_self_": continue
        if isinstance(entry, str) and entry.startswith("/"):
            result = merge(result, compose(CONFIG_ROOT / f"{entry.removeprefix('/')}.yaml"))
        elif isinstance(entry, dict) and len(entry) == 1:
            key, target = next(iter(entry.items()))
            if not isinstance(key, str) or not key.startswith("override /") or not isinstance(target, str):
                raise RuntimeError(f"unsupported R1 default: {entry!r}")
            result = merge(result, compose(CONFIG_ROOT / f"{key.removeprefix('override /')}/{target}.yaml"))
        else: raise RuntimeError(f"unsupported R1 default: {entry!r}")
    value.pop("defaults", None)
    return merge(result, value)

def main() -> None:
    p = argparse.ArgumentParser(description=__doc__); p.add_argument("--output-dir", type=Path, required=True); a = p.parse_args()
    if a.output_dir.exists(): raise RuntimeError(f"refusing to overwrite R1 static root: {a.output_dir}")
    a.output_dir.mkdir(parents=True)
    for kind, selector in (("train", "ablation/wbmanip/base_v26_5_wave2_R1_policy_residual"), ("eval", "ablation/wbmanip/base_v26_5_wave2_R1_eval_policy_residual")):
        for seed in (0, 1):
            cfg = compose(CONFIG_ROOT / f"{selector}.yaml"); cfg["seed"] = seed; cfg.setdefault("env", {}).setdefault("config", {})["a2_v26_side_permutation_seed"] = seed
            (a.output_dir / f"R1_S{seed}_{kind}.yaml").write_text(yaml.safe_dump(cfg, sort_keys=True), encoding="utf-8")
    print(a.output_dir)

if __name__ == "__main__": main()
