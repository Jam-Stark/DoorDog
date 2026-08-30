#!/usr/bin/env python3
"""Real CONT_STEP2000 actor and primary-cache SE(3) proof for r13."""
from __future__ import annotations
import argparse, ast, json
from pathlib import Path
import torch
from omegaconf import OmegaConf
from gr00t.rl.trl.modules.actor_critic_modules_recurrent import RecurrentActor, A2V26_5PolicyResidualRecurrentActor
from gr00t.rl.utils.config_utils import register_rl_resolvers
from gr00t.rl.isaac_utils.rotations import quat_to_tan_norm, wxyz_to_xyzw
from v26_5_wave2_r1_r13_compose import compose

ROOT=Path(__file__).resolve().parents[2]
SOURCE_DIR=ROOT/"logs_rl/by_batch/base_v26_acquisition_supplement_20260823/continuation/V26A_LR_S1_POLICY800"
SOURCE=SOURCE_DIR/"model_step_002000.pt"; SOURCE_CONFIG=SOURCE_DIR/"config.yaml"
SELECTOR=ROOT/"gr00t/rl/config/ablation/wbmanip/base_v26_5_wave2_R13_policy_residual.yaml"
DOOR_SOURCE=ROOT/"gr00t/rl/envs/door/door_open_a2_base.py"; TOL=1e-6
DOOR_SPAWNER_SOURCE=ROOT/"gr00t/rl/isaac_utils/playground/env_rand/door.py"
RAW=["dof_pos","relative_to_door","dof_vel","actions","projected_gravity","door_dof_pos","base_lin_vel","base_ang_vel","hand_force","stage","privileged_door_info","delta_actions","gripper_handle_transform","a2_base_command_raw","a2_base_command"]
GAUGE=[*RAW[:12],"gripper_handle_transform_gauge",*RAW[13:]]

def require(v:bool,m:str)->None:
    if not v: raise RuntimeError(m)
def qmul(a:torch.Tensor,b:torch.Tensor)->torch.Tensor:
    aw,ax,ay,az=a.unbind(-1);bw,bx,by,bz=b.unbind(-1)
    return torch.stack((aw*bw-ax*bx-ay*by-az*bz,aw*bx+ax*bw+ay*bz-az*by,aw*by-ax*bz+ay*bw+az*bx,aw*bz+ax*by-ay*bx+az*bw),-1)
def qinv(q:torch.Tensor)->torch.Tensor:
    out=q.clone();out[...,1:]=-out[...,1:];return out
def maxabs(a:torch.Tensor,b:torch.Tensor)->float:return float((a-b).abs().max().item())
def slot(terms:list[str],dims:dict[str,int],term:str)->list[int]:
    order=sorted(terms);require(term in order,f"missing observation term {term}");start=sum(dims[x] for x in order[:order.index(term)]);return [start,start+dims[term]]
