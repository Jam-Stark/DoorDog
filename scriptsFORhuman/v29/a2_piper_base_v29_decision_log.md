# base_v29 决策记录

创建：2026-09-17 19:31 HKT。记录：-codex planner；决定与授权：-owner 当前会话。

V29-D001–D003 均为 **ACCEPTED / OWNER_AUTHORIZED / IMPLEMENTED**。2026-09-17（HKT）按 Owner“直接改，然后将基础改动记录”的要求完成 source、v29 配置、MERGED URDF/USD 与记录。已完成 64-env / 1-batch PPO 运行；尚无正式训练或策略质量验收。后续决定的状态分别记在各条目中。

## V29-D001：Stage5 朝向与直立姿态

Owner 决定：

- goal 位置保留 `[2,0,0.5]`。
- 改善 v28 及此前最后斜着身子走向 goal 的行为，让机身朝向与走向目标的要求一致。
- Stage5 加强 roll/pitch 保持 `0/0`。

执行路径与实现：

- [环境配置](../../gr00t/rl/config/env/door_open_a2_base.yaml)的 `target_root_pos` 已是 `[2.0,0.0,0.5]`，A282 训练 resolved config 同值。
- [环境实现](../../gr00t/rl/envs/door/door_open_a2_base.py)中 `_reward_target_root_distance` 奖励目标距离与朝目标的速度；原 `_reward_penalty_face_door` 只在 Stage0/1/2 生效。本次新增 `_reward_penalty_a2_stage5_goal_heading_l2`，仅 Stage5 生效，计算 `wrap_to_pi(actual_yaw - atan2(goal_delta_y, goal_delta_x))²`；`goal_delta` 使用扣除 `env_origins` 后的 root 位置。
- `_reward_penalty_base_roll_pitch_l2` 已在 Stage5 惩罚实际 roll/pitch；`_reward_orientation_control` 跟踪策略给出的 pitch/roll 指令，不能将它等同于保持绝对 `0/0`。
- `_stage_5_to_complete_condition` 当前只检查环境相对 `root_x > 1.5`，并不检查实际到达 goal 或最终 yaw/roll/pitch。该事实作为后续实现输入，不把新增终止门或角度阈值冒充本次已确定的参数。

新增 `_reward_penalty_a2_stage5_upright_l2`，仅 Stage5 返回实际 `roll² + pitch²`，目标为绝对 `0/0`。[v29 common](../../gr00t/rl/config/ablation/wbmanip/base_v29_common.yaml)将 heading scale 设为 `-4.0`，新增 upright scale 为 `-8.0`；原姿态项 `-2.0` 保留，因此 Stage5 同类总系数为 `-10.0`。两项均不进入 K 衰减列表，其余 stage 不受新增项影响。数值是本轮初始实现值，尚未训练调优。

完成条件仍为 `root_x > 1.5`；本次通过 reward 引导朝向和直立，未增加终点姿态门或限制横向动作。局部 tensor 验证确认 Stage0–4 掩码为零、Stage5 yaw 环绕与平方值正确；实际 PPO 运行已注册并调用两项奖励。本次一批运行未产生 Stage5 学习效果证据。

## V29-D002：把手高度覆盖范围

Owner 决定：handle 高度 randomization 改为 **`[0.90,1.20] m`**。

[v28 common](../../gr00t/rl/config/ablation/wbmanip/base_v28_common.yaml)与 A282 实际训练配置为 `a2_v26_door_handle_height_range: [0.85,0.95]`；v29 common 已改为 `[0.90,1.20]`，本次实际训练的 resolved config 同值。

Owner 对旧范围来源的追问另作历史说明；无论旧范围由何处继承，v29 新范围已经确认。不得因更高把手尚未训练而静默缩回旧区间。

来源已核对（INSPECTED）：这不是 v28 临时缩窄，而是沿用 v26 R0 acquisition 的初始范围。[v26 原计划](../v26/a2_piper_base_v26_execution_plan_R1_20260821.md)明确第一波/从 batch0 使用0.85–0.95m，将全宽0.80–1.10m后移；v27/v28继续继承该窄域。已核范围内没有证据表明主线曾把handle高度定为0.90–1.20m；本次按Owner新决定设定。

