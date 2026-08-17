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
import hashlib
import io
import json
import logging
import math
import os
import random
import re
import subprocess
import sys
import tempfile
import traceback
import uuid
from pathlib import Path
from collections.abc import Mapping


_P2_DEFAULT_TARGET_GLOBAL_STEP = 500
_P2_DEFAULT_NUM_MINI_BATCHES = 4
_P2_DEFAULT_NUM_PPO_EPOCHS = 1
_P2_EXPECTED_OPTIMIZER_STATE_STEP = (
    _P2_DEFAULT_TARGET_GLOBAL_STEP * _P2_DEFAULT_NUM_MINI_BATCHES * _P2_DEFAULT_NUM_PPO_EPOCHS
)
_P2_LIFECYCLE_RUNTIMES = {}


_A2_GPU_BINDING_MODE = "single-visible-logical-cuda0-v3"
_A2_MGPU_BINDING_MODE = "accelerate-ddp-4rank-64e-v1"
_A2_MGPU_TOPOLOGY_ID = "A2-ACCELERATE-DDP-4RANK-64E-V1"
_A2_MGPU_CUDA_VISIBLE_DEVICES = "4,5,6,7"
_A2_MGPU_PHYSICAL_GPU_SET = "4,5,6,7"
_A2_MGPU_MASTER_ADDR = "127.0.0.1"
_A2_MGPU_MASTER_PORT = "29640"
_A2_MGPU_GPU_UUIDS = {
    0: "GPU-20093912-98d6-3c89-9517-3ac344e38fc3",
    1: "GPU-b126539d-3319-a583-f61d-55879b327ddb",
    2: "GPU-4ac67b5e-dc39-3565-d84b-1e7ce20127fa",
    3: "GPU-7c8cb1d2-4ebf-e2e3-35ad-fa0f6f72924d",
}
_A2_GRPO_MGPU_BINDING_MODE = "accelerate-ddp-2rank-gpu23-grpo-v1"
_A2_GRPO_MGPU_TOPOLOGY_ID = "A2-ACCELERATE-DDP-2RANK-GPU23-GRPO-V1"
_A2_GRPO_MGPU_PHYSICAL_GPU_SET = "2,3"
_A2_GRPO_MGPU_MASTER_PORT = "29623"
_A2_GRPO_MGPU_GPU_UUIDS = {
    0: "GPU-7bb5efaa-24d3-ea73-c1ee-9b3341a708be",
    1: "GPU-ffc02ac2-e15e-00e3-f842-6f501cb0b6e5",
}
_A2_DDP_BINDING_MODES = frozenset(
    (_A2_MGPU_BINDING_MODE, _A2_GRPO_MGPU_BINDING_MODE)
)
_A2_GPU_BINDING_ENV = "A2_GPU_BINDING_MODE"
# The single-visible and four-rank contracts declare disjoint required schemas.
# ``_A2_EXPECTED_ENV`` is only the union used to reject unknown names; each
# binding mode validates exactly its own required set below.
_A2_SINGLE_EXPECTED_ENV = (
    "A2_EXPECTED_WORLD_SIZE",
    "A2_EXPECTED_HOST_GPU_INDEX",
    "A2_EXPECTED_LOGICAL_GPU_INDEX",
    "A2_EXPECTED_GPU_UUID",
)
_A2_MGPU_ONLY_EXPECTED_ENV = (
    "A2_EXPECTED_RANK",
    "A2_EXPECTED_PHYSICAL_GPU_SET",
    "A2_EXPECTED_MASTER_ADDR",
    "A2_EXPECTED_MASTER_PORT",
    "A2_EXPECTED_LOCAL_RANK",
)
_A2_EXPECTED_ENV = (
    "A2_EXPECTED_WORLD_SIZE",
    "A2_EXPECTED_RANK",
    "A2_EXPECTED_HOST_GPU_INDEX",
    "A2_EXPECTED_LOGICAL_GPU_INDEX",
    "A2_EXPECTED_GPU_UUID",
    "A2_EXPECTED_PHYSICAL_GPU_SET",
    "A2_EXPECTED_MASTER_ADDR",
    "A2_EXPECTED_MASTER_PORT",
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


def _validate_a2_mgpu_binding(env: Mapping[str, str]):
    """Validate either the legacy four-visible or single-CVD four-rank schema."""
    required = (
        _A2_GPU_BINDING_ENV,
        "CUDA_VISIBLE_DEVICES",
        "CUDA_DEVICE_ORDER",
        "WORLD_SIZE",
        "LOCAL_WORLD_SIZE",
        "RANK",
        "LOCAL_RANK",
        "MASTER_ADDR",
        "MASTER_PORT",
        "A2_EXPECTED_WORLD_SIZE",
    )
    missing = [name for name in required if name not in env]
    if missing:
        raise RuntimeError(f"A2 four-rank binding requires the complete schema; missing={missing}")
    if env[_A2_GPU_BINDING_ENV] != _A2_MGPU_BINDING_MODE:
        raise RuntimeError(
            f"A2 four-rank binding requires {_A2_GPU_BINDING_ENV}={_A2_MGPU_BINDING_MODE!r}; "
            f"got {env[_A2_GPU_BINDING_ENV]!r}"
        )
    if env["CUDA_DEVICE_ORDER"] != "PCI_BUS_ID":
        raise RuntimeError("A2 four-rank binding requires CUDA_DEVICE_ORDER=PCI_BUS_ID")
    world_size = _parse_distributed_int(env["WORLD_SIZE"], "WORLD_SIZE")
    local_world_size = _parse_distributed_int(env["LOCAL_WORLD_SIZE"], "LOCAL_WORLD_SIZE")
    rank = _parse_distributed_int(env["RANK"], "RANK")
    local_rank = _parse_distributed_int(env["LOCAL_RANK"], "LOCAL_RANK")
    expected_world_size = _parse_distributed_int(env["A2_EXPECTED_WORLD_SIZE"], "A2_EXPECTED_WORLD_SIZE")
    visible_device = env["CUDA_VISIBLE_DEVICES"]
    single_cvd = visible_device in {str(index) for index in range(4, 8)}
    if not single_cvd and visible_device != _A2_MGPU_CUDA_VISIBLE_DEVICES:
        raise RuntimeError(
            "A2 four-rank binding requires either one physical CVD entry 4/5/6/7 "
            "or the legacy CUDA_VISIBLE_DEVICES=4,5,6,7 schema; "
            f"got {visible_device!r}"
        )
    if single_cvd:
        required_single = (
            "A2_EXPECTED_RANK",
            "A2_EXPECTED_HOST_GPU_INDEX",
            "A2_EXPECTED_LOGICAL_GPU_INDEX",
            "A2_EXPECTED_GPU_UUID",
            "A2_EXPECTED_PHYSICAL_GPU_SET",
            "A2_EXPECTED_MASTER_ADDR",
            "A2_EXPECTED_MASTER_PORT",
        )
        missing_single = [name for name in required_single if name not in env]
        if missing_single:
            raise RuntimeError(
                f"A2 single-CVD four-rank binding requires the complete schema; missing={missing_single}"
            )
        expected_rank = _parse_distributed_int(env["A2_EXPECTED_RANK"], "A2_EXPECTED_RANK")
        expected_host_gpu = _parse_distributed_int(
            env["A2_EXPECTED_HOST_GPU_INDEX"], "A2_EXPECTED_HOST_GPU_INDEX"
        )
        expected_logical_gpu = _parse_distributed_int(
            env["A2_EXPECTED_LOGICAL_GPU_INDEX"], "A2_EXPECTED_LOGICAL_GPU_INDEX"
        )
        expected_master_port = _parse_distributed_int(
            env["A2_EXPECTED_MASTER_PORT"], "A2_EXPECTED_MASTER_PORT"
        )
        if world_size != 4 or local_world_size != 1 or expected_world_size != 4:
            raise RuntimeError(
                "A2 single-CVD binding requires WORLD_SIZE=4, LOCAL_WORLD_SIZE=1, "
                f"A2_EXPECTED_WORLD_SIZE=4; got {world_size}/{local_world_size}/{expected_world_size}"
            )
        if rank not in range(4) or expected_rank != rank or local_rank != 0:
            raise RuntimeError(
                "A2 single-CVD binding requires global rank 0..3 and LOCAL_RANK=0; "
                f"rank={rank} expected_rank={expected_rank} local_rank={local_rank}"
            )
        if expected_host_gpu != rank + 4 or visible_device != str(expected_host_gpu):
            raise RuntimeError(
                "A2 single-CVD physical GPU mapping drifted; "
                f"rank={rank} expected_host={rank + 4} configured_host={expected_host_gpu} "
                f"visible={visible_device}"
            )
        if expected_logical_gpu != 0:
            raise RuntimeError(
                "A2 single-CVD binding requires A2_EXPECTED_LOGICAL_GPU_INDEX=0; "
                f"got {expected_logical_gpu}"
            )
        if env["A2_EXPECTED_PHYSICAL_GPU_SET"] != _A2_MGPU_PHYSICAL_GPU_SET:
            raise RuntimeError(
                "A2 single-CVD binding requires the global physical GPU set 4,5,6,7; "
                f"got {env['A2_EXPECTED_PHYSICAL_GPU_SET']!r}"
            )
        if env["MASTER_ADDR"] != _A2_MGPU_MASTER_ADDR or env["A2_EXPECTED_MASTER_ADDR"] != env["MASTER_ADDR"]:
            raise RuntimeError(
                "A2 single-CVD binding master address drifted; "
                f"expected={_A2_MGPU_MASTER_ADDR!r} actual={env['MASTER_ADDR']!r}"
            )
        if env["MASTER_PORT"] != _A2_MGPU_MASTER_PORT or expected_master_port != int(_A2_MGPU_MASTER_PORT):
            raise RuntimeError(
                f"A2 single-CVD binding requires MASTER_PORT={_A2_MGPU_MASTER_PORT}"
            )
        expected_uuid = _A2_MGPU_GPU_UUIDS[rank]
        if env["A2_EXPECTED_GPU_UUID"] != expected_uuid:
            raise RuntimeError(
                "A2 single-CVD GPU UUID mapping drifted; "
                f"rank={rank} expected={expected_uuid!r} actual={env['A2_EXPECTED_GPU_UUID']!r}"
            )
    else:
        if world_size != 4 or local_world_size != 4 or expected_world_size != 4:
            raise RuntimeError(
                "A2 four-rank binding requires WORLD_SIZE=LOCAL_WORLD_SIZE=A2_EXPECTED_WORLD_SIZE=4; "
                f"got {world_size}/{local_world_size}/{expected_world_size}"
            )
        expected_local_rank = (
            _parse_distributed_int(env["A2_EXPECTED_LOCAL_RANK"], "A2_EXPECTED_LOCAL_RANK")
            if "A2_EXPECTED_LOCAL_RANK" in env
            else local_rank
        )
        expected_host_gpu = (
            _parse_distributed_int(env["A2_EXPECTED_HOST_GPU_INDEX"], "A2_EXPECTED_HOST_GPU_INDEX")
            if "A2_EXPECTED_HOST_GPU_INDEX" in env
            else rank + 4
        )
        expected_logical_gpu = (
            _parse_distributed_int(env["A2_EXPECTED_LOGICAL_GPU_INDEX"], "A2_EXPECTED_LOGICAL_GPU_INDEX")
            if "A2_EXPECTED_LOGICAL_GPU_INDEX" in env
            else local_rank
        )
        if rank not in range(4) or local_rank != rank or expected_local_rank != rank:
            raise RuntimeError(
                "A2 four-rank binding requires rank/local-rank values 0..3 with exact equality; "
                f"rank={rank} local_rank={local_rank} expected_local_rank={expected_local_rank}"
            )
        if expected_host_gpu != rank + 4 or expected_logical_gpu != rank:
            raise RuntimeError(
                "A2 four-rank physical/logical mapping drifted; "
                f"rank={rank} host={expected_host_gpu} logical={expected_logical_gpu}"
            )
        expected_uuid = _A2_MGPU_GPU_UUIDS[rank]
        configured_uuid = env.get("A2_EXPECTED_GPU_UUID", expected_uuid)
        if configured_uuid != expected_uuid:
            raise RuntimeError(
                "A2 four-rank GPU UUID mapping drifted; "
                f"rank={rank} expected={expected_uuid!r} actual={configured_uuid!r}"
            )
    if env["MASTER_PORT"] != _A2_MGPU_MASTER_PORT:
        raise RuntimeError(
            f"A2 distributed phases require MASTER_PORT={_A2_MGPU_MASTER_PORT}; got {env['MASTER_PORT']!r}"
        )
    if not env["MASTER_ADDR"].strip():
        raise RuntimeError("A2 four-rank binding requires a non-empty MASTER_ADDR")
    forbidden = [
        name for name in env
        if name in {"ACCELERATE_USE_CPU", "ACCELERATE_TORCH_DEVICE", "ACCELERATE_BYPASS_DEVICE_MAP"}
    ]
    if forbidden:
        raise RuntimeError(f"A2 four-rank binding rejects CPU/device override variables: {forbidden}")
    identity = {
        "mode": _A2_MGPU_BINDING_MODE,
        "topology_id": _A2_MGPU_TOPOLOGY_ID,
        "world_size": 4,
        "rank": rank,
        "local_rank": local_rank,
        "host_gpu_index": expected_host_gpu,
        "logical_gpu_index": expected_logical_gpu,
        "pinned_uuid": expected_uuid,
        "cuda_visible_devices": visible_device,
        "physical_gpu_set": _A2_MGPU_PHYSICAL_GPU_SET,
        "single_visible": single_cvd,
        "master_addr": env["MASTER_ADDR"],
        "master_port": int(_A2_MGPU_MASTER_PORT),
    }
    print(
        "[A2_MGPU_BINDING_ENV] "
        f"topology={_A2_MGPU_TOPOLOGY_ID} CVD={visible_device} "
        f"rank={rank} local_rank={local_rank} host_gpu={expected_host_gpu} "
        f"logical_cuda={expected_logical_gpu} uuid={expected_uuid} world_size=4",
        flush=True,
    )
    return identity


def _validate_a2_grpo_mgpu_binding(env: Mapping[str, str]):
    """Validate the two-rank, one-visible-GPU-per-rank GRPO topology."""
    required = (
        _A2_GPU_BINDING_ENV,
        "CUDA_VISIBLE_DEVICES",
        "CUDA_DEVICE_ORDER",
        "WORLD_SIZE",
        "LOCAL_WORLD_SIZE",
        "RANK",
        "LOCAL_RANK",
        "MASTER_ADDR",
        "MASTER_PORT",
        "A2_EXPECTED_WORLD_SIZE",
        "A2_EXPECTED_RANK",
        "A2_EXPECTED_HOST_GPU_INDEX",
        "A2_EXPECTED_LOGICAL_GPU_INDEX",
        "A2_EXPECTED_GPU_UUID",
        "A2_EXPECTED_PHYSICAL_GPU_SET",
        "A2_EXPECTED_MASTER_ADDR",
        "A2_EXPECTED_MASTER_PORT",
    )
    missing = [name for name in required if name not in env]
    if missing:
        raise RuntimeError(f"A2 GRPO DDP binding schema is incomplete; missing={missing}")
    if env[_A2_GPU_BINDING_ENV] != _A2_GRPO_MGPU_BINDING_MODE:
        raise RuntimeError("A2 GRPO DDP binding mode drifted")
    if env["CUDA_DEVICE_ORDER"] != "PCI_BUS_ID":
        raise RuntimeError("A2 GRPO DDP requires CUDA_DEVICE_ORDER=PCI_BUS_ID")

    world_size = _parse_distributed_int(env["WORLD_SIZE"], "WORLD_SIZE")
    local_world_size = _parse_distributed_int(env["LOCAL_WORLD_SIZE"], "LOCAL_WORLD_SIZE")
    rank = _parse_distributed_int(env["RANK"], "RANK")
    local_rank = _parse_distributed_int(env["LOCAL_RANK"], "LOCAL_RANK")
    expected_world_size = _parse_distributed_int(
        env["A2_EXPECTED_WORLD_SIZE"], "A2_EXPECTED_WORLD_SIZE"
    )
    expected_rank = _parse_distributed_int(env["A2_EXPECTED_RANK"], "A2_EXPECTED_RANK")
    host_gpu_index = _parse_distributed_int(
        env["A2_EXPECTED_HOST_GPU_INDEX"], "A2_EXPECTED_HOST_GPU_INDEX"
    )
    logical_gpu_index = _parse_distributed_int(
        env["A2_EXPECTED_LOGICAL_GPU_INDEX"], "A2_EXPECTED_LOGICAL_GPU_INDEX"
    )
    expected_master_port = _parse_distributed_int(
        env["A2_EXPECTED_MASTER_PORT"], "A2_EXPECTED_MASTER_PORT"
    )
    if (world_size, local_world_size, expected_world_size) != (2, 1, 2):
        raise RuntimeError("A2 GRPO DDP requires world/local/expected world sizes 2/1/2")
    if rank not in range(2) or expected_rank != rank or local_rank != 0:
        raise RuntimeError("A2 GRPO DDP requires global ranks 0..1 and LOCAL_RANK=0")
    if host_gpu_index != rank + 2 or env["CUDA_VISIBLE_DEVICES"] != str(host_gpu_index):
        raise RuntimeError("A2 GRPO DDP physical GPU mapping must be rank0->2 and rank1->3")
    if logical_gpu_index != 0:
        raise RuntimeError("A2 GRPO DDP requires one visible logical CUDA device at index 0")
    if env["A2_EXPECTED_PHYSICAL_GPU_SET"] != _A2_GRPO_MGPU_PHYSICAL_GPU_SET:
        raise RuntimeError("A2 GRPO DDP physical GPU set must be exactly 2,3")
    if env["MASTER_ADDR"] != "127.0.0.1" or env["A2_EXPECTED_MASTER_ADDR"] != env["MASTER_ADDR"]:
        raise RuntimeError("A2 GRPO DDP master address must be 127.0.0.1")
    if env["MASTER_PORT"] != _A2_GRPO_MGPU_MASTER_PORT or expected_master_port != int(
        _A2_GRPO_MGPU_MASTER_PORT
    ):
        raise RuntimeError(f"A2 GRPO DDP master port must be {_A2_GRPO_MGPU_MASTER_PORT}")
    expected_uuid = _A2_GRPO_MGPU_GPU_UUIDS[rank]
    if env["A2_EXPECTED_GPU_UUID"] != expected_uuid:
        raise RuntimeError("A2 GRPO DDP GPU UUID mapping drifted")

    identity = {
        "mode": _A2_GRPO_MGPU_BINDING_MODE,
        "topology_id": _A2_GRPO_MGPU_TOPOLOGY_ID,
        "world_size": 2,
        "rank": rank,
        "local_rank": 0,
        "host_gpu_index": host_gpu_index,
        "logical_gpu_index": 0,
        "pinned_uuid": expected_uuid,
        "cuda_visible_devices": env["CUDA_VISIBLE_DEVICES"],
        "physical_gpu_set": _A2_GRPO_MGPU_PHYSICAL_GPU_SET,
        "single_visible": True,
        "master_addr": env["MASTER_ADDR"],
        "master_port": int(_A2_GRPO_MGPU_MASTER_PORT),
    }
    print(
        "[A2_GRPO_MGPU_BINDING_ENV] "
        f"topology={_A2_GRPO_MGPU_TOPOLOGY_ID} rank={rank} "
        f"host_gpu={host_gpu_index} logical_cuda=0 world_size=2",
        flush=True,
    )
    return identity


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
        and name != "A2_EXPECTED_LOCAL_RANK"
    )
    if unknown_gpu or unknown_expected:
        raise RuntimeError(
            "A2 GPU binding accepts only the declared single-visible schema; "
            f"unexpected_gpu={unknown_gpu} unexpected_expected={unknown_expected}"
        )
    if not _a2_gpu_binding_env_present(values):
        return None
    if values.get(_A2_GPU_BINDING_ENV) == _A2_GRPO_MGPU_BINDING_MODE:
        return _validate_a2_grpo_mgpu_binding(values)
    if values.get(_A2_GPU_BINDING_ENV) == _A2_MGPU_BINDING_MODE:
        return _validate_a2_mgpu_binding(values)
    if values.get(_A2_GPU_BINDING_ENV) != _A2_GPU_BINDING_MODE:
        raise RuntimeError(
            f"A2 GPU binding requires A2_GPU_BINDING_MODE={_A2_GPU_BINDING_MODE!r}; "
            f"got {values.get(_A2_GPU_BINDING_ENV)!r}"
        )
    required = (_A2_GPU_BINDING_ENV,) + _A2_SINGLE_EXPECTED_ENV
    missing = [name for name in required if name not in values]
    if missing:
        raise RuntimeError(
            "A2 single-visible GPU binding requires the complete schema; "
            f"missing={missing}"
        )
    mgpu_only_present = [name for name in _A2_MGPU_ONLY_EXPECTED_ENV if name in values]
    if mgpu_only_present:
        raise RuntimeError(
            "A2 single-visible GPU binding rejects four-rank-only schema fields; "
            f"present={mgpu_only_present}"
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
    """Bind the validated process to its logical CUDA device after UUID validation."""
    import torch

    host_gpu_index = int(identity["host_gpu_index"])
    logical_gpu_index = int(identity["logical_gpu_index"])
    expected_uuid = str(identity["pinned_uuid"])
    if identity.get("mode") in _A2_DDP_BINDING_MODES and identity.get("single_visible") is True:
        if logical_gpu_index != 0:
            raise RuntimeError("A2 single-CVD four-rank binding requires logical CUDA device 0")
        if torch.cuda.device_count() != 1:
            raise RuntimeError(
                "A2 single-CVD DDP binding requires exactly one visible CUDA device; "
                f"got device_count={torch.cuda.device_count()}"
            )
        torch.cuda.set_device(0)
        if torch.cuda.current_device() != 0:
            raise RuntimeError("A2 single-CVD four-rank logical CUDA device mismatch")
        properties = torch.cuda.get_device_properties(0)
        observed_uuid = _canonicalize_a2_cuda_uuid(getattr(properties, "uuid", None))
        if observed_uuid != expected_uuid:
            raise RuntimeError(
                "A2 single-CVD four-rank Torch UUID mismatch; "
                f"rank={identity['rank']} host_gpu_index={host_gpu_index} "
                f"expected={expected_uuid!r} observed={observed_uuid!r}"
            )
        print(
            "[A2_MGPU_BINDING_TORCH] "
            f"rank={identity['rank']} local_rank=0 host_gpu_index={host_gpu_index} "
            f"logical_cuda=0 uuid={expected_uuid} world_size={identity['world_size']} single_cvd=true",
            flush=True,
        )
        return torch.device("cuda", 0)
    if identity.get("mode") == _A2_MGPU_BINDING_MODE:
        if torch.cuda.device_count() != 4:
            raise RuntimeError(
                "A2 four-rank binding requires exactly four visible CUDA devices; "
                f"got device_count={torch.cuda.device_count()}"
            )
        if logical_gpu_index != int(identity["local_rank"]):
            raise RuntimeError("A2 four-rank logical CUDA index must equal LOCAL_RANK")
        torch.cuda.set_device(logical_gpu_index)
        if torch.cuda.current_device() != logical_gpu_index:
            raise RuntimeError(
                "A2 four-rank logical CUDA device mismatch; "
                f"expected={logical_gpu_index} actual={torch.cuda.current_device()}"
            )
        properties = torch.cuda.get_device_properties(logical_gpu_index)
        observed_uuid = _canonicalize_a2_cuda_uuid(getattr(properties, "uuid", None))
        if observed_uuid != expected_uuid:
            raise RuntimeError(
                "A2 four-rank Torch UUID mismatch; "
                f"rank={identity['rank']} host_gpu_index={host_gpu_index} "
                f"expected={expected_uuid!r} observed={observed_uuid!r}"
            )
        print(
            "[A2_MGPU_BINDING_TORCH] "
            f"rank={identity['rank']} local_rank={identity['local_rank']} "
            f"host_gpu_index={host_gpu_index} logical_cuda={logical_gpu_index} "
            f"uuid={expected_uuid} world_size=4",
            flush=True,
        )
        return torch.device("cuda", logical_gpu_index)
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
    """Validate the explicit A2 barrier contract for single-rank or four-rank mode."""
    if identity is None:
        accelerator.wait_for_everyone()
        return
    import torch

    if identity.get("mode") in _A2_DDP_BINDING_MODES:
        world_size = int(identity["world_size"])
        if accelerator.num_processes != world_size or accelerator.process_index != int(identity["rank"]):
            raise RuntimeError(
                "A2 four-rank Accelerator identity mismatch at barrier; "
                f"world={accelerator.num_processes} rank={accelerator.process_index} "
                f"expected_rank={identity['rank']}"
            )
        if torch.device(accelerator.device) != torch.device("cuda", int(identity["local_rank"])):
            raise RuntimeError(
                "A2 four-rank Accelerator device mismatch at barrier; "
                f"expected=cuda:{identity['local_rank']} actual={accelerator.device}"
            )
        if not (torch.distributed.is_available() and torch.distributed.is_initialized()):
            raise RuntimeError("A2 four-rank binding requires initialized torch.distributed")
        getattr(accelerator, "wait_for_everyone")()
        return

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

    if identity.get("mode") in _A2_DDP_BINDING_MODES:
        state = getattr(training_args, "distributed_state", None)
        expected_device = torch.device("cuda", int(identity["local_rank"]))
        if state is None or torch.device(state.device) != expected_device:
            raise RuntimeError("A2 four-rank PPOConfig device/state mismatch")
        if state.distributed_type is not DistributedType.MULTI_GPU:
            raise RuntimeError(
                "A2 four-rank PPOConfig requires Accelerate DistributedType.MULTI_GPU; "
                f"got {state.distributed_type}"
            )
        world_size = int(identity["world_size"])
        if int(state.num_processes) != world_size or int(state.process_index) != int(identity["rank"]):
            raise RuntimeError("A2 DDP PPOConfig world/rank mismatch")
        if torch.cuda.current_device() != int(identity["local_rank"]):
            raise RuntimeError("A2 four-rank PPOConfig current CUDA index mismatch")
        if int(training_args.local_rank) != int(identity["local_rank"]):
            raise RuntimeError("A2 four-rank PPOConfig local_rank mismatch")
        if int(training_args._n_gpu) != 1:
            raise RuntimeError("A2 four-rank each process must expose exactly one local GPU")
        if training_args.parallel_mode is not ParallelMode.DISTRIBUTED:
            raise RuntimeError("A2 four-rank PPOConfig must use distributed parallel mode")
        if getattr(training_args, "world_size", None) != world_size:
            raise RuntimeError(f"A2 DDP PPOConfig world_size must equal {world_size}")
        print(
            "[A2_MGPU_PPO_CONFIG] "
            f"topology={identity['topology_id']} rank={identity['rank']} "
            f"local_rank={identity['local_rank']} device={expected_device} world_size={world_size}",
            flush=True,
        )
        return

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

    if identity.get("mode") in _A2_DDP_BINDING_MODES:
        expected_device = torch.device("cuda", int(identity["local_rank"]))
        state = getattr(accelerator, "state", None)
        world_size = int(identity["world_size"])
        if accelerator.num_processes != world_size or accelerator.process_index != int(identity["rank"]):
            raise RuntimeError("A2 DDP Accelerator world/rank mismatch")
        if state is None or state.distributed_type is not DistributedType.MULTI_GPU:
            raise RuntimeError("A2 four-rank Accelerator requires DistributedType.MULTI_GPU")
        if torch.device(accelerator.device) != expected_device:
            raise RuntimeError(
                "A2 four-rank Accelerator device mismatch; "
                f"expected={expected_device} actual={accelerator.device}"
            )
        if torch.cuda.current_device() != int(identity["local_rank"]):
            raise RuntimeError("A2 four-rank current CUDA device mismatch")
        if not (torch.distributed.is_available() and torch.distributed.is_initialized()):
            raise RuntimeError("A2 four-rank Accelerator requires initialized torch.distributed")
        print(
            "[A2_MGPU_ACCELERATOR] "
            f"topology={identity['topology_id']} rank={identity['rank']} "
            f"local_rank={identity['local_rank']} device={expected_device} world_size={world_size}",
            flush=True,
        )
        return

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
    if identity.get("mode") != _A2_MGPU_BINDING_MODE and logical_gpu_index != 0:
        raise RuntimeError(
            "A2 AppLauncher single-visible binding requires logical_gpu_index=0; "
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
    if identity.get("mode") == _A2_MGPU_BINDING_MODE:
        if app_launcher.device_id != logical_gpu_index:
            raise RuntimeError(
                "A2 four-rank AppLauncher logical CUDA identity mismatch; "
                f"expected={logical_gpu_index} actual={app_launcher.device_id}"
            )
        if accelerator is None or str(getattr(accelerator, "device", "")) != f"cuda:{logical_gpu_index}":
            raise RuntimeError("A2 four-rank AppLauncher Accelerator device mismatch")
    elif logical_gpu_index != 0:
        raise RuntimeError("A2 single-visible AppLauncher logical identity must be 0")
    if app_launcher.device_id != logical_gpu_index:
        raise RuntimeError(
            "A2 single-visible AppLauncher device must be cuda:0; "
            f"got {app_launcher.device_id}"
        )
    accelerator_device = getattr(accelerator, "device", None)
    expected_accelerator_device = (
        f"cuda:{logical_gpu_index}"
        if identity.get("mode") == _A2_MGPU_BINDING_MODE
        else "cuda:0"
    )
    if accelerator_device is None or str(accelerator_device) != expected_accelerator_device:
        raise RuntimeError(
            "A2 AppLauncher Accelerator device must match its logical CUDA binding; "
            f"expected={expected_accelerator_device} got={accelerator_device}"
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
            "A2 Kit renderer must disable multi-GPU with maxGpuCount=1 per process; "
            f"enabled={multi_gpu_enabled} autoEnable={multi_gpu_auto} maxGpuCount={max_gpu_count}"
        )
    global _A2_KIT_BINDING_EMITTED
    if not _A2_KIT_BINDING_EMITTED:
        print(
            "[A2_GPU_BINDING_KIT] "
            f"mode={identity['mode']} CVD={host_gpu_index} host_gpu_index={host_gpu_index} "
            f"logical_gpu_index={identity['logical_gpu_index']} UUID={identity['pinned_uuid']} "
            f"world_size={identity['world_size']} renderer_multi_gpu_enabled=false renderer_multi_gpu_autoEnable=false "
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
_A2_GRPO_TRAINER_TARGET = (
    "gr00t.rl.trl.trainer.grpo_trainer_a2_base_api.GRPOTrainerA2BaseAPI"
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
        if trainer_target not in (_A2_BASE_API_TRAINER_TARGET, _A2_GRPO_TRAINER_TARGET):
            raise ValueError(
                "checkpoint_load_mode='policy_only' is only implemented by "
                "the A2 PPO/GRPO trainers; "
                f"got trainer target {trainer_target!r}."
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


def _initialize_p2_common_init(
    policy,
    config,
    *,
    branch_config,
    rng_before_policy,
    device,
    runtime_identity,
):
    """Create/load the P2 common core before Teacher/value construction."""
    from gr00t.rl.trl.modules.vision_actor_critic_modules_p2_recurrent import (
        P2_B1_ARCHITECTURE,
        P2_B2_ARCHITECTURE,
        P2_COMMON_KEY_SCHEMA_SHA256,
        capture_rng_state,
        common_core_state,
        create_common_init_artifact,
        load_common_init_artifact,
        restore_rng_state,
        sha256_file,
        write_step0_manifest,
    )

    if branch_config is None or branch_config.get("enabled") is not True:
        return None
    branch = branch_config.get("branch")
    mode = branch_config.get("mode")
    architecture = branch_config.get("architecture")
    expected_architectures = {"b1": P2_B1_ARCHITECTURE, "b2": P2_B2_ARCHITECTURE}
    if branch not in expected_architectures or architecture != expected_architectures[branch]:
        raise ValueError(
            "P2 common-init branch/architecture contract drifted: "
            f"branch={branch!r} architecture={architecture!r}"
        )
    expected_mode = "create" if branch == "b1" else "load"
    if mode != expected_mode:
        raise ValueError(f"P2 {branch} common-init mode must be {expected_mode!r}; got {mode!r}")
    if getattr(policy, "architecture_id", None) != architecture:
        raise RuntimeError(
            "P2 actor architecture does not match common-init config: "
            f"actor={getattr(policy, 'architecture_id', None)!r} config={architecture!r}"
        )
    seed = branch_config.get("seed")
    if isinstance(seed, bool) or not isinstance(seed, int) or seed != 0:
        raise ValueError(f"P2 common-init seed must be integer 0; got {seed!r}")
    config_sha256 = branch_config.get("config_sha256")
    if (
        not isinstance(config_sha256, str)
        or len(config_sha256) != 64
        or re.fullmatch(r"[0-9a-f]{64}", config_sha256) is None
    ):
        raise ValueError("P2 common-init config_sha256 must be a lowercase SHA-256 string")
    artifact_path = branch_config.get("artifact_path")
    step0_manifest_path = branch_config.get("step0_manifest_path")
    trusted_artifact_sha256 = branch_config.get("trusted_artifact_sha256")
    source_step0_manifest_path = branch_config.get("source_step0_manifest_path")
    trusted_source_step0_manifest_sha256 = branch_config.get("trusted_source_step0_manifest_sha256")
    if not isinstance(artifact_path, str) or not artifact_path.strip():
        raise ValueError("P2 common-init artifact_path must be a non-empty string")
    if not isinstance(step0_manifest_path, str) or not step0_manifest_path.strip():
        raise ValueError("P2 common-init step0_manifest_path must be a non-empty string")
    if branch == "b2":
        if (
            not isinstance(trusted_artifact_sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", trusted_artifact_sha256) is None
        ):
            raise ValueError("P2 B2 requires trusted_artifact_sha256 from the parent seal")
        if not isinstance(source_step0_manifest_path, str) or not source_step0_manifest_path.strip():
            raise ValueError("P2 B2 requires source_step0_manifest_path from the B1 seal")
        if (
            not isinstance(trusted_source_step0_manifest_sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", trusted_source_step0_manifest_sha256) is None
        ):
            raise ValueError("P2 B2 requires trusted_source_step0_manifest_sha256")
    if not isinstance(runtime_identity, Mapping) or not runtime_identity:
        raise ValueError("P2 common-init runtime_identity must be a non-empty mapping")
    rng_downstream = None
    if branch == "b1":
        rng_downstream = capture_rng_state()
        common_manifest = create_common_init_artifact(
            policy,
            artifact_path,
            branch=branch,
            architecture=architecture,
            seed=seed,
            config_sha256=config_sha256,
            runtime_identity=runtime_identity,
            rng_before_policy=rng_before_policy,
            rng_downstream=rng_downstream,
        )
        artifact_sha256 = sha256_file(artifact_path)
    else:
        common_manifest, rng_downstream = load_common_init_artifact(
            policy,
            artifact_path,
            branch=branch,
            architecture=architecture,
            seed=seed,
            config_sha256=config_sha256,
            runtime_identity=runtime_identity,
            rng_before_policy=rng_before_policy,
            trusted_artifact_sha256=trusted_artifact_sha256,
            source_step0_manifest_path=source_step0_manifest_path,
            trusted_source_step0_manifest_sha256=trusted_source_step0_manifest_sha256,
        )
        restore_rng_state(rng_downstream)
        artifact_sha256 = trusted_artifact_sha256
    _, _, common_core_sha256 = common_core_state(policy)
    step0_manifest = {
        "branch": branch,
        "architecture": architecture,
        "seed": seed,
        "config_sha256": config_sha256,
        "runtime_identity": dict(runtime_identity),
        "common_core_sha256": common_core_sha256,
        "common_init_artifact": str(Path(artifact_path).expanduser().resolve()),
        "common_init_manifest_sha256": hashlib.sha256(
            json.dumps(common_manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        "common_core_key_schema_sha256": common_manifest.get(
            "common_core_key_schema_sha256", P2_COMMON_KEY_SCHEMA_SHA256
        ),
        "common_core_keys": [item["key"] for item in common_manifest.get("keys", [])],
        "common_core_key_identities": list(common_manifest.get("keys", [])),
        "artifact_sha256": artifact_sha256,
        "rng_before_policy_identity": rng_before_policy.get("identity"),
        "rng_downstream_identity": rng_downstream.get("identity"),
        "device": str(device),
    }
    write_step0_manifest(step0_manifest_path, step0_manifest)
    print(
        "[A2_P2_COMMON_INIT] "
        f"branch={branch} architecture={architecture} common_core_sha256={common_core_sha256} "
        f"artifact={Path(artifact_path).expanduser().resolve()} "
        f"step0_manifest={Path(step0_manifest_path).expanduser().resolve()}",
        flush=True,
    )
    return step0_manifest


def _fresh_state_hash(module) -> str:
    """Hash an ordered CPU snapshot of a fresh policy/value module."""
    import torch

    if module is None:
        raise ValueError("fresh-init module cannot be None")
    identities = []
    for key, value in module.state_dict().items():
        if not isinstance(key, str) or not key or not torch.is_tensor(value):
            raise RuntimeError("fresh-init state contains an invalid key/tensor")
        cpu_value = value.detach().to(device="cpu").contiguous()
        if not bool(torch.isfinite(cpu_value.float()).all().item()):
            raise RuntimeError(f"fresh-init state is non-finite: {key}")
        identities.append(
            {
                "key": key,
                "shape": list(cpu_value.shape),
                "dtype": str(cpu_value.dtype),
                "bytes": cpu_value.numpy().tobytes(order="C").hex(),
            }
        )
    payload = json.dumps(identities, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _validate_fresh_ddp_contract(config, accelerator, binding):
    """Validate the no-checkpoint/fresh-init contract for four-rank mode."""
    fresh = config.algo.config.get("fresh_ddp_init", None)
    if fresh is None or fresh.get("enabled") is not True:
        return None
    if binding is None or binding.get("mode") != _A2_MGPU_BINDING_MODE:
        raise RuntimeError("fresh_ddp_init requires the explicit four-rank A2 binding")
    if config.get("checkpoint", None) is not None:
        raise RuntimeError("fresh_ddp_init requires checkpoint=null")
    if config.get("auto_load_latest", False) is not False:
        raise RuntimeError("fresh_ddp_init requires auto_load_latest=false")
    if config.algo.config.get("distill_only", False) is not True:
        raise RuntimeError("fresh_ddp_init requires distill_only=true")
    if config.algo.config.get("freeze_noise_std", False) is not True:
        raise RuntimeError("fresh_ddp_init requires freeze_noise_std=true")
    if config.algo.config.get("p2_common_init", {}).get("enabled", False):
        raise RuntimeError("fresh_ddp_init cannot consume a P2 common-init artifact")
    if int(config.num_envs) != 64 or int(binding["world_size"]) != 4:
        raise RuntimeError("fresh_ddp_init requires 64 local envs and world_size=4")
    if accelerator.num_processes != 4:
        raise RuntimeError("fresh_ddp_init requires an actual four-process Accelerator")
    required_fields = {
        "architecture_id": "C-B2H-DUALRAW-SHAREDENC-TOEOUT6-V19-P2",
        "topology_id": _A2_MGPU_TOPOLOGY_ID,
        "seed": 0,
        "rank_seed_offset": "global_rank",
        "load_before_optimizer": True,
        "strict_model_hash": True,
    }
    for key, expected in required_fields.items():
        if fresh.get(key) != expected:
            raise RuntimeError(
                f"fresh_ddp_init.{key} must be {expected!r}; got {fresh.get(key)!r}"
            )
    return dict(fresh)


def _initialize_fresh_ddp_models(policy, value_model, config, accelerator, binding):
    """Rank-zero fresh init + strict byte/hash load before optimizer preparation."""
    fresh = _validate_fresh_ddp_contract(config, accelerator, binding)
    if fresh is None:
        return None
    import torch

    if getattr(policy, "architecture_id", None) != fresh["architecture_id"]:
        raise RuntimeError(
            "fresh-init policy architecture identity drifted; "
            f"expected={fresh['architecture_id']!r} got={getattr(policy, 'architecture_id', None)!r}"
        )
    if int(config.seed) != int(fresh["seed"]):
        raise RuntimeError(
            "fresh-init common seed must be loaded before any rank-specific seed offset: "
            f"config.seed={config.seed!r} common_seed={fresh['seed']!r}"
        )
    experiment_root = Path(config.experiment_dir).expanduser().resolve()
    init_root = experiment_root / "fresh_init"
    artifact_path = init_root / "step0_model_init.pt"
    rank = int(binding["rank"])
    if accelerator.is_main_process:
        init_root.mkdir(parents=True, exist_ok=False)
        payload = {
            "schema": "a2_cb2h_toeout6_fresh_ddp_init_v1",
            "architecture_id": fresh["architecture_id"],
            "topology_id": fresh["topology_id"],
            "seed": fresh["seed"],
            "common_seed": int(fresh["seed"]),
            "policy_state_dict": {
                key: value.detach().to(device="cpu").contiguous()
                for key, value in policy.state_dict().items()
            },
            "value_state_dict": (
                {
                    key: value.detach().to(device="cpu").contiguous()
                    for key, value in value_model.state_dict().items()
                }
                if value_model is not None
                else None
            ),
        }
        encoded = io.BytesIO()
        torch.save(payload, encoded)
        encoded_bytes = encoded.getvalue()
        temporary = init_root / ".step0_model_init.pt.writing"
        with temporary.open("wb") as stream:
            stream.write(encoded_bytes)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, artifact_path)
        digest = hashlib.sha256(encoded_bytes).hexdigest()
        manifest = {
            "schema": "a2_cb2h_toeout6_fresh_ddp_init_manifest_v1",
            "architecture_id": fresh["architecture_id"],
            "topology_id": fresh["topology_id"],
            "artifact_sha256": digest,
            "policy_hash": _fresh_state_hash(policy),
            "value_hash": _fresh_state_hash(value_model) if value_model is not None else None,
            "global_step": 0,
            "optimizer": None,
        }
        manifest_path = init_root / "step0_manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
    _a2_wait_for_everyone(accelerator, binding)
    if not artifact_path.is_file():
        raise FileNotFoundError(f"fresh-init artifact is unavailable after rank barrier: {artifact_path}")
    payload = torch.load(artifact_path, map_location="cpu", weights_only=False)
    if not isinstance(payload, Mapping) or payload.get("schema") != "a2_cb2h_toeout6_fresh_ddp_init_v1":
        raise RuntimeError("fresh-init artifact schema drifted")
    policy.load_state_dict(payload["policy_state_dict"], strict=True)
    if value_model is not None:
        if payload.get("value_state_dict") is None:
            raise RuntimeError("fresh-init artifact is missing value state")
        value_model.load_state_dict(payload["value_state_dict"], strict=True)
    # Rank-specific randomness is permitted only after every rank has loaded
    # the rank-zero byte snapshot.  No rank offset is applied before this
    # strict byte/hash load.
    rank_seed = int(fresh["seed"]) + rank
    seeding(rank_seed)
    local_hashes = {
        "rank": rank,
        "common_seed": int(fresh["seed"]),
        "rank_seed": rank_seed,
        "rank_seed_after_load": True,
        "policy_hash": _fresh_state_hash(policy),
        "value_hash": _fresh_state_hash(value_model) if value_model is not None else None,
    }
    gathered = [None] * int(binding["world_size"])
    torch.distributed.all_gather_object(gathered, local_hashes)
    if not all(isinstance(item, Mapping) for item in gathered):
        raise RuntimeError(f"fresh-init hash gather returned malformed rank records: {gathered!r}")
    if {int(item.get("rank", -1)) for item in gathered} != set(range(int(binding["world_size"]))):
        raise RuntimeError(f"fresh-init hash gather rank set drifted: {gathered!r}")
    reference_hashes = {
        "policy_hash": gathered[0].get("policy_hash"),
        "value_hash": gathered[0].get("value_hash"),
    }
    if any(
        {
            "policy_hash": item.get("policy_hash"),
            "value_hash": item.get("value_hash"),
        }
        != reference_hashes
        for item in gathered
    ):
        raise RuntimeError(f"fresh-init synchronized hash mismatch: {gathered!r}")
    _a2_wait_for_everyone(accelerator, binding)
    print(
        "[A2_MGPU_FRESH_INIT] "
        f"rank={rank} architecture={fresh['architecture_id']} topology={fresh['topology_id']} "
        f"policy_hash={local_hashes['policy_hash']} value_hash={local_hashes['value_hash']} "
        "global_step=0 optimizer=none",
        flush=True,
    )
    return {"artifact_path": str(artifact_path), **local_hashes}


def _p2_model_state_schema(state_dict, *, name, branch, architecture, implementation, module=None):
    """Capture exact ordered model state identities immediately before training."""
    import torch

    identities = []
    for key, tensor in state_dict.items():
        if not isinstance(key, str) or not key:
            raise RuntimeError(f"P2 {name} state schema contains an invalid key")
        if not torch.is_tensor(tensor) or tensor.layout != torch.strided or tensor.numel() <= 0:
            raise RuntimeError(f"P2 {name} state {key!r} must be a non-empty strided tensor")
        if not bool(torch.isfinite(tensor.detach().float()).all().item()):
            raise RuntimeError(f"P2 {name} state {key!r} is non-finite")
        contiguous = tensor.detach().to(device="cpu").contiguous()
        identities.append(
            {
                "key": key,
                "shape": list(contiguous.shape),
                "dtype": str(contiguous.dtype),
                "sha256": hashlib.sha256(contiguous.numpy().tobytes(order="C")).hexdigest(),
            }
        )
    if not identities:
        raise RuntimeError(f"P2 {name} state schema must not be empty")
    keys = [identity["key"] for identity in identities]
    digest = hashlib.sha256(json.dumps(identities, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    from gr00t.rl.trl.modules.vision_actor_critic_modules_p2_recurrent import p2_production_state_contract

    trusted_contract = p2_production_state_contract(branch, name)
    structural = [
        {"key": item["key"], "shape": item["shape"], "dtype": item["dtype"]}
        for item in identities
    ]
    trusted_structural = [
        {"key": item["key"], "shape": item["shape"], "dtype": item["dtype"]}
        for item in trusted_contract["identities"]
    ]
    if structural != trusted_structural:
        raise RuntimeError(f"P2 {name} state schema does not match the exact production contract")
    if module is None:
        raise RuntimeError(f"P2 {name} schema requires the independently instantiated module")
    parameter_identities = []
    for key, parameter in module.named_parameters():
        if key not in keys:
            raise RuntimeError(f"P2 {name} parameter {key!r} is absent from state schema")
        parameter_identities.append(
            {"key": key, "shape": list(parameter.shape), "dtype": str(parameter.dtype)}
        )
    if parameter_identities != trusted_contract["parameter_identities"]:
        raise RuntimeError(f"P2 {name} parameter schema does not match the exact production contract")
    parameter_schema_sha256 = hashlib.sha256(
        json.dumps(parameter_identities, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "schema": "a2_cb2h_pro_p2_model_state_schema_v1",
        "role": name,
        "architecture": architecture,
        "implementation": implementation,
        "key_count": len(keys),
        "keys": keys,
        "identities": identities,
        "schema_sha256": digest,
        "aggregate_sha256": digest,
        "contract_sha256": trusted_contract["contract_sha256"],
        "parameter_keys": [item["key"] for item in parameter_identities],
        "parameter_identities": parameter_identities,
        "parameter_count": len(parameter_identities),
        "parameter_schema_sha256": parameter_schema_sha256,
    }


def _finalize_p2_step0_model_schema(step0_manifest_path, policy, value_model, *, branch):
    """Atomically append full policy/value schemas after common-init and model creation."""
    if value_model is None:
        raise RuntimeError("P2 full step0 schema requires a value model before trainer construction")
    from gr00t.rl.trl.modules.vision_actor_critic_modules_p2_recurrent import read_immutable_snapshot

    manifest_path = Path(step0_manifest_path).expanduser().resolve(strict=True)
    payload_bytes, _ = read_immutable_snapshot(manifest_path)
    payload = json.loads(payload_bytes.decode("utf-8"))
    if not isinstance(payload, dict) or payload.get("global_step") != 0 or payload.get("optimizer") is not None:
        raise RuntimeError("P2 step0 manifest cannot be finalized from an invalid pre-training state")
    policy_name = type(policy).__module__ + "." + type(policy).__name__
    value_name = type(value_model).__module__ + "." + type(value_model).__name__
    expected_policy_name = (
        "gr00t.rl.trl.modules.vision_actor_critic_modules_p2_recurrent."
        + ("DualD435VisionRecurrentActor" if branch == "b1" else "DualD435HeadVisionRecurrentActor")
    )
    if policy_name != expected_policy_name or value_name != "gr00t.rl.trl.modules.actor_critic_modules_recurrent.RecurrentCritic":
        raise RuntimeError(
            "P2 model implementations drifted before step0 schema finalization: "
            f"policy={policy_name!r} value={value_name!r}"
        )
    payload["policy_state_schema"] = _p2_model_state_schema(
        policy.state_dict(),
        name="policy",
        branch=branch,
        architecture=getattr(policy, "architecture_id", None),
        implementation=policy_name,
        module=policy,
    )
    payload["value_state_schema"] = _p2_model_state_schema(
        value_model.state_dict(),
        name="value",
        branch=branch,
        architecture="RecurrentCritic",
        implementation=value_name,
        module=value_model,
    )
    payload["policy_state_schema_sha256"] = payload["policy_state_schema"]["schema_sha256"]
    payload["value_state_schema_sha256"] = payload["value_state_schema"]["schema_sha256"]
    _p2_atomic_json(manifest_path, payload)
    return payload


def _p2_trainable_parameter_order(policy, value_model):
    if value_model is None:
        raise RuntimeError("P2 optimizer schema requires a recurrent value model")
    ordered = []
    for prefix, module in (("policy", policy), ("value_model", value_model)):
        for name, parameter in module.named_parameters():
            if parameter.requires_grad:
                ordered.append((f"{prefix}.{name}", parameter))
    if not ordered or not any(name.startswith("value_model.") for name, _ in ordered):
        raise RuntimeError("P2 optimizer parameter order must contain trainable policy and value parameters")
    return ordered


def _p2_register_gradient_activity(expected_order, *, expected_optimizer_state_step=None):
    """Track the exact parameters that receive real backward gradients."""
    import torch

    if not expected_order:
        raise RuntimeError("P2 gradient activity tracking requires a non-empty optimizer order")
    if expected_optimizer_state_step is None:
        expected_optimizer_state_step = _P2_EXPECTED_OPTIMIZER_STATE_STEP
    if (
        isinstance(expected_optimizer_state_step, bool)
        or not isinstance(expected_optimizer_state_step, int)
        or expected_optimizer_state_step <= 0
    ):
        raise ValueError("P2 expected optimizer state step must be a positive integer")
    active_names = set()
    observed_order = []
    gradient_event_counts = {}
    handles = []
    expected_by_name = {name: parameter for name, parameter in expected_order}

    def register(name, parameter):
        if not isinstance(parameter, torch.nn.Parameter) or not parameter.requires_grad:
            raise RuntimeError(f"P2 activity tracker received a non-trainable parameter: {name!r}")

        def on_gradient(gradient):
            if not torch.is_tensor(gradient) or gradient.shape != parameter.shape or gradient.dtype != parameter.dtype:
                raise RuntimeError(f"P2 gradient shape/dtype drifted for {name!r}")
            if not bool(torch.isfinite(gradient.detach()).all().item()):
                raise RuntimeError(f"P2 observed a non-finite gradient for {name!r}")
            gradient_event_counts[name] = gradient_event_counts.get(name, 0) + 1
            if name not in active_names:
                observed_order.append(name)
            active_names.add(name)
            return gradient

        handles.append(parameter.register_hook(on_gradient))

    for name, parameter in expected_order:
        register(name, parameter)

    class ActivityTracker:
        def bind_optimizer_schema(self, optimizer_schema):
            if not isinstance(optimizer_schema, Mapping):
                raise RuntimeError("P2 activity tracker requires the finalized optimizer schema")
            ordered_schema = optimizer_schema.get("ordered_parameters")
            if not isinstance(ordered_schema, list) or not ordered_schema:
                raise RuntimeError("P2 activity tracker requires ordered optimizer parameters")
            if any(not isinstance(item, Mapping) for item in ordered_schema):
                raise RuntimeError("P2 activity tracker optimizer parameters are malformed")
            schema_names = [item.get("name") for item in ordered_schema]
            if schema_names != [name for name, _ in expected_order]:
                raise RuntimeError("P2 activity tracker optimizer order is not cross-bound to the production wrapper")
            for item in ordered_schema:
                name = item.get("name")
                parameter = expected_by_name.get(name)
                if parameter is None or list(parameter.shape) != item.get("shape") or str(parameter.dtype) != item.get("dtype"):
                    raise RuntimeError(f"P2 activity tracker optimizer parameter binding drifted for {name!r}")
            policy_parameters = [
                item for item in ordered_schema
                if isinstance(item.get("name"), str) and item["name"].startswith("policy.")
            ]
            std_parameters = [item for item in policy_parameters if item["name"] == "policy.core.std"]
            if len(std_parameters) != 1:
                raise RuntimeError("P2 activity tracker requires exactly one policy.core.std parameter")
            if not any(
                isinstance(item.get("name"), str) and item["name"].startswith("value_model.")
                for item in ordered_schema
            ):
                raise RuntimeError("P2 activity tracker requires value_model parameters in the cross-bound schema")
            expected_active = [
                item for item in policy_parameters if item["name"] != "policy.core.std"
            ]
            if not expected_active:
                raise RuntimeError("P2 activity tracker requires a non-empty trusted BC-active sequence")
            self._optimizer_schema = optimizer_schema
            self._expected_active = [dict(item) for item in expected_active]

        def snapshot(self, optimizer):
            if not hasattr(self, "_optimizer_schema") or not hasattr(self, "_expected_active"):
                raise RuntimeError("P2 activity tracker was not bound to the finalized optimizer schema")
            serialized = optimizer.state_dict()
            id_by_parameter = {}
            for group_state, group_runtime in zip(serialized["param_groups"], optimizer.param_groups, strict=True):
                for parameter_id, parameter in zip(group_state["params"], group_runtime["params"], strict=True):
                    id_by_parameter[id(parameter)] = int(parameter_id)
            expected_names = [item["name"] for item in self._expected_active]
            if active_names != set(expected_names):
                missing = [name for name in expected_names if name not in active_names]
                extra = sorted(active_names.difference(expected_names))
                raise RuntimeError(
                    f"P2 observed BC-active membership drifted: missing={missing!r} extra={extra!r}"
                )
            ordered = []
            for expected_item in self._expected_active:
                name = expected_item["name"]
                parameter = expected_by_name[name]
                if id(parameter) not in id_by_parameter:
                    raise RuntimeError(f"P2 active parameter {name!r} is absent from the prepared optimizer")
                actual_id = id_by_parameter[id(parameter)]
                if actual_id != expected_item["id"]:
                    raise RuntimeError(f"P2 active parameter {name!r} ID drifted from the cross-bound optimizer schema")
                if list(parameter.shape) != expected_item["shape"] or str(parameter.dtype) != expected_item["dtype"]:
                    raise RuntimeError(f"P2 active parameter {name!r} shape/dtype drifted")
                ordered.append(
                    {
                        "id": actual_id,
                        "name": name,
                        "shape": list(parameter.shape),
                        "dtype": str(parameter.dtype),
                    }
                )
            if not ordered:
                raise RuntimeError("P2 training produced no observed active gradients")
            expected_ids = [item["id"] for item in ordered]
            if set(serialized["state"]) != set(expected_ids):
                raise RuntimeError("P2 optimizer state IDs do not exactly match the observed BC-active membership")
            parameter_ids = [item["id"] for item in ordered]
            parameter_names = [item["name"] for item in ordered]
            return {
                "schema": "a2_cb2h_pro_p2_active_parameter_schema_v1",
                "parameter_count": len(ordered),
                "ordered_parameters": ordered,
                "parameter_ids": parameter_ids,
                "parameter_names": parameter_names,
                "schema_sha256": hashlib.sha256(
                    json.dumps(ordered, sort_keys=True, separators=(",", ":")).encode("utf-8")
                ).hexdigest(),
            }

        def hook_order(self):
            return list(observed_order)

        def backward_call_count(self):
            if not hasattr(self, "_expected_active"):
                raise RuntimeError("P2 activity tracker was not bound to the finalized optimizer schema")
            expected_names = [item["name"] for item in self._expected_active]
            counts = [gradient_event_counts.get(name, 0) for name in expected_names]
            if not counts or any(count <= 0 for count in counts) or len(set(counts)) != 1:
                raise RuntimeError(f"P2 gradient-event counts disagree across active parameters: {counts!r}")
            return counts[0]

        def native_optimizer_step_count(self, optimizer, active_parameter_schema):
            serialized = optimizer.state_dict()
            active_ids = active_parameter_schema.get("parameter_ids")
            states = serialized.get("state")
            if not isinstance(active_ids, list) or not isinstance(states, Mapping):
                raise RuntimeError("P2 native optimizer state is missing active IDs")
            if set(states) != set(active_ids):
                raise RuntimeError("P2 native optimizer state IDs do not match active membership")
            steps = []
            for parameter_id in active_ids:
                state = states.get(parameter_id)
                if not isinstance(state, Mapping) or "step" not in state:
                    raise RuntimeError(f"P2 native optimizer state lacks step for parameter {parameter_id!r}")
                step = state["step"]
                if not torch.is_tensor(step) or not torch.is_floating_point(step) or step.numel() != 1:
                    raise RuntimeError(f"P2 native optimizer step for parameter {parameter_id!r} is malformed")
                value = float(step.item())
                if value != expected_optimizer_state_step:
                    raise RuntimeError(
                        f"P2 native optimizer step for parameter {parameter_id!r} must equal "
                        f"{expected_optimizer_state_step}"
                    )
                steps.append(int(value))
            if not steps or len(set(steps)) != 1:
                raise RuntimeError(f"P2 native optimizer steps disagree: {steps!r}")
            return steps[0]

        def remove(self):
            for handle in handles:
                handle.remove()
            handles.clear()

    return ActivityTracker()


def _p2_optimizer_json(value):
    if isinstance(value, tuple):
        return [_p2_optimizer_json(item) for item in value]
    if isinstance(value, list):
        return [_p2_optimizer_json(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _p2_optimizer_json(item) for key, item in value.items()}
    if hasattr(value, "item") and not isinstance(value, (str, bytes)):
        try:
            return value.item()
        except (TypeError, ValueError):
            pass
    return value


def _p2_optimizer_parameter_schema(trainer_model, optimizer, scheduler, expected_order):
    import torch
    from torch.optim.adamw import AdamW

    wrapper_class = type(optimizer).__module__ + "." + type(optimizer).__name__
    inner_optimizer = getattr(optimizer, "optimizer", None)
    inner_class = (
        type(inner_optimizer).__module__ + "." + type(inner_optimizer).__name__
        if inner_optimizer is not None
        else None
    )
    if wrapper_class != "accelerate.optimizer.AcceleratedOptimizer":
        raise RuntimeError(
            "P2 optimizer schema requires the trainer's prepared AcceleratedOptimizer wrapper; "
            f"got {wrapper_class!r}"
        )
    if inner_class != "torch.optim.adamw.AdamW" or not isinstance(inner_optimizer, AdamW):
        raise RuntimeError(
            "P2 optimizer schema requires AcceleratedOptimizer.optimizer to be torch.optim.adamw.AdamW; "
            f"got {inner_class!r}"
        )
    named_parameters = list(trainer_model.named_parameters())
    model_parameters = {id(parameter): (name, parameter) for name, parameter in named_parameters}
    expected_names = [name for name, _ in expected_order]
    wrapper_trainable_names = [
        name for name, parameter in named_parameters
        if parameter.requires_grad and (name.startswith("policy.") or name.startswith("value_model."))
    ]
    if wrapper_trainable_names != expected_names:
        raise RuntimeError("P2 optimizer parameter schema does not match PolicyAndValueWrapper order")
    serialized = optimizer.state_dict()
    runtime_groups = optimizer.param_groups
    if len(runtime_groups) != len(serialized["param_groups"]) or len(runtime_groups) != 2:
        raise RuntimeError("P2 optimizer must expose exactly two AdamW parameter groups")
    id_by_parameter = {}
    for group_state, group_runtime in zip(serialized["param_groups"], runtime_groups, strict=True):
        if len(group_state["params"]) != len(group_runtime["params"]):
            raise RuntimeError("P2 optimizer serialized/runtime parameter groups disagree")
        for parameter_id, parameter in zip(group_state["params"], group_runtime["params"], strict=True):
            if id(parameter) not in model_parameters:
                raise RuntimeError("P2 optimizer contains a parameter outside PolicyAndValueWrapper")
            id_by_parameter[id(parameter)] = int(parameter_id)
    ordered_parameters = []
    for name, expected_parameter in expected_order:
        if id(expected_parameter) not in id_by_parameter:
            raise RuntimeError(f"P2 optimizer omitted expected trainable parameter {name!r}")
        ordered_parameters.append(
            {
                "id": id_by_parameter[id(expected_parameter)],
                "name": name,
                "shape": list(expected_parameter.shape),
                "dtype": str(expected_parameter.dtype),
            }
        )
    param_groups = []
    for index, group_state in enumerate(serialized["param_groups"]):
        names = []
        for parameter_id in group_state["params"]:
            matching = [item["name"] for item in ordered_parameters if item["id"] == int(parameter_id)]
            if len(matching) != 1:
                raise RuntimeError("P2 optimizer group ID cannot be bound to the wrapper order")
            names.append(matching[0])
        hyperparameters = {key: _p2_optimizer_json(value) for key, value in group_state.items() if key != "params"}
        param_groups.append(
            {
                "index": index,
                "parameter_ids": [int(value) for value in group_state["params"]],
                "parameter_names": names,
                "hyperparameters": hyperparameters,
            }
        )
    scheduler_state = scheduler.state_dict()
    scheduler_schema = {
        "schema": "a2_cb2h_pro_p2_constant_scheduler_schema_v1",
        "scheduler_class": type(scheduler).__module__ + "." + type(scheduler).__name__,
        "state_dict": _p2_optimizer_json(scheduler_state),
    }
    return {
        "schema": "a2_cb2h_pro_p2_optimizer_parameter_schema_v1",
        "optimizer_wrapper_class": wrapper_class,
        "optimizer_class": inner_class,
        "parameter_count": len(ordered_parameters),
        "ordered_parameters": ordered_parameters,
        "param_groups": param_groups,
        "state_parameter_ids": sorted(int(key) for key in serialized["state"]),
    }, scheduler_schema


def _finalize_p2_step0_optimizer_schema(step0_manifest_path, trainer, expected_order):
    from gr00t.rl.trl.modules.vision_actor_critic_modules_p2_recurrent import read_immutable_snapshot

    manifest_path = Path(step0_manifest_path).expanduser().resolve(strict=True)
    payload_bytes, _ = read_immutable_snapshot(manifest_path)
    payload = json.loads(payload_bytes.decode("utf-8"))
    if not isinstance(payload, dict) or payload.get("global_step") != 0 or payload.get("optimizer") is not None:
        raise RuntimeError("P2 step0 manifest cannot be finalized from an invalid pre-training state")
    optimizer_schema, scheduler_schema = _p2_optimizer_parameter_schema(
        trainer.model,
        trainer.optimizer,
        trainer.lr_scheduler,
        expected_order,
    )
    payload["optimizer_parameter_schema"] = optimizer_schema
    payload["scheduler_schema"] = scheduler_schema
    _p2_atomic_json(manifest_path, payload)
    return payload


def _p2_atomic_json(path, payload):
    """Atomically seal one P2 lifecycle artifact in its destination directory."""
    destination = Path(path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode(
        "utf-8"
    )
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=str(destination.parent)
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
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


class _P2LifecycleCallback:
    """Top-level callback observer; no nested callable is attached to a trainer."""

    def __init__(self, expected_args, target_global_step):
        self.expected_args = expected_args
        self.target_global_step = target_global_step
        self.callback_train_begin_seen = False
        self.callback_step_end_count = 0
        self.callback_max_steps = None
        self.observed_global_steps = []

    def on_train_begin(self, args, state, control, **kwargs):
        del kwargs
        if args is not self.expected_args or getattr(state, "max_steps", None) != self.target_global_step:
            raise RuntimeError("P2 callback train-begin absolute target proof failed")
        self.callback_train_begin_seen = True
        self.callback_max_steps = state.max_steps
        return control

    def on_step_end(self, args, state, control, **kwargs):
        del kwargs
        if args is not self.expected_args or getattr(state, "max_steps", None) != self.target_global_step:
            raise RuntimeError("P2 callback step-end absolute target proof failed")
        self.callback_step_end_count += 1
        self.observed_global_steps.append(int(state.global_step))
        return control

    def on_train_end(self, args, state, control, **kwargs):
        del args, state, kwargs
        return control

    def on_save(self, args, state, control, **kwargs):
        del args, state, kwargs
        return control

    def on_log(self, args, state, control, logs, **kwargs):
        del args, state, logs, kwargs
        return control


def _p2_guarded_train(self, *train_args, **train_kwargs):
    """Run native training, then seal P2 evidence from native state deltas."""
    runtime_id = getattr(self, "_a2_p2_lifecycle_runtime_id", None)
    runtime = _P2_LIFECYCLE_RUNTIMES.get(runtime_id)
    if runtime is None:
        raise RuntimeError("P2 lifecycle runtime registry entry is missing")
    optimizer = getattr(self, "optimizer", None)
    scheduler = getattr(self, "lr_scheduler", None)
    callback_handler = getattr(self, "callback_handler", None)
    active_parameter_tracker = runtime["active_parameter_tracker"]
    observer = runtime["observer"]
    if optimizer is None or scheduler is None or callback_handler is None:
        raise RuntimeError("P2 lifecycle requires optimizer, scheduler, and callbacks")
    native_train = getattr(type(self), "train", None)
    if not callable(native_train) or native_train is _p2_guarded_train:
        raise RuntimeError("P2 native trainer.train method is unavailable")
    training_succeeded = False
    try:
        native_train(self, *train_args, **train_kwargs)
        training_succeeded = True
    finally:
        callback_handler.remove_callback(observer)
        if not training_succeeded:
            active_parameter_tracker.remove()
            _P2_LIFECYCLE_RUNTIMES.pop(runtime_id, None)
            self.__dict__.pop("train", None)
            self.__dict__.pop("_a2_p2_lifecycle_runtime_id", None)
    if not training_succeeded:
        raise RuntimeError("P2 native training did not complete")

    final_step = int(getattr(getattr(self, "state", None), "global_step", -1))
    scheduler_after = {
        "step_count": int(getattr(scheduler, "_step_count", 0)),
        "last_epoch": int(getattr(scheduler, "last_epoch", -1)),
    }
    scheduler_before = runtime["scheduler_before"]
    scheduler_step_count = scheduler_after["step_count"] - scheduler_before["step_count"]
    if final_step != runtime["target_global_step"]:
        raise RuntimeError(f"P2 final global_step drifted: {final_step}")
    if observer.callback_step_end_count != runtime["target_global_step"]:
        raise RuntimeError("P2 callback step count drifted")
    if observer.observed_global_steps != list(range(1, runtime["target_global_step"] + 1)):
        raise RuntimeError("P2 callback global-step progression drifted")
    expected_scheduler_after = {
        "step_count": scheduler_before["step_count"] + runtime["target_global_step"],
        "last_epoch": scheduler_before["last_epoch"] + runtime["target_global_step"],
    }
    if scheduler_step_count != runtime["target_global_step"] or scheduler_after != expected_scheduler_after:
        raise RuntimeError(f"P2 scheduler lifecycle drifted: calls={scheduler_step_count} after={scheduler_after}")
    final_checkpoint = runtime["branch_root"] / f"model_step_{runtime['target_global_step']:06d}.pt"
    final_config = runtime["branch_root"] / "config.yaml"
    if not final_checkpoint.is_file() or not final_config.is_file():
        raise RuntimeError("P2 final checkpoint/config was not sealed before teardown")
    if not callable(getattr(active_parameter_tracker, "snapshot", None)):
        raise RuntimeError("P2 lifecycle requires the real gradient-activity tracker")
    active_parameter_schema = active_parameter_tracker.snapshot(optimizer)
    backward_call_count = active_parameter_tracker.backward_call_count()
    optimizer_step_count = active_parameter_tracker.native_optimizer_step_count(
        optimizer,
        active_parameter_schema,
    )
    expected_updates = runtime["expected_optimizer_state_step"]
    if backward_call_count != expected_updates or optimizer_step_count != expected_updates:
        raise RuntimeError(
            f"P2 native backward/optimizer evidence drifted from {expected_updates}: "
            f"backward={backward_call_count} optimizer={optimizer_step_count}"
        )
    from gr00t.rl.trl.modules.vision_actor_critic_modules_p2_recurrent import sha256_file

    lifecycle = {
        "schema": "a2_cb2h_pro_p2_pre_teardown_completion_v1",
        "operation": "p2_pre_teardown_completion",
        "proof_stage": "PRE_TEARDOWN",
        "branch": runtime["branch"],
        "root": str(runtime["branch_root"]),
        "start_global_step": 0,
        "target_global_step": runtime["target_global_step"],
        "expected_optimizer_state_step": expected_updates,
        "expected_additional_iterations": runtime["target_global_step"],
        "completed_iterations": runtime["target_global_step"],
        "callback_train_begin_seen": observer.callback_train_begin_seen,
        "callback_step_end_count": observer.callback_step_end_count,
        "callback_max_steps": observer.callback_max_steps,
        "backward_call_count": backward_call_count,
        "optimizer_step_count": optimizer_step_count,
        "scheduler_step_count": scheduler_step_count,
        "scheduler_step_count_before": scheduler_before["step_count"],
        "scheduler_step_count_after": scheduler_after["step_count"],
        "scheduler_last_epoch_before": scheduler_before["last_epoch"],
        "scheduler_last_epoch_after": scheduler_after["last_epoch"],
        "observed_global_steps": list(observer.observed_global_steps),
        "final_checkpoint": {"path": str(final_checkpoint), "sha256": sha256_file(final_checkpoint), "global_step": runtime["target_global_step"]},
        "final_config": {"path": str(final_config), "sha256": sha256_file(final_config)},
        "common_init_artifact": {"path": str(runtime["common_artifact_path"]), "sha256": sha256_file(runtime["common_artifact_path"])},
        "step0_manifest": {"path": str(runtime["step0_manifest_path"]), "sha256": sha256_file(runtime["step0_manifest_path"])},
        "runtime": dict(runtime["runtime_identity"]),
        "natural_kit_lifecycle_pass": False,
        "lifecycle_status": "UNRESOLVED",
        "controlled_post_training_exit": True,
        "active_parameter_schema": active_parameter_schema,
    }
    lifecycle["manifest_content_sha256"] = hashlib.sha256(
        json.dumps(lifecycle, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()
    metrics = {
        "schema": "a2_cb2h_pro_p2_runtime_metrics_v1",
        "branch": runtime["branch"],
        "training_performed": True,
        "global_step_start": 0,
        "global_step_final": final_step,
        "target_global_step": runtime["target_global_step"],
        "expected_optimizer_state_step": expected_updates,
        "completed_iterations": lifecycle["completed_iterations"],
        "callbacks": lifecycle["callback_step_end_count"],
        "callback_train_begin_seen": lifecycle["callback_train_begin_seen"],
        "callback_step_end_count": lifecycle["callback_step_end_count"],
        "callback_max_steps": lifecycle["callback_max_steps"],
        "backward_calls": lifecycle["backward_call_count"],
        "optimizer_steps": lifecycle["optimizer_step_count"],
        "backward_call_count": lifecycle["backward_call_count"],
        "optimizer_step_count": lifecycle["optimizer_step_count"],
        "scheduler_step_count": lifecycle["scheduler_step_count"],
        "scheduler_step_count_before": lifecycle["scheduler_step_count_before"],
        "scheduler_step_count_after": lifecycle["scheduler_step_count_after"],
        "scheduler_last_epoch_before": lifecycle["scheduler_last_epoch_before"],
        "scheduler_last_epoch_after": lifecycle["scheduler_last_epoch_after"],
        "observed_global_steps": list(lifecycle["observed_global_steps"]),
        "scheduler": scheduler_after,
        "lifecycle": {"natural": False, "status": "UNRESOLVED", "controlled": True},
        "runtime": dict(runtime["runtime_identity"]),
        "final_checkpoint": lifecycle["final_checkpoint"],
        "final_config": lifecycle["final_config"],
        "common_init": lifecycle["common_init_artifact"],
        "step0_manifest": lifecycle["step0_manifest"],
        "active_parameter_schema": active_parameter_schema,
    }
    metrics["content_sha256"] = hashlib.sha256(
        json.dumps(metrics, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()
    _p2_atomic_json(runtime["branch_root"] / "runtime_metrics.json", metrics)
    _p2_atomic_json(runtime["branch_root"] / "pre_teardown_completion_proof.json", lifecycle)
    active_parameter_tracker.remove()
    _P2_LIFECYCLE_RUNTIMES.pop(runtime_id, None)
    self.__dict__.pop("train", None)
    self.__dict__.pop("_a2_p2_lifecycle_runtime_id", None)
    print(
        f"[A2_P2_TRAINING_COMPLETION] branch={runtime['branch']} global_step={final_step} "
        f"callbacks={observer.callback_step_end_count} backward={backward_call_count} "
        f"optimizer={optimizer_step_count} scheduler={scheduler_after}",
        flush=True,
    )
    os._exit(0)
    raise RuntimeError("P2 controlled post-training exit returned unexpectedly")


def _install_p2_lifecycle_guard(
    trainer,
    *,
    branch,
    branch_root,
    common_artifact_path,
    step0_manifest_path,
    runtime_identity,
    target_global_step=_P2_DEFAULT_TARGET_GLOBAL_STEP,
    expected_optimizer_state_step=None,
    active_parameter_tracker=None,
):
    """Install serialization-safe lifecycle evidence around native trainer methods."""
    if branch not in ("b1", "b2"):
        raise ValueError(f"P2 lifecycle branch must be b1/b2; got {branch!r}")
    if isinstance(target_global_step, bool) or not isinstance(target_global_step, int) or target_global_step <= 0:
        raise ValueError("P2 lifecycle target_global_step must be a positive integer")
    if expected_optimizer_state_step is None:
        expected_optimizer_state_step = target_global_step * _P2_DEFAULT_NUM_MINI_BATCHES * _P2_DEFAULT_NUM_PPO_EPOCHS
    if (
        isinstance(expected_optimizer_state_step, bool)
        or not isinstance(expected_optimizer_state_step, int)
        or expected_optimizer_state_step <= 0
    ):
        raise ValueError("P2 lifecycle expected optimizer state step must be a positive integer")
    branch_root = Path(branch_root).expanduser().resolve()
    common_artifact_path = Path(common_artifact_path).expanduser().resolve(strict=True)
    step0_manifest_path = Path(step0_manifest_path).expanduser().resolve(strict=True)
    if getattr(trainer, "_a2_p2_lifecycle_guard", False):
        raise RuntimeError("P2 lifecycle guard is already installed")
    state = getattr(trainer, "state", None)
    args = getattr(trainer, "args", None)
    scheduler = getattr(trainer, "lr_scheduler", None)
    callback_handler = getattr(trainer, "callback_handler", None)
    if state is None or args is None or scheduler is None or callback_handler is None:
        raise RuntimeError("P2 lifecycle requires trainer state, args, scheduler, and callbacks")
    if getattr(state, "global_step", None) != 0:
        raise RuntimeError("P2 fresh lifecycle must start at global_step=0")
    if getattr(args, "num_total_batches", None) != target_global_step:
        raise RuntimeError(
            "P2 lifecycle requires num_total_batches to equal target_global_step: "
            f"target={target_global_step} actual={getattr(args, 'num_total_batches', None)}"
        )
    if active_parameter_tracker is None or not callable(getattr(active_parameter_tracker, "snapshot", None)):
        raise RuntimeError("P2 lifecycle requires the real gradient-activity tracker")
    scheduler_before = {
        "step_count": int(getattr(scheduler, "_step_count", 0)),
        "last_epoch": int(getattr(scheduler, "last_epoch", -1)),
    }
    if scheduler_before != {"step_count": 1, "last_epoch": 0}:
        raise RuntimeError(f"P2 scheduler before proof drifted: {scheduler_before}")
    observer = _P2LifecycleCallback(args, target_global_step)
    if not callable(getattr(callback_handler, "add_callback", None)) or not callable(
        getattr(callback_handler, "remove_callback", None)
    ):
        raise RuntimeError("P2 lifecycle callback handler lacks serialization-safe observer registration")
    callback_handler.add_callback(observer)
    if not isinstance(getattr(callback_handler, "callbacks", None), list):
        raise RuntimeError("P2 lifecycle callback handler does not expose an ordered callback list")
    callback_handler.callbacks.remove(observer)
    callback_handler.callbacks.insert(0, observer)
    runtime_id = id(trainer)
    _P2_LIFECYCLE_RUNTIMES[runtime_id] = {
        "branch": branch,
        "branch_root": branch_root,
        "common_artifact_path": common_artifact_path,
        "step0_manifest_path": step0_manifest_path,
        "runtime_identity": dict(runtime_identity),
        "target_global_step": target_global_step,
        "expected_optimizer_state_step": expected_optimizer_state_step,
        "scheduler_before": scheduler_before,
        "observer": observer,
        "active_parameter_tracker": active_parameter_tracker,
    }
    trainer._a2_p2_lifecycle_runtime_id = runtime_id
    trainer.train = __import__("types").MethodType(_p2_guarded_train, trainer)
    trainer._a2_p2_lifecycle_guard = True


def _install_mgpu_lifecycle_contract(trainer, *, target_global_step: int, binding):
    """Register the standalone fresh-init lifecycle without B1/B2 artifact loading."""
    if binding is None or binding.get("mode") != _A2_MGPU_BINDING_MODE:
        raise RuntimeError("standalone DDP lifecycle requires the four-rank binding")
    state = getattr(trainer, "state", None)
    args = getattr(trainer, "args", None)
    accelerator = getattr(trainer, "accelerator", None)
    callback_handler = getattr(trainer, "callback_handler", None)
    if state is None or args is None or accelerator is None:
        raise RuntimeError("standalone DDP lifecycle requires trainer state/args/accelerator")
    if callback_handler is None or not isinstance(getattr(callback_handler, "callbacks", None), list):
        raise RuntimeError("standalone DDP lifecycle requires an ordered callback handler")
    if getattr(state, "global_step", None) != 0:
        raise RuntimeError("standalone DDP lifecycle must start at global_step=0")
    if int(getattr(args, "num_total_batches", -1)) != int(target_global_step):
        raise RuntimeError("standalone DDP lifecycle target must equal num_total_batches")
    if accelerator.num_processes != 4:
        raise RuntimeError("standalone DDP lifecycle requires world_size=4")
    strict_callbacks = [
        callback
        for callback in callback_handler.callbacks
        if getattr(callback, "strict_mode", False) is True
    ]
    expected_save_frequency = 500
    runner_mode = str(getattr(trainer, "_a2_mgpu_runner_mode", "formal"))
    if runner_mode == "admission":
        expected_save_frequency = 1
    if len(strict_callbacks) != 1 or int(getattr(strict_callbacks[0], "save_frequency", -1)) != expected_save_frequency:
        raise RuntimeError(
            "standalone DDP lifecycle requires exactly one strict rank-zero callback at the sealed frequency"
        )
    trainer._a2_mgpu_lifecycle_contract = {
        "schema": "a2_cb2h_toeout20_mgpu_lifecycle_v1",
        "topology_id": _A2_MGPU_TOPOLOGY_ID,
        "target_global_step": int(target_global_step),
        "save_frequency": expected_save_frequency,
        "rank0_canonical_owner": True,
        "checkpoint_load": None,
        "auto_load_latest": False,
    }
    print(
        "[A2_MGPU_LIFECYCLE] "
        f"topology={_A2_MGPU_TOPOLOGY_ID} rank={binding['rank']} "
        f"target_global_step={target_global_step} checkpoint=null auto_load_latest=false",
        flush=True,
    )


def _a2_rank_output_root(experiment_root, binding):
    """Return the exclusive output root owned by one DDP rank."""
    root = Path(experiment_root).expanduser().resolve()
    if binding is None or binding.get("mode") != _A2_MGPU_BINDING_MODE:
        return root
    rank = int(binding["rank"])
    if rank == 0:
        return root
    rank_root = root / "ranks" / f"rank{rank}"
    if rank_root.parent != root / "ranks" or rank_root.name != f"rank{rank}":
        raise RuntimeError("A2 DDP rank output path escaped the sealed experiment root")
    return rank_root


def _a2_rank_hydra_output_root(experiment_root, rank):
    root = Path(experiment_root).expanduser().resolve()
    if isinstance(rank, bool) or not isinstance(rank, int) or rank not in range(4):
        raise ValueError(f"A2 DDP Hydra rank must be an integer in 0..3; got {rank!r}")
    return root / "ranks" / f"rank{rank}"


def _a2_validate_hydra_runtime_dir(experiment_root, binding, runtime_output_dir):
    if binding is None or binding.get("mode") != _A2_MGPU_BINDING_MODE:
        return Path(runtime_output_dir).expanduser().resolve()
    rank = int(binding["rank"])
    expected_root = _a2_rank_hydra_output_root(experiment_root, rank)
    resolved = Path(runtime_output_dir).expanduser().resolve()
    if not resolved.is_relative_to(expected_root):
        raise RuntimeError(
            "A2 DDP Hydra runtime directory escaped its exact rank root: "
            f"rank={rank} runtime={resolved} expected_under={expected_root}"
        )
    return resolved


def _a2_validate_rank_hydra_dirs(experiment_root):
    roots = tuple(_a2_rank_hydra_output_root(experiment_root, rank) for rank in range(4))
    if len({path.resolve() for path in roots}) != 4:
        raise RuntimeError("A2 DDP Hydra rank roots are not pairwise unique")
    missing = [path for path in roots if not path.is_dir()]
    if missing:
        raise FileNotFoundError(f"A2 DDP Hydra rank roots were not created before training writes: {missing}")
    return roots


def _a2_prepare_rank_output_roots(experiment_root, accelerator, binding):
    """Create rank-local evidence directories after the process-group barrier."""
    root = Path(experiment_root).expanduser().resolve()
    if binding is None or binding.get("mode") != _A2_MGPU_BINDING_MODE:
        root.mkdir(parents=True, exist_ok=True)
        return root
    if accelerator.is_main_process:
        root.mkdir(parents=True, exist_ok=True)
    _a2_wait_for_everyone(accelerator, binding)
    _a2_validate_rank_hydra_dirs(root)
    rank_root = _a2_rank_output_root(root, binding)
    if rank_root != root and not rank_root.is_dir():
        raise FileNotFoundError(f"A2 DDP rank output root was not created by Hydra: {rank_root}")
    _a2_wait_for_everyone(accelerator, binding)
    return rank_root


def _a2_atomic_rank_json(path, payload):
    path = Path(path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"refusing to overwrite rank evidence: {path}")
    temporary = path.with_name(f".{path.name}.writing")
    if temporary.exists():
        raise FileExistsError(f"rank evidence temporary path already exists: {temporary}")
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    with temporary.open("wb") as stream:
        stream.write(encoded)
        stream.write(b"\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _a2_optimizer_state_hash(optimizer):
    """Hash finite optimizer state without relying on process-local object ids."""
    import torch

    if optimizer is None:
        raise RuntimeError("A2 DDP proof requires an initialized optimizer")
    records = []
    for parameter_index, (parameter, state) in enumerate(optimizer.state.items()):
        parameter_records = []
        for key, value in sorted(state.items(), key=lambda item: str(item[0])):
            if torch.is_tensor(value):
                cpu_value = value.detach().to(device="cpu").contiguous()
                if not bool(torch.all(torch.isfinite(cpu_value.float())).item()):
                    raise RuntimeError(f"optimizer state is non-finite for {key!r}")
                parameter_records.append(
                    {
                        "key": str(key),
                        "shape": list(cpu_value.shape),
                        "dtype": str(cpu_value.dtype),
                        "bytes": cpu_value.numpy().tobytes(order="C").hex(),
                    }
                )
            elif isinstance(value, (int, float)) and math.isfinite(float(value)):
                parameter_records.append({"key": str(key), "value": float(value)})
            else:
                raise RuntimeError(f"optimizer state contains unsupported/non-finite value for {key!r}")
        records.append({"parameter_index": parameter_index, "state": parameter_records})
    encoded = json.dumps(records, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _a2_validate_teacher_phase_records(records, *, target_global_step, world_size=4):
    """Validate local/global Teacher counts and mask identities across ranks."""
    if not isinstance(records, list) or len(records) != world_size:
        raise RuntimeError(f"A2 Teacher proof gather expected {world_size} rank records")
    expected_phases = (("L0", 64),)
    if int(target_global_step) >= 8000:
        expected_phases = (("L0", 64), ("L1", 48), ("L2", 32), ("L3", 16))
    elif int(target_global_step) >= 4000:
        expected_phases = (("L0", 64), ("L1", 48), ("L2", 32))
    elif int(target_global_step) >= 2000:
        expected_phases = (("L0", 64), ("L1", 48))
    result = {}
    for phase, expected_local_count in expected_phases:
        per_rank = []
        for rank_record in records:
            phases = [item for item in rank_record if isinstance(item, Mapping) and item.get("phase") == phase]
            if not phases:
                raise RuntimeError(f"A2 Teacher proof is missing phase {phase} on a rank")
            item = phases[-1]
            if int(item.get("local_env_count", -1)) != 64 or int(item.get("local_teacher_count", -1)) != expected_local_count:
                raise RuntimeError(f"A2 Teacher local count drifted in {phase}: {item!r}")
            per_rank.append(item)
        mask_hashes = {item.get("mask_hash") for item in per_rank}
        if len(mask_hashes) != 1 or None in mask_hashes:
            raise RuntimeError(f"A2 Teacher mask identity disagreed in {phase}: {per_rank!r}")
        result[phase] = {
            "local_teacher_count": expected_local_count,
            "global_teacher_count": expected_local_count * world_size,
            "mask_hash": next(iter(mask_hashes)),
            "rank_count": world_size,
        }
    expected_global = [value["global_teacher_count"] for value in result.values()]
    if expected_global != [256, 192, 128, 64][: len(expected_global)]:
        raise RuntimeError(f"A2 Teacher global schedule drifted: {expected_global}")
    return result


def _seal_a2_mgpu_rank_evidence(trainer, *, experiment_root, rank_root, binding, target_global_step, fresh_init):
    """Write per-rank proofs and one rank-zero aggregate after native training."""
    import torch

    if binding is None or binding.get("mode") != _A2_MGPU_BINDING_MODE:
        raise RuntimeError("A2 rank evidence requires the four-rank binding")
    rank = int(binding["rank"])
    world_size = int(binding["world_size"])
    if world_size != 4:
        raise RuntimeError("A2 rank evidence requires world_size=4")
    expected_rank_root = _a2_rank_output_root(experiment_root, binding)
    if Path(rank_root).expanduser().resolve() != expected_rank_root:
        raise RuntimeError("A2 rank evidence root does not match its leased rank path")
    state = getattr(trainer, "state", None)
    final_step = int(getattr(state, "global_step", -1))
    if final_step != int(target_global_step):
        raise RuntimeError(f"A2 final global_step drifted: expected={target_global_step} actual={final_step}")
    policy = getattr(trainer, "policy_model", None)
    if policy is None:
        policy = getattr(getattr(trainer, "unwrapped_model", None), "policy", None)
    if policy is None:
        raise RuntimeError("A2 rank proof cannot access the unwrapped policy")
    policy_hash = _fresh_state_hash(policy)
    local_records = list(getattr(trainer, "_a2_teacher_phase_records", []))
    proof = {
        "schema": "a2_cb2h_toeout6_rank_proof_v1",
        "rank": rank,
        "world_size": world_size,
        "architecture_id": "C-B2H-DUALRAW-SHAREDENC-TOEOUT6-V19-P2",
        "topology_id": _A2_MGPU_TOPOLOGY_ID,
        "global_step": final_step,
        "target_global_step": int(target_global_step),
        "local_envs": 64,
        "global_envs": 256,
        "local_transitions": 512,
        "global_transitions": 2048,
        "loss_finite": isinstance(getattr(trainer, "_a2_last_bc_loss", None), (int, float))
        and math.isfinite(float(trainer._a2_last_bc_loss)),
        "gradient_finite": bool(getattr(trainer, "_a2_last_gradient_finite", False)),
        "model_hash": policy_hash,
        "optimizer_hash": _a2_optimizer_state_hash(getattr(trainer, "optimizer", None)),
        "teacher_phase_records": local_records,
        "fresh_init": dict(fresh_init or {}),
    }
    if not proof["loss_finite"] or not proof["gradient_finite"]:
        raise RuntimeError("A2 rank proof requires finite loss and gradient evidence")
    rank_proof_dir = Path(experiment_root).expanduser().resolve() / "ranks" / f"rank{rank}"
    if not rank_proof_dir.is_dir():
        raise FileNotFoundError(f"A2 rank proof directory was not created by Hydra: {rank_proof_dir}")
    _a2_wait_for_everyone(trainer.accelerator, binding)
    rank_proof_path = rank_proof_dir / "rank_proof.json"
    _a2_atomic_rank_json(rank_proof_path, proof)
    gathered = [None] * world_size
    torch.distributed.all_gather_object(gathered, proof)
    if any(not isinstance(item, Mapping) for item in gathered):
        raise RuntimeError("A2 rank proof gather returned malformed records")
    model_hashes = {item.get("model_hash") for item in gathered}
    if len(model_hashes) != 1 or None in model_hashes:
        raise RuntimeError(f"A2 model hashes disagree across ranks: {model_hashes}")
    optimizer_hashes = {item.get("optimizer_hash") for item in gathered}
    if len(optimizer_hashes) != 1 or None in optimizer_hashes:
        raise RuntimeError(f"A2 optimizer hashes disagree across ranks: {optimizer_hashes}")
    teacher_evidence = _a2_validate_teacher_phase_records(
        [item.get("teacher_phase_records", []) for item in gathered],
        target_global_step=target_global_step,
        world_size=world_size,
    )
    if rank == 0:
        final_checkpoint = Path(experiment_root).expanduser().resolve() / f"model_step_{final_step:06d}.pt"
        if not final_checkpoint.is_file():
            raise FileNotFoundError(f"A2 rank-zero final checkpoint is missing: {final_checkpoint}")
        from gr00t.rl.trl.modules.vision_actor_critic_modules_p2_recurrent import sha256_file

        aggregate = {
            "schema": "a2_cb2h_toeout6_mgpu_aggregate_proof_v1",
            "status": "ADMISSION_COMPLETE" if int(target_global_step) == 1 else "FORMAL_COMPLETE",
            "rank_count": world_size,
            "ranks": [
                {"rank": int(item["rank"]), "path": str(Path(experiment_root).resolve() / "ranks" / f"rank{int(item['rank'])}" / "rank_proof.json")}
                for item in gathered
            ],
            "rank_records": [
                {
                    "rank": int(item["rank"]),
                    "loss_finite": bool(item["loss_finite"]),
                    "gradient_finite": bool(item["gradient_finite"]),
                    "model_hash": item["model_hash"],
                    "optimizer_hash": item["optimizer_hash"],
                    "teacher_phase_records": item["teacher_phase_records"],
                }
                for item in gathered
            ],
            "model_hash": next(iter(model_hashes)),
            "teacher_evidence": teacher_evidence,
            "final_checkpoint": {"path": str(final_checkpoint), "sha256": sha256_file(final_checkpoint), "global_step": final_step},
            "fresh_init": dict(fresh_init or {}),
            "natural_teardown": False,
        }
        _a2_atomic_rank_json(Path(experiment_root).expanduser().resolve() / "aggregate_proof.json", aggregate)
    _a2_wait_for_everyone(trainer.accelerator, binding)
    return proof


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
            kwargs_handlers=[DistributedDataParallelKwargs(find_unused_parameters=False), kwargs],
        )
    if A2_GPU_BINDING is not None:
        _validate_a2_accelerator_binding(accelerator, A2_GPU_BINDING)

    if A2_GPU_BINDING is not None and A2_GPU_BINDING.get("mode") in _A2_DDP_BINDING_MODES:
        device = f"cuda:{A2_GPU_BINDING['local_rank']}"
    elif A2_GPU_BINDING is not None:
        device = "cuda:0"
    else:
        device = str(accelerator.device)
    if device == "cuda":
        device = "cuda:0"
    experiment_root = Path(config.experiment_dir).expanduser().resolve()
    rank_root = _a2_prepare_rank_output_roots(experiment_root, accelerator, A2_GPU_BINDING)
    if A2_GPU_BINDING is not None and A2_GPU_BINDING.get("mode") == _A2_MGPU_BINDING_MODE:
        training_args.output_dir = str(rank_root)
    config.multi_gpu = accelerator.num_processes > 1
    base_seed = int(config.seed)
    if config.multi_gpu:
        config.global_rank = accelerator.process_index
        config.algo.config.global_rank = accelerator.process_index
        config.algo.config.world_size = accelerator.num_processes
    seeding(base_seed)

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
        args_cli.output_dir = str(rank_root)
        args_cli.enable_cameras = (
            config.simulator.config.cameras.enable_cameras or config.simulator.config.render_results
        )
        args_cli.headless = config.headless
        if A2_GPU_BINDING is not None:
            args_cli.multi_gpu = False
            if A2_GPU_BINDING.get("mode") in _A2_DDP_BINDING_MODES:
                args_cli.distributed = True
                args_cli.device = f"cuda:{A2_GPU_BINDING['local_rank']}"
            else:
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
    from gr00t.rl.trl.modules.vision_actor_critic_modules_p2_recurrent import (
        P2_B1_ARCHITECTURE,
        P2_B2_ARCHITECTURE,
        capture_rng_state,
        common_core_state,
        create_common_init_artifact,
        load_common_init_artifact,
        restore_rng_state,
        write_step0_manifest,
    )
    from gr00t.rl.utils.helpers import pre_process_config
    from gr00t.rl.utils.logging import HydraLoggerBridge

    # --- Logging setup ---
    hydra_log_path = str(rank_root / "train.log")
    logger.remove()
    logger.add(hydra_log_path, level="DEBUG")
    if A2_GPU_BINDING is not None and A2_GPU_BINDING.get("mode") == _A2_MGPU_BINDING_MODE:
        hydra_runtime_dir = _a2_validate_hydra_runtime_dir(
            experiment_root,
            A2_GPU_BINDING,
            HydraConfig.get().runtime.output_dir,
        )
        _a2_atomic_rank_json(
            rank_root / "hydra_runtime.json",
            {
                "schema": "a2_cb2h_toeout6_rank_hydra_runtime_v1",
                "rank": int(A2_GPU_BINDING["rank"]),
                "hydra_output_dir": str(hydra_runtime_dir),
                "rank_output_root": str(rank_root),
                "canonical_root": str(experiment_root),
            },
        )
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
    config.env.config.save_rendering_dir = str(rank_root / "renderings_training")
    config.env.config.experiment_dir = str(rank_root)
    env = custom_instantiate(config.env, device=device, _resolve=False)

    # --- Build policy and value models ---
    ref_model = None
    value_model = None
    process_output_dim_in_config(config)
    p2_common_init_config = config.algo.config.get("p2_common_init", None)
    p2_lifecycle_config = config.algo.config.get("p2_lifecycle", None)
    p2_lifecycle_target = _P2_DEFAULT_TARGET_GLOBAL_STEP
    p2_expected_optimizer_state_step = _P2_EXPECTED_OPTIMIZER_STATE_STEP
    if p2_lifecycle_config is not None and p2_lifecycle_config.get("enabled") is True:
        configured_target = p2_lifecycle_config.get("target_global_step")
        if (
            isinstance(configured_target, bool)
            or not isinstance(configured_target, int)
            or configured_target <= 0
        ):
            raise ValueError("P2 lifecycle target_global_step must be a positive integer")
        p2_lifecycle_target = configured_target
        mini_batches = config.algo.config.get("num_mini_batches", _P2_DEFAULT_NUM_MINI_BATCHES)
        epochs = config.algo.config.get("num_learning_epochs", _P2_DEFAULT_NUM_PPO_EPOCHS)
        if (
            isinstance(mini_batches, bool)
            or not isinstance(mini_batches, int)
            or mini_batches <= 0
            or isinstance(epochs, bool)
            or not isinstance(epochs, int)
            or epochs <= 0
        ):
            raise ValueError("P2 lifecycle optimizer-step dimensions must be positive integers")
        p2_expected_optimizer_state_step = p2_lifecycle_target * mini_batches * epochs
        if int(config.algo.trl.num_total_batches) != p2_lifecycle_target:
            raise ValueError(
                "P2 lifecycle target_global_step must equal algo.trl.num_total_batches: "
                f"target={p2_lifecycle_target} batches={config.algo.trl.num_total_batches}"
            )
    p2_step0_manifest = None
    p2_optimizer_parameter_order = None
    p2_active_parameter_tracker = None
    p2_rng_before_policy = (
        capture_rng_state()
        if p2_common_init_config is not None and p2_common_init_config.get("enabled") is True
        else None
    )

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
        if p2_rng_before_policy is not None:
            p2_step0_manifest = _initialize_p2_common_init(
                policy,
                config,
                branch_config=p2_common_init_config,
                rng_before_policy=p2_rng_before_policy,
                device=device,
                runtime_identity=p2_common_init_config.get("runtime_identity", {}),
            )
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

    if p2_step0_manifest is not None:
        _finalize_p2_step0_model_schema(
            p2_common_init_config.get("step0_manifest_path"),
            policy,
            value_model,
            branch=str(p2_common_init_config.get("branch")),
        )
        p2_optimizer_parameter_order = _p2_trainable_parameter_order(policy, value_model)
        p2_active_parameter_tracker = _p2_register_gradient_activity(
            p2_optimizer_parameter_order,
            expected_optimizer_state_step=p2_expected_optimizer_state_step,
        )

    # The rank-zero fresh-init artifact lives below the experiment directory;
    # establish that parent before the strict ``exist_ok=False`` artifact
    # directory creation.  The later snapshot block reuses this same path.
    experiment_save_dir = experiment_root
    fresh_contract = config.algo.config.get("fresh_ddp_init", None)
    if fresh_contract is not None and fresh_contract.get("enabled") is True:
        if accelerator.is_main_process:
            experiment_save_dir.mkdir(exist_ok=True, parents=True)
        _a2_wait_for_everyone(accelerator, A2_GPU_BINDING)

    fresh_ddp_init = _initialize_fresh_ddp_models(
        policy,
        value_model,
        config,
        accelerator,
        A2_GPU_BINDING,
    )

    if fresh_ddp_init is not None:
        expected_rank_seed = int(base_seed) + int(A2_GPU_BINDING["rank"])
        if int(fresh_ddp_init["rank_seed"]) != expected_rank_seed:
            raise RuntimeError(
                "fresh-init rank seed drifted: "
                f"expected={expected_rank_seed} actual={fresh_ddp_init['rank_seed']}"
            )
        config.seed = expected_rank_seed
        config.algo.config.rank_seed = expected_rank_seed
        training_args.seed = expected_rank_seed

    _a2_wait_for_everyone(accelerator, A2_GPU_BINDING)

    # --- Callbacks ---
    callbacks = []
    for callback in config.callbacks.values():
        callback_config = callback
        callback_target = str(callback.get("_target_", ""))
        if (
            A2_GPU_BINDING is not None
            and A2_GPU_BINDING.get("mode") == _A2_MGPU_BINDING_MODE
            and callback_target
            == "gr00t.rl.trl.callbacks.model_save_callback.ModelSaveCallback"
        ):
            callback_config = OmegaConf.create(OmegaConf.to_container(callback, resolve=False))
            callback_config.save_dir = str(rank_root)
        callbacks.append(instantiate(callback_config))

    # --- Save config and initialize trainer ---
    if accelerator.is_main_process:
        experiment_save_dir.mkdir(exist_ok=True, parents=True)
        logger.info(f"Saving config files to {experiment_save_dir}")
        save_training_config_snapshots(config, experiment_save_dir, unresolved_conf)
        meta = {"wandb_run": wandb.run.id if wandb_run_exists() else None}
        yaml.safe_dump(meta, open(meta_path, "w"))
        print("saved meta:", meta)

    checkpoint_load_kwargs = {}
    if trainer_target in (_A2_BASE_API_TRAINER_TARGET, _A2_GRPO_TRAINER_TARGET):
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
        log_dir=rank_root,
        accelerator=accelerator,
        _resolve=False,
        **checkpoint_load_kwargs,
    )

    if p2_step0_manifest is not None:
        if p2_optimizer_parameter_order is None:
            raise RuntimeError("P2 optimizer parameter order was not captured before trainer construction")
        finalized_step0 = _finalize_p2_step0_optimizer_schema(
            p2_common_init_config.get("step0_manifest_path"),
            trainer,
            p2_optimizer_parameter_order,
        )
        if p2_active_parameter_tracker is None:
            raise RuntimeError("P2 optimizer schema finalization requires the gradient-activity tracker")
        p2_active_parameter_tracker.bind_optimizer_schema(finalized_step0["optimizer_parameter_schema"])

    if p2_lifecycle_config is not None and p2_lifecycle_config.get("enabled") is True:
        if p2_common_init_config is not None and p2_common_init_config.get("enabled") is True:
            _install_p2_lifecycle_guard(
                trainer,
                branch=str(p2_common_init_config.get("branch")),
                branch_root=config.experiment_dir,
                common_artifact_path=p2_common_init_config.get("artifact_path"),
                step0_manifest_path=p2_common_init_config.get("step0_manifest_path"),
                runtime_identity=p2_common_init_config.get("runtime_identity", {}),
                target_global_step=p2_lifecycle_target,
                expected_optimizer_state_step=p2_expected_optimizer_state_step,
                active_parameter_tracker=p2_active_parameter_tracker,
            )
        else:
            trainer._a2_mgpu_runner_mode = str(config.algo.config.get("mgpu_runner_mode", "formal"))
            _install_mgpu_lifecycle_contract(
                trainer,
                target_global_step=p2_lifecycle_target,
                binding=A2_GPU_BINDING,
            )

    # --- Training loop ---
    try:
        trainer.train()
        if A2_GPU_BINDING is not None and A2_GPU_BINDING.get("mode") == _A2_MGPU_BINDING_MODE:
            _seal_a2_mgpu_rank_evidence(
                trainer,
                experiment_root=experiment_root,
                rank_root=rank_root,
                binding=A2_GPU_BINDING,
                target_global_step=p2_lifecycle_target,
                fresh_init=fresh_ddp_init,
            )
    except BaseException as exc:
        rank = A2_GPU_BINDING.get("rank", "unknown") if A2_GPU_BINDING is not None else "unknown"
        print(
            f"[A2_TRAIN_EXCEPTION] rank={rank} type={type(exc).__name__} message={exc}",
            file=sys.stderr,
            flush=True,
        )
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
        raise
    finally:
        if simulator_type == "IsaacSim":
            _close_simulation_app(
                simulation_app,
                config.simulator.config.render_results,
            )


if __name__ == "__main__":
    main()
