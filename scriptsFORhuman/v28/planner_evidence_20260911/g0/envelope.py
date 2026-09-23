import numpy as np, xml.etree.ElementTree as ET
from scipy.spatial.transform import Rotation as R
U="gr00t/rl/data/robots/a2_piper_v28_cut_20260909/a2_piper.urdf"
root=ET.parse(U).getroot()
tower=[l for l in root.findall("link") if l.get("name")=="wrist_camera_tower"][0]
boxes={}
for c in tower.findall("collision"):
    o=c.find("origin"); xyz=np.array([float(x) for x in o.get("xyz").split()])
    rpy=[float(x) for x in o.get("rpy").split()]
    size=np.array([float(x) for x in c.find("geometry").find("box").get("size").split()])
    boxes[c.get("name")]=(xyz,R.from_euler("xyz",rpy),size)
for k,(p,r,s) in boxes.items():
    print(k,"origin_mm",np.round(p*1000,4),"size_mm",np.round(s*1000,4),"|p|_mm",round(np.linalg.norm(p)*1000,4))
hc=boxes["v28_wrist_housing_collision"][0]; u=hc/np.linalg.norm(hc)
print("tower axis unit (flange frame):",np.round(u,6),"camera centre dist mm",round(np.linalg.norm(hc)*1000,4))
# axial coordinates of all 8 corners of each box + lateral distance from tower axis line
def corners(p,r,s):
    o=np.array(np.meshgrid([-.5,.5],[-.5,.5],[-.5,.5])).reshape(3,-1).T*s
    return (r.apply(o))+p
for k,(p,r,s) in boxes.items():
    C=corners(p,r,s); a=C@u; lat=np.linalg.norm(C-np.outer(a,u),axis=1)
    print(f"{k}: axial_mm [{a.min()*1000:.2f},{a.max()*1000:.2f}]  radial_max_mm {lat.max()*1000:.2f}")
# tilt-plane analysis: half extent of 25x25 square rotated by theta
for th in (45,38.76,34.49,29.13):
    t=np.radians(th); print(f"theta {th}: 25mm square half-extent in tilt plane = {12.5*(np.cos(t)+np.sin(t)):.2f} mm")
