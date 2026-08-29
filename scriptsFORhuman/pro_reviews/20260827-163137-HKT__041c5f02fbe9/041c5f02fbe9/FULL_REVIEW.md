# Pull-v6 Cloud Pro 全量独立审阅

- 审阅日期：2026-08-27
- 仓库：`https://github.com/Jam-Stark/DoorDog`
- 分支：`codex/a2-piper-pull-v0-20260803`
- Source lock：`041c5f02fbe953604e5acfd971242d2cfa5d7851`
- Worker 目录：`Pro_Space/DoorDog/A2_Piper/pull-v6/20260827-163137-HKT__041c5f02fbe9`
- 审阅类型：Pull-v6 阶段验收、失败机理诊断与下一行为优化优先级
- 约束：heading 保持自由；首轮仍限 90 kg F0 轻门；不引入 release 后 regrasp/brace；本审阅未运行 IsaacLab/GPU，不把云端建议升级为本地生产硬门槛。

---

## 1. Insights 与 findings

### Finding 1 — Pull-v6 已经越过“物理上是否可能”的门槛，但只越过了 behavior-creation 门槛

**直接证据：**

- `r6an seed3 step25` 在 `r6ap` 的纯 natural、bank disabled、无 forced-gripper、无 P2 intervention 的 16-env eval 中，env14 完成了 E5 → clean release → frame passage → E6 → E7 → `complete`。
- 同 checkpoint/config/seed/env14 的五相机 render 再现 `reason-complete`；视频不是另一个统计样本，但证明事件链与可视行为一致。
- 该 episode 在 release 时有正 hinge velocity，且 `arm_tangent_share≈0.797`，不是“只靠 base 后退把门拉大”。
- 其余 15 个环境均未完成；训练 25 个 iteration 的日志中 `average_goal_reached=0` 始终为零。

**结论：**

- **F0 物理可达性：PASS。**
- **F0 learned behavior creation：PASS，但证据强度为 single-scenario existence proof。**
- **稳定 skill、population robustness、F1 family 泛化：INCONCLUSIVE。**
- 该结论不应被改写成“已经学会送门过身”或“轻门策略已稳定”。

### Finding 2 — 最严重的问题不是再缺一个 reward，而是“成功轨迹在当前 objective 中比失败轨迹更差”

env14 完整成功的 episode return 为约 **−636.65**；九个 Stage4 overtime episode 的 return 全部为正，范围约 **+10.69 到 +136.82**。成功轨迹的主要负项是：

| reward component | env14 episode sum |
|---|---:|
| `penalty_upper_body_non_gripper_deviation_l1` | −463.54 |
| `penalty_door_frame_contact` | −453.49 |
| `penalty_door_panel_contact` | −5.59 |
| `complete` | +4.08 |
| `a2_pull_v6_post_release_lateral_command_alignment` | +49.79 |
| `a2_corridor_clean_passage` | +20.46 |
| `a2_pull_frame_approach` | +21.29 |

这不是说 collision-heavy success 应无条件胜过安全失败；它说明当前 objective 没有给 PPO 一个可辨识的“安全且高效 E7”排序路径。若直接继续训练，稀有 E7 很可能因低 return 被压制或遗忘。**单纯再加大 arm-reset penalty 或 collision penalty 都不是首选**：两者已经很强，而且训练分布几乎没有覆盖长 Stage5。

### Finding 3 — 训练与最终 eval 存在决定性的 occupancy/horizon mismatch

训练 resolved config：

- `staged_reset_ratios=[0.01,0,0,0,0.99,0]`；
- 99% 从 Stage4 pre-release bank 开始；
- Stage5 reset 占比为 0；
- `max_stage_time[..., Stage5]=300`，`max_episode_length_s=24`。

最终 `r6ap` eval：

- pure natural reset；
- Stage5 budget 扩为 800；
- global episode 36 s。

