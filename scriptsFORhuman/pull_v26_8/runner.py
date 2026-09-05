#!/usr/bin/env python3
"""Run one Isaac command and reject a zero exit without its declared artifacts."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--required", action="append", default=[])
    parser.add_argument("--gpu", type=int, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command and args.command[0] == "--" else args.command
    if not command:
        raise SystemExit("runner requires a command after --")

    started = datetime.now(timezone.utc).isoformat()
    memory_path = args.output / "gpu_memory.csv"
    policy_readings_observed = False
    with memory_path.open("x", encoding="utf-8") as memory_log, (args.output / "isaac.log").open("x", encoding="utf-8") as isaac_log:
        monitor = subprocess.Popen([
            "nvidia-smi", f"--id={args.gpu}", "--query-gpu=memory.used,memory.total",
            "--format=csv,noheader,nounits", "--loop-ms=200",
        ], stdout=memory_log, stderr=subprocess.STDOUT)
        try:
            child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            for line in child.stdout:
                isaac_log.write(line)
                isaac_log.flush()
                sys.stdout.write(line)
                sys.stdout.flush()
                policy_readings_observed |= re.search(r"Learning iteration [1-9][0-9]*", line) is not None
            child_returncode = child.wait()
        finally:
            monitor.terminate()
            monitor.wait()
    samples = [[int(value.strip()) for value in line.split(",")] for line in memory_path.read_text().splitlines() if line.strip()]
    peak_memory_mib = max(row[0] for row in samples)
    total_memory_mib = min(row[1] for row in samples)
    missing = [item for item in args.required if not (args.output / item).is_file()]
    wrapper_returncode = 0 if child_returncode == 0 and not missing else 1
    payload = {
        "schema": "a2_piper_pull_v26_8_runtime_result_v1",
        "command": command,
        "child_returncode": child_returncode,
        "wrapper_returncode": wrapper_returncode,
        "required_artifacts": args.required,
        "missing_artifacts": missing,
        "actual_success": wrapper_returncode == 0,
        "started_at": started,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "policy_readings_observed": policy_readings_observed,
        "gpu": args.gpu,
        "peak_memory_mib": peak_memory_mib,
        "total_memory_mib": total_memory_mib,
        "minimum_headroom_mib": total_memory_mib - peak_memory_mib,
    }
    with (args.output / "runtime_result.json").open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return wrapper_returncode


if __name__ == "__main__":
    raise SystemExit(main())
