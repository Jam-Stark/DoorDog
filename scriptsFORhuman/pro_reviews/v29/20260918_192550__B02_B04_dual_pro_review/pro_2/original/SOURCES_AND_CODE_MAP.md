# 来源与定向源码索引

查阅日期：2026-09-18。仅使用本次Worker包、对应专用分支和下列一手API/产品资料。所有新参数均在正文单独标为工程初值。没有生成哈希清单。

## 本次身份与获取范围

仓库：https://github.com/Jam-Stark/DoorDog  
分支：`codex/v29-b02-b04-pro-20260918`  
提交主题：`Prepare v29 B02 and B04 Pro decision handoff`  
提交时间：`2026-09-18T17:14:54+08:00`  
输入release：`20260918_170419__b02_b04_decision`。Drive目录只用于读取输入，没有上传Pro结果。

两个普通ZIP分别解压；35+10个包内文件按manifest逐项检查路径与字节数。源码是定向函数审阅，不宣称对无关历史分支逻辑逐行审计。大文件`door_open_a2_base.py`的一次GitHub内容API返回空正文，因此该文件以完整ZIP字节为依据；不是把空正文当作核对成功。小文件及门构造源码另由GitHub连接器抽核。没有未取得的本轮必要包内材料；未提供的checkpoint、完整资产、GPU日志、硬件状态及新运行不在已读取范围。

## S01：门与把手的当前物理构造

`gr00t/rl/isaac_utils/playground/env_rand/door.py`：
https://github.com/Jam-Stark/DoorDog/blob/codex/v29-b02-b04-pro-20260918/gr00t/rl/isaac_utils/playground/env_rand/door.py

定位：397–491门板/handle质量与碰撞；513–632自碰撞、hinge150°、handle45°、回位drive、cone/prismatic/mimic；约704行articulation属性后写；996–1028 customData；1144起deterministic配置恢复。

## S02：当前实际配置与场景装配

`gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py`：
https://github.com/Jam-Stark/DoorDog/blob/codex/v29-b02-b04-pro-20260918/gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py

定位：1760–1845 v26 selector；1976–2050 spawner、自碰撞、三joint initial state、ImplicitActuatorCfg。当前入口固定push/out，左右门由joint frame处理。

`CURRENT_RESOLVED_CONFIG.yaml`在本次handoff目录内，是CPU配置解析，不是运行记录：
https://github.com/Jam-Stark/DoorDog/blob/codex/v29-b02-b04-pro-20260918/scriptsFORhuman/v29/pro_handoff/20260918_b02_b04/CURRENT_RESOLVED_CONFIG.yaml

主要核对`env.config`、`rewards.reward_scales`、`obs.obs_dict`、`simulator.config.sim`。对应common、env、reward与exp YAML在source包中。局部解析结果见`STATIC_REVIEW_CHECKS.json`。

## S03：环境、reward、事件与reset

`gr00t/rl/envs/door/door_open_a2_base.py`（以ZIP为阅读authority）：
https://github.com/Jam-Stark/DoorDog/blob/codex/v29-b02-b04-pro-20260918/gr00t/rl/envs/door/door_open_a2_base.py

函数名优先于将来可能变化的行号：

| 位置 | 内容 |
|---|---|
| 2089–2145 | `a2_grasp_gated_door_reward_components`，0.6rad标量与near-closed定义 |
| 2210–2300 | hold-income mask和release gate的OR锁存 |
| 5846附近 | handle hard-limit getter |
| 8247–8340、9133–9135 | creation状态/bank登记；三DOF buffer |
| 9534起 | `_post_physics_substep`，已有early return，新增机制不能放在其后被跳过 |
| 14565–14623 | creation初始化、固定45°截断与更新调用 |
| 15140–15160 | `_get_a2_door_income_hold_mask`，不是release gate mask |
| 15796–15860 | `hinge_at_release`在gate首次进入时记录 |
| 16741–16813 | close/open-command、双指、squeeze收入已有release mask；over-force不被mask |
| 16816–16854 | `_reward_grasp`的A2正挤压力收入没有release mask |
| 17028–17048 | creation、unlatch_hold、hold_and_drive活跃入口 |
| 17563–17581 | dont_push_handle固定45°；hinge位置收入mask但速度收入未mask |
| 18341–18415 | grasp-gated components随后覆盖hold_and_drive的实际路径 |
| 28484–28504 | privileged_door_info和door_dof_pos观察 |
| 29031起、29299起 | outer reset与object reset |
| 29444–29468 | 三DOF状态写入；`15*pi/180`送进effort接口 |
| 29855–29907 | Stage3→4、Stage4→5与complete条件 |
| 30196–30202 | `_apply_force_in_physics_step` |

## S04：活跃creation helper

https://github.com/Jam-Stark/DoorDog/blob/codex/v29-b02-b04-pro-20260918/gr00t/rl/envs/door/a2_v26_3_creation.py

