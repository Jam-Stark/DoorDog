# A2 + Piper 推门优化：Base v0 → Base v9 结果与经验（2026-07-13）

> 状态：`base_v9` oracle、static clamp、O-/O0/O+、matched-clean 等诊断路线已经停止。本文件归档截至停止点的证据；下一项 active work 是另行制定并审批 `base_v10` RL 优化/重新训练方案，而不是继续扩展 `base_v9` 诊断。

## 1. 结论先行

- `base_v9_A/B/C/D` 四组都训练到 step1000 / `262,144,000` timesteps，logged values finite、无 runtime error，但 training goal metric 都是 0；matched scalar eval 的 16 个 first episodes 也全部 `0/16 goal`、`stage_overtime`。这一轮没有产生成功 policy。
- Locked-base A/B 在同一 seed/config family 下明显强于 unlocked C/D。A 的 door hinge progress 最高，B 的 terminal hinge 接近且 rebound 更小；这只是 bounded ranking，不是 statistical winner，也不证明所有 base-follow 方案无效。
- Policy 并非没有下发闭合命令：四组 close command ratio 约 `99%`。主要可见 failure 是接触仍由 `arm_body8` 单侧主导、bilateral/contact stability 近乎为 0，并伴随 `arm_j6` / arm workspace bottleneck。
- A/B trace 显示 close target 始终为 `[0, 0]`，但 `arm_j8` 被接触载荷推到 `-0.035` open limit；恶化段常见 `arm_body7=0N`、`arm_body8≈27–51N`，脱离后 j8 又回到接近闭合位置。这证明 jaw 是被外部载荷顶开，不是 policy 主动发出 open command。
- 当前 gripper `Kp=80`，最大闭合 position error 约 `0.035m`，纯 P-control 静态恢复量约为 `80 × 0.035 = 2.8N/finger`，低于 `10N` effort cap。因此不能把问题简化为 effort limit 不够；直接继续提高 effort cap 很可能不改变静态夹持力。
- 没有证据表明 finger/handle 摩擦为零。当前没有专用 material override，runtime identity 记录 `friction_override=null`；未显式指定时使用 simulation default 的解释与现象一致，但 imported asset 是否另有 override 没有被最终证明。现有证据只支持“没有形成足够稳定的 grasp constraint”。
- Higher-gain static clamp 从 `80/3` 增至 `160/6`、`320/12` 只增加 transient bilateral/stability signal；三组 step40 都是 `0/8 any-contact`，且 `320/12` 转而出现 j7 saturation。因此 higher gain 是 partial factor，不是已经验证的训练默认值。
- 最后一轮 matched-clean 为 `0/8 MATCHED_CLEAN_READY`、`8/8 MATCHED_CLEAN_RETREAT_JOINT_LIMIT`。它只证明 eval controller 在 joint soft-limit safety check 处终止，不能推出 `grasp_target` 物理不可达，也没有执行 fresh O0、O-、O+ 或重新训练。

## 2. 当前基线与证据边界

停止点使用的基线是：

| 项目 | 当前值 |
|---|---|
| Policy | [`base_v9_B` ckpt1000](../logs_rl/a2_piper_full_stage_a2_base/base_v9_B-20260710_212247/model_step_001000.pt) |
| Training seed | `0` |
| Piper TCP local-Z | `0.085m` |
| Gripper Kp/Kd | `80/3` |
| Gripper effort limit | `10/10N` |
| Explicit friction override | none (`null`) |
| Formal v9 initialization | [`base_v8_A` ckpt1000](../logs_rl/a2_piper_full_stage_a2_base/base_v8_A_release_after_open-20260708_215459/model_step_001000.pt) actor-only `policy_only` warm-start |

`policy_only` 只 strict-load actor；critic、optimizer、scheduler、global step、env curriculum 与 staged snapshots 都是 fresh。普通 eval 会把 load mode normalize 为 `full` 以恢复 checkpoint/eval semantics，因此最终解释应看保存的 `.hydra/runtime_config.yaml`，不能只看请求时 overrides。

本报告区分三类结论：

- **已证实**：由 matched scalar/trace、saved config 或 JSON summary 直接支持。
- **尚未证实**：geometry、friction override、Cartesian reachability 等没有完成有效 intervention 的假设。
- **停止继续测试**：不是被证明永远无效，而是当前信息增益不足，不再用 `base_v9` 反复扩展 oracle/offset controller。

## 3. Replay v2 与 Base v0 → v9 因果时间线

