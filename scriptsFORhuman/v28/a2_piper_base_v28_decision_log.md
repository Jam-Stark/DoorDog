# v28 决策日志：G0 与 planner finalize

更新：2026-09-12 17:18 HKT；本次修改：-codex planner；依据：-owner 已同意规划裁决并要求修改 plan、做好记录。历史执行记录保留各自时点与作者。

当前更新（2026-09-17 16:58 HKT）：Owner因更急切的后续改动要求提前停止训练并直接进入Wave B（D058）。A284最后完整日志迭代5167、最新保存checkpoint5000，6000训练终点与双侧评估取消；按原D039排序冻结主候选A_S282@6000（weak clean12、总73）和备选A_S284@5000（12、总38），身份在DEV启动前落锁。原三seed终点reach1/3（REACH_SEED_UNSTABLE）保持；资格门、C_T和固定DEV→CONF程序不变。

以下 D018–D037 保留原讨论、暂停、事后修订与执行过程；末尾 D038–D040 为本次新决定，不回写原评审或旧运行结果。

| ID | 决定 | 修改者 / 依据 | 状态 | 重审触发 |
|---|---|---|---|---|
| V28-D018 | 先仿真、后硬件设计；真实腕机支架CAD尚未设计，G0-C1′记NOT_RUN，不冒充CAD通过。 | -codex worker / -owner（本次任务明确回复） | ACCEPTED | 真实CAD到位 |
| V28-D019 | 腕机单长方体支架截面90×25mm，与D435i等宽等厚；外壳另一个盒；替代8×8mm细杆。 | -codex worker / -owner（本次任务明确建议） | ACCEPTED | 几何或runtime验收失败 |
| V28-D020 | 保持相机中心和θ45；宽支架安装端按原gripper碰撞表面定位，沿轴移27.158370732mm，最终支架长114.700015242mm，静态间隙1mm。支架及外壳各估0.075kg，总0.15kg。 | -codex worker / v28 §4.2 / Owner宽支架设计 | ACCEPTED | CAD/实测质量到位或runtime接触 |
| V28-D021 | 按预授权R2分支把金属板碰撞高度5→4mm、顶部下降1mm；visual/质量及安装位姿不变。arm_body0最大接触由11.56N降为0，trunk异常接触未解决。 | -codex worker / v28 §4.2 / §9.6 | ACCEPTED | R2仍未通过，继续定位源asset碰撞 |
| V28-D022 | 不生成hash/SHA；CPU compose明确键差异，mesh使用字节比较，运行记录保留路径/命令/原始读数。 | -codex worker / -owner（当前任务AGENTS明确禁令） | ACCEPTED | Owner显式变更要求 |
| V28-D023 | R5旧预测0.40m与D-03a姿态不一致；当前URDF FK为0.432637003m，runtime为0.432636678–0.432637036m。保留原区间匹配=false和实际读数，不把数值改写成0.40m。 | -codex worker / 当前source与runtime事实优先于计划预测 | ACCEPTED | G0决定解释R5报告项及R3高度门 |

详细证据路径见 `runtime_logs/v28_camera_aware_rebaseline_20260909/decision_log.jsonl`。

D018–D023 记录时 G0 尚未通过，没有第一个本地 commit，未启动 G1、正式训练或更新 Teacher/G7；这不是当前状态。

## V28-D024：G0 高度判据修订

Owner批准R3稳定1s后检查50控制步，root z[.45,.51]m且臂|dq|<.5rad/s；R5期望改为当前FK .432637±.01m。 修改：-codex worker；依据：-owner。

## V28-D025：Owner暂停

Owner拒绝采用compound-trunk候选，保留原独立刚体并暂停G0；不做首个commit，不启动G1。 修改：-codex worker；依据：-owner。

## V28-D026：制作两个候选

Owner要求同时制作合并路线与裁切路线，分别置robots目录等待判断；不选择活动asset，不恢复G0，不commit。 修改：-codex worker；依据：-owner。

## V28-D027：整块水平裁切

Owner指出早先局部裁切不符合意图：若仅蓝色底部脚板冲突则只切脚板；若橙色support也冲突则统一水平截去整个下部。当前几何证据已定位support参与冲突，因此最终对main、support全XY范围在trunk z=0.130m作单一水平裁切，visual与collision同步删除下部，保留原joint/inertial。此规则取代早先局部碰撞分块裁切与局部长方体凹口。两版仍为待Owner选择的独立候选，G0保持暂停。修改：-codex worker；依据：-owner。

证据与入口：`gr00t/rl/data/robots/v28_asset_comparison_20260909.md`、cut目录的`validation/cut_geometry.json`和`validation/horizontal_cut_comparison.png`。仅CPU几何/参数比对与USD静态读回；本候选未运行物理/G0。

## V28-D028：降低腕机高度与俯角（PROPOSED，2026-09-10）

Owner提出降低腕机安装高度，并相应减小俯角。核对来源后确认：180mm是参考姿态下相机外壳中心相对法兰的抬高量，沿用旧U3方案；v28此前比较角度，没有优化高度。当前实体支架长约114.7mm，两者不是同一个尺寸。

Worker使用当前`camera/U3_F45_B15.json`名义内外参作几何估算：只降低中心高度、不改变前后/左右位置，保持TCP原有RGB投影行位置，不计遮挡。180mm/45°对应TCP光轴距离173.62mm；140mm/38.76°对应140.74mm；120mm/34.49°对应125.25mm；100mm/29.13°对应110.75mm。当前424×240深度合同Min-Z为105mm。这不是最优构图、真实有效深度或夹爪无遮挡的证明，现有上指遮挡问题不能由该表判定已解决。

状态：仅讨论与CPU几何计算，未选择新高度/角度、未修改rig或asset。修改：-codex worker；降低高度的提议：-owner；数值与解释：-codex worker。

## V28-D029：Teacher保守包络、光学安装延后（PROPOSED，2026-09-10）

Owner提出：Teacher先按当前较大腕机碰撞包络训练，实际相机高度/俯角到蒸馏阶段再调整。Worker核对当前实现：Teacher关闭相机渲染；新增奖励依赖腕部关节运动、塔架接触及默认姿态回位；光学可见率为report-only。因此该分阶段安排在实现上可行，但尚未作为plan变更批准。

待planner判断：哪些光学冻结与G0-C检查可移至蒸馏开始前；Teacher保留哪些碰撞、质量/惯量、默认姿态与动作合同。当前最高版本尚不能直接宣称覆盖所有较低/不同角度安装件，需用最终外壳与支架的几何包含关系判断。蒸馏应使用最终相机重新渲染并确认关键观测，Teacher动作标签可复用；若动力学或动作约定改变，则不能只当作图像变化。较大包络训练失败也不能自动否定更小的最终硬件方案，需检查plan §8.2的结论范围。

G0继续PAUSED_BY_OWNER；trunk/Vpiper异常接触仍是独立的训练前问题。本次没有恢复训练、选择asset、改变相机参数或更新plan执行合同。修改：-codex worker；分阶段提议：-owner；条件性分析：-codex worker。

## 2026-09-11 23:06 HKT — Owner 决定（planner 落笔；依据：-owner）

