"""Small, fail-fast contracts shared by the base_v23 preparation tools.

The v23 preparation layer deliberately records identity as the current git
commit plus readable source/config paths.  It does not create content digests,
large workflow ceremony, or simulation side effects.  Numerical P0 decisions
are represented as pending until a measured input is supplied.
"""

from __future__ import annotations

import json
import math
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]

V23_PLAN_ID = "base_v23_force_feasibility_initialization_posture_R1"
V23_PLAN_DOCUMENT = "scriptsFORhuman/v23/a2_piper_base_v23_plan_R1_20260809.md"
V23_ARTIFACT_ROOT = "logs_eval/base_v23"
V23_TRAINING_ROOT = "logs_rl/a2_piper_full_stage_a2_base/base_v23"
V23_LAUNCHER_ROOT = "logs_rl/launchers/base_v23"

V23_WARM_START_PATH = (
    "logs_rl/a2_piper_full_stage_a2_base/base_v22/G1/model_step_001250.pt"
)
V23_WARM_START_CONFIG = (
    "logs_rl/a2_piper_full_stage_a2_base/base_v22/G1/config.yaml"
)
V23_D0_SOURCE_CONFIG = "gr00t/rl/config/ablation/wbmanip/base_v22_G1_posture_seed0.yaml"
V23_D0_SOURCE_RESOLVED_CONFIG = V23_WARM_START_CONFIG

V23_FORMAL_ENVS = 4096
V23_FORMAL_BATCHES = 2500
V23_SAVE_FREQUENCY = 250
V23_CANONICAL_EPISODES = 16
V23_POOLED_EPISODES = 48
V23_HOLDOUT_EPISODES = 64
V23_ROUTE_A_STEPS = tuple(range(250, 2501, 250))
V23_EFFORT_RUNGS = (100.0, 60.0, 40.0, 30.0, 25.0, 20.0)
V23_LEGAL_PHYSICAL_GPUS = (0, 1, 2, 3)
V23_RP0_MASK_INDICES = (3, 4)
V23_RP0_NEUTRAL_VALUE = 0.0

V23_GPU_SUBWAVES = {
    "A1": {"seed": 0, "cells": ("G1", "G3", "G5", "G7"), "gpus": (0, 1, 2, 3)},
    "A2": {"seed": 0, "cells": ("G2", "G4", "G6", "G8"), "gpus": (0, 1, 2, 3)},
    "B1": {"seed": 1, "cells": ("G1", "G3", "G5", "G7"), "gpus": (0, 1, 2, 3)},
    "B2": {"seed": 1, "cells": ("G2", "G4", "G6", "G8"), "gpus": (0, 1, 2, 3)},
}

V23_CELL_FACTORS = {
    "G1": {"initialization": "v22_warm", "door_regime": "D0", "posture": "FULL"},
    "G2": {"initialization": "v22_warm", "door_regime": "D0", "posture": "RP0"},
    "G3": {"initialization": "scratch", "door_regime": "D0", "posture": "FULL"},
    "G4": {"initialization": "scratch", "door_regime": "D0", "posture": "RP0"},
    "G5": {"initialization": "v22_warm", "door_regime": "D1", "posture": "FULL"},
    "G6": {"initialization": "v22_warm", "door_regime": "D1", "posture": "RP0"},
    "G7": {"initialization": "scratch", "door_regime": "D1", "posture": "FULL"},
    "G8": {"initialization": "scratch", "door_regime": "D1", "posture": "RP0"},
}

V23_INTERVENTION_MODES = (
    "FULL",
    "ACUTE_RP0",
    "BASE0_AT_GRASP",
    "HIGHER_EFFORT_RESCUE",
    "ORACLE_TANGENTIAL_ASSIST",
)

# These are source-derived facts, not calibrated P0 results.  The resolved G1
# file supplies the mass range.  The other values remain labeled as inherited
# defaults until the source-lock reader verifies them.
V23_D0_SOURCE_FACTS = {
    "door_weight_kg": {"value": [80.0, 160.0], "authority": "G1_SAVED_CONFIG"},
    "handle_height_m": {
        "value": [0.85, 1.0],
        "authority": "INHERITED_SOURCE_DEFAULT",
    },
    "hinge_max_force_nm": {
        "value": [2.5, 4.5],
        "authority": "INHERITED_SOURCE_DEFAULT",
    },
    "hinge_damping_native": {
        "value": 50.0,
        "authority": "INHERITED_SOURCE_DEFAULT",
    },
    "hinge_stiffness_native": {
        "value": [1.0, 10.0],
        "authority": "INHERITED_SOURCE_DEFAULT",
    },
}

V23_ARTIFACT_PATHS = {
    "source": "logs_eval/base_v23/p0/source_lock.json",
    "effort": "logs_eval/base_v23/p0/effort_ladder/effort_profile.json",
    "kp_clip": "logs_eval/base_v23/p0/kp_clip/kp_clip_audit.json",
    "atlas": "logs_eval/base_v23/p0/door_atlas/door_atlas.json",
    "certificate": "logs_eval/base_v23/p0/feasibility/feasibility_certificate.json",
    "state_bank": "logs_eval/base_v23/p0/state_bank/state_bank_plan.json",
    "reward": "logs_eval/base_v23/p0/reward/stationary_rent_audit.json",
}


class V23Error(ValueError):
    """A v23 preparation input is missing or inconsistent."""


def now_hkt() -> str:
    """Return a stable human-readable timestamp in the project timezone."""

    hkt = timezone(timedelta(hours=8), name="HKT")
    return datetime.now(timezone.utc).astimezone(hkt).isoformat(timespec="seconds")


