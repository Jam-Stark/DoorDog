---
name: base-v28-camera-aware-rebaseline
status: active
scope: v28 re-baseline — MERGED asset, wrist tower and PiPER posture, staged camera contract, camera-aware bundle, three-seed reachability and qualification-oriented Teacher selection
last_verified: 2026-09-14
read_when:
  - implementing or resuming base_v28
  - changing the robot asset, default posture, camera mounts or A2_Base contract
  - interpreting v28 camera/telemetry metrics or the tower-clearance evidence
source_of_truth:
  - scriptsFORhuman/v28/a2_piper_base_v28_plan_20260909.md
  - scriptsFORhuman/v28/a2_piper_base_v28_deferred_register.md
  - gr00t/rl/config/robot/A2_Piper/a2_piper_vpiper.yaml
  - gr00t/rl/data/robots/v28_asset_comparison_20260909.md
  - gr00t/rl/envs/door/door_open_a2_base.py
related_entries:
  - base-v27-bilateral-hardening
  - base-v26-scratch-bilateral-teacher
---

# base_v28 camera-aware re-baseline

运行证据更新（2026-09-14 18:14 HKT，D047）：原三seed已完成1000时点的六条exact64；实际scratch配置/GPU分配成立。两侧D/S4+/complete为0，少量RIGHT到S3；相机CAMERA_PARTIAL，无事件保持null。它不是6000终点结论，训练按D046继续，A284尚未触发；统计与commit从runtime milestone_records/step1000.json路由。

当前路由（2026-09-14 10:54 HKT，D046）：Owner已批准G1失败后继续原三seed各6000 scratch，原C_T/门值/预算不变；WARM_FAIL与500消耗保留，warm附加臂取消。按原milestone、条件A284及固定资格合同推进，实际任务和资源仅由execution_20260913的state/receipts路由。下方G1停止点是历史时点，不再要求重复成本批准。

当前停止点（2026-09-14 08:56 HKT）：G1@500真实WARM_FAIL，RIGHT塔架>5N集6>2；LEFT/RIGHT complete=64/63、clean=64/47。双侧D≥40所以不触发PARTIAL；warm附加臂取消，后续scratch/WaveA/B/候选与render均NOT_RUN，原三seed终点未评估。按既定成本复议门等待Owner，不能外推scratch失败或几何无解。D16输出修复已在左右真实eval成立，晚阶段遥测有事件；完整分量及删失读[本次closure](../../../scriptsFORhuman/v28/a2_piper_base_v28_execution_closure_20260914.md)与D044/D045。N01/N02已回收为继续有界立项设计、实验执行DEFER；X05本次回收关闭。

审计材料入口：[Pro 原文、本地更新审计与 planner finalize 索引](../../../scriptsFORhuman/pro_reviews/v28/8435858/README.md)。原文与解析 prompt 保留归档时点，不在仓库保留重复 ZIP。2026-09-12 17:18 HKT，Owner 已同意 planner 裁决并授权方案/记录更新，M1–M5 已落实到活动文档；当前合同从 plan 与[决策日志 D038–D040](../../../scriptsFORhuman/v28/a2_piper_base_v28_decision_log.md)读取，不能再把审计原文的“草案未应用”当作当前状态。

当前批准合同（2026-09-12 17:18 HKT；修改：-codex planner；依据：-owner）：保持 MERGED、140 mm/38.76°、reset `[0,0.10,-0.10,0,-0.415,1.57]`、D17、bundle/K、原三 seed 各6000与固定 staged reset。D038 将原三 seed 的6000 reach可靠性与历史候选分列；D039 改用既定exact64 milestone的弱侧clean、双侧clean总和、较晚milestone、较小seed排序，DEV/CONF前固定最多两个不同checkpoint，主候选未确认才验备选，最多八条exact128 lane，不搜索第三名。D040 使实际按D31触发并启动的A_S284具有条件入池资格，待其既定评估完成后冻结候选池；其结果单列，不计原三seed分母，不证明driver因果收益。

