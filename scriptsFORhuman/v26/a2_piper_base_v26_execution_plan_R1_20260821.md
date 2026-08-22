# DoorDog A2+PiPER `base_v26` Execution Plan R1

## Scratch-Born Bilateral Teacher Acquisition, Fresh Staged Reset, Far-Start Navigation, and Force-Aware Consolidation

**日期：** 2026-08-21  
**状态：** `DRAFT_FOR_OWNER_REVIEW`  
**基础分支：** `A2_Piper`  
**起始仓库状态：** v25 已提交并归档；worker 开工时重新记录实际 HEAD。  
**资源假设：** physical GPU0–3，4×A6000 48 GB；每卡可运行一个 `4096 env` 训练进程。  
**最终产品目标：** 从随机初始化训练一个从出生起就覆盖 LEFT/RIGHT 推门的完整 Stage0→5 privileged Teacher，并形成可交给后续双侧视觉 Student 的 checkpoint。  
**第一科学问题：** v25 的双侧失败主要来自 right-only warm-start 负迁移，还是 LEFT task/init/reward/shared-policy 本身仍有缺陷？  
**第二科学问题：** 在保留 v25 已证实的 planar 主作用与 posture 接触价值后，怎样组织 randomization 才不会在完整技能形成前稀释学习信号？

> 本方案面向本地 Worker AI session 执行。由于云端无法读取生产机上的 IsaacLab/IsaacSim 安装源码、实时日志与 checkpoint 内容，本文的数值是执行起点和量级建议，而不是不可修改的远程硬门。Worker 应先读 memory、再读本地 source、证明真实运行路径，并可在 formal optimizer update 前根据本地 runtime 做一次有记录的简化或数值调整。

---

# 0. 质朴版

v26 不加载 G7，也不继承 v25 policy。

高层开门 Teacher 的 actor、critic、LSTM、动作方差、观察归一化、optimizer 和 staged-reset buffer 全部重新建立；已经训练好的 A2_Base 四足低层 locomotion policy 继续冻结使用。

从第一个 batch 开始：

```text
LEFT door = 50%
RIGHT door = 50%
FULL posture
base planar motion可用
普通/低负载门
reward curriculum关闭
fresh staged reset
```

先让 policy 学会完整的：

```text
走到门前
→ 对准把手
→ 稳定夹住
→ 压把手并打开门
→ 带门/放门并进入门洞
→ 穿过门
```

等双侧完整行为出现后，再逐层加入：

```text
更宽的门几何
更远/更偏的初始位置
P02/P05为主的摩擦负载
少量P10
更严格的clearance/release/body-contact行为优化
```

不在第一天同时加入 P10、RP0、reward curriculum、carry/fling、强 corridor 规则和所有实机压力项。

---

# 1. v25 对 v26 的直接约束

v25 已经说明：

1. LEFT/RIGHT asset mirror 与主要 handle-relative task routing可以运行；
2. G7 对 RIGHT 是成熟策略，对 LEFT 是明显 OOD；
3. G7 warm-start 后训练 1500 batches，能够学出部分 LEFT reach/grasp/opening，却不能形成干净、可重复的 LEFT completion；
4. chronic FULL 比 RP0 明显更容易形成 LEFT reach/grasp/contact；
5. stable-grasp 后，短时 hinge progress主要由 planar `vx/vy/yaw` 贡献；
6. posture 对短时 hinge progress不构成稳定正贡献，但能提高 LEFT contact retention。

因此 v26 必须：

```text
不从right-only policy warm-start
不做RP0 acquisition
不在stage3锁死planar base
不对posture收取额外command tax
不从P10开始
把初始位置/lateral/yaw作为核心randomization
把load randomization放在完整技能之后
```

v25 的因果结果继续作为 v26 randomization 与 reward routing 的设计依据，不重跑同样的 FULL/RP0 四格训练。

---

# 2. Scope

## 2.1 本轮必须完成

- 新建 clean scratch Teacher config，不继承 `base_v22/base_v23/base_v25` ablation config 树；
- LEFT/RIGHT 从 batch 0 进入训练；
- clean handedness observation；
- fresh staged-reset ecology；
- 更远的 natural-start robot pose；
- scratch acquisition reward registry；
- 四卡第一波诊断矩阵；
- side-stratified Route A / holdout / render；
- 成功后进行 moderate force-aware continuation；
- 给 Student worktree输出一个双侧 Teacher manifest与已知边界。

## 2.2 本轮明确不做

