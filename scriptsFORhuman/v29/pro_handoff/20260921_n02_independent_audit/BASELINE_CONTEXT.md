# 本次审阅的baseline上下文与证据边界

2026-09-21 HKT。资料按实际来源分开，不从进程/历史PASS推出训练结论。本页仅汇总已有文件，不新增模型计算或运行。

## 开发底座与运行底座

- 主底座是完整 `v29-c002-baseline`，保留B05；GPU1的v29−B05不是主底座。
- 本次发布source是N02开发工作区的C002＋B08公共修复。B08删除普通/canonical两路Stage0 arm累计target覆盖，保留真实reset、默认姿态reward与晋级要求；只是公共动作修复，没有实现N02方法。
- 原C002 6000/7000证据来自仍使用冻结C002输入的既有运行，不含B08。不可称为B08后的效果。原GPU0/GPU1任务及等待由原任务负责；GPU4授权属于N02，但未有N02运行。
- source ZIP依据已选过的完整C002 source/assets清单从当前审阅worktree取文件，B08四文件显式包含；不拿主运行目录脏文件混做N02源码。无checkpoint/模型权重。

## C002任务与接口

Teacher actor为133D、原LSTM两层256；Student为81D＋RGB，未显式给stage、接触力、门角/门位姿/质量或base linear velocity。Teacher可见门质量/几何等不代表这些量可由Student交互辨识。Student候选生成器、selector和名义到N02入口也不得暗用真值。

高层动作12D＝base5＋arm增量6＋gripper1，冻结A2_Base生成leg12，环境入口组合24D。Student actions历史19D＝leg12＋累计arm target6＋gripper1，另有6D delta；命令、目标、实测运动和力分别记。冻结腿策略不等于任意wrench控制。Teacher/Student各自沿真实轨迹维护hidden，真实done reset；DAgger默认Teacher执行比例1.0且固定env前缀，8tick是数据窗口。

B01三档门重30–80/80–120/120–160kg，各1/3；closer有无各1/2并与质量交叉；静/动/粘性门轴摩擦按实际native参数。B04 native最大开角90–150°；B05保留七族程序化把手及0.90–1.20m高度。B05不是一个可独立加载的静态USD，实际几何/目标由handle_v29.py与door生成路径定义。原配置control dt为0.02s、全程30s、stage预算[525,150,150,150,150,300]。这些是参数/接口，不是行为可行性证明。

原Stage5收入逐tick依赖root、hinge/handle条件，最终完成另有root>1.5；旧hold-income在Stage5关闭、回臂/回柄/闭爪偏好可能与持续辅助冲突。Owner同意重定义身体通过合同，但具体最小reward设计仍应接受Pro审议。请特别检查stage收入、完成延迟和行为代价能否被当前架构/目标利用。

## 实际证据

| 证据 | 已观察事实 | 不能推出 |
|---|---|---|
| D048 B05 contact34 | 34个manifested构型的实际几何/接触接线证据 | 所有握持/通行轨迹可行、整任务成功 |
| C002 6000 final，64自然首episode | 0/64 goal；LEFT最高Stage2/4/5为2/27/3，RIGHT32例均Stage2；均阶段超时 | “永远不会学会”、具体单因素瓶颈或N02必须存在 |
| D076 7000自然64 | LEFT31/32 goal且32例都到Stage5；RIGHT31/32到Stage3、1例Stage2，Stage4+为0 | 双侧合格Teacher、新三程序合格、B08或Student收益 |
| B08 CPU提取动作链 | Stage0输入0.2、scale0.3，三步累计约0.18；镜像/选择性reset等有限检查通过 | 完整Isaac生命周期、学习收益或硬件证明 |
| 旧N02 Pro CPU模型 | 42姿态、26解、104方向与PD补算；本地只检查材料，未复跑 | 冻结腿策略兑现、全部B05传力、持续握柄通行或动态甩门 |

压柄夹持模型遗漏 `F|d·n|≤Nmax`：156条press_down中90/36.4N不能当完整容量，更紧必要界45/18.2N仍为假设；水平、arm/足地/PD主表不受该遗漏影响。模型固定世界TCP完整位姿、base位置、脚位后重解关节角，不是只转坐标。arm100N·m与finger45N是仿真配置，18.2N来自假设指位/增益；均非硬件持续能力。

## 当前资料不足以直接证明的事

没有N02条件执行器、selector或后果头的运行结果；没有“有效握柄同时身体完成通过”的系统可达域证明。原始大逐步trace与checkpoint未打包，不应假设能从本包重建完整精确模拟分支。现有模型/接触证据可帮助定位问题，但不能补成未来反事实或隐含的动作能力。

本包只包含已归档6000/7000结论和选定原始小证据；没有正式8000结论。旧文件可能含当时的A3000或待实施状态，应按日期、当前source和本页证据区分，而非一律以旧标题当当前事实。
