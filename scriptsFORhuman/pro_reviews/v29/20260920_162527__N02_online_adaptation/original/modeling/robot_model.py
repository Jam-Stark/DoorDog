"""Minimal URDF rigid-body model, SI, world-frame tangent velocities.
No mesh loading or physics simulation. Independent static/Jacobian/M(q) implementation.
Dependencies: numpy, scipy. Floating velocity order [v_base_W, omega_base_W, qdot].
"""
from __future__ import annotations
import csv
import xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from scipy.optimize import least_squares, linprog

def vec(s, default='0 0 0'):
    return np.fromstring(s if s is not None else default, sep=' ')
def skew(a):
    x,y,z=a
    return np.array([[0,-z,y],[z,0,-x],[-y,x,0.]])
def origin(e):
    if e is None:return np.eye(3),np.zeros(3)
    return Rotation.from_euler('xyz',vec(e.get('rpy'))).as_matrix(),vec(e.get('xyz'))

class Robot:
    def __init__(self,urdf:Path,caps:Path):
        root=ET.parse(urdf).getroot()
        self.links={}
        for l in root.findall('link'):
            ie=l.find('inertial'); R,p=origin(ie.find('origin'))
            d=ie.find('inertia').attrib
            I=np.array([[float(d['ixx']),float(d['ixy']),float(d['ixz'])],
                        [float(d['ixy']),float(d['iyy']),float(d['iyz'])],
                        [float(d['ixz']),float(d['iyz']),float(d['izz'])]])
            self.links[l.get('name')]=dict(m=float(ie.find('mass').get('value')),com=p,I=R@I@R.T)
        rows=list(csv.DictReader(open(caps)));self.names=[r['joint_name'] for r in rows]
        self.index={n:i for i,n in enumerate(self.names)};self.n=len(rows); self.nv=self.n+6
        self.lo=np.array([float(r['configured_lower']) for r in rows]);self.hi=np.array([float(r['configured_upper']) for r in rows])
        self.cap=np.array([float(r['configured_effort_limit']) for r in rows]);self.kp=np.array([float(r['configured_stiffness']) for r in rows])
        self.arm=np.array([self.index['arm_j'+str(i)] for i in range(1,7)])
        self.feet=[s+'_foot' for s in ['FL','RL','FR','RR']]
        self.joints=[];self.parent_joint={}
        raw=[]
        for j in root.findall('joint'):
            R,p=origin(j.find('origin'));a=j.find('axis');t=j.get('type')
            v=dict(name=j.get('name'),typ=t,par=j.find('parent').get('link'),child=j.find('child').get('link'),R=R,p=p,axis=vec(a.get('xyz')) if a is not None else np.zeros(3))
            raw.append(v);self.parent_joint[v['child']]=v
        visited={'trunk'}
        while raw:
            ready=[j for j in raw if j['par'] in visited]
            if not ready:raise ValueError('URDF disconnected/cyclic')
            for j in ready:self.joints.append(j);visited.add(j['child']);raw.remove(j)
        self.anc={}
        for l in self.links:
            a=[];c=l
            while c in self.parent_joint:
                j=self.parent_joint[c]
                if j['typ']!='fixed':a.append(self.index[j['name']])
                c=j['par']
            self.anc[l]=a
    def fk(self,q,base_p,base_R):
        poses={'trunk':(base_R,base_p)}; jp=np.zeros((self.n,3));ja=np.zeros((self.n,3))
        for j in self.joints:
            Rp,pp=poses[j['par']];R=Rp@j['R'];p=pp+Rp@j['p']
            if j['typ']!='fixed':
                k=self.index[j['name']];jp[k]=p;ja[k]=R@j['axis']
                if j['typ']=='revolute': R=R@Rotation.from_rotvec(j['axis']*q[k]).as_matrix()
                elif j['typ']=='prismatic':p=p+ja[k]*q[k]
                else:raise ValueError(j['typ'])
            poses[j['child']]=(R,p)
        return dict(poses=poses,jp=jp,ja=ja,base_p=base_p)
    def point(self,k,link,offset=None):
        R,p=k['poses'][link];return p if offset is None else p+R@offset
    def jac(self,k,link,offset=None):
        p=self.point(k,link,offset);Jv=np.zeros((3,self.nv));Jw=np.zeros_like(Jv)
        Jv[:,:3]=np.eye(3);Jv[:,3:6]=-skew(p-k['base_p']);Jw[:,3:6]=np.eye(3)
        for i in self.anc[link]:
            if self.names[i] in ['arm_j7','arm_j8']:Jv[:,6+i]=k['ja'][i]
            else:Jv[:,6+i]=np.cross(k['ja'][i],p-k['jp'][i]);Jw[:,6+i]=k['ja'][i]
        return Jv,Jw
    def terms(self,k):
        M=np.zeros((self.nv,self.nv));g=np.zeros(self.nv);com=np.zeros(3);mass=0.;U=0.
        for name,l in self.links.items():
            R,p=k['poses'][name];pc=p+R@l['com'];Jv,Jw=self.jac(k,name,l['com']);m=l['m']
            M+=m*(Jv.T@Jv)+Jw.T@(R@l['I']@R.T)@Jw
            g+=Jv.T@np.array([0.,0.,m*9.81]);com+=m*pc;mass+=m;U+=m*9.81*pc[2]
        return M,g,com/mass,U
    def ik(self,q0,base_p,base_R,link,target_p,target_R=None,indices=None,offset=None):
        idx=np.array(indices if indices is not None else self.anc[link]);q0=q0.copy()
        def err(x):
            q=q0.copy();q[idx]=x;k=self.fk(q,base_p,base_R);R,_=k['poses'][link]
            ep=self.point(k,link,offset)-target_p
            if target_R is None:return ep
            return np.r_[ep,.3*Rotation.from_matrix(R@target_R.T).as_rotvec()]
        s=least_squares(err,np.clip(q0[idx],self.lo[idx]+1e-9,self.hi[idx]-1e-9),bounds=(self.lo[idx]+1e-10,self.hi[idx]-1e-10),xtol=2e-12,ftol=2e-12,gtol=2e-12,max_nfev=350)
        q=q0.copy();q[idx]=s.x;k=self.fk(q,base_p,base_R)
        pe=float(np.linalg.norm(self.point(k,link,offset)-target_p));re=0. if target_R is None else float(np.linalg.norm(Rotation.from_matrix(k['poses'][link][0]@target_R.T).as_rotvec()))
        return q,pe,re

