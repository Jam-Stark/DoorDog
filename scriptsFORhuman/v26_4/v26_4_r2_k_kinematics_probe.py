#!/usr/bin/env python3
"""R2 Wave K: real-articulation FK/target mirror gates, then frozen bilateral IK scan."""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import sys
import traceback
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT_ROOT = ROOT / "logs_eval/base_v26/v26_4_r2_bilateral_grasp_foundation_20260828/K"
R1_JSON = ROOT / "logs_eval/base_v26/v26_4_bilateral_grasp_foundation_20260828/K/k_kinematics.json"
ARM = tuple(f"arm_j{i}" for i in range(1, 7))
SIDES = ("LEFT", "RIGHT")
M = (-1, 1, 1, -1, 1, -1)
DEFAULT = (0.0, 0.0, 0.0, 0.25, 0.5, 1.57)
SEED = (0.0, 1.48, -0.63, -0.84, 0.0, 1.57)
GRID_X, GRID_Y, GRID_Z = (-0.72, -0.76, -0.80), (0.18, 0.22, 0.26), 0.415
TCP_Z, IK_STEPS, ACTION_SCALE = 0.085, 360, 0.25
POS_TOL, QUAT_TOL, REACH_POS, REACH_ROT, MIN_MARGIN = 1e-5, 2e-5, 0.03, 0.10, 0.10
MARGIN_GAP, J6_GAP, READBACK_TOL = 0.15, 0.25, 1e-5


def args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--device", default="cuda:0")
    p.add_argument("--output-root", type=Path, default=OUT_ROOT)
    return p.parse_args()


