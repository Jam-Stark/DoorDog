# v28 本地更新审计：Pro 回传后的核对与 finalize 草案

落盘：2026-09-12 15:45 HKT。作者：本地 Codex。

本文件将已向 Owner 回复的只读核对、建议取舍及随后对“v28 是否合理/是否稳定产出 Teacher”的澄清整理为持久文档。它是 **Pro 回传后的本地解析**，不冒充 Pro 前的独立审计，也不回写 Pro 的固定初判 A。

Pro 原文见 [FULL_REVIEW.md](FULL_REVIEW.md)。审计基准为 `84358588e2da12a9fae5748cd9da39ac2d9f5a6c`，G0 worker 父节点为 `8811c484729b1e9be017c30dcf46d922d1ad5f52`。建议均未应用；本次落盘没有增加实验或代码修改权限。

## 1. 本地版本与新进展核对

上一轮只读核对记录如下，本次落盘再次确认分支与 HEAD 未变化：

- Worktree：`/home/baoquanc/workspace/DoorDog-A2_Piper`；分支 `A2_Piper`；HEAD `8811c484729b1e9be017c30dcf46d922d1ad5f52`。
- 当前 HEAD 是审计 commit 的直接父节点；当前分支没有后续独有提交。两者的 61 文件差异来自审计交接补充的上下文，不能解释为执行代码回退。
- 当时暂存区为空；7 个已跟踪修改、75 个删除、107 个未跟踪展示条目（含目录）。这些计数是核对时快照，不是文档落盘后的实时计数。
- 核对的 73 个相关本地文件与审计 commit 内容一致；相关 v28 执行代码没有已提交或未提交的新变化。这不是对全部 source-copy 树和二进制的一致性认证。
- 当前所见运行记录仍为 `G0_PASSED_FIRST_LOCAL_COMMIT_COMPLETED`，未找到新增 G1/Wave A/B 决策记录。本次未发现取代 Pro 审计基准的新运行进展；未扫描实时进程或 GPU。

当前状态应从 [acceptance](../../../v28/a2_piper_base_v28_g0_acceptance_20260912.json)、[runtime decision](../../../v28/runtime_logs/v28_camera_aware_rebaseline_20260909/g0_decision.json) 及后续新记录读取。不能把本文件的“G1 未启动”当作未来永久事实。

## 2. 独立初判与交叉后的新增意见分开保留

- 终点标签问题是 Pro **A/P10** 在读取第二包前的独立发现。
- Wave B 否定范围、已关闭待办、备用臂及 reset 授权边界，分别是 **B-01、B-02、B-03** 的后续增补。
- 本地核对不将 B 的意见倒灌为 A；原始 A/B/C/D 保留在 FULL_REVIEW.md 中。

## 3. 当前取舍

**建议保留现行实验合同，优先澄清终点可靠性与历史候选的关系。** 以下不是执行命令。

| 意见 | 本地判定 | 核对依据与处理 |
|---|---|---|
| G0 的狭义准入和 PPO/eval 接线通过 | 当前仍成立 | acceptance 与过程记录一致；直接读取的左右各 64 条 episode records 全为 Stage0，每侧 26 个字段、7 个晚阶段字段为 null |
| 将旧 STOP、未运行 PPO 当作当前状态 | 已被后续证据取代，且发生在 Pro 审计之前 | Pro 已识别这一时点变化；保留原 FAIL/D36/D37 的历史，不继续将其当作当前阻塞 |
| 282 是确定性数值复现，X24 保持 OPEN | 当前仍成立 | 现有 seed_exposure_audit 披露冻结 harness 无新的随机消费者；不将新进程或 seed 标签当随机校准 |
| 已验证晚阶段行为、Teacher 资格、真实视觉或硬件能力 | 证据不足 | 短策略仅到 Stage0；G1/Wave A/B 无结果。当前资料不支持这些外推，也不支持据短训练否定完整学习路线 |
| `select_wave_a` 混合终点可靠性和历史候选标签 | 当前仍成立，静态问题 | 历史存在候选但 6000 为 0/3 时返回 UNSTABLE，与 plan 的终点定义不一致；尚无对应运行事故 |
| Wave B 可以否定全部三 seed/所有时点 | 不采纳该外推 | 当前合同只对选中的 seed 及实际 checkpoint 做资格确认；未评估对象不在否定范围内 |
| G1 失败证明 scratch 不可行 | 不采纳该解释 | WARM_FAIL 的既有 STOP 是 Owner 成本复议点；科学结论只到指定 warm 迁移和预算 |
| A_S284 自动拥有候选资格、计入原三 seed 或证明 driver 因果收益 | 资格证据不足，其余外推不采纳 | 当前选种只列 281–283；A284 同时改 seed 和 driver，不能称同 seed 单因素对照 |
| X25 需要重新增加承接条目 | 无需重复修改 | X25/N10 已有 Wave A Stage2/3 位姿不稳的触发，并与 X19 关联 |
| 默认增加风险梯、8000-batch、随机校准、长臂、改 staged reset 或全面测试/workflow | 不采纳默认扩展 | 未有新证据与授权支持这些动作；也不凭“收缩”建议自动取消已批准的条件路由 |

