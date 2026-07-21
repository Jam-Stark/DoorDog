# A2 + Piper 推门优化：Base v0 → Base v11 结果与经验（更新于 2026-07-14）

> 状态：`base_v11` A/B scratch 与 C full-state resume 已停止，但都没有达到计划的 global step2000：A/B 最后可评估 state 为 step1150，C 为 step1550。九个现存 checkpoint/state 已完成 seed0、16 env、first-episode matched scalar/trace；全部 `0/16 goal`、`0/16 stage4 entry`。A/B 始终停在 stage2，C 始终停在 stage3 stationary hold，没有突破。`base_v9` oracle、static clamp、O-/O0/O+、matched-clean 等诊断路线继续停止；下一项只提出一个在 stage3 exposure 下的最小 resume H+ ablation，本报告不启动训练。

## 1. 结论先行

- `base_v10_A/B/C/D` 的四个 `model_step_001000.pt` 均存在且 checkpoint archive integrity PASS；saved Hydra config/overrides 证明四组共同使用 `checkpoint=null`、`auto_load_latest=false`、seed0、命令字面值 `num_envs=4096`、2 ranks 与 1000 batches。四组是独立 scratch policies，不是 v9/v8 warm-start。
- Matched first episodes 中四组都为 `0/16 goal`、`16/16 stage_overtime`，且没有任何 stage4 entry。A/C 最高只到 stage2；B/D 都 `16/16` 进入 stage3。四组 mean max hinge 分别只有 `0.000107 / 0.001156 / ~0 / 0.001073 rad`，相对 stage3→4 的 `0.25rad` threshold 都接近零。
- B/D 的 stage3/4 hold 已不再是“持续单侧脱落”：B bilateral/contact-stability 为 `99.282% / 98.701%`，D 为 `100% / 99.147%`。但 B 的 `arm_j7` open-limit proximity 高达 `91.658%`，D 则 j7/j8 都为 `0%`，且 body7/body8 平均力更均衡。D 因而是本轮 hold-quality leader，不是 door-opening winner。
- A→B、B→C、C→D 都出现了 stage-exposure 改变：A/C 没进入 stage3，B/D 进入。因此本轮只证明 B/D learned route 与 D 的 hold signal，不能把 A/B 当成 matched-stage retention 因果实验，不能用 B/C 判定 Kp160 是否降低 stage3 backdrive，也不能用 C/D 单独证明 base movement 的因果收益。
- D 在约 `9.38s` 的 recorded stage3 control steps 中维持双面接触，却只有 `0.001073rad` mean max hinge。Saved config 与本次固定的 inspected eval source 允许 policy 在无 hinge motion 时持续获得 contact/stability reward，因此“hold-dominant local optimum”是与证据一致的机制推测，但尚未被 reward intervention 证实；training-time source snapshot equivalence 未被独立证明。
- `base_v11` 没有产生突破：A/B 在 step500、1000、1150 都是 `16/16 max-stage2`；C 在 step1250、1500、1550 都是 `16/16 max-stage3`，其 mean max hinge 仅 `.001007/.001129/.001110rad`。三组九个 eval 全部 `0/16 goal`、`0/16 stage4 entry`、`16/16 stage_overtime`。
- A/B 的 per-env hinge trace 在相同 checkpoint step 上完全相同且都没有 stage3 exposure；`push_door_hinge` 只在 stage3/4 生效，因此 scratch B 没有实际检验 hinge scale `6→12` 的 stage3 效果。C 延续了 D 的 bilateral/stability guardrail，但 step1250→1550 的绝对进展只有约 `1e-4rad`，不是 task breakthrough。
- v11 A 的 saved config 与 v10_D 一致，但“exact control”只对 saved config 成立：当前关键 source 文件的 mtime 晚于 v10_D training process 启动、早于 v11 training，因此 v10→v11 training-source equality 未证实且存在 material temporal confound。不能把 A 未复现 D 单独归因于 scratch 随机性。
- 下一轮最小建议：先冻结 exact current source，然后只做一个从同一 v10_D step1000 出发的 full-state H+ resume，唯一变量 `push_door_hinge: 6→12`，global target1500、save250；用现有 v11_C hinge6 step1250/1500 作 current-source control。若 source 再变化，则必须同时重跑 control/H+ 两臂。不增加 Kp/effort variant，也不恢复 v9 diagnostics。

以下历史 v9 stop 结论继续有效：

- `base_v9_A/B/C/D` 四组都训练到 step1000 / `262,144,000` timesteps，logged values finite、无 runtime error，但 training goal metric 都是 0；matched scalar eval 的 16 个 first episodes 也全部 `0/16 goal`、`stage_overtime`。这一轮没有产生成功 policy。
- Locked-base A/B 在同一 seed/config family 下明显强于 unlocked C/D。A 的 door hinge progress 最高，B 的 terminal hinge 接近且 rebound 更小；这只是 bounded ranking，不是 statistical winner，也不证明所有 base-follow 方案无效。
- Policy 并非没有下发闭合命令：四组 close command ratio 约 `99%`。主要可见 failure 是接触仍由 `arm_body8` 单侧主导、bilateral/contact stability 近乎为 0，并伴随 `arm_j6` / arm workspace bottleneck。
- A/B trace 显示 close target 始终为 `[0, 0]`，但 `arm_j8` 被接触载荷推到 `-0.035` open limit；恶化段常见 `arm_body7=0N`、`arm_body8≈27–51N`，脱离后 j8 又回到接近闭合位置。这证明 jaw 是被外部载荷顶开，不是 policy 主动发出 open command。
- 当前 gripper `Kp=80`，最大闭合 position error 约 `0.035m`，纯 P-control 静态恢复量约为 `80 × 0.035 = 2.8N/finger`，低于 `10N` effort cap。因此不能把问题简化为 effort limit 不够；直接继续提高 effort cap 很可能不改变静态夹持力。
- 没有证据表明 finger/handle 摩擦为零。当前没有专用 material override，runtime identity 记录 `friction_override=null`；未显式指定时使用 simulation default 的解释与现象一致，但 imported asset 是否另有 override 没有被最终证明。现有证据只支持“没有形成足够稳定的 grasp constraint”。
- Higher-gain static clamp 从 `80/3` 增至 `160/6`、`320/12` 只增加 transient bilateral/stability signal；三组 step40 都是 `0/8 any-contact`，且 `320/12` 转而出现 j7 saturation。因此 higher gain 是 partial factor，不是已经验证的训练默认值。
- 最后一轮 matched-clean 为 `0/8 MATCHED_CLEAN_READY`、`8/8 MATCHED_CLEAN_RETREAT_JOINT_LIMIT`。它只证明 eval controller 在 joint soft-limit safety check 处终止，不能推出 `grasp_target` 物理不可达，也没有执行 fresh O0、O-、O+ 或重新训练。

## 2. 当前基线与证据边界

当前用于下一轮提案的 behavioral reference 是 `base_v10_D`；它保留了任务失败边界，不能称为 solved baseline：

| 项目 | 当前值 |
|---|---|
| Policy reference | [`base_v10_D` ckpt1000](../../logs_rl/a2_piper_full_stage_a2_base/base_v10_D_scratch_hold_reward_kp160_base-20260713_174459/model_step_001000.pt) |
| Training seed | `0` |
| Initialization | `checkpoint=null`, `auto_load_latest=false` |
| Stage3→4 threshold | `0.25rad` |
| Piper TCP local-Z | `0.085m` |
| Gripper Kp/Kd | `160/6` |
| Gripper effort limit | `10/10N` |
| Stage3 base | unlocked |
| Hold bundle | close `.1`, both `2`, opposite `1`, force-window `2`, stability `4`, over-force `-2` |
| Explicit friction override | none (`null`) |
| Matched eval | seed0, 16 env, each env first episode, scalar/trace primary |

历史 v9 的 `policy_only` 只 strict-load actor；critic、optimizer、scheduler、global step、env curriculum 与 staged snapshots 都是 fresh。普通 eval 会把 load mode normalize 为 `full` 以恢复 checkpoint/eval semantics，因此最终解释应看保存的 `.hydra/runtime_config.yaml`，不能只看请求时 overrides。主 worktree 的 full-stage v0–v9 原始训练目录当前缺失；[`_recovered_wandb_full_stage_v0_to_v8_20260713`](../../logs_rl/_recovered_wandb_full_stage_v0_to_v8_20260713) 只包含恢复的 W&B config/summary/history，不含 checkpoint，不能伪装成原 run 或用于 policy eval。可用的 `base_v8_B` checkpoint 仍位于 sibling worktree `/home/baoquanc/workspace/DoorDog-A2_Piper_hold_handle/.../model_step_001000.pt`；v9 结论继续依赖现有 `logs_eval` 与本报告归档。