- 不重训 A2_Base low-level locomotion；
- 不加载 G7 actor、critic、LSTM、RMS 或 optimizer；
- 不做 pull/in-opening；
- 不做 RP0 formal；
- 不启用 reward-penalty curriculum；
- 不训练 coupling critic；
- 不做 GRPO；
- 不以 20 N·m friction 模拟真实防火门；
- 不因 v25 acute 结果而删除 roll/pitch；
- 不把 current right-only Student直接改成 mixed-LR Student；
- 不为了保留旧 v22–v25 config 构建新的 compatibility layer。

---

# 3. 开工前一次性 source/memory 回溯

Worker 开始实现前，按以下顺序读取：

```text
MEMORY.md
memory/a2-piper/MEMORY.md
memory/a2-piper/reward-implementation-goal/description.md
memory/a2-piper/push-open-door-optimization/description.md
memory/a2-piper/stage0-2-grasp-terminal/description.md
memory/a2-piper/base-v25-mirrored-teacher-force-causality/description.md

scriptsFORhuman/v25/a2_piper_base_v25_final_analysis_20260821.md

scriptsFORhuman/Reward/g1_doorman_stage0_reward_transition.md
scriptsFORhuman/Reward/g1_doorman_stage1_reward_adaptation.md
scriptsFORhuman/Reward/g1_doorman_stage2_reward_completion_a2_adaptation.md
scriptsFORhuman/Reward/g1_doorman_stage3_reward_completion_a2_adaptation.md
scriptsFORhuman/Reward/g1_doorman_stage4_reward_completion_a2_adaptation.md
scriptsFORhuman/Reward/g1_doorman_stage5_reward_completion_a2_adaptation.md

gr00t/rl/config/ablation/wbmanip/base_v12_A_v10A_scratch_control.yaml
gr00t/rl/config/ablation/wbmanip/base_v13_A_main.yaml
gr00t/rl/config/ablation/wbmanip/base_v13_1_main.yaml
gr00t/rl/config/rewards/wbmanip/reward_door_open_a2_base.yaml
gr00t/rl/config/rewards/wbmanip/reward_door_open_a2_v23.yaml
gr00t/rl/config/env/door_open_a2_base.yaml
gr00t/rl/config/robot/A2_Piper/a2_piper.yaml
gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py
gr00t/rl/envs/door/door_open_a2_base.py
gr00t/rl/envs/base_task/staged_task_base.py
```

只做一次 focused comparison：

```text
DoorMan base recipe
vs v12 scratch
vs v13_A/v13.1 first full-chain route
vs v23/v25 warm-era registry
```

产出一个人工可读表：

```text
scriptsFORhuman/v26/V26_REWARD_LINEAGE_REVIEW.md
```

不要反复全仓 review。完成该表并确定真实 runtime function binding 后，直接实现最小端到端路径。

---

# 4. Clean scratch contract

## 4.1 高层 Teacher 真正从头开始

formal config必须满足：

```yaml
checkpoint: null
auto_load_latest: false
checkpoint_load_mode: full
```

并确认新 run 中以下状态均为 fresh：

```text
actor weights
critic weights
actor/critic LSTM hidden parameters
action distribution std
actor/critic observation running statistics
optimizer
scheduler
trainer global step
environment curricula
staged-reset snapshots
previous action/history buffers
```

保留：

```text
frozen A2_Base TorchScript locomotion policy
A2+PiPER robot asset
current control-step grasp streak fix
current valid LEFT/RIGHT door asset implementation
current six-stage task state machine
```

## 4.2 不从旧 ablation config继承

建议新建：

```text
gr00t/rl/config/ablation/wbmanip/base_v26_common_scratch_lr.yaml
```

它直接继承当前通用 A2 door experiment/environment，而不是：

```text
base_v25 → base_v23 → base_v22 → ...
```

需要的历史能力值直接显式写进 v26 common config；不依赖旧 plan selector。

## 4.3 Handedness observation

当前 privileged observation 中 handedness需要整理为真正对称的两维编码，同时保持 observation dimension不变：

```text
LEFT  -> [1, 0]
RIGHT -> [0, 1]
```

不继续使用 sign 与 `1-sign` 的非对称组合。

Worker先确认当前 metadata sign：

```text
left/right raw string
doorOpenLR sign
handle physical side
```

再替换对应两个 observation slots。不要给 Student actor增加 privileged side label；本项只服务 state Teacher。

---