接线证据：[telemetry_validation.json](../../../v28/runtime_logs/v28_camera_aware_rebaseline_20260909/resume_20260911/telemetry_validation.json)；随机暴露记录：[seed_exposure_audit.json](../../../v28/runtime_logs/v28_camera_aware_rebaseline_20260909/resume_20260911/d37/seed_exposure_audit.json)。其中二进制图与完整 trace 的原核查声明，不等于本次另行重验。

## 4. M1–M5 最小修订草案

全部尚未应用。任何实际落笔需要后续明确授权；涉及代码、候选或实验合同的变化另列，不能借文档整理一并执行。

| 项目／文件 | 当前问题 | 建议文本或最小改动 | 依据 | 实际应用所需授权 |
|---|---|---|---|---|
| M1：`scriptsFORhuman/v28/a2_piper_base_v28_plan_20260909.md:4`；`a2_piper_base_v28_g0_resume_readout_20260912.md:1` | plan 开头仍为 RESUMED；readout 开头为 STOP，末尾仍写等待首 commit。memory 首页已正确 | 顶部补：“当前状态以 acceptance 和 runtime decision 为准：G0 准入及首 commit 完成；当前记录 G1 未启动。以下 STOP/D36/D37 为历史。G0 不涵盖随机校准、Teacher 资格或硬件验收。”不重写历史段落 | acceptance、g0_decision、first_commit receipt | 文档更新；不需重新裁决 G0 |
| M2：`scriptsFORhuman/v28/v28_reduce.py:155`；plan §8.2 | 历史有候选而 endpoint 0/3 时，代码返回 UNSTABLE | 分列“6000 过门数及可靠性标签”“历史候选”“selected seed/milestone”“实际 Wave B 对象”。终点标签澄清不得静默删除历史候选或改变 Wave B 开关 | A/P10；当前源码及 plan 终点定义 | 文档／代码修改；候选身份、门值、替补或路由变化须单独决定 |
| M3：plan §8.1/§8.3；`v28_contract.py:49`；`base_v28_common.yaml:83` | G1 解释、备用资格和固定 reset 容易混为执行建议 | “WARM_FAIL 保留 STOP 交 Owner，只否定指定 warm 迁移在规定预算内未过门。A284 单列，不计入原三 seed，不称同 seed 因果对照。无新决定不扩选种；staged reset 保持 `[0.5,0.1,0.1,0.1,0.1,0.1]`。”保留既有 PASS/PARTIAL/FAIL 路由 | A/P09、B-03；配置、cell 和 selection 实现 | 解释文本更新；取消 STOP、改比例、候选资格、并行或长臂预算需另授权 |
| M4：`scriptsFORhuman/v28/v28_camera_metrics.py:289`；plan §8.2 硬件反馈分支 | 投影/采样代理与几何不可行结论被混淆 | “无事件指标为 null；handle_in_wrist_* 为名义投影/min-Z 代理。失败记为‘本配方与预算下未建立，E_T 干涉为待区分解释’，不证明不存在可行抓握轨迹。”保持原 C3 档案、触发、门值和 G2 时点 | A/P07–P08；project/reduce 的实际定义 | 文档与结论口径更新；不扩实验或硬件动作 |
| M5：`scriptsFORhuman/a2_piper_longterm_TODO.md:81`；deferred X05 | N01 等待已关闭 v27 的 PROMISING；N02/未收敛门域缺回收窗口 | “v28 closure 无论成功失败，都触发 planner 复核。N01 先决定是否重新立项 pilot、定义扰动/loss，再按新 pilot 证据考虑多 seed；N02 复核传感、可辨识性与适用门域，明确继续／延期／关闭。” | A/P11；v27 closure 与当前待办 | 文档更新；新 pilot／方法实验以后另行授权 |
| M5：deferred X24/X25；长期 N09/N10 | X24 的入场条件仍指已经完成的 282；X25 已落实 | X24 改为“下次 asset/A2_Base 变更立项时复核真实随机校准需求；具体校准另行授权”。这是提醒，不是无校准不得继续的新门。X25 保留既有 Stage2/3 位姿不稳触发，与 X19 联合分析 | 282 记录、N09/N10、v28 TODO | X24 文档更新；实际校准另批。X25 保留即可 |
| M5：deferred X17/X18、X07/X09；长期 E 节 X04/X08；novelty description | 重号、陈旧阶段/rig、已关闭仍待办、D30 仍有 PROPOSED 表述 | 合并同义 X17；给 CAD 路线唯一编号并一次更新活跃引用，保留历史来源说明，不建常驻 alias 机制。X07转正确 CAD/G2 时点；X09指向 C_S 最终 rig并注明当前名义 rig；X04/X08转已有 CLOSED记录；D30标已批准 | 当前登记、接受决定与 CLOSED 记录 | 仅文档整理；不重做关节修改/worktree删除，也不提前决定最终相机布局 |

