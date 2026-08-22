# V26 Reward Lineage Review

**完成时间：** 2026-08-21 18:37 HKT  
**范围：** `base_v26` formal optimizer update 前的一次性 focused comparison  
**authority：** 当前 `A2_Piper` source/config；不是 historical checkpoint 行为推断

## Runtime binding

| Surface | Current binding | v26 decision |
|---|---|---|
| experiment root | `exp/wbmanip/door_open_a2_base_lstm.yaml` | 继续使用 frozen A2_Base low-level policy；high-level PPO fresh init |
| environment | `DoorPregrasp` in `door_open_a2_base.py` | 保留当前 six-stage state machine 与 strict Stage2 grasp completion |
| staged reset | `StagedTaskBase` per-env ring buffers | 每个 process 从空 buffer 开始；不加载旧 checkpoint/env state |
| door construction | `DoorSpawnerCfg` through `get_TaskObjCfgDict_for_door_config()` | 新增 v26 exact side assignment；仍用 high-level cfg replacement |
| reward registry | `LeggedRobotBase._prepare_reward_function()` resolves nonzero YAML keys to `_reward_<term>` | 新建独立 acquisition registry；formal 前冻结 |
| release/handoff | `_a2_stage4_release_gate`, `_get_a2_stage34_hold_income_mask()`, `a2_apply_stage4_target_root_distance_scale()` | 显式保留 v13.1 release latch、hold-income suppression 与 released target-root routing |

## Focused lineage comparison

| Capability | DoorMan/current base | v12 scratch | v13_A / v13.1 first full-chain route | v23/v25 warm-era registry | v26 acquisition decision |
|---|---|---|---|---|---|
| high-level initialization | base recipe permits normal experiment loading | `checkpoint: null`, `full`, `auto_load_latest: false` | policy-only warm-start | policy-only G7/v22 warm-start | use v12 scratch contract; no actor/critic/LSTM/RMS/optimizer/snapshot inheritance |
| Stage0–2 dense guidance | current A2 base contains repaired walk/pregrasp/grasp bundle | present, but historical scratch predates later control-step grasp fixes | retained | retained | retain current repaired dense bundle and H=5 control-step strict grasp |
| handle depression | `push_door_handle=+6` in current base | enabled | disabled after warm-start | disabled in v23/v25 | restore `+6` because scratch needs an explicit handle-direction signal |
| hinge progress | `push_door_hinge=+6` | enabled | enabled | enabled | retain `+6` in Stage3/4 |
| grasp-to-opening bridge | base defaults keep v13 terms at zero | absent | `unlatch_hold=3`, `hold_and_drive=8`, Stage3 base unlocked | retained | retain v13 terms and active planar base |
| gripper capability | current robot baseline is `80/3`, effort `10/10`, PhysX velocity iter 1 | `80/3`, velocity iter 1 | `800/25`, velocity iter 2 | warm configs inherit mature capability | use the proven v13.1 acquisition capability `800/25`, effort `10/10`, velocity iter 2, frozen across cells |
| release/handoff | current source contains release latch/suppression | source capability exists but v12 recipe did not establish full chain | v13.1 adds hinge `1.2 rad` release and target-root handoff | retained plus later behavior economics | retain v13.1 release/handoff only; keep later corridor/carry economics off |
| mature behavior terms | current base defaults mostly zero | absent | absent | corridor, carry, clearance, fling, body/posture pricing active in later registries | set all v16+ behavior-aesthetic terms to zero during acquisition |
| force randomization | native v24 backend default-off | off | off | P10 used by v25 | R0 off; moderate P00/P02/P05 with small P10 only after bilateral goal exists |
| posture/planar route | FULL actions available; base may be locked by config | locked Stage3 | Stage3 unlocked | v25 FULL/RP0 causality | FULL posture, no posture tax, Stage3 planar unlocked |

## Source conclusions frozen for R0

1. `push_door_handle`, `push_door_hinge`, `a2_stage3_unlatch_hold`, and
   `a2_stage3_stage4_hold_and_drive` are bound to current runtime functions.
2. Current A2 Stage2→3 accepts only strict control-step grasp completion; the
   historical door-open bypass is diagnostics-only on the A2 path.
3. Release suppression is implemented in source, not by a threshold string
   alone: after the Stage4 latch, hold/grasp/hinge-position income is masked and
   target-root routing switches to released behavior.
4. `push_door_force` has no authoritative generic A2 implementation and remains
   zero.
5. v26 R0 therefore uses current repaired Stage0–2 guidance, restores the
   scratch handle term, retains v13/v13.1 full-chain capability, and excludes
   later behavior-aesthetic taxes.

