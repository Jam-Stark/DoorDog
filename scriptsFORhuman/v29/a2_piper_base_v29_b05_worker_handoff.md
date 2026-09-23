# v29 B05实施技术附件（完整worker任务的一部分）

完整worker任务现在覆盖整个v29 baseline实现、修正和训练监督，统一使用[worker启动prompt](a2_piper_base_v29_worker_start_prompt.md)及[验收/协调合同](a2_piper_base_v29_acceptance_and_coordination.md)。本文件仅提供B05具体source落点，不再作为独立或总范围的启动prompt。D029全部Pro参数继续生效；D030–D031明确由planner验收、修正反馈并批准GPU0正式开训。

## 输入与已确定范围

1. 先按AGENTS及memory入口读取当前状态，再读[baseline plan §7](a2_piper_base_v29_baseline_plan.md)、[B05执行规格](a2_piper_base_v29_b05_handle_design.md)和[第二次几何确认](b05_gripper_confirmation_20260919/README.md)。三者以D029为当前决定。
2. 保留F0–F6全部七族与七个标称锚点，训练族概率各1/7；X1轻弯×椭圆仅作为未见组合配置，不进入训练抽样。
3. 实现批准的h/尺寸/roll/λ、50%条件圆滑return及Ø54×6同轴饰盖；参数表、采样先后、I/J/G及端帽定义以规格为准。
4. 保持当前PiPER网格、TCP=.085m、夹爪控制/动力学设置；不为参数范围通过而前移TCP、削指或替换碰撞模型。

## 按实际代码路径实施

| 路径 | 必须形成的最终行为 |
|---|---|
| `gr00t/rl/isaac_utils/playground/env_rand/door.py` | 统一中心线×截面×return；逐门生成参数、碰撞/visual/质量与目标frame；同一门双侧杆按同族参数镜像构造；rose作为门板子几何 |
| 同文件metadata与`get_deterministic_door_config` | 保存并重建family、尺寸/φ/λ/h、hook/R/H/r_tip、I/J/G及目标姿态；同一门reset/staged恢复不重抽几何。现有单一handleRadius/Length不能冒充非圆或曲杆完整几何 |
| `gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py` | v29实际selector/spawner使用新配方，左右侧内同样分布；X1不进入训练族概率 |
| `door_open_a2_base.py::scene_creation_callback`及`OrderedTargetFrameTransformer` | generator已经给出最终G frame，handle offset单位旋转，pregrasp沿目标局部−Z100mm；只移除旧目标约定导致的重复旋转/LEFT补偿，保留其他左右观察/动作约定 |
| `_init_door_metadata`、`_compute_grasp_target`、creation/reward相关目标读取 | 闭门G缓存、自然起点朝向、当前目标与reward使用同一新frame；不沿用旧世界中点，保持18维pose与8维door-info等观察维度，不新增族ID/参数真值输入 |
| 详细hold/contact元数据路径 | 当前会读取customData.handleRadius；改成真实截面/局部尺寸口径，不能把椭圆/扁截面伪装为一个圆半径。contact body仍是door_handle，filter仍是arm_body7/8 |
| v29配置/新资产输出 | 显式采用批准配方，资产/metadata同步版本；旧快照不自动混入。复用现有依赖与几何基础，不建立双套兼容/回退路径 |

## 具体实现关系

- 默认G固定为本门J中点，t朝轴颈，a为门侧接近方向，`R=[−t,t×a,a]`。截面roll只转物体截面，G不追随薄轴。几何左右镜像后重新构造proper rotation。
- FixedJoint两端局部框架变到世界后重合；同一frame驱动handle/pregrasp及所有消费者。grasp_target不成为新接触支点。
- 先确定族/截面/roll/λ/h与端帽r_tip，再按`C=min(60,h−r_tip−8)`、`R~U(20,min(30,C))`、`H~U(R,C)`生成回钩；主握I/J不包含回钩，弯头带来的总长增加写入几何metadata。
- 单个door_handle刚体不拆成多个可抓body；曲杆/回钩采用保留内空隙的局部分段碰撞。约0.25mm离散参考不等于接触求解精度，也不要求无意义增加片数。
- 总质量量级同hook状态沿用名义无钩0.4/有钩0.5kg，按照实际组合几何计算COM/惯量；不重复计算重叠段质量。rose计入既有门板总质量分配，不增加新的门质量随机维度。
- 旧圆杆标称/旧域记录保留作明确对照；生产v29采用同一参数化生成链，不因旧metadata缺字段而静默退回圆杆。

## worker实现后需提供的证据

先让F0标称的生成→导入→目标/接触路径走通，再接入其余族与已批准参数。报告实际生成参数、导入后的代表性截面/return/rose、左右目标和FixedJoint一致性、真实碰撞/接触设置。当前静态确认覆盖的是原始几何与参考接近姿态，不能替代这些实现证据。

不要求重新进行全仓审计、庞大测试矩阵或新一轮产品检索；发现具体接入问题时直接定位对应路径。保持B04/B05方案完成勾选，代码实施状态另列。worker负责完整baseline及获批后的训练监督；planner按全版合同锁定正式训练命令/预算并批准GPU0开训。Owner已授权双方在其离线期间自主沟通推进；本B05附件不单独提供开训批准。

## 保持既有决定

B01三档门重/closer/摩擦设计、B04原生最大开角计划按各自章节实施；B05不重选这些动力学。B02仍独立ablation后置、B03保留15°后置、D023三处原奖励保持，N02承接强回弹重抓议题。原文Pro归档保留，worker以最新D029规格而非历史“待Owner确认”状态执行。
