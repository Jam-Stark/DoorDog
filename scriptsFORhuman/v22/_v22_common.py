"""Shared strict contracts for base_v22 execution tools.

Every helper here fails fast.  There is no tolerant path: a missing artifact, a
hash mismatch, or an illegal GPU is an error, never a warning that lets the
round continue on unverified ground.
"""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml


V22_PLAN_ID = "base_v22_posture_clearance_force_routing_v3"
V22_EXECUTION_ID = "base_v22_execution_v3"
V22_PLAN_DOCUMENT = "scriptsFORhuman/a2_piper_base_v22_posture_clearance_force_routing_plan_R3_20260805.md"
V22_MANIFEST_DOCUMENT = "scriptsFORhuman/v22/a2_piper_base_v22_experiment_manifest_R3_20260805.yaml"
V22_CHANGE_LOG_DOCUMENT = "scriptsFORhuman/v22/a2_piper_base_v22_R3_change_log_20260805.md"

V22_SCIENTIFIC_BASE_COMMIT = "89c6538ad274ab6d1256389e3f2b3ceefd68d98a"
V22_LEGAL_PHYSICAL_GPUS = (0, 1)

V22_WARM_START_PATH = "logs_rl/a2_piper_full_stage_a2_base/base_v21B/formal/B1/model_step_000500.pt"
V22_WARM_START_SHA256 = "d2732c148dd3176abafbf3a5c9425d4a34c17b352e8362bbfb38c8ac960d8421"
V22_WARM_START_CONFIG_SHA256 = "70ccd1b43a07574d36702947c706b5ef80184fffd0d2853cf188c9286a959a79"
V22_URDF_PATH = "gr00t/rl/data/robots/A2_Piper/a2_piper.urdf"
V22_URDF_SHA256 = "d02cdacdcd4aaf1480b52ba9a6a62f5e9bbd040036a796154dbff70d1391a1d5"

V22_THETA_SEND_RAD = 0.90
V22_RELEASE_HINGE_RAD = 1.60
V22_FORMAL_ENVS = 4096
V22_FORMAL_BATCHES = 2500
V22_FORMAL_SAVE_FREQUENCY = 250
V22_RELEASE_GOAL_POOLED48 = 46

V22_ARTIFACT_ROOT = "logs_eval/base_v22"
V22_LOCK_ROOT = "logs_eval/base_v22/locks"
V22_TRAINING_ROOT = "logs_rl/a2_piper_full_stage_a2_base/base_v22"
V22_SMOKE_ROOT = "logs_rl/a2_piper_full_stage_a2_base_smoke/base_v22"
V22_LAUNCHER_ROOT = "logs_rl/launchers/base_v22"

V22_SOURCE_LOCK_FILES = (
    "gr00t/rl/envs/door/door_open_a2_base.py",
    "gr00t/rl/envs/door/a2_v22_evidence.py",
    "gr00t/rl/envs/door/a2_v21b_evidence.py",
    "gr00t/rl/envs/base_task/a2_base.py",
    "gr00t/rl/isaac_utils/playground/env_rand/door.py",
    "gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py",
    "gr00t/rl/scripts/generate_door_assets.py",
    "gr00t/rl/trl/trainer/ppo_trainer_a2_base_api.py",
    "gr00t/rl/eval_agent_trl.py",
    "gr00t/rl/train_agent_trl.py",
    "gr00t/rl/config/env/door_open_a2_base.yaml",
)

V22_WAVE1_CELLS = ("G1", "G2")
V22_WAVE2_CELLS = ("G3", "G4")
V22_WAVE3_CELLS = ("G5", "G6")
V22_CELL_CONFIGS = {
    "G1": "gr00t/rl/config/ablation/wbmanip/base_v22_G1_posture_seed0.yaml",
    "G2": "gr00t/rl/config/ablation/wbmanip/base_v22_G2_posture_seed1.yaml",
    "G3": "gr00t/rl/config/ablation/wbmanip/base_v22_G3_randomized_seed0.yaml",
    "G4": "gr00t/rl/config/ablation/wbmanip/base_v22_G4_randomized_seed1.yaml",
    "G5": "gr00t/rl/config/ablation/wbmanip/base_v22_G5_body_assist_seed0.yaml",
    "G6": "gr00t/rl/config/ablation/wbmanip/base_v22_G6_body_assist_seed1.yaml",
}
V22_CELL_GPU = {"G1": 0, "G2": 1, "G3": 0, "G4": 1, "G5": 0, "G6": 1}
V22_CELL_SEED = {"G1": 0, "G2": 1, "G3": 0, "G4": 1, "G5": 0, "G6": 1}

