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

## V29-D007：Pro原包接收与本地只读解析

2026-09-18 10:41 HKT。状态：**RECEIVED_AND_RECONCILED / SIX_ITEMS_OPEN**。

Owner上传`pro_delivery__full_review (2).zip`并要求保留原包/原文，先读报告、来源、参数和独立附件，再重点核对驱动单位/饱和、解闩几何、相机参考系、形状grasp frame及v28事件窗口/分母；只将结果追加TODO供Owner决定。

本次原包与12份原始文件已存[独立归档目录](../pro_reviews/v29/20260918_102906__baseline_and_v28_pro_review/README.md)。相关source/config与原交付一致，512条既有DEV记录的核心算术与Pro相符；语义修正及local-only范围见[本地核对](../pro_reviews/v29/20260918_102906__baseline_and_v28_pro_review/LOCAL_RECONCILIATION.md)。尤其补清不同env的相机投影、三种安装连线、release gate/身体力/回位三套窗口及当前45N finger配置。

六项TODO均未确认。Pro工程初值、产品锚点与现实分布分开记录；v28原科学结论、Teacher/G7和render豁免不变。本次没有代码/配置/资产实施、训练/仿真/评估、预算制定、硬件或Git操作；等待Owner后续明确决定。

## V29-D008：B06当前init/reset setup确认PASS

2026-09-18 11:48 HKT。决定：-owner；记录：-codex planner。状态：**OWNER_ACCEPTED / B06_PASS**。

Owner同意Pro对当前init/reset setup的判断。保留现有MERGED H180/F45、三台相机、arm init/reset=`[0,.10,-.10,0,-.52,1.57]`及对应光路定义，不为安装连线夹角凑零修改几何。baseline TODO B06勾选并划掉。

PASS范围是当前setup接受；不追溯改Pro原文，不把它写成新的实机/成像质量结果。B03倾角及已有Student归属议题独立处理。

## V29-D009：承接side window已落地的时间配置

2026-09-18 11:48 HKT。依据：-owner转述side window已实施结果；本地已核对current config。状态：**ACCEPTED / IMPLEMENTED_IN_SIDE_WINDOW**。

| 项目 | 当前配置 |
|---|---:|
| 整集时限 | 30s |
| Stage0 | 525步 / 10.5s |
| Stage1–4 | 各150步 / 3s |
| Stage5 | 300步 / 6s |

控制周期为200Hz物理步×4 decimation，即控制dt=.02s。此前最终smoke resolved为整集20s、stage `[350,100,100,100,100,200]`，各stage现增加50%。保留`award_remaining_time_on_advance=true`及既有剩余时间结转实现。本轮只核对并记录，不覆盖side window已完成改动。

## V29-D010：B07自然起点扩域与朝把手联合yaw

2026-09-18 11:48 HKT。范围认可/实施授权：-owner；实现与记录：-codex planner。状态：**ACCEPTED / IMPLEMENTED / B07_PASS**。

Owner认可side window建议，并授权本地认同后直接落地。采用门root坐标中的法向距离`[1.2,4.0]m`、横向偏移`[−.5,.5]m`；yaw围绕闭门主握杆中心的水平方位±10°，同时在门法向±35°以内。三相机保持本次原setup，base上仰15°。

实施：v29 common更新现有distance/lateral/relative-yaw范围，增加`a2_v29_natural_start_handle_yaw_jitter_rad=π/18`。先采位置，再计算β并在`[β−π/18,β+π/18]∩[−7π/36,7π/36]`均匀取yaw；不独立组合、不事后裁剪。在当前门宽/杆长/轴长/把手边距域内，最大|β|约39.88°，最窄交集约5.12°。

reset生命周期先robot后door，因此不用实时FrameTransformer或上轮handle body pose计算朝向。初始化时沿现有USD变换API缓存闭门`grasp_target`在door坐标系的位置，在自然reset使用；门root固定，仅在最终放置时合成世界姿态。这样跟随已生成抓握几何，不在reset另写一套直杆尺寸公式。显式target-state与staged恢复不改变；natural eval继承当前范围，Student观察接口没有增加目标真值。

既有依据为Owner提供的side window静态投影摘要：覆盖双侧及门宽/把手尺寸/高度边界，body height0.47–0.55m、pitch±3°网格仍由至少同一台相机的RGB/depth覆盖主握杆包络，最差约10%边缘余量；没有声称已含自身遮挡、Student裁剪/降采样或真实深度噪声。本轮未重算该视场网格。

