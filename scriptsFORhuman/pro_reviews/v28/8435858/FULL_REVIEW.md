# DoorDog v28 独立 Pro 审计

**审计基准：** `84358588e2da12a9fae5748cd9da39ac2d9f5a6c`  
**分支：** `codex/v28-pro-audit-g0-complete-20260912`  
**G0 worker 直接父节点：** `8811c484729b1e9be017c30dcf46d922d1ad5f52`  
**性质：** 独立方案与证据审计；所有修订均为建议，未获执行授权。本文不是生产停止门，也不是训练启动许可。

## 结论先行

**保留有界 re-baseline 主线；认可 G0 的狭义工程准入；收缩可选分支，不自动扩充实验。** 新版证据已经取代“G0仍停在旧FAIL、PPO/eval未接通”的现状判断。当前应讨论的是 G1、三 seed 重建与候选资格的科学/预算边界，不是把未提供的大 trace、X24 或后移 G2 重新包装成云端新增 STOP。

最值得 Owner 注意的不是再多一道测试，而是三个目标错位：**warm 迁移成败不等于 scratch 可行性；最早 reach 的固定候选不等于最有希望获得资格的候选；包含更小硬件的包络模型不等于已经证明真实安装可用。** 这些错位主要靠收窄结论和明确既有选择规则来处理，而非再建一套庞大基础设施。

本轮可以得到新的、部署相关的工程基线和行为轨迹；不能单凭它证明 bundle 的因果收益、Student收益或方法 novelty。将 N01/N02 后移是可辩护的取舍，但必须在 v28 closure 时主动回收立项问题，不能让“先完善baseline”变成无终点的前置链。

### 审计顺序与可复核记录

第一包先读取，初判固定后才获取、解压和阅读第二包。下面保存初判原文，后续增补另列，不回写初判。

- Phase A 固定：`2026-09-12T01:21:42.422581+00:00`。
- 初判 UTF-8 长度：16,622 bytes；SHA256：`9a6003c139eed6e06fc6eeb10538fa0a0922bd4555d09460714d350fdb6a8eac`。
- Phase B 第一次打开第二包：`2026-09-12T01:21:59.569768+00:00`。
- 第一包 SHA256：`1cd9fbfca453723ecbaa6c7537b77e4b0430e1eda7042f653b07a121b21e7d65`。
- 第二包 SHA256：`91641576fbfaa12c96931a654e775fd469fd858c6b8ee57adf3612e555019c57`。
- 第二包 planner 自省副本的 Git blob SHA 为 `2df936ea7f7f6c10a5e05bd99f1c0ff0a66fa938`，与审计 commit 中该文件相同。它仍是 2026-09-11、D01–D35 时点的文本；不能因文件位于新 commit 就把其全部状态描述当作当前事实。

这些是本次读取顺序与文件内容的审计记录，不是对远端记录生成过程的独立密码学认证。旧 Drive 目录没有打开；旧审计只按本次 v2 的撤回表作历史辨识，没有冒称复审旧报告全文。

### 阅读指引

A 为固定初判；B 为三方逐项比较与增补；C 为最终保留/收缩/后移与最小待审批文本；D 为数值、时间线和证据边界。`P01–P12` 指 A 中初判编号；`E01–E18` 是文末证据索引，均落到当前 Git 或第一包原始路径。

---

<!-- BEGIN_FROZEN_PHASE_A -->
# 独立初判 A — 在读取第二包之前固定

## 身份、范围与证据口径

审计对象：`Jam-Stark/DoorDog`，`codex/v28-pro-audit-g0-complete-20260912`，commit `84358588e2da12a9fae5748cd9da39ac2d9f5a6c`；G0 worker 直接父节点 `8811c484729b1e9be017c30dcf46d922d1ad5f52`。只使用新版 Drive 目录与第一包。尚未获取、打开 `worker_delivery__prior_audits.zip`，未阅读 planner_self_review 或 LOCAL_TEAM_AUDIT 正文。主文档中自省指针及少量署名提案不能完全避免，但本初判不以其观点为证据。

本稿是可公开的审计结论记录，不是内部思维过程。事实指读取的源码、配置、数值文件和运行档案；推断另行标明。没有运行 IsaacLab、MuJoCo、GPU、TorchScript policy 或硬件，没有修改仓库、实验合同、Teacher/G7。档案中的 RUNTIME_PASS 是原本机记录，不是 Pro 重跑认证。

路径缩写：
- `P` = `scriptsFORhuman/v28/a2_piper_base_v28_plan_20260909.md`。
- `R` = `scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/`。
- `D` = `R/resume_20260911/`。
- `V` = `scriptsFORhuman/v28/`。
所有 Git 源码引用固定到上述审计 commit；第一包路径保持仓库相对路径。

已完成的独立核对：第一包 manifest 的 228 个原始文件全部存在且长度相符；对三姿态共 195 个比较项，从 old/new `metrics.json` 重算 p50 比、p95 比及 D36/D37 门值，与保存的比较文件相符。命令轴分类与命令脚本及 slope 的 null/non-null 对照；第 13 块依赖的原始 58-step v27 replay trace 不在包内，不能声称独立重建了该块每一步命令。两种资产的 seed281/282 全部 metrics 在去掉 seed 字段后逐项相同。两侧各 64 条 episode records 与 26-field exports 已独立读取。

## P01 总体判断与最小有效交付

**判断：支持 v28 作为有界工程 re-baseline；接受当前 G0_LAUNCH_GATES_PASSED 的狭义记录，不认可任何 Teacher 质量、随机校准或硬件资格的外推。** 本轮要解决的是新装配模型、默认姿态、累积动作目标及相机相关行为约束组合后，是否仍能建立可用双侧 Teacher。它不直接回答恢复图/history latent 等方法问题。

最小有效交付不是再加一个大实验矩阵，而是：冻结一个真实被执行的 C_T；在固定配方下报告三 seed 的 reachability 稳定性，同时独立报告 clean/safety/camera 指标；存在合格候选时按已有 exact128 DEV/CONF 规则确认，否则保留有解释的失败 closure；给 Student/sim2sim 与下一轮科学路线留下可执行的依赖。无需保证本轮一定得到新 Teacher，失败但不改门、不挑替代、可定位的 closure 也有价值。候选 manifest 不等于 binding。

事实依据：P §0、§7–§9；`base_v28_common.yaml`；`v28_contract.py::cells`；`v28_reduce.py::{reachability_gate,passes_gate,select_wave_a}`；v27 execution closure。最强反方：若 Owner 当前唯一目标是尽快研究 novelty，18,000 scratch batches 的机会成本很高。回应：新碰撞包络和动作语义改变后直接移植旧结论也不可靠；必须给 re-baseline 明确闭环出口，不能让它无限吞掉方法研究。

