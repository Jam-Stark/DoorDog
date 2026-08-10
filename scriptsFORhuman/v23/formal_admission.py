"""CPU-only formal-admission reducer for the base_v23 artifact DAG.

This reducer seals only the owner-authorized start-training gate.  It reads the
current formal plan and the three prerequisite receipts, applies no policy or
symmetry criterion, and never launches training.  A lock is written only by
``REDUCE`` and only when its destination is absent.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from ._v23_common import REPO_ROOT, V23_LAUNCHER_ROOT, V23_PLAN_ID, V23Error, read_json, write_json
except ImportError:  # direct ``python scriptsFORhuman/v23/formal_admission.py``
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from scriptsFORhuman.v23._v23_common import REPO_ROOT, V23_LAUNCHER_ROOT, V23_PLAN_ID, V23Error, read_json, write_json


FORMAL_PLAN_PATH = REPO_ROOT / V23_LAUNCHER_ROOT / "FORMAL_PLAN.json"
D1_RECEIPT_PATH = REPO_ROOT / "logs_eval/base_v23/p0/p04_d1_physics_first_20260810/p04_d1_physics_first.json"
P08_RECEIPT_PATH = REPO_ROOT / "logs_eval/base_v23/p0/interventions/preformal_v2/p08_preformal_v2_receipt.json"
D1_FULL_RECEIPT_PATH = REPO_ROOT / "logs_eval/base_v23/p0/d1_full_64x10/d1_full_64x10_receipt.json"
FORMAL_ADMISSION_PATH = REPO_ROOT / "logs_eval/base_v23/locks/V23_FORMAL_ADMISSION_PASS.json"

FORMAL_PLAN_SCHEMA = "a2_piper_v23_formal_plan_v1"
FORMAL_PLAN_STATUS = "READY_TO_ADMIT"
D1_RECEIPT_SCHEMA = "a2_piper_v23_p04_d1_physics_first_v1"
D1_RECEIPT_STATUS = "P0_4_D1_PHYSICS_FIRST_FREEZE_ADMITTED"
P08_RECEIPT_SCHEMA = "a2_piper_v23_p08_preformal_v2_receipt_v1"
P08_RECEIPT_STATUS = "P0_8_PREFORMAL_COMPLETE"
D1_FULL_RECEIPT_SCHEMA = "a2_piper_v23_d1_full_64x10_receipt_v1"
D1_FULL_RECEIPT_STATUS = "D1_FULL_64X10_BUCKET_PLUMBING_RUNTIME_VERIFIED"
FORMAL_ADMISSION_SCHEMA = "a2_piper_v23_formal_admission_v1"
FORMAL_ADMISSION_STATUS = "V23_FORMAL_ADMISSION_PASS"
SCOPE = "START_FORMAL_TRAINING_ONLY"


class FormalAdmissionError(V23Error):
    """A formal-admission input or lock contract is invalid."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _absolute_regular_file(value: str | Path, *, label: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = REPO_ROOT / path
    if path.is_symlink() or not path.is_file():
        raise FormalAdmissionError(f"{label} is not a readable regular file: {path}")
    return path.resolve()


def _load_receipt(path: str | Path, *, name: str, schema: str, status: str) -> tuple[Path, dict[str, Any]]:
    target = _absolute_regular_file(path, label=name)
    payload = read_json(target)
    if payload.get("schema") != schema:
        raise FormalAdmissionError(f"{name} schema must be {schema}: {target}")
    if payload.get("status") != status:
        raise FormalAdmissionError(f"{name} status must be {status}: {target}")
    return target, payload


