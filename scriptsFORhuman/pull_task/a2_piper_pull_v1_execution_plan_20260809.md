# A2+Piper Pull v1 — Reward Port & Stage Semantics: 执行方案(本机审计后改写版)

**Plan ID:** `a2_piper_pull_v1_reward_port_and_stage_semantics`
**Date:** 2026-08-09 HKT
**Authority chain:** 本文件 > `a2_piper_pull_v1_reward_audit_and_revised_plan_20260806.md`(云端审计稿)> 其余 pull_task 文档。冲突以本文件为准。
**GPU 授权:** GPU 6、GPU 7(用户显式授权,本阶段专用;其余 GPU 禁用)。
**执行模式:** worker session 全自主完成(用户离线,无人可问)。

---

## 0. 对 20260806 云端稿的 7 条 binding 修正(本机源码/遥测审计结论)

云端稿的三方 reward 数值表、公式描述、继承 gate(hinge>0.25 ∧ 5 步 grasp streak)、P5 指标全部核实无误,主体结构(恢复 bridge rewards + 恢复物理 gate + V1-A/B 单轴分离)采纳。以下修正 binding:

1. **target_root_distance 的失效机制改写。** v0 已存在 E5 事件门控(`door_open_a2_pull.py::_reward_target_root_distance` override),不是"回落 legacy 0.5"。真正缺陷是 clearance 谓词空洞:`a2_pull_control_clearance_min_m: 0.02` 的 body-origin 点云距离在门全关、手抓着把手时也 ≥0.059 m 恒真,导致假 E5 在假 E4 后 6 步锁存,P5 实付 7.45/18.19 episode-sum。v1 修理对象 = **谓词本身**(见 C4),不是"移植缺失的 gate"。
2. **锁舌是机械死通道。** mimic gearing −0.03/45、限位 [0,0.03],右开门下正把手角驱动目标为负、被下限截断——锁舌永远钉在 0;门靠斜面锥体硬凸轮过框打开(attempt20:push 侧 hinge 1.043 rad 而 max_handle 1.5e-4 rad)。因此:`latch_pos > 0` 谓词作废;**unlatch 是 shaping 行为而非机械前提**;E3 改为把手角定义的 report-only 标签(C3);`relock` 指标改定义在 hinge 回落上;`stable_unlatch_rate` 从唯一主 DV 降为与 `positive_hinge_while_valid_hold` 并列(后者对准真瓶颈:抓住了但拉不动)。
3. **Freeze guard v1 分支是 P0 第 1 步。** `a2_pull_v0_guard.py:341` 硬钉 `a2_pull_threshold_mode == "report_only"` 且绑定 v0 plan id;不加 v1 plan-id 分支,C2 的 gate 修复在 env 构造时就被拒绝(v21-B P0-G / Amendment 3a 的既有教训)。
4. **P0.3 canonical state probe 取消独立套件。** scripted 轨迹探针已三次失败并被 Amendment 7 退役;forced-state 套件也不另建。**D0 冻结重放的遥测直接充当假事件负向测试**(v0 actor 不开门 ⇒ 修复后的 env 里 E4/E5/stage4/stage-4-only reward 必须全为零)。fail-fast:先跑,出错即暴露。
5. **P0.4 "alias 完全一致"取消。** `pull_door_hinge` 相对 push 版有**有意差异**(整积乘 load-bearing mask、活跃段含 STAGE_THROUGH),这是 E.6-3 收入连续性的正确实现,保留;只要求"正关节坐标方向不变 + 差异申报",不做逐位对齐。
6. **C2 合并谓词写全:** v1 Stage3→4 = `base 物理 gate(hinge>0.25 ∧ streak) ∧ panel_clear(body+arm 接触力==0)`。丢掉 panel_clear 会放进身体助推的 Stage 4。
7. **全程禁止计算/写入哈希(含 SHA256)。** 新 receipt/报告一律以路径 + 文件存在性绑定。旧 receipt 里的哈希字段不再延续。

