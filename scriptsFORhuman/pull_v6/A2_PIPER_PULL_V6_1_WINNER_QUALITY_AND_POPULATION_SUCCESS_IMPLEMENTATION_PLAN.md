# A2+Piper Pull-v6.1 Winner Quality → Population Success 完整增补方案

- Plan ID: `a2_piper_pull_v6_1_winner_quality_then_population_success`
- 日期: `2026-08-27 HKT`
- 状态: `AUTHORIZED_PLAN__IMPLEMENTATION_NOT_STARTED`
- Source lock: `Jam-Stark/DoorDog` / `codex/a2-piper-pull-v0-20260803` / `041c5f02fbe953604e5acfd971242d2cfa5d7851`
- Cloud Pro review: `scriptsFORhuman/pro_reviews/20260827-163137-HKT__041c5f02fbe9/041c5f02fbe9/FULL_REVIEW.md`
- v6 winner checkpoint: `logs_rl/a2_piper_pull_v6/pull_v6_F0_r6an_seed3/model_step_000025.pt`
- winner eval contract: `gr00t/rl/config/ablation/wbmanip/pull_v6_F0_r6ap.yaml`
- winner strict-natural evidence: `logs_eval/a2_piper_pull_v6/p2_true_natural_F0_r6ap_seed3_step025`
- 可用资源: GPU0–3，均获 Owner 授权用于本阶段实现、训练、实验与 test

## 0. Executive decision

v6.1 不是一次 reward-weight sweep，也不是“arm reset”和“碰撞惩罚”二选一。它是 v6 behavior-creation proof 之后的完整工程阶段，按以下不可交换的 KPI 顺序推进：

1. **v6.1Q — winner behavior quality**：先优化已验证 env14 winner 的 release→through 行为质量，分离 arm reset 与 base corridor 的因果贡献，缩短 E6→E7 长尾，降低 arm/body 对 panel/frame 的接触、路径反复与 joint-target 漂移。
2. **v6.1P — population success**：在 v6.1Q checkpoint 不退化的前提下，提高 16-env strict-natural population 中 Stage0、Phase C、clean release、E6、E7 的成功覆盖。

不允许为了提高 population success 而接受明显更差的 winner through 行为；也不允许只把 env14 做得更漂亮后就宣称 policy robust。

Cloud Pro 给出的 gate、阈值和 ratio 只作为设计输入。本方案中的数值分为三类：

- source/config 已确认的 production contract；
- 本地首轮 experiment registration；
- 只有 runtime evidence 后才能晋升的 acceptance threshold。

任何 Cloud 数值都不会仅因出现在 review 中成为本地硬门槛。

## 1. 当前事实、推断和未知项

### 1.1 本地直接事实

- v6 已在 90 kg、right-hinge、out-opening、light-door F0 中得到一个 strict-natural E7 winner。
- 16-env seed3 eval 终局为：Stage0 overtime `6`、Stage4 overtime `9`、Stage5/E7 complete `1`。这是 behavior-creation proof，不是稳定 policy。
- env14 关键事件约为：E5 `319`、clean release `357`、K25 `384`、frame passage `620`、E6 `739`、E7 `1308`、terminal complete `1358`。
- env14 E6→E7 约 `569` control steps；base path `7.05 m`、reversal `30`、post-release recontact `2`。
- post-release contact attribution：早期存在 arm-panel/arm-frame contact，后期 frame jam 以 trunk/legs 为主。arm 是局部因素，base/whole-body route 是后段主因。
- 当前 resolved reward 已包含 upper-body deviation、arm tuck progress、persistent arm-default quality、frame/panel contact、world-frame waypoint tracking。再加一个通用 L1/default/collision penalty 没有新机制。
- current actor observation 是 `135D`；它包含 current `door_dof_pos` 与 2D release mode，不包含显式 15-frame door history。时序来自 LSTM。
- 当前 v6 state bank 只有 `B/C/D1/D5/D25` Stage4 rows；没有 frame-passage 或 E6/Stage5 row。
- current D controller 是 current-normalized-observation 驱动的 9-axis absolute mean override；pre-D carrier、gripper mode mean、RMS/std 在该 actor 中冻结。
- training 使用 99% Stage4、0% Stage5 reset；r6ap 的长 Stage5/global horizon 只用于 eval。late-stage training occupancy 与最终 success horizon 不匹配。
- successful env14 episode total return 为负，而多个 Stage4 timeout episode total return 为正；这是 reward-ranking red flag，但不同 episode horizon 使它尚不能直接证明 PPO 偏好失败。