全文件：常量`A2_V26_3_HANDLE_NORM_RAD=0.785398`；当前角/high-water截断、增量与control_dt归一化。

## S05：reset bank与真正物理步

https://github.com/Jam-Stark/DoorDog/blob/codex/v29-b02-b04-pro-20260918/gr00t/rl/envs/base_task/staged_task_base.py

约593–725：每env/stage恢复robot/door的root、joint state和登记buffer；staged路径不等同自然reset。

https://github.com/Jam-Stark/DoorDog/blob/codex/v29-b02-b04-pro-20260918/gr00t/rl/envs/legged_base_task/legged_robot_base.py

1114–1125：4个实际物理步，每步PRE→simulate→POST。

https://github.com/Jam-Stark/DoorDog/blob/codex/v29-b02-b04-pro-20260918/gr00t/rl/simulator/isaacsim/isaacsim.py

2824–2840：state setter与effort setter不同；2910起：scene.write_data_to_sim→sim.step→scene.update。

## S06：本机IsaacLab setter节选

输入包`dependency_evidence/ISAACLAB_LIMIT_API.md`，采集2026-09-18，extension version **0.54.4**，原文件`/home/baoquanc/workspace/IsaacLab/source/isaaclab/isaaclab/assets/articulation/articulation.py`710–768。

完整方法`write_joint_position_limit_to_sim`已读。它更新limits/default/soft缓存，并把limits缓存转CPU调用PhysX。其default位置clamp不是当前模拟q的clamp。只证明接口内容，不证明窄限位的实际效果。不要以网上main/3.0 API替代该本机接口。

## S07：PhysX原生限位约束

NVIDIA PhysX SDK **5.8.0**，`PxArticulationLimit`：
https://nvidia-omniverse.github.io/PhysX/physx/5.8.0/_api_build/structPxArticulationLimit.html

“Detailed Description”：lower严格小于upper；等值需motion eLOCKED及相应joint frame；旋转轴单位rad。本报告没有假定本机已暴露并验证动态eLOCKED接口。

## S08：USD单位与drive定义

NVIDIA Omni Physics **107.3**，UsdPhysics Schema：
https://docs.omniverse.nvidia.com/kit/docs/omni_physics/107.3/dev_guide/schemas/usdphysics.html

`UsdPhysicsRevoluteJoint::GetLowerLimitAttr/GetUpperLimitAttr`单位degree。
`UsdPhysicsDriveAPI::GetTargetPositionAttr/GetTargetVelocityAttr/GetStiffnessAttr/GetDampingAttr/GetMaxForceAttr`给出角度、角速度、角向gain、cap单位及力/加速度drive区别。采用force-type drive，米/千克/秒场景；SI→USD angular gain乘π/180。本文是模型参数设计，不据USD author值宣称运行时力矩实测。

## S09：tensor批量limit接口

NVIDIA Omni Physics **107.3**，Python tensor API，`ArticulationView.set_dof_limits`：
https://docs.omniverse.nvidia.com/kit/docs/omni_physics/107.3/extensions/runtime/source/omni.physics.tensors/docs/api/python.html

data为全view `(count,max_dofs,2)`，indices选articulation；不支持仅稀疏传单个DOF数据，重复indices可能产生未定义行为。使用本机IsaacLab上层setter，不直接越过缓存。

## S10：原厂操作角，不是硬止挡/精确解闩曲线

PDQ，**GT Grade1 Heavy Duty Cylindrical Lock**，网页Specifications表（无页码）：
https://www.pdqlocks.com/products/gt-cylindrical-lock

标准2¾英寸backset列41°操作角，其他所列机构/选项列65°。同页latch throw有½、9/16、¾英寸选项。产品说明不提供机械硬挡止、开始解闩或负载下精确解闩角的测量曲线。因此不能把41/65直接当本报告的unlock/stop采样端点，更不能当国内频率。

## S11：IsaacLab actuator目标与state的区别

官方 **v2.1.1**源代码（交叉解释，不替代本机版本）：
https://isaac-sim.github.io/IsaacLab/v2.1.1/_modules/isaaclab/assets/articulation/articulation.html

`set_joint_position_target`、`set_joint_velocity_target`、`set_joint_effort_target`只填目标缓存，经write_data_to_sim传播；implicit actuator目标进入物理求解。本报告要求在本机核对同名方法并读回实际target/gain，避免只修改USD后又被运行时目标覆盖。

## S12：本地建议与旧Pro

本次`LOCAL_CONTEXT_AND_OPTIONS.md`、baseline plan §5/§6、decision log和旧Pro报告B02/B04相关段落均只作为比较材料。旧Pro目录：`scriptsFORhuman/pro_reviews/v29/20260918_102906__baseline_and_v28_pro_review/original/`。其v28验收、相机25°候选及其他六项研究不纳入本轮决定。
