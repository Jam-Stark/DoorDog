"""Build the immutable, serial v20 matched-render queue.

The queue is intentionally a data-only launcher description.  It never starts
Isaac Sim and it never reuses an existing render directory.  Every row uses
the same three ordered door instances and three named cameras; the only
allowed physical device is selected from GPU 0..6; GPU 7 is reserved by another task.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


SCHEMA = "a2_piper_v20_render_queue_v1"
CORE_SCHEMA_ID = "419364d1b0d20130de1f2cd0a4be7b35f8780bc6d933be964778389150172233"
CHECKPOINT_RE = re.compile(r"^model_step_[0-9]{6}\.pt$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GPU_RE = re.compile(r"^[0-6]$")
DEFAULT_RENDER_GPU = "6"
GROUPS = tuple(f"G{index}" for index in range(1, 8))
INSTITUTION_GROUPS = ("G3", "G4", "G5", "G6", "G7")
DEFAULT_RENDER_GROUPS = ("G1", "G3", "G6", "G7")
CAMERAS = ("default", "handle_side", "handle_top")
MATCHED_DOORS = (
    {
        "door_id": "low_light_weak",
        "height_m": 0.80,
        "weight_kg": 80.0,
        "spring": "weak",
    },
    {
        "door_id": "high_heavy_strong",
        "height_m": 1.10,
        "weight_kg": 160.0,
        "spring": "strong",
    },
    {
        "door_id": "median",
        "height_m": 0.95,
        "weight_kg": 120.0,
        "spring": "median",
    },
)
MATCHED_DOOR_PAIRS = [[door["height_m"], door["weight_kg"]] for door in MATCHED_DOORS]


class V20RenderQueueError(ValueError):
    """Raised when a v20 render queue would violate the frozen contract."""


def _checkpoint(path: Path) -> Path:
    resolved = Path(path).expanduser().resolve()
    if not resolved.is_file() or CHECKPOINT_RE.fullmatch(resolved.name) is None:
        raise V20RenderQueueError(
            "checkpoint must be an existing immutable model_step_######.pt file: "
            f"{resolved}"
        )
    return resolved


def sha256_file(path: Path) -> str:
    path = Path(path)
    if not path.is_file():
        raise V20RenderQueueError(f"cannot hash missing checkpoint: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _gpu(value: str) -> str:
    if not isinstance(value, str) or GPU_RE.fullmatch(value) is None:
        raise V20RenderQueueError("v20 render queue requires one physical gpu in 0..6; GPU7 is reserved")
    return value


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _group(value: Any) -> str:
    if not isinstance(value, str) or value not in GROUPS:
        raise V20RenderQueueError(f"group must be one of {GROUPS}; got {value!r}")
    return value


def _checkpoint_value(value: Any) -> tuple[Path, str | None]:
    if isinstance(value, Mapping):
        path = value.get("checkpoint") or value.get("path")
        supplied_hash = value.get("checkpoint_sha256") or value.get("sha256")
    else:
        path = value
        supplied_hash = None
    if not isinstance(path, (str, Path)):
        raise V20RenderQueueError(f"checkpoint value must contain a path; got {value!r}")
    checkpoint = _checkpoint(Path(path))
    actual_hash = sha256_file(checkpoint)
    if supplied_hash is not None:
        if not isinstance(supplied_hash, str) or SHA256_RE.fullmatch(supplied_hash) is None:
            raise V20RenderQueueError("checkpoint_sha256 must be lowercase SHA-256")
        if supplied_hash != actual_hash:
            raise V20RenderQueueError(
                f"checkpoint SHA-256 mismatch for {checkpoint}: {supplied_hash} != {actual_hash}"
            )
    return checkpoint, actual_hash


def _normalize_checkpoints(
    checkpoints: Mapping[str, Any],
    *,
    selected_group: str | None,
) -> tuple[dict[str, tuple[Path, str]], str]:
    if not isinstance(checkpoints, Mapping):
        raise V20RenderQueueError("checkpoints must be a mapping group -> checkpoint")
    keys = set(checkpoints)
    if any(key not in GROUPS for key in keys):
        raise V20RenderQueueError(f"unknown render group(s): {sorted(keys - set(GROUPS))}")
    if selected_group is None:
        if keys == set(DEFAULT_RENDER_GROUPS):
            selected_group = "G3"
        else:
            raise V20RenderQueueError(
                "selected_group is required unless the exact default groups G1/G3/G6/G7 are supplied"
            )
    selected_group = _group(selected_group)
    if selected_group not in INSTITUTION_GROUPS:
        raise V20RenderQueueError("selected_group must be an I-enabled group G3..G7")
    expected = {"G1", selected_group, "G6", "G7"}
    if set(keys) != expected:
        raise V20RenderQueueError(
            f"render queue requires exactly {sorted(expected)}; got {sorted(keys)}"
        )
    normalized = {group: _checkpoint_value(checkpoints[group]) for group in sorted(keys)}
    if len({row[0] for row in normalized.values()}) != len(normalized):
        raise V20RenderQueueError("each rendered group must bind a distinct checkpoint")
    return normalized, selected_group


def _door_override() -> str:
    return "++env.config.a2_eval_door_handle_height_weight_pairs=" + json.dumps(
        MATCHED_DOOR_PAIRS, separators=(",", ":")
    )


def build_render_command(
    checkpoint: Path,
    output_dir: Path,
    *,
    group: str,
    role: str,
    gpu: str = DEFAULT_RENDER_GPU,
    seed: int = 0,
    checkpoint_sha256: str | None = None,
) -> dict[str, Any]:
    """Build one exact three-env/three-camera render command."""

    group = _group(group)
    checkpoint, actual_hash = _checkpoint_value(
        {"checkpoint": checkpoint, "checkpoint_sha256": checkpoint_sha256}
    )
    output_dir = Path(output_dir).expanduser().resolve()
    gpu = _gpu(gpu)
    if role not in {"control", "institution", "full", "replicate"}:
        raise V20RenderQueueError(f"unsupported v20 render role: {role!r}")
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise V20RenderQueueError("render seed must be a non-negative integer")
    diagnostic_terms = [
        "a2_v20_send_ready",
        "a2_v20_pre_send_root_crossing",
        "a2_v20_hinge_at_first_root_crossing",
        "a2_v20_arm_tangent_share",
        "a2_v20_arc_tracking_quality",
        "a2_v20_handle_arc_position_error_m",
        "a2_v20_handle_arc_orientation_error_rad",
        "a2_v20_hinge_at_release",
        "a2_v20_post_release_body_contact",
        "a2_v20_post_release_body_force_max",
        "complete",
    ]
    eval_name = f"base_v20_{group}_matched3env_3cam_seed{seed}"
    argv = [
        sys.executable,
        "-m",
        "gr00t.rl.eval_agent_trl",
        f"+checkpoint={checkpoint}",
        "++checkpoint_load_mode=full",
        "++auto_load_latest=false",
        "++headless=true",
        "++num_envs=3",
        f"++seed={seed}",
        "++use_wandb=false",
        "++simulator.config.cameras.enable_cameras=false",
        "++simulator.config.render_results=true",
        "++algo.config.num_mini_batches=3",
        "++algo.config.eval.num_eval_episodes=3",
        "++algo.config.eval.eval_num_envs_episodes=true",
        "++algo.config.eval.dump_to_log_metrics=true",
        "++algo.config.eval.a2_diagnostic_trace_enabled=true",
        "++algo.config.eval.a2_eval_m41_strict_telemetry=true",
        "++algo.config.eval.a2_eval_v20_strict_telemetry=true",
        "++algo.config.eval.a2_eval_diagnostic_trace_enabled=true",
        "++algo.config.eval.a2_forced_gripper_close_enabled=false",
        "++algo.config.eval.a2_hold_oracle_enabled=false",
        "++algo.config.eval.save_goal_reached_only=false",
        "++algo.config.eval.save_videos=false",
        "++algo.config.eval.save_trajectories=false",
        "++algo.config.eval.a2_diagnostic_reward_terms=" + json.dumps(diagnostic_terms, separators=(",", ":")),
        _door_override(),
        f"++env.config.save_rendering_dir={output_dir / 'renderings'}",
        f"++eval_name={eval_name}",
        f"++eval_output_dir={output_dir}",
    ]
    return {
        "argv": argv,
        "shell": " ".join(shlex.quote(arg) for arg in argv),
        "env": {
            "CUDA_VISIBLE_DEVICES": gpu,
            "ACCELERATE_TORCH_DEVICE": "cuda:0",
            "VK_ICD_FILENAMES": "/usr/share/vulkan/icd.d/nvidia_icd.json",
        },
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": actual_hash,
        "group": group,
        "role": role,
        "seed": seed,
        "num_envs": 3,
        "expected_door_count": len(MATCHED_DOORS),
        "expected_door_pairs": MATCHED_DOOR_PAIRS,
        "expected_camera_names": list(CAMERAS),
        "expected_video_count": len(MATCHED_DOORS) * len(CAMERAS),
        "output_dir": str(output_dir),
        "execution": f"serial physical GPU{gpu} mapped to logical cuda:0; no retry, overwrite, or artifact reuse",
        "core_schema_id": CORE_SCHEMA_ID,
    }


def _role(group: str, selected_group: str) -> str:
    return {
        "G1": "control",
        selected_group: "institution",
        "G6": "full",
        "G7": "replicate",
    }[group]


def build_queue(
    checkpoints: Mapping[str, Any],
    output_root: Path,
    *,
    selected_group: str | None = None,
    gpu: str = DEFAULT_RENDER_GPU,
) -> dict[str, Any]:
    """Build the four-row serial queue for the frozen matched render review."""

    gpu = _gpu(gpu)
    normalized, selected_group = _normalize_checkpoints(
        checkpoints, selected_group=selected_group
    )
    output_root = Path(output_root).expanduser().resolve()
    rows = []
    order = ("G1", selected_group, "G6", "G7")
    for group in order:
        checkpoint, checkpoint_hash = normalized[group]
        rows.append(
            build_render_command(
                checkpoint,
                output_root / f"{group}_matched3env_3cam_seed0",
                group=group,
                role=_role(group, selected_group),
                gpu=gpu,
                seed=0,
                checkpoint_sha256=checkpoint_hash,
            )
        )
    return {
        "schema": SCHEMA,
        "core_schema_id": CORE_SCHEMA_ID,
        "serial": True,
        "physical_gpu": gpu,
        "row_count": len(rows),
        "selected_institution_group": selected_group,
        "required_groups": list(order),
        "matched_doors": list(MATCHED_DOORS),
        "matched_door_pairs": MATCHED_DOOR_PAIRS,
        "cameras": list(CAMERAS),
        "rows": rows,
    }


def _markdown(queue: Mapping[str, Any]) -> str:
    lines = [
        "# A2 Piper v20 matched render queue",
        "",
        f"Physical GPU: `{queue['physical_gpu']}` (serial)",
        f"Selected institution group: `{queue['selected_institution_group']}`",
        "",
        "| Group | Role | Checkpoint | Envs | Doors | Cameras | Output |",
        "|---|---|---|---:|---:|---:|---|",
    ]
    for row in queue["rows"]:
        lines.append(
            f"| {row['group']} | {row['role']} | `{row['checkpoint']}` | "
            f"{row['num_envs']} | {row['expected_door_count']} | "
            f"{len(row['expected_camera_names'])} | `{row['output_dir']}` |"
        )
    lines.extend(
        [
            "",
            "Door order: "
            + ", ".join(
                f"{door['door_id']}({door['height_m']:.2f}m/{door['weight_kg']:.0f}kg)"
                for door in queue["matched_doors"]
            ),
            "",
            "The queue is immutable; a different payload at the same output path is a failure.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_immutable_outputs(queue: Mapping[str, Any], output_root: Path) -> tuple[Path, Path]:
    """Write deterministic queue JSON/Markdown, refusing overwrite or drift."""

    output_root = Path(output_root).expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    json_path = output_root / "a2_piper_v20_render_queue.json"
    md_path = output_root / "a2_piper_v20_render_queue.md"
    json_payload = json.dumps(queue, indent=2, sort_keys=True) + "\n"
    md_payload = _markdown(queue)
    if json_path.exists() or md_path.exists():
        if not json_path.is_file() or not md_path.is_file():
            raise V20RenderQueueError("immutable render queue outputs are incomplete")
        try:
            existing_json = json.loads(json_path.read_text(encoding="utf-8"))
            existing_md = md_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise V20RenderQueueError("existing render queue outputs are unreadable") from exc
        if _canonical_json(existing_json) != _canonical_json(queue) or existing_md != md_payload:
            raise V20RenderQueueError("immutable render queue outputs differ")
        return json_path, md_path
    json_path.write_text(json_payload, encoding="utf-8")
    md_path.write_text(md_payload, encoding="utf-8")
    return json_path, md_path


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--group-checkpoint",
        action="append",
        required=True,
        metavar="GROUP=PATH",
        help="repeat exactly four times for G1, selected I-cell, G6, and G7",
    )
    parser.add_argument("--selected-group", choices=INSTITUTION_GROUPS)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--gpu", default=DEFAULT_RENDER_GPU)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    checkpoints: dict[str, str] = {}
    for token in args.group_checkpoint:
        if "=" not in token:
            raise V20RenderQueueError("--group-checkpoint must be GROUP=PATH")
        group, path = token.split("=", 1)
        if group in checkpoints:
            raise V20RenderQueueError(f"duplicate group checkpoint: {group}")
        checkpoints[group] = path
    queue = build_queue(
        checkpoints,
        args.output_root,
        selected_group=args.selected_group,
        gpu=args.gpu,
    )
    paths = write_immutable_outputs(queue, args.output_root)
    print(f"v20 render queue JSON: {paths[0]}")
    print(f"v20 render queue Markdown: {paths[1]}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except V20RenderQueueError as exc:
        print(f"v20 RENDER QUEUE FAIL: {exc}", file=sys.stderr)
        raise SystemExit(2)
