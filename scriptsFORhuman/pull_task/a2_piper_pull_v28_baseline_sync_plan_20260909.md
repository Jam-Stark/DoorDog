# Pull v28 新 baseline 同步计划：共享 C_T，在 m5 重建双侧 unlatch→opening

创建：2026-09-09 HKT；修订：2026-09-13 HKT。
修改：-codex planner；依据：-owner 要求更新 pull 同步 plan 并交付 m5 Codex team 启动 prompt。
状态：`BLOCKED_G0_INFRA_REPAIR_LIMIT`。P2 18条诊断已封存；S1–S8已应用。PG1/2/3/5与PG7有界证据通过，但G0 PPO因flat robot引用断裂构造LSTM(0,256)在batch1前失败。两次G0 harness修复额度已用完，第三次修复未应用，PA未运行。见pull_v28/G0_CLOSURE_20260913.md及OPENING_CLOSURE_20260913.md；下列原合同不改门、不自动扩额。

执行仓库：m5（`baoquanc@m5.precognition.team`，主机名 `ai-precog-machine5`）的 `/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0`，分支 `codex/a2-piper-pull-v0-20260803`。
canonical：pull 仓库 `scriptsFORhuman/pull_task/a2_piper_pull_v28_baseline_sync_plan_20260909.md`；主线镜像：`scriptsFORhuman/pull_v28_alignment/`。
本次决策记录：[a2_piper_pull_v28_decision_log_20260913.md](a2_piper_pull_v28_decision_log_20260913.md)。
主线输入：主线 v28 plan、D017/D030/D034–D040、当前 MERGED/robot YAML/rig 与 G0 evidence；在 m5 的 `scriptsFORhuman/pull_v28/mainline_reference/20260913/` 按交付 manifest 路由。该目录是参考输入，不能直接当成已生效的 pull 实现。

本文件定义 pull 本轮合同。Owner 指令优先；当前 source/resolved config/runtime 用于判断实际行为，不一致时记录实现差距并同步已批准内容。只继承下列 S1–S8 及明确列出的共享决定，不再使用“主线全部 ADR 自动约束 pull”的旧表述。原 v7/P2 原文与 receipts 保留历史，不从其旧 C_S1、资产门 A 或共享层禁令重开被本方案取代的分支。

## 0. 目标、范围与完成点

本轮闭环为 **P2 诊断封存 → pull G0 → Wave P-A（三 scratch seed）→ opening baseline closure**。在共享 MERGED、140 mm/38.76° 塔架、reset `[0,0.10,-0.10,0,-0.415,1.57]`、D17 累积目标夹紧及 camera-aware bundle 下，重建双侧 unlatch→opening，记录 release margin、相机运动和塔架接触。

pull 从 Stage3→4 起保留自己的物理与控制语义：Stage4 子阶段 A–D、E4–E7、10 项 release-ready、clean release、send-past-body、tensile proof。E6/E7 如出现则报告，但本轮不保证完整通行，也不授予 Teacher/Student 资格。P3–P5 是 closure 后重新立项的后续工作，未冻结矩阵和预算，不自动接着训练。

本轮不复制主线 K scaffold-decay、A_S284/target_stage=5、D039 主/备候选与 exact128 DEV/CONF；不复制主线强制 G1、4096 env 或 36,500 budget。pull 当前基线的 penalty curriculum=false、driver=null 保留。

C_T 是已批准的仿真建模/控制选择，不是已由实机测量唯一确定的事实。base 单/双相机、最终光学/CAD/Student 传感合同与安装件交换保留到 C_S/G2；不因这些待办或 X24 随机校准未完成阻塞当前集成。

## 1. m5 当前事实（2026-09-13 01:13–01:20 HKT，只读核对）

