# Pro回传的本地核对与讨论结论

2026-09-18 10:35 HKT。Main整合配置/单位、解闩/抓握几何、相机三个只读研究分工；Main核对v28事件与分母。状态：**讨论依据已整理，六项仍待Owner决定**。原报告及附件保留原样，本文件只增加本地意见。

## 阅读与核对范围

已读`FULL_REVIEW.md`、`SOURCES.md`、70行参数CSV、`HANDLE_FAMILIES.md`、独立初判及四项独立复核/媒体附件。source/config对照与既有episode核对分别见[LOCAL_SOURCE_ALIGNMENT](LOCAL_SOURCE_ALIGNMENT.json)、[LOCAL_EPISODE_READBACK](LOCAL_EPISODE_READBACK.json)。相关11个source/config/资产定义/分析文件与原交付相同；最终smoke配置和四份DEV记录也相同，当前结论无需靠旧memory代替source。

本地只核对与本轮决定相关的路径，未重跑完整trace reducer、媒体解码或实验。Pro的媒体解码声明保留为Pro证据。来源表24项不是24项全部在本地重新核验；关键API、PDQ产品和LPD轻门数据做了定向官方核对，其余产品/图读值保留Pro标注的来源等级与限制。

## 1. 驱动单位与饱和：支持单位解释，限制实际施力断言

`spawn_door`直接写USD angular DriveAPI，hinge target=−10°、k=U(1,10)、d=50、maxForce=U(2.5,12)；handle target=−15°、k=50、d=.5、maxForce=U(1,3)。当前v26 selector及最终smoke关闭D1/native摩擦；door articulation的后置actuator stiffness/damping为None，不在当前路径重写这些gain。