# Force on door = +F*d; force on robot = -F*d. No applied TCP moment.
def arm_bound(robot,k,g,d,torque_lo=None,torque_hi=None):
    J,_=robot.jac(k,'arm_body6_to_gripper',np.array([0,0,.085]));a=J[:,6+robot.arm].T@d;b=g[6+robot.arm]
    lo=-robot.cap[robot.arm] if torque_lo is None else torque_lo
    hi=robot.cap[robot.arm] if torque_hi is None else torque_hi
    L=0.;U=np.inf;binding='none'
    for i,(ai,bi) in enumerate(zip(a,b)):
        if abs(ai)<1e-12:
            if bi<lo[i]-1e-9 or bi>hi[i]+1e-9:return dict(status='INFEASIBLE',force_N=None,limiter=robot.names[robot.arm[i]],a=a,b=b)
        else:
            bounds=sorted([(lo[i]-bi)/ai,(hi[i]-bi)/ai]);L=max(L,bounds[0])
            if bounds[1]<U:U=bounds[1];binding=robot.names[robot.arm[i]]
    if U<L-1e-9:return dict(status='INFEASIBLE',force_N=None,limiter=binding,a=a,b=b)
    return dict(status='UNBOUNDED' if not np.isfinite(U) else 'OPTIMAL',force_N=float(U) if np.isfinite(U) else None,limiter=binding,a=a,b=b,minimum_force_N=float(L))

def whole_bound(robot,k,g,d,mu=.6,arm_scale=1.,foot_offset=np.array([0.,0.,-.032]),fixed_force=None,tau_bounds=None):
    # Inner approximation of Coulomb cone: |fx|+|fy| <= mu*fz.
    # Conservative wrt the friction cone, optimistic wrt omitted collision/controller/grasp.
    Jt,_=robot.jac(k,'arm_body6_to_gripper',np.array([0,0,.085]))
    # foot offset is WORLD vertical (round point foot). jac formed at offset in each link.
    Jfs=[]
    for f in robot.feet:
        R,_=k['poses'][f];Jfs.append(robot.jac(k,f,R.T@foot_offset)[0])
    Jf=np.concatenate(Jfs,axis=0)
    # x=[F, f_FL_xyz, f_RL_xyz, f_FR_xyz, f_RR_xyz]
    A=np.column_stack((Jt.T@d,-Jf.T));aeq=A[:6];beq=-g[:6]
    cap=robot.cap.copy();cap[robot.arm]*=arm_scale
    lo,hi=(-cap,cap) if tau_bounds is None else tau_bounds
    Aub=[A[6:],-A[6:]];bub=[hi-g[6:],g[6:]-lo];labels=[f'{n}:upper' for n in robot.names]+[f'{n}:lower' for n in robot.names]
    friction=[]
    for fi in range(4):
        for sx,sy in [(1,1),(1,-1),(-1,1),(-1,-1)]:
            a=np.zeros(13);a[1+3*fi]=sx;a[2+3*fi]=sy;a[3+3*fi]=-mu;friction.append(a);labels.append(f'{robot.feet[fi]}:friction({sx},{sy})')
    Aub=np.vstack(Aub+[np.array(friction)]);bub=np.r_[*bub,np.zeros(16)]
    bounds=[(0,None) if fixed_force is None else (fixed_force,fixed_force)]+[(None,None),(None,None),(0,None)]*4
    sol=linprog(np.r_[-1.,np.zeros(12)],A_ub=Aub,b_ub=bub,A_eq=aeq,b_eq=beq,bounds=bounds,method='highs')
    if not sol.success:return dict(status={2:'INFEASIBLE',3:'UNBOUNDED'}.get(sol.status,'SOLVER_FAILURE'),force_N=None,message=sol.message)
    x=sol.x;tau=g+A@x;slack=bub-Aub@x
    # Significant dual constraints rather than all contact-edge degeneracy.
    lim=[labels[i] for i,v in enumerate(sol.ineqlin.marginals) if abs(v)>1e-6]
    for fi in range(4):
        if abs(sol.lower.marginals[3+3*fi])>1e-6:lim.append(f'{robot.feet[fi]}:normal_lower')
    unloading=[robot.feet[i] for i in range(4) if x[3+3*i]<1e-7]
    return dict(status='OPTIMAL',force_N=float(x[0]),forces=x[1:].reshape(4,3).tolist(),tau=tau[6:].tolist(),eq_residual=float(np.max(np.abs(aeq@x-beq))),min_ineq_slack=float(slack.min()),limiter=';'.join(lim),unloaded_feet=unloading)
