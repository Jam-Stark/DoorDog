# Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0


# Copyright 2025 The HuggingFace Team. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Training script for RL agents using TRL (Transformer Reinforcement Learning).

Supports two training modes:
  - Teacher training: Standard PPO with state-based actor-critic
  - Student training: DAgger-based distillation from a teacher policy into a
    vision-based student policy

Usage:
    # Teacher training
    HYDRA_FULL_ERROR=1 accelerate launch --num_processes 1 groot/rl/train_agent_trl.py \\
        +exp=loco_manip/walk_stand_place_grasp_turn_homie num_envs=48

    # Student training (distillation with vision)
    HYDRA_FULL_ERROR=1 accelerate launch --num_processes 1 groot/rl/train_agent_trl.py \\
        +exp=loco_manip/wsdpt_student_for_teacher_v8q8.002_resnet_rgb_delay num_envs=8 headless=True
"""

import glob
import logging
import os
import random
import re
import subprocess
import sys
import uuid
from pathlib import Path
from collections.abc import Mapping


_A2_GPU_BINDING_MODE = "single-visible-logical-cuda0-v3"
_A2_GPU_BINDING_ENV = "A2_GPU_BINDING_MODE"
_A2_EXPECTED_ENV = (
    "A2_EXPECTED_WORLD_SIZE",
    "A2_EXPECTED_HOST_GPU_INDEX",
    "A2_EXPECTED_LOGICAL_GPU_INDEX",
    "A2_EXPECTED_GPU_UUID",
)
_A2_ACTUAL_DISTRIBUTED_ENV = (
    "WORLD_SIZE",
    "RANK",
    "LOCAL_RANK",
    "LOCAL_WORLD_SIZE",
    "MASTER_ADDR",
    "MASTER_PORT",
)
_A2_ACCELERATE_ENV = ("ACCELERATE_TORCH_DEVICE", "ACCELERATE_BYPASS_DEVICE_MAP")


def _a2_gpu_binding_env_present(values: Mapping[str, str]) -> bool:
    """Return whether the explicit A2 single-visible schema is mentioned."""
    return any(
        isinstance(name, str)
        and (
            name == _A2_GPU_BINDING_ENV
            or name.startswith("A2_GPU_")
            or name.startswith("A2_EXPECTED_")
        )
        for name in values
    )


def _parse_distributed_int(value: object, name: str) -> int:
    if not isinstance(value, str) or re.fullmatch(r"[0-9]+", value) is None:
        raise RuntimeError(f"A2 distributed identity {name} must be decimal digits; got {value!r}")
    return int(value)


def _validate_a2_gpu_binding(env: Mapping[str, str] | None = None):
    """Validate the exact single-visible CUDA0 A2 launch schema before imports."""
    values = os.environ if env is None else env
    unknown_gpu = sorted(
        name
        for name in values
        if isinstance(name, str)
        and name.startswith("A2_GPU_")
        and name != _A2_GPU_BINDING_ENV
    )
    unknown_expected = sorted(
        name
        for name in values
        if isinstance(name, str)
        and name.startswith("A2_EXPECTED_")
        and name not in _A2_EXPECTED_ENV
    )
    if unknown_gpu or unknown_expected:
        raise RuntimeError(
            "A2 GPU binding accepts only the declared single-visible schema; "
            f"unexpected_gpu={unknown_gpu} unexpected_expected={unknown_expected}"
        )
    if not _a2_gpu_binding_env_present(values):
        return None
    if values.get(_A2_GPU_BINDING_ENV) != _A2_GPU_BINDING_MODE:
        raise RuntimeError(
            f"A2 GPU binding requires A2_GPU_BINDING_MODE={_A2_GPU_BINDING_MODE!r}; "
            f"got {values.get(_A2_GPU_BINDING_ENV)!r}"
        )
    required = (_A2_GPU_BINDING_ENV,) + _A2_EXPECTED_ENV
    missing = [name for name in required if name not in values]
    if missing:
        raise RuntimeError(
            "A2 single-visible GPU binding requires the complete schema; "
            f"missing={missing}"
        )
    if values.get("CUDA_DEVICE_ORDER") != "PCI_BUS_ID":
        raise RuntimeError(
            "A2 single-visible GPU binding requires CUDA_DEVICE_ORDER=PCI_BUS_ID; "
            f"got {values.get('CUDA_DEVICE_ORDER')!r}"
        )
    distributed_present = [name for name in _A2_ACTUAL_DISTRIBUTED_ENV if name in values]
    if distributed_present:
        raise RuntimeError(
            "A2 single-visible GPU binding rejects distributed launch variables; "
            f"present={distributed_present}"
        )
    for name in _A2_ACCELERATE_ENV:
        if name in values:
            raise RuntimeError(
                f"A2 GPU binding cannot accept externally supplied {name}; "
                "the launch contract sets it after validation"
            )
    expected_world_size = _parse_distributed_int(
        values["A2_EXPECTED_WORLD_SIZE"], "A2_EXPECTED_WORLD_SIZE"
    )
    host_gpu_index = _parse_distributed_int(
        values["A2_EXPECTED_HOST_GPU_INDEX"], "A2_EXPECTED_HOST_GPU_INDEX"
    )
    logical_gpu_index = _parse_distributed_int(
        values["A2_EXPECTED_LOGICAL_GPU_INDEX"], "A2_EXPECTED_LOGICAL_GPU_INDEX"
    )
    expected_uuid = values["A2_EXPECTED_GPU_UUID"]
    if expected_world_size != 1:
        raise RuntimeError(
            "A2 single-visible GPU binding requires A2_EXPECTED_WORLD_SIZE=1; "
            f"got {expected_world_size}"
        )
    if values.get("CUDA_VISIBLE_DEVICES") != str(host_gpu_index):
        raise RuntimeError(
            "A2 single-visible GPU binding requires CUDA_VISIBLE_DEVICES to equal "
            "A2_EXPECTED_HOST_GPU_INDEX exactly; "
            f"visible={values.get('CUDA_VISIBLE_DEVICES')!r} host={host_gpu_index}"
        )
    if logical_gpu_index != 0:
        raise RuntimeError(
            "A2 single-visible GPU binding requires A2_EXPECTED_LOGICAL_GPU_INDEX=0; "
            f"got {logical_gpu_index}"
        )
    if re.fullmatch(
        r"GPU-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        expected_uuid,
    ) is None:
        raise RuntimeError(
            "A2 single-visible GPU binding requires a canonical A2_EXPECTED_GPU_UUID; "
            f"got {expected_uuid!r}"
        )
    identity = {
        "mode": _A2_GPU_BINDING_MODE,
        "world_size": 1,
        "rank": 0,
        "local_rank": 0,
        "host_gpu_index": host_gpu_index,
        "logical_gpu_index": logical_gpu_index,
        "pinned_uuid": expected_uuid,
    }
    print(
        "[A2_GPU_BINDING_ENV] "
        f"mode={_A2_GPU_BINDING_MODE} CVD={host_gpu_index} host_gpu_index={host_gpu_index} "
        f"logical_gpu_index={logical_gpu_index} pinned_uuid={expected_uuid} world_size=1",
        flush=True,
    )
    return identity


def _query_nvidia_smi_gpu_uuids() -> dict[int, str]:
    """Read the host GPU index/UUID table with a strict non-shell command."""
    result = subprocess.run(
        [
            "/usr/bin/nvidia-smi",
            "--query-gpu=index,uuid",
            "--format=csv,noheader,nounits",
        ],
        check=True,
        capture_output=True,
        text=True,
        shell=False,
    )
    if result.stderr:
        raise RuntimeError(f"nvidia-smi UUID query wrote unexpected stderr: {result.stderr!r}")
    records: dict[int, str] = {}
    lines = result.stdout.splitlines()
    if not lines:
        raise RuntimeError("nvidia-smi UUID query returned no GPU records")
    for line in lines:
        fields = [field.strip() for field in line.split(",")]
        if len(fields) != 2 or re.fullmatch(r"[0-9]+", fields[0]) is None:
            raise RuntimeError(f"nvidia-smi UUID query returned malformed row: {line!r}")
        index = int(fields[0])
        uuid = fields[1]
        if not re.fullmatch(r"GPU-[0-9a-f-]+", uuid) or index in records:
            raise RuntimeError(f"nvidia-smi UUID query returned malformed/duplicate row: {line!r}")
        records[index] = uuid
    return records


def _validate_a2_nvidia_smi_uuid(identity: Mapping[str, object]) -> None:
    records = _query_nvidia_smi_gpu_uuids()
    host_gpu_index = int(identity["host_gpu_index"])
    expected_uuid = str(identity["pinned_uuid"])
    observed_uuid = records.get(host_gpu_index)
    if observed_uuid != expected_uuid:
        raise RuntimeError(
            "A2 GPU binding nvidia-smi UUID mismatch; "
            f"host_gpu_index={host_gpu_index} expected={expected_uuid!r} observed={observed_uuid!r}"
        )


def _canonicalize_a2_cuda_uuid(value: object) -> str:
    """Convert Torch's CUDA UUID binding to the canonical nvidia-smi form."""
    try:
        raw_value = getattr(value, "bytes")
    except AttributeError as exc:
        raise RuntimeError("A2 CUDA UUID binding must expose a .bytes payload") from exc
    except Exception as exc:
        raise RuntimeError("A2 CUDA UUID .bytes payload could not be read") from exc
    if isinstance(raw_value, (str, int, float, complex, bool)):
        raise RuntimeError("A2 CUDA UUID .bytes payload must be a byte sequence")
    try:
        raw_bytes = bytes(raw_value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise RuntimeError("A2 CUDA UUID .bytes payload is not bytes-convertible") from exc
    if len(raw_bytes) != 16:
        raise RuntimeError(
            "A2 CUDA UUID .bytes payload must contain exactly 16 bytes; "
            f"got {len(raw_bytes)}"
        )
    try:
        canonical_uuid = str(uuid.UUID(bytes=raw_bytes))
    except (TypeError, ValueError) as exc:
        raise RuntimeError("A2 CUDA UUID .bytes payload is not a valid UUID") from exc
    return f"GPU-{canonical_uuid}"


def _prepare_a2_torch_device(identity: Mapping[str, object]):
    """Bind the single visible process to logical CUDA0 after host UUID validation."""
    import torch

    host_gpu_index = int(identity["host_gpu_index"])
    logical_gpu_index = int(identity["logical_gpu_index"])
    expected_uuid = str(identity["pinned_uuid"])
    if logical_gpu_index != 0:
        raise RuntimeError(
            "A2 single-visible binding requires logical_gpu_index=0; "
            f"got host={host_gpu_index} logical={logical_gpu_index}"
        )
    device_count = torch.cuda.device_count()
    if device_count != 1:
        raise RuntimeError(
            "A2 single-visible GPU binding requires exactly one visible CUDA device; "
            f"got device_count={device_count}"
        )
    torch.cuda.set_device(logical_gpu_index)
    current_device = torch.cuda.current_device()
    if current_device != logical_gpu_index:
        raise RuntimeError(
            "A2 single-visible GPU binding logical CUDA device mismatch; "
            f"expected={logical_gpu_index} actual={current_device}"
        )
    properties = torch.cuda.get_device_properties(logical_gpu_index)
    observed_uuid = _canonicalize_a2_cuda_uuid(getattr(properties, "uuid", None))
    if observed_uuid != expected_uuid:
        raise RuntimeError(
            "A2 single-visible GPU binding Torch UUID mismatch; "
            f"host_gpu_index={host_gpu_index} expected={expected_uuid!r} observed={observed_uuid!r}"
        )
    if os.environ.get("ACCELERATE_TORCH_DEVICE") is not None:
        raise RuntimeError("A2 GPU binding cannot overwrite ACCELERATE_TORCH_DEVICE")
    if os.environ.get("ACCELERATE_BYPASS_DEVICE_MAP") is not None:
        raise RuntimeError("A2 GPU binding cannot overwrite ACCELERATE_BYPASS_DEVICE_MAP")
    os.environ["ACCELERATE_TORCH_DEVICE"] = "cuda:0"
    os.environ["ACCELERATE_BYPASS_DEVICE_MAP"] = "true"
    print(
        "[A2_GPU_BINDING_TORCH] "
        f"mode={identity['mode']} CVD={host_gpu_index} host_gpu_index={host_gpu_index} "
        f"logical_gpu_index={logical_gpu_index} pinned_uuid={expected_uuid} "
        "world_size=1 ACCELERATE_TORCH_DEVICE=cuda:0 "
        "ACCELERATE_BYPASS_DEVICE_MAP=true",
        flush=True,
    )
    return torch.device("cuda", logical_gpu_index)


def _validate_a2_preinitialized_accelerate_state(identity: Mapping[str, object]) -> None:
    """Reject any pre-existing Accelerate singleton state before A2 config parsing."""
    del identity
    from accelerate.state import AcceleratorState, PartialState

    for state_type in (AcceleratorState, PartialState):
        shared_state = getattr(state_type, "_shared_state", {})
        if shared_state:
            raise RuntimeError(
                "A2 GPU binding rejects preinitialized Accelerate shared state; "
                f"state_type={state_type.__name__}"
            )


_A2_GPU_BINDING_BARRIER_EMITTED = False


def _a2_wait_for_everyone(accelerator, identity) -> None:
    """Validate the single-rank A2 boundary; never enter a distributed barrier."""
    if identity is None:
        accelerator.wait_for_everyone()
        return
    import torch

    if int(identity["world_size"]) != 1:
        raise RuntimeError("A2 single-visible binding supports only world_size=1")
    if accelerator.num_processes != 1 or accelerator.process_index != 0:
        raise RuntimeError(
            "A2 single-visible binding requires one Accelerator process at rank 0; "
            f"got world_size={accelerator.num_processes} rank={accelerator.process_index}"
        )
    if torch.device(accelerator.device) != torch.device("cuda:0"):
        raise RuntimeError(
            "A2 single-visible binding Accelerator device must be cuda:0; "
            f"got {accelerator.device}"
        )
    if torch.cuda.current_device() != 0:
        raise RuntimeError(
            "A2 single-visible binding current logical CUDA device must be 0; "
            f"got {torch.cuda.current_device()}"
        )
    if torch.distributed.is_available() and torch.distributed.is_initialized():
        raise RuntimeError("A2 single-visible binding must not initialize torch.distributed")
    global _A2_GPU_BINDING_BARRIER_EMITTED
    if not _A2_GPU_BINDING_BARRIER_EMITTED:
        print(
            "[A2_GPU_BINDING_BARRIER] "
            f"mode={identity['mode']} CVD={identity['host_gpu_index']} "
            f"host_gpu_index={identity['host_gpu_index']} "
            f"logical_gpu_index={identity['logical_gpu_index']} "
            f"pinned_uuid={identity['pinned_uuid']} world_size=1 kind=validated-noop",
            flush=True,
        )
        _A2_GPU_BINDING_BARRIER_EMITTED = True


def _validate_a2_ppo_config(training_args, identity: Mapping[str, object]) -> None:
    """Validate standard Transformers/Accelerate PPOConfig after logical CUDA0 binding."""
    import torch
    from accelerate.state import DistributedType
    from transformers.training_args import ParallelMode

    expected_device = torch.device("cuda:0")
    state = getattr(training_args, "distributed_state", None)
    if state is None:
        raise RuntimeError("A2 single-visible PPOConfig must expose PartialState")
    if torch.device(state.device) != expected_device:
        raise RuntimeError(
            "A2 single-visible PPOConfig PartialState device mismatch; "
            f"expected={expected_device} actual={state.device}"
        )
    if state.distributed_type is not DistributedType.NO or state.backend is not None:
        raise RuntimeError(
            "A2 single-visible PPOConfig must use DistributedType.NO with backend=None; "
            f"type={state.distributed_type} backend={state.backend!r}"
        )
    if (
        int(state.num_processes) != 1
        or int(state.process_index) != 0
        or int(state.local_process_index) != 0
    ):
        raise RuntimeError(
            "A2 single-visible PPOConfig PartialState must be world/rank/local 1/0/0; "
            f"got {state.num_processes}/{state.process_index}/{state.local_process_index}"
        )
    if torch.cuda.current_device() != 0:
        raise RuntimeError(
            "A2 single-visible PPOConfig current logical CUDA device must be 0; "
            f"got {torch.cuda.current_device()}"
        )
    if torch.device(training_args.device) != expected_device:
        raise RuntimeError(
            "A2 single-visible PPOConfig device mismatch; "
            f"expected={expected_device} actual={training_args.device}"
        )
    if int(training_args.local_rank) != 0:
        raise RuntimeError(
            "A2 single-visible PPOConfig local_rank must be 0; "
            f"got {training_args.local_rank}"
        )
    if int(training_args._n_gpu) != 1:
        raise RuntimeError(
            "A2 single-visible PPOConfig must expose exactly one visible GPU; "
            f"got {training_args._n_gpu}"
        )
    if training_args.parallel_mode is not ParallelMode.NOT_PARALLEL:
        raise RuntimeError(
            "A2 single-visible PPOConfig must be NOT_PARALLEL; "
            f"got {training_args.parallel_mode}"
        )
    if getattr(training_args, "world_size", None) not in (None, 1):
        raise RuntimeError(
            "A2 single-visible PPOConfig world_size must be unset or 1; "
            f"got {training_args.world_size}"
        )
    training_args.world_size = 1
    print(
        "[A2_PPO_CONFIG_BINDING] "
        f"mode={identity['mode']} CVD={identity['host_gpu_index']} "
        f"host_gpu_index={identity['host_gpu_index']} "
        f"logical_gpu_index={identity['logical_gpu_index']} UUID={identity['pinned_uuid']} "
        "world_size=1 distributed_type=NO backend=None parallel_mode=NOT_PARALLEL",
        flush=True,
    )


def _validate_a2_accelerator_binding(accelerator, identity: Mapping[str, object]) -> None:
    import torch
    from accelerate.state import DistributedType

    expected_device = torch.device("cuda:0")
    state = getattr(accelerator, "state", None)
    if int(identity["world_size"]) != 1:
        raise RuntimeError("A2 single-visible Accelerator identity must have world_size=1")
    if accelerator.num_processes != 1 or accelerator.process_index != 0:
        raise RuntimeError(
            "A2 single-visible Accelerator must be one process at rank 0; "
            f"got world_size={accelerator.num_processes} rank={accelerator.process_index}"
        )
    if state is None or state.distributed_type is not DistributedType.NO or state.backend is not None:
        raise RuntimeError(
            "A2 single-visible Accelerator must use DistributedType.NO with backend=None"
        )
    if torch.device(accelerator.device) != expected_device:
        raise RuntimeError(
            "A2 single-visible Accelerator device mismatch; "
            f"expected={expected_device} actual={accelerator.device}"
        )
    if torch.cuda.current_device() != 0:
        raise RuntimeError(
            "A2 single-visible Accelerator current logical CUDA device mismatch; "
            f"expected=0 actual={torch.cuda.current_device()}"
        )
    if torch.distributed.is_available() and torch.distributed.is_initialized():
        raise RuntimeError("A2 single-visible Accelerator must not initialize torch.distributed")
    print(
        "[A2_ACCELERATOR_BINDING] "
        f"mode={identity['mode']} CVD={identity['host_gpu_index']} "
        f"host_gpu_index={identity['host_gpu_index']} "
        f"logical_gpu_index={identity['logical_gpu_index']} UUID={identity['pinned_uuid']} "
        "world_size=1 distributed_type=NO",
        flush=True,
    )


def _seed_a2_local_generators(seed: int) -> int:
    """Seed CPU's default generator and only the already-selected CUDA device."""
    import torch

    torch.default_generator.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    return seed

_A2_KIT_BINDING_EMITTED = False
_A2_CARBONITE_SETTING_SPECS = (
    ("/renderer/activeGpu", int, "get_as_int"),
    ("/physics/cudaDevice", int, "get_as_int"),
    ("/renderer/multiGpu/enabled", bool, "get_as_bool"),
    ("/renderer/multiGpu/autoEnable", bool, "get_as_bool"),
    ("/renderer/multiGpu/maxGpuCount", int, "get_as_int"),
)


def _read_a2_carbonite_settings(settings) -> dict[str, object]:
    """Require present exact Python types before typed Carbonite reads."""
    values = {}
    for path, expected_type, getter_name in _A2_CARBONITE_SETTING_SPECS:
        raw_value = settings.get(path)
        if raw_value is None:
            raise RuntimeError(
                "A2 single-visible Kit setting is missing; "
                f"path={path!r}"
            )
        if type(raw_value) is not expected_type:
            raise RuntimeError(
                "A2 single-visible Kit setting has the wrong Python type; "
                f"path={path!r} expected={expected_type.__name__} "
                f"actual={type(raw_value).__name__}"
            )
        try:
            typed_getter = getattr(settings, getter_name)
            typed_value = typed_getter(path)
        except Exception as exc:
            raise RuntimeError(
                "A2 single-visible Kit typed setting read failed; "
                f"path={path!r} getter={getter_name!r}"
            ) from exc
        if type(typed_value) is not expected_type:
            raise RuntimeError(
                "A2 single-visible Kit typed setting has the wrong Python type; "
                f"path={path!r} expected={expected_type.__name__} "
                f"actual={type(typed_value).__name__}"
            )
        values[path] = typed_value
    return values


def _make_a2_bound_app_launcher_type(app_launcher_type, identity: Mapping[str, object]):
    """Bind Kit rendering to the host GPU while CUDA/PhysX stay on logical cuda:0."""
    host_gpu_index = int(identity["host_gpu_index"])
    logical_gpu_index = int(identity["logical_gpu_index"])
    if logical_gpu_index != 0:
        raise RuntimeError(
            "A2 AppLauncher binding requires logical_gpu_index=0; "
            f"got {logical_gpu_index}"
        )

    class _A2BoundAppLauncher(app_launcher_type):
        def _resolve_device_settings(self, launcher_args):
            super()._resolve_device_settings(launcher_args)
            if self.device_id != logical_gpu_index:
                raise RuntimeError(
                    "A2 AppLauncher resolved an unexpected logical device; "
                    f"expected={logical_gpu_index} actual={self.device_id}"
                )
            launcher_args["active_gpu"] = host_gpu_index
            launcher_args["physics_gpu"] = logical_gpu_index
            print(
                "[A2_GPU_BINDING_APP_CONFIG] "
                f"CVD={host_gpu_index} host_renderer_gpu={host_gpu_index} "
                f"logical_cuda_gpu={logical_gpu_index} physics_cuda_gpu={logical_gpu_index}",
                flush=True,
            )

    return _A2BoundAppLauncher


def _validate_a2_app_launcher_binding(app_launcher, accelerator, identity: Mapping[str, object]) -> None:
    import carb

    host_gpu_index = int(identity["host_gpu_index"])
    logical_gpu_index = int(identity["logical_gpu_index"])
    if logical_gpu_index != 0:
        raise RuntimeError("A2 single-visible AppLauncher logical identity must be 0")
    if app_launcher.device_id != logical_gpu_index:
        raise RuntimeError(
            "A2 single-visible AppLauncher device must be cuda:0; "
            f"got {app_launcher.device_id}"
        )
    accelerator_device = getattr(accelerator, "device", None)
    if accelerator_device is None or str(accelerator_device) != "cuda:0":
        raise RuntimeError(
            "A2 single-visible AppLauncher Accelerator device must be cuda:0; "
            f"got {accelerator_device}"
        )
    settings = carb.settings.get_settings()
    setting_values = _read_a2_carbonite_settings(settings)
    active_gpu = setting_values["/renderer/activeGpu"]
    physics_gpu = setting_values["/physics/cudaDevice"]
    multi_gpu_enabled = setting_values["/renderer/multiGpu/enabled"]
    multi_gpu_auto = setting_values["/renderer/multiGpu/autoEnable"]
    max_gpu_count = setting_values["/renderer/multiGpu/maxGpuCount"]
    if active_gpu != host_gpu_index or physics_gpu != logical_gpu_index:
        raise RuntimeError(
            "A2 single-visible Kit GPU settings must bind the physical renderer and "
            "logical CUDA physics devices exactly; "
            f"expected_active={host_gpu_index} actual_active={active_gpu} "
            f"expected_physics={logical_gpu_index} actual_physics={physics_gpu}"
        )
    if multi_gpu_enabled or multi_gpu_auto or max_gpu_count != 1:
        raise RuntimeError(
            "A2 single-visible Kit renderer must disable multi-GPU with maxGpuCount=1; "
            f"enabled={multi_gpu_enabled} autoEnable={multi_gpu_auto} maxGpuCount={max_gpu_count}"
        )
    global _A2_KIT_BINDING_EMITTED
    if not _A2_KIT_BINDING_EMITTED:
        print(
            "[A2_GPU_BINDING_KIT] "
            f"mode={identity['mode']} CVD={host_gpu_index} host_gpu_index={host_gpu_index} "
            f"logical_gpu_index={identity['logical_gpu_index']} UUID={identity['pinned_uuid']} "
            "world_size=1 renderer_multi_gpu_enabled=false renderer_multi_gpu_autoEnable=false "
            f"renderer_multi_gpu_maxGpuCount=1 kit_active_gpu={host_gpu_index} "
            f"kit_physics_gpu={logical_gpu_index}",
            flush=True,
        )
        _A2_KIT_BINDING_EMITTED = True


def _validate_distributed_identity(env: Mapping[str, str] | None = None):
    """Compatibility alias retained for callers while routing to the A2 contract."""
    return _validate_a2_gpu_binding(env)


A2_GPU_BINDING = _validate_a2_gpu_binding()
if A2_GPU_BINDING is not None:
    _validate_a2_nvidia_smi_uuid(A2_GPU_BINDING)
    _prepare_a2_torch_device(A2_GPU_BINDING)
    _validate_a2_preinitialized_accelerate_state(A2_GPU_BINDING)


import gr00t


def _verify_source_identity() -> Path:
    """Fail fast when the imported package is not this entry module's checkout."""
    entry_file = Path(__file__).resolve(strict=True)
    repository_root = entry_file.parents[2]
    package_file = getattr(gr00t, "__file__", None)
    if not isinstance(package_file, str) or not package_file:
        raise RuntimeError(
            "A2 source identity cannot be verified: imported gr00t has no concrete __file__."
        )
    imported_root = Path(package_file).resolve(strict=True).parent.parent
    if imported_root != repository_root:
        raise RuntimeError(
            "A2 source identity mismatch: "
            f"entry repository root={repository_root}, imported gr00t root={imported_root}."
        )
    print(f"[A2_SOURCE_IDENTITY] source_root={repository_root}", flush=True)
    return repository_root


SOURCE_ROOT = _verify_source_identity()


def _headless_rendering_experience_path() -> Path:
    """Return the required in-checkout headless camera experience file."""
    source_file = SOURCE_ROOT / "gr00t/rl/apps/phc.isaaclab.python.headless.rendering.kit"
    if not source_file.is_file():
        raise FileNotFoundError(
            "A2 headless camera experience file is missing from the source checkout: "
            f"{source_file}"
        )
    return source_file


def _close_simulation_app(simulation_app, render_results) -> None:
    """Close SimulationApp with render-aware Replicator drain semantics."""
    if type(render_results) is not bool:
        raise TypeError(
            "A2 SimulationApp close requires simulator.config.render_results "
            f"to be an exact bool; got {type(render_results).__name__}: {render_results!r}"
        )
    render_results_text = str(render_results).lower()
    wait_for_replicator_text = render_results_text
    print(
        "[A2_LIFECYCLE] simulation_app_close_start "
        f"render_results={render_results_text} "
        f"wait_for_replicator={wait_for_replicator_text}",
        flush=True,
    )
    if render_results:
        simulation_app.close()
    else:
        simulation_app.close(wait_for_replicator=False)
    print(
        "[A2_LIFECYCLE] simulation_app_close_complete "
        f"render_results={render_results_text} "
        f"wait_for_replicator={wait_for_replicator_text}",
        flush=True,
    )


import hydra
import numpy as np
import yaml
from hydra.core.hydra_config import HydraConfig
from hydra.utils import instantiate
from loguru import logger
from omegaconf import OmegaConf

from gr00t.rl.utils.config_utils import register_rl_resolvers

register_rl_resolvers()


def save_training_config_snapshots(config, experiment_save_dir, unresolved_conf=None):
    """Persist unresolved compatibility config and a fully resolved training config."""
    experiment_save_dir = Path(experiment_save_dir)
    if unresolved_conf is None:
        unresolved_conf = OmegaConf.to_container(config, resolve=False)
    # Resolve explicitly here; interpolation failures must propagate before training starts.
    OmegaConf.to_container(config, resolve=True)
    unresolved_path = experiment_save_dir / "config.yaml"
    resolved_path = experiment_save_dir / "resolved_config.yaml"
    OmegaConf.save(unresolved_conf, unresolved_path, resolve=False)
    OmegaConf.save(config, resolved_path, resolve=True)
    return unresolved_path, resolved_path


_A2_BASE_API_TRAINER_TARGET = (
    "gr00t.rl.trl.trainer.ppo_trainer_a2_base_api.TRLPPOTrainer"
)
_A2_GPU_BINDING_TRAINER_TARGETS = frozenset(
    (
        _A2_BASE_API_TRAINER_TARGET,
        "gr00t.rl.trl.trainer.distill_trainer_a2_base_api.TRLDistillTrainerA2BaseAPI",
    )
)
_CHECKPOINT_LOAD_MODES = frozenset(("full", "policy_only"))


def _validate_training_checkpoint_load_config(config):
    checkpoint_load_mode = config.checkpoint_load_mode
    if not isinstance(checkpoint_load_mode, str) or checkpoint_load_mode not in (
        _CHECKPOINT_LOAD_MODES
    ):
        raise ValueError(
            "checkpoint_load_mode must be exactly one of "
            f"{sorted(_CHECKPOINT_LOAD_MODES)}; got {checkpoint_load_mode!r}."
        )

    trainer_target = config.trainer["_target_"]
    if checkpoint_load_mode == "policy_only":
        if not config.checkpoint:
            raise ValueError(
                "checkpoint_load_mode='policy_only' requires a non-empty checkpoint path."
            )
        if trainer_target != _A2_BASE_API_TRAINER_TARGET:
            raise ValueError(
                "checkpoint_load_mode='policy_only' is only implemented by "
                f"{_A2_BASE_API_TRAINER_TARGET}; got trainer target {trainer_target!r}."
            )
    return checkpoint_load_mode, trainer_target


def seeding(seed=0, torch_deterministic=False):
    """Set random seeds for reproducibility across all libraries."""
    import torch

    print(f"Setting seed: {seed}")
    random.seed(seed)
    np.random.seed(seed)
    if A2_GPU_BINDING is None:
        torch.manual_seed(seed)
        torch.cuda.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
    else:
        _seed_a2_local_generators(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)

    if torch_deterministic:
        os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
        torch.backends.cudnn.benchmark = False
        torch.backends.cudnn.deterministic = True
        torch.use_deterministic_algorithms(True)
    else:
        torch.backends.cudnn.benchmark = True
        torch.backends.cudnn.deterministic = False

    return seed


def resume_training(config):
    """Find the latest checkpoint and update config for training resumption."""
    if config.get("checkpoint", None) is not None:
        last_existing_checkpoint = config.checkpoint
    else:
        experiment_dir_base = os.path.join(
            config.base_dir, config.project_name, config.experiment_name
        )
        last_existing_checkpoint = sorted(
            glob.glob(os.path.join(f"{experiment_dir_base}-*", "last.pt"))
        )[-1]
    experiment_dir = os.path.dirname(last_existing_checkpoint)
    config.experiment_dir = experiment_dir
    config.checkpoint = last_existing_checkpoint
    print(f"Resuming training from {last_existing_checkpoint}")


def auto_calculate_vision_feature_dim(config):
    """Auto-calculate vision_feature_dim based on history_length and temporal aggregation mode.

    For concatenation mode: vision_feature_dim = base_vision_feature_dim * history_length
    For attention mode: vision_feature_dim = base_vision_feature_dim
    """
    if not (hasattr(config, "history_length") and hasattr(config, "base_vision_feature_dim")):
        return

    use_attention = config.algo.config.get("actor", {}).get("use_temporal_attention", False)

    if not use_attention:
        calculated_dim = config.base_vision_feature_dim * config.history_length
    else:
        calculated_dim = config.base_vision_feature_dim

    if not hasattr(config, "vision_feature_dim") or config.vision_feature_dim == -1:
        config.vision_feature_dim = calculated_dim
        mode = "concatenation" if not use_attention else "attention"
        logger.info(
            f"Auto-calculated vision_feature_dim for {mode} mode: "
            f"{config.base_vision_feature_dim} * "
            f"{config.history_length if not use_attention else 1} = {calculated_dim}"
        )


def process_output_dim_in_config(config):
    """Process and adapt output dimensions for actor/teacher_actor backbones.

    When output_dim is set to -1, auto-calculates from homie command keys.
    """

    def calculate_homie_output_dim():
        output_dim = 0
        for key in config.obs["homie_command_keys"].keys():
            output_dim += len(config.obs["homie_command_default"][key])
        return output_dim

    def adapt_backbone_output_dim(backbone_config, config_name=""):
        try:
            if hasattr(backbone_config, "module_config_dict"):
                if backbone_config.module_config_dict.output_dim[0] == -1:
                    output_dim = calculate_homie_output_dim()
                    backbone_config.module_config_dict.output_dim = [output_dim]
                    return True
            elif hasattr(backbone_config, "mlp_module") and hasattr(
                backbone_config.mlp_module, "module_config_dict"
            ):
                if backbone_config.mlp_module.module_config_dict.output_dim[0] == -1:
                    output_dim = calculate_homie_output_dim()
                    backbone_config.mlp_module.module_config_dict.output_dim = [output_dim]
                    return True
        except (AttributeError, IndexError) as e:
            logger.warning(f"Could not adapt {config_name} backbone output_dim: {e}")
        return False

    if (
        config.algo.config.get("use_new_actor_critic", False)
        and hasattr(config.algo.config, "actor")
        and hasattr(config.algo.config.actor, "backbone")
    ):
        adapt_backbone_output_dim(config.algo.config.actor.backbone, "actor")
        if (
            getattr(config.algo.config, "use_dagger", False)
            and hasattr(config.algo.config, "teacher_actor")
            and hasattr(config.algo.config.teacher_actor, "backbone")
        ):
            adapt_backbone_output_dim(config.algo.config.teacher_actor.backbone, "teacher_actor")


def patch_app_launcher_toolbar_hiding(AppLauncher: type) -> None:
    """Skip optional toolbar hiding when the selected Kit omits the toolbar widget."""
    if getattr(AppLauncher, "_a2_piper_toolbar_hiding_patch_applied", False):
        return

    missing_module = "omni.kit.widget.toolbar"

    def make_wrapper(method_name: str, original_method):
        def wrapped(self, *args, **kwargs):
            try:
                return original_method(self, *args, **kwargs)
            except ModuleNotFoundError as exc:
                if exc.name != missing_module:
                    raise
                print(
                    "[WARN]: IsaacLab AppLauncher "
                    f"`{method_name}` skipped because `{missing_module}` is unavailable "
                    "in this Kit runtime.",
                    file=sys.stderr,
                    flush=True,
                )
                return None

        return wrapped

    for method_name in ("_hide_stop_button", "_hide_play_button"):
        original_method = getattr(AppLauncher, method_name, None)
        if original_method is not None:
            setattr(AppLauncher, method_name, make_wrapper(method_name, original_method))
    setattr(AppLauncher, "_a2_piper_toolbar_hiding_patch_applied", True)


@hydra.main(config_path="config", config_name="base", version_base="1.1")
def main(config: OmegaConf):
    # Auto-calculate vision_feature_dim for history-based vision models
    auto_calculate_vision_feature_dim(config)
    checkpoint_load_mode, trainer_target = _validate_training_checkpoint_load_config(config)

    from transformers import HfArgumentParser
    from trl import ModelConfig, PPOConfig, ScriptArguments

    parser = HfArgumentParser((ScriptArguments, PPOConfig, ModelConfig))
    config.algo.trl.output_dir = str(Path(config.experiment_dir))
    script_args, training_args, model_args = parser.parse_dict(config.algo.trl)
    if A2_GPU_BINDING is not None:
        _validate_a2_ppo_config(training_args, A2_GPU_BINDING)

    from datetime import timedelta

    from accelerate import Accelerator, DistributedDataParallelKwargs, InitProcessGroupKwargs

    # --- Distributed training setup ---
    kwargs = InitProcessGroupKwargs(timeout=timedelta(seconds=6000))
    if A2_GPU_BINDING is None:
        ddp_kwargs = DistributedDataParallelKwargs(find_unused_parameters=False)
        accelerator = Accelerator(
            gradient_accumulation_steps=training_args.gradient_accumulation_steps,
            kwargs_handlers=[ddp_kwargs, kwargs],
        )
    else:
        accelerator = Accelerator(
            gradient_accumulation_steps=training_args.gradient_accumulation_steps,
            kwargs_handlers=[kwargs],
        )
    if A2_GPU_BINDING is not None:
        _validate_a2_accelerator_binding(accelerator, A2_GPU_BINDING)

    device = "cuda:0" if A2_GPU_BINDING is not None else str(accelerator.device)
    if device == "cuda":
        device = "cuda:0"
    config.multi_gpu = accelerator.num_processes > 1
    if config.multi_gpu:
        config.global_rank = accelerator.process_index
        config.seed += accelerator.process_index
        config.algo.config.global_rank = accelerator.process_index
        config.algo.config.world_size = accelerator.num_processes
    seeding(config.seed)

    # Resume wandb run if meta.yaml exists from a previous run
    meta_path = Path(config.experiment_dir) / "meta.yaml"
    if meta_path.exists():
        meta = yaml.safe_load(open(meta_path, "r"))
        config.wandb.wandb_id = meta["wandb_run"]
        print(f"resume wandb from run: {config.wandb.wandb_id}")

    # --- Isaac Sim setup ---
    simulator_type = config.simulator["_target_"].split(".")[-1]
    if simulator_type == "IsaacSim":
        try:
            with open("./rl/simulator/isaacsim/.isaacsim_version", "r", encoding="utf-8") as f:
                DEFAULT_ISAACSIM_VERSION = f.read().strip()
        except FileNotFoundError:
            DEFAULT_ISAACSIM_VERSION = "4.5"

        if DEFAULT_ISAACSIM_VERSION == "4.5":
            from isaaclab.app import AppLauncher
        elif DEFAULT_ISAACSIM_VERSION == "4.2":
            logger.warning("Using IsaacSim 4.2")
            from omni.isaac.lab.app import AppLauncher

        import argparse

        import isaaclab

        parser = argparse.ArgumentParser(description="Train an RL agent with TRL.")
        AppLauncher.add_app_launcher_args(parser)
        patch_app_launcher_toolbar_hiding(AppLauncher)
        app_launcher_type = AppLauncher
        if A2_GPU_BINDING is not None:
            app_launcher_type = _make_a2_bound_app_launcher_type(
                AppLauncher, A2_GPU_BINDING
            )

        args_cli, hydra_args = parser.parse_known_args()
        sys.argv = [sys.argv[0]] + hydra_args
        args_cli.num_envs = config.num_envs
        args_cli.seed = config.seed
        args_cli.env_spacing = config.env.config.env_spacing
        args_cli.output_dir = config.output_dir
        args_cli.enable_cameras = (
            config.simulator.config.cameras.enable_cameras or config.simulator.config.render_results
        )
        args_cli.headless = config.headless
        if A2_GPU_BINDING is not None:
            args_cli.multi_gpu = False
            args_cli.distributed = False
            args_cli.device = "cuda:0"
        else:
            args_cli.multi_gpu = config.multi_gpu
            args_cli.distributed = config.multi_gpu
            args_cli.device = device

        # Point AppLauncher at the immutable kit shipped by this source checkout.
        if args_cli.enable_cameras and args_cli.headless:
            args_cli.experience = str(_headless_rendering_experience_path())

        app_launcher = app_launcher_type(args_cli)
        simulation_app = app_launcher.app
        if A2_GPU_BINDING is not None:
            _validate_a2_app_launcher_binding(app_launcher, accelerator, A2_GPU_BINDING)

    # --- Imports that must come after Isaac Sim initialization ---
    import wandb

    from gr00t.rl.agents.base_algo.base_algo import BaseAlgo  # noqa: E402, F401
    from gr00t.rl.agents.modules.ppo_modules import (
        PPOCritic,
        PPOStateActor,
        PPOStateActorFixSigma,
        PPOVisionStateActorFixSigma,
        PPOVisionStateActorWithTransformFixSigma,
    )
    from gr00t.rl.envs.base_task.base_task import BaseTask  # noqa: E402, F401
    from gr00t.rl.trl.utils.common import custom_instantiate, wandb_run_exists
    from gr00t.rl.utils.helpers import pre_process_config
    from gr00t.rl.utils.logging import HydraLoggerBridge

    # --- Logging setup ---
    hydra_log_path = os.path.join(HydraConfig.get().runtime.output_dir, "train.log")
    logger.remove()
    logger.add(hydra_log_path, level="DEBUG")
    console_log_level = os.environ.get("LOGURU_LEVEL", "INFO").upper()
    logger.add(sys.stdout, level=console_log_level, colorize=True)
    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger().addHandler(HydraLoggerBridge())

    # --- Wandb setup ---
    # resolve=False preserves interpolations for inference-time overrides
    unresolved_conf = OmegaConf.to_container(config, resolve=False)
    os.chdir(hydra.utils.get_original_cwd())

    if config.use_wandb and accelerator.is_main_process:
        project_name = f"{config.project_name}"
        run_name = config.experiment_dir.replace(f"{config.base_dir}/{project_name}/", "")
        wandb_dir = Path(config.wandb.wandb_dir)
        wandb_dir.mkdir(exist_ok=True, parents=True)
        wandb_group = None if config.wandb.wandb_id is not None else config.wandb.wandb_group
        logger.info(f"Saving wandb logs to {wandb_dir}")
        wandb.init(
            project=project_name,
            entity=config.wandb.wandb_entity,
            name=run_name,
            sync_tensorboard=True,
            config=unresolved_conf,
            dir=wandb_dir,
            id=config.wandb.wandb_id,
            group=wandb_group,
            resume="allow",
        )

    pre_process_config(config)

    # --- Initialize environment ---
    config.env.config.save_rendering_dir = str(Path(config.experiment_dir) / "renderings_training")
    config.env.config.experiment_dir = str(Path(config.experiment_dir))
    env = custom_instantiate(config.env, device=device, _resolve=False)

    # --- Build policy and value models ---
    ref_model = None
    value_model = None
    process_output_dim_in_config(config)

    if config.algo.config.get("use_new_actor_critic", False):
        # New-style actor-critic: instantiated from config with backbone specification
        module_dim_dict = getattr(config.algo.config, "module_dim", {})
        policy = custom_instantiate(
            config.algo.config.actor,
            env_config=env.config,
            algo_config=config.algo.config,
            module_dim_dict=module_dim_dict,
            _resolve=False,
        ).to(device)
        if getattr(config.algo.config, "use_dagger", False):
            ref_model = instantiate(
                config.algo.config.teacher_actor,
                env_config=env.config,
                algo_config=config.algo.config,
                module_dim_dict=module_dim_dict,
                _recursive_=False,
                input_key="teacher_obs",
            ).to(device)
        if not getattr(config.algo.config, "distill_only", False) and hasattr(
            config.algo.config, "critic"
        ):
            value_model = instantiate(
                config.algo.config.critic,
                env_config=env.config,
                algo_config=config.algo.config,
                module_dim_dict=module_dim_dict,
                _recursive_=False,
            ).to(device)
    else:
        # Legacy actor-critic: manually constructed from module_dict
        algo_obs_dim_dict = env.config.robot.algo_obs_dim_dict
        actions_dim = env.config.robot.actions_dim

        if getattr(config.algo.config, "use_dagger", False):
            # DAgger student: vision-based policy + state-based teacher
            module_dim_dict = getattr(config.algo.config, "module_dim", {})
            if getattr(config.algo.config, "use_data_transform", False):
                config.max_state_dim = algo_obs_dim_dict["actor_obs"]
                config.max_action_dim = actions_dim
                policy = PPOVisionStateActorWithTransformFixSigma(
                    obs_dim_dict=algo_obs_dim_dict,
                    mlp_module_config_dict=config.algo.config.module_dict.actor,
                    vision_module_config_dict=config.algo.config.module_dict.encoder,
                    num_actions=actions_dim,
                    module_dim_dict=module_dim_dict,
                    input_key="actor_obs",
                    transforms_cfg=config.transforms,
                    image_resolution=config.image_resolution,
                    use_data_augmentation=config.use_data_augmentation,
                ).to(device)
            else:
                policy = PPOVisionStateActorFixSigma(
                    obs_dim_dict=algo_obs_dim_dict,
                    mlp_module_config_dict=config.algo.config.module_dict.actor,
                    vision_module_config_dict=config.algo.config.module_dict.encoder,
                    num_actions=actions_dim,
                    input_key="actor_obs",
                    module_dim_dict=module_dim_dict,
                ).to(device)

            ref_model = PPOStateActorFixSigma(
                obs_dim_dict=algo_obs_dim_dict,
                module_config_dict=config.algo.config.module_dict.teacher_actor,
                num_actions=actions_dim,
                input_key="teacher_obs",
                module_dim_dict=module_dim_dict,
            ).to(device)
        else:
            # Standard PPO: state-based actor with adaptive noise + critic
            policy = PPOStateActor(
                obs_dim_dict=algo_obs_dim_dict,
                module_config_dict=config.algo.config.module_dict.actor,
                num_actions=actions_dim,
                input_key="actor_obs",
                init_noise_std=config.algo.config.init_noise_std,
            ).to(device)

            value_model = PPOCritic(algo_obs_dim_dict, config.algo.config.module_dict.critic).to(
                device
            )

    _a2_wait_for_everyone(accelerator, A2_GPU_BINDING)

    # --- Callbacks ---
    callbacks = []
    for callback in config.callbacks.values():
        callbacks.append(instantiate(callback))

    # --- Save config and initialize trainer ---
    experiment_save_dir = Path(config.experiment_dir)
    if accelerator.is_main_process:
        experiment_save_dir.mkdir(exist_ok=True, parents=True)
        logger.info(f"Saving config files to {experiment_save_dir}")
        save_training_config_snapshots(config, experiment_save_dir, unresolved_conf)
        meta = {"wandb_run": wandb.run.id if wandb_run_exists() else None}
        yaml.safe_dump(meta, open(meta_path, "w"))
        print("saved meta:", meta)

    checkpoint_load_kwargs = {}
    if trainer_target == _A2_BASE_API_TRAINER_TARGET:
        checkpoint_load_kwargs["checkpoint_load_mode"] = checkpoint_load_mode
    if trainer_target in _A2_GPU_BINDING_TRAINER_TARGETS:
        checkpoint_load_kwargs["a2_gpu_identity"] = A2_GPU_BINDING

    trainer = custom_instantiate(
        config.trainer,
        args=training_args,
        config=config.algo.config,
        env=env,
        model=policy,
        value_model=value_model,
        ref_model=ref_model,
        use_ref_model=getattr(config.algo.config, "use_dagger", False),
        train_dataset=None,
        eval_dataset=None,
        callbacks=callbacks,
        checkpoint=config.checkpoint,
        local_seed=config.seed,
        log_dir=experiment_save_dir,
        accelerator=accelerator,
        _resolve=False,
        **checkpoint_load_kwargs,
    )

    # --- Training loop ---
    trainer.train()

    if simulator_type == "IsaacSim":
        _close_simulation_app(
            simulation_app,
            config.simulator.config.render_results,
        )


if __name__ == "__main__":
    main()
