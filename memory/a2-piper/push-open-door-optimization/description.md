---
name: push-open-door-optimization
scope: A2+Piper full-stage push-open-door RL optimization from base_v9 onward
status: active
last_updated: 2026-07-16 21:09 HKT
owned_paths:
  - memory/a2-piper/MEMORY.md
  - memory/a2-piper/push-open-door-optimization/description.md
  - memory/a2-piper/push-open-door-optimization/TODO.md
  - memory/a2-piper/push-open-door-optimization/DONE.md
read_when:
  - 开始设计、训练、eval、render 或复盘 base_v9 之后的 A2+Piper full-stage 推门 policy 时
  - 需要确认当前 `v13_pre` gate patch、`base_v12` 终局、v13 run 顺序、matched eval 口径或 `logs_eval` co-location contract 时
---

# Push-Open-Door Optimization

## Purpose

本 entry 从 `base_v9` 起独立负责 A2+Piper full-stage 推门/开门 RL optimization 的当前状态、训练/eval/render 口径与下一步 TODO。Reward function 的构建历史继续保留在 [`reward-implementation-goal`](../reward-implementation-goal/description.md)，stage0–2-only quick test 继续保留在 [`stage0-2-grasp-terminal`](../stage0-2-grasp-terminal/description.md)；两者都不再拥有 full-stage `base_v9+` 的 active experiment TODO。

完整的 `replay_v2`、`base_v0→v11` 因果时间线、诊断 findings、artifact map 与可复现命令见 [`scriptsFORhuman/a2_piper_push_open_door_optimization_base_v0_to_v9_20260713.md`](../../../scriptsFORhuman/a2_piper_push_open_door_optimization_base_v0_to_v9_20260713.md)。Memory 只保存可复用结论，不复制 raw trace 或长日志。

## Current State