---

## 1. 冻结决定(不重新讨论)

| 项 | 值 |
|---|---|
| Actor warm-start | `logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/pull_v0_p4_formal_seed0-20260805_211252/model_step_002500.pt`(P5 render QA 对应的那只) |
| 加载模式 | 沿用 P4 先例 `checkpoint_load_mode: policy_only`;若该模式实际连 critic/optimizer 一起载入,查 loader 后选择能重置 optimizer 的既有模式即可,**不新写 loader**,偏差记入报告 |
| Robot / door 物理 / PPO 结构 | 全冻结(45N/1300/32 finger、STOCHASTIC_BASELINE hook、RESOLVED_V20_G4 friction,同 P2/P4) |
| 训练拓扑 | 256 env × 750 batches,save every 250(P2 模板 `pull_v0_p2_adaptation.yaml` 直接 fork) |
| 全目标 / E6 / E7 | report_only |
| 时长先验 | P2 同拓扑单 cell ≈ 3h10m/GPU(p2 run 目录时间戳 03:03→06:13→09:31);smoke 64×50 ≈ 10–20 min |

---

## 2. 代码改动 C1–C6(最小 diff,fail-fast,不加防御性 fallback)

**C1 — guard v1 分支(第一步,否则一切被挡)。**
`a2_pull_v0_guard.py`:新增 plan id `a2_piper_pull_v1_reward_port_and_stage_semantics` 分支。v1 分支接受 `a2_pull_threshold_mode: "hard_gate"` 与恢复后的 bridge scale;v0 分支逐字节不动。既有 guard 单测若因新分支失败,做最小修正让其通过即可,**不新增测试**。

**C2 — 恢复物理 Stage3→4 gate。**
`door_open_a2_pull.py::_stage_3_to_4_advance_condition`:`threshold_mode == "hard_gate"` 时返回 `super()._stage_3_to_4_advance_condition() & panel_clear`(base 即 hinge>0.25 ∧ streak;panel_clear = body+arm panel 接触力总和==0,复用现有 helper)。E4 事件 evidence 同步改为同一谓词族(E4 := E2_reached ∧ hinge>0.25 ∧ stable_contact ∧ panel_clear),E-链里 E4 不再依赖 E3。staged-reset 快照按 stage_buf 入库,gate 修复后自动纠正,无需另改。

**C3 — E3 重定义(report-only 遥测)。**
E3 := `handle_pos ≥ 0.3 rad ∧ stable_contact`(0.3 = unlatch 归一化分母 0.6 的一半;仅作测量标签,不进任何 gate/reward)。`latch_position_m` 继续原样导出。

**C4 — target_root_distance 门控修复。**
`door_open_a2_pull.py::_reward_target_root_distance`:把 `measured_e5` mask 换成锁存事件 `aperture_ready := 曾达成 (hinge ≥ a2_v20_send_hinge_threshold(=1.0) ∧ stable_contact)`。之前恒零,之后走 `super()`(legacy 0.5 stage-4 乘数语义,方向不变量)。**cdist/clearance 数值从门控中移除**,仅保留为遥测。E5 事件 evidence 同步改为 `aperture_ready ∧ panel_clear`(decision latch 逻辑随之简化,允许直接删除 `record_a2_pull_release_or_hold_decision` 的 clearance 依赖)。

**C5 — V1-B reward scales(仅 ablation yaml)。**
```yaml
a2_stage3_unlatch_hold: 3.0
a2_stage3_stage4_hold_and_drive: 8.0
```
其余不动:`dont_push_door_handle: 3.0`、`target_root_distance: 12.0`、`pull_door_hinge: 6.0`、`pull_door_handle: 0.0` 保持。

