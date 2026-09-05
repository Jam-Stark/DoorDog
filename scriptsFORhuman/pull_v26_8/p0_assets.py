#!/usr/bin/env python3
"""Check the two remote Isaac assets before a pull-v26-8 Isaac launch."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ASSETS = (
    "https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/5.1/Isaac/Environments/Grid/default_environment.usd",
    "https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/5.1/NVIDIA/Materials/Base/Wood/Ash.mdl",
)
PROXY_KEYS = ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "no_proxy", "NO_PROXY")
HTTP_STATUS = re.compile(r"^HTTP/[^ ]+ ([0-9]{3})(?: |$)", re.MULTILINE)


def check(url: str) -> dict[str, object]:
    command = ("curl", "-sI", "--max-time", "20", url)
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    codes = [int(value) for value in HTTP_STATUS.findall(result.stdout)]
    status = codes[-1] if codes else None
    return {
        "url": url,
        "command": list(command),
        "curl_returncode": result.returncode,
        "http_status": status,
        "headers": result.stdout,
        "stderr": result.stderr,
        "passed": result.returncode == 0 and status == 200,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    checks = [check(url) for url in ASSETS]
    passed = all(row["passed"] for row in checks)
    payload = {
        "schema": "a2_piper_pull_v26_8_p0_assets_v1",
        "status": "P0_ASSETS_PASS" if passed else "INFRA_ASSET_UNREACHABLE",
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "proxy_environment": {key: os.environ.get(key) for key in PROXY_KEYS},
        "assets": checks,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps(payload, ensure_ascii=False))
    if not passed:
        raise SystemExit("INFRA_ASSET_UNREACHABLE")


if __name__ == "__main__":
    main()
