#!/usr/bin/env python3
"""Regenerate portable URDF and MJCF geometry models from the supplied source URDF.

No policy, gains, joint ranges, original inertias or gripper coupling are changed.
Added-component inertias use the documented uniform effective-density material estimate.
"""
from __future__ import annotations
import argparse, copy, csv, json
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
from scipy.spatial.transform import Rotation


def fmt(values) -> str:
    return ' '.join(f'{float(x):.12g}' for x in values)


def sub(parent, tag, **attrs):
    return ET.SubElement(parent, tag, {k: str(v) for k, v in attrs.items()})


def write_xml(root, path: Path) -> None:
    ET.indent(root, space='  ')
    ET.ElementTree(root).write(path, encoding='utf-8', xml_declaration=True)


def geometry_link(name, visual_mesh, rgba, collision_meshes=(), box=None, box_center=None):
    node=ET.Element('link', name=name)
    v=sub(node,'visual', name=name+'_visual')
    sub(v,'origin',xyz='0 0 0',rpy='0 0 0')
    g=sub(v,'geometry');sub(g,'mesh',filename=visual_mesh)
    m=sub(v,'material',name=name+'_material');sub(m,'color',rgba=rgba)
    for i,mesh in enumerate(collision_meshes):
        c=sub(node,'collision', name=f'{name}_collision_{i:02d}')
        sub(c,'origin',xyz='0 0 0',rpy='0 0 0');g=sub(c,'geometry');sub(g,'mesh',filename=mesh)
    if box is not None:
        c=sub(node,'collision',name=name+'_outer_envelope_collision')
        sub(c,'origin',xyz=fmt(box_center),rpy='0 0 0');g=sub(c,'geometry');sub(g,'box',size=fmt(box))
    return node


def fixed_joint(name, parent, child, xyz):
    j=ET.Element('joint',name=name,type='fixed')
    sub(j,'parent',link=parent);sub(j,'child',link=child)
    sub(j,'origin',xyz=fmt(xyz),rpy='0 0 0')
    return j


def build_urdf(package: Path, variant: str) -> ET.Element:
    cfg=json.loads((package/'config/mount_parameters.json').read_text())
    collisions=json.loads((package/'validation/mount_collision_decomposition.json').read_text())
    src=ET.parse(package/'source/a2_piper_original.urdf').getroot()
    src.insert(0,ET.Comment(' CAD-DERIVED MOUNT GEOMETRY; NOT AN AS-BUILT DYNAMICS CALIBRATION. See README.md. '))
    # Name otherwise anonymous materials, without modifying their supplied colors.
    for l in src.findall('link'):
        for i,m in enumerate(l.findall('visual/material')):
            if not m.get('name'):m.set('name',f'source_{l.get("name")}_{i}')
    with_collisions=variant!='visual_only'
    for name in ['vpiper_main','vpiper_support']:
        refs=[r['file'] for r in collisions[name]['parts']] if with_collisions else []
        src.append(geometry_link(name, f'meshes/mount/{name}_visual.stl',
                    '0.22 0.24 0.28 1' if name=='vpiper_main' else '0.37 0.39 0.43 1',refs))
    src.append(geometry_link('metal_plate_5mm','meshes/mount/metal_plate_5mm_head_width.stl',
                '0.13 0.14 0.16 1',box=cfg['plate_size_m'] if with_collisions else None,
                box_center=cfg['plate_center_in_plate_frame_m']))
    src.append(fixed_joint('trunk_to_vpiper','trunk','vpiper_main',cfg['vpiper_main_origin_B_m']))
    src.append(fixed_joint('vpiper_to_support','vpiper_main','vpiper_support',cfg['support_origin_in_main_m']))
    src.append(fixed_joint('vpiper_to_plate','vpiper_main','metal_plate_5mm',cfg['plate_origin_in_main_m']))
    arm=src.find("joint[@name='arm_j0']")
    # Retain the original parent/coordinate contract; mounting solids are welded siblings.
    arm.find('parent').set('link','trunk')
    origin=arm.find('origin');origin.attrib.clear()
    origin.set('xyz',fmt(cfg['primary_arm_origin_B_m']))
    origin.set('rpy','0 0 0')
    # Explicit URDF extension prevents MuJoCo from inventing a density for fixed mounts.
    ext=sub(src,'mujoco')
    sub(ext,'compiler',meshdir='.',strippath='false',discardvisual='false',fusestatic='false',inertiafromgeom='false')
    materials=json.loads((package/'config/mount_materials.json').read_text())
    geometry=json.loads((package/'config/mass_properties_to_complete.json').read_text())
    report={}
    for name,material in materials['components'].items():
        shape=geometry[name]
        mass=shape['volume_mm3']*1e-9*material['density_kg_m3']
        com=np.array(shape['center_of_volume_link_m'])
        inertia=np.array(shape['uniform_density_inertia_per_kg_about_com_B_kgm2_per_kg'])*mass
        link=src.find(f"link[@name='{name}']")
        inertial=sub(link,'inertial')
        sub(inertial,'origin',xyz=fmt(com),rpy='0 0 0')
        sub(inertial,'mass',value=mass)
        sub(inertial,'inertia',ixx=inertia[0,0],iyy=inertia[1,1],izz=inertia[2,2],
            ixy=inertia[0,1],ixz=inertia[0,2],iyz=inertia[1,2])
        report[name]={**material,'volume_mm3':shape['volume_mm3'],'mass_kg':mass,
            'COM_link_m':com.tolist(),'I_com_link_axes_kgm2':inertia.tolist()}
    added=sum(item['mass_kg'] for item in report.values())
    report={'method':materials['method'],'components':report,'added_total_mass_kg':added,
            'robot_total_mass_kg':sum(float(n.get('value')) for n in src.findall('link/inertial/mass'))}
    (package/'validation/mass_configuration.json').write_text(json.dumps(report,indent=2)+'\n')
    return src