本地证据：[resolved config](implementation_evidence/init_range_20260918/resolved_config.yaml)、[CPU实施读数](implementation_evidence/init_range_20260918/implementation_readout.json)。CPU调用真实配置解析路径及生产yaw分支，1218个几何边界网格样本符合角窗、shape/dtype/device与区间非空；未启动Isaac/训练/render，不声称定位成功率或策略质量通过。Stage0远距0.5m/s仍是建议，本次保持原0.3m/s。

## V29-D011：按最远起点的时间预算提高Stage0目标速度

2026-09-18 14:44 HKT。授权：-owner要求判断0.3m/s是否够用，不够则直接改0.5；判断与实施：-codex planner。状态：**AUTHORIZED_DECISION / IMPLEMENTED / STATIC_PASS**。

决定将Stage0走近门的速度奖励目标提高到0.5m/s。最远门法向4m起点，到距离把手约0.7m的站位仍需约3.2–3.4m（视把手偏移/横移而变）；0.3m/s理想匀速需要约10.7–11.3s，已无起步、纠偏和停稳余量。Stage0预算只有10.5s，剩余时间结转只能继承前一stage剩余时间，不能从后续阶段预借。按3.3m举例，0.5m/s理想匀速为6.6s，留约3.9s余量。这是运动学预算判断，不是实际策略速度/成功率证据。

实际路径：`_reward_walk_to_door`直接读取独立的`a2_stage0_target_root_vel`；基础env声明0.3，v29 common覆盖0.5。该参数是速度跟踪奖励目标，不是强制写入root速度或新增Student观察。进入站位带后，原有target_dir归零，Stage0→1仍要求base command停稳和arm默认姿态。`_reward_target_root_distance`继续使用原`target_root_vel=0.3`，只作用Stage4/5；没有把开门/过门一起提速，也没有新增距离分段速度曲线。natural eval沿用checkpoint配置继承路径。

验证：运行真实训练入口的`--cfg job --resolve`，确认Stage0=0.5、Stage4/5=0.3、Stage0预算10.5s、`award_remaining_time_on_advance=true`；source一次AST解析通过。现有指令映射使用0.25 scale，forward/lateral物理clip均为0.5m/s，0.5目标在既有范围内；未修改底盘限幅。没有新增测试、训练、仿真、render或Git操作。B01仅将三项讨论建议写入TODO，未修改门动力学或勾选B01。

## V29-D012：B01范围确认并开始落地baseline plan

2026-09-18 15:08 HKT。范围决定：-owner；联合工程设计：-codex planner。状态：**OWNER_SCOPE_ACCEPTED / B01_DECISION_PASS / PHYSICS_IMPLEMENTATION_PENDING**。

Owner选择门板质量30–80与80–120kg各1/2；有/无闭门器各1/2，有闭门器含不同回关强度；门轴松紧加入并与已有hinge drive随机化联合设计。取代14:44提出的三档各1/3建议。Owner同时要求开始落地v29 baseline plan，因此[新plan](a2_piper_base_v29_baseline_plan.md)先收录已确认部分，B02–B05继续讨论，整体未冻结。

本地联合设计在plan §2维护：质量×闭门器形成四个等权组合；复用native drive，用回关力矩T与参考速度omega_ref构造SI k/d，再转USD degree口径；无闭门器drive置零但保留native摩擦；温和static/dynamic/viscous摩擦作为独立耗散项。全部工程初值与Owner范围决定区分，不生成新的试验预算。B01物理代码未修改。

Owner询问回关是否很快、baseline能否学会或留N02。本地公开回答：回关表示存在持续关门方向的负载，快慢由完整动力学决定；建议纳入baseline共同门域，N02研究额外交互历史适应。当前LSTM与门角/接触反馈支持该设计判断，但不保证学会；Teacher质量真值输入不等于Student可部署感知。实际source与证据边界见plan §3；讨论摘录保存在[novelty记录](../novelty/conversations/20260918_codex_b01_n02_excerpt.md)。没有改N02实现/资格结论或启动方法实验。

## V29-D013：Stage0以2m为中心平滑切换0.5/0.3m/s

