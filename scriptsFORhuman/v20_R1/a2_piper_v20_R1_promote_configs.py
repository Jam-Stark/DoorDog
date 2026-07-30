"""Promote configs only after an exact, hash-bound admission chain."""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _r1_common import (  # noqa: E402
    GROUPS,
    NO_RELEASE,
    PLAN_ID,
    POLICY_LEARNABILITY_PASS,
    POLICY_PASS,
    R1Error,
    R1_ARTIFACT_ROOT,
    RUNTIME_SEMANTIC_PASS,
    RUNTIME_PASS,
    STATIC_PASS,
    exact_digest,
    load_json,
    sha256_file,
    write_json_no_overwrite,
)

SCHEMA = "a2_piper_v20_R1_config_promotion_v3"
WHITELIST = ("a2_v20_formal_launch", "a2_v20_R1_admission_manifest_sha256")
FROZEN_NAMESPACE = "scriptsFORhuman/v20_R1/frozen_formal"
FROZEN_GROUP = "a2_v20_R1_frozen"


def _validate_admission(admission_manifest: Path, expected_sha: str) -> Mapping[str, Any]:
    exact_digest(expected_sha, name="admission_manifest_sha256", length=64)
    actual = sha256_file(admission_manifest)
    if actual != expected_sha:
        raise R1Error(f"admission manifest SHA mismatch: expected {expected_sha}, got {actual}")
    payload = load_json(admission_manifest)
    if (
        not isinstance(payload, Mapping)
        or payload.get("plan_id") != PLAN_ID
        or payload.get("status") != POLICY_PASS
    ):
        raise R1Error("admission manifest must be plan-bound POLICY PASS")
    return payload


def _validate_chain(chain_artifacts: Mapping[str, Path] | None) -> dict[str, str]:
    required = ("preflight", "semantic", "pilot", "smoke")
    if chain_artifacts is None:
        raise R1Error("promotion requires preflight, semantic, pilot, and smoke artifacts")
    expected_status = {
        "preflight": STATIC_PASS,
        "semantic": RUNTIME_SEMANTIC_PASS,
        "pilot": POLICY_LEARNABILITY_PASS,
        "smoke": RUNTIME_PASS,
    }
    resolved = {}
    for name in required:
        path = Path(chain_artifacts.get(name, ""))
        if not path.is_file() or path.is_symlink():
            raise R1Error(f"promotion chain artifact missing: {name}")
        payload = load_json(path)
        if (
            not isinstance(payload, Mapping)
            or payload.get("plan_id") != PLAN_ID
            or payload.get("status") != expected_status[name]
        ):
            raise R1Error(f"promotion chain artifact status mismatch: {path}")
        resolved[name] = str(path.resolve())
    return resolved


def _source_hashes_from_preflight(path: Path) -> dict[str, str]:
    payload = load_json(path)
    rows = payload.get("candidate_configs")
    if not isinstance(rows, list) or len(rows) != len(GROUPS):
        raise R1Error("preflight candidate config hash list must contain all seven groups")
    result = {}
    for row in rows:
        if not isinstance(row, Mapping) or not isinstance(row.get("group"), str):
            raise R1Error("preflight candidate hash row is malformed")
        exact_digest(row.get("sha256"), name="preflight.config.sha256", length=64)
        result[row["group"]] = row["sha256"]
    if set(result) != {spec["group"] for spec in GROUPS}:
        raise R1Error("preflight candidate group hash set is incomplete")
    return result


