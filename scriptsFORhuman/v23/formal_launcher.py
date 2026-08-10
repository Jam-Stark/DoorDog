"""Fail-fast controller for the v23 formal two-GPU training slices.

The controller has four explicit modes:

``PLAN``
    Materialize the frozen cell/slice order and report the typed admission
    state.  Missing owner receipts are a truthful pending state here.
``RUN_CELL``
    Admit and launch exactly one training child.  The child is never retried
    or auto-resumed; a natural exit is sealed only after the saved config and
    step-2500 trainer state are validated.
``REDUCE_SLICE``
    Consume exactly the two cell records in one D0 or D1 slice.
``REDUCE_SUBWAVE``
    Consume both slice records.  Its barrier is the only formal Route-A
    admission for that scientific sub-wave.

No simulation is performed by ``PLAN``.  Records are plain JSON and contain
no content hashes or digest fields.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from ._v23_common import (
        REPO_ROOT,
        V23_CELL_FACTORS,
        V23_FORMAL_BATCHES,
        V23_FORMAL_CELL_CONFIGS,
        V23_FORMAL_CELL_GPU,
        V23_FORMAL_EXECUTION_ORDER,
        V23_FORMAL_ENVS,
        V23_GPU_SLICES,
        V23_GPU_SUBWAVES,
        V23_LAUNCHER_ROOT,
        V23_D0_SOURCE_CONFIG,
        V23_PLAN_ID,
        V23_SAVE_FREQUENCY,
        V23_TRAINING_ROOT,
        V23_WARM_START_PATH,
        V23Error,
        read_json,
        require_file,
        write_json,
    )
except ImportError:  # direct ``python scriptsFORhuman/v23/formal_launcher.py``
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from scriptsFORhuman.v23._v23_common import (
        REPO_ROOT,
        V23_CELL_FACTORS,
        V23_FORMAL_BATCHES,
        V23_FORMAL_CELL_CONFIGS,
        V23_FORMAL_CELL_GPU,
        V23_FORMAL_EXECUTION_ORDER,
        V23_FORMAL_ENVS,
        V23_GPU_SLICES,
        V23_GPU_SUBWAVES,
        V23_LAUNCHER_ROOT,
        V23_D0_SOURCE_CONFIG,
        V23_PLAN_ID,
        V23_SAVE_FREQUENCY,
        V23_TRAINING_ROOT,
        V23_WARM_START_PATH,
        V23Error,
        read_json,
        require_file,
        write_json,
    )


PROJECT_PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
FORMAL_EXPERIMENT = "wbmanip/door_open_a2_base_lstm"
PROJECT_NAME = "a2_piper_full_stage_a2_base"

D1_RECEIPT_PATH = REPO_ROOT / "logs_eval/base_v23/p0/p04_d1_physics_first_20260810/p04_d1_physics_first.json"
P08_RECEIPT_PATH = REPO_ROOT / "logs_eval/base_v23/p0/interventions/preformal_v2/p08_preformal_v2_receipt.json"
D1_FULL_RECEIPT_PATH = REPO_ROOT / "logs_eval/base_v23/p0/d1_full_64x10/d1_full_64x10_receipt.json"

D1_RECEIPT_SCHEMA = "a2_piper_v23_p04_d1_physics_first_v1"
P08_RECEIPT_SCHEMA = "a2_piper_v23_p08_preformal_v2_receipt_v1"
D1_FULL_RECEIPT_SCHEMA = "a2_piper_v23_d1_full_64x10_receipt_v1"

EXPECTED_D1_STATUS = "P0_4_D1_PHYSICS_FIRST_FREEZE_ADMITTED"
EXPECTED_P08_STATUS = "P0_8_PREFORMAL_COMPLETE"
EXPECTED_D1_FULL_STATUS = "D1_FULL_64X10_BUCKET_PLUMBING_RUNTIME_VERIFIED"

FORMAL_CELL_RECORD_SCHEMA = "a2_piper_v23_formal_cell_record_v1"
FORMAL_SLICE_RECORD_SCHEMA = "a2_piper_v23_formal_slice_record_v1"
FORMAL_SUBWAVE_RECORD_SCHEMA = "a2_piper_v23_formal_subwave_record_v1"

CELL_RECORD_STATUS = "FORMAL_CELL_COMPLETE"
SLICE_RECORD_STATUS = "FORMAL_SLICE_COMPLETE"
SUBWAVE_RECORD_STATUS = "FORMAL_SUBWAVE_COMPLETE"

SLICE_ORDER = tuple(V23_GPU_SLICES)
SUBWAVE_ORDER = tuple(V23_GPU_SUBWAVES)


class FormalLauncherError(V23Error):
    """A formal v23 launch or barrier contract is invalid."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _absolute(path: str | Path) -> Path:
    value = Path(path)
    return value if value.is_absolute() else REPO_ROOT / value