实现状态（2026-09-13 01:47 HKT）：D038–D040 reducer/contract/manifest已同步；`v28_orchestrate.py`、`v28_watch_wave.py`、readout/render/closure及`v28_wait.py`形成实际入口。G1 full延长只执行额外500至累计1000，保存训练状态但不保存完整simulator/RNG轨迹；条件A_W281为独立旧C_S2 policy_only+actor RMS、seed281、6000批。对应CPU检查通过，该时点G1尚待真实运行；2026-09-14实际结论见顶部停止点。D16实际输出路径缺陷已修复，原G0 checkpoint旁exported副作用保留历史；新路径已于2026-09-14双侧eval得到实际证据。决策入口D041/D042；运行/等待从runtime的`execution_20260913/`读取。

后续回收：v28 closure成功或失败均触发N01/N02重新立项复核；X24在下一次asset/A2_Base变更立项时复核真实随机校准需求，X25保留Stage2/3位姿不稳触发。base单/双、真实光学/CAD、Student传感与安装件交换仍归C_S/G2。无事件指标保留null，投影为几何代理，学习失败不证明E_T几何无解。

当前状态（2026-09-12）：G0 launch门已通过，§9.7首个本地commit已完成（A2_Piper分支，未push）。D37三姿态离线与seed282数值确认均PASS；冻结harness无随机seed消费者，X24仍OPEN，不能声称随机分布校准。PPO64env×5batch与左右各64环境完整checkpoint评估均exit0，26个遥测字段接线与null口径完成；只观察到Stage0。X25与G2项保持OPEN。权威记录见v28的`g0_decision.json`和`a2_piper_base_v28_g0_acceptance_20260912.json`。

腕机局部绘图入口（2026-09-11）：[180mm/45°与140mm/38.76°四视图](../../../scriptsFORhuman/v28/camera/wrist_comparison_20260911/README.md)。沿原U3前/右/后/俯视方向、参考臂姿态`[0,0,0,0,0,1.57]`和统一比例绘制；140mm支架仅为保留原起端的连接包络，未验收间隙。该交付不代表选型、reset修改或恢复G0。

规划期记录（2026-09-09 HKT，历史状态 `PLAN_FROZEN_NOT_IMPLEMENTED`）。v28 是 re-baseline：asset 换为
`gr00t/rl/data/robots/a2_piper_vpiper_final_20260906`（+0.754 kg 安装件、convex 碰撞体、臂座下移 6.57 mm，
27 共享 link bit-identical），并新增独立固定 link `wrist_camera_tower`；PiPER reset 姿态换为
`[0,0.10,-0.10,0,-0.52,1.57]`（腕机 mount 倾角 θ=45° 时行走光轴 −15°；j2/j3 各离 0.95 软限位 0.02 rad）；base 相机对称上仰 15°；
camera-aware bundle = `penalty_a2_wrist_motion_l2`（j4/j5/j6 逐 stage 权重，Stage3 j6=0）+
`penalty_a2_wrist_tower_contact` + `penalty_a2_stage4_arm_default_pose_l1` 释放门控 −0.5。
训练 from-scratch 3 seed × 6000 batches，沿 v27 质量门与 exact128 DEV/CONF 资格程序。

规划期 COMPUTED 硬结论（证据 `scriptsFORhuman/v28/planner_evidence_20260909/`）：
- 腕机塔架在 F+Y（手指开合轴）上，任何倾角都看不到 TCP/指垫，只能看到把手条伸出指宽的两端（24–52%）；
  近场需求已改写为“把手条两端与上指尖外侧在 depth 可见”，抓握确认靠本体量 + base 相机。
- v27 RIGHT 门抓握姿态（`arm_j5` 顶 1.22 rad 限位）会让 180 mm 塔架穿过门板（Stage4 帧 41–65%），与 θ 无关；
  塔架碰撞体从 Wave A 起强制，Teacher 需学出新姿态。v26/v27 RIGHT 策略若上实机会撞相机。
