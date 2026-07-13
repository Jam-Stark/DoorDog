---
name: push-open-door-optimization
scope: A2+Piper full-stage push-open-door RL optimization from base_v9 onward
status: active
last_updated: 2026-07-13 17:42 HKT
owned_paths:
  - memory/a2-piper/MEMORY.md
  - memory/a2-piper/push-open-door-optimization/description.md
  - memory/a2-piper/push-open-door-optimization/TODO.md
  - memory/a2-piper/push-open-door-optimization/DONE.md
read_when:
  - 开始设计、训练、eval、render 或复盘 base_v9 之后的 A2+Piper full-stage 推门 policy 时
  - 需要确认当前 baseline、历史 ablation 教训、matched eval 口径或下一版 base_v10 approval gate 时
---

# Push-Open-Door Optimization

## Purpose

本 entry 从 `base_v9` 起独立负责 A2+Piper full-stage 推门/开门 RL optimization 的当前状态、训练/eval/render 口径与下一步 TODO。Reward function 的构建历史继续保留在 [`reward-implementation-goal`](../reward-implementation-goal/description.md)，stage0–2-only quick test 继续保留在 [`stage0-2-grasp-terminal`](../stage0-2-grasp-terminal/description.md)；两者都不再拥有 full-stage `base_v9+` 的 active experiment TODO。

完整的 `replay_v2`、`base_v0→v9` 因果时间线、诊断 findings、artifact map 与可复现命令见 [`scriptsFORhuman/a2_piper_push_open_door_optimization_base_v0_to_v9_20260713.md`](../../../scriptsFORhuman/a2_piper_push_open_door_optimization_base_v0_to_v9_20260713.md)。Memory 只保存可复用结论，不复制 raw trace 或长日志。

## Current State

- `base_v9_A/B/C/D` 四组都完成 step1000 / `262,144,000` timesteps，finite、无 runtime error，但 training goal metric 都是 0；matched scalar eval 的 16 个 first episodes 全部 `0/16 goal`、`stage_overtime`。
- Locked A/B 在本轮 single-seed/config family 下明显强于 unlocked C/D；A 是 provisional hinge leader，B terminal hinge 接近且 rebound 更低。该排序不是 success、statistical winner 或“所有 base mobility 无效”的证据。
- 四组 close command ratio 约 `99%`，stage3/4 contact stability 仅约 `0–0.107%`；接触持续由 `arm_body8` 单侧主导，并伴随 `arm_j6` / arm workspace bottleneck，故“close command 已下发”不能等同于 bilateral hold。
- A/B trace 证明 `arm_j8` 在 close target `[0,0]` 下被外部接触载荷推到 `-0.035` open limit，恶化段常见 `arm_body7=0N`、`arm_body8≈27–51N`；脱离后 j8 回到接近闭合位置。当前 Kp80 与最大 `0.035m` error 的静态 P response 约 `2.8N/finger`，低于 effort cap `10N`，因此不能只归因于 effort limit。
- Higher-gain S0/S1/S2 clamp 只增加 transient bilateral/stability signal；三组 step40 都为 `0/8 any-contact`，S2 又出现 j7 saturation。Gain 是 partial factor，不升级为当前 training/default。
- 最终 matched-clean 为 `0/8 MATCHED_CLEAN_READY`、`8/8 MATCHED_CLEAN_RETREAT_JOINT_LIMIT`。这是 controller-local joint-limit abort，不证明 `grasp_target` physical unreachable；fresh O0、O-、O+ 与 retraining 均未执行。
- 2026-07-13 用户决定停止继续扩展 `base_v9` oracle、static clamp、O± 与 matched-clean 诊断。下一阶段回到 RL optimization：先形成 `base_v10` 训练/ablation 方案并单独取得 approval。

## Current Baseline

| Item | Value |
|---|---|
| Policy reference | `logs_rl/a2_piper_full_stage_a2_base/base_v9_B-20260710_212247/model_step_001000.pt` |
| Training seed | `0` |
| TCP source local-Z | `0.085m` |
| Gripper Kp/Kd | `80/3` |
| Gripper effort limit | `10/10N` |
| Explicit friction override | none (`null`) |
| v9 warm-start | `base_v8_A` ckpt1000 actor-only via `checkpoint_load_mode=policy_only` |

`policy_only` 只继承 actor；critic、optimizer、scheduler、global step、env curriculum 与 snapshots 必须 fresh。Eval 会 normalize 到 `full`；解释 checkpoint 时以保存的 resolved runtime config 为准。

## Inherited Base v0→v8 Lessons

