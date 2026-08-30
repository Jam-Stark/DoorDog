#!/usr/bin/env python3
"""Fail closed before any r14 formal smoke/train/eval allocation."""
from __future__ import annotations
import argparse,json
from pathlib import Path
def main():
 p=argparse.ArgumentParser();p.add_argument("--reducer",type=Path,required=True)
 a=p.parse_args();v=json.loads(a.reducer.read_text());pairs=v.get("pairs",{})
 if v.get("typed_outcome")!="K1_R14_IDENTITY_ADMITTED" or set(pairs)!={"seed0_left","seed0_right","seed1_left","seed1_right"} or not all(x.get("pass") is True for x in pairs.values()):raise RuntimeError("r14 formal allocation requires four admitted K1 pairs")
 print(a.reducer)
if __name__=="__main__":main()