env14 从 Stage5 开始（step740）到 E7（step1308）用了约 **568 control steps**；因此这条完整 through 路径在训练的 300-step Stage5 budget 下不可能获得 E7 credit。`r6ap` 的延时窗口揭示了 latent behavior，但没有证明 PPO 已经在该 horizon 上学会了完成任务。

**下一轮优先修复的是 late-stage occupancy 与 reward ranking，而不是继续堆 penalty。**

### Finding 4 — “arm 回 reset”与“减少 through collision”有因果联系，但不是同一个问题

render 和 trace 同时表明：

- release 后 arm 没有回到紧凑的 Stage0/resting pose；后段 arm 仍高举、跨越较大工作空间，若干关节 target 进入或超过 soft-limit margin。
- release 后早期确有 arm-panel / arm-frame contact。
- 但 E6 后的主要 jam 是 trunk、后腿/大腿与 frame 的碰撞和侧向挤压；trace 中 base path 约 7.05 m、reversal 30 次，E6→E7 约 569 steps。
- raw per-body contact trace 中，post-release frame contact 的绝大多数 step 与累计量来自 trunk/legs，而不是 arm。绝对 force 数值含接触传感器峰值，不能当作硬件力估计；相对 body attribution 与视频是一致的。

所以：

- arm reset 是 **collision envelope 的一个中介变量**；
- through collision 的主因还包括 base lateral/yaw path、body geometry、door reclosure、frozen locomotion response；
- 若只能选一个 behavior-quality 优先项，应先优化 **whole-body through corridor / base path**，同时把 arm reset 作为受约束的子目标；
- 若目标是提升 1/16 的总体成功率，则更上游的 clean-release creation 仍比二者更紧迫。

### Finding 5 — 当前 135-D D-only actor 已经有足够 state，首轮不需要扩 observation

resolved actor observation 已包含：

- `delta_actions`；
- arm/base state；
- action history；
- door state history；
- `z_a2_pull_v6_release_mode`。

`PullV6PostReleaseObsOverrideActor` 还在 released mode 下直接覆盖 base x/y/yaw 与六个 arm action mean。checkpoint 中该 `post_release_obs_override` 权重非零。当前失败更像：

1. late-stage state occupancy 不足；
2. reward ranking/scale 不适配；
3. 9-D D-head 把 base path 与 arm reset 混在同一个 update 中，缺少可辨识 credit；
4. incremental/delta action 累积导致 arm target 漂移。

因此首轮建议只加 telemetry/critic target，不先改变 actor observation shape。

---

## 2. Source 与 evidence ledger

### 2.1 已直接审阅

1. 指定 Git commit `041c5f02...` 的 commit diff 与关键文件：
   - `memory/a2-piper/pull-open-door-task/description.md`
   - `gr00t/rl/config/ablation/wbmanip/pull_v6_F0_r6an.yaml`
   - `gr00t/rl/config/ablation/wbmanip/pull_v6_F0_r6ap.yaml`
   - `gr00t/rl/trl/modules/pull_v6_post_release_obs_override_actor.py`
   - `gr00t/rl/envs/door/door_open_a2_pull.py`
   - `gr00t/rl/trl/trainer/ppo_trainer_a2_base_api.py`
2. Worker 四个 ZIP；包大小与 Owner 提供值一致。
3. 关键机器可读 artifacts：
   - `metrics_eval.json`
   - `a2_v14_per_env_records.json`
   - `a2_eval_diagnostic_metadata.json`
   - `stage2_5_step_trace.json`
   - eval/train resolved Hydra configs
   - train/eval runner logs
   - `model_step_000025.pt`
4. 五个 env14 render MP4，逐时间点抽帧对照 trace。

### 2.2 Worker ZIP SHA-256

