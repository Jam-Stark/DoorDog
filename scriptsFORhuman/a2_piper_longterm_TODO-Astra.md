# A2+Piper 长期 TODO — Astra 修订提案

更新：2026-09-05。状态：PROPOSAL_FOR_OWNER_COMPARISON。

这是对 [原长期 TODO](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/a2_piper_longterm_TODO.md) 的完整当前路线修订稿，遵循 Owner 的 -Astra 后缀要求；本轮不覆盖另一方案可能同时编辑的无后缀正本。历史归档继续由原文与相应 stage memory 保存，下面替换的是“当前优先级/下一步”而不是历史实验裁定。

## A. 当前主线：可恢复交互，不再以 force-feasibility certificate 驱动立项

1. v26 收尾资格整理纳入 v27.0；W_NOT_DIFFERENT / K_REGRESSED 和未运行 Wave 2 保持原判。选出研究父策略不等于选出部署 Teacher。
2. v27 先做 LEFT 功能质量、门侧负载/摩擦分布、训练 seed 与真 scratch 可靠性；满足入口后做单次失抓恢复环 pilot。
3. 近期方法问题：同一物理 episode 内的接触失效—重抓—重入，配套恢复边界训练采样，是否优于同预算普通扰动训练？
4. 后续方向：action-conditioned history 估计有效交互状态，调整开门/持门/恢复策略。保持 force-aware 的物理问题意识，放弃用未经校准的容量代理证明“可行/不可行”。
5. coupling critic、branch PPO、body-assist 均有前置证据条件，不在 v27 主实现。

路线依据及一手文献：[Astra novelty 判断](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/a2_piper_novelty_route_20260905-Astra.md)。推拉合一、门属性估计、retry 本身已有先例，不能单独列成原创贡献。

## B. worktree 分工

| 工作区 | 当前职责 | 接口边界 |
|---|---|---|
| push 主线 | v27 功能质量、重复性、恢复机制研究 | 维护共同 obs/action/capability 语义；不向 pull 单边强加推门符号 |
| pull 训练机 | 迁移 v26 C 同构 backbone，先重建双侧 acquisition→opening | pull 的 IO/fixture/tensile 证据保留；不复制 K 负结果路线 |
| student 并行工作区 | 依据其既有授权继续工作；新 bilateral handoff 单独验收 | privileged teacher 与可部署 student 观测分开；本提案不改 G7 |

GPU 空闲/占用是运行时事实，不写成长效分配。跨机共享代码通过 Owner/受权任务传递；未传到训练机的本地文档不算远端已落实。

## C. 已排入 v27 的项目

| ID | 工作 | 验收/退出 |
|---|---|---|
| V27-00 | v26 closure 资格核对、候选开发集质量评估、独立确认集 | 可出现无合格候选；不为收尾修改 v26 阈值 |
| V27-01 | LEFT/RIGHT 功能质量对齐 | 按 crossing、接触、速度、关节驻留评价；不要求轨迹逐点镜像或都持门穿越 |
| V27-02 | 门 mass 与 hinge friction 分布收敛 | 实际写入/readback、固定训练分布与留出组合；不能声称 v26 已开 friction randomization |
| V27-03 | 3 个独立 continuation 训练 seed + 3 个真 scratch seed | 全部 seed 报告，最差侧/最差 seed；禁止只挑最好的一格 |
| V27-04 | 单次失抓后的循环技能图 pilot | 原状态机、runtime recovery、recovery+边界采样三臂；只有工程/探索证据 |
| PULL-01 | pull backbone 对齐与双侧全链路建立 | [迁移 plan](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/pull_v26_8_alignment/a2_piper_pull_backbone_plan_20260905-Astra.md)，不是 push checkpoint 直接移植 |

## D. 近期研究队列：按条件进入，不自动连跑

| ID | 候选 | 入场证据与必要对照 |
|---|---|---|
| N-01 | 循环技能图正式确认 | v27 pilot 有有效恢复且 nominal 不明显退化；3 seeds 同预算，与普通 RNN 扰动训练比较 |
| N-02 | 交互历史 latent / 在线适应 | nominal 与 recovery 已可用；固定可部署传感合同；RNN DR、latent、oracle 对照；含 episode 内参数变化 |
| N-03 | 同一 actor 的 push/pull×LEFT/RIGHT | pull 先双侧走通；共同 obs/action 语义，任务均衡采样；分别报告四格，不以平均掩盖一格失效 |
| N-04 | hold / controlled-swing 策略选择 | 两种策略均在质量规则下成立；用任务风险/回弹预测决定，不能按门重硬编码优劣 |
| N-05 | 多次打断与 Stage0/1 站位 repair | 单次恢复确认后；动态障碍、重复失抓有独立预算与恢复窗口 |

树不是正确的 retry 数据结构；采用有向循环图。side/IO 属于任务条件，历史进度、当前技能和 reset 来源分开记录。

## E. 原 LT-23 条目的新状态