### 1.2 当前推断

- 只做 arm reset 很可能改善局部 envelope 和视觉质量，但不能单独解决后期 trunk/legs frame jam。
- base corridor controller 对 E6/E7 更可能是一阶变量；arm compactness 是重要的 bounded co-objective。
- late-stage occupancy 与 horizon mismatch 很可能阻碍 safe/efficient E7 的学习。
- current observation 足以支持第一轮 evaluator intervention 和 D-head 训练，但不能据此宣称它对所有 release/door dynamics 是 Markov sufficient。

### 1.3 必须由本地 runtime 决定的未知项

- Stage0/default arm anchor 在 release 后是否真能降低 swept-envelope collision，还是会沿错误 joint-space 直线扫过 panel/frame。
- frame-relative base corridor intervention 是否能在 heading 自由的情况下缩短路径、减少 body jam并保持门开启。
- arm reset 与 base corridor 是否存在正交互。
- successful tail 的 reward ranking 是否在 event-aligned、equal-horizon 口径下仍劣于 timeout。
- frame-passage/E6 bank restore 后，cold LSTM history 对 current-observation D head之外的 policy/critic部分有多大影响。
- population failure 中 Stage0、B→C、clean release与 post-release route 的相对贡献是否随训练 seed改变。

## 2. Scope 与不变量

### 2.1 当前 stage scope

- 只做现有 90 kg light-door F0 canonical scene。
- heading 始终由 policy 自由调整；不添加 absolute yaw target或 heading lock。
- release 后 gripper保持 open；不 regrasp、不换握另一侧 handle、不 brace。
- 保持 canonical 12D action layout：base `0:5`、arm `5:11`、gripper `11`。
- 第一轮保持 135D actor observation contract；不添加 door velocity、pivot、contact gate或 phase one-hot。
- 保持现有 release state machine 与 clean-release definition，除非 runtime 直接证明 transition bug。
- 不把 PhysX raw contact peak解释为硬件安全力。

### 2.2 本阶段明确不做

- 重门、强 closer、F1 mass/closer family；
- release 后换握/撑门；
- full-body scripted oracle 取代 policy；
- world-Y-only 的单场景训练 reward；
- observation 扩维、door_dof_vel 显式输入；
- generic centralized critic / coupling critic 研究实现；
- 为旧 v6 bank/schema 添加兼容 fallback。

## 3. Stage architecture

```text
V6.1-Q0  Source/evidence freeze + telemetry semantic repair
    ↓
V6.1-Q1  Post-release evaluator intervention registry
    ↓
V6.1-Q2  Matched A/B/C/D causal discriminator
    ↓
V6.1-Q3  Reward-ranking audit + quality target selection
    ↓
V6.1-Q4  Late-state bank: D25 / frame-passage / E6
    ↓
V6.1-Q5  D-only winner-quality specialist
    ↓
V6.1-Q6  Quality qualification + multi-camera render
    ↓
V6.1-P0  Integrated actor/curriculum implementation
    ↓
V6.1-P1  Four-seed population training
    ↓
V6.1-P2  Strict-natural population evaluation
    ↓
V6.1-P3  Winner selection / render / stage closure
```

每一 phase 都有独立的 intervention 和 evidence。完整方案一次落成，但实验按 phase gate 执行，避免在一个 run 中同时改变 action ownership、reward、bank、horizon与 actor trainability。

