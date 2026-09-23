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

## V29-D027：B05独立Pro审阅输入交付完成

2026-09-18 21:53 HKT。状态：**PUBLISHED_AND_UPLOADED / PRO_REVIEW_PENDING**。D026七族全量批准及planner职责保持；本决定只记录交付，不新增实现或训练范围。

[完整prompt与入口](pro_handoff/20260918_b05/README.md)已生成；[Drive任务目录](https://drive.google.com/drive/folders/1VJ-lhwltmidIGWbASzv4sTPtI3NwXZBZ)含两个独立ZIP（source/config 347849 bytes、geometry/reference 804432 bytes）及三个索引/manifest/handoff。五个文件均按名称、字节数和父目录读回核对；只附35个明确选择的文件，无checkpoint/训练日志或完整机器人资产。

专用分支`codex/v29-b05-pro-20260918`已push，提交主题`Approve seven-family v29 B05 handle plan and prepare Pro review`，时间`2026-09-18T21:46:23+08:00`；本地review分支、远端tracking及远端分支核对一致。使用独立index发布17个规划/图/交付说明变化路径，runtime source/config未产生新变化，原A2_Piper分支和index未用于此提交。按Owner要求不提供哈希清单。

输入包含七族规格、I/J/G/frame、图和同源数据、当前source/config与三件夹爪mesh、旧Pro形状参考及七个厂家检索种子。Pro要独立判断重复、最小扩展必要性和现实覆盖，并区分静态几何与泛化收益；不得把种子链接当完整产品测量。对合并/替换/新增列显式建议，保留Owner确认权。

本地prompt及本交付记录在输入发布上传后生成，不回写不可变输入。Owner把prompt交给Pro，Pro于其对话附`pro_delivery__full_review.zip`，再由Owner上传到本地任务；当前尚无Pro审阅结论。本轮没有source实现、GPU运行、训练监督或仍活动的运行资源。

## V29-D028：B05 Pro回包归档与定向核对，扩域建议待决定

2026-09-18 23:48 HKT。依据：Owner当前附件接手请求；整合：-codex planner。状态：**PRO_REVIEW_RECEIVED / TARGETED_RECONCILIATION_COMPLETE / PARAMETER_PROPOSALS_PENDING_OWNER / NOT_IMPLEMENTED**。

Owner上传`pro_delivery__full_review (3).zip`，原包与五份要求原文、静态JSON及Worker原图已保存到[本次归档](../pro_reviews/v29/20260918_233820__B05_handle_review/README.md)。仅当前附件作为Pro回包，不到Drive寻找答案；附带接手文本保留原文，执行范围以Owner当前请求为准。

一次定向核对已完成：本轮文档整合前，34个项目输入路径有32个与送审快照逐字节一致，仅README/decision_log新增D027交付记录；当前source/config、URDF/三件mesh及七族规格/数据一致，外部FrameTransformerCfg快照也一致。Main复算有限指宽曲率/直径梯度；两路只读team分别核对TCP前伸/roll合同和关键厂家新来源。没有全仓审计、运行仿真或新增测试。

Pro建议七族全保留、暂不加第八训练族；F5在I内局部最接近同径直圆杆，F3/F4仍有约0.98/1.10mm残差，F6有约2.42mm厚度梯度。当前指体相对TCP前伸50.8mm静态复现；候选h55只留4.2mm理想无限门平面余量，不证明完整扫掠。截面roll但G保持门法向的方案自洽，区别于自动追随薄轴。

ASSA L/U的19mm杆与projection/rose字段获官方文字支持，但projection起算面未明，不能直接当h。FSB1294英德文锥度方向确实冲突；FSB1107支持弯曲×椭圆的定性组合，不能提供X1工程尺寸或抓握证明。Pro的13例产品保留各自获取/证据状态，未把未读图纸补成测量。

Main建议优先讨论站距、截面方向与条件return，X1作为未见lever组合候选。h55–85、圆杆19–30/F6中点21–28、非圆缩放/roll、λ、七族1/7、圆滑return与Ø54×6饰盖均仅整理为[待Owner决定提案](../pro_reviews/v29/20260918_233820__B05_handle_review/LOCAL_RECONCILIATION.md)，没有更换原七族或自动写成批准分布。B04/B05完成勾选、D026原标称和planner职责保持；B02/B03/D023/N02不变。无source/config/asset修改、Git提交、云端再上传、训练或硬件活动。

## V29-D029：全部采用B05 Pro建议，PiPER/TCP二次确认后交worker实施

2026-09-19 00:44 HKT。依据：Owner“全部按照pro模型建议走，但根据当前实际Piper gripper尺寸/TCP verify二次确认后落地v29 baseline；planner落地plan，由Owner交worker team做”。状态：**OWNER_APPROVED / SECOND_STATIC_CONFIRMATION_COMPLETE / PLAN_READY_FOR_WORKER / IMPLEMENTATION_PENDING**。

F0–F6、七族1/7、hook1/2、h55–85、全部截面/roll/λ、条件圆滑return、同轴Ø54×6饰盖和X1训练外组合全部采用。参数与[执行规格](a2_piper_base_v29_b05_handle_design.md)统一；不再挂为待Owner决定，不恢复首批/扩展拆分。X1仍不加入第八训练族，原标称锚点保留。

新增定向静态确认复用此前已知56mm切向包络/50.8mm前伸，进一步读取实际对置指面、检查全截面/roll的开口与掌基，Main补充rose/neck/return及当前固定腕部件组合边界。入口净隙约70mm、TCP附近约74mm；F2全roll最大34.071033mm（不是33），主杆—掌基保守分离4.964483mm；默认G下两指—rose/return至少3.499/13.463484mm。h55理想门平面余量4.2mm保留。无需削指、前移TCP或缩小Pro尺寸域。详细方法与条件见[二次确认](b05_gripper_confirmation_20260919/README.md)。

落实两个必要构造细节：端帽轴向伸出r_tip由实际圆滑帽返回且首版不超过截面外接半径；先C=min(60,h−r_tip−8)，再R~U(20,min(30,C))、H~U(R,C)，避免最贴门/最大截面组合的空区间。最保守F2边界C29.964484，整体R20–30/h55–85范围保持。每操作门面各一片rose，现有双面门镜像两片；原圆轴颈11–15mm半径域保持，主杆截面独立表达。默认G为J中点，本版不增加J内抓点随机化。

planner已更新baseline plan、B05规格和[worker交接](a2_piper_base_v29_b05_worker_handoff.md)；Owner自行交worker team，未派发实现。静态确认不替代USD/PhysX导入、实际动作/接触/整机IK、训练或硬件结果。B04/B05保持方案完成，实施状态另列；B02/B03/D023/N02保持。未修改生产source/config/asset、Git提交/上传或训练监督；新增脚本仅作离线规划几何计算。

## V29-D030：Owner委托完整baseline worker与离线planner审批

2026-09-19 01:25 HKT。**决策方：OWNER；记录方：PLANNER；planner thread：01a0af49-b5e0-75f2-8fdd-ad5c3e20744b。** 状态：**AUTHORIZED / WORKER_THREAD_PENDING / NO_TRAIN_APPROVAL_YET**。

Owner明确：worker team负责整个v29 baseline的implement和训练监督，不是仅B05；实现完成后以Codex turn/steer向本planner报告，由planner每项仔细严格验收，尤其检查B05新door asset生成及randomization组合是否可用。有问题由planner同通道直接要求worker最后修正，planner最终approve后，worker才可用GPU0开启基础baseline训练。Owner接下来离线，授权planner把关/审批/推进；planner入口`codex://threads/01a0af49-b5e0-75f2-8fdd-ad5c3e20744b`必须写入启动prompt，worker ID待Owner创建后回传。turn/steer不可用时fallback codex queue，Owner已验证同机可行。

Owner随后追加授权双方自主沟通推进，要求决策日志区分planner和worker决定。该授权不等于当前候选已通过或训练已获批准，也不自动启动第二seed、pull/N01/N02/B02独立路线。B04/B05方案完成继续保持。

## V29-D031：Planner制定全版启动prompt、逐项验收和分角色日志

2026-09-19 01:25 HKT。**决策方：PLANNER；依据：Owner D030授权；planner thread：01a0af49-b5e0-75f2-8fdd-ad5c3e20744b。** 状态：**PROTOCOL_READY / WAITING_WORKER_ID / IMPLEMENTATION_AND_TRAINING_NOT_STARTED**。

已重写[完整worker启动prompt](a2_piper_base_v29_worker_start_prompt.md)，旧B05交接保留为技术附件。建立[验收/协调合同](a2_piper_base_v29_acceptance_and_coordination.md)：逐项核实B01/B04/B05、已有Stage5/高度/B06/B07/时限/速度、D023奖励与完整训练接线；B05必须查看实际新资产/碰撞、结构组合、参数联合域、G/FixedJoint/reset与导入后接触，不以D029静态结果或worker自评代替。

planner负责最终裁定和具体TRAIN_APPROVED；worker负责实现、修正和获批GPU0运行。实现证据与训练效果分别验收。当前seed291/4096env/6000batches只作为提交流程的默认起点，最终命令/预算/ETA须在候选审查时由planner决定；本条不是直接开训批准。短时验收资源/命令由planner协调，正式训练单独批准。

通信只读核实：本机Codex CLI及daemon0.153.0，turn/steer是App Server方法而非CLI子命令；当前采用Owner指定的queue备用通道，其语法为`codex queue --thread UUID --message TEXT`。主任务ID经App元数据及CODEX_THREAD_ID确认，host为remote-ssh-discovered:gpu1-codex；没有发送自测/loopback消息，也未声称queue入队代表任务已处理。

角色分账：Owner与planner决定留主D日志，worker维护[独立W日志](a2_piper_base_v29_worker_decision_log.md)，包含角色/任务ID、依据、影响范围、候选/运行、状态和通信引用。worker范围内决定可自主推进；方案变更和开训由planner裁定。待Worker ID后绑定实际任务/资源与候选，不伪造审批，相关运行用现有team_state/run_supervisor和独立tmux、按ETA/事件等待。没有生产代码/资产/训练改动、Git提交或启动worker任务。

## V29-D032：绑定完整baseline worker并批准C001有界验证

2026-09-19T01:38:12+08:00。**决策方：PLANNER；依据：Owner D030及真实V29_WORKER_READY；planner thread：01a0af49-b5e0-75f2-8fdd-ad5c3e20744b；worker thread：01a0b592-48e3-7ad0-9263-4cb605862ed6。** 状态：**WORKER_BOUND / IMPLEMENTATION_ACTIVE / VALIDATION_AUTHORIZED / NO_TRAIN_APPROVAL**。

Worker在本仓库A2_Piper分支接手C001完整实现/监督。复用现有adaptive team state，新增planner/worker协调合同；保留worker已创建的v29_b05/v29_dynamics与其文件lease，不接管其他历史任务。生产source/config/asset和W日志归worker，planner独占主D日志、当前状态与最终验收/开训批准。

绑定时GPU0空闲且无有效GPU0 lease，已租给v29_baseline_worker用于串行有界验证。当前[验证授权](../../.ai/runtime/v29_baseline_team/C001_VALIDATION_AUTHORIZATION.md)保存具体64-env及4096-env各1-batch PPO命令、先后条件及总120 GPU分钟/单次45分钟上限；实际资产/contact/render、checkpoint重载与natural reset命令在worker实现后提交planner一次具体核对。先证明实际28结构组合和关键边界，再短接线与目标规模证据；未给6000-batch或其他GPU/第二seed授权。

App快照读取未返回，未把它记为身份核验成功；当前绑定依据worker真实注册消息，沿Owner授权codex queue通道通信并保存入队回执。已要求真实ETA和下一决策点，按事件/同一持久等待继续，不定时唤醒看日志。C001尚在准备，没有冻结候选、实现PASS或TRAIN_APPROVED。

## V29-D033：批准worker首个64-env接线命令，调整验证顺序

2026-09-19T01:42:05+08:00。**决策方：PLANNER；worker：01a0b592-48e3-7ad0-9263-4cb605862ed6；候选：C001准备中。** 状态：**SMOKE_COMMAND_APPROVED / IMPLEMENTATION_NOT_ACCEPTED / NO_TRAIN_APPROVAL**。

核对worker[精确提案](candidates/C001/bounded_verification_proposal.md)与当前训练入口：experiment_dir同时供环境与TRL输出，output_dir是已存在的AppLauncher参数；GPU0 lease仍归本worker且当时空闲。批准其64env、1-batch、step1保存及候选独立输出命令，并显式固定seed291/checkpoint=null/auto_load_latest=false；完整命令见[批准记录](../../.ai/runtime/v29_baseline_team/D033_SMOKE64_APPROVAL.json)。

同意在worker完成B05/B01/B04及消费端整合、离线几何/配置基本确认后先运行这一次PPO smoke，以尽早暴露导入/消费端错误。随后完成B05真实资产/参考接触、checkpoint/natural路径，短路径通过后再4096env规模验证；这是对D032原先先专项后PPO顺序的明确调整。D032总120 GPU分钟/单次45分钟等限额保持，没有增加正式训练预算。

Worker预计启动后2–5分钟，依据旧同规模约57秒但新资产导入未计时；实际启动/退出、命令输入、配置/资产与原始日志由worker记录并queue回报。worker主agent整合消费端，planner不抢写生产文件；正式候选提交时另行严格逐项验收。

D033协调补记（2026-09-19T01:43:55+08:00）：worker确认D032并提交[实现ETA](candidates/C001/worker_eta_D032.md)，估计02:42–03:12交付可执行资产/接触命令；planner登记单一逻辑等待至03:12，具体阻碍/启动事件可提前结束等待。该ETA基于剩余B05与harness工作量，非实测运行承诺。ETA文档沿用旧先专项顺序，已回传D033最新顺序；拟新增纯读callback/override待具体命令提交后一并核实。当前无GPU运行报告或TRAIN_APPROVED。

## V29-D034：裁定reference bench用途并批准有界采证命令

2026-09-19T01:57:46+08:00。**决策方：PLANNER；worker thread：01a0b592-48e3-7ad0-9263-4cb605862ed6；候选：C001准备中。** 状态：**VALIDATION_COMMANDS_APPROVED_WITH_BOUNDED_CORRECTIONS / NO_IMPLEMENTATION_OR_TRAINING_VERDICT**。

已读取具体asset/reference/callback实现、生产frame/contact/Jacobian接线；单路只读specialist核实callback生命周期与reload路径。固定robot root作为显式bench fixture可用于本轮局部参考几何/接触/目标链验证，保留真实mesh、arm/finger drives及门动力学；不证明自由底座、全身稳定或策略表现。到不了G的样本不能记接触路径通过。

[具体裁定与运行批准](../../.ai/runtime/v29_baseline_team/D034_VALIDATION_COMMAND_REVIEW.md)要求一次补齐：F2闭合向边界固定lambda .90并加左右最大法向支撑极端组合（34门）；接触点匹配动态handle位姿、已有arm-panel矩阵及probe原始点容量；重载绑定D033真实checkpoint和load facts。允许worker完成这批明确修正并读回后直接执行，无需再绕一轮权限申请，最终runtime证据仍由planner验收。

callback静态核对为只读，可附加64/4096短PPO；begin不是reset样本，obs shape不冒充完整语义。自然eval按64环境各首回合、继承30s配置与实际步数报告；原“1500步”不是代码现有硬截断，不为其添加生产护栏。D033短PPO可先行、assets先于reference、reload依赖smoke、目标规模待短路径通过。GPU0总120分钟/单run45分钟保留；当前未收到GPU运行证据或正式开训申请。

## V29-D035：首个64-env smoke在USD类型冲突处失败，定向修正后重试

2026-09-19T02:01:19+08:00。**记录/裁定方：PLANNER；执行方：WORKER 01a0b592-48e3-7ad0-9263-4cb605862ed6。** 状态：**PROCESS_FAILED / PPO_NOT_REACHED / NO_IMPLEMENTATION_OR_TRAINING_PASS**。

启动消息对应run `v29-c001-smoke64-a1`。planner一次核对receipt与D033命令完全一致，未附采证callback，输入快照记录316项source/config/asset文件。supervisor显示01:56:40启动、01:58:10退出1，实际耗时90.817s；本次5分钟逻辑等待因失败提前结束。[原始日志](candidates/C001/ppo_smoke.log)的直接异常为spawn_door第679行：既有grasp_target orient属性是quatd，新v29写入请求PrecisionFloat发生冲突，尚未进入PPO。日志中的GPU Foundation提示另行保留，不据此替换已明确的直接失败原因或声称render通过。

读取当前workspace时，该处已由worker改为PrecisionDouble/Gf.Quatd；planner没有再次写同一路径，也未把未运行的新source记为已修复验证。worker按已有D032直接修复权限，以新attempt输出和输入快照重跑对应短路径；D034采证callback已获批准，可在下一次附加以合并证据，无需再等重复权限。旧a1现场保留，不静默改参数域/资产/奖励。GPU0验证总额度保持，已记录本次实际耗时，正式TRAIN_APPROVED仍为空。

## V29-D036：批准参考probe追加B01释放/B04限位及自然reset读回

2026-09-19T02:04:19+08:00。**决策方：PLANNER；提案/实现方：WORKER 01a0b592-48e3-7ad0-9263-4cb605862ed6；候选：C001准备中。** 状态：**BOUNDED_PROBE_EXTENSION_APPROVED / NOT_RUN / NO_TRAIN_APPROVAL**。

读取[补充提案](candidates/C001/reference_contact_addendum.md)与reference脚本实际新增循环，批准550步接近/闭合后追加release250步与native_upper_limit50步，总850control步（预期dt .02时17s），继续使用D034修正后的34门同一manifest。精确显式flags/命令见[批准记录](../../.ai/runtime/v29_baseline_team/D036_REFERENCE_DYNAMICS_APPROVAL.json)。

每窗口开始一次设置全部door joint初态：release令hinge=min(M−.10,π/2)、零速度；upper令hinge=M−.03、正速度.40，其余joint置零。机器人fixture移至该env门外避免接触；随后只保持机器人root，不在响应窗口内写门q/qdot，原native drive/friction/limits/solver演化。该受控初态用于B01/B04机械响应，不是policy实现开门。

要求记录实际初态、dt、轨迹与原生限位；B04必须看到实际接近限位及响应，单纯q≤M不足以证明触发；无closer零速度释放的静止也不单独证明动态/粘性摩擦。最后真实env.reset_all后与之前同门metadata/G/friction等读回对照。原120 GPU分钟/单run45分钟不变，正式训练仍未批准。worker声明同域convex表示满足GPU64限制，本条不把其CPU声明提升为GPU cooking或接触通过。

D035执行回报补记（2026-09-19T02:05:31+08:00）：worker以[smoke_a1_failure.json](candidates/C001/smoke_a1_failure.json)确认同一90.82s失败与Double/Quatd直接修正，状态FIXED_NOT_RERUN。归入既有a1记录，不重复计时、不新增验收或权限轮次；继续D032/D033允许的新attempt/输出后缀，并待实际重跑结果。

## V29-D037：64-env PPO重跑完成，继续已批准自定义验证

2026-09-19T02:07:33+08:00。**裁定/核对方：PLANNER；执行方：WORKER 01a0b592-48e3-7ad0-9263-4cb605862ed6。** 状态：**ONE_BATCH_PPO_WIRING_SUPPORTED / FULL_ACCEPTANCE_PENDING / NO_TRAIN_APPROVAL**。

[worker读数](candidates/C001/smoke_a2_readout.json)、实际receipt/STATUS及原始日志一致：`v29-c001-smoke64-a2`于01:59:13–02:00:41运行，exit0、87.311s、64env/1batch/4096timesteps；命令与D033仅有获准fresh output suffix变化。输入为a1快照加double-precision door.py捕获增量。CPU checkpoint读回记录step1及policy/value/optimizer/scheduler/trainer/env组件，明确runtime reload仍待验证，不能记为完整环境恢复或策略通过。

累计a1+a2实际验证耗时178.128s。D034、D036自定义命令早已批准，现再次向worker汇总，避免跨任务消息延迟造成等批；reference脚本已有接触容量128、handle pose/arm-panel字段，asset脚本已有6边界/34门定义。继续34门assets→reference850步、实际a2 checkpoint自然reload，短路径无未解释失败后4096env单batch带纯读callback。无须仅为给64-env补callback再重复跑一次同一smoke。最终逐项验收仍待完整候选和原始采证。

## V29-D038：资产probe完成，实际图像暴露plain案例不可见，要求定向定位

2026-09-19T02:12:06+08:00。**审阅/裁定方：PLANNER；运行方：WORKER 01a0b592-48e3-7ad0-9263-4cb605862ed6。** 状态：**PROCESS_COMPLETED / ACTUAL_RENDER_EXISTS / VISUAL_COVERAGE_INCOMPLETE / FIX_REQUIRED**。

启动回报对应asset-a1实际已于02:04:31–02:05:21完成，exit0、49.802s；manifest有34门，68张真实PNG和28结构总览。Main核对D034要求的F2低h/最大截面/两类roll/lambda .90/条件return边界均出现在manifest，十分钟等待随实际完成提前结束。

Main亲自查看[总览](candidates/C001/asset_probe/structural_outside_atlas.png)、F0_right_plain内外两图及F2最大法向右return内外图。F0_right_plain两面图只有门板，未看到handle；总览另有F2/F4/F6左右plain的类似空位。F2带return边界图可见实际几何。抽查USD读回中存在这些case的handle/collider/rose节点，因此暂不指定原因为漏生成、物理位姿还是camera/capture。具体已看图与发现见[记录](../../.ai/runtime/v29_baseline_team/ASSET_A1_VISUAL_REVIEW.json)。

要求worker以一个缺失案例与一个正常案例定向定位，保留原a1图/manifest，修复真实原因后补受影响视图/运行位姿事实；不重抽样或改域掩盖。D034/D036 reference及reload仍可按同一输入继续辅助定位，4096规模仍需未解释短路径问题解决。累计已测GPU验证227.930s，总额度不变。尚无全B05、接触或正式训练PASS。

## V29-D039：reference-a1虽exit0但只完成两步，修正退出语义后定位真实中断

2026-09-19T02:17:26+08:00。**核对/裁定方：PLANNER；执行/修正方：WORKER 01a0b592-48e3-7ad0-9263-4cb605862ed6。** 状态：**FAILED_INCOMPLETE_OUTPUT / CONTACT_DYNAMICS_NOT_PROVED / NO_TRAIN_APPROVAL**。

实际receipt命令与D036完全一致，34门，02:09:13–02:12:32退出0、199.534s。进一步按产物核对发现只有pregrasp step0/1两行reference trace；summary、关键帧和dynamics_response均未生成。因此“进程完成”不升级为850步动作完成，十五分钟等待已随退出结束。初始自然reset JSON和USD可作为其实际范围内的部分证据保留。

输入快照的finally调用SimulationApp.close(skip_cleanup=True)；本机实现明确立即shutdown_and_release_framework，worker[回报](candidates/C001/reference_a1_readout.json)也确认会在异常展开时丢失失败exit/traceback。Main读取当前脚本时已看到worker改为先打印traceback并exit1、成功路径再关闭，同时补真实invalid DLS target记录；没有抢写或重复修正。实际DLS中断原因尚未观测，不从两行轨迹推定geometry/G错误。

按既有直接修复权限获取真实错误并作对应修正，新attempt保留旧现场与输入差异；不以clipping/fallback或改变生产G/关节域使probe表面通过。D038图像问题并行待定位，4096规模继续等待未解释短路径问题解决。累计实际验证427.463s，总120分钟/单45分钟不变。

## V29-D040：核准v29 full-loader被动加载事实导出并同步写入归属

2026-09-19T02:20:56+08:00。**决策方：PLANNER；实现方：WORKER 01a0b592-48e3-7ad0-9263-4cb605862ed6。** 状态：**INSPECTED / RUNTIME_EXPORT_PENDING / NO_TRAIN_APPROVAL**。

依据D034实际恢复事实要求，读取[worker说明](candidates/C001/reload_evidence_note.md)与新增代码，并由先前同一loader reviewer做一次仅针对该增量的核对。与smoke输入快照相比只有八行v29导出；位于原完整恢复与检查之后，直接输出已有各组件load facts、实际checkpoint绝对路径、mode及恢复后global_step，未改恢复顺序、tensor、状态或成功判定。eval入口传入的真实eval_output_dir与trainer属性接线一致。

Main将trainer该路径的限定被动采证修改纳入worker WRITE_SET，并同步此前已批准的probe脚本/candidates归属；无竞争writer或新的生产控制权限。旧residual专用receipt未启用。原scratch smoke没有执行full-loader分支，其既有接线证据保留；新增JSON和实际full恢复以获准eval的运行输出核实，不因静态核对记runtime PASS。具体记录见[核对结果](../../.ai/runtime/v29_baseline_team/D040_LOAD_FACTS_REVIEW.json)。D038视觉问题与D039参考路径问题继续待解决。

## V29-D041：静态可见性补齐，初始物理读回复算成立，reference暴露左侧IK越界

2026-09-19T02:30:01+08:00。**核对/裁定方：PLANNER；运行/实现方：WORKER 01a0b592-48e3-7ad0-9263-4cb605862ed6。** 状态：**STATIC_VISIBILITY_SUPPORTED / INITIAL_PARAMETER_READBACK_SUPPORTED / REFERENCE_FIX_REQUIRED / NO_TRAIN_APPROVAL**。

asset-a2用48.610s完成，Main亲自查看[新版atlas](candidates/C001/asset_probe_a2/structural_outside_atlas.png)，28结构case全部可见；两版34门manifest参数直接值比较一致。该修正同时停止逐视图推进physics并刷新RGB，因此只确认静态可见性，不据此排除动态位姿问题或单独断言旧图缺失的唯一原因。

reference-a2于02:17:10–02:20:30以exit1结束、199.683s；新异常保留路径正常报告pregrasp step2的DLS越界。Main读取invalid_dls_target：全部17个LEFT case的arm_j3给出正目标约0.000364–0.000988rad，超过原生上限0；尚无接近/闭合或B01/B04响应通过。初始/default arm姿态读回正确为[0,.1,−.1,0,−.52,1.57]，生产A2 Piper是原配置implicit PD，probe并非漏接该驱动；抽查起始两步左右panel/handle接触力均为零，不把未测到的碰撞断言为原因。

Main基于原始reference-a2初始JSON独立复算34门质量、摩擦、drive与限位/target，最大差为panel质量1.62e−5kg、摩擦≤2.84e−8、上限1.32e−7rad、damping2.65e−6、target5.08e−9rad。只保留初始化参数接线证据；COM/惯量、重复reset和动作响应仍按最终合同核实，obs shape也不代表完整语义。见[读回复算](../../.ai/runtime/v29_baseline_team/INITIAL_PHYSICAL_READBACK_RECALC.json)。

要求worker先用实际状态/运动学建立限位内的reference预定位或IK路径，再重跑受影响验证；允许probe内明确记录的合法预定位/IK seed修正，生产几何、G、gains、限位不变，不以clipping、放宽限位或重抽样掩盖。原真实驱动接近/闭合与850步证据要求保留。累计验证675.757s，总额度不变；4096及正式训练仍待短路径问题解决与候选验收。

## V29-D042：a2 checkpoint实际重载及64自然首回合路径完成

2026-09-19T02:34:52+08:00。**核对/裁定方：PLANNER；运行方：WORKER 01a0b592-48e3-7ad0-9263-4cb605862ed6。** 状态：**MODEL_TRAINER_RELOAD_SUPPORTED / NATURAL_EVAL_PATH_SUPPORTED / REFERENCE_FIX_PENDING / NO_TRAIN_APPROVAL**。

获准reload-a1于02:23:06–02:30:11完成，exit0、425.161s。实际[v29加载JSON](candidates/C001/natural_eval/v29_checkpoint_load.json)绑定a2 step1 checkpoint，full模式，actor/value strict且无missing/unexpected keys、actor RMS恢复，optimizer/scheduler/trainer/global_step均有实际loaded事实。原始日志、metrics及64个唯一env的记录确认完成每env首个自然回合，全部525步在Stage0 overtime；这只支持未训练checkpoint的加载/评估接线，不声称策略效果。

明确environment字段边界：当前LeggedRobotBase.get_env_state_dict只合并log_dict，通用BaseTask.load_env_state_dict会警告并跳过不存在属性。该loaded标记说明调用完成，不是完整物理状态、staged bank或回合轨迹的逐项复原。未因此添加兼容层/护栏或改原加载流程；本轮无需重复重载运行。详细证据及界限见[核对记录](../../.ai/runtime/v29_baseline_team/D042_RELOAD_RUNTIME_REVIEW.json)。

reference-a2重复失败回报归既有D041，不重复计时；worker拟以硬限位内bounded least-squares修正probe，可在既定参考验证范围内实施并提交实际路径。D038动态/接触及B01/B04响应仍待reference完成，4096规模未启动。累计实际验证1100.918s，总120分钟/单45分钟额度保持。

## V29-D043：批准probe内原生限位约束DLS与reference-a3

2026-09-19T02:37:50+08:00。**决策方：PLANNER；实现方：WORKER 01a0b592-48e3-7ad0-9263-4cb605862ed6。** 状态：**SOLVER_INSPECTED / REFERENCE_A3_AUTHORIZED / CONTACT_NOT_YET_PROVED / NO_TRAIN_APPROVAL**。

读取[具体提案](candidates/C001/bounded_dls_proposal.md)及实际bounded_dls_targets/调用路径。增广矩阵[J;.01I]与右端[Jq+delta;.01q]恰好实现原DLS目标，变量改为绝对q_next并直接受native limits约束；原root-frame/TCP/Jacobian与2mm/.02rad增量保持。核对本机SciPy1.15.3已安装lsq_linear接口及[官方BVLS说明](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.lsq_linear.html)，不是事后clip或生产关节域变更。float64 CPU求解后返回原GPUdtype，失败/非法目标仍显式退出。未新增测试或重复运行smoke。

批准在GPU0执行[精确reference-a3命令](../../.ai/runtime/v29_baseline_team/D043_BOUNDED_DLS_APPROVAL.json)，使用asset_probe_a2同34case manifest与fresh输出，原.60m root fixture及850步安排保持。active-bound/实际arm q/target及callback gain/cap只读字段可用于说明实际约束暴露。求解成功与进程exit0不代替真实到G、接触及动力学证据；未达目标仍记未证明。原120分钟总/45分钟单run额度及4096暂缓状态保持。独立reload已由D042完成，不再等待或重复它。

## V29-D044：批准已证明限位内的pregrasp预定位与bounded-DLS合并运行

2026-09-19T02:42:50+08:00。**决策方：PLANNER；实现/运动学计算方：WORKER 01a0b592-48e3-7ad0-9263-4cb605862ed6。** 状态：**KINEMATIC_PLAN_INSPECTED / MERGED_REFERENCE_A3_AUTHORIZED / CONTACT_PENDING**。

读取[完整IK计划](candidates/C001/reference_ik_plan.json)、[读数](candidates/C001/reference_ik_plan_readout.json)、生成脚本及probe消费路径。Pinocchio使用当前URDF与真实TCP85mm，直接比较29个实际root-relative初态，未拟合修正模型变换；最大位置差9.81e−6m、角差1.65e−6rad。SciPy带界非线性最小二乘对34门各11点求解。Main用reference-a2实际native limits独立核对374个q，零越界、最小关节余量0.523558rad，相邻采样点最大单关节变化0.038456rad；当前实际pregrasp相对G的−.10m门法向偏移也匹配至1.53e−6m。

该计划只证明采样运动学可行，不证明连续无碰撞/物理接触。probe在真实natural reset及其证据保存之后，一次预置每case合法pregrasp arm q和全开手指；随后由原drives及D043 bounded-DLS执行动作，动作期不瞬移关节。11点路径用于建立可行分支，实际probe只取首点初始化，后续为反馈DLS；不将它描述为已经逐点执行。

批准[合并后的reference-a3命令](../../.ai/runtime/v29_baseline_team/D044_IK_PREPOSITION_APPROVAL.json)，D043命令显式增加--ik-plan绝对路径；.60m/.50m root fixture、34case、850步、GPU0及原预算保持。相应离线helper纳入worker归属。实际证明从明确预定位后的pregrasp开始，不声称policy从natural起点学会抵达。无需再等待该具体命令权限，真实到位/接触/动力学继续据运行验收，4096与正式TRAIN仍未放行。

## V29-D045：reference-a3机械窗口成立，持位/接触路径仍失败，转定向小规模控制修正

2026-09-19T02:59:40+08:00。**裁定方：PLANNER；运行/实现方：WORKER；独立读数：runtime QA只读agent。** 状态：**BOUNDED_MECHANICAL_RESPONSE_SUPPORTED / RESET_PARAMETER_RETENTION_SUPPORTED / CONTACT_NOT_SUPPORTED / NO_TRAIN_APPROVAL**。

a3实际命令与D044逐argv一致，02:41:40–02:45:03完成，exit0、203.233s；550行reference+300行dynamics+102关键帧齐全。Main读取真实轨迹并亲自查看左右代表关键帧：pregrasp末端位置差约.255–.264m、闭合末端.346–.367m，全部550行双指handle法向力及raw contact点均为0，未证明可接触。实际arm/finger gains、damping、effort上限保持；合法seed首个控制样本已产生约19.5mm误差，随后持续漂移。离线URDF重力与记录的PD位置项比较支持持位控制不足这一定位方向，但不冒充实际扭矩读回或唯一原因。

独立读取release/limit/reset原始证据：18个closer门5s内回关.479–1.017rad，16个无closer门保持静止；原生上限窗口34门均实际到限位附近（误差≤2e−5rad），首个观测在step3之后，即0.08s，峰值相对M偏差仅约−2.34e−6至+1.35e−5rad。不同door参数并非配对因果实验；只支持本窗口实际作用。before/after自然reset的metadata、closed-G cache、door root、PhysX质量/COM/惯量/摩擦/limits及joint参数/targets/pos/vel一致；瞬态torque和robot state变化不混为参数漂移。

保留这些独立窗口，要求先修通probe全开pregrasp持位和接近控制，再补全34门接触。批准在原34固定样本中用F0左右plain及F2最大法向左右边界共4例、≤550控制步、GPU0原额度进行定向控制验证；可在probe内用有状态的原生限位内joint-position目标修正/已建IK路径，原physics/gains/effort/G/geometry保持，动作期不瞬移关节。独立机械窗口不因无关controller修正机械重跑；若修改相关参数则相应证据另判。具体[记录与授权](../../.ai/runtime/v29_baseline_team/D045_REFERENCE_A3_REVIEW_AND_FIX.json)。累计验证1304.151s，规模/正式训练继续等待接触路径及完整候选验收。

## V29-D046：批准目标积分控制及两例无render前缀，再回34例接触

2026-09-19T03:06:10+08:00。**决策方：PLANNER；实现方：WORKER 01a0b592-48e3-7ad0-9263-4cb605862ed6。** 状态：**INTEGRATED_TARGET_CONTROL_INSPECTED / BOUNDED_DIAGNOSTIC_AUTHORIZED / CONTACT_PENDING**。

读取[实际提案](candidates/C001/reference_target_integration_proposal.md)及bounded_dls_targets/真实调用。上一drive q_cmd保持状态；当前root-frame位姿误差按1/s增益及真实dt形成增量，再保留2mm/.02rad上限，使用实际J及原关节硬限位求下一q_cmd。积分基准从actual q变为上一command，原阻尼.01、预定位、implicit PD/gains/effort/geometry/G保持，未加力矩feedforward、事后clip或动作期状态瞬移。静态一致不预判实际稳定性。

同意将D045四例诊断收缩到F0左右plain两例无render、300/150/100步，原34manifest中的完整参数值由planner复制为[固定两例输入](../../.ai/runtime/v29_baseline_team/D046_CONTROL_TWO_CASES.json)。[批准记录](../../.ai/runtime/v29_baseline_team/D046_TARGET_INTEGRATION_APPROVAL.json)给出两例及后续34例render/contact精确命令；两例实际持位/到目标并形成双指接触后可自主进入34例，若仍漂移/无接触则先报告具体失败。最终34例覆盖要求保留。

D045已成立的B01/B04响应与reset参数保持，后续纯arm controller改变不机械重复其300步；相应命令dynamics/limit steps均为0。GPU0原120分钟总/45分钟单run额度不变，使用新输出并报告输入/实际命令/ETA；无需再问同一命令权限，4096规模及正式TRAIN仍未放行。

### V29-D046 执行路径补充 — 2026-09-19T03:10:35+08:00 / PLANNER

Worker 提交 `reference_prefix_command.json`：两例 manifest 与已批准 D046 两例逐值一致，裁剪 IK plan 的同名两例与原 34 例 plan 逐值一致；无 render，300/150/100 接近闭合步，dynamics/limit 均 0。确认这些 worker 路径和 fresh output 可按 D046 立即执行一次，无需再次申请。预计 180s；持位、到 G 和预期双侧接触成立后可按原条件直接继续完整 34 例。保留独立 B01/B04 窗口；本补充不表示 runtime PASS 或正式训练批准。核对记录：`.ai/runtime/v29_baseline_team/D046_PREFIX_COMMAND_CONFIRMATION.json`。

### V29-D047 — 2026-09-19T03:13:23+08:00 / PLANNER / 两例控制修正实测与34例运行登记

Main 独立读取 `reference_control2_a1/reference_trace.jsonl` 的全部550行及实际STATUS：300/150/100步齐全，80.714s、exit0。pregrasp末步误差0.0513/0.0410mm，close末步5.342/4.741mm、角误差0.00739/0.00605rad；两门每指均有2个真实handle contact点及非零法向力。原始点/力/时间尾段读回保存在 `.ai/runtime/v29_baseline_team/D047_CONTROL2_RUNTIME_REVIEW.json`。D046两例条件成立，仅覆盖该reference fixture与两例，不升级为全域/策略PASS。

Worker已按D046条件启动 `v29-c001-contact34-a1`，实际命令为原34例+原IK plan、render、550步、dynamics/limit均0，GPU0 named tmux；登记真实wait_until，预计03:15:25 HKT，不重置等待。原B01/B04独立证据继续保留。验证累计 1384.864756sec；正式TRAIN仍未批准。

### V29-D048 — 2026-09-19T03:19:14+08:00 / PLANNER / 完整34例接触原始证据

`v29-c001-contact34-a1` 于03:15:58 HKT正常结束，272.947s、exit0。ETA到点后一次进度检查已经观察到完成，无需延长等待。Main读取完整550行、34例manifest逐值一致；全部34末步双指handle body contact，close位置误差4.502–5.917mm，角误差0.001214–0.014112rad；所有记录的指—panel/rose与臂—panel/rose法向力为0。Main亲自查看6幅代表close总览及F2低h最大法向approach、最大closing-roll/return close关键帧。

接受上述有界事实；whole-handle sensor非零尚不能单独证明接触在预期夹持段，委托原runtime QA独立定位原始contact point到本门handle frame，限定CPU只读，不重跑动力学、不改source。点区域核对仍待结果；正式完整baseline候选尚未提交，不记B05整体/策略PASS或TRAIN_APPROVED。原始逐例记录：`.ai/runtime/v29_baseline_team/D048_CONTACT34_RUNTIME_REVIEW.json`。累计validation 1657.811636sec。

**D048 接触区域核对完成补充 — 2026-09-19T03:23:59+08:00 / PLANNER**

原runtime QA对逐步真实handle位姿及全部原始点作独立CPU定位：34门、2,305条contact记录、28,386点全部投影到各门free main-grasp interval，return/neck/axle/root-tip归类均0；18门有return。主杆arclength范围32.76–97.63mm。Main保留该区域结论；解析中心线归类不等于每个convex分片面验收，不采用“已排除全部seam效应”的扩张结论。Main额外亲自查看F3 return、F6 taper close与F0 pregrasp关键帧。结合D048完整trace和图片，接受这34门的有界reference持位/到达/预期杆段双指接触路径；此项无需追加GPU重跑。完整baseline候选仍待逐项报告/验收，正式TRAIN未批准。细节并入原D048_RUNTIME_REVIEW。

## V29-D049：短路径条件成立，释放既有4096环境单batch规模验证

2026-09-19T03:29:11+08:00。决策方：PLANNER；worker：01a0b592-48e3-7ad0-9263-4cb605862ed6。D048完整34门reference及点区域定位已接受，结合已保留64env PPO/checkpoint、真实reload/natural和机械窗口，D032/D034的短路径条件成立。批准 `candidates/C001/scale4096_command.json` 原argv：GPU0/seed291/4096env/1batch、scratch、既有只读callback，fresh输出；预计2400s，单次2700s和累计7200s保持。当前已用1657.811636s，剩余5542.188364s。使用独立named tmux及真实ETA单一等待，记录初始导入、VRAM、吞吐和checkpoint；不缩域解决资源失败。完整候选未验收，正式TRAIN未批准。精确命令/输入边界：`.ai/runtime/v29_baseline_team/D049_SCALE4096_VALIDATION_RELEASE.json`。

## V29-D050：批准真实stage advance/snapshot/reset生命周期小probe

2026-09-19T03:29:11+08:00。决策方：PLANNER。读取worker具体提案/命令以及probe branch、真实world G来源、StagedTaskBase snapshot/weighted reset和DoorPregrasp outer friction restore路径。批准原34例、无camera、process-local staged ratios [1e-6,1,0,0,0,0]/capacity200；先自然reset留读回，一次明确机器人初态布置，3次真实env.step形成生产stage1 snapshot，再一次真实reset_envs_idx及前后读回。新branch提前返回，CLI保留的300/150/100不执行。无bank/stage/sentinel伪造；按实际选中的nonzero子集报告，不为凑全数重采，异常明确暴露。此证据只覆盖具体生命周期与参数保持，不替代全阶段或生产采样比例结论。建议未启动时先做该小probe再长scale，同GPU0串行；实际生产失败先处理。精确命令/范围：`.ai/runtime/v29_baseline_team/D050_STAGED_LIFECYCLE_APPROVAL.json`。

**D049/D050 实际启动与顺序补记 — 2026-09-19T03:34:59+08:00 / PLANNER**

Worker报告4096已启动。Main核对receipt/STATUS和命令：`v29-c001-scale4096-a1` 实际03:25:43 HKT launch，argv与D049逐项一致，named tmux `jam-v29-c001-scale4096-a1`；日志GPU0 Active。该实际启动早于03:29的D049澄清记录，worker当时引用既有D032/D034条件授权；保留真实时序，不将D049日期倒填。当前明确保留已运行的同范围验证，不因之前“优先便宜probe”建议停跑/重排。真实ETA 2026-09-19T04:05:43+08:00，原45min上限 2026-09-19T04:10:43+08:00；Main登记同一逻辑等待，不周期性看日志。GPU释放后执行已批准D050。纯读stage1首份robot/door snapshot dump已经包含于Main此前读过并批准的probe，不构成新的待批项。记录：`.ai/runtime/v29_baseline_team/D049_SCALE4096_START_OBSERVATION.json`。

## V29-D051：4096单batch初始化延长到75分钟上限

2026-09-19T04:08:27+08:00。决策方：PLANNER；依据worker真实40min ETA事件和Main读取的RUNNING STATUS。当前CPU活跃、尚无PPO/config/checkpoint；worker报告64env场景47.45s，线性外推约50.6min仅作为估计，不能当作已证实扩展性或实际进度。当前run原argv/域/规模保持，允许本次single-run由45延到75min；其他run原限额不变，累计120min不变。此前已完成1657.811636s，本次即使用满4500s，累计约102.630min，仍余1042.188364s。

沿真实03:25:43启动计算，下一决策点为2026-09-19T04:25:43+08:00（总60min），本次硬上限为2026-09-19T04:40:43+08:00（总75min），不是从本次批准重新计时。Worker更新当前run的持久化WAIT_PLAN与旧45min停止定时，继续同一进程/逻辑等待；实际完成或失败提前报告，路径诊断有明确发现即处理，不因安静日志自动判挂死。未放宽生产域/scale/1batch或正式TRAIN。具体记录：`.ai/runtime/v29_baseline_team/D051_SCALE4096_BUDGET_EXTENSION.json`。

**D051 执行确认 — 2026-09-19T04:12:49+08:00 / PLANNER**

Worker报告已应用同run的04:25:43决策点及04:40:43上限，原本不存在旧kill timer。Main读取真实WAIT_PLAN，wait_until_epoch与D051一致；WAIT_PLAN记录等待决策时点，本身不代表自动kill。读 `scale4096_initialization_path.md`：4096 prototype author调用后4096 CopySpec；这是源码调用数量，不证明实时phase或实测复杂度。一次native attach被host ptrace拒绝，未绕过/重试，未改production/dependency。保持同一等待，无额外调试授权或轮询。

## V29-D052：4096目标规模单batch完成、checkpoint与全样本参数读回

2026-09-19T04:32:56+08:00。决策方：PLANNER。收到60min进度事件后一次读取实际STATUS，已于04:26:31结束、exit0、3647.831707s（60.797min），不再等待旧上限。Main核对原始日志262144timesteps/1batch、iteration23s；独立CPU读取真实step1 checkpoint，policy/value/RMS、optimizer/scheduler/trainer state及既有env log字段均存在，global_step1。after_first_batch读回4096env，actor[4096,133]/critic[4096,138]float32 cuda0。scene creation3341.085s，整体setup span3579.787s；不将单batch23s称为长期稳定吞吐，也不用日志Total episodes计数推断4096完整自然episode。

独立runtime QA读取全部4096metadata及全量PhysX张量：七族计数584/584/586/584/586/586/586、X1=0，return2042/2054、左右2048/2048、mass档1365/1365/1366、closer2048/2048。按源码分层/循环随机化解释有限计数；native参数与metadata浮点精度一致，begin与after_first_batch的稳定参数逐值相等。实际handle目标0与USD authored-15°的解释留到最终B02/current writer条目，不据此自动改代码或判新bug。此为单batch参数保持，staged另证。

资源：Torch峰值allocated13704821760B/reserved16313745408B；30s设备采样max13719MiB，不冒充连续设备峰值。累计已完成验证5305.643342s，剩余1894.356658s。D050已批准，释放GPU后继续；完整baseline未验收、正式TRAIN未批准。详细原始证据与范围：`.ai/runtime/v29_baseline_team/D052_SCALE4096_RUNTIME_REVIEW.json`。

## V29-D053：staged-a1真实失败定位及一次自然刷新step修正

2026-09-19T04:39:36+08:00。决策方：PLANNER。实际staged-a1于04:28:55失败、112.419077s/exit1，34门3步全为Stage0、Stage1 bank全0；不记生命周期PASS。Main对29个详细pose样本重算，dx1.1788–3.8777m全部超出真实gate[.68,.72]m，侧差最大.8067m；arm偏差仅.000185–.004493rad低于.1阈值。末态XY距原自然起点仅0.000012–.001185m，说明预设.70m位置未保留。

源码实际路径：reset_all留下need_to_refresh_envs，首个_post_physics_step将target_robot_root_states写回后清标志，与原自然起点恢复现象一致。批准worker仅修probe顺序：先一次真实零action env.step完成自然reset待刷新流程，再从live root/G设置同一个一次性fixture，随后原3次step/snapshot/native reset；不手动清flag、不写stage/bank、不改生产gate或模型。可补纯读gate分量作为故障证据。原D050精确命令仅fresh输出a2，预计300s，可直接执行无需再问。之前scale/contact/mechanics证据保持。累计5418.062419s，余1781.937581s。授权：`.ai/runtime/v29_baseline_team/D053_STAGED_A1_DIAGNOSIS_AND_FIX.json`。

## V29-D054：终止采证callback事件接线差异

2026-09-19T04:43:19+08:00。决策方：PLANNER。仅一次对照scale输入快照的callback窄diff：删除正常budget终止时不可达的on_train_end override，改为on_step_end在既有control.should_training_stop为true时调用原capture(end)。实际trainer默认callbacks在自定义callbacks前，已安装transformers DefaultFlowCallback在global_step>=max_steps设置stop；该dispatch位于trainer提前return之前。capture主体、生产训练/环境逻辑未改。接受此事件接线的INSPECTED结论；新end路径尚未实际执行。D052原onebatch after_first_batch即当次terminal读回，原快照/参数/checkpoint证据保留，不为补同一份end数据再跑GPU。最终候选应明确包含此小delta。记录：`.ai/runtime/v29_baseline_team/D054_TERMINAL_CALLBACK_REVIEW.json`。

**D053 public reset wrapper执行补充 — 2026-09-19T04:45:25+08:00 / PLANNER**

核对worker实际a2 branch与StagedTaskBase restore链：采样后的robot root/dof先进入target buffers，door状态由task setters写入；使用既有env.reset_all公有入口会继续把选中的robot targets写入并刷新观察，因此能采得真实robot+door恢复状态。批准该wrapper替代单独reset_envs_idx，确认共4真实ticks（1natural flush+原3fixture），无手动flag/bank/stage/target-buffer写入。a2 argv与D053已给命令完全一致；worker立即按该命令运行，无需再申请。原300s ETA、GPU0、剩余预算和结果边界保持。

## V29-D055：Stage1真实snapshot/restore证据与B02 target继承解释

2026-09-19T04:57:15+08:00。决策方：PLANNER。staged-a2实际267.896307s/exit0；Main读原始4step记录：warm step将34个pending refresh从true消费到false，随后34门真实advance到Stage1并各保存1样本，reset全部实际选择Stage1。Main独立对照真实snapshot：29个详细robot/door root、29个robot关节位置（先按config与native joint names对齐），及全部34门door q/qdot均零差；完整metadata/closedG/native参数与稳定drive/limit/target字段前后相等。接受该Stage1 fixture生命周期范围，未扩为全阶段、生产选择频率或策略成功。

B02：Main实际读取HEAD/current的_reset_door_states及apply_torques_at_task_dof，AST均一致；当前v29新增q0 setter只选hinge。全部4096 handle position target两端0，effort从0到+.261799395Nm；旧变量虽用15*pi/180，实际API是effort target。它是继承行为，不能解释成运行时−15°位置target或新的handle修复。该具体疑问关闭，不重设handle。详细记录：`.ai/runtime/v29_baseline_team/D055_STAGED_RUNTIME_AND_B02_REVIEW.json`。

累计validation5685.958726s，余1514.041274s。等待冻结最终输入与完整逐项候选索引/训练评估提案；完整baseline未验收，正式TRAIN未批准。

## V29-D056：冻结C001逐项验收，唯一Stage5定向证据补齐

2026-09-19T05:11:48+08:00。决策方：PLANNER。C001320文件与当前逐字节一致，两个最小只读lane分别核对B01/B04及reward/reset/time，Main核对B05实际构造/frames、B06/B03、B02及运行/命令整合。未发现需改production的阻断源码缺陷；已完成证据按每项范围保留。完整逐项表在 `.ai/runtime/v29_baseline_team/D056_C001_PER_ITEM_ACCEPTANCE.md`。

FIX_REQUIRED仅补Stage5非零定向实际环境reward读数：真实注册权重虽正确，当前自然样本止Stage0/实际staged止Stage1；不能据零episode sums宣称新Stage5项实际执行。用少量env的一次明确reward fixture，读实际root/goal/rpy/stage、raw与scaled贡献、Stage4零新项及K处理；不要求策略成功、不重演所有继承阶段/不写假bank。D023保留source+resolved既有公式检查，不机械追加物理过渡campaign。Worker准备具体新probe命令供一次review，完成后C002仅补相应delta/证据。

正式6000batch/48h与eval20min暂未批准。未来新产物按既有log-layout使用logs_rl/.../base_v29/push_baseline_C002_seed291及logs_eval/base_v29/.../natural_final，更新所有checkpoint/output引用，无迁移/哈希/别名。剩余有界验证1514.041274s。

## V29-D057：批准两环境Stage5实际reward probe及一组启动配置修正

2026-09-19T05:26:51+08:00。决策方：PLANNER。已读完整probe及精确argv，确认native xyzw→wxyz转换、实际RPY刷新、生产_compute_reward的raw/registered scale/K后callback采证；允许本次明确声明的pose/stage输入fixture，不冒充自然晋级/策略结果。四case为Stage5对齐、heading-only、roll/pitch与Stage4相同姿态。

启动前补齐独立Hydra compose的exp_base显式值，以及experiment_dir/output_dir指向probe目录；所继承exp_base目前仍含hydra:runtime.choices.exp，resolve前必须像既有reference probe一样固定。该一组修正仅配置身份与输出，不改域/权重。worker完成后可直接执行原argv，无需再问。GPU0/2env/no-render，ETA180s，单次600s，总预算7200s与剩余1514.041274s保持。批准记录：`.ai/runtime/v29_baseline_team/D057_STAGE5_PROBE_APPROVAL.json`。正式C002训练/eval提案路径已符合D056，预算仍未批准。

## V29-D058：Stage5 probe入口env目录转发修正

2026-09-19T05:30:24+08:00。决策方：PLANNER。收到START后实际STATUS已于05:27:53失败，30.657253s/exit1；不用再等原ETA。实际trace定位初始化时a2_v26_8 penalty trace缺env.config.experiment_dir，尚未进入reward fixture。保留D057顶层路径，补env.config.experiment_dir与env.config.save_rendering_dir转发到当前probe目录，与既有reference入口一致；允许使用++compose overrides以保存实际解析身份。命令仅改fresha2输出，其余2env/4cases/GPU0/180sETA/600s上限保持，修正后直接执行无需再问。记录：`.ai/runtime/v29_baseline_team/D058_STAGE5_PROBE_ENV_DIR_FIX.json`。累计5716.615979s，余1483.384021s，正式TRAIN未批。

## V29-D059：Stage5 fixture只刷新实际quaternion/RPY，避免重复生命周期callback

2026-09-19T05:35:05+08:00。决策方：PLANNER。a2实际55.915164s/exit1，已经完成自然step，随后probe重放full observation callback触发同step grasp-streak校验。Main核对实际两行与LeggedRobotBase1318–1319完全一致：从simulator.base_quat刷新env.base_quat，再用原get_euler_xyz_in_tensor得到env.rpy；helper已导入。保留实际native pose写入及生产_compute_reward/原reward hook，不改counter/streak/gate/bank或生产源码。批准stage5_a3_proposal原精确命令立即运行，GPU0/2env/四fixture、ETA180s/上限600s不变。仅证明目标三项即时reward输入/输出，不当作完整合成observation或policyrollout。累计5772.531142s，余1427.468858s。记录：`.ai/runtime/v29_baseline_team/D059_STAGE5_RPY_REFRESH_FIX_APPROVAL.json`。

## V29-D060：C002全部baseline项验收，批准首轮GPU0正式训练及完成后评估

2026-09-19T05:46:32+08:00。决策方：PLANNER，依据Owner D030离线授权及D031验收职责。实际Stage5 a3 exit0/123.124696s；Main已读取原始两环境四fixture输出：对齐0、heading raw .1224999353/scaled−.0097999945、roll/pitch旧−.000656+新−.002624=−.00328，Stage4新项0；dt=.02/K1且实际K名单排除三项。该即时reward证据关闭D056唯一缺口，不作为自然晋级或策略成功。C002继承320份未改生产输入与全部已接受边界，仅新增probe；Main一次比对其12427bytes冻结文件一致。C002 ACCEPTED。

**TRAIN_APPROVED**：worker物理GPU0，seed291/4096env/6000batches/save100/scratch，启动总上限172800s；39.34h为单batch外推。精确argv及输入/资产、输出、预算、停止/eval合同见`.ai/runtime/v29_baseline_team/D060_C002_ACCEPTANCE_AND_TRAIN_APPROVAL.json`。训练完成6000和精确final checkpoint后，已批准同GPU0串行64自然首episode、full load评估，上限1200s；输出按规范共置。一次初始化检查，随后实际1000/3000/6000里程碑及完成/失败/截止事件；named tmux/supervisor持久等待，不周期性模型轮询。失败不自动重启、换配方/换checkpoint；未授权第二seed、pull、B02/N01/N02、hardware或Git。现有GPU0租约保留worker，批准时未收到实际启动回执。累计有界验证5895.655838s/7200s；正式训练和eval额度另计。

**D060 实际启动确认 — 2026-09-19T05:50:41+08:00 / PLANNER**

Main一次核对实际receipt、binding及STATUS：命令argv与批准逐项一致，物理GPU0、独立tmux `jam-v29-c002-push-seed291-train`；实际启动 2026-09-19T05:47:43+08:00，当前过程RUNNING/acceptance UNASSESSED。初次初始化事件预计 2026-09-19T06:52:43+08:00，依据既有4096 setup而非固定周期。正式完成暂估 2026-09-20T21:08:07+08:00，48h总上限 2026-09-21T05:47:43+08:00，均沿实际启动计时。worker负责一次初始化及实际1000/3000/6000里程碑、提前失败/完成/截止事件；Main登记同一逻辑等待，不重复看日志。训练receipt不自动eval，D060与binding中的独立final eval条件授权保持，worker条件满足后串行执行。未将启动确认当作初始化、PPO进度或策略PASS。记录：`.ai/runtime/v29_baseline_team/D060_FORMAL_START_OBSERVATION.json`。

## V29-D061：正式初始化确认与本轮loss监督范围例外

2026-09-19T06:52:01+08:00。决策方：PLANNER。Main读取实际first-batch原始capture：4096env、actor[4096,133]/critic[4096,138] float32 cuda0，左右2048/2048；独立重算33个保存reward均有限，范围−.0358585715至.0177710801，所选stage全0。七族读回584–586；scene creation3215.823238s，前6iteration23.35/22.59/22.39/22.28/22.26/22.18s，均值22.508333s只是早期吞吐。Torch首batch峰值allocated13704821760B/reserved16313745408B；worker设备21767MiB/96%是点读，不当峰值或长期稳定证明。

原worker prompt §7确实包含loss监督。Main追踪_get_train_metrics→self.log→state.log_history→ModelSaveCallback：保存前显式删除log_history；一次CPU读取既有4096 step1 checkpoint也确认该字段不在序列化state中。不能依赖现有checkpoint恢复数值loss，也不能以有限reward/entropy推断loss有限。本轮明确记录监督范围例外：loss=NOT_OBSERVED，保留已运行冻结C002，不为此改动/注入/重启；原loss监督项未获完整证据，不伪装满足。D060其他运行/评估要求及48h总上限不变，当前不追加loss导出实现。

Worker已经持久化实际1000 checkpoint/失败/截止等待至2026-09-19T13:37:29+08:00，Main沿用同一逻辑等待；硬上限2026-09-21T05:47:43+08:00保持。详细事实、来源及限制：`.ai/runtime/v29_baseline_team/D061_INITIALIZATION_AND_LOSS_OBSERVABILITY.json`。

## V29-D062：清理已处理queue副本与当前worker通知去重

2026-09-19T11:31:30+08:00。决策方：PLANNER；Owner截图指出worker训练期间仍有D032起的大量历史通知排队。核对本机工具无可调用send/steer，CLI queue用于后续turn；当前worker的wait_event.py实际检测STATE.updated_at并读取last_planner_message，截图已确认worker处理D061，因此已处理的queue副本没有随文件通知自动消费。使用queue是既有工具限制下的选择，持续留下重复通知不是所需设计。

建议Owner删除我发的、已处理D032–D061及重复确认排队项，不再点steer重放；Main没有执行UI删除。后续Main→当前有文件事件waiter的worker，只发布决定和STATE消息指针，沿用该通知机制，不再另发同一份queue副本。此说明不修改STATE.updated_at、不新发queue、不打断现有1000checkpoint等待。D060/D061批准、GPU0、冻结输入、48h和final eval合同保持。详见`.ai/runtime/v29_baseline_team/D062_QUEUE_DUPLICATE_EXPLANATION.json`。

## V29-D063：1000-batch里程碑记录并继续原训练

2026-09-19T13:32:25+08:00。决策方：PLANNER。实际checkpoint事件2026-09-19T13:26:53+08:00，worker CPU读回global_step1000、policy/value张量有限；Main读取该artifact与对应console，未重复load。Mean reward61.54958、entropy8.93851；Stage2 active .6629，双指接触/抓握完成显示.0000，左侧历史max3并有1份Stage3 snapshot、右侧max2，双方goal显示0。当前未显示可靠抓握或目标完成；四位显示零不能当从未接触，训练/staged指标不替代final natural eval。loss仍D061 NOT_OBSERVED。

Main定向核对原_update_reward_penalty_curriculum：零pending natural samples转rate=None，任一侧缺失跳过scale更新；日志显式将缺失rate/min写NaN。当前三项penalty-driver NaN与该日志路径一致，不是loss字段；不把聚合NaN解释为整个里程碑均无自然episode，也不据此宣布数值稳定。

iteration均值22.85513s、last10022.802s，实际wall/batch24.122174s包含overhead；916次GPU采样max22845MiB、utilization中位21%，不外推连续峰值或确定瓶颈。继续D060冻结配方、现有GPU0和最终自然评估合同；不重启/调参/追加probe。沿用worker已登记3000事件等待至2026-09-20T04:11:21+08:00；6000暂估2026-09-20T22:57:03+08:00，硬48h截止2026-09-21T05:47:43+08:00不变。D062文件事件通知一次，不重复queue。完整review：`.ai/runtime/v29_baseline_team/D063_BATCH1000_MILESTONE_REVIEW.json`。

## V29-D064：3000-batch里程碑记录并继续原训练

2026-09-20T10:57:34+08:00。决策方：PLANNER。实际3000事件2026-09-20T04:04:00+08:00；worker CPU读回global_step3000、policy/value张量有限，Main核对readout及对应console，未重复load。相对1000，reward61.54958→109.80628、entropy8.93851→10.64041；Stage2双指接触字段.0000→.4098，Stage3 active.0462；双方历史max均3，Stage3 snapshot日志计数为左8688.0156/右9810.0469。snapshot字段为聚合日志，不能写成独立自然成功episode数；both-contact也不是抓握成功率。grasp-complete/to3仍.0001，Stage4/5 snapshot与双方goal均显示0；整任务成功未建立。保留D061 loss NOT_OBSERVED及D063三项penalty-driver空样本NaN解释，不重复审计或追加运行。

最近2000iteration均值24.70518s、last10025.2487s；实际1000→3000 wall/batch26.313477s。1747次区间GPU采样max24079MiB、utilization中位26%，仅记录采样范围。继续D060冻结配方、GPU0及最终自然评估合同，无重启/调参/新probe/预算延长。6000暂估2026-09-21T01:59:40+08:00；沿用worker单一6000/terminal等待至2026-09-21T04:11:14+08:00，硬48h截止2026-09-21T05:47:43+08:00不变，暂估余量3.801h。最终eval仍须实际训练成功终止于6000且精确final checkpoint存在。通过D062文件事件通知，不增加queue。详细review：`.ai/runtime/v29_baseline_team/D064_BATCH3000_MILESTONE_REVIEW.json`。

## V29-D065：GPU1旧Doorman-derived handle对照、独立计划与Git版本保存

2026-09-20 11:25 HKT。决定来源：Owner要求增加GPU1对照，由新worker team负责，撤回B05恢复原Doorman door asset，并单独落地handle ablation plan；随后明确要求保存baseline及ablation的Git记录。

Planner将对照界定为v29−B05整组：恢复本项目pre-B05/v28实际使用的旧几何、G/FixedJoint及consumer，保留v29高度、B01/B04、B07、机器人、时序/奖励/PPO。当前全局v29开关同时控制dynamics/geometry/frame，必须在独立工作区拆出明确B05选择，不可全局关闭。共同逐env参数从C002实际metadata配对，旧尺寸/hook另按旧分布生成；未记录附属随机量明确限制，不声称完整USD配对。原最早upstream的target/cap差异不随几何回退混入。该组检验B05整体，不单独证明“七族数量”因果。

独立计划：`scriptsFORhuman/v29/a2_piper_base_v29_handle_ablation_plan.md`。Planner确定匹配seed291/4096env/6000batch/save100/scratch及48h单次上限、最终64自然eval20min；必要短验证GPU1累计20min/单次10min，实施后提交一次聚焦候选验收和精确命令绑定。正式GPU1 TRAIN_APPROVED尚未签发，worker尚未绑定；当前没有新GPU运行/租约。Owner不需重复批准同一目标，日常实现由新worker推进。

已按本次Git授权在独立worktree物化C001320文件+C002新增probe共321份冻结输入，一次逐字节比较一致；本地baseline commit保存118个实际变化路径，建立`codex/v29-c002-baseline`及固定tag`v29-c002-baseline`。再从该tag建立`codex/v29-handle-ablation`，工作区`/home/baoquanc/workspace/DoorDog-A2_Piper_v29_handle_ablation`；本计划及版本约定在该分支留独立提交，后续代码候选按递增tag管理，不覆盖baseline。未提交原工作区无关改动、未切换A2_Piper、未push。保存的是已验收实现，不是策略质量PASS。

独立协调状态：`.ai/runtime/v29_handle_ablation_team/STATE.json`。本次没有改动GPU0训练源码/资产、原STATE或已有等待，也没有向其追加queue消息。

## V29-D066：Owner要求planner/两个worker统一减少通信频率

2026-09-20 11:30 HKT。来源：Owner明确指出queue容易堆积堵塞，要求planner、baseline worker和handle ablation worker全部减少message，非重大progress/待决策不轻易发送。已落实到验收合同§6、baseline worker prompt§7和handle ablation plan§10。

只在完整候选/验收裁定、需介入实质异常、约定重大里程碑及最终交付通知；普通实施状态和无需新动作的review只存档。合并同事件事实/证据/所需动作，不做收到/继续/等待确认链；启动与初始化尽量合并，每100保存不通知。底层已有terminal通知时不人工复述，后续仅补实质结果。使用已有文件事件时不再queue副本，纯记录不发布消息指针或反复唤醒worker。

此次Owner新约束通过一次共享STATE文件事件告知正在等待的baseline worker，无queue；不要求ack，原6000等待绝对时点、48h上限、GPU0和final eval保持。新ablation尚未绑定worker，约束进入计划/独立STATE及Git计划版本，等待Owner交付的新团队读取。记录：`.ai/runtime/v29_baseline_team/D066_LOW_FREQUENCY_COMMUNICATION.json`。

**D065 worker身份/实施范围绑定 — 2026-09-20 11:45 HKT / PLANNER**

收到新worker首次合并绑定，Main读取实际`/home/baoquanc/workspace/DoorDog-A2_Piper_v29_handle_ablation/scriptsFORhuman/v29/handle_ablation/WORKER_BINDING.json`：任务`01a0bce5-1c5c-7863-88a6-247bab697ae3`、独立cwd `/home/baoquanc/workspace/DoorDog-A2_Piper_v29_handle_ablation`、分支`codex/v29-handle-ablation`及baseline/plan tag一致。WRITE_SET均落在独立worktree；生产/config/pairing/versioning/runtime由team负责人写，bounded probe与fixture/IK helpers为独立writer，legacy链路检索只读。已登记共享team contract与实际agent ID，并为该worker登记GPU1逻辑租约，仅覆盖D065既定20min累计/10min单次短验证；物理占用仍在实际启动时核对，不抢占其他任务。正式TRAIN_APPROVED仍为空，未收到新run receipt。按D066仅本地登记，不发送确认消息/queue；原GPU0 STATE与等待不改。下一项是合并候选或真正待裁定事项。

## V29-D067：HA-C001 聚焦验收与 GPU1 TRAIN_APPROVED

2026-09-20T12:10:53+08:00。决策方：PLANNER，依Owner D065委托及本次完整候选请求。接受tag `v29-handle-ablation-c001`，固定baseline tag `v29-c002-baseline`。Main一次候选绑定检查、一个只读IsaacLab reviewer及本次必要证据检查完成；没有重新审计C002全边界，也未追加GPU验证。

实现保持v29总开关而关闭独立B05，复用旧几何/G/FixedJoint及匹配consumer/LEFT镜像；B01/B04、.90–1.20高度、B07、奖励/时序/PPO/机器人不变。4096共同参数表16字段逐env与A实际metadata一致；B实际16门metadata/native及一批PPO通过，checkpoint读回360有限张量。四例LEFT/RIGHT×plain/hook通过真实PD接近/闭合，Main亲看四张close图并读native/force；8/8双指最终接触12.20867–19.95174N。根固定fixture只证明该路径，不代表策略成功/持续接触。三次准备累计338s/1200s，含113s输出路径错误的失败记录，各次<600s。接受eval_agent_trl.py仅只读metadata导出的WRITE_SET补充；最终eval尚未执行。

签发本组TRAIN_APPROVED：独立worktree、GPU1、seed291、4096、scratch、6000、save100，实际启动起172800s上限，worker独立tmux/supervisor执行。精确argv与timeout wrapper保存在D067。沿用共享ledger同一gpu:1所有者，扩为正式train→eval；物理空闲由worker启动时确认。完成暂估3451.947+6000×26.3134767835秒，须由B实际初始化/吞吐修正，ETA不作为自动停止条件。当前仅已批准，尚无正式启动receipt。

实际成功终止6000并有精确final checkpoint后已条件批准64自然首episode/full loader/staged与K关闭评估，1200s。D067具体绑定null-table独立64命令及唯一paired64 table override变体：只在A实际final64完整共同metadata存在时用已审阅builder生成runtime参数表；否则如实记录未配对并用独立64域，绝不截取训练4096前64。初始化/1000/3000/6000窗口与最终结果按D066合并通知；loss仍NOT_OBSERVED。未配对frame/cover/material/reset及整组B05干预限制保留。只给本worker一次批准通知，不要求ACK；GPU0源码/STATE/租约/原逻辑等待不变。详情 `.ai/runtime/v29_handle_ablation_team/D067_HA_C001_ACCEPTANCE_AND_TRAIN_APPROVAL.json`。

## V29-D068：HA-C001 实际启动与4096初始化登记

2026-09-20T12:53:39+08:00。PLANNER一次核对实际receipt/binding与D067：argv、48h timeout wrapper、cwd、候选tag一致；实际2026-09-20 12:13:25 HKT在物理GPU1的独立tmux启动，硬截止2026-09-22 12:13:25 HKT。Main读实际first-batch JSON，确认4096、B05=false、actor[4096,133]/critic[4096,138] float32 cuda:0；4096均有v29Dynamics/legacy radius、无v29Handle，左右各2048，高度.900027504–1.199882869m。worker逐门共同+legacy字段比较0差异，native各项有限且仅记录float32精度差；Main未重复全表/native计算。初始化745.163s，worker读回时已59 batch，早期23.421525s/batch不代表长期吞吐或策略稳定。

沿用同一1000/terminal/failure/deadline等待：1000暂估2026-09-20 18:57:32 HKT，含10%余量的事件等待截止19:34:15 HKT（epoch1789904055.965588），6000暂估2026-09-22 03:29:19 HKT，48h硬截止不变。旧STATUS内启动ETA不覆盖ACTIVE_EVENT_WAIT/WAIT_PLAN。loss仍NOT_OBSERVED，策略UNASSESSED，D067最终64条件评估保持。GPU1启动前辅助136MiB枚举context由worker确认属于固定GPU2渲染进程并保持不动；Main不重复查询GPU或干预。按D066及无需确认要求只存本地review/STATE，不改通知updated_at/last_message、不发queue或确认事件；GPU0任务原等待不变。详见`.ai/runtime/v29_handle_ablation_team/D068_HA_C001_START_AND_INITIALIZATION_REVIEW.json`。

## V29-D069：完整C002/B05的N01独立Pro预研交付

2026-09-20T14:29:40+08:00。Owner要求重新思考恢复图、恢复触发与退回落点，并把抗失抓恢复Teacher训练和Student能力传递分别论证；历史novelty仅作参考。主底座固定完整C002保留B05，不使用HA-C001消融生产输入。Main与一个只读context researcher定向核对stage/旧恢复/DAgger路径：C002未启用旧v27恢复；默认DAgger ratio1.0实际Teacher控制高层动作，框架支持Student执行与在线Teacher标注，但无自动比例课程/跨batch数据聚合；Student81D＋RGB不含显式stage/contact/门真值。以上是设计输入，不是N01方案选择或方法效果结论。

已从固定baseline tag用独立Git index建立并发布审阅分支`codex/v29-n01-pro-20260920`，提交主题`Prepare C002 N01 recovery and teacher-student research handoff`，时间`2026-09-20T14:22:17+08:00`；本地review/远端tracking/远端分支一次核对一致。完整321份冻结输入加11份同tag依赖、当前brief/已存runtime、历史参考分成三个普通ZIP，共390份选定文件；无checkpoint/权重，版本以tag和提交主题/时间标识。Drive新目录 `https://drive.google.com/drive/folders/1TYMXvIKohP6-IlrhYa6hXFn4qjZqWvIo`，六个文件上传后已核对名称/大小/父目录。提示词 `scriptsFORhuman/v29/pro_handoff/20260920_n01_recovery_transfer/PRO_REVIEW_PROMPT.md` 要求Pro独立检索一手研究并返回完整图/Teacher-Student方案/伪代码/最小pilot及本地接手包。

本次只完成研究交付，未创建N01实验工作区、实现方法、运行测试/仿真/训练或新增GPU预算；原GPU0/GPU1源码、合同、STATE通知和持久化等待均不变。source/evidence与历史层级已标注，C002 pending候选字段由D056/D060取代、3000训练日志不等于自然成功率、loss仍未观测；未收到Pro结论。交付收据见本次`.ai/outgoing-artifacts/base_v29_n01_recovery_transfer/`目录。

## V29-D070：N02独立预研及A2/PiPER方向力建模的完整Pro交付

2026-09-20T15:15:35+08:00。Owner同步提出N02六问：以完整C002/B05为底座，先能力缺口/目标/信息/控制用途再网络，历史shadow和UniFP/SixthSense仅参考；Teacher/Student数据与记忆分开，直接讨论持续感知驱动的姿态、arm主导、controlled swing/quiet hold和强回弹下握持。Main定向source核对与一个只读文献researcher提供输入，没有选择或实施N02方法。

Owner在首版上传时追加Pro实际尝试A2＋PiPER动力学与roll/pitch方向出力验证。已提取28 link惯量、20配置DOF的URDF/config限值/驱动及TCP85mm，明确arm100N·m/finger45N是仿真配置，不能代替实机持续能力；Main未求解force或运行新仿真。完整执行brief要求匹配TCP/门坐标方向，分离Jacobian/重力/足地支撑/抓握/base平移与姿态贡献，回传实际代码/数值/图及执行状态，不将坐标旋转或静态上界当能力证明。

首版文件保留，新建完整R2 `https://drive.google.com/drive/folders/1m7C_mk9bFPxGcQK0RTUFwl3J8rPHjE7g`。三个普通ZIP共396份文件，包含同一332文件C002source、当前brief/已存证据/model inputs、历史novelty/shadow；六文件均已核对名称/字节数/父目录。研究分支`codex/v29-n02-pro-20260920`通过独立index更新且已push/remote核对，R2提交主题`Add A2-PiPER dynamics and directional force modeling to N02 research`、时间`2026-09-20T15:07:08+08:00`。无生产源码改动、无N02实验worktree/训练/预算变化，原GPU0/GPU1 STATE/资源/等待不变。最终prompt位于`scriptsFORhuman/v29/pro_handoff/20260920_n02_online_adaptation/PRO_REVIEW_PROMPT.md`；Pro结果未收到。

## V29-D071：HA-C001 1000重大窗口登记（无新裁定）

2026-09-20T19:38:58+08:00。按D067对901–1000合并窗口作一次本地核对，A/B各100完整batch、35选定字段与读回一致；worker精确step1000 checkpoint的policy20/value19个state tensors有限，Main未重复载入，loss仍NOT_OBSERVED。A→B Stage2 active 64.7444%→7.0320%，全env-step双指接触打印0→1.2434%，稳定/2→3打印0→0.1174%；B在Stage2 active条件下的打印均值比值为17.682%/1.6695%。B左右Stage3 occupancy约62.489%/61.887%，Stage3 bank A为LEFT1/RIGHT0、B各2048；B handle角p95的step均值仅.002483rad，双方Stage4/5 bank和goal仍打印0。仅支持本seed撤回B05整组的早期抓稳/阶段推进观察，不归因七族数量、不称自然成功率或跨seed显著；staged reset、量化零、非pooled quantile、时间平均bank计数及未配对随机量限制保留。

ETA改用实际checkpoint900→1000的wall cadence 25.921150825023652s/batch，3000预计2026-09-21T09:53:48+08:00，6000预计2026-09-22T07:29:51+08:00；同一3000/terminal/deadline观察截止2026-09-21T11:20:12+08:00，原48h硬截止2026-09-22T12:13:25+08:00不变。WAIT_PLAN是新3000计划，ACTIVE_EVENT_WAIT仍保存已消费的1000记录，不能复活旧计时。Main仅更新本地STATE，不改通知updated_at/last_message，不发ACK/queue，不新建等待或轮询GPU；D067及原GPU0、B08待办状态不变。完整记录：`.ai/runtime/v29_handle_ablation_team/D071_HA_C001_BATCH1000_MILESTONE_REVIEW.json`。

## V29-D072：C002最终交付验收关闭，策略观测0/64

2026-09-21T10:31:21+08:00。PLANNER依D030/D031/D060及worker最终交付请求裁定：保留D056/D060冻结C002实现验收范围，接受一次seed291/4096/6000训练与64自然首episode评估的执行交付。实际命令/cwd/worker均与D060一致，训练exit0、45.4594h<48h，eval exit0、723.228s<1200s；精确final checkpoint step6000及actor/value有限读回、实际6000 terminal capture和严格full-loader记录已核对，Main未重复载入模型或重审源码。

一个只读runtime reviewer从原始64条per-env和metrics按env_id独立归约，0/64 goal；LEFT最高Stage2/4/5为2/27/3，RIGHT32例均Stage2，全部stage_overtime。episode长度827×34、1129×27、1430×3。LEFT6个holding-crossing和10个release观察分别保留，不当任务完成；左右差异无单独因果解释。高度/质量范围及由实际weight、hinge cap重建的质量×closer六格与worker一致，每侧各5–6；family/最大开角未导出，不能归因。loss仍NOT_OBSERVED，0/64仅为本次观测，不宣称总体概率精确为0。

B08仍高优先级OPEN，当前候选未修复Stage0 arm覆盖，也未证明它单独造成上述结果；本次不追加诊断大trace、训练、eval、seed或Teacher/G7绑定变化。GPU0本任务租约已通过team_state释放、worker task标completed；GPU1及其他任务资源/等待未改。按D062/D066发布一次共享STATE与PLANNER_TO_WORKER_D072_FINAL_ACCEPTANCE.txt，无queue副本、不要求ACK。完整决定`.ai/runtime/v29_baseline_team/D072_C002_FINAL_DELIVERY_ACCEPTANCE.json`；人类可读结果`scriptsFORhuman/v29/a2_piper_base_v29_C002_final_readout_20260921.md`。

## V29-D073：HA-C001 3000重大窗口登记（无新裁定）

2026-09-21T10:35:38+08:00。按D067核对A/B共同2901–3000窗口：各100完整batch、35字段与汇总一致；精确step3000读回policy20/value19个state tensors有限，Main未重复载入，loss仍NOT_OBSERVED。Stage2 active A70.1723%→B2.0955%，全env-step稳定/2→3为.0069%→.1064%，active条件估计.00983%→5.07755%。双指接触的active条件估计57.77%→27.67%受Stage2驻留群体变化影响，不能单项定退步或因果。streak p90的step均值3→3.387539；handle角p50约.0001→.727161rad、p95约.000202→.7854rad。B有明显压柄及RIGHT后段推进：LEFT最高Stage3、Stage3 occupancy70.0565%、Stage4/5 bank0；RIGHT最高Stage5、Stage4/5 occupancy57.8630%/7.5153%，Stage4 bank2048、Stage5 bank时间均值1365.201874。A同窗口双侧最高Stage3、后段bank0；双方goal仍打印0。结论限于本seed撤回B05整组的训练观察，不隔离七族数量、不给自然成功率；量化、非pooled quantile、时间平均bank、staged reset和未配对随机量限制保留。D072的A6000自然评估是另一终点，不混入本窗口比较。

实际checkpoint2900→3000 wall cadence 25.774870021343233s/batch，6000预计2026-09-22T07:23:24+08:00，同一6000/terminal/deadline观察截止2026-09-22T09:32:16+08:00，原硬截止2026-09-22T12:13:25+08:00不变；WAIT_PLAN与ACTIVE_EVENT_WAIT已一致。生产输入/配方/D067最终64配对或null-table合同不变，无新预算。Main只更新本地STATE与记录，不改通知updated_at/last_message、不发ACK/queue、不新建等待或轮询；GPU0 D072关闭状态与B08待办不变。完整记录`.ai/runtime/v29_handle_ablation_team/D073_HA_C001_BATCH3000_MILESTONE_REVIEW.json`。

## V29-D074：Owner直接授权同配方6000→8000续训及7000/8000自然评估

2026-09-21 11:08 HKT。**决策方：Owner；worker执行，Main登记，不是worker自批或Main重新批准。** 原指令及实际启动记录位于`.ai/runtime/v29_resume8000/OWNER_DECISION_AND_START.md`，精确argv/合同位于同目录`OWNER_AUTHORIZED_PLAN.json`。Owner要求保持当前配方、从6000 full resume到累计8000，用于判断训练量是否不足；累计7000/8000各一次相同设置64自然首episode，重点LEFT goal出现/增加、RIGHT突破Stage2并到Stage4，不以reward或训练阶段占比替代。是否进一步延长由自然结果趋势后续决定，本次不自动越过8000。D072原6000交付及0/64结果保留历史，本次是新的明确授权。

实际2026-09-21T11:01:01+08:00由原worker在GPU0启动，receipt `/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v29-c002-resume8000-seed291/RUN_RECEIPT.json`，Main只做一次实际命令与Owner计划的一致性核对，结果一致；STATUS为RUNNING，初始化/full-resume实际读回尚待报告。累计上限8000是absolute max_steps，从6000新增2000更新，不能误写成2000总上限。worker报告320份原生产输入与冻结快照直接比较一致，reward/action/assets及B08原行为保留；新增控制callback/协调脚本用于7000保存后CUDA同步、暂停同一PID、串行eval并续行，8000正常终止后再eval。Main未重复源比较或对已授权运行另行审计。初始恢复会natural reset并重建staged bank，不声称逐比特物理续接；7000同PID行为以届时实际记录为准。

worker操作性设置：训练含7000暂停评估预计2026-09-22T03:57:41+08:00，20h上限2026-09-22T07:01:01+08:00；每次eval1200s。此为worker在Owner限定任务内的执行上限，不冒写成Owner另行批准的wall数字。当前同一初始化事件观察至2026-09-21T12:06:01+08:00；沿实际初始化/7000自然/8000自然/失败事件持久化等待，Main不新增等待器或周期查询。GPU0已由新task v29_baseline_resume8000持有，原v29_baseline_worker的D072关闭不改；GPU1 HA-C001仍按D067，A/B同6000比较基准不替换为本次8000结果。loss仍NOT_OBSERVED，checkpoint有限性另报。只本地登记主STATE/路由，不发routineACK、queue或新的批准消息。详见`.ai/runtime/v29_baseline_team/D074_OWNER_AUTHORIZED_RESUME8000_REGISTRATION.json`。

## V29-D075：Owner授权B08公共修复与四方向同步

2026-09-21 14:36 HKT。Owner要求完成B08并更新N01、N02、B05-ablation，补充要求参考N01并保持公共逻辑一致。检查N01计划要求同类删除，当前公共源码尚未落实；本次以单一公共补丁删除普通与canonical Stage0在线arm累计target覆盖，保留真实reset、历史及原限幅/映射。四个开发worktree源码已同步，CPU实际step提取路径三步累计约0.18、RIGHT镜像及选定reset通过；一次整合检查确认公共路径一致。完整实现、目录和证据见[a2_piper_v29_B08_implementation_20260921.md](a2_piper_v29_B08_implementation_20260921.md)。没有新增仿真、训练、评估、Git commit或push，策略收益未验证。

原GPU0/GPU1任务后续还会从cwd重新加载评估源码，因此保持两者运行目录原文件；baseline修复使用`codex/v29-b08-stage0-arm`独立worktree，B05-ablation开发分支转到`/home/baoquanc/workspace/DoorDog-A2_Piper_v29_handle_ablation_b08`，原运行worktree在同一版本detach。N01/N02原工作区直接应用公共补丁，既有WIP保留。C002/HA-C001标签、D074续训和D067最终评估输入/资源/等待不变。主STATE仅增加公共开发路由，不发routineACK或新增轮询。

## V29-D076：C002同配方7000自然评估重大里程碑登记

2026-09-21 20:04 HKT。按Owner D074/W013既有授权登记worker `01a0b592-48e3-7ad0-9263-4cb605862ed6` 的7000自然评估结果，不新增批准或预算。实际eval exit0、720.633s，64唯一自然首episode；Main一次核对receipt argv/cwd与Owner7000计划一致、原始per-env/metrics归约一致、exact7000 full loader记录一致。LEFT goal由6000的0/32变为31/32，32例全部最高Stage5；RIGHT由6000的32例Stage2变为31例Stage3＋1例Stage2，Stage4+仍0/32。合计31 complete、33 stage_overtime。

按env_id对照6000，六个现有门字段逐项一致：door_open_lr、door_handle_side、door_hinge_drive_max_force、door_handle_drive_max_force、door_handle_height、door_weight。它支持相同已记录人口的checkpoint比较，不声称完整物理/RNG配对，不补造family标签或族别归因。实际trainer PID3055669在7000保存/CUDA同步后暂停、eval后同PID继续，pause/resume记录一致；没有第二次trainer重启或配方修改。Main未读取大trace、重复载入模型、查询GPU/进程或重新审计source。

判断更新：追加训练后LEFT自然任务明显改善，RIGHT确实跨过Stage2；7000尚未证明RIGHT推进到Stage4、双侧完整任务或7000→8000持续趋势。此前6000的周期性开爪/K5失败仍是那个checkpoint的真实诊断，不能继续描述成7000多数RIGHT仍过不了K5；本轮未读7000动作trace，不能声称所有开合周期已消失。B08开发修复没有进入此次冻结实验，loss仍NOT_OBSERVED。

继续原授权至累计8000及一次64自然评估，不自动延长。worker按6001→7000实际wall cadence 27.703256s/batch估计最终8000eval完成于2026-09-22T03:55:47+08:00；同一事件等待截止2026-09-22T04:46:58+08:00（epoch1790023618.2716725），原训练20h截止2026-09-22T07:01:01+08:00不变。主STATE承接同一等待，不新增定时器，不改通知updated_at/last_message，不发routineACK/queue。GPU1 D067不变，A/B同6000对照仍使用原A6000结果。完整记录：[D076](/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/v29_baseline_team/D076_C002_RESUME7000_NATURAL_MILESTONE.json)；原报告：[milestone7000_readout](/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/v29_resume8000/milestone7000_readout.json)。

## V29-D077：C002同配方8000最终交付接受并关闭

2026-09-22 11:08 HKT。PLANNER依据Owner D074/W013与最终交付请求，保留D056/D060冻结C002实现验收，接受并关闭6000→8000及7000/8000自然64评估交付。Main核对实际train/eval8000命令、cwd、worker和预算：train exit0、16.693h含初始化与7000暂停，eval exit0、619.306s；实际end capture为8000/4096，full loader exact8000一致。actor20/value19有限性采用worker已有CPU读回，未重复torch.load；PPO loss仍NOT_OBSERVED。一个独立只读reviewer从原始per-env/metrics/diagnostics确认64唯一自然首episode、左右各32、全部goal/complete/maxStage5，staged load/store/cache-clear计数均0，无阻断不一致。

自然结果6000/7000/8000：LEFT goal0→31→32/32；RIGHT越过Stage2 0→31→32/32，Stage4+0→0→32/32，goal0→0→32/32；总goal0→31→64/64。六个导出门字段与6000逐env一致；无family/最大开角归因、跨seed总体成功或硬件结论。此前6000周期性开爪与7000 Stage3卡点保留历史，不能继续称8000在同人口仍受其阻断；未读新动作trace，不宣称所有开合周期消失，也不隔离具体改善机制。B08未入实验。

worker已释放自己的GPU0 lease，ledger为released、task completed；Main不重复释放、不查询GPU。关闭同一持久化等待，以共享STATE+PLANNER_TO_WORKER_D077_RESUME8000_FINAL_ACCEPTANCE.txt发布一次正式裁定，无queue副本/例行ACK。没有8000后续训、额外seed、调参或绑定授权，下一范围由Owner决定；GPU1 D067及A6000/B6000对照基准不变。正式记录[D077](/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/v29_baseline_team/D077_C002_RESUME8000_FINAL_ACCEPTANCE.json)，canonical结果[a2_piper_base_v29_C002_resume8000_final_readout_20260922.md](a2_piper_base_v29_C002_resume8000_final_readout_20260922.md)。

## V29-D078：HA-C001 D067最终交付关闭与源侧GPU1预约释放

2026-09-22T11:20:11+08:00。Main依D067及本次最终交付请求接受执行交付：seed291/4096/scratch/6000/save100训练43h26m56s、exit0，在原48h内结束；一次final64为560.02s、exit0。Main一次核对实际train/eval receipt和STATUS与版本化归档一致，实际命令与D067一致；full loader精确6000、staged/K关闭。保留worker的policy20/value19有限参数读回，loss仍NOT_OBSERVED；未重复载入checkpoint或重算完整trace。

同6000进度A自然0/64，B32/64：RIGHT32/32 complete/maxStage5，LEFT0/32且全部maxStage3/stage_overtime。B LEFT已压柄约.785398rad，但episode最大hinge仅.069529–.121646rad（中位.097690），低于Stage3→4的.25门槛；定位停滞阶段，根因仍未识别。5901–6000双方100完整batch，训练窗口和自然episode分母分开，B训练average_goal_reached=.476912为每env最近完成episode buffer的时间平均。支持本seed撤回B05整组后的RIGHT成功改善，不支持双侧全面改善、不单独归因七族数量。A实际final64缺少完整COMMON_FIELDS，按预授权采用independent64/null-table，无训练表前64替代；最终评估及训练frame/cover/material/reset轨迹的未配对限制保留。A8000/D07764/64仍是另一训练进度结果，本比较使用A6000。

源侧共享ledger的v29_handle_ablation_worker任务已completed，gpu:1预约于2026-09-22 11:18:48 HKT释放；STATE关闭原D067逻辑等待。worker本地lease及物理GPU1空闲由其最终交付报告，Main未重复查询设备。结果文档由worker本地提交至codex/v29-handle-ablation-results-seed291，未push，候选/baseline tags不变；原开发分支仍在B08工作区。此为本地最终关闭，无ACK链、queue或新文件通知，无追加运行授权。

证据：[最终报告](/home/baoquanc/workspace/DoorDog-A2_Piper_v29_handle_ablation/scriptsFORhuman/v29/handle_ablation/results_seed291/REPORT.md)及同目录20份JSON；[D078关闭记录](/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/v29_handle_ablation_team/D078_HA_C001_FINAL_DELIVERY_CLOSURE.json)。