## P02 必要复杂度与可收缩复杂度

保留：MERGED/140 mm/38.76°/j5=-0.415 的单一 C_T；D17 累积臂目标限位；塔架独立接触语义；已跑通的最小 G0 接线；三 scratch seed 与已有阶段报告；reachability 与 qualification 分层。它们分别解决资产与物理一致性、积分目标越界、相机结构碰撞遗漏、多 seed 可重复性等不同问题。

后移：base 单/双最终布局、精确光学/CAD、Student 渲染/裁剪/传感合同、mount swap 到原定 C_S；N01/N02 到下一阶段立项；bundle 因果收益到 N07b。不是把这些问题宣称解决。

条件分支：A_S284 仅响应预注册的 K_REACH_WITHOUT_COMPLETE；warm 长训练臂和 A2_Base opt-in 不应当作常规流水线。P §10 的核心为 G1 500 + 3×6000 = 18,500；三个可选 6000 臂全部触发达到 36,500，接近翻倍，尚有 G1 PARTIAL 延至1000与总额表之间的边界需要在触发时说明。**复杂性风险主要是分支叠加和交付承诺不收口，而不是门槛/文件数本身。**

最强反方：这些分支已有条件，不必删。接受：建议收缩默认承诺，并非擅自取消已经批准的条件路由；本次没有授权修改它们。

## P03 Novelty、baseline 与行为改进的交换

事实：训练配置关闭相机渲染；reward 新增 wrist motion、tower contact，并将 Stage4 default-pose 惩罚 release-gate。D17 也改变动作语义。K 的 v27 依据为 SK 1/3、SC 0/3 的注册 typed outcome，而非三 seed 稳定优胜。

获得：部署相关几何和动作可执行性更贴近目标，避免在无塔架/目标越界的旧底座上追求漂亮成功率；为后续新轨迹与蒸馏提供可冻结输入。牺牲：无法将最终增益归因于 asset、reset、clamp、reward 或 K；没有无 bundle 配对和 Student 配对，本轮不能证明 observability-aware shaping 提高蒸馏成功率；可靠闭合行为、真实视觉可用性均尚未得到结果。

最强反方：工程集成也可能成为方法贡献的一部分。接受其未来可能性，但本轮识别设计没有提供相应因果或泛化证据，不应靠名称升格。

依据：P D08/D17、§6、§8.3；`gr00t/rl/config/ablation/wbmanip/base_v28_common.yaml`；`gr00t/rl/envs/base_task/delta_action_base.py::step`；G0 commit 中 `door_open_a2_base.py` 的 reward/telemetry diff；`scriptsFORhuman/v27/a2_piper_base_v27_execution_closure_20260911.md`。

## P04 G0 commit 实际新增的证据

新增了资产/body/config 与实际进程可工作的证据，而非只补文档：28 bodies/20 joints、复合惯量数值等价与 readback、A4 默认位姿非过滤碰撞对计算、R2/R3/R5 原生运行记录；三姿态 D37 数值比较；64env×5batch PPO 真实 iteration 1–5 和两项新 reward 日志；full-checkpoint LEFT/RIGHT natural exact64 的 episode records 与 camera metrics。

独立可核：PPO日志 wrist motion 五值为 -0.0015/-0.0024/-0.0050/-0.0071/-0.0413；tower 五次0。两侧64个唯一 env_id，全部 max_stage=0、goal_reached=false；每侧26字段、7null。读取的来源含 `D/ppo_smoke_d37_r1/{runtime.log,process_receipt.json,config.yaml}`、`D/telemetry_eval_d37/{left,right}/{a2_v14_per_env_records.json,camera_metrics.json,process_receipt.json,.hydra/runtime_config.yaml}`。

没有证明：新 policy 可以抓把手/开门/释放/越门；tower 非零接触事件的正确触发；Stage2–5数值统计或控制效果；Student视觉学习；实机安全。5-batch不能被解释为学习收敛实验。

最强反方：只到Stage0是否等于G0失败？否，当前验收的对象就是接线与无事件null语义；不能把尚未观测事件偷偷记为PASS，但也不应追加强制晚阶段实验以重启旧STOP。

## P05 原FAIL → D36 → D37 的时间线、权限与结论边界

按 UTC（HKT=UTC+8）串联当前决策文本及进程记录：
- 原默认位姿结果先产生，随后保留 STOP_G0_L_FAILED；stand vx/vy/yaw p50比分别1.270609/1.199041/1.237510。新旧都0falls，forward slope过门。
- D36 Owner记录为9月12日00:26 HKT，即9月11日16:26 UTC。默认数据是事后重判，后续hold/类Stage2运行在其后。D36新增floor和p95约束；default/hold过，类Stage2三项失败：1.208313、1.230491、1.164372，再次停止。
- D37 Owner记录为9月12日01:23 HKT，即17:23 UTC，是已看到三姿态后的第二次事后修订。三姿态仅离线重判；D37 preregistration在17:28:17.231524，seed282两个进程17:28:48.773597/832320才启动，17:30:33/39退出。
- PPO在17:36:01–17:38:00；左右评估17:38:56启动、17:43:27/30退出；telemetry validation17:47:37，acceptance17:49:55，worker commit17:52:55，审计上下文commit18:06:30。

三姿态195项重算均匹配：57项命令轴全部≤1.15，最大1.123854；11项原p50比值失败均属耦合轴；所有p95通过，最大1.111611；所有耦合项也未越绝对CAP。D37不是原门通过；授权合理性与统计有效性是两件事。档案显示有Owner决定、执行顺序与保留原FAIL，但不是独立查验了Owner原会话真实性。

最强反方：二次事后改门有迁就结果之嫌。这个质疑成立为解释风险；但没有证据证明 worker 未经授权篡改实验，也不该因此否认数值准入在新合同下成立。结论必须带“Owner修订后的数值门”限定。

依据：`V/a2_piper_base_v28_decision_log.md` D036/D037；`D/walk/*comparison*.json`及对应old/new metrics；`D/d37/{preregistration,confirmation_decision}.json`与process receipts。

## P06 Seed282、X24 与 X25

独立对比发现：old asset与MERGED各自281/282的完整metrics字典，除seed元数据外完全一致。当前 `gr00t/rl/scripts/smoke_a2_base_flat_walk.py` 在 reset 后调用 manual_seed；worker `D/d37/seed_exposure_audit.json`称后续无随机消费者、policy无随机算子。后者涉及未提供的TorchScript和冻结完整树，不能冒充Pro重新检查其二进制图。

因此新增的是两次新进程的确定性数值复现，不是新随机暴露；不能用64环境或两个seed标签扩大独立样本量，不能据零散布校准15%。X24/N09保持OPEN正确。最强反方：确定性回归不需要随机性。赞同，它对回归可用，只是不回答随机稳健性。

