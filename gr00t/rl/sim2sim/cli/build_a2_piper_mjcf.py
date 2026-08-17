#!/usr/bin/env python3
"""Build the floating-base A2+Piper MuJoCo artifact and receipts."""

from __future__ import annotations

import argparse
from pathlib import Path

from gr00t.rl.sim2sim.robot.mjcf_builder import A2PiperMjcfBuilder


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--urdf", required=True, type=Path)
    parser.add_argument("--bundle-dir", required=True, type=Path)
    parser.add_argument("--output-xml", required=True, type=Path)
    parser.add_argument("--output-contract", required=True, type=Path)
    parser.add_argument("--output-report", required=True, type=Path)
    args = parser.parse_args()
    A2PiperMjcfBuilder(args.urdf, args.bundle_dir).write(
        args.output_xml, args.output_contract, args.output_report
    )


if __name__ == "__main__":
    main()