[NVIDIA schema](https://docs.omniverse.nvidia.com/kit/docs/omni_physics/107.0/dev_guide/schemas/usdphysics.html)与本机IsaacLab `schemas.py:661–671`支持USD angular gain按degree、runtime/SI gain按rad的换算：`k_rad=k_deg·180/π`、`d_rad=d_deg·180/π`。因此原生d=50的SI等价值约2864.79 N·m·s/rad是正确的**单位换算**，不是实机测得阻尼。本机D1 native常量也体现同一换算。

在force drive、米/千克单位、q正向表示开门且qdot≥0的条件下，`|k(−10°−q)|`在q≥2°时至少12N·m，达到所有当前cap的上界。关门qdot<0时，阻尼项可抵消或反转净请求；q=0°、k接近1且cap>10的样本也可能未饱和。**不能改写成所有时刻/两侧实际施力均等于cap。** 这些是静态驱动律推导，最终PhysX gain、实际扭矩、饱和比例、两侧符号与最终stage单位读回仍无本轮新增runtime证据。

源码入口：`door.py:531–582`、`scenario_cfg/isaacsim.py:1987–2041`、`door_open_a2_base.py:7404–7410,7510–7517`。spawn metadata只回读authoring值（`door.py:1013–1018`），不能充当post-load PhysX或逐步施力测量。

本地意见调整：此前“先沿用80–120kg”只能作为历史对照选择。若v29目标是一般现实建筑门覆盖，优先讨论轻/中/重门与闭门器有无的组合，比只扩到160kg更贴合新资料；这些分层与权重仍需Owner决定。原厂[LPD Mayfair](https://lpddoors.co.uk/products/white-moulded-mayfair-4p/)确有10/13kg的指定尺寸SKU，足以证明当前域漏掉这种轻门，不能证明中国市场的比例。

## 2. 解闩几何与机构：不能只改一个角度或stroke

Pro的高位代理latch描述成立：`door.py:592–632`中锥体位于x=−.083m、z=door_height−.1m，半径25mm、高50mm；局部滑动Y轴、30mm行程、mimic `−.03/45 m/deg`。当前改变handle高度没有将latch移到把手旁。单自由度mimic的实例名`rotX`不是独立bug证据，见[NVIDIA教程](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/robot_setup_tutorials/rig_closed_loop_structures.html)。

原厂[PDQ GT](https://www.pdqlocks.com/products/gt-cylindrical-lock)支持2¾″ backset关联41°/14.2875mm、2⅜″关联65°/12.7mm、双门19.05mm关联65°；它们是产品操作角与throw，**不是已测q_clear/q_stop或完整q→s曲线**。把30mm单改成14mm可能破坏现有代理几何，但本轮没有算出精确q_clear，也没有证明14mm必然打不开。

最小可讨论实现仍可为线性子类：handle_travel、stroke、latch/门框搭接几何及return_load联合定义；不要求首版实现死区、缩舌饱和后的自由过行程或复杂网络。是否继续代理机构、还是连同门框/扣板重建把手旁机构，由Owner决定。旧45°/30mm只用于历史比较，不构成保留旧兼容路径的要求。

## 3. 相机：样本身份和端点定义要修正

| 核查项 | 本地判断 |
|---|---|
| Pro投影表“首个Stage2” | 是合并trace中**env1**的`step_index=91 / episode_length_buf=92`；此前本地表是视频**env0**的`step_index=95 / episode_length_buf=96`。差异不仅是提前4步，不应拿两张表逐格当同姿态对照 |
| Pro的env1十二组投影 | 按对应env1源记录静态复现一致；1.20m时25°约101行余量，仍不能升级为轨迹/遮挡通过 |
| 远处0.90m下缘界 | Pro将光心偏置随倾角旋转，25°约2.317m、30°约0.999m；应细化此前固定光心高度近似的2.337/1.012m。本地逐姿态投影表已旋转光心，不受该近似修正影响 |
| 旧/新reset FK | 与本地相符：j5−.415/−.52分别为trunk相对俯角21.222°/15.206°；不是默认世界地面角 |
| 三种安装连线 | 法兰原点→壳中心4.9964°；支架梁start→end为5.1613°；支架start→壳中心为1.7444°。本轮已补核第三条，Pro的该local-only项可标静态已核；不构成改几何的理由 |

样本出处为历史有效`run_r2` trace/manifest。光路按该manifest实际K：RGB fy=1396.80859375、depth fy=446.80276489；不是硬件标称FOV或当前v29 renderer的新读回。25°仍是双方收敛的**候选**。

base两相机没有独立质量贡献属实，中央旧包络也没有质量，不能凭删除中央盒减重；其策略影响与实际装配质量仍未验证。门板guide与完整碰撞并存属实，80%是generator分支期望；该事项早已归长期TODO `DIST-01` / v28 `X-16`的Student lane，不能自动变成v29 baseline新前置或恢复render条件。Pro优先建议中将X24泛称参数校准应收窄：X24原义是G0-L locomotion的随机校准问题，不覆盖所有门参数。

## 4. 曲杆grasp frame：Pro框架可用，轴映射与现有偏置必须同步

当前grasp_target是零姿态的杆中点并通过FixedJoint绑定handle（`door.py:634–651`）。FrameTransformer另加固定四元数、pregrasp `−X`偏置，并对LEFT做side-conditioned旋转；实际姿态reward/close gate使用PiPER局部Y开合轴、Z接近轴（`door_open_a2_base.py:4934–4979,5323–5335,16029–16107,29943–29965`）。

Pro的`[a,c=t×a,t]`为右手基，但不是当前PiPER目标的直接轴排列。若a定义为TCP向把手的接近方向，可讨论映射`R_target=[−t,c,a]`，配合`p_pre=p_grasp−d·a`；必须选定一次性的左右变换与局部轴映射责任层，不能同时旋转grasp_target又叠旧mirror/固定offset。FixedJoint局部姿态也需同步。此处是可行性说明，未批准或实施。

主抓握段、截面滚转、approach/closing与可抓位置应由同一几何输出，保持同一door_handle刚体和两指有效握持语义。退化/无可抓点应作为几何定义中的无效样本明确处理，不为让训练继续而静默替换法向。当前URDF每指10N是资产声明；v29 common已配置45/45N及1300/32，构建路径写入`effort_limit_sim`，两者都不是已测硬件夹持力。70mm是差动关节行程，不是实际净开口。

## 5. v28事件窗口、分母与Pro验收

本地对四份既有逐回合文件的512条记录作一次算术核对，complete、complete中的低crossing角、crossing持握、release gate有效数和gate后力计数与Pro一致。未重跑full-trace clean/camera reducer。

| 候选/侧别 | complete/128 | complete中hinge不足 | crossing持握计数 | release gate记录有效数 |
|---|---:|---:|---:|---:|
| A282 LEFT | 126 | 0 | 18 | 126 |
| A282 RIGHT | 128 | 81 | 128 | 128 |
| A284 LEFT | 128 | 59 | 128 | 128 |
| A284 RIGHT | 126 | 74 | 126 | 126 |

三套事件不能混用：

| 量 | 当前实际定义与分母 |
|---|---|
| `hinge_at_release` | `release_gate`首次false→true时的门角，没有要求失去接触；四侧中位数约69°与1.2rad逻辑门一致。见环境`15841–15845` |
| `post_release_body_force_max` / reach的p95 | gate置位且stage≥4时累计非夹爪门板接触力，聚合仅纳入有效非null记录。不是从真实松手开始，也不能替代clean的身体力窗口。见环境`15846–15857`及`v28_reduce.py:102–104` |
| v28回位时间 | camera trace的`v28_post_release = release_gate & ~both_contact`，从首次满足该flag的已记录帧开始；在同类flag帧找arm姿态L1<0.5，未命中到最后active帧右删失。不是单纯gate时刻，也不是两指都零接触、持续断触或计划松手识别。见环境`27864–27868`、`v28_camera_metrics.py:231–245` |
| clean | complete集合中，首次root_x>0跨越的hinge≥1.0472rad，且从首次Stage3到该episode结束的身体门板力最大值≤5N。身体力来自步级trace，不能以terminal单帧或post-gate max替代。见`v28_reduce.py:67–90`、`v27_reduce.py:80–91` |

回位已观察/删失120/6、9/119、2/126、0/126沿用既有报告；风险集合不是自动128。特别不能把A284 LEFT仅2例的0.43s当成总体回位优势。S0+S5的姿态L1是六臂关节相对默认姿态的误差和，不是base roll/pitch；不应拿该量直接评价新增upright reward。

Pro“执行收尾可接受、Teacher资格未确认”的分层意见与closure一致。原三seed6000 reach1/3，主备DEV clean123/47、69/52，CONF未运行，既有v28结论不改。首次crossing持握与低开度共现只是机制线索，不证明哪个reward造成，也不能据此否定Owner看到的后来继续开到挡止。

来源边界补记：Pro证据索引E08列了`state.json`，但此次Worker交付manifest未包含该文件，应当作为历史链接而非Pro独立读取证据。候选锁、DEV启动、Owner停止/豁免与cleanup凭据已入包；该索引范围修正不改变它们支持的收尾事实。

## 6. 参数证据类型与Owner待决优先级

原始CSV按其id引用，不复制成新的“现实分布表”：M01–M11为指定产品/材料的厂家锚点；D01–D05含假定尺寸/工程域的推算；S08/C03–C06为特定样品图读，未提供速度，不能反推粘性阻尼；P01–P07、P09–P17是工程候选；P08是历史项目摩擦设定；U01–U06仍未知。国内门型权重、latch完整曲线和常用摩擦总体分布未建立。FSB尺寸图箭头/椭圆轴/曲率未核部分保持限制。

建议讨论优先级（不是执行顺序或预算）：

1. **先确定baseline要覆盖的物理与行为目标**：轻/中/重门和闭门器有无；如何使用正确单位表达drive与摩擦；区分解闩、逻辑允许释放、失去双指接触与非计划失抓。B01/B02/B04相互关联，避免只改数值。
2. **再确定最小几何与观察接口**：B03的25°候选及近远视场取舍；B05首批形状族及统一grasp/pregrasp frame；B06内参/质量模型的处理范围。DIST-01保留既定Student归属，若Owner要前移再明确范围。
3. **N01/N02沿既定baseline后独立分支推进讨论**：现有证据不要求完美Teacher，但有效失抓暴露、计划释放区分和可部署输入应共享清楚的语义。本轮不新增网络、实验矩阵或预算。

仍需未来授权或实物信息才能回答的local-only项：最终USD/PhysX gain和施力/惯量读回；真实latch/strike脱扣量及载荷曲线；当前v29 renderer/自然轨迹遮挡与成像；净开口/指垫和新形状接近几何；实机质量/effort/标定。它们限制相应能力主张，不自动阻止现在继续讨论。
