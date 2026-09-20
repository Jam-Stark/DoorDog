# N02当前事实：信息、历史与行为接口

2026-09-20 HKT。只陈述C002源码/config及已存证据，不预选估计目标或网络。

## 基座与当前能力结论

完整C002、保留B05；基座本地tag `v29-c002-baseline`。本次复用N01交付中已核对的332文件source包：321份完整冻结输入＋11份同tag依赖，生产内容相同。没有采用GPU1的v29−B05源文件。

C002实现已经D056/D060接受。原候选JSON的pending状态与旧baseline plan的待实施标题是历史记录；实际source/config与接受结论优先。最新已存且已审阅的A组3000里程碑仍不足以证明整任务成功、恢复或N02能力。这里只复用该证据，不为了打包再次轮询训练。loss仍NOT_OBSERVED，最终自然评估未包含在本包。

## Teacher与Student信息条件不同

| 项目 | C002/现有A2蒸馏的实际接口 | 不能直接推出 |
|---|---|---|
| Teacher actor | 133D；两层256维LSTM | 缺少独立估计器就一定缺少记忆/适应 |
| 门信息 | `privileged_door_info`8项包含宽、高、handle高/宽、门重/100、左右侧与IO；`door_dof_pos`直接给hinge/handle角 | Teacher从交互中估计出质量；或Student也有这些真值 |
| 力反馈 | `hand_force`为arm_body7/8的sim rigid-body contact force，共6D；另有面向door_handle的filtered sensor用于接触/握持判据 | net指部接触力、filtered handle接触、关节effort和全身wrench是同一量；或硬件直接可得 |
| 未显式给Teacher的量 | actor列表没有closer类别、k/d/cap、摩擦真值、直接door angular velocity或关节torque项 | 它们完全不可由历史推断；或已有C002可辨识性证明 |
| Student actor | 81D proprio/action/command＋RGB；没有显式stage、hand_force、门角/相对位姿/质量与目标frame真值 | 图像中看见门就已经得到同精度/延迟的门状态和接触信息 |
| 历史 | Teacher/Student循环state各自维护；冻结A2_Base有单独30×54=1620D腿策略历史 | 下层历史已经作为Student高层actor的全任务历史输入 |
| 部署信号 | source描述sim接口；尚无本包核验的A2/PiPER硬件torque/电流精度、延迟、带宽和完整时间同步合同 | sim implicit applied effort可直接作为稳定的实机关节力矩传感器 |

Teacher与Student必须分别讨论已有输入、可估计状态、训练监督和部署输入。若要公平检验新的历史/估计模块，请显式处理Teacher已有质量/几何oracle，不能让新增真值或不同信息预算替方法赢。

## 新门域为何需要重新讨论信息

B01按三档质量30–80/80–120/120–160kg各1/3、closer有/无各半，在左右侧内平衡组合；closer force cap、k/d与门轴static/dynamic/viscous friction由固定逐门参数定义。不是“轻门无closer，重门强closer”。原生动力学决定释放后的轨迹，设计用的reference closing speed不是强制门速。

B04为90–150°的固定native upper limit。B05七族几何、实际G/consumer与把手高度.90–1.20m保留；接触局部几何、夹持质量、杠杆和可达性都可能影响反馈。以上是环境及接口事实；哪些因素可从短时响应区分、哪些仅需低维任务预测，应由本次研究给出可检验结论。

观察到qdot接近0既可能是无有效作用，也可能是静止握持下抵住closer。预测保持与释放后的结果时，需要区分已发生的响应和动作改变后的反事实；本包没有这类C002新数据。

## 行为通道存在，但估计器不是动作能力的替代

当前学习12D高层动作，包括5D base命令、6D arm增量与1D gripper primitive。A2_Base生成冻结的腿动作；base接口包含平移/转向与pitch/roll目标，实际经过既有scale/限幅，属于位置/姿态控制链，不是任意末端wrench命令。Stage3 base_unlocked=true；“arm主导”不应被简化成base完全固定。

当前实际config与source还包含下列行为激励。它们是研究时应检查的具体接口，未证明是现有性能的唯一原因：

| 已核对事实 | 对本次目标的待研究问题 |
|---|---|
| 普通grasp目标距离在Stage4为0；mild项受Stage3/4 hold-income mask控制，release gate后关闭 | 强回弹后是否仍有足够的再接近/持续握持引导 |
| Stage4 arm-default罚在release gate且非双指接触时生效，scale−.5 | 失去/尚未重建接触时，伸臂是否受到相反偏置 |
| Stage5有arm-default罚−5，无接触豁免；hold-income-continuity=false | 身体尚未完全离开门扇影响区时，持续握持/重新辅助怎样表达 |
| Stage4/5有handle回升奖励；完成条件与root越门/hinge/handle角有关 | 再解锁、握持和正常释放的目标是否一致 |
| baseline roll/pitch平方罚−2作用于Stage0/1/4/5；Stage5另有upright罚−8 | 近中性姿态与有条件姿态调整不能只用统一外观偏好判断 |
| 旧`a2_v22_controlled_fling`函数还在，实际C002 scale=0 | 不能从函数名字推断已启用“甩门/quiet握持”模式选择器 |

当前control dt=.02s、全任务30s、stage预算[525,150,150,150,150,300]；N02要说明历史长度、预测范围、模块更新延迟与决策时机。若改变reward/行为支持，必须与信息/网络收益分开，不把改奖励的收益直接归为感知提升。

## Student训练的现状

现有A2 DAgger每步在当前env查询Teacher并计算Student动作；`ratio_teacher_rollout`允许一部分env执行Student动作。默认值为1.0且enforce=true，即环境高层动作全部由Teacher执行；没有自动annealing。选择采用batch前缀，当前storage只保存本rollout，不是跨batch聚合数据池。实际目标是12D BC。

Teacher与Student各自处理hidden与done；Teacher hidden不在蒸馏storage中。本包不包含“v29 Student已经正确compose/运行”的证据，旧v10一次Student update不能替代。N02模块如何在Student自身轨迹上训练、标注和使用，必须设计而不能外推Teacher结果。

## v27 shadow只作为历史

旧shadow使用64-control-step窗口与stride、ridge=1。特征是sim arm q/qdot/target、implicit effort估计、base重力/速度/命令和两指handle contact norms；不含门角/参数输入。每窗只做均值、std、末帧和首末差摘要。3397训练窗、1171 heldout窗、279 heldout episode，另排除51个没有完整窗口的episode。

历史window-weighted friction/mass R²为.15557/.33127；equal-episode口径为.21428/.43365。分组按seed/stratum/side/env，将配对door槽跨policy放在同一split。它只支持旧域有限离线信息，未回馈actor，也未建立部署传感或C002新域可辨识性。

本次附旧脚本、执行证据和endpoint原结果，便于Pro审视输入、人口和指标边界。没有复跑，也不把短集/失败集排除规则当作N02默认。

## N01接口与范围

N01已交付独立Pro预研，恢复图/能力传递尚未选型或实施。N02可以提出信息/状态/数据接口与恢复行为的分工，包括旧“强回弹重抓把手”议题；这些都是待Owner采纳的建议。既有GPU0/GPU1运行和等待不变，当前没有新增N02方法、实验或预算。