本报告区分三类结论：

- **已证实**：由 matched scalar/trace、saved config 或 JSON summary 直接支持。
- **尚未证实**：geometry、friction override、Cartesian reachability 等没有完成有效 intervention 的假设。
- **停止继续测试**：不是被证明永远无效，而是当前信息增益不足，不再用 `base_v9` 反复扩展 oracle/offset controller。

## 3. Replay v2 与 Base v0 → v9 因果时间线

| 版本 | 主要变量 | Runtime 结果 | 可复用经验 / 教训 |
|---|---|---|---|
| `replay_v2` | stage0–2 control；staging `0.70`；handle height `0.85–0.95m` | 能进入 close gate 并出现 grasp-like 视觉行为，但 both-force/history predicate 不满足 | 视觉上“夹住”不能替代 formal bilateral grasp 指标 |
| [`base_v0`](../../logs_eval/base_v0/base_v0) | gripper effort `10→30` 单变量 | retrained policy 进入 open-primitive/no-contact basin；reward 约从 `102–105` 降到 `71–82` | effort cap 增大不是 sufficient fix，也可能改变 RL credit/local optimum |
| [`base_v1`](../../logs_eval/base_v1/base_v1) | arm-only Kp/Kd；effort 回到 `10` | 保留 replay_v2 的 close behavior/reward，但仍没有 formal bilateral success | base_v0 分叉不是普通 retrain 必然漂移；arm gain 路线较稳定但不完整 |
| [`base_v2`](../../logs_eval/base_v2/base_v2) | gripper Kp/Kd `40/1→80/3`，effort `10` | 再次学出 open primitive、contact/squeeze 为 0 | 不应继续把纯 actuator sweep 当第一优先级 |
| full-stage `base_v3` | dense bilateral/squeeze/contact-stability shaping | reach/close 明显改善，但 `arm_body8` dominance，formal `0/150`；history-3 又会过早放行 stage3 | “route unblocked”不等于 grasp solved；eval 必须核对 checkpoint 中的 `termination_level` 与 `reward_penalty_scale` |
| full-stage `base_v4` | threshold/Kd/velocity-iteration 2×2 | `thr0.8/Kd5/vel0` 可得到 `16/16` completion，但走的是 `250N+` violent route；另一路较温和但仍未解决 grasp | hard predicate 必须与 `squeeze_window`、`over_force` dense semantics 对齐；高 completion 可能是假成功 |
| `base_v5` | historical full-stage baseline | 可用 eval 仍是 body8 单指接触 | 不能按文件名猜 run provenance；曾有“v6 render”经 mtime/saved config 核对其实属于 v5 |
| [`base_v6`](../../logs_rl/a2_piper_full_stage_a2_base/base_v6_40_effort_08TCP_offset-20260707_221058) | TCP `0.105→0.085` 与 effort `10→40` 同时变化 | `0/2`，在 stage1 因 pregrasp distance 超阈值停滞 | 两个变量同时改变且没有进入 stage2，不能解读成 effort-only 结论 |
| [`base_v7_A`](../../logs_rl/a2_piper_full_stage_a2_base/base_v7_A_tcp085_effort10-20260708_144253) / B | A=`TCP .085/effort10`；B=`.105/40` | A `2/2` complete、training goal `.747`；B `0/2`、stage4 overtime | 当前 baseline 回到 A-like `.085/10`；factor isolation 比混合改动更有信息量 |
| [`base_v8_A`](../../logs_rl/a2_piper_full_stage_a2_base/base_v8_A_release_after_open-20260708_215459) / A' | release-after-open；初始 stage3→4 threshold `.6`，A' 恢复 `.174533` 并关闭 stage4 arm-default shaping | `.6` 让 arm-only policy 在约 `.25–.28rad` 前后耗尽 j6 workspace | `.6` 不应直接作为默认；arm 仍需推门时不应把它拉回 default pose |
| `base_v8_B` scratch | hold-handle sibling route | `16/16` stage2 overtime，primitive 始终 open，contact/hinge progress 为 0 | 它没有进入 stage3/4，因此不能评价 hold retention；sibling worktree eval 应使用 module invocation 避免 editable-install 混源 |
| `base_v9_A/B/C/D` | threshold `{.174533,.25}` × stage3 base `{locked,unlocked}`；共同 B hold bundle | 四组全部 `0/16 goal`；A/B progress 强于 C/D，但稳定夹持仍失败 | close reward/command 不是 hold success；单 seed 只能做 bounded ranking |

详细的 v8→v9 design provenance、D0–D3 与原始 A–D 报告保留在 [`base_v8_to_v9_hold_handle_diagnostic_20260710.md`](base_v8_to_v9_hold_handle_diagnostic_20260710.md)。

## 4. Base v9 Formal A/B/C/D

四组共同使用 seed0、step1000、同一个 v8-A actor checkpoint 和相同训练预算：

| Config | Threshold | Stage3 base | Exact run | Goal / terminal | Hinge max / terminal / rebound | Contact stability |
|---|---:|---|---|---|---:|---:|
| A | `0.174533` | locked | [`base_v9_A-20260710_212238`](../../logs_rl/a2_piper_full_stage_a2_base/base_v9_A-20260710_212238) | `0/16`, all `stage_overtime` | `1.806586 / 1.473302 / 0.333284` | `~0.107%` |
| B | `0.25` | locked | [`base_v9_B-20260710_212247`](../../logs_rl/a2_piper_full_stage_a2_base/base_v9_B-20260710_212247) | `0/16`, all `stage_overtime` | `1.608041 / 1.450195 / 0.157847` | `0%` |
| C | `0.174533` | unlocked | [`base_v9_C-20260710_212256`](../../logs_rl/a2_piper_full_stage_a2_base/base_v9_C-20260710_212256) | `0/16`, all `stage_overtime` | `1.060336 / 0.906377 / 0.153958` | `~0.105%` |
| D | `0.25` | unlocked | [`base_v9_D-20260710_212303`](../../logs_rl/a2_piper_full_stage_a2_base/base_v9_D-20260710_212303) | `0/16`, all `stage_overtime` | `0.122457 / 0.116454 / 0.006004` | `0%` |

Matched scalar/trace artifacts：

- [A scalar/trace](../../logs_eval/base_v9/base_v9_A_ckpt1000_matched_scalar_trace_16env_20260711)
- [B scalar/trace](../../logs_eval/base_v9/base_v9_B_ckpt1000_matched_scalar_trace_16env_20260711)
- [C scalar/trace](../../logs_eval/base_v9/base_v9_C_ckpt1000_matched_scalar_trace_16env_20260711)
- [D scalar/trace](../../logs_eval/base_v9/base_v9_D_ckpt1000_matched_scalar_trace_16env_20260711)

解释边界：A 是 single-seed provisional hinge leader；B terminal hinge 仅略低且 rebound 更小，是 lower-rebound runner-up。A/B 的 base 在 config 中本来就是 locked。C/D 较弱只说明本轮 `a2_stage3_base_unlocked` reward/gate 语义没有学出改善，不能推广成“robot base 不应移动”。

## 5. j8/body8、夹持力与摩擦

### 5.1 已证实的单侧 backdrive

在 A/B 的代表性恶化段：

1. Gripper command/target 保持 close，目标 joint position 是 `[0,0]`。
2. `arm_j8` actual position 被推到 `-0.035`，正好是 open joint limit；`arm_j7` 仍接近 `0`。
3. Contact 从短暂 bilateral 变成 `body7=0N`、`body8≈27–51N`。
4. Handle 脱离后，j8 很快回到接近 `0`。

这与 render 中“一侧 jaw 被撑开、另一侧仍闭合”一致。相机画面上下与 body id 的视觉映射可能随视角改变，但 joint/body trace 不依赖相机解释。

### 5.2 为什么不能只提高 effort

Implicit PD 在静态位置误差下先产生 `Kp × error`。当前 Kp80 与最大 `0.035m` error 只产生约 `2.8N/finger` 的 P response；只有 computed effort 真正达到 `10N` cap 后，提高 effort limit 才会改变 saturation 上限。历史 base_v0 又已经表明，effort `10→30` 的 from-scratch RL 训练可能改变 action credit 并落入 open-gripper basin。