# 5. 初始化与更远的 Stage0

## 5.1 主要改变 natural-start，不先放宽 pregrasp gate

当前 Stage0 staging target已经是 handle-relative目标，约位于把手前方 0.70 m。v26 首先扩大 robot natural-start 到门的距离，不先把 Stage0→1 精确 staging gate改松。

建议的门坐标系起始范围：

```text
door-normal distance: 0.90–1.40 m
lateral offset:       -0.25–+0.25 m
relative yaw:         -0.30–+0.30 rad
root height:          保持A2 nominal，只用现有小噪声
```

这些是起始量级。Worker必须先在本地 GUI 中确认：

- 坐标符号；
- 机器人位于推门一侧；
- LEFT/RIGHT使用相同分布；
- 最远点仍可在stage timer内走到；
- 与其他env无碰撞/越界。

若实际 asset/world 坐标与上述不同，Worker用 door-relative实现等价分布，不强行套 world-X 数值。

## 5.2 Stage0 timer

起始建议：

```yaml
max_stage_time: [350, 100, 100, 100, 100, 200]
```

即给 Stage0 约 7 秒，而不是当前约 5 秒。若本地 control frequency或 episode cap不同，Worker按实际值调整，使最远 natural-start 在正常速度下有明确余量。

必要时同步把总 episode length提高到覆盖所有 stage timer总和；不要让 global episode timeout先于合法stage预算。

## 5.3 Stage0 staging range

第一轮保持已验证的 handle-relative staging中心 `0.70 m`。

仅当 GUI/短训练显示 LEFT/RIGHT某侧存在系统性reach-margin差异时，才在 formal前一次性加入：

```text
staging offset约 0.60–0.80 m
```

的窄随机化。不要同时大改 natural-start、staging target和pregrasp target，否则无法判断失败来源。

## 5.4 Arm initial pose

第一轮优先使用同一套、真实硬件合法的 common neutral arm pose，不按 side机械翻转 joint角。

Worker做一个窄的 left/right task-space preview：

- joint margin；
- self-collision；
- TCP 到 pregrasp 的最短合法路线；
- arm在walking时是否与门/腿碰撞。

只有 common pose对某一侧形成结构性不可达，才设计两个明确的 side-conditioned legal pose，并单独记录。不要用关节符号镜像近似 single-arm PiPER。

---

# 6. Fresh bilateral staged reset

## 6.1 生态从空 buffer出生

每个 formal run：

```text
fresh staged-reset buffer
fresh per-env sample counts
不导入G7/v25 snapshot
不导入其他cell snapshot
```

## 6.2 Env side固定

在每个 LR `4096 env` process中：

```text
2048 LEFT
2048 RIGHT
```

side按 seed与 env_id做一次确定性 permutation，并在该env整个run生命周期固定。

因此：

- LEFT snapshot只能回到同一 LEFT env；
- RIGHT snapshot只能回到同一 RIGHT env；
- reset不重新抽 door side；
- staged sample不跨env/side复制。

## 6.3 Reset比例

初始保持：

```yaml
staged_reset_ratios: [0.5, 0.1, 0.1, 0.1, 0.1, 0.1]
staged_reset_max_samples_per_stage: 200
```

理由：

- 50% natural-start确保更远的walk skill不会被late-stage reset淹没；
- 现有200-state容量已不低于DoorMan论文的100-state有效设置；
- 本轮问题是双侧共同出生，不是重新搜索buffer size。

每个训练日志分别记录 LEFT/RIGHT：

```text
natural-start episode count
stage occupancy
snapshot availability per stage
snapshot use count per stage
max stage reached
goal
```

不得只报告 aggregate。

## 6.4 不人为填充落后侧

若 RIGHT很快有stage4/5 snapshot，而LEFT没有：

- 这是训练结果；
- 不把RIGHT snapshot镜像/复制给LEFT；
- 不从LEFT-only cell导入snapshot到LR cell。

该模式将用于判断shared-policy interference或LEFT initialization问题。

---

# 7. v26 Acquisition Reward Registry

新建：

```text
gr00t/rl/config/rewards/wbmanip/reward_door_open_a2_v26_acquisition.yaml
```

目标是先学会完整 Stage0→5，而不是一次把最终行为审美、force novelty和实机安全全部塞进去。

## 7.1 Reward lineage结论

历史回溯得到四条关键事实：