- 新 asset/新姿态的质量与 CoM 变化（≤2.2 mm）远在 LMP A2_Base 训练随机化内；A2_Base 保留，替换预注册 v29。
- 加载器只读 USD 并按名称选择 27 个 body，30 体 USD 无需新的 body 顺序表；运行时自碰撞开启，
  `arm_body0`–金属板为零间隙接触对，G0 R2 必须测接触力。

共享层决定 D-17 `delta_action_clamp_to_dof_limits`（累积臂目标夹到物理限位；pull v7 posture trap 与主线 Stage5 j2/j3 钉限位同源）已于 2026-09-09 18:40 获 Owner 批准，两分支 v28 同时开启。
pull 分支同步计划：`scriptsFORhuman/pull_v28_alignment/a2_piper_pull_v28_baseline_sync_plan_20260909.md`。

2026-09-09 规划期授权历史：GPU0–7（受外部占用约束）；四个本地 commit 预授权；push、G7 binding、hardware 未授权。当时按 `U3_F45_B15` 开印的意见及随后暂停已被后续 D30/D35 等决定更新，当前状态以上方入口为准。
执行状态与 receipts 由 `scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/` 路由，不写入 memory。

## 2026-09-09 G0 执行决策（修改：-codex worker；Owner指示显式标注）

- Owner确认先sim后硬件设计，腕机真实CAD不存在，G0-C1′记NOT_RUN。
- Owner将细杆建议更新为与D435i等宽等厚的单长方体；当前截面90×25mm、长度114.700mm，独立`wrist_camera_tower`包含支架与外壳两盒。相机中心和θ45保持。总质量0.15kg（两盒各0.075kg）为估计，不是称重。
- 当前宽支架安装端按原gripper collision表面留1mm静态间隙，物理probe观察tower接触力为0；不构成hardware证据。
- 旧asset同姿态零指令flat-walk基线（64env）root z p50=0.4745m。Owner批准R3改为稳定1s后检查50控制步，root z∈[0.45,0.51]m、臂速度<0.5rad/s；R5预测修正为当前URDF FK的0.432637±0.01m，已与初始runtime读数吻合。
- `v28_verify.py resolve` CPU compose通过36项明确差异；delta动作限位与camera reward六项CPU测试通过。完整G0 runtime尚未通过；所有运行状态只从runtime目录读取。
- plan改动标注修改者`-codex worker`/`-owner`；worker按Owner指示修改时写明两者。

## Owner暂停（2026-09-09 19:56 HKT）

Owner明确保留独立安装件刚体，拒绝compound-trunk候选并暂停G0。当前G0未通过、没有本地commit、没有G1/正式训练。trunk↔vpiper_support接触未解决；plate4已清arm_body0，tower为0N。后续只按Owner明确恢复指示继续。修改：-codex worker；依据：-owner。

## 两个asset候选与最终裁切规则（2026-09-09）

Owner随后要求同时制作合并、裁切两个独立候选，放在robots目录后等待判断；该授权未恢复G0、未选择活动asset。修改：-codex worker；依据：-owner。

- 合并版：`gr00t/rl/data/robots/a2_piper_v28_merged_20260909/`；main/support/plate全部形状并入trunk，28刚体/20活动关节。各组件原质量、质心、完整惯量经旋转和平行轴定理合成，不使用统一密度假设。
- 裁切版：`gr00t/rl/data/robots/a2_piper_v28_cut_20260909/`；31刚体/20活动关节。Owner明确support也参与冲突时统一水平截去整个下部；因此main/support的全部visual/collision在trunk z=0.130m以下删除，距已定位冲突盒顶面1mm。早期局部分块/凹口裁切已被此规则取代。
- 两版全机URDF质量均45.64480826480732kg，arm/camera安装位姿保留。裁切版保留原inertial参数，是删除几何后的仿真近似。
- 已有CPU质量/几何计算与USD静态读回；两候选均未运行物理/G0。详细入口、对比图与证据见`gr00t/rl/data/robots/v28_asset_comparison_20260909.md`。当前候选状态`CANDIDATE_WAITING_OWNER_SELECTION`，G0仍`PAUSED_BY_OWNER`。

