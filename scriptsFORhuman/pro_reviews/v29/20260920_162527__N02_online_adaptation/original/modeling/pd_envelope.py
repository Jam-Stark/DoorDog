#!/usr/bin/env python3
"""Static arm PD envelope including C002 hard joint-target clamp; no rollout."""
from pathlib import Path
import json
import numpy as np
from robot_model import Robot,arm_bound,whole_bound
from run_analysis import dump,csvwrite
root=Path(__file__).resolve().parents[1];out=root/'results';inp=root/'modeling/inputs'
r=Robot(inp/'a2_piper.urdf',inp/'JOINT_LIMITS_AND_ACTUATORS.csv')
states=json.load(open(out/'states.json'));rows=[];details=[]
import csv
forces=list(csv.DictReader(open(out/'directional_force.csv')))
for s in states:
 if s['ik_status']!='REACHABLE':continue
 q=np.array(s['q']);k=r.fk(q,np.array(s['base_xyz']),np.array(s['base_R']));M,g,com,U=r.terms(k)
 lo=-r.cap.copy();hi=r.cap.copy()
 # qdot=0, nominal gains, arm target clamp enabled in C002. Apply only to arm.
 lo[r.arm]=np.maximum(lo[r.arm],r.kp[r.arm]*(r.lo[r.arm]-q[r.arm]))
 hi[r.arm]=np.minimum(hi[r.arm],r.kp[r.arm]*(r.hi[r.arm]-q[r.arm]))
 # cumulative action clip15 at scale.25 implies +/-3.75 about defaults;
 # all C002 configured arm limits are within that interval, so hard limits dominate.
 for row in forces:
  if (row['workpoint'],row['pose'])!=(s['workpoint'],s['pose']):continue
  d=np.array([float(row[z]) for z in ['dx','dy','dz']]);ab=arm_bound(r,k,g,d,lo[r.arm],hi[r.arm]);wb=whole_bound(r,k,g,d,tau_bounds=(lo,hi));t20=ab['b']+20*ab['a'];qd20=q[r.arm]+t20/r.kp[r.arm]
  rows.append(dict(workpoint=s['workpoint'],pose=s['pose'],direction=row['direction'],arm_PD_status=ab['status'],arm_PD_force_N=ab['force_N'],arm_PD_limiter=ab['limiter'],whole_PD_status=wb['status'],whole_PD_force_N=wb['force_N'],whole_PD_limiter=wb.get('limiter',''),target_at20N_within_limits=bool(np.all(qd20>=r.lo[r.arm]-1e-8)&np.all(qd20<=r.hi[r.arm]+1e-8)),target_limit_excess_at20N_rad=float(max(0,np.max(qd20-r.hi[r.arm]),np.max(r.lo[r.arm]-qd20)))))
  details.append(dict(workpoint=s['workpoint'],pose=s['pose'],direction=row['direction'],tau_lower_arm_Nm=lo[r.arm],tau_upper_arm_Nm=hi[r.arm],q_target_at20N_rad=qd20,whole=wb))
csvwrite(out/'pd_target_limited_force.csv',rows);dump(out/'pd_envelope_details.json',details)
print('EXECUTED',len(rows),'rows')
for z in rows:
 if z['workpoint']=='mid105' and z['direction']=='opening_normal_tangent':print(z)
print('PD infeasible',sum(z['whole_PD_status']=='INFEASIBLE' for z in rows))
