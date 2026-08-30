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
RUN_ID = "v26_5_wave2_r1_policy_residual_20260830_r4"

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
    k1=r.get("K1",{}); require(k1.get("view_trace_contract")=={"control":{"terms":["push_door_handle","a2_stage3_unlatch_hold","push_door_hinge","a2_stage3_stage4_hold_and_drive"],"a2_v26_2_handle_depression_scale":0.0,"a2_v26_3_handle_creation_scale":0.0},"dual":{"terms":["a2_stage3_handle_creation","a2_stage3_unlatch_hold","push_door_hinge","a2_stage3_stage4_hold_and_drive"],"a2_v26_2_handle_depression_scale":0.0,"a2_v26_3_handle_creation_scale":6.0}}, "K1 view-specific trace/scale contract mismatch")
    paths={}
    for item in a.config:
        name,sep,path=item.partition("="); require(sep and name not in paths, "invalid duplicate R1 config"); paths[name]=Path(path)
    require(set(paths)=={f"R1_S{s}_{k}" for s in (0,1) for k in ("train","eval")}, "R1 requires four resolved configs")
    for name,path in paths.items():
        table=flatten(yaml.safe_load(path.read_text(encoding="utf-8"))); seed=int(name[4])
        expected={"seed":seed,"env.config.a2_v26_side_permutation_seed":seed,"checkpoint_load_mode":"policy_only","policy_only_load_actor_rms":True,"auto_load_latest":False,"env.config.a2_v26_4_side_canonicalization_enabled":False,"env.config.a2_v26_5_geometry_target_enabled":True,"env.config.a2_v26_5_stage3_delta_rebase_enabled":False,"env.config.a2_v26_5_actor_gauge_enabled":True,"algo.config.actor._target_":"gr00t.rl.trl.modules.actor_critic_modules_recurrent.A2V26_5PolicyResidualRecurrentActor","algo.config.actor.residual_stage_obs_slice":[127,133],"algo.config.actor.residual_hidden_dim":128}
        for key,value in expected.items(): require(table.get(key)==value, f"{name}: {key}={table.get(key)!r}, expected {value!r}")
        if name.endswith("train"): require(table.get("algo.trl.num_total_batches")==250, f"{name}: train must be 250 batches")
    actor_text=ACTOR_SOURCE.read_text(encoding="utf-8")
    start=actor_text.index("class A2V26_5PolicyResidualRecurrentActor")
    end=actor_text.index("class RecurrentCritic", start)
    residual_actor=actor_text[start:end]
    require("self.std.requires_grad_(False)" in residual_actor, "R1 residual actor must freeze inherited std")
    require("self.running_mean_std.freeze()" in residual_actor, "R1 residual actor must freeze inherited RMS")
    require("mean[..., 5:12]" in residual_actor and "nn.init.zeros_(self.residual_module[-1].weight)" in residual_actor and "nn.init.zeros_(self.residual_module[-1].bias)" in residual_actor, "R1 residual mean/zero-init source contract mismatch")
    trainer_text=TRAINER_SOURCE.read_text(encoding="utf-8")
    require("def _load_a2_v26_5_policy_residual_state" in trainer_text and "legacy_exact_without_residual" in trainer_text and "allow_legacy=True" in trainer_text, "R1 legacy policy-only loader contract missing")
    print(a.registry)
if __name__ == "__main__": main()