def verify_hydra_promoted_group(
    *,
    repo_root: Path,
    frozen_root: Path,
    config_name: str,
    admission_sha256: str,
) -> dict[str, Any]:
    """Compose the promoted group and run the real --cfg job --resolve probe."""
    try:
        from hydra import compose, initialize_config_dir
        from omegaconf import OmegaConf
    except ImportError as exc:
        raise R1Error("Hydra/OmegaConf are required for promoted config verification") from exc
    with initialize_config_dir(
        config_dir=str((repo_root / "gr00t/rl/config").resolve()),
        version_base="1.1",
        job_name="base_v20_R1_promoted_verify",
    ):
        composed = compose(
            config_name="base",
            overrides=[
                "+exp=wbmanip/door_open_a2_base_lstm",
                "hydra.searchpath=[file://" + str(frozen_root.resolve()) + "]",
                "+ablation=" + FROZEN_GROUP + "/" + Path(config_name).stem,
            ],
            return_hydra_config=True,
        )
    composed_raw = OmegaConf.to_container(composed, resolve=False)
    if not isinstance(composed_raw, Mapping):
        raise R1Error("promoted Hydra composition did not produce a mapping")
    cfg = composed_raw.get("env", {}).get("config", {})
    if (
        cfg.get("a2_v20_formal_launch") is not True
        or cfg.get("a2_v20_R1_admission_manifest_sha256") != admission_sha256
    ):
        raise R1Error("Hydra composed source is not the promoted formal config")
    probe_command = [
        sys.executable,
        str(repo_root / "gr00t/rl/train_agent_trl.py"),
        "--cfg",
        "job",
        "--resolve",
        "+exp=wbmanip/door_open_a2_base_lstm",
        "hydra.searchpath=[file://" + str(frozen_root.resolve()) + "]",
        "+ablation=" + FROZEN_GROUP + "/" + Path(config_name).stem,
    ]
    probe = subprocess.run(
        probe_command,
        cwd=str(repo_root),
        env={**os.environ, "HYDRA_FULL_ERROR": "1"},
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.returncode != 0:
        detail = (probe.stderr or probe.stdout or "").strip().splitlines()
        raise R1Error(
            "promoted Hydra --cfg job --resolve failed: "
            + (detail[-1] if detail else "no diagnostic output")
        )
    if "a2_v20_formal_launch: true" not in probe.stdout:
        raise R1Error("Hydra --cfg job --resolve output omitted formal launch binding")
    return {
        "status": "HYDRA_RESOLVED",
        "config": config_name,
        "group": FROZEN_GROUP,
        "admission_manifest_sha256": admission_sha256,
        "cfg_job_resolve_command": probe_command,
        "resolved_formal_launch": True,
    }


def promote_configs(
    *,
    repo_root: Path,
    output_dir: Path,
    admission_manifest_sha256: str,
    admission_manifest: Path | None = None,
    chain_artifacts: Mapping[str, Path] | None = None,
) -> dict[str, Any]:
    root = repo_root.resolve()
    expected_output = (root / FROZEN_NAMESPACE).resolve()
    if output_dir.resolve() != expected_output:
        raise R1Error("formal promotion output must be scriptsFORhuman/v20_R1/frozen_formal")
    if output_dir.exists():
        raise R1Error(f"formal config namespace already exists: {output_dir}")
    if admission_manifest is None:
        raise R1Error("promotion requires the actual admission manifest path")
    admission = _validate_admission(admission_manifest, admission_manifest_sha256)
    chain = _validate_chain(chain_artifacts)
    preflight_hashes = _source_hashes_from_preflight(Path(chain["preflight"]))
    output_dir.mkdir(parents=True)
    rows = []
    for spec in GROUPS:
        source = root / "gr00t/rl/config/ablation/wbmanip" / spec["config"]
        if not source.is_file() or source.is_symlink():
            raise R1Error(f"missing or symlinked candidate config: {source}")
        source_sha = sha256_file(source)
        if preflight_hashes[spec["group"]] != source_sha:
            raise R1Error(f"candidate config hash differs from preflight for {spec['group']}")
        before = yaml.safe_load(source.read_text(encoding="utf-8"))
        if not isinstance(before, Mapping):
            raise R1Error(f"candidate config is not a mapping: {source}")
        before_cfg = before.get("env", {}).get("config", {})
        if (
            before_cfg.get("a2_v20_formal_launch") is not False
            or before_cfg.get("a2_v20_formal_values_frozen") is not True
        ):
            raise R1Error(f"candidate config is not an unpromoted frozen source: {source}")
        text = source.read_text(encoding="utf-8")
        marker = "    a2_v20_formal_launch: false\n"
        if text.count(marker) != 1:
            raise R1Error(f"candidate formal launch marker is not unique: {source}")
        promoted = text.replace(marker, "    a2_v20_formal_launch: true\n", 1)
        promoted = promoted.replace(
            "    a2_v20_formal_launch: true\n",
            "    a2_v20_formal_launch: true\n"
            + "    a2_v20_R1_admission_manifest_sha256: "
            + admission_manifest_sha256
            + "\n",
            1,
        )
        after = yaml.safe_load(promoted)
        if not isinstance(after, Mapping):
            raise R1Error(f"promoted config is not a mapping: {source}")
        after_cfg = after["env"]["config"]
        changed = {
            key
            for key in set(before_cfg) | set(after_cfg)
            if before_cfg.get(key) != after_cfg.get(key)
        }
        if changed != set(WHITELIST) or after_cfg["a2_v20_formal_launch"] is not True:
            raise R1Error(
                f"promotion semantic diff exceeds whitelist for {source}: {sorted(changed)}"
            )
        destination = output_dir / "ablation" / FROZEN_GROUP / spec["config"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(promoted, encoding="utf-8")
        hydra_binding = verify_hydra_promoted_group(
            repo_root=root,
            frozen_root=output_dir,
            config_name=spec["config"],
            admission_sha256=admission_manifest_sha256,
        )
        rows.append(
            {
                "group": spec["group"],
                "source": str(source),
                "source_sha256": source_sha,
                "destination": str(destination),
                "promoted_sha256": hashlib.sha256(promoted.encode()).hexdigest(),
                "admission_manifest_sha256": admission_manifest_sha256,
                "hydra_binding": hydra_binding,
            }
        )
    result = {
        "schema": SCHEMA,
        "plan_id": PLAN_ID,
        "status": POLICY_PASS,
        "admission_manifest_sha256": admission_manifest_sha256,
        "chain_artifacts": chain,
        "whitelist": list(WHITELIST),
        "configs": rows,
        "formal_ready": True,
        "hydra_group": FROZEN_GROUP,
        "hydra_probe": "python train_agent_trl.py --cfg job --resolve",
    }
    write_json_no_overwrite(output_dir / "promotion_manifest.json", result)
    return result


def _require_blocked_r1_cli_opt_in() -> None:
    if "BASE_V20_ALLOW_BLOCKED_R1_EXECUTION" not in __import__("os").environ:
        print(
            "R1 execution is blocked by default; set BASE_V20_ALLOW_BLOCKED_R1_EXECUTION explicitly to run historical tooling",
            file=__import__("sys").stderr,
        )
        raise SystemExit(2)


if __name__ == "__main__":
    _require_blocked_r1_cli_opt_in()
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--admission-manifest", type=Path, required=True)
    parser.add_argument("--admission-manifest-sha256", required=True)
    args = parser.parse_args()
    promote_configs(
        repo_root=args.repo_root,
        output_dir=args.output_dir,
        admission_manifest=args.admission_manifest,
        admission_manifest_sha256=args.admission_manifest_sha256,
    )