## 4. V6.1-Q：winner behavior quality

### 4.1 Q0 — source/evidence freeze 与 telemetry 语义修复

目的不是增加护栏，而是保证后续指标测的是同一个事件。

实施项：

1. 以 source lock、r6an seed3 step25、r6ap、seed3、16 env、env14 为唯一 Q baseline。
2. 修正或替代有歧义的 telemetry：
   - `release_to_whole_body_clear_s` 必须从 actual clean-release event起算；旧 E5→E7 值保留为单独命名，不静默改历史 artifact。
   - 实现 `hinge_reclosure_after_release_rad = max_hinge_after_release - final/min_hinge_after_release` 的明确口径，并记录时间窗口。
   - terminal record 中 `complete/E7/terminal_reason` 使用同一 post-step event source。
3. 明确记录 control step、`dt=0.02 s`、physics/render timebase；MP4 duration 不作科学时间。
4. 输出一个 baseline evidence reducer，不重复跑 baseline即可先解析已有 trace。

Q0 出口：同一 reducer 能从已有 strict-natural trace复现 env14 E5/release/K25/frame/E6/E7、path/reversal/recontact与 contact attribution。

### 4.2 Q1 — post-release evaluator intervention registry

新增一个 v6.1 evaluator-only action intervention，不能复用 pre-release `r6u passage lateral counterfactual` 的语义或配置名。

建议 API：

```text
init_a2_eval_pull_v61_post_release_intervention(cfg)
apply_a2_eval_pull_v61_post_release_intervention(policy_action, first_episode_mask)
update_a2_eval_pull_v61_post_release_intervention_after_step(...)
```

配置 contract：

```text
mode: policy | arm_reset | base_corridor | both
target_env_id: 14
arm_anchor: stage0_default
arm_rate_rad_per_step: local calibrated value
base_waypoint_x_progress_m: local configured value
base_xy_gain_s_inv: local calibrated value
base_max_world_speed_mps: within existing HOMIE clips
```

触发与终止：

- 只在 `episode_index==0`、target env、v6、clean release已经 post-physics latch 后的**下一次 policy action**触发。
- 干预前 action必须逐元素等于 policy action。
- Stage0–4C、release-causing action、gripper与 policy yaw/pitch/roll保持原样。
- active 直到 E7、terminal或对应 branch 的显式完成条件；不得因 recontact静默关闭 base guidance。

#### Arm branch

- 只覆盖 arm action `5:11`。
- 基于 current accumulated arm target `_delta_actions`，生成 rate-limited move toward Stage0/default anchor；不一步硬跳、不直接写 simulator joint state。
- 使用实际 delta-action scaling反解 high-level command，使 accumulator下一步朝 anchor移动且受当前 per-step action contract限制。
- gripper `11`保持 policy/r6ag released-open mean，绝不被 arm branch写入。
- 首轮 anchor 是 Stage0/default，因为它是可证伪的已知参考；若 B cell 增碰撞，Q3 必须将 production target切换为 clearance-aware safe compact set，而不是加大回零速度。

#### Base corridor branch

- 只覆盖 base planar action `0:2`；base yaw/pitch/roll `2:5`保持 policy，heading自由。
- waypoint 使用 door-frame/world geometry：`door_root_xy + [travel_dir_x * through_distance, 0]`，不使用固定 world-Y sign。
- 计算 desired world XY velocity后，用 current root yaw转到 body frame，再反解 raw HOMIE action。
- 速度受 existing x/y physical clips约束；unsupported transform/shape/config直接 fail fast。
- intervention目标是 passage corridor，不直接写 root pose或 locomotion state。

四格均在 PPO distribution之后、env action之前修改，属于 evaluator counterfactual，不进入训练 logprob。

### 4.3 Q1 telemetry

只补后续 attribution必须字段：