**C6 — 新建两个 ablation yaml。**
fork `pull_v0_p2_adaptation.yaml` →
`pull_v1_A_gate_repair.yaml`(warm ckpt + `threshold_mode: hard_gate`,scale 不动)与
`pull_v1_B_reward_port.yaml`(= A + C5)。两者都写入 v1 plan id 供 C1 校验。

不做的事:不动 push namespace 任何文件;不实现 V1-C 的 corridor/crossing 移植(条件性 stretch,见 §5);不写新测试、新护栏、新哈希。

---

## 3. Cell 与 GPU 排程(GPU 6/7)

```text
T0  P0: C1..C6 实现 → D0 冻结重放(任一空闲 GPU,eval-only,分钟级)
      D0 通过判据(即假事件负向测试):v0 actor 在修复 env 中
      - stage_buf 终态 ≤ 3,E4/E5 计数 = 0
      - dont_push / target_root episode-sum = 0
      - unlatch_hold / hold_and_drive raw 遥测有限、按掩码激活
      任何一条不满足 = 代码有 bug,修完重跑 D0(fail-fast,不绕过)
T1  smoke:64×50 跑 V1-B 配置一次(GPU6),确认训练路径/存档/新 gate 无崩溃
T2  Wave1(并行):GPU6 = V1-A seed0,GPU7 = V1-B seed0(256×750,~3.2h)
T3  Wave1 eval:全部 checkpoint(250/500/750)事件漏斗 eval(复用 P2/P4 eval 机制,
      p4_eval_all_checkpoints.sh 为命令范式),立刻出 Wave1 中期对比
T4  Wave2(并行):GPU6 = V1-A seed1,GPU7 = V1-B seed1(~3.2h)
T5  Wave2 eval → 主对比表
T6  条件性 Wave3(见 §5 预案分支,~3.2h)+ eval
T7  (可选)最佳 checkpoint 渲染 QA(单 GPU,~30min)→ 总报告、memory、commit/push
```

预计总时长 10–14h。等待纪律:launch 后 +600s 查一次 batch 进度外推剩余时间,然后**一次性 sleep 到预计完成时刻**(如 `sleep 10800`);醒后一次核对(进程退出 + `model_step_000750.pt` 存在),未完则 `sleep 1800` 递补。禁止轮询。

---

## 4. DV 与完整性 invariant

**并列主 DV**
- `true_stage3_to4_rate`(hinge>0.25 ∧ streak ∧ panel_clear 谓词直判,不信 stage 标签)
- `positive_hinge_while_valid_hold_rate` 与 `hinge_delta_while_valid_hold_rad`

**次级漏斗**:valid_grasp_rate、max_handle_angle_rad 分布、stable_unlatch_rate(handle≥0.3 rad)、handle_0p6rad_reach_rate、E2 capture/proof 指标、capture_loss_during_initial_pull_rate、stage3_overtime_rate。条件率分母为零报 `N/A` 不报 0%。

**reward 经济学**:unlatch_hold / hold_and_drive episode-sum 与 per-active-step mean;`dont_push 在真 Stage4 前激活次数` 与 `target_root 在 aperture_ready 前激活次数`——**两者必须恒 0,是完整性 invariant**(连同 假E4=0、低于 gate 的 Stage4 快照=0)。invariant 破坏 = 实现 bug,修复重跑,不作为科学结果解释。

---

## 5. 自主决策规则与预案(用户离线,worker 全权)

判读窗口:每个 wave eval 后。比较基线 = pull-v0 P5(held hinge max ≈0.0019/0.0014 rad,handle max ≈0.0003/0.107 rad)。