X25/N10有原始支持：类Stage2下vx050/pitch误差0.00593686→0.00717358 rad，vy_pos/roll 0.00726377→0.00893800 rad，vy_pos/yaw 0.03734438→0.04348277 rad/s。增幅约16–23%不等于已经导致抓握失败，也不能仅凭在CAP内就断言对近距操作无害。保留原有Wave A Stage2/3位姿不稳触发；不要本轮另增locomotion矩阵。

补充：通用比较函数的coupled门是max(relative,CAP)，而282 confirmation wrapper另行检查硬CAP；已读`D/d37/reduce_confirmation.py`确认存在该检查，本批全部CAP内，**不把这一分层实现误报成当前漏门**。以后复用比较脚本时不要遗漏wrapper合同。

## P07 接线不等于事件覆盖，投影不等于真实可见

两侧7个null分别为 crossing yaw p50/p95、Stage5 doorway bearing p95、Stage2–4 wrist depth/RGB share、post-release return time p50/p95。每侧22,400 trace rows来自已保存的归约/validation记录；完整493–495MB step trace未提供，不能宣称Pro逐行验完。已有episode终态独立支持“只有Stage0”。

`v28_camera_metrics.py::project/reduce`以单个handle target投影及depth min-z判断in-frame；输出明确写着without occlusion or stereo reconstruction。tower clearance为10mm表面采样对近似panel box的上界，不是精确最小间隙。故连未来非null的这些字段也只是名义几何/运动代理，不能直接授予无遮挡、有效depth或抓握状态可观测性资格。

最小建议：在已有milestone读数中并列population和代理定义；晚阶段事件随既有自然评估出现时再验其语义，不增加独立测试矩阵或把当前缺样本升为新STOP。最强反方：用代理做低成本report足够。赞同，问题在解释而不是要求立即替换实现。

## P08 旧C3、保守包络与硬件归因

`D/g0_c3.json`为当前140mm nominal rig回放旧C_S2/C_S21四条lane；Stage2/3密集、Stage4/5稀疏，5mm表面采样；3个lane/stage违反20mm规则，panel min约-20mm、frame min约-2.64mm。它不是当前v28策略轨迹。A4默认位姿PASS与旧动态C3 FAIL可以同时成立。

推断：加入塔架碰撞模型是必要约束；需要新策略行为，不是可以沿用旧通过率。但P §8.2用“RIGHT失败伴随tower contact高或Stage2→3停滞”直接写E_T与抓握“不兼容”，归因仍过强：优化不良、奖励冲突、locomotion耦合也可能产生同样现象。即使将指控限于E_T，也不等于证明不存在可行抓握轨迹。

最小修订建议：此时写“在本配方/预算下未建立，E_T几何干涉为待区分解释”，保留原硬件决策请求，不默认追加实验。最终小包络包含/质量更低也不自动保证策略性能单调改善；现有C_S mount swap仍有必要，但后移不前拉。

## P09 G1 的角色应与scratch可行性分开

G1当前明确必做且失败STOP交Owner，不得自行删除。其实际输入是旧C_S2、policy_only+旧actor RMS，并承受新动作零点/观测零点、D17和几何变化。失败最多证明该warm迁移在该预算未达门，不能据此证明scratch无可行解；v27本身唯一通过exact64质量门的SK_S213还来自scratch。

最强反方：G1是低成本风险探针和Owner预算复议点，不是证明scratch不可能。若按此理解，保留它合理。建议把科学解释和行政STOP分开；需Owner裁决的只是是否将失败STOP维持为复议点、是否真的值得接一个额外6000 warm臂，而不是再改G0数值门。

## P10 一个静态路由边界需要最小澄清

`v28_reduce.py::select_wave_a`先收集全部历史过reach门的候选；只有整个history一个候选都没有才返回REACH_NOT_ESTABLISHED；否则只判断endpoint是否3/3，非3/3一律REACH_SEED_UNSTABLE。

静态反例：A_S281在1000双侧过门、6000三seed全不过；代码仍返回REACH_SEED_UNSTABLE并保留1000候选，而P §8.2第333行把endpoint0/3定义为REACH_NOT_ESTABLISHED。历史候选可能依旧应保留，问题是把“终点可靠性”与“历史有无候选”揉成一个标签。需要拆清两个事实，不能擅自删除早期候选或扩大WaveB资格。

同样，A_S284已有生成/训练合同但不在选种循环，当前memory TODO也明确其选种资格未定。保持默认不扩选种；真的触发之前请Owner决定，而非等看完结果再纳入。

这是已读源码的静态边界，不是已发生运行事故。G1尚未启动，后续本机HEAD和实际dispatcher须LOCAL_CHECK_NEEDED；不据此废除G0或新增生产STOP。当前Git目录未见计划列出的v28_orchestrate.py；不能由此推断本地不存在调度实现，也不建议现在建设完整workflow。

## P11 遗留事项可回收，但入口存在条件断裂

可回收证据：长期TODO D节明确N01/N02、N07a/b、N08、N09/N10、DIST01/02；v28 register给lane/条件；当前v28 memory TODO把G1、X24/X25、晚阶段事件、G2和A284资格列出。不能说这些已丢失。

需最小修订：N01主条目仍要求已关闭的v27 pilot取得RECOVERY_PILOT_PROMISING，实际QR为UNRESOLVED；另有“v29重设计loss/扰动”补充条目，含义应统一为先重新立项pilot而非静候不会到来的旧终态。N02也应在v28 closure（成功或失败）时由planner主动复核可部署传感合同、可辨识性与适用门域，不把日历v29当自动训练授权，也不让完美Teacher成为无限前置条件。X24原入场条件仍写本次282确认，与“还需真实随机暴露”不一致，应改为下次asset/A2_Base更换前或Owner另行批准校准时。

登记中X17重复、X18被朝向项与CAD干涉项复用；X07仍指G0期旧θ45、X09旧rig名；长期TODO入口和novelty description仍残留旧几何/PROPOSED状态。当前memory首页已正确更新，不建议全面翻新历史；只修活跃行和canonical指针、保留旧编号alias以防破坏引用。

最强反方：细读最新plan即可绕过这些陈旧文本。是，但下一轮planner从TODO自动回收时恰好依赖这些入口，小改收益高于新增一套流程。

## P12 初判后的最小行动建议及证据边界

保留现有G0狭义准入与已有门，不重跑281，不补“看上去随机”的282，不改Teacher/G7。不把C_S、X24、未出现的晚阶段事件强行拉回G0。优先对齐当前状态入口、endpoint/候选两类路由、A284资格、N01/X24重启条件；G1角色/可选长臂取舍交Owner，不能默认执行云端建议。

