#!/usr/bin/env python3
"""Build the head-width plate and one final mounting configuration from audited CAD.
Replaces only the unmeasured rectangular plate envelope; no holes are fabricated.
Run verify_mount_geometry.py before this script.
"""
from pathlib import Path
import argparse,json
import numpy as np,trimesh,cadquery as cq
from OCP.BRepAdaptor import BRepAdaptor_Surface

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--package',type=Path,default=Path(__file__).resolve().parents[1]);a=ap.parse_args();p=a.package
 report=json.loads((p/'validation/final_geometry_audit.json').read_text());T=np.array(report['registration']['translation_B_mm'])
 main=cq.importers.importStep(str(p/'source/part4_original_STEP_mm.step')).solids().val().rotate((0,0,0),(0,1,0),180).translate(tuple(T))
 holes=[]
 for f in main.Faces():
  ad=BRepAdaptor_Surface(f.wrapped)
  if f.geomType()=='CYLINDER':
   c=ad.Cylinder()
   if abs(c.Radius()-2.5)<1e-8 and abs(c.Axis().Direction().Z())>.99999:holes.append([c.Location().X(),c.Location().Y()])
 assert len(holes)==4
 pattern=np.mean(holes,axis=0);z0=report['stack']['vpiper_lower_foot_plane_B_z_mm'];z1=report['stack']['vpiper_top_face_B_z_mm'];z2=report['stack']['metal_plate_top_B_z_mm'];V=np.r_[pattern,z0]
 dims=np.array([report['plate']['length_retained_mm'],report['plate']['final_width_mm'],5.]);assert np.allclose(dims,[250,100,5],atol=1e-6)
 plate=cq.Solid.makeBox(*dims,cq.Vector(-dims[0]/2,-dims[1]/2,0))
 cq.exporters.export(plate,str(p/'cad/metal_plate_5mm_head_width_local_mm.step'))
 vertices,faces=plate.tessellate(.08,.1);m=trimesh.Trimesh(vertices=np.array([v.toTuple() for v in vertices])*.001,faces=np.array(faces),process=True)
 if m.volume<0:m.invert()
 f=p/'meshes/mount/metal_plate_5mm_head_width.stl';m.export(f);m=trimesh.load(f);assert m.is_watertight and m.is_convex
 # Confirm copied Vpiper local meshes encode the same fresh CAD transform.
 matching={}
 for n,sf in [('vpiper_main','part4_original_STEP_mm.step'),('vpiper_support','part5_original_STEP_mm.step')]:
  s=cq.importers.importStep(str(p/'source'/sf)).solids().val().rotate((0,0,0),(0,1,0),180).translate(tuple(T-V))
  cq.exporters.export(s,str(p/'cad'/f'{n}_local_mm.step'))
  vv,ff=s.tessellate(.08,.1);new=trimesh.Trimesh(vertices=np.array([x.toTuple() for x in vv])*.001,faces=np.array(ff),process=True)
  if new.volume<0:new.invert()
  old=trimesh.load(p/'meshes/mount'/f'{n}_visual.stl')
  # Mesh coordinate agreement checked before overwriting with fresh CAD tessellation.
  from scipy.spatial import cKDTree
  d,_=cKDTree(old.vertices).query(new.vertices)
  matching[n]={'fresh_vertex_to_previous_vertex_max_distance_m':float(d.max()),'source_solid_valid':s.isValid(),'source_volume_mm3':s.Volume()}
  assert d.max()<1e-7
  new.export(p/'meshes/mount'/f'{n}_visual.stl')
 cfg={'model_id':'A2-PIPER-VPIPER-5MM-HEAD100-FINAL-GEOMETRY-20260906','units':'metres; radians','trunk_frame':'B: +X forward, +Y left, +Z up; original trunk link origin unchanged',
  'vpiper_main_origin_B_m':(V*.001).tolist(),'vpiper_main_rpy_rad':[0,0,0],'support_origin_in_main_m':[0,0,0],'plate_origin_in_main_m':[0,0,.05],
  'plate_size_m':(dims*.001).tolist(),'plate_center_in_plate_frame_m':[0,0,.0025],
  'primary_arm_origin_B_m':[.145,0,z2*.001],'primary_arm_origin_in_plate_m':((np.array([145.,0.,z2])-np.r_[pattern,z1])*.001).tolist(),'arm_rpy_rad':[0,0,0],
  'plate_geometry':'RECTANGULAR NOMINAL ENVELOPE 250x100x5 mm, no invented slots/holes. Width matches head portion including corner radii; head straight edge itself is 80 mm.',
  'physical_XY_status':'Original X=145 mm,Y=0 retained; slot-locking pose unmeasured, no automatic CAD-hole X correction',
  'physical_Z_status':'CAD-derived raised-rail contact plane + 50 mm Vpiper + owner-confirmed 5 mm plate; not hardware metrology',
  'rail_in_model':'Raised rail is present in source trunk visual/CAD; original simplified collision primitives retained; no extra rail-height transform added',
  'new_component_masses_status':'unknown; no guessed density/inertia; original 27 link inertials preserved',
  'cad_hole_aligned_XY_for_information_only_m':((pattern+np.array([5.,0]))*.001).tolist(),'no_policy_or_controller_changes':True}
 (p/'config/mount_parameters.json').write_text(json.dumps(cfg,ensure_ascii=False,indent=2)+'\n')
 props=json.loads((p/'config/mass_properties_to_complete.json').read_text());ext=dims*.001
 props['metal_plate_5mm']={'volume_mm3':float(np.prod(dims)),'center_of_volume_link_m':[0,0,.0025],'link_frame_origin_B_m':(np.r_[pattern,z1]*.001).tolist(),
 'mass_kg':None,'density_kg_m3':None,'uniform_density_inertia_per_kg_about_com_B_kgm2_per_kg':(np.diag([ext[1]**2+ext[2]**2,ext[0]**2+ext[2]**2,ext[0]**2+ext[1]**2])/12).tolist(),
 'geometry_status':'RECTANGULAR 250x100x5 mm nominal envelope; holes/slots/corner treatment are unmeasured', 'mass_status':'UNKNOWN; actual material and slot removal are not inferred'}
 (p/'config/mass_properties_to_complete.json').write_text(json.dumps(props,indent=2)+'\n')
 (p/'validation/fresh_mount_mesh_comparison.json').write_text(json.dumps(matching,indent=2)+'\n')
 print('Final plate:',dims,'mm; arm xyz:',np.array(cfg['primary_arm_origin_B_m'])*1000,'mm')
if __name__=='__main__':main()