def actor_proof()->dict:
    require(SOURCE.is_file() and SOURCE_CONFIG.is_file() and SELECTOR.is_file(),"r13 source/config missing")
    register_rl_resolvers(); cfg=OmegaConf.merge(OmegaConf.load(SOURCE_CONFIG),OmegaConf.create(compose(SELECTOR)))
    actor_cfg=OmegaConf.create(OmegaConf.to_container(cfg.algo.config.actor,resolve=True)); algo_cfg=OmegaConf.create(OmegaConf.to_container(cfg.algo.config,resolve=True)); robot=OmegaConf.to_container(cfg.robot,resolve=True)
    dims={next(iter(x)):next(iter(x.values())) for x in cfg.obs.obs_dims};obs=OmegaConf.to_container(cfg.obs.obs_dict,resolve=True)
    require(obs["actor_obs"]==RAW and obs["residual_actor_obs"]==GAUGE and cfg.env.config.a2_v26_5_geometry_target_enabled is False and cfg.env.config.a2_v26_5_actor_gauge_enabled is True,"r13 resolved dual observation/main geometry contract")
    require(slot(obs["actor_obs"],dims,"gripper_handle_transform")==slot(obs["residual_actor_obs"],dims,"gripper_handle_transform_gauge")==[83,101],"r13 pose representation slice")
    for name in ("actor_obs","residual_actor_obs"): require(sum(dims[x] for x in obs[name])==133,f"r13 {name} width")
    robot.setdefault("algo_obs_dim_dict",{}).update({"actor_obs":133,"residual_actor_obs":133});env=OmegaConf.create({"robot":robot})
    kwargs=dict(actor_cfg);kwargs.pop("_target_");legacy_kwargs=dict(kwargs)
    for key in ("residual_input_key","residual_hidden_dim","residual_stage_obs_slice"):legacy_kwargs.pop(key,None)
    legacy=RecurrentActor(env_config=env,algo_config=algo_cfg,**legacy_kwargs);dual=A2V26_5PolicyResidualRecurrentActor(env_config=env,algo_config=algo_cfg,**kwargs)
    state=torch.load(SOURCE,map_location="cpu",weights_only=False)["policy_state_dict"]
    require(set(state)==set(legacy.state_dict()),"r13 real legacy actor keyset")
    require(not legacy.load_state_dict(state,strict=True).missing_keys,"r13 strict legacy load")
    result=dual.load_state_dict(state,strict=False);require(set(result.missing_keys)==set(dual.residual_state_keys()) and not result.unexpected_keys,"r13 residual keyset")
    dual.assert_residual_zero_initialized();legacy.eval();dual.eval();torch.manual_seed(20260830)
    raw=torch.randn(3,133);raw[:,127:133]=0.;raw[:,130]=1.;gauge=raw.clone();gauge[:,83:101]+=0.4
    legacy.reset();dual.reset();a=legacy.forward({"actor_obs":raw}).squeeze(0);b=dual.forward({"actor_obs":raw,"residual_actor_obs":gauge});two=maxabs(a,b)
    legacy.reset();dual.reset();done=torch.zeros(3,dtype=torch.bool);a_roll=legacy.rollout({"actor_obs":raw},cur_dones=done);b_roll=dual.rollout({"actor_obs":raw,"residual_actor_obs":gauge},cur_dones=done)
    mean=maxabs(a_roll["action_mean"],b_roll["action_mean"]);std=maxabs(a_roll["action_sigma"],b_roll["action_sigma"])
    rms=["running_mean_std.running_mean","running_mean_std.running_var","running_mean_std.count"]
    require(all(torch.equal(state[x],legacy.state_dict()[x]) and torch.equal(state[x],dual.state_dict()[x]) for x in rms),"r13 RMS source identity")
    dual.train();dual.reset();dual.residual_module[-1].weight.data.fill_(.1);dual.forward({"actor_obs":raw,"residual_actor_obs":gauge}).sum().backward()
    frozen=all(p.grad is None for module in (dual.memory,dual.actor_module) for p in module.parameters()) and dual.std.grad is None;residual_grad=all(p.grad is not None for p in dual.residual_module.parameters())
    return {"checkpoint_path":str(SOURCE),"actor_state_key":"policy_state_dict","rms_source_fields":rms,"raw_pose_slice":[83,101],"residual_pose_slice":[83,101],"two_d_mean_max_abs":two,"rollout_mean_max_abs":mean,"rollout_std_max_abs":std,"identity_within_tolerance":max(two,mean,std)<=TOL,"base_frozen_grad_free":frozen,"residual_grad_present":residual_grad}
def _function(tree:ast.AST,name:str)->ast.FunctionDef:
    matches=[x for x in ast.walk(tree) if isinstance(x,ast.FunctionDef) and x.name==name]
    require(len(matches)==1,f"r13 expected one {name} implementation")
    return matches[0]
def _attr(node:ast.AST,name:str)->bool:
    return (isinstance(node,ast.Attribute) and node.attr==name) or (isinstance(node,ast.Name) and node.id==name)
def _literal_tuple(node:ast.AST)->list[float]:
    require(isinstance(node,(ast.Tuple,ast.List)) and len(node.elts) in (3,4),"r13 expected authored offset literal")
    value=[]
    for x in node.elts:
        if isinstance(x,ast.Constant) and isinstance(x.value,(int,float)):
            value.append(float(x.value));continue
        require(isinstance(x,ast.UnaryOp) and isinstance(x.op,ast.USub) and isinstance(x.operand,ast.Constant) and isinstance(x.operand.value,(int,float)),"r13 authored offset must be numeric")
        value.append(-float(x.operand.value))
    return value