def _load_object(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise FormalLauncherError(f"required formal record is missing: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise FormalLauncherError(f"formal record is not valid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise FormalLauncherError(f"formal record must be a JSON object: {path}")
    return payload


def _write(path: Path, payload: Mapping[str, Any]) -> Path:
    return write_json(path, payload)


def _receipt_specs() -> tuple[dict[str, Any], ...]:
    return (
        {
            "name": "D1_PHYSICS_FIRST",
            "path": D1_RECEIPT_PATH,
            "schema": D1_RECEIPT_SCHEMA,
            "status": EXPECTED_D1_STATUS,
        },
        {
            "name": "P0_8_PREFORMAL_V2",
            "path": P08_RECEIPT_PATH,
            "schema": P08_RECEIPT_SCHEMA,
            "status": EXPECTED_P08_STATUS,
        },
        {
            "name": "D1_FULL_64X10",
            "path": D1_FULL_RECEIPT_PATH,
            "schema": D1_FULL_RECEIPT_SCHEMA,
            "status": EXPECTED_D1_FULL_STATUS,
        },
    )


def inspect_admission() -> dict[str, Any]:
    """Inspect only receipt presence, schema, and pass status.

    Existing malformed/non-pass receipts are represented as typed blocked
    entries in PLAN output.  RUN_CELL turns any such entry into a hard error.
    No other receipt fields are interpreted here.
    """

    entries: list[dict[str, Any]] = []
    for spec in _receipt_specs():
        path = spec["path"]
        if path.is_symlink() or not path.is_file():
            entries.append({"name": spec["name"], "path": str(path), "state": "PENDING_MISSING"})
            continue
        payload = _load_object(path)
        schema = payload.get("schema")
        status = payload.get("status")
        if schema != spec["schema"]:
            state = "BLOCKED_SCHEMA"
        elif status != spec["status"]:
            state = "PENDING_STATUS"
        else:
            state = "PASS"
        entries.append(
            {
                "name": spec["name"],
                "path": str(path),
                "schema": schema,
                "expected_schema": spec["schema"],
                "status": status,
                "expected_status": spec["status"],
                "state": state,
            }
        )
    return {"all_pass": all(item["state"] == "PASS" for item in entries), "receipts": entries}


def require_admission() -> dict[str, Any]:
    admission = inspect_admission()
    if not admission["all_pass"]:
        blocked = [f"{item['name']}={item['state']}" for item in admission["receipts"] if item["state"] != "PASS"]
        raise FormalLauncherError("formal RUN_CELL requires all owner receipts to PASS: " + ", ".join(blocked))
    return admission


def _validate_matrix() -> None:
    if tuple(V23_GPU_SUBWAVES) != SUBWAVE_ORDER:
        raise FormalLauncherError("sub-wave order changed")
    if set(V23_FORMAL_CELL_GPU.values()) != {0, 1}:
        raise FormalLauncherError("formal cell map must use exactly physical GPU0 and GPU1")
    for slice_name, spec in V23_GPU_SLICES.items():
        if tuple(spec["gpus"]) != (0, 1) or len(spec["cells"]) != 2:
            raise FormalLauncherError(f"slice {slice_name} is not a two-cell GPU0/1 slice")
        for cell, expected_gpu in zip(spec["cells"], spec["gpus"]):
            if cell not in V23_CELL_FACTORS:
                raise FormalLauncherError(f"slice {slice_name} contains unknown cell {cell}")
            if V23_CELL_FACTORS[cell]["door_regime"] != spec["door_regime"]:
                raise FormalLauncherError(f"slice {slice_name} door factor disagrees for {cell}")
            if V23_FORMAL_CELL_GPU[cell] != expected_gpu:
                raise FormalLauncherError(f"slice {slice_name} GPU order disagrees for {cell}")


def _output_root(seed: int, cell: str) -> Path:
    return REPO_ROOT / V23_TRAINING_ROOT / f"seed{seed}" / cell


def _record_root(seed: int, cell: str) -> Path:
    return REPO_ROOT / V23_LAUNCHER_ROOT / f"seed{seed}" / cell


def _scenario_path(cell: str) -> Path:
    if V23_CELL_FACTORS[cell]["door_regime"] == "D0":
        return REPO_ROOT / V23_D0_SOURCE_CONFIG
    return D1_RECEIPT_PATH


def _cell_command(cell: str, seed: int) -> list[str]:
    config = V23_FORMAL_CELL_CONFIGS[cell]
    output = _output_root(seed, cell)
    factors = V23_CELL_FACTORS[cell]
    return [
        str(PROJECT_PYTHON),
        "-m",
        "gr00t.rl.train_agent_trl",
        f"+exp={FORMAL_EXPERIMENT}",
        f"+ablation=wbmanip/{Path(config).stem}",
        f"project_name={PROJECT_NAME}",
        f"experiment_name=base_v23_seed{seed}_{cell}",
        f"experiment_dir={output}",
        f"checkpoint={V23_WARM_START_PATH}",
        "checkpoint_load_mode=policy_only",
        "auto_load_latest=false",
        "max_retries=0",
        "headless=true",
        "use_wandb=false",
        "num_envs=4096",
        "num_gpus=1",
        "multi_gpu=false",
        f"seed={seed}",
        f"algo.trl.num_total_batches={V23_FORMAL_BATCHES}",
        f"callbacks.model_save.save_frequency={V23_SAVE_FREQUENCY}",
        "++v23_formal_launch=true",
        f"++v23_cell={cell}",
        f"++v23_seed={seed}",
        f"++v23_initialization={factors['initialization']}",
        f"++v23_door_regime={factors['door_regime']}",
        f"++v23_posture_mode={factors['posture']}",
        "++env.config.a2_v23_formal_launch=true",
    ]


def build_plan(*, output: Path | None = None) -> dict[str, Any]:
    _validate_matrix()
    admission = inspect_admission()
    cells: list[dict[str, Any]] = []
    slices: list[dict[str, Any]] = []
    for subwave_name in SUBWAVE_ORDER:
        subwave = V23_GPU_SUBWAVES[subwave_name]
        for slice_name in subwave["slices"]:
            spec = V23_GPU_SLICES[slice_name]
            slice_row = {
                "slice": slice_name,
                "subwave": subwave_name,
                "seed": spec["seed"],
                "door_regime": spec["door_regime"],
                "cells": list(spec["cells"]),
                "physical_gpus": [0, 1],
            }
            slices.append(slice_row)
            for cell in spec["cells"]:
                gpu = V23_FORMAL_CELL_GPU[cell]
                cells.append(
                    {
                        "subwave": subwave_name,
                        "slice": slice_name,
                        "seed": spec["seed"],
                        "cell": cell,
                        "physical_gpu": gpu,
                        "logical_gpu": "cuda:0",
                        "factors": dict(V23_CELL_FACTORS[cell]),
                        "source_branch": "A2_Piper",
                        "plan_id": V23_PLAN_ID,
                        "identity_policy": "OWNER_NO_HASH_PATH_IDENTITY",
                        "config_path": str(REPO_ROOT / V23_FORMAL_CELL_CONFIGS[cell]),
                        "checkpoint_path": str(REPO_ROOT / V23_WARM_START_PATH),
                        "scenario_path": str(_scenario_path(cell)),
                        "output_root": str(_output_root(spec["seed"], cell)),
                        "launcher_record": str(_record_root(spec["seed"], cell) / "cell_record.json"),
                        "environment": {
                            "CUDA_DEVICE_ORDER": "PCI_BUS_ID",
                            "CUDA_VISIBLE_DEVICES": str(gpu),
                            "ACCELERATE_TORCH_DEVICE": "cuda:0",
                            "WANDB_MODE": "disabled",
                        },
                        "command": _cell_command(cell, spec["seed"]),
                    }
                )
    payload = {
        "schema": "a2_piper_v23_formal_plan_v1",
        "status": "READY_TO_ADMIT" if admission["all_pass"] else "PENDING_TYPED_ADMISSION",
        "recorded_at_utc": _now(),
        "physical_gpus": [0, 1],
        "source_branch": "A2_Piper",
        "plan_id": V23_PLAN_ID,
        "identity_policy": "OWNER_NO_HASH_PATH_IDENTITY",
        "slice_order": list(SLICE_ORDER),
        "subwave_order": list(SUBWAVE_ORDER),
        "execution_order": list(V23_FORMAL_EXECUTION_ORDER),
        "formal_contract": {
            "num_envs": V23_FORMAL_ENVS,
            "num_batches": V23_FORMAL_BATCHES,
            "save_frequency": V23_SAVE_FREQUENCY,
            "num_gpus": 1,
            "multi_gpu": False,
            "logical_gpu": "cuda:0",
            "cuda_device_order": "PCI_BUS_ID",
            "wandb": False,
            "auto_resume": False,
            "retry": False,
        },
        "admission": admission,
        "slices": slices,
        "cells": cells,
    }
    if output is not None:
        _write(output, payload)
    return payload


def _checkpoint_global_step(path: Path) -> int:
    try:
        import torch
    except ImportError as exc:
        raise FormalLauncherError("trainer checkpoint validation requires the IsaacLab Python environment") from exc
    payload = torch.load(path, map_location="cpu", weights_only=False)
    if not isinstance(payload, Mapping):
        raise FormalLauncherError(f"checkpoint is not a mapping: {path}")
    state = payload.get("state")
    if isinstance(state, Mapping):
        state_values = state
    elif type(state).__name__ == "OnlineTrainerState" and hasattr(state, "__dict__"):
        state_values = vars(state)
    else:
        raise FormalLauncherError("checkpoint trainer state must be a mapping or OnlineTrainerState object with __dict__")
    if not isinstance(state_values, Mapping) or state_values.get("global_step") != V23_FORMAL_BATCHES:
        got = state_values.get("global_step") if isinstance(state_values, Mapping) else None
        raise FormalLauncherError(f"checkpoint trainer global_step={got!r}, expected {V23_FORMAL_BATCHES}")
    return int(state_values["global_step"])


def _completion(output: Path) -> tuple[Path, int]:
    config = output / "config.yaml"
    checkpoint = output / "model_step_002500.pt"
    require_file(config, label="formal saved config")
    require_file(checkpoint, label="formal step-2500 checkpoint")
    return checkpoint, _checkpoint_global_step(checkpoint)


def _cell_record(
    *,
    subwave: str,
    slice_name: str,
    seed: int,
    cell: str,
    gpu: int,
    command: Sequence[str],
    output: Path,
    record: Path,
    started: str,
    ended: str,
    pid: int,
    return_code: int,
    checkpoint: Path | None,
    global_step: int | None,
) -> dict[str, Any]:
    complete = return_code == 0 and checkpoint is not None and global_step == V23_FORMAL_BATCHES
    return {
        "schema": FORMAL_CELL_RECORD_SCHEMA,
        "status": CELL_RECORD_STATUS if complete else "FORMAL_CELL_INCOMPLETE",
        "recorded_at_utc": ended,
        "source_branch": "A2_Piper",
        "plan_id": V23_PLAN_ID,
        "identity_policy": "OWNER_NO_HASH_PATH_IDENTITY",
        "subwave": subwave,
        "slice": slice_name,
        "seed": seed,
        "cell": cell,
        "factors": dict(V23_CELL_FACTORS[cell]),
        "physical_gpu": gpu,
        "logical_gpu": "cuda:0",
        "command": list(command),
        "environment": {
            "CUDA_DEVICE_ORDER": "PCI_BUS_ID",
            "CUDA_VISIBLE_DEVICES": str(gpu),
            "ACCELERATE_TORCH_DEVICE": "cuda:0",
            "WANDB_MODE": "disabled",
        },
        "output_root": str(output),
        "config_path": str(output / "config.yaml"),
        "source_config_path": str(REPO_ROOT / V23_FORMAL_CELL_CONFIGS[cell]),
        "checkpoint_path": str(REPO_ROOT / V23_WARM_START_PATH),
        "scenario_path": str(_scenario_path(cell)),
        "pid": pid,
        "started_at_utc": started,
        "ended_at_utc": ended,
        "return_code": return_code,
        "last_checkpoint": str(checkpoint) if checkpoint is not None else None,
        "trainer_global_step": global_step,
        "natural_completion": complete,
        "retry": False,
        "auto_resume": False,
        "record_path": str(record),
    }


def run_cell(*, subwave: str, cell: str) -> dict[str, Any]:
    _validate_matrix()
    admission = require_admission()
    if subwave not in V23_GPU_SUBWAVES:
        raise FormalLauncherError(f"unknown sub-wave: {subwave}")
    subwave_spec = V23_GPU_SUBWAVES[subwave]
    if cell not in subwave_spec["cells"]:
        raise FormalLauncherError(f"{cell} is not a cell in sub-wave {subwave}")
    slice_name = next(name for name in subwave_spec["slices"] if cell in V23_GPU_SLICES[name]["cells"])
    seed = int(subwave_spec["seed"])
    gpu = int(V23_FORMAL_CELL_GPU[cell])
    config_path = REPO_ROOT / V23_FORMAL_CELL_CONFIGS[cell]
    require_file(config_path, label=f"formal config for {cell}")
    require_file(REPO_ROOT / V23_WARM_START_PATH, label="v22 warm checkpoint")
    output = _output_root(seed, cell)
    record_root = _record_root(seed, cell)
    record_path = record_root / "cell_record.json"
    if record_path.exists():
        raise FormalLauncherError(f"cell record already exists; refusing retry/overwrite: {record_path}")
    if output.exists():
        raise FormalLauncherError(f"formal output already exists; refusing retry/auto-resume: {output}")
    output.mkdir(parents=True, exist_ok=False)
    record_root.mkdir(parents=True, exist_ok=True)

    command = _cell_command(cell, seed)
    environment = os.environ.copy()
    environment["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
    environment["CUDA_VISIBLE_DEVICES"] = str(gpu)
    environment["ACCELERATE_TORCH_DEVICE"] = "cuda:0"
    environment["WANDB_MODE"] = "disabled"
    stdout_path = record_root / "stdout.log"
    stderr_path = record_root / "stderr.log"
    started = _now()
    with stdout_path.open("x", encoding="utf-8") as stdout, stderr_path.open("x", encoding="utf-8") as stderr:
        process = subprocess.Popen(command, cwd=REPO_ROOT, env=environment, stdout=stdout, stderr=stderr)
        return_code = process.wait()
    ended = _now()
    checkpoint: Path | None = None
    global_step: int | None = None
    validation_error: str | None = None
    if return_code == 0:
        try:
            checkpoint, global_step = _completion(output)
        except (OSError, V23Error) as exc:
            validation_error = str(exc)
    record = _cell_record(
        subwave=subwave,
        slice_name=slice_name,
        seed=seed,
        cell=cell,
        gpu=gpu,
        command=command,
        output=output,
        record=record_path,
        started=started,
        ended=ended,
        pid=process.pid,
        return_code=return_code,
        checkpoint=checkpoint,
        global_step=global_step,
    )
    if validation_error is not None:
        record["validation_error"] = validation_error
    _write(record_path, record)
    if record["status"] != CELL_RECORD_STATUS:
        raise FormalLauncherError(f"formal cell did not complete: {record}")
    return {"admission": admission, "record": record}


def _cell_record_path(seed: int, cell: str) -> Path:
    return _record_root(seed, cell) / "cell_record.json"


def _validate_cell_record(path: Path, *, expected_seed: int, expected_cell: str, expected_slice: str) -> dict[str, Any]:
    record = _load_object(path)
    if record.get("schema") != FORMAL_CELL_RECORD_SCHEMA:
        raise FormalLauncherError(f"cell record schema mismatch: {path}")
    if record.get("status") != CELL_RECORD_STATUS or record.get("natural_completion") is not True:
        raise FormalLauncherError(f"cell record is not complete: {path}")
    if (
        record.get("source_branch") != "A2_Piper"
        or record.get("plan_id") != V23_PLAN_ID
        or record.get("identity_policy") != "OWNER_NO_HASH_PATH_IDENTITY"
    ):
        raise FormalLauncherError(f"cell record provenance disagrees: {path}")
    for key, expected in (("seed", expected_seed), ("cell", expected_cell), ("slice", expected_slice), ("return_code", 0), ("trainer_global_step", V23_FORMAL_BATCHES)):
        if record.get(key) != expected:
            raise FormalLauncherError(f"cell record {path} field {key}={record.get(key)!r}, expected {expected!r}")
    if record.get("physical_gpu") != V23_FORMAL_CELL_GPU[expected_cell] or record.get("logical_gpu") != "cuda:0":
        raise FormalLauncherError(f"cell record has an illegal device contract: {path}")
    environment = record.get("environment")
    if not isinstance(environment, Mapping) or environment.get("CUDA_DEVICE_ORDER") != "PCI_BUS_ID":
        raise FormalLauncherError(f"cell record CUDA device-order contract is invalid: {path}")
    if environment.get("CUDA_VISIBLE_DEVICES") != str(record["physical_gpu"]):
        raise FormalLauncherError(f"cell record visible-device contract is invalid: {path}")
    if not Path(record.get("last_checkpoint", "")).is_file():
        raise FormalLauncherError(f"cell record last checkpoint is missing: {path}")
    return record


def reduce_slice(*, slice_name: str, records: Sequence[Path] | None = None) -> dict[str, Any]:
    if slice_name not in V23_GPU_SLICES:
        raise FormalLauncherError(f"unknown formal slice: {slice_name}")
    spec = V23_GPU_SLICES[slice_name]
    paths = list(records) if records is not None else [_cell_record_path(spec["seed"], cell) for cell in spec["cells"]]
    if len(paths) != 2:
        raise FormalLauncherError(f"{slice_name} requires exactly two cell records")
    loaded = [_validate_cell_record(path, expected_seed=spec["seed"], expected_cell=cell, expected_slice=slice_name) for path, cell in zip(paths, spec["cells"])]
    target = REPO_ROOT / V23_LAUNCHER_ROOT / f"seed{spec['seed']}" / slice_name / "slice_record.json"
    payload = {
        "schema": FORMAL_SLICE_RECORD_SCHEMA,
        "status": SLICE_RECORD_STATUS,
        "recorded_at_utc": _now(),
        "slice": slice_name,
        "subwave": spec["subwave"],
        "seed": spec["seed"],
        "door_regime": spec["door_regime"],
        "cells": list(spec["cells"]),
        "cell_record_paths": [str(path) for path in paths],
        "cell_records": loaded,
        "cell_count": 2,
        "natural_completion": True,
        "record_path": str(target),
    }
    _write(target, payload)
    return payload


def _slice_record_path(seed: int, slice_name: str) -> Path:
    return REPO_ROOT / V23_LAUNCHER_ROOT / f"seed{seed}" / slice_name / "slice_record.json"


def _validate_slice_record(path: Path, *, expected_slice: str) -> dict[str, Any]:
    record = _load_object(path)
    if record.get("schema") != FORMAL_SLICE_RECORD_SCHEMA or record.get("status") != SLICE_RECORD_STATUS:
        raise FormalLauncherError(f"slice record is not complete: {path}")
    spec = V23_GPU_SLICES[expected_slice]
    for key, expected in (("slice", expected_slice), ("subwave", spec["subwave"]), ("seed", spec["seed"]), ("cells", list(spec["cells"])), ("cell_count", 2)):
        if record.get(key) != expected:
            raise FormalLauncherError(f"slice record {path} field {key} disagrees")
    if record.get("natural_completion") is not True:
        raise FormalLauncherError(f"slice record is not a natural completion: {path}")
    return record


def reduce_subwave(*, subwave: str, records: Sequence[Path] | None = None) -> dict[str, Any]:
    if subwave not in V23_GPU_SUBWAVES:
        raise FormalLauncherError(f"unknown formal sub-wave: {subwave}")
    spec = V23_GPU_SUBWAVES[subwave]
    paths = list(records) if records is not None else [_slice_record_path(spec["seed"], name) for name in spec["slices"]]
    if len(paths) != 2:
        raise FormalLauncherError(f"{subwave} requires exactly two slice records")
    loaded = [_validate_slice_record(path, expected_slice=name) for path, name in zip(paths, spec["slices"])]
    cells = [cell for row in loaded for cell in row["cells"]]
    if cells != list(spec["cells"]):
        raise FormalLauncherError(f"{subwave} slice barrier does not cover the frozen cell order")
    target = REPO_ROOT / V23_LAUNCHER_ROOT / f"seed{spec['seed']}" / subwave / "subwave_record.json"
    payload = {
        "schema": FORMAL_SUBWAVE_RECORD_SCHEMA,
        "status": SUBWAVE_RECORD_STATUS,
        "recorded_at_utc": _now(),
        "subwave": subwave,
        "seed": spec["seed"],
        "slice_order": list(spec["slices"]),
        "slice_record_paths": [str(path) for path in paths],
        "slice_records": loaded,
        "cells": cells,
        "cell_count": 4,
        "route_a_admission": True,
        "natural_completion": True,
        "record_path": str(target),
    }
    _write(target, payload)
    return payload


def _parse_records(values: Sequence[str] | None) -> list[Path] | None:
    if values is None:
        return None
    return [_absolute(value) for value in values]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode_arg", nargs="?", choices=("PLAN", "RUN_CELL", "REDUCE_SLICE", "REDUCE_SUBWAVE"))
    parser.add_argument("--mode", dest="mode_option", choices=("PLAN", "RUN_CELL", "REDUCE_SLICE", "REDUCE_SUBWAVE"))
    parser.add_argument("--subwave", choices=SUBWAVE_ORDER)
    parser.add_argument("--cell")
    parser.add_argument("--slice")
    parser.add_argument("--record", action="append")
    parser.add_argument("--records", nargs="+")
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    mode = args.mode_option or args.mode_arg
    if mode is None:
        parser.error("one of PLAN, RUN_CELL, REDUCE_SLICE, or REDUCE_SUBWAVE is required")
    try:
        if mode == "PLAN":
            payload = build_plan(output=_absolute(args.output) if args.output else REPO_ROOT / V23_LAUNCHER_ROOT / "FORMAL_PLAN.json")
        elif mode == "RUN_CELL":
            if args.subwave is None or args.cell is None:
                raise FormalLauncherError("RUN_CELL requires --subwave and --cell")
            payload = run_cell(subwave=args.subwave, cell=args.cell)
        elif mode == "REDUCE_SLICE":
            if args.slice is None:
                raise FormalLauncherError("REDUCE_SLICE requires --slice")
            record_values = args.records if args.records is not None else args.record
            payload = reduce_slice(slice_name=args.slice, records=_parse_records(record_values))
        else:
            if args.subwave is None:
                raise FormalLauncherError("REDUCE_SUBWAVE requires --subwave")
            record_values = args.records if args.records is not None else args.record
            payload = reduce_subwave(subwave=args.subwave, records=_parse_records(record_values))
    except V23Error as exc:
        print(f"V23 FORMAL {mode} FAIL: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
