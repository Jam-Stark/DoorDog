import xml.etree.ElementTree as ET, json, sys
OLD="/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/data/robots/A2_Piper/a2_piper.urdf"
NEW="/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/data/robots/a2_piper_vpiper_final_20260906/a2_piper.urdf"
def f(s): return [float(x) for x in s.split()]
def parse(p):
    r=ET.parse(p).getroot()
    links={}
    for l in r.findall('link'):
        d={'inertial':None,'collision':[],'visual':[]}
        i=l.find('inertial')
        if i is not None:
            o=i.find('origin')
            d['inertial']={'xyz':f(o.get('xyz')) if o is not None else [0,0,0],'rpy':f(o.get('rpy','0 0 0')) if o is not None else [0,0,0],
                           'mass':float(i.find('mass').get('value')),
                           'I':{k:float(v) for k,v in i.find('inertia').attrib.items()}}
        for tag in ('collision','visual'):
            for c in l.findall(tag):
                o=c.find('origin'); g=list(c.find('geometry'))[0]
                d[tag].append({'xyz':f(o.get('xyz')) if o is not None else [0,0,0],'rpy':f(o.get('rpy','0 0 0')) if o is not None else [0,0,0],'geom':g.tag,'attr':dict(g.attrib)})
        links[l.get('name')]=d
    joints={}
    for j in r.findall('joint'):
        o=j.find('origin'); ax=j.find('axis'); lim=j.find('limit'); dyn=j.find('dynamics')
        joints[j.get('name')]={'type':j.get('type'),'parent':j.find('parent').get('link'),'child':j.find('child').get('link'),
            'xyz':f(o.get('xyz')) if o is not None else [0,0,0],'rpy':f(o.get('rpy','0 0 0')) if o is not None else [0,0,0],
            'axis':f(ax.get('xyz')) if ax is not None else None,
            'limit':{k:float(v) for k,v in lim.attrib.items()} if lim is not None else None,
            'dynamics':{k:float(v) for k,v in dyn.attrib.items()} if dyn is not None else None}
    return links,joints
lo,jo=parse(OLD); ln,jn=parse(NEW)
print("links old/new:",len(lo),len(ln)," joints old/new:",len(jo),len(jn))
print("links only in new:",sorted(set(ln)-set(lo)))
print("links only in old:",sorted(set(lo)-set(ln)))
print("joints only in new:",sorted(set(jn)-set(jo)))
def close(a,b,tol=1e-12):
    if isinstance(a,dict): return set(a)==set(b) and all(close(a[k],b[k],tol) for k in a)
    if isinstance(a,list): return len(a)==len(b) and all(close(x,y,tol) for x,y in zip(a,b))
    if isinstance(a,float) or isinstance(b,float): return abs(float(a)-float(b))<=tol
    return a==b
diffs=[]
for n in lo:
    for k in ('inertial','collision','visual'):
        if not close(lo[n][k],ln[n][k]): diffs.append(('link',n,k,lo[n][k],ln[n][k]))
for n in jo:
    for k in jo[n]:
        if not close(jo[n][k],jn[n][k]): diffs.append(('joint',n,k,jo[n][k],jn[n][k]))
print("\nDIFFS on shared links/joints:")
for d in diffs: print(" ",d[:3],"\n     old:",d[3],"\n     new:",d[4])
tot_old=sum(l['inertial']['mass'] for l in lo.values() if l['inertial'])
tot_new=sum(l['inertial']['mass'] for l in ln.values() if l['inertial'])
print(f"\ntotal mass old={tot_old:.9f} new={tot_new:.9f} delta={tot_new-tot_old:.9f}")
print("\nMASS TABLE (shared links):")
for n in ['trunk','FL_hip','FL_thigh','FL_calf','FL_foot','RL_hip','RL_thigh','RL_calf','RL_foot','FR_hip','FR_thigh','FR_calf','FR_foot','RR_hip','RR_thigh','RR_calf','RR_foot','arm_body0','arm_body1','arm_body2','arm_body3','arm_body4','arm_body5','arm_body6','arm_body6_to_gripper','arm_body7','arm_body8']:
    a=lo[n]['inertial']; b=ln[n]['inertial']
    print(f"  {n:22s} old m={a['mass'] if a else None} new m={b['mass'] if b else None} identical={close(a,b)}")
print("\nNEW LINKS:")
for n in sorted(set(ln)-set(lo)):
    i=ln[n]['inertial']; print(f"  {n}: mass={i['mass']:.9f} com={i['xyz']} I={i['I']} ncollision={len(ln[n]['collision'])} coll_types={sorted(set(c['geom'] for c in ln[n]['collision']))}")
json.dump({'diffs':[list(map(str,d)) for d in diffs]},open('/tmp/v28_team/asset/urdf_diffs.json','w'),indent=1)