| 原 ID | 新状态 | 修订后的工作定义 |
|---|---|---|
| LT-23-01 capability calibration | 保留，实机另授权 | 区分 nominal PD、实际 actuator 输出、电流/温度限制；v26 的 45N/1300/32 是仿真 capability，不是已完成实机标定 |
| LT-23-02 hinge friction | 实现基础已有；v27 收敛分布 | 复用 v24 native backend；static/dynamic/viscous、drive 上限与摩擦不是一回事 |
| LT-23-03 dynamics identification | 晋升后续主研究 N-02 | 优先预测控制相关响应与不确定性，不强求唯一恢复 m/I/k/c |
| LT-23-04 factorized actor | 暂缓 | 只有独立 credit assignment 有必要时再分 head；现有 12-D native action/LSTM 先保留 |
| LT-23-05 matched intervention | 复用已有资产，按需扩展 | 同物理状态、RNN history、随机量；区分 acute 与 chronic，不为流程完整重建一套工具 |
| LT-23-06 coupling critic | 暂缓到可校准的 shadow | 需 held-out 干预验证 interaction residual，不能用总成功标签当联动真值 |
| LT-23-07 counterfactual PPO | 远期 | LT-23-06 有独立收益后才进入；不是多加 critic 就自动改善协同 |
| LT-23-08 sparse posture gate | 降为条件工具 | 不以姿态使用率为成功；arm+planar 与额外姿态对照；不受旧 E1 对称密度门约束 |
| LT-23-09 downstream/handoff value | 并入恢复状态与质量分析 | 先物理事件和重入正确性，再考虑额外 value model；不单开 critic 工程 |
| LT-23-10 body-assist | 远期、单独授权 | 先证明受检场景下 arm+planar+posture 不足；有躯干/髋接触模型与硬件支持再做 |
| LT-23-11 student adaptation | 远期且和 student 团队协同 | 先 teacher 功能质量，后真实观测与噪声；不得泄漏仿真门参数或 side 真值 |
| LT-23-12 源码隔离/清理 | 轮间、最小切面 | 新功能用清晰模块；历史版本冻结可复评，不要求永久兼容所有旧分叉，更不整文件覆盖 pull |
| LT-23-13 anti-rebound re-contact | 并入 N-04/N-05 | 区分计划松手后再接触与非计划失抓，不把身体撞门替代抓握恢复 |

## F. 当前不采纳的提法

- “再加一个 critic 给 roll/pitch 打分”作为独立 novelty：缺乏可识别监督，也未证明有能力瓶颈。
- 奖励非零姿态/强行重门必倾斜：会制造外观，不是证明物理收益。
- 只按 LEFT/RIGHT 分树、只把 push/pull 合并、只增加 RNN/辨识辅助 loss：可做工程与基线，不单独声称原创。
- “10N 手指天然保证 pull 是 finger-limited”：旧设定不能当硬件真值；先落实共同 capability 再判断瓶颈。
- “20–100Nm 零样本无退化证明 arm 力矩够用”：旧探针只在被选短窗上缺乏判别力，不能外推全部轨迹。
- 以策略失败定义极限门、以同一策略的 E1 密度作为所有方法准入：会把假设与测量选择混在一起。

## G. 继续保留的工程/下游挂账

- [ ] bilateral Teacher 的 sealed confirmation、代表性渲染和部署边界；任何 G7/Student handoff 另授权。
- [ ] handle/latch 几何随机化：在四任务基本稳定之后单独扩域。
- [ ] 真实观测、视觉噪声与 Phase2 distillation；Phase3 bootstrap 以其独立项目准入为准。
- [ ] formal natural-exit receipt、trace 缺失原因、未运行项如实报告。
- [ ] 历史 v20 Route-B、v23 遗留媒体/失败证据、轮间垃圾清理仍按原 TODO 记录，不因新路线自动补跑或删除。
- [ ] Git commit/push 不自动授权；旧任务两次 commit 授权不是本阶段无限授权。

## H. 历史证据的更新说明

原 TODO 的 v16–v24 归档原地保留，不覆盖历史 typed outcomes。新增有效上下文：v25 的姿态即时力价值未决、planar 作用可测；v26 完成双侧 acquisition/scaffold 扫描，但不是全过程行为定稿。左右镜像也不再是“已整体移交 pull、push 无需关心”的事项：当前 push 已有 native bilateral 路径，两边必须共同维护语义。

v26 的门重当前为 80–120kg，handle height 0.85–0.95m；native hinge friction 关闭，普通 legged contact-friction/link-mass randomization 也未激活。后续负载研究以实际 source/config/readback 为准，不能凭旧 v24 基建存在就宣布 v26 已覆盖。[v26 common](/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/config/ablation/wbmanip/base_v26_common_scratch_lr.yaml)

原归档中的“measurement-vitals、量级锚、派生量可识别性、事件定位”继续作为证据教训；应用以解决实际问题为尺度，不扩成每轮重复的大审计门。