| ID | 决定 | 状态 |
|---|---|---|
| V28-D030 / plan D-30 | 合同分两段冻结：C_T（碰撞包络含塔架与 trunk 并集支架盒、质量/惯量、冻结姿态、D-17 夹紧、reward bundle、telemetry、G0-C3）训练前冻结；C_S（成像意义上的光学项、base 相机单/双与上仰角、G2-C1/C1′/C2/C4、Student 裁剪、渲染域一致性）蒸馏前冻结；containment 判据（最终盒 ⊂ E_T，SDF ≤ −3 mm；质量/质心/主惯量 ≤ 训练值）与蒸馏前 eval-time 安装件交换检查（plan §8.2） | ACCEPTED |
| V28-D031 / plan D-31 | K driver：保持 `target_stage=4`；预注册具名失败 `K_REACH_WITHOUT_COMPLETE`（连续两个 milestone 双侧 S4+ ≥ 56 且 complete ≤ 4）；触发时第 4 个 seed `A_S284` 用 `target_stage=5` | ACCEPTED |
| V28-D032 / plan D-32 | Wave A 选种用 reachability 门（complete ≥ 60、终止 ≤ 2、塔架接触 ≤ 2、`post_release_body_force_p95 ≤ 5 N`）；Wave B 资格仍用合取门（含 `clean_complete`，hinge ≥ 1.0472 保留） | ACCEPTED |
| V28-D033 / plan D-33 + D-06 | base 相机单中置 vs 双 ±0.155 **后移到蒸馏前**；Teacher 的 trunk 包络取两布局并集（双 ±0.155 支架/外壳盒 + 中置外壳盒，15°），质量取双相机值 | DEFERRED（C_S） |
| V28-D034 / plan D-34 | asset 采用 **MERGED**（`a2_piper_v28_merged_20260909/`，mount 并入 trunk，精确复合惯量，28 native 刚体）；CUT 保留为参考；D-021 板高修正在 MERGED 下不再必要 | ACCEPTED |
| V28-D035 / plan D-35 | 腕机塔：外壳中心离法兰 **140 mm**、θ **38.76°**；reset j5 改 **−0.415 rad**（行走光轴 −14.9°）；R5 期望改为法兰 z 0.424514 ±0.01 m；E_T 用该设计两盒，不用族包络 | ACCEPTED（取代 D-028 PROPOSED 与 D-020 的 180 mm/θ45） |
| G0 | 恢复：R2/R3/R5 在 MERGED + 新塔架 + j5 −0.415 上复跑；两候选物理验收授权（MERGED 为绑定 asset，CUT 只作对照记录）；MERGED 仍有 >1 N 异常接触则 STOP 交 Owner | AUTHORIZED |

D-028 → 由 D035 取代；D-029 → 由 D030 取代。


## D-34/D-35 执行记录（2026-09-11，修改：-codex worker；依据：-owner）

MERGED已绑定并重生成140mm/38.76°腕机；D20对新轴向实际求解得1mm间隙、支架长76.227187mm。支架沿用D20单位长度质量估算，质量0.075×L/0.11470001524266443=0.049843403kg，外壳0.075kg，总0.124843403kg；COM/I按新几何重算。中置base外壳为并集proxy，不另计第三台相机质量。稳定复合惯量对照mass差0、COM 4.60e-19m、I 5.38e-17kg·m²。

R1/R2/R3/R5已runtime通过，R2监测体全部0N；A4静态通过。其余状态由g0_decision.json记录。§4中旧A1/板高修正分支、§8/§9旧无K/G1失败转scratch条文已按Owner本次明确指令同步；G1失败STOP。相机归约已接入SDK内参/相对外参及新增朝向字段，不增加reward。

## 2026-09-12 G0-L触发STOP（执行规则，非阈值变更）

默认姿态匹配的新旧asset均0/64摔倒，vx050斜率通过；stand块vx/vy/yaw三项p50残余速度比分别1.2706/1.1990/1.2375，超过冻结1.15倍门。按Owner明确指令停止，未跑其余姿态/PPO/G1，未commit。极小绝对误差与完整读数见`a2_piper_base_v28_g0_resume_readout_20260912.md`，是否调整零指令判据交Owner；没有自行放宽。修改：-codex worker；停止依据：-owner。

## V28-D036：G0-L 零指令微速度判据（2026-09-12 00:26 HKT；SUPERSEDED by D037）

Owner裁决默认姿态的三项失败是判据仪器缺陷，不能解释为 locomotion 退化，并在查看该数据之后修订判据：G0-L p50 改为`≤max(1.15×baseline,FLOOR_axis)`，另加未放松的`p95≤1.15×baseline`；floor 为vx/vy各0.002 m/s、yaw 0.004 rad/s，pitch/roll无floor。G0-L-swap的p50也应用floor，但p50/p95继续以当前policy为上限，不加入1.15倍。替代方案为保留纯比值判MERGED FAIL，或对默认姿态作一次性豁免，均不采用。

事后披露：旧门下默认stand的vx/vy/yaw p50比为1.2706/1.1990/1.2375，故原`STOP_G0_L_FAILED`保持为历史FAIL，不改写。Owner给定的重算依据是stand p95/p50=100.5/52.0/96.3，非零指令轴median=2.66；baseline<2 mm/s的7项比值0.996–1.271，roll_neg vx baseline=0.173 mm/s、ratio=1.073仅侥幸通过。floor取既有`standing_thresholds=[.1,.1,.2]`的2%，也是健康区最小速度基线34.7 mm/s的1/17。

Main对未改动的默认姿态原始结果完成离线归约：`default_comparison_d36.json`为`PASS`，`legacy_status=FAIL`；旧`default_comparison.json`保持FAIL。7项floor适用项（stand vx/vy/yaw、roll_neg/pos vx/yaw）全PASS；其余58项纯比值p50最大1.1070773435384789（vy_pos/yaw_radps）；p95为65/65通过、最大1.0851115450749549（vx025/yaw_radps）；`vx@0.5`斜率0.9319016337394714≥0.8909371018409729；两侧各0/64 falls。证据：`runtime_logs/v28_camera_aware_rebaseline_20260909/resume_20260911/walk/default_comparison_d36.json`。这是对已有默认数据的离线重判，不是重跑；hold/Stage2尚未运行，按D-36预注册；其或任一后续修订门失败即STOP交Owner。D-36后Owner恢复G0。

修改：-codex worker；依据：-owner。状态：ACCEPTED。重审触发：下一次asset或locomotion更换前，完成X-24的同asset异seed自比校准；第三方可质疑15%标定，本次不追加建议的seed282基线自比。


### V28-D036 执行结果（2026-09-12 00:34 HKT）

记录：-codex worker；停止依据：-owner。默认姿态离线 D36 PASS/legacy FAIL；新 hold PASS；新类 Stage2 FAIL：vx050/pitch p50 比1.208313、vy_pos/roll 1.230491、vy_pos/yaw 1.164372，均超过1.15，三项均未使用floor。所有姿态的新旧两侧均0/64摔倒，p95各65/65通过，vx050斜率均通过。两个新进程均exit0，失败来自验收比较。按D36任一姿态未过规则再次STOP，状态`STOP_G0_L_D36_STAGE2_FAILED`；不重跑、不改阈值，未PPO smoke/完整PPO遥测/G1/commit。逐项证据：`resume_20260911/walk/all_postures_comparison_d36.json`，readout追加新结果并保留原FAIL表。X-24仍OPEN。

## V28-D037：G0-L 按命令轴与耦合轴分层（2026-09-12 01:23 HKT）

Owner裁决同一门进行第二次事后修订：指令轴维持p50≤1.15×baseline；零指令耦合轴用p50≤max(1.15×baseline,CAP)，CAP为vx/vy0.1m/s、yaw0.1rad/s、pitch0.05rad、roll0.04rad；全部轴p95≤1.15×baseline。G0-L-swap继续以当前policy为p50/p95上限，只对耦合轴p50应用同CAP，不加1.15。D36的“比值是噪声”依据更正为错误：旧asset同seed/同指令、单关节扰动的65项对照min/median/max为0.9702771921421439/1.0006042300581228/1.0087546657882325，说明固定seed下该量可复现、对小扰动平滑。Owner原文称扰动关节为`j4`；source/metrics显示`arm_j4`始终0，实际为`arm_j5`−0.5199999809265137→−0.41499999165534973，Main将以`resume_20260911/d37/old_asset_posture_perturbation.json`核验并登记。

三姿态的D37重判只允许离线进行，禁止重跑seed281。先预注册、后运行类Stage2姿态seed282的旧asset与MERGED各一次64env×13 blocks，harness用`source_lock_d36_stop/`字节快照，D37 reducer另存字节快照且不回溯重跑。判定：任一命令轴>1.15 → STOP交Owner，判真实locomotion不兼容并进入塔架质量/A2_Base重训选项，不改CAP；命令轴全过但任一耦合项越CAP → STOP；旧asset seed281/282自比若任一命令轴>1.15 → STOP，说明15%本身未标定。自比按命令/耦合两类报告median、max、#>1.15；p95、零falls与slope仍为合取项。全过后才为G0-L PASS，继续PPO 5-batch、完整telemetry验证，才到首个commit点。

修改：-codex worker；依据：-owner。状态：ACCEPTED，`PENDING_D37_SEED282_CONFIRMATION`；保留readout中的原FAIL与D36段落不改。


### V28-D037 seed282执行结果与证据限制（2026-09-12）

