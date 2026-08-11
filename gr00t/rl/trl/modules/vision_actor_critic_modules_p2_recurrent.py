"""P2 fresh-initialisation actors for the dual-D435 Head ablation.

This module deliberately keeps the B1/B2 causal boundary explicit.  The
``_DualD435Core`` child is the complete common policy core and therefore has a
stable ``core.*`` state-dict namespace in both actors.  B2-only Head/context
parameters live on the B2 wrapper, outside the common-init whitelist.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import pickle
import random
import tempfile
from collections.abc import Mapping
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from hydra.utils import instantiate
from torch.distributions import Normal

from gr00t.rl.trl.modules.memory import Memory
from gr00t.rl.utils.running_mean_std import RunningMeanStd


P2_B1_ARCHITECTURE = "C-B1-DUALRAW-SHAREDENC-TOEIN20-V19-P2"
P2_B2_ARCHITECTURE = "C-B2H-DUALRAW-SHAREDENC-TOEIN20-V19-P2"
# Standalone B2H toe-out architecture.  The historical P2 identifiers above
# are intentionally preserved; this is an additive identity for the new
# four-rank Accelerate/DDP path.
P2_B2H_TOEOUT6_ARCHITECTURE = "C-B2H-DUALRAW-SHAREDENC-TOEOUT6-V19-P2"
P2_COMMON_INIT_SCHEMA = "a2_cb2h_pro_p2_common_init_v1"
P2_STEP0_SCHEMA = "a2_cb2h_pro_p2_step0_manifest_v1"
P2_COMMON_PREFIX = "core."
P2_COMMON_COMPONENTS = (
    "left_view_embedding",
    "right_view_embedding",
    "std",
    "d435i_vision_module",
    "left_view_norm",
    "right_view_norm",
    "manipulation_norm",
    "manipulation_residual",
    "memory",
    "mlp_module",
    "running_mean_std",
)


def _build_real_d435_syncbn_schema() -> tuple[str, ...]:
    """Return the ordered core schema produced by BaseModule's ResNet18/SyncBN.

    The schema is deliberately explicit rather than inferred from the current
    actor.  A moved, added, or removed ``core.*`` state key therefore fails
    before any common-init artifact can be created or loaded.
    """
    keys = [
        "core.left_view_embedding",
        "core.right_view_embedding",
        "core.std",
    ]
    keys.extend(
        [
            "core.d435i_vision_module.module.0.0.weight",
            "core.d435i_vision_module.module.0.1.weight",
            "core.d435i_vision_module.module.0.1.bias",
            "core.d435i_vision_module.module.0.1.running_mean",
            "core.d435i_vision_module.module.0.1.running_var",
            "core.d435i_vision_module.module.0.1.num_batches_tracked",
        ]
    )
    stages = (
        ("0.4", ((64, 64), (64, 64))),
        ("0.5", ((64, 128), (128, 128))),
        ("0.6", ((128, 256), (256, 256))),
        ("0.7", ((256, 512), (512, 512))),
    )
    for stage_name, blocks in stages:
        for block_index, (in_channels, out_channels) in enumerate(blocks):
            prefix = f"core.d435i_vision_module.module.{stage_name}.{block_index}"
            keys.extend(
                (
                    f"{prefix}.conv1.weight",
                    f"{prefix}.bn1.weight",
                    f"{prefix}.bn1.bias",
                    f"{prefix}.bn1.running_mean",
                    f"{prefix}.bn1.running_var",
                    f"{prefix}.bn1.num_batches_tracked",
                    f"{prefix}.conv2.weight",
                    f"{prefix}.bn2.weight",
                    f"{prefix}.bn2.bias",
                    f"{prefix}.bn2.running_mean",
                    f"{prefix}.bn2.running_var",
                    f"{prefix}.bn2.num_batches_tracked",
                )
            )
            if in_channels != out_channels:
                keys.extend(
                    (
                        f"{prefix}.downsample.0.weight",
                        f"{prefix}.downsample.1.weight",
                        f"{prefix}.downsample.1.bias",
                        f"{prefix}.downsample.1.running_mean",
                        f"{prefix}.downsample.1.running_var",
                        f"{prefix}.downsample.1.num_batches_tracked",
                    )
                )
    keys.extend(
        (
            "core.d435i_vision_module.module.3.weight",
            "core.d435i_vision_module.module.3.bias",
            "core.left_view_norm.weight",
            "core.left_view_norm.bias",
            "core.right_view_norm.weight",
            "core.right_view_norm.bias",
            "core.manipulation_norm.weight",
            "core.manipulation_norm.bias",
            "core.manipulation_residual.0.weight",
            "core.manipulation_residual.0.bias",
            "core.manipulation_residual.2.weight",
            "core.manipulation_residual.2.bias",
            "core.manipulation_residual.3.weight",
            "core.manipulation_residual.3.bias",
            "core.memory.rnn.weight_ih_l0",
            "core.memory.rnn.weight_hh_l0",
            "core.memory.rnn.bias_ih_l0",
            "core.memory.rnn.bias_hh_l0",
            "core.memory.rnn.weight_ih_l1",
            "core.memory.rnn.weight_hh_l1",
            "core.memory.rnn.bias_ih_l1",
            "core.memory.rnn.bias_hh_l1",
            "core.mlp_module.module.0.weight",
            "core.mlp_module.module.0.bias",
            "core.mlp_module.module.2.weight",
            "core.mlp_module.module.2.bias",
            "core.mlp_module.module.4.weight",
            "core.mlp_module.module.4.bias",
            "core.mlp_module.module.6.weight",
            "core.mlp_module.module.6.bias",
            "core.running_mean_std.running_mean",
            "core.running_mean_std.running_var",
            "core.running_mean_std.count",
        )
    )
    return tuple(keys)


P2_COMMON_KEY_SCHEMA = _build_real_d435_syncbn_schema()


def p2_production_state_contract(branch: str, role: str) -> dict:
    """Return the exact ordered production key/shape/dtype contract.

    The contract is derived from the pinned P2 architecture components rather
    than from a checkpoint's prefixes or key count.  In particular, the ResNet
    portion is taken from an independently constructed torchvision ResNet18
    converted to SyncBatchNorm, while the recurrent/MLP dimensions are the
    explicit P2 YAML dimensions.  Tensor value hashes remain run-specific and
    are therefore intentionally excluded from this structural contract.
    """
    if branch not in {"b1", "b2"}:
        raise ValueError(f"unsupported P2 production branch: {branch!r}")
    if role not in {"policy", "value"}:
        raise ValueError(f"unsupported P2 production role: {role!r}")

    def identity(key, shape, dtype="torch.float32"):
        return {"key": key, "shape": list(shape), "dtype": dtype}

    if role == "policy":
        import torchvision.models as models

        resnet = models.resnet18(weights=None)
        resnet = nn.SyncBatchNorm.convert_sync_batchnorm(resnet)
        features = nn.Sequential(*list(resnet.children())[:-2])
        resnet_shapes = {
            key: (list(tensor.shape), str(tensor.dtype))
            for key, tensor in features.state_dict().items()
        }
        identities = []
        if branch == "b2":
            identities.append(identity("head_view_embedding", (128,)))
        for key in P2_COMMON_KEY_SCHEMA:
            if key in {
                "core.left_view_embedding",
                "core.right_view_embedding",
                "core.std",
            }:
                shape = {"core.left_view_embedding": (128,), "core.right_view_embedding": (128,), "core.std": (12,)}[key]
                identities.append(identity(key, shape))
            elif key.startswith("core.d435i_vision_module.module.0."):
                suffix = key.removeprefix("core.d435i_vision_module.module.0.")
                if suffix not in resnet_shapes:
                    raise RuntimeError(f"P2 ResNet18 shape contract lacks {suffix!r}")
                shape, dtype = resnet_shapes[suffix]
                identities.append(identity(key, shape, dtype))
            elif key == "core.d435i_vision_module.module.3.weight":
                identities.append(identity(key, (128, 512)))
            elif key == "core.d435i_vision_module.module.3.bias":
                identities.append(identity(key, (128,)))
            elif key.startswith("core.left_view_norm.") or key.startswith("core.right_view_norm.") or key.startswith("core.manipulation_norm."):
                identities.append(identity(key, (128,)))
            elif key == "core.manipulation_residual.0.weight":
                identities.append(identity(key, (256, 384)))
            elif key == "core.manipulation_residual.0.bias":
                identities.append(identity(key, (256,)))
            elif key == "core.manipulation_residual.2.weight":
                identities.append(identity(key, (256,)))
            elif key == "core.manipulation_residual.2.bias":
                identities.append(identity(key, (256,)))
            elif key == "core.manipulation_residual.3.weight":
                identities.append(identity(key, (128, 256)))
            elif key == "core.manipulation_residual.3.bias":
                identities.append(identity(key, (128,)))
            elif key.startswith("core.memory.rnn."):
                suffix = key.removeprefix("core.memory.rnn.")
                recurrent_shapes = {
                    "weight_ih_l0": (1024, 209),
                    "weight_hh_l0": (1024, 256),
                    "bias_ih_l0": (1024,),
                    "bias_hh_l0": (1024,),
                    "weight_ih_l1": (1024, 256),
                    "weight_hh_l1": (1024, 256),
                    "bias_ih_l1": (1024,),
                    "bias_hh_l1": (1024,),
                }
                identities.append(identity(key, recurrent_shapes[suffix]))
            elif key.startswith("core.mlp_module.module."):
                mlp_shapes = {
                    "core.mlp_module.module.0.weight": (512, 256),
                    "core.mlp_module.module.0.bias": (512,),
                    "core.mlp_module.module.2.weight": (256, 512),
                    "core.mlp_module.module.2.bias": (256,),
                    "core.mlp_module.module.4.weight": (128, 256),
                    "core.mlp_module.module.4.bias": (128,),
                    "core.mlp_module.module.6.weight": (12, 128),
                    "core.mlp_module.module.6.bias": (12,),
                }
                identities.append(identity(key, mlp_shapes[key]))
            elif key == "core.running_mean_std.running_mean" or key == "core.running_mean_std.running_var":
                identities.append(identity(key, (81,)))
            elif key == "core.running_mean_std.count":
                identities.append(identity(key, ()))
            else:
                raise RuntimeError(f"P2 production shape contract has no policy key {key!r}")
        if branch == "b2":
            head = []
            for key, (shape, dtype) in resnet_shapes.items():
                head.append(identity(f"head_vision_module.module.0.{key}", shape, dtype))
            head.extend(
                (
                    identity("head_vision_module.module.3.weight", (128, 512)),
                    identity("head_vision_module.module.3.bias", (128,)),
                    identity("head_view_norm.weight", (128,)),
                    identity("head_view_norm.bias", (128,)),
                    identity("context_norm.weight", (128,)),
                    identity("context_norm.bias", (128,)),
                    identity("context_residual.0.weight", (256, 390)),
                    identity("context_residual.0.bias", (256,)),
                    identity("context_residual.2.weight", (256,)),
                    identity("context_residual.2.bias", (256,)),
                    identity("context_residual.3.weight", (128, 256)),
                    identity("context_residual.3.bias", (128,)),
                    identity("context_gate.0.weight", (64, 390)),
                    identity("context_gate.0.bias", (64,)),
                    identity("context_gate.2.weight", (1, 64)),
                    identity("context_gate.2.bias", (1,)),
                )
            )
            identities.extend(head)
        expected_keys = list(P2_COMMON_KEY_SCHEMA) if branch == "b1" else [
            item["key"] for item in identities
        ]
    else:
        identities = [
            identity("critic_module.module.0.weight", (512, 256)),
            identity("critic_module.module.0.bias", (512,)),
            identity("critic_module.module.2.weight", (256, 512)),
            identity("critic_module.module.2.bias", (256,)),
            identity("critic_module.module.4.weight", (128, 256)),
            identity("critic_module.module.4.bias", (128,)),
            identity("critic_module.module.6.weight", (1, 128)),
            identity("critic_module.module.6.bias", (1,)),
            identity("running_mean_std.running_mean", (138,)),
            identity("running_mean_std.running_var", (138,)),
            identity("running_mean_std.count", ()),
            identity("memory.rnn.weight_ih_l0", (1024, 138)),
            identity("memory.rnn.weight_hh_l0", (1024, 256)),
            identity("memory.rnn.bias_ih_l0", (1024,)),
            identity("memory.rnn.bias_hh_l0", (1024,)),
            identity("memory.rnn.weight_ih_l1", (1024, 256)),
            identity("memory.rnn.weight_hh_l1", (1024, 256)),
            identity("memory.rnn.bias_ih_l1", (1024,)),
            identity("memory.rnn.bias_hh_l1", (1024,)),
        ]
        expected_keys = [item["key"] for item in identities]

    if [item["key"] for item in identities] != expected_keys:
        raise RuntimeError("P2 production state contract key order is internally inconsistent")
    contract_payload = [
        {"key": item["key"], "shape": item["shape"], "dtype": item["dtype"]}
        for item in identities
    ]
    parameter_identities = [
        item
        for item in identities
        if not item["key"].endswith(("running_mean", "running_var", "num_batches_tracked", "count"))
    ]
    contract_sha256 = _sha256_bytes(_canonical_json(contract_payload).encode("utf-8"))
    parameter_sha256 = _sha256_bytes(_canonical_json(parameter_identities).encode("utf-8"))
    return {
        "keys": [item["key"] for item in identities],
        "identities": identities,
        "contract_sha256": contract_sha256,
        "parameter_identities": parameter_identities,
        "parameter_keys": [item["key"] for item in parameter_identities],
        "parameter_count": len(parameter_identities),
        "parameter_schema_sha256": parameter_sha256,
    }


def _canonical_json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _require_sha256(value, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return value


P2_COMMON_KEY_SCHEMA_SHA256 = _sha256_bytes(_canonical_json(P2_COMMON_KEY_SCHEMA).encode("utf-8"))


def sha256_file(path: str | Path) -> str:
    path = Path(path).expanduser().resolve(strict=True)
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_immutable_snapshot(path: str | Path) -> tuple[bytes, str]:
    """Read one byte snapshot and hash exactly those bytes.

    Common-init consumers must decode from this same in-memory snapshot; a
    second filesystem open after hashing would reintroduce a TOCTOU window.
    """
    source = Path(path).expanduser().resolve(strict=True)
    with source.open("rb") as handle:
        payload = handle.read()
    return payload, _sha256_bytes(payload)


def _atomic_write_bytes(path: str | Path, payload: bytes) -> None:
    destination = Path(path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=str(destination.parent)
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
        directory_fd = os.open(destination.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary.exists():
            temporary.unlink()


def _atomic_torch_save(payload, path: str | Path) -> None:
    destination = Path(path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=str(destination.parent)
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            torch.save(payload, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
        directory_fd = os.open(destination.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary.exists():
            temporary.unlink()


def _tensor_identity(key: str, tensor: torch.Tensor) -> dict:
    if not torch.is_tensor(tensor):
        raise TypeError(f"common-init state {key!r} must be a tensor")
    if tensor.layout != torch.strided:
        raise ValueError(f"common-init state {key!r} must be strided")
    if tensor.device.type != "cpu":
        tensor = tensor.detach().to(device="cpu")
    tensor = tensor.detach().contiguous()
    if not bool(torch.all(torch.isfinite(tensor.float())).item()):
        raise ValueError(f"common-init state {key!r} contains non-finite values")
    payload = tensor.numpy().tobytes(order="C")
    return {
        "key": key,
        "shape": list(tensor.shape),
        "dtype": str(tensor.dtype),
        "sha256": _sha256_bytes(payload),
    }


def common_core_state(actor: nn.Module) -> tuple[dict[str, torch.Tensor], list[dict], str]:
    """Return the exact ``core.*`` state and deterministic aggregate hash."""
    state = actor.state_dict()
    keys = [key for key in state if key.startswith(P2_COMMON_PREFIX)]
    if not keys:
        raise RuntimeError("P2 actor has no core.* common-init state")
    components = {key.split(".", 2)[1] for key in keys if key.count(".") >= 2}
    if not components.issubset(set(P2_COMMON_COMPONENTS)):
        raise RuntimeError(
            "P2 common-init contains an unknown core component: "
            f"{sorted(components.difference(P2_COMMON_COMPONENTS))}"
        )
    if tuple(keys) != P2_COMMON_KEY_SCHEMA:
        raise RuntimeError(
            "P2 common-init ordered core schema mismatch: "
            f"expected_sha={P2_COMMON_KEY_SCHEMA_SHA256} actual_sha="
            f"{_sha256_bytes(_canonical_json(keys).encode('utf-8'))}"
        )
    selected = {}
    identities = []
    for key in keys:
        tensor = state[key]
        identity = _tensor_identity(key, tensor)
        selected[key] = tensor.detach().to(device="cpu").contiguous().clone()
        identities.append(identity)
    aggregate = _sha256_bytes(_canonical_json(identities).encode("utf-8"))
    return selected, identities, aggregate


def _rng_tensor_hash(tensor: torch.Tensor) -> str:
    tensor = tensor.detach().to(device="cpu").contiguous()
    return _sha256_bytes(tensor.numpy().tobytes(order="C"))


def capture_rng_state() -> dict:
    """Capture all RNG domains used by the P2 launcher."""
    cuda_states = []
    if torch.cuda.is_available():
        cuda_states = [state.detach().cpu().clone() for state in torch.cuda.get_rng_state_all()]
    state = {
        "python": random.getstate(),
        "numpy": np.random.get_state(),
        "torch_cpu": torch.get_rng_state().detach().cpu().clone(),
        "torch_cuda": cuda_states,
    }
    state["identity"] = rng_state_identity(state)
    return state


def restore_rng_state(state: Mapping) -> None:
    """Restore a previously captured RNG state without silent downgrade."""
    required = {"python", "numpy", "torch_cpu", "torch_cuda"}
    missing = required.difference(state)
    if missing:
        raise KeyError(f"P2 RNG state is missing fields: {sorted(missing)}")
    random.setstate(state["python"])
    np.random.set_state(state["numpy"])
    torch_cpu = state["torch_cpu"]
    if not torch.is_tensor(torch_cpu) or torch_cpu.dtype != torch.uint8:
        raise TypeError("P2 torch CPU RNG state must be a uint8 tensor")
    torch.set_rng_state(torch_cpu.detach().cpu().contiguous())
    cuda_states = state["torch_cuda"]
    if not isinstance(cuda_states, list):
        raise TypeError("P2 torch CUDA RNG state must be a list")
    if torch.cuda.is_available():
        current = torch.cuda.device_count()
        if len(cuda_states) != current:
            raise RuntimeError(
                "P2 CUDA RNG device count changed: "
                f"captured={len(cuda_states)} current={current}"
            )
        torch.cuda.set_rng_state_all([value.detach().cpu().contiguous() for value in cuda_states])
    elif cuda_states:
        raise RuntimeError("P2 CUDA RNG state is non-empty but CUDA is unavailable")


def rng_state_identity(state: Mapping) -> str:
    """Hash every serialized RNG domain so restore evidence is exact."""
    payload = []
    for name in ("torch_cpu", "torch_cuda"):
        value = state.get(name)
        if name == "torch_cpu":
            values = [value]
        else:
            values = value if isinstance(value, list) else []
        payload.append({"name": name, "hashes": [_rng_tensor_hash(item) for item in values]})
    for name in ("python", "numpy"):
        if name not in state:
            raise KeyError(f"RNG state is missing {name!r}")
        payload.append({"name": name, "sha256": _sha256_bytes(pickle.dumps(state[name], protocol=4))})
    return _sha256_bytes(_canonical_json(payload).encode("utf-8"))


def create_common_init_artifact(
    actor: nn.Module,
    path: str | Path,
    *,
    branch: str,
    architecture: str,
    seed: int,
    config_sha256: str,
    runtime_identity: Mapping,
    rng_before_policy: Mapping,
    rng_downstream: Mapping,
) -> dict:
    """Seal a fresh B1 core before trainer/optimizer construction."""
    if branch != "b1" or architecture != P2_B1_ARCHITECTURE:
        raise ValueError("common-init creation is only valid for the fresh B1 branch")
    destination = Path(path).expanduser().resolve()
    if destination.exists():
        raise FileExistsError(f"P2 common-init artifact already exists: {destination}")
    state, identities, aggregate = common_core_state(actor)
    if not isinstance(seed, int) or isinstance(seed, bool) or seed != 0:
        raise ValueError(f"P2 fresh common-init seed must be integer 0; got {seed!r}")
    if not isinstance(config_sha256, str) or len(config_sha256) != 64:
        raise ValueError("P2 common-init config SHA256 must be a 64-character string")
    manifest = {
        "schema": P2_COMMON_INIT_SCHEMA,
        "branch": branch,
        "architecture": architecture,
        "seed": seed,
        "config_sha256": config_sha256,
        "runtime_identity": dict(runtime_identity),
        "common_prefix": P2_COMMON_PREFIX,
        "common_components": list(P2_COMMON_COMPONENTS),
        "common_core_key_schema_sha256": P2_COMMON_KEY_SCHEMA_SHA256,
        "key_count": len(identities),
        "keys": identities,
        "aggregate_sha256": aggregate,
        "rng_before_policy_identity": rng_before_policy.get("identity"),
        "rng_downstream_identity": rng_downstream.get("identity"),
    }
    if not isinstance(manifest["rng_before_policy_identity"], str):
        raise ValueError("P2 common-init requires a pre-policy RNG identity")
    if not isinstance(manifest["rng_downstream_identity"], str):
        raise ValueError("P2 common-init requires a downstream RNG identity")
    _atomic_torch_save(
        {"manifest": manifest, "state_dict": state, "rng_downstream": dict(rng_downstream)},
        destination,
    )
    return manifest


def load_common_init_artifact(
    actor: nn.Module,
    path: str | Path,
    *,
    branch: str,
    architecture: str,
    seed: int,
    config_sha256: str,
    runtime_identity: Mapping,
    rng_before_policy: Mapping | None = None,
    trusted_artifact_sha256: str,
    source_step0_manifest_path: str | Path | None = None,
    trusted_source_step0_manifest_sha256: str | None = None,
) -> tuple[dict, dict]:
    """Load exactly the B1 common core into B2 and return manifest/RNG state."""
    if branch != "b2" or architecture != P2_B2_ARCHITECTURE:
        raise ValueError("common-init loading is only valid for the fresh B2 branch")
    source = Path(path).expanduser().resolve(strict=True)
    if not isinstance(trusted_artifact_sha256, str) or len(trusted_artifact_sha256) != 64:
        raise ValueError("P2 B2 requires a caller-supplied full artifact SHA256")
    artifact_bytes, actual_artifact_sha256 = read_immutable_snapshot(source)
    if actual_artifact_sha256 != trusted_artifact_sha256:
        raise RuntimeError(
            "P2 common-init external artifact digest mismatch: "
            f"trusted={trusted_artifact_sha256} actual={actual_artifact_sha256}"
        )
    payload = torch.load(io.BytesIO(artifact_bytes), map_location="cpu", weights_only=False)
    if not isinstance(payload, Mapping) or not isinstance(payload.get("manifest"), Mapping):
        raise ValueError("P2 common-init artifact must contain a manifest mapping")
    manifest = dict(payload["manifest"])
    if manifest.get("schema") != P2_COMMON_INIT_SCHEMA:
        raise RuntimeError("P2 common-init schema drifted")
    if manifest.get("branch") != "b1" or manifest.get("architecture") != P2_B1_ARCHITECTURE:
        raise RuntimeError("P2 common-init source is not the sealed B1 artifact")
    if manifest.get("seed") != seed or manifest.get("config_sha256") != config_sha256:
        raise RuntimeError("P2 common-init seed/config identity mismatch")
    if manifest.get("runtime_identity") != dict(runtime_identity):
        raise RuntimeError("P2 common-init runtime identity mismatch")
    if manifest.get("common_core_key_schema_sha256") != P2_COMMON_KEY_SCHEMA_SHA256:
        raise RuntimeError("P2 common-init core key schema SHA mismatch")
    if manifest.get("common_components") != list(P2_COMMON_COMPONENTS):
        raise RuntimeError("P2 common-init component whitelist drifted")
    if rng_before_policy is not None and manifest.get("rng_before_policy_identity") != rng_before_policy.get("identity"):
        raise RuntimeError("P2 common-init pre-policy RNG identity mismatch")
    source_state = payload.get("state_dict")
    if not isinstance(source_state, Mapping):
        raise TypeError("P2 common-init state_dict must be a mapping")
    target_state, _, target_aggregate = common_core_state(actor)
    target_state_refs = actor.state_dict()
    source_keys = list(source_state)
    target_keys = list(target_state)
    if source_keys != target_keys:
        raise RuntimeError(
            "P2 common-init core key set mismatch: "
            f"source_only={sorted(set(source_keys) - set(target_keys))} "
            f"target_only={sorted(set(target_keys) - set(source_keys))}"
        )
    manifest_keys = manifest.get("keys")
    if not isinstance(manifest_keys, list) or any(not isinstance(item, Mapping) for item in manifest_keys):
        raise RuntimeError("P2 common-init manifest key list is malformed")
    source_identities = [_tensor_identity(key, source_state[key]) for key in source_keys]
    if source_identities != manifest_keys:
        raise RuntimeError("P2 common-init manifest does not match its source state")
    if manifest.get("key_count") != len(source_keys):
        raise RuntimeError("P2 common-init manifest key_count drifted")
    for key in target_keys:
        source_tensor = source_state[key]
        target_tensor = target_state_refs[key]
        if not torch.is_tensor(source_tensor) or not torch.is_tensor(target_tensor):
            raise TypeError(f"P2 common-init state {key!r} is not a tensor")
        if tuple(source_tensor.shape) != tuple(target_tensor.shape) or source_tensor.dtype != target_tensor.dtype:
            raise RuntimeError(f"P2 common-init state shape/dtype mismatch for {key!r}")
        if not bool(torch.all(torch.isfinite(source_tensor.float())).item()):
            raise ValueError(f"P2 common-init source {key!r} is non-finite")
        target_tensor.copy_(source_tensor.to(device=target_tensor.device, dtype=target_tensor.dtype))
    _, loaded_identities, loaded_aggregate = common_core_state(actor)
    if loaded_identities != manifest.get("keys") or loaded_aggregate != manifest.get("aggregate_sha256"):
        raise RuntimeError("P2 common-init post-load hash proof failed")
    downstream_rng = payload.get("rng_downstream")
    if not isinstance(downstream_rng, Mapping):
        raise TypeError("P2 common-init artifact is missing downstream RNG state")
    if rng_state_identity(downstream_rng) != manifest.get("rng_downstream_identity"):
        raise RuntimeError("P2 common-init downstream RNG identity drifted")
    if source_step0_manifest_path is not None:
        step0 = load_step0_manifest(
            source_step0_manifest_path,
            expected_sha256=trusted_source_step0_manifest_sha256,
        )
        expected_step0 = {
            "branch": "b1",
            "architecture": P2_B1_ARCHITECTURE,
            "seed": seed,
            "config_sha256": config_sha256,
            "runtime_identity": dict(runtime_identity),
            "common_core_sha256": manifest.get("aggregate_sha256"),
            "common_core_key_schema_sha256": P2_COMMON_KEY_SCHEMA_SHA256,
            "common_core_keys": [item["key"] for item in manifest.get("keys", [])],
            "common_core_key_identities": list(manifest.get("keys", [])),
            "artifact_sha256": trusted_artifact_sha256,
            "rng_before_policy_identity": manifest.get("rng_before_policy_identity"),
            "rng_downstream_identity": manifest.get("rng_downstream_identity"),
        }
        for key, expected in expected_step0.items():
            if step0.get(key) != expected:
                raise RuntimeError(f"P2 B1 step0 manifest field drifted: {key}")
    return manifest, dict(downstream_rng)


def load_step0_manifest(
    path: str | Path,
    *,
    expected_sha256: str | None = None,
) -> dict:
    source = Path(path).expanduser().resolve(strict=True)
    manifest_bytes, actual = read_immutable_snapshot(source)
    if expected_sha256 is not None and actual != expected_sha256:
        raise RuntimeError(
            "P2 step0 external digest mismatch: "
            f"expected={expected_sha256} actual={actual}"
        )
    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"P2 step0 manifest is not valid JSON: {source}") from exc
    if not isinstance(manifest, dict) or manifest.get("schema") != P2_STEP0_SCHEMA:
        raise RuntimeError("P2 step0 manifest schema drifted")
    if manifest.get("global_step") != 0 or manifest.get("optimizer") is not None:
        raise RuntimeError("P2 step0 manifest must describe global_step=0 and optimizer=null")
    if manifest.get("common_core_key_schema_sha256") != P2_COMMON_KEY_SCHEMA_SHA256:
        raise RuntimeError("P2 step0 common key schema SHA drifted")
    if tuple(manifest.get("common_core_keys", ())) != P2_COMMON_KEY_SCHEMA:
        raise RuntimeError("P2 step0 common_core_keys must be the exact ordered 156-key schema")
    identities = manifest.get("common_core_key_identities")
    if not isinstance(identities, list) or len(identities) != len(P2_COMMON_KEY_SCHEMA):
        raise RuntimeError("P2 step0 common_core_key_identities must contain all 156 keys")
    for index, (key, identity) in enumerate(zip(P2_COMMON_KEY_SCHEMA, identities, strict=True)):
        if not isinstance(identity, Mapping) or set(identity) != {"key", "shape", "dtype", "sha256"}:
            raise RuntimeError(f"P2 step0 common core identity {index} is malformed")
        if identity["key"] != key:
            raise RuntimeError(f"P2 step0 common core key order drifted at index {index}")
        shape = identity["shape"]
        if not isinstance(shape, list) or any(isinstance(dim, bool) or not isinstance(dim, int) or dim <= 0 for dim in shape):
            raise RuntimeError(f"P2 step0 common core shape is invalid at index {index}")
        if not isinstance(identity["dtype"], str) or not identity["dtype"]:
            raise RuntimeError(f"P2 step0 common core dtype is invalid at index {index}")
        _require_sha256(identity["sha256"], f"P2 step0 common core tensor SHA {index}")
    expected_core_sha = _sha256_bytes(_canonical_json(identities).encode("utf-8"))
    if _require_sha256(manifest.get("common_core_sha256"), "P2 step0 common core SHA") != expected_core_sha:
        raise RuntimeError("P2 step0 common core aggregate SHA drifted")
    _require_sha256(manifest.get("common_init_manifest_sha256"), "P2 step0 common-init manifest SHA")
    _require_sha256(manifest.get("artifact_sha256"), "P2 step0 artifact SHA")
    _require_sha256(manifest.get("rng_before_policy_identity"), "P2 step0 pre-policy RNG identity")
    _require_sha256(manifest.get("rng_downstream_identity"), "P2 step0 downstream RNG identity")
    return manifest


def write_step0_manifest(path: str | Path, manifest: Mapping) -> None:
    destination = Path(path).expanduser().resolve()
    if destination.exists():
        raise FileExistsError(f"P2 step0 manifest already exists: {destination}")
    payload = dict(manifest)
    payload["schema"] = P2_STEP0_SCHEMA
    payload["global_step"] = 0
    payload["optimizer"] = None
    if not isinstance(payload.get("common_core_sha256"), str):
        raise ValueError("P2 step0 manifest requires common_core_sha256")
    required = (
        "artifact_sha256",
        "common_core_key_schema_sha256",
        "common_core_keys",
        "common_core_key_identities",
        "rng_downstream_identity",
    )
    missing = [key for key in required if key not in payload]
    if missing:
        raise ValueError(f"P2 step0 manifest is missing required fields: {missing}")
    if payload["common_core_key_schema_sha256"] != P2_COMMON_KEY_SCHEMA_SHA256:
        raise ValueError("P2 step0 common key schema SHA drifted")
    if list(payload["common_core_keys"]) != list(P2_COMMON_KEY_SCHEMA):
        raise ValueError("P2 step0 common core key order drifted")
    if not isinstance(payload["common_core_key_identities"], list) or len(payload["common_core_key_identities"]) != len(P2_COMMON_KEY_SCHEMA):
        raise ValueError("P2 step0 common core key identities are not ordered/exact")
    _atomic_write_bytes(destination, (_canonical_json(payload) + "\n").encode("utf-8"))


class _DualD435Core(nn.Module):
    """Common dual-D435 feature/recurrent/action core."""

    def __init__(
        self,
        env_config,
        algo_config,
        backbone,
        module_dim_dict=None,
        running_mean_std=False,
        input_key="actor_obs",
        rnn_type="lstm",
        rnn_hidden_dim=256,
        rnn_num_layers=2,
        d435i_forward_mode="packed",
    ):
        super().__init__()
        module_dim_dict = {} if module_dim_dict is None else dict(module_dim_dict)
        obs_dim_dict = env_config.robot.algo_obs_dim_dict
        if int(obs_dim_dict.get(input_key, -1)) != 81:
            raise ValueError(f"P2 actor_obs must be 81D; got {obs_dim_dict.get(input_key)!r}")
        if d435i_forward_mode != "packed":
            raise ValueError("P2 B1/B2 foundation requires packed D435 forwarding")
        self.input_key = input_key
        self.d435i_forward_mode = d435i_forward_mode
        self.d435i_vision_module = instantiate(
            backbone.d435i_vision_module,
            env_config=env_config,
            algo_config=algo_config,
            obs_dim_dict=obs_dim_dict,
            module_dim_dict=module_dim_dict,
            _recursive_=False,
        )
        if int(self.d435i_vision_module.output_dim) != 128:
            raise ValueError(f"P2 D435 encoder output must be 128; got {self.d435i_vision_module.output_dim}")
        layer_config = self.d435i_vision_module.module_config_dict.layer_config
        layer_type = layer_config.type if hasattr(layer_config, "type") else layer_config["type"]
        if layer_type != "ResNet":
            raise ValueError(f"P2 D435 encoder must use ResNet; got {layer_type!r}")

        self.left_view_embedding = nn.Parameter(torch.zeros(128))
        self.right_view_embedding = nn.Parameter(torch.zeros(128))
        self.left_view_norm = nn.LayerNorm(128)
        self.right_view_norm = nn.LayerNorm(128)
        self.manipulation_norm = nn.LayerNorm(128)
        self.manipulation_residual = nn.Sequential(
            nn.Linear(384, 256),
            nn.SiLU(),
            nn.LayerNorm(256),
            nn.Linear(256, 128),
        )
        nn.init.zeros_(self.manipulation_residual[-1].weight)
        nn.init.zeros_(self.manipulation_residual[-1].bias)
        self.manipulation_tau_s = 0.05

        concat_dim = 81 + 128
        if concat_dim != 209:
            raise RuntimeError(f"P2 recurrent input contract drifted: {concat_dim}")
        self.memory = Memory(
            input_size=concat_dim,
            type=rnn_type,
            num_layers=int(rnn_num_layers),
            hidden_size=int(rnn_hidden_dim),
        )
        recurrent_module_dim = dict(module_dim_dict)
        recurrent_module_dim[input_key] = int(rnn_hidden_dim)
        self.mlp_module = instantiate(
            backbone.mlp_module,
            env_config=env_config,
            algo_config=algo_config,
            obs_dim_dict={input_key: int(rnn_hidden_dim)},
            module_dim_dict=recurrent_module_dim,
            _recursive_=False,
        )
        if int(self.mlp_module.output_dim) != 12:
            raise ValueError(f"P2 action output must be 12; got {self.mlp_module.output_dim}")
        self.running_mean_std = RunningMeanStd((81,), per_channel=True) if running_mean_std else None
        self.num_actions = 12
        init_noise_std = float(algo_config.init_noise_std)
        self.std = nn.Parameter(init_noise_std * torch.ones(self.num_actions))
        if algo_config.get("freeze_noise_std", False):
            self.std.requires_grad = False
        self.clamp_noise_std = bool(algo_config.get("clamp_noise_std", False))
        self.max_noise_std = float(algo_config.get("max_noise_std", 1.0))
        self._diagnostic_cache = {}
        self._diagnostic_per_sample_cache = {}

    @staticmethod
    def _require_tensor(name, value, ndim, last_dim=None):
        if not torch.is_tensor(value) or value.ndim != ndim:
            raise ValueError(f"{name} must be a {ndim}D tensor; got {getattr(value, 'shape', None)}")
        if last_dim is not None and value.shape[-1] != last_dim:
            raise ValueError(f"{name} last dimension must be {last_dim}; got {tuple(value.shape)}")
        if not torch.is_floating_point(value) or not bool(torch.all(torch.isfinite(value)).item()):
            raise ValueError(f"{name} must be finite floating data")

    def normalize_actor_obs(self, actor_obs, masks):
        if not torch.is_tensor(actor_obs) or actor_obs.ndim not in (2, 3):
            raise ValueError(f"P2 actor_obs must be [B,81] or [B,T,81]; got {getattr(actor_obs, 'shape', None)}")
        self._require_tensor("actor_obs", actor_obs, actor_obs.ndim, 81)
        if actor_obs.ndim == 2:
            if masks is not None:
                raise ValueError("P2 recurrent masks are only valid for sequence observations")
            return self.running_mean_std(actor_obs) if self.running_mean_std is not None else actor_obs
        if masks is None or not torch.is_tensor(masks) or masks.dtype != torch.bool or tuple(masks.shape) != tuple(actor_obs.shape[:2]):
            raise ValueError("P2 sequence actor_obs requires boolean masks [B,T]")
        if masks.device != actor_obs.device or not bool(masks.any().item()):
            raise ValueError("P2 sequence masks must share device and contain a valid frame")
        flat = actor_obs.reshape(-1, 81)
        valid = masks.reshape(-1)
        if self.running_mean_std is None:
            normalized = torch.where(valid[:, None], flat, torch.zeros_like(flat))
        else:
            mean = self.running_mean_std.running_mean.to(device=actor_obs.device, dtype=actor_obs.dtype)
            var = self.running_mean_std.running_var.to(device=actor_obs.device, dtype=actor_obs.dtype)
            normalized = torch.clamp((flat - mean) / torch.sqrt(var + self.running_mean_std.epsilon), -5.0, 5.0)
            normalized = torch.where(valid[:, None], normalized, torch.zeros_like(normalized))
        return normalized.reshape_as(actor_obs)

    def _validate_views(self, dual, meta, masks):
        if not torch.is_tensor(dual) or not torch.is_tensor(meta):
            raise ValueError("P2 B1/B2 requires vision_obs and camera_meta tensors")
        if dual.ndim not in (4, 5):
            raise ValueError("P2 dual D435 observations must be rank 4 or 5")
        expected_meta_ndim = dual.ndim - 2
        if meta.ndim != expected_meta_ndim:
            raise ValueError("P2 dual D435 metadata rank must match image rank")
        self._require_tensor("vision_obs", dual, dual.ndim)
        self._require_tensor("camera_meta", meta, expected_meta_ndim, 4)
        if tuple(dual.shape[-3:]) != (384, 216, 6):
            raise ValueError(f"P2 dual D435 shape must be (384,216,6); got {tuple(dual.shape[-3:])}")
        if tuple(dual.shape[:-3]) != tuple(meta.shape[:-1]) or dual.device != meta.device:
            raise ValueError("P2 dual D435 image/meta leading shapes and devices must match")
        if dual.ndim == 4 and masks is not None:
            raise ValueError("P2 rank-4 rollout observations do not accept masks")
        if dual.ndim == 5 and (masks is None or masks.dtype != torch.bool or tuple(masks.shape) != tuple(dual.shape[:2])):
            raise ValueError("P2 rank-5 observations require boolean masks [B,T]")
        ages = meta[..., :2]
        validity = meta[..., 2:]
        if bool((ages < 0.0).any().item()) or bool((ages > 1.0).any().item()):
            raise ValueError("P2 D435 camera ages must be normalized to [0,1]")
        if not bool(torch.all((validity == 0.0) | (validity == 1.0)).item()):
            raise ValueError("P2 D435 validity flags must be exactly 0 or 1")

    def encode_dual(self, dual, meta, masks=None):
        self._validate_views(dual, meta, masks)
        sequence = dual.ndim == 5
        if sequence:
            batch_size, seq_len = dual.shape[:2]
            dual_flat = dual.reshape(-1, *dual.shape[2:])
            meta_flat = meta.reshape(-1, 4)
            valid = masks.reshape(-1)
            if not bool(valid.any().item()):
                raise ValueError("P2 recurrent masks contain no valid frames")
            dual_flat, meta_flat = dual_flat[valid], meta_flat[valid]
        else:
            batch_size, seq_len, valid = dual.shape[0], None, None
            dual_flat, meta_flat = dual, meta
        left = dual_flat[..., :3].permute(0, 3, 1, 2).contiguous()
        right = dual_flat[..., 3:6].permute(0, 3, 1, 2).contiguous()
        if left.dtype != right.dtype or left.device != right.device or tuple(left.shape) != tuple(right.shape):
            raise ValueError("P2 left/right D435 tensors must have matching dtype/device/shape")
        count = int(left.shape[0])
        if count <= 0:
            raise ValueError("P2 D435 encoder received no valid frame")
        packed = torch.cat((left, right), dim=0)
        if tuple(packed.shape) != (2 * count, 3, 384, 216):
            raise ValueError(f"P2 packed D435 input shape drifted: {tuple(packed.shape)}")
        encoded = self.d435i_vision_module(packed)
        if not torch.is_tensor(encoded) or tuple(encoded.shape) != (2 * count, 128):
            raise ValueError(f"P2 packed D435 output must be {(2 * count, 128)}; got {getattr(encoded, 'shape', None)}")
        if encoded.dtype != packed.dtype or encoded.device != packed.device or not bool(torch.all(torch.isfinite(encoded)).item()):
            raise ValueError("P2 packed D435 output must preserve finite dtype/device")
        f_left, f_right = encoded.split(count, dim=0)
        left = self.left_view_norm(f_left + self.left_view_embedding)
        right = self.right_view_norm(f_right + self.right_view_embedding)
        ages_s = meta_flat[:, :2] * 0.1
        left_conf = meta_flat[:, 2] * torch.exp(-ages_s[:, 0] / self.manipulation_tau_s)
        right_conf = meta_flat[:, 3] * torch.exp(-ages_s[:, 1] / self.manipulation_tau_s)
        confidence = left_conf + right_conf
        if not bool((confidence > 0.0).all().item()):
            raise ValueError("P2 requires at least one valid D435 view per row")
        base = (left_conf[:, None] * left + right_conf[:, None] * right) / confidence.clamp_min(torch.finfo(left.dtype).eps)[:, None]
        residual = self.manipulation_residual(torch.cat((left, right, (left - right).abs()), dim=-1))
        latent = self.manipulation_norm(base + residual)
        if not bool(torch.all(torch.isfinite(latent)).item()):
            raise ValueError("P2 D435 fusion produced non-finite latent")
        self._diagnostic_cache = {
            "feature/d435_norm": torch.linalg.vector_norm(latent.detach(), dim=-1).mean(),
        }
        self._diagnostic_per_sample_cache = {
            "feature/d435_norm": torch.linalg.vector_norm(latent.detach(), dim=-1),
        }
        if not sequence:
            return latent
        output = latent.new_zeros((batch_size * seq_len, 128))
        output[valid] = latent
        return output.reshape(batch_size, seq_len, 128).contiguous()

    def get_observability_snapshot(self, *, per_sample=False):
        if not self._diagnostic_cache:
            raise RuntimeError("P2 D435 feature observability is unavailable before forward")
        cache = self._diagnostic_per_sample_cache if per_sample else self._diagnostic_cache
        return {key: value.detach().clone() for key, value in cache.items()}

    def forward_from_latent(
        self,
        actor_obs,
        latent,
        masks=None,
        hidden_states=None,
        stepwise_replay=False,
    ):
        normalized = self.normalize_actor_obs(actor_obs, masks)
        if normalized.ndim == 2:
            recurrent_input = torch.cat((normalized, latent), dim=-1)
            memory_out = self.memory(recurrent_input)
            if memory_out.ndim == 3:
                memory_out = memory_out.squeeze(0)
        elif normalized.ndim == 3:
            recurrent_input = torch.cat((normalized, latent), dim=-1)
            if stepwise_replay:
                state = hidden_states
                outputs = []
                for step in range(recurrent_input.shape[1]):
                    output, state = self.memory(
                        recurrent_input[:, step].unsqueeze(0),
                        masks=masks[:, step : step + 1],
                        hidden_states=state,
                        return_new_hidden_states=True,
                    )
                    outputs.append(output)
                memory_out = torch.cat(outputs, dim=1)
            else:
                memory_out = self.memory(recurrent_input.transpose(0, 1), masks=masks, hidden_states=hidden_states)
        else:
            raise ValueError("P2 recurrent input must be rank 2 or 3")
        output = self.mlp_module(memory_out)
        if not torch.is_tensor(output) or not bool(torch.all(torch.isfinite(output)).item()):
            raise ValueError("P2 action MLP output must be finite")
        return output


class _P2ActorBase(nn.Module):
    is_recurrent = True

    def __init__(self, *, input_key="actor_obs", max_rollout_history=1, **kwargs):
        super().__init__()
        self.input_key = input_key
        self.max_rollout_history = int(max_rollout_history)
        if self.max_rollout_history <= 0:
            raise ValueError("max_rollout_history must be positive")
        self.obs_dict_buffer = {}
        self.dones_buffer = None
        self.steps = 0
        self.distribution = None
        self.is_eval_mode = False
        Normal.set_default_validate_args(False)

    @property
    def has_normalized_actions(self):
        return False

    def _update_obs_buffer(self, obs_dict, episode_attnmask=None, cur_dones=None):
        del cur_dones
        update = False
        for key, value in obs_dict.items():
            if key not in self.obs_dict_buffer:
                self.obs_dict_buffer[key] = value.unsqueeze(1)
            else:
                self.obs_dict_buffer[key] = torch.cat((self.obs_dict_buffer[key], value.unsqueeze(1)), dim=1)
            if self.obs_dict_buffer[key].shape[1] > self.max_rollout_history:
                update = True
                self.obs_dict_buffer[key] = self.obs_dict_buffer[key][:, -self.max_rollout_history:]
        if episode_attnmask is not None and update:
            return episode_attnmask[:, -self.max_rollout_history:, -self.max_rollout_history:]
        return episode_attnmask

    def init_rollout(self):
        self.obs_dict_buffer = {}
        self.dones_buffer = None
        self.steps = 0

    def clear_rollout(self):
        self.obs_dict_buffer = {}
        self.dones_buffer = None
        self.steps = 0
        self.distribution = None
        self.core.memory.detach_hidden_states()

    def reset(self, dones=None):
        self.core.memory.reset(dones)

    def get_hidden_states(self):
        return self.core.memory.hidden_states

    def eval_mode(self):
        self.is_eval_mode = True

    def train_mode(self):
        self.is_eval_mode = False

    @property
    def num_actions(self):
        return self.core.num_actions

    @property
    def std(self):
        return self.core.std

    def _distribution_from_mean(self, mean):
        if self.core.clamp_noise_std:
            with torch.no_grad():
                self.core.std.clamp_(max=self.core.max_noise_std)
        self.distribution = Normal(mean, mean * 0.0 + self.core.std)

    @property
    def action_mean(self):
        if self.distribution is None:
            raise RuntimeError("P2 action distribution is unavailable before forward")
        return self.distribution.mean

    @property
    def action_std(self):
        if self.distribution is None:
            raise RuntimeError("P2 action distribution is unavailable before forward")
        return self.distribution.stddev

    def get_actions_log_prob(self, actions):
        if self.distribution is None:
            raise RuntimeError("P2 action distribution is unavailable before sampling")
        return self.distribution.log_prob(actions).sum(dim=-1)

    def act_from_latent(self, actor_obs, latent, masks=None, hidden_states=None):
        """Evaluate the recurrent action distribution from a cached visual latent."""
        mean = self.core.forward_from_latent(
            actor_obs,
            latent,
            masks=masks,
            hidden_states=hidden_states,
            stepwise_replay=True,
        )
        self._distribution_from_mean(mean)
        return {
            "action_mean": self.action_mean,
            "action_sigma": self.action_std,
        }

    def _advance_step_once(self):
        """Advance the recurrent rollout counter exactly once per policy call."""
        previous = self.steps
        self.steps = previous + 1
        if self.steps != previous + 1:
            raise RuntimeError("P2 actor rollout step counter advanced non-deterministically")

    def get_observability_snapshot(self, *, per_sample=False):
        if not self._diagnostic_cache:
            raise RuntimeError("P2 feature observability is unavailable before forward")
        cache = self._diagnostic_per_sample_cache if per_sample else self._diagnostic_cache
        return {key: value.detach().clone() for key, value in cache.items()}


class DualD435VisionRecurrentActor(_P2ActorBase):
    """B1: dual D435i packed shared encoder with no Head path."""

    architecture_id = P2_B1_ARCHITECTURE

    @property
    def d435i_forward_mode(self):
        return self.core.d435i_forward_mode

    def __init__(
        self,
        env_config,
        algo_config,
        backbone,
        module_dim_dict=None,
        running_mean_std=False,
        max_rollout_history=1,
        input_key="actor_obs",
        rnn_type="lstm",
        rnn_hidden_dim=256,
        rnn_num_layers=2,
        view_contract=None,
        **kwargs,
    ):
        del kwargs
        super().__init__(input_key=input_key, max_rollout_history=max_rollout_history)
        contract = dict(view_contract or {})
        if contract.get("d435i_forward_mode") != "packed":
            raise ValueError("P2 B1 view_contract.d435i_forward_mode must be 'packed'")
        if int(contract.get("camera_meta_dim", 4)) != 4:
            raise ValueError("P2 B1 camera_meta_dim must be 4")
        self.camera_meta_key = "camera_meta"
        self.manipulation_vision_key = "vision_obs"
        self.core = _DualD435Core(
            env_config=env_config,
            algo_config=algo_config,
            backbone=backbone,
            module_dim_dict=module_dim_dict,
            running_mean_std=running_mean_std,
            input_key=input_key,
            rnn_type=rnn_type,
            rnn_hidden_dim=rnn_hidden_dim,
            rnn_num_layers=rnn_num_layers,
            d435i_forward_mode="packed",
        )

    def forward(self, obs_dict, masks=None, hidden_states=None, episode_attnmask=None, **kwargs):
        del episode_attnmask, kwargs
        actor_obs = obs_dict[self.input_key]
        dual = obs_dict[self.manipulation_vision_key]
        meta = obs_dict[self.camera_meta_key]
        latent = self.core.encode_dual(dual, meta, masks)
        return self.core.forward_from_latent(actor_obs, latent, masks, hidden_states)

    def get_observability_snapshot(self, *, per_sample=False):
        """Expose the exact per-forward diagnostics cached by the common core."""
        return self.core.get_observability_snapshot(per_sample=per_sample)

    def rollout(self, obs_dict, episode_attnmask=None, cur_dones=None, **kwargs):
        self._update_obs_buffer(obs_dict, episode_attnmask, cur_dones)
        del kwargs
        with torch.no_grad():
            mean = self.forward(obs_dict)
        self._distribution_from_mean(mean)
        self._advance_step_once()
        return {"actions": self.distribution.sample(), "action_mean": self.action_mean, "action_sigma": self.action_std}

    def act_inference(self, obs_dict, episode_attnmask=None, cur_dones=None, **kwargs):
        self._update_obs_buffer(obs_dict, episode_attnmask, cur_dones)
        del kwargs
        mean = self.forward(obs_dict)
        self._advance_step_once()
        return mean

    def act(self, obs_dict, episode_attnmask=None, masks=None, hidden_states=None, **kwargs):
        mean = self.forward(obs_dict, masks=masks, hidden_states=hidden_states, episode_attnmask=episode_attnmask, **kwargs)
        self._distribution_from_mean(mean)
        return {"actions": self.distribution.sample(), "action_mean": self.action_mean, "action_sigma": self.action_std}

    def update_distribution(self, obs_dict, episode_attnmask=None, last_step_only=False, masks=None, hidden_states=None, **kwargs):
        mean = self.forward(obs_dict, masks=masks, hidden_states=hidden_states, episode_attnmask=episode_attnmask, **kwargs)
        if last_step_only:
            mean = mean[:, -1]
        self._distribution_from_mean(mean)


class DualD435HeadVisionRecurrentActor(_P2ActorBase):
    """B2: B1 core plus the explicit fixed and learned OEM Head paths."""

    architecture_id = P2_B2_ARCHITECTURE

    @property
    def d435i_forward_mode(self):
        return self.core.d435i_forward_mode

    def __init__(
        self,
        env_config,
        algo_config,
        backbone,
        module_dim_dict=None,
        running_mean_std=False,
        max_rollout_history=1,
        input_key="actor_obs",
        rnn_type="lstm",
        rnn_hidden_dim=256,
        rnn_num_layers=2,
        view_contract=None,
        **kwargs,
    ):
        del kwargs
        super().__init__(input_key=input_key, max_rollout_history=max_rollout_history)
        contract = dict(view_contract or {})
        if contract.get("d435i_forward_mode") != "packed":
            raise ValueError("P2 B2 view_contract.d435i_forward_mode must be 'packed'")
        if int(contract.get("camera_meta_dim", 6)) != 6:
            raise ValueError("P2 B2 camera_meta_dim must be 6")
        self.camera_meta_key = "camera_meta"
        self.manipulation_vision_key = "vision_obs"
        self.context_vision_key = "context_vision_obs"
        self.core = _DualD435Core(
            env_config=env_config,
            algo_config=algo_config,
            backbone=backbone,
            module_dim_dict=module_dim_dict,
            running_mean_std=running_mean_std,
            input_key=input_key,
            rnn_type=rnn_type,
            rnn_hidden_dim=rnn_hidden_dim,
            rnn_num_layers=rnn_num_layers,
            d435i_forward_mode="packed",
        )
        obs_dim_dict = env_config.robot.algo_obs_dim_dict
        self.head_vision_module = instantiate(
            backbone.head_vision_module,
            env_config=env_config,
            algo_config=algo_config,
            obs_dim_dict=obs_dim_dict,
            module_dim_dict={} if module_dim_dict is None else dict(module_dim_dict),
            _recursive_=False,
        )
        if int(self.head_vision_module.output_dim) != 128:
            raise ValueError(f"P2 Head encoder output must be 128; got {self.head_vision_module.output_dim}")
        self.head_view_embedding = nn.Parameter(torch.zeros(128))
        self.head_view_norm = nn.LayerNorm(128)
        self.context_norm = nn.LayerNorm(128)
        self.context_residual = nn.Sequential(
            nn.Linear(390, 256),
            nn.SiLU(),
            nn.LayerNorm(256),
            nn.Linear(256, 128),
        )
        self.context_gate = nn.Sequential(
            nn.Linear(390, 64),
            nn.SiLU(),
            nn.Linear(64, 1),
            nn.Sigmoid(),
        )
        nn.init.zeros_(self.context_residual[-1].weight)
        nn.init.zeros_(self.context_residual[-1].bias)
        self.context_tau_s = 0.10
        self.head_base_weight = 0.25
        self._diagnostic_cache = {}
        self._diagnostic_per_sample_cache = {}

    def _fuse_head(self, manipulation, f_head, meta):
        head = self.head_view_norm(f_head + self.head_view_embedding)
        head_age_s = meta[:, 2] * 0.1
        head_conf = meta[:, 5] * torch.exp(-head_age_s / self.context_tau_s)
        context_input = torch.cat((manipulation, head, (manipulation - head).abs(), meta), dim=-1)
        context_residual = self.context_residual(context_input)
        gate = self.context_gate(context_input)
        fixed = head_conf[:, None] * (self.head_base_weight * head)
        gated = head_conf[:, None] * (gate * context_residual)
        fused = self.context_norm(manipulation + fixed + gated)
        self._diagnostic_cache = {
            "feature/d435_norm": torch.linalg.vector_norm(manipulation.detach(), dim=-1).mean(),
            "feature/head_norm": torch.linalg.vector_norm(f_head.detach(), dim=-1).mean(),
            "feature/head_gate_mean": gate.detach().mean(),
            "feature/head_fixed_contribution_norm": torch.linalg.vector_norm(fixed.detach(), dim=-1).mean(),
            "feature/context_residual_gated_norm": torch.linalg.vector_norm(gated.detach(), dim=-1).mean(),
        }
        self._diagnostic_per_sample_cache = {
            "feature/d435_norm": torch.linalg.vector_norm(manipulation.detach(), dim=-1),
            "feature/head_norm": torch.linalg.vector_norm(f_head.detach(), dim=-1),
            "feature/context_gate": gate.detach().squeeze(-1),
            "feature/head_fixed_contribution_norm": torch.linalg.vector_norm(fixed.detach(), dim=-1),
            "feature/context_residual_gated_norm": torch.linalg.vector_norm(gated.detach(), dim=-1),
        }
        if not all(bool(torch.isfinite(value).item()) for value in self._diagnostic_cache.values()):
            raise ValueError("P2 Head diagnostics must be finite")
        if not all(bool(torch.all(torch.isfinite(value)).item()) for value in self._diagnostic_per_sample_cache.values()):
            raise ValueError("P2 Head per-sample diagnostics must be finite")
        return fused

    def get_observability_snapshot(self, *, per_sample=False):
        if not self._diagnostic_cache:
            raise RuntimeError("P2 Head observability is unavailable before forward")
        if per_sample:
            return {key: value.detach().clone() for key, value in self._diagnostic_per_sample_cache.items()}
        return {key: value.detach().clone() for key, value in self._diagnostic_cache.items()}

    def _encode(self, dual, head, meta, masks):
        self.core._require_tensor("camera_meta", meta, dual.ndim - 2, 6)
        if tuple(meta.shape[:-1]) != tuple(dual.shape[:-3]) or meta.device != dual.device:
            raise ValueError("P2 B2 camera_meta leading shape/device must match dual D435 observations")
        ages = meta[..., :3]
        validity = meta[..., 3:]
        if bool((ages < 0.0).any().item()) or bool((ages > 1.0).any().item()):
            raise ValueError("P2 B2 camera ages must be normalized to [0,1]")
        if not bool(torch.all((validity == 0.0) | (validity == 1.0)).item()):
            raise ValueError("P2 B2 camera validity flags must be exactly 0 or 1")
        d435_meta_indices = torch.tensor((0, 1, 3, 4), device=meta.device)
        d435_meta = torch.index_select(meta, dim=-1, index=d435_meta_indices)
        self.core._validate_views(dual, d435_meta, masks)
        if not torch.is_tensor(head) or head.ndim != dual.ndim or tuple(head.shape[-3:]) != (136, 384, 3):
            raise ValueError(f"P2 Head image shape must be (136,384,3); got {getattr(head, 'shape', None)}")
        if tuple(head.shape[:-3]) != tuple(dual.shape[:-3]) or head.device != dual.device:
            raise ValueError("P2 Head and D435 image leading shapes/devices must match")
        sequence = dual.ndim == 5
        if sequence:
            batch_size, seq_len = dual.shape[:2]
            head_flat = head.reshape(-1, *head.shape[2:])
            valid = masks.reshape(-1)
            head_flat, meta_flat = head_flat[valid], meta.reshape(-1, 6)[valid]
        else:
            batch_size, seq_len, valid = dual.shape[0], None, None
            head_flat, meta_flat = head, meta
        manipulation = self.core.encode_dual(dual, d435_meta, masks)
        if sequence:
            manipulation_flat = manipulation.reshape(-1, 128)[valid]
        else:
            manipulation_flat = manipulation
        head_input = head_flat.permute(0, 3, 1, 2).contiguous()
        encoded = self.head_vision_module(head_input)
        if not torch.is_tensor(encoded) or tuple(encoded.shape) != (head_input.shape[0], 128):
            raise ValueError("P2 Head encoder output must be [M,128]")
        if encoded.dtype != head_input.dtype or encoded.device != head_input.device or not bool(torch.all(torch.isfinite(encoded)).item()):
            raise ValueError("P2 Head encoder output must preserve finite dtype/device")
        fused = self._fuse_head(manipulation_flat, encoded, meta_flat)
        if not sequence:
            return fused
        output = fused.new_zeros((batch_size * seq_len, 128))
        output[valid] = fused
        return output.reshape(batch_size, seq_len, 128).contiguous()

    def forward(self, obs_dict, masks=None, hidden_states=None, episode_attnmask=None, **kwargs):
        del episode_attnmask, kwargs
        latent = self._encode(obs_dict[self.manipulation_vision_key], obs_dict[self.context_vision_key], obs_dict[self.camera_meta_key], masks)
        return self.core.forward_from_latent(obs_dict[self.input_key], latent, masks, hidden_states)

    def rollout(self, obs_dict, episode_attnmask=None, cur_dones=None, **kwargs):
        self._update_obs_buffer(obs_dict, episode_attnmask, cur_dones)
        del kwargs
        with torch.no_grad():
            mean = self.forward(obs_dict)
        self._distribution_from_mean(mean)
        self._advance_step_once()
        return {"actions": self.distribution.sample(), "action_mean": self.action_mean, "action_sigma": self.action_std}

    def rollout_with_latent(self, obs_dict, episode_attnmask=None, cur_dones=None, **kwargs):
        """Sample an action and return the exact fused latent used for that action."""
        self._update_obs_buffer(obs_dict, episode_attnmask, cur_dones)
        del kwargs
        with torch.no_grad():
            latent = self._encode(
                obs_dict[self.manipulation_vision_key],
                obs_dict[self.context_vision_key],
                obs_dict[self.camera_meta_key],
                masks=None,
            )
            mean = self.core.forward_from_latent(obs_dict[self.input_key], latent)
        self._distribution_from_mean(mean)
        self._advance_step_once()
        return {
            "actions": self.distribution.sample(),
            "action_mean": self.action_mean,
            "action_sigma": self.action_std,
            "latent": latent,
        }

    def act_inference(self, obs_dict, episode_attnmask=None, cur_dones=None, **kwargs):
        self._update_obs_buffer(obs_dict, episode_attnmask, cur_dones)
        del kwargs
        mean = self.forward(obs_dict)
        self._advance_step_once()
        return mean

    def act(self, obs_dict, episode_attnmask=None, masks=None, hidden_states=None, **kwargs):
        mean = self.forward(obs_dict, masks=masks, hidden_states=hidden_states, episode_attnmask=episode_attnmask, **kwargs)
        self._distribution_from_mean(mean)
        return {"actions": self.distribution.sample(), "action_mean": self.action_mean, "action_sigma": self.action_std}

    def update_distribution(self, obs_dict, episode_attnmask=None, last_step_only=False, masks=None, hidden_states=None, **kwargs):
        mean = self.forward(obs_dict, masks=masks, hidden_states=hidden_states, episode_attnmask=episode_attnmask, **kwargs)
        if last_step_only:
            mean = mean[:, -1]
        self._distribution_from_mean(mean)


class DualD435HeadVisionRecurrentToeOut6Actor(DualD435HeadVisionRecurrentActor):
    """B2H Head actor for the standalone toe-out6 four-rank route.

    The tensor/state contract is deliberately inherited byte-for-byte from
    :class:`DualD435HeadVisionRecurrentActor`; only the explicit architecture
    identity differs.  This prevents the new geometry from silently relabeling
    historical TOEIN checkpoints while keeping the shared-encoder and Head
    paths identical.
    """

    architecture_id = P2_B2H_TOEOUT6_ARCHITECTURE


__all__ = [
    "P2_B1_ARCHITECTURE",
    "P2_B2_ARCHITECTURE",
    "P2_B2H_TOEOUT6_ARCHITECTURE",
    "P2_COMMON_INIT_SCHEMA",
    "P2_STEP0_SCHEMA",
    "P2_COMMON_COMPONENTS",
    "P2_COMMON_KEY_SCHEMA",
    "P2_COMMON_KEY_SCHEMA_SHA256",
    "p2_production_state_contract",
    "capture_rng_state",
    "restore_rng_state",
    "rng_state_identity",
    "sha256_file",
    "read_immutable_snapshot",
    "common_core_state",
    "create_common_init_artifact",
    "load_common_init_artifact",
    "write_step0_manifest",
    "DualD435VisionRecurrentActor",
    "DualD435HeadVisionRecurrentActor",
    "DualD435HeadVisionRecurrentToeOut6Actor",
]
