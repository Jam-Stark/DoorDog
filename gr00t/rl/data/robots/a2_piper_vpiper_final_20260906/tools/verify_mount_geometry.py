#!/usr/bin/env python3
"""Recompute CAD/URDF mounting datums. No inferred physical mass or photo metrology.
Requires CadQuery/OCP, numpy/scipy, trimesh. All geometry is in this package.
"""
from pathlib import Path
import argparse, csv, hashlib, json, sys
import xml.etree.ElementTree as ET
import numpy as np
import trimesh, cadquery as cq
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation
from OCP.IntCurvesFace import IntCurvesFace_ShapeIntersector
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.gp import gp_Pnt,gp_Dir,gp_Lin
sys.path.insert(0,str(Path(__file__).resolve().parent))
from verify_models import top_z_at_xy

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--package',type=Path,default=Path(__file__).resolve().parents[1]);a=ap.parse_args();p=a.package
 prior=json.loads((p/'source/previous_geometry_audit.json').read_text())
 xyz=np.load(p/'source/trunk_step_vertices_mm.npz')['xyz'];R0=np.diag([-1.,1.,-1.]);X=xyz@R0.T
 trunkmesh=trimesh.load(p/'meshes/trunk.STL',process=True);Y=trunkmesh.vertices*1000.;tree=cKDTree(Y);t=np.zeros(3)
 for _ in range(80):
  d,i=tree.query(X+t);keep=d<np.quantile(d,.7);dt=np.median(Y[i[keep]]-(X+t)[keep],axis=0);t+=dt
  if np.linalg.norm(dt)<1e-8:break
 d,ii=tree.query(X+t)
 rot=np.eye(3);t6=t.copy()
 for _ in range(40):
  dd,i=tree.query(X@rot.T+t6);k=dd<np.quantile(dd,.7);A=X[k];B=Y[i[k]];ca=A.mean(0);cb=B.mean(0);u,s,vt=np.linalg.svd((A-ca).T@(B-cb));rn=vt.T@u.T
  if np.linalg.det(rn)<0:vt[-1]*=-1;rn=vt.T@u.T
  tn=cb-ca@rn.T
  if np.max(np.abs(rn-rot))<1e-12 and np.max(np.abs(tn-t6))<1e-9:break
  rot,t6=rn,tn
 assert np.max(np.abs(t-np.array(prior['registration']['translation_B_mm'])))<1e-5
 def read_B(f):return cq.importers.importStep(str(f)).solids().val().rotate((0,0,0),(0,1,0),180).translate(tuple(t))
 main_s=read_B(p/'source/part4_original_STEP_mm.step');support_s=read_B(p/'source/part5_original_STEP_mm.step');trunk_s=read_B(p/'source/trunk_exact_STEP_mm.step')
 assert main_s.isValid() and support_s.isValid()
 trunk_valid=trunk_s.isValid()
 bb=main_s.BoundingBox();z0,z1=bb.zmin,bb.zmax
 assert abs(z1-z0-50)<1e-6
 topfaces=[f for f in main_s.Faces() if f.geomType()=='PLANE' and f.normalAt().z>.999999 and abs(f.Center().z-z1)<1e-6]
 top=max(topfaces,key=lambda x:x.Area());edges=[]
 for e in top.outerWire().Edges():
  edges.append({'type':e.geomType(),'length_mm':e.Length(),'start_B_mm':list(e.startPoint().toTuple()),'end_B_mm':list(e.endPoint().toTuple())})
 long=[e for e in edges if e['type']=='LINE' and abs(e['length_mm']-120)<1e-6]
 assert len(long)==2
 width=abs(long[0]['start_B_mm'][1]-long[1]['start_B_mm'][1]);assert abs(width-100)<1e-6
 head=[e for e in edges if e['type']=='LINE' and abs(e['start_B_mm'][0]-bb.xmax)<1e-6 and abs(e['end_B_mm'][0]-bb.xmax)<1e-6]
 assert len(head)==1 and abs(head[0]['length_mm']-80)<1e-6
 root=ET.parse(p/'source/a2_piper_original.urdf').getroot();coll=root.find("link[@name='trunk']").findall('collision');boxes=[]
 for i,c in enumerate(coll):
  o=c.find('origin');pos=np.fromstring(o.get('xyz'),sep=' ')*1000;rr=Rotation.from_euler('xyz',np.fromstring(o.get('rpy'),sep=' ')).as_matrix();size=np.fromstring(c.find('geometry/box').get('size'),sep=' ')*1000
  corners=np.array([[x,y,z] for x in [-1,1] for y in [-1,1] for z in [-1,1]])*size/2;corners=corners@rr.T+pos
  boxes.append({'index':i,'origin_B_mm':pos.tolist(),'rpy_rad':np.fromstring(o.get('rpy'),sep=' ').tolist(),'full_size_mm':size.tolist(),'aabb_B_mm':[corners.min(0).tolist(),corners.max(0).tolist()]})
 collision_top=boxes[0]['aabb_B_mm'][1][2];assert abs(collision_top-92)<1e-9
 # Exact BRep vertical intersections and independent STL interpolation.
 inter=IntCurvesFace_ShapeIntersector();inter.Load(trunk_s.wrapped,1e-7)
 footinter=IntCurvesFace_ShapeIntersector();footinter.Load(main_s.wrapped,1e-7)
 trunkcheck=BRepCheck_Analyzer(trunk_s.wrapped)
 def zhits(x,y):
  inter.Perform(gp_Lin(gp_Pnt(x,y,1000),gp_Dir(0,0,-1)),0,2000)
  return sorted([inter.Pnt(i).Z() for i in range(1,inter.NbPnt()+1)],reverse=True)
 tri=trunkmesh.triangles;rail=[]
 for x in [24.,48.,82.,94.]:
  for y in [-110.,-102.,102.,110.]:
   zs=zhits(x,y);zm=top_z_at_xy(tri,(x/1000,y/1000))*1000
   top_i=max(range(1,inter.NbPnt()+1),key=lambda i:inter.Pnt(i).Z())
   face_valid=trunkcheck.IsValid(inter.Face(top_i));assert face_valid
   footinter.Perform(gp_Lin(gp_Pnt(x,y,-1000),gp_Dir(0,0,1)),0,2000)
   footmin=min(footinter.Pnt(i).Z() for i in range(1,footinter.NbPnt()+1));assert abs(footmin-z0)<1e-6
   rail.append({'x_B_mm':x,'y_B_mm':y,'exact_trunk_rail_top_z_mm':zs[0],'mesh_trunk_top_z_mm':zm,'vpiper_foot_z_mm':z0,'CAD_gap_mm':z0-zs[0],'mesh_gap_mm':z0-zm,'vpiper_local_underside_hit_mm':footmin,'trunk_bearing_face_valid':bool(face_valid)})
 with (p/'validation/rail_contact_samples.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rail[0]));w.writeheader();w.writerows(rail)
 maxgap=max(abs(r['CAD_gap_mm']) for r in rail);maxmesh=max(abs(r['mesh_gap_mm']) for r in rail);assert maxgap<1e-6 and maxmesh<.001
 # Same CAD location: raised bearing lip and its underlying nominal plane.
 lip=zhits(24,102);assert len(lip)>=3
 probes=[]
 for x,y,label in [(24,95,'adjacent_back_shell'),(24,102,'bearing_lip_inner'),(24,106,'rail_groove_floor_NOT_mount_datum'),(24,110,'bearing_lip_outer'),(0,0,'back_shell_center_reference'),(145,0,'front_hump_NOT_mount_datum')]:
  zs=zhits(x,y);probes.append({'label':label,'xy_B_mm':[x,y],'exact_top_B_z_mm':zs[0],'all_intersections_B_z_mm':zs})
 mount_z=z1+5
 old_z=float(root.find("joint[@name='arm_j0']/origin").get('xyz').split()[2])*1000
 piper=trimesh.load(p/'meshes/piper/base_link.STL');piper_z0=float(piper.bounds[0,2]*1000);assert abs(piper_z0)<1e-6
 report={'status':'CAD_AND_MESH_DATUM_PASS','scope':'Supplied CAD/URDF geometry only; no hardware metrology or dynamics validation',
  'registration':{'R_B_from_STEP':R0.tolist(),'translation_B_mm':t.tolist(),'vertex_count':len(xyz),'residual_p50_p95_p99_max_mm':np.quantile(d,[.5,.95,.99,1]).tolist(),'six_dof_extra_rotation_vector_deg':(Rotation.from_matrix(rot).as_rotvec()*180/np.pi).tolist(),'six_dof_translation_mm':t6.tolist()},
  'plate':{'owner_constraint':'Thickness 5 mm; width matches narrower head portion of Vpiper, NOT the rear-wide top-face AABB. Overall head width interpreted including rounded corners.','length_retained_mm':bb.xmax-bb.xmin,'narrow_head_overall_width_mm':width,'head_straight_edge_mm':head[0]['length_mm'],'head_corner_radius_mm':10.,'previous_plate_width_mm':173.1042899275307,'final_width_mm':100.,'width_reduction_each_side_mm':(173.1042899275307-100)/2,'hole_slot_edge_detail':'unmeasured; rectangular nominal envelope, not a machining model','top_wire_edges':edges},
  'trunk_collision_boxes':boxes,'rail_back_probes':probes,
  'stack':{'source_main_collision_top_B_z_mm':collision_top,'rail_lower_reference_plane_B_z_mm':lip[1],'rail_lip_top_B_z_mm':lip[0],'rail_lip_rise_above_lower_reference_mm':lip[0]-lip[1],'rail_lip_top_minus_collision_box_top_mm':z0-collision_top,'vpiper_lower_foot_plane_B_z_mm':z0,'vpiper_top_face_B_z_mm':z1,'vpiper_height_mm':z1-z0,'metal_plate_thickness_mm':5.,'metal_plate_top_B_z_mm':mount_z,'piper_original_bottom_local_z_mm':piper_z0,'final_arm_j0_B_xyz_mm':[145.,0.,mount_z],'original_arm_j0_B_xyz_mm':[145.,0.,old_z],'final_minus_original_Z_mm':mount_z-old_z,'old_Z_minus_box_top_and_5mm_mm':old_z-collision_top-5,'final_box_referenced_chain_mm':[collision_top,z0-collision_top,z1-z0,5.]},
  'rail_contacts':{'count':len(rail),'max_abs_exact_gap_mm':maxgap,'max_abs_STL_gap_mm':maxmesh},
  'fixed_XY':'Retain original [145,0] mm; slot-locking position is not independently measured. No new horizontal shift imposed.',
  'do_not_add_extra_rail_height':'The CAD/mesh contact plane already is the top of the raised rail. Do not add 2.8 mm again.',
  'source_BRep_validity':{'vpiper_main':True,'vpiper_support':True,'trunk':bool(trunk_valid),'trunk_healing_applied':False,'scope_note':'Source trunk has one unorientable side-wall face; datum sampling is not global BRep validity certification. See source_trunk_brep_warning.json.'},
  'original_collision_policy':'All original trunk collision primitives retained; no new detailed rail collider; simplified collision box is not a mechanical datum.',
  'new_component_masses':'not provided and not guessed'}
 (p/'validation/final_geometry_audit.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
 print(json.dumps({'status':report['status'],'plate_width_mm':width,'stack':report['stack'],'rail_contacts':report['rail_contacts']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
