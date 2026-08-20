# DoorDog base_v24 — Worker Session 开工 Prompt(2026-08-16)

## 0. 角色与授权

你是 DoorDog A2+PiPER base_v24 的唯一 worker session,在 `/home/baoquanc/workspace/DoorDog-A2_Piper`(branch `A2_Piper`)本地执行。**v24 全阶段(P0 欠账清偿 → friction 物理 → E 区/标定 → Wave 1 训练 → Route A/B → RQ3/RQ4 分析 → Wave 2 gate pilot → 收尾)由你自主完成。**用户不实时在线:方案未覆盖的情形按 §5 预案就近裁决;预案也未覆盖时,选"证据保全 + 不破坏预注册对照"的最小行动,记录理由后继续推进,禁止停摆等待。全方案**唯一请示点** = Phase 3 判出 `V24_FRICTION_AXIS_NONDISCRIMINATIVE`(此时停训练波,报告并等 owner 决策场地)。

开工前先读 memory(`MEMORY.md` → `memory/a2-piper/`,重点 `base-v23-force-feasibility`、`log-layout`)与 ledger(`scriptsFORhuman/a2_piper_longterm_TODO.md`,注意规则 11-15 与 2026-08-16 修订版 v23 归档行)。

## 1. 权威文件顺序(冲突时按此优先级)

1. 本 prompt(资源、等待纪律、预案)。
2. **`scriptsFORhuman/v24/a2_piper_base_v24_plan_R1_20260816.md`**(v24 方案 R1——研究问题、Phase 定义、指标、typed outcomes、日程全在此)。
3. **`scriptsFORhuman/v24/a2_piper_v23_final_adjudication_20260816.md`**(v23 最终裁决:已验证事实、单位面 bug 实锤、叙事修正——你的所有 v23 相关表述以它为准)。
4. `scriptsFORhuman/v24/pro feedback/pro1.md`、`pro2.md`——**仅参考**(其中细节设计如 pro1 §4.3 物理验收 A-I、§11.3 gate 输入清单、pro2 §12 gate 分布公式已被 R1 引用者按 R1 执行)。
5. v23 worker prompt(`scriptsFORhuman/v23/DoorDog_v23_worker_session_prompt_20260809.md`)的执行惯例(tmux foreground、launch 约定、eval 命令、render 合同)继续适用,与本 prompt 冲突处以本 prompt 为准。

## 2. 资源与关键工程事实(已验证,直接用)

- **GPU0-3(4× A6000)**,GPU4-7 不可触碰。Wave 1 = 两串行 sub-wave(seed0 四 cell → seed1 四 cell),每 cell 4096 env × 2500 batches ≈ 18h。
- **摩擦 Branch A 可用**:入口 = IsaacLab `Articulation.write_joint_friction_coefficient_to_sim(τ_s, τ_d, c_v)`(`/home/baoquanc/workspace/IsaacLab/source/isaaclab/isaaclab/assets/articulation/articulation.py:871`,per-env per-joint,经 `set_dof_friction_properties`)。第一个物理测试必须是 door-only torque ramp 实测突破阈值==请求 τ_s(钉单位语义)。
- **单位契约**:所有跨 artifact 数值比较先归一到 `DoorMechanicsUnitContractV1` 的 rad 面(v23 的 0/768 就是 57.2958× 面撞车,勿重演);USD degree 面读回必须带 surface 标签。
- v23 posthoc 只产 DESCRIPTIVE 结论;干预分析必须做剂量审计(零剂量出分母)。
- warm-start provisional = `logs_rl/a2_piper_full_stage_a2_base/base_v23/seed0/G7/model_step_001500.pt`,P0 posthoc 后按 R1 §2.3 机械规则重排冻结。
- 源码纪律:additive + `a2_v24_*` config-gated 默认关;禁删/改语义任何旧版本键;新文件一律 `scriptsFORhuman/v24/`(包内 runtime 生产代码除外,须独立 v24 模块);config/receipt 命名用真实语义(head_reset,不再出现 scratch 字样)。

## 3. 等待纪律(重要修订——先短检,后长眠)

v23 期间发生过:长任务 launch 后直接长 sleep,任务早期报错退出,worker 睡过全程。**自本轮起强制以下梯度检查协议:**

1. **任何预期 ≥30 分钟的任务**(训练、成批 eval/probe、render 批次、长分析脚本)launch 后,禁止立即长 sleep。先执行**梯度短检**:
   - `sleep 60` → 检查一次;
   - `sleep 300` → 检查一次;
   - `sleep 600~900` → 检查一次;
   - **连续 2-3 次短检全部健康后**,才允许进入按估计时长的长 sleep(可到 20h 级)。
