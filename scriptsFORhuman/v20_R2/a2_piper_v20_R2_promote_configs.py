"""Acyclic admission bundle builder and exact two-key config promoter."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from ._r2_common import R2Error, canonical_json, write_bytes_exclusive
from ._r2_workflow import GROUPS, artifact_hash, config_identity, r2_config_path, read_artifact, write_adjudication, write_raw

BUNDLE_SCHEMA = "a2_piper_base_v20_R2_config_promotion_artifact_v1"


def build_bundle(*, parents: dict[str, Path], source_lock: Path, output: Path) -> dict[str, object]:
    required = ("p0", "b0", "forced", "zero_shot", "p1", "pilot", "smoke")
    if tuple(parents) != required:
        raise R2Error("formal bundle parent set/order is incomplete")
    states = {"p0": ("a2_piper_base_v20_R2_p0_adjudication_v1", "STATIC_PASS"),
              "b0": ("a2_piper_base_v20_R2_endpoint_report_v1", "B0_RUNTIME_PASS"),
              "forced": ("a2_piper_base_v20_R2_semantic_adjudication_v1", "FORCED_RUNTIME_SEMANTIC_PASS"),
              "zero_shot": ("a2_piper_base_v20_R2_semantic_adjudication_v1", "ZERO_SHOT7_RUNTIME_SEMANTIC_PASS"),
              "p1": ("a2_piper_base_v20_R2_semantic_adjudication_v1", "R2_P1_RUNTIME_SEMANTIC_PASS"),
              "pilot": ("a2_piper_base_v20_R2_endpoint_report_v1", "POLICY_LEARNABILITY_PASS"),
              "smoke": ("a2_piper_base_v20_R2_endpoint_report_v1", "SMOKE_PASS")}
    hashes: dict[str, str] = {}
    source_hash = artifact_hash(source_lock)
    read_artifact(source_lock, schema="a2_piper_base_v20_R2_source_lock_v1", producer_state="SOURCE_FROZEN")
    for name in required:
        schema, state = states[name]
        payload = read_artifact(parents[name], schema=schema, adjudicator_state=state)
        if payload.get("source_lock_sha256") not in (None, source_hash):
            raise R2Error(f"formal bundle parent {name} source-lock mismatch")
        hashes[name] = artifact_hash(parents[name])
    payload = {"schema": BUNDLE_SCHEMA, "producer_state": "LAUNCH_PLAN_COMPLETE",
               "source_lock_sha256": source_hash, "parents": hashes,
               "configs": [], "bundle_inputs": list(required)}
    write_raw(output, payload, producer_state="LAUNCH_PLAN_COMPLETE")
    return payload


def _promoted_text(source_text: str, bundle_hash: str) -> str:
    if source_text.count("a2_v20_R2_formal_launch: false") != 1:
        raise R2Error("source config must contain exactly one formal_launch=false key")
    if source_text.count("a2_v20_R2_admission_bundle_sha256: null") != 1:
        raise R2Error("source config must contain exactly one null admission bundle key")
    return source_text.replace("a2_v20_R2_formal_launch: false", "a2_v20_R2_formal_launch: true", 1).replace(
        "a2_v20_R2_admission_bundle_sha256: null", f"a2_v20_R2_admission_bundle_sha256: {bundle_hash}", 1)


def _semantic_config(text: str) -> Any:
    try:
        import yaml
    except ImportError as exc:
        raise R2Error("PyYAML is required to reparse promoted configs") from exc
    try:
        value = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise R2Error("promoted config YAML is invalid") from exc
    if not isinstance(value, dict):
        raise R2Error("R2 config must parse to a mapping")
    return value


def _expected_promoted(source_text: str, bundle_hash: str) -> Any:
    expected = _semantic_config(source_text)
    env = expected.get("env", {}).get("config", {})
    if env.get("a2_v20_R2_formal_launch") is not False or env.get("a2_v20_R2_admission_bundle_sha256") is not None:
        raise R2Error("source config has unexpected pre-promotion values")
    env["a2_v20_R2_formal_launch"] = True
    env["a2_v20_R2_admission_bundle_sha256"] = bundle_hash
    return expected


def promote(*, repo_root: Path, bundle: Path, config_root: Path | None = None, output_root: Path) -> dict[str, object]:
    root = Path(repo_root).resolve()
    payload = read_artifact(bundle, schema=BUNDLE_SCHEMA, producer_state="LAUNCH_PLAN_COMPLETE")
    bundle_hash = artifact_hash(bundle)
    config_root = config_root or root / "gr00t/rl/config/ablation/wbmanip"
    if output_root.exists():
        raise R2Error(f"frozen config output root already exists; overwrite is forbidden: {output_root}")
    output_root.mkdir(parents=True)
    rows: list[dict[str, object]] = []
    for group in GROUPS:
        source = r2_config_path(config_root, group)
        source_identity = config_identity(source)
        promoted = _promoted_text(source_identity["text"], bundle_hash)
        target = output_root / source.name
        digest = write_bytes_exclusive(target, promoted.encode("utf-8"))
        reparsed = _semantic_config(target.read_text(encoding="utf-8"))
        if reparsed != _expected_promoted(source_identity["text"], bundle_hash):
            raise R2Error(f"promoted config semantic diff exceeds the exact two-key delta: {group}")
        rows.append({"group": group, "source_sha256": source_identity["sha256"],
                     "frozen_sha256": digest, "resolved_sha256": digest,
                     "source_path": str(source), "frozen_path": str(target),
                     "delta_keys": ["env.config.a2_v20_R2_formal_launch", "env.config.a2_v20_R2_admission_bundle_sha256"]})
    result = {"schema": BUNDLE_SCHEMA, "adjudicator_state": "PROMOTION_PASS",
              "source_lock_sha256": payload["source_lock_sha256"], "bundle_sha256": bundle_hash,
              "parents": {"bundle": bundle_hash}, "configs": rows}
    write_adjudication(output_root / "PROMOTION_PASS.json", result, "PROMOTION_PASS")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    b = sub.add_parser("build-bundle")
    b.add_argument("--source-lock", type=Path, required=True); b.add_argument("--p0", type=Path, required=True); b.add_argument("--b0", type=Path, required=True)
    b.add_argument("--forced", type=Path, required=True); b.add_argument("--zero-shot", type=Path, required=True); b.add_argument("--p1", type=Path, required=True)
    b.add_argument("--pilot", type=Path, required=True); b.add_argument("--smoke", type=Path, required=True); b.add_argument("--output", type=Path, required=True)
    x = sub.add_parser("promote")
    x.add_argument("--repo-root", type=Path, required=True); x.add_argument("--admission-bundle", type=Path, required=True)
    x.add_argument("--config-root", type=Path); x.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.mode == "build-bundle":
        build_bundle(parents={name: getattr(args, name.replace("-", "_")) for name in ("p0", "b0", "forced", "zero_shot", "p1", "pilot", "smoke")}, source_lock=args.source_lock, output=args.output)
    else:
        promote(repo_root=args.repo_root, bundle=args.admission_bundle, config_root=args.config_root, output_root=args.output_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