- Git 分支如上；最近已提交主题仍为 `feat(pull-v26): finish continuation and record E7 results`（2026-09-08）。v7/P2 与 memory 有未提交改动，必须保留。
- T_S1/T_S2/C_S2 的 `logs_rl/a2_piper_pull_v7/p2_20260909/<CELL>/runtime_result.json` 均记录 `child_returncode=0`；各自 step10500 checkpoint 存在。进程完成不等于 P2 结论成立。
- `logs_eval/a2_piper_pull_v7/p2_20260909/` 为空，没有 P2_RESULTS/closure；三份 `.ai/runtime/runs/pull_v7_p2_<cell>_20260909/RUN_RECEIPT.json` 仍为旧 `RUNNING`，C_S1 为 `DECLARED`。本次未 finalize 或确认这些事件。
- m5 尚无本计划、MERGED 资产、`a2_piper_vpiper.yaml`、pull_v28 执行链或 pull-v28 memory。本次交付后以 manifest/receipt 区分“已接收”与“已集成”。
- GPU0 有两个外部 compute 进程，约16 GB占用；GPU1/2/3分别约24.1/23.5/24.1 GB空闲，未见本任务训练/评估进程。只有一个无关 tmux 会话。此为快照，launch 重新读取一次实际资源，GPU0不在本轮授权内。
- `/home/baoquanc/anaconda3/envs/isaaclab/bin/python` 存在；m5 已采用项目 v1.4 workflow，是普通 Git checkout，沿用其现有 hooks，不能照搬主线 linked-worktree 的 hooks 安装步骤。m5 当前未安装 rg，可用 Python/pathlib 或 grep，不为此安装依赖。
- P_S2 的真实继承输入是 `logs_rl/a2_piper_pull_v26_8_backbone/pull_v26_8_backbone_20260905_natural1_r2/wave2/train/P_S2/resolved_config.yaml`：1024 env、completion_stage=5、staged reset `[0.5,0.1,0.1,0.1,0.1,0.1]`、curriculum=false、driver=null。源码 `pull_v26_8_backbone_common.yaml` 表面仍有2048/4000，不能直接当本轮 resolved 配方。
- 主线、GPU1本地 pull worktree 与 m5 不是同一运行环境；本机 mirror 的旧状态不能替代 m5。主线 G0 PASS 只作为输入依据，pull G0 仍需自己的窄运行证据。

## 2. S1–S8 共享清单与交付方法

参考输入目录 `scriptsFORhuman/pull_v28/mainline_reference/20260913/files/` 保持主线相对路径；清单见同级 `SHARED_INPUTS_MANIFEST.json`。S1/S2/rig 采用文件内容直接比较；记录来源、路径、大小及差异，不生成摘要校验文件。历史快照、资产和 checkpoint 不重新生成、不覆盖。

| ID | 同步项 | pull 应用方式与证据 |
|---|---|---|
| S1 | `gr00t/rl/data/robots/a2_piper_v28_merged_20260909/`：MERGED、28 native bodies/20活动关节、独立腕机 tower、140 mm/38.76°、trunk base布局并集、URDF/USD及相对依赖 | 从已交付运行资产文件逐个复制到 pull 活动路径，不在 m5 重新生成资产。执行者做一次内容比对和本机body/joint读回；主线导入证据不是pull运行证明 |
| S2 | `gr00t/rl/config/robot/A2_Piper/a2_piper_vpiper.yaml` | 同内容复制后显式选择此robot组；按真实pull compose检查robot字段、body按名称映射及contact sensor计数。不能给保留的P2旧配置换robot |
| S3 | reset/观测零点/动作默认角 `[0,0.10,-0.10,0,-0.415,1.57]` | 随S2生效，Stage0/5锚点等由真实调用链读取。物理关节限位和动作顺序保持；不另拆默认角兼容层 |
| S4 | D17 `delta_action_clamp_to_dof_limits=true` | 移植实际累积目标夹紧语义：在臂六关节物理限位内约束目标，观测中的累积动作与执行值一致。参考主线`delta_action_base.py`，只移植所需差异；不用D2 reward代替结构修改 |
| S5 | 腕部运动、独立tower接触、释放后回位三个bundle组成部分 | 按函数与配置字段移植，保留§3的pull权重/事件门控；不得整文件覆盖已分叉的base/env类 |
| S6 | 当前rig `U3_F39_H140`，相机/朝向/tower字段及投影/归约语义 | 使用资产的`config/camera_rig.json`与主线名义rig参考。保留pull K5/D/E4–E7、4A/4B、margin/overshoot；适配pull事件映射，不导入主线选种reducer。无事件=null，投影/min-Z不等于无遮挡或有效深度 |
| S7 | 按已就绪格推进milestone、隔离experiment_dir、显式GPU/进程/验收记录、v1.4长等待 | 在pull现有runner/evaluator上补齐pull_v28执行链。进程完成和实验通过分开；reducer INVALID不自动停止训练；不建立通用框架或默认全面review |
| S8 | 保留现有A2_Base与主线D37步行比较口径 | 现有policy不替换；以m5同harness/同命令/同姿态的旧asset为基线做PG7。主线原始数值不能直接代替m5基线，也不声称换seed即随机校准 |

本次主线 D038 的状态/证据/独立分母原则适用于 pull；D039/D040 的具体选择合同不适用。后续若需要 pull Teacher 资格、K 或备用臂，必须单独立项，不从参考文件自动启用。

## 3. pull 差异保持与本次明确项