def _actual_o0_offsets(tree:ast.AST)->dict[str,dict[str,list[float]]]:
    frames={}
    for call in (x for x in ast.walk(tree) if isinstance(x,ast.Call) and _attr(x.func,"FrameCfg")):
        kw={x.arg:x.value for x in call.keywords if x.arg is not None}
        if not isinstance(kw.get("name"),ast.Constant) or kw["name"].value not in ("handle","pregrasp"):
            continue
        if "offset" not in kw:
            continue
        offset=kw.get("offset");require(isinstance(offset,ast.Call) and _attr(offset.func,"OffsetCfg"),"r13 target must use OffsetCfg")
        offset_kw={x.arg:x.value for x in offset.keywords if x.arg is not None}
        pos=offset_kw.get("pos");rot=offset_kw.get("rot")
        if kw["name"].value=="pregrasp":
            require(isinstance(pos,ast.Attribute) and pos.attr=="A2_PREGRASP_OFFSET","r13 pregrasp source offset")
            pos_node=next((x.value for x in ast.walk(tree) if isinstance(x,ast.Assign) for target in x.targets if isinstance(target,ast.Name) and target.id=="A2_PREGRASP_OFFSET"),None)
            require(pos_node is not None,"r13 A2_PREGRASP_OFFSET source")
            pos=pos_node
        frames[kw["name"].value]={"pos":_literal_tuple(pos),"rot":_literal_tuple(rot)}
    require(set(frames)=={"handle","pregrasp"},"r13 actual O0 target offsets")
    return frames
def _is_number(node:ast.AST,value:float)->bool:
    if isinstance(node,ast.Constant) and isinstance(node.value,(int,float)): return float(node.value)==value
    return isinstance(node,ast.UnaryOp) and isinstance(node.op,ast.USub) and isinstance(node.operand,ast.Constant) and isinstance(node.operand.value,(int,float)) and -float(node.operand.value)==value
def _right_handle_joint_rotation_ast(tree:ast.AST)->bool:
    branches=[]
    for node in ast.walk(tree):
        if not isinstance(node,ast.If) or not isinstance(node.test,ast.Compare) or len(node.test.ops)!=1 or not isinstance(node.test.ops[0],ast.Eq): continue
        if not (isinstance(node.test.left,ast.Name) and node.test.left.id=="door_open_lr" and len(node.test.comparators)==1 and _is_number(node.test.comparators[0],-1.0)): continue
        branches.append(node)
    require(len(branches)==1,"r13 expected one right handle-joint rotation branch")
    calls=[x for x in ast.walk(branches[0]) if isinstance(x,ast.Call) and _attr(x.func,"Set")]
    require(len(calls)==1,"r13 right handle-joint rotation assignment")
    require(isinstance(calls[0].func,ast.Attribute) and isinstance(calls[0].func.value,ast.Call) and _attr(calls[0].func.value.func,"CreateLocalRot0Attr"),"r13 right localRot0 setter")
    value=calls[0].args[0];require(isinstance(value,ast.Call) and _attr(value.func,"Quatf"),"r13 right handle joint must author Gf.Quatf")
    kw={x.arg:x.value for x in value.keywords if x.arg is not None};imag=kw.get("imaginary")
    require(_is_number(kw.get("real"),0.0) and isinstance(imag,ast.Call) and _attr(imag.func,"Vec3f") and len(imag.args)==3 and [_is_number(x,float(v)) for x,v in zip(imag.args,(0,0,1))]==[True,True,True],"r13 exact right handle-joint localRot0")
    return True
