# v28 决策日志：G0 与 planner finalize

更新：2026-09-12 17:18 HKT；本次修改：-codex planner；依据：-owner 已同意规划裁决并要求修改 plan、做好记录。历史执行记录保留各自时点与作者。

当前 G0 launch 准入与首个本地 commit 已完成，未 push；本次核对尚无 G1/Wave A/B 结果。D038–D040 已获批准并完成方案落盘，reducer/调度实现待同步；本次没有代码修改、训练、评估或 Git 操作。运行事实仍从 [g0_decision.json](runtime_logs/v28_camera_aware_rebaseline_20260909/g0_decision.json)读取。

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