记录：-codex worker；数值路由依据：-owner。两次类Stage2 seed282运行均exit0；新旧asset按D37比较PASS，指令轴max1.062727、全轴p95max1.111611、耦合项均≤CAP，0摔倒、前向斜率通过。旧asset281/282自比：指令轴19项与耦合轴46项的median/max均1.0、>1.15均0；两种asset的全部blocks与各自281结果精确相同，只有seed元数据不同。

只读核实发现冻结harness在reset后调用torch.manual_seed，但后续没有RNG消费者，TorchScript eval policy也无随机算子；命令、姿态、phase/history全确定，没有显式PhysX seed。因此不能把这两次运行称为不同随机实现，X-24仍OPEN（换seed随机校准未实现），不将0散布当作15%统计标定。按Owner明确预注册的数值分支，三姿态离线+282确认及自比阈值均PASS，G0-L数值门成立，继续PPO smoke/完整遥测；这不声称随机分布已校准。证据：`d37/confirmation_decision.json`、`d37/seed_exposure_audit.json`。未改变harness、CAP或预注册阈值。


### G0首个commit验收（2026-09-12，D037后）

记录：-codex worker；依据：-owner（§9.7）。PPO64env×5batch与LEFT/RIGHT各exact64完整checkpoint评估均exit0；每侧22400条raw trace，26个计划字段完成schema/归约验证，两项新reward进入训练日志。自然评估仅Stage0，7个无事件字段为null，不声称晚阶段事件已验证。G0 launch门通过，准备首个本地commit；X24随机校准和X25耦合问题保持OPEN，旧C3轨迹FAIL未改，G2后移项不升级为通过。证据`resume_20260911/telemetry_validation.json`，未push。

## 2026-09-12 17:18 HKT — Owner 批准 planner finalize

修改：-codex planner；依据：-owner 本次原话“ok，同意。按照你的决策修改plan，做好决策修改记录。”。状态：**ACCEPTED**。授权范围为已同意决策的 plan、决策记录和相关待办/memory 更新；本次不执行源码改动、训练、评估、硬件、Teacher/G7、commit/push 或外部写入。

输入依次为原 Cursor planner 对话（`b6b2f107-333e-4356-a18a-5215e5ff83a7`，2026-09-09 至 2026-09-11 的方案推导、Owner 定案和自省）、[审计索引](../pro_reviews/v28/8435858/README.md)中的 Pro 原文与本地更新审计、当前 plan/source 及 G0 记录。当前 `g0_decision.json` 为 `G0_PASSED_FIRST_LOCAL_COMMIT_COMPLETED`，未发现 G1、Wave A/B 的 decision/receipt。以下选择合同在这些训练/资格结果出现前确定；既有 G0 数据已可见，不将其冒充盲样。

### V28-D038 / plan D-38：M1–M5 取舍与主线边界

| 审计项 | 裁决 | 变更及落点 |
|---|---|---|
| M1 | 接受 | plan 顶部与 §0、G0 readout 当前入口、memory 路由更新为 G0 完成与 MERGED/140 mm/38.76°/j5=-0.415。base 最终布局仍在 C_S；原 FAIL/D36/D37 与旧几何结果按历史保留 |
| M2 | 接受，单列标签修复 | plan §8.2 将原三 seed 的 6000 可靠性、历史 reach、候选与 Wave B 对象分列。0/3 为 `REACH_NOT_ESTABLISHED`，即使历史已有候选；历史候选不因此删除。`v28_reduce.py` 当前在此情形返回 UNSTABLE，代码同步仍待执行；选择合同变化另见 D039 |
| M3 | 修改后接受 | plan §8.1/§8.3 保留 G1 PASS/PARTIAL/FAIL、失败 STOP 交 Owner 与固定 reset 比例。warm 失败只表示指定迁移未达门，STOP 是成本复议，不否定 scratch。A284 资格另见 D040 |
| M4 | 接受 | plan §6.4/§8.2/§13 明确无事件 null、投影/min-Z 代理与采样 clearance 的边界。RIGHT 学习失败伴随塔架接触仅支持“本配方和预算下未建立，E_T 干涉是待区分解释”，不证明几何无解；保留旧 C3 与原触发、G2 时点，不新增当前 STOP |
| M5 | 修改后接受 | deferred register、长期 TODO 与相关 memory 修复 closure 回收、旧 rig/阶段、重复编号和已关闭项；不保留常驻兼容 alias，不改历史评审/实验档案 |

主线决定：保留 MERGED、140 mm/38.76°、新 reset、D17、现有 bundle 与 K；它们是已批准的工程选择，不声称已由实机测量唯一确定。不采纳默认无 bundle/K 风险梯、8000-batch 延长、当前 reward 重调或 G1/scratch 并行；不取消既有条件分支，也不把它们变为常规必交付。G1 PARTIAL 原定额外 500 batches 计入 36,500 总上限、占用可选余额；若条件臂叠加超额，沿 §9.8 既有预算裁决处理，不自动缩短单格或追加上限。

待办回收：v28 closure 成功或失败均触发 N01/N02 复核；N01 先决定是否重新立项 pilot、定义扰动/loss，新证据成立后再考虑多 seed，不等待已关闭 v27 的 PROMISING；N02 复核可部署传感、可辨识性与未收敛门域，明确继续/延期/关闭。X24 在下一次 asset/A2_Base 变更立项时复核真实随机暴露的校准需求，运行另行授权；X25 保留原 Stage2/3 位姿不稳触发。X17 合并重复项，朝向项统一为 X19、CAD 路线保留唯一 X18；X07 移到 G2 CAD，X09 以最终 C_S 为准；X04/X08 指向已有关闭记录，不重复操作。

### V28-D039 / plan D-39：资格导向的主候选与备选

**替代的旧规则**：plan §8.2 的“最早双侧 reach、并列最小 seed”，以及 §8.4 的“同一 seed 在选种时点和 6000 各做资格确认”。这不是 M2 标签修复的隐含副作用，而是 Owner 明确批准的选择/替补合同变更。

理由：v28 仍需报告原三 seed 的从零可靠性，同时在有限预算内尽力产出供蒸馏使用的 Teacher。最早 reach 与最终 qualification 目标不一致；利用已经安排的 milestone 质量字段可改变候选选择，不必增加训练或采集矩阵。此选择不保证成功，也不消除筛选带来的偏差，候选资格不能替代三 seed 可靠性结论。

新规则（plan §7、§8.2、§8.4、§10）：

1. 基础候选池仅来自 A_S281–283 的六个既定 milestone（1000 至 6000、步长 1000）双侧 exact64；A_S284 仅按 D040 条件纳入。
2. 双侧过现行 reach 门后，依次按弱侧 `clean_complete` 降序、双侧 clean 总和降序、较晚 milestone、较小训练 seed 排序。不增加 clean 入池阈值或加权评分。
3. 固定最多两个不同 checkpoint，可来自同一 seed；依次为主候选和备选。原三 seed 的既定评估完成后冻结；若 A284 实际启动，则待它完成既定训练/评估后冻结。身份与顺序在任何 DEV/CONF 结果读取前写入既有 `wave_a_endpoint_lock.json`。
4. 主候选先做双侧 exact128 DEV（280101），双侧通过才做 CONF（280201）；CONF 通过即取得 sim 资格，备选 NOT_RUN。主候选 DEV 或 CONF 未确认资格时才验预定备选，程序相同；两者均未确认即结束，不从池内寻找第三名。
5. 无候选则 Wave B NOT_RUN；仅一名则只验该名。最多八条 exact128 lane，现有 quality/hinge/tower 门和评估 seed 不变。实际未评估对象不被此结果否定。

**实现状态**：合同已批准并落盘，当前 reducer 仍是旧单 seed 选择；本次不改代码或宣称新排序已有 runtime 证据。后续 worker 同步 reducer、endpoint lock/manifest 和 DEV→CONF 固定顺序。warm 与 A2_Base 附加臂不自动进入本次资格池。

### V28-D040 / plan D-40：A_S284 的条件资格

补充 D031，保持原触发：任一 A_S281/282/283 cell 在相邻两个 milestone 的双侧均满足 `S4+≥56` 且 `complete≤4`，且既有预留额度可用时，A_S284 以 scratch、seed284、`target_stage=5`、6000 batches 启动；不要求三个 cell 同时触发，不改已运行格。