def _load_inputs(
    *,
    formal_plan: str | Path,
    d1_receipt: str | Path,
    p08_receipt: str | Path,
    d1_full_receipt: str | Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    plan_path, plan = _load_receipt(
        formal_plan,
        name="FORMAL_PLAN",
        schema=FORMAL_PLAN_SCHEMA,
        status=FORMAL_PLAN_STATUS,
    )
    if plan.get("physical_gpus") != [0, 1]:
        raise FormalAdmissionError("FORMAL_PLAN physical_gpus must be exactly [0, 1]")
    if plan.get("source_branch") != "A2_Piper" or plan.get("plan_id") != V23_PLAN_ID:
        raise FormalAdmissionError("FORMAL_PLAN provenance disagrees with base_v23")
    admission = plan.get("admission")
    if not isinstance(admission, Mapping) or admission.get("all_pass") is not True:
        raise FormalAdmissionError("FORMAL_PLAN admission.all_pass must be true")

    specs = (
        ("D1_PHYSICS_FIRST", d1_receipt, D1_RECEIPT_SCHEMA, D1_RECEIPT_STATUS),
        ("P0_8_PREFORMAL_V2", p08_receipt, P08_RECEIPT_SCHEMA, P08_RECEIPT_STATUS),
        ("D1_FULL_64X10", d1_full_receipt, D1_FULL_RECEIPT_SCHEMA, D1_FULL_RECEIPT_STATUS),
    )
    required = [
        {
            "name": "FORMAL_PLAN",
            "path": str(plan_path),
            "schema": FORMAL_PLAN_SCHEMA,
            "status": FORMAL_PLAN_STATUS,
        }
    ]
    for name, path, schema, status in specs:
        target, _payload = _load_receipt(path, name=name, schema=schema, status=status)
        required.append({"name": name, "path": str(target), "schema": schema, "status": status})
    if len({row["path"] for row in required}) != 4:
        raise FormalAdmissionError("formal-admission inputs must contain exactly four unique paths")
    return plan, required


def build_receipt(
    *,
    formal_plan: str | Path = FORMAL_PLAN_PATH,
    d1_receipt: str | Path = D1_RECEIPT_PATH,
    p08_receipt: str | Path = P08_RECEIPT_PATH,
    d1_full_receipt: str | Path = D1_FULL_RECEIPT_PATH,
) -> dict[str, Any]:
    """Validate the exact owner conjunction and build its lock payload."""

    _plan, required = _load_inputs(
        formal_plan=formal_plan,
        d1_receipt=d1_receipt,
        p08_receipt=p08_receipt,
        d1_full_receipt=d1_full_receipt,
    )
    return {
        "schema": FORMAL_ADMISSION_SCHEMA,
        "status": FORMAL_ADMISSION_STATUS,
        "recorded_at_utc": _utc_now(),
        "source_branch": "A2_Piper",
        "plan_id": V23_PLAN_ID,
        "scope": SCOPE,
        "formal_admission": True,
        "policy_quality_claim": False,
        "release_receipt": False,
        "formal_training_completed": False,
        "required_receipts": required,
        "excluded_claims": [
            "NO_POLICY_QUALITY_CLAIM",
            "NO_RELEASE_RECEIPT",
            "NO_FORMAL_TRAINING_COMPLETION",
        ],
    }


def reduce_receipt(
    *,
    formal_plan: str | Path = FORMAL_PLAN_PATH,
    d1_receipt: str | Path = D1_RECEIPT_PATH,
    p08_receipt: str | Path = P08_RECEIPT_PATH,
    d1_full_receipt: str | Path = D1_FULL_RECEIPT_PATH,
    output: str | Path = FORMAL_ADMISSION_PATH,
) -> dict[str, Any]:
    """Write one absent formal-admission lock after strict CPU validation."""

    target = Path(output)
    if not target.is_absolute():
        target = REPO_ROOT / target
    if target.exists() or target.is_symlink():
        raise FormalAdmissionError(f"refusing to overwrite existing formal-admission lock: {target}")
    target = target.resolve()
    payload = build_receipt(
        formal_plan=formal_plan,
        d1_receipt=d1_receipt,
        p08_receipt=p08_receipt,
        d1_full_receipt=d1_full_receipt,
    )
    write_json(target, payload, overwrite=False)
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("REDUCE",), required=True)
    parser.add_argument("--formal-plan", type=Path, default=FORMAL_PLAN_PATH)
    parser.add_argument("--d1", type=Path, default=D1_RECEIPT_PATH)
    parser.add_argument("--p08", type=Path, default=P08_RECEIPT_PATH)
    parser.add_argument("--d1-full", type=Path, default=D1_FULL_RECEIPT_PATH)
    parser.add_argument("--output", type=Path, default=FORMAL_ADMISSION_PATH)
    args = parser.parse_args(argv)
    try:
        payload = reduce_receipt(
            formal_plan=args.formal_plan,
            d1_receipt=args.d1,
            p08_receipt=args.p08,
            d1_full_receipt=args.d1_full,
            output=args.output,
        )
    except (OSError, TypeError, ValueError, V23Error) as exc:
        print(f"V23 FORMAL_ADMISSION REDUCE FAIL: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