LOCAL_CHECK_NEEDED：当前本机HEAD/dirty diff；缺失的完整source-copy树与checkpoint真实性/加载；原始大型step trace与非零晚阶段事件；第13块原v27命令回放；IsaacLab/GPU/硬件与实际测量的质量、CAD、标定、传感能力。已存在档案的静态/数值检查与这些未知分列，不因无法本机复现而停止审计。

截至本初判，对总体方向的判断为“保留主线，收缩分支承诺，限制证据外推”，不是生产执行许可。
<!-- END_FROZEN_PHASE_A -->

---

# B. 三方交叉检查

## B1. 材料时点与裁定原则

**Planner自省**：`prior_audits/a2_piper_base_v28_planner_self_review_20260911.md`，2026-09-11，评价 D01–D35 的方案。含风险梯、延长训练、调整G1角色等未授权建议。其“无需重新推导、可直接引用”并不构成证据豁免。

**本地团队v2**：`prior_audits/LOCAL_TEAM_AUDIT.md`，2026-09-12，执行基准为 G0 worker commit，已明确撤回当前旧STOP、PPO链未通和memory入口仍暂停的旧例子；保留统计、质量及待办问题。它不是旧STOP报告。

**Pro独立A**：基于第一包和当前源代码先固定。交叉检查只引入可定位的新证据或指出遗漏，不按多数票决定；同意某方时仍给出源码/数据理由。

## B2. 三方逐项表

| 议题 | Planner自省 | 本地团队v2 | Pro独立A | 最终裁定与证据 |
|---|---|---|---|---|
| 当前G0状态 | 文本时点为恢复执行、D35；保留早期R2等历史描述 | 更新为G0_LAUNCH_GATES_PASSED，撤回当前阻塞 | P04/P05已从原始记录确认狭义通过 | **时点差异，不是争论投票。** 旧“目前STOP/没有PPO-eval”失效。没有理由据旧包阻断当前状态；E01/E03/E04/E07。 |
| 原FAIL与D36/D37 | 早于这两次修订，不能据其沉默推定认可/否定 | 两次Owner授权事后修订；保留原FAIL | P05独立核对时序与195项门值 | **一致。** 现有PASS是新工程合同的数值PASS，不是原门通过；预注册282运行不把已观测的281变成盲样；E04/E05。 |
| seed282与X24 | 无该轮后续证据 | 确定性复现，X24/N09仍OPEN | P06逐项字典比较，除seed外相同 | **一致且可复算。** 新进程≠新随机实现；不新增当前训练STOP，也不关闭校准；E05/E06。 |
| X25因果边界 | 自省早于D37，不覆盖此新增项 | 已有条件触发；不得预判未来失败原因 | P06区分耦合增幅、绝对量和任务因果 | **一致。** 保持Wave A Stage2/3条件触发，不立即叠加shaping或A2_Base训练；E04/E13。 |
| 接线与晚阶段事件 | S3/S9强调估计/几何边界，但未见当前接线完成 | 关闭接线未验证，保留真实晚阶段未覆盖 | P04/P07核对64+64 episode与26/7null | **进展替代旧判断。** tower日志为0不验证非零接触响应；Stage0 smoke不能正面或负面证明完整开门策略；E07/E08。 |
| “1–4皆不可选硬件事实” | §2.1将MERGED、并集盒和reset归为不可选硬件事实 | 接受选定工程基线，未赋予实机证明 | P01/P02/P08将其视为被批准的单一C_T | **部分不同意planner措辞。** 相机存在是需求，但MERGED/并集proxy/reset是建模与控制选择；塔架质量为估算。当前对齐的是明确仿真合同，不是已测量的最终实机；E02/E09/E10。 |
| S1风险梯 | 加新底座、无bundle/K的2000–3000-batch格，甚至pull也加 | 不为形式完整扩矩阵 | P02/P03反对默认叠加条件臂 | **不采纳默认加梯。** 改多个机制、换训练时长、只测D/S4，并不能充分区分最终配方失败机理；去掉已有最有利K先例还可能制造低信息负结果。存在潜在诊断价值，但无证据足以支持现在自动增预算。 |
| S2延至8000 | 按末两个milestone质量上涨条件延长 | 核心18.5k，36.5k为条件上限 | P02接受有限预算下可能失败 | **不默认延长。** 单次SK晚跃升不足以证明8000更划算；预注册延长可以合法，但那是Owner另选预算/问题，不是G0后必须补齐的缺陷；E10/E11。 |
| S3 36个权重数 | 单cell旧trace，建议标三档并在G0重校准 | 作为固定bundle，收益未证明 | P03/P07区分设计先验与经验校准 | **同意披露，不重调。** 当前G0已完成，R5是姿态高度检查，5batch日志是计算接线；均不能自动成为重新定权重的授权/质量校准。无需追加扫描矩阵；E07/E09/E10。 |
| S4 G1逻辑 | warm门弱；建议与scratch/风险梯并行，取消其scratch启动否决权 | 将STOP解释为Owner成本控制，保留现行门 | P09独立指出失败不预测scratch不可行 | **科学判断一致，执行建议不同。** 保留当前G1失败STOP交Owner；不自动并行。修改其行政角色必须Owner显式批准；E10/E12。 |
| S5质量问题与hinge代理 | 主要质量缺陷未直接解决；塔架接触信号与hinge代理可能重叠 | 资格与CAMERA独立，可资格过而CAMERA_UNMET | P03/P07指出没有收益证据 | **同意未解决，不接受“有塔架信号即可删hinge门”。** tower无接触不能逻辑推出开角、身体接触与通过裕度均满足。质量门本轮保持；未来X21是重审议题，不是已证伪判据；E08/E10/E11。 |
| S6 C_T/包络固化 | 要求核查G0是否真正固化并集/盒参数 | 新资产→PPO链降低实现不确定性 | P04/P08已有当前绑定及计算档案 | **部分因进展解决。** 当前robot YAML/rig/source与A4/R2记录不是空头包络；但Pro未独立读回全部USD/mesh，最终containment与硬件domination仍未验证。G2不提前；E02/E09。 |
| 固定选种与产出Teacher的目标 | 赞成分层，未突出最早reach会略过后期高质量格 | 明确指出最早milestone/最小seed可能错过更好候选 | P10查到endpoint标签混合，但对“所有候选”否定边界未充分强调 | **新增B-01。** 现有规则可作为控制选择偏差/预算的预先固定规则；WaveB失败只能否定被选候选及实际评估checkpoint，不得写“全部三seed均无合格Teacher”；E10/E12。 |
| endpoint0/3且历史有候选 | 未指出此具体源码分支 | 讨论选种目标，未指出此具体分支 | P10独立静态反例 | **保留Pro独有发现。** `select_wave_a`在有历史候选但endpoint0/3时返回UNSTABLE，和§8.2终点定义不符。至少分清终点可靠性与历史候选存在性；尚无运行事故，不升级G0停止门；E12。 |
| A_S284与LEFT失败杠杆 | 认为第4seed/driver是出口；X23还称staged_reset比例是预注册杠杆 | 附加分支单列，固定三seed结论 | P02/P10保留A284资格未定 | **新增B-03。** A284同时换seed和driver，报告配对≠因果配对；不计入原三seed。当前P只固定reset比例，未见X23允许自主改比例的触发合同，不把自省提法当授权；E10/E12/E13。 |
| N01/N02/门域延期 | 已登记并称v29回收，N02依赖旧门域 | 指出PROMISING旧入口、域未收敛与未来窗口未闭合 | P11已找到N01/X24条件断裂 | **一致并细化。** 区分“重做pilot”与“多seed确认”，v28 closure触发下一planner复核，不强制启动新矩阵；QB未收敛/当前无arm-only失败层不得被略过或宣称已完成；E11/E13/E14。 |
| 文档维护与已关闭项 | S8建议首commit整理authority并建映射表 | 当前memory入口已修；X04/X08仍在长期未完成项 | P11不主张全面历史重写 | **新增B-02。** 已从长期TODO E节确认X04/X08仍unchecked，与register CLOSED冲突。只修活跃行/别名/指针，不重复机械动作，也不创建新提醒系统；E13/E14。 |
| Pull S7及跨分支字节相同 | 建议pull梯子/2seed+梯子，声明两分支字节相同 | 此轮主报告不提供新pull执行验证 | P12范围外材料LOCAL_CHECK_NEEDED | **不采纳扩展。** 本次没有核对pull实时HEAD、GPU预算及policy二进制；不能将本轮G0审计外推为pull资格或授权新训练。 |
| Novelty与80/20/0粗估 | 明确不承载novelty；工作量80/20/0粗估 | baseline优先、方法证据以后 | P03同意因果识别让步 | **定性一致。** 不把粗估百分比当计量结果。新基线是研究前提，不是本身已证明方法贡献；E10/E13/E15。 |

