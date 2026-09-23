# B02=A / B04=native joint limit：统一设计规格 v1

状态：**Pro选定设计，未实施、未运行、未训练验收。** 本文件与`DESIGN_PARAMETERS.json`为同一方案。来源、对比与证据边界见`FULL_REVIEW.md`及`SOURCES_AND_CODE_MAP.md`。

## 1. 范围与不变量

B02只保留A实现：真实handle和hinge＋软件虚拟锁闩，不保留实体latch/mimic或dummy第三DOF。B04只采用原生hinge limit；不得在正常物理步中clamp/write door q、重置qdot来锁住或限制最大角。合法自然/staged reset写状态不在此禁令之内。

B03固定15°，不增加相机或render前置。B01已批准质量分层30–80/80–120/120–160kg各1/3、closer有无各半、门轴松紧；这些参数由B01模块负责，本设计不改其权重、不代写新的B01配方。30s与已实施自然起点/Stage0平滑速度保持。

必须维持：

- `mechanical_hinge_max`、handle总行程及本门物理参数在生成后固定；临时lock upper不能污染它们。
- 任何新参数/R/E不进入actor/Student。Teacher现有质量/几何真值不因此删除，也不冒称可部署。
- 解锁仅改变约束集合，不推进door角、不代发推/拉/张爪动作、不跳stage。
- restore跨越正常/窄限位时不夹杂physics step；运行时E切换只有单一限位writer。
- API失败或非法snapshot明确失败，不fallback到q rewrite、忽略锁或套用150°。

## 2. 坐标、类型与选定参数

q=本门正向开启角，h=本门正向下压角。当前push场景两个DOF均为rad，两侧通过USD joint frame镜像，都使用q≥0/h≥0。不能把RIGHT按world yaw符号写成反序limits。

### 2.1 每门一次性生成

| 字段（建议命名） | 类型/采样 | 含义 |
|---|---|---|
| `handle_stop_rad` | H_deg~U(40,60)，一次deg→rad | 真实handle native上限 |
| `unlock_fraction` | ρ~U(0.65,0.85) | 相对行程比例 |
| `unlock_rad` | u=ρH_rad | 解除锁约束的角度 |
| `handle_return_at_stop_Nm` | T_H~U(1,3) | 模型准静态回位力矩 |
| `mechanical_hinge_max_rad` | M_deg~U(90,150)，一次deg→rad | 真正最大开角，不随锁态变化 |
| `mechanism_schema` | 固定`v29_virtual_latch_native_v1` | topology/状态含义版本 |
| `door_parameter_id` | 不含哈希的门实例/参数版本标识 | bank恢复必须同门同参数 |

H、ρ、T_H、M独立抽样；B01分层与左右分配不因上述抽样改变。u支持26–51°、H−u支持6–21°，两者的边缘分布**不是**uniform，不再独立抽u或余程。

本轮选定参数均是工程初值。PDQ的41°/65°为产品操作角证据，不是本表的真实频率或硬止挡标定。默认不把60–65°区间作为baseline必须覆盖；未来扩域要显式变更schema/范围，不能当前默默生成。

### 2.2 全局固定常量

| 字段 | 值 |
|---|---:|
| `lock_lower_rad` | 0 |
| `lock_upper_rad` ε | deg2rad(0.25)=0.00436332313 |
| `recapture_upper_rad` c | deg2rad(0.20)=0.00349065850 |
| `negative_tolerance_rad` η | deg2rad(0.05)=0.00087266463 |
| `handle_hysteresis_rad` δ | deg2rad(2)=0.03490658504 |
| τ₀，模型零位预载 | 0.35N·m |
| b_h，模型阻尼 | 0.05N·m·s/rad |
| native handle torque cap | 3N·m |
| near-handle-stop位置容差 | 0.005rad（沿用现有遥测容差） |
| physical dt | 当前0.005s |
| policy/control dt | 当前0.02s |
| contact事件确认 | 连续2个control样本，40ms；原始样本及首见时间保留 |

ε不是“数值上等于零”，而是模型允许的真实游隙；η不是新增负向机械行程。c<ε，避免在门已超过窄upper时收紧。若这些初值在本机不成立，记录未通过并回报，不自动扩大游隙或clamp。

### 2.3 handle native drive

所有SI值按本门计算：

```
k_h = (T_H - 0.35) / H_rad
h_rest = -0.35 / k_h
b_h = 0.05
v_rest = 0
ff_effort = 0
cap = 3 N·m
```

