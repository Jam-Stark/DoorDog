"""Build the v29 MERGED H180/F45 asset from the retained v28 source asset.

Run with the installed Isaac Sim USD Python libraries (see README.md).
"""
from pathlib import Path
import copy
import json
import shutil
import sys
import xml.etree.ElementTree as ET

import numpy as np
from scipy.spatial.transform import Rotation
from pxr import Gf, Usd, UsdGeom, UsdPhysics

REPO = Path(__file__).resolve().parents[2]
SOURCE = REPO / "gr00t/rl/data/robots/a2_piper_v28_merged_20260909"
ASSET = REPO / "gr00t/rl/data/robots/a2_piper_v29_merged_20260917"
sys.path.insert(0, str(REPO / "scriptsFORhuman/v28"))
from v28_camera_geometry import simplify_wrist_support, serial
from v28_build_asset import add_geometry, add_tower_inertial

HOUSING_VISUALS = {
    "trunk": ["v28_base_left_housing_visual", "v28_base_right_housing_visual"],
    "wrist_camera_tower": ["v28_wrist_housing_visual"],
}


def remove_central_usd_envelope(asset):
    removals = {
        "a2_piper.usd": ["/a2_piper/trunk/visuals/v28_base_center_housing_visual"],
        "configuration/a2_piper_base.usd": ["/visuals/trunk/v28_base_center_housing_visual",
                                             "/colliders/trunk/v28_base_center_housing_collision"],
        "configuration/a2_piper_physics.usd": ["/colliders/trunk/v28_base_center_housing_collision"],
    }
    for layer, paths in removals.items():
        stage = Usd.Stage.Open(str(asset / layer))
        for path in paths:
            stage.RemovePrim(path)
        stage.GetRootLayer().Save()


