#!/usr/bin/env python3
import argparse,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument("--reducer",type=Path,required=True);a=p.parse_args();v=json.loads(a.reducer.read_text())
if v.get("typed_outcome")!="R15_SHARED_O0_PILOT_ADMITTED" or v.get("pass") is not True:raise RuntimeError("R15 K1 requires admitted shared-O0 pilot reducer")
print(a.reducer)