实际链路为训练配置（评估时为 checkpoint 相邻配置 + natural-start overlay）→ [v26 door selector](../../gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py) → [spawn_door](../../gr00t/rl/isaac_utils/playground/env_rand/door.py)按上下界 uniform 采样。v29 natural-start overlay 只关闭 staged reset、penalty driver 与 reward curriculum，不覆盖高度。

路径纠正：v26 selector 会提前返回 uniform 配置，并明确拒绝与显式 eval linspace/pairs 组合。另一路 linspace 的默认 1.10 m 上限不作用于本次路径；此前记录把两条路径混在一起。本轮无需修改 selector 或新增 linspace 能力。运行验证为环境成功生成和 PPO 完成，未对新范围进行成功率评估。

## V29-D003：MERGED 腕机 180 mm / 45°、视觉盒与默认姿态

Owner 决定：

- 继续使用 MERGED 装配路线，腕机改为 **180 mm / 45°**。
- 隐藏三台相机的外壳视觉包络（视觉盒），保留三台相机的碰撞。Owner 随后明确要求完整删除多余的中央包络 visual/collision/mass 等。
- arm init/reset 回到 180 mm / 45° 对应版本，让腕机在默认姿态下前视。

对应既有版本的具体姿态为 **`[0,0.10,-0.10,0,-0.52,1.57]`**（arm_j1…j6）。恢复 j5=-0.52，保留 j2/j3=+0.10/-0.10；后两者避免默认点落在既有软限位惩罚区，不回到更早的 0/0。

新 v29 URDF、rig 与默认姿态的前向运动学核对得到腕机 RGB 光轴相对 trunk 的 pitch 为 **−15.206°**，即前视兼顾下方视野。该结果是几何证据，未验证成像质量。

已实施联动：

- 180 mm 表示外壳中心相对法兰的名义高度，不是支架梁长。物理两盒、光学外参、安装间隙、质量/质心/惯量和 URDF/USD 必须一致。
- j5 变化同时影响 reset、动作零点、关节位置观测零点、姿态奖励锚点和 Stage0→1 姿态条件；不能只改变渲染相机。
- v29 入口显式选择新 [robot 配置](../../gr00t/rl/config/robot/A2_Piper/a2_piper_v29.yaml)，指向独立 [v29 asset](../../gr00t/rl/data/robots/a2_piper_v29_merged_20260917/)；默认 arm 向量已恢复。v28 原配置与资产保持为已关闭阶段的输入。
- 已有 [180/45 visual 隐藏预览说明](../../logs_eval/base_v28/side_camera_visual_only_20260917/README.md)使用 H180/F45 光学 overlay，但物理塔架仍是 H140；它隐藏了包括支架在内的13个相机视觉盒，不等于本次 v29 完整物理变更已实现，也不能不加区分扩大 Owner 的“相机外壳视觉包络”范围。
- [v29 生成器](v29_build_asset.py)沿用既有 H180/F45 的几何构建方法，直接从 canonical v28 MERGED 资产与 `U3_F45_B15.json` 生成新资产，不把临时 side-eval 路径作为训练依赖。更新腕机 support/housing 的实体变换及 tower mass/COM/inertia，URDF 与 USD 一致；保留 28 个刚体。

生成结果：外壳中心名义高度 `0.180 m`，倾角 `45°`，支架长 `0.11470001524242776 m`，静态安装间隙约 `0.001 m`，tower 总质量约 `0.150 kg`。质量沿用仿真估计，不升级为实机测量。

**相机始终只有 3 台**，rig 中是 `base_left`、`base_right`、`wrist`。三台相机外壳在 USD 设置 invisibility，在 URDF 移除 visual；其 collision 保留，支架可见。

按 Owner 追加要求，旧 D06/D33 的 `base_center_housing` 中央包络已完整移除：删除 URDF collision、USD 根层/base层/physics层对应 visual 和 collision spec，以及 rig 的 `trunk_envelope_housings` 几何记录。当前资产中不存在中央盒，不以 invisible 或 inactive 代替删除。

