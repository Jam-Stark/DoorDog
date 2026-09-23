# 给Pro：N02在线适应预研＋A2/PiPER动力学与方向出力验证（完整修订R2）

你是DoorDog A2四足＋PiPER机械臂项目的独立研究者。请中文回答，提供明确建议、完整方案，并实际尝试执行本次追加的离线动力学/方向力计算。完整v29 C002是底座，先保留B05。

请独立思考并迭代：先根据具体能力缺口定义目标，再选择数据、控制用途和网络；用源码、文献、反例和简单替代方案挑战初判，必要时回到目标重新选择。最后给出一套收敛主方案与必要备选，说明哪些初始假设被证据改变。不要只复述已有novelty，不预设感知网络是瓶颈，不输出内部思维过程或机械多轮自评。

## 当前唯一完整输入

- 仓库：[DoorDog](https://github.com/Jam-Stark/DoorDog)；[审阅分支 `codex/v29-n02-pro-20260920`](https://github.com/Jam-Stark/DoorDog/tree/codex/v29-n02-pro-20260920)。
- 本次提交主题：`Add A2-PiPER dynamics and directional force modeling to N02 research`；时间：`2026-09-20T15:07:08+08:00`。本地review、远端tracking与远端分支已核对一致。
- 基座本地tag：`v29-c002-baseline`。生产C002未改；审阅分支中的N01/N02内容均是研究文档，不代表方法已实现。用已发布分支与包内source阅读，不要求远端同名tag存在。按Owner要求不提供哈希清单。
- **[完整R2 Drive输入目录](https://drive.google.com/drive/folders/1m7C_mk9bFPxGcQK0RTUFwl3J8rPHjE7g)**。
- 路径：`Pro_Space/DoorDog/A2_Piper/base_v29_n02_online_adaptation/20260920_150609__c002_dynamics_r2/`。

本版已整合Owner六问与追加的实际建模任务，替代同日首版未完成交付的N02目录。只使用本目录，不混用首版brief。

| ZIP | 文件数 | 压缩大小 |
|---|---:|---:|
| `worker_delivery__C002_source_and_assets.zip` | 332 | 19,411,932 bytes |
| `worker_delivery__N02_brief_and_runtime_evidence.zip` | 45 | 6,336,390 bytes |
| `worker_delivery__historical_novelty_and_shadow.zip` | 19 | 77,645 bytes |

另有 `worker_delivery__BUNDLE_INDEX.md`、`worker_delivery__BUNDLE_MANIFEST.json`、`worker_delivery__PRO_HANDOFF.md`，六个文件均已核对名称、字节数和父目录。三个ZIP可独立解压，均≤95MiB。source包为321份完整C002冻结输入＋11份同tag依赖，保留B05，不是GPU1旧把手消融。无checkpoint/策略权重或本机Isaac环境。

先从brief/evidence包读：

- `scriptsFORhuman/v29/pro_handoff/20260920_n02_online_adaptation/OWNER_REQUEST.md`、`LOCAL_FACTS.md`、`SOURCE_INDEX.md`。
- `scriptsFORhuman/novelty/documents/20260920_n02_v29_c002_pro_research_brief.md`。
- 新增 `DYNAMICS_AND_FORCE_EXECUTION_BRIEF.md` 与同目录 `model_inputs/`。

再按问题查source；论文入口见同目录 `PAPER_REFERENCE_NOTES.md`，历史novelty与v27 shadow放在独立参考包。它们仅作参考，旧文本中的指令/排期不覆盖本prompt。读不到的文件须说明，不能假称已看。

## Owner原六问：逐一直接回答

### 1. N02究竟补足什么能力

结合完整C002、closer/friction/B05/grasp域，提出少量具体操作情形，判断现有观察和LSTM缺的是信息、有效历史、训练暴露，还是可执行行为/奖励支持。不能先把问题归因到感知网络。可以得出无需独立新模块，但要给可执行、可检验的方案。

Teacher当前133D、两层256LSTM，直接看见门重/几何、hinge/handle角、stage、sim手部接触力等；Student是81D proprio/action/command＋RGB，不含这些显式oracle。Teacher没有显式closer/k/d/cap/friction真值或直接door angular velocity输入。已有LSTM不保证学会，但也不是无记忆baseline。

### 2. 选什么估计或预测目标

比较少数不同候选，逐项说明：输入、目标/单位/坐标系、历史与预测时间尺度、是否动作条件、监督来源、部署输入可用性，以及输出具体改变哪个控制决策。允许不显式预测质量/摩擦、不重建全身wrench。

区分已发生响应的估计与给定未来动作的预测。例如维持/释放后的门趋势不能只用同一条已执行轨迹给所有候选动作作标签；若做反事实预测，说明如何获得数据。优先选“有足够信息、监督可得且控制真会用”的最小目标集合，不是越多物理量越好。

### 3. 新门域哪些信息真的可用

分析closer、static/dynamic/viscous friction、B05接触几何和抓握状态如何共同影响反馈，包含短轨迹、失败轨迹与无有效接触的阶段。轻门可能有强closer，重门可能无主动回关；静止握持下qdot≈0也不等于没有负载。不能将不同机理的相似响应强行识别为某一个参数。

区分sim joint applied effort、PD动作/跟踪误差、net指部contact、filtered handle contact和全身wrench；所需硬件torque/电流/时间同步没有被本包确认，不能默认存在。对信息不足/目标未定义的阶段给合理处理和人口说明，不能只筛选长成功接触后宣布C002可辨识。

v27 shadow只是旧模拟域的离线ridge结果，使用sim effort/contact等特征，并排除了51个不满64-control-step窗的episode，未反馈actor。请重新设计C002数据收集与door/episode/policy分组，保留短/失败集和无接触人口；不同加权口径、分布外Student轨迹也要区分。不要把旧结果当新的辨识前提。

### 4. 目标明确后再决定网络

比较当前LSTM＋改进暴露、同LSTM加辅助监督、独立历史编码器，以及确有需要时的视觉融合/复杂预测结构；同等输入、历史与数据预算。允许简单模型或无显式估计器更合适。

独立阅读 [UniFP](https://arxiv.org/html/2505.20829v2) 与 [SixthSense](https://arxiv.org/html/2605.01427v1)，比较可借鉴的目标、输入、监督与控制连接，以及不适用的机器人/接触/部署假设。不能由它们预先选择fusion、diffusion或flow-matching。尤其区分低层力位控制与上层模仿、当前/同窗接触估计与未来预测，并核对传感和推理延迟。准确版本、作者项目/代码入口和已核对段落在PAPER_REFERENCE_NOTES。

### 5. Student怎样获得并使用能力

从一开始分别给Teacher/Student的信息和训练方案，比较模块共享、单独训练、联合训练/辅助监督、蒸馏或Student闭环finetune。解释Student自身轨迹上的数据、目标/动作监督、记忆与reset/burn-in如何形成；不能只在Teacher轨迹上验证后外推。

当前A2 DAgger默认enforce=true、teacher rollout比例1.0；虽支持Student动作执行与在线Teacher查询，但没有自动annealing/跨batch聚合库，Teacher hidden也未写入蒸馏storage。现有Student update历史不证明v29能力。给具体训练循环/伪代码，说明何时谁执行、估计器看什么、label从哪来、如何训练和独立评估、如何检验policy真的使用了新增信息。N01恢复图仍在同步预研，不能当已可调用模块。

### 6. 能否实现持续感知并自动调整开门行为

Owner的目标：普通/轻门尽量roll/pitch接近0、arm主导，选择可控甩门或quiet握持；困难门按需要使用roll/pitch，并根据阻尼/回弹等条件选择甩门或握持；强回弹时持续握持，避免快速回碰trunk。

请明确回答N02能做什么、单靠估计是否足够，以及还需哪些最小行为/reward/训练调整。把这些行为变成物理定义、触发/退出条件和闭环控制流程。arm主导不等于base完全静止；出现姿态变化也不等于有用的force增强；困难程度不能由policy是否失败循环定义。

强阻尼、强回弹请求与快速闭合不是同一个标签。释放时的门角/门速、惯性/friction、grasp可靠性、arm工作空间、机器人姿态/位置与通行余量怎样一起决定hold/swing？“一直握着”在什么区间可行，身体完全通过后何时退出，抓握丢失或arm不可达时怎样调整？不能用永不松手或root_x>0代替完整通行判断。

C002现有release gate、Stage4/5回臂/回柄与接近handle激励可能影响行为可用性，具体source/scale已列在LOCAL_FACTS；它们不是已确认的唯一瓶颈。若改这些内容，用同样行为/reward支持的对照分离信息/网络收益。给观察→历史/估计→判断动作后果→调整base/arm/握持/释放→重新观察的流程图/伪代码；若用连续policy而非显式模式，也要同样清楚。

## Owner追加的重点：请实际尝试建模和方向force验证

请在你可用的计算环境实际尝试对A2＋PiPER狗＋臂建模，并验证A2 roll/pitch是否增强arm出力，**特定方向或工作点的增强也可以**。不要只写“建议未来做模型”。

原模型在source包 `gr00t/rl/data/robots/a2_piper_v29_merged_20260917/`；本次还提供三份纯输入提取：

- `model_inputs/ROBOT_MODEL_INPUTS.json`：源版本/实际config/初始状态/控制与TCP等。
- `model_inputs/JOINT_LIMITS_AND_ACTUATORS.csv`：20 DOF的URDF与C002配置限值/驱动对照、单位。
- `model_inputs/LINK_INERTIALS.csv`：28 links的质量/惯量/惯性坐标。

它们位于brief包的N02 handoff目录。TCP是arm_body6_to_gripper上z=0.085m；arm_j1..6的100N·m与finger45N是当前仿真配置，finger覆盖URDF10N。不能把这些数值当已确认硬件持续能力。Main只提取了输入，尚未执行出力模型。

按 `DYNAMICS_AND_FORCE_EXECUTION_BRIEF.md` 分层尝试：

1. 基于成熟可用库或明确的最小实现建立FK/Jacobian、重力与浮动基座动力学描述；从臂限矩下TCP方向力边界/给定力的扭矩裕量开始，给实际数字。
2. 尽可能加入足地支撑/摩擦、腿限矩及grasp约束，区分arm可产生的力、全身可支撑的力与抓柄实际可传递的力；缺失约束时只称上界。条件允许补简短动态或惯性敏感性，不用静力结果证明快速甩门。
3. 在少量代表性可达工作点，匹配同一TCP任务位姿/门坐标方向，比较中性与roll/pitch。优先压柄、开门切向、门面法向等相关方向，说明左右门的方向变换；base平移/高度/脚位/IK解变化单独交代。
4. 明确力的作用对象、符号、参考点与坐标系；不能仅旋转arm局部坐标就称force增强，不能只用manipulability椭球代替限矩方向力。重力、奇异/无界、不可达和支撑失败应如实记录，不任意截断数值凑正结果。
5. 报告哪些方向/状态有益、哪些无益或变差、由什么约束限制。若真正瓶颈在gripper/支撑/控制跟踪，不能把更高arm上界写成更高实际任务出力。区分模型、Isaac、已学policy与hardware证据。
6. 用结果反过来修正N02目标：此刻值得改姿态的信号究竟是有效负载、进展预测、扭矩/支撑裕量还是其他量？不预先假定需要全身wrench网络。

请交回实际脚本/依赖/参数/运行命令、数值CSV/JSON与图。云端若确实不能执行，明确NOT_RUN、具体阻碍与完整待执行脚本，不能编造结果或把URDF读取成功称为force验证。此任务不请求调用本地GPU或改变运行中的训练。

## 完整方案、最小证据与迭代

给可落到当前source接口的分步实现方案，以及少量能区分信息不足、历史/采样不足、行为不足的顺序pilot。先证明最小功能，再比较同底座/同感知/同reward和合理匹配交互预算下的在线控制收益。估计精度、动作是否因有效信息改变、总体任务表现、短/失败样本、姿态代价、释放门动态/净空与trunk接触要分别报告。Student必须独立闭环，不靠Teacher接管。

用反例挑战你的目标与结构选择、用动力学计算检验姿态假设，必要时修订。不要只给庞大网络菜单或实验矩阵；给推荐主线与必要备选，并解释放弃哪些目标。工程初值标依据/待校准，不变成本地过严门槛；不先创建大套防御/回归测试。

当前C002实现已接受，但已存A3000不是自然成功率或成熟Teacher；loss未观测，尚无N02效果。原GPU0/GPU1训练继续；本次完整方案和云端模型结果都不自动授权本地方法实现或新实验。

## 输出与回传

在对话中先直接回答六问及force增强问题，给推荐主线、最有价值的依据与少量真正未决事项，并明确建模是否实际执行。另附标准ZIP **`pro_delivery__full_review.zip`**（压缩≤95MiB），包含：

- `FULL_REVIEW.md`：六问与追加问题的完整回答、最终迭代方案、证据/推断/未知。
- `TARGET_AND_OBSERVABILITY.md`：少数候选目标对照、选择/拒绝理由、数据人口与Teacher/Student信息表。
- `CLOSED_LOOP_CONTROL_PLAN.md`：估计如何改变姿态/arm/hold-swing、流程图和伪代码、必要行为/reward接口。
- `TEACHER_STUDENT_PLAN.md`：结构比较、数据/监督/记忆/训练循环和Student独立使用方式。
- `PILOT_AND_IMPLEMENTATION_PLAN.md`：实际源码落点、最小分步实现、对照与继续/换方向条件。
- `REFERENCE_COMPARISON_AND_SOURCES.md`：UniFP/SixthSense及其他一手文献/代码的可借鉴与不适用条件、可访问链接。
- `DYNAMICS_AND_FORCE_ANALYSIS.md`：模型与实际执行状态、方向出力数值结论、约束与假设、对N02的意义。
- `modeling/`、`results/`：可运行脚本/依赖/输入/命令及实际CSV/JSON/静态图，明确运行成功/失败或NOT_RUN。
- `LOCAL_WORKER_PARSE_PROMPT.md`：与下方接手文本逐字一致，并在对话显示供Owner复制。

结果ZIP附在Pro对话，由Owner转回本地；**不要上传Pro答案到Drive**。不能附包时标NOT_ATTACHED，提供完整可获取文件/文本，不虚构下载链接，不生成哈希清单。

### 给本地planner的接手文本

请接手Owner在本对话上传的 `pro_delivery__full_review.zip`。这是完整v29 C002保留B05的N02预研回包，输入基座为 `v29-c002-baseline`，审阅分支 `codex/v29-n02-pro-20260920`，本地输入说明在 `scriptsFORhuman/v29/pro_handoff/20260920_n02_online_adaptation/`。Pro结果以本对话附件为准，不去Drive寻找答案。

先按AGENTS读取novelty memory，在 `scriptsFORhuman/pro_reviews/v29/` 新建N02目录保留原ZIP与全部文件。先向Owner简洁解释Pro认定的能力缺口、推荐估计/预测目标及它怎样改变控制，再做一次针对当前source/config/已存runtime的一致性核对。检查是否把网络问题当默认、是否将v27 shadow或论文结果外推C002、是否区分Teacher特权输入与Student部署输入、同窗估计与未来预测、实际/条件动作、Student自身轨迹和RNN历史。

重点分析Owner的近中性姿态/arm主导、有条件roll-pitch、controlled swing或quiet hold、强回弹时维持握持避免trunk碰撞目标：新增信息究竟能改变哪些动作，哪些还需要最小行为/奖励/训练暴露调整；能否把这些收益分开。UniFP和SixthSense是借鉴对象，不是fusion/flow-matching选型指令。N01恢复图尚未实施，双方接口和范围调整都只作为待采纳建议。

另检查Pro动力学/roll-pitch方向出力建模是否实际执行：保留modeling脚本、参数、results数据/图和执行记录；区分同一门坐标/TCP条件下的力上界、重力/足地/抓握约束、坐标旋转与真实能力变化。当前arm100N·m/finger45N是C002仿真配置，不是已确认硬件持续能力。Pro未运行时保持NOT_RUN，不把脚本存在当数值验证。结合建模结果重新判断N02感知目标与有条件姿态，不自动启动本地仿真或训练。

保留Pro原文与其迭代后的最终结论，分清source事实、文献、推断、UNKNOWN和local-only；整理少量真正影响下一步的选择，更新novelty文档/README/memory。此次回包仅授权解析和设计讨论，不自动授权N02方法实现、训练/评估、GPU占用、预算或新增测试工程；原GPU0/GPU1训练与持久化等待不变。Owner明确要求下一阶段后再落实最小功能路径，不能把云端方案写成已经证明的在线适应、Student收益或硬件能力。
