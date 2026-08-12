"""v23 Route-A canonical16 build, run, and index controller.

Route A is deliberately mechanical: after a formal sub-wave barrier it builds
the four cells in that sub-wave at steps 250 through 2500, evaluates each on
canonical16, and seals 40 strict rows (640 episode records).  Each independent
row runner uses one visible physical GPU and never retries a failed row.
Selection is implemented separately in :mod:`route_a_selection`.
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
        V23_D0_SOURCE_CONFIG,
        V23_FORMAL_CELL_CONFIGS,
        V23_GPU_SUBWAVES,
        V23_GPU_SLICES,
        V23_LAUNCHER_ROOT,
        V23_PLAN_ID,
        V23_ROUTE_A_STEPS,
        V23_TRAINING_ROOT,
        V23Error,
        read_json,
        require_file,
        write_json,
    )
    from .formal_launcher import (
        D1_RECEIPT_PATH,
        FORMAL_CELL_RECORD_SCHEMA,
        CELL_RECORD_STATUS,
        FORMAL_SLICE_RECORD_SCHEMA,
        SLICE_RECORD_STATUS,
        FORMAL_SUBWAVE_RECORD_SCHEMA,
        SUBWAVE_RECORD_STATUS,
        D1_LITE_REPLICATION_LABEL,
        _record_d1_binding,
        _validate_d1_variant,
    )
except ImportError:  # direct ``python scriptsFORhuman/v23/m22.py``
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from scriptsFORhuman.v23._v23_common import (
        REPO_ROOT,
        V23_CELL_FACTORS,
        V23_D0_SOURCE_CONFIG,
        V23_FORMAL_CELL_CONFIGS,
        V23_GPU_SUBWAVES,
        V23_GPU_SLICES,
        V23_LAUNCHER_ROOT,
        V23_PLAN_ID,
        V23_ROUTE_A_STEPS,
        V23_TRAINING_ROOT,
        V23Error,
        read_json,
        require_file,
        write_json,
    )
    from scriptsFORhuman.v23.formal_launcher import (
        D1_RECEIPT_PATH,
        FORMAL_CELL_RECORD_SCHEMA,
        CELL_RECORD_STATUS,
        FORMAL_SLICE_RECORD_SCHEMA,
        SLICE_RECORD_STATUS,
        FORMAL_SUBWAVE_RECORD_SCHEMA,
        SUBWAVE_RECORD_STATUS,
        D1_LITE_REPLICATION_LABEL,
        _record_d1_binding,
        _validate_d1_variant,
    )


PROJECT_PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
EVAL_EXPERIMENT = "wbmanip/door_open_a2_base_lstm"
ROUTE_A_ROOT = REPO_ROOT / "logs_eval/base_v23/route_a"
ROUTE_A_TOPOLOGY = "canonical16"
ROUTE_A_ENVS = 16
ROUTE_A_EPISODES = 16
ROW_SCHEMA = "a2_piper_v23_route_a_row_receipt_v1"
MANIFEST_SCHEMA = "a2_piper_v23_route_a_manifest_v1"
INDEX_SCHEMA = "a2_piper_v23_route_a_evidence_index_v1"
MANIFEST_ROW_STATUS = "ROW_READY"
# Route-A rows are independently launchable on the eight physical GPUs.  This
# is intentionally local to this controller: the formal training launcher
# retains its separate training GPU lease.
ROUTE_A_LEGAL_PHYSICAL_GPUS = (0, 1, 2, 3, 4, 5, 6, 7)


class RouteAError(V23Error):
    """A v23 Route-A artifact or runtime contract is invalid."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _absolute(path: str | Path) -> Path:
    value = Path(path)
    return value if value.is_absolute() else REPO_ROOT / value


