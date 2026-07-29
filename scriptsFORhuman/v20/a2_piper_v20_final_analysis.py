"""Bind v20 M22/pooled/holdout/render evidence into the final release decision."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


SCHEMA = "a2_piper_v20_final_analysis_v1"


class V20FinalError(ValueError):
    pass


def _module(filename: str, name: str):
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise V20FinalError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ENDPOINT = _module("a2_piper_v20_endpoint_report.py", "v20_endpoint_for_final")
ADJ = _module("a2_piper_v20_m22_adjudicator.py", "v20_adjudicator_for_final")


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise V20FinalError(f"cannot read {path}: {exc}") from exc


def build_final_analysis(
    *,
    endpoint: Mapping[str, Any],
    m22_rows: Sequence[Mapping[str, Any]],
    paired: Mapping[str, Any],
    holdout: Mapping[str, Any] | None,
    render_qa: Mapping[str, Any] | None,
    frozen_values: Mapping[str, Any],
) -> dict[str, Any]:
    if endpoint.get("schema") != ENDPOINT.SCHEMA:
        raise V20FinalError("endpoint schema mismatch")
    if len(m22_rows) != 70:
        raise V20FinalError(f"final analysis requires exactly 70 M22 rows; got {len(m22_rows)}")
    identities = {(row.get("group"), row.get("candidate_id")) for row in m22_rows}
    if len(identities) != 70 or {group for group, _ in identities} != {f"G{i}" for i in range(1, 8)}:
        raise V20FinalError("M22 identity/group coverage is not exact 7x10")
    if any(row.get("strict_status") not in {"STRICT_VALID", "STRICT_INVALID"} for row in m22_rows):
        raise V20FinalError("M22 strict statuses are malformed")
    if paired.get("schema") != "a2_piper_v20_paired_analysis_v1":
        raise V20FinalError("paired analysis schema mismatch")
    release = endpoint.get("release_candidate")
    holdout_status = "NOT_RUN"
    render_status = "NOT_RUN"
    failed = []
    if endpoint.get("release_status") == "NO_V20_RELEASE":
        if release is not None:
            raise V20FinalError("NO_V20_RELEASE cannot contain a candidate")
        failed.append("no_pooled_release_candidate")
    else:
        if not isinstance(release, Mapping):
            raise V20FinalError("frozen release candidate is missing")
        if holdout is None:
            failed.append("holdout64_missing")
        else:
            if holdout.get("schema") != "a2_piper_v20_holdout64_v1":
                raise V20FinalError("holdout64 schema mismatch")
            if (
                holdout.get("checkpoint_path") != release.get("path")
                or holdout.get("checkpoint_sha256") != release.get("sha256")
                or holdout.get("group") != release.get("group")
            ):
                raise V20FinalError("holdout64 does not bind the frozen candidate")
            if holdout.get("strict_status") != "STRICT_VALID" or not isinstance(holdout.get("metrics"), Mapping):
                holdout_status = "FAIL"
                failed.append("holdout64_strict_invalid")
            else:
                gate = ADJ.evaluate_gates(
                    holdout["metrics"],
                    topology="holdout64",
                    theta_send=frozen_values["theta_send"],
                    relief_limit_m=frozen_values["relief_limit_m"],
                    arm_share_baseline=frozen_values["arm_share_baseline"],
                    orientation_tolerance_rad=frozen_values["orientation_tolerance_rad"],
                    smoothness_baseline=frozen_values["smoothness_baseline"],
                )
                holdout_status = gate["status"]
                failed.extend(f"holdout64:{name}" for name in gate["failed_gates"])
        if render_qa is None:
            failed.append("render_qa_missing")
        else:
            if render_qa.get("schema") != "a2_piper_v20_render_qa_v1":
                raise V20FinalError("render QA schema mismatch")
            groups = render_qa.get("groups")
            if not isinstance(groups, Mapping) or release["group"] not in groups:
                raise V20FinalError("render QA does not include frozen release group")
            rendered = groups[release["group"]]
            if (
                rendered.get("checkpoint") != release["path"]
                or rendered.get("checkpoint_sha256") != release["sha256"]
            ):
                raise V20FinalError("render QA checkpoint differs from frozen release")
            render_status = (
                "PASS"
                if render_qa.get("media_status") == "PASS"
                and rendered.get("behavior_status") == "PASS"
                else "FAIL"
            )
            if render_status != "PASS":
                failed.append("render_behavior_or_media")
    final_status = "RELEASE" if not failed and holdout_status == "PASS" and render_status == "PASS" else "NO_RELEASE"
    return {
        "schema": SCHEMA,
        "pooled_release_status": endpoint["release_status"],
        "frozen_release_candidate": release,
        "holdout64_status": holdout_status,
        "render_status": render_status,
        "final_status": final_status,
        "failed_gates": failed,
        "fallback": None,
        "groups": endpoint["groups"],
        "m22_coverage": {
            "rows": 70,
            "strict_valid": sum(row["strict_status"] == "STRICT_VALID" for row in m22_rows),
            "strict_invalid": sum(row["strict_status"] == "STRICT_INVALID" for row in m22_rows),
        },
        "sample_size_statement": "Canonical16, pooled48, and holdout64 are preregistered behavior evidence, not statistical proof.",
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", type=Path, required=True)
    parser.add_argument("--m22-rows", type=Path, required=True)
    parser.add_argument("--paired", type=Path, required=True)
    parser.add_argument("--holdout", type=Path)
    parser.add_argument("--render-qa", type=Path)
    parser.add_argument("--frozen-values", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.output.exists():
        raise V20FinalError(f"refusing to overwrite {args.output}")
    rows_payload = _load_json(args.m22_rows)
    rows = rows_payload.get("rows") if isinstance(rows_payload, Mapping) else rows_payload
    report = build_final_analysis(
        endpoint=_load_json(args.endpoint),
        m22_rows=rows,
        paired=_load_json(args.paired),
        holdout=None if args.holdout is None else _load_json(args.holdout),
        render_qa=None if args.render_qa is None else _load_json(args.render_qa),
        frozen_values=_load_json(args.frozen_values),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"v20 final status: {report['final_status']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (V20FinalError, ADJ.V20AdjudicationError) as exc:
        print(f"v20 FINAL ANALYSIS FAIL: {exc}", file=sys.stderr)
        raise SystemExit(2)