2026-09-18 15:08 HKT。行为要求与速度澄清：-owner；实施：-codex planner。状态：**OWNER_ACCEPTED / IMPLEMENTED / STATIC_PASS**。

Owner明确“指0.5 / 0.3 m/s，在2米附近平滑过渡”。以door root固定yaw坐标下的法向距离为准，1.8m内目标0.3，2.2m外0.5；中间使用`smoothstep(u)=3u²−2u³`，2m处0.4，两个端点斜率为0。过渡带0.4m是本地实现选择。`target_speed (N,)`广播乘原`target_dir (N,3)`，保留站位带内目标方向归零及原stage0→1条件。未改变Stage4/5目标0.3、奖励权重、时限或动作上限。

实施：[v29 common](../../gr00t/rl/config/ablation/wbmanip/base_v29_common.yaml)追加近距目标与过渡距离；基础env提供明确默认配置；`_reward_walk_to_door`使用现有`get_task_root_state`、`yaw_quat`、`quat_apply_inverse`路径。真实入口`--cfg job --resolve`和一次source AST解析通过；未添加测试、进行仿真/训练或验证实际步态加减速。B01仅落地计划，不能与本项速度代码实现混淆。

## V29-D014：B01增加120–160kg第三档并更新联合配方

2026-09-18 15:27 HKT。质量域决定：-owner；联合设计更新：-codex planner。状态：**OWNER_ACCEPTED / PLAN_UPDATED / PHYSICS_IMPLEMENTATION_PENDING**。

Owner要求增加120–160kg，三档各1/3。当前质量域为30–80、80–120、120–160kg；替代D012的两档各半。有/无闭门器仍各半，因此质量×闭门器从四格改为六格、各1/6，左右侧目标配比一致。有限env数使用尽量平衡的整数分配，等权指采样设计而非要求改变env总数。

联合适配见[plan §2](a2_piper_base_v29_baseline_plan.md)：先选质量档、再档内uniform，实际惯量沿质量/几何生成；新增薄板近似量级说明，120–160kg档约25.60–64.53kg·m²（宽0.8–1.1m，非PhysX读回）。三档共享T=2.5–12N·m、omega_ref=.15–.40rad/s及已有温和摩擦域，k/d仍由T与参考速度联动；不按质量自动抬高drive或强制速度来抵消重门响应。参考速度仍是忽略惯性/摩擦的准静态设计量，不能承诺重档与轻档具有相同回关时长。

本轮仅更新plan、TODO、当前入口与memory；source、训练配置及物理资产未修改，未新增测试、训练、仿真、预算或Git操作。原D012保留为历史决定，后续实施以D014及当前plan为准。

## V29-D015：B02选择软件虚拟锁闩方向，角度建议待决定

2026-09-18 16:45 HKT。建模方向：-owner；source澄清与方案整合：-codex planner及两路只读team。状态：**SOFTWARE_LATCH_DIRECTION / ANGLE_DISCUSSION_OPEN / NOT_IMPLEMENTED**。

Owner询问当前handle角度如何解锁、随机范围0–45°或20–60°及学习难度，并明确希望软件定义解锁、不仿真实体锁舌内部机构。本地澄清当前是高位cone碰撞锁舌+mimic，确实通过handle联动与门框接触决定解闩；“没有布尔开关”不表示latch不锁门。软件方案需要替换现有代理，不是保留一个已存在的软件解锁分支。

team比较了维持45°行程的小幅方案与扩展角度域；Main推荐解锁`U(20°,60°)`、机械止挡=`解锁角+5°`，每门固定。该推荐未获Owner最终确认。角度逻辑上保证到止挡前已经允许开门，baseline可采用压到底再试推；推不动还可能来自B01重门/闭门器/摩擦，不能作为未解锁真值。参数/锁态留在环境内部，不加入actor/Student，不硬编码试推动作。

软件锁闩建议用原生门轴有限游隙约束与正常限位切换，保持门的动力学/接触反馈；PhysX普通limit要求low<high，不能声称`[0,0]`已可用。半开门不因handle回位被锁住，回关后的复锁语义仍待具体确定。自然/staged reset、锁态恢复和删除旧第三DOF假定必须随实现同步。奖励需同步当前0.6rad尺度及creation路径固定45°截断，不能仅改配置中的一项。具体建议与API/Pro出处见[plan §5](a2_piper_base_v29_baseline_plan.md)。

