#!/usr/bin/env python3
"""Independent Newton/Euler balance and separately labelled base relocation diagnostics."""
from pathlib import Path
import json,csv,sys
import numpy as np
from scipy.spatial.transform import Rotation
from robot_model import Robot,arm_bound,whole_bound
from run_analysis import dump,csvwrite,TCP
ROOT=Path(__file__).resolve().parents[1];out=ROOT/'results';inp=ROOT/'modeling/inputs'
r=Robot(inp/'a2_piper.urdf',inp/'JOINT_LIMITS_AND_ACTUATORS.csv')
s=next(s for s in json.load(open(out/'states.json')) if s['workpoint']=='mid105' and s['pose']=='neutral')
q=np.array(s['q']);base=np.array(s['base_xyz']);k=r.fk(q,base,np.eye(3));M,g,com,U=r.terms(k)
J,Jw=r.jac(k,'arm_body6_to_gripper',TCP);d=np.array([1.,0,0]);F=whole_bound(r,k,g,d)
feet=np.array([r.point(k,f)+[0,0,-.032] for f in r.feet]);forces=np.array(F['forces']);P=r.point(k,'arm_body6_to_gripper',TCP);m=sum(l['m'] for l in r.links.values());weight=np.array([0.,0.,-m*9.81]);onrobot=-F['force_N']*d
force_res=forces.sum(0)+weight+onrobot
moment_res=np.cross(feet-base,forces).sum(0)+np.cross(com-base,weight)+np.cross(P-base,onrobot)
# FD floating columns using world rotation perturbations.
eps=1e-6;Jfd=np.zeros((3,6));gfd=np.zeros(6)
def potential(kk):return sum(l['m']*9.81*r.point(kk,n,l['com'])[2] for n,l in r.links.items())
for i in range(6):
 if i<3:
  dp=np.eye(3)[i]*eps;kp=r.fk(q,base+dp,np.eye(3));km=r.fk(q,base-dp,np.eye(3))
 else:
  v=np.eye(3)[i-3]*eps;kp=r.fk(q,base,Rotation.from_rotvec(v).as_matrix());km=r.fk(q,base,Rotation.from_rotvec(-v).as_matrix())
 Jfd[:,i]=(r.point(kp,'arm_body6_to_gripper',TCP)-r.point(km,'arm_body6_to_gripper',TCP))/(2*eps)
 gfd[i]=(potential(kp)-potential(km))/(2*eps)
dump(out/'independent_balance_checks.json',dict(status='EXECUTED',force_balance_residual_N=force_res,moment_balance_residual_Nm=moment_res,floating_J_fd_error=float(np.max(abs(Jfd-J[:,:6]))),floating_g_fd_error=float(np.max(abs(gfd-g[:6])))))
# Separate base translation experiment: never mix into fixed-position posture comparison.
rows=[]
for dx in [-.05,0.,.05]:
 b=base+np.array([dx,0,0]);qq=q.copy();fe=0.
 for f in r.feet:
  qq,ep,_=r.ik(qq,b,np.eye(3),f,r.point(k,f),indices=sorted(r.anc[f]));fe=max(fe,ep)
 qq,pe,re=r.ik(qq,b,np.eye(3),'arm_body6_to_gripper',np.array(s['tcp_target_world_m']),np.array(s['tcp_R_world']),r.arm,TCP)
 row=dict(experiment='BASE_TRANSLATION_NOT_POSTURE_GAIN',base_dx_m=dx,foot_residual_m=fe,tcp_residual_m=pe,orientation_residual_rad=re)
 if max(fe,pe)<1e-5 and re<1e-4:
  kk=r.fk(qq,b,np.eye(3));_,gg,cc,_=r.terms(kk);ab=arm_bound(r,kk,gg,d);wb=whole_bound(r,kk,gg,d);tt=ab['b']+20*ab['a']
  row.update(status='RESOLVED',arm_force_N=ab['force_N'],whole_force_N=wb['force_N'],peak_tau_at20N_Nm=float(max(abs(tt))),limiter=wb['limiter'])
 else:row.update(status='NOT_RESOLVED_WITHIN_LIMITS')
 rows.append(row)
csvwrite(out/'separate_base_translation.csv',rows)
print(json.dumps(rows,indent=2));print((out/'independent_balance_checks.json').read_text())
