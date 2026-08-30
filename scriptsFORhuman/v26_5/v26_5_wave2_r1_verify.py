#!/usr/bin/env python3
"""Fail-fast static contract verifier for Wave2 R1."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any
import yaml

ROOT = Path(__file__).resolve().parents[2]
ACTOR_SOURCE = ROOT / "gr00t/rl/trl/modules/actor_critic_modules_recurrent.py"
TRAINER_SOURCE = ROOT / "gr00t/rl/trl/trainer/ppo_trainer_a2_base_api.py"
EVAL_SOURCE = ROOT / "gr00t/rl/eval_agent_trl.py"
K1_SIDE_SCRIPT = ROOT / "scriptsFORhuman/v26_5/v26_5_wave2_r1_k1_eval_side.sh"
REDUCER_SOURCE = ROOT / "scriptsFORhuman/v26_5/v26_5_wave2_r1_reduce.py"
RUN_ID = "v26_5_wave2_r1_policy_residual_20260830_r11"
SOURCE = ROOT / "logs_rl/by_batch/base_v26_acquisition_supplement_20260823/continuation/V26A_LR_S1_POLICY800/model_step_002000.pt"

def require(value: bool, message: str) -> None:
    if not value: raise RuntimeError(message)
def flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k,v in value.items(): out.update(flatten(v, f"{prefix}.{k}" if prefix else k))
        return out
    return {prefix: value}
def main() -> None:
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--registry",type=Path,required=True); p.add_argument("--config",action="append",required=True); a=p.parse_args()
    r=json.loads(a.registry.read_text(encoding="utf-8")); require(r.get("schema")=="a2_piper_base_v26_5_wave2_r1_registry_v1" and r.get("status")=="PREREGISTERED_NOT_RUN" and r.get("run_id")==RUN_ID, "R1 registry mismatch")
    k1=r.get("K1",{}); require(k1.get("view_trace_contract")=={"control":{"terms":["push_door_handle","a2_stage3_unlatch_hold","push_door_hinge","a2_stage3_stage4_hold_and_drive"],"a2_v26_2_handle_depression_scale":0.0,"a2_v26_3_handle_creation_scale":0.0},"dual":{"terms":["push_door_handle","a2_stage3_unlatch_hold","push_door_hinge","a2_stage3_stage4_hold_and_drive"],"a2_v26_2_handle_depression_scale":0.0,"a2_v26_3_handle_creation_scale":0.0}}, "K1 common active-reward trace/scale contract mismatch")
    require(k1.get("runtime_load_contract")=={"control":{"checkpoint_load_mode":"policy_only","a2_v23_p06_policy_only":False,"a2_v26_5_policy_only_identity_control":True,"a2_v26_5_policy_only_residual":False,"actor_keyset_contract":"legacy_identity_control_exact","actor_strict":True},"dual":{"checkpoint_load_mode":"policy_only","a2_v23_p06_policy_only":False,"a2_v26_5_policy_only_identity_control":False,"a2_v26_5_policy_only_residual":True,"actor_keyset_contract":"legacy_exact_without_residual","actor_strict":False},"receipt_schema":"a2_piper_base_v26_5_runtime_load_receipt_v1","required_artifacts":["a2_v26_5_runtime_load_receipt.json","a2_eval_diagnostic_metadata.json"],"metadata_reward_terms":["push_door_handle","a2_stage3_unlatch_hold","push_door_hinge","a2_stage3_stage4_hold_and_drive"]}, "K1 runtime load/receipt contract mismatch")
    k1_side_text=K1_SIDE_SCRIPT.read_text(encoding="utf-8")
    for required in ("identity_control=true", "residual_policy_only=false", "identity_control=false", "residual_policy_only=true", '++algo.config.eval.a2_v23_p06_policy_only=false ++algo.config.eval.a2_v26_5_policy_only_identity_control="$identity_control" ++algo.config.eval.a2_v26_5_policy_only_residual="$residual_policy_only" ++algo.config.eval.a2_v26_5_runtime_load_receipt=true', "a2_v26_5_runtime_load_receipt.json", "a2_eval_diagnostic_metadata.json"):
        require(required in k1_side_text, f"K1 control/dual runtime receipt command contract missing: {required}")
    reducer_text=REDUCER_SOURCE.read_text(encoding="utf-8")
    for required in ("a2_v26_5_runtime_load_receipt.json", "legacy_identity_control_exact", "legacy_exact_without_residual", "a2_v23_p06_policy_only", "R1_SYNTHETIC_BAD_RECEIPT_FLAGS_AND_MISSING_REJECTED", "R1_SYNTHETIC_UNEQUAL_WINDOW_TYPED_FAILURE_PASS"):
        require(required in reducer_text, f"K1 reducer runtime receipt binding missing: {required}")
    require(k1.get("cells")==[{"label":"K1_S0","seed":0,"physical_gpu":4},{"label":"K1_S1","seed":1,"physical_gpu":5}], "K1 GPU mapping mismatch")
    require(r.get("R1",{}).get("cells")==[{"label":"R1_S0","seed":0,"physical_gpu":4},{"label":"R1_S1","seed":1,"physical_gpu":5}], "R1 GPU mapping mismatch")
    require(r.get("R1",{}).get("actor_hydra_listconfig_contract")=={"selector_value":[127,133],"validator_sequence_type":"collections.abc.Sequence","forbidden_sequence_types":["str","bytes"],"required_length":2,"required_element_type":"int"}, "R1 Hydra ListConfig actor-construction contract mismatch")
    require(r.get("R1",{}).get("static_eval_compose")=={"ablation_partial":"R1_eval_ablation_partial.yaml","host_entrypoint":"gr00t.rl.eval_agent_trl","host_hydra_config_path":str(SOURCE.parent),"host_hydra_config_name":"config","host_resolve_args":["--cfg","job","--resolve"],"runtime_merge":"OmegaConf.merge(train_config, override_config)","checkpoint_load_mode":"policy_only"}, "R1 two-stage eval compose contract mismatch")
    paths={}
    for item in a.config:
        name,sep,path=item.partition("="); require(sep and name not in paths, "invalid duplicate R1 config"); paths[name]=Path(path)
    require(set(paths)=={"R1_eval_ablation_partial"} | {f"R1_S{s}_train" for s in (0,1)} | {f"R1_S{s}_eval_{side}" for s in (0,1) for side in ("left","right")}, "R1 requires one eval partial plus two train and four eval-entry resolved configs")
    partial=flatten(yaml.safe_load(paths["R1_eval_ablation_partial"].read_text(encoding="utf-8")))
    partial_expected={"v26_schema":"a2_piper_base_v26_5_wave2_r1_eval_policy_residual_v1","env.config.a2_v26_5_geometry_target_enabled":True,"env.config.a2_v26_5_actor_gauge_enabled":True,"algo.config.actor._target_":"gr00t.rl.trl.modules.actor_critic_modules_recurrent.A2V26_5PolicyResidualRecurrentActor"}
    for key,value in partial_expected.items(): require(partial.get(key)==value, f"R1 eval partial: {key}={partial.get(key)!r}, expected {value!r}")
    for name,path in paths.items():
        if name == "R1_eval_ablation_partial": continue
        table=flatten(yaml.safe_load(path.read_text(encoding="utf-8"))); seed=int(name[4])
        expected={"seed":seed,"env.config.a2_v26_side_permutation_seed":seed,"checkpoint_load_mode":"policy_only","policy_only_load_actor_rms":True,"auto_load_latest":False}
        if name.endswith("train"):
            expected.update({"env.config.a2_v26_4_side_canonicalization_enabled":False,"env.config.a2_v26_5_geometry_target_enabled":True,"env.config.a2_v26_5_stage3_delta_rebase_enabled":False,"env.config.a2_v26_5_actor_gauge_enabled":True,"algo.config.actor._target_":"gr00t.rl.trl.modules.actor_critic_modules_recurrent.A2V26_5PolicyResidualRecurrentActor","algo.config.actor.residual_stage_obs_slice":[127,133],"algo.config.actor.residual_hidden_dim":128})
        for key,value in expected.items(): require(table.get(key)==value, f"{name}: {key}={table.get(key)!r}, expected {value!r}")
        checkpoint=table.get("checkpoint")
        require(isinstance(checkpoint, str), f"{name}: checkpoint must be a path string")
        checkpoint_path=Path(checkpoint)
        if not checkpoint_path.is_absolute(): checkpoint_path=ROOT / checkpoint_path
        require(checkpoint_path.resolve() == SOURCE, f"{name}: checkpoint does not resolve to CONT_STEP2000")
        if name.endswith("train"): require(table.get("algo.trl.num_total_batches")==250, f"{name}: train must be 250 batches")
        else:
            side=name.rsplit("_", 1)[1]
            require(table.get("env.config.a2_v26_door_open_lr")==side, f"{name}: eval side mismatch")
    eval_text=EVAL_SOURCE.read_text(encoding="utf-8")
    require("OmegaConf.merge(train_config, override_config)" in eval_text, "eval entrypoint no longer merges checkpoint host with eval selector override")
    actor_text=ACTOR_SOURCE.read_text(encoding="utf-8")
    start=actor_text.index("class A2V26_5PolicyResidualRecurrentActor")
    end=actor_text.index("class RecurrentCritic", start)
    residual_actor=actor_text[start:end]
    require("self.std.requires_grad_(False)" in residual_actor, "R1 residual actor must freeze inherited std")
    require("self.running_mean_std.freeze()" in residual_actor, "R1 residual actor must freeze inherited RMS")
    require("from collections.abc import Sequence" in actor_text and "not isinstance(residual_stage_obs_slice, Sequence)" in residual_actor and "self.residual_stage_obs_slice = tuple(residual_stage_obs_slice)" in residual_actor, "R1 actor must accept Hydra ListConfig as a Sequence then freeze its exact slice")
    require("mean[..., 5:12]" in residual_actor and "nn.init.zeros_(self.residual_module[-1].weight)" in residual_actor and "nn.init.zeros_(self.residual_module[-1].bias)" in residual_actor, "R1 residual mean/zero-init source contract mismatch")
    trainer_text=TRAINER_SOURCE.read_text(encoding="utf-8")
    require("def _load_a2_v26_5_policy_residual_state" in trainer_text and "legacy_exact_without_residual" in trainer_text and "allow_legacy=True" in trainer_text, "R1 legacy policy-only loader contract missing")
    print(a.registry)
if __name__ == "__main__": main()