- `base_v12` A/B/C/D 已完成训练与 matched eval，不再是“尚未启动”的 config anchor。四组 matched 终局均 `0/16 goal`、无 stage4；A step3000 仅 2/16 进入 stage3，C step3000 保持最佳 stage2 grasp 但旧 gate 下 0/16 stage3，B/D step2750 均停在 stage2 open-command/no-contact basin。single-seed 2×2 受 learned basin/stage exposure 支配，不能给出稳定 factorial causality 或 winner。
- v12_C step3000 的旧 gate 直接证据：stage2 current-frame both contact `92.0%`、opposite/sufficient squeeze 各约 `93.1%`，但 5 个连续 physics-frame all-history stability/completion 恰为 `0`。ContactSensor history 在 200Hz physics loop 更新，而 policy control 为 50Hz；旧 5-frame window 仅约 25ms 且跨 action boundary，故 gate 时间尺度是结构性 blocker。
- `v13_pre` 已实施 M1：required config `a2_grasp_gate_mode` 支持显式 `control_streak|physics_history`，`a2_grasp_streak_control_steps=5`；control mode 每个 control step 取 sensor latest frame `[:,0]`，stage2 squeeze 与 stage3/4 bilateral streak 只更新一次，reset/stage switch 清零，completion/stability getters 无副作用。未知 mode、缺失/非法 K、shape/dtype/device 或 duplicate full update 直接 fail-fast；legacy physics-history path 只用于历史复现/消融。
- M10 最终 matched runtime artifact 为 `logs_eval/base_v13/base_v13_pre_gatepatch_C3000_matched_scalar_trace_16env_seed0_20260716_r2/`：v12_C step3000、seed0、16 env、per-env first episode，且相对 v12_C 原 eval 只新增 `control_streak/K=5`。结果 `16/16 stage3 entry`、`0/16 stage4`、`0/16 goal`；stage2 首过 control-step min/median/max `16/20.5/27`，达到 plan `>=14/16` gate。stage3 pooled bilateral `99.815%`、control-streak stability `98.692%`，但 hinge max mean 仅 `.000918rad`，支持“根因 A 已解除、B/C 仍待 v13_A”的分离结论。
- `v13_pre` validation：72 个 targeted no-sim tests、Python compile、YAML parse、Hydra compose、diff check、matched runtime 与 artifact/config consistency PASS。Black/Ruff 在当前 env 未安装，保持 NOT_RUN；IsaacSim 启动有 `CUDA_VISIBLE_DEVICES`/GLFW enumeration warnings，但 scene/checkpoint/16 episodes 均成功且进程 exit0，不升级为 blocker。
- `base_v11` A/B/C 都在计划 global step2000 前停止；可用 full-state checkpoint 为 A/B `500/1000/last=1150`、C `1250/1500/last=1550`。九个 payload 的 ZIP integrity 与 CPU load 都 PASS，但训练停止原因及训练到 step2000 的行为均未证实，故仅构成 incomplete-budget comparison。
- Matched module scalar/trace eval（seed0、16 env、per-env first episode）在九个可用 state 全部为 `0/16 goal`、`0/16 stage4 entry`、`stage_overtime`；A/B 均 max-stage2，C 均 max-stage3。它是 single-seed/incomplete-budget evidence，不产生 full-budget 或 statistical winner。
- A/B 三个 aligned per-env hinge 完全相同，且两组均无 stage3 exposure；`push_door_hinge=12` 只在 stage3/4 gate 生效，所以 B 没有实际测试 exposure 下的 H+。C 最新 step1550 mean max hinge 约 `.001110rad`，保留 bilateral `100%`、stability `99.159%`、close `100%`、over-force `0%`、j7/j8 open-limit proximity `0%`；stable hold 不是 door progress。
- C 的 realized hold bundle 约 `.1813`、hinge reward 约 `.00007`，支持当前轨迹存在 reward-magnitude imbalance 的观察；hold-dominant causality 仍是 inference，未经 reward intervention 证实。没有新增 render：无新的定性事件，scalar/trace 仍是 primary evidence。
- 当前关键 source mtime 晚于 v10_D training launch、早于 v11；A 是 exact saved-config control，但不是已证明的 exact-source control。现有 observation-order diff 是 plausible confound，因果未证实；下一轮训练前必须 freeze/record exact source。
- Durable resume gotcha：当前 trainer 中 `algo.trl.num_total_batches` 是全局 iteration 上限，不是 resume 后的 remaining iterations。Full-state checkpoint 会恢复 `state.global_step`，trainer 将 `state.max_steps` 设为 `num_total_batches`，`DefaultFlowCallback` 在 `global_step >= max_steps` 时终止。因此从 step1000 续训到 step2000 必须传 `num_total_batches=2000`；传 `1000` 会在 resume 后立即命中终止条件。不得只根据外层 `for range(...)` 误判为“额外训练 1000 batches”。
- `base_v10_A/B/C/D` 是四个独立 scratch policy：saved config/overrides 与 checkpoint integrity 已证明 `checkpoint=null`、`auto_load_latest=false`、seed0、命令字面值 `num_envs=4096`、2 ranks、1000 batches；四个 `model_step_001000.pt` 均存在。训练时未能逐字冻结的 source equivalence 仍未证实。
- Matched scalar/trace runtime PASS：四组均为 seed0、16 env、each-env first episode；全部 `0/16 goal`、`stage_overtime`，没有 stage4。A/C 只到 stage2；B/D 全部到 stage3。
- D 是当前 behavioral reference，不是 task winner：stage3/4 pooled bilateral contact `100%`、contact stability `99.147%`、j7/j8 open-limit proximity `0%/0%`，但 hinge max mean 仅 `.001073rad`，远低于 `.25rad` stage3→4 threshold。单 seed 不能给出统计 winner。
- A→B、B→C、C→D 的比较都被 learned route/stage exposure 限制：B/D 的 high-quality hold 不可由 A/C 的无 stage3 exposure 单独隔离；C 是 open/no-contact basin，workspace signal 为 j3 dominant/argmin bottleneck（不是 only-j3 root cause）。D 的 stationary bilateral hold 与 strong hold reward / low progress motion 一致，但 reward dominance 仍是待 intervention 验证的推测。
- D matched render 有 48 个有效 MP4，定性显示 stationary bilateral hold、没有可见持续 door rotation。strict no-trace output QA 为 FAIL：即使 diagnostic flag=false 仍写出 base trace；source diagnosis 证明这是 unconditional base trace output，发生在 physics/reward 后且不改 policy action。render 的 numeric exit code unverified，不能把整条 render QA 写为 PASS。
- `base_v9` oracle、static clamp、O± 与 matched-clean 诊断继续停止。`base_v11_repair_r1` A/B 都从 staged v11_C step1550 policy-only 启动，seed0、literal `num_envs=4096`、500 batches/save125；唯一语义 A/B 差异是 `push_door_handle: 6→0`，两组 hinge 均为6。
- repair_r1 的 step125/250/375/500 共八个 matched eval（seed0、16 env、per-env first episode）均为 `0/16 goal`、`0 stage4`、`stage_overtime`。A500 mean max hinge `.002081rad`，仅为 `.25rad` threshold 的 `.832%`，并与 j8/base/workspace/doorframe regression co-occur；B 保留 stable hold/j8 guardrail，但 hinge flat。没有 promotable checkpoint、statistical winner 或 causal root cause。
- `base_v12` 四个 current-source、v10_A-style scratch factorial run（A/B/C/D）均为 `checkpoint=null`、`auto_load_latest=false`、seed0；它们不是 historical `base_v9` reproduction，因为 v9 使用 v8_A policy-only warm-start，且 historical source byte equivalence 未证实。
- v12 的实际 launch contract 保持每 rank literal `num_envs=4096`、2 ranks、global rollout batch8192、global cap3000/save250，不得除成2048。common config 包括 threshold `.25`、stage3 base locked、effort `10/10`、handle/hinge `6/6`、fixed penalty scale、cameras/render false、PhysX velocity iterations1。
- Matrix：A=`80/3 + stability .5`，B=`160/6 + .5`，C=`80/3 + 1.0`，D=`160/6 + 1.0`。四组 static/config checks 均 PASS，训练与 matched eval 终局见本节首条；由于 learned basin/stage exposure 不同，H 的 `.5→1.0` 与 gain 的 `80/3→160/6` 都没有形成稳定 factorial causality。