- intervention `mode/active/start_step/stop_reason`；
- policy action与 applied action的 base `0:3`、arm `5:11`；
- base desired/actual world XY command、waypoint error；
- arm anchor、current target、target L1、per-step target change；
- actual arm joint margin与 soft-limit violation count；
- arm/body × panel/frame contact bool、step count与 bounded diagnostic force；
- clean release后 hinge max/min/current与 reclosure；
- frame passage、E6、E7、path length、reversal count；
- pre-release equality proof fields。

这些字段进入 eval trace/episode record，不进入 actor observation。

### 4.4 Q2 — matched A/B/C/D discriminator

| Cell | Base after release | Arm after release | GPU |
|---|---|---|---:|
| A | policy | policy | 0 |
| B | policy | rate-limited Stage0/default anchor | 1 |
| C | frame-relative corridor | policy | 2 |
| D | frame-relative corridor | same arm anchor | 3 |

固定条件：

- checkpoint/config/seed/num-envs/target-env/episode 都与 Q baseline一致；
- `r6an seed3 step25 + r6ap + seed3 + 16 env + env14 + one episode`；
- deterministic inference；
- intervention只影响 env14，其他 15 env用于确认 batch scenario identity没有改变；
- 四卡同时运行，独立 output root/port；同一卡只跑一个 IsaacSim process。

Matched admission：

- 逐行比较 intervention start之前的 selected state/action/event fields；不用 hash。
- A 必须复现 clean release与 post-release baseline vitals。
- 任一 cell prefix不匹配则记 `NOT_ADMITTED`，不把结果纳入2×2；只在 replay nondeterminism被实际观察后才安排 paired repeat。

直接指标：

- E6/E7与 event time；
- release→frame、frame→E6、E6→E7；
- base path length、reversal；
- arm/body × panel/frame contact steps；
- arm target L1、actual joint margin；
- hinge reclosure；
- fall/undesired contact/terminal reason。

因果分解：

```text
arm effect  = B - A
base effect = C - A
interaction = D - C - B + A
```

Q2 decision：

- B 只改善姿态但不改善 contact/path/E7：arm reset保留为次目标，不作为主训练机制。
- B 降低 arm contact且不损害 passage：Stage0/default anchor可进入 Q5 bounded arm objective。
- B 增碰撞：Stage0 exact pose退出 production target，改建 clearance-aware safe compact set。
- C 改善 body contact/path/E7：base corridor为主目标。
- D 明显优于 C：Q5 联合训练 base corridor + bounded arm compactness。
- 四格都无改善：停止 reward tuning，转查 locomotion interface、door reclosure和 late-state restore contract。

### 4.5 Q3 — reward-ranking audit

Q3 是 offline + evaluator evidence，不先改 scale。

审核三种口径：

1. full episode return；
2. clean-release→terminal tail return；
3. equal-horizon/event-aligned return，将 successful与timeout在同 control-step窗口比较。

必须拆分：

- progress/one-shot event；
- contact/safety；
- posture/arm compactness；
- time/termination；
- legacy Stage4 hold income。

只有当 event-aligned evidence仍显示 passive/timeout tail优于更安全高效的 E7 tail时，才修改 reward。目标不是让所有 success return变正，而是建立以下排序：

```text
safe efficient E7
  > collision-heavy slow E7
  > active but incomplete through
  > passive Stage4/Stage5 timeout
```

允许的最小 reward重构：

- `Δ signed whole-body-clear progress`；
- `Δ frame-relative lateral clearance`；
- one-shot E6/E7 credit；
- bounded new-contact event cost；
- bounded reversal/backtracking cost；
- arm safe-compact potential difference，在 safe envelope形成后停止支付。

禁止：

- 按帧 maintenance annuity；
- 继续加大 generic force/L1 penalty；
- 让长 episode仅因活得久就获得更高 return；
- 为使 env14总 return变正而无条件放大奖励。

### 4.6 Q4 — v6.1 late-state bank

v6.1 新建 exact late-state bank，不修改旧 v3 bank schema，也不加兼容 fallback。

