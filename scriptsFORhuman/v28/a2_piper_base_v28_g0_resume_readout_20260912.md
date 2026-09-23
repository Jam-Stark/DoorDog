# v28 G0 恢复执行记录：当前 G0 与首个本地 commit 已完成

当前入口更新：2026-09-12 17:18 HKT；修改：-codex planner；依据：-owner（D038–D040）。[G0 acceptance](a2_piper_base_v28_g0_acceptance_20260912.json)与 [runtime decision](runtime_logs/v28_camera_aware_rebaseline_20260909/g0_decision.json)记录 `G0_PASSED_FIRST_LOCAL_COMMIT_COMPLETED`，首 commit 见 [receipt](runtime_logs/v28_camera_aware_rebaseline_20260909/resume_20260911/first_commit_receipt.json)，未 push；本次核对尚无 G1/Wave A/B 结果。

以下 STOP、D36/D37 与“等待首 commit”为原时点的执行历史，保留不改。G0 只证明修订后的工程数值准入与接线，不含随机校准、晚阶段行为、Teacher 资格或硬件验收。D038–D040 的新选择合同见 [plan](a2_piper_base_v28_plan_20260909.md)与[决策日志](a2_piper_base_v28_decision_log.md)；A_S284 已获条件候选资格，执行代码仍待同步，不能以本文历史中的“资格未定”作为当前合同。

## 历史：原始 STOP_G0_L_FAILED

日期：2026-09-12 HKT。修改：-codex worker；停止依据：-owner（G0-L失败STOP，阈值/路由变更按plan §9.8）。

MERGED、140mm/38.76°腕机、j5=-0.415、base并集包络和K配方已落地。R1/R2/R3/R5及A4通过；G0-L默认姿态匹配比较未过，因此按指令停止。没有继续其它姿态、PPO smoke、G1或Wave A/B，没有commit/push。

## G0-L失败读数（RUNTIME）

新旧asset均使用[0,0.10,-0.10,0,-0.415,1.57]，64env、相同13个指令块与seed281。两组全程均0摔倒。以每个块的五个物理指令分量p50误差逐项执行candidate≤1.15×baseline，未加绝对下限。

| 失败项（均为stand零指令块） | 旧asset p50 | MERGED p50 | 1.15倍上限 | 比值 |
|---|---:|---:|---:|---:|
| vx残余速度，mm/s | 0.573011 | 0.728073 | 0.658963 | 1.2706 |
| vy残余速度，mm/s | 0.747493 | 0.896274 | 0.859617 | 1.1990 |
| yaw残余角速度，mrad/s | 0.904333 | 1.119121 | 1.039983 | 1.2375 |

其余62/65项p50比较通过。vx=0.5块的实现/指令斜率：旧0.940937、新0.931902，下限0.890937，通过。失败集中在零指令站立的极小残余速度比值，不据此声称行走能力崩溃；但冻结的1.15倍门确实未过。未自行更改阈值、滤除stand项或重跑挑结果。是否调整零指令判据须Owner决定。

原始结果：`runtime_logs/v28_camera_aware_rebaseline_20260909/resume_20260911/walk/{baseline_default,v28_default}/metrics.json`；逐项比较：`walk/default_comparison.json`。两进程exit0，FAIL是验收结果，不是执行失败。

## 已完成

- D34/D35：MERGED 28刚体/20活动关节；同新几何独立输入的复合惯量差mass=0、COM=4.60e-19m、I=5.38e-17kg·m²；USD已转换并读回。
- 腕机实际1mm安装间隙已重求：支架长76.227187mm、估算质量0.049843403kg＋外壳0.075kg，总0.124843403kg；质心/惯量重算。trunk为8支架+双外壳+中央外壳并集，中央不另计第三台相机质量。
- K块17项、G1完整配方、备用A_S284(target_stage=5)、K_REACH_WITHOUT_COMPLETE、reachability/qualification分层reducer已实现。CPU compose通过53项登记差异；7项v28语义/姿态检查通过，resolved-asset/M23子集检查通过。
- R1/R2/R3/R5 RUNTIME_PASS：trunk、arm_body0..6、tower在R2窗口全部0N；R3 root z为0.465865–0.477995m、臂|dq|max=0.050957rad/s；R5为0.424513m。
- A4 COMPUTED_PASS，无非过滤刚体对穿透。
- C3旧v27轨迹扫掠已完成，3个lane/stage未过20mm条件，panel min约-20mm、frame min约-2.64mm。按plan §3.2保留旧轨迹FAIL；不是v28 policy结果，更不代表较小最终硬件方案不可行。
- 新朝向raw字段及首次越门yaw锁存已接入；R2自然零指令trace和离线归约已走通。SDK内参与RGB/depth相对外参已接入。未观测的crossing/release/Stage5统计保留null，不能冒充这些事件已在PPO中验证。

