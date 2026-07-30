"""Independent strict holdout64 consumer."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from ._r2_common import R2Error, canonical_json
from ._r2_workflow import artifact_hash, read_artifact, write_adjudication

HOLDOUT_SEEDS = (3, 4, 5, 6)


def adjudicate_holdout(release_freeze: Path, root: Path, *, source_lock: Path | None = None) -> dict[str, object]:
    freeze = read_artifact(release_freeze, schema="a2_piper_base_v20_R2_release_freeze_v1", adjudicator_state="POLICY_PASS")
    if freeze.get("holdout_allowed") is not True or freeze.get("selected_group") is None:
        raise R2Error("holdout cannot run for NO_RELEASE")
    if source_lock is not None and freeze.get("source_lock_sha256") != artifact_hash(source_lock):
        raise R2Error("holdout freeze source-lock mismatch")
    identities: set[tuple[int, int]] = set(); records_out: list[dict[str, Any]] = []
    for seed in HOLDOUT_SEEDS:
        path = root / f"seed{seed}" / "record_set.json"
        payload = read_artifact(path, schema="a2_piper_base_v20_R2_record_set_v1", producer_state="RECORD_SET_COMPLETE")
        records = payload.get("records")
        if not isinstance(records, list) or len(records) != 16:
            raise R2Error(f"holdout seed{seed} must contain exactly 16 records")
        for record in records:
            prov = record.get("provenance", {})
            if prov.get("seed") != seed:
                raise R2Error("holdout seed leakage or substitution detected")
            if prov.get("checkpoint_sha256") != freeze.get("selected_checkpoint_sha256"):
                raise R2Error("holdout checkpoint is not the frozen candidate")
            identity = (seed, prov.get("env_id"))
            if identity in identities:
                raise R2Error("holdout duplicate scenario identity")
            identities.add(identity)
        records_out.append({"seed": seed, "record_set_sha256": artifact_hash(path), "record_count": len(records)})
    if identities != {(seed, env_id) for seed in HOLDOUT_SEEDS for env_id in range(16)}:
        raise R2Error("holdout scenario set is not exact seeds3-6 x env0-15")
    return {"schema": "a2_piper_base_v20_R2_endpoint_report_v1", "adjudicator_state": "HOLDOUT64_PASS",
            "source_lock_sha256": freeze["source_lock_sha256"], "record_set_sha256": artifact_hash(release_freeze),
            "group": freeze["selected_group"], "record_count": 64,
            "metrics": {"seed_count": 4, "records": records_out, "exact_scenarios": True},
            "invalid_reasons": [], "parents": {"release_freeze": artifact_hash(release_freeze)}}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-freeze", type=Path, required=True); parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--source-lock", type=Path); parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = adjudicate_holdout(args.release_freeze, args.root, source_lock=args.source_lock)
    write_adjudication(args.output, result, "HOLDOUT64_PASS")
    print(canonical_json(result)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