实际启动后，A_S284 在与原三 seed 相同的六个 milestone 做既定双侧 exact64，并可按 D039 竞争原有两个 Wave B 名额；它完成前不冻结资格池。A284 始终单列为 driver 变体，manifest 披露 seed/driver 谱系，不计入原三 seed 的 6000 分母；其成功不把 0/3 或 1–2/3 改成 3/3。与触发格同时改变 seed 和 driver，不能视作同 seed 单因素因果比较。训练 staged reset 保持 `[0.5,0.1,0.1,0.1,0.1,0.1]`，natural eval 关闭 staged reset。

实现状态：cell/触发合同已有，当前 `select_wave_a` 仍排除 A284；D040 的资格接入待代码同步。本次未启动 A284，也未改 budget、driver 数值、门或配置。

## V28-D041：阶段执行授权与代码同步（2026-09-13 01:47 HKT）

修改：-codex Main；依据：-owner 的 `goal-objective.md` 新阶段执行授权。状态：ACCEPTED / CODE_SYNC_COMPLETED。既有C_T、reward/stage/loader、门、预算和G2边界保持。已实现D038独立endpoint、D039最多两个固定主备、D040实际启动A284、G1一次500→累计1000、条件A_W281、active-cell milestone、预算/attempt记账、DEV→CONF、readout/render/closure与安静持久等待。

A_W281按“附加6000批”执行为独立warm arm：同一旧C_S2、policy_only+actor RMS、seed281、fresh counters，不把G1的剩余5500批称为额外6000。SC1000原始D读数LEFT/RIGHT为SC201=0/0、SC202=0/9、SC203=0/63；既有取消条件等价于原warm500的RIGHT D<59，不新增阈值。G1 full续训保留训练state/counter，但当前loader不保存完整simulator/RNG轨迹，receipt显式披露。

证据：[semantic CPU receipt](runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/semantic_cpu_check.json)与[最终集成CPU receipt](runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/cpu_integration/cpu_integration_receipt.json)。原G0真实trace只用于接口/无事件null检查，诊断分类不作为G1 decision；没有新GPU训练、eval或render结果。后续训练成本与实际结果仅以注册receipt/manifest/reducer为证据。

## V28-D042：评估输出目录接线修复（2026-09-13 01:47 HKT）

修改：-codex Main；依据：-owner 已授权不改变实验合同的路径/接线修复及D16。状态：IMPLEMENTED / STATIC_PASS。实际source在读取checkpoint邻接config后把`experiment_dir`覆盖为checkpoint.parent；G0 LEFT runtime_config与PPO checkpoint根已有`exported/`共同证明原D16 CLI覆盖并未落实到所有输出。旧G0证据和该副作用原样保留，不重跑G0。

`eval_agent_trl.py`现在把顶层experiment_dir置为本次eval_output_dir，checkpoint旁meta仍只读；移除了未被下游使用的checkpoint别名复制。后续trainer输出和export写入eval artifact根，权重加载语义未改。实际新eval路径证据待G1既定eval；不以AST/compose宣称runtime路径通过。

## V28-D043：G1首次尝试的外部显存争用（2026-09-13 04:22 HKT）

记录：-codex Main；依据：-owner 已授权的policy读数前infra修复额度（每格最多两次）。G1 attempt1于04:07:57在物理GPU1准入：当时空闲48536 MiB且无compute进程，见`execution_20260913/gpu_occupancy/0138.json`。随后外部PID380745占用44.04 GiB，环境状态分配244 MiB时仅余168.81 MiB，`staged_task_base.py:506`发生CUDA OOM。证据：`execution_20260913/attempts/g1_train_500/attempt1/runtime.log:528-540`及同目录`process_receipt.json`。逻辑GPU0对应已限制可见的物理GPU1。

分类为`RUNTIME_INFRA_FAILURE`，尚无policy/PPO读数、checkpoint或训练config，实际消耗0 batches；不生成G1 PASS/FAIL科研判定。调度器已取消并确认退出，保留原attempt和全部证据。修复方式为在现有资源准入条件下重新排队到空闲GPU，使用attempt2；资源争用无需源码或实验合同修改，4096env、500批、旧C_S2 policy_only+actor RMS及C_T保持。重排前GPU0–7均有外部compute占用；不处理这些外部进程。修复次数记1/2，后续仅在资源条件满足时启动。

## V28-D044：G1@500失败与Owner成本复议（2026-09-14 08:56 HKT）

修改：-codex Main；依据：-owner 阶段执行授权、plan §8.1/§9.6。状态：ACCEPTED（执行既有STOP规则；后续路线仍待Owner）。

- attempt1因准入后外部进程进入发生pre-policy OOM，消耗0批；D043一次资源重排后，attempt2在GPU4完成500批，使用旧C_S2 policy_only+actor RMS、seed281、4096env。训练进程完成不等于G1科学通过。
- 双侧自然exact64、seed280001，reducer `V28_COMPLETE`：LEFT D62/S4+64/complete64/clean64/塔架>5N集0；RIGHT D58/S4+63/complete63/clean47/塔架集6。RIGHT有16集hinge质量分量失败、1集stage_overtime；body/低高度或超速质量分量为0。G1失败的决定项为RIGHT塔架6>2。
- 双侧D均≥40，既定PARTIAL条件不成立，不延至1000。RIGHT D58<SC1000最佳RIGHT63−4=59，另满足warm附加臂取消条件。门值、配方、几何和loader语义均未改。
- Wave A/B、原三seed6000、候选池排序/冻结、DEV/CONF及预定候选render均NOT_RUN；原三seed结果为未评估，不写成0/3。累计实际训练500，未支用后续额度。warm迁移失败不能否定scratch或证明E_T几何无解。
- 双侧相机标签CAMERA_UNMET，属report-only；RIGHT释放后回位仅10集观察到、53集右删失，不能把0.46/0.54秒分位数外推到全部释放集。针孔投影和采样间隙仍是几何代理。D16新eval输出路径在本次左右评估均成立。

证据：[G1权威decision](runtime_logs/v28_camera_aware_rebaseline_20260909/g1_probe_decision.json)、[停止点事实](runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/g1_owner_gate_record.json)、[实际readout](runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/readouts/milestone_g1_train_500_500.md)。证据等级RUNTIME_OBSERVATION；依既定门得到WARM_FAIL，不是Teacher或硬件结论。重审触发：Owner决定是否在原C_T和既有预算内继续三seed scratch；未经裁决不启动。

## V28-D045：停止点closure与N01/N02回收（2026-09-14 08:56 HKT）

修改：-codex Main；依据：-owner closure要求、D038/X05。状态：ACCEPTED（回收与归档）；新方法实验未授权。

N01=CONTINUE有界pilot立项设计：重设计扰动和失抓事件定义，区分正常释放、未触发、失抓、重抓与恢复后clean；保留sham/nominal和全部注入分母。有效事件暴露及完整endpoint之后再考虑多seed。N02=CONTINUE传感/可辨识性立项设计：明确proprio/action history/夹爪qpos及effort代理的可读性，保留短集/失败集，并按物理质量、摩擦、侧别和交互暴露定义门域。两项实验执行均DEFER，须有独立范围和预算；不等待旧v27 PROMISING、完美Teacher或最终相机。X05本次复核义务关闭，N01/N02方法条目继续开放。

本次closure标记OWNER_DECISION_REQUIRED，候选manifest资格NOT_RUN；它是G1停止点的执行收尾，不声称Wave A/B已完成。Wave A1000与endpoint两个commit节点未到达；按已授权closure节点保存本任务实现、证据和文档，不制造未执行阶段的空commit。实际commit与资源释放由execution目录receipts记录。

证据：[后续立项复核](../novelty/documents/20260914_v28_g1_closure_N01_N02.md)、[机器可读决定](runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/next_stage_review.json)。证据等级INSPECTED；不改变G7、C_S/G2、X24/X25或硬件边界。

## V28-D046：Owner批准G1失败后继续scratch Wave A（2026-09-14 10:54 HKT）

修改：-codex Main；依据：-owner本次明确授权。状态：ACCEPTED。

继续A_S281/A_S282/A_S283，各6000 batches scratch；保留原C_T、门值、staged reset及既有预算。G1的WARM_FAIL不改判，warm附加臂取消，已消耗500批进入总账；原三seed完成后核心累计18500，总上限仍36500。1000/2000/3000/4000/5000/6000双侧exact64自然评估与readout按原计划，固定eval seed280001。条件A284和后续固定主备资格合同仍按D038–D040。

