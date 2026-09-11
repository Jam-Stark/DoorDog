#!/usr/bin/env python3
"""Task 3: run the read-only v28 geometry precheck with a variant layout JSON and a new reset posture.
usage: t3_coverage.py <variant.json> <j5_rad> <out_dir>
Monkeypatches pc.CAM_JSON (layout) and pc.DEFAULT_ARM_Q (arm posture for the synthetic Stage0/1 sweep).
Stage2-5 replay uses the archived v27 traces (cells C_S2, C_S21) unchanged."""
import importlib.util, json, sys, time
from pathlib import Path
import numpy as np

SRC = Path('/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/v28_u3f0_geometry_precheck.py')
spec = importlib.util.spec_from_file_location('pc', SRC)
pc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pc)

variant, j5, out = Path(sys.argv[1]), float(sys.argv[2]), Path(sys.argv[3])
pc.CAM_JSON = variant
pc.DEFAULT_ARM_Q = np.array([0.0, 0.0, 0.0, 0.0, j5, 1.57])
t0 = time.time()
rep = pc.run(['C_S2', 'C_S21'], out)
rep['variant_json'] = str(variant)
rep['synthetic_arm_q'] = pc.DEFAULT_ARM_Q.tolist()
rep['runtime_s'] = time.time() - t0
(out / 'u3f0_geometry_precheck.json').write_text(json.dumps(rep, indent=1))
print(variant.name, 'j5', j5, 'done in', round(time.time() - t0), 's')
print(json.dumps(rep['fk_check_vs_csv_flange']))