- `replay_v2` 的视觉 grasp-like close 没有满足 formal bilateral force/history predicate；视频不能代替 success metric。
- `base_v0` effort `10→30` 与 `base_v2` gripper Kp/Kd `40/1→80/3` 都可能把 from-scratch RL 推入 open-gripper/no-contact basin；不要把 actuator sweep 当 sufficient fix。
- `base_v1` arm-only Kp/Kd 保留 replay behavior，说明负向分叉不是一般 retrain 必然漂移，但它仍未解决 bilateral grasp。
- `base_v3/v4` 证明 route/completion 与安全语义必须分开检查：history/threshold 可以放行错误 route，高 completion 也可能来自 `250N+` violent false-success。Hard predicate 应与 `squeeze_window` 和 `over_force` 对齐。
- `base_v5` 教训是不能按 filename 归因 run；必须核对 saved config、checkpoint、mtime 与 code state。
- `base_v6` 同时改变 TCP `.105→.085` 和 effort `10→40` 且停在 stage1，不能当成 effort-only 证据。
- `base_v7` 的 factor separation 支持当前 `.085/10` baseline；A `2/2 complete` 不代表后续 v9 hold route 已解决。
- `base_v8 A/A'` 显示 threshold `.6` 会先耗尽 j6 workspace；arm 仍需推门时不应恢复 stage4 arm-default-pose shaping。Scratch `base_v8 B` 从未进入 stage3/4，不能评价 hold retention。

## Evaluation and Command Contract

- Formal v9 matched resource contract：每组 2 GPUs / 2 processes，每 rank `num_envs=2048`，每组 total env 4096；四组保持相同 seed、source checkpoint、batch budget 与 environment count。
- `base_v10` launcher 必须使用四个独立前台 terminal，分别绑定 GPU `0,1` / `2,3` / `4,5` / `6,7`，使用不同 `main_process_port` 并间隔约 10 秒启动；每组自然写出 `model_step_001000.pt` 后在对应 terminal 手动 `Ctrl-C`。禁止用 `setsid`、单 shell 后台 `&` 或 detached wrapper 管理 IsaacSim：2026-07-13 的失败尝试中 `setsid` wrapper 先退出并显示 `Done`，实际 4 个 Accelerate parent + 8 个 rank 成为 orphan，且多组出现 Vulkan/GPU Foundation initialization failure。
- Matched scalar/trace 使用 module invocation、step1000、16 env、每 env first episode；scalar/trace 是 primary evidence。
- Render 保持相同 checkpoint/seed/env/episode contract，只用于解释 contact、detach、jam、doorframe event 与动作自然性，不参与 success-rate 统计。
- 原始完整 shell command 未保留；human report 中的 train/eval/render blocks 明确是从 saved Hydra overrides/config 重建的模板。
- Sibling worktree eval 使用 `python -m gr00t.rl.eval_agent_trl`，避免 direct-script invocation 命中另一 worktree 的 editable-install source。

## Evidence Boundaries

- 未证明 imported USD material override、exact collider/inner-pad geometry、closing axis/aperture 或 Cartesian reachability root cause。
- Target-side lever-center/X+Z recenter、source-side TCP local-Z `.105→.085` 与 source-local-Y O probes 是三个不同坐标变量，不能混写。
- Current C/D 失败不否定其他 base-follow reward/action design；A 的单 seed lead 也不是 final winner。
- 停止诊断表示当前路线信息增益不足，不表示 forced-close、gain、friction 或 geometry 在所有未来训练中永远无效。

## TODO Summary

- 2026-07-13 17:42 HKT - 执行已确定的 `base_v10` fresh-training cumulative ablation：A=从随机初始化训练的 v9-B-config control，B=A+hold-reward rebalance，C=B+gripper Kp/Kd `160/6`，D=C+stage3 base unlocked。四组必须各自训练一个全新 policy，统一 `checkpoint=null`、`auto_load_latest=false`，actor/critic/optimizer/scheduler/global step 全部 fresh；每组固定 `--num_processes 2`、命令字面值 `num_envs=4096`、`WANDB_MODE=online`、threshold `0.25`、seed0 与 1000 batches。只使用四 terminal foreground launch；训练完成后进入 matched scalar/trace + render comparison。

## DONE Summary

- 2026-07-13 17:42 HKT - 用户提供历史 verified launch template，明确 v10 每组即使使用 2 processes 也保持 trainer override `num_envs=4096`，并沿用 `WANDB_MODE=online`、fixed reward penalty scale、stage2 contact threshold `1.0` 与 PhysX velocity iterations `1`；不得自行换算成 2048。
- 2026-07-13 17:41 HKT - 用户明确版本语义：新 `base_v10` 必须是四个 random-init long-training policies，不允许从 v9/v8 checkpoint warm-start；该决定 supersede 17:36 HKT 的 `base_v9_B policy_only` 方案。
- 2026-07-13 17:36 HKT - 归档并清理一次 launcher-only failure：删除四个 `20260713_173141` partial run 与对应 `/tmp` logs，终止 12 个 orphan processes；该启动未产出 checkpoint，不是 `base_v10` 实验结果。Durable gotcha 是 IsaacSim multi-group training 不使用 `setsid`/detached wrapper。
- 2026-07-13 16:37 HKT - 建立独立 full-stage push-open-door optimization memory；归档 `base_v9` 四组 formal/matched 失败结论、j8/body8 backdrive、gain/friction evidence boundary、matched-clean scientific failure与停止诊断决定，并把详细 base_v0→v9 findings/commands route 到 human report。
