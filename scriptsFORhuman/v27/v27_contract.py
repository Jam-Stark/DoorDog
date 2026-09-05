"""Frozen v27 experiment declarations and paths; no runtime policy decisions."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
RUN_ID = "v27_bilateral_hardening_20260905"
HERE = ROOT / "scriptsFORhuman/v27"
PLAN = HERE / "a2_piper_base_v27_plan_20260905.md"
CONFIG = ROOT / "gr00t/rl/config/ablation/wbmanip"
RUNTIME = HERE / "runtime_logs" / RUN_ID
TRAIN = ROOT / "logs_rl/by_batch/base_v27" / RUN_ID / "train"
EVAL = ROOT / "logs_eval/base_v27" / RUN_ID
PYTHON = "/home/baoquanc/anaconda3/envs/isaaclab/bin/python"
OLD_TRAIN = ROOT / "logs_rl/by_batch/base_v26/v26_8_bilateral_opening_scaffold_decay_20260903_r3a/train"
SIDES = ("left", "right")
PROXY_KEYS = ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "no_proxy", "NO_PROXY")
SEEDS = {"DEV": 270001, "CONF": 270101, "probe": 270201, "final": 270303}
METRICS = ("D", "S3+", "S4+", "open_hold", "S5+", "complete", "clean_complete")


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def read_json(path):
    return json.loads(Path(path).read_text())


def write_json(path, value, *, replace=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w" if replace else "x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def flatten(value, prefix=""):
    result = {}
    for key, item in value.items():
        name = f"{prefix}.{key}" if prefix else key
        if isinstance(item, dict):
            result.update(flatten(item, name))
        else:
            result[name] = item
    return result


def merge(left, right):
    result = copy.deepcopy(left)
    for key, value in right.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def yaml_write(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        stream.write("# @package _global_\n")
        yaml.safe_dump(value, stream, sort_keys=False)


def cells(wave):
    if wave == "A":
        return {f"{arm}_S{seed}": {"arm": arm, "seed": seed, "gpu": gpu,
                "batches": 3000, "milestones": [500, 1000, 1500, 2000, 2500, 3000]}
                for arm, seed, gpu in (("C",21,2),("Q1",21,3),("Q2",21,4),
                                      ("C",22,5),("Q1",22,6),("Q2",22,7))}
    if wave == "B":
        return {f"{arm}_S{seed}": {"arm": arm, "seed": seed, "gpu": gpu,
                "batches": 1500 if arm.startswith("R") else 3000,
                "milestones": [500,1000,1500] if arm.startswith("R") else [1000,2000,3000]}
                for arm, seed, gpu in (("L0",31,2),("L1",31,3),("L1",32,4),
                                      ("R0",41,5),("R1",41,6),("R2",41,7))}
    if wave == "C":
        return {f"{arm}_S{seed}": {"arm": arm, "seed": seed, "gpu": gpu,
                "batches": 6000, "milestones": [1000,2000,3000,4000,5000,6000]}
                for arm, seed, gpu in (("SC",201,2),("SC",202,3),("SC",203,4),
                                      ("SK",211,5),("SK",212,6),("SK",213,7))}
    raise ValueError(wave)


def cell_contract(cell):
    for wave in ("A", "B", "C"):
        if cell in cells(wave):
            return {"wave": wave, "cell": cell, **cells(wave)[cell]}
    raise ValueError(f"unknown v27 cell {cell}")


def input_checkpoint(cell):
    return EVAL / "inputs" / cell / "model_step_003000.pt"


def train_checkpoint(cell, step):
    active_path = RUNTIME / "active_attempts.json"
    active = read_json(active_path) if active_path.exists() else {}
    directory = Path(active.get(cell, str(TRAIN / cell)))
    return directory / f"model_step_{step:06d}.pt"


def stratum_overlay(stratum):
    if stratum in ("nominal", "injected", "sham"):
        return {"env.config.a2_v26_door_weight_range": [80.0,120.0],
                "env.config.a2_v24_friction_enabled": False}
    static = {"P02": 2.0, "P05": 5.0}[stratum]
    return {"env.config.a2_v26_door_weight_range": [80.0,160.0],
            "env.config.a2_v24_friction_enabled": True,
            "env.config.a2_v24_friction_backend": "native_joint_friction_v1",
            "env.config.a2_v24_friction_static_effort": static,
            "env.config.a2_v24_friction_dynamic_effort": 0.75 * static,
            "env.config.a2_v24_friction_viscous_coefficient": 0.0}
