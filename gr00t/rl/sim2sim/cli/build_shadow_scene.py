#!/usr/bin/env python3
"""Compose the independent A2+Piper and door artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path

from gr00t.rl.sim2sim.mujoco.scene_builder import ShadowSceneBuilder


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--robot", required=True, type=Path)
    parser.add_argument("--door", required=True, type=Path)
    parser.add_argument("--output-scene", required=True, type=Path)
    parser.add_argument("--output-report", required=True, type=Path)
    args = parser.parse_args()
    ShadowSceneBuilder(args.robot, args.door).write(args.output_scene, args.output_report)


if __name__ == "__main__":
    main()