期望模型：`tau = clip(k_h*(h_rest-h) - b_h*h_dot, -cap, cap)`。这是力矩公式中的clip，不是状态clip。

USD生成器显式force-type angular drive：`stiffness=k_h*pi/180`、`damping=b_h*pi/180`、`targetPosition=rad2deg(h_rest)`、`targetVelocity=0`、`maxForce=3`；handle Revolute物理limit仍为0–H_deg。米/千克/秒场景单位需在本机确认。

运行时implicit actuator的position target使用h_rest(rad)，velocity target=0、effort target=0；在创建和每次自然/staged restore的最终步骤重设，不能只改USD author属性。`default_joint_pos`仍0，绝不可为了预载把default物理位置设成负h_rest。本机public方法须与现有版本对照；API交叉依据[S11]，限位setter原文以[S06]为准。

k_h支持约0.621–3.796N·m/rad，是H/T_H联合派生；不新增独立k随机化。T_H是模型静态端点力矩，不是每步实际施加力矩。重力、速度项和接触反力分别存在，不把joint reaction或robot安全载荷等同cap。

## 3. 环境状态机：两位状态，不是两个policy开关

### 3.1 持久状态

按env维度保存：

- R=`_a2_v29_lever_retracted`，bool。
- E=`_a2_v29_latch_engaged`，bool。
- 本门参数及schema/parameter id。
- handle creation high-water及现有release gate/阶段历史buffer。

`effective_hinge_upper`可作为缓存/读回记录，但只由E和M派生，不能反过来充当M。只要API尚未成功提交新限位，E不能被记为已经生效；分别记录检测时间/提交时间/下个生效物理步。

### 3.2 每个真实物理步后的更新规则

读取scene.update后最新的q/h，先计算：

```
R_next = True   when h >= u
R_next = False  when h <= u - delta
R_next = R     otherwise
```

然后按优先级：

```
if R_next:
    E_next = False
elif (-eta <= q <= c):
    E_next = True
else:
    E_next = E

upper_next = epsilon if E_next else M
lower_next = 0
```

上述最后分支不会把已锁住的异常大q自动改成“解锁”；约束越界应另报fault。R=true优先，因此压住把手回关时不复锁。R回false而q仍半开时保持E=false；E不因“h回到了零”就收紧。未处于任何特定stage也照常执行。

**捕获不要求qdot=0。** 在当前upper收紧前，q必须不高于c；solver负责之后的反力/速度变化。接近lower可能有−η内数值误差，lower本来就是0、此操作不改变它；更大负误差应记fault。未证明高速回关的捕获/反弹可以接受，故它列为运行验证点，不当作已实现真实斜舌碰撞。

不按h速度平台、action饱和、contact总力阈值猜测解锁，不用robot位置改变E；那些只能是策略可利用的间接反馈或诊断。

### 3.3 真正的约束提交接口

当前本机方法节选支持：

```python
# 接口示意，不是可直接部署的补丁；hinge_id按名字解析。
door.write_joint_position_limit_to_sim(
    limits=desired_limits_rad,  # [M_changed, 1, 2], finite float tensor
    joint_ids=[hinge_id],
    env_ids=changed_env_ids,    # 唯一、有效、device-local整数tensor
    warn_limit_violation=True,
)
```

desired lower全部0，upper取ε或该env的M。empty changed set不调用；同一substep合并一次，不per-env循环。入参shape必须使用本机上层setter的shape；不能把它与底层`set_dof_limits`需要全view缓存的shape混淆。

本机setter会修改limit/default/soft缓存并`.cpu()`传完整limits缓存，只有indices筛选articulation。因此净耗时不能由“changed很少”直接推出。使用public setter；本轮不设计绕过缓存的高速私有路径。

所有状态转移先计算候选、校验、提交limits成功，再更新E/R及日志；实际physics反应发生在下一solver步。失败不得记录unlock成功，不得继续运行一组与state不一致的bounds。

### 3.4 时序接入

`legged_robot_base.py`已有：

```
PRE: _apply_force_in_physics_step
scene.write_data_to_sim -> sim.step -> scene.update
POST: _post_physics_substep
```

在Door类现有`_post_physics_substep`中，`super`之后且temporal-evidence early return之前，执行机制更新/dirty limit写入；不得受日志开关禁用。POST读取的是本物理步结果，新约束供下一步。首个rollout物理步之前已有初始化后的正确约束，不依赖等第一帧才锁住。

