#!/usr/bin/env python3
"""CPU offline force bounds. Run from delivery root:
OPENBLAS_NUM_THREADS=1 python modeling/run_analysis.py --out results
See DYNAMICS_AND_FORCE_ANALYSIS.md for assumptions; no Isaac/policy/hardware run.
"""
from __future__ import annotations
import argparse,csv,json,platform,sys,time
from pathlib import Path
import numpy as np
import scipy
from scipy.spatial.transform import Rotation
from scipy.optimize import linprog
from robot_model import Robot,arm_bound,whole_bound

TCP=np.array([0.,0.,.085])
def dump(p,obj):
    def conv(x):
        if isinstance(x,np.ndarray):return x.tolist()
        if isinstance(x,np.generic):return x.item()
        raise TypeError(type(x).__name__)
    p.write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=conv,allow_nan=False)+'\n')
def csvwrite(path,rows):
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with open(path,'w',newline='') as f:
        w=csv.DictWriter(f,keys);w.writeheader();w.writerows(rows)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,default=Path(__file__).resolve().parents[1]/'results');args=ap.parse_args();out=args.out;out.mkdir(parents=True,exist_ok=True)
    start=time.time();inputs=Path(__file__).parent/'inputs';inp=json.load(open(inputs/'ROBOT_MODEL_INPUTS.json'));r=Robot(inputs/'a2_piper.urdf',inputs/'JOINT_LIMITS_AND_ACTUATORS.csv')
    q0=np.array([inp['init_state']['default_joint_angles'][n] for n in r.names]);q0[r.index['arm_j7']]=.014;q0[r.index['arm_j8']]=-.014 # hypothetical 28mm span, inertial only
    base=np.array([0.,0.,.55*np.cos(.5)+.032]);kn=r.fk(q0,base,np.eye(3));foot_centres={f:r.point(kn,f).copy() for f in r.feet}
    targets=[dict(name='low90',p=[.50,.12,.90],side=-1,angle=0),dict(name='mid105',p=[.55,.12,1.05],side=-1,angle=0),dict(name='far90',p=[.70,.12,.90],side=-1,angle=0),dict(name='high120',p=[.60,0.,1.20],side=-1,angle=0),dict(name='left105',p=[.55,-.12,1.05],side=1,angle=0),dict(name='open30',p=[.55,.12,1.05],side=-1,angle=30)]
    poses=[('neutral',0.,0.),('roll+8',8.,0.),('roll-8',-8.,0.),('pitch+8',0.,8.),('pitch-8',0.,-8.),('pitch+15',0.,15.),('pitch-15',0.,-15.)]
    settings=dict(base_xyz_m=base,foot_sphere_radius_m=.032,foot_centres_world_m=foot_centres,tcp_offset_m=TCP,targets=targets,poses=poses,force_definition='robot ON door at TCP, +F*d_W, zero moment at TCP',world_axes='X forward closed-door normal; Y robot left; Z up',gravity_m_s2=9.81,ground_mu_main=.6,ground_mu_sensitivity=[.3,1.],friction_pyramid='abs(fx)+abs(fy)<=mu*fz (inner cone)',grip_model='parametric pinch; no collision/contact solution',grip_mu_sensitivity=[.2,.4,.8],finger_normal_upper_each_N=45.,arm_cap_scale_sensitivity=[.1,.2,1.],posture_comparison='fixed base xyz and four foot sphere centres; full TCP position/orientation fixed within target',mesh_collision_checked=False,controller_replayed=False)
    dump(out/'parameters.json',settings)
    rng=np.random.default_rng(2902);allstates=[];fr=[];sens=[];dyn=[];detail=[];val=[]
    for target in targets:
        side=target['side'];theta=np.deg2rad(target['angle']);yaw=-side*theta
        e=np.array([0.,-side,0.]);approach=np.array([1.,0.,0.]);R0=np.column_stack((e,np.cross(-e,approach),approach));Rt=Rotation.from_euler('z',yaw).as_matrix()@R0
        p=np.array(target['p']);best=None
        # independent bounded multistart for a reproducible neutral IK branch, NOT force maximization
        for it in range(10):
            seed=q0.copy()
            if it:seed[r.arm]=[(-side)*.2,rng.uniform(.1,2.5),-rng.uniform(.2,2.5),rng.uniform(-1,1),rng.uniform(-.8,.8),(-side)*1.57]
            q,pe,re=r.ik(seed,base,np.eye(3),'arm_body6_to_gripper',p,Rt,r.arm,TCP)
            if best is None or pe+.3*re<best[1]+.3*best[2]:best=(q,pe,re)
            if pe<1e-7 and re<1e-7:break
        qneutral=best[0]
        for name,rol,pit in poses:
            Rb=Rotation.from_euler('xyz',np.deg2rad([rol,pit,0])).as_matrix();q=qneutral.copy();maxfoot=0.
            for f in r.feet:
                idx=sorted(r.anc[f]);q,ep,_=r.ik(q,base,Rb,f,foot_centres[f],indices=idx);maxfoot=max(maxfoot,ep)
            q,pe,re=r.ik(q,base,Rb,'arm_body6_to_gripper',p,Rt,r.arm,TCP)
            good=pe<1e-5 and re<1e-4 and maxfoot<1e-5
            k=r.fk(q,base,Rb);M,g,com,U=r.terms(k);Jv,Jw=r.jac(k,'arm_body6_to_gripper',TCP);J6=np.vstack([Jv[:,6+r.arm],Jw[:,6+r.arm]])
            state=dict(workpoint=target['name'],pose=name,roll_deg=rol,pitch_deg=pit,ik_status='REACHABLE' if good else 'NOT_RESOLVED_WITHIN_LIMITS',tcp_position_residual_m=pe,tcp_rotation_residual_rad=re,foot_max_residual_m=maxfoot,q=q.tolist(),joint_names=r.names,tcp_target_world_m=p.tolist(),tcp_R_world=Rt.tolist(),base_xyz=base.tolist(),base_R=Rb.tolist(),com_world_m=com.tolist(),g_arm_nm=g[6+r.arm].tolist(),J6_singular_values=np.linalg.svd(J6,compute_uv=False).tolist())
            allstates.append(state);print(target['name'],name,state['ik_status'],f'xyz_err={pe:.3g}; ori_err={re:.3g}; foot_err={maxfoot:.3g}',flush=True)
            if not good:continue
            # Numerical cross-check at every resolved state: central-difference gravity and TCP Jacobian.
            eps=1e-6;maxjg=0.;maxgg=0.
            for j in range(r.n):
                qp=q.copy();qm=q.copy();qp[j]+=eps;qm[j]-=eps
                kp=r.fk(qp,base,Rb);km=r.fk(qm,base,Rb)
                fd=(r.point(kp,'arm_body6_to_gripper',TCP)-r.point(km,'arm_body6_to_gripper',TCP))/(2*eps)
                maxjg=max(maxjg,float(np.max(np.abs(fd-Jv[:,6+j]))))
                # direct potential energy, independent of Jacobian expression
                def pot(kk):return sum(l['m']*9.81*r.point(kk,n,l['com'])[2] for n,l in r.links.items())
                fdg=(pot(kp)-pot(km))/(2*eps);maxgg=max(maxgg,abs(fdg-g[6+j]))
            val.append(dict(workpoint=target['name'],pose=name,jacobian_max_abs_error=maxjg,gravity_max_abs_error_nm=maxgg,M_symmetry_error=float(np.max(abs(M-M.T))),M_min_eigenvalue=float(np.linalg.eigvalsh(M)[0])))
            t=Rotation.from_euler('z',yaw).apply([1.,0.,0.]);rad=Rotation.from_euler('z',yaw).apply([0.,-side,0.])
            dirs=[('press_down',np.array([0.,0.,-1.])),('opening_normal_tangent',t),('closing_normal_tangent',-t),('handle_axis',rad)]
            for direction,d in dirs:
                ab=arm_bound(r,k,g,d);wb=whole_bound(r,k,g,d)
                ab_no_g=arm_bound(r,k,np.zeros_like(g),d)
                row=dict(workpoint=target['name'],pose=name,roll_deg=rol,pitch_deg=pit,direction=direction,dx=d[0],dy=d[1],dz=d[2],arm_status=ab['status'],arm_force_N=ab['force_N'],arm_no_gravity_force_N=ab_no_g['force_N'],arm_limiter=ab['limiter'],whole_status=wb['status'],whole_force_N=wb['force_N'],whole_limiter=wb.get('limiter',''),unloaded_feet=';'.join(wb.get('unloaded_feet',[])))
                a,b=ab['a'],ab['b'];tau20=b+a*20;row['arm_peak_abs_tau_at20N_Nm']=float(max(abs(tau20)));row['arm_peak_PD_error_at20N_rad']=float(max(abs(tau20/r.kp[r.arm])));row['arm_min_cap_margin_at20N_Nm']=float(min(r.cap[r.arm]-abs(tau20)))
                lp=linprog([-1.],A_ub=np.r_[a,-a].reshape(-1,1),b_ub=np.r_[r.cap[r.arm]-b,r.cap[r.arm]+b],bounds=[(0,None)],method='highs')
                row['arm_analytic_vs_LP_abs_N']=float(abs(ab['force_N']-lp.x[0])) if lp.success and ab['force_N'] is not None else None
                fr.append(row);detail.append(dict(workpoint=target['name'],pose=name,direction=direction,whole=wb,arm_a_m=a,arm_g_nm=b))
                for mu in [.3,1.]:
                    z=whole_bound(r,k,g,d,mu=mu);sens.append(dict(workpoint=target['name'],pose=name,direction=direction,kind='ground_mu',parameter=mu,force_N=z['force_N'],status=z['status']))
                for scale in [.1,.2]:
                    z=whole_bound(r,k,g,d,arm_scale=scale);sens.append(dict(workpoint=target['name'],pose=name,direction=direction,kind='arm_sim_cap_scale',parameter=scale,force_N=z['force_N'],status=z['status']))
                # Approximate pinch upper bound with opposite normals n=local TCP y; not measured grasp.
                n=Rt[:,1];dn=abs(d@n);dt=np.linalg.norm(d-(d@n)*n)
                for mu in [.2,.4,.8]:
                    # minimum normal difference |F.n|, max available sum 2*Nmax-|F.n|
                    cap=2*45.*mu/(dt+mu*dn) if dt+mu*dn>1e-12 else None
                    z=min(wb['force_N'],cap) if wb['force_N'] is not None and cap is not None else None
                    sens.append(dict(workpoint=target['name'],pose=name,direction=direction,kind='pinch_mu_two45N',parameter=mu,force_N=z,grip_only_force_N=cap,status=wb['status']))
                # Configured static finger PD at this assumed finger position (not measured squeeze).
                Npd=min(45.,1300.*abs(q[r.index['arm_j7']]))
                for mu in [.2,.4,.8]:
                    cap=2*Npd*mu/(dt+mu*dn) if dt+mu*dn>1e-12 else None
                    z=min(wb['force_N'],cap) if wb['force_N'] is not None and cap is not None else None
                    sens.append(dict(workpoint=target['name'],pose=name,direction=direction,kind='pinch_mu_PD_q014',parameter=mu,force_N=z,grip_only_force_N=cap,status=wb['status']))
                # Instantaneous rest acceleration sensitivity. Not a rollout or tracking proof.
                if direction=='opening_normal_tangent':
                    for acc in [-.5,.5]:
                        qdd=np.linalg.lstsq(J6,np.r_[d*acc,np.zeros(3)],rcond=1e-9)[0];res=float(np.linalg.norm(J6@qdd-np.r_[d*acc,np.zeros(3)]));gh=g+M[:,6+r.arm]@qdd
                        z=whole_bound(r,k,gh,d);za=arm_bound(r,k,gh,d)
                        dyn.append(dict(workpoint=target['name'],pose=name,acceleration_m_s2=acc,qddot_peak_rad_s2=float(max(abs(qdd))),acceleration_residual=res,delta_arm_tau_peak_Nm=float(max(abs((gh-g)[6+r.arm]))),arm_force_N=za['force_N'],whole_force_N=z['force_N'],status=z['status']))
            # Save one floating mass matrix and full terms for independent inspection.
            if target['name']=='mid105' and name=='neutral':np.savez(out/'mid105_neutral_model.npz',M=M,g=g,Jtcp_v=Jv,Jtcp_w=Jw,q=q,base=base,R=Rb)
    csvwrite(out/'directional_force.csv',fr);csvwrite(out/'sensitivity.csv',sens);csvwrite(out/'inertial_sensitivity.csv',dyn);csvwrite(out/'validation.csv',val);dump(out/'states.json',allstates);dump(out/'solver_details.json',detail)
    failures=[s for s in allstates if s['ik_status']!='REACHABLE'];csvwrite(out/'ik_status.csv',[{k:s[k] for k in ['workpoint','pose','roll_deg','pitch_deg','ik_status','tcp_position_residual_m','tcp_rotation_residual_rad','foot_max_residual_m']} for s in allstates])
    summary=dict(status='EXECUTED_CPU_OFFLINE_MODEL',python=sys.version,platform=platform.platform(),numpy=np.__version__,scipy=scipy.__version__,elapsed_seconds=time.time()-start,model_links=len(r.links),actuated_dof=r.n,tangent_dimension=r.nv,mass_kg=sum(l['m'] for l in r.links.values()),n_workpoint_poses=len(allstates),n_resolved_poses=len(allstates)-len(failures),n_unresolved_poses=len(failures),n_direction_rows=len(fr),n_unbounded_arm=sum(x['arm_status']=='UNBOUNDED' for x in fr),n_unbounded_whole=sum(x['whole_status']=='UNBOUNDED' for x in fr),max_jacobian_fd_error=max(x['jacobian_max_abs_error'] for x in val),max_gravity_fd_error_nm=max(x['gravity_max_abs_error_nm'] for x in val),max_arm_analytic_lp_error_N=max(x['arm_analytic_vs_LP_abs_N'] or 0 for x in fr),max_whole_equilibrium_residual=max(x['whole'].get('eq_residual',0) for x in detail),notes=['No trained policy or simulator runtime.','URDF rigid-body inertias, not USD runtime equivalence.','Ground cone inner approximation; omitted grasp/collision/controller mean relaxed capacity, not hardware guarantee.','IK failure means bounded solver did not resolve; not a global mathematical infeasibility proof.','Armature omitted from rigid body M; static results unaffected.','All torque values are simulation caps.'])
    dump(out/'execution_summary.json',summary);print(json.dumps(summary,indent=2),flush=True)
if __name__=='__main__':main()
