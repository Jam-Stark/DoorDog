#!/usr/bin/env python3
"""Apply the frozen G2 premise gate to a fresh Wave-B reducer result."""
from __future__ import annotations
import argparse, json
from pathlib import Path

CELLS = ("B0_S0", "B0_S1", "B1_S0", "B1_S1")

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--waveb-reducer", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise RuntimeError(f"refusing to overwrite G2 result: {args.output}")
    source = json.loads(args.waveb_reducer.read_text(encoding="utf-8"))
    if source.get("status") != "EXPERIMENT_COMPLETE" or source.get("failures"):
        raise RuntimeError("G2 requires a completed valid v26-6 Wave-B reducer result")
    endpoint = {}
    for cell in CELLS:
        row = source.get("endpoint_gates", {}).get(cell, {}).get("durable_depression", {})
        value = row.get("left")
        if not isinstance(value, int):
            raise RuntimeError(f"G2 reducer missing endpoint LEFT durable depression for {cell}")
        endpoint[cell] = value
    challenged = {cell: value for cell, value in endpoint.items() if value > 0}
    status = "V26_7_PREMISE_CHALLENGED" if challenged else "G2_PASS"
    payload = {"schema": "a2_piper_base_v26_7_g2_premise_gate_v1", "status": status, "waveb_reducer": str(args.waveb_reducer), "endpoint_left_durable_depression": endpoint, "challenged_cells": challenged}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "output": str(args.output), "challenged_cells": challenged}))
    return 0 if not challenged else 2

if __name__ == "__main__":
    raise SystemExit(main())