1. v12是真正scratch，但当时Stage2 contact gate存在physics-frame/control-step时间尺度缺陷；它的失败不能直接否定scratch reward。
2. `push_door_handle` 在scratch时代为正，进入warm-start后被关为0；成熟policy可以靠已有unlatch route继续学，但fresh policy需要明确的handle-depression方向信号。
3. v13_A加入 `unlatch_hold + hold_and_drive + stage3 base unlock` 后突破开门；v13.1再加入release latch与released target-root routing后首次得到完整完成。
4. v16–v23加入的corridor、carry、posture economy、clearance/fling和强body-contact定价主要是成熟行为优化，不适合作为scratch acquisition的第一层。

因此 acquisition registry应当是：

```text
原始Stage0–2 dense guidance
+ scratch handle reward
+ v13的unlatch/hold-and-drive
+ v13.1 release/handoff
+ 基础安全regularization
- v16之后的行为审美/机制ablation税项
```

## 7.2 建议的初始scale

下表是正式前的默认提案。Worker可在真实 source binding/短smoke发现明显量纲错误时修订一次，并在 ledger中记录；formal启动后不再改。

### 全局与安全

| term | v26 R0 |
|---|---:|
| `penalty_dof_acc` | `-1.0e-5` |
| `penalty_dof_vel` | `-1.0e-3` |
| `penalty_delta_action_rate` | `-0.01` |
| `termination` | `-1000.0` |
| `limits_dof_pos` | `-5.0` |
| `limits_gripper_primitive_action` | `-1.0` |
| `ref_dof_legs` | `+0.25` |
| `penalty_door_frame_contact` | `-1.0` |
| `penalty_door_panel_contact` | `-0.1` |
| `penalty_base_command_limit` | `-1.0` |
| `penalty_undesired_contact` | `-0.2` |
| `penalty_dof_overspeed` | `-0.1` |
| `orientation_control` | `-5.0` |

不启用额外的：

```text
penalty_a2_door_body_contact
penalty_a2_posture_command_l1
penalty_a2_v22_excess_posture
penalty_a2_v22_posture_saturation
```

基础frame/panel/undesired-contact仍然提供安全代价。

### Stage0 — Walk

| term | v26 R0 |
|---|---:|
| `walk_to_door` | `+5.0` |
| `penalty_upper_body_non_gripper_deviation_l1` | `-5.0` |
| `pregrasp_gripper_dof_pos_l1` | `+0.5` |
| `penalty_face_door` | `-1.0` |
| `penalty_base_roll_pitch_l2` | `-2.0` |

Stage0既要走远，也要让arm安全收起，因此第一轮不削弱upper-body stow reward。

### Stage1 — Pregrasp

| term | v26 R0 |
|---|---:|
| `gripper_handle_orientation` | `+3.0` |
| `pregrasp_gripper_dof_pos_l1` | `+0.5` |
| `pregrasp_target_distance` | `+6.0` |
| `penalty_not_standing_still` | `-15.0` |
| `penalty_a2_stage1_stage2_base_forward_creep` | `-1.5` |
| `penalty_face_door` | `-1.0` |

planar reposition应主要在Stage0完成；进入精细pregrasp后，base稳定仍是已验证的接触条件。

### Stage2 — Grasp

完整保留当前A2 dense grasp bundle：

| term | v26 R0 |
|---|---:|
| `grasp_target_distance` | `+3.0` |
| `grasp` | `+0.2` |
| `a2_stage2_close_command` | `+1.0` |
| `penalty_a2_stage2_open_command_in_close_gate` | `-0.4` |
| `a2_stage2_close_progress` | `+0.5` |
| `a2_stage2_handle_center_y` | `+6.0` |
| `a2_stage2_handle_approach_xz` | `+3.0` |
| `a2_stage2_both_contact` | `+1.0` |
| `a2_stage2_opposite_squeeze` | `+1.0` |
| `a2_stage2_squeeze_force_window` | `+1.0` |
| `a2_stage2_contact_stability` | `+1.0` |
| `penalty_a2_stage2_over_force` | `-1.0` |

并保持：

```text
5 consecutive CONTROL steps
strict Stage2→3 grasp completion
no door-open bypass
```

不恢复：

```text
grasp_finger_dof_pos_l1
```

因为当前binary gripper已由close command/progress与contact bundle替代。

### Stage3 — Open

