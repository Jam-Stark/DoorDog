#!/usr/bin/env python3
"""Generate and execute the Pull-v5.3 conditional T0→P4 workflow.

T1 is deliberately serialized on GPU4: the narrow anchor completes before any
door-side probe launches.  T2 is a real G1/G2 gate; training is never started
from an all-zero probe receipt.  T3 is the conditional four-GPU training wave,
and T4 evaluates every saved checkpoint through the strict v5.2 analyzer.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_pull_v5_training as training
from write_pull_v5_3_p0_adjudication import require_p0_adjudication


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent
PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
TRAIN_ROOT = ROOT / "logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull"
EVAL_ROOT = ROOT / "logs_eval/a2_piper_pull_v5"
VERSION = "5.3"
VERSION_TAG = "v5_3"
P1_ROOT = EVAL_ROOT / f"pull_{VERSION_TAG}_p1_anchor_probe"
GATE_ROOT = EVAL_ROOT / f"{VERSION_TAG}_gates"
ANCHOR_DIR = P1_ROOT / "anchor"
ANCHOR_RECEIPT = ANCHOR_DIR / "P1_v5_3_anchor_natural_attempt1_RECEIPT.json"
BUCKETS = ("2.5-5", "5-9", "9-12")
SEQUENCES = ("S1", "S2", "S3", "S4")
CELLS = (("M_s0", 4), ("M_s1", 5), ("C_s0", 6), ("C_s1", 7))
CHECKPOINT_STEPS = (50, 100, 150, 200, 250)
P4_ANNEAL_RATIOS = (0.9, 0.5, 0.3)
PHASES = ("T0", "T1", "T2", "T3", "T4", "P4")
PHASE_DEPENDENCIES = {
    "T0": (), "T1": ("T0",), "T2": ("T1",), "T3": ("T2",), "T4": ("T3",), "P4": ("T4",),
}
ANALYSIS = SCRIPT_DIR / "PULL_V5_3_ANALYSIS.json"
GATE_RECEIPT = GATE_ROOT / "T2_GATE_RECEIPT.json"
G2_RECEIPT = GATE_ROOT / "G2_lattice_RECEIPT.json"


def _script(name: str) -> list[str]:
    return [str(PYTHON), str(SCRIPT_DIR / name)]


def _tmux(name: str, command: Sequence[str]) -> list[str]:
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
    parser.add_argument("--phase", choices=PHASES, required=True)
    parser.add_argument("--p1-attempt", type=int, choices=(1, 2, 3), default=1)
    parser.add_argument("--checkpoint-root", type=Path, default=TRAIN_ROOT)
    parser.add_argument("--step", type=int)
    parser.add_argument("--p4-cell", choices=tuple(cell for cell, _gpu in CELLS), default="M_s0")
    parser.add_argument("--p4-checkpoint", type=Path)
    parser.add_argument("--p4-ratio", type=float)
    parser.add_argument("--p4-additional-batches", type=int, default=250)
    parser.add_argument("--p4-fixed", action="store_true", help="emit one selected-ratio P4 step instead of .9→.5→.3")
    parser.add_argument("--p0-adjudication", type=Path)
    parser.add_argument("--run", action="store_true")
    return parser.parse_args()


def _p1_paths(attempt: int) -> tuple[Path, Path, tuple[Path, ...]]:
    suffix = "" if attempt == 1 else f"_attempt{attempt}"
    root = EVAL_ROOT / f"pull_{VERSION_TAG}_p1_anchor_probe"
    anchor_dir = root / ("anchor" if attempt == 1 else f"anchor{suffix}")
    anchor_receipt = anchor_dir / f"P1_{VERSION_TAG}_anchor_natural_attempt{attempt}_RECEIPT.json"
    probe_receipts = tuple(
        root / (f"probe_{bucket.replace('-', '_')}" if attempt == 1 else f"probe_{bucket.replace('-', '_')}{suffix}")
        / f"P1_{VERSION_TAG}_probe_canonical_attempt{attempt}_RECEIPT.json"
        for bucket in BUCKETS
    )
    return anchor_dir, anchor_receipt, probe_receipts


def _t0_commands() -> list[dict[str, Any]]:
    return [{
        "name": "t0_contract_preflight",
        "gpu": None,
        "tmux_ready": False,
        "command": [],
        "shell": "",
        "tmux_command": [],
        "output_dir": str(SCRIPT_DIR),
        "consumes": [],
        "produces": [],
        "contract": {
            "sequence_ids": list(SEQUENCES),
            "sequence_phases": {
                "S1": ["straight_minus_x"],
                "S2": ["side_step"],
                "S3": ["side_step", "straight_minus_x"],
                "S4": ["straight_minus_x", "side_step"],
            },
            "rows_per_sequence": 16,
            "allow_g8_pure_a": True,
            "start_override_keys": [
                "a2_pull_v5_start_override_enabled",
                "a2_pull_v5_start_override_steps",
            ],
            "invariants": 11,
        },
    }]


def _t1_commands(attempt: int, p0_adjudication: Path) -> list[dict[str, Any]]:
    anchor_dir, anchor_receipt, probe_receipts = _p1_paths(attempt)
    anchor = _script("run_pull_v5_p1_anchor_probe.py") + [
        "--mode", "anchor", "--source", "natural", "--gpu", "4",
        "--anchor-attempt", str(attempt), "--output-dir", str(anchor_dir), "--allow-g8-pure-a", "--run",
        "--p0-adjudication", str(p0_adjudication),
    ]
    records = [_command_record(
        name="t1_anchor_gpu4", gpu=4, command=anchor, output_dir=anchor_dir,
        produces=(anchor_receipt,),
    )]
    for bucket, probe_receipt in zip(BUCKETS, probe_receipts):
        output = probe_receipt.parent
        probe = _script("run_pull_v5_p1_anchor_probe.py") + [
            "--mode", "probe", "--source", "canonical", "--gpu", "4",
            "--closer-bucket", bucket, "--anchor-attempt", str(attempt),
            "--anchor-receipt", str(anchor_receipt), "--output-dir", str(output), "--allow-g8-pure-a", "--run",
            "--p0-adjudication", str(p0_adjudication),
        ]
        records.append(_command_record(
            name=f"t1_probe_{bucket.replace('-', '_')}_gpu4", gpu=4, command=probe,
            output_dir=output, consumes=(anchor_receipt,), produces=(probe_receipt,),
        ))
    return records


def _t2_commands(attempt: int, p0_adjudication: Path) -> list[dict[str, Any]]:
    _anchor_dir, anchor_receipt, probe_receipts = _p1_paths(attempt)
    lattice_dir = P1_ROOT / ("lattice" if attempt == 1 else f"lattice_attempt{attempt}")
    lattice_command = _script("run_pull_v5_p1_anchor_probe.py") + [
        "--mode", "lattice", "--source", "canonical", "--gpu", "4",
        "--anchor-attempt", str(attempt), "--output-dir", str(lattice_dir), "--receipt", str(G2_RECEIPT), "--allow-g8-pure-a", "--run",
        "--p0-adjudication", str(p0_adjudication),
    ]
    return [
        _command_record(
            name="t2_g1_gate", gpu=None, command=[], output_dir=GATE_ROOT,
            consumes=(*probe_receipts,), produces=(GATE_RECEIPT,),
        ),
        _command_record(
            name="t2_g2_lattice_gpu4", gpu=4, command=lattice_command, output_dir=lattice_dir,
            consumes=(*probe_receipts, anchor_receipt), produces=(G2_RECEIPT,),
        ),
    ]


def _t3_commands(attempt: int, p0_adjudication: Path) -> list[dict[str, Any]]:
    _anchor_dir, anchor_receipt, probe_receipts = _p1_paths(attempt)
    records = []
    for cell, gpu in CELLS:
        output = TRAIN_ROOT / f"pull_{VERSION_TAG}_{cell}"
        command = _script("run_pull_v5_training.py") + [
            "--cell", cell, "--gpu", str(gpu), "--version", VERSION,
            "--allow-g8-pure-a", "--run",
            "--p0-adjudication", str(p0_adjudication),
        ]
        records.append(_command_record(
            name=f"t3_train_{cell}_gpu{gpu}", gpu=gpu, command=command, output_dir=output,
            consumes=(GATE_RECEIPT, anchor_receipt, *probe_receipts),
            produces=(output / "model_step_000250.pt",),
        ))
    return records


def _t4_commands(args: argparse.Namespace, attempt: int, p0_adjudication: Path) -> list[dict[str, Any]]:
    steps = (args.step,) if args.step is not None else CHECKPOINT_STEPS
    records: list[dict[str, Any]] = []
    for cell, gpu in CELLS:
        for step in steps:
            checkpoint = args.checkpoint_root.resolve() / f"pull_{VERSION_TAG}_{cell}/model_step_{step:06d}.pt"
            output = EVAL_ROOT / f"{VERSION_TAG}_{cell}_step{step}"
            command = _script("run_pull_v5_eval.py") + [
                "--checkpoint", str(checkpoint), "--cell", cell, "--step", str(step),
                "--gpu", str(gpu), "--version", VERSION, "--allow-g8-pure-a", "--run",
                "--p0-adjudication", str(p0_adjudication),
            ]
            records.append(_command_record(
                name=f"t4_eval_{cell}_step{step}_gpu{gpu}", gpu=gpu, command=command,
                output_dir=output, consumes=(TRAIN_ROOT / f"pull_{VERSION_TAG}_{cell}/model_step_000250.pt",),
                produces=(
                    EVAL_ROOT / f"{VERSION_TAG}_{cell}_step{step}_canonical/terminal_records.json",
                    EVAL_ROOT / f"{VERSION_TAG}_{cell}_step{step}_natural/terminal_records.json",
                ),
            ))
    eval_records = tuple(records)
    analysis_command = _script("analyze_pull_v5.py") + [
        *sum((["--cell-root", str(Path(product).parent)] for record in eval_records for product in record["produces"]), []),
        "--version", VERSION, "--output", str(ANALYSIS),
    ]
    records.append(_command_record(
        name="t4_analyze_v5_3", gpu=None, command=analysis_command, output_dir=ANALYSIS.parent,
        consumes=tuple(Path(product) for record in eval_records for product in record["produces"]),
        produces=(ANALYSIS,),
    ))
    return records


def _p4_commands(args: argparse.Namespace, p0_adjudication: Path) -> list[dict[str, Any]]:
    """Build a sequential evidence-selected P4 continuation/anneal."""

    cell = args.p4_cell
    gpu = dict(CELLS)[cell]
    checkpoint = (
        args.p4_checkpoint.resolve()
        if args.p4_checkpoint is not None
        else (TRAIN_ROOT / f"pull_{VERSION_TAG}_{cell}/model_step_000250.pt").resolve()
    )
    if args.p4_fixed and args.p4_ratio is None:
        raise ValueError("--p4-fixed requires --p4-ratio")
    ratios = (args.p4_ratio,) if args.p4_ratio is not None else P4_ANNEAL_RATIOS
    records: list[dict[str, Any]] = []
    for index, ratio in enumerate(ratios):
        command, _env, output_dir = training.build_p4_command(
            cell=cell, gpu=gpu, checkpoint=checkpoint, ratio=float(ratio),
            additional_batches=args.p4_additional_batches, version=VERSION,
            anneal_index=index, allow_missing_checkpoint=True, allow_g8_pure_a=True,
            p0_adjudication=p0_adjudication,
        )
        produced = output_dir / f"model_step_{args.p4_additional_batches:06d}.pt"
        records.append(_command_record(
            name=f"p4_{cell}_r{str(ratio).replace('.', 'p')}_gpu{gpu}", gpu=gpu,
            command=command, output_dir=output_dir, consumes=(checkpoint,), produces=(produced,),
        ))
        checkpoint = produced
    return records


def phase_commands(args: argparse.Namespace) -> list[dict[str, Any]]:
    if args.phase == "T0":
        return _t0_commands()
    p0_adjudication = getattr(args, "p0_adjudication", None)
    if p0_adjudication is None:
        raise ValueError("Pull-v5.3 downstream phases require --p0-adjudication")
    require_p0_adjudication(p0_adjudication)
    if args.phase == "T1":
        return _t1_commands(args.p1_attempt, p0_adjudication)
    if args.phase == "T2":
        return _t2_commands(args.p1_attempt, p0_adjudication)
    if args.phase == "T3":
        return _t3_commands(args.p1_attempt, p0_adjudication)
    if args.phase == "T4":
        return _t4_commands(args, args.p1_attempt, p0_adjudication)
    if args.phase == "P4":
        return _p4_commands(args, p0_adjudication)
    raise AssertionError(args.phase)


def _read_json(path: Path, label: str) -> Mapping[str, Any]:
    if not path.is_file():
        raise RuntimeError(f"{label} product is missing: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise RuntimeError(f"{label} product must be a mapping: {path}")
    return value


def _require_schema(path: Path, label: str, prefix: str) -> Mapping[str, Any]:
    value = _read_json(path, label)
    schema = value.get("schema")
    if not isinstance(schema, str) or not schema.startswith(prefix):
        raise RuntimeError(f"{label} has unexpected schema {schema!r}")
    return value


def _probe_passage(receipt: Mapping[str, Any]) -> int:
    records = receipt.get("bucket_sequence_records")
    if not isinstance(records, Mapping):
        raise RuntimeError("v5.3 probe receipt requires bucket_sequence_records")
    requested_bucket = receipt.get("closer_bucket")
    if requested_bucket not in BUCKETS:
        raise RuntimeError(f"v5.3 probe receipt must identify one closer bucket; got {requested_bucket!r}")
    total = 0
    for bucket, sequence_records in records.items():
        if bucket not in BUCKETS or not isinstance(sequence_records, Mapping):
            raise RuntimeError(f"invalid bucket×sequence receipt entry: {bucket!r}")
        for sequence, summary in sequence_records.items():
            if sequence not in SEQUENCES or not isinstance(summary, Mapping):
                raise RuntimeError(f"invalid bucket×sequence receipt entry: {bucket}×{sequence}")
            episodes = summary.get("episodes")
            passage = summary.get("passage")
            expected = 16 if bucket == requested_bucket else 0
            if episodes != expected or isinstance(passage, bool) or not isinstance(passage, int) or passage < 0 or passage > episodes:
                raise RuntimeError(f"invalid actual denominator/passage for {bucket}×{sequence}: {summary!r}")
            total += passage
    return total


def _write_gate(*, attempt: int, status: str, probe_passage: int, lattice_passage: int | None = None) -> None:
    GATE_ROOT.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "a2_piper_pull_v5_3_gate_receipt_v1",
        "status": status,
        "p1_attempt": attempt,
        "probe_frame_passage": probe_passage,
        "lattice_frame_passage": lattice_passage,
        "training_gate": status in {"G1_PASS", "G2_PASS"},
        "all_zero_routes_to_g2": probe_passage == 0,
    }
    GATE_RECEIPT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _run_wave(records: Sequence[Mapping[str, Any]]) -> None:
    processes: list[subprocess.Popen[bytes]] = []
    for record in records:
        command = list(record["command"])
        if not command:
            continue
        env = os.environ.copy()
        if record.get("gpu") is not None:
            env["CUDA_VISIBLE_DEVICES"] = str(record["gpu"])
            env["ACCELERATE_TORCH_DEVICE"] = "cuda:0"
        processes.append(subprocess.Popen(command, cwd=ROOT, env=env))
    statuses = [process.wait() for process in processes]
    if any(status != 0 for status in statuses):
        raise RuntimeError(f"workflow wave failed with return codes {statuses}")


def _run_t1(records: Sequence[Mapping[str, Any]]) -> None:
    anchor = [record for record in records if record["name"] == "t1_anchor_gpu4"]
    _run_wave(anchor)
    anchor_record = records[0]
    anchor_receipt = Path(anchor_record["produces"][0])
    anchor_payload = _require_schema(anchor_receipt, "T1 anchor", "a2_piper_pull_v5_3_p1_receipt")
    if anchor_payload.get("anchor_pass") is not True:
        raise RuntimeError("T1 anchor failed; door probes are not admissible")
    for record in records[1:]:
        _run_wave([record])


def _run_t2(records: Sequence[Mapping[str, Any]], attempt: int) -> None:
    _anchor_dir, _anchor_receipt, probe_receipts = _p1_paths(attempt)
    passage = 0
    for path in probe_receipts:
        receipt = _require_schema(path, f"T2 probe {path.name}", "a2_piper_pull_v5_3_p1_receipt")
        passage += _probe_passage(receipt)
    if passage > 0:
        _write_gate(attempt=attempt, status="G1_PASS", probe_passage=passage)
        return
    lattice_record = next(record for record in records if record["name"] == "t2_g2_lattice_gpu4")
    _run_wave([lattice_record])
    lattice_payload = _require_schema(G2_RECEIPT, "T2 G2 lattice", "a2_piper_pull_v5_3_p1_receipt")
    lattice_passage = int(lattice_payload.get("frame_passage_count", 0))
    _write_gate(
        attempt=attempt,
        status="G2_PASS" if lattice_passage > 0 else "G2_STOP",
        probe_passage=passage,
        lattice_passage=lattice_passage,
    )


def _require_training_gate() -> None:
    gate = _require_schema(GATE_RECEIPT, "T3 gate", "a2_piper_pull_v5_3_gate_receipt")
    if gate.get("status") not in {"G1_PASS", "G2_PASS"}:
        raise RuntimeError(f"T3 cannot start without a passage-positive gate: {gate.get('status')!r}")


def _run_t4(records: Sequence[Mapping[str, Any]]) -> None:
    eval_records = [record for record in records if record["gpu"] is not None]
    by_cell: dict[str, list[Mapping[str, Any]]] = {cell: [] for cell, _gpu in CELLS}
    for record in eval_records:
        cell = next(cell for cell, _gpu in CELLS if f"t4_eval_{cell}_" in record["name"])
        by_cell[cell].append(record)
    for cell_records in by_cell.values():
        cell_records.sort(key=lambda record: record["name"])
    for index in range(max(len(cell_records) for cell_records in by_cell.values())):
        _run_wave([items[index] for items in by_cell.values() if index < len(items)])
    _run_wave([record for record in records if record["name"] == "t4_analyze_v5_3"])


def _run_p4(records: Sequence[Mapping[str, Any]]) -> None:
    """Run P4 continuation stages in order so anneal stages consume evidence."""

    for record in records:
        _run_wave([record])
        products = record.get("produces", ())
        if products and not Path(products[0]).is_file():
            raise RuntimeError(f"P4 stage exited without checkpoint: {products[0]}")


def main() -> int:
    args = _parse_args()
    records = phase_commands(args)
    receipt = {
        "schema": "a2_piper_pull_v5_3_orchestration_v1",
        "phase": args.phase,
        "phase_order": list(PHASES),
        "dependencies": {name: list(deps) for name, deps in PHASE_DEPENDENCIES.items()},
        "commands": records,
        "run": args.run,
        "gpu_scope": [4, 5, 6, 7],
        "t1_contract": {"anchor_first": True, "gpu": 4, "rows_per_sequence": 16, "sequence_ids": list(SEQUENCES)},
        "t2_contract": {"g1_any_bucket_sequence_passage": True, "all_zero_routes_to": "G2_lattice", "g2_gpu": 4},
        "t3_contract": {"conditional": True, "cells": [f"{cell}:GPU{gpu}" for cell, gpu in CELLS], "num_envs": 256, "batches": 250, "save_frequency": 50},
        "t4_contract": {"sources": ["canonical", "natural"], "episodes_per_source": 16, "checkpoint_steps": list(args.step and (args.step,) or CHECKPOINT_STEPS), "invariants": 11},
        "p4_contract": {
            "conditional": True,
            "selected_cell": args.p4_cell,
            "ratios": [args.p4_ratio] if args.p4_fixed and args.p4_ratio is not None else list(P4_ANNEAL_RATIOS),
            "additional_batches": args.p4_additional_batches,
            "checkpoint_load_mode": "policy_only",
            "load_optimizer": False,
        },
    }
    if args.phase != "T0":
        receipt["p0_adjudication_path"] = str(args.p0_adjudication.resolve())
    print(json.dumps(receipt, indent=2, sort_keys=True))
    if not args.run:
        return 0
    if args.phase == "T0":
        return 0
    if args.phase == "T1":
        _run_t1(records)
    elif args.phase == "T2":
        _run_t2(records, args.p1_attempt)
    elif args.phase == "T3":
        _require_training_gate()
        _run_wave(records)
    elif args.phase == "T4":
        _run_t4(records)
    elif args.phase == "P4":
        _run_p4(records)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
