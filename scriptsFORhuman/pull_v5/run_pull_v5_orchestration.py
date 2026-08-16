#!/usr/bin/env python3
"""Generate and execute the Pull-v5.4 conditional T0→P4 workflow.

T1 is deliberately serialized on GPU4 for the Stage-B rehearsal.  T2 runs the
narrow anchor before any door-side probe launches.  T2 is a real G1/G2 gate; training is never started
from an all-zero probe receipt.  T3 is the conditional four-GPU training wave,
and T4 evaluates every saved checkpoint through the strict v5.4 analyzer.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_pull_v5_training as training
import pull_v5_4_gates as gates


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent
PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
TRAIN_ROOT = ROOT / "logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull"
EVAL_ROOT = ROOT / "logs_eval/a2_piper_pull_v5"
VERSION = "5.4"
VERSION_TAG = "v5_4"
P1_ROOT = EVAL_ROOT / f"pull_{VERSION_TAG}_p1_anchor_probe"
GATE_ROOT = EVAL_ROOT / f"{VERSION_TAG}_gates"
ANCHOR_DIR = P1_ROOT / "anchor"
ANCHOR_RECEIPT = ANCHOR_DIR / "P1_v5_4_anchor_natural_attempt1_RECEIPT.json"
BUCKETS = ("2.5-5", "5-9", "9-12")
SEQUENCES = ("S1", "S2", "S3", "S4")
CELLS = (("M_s0", 4), ("M_s1", 5), ("C_s0", 6), ("C_s1", 7))
CHECKPOINT_STEPS = (50, 100, 150, 200, 250)
P4_ANNEAL_RATIOS = (0.9, 0.5, 0.3)
PHASES = ("T0", "T1", "T2", "T3", "T4", "P4")
PHASE_DEPENDENCIES = {
    "T0": (), "T1": ("T0",), "T2": ("T1",), "T3": ("T2",), "T4": ("T3",), "P4": ("T4",),
}
ANALYSIS = SCRIPT_DIR / "PULL_V5_4_ANALYSIS.json"
GATE_RECEIPT = GATE_ROOT / "T2_GATE_RECEIPT.json"
G2_RECEIPT = GATE_ROOT / "G2_lattice_RECEIPT.json"


def _script(name: str) -> list[str]:
    return [str(PYTHON), str(SCRIPT_DIR / name)]


def _tmux(name: str, command: Sequence[str], *, output_dir: Path | None = None) -> list[str]:
    if output_dir is not None:
        log_path = output_dir / "runner.log"
        shell = (
            f"mkdir -p {shlex.quote(str(output_dir))}; "
            "set -o pipefail; "
            f"{' '.join(shlex.quote(item) for item in command)} 2>&1 | "
            f"tee {shlex.quote(str(log_path))}; "
            "status=${PIPESTATUS[0]}; "
            f"printf '%s\\n' \"$status\" > {shlex.quote(str(output_dir / 'tmux.exit'))}; "
            f"tmux wait-for -S {shlex.quote(name + '.done')}"
        )
        return ["tmux", "new-session", "-d", "-s", name, "--", "bash", "-lc", shell]
    return ["tmux", "new-session", "-d", "-s", name, "--", *command]


def _command_record(
    *, name: str, gpu: int | None, command: Sequence[str], output_dir: Path,
    consumes: Sequence[Path] = (), produces: Sequence[Path] = (),
    tmux_managed: bool = False,
) -> dict[str, Any]:
    return {
        "name": name,
        "gpu": gpu,
        "tmux_ready": gpu is not None,
        "command": list(command),
        "shell": " ".join(command),
        "tmux_command": _tmux(
            name,
            command,
            output_dir=output_dir if tmux_managed else None,
        ) if gpu is not None else list(command),
        "tmux_managed": tmux_managed,
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
    parser.add_argument("--decision", type=Path, default=gates.DEFAULT_DECISION)
    parser.add_argument("--stage-a", type=Path, default=gates.DEFAULT_STAGE_A)
    parser.add_argument("--rehearsal", type=Path, default=gates.DEFAULT_REHEARSAL)
    parser.add_argument("--anchor-receipt", type=Path)
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


def _current_anchor_receipt(args: argparse.Namespace, attempt: int) -> Path:
    _anchor_dir, generated, _probe_receipts = _p1_paths(attempt)
    if args.anchor_receipt is None:
        return generated
    explicit = args.anchor_receipt.expanduser().resolve()
    if attempt > 1 and explicit == _p1_paths(1)[1].resolve():
        raise ValueError("attempt-specific anchor receipt cannot reuse attempt-1 path")
    return explicit


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


def _t1_commands(args: argparse.Namespace) -> list[dict[str, Any]]:
    rehearsal_root = EVAL_ROOT / "v5_4_stage_b_rehearsal"
    receipt = rehearsal_root / "REHEARSAL_RECEIPT.json"
    command = _script("run_pull_v5_4_terminal_scheduler.py") + [
        "--checkpoint", str((TRAIN_ROOT / "pull_v4_B_wave1_seed1/model_step_000750.pt").resolve()),
        "--gpu", "4", "--decision", str(args.decision), "--stage-a", str(args.stage_a),
        "--output-root", str(rehearsal_root), "--receipt", str(receipt), "--run",
    ]
    return [_command_record(
        name="t1_stage_b_rehearsal_gpu4", gpu=4, command=command,
        output_dir=rehearsal_root, consumes=(args.stage_a, args.decision), produces=(receipt,),
    )]


def _t2_commands(args: argparse.Namespace, attempt: int) -> list[dict[str, Any]]:
    _anchor_dir, _generated_anchor_receipt, probe_receipts = _p1_paths(attempt)
    anchor_receipt = _current_anchor_receipt(args, attempt)
    lattice_dir = P1_ROOT / ("lattice" if attempt == 1 else f"lattice_attempt{attempt}")
    lattice_command = _script("run_pull_v5_p1_anchor_probe.py") + [
        "--mode", "lattice", "--source", "canonical", "--gpu", "4",
        "--anchor-attempt", str(attempt), "--output-dir", str(lattice_dir), "--receipt", str(G2_RECEIPT), "--allow-g8-pure-a", "--run",
        "--decision", str(args.decision), "--stage-a", str(args.stage_a), "--rehearsal", str(args.rehearsal),
        "--anchor-receipt", str(anchor_receipt),
    ]
    anchor_command = _script("run_pull_v5_p1_anchor_probe.py") + [
        "--mode", "anchor", "--source", "natural", "--gpu", "4", "--anchor-attempt", str(attempt),
        "--output-dir", str(_anchor_dir), "--allow-g8-pure-a", "--run",
        "--decision", str(args.decision), "--stage-a", str(args.stage_a), "--rehearsal", str(args.rehearsal),
        "--receipt", str(anchor_receipt),
    ]
    records = [
        _command_record(name="t2_anchor_gpu4", gpu=4, command=anchor_command, output_dir=_anchor_dir,
                        consumes=(args.rehearsal,), produces=(anchor_receipt,)),
    ]
    for bucket, probe_receipt in zip(BUCKETS, probe_receipts):
        output = probe_receipt.parent
        probe = _script("run_pull_v5_p1_anchor_probe.py") + [
            "--mode", "probe", "--source", "canonical", "--gpu", "4", "--closer-bucket", bucket,
            "--anchor-attempt", str(attempt), "--anchor-receipt", str(anchor_receipt), "--output-dir", str(output),
            "--allow-g8-pure-a", "--run", "--decision", str(args.decision), "--stage-a", str(args.stage_a),
            "--rehearsal", str(args.rehearsal),
        ]
        records.append(_command_record(name=f"t2_probe_{bucket.replace('-', '_')}_gpu4", gpu=4, command=probe,
                                       output_dir=output, consumes=(anchor_receipt,), produces=(probe_receipt,)))
    records.extend([
        _command_record(
            name="t2_g1_gate", gpu=None, command=[], output_dir=GATE_ROOT,
            consumes=(*probe_receipts,), produces=(GATE_RECEIPT,),
        ),
        _command_record(
            name="t2_g2_lattice_gpu4", gpu=4, command=lattice_command, output_dir=lattice_dir,
            consumes=(*probe_receipts, anchor_receipt), produces=(G2_RECEIPT,),
        ),
    ])
    return records


def _t3_commands(args: argparse.Namespace, attempt: int) -> list[dict[str, Any]]:
    _anchor_dir, _generated_anchor_receipt, probe_receipts = _p1_paths(attempt)
    anchor_receipt = _current_anchor_receipt(args, attempt)
    records = []
    for cell, gpu in CELLS:
        output = TRAIN_ROOT / f"pull_{VERSION_TAG}_{cell}"
        command = _script("run_pull_v5_training.py") + [
            "--cell", cell, "--gpu", str(gpu), "--version", VERSION,
            "--allow-g8-pure-a", "--run",
            "--decision", str(args.decision), "--stage-a", str(args.stage_a),
            "--rehearsal", str(args.rehearsal), "--anchor-receipt", str(anchor_receipt), "--gate-receipt", str(GATE_RECEIPT),
        ]
        records.append(_command_record(
            name=f"pull_v5_4_p3_{cell}", gpu=gpu, command=command, output_dir=output,
            tmux_managed=True,
            consumes=(GATE_RECEIPT, anchor_receipt, *probe_receipts),
            produces=(output / "model_step_000250.pt",),
        ))
    return records


def _t4_commands(args: argparse.Namespace, attempt: int) -> list[dict[str, Any]]:
    anchor_receipt = _current_anchor_receipt(args, attempt)
    steps = (args.step,) if args.step is not None else CHECKPOINT_STEPS
    records: list[dict[str, Any]] = []
    for cell, gpu in CELLS:
        for step in steps:
            checkpoint = args.checkpoint_root.resolve() / f"pull_{VERSION_TAG}_{cell}/model_step_{step:06d}.pt"
            output = EVAL_ROOT / f"{VERSION_TAG}_{cell}_step{step}"
            command = _script("run_pull_v5_eval.py") + [
                "--checkpoint", str(checkpoint), "--cell", cell, "--step", str(step),
                "--gpu", str(gpu), "--version", VERSION, "--allow-g8-pure-a", "--run",
                "--decision", str(args.decision), "--stage-a", str(args.stage_a),
                "--rehearsal", str(args.rehearsal), "--anchor-receipt", str(anchor_receipt), "--gate-receipt", str(GATE_RECEIPT),
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
        "--decision", str(args.decision), "--stage-a", str(args.stage_a),
        "--rehearsal", str(args.rehearsal), "--anchor-receipt", str(anchor_receipt),
    ]
    records.append(_command_record(
        name="t4_analyze_v5_4", gpu=None, command=analysis_command, output_dir=ANALYSIS.parent,
        consumes=tuple(Path(product) for record in eval_records for product in record["produces"]),
        produces=(ANALYSIS,),
    ))
    return records


def _p4_commands(args: argparse.Namespace) -> list[dict[str, Any]]:
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
    anchor_receipt = _current_anchor_receipt(args, args.p1_attempt)
    records: list[dict[str, Any]] = []
    for index, ratio in enumerate(ratios):
        command, _env, output_dir = training.build_p4_command(
            cell=cell, gpu=gpu, checkpoint=checkpoint, ratio=float(ratio),
            additional_batches=args.p4_additional_batches, version=VERSION,
            anneal_index=index, allow_missing_checkpoint=True, allow_g8_pure_a=True,
            decision_path=args.decision, stage_a_path=args.stage_a,
            rehearsal_path=args.rehearsal, anchor_receipt=anchor_receipt, gate_receipt=GATE_RECEIPT,
        )
        produced = output_dir / f"model_step_{args.p4_additional_batches:06d}.pt"
        records.append(_command_record(
            name=f"pull_v5_4_p4_{cell}_r{str(ratio).replace('.', 'p')}", gpu=gpu,
            command=command, output_dir=output_dir, tmux_managed=True,
            consumes=(checkpoint,), produces=(produced,),
        ))
        checkpoint = produced
    return records


def phase_commands(args: argparse.Namespace) -> list[dict[str, Any]]:
    if args.phase == "T0":
        return _t0_commands()
    if args.phase == "T1":
        gates.require_chain("stage_a", decision_path=args.decision, stage_a_path=args.stage_a)
        return _t1_commands(args)
    if args.phase == "T2":
        gates.require_chain("rehearsal", decision_path=args.decision, stage_a_path=args.stage_a, rehearsal_path=args.rehearsal)
        return _t2_commands(args, args.p1_attempt)
    if args.phase == "T3":
        current_anchor = _current_anchor_receipt(args, args.p1_attempt)
        gates.require_chain("anchor", decision_path=args.decision, stage_a_path=args.stage_a, rehearsal_path=args.rehearsal, anchor_path=current_anchor)
        gates.validate_downstream_gate(GATE_RECEIPT, anchor_path=current_anchor)
        return _t3_commands(args, args.p1_attempt)
    if args.phase == "T4":
        current_anchor = _current_anchor_receipt(args, args.p1_attempt)
        gates.require_chain("anchor", decision_path=args.decision, stage_a_path=args.stage_a, rehearsal_path=args.rehearsal, anchor_path=current_anchor)
        gates.validate_downstream_gate(GATE_RECEIPT, anchor_path=current_anchor)
        return _t4_commands(args, args.p1_attempt)
    if args.phase == "P4":
        current_anchor = _current_anchor_receipt(args, args.p1_attempt)
        gates.require_chain("anchor", decision_path=args.decision, stage_a_path=args.stage_a, rehearsal_path=args.rehearsal, anchor_path=current_anchor)
        gates.validate_downstream_gate(GATE_RECEIPT, anchor_path=current_anchor)
        return _p4_commands(args)
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
        raise RuntimeError("v5.4 probe receipt requires bucket_sequence_records")
    requested_bucket = receipt.get("closer_bucket")
    if requested_bucket not in BUCKETS:
        raise RuntimeError(f"v5.4 probe receipt must identify one closer bucket; got {requested_bucket!r}")
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


def _write_gate(
    *,
    attempt: int,
    status: str,
    anchor_receipt: Path,
    probe_receipts: Sequence[Path],
    probe_passage: int,
    lattice_receipt: Path | None = None,
    lattice_passage: int | None = None,
) -> None:
    GATE_ROOT.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "a2_piper_pull_v5_4_gate_receipt_v1",
        "plan_id": "a2_piper_pull_v5_4_terminal_yaw_scheduler",
        "scientific_denominator_included": False,
        "denominator_scope": "none",
        "status": status,
        "p1_attempt": attempt,
        "probe_frame_passage": probe_passage,
        "lattice_frame_passage": lattice_passage,
        "training_gate": status in {"G1_PASS", "G2_PASS"},
        "all_zero_routes_to_g2": probe_passage == 0,
        "anchor_receipt_path": str(anchor_receipt.resolve()),
        "probe_receipt_paths": [str(path.resolve()) for path in probe_receipts],
        "lattice_receipt_path": None if lattice_receipt is None else str(lattice_receipt.resolve()),
    }
    GATE_RECEIPT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _run_wave(records: Sequence[Mapping[str, Any]]) -> None:
    processes: list[subprocess.Popen[bytes]] = []
    tmux_records: list[Mapping[str, Any]] = []
    for record in records:
        command = list(record["command"])
        if not command:
            continue
        env = os.environ.copy()
        if record.get("gpu") is not None:
            env["CUDA_VISIBLE_DEVICES"] = str(record["gpu"])
            env["ACCELERATE_TORCH_DEVICE"] = "cuda:0"
        name = str(record.get("name", ""))
        if record.get("tmux_managed") is True:
            tmux_command = list(record["tmux_command"])
            subprocess.run(tmux_command, cwd=ROOT, env=env, check=True)
            tmux_records.append(record)
        else:
            processes.append(subprocess.Popen(command, cwd=ROOT, env=env))
    statuses = [process.wait() for process in processes]
    if any(status != 0 for status in statuses):
        raise RuntimeError(f"workflow wave failed with return codes {statuses}")
    for record in tmux_records:
        name = str(record["name"])
        subprocess.run(["tmux", "wait-for", f"{name}.done"], cwd=ROOT, check=True)
        exit_path = Path(str(record["output_dir"])) / "tmux.exit"
        if not exit_path.is_file():
            raise RuntimeError(f"{name} exited without tmux status receipt: {exit_path}")
        status = int(exit_path.read_text(encoding="utf-8").strip())
        if status != 0:
            raise RuntimeError(f"workflow tmux session {name} failed with return code {status}")


def _run_t1(records: Sequence[Mapping[str, Any]], args: argparse.Namespace) -> None:
    _run_wave(records)
    rehearsal = Path(records[0]["produces"][0])
    gates.validate_rehearsal(rehearsal, stage_a_path=args.stage_a, decision_path=args.decision)


def _run_t2(records: Sequence[Mapping[str, Any]], attempt: int, args: argparse.Namespace) -> None:
    _anchor_dir, _generated_anchor_receipt, probe_receipts = _p1_paths(attempt)
    _anchor_receipt = _current_anchor_receipt(args, attempt)
    anchor_record = next(record for record in records if record["name"] == "t2_anchor_gpu4")
    _run_wave([anchor_record])
    gates.validate_anchor(
        _anchor_receipt,
        rehearsal_path=args.rehearsal,
        stage_a_path=args.stage_a,
        decision_path=args.decision,
    )
    passage = 0
    for record, path in zip((item for item in records if item["name"].startswith("t2_probe_")), probe_receipts):
        _run_wave([record])
        receipt = _require_schema(path, f"T2 probe {path.name}", "a2_piper_pull_v5_4_p1_receipt")
        if receipt.get("anchor_receipt_path") != str(_anchor_receipt.resolve()) or receipt.get("anchor_attempt") != attempt:
            raise RuntimeError(f"T2 probe {path.name} is stale or bound to a different anchor receipt")
        passage += _probe_passage(receipt)
    if passage > 0:
        _write_gate(
            attempt=attempt,
            status="G1_PASS",
            anchor_receipt=_anchor_receipt,
            probe_receipts=probe_receipts,
            probe_passage=passage,
        )
        return
    lattice_record = next(record for record in records if record["name"] == "t2_g2_lattice_gpu4")
    _run_wave([lattice_record])
    lattice_payload = _require_schema(G2_RECEIPT, "T2 G2 lattice", "a2_piper_pull_v5_4_p1_receipt")
    if lattice_payload.get("anchor_receipt_path") != str(_anchor_receipt.resolve()) or lattice_payload.get("anchor_attempt") != attempt:
        raise RuntimeError("T2 lattice receipt is stale or bound to a different anchor receipt")
    lattice_passage = int(lattice_payload.get("frame_passage_count", 0))
    _write_gate(
        attempt=attempt,
        status="G2_PASS" if lattice_passage > 0 else "G2_STOP",
        anchor_receipt=_anchor_receipt,
        probe_receipts=probe_receipts,
        probe_passage=passage,
        lattice_receipt=G2_RECEIPT,
        lattice_passage=lattice_passage,
    )


def _require_training_gate(anchor_receipt: Path) -> None:
    gates.validate_downstream_gate(GATE_RECEIPT, anchor_path=anchor_receipt)


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
    _run_wave([record for record in records if record["name"] == "t4_analyze_v5_4"])


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
        "schema": "a2_piper_pull_v5_4_orchestration_v1",
        "phase": args.phase,
        "phase_order": list(PHASES),
        "dependencies": {name: list(deps) for name, deps in PHASE_DEPENDENCIES.items()},
        "commands": records,
        "run": args.run,
        "gpu_scope": [4, 5, 6, 7],
        "t1_contract": {"stage_b_rehearsal_first": True, "gpu": 4, "num_envs": 8, "targets": [-2.5, 1.0]},
        "t2_contract": {"anchor_first": True, "gpu": 4, "rows_per_sequence": 16, "sequence_ids": list(SEQUENCES)},
        "t3_contract": {
            "g1_any_bucket_sequence_passage": True, "all_zero_routes_to": "G2_lattice", "g2_gpu": 4,
            "conditional": True, "cells": [f"{cell}:GPU{gpu}" for cell, gpu in CELLS],
            "num_envs": 256, "batches": 250, "save_frequency": 50,
        },
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
        current_anchor_path = _current_anchor_receipt(args, args.p1_attempt)
        receipt["v5_4_gate_paths"] = {
            "decision": str(args.decision.resolve()),
            "stage_a": str(args.stage_a.resolve()),
            "rehearsal": str(args.rehearsal.resolve()),
            "anchor": str(current_anchor_path.resolve()),
        }
    print(json.dumps(receipt, indent=2, sort_keys=True))
    if not args.run:
        return 0
    if args.phase == "T0":
        return 0
    if args.phase == "T1":
        _run_t1(records, args)
    elif args.phase == "T2":
        _run_t2(records, args.p1_attempt, args)
    elif args.phase == "T3":
        _require_training_gate(_current_anchor_receipt(args, args.p1_attempt))
        _run_wave(records)
    elif args.phase == "T4":
        _run_t4(records)
    elif args.phase == "P4":
        _run_p4(records)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