## 未完成与状态

默认姿态G0-L失败后，未运行新asset的hold/Stage2比较、5-batch PPO smoke与完整PPO/eval遥测验证、G1及后续训练。G2-C1/C1′/C2/C4仍按D30后移，非本次阻塞原因。A_S284是否参与选种在plan尚未明确，当前仅预注册备用配对报告，不擅自扩大A_S281–283选种范围。

当前权威状态为`runtime_logs/v28_camera_aware_rebaseline_20260909/g0_decision.json`。保留R2运行时字节快照`resume_20260911/source_lock_g0/`和停止时完整源码快照`source_lock_stop/`；后者包含后处理SDK归约、步行判据脚本及执行记录，不声称这些后处理改动重新运行了R2。没有硬件操作或Teacher/G7 binding更新。


## D-36：Owner 修订判据后恢复（2026-09-12 HKT）

依据：-owner（2026-09-12 00:26 HKT 明确裁决）；执行与记录：-codex worker。上文为修订前的原始 FAIL 记录，保留不改。默认姿态三项失败由 Owner 裁定为判据仪器缺陷；本次 D-36 在看到默认姿态数据之后修订，hold/类 Stage2 尚未运行，对后两者是预注册。原始 metrics 与 `walk/default_comparison.json` 未改，也未重跑默认姿态 GPU。

新比较 `walk/default_comparison_d36.json` 同时记录 `criterion_version=d36`、`status=PASS`、`legacy_status=FAIL`。逐轴 p50 采用 max(1.15×基线 p50, FLOOR)，vx/vy 下限 0.002 m/s、yaw 0.004 rad/s、pitch/roll 无下限；同时新增无下限的 p95≤1.15×基线 p95 合项。

- 7 个使用下限的比较全部通过：stand 的 vx/vy/yaw、roll_neg 与 roll_pos 的 vx/yaw。
- 58 个纯比值比较全部通过，最大 1.107077（vy_pos/yaw_radps）。
- p95 合项 65/65 通过，最大 1.085112（vx025/yaw_radps）。
- vx=0.5 斜率 0.931902≥0.890937；新旧两侧各 0/64 摔倒。

G0 仍未通过：继续运行并比较 hold/类 Stage2，全部通过后执行 5-batch PPO smoke 与完整遥测验证，才能到首个本地 commit 点；任一 D-36 姿态失败仍 STOP。X-24 如实保留单次运行、缺少零假设散布估计的限制；本次不追加 seed282 自比校准。


## D-36 后续结果：类 Stage2 未过，按规则停止

记录：-codex worker；停止依据：-owner（D-36）。当前状态 `STOP_G0_L_D36_STAGE2_FAILED`，G0 尚未通过。新 MERGED hold/类 Stage2 各运行一次、进程均 exit0；分别对照已存在的旧 asset 同姿态 seed281/64env 基线，没有补跑默认姿态或 seed282。

| 姿态 | D36 | 旧纯 p50 判据 | p50 通过项 | p95 通过项 | 新旧摔倒 | vx050斜率（新 / 下限） |
|---|---|---|---:|---:|---|---|
| default | PASS | FAIL | 65/65 | 65/65 | 0/64、0/64 | 0.931902 / 0.890937 |
| hold | PASS | FAIL | 65/65 | 65/65 | 0/64、0/64 | 0.908500 / 0.864195 |
| stage2 | FAIL | FAIL | 62/65 | 65/65 | 0/64、0/64 | 0.934246 / 0.883650 |

类 Stage2 的三项失败如下。三个块均有非零指令；pitch/roll 按 D36 不设下限，yaw 的比值上限已高于 0.004 rad/s 下限。三项的 p95 均通过，不能以 p95 单独替代 p50/p95 合项。

| 块 / 轴 | 单位 | 旧 p50 | 新 p50 | D36 上限 | p50 比值 | p95 比值 |
|---|---|---:|---:|---:|---:|---:|
| vx050 / pitch_rad | mrad | 5.936860 | 7.173582 | 6.827389 | 1.208313 | 1.048885 |
| vy_pos / roll_rad | mrad | 7.263770 | 8.938002 | 8.353336 | 1.230491 | 1.003806 |
| vy_pos / yaw_radps | mrad/s | 37.344381 | 43.482769 | 42.946038 | 1.164372 | 1.064895 |

综合证据：`walk/all_postures_comparison_d36.json`；逐项证据：`walk/{default,hold,stage2}_comparison_d36.json`。原始默认 FAIL 文件与上方表格保持不变。

