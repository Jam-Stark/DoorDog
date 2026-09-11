"""Read the composed v28 USD through the installed Isaac Sim runtime."""
import argparse
import json
from pathlib import Path

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--usd", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--expected-bodies", type=int, required=True)
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()
app = AppLauncher(args).app

from pxr import Usd, UsdPhysics

try:
    stage = Usd.Stage.Open(str(args.usd.resolve()))
    bodies = [prim for prim in stage.Traverse() if prim.HasAPI(UsdPhysics.RigidBodyAPI)]
    joints = [prim.GetName() for prim in stage.Traverse()
              if prim.IsA(UsdPhysics.RevoluteJoint) or prim.IsA(UsdPhysics.PrismaticJoint)]
    components = {}
    for prim in bodies:
        mass = UsdPhysics.MassAPI(prim)
        components[prim.GetName()] = {
            "mass_kg": float(mass.GetMassAttr().Get()),
            "COM_link_m": list(mass.GetCenterOfMassAttr().Get()),
            "diagonal_inertia_kgm2": list(mass.GetDiagonalInertiaAttr().Get()),
            "principal_axes_wxyz": [float(mass.GetPrincipalAxesAttr().Get().GetReal()),
                                    *list(mass.GetPrincipalAxesAttr().Get().GetImaginary())],
        }
    if len(bodies) != args.expected_bodies or len(joints) != 20 or "wrist_camera_tower" not in components:
        raise ValueError(f"v28 USD must have {args.expected_bodies} rigid bodies, 20 active joints and the wrist tower")
    report = {"evidence":"STATIC_PASS: composed USD readback; no physics stepping",
              "conversion":"local IsaacLab convert_urdf.py; floating root; fixed joints retained; PD gains zero",
              "rigid_body_count":len(bodies),"active_joint_count":len(joints),
              "body_names":[prim.GetName() for prim in bodies],"joint_names":joints,
              "components":components,
              "relative_dependencies":[str(Path(layer.realPath).relative_to(args.usd.resolve().parent))
                                       for layer in stage.GetUsedLayers() if layer.realPath],
              "real_cad_validation":"NOT_RUN: wrist bracket not designed; Owner authorizes simulation envelopes"}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+"\n")
    print(f"STATIC_PASS: {len(bodies)} bodies, {len(joints)} joints")
finally:
    app.close()