20ms一次的reward高水位更新仍按control间隔；物理锁状态按5ms更新，两者不能互相替代。一次control内部可能有unlock/relock，日志要保留物理步事件，不只留下最终bool。obs getter和reward getter不写限位、不推进模拟。

## 4. 拓扑、碰撞与单一限位所有者

### 4.1 删除路径

v29生成器路径不再创建`latch_link`、`latch_geom`、`latch_joint`及`PhysxMimicJointAPI`；同时移除它们的mass/collider和初始state。可以保留共享旧生成器对非v29任务的旧分支，但v29 A不能同时有可碰撞旧锁舌，也无需另行实现B作为兼容对照。

门的DOF集合必须正好`hinge_joint`、`handle_joint`。用名字找到索引，而非假定“第3列照旧填0”。`door_dof_state_buf`、effort target和全部直接写state的索引同步为两DOF；现有actor门角观察仍取hinge/handle两维，不新增维度。

### 4.2 self-collision处理

不能使`build_latch=False`自动等价`enabledSelfCollisions=False`。生成器早期属性和场景articulation_props后写要统一：v29采用显式door self-collision设置，保持应有门板/门框/handle接触和既有过滤，移除的仅是latch。通过最终prim和runtime collision结果核对，而非只检查单处文本。

### 4.3 B04 master与B02 temporary bounds

生成时把M作为独立customData字段写入，正常hinge bounds为[0,M]；在首个有效任务物理步前根据自然锁态写成[0,ε]。初始化允许的引擎warmup不被宣称为任务轨迹；正式自然起点写状态后必须先锁再步进。

之后唯一writer依据E派生effective bounds；B01改变closer/friction时不碰这份M，也不通过读取effective upper“保存原上限”。自然reset和staged restore都从独立本门参数恢复M。不得把90–150°变成按每control或每stage重抽的墙。

## 5. reset与bank规格

### 5.1 统一outer reset事务

对选中env完成下列事务，期间不sim.step：

1. 确认/取得同一门的参数与机制schema；已有门不重抽H/u/T_H/M。
2. 选中env临时写正常[0,M]。只影响本次reset env，不改变其他正在运行env。
3. 调用原reset流程恢复robot/door q、qdot和buffer：自然或staged各用自己的合法状态。自然door q=h=0且速度0；staged保持snapshot速度，不能借reset gate把它全清掉。
4. 最终outer hook恢复或初始化R/E、creation、release gate、事件历史，验证snapshot。
5. 恢复handle native h_rest/0velocity/0effort目标及B01本门参数所需状态；不得复活旧`15*pi/180`effort注入。B01的hinge目标归其模块，不被handle操作覆写。
6. 根据E提交[0,ε]或[0,M]，记录有效readback来源；清除上回合未提交dirty状态。之后才开始下个physics步。

当前`randomize_door_init_state=False`保持。将来如明确允许自然预开门，必须在[0,M]内构造、正确初始化E/R；不能先抽到100°再裁成90°。本轮不引入该新reset域。

### 5.2 bank版本与合法性

旧三DOF snapshot与本方案拓扑不同，直接失效；不静默去掉最后一列并假定剩余隐状态正确。不需要保留旧bank向后兼容。每条新snapshot至少登记mechanism_schema、door_parameter_id、R/E、creation high-water；现有release gate/抓握streak/阶段buffer继续完整保存。M/H/u/T_H可存整组或通过同门参数表引用，但引用身份必须可校验。

验证必须包括：同门同参数、2DOF、有限q/qdot、q不超过M（数值容差另报）、h在物理行程内；E与R不同时为true；h≥u时R必须true，h≤u−δ时R必须false，中间由已保存历史决定；E=true的snapshot q不得高于ε，微小lower误差仅限−η。已经超过捕获区的open/armed状态必须E=false。

旧参数身份、缺R历史或不合法状态拒绝入bank/恢复。可以按已有自然回退机制处理无可用snapshot的env，但标明来源，不把回退样本报成成功staged恢复。重新生成物理门或改参数范围需使对应bank失效。只修改自然`_reset_door_states`而不处理staged直接state restore不满足本规格。

## 6. reward、stage与观测契约

### 6.1 B02参数化消费者

| 当前消费者 | 选定变更 |
|---|---|
| `a2_grasp_gated_door_reward_components`的0.6rad标量 | 改为每env u(rad)；校验shape/device/finite/u>0 |
| 活跃creation固定45° | cap、归一化、初始化、high-water全改同门u |
| handle hard-limit getter/telemetry | 改为H(rad)，near-stop容差0.005rad；不要读hinge临时limits |
| `dont_push_door_handle`固定45° | 位置项改clip(1−h/H,0,1)，保留原速度项与有效stage |
| inactive历史/诊断路径 | 所有v29实际会调用的阈值消费者不得继续用45°；无关机器人45°数值不动 |

