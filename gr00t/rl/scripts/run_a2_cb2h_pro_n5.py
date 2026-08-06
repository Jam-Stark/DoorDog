#!/usr/bin/env python3
"""C-B2H N5 packed D435 SyncBN recalibration and open-loop comparison.

This command is intentionally offline.  It consumes the sealed N3 Teacher
trajectories and N4 sequential baseline, performs one packed D435 encoder
forward per non-empty active 16-env step slice, and writes a new checkpoint
whose only permitted changes are D435 ``SyncBatchNorm`` running buffers.  No
head/fusion/recurrent/MLP path, backward pass, optimizer, or IsaacSim step is
used by calibration.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import copy
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gr00t.rl.scripts import run_a2_cb2h_pro_n4 as n4
from gr00t.rl.scripts import run_a2_student_eval_v19 as eval_v19


CHECKPOINT = n4.CHECKPOINT
CHECKPOINT_CONFIG = n4.CHECKPOINT_CONFIG
CHECKPOINT_SHA256 = n4.CHECKPOINT_SHA256
CHECKPOINT_CONFIG_SHA256 = n4.CHECKPOINT_CONFIG_SHA256
N3_INPUT_ROOT = n4.N3_INPUT_ROOT
N4_BASELINE_ROOT = (
    REPO_ROOT / "logs_eval/cb2h_pro_n4_view_diagnostic_step10000_gpu7-retry1-20260802"
).resolve()
EXPECTED_N4_ROOT_NAME = N4_BASELINE_ROOT.name
EXPECTED_N4_MANIFEST_SHA256 = "eb79410fa08adaec045d4bc8b6e5929c9966f8376caa0802a878ec6337c95b83"
EXPECTED_N4_METRICS_SHA256 = "94ea42565733d3102536e229ef9839c57e090548c6062a2a5500a50879efc038"
EXPECTED_N4_ACTIVE_FRAMES_SHA256 = "13a07b8eaec1143fa12994092f891d208d5c9baa25b2f4c0d1f58c3f12ac7c68"
EXPECTED_LOGICAL_DEVICE = n4.EXPECTED_LOGICAL_DEVICE
EXPECTED_GPU_INDEX = n4.EXPECTED_GPU_INDEX
EXPECTED_GPU_UUID = n4.EXPECTED_GPU_UUID
EXPECTED_ACTIVE_FRAMES = 30618
EXPECTED_PACKED_SAMPLES = EXPECTED_ACTIVE_FRAMES * 2
EXPECTED_N3_STEPS = 716
EXPECTED_N3_REPLICATES = 3
EXPECTED_PACKED_FORWARD_CALLS = EXPECTED_N3_STEPS * EXPECTED_N3_REPLICATES
N5_OUTPUT_ROOT = (
    REPO_ROOT / "logs_rl/cb2h_pro_n5_packed_bn_recalibrated_step10000_gpu7-20260803"
).resolve()
N5_METRICS_FILENAME = "n5_metrics.json"
N5_ACTIVE_FRAMES_FILENAME = "n5_active_frames.npz"
N5_CHECKPOINT_FILENAME = "model_step_010000.pt"
N5_CONFIG_FILENAME = "config.yaml"
N5_MANIFEST_FILENAME = "n5_provenance_manifest.json"
N4_METRICS_FILENAME = "n4_metrics.json"
N4_ACTIVE_FRAMES_FILENAME = "n4_active_frames.npz"
N4_MANIFEST_FILENAME = "n4_provenance_manifest.json"
N5_SCHEMA = "a2_cb2h_n5_packed_bn_recalibration_v1"
ALLOWED_BN_SUFFIXES = ("running_mean", "running_var", "num_batches_tracked")


EXPECTED_GPU_IDENTITY = {
    "physical_gpu_index": EXPECTED_GPU_INDEX,
    "logical_device": EXPECTED_LOGICAL_DEVICE,
    "uuid": EXPECTED_GPU_UUID,
    "cuda_visible_devices": EXPECTED_GPU_INDEX,
    "training_performed": False,
    "backward_call_count": 0,
    "optimizer_step_count": 0,
}


@dataclass(frozen=True)
class N4Baseline:
    root: Path
    manifest_path: Path
    manifest_sha256: str
    metrics_path: Path
    metrics_sha256: str
    active_frames_path: Path
    active_frames_sha256: str
    manifest: Mapping[str, Any]
    metrics: Mapping[str, Any]


@dataclass(frozen=True)
class CalibrationSummary:
    forward_call_count: int
    active_frame_count: int
    packed_sample_count: int
    per_replicate: tuple[Mapping[str, Any], ...]
    bn_state_deltas: Mapping[str, int]
    changed_running_stat_keys: tuple[str, ...]
    allowed_policy_state_keys: tuple[str, ...]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.expanduser().resolve(strict=True).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    with path.expanduser().resolve(strict=True).open(encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise TypeError(f"JSON artifact must be an object: {path}")
    return value


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _require_sha(value: Any, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(f"{name} must be a 64-character SHA256 string")
    int(value, 16)
    return value


def validate_gpu_identity(identity: Mapping[str, Any]) -> dict[str, Any]:
    """Require the exact GPU7/logical-cuda0, training-free provenance contract."""
    if not isinstance(identity, Mapping):
        raise TypeError("N5 GPU identity must be a mapping")
    for key, expected in EXPECTED_GPU_IDENTITY.items():
        if identity.get(key) != expected:
            raise RuntimeError(
                f"N5 GPU identity drift for {key}: expected={expected!r} "
                f"got={identity.get(key)!r}"
            )
    return dict(identity)


def _path_from_output(root: Path, output: Mapping[str, Any], name: str) -> Path:
    if not isinstance(output, Mapping):
        raise RuntimeError(f"N4 manifest outputs.{name} must be a mapping")
    declared = Path(str(output.get("path", ""))).expanduser().resolve()
    expected = (root / declared.name).resolve()
    if declared != expected:
        raise RuntimeError(f"N4 manifest outputs.{name} path is not rooted at the baseline")
    if not declared.is_file():
        raise FileNotFoundError(f"N4 baseline output is unavailable: {declared}")
    declared_sha = _require_sha(output.get("sha256"), f"N4 outputs.{name}.sha256")
    actual_sha = sha256_file(declared)
    if actual_sha != declared_sha:
        raise RuntimeError(f"N4 baseline outputs.{name} SHA256 drifted")
    return declared


def validate_n4_baseline(root: Path = N4_BASELINE_ROOT) -> N4Baseline:
    """Validate the exact sealed N4 sequential baseline and compact frames."""
    root = root.expanduser().resolve(strict=True)
    if root.name != EXPECTED_N4_ROOT_NAME:
        raise RuntimeError(f"N5 requires the exact sealed N4 root name; got {root.name!r}")
    manifest_path = root / N4_MANIFEST_FILENAME
    metrics_path = root / N4_METRICS_FILENAME
    active_frames_path = root / N4_ACTIVE_FRAMES_FILENAME
    manifest = _load_json(manifest_path)
    metrics = _load_json(metrics_path)
    if sha256_file(manifest_path) != EXPECTED_N4_MANIFEST_SHA256:
        raise RuntimeError("N4 baseline manifest SHA256 drifted")
    if sha256_file(metrics_path) != EXPECTED_N4_METRICS_SHA256:
        raise RuntimeError("N4 baseline metrics SHA256 drifted")
    if sha256_file(active_frames_path) != EXPECTED_N4_ACTIVE_FRAMES_SHA256:
        raise RuntimeError("N4 baseline active-frame SHA256 drifted")
    if manifest.get("schema") != "a2_cb2h_n4_view_diagnostic_manifest_v1":
        raise RuntimeError("N4 baseline manifest schema drifted")
    if manifest.get("operation") != "n4" or manifest.get("training_performed") is not False:
        raise RuntimeError("N4 baseline is not the training-free N4 diagnostic")
    if manifest.get("backward_call_count") != 0 or manifest.get("optimizer_step_count") != 0:
        raise RuntimeError("N4 baseline reports forbidden training calls")
    if metrics.get("schema") != "a2_cb2h_n4_metrics_v1" or metrics.get("operation") != "n4":
        raise RuntimeError("N4 baseline metrics schema/operation drifted")
    if metrics.get("training_performed") is not False:
        raise RuntimeError("N4 baseline metrics report training")
    if metrics.get("backward_call_count") != 0 or metrics.get("optimizer_step_count") != 0:
        raise RuntimeError("N4 baseline metrics report forbidden training calls")
    config = manifest.get("config")
    if not isinstance(config, Mapping):
        raise RuntimeError("N4 baseline manifest is missing config provenance")
    if config.get("path") != str(CHECKPOINT_CONFIG) or config.get("sha256") != CHECKPOINT_CONFIG_SHA256:
        raise RuntimeError("N4 baseline config identity drifted")
    if config.get("d435i_forward_mode") != "sequential":
        raise RuntimeError("N4 baseline must identify sequential D435 mode")
    checkpoint = manifest.get("checkpoint")
    if not isinstance(checkpoint, Mapping):
        raise RuntimeError("N4 baseline manifest is missing checkpoint provenance")
    expected_checkpoint = {
        "path": str(CHECKPOINT),
        "sha256": CHECKPOINT_SHA256,
        "config_path": str(CHECKPOINT_CONFIG),
        "config_sha256": CHECKPOINT_CONFIG_SHA256,
        "global_step": 10000,
        "controller": "student",
    }
    for key, expected in expected_checkpoint.items():
        if checkpoint.get(key) != expected:
            raise RuntimeError(f"N4 baseline checkpoint identity drifted for {key}")
    n3_input = manifest.get("n3_input")
    if not isinstance(n3_input, Mapping) or n3_input.get("root") != str(N3_INPUT_ROOT):
        raise RuntimeError("N4 baseline N3 input root identity drifted")
    n3_inputs = n4.validate_n3_inputs(N3_INPUT_ROOT)
    if n3_input.get("phase_manifest_sha256") != n3_inputs.phase_manifest_sha256:
        raise RuntimeError("N4 baseline N3 phase manifest hash drifted")
    declared_outputs = manifest.get("outputs")
    if not isinstance(declared_outputs, Mapping):
        raise RuntimeError("N4 baseline manifest is missing outputs")
    declared_metrics = _path_from_output(root, declared_outputs.get("metrics"), "metrics")
    declared_frames = _path_from_output(root, declared_outputs.get("active_frames"), "active_frames")
    if declared_metrics != metrics_path.resolve() or declared_frames != active_frames_path.resolve():
        raise RuntimeError("N4 baseline output filenames drifted")
    if sha256_file(metrics_path) != sha256_file(declared_metrics):
        raise RuntimeError("N4 baseline metrics artifact identity drifted")
    import numpy as np

    with np.load(active_frames_path, allow_pickle=False) as data:
        required = {
            "replicate_index",
            "env_id",
            "frame_id",
            "pre_action_stage",
            "case_id",
            "active_mask",
            "teacher_action",
            "actions",
            "transition_window_pm5_active",
        }
        if not required.issubset(set(data.files)):
            raise RuntimeError("N4 active-frame artifact is missing required arrays")
        count = int(data["active_mask"].shape[0])
        if count != EXPECTED_ACTIVE_FRAMES:
            raise RuntimeError(f"N4 active-frame count drifted: expected {EXPECTED_ACTIVE_FRAMES}, got {count}")
        if tuple(data["teacher_action"].shape) != (count, 12):
            raise RuntimeError("N4 teacher_action shape drifted")
        if tuple(data["actions"].shape) != (count, len(n4.VARIANTS), 12):
            raise RuntimeError("N4 action variant shape drifted")
    return N4Baseline(
        root=root,
        manifest_path=manifest_path,
        manifest_sha256=sha256_file(manifest_path),
        metrics_path=metrics_path,
        metrics_sha256=sha256_file(metrics_path),
        active_frames_path=active_frames_path,
        active_frames_sha256=sha256_file(active_frames_path),
        manifest=manifest,
        metrics=metrics,
    )


def _allowed_d435_bn_state_keys(state: Mapping[str, Any]) -> tuple[str, ...]:
    keys = tuple(
        sorted(
            key
            for key in state
            if key.startswith("d435i_vision_module.")
            and key.rsplit(".", 1)[-1] in ALLOWED_BN_SUFFIXES
        )
    )
    if not keys:
        raise RuntimeError("N5 checkpoint has no D435 SyncBatchNorm running-state keys")
    return keys


def _tensor_equal(left: Any, right: Any) -> bool:
    import torch

    if torch.is_tensor(left) or torch.is_tensor(right):
        return torch.is_tensor(left) and torch.is_tensor(right) and torch.equal(left, right)
    return left == right


def _payload_equal(left: Any, right: Any) -> bool:
    import torch

    if torch.is_tensor(left) or torch.is_tensor(right):
        return torch.is_tensor(left) and torch.is_tensor(right) and torch.equal(left, right)
    if isinstance(left, Mapping) or isinstance(right, Mapping):
        if not isinstance(left, Mapping) or not isinstance(right, Mapping) or set(left) != set(right):
            return False
        return all(_payload_equal(left[key], right[key]) for key in left)
    if isinstance(left, (list, tuple)) or isinstance(right, (list, tuple)):
        if not isinstance(left, type(right)) or len(left) != len(right):
            return False
        return all(_payload_equal(a, b) for a, b in zip(left, right))
    return left == right


def configure_bn_calibration(model: Any) -> tuple[Any, tuple[str, ...]]:
    """Freeze all parameters; train only D435 SyncBN children for calibration."""
    import torch

    if not hasattr(model, "d435i_vision_module"):
        raise RuntimeError("N5 model is missing d435i_vision_module")
    model.eval()
    for parameter in model.parameters():
        parameter.requires_grad_(False)
        if parameter.grad is not None:
            raise RuntimeError("N5 model entered calibration with a non-empty parameter gradient")
    d435 = model.d435i_vision_module
    batch_norms = [module for module in d435.modules() if isinstance(module, torch.nn.SyncBatchNorm)]
    if not batch_norms:
        raise RuntimeError("N5 D435 encoder has no SyncBatchNorm modules to recalibrate")
    for module in model.modules():
        module.eval()
    for module in batch_norms:
        module.train()
    state = model.state_dict()
    allowed = _allowed_d435_bn_state_keys(state)
    actual_allowed = {
        name
        for name, module in d435.named_modules()
        if isinstance(module, torch.nn.SyncBatchNorm)
        for name in (
            f"d435i_vision_module.{name}.running_mean" if name else "d435i_vision_module.running_mean",
            f"d435i_vision_module.{name}.running_var" if name else "d435i_vision_module.running_var",
            f"d435i_vision_module.{name}.num_batches_tracked" if name else "d435i_vision_module.num_batches_tracked",
        )
    }
    if not actual_allowed.issubset(set(allowed)):
        raise RuntimeError("N5 D435 SyncBatchNorm state keys are not represented in policy_state_dict")
    return d435, allowed


def _packed_active_input(raw: Mapping[str, Any], device: str):
    import torch
    from gr00t.rl.utils.a2_policy_camera import compose_channel_stacked_dual_rgb

    if not all(key in raw for key in ("left_rgb", "right_rgb", "head_rgb", "camera_meta", "active_mask")):
        raise KeyError("N5 calibration step is missing camera or active-mask fields")
    def as_tensor(value):
        return value if torch.is_tensor(value) else torch.from_numpy(value)

    active = as_tensor(raw["active_mask"]).to(dtype=torch.bool)
    if tuple(active.shape) != (n4.EXPECTED_ENV_COUNT,):
        raise ValueError("N5 active_mask step must be [16]")
    if not bool(active.any().item()):
        return None, 0
    left, right, _, _ = n4.transform_variant(
        as_tensor(raw["left_rgb"]),
        as_tensor(raw["right_rgb"]),
        as_tensor(raw["head_rgb"]),
        as_tensor(raw["camera_meta"]),
        "FULL",
    )
    dual = compose_channel_stacked_dual_rgb(
        left.to(device),
        right.to(device),
        resolution=(384, 216),
        image_mean=n4.IMAGE_MEAN,
        image_std=n4.IMAGE_STD,
    )
    dual = dual[active.to(device)]
    left_tensor = dual[..., :3].permute(0, 3, 1, 2).contiguous()
    right_tensor = dual[..., 3:6].permute(0, 3, 1, 2).contiguous()
    count = int(left_tensor.shape[0])
    packed = torch.cat((left_tensor, right_tensor), dim=0)
    if tuple(packed.shape) != (2 * count, 3, 384, 216):
        raise RuntimeError(f"N5 packed D435 input shape drifted: {tuple(packed.shape)}")
    return packed, count


def calibrate_d435_bn(model: Any, inputs: n4.N3Inputs, device: str = EXPECTED_LOGICAL_DEVICE) -> CalibrationSummary:
    """Run the exact active-only packed calibration pass over all N3 rows."""
    import torch

    _, allowed = configure_bn_calibration(model)
    before = {key: model.state_dict()[key].detach().clone() for key in allowed}
    forward_call_count = 0
    active_frame_count = 0
    packed_sample_count = 0
    per_replicate: list[Mapping[str, Any]] = []
    encoder = model.d435i_vision_module
    for replicate in inputs.replicates:
        replicate_calls = 0
        replicate_active = 0
        with n4._open_h5(replicate.h5_path) as handle:
            for offset in range(0, replicate.row_count, n4.EXPECTED_ENV_COUNT):
                raw = n4._read_step(handle, offset)
                packed, count = _packed_active_input(raw, device)
                if packed is None:
                    continue
                with torch.no_grad():
                    encoded = encoder(packed)
                if not torch.is_tensor(encoded) or tuple(encoded.shape) != (2 * count, 128):
                    raise RuntimeError(
                        "N5 packed D435 encoder output must be [2M,128]; "
                        f"got {getattr(encoded, 'shape', None)}"
                    )
                if not bool(torch.all(torch.isfinite(encoded)).item()):
                    raise RuntimeError("N5 packed D435 encoder output contains non-finite values")
                forward_call_count += 1
                replicate_calls += 1
                active_frame_count += count
                replicate_active += count
                packed_sample_count += 2 * count
        per_replicate.append(
            {
                "replicate_id": replicate.replicate_id,
                "forward_call_count": replicate_calls,
                "active_frame_count": replicate_active,
                "packed_sample_count": replicate_active * 2,
            }
        )
    after = model.state_dict()
    changed_running_stats = tuple(
        sorted(key for key in allowed if not _tensor_equal(before[key], after[key]))
    )
    if not any(key.endswith(("running_mean", "running_var")) for key in changed_running_stats):
        raise RuntimeError("N5 calibration did not change any D435 SyncBatchNorm running mean/variance")
    deltas: dict[str, int] = {}
    for key in allowed:
        if key.endswith("num_batches_tracked"):
            deltas[key] = int(after[key].item()) - int(before[key].item())
            if deltas[key] != forward_call_count:
                raise RuntimeError(
                    f"N5 SyncBatchNorm count drift for {key}: expected {forward_call_count}, got {deltas[key]}"
                )
    expected_active = sum(rep.active_frame_count for rep in inputs.replicates)
    if active_frame_count != expected_active or packed_sample_count != 2 * expected_active:
        raise RuntimeError(
            "N5 active-frame accounting drifted: "
            f"expected={expected_active} packed={2 * expected_active} "
            f"got={active_frame_count}/{packed_sample_count}"
        )
    expected_calls = sum(
        (rep.row_count + n4.EXPECTED_ENV_COUNT - 1) // n4.EXPECTED_ENV_COUNT
        for rep in inputs.replicates
    )
    if forward_call_count != expected_calls:
        raise RuntimeError(
            f"N5 packed calibration must call once per non-empty step slice: expected {expected_calls}, got {forward_call_count}"
        )
    return CalibrationSummary(
        forward_call_count=forward_call_count,
        active_frame_count=active_frame_count,
        packed_sample_count=packed_sample_count,
        per_replicate=tuple(per_replicate),
        bn_state_deltas=deltas,
        changed_running_stat_keys=changed_running_stats,
        allowed_policy_state_keys=allowed,
    )


def _read_replicate_raw(replicate: n4.N3Replicate):
    import numpy as np

    parts: dict[str, list[Any]] = {
        "teacher_action": [],
        "active_mask": [],
        "env_id": [],
        "frame_id": [],
        "case_id": [],
        "pre_action_stage": [],
    }
    with n4._open_h5(replicate.h5_path) as handle:
        for offset in range(0, replicate.row_count, n4.EXPECTED_ENV_COUNT):
            for key in parts:
                parts[key].append(handle[key][offset : offset + n4.EXPECTED_ENV_COUNT])
    return {key: np.concatenate(value, axis=0) for key, value in parts.items()}


def _evaluate_open_loop(model: Any, inputs: n4.N3Inputs, device: str):
    import numpy as np

    raw_replicates = []
    action_replicates = []
    for replicate in inputs.replicates:
        raw = _read_replicate_raw(replicate)
        result = n4.evaluate_variant(model, replicate, "FULL", device)
        if tuple(result.actions.shape) != (replicate.row_count, n4.EXPECTED_ACTION_DIM):
            raise RuntimeError("N5 open-loop action row shape drifted")
        raw_replicates.append(raw)
        action_replicates.append(result.actions)
    active = [raw["active_mask"].astype(bool) for raw in raw_replicates]
    return raw_replicates, action_replicates, [np.flatnonzero(mask) for mask in active]


def _aggregate_open_loop(raw: Mapping[str, Any], actions: Any) -> dict[str, Any]:
    import numpy as np

    active = raw["active_mask"].astype(bool)
    stage = raw["pre_action_stage"].astype(np.int64)
    transition = n4.build_transition_window_mask(active, raw["env_id"], stage, radius=5)
    metrics = n4._grouped_metric_stats(
        np.asarray(actions), raw["teacher_action"].astype(np.float32), active, stage, transition
    )
    metrics["active_frame_count"] = int(active.sum())
    return metrics


def _save_recalibrated_checkpoint(
    source_checkpoint: Path,
    destination: Path,
    model: Any,
    allowed_keys: Sequence[str],
) -> dict[str, Any]:
    import torch

    source_payload = torch.load(source_checkpoint.expanduser().resolve(strict=True), map_location="cpu", weights_only=False)
    if not isinstance(source_payload, Mapping) or not isinstance(source_payload.get("policy_state_dict"), Mapping):
        raise RuntimeError("N5 source checkpoint must contain a policy_state_dict mapping")
    before_state = source_payload["policy_state_dict"]
    model_state = model.state_dict()
    allowed = set(allowed_keys)
    if not allowed.issubset(set(before_state)):
        raise RuntimeError("N5 allowed BN keys are missing from the source checkpoint")
    output_payload = copy.deepcopy(source_payload)
    output_policy = dict(output_payload["policy_state_dict"])
    changed_keys = []
    for key in sorted(allowed):
        updated = model_state[key].detach().cpu().clone()
        if not _tensor_equal(before_state[key], updated):
            changed_keys.append(key)
        output_policy[key] = updated
    output_payload["policy_state_dict"] = output_policy
    destination.parent.mkdir(parents=True, exist_ok=True)
    torch.save(output_payload, destination)
    loaded = torch.load(destination, map_location="cpu", weights_only=False)
    if not isinstance(loaded, Mapping) or set(loaded) != set(source_payload):
        raise RuntimeError("N5 output checkpoint top-level fields drifted")
    for key in source_payload:
        if key == "policy_state_dict":
            continue
        if not _payload_equal(source_payload[key], loaded[key]):
            raise RuntimeError(f"N5 output checkpoint field changed unexpectedly: {key}")
    loaded_policy = loaded.get("policy_state_dict")
    if not isinstance(loaded_policy, Mapping) or set(loaded_policy) != set(before_state):
        raise RuntimeError("N5 output policy_state_dict keys drifted")
    for key in before_state:
        if key not in allowed and not _tensor_equal(before_state[key], loaded_policy[key]):
            raise RuntimeError(f"N5 non-BN policy tensor changed unexpectedly: {key}")
    return {
        "source_sha256": sha256_file(source_checkpoint),
        "output_sha256": sha256_file(destination),
        "allowed_policy_state_keys": sorted(allowed),
        "changed_policy_state_keys": changed_keys,
    }


def _copy_exact_config(source: Path, destination: Path) -> dict[str, Any]:
    if destination.exists():
        raise FileExistsError(f"N5 refuses existing config destination: {destination}")
    shutil.copyfile(source, destination)
    source_sha = sha256_file(source)
    output_sha = sha256_file(destination)
    if source_sha != output_sha:
        raise RuntimeError("N5 output config is not byte-identical to the source config")
    return {"source_path": str(source), "path": str(destination), "sha256": output_sha}


def run_n5_recalibration(
    model: Any,
    inputs: n4.N3Inputs,
    n4_baseline: N4Baseline,
    source_checkpoint: Path,
    source_config: Path,
    output_root: Path = N5_OUTPUT_ROOT,
    *,
    device: str = EXPECTED_LOGICAL_DEVICE,
    gpu_identity: Mapping[str, Any] | None = None,
    checkpoint_info: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Calibrate, evaluate, and atomically publish the N5 checkpoint bundle.

    The final output root is published only by the last ``os.replace``.  Any
    exception before that point intentionally leaves the owned ``.writing``
    directory in place as failure evidence; a retry against the same output
    root is blocked until an independently authorized new root is chosen.
    """
    import numpy as np

    output_root = output_root.expanduser().resolve()
    staging = output_root.with_name(f".{output_root.name}.writing")
    if output_root.exists() or staging.exists():
        raise FileExistsError(f"N5 refuses existing output/staging roots: {output_root} {staging}")
    staging.mkdir(parents=True)
    gpu_identity = validate_gpu_identity(gpu_identity)
    source_checkpoint = source_checkpoint.expanduser().resolve(strict=True)
    source_config = source_config.expanduser().resolve(strict=True)
    if source_checkpoint != CHECKPOINT or source_config != CHECKPOINT_CONFIG:
        raise RuntimeError("N5 source checkpoint/config must be the exact sealed step10000 pair")
    if sha256_file(source_checkpoint) != CHECKPOINT_SHA256 or sha256_file(source_config) != CHECKPOINT_CONFIG_SHA256:
        raise RuntimeError("N5 source checkpoint/config SHA256 drifted")
    if n4_baseline.root != N4_BASELINE_ROOT:
        raise RuntimeError("N5 requires the exact sealed N4 baseline root")
    if len(inputs.replicates) != EXPECTED_N3_REPLICATES:
        raise RuntimeError("N5 requires exactly three N3 replicates")
    if getattr(model, "d435i_forward_mode", None) != "packed":
        raise RuntimeError("N5 model must be explicitly configured for packed D435 mode")
    import torch

    source_payload = torch.load(source_checkpoint, map_location="cpu", weights_only=False)
    if not isinstance(source_payload, Mapping) or not isinstance(source_payload.get("policy_state_dict"), Mapping):
        raise RuntimeError("N5 source checkpoint must contain a policy_state_dict mapping")
    model_state = model.state_dict()
    allowed_keys = _allowed_d435_bn_state_keys(source_payload["policy_state_dict"])
    for key in allowed_keys:
        if key not in model_state:
            raise RuntimeError(f"N5 model state is missing source checkpoint key {key}")
    # PRECAL runs with all BN layers in eval mode and packed mode; this path is
    # the open-loop evidence before any running-stat mutation.
    model.eval()
    for parameter in model.parameters():
        parameter.requires_grad_(False)
        if parameter.grad is not None:
            raise RuntimeError("N5 model entered PRECAL evaluation with a non-empty gradient")
    raw_replicates, pre_actions, active_indices = _evaluate_open_loop(model, inputs, device)
    calibration = calibrate_d435_bn(model, inputs, device)
    model.eval()
    _, post_actions, _ = _evaluate_open_loop(model, inputs, device)
    calibrated_state = model.state_dict()
    source_policy = source_payload["policy_state_dict"]
    for key, source_value in source_policy.items():
        if key not in set(calibration.allowed_policy_state_keys) and not _tensor_equal(
            source_value, calibrated_state[key].detach().cpu()
        ):
            raise RuntimeError(f"N5 calibration mutated a non-BN policy state key: {key}")

    output_checkpoint = staging / N5_CHECKPOINT_FILENAME
    checkpoint_delta = _save_recalibrated_checkpoint(
        source_checkpoint, output_checkpoint, model, calibration.allowed_policy_state_keys
    )
    output_config = staging / N5_CONFIG_FILENAME
    config_identity = _copy_exact_config(source_config, output_config)

    replicate_metrics = []
    pre_actions_parts = []
    post_actions_parts = []
    active_parts = []
    stage_parts = []
    teacher_parts = []
    transition_parts = []
    replicate_parts = []
    env_parts = []
    frame_parts = []
    case_parts = []
    with np.load(n4_baseline.active_frames_path, allow_pickle=False) as baseline_data:
        n4_actions = np.asarray(baseline_data["actions"][:, 0], dtype=np.float32)
        baseline_active = np.asarray(baseline_data["active_mask"], dtype=bool)
        baseline_case = np.asarray(baseline_data["case_id"])
        baseline_env = np.asarray(baseline_data["env_id"])
        baseline_frame = np.asarray(baseline_data["frame_id"])
        baseline_stage = np.asarray(baseline_data["pre_action_stage"])
        baseline_teacher = np.asarray(baseline_data["teacher_action"], dtype=np.float32)
        baseline_transition = np.asarray(baseline_data["transition_window_pm5_active"], dtype=bool)
    n4_cursor = 0
    for index, (raw, pre, post, active_idx) in enumerate(
        zip(raw_replicates, pre_actions, post_actions, active_indices)
    ):
        active = raw["active_mask"].astype(bool)
        stage = raw["pre_action_stage"].astype(np.int64)
        transition = n4.build_transition_window_mask(active, raw["env_id"], stage, radius=5)
        active_count = int(active.sum())
        baseline_slice = n4_actions[n4_cursor : n4_cursor + active_count]
        n4_cursor += active_count
        active_teacher = raw["teacher_action"][active].astype(np.float32)
        active_stage = stage[active]
        active_transition = transition[active]
        baseline_metrics = n4._grouped_metric_stats(
            baseline_slice,
            active_teacher,
            np.ones(active_count, dtype=bool),
            active_stage,
            active_transition,
        )
        baseline_metrics["active_frame_count"] = active_count
        replicate_metrics.append(
            {
                "replicate_id": inputs.replicates[index].replicate_id,
                "n4_sequential": baseline_metrics,
                "precal_packed": _aggregate_open_loop(raw, pre),
                "postcal_packed": _aggregate_open_loop(raw, post),
                "post_minus_pre_action_delta": n4.summarize_variant_deltas(
                    pre, post, active, stage=stage, transition_window=transition
                ),
            }
        )
        active_parts.append(active[active_idx])
        stage_parts.append(raw["pre_action_stage"][active_idx].astype(np.int16))
        teacher_parts.append(raw["teacher_action"][active_idx].astype(np.float32))
        transition_parts.append(transition[active_idx])
        replicate_parts.append(np.full(active_idx.size, index, dtype=np.int16))
        env_parts.append(raw["env_id"][active_idx].astype(np.int16))
        frame_parts.append(raw["frame_id"][active_idx].astype(np.int64))
        case_parts.append(raw["case_id"][active_idx].astype("S64"))
        pre_actions_parts.append(pre[active_idx].astype(np.float32))
        post_actions_parts.append(post[active_idx].astype(np.float32))
    # The N4 compact artifact is already ordered by replicate/active row; bind
    # its sequential baseline to the newly reconstructed N3 active ordering.
    aggregate_active = np.concatenate(active_parts).astype(bool)
    aggregate_pre = np.concatenate(pre_actions_parts)
    aggregate_post = np.concatenate(post_actions_parts)
    aggregate_teacher = np.concatenate(teacher_parts)
    aggregate_stage = np.concatenate(stage_parts).astype(np.int64)
    aggregate_transition = np.concatenate(transition_parts).astype(bool)
    aggregate_rep = np.concatenate(replicate_parts)
    aggregate_env = np.concatenate(env_parts)
    aggregate_frame = np.concatenate(frame_parts)
    aggregate_case = np.concatenate(case_parts)
    if not np.array_equal(aggregate_active, baseline_active) or not np.array_equal(aggregate_case, baseline_case):
        raise RuntimeError("N5 active-frame ordering/case identity does not match N4 baseline")
    if not np.array_equal(aggregate_env, baseline_env) or not np.array_equal(aggregate_frame, baseline_frame):
        raise RuntimeError("N5 active-frame env/frame identity does not match N4 baseline")
    if not np.array_equal(aggregate_stage, baseline_stage) or not np.array_equal(aggregate_teacher, baseline_teacher):
        raise RuntimeError("N5 active-frame stage/Teacher action identity does not match N4 baseline")
    if not np.array_equal(aggregate_transition, baseline_transition):
        raise RuntimeError("N5 transition-window identity does not match N4 baseline")
    aggregate_n4 = n4._grouped_metric_stats(
        n4_actions, aggregate_teacher, aggregate_active, aggregate_stage, aggregate_transition
    )
    aggregate_pre_metrics = n4._grouped_metric_stats(
        aggregate_pre, aggregate_teacher, aggregate_active, aggregate_stage, aggregate_transition
    )
    aggregate_post_metrics = n4._grouped_metric_stats(
        aggregate_post, aggregate_teacher, aggregate_active, aggregate_stage, aggregate_transition
    )
    aggregate_deltas = n4.summarize_variant_deltas(
        aggregate_pre,
        aggregate_post,
        aggregate_active,
        stage=aggregate_stage,
        transition_window=aggregate_transition,
    )
    if n4_cursor != n4_actions.shape[0]:
        raise RuntimeError("N5 N4 sequential baseline active-frame cursor drifted")
    metrics_payload = {
        "schema": "a2_cb2h_n5_metrics_v1",
        "operation": "n5",
        "d435i_forward_mode": "packed",
        "gpu_identity": dict(gpu_identity),
        "replicate_metrics": replicate_metrics,
        "aggregate_metrics": {
            "n4_sequential": aggregate_n4,
            "precal_packed": aggregate_pre_metrics,
            "postcal_packed": aggregate_post_metrics,
            "post_minus_pre_action_delta": aggregate_deltas,
            "active_frame_count": int(aggregate_active.sum()),
        },
        "calibration": {
            "forward_call_count": calibration.forward_call_count,
            "active_frame_count": calibration.active_frame_count,
            "packed_sample_count": calibration.packed_sample_count,
            "per_replicate": list(calibration.per_replicate),
            "bn_state_deltas": dict(calibration.bn_state_deltas),
            "changed_running_stat_keys": list(calibration.changed_running_stat_keys),
        },
        "training_performed": False,
        "calibration_performed": True,
        "backward_call_count": 0,
        "optimizer_step_count": 0,
        "policy_quality_evidence": False,
        "open_loop_action_evidence_only": True,
    }
    metrics_path = staging / N5_METRICS_FILENAME
    metrics_path.write_text(json.dumps(metrics_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    active_frames_path = staging / N5_ACTIVE_FRAMES_FILENAME
    np.savez_compressed(
        active_frames_path,
        replicate_index=aggregate_rep,
        env_id=aggregate_env,
        frame_id=aggregate_frame,
        pre_action_stage=aggregate_stage.astype(np.int16),
        case_id=aggregate_case,
        active_mask=aggregate_active,
        teacher_action=aggregate_teacher,
        n4_sequential_actions=n4_actions,
        precal_packed_actions=aggregate_pre,
        postcal_packed_actions=aggregate_post,
        transition_window_pm5_active=aggregate_transition,
    )
    manifest: dict[str, Any] = {
        "schema": N5_SCHEMA,
        "operation": "n5",
        "d435i_forward_mode": "packed",
        "gpu_identity": dict(gpu_identity),
        "source": {
            "n5_runner": {"path": str(Path(__file__).resolve()), "sha256": sha256_file(Path(__file__))},
            "n4_runner": {"path": str(Path(n4.__file__).resolve()), "sha256": sha256_file(Path(n4.__file__).resolve())},
            "actor": {"path": str(n4.TRIVIEW_ACTOR_SOURCE), "sha256": sha256_file(n4.TRIVIEW_ACTOR_SOURCE)},
        },
        "checkpoint_source": dict(checkpoint_info or {
            "path": str(source_checkpoint),
            "sha256": CHECKPOINT_SHA256,
            "config_path": str(source_config),
            "config_sha256": CHECKPOINT_CONFIG_SHA256,
            "global_step": 10000,
            "controller": "student",
        }),
        "checkpoint_output": {
            "path": str(output_root / output_checkpoint.name),
            "sha256": checkpoint_delta["output_sha256"],
            "allowed_policy_state_keys": checkpoint_delta["allowed_policy_state_keys"],
            "changed_policy_state_keys": checkpoint_delta["changed_policy_state_keys"],
            "non_bn_policy_state_unchanged": True,
            "top_level_fields_unchanged": True,
        },
        "config": {
            **config_identity,
            "path": str(output_root / output_config.name),
            "d435i_forward_mode": "packed",
        },
        "n3_input": {
            "root": str(inputs.root),
            "phase_manifest_path": str(inputs.phase_manifest_path),
            "phase_manifest_sha256": inputs.phase_manifest_sha256,
            "replicates": [
                {
                    "replicate_id": rep.replicate_id,
                    "h5_path": str(rep.h5_path),
                    "h5_sha256": rep.h5_sha256,
                    "active_frame_count": rep.active_frame_count,
                }
                for rep in inputs.replicates
            ],
        },
        "n4_baseline": {
            "root": str(n4_baseline.root),
            "manifest_path": str(n4_baseline.manifest_path),
            "manifest_sha256": n4_baseline.manifest_sha256,
            "metrics_path": str(n4_baseline.metrics_path),
            "metrics_sha256": n4_baseline.metrics_sha256,
            "active_frames_path": str(n4_baseline.active_frames_path),
            "active_frames_sha256": n4_baseline.active_frames_sha256,
            "d435i_forward_mode": "sequential",
        },
        "calibration": {
            "encoder": "d435i_vision_module",
            "batch_norm_type": "SyncBatchNorm",
            "forward_mode": "packed",
            "forward_call_count": calibration.forward_call_count,
            "active_frame_count": calibration.active_frame_count,
            "packed_sample_count": calibration.packed_sample_count,
            "expected_forward_call_count": EXPECTED_PACKED_FORWARD_CALLS,
            "expected_active_frame_count": EXPECTED_ACTIVE_FRAMES,
            "expected_packed_sample_count": EXPECTED_PACKED_SAMPLES,
            "head_fusion_lstm_mlp_calls": 0,
            "backward_call_count": 0,
            "optimizer_step_count": 0,
        },
        "outputs": {
            "metrics": {"path": str(output_root / metrics_path.name), "sha256": sha256_file(metrics_path)},
            "active_frames": {"path": str(output_root / active_frames_path.name), "sha256": sha256_file(active_frames_path)},
            "checkpoint": {"path": str(output_root / output_checkpoint.name), "sha256": checkpoint_delta["output_sha256"]},
            "config": {"path": str(output_root / output_config.name), "sha256": config_identity["sha256"]},
        },
        "training_performed": False,
        "calibration_performed": True,
        "backward_call_count": 0,
        "optimizer_step_count": 0,
        "sealed": True,
    }
    manifest["manifest_content_sha256"] = hashlib.sha256(_canonical_json(manifest).encode("utf-8")).hexdigest()
    manifest_path = staging / N5_MANIFEST_FILENAME
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(staging, output_root)
    manifest["manifest_file_sha256"] = sha256_file(output_root / N5_MANIFEST_FILENAME)
    return manifest


def parse_args(argv: Sequence[str] | None = None) -> Any:
    parser = __import__("argparse").ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=CHECKPOINT)
    parser.add_argument("--config", dest="config_path", type=Path, default=CHECKPOINT_CONFIG)
    parser.add_argument("--n3-root", type=Path, default=N3_INPUT_ROOT)
    parser.add_argument("--n4-root", type=Path, default=N4_BASELINE_ROOT)
    parser.add_argument("--output-root", type=Path, default=N5_OUTPUT_ROOT)
    parser.add_argument("--device", default=EXPECTED_LOGICAL_DEVICE)
    parser.add_argument("--expected-physical-gpu", default=EXPECTED_GPU_INDEX)
    parser.add_argument("--expected-gpu-uuid", default=EXPECTED_GPU_UUID)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.checkpoint.expanduser().resolve() != CHECKPOINT:
        raise RuntimeError("N5 source checkpoint is pinned to exact step10000 Student checkpoint")
    if args.config_path.expanduser().resolve() != CHECKPOINT_CONFIG:
        raise RuntimeError("N5 source config is pinned to exact step10000 Student config")
    gpu_identity = n4.validate_gpu_binding(args.device, args.expected_physical_gpu, args.expected_gpu_uuid)
    checkpoint_info = eval_v19.validate_checkpoint_artifacts(
        args.checkpoint,
        args.config_path,
        controller="student",
        expected_global_step=10000,
        expected_sha256=CHECKPOINT_SHA256,
        expected_config_sha256=CHECKPOINT_CONFIG_SHA256,
    )
    inputs = n4.validate_n3_inputs(args.n3_root)
    baseline = validate_n4_baseline(args.n4_root)
    model = n4._model_from_exact_checkpoint(args.checkpoint, args.config_path, args.device)
    model.d435i_forward_mode = "packed"
    manifest = run_n5_recalibration(
        model,
        inputs,
        baseline,
        args.checkpoint,
        args.config_path,
        args.output_root,
        device=args.device,
        gpu_identity=gpu_identity,
        checkpoint_info=checkpoint_info,
    )
    print(
        f"[A2_N5_PASS] mode=packed active_frames={manifest['calibration']['active_frame_count']} "
        f"packed_samples={manifest['calibration']['packed_sample_count']} "
        f"forward_calls={manifest['calibration']['forward_call_count']} output={args.output_root.resolve()}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