| term | v26 R0 |
|---|---:|
| `push_door_handle` | `+6.0` |
| `push_door_hinge` | `+6.0` |
| `a2_stage3_unlatch_hold` | `+3.0` |
| `a2_stage3_stage4_hold_and_drive` | `+8.0` |
| `a2_stage3_stage4_keep_close_command` | `+0.5` |
| `penalty_a2_stage3_stage4_open_command` | `-1.0` |
| `a2_stage3_stage4_both_contact` | `+0.5` |
| `a2_stage3_stage4_opposite_squeeze` | `+0.5` |
| `a2_stage3_stage4_squeeze_force_window` | `+0.5` |
| `a2_stage3_stage4_contact_stability` | `+0.5` |
| `penalty_a2_stage3_stage4_over_force` | `-1.0` |

同时：

```yaml
a2_stage3_base_unlocked: true
penalty_a2_posture_command_l1: 0.0
push_door_force: 0.0
```

说明：

- `push_door_handle` 是本轮明确捡回的scratch acquisition信号；
- `unlatch_hold/hold_and_drive` 是后续证明能把抓握转成开门的信号；
- base unlock落实v25的planar因果结果；
- `push_door_force`继续关闭，因为当前A2实现没有可靠的通用推门力reward authority；
- posture保持FULL，不交额外租金。

### Stage4 — Swing/Handoff

| term | v26 R0 |
|---|---:|
| `dont_push_door_handle` | `+3.0` |
| `push_door_hinge` | `+6.0` |
| `target_root_distance` | `+12.0` |
| `a2_stage4_grasp_target_distance_mild` | `+1.0` |
| `penalty_standing_still` | `-1.0` |
| Stage3/4 close/contact bundle | 保持原`.5/-1` |

显式采用v13.1式handoff：

```text
release latch around hinge 1.20 rad
latch后停止handle/hold/grasp-distance/hinge-position rent
保留必要的hinge velocity/progress与root traversal
released target-root使用完整权重
```

Worker必须确认当前source中这些suppressions的实际函数，而不是只设置threshold字符串。

不启用：

```text
stage5 hold-income continuity
corridor carry income
1.60 rad carry ceiling
```

v26 R0的目标是完整完成，不是先追求长期hold/carry form。

### Stage5 — Through

| term | v26 R0 |
|---|---:|
| `target_root_distance` | `+12.0` |
| `dont_push_door_handle` | `+3.0` |
| `penalty_upper_body_non_gripper_deviation_l1` | `-5.0` |
| `pregrasp_gripper_dof_pos_l1` | `+0.5` |
| `penalty_base_roll_pitch_l2` | `-2.0` |

Stage5不再付：

```text
hinge progress
grasp/contact bundle
handle depression
```

### 流程信号

| term | v26 R0 |
|---|---:|
| `stage` | `+1.0` |
| `complete` | `+4.0` |
| `success_save_time` | `+0.5` |

## 7.3 Acquisition阶段暂时关闭的成熟行为项

全部设0：

```text
a2_corridor_door_wide
a2_corridor_clean_passage
penalty_a2_v20_pre_send_crossing
a2_v20_arm_tangent_carry
a2_v20_handle_arc_tracking
a2_v22_clearance_success
a2_v22_controlled_fling
penalty_a2_v22_unsafe_release
penalty_a2_stage4_arm_default_pose_l1
```

这些指标仍可记录，但不参与R0 reward。

## 7.4 简单的stationary-rent检查

不建设新critic或复杂审计系统。Worker在每个有实际stage progression的候选上做一个短诊断：

```text
20 control steps保持近中性动作
vs
20 control steps执行policy动作
```

比较每个stage的：

```text
task progress
reward component sum
transition rate
```

若“静止不进展”持续拿到明显更高收益，优先修对应reward gate/income continuity，不通过增加更多惩罚掩盖。

---

# 8. R0 acquisition physics/randomization

## 8.1 从容易、真实可学的门开始

第一波不启用v24 native friction：

```yaml
a2_v24_friction_enabled: false
```

使用已经可解的普通push-door dynamics。exact D0参数由Worker从本地当前source与v13.1可解路径中确认，不从文档猜数值。

## 8.2 第一波随机化

从batch0启用：

```text
LEFT/RIGHT exact 50/50
natural-start distance/lateral/yaw
普通door width/height
handle height narrow-to-moderate range
door mass ordinary range
现有小幅robot state noise
```

建议起点：

```text
handle height: 0.85–0.95 m
door mass:     80–120 kg
```

不在R0一开始就使用：

```text
0.80–1.10 m handle height全宽域
80–160 kg heavy域
P10/P20 friction
强gripper material/force ablation
corridor/carry target
```

