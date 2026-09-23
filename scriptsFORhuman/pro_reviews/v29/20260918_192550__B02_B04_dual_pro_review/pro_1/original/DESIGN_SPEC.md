# v29 B02 A＋B04原生门轴限位：统一设计规范

状态：**PROPOSED / NOT_IMPLEMENTED / NOT_RUNTIME_VERIFIED**。

本规范只设计选中的A和B04，不要求并行实施B。数字是工程初值，未宣称实机标定或训练可学性。源码依据编号见 SOURCE_MAP.md，解释与选择理由见 FULL_REVIEW.md。

## 1. 边界与不变量

B02以物理求解器门轴窄限位近似锁闩；B04以同一门轴的正常限位表达每门最大开角。运行中禁止写门q/qdot来“锁住”“截断”“开门”“关门”。允许的状态写入只有显式episode/reset/staged恢复边界，且必须有合法状态和配方。

B01沿用Owner批准的三档门重30–80/80–120/120–160 kg各1/3、closer有无各半及摩擦；本规范不把这些关闭来帮助A通过。门在锁住和解锁时使用同一质量、closer及摩擦配方。B03保持15°并后置；30 s与既有自然起点/Stage0速度平滑保持。不扩展B05、N01/N02实验或v28验收，不规定训练预算。

必须恒成立：

```text
0 < theta_return < theta_unlock < handle_stop
handle_stop - theta_unlock >= 5 deg
0 < capture_angle = 0.10 deg < locked_upper = 0.25 deg
locked_upper < opened_diagnostic = 2 deg < stage3_to4 = 0.25 rad
stage4_to5 = 1.0472 rad < release_gate_threshold = 1.2 rad < min(theta_max) = pi/2
active_upper == locked_upper if latch_engaged else normal_hinge_max
normal_hinge_max comes from door_recipe, NEVER from current active/soft limits
```

其中0.25°锁游隙与0.25 rad阶段阈值、0.10°捕获角与0.1 rad旧near-closed reward尺度必须分别命名，禁止同名复用。

## 2. 变量、单位与配方采样

### 2.1 推荐配置值

```yaml
# Proposed v29 keys; these are NOT existing implemented keys.
a2_v29_latch_mode: virtual_joint_limit
a2_v29_handle_stop_deg: 45.0
a2_v29_unlock_angle_range_deg: [25.0, 40.0]
a2_v29_handle_hysteresis_deg: 3.0
a2_v29_min_handle_overtravel_deg: 5.0
a2_v29_locked_hinge_upper_deg: 0.25
a2_v29_relock_capture_deg: 0.10
a2_v29_opened_diagnostic_deg: 2.0
a2_v29_normal_hinge_max_range_deg: [90.0, 150.0]
a2_v29_physics_parameter_resample: asset_generation_only
a2_v29_handle_return_max_torque_range_nm: [1.0, 3.0]
a2_v29_handle_drive_stiffness_usd_per_deg: 50.0
a2_v29_handle_drive_damping_usd_per_deg: 0.5
a2_v29_handle_drive_target_deg: -15.0
a2_v29_handle_effort_feedforward_nm: 0.0
a2_v29_handle_creation_norm_source: door_recipe_unlock
a2_v29_release_contact_free_control_steps: 3
# Reuse existing contact force threshold = 1.0 N, not a new tuned threshold.
```

不能把旧0.6 rad与上述theta_unlock同时作为两套权威。v29路径显式选择door recipe；旧常数可以留给其他历史任务，但在v29必须不可到达。机械hard-limit telemetry仍来自handle_stop，不来自theta_unlock。

### 2.2 采样时机与联合规则

每扇门在资产配置生成/分配时创建一个 `DoorRecipeV29`，而不是在`reset_envs_idx`中重抽。建议新增纯配置结构，记录：

```text
door_uid, physics_schema_version = v29_virtual_latch_2dof_v1
sampler_seed, door_index, handedness, opening_direction
mass_bin, mass_kg, closer_present, closer_parameters, friction_parameters
theta_unlock_rad, theta_return_rad, handle_stop_rad
normal_hinge_max_rad, locked_hinge_upper_rad, relock_capture_rad
handle_return_max_torque_nm, handle_return_target_rad, drive_unit_metadata
```

