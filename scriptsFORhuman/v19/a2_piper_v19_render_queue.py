"""Build the exact serial winner/G7 render queue required by the v19 plan."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


SCHEMA = "a2_piper_v19_render_queue_v1"
CHECKPOINT_RE = re.compile(r"^model_step_[0-9]+\.pt$")
GPU_RE = re.compile(r"(?:0|[1-9][0-9]*)")
WINNER_GROUPS = {"G1", "G2", "G3", "G4", "G5", "G6"}
P0_DIAGNOSTIC_REWARD_TERMS = (
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


class V19RenderQueueError(ValueError):
    """Raised when a v19 render command would violate the plan contract."""


def _checkpoint(path: Path) -> Path:
    resolved = Path(path).expanduser().resolve()
    if not resolved.is_file() or CHECKPOINT_RE.fullmatch(resolved.name) is None:
        raise V19RenderQueueError(f"checkpoint must be an existing numbered model_step file: {resolved}")
    return resolved


def _gpu(value: str) -> str:
    if not isinstance(value, str) or GPU_RE.fullmatch(value) is None:
        raise V19RenderQueueError(f"gpu must be an exact physical decimal id; got {value!r}")
    return value


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def build_render_command(
    checkpoint: Path,
    output_dir: Path,
    *,
    role: str,
    group: str,
    gpu: str = "7",
) -> dict[str, Any]:
    checkpoint = _checkpoint(checkpoint)
    output_dir = Path(output_dir).expanduser().resolve()
    gpu = _gpu(gpu)
    if role == "winner":
        if group not in WINNER_GROUPS:
            raise V19RenderQueueError("winner group must be one of G1..G6")
        num_envs = 2
        door_eval_override = "++env.config.a2_eval_door_handle_height_linspace=[0.80,1.10]"
    elif role == "g7_probe":
        if group != "G7":
            raise V19RenderQueueError("g7_probe role requires group G7")
        num_envs = 1
        door_eval_override = (
            "++env.config.a2_eval_door_handle_height_weight_pairs=[[1.10,120.0]]"
        )
    else:
        raise V19RenderQueueError(f"unsupported render role {role!r}")

    diagnostic_terms = "[" + ",".join(P0_DIAGNOSTIC_REWARD_TERMS) + "]"
    eval_name = f"base_v19_{group}_{role}_{num_envs}env_3cam_seed0_20260727"
    argv = [
        sys.executable,
        "-m",
        "gr00t.rl.eval_agent_trl",
        f"+checkpoint={checkpoint}",
        "++checkpoint_load_mode=full",
        "++auto_load_latest=false",
        "++headless=true",
        f"++num_envs={num_envs}",
        "++seed=0",
        "++use_wandb=false",
        "++simulator.config.cameras.enable_cameras=false",
        "++simulator.config.render_results=true",
        f"++algo.config.num_mini_batches={num_envs}",
        f"++algo.config.eval.num_eval_episodes={num_envs}",
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
        door_eval_override,
        f"++env.config.save_rendering_dir={output_dir / 'renderings'}",
        f"++eval_name={eval_name}",
        f"++eval_output_dir={output_dir}",
    ]
    return {
        "argv": argv,
        "env": {
            "CUDA_VISIBLE_DEVICES": gpu,
            "ACCELERATE_TORCH_DEVICE": "cuda:0",
            "VK_ICD_FILENAMES": "/usr/share/vulkan/icd.d/nvidia_icd.json",
        },
        "checkpoint": str(checkpoint),
        "group": group,
        "role": role,
        "seed": 0,
        "num_envs": num_envs,
        "expected_camera_names": ["default", "handle_side", "handle_top"],
        "expected_video_count": num_envs * 3,
        "output_dir": str(output_dir),
        "execution": "serial physical GPU mapped to logical cuda:0 for UsdRT; no retry or artifact reuse",
    }


def build_queue(
    winner_group: str,
    winner_checkpoint: Path,
    g7_checkpoint: Path,
    output_root: Path,
    *,
    gpu: str = "7",
) -> dict[str, Any]:
    if winner_group not in WINNER_GROUPS:
        raise V19RenderQueueError("winner group must be one of G1..G6")
    output_root = Path(output_root).expanduser().resolve()
    rows = [
        build_render_command(
            winner_checkpoint,
            output_root / f"winner_{winner_group}_2env_3cam_seed0",
            role="winner",
            group=winner_group,
            gpu=gpu,
        ),
        build_render_command(
            g7_checkpoint,
            output_root / "G7_probe_1env_3cam_seed0",
            role="g7_probe",
            group="G7",
            gpu=gpu,
        ),
    ]
    if rows[0]["checkpoint"] == rows[1]["checkpoint"]:
        raise V19RenderQueueError("winner and G7 render checkpoints must be distinct artifacts")
    if rows[0]["output_dir"] == rows[1]["output_dir"]:
        raise V19RenderQueueError("render output directories must be distinct")
    return {
        "schema": SCHEMA,
        "serial": True,
        "physical_gpu": _gpu(gpu),
        "row_count": 2,
        "rows": rows,
    }


def _markdown(queue: Mapping[str, Any]) -> str:
    lines = [
        "# A2 Piper v19 render queue",
        "",
        "| Role | Group | Checkpoint | Envs | Cameras | Output |",
        "|---|---|---|---:|---:|---|",
    ]
    for row in queue["rows"]:
        lines.append(
            f"| {row['role']} | {row['group']} | `{row['checkpoint']}` | {row['num_envs']} | 3 | `{row['output_dir']}` |"
        )
    return "\n".join(lines) + "\n"


def write_immutable_outputs(queue: Mapping[str, Any], output_root: Path) -> tuple[Path, Path]:
    output_root = Path(output_root).expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    json_path = output_root / "a2_piper_v19_render_queue.json"
    md_path = output_root / "a2_piper_v19_render_queue.md"
    json_payload = json.dumps(queue, indent=2, sort_keys=True) + "\n"
    md_payload = _markdown(queue)
    if json_path.exists() or md_path.exists():
        if not json_path.is_file() or not md_path.is_file():
            raise V19RenderQueueError("immutable render queue outputs are incomplete")
        try:
            existing_json = json.loads(json_path.read_text(encoding="utf-8"))
            existing_md = md_path.read_text(encoding="utf-8")
        except (OSError, json.JSONDecodeError) as exc:
            raise V19RenderQueueError("existing render queue outputs are unreadable") from exc
        if _canonical_json(existing_json) != _canonical_json(queue) or existing_md != md_payload:
            raise V19RenderQueueError("immutable render queue outputs differ")
        return json_path, md_path
    json_path.write_text(json_payload, encoding="utf-8")
    md_path.write_text(md_payload, encoding="utf-8")
    return json_path, md_path


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--winner-group", required=True)
    parser.add_argument("--winner-checkpoint", type=Path, required=True)
    parser.add_argument("--g7-checkpoint", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--gpu", default="7")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    queue = build_queue(
        args.winner_group,
        args.winner_checkpoint,
        args.g7_checkpoint,
        args.output_root,
        gpu=args.gpu,
    )
    paths = write_immutable_outputs(queue, args.output_root)
    print(f"v19 render queue JSON: {paths[0]}")
    print(f"v19 render queue Markdown: {paths[1]}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except V19RenderQueueError as exc:
        print(f"v19 RENDER QUEUE FAIL: {exc}", file=sys.stderr)
        raise SystemExit(2)
