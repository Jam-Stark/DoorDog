# N01：末端滑脱力幅、持续时间与触发窗口

2026-09-21 HKT。作者：N01 planner。状态：**离线量级估算与数值提案，未标定、未实施。**

依据[Owner本轮问题](../conversations/20260921_codex_n01_force_calibration_request.md)，从当前C002的夹爪材质、关节驱动和v29 URDF估算。Owner建议的0.5–2s与grasp到release窗口是供独立判断的想法，不是已批准的数值合同。N01-D001～D003保持不变，当前入口仍为[v29 N01 plan](../../v29/a2_piper_v29_n01_plan.md)。

## 1. 建议先采用的范围

| 项目 | 首轮校准提案 | 理由 |
|---|---|---|
| 向实时pregrasp退出，−Z_G | 幅值均匀抽样40–100 N | 摩擦之外，当前arm对这个方向的位移较硬；需要覆盖开始滑动和继续移出两种情况 |
| 沿把手切向，±X_G | 每侧幅值均匀抽样25–60 N | 本次姿态示例的方向刚度较低；保留低于起滑阈值的保持握持样本 |
| 时长 | 0.2–0.5s；200Hz下整数40–100 physics step | 0.5s作为首轮长档；先避免失抓后仍持续受力1–2s而改变局部恢复问题 |
| 触发 | 新的稳定握持资格成立后，随机等待0–0.3s | 已有5 control tick约0.1s的资格持续要求，不再强加额外固定0.5s等待 |
| 窗口 | 当前抓稳、仍需把手控门、正常释放开始前 | 不以历史grasp标记或release资格latch代替当前物理握持与任务需要 |

三个方向仍建议等概率选择，时长与方向内幅值独立抽样；触发等待可用0–15个整数control tick表示。方向在t0转成世界向量并保持这次脉冲不变。第一版每episode最多一次计划脉冲，等待中资格消失则取消。**时长在注入前确定，不因滑脱而续长、加力或提前停力；真实episode done结束剩余脉冲。**

这些是给未来首个功能片段的起点，不是最终训练分布或“必定脱手”的范围。名义/扰动比例、预算和Teacher选择不由本次计算决定。

## 2. 当前参数与尚缺的真实接触量

| 项目 | 当前source/config事实 | 对估算的含义 |
|---|---|---|
| arm_j7/8 | URDF为prismatic；C002每指kp=1300 N/m、kd=32 N·s/m、effort cap=45 N，闭合target为0 | 不能按转动关节的N·m/rad解释。URDF原始effort=10被当前配置覆盖，不能拿旧10 N作当前能力 |
| 六个arm joint | kp=[64,128,64,64,64,64] N·m/rad；kd=[3,4.5,3,3,3,3] N·m·s/rad；effort cap各100 N·m | 必须通过姿态与Jacobian换算到受力方向；100 N·m不能直接加到夹持摩擦上 |
| PD随机化 | C002 resolved config的randomize_pd_gain=false | 本次采用上述名义增益；仍不包含策略在线更新target的响应 |
| M39手指材质 | arm_body7/8的μs=1.1、μd=0.9；M39不改door_handle | 不能直接把1.1当指–把手接触对的有效摩擦系数 |
| 把手材质与组合 | 默认μs=μd=0.5，默认average组合；既存M39记录支持这一默认路径 | 得到μs_eff≈0.8、μd_eff≈0.7；本轮没有C002接触对系数的新readback |
| 抓稳门槛 | squeeze阈值0.5–30 N、over-force阈值55 N | 它们是行为判别/奖励参数，不能当作抓稳时实际N_i |

