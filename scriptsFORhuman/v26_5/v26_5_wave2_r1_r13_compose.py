#!/usr/bin/env python3
"""Compose the r13 selector halves without allocating Isaac/GPU."""
from __future__ import annotations
import argparse
from pathlib import Path
from typing import Any
import yaml

ROOT=Path(__file__).resolve().parents[2]; CONFIG_ROOT=ROOT/"gr00t/rl/config"
def merge(left:dict[str,Any],right:dict[str,Any])->dict[str,Any]:
    out=dict(left)
    for key,value in right.items(): out[key]=merge(out[key],value) if isinstance(value,dict) and isinstance(out.get(key),dict) else value
    return out
def compose(path:Path)->dict[str,Any]:
    value=yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value,dict): raise RuntimeError(f"config is not mapping: {path}")
    out={}
    for entry in value.get("defaults",[]):
        if entry=="_self_": continue
        if isinstance(entry,str) and entry.startswith("/"): target=CONFIG_ROOT/f"{entry[1:]}.yaml"
        elif isinstance(entry,dict) and len(entry)==1:
            key,target_name=next(iter(entry.items()))
            if not isinstance(key,str) or not isinstance(target_name,str): raise RuntimeError(f"unsupported default: {entry!r}")
            prefix=key.removeprefix("override /").removeprefix("/");target=CONFIG_ROOT/f"{prefix}/{target_name}.yaml"
        else: raise RuntimeError(f"unsupported default: {entry!r}")
        out=merge(out,compose(target))
    value.pop("defaults",None);return merge(out,value)
def main()->None:
    p=argparse.ArgumentParser();p.add_argument("--output-dir",type=Path,required=True);a=p.parse_args()
    if a.output_dir.exists():raise RuntimeError(f"refusing to overwrite r13 selector root: {a.output_dir}")
    a.output_dir.mkdir(parents=True)
    for name in ("train","eval"):
        selector=CONFIG_ROOT/f"ablation/wbmanip/base_v26_5_wave2_R13_{'policy_residual' if name=='train' else 'eval_policy_residual'}.yaml"
        a.output_dir.joinpath(f"R13_{name}_selector.yaml").write_text(yaml.safe_dump(compose(selector),sort_keys=True),encoding="utf-8")
    print(a.output_dir)
if __name__=="__main__":main()