先按B01分配质量档/closer，再独立采样 `theta_unlock∼U(25,40) deg`、`theta_max∼U(90,150) deg`、`handle_return_cap∼U(1,3) N·m`；handle_stop固定45°，theta_return=theta_unlock−3°。左右侧和各B01组合使用同域，可分层平衡但不人为让某一侧专属大角或轻门。使用按字段分离的随机流，避免新增角度抽样悄悄重排既有质量/左右门分配；有限env数量不整除时，计数允许最小整数误差。

同一个door_uid在natural/staged/跨episode期间保持上述配方。重建资产、更换参数版本或改变door_uid才生成新配方，并使旧bank失效。新staged样本只能恢复相同door_uid与匹配配方，不能靠第三DOF截断或角度clip迁移旧bank。

### 2.3 单位表

| 层 | hinge/handle位置 | angular drive target | K / D |
|---|---|---|---|
| 人类YAML、USD RevoluteJoint作者层 | degree | degree | USD angular参数为每degree单位 |
| runtime torch / IsaacLab / PhysX articulation limits | rad | rad | SI每rad；不要把USD raw 50直接当50 N·m/rad |
| prismatic旧B | m | 不适用 | mimic旧gearing为m/degree，不是m/rad |

USD K=50、D=0.5对应每rad数值分别约2864.789 N·m/rad、28.648 N·m·s/rad，前提为本场景kg/m/s单位；其输出受1–3 N·m drive cap限制。此换算是单位换算，不是测得的真实力曲线。若未来从SI写USD应乘pi/180；从USD解释成SI则乘180/pi，不得重复转换。[API05]

## 3. 拓扑：A必须删掉什么、保留什么

### 3.1 `gr00t/rl/isaac_utils/playground/env_rand/door.py`

将selected v29资产的建模结果确定为**两个运动DOF：hinge_joint、handle_joint**。

1. 为DoorSpawnerCfg新增显式latch_mode、normal_max、handle_stop、self_collision配置/recipe接入口。历史分支可显式解析到physical_latch；v29只能解析virtual_joint_limit，互相矛盾配置报错。
2. 在资产生成时，A不创建`latch_link/latch_geom/latch_joint`，不Apply mimic。不要先创建再在模拟过程中删关节，也不要保留假第三DOF。
3. 将当前`enabledSelfCollisions.Set(cfg.build_latch)`解耦。v29没有实体latch不意味着门板/门框等应全部禁用自碰撞；使用独立开关并与ArticulationRootPropertiesCfg保持一致。保持本任务需要的panel/frame、机器人/门、gripper/handle接触。必要时只过滤确定不应相撞的具体pair，不能全球关闭碰撞来掩盖穿透。
4. USD hinge lower=0°，upper=本门theta_max_deg；handle lower=0°、upper=45°。保持现有左右局部frame翻转，使两个开门方向在该任务joint坐标中均为正。当前只覆盖out-door；不把双侧宣称为推拉方向覆盖。
5. 配方附着到每个资产/由有序env映射持有；禁止以后通过active limit反推出正常最大角。

### 3.2 `gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py`

改动必须穿透活跃的v26/v29 selector和逐env `replace` 路径，而非只改文件尾部默认DoorSpawnerCfg。清理init_state中的`.*latch.*`；保留hinge/handle ImplicitActuator，但保证被读取的最大扭矩、drive类型和单位与recipe一致。生成期读取门max角后，再由runtime在第一次物理步前设置锁区间。

### 3.3 消费者迁移

启动时按名称解析两个joint index，断言名称唯一且num_joints=2；外部观察仍按规范顺序输出`[hinge,handle]`。所有直接读取原始`[:,0]`/`[:,1]`的门奖励、遥测与观察应转向规范访问器或显式索引。