| 版本 | 主要变量 | Runtime 结果 | 可复用经验 / 教训 |
|---|---|---|---|
| `replay_v2` | stage0–2 control；staging `0.70`；handle height `0.85–0.95m` | 能进入 close gate 并出现 grasp-like 视觉行为，但 both-force/history predicate 不满足 | 视觉上“夹住”不能替代 formal bilateral grasp 指标 |
| [`base_v0`](../logs_eval/20260702_211128-logs_eval/base_v0) | gripper effort `10→30` 单变量 | retrained policy 进入 open-primitive/no-contact basin；reward 约从 `102–105` 降到 `71–82` | effort cap 增大不是 sufficient fix，也可能改变 RL credit/local optimum |
| [`base_v1`](../logs_eval/20260703_092635-logs_eval/base_v1) | arm-only Kp/Kd；effort 回到 `10` | 保留 replay_v2 的 close behavior/reward，但仍没有 formal bilateral success | base_v0 分叉不是普通 retrain 必然漂移；arm gain 路线较稳定但不完整 |
| [`base_v2`](../logs_eval/20260703_144741-logs_eval/base_v2) | gripper Kp/Kd `40/1→80/3`，effort `10` | 再次学出 open primitive、contact/squeeze 为 0 | 不应继续把纯 actuator sweep 当第一优先级 |
| full-stage `base_v3` | dense bilateral/squeeze/contact-stability shaping | reach/close 明显改善，但 `arm_body8` dominance，formal `0/150`；history-3 又会过早放行 stage3 | “route unblocked”不等于 grasp solved；eval 必须核对 checkpoint 中的 `termination_level` 与 `reward_penalty_scale` |
| full-stage `base_v4` | threshold/Kd/velocity-iteration 2×2 | `thr0.8/Kd5/vel0` 可得到 `16/16` completion，但走的是 `250N+` violent route；另一路较温和但仍未解决 grasp | hard predicate 必须与 `squeeze_window`、`over_force` dense semantics 对齐；高 completion 可能是假成功 |
| `base_v5` | historical full-stage baseline | 可用 eval 仍是 body8 单指接触 | 不能按文件名猜 run provenance；曾有“v6 render”经 mtime/saved config 核对其实属于 v5 |
| [`base_v6`](../logs_rl/a2_piper_full_stage_a2_base/base_v6_40_effort_08TCP_offset-20260707_221058) | TCP `0.105→0.085` 与 effort `10→40` 同时变化 | `0/2`，在 stage1 因 pregrasp distance 超阈值停滞 | 两个变量同时改变且没有进入 stage2，不能解读成 effort-only 结论 |
| [`base_v7_A`](../logs_rl/a2_piper_full_stage_a2_base/base_v7_A_tcp085_effort10-20260708_144253) / B | A=`TCP .085/effort10`；B=`.105/40` | A `2/2` complete、training goal `.747`；B `0/2`、stage4 overtime | 当前 baseline 回到 A-like `.085/10`；factor isolation 比混合改动更有信息量 |
| [`base_v8_A`](../logs_rl/a2_piper_full_stage_a2_base/base_v8_A_release_after_open-20260708_215459) / A' | release-after-open；初始 stage3→4 threshold `.6`，A' 恢复 `.174533` 并关闭 stage4 arm-default shaping | `.6` 让 arm-only policy 在约 `.25–.28rad` 前后耗尽 j6 workspace | `.6` 不应直接作为默认；arm 仍需推门时不应把它拉回 default pose |
| `base_v8_B` scratch | hold-handle sibling route | `16/16` stage2 overtime，primitive 始终 open，contact/hinge progress 为 0 | 它没有进入 stage3/4，因此不能评价 hold retention；sibling worktree eval 应使用 module invocation 避免 editable-install 混源 |
| `base_v9_A/B/C/D` | threshold `{.174533,.25}` × stage3 base `{locked,unlocked}`；共同 B hold bundle | 四组全部 `0/16 goal`；A/B progress 强于 C/D，但稳定夹持仍失败 | close reward/command 不是 hold success；单 seed 只能做 bounded ranking |

详细的 v8→v9 design provenance、D0–D3 与原始 A–D 报告保留在 [`base_v8_to_v9_hold_handle_diagnostic_20260710.md`](base_v8_to_v9_hold_handle_diagnostic_20260710.md)。

## 4. Base v9 Formal A/B/C/D

四组共同使用 seed0、step1000、同一个 v8-A actor checkpoint 和相同训练预算：

| Config | Threshold | Stage3 base | Exact run | Goal / terminal | Hinge max / terminal / rebound | Contact stability |
|---|---:|---|---|---|---:|---:|
| A | `0.174533` | locked | [`base_v9_A-20260710_212238`](../logs_rl/a2_piper_full_stage_a2_base/base_v9_A-20260710_212238) | `0/16`, all `stage_overtime` | `1.806586 / 1.473302 / 0.333284` | `~0.107%` |
| B | `0.25` | locked | [`base_v9_B-20260710_212247`](../logs_rl/a2_piper_full_stage_a2_base/base_v9_B-20260710_212247) | `0/16`, all `stage_overtime` | `1.608041 / 1.450195 / 0.157847` | `0%` |
| C | `0.174533` | unlocked | [`base_v9_C-20260710_212256`](../logs_rl/a2_piper_full_stage_a2_base/base_v9_C-20260710_212256) | `0/16`, all `stage_overtime` | `1.060336 / 0.906377 / 0.153958` | `~0.105%` |
| D | `0.25` | unlocked | [`base_v9_D-20260710_212303`](../logs_rl/a2_piper_full_stage_a2_base/base_v9_D-20260710_212303) | `0/16`, all `stage_overtime` | `0.122457 / 0.116454 / 0.006004` | `0%` |

