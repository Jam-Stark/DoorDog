#!/usr/bin/env python3
"""Build the single env14 deterministic late-state-bank capture command; default is print-only."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scriptsFORhuman/pull_v6_1/run_pull_v6_1.py"
DEFAULT_BANK = ROOT / "logs_rl/a2_piper_pull_v6_1/late_state_bank/pull_v6_1_late_state_bank.pt"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gpu", type=int, choices=(0, 1, 2, 3), required=True)
    parser.add_argument("--label", default="q4_env14_late_bank_capture")
    parser.add_argument("--bank-path", type=Path, default=DEFAULT_BANK)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    if args.bank_path.exists():
        raise FileExistsError(f"refusing to overwrite late-state bank: {args.bank_path}")
    command = [
        sys.executable, str(RUNNER), "capture", "--gpu", str(args.gpu), "--label", args.label,
        "--num-envs", "16", "--seed", "3", "--bank-path", str(args.bank_path),
    ]
    if args.run:
        command.append("--run")
    print("[pull-v6.1 capture]", " ".join(command))
    return subprocess.run(command, cwd=ROOT, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