按预注册停止，不改阈值、不重跑挑结果；未启动 PPO smoke、完整 PPO/eval 遥测验证、G1 或正式训练，未 commit/push。D36 源码字节快照为 `resume_20260911/source_lock_d36_stop/`；GPU4/5 与本任务 writer 释放情况见 `resume_20260911/d36_stop_cleanup.json`。


## D-37：第二次事后修订与 seed282 确认前置

依据：-owner（2026-09-12明确裁决）；执行：-codex worker。以上原始FAIL与D36段落均保留。D36的“比值是噪声”解释被更正：同asset/seed/命令、只把arm_j5从−0.52改到−0.415的65项比值min/median/max为0.970277/1.000604/1.008755；Owner原文称j4，实际j4始终0。此对照说明固定seed下响应可复现、对小扰动平滑，不是换seed分布。证据：`d37/old_asset_posture_perturbation.json`。

D37按权威commands.json分层：任一步非零的轴为指令轴；两侧slope的null/非null均已与分类核对。指令轴p50维持1.15倍，耦合轴p50可用max(1.15×baseline,CAP)，全部p95仍1.15倍。CAP=vx/vy0.1m/s、yaw0.1rad/s、pitch0.05rad、roll0.04rad。`cap_applied`表示原比值分支失败、需要CAP分支；`cap_sets_limit`另记CAP是否大于比值上限。

| 姿态 | D37 / D36 / 原判据 | 指令轴max比值 | 全轴p95max比值 | 依赖CAP的项数 |
|---|---|---:|---:|---:|
| default | PASS / PASS / FAIL | 1.091012 | 1.085112 | 3 |
| hold | PASS / PASS / FAIL | 1.123854 | 1.105375 | 3 |
| stage2 | PASS / FAIL / FAIL | 1.062727 | 1.111611 | 5 |

仅离线重判，三组seed281 GPU均未重跑。G0-L尚未成立，当前`PENDING_D37_SEED282_CONFIRMATION`。预注册文件`d37/preregistration.json`已在GPU运行前写入：类Stage2 seed282旧asset/MERGED各一次64env×13blocks；用D36停止快照harness和单独冻结D37 reducer。任一命令轴>1.15、耦合项越CAP、p95/摔倒/斜率失败，或旧asset281/282自比命令轴>1.15均STOP。X24由本次自比决定关闭或保留；X25登记臂前伸耦合残余与X19朝向遥测的关联。


### D37 seed282结果：数值门通过，X24保留

旧/MERGED两个新进程分别于17:28:48 UTC启动、17:30:33/39退出，均exit0。新旧比较指令轴max1.062727，p95max1.111611，耦合项均在CAP内；旧/新vx050斜率0.933650/0.934246，下限0.883650；均0/64摔倒。旧asset281/282自比的19个指令轴与46个耦合轴，median/max均1.0，超过1.15项数均0。

**证据限制**：每种asset的全部block读数与其281结果精确相同。冻结harness在reset后调用manual_seed，后续无采样，eval policy无随机算子，命令/初值/phase/history固定，未显式设置PhysX seed。因此这是确定性复现，不能关闭X24随机校准项，也不是独立随机样本。详细source核查见`d37/seed_exposure_audit.json`。Owner注册的数值分支均通过，按该分支继续5-batch PPO与完整遥测验证，G0整体仍未通过，尚不能commit。


## D37 后 G0完成：等待首个本地commit

记录：-codex worker；授权与验收路由：-owner。64env×5batch PPO smoke正常退出并保存`model_step_000005.pt`，两个新reward均出现真实训练日志值（wrist motion最后−0.0413，tower contact 0）。随后完整checkpoint在LEFT/RIGHT各自然起始exact64评估，两个进程均exit0；每侧22,400条首回合raw记录通过schema/有限数/形状检查，§6.4的26个输出字段全部存在并完成归约。证据：`resume_20260911/telemetry_validation.json`。

该短训练checkpoint只观测到Stage0。Stage2–4可见率、释放回位、越门yaw、Stage5门口方位等7个无观测字段正确为null，不能声称晚阶段事件或Teacher开门质量已验证。G0验收的是接线链路；这些事件的实测覆盖仍需后续正式评估。

当前G0 launch门通过：资产/姿态/惯量与body合同、A4、R1/R2/R3/R5、D37步行数值门、5batch PPO及全字段导出/归约。旧v27 C3扫掠FAIL仍原样保留，后续v28轨迹需重测；G2光学/硬件项按D30后移。X24（无有效随机seed暴露）与X25保持OPEN。当前权威状态`G0_PASSED_PENDING_FIRST_LOCAL_COMMIT`，满足§9.7首个本地commit点；未push，G1/Wave尚未启动。
