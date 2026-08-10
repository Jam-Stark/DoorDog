# C-B2H v19 大规模 Camera 配置验证 Eval — 方案设计

日期：2026-08-10
设计：main agent（Claude）
执行：worker session（按本文档执行，预案范围内自主决策）
状态：待执行

---

## 1. 背景与决策问题

C-B2H v19（双 D435i RGB packed、toe-out6、pitch50）Student 蒸馏在修复 G2 Stage0 契约后：

- Student 8000-step checkpoint 三 seed：13/16、16/16、13/16，合计 42/48 = 87.5%
- fixed-G2 Teacher：32/32 = 100%
- 小样本诊断（`C-B2H_v19_G2_Stage2_Diagnosis_20260809.md`）：残余失败集中在 Stage2 接触连续性（streak 2 vs 要求 5），失败集跨 seed 不重叠、同 seed replay 漂移、把手全程可见 → 初步判断为策略随机性，**非视觉信息不足**。

导师提出两个候选感知升级：(a) 开启双 D435i 深度图；(b) 腕部加深度相机。本实验的唯一目的：**用足够统计量把残余 gap 归因为"视觉不足"或"策略随机性"，据此决定是否需要感知升级**。

48 集样本的 95% CI 约 75%–94%，无法支撑该决策；目标是将 Student 成功率区间收窄到约 ±3%。

## 2. 实验设置

### 2.1 资产

- Student checkpoint：`logs_rl/by_batch/cb2h_v19_toeout6_pitch50_20260805/formal_4x64_8k_gpu4-7_timeoutfix_retry/model_step_008000.pt`（8000 step，不做任何续训）
- Eval pipeline：`gr00t/rl/scripts/run_a2_toeout6_student_eval.py` 及其 Teacher lane
- 契约：修复后的 G2 Stage0 band（`0.50 ≤ dx ≤ 0.80`、`|dy| < 0.15`、arm deviation < 0.10、base command norm ≤ 0.10），Stage 超时 `[250,100,100,100,100,200]`，与训练侧一致
- 门随机化：正式 G2 全范围（17 项 customData）

### 2.2 规模

| Lane | 结构 | 集数 | ratio_teacher_rollout |
|---|---|---|---|
| Student | 16 env × 32 seed（seed 0–31）× 1 episode | 512 | 0.0 |
| Teacher 对照 | 16 env × 16 seed（seed 0–15）× 1 episode | 256 | 1.0 |

Teacher 仅作天花板参照，不需要与 Student 同宽的置信区间，故减半。

### 2.3 并行与调度（GPU4–7）

- 按 seed 分片，每分片 = 16 env × 若干 seed，单卡串行跑分片内 seed。
- 默认分配：GPU4/5/6/7 各领 Student 8 个 seed；先完成的卡依次认领 Teacher 分片（每片 4 seed × 4 片）。
- worker 可根据实测单 seed 耗时与显存重排分片，原则：四卡负载均衡、总墙钟最短。
- 预估：此前 16 env formal eval 单卡约 10–20 min/seed 量级，Student lane 单卡 8 seed 约 1.5–3 h，全程（含 Teacher）约 3–5 h。worker 实测 smoke run 后自行修正估计并按估计 sleep。

### 2.4 执行顺序

1. **Smoke run**：Student、Teacher 各 1 个 seed 分片，验证脚本、输出路径、契约版本；**Teacher lane 必须抽查动作链与 gt_actions 一致、Student rollout 调用为 0**（本任务此前出过"假 Teacher"事故，此项不可省）。
2. Smoke 通过后放量，四卡并行。
3. 全部分片完成后做后处理与分析（§3、§4）。

## 3. 逐集记录字段

在现有 `terminal_diagnostic` / selection 输出基础上增量后处理，**不修改 env 逻辑**：

1. 基础：env_id、seed、goal_reached、max_stage、terminal_reason、reward、episode 长度、17 项门 customData。
2. Stage2 归因：`a2_stage2_squeeze_streak` 最大值、双侧接触总时长/最长连续时长。
3. 视觉条件量化（用于视觉归因）：
   - 把手在左/右 D435 画面中的可见帧比例；
   - 最长连续遮挡时长；
   - 把手平均像素尺寸（近似观测难度/距离代理）。
   - 计算方式：优先离线投影估算（把手世界位姿 + 相机内外参 + 手臂遮挡近似）；若逐集成本不可接受，**降级为抽样**：全部失败集 + 等量随机成功集，报告中注明抽样方案。

## 4. 分析与判据（事先固定）

### 4.1 统计

- Student 总成功率 + Wilson 95% CI；Teacher 同口径；gap = Teacher − Student。
- 失败按 stage 分布；按 seed 的失败 env 重叠度。
- 失败集 vs 成功集：视觉条件三指标、17 项门几何的分布对比（均值/分位数 + 简单显著性即可，不做机械化 rubric）。

### 4.2 结论判据（三选一）

- **(a) 当前配置充分**：gap ≤ ~5%，且失败与可见性指标无相关 → 双 D435i RGB 对本任务充分，深度/腕部相机暂无必要；剩余 gap 走 Stage2 contact-continuity DAgger finetune（另行批准）。
- **(b) 需要感知升级**：gap 明显（> ~10%）且失败集中于视觉困难条件（低可见比例/长遮挡/小像素把手）→ 优先开启现有 D435i 深度通道（硬件零改动），腕部相机作为深度通道无效后的下一步。
- **(c) 混合**：两类信号并存 → 按占比拆分，分头给建议。
- 边界情况（gap 5–10% 且相关性弱）归入 (a) 倾向 + 报告中说明不确定性。

### 4.3 异常防线

若 Student 大规模成功率 < 70%（与三 seed 基线严重矛盾）→ 先怀疑管线（契约版本、checkpoint 路径、Teacher 路由、随机化范围），逐项验证无误后才接受数据。

## 5. 产出

- 结果目录：`logs_eval/by_batch/cb2h_v19_toeout6_pitch50_largescale_camera_eval_20260810/`
  - `student_gpu{4..7}/`、`teacher_gpu{N}/` 分片原始产物
  - `summary/per_episode_records.json`（逐集全字段）
  - `summary/aggregate_stats.json`（聚合统计 + CI + 判据结果）
- 结果报告：`scriptsFORhuman/C-B2H_v19_LargeScale_Camera_Eval_Report_20260810.md`（结论先行：判据命中哪一条、对"开深度图/腕部相机"两个提议的数据回应、给导师的一段汇报摘要；附结果表与失败归因）。
- 收尾：worktree 内 commit（不 push）、更新 memory、释放全部 GPU 与 tmux。

## 6. Worker 自主决策边界

无需请示、按预案处置：分片崩溃/OOM 重跑与降并发、GPU 被占重分片、可见性统计降级抽样、耗时估计修正与 sleep 时长、分片方案重排。
2 次重试内无法解决的阻塞：记录现场、跳过该分片、报告中标注缺口，不卡死整体。
禁止事项：修改 env/契约逻辑、对 checkpoint 做任何训练、push、超出本目录写产物。