资源边界为GPU4–7。Main分配GPU4/5/6各一条训练，GPU7优先处理ready eval；其他训练卡空闲后可并行eval。条件A284进入既定训练lane队列，以保持milestone评估可推进。GPU仍须符合>=20GiB空闲且无外部compute准入，不处理外部进程。只运行既有训练/评估任务，不用额外训练填满空闲卡。

恢复保留G1停止点state与canonical WaveA/B NOT_RUN的时点副本，再单独记录Owner续行；新任务指向本次source snapshot，已完成G1/eval的source引用不改。G1所用gr00t/rl科学代码、配置、活动asset/A2_Base及camera输入与续行前当前文件经一次字节比较相同；调度和文档更新单列，不重跑G0或追加测试套件。恢复1000/endpoint两个未触发commit节点；失败修复上限、精确评估分母、选种和结论边界不变。

证据：[Owner授权记录](runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/owner_resume_wave_a_20260914.json)、[C_T连续性](runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/wave_a_ct_continuity_20260914.json)。重审触发仍按原Owner门；当前记录是路由授权和STATIC证据，不是Wave A结果。

## V28-D047：Wave A step1000实际结果与继续训练（2026-09-14 18:14 HKT）

修改：-codex Main；依据：-owner D046、plan §8.2/§9.3/§9.7。状态：ACCEPTED（执行预注册继续及commit节点，无新实验合同）。

原三seed的6/6自然exact64 lane全部完成、integrity=0、invalid为空。每个seed双侧D/S4+/complete/clean均0，RIGHT S3+为A_S282=1、A_S283=4，其余0；每条lane64集均stage_overtime，塔架>5N集数/接触步占比0。相机CAMERA_PARTIAL，crossing/release和晚阶段事件尚缺，相关字段保持null。它是1000时点的早期学习读数，不是6000的原三seed可靠性或全轮失败结论。

三条配置已实际物化：seed281/282/283、4096env、checkpoint null、6000、K target4、固定staged reset [.5,.1,.1,.1,.1,.1]、MERGED与原reset。启动时待bootstrap验证的合同现有运行配置证据。A284条件不成立（S4+全0且仅一个milestone）；不改变配方、reset比例、门值或6000终点，继续训练。

一次runtime快照见iteration1104/1134/1118，约22.85/22.2/22.0秒每迭代；六条step1000评估在GPU7串行墙钟约44.9分钟，与GPU4/5/6训练并行。按最慢训练剩余与实际eval成本，下一2000汇总预计约6.5小时；绝对等待截止见milestone记录，真实结果/故障提前返回。账本已结算500、在途预留18000；保存的checkpoint已证明至少3500累计训练批（含G1），不把已结算计数冒充实时总进度。

证据：[step1000 readout](runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/readouts/wave_a_step1000_aggregate.md)、[有界核对记录](runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/milestone_records/step1000.json)。执行本地step1000 commit，实际receipt在execution目录；训练与watcher持续，未push或追加评估。

## V28-D048：Wave A step2000分化与继续训练（2026-09-15 00:48 HKT）

修改：-codex Main；依据：-owner D046、plan §8.2/§8.3/§9.7。状态：ACCEPTED（执行预注册继续，无新实验合同）。

原三seed的6/6自然exact64 lane全部完成、integrity=0、invalid为空。A_S281 LEFT/RIGHT的D=64/59、S4+=64/64、S5+=8/9；A_S282 D=63/63、S4+=0/0；A_S283 D=1/0、S4+=0/0。所有lane的complete/clean均0、stage_overtime均64。塔架>5N集数仅281 RIGHT为1，接触步占比0.00041945，其余0；281松手后身体力p95为340.39/173.84 N，crossing hinge p50为1.0325/1.3976 rad。到达进展尚未形成完成能力，当前无格过reach门；不外推6000终点可靠性或因果结论。

相机281双侧及282 LEFT为CAMERA_UNMET，282 RIGHT与283双侧为PARTIAL。281回位观测0/0集、右删失8/26集，回位分位数仍null；其他seed缺crossing/Stage5/release事件，相应字段保持null。相机是report-only；腕部速度/反转失败本身不证明X25的base位姿耦合问题。既有K trace至2000显示281 scale约0.301、282/283仍1.0，仅作训练过程观测。281仅在2000满足双侧S4+≥56且complete≤4，1000未满足，故不触发相邻两milestone的D31/A284；既有训练配方保持不变。

一次runtime快照下界为iteration2073/2149/2127，281当前约24.23秒每迭代；六条step2000评估在GPU7串行墙钟50.4分钟，与GPU4/5/6训练并行。下一3000汇总估计约7小时15分，固定等待边界为2026-09-15 08:03:31 HKT，真实结果/故障提前返回。账本已结算500、在途预留18000；step2000 checkpoint证明至少6500累计批（含G1）。1000本地commit已完成，本时点没有新commit节点；下一节点仍为endpoint冻结。

证据：[step2000 readout](runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/readouts/wave_a_step2000_aggregate.md)、[分量与等待依据](runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/milestone_records/step2000.json)。训练与watcher持续，无额外评估或源码改动。

## V28-D049：Wave A step3000完成行为与质量分量（2026-09-15 07:41 HKT）

修改：-codex Main；依据：-owner D046、plan §8.2/§8.3/§9.7。状态：ACCEPTED（执行预注册继续，无新实验合同）。

原三seed的6/6自然exact64 lane全部完成、integrity=0、invalid为空。A_S281 LEFT/RIGHT D=64/53、S4+=64/64、S5+=5/64、complete=5/64、clean=1/40；LEFT四次完成hinge<1.0472，RIGHT24次完成body>5N，松手后身体力p95=0/1080.724 N，crossing hinge p50=0.91349/1.6443 rad。A_S282 D=64/64、S4+=64/64、S5+=20/0，A_S283 D=62/17、S4+=64/0，两者complete/clean均0。塔架>5N集数282 RIGHT=10（步占比0.001098309）、283 LEFT=3（0.000538793），其余0；两处超过现行64样本塔架门。281 LEFT终止complete5/overtime59、RIGHT complete64，其余lane均overtime64。完成行为出现但双侧能力与质量尚不足；这不是6000终点可靠性或资格结论。

相机281/282双侧CAMERA_UNMET，283双侧PARTIAL，完整逐stage失败/缺失分量见readout。281回位观测LEFT/RIGHT=0/64，右删失6/0；LEFT回位分位数null，RIGHT分位数有实际观测。282/283回位观测和删失均0，相应事件缺失保持null；不把282 LEFT的Stage5到达20等同有效回位事件。相机仍report-only，不能仅凭腕部失败宣称X25 base位姿失稳。K trace至3000：281/282 scale均0.2、driver两侧1/1；283 scale1.0、driver1/0，仅作过程观测。

D31不触发：281在2000满足数值条件，但3000 complete=5/64不满足每侧≤4；282仅3000首次双侧到S4，283仍非双侧。不存在合格相邻两milestone及A284任务；不改已运行格的driver或配方。

一次runtime快照下界iteration3055/3161/3159，慢侧281约24.02秒每迭代；六条step3000评估在GPU7串行墙钟62.1分钟、process总和2869.0秒，均exit0。下一4000汇总估计约7小时45分，固定等待边界为2026-09-15 15:26:40 HKT；真实结果/故障提前返回。账本已结算500、在途预留18000；step3000 checkpoint证明至少9500累计批（含G1）。1000本地commit已完成，本时点没有新commit节点，下一节点仍为endpoint。

证据：[step3000 readout](runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/readouts/wave_a_step3000_aggregate.md)、[分量与等待依据](runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/milestone_records/step3000.json)。训练与watcher持续，无额外评估或源码改动。

## V28-D050：Wave A step4000实际读数与继续原6000

2026-09-15 14:45 HKT；修改：-codex Main；依据：-owner D046及§9.3既定milestone路由；状态ACCEPTED。

原三seed step4000的6条自然exact64评估完整且integrity=0。281 LEFT/RIGHT complete=64/64、clean=47/38；LEFT完成中17集门角不足，RIGHT26集身体接触。282 complete=36/33、clean=3/2；283 complete/clean=0/0。塔架>5N集数为282 LEFT=13、283 RIGHT=26，其余0；六条相机报告均UNMET，回位null与右删失单列。D31仍无合格相邻对，A284未触发。原6000继续，终点/候选/资格未评估；G1 WARM_FAIL与500保留、warm取消。

