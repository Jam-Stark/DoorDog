#!/usr/bin/env python3
"""Compose fresh R15 selectors without Isaac allocation."""
from __future__ import annotations
import argparse
from pathlib import Path
from v26_5_wave2_r1_r13_compose import compose
ROOT=Path(__file__).resolve().parents[2];CONFIG=ROOT/"gr00t/rl/config/ablation/wbmanip"
def main():
 p=argparse.ArgumentParser();p.add_argument("--output-dir",type=Path,required=True);a=p.parse_args()
 if a.output_dir.exists():raise RuntimeError(f"refusing R15 selector overwrite: {a.output_dir}")
 a.output_dir.mkdir(parents=True)
 import yaml
 for name,file in (("train","base_v26_5_wave2_R15_policy_residual.yaml"),("eval","base_v26_5_wave2_R15_eval_policy_residual.yaml")):
  a.output_dir.joinpath(f"R15_{name}_selector.yaml").write_text(yaml.safe_dump(compose(CONFIG/file),sort_keys=True),encoding="utf-8")
 print(a.output_dir)
if __name__=="__main__":main()
