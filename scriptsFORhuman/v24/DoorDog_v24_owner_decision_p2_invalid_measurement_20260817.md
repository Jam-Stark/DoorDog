# v24 Owner 决策:P2 终局重分类为疑似无效测量,诊断后重跑(2026-08-17)

```text
DECISION                 = P2_TERMINAL_RECLASSIFIED + DIAGNOSE_THEN_RERUN
V24_E1_DENOMINATOR_INSUFFICIENT(r10) = 科学地位重分类为 SUSPECTED_INVALID_MEASUREMENT_PENDING_VITALS
                           (r10 receipt 文件本身不改;本决策文件记录重分类依据)
WORKER_CONDUCT           = 按注册 gate 执行无误;缺陷再次在 gate 作者侧(R1 未设仪器体征前置门)
```

## 依据

1. **测量自相矛盾**:warm checkpoint `G7-s0:1500` 在 v23 pooled 48/48、holdout 63/64(抓握率≈100%);hinge friction 不阻碍抓握(抓握先于开门),arm cap 亦然(v23 中 20 N·m 零样本正常抓握)。288 行覆盖 6 cap × 3 profile 却 stable grasp **0/288**、loaded-foot windows 0、E0 anchor 0——全配置一致归零不随任何实验轴变化,是仪器特征,不是物理特征。
2. **零分母 ≠ 分母不足**:注册终局 `E1_DENOMINATOR_INSUFFICIENT` 的语义前提是测量有效(体征正常、仅 E1 样本稀少,F3 pilot 才有意义)。测量无效时触发它,等价于把探头断线读成"无信号源"。
3. **新增常设规则(规则 16 候补,轮末入 ledger)**:任何 calibration/eval 种群,必须先在 easy/sham cell 上复现同 checkpoint 的既有基线体征(抓握率、stage-reach 在参考带内),其派生分母/分区/终局才可解释;零分母终局必须附带体征 PASS 才有效。

## 诊断阶梯(按序执行,找到根因即止,全部 GPU0 轻量)

1. **体征复现**:同一校准 harness,单配置=friction 关(真 sham)+ v23 冻结 arm profile(40 N·m)+ v23 D0 canonical 场景,16 env。预期 stable grasp ≥14/16。仍为 0 → 走第 2 步(harness 侧);恢复正常 → 走第 3 步(配置轴二分)。
2. **Harness 二分**:(a) checkpoint 身份——固定 obs batch 的动作与 P0 兼容 receipt 数值对拍;(b) **新 stable-grasp 检测器**——用一条 v23 已知有抓握的 trace 喂入,必须触发;(c) episode/stage 设置——horizon 长度、stage 初始化、staging bounds 与 v23 canonical16 对拍;(d) "paired scenarios" 生成器的门/机器人位姿合法性。
3. **配置轴二分**:(a) friction 是否只加在 hinge joint(不得波及 handle/gripper 关节);(b) τ_s 数值在 rad 面契约上核对(57.3× 复发检查:requested vs readback vs contract face 三面打印);(c) **arm cap 施加范围**——确认只作用 arm_j1-j6,gripper j7/j8 的 45/45 与 Kp/Kd 未被清扫(gripper cap 被清扫会精确制造"全配置抓握归零");(d) 6 个 cap 的实际数值与预期一致。
4. 根因修复后 **P2 r11 重跑**:体征门(sham cell 抓握率入带)PASS 后,才允许解释分母并继续注册生命周期(ladder freeze → E 区 certificate → P3)。若 harness 验证健康、sham 体征正常、friction cell 呈**梯度化**退化而 E1 分母仍 <8:先按 R1 F3 跑 marginal-E1 pilot 一次;仍不足才是合法的 `E1_DENOMINATOR_INSUFFICIENT` 终局。
5. 全程纪律不变:旧 receipts 不改、新裁决新文件引用本决策、additive、不 push、梯度短检→长眠。P3 的 owner 决策点维持原语义。