尤其处理主环境中的：`door_dof_state_buf`当前三列（约L9133）、`_reset_door_states`的`[0,1,2]`与三列effort（L29444起）、`_get_obs_door_dof_pos`（L28501）、读取raw joint_pos/vel的回柄/开门奖励（L17562起）。不要假设删除latch后PhysX内部joint排序仍与旧数组相同。

## 4. 虚拟锁闩状态机

### 4.1 持久隐藏状态

每env两个bool：

- `handle_retracted`：把手是否处于退舌分支，含3°滞回记忆。
- `latch_engaged`：虚拟锁舌是否已捕获门框，决定门轴使用窄/正常上限。

另有诊断事件计数/时戳和`last_applied_upper`，它们不能成为actor输入。`OPEN_FREE`不是额外强制状态：q>2°可记录“已离开近闭门区”，物理上从解锁起即按正常门轴范围运动。

### 4.2 事件表

| 现状/事件 | 更新 | 实际物理动作 |
|---|---|---|
| 自然闭门初始化，handle=0 | retracted=False, engaged=True | hinge上限epsilon |
| q_handle≥theta_unlock | retracted=True, engaged=False | 恢复本门theta_max |
| q_handle处于theta_return与theta_unlock之间 | 保留retracted | 不凭当前位置丢掉滞回记忆 |
| q_handle≤theta_return | retracted=False | 若门仍开着，先不收紧上限 |
| retracted=False且q_hinge≤capture | engaged=True | 窄上限；当前q必须不超过新上限 |
| 已锁住，在游隙内从capture移动到epsilon | engaged保持True | 不因q超过capture自动解锁 |
| 门开后handle回到0 | retracted=False，engaged仍False | 门正常运动，可由closer关回 |
| 压住handle关门 | retracted=True，engaged=False | 不复锁；松手且位于捕获区才锁 |

捕获不增加“必须低速才复锁”的常驻门槛，以免一次快速关门后永久无法上锁。可能出现的闭门捕获冲量由solver承担，其稳定性需local测。不得先收紧一个不包含当前q的区间，再依赖solver把半开门拉回。

### 4.3 逻辑伪代码

以下是接口合同，不是已经测试过的PhysX实现：

```python
# q_h / q_d are most recently refreshed physical joint states (rad).
# All arrays are per-env; only selected reset envs are handled during reset.
r_new = where(q_h >= theta_unlock, True,
              where(q_h <= theta_return, False, handle_retracted))
e_new = where(r_new, False,
              where(q_d <= relock_capture, True, latch_engaged))
upper_new = where(e_new, locked_hinge_upper, normal_hinge_max)

# New upper must contain q before tightening. A lower-limit violation that
# already exists must be logged as solver error, never fixed by rewriting q.
assert not any(tightening & (q_d > upper_new))
changed = upper_new != last_applied_upper
# Write one batched setter call for changed envs, then publish state/events.
```

运行时若engaged且q明显超过epsilon，是锁约束失效诊断，不是“自动解锁成功”。锁态更新不受stage编号抑制；Stage4或Stage5回到近闭门区仍可复锁。新释放gate也不能使该门永久解锁。

## 5. 原生限位API与物理步时序

### 5.1 唯一限位管理器

建议新增小模块 `gr00t/rl/envs/door/a2_v29_latch.py`，放参数/FSM纯函数；实际IsaacLab资产写入由环境或模拟器内单一adapter负责。B02/B04不得各自直接写门轴导致last-writer-wins。

以包内extension 0.54.4接口为准：

```python
# env_ids: LongTensor [M], selected environment indices.
# hinge_joint_id: resolved by name, not guessed as 0.
# limits_rad: Tensor [M, 1, 2] on the expected asset device.
limits_rad = torch.stack((torch.zeros_like(upper_rad), upper_rad), dim=-1)[:, None, :]
door.write_joint_position_limit_to_sim(
    limits_rad,
    joint_ids=[hinge_joint_id],
    env_ids=env_ids,
    warn_limit_violation=True,
)
```

必须检查`lower < upper`。PhysX标准articulation limit并未支持拿`[0,0]`直接锁死；文档提到的motion eLOCKED是另一接口，本机batched runtime可用性未获证明，本设计不依赖它。[API01]

