---
name: base-v25-mirrored-teacher-force-causality
scope: A2+Piper left/right push-door Teacher adaptation and matched posture/planar causality
status: completed_retain_g7
last_updated: 2026-08-21 16:06 HKT
owned_paths:
  - memory/a2-piper/MEMORY.md
  - memory/a2-piper/base-v25-mirrored-teacher-force-causality/description.md
  - memory/a2-piper/base-v25-mirrored-teacher-force-causality/TODO.md
  - memory/a2-piper/base-v25-mirrored-teacher-force-causality/DONE.md
  - scriptsFORhuman/v25/a2_piper_base_v25_execution_ledger_20260821.md
read_when:
  - implementing or executing base_v25
  - changing push-door left/right handedness or choosing the post-v25 Teacher
  - implementing the matched posture/planar intervention
---

# base_v25 Mirrored Teacher and Posture Causality

## Purpose

本 entry 路由 base_v25：保持 `door_open_io="out"`，先证明 deterministic LEFT-handle path，再在 owner M1 确认后进入 mixed LEFT/RIGHT、G7 warm adaptation、v24 friction load selection 与 matched stable-grasp 2x2 intervention。

## Authority and current state

- Canonical plan: `scriptsFORhuman/v25/a2_piper_base_v25_execution_plan_R2_20260820.md`。
- Execution ledger: `scriptsFORhuman/v25/a2_piper_base_v25_execution_ledger_20260821.md`。
- Frozen Teacher anchor: `logs_rl/a2_piper_full_stage_a2_base/base_v23/seed0/G7/model_step_001500.pt` (`A1_G7_seed0_step1500`)。
- 2026-08-21 00:04 HKT - 当前 GPU0-3 被其他用户占用，GPU4-7 被独立 Student 使用；本轮只允许 static coding 与 CPU/light smoke，不运行 Isaac Sim、render、training 或 formal cells。
- Student actual resolved config 已 read-only 确认使用 G7 seed0 step1500，状态 `CONFIRMED_G7_STEP1500`；Student worktree/process 不属于 v25 写边界。
- 2026-08-21 00:09 HKT - deterministic LEFT-only preset 与 scene routing 已完成。CPU/light smoke 证明 Hydra config、selector function body 与 G7 static policy contract；证据边界为 `NO_ISAAC_SIM_NO_CUDA`，不宣称 visual/runtime PASS。
- 2026-08-21 01:35 HKT - GPU0-3 释放后完成 M1 Isaac Sim proof：RIGHT 单 episode 在 446 steps `complete`，`goal_reached=true`，cross/release hinge 为 `0.9108445/1.6081884 rad`；LEFT 单 episode 正确镜像 handle/hinge/target 并进入 stage 2，但 452 steps `stage_overtime`、hinge 近零。当前停止在 M1 owner confirmation 前，不实现 mixed-LR 或启动 formal training。
- 2026-08-21 01:43 HKT - Owner 已明确确认 M1；Phase C 获准开始。GPU1-3 空闲，mixed-LR 将复用 native `[left,right]` equal-probability spawn，fresh staged-reset 由新进程内 per-env ring buffer 保证。
- 2026-08-21 02:16 HKT - Phase C mixed-LR 已实际跑通：64 env 恰有 32 LEFT/32 RIGHT，G7 policy-only warm start 完成 8/8 optimizer updates、32768 timesteps、512 episodes 并写出 step8 checkpoint。Isaac Sim 5.1 在本机禁止用 `CUDA_VISIBLE_DEVICES` 绑定；原生物理卡契约为 unset CVD + `ACCELERATE_TORCH_DEVICE=cuda:N`。
- 2026-08-21 02:16 HKT - v25 native-friction pilot 在同一 mixed16/seed0 上完成 P02/P10/P20。每档均为 5 LEFT/11 RIGHT；RIGHT 三档均 11/11 goal，LEFT 均 0/5。P10 仍有 LEFT stage4/stage3 各 1，P20 已无 LEFT stage4。结合 v24 已冻结的 P02>P05>P10>P20 behavioral gradient 与 P10 boundary face，v25 formal 主负载固定为 P10：static/dynamic/viscous=`10/7.5/0 N.m`。
- 2026-08-21 02:34 HKT - FULL/RP0 P10 pre-launch 均完成 64×8、512 episodes、32768 timesteps 并写出 step8。四个 formal tmux 已在 GPU0-3 启动并全部进入真实第 1 次 update：4096 env/cell、1500 batches、save250；单 update 约 24.5 s，初始 ETA 约 10.2 h。
- 2026-08-21 04:26 HKT - 四格均跨过 step250，四个 `model_step_000250.pt` 已落盘；训练继续健康运行，未提前占用正式 checkpoint 做并发 eval。
- 2026-08-21 16:06 HKT - v25 已完成。四个 4096×1500 formal cells 全部自然结束；common-suite Teacher 结论为保留 G7，Student 未改。FULL S0 step500 是 science checkpoint，不是 Teacher：LEFT 22/32 crossing-while-holding 但 0/32 goal，RIGHT 32/32 goal。
- 2026-08-21 16:06 HKT - P10 matched-prefix acute intervention 有 30 LEFT/32 RIGHT 完整配对。planar ON−OFF median hinge effect 为 LEFT `+0.074 rad`、RIGHT `+0.148 rad`；posture ON−OFF 为 LEFT `+0.007 rad`、RIGHT `-0.013 rad`。结论是 posture 主要帮助 reach/grasp/contact geometry，planar motion 提供 stable-grasp 后的即时 opening mechanics。

## Reusable handedness facts

- `DoorSpawner` raw `left -> +1`、`right -> -1`。在固定从 -X 朝 +X approach 下，raw label 对应 robot-view handle side；hinge 位于相反 lateral side。
- A2 grasp/pregrasp target 来自 handle `FrameTransformer`，stage-0 staging reward/advance 直接跟随 world-frame grasp target。
- hinge opening progress 始终为正角度增加；push/out through direction 维持 +X，不因 LEFT/RIGHT 改变。
- M1 runtime visual confirmed no `door_open_a2_base.py` handedness patch is required: handle-relative targets follow the mirrored physical handle, while positive hinge and +X through semantics remain valid on the successful RIGHT episode.

## v24 load boundary

- Reuse `gr00t/rl/envs/door/a2_v24_friction.py` native backend。
- v24 已验证 static effort `2/5/10/20 N.m` 轴具有 behavioral discrimination；v25 在 M1 后用小 pilot 选择 stable-grasp boundary，不重开 v24 terminal。
- v25 选定 P10 单一主负载。P02 是 easy anchor，P20 是更重候选；formal 与 matched causal dataset 不按 side 改变负载。

## Validation boundary

Final evidence includes deterministic M1 visuals, mixed-LR runtime, P02/P10/P20 load pilots, four completed P10 formal cells, side-stratified Teacher evaluation, chronic FULL/RP0 comparison, 30 LEFT/32 RIGHT acute matched-prefix pairs, a paired figure, and representative videos. Acute conclusions remain limited to simulation, P10, FULL S0 step500, a 50-step horizon, and matched-prefix rather than exact solver-state restore. No real-site torque capability is inferred.
