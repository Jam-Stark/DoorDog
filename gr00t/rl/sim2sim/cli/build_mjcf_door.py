"""Build one deterministic MJCF door and its three-face receipt."""

from __future__ import annotations

import argparse

from gr00t.rl.sim2sim.doors.mjcf_builder import MjcfDoorBuilder
from gr00t.rl.sim2sim.doors.spec import DoorInstanceSpec


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instance", required=True)
    parser.add_argument("--output-xml", required=True)
    parser.add_argument("--output-report", required=True)
    args = parser.parse_args()
    MjcfDoorBuilder(DoorInstanceSpec.from_path(args.instance)).write(
        args.output_xml,
        args.output_report,
    )


if __name__ == "__main__":
    main()