因此，现有证据不支持继续盲目增加 effort。它也没有证明更高 Kp 永远无效：static clamp 确实增加了 transient bilateral frames，但没有留下持久 contact，且更高档位出现新的 saturation。

### 5.3 为什么不能说“摩擦为零”

- 当前 diagnostic runtime 记录 `friction_override=null`，不是显式 zero friction。
- 未显式 material 时通常继承 simulation default；历史 source inspection 指向 static/dynamic friction 约 `0.5/0.5`、average combine，但 imported USD 是否有额外 override 没有完成最终 runtime material-path 证明。
- 单侧/边缘接触、较小正压力、door rotation 的 peel/wedge、arm workspace 与 base 不跟随，都可能让 tangential load 超过 `μN`，呈现“滑开后门继续靠惯性转动”。

所以可记录的结论是：没有建立足够的 bilateral grasp constraint；不能记录成 `μ=0`。

## 6. 停止点前的 Eval-only 诊断

| 诊断 | 结果 | 能说明什么 | 不能说明什么 |
|---|---|---|---|
| G1/G2/G3 TCP hold oracle | 三组都没有形成 bilateral center-close，也未进入有效 depress；最终为 convergence/IK tracking failure | scripted controller 没有提供可用的 hold-follow oracle | 不能比较三个 TCP 的真实抓持优劣，也不能证明 policy geometry root cause |
| Static clamp S0/S1/S2 | Kp/Kd `80/3`,`160/6`,`320/12`；bilateral frames `2/16/44 of 320`，stability `0/4/19`；step40 全部 `0/8 any-contact`；S2 出现 j7 saturation | higher gain 是 anti-backdrive 的 partial factor | 不能把 S1/S2 升级为 training/default config |
| O0 placement / stabilization preflight | O0 `8/8 PLACEMENT_NOT_CONVERGED`；preflight 未得到 READY | floating-root relative-target/catch-up 与 contact contamination 让该诊断 protocol 无法建立 clean initial state | 没有执行有效 O0 clamp，因此 O-/O+ 没有可比较性 |
| Matched-clean reacquisition | [`0/8 READY`, `8/8 RETREAT_JOINT_LIMIT`](../../logs_eval/base_v9/base_v9_B_matched_clean_preflight_8env_20260713/a2_hold_oracle_summary.json)；release action counts `[1,0,64,58,0,0,0,1]` | controller-local safety abort；六个 env 为 j6 upper，env2/3 在 64/58 actions 后为 j5 lower | 不证明 physical reachability failure，不证明 grasp target/offset 错误，不支持继续 O-/O0/O+ |

Static clamp artifacts：

- [S0 Kp/Kd 80/3](../../logs_eval/base_v9/base_v9_B_static_clamp_S0_kp80_kd3_8env_20260712/a2_hold_oracle_summary.json)
- [S1 Kp/Kd 160/6](../../logs_eval/base_v9/base_v9_B_static_clamp_S1_kp160_kd6_8env_20260712/a2_hold_oracle_summary.json)
- [S2 Kp/Kd 320/12](../../logs_eval/base_v9/base_v9_B_static_clamp_S2_kp320_kd12_8env_20260712/a2_hold_oracle_summary.json)

这一系列测试没有建立一个可信、可复用的 scripted grasp oracle。继续在同一 checkpoint 上增加 controller state、offset 或 placement preflight，已经不能有效回答 RL policy 应如何改进，因此在这里停止。

## 7. 已证实、未证实与不再建议

### 已证实

- base_v9 四组都失败；A/B 只有相对 door progress 优势。
- Policy 基本持续发 close command，但 durable bilateral grasp 没有形成。
- j8/body8 会被单侧接触载荷顶开；静态 P response 可能先于 effort cap 成为限制。
- A/B locked-base route 没有让 base 跟门；当前 C/D unlocked reward/gate 语义也没有学出更好 route。
- Higher gain 只改善 transient signal，没有保留 contact。
- 当前 scripted diagnostics 没有到达能判断 geometry/offset 的 clean scientific state。

### 尚未证实

- `grasp_target` 是否在当前 jaw inner-pad 的最佳 midpoint。历史 target-side 修改是把 `grasp_target` X 对齐 `handle_inside` lever center（随 `-axle_length/2` randomization）并移除 Z `+0.02`，修正当时约 `4.5–6cm` 的 lever-center 偏差；它与 source-side TCP local-Z `0.105→0.085` 的独立 `2cm` 改动、以及未执行的 source-local-Y O-/O0/O+ `-3/0/+3mm` probe 都不是同一坐标变量。这些历史事实本身不能证明当前 target 错误。
- finger/handle exact collider、closing axis/aperture 是否构成主要 root cause。
- imported USD 是否存在 material override，以及显式 friction 1.0 是否会改善或恶化 wedge。
- 一个以 RL 重新训练、正确奖励 base-follow/arm-follow 的 policy 能否稳定持握。

### 本路线不再继续

- 不再扩展 `base_v9` hold oracle、O-/O0/O+、matched-clean state machine。
- 不把 forced-close、更大 effort、更大 Kp 或更高 keep-close scale 单独当成已验证修复。
- 不把 threshold `.6`、violent Kd5 route 或 stage4 arm-default-pose shaping 恢复为默认。
- 不从 C/D 失败推导“base mobility 无效”，也不把 A 的 single-seed lead 当作 winner。

这个停止决定随后产生了已完成的 `base_v10` scratch A/B/C/D；结果见 Section 12。它不构成恢复 `base_v9` diagnostics 的理由。

## 8. 训练命令经验

以下命令是根据保存的 Hydra overrides/config **重建的可复现模板**，不是原始 shell 的逐字副本。正式 v9 资源分配为四组并行，每组 2 GPU / 2 ranks，每 rank `num_envs=2048`，即每组总 env 4096：

| Group | GPUs | Ablation | Experiment |
|---|---|---|---|
| A | `0,1` | `wbmanip/base_v9_A` | `base_v9_A` |
| B | `2,3` | `wbmanip/base_v9_B` | `base_v9_B` |
| C | `4,5` | `wbmanip/base_v9_C` | `base_v9_C` |
| D | `6,7` | `wbmanip/base_v9_D` | `base_v9_D` |

```bash
PYTHONPATH=$PWD \
VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/nvidia_icd.json \
CUDA_VISIBLE_DEVICES=<GPU_PAIR> \
WANDB_MODE=offline \
HYDRA_FULL_ERROR=1 \
/home/baoquanc/anaconda3/envs/isaaclab/bin/accelerate launch \
  --multi_gpu \
  --num_processes 2 \
  gr00t/rl/train_agent_trl.py \
  +exp=wbmanip/door_open_a2_base_lstm \
  +ablation=wbmanip/<base_v9_A_OR_B_OR_C_OR_D> \
  project_name=a2_piper_full_stage_a2_base \
  experiment_name=<base_v9_A_OR_B_OR_C_OR_D> \
  headless=True \
  simulator.config.cameras.enable_cameras=false \
  simulator.config.render_results=false \
  num_envs=2048 \
  seed=0 \
  auto_load_latest=False \
  checkpoint=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/a2_piper_full_stage_a2_base/base_v8_A_release_after_open-20260708_215459/model_step_001000.pt \
  checkpoint_load_mode=policy_only \
  algo.trl.num_total_batches=1000
```

训练比较必须保持 seed、source checkpoint、batch budget、rank 数与 total env 一致。一个 PPO batch / 64 timesteps 的 smoke 只证明 startup、reward registration 与 load routing，不代表 policy quality。若某组 OOM，应统一调整所有组的资源 contract，不能只降低一组破坏 matched comparison。

## 9. Matched Scalar / Trace Eval 命令经验

同样是根据保存 overrides 重建。Sibling worktree 或 editable install 并存时应使用 module invocation，避免 direct script path 导入当前 worktree 的错误 source：

