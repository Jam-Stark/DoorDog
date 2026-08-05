"""Fail-fast serial launcher for the 16 new v19/v20/v21B report renders.

The matrix is declarative.  Planning only reads and hashes its signed inputs;
execution creates one fresh evidence root per case, launches exactly one
child for each case in GPU order, and stops at the first failure.  This file
does not launch Isaac Sim during planning and never retries a failed case.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

# This is the existing R2 authority, not a local reimplementation of its hash.
from scriptsFORhuman.v20_R2._r2_workflow import hash_command_env
from scriptsFORhuman.v21B._v21b_common import command_sha256 as v21b_command_sha256


SCHEMA = "a2_piper_v19_v21_report_only_render_matrix_v1"
PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
LOCK_PATH = Path("/tmp/doordog-a2-piper-headless-kit-copy.lock")
LOCK_MARKER = b"[INFO][AppLauncher]: Loading experience file:"
GPU_IDS = (0, 1, 2, 3)
V19_SOURCE_SCRIPT = REPO / "scriptsFORhuman/v19/a2_piper_v19_render_queue.py"
V19_HISTORIC_RECEIPT = REPO / (
    "logs_eval/base_v19/render/_v19_render_G3_G7_r4_20260728/"
    "G7_probe_1env_3cam_seed0/render_eval_command.json"
)
V20_HASH_SOURCE = REPO / "scriptsFORhuman/v20_R2/_r2_workflow.py"
V21_QUEUE = REPO / (
    "logs_eval/base_v21B/postformal_20260803_route_a_exact70_r16/R17_QUEUE.json"
)
V21B_HASH_SOURCE = REPO / "scriptsFORhuman/v21B/_v21b_common.py"
V21B_COMMAND_IDENTITY_PREFIX = "+env.config.a2_v21B_evaluation_command_sha256="
MEDIA_SUFFIXES = frozenset({".mp4", ".webm", ".mov", ".avi", ".mkv", ".png", ".jpg", ".jpeg"})
PRIMARY_V21B_MP4_RE = re.compile(
    r"^.+_env(?P<env>[0-9]{4})_episode(?P<episode>[0-9]{4})"
    r"(?P<camera>_handle_side|_handle_top)?_len(?P<length>[0-9]+)_reason-(?P<reason>.+)\.mp4$"
)
DIAGNOSTIC_TERMS = (
    "gripper_handle_orientation",
    "grasp_target_distance",
    "grasp",
    "penalty_not_standing_still",
    "a2_stage3_unlatch_hold",
    "a2_stage3_stage4_hold_and_drive",
    "push_door_hinge",
    "dont_push_door_handle",
    "target_root_distance",
    "penalty_standing_still",
    "stage",
    "penalty_door_frame_contact",
    "penalty_door_panel_contact",
    "penalty_a2_door_body_contact",
    "penalty_undesired_contact",
    "penalty_base_roll_pitch_l2",
    "a2_corridor_door_wide",
    "a2_corridor_clean_passage",
    "penalty_a2_posture_command_l1",
    "complete",
)
V19_LEGACY_DEFAULT_OVERRIDES = (
    "++env.config.a2_v20_send_latch_enabled=false",
    "++env.config.a2_v20_send_hinge_threshold=1.0",
    "++env.config.a2_v20_send_hinge_tolerance=0.05",
    "++env.config.a2_v20_pre_send_root_x_margin=0.03",
    "++env.config.a2_v20_pre_send_crossing_mode=disabled",
    "++env.config.a2_v20_pre_send_crossing_penalty_component=1.0",
    "++env.config.a2_v20_telemetry_enabled=false",
    "++env.config.a2_v20_traversal_economics_enabled=false",
    "++env.config.a2_v20_target_root_pre_send_scale=0.0",
    "++env.config.a2_v20_target_root_post_send_stage4_scale=0.5",
    "++env.config.a2_v20_target_root_ramp_width_rad=0.20",
    "++env.config.a2_corridor_latch_mode=legacy_root_or_hinge",
    "++env.config.a2_v20_arm_tie_enabled=false",
    "++env.config.a2_v20_arm_tangent_carry_scale=0.0",
    "++env.config.a2_v20_handle_arc_tracking_scale=0.0",
    "++env.config.a2_v20_taskspace_activity_floor_mps=0.005",
    "++env.config.a2_v20_arc_position_tolerance_m=0.03",
    "++env.config.a2_v20_arc_orientation_tolerance_rad=0.20",
    "++env.config.a2_v20_formal_values_frozen=false",
    "++env.config.a2_v20_formal_launch=false",
    "++env.config.a2_v20_calibration_label=non_formal_calibration_only",
    "++env.config.a2_v20_R1_plan_id=disabled",
    "++env.config.a2_v20_R1_send_curriculum_enabled=false",
    "++env.config.a2_v20_R1_soft_phase_end_batch=500",
    "++env.config.a2_v20_R1_snapshot_guard_enabled=false",
    "++env.config.a2_v20_R1_crossing_base_component=1.0",
    "++env.config.a2_v20_R1_crossing_shortfall_gain=1.0",
)


class RenderLauncherError(ValueError):
    """A matrix, provenance, or fail-fast launch contract violation."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise RenderLauncherError(f"expected a regular file: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _load_json(path: Path) -> Any:
    if path.is_symlink() or not path.is_file():
        raise RenderLauncherError(f"expected a regular JSON file: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RenderLauncherError(f"invalid JSON: {path}") from exc


def _repo_path(value: str | Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = REPO / path
    return path.resolve()


def _require_hash(path: Path, expected: str, label: str) -> str:
    actual = _sha256(path)
    if actual != expected:
        raise RenderLauncherError(f"{label} hash mismatch: {actual} != {expected}: {path}")
    return actual


def _replace_once(argv: list[str], prefix: str, replacement: str) -> None:
    matches = [index for index, token in enumerate(argv) if token.startswith(prefix)]
    if len(matches) != 1:
        raise RenderLauncherError(f"expected one {prefix!r} token, found {matches}")
    argv[matches[0]] = prefix + replacement


def _set_hydra(argv: list[str], key: str, value: str, *, plus: str = "++") -> None:
    """Set one Hydra key while preserving a signed token when it exists."""

    matches = [
        index
        for index, token in enumerate(argv)
        if token.lstrip("+").startswith(key)
    ]
    if len(matches) > 1:
        raise RenderLauncherError(f"duplicate Hydra key {key!r}: {matches}")
    if matches:
        token = argv[matches[0]]
        lead = token[: len(token) - len(token.lstrip("+"))]
        argv[matches[0]] = f"{lead}{key}{value}"
    else:
        argv.append(f"{plus}{key}{value}")


def _remove_exact_prefix(argv: list[str], prefix: str) -> None:
    matches = [index for index, token in enumerate(argv) if token.startswith(prefix)]
    if len(matches) != 1:
        raise RenderLauncherError(f"expected one removable {prefix!r} token, found {matches}")
    del argv[matches[0]]


def _replace_quoted_path(argv: list[str], prefix: str, path: Path) -> None:
    _replace_once(argv, prefix, repr(str(path)))


def _check_fresh_root(path: Path) -> None:
    if path.exists() or path.is_symlink():
        raise RenderLauncherError(f"output root must be absent (no overwrite): {path}")


def _contract_env(gpu: int, version: str) -> dict[str, str]:
    if gpu not in GPU_IDS:
        raise RenderLauncherError(f"unsupported physical GPU: {gpu}")
    env = {
        "CUDA_VISIBLE_DEVICES": str(gpu),
        "ACCELERATE_TORCH_DEVICE": "cuda:0",
        "VK_ICD_FILENAMES": "/usr/share/vulkan/icd.d/nvidia_icd.json",
    }
    if version == "v20":
        env["WANDB_MODE"] = "offline"
    elif version == "v21B":
        env["WANDB_MODE"] = "disabled"
        env["WANDB_DISABLED"] = "true"
    elif version != "v19":
        raise RenderLauncherError(f"unsupported version: {version}")
    return env


def _version_output_prefix(version: str) -> str:
    return {
        "v19": "logs_eval/base_v19/progress_report_multickpt_render_20260806/",
        "v20": "logs_eval/base_v20_R2/progress_report_multickpt_render_20260806/",
        "v21B": "logs_eval/base_v21B/progress_report_multickpt_render_20260806/",
    }[version]


def _load_matrix(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = _load_json(path)
    if not isinstance(payload, dict) or payload.get("schema") != SCHEMA:
        raise RenderLauncherError(f"matrix schema mismatch: {path}")
    if payload.get("purpose") != "REPORT_ONLY_SCIENTIFIC_ILLUSTRATION_NOT_RELEASE":
        raise RenderLauncherError("matrix purpose must remain report-only")
    if payload.get("serial_per_gpu") is not True or tuple(payload.get("gpu_ids", ())) != GPU_IDS:
        raise RenderLauncherError("matrix GPU/serial contract mismatch")
    cases = payload.get("cases")
    if not isinstance(cases, list) or len(cases) != 16:
        raise RenderLauncherError("matrix must contain exactly 16 cases")
    ids = [case.get("case_id") for case in cases if isinstance(case, dict)]
    if len(ids) != 16 or len(set(ids)) != 16 or any(not isinstance(item, str) for item in ids):
        raise RenderLauncherError("case IDs must be exactly 16 unique strings")
    output_roots = [case.get("output_root") for case in cases]
    if len(set(output_roots)) != 16:
        raise RenderLauncherError("case output roots must be unique")
    versions = Counter(case.get("version") for case in cases)
    if versions != Counter({"v19": 5, "v20": 5, "v21B": 6}):
        raise RenderLauncherError(f"version allocation mismatch: {versions}")
    gpu_counts = Counter(case.get("gpu") for case in cases)
    if gpu_counts != Counter({gpu: 4 for gpu in GPU_IDS}):
        raise RenderLauncherError(f"GPU allocation mismatch: {gpu_counts}")

    if not PYTHON.exists() or not os.access(PYTHON, os.X_OK):
        raise RenderLauncherError(f"IsaacLab Python executable missing: {PYTHON}")
    for source in (V19_SOURCE_SCRIPT, V19_HISTORIC_RECEIPT, V20_HASH_SOURCE, V21_QUEUE, V21B_HASH_SOURCE):
        _sha256(source)
    queue = _load_json(V21_QUEUE)
    if not isinstance(queue, dict) or queue.get("schema") != "a2_piper_base_v21B_route_a_queue_v1":
        raise RenderLauncherError("R17_QUEUE schema mismatch")
    _require_hash(
        V21_QUEUE,
        str(payload["source_contracts"]["v21b_signed_queue_sha256"]),
        "R17_QUEUE",
    )
    queue_rows = queue.get("rows")
    if not isinstance(queue_rows, list):
        raise RenderLauncherError("R17_QUEUE rows are missing")
    queue_by_id = {row.get("row_id"): row for row in queue_rows if isinstance(row, dict)}

    historic = _load_json(V19_HISTORIC_RECEIPT)
    if not isinstance(historic, dict) or not isinstance(historic.get("argv"), list):
        raise RenderLauncherError("historic v19 receipt has no argv")
    if historic.get("num_envs") != 1 or historic.get("seed") != 0:
        raise RenderLauncherError("historic v19 receipt is not the one-env seed0 contract")
    if "++env.config.a2_eval_door_handle_height_weight_pairs=[[1.10,120.0]]" not in historic["argv"]:
        raise RenderLauncherError("historic v19 ordered pair contract is missing")

    known_existing = {_repo_path(item) for item in payload.get("known_existing_render_checkpoints", [])}
    if len(known_existing) != len(payload.get("known_existing_render_checkpoints", [])):
        raise RenderLauncherError("known existing render checkpoint list contains duplicates")
    for known in known_existing:
        _sha256(known)

    for case in cases:
        if not isinstance(case, dict):
            raise RenderLauncherError("matrix case must be an object")
        version = case.get("version")
        gpu = case.get("gpu")
        if version not in {"v19", "v20", "v21B"} or gpu not in GPU_IDS:
            raise RenderLauncherError(f"invalid version/GPU in {case.get('case_id')}")
        checkpoint = _repo_path(str(case.get("checkpoint")))
        actual_checkpoint_sha = _require_hash(
            checkpoint, str(case.get("checkpoint_sha256")), f"{case['case_id']} checkpoint"
        )
        if checkpoint in known_existing:
            raise RenderLauncherError(f"matrix reuses known rendered checkpoint: {checkpoint}")
        output_root = _repo_path(str(case.get("output_root")))
        expected_prefix = _repo_path(_version_output_prefix(str(version))).parent
        if not str(case["output_root"]).startswith(_version_output_prefix(str(version))):
            raise RenderLauncherError(f"output root is not version-routed: {output_root}")
        if output_root == REPO or output_root == expected_prefix:
            raise RenderLauncherError(f"output root is too broad: {output_root}")
        if case.get("report_role") != "report_only_illustration":
            raise RenderLauncherError(f"report role mismatch: {case['case_id']}")
        if case.get("scenario_contract", {}).get("purpose_label") != payload["purpose"]:
            raise RenderLauncherError(f"scenario purpose mismatch: {case['case_id']}")
        if version == "v19":
            saved_config = _repo_path(str(case.get("saved_run_config")))
            _require_hash(saved_config, str(case.get("saved_run_config_sha256")), f"{case['case_id']} config")
            if case.get("scenario_contract", {}).get("ordered_pairs") != [[1.1, 120.0]]:
                raise RenderLauncherError(f"v19 ordered pair mismatch: {case['case_id']}")
        elif version == "v20":
            receipt_path = _repo_path(str(case.get("route_a_receipt")))
            _require_hash(receipt_path, str(case.get("route_a_receipt_sha256")), f"{case['case_id']} Route-A receipt")
            receipt = _load_json(receipt_path)
            if receipt.get("render") is not False or receipt.get("exit_code") != 0:
                raise RenderLauncherError(f"Route-A receipt is not a completed non-render source: {receipt_path}")
            route_argv = receipt.get("argv")
            if not isinstance(route_argv, list):
                raise RenderLauncherError(f"Route-A receipt argv missing: {receipt_path}")
            checkpoint_tokens = [token for token in route_argv if token.startswith("+checkpoint=")]
            config_tokens = [token for token in route_argv if token.startswith("+r2_bound_config_path=")]
            config_sha_tokens = [token for token in route_argv if token.startswith("+r2_bound_config_sha256=")]
            if len(checkpoint_tokens) != 1 or checkpoint_tokens[0].split("=", 1)[1] != str(checkpoint):
                raise RenderLauncherError(f"Route-A checkpoint identity mismatch: {receipt_path}")
            if len(config_tokens) != 1 or _repo_path(config_tokens[0].split("=", 1)[1]) != _repo_path(str(case["bound_config"])):
                raise RenderLauncherError(f"Route-A config identity mismatch: {receipt_path}")
            if len(config_sha_tokens) != 1 or config_sha_tokens[0].split("=", 1)[1] != str(case["bound_config_sha256"]):
                raise RenderLauncherError(f"Route-A config hash mismatch: {receipt_path}")
            _require_hash(_repo_path(str(case["bound_config"])), str(case["bound_config_sha256"]), f"{case['case_id']} bound config")
            saved_config = _repo_path(str(case.get("saved_run_config")))
            adjacent_config = checkpoint.parent / "config.yaml"
            if saved_config != adjacent_config:
                raise RenderLauncherError(
                    f"v20 saved run config is not checkpoint-adjacent: {saved_config} != {adjacent_config}"
                )
            _require_hash(saved_config, str(case.get("saved_run_config_sha256")), f"{case['case_id']} saved run config")
            if case["scenario_contract"].get("render_topology") != "render1":
                raise RenderLauncherError(f"v20 render topology mismatch: {case['case_id']}")
            if (
                case["scenario_contract"].get("seed") != 0
                or case["scenario_contract"].get("r2_evidence") is not False
                or case["scenario_contract"].get("strict_telemetry") is not False
            ):
                raise RenderLauncherError(f"v20 report-only telemetry contract mismatch: {case['case_id']}")
        else:
            row_id = case.get("signed_queue_row_id")
            row = queue_by_id.get(row_id)
            if row is None:
                raise RenderLauncherError(f"signed R17 row missing: {row_id}")
            if row.get("topology") != "canonical16" or row.get("episodes") != 16:
                raise RenderLauncherError(f"R17 row is not canonical16: {row_id}")
            if _repo_path(str(row.get("checkpoint_path"))) != checkpoint or row.get("checkpoint_sha256") != actual_checkpoint_sha:
                raise RenderLauncherError(f"R17 checkpoint identity mismatch: {row_id}")
            if _repo_path(str(row.get("config_path"))) != _repo_path(str(case["config"])):
                raise RenderLauncherError(f"R17 config identity mismatch: {row_id}")
            _require_hash(_repo_path(str(case["config"])), str(case["config_sha256"]), f"{case['case_id']} config")
            if row.get("config_sha256") != case.get("config_sha256"):
                raise RenderLauncherError(f"R17 config hash mismatch: {row_id}")
            if case["scenario_contract"].get("expected_primary_videos") != 48:
                raise RenderLauncherError(f"v21B primary video contract mismatch: {case['case_id']}")
    return payload, {"queue": queue, "queue_by_id": queue_by_id, "historic_v19": historic}


def _v19_plan(case: Mapping[str, Any], historic: Mapping[str, Any]) -> dict[str, Any]:
    checkpoint = _repo_path(str(case["checkpoint"]))
    output_root = _repo_path(str(case["output_root"]))
    diagnostic_terms = "[" + ",".join(DIAGNOSTIC_TERMS) + "]"
    group = str(case["group"])
    argv = [
        str(PYTHON),
        "-m",
        "gr00t.rl.eval_agent_trl",
        f"+checkpoint={checkpoint}",
        "++checkpoint_load_mode=full",
        "++auto_load_latest=false",
        "++headless=true",
        "++num_envs=1",
        "++seed=0",
        "++use_wandb=false",
        "++simulator.config.cameras.enable_cameras=false",
        "++simulator.config.render_results=true",
        "++algo.config.num_mini_batches=1",
        "++algo.config.eval.num_eval_episodes=1",
        "++algo.config.eval.eval_num_envs_episodes=true",
        "++algo.config.eval.dump_to_log_metrics=true",
        "++algo.config.eval.a2_diagnostic_trace_enabled=true",
        f"++algo.config.eval.a2_diagnostic_reward_terms={diagnostic_terms}",
        "++algo.config.eval.a2_eval_p2_posture_axis=none",
        "++algo.config.eval.a2_forced_gripper_close_enabled=false",
        "++algo.config.eval.a2_hold_oracle_enabled=false",
        "++algo.config.eval.save_goal_reached_only=false",
        "++algo.config.eval.save_videos=false",
        "++algo.config.eval.save_trajectories=false",
        "++algo.config.eval.a2_eval_m41_strict_telemetry=true",
        "++env.config.a2_eval_door_handle_height_weight_pairs=[[1.10,120.0]]",
        *V19_LEGACY_DEFAULT_OVERRIDES,
        f"++env.config.save_rendering_dir={output_root / 'renderings'}",
        f"++eval_name=base_v19_{group}_report_only_1env_3cam_seed0_20260806",
        f"++eval_output_dir={output_root}",
    ]
    env = _contract_env(int(case["gpu"]), "v19")
    return {
        "schema": "a2_piper_report_render_case_plan_v1",
        "case": dict(case),
        "version": "v19",
        "gpu": int(case["gpu"]),
        "argv": argv,
        "env": env,
        "command_sha256": hash_command_env(argv, env),
        "checkpoint_path": str(checkpoint),
        "checkpoint_sha256": case["checkpoint_sha256"],
        "source_bindings": {
            "command_source": str(V19_SOURCE_SCRIPT),
            "command_source_sha256": _sha256(V19_SOURCE_SCRIPT),
            "historic_receipt": str(V19_HISTORIC_RECEIPT),
            "historic_receipt_sha256": _sha256(V19_HISTORIC_RECEIPT),
            "saved_run_config": str(_repo_path(str(case["saved_run_config"]))),
            "saved_run_config_sha256": case["saved_run_config_sha256"],
        },
        "output_root": str(output_root),
        "media_gate": {"expected_finalized_mp4_count": 3},
        "startup_lock": {"path": str(LOCK_PATH), "marker": LOCK_MARKER.decode("ascii")},
    }


def _v20_plan(case: Mapping[str, Any], receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Build a report-only command from the checkpoint-adjacent saved run config.

    The Route-A receipt is read-only parent provenance.  It is deliberately not
    used as the command template: the eval entrypoint loads the adjacent R3
    config from the checkpoint directory, while these overrides make the run
    non-formal and disable the R2 evidence/strict-telemetry surfaces.
    """

    checkpoint = _repo_path(str(case["checkpoint"]))
    output_root = _repo_path(str(case["output_root"]))
    saved_config = _repo_path(str(case["saved_run_config"]))
    adjacent_config = checkpoint.parent / "config.yaml"
    if saved_config != adjacent_config:
        raise RenderLauncherError(f"v20 command source config is not checkpoint-adjacent: {saved_config}")
    source_argv = receipt.get("argv")
    if not isinstance(source_argv, list) or not source_argv or not all(isinstance(item, str) for item in source_argv):
        raise RenderLauncherError(f"v20 Route-A argv is invalid: {case['case_id']}")
    if source_argv[0] != str(PYTHON) or "gr00t.rl.eval_agent_trl" not in source_argv:
        raise RenderLauncherError(f"v20 Route-A receipt does not identify the eval entrypoint: {case['case_id']}")

    group = str(case["group"])
    argv = [
        str(PYTHON),
        "-B",
        "-m",
        "gr00t.rl.eval_agent_trl",
        f"+checkpoint={checkpoint}",
        "++checkpoint_load_mode=full",
        "++auto_load_latest=false",
        "++headless=true",
        "++num_envs=1",
        "++seed=0",
        "++use_wandb=false",
        "++scientific_plan_id=a2_piper_v20_progress_report_render_v1",
        "++admission_plan_id=REPORT_ONLY_SCIENTIFIC_ILLUSTRATION_NOT_RELEASE",
        "++r2_evidence_enabled=false",
        "++r2_real_execution=false",
        "++r2_source_lock_path=null",
        "++simulator.config.cameras.enable_cameras=false",
        "++simulator.config.render_results=true",
        "++algo.config.num_mini_batches=1",
        "++algo.config.eval.num_eval_episodes=1",
        "++algo.config.eval.eval_num_envs_episodes=true",
        "++algo.config.eval.save_goal_reached_only=false",
        "++algo.config.eval.save_videos=false",
        "++algo.config.eval.save_trajectories=false",
        "++algo.config.eval.a2_diagnostic_trace_enabled=false",
        "++algo.config.eval.a2_eval_v20_strict_telemetry=false",
        "++algo.config.eval.a2_eval_m41_strict_telemetry=false",
        "++env.config.a2_v20_R2_evidence_enabled=false",
        "++env.config.a2_v20_R2_full_evidence=false",
        "++env.config.a2_v20_R2_formal_launch=false",
        "++env.config.a2_v20_R2_source_lock_sha256=null",
        "++env.config.a2_v20_R2_admission_bundle_sha256=null",
        "++env.config.a2_v20_formal_launch=false",
        "++env.config.a2_v20_report_only=true",
        f"++env.config.a2_v20_R2_group={group}",
        "++env.config.a2_v20_R2_seed=0",
        f"++env.config.save_rendering_dir={output_root / 'renderings'}",
        f"++eval_name=report_only_{case['case_id']}_20260806",
        f"++eval_output_dir={output_root}",
        f"++eval_log_dir={output_root / 'hydra'}",
    ]
    env = _contract_env(int(case["gpu"]), "v20")
    source_run_root = str(_repo_path(str(case["route_a_receipt"])).parent)
    if any(token.startswith(("+r2_bound_config_path=", "+r2_bound_config_sha256=", "+r2_resolved_config_sha256=", "+r2_command_sha256=")) for token in argv):
        raise RenderLauncherError("v20 report-only argv contains a formal R2 identity token")
    if any("base_v20_R2_admission_execution_v1" in token for token in argv):
        raise RenderLauncherError("v20 report-only argv retained formal admission identity")
    if any(source_run_root in token for token in argv):
        raise RenderLauncherError(f"v20 derived argv retains Route-A writable path: {source_run_root}")
    return {
        "schema": "a2_piper_report_render_case_plan_v1",
        "case": dict(case),
        "version": "v20",
        "gpu": int(case["gpu"]),
        "argv": argv,
        "env": env,
        "command_sha256": hash_command_env(argv, env),
        "checkpoint_path": str(checkpoint),
        "checkpoint_sha256": case["checkpoint_sha256"],
        "source_bindings": {
            "parent_route_a_receipt_path": str(_repo_path(str(case["route_a_receipt"]))),
            "parent_route_a_receipt_sha256": case["route_a_receipt_sha256"],
            "parent_checkpoint_path": str(checkpoint),
            "parent_checkpoint_sha256": case["checkpoint_sha256"],
            "parent_bound_config_path": str(_repo_path(str(case["bound_config"]))),
            "parent_bound_config_sha256": case["bound_config_sha256"],
            "saved_run_config": str(saved_config),
            "saved_run_config_sha256": case["saved_run_config_sha256"],
            "checkpoint_adjacent_saved_run_config": str(saved_config),
            "checkpoint_adjacent_saved_run_config_sha256": case["saved_run_config_sha256"],
            "eval_entrypoint": str(REPO / "gr00t/rl/eval_agent_trl.py"),
            "eval_entrypoint_sha256": _sha256(REPO / "gr00t/rl/eval_agent_trl.py"),
            "launcher_hash_authority": str(V20_HASH_SOURCE),
            "launcher_hash_authority_sha256": _sha256(V20_HASH_SOURCE),
        },
        "output_root": str(output_root),
        "media_gate": {"expected_finalized_mp4_count": 3},
        "startup_lock": {"path": str(LOCK_PATH), "marker": LOCK_MARKER.decode("ascii")},
    }


def _v21b_plan(case: Mapping[str, Any], row: Mapping[str, Any], queue_sha256: str) -> dict[str, Any]:
    checkpoint = _repo_path(str(case["checkpoint"]))
    output_root = _repo_path(str(case["output_root"]))
    source_argv = row.get("argv")
    if not isinstance(source_argv, list) or not all(isinstance(item, str) for item in source_argv):
        raise RenderLauncherError(f"signed R17 argv is invalid: {case['case_id']}")
    signed_tokens = (
        "num_envs=16",
        f"seed={row['seed']}",
        "use_wandb=false",
        "env.config.a2_v21B_census_topology=canonical16",
        "+env.config.a2_v21B_evidence_aggregation_topology=canonical16",
        f"+env.config.a2_v21B_queue_row_id='{row['row_id']}'",
    )
    if any(token not in source_argv for token in signed_tokens):
        raise RenderLauncherError(f"signed canonical16 selector token missing: {row['row_id']}")
    argv = list(source_argv)
    parent_identity_tokens = [token for token in argv if token.startswith(V21B_COMMAND_IDENTITY_PREFIX)]
    if len(parent_identity_tokens) != 1:
        raise RenderLauncherError(f"signed row must contain exactly one evaluation identity token: {row['row_id']}")
    _remove_exact_prefix(argv, V21B_COMMAND_IDENTITY_PREFIX)
    report_run_uuid = (
        f"report-v21B-{case['case_id']}-seed{int(row['seed'])}-canonical16-20260806"
    )
    report_queue_row_id = (
        f"report_only:{case['case_id']}:canonical16:seed{int(row['seed'])}"
    )
    _set_hydra(argv, "env.config.a2_v21B_run_uuid=", repr(report_run_uuid), plus="+")
    _set_hydra(argv, "env.config.a2_v21B_queue_row_id=", repr(report_queue_row_id), plus="+")
    _set_hydra(argv, "simulator.config.cameras.enable_cameras=", "false", plus="")
    _set_hydra(argv, "simulator.config.render_results=", "true", plus="")
    _replace_quoted_path(argv, "env.config.a2_v21B_terminal_export_root=", output_root / "terminal_exports")
    _replace_quoted_path(argv, "+env.config.a2_v21B_evaluation_root=", output_root)
    _replace_once(argv, "+eval_name=", repr(f"{case['case_id']}_report_render_20260806"))
    _replace_quoted_path(argv, "+eval_output_dir=", output_root)
    _set_hydra(argv, "env.config.save_rendering_dir=", str(output_root / "renderings"))
    _set_hydra(argv, "eval_log_dir=", str(output_root))
    _set_hydra(argv, "output_dir=", str(output_root / "app_output"))
    env = _contract_env(int(case["gpu"]), "v21B")
    original_root = str(_repo_path(str(row["evaluation_root"])))
    writable_keys = ("evaluation_root", "eval_output_dir", "terminal_export_root", "save_rendering_dir", "eval_log_dir", "output_dir")
    stale = [token for token in argv if original_root in token and any(key in token for key in writable_keys)]
    if stale:
        raise RenderLauncherError(f"v21B derived argv retains original writable path: {stale}")
    camera = [token for token in argv if token.lstrip("+").startswith("simulator.config.cameras.enable_cameras=")]
    render = [token for token in argv if token.lstrip("+").startswith("simulator.config.render_results=")]
    if camera != ["simulator.config.cameras.enable_cameras=false"] or render != ["simulator.config.render_results=true"]:
        raise RenderLauncherError(f"v21B camera/render contract mismatch: {camera} {render}")
    preserved_semantics = (
        "a2_v20_send_hinge_threshold",
        "a2_v21B_target_root_ramp_theta_rad",
        "a2_v20_arm",
        "a2_v21B_arm",
        "scenario_manifest",
        "canonical_manifest",
        "census_topology",
        "evidence_aggregation_topology",
    )
    for token in source_argv:
        if any(key in token for key in preserved_semantics) and token not in parent_identity_tokens:
            if token not in argv:
                raise RenderLauncherError(f"v21B derived argv changed signed scenario/torque semantics: {token}")
    argv_without_identity_token = list(argv)
    declared_evaluation_command_sha256 = v21b_command_sha256(argv_without_identity_token, env)
    argv.append(V21B_COMMAND_IDENTITY_PREFIX + declared_evaluation_command_sha256)
    identity_tokens = [token for token in argv if token.startswith(V21B_COMMAND_IDENTITY_PREFIX)]
    if len(identity_tokens) != 1 or identity_tokens[0].split("=", 1)[1] != declared_evaluation_command_sha256:
        raise RenderLauncherError(f"v21B report command identity declaration is invalid: {case['case_id']}")
    if v21b_command_sha256(
        [token for token in argv if not token.startswith(V21B_COMMAND_IDENTITY_PREFIX)], env
    ) != declared_evaluation_command_sha256:
        raise RenderLauncherError(f"v21B report command identity does not round-trip: {case['case_id']}")
    if report_run_uuid == row.get("run_uuid") or report_queue_row_id == row.get("row_id"):
        raise RenderLauncherError(f"v21B report identity reused signed parent identity: {case['case_id']}")
    return {
        "schema": "a2_piper_report_render_case_plan_v1",
        "case": dict(case),
        "version": "v21B",
        "gpu": int(case["gpu"]),
        "argv": argv,
        "env": env,
        "report_run_uuid": report_run_uuid,
        "report_queue_row_id": report_queue_row_id,
        "declared_evaluation_command_sha256": declared_evaluation_command_sha256,
        "command_sha256": hash_command_env(argv, env),
        "checkpoint_path": str(checkpoint),
        "checkpoint_sha256": case["checkpoint_sha256"],
        "source_bindings": {
            "parent_signed_queue_path": str(V21_QUEUE),
            "parent_signed_queue_sha256": queue_sha256,
            "parent_signed_queue_row_id": row["row_id"],
            "parent_signed_run_uuid": row["run_uuid"],
            "parent_signed_evaluation_command_sha256": row["evaluation_command_sha256"],
            "parent_signed_canonical_manifest_sha256": row["canonical_manifest_sha256"],
            "v21b_command_hash_authority": str(V21B_HASH_SOURCE),
            "v21b_command_hash_authority_sha256": _sha256(V21B_HASH_SOURCE),
            "surface_env_id": case["scenario_contract"]["surface_env_id"],
            "surface_scenario_id": case["scenario_contract"]["surface_scenario_id"],
        },
        "output_root": str(output_root),
        "media_gate": {
            "expected_primary_v21b_mp4_count": 48,
            "primary_episode": 0,
            "expected_env_ids": list(range(16)),
            "expected_cameras": ["main", "handle_top", "handle_side"],
        },
        "startup_lock": {"path": str(LOCK_PATH), "marker": LOCK_MARKER.decode("ascii")},
    }


def _validate_case_selection(
    payload: Mapping[str, Any], gpu: int, case_ids: Sequence[str] | None
) -> frozenset[str] | None:
    if case_ids is None:
        return None
    if not case_ids:
        raise RenderLauncherError("--case-id requires at least one case ID")
    if any(not isinstance(case_id, str) or not case_id for case_id in case_ids):
        raise RenderLauncherError("--case-id values must be non-empty strings")
    counts = Counter(case_ids)
    duplicates = sorted(case_id for case_id, count in counts.items() if count > 1)
    if duplicates:
        raise RenderLauncherError(f"duplicate --case-id selector(s): {duplicates}")
    cases = payload["cases"]
    case_by_id = {str(case["case_id"]): case for case in cases}
    unknown = sorted(case_id for case_id in case_ids if case_id not in case_by_id)
    if unknown:
        raise RenderLauncherError(f"unknown --case-id selector(s): {unknown}")
    cross_gpu = sorted(
        case_id for case_id in case_ids if int(case_by_id[case_id]["gpu"]) != gpu
    )
    if cross_gpu:
        raise RenderLauncherError(f"--case-id selector(s) are assigned to another GPU: {cross_gpu}")
    return frozenset(case_ids)


def _build_plans(
    payload: Mapping[str, Any],
    sources: Mapping[str, Any],
    gpu: int,
    case_ids: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    selected_case_ids = _validate_case_selection(payload, gpu, case_ids)
    queue = sources["queue"]
    queue_sha256 = str(payload["source_contracts"]["v21b_signed_queue_sha256"])
    queue_by_id = sources["queue_by_id"]
    historic = sources["historic_v19"]
    plans = []
    for case in payload["cases"]:
        if case["gpu"] != gpu:
            continue
        if selected_case_ids is not None and case["case_id"] not in selected_case_ids:
            continue
        if case["version"] == "v19":
            plan = _v19_plan(case, historic)
        elif case["version"] == "v20":
            receipt = _load_json(_repo_path(str(case["route_a_receipt"])))
            plan = _v20_plan(case, receipt)
        else:
            row = queue_by_id[case["signed_queue_row_id"]]
            plan = _v21b_plan(case, row, queue_sha256)
        _check_fresh_root(Path(plan["output_root"]))
        plans.append(plan)
    expected_count = 4 if selected_case_ids is None else len(selected_case_ids)
    if len(plans) != expected_count:
        raise RenderLauncherError(f"GPU {gpu} expected {expected_count} selected cases, got {len(plans)}")
    return plans


def _write_exclusive(path: Path, payload: Any) -> None:
    if path.exists() or path.is_symlink():
        raise RenderLauncherError(f"refusing to overwrite evidence file: {path}")
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _contains_marker(path: Path) -> bool:
    try:
        return LOCK_MARKER in path.read_bytes()
    except OSError:
        return False


def _collect_media_inventory(plan: Mapping[str, Any], output_root: Path) -> dict[str, Any]:
    """Apply the pre-PASS media cardinality gate and return its receipt payload."""

    renderings_root = output_root / "renderings"
    media_paths: list[Path] = []
    invalid_media_paths: list[str] = []
    writing_mp4_paths: list[str] = []
    renderings_regular = (
        renderings_root.exists()
        and not renderings_root.is_symlink()
        and renderings_root.is_dir()
    )
    if not renderings_regular:
        invalid_media_paths.append("renderings")
    if output_root.exists() and not output_root.is_dir():
        invalid_media_paths.append(".")
    elif output_root.exists():
        for path in output_root.rglob("*"):
            suffix = path.suffix.lower()
            is_media = suffix in MEDIA_SUFFIXES or path.name.lower().endswith(".writing.mp4")
            in_renderings = renderings_root in path.parents
            if path.is_symlink() and (is_media or in_renderings or path == renderings_root):
                invalid_media_paths.append(str(path.relative_to(output_root)))
            if not is_media:
                continue
            media_paths.append(path)
            if path.name.lower().endswith(".writing.mp4"):
                writing_mp4_paths.append(str(path.relative_to(output_root)))
            if path.is_symlink() or not path.is_file():
                invalid_media_paths.append(str(path.relative_to(output_root)))

    final_mp4_paths = sorted(
        str(path.relative_to(output_root))
        for path in media_paths
        if path.suffix.lower() == ".mp4" and not path.name.lower().endswith(".writing.mp4")
    )
    direct_rendering_mp4_paths: list[Path] = []
    if renderings_regular:
        direct_rendering_mp4_paths = [
            path
            for path in renderings_root.iterdir()
            if (
                path.suffix.lower() == ".mp4"
                and not path.name.lower().endswith(".writing.mp4")
                and path.is_file()
                and not path.is_symlink()
            )
        ]
    inventory: dict[str, Any] = {
        "schema": "a2_piper_report_media_cardinality_v1",
        "version": plan["version"],
        "media_root": str(renderings_root),
        "renderings_directory_regular": renderings_regular,
        "media_paths": sorted(str(path.relative_to(output_root)) for path in media_paths),
        "invalid_media_paths": sorted(set(invalid_media_paths)),
        "writing_mp4_paths": sorted(set(writing_mp4_paths)),
        "final_mp4_paths": final_mp4_paths,
        "finalized_mp4_count": len(final_mp4_paths),
    }
    expected_env_ids = (0,) if plan["version"] in {"v19", "v20"} else tuple(range(16))
    expected_primary = {
        (env_id, 0, camera)
        for env_id in expected_env_ids
        for camera in ("main", "handle_top", "handle_side")
    }
    primary_paths: list[str] = []
    primary_keys: list[tuple[int, int, str]] = []
    malformed_primary: list[str] = []
    primary_path_set: set[str] = set()
    for path in direct_rendering_mp4_paths:
        relative = str(path.relative_to(output_root))
        match = PRIMARY_V21B_MP4_RE.fullmatch(path.name)
        if match is None:
            if "_episode0000" in Path(relative).name:
                malformed_primary.append(relative)
            continue
        env_id = int(match.group("env"))
        episode = int(match.group("episode"))
        camera = {
            None: "main",
            "_handle_top": "handle_top",
            "_handle_side": "handle_side",
        }[match.group("camera")]
        key = (env_id, episode, camera)
        if key in expected_primary:
            primary_paths.append(relative)
            primary_path_set.add(relative)
            primary_keys.append(key)
    primary_key_counts = Counter(primary_keys)
    duplicate_primary = sorted(
        f"env{env_id:04d}_episode{episode:04d}:{camera}:{count}"
        for (env_id, episode, camera), count in primary_key_counts.items()
        if count != 1
    )
    missing_primary = sorted(
        f"env{env_id:04d}_episode{episode:04d}:{camera}"
        for env_id, episode, camera in expected_primary
        if (env_id, episode, camera) not in primary_key_counts
    )
    auxiliary_paths = sorted(path for path in final_mp4_paths if path not in primary_path_set)
    expected_primary_labels = sorted(
        f"env{env_id:04d}_episode{episode:04d}:{camera}"
        for env_id, episode, camera in expected_primary
    )
    primary_labels = sorted(
        f"env{env_id:04d}_episode{episode:04d}:{camera}"
        for env_id, episode, camera in primary_keys
    )
    primary_set_complete = (
        renderings_regular
        and len(primary_paths) == len(expected_primary)
        and set(primary_keys) == expected_primary
        and not duplicate_primary
        and not malformed_primary
    )
    common_primary_inventory = {
        "expected_primary_media_keys": expected_primary_labels,
        "primary_media_keys": primary_labels,
        "primary_media_paths": sorted(primary_paths),
        "primary_media_cardinality": len(primary_paths),
        "missing_primary_media_keys": missing_primary,
        "duplicate_primary_media_keys": duplicate_primary,
        "malformed_primary_paths": sorted(malformed_primary),
        "auxiliary_mp4_paths": auxiliary_paths,
        "auxiliary_mp4_count": len(auxiliary_paths),
        "pass": (
            primary_set_complete
            and not inventory["invalid_media_paths"]
            and not inventory["writing_mp4_paths"]
        ),
    }
    if plan["version"] in {"v19", "v20"}:
        inventory.update(
            {
                "expected_finalized_mp4_count": 3,
                "expected_primary_mp4_count": 3,
                "primary_episode": 0,
                "primary_v21b_set_complete": None,
                "primary_v19_v20_set_complete": primary_set_complete,
                **common_primary_inventory,
            }
        )
        inventory["pass"] = (
            inventory["pass"]
            and inventory["finalized_mp4_count"] == inventory["expected_finalized_mp4_count"]
            and inventory["auxiliary_mp4_count"] == 0
        )
        return inventory
    inventory.update(
        {
            "expected_primary_v21b_mp4_count": 48,
            "primary_episode": 0,
            "primary_mp4_paths": sorted(primary_paths),
            "primary_v21b_cardinality": len(primary_paths),
            "primary_v21b_set_complete": primary_set_complete,
            "missing_primary_v21b": missing_primary,
            "duplicate_primary_v21b": duplicate_primary,
            "malformed_episode0000": sorted(malformed_primary),
            "auxiliary_mp4_paths": sorted(auxiliary_paths),
            "auxiliary_mp4_count": len(auxiliary_paths),
            **common_primary_inventory,
        }
    )
    return inventory


def _execute_case(plan: Mapping[str, Any]) -> int:
    output_root = Path(str(plan["output_root"]))
    _check_fresh_root(output_root)
    output_root.parent.mkdir(parents=True, exist_ok=True)
    output_root.mkdir()
    _write_exclusive(output_root / "execution_plan.json", plan)
    stdout_path = output_root / "stdout.log"
    stderr_path = output_root / "stderr.log"
    launch_env = os.environ.copy()
    launch_env.update({str(key): str(value) for key, value in plan["env"].items()})
    started_at = _utc_now()
    child_pid: int | None = None
    returncode: int | None = None
    startup_marker_seen = False
    launch_error: str | None = None
    lock_acquired_at: str | None = None
    marker_seen_at: str | None = None
    lock_released_at: str | None = None
    lock_release_reason: str | None = None
    lock_handle = LOCK_PATH.open("a+")
    process: subprocess.Popen[bytes] | None = None
    try:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        lock_acquired_at = _utc_now()
        with stdout_path.open("wb") as stdout_handle, stderr_path.open("wb") as stderr_handle:
            try:
                process = subprocess.Popen(
                    [str(item) for item in plan["argv"]],
                    cwd=str(REPO),
                    env=launch_env,
                    stdout=stdout_handle,
                    stderr=stderr_handle,
                )
                child_pid = process.pid
            except OSError as exc:
                launch_error = repr(exc)
                stderr_handle.write((launch_error + "\n").encode("utf-8", errors="replace"))
            if process is not None:
                while True:
                    if _contains_marker(stdout_path):
                        startup_marker_seen = True
                        marker_seen_at = _utc_now()
                        lock_release_reason = "experience_marker"
                        break
                    observed = process.poll()
                    if observed is not None:
                        returncode = observed
                        lock_release_reason = "child_exit_before_experience_marker"
                        break
                    time.sleep(0.1)
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
                lock_released_at = _utc_now()
                if returncode is None:
                    returncode = process.wait()
    finally:
        if lock_released_at is None:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
            lock_released_at = _utc_now()
            if lock_release_reason is None:
                lock_release_reason = "spawn_error_or_exception"
        lock_handle.close()
    ended_at = _utc_now()
    if returncode is None:
        returncode = 127
    if launch_error is not None:
        returncode = 127
    stdout_sha = _sha256(stdout_path)
    stderr_sha = _sha256(stderr_path)
    media_cardinality = _collect_media_inventory(plan, output_root)
    media_gate_pass = bool(media_cardinality["pass"])
    receipt = {
        "schema": "a2_piper_report_render_process_receipt_v1",
        "case_id": plan["case"]["case_id"],
        "version": plan["version"],
        "purpose": plan["case"]["scenario_contract"]["purpose_label"],
        "physical_gpu": plan["gpu"],
        "argv": list(plan["argv"]),
        "env": dict(sorted({str(k): str(v) for k, v in plan["env"].items()}.items())),
        "command_sha256": plan["command_sha256"],
        "env_sha256": _json_sha256(dict(sorted(plan["env"].items()))),
        "started_at_utc": started_at,
        "ended_at_utc": ended_at,
        "exit_code": returncode,
        "pid": child_pid,
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "stdout_sha256": stdout_sha,
        "stderr_sha256": stderr_sha,
        "stdout_size": stdout_path.stat().st_size,
        "stderr_size": stderr_path.stat().st_size,
        "natural_exit": bool(returncode == 0 and startup_marker_seen and launch_error is None and media_gate_pass),
        "startup_marker": LOCK_MARKER.decode("ascii"),
        "startup_marker_seen": startup_marker_seen,
        "startup_lock": {
            "path": str(LOCK_PATH),
            "acquired_at_utc": lock_acquired_at,
            "marker_seen_at_utc": marker_seen_at,
            "released_at_utc": lock_released_at,
            "release_reason": lock_release_reason,
        },
        "source_bindings": plan["source_bindings"],
        "output_root": str(output_root),
        "launch_error": launch_error,
        "media_cardinality": media_cardinality,
        "media_gate_pass": media_gate_pass,
    }
    _write_exclusive(output_root / "process_receipt.json", receipt)
    if not startup_marker_seen or not media_gate_pass:
        return 1
    return int(returncode)


def _print_plan(plan: Mapping[str, Any], prefix: str) -> None:
    case = plan["case"]
    print(f"{prefix} case={case['case_id']} gpu={plan['gpu']} version={plan['version']}")
    print(f"  checkpoint={plan['checkpoint_path']} sha256={plan['checkpoint_sha256']}")
    print(f"  output_root={plan['output_root']} report_role={case['report_role']}")
    print(f"  media_gate={json.dumps(plan['media_gate'], sort_keys=True, separators=(',', ':'))}")
    if plan["version"] == "v21B":
        contract = case["scenario_contract"]
        print(f"  surface=env{contract['surface_env_id']}/{contract['surface_scenario_id']} expected_primary_videos=48")
    print(f"  source_bindings={json.dumps(plan['source_bindings'], sort_keys=True, separators=(',', ':'))}")
    print(f"  env={json.dumps(plan['env'], sort_keys=True, separators=(',', ':'))}")
    print(f"  command_sha256={plan['command_sha256']}")
    if plan["version"] == "v21B":
        print(f"  declared_evaluation_command_sha256={plan['declared_evaluation_command_sha256']}")
    print(f"  argv_json={json.dumps(plan['argv'], ensure_ascii=False, separators=(',', ':'))}")
    print(f"  command={shlex.join(str(item) for item in plan['argv'])}")


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--gpu", type=int, choices=GPU_IDS, required=True)
    parser.add_argument("--case-id", dest="case_ids", action="append")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan-only", action="store_true")
    mode.add_argument("--execute", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    matrix_path = args.matrix if args.matrix.is_absolute() else REPO / args.matrix
    payload, sources = _load_matrix(matrix_path.resolve())
    plans = _build_plans(payload, sources, int(args.gpu), args.case_ids)
    if args.plan_only:
        for plan in plans:
            _print_plan(plan, "PLAN")
        print(f"PLAN_ONLY_PASS gpu={args.gpu} cases={len(plans)} output_roots_absent=true")
        return 0
    # All selected roots are checked before the first child starts.  A failed case
    # leaves its complete evidence unit and prevents later siblings from running.
    for plan in plans:
        _check_fresh_root(Path(plan["output_root"]))
    for index, plan in enumerate(plans, start=1):
        _print_plan(plan, f"EXECUTE[{index}/{len(plans)}]")
        result = _execute_case(plan)
        print(f"CASE_EXIT case={plan['case']['case_id']} exit_code={result}")
        if result != 0:
            print(f"EXECUTE_STOP first_nonzero_case={plan['case']['case_id']}", file=sys.stderr)
            return result if 0 < result < 256 else 1
    print(f"EXECUTE_PASS gpu={args.gpu} cases={len(plans)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RenderLauncherError as exc:
        print(f"REPORT RENDER LAUNCHER FAIL: {exc}", file=sys.stderr)
        raise SystemExit(2)
