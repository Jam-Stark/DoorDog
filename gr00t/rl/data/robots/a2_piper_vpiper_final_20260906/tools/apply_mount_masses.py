#!/usr/bin/env python3
"""Create separate mass-configured variants after actual masses become available.

Requires acknowledging that the new masses are not already included in source inertias.
Uniform-density CAD inertia is an explicit approximation, not a measured inertia tensor.
"""
from pathlib import Path
import argparse,json,xml.etree.ElementTree as ET
import numpy as np
from build_models import sub,fmt,write_xml,urdf_to_mjcf

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--package',type=Path,default=Path(__file__).resolve().parents[1])
    ap.add_argument('--mass-file',type=Path,required=True)
    ap.add_argument('--confirm-not-already-in-source',action='store_true')
    ap.add_argument('--accept-uniform-density',action='store_true')
    a=ap.parse_args();p=a.package.resolve()
    if not a.confirm_not_already_in_source:ap.error('Confirm that these masses are not already in the original trunk/arm inertials.')
    inputs=json.loads(a.mass_file.read_text());nom=json.loads((p/'config/mass_properties_to_complete.json').read_text())
    report={};r=ET.parse(p/'a2_piper.urdf').getroot();total=0.
    for name in ['vpiper_main','vpiper_support','metal_plate_5mm']:
        cfg=inputs[name];mass=cfg.get('mass_kg')
        if mass is None or not np.isfinite(mass) or mass<=0:ap.error(f'{name}: supply a positive measured mass_kg.')
        if 'measured_center_of_mass_link_m' in cfg and 'measured_inertia_about_com_link_axes_kgm2' in cfg:
            com=np.array(cfg['measured_center_of_mass_link_m']);I=np.array(cfg['measured_inertia_about_com_link_axes_kgm2']);mode='user-provided measured COM/inertia'
        else:
            if not a.accept_uniform_density:ap.error(f'{name}: provide COM/inertia or explicitly accept the uniform-density approximation.')
            com=np.array(nom[name]['center_of_volume_link_m']);I=np.array(nom[name]['uniform_density_inertia_per_kg_about_com_B_kgm2_per_kg'])*mass;mode='measured mass + uniform-density CAD/envelope inertia approximation'
        if com.shape!=(3,) or I.shape!=(3,3) or not np.isfinite(com).all() or not np.isfinite(I).all():ap.error('Invalid shape or non-finite COM/inertia.')
        ev=np.linalg.eigvalsh(I)
        if not np.allclose(I,I.T,atol=1e-12) or ev.min()<=0 or ev.max()>ev.sum()-ev.max()+1e-12:ap.error(f'{name}: invalid physical inertia tensor.')
        link=r.find(f"link[@name='{name}']");inertial=sub(link,'inertial');sub(inertial,'origin',xyz=fmt(com),rpy='0 0 0');sub(inertial,'mass',value=mass)
        sub(inertial,'inertia',ixx=I[0,0],iyy=I[1,1],izz=I[2,2],ixy=I[0,1],ixz=I[0,2],iyz=I[1,2])
        report[name]={'mass_kg':mass,'mode':mode,'COM_link_m':com.tolist(),'I_com_link_axes_kgm2':I.tolist()};total+=mass
    stem='a2_piper_mass_configured';write_xml(r,p/(stem+'.urdf'));mj,_=urdf_to_mjcf(r,p,stem,True)
    for node in list(mj):
        if node.tag is ET.Comment:
            node.text = 'User-configured added masses; not a validated controller or dynamics model.'
    mj.find("custom/numeric[@name='mount_masses_unknown']").set('data','0')
    mj.find("custom/text[@name='validation_scope']").set('data','User-specified added mass configuration. No dynamics or hardware validation.')
    write_xml(mj,p/(stem+'.xml'))
    source=ET.parse(p/'source/a2_piper_original.urdf').getroot()
    retained=sum(float(x.get('value')) for x in source.findall('link/inertial/mass'))
    report['added_total_mass_kg']=total;report['retained_plus_added_mass_kg']=retained+total
    (p/'validation/mass_configuration.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'Wrote {stem}.urdf and .xml, without overwriting nominal files. Added mass = {total:g} kg.')
if __name__=='__main__':main()