| ZIP | bytes | SHA-256 |
|---|---:|---|
| `worker_delivery__logs_and_metrics.zip` | 51,587 | `667fbd1bcbb60b348cb732d19ff4ed78916c613a64df76be6f7d7a1619efd9ae` |
| `worker_delivery__source_and_configs.zip` | 49,567,372 | `a66a0aa4de84a7cb43e019af2164521ab785c42acd7f318066b2078b188ddb6f` |
| `worker_delivery__plots_and_evidence.zip` | 22,216,942 | `92325338e6e1b12b6e9598d4ef55c96d736ca3044ce9dd67c9cbfcf75e16a91f` |
| `worker_delivery__checkpoints.zip` | 18,225,021 | `3e6606c4c337899b64c498295219271a3d27e3366eb7aeb193959678b616d115` |

### 2.3 关键解包文件 SHA-256

| file | SHA-256 |
|---|---|
| `stage2_5_step_trace.json` | `6d26be790e29a862b38b214b7c09d929c14970eb8fb148e6fd95e1c5eb00c185` |
| `metrics_eval.json` | `64a109b0aebf135913aefc2add6b3c9b89ddeefc40b603832b20ecf79ba8abdc` |
| `a2_v14_per_env_records.json` | `3c197396ec3c240a3b4b22936194cb44b037d17f83eb96b6931f15e109fde880` |
| `model_step_000025.pt` | `2640ec013fa6b9918928b087d33fce59b9eec25d7991cf47f23fbaee7601d30b` |

### 2.4 未知项 / 只能由本地 AI 验证

- 当前本地 HEAD、未提交 diff、生产 config override；
- `.ai/PROJECT.md` 中当前有效命令；
- IsaacLab/Isaac Sim 版本与当前 GPU/process 状态；
- pre-release / clean-release state bank 是否仍在本地；
- state replay 的确定性与 clone API；
- 硬件上的 frame/panel contact、安全限值、PiPER cable/fixture envelope；
- 真实门的 closer、摩擦与重闭合；
- 是否允许新的 Stage5 snapshot capture；
- 本地可接受的训练预算和 seed 数。

这些均不得由本报告替本地生产环境作事实判断。

---

## 3. 阶段验收结果

| 项目 | Cloud Pro verdict | 依据与边界 |
|---|---|---|
| Source/provenance | PASS | commit/source lock 清楚；Worker 包可解析；eval metadata 可审计 |
| Eval 是否 pure natural | PASS | ratios `[1,0,0,0,0,0]`、bank disabled、forced close=0、P2 intervention disabled |
| F0 物理可达性 | PASS | env14 完成 clean release、frame passage、E6/E7 |
| “送门过身”行为创建 | PASS（单例） | 正 hinge velocity release、arm tangent attribution、cross without holding |
| learned closed-loop existence | WEAK PASS | 不是 eval oracle；D-only learned head 生效；但仅一个 scenario |
| population robustness | INCONCLUSIVE | 1/16；同 render 非独立；训练 goal 全零 |
| natural integration | FAIL/未收敛 | 6/16 终止于 Stage0，9/16 终止于 Stage4 |
| safe/efficient traversal | FAIL/未形成 | collision-heavy、7.05 m、30 reversals、长 E6→E7 |
| F1 / 重门 / strong closer | NOT EVALUATED | 当前证据只覆盖 90 kg F0、4 N·m closer、`add_walls=false` |
| release 后 regrasp/brace | OUT OF SCOPE | Owner 明确排除 |

**推荐的阶段处置：**

- 将 Pull-v6 标记为 **`F0_BEHAVIOR_CREATION_PASS__ROBUSTNESS_INCONCLUSIVE`**。
- 允许进入一个 bounded F0 post-release causal round。
- 不把它升级为稳定 policy 或 F1 family acceptance。
- 这是一项审阅建议，不是本地 release blocker。

---

## 4. “送门过身”合理/可学习结论的证据边界

### 4.1 可以说什么

在指定 F0 轻门、当前几何、无 wall hardening、heading 自由、无 regrasp/brace 条件下：

