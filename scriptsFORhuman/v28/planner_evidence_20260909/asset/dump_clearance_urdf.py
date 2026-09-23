import xml.etree.ElementTree as ET, os
os.chdir("/home/baoquanc/workspace/DoorDog-A2-Piper-v13-student-distillation-20260717_2103/camera_setup/Vpiper-Plate-Dual-D435i")
for p in ("robot/a2_piper_U3_F0_clearance_only.urdf", "robot/a2_piper_U3_F15_clearance_only.urdf", "robot/a2_piper_U3_F0_camera_visuals.urdf"):
    r = ET.parse(p).getroot()
    print("==", p, "links", len(r.findall('link')), "joints", len(r.findall('joint')))
    for l in r.findall('link'):
        if l.get('name') in ('trunk', 'arm_body6_to_gripper'):
            for c in l.findall('collision'):
                o = c.find('origin'); g = list(c.find('geometry'))[0]
                print(f"  {l.get('name')} collision name={c.get('name')} origin={o.attrib if o is not None else None} {g.tag} {g.attrib}")
            for v in l.findall('visual'):
                o = v.find('origin'); g = list(v.find('geometry'))[0]
                if g.tag != 'mesh':
                    print(f"  {l.get('name')} visual name={v.get('name')} origin={o.attrib if o is not None else None} {g.tag} {g.attrib}")
    for j in r.findall('joint'):
        if j.get('name') in ('dd_wrist_M_fixed', 'dd_base_left_M_fixed', 'dd_base_right_M_fixed'):
            print("  ", j.get('name'), j.find('parent').get('link'), '->', j.find('child').get('link'), j.find('origin').attrib)
print("\n=== README.md head ===")
with open("README.md", encoding="utf-8") as f:
    for i, line in enumerate(f):
        if i > 140: break
        print(line.rstrip()[:220])
print("\n=== config dir ===")
for root, dirs, files in os.walk("config"):
    for fn in files:
        print(os.path.join(root, fn))