本轮只读source/API及更新讨论文档；B02未标PASS，未改source/config/asset、添加测试或启动仿真/训练/方法实验。B01三档与D013速度决定不变。

## V29-D016：B02重新开放二选一，交Pro独立决策

2026-09-18 17:04 HKT。授权与范围：-owner。状态：**OWNER_PRO_HANDOFF_AUTHORIZED / DECISION_PENDING**。

Owner要求B02打包给Pro，在软件约束A与保留当前物理解锁B之间二选一，列优劣、给出明确选择和对应设计。D015的软件偏好与本地20–60°/+5°候选不再作为预设结论；原讨论保留为背景。本次按项目handoff流程授权相关review分支提交/发布、选择性打包与新Drive目录上传，不涉及主工作分支合并、训练或B02实现。

具体范围以[Owner任务](pro_handoff/20260918_b02_b04/OWNER_REQUEST.md)、[研究说明](pro_handoff/20260918_b02_b04/REVIEW_BRIEF.md)为准。新交付只包含B02/B04有关的source/config/静态依赖依据和明确标记日期的旧接线证据，不重开v28验收。按Owner约定不生成哈希清单，采用专用分支、提交主题/时间与文件清单定位。

## V29-D017：B03后置，Pro同包追加B04限位设计

2026-09-18 17:04 HKT。决定：-owner。状态：**B03_DEFERRED / B04_PRO_REVIEW_PENDING**。

B03保持base双D435i上仰15°，等待v29 baseline出来后再微调；不作为当前baseline前置。TODO勾选并标DEFERRED，只表示处置决定，不是角度/成像质量PASS。

Owner同时要求Pro细化B04最大张开角随机化的“软件限制还是物理限制”。交付要求先区分强制角度裁剪/状态重写、原生hinge joint limit、实体stopper碰撞；当前150°属于原生物理约束。Pro须明确推荐实现、90–150°候选域及其与B02临时锁定/解锁限位的配合，分开最大角、release gate、实际松手和过门质量。B04仍未实施，未因此改奖励或启动运行。

## V29-D018：B02/B04 Pro输入交付完成

2026-09-18（HKT）。状态：**PUBLISHED_AND_UPLOADED / PRO_DECISION_PENDING**。

按D016–D017完成[独立交付](pro_handoff/20260918_b02_b04/README.md)：review分支`codex/v29-b02-b04-pro-20260918`已发布；提交主题`Prepare v29 B02 and B04 Pro decision handoff`，时间`2026-09-18T17:14:54+08:00`，本地review ref、remote-tracking和remote ref一致。使用独立index提交本轮选定14个变化路径，没有使用主工作分支index或合并其他改动。

