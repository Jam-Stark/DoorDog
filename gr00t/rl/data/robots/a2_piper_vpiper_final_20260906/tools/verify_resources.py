#!/usr/bin/env python3
"""Check source hashes, serialized new collision hulls, ROS paths, and fixed MJCF FK."""
from pathlib import Path
import argparse,hashlib,json
import xml.etree.ElementTree as ET
import numpy as np,trimesh
from verify_models import urdf_tree,mjcf_fk,semantic

def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--package',type=Path,default=Path(__file__).resolve().parents[1]);p=ap.parse_args().package
 provenance=json.loads((p/'source/source_provenance.json').read_text());matches=[]
 for f,row in provenance['preserved_worker_files'].items():
  target=p/row['final_package_path'];assert target.is_file() and sha(target)==row['sha256'],f;matches.append(f)
 hulls=[]
 for f in sorted((p/'meshes/mount').glob('*collision_*.stl')):
  m=trimesh.load(f,process=True);assert m.is_watertight and m.is_convex and m.volume>0, f
  hulls.append({'file':str(f.relative_to(p)),'faces':len(m.faces),'volume_m3':float(m.volume),'watertight':True,'convex':True})
 assert len(hulls)==51
 plate=trimesh.load(p/'meshes/mount/metal_plate_5mm_head_width.stl');assert plate.is_watertight and plate.is_convex and plate.volume>0
 assert np.max(np.abs(plate.bounds-np.array([[-.125,-.05,0],[.125,.05,.005]])))<1e-8
 u,links,joints,fk=urdf_tree(p/'a2_piper.urdf');ros=ET.parse(p/'a2_piper_ros.urdf').getroot();prefix='package://a2_piper_vpiper_description/'
 for m in ros.findall('.//mesh'):
  assert m.get('filename').startswith(prefix);f=m.get('filename')[len(prefix):];assert (p/f).is_file();m.set('filename',f)
 uc=ET.fromstring(ET.tostring(u));ext=uc.find('mujoco');uc.remove(ext)
 assert semantic(ros)==semantic(uc),'ROS model differs beyond path prefix/compiler extension'
 fixed=ET.parse(p/'a2_piper_fixed.xml').getroot();floating=ET.parse(p/'a2_piper.xml').getroot()
 assert len(fixed.findall('.//freejoint'))==0 and len(floating.findall('.//freejoint'))==1
 moving=[j for j in joints if j.get('type')!='fixed'];rng=np.random.default_rng(20260907);err=0
 for _ in range(256):
  q={j.get('name'):rng.uniform(float(j.find('limit').get('lower')),float(j.find('limit').get('upper'))) for j in moving}
  a,b=fk(q),mjcf_fk(fixed,q)
  for n in links:err=max(err,float(np.max(np.abs(a[n]-b[n]))))
 assert err<1e-9
 for file in ['a2_piper.xml','a2_piper_fixed.xml']:
  r=ET.parse(p/file).getroot()
  for m in r.findall('asset/mesh'):assert (p/m.get('file')).is_file()
 assert ET.parse(p/'scene.xml').getroot().find('include').get('file')=='a2_piper.xml'
 result={'status':'RESOURCE_AND_SECONDARY_FORMAT_PASS','worker_original_URDF_and_mesh_files_preserved':len(matches),'new_serialized_convex_mount_hulls':len(hulls),'plate_visual_and_collision_size_mm':[250,100,5],'ROS_variant_equivalent_except_URI_and_extension':True,'fixed_MJCF_FK_test_configurations':256,'fixed_MJCF_max_matrix_error':err,'native_engine_compile':'NOT_RUN','collision_hulls':hulls}
 (p/'validation/resource_validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='collision_hulls'},indent=2))
if __name__=='__main__':main()