## Current Baseline

| Item | Value |
|---|---|
| Policy reference | `logs_rl/a2_piper_full_stage_a2_base/base_v12_C_v10A_scratch_stability1-20260716_004404/model_step_003000.pt` |
| Training seed | `0` |
| TCP source local-Z | `0.085m` |
| Gripper Kp/Kd | `80/3` for v13_pre/v13_B; v13_A proposes `800/25` |
| Gripper effort limit | `10/10N` |
| Grasp gate | `control_streak`, K=`5` control steps; `physics_history` is explicit legacy ablation |
| Stage3 base | locked in v13_pre/v13_B; v13_A proposes unlocked |
| Stage3→4 threshold | `.25rad` |
| v13_pre reward | exact v12_C reward, including `push_door_handle=6` and stage3/4 stability `1` |
| Explicit friction override | none (`null`) |
| Matched eval | seed0、16 env、each-env first episode；scalar/trace primary |

当前 v13 warm-start policy reference 是 v12_C step3000；它已由 M10 证明可在 control-step gate 下稳定进入 stage3，但仍没有压 handle 或推门。所有训练/eval 解释以保存的 resolved runtime config 为准。

## Current Experiment

`v13_pre` 是当前已完成 experiment：只实施 M1，并对 v12_C step3000 运行 matched eval；没有新 training、没有 M2–M9 behavior claim。最终 r2 artifact 已通过 `16/16 stage3 entry` gate，故 root-cause A 的 stopping condition 达成。