Matched scalar/trace artifacts：

- [A scalar/trace](../logs_eval/base_v9_A_ckpt1000_matched_scalar_trace_16env_20260711)
- [B scalar/trace](../logs_eval/base_v9_B_ckpt1000_matched_scalar_trace_16env_20260711)
- [C scalar/trace](../logs_eval/base_v9_C_ckpt1000_matched_scalar_trace_16env_20260711)
- [D scalar/trace](../logs_eval/base_v9_D_ckpt1000_matched_scalar_trace_16env_20260711)

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
| Matched-clean reacquisition | [`0/8 READY`, `8/8 RETREAT_JOINT_LIMIT`](../logs_eval/base_v9_B_matched_clean_preflight_8env_20260713/a2_hold_oracle_summary.json)；release action counts `[1,0,64,58,0,0,0,1]` | controller-local safety abort；六个 env 为 j6 upper，env2/3 在 64/58 actions 后为 j5 lower | 不证明 physical reachability failure，不证明 grasp target/offset 错误，不支持继续 O-/O0/O+ |

Static clamp artifacts：

- [S0 Kp/Kd 80/3](../logs_eval/base_v9_B_static_clamp_S0_kp80_kd3_8env_20260712/a2_hold_oracle_summary.json)
- [S1 Kp/Kd 160/6](../logs_eval/base_v9_B_static_clamp_S1_kp160_kd6_8env_20260712/a2_hold_oracle_summary.json)
- [S2 Kp/Kd 320/12](../logs_eval/base_v9_B_static_clamp_S2_kp320_kd12_8env_20260712/a2_hold_oracle_summary.json)

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

下一步另起 `base_v10` RL optimization/retraining plan：先明确 learnable behavior、最小 A/B factors、success/guardrail metrics 与训练预算，再取得用户 approval。该设计不属于本次归档范围。

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
  ++eval_output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_eval/<MATCHED_SCALAR_NAME>
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
  ++eval_output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_eval/<MATCHED_RENDER_NAME> \
  ++env.config.save_rendering_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_eval/<MATCHED_RENDER_NAME>/renderings
```

Render 经验：

- Scalar/trace 是 primary evidence；render 只解释 contact position、detach、jam、doorframe event 与动作自然性。
- v9 B 生成了 48 个预期 episode0 artifacts；A 除 48 个有效 episode0 artifacts 外还多出 3 个 env0 episode1 terminal-only artifacts，所以 A strict total-count FAIL。
- 不用目录名或视频名独立判断 provenance；至少核对 mtime、saved Hydra config、checkpoint path、seed 和 env id。
- `++` 是对 eval saved config 的显式 Hydra override；不要把训练命令的 `+ablation` 语法直接照搬到 checkpoint eval。

## 11. Evidence Map

- v8→v9 historical design/formal report：[`base_v8_to_v9_hold_handle_diagnostic_20260710.md`](base_v8_to_v9_hold_handle_diagnostic_20260710.md)
- v9 B training overrides：[`overrides.yaml`](../logs_rl/a2_piper_full_stage_a2_base/base_v9_B-20260710_212247/.hydra/.hydra/overrides.yaml)
- v9 B matched scalar overrides：[`overrides.yaml`](../logs_eval/base_v9_B_ckpt1000_matched_scalar_trace_16env_20260711/hydra/.hydra/overrides.yaml)
- v9 B matched render overrides：[`overrides.yaml`](../logs_eval/base_v9_B_ckpt1000_matched_render16_20260711/hydra/.hydra/overrides.yaml)
- matched-clean requested overrides：[`overrides.yaml`](../logs_eval/base_v9_B_matched_clean_preflight_8env_20260713/hydra/.hydra/overrides.yaml)
- matched-clean resolved config：[`runtime_config.yaml`](../logs_eval/base_v9_B_matched_clean_preflight_8env_20260713/hydra/.hydra/runtime_config.yaml)
- matched-clean result：[`a2_hold_oracle_summary.json`](../logs_eval/base_v9_B_matched_clean_preflight_8env_20260713/a2_hold_oracle_summary.json)
- matched-clean runtime identity：[`a2_hold_diagnostic_runtime_metadata.json`](../logs_eval/base_v9_B_matched_clean_preflight_8env_20260713/a2_hold_diagnostic_runtime_metadata.json)

Raw traces 与长日志继续保留在原 run directory；本报告只保存可复用结论、口径与入口。
