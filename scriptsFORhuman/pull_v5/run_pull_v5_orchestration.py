#!/usr/bin/env python3
"""Fail-fast Pull-v5 phase orchestrator with explicit G1–G12 barriers."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent
PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
BANK = ROOT / "logs_rl/a2_piper_full_stage_a2_pull/pull_v5_state_bank/pull_v5_state_bank.pt"
BANK_RECEIPT = BANK.with_suffix(BANK.suffix + ".receipt.json")
ANALYSIS = SCRIPT_DIR / "PULL_V5_ANALYSIS.json"
CELLS = (("M_s0", 4), ("M_s1", 5), ("C_s0", 6), ("C_s1", 7))
P1_ROOT = ROOT / "logs_eval/a2_piper_pull_v5/p1_anchor_probe"
P2_RECEIPT = ROOT / "logs_eval/a2_piper_pull_v5/p2_intervention/P2_INTERVENTION_RECEIPT.json"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--phase",
        choices=("p0", "census", "state_bank", "p1", "p2", "p3", "eval", "analyze"),
        required=True,
    )
    parser.add_argument("--source-a", type=Path)
    parser.add_argument("--source-b", type=Path)
    parser.add_argument("--checkpoint-root", type=Path)
    parser.add_argument("--step", type=int, default=250)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--enforce-barriers", action="store_true")
    parser.add_argument("--allow-missing-runtime", action="store_true")
    return parser.parse_args()


def _barrier(path: Path, label: str) -> None:
    if not path.is_file():
        raise RuntimeError(f"barrier {label} requires {path}")


def _receipt_paths(pattern: str) -> list[Path]:
    return sorted(P1_ROOT.glob(pattern))


def _read_receipt(path: Path, *, schema_prefix: str, label: str) -> Mapping[str, Any]:
    if not path.is_file():
        raise RuntimeError(f"{label} receipt is missing: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping) or not isinstance(value.get("schema"), str) or not value["schema"].startswith(schema_prefix):
        raise RuntimeError(f"{label} receipt schema is invalid: {path}")
    if value.get("status") != "PASS":
        raise RuntimeError(f"{label} receipt status is not PASS: {path}")
    return value


def _find_single_receipt(pattern: str, *, schema_prefix: str, label: str) -> Mapping[str, Any]:
    paths = _receipt_paths(pattern)
    if len(paths) != 1:
        raise RuntimeError(f"{label} requires exactly one receipt matching {pattern}; found {paths}")
    return _read_receipt(paths[0], schema_prefix=schema_prefix, label=label)


def _gate_decision(args: argparse.Namespace) -> dict[str, Any]:
    """Evaluate G1/G2/G5/G6/G7/G11/G12 before any dependent launch."""

    decision: dict[str, Any] = {"gates": {}, "action": "proceed"}
    if args.phase in {"p3", "eval", "analyze"}:
        anchor = _find_single_receipt("anchor_*/*P1_anchor*RECEIPT.json", schema_prefix="a2_piper_pull_v5_p1_receipt", label="G3 anchor")
        decision["gates"]["G3"] = "PASS"
        if anchor.get("anchor_pass") is not True:
            raise RuntimeError("G3 failed: P1 anchor did not pass; P3 launch is refused.")
        probe_paths = _receipt_paths("probe_*/*P1_probe*RECEIPT.json")
        if len(probe_paths) != 1:
            raise RuntimeError("G1 requires exactly one P1 probe receipt after the anchor.")
        if probe_paths:
            probe = _read_receipt(probe_paths[0], schema_prefix="a2_piper_pull_v5_p1_receipt", label="G1 probe")
            decision["gates"]["G1"] = "PASS" if int(probe.get("frame_passage_count", 0)) > 0 else "ZERO"
            if int(probe.get("frame_passage_count", 0)) == 0:
                lattice_paths = _receipt_paths("lattice_*/*P1_lattice*RECEIPT.json")
                if len(lattice_paths) != 1:
                    decision["gates"]["G2"] = "REQUIRED"
                    decision["action"] = "run_lattice_then_resume"
                else:
                    lattice = _read_receipt(lattice_paths[0], schema_prefix="a2_piper_pull_v5_p1_receipt", label="G2 lattice")
                    if lattice.get("interface_feasible") is False:
                        raise RuntimeError("G2 interface is infeasible; dependent P3 launch is refused.")
                    if int(lattice.get("lattice_state_count", 0)) < 20 or int(lattice.get("lattice_state_count", 0)) > 50:
                        raise RuntimeError("G2 lattice must contain 20-50 command states.")
                    decision["gates"]["G2"] = "PASS"
            else:
                decision["gates"]["G2"] = "NOT_REQUIRED"
        p2 = _read_receipt(P2_RECEIPT, schema_prefix="a2_piper_pull_v5_p2_receipt", label="G4 P2")
        decision["gates"]["G4"] = "PASS"
        if p2.get("intervention", {}).get("episodes", 0) == 0:
            raise RuntimeError("G7 has no P2 intervention episodes; dependent P3 launch is refused.")
    if args.phase == "analyze" and ANALYSIS.is_file():
        analysis = json.loads(ANALYSIS.read_text(encoding="utf-8"))
        if not isinstance(analysis, Mapping) or analysis.get("status") not in {"PASS", "FAIL"}:
            raise RuntimeError("G5 analysis receipt/verdict is invalid.")
        if analysis.get("timeout") is True:
            decision["gates"]["G11"] = "TIMEOUT_MINIMAL_P0_P1_P2_REPORT"
            decision["action"] = "stop_report"
            return decision
        canonical = analysis.get("sources", {}).get("canonical_bank", {}).get("frame_passage_rate")
        natural = analysis.get("sources", {}).get("natural", {}).get("frame_passage_rate")
        if canonical is None or natural is None:
            raise RuntimeError("G5 analysis lacks canonical/natural frame-passage rates.")
        if canonical > 0 and natural > 0:
            decision["gates"]["G5"] = "PASS_STOPPING_CONDITION"
        elif canonical > 0 and natural == 0:
            decision["gates"]["G6"] = "ANNEAL_CONTINUATION"
        elif canonical == 0 and natural == 0:
            decision["gates"]["G7"] = "FORK_REQUIRED"
            decision["action"] = "stop_report_fork"
        else:
            decision["gates"]["G12"] = "NATURAL_DEGRADATION_BIAS_M_NO_REGULARIZATION"
    return decision


def _commands(args: argparse.Namespace) -> list[list[str]]:
    def script(name: str) -> tuple[str, str]:
        return str(PYTHON), str(SCRIPT_DIR / name)
    phase = args.phase
    if phase == "p0":
        return [list(script("run_pull_v5_census.py")) + ["--variant", "v4_B", "--seed", "0", "--gpu", "4"]]
    if phase == "census":
        return [list(script("run_pull_v5_census.py")) + ["--variant", "v4_B", "--seed", "0", "--gpu", "4"]]
    if phase == "state_bank":
        if args.source_a is None or args.source_b is None:
            raise ValueError("state_bank requires --source-a and --source-b")
        return [list(script("build_pull_v5_state_bank.py")) + ["--source-a", str(args.source_a), "--source-b", str(args.source_b), "--output", str(BANK)]]
    if phase == "p1":
        base = list(script("run_pull_v5_p1_anchor_probe.py"))
        return [
            base + ["--mode", "anchor", "--source", "canonical", "--gpu", "4", "--anchor-attempt", "1"],
            base + ["--mode", "probe", "--source", "canonical", "--gpu", "4"],
        ]
    if phase == "p2":
        return [list(script("run_pull_v5_p2_intervention.py")) + ["--gpu", "5"]]
    if phase == "p3":
        return [
            list(script("run_pull_v5_training.py")) + ["--cell", cell, "--gpu", str(gpu)]
            for cell, gpu in CELLS
        ]
    if phase == "eval":
        if args.checkpoint_root is None:
            raise ValueError("eval requires --checkpoint-root pointing at the four cell directories")
        commands = []
        for index, (cell, gpu) in enumerate(CELLS):
            checkpoint = args.checkpoint_root / cell / f"model_step_{args.step:06d}.pt"
            commands.append(list(script("run_pull_v5_eval.py")) + [
                "--checkpoint", str(checkpoint), "--cell", cell, "--step", str(args.step), "--gpu", str(gpu)
            ])
        return commands
    if phase == "analyze":
        return [list(script("analyze_pull_v5.py")) + ["--input-root", str(ROOT / "logs_eval/a2_piper_pull_v5"), "--output", str(ANALYSIS)]]
    raise AssertionError(phase)


def _check_barriers(args: argparse.Namespace) -> None:
    if not args.enforce_barriers:
        return
    if args.phase in {"p1", "p2", "p3", "eval", "analyze"}:
        _barrier(BANK, "G1/state-bank")
        _read_receipt(BANK_RECEIPT, schema_prefix="a2_piper_pull_v5_state_bank_v1", label="G1/state-bank")
    if args.phase in {"p2", "p3", "eval", "analyze"}:
        _find_single_receipt("anchor_*/*P1_anchor*RECEIPT.json", schema_prefix="a2_piper_pull_v5_p1_receipt", label="G3/P1-anchor")
    if args.phase in {"p3", "eval", "analyze"}:
        _read_receipt(P2_RECEIPT, schema_prefix="a2_piper_pull_v5_p2_receipt", label="G4/P2-intervention")
    if args.phase == "analyze":
        for cell, _gpu in CELLS:
            _barrier(ROOT / "logs_eval/a2_piper_pull_v5" / f"{cell}_step{args.step}_canonical/eval/metrics_eval.json", f"G5/{cell}")


def main() -> int:
    args = _parse_args()
    _check_barriers(args)
    decision = _gate_decision(args) if args.enforce_barriers else {"gates": {}, "action": "proceed"}
    commands = _commands(args)
    print(json.dumps({
        "schema": "a2_piper_pull_v5_orchestration_v1",
        "phase": args.phase,
        "barriers": [f"G{i}" for i in range(1, 13)],
        "commands": [" ".join(command) for command in commands],
        "run": args.run,
        "gate_decision": decision,
    }, indent=2))
    if not args.run:
        return 0
    if args.phase == "p3" and decision.get("action") == "run_lattice_then_resume":
        lattice_command = [
            str(PYTHON), str(SCRIPT_DIR / "run_pull_v5_p1_anchor_probe.py"),
            "--mode", "lattice", "--source", "canonical", "--gpu", "4", "--run",
        ]
        lattice_result = subprocess.run(lattice_command, cwd=ROOT, check=False)
        if lattice_result.returncode != 0:
            raise SystemExit(lattice_result.returncode)
        decision = _gate_decision(args)
        if decision.get("action") != "proceed":
            raise RuntimeError(f"G2 did not clear after lattice: {decision}")
    for command in commands:
        no_run_flag = args.phase in {"state_bank", "analyze"}
        run_command = command if no_run_flag or "--run" in command else command + ["--run"]
        result = subprocess.run(run_command, cwd=ROOT, check=False)
        if result.returncode != 0:
            raise SystemExit(result.returncode)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