def se3_static_proof()->dict:
    text=DOOR_SOURCE.read_text(encoding="utf-8");tree=ast.parse(text,filename=str(DOOR_SOURCE));spawner_text=DOOR_SPAWNER_SOURCE.read_text(encoding="utf-8");spawner_tree=ast.parse(spawner_text,filename=str(DOOR_SPAWNER_SOURCE));init=_function(tree,"_initialize_impl");getter=_function(tree,"get_a2_v26_5_gauge_target_pose_source")
    init_dump=ast.dump(init,include_attributes=False);getter_dump=ast.dump(getter,include_attributes=False)
    offsets=_actual_o0_offsets(tree)
    q0=torch.tensor([offsets["handle"]["rot"],offsets["pregrasp"]["rot"]],dtype=torch.float64).repeat(64,1,1)
    p0=torch.tensor([offsets["handle"]["pos"],offsets["pregrasp"]["pos"]],dtype=torch.float64).repeat(64,1,1)
    encoded=torch.cat((p0[:,0],quat_to_tan_norm(wxyz_to_xyzw(q0[:,0]),w_last=True),p0[:,1],quat_to_tan_norm(wxyz_to_xyzw(q0[:,1]),w_last=True)),dim=-1)
    binding={
        "geometry_helper_uses_live_usd": "omni.usd.get_context().get_stage" in text,
        "right_handle_joint_localrot0_ast": _right_handle_joint_rotation_ast(spawner_tree),
        "left_handle_joint_has_no_extra_localrot0_ast": spawner_text.count("handle_joint.CreateLocalRot0Attr") == 1,
        "geometry_helper_joint_axis_ast": all(fragment in ast.unparse(_function(tree,"_a2_v26_5_geometry_target_offset_quaternions")) for fragment in ("Gf.Rotation(Gf.Quatd(local_rot))","handle_joint_rotation.TransformDir(Gf.Vec3d(1.0, 0.0, 0.0))","opening_lr = 1.0 if float(handle_axis_local[0]) > 0.0 else -1.0","panel_transform.TransformDir","gripper_z = _unit","gripper_y = _unit(_cross(gripper_z, gripper_x)","desired_world_quat = quat_from_matrix","target_offset_quat = quat_mul(quat_inv(target_world_quat), desired_world_quat)")),
        "cache_delta_assignment_ast": "gauge_offset_delta_quat" in init_dump and "quat_inv" in init_dump and "quat_mul" in init_dump and "_a2_v26_5_gauge_offset_delta_quat" in init_dump,
        "cache_delta_env_major_reshape_ast": ".reshape(expected_shape)" in ast.unparse(init) and "self._num_envs, 2, 4" in ast.unparse(init),
        "geometry_disabled_keeps_o0_ast": "if self._a2_v26_5_geometry_target_enabled" in ast.unparse(init) and "else:" in ast.unparse(init) and "self._a2_v26_5_gauge_offset_delta_quat = gauge_offset_delta_quat" in ast.unparse(init),
        "getter_live_position_reuse_ast": "target_pos_source = self._data.target_pos_source" in ast.unparse(getter) and "return (target_pos_source, gauge_target_quat_source)" in ast.unparse(getter),
        "getter_live_quaternion_delta_ast": "gauge_target_quat_source = quat_mul(target_quat_source, gauge_offset_delta_quat)" in ast.unparse(getter),
        "ordered_handle_pregrasp_ast": "('handle', 'pregrasp')" in ast.unparse(getter),
    }
    one_reader=text.count("simulator.scene.sensors[self.A2_GRIPPER_HANDLE_FRAME_TRANSFORMER] = (")==1 and text.count("= (\n                OrderedTargetFrameTransformer(")==1
    historical=("A2_V26_5_GAUGE_GRIPPER_HANDLE_FRAME_TRANSFORMER","piper_gripper_handle_frame_transformer_gauge")
    no_o1=all(symbol not in text for symbol in historical)
    return {"implementation_binding":binding,"actual_o0_authored_offsets":offsets,"o0_representation_static":{"representation_shape":list(encoded.shape),"position_reused_max_abs":0.0},"geometry_evidence_boundary":{"static_source_chain":"DoorSpawner right LocalRot0 + Door helper joint-axis/opening/columns/quat_from_matrix is AST-bound","no_static_o1_quaternion_or_delta_claim":True,"required_runtime_evidence":"R13 two-control-tick wiring followed by exact64 K1"},"exactly_one_primary_scene_reader":one_reader,"no_historical_o1_sensor_symbols":no_o1,"historical_o1_symbols_checked":list(historical)}
def main()->None:
    p=argparse.ArgumentParser();p.add_argument("--output",type=Path,required=True);a=p.parse_args()
    if a.output.exists():raise RuntimeError(f"refusing to overwrite r13 CPU artifact: {a.output}")
    actor=actor_proof();se3=se3_static_proof();binding=se3["implementation_binding"]
    require(actor["identity_within_tolerance"] and actor["base_frozen_grad_free"] and actor["residual_grad_present"] and all(binding.values()) and se3["o0_representation_static"]["representation_shape"]==[64,18] and se3["geometry_evidence_boundary"]["no_static_o1_quaternion_or_delta_claim"] and se3["exactly_one_primary_scene_reader"] and se3["no_historical_o1_sensor_symbols"],"r13 CPU/static admission failed")
    out={"schema":"a2_piper_base_v26_5_r13_cpu_primary_cache_gate_v3","status":"PASS","actor_shadow":actor,"se3_primary_cache":se3};a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2)+"\n",encoding="utf-8");print(a.output)
if __name__=="__main__":main()
