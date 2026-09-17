# v29 baseline TODO

更新：2026-09-17 21:22 HKT。维护：-codex planner；初始议题：-owner；第一轮只读研究由配置、门交互、相机几何三个focused agents完成并由Main整合。

状态：DISCUSSION_OPEN。本文是与 Owner 逐项收敛的讨论清单，不是正式 baseline plan。

2026-09-18 Owner追加：将本清单交云端Pro先作逐项独立判断，再调研现实门动力学/质量/铰链、latch范围及随机化方法、可保持两指夹握的把手形状族；同时独立验收v28并建议v29方向。任务说明见[Pro研究说明](pro_handoff/20260918/RESEARCH_BRIEF.md)。六项仍未获确认，等待本地讨论与Pro材料回传。

维护方式：新动向追加到对应条目；team 事实、建议与 Owner 决定分别标记。只有与 Owner 讨论后明确确定的事项才改为 `[x]` 并划掉标题，同时保留结论和出处。讨论结案不等于代码已经实施。Owner 确认整体 clean 后，再落地正式 baseline 文档。

总体 GPU 分工与 N01/N02 独立工作时机见 [总体安排](a2_piper_base_v29_overall_arrangement.md)。

本轮证据为source/resolved config读取、历史有效render数据与CPU静态几何计算；没有新增训练、物理/渲染运行或策略收益证据。文中的建议均未获Owner逐项确认，未改source/config/asset。

## 待讨论事项