2026-09-11 HKT — v27 closure 后的 v28 状态：G0 `PAUSED_BY_OWNER`（trunk↔vpiper_support 源几何干涉造成持续自接触，两候选 asset MERGED/CUT 待 Owner 选型）。
Wave C 实际读数 `SCRATCH_NOT_ESTABLISHED` + `K_SCRATCH_SUPERIOR` 触发 §8.3：G1 warm probe 必做，K 块（16 项 + `penalty_a2_wrist_motion_l2`，
排除塔架接触与 stage4 姿态项，seed 键不复制）进入配方，`K_REACH_WITHOUT_COMPLETE` 具名失败预注册。v27 全部 64 样本格里唯一过门的是
SK_S213@6000（scratch + K）；所有 warm 血统格都未过质量门，失败分量集中在 crossing hinge。plan §1 新增 D-30…D-35 六条待 Owner 的建议
（分期冻结、K driver 备选、选种门拆层、单中置 base 相机、MERGED asset、塔高 140 mm/38.76°）。通过性核算：板上相机对门口净宽代价 0 mm。
证据：`scriptsFORhuman/v28/planner_evidence_20260911/`。G7 binding 建议维持 v23（§8.6）。

2026-09-11 23:06 HKT — Owner 决定：asset = MERGED（`a2_piper_v28_merged_20260909`）；腕机塔 140 mm / θ 38.76°，reset j5 −0.415
（行走光轴 −14.9°，法兰 z 0.4245）；合同分期冻结 D-30（base 相机单/双后移到蒸馏前，Teacher 用两布局并集包络）；K driver 备选 D-31；
选种门拆层 D-32（Wave A reachability 门选种，Wave B 合取门资格）；G0 恢复，R2/R3/R5 复跑与候选物理验收已授权。


## 2026-09-12 已验证执行事实

D34/D35实施：新塔架实际静态间隙1mm，支架长76.227187mm，按旧D20单位长度质量估算支架0.049843403kg＋外壳0.075kg。MERGED复合mass差0、COM/I误差均≤1e-16。R2监测体全部0N，原trunk/support自接触已在该检查中消除。K完整配方及分层reducer已实现。G0-L失败集中在stand零指令残余微速度的相对门，绝对量和后续判据由Owner查看readout决定，不将它等同于行走能力崩溃。修改：-codex worker；停止依据：-owner。


## D36 判据与再次停止（2026-09-12）

Owner判定原默认站立微速度失败为判据仪器缺陷，修订为p50≤max(1.15×baseline, floor)且p95≤1.15×baseline；vx/vy floor=.002m/s、yaw=.004rad/s，pitch/roll无floor。G0-L-swap仅共享floor，p50/p95上限仍是当前policy、不使用1.15倍。默认数据先于修订已可见，原FAIL保留且禁止GPU重跑；后两姿态按D36预注册。新类Stage2的vx050/pitch、vy_pos/roll、vy_pos/yaw比分别1.208313/1.230491/1.164372，触发STOP。X-24/N-09登记单次run无null分布估计、下次asset/locomotion更换前同asset异seed自比校准；本次不补seed282。修改：-codex worker；依据：-owner。


## D37与G0 launch验收（2026-09-12）

指令轴维持p50≤1.15×baseline，零指令耦合轴p50≤max(1.15×baseline,CAP)，CAP vx/vy=.1m/s、yaw=.1rad/s、pitch=.05rad、roll=.04rad；全部p95≤1.15×baseline，swap的相对上限仍为当前policy。D36已被取代，原FAIL与两次事后修订披露保留。旧旧小扰动实际arm_j5变化，不是j4，65比值范围.970277–1.008755，不能称原比值为噪声。282旧/新各一次真实运行的数值分支通过，但冻结harness没有设seed后的随机消费者，两侧同asset281/282均全指标相同，X24保留。PPO与全字段接线通过不等于Stage2–5事件或Teacher质量通过；G1完整v28+K仍是下一必做训练门。修改：-codex worker；依据：-owner。