def origin(el):
    if el is None:return np.zeros(3),np.array([1.,0,0,0])
    xyz=np.fromstring(el.get('xyz','0 0 0'),sep=' ')
    q=Rotation.from_euler('xyz',np.fromstring(el.get('rpy','0 0 0'),sep=' ')).as_quat()
    return xyz,q[[3,0,1,2]]


def inspection_pose(names):
    ans=[]
    for name in names:
        if 'thigh_joint' in name:x=.7
        elif 'calf_joint' in name:x=-1.4
        elif name=='arm_j2':x=.55
        elif name=='arm_j3':x=-1.1
        elif name=='arm_j5':x=.4
        elif name=='arm_j7':x=.02
        elif name=='arm_j8':x=-.02
        else:x=0.
        ans.append(x)
    return ans


def urdf_to_mjcf(urdf: ET.Element, package: Path, stem: str, floating=True):
    links={n.get('name'):n for n in urdf.findall('link')}
    children={n:[] for n in links}; childnames=set()
    for j in urdf.findall('joint'):
        children[j.find('parent').get('link')].append(j)
        childnames.add(j.find('child').get('link'))
    root_names=set(links)-childnames
    if root_names!={'trunk'}:raise ValueError(f'Unexpected roots: {root_names}')
    mj=ET.Element('mujoco',model=stem)
    mj.append(ET.Comment('Material-estimated mount inertias; no trained-policy or hardware dynamics validation.'))
    sub(mj,'compiler',angle='radian',autolimits='true',meshdir='.',strippath='false',
        inertiafromgeom='false',fusestatic='false',discardvisual='false',balanceinertia='false')
    # Gravity is conventional MJCF default; no source contact solver or controller is available.
    sub(mj,'option',gravity='0 0 -9.81')
    assets=sub(mj,'asset');assetnames={}
    def asset(mesh):
        key=(mesh.get('filename'),mesh.get('scale','1 1 1'))
        if key not in assetnames:
            name=f'mesh_{len(assetnames):03d}';assetnames[key]=name
            f=package/key[0]
            if not f.is_file():raise FileNotFoundError(f)
            sub(assets,'mesh',name=name,file=key[0],scale=key[1])
        return assetnames[key]
    world=sub(mj,'worldbody');ordered=[]
    def emit(link_name,parent,urdf_joint=None):
        at={'name':link_name}
        if urdf_joint is not None:
            xyz,q=origin(urdf_joint.find('origin'));at.update(pos=fmt(xyz),quat=fmt(q))
        body=sub(parent,'body',**at)
        if link_name=='trunk' and floating:sub(body,'freejoint',name='root')
        if urdf_joint is not None and urdf_joint.get('type')!='fixed':
            kind=urdf_joint.get('type')
            if kind not in ['revolute','continuous','prismatic']:raise ValueError(kind)
            lim=urdf_joint.find('limit')
            ja={'name':urdf_joint.get('name'),'type':'slide' if kind=='prismatic' else 'hinge',
                'axis':urdf_joint.find('axis').get('xyz','1 0 0')}
            if kind!='continuous':ja.update(limited='true',range=fmt([lim.get('lower'),lim.get('upper')]))
            sub(body,'joint',**ja)
            ordered.append({'joint_name':urdf_joint.get('name'),'joint_type':kind,
                            'lower':lim.get('lower',''),'upper':lim.get('upper',''),
                            'source_effort_limit':lim.get('effort',''), 'source_velocity_limit':lim.get('velocity','')})
        source=links[link_name]
        it=source.find('inertial')
        if it is not None:
            pos,q=origin(it.find('origin'))
            ii=it.find('inertia');val={k:float(v) for k,v in ii.attrib.items()}
            I=np.array([[val['ixx'],val['ixy'],val['ixz']],[val['ixy'],val['iyy'],val['iyz']],[val['ixz'],val['iyz'],val['izz']]])
            RR=Rotation.from_quat(q[[1,2,3,0]]).as_matrix();I=RR@I@RR.T
            sub(body,'inertial',pos=fmt(pos),mass=it.find('mass').get('value'),
                fullinertia=fmt([I[0,0],I[1,1],I[2,2],I[0,1],I[0,2],I[1,2]]))
        for tag,group in [('visual','2'),('collision','3')]:
            for ix,item in enumerate(source.findall(tag)):
                pos,q=origin(item.find('origin'))
                g=item.find('geometry');shape=list(g)[0]
                attrs={'name':f'{link_name}_{tag}_{ix}','pos':fmt(pos),'quat':fmt(q),'group':group}
                if tag=='visual':
                    attrs.update(contype='0',conaffinity='0',mass='0')
                    color=item.find('material/color')
                    attrs['rgba']=color.get('rgba') if color is not None else '0.55 0.57 0.61 1'
                else:attrs.update(contype='1',conaffinity='1',mass='0',rgba='0.3 0.5 0.7 0.15')
                if shape.tag=='mesh':attrs.update(type='mesh',mesh=asset(shape))
                elif shape.tag=='box':attrs.update(type='box',size=fmt(np.fromstring(shape.get('size'),sep=' ')/2))
                elif shape.tag=='cylinder':attrs.update(type='cylinder',size=fmt([float(shape.get('radius')),float(shape.get('length'))/2]))
                elif shape.tag=='sphere':attrs.update(type='sphere',size=shape.get('radius'))
                else:raise ValueError(shape.tag)
                sub(body,'geom',**attrs)
        for j in children[link_name]:emit(j.find('child').get('link'),body,j)
    emit('trunk',world)
    actuators=sub(mj,'actuator')
    for row in ordered:
        e=float(row['source_effort_limit'])
        sub(actuators,'motor',name=row['joint_name']+'_torque',joint=row['joint_name'],gear='1',
            ctrllimited='true',ctrlrange=fmt([-e,e]),forcelimited='true',forcerange=fmt([-e,e]))
    custom=sub(mj,'custom')
    sub(custom,'numeric',name='source_joint_velocity_limits_NOT_ENFORCED',data=fmt([r['source_velocity_limit'] for r in ordered]))
    sub(custom,'numeric',name='mount_masses_unknown',data='0')
    sub(custom,'text',name='validation_scope',data='Uniform effective-density material-estimated mount masses and inertias. No hardware or trained-policy validation.')
    key=sub(mj,'keyframe');q=inspection_pose([r['joint_name'] for r in ordered]);q=([0,0,0,1,0,0,0]+q) if floating else q
    sub(key,'key',name='inspection_only',qpos=fmt(q))
    for i,row in enumerate(ordered):
        row.update(actuator_index=i,qpos_index=i+(7 if floating else 0),qvel_index=i+(6 if floating else 0))
    return mj,ordered


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package',type=Path,default=Path(__file__).resolve().parents[1])
    args=parser.parse_args();p=args.package.resolve()
    for variant,stem in [('final','a2_piper')]:
        urdf=build_urdf(p,variant);write_xml(urdf,p/(stem+'.urdf'))
        mj,ordered=urdf_to_mjcf(urdf,p,stem,True);write_xml(mj,p/(stem+'.xml'))
        if variant=='final':
            with (p/'config/joint_mapping.csv').open('w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=list(ordered[0]));w.writeheader();w.writerows(ordered)
            (p/'config/inspection_pose.json').write_text(json.dumps(dict(zip([r['joint_name'] for r in ordered],inspection_pose([r['joint_name'] for r in ordered]))),indent=2)+'\n')
            fixed,_=urdf_to_mjcf(urdf,p,'a2_piper_fixed',False);write_xml(fixed,p/'a2_piper_fixed.xml')
            ros=copy.deepcopy(urdf)
            for mesh in ros.findall('.//mesh'):mesh.set('filename','package://a2_piper_vpiper_description/'+mesh.get('filename'))
            ext=ros.find('mujoco')
            if ext is not None:ros.remove(ext)
            write_xml(ros,p/'a2_piper_ros.urdf')
    scene=ET.Element('mujoco',model='mount_geometry_inspection')
    sub(scene,'include',file='a2_piper.xml')
    visual=sub(scene,'visual');global_=sub(visual,'global',azimuth='130',elevation='-20')
    world=sub(scene,'worldbody')
    sub(world,'light',pos='0 0 2',dir='0 0 -1',directional='true')
    sub(world,'geom',name='inspection_floor',type='plane',size='2 2 0.05',pos='0 0 -0.55',rgba='.85 .87 .89 1')
    write_xml(scene,p/'scene.xml')
    print('Wrote one final geometry: URDF/MJCF, fixed MJCF, ROS URDF and scene. Original URDF retained only in source/.')

if __name__=='__main__':main()
