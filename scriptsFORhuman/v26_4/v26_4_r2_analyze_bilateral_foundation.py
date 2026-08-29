#!/usr/bin/env python3
"""Run the frozen R1 reducer only with admitted R2 gate and provenance."""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path, PosixPath

import yaml


POSIX_PATH_TAG = "tag:yaml.org,2002:python/object/apply:pathlib.PosixPath"


def construct_posix_path(loader: yaml.SafeLoader, node: yaml.SequenceNode) -> str:
    """Decode Hydra's serialized PosixPath into the plain path string reducer expects."""
    components = loader.construct_sequence(node, deep=True)
    return str(PosixPath(*components))


yaml.SafeLoader.add_constructor(POSIX_PATH_TAG, construct_posix_path)


def load(path: Path) -> dict:
    if not path.is_file():
        raise RuntimeError(f"required R2 provenance artifact is missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"R2 provenance artifact must be an object: {path}")
    return payload


def compile_r2_repaired_reducer(reducer: Path):
    """Apply only the R2 exposure and trace-completeness semantic repairs in memory."""
    tree = ast.parse(reducer.read_text(encoding="utf-8"), filename=str(reducer))
    class ApplyR2ReducerRepairs(ast.NodeTransformer):
        def __init__(self) -> None:
            self.inside_load_side = False
            self.removed_exposure_reconcile = 0
            self.replaced_trace_list_requirement = 0
            self.replaced_trace_coverage_requirement = 0

        def visit_FunctionDef(self, node: ast.FunctionDef):
            previous = self.inside_load_side
            self.inside_load_side = node.name == "load_side"
            result = self.generic_visit(node)
            self.inside_load_side = previous
            return result

        def visit_Expr(self, node: ast.Expr):
            call = node.value
            message = call.args[1] if isinstance(call, ast.Call) and len(call.args) == 2 else None
            fragments = "".join(
                value.value for value in message.values
                if isinstance(value, ast.Constant) and isinstance(value.value, str)
            ) if isinstance(message, ast.JoinedStr) else ""
            if (
                self.inside_load_side
                and isinstance(call, ast.Call)
                and isinstance(call.func, ast.Name)
                and call.func.id == "require"
                and "v26-3 highwater and v26-2 max handle disagree" in fragments
            ):
                self.removed_exposure_reconcile += 1
                return None
            if self.inside_load_side and "requires non-empty trace" in fragments:
                self.replaced_trace_list_requirement += 1
                return ast.parse(
                    'require(isinstance(trace, list), f"{path}: trace must be a list")'
                ).body[0]
            if self.inside_load_side and "trace does not cover exact64 first episodes" in fragments:
                self.replaced_trace_coverage_requirement += 1
                return ast.parse(
                    'require(set(trace_envs) == {row["env_id"] for row, max_stage_value in zip(terminal, max_stage, strict=True) if max_stage_value >= 2}, f"{path}: trace coverage does not match terminal Stage2-or-later env ids")'
                ).body[0]
            return self.generic_visit(node)

    transformer = ApplyR2ReducerRepairs()
    tree = transformer.visit(tree)
    if transformer.removed_exposure_reconcile != 1:
        raise RuntimeError(f"R2 overlay expected one exposure reconcile, removed {transformer.removed_exposure_reconcile}")
    if transformer.replaced_trace_list_requirement != 1:
        raise RuntimeError(f"R2 overlay expected one trace-list requirement, replaced {transformer.replaced_trace_list_requirement}")
    if transformer.replaced_trace_coverage_requirement != 1:
        raise RuntimeError(f"R2 overlay expected one trace-coverage requirement, replaced {transformer.replaced_trace_coverage_requirement}")
    return compile(ast.fix_missing_locations(tree), str(reducer), "exec")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gate", type=Path, required=True)
    parser.add_argument("--source-metadata", type=Path, required=True)
    parser.add_argument("--eval-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise RuntimeError(f"refusing to overwrite R2 reducer output: {args.output}")
    gate, metadata = load(args.gate), load(args.source_metadata)
    if gate.get("status") != "K_C_GATE_ADMITTED_READY_FOR_R2_RUNNER":
        raise RuntimeError("R2 reducer requires admitted K/C gate")
    if metadata.get("schema") != "a2_piper_base_v26_4_r2_source_metadata_v1" or metadata.get("status") != "SOURCE_METADATA_CAPTURED":
        raise RuntimeError("R2 reducer requires captured R2 source metadata")
    reducer = Path(__file__).with_name("v26_4_analyze_bilateral_foundation.py")
    original_argv = sys.argv
    sys.argv = [str(reducer), "--eval-root", str(args.eval_root), "--output", str(args.output)]
    try:
        exec(
            compile_r2_repaired_reducer(reducer),
            {"__name__": "__main__", "__file__": str(reducer), "__package__": None},
        )
    finally:
        sys.argv = original_argv
    payload = load(args.output)
    if payload.get("schema") != "a2_piper_base_v26_4_bilateral_foundation_v1" or payload.get("status") != "EXPERIMENT_COMPLETE":
        raise RuntimeError("frozen R1 reducer output schema/status mismatch")
    if not isinstance(payload.get("typed_outcome"), str) or not payload["typed_outcome"]:
        raise RuntimeError("frozen R1 reducer did not emit an R2 typed outcome")
    print(args.output)


if __name__ == "__main__":
    main()