- [ ] **B01：恢复/扩展 door randomization。** 核查 door mass、hinge drive 等当前实际配置与历史启用范围，讨论是否恢复及如何取舍。handle 高度已是 uniform `[0.90,1.20] m`，不重复实施。
  - Owner 决定：待讨论。
  - 研究关注：实际 selector/spawn/物理参数链路；mass、惯量、回弹 drive 与摩擦各自含义；不得把已有能力误报为当前已启用。
  - Team 核实（INSPECTED）：当前door panel mass已经是 `U(80,120) kg`；hinge drive maxForce为 `U(2.5,12.0)`、stiffness为 `U(1,10)`、damping固定 `50`。handle drive maxForce为 `U(1,3)`，stiffness/damping为 `50/0.5`。这些是生成链路中的参数分布，不表示实际每步恒定施加该上限的力矩。[selector](../../gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py#L1745)、[默认drive范围](../../gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py#L1985)、[质量采样](../../gr00t/rl/isaac_utils/playground/env_rand/door.py#L224)、[drive写入](../../gr00t/rl/isaac_utils/playground/env_rand/door.py#L531)
  - Team 核实：native hinge friction明确关闭，profile为null；robot link mass/PD/generic contact-friction/RFI随机化也关闭，但它们不是door panel mass随机化。[v29 resolved config](runtime_logs/baseline_no_center_smoke_20260917/config.yaml)、[native friction分支](../../gr00t/rl/envs/door/door_open_a2_base.py#L6897)
  - 历史对照：v27 L1曾用mass `[80,160] kg`、native static friction `{0,2,5}`、dynamic为static的0.75倍、viscous为0；v22的bucket还联合改变质量、stiffness、damping和drive上限。它们是历史试验分布，不代表v27/v28 baseline一直开启或已经证明有效。[v27 L1配置](../../gr00t/rl/config/ablation/wbmanip/base_v27_L1_S32.yaml)
  - Team 建议（未确认）：无需重新开启已经生效的mass/drive随机化；baseline可先沿用当前分布。若Owner希望恢复80–160kg覆盖，直接将其作为扩域决定讨论；hinge damping分布、native friction是否纳入分别决定，避免机械地恢复旧版成套bucket。这里不要求为每个参数另开实验。`penalty_driver`调的是reward curriculum，不覆盖hinge/handle物理drive。

- [ ] **B02：latch 解锁角度与转轴动力学随机化。** Owner 希望覆盖现实不同 latch 解锁角度，并让 robot 学会根据下压交互判断解锁；原始意图为“下压到压不动了就是解锁了”。
  - Owner 决定：待讨论。
  - 研究关注：解锁阈值、机械行程终点、阻力/回位与解锁后的可观测反馈是否被当前模型混为一谈；先澄清行为目标，再决定随机化维度。
  - Team 核实（INSPECTED）：当前把手机械行程固定 `0–45°`，回位目标 `−15°`、stiffness `50`、damping `0.5`；latch 是带碰撞的滑动刚体，最大缩回 `0.03 m`，mimic gearing=`−0.03/45`。实际解闩由缩回量与门框几何共同决定，没有独立的布尔解锁角开关。[生成链路](../../gr00t/rl/isaac_utils/playground/env_rand/door.py#L559)
  - Team 核实：v29 的 `0.6 rad` 是 unlatch reward 归一化/饱和尺度，不能当作物理解闩阈值；另有45°硬限位遥测常量。[配置](../../gr00t/rl/config/ablation/wbmanip/base_v29_common.yaml#L72)、[公式](../../gr00t/rl/envs/door/door_open_a2_base.py#L2134)
  - Team 建议（未确认）：支持覆盖不同下压行程和回位负载，但把“最大下压行程”“latch退出门框所需行程”“回位负载”分开定义并协调采样。对本轮正常可开启门，可保证到挡止前或到挡止时已经解闩；策略目标是交互完成解闩，不能仅把运动停滞当作解闩证据。若改变行程，reward尺度与限位遥测应同步对应样本，而非只改一个reward阈值。
  - 外部语义核对：[NVIDIA mimic 定义](https://docs.omniverse.nvidia.com/kit/docs/omni_physics/107.2/dev_guide/schemas/physxschema.html)；[Allegion关于全行程仍未充分缩回latch的原厂实例](https://kc.allegion.com/kb/article/why-doesn-t-full-rotation-of-the-ad-or-co-series-exit-trim-993-outside-lever-fully-retract-the-von-duprin-98-99-exit-device-latch/)。后者只说明不能把二者视为普遍等价，不要求本轮加入故障锁。

- [ ] **B03：重新计算 base 双 D435i 上仰角。** 当前为 15°。Owner 怀疑其沿旧 0.85–0.95 m 高度域确定；v28 render 中 1.10 m 把手已靠画面上界，需要讨论 1.20 m 覆盖。
  - Owner 决定：待讨论。
  - 研究关注：实际相机位置、RGB/depth 内外参、近远距离、机身姿态、遮挡与高度范围。旧角度来源及图像观察先保留为待核事实，不预先指定新角度。
  - Team 核实（INSPECTED/静态计算）：base外壳中心相对trunk是 `[0.025,±0.155,0.190] m`、上仰15°；RGB/depth光心分别偏离外壳中心，不能用同一光心替代。[当前rig](../../gr00t/rl/data/robots/a2_piper_v29_merged_20260917/config/camera_rig.json#L16)。已证明15°被继承，未证明它最初专为0.85–0.95m设计。
  - Team 核实：有效v28预览的真实renderer K为RGB `fx=fy=1396.80859`（1920×1080，约69°×42.2726°），depth `fx=fy=446.80276`（848×480，约87°×56.4849°）。rig名义fy分别是1406.74809/432.97146；本机IsaacLab的square-pixel实现使两者不同，计算采用实际manifest K。[有效manifest](../../logs_eval/base_v28/side_video_a282_6000_h180_h110_20260917/run_r2/video_manifest.json)、[官方Camera源码](https://isaac-sim.github.io/IsaacLab/main/_modules/isaaclab/sensors/camera/camera.html)
  - Team 计算：冻结该有效预览首个Stage2（step96、1.92s）的机器人姿态与目标XY，仅替换把手高度并调整相机仰角，1080行RGB中的投影行如下。这是静态投影，未重跑高把手下的策略轨迹。

| 上仰角 | 高度0.90m | 高度1.10m | 高度1.20m |
|---|---:|---:|---:|
| 15° | 402.4 | 56.9 | −100.7（越过上缘） |
| 20° | 526.2 | 191.0 | 42.8 |
| 25° | 649.7 | 319.4 | 177.5 |
| 30° | 774.9 | 444.2 | 306.3 |

Team 建议（未确认）：提高仰角有依据；优先讨论20–25°，近距离1.20m把手覆盖优先时倾向25°。但在水平trunk、RGB光心约0.742m的剖面计算下，25°会使0.90m目标在约2.337m以外掉出画面下沿，30°则约1.012m即出现该限制。需Owner共同取舍近高把手与远低把手/下方视野，不凭单帧批准最终倾角。已排除首次位姿读取受干扰的录制，只用`run_r2`有效记录。

- [ ] **B04：门最大张开角随机化。** Owner 观察 v28 会持把手开到最大角度才释放，提出把最大开角随机化为 90° 至当前上限，以覆盖现实门的不同限位。
  - Owner 决定：待讨论。
  - 研究关注：当前 joint limit、stage/release/hold 与奖励阈值的关系；较小机械限位是否使固定阈值不可达；区分改变环境上限与改变何时松手的行为目标。
  - Team 核实（INSPECTED）：当前机械上限 `150°`，闭门 drive target `−10°`。[门轴构建](../../gr00t/rl/isaac_utils/playground/env_rand/door.py#L521)。当前 Stage3→4 约 `14.3°`、release gate `1.2 rad≈68.8°`、Stage4→5 开度门 `1.0472 rad≈60°`，还分别需要握持/释放及root位置条件；因此 `90°` 本身没有被这些固定角度阈值排除。[配置](../../gr00t/rl/config/ablation/wbmanip/base_v29_common.yaml#L69)、[阶段条件](../../gr00t/rl/envs/door/door_open_a2_base.py#L29804)
  - Team 核实：release gate 后 hinge位置收入关闭，但 `hold_and_drive` 仍奖励有效双指握持与正门速；收臂惩罚又要求已经失去双指接触才生效。这是继续持把开门的收益线索，尚未证明是v28观测行为的因果来源。[hold条件](../../gr00t/rl/envs/door/door_open_a2_base.py#L15123)、[门角奖励](../../gr00t/rl/envs/door/door_open_a2_base.py#L17537)、[握持驱动奖励](../../gr00t/rl/envs/door/door_open_a2_base.py#L18360)、[收臂条件](../../gr00t/rl/envs/door/door_open_a2_base.py#L15942)
  - Team 建议（未确认）：支持讨论 `U(90°,150°)` 的机械限位变化，保留按实际通行需求表达的释放/过门条件。随机终点仍可能得到“开到各自挡止才松手”；如果Owner还希望改变这一行为，再单独讨论release后继续握持的收入。当前不把提前松手另立为已批准要求，也未验证90°门的实际通行和回弹质量。

- [ ] **B05：handle 几何族与概率末端回钩。** 保持当前圆截面直杆的大体抓握方式，讨论椭圆截面、曲线/不规则轮廓与不同现实把手形状，并按概率启用末端回钩。
  - Owner 决定：待讨论。
  - 研究关注：已有 generator 能力、可抓握区域、碰撞与 visual 一致性；形状变化对抓握目标定义和 push/pull 的影响。先讨论具体形状族，不自动改变抓握方式。
  - Team 核实（INSPECTED）：实际generator为圆截面Capsule杆，长度 `0.11–0.14 m`、半径 `0.011–0.015 m`；**末端已存在50%概率回钩**，长度 `0.04–0.06 m`，朝向门板。`door_handle_type`枚举当前仅被采样/记录，并未按knob/lever/pushbar分派几何。[尺寸与概率](../../gr00t/rl/isaac_utils/playground/env_rand/door.py#L305)、[几何构建](../../gr00t/rl/isaac_utils/playground/env_rand/door.py#L426)
  - Team 核实：当前grasp_target固定在杆中点、绑定同一handle刚体；改变杆中心线后需要根据真实可抓握段更新目标位置/方向。[目标生成](../../gr00t/rl/isaac_utils/playground/env_rand/door.py#L634)
  - Team 建议（未确认）：先讨论“椭圆截面直杆”和“轻微弯曲且保留中央抓握段”两个有限形状族；保留两指相向夹握与同一handle接触语义。回钩概率单独决定，不当作从零新增功能。visual/collision、抓握frame与质量建模同步说明；自由不规则形状暂不无限扩张到新抓法。

- [ ] **B06：相机光路与 MERGED 几何精度。** 追溯下表与当前 v29 实体/rig 的差异，核清坐标系、reset 姿态和光学轴定义，再讨论需修正的几何。
  - Owner 决定：待讨论。
  - Owner 提供的核对结果（保留原始输入；team已用当前资产配旧reset复现，见下表后说明）：

| 检查项 | Owner 提供结果 | 原判断 |
|---|---|---|
| 夹爪开合轴与地面法线 | reset 相差 28.77° | 不对地竖直 |
| 图像水平轴与夹爪开合轴 | 89.95° | 基本垂直，偏差约 0.046° |
| 图像水平轴与地面 | reset 倾斜约 0.00018° | 初始画面基本水平 |
| 180/45 外壳中心—安装端中心连线与开合轴 | 相差 1.74° | 不是严格平行 |
| 180/45 光轴相对水平面 | reset 向前下俯 21.22° | 朝前，非水平前视 |

Team 核实（CPU静态FK）：同一当前URDF/rig下，Owner表的全部数值对应旧reset `j5=−0.415`；当前 `j5=−0.52` 得到下表。光轴俯角变化 `6.01606°` 正好等于 `0.105 rad` 的reset差，不是两套光学定义冲突。[当前reset](../../gr00t/rl/config/robot/A2_Piper/a2_piper_v29.yaml#L135)、[URDF关节链](../../gr00t/rl/data/robots/a2_piper_v29_merged_20260917/a2_piper.urdf#L1277)、[生成器](v29_build_asset.py#L44)

| 检查量（trunk参考系） | 旧j5=−0.415 | 当前j5=−0.52 |
|---|---:|---:|
| 开合轴与trunk法线夹角 | 28.77397° | 34.79002° |
| 图像横轴与开合轴夹角 | 89.95413° | 89.95413° |
| 图像横轴相对trunk水平倾斜 | 0.0001759° | 0.0002225° |
| 外壳中心—安装端中心连线与开合轴夹角 | 1.744408° | 1.744408° |
| 光轴相对trunk水平面俯仰 | −21.22225° | −15.20619° |

这些静态量只有在trunk水平时才能直接称“相对地面”；实际world角度需组合trunk姿态。1.744°是确实存在的安装连线差，但该连线不等于光轴或支架梁轴；0.046°是图像横轴相对开合轴的非正交差，不是画面滚转。Team建议（未确认）：优先统一rig与实际renderer内参口径、视场/遮挡需求；没有安装平行度要求或可见问题时，不为凑零改掉现有几何。光学世界姿态精度、有效深度与成像质量仍未获本轮运行验证。

## 已确认结论

尚无。本轮六项均待 Owner 讨论确认；已有 V29-D001–D003 实施状态沿用 [决策记录](a2_piper_base_v29_decision_log.md)。