```bash
PYTHONPATH=$PWD \
VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/nvidia_icd.json \
CUDA_VISIBLE_DEVICES=<ONE_GPU> \
HYDRA_FULL_ERROR=1 \
/home/baoquanc/anaconda3/envs/isaaclab/bin/python \
  -m gr00t.rl.eval_agent_trl \
  +checkpoint=<MODEL_STEP_001000.PT> \
  ++headless=True \
  ++num_envs=16 \
  ++seed=0 \
  ++use_wandb=false \
  ++simulator.config.cameras.enable_cameras=false \
  ++simulator.config.render_results=false \
  ++algo.config.eval.num_eval_episodes=16 \
  ++algo.config.eval.eval_num_envs_episodes=true \
  ++algo.config.eval.dump_to_log_metrics=true \
  ++algo.config.eval.a2_diagnostic_trace_enabled=true \
  ++algo.config.eval.save_videos=false \
  ++algo.config.eval.save_trajectories=false \
  ++eval_name=<MATCHED_SCALAR_NAME> \
  ++eval_output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_eval/base_vN/<MATCHED_SCALAR_NAME>
```

`eval_num_envs_episodes=true` 的口径是每个 env 的 first episode；跨 config 比较时必须保持 seed、env count、episode contract 与 checkpoint step 一致。请求 overrides 之外还要核对输出目录中的 `.hydra/runtime_config.yaml`，因为 eval 会做 saved-config migration 和 load-mode normalization。

## 10. Render 命令经验

Render 应与 scalar 使用同一 checkpoint、seed、env/episode contract，只把 rendering 打开并关闭不必要的 trace dump：

```bash
PYTHONPATH=$PWD \
VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/nvidia_icd.json \
CUDA_VISIBLE_DEVICES=<ONE_GPU> \
HYDRA_FULL_ERROR=1 \
/home/baoquanc/anaconda3/envs/isaaclab/bin/python \
  -m gr00t.rl.eval_agent_trl \
  +checkpoint=<MODEL_STEP_001000.PT> \
  ++headless=True \
  ++num_envs=16 \
  ++seed=0 \
  ++use_wandb=false \
  ++simulator.config.cameras.enable_cameras=false \
  ++simulator.config.render_results=true \
  ++algo.config.eval.num_eval_episodes=16 \
  ++algo.config.eval.eval_num_envs_episodes=true \
  ++algo.config.eval.dump_to_log_metrics=false \
  ++algo.config.eval.a2_diagnostic_trace_enabled=false \
  ++algo.config.eval.save_videos=false \
  ++algo.config.eval.save_trajectories=false \
  ++eval_name=<MATCHED_RENDER_NAME> \
  ++eval_output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_eval/base_vN/<MATCHED_RENDER_NAME> \
  ++env.config.save_rendering_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_eval/base_vN/<MATCHED_RENDER_NAME>/renderings
```

Render 经验：

- Scalar/trace 是 primary evidence；render 只解释 contact position、detach、jam、doorframe event 与动作自然性。
- v9 B 生成了 48 个预期 episode0 artifacts；A 除 48 个有效 episode0 artifacts 外还多出 3 个 env0 episode1 terminal-only artifacts，所以 A strict total-count FAIL。
- 不用目录名或视频名独立判断 provenance；至少核对 mtime、saved Hydra config、checkpoint path、seed 和 env id。
- `++` 是对 eval saved config 的显式 Hydra override；不要把训练命令的 `+ablation` 语法直接照搬到 checkpoint eval。

## 11. Evidence Map

- v8→v9 historical design/formal report：[`base_v8_to_v9_hold_handle_diagnostic_20260710.md`](base_v8_to_v9_hold_handle_diagnostic_20260710.md)
- v9 B training overrides：[`overrides.yaml`](../../logs_rl/a2_piper_full_stage_a2_base/base_v9_B-20260710_212247/.hydra/.hydra/overrides.yaml)
- v9 B matched scalar overrides：[`overrides.yaml`](../../logs_eval/base_v9/base_v9_B_ckpt1000_matched_scalar_trace_16env_20260711/hydra/.hydra/overrides.yaml)
- v9 B matched render overrides：[`overrides.yaml`](../../logs_eval/base_v9/base_v9_B_ckpt1000_matched_render16_20260711/hydra/.hydra/overrides.yaml)
- matched-clean requested overrides：[`overrides.yaml`](../../logs_eval/base_v9/base_v9_B_matched_clean_preflight_8env_20260713/hydra/.hydra/overrides.yaml)
- matched-clean resolved config：[`runtime_config.yaml`](../../logs_eval/base_v9/base_v9_B_matched_clean_preflight_8env_20260713/hydra/.hydra/runtime_config.yaml)
- matched-clean result：[`a2_hold_oracle_summary.json`](../../logs_eval/base_v9/base_v9_B_matched_clean_preflight_8env_20260713/a2_hold_oracle_summary.json)
- matched-clean runtime identity：[`a2_hold_diagnostic_runtime_metadata.json`](../../logs_eval/base_v9/base_v9_B_matched_clean_preflight_8env_20260713/a2_hold_diagnostic_runtime_metadata.json)
- base_v10 A/B/C/D matched scalar/trace：Section 12.2 的四个 `logs_eval/base_v10/base_v10_*_ckpt1000_matched_scalar_trace_16env_20260714` directory
- base_v10 training provenance：Section 12.1 的四个 saved run config/overrides 与 W&B run id

## 12. Base v10 Scratch A/B/C/D（2026-07-14 update）

### 12.1 Training provenance 与唯一变量

四组实际目录与 W&B run id：

| Group | Run / W&B | 相对前一组的唯一配置变化 |
|---|---|---|
| A | [`base_v10_A_scratch_control-20260713_174440`](../../logs_rl/a2_piper_full_stage_a2_base/base_v10_A_scratch_control-20260713_174440), `e6gzkfha` | scratch control；threshold `.25`；base locked；finger `80/3`；默认 hold scales |
| B | [`base_v10_B_scratch_hold_reward-20260713_174446`](../../logs_rl/a2_piper_full_stage_a2_base/base_v10_B_scratch_hold_reward-20260713_174446), `bq4qj8ik` | A + hold bundle `.1/2/1/2/4/-2` |
| C | [`base_v10_C_scratch_hold_reward_kp160-20260713_174452`](../../logs_rl/a2_piper_full_stage_a2_base/base_v10_C_scratch_hold_reward_kp160-20260713_174452), `4hjn6qv4` | B + finger Kp/Kd `160/6`；base 仍 locked |
| D | [`base_v10_D_scratch_hold_reward_kp160_base-20260713_174459`](../../logs_rl/a2_piper_full_stage_a2_base/base_v10_D_scratch_hold_reward_kp160_base-20260713_174459), `78mm9bbi` | C + `a2_stage3_base_unlocked=true` |

四个 step1000 checkpoint 都通过 ZIP integrity check。Saved overrides/config 共同证明：`checkpoint=null`、`auto_load_latest=false`、seed0、命令字面值 `num_envs=4096`、`--num_processes 2`、1000 batches、`WANDB_MODE=online`、fixed reward-penalty scale、stage2 contact threshold `1.0`、stage3→4 threshold `.25`、PhysX velocity iterations `1`。失败且已清理的 `20260713_173141` setsid launcher 不属于上述实验。

### 12.2 Matched eval 口径与 artifacts

四组都用各自 saved training config 加载对应 step1000 checkpoint，并统一使用：module invocation、seed0、16 env、每 env first episode、forced close=false、hold oracle=false、render=false。每组 `metrics_eval.json` 都有 16 个 completed episodes，trace 只包含 episode index 0，`stage2_step_trace.json` 与 compatibility alias byte-identical：

- [A scalar/trace](../../logs_eval/base_v10/base_v10_A_ckpt1000_matched_scalar_trace_16env_20260714)
- [B scalar/trace](../../logs_eval/base_v10/base_v10_B_ckpt1000_matched_scalar_trace_16env_20260714)
- [C scalar/trace](../../logs_eval/base_v10/base_v10_C_ckpt1000_matched_scalar_trace_16env_20260714)
- [D scalar/trace](../../logs_eval/base_v10/base_v10_D_ckpt1000_matched_scalar_trace_16env_20260714)

Hydra 另生成 timestamped provenance directory：A=`20260714_002808-*`、B=`002646-*`、C=`002655-*`、D=`002804-*`。这些目录已纳入只读 evidence accounting；它们不是另一轮 eval。

四组 scalar eval 绑定同一输入 manifest `c58031dcf97032fe05e6eddc583a67f2b8f2aafd6fab37604bbfdfc06dbd5ef9`，checkpoint、saved config/overrides 与相关 eval/env/simulator source 在各 run 前后 hash 不变。该 manifest 证明本次 A/B/C/D eval 可比，不证明 2026-07-13 training 时的 uncommitted source 与当前 source 完全相同。