控制参数见[v29 robot](../../../gr00t/rl/config/robot/A2_Piper/a2_piper_v29.yaml)、[C002 common](../../../gr00t/rl/config/ablation/wbmanip/base_v29_common.yaml)及[既存C002 resolved config](/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/a2_piper_full_stage_a2_base/base_v29/push_baseline_C002_seed291/config.yaml:688)；关节类型见[URDF](../../../gr00t/rl/data/robots/a2_piper_v29_merged_20260917/a2_piper.urdf)。当前backend以ImplicitActuator配置这些增益，参见[实现](../../../gr00t/rl/simulator/isaacsim/isaacsim.py)和[IsaacLab官方actuator说明](https://isaac-sim.github.io/IsaacLab/main/source/api/lab/isaaclab.actuators.html)。

average是两材质系数的算术平均；不同组合模式的优先级会影响实际结果。当前估算沿已读默认路径，不能将地面使用的multiply模式套到手指–把手接触上。参见[PhysX组合规则](https://nvidia-omniverse.github.io/PhysX/physx/5.1.0/_build/physx/latest/struct_px_combine_mode.html)及[本机RigidBodyMaterialCfg](/home/baoquanc/workspace/IsaacLab/source/isaaclab/isaaclab/sim/spawners/materials/physics_materials_cfg.py:38)。

已读的C002 natural-final归档只有episode末端的接触快照，没有同一抓稳时刻的实际gripper q和切向预载，不能用末端快照的总体中位数代替抓稳人口的法向力。当前IsaacLab的ContactSensor.force_matrix_w记录接触法向力向量的合成结果，摩擦另有数据路径；C002未启用详细接触记录。现有向量范数仍不能恢复每个局部接触点的法向载荷之和及剩余摩擦裕量。参见[ContactSensor数据定义](/home/baoquanc/workspace/IsaacLab/source/isaaclab/isaaclab/sensors/contact_sensor/contact_sensor_data.py:97)。

## 3. 先估摩擦，再估移出所需的arm位移

在静止、两指近似平面对夹、接触法线沿指驱动方向且无楔紧的简化条件下：

```text
N_i ≈ min(1300 × |q_i − q_close|, 45) N
C_static ≈ 0.8 × (N_1 + N_2)
C_kinetic ≈ 0.7 × (N_1 + N_2)
```

这里45 N是单指驱动上限，不是碰撞、惯性或形状楔紧下接触法向力的普遍上界。kd=32在单指0.1m/s的运动速度下对应约3.2 N的驱动变化，符号依运动方向；静态夹持时不能把它作为固定额外握力加上去。

| 每指距闭合target的位移 | 估计每指N_i | 两指静摩擦容量 | 两指动摩擦容量 |
|---|---:|---:|---:|
| 5 mm | 6.5 N | 10.4 N | 9.1 N |
| 10 mm | 13.0 N | 20.8 N | 18.2 N |
| 14 mm | 18.2 N | 29.1 N | 25.5 N |
| 20 mm | 26.0 N | 41.6 N | 36.4 N |
| 驱动已达到45 N/指 | 45.0 N | 72.0 N | 63.0 N |

14 mm只是示例，并未从C002抓稳轨迹测得。B05主杆截面为厘米量级，圆杆、椭圆、扁杆和回钩的接触几何不同；即使已知截面宽度，也须结合手指实际闭合间隙、握持位置和表面方向才能得到q。**不能机械地把所有B05把手直径除二并当作实际夹爪位移。**

以上容量还没有扣除正在拉门/压柄所占用的切向载荷。外力若与已有切向载荷同向，新增起滑力通常更低；反向可能先卸载再起滑，不能把整个容量总作为剩余裕量。

为了估arm增益对“继续滑出”的影响，本次在CPU上读取当前URDF，并只取既存N02输入中的5个可达中性姿态q，重新计算FK、受力点/接触点Jacobian及线性顺应性。它们是合成IK示例，不是C002 Teacher真实抓稳姿态；没有沿用N02的夹持容量结果或压柄模型。完整输入、公式和输出见[计算数据](20260921_n01_force_estimate.json)。

受力点C为arm_body6_to_gripper质心；接触代理点H用当前TCP的局部z=0.085m。二者相差约53mm，侧向受力时力臂不同，不能当成同一点。设G与TCP方向对齐、base固定、arm target固定，只考虑方向d上的小位移和摩擦反力R：

```text
j_c = J_C^T d ; j_h = J_H^T d
K_q Δq = j_c F − j_h R
C_hc = j_h^T K_q^-1 j_c ; C_hh = j_h^T K_q^-1 j_h
δ_h = C_hc F − C_hh R
F ≈ α R + K_eff δ_h
α = C_hh / C_hc ; K_eff = 1 / C_hc
D_eff ≈ (j_h^T K_q^-1 D_q K_q^-1 j_c) / C_hc²
```

Jacobian力映射依据[Modern Robotics：开链静力学](https://modernrobotics.northwestern.edu/nu-gm-book-resource/5-2-statics-of-open-chains/)。D_eff是逆顺应性的低频近似；惯量和其他接触约束未建模，不能由D_eff/K_eff推出实际settling time或滑脱用时。

| 示例TCP位置x/y/z（m） | 退出方向K_eff（N/m） | 沿把手K_eff（N/m） | 退出/沿把手D_eff（N·s/m） |
|---|---:|---:|---:|
| 0.50 / 0.12 / 0.90 | 1660 | 476 | 75 / 22 |
| 0.55 / 0.12 / 1.05 | 1515 | 376 | 59 / 17 |
| 0.70 / 0.12 / 0.90 | 2011 | 220 | 90 / 10 |
| 0.60 / 0.00 / 1.20 | 608 | 341 | 23 / 16 |
| 0.55 / −0.12 / 1.05 | 1516 | 376 | 59 / 17 |

这组示例的α在退出方向约1.00、沿把手方向约1.12–1.19。因此在每指14mm、无初始切向载荷的例子里，**开始滑动约需29 N退出力或33–35 N侧向力**。这只是简化摩擦阈值，还不等于已经脱离。

若只用滑动20–40mm、速度0.1m/s举例，估算式为 `F ≈ α C_kinetic + K_eff δ_h + D_eff v_h`。本次结果是退出约40–115 N、沿把手约34–52 N。20–40mm不是已经确认的脱离距离：长杆上侧移可能仍保持接触，回钩可能形成几何约束，而退出方向也依实际插入深度不同。这解释了首轮40–100 N / 25–60 N的取值依据，但不保证某个值必定失抓。

策略会持续更新target，base和门也会动；夹爪还能旋转、楔紧或产生多点接触。这些都可能显著改变上述力幅。当前计算给出可解释的起始量级，真实功能片段才决定是否适合局部恢复课程。

## 4. 为什么首轮不统一使用0.5–2s

0.5s可以保留，1–2s不建议作为第一批默认时长。当前控制周期0.02s：0.2s为10次策略更新，0.5s为25次，2s为100次。若0.2s已失抓而外力继续到2s，剩余1.8s可能继续拖动arm/base，或者让策略在持续载荷下恢复；这与短时失抓后局部恢复的条件已有明显差别。

持续更久也不等于更快滑脱。固定条件下，低于静摩擦阈值的力可能一直被抵消；超过阈值之后，位移仍受arm刚度、惯量、几何和策略响应影响。本次低频代数不足以预测达到脱离距离的时间，因此0.2–0.5s仍需看实际物理片段，而不是由静态公式证明“足够”。

若后续需要研究持续外力下的抗扰/恢复，可把1–2s作为独立条件。首轮先按预定短时程结束，不为了制造loss改成长时间追推。

## 5. grasp完成到release前：大窗口成立，先分清两类握持

推荐的大窗口就是**真实grasp完成之后、正常release开始之前，而且当前任务仍需把手控门**。起点用本次新的5 control tick握持资格与实时几何，不用曾经grasp成功的历史标记；终点也不能只看门角或release latch。现有latch只代表达到过释放资格，不代表已经松手。

首次校准优先选“刚抓稳、门尚未大幅运动”的早期握持；“门已运动、仍在控门”的握持随后单列。后者的切向预载、arm姿态和门速度不同，不能把本次中性姿态的力范围直接宣称为整段窗口都合适。Stage3/Stage4可以作记录分层，但不能替代当前握持与释放状态。

这替代v0.1把课程整体保守限定在release资格尚未出现的提案：**达到释放资格后若还真实握持且确实需要控门，不应仅因latch=true就永久排除；已经开始正常释放则不再新触发。** 首次校准聚焦早期窗口不等于将N01方法范围永久限在这个片段。

脉冲中途若策略开始正常释放，保持原定短时程并记录发生顺序；不能将它重贴为纯扰动失抓。正常释放后强回弹导致重新伸臂抓把手仍属N02，D023不变。

## 6. 未来功能片段需要回答的最少问题

先按当前原生逐physics step路径实现一个有限脉冲；策略命令正常执行。把脉冲前抓稳时刻的gripper实际q、已有指–把手接触、arm q/target和门状态，与施力时程、相对位移和撤力后的行为对齐，便能判断本次力主要被夹持抵消、造成局部滑脱，还是主要推动了门/base。无需先建完整动力学辨识或额外测试体系。

力值调整应由这些具体结果解释：例如达到60 N侧向力仍沿长杆保持接触，先判断是否尚未到几何出口；不能仅延长为2s并假定“失抓剂量不足”。保持握持是有效结果；局部滑脱后的新握持及完整任务后缀另看。

本轮完成source/config/官方资料定向阅读与CPU离线代数计算；没有启动Isaac、物理积分、策略执行、训练、评估或GPU任务。没有实现代码、测试、Git提交或外部发布。数值采纳与实际校准结果仍待后续决定/独立实施任务提供。