精确creation语义可以保留原rad buffer以减少迁移：

```
z_t = min(max(h_t, 0), u)
m_t = max(m_(t-1), z_t)
creation_raw = active_K5_stage3 * (m_t - m_(t-1)) / (u * control_dt)
```

这等价Δ归一化high-water，达到u后到H没有新收益。保持当前helper对active外high-water的更新规则，避免隐式改变探索合同；自然reset初始化0，新staged恢复已有值；复锁/抬手不重置high-water。原raw物理h另存，不能把z当真实观测角。

`unlatch_hold`采用同一p=clip(h/u,0,1)，near-closed 0.1rad保持奖励窗口。它不是E的代用判据。进入u只解除物理锁，Stage3→4继续要求真实q>0.25rad与握持。

### 6.2 B04三处最小收入修正

定义A=`_get_a2_stage34_hold_income_mask()`，即Stage3，或Stage4且release_permission尚未进入。沿用现有OR gate，不另建每门随M改变的release门。

1. `_reward_push_door_hinge`：将现有位置＋速度整项乘A，而非只给位置项乘A。写成`A*clip(10*qdot + clip(q,0,1.5708)/1.5708,-1,1)`。**这里的clip仅在reward值内，不写物理q。**
2. `_get_a2_grasp_gated_door_reward_components`实际覆盖后的`hold_and_drive`乘A；Stage5 continuity保持false。不要只改前半已被覆盖的helper输出。
3. `_reward_grasp`的A2原始值g：仅在`stage==4 && release_gate`时改为`min(g,0)`；其他stage不动。保留off-axis等负收益，去掉gate后正挤压力收入。

有效scale保持当前6、8、0.2；不把奖励改成追M、M−差值或q/M。现有keep-close、open-command惩罚、双指contact/squeeze、mild-distance的release mask保留，不重复叠乘；over-force/碰撞/稳定代价不因gate清零。其余stage/姿态/goal奖励不扩写。

这三处修正消除指定直接继续开大/挤压收入，不是已证明所有“开到挡止”行为都会消失。尤其Stage3的gate语义仍按原合同，gate后的恢复依赖后续任务收益；不由本轮静态设计许诺恢复质量。

### 6.3 保留的阶段条件

- Stage3→4：q>0.25rad且既有K5握持要求。
- release permission：Stage4 q≥1.2rad，进入后OR锁存。
- Stage4→5：q>1.0472rad、h<0.2rad、环境相对root_x>0。
- 既有complete/goal不改；机械M最小90°大于上述门，只证明阈值顺序可行，不证明能过门。

release permission不发张爪命令、不禁止后续接触、不暂停物理closer。实际把手回位也不自动当成手已离开。反之失去双指接触可能仍有单指回钩，不能直接当全部断触。

### 6.4 观察边界

不向actor/Student新增u、H、M、ρ、R、E、p或constraint反力真值；本轮critic也不新增这些输入。真实h/q的现有Teacher观察保持，不归一化为h/u（否则泄漏隐藏阈值）。记录内部参数用于环境正确性和事后统计不等于馈入policy。

Teacher现有质量/几何真值继续存在；Student应按其部署传感输入另立合同，本轮不改网络/Student传感。不存在“因为Teacher LSTM看得到sim force，因此Student已经具备力辨识”的结论。

## 7. 事件与遥测字段

至少分别记录：

| 事件/状态 | 精确定义 |
|---|---|
| `unlock_constraint_released` | 原E=true，提交后E=false；检测/提交/下一物理步分别有时间 |
| `relatch_constraint_engaged` | 原E=false，提交后E=true |
| `lever_retracted` | 带2°迟滞的内部R，不是物理锁舌位置 |
| `near_handle_stop` | h≥H−0.005rad；位置近限位不等同“压不动/解锁/实测止挡力” |
| `near_mechanical_door_stop` | q接近M；与E=true的窄锁上限分开统计 |
| `release_permission_enter` | 现有Stage4 gate false→true；旧hinge_at_release只能映射到这里 |
| `gripper_open_intent` | 使用现有gripper primitive正向open约定；raw primitive>0.2的进入事件，不代替断触 |
| `two_finger_contact_lost` | 由先前双指handle接触变为不再双指，连续2control样本确认 |
| `all_finger_contact_lost` | 从至少一指handle接触变为两指都无接触，连续2control样本确认 |
| `contact_reacquired` | 断触后重新出现对应handle接触；双指稳定另按既有K5统计 |
| `first_root_crossing` | 环境相对root_x首次跨过0；记录当时q/h、E、R、contact和gate |