指标定义：hinge max/terminal/rebound 是 16 个 first episodes 的 per-env 值再取 mean，其中 rebound=`max-terminal`；contact/joint fractions 是指定 stage 的 pooled trace frames；stage3 duration 是每 env 的 recorded unique control steps，按 50Hz 换算；TCP distance 是 source TCP 到 handle target 的 pooled mean。不同 stage exposure 的 pooled fractions 不能直接混成一个总分，所以这里用 audit tables，不构造 composite score。

### 12.3 Task / door / stage 结果

| Group | Goal / terminal | Max stage | Stage3 / Stage4 entry | Hinge max / terminal / rebound mean (rad) | Recorded stage3 duration | Stage3/4 base max / end XY displacement mean (m) |
|---|---|---:|---:|---:|---:|---:|
| A | `0/16`; `16/16 stage_overtime` | 2 | `0/16` / `0/16` | `.000107 / .000092 / .000015` | N/A | N/A |
| B | `0/16`; `16/16 stage_overtime` | 3 | `16/16` / `0/16` | `.001156 / .000476 / .000680` | `409.1` steps ≈ `8.18s` | `.02579 / .01129` |
| C | `0/16`; `16/16 stage_overtime` | 2 | `0/16` / `0/16` | `~0 / ~0 / 0` | N/A | N/A |
| D | `0/16`; `16/16 stage_overtime` | 3 | `16/16` / `0/16` | `.001073 / .001028 / .000045` | `469.1` steps ≈ `9.38s` | `.02871 / .02215` |

Paired env direction：A→B 的 max hinge `16/16` 增加且 stage3 entry `+16`；B→C 的 max hinge `16/16` 下降且 stage3 entry `-16`；C→D 的 max hinge `16/16` 增加且 stage3 entry `+16`。这些变化首先是 learned-route/stage-exposure 差异，不是纯 stage3 mechanism 的因果估计。B 与 D 的绝对 hinge 都比 `.25rad` threshold 小两个数量级以上。

### 12.4 Stage3/4 hold quality（只比较实际进入 stage3 的 B/D）

| Metric | B | D |
|---|---:|---:|
| Pooled stage3/4 frames | `6,545` | `7,505` |
| Any / bilateral contact | `99.878% / 99.282%` | `100% / 100%` |
| Contact stability | `98.701%` | `99.147%` |
| Close-command / over-force | `100% / 0%` | `100% / 0%` |
| Mean body7 / body8 force | `9.162 / 3.616N` | `3.911 / 3.746N` |
| body8 force share | `28.30%` | `48.93%` |
| j7 / j8 open-limit proximity | `91.658% / 2.796%` | `0% / 0%` |
| Envs with j8 open-limit proximity | `7/16` | `0/16` |
| Mean j7 / j8 position | `.03460 / -.02997m` | `.02335 / -.01974m` |
| TCP-handle distance mean | `.01821m` | `.01040m` |
| Arm soft-margin `<=0` | none observed | none observed |

D 同时满足 bilateral、contact balance、close、stability、no-over-force 与 no-gripper-limit saturation；B 虽然 bilateral 很高，却把 j7 长时间推近 `+0.035m` open limit。D 因而是 hold behavior 的 bounded leader，但其 hinge 几乎不动，不能升级为 task baseline success。

A/C 没进入 stage3；为了不把“没有 stage exposure”误写为 hold failure，单独记录其 stage2 diagnostics：

| Metric in stage2 | A | C |
|---|---:|---:|
| Frames | `6,157` | `5,516` |
| Any / bilateral contact | `93.422% / 8.608%` | `0% / 0%` |
| Contact stability | `0%` | `0%` |
| Close-command / over-force | `97.158% / 0%` | `0% / 0%` |
| Mean body7 / body8 force | `.697 / 1.328N` | `0 / 0N` |
| j7 / j8 open-limit proximity | `2.209% / .016%` | `99.783% / 0%` |
| Mean j7 / j8 position | `.01127 / -.01336m` | `.03500 / -.03357m` |
| TCP-handle distance mean | `.00764m` | `.26161m` |
| Arm soft-margin `<=0` | j6, `7/16` envs | j3, `16/16` envs |

C 是 open/no-contact policy basin，而不是“在同一 stage3 hold 下提高 stiffness”的结果。因此 B/C 不能回答 Kp160 是否降低 j8 backdrive；它只再次证明 actuator change 会改变 scratch RL basin。

### 12.5 D matched render：定性复核与 artifact caveat

[D matched render](../../logs_eval/base_v10/base_v10_D_ckpt1000_matched_render_16env_20260714) 使用同一 D checkpoint、seed0、16 env 与 first-episode contract。Render input manifest 为 `04257a1e58deffce300d6d8a545a2875b1f4d8e0935b5ad5c827eaa9550e4358`，运行前后 8 个输入 hash 不变；log 记录 `Finished evaluation` 且 process 自然终止，但 command runner 没有回传可核对的 numeric exit code，因此显式 `exit 0` 保持 unverified。

- 产出 48 个 finalized、non-empty MP4，正好是 16 default + 16 handle-side + 16 handle-top；每个 env 只有 episode0000，全部 filename 为 `len553_reason-stage_overtime`，无 `.writing.mp4` 或 episode1。
- `metrics_eval.json` 与 scalar direction 一致：16 episodes、全部 goal=false、max stage3、stage_overtime。
- 抽查低/中/最高 hinge 的 env12/env0/env3 三视角时间序列：policy 接近后把两侧 jaw 长时间留在 handle 周围；arm/base 只有小幅姿态漂移，door/handle 没有可见持续转动。这只定性支持“stationary bilateral hold”，不产生新的 success 或因果结论。
- Runtime QA 的严格 no-trace artifact check 为 FAIL：resolved flag 虽为 `a2_diagnostic_trace_enabled=false`，output root 仍出现两个各 `41,151,204` bytes 的 trace JSON；两者 SHA-256 都是 `c7f1e0235d6c619545aea1a4fe76cd0634bf03dfb241cd9d3d616fb35b31dbf3`。
- Targeted source diagnosis PASS：当前 trainer 只用 `env._use_a2_base` 决定 base stage2–5 trace 是否写出；`a2_diagnostic_trace_enabled=false` 只关闭 expanded action/reward diagnostics，不关闭 52-field base trace。Trace capture 发生在 physics/reward 后，forced-close/oracle 又分别保持 false，因此这个 output-hygiene side effect 不修改 policy action。视频可保留为定性证据，但不能称为 trace-free，也不伪报整条 render QA PASS。

### 12.6 Joint-limit / workspace 证据边界

- 已证实的 terminal reason 只有 `stage_overtime`；四组都没有被日志归因为 joint-limit/workspace termination。
- Saved config 关闭 `terminate_when_close_to_dof_pos_limit`。Trace 的 normalized soft-margin `<=0` 只能标记 proximity/violation signal，不能改写成 terminal cause。
- A 的 j6 与 C 的 j3 proximity 是 workspace-pressure 线索；B/D 没观察到 arm soft-margin `<=0`。是否存在未记录的 kinematic bottleneck、以及它是否导致 policy 不推门，仍未证实。

### 12.7 因果解释：已证实、推测、未证实

| 结论等级 | 结论 |
|---|---|
| 已证实 | A/C 不进入 stage3；B/D 全部进入 stage3；四组都不进入 stage4且 task failure。 |
| 已证实 | B 的 hold shaping 与 learned route 同时出现；B 的 stage3/4 bilateral/stability 很高，但 j7 saturation 严重。A 没有 matched stage3 exposure，因此 A/B 不能单独隔离“retention 是否改善”。 |
| 已证实 | C 没有 contact/stage3 exposure；B/C 不能评价 stiffness 的 stage3 anti-backdrive 效果。 |
| 已证实 | D 恢复 stage3 entry并形成最均衡的 bilateral hold；C/D 仍因 stage exposure 不同，不能单独证明 base movement 是改善原因。 |
| 推测 | D 的强、无需 hinge motion 的 hold rewards 与既有 `push_door_hinge=6` 共同形成 stationary-hold local optimum。该机制与 runtime 一致，但必须通过 reward-scale intervention 才能验证。 |
| 未证实 | 单 seed 的跨 seed generalization、base unlock 的独立因果收益、reward dominance 是唯一 root cause、任何 joint/workspace terminal failure，以及 training-time uncommitted source 与当前 eval source 的逐字 equivalence。 |

### 12.8 base_v11 历史提案（已执行；由 Section 13 supersede）