## B3. 初判修订/增补记录

本次**没有撤回 P01 的总体方向、P04–P07 的 G0/随机/接线结论，也没有回写A原文**。新增事项如下：

| ID | 初判状态 | 新增来源或纠正的假设 | 最终变化 |
|---|---|---|---|
| B-01 选中候选≠全部候选 | P10主要聚焦endpoint标签和A284资格 | 本地v2第4项指出选种目标偏差；重新对照P §8.2/8.4与`select_wave_a` | 明确WaveB失败的否定范围。默认不替换候选；Owner若重视成功产出，须在看v28结果前决定是否改用已有质量读数排序/替补规则。不是追加实验矩阵。 |
| B-02 X04/X08状态残留 | P11已经指出活跃入口问题，未列这两个已关闭例子 | v2第5项；独立读取长期TODO E节，确有两条unchecked，与register CLOSED相冲突 | 纳入最小文档整理。只关闭/指向已有记录，不重做关节修改或worktree删除；不声称重新核实了student本机删除动作。 |
| B-03 备用臂与reset授权 | P10指出A284资格未定，未显式写比较因果边界 | 第二包自省X23引出对照；再次检索完整当前P，只有固定reset比例及natural-eval关闭，无自主改比例路线 | A284救援比较不证明driver因果收益；原三seed分母不变；reset比例改变仍待Owner，不把意见文件升格为合同。 |
| B-04 “实机事实”措辞 | P01/P08已区分模型与硬件 | planner §2.1的“1–4不可选硬件事实”与当前质量估计/并集proxy记录不等价 | 强化表述：本轮冻结一个明确批准的工程模型，不宣称选择已由实机测量唯一确定。 |
| B-05 风险梯/延长建议 | P02建议收缩，但A尚未看过具体梯子/8000提案 | 现在读到planner S1/S2具体方案；没有新增支持其预测价值的结果 | 维持“不默认新增”；解释其多变量和低阶段终点为何不足以自动换取预算。无新实验证据，只有方案权衡。 |

额外澄清：原先可疑的“D37 max(relative,CAP)可能漏绝对CAP”在A固定前已经由`reduce_confirmation.py`的独立硬CAP分支排除，本次不将其列为代码缺陷；当前数据也全在CAP内。未来复用通用比较器需保留相应wrapper语义，这是已有合同复用提醒，不是新门槛。

---

# C. 最终判断与最小必要修订

## C1. 保留、收缩、后移

| 类别 | 最小方案 | 获得什么 | 明确牺牲/不能声称什么 |
|---|---|---|---|
| **保留主线** | 一个C_T，现行G1角色，固定A_S281–283/6000和原里程碑，reach/quality/camera分开，合格候选按既有DEV/CONF | 有界、可比较、与新装配相关的从零可靠性结果 | 不能保证一定有Teacher；不能靠中途换配方挽救后仍宣称同一三seed结论 |
| **收缩默认承诺** | 备用seed只在原触发条件下；warm长臂不当常规必交付；A2_Base opt-in不视本轮承诺；不自动加风险梯/8000 | 避免核心18.5k被顺手扩成36.5k以上，给closure留下清晰问题 | 接受本轮可能没有合格候选，不靠额外格掩盖这一结果 |
| **保留行为机制但限制宣传** | 保留已冻结wrist/tower/回位/D17/K，不新加第五项heading shaping | 获得部署相关运动/碰撞约束及可观察失败 | 不声称每项机制收益、真实视觉可用性或Student提升已成立 |
| **后移C_S** | base单/双、真实CAD/成像/裁剪/传感合同与mount swap按原定蒸馏前节点 | Teacher训练与光学细节解耦 | 更小/更轻/被包含不保证行为单调改善；未过G2不代表已可上硬件 |
| **后移方法实验，但确保回收** | v28 closure时复核N01新pilot、N02历史适应条件；N07b配对蒸馏另有预算再立项 | 避免在同时换底座时混淆因果；保留可执行科研问题 | 本轮无恢复/history/bundle因果novelty结论；v29不是自动开训授权 |

**核心判断：** re-baseline中同时落实真实需要的模型变化并非天然“太胖”。真正风险是将这些变化的实施、三seed可靠性、干净开门、Teacher资格和最终硬件兼容全部许诺为一次必成任务，再用条件臂补救所有未解问题。应以一个固定合同下的明确closure结束本轮，而不是以“终于拿到满意policy”才结束。

## C2. 最小待审批修订——不执行、不改门

以下是供本地planner核对HEAD后整理的建议稿。无需新建全面测试、提醒系统、workflow或另一个实验矩阵。

### M1. 当前入口只补一条状态声明

建议在plan/readout当前入口明确：