本机setter会修改joint_pos_limits/default_joint_pos/soft_joint_pos_limits，并向PhysX传CPU tensor；它不会在该方法里重写当前物理q。因为正常/窄区间均含0，默认closed q=0应保持有效。不得把staged中途门角写成default_joint_pos，再允许该方法静默裁剪该默认值。不要用soft limit计算θ_max、锁态或成败。

调用策略：只有发生engagement切换或显式reset/recipe恢复时写；同一个physics step中的全部变化env合成一次，空集合不调用。大并行下全局事件可能每步都有，必须测实际CPU同步/传输成本。不要先绕过封装直接写root_physx_view，却遗漏Lab缓存维护；若必须优化adapter，须显式同步所有相关缓存并重新核对版本，而非本轮预设。

### 5.2 接入时序

现有控制链为`legged_robot_base._physics_step`循环 → `_apply_force_in_physics_step` → `simulate_at_each_physics_step`，后者包含`scene.write_data_to_sim → sim.step → scene.update`，然后`_post_physics_substep`。[S07,S08]

推荐在Door环境的`_apply_force_in_physics_step`中加入一次使用最新数据的latch同步，位置在实际`sim.step`之前，保留B01/机器人现有force处理顺序。reward、观察和stage更新不能成为物理锁态的唯一更新位置。

```text
q(k)已从上一scene.update刷新
→ 计算latch FSM(k)、批量写变化限位、写本步必要的被动负载目标
→ scene.write_data_to_sim
→ sim.step（机器人接触、原生限位、闭门器/摩擦共同求解）
→ scene.update 获得q(k+1)
→ post-substep记录contact/越界/事件证据
→ 下一个physics step
```

本配置200 Hz、4倍decimation（控制50 Hz）。跨阈值的事件至多在下一次离散检查生效；不能声称连续时间无延迟。若把手在一个物理步内越阈值又退回，离散采样可能看不到；本地要记录高速行为边界，不安装额外神经网络来补。

## 6. 回位负载：一个权威，不混合角度和effort

保留名义USD参数域：force-type drive，K=50 / D=0.5（每度口径），目标−15°，cap每门1–3 N·m。runtime对应handle位置target为`−pi/12` rad、速度target=0、额外effort=0；必须通过实际position/velocity target接口明确设置，不能把角度写进effort函数。

删除当前reset的`door_dof_target[:,1] = 15*pi/180`正effort写入。不要在每次reset同时产生另一份隐含回位力。在选中joint上设置handle目标，hinge目标和B01被动负载仍从其recipe持有，不能被B02的全零目标数组覆盖。

需要本地读回确认：关节解析后的stiffness/damping/maxForce、implicit actuator实际targets、额外effort=0及最终回位方向。USD−15°目标可能被运行时默认目标覆盖，所以本设计称“保留作者层名义参数、明确运行时负载”，不称“已证明与旧有效轨迹完全等价”。1–3 N·m是drive cap而非机器人手部最大碰撞力；保留原有过力保护/惩罚。

为了最小化本轮改动，不额外把回位刚度/阻尼、负载依赖解锁或handle大角度包络一起随机化。theta_unlock、cap和B01质量/closer独立抽取，机械行程约束始终先于样本发放检查。

## 7. reset、staged bank与同一物理门身份

### 7.1 新的bank合同

建议新bank schema `v29_virtual_latch_2dof_v1`，包含：

```text
door_uid + physics_schema_version + fixed DoorRecipe identity/parameters
ordered_door_joint_names + q[hinge,handle] + qdot[hinge,handle]
handle_retracted + latch_engaged
existing release_gate/root-crossing latches
creation previous position/high-water/cache contract (new theta_u normalization)
finger-contact-free streak + whether gripper contact was ever observed
physical/control tick and snapshot phase marker
existing robot/root/stage buffers needed by the current staged framework
```

包含这些字段不等于给policy增加观察。位置/速度与配方属于物理恢复，FSM是不可单靠一个处于滞回区的handle角恢复的历史。