| # | 触发 | 自主响应 |
|---|---|---|
| F1 | V1-A ≈ V1-B ≈ v0(双 seed 均无 handle/hinge 增益) | 执行 rescue:`pull_v1_R_handle_rescue.yaml` = V1-B + `pull_door_handle: 6.0`,Wave3 双 GPU 双 seed。仍无效 ⇒ 记录"reward 迁移不是主要瓶颈"的预登记负结果,指向 tensile 力传递/轨迹分析,收官 |
| F2 | V1-B 增益明确 > V1-A(任一主 DV,双 seed 同向) | 主结论成立。Wave3 改跑 V1-B seed2(GPU6)+ V1-B 最佳配置 2500-batch 延长确认(GPU7);V1-C 仍不做 |
| F3 | V1-A 单独已解决(gate 修复即出 hinge 进展) | 同 F2 流程,主角换 V1-A;V1-B 结果作为 reward-port 附加效应报告 |
| F4 | 双臂 seed 间分裂(同臂两 seed 结论相反) | 标注 basin 敏感;Wave3 给分裂臂补第 3 seed;报告按"多数 + 不确定度"写,不摘樱桃 |
| F5 | 真 Stage4 出现且 policy 过早冲向 [-2,0,0.5] | 检查 aperture_ready 锁存是否过早(hinge≥1.0 是否真达成);是实现 bug 则修+重跑该 cell;是行为问题则记录,留给 V1-C,不现场加 reward |
| F6 | 训练进程崩溃 | 读 traceback 修根因(fail-fast,不 try/except 吞掉),重启该 cell;同一 cell 崩 3 次 ⇒ 放弃该 cell,记录,继续其余矩阵 |
| F7 | GPU 6/7 之一被外部占用 | 用空闲的那只串行执行,顺序不变,报告记录 |
| F8 | D0 发现 C1–C4 语义错误 | 修复→重跑 D0,循环直到通过;这是唯一允许"反复"的环节,因为它是功能正确性本身 |
| F9 | 时间超预算(如单 cell >6h) | 检查吞吐是否异常;正常但慢 ⇒ 砍掉可选项(渲染 QA、延长确认),保住 Wave1+Wave2+eval+报告的最小完整闭环 |

**Stretch(仅当 F2/F3 且全部主线完成后仍有时间)**:V1-C 的最小版 = 打开 `a2_v20_traversal_economics_enabled: true` 并把 send_ready 供给源换成 aperture_ready,单 seed 试跑。不新写 corridor 移植。

---

## 6. 交付物

1. 代码 commit(`feat(a2): ...` 风格,小步提交)+ **push 到 `codex/a2-piper-pull-v0-20260803`**(同时补 push 本地领先的 v0 实现 commit 与本文件,闭合云端稿 provenance gap 2)。
2. `logs_rl/.../pull_v1_*` 训练目录 + `logs_eval/a2_piper_pull_v1/` 漏斗 eval。
3. `scriptsFORhuman/pull_v1/PULL_V1_ROUND_REPORT.md`:主对比表(cell × checkpoint × 主 DV/次级 DV/invariant,含 v0 基线行)、D0 结果、走过的预案分支及理由、Appendix-D 风格表含本轮 DV、预登记负结果(若触发)。**表内不写哈希。**
4. `memory/a2-piper/pull-open-door-task/` 更新(HKT 时间戳,zh + EN 术语)+ `a2_piper_longterm_TODO.md` 同步一行。

## 7. 执行纪律(coding role,全程有效)

- fail-fast:isaaclab/训练代码禁止为"健壮性"加保护性 fallback 强行让仿真跑下去;问题必须在运行中暴露。
- 先功能后护栏:先证明操作路径、把功能跑通;不新增测试/护栏/兼容层,除非某功能已实际出错。
- 严控审计次数:单次 review 上限一轮;禁止反复 diff/编译/路径边界检查、过度串行 fixture 修复与 sandbox loopback。
- 禁止计算/写入任何哈希(含 SHA256);禁止为基本不可能的 case 写防御;rubric 处不过度机械化。
- 等待一律大块 sleep(600s/1800s/10800s/更长),或派子 agent 等待、主线并行写 eval 编排;禁止轮询。
- 工具调用尽量并行批量;上下文压缩重启后不重复回应旧指令,跟紧最新进度。
