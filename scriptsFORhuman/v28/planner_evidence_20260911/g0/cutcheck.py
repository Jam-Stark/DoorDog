import numpy as np, xml.etree.ElementTree as ET, os
from scipy.spatial.transform import Rotation as Rt
import trimesh
def T(xyz,rpy):
    m=np.eye(4); m[:3,:3]=Rt.from_euler("xyz",rpy).as_matrix(); m[:3,3]=xyz; return m
def shapes(urdf, linkname):
    root=ET.parse(urdf).getroot(); base=os.path.dirname(urdf); out=[]
    for l in root.findall("link"):
        if l.get("name")!=linkname: continue
        for c in l.findall("collision"):
            o=c.find("origin"); xyz=[float(x) for x in (o.get("xyz") if o is not None else "0 0 0").split()]
            rpy=[float(x) for x in ((o.get("rpy","0 0 0")) if o is not None else "0 0 0").split()]
            g=list(c.find("geometry"))[0]
            if g.tag=="box":
                s=np.array([float(x) for x in g.get("size").split()])
                gg=np.array(np.meshgrid([-.5,.5],[-.5,.5],[-.5,.5])).reshape(3,-1).T*s
            else:
                mesh=trimesh.load(os.path.join(base,g.get("filename")),force="mesh")
                sc=g.get("scale"); v=mesh.vertices*(np.array([float(x) for x in sc.split()]) if sc else 1.0)
                gg=np.asarray(v)
            M=T(xyz,rpy); out.append((c.get("name"), (M[:3,:3]@gg.T).T+M[:3,3]))
    return out
def jointT(urdf, child):
    root=ET.parse(urdf).getroot()
    for j in root.findall("joint"):
        if j.find("child").get("link")==child:
            o=j.find("origin")
            return T([float(x) for x in o.get("xyz").split()],[float(x) for x in o.get("rpy","0 0 0").split()]), j.find("parent").get("link")
    return None,None
for name in ["a2_piper_vpiper_final_20260906","a2_piper_v28_cut_20260909"]:
    u=f"gr00t/rl/data/robots/{name}/a2_piper.urdf"
    print("###",name)
    tk=shapes(u,"trunk")
    zmax=max(p[:,2].max() for _,p in tk)
    print("  trunk collision z range: [%.5f, %.5f], #shapes=%d"%(min(p[:,2].min() for _,p in tk), zmax, len(tk)))
    for lk in ("vpiper_main","vpiper_support"):
        M,par=jointT(u,lk)
        sh=shapes(u,lk)
        if not sh: print("   ",lk,"no collisions"); continue
        allp=np.vstack([(M[:3,:3]@p.T).T+M[:3,3] for _,p in sh])
        print("   %s (parent %s): #shapes=%d z range in trunk frame [%.5f, %.5f]"%(lk,par,len(sh),allp[:,2].min(),allp[:,2].max()))
    # per-trunk-shape z top, list those above 0.130
    hi=[(n,p[:,2].max()) for n,p in tk if p[:,2].max()>0.1295]
    print("  trunk shapes with top z>0.1295:",[(n,round(z,5)) for n,z in hi])