bank保存时标明当前控制边界在最近scene.update之后、下一pre-physics同步之前。恢复时先加载快照中的滞回状态，再按恢复出的q执行一次正常的pre-physics FSM评估；不要无历史地用`q_h>=theta_u`重建retracted。这样正确处理最后一个物理步刚跨阈值、下一检查尚未应用的样本。

### 7.2 reset顺序

1. 固定本门recipe，确认待恢复样本版本、两DOF名称、q范围与recipe匹配。失败样本拒收/丢弃或按既有fallback走natural reset，禁止静默clamp。
2. 对**选中env**，在无physics step的reset事务内准备正常限位，避免前次episode锁限位与已开门恢复样本冲突。此临时准备不是解锁事件奖励。
3. 完成全部robot/task root、DOF、已有staged/recovery bank的写入。只改选中env；当前`door_dof_state_buf[:]`应改成选中索引清零。模拟器task root writer内无参数`task_obj.reset()`也应核对/改为选中env，避免全asset缓存/力重置波及其他env。
4. 自然closed起点设置q=qdot=0、retracted=False、engaged=True；初始化creation当前值/高水位而不发reset奖励。staged则加载匹配的新FSM/历史，再执行上节的下一步同步。
5. 恢复被动drive targets/effort、B01需要重施加的摩擦/负载参数；最后调用**同一限位管理器**施加与恢复后q兼容的active upper。
6. 接触sensor历史在state teleport后不能当作新的真实接触。清理选中env的接触去抖缓存；staged保存的“已释放”语义可保留作历史事件，但在第一次新物理观测确认前，不新发释放事件、不借旧接触缓存立即通过新的断触gate。阶段成功资格所需连续3次断触应由恢复后的观测重新确认。
7. 第一物理步前做有限状态/单位/两DOF/正常最大角不被改写的断言；恢复事件不计新的unlock/creation收益。

因为staged分支直接写root/joint，不只经过`_reset_object_states_callback`，必须把最终同步放在`door_open_a2_base.py`中的`DoorPregrasp.reset_envs_idx`中`super`及所有可能的bank恢复之后，并联动`_validate_loaded_staged_reset_sample`。仅修`_reset_door_states`是不完整的。[S05,S06]

当前`randomize_door_init_state=false`；其保留的旧15–100°分支若后来启用，合法自然采样范围应取`[15°, min(100°, theta_max)]`并初始化为开门未捕获；本次θ_max最低90°保证该区间非空。这是**初始化采样约束**，不是运行中强制状态clip。

### 7.3 不兼容情况

旧三DOF bank、新两DOF bank但来自不同theta_max/theta_u/质量/closer配方、没有滞回状态的中途样本、超出真实最大角的样本，一律拒绝冒充可恢复。旧checkpoint未提供也未核验；观察维度保持并不证明旧checkpoint/旧bank在新物理域可直接验收。

## 8. reward与observation一致化

### 8.1 handle creation

`a2_v26_3_creation.py`当前活跃helper把handle截断到固定0.785398并用该常数归一化。v29必须传入每env theta_unlock张量，不能只改YAML中另一项0.6。推荐保留现有位置/高水位的rad单位以减少日志合同变化：

```text
h = min(max(q_handle, 0), theta_unlock)
highwater_new = max(highwater_prev, h)
delta_highwater = highwater_new - highwater_prev
creation_raw = delta_highwater / (theta_unlock * control_dt) * existing_active_mask
```

active_mask沿用Stage3/K5有效条件；高水位更新时机沿用现有每控制间隔一次合同。theta_unlock必须为正、有界、与输入shape/device一致。解锁后余程不再增加creation，反复释放/复锁不清零highwater，不因同门重复动作刷增量。natural初值与staged加载/validator、telemetry中的归一化也同步更新；reset自身不能生成进度。

`a2_grasp_gated_door_reward_components`中的unlatch_hold pressing fraction也改为`clamp(q_handle/theta_unlock,0,1)`；旧near-closed 0.1 rad继续只是reward mask，不承担复锁判断。机械hard-stop getter/telemetry改读handle_stop，保留原hard-stop容差用途，不把它用于门轴游隙。

### 8.2 B04后的持续开门收入