> 当前状态以`a2_piper_base_v28_g0_acceptance_20260912.json`及当前runtime decision为准：G0_LAUNCH_GATES_PASSED；G1未启动。后续历史STOP/D36/旧几何段落保留为历史，不作为当前执行状态。G0仅涵盖修订后的工程数值准入及接线，不含随机校准、Teacher资格、真实晚阶段行为和硬件验收。

同时将活跃引用指向MERGED、`U3_F39_H140`、j5=-0.415及C_S仍未定的最终base布局；不要全局搜索替换历史45°/180mm证据。memory首页已正确，不重复修复已经修好的例子。

### M2. 两个选种事实分列，不新增资格门

建议把“endpoint三seed可靠性标签”和“历史候选/实际WaveB评估对象”在已有readout中分列。静态反例必须保持清晰：

| 输入情形 | 当前`select_wave_a` | 按plan终点定义应单列的事实 |
|---|---|---|
| 历史从无任何候选；6000为0/3 | NOT_ESTABLISHED，无候选 | 两项一致 |
| 1000有A_S281双侧过reach；6000为0/3 | UNSTABLE，仍选A_S281@1000 | endpoint=NOT_ESTABLISHED；历史候选仍存在，不能静默删除 |
| 6000为1–2/3 | UNSTABLE，按历史最早选 | endpoint不稳定；候选身份另列 |
| 6000为3/3 | REACH_3SEED，按历史最早选 | endpoint三seed达标；候选不自动拥有quality/CONF资格 |

这不是要求立刻改源代码，更不是云端自动STOP。若本机仍为该实现，请由Owner/既有明确代码维护授权决定如何对齐标签。**不能借修标签顺便改候选身份、门值或增加替補。** 默认继续保留现行固定选种合同，但closure写：

> 未确认所选候选的双侧Teacher资格；未按本合同评估的其他seed/时点不能据此被判为全部无合格Teacher。

如果Owner的第一目标是“尽可能获得合格Teacher”，而不是“最低成本验证一个预先固定规则选出的候选”，可在尚无v28读数时决定是否基于已有milestone质量字段预注册选择/替补；这属于选择合同变更，须另授权，不要求新增采集矩阵。

### M3. G1及备用臂保持行政、科学、因果三层分开

建议只增加解释，不擅改现行路由：

> G1 WARM_FAIL保留STOP交Owner；它表示该warm迁移在500/获准延长预算内未达门，不表示scratch不存在可行解。是否启动scratch或warm长臂，由现行合同与Owner决定。本次Pro审计不授权并行或追加训练。

A_S284启动前明确其候选资格。无新决定时维持当前“预注册备用、单列报告、不自动扩展A_S281–283选种范围”的保守处理。A_S284同时换seed和K driver；即使成功也不把它当作固定三seed达到3/3，不把与触发格的比较当作同seed单因素消融。

`staged_reset_ratios`当前为固定`[0.5,0.1,0.1,0.1,0.1,0.1]`；自省提到的“比例杠杆”未在已读plan中形成可自主执行合同，不能直接采纳。

### M4. 把不可观测、几何不兼容、未学会分开

无需增加新遥测字段或测试，只在已有报告中保留其含义：

> `handle_in_wrist_*`为名义目标点in-frustum/min-z代理，不检测遮挡或有效depth；采样clearance不是硬件最小间隙。无对应事件的指标为null。RIGHT学习失败加塔架接触仅支持“当前配方/预算下未建立，E_T干涉为候选解释”，不证明不存在可行抓握轨迹，更不否定更小最终硬件。

保持旧C3 FAIL档案与原定后续v28轨迹复核，不用G0 Stage0零接触覆盖它，也不增当前STOP。

### M5. 只修四组真正会阻碍回收的TODO

| 记录 | 建议替换/追加的最小承接内容 | 不做什么 |
|---|---|---|
| N01 / X05 | v27 QR=UNRESOLVED；v28 closure后planner主动审查“重新设计pilot入口/扰动与loss可观测性”；新pilot取得有意义证据后，才考虑多seed确认。旧v27 PROMISING不再作为等待会自然变真的条件。 | 不自动启动3seed或2×2，不宣称恢复方法已有效 |
| N02及门域未收敛 | v28 closure（成功/失败都触发）复核可部署传感、可辨识性、门负载/摩擦未收敛的承接与适用域；明确本轮处理/延期/关闭。 | 不把v27 QB已闭合为未收敛当作域已解决，也不将完美Teacher或最终相机装配无限前置 |
| X24/N09、X25/N10 | X24未来触发写“下次asset/A2_Base更换前，或Owner另行授权具有真实随机暴露的校准”；本次282确认已完成但不足关闭。X25保留既有Stage2/3位姿不稳条件，与X19共同解释。 | 不重跑281、不静默改harness、不追加当前校准；不预先加shaping |
| 活跃登记一致性 | X17/X18去重并保留旧alias；X07/X09旧阶段/rig指向更新；长期E节X04/X08指向已有CLOSED记录，保留历史。 | 不全量翻修memory，不删除/重建worktree，不再次改关节配置，不新增提醒系统 |

## C3. 仍需Owner决定的最小事项

**不需要Owner为本次审计重新裁决G0数值门、重新选择硬件或批准全面测试。** 当前本机是否能执行下一步，仍以已有授权和HEAD为准；本交付本身没有新增执行权。

真正会影响本轮目标的一项前置取舍是：**保留“固定最早reach候选、接受可能不产出Teacher”的有限验证目标，还是优先提高获得qualified Teacher的机会。** 后者需在看v28结果前预注册选择/替补范围；无需先增加风险梯或全部消融。默认保持原合同。

另外两件事到触发时才需要决定：G1失败后的继续/停止成本裁决；A_S284及其他可选长臂的资格/预算边界。不要今天把所有后备分支都变成必做，也不要等看到备用臂结果后才决定其是否有资格。

---

# D. 数值核对、版本事实与证据边界

## D1. 源码与交付版本核对

Git metadata确认worker commit的父节点为`49a4c64de0bcfcbbce64070224e3c28c2cabc612`，提交时刻`2026-09-11T17:52:55Z`；审计commit唯一父节点为worker，时刻`18:06:30Z`。两commit比较显示审计交接补充计划、memory、原始计算和参考资产材料，没有改变已选G0的环境/训练/评估/判据实现。**不把“运行实现未变”写成“审计commit没有任何源文件或资产新增”**：它确有补充的参考生成/独立资产资料。

从第一包冻结输入复制的三个文件，按Git blob算法计算后与当前Git返回的SHA一致：

| 文件 | Git blob SHA | 本地复制与当前审计commit |
|---|---|---|
| `a2_piper_base_v28_plan_20260909.md` | `9cca7942601fb41823ccfa842eaaebb596cea5c4` | 相同 |
| `v28_g0_walk_gate.py` | `b19d4308d2532b75af73729dbc046a5c1b17608e` | 相同 |
| `v28_run_cell.py` | `c1e0357dbd15555708e4c05133ce35d63626b317` | 相同 |

