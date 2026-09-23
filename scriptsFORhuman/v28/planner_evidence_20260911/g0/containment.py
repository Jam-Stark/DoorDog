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
def inside(pt,p,rot,s,tol=0.0):
    l=rot.inv().apply(pt-p); return np.all(np.abs(l)<=s/2+tol)
def corners(p,rot,s,n=6):
    g=np.linspace(-.5,.5,n)
    o=np.array(np.meshgrid(g,g,g)).reshape(3,-1).T*s
    return rot.apply(o)+p
def maxviol(pts):
    # signed distance outside union of the two 180 boxes (approx: min over boxes of Linf-style slack)
    out=[]
    for pt in pts:
        best=1e9
        for (p,rot,s) in ((sp,sr,ss),(hp,hr,hs)):
            l=np.abs(rot.inv().apply(pt-p))-s/2
            best=min(best,max(l.max(),0.0))
        out.append(best)
    return np.array(out)
axis=hp/np.linalg.norm(hp)
print("support local-z vs tower axis angle deg:",np.degrees(np.arccos(abs(sr.apply([0,0,1])@axis))))
for h_mm,theta in ((180,45.0),(140,38.76),(120,34.49),(100,29.13)):
    # housing centre: keep x,z, scale so |p| = h
    y=np.sqrt((h_mm/1000)**2-hp[0]**2-hp[2]**2); hp2=np.array([hp[0],y,hp[2]])
    # housing rotation: same as current but tilt changed by (theta-45) about the image x axis (local x of housing box)
    dt=np.radians(theta-45.0)
    hr2=hr*R.from_euler("y",dt)
    # support: base face fixed, top face follows housing: shorten by the axial drop
    drop=(180-h_mm)/1000
    L2=ss[2]-drop; ss2=np.array([ss[0],ss[1],L2])
    sp2=sp-sr.apply([0,0,drop/2])
    pts=np.vstack([corners(sp2,sr,ss2),corners(hp2,hr2,hs)])
    v=maxviol(pts)
    print(f"h={h_mm}mm theta={theta}: support_len={L2*1000:.2f}mm  max_protrusion_outside_E180={v.max()*1000:.2f}mm  frac_pts_outside={np.mean(v>1e-9):.3f}")
# family bound: thicken support to 2*17.68 and extend axial span 54.59..197.68
print()
print("family bound proposal: 90 x 36 x 145 mm box, axial span 53..198 mm along tower axis")
for h_mm,theta in ((180,45.0),(140,38.76),(120,34.49),(100,29.13)):
    y=np.sqrt((h_mm/1000)**2-hp[0]**2-hp[2]**2); hp2=np.array([hp[0],y,hp[2]])
    dt=np.radians(theta-45.0); hr2=hr*R.from_euler("y",dt)
    drop=(180-h_mm)/1000; L2=ss[2]-drop; ss2=np.array([ss[0],ss[1],L2]); sp2=sp-sr.apply([0,0,drop/2])
    pts=np.vstack([corners(sp2,sr,ss2),corners(hp2,hr2,hs)])
    a=pts@axis; lat=pts-np.outer(a,axis)
    # decompose lateral into width dir (support local x) and thickness dir
    wdir=sr.apply([1,0,0]); wdir=wdir-(wdir@axis)*axis; wdir/=np.linalg.norm(wdir)
    tdir=np.cross(axis,wdir)
    print(f"h={h_mm}: axial [{a.min()*1000:.2f},{a.max()*1000:.2f}] width |.|max {np.abs(lat@wdir).max()*1000:.2f} thickness |.|max {np.abs(lat@tdir).max()*1000:.2f}")
