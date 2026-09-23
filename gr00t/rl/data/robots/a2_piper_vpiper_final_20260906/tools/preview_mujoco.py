#!/usr/bin/env python3
"""Open an installed MuJoCo viewer at the inspection keyframe, WITHOUT mj_step."""
from pathlib import Path
import argparse,time

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--model',type=Path,default=Path(__file__).resolve().parents[1]/'scene.xml');a=ap.parse_args()
    if not a.model.is_file():ap.error(f'Missing model: {a.model}')
    try:import mujoco;import mujoco.viewer
    except ImportError:raise SystemExit('An installed MuJoCo is required. This script does not install dependencies.')
    model=mujoco.MjModel.from_xml_path(str(a.model.resolve()));data=mujoco.MjData(model)
    key=model.key('inspection_only').id;mujoco.mj_resetDataKeyframe(model,data,key);mujoco.mj_forward(model,data)
    with mujoco.viewer.launch_passive(model,data) as viewer:
        viewer.opt.geomgroup[3]=0
        while viewer.is_running():
            viewer.sync();time.sleep(.03)
if __name__=='__main__':main()
