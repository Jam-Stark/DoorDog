#!/usr/bin/env python3
"""Execute and adjudicate sealed C-B2H P1 post-training checks.

The runner is deliberately separate from training.  It consumes two sealed
    step-10200 or step-10500 branch manifests, plans exactly three N3 open-loop
    runs and three formal Student runs per branch, executes them serially when
    explicitly asked, and seals one final stage decision.  Dry-run is CPU-only and non-mutating;
no checkpoint discovery, resume, GPU fallback, tmux management, or in-place
retry is permitted.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gr00t.rl.scripts import run_a2_cb2h_pro_p1 as p1


PAIR_ROOT = (REPO_ROOT / "logs_rl/cb2h_pro_p1_pair200_gpu7-retry3-20260803").resolve()
SEQUENTIAL_MANIFEST_SHA256 = "a05c8894c6731717c83c0e413ba1d17e9103c4c6008c210d5ae2444b37d8f8aa"
PACKED_MANIFEST_SHA256 = "aba487aa9a9294e28cc50840f798170a66a2733c9f7e2bd6019306631e050ab1"
POST_SCHEMA = "a2_cb2h_pro_p1_post_v1"
FINAL_MANIFEST_FILENAME = "p1_adjudication_manifest.json"
FAILURE_FILENAME = "p1_post_failure.json"
N3_ACTION_FILENAME = "p1_n3_actions.json"
N3_CHILD_ACTION_FILENAME = p1.P1_N3_ACTION_MANIFEST_FILENAME
FORMAL_METRICS_FILENAME = "formal_student_metrics.json"
FORMAL_SELECTION_FILENAME = "student_selection.json"
TELEMETRY_FILENAME = p1.P1_GPU_TELEMETRY_FILENAME
TELEMETRY_SCHEMA = p1.P1_GPU_TELEMETRY_SCHEMA
REPLICATE_IDS = ("replicate_01", "replicate_02", "replicate_03")
POST_BRANCHES = p1.P1_BRANCHES
EXPECTED_ACTIVE_FRAME_COUNT = p1.EXPECTED_ACTIVE_FRAME_COUNT
DECISION_PASS = "PASS"
DECISION_EXTEND = "EXTEND_BOTH_TO_500"
DECISION_DIRECTIONAL_SUPPORT = "PACKED_DIRECTIONAL_SUPPORT"
DECISION_STOP = "STOP_H5_SIGNIFICANTLY_WEAKENED"


class P1PostBlocked(RuntimeError):
    """A required resource or evidence gate blocks post-training adjudication."""


@dataclass(frozen=True)
class PostStage:
    stage_id: str
    requested_iterations: int
    additional_iterations: int
    source_global_step: int
    target_global_step: int
    operation: str


POST_STAGE_200 = PostStage(
    stage_id="p1_stage_200",
    requested_iterations=p1.INITIAL_ITERATIONS,
    additional_iterations=p1.INITIAL_ITERATIONS,
    source_global_step=p1.EXPECTED_INITIAL_GLOBAL_STEP,
    target_global_step=p1.INITIAL_TARGET_GLOBAL_STEP,
    operation="p1_post_training_200",
)
POST_STAGE_500 = PostStage(
    stage_id="p1_stage_500",
    requested_iterations=p1.EXTENDED_ITERATIONS,
    additional_iterations=p1.EXTENSION_ITERATIONS,
    source_global_step=p1.INITIAL_TARGET_GLOBAL_STEP,
    target_global_step=p1.EXTENDED_TARGET_GLOBAL_STEP,
    operation="p1_post_training_500",
)
POST_STAGES = (POST_STAGE_200, POST_STAGE_500)
POST_OPERATION = POST_STAGE_200.operation
EXPECTED_ITERATIONS = POST_STAGE_200.requested_iterations
EXPECTED_TARGET_GLOBAL_STEP = POST_STAGE_200.target_global_step


@dataclass(frozen=True)
class PlannedPostRun:
    operation: str
    mode: str
    replicate_id: str
    output_root: Path
    command: tuple[str, ...]
    artifact_paths: tuple[Path, ...]

    @property
    def command_sha256(self) -> str:
        return p1.sha256_bytes(canonical_json(list(self.command)).encode("utf-8"))

    def as_dict(
        self,
        *,
        artifact_refs: Sequence[Mapping[str, Any]] | None = None,
        telemetry_ref: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        result = {
            "operation": self.operation,
            "mode": self.mode,
            "replicate_id": self.replicate_id,
            "output_root": str(self.output_root),
            "command": list(self.command),
            "command_id": self.command_sha256,
            "command_sha256": self.command_sha256,
            "artifacts": list(artifact_refs or [{"path": str(path)} for path in self.artifact_paths]),
        }
        if telemetry_ref is not None:
            result["telemetry"] = dict(telemetry_ref)
            result["telemetry_artifact"] = {
                key: telemetry_ref[key] for key in ("path", "size_bytes", "sha256")
            }
        return result


@dataclass(frozen=True)
class PostPlan:
    stage: PostStage
    pair_root: Path
    output_root: Path
    n3_root: Path
    n3_phase_manifest_sha256: str
    branch_manifest_shas: Mapping[str, str]
    branch_manifests: Mapping[str, Mapping[str, Any]]
    n3_contract: Mapping[str, Any]
    n3_runs: tuple[PlannedPostRun, ...]
    formal_runs: tuple[PlannedPostRun, ...]
    branch_manifest_sha_snapshot: tuple[tuple[str, str], ...] = ()

    @property
    def all_runs(self) -> tuple[PlannedPostRun, ...]:
        return self.n3_runs + self.formal_runs


def _json_value(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("post manifest cannot contain non-finite floats")
        return value
    if isinstance(value, Mapping):
        return {str(key): _json_value(child) for key, child in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_json_value(child) for child in value]
    raise TypeError(f"post manifest value is not JSON serializable: {type(value).__name__}")


def canonical_json(value: Any) -> str:
    return json.dumps(_json_value(value), sort_keys=True, separators=(",", ":"), allow_nan=False)


def _require_sha(value: Any, name: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise TypeError(f"{name} must be a lowercase SHA256")
    return value


def _under(path: Path, root: Path, name: str) -> Path:
    resolved = path.expanduser().resolve()
    root = root.expanduser().resolve()
    if not resolved.is_relative_to(root):
        raise RuntimeError(f"{name} escapes post output root: {resolved}")
    return resolved


def _validate_post_output_root(path: Path) -> Path:
    root = p1.validate_fresh_output_root(path)
    staging = root.with_name(f".{root.name}.writing")
    if staging.exists():
        raise FileExistsError(f"post runner refuses an existing staging root: {staging}")
    return root


def _arg(command: Sequence[str], flag: str) -> str:
    matches = [index for index, value in enumerate(command) if value == flag]
    if len(matches) != 1 or matches[0] + 1 >= len(command):
        raise RuntimeError(f"planned command must contain one {flag} value")
    return command[matches[0] + 1]


def _has_flag(command: Sequence[str], flag: str) -> bool:
    return sum(value == flag for value in command) == 1


def _stage_for_source_target(source_global_step: Any, target_global_step: Any) -> PostStage:
    source = p1._strict_int(source_global_step, "post source_global_step")
    target = p1._strict_int(target_global_step, "post target_global_step")
    for stage in POST_STAGES:
        if (source, target) == (stage.source_global_step, stage.target_global_step):
            return stage
    raise P1PostBlocked(
        "post branch source/target is outside the exact P1 post-stage grid: "
        f"source={source} target={target}"
    )


def _stage_from_manifest(manifest: Mapping[str, Any]) -> PostStage:
    source = manifest.get("source")
    result = manifest.get("result")
    if not isinstance(source, Mapping) or not isinstance(result, Mapping):
        raise TypeError("post sealed branch source/result must be mappings")
    stage = _stage_for_source_target(source.get("global_step"), result.get("target_global_step"))
    requested = p1._strict_int(result.get("requested_iterations"), "post requested_iterations")
    completed = p1._strict_int(result.get("completed_iterations"), "post completed_iterations")
    run_iterations = p1._strict_int(result.get("run_iterations"), "post run_iterations")
    has_total = "total_completed_iterations" in result
    has_additional = "additional_iterations" in result
    if has_total != has_additional:
        raise P1PostBlocked("post branch total/additional iteration fields must be supplied together")
    total = p1._strict_int(
        result.get("total_completed_iterations", completed),
        "post total_completed_iterations",
    )
    additional = p1._strict_int(
        result.get("additional_iterations", run_iterations),
        "post additional_iterations",
    )
    actual = (requested, completed, total, additional, run_iterations)
    expected = (
        stage.requested_iterations,
        stage.requested_iterations,
        stage.requested_iterations,
        stage.additional_iterations,
        stage.additional_iterations,
    )
    if actual != expected:
        raise P1PostBlocked(
            "post branch iteration tuple is not the exact sealed stage: "
            f"expected={expected} got={actual}"
        )
    if stage is POST_STAGE_500 and not (has_total and has_additional):
        raise P1PostBlocked("500-stage post manifest requires explicit total/additional iteration fields")
    final_checkpoint = manifest.get("final_checkpoint")
    if not isinstance(final_checkpoint, Mapping) or final_checkpoint.get("global_step") != stage.target_global_step:
        raise P1PostBlocked("post final checkpoint is not bound to the exact stage target")
    return stage


def _load_stage_manifest(root: Path, expected_sha256: str, mode: str) -> tuple[PostStage, dict[str, Any]]:
    root = root.expanduser().resolve(strict=True)
    path = root / p1.P1_BRANCH_MANIFEST_FILENAME
    if not path.is_file():
        raise FileNotFoundError(f"post sealed branch manifest is unavailable: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except BaseException as error:
        raise P1PostBlocked(f"post sealed branch manifest JSON cannot be decoded: {path}") from error
    if not isinstance(raw, Mapping):
        raise TypeError("post sealed branch manifest must be a mapping")
    stage = _stage_from_manifest(raw)
    loaded = p1.load_sealed_branch_manifest(
        root,
        expected_sha256=expected_sha256,
        expected_mode=mode,
        expected_target_global_step=stage.target_global_step,
    )
    loaded_stage = _stage_from_manifest(loaded)
    if loaded_stage != stage:
        raise P1PostBlocked("post sealed branch stage identity changed during reload")
    return stage, loaded


def build_gpu7_environment(base: Mapping[str, str] | None = None) -> dict[str, str]:
    """Return the exact physical-GPU7/logical-cuda0 single-process environment."""
    environment = dict(os.environ if base is None else base)
    forbidden = set(getattr(p1, "_ALLOWED_DISTRIBUTED_NAMES", ())) | set(
        getattr(p1, "_FORBIDDEN_DEVICE_NAMES", ())
    )
    for name in list(environment):
        if name in forbidden or name.startswith("A2_GPU_") or name.startswith("A2_EXPECTED_"):
            environment.pop(name, None)
    environment.update(
        {
            "CUDA_VISIBLE_DEVICES": p1.EXPECTED_GPU_INDEX,
            "CUDA_DEVICE_ORDER": p1.EXPECTED_CUDA_DEVICE_ORDER,
            "A2_GPU_BINDING_MODE": p1.EXPECTED_GPU_BINDING_MODE,
            "A2_EXPECTED_WORLD_SIZE": "1",
            "A2_EXPECTED_HOST_GPU_INDEX": p1.EXPECTED_GPU_INDEX,
            "A2_EXPECTED_LOGICAL_GPU_INDEX": p1.EXPECTED_LOGICAL_GPU_INDEX,
            "A2_EXPECTED_GPU_UUID": p1.EXPECTED_GPU_UUID,
            "PYTHONUNBUFFERED": "1",
            "HYDRA_FULL_ERROR": "1",
        }
    )
    p1.validate_gpu_binding_environment(environment)
    return environment


def _validate_gpu_identity(identity: Mapping[str, Any], name: str) -> None:
    expected = {
        "physical_gpu_index": p1.EXPECTED_GPU_INDEX,
        "logical_gpu_index": int(p1.EXPECTED_LOGICAL_GPU_INDEX),
        "logical_device": p1.EXPECTED_LOGICAL_DEVICE,
        "uuid": p1.EXPECTED_GPU_UUID,
        "cuda_visible_devices": p1.EXPECTED_GPU_INDEX,
        "world_size": 1,
        "binding_mode": p1.EXPECTED_GPU_BINDING_MODE,
        "cuda_device_order": p1.EXPECTED_CUDA_DEVICE_ORDER,
    }
    for field, expected_value in expected.items():
        if identity.get(field) != expected_value:
            raise RuntimeError(f"{name} GPU identity drifted for {field}: {identity.get(field)!r}")


def _validate_peak(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise TypeError(f"{name} peak_vram_mib must be finite numeric")
    peak = float(value)
    if peak >= p1.VRAM_LIMIT_MIB:
        raise P1PostBlocked(f"{name} peak VRAM {peak:.3f} MiB reaches the strict limit")
    if peak < 0:
        raise ValueError(f"{name} peak VRAM cannot be negative")
    return peak


def _branch_metrics(manifest: Mapping[str, Any]) -> Mapping[str, Any]:
    evidence = manifest.get("runtime_evidence")
    if not isinstance(evidence, Mapping) or not isinstance(evidence.get("metrics"), Mapping):
        raise TypeError("sealed branch runtime_evidence.metrics must be a mapping")
    return evidence["metrics"]


def _validate_sealed_pair(
    pair_root: Path,
    manifests: Mapping[str, Mapping[str, Any]],
) -> PostStage:
    if set(manifests) != set(POST_BRANCHES):
        raise ValueError("post runner requires exactly sequential and packed branch manifests")
    pair_root = pair_root.expanduser().resolve()
    common_source = None
    pair_stage: PostStage | None = None
    common_target_config = None
    common_runtime = None
    common_teacher = None
    common_effective = None
    common_launch = None
    common_result = None
    for mode in POST_BRANCHES:
        manifest = manifests[mode]
        raw = manifest.get("raw", manifest)
        if not isinstance(raw, Mapping):
            raise TypeError(f"{mode} branch raw manifest must be a mapping")
        branch_root = Path(str(manifest["root"])).expanduser().resolve()
        if branch_root != pair_root / mode:
            raise RuntimeError(f"{mode} branch root is not the exact pair child root")
        stage = _stage_from_manifest(manifest)
        if pair_stage is None:
            pair_stage = stage
        elif stage != pair_stage:
            raise P1PostBlocked("sequential/packed branches are from mixed post-training stages")
        source = manifest.get("source")
        target_config = raw.get("target_config")
        runtime = raw.get("runtime")
        teacher = raw.get("teacher")
        effective = manifest.get("effective_training_contract")
        launch = manifest.get("launch_contract")
        result = manifest.get("result")
        for name, value in (
            ("source", source),
            ("target_config", target_config),
            ("runtime", runtime),
            ("teacher", teacher),
            ("effective_training_contract", effective),
            ("launch_contract", launch),
            ("result", result),
        ):
            if not isinstance(value, Mapping):
                raise TypeError(f"{mode} branch {name} must be a mapping")
        if target_config.get("path") != str(p1.TARGET_CONFIG) or target_config.get("sha256") != p1.sha256_file(p1.TARGET_CONFIG):
            raise RuntimeError("P1 post runner target config is not the exact pinned config")
        if result.get("training_performed") is not True:
            raise RuntimeError("P1 post runner requires training_performed=true")
        if runtime.get("commit") != p1.EXPECTED_RUNTIME_COMMIT:
            raise RuntimeError("P1 post runner c18 runtime commit drifted")
        if runtime.get("clean_gr00t") is not True:
            raise RuntimeError("P1 post runner requires clean c18 gr00t runtime")
        metrics = _branch_metrics(manifest)
        _validate_gpu_identity(metrics.get("gpu_identity"), f"{mode} branch metrics")
        _validate_peak(metrics.get("peak_vram_mib"), f"{mode} branch metrics")
        _validate_peak(result.get("peak_vram_mib"), f"{mode} branch result")
        mode_effective = dict(effective)
        mode_effective.pop("d435i_forward_mode", None)
        mode_launch = dict(launch)
        mode_launch.pop("forward_mode", None)
        mode_result = {
            key: result.get(key)
            for key in (
                "requested_iterations",
                "completed_iterations",
                "total_completed_iterations",
                "additional_iterations",
                "run_iterations",
                "start_global_step",
                "target_global_step",
                "training_performed",
                "backward_call_count",
                "optimizer_step_count",
                "scheduler_step_count",
                "scheduler_step_count_before",
                "scheduler_step_count_after",
                "scheduler_last_epoch_before",
                "scheduler_last_epoch_after",
            )
        }
        source_contract = (
            dict(source)
            if stage == POST_STAGE_200
            else {
                "global_step": source.get("global_step"),
                "checkpoint_load_mode": source.get("checkpoint_load_mode"),
            }
        )
        if common_source is None:
            common_source = source_contract
            common_target_config = target_config
            common_runtime = runtime
            common_teacher = teacher
            common_effective = mode_effective
            common_launch = mode_launch
            common_result = mode_result
        elif any(
            canonical_json(actual) != canonical_json(expected)
            for actual, expected in (
                (source_contract, common_source),
                (target_config, common_target_config),
                (runtime, common_runtime),
                (teacher, common_teacher),
                (mode_effective, common_effective),
                (mode_launch, common_launch),
                (mode_result, common_result),
            )
        ):
            raise P1PostBlocked("sequential/packed branches differ beyond forward mode/root/artifacts")
        if manifest.get("branch") != mode or effective.get("d435i_forward_mode") != mode or launch.get("forward_mode") != mode:
            raise RuntimeError(f"{mode} branch mode identity drifted")
    if pair_stage is None:
        raise AssertionError("post pair stage was not resolved")
    return pair_stage


def _validate_n3_contract(n3_root: Path, expected_phase_sha: str) -> dict[str, Any]:
    n3_root = n3_root.expanduser().resolve(strict=True)
    if n3_root != p1.N3_INPUT_ROOT.expanduser().resolve():
        raise RuntimeError("post runner requires the exact pinned N3 input root")
    contract = p1.validate_n3_contract(n3_root)
    phase = contract.get("phase_manifest")
    if not isinstance(phase, Mapping) or phase.get("sha256") != expected_phase_sha:
        raise RuntimeError("post runner N3 phase manifest SHA256 drifted")
    if phase.get("path") != str(p1.N3_PHASE_MANIFEST.resolve()):
        raise RuntimeError("post runner N3 phase manifest path drifted")
    replicas = contract.get("replicates")
    if not isinstance(replicas, Sequence) or len(replicas) != 3:
        raise RuntimeError("post runner requires exactly three N3 replicates")
    ids = [item.get("replicate_id") for item in replicas if isinstance(item, Mapping)]
    if tuple(ids) != REPLICATE_IDS:
        raise RuntimeError(f"post runner N3 replicate order/identity drifted: {ids!r}")
    for item in replicas:
        if item.get("active_frame_count") != EXPECTED_ACTIVE_FRAME_COUNT:
            raise RuntimeError("post runner N3 active frame count drifted")
        for field in ("h5", "trajectory_manifest"):
            artifact = item.get(field)
            if not isinstance(artifact, Mapping):
                raise TypeError(f"N3 replicate {item.get('replicate_id')} lacks {field} artifact")
            _require_sha(artifact.get("sha256"), f"N3 {item.get('replicate_id')} {field}.sha256")
            path = Path(str(artifact.get("path"))).expanduser().resolve(strict=True)
            if not path.is_file():
                raise FileNotFoundError(path)
    return contract


def _spec_from_manifest(
    mode: str,
    manifest: Mapping[str, Any],
    stage: PostStage | None = None,
) -> p1.P1BranchSpec:
    stage = _stage_from_manifest(manifest) if stage is None else stage
    source = manifest["source"]
    branch_root = Path(str(manifest["root"])).expanduser().resolve(strict=True)
    checkpoint = Path(str(source["checkpoint"]["path"])).expanduser().resolve(strict=True)
    config = Path(str(source["config"]["path"])).expanduser().resolve(strict=True)
    return p1.P1BranchSpec(
        mode=mode,
        root=branch_root,
        checkpoint=checkpoint,
        checkpoint_sha256=str(source["checkpoint"]["sha256"]),
        checkpoint_config=config,
        checkpoint_config_sha256=str(source["config"]["sha256"]),
        start_global_step=stage.source_global_step,
        requested_iterations=stage.requested_iterations,
        run_iterations=stage.additional_iterations,
        target_global_step=stage.target_global_step,
        overrides=(),
        command=(),
    )


def _validate_n3_command(
    command: Sequence[str],
    *,
    mode: str,
    replicate_id: str,
    output_root: Path,
    n3_root: Path,
    n3_contract: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> None:
    if command[1] != str(Path(p1.__file__).resolve()):
        raise RuntimeError("N3 command does not use the pinned P1 runner")
    if "--n3-infer" not in command or _arg(command, "--mode") != mode:
        raise RuntimeError("N3 command mode/topology drifted")
    if _arg(command, "--device") != p1.EXPECTED_LOGICAL_DEVICE:
        raise P1PostBlocked("N3 command is not bound to logical cuda:0")
    if "--recurrent-reset-per-replicate" not in command:
        raise RuntimeError("N3 command lacks recurrent reset per replicate")
    if Path(_arg(command, "--output")).resolve() != output_root.resolve():
        raise RuntimeError("N3 command output escapes its planned root")
    if Path(_arg(command, "--n3-root")).resolve() != n3_root.resolve():
        raise RuntimeError("N3 command N3 root drifted")
    if _arg(command, "--replicate-id") != replicate_id:
        raise RuntimeError("N3 command replicate identity drifted")
    identity = manifest["final_checkpoint"]
    config = manifest["final_config"]
    expected_pairs = {
        "--checkpoint": identity["path"],
        "--checkpoint-sha256": identity["sha256"],
        "--config": config["path"],
        "--config-sha256": config["sha256"],
        "--n3-phase-manifest": n3_contract["phase_manifest"]["path"],
        "--n3-phase-manifest-sha256": n3_contract["phase_manifest"]["sha256"],
    }
    for flag, expected in expected_pairs.items():
        if _arg(command, flag) != str(expected):
            raise RuntimeError(f"N3 command {flag} identity drifted")
    replicate = next(item for item in n3_contract["replicates"] if item["replicate_id"] == replicate_id)
    for flag, field in (
        ("--n3-h5", "h5"),
        ("--n3-h5-sha256", "h5"),
        ("--n3-trajectory-manifest", "trajectory_manifest"),
        ("--n3-trajectory-manifest-sha256", "trajectory_manifest"),
    ):
        key = "path" if flag.endswith("manifest") or flag == "--n3-h5" else "sha256"
        if _arg(command, flag) != str(replicate[field][key]):
            raise RuntimeError(f"N3 command {flag} identity drifted")
    if "--render" in command or "last.pt" in canonical_json(list(command)):
        raise RuntimeError("N3 command contains forbidden rendering/resume discovery")


def _validate_formal_command(
    command: Sequence[str],
    *,
    mode: str,
    replicate_id: str,
    output_root: Path,
    manifest: Mapping[str, Any],
    stage: PostStage = POST_STAGE_200,
) -> None:
    if Path(command[1]).name != "run_a2_student_eval_v19.py":
        raise RuntimeError("formal command does not use evaluator-v2")
    for flag, expected in (
        ("--mode", "formal"),
        ("--controller", "student"),
        ("--replicate-id", replicate_id),
        ("--case-seed", "0"),
        ("--student-d435i-forward-mode", mode),
        ("--expected-global-step", str(stage.target_global_step)),
    ):
        if _arg(command, flag) != expected:
            raise RuntimeError(f"formal command {flag} contract drifted")
    if Path(_arg(command, "--output-root")).resolve() != output_root.resolve():
        raise RuntimeError("formal command output escapes its planned root")
    if _arg(command, "--checkpoint") != manifest["final_checkpoint"]["path"]:
        raise RuntimeError("formal command checkpoint path drifted")
    if _arg(command, "--checkpoint-sha256") != manifest["final_checkpoint"]["sha256"]:
        raise RuntimeError("formal command checkpoint SHA256 drifted")
    if _arg(command, "--checkpoint-config") != manifest["final_config"]["path"]:
        raise RuntimeError("formal command config path drifted")
    if _arg(command, "--checkpoint-config-sha256") != manifest["final_config"]["sha256"]:
        raise RuntimeError("formal command config SHA256 drifted")
    if "--render" in command or any("teacher" in value.lower() for value in command):
        raise RuntimeError("formal command is not pure Student/no-render")


def build_post_plan(
    pair_root: Path = PAIR_ROOT,
    *,
    sequential_manifest_sha256: str = SEQUENTIAL_MANIFEST_SHA256,
    packed_manifest_sha256: str = PACKED_MANIFEST_SHA256,
    output_root: Path,
    n3_root: Path = p1.N3_INPUT_ROOT,
    n3_phase_manifest_sha256: str = p1.N3_PHASE_MANIFEST_SHA256,
) -> PostPlan:
    """Validate sealed inputs and build exactly six N3 plus six formal runs."""
    pair_root = pair_root.expanduser().resolve(strict=True)
    output_root = _validate_post_output_root(output_root)
    seq_sha = _require_sha(sequential_manifest_sha256, "sequential manifest SHA256")
    packed_sha = _require_sha(packed_manifest_sha256, "packed manifest SHA256")
    expected_phase_sha = _require_sha(n3_phase_manifest_sha256, "N3 phase manifest SHA256")
    sequential_stage, sequential_manifest = _load_stage_manifest(
        pair_root / "sequential", seq_sha, "sequential"
    )
    packed_stage, packed_manifest = _load_stage_manifest(
        pair_root / "packed", packed_sha, "packed"
    )
    if sequential_stage != packed_stage:
        raise P1PostBlocked("sequential/packed branches are from mixed post-training stages")
    manifests = {"sequential": sequential_manifest, "packed": packed_manifest}
    stage = _validate_sealed_pair(pair_root, manifests)
    n3_contract = _validate_n3_contract(n3_root, expected_phase_sha)
    n3_runs: list[PlannedPostRun] = []
    formal_runs: list[PlannedPostRun] = []
    for mode in POST_BRANCHES:
        for replicate_id in REPLICATE_IDS:
            output = output_root / mode / "n3" / replicate_id
            command = p1.build_n3_inference_command(
                manifests[mode],
                n3_root,
                output,
                replicate_id=replicate_id,
                n3_contract=n3_contract,
            )
            _validate_n3_command(
                command,
                mode=mode,
                replicate_id=replicate_id,
                output_root=output,
                n3_root=n3_root,
                n3_contract=n3_contract,
                manifest=manifests[mode],
            )
            n3_runs.append(
                PlannedPostRun(
                    "n3",
                    mode,
                    replicate_id,
                    output,
                    tuple(command),
                    (output / N3_ACTION_FILENAME,),
                )
            )
    for mode in POST_BRANCHES:
        spec = _spec_from_manifest(mode, manifests[mode], stage)
        for replicate_id in REPLICATE_IDS:
            output = output_root / mode / "formal" / replicate_id
            command = p1.build_formal_eval_command(spec, output, replicate_id=replicate_id)
            _validate_formal_command(
                command,
                mode=mode,
                replicate_id=replicate_id,
                output_root=output,
                manifest=manifests[mode],
                stage=stage,
            )
            formal_runs.append(
                PlannedPostRun(
                    "formal",
                    mode,
                    replicate_id,
                    output,
                    tuple(command),
                    (output / FORMAL_METRICS_FILENAME, output / FORMAL_SELECTION_FILENAME),
                )
            )
    if len(n3_runs) != 6 or len(formal_runs) != 6:
        raise AssertionError("post plan cardinality is not exactly 6+6")
    return PostPlan(
        stage=stage,
        pair_root=pair_root,
        output_root=output_root,
        n3_root=n3_root.expanduser().resolve(strict=True),
        n3_phase_manifest_sha256=expected_phase_sha,
        branch_manifest_shas={"sequential": seq_sha, "packed": packed_sha},
        branch_manifests=manifests,
        n3_contract=n3_contract,
        n3_runs=tuple(n3_runs),
        formal_runs=tuple(formal_runs),
        branch_manifest_sha_snapshot=tuple(
            (mode, manifests_sha)
            for mode, manifests_sha in (("sequential", seq_sha), ("packed", packed_sha))
        ),
    )


def _artifact_ref(path: Path, root: Path) -> dict[str, Any]:
    path = _under(path, root, "post artifact")
    if not path.is_file():
        raise FileNotFoundError(f"post artifact is unavailable: {path}")
    return {"path": str(path), "size_bytes": path.stat().st_size, "sha256": p1.sha256_file(path)}


def _strict_telemetry_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise P1PostBlocked(f"post GPU telemetry {name} must be numeric")
    if not math.isfinite(float(value)):
        raise P1PostBlocked(f"post GPU telemetry {name} must be finite")
    return float(value)


def _strict_telemetry_identity(payload: Mapping[str, Any], name: str) -> None:
    expected = {
        "physical_gpu_index": p1.EXPECTED_GPU_INDEX,
        "logical_device": p1.EXPECTED_LOGICAL_DEVICE,
        "uuid": p1.EXPECTED_GPU_UUID,
        "cuda_visible_devices": p1.EXPECTED_GPU_INDEX,
        "world_size": 1,
    }
    for field, expected_value in expected.items():
        value = payload.get(field)
        if type(value) is not type(expected_value) or value != expected_value:
            raise P1PostBlocked(f"post GPU telemetry {name}.{field} identity/type drifted")


def _load_child_telemetry(path: Path) -> dict[str, Any]:
    """Load only the exact sampler artifact and enforce its complete schema."""
    try:
        summary = p1.load_gpu_telemetry_peak_vram(path)
    except BaseException as error:
        raise P1PostBlocked(f"post GPU telemetry is invalid: {path}") from error
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except BaseException as error:
        raise P1PostBlocked(f"post GPU telemetry JSON cannot be decoded: {path}") from error
    if not isinstance(payload, Mapping):
        raise P1PostBlocked("post GPU telemetry wrapper must be a JSON object")
    allowed_fields = {
        "schema",
        "physical_gpu_index",
        "logical_device",
        "uuid",
        "cuda_visible_devices",
        "world_size",
        "started_at_epoch_s",
        "ended_at_epoch_s",
        "samples",
        "peak_vram_mib",
        "manifest_content_sha256",
    }
    if set(payload) != allowed_fields:
        raise P1PostBlocked("post GPU telemetry wrapper schema has unexpected or missing fields")
    manifest_content_sha256 = payload.get("manifest_content_sha256")
    if not isinstance(manifest_content_sha256, str) or re.fullmatch(r"[0-9a-f]{64}", manifest_content_sha256) is None:
        raise P1PostBlocked("post GPU telemetry manifest content SHA256 is malformed")
    unsigned_payload = dict(payload)
    unsigned_payload.pop("manifest_content_sha256")
    if manifest_content_sha256 != p1.sha256_bytes(p1.canonical_json(unsigned_payload).encode("utf-8")):
        raise P1PostBlocked("post GPU telemetry manifest content SHA256 drifted")
    if payload.get("schema") != TELEMETRY_SCHEMA:
        raise P1PostBlocked("post GPU telemetry schema drifted")
    _strict_telemetry_identity(payload, "wrapper")
    started = _strict_telemetry_number(payload.get("started_at_epoch_s"), "started_at_epoch_s")
    ended = _strict_telemetry_number(payload.get("ended_at_epoch_s"), "ended_at_epoch_s")
    if ended < started:
        raise P1PostBlocked("post GPU telemetry timestamps are not monotonic")
    samples = payload.get("samples")
    if not isinstance(samples, list) or not samples:
        raise P1PostBlocked("post GPU telemetry must contain at least one sample")
    sample_fields = {
        "physical_gpu_index",
        "logical_device",
        "uuid",
        "cuda_visible_devices",
        "world_size",
        "peak_vram_mib",
        "sample_epoch_s",
    }
    sample_peaks: list[float] = []
    sample_stamps: list[float] = []
    for index, sample in enumerate(samples):
        if not isinstance(sample, Mapping) or set(sample) != sample_fields:
            raise P1PostBlocked(f"post GPU telemetry sample {index} schema drifted")
        _strict_telemetry_identity(sample, f"sample[{index}]")
        sample_peaks.append(
            _validate_peak(
                _strict_telemetry_number(sample.get("peak_vram_mib"), f"sample[{index}].peak_vram_mib"),
                f"sample[{index}].peak_vram_mib",
            )
        )
        sample_stamps.append(
            _strict_telemetry_number(sample.get("sample_epoch_s"), f"sample[{index}].sample_epoch_s")
        )
    if any(later < earlier for earlier, later in zip(sample_stamps, sample_stamps[1:])):
        raise P1PostBlocked("post GPU telemetry sample timestamps are not monotonic")
    declared_peak = _validate_peak(
        _strict_telemetry_number(payload.get("peak_vram_mib"), "peak_vram_mib"),
        "wrapper.peak_vram_mib",
    )
    if declared_peak != max(sample_peaks):
        raise P1PostBlocked("post GPU telemetry declared peak does not match its samples")
    if summary["record_count"] != len(samples) or summary["peak_vram_mib"] != declared_peak:
        raise P1PostBlocked("post GPU telemetry loader summary disagrees with its sealed payload")
    return {
        **summary,
        "record_count": len(samples),
        "peak_vram_mib": declared_peak,
        "started_at_epoch_s": started,
        "ended_at_epoch_s": ended,
    }


def _failure_json_value(value: Any) -> Any:
    """Make an invalid telemetry payload retainable without hiding its failure."""
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _failure_json_value(child) for key, child in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_failure_json_value(child) for child in value]
    return repr(value)


def _write_unvalidated_json(path: Path, payload: Mapping[str, Any]) -> None:
    """Retain malformed sampler evidence so the caller can fail closed."""
    staging = path.with_name(f".{path.name}.writing")
    if staging.exists():
        raise P1PostBlocked(f"post GPU telemetry staging path already exists: {staging}")
    staging.write_text(
        json.dumps(_failure_json_value(payload), sort_keys=True, indent=2, allow_nan=True),
        encoding="utf-8",
    )
    os.replace(staging, path)


def _failed_telemetry_payload(sampler: Any, error: BaseException) -> dict[str, Any]:
    samples = getattr(sampler, "samples", [])
    if not isinstance(samples, list):
        samples = [samples]
    started = getattr(sampler, "started_at_epoch_s", time.time())
    ended = getattr(sampler, "ended_at_epoch_s", time.time())
    numeric_peaks = [
        float(sample["peak_vram_mib"])
        for sample in samples
        if isinstance(sample, Mapping)
        and not isinstance(sample.get("peak_vram_mib"), bool)
        and isinstance(sample.get("peak_vram_mib"), (int, float))
    ]
    peak: Any = max(numeric_peaks) if numeric_peaks else None
    return {
        "schema": TELEMETRY_SCHEMA,
        "physical_gpu_index": p1.EXPECTED_GPU_INDEX,
        "logical_device": p1.EXPECTED_LOGICAL_DEVICE,
        "uuid": p1.EXPECTED_GPU_UUID,
        "cuda_visible_devices": p1.EXPECTED_GPU_INDEX,
        "world_size": 1,
        "started_at_epoch_s": started,
        "ended_at_epoch_s": ended,
        "samples": samples,
        "peak_vram_mib": peak,
        "telemetry_error": f"{type(error).__name__}: {error}",
    }


def _seal_child_telemetry(run: PlannedPostRun, sampler: Any) -> dict[str, Any]:
    if run.output_root.is_symlink() or not run.output_root.is_dir():
        raise P1PostBlocked(f"child telemetry root is not a real directory: {run.output_root}")
    path = _under(run.output_root / TELEMETRY_FILENAME, run.output_root, "child telemetry")
    if path.exists():
        raise P1PostBlocked(f"child reserved telemetry path already exists: {path}")
    try:
        payload = sampler.stop()
    except BaseException as stop_error:
        payload = _failed_telemetry_payload(sampler, stop_error)
        _write_unvalidated_json(path, payload)
        try:
            _load_child_telemetry(path)
        except BaseException:
            raise
        raise P1PostBlocked("post GPU telemetry sampler failed") from stop_error
    if not isinstance(payload, Mapping):
        payload = _failed_telemetry_payload(sampler, TypeError("sampler.stop() did not return a mapping"))
        _write_unvalidated_json(path, payload)
        raise P1PostBlocked("post GPU telemetry sampler returned a non-mapping")
    try:
        p1.seal_json(path, payload)
    except BaseException as seal_error:
        if not path.exists():
            _write_unvalidated_json(path, _failed_telemetry_payload(sampler, seal_error))
        raise P1PostBlocked("post GPU telemetry could not be sealed") from seal_error
    return _load_child_telemetry(path)


def _child_telemetry_ref(run: PlannedPostRun, summary: Mapping[str, Any]) -> dict[str, Any]:
    path = (run.output_root / TELEMETRY_FILENAME).expanduser().resolve(strict=True)
    if summary.get("path") != str(path):
        raise P1PostBlocked("post GPU telemetry summary path drifted")
    return {
        "path": str(path),
        "size_bytes": path.stat().st_size,
        "sha256": p1.sha256_file(path),
        "schema": summary["schema"],
        "record_count": summary["record_count"],
        "peak_vram_mib": summary["peak_vram_mib"],
        "physical_gpu_index": summary["physical_gpu_index"],
        "logical_device": summary["logical_device"],
        "uuid": summary["uuid"],
        "cuda_visible_devices": summary["cuda_visible_devices"],
        "world_size": summary["world_size"],
        "operation": run.operation,
        "mode": run.mode,
        "replicate_id": run.replicate_id,
        "command_id": run.command_sha256,
    }


def _telemetry_ref(run: PlannedPostRun, root: Path) -> dict[str, Any]:
    path = _under(run.output_root / TELEMETRY_FILENAME, root, "post GPU telemetry")
    summary = _load_child_telemetry(path)
    ref = _child_telemetry_ref(run, summary)
    return ref


def _write_process_log(run: PlannedPostRun, result: subprocess.CompletedProcess[str]) -> None:
    run.output_root.mkdir(parents=True, exist_ok=True)
    stdout = result.stdout if isinstance(result.stdout, str) else ""
    stderr = result.stderr if isinstance(result.stderr, str) else ""
    (run.output_root / "post_runner.stdout.log").write_text(stdout, encoding="utf-8")
    (run.output_root / "post_runner.stderr.log").write_text(stderr, encoding="utf-8")


def _ensure_child_root_after_child(run: PlannedPostRun) -> bool:
    """Validate a child-owned root, creating it only after the child has returned."""
    if run.output_root.is_symlink():
        raise P1PostBlocked(f"child output root must not be a symlink: {run.output_root}")
    if run.output_root.exists():
        if not run.output_root.is_dir():
            raise NotADirectoryError(f"child output root is not a directory: {run.output_root}")
        return False
    run.output_root.mkdir(parents=True, exist_ok=False)
    return True


def _normalize_n3_artifact(run: PlannedPostRun) -> Path:
    plural = run.output_root / N3_ACTION_FILENAME
    singular = run.output_root / N3_CHILD_ACTION_FILENAME
    if plural.exists() and singular.exists():
        raise RuntimeError("N3 child emitted both singular and post action manifests")
    if not plural.exists() and singular.is_file():
        os.replace(singular, plural)
    if not plural.is_file():
        raise FileNotFoundError(f"N3 action artifact is unavailable: {plural}")
    return plural


def _write_child_failure(
    run: PlannedPostRun,
    *,
    result: subprocess.CompletedProcess[str] | None,
    child_error: BaseException | None,
    telemetry_error: BaseException | None,
    telemetry_ref: Mapping[str, Any] | None,
) -> None:
    if run.output_root.is_symlink() or not run.output_root.is_dir():
        raise P1PostBlocked(f"child failure root is not a real directory: {run.output_root}")
    path = run.output_root / "p1_post_child_failure.json"
    if path.exists():
        return
    payload: dict[str, Any] = {
        "schema": "a2_cb2h_pro_p1_post_child_failure_v1",
        "operation": run.operation,
        "mode": run.mode,
        "replicate_id": run.replicate_id,
        "command_id": run.command_sha256,
        "returncode": None if result is None else result.returncode,
        "child_error": None if child_error is None else f"{type(child_error).__name__}: {child_error}",
        "telemetry_error": None
        if telemetry_error is None
        else f"{type(telemetry_error).__name__}: {telemetry_error}",
        "telemetry_path": str(run.output_root / TELEMETRY_FILENAME),
    }
    if telemetry_ref is not None:
        payload["telemetry"] = dict(telemetry_ref)
    p1.seal_json(path, payload)


def _run_one(run: PlannedPostRun, environment: Mapping[str, str]) -> dict[str, Any]:
    p1.validate_gpu_binding_environment(environment)
    if run.output_root.exists() or run.output_root.is_symlink():
        raise FileExistsError(f"child output root must be absent before spawn: {run.output_root}")
    sampler = p1.GpuTelemetrySampler(dict(environment))
    sampler.start()
    result: subprocess.CompletedProcess[str] | None = None
    child_error: BaseException | None = None
    telemetry_error: BaseException | None = None
    telemetry_summary: dict[str, Any] | None = None
    try:
        try:
            result = subprocess.run(
                list(run.command),
                cwd=str(REPO_ROOT),
                env=dict(environment),
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                child_error = RuntimeError(
                    f"P1 post {run.operation} failed for {run.mode}/{run.replicate_id}: "
                    f"returncode={result.returncode}"
                )
        except BaseException as error:
            child_error = error
        try:
            runner_created_root = _ensure_child_root_after_child(run)
            if runner_created_root and child_error is None:
                child_error = FileNotFoundError(
                    f"child did not create its output root: {run.output_root}"
                )
        except BaseException as error:
            if child_error is None:
                child_error = error
        if result is not None and run.output_root.is_dir() and not run.output_root.is_symlink():
            try:
                _write_process_log(run, result)
            except BaseException as error:
                if child_error is None:
                    child_error = error
        elif child_error is not None and run.output_root.is_dir():
            (run.output_root / "post_runner.stderr.log").write_text(
                f"{type(child_error).__name__}: {child_error}\n", encoding="utf-8"
            )
    finally:
        try:
            telemetry_summary = _seal_child_telemetry(run, sampler)
        except BaseException as error:
            telemetry_error = error
    telemetry_ref = None
    if telemetry_summary is not None:
        try:
            telemetry_ref = _child_telemetry_ref(run, telemetry_summary)
        except BaseException as error:
            telemetry_error = telemetry_error or error
    if child_error is not None or telemetry_error is not None:
        _write_child_failure(
            run,
            result=result,
            child_error=child_error,
            telemetry_error=telemetry_error,
            telemetry_ref=telemetry_ref,
        )
        if telemetry_error is not None:
            if child_error is not None:
                raise telemetry_error from child_error
            raise telemetry_error
        if child_error is None:
            raise RuntimeError("post child failure state lost its root error")
        raise child_error
    try:
        if run.operation == "n3":
            _normalize_n3_artifact(run)
        else:
            for path in run.artifact_paths:
                if not path.is_file():
                    raise FileNotFoundError(f"formal artifact is unavailable: {path}")
    except BaseException as error:
        _write_child_failure(
            run,
            result=result,
            child_error=error,
            telemetry_error=None,
            telemetry_ref=telemetry_ref,
        )
        raise
    assert telemetry_summary is not None
    return _child_telemetry_ref(run, telemetry_summary)


def _formal_report(plan: PostPlan, formal_refs: Mapping[str, Sequence[Mapping[str, Any]]]) -> dict[str, Any]:
    """Create per-replicate reporting only; P1 path adjudication owns the verdict."""
    per_replicate: dict[str, list[dict[str, Any]]] = {mode: [] for mode in POST_BRANCHES}
    records: dict[str, dict[str, list[Mapping[str, Any]]]] = {mode: {} for mode in POST_BRANCHES}
    for mode in POST_BRANCHES:
        for ref in formal_refs[mode]:
            path = Path(str(ref["metrics_path"])).expanduser().resolve(strict=True)
            payload = json.loads(path.read_text(encoding="utf-8"))
            episodes = payload.get("episodes")
            if not isinstance(episodes, list) or len(episodes) != p1.EXPECTED_EPISODES:
                raise RuntimeError("formal report requires exactly 16 episodes per replicate")
            replicate_id = str(ref["replicate_id"])
            env_ids = {int(item["env_id"]) for item in episodes}
            if env_ids == set(range(1, p1.EXPECTED_EPISODES + 1)):
                normalized_episodes = [dict(item, env_id=int(item["env_id"]) - 1) for item in episodes]
            elif env_ids == set(range(p1.EXPECTED_EPISODES)):
                normalized_episodes = episodes
            else:
                raise P1PostBlocked("formal report case identity is not exact env_id 0..15 or 1..16")
            records[mode][replicate_id] = normalized_episodes
            stages = [int(item["max_stage"]) for item in normalized_episodes]
            rewards = [float(item["reward"]) for item in normalized_episodes if isinstance(item.get("reward"), (int, float))]
            per_replicate[mode].append(
                {
                    "replicate_id": replicate_id,
                    "count": len(normalized_episodes),
                    "goals": sum(item.get("goal_reached") is True for item in normalized_episodes),
                    "stage0_count": sum(stage == 0 for stage in stages),
                    "mean_max_stage": sum(stages) / len(stages),
                    "mean_reward": sum(rewards) / len(rewards) if rewards else None,
                }
            )
    paired: list[dict[str, Any]] = []
    for replicate_id in REPLICATE_IDS:
        seq = {int(item["env_id"]): item for item in records["sequential"][replicate_id]}
        packed = {int(item["env_id"]): item for item in records["packed"][replicate_id]}
        if set(seq) != set(packed) or set(seq) != set(range(p1.EXPECTED_EPISODES)):
            raise P1PostBlocked("formal paired case identity is not exact env_id 0..15")
        seq_stages = [int(seq[index]["max_stage"]) for index in range(p1.EXPECTED_EPISODES)]
        packed_stages = [int(packed[index]["max_stage"]) for index in range(p1.EXPECTED_EPISODES)]
        paired.append(
            {
                "replicate_id": replicate_id,
                "mean_stage_delta": (sum(packed_stages) - sum(seq_stages)) / p1.EXPECTED_EPISODES,
                "stage0_count_reduction": seq_stages.count(0) - packed_stages.count(0),
                "stage0_count_reduction_per_16": seq_stages.count(0) - packed_stages.count(0),
                "goal_count_delta": sum(packed[index].get("goal_reached") is True for index in range(p1.EXPECTED_EPISODES))
                - sum(seq[index].get("goal_reached") is True for index in range(p1.EXPECTED_EPISODES)),
            }
        )
    return {"per_replicate": per_replicate, "paired_deltas": paired}


def _decision(
    adjudication: Mapping[str, Any],
    stage: PostStage = POST_STAGE_200,
) -> dict[str, Any]:
    status = adjudication.get("status")
    outcomes = adjudication.get("formal_outcomes")
    if not isinstance(outcomes, Mapping):
        raise TypeError("P1 adjudicator formal_outcomes must be a mapping")
    packed = outcomes.get("packed")
    if not isinstance(packed, Mapping):
        raise TypeError("P1 adjudicator packed formal outcome must be a mapping")
    packed_goals = packed.get("goals")
    if isinstance(packed_goals, bool) or not isinstance(packed_goals, int):
        raise TypeError("P1 adjudicator packed goals must be an integer")
    gates = adjudication.get("directional_gates")
    if not isinstance(gates, Mapping):
        raise TypeError("P1 adjudicator directional_gates must be a mapping")
    gate_map = gates.get("gates")
    if not isinstance(gate_map, Mapping):
        raise TypeError("P1 adjudicator gate map must be a mapping")
    directional_pass = any(isinstance(value, Mapping) and value.get("pass") is True for value in gate_map.values())
    policy_quality_pass = packed_goals > 0 and directional_pass and status == "PASS_DIRECTIONAL"
    if stage == POST_STAGE_200:
        decision = DECISION_PASS if policy_quality_pass else DECISION_EXTEND
        verdict = DECISION_DIRECTIONAL_SUPPORT if decision == DECISION_PASS else DECISION_EXTEND
        extend_both_only = decision == DECISION_EXTEND
    elif directional_pass:
        decision = DECISION_DIRECTIONAL_SUPPORT
        verdict = DECISION_DIRECTIONAL_SUPPORT
        extend_both_only = False
    else:
        decision = DECISION_STOP
        verdict = DECISION_STOP
        extend_both_only = False
    return {
        "decision": decision,
        "verdict": verdict,
        "stage_id": stage.stage_id,
        "requested_iterations": stage.requested_iterations,
        "additional_iterations": stage.additional_iterations,
        "source_global_step": stage.source_global_step,
        "target_global_step": stage.target_global_step,
        "adjudicator_status": status,
        "directional_support": directional_pass,
        "packed_goal_count": packed_goals,
        "zero_goals_is_not_policy_quality_pass": packed_goals == 0,
        "policy_quality_pass": policy_quality_pass,
        "extend_both_only": extend_both_only,
        "terminal": stage == POST_STAGE_500,
    }


def _run_refs(plan: PostPlan) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
    actions: dict[str, list[dict[str, Any]]] = {mode: [] for mode in POST_BRANCHES}
    formal: dict[str, list[dict[str, Any]]] = {mode: [] for mode in POST_BRANCHES}
    for run in plan.n3_runs:
        path = _artifact_ref(run.artifact_paths[0], plan.output_root)
        actions[run.mode].append({"replicate_id": run.replicate_id, **path})
    for run in plan.formal_runs:
        metrics = _artifact_ref(run.artifact_paths[0], plan.output_root)
        selection = _artifact_ref(run.artifact_paths[1], plan.output_root)
        formal[run.mode].append(
            {
                "replicate_id": run.replicate_id,
                "metrics_path": metrics["path"],
                "metrics_sha256": metrics["sha256"],
                "selection_path": selection["path"],
                "selection_sha256": selection["sha256"],
            }
        )
    for mode in POST_BRANCHES:
        actions[mode].sort(key=lambda item: item["replicate_id"])
        formal[mode].sort(key=lambda item: item["replicate_id"])
    return actions, formal


def _run_key(run: PlannedPostRun) -> tuple[str, str, str]:
    return run.operation, run.mode, run.replicate_id


def _ordered_telemetry_refs(
    plan: PostPlan,
    telemetry_by_run: Mapping[tuple[str, str, str], Mapping[str, Any]],
) -> dict[str, Any]:
    expected_runs = plan.all_runs
    expected_keys = {_run_key(run) for run in expected_runs}
    if set(telemetry_by_run) != expected_keys or len(telemetry_by_run) != len(expected_runs):
        raise P1PostBlocked("post GPU telemetry is not present for exactly the planned child runs")
    refs: list[dict[str, Any]] = []
    for run in expected_runs:
        key = _run_key(run)
        ref = _telemetry_ref(run, plan.output_root)
        recorded = telemetry_by_run[key]
        for field in ("path", "size_bytes", "sha256", "record_count", "peak_vram_mib"):
            if recorded.get(field) != ref.get(field):
                raise P1PostBlocked(f"post GPU telemetry ref drifted for {run.operation}/{run.mode}/{run.replicate_id}")
        if recorded.get("command_id") not in (None, run.command_sha256):
            raise P1PostBlocked("post GPU telemetry command alignment drifted")
        ref["operation"] = run.operation
        ref["mode"] = run.mode
        ref["replicate_id"] = run.replicate_id
        ref["command_id"] = run.command_sha256
        refs.append(ref)
    paths = [ref["path"] for ref in refs]
    command_ids = [ref["command_id"] for ref in refs]
    if len(set(paths)) != len(expected_runs):
        raise P1PostBlocked("post GPU telemetry artifacts are not exactly distinct")
    if len(set(command_ids)) != len(expected_runs):
        raise P1PostBlocked("post GPU telemetry artifacts are not aligned to distinct command IDs")
    overall_peak = _validate_peak(
        max(float(ref["peak_vram_mib"]) for ref in refs),
        "overall post GPU telemetry peak_vram_mib",
    )
    return {
        "schema": TELEMETRY_SCHEMA,
        "limit_mib": p1.VRAM_LIMIT_MIB,
        "run_count": len(refs),
        "overall_peak_vram_mib": overall_peak,
        "peak_vram_mib": overall_peak,
        "artifacts": refs,
    }


def _assert_current_branch_manifest_hashes(plan: PostPlan) -> None:
    """Require each on-disk branch manifest to match its supplied identity."""
    if set(plan.branch_manifest_shas) != set(POST_BRANCHES):
        raise P1PostBlocked("post branch manifest SHA mapping is not exactly sequential/packed")
    for mode in POST_BRANCHES:
        expected = _require_sha(plan.branch_manifest_shas[mode], f"{mode} manifest SHA256")
        path = plan.pair_root / mode / p1.P1_BRANCH_MANIFEST_FILENAME
        if not path.is_file():
            raise FileNotFoundError(f"post sealed branch manifest is unavailable: {path}")
        actual = p1.sha256_file(path)
        if actual != expected:
            raise P1PostBlocked(
                f"{mode} post branch manifest SHA256 drifted: expected={expected} actual={actual}"
            )


def _reload_stage500_plan_inputs(plan: PostPlan) -> PostPlan:
    """Reload and reseal stage-500 branch identities immediately before adjudication."""
    if plan.stage != POST_STAGE_500:
        _assert_current_branch_manifest_hashes(plan)
        return plan
    supplied_snapshot = tuple(
        (mode, plan.branch_manifest_shas.get(mode)) for mode in POST_BRANCHES
    )
    if plan.branch_manifest_sha_snapshot and supplied_snapshot != plan.branch_manifest_sha_snapshot:
        raise P1PostBlocked("supplied branch manifest SHA drifted after post plan creation")
    _assert_current_branch_manifest_hashes(plan)
    fresh_manifests: dict[str, dict[str, Any]] = {}
    for mode in POST_BRANCHES:
        stage, manifest = _load_stage_manifest(
            plan.pair_root / mode,
            plan.branch_manifest_shas[mode],
            mode,
        )
        if stage != POST_STAGE_500:
            raise P1PostBlocked("stage-500 final reload found a non-500 branch manifest")
        fresh_manifests[mode] = manifest
    stage = _validate_sealed_pair(plan.pair_root, fresh_manifests)
    if stage != POST_STAGE_500:
        raise P1PostBlocked("stage-500 final reload did not validate an exact POST_STAGE_500 pair")
    return replace(plan, stage=stage, branch_manifests=fresh_manifests)


def _branch_input_refs(plan: PostPlan) -> dict[str, Any]:
    _assert_current_branch_manifest_hashes(plan)
    result: dict[str, Any] = {}
    for mode in POST_BRANCHES:
        manifest = plan.branch_manifests[mode]
        path = plan.pair_root / mode / p1.P1_BRANCH_MANIFEST_FILENAME
        actual = p1.sha256_file(path)
        result[mode] = {
            "manifest": {"path": str(path), "sha256": actual, "size_bytes": path.stat().st_size},
            "root": str(plan.pair_root / mode),
            "mode": mode,
            "source": manifest["source"],
            "final_checkpoint": manifest["final_checkpoint"],
            "final_config": manifest["final_config"],
            "target_config": manifest["raw"].get("target_config", manifest.get("target_config")),
            "runtime": manifest["raw"].get("runtime", manifest.get("runtime")),
            "teacher": manifest["raw"].get("teacher", manifest.get("teacher")),
            "target_global_step": plan.stage.target_global_step,
            "requested_iterations": plan.stage.requested_iterations,
            "additional_iterations": plan.stage.additional_iterations,
        }
    return result


def _write_failure(root: Path, error: BaseException, *, operation: str = POST_OPERATION) -> None:
    if not root.exists() or (root / FINAL_MANIFEST_FILENAME).exists():
        return
    path = root / FAILURE_FILENAME
    if path.exists():
        return
    payload = {
        "schema": "a2_cb2h_pro_p1_post_failure_v1",
        "operation": operation,
        "root": str(root),
        "error_type": type(error).__name__,
        "error_message": str(error),
    }
    p1.seal_json(path, payload)


def _adjudicate_stage500_from_paths(
    plan: PostPlan,
    formal_artifacts: Mapping[str, Sequence[Mapping[str, Any]]],
    action_artifacts: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    """Run the same sealed-path adjudication gates for the 500-stage tuple."""
    _assert_current_branch_manifest_hashes(plan)
    if set(formal_artifacts) != set(p1.P1_BRANCHES) or set(action_artifacts) != set(p1.P1_BRANCHES):
        raise ValueError("P1 500-stage adjudication requires both branch artifact sets")
    branch_identities = {
        mode: {
            "branch": mode,
            "final_checkpoint": plan.branch_manifests[mode]["final_checkpoint"],
            "final_config": plan.branch_manifests[mode]["final_config"],
        }
        for mode in p1.P1_BRANCHES
    }
    expected_experience = plan.n3_contract.get("experience_identity")
    if not isinstance(expected_experience, Mapping):
        raise RuntimeError("P1 500-stage adjudication lacks one exact N3 experience identity")
    n3_replicate_ids = {
        item.get("replicate_id")
        for item in plan.n3_contract.get("replicates", [])
        if isinstance(item, Mapping)
    }
    if len(n3_replicate_ids) != 3 or any(not isinstance(value, str) for value in n3_replicate_ids):
        raise RuntimeError("P1 500-stage N3 contract must contain three distinct replicate IDs")
    formal_records: dict[str, list[Mapping[str, Any]]] = {}
    nrmse: dict[str, Mapping[str, Any]] = {}
    expected_phase_sha = plan.n3_phase_manifest_sha256
    for mode in p1.P1_BRANCHES:
        metrics_by_rep = formal_artifacts[mode]
        actions_by_rep = action_artifacts[mode]
        if len(metrics_by_rep) != 3 or len(actions_by_rep) != 3:
            raise ValueError("P1 500-stage adjudication requires exactly three replicates per branch")
        formal_ids = [artifact.get("replicate_id") for artifact in metrics_by_rep]
        action_ids = [artifact.get("replicate_id") for artifact in actions_by_rep]
        if any(not isinstance(value, str) for value in (*formal_ids, *action_ids)):
            raise TypeError("P1 500-stage replicate IDs must be strings")
        if len(set(formal_ids)) != 3 or len(set(action_ids)) != 3 or set(formal_ids) != set(action_ids):
            raise P1PostBlocked("P1 500-stage formal/N3 replicate IDs must align exactly")
        if set(formal_ids) != n3_replicate_ids:
            raise P1PostBlocked("P1 500-stage replicate IDs do not match the sealed N3 contract")
        formal_by_id = {artifact["replicate_id"]: artifact for artifact in metrics_by_rep}
        action_by_id = {artifact["replicate_id"]: artifact for artifact in actions_by_rep}
        records: list[Mapping[str, Any]] = []
        for replicate_index, replicate_id in enumerate(sorted(formal_ids)):
            artifact = formal_by_id[replicate_id]
            required = ("metrics_path", "selection_path", "metrics_sha256", "selection_sha256", "replicate_id")
            if any(key in artifact for key in ("episodes", "metrics", "selection")) and not set(required).issubset(artifact):
                raise P1PostBlocked("raw formal records are forbidden; provide sealed evaluator-v2 paths")
            if any(key not in artifact for key in required):
                raise ValueError("P1 500-stage formal path mapping lacks metrics/selection/hash/replicate_id")
            loaded = p1.load_formal_replicate_artifact(
                Path(artifact["metrics_path"]),
                Path(artifact["selection_path"]),
                metrics_sha256=artifact["metrics_sha256"],
                selection_sha256=artifact["selection_sha256"],
                branch=branch_identities[mode],
                replicate_id=replicate_id,
                expected_mode=mode,
                expected_experience=expected_experience,
            )
            records.extend(dict(record, replicate_index=replicate_index) for record in loaded["episodes"])
        formal_records[mode] = records
        nrmse_values = []
        for replicate_id in sorted(action_ids):
            artifact = action_by_id[replicate_id]
            required = ("path", "sha256", "replicate_id")
            if any(key in artifact for key in ("actions", "teacher_action", "active_identity")) and "path" not in artifact:
                raise P1PostBlocked("raw N3 action records are forbidden; provide a sealed action path")
            if any(key not in artifact for key in required):
                raise ValueError("P1 500-stage N3 path mapping lacks path/sha256/replicate_id")
            loaded_action = p1.load_n3_action_artifact(
                Path(artifact["path"]),
                expected_sha256=artifact["sha256"],
                branch=branch_identities[mode],
                n3_contract=plan.n3_contract,
                replicate_id=replicate_id,
                expected_experience=expected_experience,
            )
            if loaded_action["branch"] != mode or loaded_action["active_frame_count"] != EXPECTED_ACTIVE_FRAME_COUNT:
                raise RuntimeError("P1 500-stage N3 action branch/active-frame identity drifted")
            stats = p1.n3_open_loop_nrmse(
                loaded_action["actions"],
                loaded_action["teacher_action"],
                branch_identity={
                    "mode": mode,
                    "checkpoint": loaded_action["checkpoint"],
                    "config": loaded_action["config"],
                },
                n3_identity={
                    "phase_manifest": loaded_action["n3_phase_manifest"],
                    "h5": loaded_action["n3_h5"],
                },
            )
            if stats.get("n3_phase_manifest_sha256") != expected_phase_sha:
                raise RuntimeError("P1 500-stage NRMSE is not bound to the exact phase manifest")
            if stats.get("count") != EXPECTED_ACTIVE_FRAME_COUNT:
                raise RuntimeError("P1 500-stage NRMSE must use exactly active rows")
            nrmse_values.append(stats["nrmse_median_12d"])
        ordered = sorted(nrmse_values)
        middle = len(ordered) // 2
        median = ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2.0
        nrmse[mode] = {
            "schema": "a2_cb2h_pro_p1_open_loop_nrmse_v1",
            "n3_phase_manifest_sha256": expected_phase_sha,
            "nrmse_median_12d": float(median),
            "replicate_values": nrmse_values,
        }
    return p1._adjudicate_p1(
        sequential_nrmse=nrmse["sequential"],
        packed_nrmse=nrmse["packed"],
        sequential_formal=formal_records["sequential"],
        packed_formal=formal_records["packed"],
    )


def _adjudicate_post_paths(
    plan: PostPlan,
    formal_artifacts: Mapping[str, Sequence[Mapping[str, Any]]],
    action_artifacts: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    if plan.stage == POST_STAGE_200:
        return p1.adjudicate_p1_from_paths(
            branch_roots={mode: plan.pair_root / mode for mode in POST_BRANCHES},
            branch_manifest_shas=plan.branch_manifest_shas,
            n3_root=plan.n3_root,
            n3_phase_manifest_sha256=plan.n3_phase_manifest_sha256,
            formal_artifacts=formal_artifacts,
            action_artifacts=action_artifacts,
        )
    return _adjudicate_stage500_from_paths(plan, formal_artifacts, action_artifacts)


def execute_post_plan(plan: PostPlan) -> dict[str, Any]:
    """Run N3 then formal serially and atomically seal the final decision."""
    output_root = _validate_post_output_root(plan.output_root)
    output_root.parent.mkdir(parents=True, exist_ok=True)
    output_root.mkdir()
    try:
        telemetry_by_run: dict[tuple[str, str, str], Mapping[str, Any]] = {}
        for run in plan.n3_runs:
            telemetry_by_run[_run_key(run)] = _run_one(run, build_gpu7_environment())
        for run in plan.formal_runs:
            telemetry_by_run[_run_key(run)] = _run_one(run, build_gpu7_environment())
        final_plan = _reload_stage500_plan_inputs(plan)
        gpu_telemetry = _ordered_telemetry_refs(final_plan, telemetry_by_run)
        action_refs, formal_refs = _run_refs(final_plan)
        adjudication = _adjudicate_post_paths(final_plan, formal_refs, action_refs)
        decision = _decision(adjudication, final_plan.stage)
        formal_report = _formal_report(final_plan, formal_refs)
        runs = {
            "n3": [
                run.as_dict(
                    artifact_refs=[_artifact_ref(run.artifact_paths[0], output_root)],
                    telemetry_ref=telemetry_by_run[_run_key(run)],
                )
                for run in final_plan.n3_runs
            ],
            "formal": [
                run.as_dict(
                    artifact_refs=[
                        _artifact_ref(run.artifact_paths[0], output_root),
                        _artifact_ref(run.artifact_paths[1], output_root),
                    ],
                    telemetry_ref=telemetry_by_run[_run_key(run)],
                )
                for run in final_plan.formal_runs
            ],
        }
        manifest = {
            "schema": POST_SCHEMA,
            "operation": final_plan.stage.operation,
            "post_stage": {
                "stage_id": final_plan.stage.stage_id,
                "requested_iterations": final_plan.stage.requested_iterations,
                "completed_iterations": final_plan.stage.requested_iterations,
                "total_completed_iterations": final_plan.stage.requested_iterations,
                "additional_iterations": final_plan.stage.additional_iterations,
                "run_iterations": final_plan.stage.additional_iterations,
                "source_global_step": final_plan.stage.source_global_step,
                "target_global_step": final_plan.stage.target_global_step,
                "terminal": final_plan.stage == POST_STAGE_500,
            },
            "pair_root": str(final_plan.pair_root),
            "output_root": str(output_root),
            "branch_inputs": _branch_input_refs(final_plan),
            "n3_input": {
                "root": str(final_plan.n3_root),
                "phase_manifest": final_plan.n3_contract["phase_manifest"],
                "phase_manifest_sha256": final_plan.n3_phase_manifest_sha256,
                "replicates": final_plan.n3_contract["replicates"],
            },
            "gpu_identity": {
                "physical_gpu_index": p1.EXPECTED_GPU_INDEX,
                "logical_gpu_index": int(p1.EXPECTED_LOGICAL_GPU_INDEX),
                "logical_device": p1.EXPECTED_LOGICAL_DEVICE,
                "uuid": p1.EXPECTED_GPU_UUID,
                "world_size": 1,
                "binding_mode": p1.EXPECTED_GPU_BINDING_MODE,
            },
            "runtime": {"commit": p1.EXPECTED_RUNTIME_COMMIT},
            "runs": runs,
            "artifact_inputs": {"n3": action_refs, "formal": formal_refs, "gpu_telemetry": gpu_telemetry},
            "gpu_telemetry": gpu_telemetry,
            "adjudication": adjudication,
            "status": adjudication["status"],
            "report": {
                "n3_nrmse": adjudication["open_loop_nrmse"],
                "formal": {
                    "per_replicate": formal_report["per_replicate"],
                    "paired_deltas": formal_report["paired_deltas"],
                    "pooled": adjudication["formal_outcomes"],
                },
            },
            "decision_gate": decision,
            "decision": decision["decision"],
            "policy_quality_evidence": {
                "packed_goal_count": decision["packed_goal_count"],
                "policy_quality_pass": decision["policy_quality_pass"],
                "zero_goals_is_not_policy_quality_pass": decision["zero_goals_is_not_policy_quality_pass"],
            },
            "extension_policy": {
                "automatic_extension": False,
                "if_extended": "both_branches_only" if final_plan.stage == POST_STAGE_200 else None,
                "one_branch_extension_forbidden": True,
                "stage500_never_requests_another_extension": final_plan.stage == POST_STAGE_500,
            },
        }
        sealed = p1.seal_json(output_root / FINAL_MANIFEST_FILENAME, manifest)
        return sealed
    except BaseException as error:
        _write_failure(output_root, error, operation=plan.stage.operation)
        raise


def print_plan(plan: PostPlan) -> None:
    print(f"[A2_CB2H_P1_POST_DRY_RUN] n3_runs={len(plan.n3_runs)} formal_runs={len(plan.formal_runs)}", flush=True)
    for run in plan.all_runs:
        print(
            f"[A2_CB2H_P1_POST_COMMAND] operation={run.operation} mode={run.mode} "
            f"replicate={run.replicate_id} output={run.output_root} "
            f"command_sha256={run.command_sha256}",
            flush=True,
        )
        print(" ".join(run.command), flush=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pair-root", type=Path, default=PAIR_ROOT)
    parser.add_argument("--sequential-manifest-sha256", default=SEQUENTIAL_MANIFEST_SHA256)
    parser.add_argument("--packed-manifest-sha256", default=PACKED_MANIFEST_SHA256)
    parser.add_argument("--n3-root", type=Path, default=p1.N3_INPUT_ROOT)
    parser.add_argument("--n3-phase-manifest-sha256", default=p1.N3_PHASE_MANIFEST_SHA256)
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
    plan = build_post_plan(
        args.pair_root,
        sequential_manifest_sha256=args.sequential_manifest_sha256,
        packed_manifest_sha256=args.packed_manifest_sha256,
        output_root=args.output_root,
        n3_root=args.n3_root,
        n3_phase_manifest_sha256=args.n3_phase_manifest_sha256,
    )
    if args.dry_run:
        print_plan(plan)
        return 0
    result = execute_post_plan(plan)
    print(
        f"[A2_CB2H_P1_POST_{result['decision']}] decision={result['decision']} "
        f"manifest={args.output_root.expanduser().resolve() / FINAL_MANIFEST_FILENAME}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