281 D=64/28、S4+/S5+/complete均64/64；松手后身体力p95=0/603.266N，crossing hinge p50=1.117632/1.416776rad。282 D=62/64、S4+=64/64、S5+=61/33；完成分量：门角不足17/30、身体接触33/8，分量可能重叠；终止complete36/33、overtime28/31。283 D/S4+=64/64、S5+=0/7、overtime64/64，松手后身体力p95=0/649.729N。不能由本milestone预判6000终点或Teacher资格。

D31：281/282在4000的complete均超过4；283首次在4000满足双侧S4+=64且complete=0，但3000 RIGHT S4+=0，所以没有相邻两次满足的seed，不启动A284。

相机：六lane均有实测失败，按report-only规则记UNMET。回位已观察/右删失：281 LEFT0/64、RIGHT41/20（已观察p50=1.82s、p95=2.42s）；282 LEFT32/0（.73s/1.907s）、RIGHT17/17（1.42s/4.12s）；283 LEFT0/3、RIGHT0/19。未观察分位数保留null；这些条件分位数不能代表所有episode已回位。逐stage失败、事件分母与完整26字段从readout读取。K三seed在4000的scale均0.2；281末次更新缺RIGHT natural sample、skipped=true，282/283末次consumed=true，非因果证据。

三训练日志一次观测的已完成iteration下界4050/4177/4169，近四次均值24.1225/23.0475/23.8425s。六条eval均GPU7、exit0，process总和2856.8s、串行墙钟3892.9s。closed invocation实际500、active reservation18000、scheduled0；4000 checkpoint证明总进度至少12500批含G1，不混作closed counter。下一真实step5000等待截止2026-09-15T22:30:31+08:00，依据最慢seed剩950批、实测评估耗时与调度余量；readout/故障可提前返回。

证据：`runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/milestone_records/step4000.json`及同目录`step4000_state_snapshot.json`；原始reducer/readout与六eval receipts保留。继续5000/6000、条件A284、固定WaveB与render/closure。4000没有新commit节点，本次仅更新实际证据与记录。

## V28-D051：Wave A step5000质量分量与A284条件触发

2026-09-15 21:59 HKT；修改：-codex Main；依据：-owner D046及§8.3/§9既定条件；状态ACCEPTED。

原三seed step5000的6条自然exact64均有效、integrity=0。281 LEFT/RIGHT complete=52/0、clean=51/0，上肢超速终止12/64；282 complete=63/64、clean=12/7，LEFT身体接触51集、RIGHT门角不足57集；283 complete=0/0，RIGHT塔架>5N为16集。六条相机均UNMET，回位null与右删失保留。283在4000/5000连续双侧S4+=64、complete=0，触发D31；A284已按原合同排队，尚未实际启动。原三seed继续6000，候选冻结需等实际启动的A284完成既定证据；G1 WARM_FAIL/500与warm取消保持。

281 D=54/14、S4+=55/44、S5+=54/42；LEFT完成52、超速12，RIGHT超速64、无完成。松手后身体力p95=0/155.073N，crossing hinge p50=1.332701/1.420162rad。282 D=53/64、S4+/S5+/complete=63/64，LEFT overtime1；松手后身体力p95=846.134/0N，crossing hinge p50=1.723882/.921548rad。283 D=64/61、S4+=64/64、S5+/complete=0/0，双侧overtime64，RIGHT塔架步占比.011853448；其余塔架集数0。low_height/overspeed分量按所有评估集计，不能把281的12/64解释为已完成子群。当前没有新增双侧reach合格checkpoint，不预判6000终点或冻结资格排序。

D31证据为A_S283同一seed的相邻4000/5000，两次每侧S4+=64且complete=0，满足≥56/≤4；watcher已创建wave_a_s284，状态PENDING_GPU。保持scratch、seed284、target_stage=5、4096env、6000及原六milestone；不修改原三seed，A284不入其分母、不构成driver因果比较。预算closed实际500、active预留18000、scheduled6000，总承诺24500≤36500；5000 checkpoint证明至少15500累计批含G1。继续既有GPU4–6训练队列，GPU7与后续释放卡推进评估；本时点不把queued记为实际启动或已具入池资格。

相机六lane均UNMET。回位已观察/右删失：281 LEFT0/55、RIGHT0/36；282 LEFT63/0（已观察p50=.42s、p95=.738s）、RIGHT33/31（.86s/1.072s）；283 LEFT0/1、RIGHT0/5。无回位的分位数保持null，282条件分位数不代表所有episode。逐stage失败、事件分母与26字段保留在readout；腕部失败不独自证明X25 base位姿不稳。K在common_step320000均scale≈.2、consumed=true，末次driver281=5/6与2/3、282/283=1/1，仅过程观测。

已完成iteration下界5025/5167/5113，最近四次均值35.5625/33.9625/25.625s；六条eval均GPU7、exit0，process总和2217.1s、串行墙钟4650.6s。下一原三seed6000等待截止2026-09-16T09:14:50+08:00，按这次较慢训练速度、既有eval耗时与调度余量估计11h15；真实readout/异常提前返回。A284触发不改变原三seed6000单独报告要求，候选池冻结仍依D040等待实际启动的A284全套结果。

证据：[step5000 readout](runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/readouts/wave_a_step5000_aggregate.md)、[分量与等待依据](runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/milestone_records/step5000.json)及step5000_state_snapshot.json。5000没有新commit节点；本次仅处理实际milestone与预注册条件，不改实验配方。


## V28-D052：原三seed6000可靠性与A284实际启动

2026-09-16 10:30 HKT；修改：-codex Main；依据：-owner D046与既定D038/D040；状态ACCEPTED。

原三seed各6000已完成；终点6条自然exact64均有效、integrity=0。双侧reach为1/3，仅A282通过，结论REACH_SEED_UNSTABLE。281 LEFT/RIGHT complete=62/63、clean=59/43，RIGHT松手后身体力p95=536.013N；282 complete=62/64、clean=61/12，RIGHT门角不足52集；283 complete=64/4、clean=29/2，RIGHT塔架>5N为24集。六lane相机均UNMET。A284已于09-16 03:52HKT在GPU5按原scratch/target_stage5/6000合同实际启动，待其六个milestone齐全后依D040冻结候选；G1 WARM_FAIL/500与warm取消保持。

D038的原三seed6000分母固定为3：281 LEFT通过、RIGHT因松手后身体力p95>5N失败；282双侧通过；283 LEFT通过、RIGHT因complete4<60及塔架24>2失败。该reach门不含crossing hinge质量门，故282入池资格不消除RIGHT的52集hinge失败，也不等于Teacher通过。现有历史中仅A282@6000满足双侧reach，弱侧clean12、总clean73；这是尚未冻结的观察，主备候选依D040等待实际启动的A284全部六个milestone，不提前运行DEV/CONF。

原三seed进程均exit0、actual_batches各6000。281 D58/2、S4+62/63、open_hold62/51、S5+62/63；超速2/1，塔架1/0，crossing hinge p50=1.198090/1.365353rad。282 D56/64、S4+63/64、S5+62/64；LEFT超速2，身体接触1/0，塔架0/0，hinge p50=1.561679/.954489rad。283 D61/55、S4+64/64、S5+64/4；RIGHT overtime60，hinge p50=1.031354/1.404117rad；LEFT hinge不足34、身体接触1集，RIGHT身体接触2集。low_height/overspeed分量按全部评估集计；身体接触与hinge分量可重叠。除281 RIGHT外，松手后身体力p95均0。

相机六lane均UNMET，逐stage失败和26字段保留readout。回位观察/右删失：281为0/61、0/49且分位数null；282为58/5（已观察p50=.72s、p95=1.029s）和3/61（.76s/.85s）；283为18/46（.92s/.96s）和1/7（.60s/.60s）。这些条件分位数不代表全部episode；腕部失败不独自触发X25。K末次common_step384000均scale≈.2，281 driver1/.5且consumed，282 driver null/1、LEFT零natural样本所以skipped，283 driver1/1且consumed；不构成因果比较。