> 本节只保留当时的 proposal provenance，下面的旧命令不得复用。实际启动时 A/B 已更正为全局 `num_total_batches=2000`、`save_frequency=500`，并增加了从 v10_D step1000 full-state resume、全局目标 step2000、save250 的 C；实际 checkpoint/eval 与下一轮建议以 Section 13 为准。特别地，full-state resume 的 `num_total_batches` 是全局 iteration 上限，不是 remaining count。

最小批准范围是两组、每组重新 scratch：

| Group | Base | 唯一变量 | 问题 |
|---|---|---|---|
| `base_v11_A_D_control` | exact saved D | none；显式保持 `push_door_hinge=6` | D direction 是否可复现 |
| `base_v11_B_D_hinge12` | exact saved D | `push_door_hinge: 6→12` | 增强已有 progress incentive 是否能打破 stationary hold |

若用户批准第三组，再增加 `base_v11_C_D_stability05`：相对 D 只把 `a2_stage3_stage4_contact_stability: 4→0.5`，不与 H+ 累加；`0.5` 是 direct reward-config default。它回答 history-based stability bonus 是否过强。不要增加 Kp/effort variant；D 已经是 `160/6` 且没有 gripper-limit saturation。

共同 training contract 保持 v10：`checkpoint=null`、`auto_load_latest=false`、seed0、`num_envs=4096` 字面值、1000 batches、2 GPU / 2 processes、threshold `.25`、online W&B、fixed penalty scale、velocity iterations `1`。每组使用独立 foreground terminal、GPU pair、port 与约 10 秒 stagger；看到各自 `model_step_001000.pt` 后由用户在对应 terminal `Ctrl-C`。以下是 saved D overrides 重建的命令模板，不会在本次自动执行：

```bash
PYTHONPATH=$PWD \
VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/nvidia_icd.json \
CUDA_VISIBLE_DEVICES=<GPU_PAIR> \
WANDB_MODE=online \
HYDRA_FULL_ERROR=1 \
/home/baoquanc/anaconda3/envs/isaaclab/bin/accelerate launch \
  --multi_gpu \
  --num_processes 2 \
  --main_process_port <UNIQUE_PORT> \
  gr00t/rl/train_agent_trl.py \
  +exp=wbmanip/door_open_a2_base_lstm \
  project_name=a2_piper_full_stage_a2_base \
  experiment_name=<base_v11_A_D_control_OR_base_v11_B_D_hinge12> \
  headless=True \
  simulator.config.cameras.enable_cameras=false \
  simulator.config.render_results=false \
  num_envs=4096 \
  seed=0 \
  auto_load_latest=False \
  checkpoint=null \
  algo.trl.num_total_batches=1000 \
  rewards.reward_penalty_curriculum=false \
  rewards.reward_initial_penalty_scale=1.0 \
  rewards.reward_min_penalty_scale=1.0 \
  rewards.reward_max_penalty_scale=1.0 \
  rewards.reward_penalty_degree=0.0 \
  env.config.a2_stage2_contact_force_threshold=1.0 \
  env.config.a2_stage3_to4_door_hinge_threshold=0.25 \
  env.config.a2_stage3_base_unlocked=true \
  robot.control.stiffness.arm_j7=160.0 \
  robot.control.stiffness.arm_j8=160.0 \
  robot.control.damping.arm_j7=6.0 \
  robot.control.damping.arm_j8=6.0 \
  rewards.reward_scales.a2_stage3_stage4_keep_close_command=0.1 \
  rewards.reward_scales.a2_stage3_stage4_both_contact=2.0 \
  rewards.reward_scales.a2_stage3_stage4_opposite_squeeze=1.0 \
  rewards.reward_scales.a2_stage3_stage4_squeeze_force_window=2.0 \
  rewards.reward_scales.a2_stage3_stage4_contact_stability=4.0 \
  rewards.reward_scales.penalty_a2_stage3_stage4_over_force=-2.0 \
  rewards.reward_scales.push_door_hinge=<6.0_FOR_CONTROL_OR_12.0_FOR_H+> \
  simulator.config.sim.physx.num_velocity_iterations=1
```

Promotion gate：先复用本报告的 matched scalar/trace contract；primary 是 stage4 entry count 与 per-env hinge max/terminal/rebound，hold guardrail 是 stage3/4 bilateral/contact-stability `>=95%`、over-force `0%`、且不重新出现 j7/j8 open-limit saturation。至少一个 stage4 entry 才把 variant 标成 promising；sub-threshold hinge improvement 只能写成 directional evidence。单 seed 仍不产生 statistical winner；通过方向 gate 后再决定是否补 seeds。

Raw traces 与长日志继续保留在原 run directory；本报告只保存可复用结论、口径与入口。

## 13. Base v11：incomplete-budget matched eval

### 13.1 实际训练与 checkpoint 边界

三组 saved contract 都把 `algo.trl.num_total_batches` 设为全局 step2000，但实际 artifact 在更早的 state 停止。九个现存 payload 都通过 ZIP integrity 与 CPU `torch.load`，并含 policy、value、optimizer、scheduler、environment 与 trainer state；它们是可用的 full-state checkpoint，但不能伪装成 step2000 结果。

| Group | Initialization / 唯一设计变量 | Global cap / save | 可评估 state | W&B / log 最后 iteration | 缺失的计划 checkpoint |
|---|---|---:|---|---:|---|
| A `base_v11_A_D_control` | scratch；saved D config，hinge=`6` | `2000 / 500` | `500, 1000, last=1150` | `m3sd8noh` / `1174` | `1500, 2000` |
| B `base_v11_B_D_hinge12` | scratch；相对 A 仅 hinge `6→12` | `2000 / 500` | `500, 1000, last=1150` | `9k5eko6c` / `1183` | `1500, 2000` |
| C `base_v11_C_D_resume_step1000_to2000` | v10_D step1000 full-state resume；hinge=`6` | `2000 / 250` | `1250, 1500, last=1550` | `1mate3bs` / `1593` | `1750, 2000` |

`last.pt` 的 persisted global step 低于 console 最后一行是正常的 save cadence 差异；本报告按 checkpoint 内 state 命名，不把 log iteration 当成可加载 checkpoint。现有 log 没有足以判定 normal completion、异常退出或人工停止原因的 terminal marker。因此本节只做 incomplete-budget bounded comparison；不能推断训练到 step2000 会保持同样结果。

Full-state resume 的 durable contract 再次确认：`num_total_batches` 是恢复后的**全局 iteration 上限**。从 step1000 续到 step2000 必须传 `2000`；传 `1000` 会因 restored `global_step >= max_steps` 立即结束。

### 13.2 Matched eval contract、artifact 与 source 边界

九个 eval 都使用 `python -m gr00t.rl.eval_agent_trl`、各自 saved config、seed0、16 env、每 env first episode；camera/render/video/trajectory、forced-close、hold oracle 都关闭，scalar/trace diagnostics 打开。每次都是 `16/16` first episodes、JSON parse PASS、trace aliases byte-identical、process exit0。有效 artifact：

- A：[step500](../../logs_eval/base_v11/base_v11_A_ckpt0500_matched_scalar_trace_16env_seed0_20260714)、[step1000](../../logs_eval/base_v11/base_v11_A_ckpt1000_matched_scalar_trace_16env_seed0_20260714)、[staged step1150](../../logs_eval/base_v11/base_v11_A_last_step1150_staged_matched_scalar_trace_16env_seed0_20260714)
- B：[step500](../../logs_eval/base_v11/base_v11_B_ckpt0500_matched_scalar_trace_16env_seed0_20260714)、[step1000](../../logs_eval/base_v11/base_v11_B_ckpt1000_matched_scalar_trace_16env_seed0_20260714)、[staged step1150](../../logs_eval/base_v11/base_v11_B_last_step1150_staged_matched_scalar_trace_16env_seed0_20260714)
- C：[step1250](../../logs_eval/base_v11/base_v11_C_ckpt1250_matched_scalar_trace_16env_seed0_20260714)、[step1500](../../logs_eval/base_v11/base_v11_C_ckpt1500_matched_scalar_trace_16env_seed0_20260714)、[staged step1550](../../logs_eval/base_v11/base_v11_C_last_step1550_staged_matched_scalar_trace_16env_seed0_20260714)