Canonical labels：

1. `post_release_d25`：clean release且 persistence=25；
2. `frame_passage`：首次 frame passage的 post-physics完整 state；
3. `e6_stage5_entry`：E6 latch并进入 Stage5后的首个稳定 state。

每 row必须包含：

- robot/door root+dof state；
- env origin和门 metadata；
- v6 state/event/subphase/persistence buffers；
- delta action、previous action、unwarped action、HOMIE command/executor buffers；
- reward/state-machine所需累计量；
- source env/step/event label与 config/checkpoint provenance。

不保存 policy LSTM hidden state。理由：normal episode reset会清零 LSTM；current D absolute head应基于 current normalized obs工作。该选择必须在 bank→natural transfer里显式承认，不能把 bank成功直接外推 natural。

Bank capture先从 env14 deterministic replay得到三行。若后续 natural eval产生新的 clean/E6 state，再追加独立 scenario rows；不复制只有不同文件名的同一 state。

Restore smoke需要证明：

- articulation/buffer/row一致；
- event/subphase与 label一致；
- first-step observation/action有限且语义正确；
- D25→frame、frame→E6、E6→E7路径在至少一个已知 policy rollout中可继续；
- Stage5 row真实进入 Stage5 reset sampling，而不是仍被放到 Stage4 slot。

### 4.7 Q5 — D-only winner-quality specialist

Actor contract：

- 从 v6.1Q 选定的 winner-quality source checkpoint开始；初始默认 r6an seed3 step25。
- 保持 135D observation、12D action、release mode与 current-observation 9-axis absolute D head。
- 冻结 pre-D recurrent carrier、carrier MLP、RMS/std与已学 gripper mode means。
- 只训练 D absolute head；critic fresh/trainable。
- 若 Q2 证明 arm anchor有效，D head仍负责 base/arm 9 axes，arm safe-compact reward进入 Q5；不新增 scripted action到训练 rollout。

首轮本地注册 curriculum：

| source | reset mass |
|---|---:|
| natural Stage0 | 0.10 |
| post_release_d25 | 0.30 |
| frame_passage | 0.30 |
| E6 Stage5 entry | 0.30 |

这是 Q5 experiment ratio，不是 production硬门槛。它同时满足：natural非零、Stage4非零、Stage5 materially nonzero。

训练注册：

- 4 seeds，GPU0–3各一 seed；
- `256 env × 50 batches`，save step25/50；
- 相同 source checkpoint，不把 warm-start lineage称为四个独立 foundational policy；
- Stage5 horizon沿用 r6ap 的 `800`，global `36s`，确保 E7 credit可达；bank start实际所需时间由 event-relative metric报告。
- 超过30分钟使用四个独立 tmux session；输出目录、port、GPU独占。

Q5 stopping：

- step25如果四 seed都不能从 late bank恢复并产生 E6/E7，停止到50，回查 bank/action/critic contract。
- bank成功但 strict-natural全部失去 clean release，判定 integration failure，不选择该 checkpoint。
- contact下降但 path/reversal/E7不改善，不能以 reward income选 winner。
- arm target/joint margin持续恶化时停止 arm objective扩权。

### 4.8 Q6 — quality qualification

Q5 step25/50先各 seed运行同 seed strict-natural 16-env screening，四卡并行。选择最多两个 candidate，再执行：

- exact env14 baseline replay；
- Q2同一 quality reducer；
- 五相机 render；
- 旧 r6an/r6ap baseline并排比较。

v6.1Q winner优先级：

1. 保留 clean release、frame passage、E6、E7；
2. E6→E7 time/path/reversal改善；
3. body-frame contact减少；
4. arm contact、arm compactness、joint margin改善；
5. hinge reclosure不恶化到阻断 passage。

不设 Cloud 固定百分比。若没有 candidate同时保留 E7并改善至少一个直接质量变量，v6.1Q结论为 `INCONCLUSIVE/NOT_SUPPORTED`，不得进入 population fine-tune。

