#!/usr/bin/env python3
"""Render selected Pull-v5.3 episodes with the project eval camera lifecycle.

Rendering is an evidence-only producer.  It reads a completed anchor, door
probe, or dual-source evaluation receipt, replays exactly one explicitly
selected episode on one visible physical GPU, and writes an index whose rows
are excluded from every scientific denominator.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

try:
    from .write_pull_v5_3_p0_adjudication import require_p0_adjudication
except ImportError:
    from write_pull_v5_3_p0_adjudication import require_p0_adjudication


ROOT = Path(__file__).resolve().parents[2]
PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
RENDER_ROOT = ROOT / "logs_eval/a2_piper_pull_v5/render_v5_3"
ALLOWED_GPUS = (4, 5, 6, 7)
FIXTURES = ("anchor", "door", "final_eval")
SOURCES = ("canonical", "natural")
CLOSER_BUCKETS = ("2.5-5", "5-9", "9-12")
SEQUENCES = ("S1", "S2", "S3", "S4")


def _require_file(path: Path, label: str) -> Path:
    path = path.expanduser().resolve()
    if not path.is_file() or path.is_symlink():
        raise FileNotFoundError(f"{label} must be a regular file: {path}")
    return path


def _inside(path: Path, parent: Path, label: str) -> Path:
    path = path.expanduser().resolve()
    if not path.is_relative_to(parent.resolve()):
        raise ValueError(f"{label} must remain under {parent}: {path}")
    return path


def _read_receipt(path: Path) -> dict[str, object]:
    path = _require_file(path, "render receipt")
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError(f"render receipt must be a mapping: {path}")
    schema = document.get("schema")
    if not isinstance(schema, str) or not schema.startswith("a2_piper_pull_v5_3_"):
        raise ValueError(f"render receipt is not a v5.3 receipt: {path}")
    return document


def _reset_source(source: str) -> str:
    if source == "natural":
        return "natural"
    if source == "canonical":
        return "bank_natural_e5"
    raise ValueError(f"unknown render source: {source!r}")


def _validate_selection(
    *, receipt: dict[str, object], fixture: str, source: str, episode_id: int,
    sequence: str | None, closer_bucket: str | None, selection: str,
) -> dict[str, object]:
    if fixture not in FIXTURES:
        raise ValueError(f"unknown render fixture: {fixture!r}")
    if source not in SOURCES:
        raise ValueError(f"unknown render source: {source!r}")
    if episode_id < 0:
        raise ValueError("render episode_id must be non-negative")
    receipt_fixture = receipt.get("fixture")
    receipt_source = receipt.get("source")
    if fixture in {"anchor", "door"} and receipt_fixture != fixture:
        raise ValueError(
            f"receipt fixture {receipt_fixture!r} does not match requested {fixture!r}"
        )
    if fixture == "final_eval" and receipt_fixture not in (None, "final_eval"):
        raise ValueError(f"final-eval render received incompatible fixture {receipt_fixture!r}")
    if fixture == "anchor" and source != "natural":
        raise ValueError("anchor render must use natural open-field source")
    if fixture in {"door", "final_eval"} and source == "canonical":
        expected_sources = {"canonical", "bank_natural_e5", "bank_natural_e5_plus", "bank_natural_e5_override"}
        reset_sources = receipt.get("reset_sources")
        if isinstance(reset_sources, list) and reset_sources and not set(reset_sources).intersection(expected_sources):
            raise ValueError("canonical render receipt has no canonical reset provenance")
    anchor_verdict: str | None = None
    if fixture == "door":
        if source != "canonical":
            raise ValueError("door render requires canonical bank source")
        if sequence not in SEQUENCES:
            raise ValueError("door render requires one of S1..S4")
        if closer_bucket not in CLOSER_BUCKETS:
            raise ValueError("door render requires a closer bucket")
        bucket_rows = receipt.get("bucket_sequence_records")
        if not isinstance(bucket_rows, dict):
            raise ValueError("door receipt is missing bucket_sequence_records")
        bucket_record = bucket_rows.get(closer_bucket)
        if not isinstance(bucket_record, dict):
            raise ValueError(f"door receipt has no closer bucket {closer_bucket!r}")
        sequence_record = bucket_record.get(sequence)
        if not isinstance(sequence_record, dict) or sequence_record.get("episodes", 0) <= 0:
            raise ValueError(f"door receipt has no terminal rows for {closer_bucket}×{sequence}")
    elif fixture == "anchor":
        if sequence not in SEQUENCES:
            raise ValueError("anchor render requires one of S1..S4")
        sequence_results = receipt.get("sequence_results")
        if not isinstance(sequence_results, dict) or not isinstance(sequence_results.get(sequence), dict):
            raise ValueError(f"anchor receipt has no sequence result for {sequence!r}")
        sequence_result = sequence_results[sequence]
        sequence_pass = sequence_result.get("sequence_pass")
        if not isinstance(sequence_pass, bool):
            raise ValueError(f"anchor receipt sequence {sequence!r} has no boolean verdict")
        anchor_verdict = "PASS" if sequence_pass else "FAIL"
        if selection == "pass" and not sequence_pass:
            raise ValueError(f"requested anchor PASS but {sequence} is FAIL")
        if selection == "fail" and sequence_pass:
            raise ValueError(f"requested anchor FAIL but {sequence} is PASS")
    else:
        if source != receipt_source and receipt_source in SOURCES:
            raise ValueError(f"final-eval receipt source {receipt_source!r} disagrees with {source!r}")
        terminal_records_path = receipt.get("terminal_records_path")
        if not isinstance(terminal_records_path, str):
            raise ValueError("final-eval receipt must bind terminal_records_path")
        terminal_path = _require_file(Path(terminal_records_path), "final-eval terminal records")
        terminal = json.loads(terminal_path.read_text(encoding="utf-8"))
        if not isinstance(terminal, list):
            raise ValueError("final-eval terminal records must be a list")
        selected = [row for row in terminal if isinstance(row, dict) and row.get("episode_id") == episode_id]
        if len(selected) != 1:
            raise ValueError(f"final-eval receipt must contain exactly one selected episode_id={episode_id}")
        selected_source = selected[0].get("source")
        expected_source = "canonical_bank" if source == "canonical" else "natural"
        if selected_source != expected_source:
            raise ValueError(f"final-eval selected row source {selected_source!r} != {expected_source!r}")
    return {
        "receipt_schema": receipt["schema"],
        "receipt_fixture": receipt_fixture or "final_eval",
        "source": source,
        "reset_source": _reset_source(source),
        "episode_id": episode_id,
        "sequence": sequence,
        "closer_bucket": closer_bucket,
        "selection": selection,
        "anchor_verdict": anchor_verdict,
        "scientific_denominator_included": False,
        "record_class": "render_only",
    }


def build_render_command(
    *, checkpoint: Path, gpu: int, fixture: str, source: str, output_dir: Path,
    episode_id: int, sequence: str | None, closer_bucket: str | None,
    p0_adjudication: Path,
) -> tuple[list[str], dict[str, str]]:
    require_p0_adjudication(p0_adjudication)
    if gpu not in ALLOWED_GPUS:
        raise ValueError(f"render only permits physical GPU4-7; got GPU{gpu}")
    checkpoint = _require_file(checkpoint, "render checkpoint")
    output_dir = _inside(output_dir, RENDER_ROOT, "render output")
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite render output: {output_dir}")
    if fixture not in FIXTURES or source not in SOURCES:
        raise ValueError(f"unsupported fixture/source: {fixture!r}/{source!r}")
    reset_source = _reset_source(source)
    command = [
        str(PYTHON), "-B", "-m", "gr00t.rl.eval_agent_trl",
        f"checkpoint={checkpoint}", "checkpoint_load_mode=policy_only", "auto_load_latest=false",
        "num_envs=1", f"seed={episode_id}", "headless=true", "use_wandb=false",
        "+ablation=wbmanip/pull_v5_M_s0", "algo.config.load_optimizer=false",
        "+algo.config.eval.eval_num_envs_episodes=true", "algo.config.eval.num_eval_episodes=1",
        "+algo.config.eval.dump_to_log_metrics=true", "algo.config.eval.save_videos=false",
        "algo.config.eval.save_trajectories=false", "algo.config.eval.num_save_episodes=1",
        "algo.config.eval.a2_diagnostic_trace_enabled=true",
        "env.config.a2_pull_v5_stage4_bank_injection_enabled=false",
        "env.config.a2_pull_v5_stage4_bank_injection_ratio=0.0",
        f"env.config.a2_pull_v5_reset_source={reset_source}",
        "env.config.a2_pull_v5_release_streak_steps=25",
        "env.config.a2_pull_v5_intervention_enabled=false",
        "env.config.a2_pull_v5_snapshot_freeze_enabled=true",
        "env.config.a2_pull_v5_reset_source_telemetry_enabled=true",
        "env.config.a2_pull_v5_start_override_enabled=false",
        "env.config.a2_pull_v5_start_override_steps=50",
        "env.config.a2_pull_v5_state_bank_min_samples=64",
        "env.config.a2_pull_v5_state_bank_allow_g8_pure_a=true",
        "env.config.a2_pull_v5_state_bank_path=logs_rl/a2_piper_full_stage_a2_pull/pull_v5_state_bank/pull_v5_state_bank.pt",
        f"env.config.a2_pull_v5_load_receipt_path=logs_rl/a2_piper_full_stage_a2_pull/pull_v5_load_receipts/pull_v5_3_render_{output_dir.name}.json",
        f"+env.config.a2_pull_v5_render_episode_id={episode_id}",
        "simulator.config.render_results=true", "simulator.config.cameras.enable_cameras=true",
        f"eval_output_dir={output_dir / 'eval'}", f"hydra.run.dir={output_dir / 'hydra'}",
        f"env.config.save_rendering_dir={output_dir / 'videos'}", "+device=cuda:0",
        "+main_process_port=30640",
    ]
    if fixture in {"anchor", "door"}:
        if sequence not in SEQUENCES:
            raise ValueError(f"{fixture} render requires one of S1..S4")
        command.extend((
            "+env.config.a2_pull_v5_probe_enabled=true",
            f"+env.config.a2_pull_v5_probe_fixture={fixture}",
            f"+env.config.a2_pull_v5_probe_command={sequence}",
            f"+env.config.a2_pull_v5_probe_sequence={sequence}",
            "+env.config.a2_pull_v5_probe_correction_retry=0",
            f"+env.config.a2_pull_v5_probe_open_field={'true' if fixture == 'anchor' else 'false'}",
            "+env.config.a2_pull_v5_probe_waypoint_tolerance_m=0.05",
            "+env.config.a2_pull_v5_probe_yaw_tolerance_rad=0.15",
        ))
        if fixture == "door":
            command.extend((
                f"+env.config.a2_pull_v5_eval_closer_bucket={closer_bucket}",
                "+env.config.a2_pull_v5_eval_state_count=16",
                "+env.config.a2_pull_v5_eval_sequence_count=4",
                "+env.config.a2_pull_v5_eval_selection=deterministic_provenance_balanced",
                "+env.config.a2_pull_v5_eval_selection_seed=0",
            ))
    else:
        command.extend((
            "+env.config.a2_pull_v5_probe_enabled=false",
            "+env.config.a2_pull_v5_start_override_enabled=true",
            "+env.config.a2_pull_v5_eval_closer_bucket=all",
            "+env.config.a2_pull_v5_eval_state_count=16",
            "+env.config.a2_pull_v5_eval_selection=deterministic_provenance_balanced",
            "+env.config.a2_pull_v5_eval_selection_seed=0",
        ))
    return command, {
        "PYTHONPATH": str(ROOT), "CUDA_VISIBLE_DEVICES": str(gpu),
        "ACCELERATE_TORCH_DEVICE": "cuda:0", "HYDRA_FULL_ERROR": "1",
        "PYTHONUNBUFFERED": "1", "WANDB_MODE": "offline",
    }


def _write_index(output_dir: Path, metadata: dict[str, object], videos: list[Path], command: list[str]) -> Path:
    rows = []
    for video in videos:
        rows.append({
            **metadata,
            "video_path": str(video.resolve()),
            "output_dir": str(output_dir.resolve()),
            "command": command,
        })
    index = {
        "schema": "a2_piper_pull_v5_3_render_index_v1",
        "status": "PASS",
        "record_class": "render_only",
        "scientific_denominator_included": False,
        "rows": rows,
    }
    path = output_dir / "render_index.json"
    path.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--fixture", choices=FIXTURES, required=True)
    parser.add_argument("--source", choices=SOURCES, required=True)
    parser.add_argument("--episode-id", type=int, required=True)
    parser.add_argument("--sequence", choices=SEQUENCES)
    parser.add_argument("--closer-bucket", choices=CLOSER_BUCKETS)
    parser.add_argument("--selection", choices=("auto", "pass", "fail"), default="auto")
    parser.add_argument("--gpu", type=int, choices=ALLOWED_GPUS, default=4)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--p0-adjudication", type=Path, required=True)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    require_p0_adjudication(args.p0_adjudication)
    receipt = _read_receipt(args.receipt)
    metadata = _validate_selection(
        receipt=receipt, fixture=args.fixture, source=args.source, episode_id=args.episode_id,
        sequence=args.sequence, closer_bucket=args.closer_bucket, selection=args.selection,
    )
    suffix = f"{args.fixture}_{args.source}_ep{args.episode_id:04d}"
    if args.sequence is not None:
        suffix += f"_{args.sequence}"
    if args.closer_bucket is not None:
        suffix += f"_{args.closer_bucket.replace('-', '_')}"
    output_dir = (args.output_dir or RENDER_ROOT / suffix).resolve()
    command, process_env = build_render_command(
        checkpoint=args.checkpoint, gpu=args.gpu, fixture=args.fixture, source=args.source,
        output_dir=output_dir, episode_id=args.episode_id, sequence=args.sequence,
        closer_bucket=args.closer_bucket,
        p0_adjudication=args.p0_adjudication,
    )
    metadata["checkpoint"] = str(_require_file(args.checkpoint, "render checkpoint"))
    metadata["output_dir"] = str(output_dir)
    print("[pull-v5.3 render] command:", " ".join(command))
    print("[pull-v5.3 render] environment:", process_env)
    if not args.run:
        print(json.dumps({"schema": "a2_piper_pull_v5_3_render_plan_v1", **metadata, "command": command, "environment": process_env}, indent=2, sort_keys=True))
        return 0
    output_dir.mkdir(parents=True, exist_ok=False)
    run_env = os.environ.copy()
    run_env.update(process_env)
    with (output_dir / "runner.log").open("x", encoding="utf-8") as stream:
        result = subprocess.run(command, cwd=ROOT, env=run_env, stdout=stream, stderr=subprocess.STDOUT, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"render evaluator exited with {result.returncode}; inspect {output_dir / 'runner.log'}")
    videos = sorted(path for path in (output_dir / "videos").glob("*.mp4") if path.is_file() and not path.name.endswith(".writing"))
    if not videos:
        raise RuntimeError(f"render evaluator exited zero without MP4 output: {output_dir / 'videos'}")
    index_path = _write_index(output_dir, metadata, videos, command)
    print(json.dumps({"schema": "a2_piper_pull_v5_3_render_index_v1", "status": "PASS", "index": str(index_path), "videos": [str(path) for path in videos]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