## 8.3 Proven capability，不继承policy

R0可以显式采用v13.1首次完整链路证明过的能力配置，例如：

```text
control-step grasp streak
stage3 base unlock
release latch
target-root handoff
gripper control gains/PhysX velocity iteration
```

但必须写入clean v26 config；不要通过继承v13/v22/v23 config获得。

Worker根据本地current hardware-approximation path决定是使用v13.1的`800/25` gripper gains，还是已被后续fix稳定下来的等价配置。选择需在formal前冻结，且四个cell相同。

---

# 9. 第一波四卡诊断矩阵

所有cell：

```text
scratch high-level Teacher
FULL posture
friction off
reward R0
fresh staged reset
4096 env
save every 250 batches
initial planned budget 4000 batches
```

| GPU | Cell | Purpose |
|---|---|---|
| GPU0 | `V26_LR_S0` | bilateral main，seed0 |
| GPU1 | `V26_LR_S1` | bilateral replicate，seed1 |
| GPU2 | `V26_L_S0` | LEFT task/init/reward可学性 |
| GPU3 | `V26_R_S0` | scratch protocol能否重现RIGHT能力 |

LR cell：

```text
2048 LEFT + 2048 RIGHT
```

L/R unilateral cell：

```text
4096 same-side env
```

## 9.1 预算

4000是上限计划，不要求所有run盲跑到终点。

Worker在：

```text
250 / 500 / 1000 / 1500 / 2000 / 3000 / 4000
```

查看side-stratified progression。只在明显实现错误或长期完全无进展时提前停；不要因早期goal为0就判死scratch long-horizon训练。

若3000–4000仍持续出现新的stage突破且无收敛迹象，Worker可提交一次延长建议；不得自动无限续训。

## 9.2 早期判读，不设机械硬门

### RIGHT-only也停在Stage0/1

优先检查：

```text
scratch actor/trainer init
far-start坐标
walk reward
staging timer
staged reset
reward binding
```

不是LEFT问题。

### RIGHT-only能学、LEFT-only停在Stage0/1/2

优先检查：

```text
common arm init pose
LEFT pregrasp orientation
workspace/joint margin
side-conditioned generic branch仍被A2调用
camera不相关，因为Teacher无RGB
```

### LEFT与RIGHT unilateral都能学，LR失败

这是shared-policy multimodality/interference证据。下一步优先：

```text
clean one-hot确认
side-conditioned feature modulation或双output head
适当增加shared recurrent capacity
```

而不是继续加reward。

### LR始终只学一侧

检查：

```text
exact side counts
actor handedness observation
per-side staged-reset occupancy
side-specific reward magnitude
```

### Stage2→3稳定但hinge flat

检查：

```text
push_door_handle绑定
stage3 base unlock
unlatch_hold/hold_and_drive
handle hard-limit
grasp保持
```

### Stage4 stationary

检查：

```text
release latch
hold income suppression
target-root stage4权重
stage reward rent
```

### Stage5 overtime

检查：

```text
target_root routing
stage5 timer
arm/gripper收尾是否挡住门框
```

---

# 10. v25-informed force-aware consolidation

只有存在至少一个能在LEFT和RIGHT都产生重复完整goal的scratch LR checkpoint后才进入。

## 10.1 Randomization分层

### R0 — Skill acquisition

已定义：

```text
side + far start + narrow geometry
friction off
```

### R1 — Planar/load consolidation

继续从新的scratch LR checkpoint训练，不从G7开始。

建议初始load mixture：

```text
60% P00 / legacy no-friction
20% P02
15% P05
 5% P10
```

P20 held-out only。

Worker可依据本地v24/v25已保存的行为梯度对比例做一次formal前调整，但原则不变：

```text
大多数样本仍可完成
中等比例迫使planar compensation
少量P10形成边界曝光
不让高摩擦淹没完整chain
```

## 10.2 v25因果结果如何改变randomization

### Planar是主要stable-grasp opening资源

因此R1重点随机：

```text
initial lateral offset
initial yaw
door side
handle lateral position/door width
moderate foot-ground traction
door reaction load
door mass/inertia
```

并记录：

```text
planar command
realized root displacement
foot slip
hinge progress
```

不要通过stage3 stillness penalty或base lock剥夺planar通道。

### Posture主要帮助reach/contact

因此：

```text
保持FULL posture
不随机强制RP0
不加posture command tax
randomize handle height与reach geometry
记录contact retention / achieved posture
```

