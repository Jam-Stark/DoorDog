#!/usr/bin/env python3
"""Prepare/run the Pull-v5.4 dual-source evaluation for one checkpoint."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

try:
    from .pull_v5_4_gates import DEFAULT_DECISION, DEFAULT_REHEARSAL, DEFAULT_STAGE_A, require_chain, require_v5_4_downstream_gate
except ImportError:
    from pull_v5_4_gates import DEFAULT_DECISION, DEFAULT_REHEARSAL, DEFAULT_STAGE_A, require_chain, require_v5_4_downstream_gate


ROOT = Path(__file__).resolve().parents[2]
PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
EVAL_ROOT = ROOT / "logs_eval/a2_piper_pull_v5"
ALLOWED_GPUS = (4, 5, 6, 7)
SOURCES = ("canonical", "natural")
VERSIONS = ("5.4",)
INVARIANTS = (
    "fake_e4",
    "stage4_snapshot_below_hinge_gate",
    "dont_push_before_true_stage3_to4",
    "target_root_before_aperture_ready",
    "corridor_active_before_aperture_ready",
    "complete_without_frame_passage",
    "frame_approach_active_before_aperture_ready",
    "frame_approach_active_after_frame_passage",
    "canonical_not_counted_as_natural_start",
    "failed_settle_not_in_bank",
    "override_active_outside_canonical_start",
)


def _version_tag(version: str) -> str:
    if version not in VERSIONS:
        raise ValueError(f"unsupported Pull version: {version!r}")
    return f"v{version.replace('.', '_')}"


def _canonical_reset_sources() -> tuple[str, ...]:
    return ("bank_natural_e5", "bank_natural_e5_plus", "bank_constructed", "bank_natural_e5_override")


def _nested_value(row: dict[str, object], *paths: tuple[str, ...]) -> object:
    for path in paths:
        value: object = row
        for key in path:
            if not isinstance(value, dict) or key not in value:
                value = None
                break
            value = value[key]
        if value is not None:
            return value
    return None


def _required_bool(value: object, *, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"terminal producer field {name} must be bool; got {value!r}")
    return value


def _required_float(value: object, *, name: str) -> float:
    import math

    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"terminal producer field {name} must be finite numeric; got {value!r}")
    return float(value)


def _required_int(value: object, *, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"terminal producer field {name} must be a non-negative int; got {value!r}")
    return value


def _event_map(row: dict[str, object]) -> dict[str, bool]:
    value = _nested_value(row, ("pull_v0_episode", "event_reached"), ("event_reached",))
    if not isinstance(value, dict):
        raise ValueError("terminal producer row is missing pull_v0_episode.event_reached")
    result: dict[str, bool] = {}
    for name in ("E6_PATH_REVERSAL_ENTRY", "E7_WHOLE_BODY_CLEAR"):
        result[name] = _required_bool(value.get(name), name=name)
    return result


def _normalize_terminal_rows(
    metrics: dict[str, object], *, cell: str, checkpoint: Path, source: str, version: str,
) -> list[dict[str, object]]:
    raw = metrics.get("episode_terminal_diagnostics")
    if not isinstance(raw, list) or len(raw) != 16 or not all(isinstance(row, dict) for row in raw):
        raise ValueError("Pull evaluator requires exactly 16 explicit terminal diagnostics")
    expected_source = _canonical_reset_sources() if source == "canonical" else ("natural",)
    normalized: list[dict[str, object]] = []
    seen_env_ids: set[int] = set()
    for row in raw:
        env_id = row.get("env_id")
        if isinstance(env_id, bool) or not isinstance(env_id, int) or env_id < 0 or env_id in seen_env_ids:
            raise ValueError(f"terminal producer env_id must be unique non-negative int; got {env_id!r}")
        seen_env_ids.add(env_id)
        for flag in ("terminal", "is_terminal"):
            if flag in row and row[flag] is not True:
                raise ValueError(f"terminal producer row {env_id} is nonterminal")
        source_provenance = _nested_value(row, ("pull_v5", "reset_source"), ("reset_source",))
        if source == "canonical":
            if source_provenance not in expected_source:
                raise ValueError(f"canonical evaluator row {env_id} has invalid reset_source {source_provenance!r}")
        elif source_provenance not in expected_source:
            raise ValueError(f"natural evaluator row {env_id} has reset_source {source_provenance!r}")
        source_provenance = str(source_provenance)
        declared_provenance = _nested_value(
            row,
            ("pull_v5", "declared_reset_source"),
            ("declared_reset_source",),
        )
        if not isinstance(declared_provenance, str) or not declared_provenance:
            raise ValueError(f"terminal producer row {env_id} is missing declared_reset_source")
        declared_group = "bank" if declared_provenance.startswith("bank_") else "natural"
        expected_group = "bank" if source == "canonical" else "natural"
        if declared_group != expected_group:
            raise ValueError(
                f"{source} evaluator row {env_id} declares {declared_provenance!r}, "
                f"expected {expected_group} provider"
            )
        actual_group = "bank" if source_provenance.startswith("bank_") else "natural"
        if actual_group != declared_group:
            raise ValueError(
                f"terminal producer row {env_id} mixes declared={declared_provenance!r} "
                f"with actual={source_provenance!r} provenance"
            )
        dv_source = "canonical_bank" if source_provenance.startswith("bank_") else "natural"
        traversal = row.get("pull_v3_traversal")
        if not isinstance(traversal, dict):
            raise ValueError(f"terminal producer row {env_id} is missing pull_v3_traversal")
        events = _event_map(row)
        frame_passage = _required_bool(traversal.get("frame_passage"), name="pull_v3_traversal.frame_passage")
        persistent_release = _required_bool(
            _nested_value(row, ("pull_v5", "persistent_release"), ("persistent_release",)),
            name="pull_v5.persistent_release",
        )
        settle_valid = _required_bool(
            _nested_value(row, ("pull_v5", "settle_valid"), ("settle_valid",)),
            name="pull_v5.settle_valid",
        )
        bank_settle_value = _nested_value(
            row, ("pull_v5", "bank_settle_valid"), ("bank_settle_valid",)
        )
        if source == "canonical":
            bank_settle_valid = _required_bool(
                bank_settle_value, name="pull_v5.bank_settle_valid"
            )
            if not bank_settle_valid:
                raise ValueError(f"canonical evaluator row {env_id} failed bank settle validation")
        elif bank_settle_value is not None:
            raise ValueError(
                f"natural evaluator row {env_id} must not carry bank_settle_valid; "
                f"got {bank_settle_value!r}"
            )
        else:
            bank_settle_valid = None
        invariants_value = _nested_value(row, ("pull_v5", "invariants"), ("invariants",))
        if not isinstance(invariants_value, dict):
            raise ValueError(f"terminal producer row {env_id} is missing the eleven pull_v5 invariants")
        invariants = {
            name: _required_bool(invariants_value.get(name), name=f"invariants.{name}")
            for name in INVARIANTS
        }
        pull_v5 = row.get("pull_v5")
        if not isinstance(pull_v5, dict):
            raise ValueError(f"terminal producer row {env_id} is missing pull_v5 telemetry")
        start_override_active = _required_bool(
            pull_v5.get("start_override_active"), name="pull_v5.start_override_active"
        )
        start_override_steps = _required_int(
            pull_v5.get("start_override_active_steps"), name="pull_v5.start_override_active_steps"
        )
        start_override_base_equal = _required_bool(
            pull_v5.get("start_override_base_slice_equal"), name="pull_v5.start_override_base_slice_equal"
        )
        if source == "canonical" and not start_override_active:
            raise ValueError(f"canonical evaluator row {env_id} did not activate the start override")
        if source == "natural" and start_override_active:
            raise ValueError(f"natural evaluator row {env_id} activated the start override")
        passage_attempt_hinge = pull_v5.get("passage_attempt_hinge_rad")
        if frame_passage:
            passage_attempt_hinge = _required_float(
                passage_attempt_hinge, name="pull_v5.passage_attempt_hinge_rad"
            )
        elif passage_attempt_hinge is not None:
            raise ValueError(
                f"terminal producer row {env_id} has non-null passage_attempt_hinge_rad without frame passage"
            )
        panel = row.get("pull_v0_episode")
        if not isinstance(panel, dict):
            raise ValueError(f"terminal producer row {env_id} is missing pull_v0_episode telemetry")
        panel_contact_steps = _required_int(
            panel.get("body_panel_contact_steps_per_20s"),
            name="pull_v0_episode.body_panel_contact_steps_per_20s",
        )
        post_release_recontact_count = _required_int(
            traversal.get("post_release_recontact_count"),
            name="pull_v3_traversal.post_release_recontact_count",
        )
        frame_midpoint_distance = _required_float(
            traversal.get("frame_midpoint_distance_min_m"),
            name="pull_v3_traversal.frame_midpoint_distance_min_m",
        )
        door_hinge_joint_pos = _required_float(
            row.get("door_hinge_joint_pos"), name="door_hinge_joint_pos"
        )
        normalized.append(
            {
                "schema": f"a2_piper_pull_v{version.replace('.', '_')}_terminal_record_v1",
                "run_id": f"pull_v{version.replace('.', '_')}_{cell}_step{checkpoint.stem.rsplit('_', 1)[-1]}_{source}",
                "cell": cell,
                "checkpoint": str(checkpoint),
                "episode_id": env_id,
                "env_id": env_id,
                "source": "canonical_bank" if dv_source == "canonical_bank" else "natural",
                "source_provenance": source_provenance,
                "declared_reset_source": declared_provenance,
                "reset_source": source_provenance,
                "dv_source": dv_source,
                "frame_passage": frame_passage,
                "persistent_release": persistent_release,
                "complete": events["E7_WHOLE_BODY_CLEAR"],
                "E6_PATH_REVERSAL_ENTRY": events["E6_PATH_REVERSAL_ENTRY"],
                "E7_WHOLE_BODY_CLEAR": events["E7_WHOLE_BODY_CLEAR"],
                "settle_valid": settle_valid,
                "bank_settle_valid": bank_settle_valid,
                "start_override_active": start_override_active,
                "start_override_active_steps": start_override_steps,
                "start_override_base_slice_equal": start_override_base_equal,
                "passage_attempt_hinge_rad": passage_attempt_hinge,
                "door_hinge_joint_pos": door_hinge_joint_pos,
                "panel_contact_steps_per_20s": panel_contact_steps,
                "post_release_recontact_count": post_release_recontact_count,
                "frame_midpoint_distance_min_m": frame_midpoint_distance,
                "hinge_drive_max_force_nm": _required_float(
                    _nested_value(
                        row,
                        ("pull_v5", "hinge_drive_max_force_nm"),
                        ("hinge_drive_max_force_nm",),
                        ("door_scenario", "hinge_max_force_nm"),
                        ("pull_v0_episode", "hinge_drive_max_force_nm"),
                    ),
                    name="hinge_drive_max_force_nm",
                ),
                "invariants": invariants,
            }
        )
    return normalized


def build_command(
    *, checkpoint: Path, cell: str, step: int, source: str, gpu: int,
    output_dir: Path, version: str = "5.4", allow_missing_checkpoint: bool = False,
    allow_g8_pure_a: bool = False, decision_path: Path = DEFAULT_DECISION,
    stage_a_path: Path = DEFAULT_STAGE_A, rehearsal_path: Path = DEFAULT_REHEARSAL,
    anchor_receipt: Path, gate_receipt: Path,
) -> tuple[list[str], dict[str, str]]:
    require_chain("anchor", decision_path=decision_path, stage_a_path=stage_a_path, rehearsal_path=rehearsal_path, anchor_path=anchor_receipt)
    require_v5_4_downstream_gate(gate_receipt, anchor_path=anchor_receipt)
    if source not in SOURCES:
        raise ValueError(f"unknown evaluation source: {source!r}")
    if gpu not in ALLOWED_GPUS:
        raise ValueError(f"Pull eval only permits physical GPU4-7; got GPU{gpu}")
    tag = _version_tag(version)
    if step % 50 != 0 or step < 50 or step > 250:
        raise ValueError("Pull-v5.4 eval checkpoints are the saved 50-step cells through step250")
    if not checkpoint.is_file() and not allow_missing_checkpoint:
        raise FileNotFoundError(checkpoint)
    if output_dir.parent.resolve() != EVAL_ROOT.resolve():
        raise ValueError(f"Pull-v5.4 eval output must be directly under {EVAL_ROOT}")
    reset_source = "bank_natural_e5" if source == "canonical" else "natural"
    command = [
        str(PYTHON), "-B", "-m", "gr00t.rl.eval_agent_trl",
        f"checkpoint={checkpoint}", "checkpoint_load_mode=policy_only", "auto_load_latest=false",
        "num_envs=16", "seed=0", "headless=true", "use_wandb=false",
        "+ablation=wbmanip/pull_v5_M_s0", "algo.config.load_optimizer=false",
        "+algo.config.eval.eval_num_envs_episodes=true", "algo.config.eval.num_eval_episodes=1",
        "+algo.config.eval.dump_to_log_metrics=true", "algo.config.eval.save_goal_reached_only=false",
        "algo.config.eval.save_trajectories=true", "algo.config.eval.save_videos=false",
        "algo.config.eval.num_save_episodes=16", "algo.config.eval.a2_diagnostic_trace_enabled=true",
        "env.config.a2_pull_v5_stage4_bank_injection_enabled=false",
        "env.config.a2_pull_v5_stage4_bank_injection_ratio=0.0",
        f"env.config.a2_pull_v5_reset_source={reset_source}",
        "env.config.a2_pull_v5_start_override_enabled=true",
        "env.config.a2_pull_v5_start_override_steps=50",
        "env.config.a2_pull_v5_release_streak_steps=25",
        "env.config.a2_pull_v5_intervention_enabled=false",
        "env.config.a2_pull_v5_snapshot_freeze_enabled=true",
        "env.config.a2_pull_v5_reset_source_telemetry_enabled=true",
        "env.config.a2_pull_v5_state_bank_min_samples=64",
        f"env.config.a2_pull_v5_state_bank_allow_g8_pure_a={'true' if allow_g8_pure_a else 'false'}",
        "env.config.a2_pull_v5_state_bank_path=logs_rl/a2_piper_full_stage_a2_pull/pull_v5_state_bank/pull_v5_state_bank.pt",
        f"env.config.a2_pull_v5_load_receipt_path=logs_rl/a2_piper_full_stage_a2_pull/pull_v5_load_receipts/pull_{tag}_eval_{cell}_step{step}_{source}.json",
        f"eval_output_dir={output_dir / 'eval'}", f"hydra.run.dir={output_dir / 'hydra'}",
        f"env.config.save_rendering_dir={output_dir / 'renderings'}", "+device=cuda:0",
        f"+main_process_port={30100 + gpu * 100 + step * 2 + (0 if source == 'canonical' else 1)}",
    ]
    if source == "canonical":
        command.extend((
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--cell", required=True)
    parser.add_argument("--step", type=int, required=True)
    parser.add_argument("--gpu", type=int, choices=ALLOWED_GPUS, required=True)
    parser.add_argument("--version", choices=VERSIONS, default="5.4")
    parser.add_argument("--output-root", type=Path, default=EVAL_ROOT)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--decision", type=Path, default=DEFAULT_DECISION)
    parser.add_argument("--stage-a", type=Path, default=DEFAULT_STAGE_A)
    parser.add_argument("--rehearsal", type=Path, default=DEFAULT_REHEARSAL)
    parser.add_argument("--anchor-receipt", type=Path, required=True)
    parser.add_argument("--gate-receipt", type=Path, required=True)
    parser.add_argument("--allow-g8-pure-a", action="store_true")
    args = parser.parse_args()
    checkpoint = args.checkpoint.resolve()
    tag = _version_tag(args.version)
    for source in SOURCES:
        output_dir = (args.output_root / f"{tag}_{args.cell}_step{args.step}_{source}").resolve()
        command, process_env = build_command(
            checkpoint=checkpoint, cell=args.cell, step=args.step, source=source,
            gpu=args.gpu, output_dir=output_dir, version=args.version,
            allow_missing_checkpoint=args.dry_run,
            allow_g8_pure_a=args.allow_g8_pure_a,
            decision_path=args.decision, stage_a_path=args.stage_a,
            rehearsal_path=args.rehearsal, anchor_receipt=args.anchor_receipt, gate_receipt=args.gate_receipt,
        )
        print(f"[pull-{args.version} eval {source}] command:", " ".join(command))
        print(f"[pull-{args.version} eval {source}] environment:", process_env)
        if not args.run:
            continue
        if output_dir.exists():
            raise FileExistsError(f"refusing to overwrite Pull-v5.4 eval output: {output_dir}")
        output_dir.mkdir(parents=True, exist_ok=False)
        run_env = os.environ.copy(); run_env.update(process_env)
        with (output_dir / "runner.log").open("x", encoding="utf-8") as stream:
            result = subprocess.run(command, cwd=ROOT, env=run_env, stdout=stream, stderr=subprocess.STDOUT, check=False)
        if result.returncode != 0:
            return result.returncode
        metrics_path = output_dir / "eval" / "metrics_eval.json"
        if not metrics_path.is_file():
            raise RuntimeError(f"Pull-v5.4 eval exited without terminal metrics: {metrics_path}")
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        if not isinstance(metrics, dict):
            raise ValueError("Pull-v5.4 evaluator metrics must be a mapping")
        terminal = _normalize_terminal_rows(
            metrics, cell=args.cell, checkpoint=checkpoint, source=source, version=args.version,
        )
        terminal_path = output_dir / "terminal_records.json"
        terminal_path.write_text(json.dumps(terminal, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        receipt = {
            "schema": f"a2_piper_pull_v{args.version.replace('.', '_')}_eval_receipt_v1",
            "status": "PASS",
            "cell": args.cell,
            "checkpoint": str(checkpoint),
            "step": args.step,
            "source": "canonical" if source == "canonical" else "natural",
            "reset_source_group": "canonical" if source == "canonical" else "natural",
            "terminal_records": len(terminal),
            "output_dir": str(output_dir),
            "injection_enabled": False,
            "eval_reset_provider": "bank" if source == "canonical" else "stage0",
            "start_override_enabled": True,
            "start_override_steps": 50,
            "load_optimizer": False,
            "load_receipt_path": str((ROOT / f"logs_rl/a2_piper_full_stage_a2_pull/pull_v5_load_receipts/pull_{tag}_eval_{args.cell}_step{args.step}_{source}.json").resolve()),
            "terminal_records_path": str(terminal_path.resolve()),
            "reset_sources": sorted({row["reset_source"] for row in terminal}),
            "reset_source_contract": {
                "canonical": list(_canonical_reset_sources()),
                "natural": ["natural"],
                "training_injection_enabled": False,
            },
            "plan_id": "a2_piper_pull_v5_4_terminal_yaw_scheduler",
            "scientific_denominator_included": True,
            "denominator_scope": "dual_source_terminal_eval",
            "anchor_receipt_path": str(args.anchor_receipt.resolve()),
        }
        (output_dir / "eval_receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