这一核对允许使用包内长plan及脚本作为当前源内容，**不代表所有source_lock中的541文件均被Pro逐字验证**。完整copy trees未提供。环境大文件的相关新增实现通过worker commit diff核查，并结合审计commit不改runtime的比较；不是对整份约1.49MB环境文件所有逻辑作完备审计。

## D2. 三姿态原始汇总数值重算

从old/new `metrics.json`分别取每block/axis的p50、p95，独立算ratio与D36/D37门值；与三份保存的D37比较逐项相符。没有重算原始时间序列分位数，因为对应完整样本未全部随包提供。

| 姿态 | 比较项数 | 原p50比值失败 | D36失败 | D37失败 | 命令轴最大p50比 | 全轴最大p95比 | 新/旧falls |
|---|---:|---:|---:|---:|---:|---:|---|
| default | 65 | 3 | 0 | 0 | 1.091012 | 1.085112 | 0 / 0 |
| hold | 65 | 3 | 0 | 0 | 1.123854 | 1.105375 | 0 / 0 |
| stage2 | 65 | 5 | 3 | 0 | 1.062727 | 1.111611 | 0 / 0 |

每姿态19个命令轴、46个耦合轴；三姿态57个命令轴全过1.15。原p50失败的11项全属耦合轴，当前所有耦合项也都在绝对CAP内。命令分类与slope null/non-null一致；第13 replay块的逐步原始命令重建仍有材料限制。

D36类Stage2三项不是默认站立毫米级残余速度的重复：

| block / axis | 单位 | 旧p50 | 新p50 | 新/旧 | 解释边界 |
|---|---|---:|---:|---:|---|
| vx050 / pitch | rad | 0.005936860 | 0.007173582 | 1.208313 | 有前向指令下的耦合姿态误差 |
| vy_pos / roll | rad | 0.007263770 | 0.008938002 | 1.230491 | 有横移指令下的耦合姿态误差 |
| vy_pos / yaw | rad/s | 0.037344381 | 0.043482769 | 1.164372 | 角速度而非角度，不能混单位推导安全裕度 |

它们支持X25“已观察到耦合残余上升”；不支持已证明抓握失败因果，也不支持“绝对值小就与操作无关”。表中的绝对量不是最终硬件测量。

## D3. Seed282的确切新增量

独立将完整metrics去掉顶层seed后规范化：old asset与MERGED的281/282各自完全相同，规范化JSON SHA256分别为：

- old：`41885e5ddad97ff0bcb4ef2d8111a5d598d6522ec657a641d2144a55c4531738`。
- MERGED：`a3e31dc1f57419de6469ad530a13d4f9997ccf7b69cfe68e9996a926c29e4600`。

两次新进程确实被记录，不是说282没有执行；新增量是确定性复核和执行链证据。64env是并行运行规模，不自动是64个独立随机实例；多个命令块也不等于随机重采样。不能由汇总数值相同推断整个物理引擎永远bitwise deterministic，也不能由seed标签不同反向宣称已建立随机稳健性。

D37 wrapper代码还独立检查coupled hard CAP，因此本轮没有发现“只过max门、但漏掉硬CAP”的假PASS。X24未知的是实际随机暴露下散布与15%准则表现，不是本次算术真假。

## D4. 关键时间线

所有下列时间为2026-09-11 UTC；换HKT后部分为9月12日，日期跨天没有矛盾。

| 时间 | 记录 | 能证明的范围 |
|---|---|---|
| 16:05:37 左右 | 原default失败后STOP记录 | 旧纯比例门确实失败、并未被抹除 |
| 16:26（Owner决策文字） | D36 | 默认数据事后；hold/Stage2后续执行前 |
| 16:31起、16:33完成 | D36 hold/Stage2进程 | 两次进程正常，Stage2门失败 |
| 16:36:02.641203 | D36 STOP | 第二次停止记录 |
| 17:23（Owner决策文字） | D37 | 看过三姿态后的第二次门修订 |
| 17:28:17.231524 | preregistration写入 | 早于282 GPU进程 |
| 17:28:48.773597 / .832320 | 282 old / MERGED启动 | 新进程，非新随机实现 |
| 17:30:33.545154 / 39.618550 | 282 old / MERGED退出 | 记录exit0、输出存在 |
| 17:31:38.430016 | confirmation_decision | D37数值分支PASS |
| 17:34:14 左右 | seed_exposure_audit | 披露无新增随机消费者的证据边界 |
| 17:35:40.256776 | source_lock_d37_ppo | 后续source-copy记录，完整树未提供 |
| 17:36:01.034569 → 17:38:00.584103 | PPO smoke | 64env、iteration1–5、exit0 |
| 17:38:56 → 17:43:27/30 | LEFT/RIGHT eval | full-checkpoint natural exact64、exit0 |
| 17:47:37.431316 | telemetry_validation | 26字段与无事件null的原本机验收 |
| 17:49:55.042737 | G0 acceptance | launch范围的通过 |
| 17:52:55 | Git worker commit | 首个G0实现提交 |
| 18:06:30 | Git审计上下文commit | 只追加交接相关上下文，不改G0运行实现 |

Owner时间来自已提交决策记录，进程时间来自原始receipt；本次未访问Owner原会话或现场系统来独立认证授权主体。

## D5. 接线、事件、Teacher与硬件的五级证据

| 层级 | 本次可得结论 | 不可跨越的边界 |
|---|---|---|
| 源码/配置 | 当前MERGED/28体、reset、clamp、bundle/K、camera reducer及run/eval逻辑可检查 | 不是完整本机环境安装/二进制一致性认证 |
| G0进程链 | 原始日志支持64env×5batch PPO→checkpoint→左右exact64 eval | 未在Pro环境实际加载checkpoint/运行训练 |
| 遥测接线 | 每侧64条唯一env终态、26字段，7null；记录只到Stage0 | 22,400全trace rows未由Pro重解析；晚事件逻辑未被实际覆盖 |
| 学习和Teacher质量 | 当前无G1/WaveA/B结果，不授予资格，也不据5batch Stage0判训练路线失败 | 不能把launch、名义FOV、零接触当抓握/释放/通过能力 |
| Student/硬件 | 只有接口与后移计划、名义模型/SDK配置引用 | 没有本轮Student成功率、实测CAD/质量、标定运行或硬件安全证明 |

## D6. LOCAL_CHECK_NEEDED清单——不是新生产门

