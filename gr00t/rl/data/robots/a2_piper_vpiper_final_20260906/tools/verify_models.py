#!/usr/bin/env python3
"""Static URDF/MJCF geometry and FK checks. Optional genuine MuJoCo compile/FK check.

Static validation does not replace a simulator import or hardware measurement.
With --mujoco, the command fails rather than claiming success if MuJoCo is absent.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, sys
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
from scipy.spatial.transform import Rotation
import trimesh


def semantic(el):
    return (el.tag,sorted(el.attrib.items()),[semantic(x) for x in el])

def vec(s, default='0 0 0'):return np.fromstring(s if s is not None else default,sep=' ')

def transform(xyz=None,rpy=None,quat=None):
    M=np.eye(4)
    if xyz is not None:M[:3,3]=vec(xyz)
    if quat is not None:
        q=vec(quat);M[:3,:3]=Rotation.from_quat(q[[1,2,3,0]]).as_matrix()
    elif rpy is not None:M[:3,:3]=Rotation.from_euler('xyz',vec(rpy)).as_matrix()
    return M

def jmotion(kind,axis,q):
    axis=axis/np.linalg.norm(axis);T=np.eye(4)
    if kind in ['revolute','continuous','hinge']:T[:3,:3]=Rotation.from_rotvec(axis*q).as_matrix()
    elif kind in ['prismatic','slide']:T[:3,3]=axis*q
    else:raise ValueError(kind)
    return T

def urdf_tree(path):
    r=ET.parse(path).getroot();links={n.get('name'):n for n in r.findall('link')}
    if len(links)!=len(r.findall('link')):raise ValueError('Duplicate link')
    joints=r.findall('joint');names=[j.get('name') for j in joints]
    if len(names)!=len(set(names)):raise ValueError('Duplicate joint')
    by_parent={n:[] for n in links};parented=set()
    for j in joints:
        p=j.find('parent').get('link');c=j.find('child').get('link')
        assert p in links and c in links and c not in parented
        parented.add(c);by_parent[p].append(j)
    roots=set(links)-parented;assert roots=={'trunk'}
    def fk(q):
        poses={}
        def recurse(n,T):
            assert n not in poses, 'Cycle'
            poses[n]=T
            for j in by_parent[n]:
                o=j.find('origin');C=T@transform(o.get('xyz'),o.get('rpy'))
                if j.get('type')!='fixed':C=C@jmotion(j.get('type'),vec(j.find('axis').get('xyz')),q.get(j.get('name'),0))
                recurse(j.find('child').get('link'),C)
        recurse('trunk',np.eye(4));assert len(poses)==len(links)
        return poses
    fk({})
    return r,links,joints,fk

def mjcf_fk(root,q):
    poses={}
    def recurse(b,T):
        C=T@transform(b.get('pos'),quat=b.get('quat','1 0 0 0'))
        for j in b.findall('joint'):
            assert np.allclose(vec(j.get('pos')),0)
            C=C@jmotion(j.get('type','hinge'),vec(j.get('axis','0 0 1')),q.get(j.get('name'),0))
        poses[b.get('name')]=C
        for ch in b.findall('body'):recurse(ch,C)
    for b in root.findall('worldbody/body'):recurse(b,np.eye(4))
    return poses

def inertia_matrix(el):
    a={k:float(v) for k,v in el.attrib.items()}
    return np.array([[a['ixx'],a['ixy'],a['ixz']],[a['ixy'],a['iyy'],a['iyz']],[a['ixz'],a['iyz'],a['izz']]])

def top_z_at_xy(tri,xy):
    a,b,c=tri[:,0],tri[:,1],tri[:,2];x,y=xy
    den=(b[:,1]-c[:,1])*(a[:,0]-c[:,0])+(c[:,0]-b[:,0])*(a[:,1]-c[:,1])
    valid=np.abs(den)>1e-18;ii=np.where(valid)[0];a,b,c=a[valid],b[valid],c[valid];den=den[valid]
    u=((b[:,1]-c[:,1])*(x-c[:,0])+(c[:,0]-b[:,0])*(y-c[:,1]))/den
    v=((c[:,1]-a[:,1])*(x-c[:,0])+(a[:,0]-c[:,0])*(y-c[:,1]))/den
    w=1-u-v;inside=(u>=-1e-10)&(v>=-1e-10)&(w>=-1e-10)
    z=(u*a[:,2]+v*b[:,2]+w*c[:,2])[inside]
    return float(z.max()) if len(z) else None

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--package',type=Path,default=Path(__file__).resolve().parents[1])
    ap.add_argument('--mujoco',action='store_true',help='Actually compile and evaluate FK with an installed MuJoCo')
    args=ap.parse_args();p=args.package.resolve()
    cfg=json.loads((p/'config/mount_parameters.json').read_text());audit=json.loads((p/'validation/final_geometry_audit.json').read_text())
    old,oldlinks,oldjoints,oldfk=urdf_tree(p/'source/a2_piper_original.urdf')
    oj={j.get('name'):j for j in oldjoints};moving=[j for j in oldjoints if j.get('type')!='fixed']
    rng=np.random.default_rng(20260906);qs=[{}]
    for _ in range(256):qs.append({j.get('name'):float(rng.uniform(float(j.find('limit').get('lower')),float(j.find('limit').get('upper')))) for j in moving})
    result={'status':'STATIC_PASS','scope':'geometry, tree, source-preservation and independently evaluated URDF/MJCF FK; NOT dynamics or hardware validation',
            'random_seed':20260906,'fk_configurations_per_variant':len(qs),'variants':{},
            'mujoco_engine_compile':'NOT_RUN: engine unavailable in delivery environment; optional --mujoco performs a real check',
            'isaac_import':'NOT_RUN','physical_assembly_measurement':'NOT_RUN','new_component_masses':'UNKNOWN / OMITTED'}
    if args.mujoco:
        try:import mujoco
        except ImportError:raise SystemExit('MuJoCo is not installed. No engine validation was performed.')
        result['mujoco_version']=mujoco.__version__
    for stem,pose in [('a2_piper',cfg['primary_arm_origin_B_m'])]:
        r,links,joints,fk=urdf_tree(p/(stem+'.urdf'));jmap={j.get('name'):j for j in joints}
        assert len(links)==30 and len(joints)==29
        assert jmap['arm_j0'].find('parent').get('link')=='trunk'
        assert len([j for j in joints if j.get('type')!='fixed'])==20
        for n,j in oj.items():
            if n=='arm_j0':continue
            assert semantic(j)==semantic(jmap[n]),f'Changed original joint {n}'
        preserved_inertia=0
        for n,l in oldlinks.items():
            # Element whitespace was re-indented; compare numeric attributes and geometry paths.
            for xp in ['inertial/origin','inertial/mass','inertial/inertia']:
                assert l.find(xp).attrib==links[n].find(xp).attrib,(n,xp)
            preserved_inertia+=1
            for tag in ['visual','collision']:
                src=l.findall(tag);dst=links[n].findall(tag);assert len(src)==len(dst)
                for a,b in zip(src,dst):
                    assert a.find('origin').attrib==b.find('origin').attrib
                    assert list(a.find('geometry'))[0].attrib==list(b.find('geometry'))[0].attrib
        for n in ['vpiper_main','vpiper_support','metal_plate_5mm']:assert links[n].find('inertial') is None
        for l in links.values():
            I=l.find('inertial/inertia')
            if I is not None:
                ev=np.linalg.eigvalsh(inertia_matrix(I));assert ev.min()>0 and ev.max()<=ev.sum()-ev.max()+1e-12
        mesh_refs=[m.get('filename') for m in r.findall('.//mesh')]
        assert all((p/f).is_file() for f in mesh_refs)
        delta=np.array(pose)-[.145,0,.154]
        mj=ET.parse(p/(stem+'.xml')).getroot()
        # Required opt-outs from automatic mass inference and fixed-body elimination.
        comp=mj.find('compiler');assert comp.get('inertiafromgeom')=='false' and comp.get('fusestatic')=='false'
        assert mj.tag=='mujoco' and len(mj.findall('.//actuator/motor'))==20
        mesh_names={m.get('name') for m in mj.findall('asset/mesh')}
        assert all((p/m.get('file')).is_file() for m in mj.findall('asset/mesh'))
        for g in mj.findall('.//geom'):
            if g.get('type')=='mesh':assert g.get('mesh') in mesh_names
        newfkerr=rot_err=mjerr=0.
        for q in qs:
            a,b=oldfk(q),fk(q);c=mjcf_fk(mj,q)
            for n in oldlinks:
                expected=delta if n.startswith('arm_body') else np.zeros(3)
                newfkerr=max(newfkerr,float(np.max(np.abs((b[n][:3,3]-a[n][:3,3])-expected))))
                rot_err=max(rot_err,float(np.max(np.abs(b[n][:3,:3]-a[n][:3,:3]))))
            for n in links:mjerr=max(mjerr,float(np.max(np.abs(b[n]-c[n]))))
        assert newfkerr<1e-10 and rot_err<1e-10 and mjerr<1e-10
        body=fk({})['arm_body0'];assert np.allclose(body[:3,3],pose,atol=1e-11)
        plate=fk({})['metal_plate_5mm']
        gap=body[2,3]+audit['stack']['piper_original_bottom_local_z_mm']/1000-(plate[2,3]+.005)
        assert abs(gap)<1e-11
        mass=sum(float(l.find('inertial/mass').get('value')) for l in links.values() if l.find('inertial/mass') is not None)
        assert abs(mass-44.741)<1e-10
        v={'links':len(links),'joints':len(joints),'actuated_joints':20,'original_inertias_preserved':preserved_inertia,
           'all_mesh_paths_exist':True,'mesh_reference_count':len(mesh_refs),
           'net_arm_origin_B_m':body[:3,3].tolist(),'arm_origin_delta_vs_old_B_mm':(delta*1000).tolist(),
           'fk_translation_invariant_max_error_m':newfkerr,'fk_orientation_max_matrix_error':rot_err,
           'urdf_vs_mjcf_fk_max_matrix_error':mjerr,'piper_to_plate_contact_plane_gap_m':gap,
           'retained_source_mass_kg':mass,'added_mass_kg_in_nominal_model':0,'added_actual_mass_kg':None}
        if args.mujoco:
            model=mujoco.MjModel.from_xml_path(str(p/(stem+'.xml')));data=mujoco.MjData(model);err=0
            for q in qs:
                data.qpos[:]=model.qpos0
                for n,x in q.items():data.qpos[model.jnt_qposadr[model.joint(n).id]]=x
                mujoco.mj_forward(model,data)
                for n,T in fk(q).items():
                    bid=model.body(n).id
                    err=max(err,float(np.max(np.abs(data.xpos[bid]-T[:3,3]))),float(np.max(np.abs(data.xmat[bid].reshape(3,3)-T[:3,:3]))))
            assert err<1e-8
            v['mujoco_compile']='PASS';v['mujoco_fk_error']=err
        result['variants'][stem]=v
    # CAD/STL contact-plane check at rail support points. No photographic metrology.
    tri=trimesh.load(p/'meshes/trunk.STL',process=False).triangles
    rail=[]
    for x in [24,48,82,94]:
        for y in [-110,-102,102,110]:
            z=top_z_at_xy(tri,(x/1000,y/1000));assert z is not None
            gap=audit['stack']['vpiper_lower_foot_plane_B_z_mm']-z*1000
            rail.append({'x_B_mm':x,'y_B_mm':y,'trunk_top_mesh_z_mm':z*1000,'vpiper_foot_gap_mm':gap})
    with (p/'validation/trunk_rail_contact_samples.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rail[0]));w.writeheader();w.writerows(rail)
    result['rail_contact_sample_count']=len(rail)
    result['rail_contact_max_abs_gap_mm']=max(abs(r['vpiper_foot_gap_mm']) for r in rail)
    assert result['rail_contact_max_abs_gap_mm']<.01
    for n in ['vpiper_main','vpiper_support','metal_plate_5mm_head_width']:
        f=p/'meshes/mount'/(n+('_visual' if n.startswith('vpiper') else '')+'.stl')
        m=trimesh.load(f);assert m.extents.max()<.5 and m.extents.max()>.04
    plate=trimesh.load(p/'meshes/mount/metal_plate_5mm_head_width.stl')
    assert np.max(np.abs(plate.extents-np.array(cfg['plate_size_m'])))<2e-8
    result['plate_STL_extents_mm']=(plate.extents*1000).tolist()
    if args.mujoco:result['mujoco_engine_compile']='PASS (actual engine compilation and FK, no time-stepping)'
    out=p/'validation'/('engine_validation.json' if args.mujoco else 'static_validation.json')
    out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__':main()