1. arm-dominant tangent transport + positive-momentum release + immediate through 在物理上可行；
2. 当前 actor/action contract 能表达该行为；
3. 一个非 scripted、pure-natural eval episode 产生了完整事件链；
4. release 不需要硬锁 heading；成功 episode 的 yaw 是自由变化的；
5. release 后无需继续握持也可以通过。

### 4.2 不能说什么

当前证据不能支持：

- “策略稳定学会送门过身”；
- “多 seed 可学习”；
- “90 kg 轻门 family 已泛化”；
- “arm 回 Stage0 pose 会必然减少 collision”；
- “through collision 的主因就是 arm 没收回”；
- “将 Stage5 时间扩到 800 就解决了问题”；
- “该行为可直接迁移到重门、强 closer、walls 或实机”。

### 4.3 为什么 render 不是第二个独立成功样本

五相机 render 使用同 checkpoint、同 config、同 seed、同 env14 identity，只是多视角重放。它提升了行为解释力，不提升统计独立性。视频 1360 帧以 20 fps 写出，时长约 68 s；control trace 的 `dt=0.02 s`，物理 episode 约 27.16 s。因此应以 control step 和 trace time 作为科学时间，MP4 时间只用于视觉定位。

---

## 5. 失败漏斗与 winner 时间线

### 5.1 16-env natural eval 漏斗

| 终局 | 数量 |
|---|---:|
| Stage0 overtime | 6 |
| Stage4 overtime | 9 |
| Stage5 complete/E7 | 1 |

在 10 个到达 Stage4 的环境中：

- 5 个进入 Phase D / 记录 `release_event`；
- 4 个被 terminal telemetry 记为 deliberate release；
- 只有 env14 是 clean release；
- 其余 release event 均发生在负 hinge velocity、passage not ready、pivot displacement 过大的状态。

所以总体成功率的主导阻断仍包括：

1. Stage0 natural integration；
2. Phase C clean-release creation；
3. post-release through quality。

只优化 env14 的 arm reset 不会自动修复前两项。

### 5.2 env14 关键事件

| event | control step |
|---|---:|
| E5 clearance decision | 319 |
| release-ready / Phase C | 357 附近 |
| clean release / Phase D | 358 附近 |
| K25 persistence | 384 |
| frame passage | 620 |
| E6 / planar crossing | 739 |
| Stage5 begins | 740 |
| E7 whole-body clear | 1308 |
| terminal complete | 1358 |

说明：

- project memory 与 step trace 在 release/clean-release 上有 1-step 差；metadata 明确 trace 中 policy、physics、stage-advance 的时序不同。这是 indexing 语义，不是行为冲突。
- release→E7 由 trace 计算约 950 steps / 19.0 s；
- terminal 字段 `release_to_whole_body_clear_s=19.78` 实际等于 E5→E7 的 989 steps，字段名可能沿用 “release-or-hold decision” 语义；本地应修正文档或 telemetry 名称，避免误读。
- E6→E7 仍用了约 569 steps / 11.38 s，是 through quality 的主要长尾。

---

## 6. Arm reset 与 through collision 的详细因果分析

### 6.1 当前 arm 确实没有回到紧凑 pose

直接迹象：

- render 在 frame passage 后仍显示 arm 高举/伸展，而非初始 folded/resting envelope；
- trace 中 arm target 从 release pose持续漂移；后段有 target 到约 4 rad，若干 soft-limit normalized margin 为负；
- env14 `a2_pull_v6_post_release_arm_default_target_quality` episode sum 为负；
- `penalty_upper_body_non_gripper_deviation_l1` 达 −463.54；
- checkpoint 已含非零 `post_release_obs_override`，说明不是“没有 D-head”，而是 learned D-head 没有得到合适 occupancy/credit。

### 6.2 contact 时序表明 arm 是早期因素，base/body 是后期主因

以 deliberate release step358 为界，trace 的非零 contact step 统计：

| surface | arm steps | trunk/legs steps | 解释 |
|---|---:|---:|---|
| panel | 9 | 8 | release 后早期 arm 与 panel、随后 trunk 与 panel |
| frame | 60 | 139 | arm 接触集中在 frame passage→E6；大多数后期 jam 来自 trunk/legs |