1. 本机当前HEAD、dirty/untracked差分、后续dispatcher以及后续是否已经运行G1；本报告只绑定指定commit，不推测本机现在状态。
2. 完整`source_lock_g0/source_lock_stop/source_lock_d36_stop/source_lock_d37_ppo`副本与原checkpoint/导出TorchScript的字节一致性。manifest记录BYTE_COPY_VERIFIED，不等于Pro重做了全树检查。
3. 未附的LEFT `494,858,088` bytes、RIGHT `493,999,381` bytes step traces及真实晚阶段事件；需要时只读核对已有材料，不默认追加采集。
4. 第13命令块引用的原v27 trace及其58-step命令序列；当前能验证来源指针、记录分类和汇总算术，不能声称重建了缺失序列。
5. 实际IsaacLab/驱动安装、当前GPU占用、实时policy进程、最终CAD/质量/标定/真实传感能力、硬件碰撞/行走/开门；均没有在云端执行或现场验证。
6. Pull/student/sim2sim最新worktree及跨分支二进制相同的声明。第二包提到这些，不等于本轮已经访问和验证。

不建议为了消除每个LOCAL_CHECK_NEEDED就重跑全实验。它们标记“不能声称已验证”的边界；实际执行仍由Owner授权与原合同决定。

## D7. 证据索引

所有`R/`和`D/`均按A开头定义展开；ZIP中不存在的本机路径只作为原始引用，不被当作已获取文件。编号便于本地AI追溯，不取代具体路径。

| 编号 | 具体来源 | 本次用途与边界 |
|---|---|---|
| E01 | Git commit `8811c...`、`843585...` metadata及两者compare；第一包`worker_delivery__BUNDLE_INDEX.md/PRO_HANDOFF.md/BUNDLE_MANIFEST.json` | 版本、父子关系、包清单、读取边界；228原始文件长度核对 |
| E02 | `gr00t/rl/config/robot/A2_Piper/a2_piper_vpiper.yaml`；`gr00t/rl/config/ablation/wbmanip/base_v28_common.yaml` | 当前28 bodies、MERGED、j5=-.415、reset/K/reward、camera关闭 |
| E03 | `V/a2_piper_base_v28_g0_acceptance_20260912.json`；`R/g0_decision.json`；`D/first_commit_receipt.json` | 当前launch验收、首commit与未运行范围 |
| E04 | `V/a2_piper_base_v28_decision_log.md` D036/D037；`V/a2_piper_base_v28_g0_resume_readout_20260912.md`；`D/walk/{default,hold,stage2}_comparison*.json`及各process receipt | 原FAIL、D36/D37的版本、授权档案与时间顺序 |
| E05 | `D/d37/{preregistration,confirmation_decision,old_asset_posture_perturbation,asset_pair_seed282_comparison_d37,old_asset_seed281_vs282_d37}.json`；`D/d37/reduce_confirmation.py` | 预注册时点、离线/282数值判断、wrapper硬CAP |
| E06 | `R/g0/walk/baseline_stage2/metrics.json`；`D/walk/v28_stage2_d36/metrics.json`；`D/d37/{baseline_stage2_seed282,merged_stage2_seed282}/metrics.json`；`D/d37/seed_exposure_audit.json`；`gr00t/rl/scripts/smoke_a2_base_flat_walk.py::run_flat_walk_smoke` | 除seed外完整字典相同；seed设置在reset后；policy图无随机算子是worker核查声明，二进制未由Pro重验 |
| E07 | `D/ppo_smoke_d37_r1/{runtime.log,process_receipt.json,config.yaml}`；`D/telemetry_eval_d37/{left,right}/{process_receipt.json,.hydra/runtime_config.yaml,a2_v14_per_env_records.json,camera_metrics.json,metrics_eval.json}`；`D/telemetry_validation.json` | 5次iteration/reward、64+64终态、26字段/7null；不含完整trace重算 |
| E08 | `V/v28_camera_metrics.py::{project,reduce,summary,reversal_stats}`，尤其`projection/geometry/sample_counts`输出 | in-frame不是无遮挡/立体重建；clearance表面采样上界；空population为null |
| E09 | `D/{g0_a4,g0_c3}.json`；`D/contact_merged_h140_r1/data/contact_probe.json`；G0 acceptance相关R1/R2/R3/R5记录 | 默认姿态静态A4与历史动态C3分离；原生运行接触/姿态记录；并非硬件验证 |
| E10 | `P` §0、D17/D30–D37、§3/6/7/8/9/10；当前copy blob已比对 | 审计对象的合同和权衡；理由不自证正确 |
| E11 | `scriptsFORhuman/v27/a2_piper_base_v27_execution_closure_20260911.md` | v27 scientific no-release、QR未决、SC0/3、SK1/3、确认NOT_RUN；未声称复算所有v27 trace |
| E12 | `V/v28_contract.py::{cell_contract,cells}`；`V/v28_reduce.py::{reachability_gate,passes_gate,select_wave_a,k_reach_without_complete}`；`V/v28_run_cell.py::{train,evaluate}` | G1/scratch/A284合同、endpoint与历史选择逻辑、自然eval覆盖 |
| E13 | `V/a2_piper_base_v28_deferred_register.md`；`scriptsFORhuman/a2_piper_longterm_TODO.md` D/E节 | N01/N02/N07–10、X24/X25、重号、已关闭项未同步 |
| E14 | `MEMORY.md`；`memory/a2-piper/MEMORY.md`；`memory/a2-piper/base-v28-camera-aware-rebaseline/{description,TODO}.md` | 当前状态已更新；历史与活跃入口区别；A284资格未定 |
| E15 | `memory/a2-piper/novelty-research/description.md`及长期TODO R/D节 | 方法路线延期与研究前提；未阅读其归档意见来生成A初判 |
| E16 | `gr00t/rl/envs/base_task/delta_action_base.py::step`；worker commit中`door_open_a2_base.py`的wrist/接触/Stage4门控及telemetry diff | 动作积分器限位与新增机制；没有执行核心类或导入IsaacLab |
| E17 | 第二包planner自省及`LOCAL_TEAM_AUDIT.md` v2 | 只在A固定后读取，作为意见交叉，不替代源码/实验事实 |
| E18 | Pro只读JSON计算：195比较项、128episode记录、52导出字段键、两组seed字典对比；本报告D1–D4列出结果 | 计算对象是已提供汇总值，不是补做仿真、GPU实验或全trace重归约 |

## D8. 交付与未执行事项

本次只生成对话附件中的`FULL_REVIEW.md`与`LOCAL_WORKER_PARSE_PROMPT.md`及普通ZIP。没有上传Drive，没有改代码/config/plan/TODO或远程仓库，没有启动训练/实验，没有变更Teacher/G7，没有操作硬件。没有对外部文献作全面新颖性检索；“本轮不证明novelty”是实验设计与证据边界判断，不是宣称不存在任何潜在可发表贡献。

**最终建议仍是：承认G0已经完成的工作，拒绝其未证明的外推；用更清晰的范围和结论收口，而不是默认再加一轮基建。**
