#!/usr/bin/env python3
"""Compare four live O0/O1 target-sensor receipts into the Wave1 runtime contract."""

from __future__ import annotations
import argparse, json
from pathlib import Path

def load(path: Path) -> dict:
    value=json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema") != "a2_piper_base_v26_5_live_target_case_v1" or value.get("status") != "RUNTIME_COMPLETE":
        raise RuntimeError(f"invalid runtime case receipt: {path}")
    return value

def max_diff(a, b):
    if isinstance(a, list):
        if not isinstance(b, list) or len(a) != len(b): raise RuntimeError("target sensor shape mismatch")
        return max((max_diff(x,y) for x,y in zip(a,b,strict=True)), default=0.0)
    return abs(float(a)-float(b))

def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--case-root",type=Path,required=True); p.add_argument("--output",type=Path,required=True); a=p.parse_args()
    if a.output.exists(): raise RuntimeError(f"refusing to overwrite runtime contract: {a.output}")
    cases={(factor,side):load(a.case_root/f"{factor}_{side}.json") for factor in ("O0","O1") for side in ("left","right")}
    position_diffs={side:max_diff(cases[("O0",side)]["active_sensor_target_pos_w"],cases[("O1",side)]["active_sensor_target_pos_w"]) for side in ("left","right")}
    order_pass=all(value["target_frame_names"] == ["handle","pregrasp"] for value in cases.values())
    oracle_errors={side:max(float(x) for x in cases[("O1",side)]["O1_oracle_double_cover_component_error"]) for side in ("left","right")}
    if not order_pass or max(position_diffs.values()) > 1e-6 or max(oracle_errors.values()) > 2e-5: raise RuntimeError("Wave1 live target contract failed")
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps({"schema":"a2_piper_base_v26_5_runtime_target_contract_v1","status":"RUNTIME_PASS","readback":"full A2 env active OrderedTargetFrameTransformer","frame_order":["handle","pregrasp"],"O0_O1_position_max_abs_difference_m":position_diffs,"O1_geometry_oracle_double_cover_component_error":oracle_errors,"cases":{f"{f}_{s}":str((a.case_root/f"{f}_{s}.json").resolve()) for f,s in cases}},indent=2)+"\n",encoding="utf-8")
    print(a.output)
if __name__ == "__main__": main()