[Drive任务目录](https://drive.google.com/drive/folders/1RfrGhpw4hsi-FElR7Fc9L4UIrWjuuOBt)包含source/config ZIP（438863 bytes、35文件）、参考/证据ZIP（63988 bytes、10文件）及三份索引/manifest/handoff；五文件已按名称、字节数及父目录读回。无checkpoint，当前配置只执行Hydra解析，旧one-batch明确为历史证据。本地最终[Pro prompt](pro_handoff/20260918_b02_b04/PRO_REVIEW_PROMPT.md)在发布/上传核对后生成；回包要求FULL_REVIEW、DESIGN_SPEC与LOCAL_WORKER_PARSE_PROMPT，由Owner以附件传回，不由Pro上传Drive。

本次完成的是交付，未替Pro选择B02/B04、未实现新门动力学或启动训练。B03后置保持15°。源码快照后的交付收据和当前文档记录不回写已上传的不可变输入包。

## V29-D019：两份B02/B04独立Pro回包归档与定向核对

2026-09-18 19:47 HKT。范围：-owner；整合：-codex planner及两路只读source/API核对。状态：**DUAL_PRO_ARCHIVED / TARGETED_SOURCE_RECONCILED / OWNER_DECISION_PENDING / NOT_IMPLEMENTED**。

Owner上传`pro_delivery__full_review-1.zip`及`pro_delivery__full_revie-2.zip`，要求独立保留原包/原文、对照当前source/config/本机IsaacLab/已有runtime，仅解析并更新plan/TODO。两包分别归档于[新目录](../pro_reviews/v29/20260918_192550__B02_B04_dual_pro_review/README.md)的pro_1/pro_2，未猜测具体模型身份、未去Drive寻找答案。来源review分支仍为`codex/v29-b02-b04-pro-20260918`，提交主题`Prepare v29 B02 and B04 Pro decision handoff`，时间`2026-09-18T17:14:54+08:00`。本轮文档更新前34个输入路径逐字节对照：全部受核source/config一致，只有本地README/decision log的较新交付记录不同，未覆盖它们。

两份均选择B02 A虚拟锁闩与B04原生门轴限位M~U(90°,150°)、每门固定；均删除旧实体latch/mimic/第三DOF，不用每步重写q/qdot。选择共同但参数不同：Pro1 H45°/u25–40°、raw USD饱和回位、PRE；Pro2 H40–60°/u=ρH支持26–51°、SI渐增回位、POST。Main建议以Pro2为讨论基案，Pro1为完整保留的窄行程备选；D015的20–60°/+5°不继续作为默认。全部工程初值与采用意见仍待Owner确认。

关键本地核对：native API支持所需rad tensor和选中env，但CPU传输/承载未运行；正常M须独立于epsilon。R/E迟滞状态、时相和snapshot validator不能混搭；Pro2不能把capture外/epsilon内的合法已锁状态判错。staged与recovery原本per-env，可复用tracked bool；最终reset限位/target提交必须晚于所有recovery恢复。删除第三DOF须同步直接消费者并解耦build_latch与self-collision。0.6rad helper和creation固定45°均活跃，下压用u、止挡用H。

当前reset的15π/180写入effort目标是源码事实；作者层−15°被runtime零position-target覆盖是完整链路支持的静态推断，实际读回未做。显式负回位目标是有效负载改变，不能称已证明保留旧行为。source还支持三处post-gate收入路径；Main建议Pro2整项hinge/hold mask及去正grasp，明确连负关门项也去掉、恢复行为效果未知。Pro1新增3control双指断触的Stage4→5/回臂门槛及近闭门回柄mask另列，本地不自动采纳；保留当前阶段条件的Pro2基案待Owner确认。

完整出处、参数差异、采用/调整意见与LOCAL_ONLY未知统一见[LOCAL_RECONCILIATION](../pro_reviews/v29/20260918_192550__B02_B04_dual_pro_review/LOCAL_RECONCILIATION.md)，当前计划见[plan §5–6](a2_piper_base_v29_baseline_plan.md)。两包静态PASS仅为云端静态材料，旧9月17日64env/one-batch只证明当时接线，不证明新B01/B02/B04。B02/B04未勾选、未PASS；B03保持15°并后置到baseline出来后，B01三档各1/3与closer有无各半不变。未改source/config/asset、添加测试、启动训练/仿真/render、提交Git或更新Teacher/G7，未重开v28验收；无本轮活动资源。

## V29-D020：B02后置独立ablation，B04进入当前baseline设计

2026-09-18 20:00 HKT。安排决定：-owner；B04工程整合：-codex planner。状态：**B02_DEFERRED_TO_ABLATION / B04_BASELINE_PLAN_DESIGNED / NOT_IMPLEMENTED**。

Owner明确：“这里先不做B02，等待其他baseline项确定后，再单开一个apply B02的分支做ablation。B04参照两份pro feedback设计baseline plan。”该决定覆盖D019将B02/B04联合列为当前候选的安排，不否定或改写两份Pro原结论。

当前baseline保留实体latch/mimic、三DOF、handle固定45°及既有handle动力学/target和0.6rad/45°奖励消费者；不加入R/E虚拟锁态、epsilon临时约束、两DOF迁移或Pro2 handle负载。已知handle effort/position target问题保留在B02资料中，不以B04名义顺带改动；B01设置hinge目标须维持关节边界。B02本轮清单标DEFERRED_TO_ABLATION，独立分支实际工作仍为未完成。其他baseline项确定后再安排`codex/v29-apply-b02`等独立分支，当前未创建；对照共享B01/B04等域及训练/评估设置，B02若包含机制/行程/负载多项，结论按整组改动解释。

[plan §6](a2_piper_base_v29_baseline_plan.md)按两份共同意见选择每门生成时M~U(90°,150°)、native hinge limit [0,M]，与B01分组独立采样、跨episode/stage/reset固定。当前实体锁舌继续负责解锁，B04无动态限位切换依赖；沿既有生成器→metadata/deterministic配置→逐env场景→per-env bank路径，训练/自然评估同域，不新增policy真值。

B04奖励工程设计采用Pro2：hinge整个位置＋速度及最终hold_and_drive用Stage3/Stage4未gate收入mask，Stage4 gate后grasp只保留负值，原scales 6/8/.2不变。明确连gate后hinge负关门项也取消，以容纳B01正常回关；重开恢复的学习效果未知。保留当前阶段/回臂条件，不采纳Pro1新增3control双指断触晋级门槛或近闭门回柄mask。Pro2的2control断触确认只用于独立事件记录，不改变成功门。角度随机与收入修改不保证实际提前松手或90°成功通行。

同步plan/TODO/总体安排/README与memory；B04保留未勾选并标PLAN_DESIGNED，未将工程建议记为Owner逐参数批准。B01三档等权及closer各半不变，B03仍保持15°并后置到baseline出来后，B05继续讨论。只更新计划文档，未实施source/config/asset、创建分支、运行训练/仿真/render或新增测试；未改Teacher/G7或v28验收。

## V29-D021：直接修复释放许可后的开门与握持收入

后续状态：本项代码已按Owner的D023决定精确回退；以下保留当时实施/CPU核对记录。

2026-09-18 20:19 HKT。决定：-owner；实施：-codex planner。状态：**OWNER_AUTHORIZED / IMPLEMENTED / CPU_TEST_PASS**。

Owner确认当前仍有release gate后的hinge速度与hold_and_drive收入，并要求“直接先修复这个，决策纳入记录”。本次实施D020 plan §6.3的三处修复，不等待B02 ablation、不扩展为B04最大角实施。

在`gr00t/rl/envs/door/door_open_a2_base.py`的共享A2奖励路径中：`_reward_push_door_hinge`将位置＋速度先按原方式合成/clamp，再整体乘已有Stage3或Stage4未release的收入mask；`_get_a2_grasp_gated_door_reward_components`对最终覆盖后的`hold_and_drive`乘同一mask；`_reward_grasp`仅对Stage4且release gate已置位的env去掉正值、保留负值。mask为device上(N,) bool，转换后与(N,)浮点奖励逐env相乘；grasp使用同shape的where。没有新增配置开关、fallback或观察输入。

gate前保留抓握推动激励，防止退回只压把手不推门的奖励结构。gate后也取消该hinge项的负关门值，容纳B01闭门器正常回关；其他碰撞/过力/稳定/通行收益照旧。保持1.2rad gate、OR锁存、阶段转换/回臂条件、reward权重和动作/观察合同，不强制松手或禁止再接触。

本次直接修正共享A2公式，不添加历史版本兼容开关；已有冻结run及其v28裁定不回写。B02实体latch/mimic/三DOF及后置ablation安排保持；B04上限仍150°，90–150°随机化和新增断触事件记录未实施。未改source以外的config/asset、创建分支、Git提交、启动仿真/训练/render或更新Teacher/G7。

验证：2026-09-18 20:22 HKT完成一次修正harness后的[定向CPU核对](implementation_evidence/release_income_20260918/README.md)。直接执行提取的生产方法和本机IsaacLab quaternion math：Stage3/gate前hinge=1、hold≈.8保持；gate后开门/关门hinge与hold均0；正grasp变0、负grasp保留−1；1.2rad置位及回关后OR锁存保持。源码AST随probe解析成功，未运行IsaacSim或训练，不据此认定实际松手/策略收益。

## V29-D022：补充强回弹下重新抓把手扶门目标，重开最终奖励讨论

后续状态：Owner在D023将此议题移至N02讨论，不作为当前baseline前置；候选未实施。

2026-09-18 20:35 HKT。行为目标与接触范围：-owner；方案建议：-codex planner及一路只读语义核对。状态：**REGRASP_GOAL_CONFIRMED / REWARD_REDESIGN_DISCUSSION_OPEN / NO_NEW_CODE_CHANGE**。

Owner指出D021的gate后关闭可能带来早松手/净空不足、回关后重开变弱、握持学习变慢，并希望policy在强回弹时重新伸臂抵住门。经范围澄清，Owner选择“先限定为重新抓把手扶门”。手掌/前臂顶门板不纳入首版。

定向核对确认：Stage4普通grasp距离奖励为0、mild距离项在gate后关闭；回臂罚在非双指接触时生效，恰好覆盖伸手过程。Stage5有更强的−5 arm默认姿态项且无接触豁免，也无接近把手收入。门近闭时仍存在回柄偏好。stage reward、目标运动和完成收益仍在，失抓不会自然退stage或立即终止；不能说完全只剩碰撞/失败，也不能据源码断言D021必然导致上述行为。没有新训练结果。

Main建议将release gate保留为历史许可，另按当前身体通行区域、净空、回关趋势与已有接触反馈建立可再次生效的辅助需求，覆盖Stage4/5。需要时引导接近/有效握持/恢复必要净空，解除相冲突的回臂偏置；真实latch重新捕获时还需允许再压柄，避免回柄奖励抵消。扶门qdot≈0也可能有用，不能只奖励正门速，或用瞬时零门速判断辅助结束；退出结合净空余量、通过进度及有限迟滞。

继续去掉无条件开大/大力握持的收入；恢复进展需同时计入改善与恶化，避免反复关回再开/反复重抓得到重复奖金。势函数差分是待细化的shaping方向，具体Phi、几何包络、时窗/迟滞、权重与终止口径尚未确定。完整候选、source定位与论文出处见[plan §6.3.1](a2_piper_base_v29_baseline_plan.md)。该讨论不自动引入N01恢复图/采样或N02网络，也不重开B02机制实现。

D021仍是当前源码；其CPU方法证据保持原限定，不提升为最终恢复行为认可。本轮仅更新目标、计划与待决记录，没有回滚或继续改reward代码、添加测试、运行仿真/训练、Git操作或Teacher/G7变更。B01三档、B02后置、B03保持15°后置与B04最大角仍待实施的状态保持。

## V29-D023：精确回退D021奖励，重新扶门移到N02讨论

2026-09-18 20:43 HKT。范围及回退选择：-owner；实施：-codex planner。状态：**OWNER_CONFIRMED / EXACT_REVERT_IMPLEMENTED / STATIC_PASS**。

Owner要求baseline先不做按需回弹恢复，回退之前门轴奖励，并将“arm重新抵住门”放到N02讨论。Main说明原公式在release gate后门角位置项仍关闭、只保留门速/持握推动收入，并明确回退按D021整组三处处理；Owner选择“恢复D021之前的原公式（推荐，精确回退）”。本条以该澄清为准，不额外打开gate后门角位置项。

已精确恢复`_reward_push_door_hinge`、`_get_a2_grasp_gated_door_reward_components`与`_reward_grasp`：hinge仅位置项乘旧A mask，正/负门速仍计入；最终hold_and_drive不再乘新增release mask；grasp撤回Stage4去正留负的新增处理。位置项原90°饱和、合成[-1,1]限幅、原scale及Stage5 continuity=false保留。其他近期source改动不回退。

[静态回退记录](implementation_evidence/reward_revert_20260918/readout.json)对照D021前的`codex/v29-b02-b04-pro-20260918`输入分支（提交主题`Prepare v29 B02 and B04 Pro decision handoff`、时间`2026-09-18T17:14:54+08:00`），三处函数源码逐段完全相同，当前source AST解析通过。没有重跑旧D021 probe或仿真/训练；其旧CPU证据已标历史适用，不能宣称为当前公式通过。

D022关于净空/闭合风险、重新接近把手、Stage4/5回臂及近闭门再压柄的候选移入[N02讨论文档](../novelty/documents/20260918_n02_regrasp_rebound_discussion.md)，Owner首版接触范围仍是重新抓把手。N02讨论与实验另行推进；共同任务reward改动和交互历史方法收益需分开解释，未授权新网络/分支/预算。N01原有恢复图/采样安排不自动取消。

B04最大角U(90°,150°)的原生限位计划保留、尚未实施，当前仍150°；本版不增加专门的重抓事件/去抖或按需辅助mask。B01三档与closer各半、B02后置独立ablation、B03保持15°后置及其他基础决定不变。已同步plan/TODO/总体安排/novelty归档与memory；无配置/资产修改、Git提交或Teacher/G7变更。

## V29-D024：B04讨论结案与实施待办分开

2026-09-18 21:01 HKT。确认：-owner。状态：**B04_PLAN_DECISION_PASS / IMPLEMENTATION_PENDING**。

Owner指出B04已落地plan，要求讨论TODO标完成。现将B04勾选并划掉标题，标方案讨论PASS；每门固定U(90°,150°)原生限位、D023原奖励及既有阶段条件为已确定方案。物理代码尚未实施、当前上限150°，另列明确实施待办，不以此继续扣留讨论完成状态。此前未勾选混淆了方案与代码阶段，按本条纠正；未启动运行或改动训练源码。

## V29-D025：B05七族设计与自由段/抓握目标可视化

2026-09-18 21:23 HKT。任务：-owner；整合/绘图：-codex Main；两路只读team分别给形状族和grasp-frame/指部几何合同。状态：**DESIGN_OPTIONS_READY / OWNER_SELECTION_PENDING / NOT_IMPLEMENTED**。

交付F0原圆直杆、F1椭圆、F2圆角扁、F3单弧、F4浅S、F5偏置直腹、F6缓变锥度。完整标称值、图、出处和G映射统一维护在[B05设计](a2_piper_base_v29_b05_handle_design.md)，与PNG/SVG及会话比较图共用[参数/中心线](b05_designs_20260918/families.json)。没有把上下镜像或回钩单独凑成新族；族/回钩权重和尺寸域待Owner选择，B05未标方案PASS。

source确认Capsule的110–140mm是轴段、含球帽为132–170mm；完整axle180–210mm。F0选L125/r13/A195。当前TCP处不能用指尖25.4mm代替切向覆盖：原始全指包络约56mm、TCP截面约41.47mm；30–50mm自由段尚不能标已足够。Main据此把本次标称主段设65–74mm，以56mm参照＋每端3mm余量得到3–12mm中心候选，只作静态设计，不证明扫掠可抓。

G由有向切线和同源位置定义，t朝轴颈以匹配当前PiPER姿态，Y闭合/+Z接近。F3抬高5.68mm、F4倾角约−8.25°、F5抬高8mm。未来统一生成器/FixedJoint/consumer责任层，避免旧固定四元数与LEFT处理重复叠加，保持单一handle刚体/双指接触过滤。

已检查七族显示、切换F4/下压30°/回返显示与窄屏无水平溢出，静态概览排版已修正。证据仅标称几何计算和图形交互，非IsaacLab资产/抓握/训练结果。未改训练source/config/URDF/USD，未启动仿真/训练、Git提交或新分支；B01/B02/B03、D023原奖励和N02归属保持。

## V29-D026：B05七族全量确认、planner职责与独立Pro审阅

2026-09-18 21:38 HKT。依据：-owner；记录：-codex planner。状态：**OWNER_APPROVED / PASS_PLAN_DISCUSSION / PRO_HANDOFF_REQUESTED / NOT_IMPLEMENTED**。

Owner原话：“要求全部apply，我同意这7族设计。放入v29 baseline plan。”同时要求打包给Pro审阅：1. 设计是否重复；2. 是否还要拓展构型；3. 搜集现实handle对比，判断能否在sim模型简单的情况下增强泛化能力。

Owner并明确：“你的职责是planner，在非我要求的情况下你都是负责设计plan，不做具体的code implement和训练监督。所以B04，B05这里设计好，得到我确认后放入plan了，TODO这里就可以标记完成。”本轮apply据此指方案纳入，不是代码实施命令。

F0–F6七族及自由段/目标设计全部进入baseline §7，B05勾选并划掉标题，取消D025中F0–F3基础组/F4–F6扩展组的分期建议。B04继续按方案完成保持勾选。族概率、连续随机尺寸域等由Pro提出细化建议，不据此让已确认方案继续挂为未完成；没有将未定概率伪写成Owner批准值。

Pro必须独立区分整体轮廓、抓点邻域截面/曲率、净空与接触力学，给现实厂家来源及最小模型建议。几何覆盖可以静态分析，但没有训练/实机证据时不能保证泛化收益。合并、替换或新增族只作为明确建议，后续由Owner决定。保留B02独立ablation、B03后置、D023原奖励与N02归属，不重开这些议题。本轮不改source/config/asset、不运行仿真或训练；只按已请求的Pro交付发布选定文档/材料。