分段：

- release→frame passage：arm-panel contact，随后 trunk-panel contact；
- frame passage→E6：arm_body7/8 与 frame、少量前腿 contact；
- E6→E7：trunk、后腿/大腿与 frame 的长 contact/jam，占主导。

绝对 frame force 峰值非常大，可能包含 PhysX contact sensor/filter 峰值，不应用作硬件力或安全阈值；但 body-category attribution、contact step 与 render 对得上。

### 6.3 因果图

```text
clean release state quality
  ├─ hinge momentum / reclosure
  ├─ root pose / lateral deficit / heading
  ├─ arm configuration / swept envelope
  └─ locomotion-controller state
          ↓
post-release base+arm action
  ├─ arm reset/tuck ───────────────┐
  ├─ base corridor path ───────────┼─> arm/body/frame contact
  └─ yaw/translation coordination ─┘             ↓
                                      path reversal / delay / E7
```

因此：

- `arm reset → collision reduction` 是可检验的局部路径；
- `collision reduction → E7 improvement` 还受 base path 与 door reclosure调节；
- 当前单 episode 不能从 correlation 推出 arm reset 是主因。

---

## 7. 优先级判断

### 7.1 总体优先级

1. **P0：late-stage curriculum/horizon 与 return-ranking 修复。**
2. **P1：在 matched clean-release state 上分离 arm-only 与 base-only causal effect。**
3. **P2：若 base path 是主因，优化 frame-relative corridor progress；arm reset 作为 bounded co-objective。**
4. **P3：若 arm-only intervention 显著减少 arm contact并提高 E7，再训练 geometry-aware tuck/reset。**
5. **P4：最后才做 multi-seed natural robustness；F1 暂缓。**

### 7.2 若 Owner 要求在“arm reset”与“through collision”之间二选一

选择 **through collision / whole-body corridor efficiency** 作为首要 behavior-quality 目标，理由：

- winner 后半段主要 collision 来自 trunk/legs；
- E6→E7 长尾最大；
- base path 7.05 m、30 reversals；
- arm reset reward/penalty已经存在且很强；
- 当前缺的是能让 policy 学到“如何安全穿过”的 occupancy 与 positive alternative。

但 arm reset 应保留为同一 post-release envelope 目标的子项，而不是删除。

### 7.3 对成功率提升的额外提醒

在 16-env 漏斗中，15 个失败都发生在 arm-reset 能生效之前或 clean release 之前。因此，若本轮 KPI 是总体 success rate，而不是 winner 行为质量，则 clean-release creation 比 arm reset/collision 更优先。建议 Owner 明确下一轮 KPI：

- `quality-of-the-winner`；
- 或 `population success creation`。

二者不应混在同一个小实验里。

---

## 8. 最小因果判别实验：同状态 2×2

### 8.1 设计

从同一个 verified clean-release state 开始，保持 door physics、random seed、carrier checkpoint、gripper-open contract 一致，运行：

| Cell | Base D-action | Arm D-action | 目的 |
|---|---|---|---|
| A baseline | learned | learned | 当前策略 |
| B arm-only reset | learned | rate-limited toward Stage0/default | 测 arm reset 的边际效果 |
| C base-only corridor | frame-relative intervention/现有 lateral CF | learned | 测 base/path 的边际效果 |
| D both | same as C | same as B | 测交互项 |

实施边界：

- heading 不设 absolute target；
- gripper保持 open，不 regrasp、不 brace；
- arm reset 不要一步硬跳到零；采用 bounded velocity/target decay；
- base-only 首轮可以复用 commit 中已有 `a2_pull_v6_passage_lateral_counterfactual`，但训练版应改为 door-frame coordinates，避免 world-Y 只适配单场景；
- 若本地没有 release snapshot，可 deterministic replay seed3/env14 到 release 并 clone；若 replay 不确定，则每 cell 运行 paired repeats。