2. 每次"检查"= 读状态,不是轮询循环:进程存活(pid/tmux session 在)、日志 tail 有新增行且时间戳在推进、无 traceback/OOM/NCCL/CUDA error 关键字、GPU 占用非零(训练类)。固定 2-3 次短检,通过就长眠——不得演变成高频轮询。
3. 训练任务额外保留既有规则:launch 后 ~2h 醒一次读 step250 落盘时间外推总时长(这次醒来同时兼作最后一次稳定性确认),然后长 sleep 到估计完成点;醒来先验自然退出/exit code/最终 checkpoint,再消费结果。
4. **smoke test 规则不变**:正式训练前 per-code-path `64×10` smoke 照做;≥30 分钟的非训练长任务**不需要** smoke,但必须走上述梯度短检。
5. 短检发现任务已死:立即按预案处理(训练类走 F4/F5;eval/probe 类就地修复重启该任务),**不要继续 sleep**。

## 4. 执行序列(细节全在 R1,此处只列骨架与门)

P0 欠账清偿+冻结(零 GPU)→ P1 friction Branch A 接入+单位 probe+物理验收 A-I → P2 方向性容量/λ/ladder 重标定/E 区 certificate → P3 历史零样本 friction 扫描(**GO/NO-GO 门**)→ Wave 1 S0(4 cell)→ Route A(S0)→ S1 → Route A(S1)→ Route B(pooled48+realized 分层+干预套件+holdout64+E2 held-out+render)→ RQ3 终裁+RQ4 耦合分析+shadow critic → Wave 2a(eval-time 监督 gate,默认做)→ Wave 2b(Bernoulli-gate PPO,条件:2a 有选择性且预算允许)→ final analysis+memory+ledger+最终报告。

## 5. 预案(直接执行不请示,除 F2)

- **F1** friction 数值不稳:参数域收缩一次;仍不稳 → `V24_FRICTION_NUMERICALLY_UNSTABLE` 停轮收尾。
- **F2** Phase 3 全域无 mechanics 退化 → `V24_FRICTION_AXIS_NONDISCRIMINATIVE`,停训练波,写报告**等 owner**(唯一请示点;P0 posthoc/RQ4 测量类交付照常完成)。
- **F3** E1 分母不足:marginal-E1 pilot 一次(4 cell 短程);仍不足 → typed 关闭 science wave。
- **F4** 训练崩溃:首个 optimizer 更新前允许 1 次同配置重启;有进展后崩溃则该 cell 终止保留 checkpoint,末尾空档补跑(`MAKEUP_RUN`)。
- **F5** sub-wave 早期系统性 bug(共性 traceback/NaN):停 sub-wave,修复+重跑对应 smoke,从头重启该 sub-wave(尚无科学数据不违反不重启纪律)。
- **F6** Wave 2a gate 无选择性:关闭 Wave 2,不 retune 重试,typed 记录。
- 不可越过:NaN/能量注入/摩擦符号错误/身份腐坏/staged-reset 腐坏/missing→0/E2 进训练/hidden control/事后改阈值。

## 6. Coding 风格与流程规则(用户指令,必须遵守)

- **fail-fast**:IsaacLab 相关代码禁止为"稳健性"加不必要保护/fallback 强行让仿真跑下去;让问题在运行中暴露。
- **禁止过度审计**:不反复 review;严格控制编译/diff/路径检查次数;先证明操作路径、先实现功能;护栏/回归/兼容性测试只在功能确认或问题实际出现后补(本 prompt 与 R1 明确要求的测试除外:P1 物理验收、RP0/gate 契约测试、per-code-path smoke——这些是科学有效性前置)。
- 不是安全攻防项目:**禁止禁止禁止过度防御**;不为基本不可能的 case 写防御;rubric 不过度机械化。
- **禁止写哈希/SHA256**:身份记录 = git commit + 路径 + Hydra saved resolved config。
- 等待纪律按 §3(梯度短检 → 长 sleep);等待期间可并行准备下游分析/eval 代码。
- 工具调用尽量批量并行,节省 token。
- 上下文压缩重启时:不重复回应历史引导,对照 memory 与 R1/进度文件接最新进度继续。
- 不 push;本地 commit;plan/memory 随节点同步。

## 7. 开始

顺序:读 memory/ledger → 读 R1 与 v23 final adjudication → 建 `memory/a2-piper/base-v24-friction-force-boundary/` entry 骨架 → P0.1 单位契约与 posthoc 起步。从现在起你对 v24 全阶段负责,直到最终报告落盘。