使用既有episode-latched的`release_gate`，定义已有同语义mask：

```text
opening_income_allowed = Stage3 OR (Stage4 AND NOT release_gate)
```

在v29统一做到：

- `_reward_push_door_hinge`的位置项保持该mask；速度项的**正部分**也乘该mask，负部分保留，以免把门回弹/关闭的代价一起删掉。
- `_get_a2_grasp_gated_door_reward_components`中的hold-and-drive正收入同样乘该mask，而不是只修改一个旧未活跃函数。
- 不将奖励改成`q/theta_max`来鼓励每扇门开到各自挡止；原90°位置饱和的物理含义不变，只修收入时机。
- 现有过门/根部运动、碰撞、过力与腕部运动惩罚保留。不自动惩罚一切gate后的握持：重闭门器下合理hold/recontact仍应物理上允许。
- `_reward_dont_push_door_handle`改用handle_stop替代魔法45°尺度；当hinge≤0.25 rad时将该回柄收入停用，避免门已回闭时奖励阻止再压柄。物理FSM照常工作。

该最小修复去掉一个明确的“继续开门就得分”驱动，**不保证最终policy一定在最佳时刻松手**。旧gate为OR锁存，不因回弹自动重置；本设计不通过反复清gate重新发开门收入。Stage4自然恢复通路仍在，但其学习充分性需要后续证据，不能由本设计宣称。

### 8.3 观察

保持actor/critic已有输入合同，门角/把手角显式按名称输出同样两维。禁止加入theta_unlock、theta_return、latch_engaged、theta_max、closer/friction真值、归一化q/theta_unlock、限位反力oracle或unlock事件答案；不把它们隐藏进RNN辅助输入或Student蒸馏标签。

允许这些字段用于environment机制、reward和隔离的诊断日志。当前Teacher已有LSTM、hand_force和质量/几何特权量，这只是SRC事实；不等价于部署Student具备同样信息，也不授权新增网络。

## 9. 释放与过门：四个不同事件

### 9.1 定义

| 字段/事件 | 本次定义 | 不能据此声称 |
|---|---|---|
| `release_gate_first` | Stage4首次hinge≥1.2 rad，随后OR锁存 | policy已经开夹爪或手已断触 |
| `gripper_open_command` | 按既有action/target口径记录策略开夹爪命令，不生成命令 | 物理上已经脱开 |
| `finger_handle_contact_free` | 现有arm_body7/8—handle定向接触，两指都≤既有1 N判据，连续3控制间隔 | 严格数学零接触、腕部/整个机器人都离开门 |
| `stage5_enter / root_goal / clearance_verified` | 各自独立记录：阶段进入、既有root_x>1.5、额外有证据的几何通行 | 三者天然等价 |

当前ContactSensor的filter明确只有arm_body7/8，且来自normal contact force。使用`~contacting.any(dim=-1)`而不是`~both_contact`；阈值以下只可称“该传感器判据下的断触”。记录观测覆盖范围。没有全机器人—handle接触覆盖时，`all_robot_handle_contact_free`为null/NOT_MEASURED，不能填True。[S05:30045–30060]

为避免未抓过把手就产生“首次release”事件，另保存`gripper_contact_ever_observed`；两指断触条件可作阶段guard，但只有先前存在相应接触才发“从接触到释放”的事件。记录的`t_contact_free_confirmed`是3次确认后的时间；首次无接触样本时刻另记，不虚报精确连续时间脱离点。缺事件写null，而非0或复制gate时刻。

### 9.2 最小阶段/姿态联动

Stage3→4保留hinge>0.25 rad＋现有握持要求。

Stage4回默认臂姿态的惩罚开关改为：`release_gate & stable_finger_handle_contact_free`，不在只剩一指接触时启动。Stage4→5改为：

```text
existing(root_x > 0 and hinge > 1.0472 rad and handle < 0.2 rad)
AND release_gate
AND stable_finger_handle_contact_free
```

这不是脚本释放或脚本试推；policy仍可握持、开夹爪、意外失抓或重新接触。资格flag不作为物理“禁止松手”装置。早于gate的意外失抓应如实记为`contact_free_before_gate`，不能改写为合规release。

