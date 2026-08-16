"""Small shared helpers for the CPU-only base-v24 P0 reducers.

The posthoc inputs contain multi-hundred-megabyte JSON arrays.  The array
iterator below deliberately keeps one JSON object in memory at a time and is
used for every trace file; the reducer never loads a trace batch or rewrites
the immutable v23 evidence.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Iterator, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]
V24_ARTIFACT_ROOT = REPO_ROOT / "logs_eval/base_v24"
V24_P0_ROOT = V24_ARTIFACT_ROOT / "p0/v23_posthoc"
V24_CHECKPOINT_FREEZE_ROOT = V24_ARTIFACT_ROOT / "p0/checkpoint_freeze"
V24_P1_FRICTION_ROOT = V24_ARTIFACT_ROOT / "p1/friction_backend"

V23_ROUTE_B_PATH = REPO_ROOT / "logs_eval/base_v23/postformal_gpu8_orchestration_r7/V23_ROUTE_B.json"
V23_STRATIFIED_PATH = REPO_ROOT / "logs_eval/base_v23/postformal_gpu8_orchestration_r7/V23_STRATIFIED_EVAL.json"
V23_INTERVENTION_PATH = REPO_ROOT / "logs_eval/base_v23/postformal_gpu8_orchestration_r7/V23_INTERVENTION_EVAL.json"
V23_FREEZE_PATH = REPO_ROOT / "logs_eval/base_v23/postformal_gpu8_orchestration_r7_f8_candidate_freeze/candidate_freeze.json"
V23_HOLDOUT_PATH = REPO_ROOT / "logs_eval/base_v23/postformal_gpu8_orchestration_r8_holdout/holdout_receipt.json"
V23_FINAL_PATH = REPO_ROOT / "logs_eval/base_v23/final_analysis/V23_FINAL_ANALYSIS.json"
V23_P05_BANDS_PATH = REPO_ROOT / "logs_eval/base_v23/p0/r35_p05_cert_20260809/p05_bands.json"
V23_ROUTE_A_ROOT = REPO_ROOT / "logs_eval/base_v23/route_a"

EXPECTED_CANDIDATES = 16
EXPECTED_REALIZED_EPISODES = 768
EXPECTED_INTERVENTION_RECORDS = 1280
INTERVENTION_MODES = (
    "FULL",
    "ACUTE_RP0",
    "BASE0_AT_GRASP",
    "HIGHER_EFFORT_RESCUE",
    "ORACLE_TANGENTIAL_ASSIST",
)


class V24Error(ValueError):
    """A frozen v23 source or v24 reducer contract is invalid."""


def absolute(path: str | Path) -> Path:
    target = Path(path)
    return target if target.is_absolute() else REPO_ROOT / target


def require_file(path: str | Path, *, label: str = "required input") -> Path:
    target = absolute(path)
    if target.is_symlink() or not target.is_file():
        raise V24Error(f"{label} is not a regular file: {target}")
    return target


def read_json(path: str | Path, *, label: str = "JSON input") -> Any:
    target = require_file(path, label=label)
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise V24Error(f"{label} is not valid JSON: {target}") from exc


def require_object(value: Any, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise V24Error(f"{label} must be a JSON object")
    return value


def finite_number(value: Any, *, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise V24Error(f"{label} must be a finite number; got {value!r}")
    result = float(value)
    if not math.isfinite(result):
        raise V24Error(f"{label} must be finite; got {value!r}")
    return result


def write_json(path: str | Path, payload: Mapping[str, Any], *, overwrite: bool = False) -> Path:
    target = absolute(path)
    if target.exists() and not overwrite:
        raise V24Error(f"refusing to overwrite v24 artifact: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(dict(payload), ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return target


def write_text(path: str | Path, text: str, *, overwrite: bool = False) -> Path:
    target = absolute(path)
    if target.exists() and not overwrite:
        raise V24Error(f"refusing to overwrite v24 artifact: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target


def iter_json_array(path: str | Path, *, chunk_size: int = 8 * 1024 * 1024) -> Iterator[Any]:
    """Yield elements from a top-level JSON array without batch loading it."""

    target = require_file(path, label="trace input")
    decoder = json.JSONDecoder()
    with target.open("r", encoding="utf-8") as handle:
        buffer = ""
        cursor = 0
        eof = False

        def refill() -> None:
            nonlocal buffer, eof
            chunk = handle.read(chunk_size)
            if chunk:
                buffer += chunk
            else:
                eof = True

        refill()
        while cursor < len(buffer) and buffer[cursor].isspace():
            cursor += 1
        if cursor >= len(buffer) or buffer[cursor] != "[":
            raise V24Error(f"trace input must start with a JSON array: {target}")
        cursor += 1
        first = True
        while True:
            while True:
                while cursor < len(buffer) and buffer[cursor].isspace():
                    cursor += 1
                if cursor < len(buffer):
                    break
                if eof:
                    raise V24Error(f"unterminated JSON array: {target}")
                buffer = ""
                cursor = 0
                refill()

            if buffer[cursor] == "]":
                return
            if not first:
                if buffer[cursor] != ",":
                    raise V24Error(f"missing comma in trace array: {target}")
                cursor += 1
                while True:
                    while cursor < len(buffer) and buffer[cursor].isspace():
                        cursor += 1
                    if cursor < len(buffer):
                        break
                    if eof:
                        raise V24Error(f"unterminated JSON array: {target}")
                    buffer = ""
                    cursor = 0
                    refill()
                if buffer[cursor] == "]":
                    raise V24Error(f"trailing comma in trace array: {target}")

            while True:
                try:
                    value, end = decoder.raw_decode(buffer, cursor)
                    break
                except json.JSONDecodeError as exc:
                    if eof:
                        raise V24Error(f"invalid JSON element in trace: {target}: {exc}") from exc
                    if cursor > 0:
                        buffer = buffer[cursor:]
                        cursor = 0
                    refill()
            yield value
            cursor = end
            first = False
            if cursor > chunk_size:
                buffer = buffer[cursor:]
                cursor = 0


def rel_path(path: str | Path) -> str:
    target = absolute(path)
    try:
        return target.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(target)


__all__ = [
    "EXPECTED_CANDIDATES",
    "EXPECTED_INTERVENTION_RECORDS",
    "EXPECTED_REALIZED_EPISODES",
    "INTERVENTION_MODES",
    "REPO_ROOT",
    "V23_FINAL_PATH",
    "V23_P05_BANDS_PATH",
    "V23_FREEZE_PATH",
    "V23_HOLDOUT_PATH",
    "V23_INTERVENTION_PATH",
    "V23_ROUTE_B_PATH",
    "V23_STRATIFIED_PATH",
    "V24_P0_ROOT",
    "V24_P1_FRICTION_ROOT",
    "V24_CHECKPOINT_FREEZE_ROOT",
    "V23_ROUTE_A_ROOT",
    "V24Error",
    "absolute",
    "finite_number",
    "iter_json_array",
    "read_json",
    "rel_path",
    "require_file",
    "require_object",
    "write_json",
    "write_text",
]