posture的作用通过几何域自然出现，不把它塑造成持续饱和目标。

### Load不应从训练出生时就过强

v25表明P10会明显压低progress，但没有证明P10适合从scratch发现完整chain。R1才引入P02/P05/P10。

## 10.3 R1几何扩展

建议逐步扩至：

```text
handle height: 0.80–1.10 m
door mass:     80–160 kg
start distance: 0.80–1.55 m
lateral offset: ±0.35 m
yaw:             ±0.40 rad
```

每次只扩一层已注册distribution，不在一个run中持续无记录地改range。

---

# 11. Behavior-quality continuation

R0/R1先保证技能和负载泛化。随后才能恢复成熟行为优化。

优先级：

1. generic frame/panel/body contact；
2. unsafe release；
3. clearance；
4. natural quiet hold/release；
5. controlled fling；
6. corridor/carry；
7. posture economy。

恢复顺序建议：

```text
penalty_a2_v22_unsafe_release
→ a2_v22_clearance_success
→ body-contact event pricing
→ controlled_fling
→ corridor/carry
```

每次 continuation都从双侧scratch Teacher出发，并保留LEFT/RIGHT分层。

不要把所有行为项一次恢复。历史v13–v19已反复出现reward income cliff和stage-boundary rent。

Reward curriculum继续关闭；只有双侧Teacher行为定稿后，另开独立ablation。

---

# 12. Candidate selection

Teacher不以aggregate goal单独选点。

每个checkpoint按LEFT/RIGHT分别报告：

```text
natural-start max stage
stable grasp
goal
crossing while holding
hinge progress
release/no-release
clearance
body/frame/panel contact
fall/overspeed
planar path
posture use
completion time
```

## 12.1 Product candidate最低语义

```text
LEFT有重复、干净的完整goal
RIGHT有重复、干净的完整goal
不存在明显单侧collapse
从far natural-start可完成
不是只靠staged-reset完成
无系统性fall/unsafe/body-force路径
checkpoint/config可独立恢复
```

具体episode数和non-inferiority margin由本地Worker根据同轮样本量与noise在final holdout前冻结，不由云端写死。

## 12.2 两类候选允许分开

```text
TEACHER_LR_ACQUISITION
TEACHER_LR_LOAD_ROBUST
```

第一类用于快速Student启动；第二类用于更强力学泛化。只有第二类不拖延第一类交付。

---

# 13. Student handoff

当前G7 Student保留为：

```text
RIGHT_ONLY_BASELINE
```

不在原run中改变Teacher或door distribution。

双侧Student必须：

```text
从训练第一批数据就包含LEFT/RIGHT
使用新的scratch LR Teacher
使用新experiment root
不继承旧right-only optimizer/RMS作为默认
```

Teacher actor observation中的privileged side one-hot不直接进入Student；Student依靠RGB与proprioception判断handle side。

---

# 14. Worker自主权与升级点

## Worker可自主决定

在formal optimizer update前，Worker可根据本地source/runtime决定：

- door-relative spawn实现位置；
- far-start exact range；
- Stage0 timer；
- common neutral arm pose；
- handedness one-hot放置方式；
- v13.1 capability constants的显式值；
- R0普通门的exact参数；
- 4000 budget内是否提前停止明显死亡run；
- Route A样本数与视频数量；
- R1 load mixture的小幅调整。

每项改动写入ledger一次，不需要反复请示。

## 必须提交Owner的变化

- 改回G7或其他warm-start；
- 不再scratch；
- 取消LEFT/RIGHT batch0；
- 改成pull/in；
- 在R0引入P10主导或P20训练；
- 删除FULL posture；
- 更改Stage2 strict grasp semantics；
- 更改最终success定义；
- 改用side-specific scripted action；
- 需要训练/修改A2_Base low-level policy；
- 修改formal reward registry后继续沿用已产生的数据。

---

# 15. 工程执行纪律

1. 开工前先读file-based memory。
2. 先实现最小end-to-end：
   ```text
   clean config
   → 1-env LEFT/RIGHT preview
   → 64-env scratch smoke
   → 4096-env短学习
   ```
3. 功能路径确认前，不写broad regression、mutation test、legacy migration或通用fallback框架。
4. IsaacLab/IsaacSim code fail-fast；不为让训练继续而silent fallback。
5. 不写hash/SHA-256流程。
6. 不反复做全仓review；focused diff一次。
7. 超过30分钟任务放独立tmux。
8. 等待节奏：
   ```text
   sleep 30
   sleep 200
   sleep 600
   sleep 1800
   然后按预计完成时间长sleep
   ```
   不高频轮询。