## 5. V6.1-P：population success

### 5.1 P0 — integrated actor

Q actor刻意冻结 pre-D carrier，无法改善 6 个 Stage0 failure和多数 Stage4/clean-release failure。P阶段需要新的 integrated actor contract：

- state dict与 135D/12D contract不变；
- 保留 current-observation D absolute head与 release gripper mode means；
- 保持 actor RMS冻结，避免改变 D-head输入分布定义；
- 解冻 recurrent carrier、carrier MLP、release gripper means、D head和 std；
- critic fresh/trainable；
- 不引入 phase selector、aux supervision或 scripted release。

如果全 actor unfreeze在首个 smoke中立即破坏 Q winner，则退回分组训练：先解冻 carrier output/release means，再视证据解冻 LSTM。这个分支由实际 regression触发，不预建兼容层。

### 5.2 P1 — population curriculum

首轮本地注册 distribution：

| reset family | total mass | row mix |
|---|---:|---|
| natural Stage0 | 0.50 | natural |
| Stage4 | 0.35 | B `0.30` / C `0.30` / D25 `0.20` / frame `0.20` |
| Stage5 | 0.15 | E6 entry |

折算总 mass约为：natural `50%`、B `10.5%`、C `10.5%`、D25 `7%`、frame `7%`、E6 `15%`。

设计理由：

- natural从1%提高到50%，Stage0/连续 upstream credit成为主样本；
- B/C明确保留 clean-release creation；
- late state继续占29%，防止只优化前半段后丢失 through；
- Stage5从0提升到15%，但不吞掉 population主目标。

这是第一组 registered curriculum，不自动成为最终 production ratio。只允许在 phase分析后修改一次主因明确的 row mix，不做无界 ratio sweep。

训练注册：

- 从 v6.1Q selected checkpoint warm start；
- 4 training seeds，GPU0–3各一；
- `256 env × 50 batches`，save step25/50；
- 若 step50 natural funnel仍在改善且无 Q regression，可一次性延长到100；否则停止。

训练 telemetry必须同时报告：

- reset realized counts/ratio；
- Stage0→E5 funnel；
- B→C、release-ready、clean release、D25；
- frame passage、E6、E7；
- quality metrics按 natural/bank source分层；
- return ranking按 stage/source分层。

### 5.3 P2 — strict-natural population evaluation

Screening：

- 四个 training seed的 step25/50分别先做 matching eval seed、16 env、1 episode；四卡并行。
- 只选择保留 Q-quality且 funnel有改善的最多两个 checkpoint。

Formal local evaluation：

- 每个 selected checkpoint运行 eval seed `0/1/2/3`，每 seed `16 env × 1 episode`；
- 四卡同时跑一个 checkpoint的四个 eval seed；两个 checkpoint则两 wave；
- 全部 strict-natural、bank disabled、无 evaluator intervention；
- 报告 64-episode funnel与 scenario strata，不把训练 seed当作唯一 denominator。

Population winner选择顺序：

1. Q-quality不退化；
2. E7 count与 E6→E7 conversion；
3. clean release count与 C→D conversion；
4. Stage0/E5 admission；
5. contact/path/reversal/hinge quality。

不从事后最有利 seed选结论。若 E7不增加，但 Stage0/C/clean显著改善，结论写为 upstream progress而不是 population success pass。

### 5.4 P3 — render与stage closure

对 population selected checkpoint：

- 渲染一个最优 complete episode和一个代表性 failure；
- 保持 trunk、handle top、handle side、world +X、world -X五视角；
- render与对应 strict-natural config/seed/env identity完全一致；
- 视频只用于行为解释，结论以 trace/episode record为准。

v6.1 close verdict只允许：

- `QUALITY_PASS__POPULATION_PASS`
- `QUALITY_PASS__POPULATION_INCONCLUSIVE`
- `QUALITY_INCONCLUSIVE`
- `NOT_SUPPORTED`

