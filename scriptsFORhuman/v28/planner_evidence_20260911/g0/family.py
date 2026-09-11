import numpy as np, xml.etree.ElementTree as ET
from scipy.spatial.transform import Rotation as R
U="gr00t/rl/data/robots/a2_piper_v28_cut_20260909/a2_piper.urdf"
root=ET.parse(U).getroot()
tower=[l for l in root.findall("link") if l.get("name")=="wrist_camera_tower"][0]
B={}
for c in tower.findall("collision"):
    o=c.find("origin"); p=np.array([float(x) for x in o.get("xyz").split()])
    rot=R.from_euler("xyz",[float(x) for x in o.get("rpy").split()])
    s=np.array([float(x) for x in c.find("geometry").find("box").get("size").split()])
    B[c.get("name")]=(p,rot,s)
sp,sr,ss=B["v28_wrist_camera_support_collision"]; hp,hr,hs=B["v28_wrist_housing_collision"]
def corners(p,rot,s,n=5):
    g=np.linspace(-.5,.5,n); o=np.array(np.meshgrid(g,g,g)).reshape(3,-1).T*s
    return rot.apply(o)+p
def variant(h_mm,theta):
    y=np.sqrt((h_mm/1000)**2-hp[0]**2-hp[2]**2); hp2=np.array([hp[0],y,hp[2]])
    hr2=hr*R.from_euler("y",np.radians(theta-45.0))
    drop=(180-h_mm)/1000; L2=ss[2]-drop; sp2=sp-sr.apply([0,0,drop/2])
    return np.vstack([corners(sp2,sr,np.array([ss[0],ss[1],L2])),corners(hp2,hr2,hs)])
sets={f"h{h}_t{t}":variant(h,t) for h,t in ((180,45.0),(140,38.76),(120,34.49),(100,29.13))}
# express in support frame
for k,pts in sets.items():
    loc=sr.inv().apply(pts-sp)
    print(k, "support-frame extents mm: x[%.2f,%.2f] y[%.2f,%.2f] z[%.2f,%.2f]"%tuple(
        np.round(np.concatenate([[loc[:,i].min()*1000,loc[:,i].max()*1000] for i in range(3)]),2)))
for label,keys in (("180 only",["h180_t45.0"]),("140-180",["h180_t45.0","h140_t38.76"]),
                   ("120-180",["h180_t45.0","h140_t38.76","h120_t34.49"]),
                   ("100-180",list(sets))):
    loc=np.vstack([sr.inv().apply(sets[k]-sp) for k in keys])
    lo,hi=loc.min(0)*1000,loc.max(0)*1000
    size=hi-lo; ctr=(hi+lo)/2
    print(f"{label}: single support-aligned box size mm {np.round(size,2)} centre(in support frame) mm {np.round(ctr,2)}  volume ratio vs 180-only box "
          f"{np.prod(size):.0f}")