def r1_module():
    path = ROOT / "scriptsFORhuman/v26_4/v26_4_k_kinematics_probe.py"
    spec = importlib.util.spec_from_file_location("v26_4_r1_k", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("R2 cannot load the R1 fixture module.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def finite(torch, name, value, shape):
    if not torch.is_tensor(value) or tuple(value.shape) != shape or not value.is_floating_point():
        raise RuntimeError(f"R2 {name} shape/dtype mismatch: {getattr(value, 'shape', None)}.")
    if not bool(torch.all(torch.isfinite(value)).item()):
        raise RuntimeError(f"R2 {name} is non-finite.")


def js(x):
    x = float(x)
    if not math.isfinite(x):
        raise RuntimeError("R2 attempted non-finite JSON evidence.")
    return x


def scene_make(a, r1):
    import isaaclab.sim as sim_utils
    import torch
    from isaaclab.assets import ArticulationCfg
    from isaaclab.scene import InteractiveScene, InteractiveSceneCfg
    from isaaclab.sim import SimulationContext
    from isaaclab.utils import configclass
    from gr00t.rl.envs.door.a2_piper_door_scene_preview import build_a2_piper_robot_cfg, build_doorman_door_cfg

    rcfg = build_a2_piper_robot_cfg(ROOT / "gr00t/rl/data/robots/A2_Piper/a2_piper.usd", 0.0, 0.0, 0.0, 0.0)
    rcfg.spawn.rigid_props.disable_gravity = True
    rcfg.spawn.articulation_props.fix_root_link = True
    dcfg = r1._door_cfg(build_doorman_door_cfg)

    @configclass
    class Cfg(InteractiveSceneCfg):
        robot: ArticulationCfg = rcfg.replace(prim_path="{ENV_REGEX_NS}/Robot")
        door: ArticulationCfg = dcfg.replace(prim_path="{ENV_REGEX_NS}/door")

    sim = SimulationContext(sim_utils.SimulationCfg(dt=0.005, device=a.device))
    return sim, InteractiveScene(Cfg(num_envs=2, env_spacing=3.0, replicate_physics=False)), torch


def mirror_q(torch, q):
    return q * torch.tensor(M, device=q.device, dtype=q.dtype)


def reset(sim, scene, arm_ids, offsets, q_pair, torch):
    from isaaclab.utils.math import quat_apply
    robot, door = scene["robot"], scene["door"]
    droot = door.data.default_root_state.clone(); droot[:, :3] += scene.env_origins
    door.write_root_pose_to_sim(droot[:, :7]); door.write_root_velocity_to_sim(droot[:, 7:])
    dq = door.data.default_joint_pos.clone(); door.write_joint_state_to_sim(dq, torch.zeros_like(door.data.default_joint_vel)); door.set_joint_position_target(dq)
    root = robot.data.default_root_state.clone()
    root[:, :3] = droot[:, :3] + quat_apply(droot[:, 3:7], offsets); root[:, 3:7] = droot[:, 3:7]; root[:, 7:] = 0.0
    robot.write_root_pose_to_sim(root[:, :7]); robot.write_root_velocity_to_sim(root[:, 7:])
    q = robot.data.default_joint_pos.clone(); q[:, arm_ids] = q_pair
    robot.set_joint_position_target(q); robot.write_joint_state_to_sim(q, torch.zeros_like(robot.data.joint_vel))
    scene.reset(); scene.write_data_to_sim(); sim.forward(); scene.update(sim.get_physics_dt())


def tcp_pose(scene, body_id, torch):
    from isaaclab.utils.math import quat_apply
    robot = scene["robot"]
    bpos, bquat = robot.data.body_pos_w[:, body_id], robot.data.body_quat_w[:, body_id]
    offset = torch.tensor((0.0, 0.0, TCP_Z), device=robot.device, dtype=bpos.dtype).expand(2, -1)
    return bpos + quat_apply(bquat, offset), bquat, bpos


def local_pose(scene, pos, quat):
    from isaaclab.utils.math import subtract_frame_transforms
    door = scene["door"]
    return subtract_frame_transforms(door.data.root_pos_w, door.data.root_quat_w, pos, quat)


def quat_error(torch, actual, expected):
    raw = torch.max(torch.abs(actual - expected), dim=-1).values
    neg = torch.max(torch.abs(actual + expected), dim=-1).values
    return torch.minimum(raw, neg), raw, neg


def geom_target(scene, torch):
    """Derive the target solely from authored grasp point and handle-joint geometry."""
    from isaaclab.utils.math import quat_from_matrix, subtract_frame_transforms
    from omni.usd import get_context
    from pxr import Gf, UsdGeom

    stage, cache = get_context().get_stage(), UsdGeom.XformCache()
    pos, matrices, details = [], [], []
    for env, side in enumerate(SIDES):
        panel = stage.GetPrimAtPath(f"/World/envs/env_{env}/door/door_panel")
        joint = stage.GetPrimAtPath(f"/World/envs/env_{env}/door/door_panel/handle_joint")
        grasp = stage.GetPrimAtPath(f"/World/envs/env_{env}/door/grasp_target")
        if not panel.IsValid() or not joint.IsValid() or not grasp.IsValid():
            raise RuntimeError(f"R2 missing {side} authored handle geometry.")
        rot = joint.GetAttribute("physics:localRot0").Get(); lp = joint.GetAttribute("physics:localPos0").Get()
        if rot is None or lp is None: raise RuntimeError(f"R2 {side} missing handle LocalRot0/LocalPos0.")
        wxyz = [float(rot.GetReal()), *[float(v) for v in rot.GetImaginary()]]
        if side == "RIGHT" and not (abs(wxyz[0]) < 1e-6 and abs(wxyz[1]) < 1e-6 and abs(wxyz[2]) < 1e-6 and abs(abs(wxyz[3]) - 1.0) < 1e-6):
            raise RuntimeError(f"R2 RIGHT LocalRot0 must be Z-pi: {wxyz}.")
        panel_xf = cache.GetLocalToWorldTransform(panel)
        local = Gf.Rotation(Gf.Quatd(rot))
        handle_axis = panel_xf.TransformDir(local.TransformDir(Gf.Vec3d(1.0, 0.0, 0.0)))
        axis_origin = panel_xf.Transform(Gf.Vec3d(lp))
        gxf = cache.GetLocalToWorldTransform(grasp)
        t = gxf.ExtractTranslation(); grasp_pos = [float(t[0]),float(t[1]),float(t[2])]
        def unit(v):
            n = math.sqrt(sum(x * x for x in v))
            if not math.isfinite(n) or n <= 0.0: raise RuntimeError(f"R2 {side} derived target basis is degenerate.")
            return [x / n for x in v]
        def cross(a, b): return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]
        hx = unit([float(handle_axis[i]) for i in range(3)])
        axis_to_grasp = [float(axis_origin[i]) - grasp_pos[i] for i in range(3)]
        axial_component = sum(a*b for a,b in zip(axis_to_grasp, hx, strict=True))
        gx = unit([axis_to_grasp[i] - axial_component * hx[i] for i in range(3)])
        gz = [hx[i] * (1.0 if side == "LEFT" else -1.0) for i in range(3)]
        gy = unit(cross(gz, gx))
        right_handed = sum(a*b for a,b in zip(cross(gx, gy), gz, strict=True))
        orthogonality = max(abs(sum(a*b for a,b in zip(u,v,strict=True))) for u,v in ((gx,gy),(gy,gz),(gz,gx)))
        if orthogonality > 1e-6 or abs(right_handed - 1.0) > 1e-6:
            raise RuntimeError(f"R2 {side} target basis is not orthonormal/right-handed.")
        matrices.append([[gx[0], gy[0], gz[0]], [gx[1], gy[1], gz[1]], [gx[2], gy[2], gz[2]]])
        pos.append(grasp_pos)
        details.append({"side": side, "handle_joint_path": str(joint.GetPath()), "local_pos0_m": [float(v) for v in lp], "local_rot0_wxyz": wxyz, "axis_origin_world_m": [float(axis_origin[i]) for i in range(3)], "handle_axis_world_unit": hx, "tool_basis_from_geometry": {"gripper_x": "normalize(v-dot(v,handle_axis)*handle_axis), v=axis_origin-grasp_target", "gripper_y": "normalize((door_open_lr*handle_axis) cross gripper_x)", "gripper_z": "door_open_lr*handle_axis"}, "basis_orthogonality_max_abs": orthogonality, "basis_right_handed_dot": right_handed})
    dtype, device = scene["robot"].data.joint_pos.dtype, scene["robot"].device
    wp = torch.tensor(pos, device=device, dtype=dtype); mats = torch.tensor(matrices, device=device, dtype=dtype)
    wq = quat_from_matrix(mats); lp, lq = subtract_frame_transforms(scene["door"].data.root_pos_w, scene["door"].data.root_quat_w, wp, wq)
    return wp, wq, lp, lq, details


def r1_samples():
    data = json.loads(R1_JSON.read_text(encoding="utf-8"))
    values = []
    for c in data["candidates"]:
        values.append((c["candidate_id"], c["expected_door_local_root_offsets_xyz_m"], c["sides"]["LEFT"]["ik_requested_q_arm_j1_to_j6_rad"]))
    if len(values) != 9: raise RuntimeError("R2 requires all nine R1 LEFT convergence samples.")
    fixed = [[-0.76,0.22,GRID_Z],[-0.76,-0.22,GRID_Z]]
    values.extend([("workspace_default", fixed, list(DEFAULT)), ("workspace_anchor_seed", fixed, list(SEED)), ("workspace_zero", fixed, [0.0]*6), ("workspace_mid", fixed, [0,1.2,-.8,-.5,.2,1.0]), ("workspace_high", fixed, [0,2.0,-1.5,.7,-.3,.7])])
    return values


def fk_gate(sim, scene, arm_ids, body_id, torch):
    from isaaclab.utils.math import subtract_frame_transforms
    records, passed = [], True
    for name, offsets, left_raw in r1_samples():
        off = torch.tensor(offsets, device=scene["robot"].device, dtype=scene["robot"].data.joint_pos.dtype)
        left = torch.tensor(left_raw, device=off.device, dtype=off.dtype); qp = torch.stack((left, mirror_q(torch,left)))
        reset(sim, scene, arm_ids, off, qp, torch)
        root_pos, root_quat = subtract_frame_transforms(scene["door"].data.root_pos_w, scene["door"].data.root_quat_w, scene["robot"].data.root_pos_w, scene["robot"].data.root_quat_w)
        root_pos_error = torch.max(torch.abs(root_pos - off)); root_quat_error, _, _ = quat_error(torch, root_quat, torch.tensor((1.0,0.0,0.0,0.0),device=off.device,dtype=off.dtype).expand(2,-1))
        if not bool(torch.all(root_pos_error <= 1e-4).item() and torch.all(root_quat_error <= QUAT_TOL).item()):
            raise RuntimeError(f"R2 door-local mirrored root/yaw contract failed: {root_pos.tolist()}, {root_quat.tolist()}.")
        q_readback = scene["robot"].data.joint_pos[:, arm_ids]; qdot_readback = scene["robot"].data.joint_vel[:, arm_ids]
        q_readback_error = torch.max(torch.abs(q_readback - qp), dim=-1).values
        if not bool(torch.all(q_readback_error <= READBACK_TOL).item() and torch.all(torch.abs(qdot_readback) <= READBACK_TOL).item()):
            raise RuntimeError("R2 FK direct joint-state/qdot readback contract failed.")
        pos, quat, _ = tcp_pose(scene, body_id, torch); lpos,lquat = local_pose(scene,pos,quat)
        predicted_pos = lpos[0].clone(); predicted_pos[1] *= -1
        predicted_quat = torch.stack((lquat[0,0],-lquat[0,1],lquat[0,2],-lquat[0,3]))
        pe = torch.max(torch.abs(lpos[1]-predicted_pos)); qe,raw,neg=quat_error(torch,lquat[1],predicted_quat)
        ok = bool((pe <= POS_TOL).item() and (qe <= QUAT_TOL).item()); passed &= ok
        records.append({"sample_id":name,"expected_door_local_root_offsets_xyz_m":[[js(v) for v in row] for row in off.tolist()],"readback_door_local_root_offsets_xyz_m":[[js(v) for v in row] for row in root_pos.tolist()],"readback_door_local_root_quat_wxyz":[[js(v) for v in row] for row in root_quat.tolist()],"left_q_arm_j1_to_j6_rad":[js(x) for x in left.tolist()],"right_q_masked_arm_j1_to_j6_rad":[js(x) for x in qp[1].tolist()],"direct_joint_state_readback_arm_j1_to_j6_rad":[[js(v) for v in row] for row in q_readback.tolist()],"direct_joint_velocity_readback_arm_j1_to_j6_rad_s":[[js(v) for v in row] for row in qdot_readback.tolist()],"joint_state_readback_max_abs_error_rad":js(q_readback_error.max().item()),"root_door_local_position_max_abs_error_m":js(root_pos_error.item()),"root_door_local_quat_max_abs_error":js(root_quat_error.max().item()),"position_component_max_abs_error_m":js(pe.item()),"quaternion_component_max_abs_error":js(qe.item()),"quaternion_raw_error":js(raw.item()),"quaternion_negated_error":js(neg.item()),"pass":ok})
    return passed, records


def target_gate(scene, torch):
    wp,wq,lp,lq,details = geom_target(scene,torch)
    pp=lp[0].clone(); pp[1]*=-1; pq=torch.stack((lq[0,0],-lq[0,1],lq[0,2],-lq[0,3]))
    pe=torch.max(torch.abs(lp[1]-pp)); qe,raw,neg=quat_error(torch,lq[1],pq); ok=bool((pe<=POS_TOL).item() and (qe<=QUAT_TOL).item())
    return ok, {"target_mirror_identity":"PASS" if ok else "FAIL","position_component_max_abs_error_m":js(pe.item()),"quaternion_component_max_abs_error":js(qe.item()),"quaternion_raw_error":js(raw.item()),"quaternion_negated_error":js(neg.item()),"targets":{s:{"world_position_m":[js(x) for x in wp[i].tolist()],"world_quat_wxyz":[js(x) for x in wq[i].tolist()],"door_local_position_m":[js(x) for x in lp[i].tolist()],"door_local_quat_wxyz":[js(x) for x in lq[i].tolist()],"handle_geometry":details[i]} for i,s in enumerate(SIDES)}}


def scan(sim, scene, arm_ids, body_id, offsets, target_pos, target_quat, torch):
    from isaaclab.controllers import DifferentialIKController, DifferentialIKControllerCfg
    from isaaclab.utils.math import axis_angle_from_quat, quat_inv, quat_mul, subtract_frame_transforms
    from gr00t.rl.envs.door.door_open_a2_base import a2_hold_apply_source_offset_to_jacobian, a2_hold_bound_pose_command_step, a2_hold_rotate_jacobian_to_root
    seed=torch.tensor(SEED,device=scene["robot"].device,dtype=scene["robot"].data.joint_pos.dtype); qp=torch.stack((seed,mirror_q(torch,seed)))
    reset(sim,scene,arm_ids,offsets,qp,torch); robot=scene["robot"]
    ctl=DifferentialIKController(DifferentialIKControllerCfg(command_type="pose",use_relative_mode=False,ik_method="dls",ik_params={"lambda_val":.01}),num_envs=2,device=str(robot.device))
    active=torch.ones(2,dtype=torch.bool,device=robot.device); invalid=torch.zeros_like(active); first=[None,None]; last=robot.data.joint_pos[:,arm_ids].clone()
    cond=torch.zeros(2,dtype=last.dtype,device=robot.device)
    for _ in range(IK_STEPS):
        sp,sq,bp=tcp_pose(scene,body_id,torch); rq=robot.data.root_quat_w; rp=robot.data.root_pos_w; bq=robot.data.body_quat_w[:,body_id]
        srp,srq=subtract_frame_transforms(rp,rq,sp,sq); trp,trq=subtract_frame_transforms(rp,rq,target_pos,target_quat); brp,_=subtract_frame_transforms(rp,rq,bp,bq)
        jac=robot.root_physx_view.get_jacobians()[:,body_id-1,:,arm_ids]; jac=a2_hold_rotate_jacobian_to_root(jac,rq); jac=a2_hold_apply_source_offset_to_jacobian(jac,srp-brp)
        sv=torch.linalg.svdvals(jac); cond=torch.maximum(cond,sv[:,0]/sv[:,-1])
        cp,cq,*_=a2_hold_bound_pose_command_step(srp,srq,trp,trq,.005,.03); ctl.set_command(torch.cat((cp,cq),-1)); cur=robot.data.joint_pos[:,arm_ids]; des=ctl.compute(srp,srq,jac,cur)
        lim=robot.data.joint_pos_limits[:,arm_ids]; lower=des<lim[...,0]; upper=des>lim[...,1]; bad=torch.any(lower|upper,-1)
        for i in range(2):
            if bool((active[i]&bad[i]).item()): first[i]={"iteration":_,"q_des_arm_j1_to_j6_rad":[js(v) for v in des[i].tolist()],"hard_limit_lower_violation_mask_arm_j1_to_j6":[bool(v) for v in lower[i].tolist()],"hard_limit_upper_violation_mask_arm_j1_to_j6":[bool(v) for v in upper[i].tolist()],"hard_limit_overshoot_rad_arm_j1_to_j6":[js(v) for v in torch.where(lower[i],lim[i,:,0]-des[i],torch.where(upper[i],des[i]-lim[i,:,1],torch.zeros_like(des[i]))).tolist()]}
        invalid|=active&bad; accepted=active&~bad; last=torch.where(accepted[:,None],des,last)
        q=robot.data.joint_pos.clone(); q[:,arm_ids]=torch.where(accepted[:,None],des,cur); robot.set_joint_position_target(q); robot.write_joint_state_to_sim(q,torch.zeros_like(robot.data.joint_vel)); scene.write_data_to_sim(); sim.forward(); scene.update(sim.get_physics_dt()); active &= ~bad
        if not bool(torch.any(active).item()): break
    sp,sq,_=tcp_pose(scene,body_id,torch); q=robot.data.joint_pos[:,arm_ids]; err=torch.max(torch.abs(q-last),-1).values
    if not bool(torch.all(err<=READBACK_TOL).item()): raise RuntimeError(f"R2 direct-state readback failure: {err.tolist()}")
    lim=robot.data.joint_pos_limits[:,arm_ids]; margins=torch.minimum(q-lim[...,0],lim[...,1]-q); pe=torch.linalg.norm(sp-target_pos,dim=-1); oe=torch.linalg.norm(axis_angle_from_quat(quat_mul(quat_inv(sq),target_quat)),dim=-1)
    finite(torch, "per_side_position_error", pe, (2,)); finite(torch, "per_side_orientation_error", oe, (2,))
    reachable=(~invalid)&(pe<=REACH_POS)&(oe<=REACH_ROT)&(torch.min(margins,-1).values>=MIN_MARGIN)
    if tuple(reachable.shape) != (2,) or reachable.dtype != torch.bool:
        raise RuntimeError(f"R2 reachable must be bool shape (2,), got {reachable.dtype}/{tuple(reachable.shape)}.")
    return {"q":q,"last":last,"margins":margins,"limits":lim,"pe":pe,"oe":oe,"reach":reachable,"invalid":invalid,"first":first,"readback":err,"cond":cond,"source_pos":sp,"source_quat":sq,"target_pos":target_pos,"target_quat":target_quat}


def main(a):
    if a.device!="cuda:0" or os.environ.get("CUDA_VISIBLE_DEVICES")!="0": raise RuntimeError("R2 requires physical GPU0 sole visibility/process-local cuda:0.")
    unexpected = [] if not a.output_root.exists() else [p.name for p in a.output_root.iterdir() if p.name not in {"supervisor.log", "r2_k.log"} and "_failed_" not in p.name]
    if unexpected: raise FileExistsError(f"R2 refuses evidence-bearing output root: {unexpected}")
    r1=r1_module(); from isaacsim import SimulationApp
    app=SimulationApp({"headless":True,"fast_shutdown":True}); sim=None; ok=False
    try:
        sim,scene,torch=scene_make(a,r1); sim.reset(); robot=scene["robot"]; arm_ids,names=robot.find_joints(list(ARM),preserve_order=True); body_ids,bodies=robot.find_bodies("arm_body6_to_gripper",preserve_order=True)
        if tuple(names)!=ARM or bodies!=["arm_body6_to_gripper"] or not robot.is_fixed_base: raise RuntimeError("R2 articulation mapping/fixed-base contract failed.")
        fk_ok,fk_records=fk_gate(sim,scene,arm_ids,body_ids[0],torch)
        central=torch.tensor(((-.76,.22,GRID_Z),(-.76,-.22,GRID_Z)),device=robot.device,dtype=robot.data.joint_pos.dtype); seed=torch.tensor(SEED,device=robot.device,dtype=robot.data.joint_pos.dtype); reset(sim,scene,arm_ids,central,torch.stack((seed,mirror_q(torch,seed))),torch)
        target_ok,target=target_gate(scene,torch) if fk_ok else (False,{"target_mirror_identity":"NOT_RUN"})
        a.output_root.mkdir(parents=True, exist_ok=True); fk_receipt={"schema":"a2_piper_base_v26_4_r2_fk_mirror_identity_v1","status":"RUNTIME_COMPLETE","typed_outcome":"FK_MIRROR_IDENTITY_PASS" if fk_ok else "FK_MIRROR_IDENTITY_FAIL","quaternion_convention":"wxyz; double-cover is compared componentwise after explicit recorded global sign choice","door_local_reflection":"position (x,y,z)->(x,-y,z); quaternion candidate (w,x,y,z)->(w,-x,y,-z)","tolerances":{"position_m":POS_TOL,"quaternion_component":QUAT_TOL},"mirror_mask_arm_j1_to_j6":list(M),"samples":fk_records,"target_mirror_identity":target["target_mirror_identity"],"target_geometry":target}
        (a.output_root/"fk_mirror_identity.json").write_text(json.dumps(fk_receipt,indent=2)+"\n")
        if not fk_ok or not target_ok: raise RuntimeError("R2 hard gate failed; reachability is prohibited.")
        candidates=[]
        for x in GRID_X:
            for y in GRID_Y:
                offsets=torch.tensor(((x,y,GRID_Z),(x,-y,GRID_Z)),device=robot.device,dtype=robot.data.joint_pos.dtype); wp,wq,_,_,target_details=geom_target(scene,torch); result=scan(sim,scene,arm_ids,body_ids[0],offsets,wp,wq,torch)
                candidates.append((f"stage3_x_{x:+.3f}_abs_y_{y:.3f}",offsets,result,target_details))
        bilateral=[c for c in candidates if bool(torch.all(c[2]["reach"]).item())]
        if not bilateral: raise RuntimeError("R2 target-valid frozen grid has no bilateral candidate (NOT_ADMITTED).")
        def score(c):
            r=c[2]; np=float(r["pe"].max().item())/REACH_POS; no=float(r["oe"].max().item())/REACH_ROT
            return (max(np,no),np,no,-float(r["margins"].min().item()))
        choose=min(bilateral,key=score); _,offs,res,_=choose; gap=torch.abs(res["margins"][0]-res["margins"][1]); mx,idx=torch.max(gap,0); j6=torch.abs(res["q"][:,5]-DEFAULT[5]); typed=f"BILATERAL_ASYMMETRIC_AT_{ARM[int(idx)]}" if float(mx)>MARGIN_GAP else ("BILATERAL_ASYMMETRIC_IN_ACTION_OFFSET" if float(torch.abs(j6[0]-j6[1]))>J6_GAP else "BILATERAL_KINEMATICALLY_SYMMETRIC")
        def record(c):
            r=c[2]; default=torch.tensor(DEFAULT,device=robot.device,dtype=r["q"].dtype); action=(r["q"]-default)/ACTION_SCALE; sides={}
            for i,s in enumerate(SIDES):
                detail=c[3][i]; axis=torch.tensor(detail["handle_axis_world_unit"],device=robot.device,dtype=r["q"].dtype); origin=torch.tensor(detail["axis_origin_world_m"],device=robot.device,dtype=r["q"].dtype); radius=r["source_pos"][i]-origin; lever=torch.linalg.norm(radius-torch.dot(radius,axis)*axis)
                sides[s]={"reachable":bool(r["reach"][i]),"invalid_limit":bool(r["invalid"][i]),"first_hard_limit_rejection":r["first"][i],"tcp_source_position_world_m":[js(v) for v in r["source_pos"][i].tolist()],"tcp_source_orientation_world_wxyz":[js(v) for v in r["source_quat"][i].tolist()],"tcp_target_position_world_m":[js(v) for v in r["target_pos"][i].tolist()],"tcp_target_orientation_world_wxyz":[js(v) for v in r["target_quat"][i].tolist()],"position_error_m":js(r["pe"][i]),"orientation_error_rad":js(r["oe"][i]),"joint_limits":{ARM[j]:{"q_rad":js(r["q"][i,j]),"hard_limit_rad":[js(v) for v in r["limits"][i,j].tolist()],"hard_limit_margin_rad":js(r["margins"][i,j])} for j in range(6)},"minimum_hard_limit_margin_rad":js(r["margins"][i].min()),"arm_j4_relative_default_travel_rad":js(r["q"][i,3]-DEFAULT[3]),"arm_j6_relative_default_travel_rad":js(r["q"][i,5]-DEFAULT[5]),"holding_action_vector_arm_j1_to_j6":[js(v) for v in action[i].tolist()],"holding_action_vector_norm":js(torch.linalg.norm(action[i])),"q_readback_max_abs_error_rad":js(r["readback"][i]),"handle_axis_to_gripper_contact_lever_arm_m":js(lever),"target_geometry_reference":"fk_mirror_identity.json#target_geometry"}
            return {"candidate_id":c[0],"root_offsets_door_local_m":[[js(v) for v in row] for row in c[1].tolist()],"sides":sides}
        receipt={"schema":"a2_piper_base_v26_4_r2_wave_k_kinematics_v1","status":"RUNTIME_COMPLETE","typed_outcome":typed,"fk_mirror_identity":"PASS","target_mirror_identity":"PASS","selected_candidate_id":choose[0],"selected_candidate_score":list(score(choose)),"selected_candidate_rule":"bilaterally reachable only; then (max normalized position/orientation, normalized position, normalized orientation, negative global minimum margin)","candidates":[record(c) for c in candidates],"frozen_grid":{"x_m":list(GRID_X),"abs_y_m":list(GRID_Y),"z_m":GRID_Z,"yaw_rad":0.0},"direct_state_forward_only":True}
        (a.output_root/"k_kinematics.json").write_text(json.dumps(receipt,indent=2)+"\n"); ok=True; return receipt
    finally:
        if ok: app.close()
        elif sim is not None: sim.clear_all_callbacks(); sim.clear_instance()


if __name__=="__main__":
    try: print(json.dumps(main(args()),indent=2))
    except BaseException: traceback.print_exc(); raise