接触使用既有handle过滤与阈值，不能拿所有robot接触力作hand-handle事件。保留raw两个指尖的接触mask/力范数、首次样本时间和确认时间。null表示无事件，不填episode尾时刻。已有处于失抓状态的staged起点登记“起点无双指”，不虚构一次loss；日志时间统一注明从恢复点还是自然回合累计计时，不能混合。

每次limit变化记录env/episode/physics_step、reason、M、effective lower/upper、h/u/H、q/qdot、R/E前后、setter调用/返回情况。参数读取、限位提交与运行反力证据分开。没有constraint反力通道就记未知，不从cap或接触总力伪造原生limit反力。

## 8. 文件级改动清单（设计，不是已实施）

| 文件/函数 | 本轮应负责的变更 |
|---|---|
| `env_rand/door.py::DoorSpawnerCfg/spawn_door` | H/ρ/u/T_H/M采样及customData；两个native joints、SI正确return drive；v29移除latch分支；自碰撞与build_latch解耦 |
| 同文件deterministic config/metadata消费者 | 恢复全参数，不从effective bounds猜M；未知schema报错 |
| `scenario_cfg/isaacsim.py::get_TaskObjCfgDict_for_door_config/TaskObjCfgDict` | 只对v29 A选择no-latch两DOF；删除latch init pattern；保持side/geometry和B01合同；handle actuator cap/targets一致 |
| `door_open_a2_base.py`初始化及name mapping | 两DOF buffer；读取immutable门参数；初始化R/E和bank schema；不扩actor_obs |
| `door_open_a2_base.py::_post_physics_substep` | 在日志early return之前加入机构更新/批量限位提交；每个physics步生效 |
| `_reset_door_states/reset_envs_idx/_validate_loaded_staged_reset_sample`与bank登记 | 统一reset事务、zero FF、恢复native目标、schema拒绝旧bank |
| `a2_v26_3_creation.py`及环境初始化/调用/记录 | v29参数化u代替45°常量；可抽成v29 helper但不保留一条仍活跃的旧归一化 |
| 环境reward/hard-limit getters | p/H消费者及三处post-gate收入修正；保留阶段门和安全项 |
| `staged_task_base.py` | 优先利用现有tracked-buffer/per-env bank；只在无法承载schema/最终事务时作最小hook，不重写通用框架 |
| `simulator/isaacsim/isaacsim.py` | 现有通用state/effort setter本可支持两DOF；消除caller硬编码，必要时仅加接口校验，不改变机器人PD |
| v29 common/env/reward配置 | 新机制与采样字段、清理活跃0.6/45°冲突配置；其他robot/camera常量不动 |
| baseline plan/TODO/decision log | 写入Pro选择及待核点，Owner确认前不擅自标IMPLEMENTED/PASS |

代码可采用一个小的`a2_v29_door_mechanism.py`承载纯状态规则，由环境负责API提交；这只是职责划分，不是要求新增复杂框架或另一个神经网络。

## 9. 有界验收点与失败处置

本轮云端完成的只有源码/配置读取、单位及采样不变量推导、离散状态规则静态检查；见`STATIC_REVIEW_CHECKS.json`。它不import IsaacLab，不代表模拟物理测试。

本地后续按Owner授权，只需围绕四类关键问题取得证据：原生窄带承载/解锁、开门回位与关门捕获、两DOF/异步reset/bank/targets、B04正常M及gate收入/事件式setter成本。无需先实现B、不需要正式训练矩阵或新增render。

当API拒绝、bounds读回错误、持续锁泄漏、半开门被收紧、跨env污染、旧bank混入或restore参数不一致时，应停止该机制的有效性声明并报告。不能把state clamp当修复；不能通过仅放宽到很大游隙换来表面稳定。可改变Pro选择的关键未知在FULL_REVIEW中明确列出。

本规格的模型能力边界：不模拟真实斜舌撞扣板的连续压缩，不模拟锁体侧压卡滞、断裂或材料门挡冲击。它仍产生真实求解约束与机器人接触响应，足以作为本轮明确选定的有限baseline机制；策略学习与sim-to-real效果仍未验证。
