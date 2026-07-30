#!/usr/bin/env python3
"""Run a sealed A2 camera visibility evaluation without training."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))
DEFAULT_ISAACLAB_PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
MAINLINE_RUNTIME_REPOSITORY = Path("/home/baoquanc/workspace/DoorDog-A2_Piper")
CAMERA_CONFIGS = (
    "gemini_335l_centerline",
    "d435i_portrait_a2_head",
    "d435i_landscape_up45_a2_head",
    "d435i_landscape_up60_a2_head",
    "d435i_landscape_stage0_3_pitch_sweep",
    "d435i_dual_portrait_up60_a2_head_oem",
)
CAMERA_RANKING_STAGES = {
    "gemini_335l_centerline": [1, 2, 3, 4, 5],
    "d435i_portrait_a2_head": [1, 2, 3, 4, 5],
    "d435i_landscape_up45_a2_head": [1, 2, 3, 4, 5],
    "d435i_landscape_up60_a2_head": [1, 2, 3, 4, 5],
    "d435i_landscape_stage0_3_pitch_sweep": [0, 1, 2, 3],
    "d435i_dual_portrait_up60_a2_head_oem": [1, 2, 3, 4, 5],
}
SCHEME_C_CONFIGS = {
    "d435i_portrait_a2_head": (
        "C",
        ["d435i_portrait_up12", "a2_head_context"],
    ),
    "d435i_landscape_up45_a2_head": (
        "C-A",
        ["d435i_landscape_up45", "a2_head_context"],
    ),
    "d435i_landscape_up60_a2_head": (
        "C-B",
        ["d435i_landscape_up60", "a2_head_context"],
    ),
    "d435i_dual_portrait_up60_a2_head_oem": (
        "C-B2-DUAL-PORTRAIT-OEM",
        [
            "d435i_left_portrait_up60_toein15",
            "d435i_right_portrait_up60_toein15",
            "a2_head_oem",
        ],
    ),
}
SCHEME_C_HEAD_EXTRINSIC_STATUS = {
    "d435i_portrait_a2_head": "provisional_not_cad_or_calibrated",
    "d435i_landscape_up45_a2_head": "provisional_not_cad_or_calibrated",
    "d435i_landscape_up60_a2_head": "provisional_not_cad_or_calibrated",
    "d435i_dual_portrait_up60_a2_head_oem": (
        "official_unitree_a2_urdf_camera_link"
    ),
}


@dataclass(frozen=True)
class TeacherProfile:
    name: str
    checkpoint: Path
    checkpoint_sha256: str
    config_sha256: str
    runtime_repository: Path
    expected_runtime_commit: str | None


TEACHER_PROFILES = {
    "base_v13_A": TeacherProfile(
        name="base_v13_A",
        checkpoint=(
            REPOSITORY_ROOT
            / "logs_rl/a2_piper_student_distillation_v13_A_teacher-20260717_2103/"
            "model_step_003000.pt"
        ),
        checkpoint_sha256=(
            "d576ca4bc6f596e45a8d744ca766164b374f8aba4409b06bcd7c460d6b057a36"
        ),
        config_sha256=(
            "5cc3a10e3271f4faedaaff3a085344245eb6aa78b3ff29e707e050aa95b0471d"
        ),
        runtime_repository=REPOSITORY_ROOT,
        expected_runtime_commit=None,
    ),
    "base_v16_B": TeacherProfile(
        name="base_v16_B",
        checkpoint=(
            MAINLINE_RUNTIME_REPOSITORY
            / "logs_rl/a2_piper_full_stage_a2_base/"
            "base_v16_B_m29_m32_mass80_160-20260721_230405/"
            "model_step_002000.pt"
        ),
        checkpoint_sha256=(
            "5628a25ee53395ddc581d2da184c32635e109ff3691e54a823ad054236475e3f"
        ),
        config_sha256=(
            "3c8aead9025b66a7f6f2ac3afc81bedc9cdafa1d12bd08fd43058eff8b4fd144"
        ),
        runtime_repository=MAINLINE_RUNTIME_REPOSITORY,
        expected_runtime_commit="815b367f5de2a52b26a4b872d0457af8817d01bd",
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Drive a sealed A2 Teacher eval with an approved diagnostic camera "
            "configuration. No training occurs."
        )
    )
    parser.add_argument(
        "--teacher",
        choices=tuple(TEACHER_PROFILES),
        default="base_v16_B",
    )
    parser.add_argument(
        "--checkpoint",
        type=Path,
        help="Optional relocation of the selected sealed Teacher artifact.",
    )
    parser.add_argument(
        "--camera-config",
        choices=CAMERA_CONFIGS,
        default="gemini_335l_centerline",
    )
    parser.add_argument(
        "--runtime-repository",
        type=Path,
        help=(
            "Optional relocation of the selected Teacher runtime. The checked-out "
            "commit and clean-source gates remain mandatory."
        ),
    )
    parser.add_argument("--python", type=Path, default=DEFAULT_ISAACLAB_PYTHON)
    parser.add_argument("--gpu", type=int, choices=(0, 1), default=0)
    parser.add_argument("--num-envs", type=int, default=16)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def nominal_gemini_335l_crop_intrinsics() -> dict[str, object]:
    from gr00t.rl.utils.a2_camera_pose_sweep import derive_center_crop_intrinsics

    return derive_center_crop_intrinsics(
        native_width=1280,
        native_height=800,
        horizontal_fov_deg=94.0,
        vertical_fov_deg=68.0,
        crop_width=1280,
        crop_height=720,
        output_width=384,
        output_height=216,
    )


def build_eval_command(
    *,
    python_path: Path,
    checkpoint: Path,
    num_envs: int,
    output_dir: Path,
    runtime_repository: Path,
    overlay_repository: Path,
    camera_config: str = "gemini_335l_centerline",
) -> list[str]:
    if isinstance(num_envs, bool) or not isinstance(num_envs, int) or num_envs < 2:
        raise ValueError(
            "num_envs must be an int >= 2 so eval does not trigger the unrelated "
            f"single-env ONNX export; got {num_envs!r}"
        )
    if camera_config not in CAMERA_CONFIGS:
        raise ValueError(
            f"unsupported camera config {camera_config!r}; expected one of {CAMERA_CONFIGS}"
        )
    bootstrap = overlay_repository / "gr00t/rl/scripts/run_a2_camera_pose_eval.py"
    overlay_config_root = overlay_repository / "gr00t/rl/config"
    return [
        str(python_path),
        str(bootstrap),
        "--runtime-repository",
        str(runtime_repository),
        "--overlay-repository",
        str(overlay_repository),
        "--",
        f"checkpoint={checkpoint}",
        f"+camera_pose_sweep={camera_config}",
        f"+num_envs={num_envs}",
        "+headless=true",
        "+use_wandb=false",
        "+multi_gpu=false",
        "++seed=0",
        "++algo.config.num_mini_batches=1",
        "++algo.config.eval.save_videos=false",
        "simulator.config.render_results=false",
        "env.config.save_rendering_dir=null",
        f"eval_output_dir={output_dir}",
        f"eval_log_dir={output_dir}",
        f"hydra.run.dir={output_dir / '.hydra'}",
        f"hydra.searchpath=[file://{overlay_config_root}]",
    ]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_teacher_artifacts(
    *,
    profile: TeacherProfile,
    checkpoint: Path,
) -> dict[str, str]:
    if not checkpoint.is_file():
        raise FileNotFoundError(f"{profile.name} checkpoint not found: {checkpoint}")
    config_path = checkpoint.parent / "config.yaml"
    if not config_path.is_file():
        raise FileNotFoundError(f"checkpoint-adjacent config not found: {config_path}")
    checkpoint_sha256 = sha256_file(checkpoint)
    config_sha256 = sha256_file(config_path)
    if checkpoint_sha256 != profile.checkpoint_sha256:
        raise RuntimeError(
            f"checkpoint is not the sealed {profile.name} Teacher; "
            f"expected_sha256={profile.checkpoint_sha256}, "
            f"actual_sha256={checkpoint_sha256}"
        )
    if config_sha256 != profile.config_sha256:
        raise RuntimeError(
            f"checkpoint-adjacent config is not the sealed {profile.name} config; "
            f"expected_sha256={profile.config_sha256}, actual_sha256={config_sha256}"
        )
    return {
        "checkpoint_sha256": checkpoint_sha256,
        "config_path": str(config_path),
        "config_sha256": config_sha256,
    }


def _git_output(repository: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repository), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def verify_runtime_repository(profile: TeacherProfile) -> str:
    repository = profile.runtime_repository.resolve()
    required_paths = (
        repository / "gr00t/rl/eval_agent_trl.py",
        repository / "gr00t/rl/envs/door/door_open_a2_base.py",
    )
    for required_path in required_paths:
        if not required_path.is_file():
            raise FileNotFoundError(f"Teacher runtime source not found: {required_path}")
    commit = _git_output(repository, "rev-parse", "HEAD")
    if profile.expected_runtime_commit is not None and commit != profile.expected_runtime_commit:
        raise RuntimeError(
            f"{profile.name} runtime commit mismatch; "
            f"expected={profile.expected_runtime_commit}, actual={commit}"
        )
    dirty_runtime_source = _git_output(repository, "status", "--short", "--", "gr00t")
    if dirty_runtime_source:
        raise RuntimeError(
            f"{profile.name} runtime gr00t source is dirty:\n{dirty_runtime_source}"
        )
    return commit


def prepare_writable_eval_input(
    *,
    output_dir: Path,
    checkpoint: Path,
    profile: TeacherProfile,
) -> tuple[Path, Path]:
    config_path = checkpoint.parent / "config.yaml"
    output_dir.mkdir(parents=True, exist_ok=False)
    input_dir = output_dir / "_eval_input"
    input_dir.mkdir()
    runtime_checkpoint = input_dir / checkpoint.name
    runtime_config = input_dir / "config.yaml"
    shutil.copyfile(checkpoint, runtime_checkpoint)
    shutil.copyfile(config_path, runtime_config)
    if sha256_file(runtime_checkpoint) != profile.checkpoint_sha256:
        raise RuntimeError("writable eval checkpoint copy failed SHA-256 verification")
    if sha256_file(runtime_config) != profile.config_sha256:
        raise RuntimeError("writable eval config copy failed SHA-256 verification")
    return runtime_checkpoint, runtime_config


def _validate_candidate_videos(
    output_dir: Path,
    sweep: dict[str, object],
    ranking_stage_indices: list[int],
) -> None:
    candidates = sweep.get("candidates")
    videos = sweep.get("candidate_videos")
    metadata = sweep.get("candidate_video_metadata")
    if not isinstance(candidates, list) or not candidates:
        raise RuntimeError("completed sweep has no camera candidates")
    candidate_names = {candidate["name"] for candidate in candidates}
    if not isinstance(videos, dict) or set(videos) != candidate_names:
        raise RuntimeError("candidate video set does not exactly match camera candidates")
    if not isinstance(metadata, dict):
        raise RuntimeError("completed sweep has no candidate video metadata")
    frame_counts = metadata.get("frame_counts")
    if not isinstance(frame_counts, dict) or set(frame_counts) != candidate_names:
        raise RuntimeError("candidate video frame-count set does not match candidates")
    unique_frame_counts = {int(value) for value in frame_counts.values()}
    if len(unique_frame_counts) != 1 or next(iter(unique_frame_counts)) <= 0:
        raise RuntimeError(f"candidate videos have invalid frame counts: {frame_counts}")
    stage_frame_counts = metadata.get("stage_frame_counts")
    stage_names = {
        0: "stage0_approach",
        1: "stage1_pregrasp",
        2: "stage2_grasp",
        3: "stage3_open",
        4: "stage4_swing",
        5: "stage5_through",
    }
    required_video_stages = [stage_names[index] for index in ranking_stage_indices]
    if not isinstance(stage_frame_counts, dict) or any(
        int(stage_frame_counts.get(stage_name, 0)) < 1
        for stage_name in required_video_stages
    ):
        raise RuntimeError(
            "candidate video trajectory does not cover exact ranking stages "
            f"{ranking_stage_indices}: {stage_frame_counts}"
        )
    for name, raw_path in videos.items():
        video_path = Path(raw_path).resolve()
        if not video_path.is_relative_to(output_dir):
            raise RuntimeError(f"candidate video escaped eval output: {name}={video_path}")
        if not video_path.is_file() or video_path.stat().st_size <= 0:
            raise RuntimeError(f"candidate video is missing or empty: {name}={video_path}")
    writing_files = list(output_dir.rglob("*.writing.mp4"))
    if writing_files:
        raise RuntimeError(f"unsealed candidate video files remain: {writing_files}")
    recommendation = sweep.get("recommendation")
    if not isinstance(recommendation, dict):
        raise RuntimeError("completed sweep has no recommendation")
    recommended_name = recommendation.get("recommended_candidate")
    if sweep.get("recommended_candidate_video") != videos.get(recommended_name):
        raise RuntimeError("recommended candidate video does not match ranking")


def seal_summary(
    *,
    output_dir: Path,
    command: list[str],
    profile: TeacherProfile,
    checkpoint: Path,
    artifact_identity: dict[str, str],
    runtime_checkpoint: Path,
    runtime_config: Path,
    runtime_commit: str,
    metrics: dict[str, object],
    camera_config: str,
) -> Path:
    sweep = metrics.get("a2_camera_pose_sweep")
    if not isinstance(sweep, dict) or sweep.get("status") != "SWEEP_COMPLETE":
        raise RuntimeError("metrics_eval.json has no completed camera pose sweep")
    if sweep.get("training_performed") is not False:
        raise RuntimeError("camera pose sweep must explicitly report training_performed=false")
    expected_ranking_stages = CAMERA_RANKING_STAGES[camera_config]
    if sweep.get("ranking_stage_indices") != expected_ranking_stages:
        raise RuntimeError(
            "camera pose sweep did not rank exact configured stages; "
            f"expected={expected_ranking_stages}"
        )
    recommendation = sweep.get("recommendation")
    if not isinstance(recommendation, dict) or recommendation.get(
        "ranking_stage_indices"
    ) != expected_ranking_stages:
        raise RuntimeError("camera pose recommendation used the wrong ranking stages")
    _validate_candidate_videos(output_dir, sweep, expected_ranking_stages)
    scheme_c = None
    if camera_config in SCHEME_C_CONFIGS:
        expected_ablation_id, expected_view_order = SCHEME_C_CONFIGS[camera_config]
        scheme_c = metrics.get("a2_camera_scheme_c")
        if not isinstance(scheme_c, dict) or scheme_c.get("status") != "SCHEME_C_COMPLETE":
            raise RuntimeError("metrics_eval.json has no completed scheme C summary")
        if scheme_c.get("training_performed") is not False:
            raise RuntimeError("scheme C must explicitly report training_performed=false")
        if scheme_c.get("ablation_id") != expected_ablation_id:
            raise RuntimeError(
                "scheme C ablation identity drifted; "
                f"expected={expected_ablation_id!r}, "
                f"got={scheme_c.get('ablation_id')!r}"
            )
        if scheme_c.get("view_order") != expected_view_order:
            raise RuntimeError("scheme C view order drifted")
        expected_head_extrinsic = SCHEME_C_HEAD_EXTRINSIC_STATUS[camera_config]
        if scheme_c.get("head_extrinsic_status") != expected_head_extrinsic:
            raise RuntimeError("scheme C A2 Head extrinsic boundary drifted")
        if scheme_c.get("physics_advanced_between_views") is not False:
            raise RuntimeError("scheme C must prove no physics advance between views")
        intrinsic_error = scheme_c.get("runtime_intrinsic_max_error_px")
        if (
            isinstance(intrinsic_error, bool)
            or not isinstance(intrinsic_error, (int, float))
            or float(intrinsic_error) > 1.0e-4
        ):
            raise RuntimeError(
                f"scheme C runtime intrinsic error is invalid: {intrinsic_error!r}"
            )
        combined_visibility = scheme_c.get("combined_visibility")
        stages = (
            None
            if not isinstance(combined_visibility, dict)
            else combined_visibility.get("stages")
        )
        required_stage_names = tuple(
            f"stage{index}_{suffix}"
            for index, suffix in (
                (1, "pregrasp"),
                (2, "grasp"),
                (3, "open"),
                (4, "swing"),
                (5, "through"),
            )
        )
        if not isinstance(stages, dict) or any(
            not isinstance(stages.get(stage_name), dict)
            or int(stages[stage_name].get("sampled_frames", 0)) < 1
            for stage_name in required_stage_names
        ):
            raise RuntimeError(
                f"scheme C combined visibility does not cover stages 1-5: {stages}"
            )
        combined_metadata = scheme_c.get("combined_video_metadata")
        if (
            not isinstance(combined_metadata, dict)
            or int(combined_metadata.get("frame_count", 0)) < 1
        ):
            raise RuntimeError("scheme C combined video has no frames")
        stage_frame_counts = combined_metadata.get("stage_frame_counts")
        if not isinstance(stage_frame_counts, dict) or any(
            int(stage_frame_counts.get(stage_name, 0)) < 1
            for stage_name in required_stage_names
        ):
            raise RuntimeError(
                "scheme C combined video trajectory does not cover stages 1-5"
            )
        combined_path = Path(str(scheme_c.get("combined_video", ""))).resolve()
        if not combined_path.is_relative_to(output_dir):
            raise RuntimeError(f"scheme C combined video escaped eval output: {combined_path}")
        if not combined_path.is_file() or combined_path.stat().st_size <= 0:
            raise RuntimeError(f"scheme C combined video is missing or empty: {combined_path}")
        if camera_config == "d435i_dual_portrait_up60_a2_head_oem":
            panorama = scheme_c.get("panorama")
            if (
                not isinstance(panorama, dict)
                or panorama.get("projection") != "cylindrical_depth_aware"
                or panorama.get("stitch_mode") != "z_buffer_no_rgb_averaging"
                or panorama.get("invalid_depth_fallback")
                != "best_single_view_fixed_geometry"
                or panorama.get("output_resolution") != [384, 416]
            ):
                raise RuntimeError("C-B2 panorama contract is missing or drifted")
            panorama_metadata = scheme_c.get("panorama_video_metadata")
            if (
                not isinstance(panorama_metadata, dict)
                or panorama_metadata.get("frame_count")
                != combined_metadata.get("frame_count")
                or panorama_metadata.get("pair_frame_delta_max") != 0
            ):
                raise RuntimeError("C-B2 panorama frame synchronization gate failed")
            pixel_totals = panorama_metadata.get("pixel_totals")
            if (
                not isinstance(pixel_totals, dict)
                or int(pixel_totals.get("valid_input_depth_pixels", 0)) < 1
                or int(pixel_totals.get("depth_fused_output_pixels", 0)) < 1
            ):
                raise RuntimeError("C-B2 panorama did not consume and fuse valid depth")
            panorama_path = Path(
                str(scheme_c.get("panorama_video", ""))
            ).resolve()
            if not panorama_path.is_relative_to(output_dir):
                raise RuntimeError(
                    f"C-B2 panorama video escaped eval output: {panorama_path}"
                )
            if (
                not panorama_path.is_file()
                or panorama_path.stat().st_size <= 0
            ):
                raise RuntimeError(
                    f"C-B2 panorama video is missing or empty: {panorama_path}"
                )
        writing_files = list(output_dir.rglob("*.writing.mp4"))
        if writing_files:
            raise RuntimeError(f"unsealed scheme C video files remain: {writing_files}")
    elif camera_config != "gemini_335l_centerline":
        raise RuntimeError(f"unsupported camera config at seal time: {camera_config}")
    if sha256_file(runtime_checkpoint) != profile.checkpoint_sha256:
        raise RuntimeError("runtime checkpoint SHA-256 differs from sealed source")
    if sha256_file(runtime_config) != profile.config_sha256:
        raise RuntimeError("runtime config SHA-256 differs from sealed source")
    summary = {
        "schema_version": 3,
        "sealed_at_hkt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "SWEEP_COMPLETE",
        "training_performed": False,
        "teacher_profile": profile.name,
        "camera_config": camera_config,
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": artifact_identity["checkpoint_sha256"],
        "checkpoint_config": artifact_identity["config_path"],
        "checkpoint_config_sha256": artifact_identity["config_sha256"],
        "runtime_checkpoint": str(runtime_checkpoint),
        "runtime_checkpoint_sha256": sha256_file(runtime_checkpoint),
        "runtime_config": str(runtime_config),
        "runtime_config_sha256": sha256_file(runtime_config),
        "runtime_repository": str(profile.runtime_repository.resolve()),
        "runtime_commit": runtime_commit,
        "overlay_repository": str(REPOSITORY_ROOT),
        "command": command,
        "sweep": sweep,
    }
    if camera_config == "gemini_335l_centerline":
        summary["spec_derived_intrinsics"] = nominal_gemini_335l_crop_intrinsics()
    else:
        summary["scheme_c"] = scheme_c
    serialized = json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n"
    summary_path = output_dir / "camera_pose_sweep_summary.json"
    if summary_path.exists():
        raise FileExistsError(f"refusing to overwrite sealed summary: {summary_path}")
    temporary_path = output_dir / "camera_pose_sweep_summary.json.tmp"
    with temporary_path.open("x", encoding="utf-8") as stream:
        stream.write(serialized)
        stream.flush()
        os.fsync(stream.fileno())
    temporary_path.replace(summary_path)
    return summary_path


def main() -> int:
    args = parse_args()
    profile = TEACHER_PROFILES[args.teacher]
    if args.runtime_repository is not None:
        profile = replace(
            profile,
            runtime_repository=args.runtime_repository.resolve(),
        )
    checkpoint = (
        profile.checkpoint.resolve()
        if args.checkpoint is None
        else (
            (REPOSITORY_ROOT / args.checkpoint).resolve()
            if not args.checkpoint.is_absolute()
            else args.checkpoint.resolve()
        )
    )
    output_dir = args.output_dir.resolve()
    python_path = args.python.resolve()
    artifact_identity = verify_teacher_artifacts(
        profile=profile,
        checkpoint=checkpoint,
    )
    runtime_commit = verify_runtime_repository(profile)
    if not python_path.is_file():
        raise FileNotFoundError(f"IsaacLab Python not found: {python_path}")
    if output_dir.exists():
        raise FileExistsError(f"refusing to reuse camera sweep output directory: {output_dir}")
    runtime_checkpoint = output_dir / "_eval_input" / checkpoint.name
    command = build_eval_command(
        python_path=python_path,
        checkpoint=runtime_checkpoint,
        num_envs=args.num_envs,
        output_dir=output_dir,
        runtime_repository=profile.runtime_repository.resolve(),
        overlay_repository=REPOSITORY_ROOT,
        camera_config=args.camera_config,
    )
    if args.dry_run:
        print(
            json.dumps(
                {
                    "teacher_profile": profile.name,
                    "camera_config": args.camera_config,
                    "checkpoint_sha256": artifact_identity["checkpoint_sha256"],
                    "runtime_commit": runtime_commit,
                    "cuda_visible_devices": args.gpu,
                    "command": command,
                },
                indent=2,
            )
        )
        return 0

    environment = os.environ.copy()
    prepared_checkpoint, runtime_config = prepare_writable_eval_input(
        output_dir=output_dir,
        checkpoint=checkpoint,
        profile=profile,
    )
    if prepared_checkpoint != runtime_checkpoint:
        raise RuntimeError("prepared eval checkpoint path mismatch")
    environment["CUDA_VISIBLE_DEVICES"] = str(args.gpu)
    environment["HYDRA_FULL_ERROR"] = "1"
    environment["PYTHONUNBUFFERED"] = "1"
    existing_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = str(profile.runtime_repository.resolve())
    if existing_pythonpath:
        environment["PYTHONPATH"] += os.pathsep + existing_pythonpath
    completed = subprocess.run(command, cwd=REPOSITORY_ROOT, env=environment, check=False)
    if completed.returncode != 0:
        raise RuntimeError(
            f"camera pose sweep eval failed with exit code {completed.returncode}; "
            f"partial output remains at {output_dir}"
        )
    if verify_runtime_repository(profile) != runtime_commit:
        raise RuntimeError("Teacher runtime repository changed during camera pose eval")
    metrics_path = output_dir / "metrics_eval.json"
    if not metrics_path.is_file():
        raise FileNotFoundError(f"camera pose sweep did not produce {metrics_path}")
    with metrics_path.open("r", encoding="utf-8") as stream:
        metrics = json.load(stream)
    summary_path = seal_summary(
        output_dir=output_dir,
        command=command,
        profile=profile,
        checkpoint=checkpoint,
        artifact_identity=artifact_identity,
        runtime_checkpoint=runtime_checkpoint,
        runtime_config=runtime_config,
        runtime_commit=runtime_commit,
        metrics=metrics,
        camera_config=args.camera_config,
    )
    print(f"[CAMERA_POSE_SWEEP_SEALED] {summary_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