| 项 | pull 合同 |
|---|---|
| Stage/事件 | 保留pull现行A–D、E4–E7、release-ready和tensile proof，不能替换为主线Stage4/release hinge门 |
| 腕运动权重 | 保留旧同步方案的Stage4 Wv `(0.5,0.5,0.25)`，Wr与主线固定表相同；Stage3 j6速度权重0，其他stage沿主线固定表。它们是pull设计先验，不把旧trace或短smoke当作新底座已校准；本轮不做权重扫描 |
| 释放后回位 | scale=-0.5，使用pull的持久`_a2_pull_v6_release_event`、无双指接触及既有Stage4 C/D范围。实际source在释放时进入D；不使用主线release gate，也不把单步`_a2_pull_v6_clean_release_event`当作持续回位门。事件定义不改 |
| tower接触 | 与主线相同raw定义与scale=-1，全stage；独立body与telemetry，不能塞入旧固定20体undesired-contact元组 |
| 门域/actor/obs/action | 沿P_S2真实resolved基线与当前plain actor合同，旧actor/critic记为133/138、action19；执行者核对实际compose，不照抄过时135/140说明 |
| curriculum/reset | 不加主线K；固定原pull staged reset比例，现有v6/v6.1 bank关闭；natural eval关闭staged reset |
| 训练规模 | PA_S1/PA_S2/PA_S3全部scratch、1024env、6000 batches，保持三seed分母；不能用warm替换第三格 |
| 可选warm probe | 默认NOT_RUN；Owner另行要求时可在预留500内作迁移诊断，结果单列，不自动追加warm长臂或替换PA_S3；没有主线G1的强制STOP路由 |
| 资格/渲染 | 本轮只做pull exact64 natural与opening/margin结果，不做Teacher exact128 DEV/CONF或Student渲染。相机运动阈值为report-only；最终光学仍是G2问题 |

## 4. P2 诊断封存：先完成旧配方评估

已有入口（从m5项目根执行，实际参数以当前脚本为准）：

```bash
bash scriptsFORhuman/pull_v7/eval_p2_cell.sh GPU CELL STEP P2_TRAIN_ROOT EVAL_ROOT
python scriptsFORhuman/pull_v7/analyze_p2.py --eval-root MILESTONE_ROOT --step STEP --cells T_S1 T_S2 C_S2
```

`P2_TRAIN_ROOT=logs_rl/a2_piper_pull_v7/p2_20260909`；`EVAL_ROOT=logs_eval/a2_piper_pull_v7/p2_20260909`。T_S1/T_S2/C_S2的9500/10000/10500各双侧exact64，共18条lane。只补实际缺失项；不重跑三格训练、不补C_S1、不触发旧v7 §4.5的D2 scale重试或资产门A的另一个迁移矩阵。

P2期间保持其旧asset、source、checkpoint邻接配置与自然评估合同。先封存这18条lane，再将D17/S2/S5等改动应用到活动共享路径；等待期间可准备文档和独立的新调度文件，不能让新baseline改动污染旧P2读数。

修复真实的eval路径/接线缺陷可自主进行，不能改D2、门或样本口径。输出各step的P2中介和保留能力，并写`P2_CLOSURE_20260913.md`（实际完成日期可另取），保留旧失败与无效尝试。三份legacy receipt只能按已完成的实际后续处理收口，不能以现有RUNNING或旧PASS推断实验结论；旧supervisor活动任务不迁移。

P2只作为诊断封存，其结果不路由pull v28。D17替代D2作为本轮动作修正；v28配置不含D2 scale，历史D2源码/配置继续只服务旧证据复现。

## 5. pull G0：最小运行证明

PG1–PG8是验收项目，不要求分别构建八套测试；合并同一构造/smoke能覆盖的检查。先实现，再做一次相匹配的CPU/运行证明；不自动新增永久测试套件、变异/兼容测试或重复全仓审阅。