质量追溯：中央包络原先仅由 `add_geometry()` 生成，没有独立或并入 trunk 的质量/惯量贡献。实际 MERGED trunk inertial 来自 [v28_merge_mount_bodies.py](../v28/v28_merge_mount_bodies.py) 合并 `trunk + vpiper_main + vpiper_support + metal_plate_5mm`，质量为 `19.651 + 0.31068443156420167 + 0.10562383324311508 + 0.3375 = 20.404808264807316 kg`。删除中央盒后这组质量/惯量保持原值，无需虚构扣减。旧 rig 关于 two-base-camera mass 的文案与实际构建不符，v29 rig 已改为准确描述；没有借此新增其他质量建模。

证据：[asset build](../../gr00t/rl/data/robots/a2_piper_v29_merged_20260917/config/asset_build.json)、[资产与配置核对](asset_and_config_verification_20260917.json)。

## 记录范围

2026-09-17 19:48:23–19:49:20 HKT，物理 GPU4 执行初版 64-env / 1-batch PPO，exit=0，checkpoint `global_step=1`、`tot_timesteps=4096`。这份 [初版接线证据](runtime_logs/baseline_smoke_20260917/)发生在中央碰撞包络删除前。

中央包络删除后，同一 GPU 按相同 64-env / 1-batch 规模进行一次针对资产变化的运行复核，于 2026-09-17 19:59:05–20:00:02 HKT 完成，exit=0、step=1、4096 timesteps。见 [最终资产运行目录](runtime_logs/baseline_no_center_smoke_20260917/)及其中 `process_receipt.json`、`runtime_readout.json`。headless renderer 报 GPU Foundation 初始化错误；本次不构成渲染验证。

基础改动已完成；更直立的行走行为、新高度范围的任务成功率、正式训练预算、选种/资格规则仍待后续阶段。common 中 6000-batch 为继承默认值，本次没有启动该预算，不继承 v28 剩余预算，不启动 N01/N02。没有 Git commit/push 或实机操作。

## V29-D004：阶段方向、GPU 分工与独立工作时机

2026-09-17 21:13 HKT。状态：**OWNER_DIRECTION_ACCEPTED / EXECUTION_NOT_STARTED**。

Owner 决定建立稳定优秀的 push baseline（GPU0/1，2 seed），v29 同时推进 N01（GPU2）与 N02（GPU3），并把适用 baseline 改动同步至 pull 工作区（GPU4/5，2 seed）；GPU6 动态分配，GPU7 供监控/eval/其他任务灵活使用。完整安排统一维护在 [总体安排](a2_piper_base_v29_overall_arrangement.md)。

N01/N02 的阶段归属现已确定为 v29；等待任务1 baseline 落地后才 checkout 到各自独立 branch/worktree 开展改动。此决定未把旧 pilot/shadow 升格为方法有效性结论，尚未确定正式批数、seed编号、资格规则或执行命令。

## V29-D005：baseline 逐项讨论与 TODO 维护

2026-09-17 21:13 HKT。状态：**OWNER_WORKFLOW_ACCEPTED / DISCUSSION_OPEN**。

Owner 要求组建研究 team，先登记六项议题，再逐项交付意见、共同收敛；新动向进入 [baseline TODO](a2_piper_base_v29_baseline_TODO.md)，确认一项结论后划掉一项。Owner 确认整体 clean 后再完成 baseline 正式文档落地。当前六项均未决，本次只开展只读研究和文档维护。

## V29-D006：云端 Pro 独立判断、现实调研与 v28 验收

2026-09-18（HKT）。状态：**OWNER_HANDOFF_AUTHORIZED / REVIEW_PENDING**。

Owner要求按workflow打包baseline TODO给Pro：先独立判断B01–B06，再调研现实门从轻质到防盗/防火门的动力学/铰链/质量范围、latch范围与随机化方法、保持两指夹握且grasp frame随几何变化的把手形状族；随后追加v28阶段独立验收和v29方向建议。完整要求见[Owner问题](pro_handoff/20260918/OWNER_REQUEST.md)与[研究说明](pro_handoff/20260918/RESEARCH_BRIEF.md)。

本次workflow授权限于相关材料的review分支commit/push、选择性打包与新Drive目录上传；不提交工作区无关改动，不启动训练或修改六项实现。按Owner不生成哈希的约定，用专用review分支、时间目录、文件清单和远端一致性结果定位交付；不生成校验和清单。Pro返回的判断仍需与Owner讨论，不自动划掉TODO或形成正式计划。