完成 v6.1 仍不自动进入重门/F1；需 Owner单独授权下一阶段。

## 6. Code/config work breakdown

### 6.1 Environment/evaluator

主路径：`gr00t/rl/envs/door/door_open_a2_pull.py`

- post-release intervention registry；
- arm target rate-limited action mapping；
- frame-relative base corridor action mapping；
- intervention telemetry；
- late-state capture/export/load；
- event-aligned reward/hinge/contact metrics；
- Stage4/Stage5 weighted row sampling。

保持现有 pre-release `r6u`接口语义不变；v6.1接口使用新名字，避免把两个不同时期的干预混淆。

### 6.2 Trainer/eval action hook

主路径：`gr00t/rl/trl/trainer/ppo_trainer_a2_base_api.py`

- 在 deterministic policy action形成后、P2/hardware intervention之前调用 v6.1 evaluator hook；
- 仅 eval config显式启用；
- 记录 policy/applied action；
- train路径不调用该 hook。

### 6.3 Actor

主路径：`gr00t/rl/trl/modules/`

- Q阶段复用 `PullV6PostReleaseObsOverrideActor`语义；
- P阶段新增 integrated actor，仅改变 trainability，不改变 forward/rollout/inference distribution语义；
- strict checkpoint conversion只在 state key确有变化时使用。若 shape/key不变，直接 strict load，不制造 converter。

### 6.4 Config

建议命名：

```text
pull_v6_1_Q_counterfactual.yaml
pull_v6_1_Q_specialist.yaml
pull_v6_1_Q_eval.yaml
pull_v6_1_P_integrated.yaml
pull_v6_1_P_eval.yaml
```

Q/P config必须从已确认 lineage继承，显式写 source checkpoint、horizon、bank path、row weights、actor target和 batch budget。

### 6.5 Scripts/artifacts

`scriptsFORhuman/pull_v6_1/`：

- `run_pull_v6_1.py`：train/eval/render/counterfactual入口；
- `capture_pull_v6_1_late_bank.py`；
- `analyze_pull_v6_1_counterfactual.py`；
- `analyze_pull_v6_1_reward_ranking.py`；
- `analyze_pull_v6_1_population.py`；
- `PULL_V6_1_ROUND_REPORT.md`。

不复制旧 v5 ceremony，不创建 hash manifest。

## 7. Command registry 与 GPU调度

### 7.1 Command management

实际 command在对应 hook/config存在并经过一次 narrow runtime smoke后生成，不能提前伪造 runnable command。

- exact command落在 `experiments/commands/`；
- train batch使用 `rl-command-manager`追加到 `experiments/COMMAND_BATCHES.md`；
- Q specialist比较 previous=`pull_v6_F0_r6an_seed{n}`，base沿用 active pull-v6 base；
- P integrated batch比较 previous=对应 Q selected lineage，同时保留 vs active base diff；
- 不重写历史 batch section。

### 7.2 GPU waves

| Wave | GPU0 | GPU1 | GPU2 | GPU3 |
|---|---|---|---|---|
| Q2 | A | B | C | D |
| Q4 smoke | D25 | frame | E6 | natural replay |
| Q5 train | seed0 | seed1 | seed2 | seed3 |
| Q6 screen | seed0 eval | seed1 eval | seed2 eval | seed3 eval |
| P1 train | seed0 | seed1 | seed2 | seed3 |
| P2 formal | eval seed0 | eval seed1 | eval seed2 | eval seed3 |

调度规则：

- 每卡同一时间一个 IsaacSim/train process；
- 独立 port、tmux session、output root；
- 训练期间空闲卡可运行已完成 checkpoint的 eval，但不能与同 GPU train重叠；
- 不为追求表面利用率同时启动无 decision value的 render；
- 长于30分钟的 run放独立 tmux并记录 command/output/process状态；
- 等待采用长间隔或 process completion，不高频轮询。

