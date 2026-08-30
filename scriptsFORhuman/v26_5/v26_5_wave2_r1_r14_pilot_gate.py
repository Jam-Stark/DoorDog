#!/usr/bin/env python3
import argparse,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument("--reducer",type=Path,required=True);a=p.parse_args();v=json.loads(a.reducer.read_text())
if v.get("typed_outcome")!="R14_RESEED_PILOT_ADMITTED" or v.get("pass") is not True:raise RuntimeError("r14 K1 requires admitted pilot reducer")
print(a.reducer)