def _load_object(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise RouteAError(f"required Route-A artifact is missing: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RouteAError(f"Route-A artifact is not valid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise RouteAError(f"Route-A artifact must be a JSON object: {path}")
    return payload


def _write(path: Path, payload: Mapping[str, Any]) -> Path:
    return write_json(path, payload)


def _subwave_spec(subwave: str) -> Mapping[str, Any]:
    if subwave not in V23_GPU_SUBWAVES:
        raise RouteAError(f"unknown scientific sub-wave: {subwave}")
    return V23_GPU_SUBWAVES[subwave]


def _route_root(subwave: str) -> Path:
    spec = _subwave_spec(subwave)
    return ROUTE_A_ROOT / f"seed{spec['seed']}" / subwave


def _barrier_path(subwave: str) -> Path:
    spec = _subwave_spec(subwave)
    return REPO_ROOT / V23_LAUNCHER_ROOT / f"seed{spec['seed']}" / subwave / "subwave_record.json"


def _scenario_path(cell: str) -> Path:
    if V23_CELL_FACTORS[cell]["door_regime"] == "D0":
        return REPO_ROOT / V23_D0_SOURCE_CONFIG
    return D1_RECEIPT_PATH


def _require_barrier(subwave: str) -> dict[str, Any]:
    path = _barrier_path(subwave)
    barrier = _load_object(path)
    if barrier.get("schema") != FORMAL_SUBWAVE_RECORD_SCHEMA or barrier.get("status") != SUBWAVE_RECORD_STATUS:
        raise RouteAError(f"formal sub-wave barrier is not complete: {path}")
    spec = _subwave_spec(subwave)
    if barrier.get("subwave") != subwave or barrier.get("seed") != spec["seed"]:
        raise RouteAError(f"formal sub-wave barrier identity disagrees: {path}")
    if barrier.get("cells") != list(spec["cells"]) or barrier.get("route_a_admission") is not True:
        raise RouteAError(f"formal sub-wave barrier does not admit Route A: {path}")
    _sealed_cell_bindings(barrier, subwave)
    return barrier


def _sealed_cell_bindings(
    barrier: Mapping[str, Any],
    subwave: str,
) -> dict[str, dict[str, str | None]]:
    """Derive each Route-A cell identity from its immutable barrier records."""

    spec = _subwave_spec(subwave)
    slice_records = barrier.get("slice_records")
    if not isinstance(slice_records, list) or len(slice_records) != len(spec["slices"]):
        raise RouteAError(f"formal sub-wave barrier has no exact slice records: {subwave}")
    bindings: dict[str, dict[str, str | None]] = {}
    observed_cells: list[str] = []
    for slice_record, slice_name in zip(slice_records, spec["slices"]):
        if not isinstance(slice_record, Mapping):
            raise RouteAError(f"formal sub-wave barrier slice is not an object: {subwave}/{slice_name}")
        slice_spec = V23_GPU_SLICES[slice_name]
        if slice_record.get("slice") != slice_name or slice_record.get("subwave") != subwave:
            raise RouteAError(f"formal sub-wave barrier slice identity disagrees: {subwave}/{slice_name}")
        if (
            slice_record.get("schema") != FORMAL_SLICE_RECORD_SCHEMA
            or slice_record.get("status") != SLICE_RECORD_STATUS
            or slice_record.get("natural_completion") is not True
            or slice_record.get("seed") != spec["seed"]
            or slice_record.get("cell_count") != 2
        ):
            raise RouteAError(f"formal sub-wave barrier slice status disagrees: {subwave}/{slice_name}")
        expected_slice_cells = slice_spec["cells"]
        if slice_record.get("cells") != list(expected_slice_cells):
            raise RouteAError(f"formal sub-wave barrier slice cell order disagrees: {subwave}/{slice_name}")
        cell_records = slice_record.get("cell_records")
        if not isinstance(cell_records, list) or len(cell_records) != len(expected_slice_cells):
            raise RouteAError(f"formal sub-wave barrier has no exact cell records: {subwave}/{slice_name}")
        for cell_record, cell in zip(cell_records, expected_slice_cells):
            if not isinstance(cell_record, Mapping):
                raise RouteAError(f"formal cell record is not an object: {subwave}/{cell}")
            if (
                cell_record.get("schema") != FORMAL_CELL_RECORD_SCHEMA
                or cell_record.get("status") != CELL_RECORD_STATUS
                or cell_record.get("natural_completion") is not True
                or cell_record.get("subwave") != subwave
                or cell_record.get("seed") != spec["seed"]
                or cell_record.get("slice") != slice_name
                or cell_record.get("cell") != cell
                or cell_record.get("factors") != dict(V23_CELL_FACTORS[cell])
            ):
                raise RouteAError(f"formal cell record identity disagrees: {subwave}/{cell}")
            variant, label = _record_d1_binding(
                cell_record,
                subwave=subwave,
                seed=spec["seed"],
                cell=cell,
                allow_legacy_a1=True,
            )
            bindings[cell] = {
                "d1_variant": variant,
                "replication_label": label,
            }
            observed_cells.append(cell)
    if observed_cells != list(spec["cells"]):
        raise RouteAError(f"formal sub-wave barrier cell order disagrees: {subwave}")
    return bindings


def _training_checkpoint(seed: int, cell: str, step: int) -> Path:
    return REPO_ROOT / V23_TRAINING_ROOT / f"seed{seed}" / cell / f"model_step_{step:06d}.pt"


def _evaluation_root(subwave: str, cell: str, step: int) -> Path:
    spec = _subwave_spec(subwave)
    return _route_root(subwave) / cell / f"step{step:04d}" / ROUTE_A_TOPOLOGY


def _eval_command(
    subwave: str,
    cell: str,
    step: int,
    checkpoint: Path,
    output: Path,
    *,
    d1_variant: str,
) -> list[str]:
    spec = _subwave_spec(subwave)
    seed = int(spec["seed"])
    variant = _validate_d1_variant(
        d1_variant,
        subwave=subwave,
        seed=seed,
        cell=cell,
        door_regime=V23_CELL_FACTORS[cell]["door_regime"],
    )
    config = V23_FORMAL_CELL_CONFIGS[cell]
    command = [
        str(PROJECT_PYTHON),
        "-m",
        "gr00t.rl.eval_agent_trl",
        f"+exp={EVAL_EXPERIMENT}",
        f"+ablation=wbmanip/{Path(config).stem}",
        f"++checkpoint={checkpoint}",
        "++checkpoint_load_mode=policy_only",
        "++auto_load_latest=false",
        "++headless=true",
        f"++num_envs={ROUTE_A_ENVS}",
        "++num_gpus=1",
        "++multi_gpu=false",
        f"++seed={seed}",
        "++use_wandb=false",
        "++simulator.config.cameras.enable_cameras=false",
        "++simulator.config.render_results=false",
        f"++algo.config.eval.num_eval_episodes={ROUTE_A_EPISODES}",
        "++algo.config.eval.eval_num_envs_episodes=true",
        "++algo.config.eval.a2_diagnostic_trace_enabled=true",
        "++env.config.a2_v23_route_a_unsafe_contact_enabled=true",
        "++algo.config.eval.a2_v23_route_a_unsafe_contact_export=true",
        "++algo.config.eval.save_videos=false",
        "++algo.config.eval.save_trajectories=false",
        f"++eval_output_dir={output}",
        f"++v23_route_a_subwave={subwave}",
        f"++v23_route_a_cell={cell}",
        f"++v23_route_a_step={step}",
        "++env.config.a2_v23_warm_head_reset_enabled=false",
        "++env.config.a2_v23_formal_launch=false",
    ]
    if variant == "lite":
        command.extend(
            [
                "env.config.a2_v23_d1_variant=lite",
                f"++v23_d1_replication_label={D1_LITE_REPLICATION_LABEL}",
            ]
        )
    return command


def _validate_physical_gpus(values: Any) -> tuple[int, ...]:
    if not isinstance(values, (list, tuple)) or not values:
        raise RouteAError("Route-A physical GPU mapping must be a nonempty list")
    if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
        raise RouteAError("Route-A physical GPU mapping must contain integers")
    if any(value not in ROUTE_A_LEGAL_PHYSICAL_GPUS for value in values):
        raise RouteAError(
            f"Route-A physical GPU mapping must be an ordered subset of {ROUTE_A_LEGAL_PHYSICAL_GPUS}"
        )
    if len(set(values)) != len(values):
        raise RouteAError("Route-A physical GPU mapping must not contain duplicates")
    return tuple(values)


def _parse_physical_gpus(raw: str | None) -> tuple[int, ...]:
    if raw is None:
        return ROUTE_A_LEGAL_PHYSICAL_GPUS
    tokens = raw.split(",")
    if any(not token.strip() for token in tokens):
        raise RouteAError("--physical-gpus must be a comma-separated nonempty list")
    try:
        values = tuple(int(token.strip()) for token in tokens)
    except ValueError as exc:
        raise RouteAError("--physical-gpus must contain only integer GPU indices") from exc
    return _validate_physical_gpus(values)


def _row_manifest(
    subwave: str,
    cell: str,
    step: int,
    row_ordinal: int,
    physical_gpus: Sequence[int],
    d1_variant: str,
    replication_label: str | None,
) -> dict[str, Any]:
    spec = _subwave_spec(subwave)
    checkpoint = _training_checkpoint(spec["seed"], cell, step)
    require_file(checkpoint, label=f"{cell} step {step} checkpoint")
    output = _evaluation_root(subwave, cell, step)
    gpu = physical_gpus[row_ordinal % len(physical_gpus)]
    variant = _validate_d1_variant(
        d1_variant,
        subwave=subwave,
        seed=int(spec["seed"]),
        cell=cell,
        door_regime=V23_CELL_FACTORS[cell]["door_regime"],
    )
    expected_label = D1_LITE_REPLICATION_LABEL if variant == "lite" else None
    if replication_label != expected_label:
        raise RouteAError(f"Route-A cell binding label disagrees: {subwave}/{cell}")
    return {
        "row_id": f"{cell}:step{step:04d}",
        "schema": ROW_SCHEMA,
        "status": MANIFEST_ROW_STATUS,
        "source_branch": "A2_Piper",
        "plan_id": V23_PLAN_ID,
        "identity_policy": "OWNER_NO_HASH_PATH_IDENTITY",
        "subwave": subwave,
        "seed": spec["seed"],
        "cell": cell,
        "step": step,
        "d1_variant": variant,
        "replication_label": replication_label,
        "physical_gpu": gpu,
        "logical_gpu": "cuda:0",
        "topology": ROUTE_A_TOPOLOGY,
        "checkpoint_path": str(checkpoint),
        "checkpoint_load_mode": "policy_only",
        "config_path": str(REPO_ROOT / V23_FORMAL_CELL_CONFIGS[cell]),
        "scenario_path": str(_scenario_path(cell)),
        "evaluation_root": str(output),
        "command": _eval_command(
            subwave,
            cell,
            step,
            checkpoint,
            output,
            d1_variant=variant,
        ),
        "environment": {
            "CUDA_DEVICE_ORDER": "PCI_BUS_ID",
            "CUDA_VISIBLE_DEVICES": str(gpu),
            "ACCELERATE_TORCH_DEVICE": "cuda:0",
            "WANDB_MODE": "disabled",
        },
    }


def build(subwave: str, *, physical_gpus: Sequence[int] | None = None) -> dict[str, Any]:
    barrier = _require_barrier(subwave)
    spec = _subwave_spec(subwave)
    cell_bindings = _sealed_cell_bindings(barrier, subwave)
    selected_gpus = _validate_physical_gpus(
        ROUTE_A_LEGAL_PHYSICAL_GPUS if physical_gpus is None else physical_gpus
    )
    rows = []
    for cell in spec["cells"]:
        for step in V23_ROUTE_A_STEPS:
            binding = cell_bindings[cell]
            rows.append(
                _row_manifest(
                    subwave,
                    cell,
                    step,
                    len(rows),
                    selected_gpus,
                    binding["d1_variant"],
                    binding["replication_label"],
                )
            )
    expected = len(spec["cells"]) * len(V23_ROUTE_A_STEPS)
    if len(rows) != expected or expected != 40:
        raise RouteAError(f"Route-A row cardinality is {len(rows)}, expected 40")
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "status": "BUILT",
        "recorded_at_utc": _now(),
        "source_branch": "A2_Piper",
        "plan_id": V23_PLAN_ID,
        "identity_policy": "OWNER_NO_HASH_PATH_IDENTITY",
        "route": "A",
        "subwave": subwave,
        "seed": spec["seed"],
        "cells": list(spec["cells"]),
        "steps": list(V23_ROUTE_A_STEPS),
        "topology": ROUTE_A_TOPOLOGY,
        "num_envs": ROUTE_A_ENVS,
        "episodes_per_row": ROUTE_A_EPISODES,
        "expected_checkpoint_evals": 40,
        "expected_episode_records": 640,
        "physical_gpus": list(selected_gpus),
        "max_live_eval_processes": len(selected_gpus),
        "cell_bindings": cell_bindings,
        "formal_barrier": str(_barrier_path(subwave)),
        "barrier_record": barrier,
        "row_count": len(rows),
        "rows": rows,
    }
    _validate_manifest(subwave, manifest)
    root = _route_root(subwave)
    if root.exists() and any(root.iterdir()):
        raise RouteAError(f"Route-A root is not empty; refusing overwrite: {root}")
    root.mkdir(parents=True, exist_ok=True)
    queue = {
        "schema": "a2_piper_v23_route_a_queue_v1",
        "status": "BUILT",
        "recorded_at_utc": _now(),
        "subwave": subwave,
        "row_count": len(rows),
        "physical_gpus": list(selected_gpus),
        "max_live_eval_processes": len(selected_gpus),
        "cell_bindings": cell_bindings,
        "rows": [
            {
                "row_id": row["row_id"],
                "physical_gpu": row["physical_gpu"],
                "evaluation_root": row["evaluation_root"],
                "d1_variant": row["d1_variant"],
                "replication_label": row["replication_label"],
            }
            for row in rows
        ],
        "scheduling": (
            f"independent row jobs on physical GPUs {','.join(str(gpu) for gpu in selected_gpus)}; "
            "all-row serial barrier stops on first nonzero exit or validation failure; no retry"
        ),
    }
    _write(root / "V23_ROUTE_A_MANIFEST.json", manifest)
    _write(root / "V23_ROUTE_A_QUEUE.json", queue)
    _write(root / "V23_ROUTE_A_RUNTIME_PLAN.json", {
        "schema": "a2_piper_v23_route_a_runtime_plan_v1",
        "status": "READY",
        "recorded_at_utc": _now(),
        "source_branch": "A2_Piper",
        "plan_id": V23_PLAN_ID,
        "identity_policy": "OWNER_NO_HASH_PATH_IDENTITY",
        "subwave": subwave,
        "cuda_device_order": "PCI_BUS_ID",
        "logical_gpu": "cuda:0",
        "max_live_training_processes": 0,
        "physical_gpus": list(selected_gpus),
        "cell_bindings": cell_bindings,
        "max_live_eval_processes": len(selected_gpus),
        "checkpoint_load_mode": "policy_only",
        "no_concurrent_training": True,
        "row_count": len(rows),
    })
    return manifest


def _load_manifest(subwave: str) -> dict[str, Any]:
    path = _route_root(subwave) / "V23_ROUTE_A_MANIFEST.json"
    manifest = _load_object(path)
    _validate_manifest(subwave, manifest, path=path)
    return manifest


def _validate_manifest(subwave: str, manifest: Mapping[str, Any], *, path: Path | None = None) -> None:
    source = path or Path(f"<in-memory:{subwave}:manifest>")
    spec = _subwave_spec(subwave)
    barrier = _require_barrier(subwave)
    cell_bindings = _sealed_cell_bindings(barrier, subwave)
    manifest_gpus = _validate_physical_gpus(manifest.get("physical_gpus"))
    expected_top_level = {
        "schema": MANIFEST_SCHEMA,
        "status": "BUILT",
        "source_branch": "A2_Piper",
        "plan_id": V23_PLAN_ID,
        "identity_policy": "OWNER_NO_HASH_PATH_IDENTITY",
        "route": "A",
        "subwave": subwave,
        "seed": spec["seed"],
        "cells": list(spec["cells"]),
        "steps": list(V23_ROUTE_A_STEPS),
        "topology": ROUTE_A_TOPOLOGY,
        "num_envs": ROUTE_A_ENVS,
        "episodes_per_row": ROUTE_A_EPISODES,
        "expected_checkpoint_evals": 40,
        "expected_episode_records": 640,
        "physical_gpus": list(manifest_gpus),
        "max_live_eval_processes": len(manifest_gpus),
        "cell_bindings": cell_bindings,
        "row_count": 40,
    }
    for key, expected in expected_top_level.items():
        if manifest.get(key) != expected:
            raise RouteAError(f"Route-A manifest {source} field {key} disagrees")
    rows = manifest.get("rows")
    if not isinstance(rows, list) or len(rows) != 40:
        raise RouteAError(f"Route-A manifest must contain exactly 40 rows: {source}")
    expected_pairs = {(cell, step) for cell in spec["cells"] for step in V23_ROUTE_A_STEPS}
    observed_ids: set[str] = set()
    observed_pairs: set[tuple[str, int]] = set()
    for row_index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise RouteAError(f"Route-A manifest row {row_index} is not an object: {source}")
        cell = row.get("cell")
        step = row.get("step")
        if cell not in spec["cells"] or step not in V23_ROUTE_A_STEPS:
            raise RouteAError(f"Route-A manifest row {row_index} has an invalid cell/step: {source}")
        binding = cell_bindings[cell]
        expected_checkpoint = _training_checkpoint(spec["seed"], cell, step)
        expected_output = _evaluation_root(subwave, cell, step)
        expected_gpu = manifest_gpus[row_index % len(manifest_gpus)]
        expected_row = {
            "row_id": f"{cell}:step{step:04d}",
            "schema": ROW_SCHEMA,
            "status": MANIFEST_ROW_STATUS,
            "source_branch": "A2_Piper",
            "plan_id": V23_PLAN_ID,
            "identity_policy": "OWNER_NO_HASH_PATH_IDENTITY",
            "subwave": subwave,
            "seed": spec["seed"],
            "cell": cell,
            "step": step,
            "d1_variant": binding["d1_variant"],
            "replication_label": binding["replication_label"],
            "physical_gpu": expected_gpu,
            "logical_gpu": "cuda:0",
            "topology": ROUTE_A_TOPOLOGY,
            "checkpoint_path": str(expected_checkpoint),
            "checkpoint_load_mode": "policy_only",
            "config_path": str(REPO_ROOT / V23_FORMAL_CELL_CONFIGS[cell]),
            "scenario_path": str(_scenario_path(cell)),
            "evaluation_root": str(expected_output),
            "environment": {
                "CUDA_DEVICE_ORDER": "PCI_BUS_ID",
                "CUDA_VISIBLE_DEVICES": str(expected_gpu),
                "ACCELERATE_TORCH_DEVICE": "cuda:0",
                "WANDB_MODE": "disabled",
            },
        }
        for key, expected in expected_row.items():
            if row.get(key) != expected:
                raise RouteAError(f"Route-A manifest row {row_index} field {key} disagrees: {source}")
        expected_command = _eval_command(
            subwave,
            cell,
            step,
            expected_checkpoint,
            expected_output,
            d1_variant=binding["d1_variant"],
        )
        if row.get("command") != expected_command:
            raise RouteAError(f"Route-A manifest row {row_index} command disagrees: {source}")
        row_id = expected_row["row_id"]
        pair = (cell, step)
        if row_id in observed_ids:
            raise RouteAError(f"Route-A manifest has duplicate row_id {row_id!r}: {source}")
        if pair in observed_pairs:
            raise RouteAError(f"Route-A manifest has duplicate cell/step pair {pair!r}: {source}")
        observed_ids.add(row_id)
        observed_pairs.add(pair)
    if observed_pairs != expected_pairs:
        raise RouteAError(f"Route-A manifest cell/step coverage is not exact: {source}")
    if manifest.get("formal_barrier") != str(_barrier_path(subwave)):
        raise RouteAError(f"Route-A manifest formal barrier path disagrees: {source}")
    if manifest.get("barrier_record") != barrier:
        raise RouteAError(f"Route-A manifest barrier record disagrees: {source}")


def _expected_receipt_fields(row: Mapping[str, Any]) -> dict[str, Any]:
    root_value = row["evaluation_root"]
    root = Path(root_value)
    return {
        "schema": ROW_SCHEMA,
        "status": "ROW_PASS",
        "row_id": row["row_id"],
        "source_branch": row["source_branch"],
        "plan_id": row["plan_id"],
        "identity_policy": row["identity_policy"],
        "subwave": row["subwave"],
        "seed": row["seed"],
        "cell": row["cell"],
        "step": row["step"],
        "d1_variant": row["d1_variant"],
        "replication_label": row["replication_label"],
        "topology": row["topology"],
        "physical_gpu": row["physical_gpu"],
        "logical_gpu": "cuda:0",
        "checkpoint_path": row["checkpoint_path"],
        "checkpoint_load_mode": "policy_only",
        "config_path": row["config_path"],
        "scenario_path": row["scenario_path"],
        "evaluation_root": root_value,
        "records_path": str(root / "a2_v14_per_env_records.json"),
        "raw_trace_path": str(root / "stage2_step_trace.json"),
        "episode_record_count": ROUTE_A_ENVS,
        "trace_env_ids": list(range(ROUTE_A_ENVS)),
        "metrics_completed_episodes": ROUTE_A_EPISODES,
    }


def _validate_receipt_binding(row: Mapping[str, Any], receipt: Mapping[str, Any], *, path: Path) -> None:
    for key, expected in _expected_receipt_fields(row).items():
        if receipt.get(key) != expected:
            raise RouteAError(f"Route-A receipt {path} field {key} disagrees with manifest row {row['row_id']!r}")


def _json_any(path: Path) -> Any:
    if path.is_symlink() or not path.is_file():
        raise RouteAError(f"Route-A row evidence is missing: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RouteAError(f"Route-A row evidence is not valid JSON: {path}") from exc


def _validate_row(row: Mapping[str, Any], *, process: Mapping[str, Any]) -> dict[str, Any]:
    root = Path(row["evaluation_root"])
    metrics = _json_any(root / "metrics_eval.json")
    records = _json_any(root / "a2_v14_per_env_records.json")
    trace = _json_any(root / "stage2_step_trace.json")
    if not isinstance(metrics, Mapping):
        raise RouteAError(f"metrics_eval.json must be an object: {root}")
    if not isinstance(records, list) or len(records) != ROUTE_A_ENVS:
        raise RouteAError(f"Route-A row must contain exactly 16 episode records: {root}")
    if not isinstance(trace, list) or not trace:
        raise RouteAError(f"Route-A raw trace is empty: {root}")
    ids = sorted(record.get("env_id") for record in records)
    if ids != list(range(ROUTE_A_ENVS)):
        raise RouteAError(f"Route-A episode records do not cover env ids 0..15: {root}")
    trace_ids = {entry.get("env_id") for entry in trace if isinstance(entry, Mapping)}
    if trace_ids != set(range(ROUTE_A_ENVS)):
        raise RouteAError(f"Route-A raw trace does not cover env ids 0..15: {root}")
    if metrics.get("completed_episodes") != ROUTE_A_EPISODES:
        raise RouteAError(f"Route-A metrics must report completed_episodes=16: {root}")
    receipt = {
        "schema": ROW_SCHEMA,
        "status": "ROW_PASS",
        "recorded_at_utc": _now(),
        "row_id": row["row_id"],
        "source_branch": row["source_branch"],
        "plan_id": row["plan_id"],
        "identity_policy": row["identity_policy"],
        "subwave": row["subwave"],
        "seed": row["seed"],
        "cell": row["cell"],
        "step": row["step"],
        "d1_variant": row["d1_variant"],
        "replication_label": row["replication_label"],
        "topology": row["topology"],
        "physical_gpu": row["physical_gpu"],
        "logical_gpu": "cuda:0",
        "checkpoint_path": row["checkpoint_path"],
        "checkpoint_load_mode": "policy_only",
        "config_path": row["config_path"],
        "scenario_path": row["scenario_path"],
        "evaluation_root": str(root),
        "episode_record_count": len(records),
        "trace_row_count": len(trace),
        "trace_env_ids": sorted(trace_ids),
        "metrics_completed_episodes": metrics["completed_episodes"],
        "process": dict(process),
        "records_path": str(root / "a2_v14_per_env_records.json"),
        "raw_trace_path": str(root / "stage2_step_trace.json"),
    }
    _validate_receipt_binding(row, receipt, path=root / "row_receipt.json")
    _write(root / "row_receipt.json", receipt)
    return receipt


def run(subwave: str, *, only_row: str | None = None) -> dict[str, Any]:
    manifest = _load_manifest(subwave)
    rows = {row["row_id"]: row for row in manifest["rows"]}
    if only_row is not None and only_row not in rows:
        raise RouteAError(f"unknown Route-A row: {only_row}")
    selected = [rows[only_row]] if only_row else list(manifest["rows"])
    completed: list[str] = []
    for row in selected:
        root = Path(row["evaluation_root"])
        receipt_path = root / "row_receipt.json"
        if receipt_path.is_file() and not receipt_path.is_symlink():
            receipt = _load_object(receipt_path)
            _validate_receipt_binding(row, receipt, path=receipt_path)
            completed.append(row["row_id"])
            continue
        if root.exists():
            raise RouteAError(f"Route-A row output exists without a sealed receipt: {root}")
        root.mkdir(parents=True, exist_ok=False)
        stdout_path = root / "runtime_stdout.log"
        stderr_path = root / "runtime_stderr.log"
        env = os.environ.copy()
        env["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
        env["CUDA_VISIBLE_DEVICES"] = str(row["physical_gpu"])
        env["ACCELERATE_TORCH_DEVICE"] = "cuda:0"
        env["WANDB_MODE"] = "disabled"
        started = _now()
        with stdout_path.open("x", encoding="utf-8") as stdout, stderr_path.open("x", encoding="utf-8") as stderr:
            process = subprocess.Popen(row["command"], cwd=REPO_ROOT, env=env, stdout=stdout, stderr=stderr)
            return_code = process.wait()
        ended = _now()
        process_record = {
            "pid": process.pid,
            "started_at_utc": started,
            "ended_at_utc": ended,
            "return_code": return_code,
            "natural_completion": return_code == 0,
        }
        if return_code != 0:
            raise RouteAError(f"Route-A row {row['row_id']} exited {return_code}; no retry")
        _validate_row(row, process=process_record)
        completed.append(row["row_id"])
    result = {
        "schema": "a2_piper_v23_route_a_run_result_v1",
        "status": "PASS",
        "recorded_at_utc": _now(),
        "subwave": subwave,
        "seed": manifest["seed"],
        "cells": list(manifest["cells"]),
        "cell_bindings": manifest["cell_bindings"],
        "row_count": len(completed),
        "completed_rows": completed,
        "no_retry": True,
    }
    result_path = (
        Path(selected[0]["evaluation_root"]) / "V23_ROUTE_A_RUN_RESULT.json"
        if only_row
        else _route_root(subwave) / "V23_ROUTE_A_RUN_RESULT.json"
    )
    _write(result_path, result)
    return result


def index(subwave: str) -> dict[str, Any]:
    manifest = _load_manifest(subwave)
    rows: list[dict[str, Any]] = []
    for row in manifest["rows"]:
        receipt_path = Path(row["evaluation_root"]) / "row_receipt.json"
        receipt = _load_object(receipt_path)
        _validate_receipt_binding(row, receipt, path=receipt_path)
        rows.append(dict(receipt))
    expected_pairs = {
        (cell, step)
        for cell in V23_GPU_SUBWAVES[subwave]["cells"]
        for step in V23_ROUTE_A_STEPS
    }
    expected_row_ids = {f"{cell}:step{step:04d}" for cell, step in expected_pairs}
    receipt_ids = {row["row_id"] for row in rows}
    receipt_pairs = {(row["cell"], row["step"]) for row in rows}
    if (
        len(rows) != 40
        or receipt_ids != expected_row_ids
        or len(receipt_ids) != 40
        or receipt_pairs != expected_pairs
        or sum(row["episode_record_count"] for row in rows) != 640
    ):
        raise RouteAError("Route-A index cardinality is not 40 rows / 640 episode records")
    payload = {
        "schema": INDEX_SCHEMA,
        "status": "COMPLETE",
        "recorded_at_utc": _now(),
        "source_branch": "A2_Piper",
        "plan_id": V23_PLAN_ID,
        "identity_policy": "OWNER_NO_HASH_PATH_IDENTITY",
        "route": "A",
        "subwave": subwave,
        "seed": manifest["seed"],
        "cell_bindings": manifest["cell_bindings"],
        "topology": ROUTE_A_TOPOLOGY,
        "cells": list(V23_GPU_SUBWAVES[subwave]["cells"]),
        "steps": list(V23_ROUTE_A_STEPS),
        "row_count": len(rows),
        "episode_record_count": sum(int(row["episode_record_count"]) for row in rows),
        "missing_evidence": [],
        "rows": rows,
    }
    _write(_route_root(subwave) / "V23_ROUTE_A_EVIDENCE_INDEX.json", payload)
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command_arg", nargs="?")
    parser.add_argument("--mode", dest="mode_option")
    parser.add_argument("--subwave", required=True, choices=tuple(V23_GPU_SUBWAVES))
    parser.add_argument("--only-row")
    parser.add_argument("--physical-gpus", dest="physical_gpus")
    args = parser.parse_args(argv)
    command_arg = args.mode_option or args.command_arg
    if command_arg is None:
        parser.error("BUILD, RUN, or INDEX is required")
    command = command_arg.upper()
    try:
        if command == "BUILD":
            payload = build(args.subwave, physical_gpus=_parse_physical_gpus(args.physical_gpus))
        elif command == "RUN":
            if args.physical_gpus is not None:
                raise RouteAError("--physical-gpus is only valid with BUILD")
            payload = run(args.subwave, only_row=args.only_row)
        elif command == "INDEX":
            if args.physical_gpus is not None:
                raise RouteAError("--physical-gpus is only valid with BUILD")
            payload = index(args.subwave)
        else:
            raise RouteAError("command must be BUILD, RUN, or INDEX")
    except V23Error as exc:
        print(f"V23 M22 {command} FAIL: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
