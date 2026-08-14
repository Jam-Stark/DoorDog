#!/usr/bin/env python3
"""Generate and execute the Pull-v5.1 S1→S7 dependency topology.

The phase graph is executable state, not a descriptive checklist.  Every
downstream phase names the receipts it consumes, commands are emitted with
stable output directories, and GPU work is represented as detached tmux-ready
launches.  Runtime execution is opt-in; command generation never starts Isaac
Sim.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent
PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
TRAIN_ROOT = ROOT / "logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull"
STATE_BANK_ROOT = ROOT / "logs_rl/a2_piper_full_stage_a2_pull/pull_v5_state_bank"
BANK = STATE_BANK_ROOT / "pull_v5_state_bank.pt"
BANK_RECEIPT = BANK.with_suffix(BANK.suffix + ".receipt.json")
EVAL_ROOT = ROOT / "logs_eval/a2_piper_pull_v5"
P2_ROOT = EVAL_ROOT / "p2_intervention_v5_1"
P2_RECEIPT = P2_ROOT / "P2_INTERVENTION_RECEIPT.json"
ANALYSIS = SCRIPT_DIR / "PULL_V5_1_ANALYSIS.json"
CELLS = (("M_s0", 4), ("M_s1", 5), ("C_s0", 6), ("C_s1", 7))
BUCKETS = ("2.5-5", "5-9", "9-12")
CHECKPOINT_STEPS = (50, 100, 150, 200, 250)
P1_ATTEMPTS = (1, 2, 3)
SOURCE_A_LEGACY = STATE_BANK_ROOT / "source_a_actor_e5_r5.pt"
SOURCE_A_LEGACY_METRICS = STATE_BANK_ROOT / "source_a_actor_e5_r5_eval/metrics_eval.json"
SOURCE_A_DEFAULT = STATE_BANK_ROOT / "source_a_actor_e5_v5_1.pt"
SOURCE_A_PLUS2_DEFAULT = STATE_BANK_ROOT / "source_a_actor_e5_plus2s_v5_1.pt"
SOURCE_A_PLUS4_DEFAULT = STATE_BANK_ROOT / "source_a_actor_e5_plus4s_v5_1.pt"
SOURCE_B_DEFAULT = STATE_BANK_ROOT / "source_b_constructed_v5_1.pt"
PHASES = ("s1", "s2", "s3", "s4", "s5", "s6", "s7")
PHASE_DEPENDENCIES = {
    "s1": (),
    "s2": ("s1",),
    "s3": ("s2",),
    "s4": ("s3",),
    "s5": ("s4",),
    "s6": ("s5",),
    "s7": ("s6",),
}


def _script(name: str) -> list[str]:
    return [str(PYTHON), str(SCRIPT_DIR / name)]


def _tmux(name: str, command: Sequence[str]) -> list[str]:
    """Return a detached, directly launchable tmux command."""

    return ["tmux", "new-session", "-d", "-s", name, "--", *command]


def _command_record(
    *, name: str, gpu: int | None, command: Sequence[str], output_dir: Path,
    consumes: Sequence[Path] = (), produces: Sequence[Path] = (),
) -> dict[str, Any]:
    return {
        "name": name,
        "gpu": gpu,
        "tmux_ready": gpu is not None,
        "command": list(command),
        "shell": " ".join(command),
        "tmux_command": _tmux(name, command) if gpu is not None else list(command),
        "output_dir": str(output_dir),
        "consumes": [str(path) for path in consumes],
        "produces": [str(path) for path in produces],
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=PHASES + ("p0", "state_bank", "p1", "p2", "p3", "eval", "analyze"), required=True)
    parser.add_argument("--p1-attempt", type=int, choices=P1_ATTEMPTS, default=1)
    parser.add_argument("--source-a", type=Path, default=SOURCE_A_DEFAULT)
    parser.add_argument("--source-a-plus2", type=Path, default=SOURCE_A_PLUS2_DEFAULT)
    parser.add_argument("--source-a-plus4", type=Path, default=SOURCE_A_PLUS4_DEFAULT)
    parser.add_argument("--source-b", type=Path, default=SOURCE_B_DEFAULT)
    parser.add_argument("--checkpoint-root", type=Path, default=TRAIN_ROOT)
    parser.add_argument("--step", type=int)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--allow-g8-pure-a", action="store_true")
    return parser.parse_args()


def _read_json(path: Path, *, label: str) -> Mapping[str, Any]:
    if not path.is_file():
        raise RuntimeError(f"{label} barrier receipt is missing: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise RuntimeError(f"{label} barrier receipt must be a mapping: {path}")
    return value


def _require_pass(path: Path, *, label: str, schemas: tuple[str, ...]) -> Mapping[str, Any]:
    receipt = _read_json(path, label=label)
    schema = receipt.get("schema")
    if not isinstance(schema, str) or not any(schema.startswith(prefix) for prefix in schemas):
        raise RuntimeError(f"{label} receipt has an unexpected schema: {schema!r}")
    if receipt.get("status") not in {"PASS", "PASS_G8_PURE_A"}:
        raise RuntimeError(f"{label} receipt is not PASS: {receipt.get('status')!r}")
    return receipt


def _require_f5_actual(path: Path, *, label: str) -> Mapping[str, Any]:
    receipt = _read_json(path, label=label)
    if receipt.get("schema") != "a2_piper_pull_v5_1_load_receipt_v2":
        raise RuntimeError(f"{label} receipt has an unexpected schema: {receipt.get('schema')!r}")
    if receipt.get("status") != "ACTUAL":
        raise RuntimeError(f"{label} receipt is not ACTUAL: {receipt.get('status')!r}")
    return receipt


def _phase_for_cli(phase: str) -> str:
    return {"p0": "s1", "state_bank": "s3", "p1": "s4", "p2": "s2", "p3": "s5", "eval": "s6", "analyze": "s6"}.get(phase, phase)


def _s1_commands() -> list[dict[str, Any]]:
    return [_command_record(
        name="s1_repair_runtime_startup_gate", gpu=None, command=[],
        output_dir=SCRIPT_DIR,
    )]


def _s2_commands(args: argparse.Namespace) -> list[dict[str, Any]]:
    source_a = args.source_a.resolve()
    source_a_plus2 = args.source_a_plus2.resolve()
    source_a_plus4 = args.source_a_plus4.resolve()
    source_b = args.source_b.resolve()
    checkpoint = TRAIN_ROOT / "pull_v4_B_wave1_seed1/model_step_000750.pt"
    records: list[dict[str, Any]] = []
    repair_command = _script("build_pull_v5_state_bank.py") + [
        "--repair-legacy-source-a", str(SOURCE_A_LEGACY),
        "--repair-legacy-metrics", str(SOURCE_A_LEGACY_METRICS),
        "--repair-output", str(source_a),
    ]
    records.append(_command_record(
        name="s2_source_a_repair_gpu7", gpu=7, command=repair_command,
        output_dir=source_a.parent,
        consumes=(SOURCE_A_LEGACY, SOURCE_A_LEGACY_METRICS), produces=(source_a,),
    ))
    f5_receipt = ROOT / "logs_rl/a2_piper_full_stage_a2_pull/pull_v5_load_receipts/pull_v5_1_policy_only.json"
    records.insert(0, _command_record(
        name="s2_f5_load_receipt_gpu6", gpu=6,
        command=_script("run_pull_v5_training.py") + ["--load-receipt-only", "--gpu", "6", "--run"],
        output_dir=TRAIN_ROOT / "pull_v5_1_policy_only_load", produces=(f5_receipt,),
    ))
    p2_dir = P2_ROOT
    records.append(_command_record(
        name="s2_p2_intervention_gpu5", gpu=5,
        command=_script("run_pull_v5_p2_intervention.py") + [
            "--gpu", "5", "--output-root", str(p2_dir), "--run",
        ],
        output_dir=p2_dir, produces=(P2_RECEIPT,),
    ))
    for label, tier, output in (
        ("plus2s", "e5_plus_2s", source_a_plus2),
        ("plus4s", "e5_plus_4s", source_a_plus4),
    ):
        command = _script("build_pull_v5_state_bank.py") + [
            "--source-a", str(output), "--run-source-a", "--source-a-tier", tier,
            "--capture-only", "--checkpoint", str(checkpoint), "--gpu", "7",
        ]
        records.append(_command_record(
            name=f"s2_source_a_{label}_gpu7", gpu=7, command=command, output_dir=output.parent,
            produces=(output,),
        ))
    source_b_command = _script("build_pull_v5_state_bank.py") + [
        "--source-a", str(source_a), "--source-b", str(source_b), "--run-source-b",
        "--capture-only", "--checkpoint", str(checkpoint), "--gpu", "4",
    ]
    records.append(_command_record(
        name="s2_source_b_gpu4", gpu=4, command=source_b_command, output_dir=source_b.parent,
        produces=(source_b,),
    ))
    return records


def _s3_commands(args: argparse.Namespace) -> list[dict[str, Any]]:
    source_a = args.source_a.resolve()
    plus2 = args.source_a_plus2.resolve()
    plus4 = args.source_a_plus4.resolve()
    # The first E5 payload is the source-A anchor; delayed captures are explicit
    # products and are consumed only after all S2 commands have completed.
    command = _script("build_pull_v5_state_bank.py") + [
        "--source-a", str(source_a), "--source-a-plus", str(plus2), "--source-a-plus", str(plus4),
    ]
    if not args.allow_g8_pure_a:
        command.extend(("--source-b", str(args.source_b.resolve())))
    command.extend(("--output", str(BANK)))
    if args.allow_g8_pure_a:
        command.append("--allow-g8-pure-a")
    consumes = [record_path for record_path in (
        source_a, plus2, plus4,
        ROOT / "logs_rl/a2_piper_full_stage_a2_pull/pull_v5_load_receipts/pull_v5_1_policy_only.json",
        P2_RECEIPT,
    )]
    if not args.allow_g8_pure_a:
        consumes.append(args.source_b.resolve())
    return [_command_record(
        name="s3_state_bank_g13", gpu=None, command=command, output_dir=STATE_BANK_ROOT,
        consumes=consumes, produces=(BANK, BANK_RECEIPT, STATE_BANK_ROOT / "pull_v5_state_bank_manifest.json"),
    )]


def _p1_paths(attempt: int) -> tuple[Path, Path, tuple[Path, ...]]:
    if attempt not in P1_ATTEMPTS:
        raise ValueError(f"P1 attempt must be one of {P1_ATTEMPTS}; got {attempt}")
    root = EVAL_ROOT / "pull_v5_1_p1_anchor_probe"
    suffix = "" if attempt == 1 else f"_attempt{attempt}"
    anchor_dir = root / ("anchor" if attempt == 1 else f"anchor{suffix}")
    anchor_receipt = anchor_dir / f"P1_anchor_natural_attempt{attempt}_RECEIPT.json"
    probe_receipts = tuple(
        root / (f"probe_{bucket.replace('-', '_')}" if attempt == 1 else f"probe_{bucket.replace('-', '_')}{suffix}")
        / f"P1_probe_canonical_attempt{attempt}_RECEIPT.json"
        for bucket in BUCKETS
    )
    return anchor_dir, anchor_receipt, probe_receipts


def _s4_commands(args: argparse.Namespace) -> list[dict[str, Any]]:
    anchor_dir, anchor_receipt, probe_receipts = _p1_paths(args.p1_attempt)
    anchor = _script("run_pull_v5_p1_anchor_probe.py") + [
        "--mode", "anchor", "--source", "natural", "--gpu", "4", "--anchor-attempt", str(args.p1_attempt),
        "--output-dir", str(anchor_dir), "--run",
    ]
    if args.allow_g8_pure_a:
        anchor.append("--allow-g8-pure-a")
    records = [_command_record(
        name="s4_anchor_open_field_gpu4", gpu=4, command=anchor, output_dir=anchor_dir,
        consumes=(BANK_RECEIPT,), produces=(anchor_receipt,),
    )]
    for bucket, probe_receipt in zip(BUCKETS, probe_receipts):
        output = probe_receipt.parent
        command = _script("run_pull_v5_p1_anchor_probe.py") + [
            "--mode", "probe", "--source", "canonical", "--gpu", "4", "--closer-bucket", bucket,
            "--anchor-attempt", str(args.p1_attempt), "--output-dir", str(output), "--run",
        ]
        if args.allow_g8_pure_a:
            command.append("--allow-g8-pure-a")
        records.append(_command_record(
            name=f"s4_probe_{bucket.replace('-', '_')}_gpu4", gpu=4, command=command, output_dir=output,
            consumes=(anchor_receipt, BANK_RECEIPT),
            produces=(probe_receipt,),
        ))
    return records


def _s5_commands(args: argparse.Namespace) -> list[dict[str, Any]]:
    _anchor_dir, anchor_receipt, probe_receipts = _p1_paths(args.p1_attempt)
    p2_receipt = P2_RECEIPT
    return [
        _command_record(
            name=f"s5_train_{cell}_gpu{gpu}", gpu=gpu,
            command=_script("run_pull_v5_training.py") + ["--cell", cell, "--gpu", str(gpu), "--run"] + (["--allow-g8-pure-a"] if args.allow_g8_pure_a else []),
            output_dir=TRAIN_ROOT / f"pull_v5_1_{cell}", consumes=(anchor_receipt, p2_receipt, BANK_RECEIPT, *probe_receipts),
            produces=(TRAIN_ROOT / f"pull_v5_1_{cell}/model_step_000250.pt",),
        )
        for cell, gpu in CELLS
    ]


def _s6_commands(args: argparse.Namespace) -> list[dict[str, Any]]:
    steps = (args.step,) if args.step is not None else CHECKPOINT_STEPS
    records: list[dict[str, Any]] = []
    for cell, gpu in CELLS:
        training_checkpoint = args.checkpoint_root.resolve() / f"pull_v5_1_{cell}/model_step_000250.pt"
        for step in steps:
            checkpoint = args.checkpoint_root.resolve() / f"pull_v5_1_{cell}/model_step_{step:06d}.pt"
            output = EVAL_ROOT / f"pull_v5_1_{cell}_step{step}"
            command = _script("run_pull_v5_eval.py") + [
                "--checkpoint", str(checkpoint), "--cell", cell, "--step", str(step), "--gpu", str(gpu), "--run",
            ] + (["--allow-g8-pure-a"] if args.allow_g8_pure_a else [])
            records.append(_command_record(
                name=f"s6_eval_{cell}_step{step}_gpu{gpu}", gpu=gpu, command=command, output_dir=output,
                consumes=(training_checkpoint,),
                produces=(
                    EVAL_ROOT / f"pull_v5_1_{cell}_step{step}_canonical/terminal_records.json",
                    EVAL_ROOT / f"pull_v5_1_{cell}_step{step}_natural/terminal_records.json",
                ),
            ))
    records.append(_command_record(
        name="s6_analyze_v5_1", gpu=None,
        command=_script("analyze_pull_v5.py") + [
            *sum((
                ["--cell-root", str(Path(product).parent)]
                for item in records
                if item["name"].startswith("s6_eval_")
                for product in item["produces"]
            ), []),
            "--output", str(ANALYSIS),
        ],
        output_dir=ANALYSIS.parent,
        consumes=tuple(Path(product) for record in records if record["name"].startswith("s6_eval_") for product in record["produces"]),
        produces=(ANALYSIS,),
    ))
    return records


def _s7_commands() -> list[dict[str, Any]]:
    return [{
        "name": "s7_closure_artifacts",
        "gpu": None,
        "tmux_ready": False,
        "command": [],
        "shell": "",
        "tmux_command": [],
        "output_dir": str(SCRIPT_DIR),
        "consumes": [str(ANALYSIS)],
        "produces": [
            str(SCRIPT_DIR / "PULL_V5_1_ROUND_REPORT.md"),
            "memory/a2-piper/pull-open-door-task/description.md",
            "memory/a2-piper/pull-open-door-task/TODO.md",
            "memory/a2-piper/pull-open-door-task/DONE.md",
        ],
        "conditional_p4": {
            "record_only": True,
            "condition": "canonical frame_passage_rate > 0 and natural frame_passage_rate > 0",
            "otherwise": "record G5/G6/G7/G11/G12 decision and stop",
        },
    }]


def phase_commands(args: argparse.Namespace) -> list[dict[str, Any]]:
    phase = _phase_for_cli(args.phase)
    if phase == "s1":
        return _s1_commands()
    if phase == "s2":
        return _s2_commands(args)
    if phase == "s3":
        return _s3_commands(args)
    if phase == "s4":
        return _s4_commands(args)
    if phase == "s5":
        return _s5_commands(args)
    if phase == "s6":
        return _s6_commands(args)
    if phase == "s7":
        return _s7_commands()
    raise AssertionError(phase)


def _barrier_paths(phase: str, args: argparse.Namespace) -> list[tuple[Path, str, tuple[str, ...]]]:
    phase = _phase_for_cli(phase)
    if phase == "s1":
        return []
    if phase == "s2":
        return []
    if phase == "s3":
        paths = [
            (ROOT / "logs_rl/a2_piper_full_stage_a2_pull/pull_v5_load_receipts/pull_v5_1_policy_only.json", "S2/F5", ("a2_piper_pull_v5_1",)),
            (P2_RECEIPT, "S2/P2", ("a2_piper_pull_v5_1_p2",)),
            (args.source_a.resolve(), "S2/SourceA E5", ()),
            (args.source_a_plus2.resolve(), "S2/SourceA +2s", ()),
            (args.source_a_plus4.resolve(), "S2/SourceA +4s", ()),
        ]
        if not args.allow_g8_pure_a:
            paths.append((args.source_b.resolve(), "S2/SourceB", ()))
        return paths
    if phase == "s4":
        return [(BANK_RECEIPT, "S3/G13", ("a2_piper_pull_v5_state_bank_v2",))]
    if phase == "s5":
        _anchor_dir, anchor, probe_receipts = _p1_paths(args.p1_attempt)
        paths = [
            (BANK_RECEIPT, "S3/G13", ("a2_piper_pull_v5_state_bank_v2",)),
            (anchor, "S4/anchor", ("a2_piper_pull_v5_1_p1_receipt",)),
            (P2_RECEIPT, "S2/P2", ("a2_piper_pull_v5_1_p2",)),
        ]
        paths.extend(
            (
                probe_receipt,
                f"S4/probe_{bucket}",
                ("a2_piper_pull_v5_1_p1_receipt",),
            )
            for bucket, probe_receipt in zip(BUCKETS, probe_receipts)
        )
        return paths
    if phase == "s6":
        return [
            (TRAIN_ROOT / f"pull_v5_1_{cell}/model_step_000250.pt", f"S5/{cell}", ())
            for cell, _gpu in CELLS
        ] + [(BANK_RECEIPT, "S3/G13", ("a2_piper_pull_v5_state_bank_v2",))]
    if phase == "s7":
        return [(ANALYSIS, "S6/analysis", ("a2_piper_pull_v5_1_analysis",))]
    raise AssertionError(phase)


def enforce_barriers(phase: str, args: argparse.Namespace) -> None:
    for path, label, schemas in _barrier_paths(phase, args):
        if not path.is_file():
            raise RuntimeError(f"{label} barrier product is missing: {path}")
        if label == "S2/F5":
            _require_f5_actual(path, label=label)
        elif schemas:
            _require_pass(path, label=label, schemas=schemas)


def _run_wave(records: Sequence[Mapping[str, Any]]) -> None:
    processes: list[subprocess.Popen[bytes]] = []
    for record in records:
        command = list(record["command"])
        if not command:
            continue
        env = os.environ.copy()
        gpu = record.get("gpu")
        if gpu is not None:
            env["CUDA_VISIBLE_DEVICES"] = str(gpu)
            env["ACCELERATE_TORCH_DEVICE"] = "cuda:0"
        processes.append(subprocess.Popen(command, cwd=ROOT, env=env))
    statuses = [process.wait() for process in processes]
    if any(status != 0 for status in statuses):
        raise RuntimeError(f"phase wave failed with return codes {statuses}")


def _run_s6_eval_wave(records: Sequence[Mapping[str, Any]]) -> None:
    """Run one checkpoint at a time per cell while keeping cells parallel."""

    by_cell: dict[str, list[Mapping[str, Any]]] = {cell: [] for cell, _gpu in CELLS}
    for record in records:
        name = str(record["name"])
        cell = next(
            (candidate for candidate, _gpu in CELLS if f"s6_eval_{candidate}_" in name),
            None,
        )
        if cell is None:
            raise RuntimeError(f"S6 eval record is not bound to a known cell: {name}")
        by_cell[cell].append(record)
    for cell_records in by_cell.values():
        cell_records.sort(key=lambda record: str(record["name"]))
    for index in range(max(len(cell_records) for cell_records in by_cell.values())):
        _run_wave(
            [cell_records[index] for cell_records in by_cell.values() if index < len(cell_records)]
        )


def _run_s2_wave(records: Sequence[Mapping[str, Any]], *, allow_g8_pure_a: bool) -> None:
    """Run S2's independent lanes with Source-A captures serialized on GPU7."""

    source_a = [record for record in records if str(record["name"]).startswith("s2_source_a_")]
    other_lanes = [record for record in records if record not in source_a]
    if allow_g8_pure_a:
        other_lanes = [record for record in other_lanes if record["name"] != "s2_source_b_gpu4"]
    if not source_a:
        raise RuntimeError("S2 requires the three Source-A capture commands")
    _run_wave([source_a[0], *other_lanes])
    for record in source_a[1:]:
        _run_wave([record])