Evaluator 会在 checkpoint 邻近目录创建 `exported/`，并按 loaded global step 写一个 checkpoint clone。为避免修改 frozen training directories，三个 `last.pt` 先复制到 `logs_eval/_eval_inputs/`，再从 staging eval；曾直接运行产生的 A step1150 与中断的 C step1550 artifact 已排除，不进入任何结论。原训练目录中的 task-created clone/exported 已清理并复核 hash。

本轮不新增 render：A/B 没有 stage3/contact/hinge event；C 的 scalar/trace 与 v10_D 已 render 的 stationary bilateral hold 同方向，且没有 stage4、新 terminal 或明显 hinge excursion。C step1550 的单个 handle-reward transient 没有伴随 hinge/stage 改变。重复视频不会改变 primary evidence。

当前 eval-source manifest 为 `6d5730616d91530e59c9f5f0ce7d4de6ac3e5b12fd085e62126656434bda71ef`。v10 报告只保留 aggregate manifest ID，缺少 member hashes 与构造算法，因此 current eval source 与 v10 eval source的 byte equality/mismatch 都未证实。更重要的是，v10_D training process 约在 `2026-07-13 17:45 HKT` 启动，而当前五个关键 source 文件 mtime 为当日 `19:02–20:56`，均晚于 v10_D 启动、早于 v11 启动：

| Source | Current mtime (HKT) | Current SHA-256（前 12 位） |
|---|---|---|
| `legged_robot_base.py` | `19:02:43` | `ce42c48e4a6e` |
| `eval_agent_trl.py` | `19:34:10` | `7f0edb3c1ecc` |
| `door_open_a2_base.py` | `19:45:05` | `e07e9867d3d8` |
| `inference_helpers.py` | `19:50:33` | `1e1299c12444` |
| `isaacsim.py` | `20:56:19` | `6070c65233f7` |

已证实的是 current file state 晚于 v10_D launch；“v10_D 已加载的 training source 与 v11 相同”未证实，并存在 material temporal confound。尤其当前 `door_open_a2_base.py` 的 dirty diff 改变了 A2 non-finger DOF observation ordering；它在 v11 时已存在，但是否导致 scratch route 分叉没有 intervention 证据。故 A 是 exact saved-config control，不是已证明的 exact source control，也不能把未复现 D 单独归因为随机初始化。

### 13.3 Task、door 与 stage 结果

下表 hinge 为 16 个 first episodes 的 `mean(per-env max) / mean(terminal) / mean(rebound)`；dominant-stage duration 是 mean unique control steps，按 50Hz 换算。所有行都是 `0/16 goal`、`16/16 stage_overtime`、`0/16 stage4 entry`。

| Policy state | Max stage / stage3 entry | Hinge max / terminal / rebound (rad) | Dominant-stage duration |
|---|---:|---:|---:|
| v10_D step1000 reference | `3 / 16/16` | `.00107280 / .00102779 / .00004501` | stage3 `469.1` steps ≈ `9.38s` |
| v11_A step500 | `2 / 0/16` | `.000000151 / .000000151 / 0` | stage2 `369.2` steps ≈ `7.38s` |
| v11_A step1000 | `2 / 0/16` | `.000000151 / .000000151 / 0` | stage2 `374.1` steps ≈ `7.48s` |
| v11_A step1150 | `2 / 0/16` | `.000000151 / .000000151 / 0` | stage2 `374.6` steps ≈ `7.49s` |
| v11_B step500 | `2 / 0/16` | `.000000151 / .000000151 / 0` | stage2 `370.4` steps ≈ `7.41s` |
| v11_B step1000 | `2 / 0/16` | `.000000151 / .000000151 / 0` | stage2 `373.8` steps ≈ `7.48s` |
| v11_B step1150 | `2 / 0/16` | `.000000151 / .000000151 / 0` | stage2 `373.6` steps ≈ `7.47s` |
| v11_C step1250 | `3 / 16/16` | `.00100665 / .00095421 / .00005244` | stage3 `473.6` steps ≈ `9.47s` |
| v11_C step1500 | `3 / 16/16` | `.00112864 / .00103027 / .00009837` | stage3 `476.4` steps ≈ `9.53s` |
| v11_C step1550 | `3 / 16/16` | `.00111019 / .00103435 / .00007584` | stage3 `475.6` steps ≈ `9.51s` |

A/B 在三个 aligned states 的 per-env hinge values 完全相同；由于两组都不进入 stage3，而 `push_door_hinge` 只在 stage3/4 生效，B 的 hinge12 intervention 没有获得 stage exposure，不能据此判断 H+ 有效或无效。A/B 的真实差别只表现为各自学到的 stage2 open/no-contact basin 细节。

C 相对 v10_D 的 mean max hinge 差为：step1250 `-.00006615rad`（9/16 env 更高）、step1500 `+.00005584rad`（11/16）、step1550 `+.00003739rad`（12/16）。C step1500 相对 step1250 为 `+.00012199rad`（13/16），step1550 相对 step1250 为 `+.00010354rad`（12/16）。方向上有轻微增量，但绝对量只有约 `1e-4rad`，仅占 `.25rad` stage4 threshold 的约 `0.04%`；C step1550 的 mean max hinge 也只有 threshold 的 `0.44%`。这不是 breakthrough。

### 13.4 Hold、contact、joint 与 workspace guardrails

只有 C 与 v10_D 有 stage3 exposure；其 stage3/4 pooled guardrails 如表。Force share=`body8/(body7+body8)`：

| State | Frames | Bilateral / stability | Close / over-force | body7 / body8 force; body8 share | TCP-handle | Base max / end XY |
|---|---:|---:|---:|---:|---:|---:|
| v10_D step1000 | `7,505` | `100% / 99.147%` | `100% / 0%` | `3.911 / 3.746N; 48.93%` | `.01040m` | `.02871 / .02215m` |
| v11_C step1250 | `7,577` | `100% / 99.155%` | `100% / 0%` | `4.007 / 3.788N; 48.59%` | `.01278m` | `.02779 / .02119m` |
| v11_C step1500 | `7,622` | `100% / 99.160%` | `100% / 0%` | `3.743 / 3.889N; 50.96%` | `.01149m` | `.02980 / .02206m` |
| v11_C step1550 | `7,610` | `100% / 99.159%` | `100% / 0%` | `3.797 / 3.831N; 50.22%` | `.01060m` | `.02860 / .02145m` |

C 确实保持了 bilateral/contact balance、close、stability、no-over-force 与 base-follow displacement；问题不是 retention 再次崩溃，而是这些稳定信号没有转化为 hinge motion。A/B 无 stage3 samples，不能把 N/A 写成 `0% hold`。

| Latest state | Stage exposure | Mean j7 / j8 pos | j7 / j8 open-limit proximity | TCP-handle | Arm soft-margin `<=0` |
|---|---|---:|---:|---:|---|
| v11_A step1150 | stage2 only | `.03500 / -.03361m` | `99.650% / 0%` | `.29550m` | j3 `11/16`；j5 `16/16` envs |
| v11_B step1150 | stage2 only | `.03500 / -.03356m` | `99.498% / .033%` | `.26232m` | j5 `16/16` envs |
| v11_C step1550 | stage3 | `.02254 / -.02055m` | `0% / 0%` | `.01060m` | j6 `3/16` envs |
| v10_D step1000 | stage3 | `.02335 / -.01974m` | `0% / 0%` | `.01040m` | none observed |

A/B 的主要 guardrail failure 是 j7 长期贴近 `+0.035m` open limit 和 TCP 远离 handle，不是用户特别关注的 j8 `-0.035m` saturation；B 只有极少 j8 proximity frames。C/D 的 j7/j8 都不饱和。所有 policy 的 formal terminal reason 仍只有 `stage_overtime`；soft-margin 是 workspace-pressure signal，不是 joint-limit termination。

### 13.5 实际 reward magnitude

以下是有 stage3 exposure 的 per-trace-frame scaled reward mean；hold bundle 是 keep-close、both-contact、opposite-squeeze、force-window、stability 与 over-force/open-command 项之和：

| State | Hold bundle | Hinge reward | Handle reward | Hold / abs(hinge) |
|---|---:|---:|---:|---:|
| v10_D step1000 | `.181317` | `.00009556` | `-.012182` | `1,898×` |
| v11_C step1250 | `.181324` | `.00006929` | `-.012903` | `2,617×` |
| v11_C step1500 | `.181328` | `.00007216` | `-.013025` | `2,513×` |
| v11_C step1550 | `.181327` | `.00007086` | `-.013191` | `2,559×` |

