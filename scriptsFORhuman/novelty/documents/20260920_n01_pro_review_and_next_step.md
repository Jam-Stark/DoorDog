# N01 Pro回包：研究结论、待定选择与最小下一步

2026-09-20 HKT；作者：Codex Main。状态：**设计讨论，未批准实施/实验**。证据等级：INSPECTED。Owner本轮只授权附件归档、解释、定向核对及讨论区维护；原话见[本次请求](../conversations/20260920_codex_n01_pro_return_request.md)。

后续路由（2026-09-20 16:07 HKT）：N01 planner已交付[局部恢复与能力传递最小设计](20260920_n01_minimal_recovery_transfer_design.md)，其中L0/L1、共享stage-blind Teacher/Student接口及按需要扩展记忆均为待Owner裁定的推荐。本页保留回包时的研究记录，不将后续推荐回写成Pro结论或实施授权。

原ZIP与全部六份Pro文件保存在[回包目录](../../pro_reviews/v29/20260920_153418__N01_recovery_transfer/README.md)。[一页解释](../../pro_reviews/v29/20260920_153418__N01_recovery_transfer/OWNER_ONE_PAGE.md)回答四个核心问题；具体source/config定位、证据分类和文献核对深度以[本地定向核对](../../pro_reviews/v29/20260920_153418__N01_recovery_transfer/LOCAL_RECONCILIATION.md)为准，本页只维护研究结论与后续选择。

## 1. Pro的核心回答

- **哪里恢复：** 优先处理正常释放前的捕获失败和仍需控门时的真实失抓，区分接触闪断、正常释放、可以直接通过及无可行恢复的情况。
- **退回哪里：** 退到能继续完成原任务的物理条件。由近到远为原地闭合、实时pregrasp、base重新站位、重观察；能直接通过时继续通过，无可行落点/时间时结束尝试。A/C/M/P四类目标集合并不要求四个网络。
- **Teacher怎样学：** 名义任务与有效失败课程结合，扰动要读回物理结果；同一episode中恢复后完成原任务。名义续训对照要匹配额外训练量，恢复退边不能刷新时间或重复取得进展奖励。
- **Student怎样得到能力：** 受扰Teacher示范作为起步，关键数据来自Student实际执行的闭环，Teacher沿其真实历史在线给标签；事件序列采样与循环状态要一致。Teacher接管成绩不能混作Student自主成绩。

这些是值得继续的研究建议，尚未证明局部恢复可行、能力能传递或构成新的学术贡献。课程比例、扰动长度、loss unroll与采样配额均为Pro待校准提案。

## 2. 本次核对改变了哪些理解

现有DAgger可以让Student执行并实时问Teacher，但默认Teacher执行比例为1.0，按固定env前缀分配；当前storage按rollout更新，没有跨rollout恢复序列库。8 tick是数据窗口，Teacher/Student在线hidden按真实done reset，并不每8 tick失忆。Pro的全episode前缀重放是新增方案，不能当作整个训练栈必须先重构的证据。

Student的81D＋RGB没有Teacher的stage/contact/门真值。现有81D中的`actions`实际为19D腿动作/累计arm target/gripper，另有6D delta；它不是12D高层command。Stage0会按真值stage覆盖arm累计target。因此，Pro的stage-blind执行适配器及有效增量标签是控制接口设计，需要与数据方案一起说明并由所有相关Student对照共享。

恢复图可在Teacher训练/奖励/课程中使用特权信息；部署Student若靠同样真值切换执行器或清动作状态，单看actor输入就不能宣称部署闭合。当前实时G已经更新；困难在可达性和门继续运动后的执行条件。

恢复奖励不只涉及Stage4/5的arm-return；base重定位也会遇到Stage1停稳条件和Stage1/2前移惩罚。Pro的时间/进展分离值得讨论，但当前尚未实现。旧DAgger和C002的solver配置不同，v29 Student组合及相机输入必须在后续实施前实际resolve，不能仅换robot便默认对齐。

本次13份相关source/config与审阅分支一致。已存D056/D060是C002实现验收，不是成熟Teacher或恢复能力证明；D064只提供其对应时点的staged-training里程碑。本轮未重新审计C002、轮询运行任务或产生新实验数据。三篇一手文献只核对摘要/问题定位，其余保留Pro出处，未完成全文或新颖性审查。

## 3. 尚未定案的四组选择

| 选择 | 建议的最小起点 | 仍需planner解决 |
|---|---|---|
| 恢复范围、目标与时间奖励 | 完整C002＋B05；正常释放前；优先L0原地闭合/L1实时pregrasp | 哪些失败人口与可达条件纳入；L2/L3是否首轮不可缺；预算/进展及已有奖励怎样支持恢复 |
| Teacher能力与有效课程 | 自然失败＋能读回物理loss的短开爪扰动，先完成原任务的局部恢复 | 可用Teacher的名义能力/标签可信区域、扰动插入点；何时才需要额外Teacher adaptation |
| Student执行、信息与记忆 | 现有网络为候选；Student亲自执行，专家沿真实历史标注 | stage-blind执行/target/动作历史/监督合同；最小序列存储与hidden处理；完整prefix重放的必要性与成本；v29输入/相机组合 |
| 比较与证据 | 分开Teacher收益、Student闭环数据收益、事件采样收益及名义代价 | 最小功能操作路径和可见信号；自然起点自主成绩/接管成绩的分母；后续必要运行量与预算由Owner决定 |

完整episode snapshot库、多技能网络、全13条边、Student RL和大规模回归体系均非目前已确定的必需项。先以实际操作路径判断需要什么，避免先建设完整框架。

## 4. N01/N02接口

Owner D023把强回弹后重新伸臂、重抓把手移入N02。Pro提出释放后P→A可后续纳入N01任务层恢复；这是新的分工建议，**待Owner采纳，当前不取代D023**。N02在线适应与A2＋PiPER方向力建模的独立Pro研究仍按其原任务处理，N01本次没有取得或执行这些结果。

N01默认主底座完整C002保留B05；GPU1的v29−B05消融不能替代。GPU0/GPU1已有训练/监督/等待合同保持原样；此前GPU2/GPU3的方向规划不是本次资源或预算授权。

## 5. 建议的最小下一步

新N01 planner先依据本次核对收敛一份小范围设计：选定一个真实失抓到可达恢复落点再继续原任务的路径，写清Teacher如何学到它，以及Student如何实际经历、取得有效标签和维护记忆。给出涉及的source/config入口、必要的接口/奖励/计时变化、可运行的最小功能演示与待决定选项。

当前先完成这份设计讨论。Owner随后明确要求实施时，再制定相应WRITE_SET、执行路径与必要验证；不把本次预研转成训练队列或测试工程。新planner交接prompt由Main在最终回复提供，不落成另一个文档。