A284的process receipt证明fresh counters/start_global_step0、checkpoint null、full、seed284、4096env、6000与target_stage5，固定reset [.5,.1,.1,.1,.1,.1]成立；03:52HKT在GPU5启动。单次日志观察iteration933，最近四次均值23.6225s。预算closed实际18500、active预留6000、scheduled0，总承诺24500≤36500；未把A284在训进度记成闭合消耗。其首个milestone等待目标为a284_step1000，截止2026-09-16T11:15:07+08:00；按67个剩余batch约26.4min、单lane评估5.2–8.4min且可并行及调度余量估计45min，真实readout/异常提前返回。

证据：[step6000 readout](runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/readouts/wave_a_step6000_aggregate.md)、[分量、终点判定和等待依据](runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/milestone_records/step6000.json)及step6000_state_snapshot.json。候选endpoint lock尚未触发，不在本节点提前commit；原三seed训练及六lane评估、旧Main等待的10个完成事件在处理后单独ack。


## V28-D053：A284首个milestone与独立等待路径

2026-09-16 11:06 HKT；修改：-codex Main；依据：-owner D046与既定D31/D040；状态ACCEPTED。

A284@1000双侧自然exact64均有效、integrity=0；LEFT/RIGHT D=0/2、S3+=0/3，S4+/S5+/complete/clean均0，双侧stage_overtime64、塔架接触0。相机均CAMERA_PARTIAL，晚阶段与回位无事件的指标保留null。按原合同继续A284至6000；原三seed6000的reach1/3（REACH_SEED_UNSTABLE）保持独立，候选冻结及资格待条件臂完整证据。 首个checkpoint不支持A284终点失败或driver因果结论。

双侧松手后身体力p95、crossing hinge和回位分位数均null；回位观察/右删失均0/0。LEFT未到Stage3，缺少Stage3–5角速度、Stage4/5反转与回位；RIGHT有3集到Stage3，缺少Stage4/5及回位。已测目标没有失败，故CAMERA_PARTIAL，不写MET。26字段和事件分母保留原readout。K末次common_step64000，scale1.0，driver左右0、natural样本4/3、reached0/0、consumed=true。

A284仍在GPU5训练，11:04:42HKT单次日志观察iteration1026，四次均值24.33s。双侧eval分别GPU7/4，exit0，耗时377.4/401.4s，实际并行。预算closed18500、active预留6000、scheduled0、cap36500；已保存A284@1000证明累计至少19500，但不把在训cell写成闭合预算。下一a284_step2000截止2026-09-16T18:06:45+08:00，按剩余974批约6.58h、双侧评估约7min及调度余量给出7h，真实readout/异常提前返回。

`a284_step1000`于11:04:07HKT实际返回MILESTONE_READOUT_READY，与独立readout一致，首个等待目标的runtime路径已验证。仅确认这次实际功能，后续五个目标尚未单独运行。证据：[A284@1000 readout](runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/readouts/milestone_wave_a_s284_1000.md)、[milestone记录](runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/milestone_records/a284_step1000.json)及a284_wait_target_implementation_20260916.json。处理后只ack双侧eval与本次Main等待三个完成事件；没有新增commit节点、测试或实验。

## V28-D054：A284@2000 评估与等待续期

2026-09-16 18:26 HKT；修改：-codex Main；依据：-owner D046与既定D31/D040；状态ACCEPTED。

A284@2000双侧自然exact64均有效、integrity=0；LEFT/RIGHT D、S3+、S4+、open_hold均64，S5+=9/1，complete/clean=0/0，双侧stage_overtime64，塔架接触0/1。相机均CAMERA_UNMET，回位observed=0/0、censored=37/1且分位数null。按原合同继续A284至6000；原三seed终点reach1/3保持独立，候选冻结及资格待A284完整证据。

LEFT/RIGHT post-release身体接触p95=220.326/0N，首次crossing hinge p50=1.067583/0.819901rad。双侧complete为0，clean分量不能据此声称所有episode均无接触或hinge问题。相机LEFT未达S5速度、S4反向、姿态与j6偏离份额；RIGHT未达S2/S5速度及S4反向。回位无观测成功，删失37/1；26字段和原始缺失口径保留。该读数不触发对X25 base pose或真实光学/硬件的归因。

K最后common_step128000，scale1.0，driver0/0，自然样本2/3、reached0/0，consumed=true/skipped=false；只作过程观察。双侧eval均GPU7、exit0，实际顺序运行549.2/514.0s。预算closed18500、active预留6000、scheduled0、cap36500；A284@2000 checkpoint证明累计至少20500，不闭合在训cell预算。

原2000等待于18:06:45HKT到期；一次日志观察18:07:29HKT为iteration2017。首次续期漏传既有--renew-reason，按旧deadline立即返回；补齐调用参数后保留18:38:59HKT截止，18:22:31HKT由实际双侧readout提前返回。没有source/config修改或训练重启，详情见runtime waits/a284_step2000_deadline_extension1_20260916.json。下一3000截止2026-09-17T01:37:29+08:00；18:07:29HKT single actual training observation: iteration2017, remaining983 to3000, last four iteration times24.51/25.10/24.86/24.88s mean24.8375s (~6.78h training). Step2000 bilateral eval actually ran sequentially onGPU7, process549.2/514.0s (~18min) plus scheduling/readout. Set7h30 from observation including margin, conditional on throughput/admission; actual readout/failure returns early. No second progress poll.

证据：[A284@2000 readout](runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/readouts/milestone_wave_a_s284_2000.md)、[milestone记录](runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/milestone_records/a284_step2000.json)。本节点仅处理对应完成事件；无新增commit节点、测试或实验。


## V28-D055：A284@3000 单侧完成与继续既定训练

2026-09-17 01:42 HKT；修改：-codex Main；依据：-owner D046与既定D31/D040；状态ACCEPTED。

A284@3000双侧自然exact64均有效、integrity=0；LEFT/RIGHT D、S3+、S4+、open_hold均64，S5+/complete=0/64，clean=0/32。LEFT stage_overtime64；RIGHT完成64，其中32集因crossing hinge低于1.0472rad不clean。双侧塔架接触0，相机均CAMERA_UNMET；回位observed=0/0、censored=0/64且分位数null。按原合同继续A284至6000；原三seed终点reach1/3保持独立，候选冻结及资格待A284完整证据。

LEFT/RIGHT post-release body force p95=228.260/0N，first crossing hinge p50=1.000044/1.047061rad；hold_through/crossing_while_holding均64。LEFT clean-complete分量全0来自complete0分母，不代表所有episode无接触或hinge问题。RIGHT不clean的32集均为hinge分量，body/low-height-or-overspeed分量0。

相机LEFT失败于S2/S3腕机速度106.545/314.098deg/s与S2 j6反转2.614/s；S5没有样本，保持null。RIGHT失败于S2/S5速度123.466/191.110deg/s、S2反转3.437/s、stage0/5姿态p95=2.120rad及q6偏差frame share=.12979。回位observed0/0、censored0/64，RIGHT删失时长p50/p95=2.030/2.678s；这些不是回位完成时间。完整26字段及分母见readout/record；相机report-only，不独自证明X25 base位姿失稳、真实光学或hardware结论。

K最后common_step192000，scale1.0，driver0/.6，自然样本2/5、reached0/3，consumed=true/skipped=false；全程scale范围[.9998999834,1]，仅过程观察。两条eval均GPU7顺序运行、exit0，耗时509.99/478.73s。预算closed18500、active预留6000、scheduled0、cap36500；A284@3000 checkpoint证明累计至少21500，不闭合在训cell预算。

原3000等待于01:37:29HKT到期；双侧readout实际记录01:38HKT并于01:39:06HKT在本次follow-up观察到，无需续期。单次训练日志观察iteration3048，下一4000截止2026-09-17T09:09:06+08:00。01:39:06HKT single actual training observation: iteration3048, remaining952 to4000; last four iteration times24.57/24.67/24.92/24.73s mean24.7225s (~6.54h training). Step3000 bilateral eval actually ran sequentially onGPU7, process509.99/478.73s (~16.5min), plus scheduling/readout. Recent whole-milestone interval was slower than four-iteration estimate; set7h30 from observation including margin, conditional on throughput/admission. Actual readout/failure returns early; no second progress poll.

证据：[A284@3000 readout](runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/readouts/milestone_wave_a_s284_3000.md)、[milestone记录](runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/milestone_records/a284_step3000.json)。本节点仅处理对应完成事件，无新增commit节点、测试或实验。


## V28-D056：A284@4000 双侧完成与clean质量分量

