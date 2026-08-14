#!/usr/bin/env python3
"""Build and validate the Pull-v5.1 state bank (schema v2).

The builder is intentionally strict: every row must carry closer-force and
capture provenance metadata, failed settle rows are rejected, and the G13
counts are checked before the tensor bank is written.  The optional Source-B
argument is only available for the documented G8 pure-Source-A fallback and
must be requested explicitly.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
from pathlib import Path
from typing import Any, Mapping

import torch


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / (
    "logs_rl/a2_piper_full_stage_a2_pull/pull_v5_state_bank/pull_v5_state_bank.pt"
)
MANIFEST_NAME = "pull_v5_state_bank_manifest.json"
SCHEMA_SOURCE = "a2_piper_pull_v5_state_bank_source_v2"
SCHEMA_BANK = "a2_piper_pull_v5_state_bank_v2"
MIN_SAMPLES = 64
MIN_PLUS = 8
MIN_CONSTRUCTED = 16
BUCKETS = ("2.5-5", "5-9", "9-12")
PROVENANCE = ("bank_natural_e5", "bank_natural_e5_plus", "bank_constructed")
CAPTURE_TIERS = ("e5", "e5_plus_2s", "e5_plus_4s", "constructed")
PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
ALLOWED_GPUS = (4, 5, 6, 7)
LEGACY_SOURCE_SCHEMA = "a2_piper_pull_v5_state_bank_source_v1"
LEGACY_SOURCE_ROWS = 64
LEGACY_SOURCE_BUFFER_COUNT = 86


def _load(path: Path) -> Mapping[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    payload = torch.load(path, map_location="cpu", weights_only=False)
    if not isinstance(payload, Mapping):
        raise ValueError(f"state-bank source must be a mapping: {path}")
    return payload


def _metadata_rows(payload: Mapping[str, Any], key: str, count: int, label: str) -> list[Any]:
    value = payload.get(key)
    if torch.is_tensor(value):
        value = value.detach().cpu().tolist()
    if not isinstance(value, (list, tuple)) or len(value) != count:
        raise ValueError(f"{label}.{key} must contain one value per row")
    return list(value)


def _closer_bucket(force: float) -> str:
    if 2.5 <= force < 5.0:
        return "2.5-5"
    if 5.0 <= force < 9.0:
        return "5-9"
    if 9.0 <= force <= 12.0:
        return "9-12"
    raise ValueError(f"hinge_drive_max_force_nm outside planned closer buckets: {force!r}")


def _tensor_values_equal(left: torch.Tensor, right: torch.Tensor) -> bool:
    if tuple(left.shape) != tuple(right.shape) or left.dtype != right.dtype:
        return False
    if left.is_floating_point() or left.is_complex():
        equal = left == right
        equal |= torch.isnan(left) & torch.isnan(right)
        return bool(torch.all(equal).item())
    return bool(torch.equal(left, right))


def repair_legacy_source_a_v5_1(
    legacy_path: Path, metrics_path: Path, output_path: Path
) -> dict[str, Any]:
    """Attach v5.1 closer metadata to the immutable legacy Source-A payload."""

    if output_path.exists():
        raise FileExistsError(f"refusing to overwrite repaired source payload: {output_path}")
    legacy = _load(legacy_path)
    if legacy.get("schema") != LEGACY_SOURCE_SCHEMA:
        raise ValueError(f"legacy source schema must be {LEGACY_SOURCE_SCHEMA}")
    required_tensors = (
        "robot_root_state",
        "robot_dof_pos",
        "robot_dof_vel",
        "door_root_state",
        "door_dof_pos",
        "door_dof_vel",
        "source_env_origin",
        "settle_valid",
        "settle_steps",
    )
    missing = [name for name in required_tensors if name not in legacy]
    if missing:
        raise ValueError(f"legacy source payload is missing required tensors: {missing!r}")
    provenance = legacy.get("provenance")
    if not isinstance(provenance, (list, tuple)) or len(provenance) != LEGACY_SOURCE_ROWS:
        raise ValueError("legacy source provenance must contain exactly 64 rows")
    if any(item != "bank_natural_e5" for item in provenance):
        raise ValueError("legacy Source-A provenance must be bank_natural_e5 for every row")
    for name in required_tensors:
        value = legacy[name]
        if (
            not torch.is_tensor(value)
            or value.ndim == 0
            or value.shape[0] != LEGACY_SOURCE_ROWS
        ):
            raise ValueError(f"legacy source tensor {name!r} must have leading dimension 64")
    settle_valid = legacy["settle_valid"]
    settle_steps = legacy["settle_steps"]
    if settle_valid.dtype != torch.bool or tuple(settle_valid.shape) != (LEGACY_SOURCE_ROWS,):
        raise ValueError("legacy settle_valid must be a bool tensor with shape [64]")
    if settle_steps.dtype != torch.long or tuple(settle_steps.shape) != (LEGACY_SOURCE_ROWS,):
        raise ValueError("legacy settle_steps must be an int64 tensor with shape [64]")
    if not bool(torch.all(settle_valid).item()) or torch.any(settle_steps < 50):
        raise ValueError("legacy Source-A rows must all retain settle_valid=true and settle_steps>=50")
    buffers = legacy.get("buffers")
    if not isinstance(buffers, Mapping) or len(buffers) != LEGACY_SOURCE_BUFFER_COUNT:
        raise ValueError(
            f"legacy source buffers must contain exactly {LEGACY_SOURCE_BUFFER_COUNT} entries"
        )
    for name, value in buffers.items():
        if not torch.is_tensor(value) or value.ndim == 0 or value.shape[0] != LEGACY_SOURCE_ROWS:
            raise ValueError(f"legacy source buffer {name!r} must have leading dimension 64")

    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    terminal_rows = metrics.get("episode_terminal_diagnostics")
    if not isinstance(terminal_rows, list) or len(terminal_rows) != LEGACY_SOURCE_ROWS:
        raise ValueError("legacy metrics must contain exactly 64 terminal diagnostics")
    by_env_id: dict[int, Mapping[str, Any]] = {}
    for row in terminal_rows:
        if not isinstance(row, Mapping):
            raise ValueError("legacy terminal diagnostics must be mappings")
        env_id = row.get("env_id")
        if isinstance(env_id, bool) or not isinstance(env_id, int) or not 0 <= env_id < LEGACY_SOURCE_ROWS:
            raise ValueError(f"legacy terminal env_id must be an integer in [0,63]; got {env_id!r}")
        if env_id in by_env_id:
            raise ValueError(f"legacy metrics contain duplicate terminal env_id {env_id}")
        by_env_id[env_id] = row
    if set(by_env_id) != set(range(LEGACY_SOURCE_ROWS)):
        raise ValueError("legacy metrics must contain one terminal record for every env_id 0..63")
    ordered_rows = [by_env_id[index] for index in range(LEGACY_SOURCE_ROWS)]

    forces: list[float] = []
    buckets: list[str] = []
    for env_id, row in enumerate(ordered_rows):
        pull_v5 = row.get("pull_v5")
        if not isinstance(pull_v5, Mapping) or pull_v5.get("reset_source") != "natural":
            raise ValueError(f"legacy terminal row {env_id} must be a natural Source-A episode")
        scenario = row.get("door_scenario")
        if not isinstance(scenario, Mapping):
            raise ValueError(f"legacy terminal row {env_id} is missing door_scenario metadata")
        raw_force = scenario.get("hinge_max_force_nm")
        if isinstance(raw_force, bool) or not isinstance(raw_force, (int, float)):
            raise ValueError(f"legacy terminal row {env_id} hinge force must be numeric")
        force = float(raw_force)
        if not math.isfinite(force):
            raise ValueError(f"legacy terminal row {env_id} hinge force must be finite")
        drive_force = row.get("door_hinge_drive_max_force")
        if isinstance(drive_force, bool) or not isinstance(drive_force, (int, float)):
            raise ValueError(f"legacy terminal row {env_id} is missing door_hinge_drive_max_force")
        if float(drive_force) != force:
            raise ValueError(
                f"legacy terminal row {env_id} hinge force fields disagree: {drive_force!r} vs {force!r}"
            )
        forces.append(force)
        buckets.append(_closer_bucket(force))

    repaired: dict[str, Any] = dict(legacy)
    for name, value in legacy.items():
        if torch.is_tensor(value):
            repaired[name] = value.detach().cpu().clone()
    repaired["buffers"] = {
        name: value.detach().cpu().clone() for name, value in buffers.items()
    }
    repaired["schema"] = SCHEMA_SOURCE
    repaired["provenance"] = ["bank_natural_e5"] * LEGACY_SOURCE_ROWS
    repaired["hinge_drive_max_force_nm"] = torch.tensor(forces, dtype=torch.float32)
    repaired["closer_bucket"] = buckets
    repaired["capture_tier"] = ["e5"] * LEGACY_SOURCE_ROWS
    repaired["capture_delay_steps"] = torch.zeros(LEGACY_SOURCE_ROWS, dtype=torch.long)
    repaired["source_row"] = list(range(LEGACY_SOURCE_ROWS))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(repaired, output_path)
    written = _load(output_path)
    if written.get("schema") != SCHEMA_SOURCE:
        raise RuntimeError("repaired source payload did not persist source v2 schema")
    for name, value in legacy.items():
        if torch.is_tensor(value):
            candidate = written.get(name)
            if (
                not torch.is_tensor(candidate)
                or tuple(candidate.shape) != tuple(value.shape)
                or candidate.dtype != value.dtype
                or not _tensor_values_equal(candidate, value)
            ):
                raise RuntimeError(f"repaired tensor {name!r} differs from legacy source")
    written_buffers = written.get("buffers")
    if not isinstance(written_buffers, Mapping) or set(written_buffers) != set(buffers):
        raise RuntimeError("repaired source buffer keys differ from legacy source")
    for name, value in buffers.items():
        candidate = written_buffers[name]
        if (
            not torch.is_tensor(candidate)
            or tuple(candidate.shape) != tuple(value.shape)
            or candidate.dtype != value.dtype
            or not _tensor_values_equal(candidate, value)
        ):
            raise RuntimeError(f"repaired buffer {name!r} differs from legacy source")
    if len(written["provenance"]) != LEGACY_SOURCE_ROWS or len(written["closer_bucket"]) != LEGACY_SOURCE_ROWS:
        raise RuntimeError("repaired source metadata row count is not 64")
    bucket_counts = {bucket: written["closer_bucket"].count(bucket) for bucket in BUCKETS}
    if any(count == 0 for count in bucket_counts.values()):
        raise RuntimeError(f"repaired source does not populate all closer buckets: {bucket_counts}")
    receipt_path = output_path.with_suffix(output_path.suffix + ".receipt.json")
    if receipt_path.exists():
        raise FileExistsError(f"refusing to overwrite repair receipt: {receipt_path}")
    result = {
        "schema": SCHEMA_SOURCE,
        "status": "PASS",
        "source_legacy": str(legacy_path),
        "metrics": str(metrics_path),
        "output": str(output_path),
        "receipt": str(receipt_path),
        "samples": LEGACY_SOURCE_ROWS,
        "buffers": LEGACY_SOURCE_BUFFER_COUNT,
        "tensor_values_unchanged": True,
        "settle_valid_retained": True,
        "settle_steps": sorted(set(int(value) for value in written["settle_steps"].tolist())),
        "closer_bucket_counts": bucket_counts,
        "metadata": {
            "provenance": "bank_natural_e5",
            "capture_tier": "e5",
            "capture_delay_steps": 0,
            "source_rows": "0..63",
        },
    }
    receipt_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def _source_cases(payload: Mapping[str, Any], label: str, expected: str | None) -> tuple[int, dict[str, Any]]:
    if payload.get("schema") != SCHEMA_SOURCE:
        raise ValueError(f"{label}.schema must be {SCHEMA_SOURCE}")
    raw_provenance = payload.get("provenance")
    if not isinstance(raw_provenance, (list, tuple)):
        raise ValueError(f"{label}.provenance must be a non-empty sequence")
    provenance = [str(item) for item in raw_provenance]
    if not provenance:
        raise ValueError(f"{label}.provenance must be a non-empty sequence")
    count = len(provenance)
    if any(item not in PROVENANCE for item in provenance):
        raise ValueError(f"{label}.provenance contains an unsupported source")
    if expected is not None and any(item != expected for item in provenance):
        raise ValueError(f"{label}.provenance must contain only {expected}")
    required = (
        "robot_root_state", "robot_dof_pos", "robot_dof_vel",
        "door_root_state", "door_dof_pos", "door_dof_vel", "source_env_origin",
        "settle_valid", "settle_steps", "buffers", "hinge_drive_max_force_nm",
        "closer_bucket", "capture_tier", "capture_delay_steps", "source_row",
    )
    missing = [name for name in required if name not in payload]
    if missing:
        raise ValueError(f"{label} is missing {missing!r}")
    tensor_names = (
        "robot_root_state", "robot_dof_pos", "robot_dof_vel",
        "door_root_state", "door_dof_pos", "door_dof_vel", "source_env_origin",
    )
    tensors: dict[str, torch.Tensor] = {}
    for name in tensor_names:
        value = payload[name]
        if not torch.is_tensor(value) or value.shape[0] != count:
            raise ValueError(f"{label}.{name} must have leading dimension {count}")
        if not torch.is_floating_point(value) or not torch.all(torch.isfinite(value)):
            raise ValueError(f"{label}.{name} must contain finite floating values")
        tensors[name] = value.detach().cpu()
    settle_valid = _metadata_rows(payload, "settle_valid", count, label)
    settle_steps = _metadata_rows(payload, "settle_steps", count, label)
    force = [float(item) for item in _metadata_rows(payload, "hinge_drive_max_force_nm", count, label)]
    buckets = [str(item) for item in _metadata_rows(payload, "closer_bucket", count, label)]
    tiers = [str(item) for item in _metadata_rows(payload, "capture_tier", count, label)]
    capture_delay_steps = _metadata_rows(payload, "capture_delay_steps", count, label)
    source_rows = _metadata_rows(payload, "source_row", count, label)
    if any(not isinstance(item, bool) or not item for item in settle_valid):
        raise ValueError(f"{label}.settle_valid must be true for every admitted row")
    if any(isinstance(item, bool) or not isinstance(item, int) or item < 50 for item in settle_steps):
        raise ValueError(f"{label}.settle_steps must be integer >=50 for every row")
    if any(not math.isfinite(item) or not (2.5 <= item <= 12.0) for item in force):
        raise ValueError(f"{label}.hinge_drive_max_force_nm must lie within the planned closer range")
    if any(item not in BUCKETS for item in buckets):
        raise ValueError(f"{label}.closer_bucket contains an unsupported bucket")
    if any(item not in CAPTURE_TIERS for item in tiers):
        raise ValueError(f"{label}.capture_tier contains an unsupported tier")
    for index, (source, tier) in enumerate(zip(provenance, tiers)):
        expected_tiers = {
            "bank_natural_e5": {"e5"},
            "bank_natural_e5_plus": {"e5_plus_2s", "e5_plus_4s"},
            "bank_constructed": {"constructed"},
        }[source]
        if tier not in expected_tiers:
            raise ValueError(
                f"{label} row {index} capture tier {tier!r} contradicts provenance {source!r}"
            )
    if any(isinstance(item, bool) or not isinstance(item, int) or item < 0 for item in capture_delay_steps):
        raise ValueError(f"{label}.capture_delay_steps must contain non-negative integers")
    if any(isinstance(item, bool) or not isinstance(item, int) or item < 0 for item in source_rows):
        raise ValueError(f"{label}.source_row must contain non-negative integers")
    buffers = payload["buffers"]
    if not isinstance(buffers, Mapping) or not buffers:
        raise ValueError(f"{label}.buffers must be a non-empty mapping")
    buffer_tensors: dict[str, torch.Tensor] = {}
    for name, value in buffers.items():
        if not torch.is_tensor(value) or value.shape[0] != count:
            raise ValueError(f"{label}.buffers[{name!r}] must have leading dimension {count}")
        buffer_tensors[str(name)] = value.detach().cpu()
    return count, {
        **tensors,
        "provenance": provenance,
        "settle_valid": [bool(item) for item in settle_valid],
        "settle_steps": [int(item) for item in settle_steps],
        "hinge_drive_max_force_nm": force,
        "closer_bucket": buckets,
        "capture_tier": tiers,
        "capture_delay_steps": [int(item) for item in capture_delay_steps],
        "source_row": [int(item) for item in source_rows],
        "buffers": buffer_tensors,
    }


def _cat(a: Mapping[str, Any], b: Mapping[str, Any] | None, key: str) -> torch.Tensor:
    first = a[key]
    if b is None:
        return first.clone()
    second = b[key]
    if tuple(first.shape[1:]) != tuple(second.shape[1:]):
        raise ValueError(f"source tensor {key} shape mismatch: {tuple(first.shape)} vs {tuple(second.shape)}")
    return torch.cat((first, second), dim=0)


def _merge_source_rows(left: dict[str, Any], right: Mapping[str, Any]) -> dict[str, Any]:
    if set(left["buffers"]) != set(right["buffers"]):
        raise ValueError("Source-A E5 and delayed capture registered-buffer keys differ")
    merged = dict(left)
    for name in ("robot_root_state", "robot_dof_pos", "robot_dof_vel", "door_root_state", "door_dof_pos", "door_dof_vel", "source_env_origin"):
        merged[name] = torch.cat((left[name], right[name]), dim=0)
    for name in ("provenance", "settle_valid", "settle_steps", "hinge_drive_max_force_nm", "closer_bucket", "capture_tier", "capture_delay_steps", "source_row"):
        merged[name] = list(left[name]) + list(right[name])
    merged["buffers"] = {
        name: torch.cat((left["buffers"][name], right["buffers"][name]), dim=0)
        for name in left["buffers"]
    }
    return merged


def build_bank(
    source_a: Path,
    source_b: Path | None,
    output: Path,
    *,
    source_a_plus: tuple[Path, ...] = (),
    allow_g8_pure_a: bool = False,
) -> dict[str, Any]:
    count_a, payload_a = _source_cases(_load(source_a), "source_a", None)
    for plus_index, plus_path in enumerate(source_a_plus):
        plus_count, plus_payload = _source_cases(_load(plus_path), f"source_a_plus_{plus_index}", "bank_natural_e5_plus")
        payload_a = _merge_source_rows(payload_a, plus_payload)
        count_a += plus_count
    if payload_a["provenance"][0] != "bank_natural_e5":
        raise ValueError("source_a must begin with bank_natural_e5 provenance")
    if any(item not in {"bank_natural_e5", "bank_natural_e5_plus"} for item in payload_a["provenance"]):
        raise ValueError("source_a may contain only bank_natural_e5 or bank_natural_e5_plus provenance")
    count_b = 0
    payload_b: dict[str, Any] | None = None
    if source_b is not None:
        count_b, payload_b = _source_cases(_load(source_b), "source_b", "bank_constructed")
    elif not allow_g8_pure_a:
        raise ValueError("source_b is required unless --allow-g8-pure-a is explicit")
    for name in ("robot_root_state", "robot_dof_pos", "robot_dof_vel", "door_root_state", "door_dof_pos", "door_dof_vel", "source_env_origin"):
        if payload_b is not None and tuple(payload_a[name].shape[1:]) != tuple(payload_b[name].shape[1:]):
            raise ValueError(f"source A/B tensor {name} shape mismatch")
    if payload_b is not None and set(payload_a["buffers"]) != set(payload_b["buffers"]):
        raise ValueError("source A and source B registered-buffer keys differ")
    combined_provenance = payload_a["provenance"] + ([] if payload_b is None else payload_b["provenance"])
    combined_force = payload_a["hinge_drive_max_force_nm"] + ([] if payload_b is None else payload_b["hinge_drive_max_force_nm"])
    combined_buckets = payload_a["closer_bucket"] + ([] if payload_b is None else payload_b["closer_bucket"])
    combined_tiers = payload_a["capture_tier"] + ([] if payload_b is None else payload_b["capture_tier"])
    combined_delays = payload_a["capture_delay_steps"] + ([] if payload_b is None else payload_b["capture_delay_steps"])
    combined_valid = payload_a["settle_valid"] + ([] if payload_b is None else payload_b["settle_valid"])
    combined_steps = payload_a["settle_steps"] + ([] if payload_b is None else payload_b["settle_steps"])
    combined_rows = payload_a["source_row"] + ([] if payload_b is None else payload_b["source_row"])
    counts = {source: combined_provenance.count(source) for source in PROVENANCE}
    if len(combined_provenance) < MIN_SAMPLES:
        raise ValueError(f"combined state bank has {len(combined_provenance)} samples; minimum is {MIN_SAMPLES}")
    if counts["bank_natural_e5_plus"] < MIN_PLUS and not allow_g8_pure_a:
        raise ValueError(f"G13 requires at least {MIN_PLUS} bank_natural_e5_plus rows; got {counts['bank_natural_e5_plus']}")
    if counts["bank_constructed"] < MIN_CONSTRUCTED and not allow_g8_pure_a:
        raise ValueError(f"G13 requires at least {MIN_CONSTRUCTED} bank_constructed rows; got {counts['bank_constructed']}")
    if set(combined_buckets) != set(BUCKETS):
        raise ValueError("G13 requires all closer buckets to be populated")
    output_payload: dict[str, Any] = {
        "schema": SCHEMA_BANK,
        "robot_root_state": _cat(payload_a, payload_b, "robot_root_state"),
        "robot_dof_pos": _cat(payload_a, payload_b, "robot_dof_pos"),
        "robot_dof_vel": _cat(payload_a, payload_b, "robot_dof_vel"),
        "door_root_state": _cat(payload_a, payload_b, "door_root_state"),
        "door_dof_pos": _cat(payload_a, payload_b, "door_dof_pos"),
        "door_dof_vel": _cat(payload_a, payload_b, "door_dof_vel"),
        "source_env_origin": _cat(payload_a, payload_b, "source_env_origin"),
        "provenance": combined_provenance,
        "hinge_drive_max_force_nm": combined_force,
        "closer_bucket": combined_buckets,
        "capture_tier": combined_tiers,
        "capture_delay_steps": combined_delays,
        "settle_valid": combined_valid,
        "settle_steps": combined_steps,
        "source_row": combined_rows,
        "buffers": {
            name: _cat(payload_a["buffers"], None if payload_b is None else payload_b["buffers"], name)
            for name in payload_a["buffers"]
        },
        "provenance_counts": {**counts, "total": len(combined_provenance)},
        "g13": {
            "total_minimum": MIN_SAMPLES,
            "natural_e5_plus_minimum": MIN_PLUS,
            "constructed_minimum": MIN_CONSTRUCTED,
            "constructed_requirement": "optional_g8_pure_a" if allow_g8_pure_a else "required",
            "closer_buckets": list(BUCKETS),
        },
    }
    if output.exists():
        raise FileExistsError(f"refusing to overwrite state bank: {output}")
    manifest_path = output.parent / MANIFEST_NAME
    if manifest_path.exists():
        raise FileExistsError(f"refusing to overwrite state-bank manifest: {manifest_path}")
    output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(output_payload, output)
    manifest = {
        "schema": "a2_piper_pull_v5_state_bank_manifest_v2",
        "bank": str(output),
        "rows": [
            {
                "index": index,
                "provenance": combined_provenance[index],
                "hinge_drive_max_force_nm": combined_force[index],
                "closer_bucket": combined_buckets[index],
                "capture_tier": combined_tiers[index],
                "capture_delay_steps": combined_delays[index],
                "settle_valid": combined_valid[index],
                "settle_steps": combined_steps[index],
                "source_row": combined_rows[index],
            }
            for index in range(len(combined_provenance))
        ],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    result = {
        "schema": SCHEMA_BANK,
        "status": "PASS_G8_PURE_A" if allow_g8_pure_a and count_b == 0 else "PASS",
        "samples": len(combined_provenance),
        "source_a_samples": count_a,
        "source_b_samples": count_b,
        "output": str(output),
        "manifest": str(manifest_path),
        "provenance_counts": output_payload["provenance_counts"],
    }
    receipt_path = output.with_suffix(output.suffix + ".receipt.json")
    if receipt_path.exists():
        raise FileExistsError(f"refusing to overwrite state-bank receipt: {receipt_path}")
    receipt_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    result["receipt"] = str(receipt_path)
    return result


def build_runtime_source_command(
    *, source: str, output: Path, checkpoint: Path, gpu: int,
    capture_tier: str, allow_missing_checkpoint: bool = False,
) -> tuple[list[str], dict[str, str], Path]:
    if source not in {"bank_natural_e5", "bank_constructed"}:
        raise ValueError(f"unsupported runtime source: {source!r}")
    if capture_tier not in CAPTURE_TIERS:
        raise ValueError(f"unsupported capture tier: {capture_tier!r}")
    if gpu not in ALLOWED_GPUS:
        raise ValueError(f"runtime capture only permits physical GPU4-7; got GPU{gpu}")
    if not PYTHON.is_file():
        raise FileNotFoundError(PYTHON)
    if not checkpoint.is_file() and not allow_missing_checkpoint:
        raise FileNotFoundError(checkpoint)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite runtime source payload: {output}")
    capture_provenance = (
        source
        if source == "bank_constructed"
        else ("bank_natural_e5" if capture_tier == "e5" else "bank_natural_e5_plus")
    )
    relative_output = output.resolve().relative_to(ROOT.resolve())
    command = [
        str(PYTHON), "-B", "-m", "gr00t.rl.eval_agent_trl",
        f"checkpoint={checkpoint.resolve()}", "checkpoint_load_mode=policy_only", "auto_load_latest=false",
        "num_envs=64", "seed=0", "headless=true", "use_wandb=false",
        "+ablation=wbmanip/pull_v5_M_s0", "algo.config.load_optimizer=false",
        "algo.config.eval.num_eval_episodes=1", "+algo.config.eval.eval_num_envs_episodes=true",
        "+algo.config.eval.dump_to_log_metrics=true", "algo.config.eval.save_videos=false",
        "algo.config.eval.num_save_episodes=64", "env.config.enable_staged_reset=true",
        "env.config.a2_pull_v5_stage4_bank_injection_enabled=false",
        "+env.config.a2_pull_v5_bank_capture_only=true",
        f"+env.config.a2_pull_v5_bank_capture_tier={capture_tier}",
        "+env.config.a2_pull_v5_bank_capture_settle_valid=true",
        "+env.config.a2_pull_v5_bank_capture_settle_steps=50",
        f"+env.config.a2_pull_v5_bank_capture_provenance={capture_provenance}",
        f"+env.config.a2_pull_v5_bank_capture_path={relative_output}",
        "+env.config.a2_pull_v5_bank_capture_source_row=0",
        "env.config.a2_pull_v5_reset_source=natural",
        f"eval_output_dir={output.parent / (output.stem + '_eval')}",
        f"hydra.run.dir={output.parent / (output.stem + '_hydra')}",
        "+device=cuda:0",
    ]
    if source == "bank_constructed":
        command.append("+env.config.a2_pull_v5_source_b_direct_capture=true")
    return command, {
        "PYTHONPATH": str(ROOT), "CUDA_VISIBLE_DEVICES": str(gpu),
        "ACCELERATE_TORCH_DEVICE": "cuda:0", "HYDRA_FULL_ERROR": "1",
        "PYTHONUNBUFFERED": "1", "WANDB_MODE": "offline",
    }, output.with_suffix(".runner.log")


def _capture_runtime_source(*, source: str, output: Path, checkpoint: Path, gpu: int, capture_tier: str) -> None:
    command, process_env, log_path = build_runtime_source_command(
        source=source, output=output, checkpoint=checkpoint, gpu=gpu, capture_tier=capture_tier
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    run_env = os.environ.copy()
    run_env.update(process_env)
    with log_path.open("x", encoding="utf-8") as stream:
        result = subprocess.run(command, cwd=ROOT, env=run_env, stdout=stream, stderr=subprocess.STDOUT, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"runtime {source} producer failed with exit code {result.returncode}; see {log_path}")
    if not output.is_file():
        raise RuntimeError(f"runtime {source} producer exited without state-bank payload: {output}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-a", type=Path)
    parser.add_argument("--source-b", type=Path)
    parser.add_argument("--source-a-plus", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--run-source-a", action="store_true")
    parser.add_argument("--run-source-b", action="store_true")
    parser.add_argument("--source-a-tier", choices=("e5", "e5_plus_2s", "e5_plus_4s"), default="e5")
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--gpu", type=int, choices=ALLOWED_GPUS, default=4)
    parser.add_argument("--allow-g8-pure-a", action="store_true")
    parser.add_argument("--capture-only", action="store_true")
    parser.add_argument("--repair-legacy-source-a", type=Path)
    parser.add_argument("--repair-legacy-metrics", type=Path)
    parser.add_argument("--repair-output", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    repair_args = (
        args.repair_legacy_source_a,
        args.repair_legacy_metrics,
        args.repair_output,
    )
    if any(value is not None for value in repair_args):
        if not all(value is not None for value in repair_args):
            raise ValueError(
                "offline repair requires --repair-legacy-source-a, --repair-legacy-metrics, "
                "and --repair-output"
            )
        if (
            args.source_a is not None
            or args.source_b is not None
            or args.source_a_plus
            or args.run_source_a
            or args.run_source_b
        ):
            raise ValueError("offline repair cannot be combined with runtime/bank build inputs")
        print(
            json.dumps(
                repair_legacy_source_a_v5_1(
                    args.repair_legacy_source_a.resolve(),
                    args.repair_legacy_metrics.resolve(),
                    args.repair_output.resolve(),
                ),
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    if args.source_a is None:
        raise ValueError("--source-a is required for runtime capture or bank build")
    source_a = args.source_a.resolve()
    source_b = None if args.source_b is None else args.source_b.resolve()
    output = args.output.resolve()
    if (args.run_source_a or args.run_source_b) and args.checkpoint is None:
        raise ValueError("runtime source capture requires --checkpoint")
    if args.dry_run:
        for source, output_path, selected, tier in (
            ("bank_natural_e5", source_a, args.run_source_a, args.source_a_tier),
            ("bank_constructed", source_b, args.run_source_b, "constructed"),
        ):
            if selected:
                if output_path is None:
                    raise ValueError("--run-source-b requires --source-b")
                command, _env, _log = build_runtime_source_command(
                    source=source, output=output_path, checkpoint=args.checkpoint.resolve(),
                    gpu=args.gpu, capture_tier=tier, allow_missing_checkpoint=True,
                )
                print(f"[pull-v5.1 state-bank] {source} command:", " ".join(command))
        print(json.dumps({"status": "DRY_RUN", "schema": SCHEMA_BANK, "g13": {"total": MIN_SAMPLES, "plus": MIN_PLUS, "constructed": MIN_CONSTRUCTED, "buckets": BUCKETS}}, sort_keys=True))
        return 0
    if args.run_source_a:
        _capture_runtime_source(source="bank_natural_e5", output=source_a, checkpoint=args.checkpoint.resolve(), gpu=args.gpu, capture_tier=args.source_a_tier)
    if args.run_source_b:
        if source_b is None:
            raise ValueError("--run-source-b requires --source-b")
        _capture_runtime_source(source="bank_constructed", output=source_b, checkpoint=args.checkpoint.resolve(), gpu=args.gpu, capture_tier="constructed")
    if args.capture_only:
        print(json.dumps({"status": "CAPTURE_ONLY", "source_a": str(source_a), "source_b": None if source_b is None else str(source_b)}, sort_keys=True))
        return 0
    print(json.dumps(build_bank(source_a, source_b, output, source_a_plus=tuple(path.resolve() for path in args.source_a_plus), allow_g8_pure_a=args.allow_g8_pure_a), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