9. context被压缩后：
   ```text
   读最新ledger
   → 读v26 memory
   → 查tmux/run状态
   → 继续最近未完成动作
   ```
   不重新回答旧问题。

---

# 16. 建议代码与文件

```text
gr00t/rl/config/rewards/wbmanip/
  reward_door_open_a2_v26_acquisition.yaml
  reward_door_open_a2_v26_consolidation.yaml

gr00t/rl/config/ablation/wbmanip/
  base_v26_common_scratch_lr.yaml
  base_v26_lr_scratch_seed0.yaml
  base_v26_lr_scratch_seed1.yaml
  base_v26_left_scratch_seed0.yaml
  base_v26_right_scratch_seed0.yaml
  base_v26_lr_load_seed0.yaml
  base_v26_lr_load_seed1.yaml

scriptsFORhuman/v26/
  a2_piper_base_v26_execution_plan_R1_20260821.md
  V26_REWARD_LINEAGE_REVIEW.md
  a2_piper_base_v26_execution_ledger_*.md
  a2_piper_base_v26_final_analysis_*.md

memory/a2-piper/
  base-v26-scratch-bilateral-teacher/
```

只有真实需要时才新增Python模块。优先使用现有：

```text
door spawner handedness
reset noise
staged reset
reward functions
v24 friction backend
v25 evaluation tooling
```

---

# 17. 预案

## Plan A — Scratch LR成功

进入R1 moderate load consolidation，随后Teacher handoff。

## Plan B — 单侧scratch都成功，LR失败

建立最小side-conditioned policy版本：

```text
clean one-hot
shared recurrent trunk
side-conditioned feature modulation或side-specific small output heads
```

保持reward、randomization和budget不变做单因素比较。

## Plan C — LEFT-only失败，RIGHT-only成功

停止LR长跑。优先修：

```text
arm neutral init
LEFT pregrasp orientation
stage0 lateral target
A2 runtime generic hand branch
joint/workspace margin
```

不通过增加LEFT reward权重掩盖几何错误。

## Plan D — 左右单侧都失败

说明R0 scratch exploration/reward/staged-reset协议仍不足。回到：

```text
Stage0–2 progression
Stage2 contact streak
handle depression signal
release/handoff
```

逐段恢复；不进入load randomization。

## Plan E — 完整行为出现后期又消失

优先检查：

```text
stage stationary rent
release income cliff
side-specific snapshot occupancy
checkpoint drift
```

使用机械checkpoint selection，不默认endpoint最好。

---

# 18. Typed outcomes

```text
V26_SCRATCH_PROTOCOL_VALID
V26_RIGHT_SCRATCH_REPRODUCED
V26_LEFT_SCRATCH_LEARNABLE
V26_BILATERAL_SCRATCH_TEACHER_READY
V26_BILATERAL_SHARED_POLICY_INTERFERENCE
V26_LEFT_INITIALIZATION_OR_ROUTING_BLOCKED
V26_SCRATCH_REWARD_OR_EXPLORATION_BLOCKED

V26_FAR_START_NAVIGATION_READY
V26_BILATERAL_STAGED_RESET_HEALTHY
V26_BILATERAL_STAGED_RESET_SIDE_IMBALANCED

V26_MODERATE_LOAD_CONSOLIDATION_PASS
V26_LOAD_CONSOLIDATION_DEGRADES_CHAIN
V26_TEACHER_LR_ACQUISITION_READY
V26_TEACHER_LR_LOAD_ROBUST_READY

V26_RESEARCH_PASS_NO_HARDWARE_RELEASE
V26_CONTINUATION_REQUIRED
```

---

# 19. 最终推荐

v26 的主线是：

```text
先恢复“从头发现完整双侧任务”的学习条件，
再恢复“成熟policy行为优化”的复杂奖励，
最后引入v25证明有意义的planar/load randomization。
```

最重要的四个不变量：

```text
scratch high-level policy
LEFT/RIGHT from batch0
fresh side-preserving staged reset
FULL posture + active planar base
```

最重要的reward决定：

```text
捡回push_door_handle
保留A2 dense grasp bundle
保留v13 unlatch/hold-and-drive
保留v13.1 release/handoff
暂时关闭v16+ corridor/carry/clearance/fling/posture-economy优化
```