PYTHON_BIN = "/home/baoquanc/anaconda3/envs/isaaclab/bin/python"
V22_EXP_NAME = "wbmanip/door_open_a2_base_lstm"
V22_PROJECT_NAME = "a2_piper_full_stage_a2_base"

REPO_ROOT = Path(__file__).resolve().parents[2]


class V22Error(ValueError):
    """Fail-fast v22 contract violation."""


def canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def digest(payload: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def sha256_file(path: Path) -> str:
    target = Path(path)
    if target.is_symlink() or not target.is_file():
        raise V22Error(f"expected a regular non-symlink file: {target}")
    hasher = hashlib.sha256()
    with target.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def write_json(path: Path, payload: Mapping[str, Any]) -> str:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    raw = canonical_json_bytes(dict(payload)) + b"\n"
    target.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    target = Path(path)
    if target.is_symlink() or not target.is_file():
        raise V22Error(f"required v22 artifact is missing: {target}")
    return json.loads(target.read_text(encoding="utf-8"))


def read_yaml(path: Path) -> dict[str, Any]:
    target = Path(path)
    if target.is_symlink() or not target.is_file():
        raise V22Error(f"required v22 YAML is missing: {target}")
    loaded = yaml.safe_load(target.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise V22Error(f"v22 YAML must decode to a mapping: {target}")
    return loaded


def require_gpu(gpu: int) -> int:
    if isinstance(gpu, bool) or not isinstance(gpu, int) or gpu not in V22_LEGAL_PHYSICAL_GPUS:
        raise V22Error(
            f"v22 may only schedule physical GPU {list(V22_LEGAL_PHYSICAL_GPUS)}; got {gpu!r}. "
            "GPU2/3 are leased to pull-v0 and GPU4-7 are occupied; an idle reading is not a lease."
        )
    return gpu


def git_identity(repo_root: Path = REPO_ROOT) -> dict[str, str]:
    identity = {}
    for key, expression in (("commit", "HEAD"), ("tree", "HEAD^{tree}")):
        value = subprocess.check_output(
            ["git", "rev-parse", expression], cwd=repo_root, text=True
        ).strip()
        if len(value) != 40 or any(char not in "0123456789abcdef" for char in value):
            raise V22Error(f"v22 cannot bind to git {key}: {value!r}")
        identity[key] = value
    return identity


def quantile(values: Sequence[float], q: float) -> float:
    """Linear-interpolation quantile over an explicit finite sample."""
    if not values:
        raise V22Error("quantile requires a non-empty sample")
    if not 0.0 <= q <= 1.0:
        raise V22Error(f"quantile q must be in [0, 1]; got {q!r}")
    ordered = sorted(float(item) for item in values)
    if any(not math.isfinite(item) for item in ordered):
        raise V22Error("quantile sample contains non-finite values")
    if len(ordered) == 1:
        return ordered[0]
    position = q * (len(ordered) - 1)
    low = int(math.floor(position))
    high = int(math.ceil(position))
    if low == high:
        return ordered[low]
    return ordered[low] + (position - low) * (ordered[high] - ordered[low])


def artifact_payload(schema_suffix: str, **fields: Any) -> dict[str, Any]:
    payload = {
        "schema": f"a2_piper_base_v22_{schema_suffix}_v1",
        "plan_id": V22_PLAN_ID,
        "execution_id": V22_EXECUTION_ID,
    }
    payload.update(fields)
    return payload


__all__ = [name for name in dir() if name.startswith("V22") or name.startswith("v22")] + [
    "PYTHON_BIN",
    "REPO_ROOT",
    "V22Error",
    "artifact_payload",
    "canonical_json_bytes",
    "digest",
    "git_identity",
    "quantile",
    "read_json",
    "read_yaml",
    "require_gpu",
    "sha256_file",
    "write_json",
]