def main():
    rig = json.loads((SOURCE / "config/camera_rig.json").read_text())
    old = json.loads((REPO / "scriptsFORhuman/v28/camera/U3_F45_B15.json").read_text())
    camera = copy.deepcopy(next(c for c in old["cameras"] if c["name"] == "wrist"))
    rig["cameras"] = [camera if c["name"] == "wrist" else c for c in rig["cameras"]]
    rig = serial(simplify_wrist_support(rig))
    rig["plan_id"] = "U3_F45_H180_V29"
    rig["name_cn"] = "v29 MERGED 腕机180mm/45度，外壳视觉盒隐藏"
    rig["design_revision"]["reference_down_pitch_B_deg"] = 45.0
    rig["design_revision"]["reference_forward_axis_B"] = old["design_revision"]["reference_forward_axis_B"]
    rig["wrist_tower_contract"]["centre_height_from_flange_m"] = 0.180
    rig["wrist_tower_contract"]["theta_deg"] = 45.0
    rig["wrist_support_model"]["decision"] = "V29-D003: H180/F45, D19 cross section and D20 1mm mounting clearance"
    rig["wrist_support_model"]["clearance_status"] = "D20_1MM_STATIC_CONVEX_CLEARANCE_SOLVED_FOR_F45_H180"
    del rig["trunk_envelope_housings"]
    rig["mass_and_collision"] = "Trunk inertial is the MERGED sum of trunk, vpiper_main, vpiper_support and metal_plate_5mm. Base housing boxes have no separate mass contribution. The central envelope visual/collision is removed. Wrist tower mass/inertia is recomputed from its support and housing for H180/F45."
    rig["v29_default_arm_pose_rad"] = [0.0, 0.10, -0.10, 0.0, -0.52, 1.57]
    rig["housing_visuals"] = {"visible": False, "names_by_link": HOUSING_VISUALS,
                              "collision_and_mass_retained": True, "supports_visible": True}
    support = next(b for b in rig["brackets"] if b["parent"] == "arm_body6_to_gripper")
    mass_support = 0.075 * support["size_m"][2] / 0.11470001524266443
    parts = [(support["T_parent_item"], support["size_m"], mass_support),
             (camera["T_parent_M"], rig["housing_size_M_m"], 0.075)]

    ASSET.mkdir()
    shutil.copytree(SOURCE / "configuration", ASSET / "configuration")
    shutil.copytree(SOURCE / "meshes", ASSET / "meshes")
    shutil.copy2(SOURCE / "a2_piper.usd", ASSET / "a2_piper.usd")
    remove_central_usd_envelope(ASSET)
    (ASSET / "config").mkdir()
    (ASSET / "config/camera_rig.json").write_text(json.dumps(rig, ensure_ascii=False, indent=2) + "\n")
    tree = ET.parse(SOURCE / "a2_piper.urdf")
    root = tree.getroot()
    trunk = root.find("link[@name='trunk']")
    for category in ("visual", "collision"):
        trunk.remove(trunk.find(f"{category}[@name='v28_base_center_housing_{category}']"))
    tower = root.find("link[@name='wrist_camera_tower']")
    for element in list(tower):
        tower.remove(element)
    add_geometry(tower, name="v28_wrist_camera_support", transform=parts[0][0], size=parts[0][1])
    add_geometry(tower, name="v28_wrist_housing", transform=parts[1][0], size=parts[1][1])
    add_tower_inertial(tower, parts)
    for link_name, names in HOUSING_VISUALS.items():
        link = root.find(f"link[@name='{link_name}']")
        for name in names:
            link.remove(link.find(f"visual[@name='{name}']"))
    tree.write(ASSET / "a2_piper.urdf", encoding="utf-8", xml_declaration=True)

    stage = Usd.Stage.Open(str(ASSET / "a2_piper.usd"))
    stage.SetEditTarget(stage.GetRootLayer())
    tower_path = "/a2_piper/wrist_camera_tower"
    for category, suffix in [("visuals", "visual"), ("collisions", "collision")]:
        stage.GetPrimAtPath(f"{tower_path}/{category}").SetInstanceable(False)
        for name, (transform, size, _) in zip(("v28_wrist_camera_support", "v28_wrist_housing"), parts):
            prim = stage.GetPrimAtPath(f"{tower_path}/{category}/{name}_{suffix}")
            t = np.asarray(transform)
            q = Rotation.from_matrix(t[:3, :3]).as_quat()
            for attr_name, values in [("xformOp:translate", t[:3, 3]), ("xformOp:scale", size)]:
                attr = prim.GetAttribute(attr_name)
                attr.Set(type(attr.Get())(*[float(x) for x in values]))
            attr = prim.GetAttribute("xformOp:orient")
            old_q = attr.Get()
            attr.Set(type(old_q)(float(q[3]), type(old_q.GetImaginary())(*[float(x) for x in q[:3]])))
            # The source importer uses a unit cube before applying the size transform.
            cube = stage.GetPrimAtPath(str(prim.GetPath()) + "/box")
            cube.GetAttribute("extent").Set([Gf.Vec3f(-0.5), Gf.Vec3f(0.5)])
    for link_name, names in HOUSING_VISUALS.items():
        stage.GetPrimAtPath(f"/a2_piper/{link_name}/visuals").SetInstanceable(False)
        for name in names:
            prim = stage.GetPrimAtPath(f"/a2_piper/{link_name}/visuals/{name}")
            UsdGeom.Imageable(prim).MakeInvisible()

    inertial = tower.find("inertial")
    com = np.fromstring(inertial.find("origin").get("xyz"), sep=" ")
    fields = inertial.find("inertia").attrib
    matrix = np.array([[float(fields["i" + "".join(sorted((a, b)))]) for b in "xyz"] for a in "xyz"])
    values, axes = np.linalg.eigh(matrix)
    if np.linalg.det(axes) < 0:
        axes[:, 0] *= -1
    q = Rotation.from_matrix(axes).as_quat()
    api = UsdPhysics.MassAPI(stage.GetPrimAtPath(tower_path))
    api.GetMassAttr().Set(float(inertial.find("mass").get("value")))
    api.GetCenterOfMassAttr().Set(Gf.Vec3f(*[float(x) for x in com]))
    api.GetDiagonalInertiaAttr().Set(Gf.Vec3f(*[float(x) for x in values]))
    api.GetPrincipalAxesAttr().Set(Gf.Quatf(float(q[3]), Gf.Vec3f(*[float(x) for x in q[:3]])))
    stage.GetRootLayer().Save()

    report = {"source_asset": str(SOURCE.relative_to(REPO)), "asset": str(ASSET.relative_to(REPO)),
              "method": "Reuse MERGED layers; replace wrist geometry and mass; hide only housing visuals",
              "height_m": 0.180, "tilt_deg": 45.0, "support_length_m": support["size_m"][2],
              "static_mount_clearance_m": rig["wrist_support_model"]["actual_static_clearance_m"],
              "tower_mass_kg": float(api.GetMassAttr().Get()), "tower_com_m": com.tolist(),
              "tower_inertia_kgm2": matrix.tolist(), "hidden_housing_visuals": HOUSING_VISUALS,
              "central_envelope_removed": True,
              "central_envelope_mass_contribution_kg": 0.0,
              "rigid_body_count": sum(p.HasAPI(UsdPhysics.RigidBodyAPI) for p in stage.Traverse()),
              "evidence": "CPU asset construction; no policy-quality or hardware claim"}
    (ASSET / "config/asset_build.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
