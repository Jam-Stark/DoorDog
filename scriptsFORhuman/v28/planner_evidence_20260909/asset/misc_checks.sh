#!/bin/bash
cd /home/baoquanc/workspace/DoorDog-A2_Piper
echo "=== .isaacsim_version ==="; cat gr00t/rl/simulator/isaacsim/.isaacsim_version; echo
echo "=== tests/scripts referencing asset paths or num_bodies ==="
rg -n "A2_Piper/a2_piper|a2_piper\.usd|a2_piper\.urdf|num_bodies|a2_piper_vpiper" gr00t/rl/tests gr00t/rl/scripts scripts 2>/dev/null | head -40
echo "=== isaacsim.py version import lines ==="
sed -n '80,95p;140,150p' gr00t/rl/simulator/isaacsim/isaacsim.py
echo "=== IsaacLab articulation body ordering ==="
rg -n "link_names|def body_names|def find_bodies|shared_metatype" /home/baoquanc/workspace/IsaacLab/source/isaaclab/isaaclab/assets/articulation/articulation.py | head -20
echo "=== IsaacLab urdf importer joint collision / self collision handling ==="
rg -n "collisionEnabled|collision_enabled|enabledSelfCollisions|set_self_collision" /home/baoquanc/workspace/IsaacLab/source/isaaclab/isaaclab/sim/converters/urdf_converter.py | head
echo "=== tilt param in camera bundle config ==="
cd /home/baoquanc/workspace/DoorDog-A2-Piper-v13-student-distillation-20260717_2103/camera_setup/Vpiper-Plate-Dual-D435i
python3 - <<'EOF'
import json
for p in ("config/U3_F0.json","config/U3_F15.json"):
    d=json.load(open(p))
    print("==",p, "top keys:", list(d.keys())[:30])
    def walk(o,pre=""):
        if isinstance(o,dict):
            for k,v in o.items():
                if any(s in k.lower() for s in ("tilt","pitch","upright","tower","height","plan","posture","joint","reference")):
                    if not isinstance(v,(dict,list)) or len(json.dumps(v))<300: print("  ",pre+k,"=",json.dumps(v)[:300])
                walk(v,pre+k+".")
    walk(d)
EOF
echo "=== reference_joint_pose.json ==="; cat config/reference_joint_pose.json | head -40
echo "=== code dir ==="; ls code | head -30