def main() -> int:
    args = _parse_args()
    phase = _phase_for_cli(args.phase)
    if args.run:
        enforce_barriers(phase, args)
    records = phase_commands(args)
    receipt = {
        "schema": "a2_piper_pull_v5_1_orchestration_v3",
        "phase": phase,
        "p1_attempt": args.p1_attempt,
        "phase_order": list(PHASES),
        "dependencies": {name: list(deps) for name, deps in PHASE_DEPENDENCIES.items()},
        "barriers_enforced_on_run": True,
        "commands": records,
        "s2_contract": {
            "f5_phase": "s2",
            "f5_gpu": 6,
            "p2_gpu": 5,
            "source_a_gpu": 7,
            "source_b_gpu": 4,
            "source_a_tiers": ["e5_repaired_offline", "e5_plus_2s", "e5_plus_4s"],
            "source_a_serialized_on_gpu7": True,
            "capture_only": True,
        },
        "s1_contract": {"purpose": "F1 guard and F2 P2 decoupling repair/runtime-startup gate"},
        "s4_contract": {"anchor_first": True, "anchor_retry_limit": 3, "selected_attempt": args.p1_attempt, "closer_buckets": list(BUCKETS)},
        "s5_contract": {"p1_p2_gates": ["anchor_pass", "p2_pass"], "concurrent_cells": [f"{cell}:GPU{gpu}" for cell, gpu in CELLS]},
        "s6_contract": {"checkpoint_steps": list(args.step and (args.step,) or CHECKPOINT_STEPS), "sources": ["canonical", "natural"], "episodes_per_source": 16},
        "s7_contract": _s7_commands()[0],
        "run": args.run,
    }
    print(json.dumps(receipt, indent=2, sort_keys=True))
    if not args.run:
        return 0
    if phase == "s4":
        anchor = [record for record in records if record["name"] == "s4_anchor_open_field_gpu4"]
        _run_wave(anchor)
        _anchor_dir, anchor_receipt, _probe_receipts = _p1_paths(args.p1_attempt)
        anchor_payload = _require_pass(
            anchor_receipt, label="S4/anchor", schemas=("a2_piper_pull_v5_1_p1_receipt",)
        )
        if anchor_payload.get("anchor_pass") is not True:
            raise RuntimeError("S4 door probes require measured anchor_pass=true")
        measurements = anchor_payload.get("anchor_measurements")
        if (
            not isinstance(measurements, list)
            or not measurements
            or any(
                not isinstance(measurement, Mapping)
                or measurement.get("waypoint_arrived") is not True
                or measurement.get("yaw_arrived") is not True
                for measurement in measurements
            )
        ):
            raise RuntimeError("S4 door probes require measured waypoint and yaw arrival for every anchor row")
        for probe in (record for record in records if record["name"] != "s4_anchor_open_field_gpu4"):
            _run_wave([probe])
    elif phase == "s5":
        _run_wave(records)
    elif phase == "s6":
        # Training products are already a barrier; each GPU advances one cell's
        # checkpoints sequentially while the four cells run in parallel.
        _run_s6_eval_wave([record for record in records if record.get("gpu") is not None])
        analysis = [record for record in records if record.get("name") == "s6_analyze_v5_1"]
        _run_wave(analysis)
    elif phase == "s2":
        _run_s2_wave(records, allow_g8_pure_a=args.allow_g8_pure_a)
    else:
        _run_wave(records)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