### 8.2 必须记录

- `frame_passage`、E6、E7；
- release→E6、E6→E7、release→E7；
- base path length、reversal count；
- arm/body × panel/frame contact steps与 bounded impulse；
- min swept clearance；
- arm `delta_actions` L1、actual joint margin、target overshoot；
- hinge angle/velocity/reclosure；
- fall、undesired contact、base stability；
- pre-release invariants，确认干预只发生在 clean release 后。

### 8.3 判读

- **B 显著降低 arm contact，但 body jam、path、E7不变**：arm reset 是安全/美观次目标，不是主瓶颈。
- **C 显著降低 body-frame contact并缩短 E6→E7**：base corridor 是主因。
- **D 明显优于 C**：arm reset 与 base path存在正 synergy，适合联合训练。
- **B 反而增碰撞/失稳**：Stage0 exact pose 不是安全 tuck；改用 clearance-aware safe set。
- **四格均无改善**：回查 Stage5 state distribution、frozen locomotion interface、door reclosure，不扩 reward budget。

这是本轮最高信息增益实验；在它之前直接重训多个 reward weight，因果信息较低。

---

## 9. 最小 reward / state / curriculum 改动

### 9.1 State：首轮不扩 actor observation

保留 135-D contract。只新增或显式落盘：

- `arm_delta_l1` / `arm_default_quality_current`；
- `time_since_clean_release`；
- arm/body 分组的 panel/frame contact；
- frame-relative corridor progress / lateral deficit；
- arm envelope clearance；
- D-head base/arm output分别统计。

若 2×2 证明当前 obs 无法做闭环 reset，才考虑把 `arm_joint_pos_target` 或 compactness margin 显式加入 current observation；现有 `delta_actions` 已经很接近所需 state。

### 9.2 Arm reward：不要再简单加大 L1 penalty

当前已经有：

- generic upper-body-rest penalty；
- `post_release_arm_tuck_progress`；
- persistent `arm_default_target_quality`。

建议最小重构为：

```text
r_arm_clear =
    potential_improvement(compact_arm_or_safe_tuck)
    gated by clean_release
    active until arm-frame/panel envelope is clear
```

要求：

- 用 potential difference 或 one-shot bonus，避免每帧 annuity；
- target 优先是 `safe compact set`，Stage0 pose只作 anchor；
- 到达 safe envelope 后停止支付；
- 对 incremental target 漂移加 bounded target/soft-limit penalty；
- 不影响 pre-release Stage4B/4C。

### 9.3 Through reward：给“可行替代路径”，不是更大 collision penalty

建议：

```text
r_pass =
    Δ signed whole-body-clear progress
  + Δ frame-relative lateral clearance
  + one-shot E6 / E7
  - bounded new-contact event cost
  - bounded reversal / backtracking cost
```

注意：

- 现有 raw force penalty可能高方差；建议对 force/impulse做 clipping或 event-bounded aggregation，但保留 safety semantics。
- 不要把 collision penalty在 frame passage 后直接 mask掉。
- E6/E7 bonus需按 return audit 校准：**collision-free efficient E7 应明确优于 Stage4 timeout**。
- 不应为了让 env14 负回报转正而无条件放大奖励；env14 的高碰撞仍应被判为低质量成功。

### 9.4 Curriculum：这是最小且最高优先级的实际改动

当前 99% Stage4 bank、0% Stage5 reset、300-step Stage5，不足以训练 env14 的 568-step Stage5 path。

建议建立两个 late-state anchors：

1. clean-release / Phase D start；
2. frame-passage 或 E6 start。

短轮 D-only specialist：

- frozen carrier；
- materially nonzero Stage5/through snapshot occupancy；
- 保留 nonzero natural 与 Stage4 occupancy防止只会 bank；
- 初期不用把 Stage5 budget直接拉到800；从 frame/E6 snapshot训练可在较短 horizon获得 E7 credit；
- 得到快且低碰撞的 through 后，再做 full-natural integration。