| ID | 内容 | 本轮证据 |
|---|---|---|
| PG1 | S1/S2直接内容比对、URDF/USD相对路径、28 bodies/20 joints、按名body/dof/contact映射 | 主线交付与m5静态读回；不能按旧30/31体列表推断 |
| PG2 | reset/动作/观测锚点与D17实际目标限位语义 | 相关CPU计算与下述smoke；不新增默认姿态fallback |
| PG3 | S5固定权重、tower索引、pull持久释放事件门控与S6字段映射 | 单次有界计算/实际日志；没有晚阶段事件不填假值 |
| PG4 | `pull_v28_common.yaml`以P_S2真实resolved合同扁平化；差异只含已登记asset/robot/姿态/夹紧/bundle/telemetry/seed/预算/输出 | 一次compose差异说明；checkpoint=null/full、1024/6000、原reset/无K必须可追踪 |
| PG5 | 新asset下pull LEFT镜像目标仍为既有180°关系，RIGHT维持本侧几何定义 | 复用原G1目标帧读回口径，不把新旧asset完整行为逐位相等作为要求 |
| PG6 | 新配方256env×5batch PPO及其full-checkpoint双侧natural评估接线；零指令窗口trunk/arm_body0..6/tower接触<1N、body数与reward日志 | 一次smoke及配套小样本评估；仅有Stage0/null不证明opening或晚阶段事件 |
| PG7 | 当前A2_Base在m5新旧asset上的步行比较 | 下述D37预先固定口径；失败保留原始值交Owner，不事后改门 |
| PG8 | receipt、active-cell watcher、milestone reducer/readout与endpoint closure路径 | 用上述真实小运行串起链路；正式claim仍由规定natural评估给出 |

**PG7 / D37口径**：复用主线已交付的步行harness及命令/姿态定义，在m5以相同姿态/命令分别运行旧asset与MERGED，三种姿态为新默认、Stage1 hold、类Stage2，各64env。可以复用m5已有完全匹配的原始对照，不混用不同姿态或主机读数。命令轴p50≤1.15×baseline；零指令耦合轴p50≤max(1.15×baseline,CAP)，CAP vx/vy=0.1m/s、yaw=0.1rad/s、pitch=0.05rad、roll=0.04rad；全部轴p95≤1.15×baseline；0/64摔倒、vx@0.5 slope≥baseline−0.05。此次接收前已冻结口径，不套用已废弃的纯p50比例门。

主线D37两次事后修订历史保持披露；其seed282只是确定性复现，不能关闭X24。pull不复制“再换seed确认”的生产前置，不静默修改冻结harness；真实随机校准仍在下一次asset/A2_Base立项时复核。当前PG7只回答本机批准工程比较。

## 6. Wave P-A：三 scratch seed重建

- PA_S1/PA_S2/PA_S3，训练seed1/2/3。使用pull实际侧别键`a2_door_open_lr_permutation_seed`对应训练seed，不添加无人读取的主线同名近似键。
- checkpoint=null、full、auto_load_latest=false、1024env、6000batches、save250；1500/3000/4500/6000各双侧exact64 natural，共24条lane。自然评估关闭staged reset、curriculum和driver，first-episode/exact64/integrity沿pull既有口径。
- 原三seed在6000的结果单独判：每个seed必须两侧K5/D/E4/E5≥60/64且tower接触episode>5N的计数≤2/64/侧；≥2/3为`PULL_V28_OPENING_ESTABLISHED`，1/3为`PULL_V28_OPENING_UNSTABLE`，0/3为`PULL_V28_OPENING_NOT_ESTABLISHED`。同时报告精确k/3，不把2/3写成3/3。缺失/INVALID不填0、不算完整终点。
- 历史过门checkpoint、最早opening时点和逐侧中介另列，不覆盖6000标签，也不在本轮授予Teacher资格或自动替换候选。
- 保留`MARGIN_TRAP_RESOLVED/PERSISTS`原观测定义：E5后release margin≥0.07的步份额>0，且逐关节target overshoot中位=0时为RESOLVED，否则PERSISTS。无E5事件则NOT_OBSERVED/null，不能据无样本判已解决。该标签不等于10项ready同时成立、稳定release或E6/E7通过。
- 相机行为`CAMERA_MET/PARTIAL/UNMET`按已有可用事件报告；无样本不硬判。RIGHT失败伴随tower接触只提出E_T干涉的待区分解释，不证明几何无解；提交X01硬件决策请求，不追加预算或改包络。

## 7. 后续P3–P5：回收议题，不是本轮自动续训

Wave P-A closure后，无论成功失败，planner复核：双侧opening是否建立、哪些seed/时点可供后续研究、margin与ready剩余缺项、send-past-body/clearance/handle-Y/hinge速度、释放后时间预算与E6/E7。只有另行批准addendum、处理变量/对照/预算后才能启动P-B/P3–P5。

N03 push/pull合一只登记共享合同与各侧实际能力，不因完成输入同步就声称合一。N01/N02可在同一closure窗口提交与pull有关的恢复/传感/门域需求，不自动运行主线方法实验。

## 8. 自主权限与停止边界

执行team收到Owner启动prompt后，可自主完成本轮S1–S8必要代码/配置/调度修复、P2缺失评估、G0、三seedP-A、各milestone与closure；条件满足的阶段转换通知后继续，不逐项等待审批。

