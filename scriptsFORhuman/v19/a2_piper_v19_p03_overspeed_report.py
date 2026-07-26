"""Strict P0.3 overspeed diagnosis and F2 variant selector."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


SCHEMA = "a2_piper_v19_p03_overspeed_report_v1"
EXPECTED_ARM_NAMES = [f"arm_j{index}" for index in range(1, 7)]


class P03ReportError(ValueError):
    """Raised when overspeed telemetry is missing or malformed."""


def _finite(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise P03ReportError(f"{name} must be finite; got {value!r}")
    return float(value)


def _load_rows(path: Path) -> list[Mapping[str, Any]]:
    path = Path(path).expanduser()
    if path.is_dir():
        path = path / "stage2_5_step_trace.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise P03ReportError(f"cannot read trace input {path}") from exc
    if not isinstance(payload, list) or not payload:
        raise P03ReportError(f"trace input {path} must be a non-empty row list")
    if any(not isinstance(row, Mapping) for row in payload):
        raise P03ReportError(f"trace input {path} contains a non-mapping row")
    return payload


def _terminal_reason(row: Mapping[str, Any]) -> bool:
    reasons = row.get("terminal_reasons")
    return isinstance(reasons, str) and "upper_dof_overspeed" in reasons


def parse_traces(paths: Sequence[Path]) -> list[dict[str, Any]]:
    if not paths:
        raise P03ReportError("at least one endpoint trace is required")
    terminal_rows: list[dict[str, Any]] = []
    for source in paths:
        for row_index, row in enumerate(_load_rows(source)):
            if not _terminal_reason(row):
                continue
            names = row.get("arm_joint_names")
            velocities = row.get("arm_joint_vel")
            if names != EXPECTED_ARM_NAMES:
                raise P03ReportError(
                    f"{source} row {row_index} requires exact arm names {EXPECTED_ARM_NAMES}; got {names!r}"
                )
            if not isinstance(velocities, (list, tuple)) or len(velocities) != 6:
                raise P03ReportError(f"{source} row {row_index} arm_joint_vel must contain six values")
            velocities = [_finite(value, f"{source} row {row_index} arm_joint_vel") for value in velocities]
            absolute = [abs(value) for value in velocities]
            max_index = max(range(6), key=absolute.__getitem__)
            max_velocity = absolute[max_index]
            if max_velocity <= 3.0:
                raise P03ReportError(
                    f"{source} row {row_index} upper_dof_overspeed max velocity must exceed 3.0; got {max_velocity}"
                )
            stage = row.get("stage_buf")
            if isinstance(stage, bool) or not isinstance(stage, int):
                raise P03ReportError(f"{source} row {row_index} stage_buf must be an int")
            terminal_rows.append(
                {
                    "source": str(Path(source).expanduser()),
                    "row_index": row_index,
                    "env_id": row.get("env_id"),
                    "stage_buf": stage,
                    "terminal_reason": row["terminal_reasons"],
                    "max_dof": EXPECTED_ARM_NAMES[max_index],
                    "max_velocity": max_velocity,
                    "arm_joint_names": list(names),
                    "arm_joint_vel": velocities,
                }
            )
    if not terminal_rows:
        raise P03ReportError("no upper_dof_overspeed terminal rows were found")
    return terminal_rows


def build_report(paths: Sequence[Path]) -> dict[str, Any]:
    rows = parse_traces(paths)
    selected = "F2" if all(row["max_dof"] in EXPECTED_ARM_NAMES for row in rows) else "INCONCLUSIVE"
    return {
        "schema": SCHEMA,
        "status": "PASS",
        "input_traces": [str(Path(path).expanduser()) for path in paths],
        "terminal_row_count": len(rows),
        "terminal_rows": rows,
        "overspeed_dof_counts": {
            name: sum(row["max_dof"] == name for row in rows) for name in EXPECTED_ARM_NAMES
        },
        "f2_selection": selected,
        "selection_basis": "arm_j1..arm_j6 telemetry only; no gain or termination inference",
    }


def write_outputs(report: Mapping[str, Any], output_dir: Path) -> tuple[Path, Path]:
    output_dir = Path(output_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "a2_piper_v19_p03_overspeed_report.json"
    md_path = output_dir / "a2_piper_v19_p03_overspeed_report.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# A2 Piper v19 P0.3 overspeed report",
        "",
        f"F2 selection: **{report['f2_selection']}**",
        "",
        "| Source | Env | Stage | Max DOF | Max |",
        "|---|---:|---:|---|---:|",
    ]
    for row in report["terminal_rows"]:
        lines.append(
            f"| `{row['source']}` | {row['env_id']} | {row['stage_buf']} | "
            f"{row['max_dof']} | {row['max_velocity']:.7f} |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace", type=Path, action="append", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_report(args.trace)
    paths = write_outputs(report, args.output_dir)
    print(f"P0.3 JSON: {paths[0]}")
    print(f"P0.3 Markdown: {paths[1]}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except P03ReportError as exc:
        print(f"P0.3 FAIL: {exc}", file=sys.stderr)
        sys.exit(2)
