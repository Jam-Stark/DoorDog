"""Generate the formal R1 launcher only from an admitted frozen config set."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _r1_common import (  # noqa: E402
    GROUPS,
    PLAN_ID,
    POLICY_PASS,
    R1Error,
    R1_FORMAL_ROOT,
    R1_LAUNCHER_ROOT,
    RUNTIME_PASS,
    validate_clean_expected_git,
    device_env,
    exact_digest,
    load_json,
    sha256_file,
    validate_gpu,
    write_json_no_overwrite,
)

SCHEMA = "a2_piper_v20_R1_formal_launcher_v3"
FROZEN_NAMESPACE = "scriptsFORhuman/v20_R1/frozen_formal"
FROZEN_GROUP = "a2_v20_R1_frozen"


def _validate_frozen_config(config: Path, admission_sha256: str) -> dict[str, Any]:
    if not config.is_file() or config.is_symlink():
        raise R1Error(f"formal launcher accepts frozen_formal regular files only: {config}")
    try:
        parsed = yaml.safe_load(config.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise R1Error(f"invalid frozen formal YAML: {config}") from exc
    if not isinstance(parsed, Mapping):
        raise R1Error(f"frozen formal config must be a mapping: {config}")
    cfg = parsed.get("env", {}).get("config", {})
    if (
        cfg.get("a2_v20_formal_launch") is not True
        or cfg.get("a2_v20_R1_admission_manifest_sha256") != admission_sha256
    ):
        raise R1Error(f"frozen formal config is not bound to admission manifest: {config}")
    if (
        parsed.get("checkpoint_load_mode") != "policy_only"
        or parsed.get("auto_load_latest") is not False
        or parsed.get("headless") is not True
    ):
        raise R1Error(f"frozen formal config checkpoint/topology contract failed: {config}")
    return dict(parsed)


def _validate_admission(
    repo_root: Path,
    admission_manifest: Path,
    admission_sha256: str,
) -> Mapping[str, Any]:
    exact_digest(admission_sha256, name="formal admission SHA256", length=64)
    if sha256_file(admission_manifest) != admission_sha256:
        raise R1Error("formal launcher admission manifest SHA mismatch")
    payload = load_json(admission_manifest)
    if (
        not isinstance(payload, Mapping)
        or payload.get("plan_id") != PLAN_ID
        or payload.get("status") != POLICY_PASS
    ):
        raise R1Error("formal launcher requires POLICY PASS admission manifest")
    identity = validate_clean_expected_git(repo_root, expected_branch="A2_Piper")
    if payload.get("git_commit") is not None and payload["git_commit"] != identity["commit"]:
        raise R1Error("formal admission commit does not match current commit")
    promotion = payload.get("promotion_manifest")
    if not isinstance(promotion, Mapping):
        raise R1Error("formal admission must bind promotion_manifest")
    rows = promotion.get("configs")
    if not isinstance(rows, list) or len(rows) != len(GROUPS):
        raise R1Error("formal admission promotion rows must contain all seven groups")
    return payload


def build_training_command(
    *,
    repo_root: Path,
    spec: Mapping[str, Any],
    accelerate_path: str = "accelerate",
    artifact_root: Path,
    timestamp: str,
    wandb_mode: str = "online",
    admission_manifest_sha256: str | None = None,
) -> dict[str, Any]:
    root = repo_root.resolve()
    if wandb_mode not in ("online", "offline"):
        raise R1Error("WANDB_MODE must be explicit")
    gpu = validate_gpu(spec["gpu"])
    if admission_manifest_sha256 is None:
        raise R1Error("formal command requires exact admission SHA")
    exact_digest(admission_manifest_sha256, name="admission SHA256", length=64)
    config_name = str(spec["config"])
    frozen_root = root / FROZEN_NAMESPACE
    config = frozen_root / "ablation" / FROZEN_GROUP / config_name
    expected_root = (root / R1_FORMAL_ROOT / timestamp / str(spec["group"])).resolve()
    if artifact_root.resolve() != expected_root:
        raise R1Error("formal artifact root must be canonical")
    _validate_frozen_config(config, admission_manifest_sha256)
    port = 29740 + int(str(spec["group"])[1:]) - 1
    command = [
        accelerate_path,
        "launch",
        "--num_processes",
        "1",
        "--main_process_port",
        str(port),
        "gr00t/rl/train_agent_trl.py",
        "+exp=wbmanip/door_open_a2_base_lstm",
        "hydra.searchpath=[file://" + str(frozen_root.resolve()) + "]",
        "+ablation=" + FROZEN_GROUP + "/" + config.stem,
        "num_envs=4096",
        "algo.trl.num_total_batches=2500",
        "callbacks.model_save.save_frequency=250",
        "headless=true",
        "simulator.config.cameras.enable_cameras=false",
        "checkpoint_load_mode=policy_only",
        "auto_load_latest=false",
        "base_dir=" + R1_FORMAL_ROOT,
        "project_name=base_v20_R1",
        "experiment_name=" + str(spec["group"]),
        "timestamp=" + timestamp,
        "experiment_dir=" + str(expected_root),
        "device=cuda:" + str(gpu),
        "a2_v20_R1_admission_manifest_sha256=" + admission_manifest_sha256,
    ]
    env = device_env(gpu)
    env["WANDB_MODE"] = wandb_mode
    if "CUDA_VISIBLE_DEVICES" in env:
        raise R1Error("non-render formal training must not set CUDA_VISIBLE_DEVICES")
    return {
        "group": spec["group"],
        "gpu": gpu,
        "env": env,
        "command": command,
        "num_envs": 4096,
        "num_processes": 1,
        "admission_manifest_sha256": admission_manifest_sha256,
        "artifact_root": str(expected_root),
        "timestamp": timestamp,
        "status": "COMMAND_BOUND",
    }


def generate_launcher(
    *,
    repo_root: Path,
    launcher_root: Path,
    artifact_root: Path,
    manifest_sha256: str,
    timestamp: str,
    wandb_mode: str = "online",
    admission_manifest: Path | None = None,
) -> dict[str, Any]:
    root = repo_root.resolve()
    expected_launcher = (root / R1_LAUNCHER_ROOT / timestamp).resolve()
    expected_artifact = (root / R1_FORMAL_ROOT / timestamp).resolve()
    if launcher_root.resolve() != expected_launcher or artifact_root.resolve() != expected_artifact:
        raise R1Error("formal launcher/output roots must be canonical")
    if launcher_root.exists() or artifact_root.exists():
        raise R1Error("formal R1 launcher/output roots must not already exist")
    if admission_manifest is None:
        raise R1Error("formal launcher requires the actual admission manifest")
    admission = _validate_admission(root, admission_manifest, manifest_sha256)
    launcher_root.mkdir(parents=True)
    rows = []
    for spec in GROUPS:
        group_root = artifact_root / spec["group"]
        row = build_training_command(
            repo_root=root,
            spec=spec,
            artifact_root=group_root,
            timestamp=timestamp,
            wandb_mode=wandb_mode,
            admission_manifest_sha256=manifest_sha256,
        )
        group_root.mkdir(parents=True)
        (launcher_root / (spec["group"] + ".command")).write_text(
            " ".join(row["command"]) + chr(10), encoding="utf-8"
        )
        rows.append(row)
    manifest = {
        "schema": SCHEMA,
        "plan_id": PLAN_ID,
        "status": RUNTIME_PASS,
        "admission_manifest": str(admission_manifest.resolve()),
        "admission_manifest_sha256": manifest_sha256,
        "git_commit": admission.get("git_commit"),
        "topology": {
            "envs_per_group": 4096,
            "groups": 7,
            "gpus": list(range(7)),
            "reserved_gpu": 7,
            "formal_training": True,
        "hydra_frozen_group": FROZEN_GROUP,
        "hydra_searchpath": "file://" + str((root / FROZEN_NAMESPACE).resolve()),
        },
        "launcher_root": str(launcher_root),
        "artifact_root": str(artifact_root),
        "timestamp": timestamp,
        "groups": rows,
        "visibility_mask_forbidden": True,
    }
    write_json_no_overwrite(launcher_root / "manifest.json", manifest)
    return manifest


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
    parser.add_argument("--launcher-root", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--timestamp", required=True)
    args = parser.parse_args()
    generate_launcher(
        repo_root=args.repo_root,
        launcher_root=args.launcher_root,
        artifact_root=args.artifact_root,
        admission_manifest=args.manifest,
        manifest_sha256=args.manifest_sha256,
        timestamp=args.timestamp,
    )
