#!/usr/bin/env python3
"""Write and validate the fixed Pull-v5.3 P0 adjudication contract.

The P0 scientific hypothesis was adjudicated by a human from attempt8/report.
This artifact is a gate, not a hypothesis-fitting implementation: downstream
routes consume the recorded decision and never recompute H-A/H-B/H-C/H-D.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "logs_eval/a2_piper_pull_v5/v5_3_p0_adjudication.json"
SCHEMA = "a2_piper_pull_v5_3_p0_adjudication_v1"
PLAN_ID = "a2_piper_pull_v5_3_locomotion_interface_probe"
VALID_HYPOTHESES = ("H-A", "H-B", "H-C", "H-D")
SOURCE_ATTEMPT = "attempt8"
SOURCE_REPORT = "PULL_V5_3_ROUND_REPORT.md"


def build_adjudication(
    *,
    hypothesis: str,
    downstream_admitted: bool,
    source_attempt: str = SOURCE_ATTEMPT,
    source_report: str = SOURCE_REPORT,
) -> dict[str, object]:
    """Build the explicit, human-fixed decision without scientific recomputation."""

    if hypothesis not in VALID_HYPOTHESES:
        raise ValueError(f"hypothesis must be one of {VALID_HYPOTHESES!r}; got {hypothesis!r}")
    if not isinstance(downstream_admitted, bool):
        raise TypeError("downstream_admitted must be a strict bool")
    if source_attempt != SOURCE_ATTEMPT:
        raise ValueError(f"source_attempt must be {SOURCE_ATTEMPT!r}")
    if source_report != SOURCE_REPORT:
        raise ValueError(f"source_report must be {SOURCE_REPORT!r}")
    return {
        "schema": SCHEMA,
        "version": 1,
        "plan_id": PLAN_ID,
        "adjudication_mode": "human_fixed",
        "hypothesis": hypothesis,
        "downstream_admitted": downstream_admitted,
        "scientific_hypothesis_recomputed": False,
        "source_attempt": source_attempt,
        "source_report": source_report,
    }


def _read(path: Path) -> Mapping[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise FileNotFoundError(f"P0 adjudication artifact must be a regular file: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"P0 adjudication artifact is not valid JSON: {path}") from exc
    if not isinstance(payload, Mapping):
        raise ValueError(f"P0 adjudication artifact must be a JSON object: {path}")
    return payload


def require_p0_adjudication(path: Path | str) -> dict[str, object]:
    """Validate a downstream admission artifact and reject H-D/false gates."""

    artifact_path = Path(path).expanduser().resolve()
    payload = _read(artifact_path)
    if payload.get("schema") != SCHEMA:
        raise ValueError(
            f"P0 adjudication artifact schema must be {SCHEMA!r}; got {payload.get('schema')!r}"
        )
    if payload.get("plan_id") != PLAN_ID:
        raise ValueError(
            f"P0 adjudication artifact plan_id must be {PLAN_ID!r}; got {payload.get('plan_id')!r}"
        )
    if payload.get("source_attempt") != SOURCE_ATTEMPT or payload.get("source_report") != SOURCE_REPORT:
        raise ValueError("P0 adjudication artifact must bind attempt8/PULL_V5_3_ROUND_REPORT.md")
    if payload.get("adjudication_mode") != "human_fixed":
        raise ValueError("P0 adjudication artifact must record adjudication_mode='human_fixed'")
    if payload.get("scientific_hypothesis_recomputed") is not False:
        raise ValueError("P0 adjudication artifact must not recompute scientific hypotheses")
    hypothesis = payload.get("hypothesis")
    if hypothesis not in VALID_HYPOTHESES:
        raise ValueError(f"P0 adjudication artifact hypothesis is invalid: {hypothesis!r}")
    admitted = payload.get("downstream_admitted")
    if not isinstance(admitted, bool):
        raise ValueError("P0 adjudication artifact downstream_admitted must be a strict bool")
    if hypothesis == "H-D":
        raise RuntimeError("Pull-v5.3 downstream is forbidden by fixed P0 hypothesis H-D")
    if admitted is not True:
        raise RuntimeError("Pull-v5.3 downstream is forbidden: downstream_admitted=false")
    return dict(payload)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hypothesis", choices=VALID_HYPOTHESES, required=True)
    admission = parser.add_mutually_exclusive_group(required=True)
    admission.add_argument("--downstream-admitted", action="store_true")
    admission.add_argument("--downstream-not-admitted", action="store_true")
    parser.add_argument("--source-attempt", default=SOURCE_ATTEMPT)
    parser.add_argument("--source-report", default=SOURCE_REPORT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    payload = build_adjudication(
        hypothesis=args.hypothesis,
        downstream_admitted=bool(args.downstream_admitted),
        source_attempt=args.source_attempt,
        source_report=args.source_report,
    )
    output = args.output.expanduser().resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite P0 adjudication artifact: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(f"wrote P0 adjudication artifact: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
