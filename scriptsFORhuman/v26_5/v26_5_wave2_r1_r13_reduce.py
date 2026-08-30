#!/usr/bin/env python3
"""Apply the unchanged r12 per-env K1 reducer gates to fresh r13 raw paths."""
from __future__ import annotations
import argparse,importlib.util,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/"scriptsFORhuman/v26_5/v26_5_wave2_r1_reduce.py"
def main()->None:
 p=argparse.ArgumentParser();p.add_argument("--eval-root",type=Path);p.add_argument("--output",type=Path);p.add_argument("--self-check",action="store_true");a=p.parse_args()
 if a.self_check:
  expected={f"seed{s}_{side}" for s in (0,1) for side in ("left","right")};passing={key:{"pass":True} for key in expected};killed=dict(passing);killed["seed1_right"]={"pass":False}
  if not all(x["pass"] for x in passing.values()) or all(x["pass"] for x in killed.values()):raise RuntimeError("r13 reducer synthetic admission logic")
  print("R13_REDUCER_SYNTHETIC_ADMISSION_GATE_PASS");return
 if a.eval_root is None or a.output is None:raise RuntimeError("r13 reducer requires --eval-root and --output")
 if a.output.exists():raise RuntimeError(f"refusing to overwrite r13 reducer: {a.output}")
 spec=importlib.util.spec_from_file_location("unchanged_r12_reducer",BASE);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 rows={f"seed{s}_{side}":module.k1_pair(module.runtime(a.eval_root/"K1"/"control"/f"K1_S{s}"/side),module.runtime(a.eval_root/"K1"/"dual"/f"K1_S{s}"/side),s,side) for s in (0,1) for side in module.SIDES}
 admitted=all(x["pass"] for x in rows.values());out={"schema":"a2_piper_base_v26_5_wave2_r13_k1_reducer_v1_unchanged_full_topology","status":"EXPERIMENT_COMPLETE","raw_input_root":str(a.eval_root/"K1"),"pairs":rows,"typed_outcome":"R13_CAUSAL_IDENTITY_ADMITTED" if admitted else "KILL_R13_IDENTITY_NOT_ADMITTED"}
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2,allow_nan=False)+"\n");print(a.output)
if __name__=="__main__":main()