- GPU只用1/2/3；训练启动时≥20GB空闲且无外部compute进程。P2评估可在空闲授权卡并行；P-A评估仅在实际余量≥5GB且不会挤占18GB级训练格时同卡，否则等一格结束。GPU0外部进程只记录，不处置。
- policy读数前的infra/harness失败，在合同不变下自主修复，最多2次/格，使用新attempt并记录；policy读数后的非零退出停该格、其余继续，不自动重跑。
- reducer INVALID只停止对应评估，不自动杀训练；进程exit0、checkpoint存在、评估完成与实验结论分开。
- G0真实接触/目标映射/PG7门失败、改事件/ready/stage/reward/门值、超预算、asset几何/质量或A2_Base变更、硬件/Teacher绑定/push等，必须交Owner；不设置新默认长臂来绕过失败。
- 本地commit节点保持：P2 closure、pull G0完成、P-A endpoint、最终closure；是否执行以收到的Owner启动prompt明确授权为准，仅Main操作，不push。本次文档同步未commit。
- 本轮不是workflow迁移任务。m5现有v1.4可用能力直接复用，不重装hooks/插件，不改Main模型/effort或全局配置。

## 9. 预算与长等待

训练预算保持原上限：三scratch×6000=18,000 batches；可选warm probe至多500，默认不运行，总上限18,500。G0允许一组不超过32batch的接线smoke；本计划采用256env×5batch及配套小评估。P2仅补18条旧natural lane，P-A24条natural lane；本轮没有exact128资格矩阵或额外warm训练臂。

历史吞吐估计：约22s/batch，6000约37h/格，计划42h；P2两卡补评估约2h，G0约40min GPU（含本机对照会随吞吐调整）。执行者完成一次启动/稳定性检查后依据实际吞吐记录ETA与真正下一决策点，不能将此估计写成固定完成保证。

超过30分钟使用命名tmux和现有run_supervisor，固定命令、资源、输出、ETA、stop condition及已授权eval。按绝对截止恢复同一安静waiter；完成/失败/取消/真实决策点提前返回，不固定每30分钟唤醒Main或派agent反复看日志。传输层提前返回时沿用同一waiter/截止，不重置逻辑等待。不以日志静默判死锁，不把后台终端退出等同于自动唤醒保证。

legacy receipt/事件不批量迁移或确认；先核实其进程与尚缺的指定后续处理。新任务使用v1.4分离process_state/acceptance_state，只有授权evaluator的对应claim才记PASS。

## 10. 文档、输入与memory

- 本计划与同目录决策日志记录V28P-D001起的pull具体决定，并引用主线D号；不要对主线全部ADR机械加P或覆盖原记录。
- 新建`memory/a2-piper/pull-v28-baseline-sync/{description,TODO,DONE}.md`，作为本轮入口；`pull-lr-full-stage`保留原v7/P2证据，不整表删除或重分类其历史日志。
- 运行输出统一在`logs_rl/a2_piper_pull_v28/pull_v28_baseline_sync_20260913/`、`logs_eval/a2_piper_pull_v28/pull_v28_baseline_sync_20260913/`及项目runtime receipts；每milestone先写真实decision/归约JSON，再写readout。
- closure包含S1–S8来源/内容比对、实际resolved差异、k/3终点、历史checkpoint、中介/null、进程/eval状态、未运行项与后续议题。主线G0与pull运行证据分开。
- 参考输入清单只包含明确需要的资产、YAML、rig、源码参考和G0材料，不含训练checkpoint、凭据或整个工作树。A2_Base仍使用m5已有policy；其同源性由输入核对记录，不在本次替换。

## 11. 本次变更与旧规则替代关系

详见同目录决策日志：V28P-D001明确当前scope与主线继承边界；D002固定C_T/rig/D17；D003采用D37本机工程门与proxy/null边界；D004固定pull权重/释放事件/无K；D005保留三个scratch分母，warm不替换PA_S3；D006更新v1.4等待、窄验证与输入交付。

旧同步plan中的纯p50比例门、U3_F45_B15、默认强制测试清单、摘要校验要求，以及warm替换PA_S3的分支已被本修订取代；不是运行后改门。P2旧C_S1补跑、D2下一步及独立资产门A不在本轮执行范围。主线D039/D040的具体candidate/DEVCONF保持主线专用。

本次SSH读取、plan/memory与输入交付不构成任何pull G0、opening或硬件PASS。执行团队应在真实完成对应步骤后更新IMPLEMENTATION_PENDING，不因文件已收到而标为已实现。
