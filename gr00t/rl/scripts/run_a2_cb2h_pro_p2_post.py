#!/usr/bin/env python3
"""Run and adjudicate the sealed C-B2H P2 B1/B2 formal Student pair.

The post runner is intentionally independent from training.  It consumes one
immutable retry3 pair snapshot, plans exactly six formal Student evaluations
(B1/B2 x three replicates), executes them serially when explicitly requested,
and seals one relative architecture decision.  The CPU dry-run only validates
inputs and prints commands; it never discovers checkpoints or creates output
roots.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gr00t.rl.scripts import run_a2_cb2h_pro_p2 as p2
from gr00t.rl.scripts import run_a2_student_eval_v19 as student_eval


PAIR_ROOT = (REPO_ROOT / "logs_rl/cb2h_pro_p2_b1_b2_gpu7-retry3-20260804").resolve()
PAIR_MANIFEST_FILENAME = "pair_manifest.json"
BRANCH_MANIFEST_FILENAME = "p2_branch_manifest.json"
PAIR_MANIFEST_SHA256 = "1dbc44065f103873412f4cc1063547f2e97b0ed458f199d1e6c1f196b0d269da"
PAIR_CONTENT_SHA256 = "193177e29015eff1b4e6d8893b86c77bd20c040abda2e56b9363677aa496ba1c"
BRANCH_MANIFEST_SHA256 = {
    "b1": "77913018528ca4576e9e5dd71e4076a55fd52d282fb4ad7e5d4ca5cf3695cc6d",
    "b2": "237cdbb950ac94d3b37e3f98ca5dcec6802ccf77022dccae21cbc455077a1062",
}
BRANCH_CHECKPOINT_SHA256 = {
    "b1": "cad89103bfcf877dcf0987d3dc8331ed60f215c1d6dffc1c6755a063db5912a5",
    "b2": "c02b17116ba29ed14c4c49090650821cd77d3cd6a379758ea036468f0f4a33ca",
}
BRANCH_CONFIG_SHA256 = {
    "b1": "bd1c4367858df27028b9e29d724bc3caa07d4bd2e274b91ef19d72b70b80a304",
    "b2": "a2bac1759fa9b95697b2988b0a883e57d53eab78b79ac04ca6d1b583ad136e29",
}
COMMON_ARTIFACT_SHA256 = "37dd3dba123a1906dadc052f9f9490d1c392ac9e988c2acb4008209a32c6f4ef"
COMMON_B1_STEP0_SHA256 = "ad4b8a0ef90b4dbe0d3f4c898d1508a83435b0616786481d94b05aae522a9365"
COMMON_B2_STEP0_SHA256 = "26ced39a5f3677f9aba332cc1b71f96aa11919a5e14598b0d1eed60e02370828"
COMMON_CORE_SHA256 = "16e0aaeefc64c3c3d64c95e6fab1baf4cf4e838a0f0a258dfc267e9004e9f60e"
COMMON_KEY_SCHEMA_SHA256 = "b608ce21d8477983aa9a78a8db4139140309f39dd8ca3e5fc1aba5327abefd97"
COMMON_CONFIG_SHA256 = "9b3121b2d92b79237d0a871b5ff96eab8d4e32165627075170dafe7a3c6e4cfa"
EXPECTED_RUNTIME_REPOSITORY = Path("/tmp/cb2h_v19_runtime.waPJHftX/c18").resolve()
EXPECTED_RUNTIME_COMMIT = "c18aea8bdc1c76ce850b5223663d0ad8a7474c0a"
EXPECTED_GPU_INDEX = "7"
EXPECTED_LOGICAL_GPU_INDEX = 0
EXPECTED_LOGICAL_DEVICE = "cuda:0"
EXPECTED_GPU_UUID = "GPU-7c8cb1d2-4ebf-e2e3-35ad-fa0f6f72924d"
EXPECTED_GPU_BINDING_MODE = "single-visible-logical-cuda0-v3"
EXPECTED_CUDA_DEVICE_ORDER = "PCI_BUS_ID"
VRAM_LIMIT_MIB = 47104
EXPECTED_GLOBAL_STEP = 500
EXPECTED_NUM_ENVS = 16
EXPECTED_EPISODES_PER_REPLICATE = 16
EXPECTED_EPISODES = EXPECTED_EPISODES_PER_REPLICATE
EXPECTED_TOTAL_EPISODES = 48
BRANCHES = ("b1", "b2")
POST_BRANCHES = BRANCHES
REPLICATE_IDS = ("replicate_01", "replicate_02", "replicate_03")
FORMAL_METRICS_FILENAME = "formal_student_metrics.json"
FORMAL_SELECTION_FILENAME = "student_selection.json"
TELEMETRY_FILENAME = "gpu_telemetry.json"
PROCESS_STDOUT_FILENAME = "post_runner.stdout.log"
PROCESS_STDERR_FILENAME = "post_runner.stderr.log"
FAILURE_FILENAME = "p2_post_child_failure.json"
ROOT_FAILURE_FILENAME = "p2_post_failure.json"
FINAL_MANIFEST_FILENAME = "p2_post_adjudication_manifest.json"
POST_SCHEMA = "a2_cb2h_pro_p2_post_v1"
FAILURE_SCHEMA = "a2_cb2h_pro_p2_post_failure_v1"
CHILD_FAILURE_SCHEMA = "a2_cb2h_pro_p2_post_child_failure_v1"
# Keep the post-run artifact on the exact P2 telemetry contract.  The post
# runner may add path/hash references to its manifest, but it must not invent a
# second, weaker telemetry schema.
TELEMETRY_SCHEMA = p2.P2_TELEMETRY_SCHEMA
DECISION_SELECT_B2 = "SELECT_B2"
DECISION_SELECT_B1 = "SELECT_B1"
EVAL_PYTHON = "/home/baoquanc/anaconda3/envs/isaaclab/bin/python"
EVAL_SCRIPT = (REPO_ROOT / "gr00t/rl/scripts/run_a2_student_eval_v19.py").resolve()
TEACHER_IDENTITY = {
    "checkpoint": {
        "path": str(p2.TEACHER_CHECKPOINT),
        "sha256": p2.TEACHER_CHECKPOINT_SHA256,
    },
    "config": {"path": str(p2.TEACHER_CONFIG), "sha256": p2.TEACHER_CONFIG_SHA256},
    "manifest": {"path": str(p2.TEACHER_MANIFEST), "sha256": p2.TEACHER_MANIFEST_SHA256},
}
EXPECTED_EFFECTIVENESS_STAGE0_REDUCTION = 4
EXPECTED_EFFECTIVENESS_STAGE_MEAN_DELTA = 0.20
EXPECTED_DOORFRAME_REDUCTION_RATIO = 0.20
EXPECTED_STAGE2_DECREASE_MAX = 2
EXPECTED_SAFETY_MEAN_WORSENING_RATIO = 0.10


class P2PostBlocked(RuntimeError):
    """A required post-training input or gate failed closed."""


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("post JSON cannot contain non-finite floats")
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _json_value(child) for key, child in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_json_value(child) for child in value]
    raise TypeError(f"post JSON value is not serializable: {type(value).__name__}")


def canonical_json(value: Any) -> str:
    return json.dumps(_json_value(value), sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _require_sha(value: Any, name: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise TypeError(f"{name} must be a lowercase SHA256")
    return value


def _strict_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    return value


def _strict_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _confined(path_value: Any, root: Path, name: str, *, strict: bool = True) -> Path:
    if not isinstance(path_value, str) or not path_value:
        raise TypeError(f"{name} path must be a non-empty string")
    path = Path(path_value).expanduser().resolve(strict=strict)
    root = root.expanduser().resolve()
    if not path.is_relative_to(root):
        raise P2PostBlocked(f"{name} escapes immutable root: {path}")
    return path


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise P2PostBlocked(f"post JSON artifact is unreadable: {path}") from exc
    if not isinstance(value, Mapping):
        raise TypeError(f"post JSON artifact must be an object: {path}")
    return dict(value)


def _content_hash(payload: Mapping[str, Any], field: str = "content_sha256") -> str:
    unsigned = dict(payload)
    unsigned.pop(field, None)
    unsigned.pop("seal_artifact", None)
    return sha256_bytes(canonical_json(unsigned).encode("utf-8"))


def _artifact_ref(path: Path, expected_sha: str, name: str, *, root: Path | None = None) -> dict[str, Any]:
    path = path.expanduser().resolve(strict=True)
    if root is not None:
        _confined(str(path), root, name)
    actual = sha256_file(path)
    if actual != expected_sha:
        raise P2PostBlocked(f"{name} SHA256 drifted: expected={expected_sha} actual={actual}")
    return {"path": str(path), "sha256": actual, "size": path.stat().st_size}


def _expected_teacher_identity() -> dict[str, Any]:
    # The G2 triplet is an external immutable input, not discovered from a
    # candidate output.  Verify all three bytes before accepting the pair.
    for label, ref in TEACHER_IDENTITY.items():
        path = Path(ref["path"])
        _artifact_ref(path, ref["sha256"], f"Teacher {label}")
    return json.loads(canonical_json(TEACHER_IDENTITY))


def _expected_branch_command(branch: str, branch_root: Path, common_root: Path) -> tuple[str, ...]:
    if branch not in BRANCHES:
        raise ValueError(f"unknown P2 branch {branch!r}")
    trusted_artifact = COMMON_ARTIFACT_SHA256 if branch == "b2" else "REQUIRED_AFTER_B1_STEP0_SEAL"
    trusted_step0 = COMMON_B1_STEP0_SHA256 if branch == "b2" else "REQUIRED_AFTER_B1_STEP0_SEAL"
    overrides = p2.build_training_overrides(
        branch,
        branch_root,
        common_root,
        trusted_artifact_sha256=trusted_artifact,
        trusted_source_step0_manifest_sha256=trusted_step0,
    )
    command = list(p2._build_branch_command_with_overrides(branch, branch_root, common_root, overrides))
    command[0] = EVAL_PYTHON
    return tuple(command)


def _validate_branch_runtime(branch: str, runtime: Mapping[str, Any]) -> None:
    if runtime.get("repository") != str(EXPECTED_RUNTIME_REPOSITORY):
        raise P2PostBlocked(f"{branch} runtime repository is not pinned c18")
    if runtime.get("commit") != EXPECTED_RUNTIME_COMMIT:
        raise P2PostBlocked(f"{branch} runtime commit is not c18")
    if runtime.get("finder") != "V19RuntimeFinder" or runtime.get("scenario_file_pin") is not True:
        raise P2PostBlocked(f"{branch} runtime finder/scenario pin drifted")
    sources = runtime.get("module_sources")
    if not isinstance(sources, Mapping) or not sources:
        raise P2PostBlocked(f"{branch} runtime module source seal is missing")
    for source in sources.values():
        if not isinstance(source, str) or not source.startswith(str(EXPECTED_RUNTIME_REPOSITORY) + "/"):
            raise P2PostBlocked(f"{branch} runtime module source escapes c18: {source!r}")
    try:
        head = subprocess.run(
            ["git", "-C", str(EXPECTED_RUNTIME_REPOSITORY), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "-C", str(EXPECTED_RUNTIME_REPOSITORY), "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        raise P2PostBlocked("pinned c18 runtime clean-commit check failed") from exc
    if head != EXPECTED_RUNTIME_COMMIT or dirty:
        raise P2PostBlocked("pinned c18 runtime commit is not the exact clean commit")


def _validate_adjacent_p2_actor_contract(config_path: Path, branch: str) -> None:
    """Validate the saved retry3 config against the real P2 actor contract."""
    try:
        from omegaconf import OmegaConf

        config = OmegaConf.load(config_path)
        p2.validate_composed_config(config, branch)
        actor = config.algo.config.actor
        view_contract = actor.view_contract
        expected_target = (
            "gr00t.rl.trl.modules.vision_actor_critic_modules_p2_recurrent."
            + ("DualD435VisionRecurrentActor" if branch == "b1" else "DualD435HeadVisionRecurrentActor")
        )
        if actor._target_ != expected_target:
            raise RuntimeError(f"{branch} adjacent actor target drifted: {actor._target_!r}")
        if view_contract.d435i_forward_mode != "packed":
            raise RuntimeError(f"{branch} adjacent actor D435 mode is not packed")
        expected_meta_dim = 4 if branch == "b1" else 6
        if int(view_contract.camera_meta_dim) != expected_meta_dim:
            raise RuntimeError(f"{branch} adjacent camera_meta_dim drifted")
    except Exception as exc:
        if isinstance(exc, P2PostBlocked):
            raise
        raise P2PostBlocked(f"{branch} adjacent retry3 config failed the P2 actor contract") from exc


def _validate_branch_manifest(
    branch: str,
    root: Path,
    common_root: Path,
    manifest: Mapping[str, Any],
    manifest_path: Path,
    manifest_sha: str,
    pair: Mapping[str, Any],
) -> dict[str, Any]:
    expected_keys = {
        "architecture", "branch", "command", "command_sha256", "common_init",
        "content_sha256", "effective_training_contract", "final_checkpoint",
        "final_config", "lifecycle", "root", "runtime", "schema", "teacher",
        "runtime_metrics", "telemetry",
    }
    if set(manifest) != expected_keys:
        raise P2PostBlocked(f"{branch} branch manifest schema drifted")
    if manifest.get("schema") != p2.P2_BRANCH_SCHEMA or manifest.get("branch") != branch:
        raise P2PostBlocked(f"{branch} branch manifest schema/identity drifted")
    expected_arch = p2.ARCHITECTURES[branch]
    if manifest.get("architecture") != expected_arch or manifest.get("root") != str(root):
        raise P2PostBlocked(f"{branch} branch architecture/root drifted")
    if manifest.get("teacher") != TEACHER_IDENTITY:
        raise P2PostBlocked(f"{branch} G2 Teacher identity drifted")
    command = manifest.get("command")
    expected_command = _expected_branch_command(branch, root, common_root)
    if command != list(expected_command):
        raise P2PostBlocked(f"{branch} sealed training command drifted")
    command_sha = _require_sha(manifest.get("command_sha256"), f"{branch} command SHA")
    if command_sha != sha256_bytes(canonical_json(command).encode("utf-8")):
        raise P2PostBlocked(f"{branch} sealed training command hash drifted")
    if _require_sha(manifest.get("content_sha256"), f"{branch} content SHA") != _content_hash(manifest):
        raise P2PostBlocked(f"{branch} branch content hash drifted")
    _validate_branch_runtime(branch, manifest["runtime"])
    if manifest.get("effective_training_contract") != dict(p2.P2_COMMON_INIT_CONTRACT["effective_training"]):
        raise P2PostBlocked(f"{branch} effective training contract drifted")

    common = manifest["common_init"]
    expected_common = pair["common_init"]
    if not isinstance(common, Mapping) or common.get("artifact") != expected_common["artifact"]:
        raise P2PostBlocked(f"{branch} common-init artifact identity drifted")
    expected_step0 = pair[f"{branch}_step0"]
    if common.get("step0_manifest") != expected_step0:
        raise P2PostBlocked(f"{branch} common-init step0 identity drifted")
    if common.get("common_core_sha256") != COMMON_CORE_SHA256:
        raise P2PostBlocked(f"{branch} common core aggregate drifted")

    lifecycle = manifest["lifecycle"]
    if not isinstance(lifecycle, Mapping) or lifecycle.get("controlled") is not True or lifecycle.get("natural") is not False or lifecycle.get("status") != "UNRESOLVED":
        raise P2PostBlocked(f"{branch} lifecycle is not controlled/unresolved")
    proof = lifecycle.get("proof")
    if not isinstance(proof, Mapping):
        raise P2PostBlocked(f"{branch} lifecycle proof is missing")
    proof_path = _confined(proof.get("path"), root, f"{branch} lifecycle proof")
    if proof_path != root / "pre_teardown_completion_proof.json":
        raise P2PostBlocked(f"{branch} lifecycle proof path drifted")
    _artifact_ref(proof_path, _require_sha(proof.get("sha256"), f"{branch} proof SHA"), f"{branch} lifecycle proof", root=root)
    proof_payload = _load_json(proof_path)
    if proof_payload.get("branch") != branch or proof_payload.get("root") != str(root) or proof_payload.get("lifecycle_status") != "UNRESOLVED" or proof_payload.get("controlled_post_training_exit") is not True:
        raise P2PostBlocked(f"{branch} lifecycle proof identity drifted")
    if _require_sha(proof_payload.get("manifest_content_sha256"), f"{branch} proof content SHA") != _content_hash(proof_payload, "manifest_content_sha256"):
        raise P2PostBlocked(f"{branch} lifecycle proof content hash drifted")

    final_checkpoint = manifest["final_checkpoint"]
    if not isinstance(final_checkpoint, Mapping):
        raise TypeError(f"{branch} final checkpoint ref must be a mapping")
    checkpoint_path = _confined(final_checkpoint.get("path"), root, f"{branch} checkpoint")
    if checkpoint_path != root / "model_step_000500.pt" or final_checkpoint.get("global_step") != EXPECTED_GLOBAL_STEP:
        raise P2PostBlocked(f"{branch} final checkpoint step/path drifted")
    checkpoint_ref = _artifact_ref(checkpoint_path, BRANCH_CHECKPOINT_SHA256[branch], f"{branch} checkpoint", root=root)
    if final_checkpoint.get("sha256") != checkpoint_ref["sha256"]:
        raise P2PostBlocked(f"{branch} final checkpoint ref drifted: sha256")
    if final_checkpoint.get("size") != checkpoint_ref["size"]:
        raise P2PostBlocked(f"{branch} final checkpoint ref drifted: size")

    final_config = manifest["final_config"]
    if not isinstance(final_config, Mapping):
        raise TypeError(f"{branch} final config ref must be a mapping")
    config_path = _confined(final_config.get("path"), root, f"{branch} config")
    if config_path != root / "config.yaml" or final_config.get("branch") != branch or final_config.get("architecture") != expected_arch:
        raise P2PostBlocked(f"{branch} final config identity drifted")
    config_ref = _artifact_ref(config_path, BRANCH_CONFIG_SHA256[branch], f"{branch} config", root=root)
    if final_config.get("sha256") != config_ref["sha256"]:
        raise P2PostBlocked(f"{branch} final config SHA ref drifted")
    if final_config.get("size") != config_ref["size"]:
        raise P2PostBlocked(f"{branch} final config size ref drifted")
    if final_config.get("effective_training_contract") != dict(p2.P2_COMMON_INIT_CONTRACT["effective_training"]):
        raise P2PostBlocked(f"{branch} final config training provenance drifted")
    if final_config.get("common_init", {}).get("runtime_identity", {}).get("runtime_commit") != EXPECTED_RUNTIME_COMMIT:
        raise P2PostBlocked(f"{branch} final config c18 identity drifted")
    _validate_adjacent_p2_actor_contract(config_path, branch)

    telemetry = manifest["telemetry"]
    if not isinstance(telemetry, Mapping) or not isinstance(telemetry.get("artifact"), Mapping) or not isinstance(telemetry.get("validated"), Mapping):
        raise P2PostBlocked(f"{branch} telemetry seal is incomplete")
    telemetry_ref = telemetry["artifact"]
    telemetry_path = _confined(telemetry_ref.get("path"), root, f"{branch} telemetry")
    if telemetry_path != root / "gpu_telemetry.json":
        raise P2PostBlocked(f"{branch} telemetry path drifted")
    _artifact_ref(telemetry_path, _require_sha(telemetry_ref.get("sha256"), f"{branch} telemetry SHA"), f"{branch} telemetry", root=root)
    telemetry_payload = _load_json(telemetry_path)
    try:
        validated_telemetry = p2.validate_gpu_telemetry(telemetry_payload)
    except BaseException as exc:
        raise P2PostBlocked(f"{branch} sealed training telemetry is invalid") from exc
    if telemetry.get("validated") != validated_telemetry:
        raise P2PostBlocked(f"{branch} telemetry validation snapshot drifted")
    if float(validated_telemetry["peak_vram_mib"]) >= VRAM_LIMIT_MIB:
        raise P2PostBlocked(f"{branch} training telemetry reaches VRAM limit")

    runtime_metrics = manifest["runtime_metrics"]
    if not isinstance(runtime_metrics, Mapping):
        raise TypeError(f"{branch} runtime metrics ref must be a mapping")
    metrics_path = _confined(runtime_metrics.get("path"), root, f"{branch} runtime metrics")
    if metrics_path != root / "runtime_metrics.json":
        raise P2PostBlocked(f"{branch} runtime metrics path drifted")
    _artifact_ref(metrics_path, _require_sha(runtime_metrics.get("sha256"), f"{branch} runtime metrics SHA"), f"{branch} runtime metrics", root=root)
    metrics = _load_json(metrics_path)
    for field, expected in {
        "global_step_start": 0,
        "global_step_final": EXPECTED_GLOBAL_STEP,
        "completed_iterations": EXPECTED_GLOBAL_STEP,
        "callbacks": EXPECTED_GLOBAL_STEP,
        "backward_calls": EXPECTED_GLOBAL_STEP * p2.EXPECTED_NUM_MINI_BATCHES,
        "optimizer_steps": EXPECTED_GLOBAL_STEP * p2.EXPECTED_NUM_MINI_BATCHES,
        "scheduler_step_count": EXPECTED_GLOBAL_STEP,
        "runtime": {"runtime_repository": str(EXPECTED_RUNTIME_REPOSITORY), "runtime_commit": EXPECTED_RUNTIME_COMMIT},
    }.items():
        if metrics.get(field) != expected:
            raise P2PostBlocked(f"{branch} runtime metric {field} drifted")
    return {
        "branch": branch,
        "architecture": expected_arch,
        "root": str(root),
        "manifest": dict(manifest),
        "manifest_ref": {"path": str(manifest_path), "sha256": manifest_sha, "size": manifest_path.stat().st_size},
        "final_checkpoint": dict(final_checkpoint),
        "final_config": dict(final_config),
        "common_init": dict(common),
        "runtime": dict(manifest["runtime"]),
        "teacher": dict(manifest["teacher"]),
    }


def validate_pair_manifest(
    pair_root: Path = PAIR_ROOT,
    *,
    pair_manifest_sha256: str = PAIR_MANIFEST_SHA256,
    validate_external_teacher: bool = True,
) -> dict[str, Any]:
    """Validate one immutable retry3 pair and return its frozen identities."""
    pair_root = pair_root.expanduser().resolve(strict=True)
    pair_path = pair_root / "serial" / PAIR_MANIFEST_FILENAME
    if not pair_path.is_file():
        raise FileNotFoundError(f"P2 post pair manifest is unavailable: {pair_path}")
    expected_pair_sha = _require_sha(pair_manifest_sha256, "pair manifest SHA")
    actual_pair_sha = sha256_file(pair_path)
    if actual_pair_sha != expected_pair_sha:
        raise P2PostBlocked(f"pair manifest SHA drifted: expected={expected_pair_sha} actual={actual_pair_sha}")
    pair = _load_json(pair_path)
    expected_keys = {
        "artifact_sha256", "b1_step0", "b2_step0", "branch_manifests", "common_init",
        "config_sha256", "content_sha256", "core_aggregate_sha256", "core_key_schema_sha256",
        "downstream_rng_identity", "ordered_core_key_identities", "ordered_core_keys",
        "runtime_identity", "schema", "seed", "source_branch", "target_branch",
    }
    if set(pair) != expected_keys:
        raise P2PostBlocked("pair manifest schema has unexpected or missing fields")
    if pair.get("schema") != p2.P2_PAIR_SCHEMA or pair.get("source_branch") != "b1" or pair.get("target_branch") != "b2" or pair.get("seed") != 0:
        raise P2PostBlocked("pair manifest B1/B2/seed identity drifted")
    pair_content = _require_sha(pair.get("content_sha256"), "pair content SHA")
    if pair_content != PAIR_CONTENT_SHA256 or pair_content != _content_hash(pair):
        raise P2PostBlocked("pair manifest content hash drifted")
    if pair.get("artifact_sha256") != COMMON_ARTIFACT_SHA256 or pair.get("core_aggregate_sha256") != COMMON_CORE_SHA256 or pair.get("core_key_schema_sha256") != COMMON_KEY_SCHEMA_SHA256 or pair.get("config_sha256") != COMMON_CONFIG_SHA256:
        raise P2PostBlocked("pair common-init identity drifted")
    if pair.get("runtime_identity") != {"runtime_repository": str(EXPECTED_RUNTIME_REPOSITORY), "runtime_commit": EXPECTED_RUNTIME_COMMIT}:
        raise P2PostBlocked("pair runtime identity drifted")

    common_root = pair_root / "common_init"
    artifact_path = _confined(pair["common_init"]["artifact"]["path"], pair_root, "pair common-init artifact")
    if artifact_path != common_root / "b1_common_init.pt":
        raise P2PostBlocked("pair common-init artifact path drifted")
    _artifact_ref(artifact_path, COMMON_ARTIFACT_SHA256, "pair common-init artifact", root=pair_root)
    seal_path = common_root / "b1_common_init_seal.json"
    seal = _load_json(seal_path)
    seal_ref = pair["common_init"].get("seal_artifact")
    if not isinstance(seal_ref, Mapping) or _confined(seal_ref.get("path"), pair_root, "pair common-init seal") != seal_path:
        raise P2PostBlocked("pair common-init seal artifact path drifted")
    _artifact_ref(seal_path, _require_sha(seal_ref.get("sha256"), "pair common-init seal SHA"), "pair common-init seal", root=pair_root)
    pair_common_without_artifact = dict(pair["common_init"])
    pair_common_without_artifact.pop("seal_artifact", None)
    if seal != pair_common_without_artifact:
        raise P2PostBlocked("pair common-init seal snapshot drifted")
    if _require_sha(seal.get("content_sha256"), "common-init content SHA") != _content_hash(seal):
        raise P2PostBlocked("common-init content hash drifted")
    if pair["common_init"].get("runtime_identity") != pair["runtime_identity"] or pair["common_init"].get("seed") != 0:
        raise P2PostBlocked("common-init runtime/seed identity drifted")

    step0_values: dict[str, dict[str, Any]] = {}
    for branch, expected_sha in (("b1", COMMON_B1_STEP0_SHA256), ("b2", COMMON_B2_STEP0_SHA256)):
        key = f"{branch}_step0"
        ref = pair[key]
        if not isinstance(ref, Mapping):
            raise TypeError(f"pair {key} must be a mapping")
        path = _confined(ref.get("path"), pair_root, f"pair {key}")
        expected_path = common_root / f"{branch}_step0_manifest.json"
        if path != expected_path:
            raise P2PostBlocked(f"pair {key} path drifted")
        _artifact_ref(path, expected_sha, f"pair {key}", root=pair_root)
        if ref.get("sha256") != expected_sha or ref.get("size") != path.stat().st_size:
            raise P2PostBlocked(f"pair {key} ref drifted")
        step0 = _load_json(path)
        if step0.get("branch") != branch or step0.get("seed") != 0 or step0.get("global_step") != 0 or step0.get("artifact_sha256") != COMMON_ARTIFACT_SHA256 or step0.get("common_core_sha256") != COMMON_CORE_SHA256 or step0.get("common_core_key_schema_sha256") != COMMON_KEY_SCHEMA_SHA256:
            raise P2PostBlocked(f"pair {key} common-init provenance drifted")
        if step0.get("runtime_identity") != pair["runtime_identity"]:
            raise P2PostBlocked(f"pair {key} runtime identity drifted")
        step0_values[branch] = step0
    if step0_values["b2"].get("rng_before_policy_identity") != step0_values["b1"].get("rng_before_policy_identity"):
        raise P2PostBlocked("B1/B2 pre-policy RNG identity drifted")
    if step0_values["b2"].get("rng_downstream_identity") != step0_values["b1"].get("rng_downstream_identity"):
        raise P2PostBlocked("B1/B2 downstream RNG identity drifted")
    if pair.get("downstream_rng_identity") != step0_values["b1"].get("rng_downstream_identity"):
        raise P2PostBlocked("pair downstream RNG identity drifted")
    if pair.get("ordered_core_keys") != step0_values["b1"].get("common_core_keys") or pair.get("ordered_core_key_identities") != step0_values["b1"].get("common_core_key_identities"):
        raise P2PostBlocked("pair ordered common-core identity drifted")
    if step0_values["b1"].get("common_core_key_identities") != step0_values["b2"].get("common_core_key_identities"):
        raise P2PostBlocked("B1/B2 common-core key identities differ")

    if validate_external_teacher:
        _expected_teacher_identity()
    branches: dict[str, dict[str, Any]] = {}
    branch_refs = pair.get("branch_manifests")
    if set(branch_refs) != set(BRANCHES):
        raise P2PostBlocked("pair branch manifest set is not exactly B1/B2")
    for branch in BRANCHES:
        ref = branch_refs[branch]
        if not isinstance(ref, Mapping):
            raise TypeError(f"pair {branch} branch ref must be a mapping")
        path = _confined(ref.get("path"), pair_root, f"pair {branch} branch manifest")
        expected_path = pair_root / branch / BRANCH_MANIFEST_FILENAME
        if path != expected_path or ref.get("sha256") != BRANCH_MANIFEST_SHA256[branch] or ref.get("size") != path.stat().st_size:
            raise P2PostBlocked(f"pair {branch} branch manifest ref drifted")
        actual = sha256_file(path)
        if actual != BRANCH_MANIFEST_SHA256[branch]:
            raise P2PostBlocked(f"pair {branch} branch manifest bytes drifted")
        branch_payload = _load_json(path)
        branches[branch] = _validate_branch_manifest(branch, pair_root / branch, common_root, branch_payload, path, actual, pair)
    return {
        "schema": POST_SCHEMA,
        "pair_root": str(pair_root),
        "pair_manifest": {"path": str(pair_path), "sha256": actual_pair_sha, "size": pair_path.stat().st_size},
        "content_sha256": pair_content,
        "payload": pair,
        "common_root": str(common_root),
        "common_init": dict(pair["common_init"]),
        "b1_step0": dict(pair["b1_step0"]),
        "b2_step0": dict(pair["b2_step0"]),
        "branches": branches,
        "teacher": _expected_teacher_identity() if validate_external_teacher else dict(TEACHER_IDENTITY),
    }


@dataclass(frozen=True)
class FormalJob:
    branch: str
    replicate_id: str
    output_root: Path
    checkpoint: Path
    checkpoint_sha256: str
    config: Path
    config_sha256: str
    command: tuple[str, ...]

    @property
    def command_sha256(self) -> str:
        return sha256_bytes(canonical_json(list(self.command)).encode("utf-8"))

    @property
    def metrics_path(self) -> Path:
        return self.output_root / FORMAL_METRICS_FILENAME

    @property
    def selection_path(self) -> Path:
        return self.output_root / FORMAL_SELECTION_FILENAME

    def as_dict(self) -> dict[str, Any]:
        return {
            "branch": self.branch,
            "replicate_id": self.replicate_id,
            "output_root": str(self.output_root),
            "command": list(self.command),
            "command_sha256": self.command_sha256,
            "checkpoint": {"path": str(self.checkpoint), "sha256": self.checkpoint_sha256, "global_step": EXPECTED_GLOBAL_STEP},
            "config": {"path": str(self.config), "sha256": self.config_sha256},
            "artifacts": {
                "metrics_path": str(self.metrics_path),
                "selection_path": str(self.selection_path),
            },
        }


@dataclass(frozen=True)
class FormalPlan:
    pair: Mapping[str, Any]
    output_root: Path
    jobs: tuple[FormalJob, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": POST_SCHEMA,
            "pair_root": self.pair["pair_root"],
            "output_root": str(self.output_root),
            "job_count": len(self.jobs),
            "jobs": [job.as_dict() for job in self.jobs],
        }


def _validate_fresh_output_root(root: Path) -> Path:
    root = root.expanduser().resolve()
    if root.exists() or root.is_symlink():
        raise FileExistsError(f"P2 post output root must be fresh: {root}")
    staging = root.with_name(f".{root.name}.writing")
    if staging.exists() or staging.is_symlink():
        raise FileExistsError(f"P2 post staging root already exists: {staging}")
    return root


def _command_arg(command: Sequence[str], flag: str) -> str:
    matches = [i for i, value in enumerate(command) if value == flag]
    if len(matches) != 1 or matches[0] + 1 >= len(command):
        raise P2PostBlocked(f"formal command must contain exactly one {flag}")
    return command[matches[0] + 1]


def _validate_formal_command(job: FormalJob) -> None:
    command = job.command
    if len(command) < 2 or command[0] != EVAL_PYTHON or Path(command[1]).resolve() != EVAL_SCRIPT:
        raise P2PostBlocked("formal command is not pinned evaluator-v2")
    for flag, expected in (
        ("--mode", "formal"),
        ("--controller", "student"),
        ("--output-root", str(job.output_root)),
        ("--replicate-id", job.replicate_id),
        ("--case-seed", "0"),
        ("--student-d435i-forward-mode", "packed"),
        ("--checkpoint", str(job.checkpoint)),
        ("--checkpoint-sha256", job.checkpoint_sha256),
        ("--checkpoint-config", str(job.config)),
        ("--checkpoint-config-sha256", job.config_sha256),
        ("--expected-global-step", str(EXPECTED_GLOBAL_STEP)),
        ("--overlay-repository", str(REPO_ROOT)),
        ("--runtime-repository", str(EXPECTED_RUNTIME_REPOSITORY)),
    ):
        if _command_arg(command, flag) != expected:
            raise P2PostBlocked(f"formal command {flag} identity drifted")
    # The mode is a formal Student contract, not an evaluator default.  The
    # exact command must pin packed exactly once so a future evaluator default
    # change cannot silently switch the architecture back to sequential.
    forbidden = {"--render", "--selection-json", "--source-metrics", "--n3-control-controller"}
    if any(flag in command for flag in forbidden):
        raise P2PostBlocked("formal command contains a forbidden render/Teacher/N3 control flag")


def build_formal_plan(
    pair: Mapping[str, Any],
    *,
    output_root: Path,
) -> FormalPlan:
    """Build exactly six fresh formal jobs from a validated pair snapshot."""
    output_root = _validate_fresh_output_root(output_root)
    pair_root = Path(pair["pair_root"]).expanduser().resolve()
    if output_root.is_relative_to(pair_root):
        raise P2PostBlocked("post output root may not be inside the immutable pair root")
    jobs: list[FormalJob] = []
    for branch in BRANCHES:
        identity = pair["branches"][branch]
        checkpoint = Path(identity["final_checkpoint"]["path"]).resolve(strict=True)
        config = Path(identity["final_config"]["path"]).resolve(strict=True)
        for replicate_id in REPLICATE_IDS:
            root = output_root / branch / "formal" / replicate_id
            command = (
                EVAL_PYTHON,
                str(EVAL_SCRIPT),
                "--mode", "formal",
                "--controller", "student",
                "--output-root", str(root),
                "--replicate-id", replicate_id,
                "--case-seed", "0",
                "--student-d435i-forward-mode", "packed",
                "--checkpoint", str(checkpoint),
                "--checkpoint-sha256", str(identity["final_checkpoint"]["sha256"]),
                "--checkpoint-config", str(config),
                "--checkpoint-config-sha256", str(identity["final_config"]["sha256"]),
                "--expected-global-step", str(EXPECTED_GLOBAL_STEP),
                "--overlay-repository", str(REPO_ROOT),
                "--runtime-repository", str(EXPECTED_RUNTIME_REPOSITORY),
            )
            job = FormalJob(
                branch=branch,
                replicate_id=replicate_id,
                output_root=root,
                checkpoint=checkpoint,
                checkpoint_sha256=str(identity["final_checkpoint"]["sha256"]),
                config=config,
                config_sha256=str(identity["final_config"]["sha256"]),
                command=command,
            )
            _validate_formal_command(job)
            jobs.append(job)
    if len(jobs) != 6 or [(job.branch, job.replicate_id) for job in jobs] != [
        (branch, replicate_id) for branch in BRANCHES for replicate_id in REPLICATE_IDS
    ]:
        raise AssertionError("P2 formal plan cardinality/order drifted")
    return FormalPlan(pair=pair, output_root=output_root, jobs=tuple(jobs))


def build_plan(
    pair_root: Path = PAIR_ROOT,
    *,
    output_root: Path,
    pair_manifest_sha256: str = PAIR_MANIFEST_SHA256,
    validate_external_teacher: bool = True,
) -> FormalPlan:
    pair = validate_pair_manifest(
        pair_root,
        pair_manifest_sha256=pair_manifest_sha256,
        validate_external_teacher=validate_external_teacher,
    )
    return build_formal_plan(pair, output_root=output_root)


# Keep the P1-post naming available to callers while retaining the explicit
# P2 formal-plan name above.
build_post_plan = build_plan


def _gpu_identity() -> dict[str, Any]:
    return {
        "physical_gpu_index": EXPECTED_GPU_INDEX,
        "logical_gpu_index": EXPECTED_LOGICAL_GPU_INDEX,
        "logical_device": EXPECTED_LOGICAL_DEVICE,
        "uuid": EXPECTED_GPU_UUID,
        "cuda_visible_devices": EXPECTED_GPU_INDEX,
        "cuda_device_order": EXPECTED_CUDA_DEVICE_ORDER,
        "binding_mode": EXPECTED_GPU_BINDING_MODE,
        "world_size": 1,
    }


def _validate_post_telemetry(payload: Mapping[str, Any]) -> dict[str, Any]:
    try:
        # This is intentionally the P2 validator itself.  It owns the exact
        # top-level/record fields, identity, finite physical ranges, cadence,
        # process bracketing, n-1 count formula, and declared-peak equality.
        return p2.validate_gpu_telemetry(payload)
    except (TypeError, ValueError, RuntimeError) as exc:
        raise P2PostBlocked(
            f"post telemetry failed the exact P2 telemetry contract: {exc}"
        ) from exc


def _seal_json(path: Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    path = path.expanduser().resolve()
    if path.exists() or path.is_symlink():
        raise FileExistsError(f"post seal refuses overwrite: {path}")
    unsigned = dict(payload)
    if "content_sha256" in unsigned:
        raise ValueError("post seal payload must not pre-populate content_sha256")
    unsigned["content_sha256"] = sha256_bytes(canonical_json(unsigned).encode("utf-8"))
    staging = path.with_name(f".{path.name}.writing")
    if staging.exists() or staging.is_symlink():
        raise FileExistsError(f"post seal staging path already exists: {staging}")
    staging.write_text(canonical_json(unsigned), encoding="utf-8")
    os.replace(staging, path)
    return {"path": str(path), "sha256": sha256_file(path), "size": path.stat().st_size, **unsigned}


def _write_failure(path: Path, payload: Mapping[str, Any]) -> None:
    if path.exists() or path.is_symlink():
        return
    try:
        _seal_json(path, payload)
    except BaseException:
        # A failure artifact is best effort; the original exception remains the
        # terminal result and no final decision can be sealed.
        pass


def _failure_json_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _failure_json_value(child) for key, child in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_failure_json_value(child) for child in value]
    return repr(value)


GpuTelemetrySampler = p2.GpuTelemetrySampler
build_child_environment = p2.build_child_environment


def _seal_child_telemetry(job: FormalJob, sampler: Any, started_ns: int, ended_ns: int) -> dict[str, Any]:
    if job.output_root.is_symlink() or not job.output_root.is_dir():
        raise P2PostBlocked("child telemetry root is not a real directory")
    path = job.output_root / TELEMETRY_FILENAME
    if path.exists() or path.is_symlink():
        raise FileExistsError(f"child telemetry path already exists: {path}")
    try:
        payload = sampler.stop(process_started_ns=started_ns, process_ended_ns=ended_ns)
    except BaseException as exc:
        fallback = {
            "schema": TELEMETRY_SCHEMA,
            "record_count": len(getattr(sampler, "records", [])) if isinstance(getattr(sampler, "records", []), list) else 0,
            "records": getattr(sampler, "records", []),
            "peak_vram_mib": None,
            "process_started_ns": started_ns,
            "process_ended_ns": ended_ns,
            "sample_interval_s": 5.0,
            "max_adjacent_gap_s": 15.0,
            "gpu_identity": _gpu_identity(),
            "telemetry_error": f"{type(exc).__name__}: {exc}",
        }
        path.write_text(json.dumps(_failure_json_value(fallback), sort_keys=True, allow_nan=True), encoding="utf-8")
        raise P2PostBlocked("child GPU telemetry sampler failed") from exc
    if not isinstance(payload, Mapping):
        raise TypeError("child telemetry sampler returned a non-mapping")
    # Do not wrap or augment this payload: P2 telemetry has an exact field set,
    # and adding post-only content_sha256 metadata would violate it.  The
    # manifest stores the file hash separately.
    validated = _validate_post_telemetry(payload)
    staging = path.with_name(f".{path.name}.writing")
    if staging.exists() or staging.is_symlink():
        raise FileExistsError(f"post seal staging path already exists: {staging}")
    staging.write_text(canonical_json(validated), encoding="utf-8")
    os.replace(staging, path)
    return {
        "path": str(path),
        "sha256": sha256_file(path),
        "size": path.stat().st_size,
        "schema": p2.P2_TELEMETRY_SCHEMA,
        "record_count": validated["record_count"],
        "peak_vram_mib": validated["peak_vram_mib"],
        "gpu_identity": validated["gpu_identity"],
    }


def _process_log_ref(path: Path, root: Path, name: str) -> dict[str, Any]:
    path = _confined(str(path), root, name)
    if not path.is_file():
        raise FileNotFoundError(f"sealed child process log is unavailable: {path}")
    return {"path": str(path), "sha256": sha256_file(path), "size": path.stat().st_size}


def _run_one(job: FormalJob, environment: Mapping[str, str]) -> dict[str, Any]:
    if job.output_root.exists() or job.output_root.is_symlink():
        raise FileExistsError(f"child output root must be absent before spawn: {job.output_root}")
    environment = dict(environment)
    expected_environment = {
        "CUDA_VISIBLE_DEVICES": EXPECTED_GPU_INDEX,
        "CUDA_DEVICE_ORDER": EXPECTED_CUDA_DEVICE_ORDER,
        "A2_GPU_BINDING_MODE": EXPECTED_GPU_BINDING_MODE,
        "A2_EXPECTED_WORLD_SIZE": "1",
        "A2_EXPECTED_HOST_GPU_INDEX": EXPECTED_GPU_INDEX,
        "A2_EXPECTED_LOGICAL_GPU_INDEX": str(EXPECTED_LOGICAL_GPU_INDEX),
        "A2_EXPECTED_GPU_UUID": EXPECTED_GPU_UUID,
    }
    for key, expected in expected_environment.items():
        if environment.get(key) != expected:
            raise P2PostBlocked(f"formal child GPU environment drifted for {key}")
    sampler = GpuTelemetrySampler(environment)
    try:
        # Prime the sampler synchronously before taking the process-start
        # timestamp.  The first record must be able to precede the child
        # interval even when the background thread is delayed at startup.
        sampler.sample_once()
    except BaseException as exc:
        # This failure occurs before a child is launched, so retain the same
        # bounded per-child evidence as the normal child/telemetry failure
        # path while preserving the original sampler diagnostic.
        job.output_root.mkdir(parents=True, exist_ok=False)
        (job.output_root / PROCESS_STDERR_FILENAME).write_text(
            f"{type(exc).__name__}: {exc}\n", encoding="utf-8"
        )
        _write_failure(
            job.output_root / FAILURE_FILENAME,
            {
                "schema": CHILD_FAILURE_SCHEMA,
                "branch": job.branch,
                "replicate_id": job.replicate_id,
                "command_sha256": job.command_sha256,
                "returncode": None,
                "child_error": None,
                "telemetry_error": f"{type(exc).__name__}: {exc}",
                "telemetry": None,
                "phase": "initial_gpu_sample",
            },
        )
        raise P2PostBlocked(f"initial GPU telemetry sample failed: {exc}") from exc
    started_ns = time.time_ns()
    sampler.start()
    result: subprocess.CompletedProcess[str] | None = None
    child_error: BaseException | None = None
    telemetry_ref: dict[str, Any] | None = None
    telemetry_error: BaseException | None = None
    try:
        try:
            result = subprocess.run(
                list(job.command),
                cwd=str(REPO_ROOT),
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                child_error = RuntimeError(
                    f"P2 formal child failed for {job.branch}/{job.replicate_id}: returncode={result.returncode}"
                )
        except BaseException as exc:
            child_error = exc
        if not job.output_root.exists():
            job.output_root.mkdir(parents=True, exist_ok=False)
        if job.output_root.is_symlink() or not job.output_root.is_dir():
            raise P2PostBlocked("child output root is not a real directory")
        if result is not None:
            (job.output_root / PROCESS_STDOUT_FILENAME).write_text(result.stdout or "", encoding="utf-8")
            (job.output_root / PROCESS_STDERR_FILENAME).write_text(result.stderr or "", encoding="utf-8")
        elif child_error is not None:
            (job.output_root / PROCESS_STDERR_FILENAME).write_text(
                f"{type(child_error).__name__}: {child_error}\n", encoding="utf-8"
            )
    finally:
        ended_ns = time.time_ns()
        try:
            telemetry_ref = _seal_child_telemetry(job, sampler, started_ns, ended_ns)
        except BaseException as exc:
            telemetry_error = exc
    if child_error is not None or telemetry_error is not None:
        _write_failure(
            job.output_root / FAILURE_FILENAME,
            {
                "schema": CHILD_FAILURE_SCHEMA,
                "branch": job.branch,
                "replicate_id": job.replicate_id,
                "command_sha256": job.command_sha256,
                "returncode": None if result is None else result.returncode,
                "child_error": None if child_error is None else f"{type(child_error).__name__}: {child_error}",
                "telemetry_error": None if telemetry_error is None else f"{type(telemetry_error).__name__}: {telemetry_error}",
                "telemetry": telemetry_ref,
            },
        )
        if telemetry_error is not None:
            raise telemetry_error from child_error
        assert child_error is not None
        raise child_error
    if not job.metrics_path.is_file() or not job.selection_path.is_file():
        error = FileNotFoundError(f"formal child did not seal both evaluator artifacts: {job.output_root}")
        _write_failure(job.output_root / FAILURE_FILENAME, {"schema": CHILD_FAILURE_SCHEMA, "branch": job.branch, "replicate_id": job.replicate_id, "command_sha256": job.command_sha256, "child_error": str(error), "telemetry": telemetry_ref})
        raise error
    assert telemetry_ref is not None
    telemetry_ref["stdout_log"] = _process_log_ref(job.output_root / PROCESS_STDOUT_FILENAME, job.output_root, "child stdout log")
    telemetry_ref["stderr_log"] = _process_log_ref(job.output_root / PROCESS_STDERR_FILENAME, job.output_root, "child stderr log")
    return telemetry_ref


def _require_exact_identity(actual: Any, expected: Any, name: str) -> None:
    if actual != expected:
        raise P2PostBlocked(f"{name} provenance drifted")


def _validate_case(value: Any, name: str) -> dict[str, float]:
    if not isinstance(value, Mapping) or set(value) != set(student_eval.RANDOMIZED_CASE_KEYS):
        raise P2PostBlocked(f"{name} randomized_case schema drifted")
    return {key: _strict_number(value[key], f"{name}.{key}") for key in student_eval.RANDOMIZED_CASE_KEYS}


def _record_event_metrics(record: Mapping[str, Any], name: str) -> dict[str, float | bool]:
    diagnostic = record.get("terminal_diagnostic")
    if not isinstance(diagnostic, Mapping):
        raise TypeError(f"{name} terminal_diagnostic must be a mapping")
    if diagnostic.get("reward_episode_sums_unit") != "episode-sum":
        raise P2PostBlocked(f"{name} reward_episode_sums_unit must be exactly 'episode-sum'")
    sums = diagnostic.get("reward_episode_sums")
    if not isinstance(sums, Mapping):
        raise P2PostBlocked(f"{name} lacks episode reward sums required for safety evidence")
    required_sums = (
        "penalty_door_frame_contact",
        "penalty_dof_overspeed",
        "penalty_a2_stage2_over_force",
        "penalty_a2_stage3_stage4_over_force",
    )
    if any(key not in sums for key in required_sums):
        raise P2PostBlocked(f"{name}.reward_episode_sums is missing a required c18 safety term")
    values = {key: _strict_number(sums[key], f"{name}.reward_episode_sums.{key}") for key in required_sums}
    root_yaw = abs(_strict_number(diagnostic.get("root_yaw"), f"{name}.root_yaw"))
    root_pos_rel = diagnostic.get("root_pos_rel")
    if not isinstance(root_pos_rel, Sequence) or isinstance(root_pos_rel, (str, bytes, bytearray)) or len(root_pos_rel) != 3:
        raise P2PostBlocked(f"{name}.root_pos_rel must be the exact c18 three-vector")
    _strict_number(root_pos_rel[0], f"{name}.root_pos_rel[0]")
    root_y = abs(_strict_number(root_pos_rel[1], f"{name}.root_pos_rel[1]"))
    _strict_number(root_pos_rel[2], f"{name}.root_pos_rel[2]")
    over_force = diagnostic.get("over_force")
    if type(over_force) is not bool:
        raise TypeError(f"{name}.over_force must be a required bool")
    return {
        "doorframe_contact": values["penalty_door_frame_contact"] < 0.0,
        "doorframe_penalty": values["penalty_door_frame_contact"],
        "overspeed": values["penalty_dof_overspeed"] < 0.0 or record.get("terminal_reason") == "upper_dof_overspeed",
        "overspeed_penalty": values["penalty_dof_overspeed"],
        "over_force": bool(over_force) or values["penalty_a2_stage2_over_force"] < 0.0 or values["penalty_a2_stage3_stage4_over_force"] < 0.0,
        "over_force_penalty": values["penalty_a2_stage2_over_force"] + values["penalty_a2_stage3_stage4_over_force"],
        "root_yaw_abs": root_yaw,
        "root_y_abs": root_y,
    }


def _load_formal_artifacts(job: FormalJob, branch_identity: Mapping[str, Any]) -> dict[str, Any]:
    metrics_ref = _artifact_ref(job.metrics_path, sha256_file(job.metrics_path), "formal metrics", root=job.output_root)
    selection_ref = _artifact_ref(job.selection_path, sha256_file(job.selection_path), "formal selection", root=job.output_root)
    try:
        selection, metrics = student_eval.load_sealed_selection(job.selection_path, job.metrics_path)
    except BaseException as exc:
        raise P2PostBlocked(f"{job.branch}/{job.replicate_id} sealed formal artifacts failed evaluator-v2 validation") from exc
    formal_teacher: Mapping[str, Any] | None = None
    for label, payload, schema in (("metrics", metrics, student_eval.STUDENT_METRICS_SCHEMA), ("selection", selection, student_eval.STUDENT_SELECTION_SCHEMA)):
        if payload.get("schema") != schema or payload.get("controller") != "student" or payload.get("case_seed") != 0 or payload.get("replicate_id") != job.replicate_id:
            raise P2PostBlocked(f"{job.branch}/{job.replicate_id} formal {label} controller/seed/replicate drifted")
        checkpoint = payload.get("checkpoint")
        if not isinstance(checkpoint, Mapping):
            raise TypeError(f"{job.branch}/{job.replicate_id} {label} checkpoint identity is missing")
        for key, expected in (
            ("path", str(job.checkpoint)),
            ("sha256", job.checkpoint_sha256),
            ("config_path", str(job.config)),
            ("config_sha256", job.config_sha256),
            ("global_step", EXPECTED_GLOBAL_STEP),
            ("controller", "student"),
        ):
            if checkpoint.get(key) != expected:
                raise P2PostBlocked(f"{job.branch}/{job.replicate_id} {label} checkpoint {key} drifted")
        teacher = payload.get("teacher")
        if not isinstance(teacher, Mapping):
            raise TypeError(f"{job.branch}/{job.replicate_id} {label} Teacher identity is missing")
        teacher_checkpoint = teacher.get("checkpoint")
        teacher_manifest = teacher.get("manifest")
        if not isinstance(teacher_checkpoint, Mapping) or not isinstance(teacher_manifest, Mapping):
            raise TypeError(f"{job.branch}/{job.replicate_id} {label} Teacher triplet is incomplete")
        if (
            teacher_checkpoint.get("path") != TEACHER_IDENTITY["checkpoint"]["path"]
            or teacher_checkpoint.get("sha256") != TEACHER_IDENTITY["checkpoint"]["sha256"]
            or teacher_checkpoint.get("config_path") != TEACHER_IDENTITY["config"]["path"]
            or teacher_checkpoint.get("config_sha256") != TEACHER_IDENTITY["config"]["sha256"]
            or teacher_manifest.get("path") != TEACHER_IDENTITY["manifest"]["path"]
            or teacher_manifest.get("sha256") != TEACHER_IDENTITY["manifest"]["sha256"]
            or teacher.get("runtime_commit") != EXPECTED_RUNTIME_COMMIT
        ):
            raise P2PostBlocked(f"{job.branch}/{job.replicate_id} {label} Teacher identity drifted")
        if formal_teacher is None:
            formal_teacher = teacher
        elif canonical_json(formal_teacher) != canonical_json(teacher):
            raise P2PostBlocked(f"{job.branch}/{job.replicate_id} metrics/selection Teacher identity differs")
        contract = payload.get("contract")
        if not isinstance(contract, Mapping):
            raise TypeError(f"{job.branch}/{job.replicate_id} {label} formal contract missing")
        for key, expected in {
            "case_seed": 0,
            "replicate_id": job.replicate_id,
            "num_envs": EXPECTED_NUM_ENVS,
            "one_episode_per_env": True,
            "pure_student": True,
            "enforce_teacher_rollout": False,
            "ratio_teacher_rollout": 0.0,
            "use_a2_base": True,
            "student_d435i_forward_mode": "packed",
        }.items():
            if contract.get(key) != expected:
                raise P2PostBlocked(f"{job.branch}/{job.replicate_id} {label} contract {key} drifted")
        experience = payload.get("experience")
        if not isinstance(experience, Mapping) or experience.get("controller") != "student" or experience.get("camera_mode") != "cameras" or experience.get("relative_path") != "gr00t/rl/apps/phc.isaaclab.python.headless.rendering.kit":
            raise P2PostBlocked(f"{job.branch}/{job.replicate_id} {label} experience is not pure Student cameras")
    episodes = metrics.get("episodes")
    if not isinstance(episodes, list) or len(episodes) != EXPECTED_EPISODES_PER_REPLICATE:
        raise P2PostBlocked(f"{job.branch}/{job.replicate_id} formal metrics must contain exactly 16 episodes")
    seen: set[int] = set()
    normalized: list[dict[str, Any]] = []
    for index, record in enumerate(episodes):
        if not isinstance(record, Mapping):
            raise TypeError(f"{job.branch}/{job.replicate_id} episode {index} must be a mapping")
        env_id = _strict_int(record.get("env_id"), f"{job.branch}/{job.replicate_id} episode env_id")
        if env_id in seen or not 0 <= env_id < EXPECTED_NUM_ENVS:
            raise P2PostBlocked(f"{job.branch}/{job.replicate_id} episode env IDs are not unique 0..15")
        seen.add(env_id)
        if record.get("episode_index") != 0 or type(record.get("goal_reached")) is not bool:
            raise P2PostBlocked(f"{job.branch}/{job.replicate_id} episode index/goal type drifted")
        stage = _strict_int(record.get("max_stage"), f"{job.branch}/{job.replicate_id} max_stage")
        if stage < 0:
            raise ValueError("max_stage cannot be negative")
        _strict_number(record.get("reward"), f"{job.branch}/{job.replicate_id} reward")
        if not isinstance(record.get("terminal_reason"), str) or not record["terminal_reason"]:
            raise TypeError(f"{job.branch}/{job.replicate_id} terminal_reason must be non-empty")
        _validate_case(record.get("randomized_case"), f"{job.branch}/{job.replicate_id} env{env_id}")
        metrics_for_record = _record_event_metrics(record, f"{job.branch}/{job.replicate_id} env{env_id}")
        normalized.append({**dict(record), "event_metrics": metrics_for_record})
    if seen != set(range(EXPECTED_NUM_ENVS)):
        raise P2PostBlocked(f"{job.branch}/{job.replicate_id} formal env set is not exactly 0..15")
    return {
        "branch": job.branch,
        "replicate_id": job.replicate_id,
        "metrics": metrics_ref,
        "selection": selection_ref,
        "metrics_payload": metrics,
        "selection_payload": selection,
        "episodes": sorted(normalized, key=lambda item: item["env_id"]),
    }


def _mean(values: Sequence[float], name: str) -> float:
    if not values:
        raise ValueError(f"{name} cannot be empty")
    result = sum(values) / len(values)
    if not math.isfinite(result):
        raise ValueError(f"{name} mean is not finite")
    return result


def _branch_summary(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if len(records) != EXPECTED_TOTAL_EPISODES:
        raise P2PostBlocked(f"branch pooled formal record count must be 48, got {len(records)}")
    stages = [int(record["max_stage"]) for record in records]
    events = [record["event_metrics"] for record in records]
    return {
        "episode_count": len(records),
        "goal_count": sum(bool(record["goal_reached"]) for record in records),
        "stage0_count": sum(stage == 0 for stage in stages),
        "stage2_plus_count": sum(stage >= 2 for stage in stages),
        "doorframe_contact_count": sum(bool(event["doorframe_contact"]) for event in events),
        "overspeed_count": sum(bool(event["overspeed"]) for event in events),
        "over_force_count": sum(bool(event["over_force"]) for event in events),
        "mean_doorframe_penalty": _mean([float(event["doorframe_penalty"]) for event in events], "mean_doorframe_penalty"),
        "mean_overspeed_penalty": _mean([float(event["overspeed_penalty"]) for event in events], "mean_overspeed_penalty"),
        "mean_over_force_penalty": _mean([float(event["over_force_penalty"]) for event in events], "mean_over_force_penalty"),
        "mean_max_stage": _mean([float(stage) for stage in stages], "mean_max_stage"),
        "mean_reward": _mean([_strict_number(record["reward"], "episode reward") for record in records], "mean_reward"),
        "mean_abs_root_yaw": _mean([float(event["root_yaw_abs"]) for event in events], "mean_abs_root_yaw"),
        "mean_abs_root_y": _mean([float(event["root_y_abs"]) for event in events], "mean_abs_root_y"),
    }


def _relative_mean_gate(baseline: float, candidate: float, name: str) -> dict[str, Any]:
    if baseline < 0.0 or candidate < 0.0:
        raise ValueError(f"{name} means must be non-negative")
    if baseline == 0.0:
        passed = candidate == 0.0
        ratio = None
        reason = "baseline_zero_candidate_zero" if passed else "baseline_zero_positive_worsening"
    else:
        ratio = candidate / baseline
        allowed = baseline * (1.0 + EXPECTED_SAFETY_MEAN_WORSENING_RATIO)
        passed = candidate <= allowed or math.isclose(candidate, allowed, rel_tol=0.0, abs_tol=1e-12)
        reason = "candidate_within_10_percent" if passed else "candidate_worsened_over_10_percent"
    return {
        "baseline_mean": baseline,
        "candidate_mean": candidate,
        "delta": candidate - baseline,
        "ratio": ratio,
        "max_allowed_mean": baseline * (1.0 + EXPECTED_SAFETY_MEAN_WORSENING_RATIO),
        "pass": passed,
        "reason": reason,
    }


def _gate(name: str, passed: bool, reason: str, **values: Any) -> dict[str, Any]:
    return {"name": name, "pass": bool(passed), "reason": reason, **values}


def adjudicate_formal_records(
    pair: Mapping[str, Any],
    artifacts: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    """Pool 48 episodes per branch and apply P2 effectiveness/safety gates."""
    if set(artifacts) != set(BRANCHES):
        raise ValueError("formal artifacts must contain exactly b1 and b2")
    pooled: dict[str, list[dict[str, Any]]] = {branch: [] for branch in BRANCHES}
    for branch in BRANCHES:
        runs = artifacts[branch]
        if len(runs) != len(REPLICATE_IDS):
            raise P2PostBlocked(f"{branch} formal artifact set must contain exactly three replicates")
        ids = [run.get("replicate_id") for run in runs]
        if ids != list(REPLICATE_IDS) and set(ids) != set(REPLICATE_IDS):
            raise P2PostBlocked(f"{branch} formal replicate IDs are incomplete/duplicated")
        for run in runs:
            pooled[branch].extend(dict(record, branch=branch, replicate_id=run["replicate_id"]) for record in run["episodes"])
    by_key: dict[tuple[str, str, int], dict[str, Any]] = {}
    for branch in BRANCHES:
        for record in pooled[branch]:
            key = (str(record["replicate_id"]), int(record["env_id"]))
            full_key = (branch, *key)
            if full_key in by_key:
                raise P2PostBlocked(f"{branch} duplicate formal replicate/env record")
            by_key[full_key] = record
    for env_id in range(EXPECTED_NUM_ENVS):
        reference_case: str | None = None
        for branch in BRANCHES:
            for replicate_id in REPLICATE_IDS:
                record = by_key[(branch, replicate_id, env_id)]
                case = canonical_json(record["randomized_case"])
                if reference_case is None:
                    reference_case = case
                elif case != reference_case:
                    raise P2PostBlocked(f"randomized-case identity mismatch at env{env_id}")
    summary = {branch: _branch_summary(pooled[branch]) for branch in BRANCHES}
    b1 = summary["b1"]
    b2 = summary["b2"]
    stage0_reduction = b1["stage0_count"] - b2["stage0_count"]
    mean_stage_delta = b2["mean_max_stage"] - b1["mean_max_stage"]
    doorframe_reduction = b1["doorframe_contact_count"] - b2["doorframe_contact_count"]
    doorframe_baseline = b1["doorframe_contact_count"]
    if doorframe_baseline == 0:
        doorframe_ratio = None
        doorframe_pass = False
        doorframe_reason = "baseline_zero_no_relative_reduction"
    else:
        doorframe_ratio = doorframe_reduction / doorframe_baseline
        doorframe_pass = doorframe_ratio >= EXPECTED_DOORFRAME_REDUCTION_RATIO
        doorframe_reason = "reduction_at_least_20_percent" if doorframe_pass else "reduction_below_20_percent"
    mean_stage_pass = mean_stage_delta >= EXPECTED_EFFECTIVENESS_STAGE_MEAN_DELTA or math.isclose(
        mean_stage_delta,
        EXPECTED_EFFECTIVENESS_STAGE_MEAN_DELTA,
        rel_tol=0.0,
        abs_tol=1.0e-12,
    )
    effectiveness = {
        "stage0_failures_reduction": _gate(
            "stage0_failures_reduction",
            stage0_reduction >= EXPECTED_EFFECTIVENESS_STAGE0_REDUCTION,
            "reduction_at_least_4_of_48" if stage0_reduction >= EXPECTED_EFFECTIVENESS_STAGE0_REDUCTION else "reduction_below_4_of_48",
            baseline_count=b1["stage0_count"], candidate_count=b2["stage0_count"], reduction=stage0_reduction, threshold=EXPECTED_EFFECTIVENESS_STAGE0_REDUCTION,
        ),
        "paired_mean_max_stage": _gate(
            "paired_mean_max_stage",
            mean_stage_pass,
            "mean_delta_at_least_0.20" if mean_stage_pass else "mean_delta_below_0.20",
            baseline_mean=b1["mean_max_stage"], candidate_mean=b2["mean_max_stage"], delta=mean_stage_delta, threshold=EXPECTED_EFFECTIVENESS_STAGE_MEAN_DELTA,
        ),
        "doorframe_contact_reduction": _gate(
            "doorframe_contact_reduction", doorframe_pass, doorframe_reason,
            baseline_count=doorframe_baseline, candidate_count=b2["doorframe_contact_count"], reduction=doorframe_reduction, ratio=doorframe_ratio, threshold=EXPECTED_DOORFRAME_REDUCTION_RATIO,
        ),
    }
    effectiveness_pass = any(item["pass"] for item in effectiveness.values())
    stage2_decrease = b1["stage2_plus_count"] - b2["stage2_plus_count"]
    safety = {
        "stage2_plus_count": _gate(
            "stage2_plus_count",
            stage2_decrease <= EXPECTED_STAGE2_DECREASE_MAX,
            "decrease_within_2_of_48" if stage2_decrease <= EXPECTED_STAGE2_DECREASE_MAX else "decrease_exceeds_2_of_48",
            baseline_count=b1["stage2_plus_count"], candidate_count=b2["stage2_plus_count"], decrease=stage2_decrease, threshold=EXPECTED_STAGE2_DECREASE_MAX,
        ),
        "overspeed_count": _gate(
            "overspeed_count",
            b2["overspeed_count"] <= b1["overspeed_count"],
            "candidate_not_increased" if b2["overspeed_count"] <= b1["overspeed_count"] else "candidate_increased",
            baseline_count=b1["overspeed_count"], candidate_count=b2["overspeed_count"], delta=b2["overspeed_count"] - b1["overspeed_count"],
        ),
        "over_force_count": _gate(
            "over_force_count",
            b2["over_force_count"] <= b1["over_force_count"],
            "candidate_not_increased" if b2["over_force_count"] <= b1["over_force_count"] else "candidate_increased",
            baseline_count=b1["over_force_count"], candidate_count=b2["over_force_count"], delta=b2["over_force_count"] - b1["over_force_count"],
        ),
        "mean_abs_root_yaw": _relative_mean_gate(b1["mean_abs_root_yaw"], b2["mean_abs_root_yaw"], "mean_abs_root_yaw"),
        "mean_abs_root_y": _relative_mean_gate(b1["mean_abs_root_y"], b2["mean_abs_root_y"], "mean_abs_root_y"),
    }
    safety_pass = all(item["pass"] for item in safety.values())
    selected_branch = "b2" if effectiveness_pass and safety_pass else "b1"
    selected_identity = pair["branches"][selected_branch]
    paired_deltas = []
    for replicate_id in REPLICATE_IDS:
        for env_id in range(EXPECTED_NUM_ENVS):
            left = by_key[("b1", replicate_id, env_id)]
            right = by_key[("b2", replicate_id, env_id)]
            paired_deltas.append({
                "replicate_id": replicate_id,
                "env_id": env_id,
                "max_stage_delta": int(right["max_stage"]) - int(left["max_stage"]),
                "stage0_delta": int(int(right["max_stage"] == 0) - int(left["max_stage"] == 0)),
                "doorframe_contact_delta": int(right["event_metrics"]["doorframe_contact"]) - int(left["event_metrics"]["doorframe_contact"]),
                "overspeed_delta": int(right["event_metrics"]["overspeed"]) - int(left["event_metrics"]["overspeed"]),
                "over_force_delta": int(right["event_metrics"]["over_force"]) - int(left["event_metrics"]["over_force"]),
            })
    return {
        "schema": "a2_cb2h_pro_p2_post_adjudication_v1",
        "pooled": summary,
        "paired_deltas": paired_deltas,
        "effectiveness": effectiveness,
        "effectiveness_pass": effectiveness_pass,
        "safety": safety,
        "safety_pass": safety_pass,
        "decision": DECISION_SELECT_B2 if selected_branch == "b2" else DECISION_SELECT_B1,
        "winner": selected_branch,
        "selected_branch": selected_branch,
        "selected_provenance": {
            "branch": selected_branch,
            "architecture": selected_identity["architecture"],
            "manifest": selected_identity["manifest_ref"],
            "checkpoint": selected_identity["final_checkpoint"],
            "config": selected_identity["final_config"],
            "common_init": selected_identity["common_init"],
            "teacher": selected_identity["teacher"],
        },
        "zero_goals_or_poor_quality_visible": True,
        "relative_architecture_gate_only": True,
    }


def _assert_pair_snapshot(pair: Mapping[str, Any]) -> None:
    root = Path(pair["pair_root"]).resolve(strict=True)
    pair_ref = pair["pair_manifest"]
    path = Path(pair_ref["path"]).resolve(strict=True)
    if sha256_file(path) != pair_ref["sha256"]:
        raise P2PostBlocked("pair manifest changed before final adjudication")
    payload = _load_json(path)
    if _content_hash(payload) != pair["content_sha256"]:
        raise P2PostBlocked("pair content changed before final adjudication")
    common_artifact = pair["common_init"]["artifact"]
    if sha256_file(Path(common_artifact["path"]).resolve(strict=True)) != common_artifact["sha256"]:
        raise P2PostBlocked("common-init artifact changed before final adjudication")
    for branch in BRANCHES:
        step0 = pair[f"{branch}_step0"]
        if sha256_file(Path(step0["path"]).resolve(strict=True)) != step0["sha256"]:
            raise P2PostBlocked(f"{branch} step0 manifest changed before final adjudication")
    for branch in BRANCHES:
        identity = pair["branches"][branch]
        manifest_path = Path(identity["manifest_ref"]["path"]).resolve(strict=True)
        if sha256_file(manifest_path) != identity["manifest_ref"]["sha256"]:
            raise P2PostBlocked(f"{branch} branch manifest changed before final adjudication")
        checkpoint = Path(identity["final_checkpoint"]["path"]).resolve(strict=True)
        config = Path(identity["final_config"]["path"]).resolve(strict=True)
        if sha256_file(checkpoint) != BRANCH_CHECKPOINT_SHA256[branch] or sha256_file(config) != BRANCH_CONFIG_SHA256[branch]:
            raise P2PostBlocked(f"{branch} final artifact changed before final adjudication")
    if not root.is_relative_to(REPO_ROOT):
        raise P2PostBlocked("pair root unexpectedly escaped repository")


def _assert_same_artifact_ref(initial: Mapping[str, Any], current: Mapping[str, Any], name: str) -> None:
    for key in ("path", "sha256", "size"):
        if initial.get(key) != current.get(key):
            raise P2PostBlocked(f"{name} changed after initial load")


def _final_formal_snapshot_barrier(
    plan: FormalPlan,
    initial_artifacts: Mapping[str, Sequence[Mapping[str, Any]]],
    initial_telemetry_refs: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    """Revalidate all six formal outputs from final on-disk bytes exactly once."""
    _assert_pair_snapshot(plan.pair)
    final_artifacts: dict[str, list[dict[str, Any]]] = {branch: [] for branch in BRANCHES}
    final_telemetry_refs: list[dict[str, Any]] = []
    initial_by_job = {
        (str(item["branch"]), str(item["replicate_id"])): item for item in initial_telemetry_refs
    }
    for job in plan.jobs:
        if job.output_root.is_symlink() or not job.output_root.is_dir():
            raise P2PostBlocked(f"{job.branch}/{job.replicate_id} formal output root changed or disappeared")
        initial_loaded = next(
            item for item in initial_artifacts[job.branch] if item["replicate_id"] == job.replicate_id
        )
        initial_metrics = initial_loaded.get("metrics")
        initial_selection = initial_loaded.get("selection")
        if not isinstance(initial_metrics, Mapping) or not isinstance(initial_selection, Mapping):
            raise P2PostBlocked(f"{job.branch}/{job.replicate_id} initial formal artifact refs are incomplete")
        metrics_path = _confined(str(job.metrics_path), job.output_root, "final formal metrics")
        selection_path = _confined(str(job.selection_path), job.output_root, "final formal selection")
        _artifact_ref(metrics_path, _require_sha(initial_metrics.get("sha256"), "final formal metrics SHA"), "final formal metrics", root=job.output_root)
        _artifact_ref(selection_path, _require_sha(initial_selection.get("sha256"), "final formal selection SHA"), "final formal selection", root=job.output_root)
        loaded = _load_formal_artifacts(job, plan.pair["branches"][job.branch])
        _assert_same_artifact_ref(initial_metrics, loaded["metrics"], f"{job.branch}/{job.replicate_id} metrics")
        _assert_same_artifact_ref(initial_selection, loaded["selection"], f"{job.branch}/{job.replicate_id} selection")
        final_artifacts[job.branch].append(loaded)

        initial_telemetry = initial_by_job.get((job.branch, job.replicate_id))
        if initial_telemetry is None:
            raise P2PostBlocked(f"{job.branch}/{job.replicate_id} initial telemetry ref is missing")
        telemetry_path = _confined(
            str(initial_telemetry.get("path")), job.output_root, "final GPU telemetry"
        )
        if telemetry_path != job.output_root / TELEMETRY_FILENAME:
            raise P2PostBlocked(f"{job.branch}/{job.replicate_id} final GPU telemetry path drifted")
        telemetry_ref = _artifact_ref(
            telemetry_path,
            _require_sha(initial_telemetry.get("sha256"), "final GPU telemetry SHA"),
            "final GPU telemetry",
            root=job.output_root,
        )
        telemetry_payload = _load_json(telemetry_path)
        validated_telemetry = _validate_post_telemetry(telemetry_payload)
        if telemetry_ref["size"] != initial_telemetry.get("size"):
            raise P2PostBlocked(f"{job.branch}/{job.replicate_id} final GPU telemetry size drifted")
        stdout_initial = initial_telemetry.get("stdout_log")
        stderr_initial = initial_telemetry.get("stderr_log")
        if not isinstance(stdout_initial, Mapping) or not isinstance(stderr_initial, Mapping):
            raise P2PostBlocked(f"{job.branch}/{job.replicate_id} initial process log refs are incomplete")
        stdout_ref = _process_log_ref(job.output_root / PROCESS_STDOUT_FILENAME, job.output_root, "final child stdout log")
        stderr_ref = _process_log_ref(job.output_root / PROCESS_STDERR_FILENAME, job.output_root, "final child stderr log")
        _assert_same_artifact_ref(stdout_initial, stdout_ref, f"{job.branch}/{job.replicate_id} stdout log")
        _assert_same_artifact_ref(stderr_initial, stderr_ref, f"{job.branch}/{job.replicate_id} stderr log")
        final_telemetry_refs.append(
            {
                "branch": job.branch,
                "replicate_id": job.replicate_id,
                "command_sha256": job.command_sha256,
                **telemetry_ref,
                "schema": validated_telemetry["schema"],
                "record_count": validated_telemetry["record_count"],
                "peak_vram_mib": validated_telemetry["peak_vram_mib"],
                "gpu_identity": validated_telemetry["gpu_identity"],
                "stdout_log": stdout_ref,
                "stderr_log": stderr_ref,
            }
        )
    return final_artifacts, final_telemetry_refs


def execute_post_plan(
    plan: FormalPlan,
    *,
    environment_factory: Callable[[], Mapping[str, str]] | None = None,
) -> dict[str, Any]:
    """Execute six children serially, then atomically seal the final decision."""
    output_root = plan.output_root
    if output_root.exists() or output_root.is_symlink():
        raise FileExistsError(f"P2 post output root must remain fresh: {output_root}")
    output_root.parent.mkdir(parents=True, exist_ok=True)
    output_root.mkdir()
    environment_factory = build_child_environment if environment_factory is None else environment_factory
    telemetry_refs: list[dict[str, Any]] = []
    artifacts: dict[str, list[dict[str, Any]]] = {branch: [] for branch in BRANCHES}
    try:
        for job in plan.jobs:
            telemetry_ref = _run_one(job, environment_factory())
            telemetry_refs.append({"branch": job.branch, "replicate_id": job.replicate_id, "command_sha256": job.command_sha256, **telemetry_ref})
            artifacts[job.branch].append(_load_formal_artifacts(job, plan.pair["branches"][job.branch]))
        artifacts, telemetry_refs = _final_formal_snapshot_barrier(plan, artifacts, telemetry_refs)
        adjudication = adjudicate_formal_records(plan.pair, artifacts)
        runs = []
        for job in plan.jobs:
            telemetry = next(item for item in telemetry_refs if item["branch"] == job.branch and item["replicate_id"] == job.replicate_id)
            loaded = next(item for item in artifacts[job.branch] if item["replicate_id"] == job.replicate_id)
            runs.append({**job.as_dict(), "telemetry": telemetry, "metrics": loaded["metrics"], "selection": loaded["selection"]})
        sealed_formal_refs = {
            branch: [
                {
                    "replicate_id": item["replicate_id"],
                    "metrics": item["metrics"],
                    "selection": item["selection"],
                }
                for item in artifacts[branch]
            ]
            for branch in BRANCHES
        }
        manifest_payload = {
            "schema": POST_SCHEMA,
            "operation": "p2_formal_post_adjudication",
            "pair_input": {
                "root": plan.pair["pair_root"],
                "manifest": plan.pair["pair_manifest"],
                "content_sha256": plan.pair["content_sha256"],
                "branches": {branch: plan.pair["branches"][branch]["manifest_ref"] for branch in BRANCHES},
                "common_init": plan.pair["common_init"],
            },
            "output_root": str(output_root),
            "runtime": {"repository": str(EXPECTED_RUNTIME_REPOSITORY), "commit": EXPECTED_RUNTIME_COMMIT},
            "gpu_identity": _gpu_identity(),
            "runs": runs,
            "telemetry": {"schema": TELEMETRY_SCHEMA, "run_count": len(telemetry_refs), "artifacts": telemetry_refs, "overall_peak_vram_mib": max(item["peak_vram_mib"] for item in telemetry_refs)},
            "formal_artifacts": sealed_formal_refs,
            "adjudication": adjudication,
            "decision": adjudication["decision"],
        }
        return _seal_json(output_root / FINAL_MANIFEST_FILENAME, manifest_payload)
    except BaseException as exc:
        _write_failure(output_root / ROOT_FAILURE_FILENAME, {"schema": FAILURE_SCHEMA, "root": str(output_root), "error_type": type(exc).__name__, "error_message": str(exc)})
        raise


def print_plan(plan: FormalPlan) -> None:
    print(f"[A2_CB2H_PRO_P2_POST_DRY_RUN] formal_runs={len(plan.jobs)}", flush=True)
    for job in plan.jobs:
        print(f"[A2_CB2H_PRO_P2_POST_COMMAND] branch={job.branch} replicate={job.replicate_id} output={job.output_root} command_sha256={job.command_sha256}", flush=True)
        print(" ".join(job.command), flush=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pair-root", type=Path, default=PAIR_ROOT)
    parser.add_argument("--pair-manifest-sha256", default=PAIR_MANIFEST_SHA256)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute", action="store_true")
    return parser


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    args = _parser().parse_args(argv)
    if args.dry_run == args.execute:
        raise ValueError("select exactly one of --dry-run or --execute")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    plan = build_plan(
        args.pair_root,
        output_root=args.output_root,
        pair_manifest_sha256=args.pair_manifest_sha256,
    )
    if args.dry_run:
        print_plan(plan)
        return 0
    result = execute_post_plan(plan)
    print(f"[A2_CB2H_PRO_P2_POST_{result['decision']}] decision={result['decision']} manifest={args.output_root.expanduser().resolve() / FINAL_MANIFEST_FILENAME}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