典型 hold components 约为 keep-close `.002`、both `.04`、opposite `.02`、force-window `.04`、stability `.0793`，open-command 与 over-force 为 0。已证实的是当前轨迹下存在约三数量级的 realized reward-magnitude imbalance；这不等于已证实 hold reward 在因果上“压制” hinge。把 hinge scale `6→12` 若沿用同一轨迹只会先把很小的 hinge 项翻倍，但 policy 更新后行为是否改变仍需 stage3-exposed intervention。

### 13.6 已证实、推测与未证实

| 等级 | 结论 |
|---|---|
| 已证实 | 九个可用 state 全部 `0/16 goal`、`0/16 stage4`；A/B 始终 stage2，C 始终 stage3。计划 step2000 checkpoint 均不存在，因此这不是 full-budget verdict。 |
| 已证实 | B 的 hinge12 reward 没有 stage3 exposure，A/B 不构成有效 H+ test；C 保留 D 的高质量 bilateral hold，但 hinge 仍约 `.0011rad`。 |
| 已证实 | C/D 的 j7/j8 limit、over-force 与 contact stability guardrails 良好；A/B 则落入 TCP 远离 handle、j7 open-limit 的 stage2 basin。 |
| 已证实 | 当前文件 mtime 晚于 v10_D training launch、早于 v11；因此 A 只证明 saved-config reproduction 失败，不能证明 exact-source reproduction 失败。 |
| 推测 | C/D 是 hold-dominant stationary local optimum；realized reward magnitude 与此一致，但尚无 reward intervention 的因果证明。 |
| 推测 | v10→v11 source-state 差异可能参与 scratch route 分叉；当前 A2 observation-order dirty diff 是 plausible confound，不是已定位 root cause。 |
| 未证实 | H+ 在 stage3 exposure 下是否提升 hinge、任何 run 到 step2000 的行为、多 seed statistical winner、训练提前停止的具体原因、v10 与 current source 的 byte equality。 |

### 13.7 下一轮最小 RL ablation 建议（已 superseded；执行证据见 Section 14）

本节旧的 H+ resume proposal 已被 `base_v11_repair_r1` A/B training/eval 执行证据 supersede；它不再是 active recommendation。后续判断只引用 Section 14 的 matched evidence，不复用本节旧 proposal 的版本命名或 gate。

## 14. `base_v11_repair_r1` A/B 训练/eval 与 logs_eval 布局（2026-07-15）

### 14.1 训练口径

两组都从同一个 v11_C staged step1550 policy-only source 启动：[`base_v11_C_last_step1550/model_step_001550.pt`](../../logs_eval/_eval_inputs/base_v11_C_last_step1550/model_step_001550.pt)。保存配置与启动日志显示 `checkpoint_load_mode=policy_only`、`num_total_batches=500`、`save_frequency=125`、seed0、literal `num_envs=4096`。A/B 唯一的语义差异是 `push_door_handle: 6→0`；两组都保持 `push_door_hinge=6`。

- A：[保存配置](../../logs_rl/a2_piper_full_stage_a2_base/base_v11_repair_r1_A_handle6_control-20260715_161304/config.yaml)，`push_door_handle=6`
- B：[保存配置](../../logs_rl/a2_piper_full_stage_a2_base/base_v11_repair_r1_B_handle0-20260715_161312/config.yaml)，`push_door_handle=0`

### 14.2 Matched eval 结果

八个 eval 均为 seed0、16 env、每 env first episode；每个都已证实为 `0/16 goal`、`0/16 stage4 entry`、terminal `stage_overtime`。下表的 primary/guardrail 数值来自 16 个 first episodes；`stage3 env 数` 是进入 stage3 的 env 数。

| 组别 / step | 精确 scalar/trace artifact | Stage3 env 数 | Hinge max / terminal mean (rad) | Handle max mean | Bilateral / stability | TCP-handle mean (m) | j8 open-limit proximity |
|---|---|---:|---:|---:|---:|---:|---:|
| A125 | [holdterms](../../logs_eval/base_v11/base_v11_repair_r1_A_handle6_ckpt125_matched_scalar_trace_holdterms_16env_seed0_20260715) | 12/16 | `.001405 / .001393` | `.07378` | `54.40% / 41.11%` | `.04734` | `38.01%` |
| A250 | [holdterms](../../logs_eval/base_v11/base_v11_repair_r1_A_handle6_ckpt250_matched_scalar_trace_holdterms_16env_seed0_20260715) | 16/16 | `.001638 / .000410` | `.02287` | `96.94% / 93.96%` | `.04740` | `1.86%` |
| A375 | [holdterms](../../logs_eval/base_v11/base_v11_repair_r1_A_handle6_ckpt375_matched_scalar_trace_holdterms_16env_seed0_20260715) | 16/16 | `.001256 / .000916` | `.07294` | `100% / 99.15%` | `.02615` | `4.77%` |
| A500 | [holdterms](../../logs_eval/base_v11/base_v11_repair_r1_A_handle6_ckpt500_matched_scalar_trace_holdterms_16env_seed0_20260715) | 16/16 | `.002081 / .001540` | `.50734` | `99.80% / 98.73%` | `.02959` | `60.52%` |
| B125 | [holdterms](../../logs_eval/base_v11/base_v11_repair_r1_B_handle0_ckpt125_matched_scalar_trace_holdterms_16env_seed0_20260715) | 16/16 | `.001311 / .001255` | `.000391` | `100% / 99.15%` | `.02756` | `0%` |
| B250 | [holdterms](../../logs_eval/base_v11/base_v11_repair_r1_B_handle0_ckpt250_matched_scalar_trace_holdterms_16env_seed0_20260715) | 16/16 | `.001149 / .001038` | `.001736` | `100% / 99.15%` | `.00992` | `0%` |
| B375 | [holdterms](../../logs_eval/base_v11/base_v11_repair_r1_B_handle0_ckpt375_matched_scalar_trace_holdterms_16env_seed0_20260715) | 16/16 | `.000963 / .000908` | `.000299` | `100% / 99.15%` | `.00841` | `0%` |
| B500 | [holdterms](../../logs_eval/base_v11/base_v11_repair_r1_B_handle0_ckpt500_matched_scalar_trace_holdterms_16env_seed0_20260715) | 16/16 | `.001226 / .001067` | `.000444` | `100% / 99.16%` | `.00839` | `0%` |

### 14.3 证据解释与停止边界

- **已证实：** 上述八个 eval 的结果、A/B 唯一的语义配置差异，以及两组都使用 hinge6；A500 的 mean max hinge 仅为 `.25rad` stage4 threshold 的 `0.832%`。B250/B375 是干净的 stable-hold 诊断锚点，不是 task-progress candidate。
- **推测：** A handle6 motion 与 guardrail regression 同时出现：A500 的 handle max 最大，但也出现 j8/base/workspace/doorframe regression。B handle0 保留 bilateral/stability hold 与平坦的 j8 guardrail，但 hinge 仍平坦且没有 task progress。这些只是 co-occurrence，不是因果归因。
- **未证实：** 没有 statistical winner，没有 checkpoint 可 promotion，也没有建立 causal root cause。Single-seed evidence 不支持 cross-seed/generalization 结论。

### 14.4 logs_eval 布局约定

**未来产物约定：** `logs_eval/base_vN/<eval-run>/` 是单个 eval 的完整 result folder，直接包含 `.hydra/`、`eval.log`、`eval_agent_trl.log`、metrics/traces/diagnostics，以及可选的 `renderings/`。`base_eval.yaml` 现已让 `eval_log_dir` 与 rendering default 跟随 `eval_output_dir`；base-specific A2 命令必须把 `eval_output_dir` 设为 grouped path，并让 `eval_name` 保持 leaf label，不需要另写 `hydra.run.dir` override。对应 config validation 仅为 static/no-sim evidence：`3 passed` 加 resolved compose；它不构成新的 runtime eval 声明。

**历史迁移约定：** 48 个旧 top-level Hydra directory 已按 whole-tree 迁移。其中 36 个 exact-paired directory 位于对应 canonical result 的 `.hydra_provenance/<old-top-dir>`；12 个 versioned/unpaired directory 位于 `base_vN/_unpaired_hydra/<old-top-dir>`。`_eval_inputs` 与 `replay_v2` 继续保留在 `logs_eval/` top-level；迁移后 top-level 共 14 个 entry。`.hydra_provenance` 只是 historical archive，不是 future layout。