2026-09-17 08:46 HKT；修改：-codex Main；依据：-owner D046与既定D31/D040；状态ACCEPTED。

A284@4000双侧自然exact64均有效、integrity=0；LEFT/RIGHT D、S3+、S4+、open_hold、S5+及complete均64，clean=13/12。clean失败分量：hinge50/52、身体接触1/0、low-height/overspeed0/0；双侧塔架接触0。相机均CAMERA_UNMET；回位observed=19/17、censored=45/47，已观察回位p50/p95分别1.080/1.746s与.900/1.224s，不能代表全部episode。继续A284既定5000/6000证据后冻结候选；原三seed终点reach1/3保持独立。

双侧hold_through/crossing_while_holding均64，post-release body force p95均0N，first crossing hinge p50 LEFT/RIGHT=.956957/.955887rad。p95为0不否定LEFT另有1集>5N身体接触；完整episode分量保留。episode length p50=796/426，arm_j4限位step share=.0000196974/0。

相机LEFT失败于S2/S5腕速186.187/363.337deg/s、S2/S4 j6反转9.152/2.686/s和stage0/5姿态p95=3.818rad；RIGHT失败于S2/S3/S5腕速105.598/335.628/296.654deg/s、S4反转3.208/s和姿态p95=3.393rad。两侧q6偏差frame share=.001637/.023933均过对应report-only目标。回位观测19/17、右删失45/47；删失时长p50/p95 LEFT2.820/3.012s、RIGHT1.860/2.142s，不是回位完成时间。完整26字段、stage分母与条件分位数见record/readout。上述腕部指标不独自证明X25 base位姿失稳或硬件/真实光学结论。

K最后common_step256000，scale_before=.2941158414、after=.2940864265，driver1/1，自然样本1/2、reached1/2，consumed=true/skipped=false；全程scale范围[.2940864265,1]，只作训练过程观察。此次eval在GPU7/4真实并行、均exit0，耗时511.43/324.75s。预算closed18500、active预留6000、scheduled0、cap36500；A284@4000 checkpoint证明累计至少22500，不闭合在训cell预算。

4000readout实际记录08:42HKT，持久wait08:43HKT提前返回。单次训练观察08:43:55HKT为iteration4031；下一5000截止2026-09-17T16:13:55+08:00。08:43:55HKT single actual training observation: iteration4031, remaining969 to5000; last four times23.98/24.08/24.08/24.14s mean24.07s (~6.48h training). Step4000 eval actually ran in parallel onGPU7/4, process511.43/324.75s (~8.5min parallel, ~14min if serialized). Whole-milestone throughput has been slower than a four-iteration estimate; set7h30 from observation for evaluation, scheduling/readout and throughput margin, conditional on admission. Actual readout/failure returns early; no further progress poll.

证据：[A284@4000 readout](runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/readouts/milestone_wave_a_s284_4000.md)、[milestone记录](runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/milestone_records/a284_step4000.json)。本节点仅处理对应完成事件，无新增commit节点、测试或实验。

## V28-D057：A284@5000 完成、clean与回位删失

2026-09-17 15:54 HKT；修改：-codex Main；依据：-owner D046与既定D31/D040；状态ACCEPTED。

A284@5000双侧自然exact64有效、integrity=0；LEFT/RIGHT D=63/62，S3+、S4+、open_hold、S5+及complete=64/63，clean=26/12。clean失败分量hinge38/51、身体接触0/0、low-height/overspeed0/1；RIGHT有1集upper_dof_overspeed终止，双侧塔架接触0。相机均CAMERA_UNMET；回位仅LEFT观察1集、RIGHT0集，右删失63/63，LEFT观测p50/p95=.5/.5s、RIGHT为null，不能代表全部episode。继续既定6000证据后冻结候选，原三seed终点reach1/3保持独立。

LEFT/RIGHT hold_through与crossing_while_holding=64/63；post-release body force p95均0N，first crossing hinge p50=1.029170/.978494rad，episode length p50=454/382，arm_j4限位step share均0。

相机LEFT失败于S2/S5腕速196.069/316.751deg/s、S2/S4 j6反转18.854/3.576/s、stage0/5姿态p95=4.318rad，以及q6偏差frame share=.538855（上限.05）。RIGHT失败于S2/S3/S4/S5腕速246.006/258.060/170.723/344.691deg/s、S2/S4反转22.739/5.088/s和姿态p95=2.545rad；RIGHT q6偏差share=.022177过对应目标。回位LEFT仅1集观测，其.5/.5s分位数不能代表总体；RIGHT0集观测、分位数null。两侧各63集右删失，删失时长p50/p95 LEFT2.680/3.072s、RIGHT1.540/1.760s，不是完成时间；RIGHT超速终止的一集不构成额外release样本。完整26字段及stage分母见record/readout；不外推X25 base位姿不稳、硬件或真实光学结论。

K最后common_step320000，scale_before/after=.20000000298，driver1/1，自然样本4/6、reached4/6，consumed=true/skipped=false；319941次updates、scale范围[.20000000298,1]，只作过程观察。此次eval在GPU7/4实际并行、均exit0，耗时349.76/326.65s。预算closed18500、active预留6000、scheduled0、cap36500；5000checkpoint证明累计至少23500，不闭合在训cell预算。

5000readout记录15:49HKT，持久wait15:50:11HKT提前返回。单次训练观察15:51:41HKT为iteration5023；下一6000截止2026-09-17T23:21:41+08:00。15:51:41HKT single training observation: iteration5023, remaining977 to6000; last four times24.36/23.77/23.61/23.79s mean23.8825s (~6.48h training). Step5000 eval actually ran in parallel onGPU7/4, process349.76/326.65s (~5.83min parallel, ~11.27min serialized). Actual4000-to5000 checkpoint/eval launch interval was7h11min, slower than four-iteration extrapolation. Set7h30 from observation for training, final process exit, bilateral eval, scheduling/readout and endpoint lock margin, conditional on admission; readiness/failure returns early with no further progress poll.

证据：[A284@5000 readout](runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/readouts/milestone_wave_a_s284_5000.md)、[milestone记录](runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/milestone_records/a284_step5000.json)。本节点仅处理对应完成事件，无新增commit节点、测试或实验。


## V28-D058：Owner提前终止训练并进入固定Wave B

2026-09-17 16:58 HKT；修改：-codex Main；依据：-owner“先终止训练，直接进入Wave B。v28阶段我准备收尾了，因为有了更急切的改动需求，可能得进入v29了”。

Owner因更急切的后续改动要求提前停止训练并直接进入Wave B（D058）。A284最后完整日志迭代5167、最新保存checkpoint5000，6000训练终点与双侧评估取消；按原D039排序冻结主候选A_S282@6000（weak clean12、总73）和备选A_S284@5000（12、总38），身份在DEV启动前落锁。原三seed终点reach1/3（REACH_SEED_UNSTABLE）保持；资格门、C_T和固定DEV→CONF程序不变。

停止使用既有supervisor取消watcher_a3、A284训练及a284_step6000等待；训练wrapper退出后其Isaac子进程仍存活，Main对已确认属于本任务的PGID2808390发送SIGKILL，并确认PID2808391消失。保留原process_receipt的中断状态与supervisor CANCELLED，补充实际终止记录，不把SIGTERM退出或缺失6000 checkpoint当作policy失败。原三seed已自然完成6000；训练累计已记录23667 batches（G1 500+原三seed18000+A284已打印5167），中断中的额外计算量未知，6000预留已释放。

原reducer给出的完整历史条件仍为false、缺失项仅A284@6000。Owner本次授权覆盖等待条件；endpoint lock披露该例外和原始选择结果，候选顺序保持weak clean→clean总和→较晚milestone→较小seed，未因DEV结果重排。A284@4000为已入池但未进入固定前二的第三项，不追加资格搜索。主候选双侧DEV seed280101、exact128已于16:56HKT在GPU7/4启动；双侧通过才做seed280201 CONF，主候选未确认才验固定备选，最多八条lane。预定render和N01/N02增量复核仍须在实际closure交付；v29仅作为后续方向，未启动其实现或方法实验。

证据：[Owner裁决与终止记录](runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/owner_stop_training_wave_b_20260917.json)、[endpoint lock](runtime_logs/v28_camera_aware_rebaseline_20260909/wave_a_endpoint_lock.json)、[Wave B启动记录](runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/wave_b_launch_receipt_20260917.json)。