精确 ratio 由本地 snapshot availability 与资源决定；Cloud 不给硬比例。原则是：**Stage5 不能再是 0%，natural 不能长期只有 1%。**

---

## 10. 实验停止条件

以下是 bounded experiment stop，不是生产硬门槛。

### 10.1 2×2 discriminator

停止 arm-reset 路线扩展，当：

- B 相对 A 只改善 arm L1/姿态，却不改善 arm contact、whole-body contact、E6/E7或时间；
- B 导致 base instability、joint-limit、frame contact或 passage下降；
- B 的效果在 paired repeats 中方向不稳定。

停止 base-collision 路线扩展，当：

- C 只降低 raw contact penalty，但不缩短路径、不减少 reversal、不提高 E7；
- C 破坏 clean release / hinge momentum；
- C 依赖 world-Y 单场景符号，换场景即翻转。

### 10.2 D-only training

立即停并回查 objective，当：

- success return仍系统性低于 Stage4 timeout，且差异由正常时长 penalty而非真正危险行为主导；
- 三个连续 checkpoint只在 bank成功，pure-natural无任何 E6/E7增加；
- pre-release E5、clean release、arm-tangent attribution回退；
- D-head output产生 target drift / soft-limit持续恶化；
- frame contact下降但 fall/undesired contact上升。

### 10.3 stronger claim 的证据要求

在声称“可学习/稳定”前，至少应有：

- 不同训练 seed或独立 D-head lineage；
- 不止同一 env14 scenario；
- natural reset；
- behavior-quality metrics，不只 E7 count；
- render/trace 交叉验证。

具体 seed 数、成功率阈值由本地 AI和 Owner决定。Cloud 不把“2 seed”“x/16”等自动升级为硬 gate。

---

## 11. QA / fact-check

### 11.1 PASS

- 指定 commit存在，commit message与 Pull-v6 实现一致。
- `r6ap` 只扩 Stage5/global time，不改 actor/reward/physics。
- eval metadata显示 forced gripper close count全零，P2 intervention disabled。
- action layout为 12-D：base 0:5、arm 5:11、gripper 11。
- render文件均为 env14、episode0、reason-complete、1360帧。
- checkpoint含非零 `post_release_obs_override`，不是零初始化未训练状态。
- 事件顺序与视频相符：release → frame passage → crossing → whole-body clear。

### 11.2 需要本地修正或澄清

1. `release_to_whole_body_clear_s` 的名称与计算起点疑似使用 E5 decision，而非 deliberate release。
2. `source_and_configs.zip` 主要包含 resolved config与机器可读证据，不应被误当成完整 Git source；代码事实仍以 source lock commit为准。
3. raw frame contact峰值很大，需确认 contact filter/aggregation语义；不可直接映射实机力。
4. final hinge从 release约1.248 rad降到终局约0.351 rad；`hinge_reclosure_after_release`却为 `N/A`，建议修复 telemetry。
5. success episode的 return排序异常，应加离线 reward-rank audit。
6. 训练 seed3是从共同的 r6am seed0 carrier warm-start，不应被表述为完整独立 seed lineage。

---

## 12. One more thing：research novelty 可能

### 12.1 最有潜力的算法点不是“arm 回 Stage0 pose”

本轮已经形成一个非常清晰的研究问题：

> 在相同 clean-release handoff state 上，arm reset 与 base corridor action 对 downstream safe passage 的边际贡献和交互贡献是什么？

可将 2×2 intervention 扩展成：

```text
Δ_arm  = R(learned base, reset arm) - R(learned base, learned arm)
Δ_base = R(corridor base, learned arm) - R(learned base, learned arm)
Δ_int  = R(corridor base, reset arm)
       - R(corridor base, learned arm)
       - R(learned base, reset arm)
       + R(learned base, learned arm)
```

然后训练一个 **handoff-conditioned coupling critic**：