下一 run 顺序是 v13_A main 后 v13_B gate-only；两者尚未创建 config、smoke 或启动。v13_A 才负责验证 Kp/Kd `800/25`、stage3 base unlock、policy-only warm-start、grasp-gated unlatch/hold-and-drive reward 与 stage3→4 grasp condition；v13_B 保持 v12_C 的 Kp80/base locked/reward，只分离 M1。M7/M8/v13_C/v13_D 仍按 plan 条件触发，不因 pre PASS 自动进入。

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
- 旧 `base_v11` launch 沿用 v10 resource contract：独立 foreground terminal、GPU pair、distinct port、约 10 秒 stagger。禁止 `setsid`、单 shell `&` 或 detached wrapper 管理 IsaacSim；2026-07-13 的 setsid 尝试曾产生 orphan parent/rank 与 Vulkan/GPU Foundation initialization failure。
- `base_v12` superseded the old repair_r2 proposal：四组 current-source scratch launch 使用 literal `num_envs=4096` per rank、2 ranks（global rollout batch8192）、global cap3000/save250、committed exact source freeze 与四个独立 foreground terminals/distinct ports；后续训练与 matched eval 已完成，终局见 Current State。
- Resume command 的 `num_total_batches` 必须写全局 target step：从 restored step1000 到 step2000 传 `2000`，不是传 remaining count `1000`；此 global-cap gotcha 继续适用于任何 future full-state resume。
- `base_v11` matched scalar/trace 使用 module invocation、seed0、16 env、每 env first episode；scalar/trace 是 primary evidence。比较 hinge max/terminal 与 stage4 entry，bilateral/stability、over-force、j7/j8 limit 作为 guardrail。
- Render 保持相同 checkpoint/seed/episode semantics，只用于解释 contact、detach、jam、doorframe event 与动作自然性，不参与 success-rate 统计。默认从 matched eval env 中随机选取2个 env，只渲染这2个 env；每个 env 生成 default、handle-side、handle-top 3个 camera video，总计 `2 env × 3 camera = 6 videos`。除非用户明确要求，不再默认对16个 env 做全量 render；2-env qualitative subsample 不能替代16-env scalar/trace primary evidence。
- 原始完整 shell command 未保留；human report 中的 train/eval/render blocks 明确是从 saved Hydra overrides/config 重建的模板。
- Sibling worktree eval 使用 `python -m gr00t.rl.eval_agent_trl`，避免 direct-script invocation 命中另一 worktree 的 editable-install source。
- Future base-specific A2 eval 必须把完整 result folder 写到 `logs_eval/base_vN/<eval-run>/`：folder 直接包含 `.hydra/`、eval logs、metrics/traces/diagnostics 与可选 `renderings/`。`eval_output_dir` 是 canonical path，`eval_name` 仅为 leaf label；`base_eval.yaml` 的 `eval_log_dir` alias 与 rendering default 都跟随 `eval_output_dir`。该 co-location contract 已由 v13_pre scalar/trace runtime 验证；新 eval 的 rendering path 仍保持未验证。
- Historical `logs_eval` migration：首批129个 version-named eval dirs 已归入 `base_v0..base_v11`；另有48个旧 top-level Hydra dirs whole-tree 迁移，36个 exact-paired 到 canonical result 的 `.hydra_provenance/<old-top-dir>`，12个 versioned/unpaired 到 `base_vN/_unpaired_hydra/<old-top-dir>`。`_eval_inputs` 与 `replay_v2` 保留 top-level，迁移后 top-level 共14项；无 symlink/collision，但未收集 content hash，故仅有 layout/static evidence。

## Evidence Boundaries

- 未证明 imported USD material override、exact collider/inner-pad geometry、closing axis/aperture 或 Cartesian reachability root cause。
- Target-side lever-center/X+Z recenter、source-side TCP local-Z `.105→.085` 与 source-local-Y O probes 是三个不同坐标变量，不能混写。
- Current C/D 失败不否定其他 base-follow reward/action design；A 的单 seed lead 也不是 final winner。
- 停止诊断表示当前路线信息增益不足，不表示 forced-close、gain、friction 或 geometry 在所有未来训练中永远无效。

## TODO Summary

- 2026-07-16 21:09 HKT - `v13_pre` 已通过；下一步是尚未实施/启动的 v13_A main 与 v13_B gate-only。M7/M8/v13_C/v13_D 保持 conditional，不得写成 current DONE。

## DONE Summary

