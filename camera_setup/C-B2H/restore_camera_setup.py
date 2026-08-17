#!/usr/bin/env python3
"""Restore the archived C-B2H camera subtree and observation config."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil

from omegaconf import OmegaConf


BACKUP_DIR = Path(__file__).resolve().parent
REPO_ROOT = BACKUP_DIR.parents[1]
DEFAULT_TARGET_EXP = (
    REPO_ROOT
    / "gr00t/rl/config/exp/wbmanip/door_open_a2_base_v19_p2_b2h_toeout6_mgpu.yaml"
)
OBS_TARGET = (
    REPO_ROOT
    / "gr00t/rl/config/obs/wbmanip/door_open_a2_base_dagger_triview.yaml"
)
CAMERA_OVERLAY = BACKUP_DIR / "camera_config.yaml"
OBS_SNAPSHOT = BACKUP_DIR / "observation_contract.yaml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target-exp",
        type=Path,
        default=DEFAULT_TARGET_EXP,
        help="experiment YAML whose simulator.config.cameras subtree is replaced",
    )
    parser.add_argument(
        "--observation-target",
        type=Path,
        default=OBS_TARGET,
        help="destination for the archived three-view observation config",
    )
    return parser.parse_args()


def resolve_repo_path(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def main() -> int:
    args = parse_args()
    target_exp = resolve_repo_path(args.target_exp)
    observation_target = resolve_repo_path(args.observation_target)
    if not target_exp.is_file():
        raise FileNotFoundError(f"target experiment config not found: {target_exp}")
    if not CAMERA_OVERLAY.is_file() or not OBS_SNAPSHOT.is_file():
        raise FileNotFoundError("C-B2H backup is incomplete")

    target_config = OmegaConf.load(target_exp)
    camera_overlay = OmegaConf.load(CAMERA_OVERLAY)
    target_simulator_config = OmegaConf.select(target_config, "simulator.config")
    archived_cameras = OmegaConf.select(camera_overlay, "simulator.config.cameras")
    if target_simulator_config is None:
        raise KeyError(f"target experiment has no simulator.config: {target_exp}")
    if archived_cameras is None:
        raise KeyError(f"backup has no simulator.config.cameras: {CAMERA_OVERLAY}")

    OmegaConf.update(
        target_config,
        "simulator.config.cameras",
        archived_cameras,
        merge=False,
    )
    OmegaConf.save(target_config, target_exp)
    shutil.copyfile(OBS_SNAPSHOT, observation_target)

    print(f"restored camera config: {target_exp}")
    print(f"restored observation config: {observation_target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