相关文件：[plan](../../../v28/a2_piper_base_v28_plan_20260909.md)、[readout](../../../v28/a2_piper_base_v28_g0_resume_readout_20260912.md)、[reducer](../../../v28/v28_reduce.py)、[deferred register](../../../v28/a2_piper_base_v28_deferred_register.md)、[长期 TODO](../../../a2_piper_longterm_TODO.md)、[novelty memory](../../../../memory/a2-piper/novelty-research/description.md)。

## 5. 关于“v28 是否合理、能否稳定得到 Teacher”的澄清

v28 主线基本合理，可以保留。准确说是 **尚未证明能稳定产出合格 Teacher**，不是已经证明它不能。

- 验证新基线：三 seed 检查可达性，再对固定候选做资格确认；允许最终没有合格 Teacher，但得到明确的成功／失败结论。
- 尽量取得可用 Teacher：当前“最早 reach，再取最小 seed”未必最适合这个目标，可能略过较晚才表现好的候选。
- 三 seed 都通过可达性门，也不等于三 seed 都是合格 Teacher；当前 Wave B 只确认选中的候选。

本地建议继续保留“固定最早 reach 候选，接受本轮可能不产出 Teacher”的现行目标。如果 Owner 的硬性交付已经转为“本轮必须拿到可蒸馏 Teacher”，需要在查看 v28 结果前明确新的选择／替补合同。改变选种也不是对训练成功的保证。本次问答与落盘均未改变当前选择规则。

## 6. Owner 现在与条件触发后分别需要决定什么

现在的实质取舍是是否保持现行固定候选目标。默认保持；若要优先提高取得 qualified Teacher 的机会，才需另行决定选择／替补范围。文档草案的实际应用也留待后续 finalize 授权。

条件触发后：

- G1 失败时依既有 STOP 决定继续、停止或重新立项，不把它解释为 scratch 已被否定。
- A_S284 若要取得选种或 DEV/CONF 资格，应在启动/查看结果前明确；否则保持单列备用定位，原三 seed 分母不变。
- warm 长臂、A2_Base opt-in、额外预算与新方法实验，按各自条件和授权处理，不全部变为本轮必做。

## 7. 证据限制与未执行事项

完整 trace 的独立逐行核查、完整 source snapshot/checkpoint/TorchScript 一致性、实时环境与 GPU、硬件以及其他 worktree 最新状态，仍属 **LOCAL_CHECK_NEEDED**。只读已有必要材料能解决的才核对，不因这些未核事项、X24 OPEN 或后移 G2 增加当前生产 STOP。

上一轮解析仅在回复中交付，没有修改文件或执行实验。本次新增的是本文件、Pro 文档归档、索引及对应 memory 路由；重复 ZIP 按 Owner 后续要求删除。没有应用 M1–M5，没有修改 v28 plan/源码/配置/门值/选择规则，没有训练、评估、Teacher/G7、硬件、commit/push 或 Drive 操作。