- 输入 release state、base action、arm action；
- 输出 E7 probability、time-to-clear、collision risk；
- 给 base/arm branch分配不同 advantage；
- 只在 Stage4C→Stage5 handoff附近使用。

这比“再加一个 centralized critic”更有辨识度，也直接对应当前 failure。

### 12.2 数据创新

当前 project 已具备少见的同步证据：

- event-aligned stage trace；
- arm/base action decomposition；
- per-body panel/frame contact；
- hinge/release state；
- multi-camera render；
- exact source/checkpoint/config provenance。

若用 matched state clones生成 arm-only/base-only/both反事实，能形成一个 **post-release handoff counterfactual dataset**。其价值在于学习“哪一种 release terminal state为下游 through留下了好起点”，而不是只学习当前 stage是否完成。

### 12.3 工程创新

可以将当前 evaluator扩为：

- action-branch intervention registry；
- paired-state replay；
- automatic causal attribution report；
- reward-rank audit；
- render/trace time alignment。

这类 infrastructure本身未必是算法 novelty，但能显著提高长程 contact-rich RL 的可证伪性与审阅质量。

### 12.4 不应夸大的部分

- Stage0 arm reset不是新算法；
- collision penalty不是 novelty；
- staged reset已有明确先例；
- centralized critic / multi-head critic已有广泛工作；
- 当前只有一个 F0 winner，不能据此声称 counterfactual critic有效。

更稳妥的 research claim候选是：

> **Counterfactual Handoff Credit for Safe Post-Release Traversal in Hierarchical Legged Loco-Manipulation**

其成立前提是完成 matched interventions、multi-seed natural integration和消融。

---

## 13. 给本地 AI 的最小下一步建议

1. 保留当前 source/head，不先改 observation。
2. 用 env14 clean-release state做 A/B/C/D matched discriminator。
3. 增加 arm/base contact attribution与 arm-delta telemetry。
4. 建一个 frame-passage/E6 Stage5 bank，训练同一 D-only head。
5. 先审计 return ranking，再决定是否改 reward scale。
6. 保持 heading自由、轻门F0、无 regrasp/brace。
7. 结果按 `FACT / INFERENCE / UNKNOWN / LOCAL_ONLY` 回写，不把本报告阈值当硬门槛。

---

## 14. 最终 verdict

**Pull-v6 已获得真实的 F0 “送门过身” behavior-creation proof，但当前 policy 不是稳定 skill。**

最重要的下一步不是“arm reset reward vs collision penalty”二选一，而是：

1. 先用 matched intervention确定 arm reset对 collision与E7的因果贡献；
2. 同时修复 Stage5 occupancy/horizon；
3. 让 safe efficient E7在 reward ranking中可学习；
4. 将 through corridor作为主目标，arm reset作为安全 envelope子目标；
5. 在此之后再做 multi-seed natural robustness。

这条路线满足 Owner 当前边界：heading自由、首轮轻门、不引入 release 后 regrasp/brace。


---

## 15. Research/context references used for comparison

- `Xue 等 - 2025 - Opening the Sim-to-Real Door for Humanoid Pixel-to-Action Policy Transfer.pdf`
  - staged-reset reweights late-stage occupancy；
  - teacher task separates Swing / Pass-through；
  - resting-pose、door-frame/panel contact均已存在于其 reward设计。
- `Pan 等 - 2025 - RoboDuet Learning a Cooperative Policy for Whole-body Legged Loco-Manipulation.pdf`
  - arm/default pose与base协调可改善whole-body workspace/stability，但不是本轮 arm-reset 因果结论。
- `Counterfactual Coupling and Handoff Critics for Long-Horizon Legged_Loco-Manipulation.md`
  - 作为项目内部研究假设参考；本轮 2×2 matched intervention 是对其 handoff/coupling 思路的最小可证伪实现。

这些文献只用于机制对照，不替代指定 commit 与 Worker artifact 的事实地位。