不改变最终root_x>1.5的历史指标含义，也不把它升级为全身净空PASS。90°附近是否够PiPER回收、机身过门、避免frame/door扫掠及闭门器回弹，需要实际本地物理证据；既有body/panel、arm/panel、frame接触与位姿可用于定向核对，无需新增render作为前置。

### 9.3 最大角相关遥测

按env记录不可变`normal_hinge_max`、当前`active_hinge_upper`和solver读回值；分开`locked_limit_overshoot`与`normal_limit_overshoot`。`q >= theta_max−1°`仅称`near_normal_upper_limit`（1°为诊断窗口，不改变物理），没有约束冲量证据就不称“确实撞到了门挡”。闭门锁住时接近epsilon绝不能算接近正常最大角。

记录每次gate、双指断触、重新接触、unlock/relock、Stage5/root_goal的时间和当时hinge角，以及是否接近本门真正最大角。分层结果按左右、B01质量/closer、theta_max区间输出；不把所有未知扭矩/锁态真值塞入policy。

## 10. 具体源码改动清单

| 文件/位置 | 必要改动 |
|---|---|
| `env_rand/door.py:513–632` | 选中A不建cone/latch/mimic；self-collision解耦；USD theta_max/handle_stop与recipe |
| `scenario_cfg/isaacsim.py`活跃selector及1976–2044 | recipe生成/逐env传播、两DOF init、被动drive配置 |
| 新增`envs/door/a2_v29_latch.py` | 小型参数校验/FSM/active limit纯逻辑；不引入网络 |
| `door_open_a2_base.py:9133`与门DOF所有直接消费者 | 两DOF名称索引、规范观察顺序，消除三列及裸0/1假设 |
| `door_open_a2_base.py:_apply_force_in_physics_step` | 每物理步事件判别与唯一batched limit adapter |
| `door_open_a2_base.py:reset_envs_idx / _reset_door_states / _validate_loaded_staged_reset_sample` | 完整恢复事务、配方/FSM/目标/接触去抖、旧bank拒绝、局部reset隔离 |
| `staged_task_base.py`注册buffer与加载验证接口 | 新schema字段，保留同env/同门物理身份，不只修natural callback |
| `a2_v26_3_creation.py`及主环境对应init/update/register | per-env theta_u截断/归一化、highwater与reset一致 |
| `door_open_a2_base.py:17562–17582,18341–18401` | 正开门速度/hold-and-drive与gate统一；回柄尺度及近闭门恢复mask |
| `door_open_a2_base.py:15949–15983,29884–29906` | 双指断触去抖用于Stage4姿态与Stage4→5 guard，事件分离 |
| `simulator/isaacsim.py:2818–2840` | 选中env的reset/effort语义；不得用角度冒充effort；核对目标传播 |
| v29 common/baseline、env/reward配置 | 新字段及权威来源；仅v29切换，保持B01/B03既定范围 |
| obs/exp YAML | 观察/action/LSTM结构不新增答案或网络；只核对canonical门角含义 |
| plan/TODO/decision log | 记录选择、采用/调整、证据等级、未验证项；不勾选运行/训练PASS |

## 11. 本地最小判别与失败处理

四项定向检查与FULL_REVIEW一致：约束/单位；回柄/复锁；natural与新staged恢复隔离；90°实际释放/通行语义与setter开销。覆盖关键端点及左右即可，不制定训练预算、不要求两个方案都做或庞大网格。

A若不能在约定游隙和既有负载下产生可靠锁住/复锁，先报告具体超限、时间相位、反力/接触和API读回，不以“换成[0,0]”“每步q=0”“放宽stage门槛”补洞。若是CPU更新瓶颈，报告每步调用分布和整体耗时，而不是仅贴tensor shape。必要时由Owner重新决定是否保留B；本设计不是暗含的双方案实施授权。

所有报告都须把CONFIG_PARSE/PURE_LOGIC_CHECK与PHYSICS_RUNTIME/LEARNING结果分开。当前回包不含新仿真或训练结果。
