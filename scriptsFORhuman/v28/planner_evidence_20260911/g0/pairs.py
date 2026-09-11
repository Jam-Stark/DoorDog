import numpy as np, xml.etree.ElementTree as ET, os, json, itertools
from scipy.spatial.transform import Rotation as R
from scipy.spatial import ConvexHull
from scipy.optimize import linprog, minimize
import trimesh
def T(xyz,rpy):
    m=np.eye(4); m[:3,:3]=R.from_euler("xyz",rpy).as_matrix(); m[:3,3]=xyz; return m
def parse(urdf):
    root=ET.parse(urdf).getroot(); base=os.path.dirname(urdf); links={}; joints={}
    for l in root.findall("link"):
        cols=[]
        for i,c in enumerate(l.findall("collision")):
            o=c.find("origin"); xyz=[float(x) for x in (o.get("xyz") if o is not None else "0 0 0").split()]
            rpy=[float(x) for x in ((o.get("rpy","0 0 0")) if o is not None else "0 0 0").split()]
            g=list(c.find("geometry"))[0]
            if g.tag=="box":
                s=[float(x)/2 for x in g.get("size").split()]
                v=np.array([[i2*s[0],j2*s[1],k2*s[2]] for i2 in(-1,1) for j2 in(-1,1) for k2 in(-1,1)])
            elif g.tag=="cylinder":
                r_=float(g.get("radius")); h_=float(g.get("length"))/2
                a=np.linspace(0,2*np.pi,24,endpoint=False)
                v=np.array([[r_*np.cos(t),r_*np.sin(t),z] for t in a for z in (-h_,h_)])
            elif g.tag=="sphere":
                v=np.asarray(trimesh.creation.icosphere(subdivisions=2,radius=float(g.get("radius"))).vertices,float)
            else:
                m=trimesh.load(os.path.join(base,g.get("filename")),force="mesh"); v=np.asarray(m.vertices,float)
                sc=g.get("scale")
                if sc: v=v*np.array([float(x) for x in sc.split()])
            M=T(xyz,rpy); cols.append((c.get("name") or f"{l.get('name')}#{i}", (M[:3,:3]@v.T).T+M[:3,3]))
        links[l.get("name")]=cols
    for j in root.findall("joint"):
        o=j.find("origin")
        joints[j.get("name")]=dict(parent=j.find("parent").get("link"),child=j.find("child").get("link"),
                                   T=T([float(x) for x in o.get("xyz").split()],[float(x) for x in o.get("rpy","0 0 0").split()]))
    return links,joints
def fk(joints,root="trunk"):
    Tw={root:np.eye(4)}; ch={}
    for n,j in joints.items(): ch.setdefault(j["parent"],[]).append(n)
    st=[root]
    while st:
        p=st.pop()
        for jn in ch.get(p,[]):
            Tw[joints[jn]["child"]]=Tw[p]@joints[jn]["T"]; st.append(joints[jn]["child"])
    return Tw
class H:
    def __init__(s,n,p):
        h=ConvexHull(p); s.name=n; s.v=p[h.vertices]; eq=h.equations
        nr=np.linalg.norm(eq[:,:3],axis=1,keepdims=True); s.A=eq[:,:3]/nr; s.b=-eq[:,3:4]/nr
        s.c=s.v.mean(0); s.r=np.linalg.norm(s.v-s.c,axis=1).max()
def depth(a,b):
    A=np.vstack([np.hstack([a.A,np.ones((len(a.A),1))]),np.hstack([b.A,np.ones((len(b.A),1))])])
    bb=np.vstack([a.b,b.b]).ravel()
    r=linprog(c=[0,0,0,-1],A_ub=A,b_ub=bb,bounds=[(None,None)]*3+[(-1.,1.)],method="highs")
    return float(r.x[3]) if r.status==0 else None
def dist(a,b):
    z0=np.concatenate([a.c,b.c])
    cons=[{"type":"ineq","fun":lambda z,A=a.A,bv=a.b:(bv.ravel()-A@z[:3])},
          {"type":"ineq","fun":lambda z,A=b.A,bv=b.b:(bv.ravel()-A@z[3:])}]
    r=minimize(lambda z:np.sum((z[:3]-z[3:])**2),z0,constraints=cons,method="SLSQP",
               options={"maxiter":400,"ftol":1e-14})
    return float(np.sqrt(max(r.fun,0.0)))
for name in ["a2_piper_vpiper_final_20260906","a2_piper_v28_cut_20260909"]:
    u=f"gr00t/rl/data/robots/{name}/a2_piper.urdf"
    links,joints=parse(u); Tw=fk(joints)
    def hulls(lk):
        M=Tw[lk]; return [H(n,(M[:3,:3]@p.T).T+M[:3,3]) for n,p in links[lk]]
    trunk=hulls("trunk"); out=[]
    for other in ("vpiper_main","vpiper_support","metal_plate_5mm"):
        if other not in links or not links[other]: continue
        for a in trunk:
            for b in hulls(other):
                if np.linalg.norm(a.c-b.c) > a.r+b.r+0.02: continue
                d=depth(a,b)
                if d is not None and d>1e-9: out.append((other,a.name,b.name,"OVERLAP",-d))
                else: out.append((other,a.name,b.name,"sep",dist(a,b)))
    out.sort(key=lambda x:x[4])
    print("###",name,"  screened pairs:",len(out))
    for row in out[:6]: print("   %-16s %-34s %-40s %-8s %+.5f m"%row)