## 8. Evidence contract

每个 formal run登记：

```text
QUESTION / CLAIM CLASS
INTERVENTION / BASELINE
UNIT / TIMEBASE / EVENT
DIRECT METRIC
POPULATION / DENOMINATOR
ADMISSION / STOPPING
SOURCE / CONFIG / CHECKPOINT / COMMAND / GPU / OUTPUT
```

Evidence分级：

- code/config review: `INSPECTED`
- compile/config composition: `STATIC_PASS`
- hook真实执行/trace字段: `RUNTIME_PASS`
- A/B/C/D与training/eval: `EXPERIMENT_PASS`
- hardware: 本阶段 `NOT_RUN`

所有 absent evidence写 `NOT_RUN`；样本不足或方向不一致写 `INCONCLUSIVE`。

## 9. Failure routing

| 首个失败位置 | 结论 | 下一动作 |
|---|---|---|
| prefix不一致 | counterfactual未admit | 修 replay/action hook，不解释行为 |
| B增碰撞 | Stage0 anchor不安全 | 建 safe compact set，不加回零强度 |
| C无改善 | base intervention/locomotion不足 | 检查 frame geometry与 command realization |
| D不优于 C | arm不是主交互项 | Q5以 base route为主，arm只作 bounded constraint |
| reward rank错误 | objective credit错误 | Q3重构后再训练 |
| late bank不能续跑 | restore contract错误 | 修 bank，不用训练掩盖 |
| bank成功/natural失败 | distribution transfer失败 | 调整 natural occupancy或 actor trainability |
| Q通过/P upstream不动 | carrier冻结/credit不足 | P integrated actor + B/C occupancy |
| Stage0改善/C仍零 | release decision bottleneck | 聚焦 B/C，不改 D reward |
| C/clean改善/E6仍零 | post-release integration bottleneck | 增 late occupancy，不回退 release |

## 10. Deliverables

### Implementation deliverables

- v6.1 evaluator intervention；
- event-aligned telemetry fixes；
- counterfactual/reward/population analyzers；
- v6.1 late-state bank与 restore path；
- Q specialist + P integrated actor/config；
- command registry entries与 tmux receipts；
- Q/P strict-natural eval与 five-camera render。

### Stage artifacts

- `PULL_V6_1_COUNTERFACTUAL_REPORT.json/md`
- `PULL_V6_1_REWARD_RANKING_REPORT.json/md`
- `pull_v6_1_late_state_bank.pt`
- `PULL_V6_1_Q_QUALITY_REPORT.json/md`
- `PULL_V6_1_P_POPULATION_REPORT.json/md`
- `PULL_V6_1_ROUND_REPORT.md`

### Durable memory

只在 runtime后写入：

- arm/base/interactions的 causal direction；
- late bank restore与 transfer事实；
- quality/population winner与证据边界；
- reusable reward-ranking或 telemetry语义。

计划、heartbeat、单次失败日志不写 durable memory。

## 11. Research insight的处理边界

Q2会自然生成 post-release handoff counterfactual dataset，保留 matched state、policy/applied base/arm action与 downstream outcome。该数据可用于未来的 handoff-conditioned coupling critic研究，但 v6.1 production stage不实现 critic，也不把 novelty当 acceptance criterion。

只有 v6.1 完成 multi-seed natural integration后，才讨论：

```text
Counterfactual Handoff Credit for Safe Post-Release Traversal
```

当前 production目标仍是可复现的 safe/efficient through与更高 population success。

## 12. Final stage contract

v6.1 的完整目标是：

> 在不改变 light-door、heading-free、no-regrasp和135D/12D基础合同的前提下，先用 matched intervention找出 arm compactness与 base corridor对 winner through质量的真实贡献；再用 late-state occupancy、正确 reward ranking和 integrated natural curriculum，把该质量改进扩展到更多 strict-natural episodes。

阶段顺序固定为 `quality first → population second`；实现可以一次规划，证据不能越级。