def finite_number(value: Any, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise V23Error(f"{name} must be a finite number; got {value!r}")
    result = float(value)
    if not math.isfinite(result):
        raise V23Error(f"{name} must be finite; got {value!r}")
    return result


def finite_sequence(values: Sequence[Any], *, name: str) -> list[float]:
    if isinstance(values, (str, bytes)):
        raise V23Error(f"{name} must be a numeric sequence")
    return [finite_number(item, name=f"{name}[{index}]") for index, item in enumerate(values)]


def require_file(relative_path: str | Path, *, label: str | None = None) -> Path:
    path = Path(relative_path)
    if not path.is_absolute():
        path = REPO_ROOT / path
    if path.is_symlink() or not path.is_file():
        display = label or "required source"
        raise V23Error(f"{display} is not a regular file: {path}")
    return path


def git_commit(repo_root: Path = REPO_ROOT) -> str:
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "--verify", "HEAD"],
            cwd=repo_root,
            text=True,
            stderr=subprocess.STDOUT,
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise V23Error("v23 source identity requires a readable git commit") from exc
    if not commit:
        raise V23Error("v23 source identity returned an empty git commit")
    return commit


def source_identity(paths: Sequence[str | Path], *, repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    readable = []
    for raw_path in paths:
        path = require_file(raw_path)
        try:
            relative = path.relative_to(repo_root).as_posix()
        except ValueError:
            relative = str(path)
        readable.append(relative)
    return {"git_commit": git_commit(repo_root), "source_paths": readable}


def read_json(path: str | Path) -> dict[str, Any]:
    target = require_file(path)
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise V23Error(f"invalid JSON input: {target}") from exc
    if not isinstance(value, dict):
        raise V23Error(f"JSON input must be an object: {target}")
    return value


def read_yaml(path: str | Path) -> dict[str, Any]:
    target = require_file(path)
    try:
        import yaml

        value = yaml.safe_load(target.read_text(encoding="utf-8"))
    except ImportError as exc:
        raise V23Error("YAML parsing requires PyYAML") from exc
    except yaml.YAMLError as exc:
        raise V23Error(f"invalid YAML input: {target}") from exc
    if not isinstance(value, dict):
        raise V23Error(f"YAML input must be an object: {target}")
    return value


def write_json(path: str | Path, payload: Mapping[str, Any], *, overwrite: bool = False) -> Path:
    target = Path(path)
    if not target.is_absolute():
        target = REPO_ROOT / target
    if target.exists() and not overwrite:
        raise V23Error(f"refusing to overwrite existing v23 artifact: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(dict(payload), ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    return target


def emit_payload(payload: Mapping[str, Any], output: str | Path | None = None) -> None:
    if output is None:
        print(json.dumps(dict(payload), ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))
    else:
        target = write_json(output, payload)
        print(json.dumps({"status": "WRITTEN", "path": str(target)}, indent=2))


def freeze_status(path: str | Path) -> str:
    target = Path(path)
    if not target.is_absolute():
        target = REPO_ROOT / target
    if not target.is_file():
        return "MISSING"
    payload = read_json(target)
    status = payload.get("status")
    if not isinstance(status, str) or not status:
        raise V23Error(f"freeze record has no status: {target}")
    return status


def require_freezes(paths: Sequence[str | Path]) -> None:
    missing = []
    non_pass = []
    for path in paths:
        target = Path(path)
        if not target.is_absolute():
            target = REPO_ROOT / target
        if not target.is_file():
            missing.append(str(target))
            continue
        state = freeze_status(target)
        if state != "PASS":
            non_pass.append(f"{target}={state}")
    if missing or non_pass:
        parts = []
        if missing:
            parts.append("missing=" + ",".join(missing))
        if non_pass:
            parts.append("not_pass=" + ",".join(non_pass))
        raise V23Error("required v23 P0 freezes are unavailable: " + "; ".join(parts))


def artifact_payload(node: str, **fields: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema": f"a2_piper_v23_{node}_v1",
        "plan_id": V23_PLAN_ID,
        "recorded_at_hkt": now_hkt(),
    }
    payload.update(fields)
    return payload


def validate_cell(cell: str) -> str:
    if cell not in V23_CELL_FACTORS:
        raise V23Error(f"unknown v23 cell: {cell!r}")
    return cell


__all__ = [
    "REPO_ROOT",
    "V23_ARTIFACT_PATHS",
    "V23_ARTIFACT_ROOT",
    "V23_CANONICAL_EPISODES",
    "V23_CELL_FACTORS",
    "V23_D0_SOURCE_CONFIG",
    "V23_D0_SOURCE_FACTS",
    "V23_D0_SOURCE_RESOLVED_CONFIG",
    "V23_EFFORT_RUNGS",
    "V23_FORMAL_BATCHES",
    "V23_FORMAL_ENVS",
    "V23_GPU_SUBWAVES",
    "V23_HOLDOUT_EPISODES",
    "V23_INTERVENTION_MODES",
    "V23_LEGAL_PHYSICAL_GPUS",
    "V23_PLAN_DOCUMENT",
    "V23_PLAN_ID",
    "V23_POOLED_EPISODES",
    "V23_ROUTE_A_STEPS",
    "V23_RP0_MASK_INDICES",
    "V23_RP0_NEUTRAL_VALUE",
    "V23_SAVE_FREQUENCY",
    "V23_TRAINING_ROOT",
    "V23_WARM_START_CONFIG",
    "V23_WARM_START_PATH",
    "V23Error",
    "artifact_payload",
    "emit_payload",
    "finite_number",
    "finite_sequence",
    "freeze_status",
    "git_commit",
    "now_hkt",
    "read_json",
    "read_yaml",
    "require_file",
    "require_freezes",
    "source_identity",
    "validate_cell",
    "write_json",
]
