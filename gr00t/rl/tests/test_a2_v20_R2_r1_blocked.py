"""R1 historical CLIs are blocked by default but remain import-safe."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
R1_ROOT = ROOT / "scriptsFORhuman/v20_R1"
R1_CLIS = sorted(path for path in R1_ROOT.glob("*.py") if path.name not in {"__init__.py", "_r1_common.py"})


def test_every_r1_cli_exits_two_without_artifact(tmp_path: Path):
    env = os.environ.copy()
    env.pop("BASE_V20_ALLOW_BLOCKED_R1_EXECUTION", None)
    for path in R1_CLIS:
        result = subprocess.run(
            [sys.executable, str(path), "--help"],
            cwd=tmp_path,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 2, (path.name, result.stdout, result.stderr)
        assert not list(tmp_path.rglob("*.json")), path.name
        assert not list(tmp_path.rglob("*.csv")), path.name


def test_r1_modules_still_import_without_opt_in():
    for path in R1_CLIS:
        name = "r1_safe_import_" + path.stem
        spec = importlib.util.spec_from_file_location(name, path)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