- 2026-07-16 21:09 HKT - `v13_pre` M1 + M10 runtime PASS：control-step streak gate/config/telemetry 已实现，72 tests/compile/compose/diff checks PASS；v12_C step3000 matched r2 为 16/16 stage3 entry，首过 stage2 control-step `16/20.5/27`，stage3 bilateral/stability `99.815%/98.692%`，hinge 仍近零。根因 A 已证实，M2–M9/v13_A 尚未完成。
- 2026-07-16 00:29 HKT - 完成 `base_v12` A/B/C/D current-source v10_A-style scratch factorial configuration/static evidence sync：A `80/3+.5`、B `160/6+.5`、C `80/3+1.0`、D `160/6+1.0`；四组均 checkpoint null、planned 2 ranks、literal `num_envs=4096` per rank、global cap3000/save250。strict YAML/resolved compose/factorial/mapping、CODE_QUALITY、IsaacLab static/no-sim semantics 与 NO_SIM_QA PASS。`base_v12` 不是 v9 reproduction（v9 是 v8_A policy-only warm-start，historical source byte equivalence 未证实）；未启动 training/eval/IsaacSim/runtime，故没有 behavior、resource feasibility、checkpoint I/O 或 winner evidence。
- 2026-07-15 21:18 HKT - 新增 default render resource contract：从 matched eval env 中随机选2个 env，每个 env 只生成 default、handle-side、handle-top 3个 camera video，总计6个；16-env scalar/trace 继续作为 primary evidence，除非用户明确要求，不再默认16-env全量 render。
- 2026-07-15 20:56 HKT - `base_v11_repair_r1` A/B matched eval 完成：均从 staged v11_C step1550 policy-only 启动、seed0、literal `num_envs=4096`、500 batches/save125，唯一语义差异为 `push_door_handle: 6→0`（hinge均为6）。八个 step125/250/375/500 eval 均 `0/16 goal`、`0 stage4`、`stage_overtime`；A500 hinge 仅 `.002081rad`（`.25rad` threshold 的 `.832%`）且与 guardrail regression co-occur，B stable hold/j8 guardrail 但 hinge flat。因此没有 checkpoint promotion、statistical winner 或 causal root cause。
- 2026-07-15 20:56 HKT - 完成 historical `logs_eval` grouping/migration，并确立 future base-specific eval co-location：`eval_output_dir` 为 canonical grouped path、`eval_name` 为 leaf；config tests `3 passed` 与 resolved compose PASS。迁移无 symlink/collision，但未收集 content hash；新 eval runtime 未验证，以上不构成 runtime eval PASS。
- 2026-07-14 22:02 HKT - `base_v11` incomplete-budget matched eval 完成：九个 usable state 全为 `0/16 goal`、`0/16 stage4`、`stage_overtime`；A/B 仅 stage2、C 仅 stage3。A/B 无 stage3 exposure，不能评价 hinge12 H+；C 的 stable bilateral hold 没有转化为 hinge breakthrough，当前结果不是 full-budget/statistical winner。
- 2026-07-14 22:02 HKT - 确认 v11 的 source temporal confound 与 reward-evidence boundary：A 仅是 exact saved-config control，observation-order diff 是 plausible confound；hold/hinge realized magnitude imbalance 不构成 hold-dominant causality。旧的 stage3-exposed H+ resume 方向已由 repair_r1 执行证据 supersede，不启动训练。
- 2026-07-14 01:11 HKT - 完成 `base_v10` scratch A/B/C/D provenance、matched scalar/trace 与 D qualitative render 复盘；四组都未完成任务，当前仅形成 D stable-hold behavioral reference 与 approval-gated `base_v11` H+ proposal。详细 metrics、artifact 与命令见 human report。

- 2026-07-13 17:42 HKT - 用户提供历史 verified launch template，明确 v10 每组即使使用 2 processes 也保持 trainer override `num_envs=4096`，并沿用 `WANDB_MODE=online`、fixed reward penalty scale、stage2 contact threshold `1.0` 与 PhysX velocity iterations `1`；不得自行换算成 2048。
- 2026-07-13 17:41 HKT - 用户明确版本语义：新 `base_v10` 必须是四个 random-init long-training policies，不允许从 v9/v8 checkpoint warm-start；该决定 supersede 17:36 HKT 的 `base_v9_B policy_only` 方案。
- 2026-07-13 17:36 HKT - 归档并清理一次 launcher-only failure：删除四个 `20260713_173141` partial run 与对应 `/tmp` logs，终止 12 个 orphan processes；该启动未产出 checkpoint，不是 `base_v10` 实验结果。Durable gotcha 是 IsaacSim multi-group training 不使用 `setsid`/detached wrapper。
- 2026-07-13 16:37 HKT - 建立独立 full-stage push-open-door optimization memory；归档 `base_v9` 四组 formal/matched 失败结论、j8/body8 backdrive、gain/friction evidence boundary、matched-clean scientific failure与停止诊断决定，并把详细 base_v0→v9 findings/commands route 到 human report。
