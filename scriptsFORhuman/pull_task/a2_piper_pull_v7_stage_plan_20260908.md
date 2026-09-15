# Pull v7：当前 plain backbone 下的 E5 入口与 release→E7 阶段方案

日期：2026-09-08 HKT。工作目录：`/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0`。
分支：`codex/a2-piper-pull-v0-20260803`；本次核对的 HEAD：`025ce28`。

**本版已被 [2026-09-09 修订版](a2_piper_pull_v7_stage_plan_20260909.md) 取代；P0/P1 定义与产物继续有效，P2 以修订版为准。**

**状态：方案已落盘；未启动 v7 仿真或训练。** Owner 已要求落地阶段方案；新 GPU 诊断预算与正式实验预算尚未批准。本文不重新打开 v26.8 迁移验收，也不继承旧 Wave1/Wave2 预算。

## 1. 阶段决定

v7 在当前已验证的 plain LSTM backbone 上推进送门、松手、机械臂回收、通行直到 E7，同时保留双侧抓握、解锁和 opening。

首段固定为 **E5 入口轨迹与实际训练曝光诊断**。先解释当前策略如何进入近限位的 E5 状态，再判断什么干预能改变这条轨迹。首段不改 reward、E 事件、actor、观测、plant 或 reset ratios。

上一版 `workspace_margin_progress=30` 配对实验及其预算建议已撤回。margin 是直接诊断量；“未满足 margin”不能推出“必须增加 margin 奖励”。本版同样不预设新的 reset 比例，也不把旧 99% Stage4 配置直接搬入当前 backbone。

执行闭环为：

```text
P0 既有轨迹/配置证据 -> 必要时 P1 有界原配置续训曝光诊断
-> 一次阶段裁决 -> 冻结一个 P2 干预及同期对照 -> Owner 批准正式预算 -> 实施与评估
```

P0 的问题、数据范围和输出已具体定义；P1 的运行上限已给出。P2 的处理变量尚未有足够证据支持，本版不伪造一组可直接启动的正式矩阵。

工作流采用 STANDARD：Main 是文档唯一 writer；focused read-only agent 核对历史分支和 reset/telemetry 路径。此规划不启用 ledger、lease、freeze 或 artifact handoff。实施资源任务时再按实际冲突启用必要设施。

## 2. 已知事实和因果边界

### 2.1 当前 backbone 与历史成功的关系

- v26.8 已建立两个 seed 的双侧 durable unlatch/opening；最终 P_S2 两侧 D/E4/E5=64/64，P_S1 LEFT=64/64、RIGHT=62/64；四侧 E6/E7=0。4500 首次 unlatch endpoint、5250 首次双 seed bilateral opening 与旧 6000 源选择保持不变。
- 旧 r6an seed3 step25 在 strict-natural 4 eval seeds×16 首 episodes 下，E5/clean/frame/E6/E7=`41/5/3/2/1`。这是真实完整链路的可实现性证据，成功率尚低；不能因其含 learned override 否认该参考。
- 已逐项比较旧 r6an seed3 保存配置与当前 P_S1 resolved config：非零 reward 权重相同，二者都没有启用 `a2_pull_v6_workspace_margin_progress`。这项比较是保存配置的权重事实，不代表整个历史开发过程从未改过 reward 函数或权重。
- 旧 release mean 是可训练参数，D-only base/arm 输出由可训练线性层给出；显式 release-mode 门控和参数冻结提供了结构上的学习条件。旧成功由奖励训练出的策略产生；“奖励相同”不等于状态分布、优化问题或学习路径相同。
- r6an 训练源为 r6am seed0 step25，256 env、policy-only、99% Stage4 reset、专用 Stage4 bank 开启；其 D-only actor 冻结既有 carrier。当前两源是1024 env、固定混合 reset、banks off、全参数 plain LSTM。旧 r6ap 的36秒/Stage5 800步是该胜者的 eval 合同，旧 r6an 训练仍为24秒/Stage5 300步。
- 历史 population integrated/grouped/B-focus 方案均未保留 baseline E6/E7；提高 E5 admission 不等于改善 B→C 或保住下游链路。因此本版没有直接提高 Stage4 reset 比例的建议。

### 2.2 当前四侧 E5 后条件读数

范围：step9000、各环境首 episode、自首次 E5 起的已存 trace。每格原始分母64；下表按 E5 到达者统计单项 ever，不把 trace rows 当独立样本，不声称单项 ever 的集合曾同时满足。

| 来源/侧别 | E5分母 | workspace≥0.07 | hinge≥1.134464 rad | hinge速度≥0.15 rad/s | clearance≥0.02 m | release-ready |
|---|---:|---:|---:|---:|---:|---:|
| P_S1 LEFT | 64 | 0 | 1 | 2 | 37 | 0 |
| P_S1 RIGHT | 62 | 0 | 61 | 6 | 62 | 0 |
| P_S2 LEFT | 64 | 0 | 45 | 11 | 0 | 0 |
| P_S2 RIGHT | 64 | 0 | 47 | 0 | 63 | 0 |

四侧 workspace 最大值依次约0.000249、0.000268、0.000233、0.000067，全部远低于0.07。该指标是六个非夹爪关节的最小归一化限位余量；arm_j4 限位占比为零不能替代它。

P_S2 LEFT handle-crossed=64/64，但 clearance 始终在约[-0.0775,-0.00646] m；P_S2 RIGHT handle-side 条件从未满足，handle-Y 在约[0.0938,0.2085] m，高于≤0.06 m门槛。四侧 E5 后 raw/applied 开爪命令、release、clean release、frame passage 和 crossing 均未出现。

这些是既有运行的描述性再分析，不是新增因果实验。P_S1 RIGHT 另外两个未达 E5 的 episode 仍计入最终 natural64 能力分母。

### 2.3 旧成功轨迹的入口对照

取现存 r6an seed3/env14 成功 render trace，其 native natural 场景为16 env、无 evaluator 动作干预。以下 `trace_step` 为文件内零基 step_index，`episode_length_buf` 比它大1。

| 时刻 | trace_step | workspace margin | clearance m | hinge rad | hinge速度 rad/s |
|---|---:|---:|---:|---:|---:|
| E5后pivot首次捕获、进入B | 318 | 0.121978 | 0.315599 | 1.004406 | 0.272303 |
| release-ready | 356 | 0.102693 | 0.296395 | 1.240270 | 0.374817 |
| clean release | 357 | 0.105285 | 0.294199 | 1.247737 | 0.371905 |

旧成功 episode 在 E5 入口已经具备 margin 和 clearance 余量；当前 E5 后的全部已观测 margin 连入口在内均不达标。因此“入口轨迹不同”有直接证据；尚不能据此判断差异始于哪个上游事件，或断言哪个训练因素造成它。旧单侧成功轨迹只作为机制参照，不与当前双侧群体做 matched causal comparison。

### 2.4 r6r 的已知范围

`pull_v6_F0_r6r.yaml` 继承 r6q，仅新增 workspace-progress scale4；四个登记命令从 r6q seed2 step50 做 policy-only、256 env×50 batches。当前本地没有找到该格独立 checkpoint、eval metrics/reducer；命令表虽然标记 done，结果说明仍为空。

结论为 **独立效果 UNRESOLVED**。r6an 不继承 r6r 的 checkpoint 或 reward 配置，不能把 r6an 的 E7 归功于 r6r；也不能将缺失 artifact 写成 r6r 失败。本阶段不为找回 r6r 结果重跑该实验。

## 3. 冻结的当前基线

| 项目 | v7首段固定值 |
|---|---|
| Actor / critic | 原生 plain RecurrentActor/RecurrentCritic，LSTM；133/138维，native RMS行为 |
| 策略来源 | P_S1、P_S2各自Wave2 step9000；不视作Teacher，不改写旧6000选择 |
| 几何与plant | LEFT抓握目标镜像开启；finger45/45 N，Kp/Kd1300/32，M39开启 |
| 抓握能力窗口 | squeeze0.5/30；over-force55 |
| Gate / rewards / events | grasp_completion；现有Stage3+ reward与E事件语义全部保留 |
| 训练reset | enable_staged_reset=true，固定[0.5,0.1,0.1,0.1,0.1,0.1]；两项v6 bank关闭 |
| Natural eval | enable_staged_reset=true，Stage0-only [1.0,0,0,0,0,0]；两项v6 bank关闭，核对真实首episode出生trace |
| 时间尺度 | 200 Hz physics / decimation4，即0.02秒/control step；64 control steps/batch |
| Full加载限制 | 恢复policy/critic/optimizer/scheduler/TrainerState；online reset样本新进程重新积累；不声称恢复了完整physics与LSTM轨迹历史 |

两个来源：

```text
logs_rl/a2_piper_pull_v26_8_backbone/pull_v26_8_backbone_20260905_natural1_r2/wave2/train/P_S1/model_step_009000.pt
logs_rl/a2_piper_pull_v26_8_backbone/pull_v26_8_backbone_20260905_natural1_r2/wave2/train/P_S2/model_step_009000.pt
```

## 4. 实际执行语义：避免诊断错位

- `DoorOpenA2Pull._update_a2_pull_v6_state` 在E5捕获pivot并进入B。release-side要求handle-Y≤0.06、双指接触、panel-clear、pivot≤0.15m、累计arm tangent share≥0.6；ready再要求门角、正速度、clearance和workspace同时合格并进入C。
- 当前 `hard_gate` E5由aperture-ready与panel-clear产生；它不保证release-ready。ready不依赖frame passage或crossing，没有“必须先通行才能松手”的直接循环。
- `minimum_panel_robot_clearance` 是trunk中心到门板线段距离减0.02m门板半厚与0.40m footprint半径；它不是接触力。负值不能直接写成真实穿透。
- 开爪primitive>0映射为open target。release-open scale96仅在action-start ready或clean-event支付；B阶段仍有keep-close和open-command penalty。当前不开爪不证明执行器把开爪命令强行抹掉。
- E6要求prior E5、正向crossing/velocity、panel-clear、frame passage、clean-release persistence≥25；E7要求prior E6、所有robot bodies越过门平面1.5m、panel-clear、frame passage。
- release event要求previous bilateral→current no-contact，clean还要求previous ready。真实ready/open形成后再检查接触过渡，不能预先更改事件定义。
- `_sample_reset_stages` 会把该env没有样本的stage权重置零再抽样。因此配置ratio不是实际reset比例，更不是实际训练step占比。
- 当前没有可直接还原v6实际reset来源/phase的日志。`get_a2_pull_control_step_telemetry`与`_after_reward_components`已有本步状态/raw reward可复用；`export_a2_pull_v5_census`仅支持旧variant且统计库存，不能替代v6实际抽样曝光。
- banks off时，v6仍通过普通online snapshots保存E5、ready与D阶段状态。关闭外部v6 bank不等于禁用online staged reset。
- 当前P_S1末尾训练日志的Stage4 active fraction曾为0.6223，尽管配置Stage4 ratio只有0.1。这只是一处日志读数，已足以说明不能把0.1当作Stage4实际曝光，更不能把它当作B/C/D曝光。

## 5. P0：既有artifact的有界入口诊断

**成本：0个新GPU运行、0个训练batch。** 实施时Main可委托一个只读数据lane；不重验G0/G1、不通读全部旧session、不重扫旧residual/head路线。

输入限定：

1. 当前step9000四侧首episode traces、对应metrics/per-env records与resolved configs。
2. 旧r6an seed3/env14成功render trace；同文件其他episode作为有限失败参照，不能只拿winner当群体分布。
3. 两个当前来源的Wave2训练日志、checkpoint中实际保存的env state，以及r6an保存配置。

一次流式提取成小表后停止反复解析原始大trace。按env保留：E2/E3/E4/E5首事件、E5后25/50/100步及terminal；不存在的事件明确为空，不用最近的一行冒充事件发生行。E5条件检查仍使用全部E5后控制步，而非仅这些摘要行。

必要列：

- source/side/env/episode、trace step与episode counter、事件标记与实际stage；
- 六关节实际角度、实际target、各关节按release公式计算的margin及最小值的关节名；soft-limit penalty使用的另一种margin单独标注；
- hinge角/速度、TCP pose误差、raw/applied arm与base command、双指接触；
- clearance、handle-send-Y、pivot displacement、累计arm tangent share；
- 同一步ready全部条件、全部通过数、仅缺某一条件的窗口、ready最长连续窗口；
- E5前后轨迹的margin变化，首次低于0.07的实际可观测位置；若入trace前已经不达标则明确左截断，不补造上游事实。

输出落 `scriptsFORhuman/pull_v7/`：`P0_ENTRY_TRAJECTORY.csv`、`P0_READINESS_FUNNEL.json`、`P0_DIAGNOSIS.md`。它们是计划产物，目前尚未生成；§2保存已完成的接手读数，不能把它冒充完整P0。

P0必须回答：

1. margin缺口是在E3/E4以前已有，还是opening过程中形成；是否是同一关节、同一类target与base运动？
2. 是否存在除margin外其余ready条件同一步全合格的真实窗口？若没有，margin不能被称为唯一瓶颈。
3. 从当前自然轨迹中能否观察到有余量的进入B路径，以及这些状态在现有snapshot规则下是否有被采集的机会？
4. 现有训练artifact是否足以给出B/C/D、ready及奖励激活的实际曝光？只能看到Stage4总占比时，结论仍不充分。

P0结束即做一次裁决：足够支持具体干预则进入P2设计；只有实际曝光缺口需要新数据时才申请P1。不为了流程完整运行P1。

## 6. P1：必要时进行原配置曝光诊断续训

**授权状态：待Owner批准；这是真实PPO更新，消耗新的训练预算。** 用途为测量原配置在新进程中的实际曝光，不比较干预、不自动promotion诊断checkpoint。

### 6.1 固定运行合同

- 两个source各一个cell，分别full加载自己的step9000，seed仍为1/2；每格1024 env、绝对batch上限9100，即各新增100 batches。
- actor/critic与原PPO照常更新；不冻结一部分参数，不重置optimizer，不改奖励、ratio或场景。加入的只有计数/导出，不能增加policy observation或随机抽样来实现遥测。
- 在9050/9100保存诊断checkpoint。两格总计200新batches、13,107,200 transitions。按旧Wave2约22秒/batch估算总计约1.2 GPU小时；两格并行约37分钟，启动开销另计。这不是承诺当前速度。
- 本预算不包含额外natural eval、render或延长训练。当前baseline natural评估已存在，不重复迁移验收。
- 100 batches只代表初期曝光窗口；不能保证banks成熟。若末段样本/曝光仍在漂移，报告瞬态与不足，不自动延长或宣称稳态。

### 6.2 遥测必须按真实总体计数

每个cell按side与10-batch窗口聚合，覆盖全部1024 env；同时区分真实Stage0出生episode与staged出生episode。

reset记录直接绑定实际selected stage/sample index与加载后的subphase。源码并无“先抽一个请求stage再拒绝”的步骤，不创造requested-stage标签；只保存配置权重、有效性mask和实际抽样。库存需区分累计写入计数与环形buffer中有效槽位数，不能把累计计数当作当前存量。

| 要回答的问题 | 直接计数/读数 |
|---|---|
| 到底从哪里reset | `_sample_reset_stages`实际返回stage的计数；分母为实际reset数；各stage可用样本的env数与库存摘要 |
| Stage4里学到哪一段 | B/C/D控制步数，分母为全部有效rollout步；另给各side的条件分母 |
| ready是否有训练曝光 | ready步数、episode数、连续窗口；按自然/staged出生分开 |
| 后段奖励是否能起作用 | 复用本步已算出的reward raw/scaled值及对应激活mask，分别记录曝光与正负收益；不能以四舍五入0.0000推断绝对零 |
| 有没有可用的入口样本 | E5/ready/D snapshot实际写入次数、reset后实际加载的subphase及margin分布 |
| 是否形成释放 | raw/applied开爪、release、clean、persistence25与E6/E7的实际计数 |

实现先追踪真实trainer rollout与env状态更新时序，避免在reset之后读取上一episode terminal。已有hook能完成时直接复用；不要为诊断增加actor head、bank格式或通用监控框架。

输出：每格`resolved_config.yaml`、run receipt、`exposure_by_side_origin_window.jsonl`、9050/9100 checkpoint与退出码；统一汇总为`P1_EXPOSURE_REPORT.md`。指标缺失就报告对应证据缺口，不造默认零。

### 6.3 执行边界

任一真实异常、NaN、缺失源checkpoint、来源/配置不符或用户停止指令即停止该cell并保留日志；不新增fallback。达到9100自然停止，不因没有E7自动加时。

使用当时实际空闲GPU，至少每作业一张卡，不从旧GPU编号推定授权。预计超过30分钟，各cell在独立tmux；等待由作业监督器长间隔处理，Main只报告有意义的完成、失败或待决事项。未到启动阶段不创建GPU lease。

## 7. P2：一次证据驱动的正式方案裁决

P0/P1结束后，Main提交一份短决策，固定一个主要因果问题。下表是决策约束，不是同时执行的实验轴。

| 读数 | 允许形成的判断 | 尚不能推出的结论 |
|---|---|---|
| E5前已经近限位，B阶段很少获得有余量入口 | 优先针对入口轨迹形成/保留设计干预，并测量其上游影响 | 再加一个E5后margin奖励就会解决问题 |
| 有余量入口存在，但实际采集/加载很少 | 可提出一个有实际库存和曝光依据的采样干预 | 直接照搬99%Stage4或仅按配置ratio估算预算 |
| 训练有ready窗口但natural没有 | 重点处理natural/staged状态分布与连续历史差异 | ready在当前任务物理不可达 |
| natural ready持续出现，但没有正开爪 | 此时才定位开爪动作的时序信用、梯度曝光与mean变化 | 在ready仍为零时归因于夹爪输出结构 |
| clean release形成但E6/E7缺失 | 按release→persistence→frame→E6→E7定位下一个中介 | 放宽事件门槛或把release当作E7能力 |

若证据仍不能区分，只允许说明一个具体缺失测量与有界获取办法；不循环审计整套迁移。只有在已有奖励对目标轨迹确有未覆盖/反向支付证据时，才重新提出一个reward语义改动交Owner裁定。

正式矩阵冻结前必须填全：唯一处理变量及数值、同期原配置C、source checkpoint、更新参数范围、reset与history合同、实际env数/control steps、新增batch绝对上限、预计GPU小时、eval频次、直接中介和停止条件。**当前P2训练预算未申请、未批准；P1预算不能流用。**

旧r6an只用于源轨迹对照；不将其checkpoint、action labels或bank导入当前训练。若未来需要BC/Teacher、旧override、release-mode观测或E门改动，属于新的Owner决策，不在v7首段中自动获得授权。

## 8. 后续正式候选的报告口径

这些是v7拟采用的能力判定口径，待P2具体实验注册时确认；P0/P1不产生promotion。

- 同一cell两侧分别exact64首natural episodes，保留真实出生trace与当前E事件validator；K5/D/E4/E5、ready、clean、persistence25、frame、E6、E7、complete分别报告。
- 先报告每侧全体64分母，再报告E5到达者的条件转化率；不隐藏未达E5的环境。
- 保留能力的操作门暂定每侧D/E4/E5≥60/64，K5同时报告；它是实验决策阈值，不是统计等效性证明。正式C/T比较必须保留各自9000源读数。
- 一条有效natural E7只能标记“观察到完整链路”；同一cell两侧E7各≥8/64可沿用`PULL_FULL_CHAIN_OBSERVED`标签。两个独立来源复现再报告重复性，不能据此称稳健部署策略。
- 干预中介改善但release/E6/E7未形成时，保留中介结论并明确全链路未达成。没有中介变化的负结果只适用于该次处理与曝光，不能否定plain LSTM整体能力。
- 正式训练源暂保留P_S1/P_S2的9000 checkpoints，P0/P1裁决前不预选胜者。P1的9100诊断checkpoint不自动替换它们。

## 9. 最小施工顺序与产物

1. 本轮：本文、相关memory与文档入口；不修改训练源码/config，不建立可误启动的新训练shell。
2. P0实施：一个离线提取/分析入口和三个小型结果文件；优先复用现有trace/reducer字段，只扫本计划输入集合。
3. 若P1获批：补实际缺少的遥测、一个v7诊断launcher及报告；完成最小端到端路径。用该次真实诊断的配置、计数和产物证明运行，不新增测试矩阵或反复smoke。
4. P2获批后才实施处理变量。后续正式run必须使用新输出目录；历史v26.8和v6 artifact只读。

计划输出根：`scriptsFORhuman/pull_v7/`；GPU诊断/训练输出：`logs_rl/a2_piper_pull_v7/<run_id>/`；后续评估：`logs_eval/a2_piper_pull_v7/<run_id>/`。本轮不提前创建空run目录或运行receipt。

不默认启动push/pull合一、Teacher/Student、hardware、云端handoff；不commit/push。既存`.codex/config.toml`改动、`Codex-Cashier/`与新robot目录不属于本任务WRITE_SET。

## 10. 最小证据路由

- 当前迁移closure：[v26.8 closure](../pull_v26_8/a2_piper_pull_v26_8_backbone_closure_20260908.md)、[SUMMARY](../pull_v26_8/SUMMARY.json)、[reducer合同](../pull_v26_8/REDUCER_CONTRACT.md)。
- 旧完整链路与population反例：[v6.1 population报告](../pull_v6_1/PULL_V6_1_P_POPULATION_REPORT.md)。
- 旧成功trace：`logs_eval/a2_piper_pull_v6/p2_render_F0_r6ap_r6an_seed3_env14/eval/stage2_5_step_trace.json.gz`。
- 当前四侧trace：`logs_eval/a2_piper_pull_v26_8_backbone/pull_v26_8_backbone_20260905_natural1_r2/wave2/eval/milestones/step9000/{P_S1,P_S2}_STEP9000/{left,right}/stage2_5_step_trace.json`。
- 权重比较：`logs_rl/a2_piper_pull_v6/pull_v6_F0_r6an_seed3/config.yaml`与当前Wave2 `P_S1/resolved_config.yaml`。
- r6r：`gr00t/rl/config/ablation/wbmanip/pull_v6_F0_r6r.yaml`；`experiments/COMMAND_BATCHES.md`约8501行的四seed命令。只证明登记内容，不能替代缺失的结果。
- release/奖励/snapshot：`gr00t/rl/envs/door/door_open_a2_pull.py`中的`_update_a2_pull_v6_state`、`_reward_a2_pull_v6_release_open_command_quality`、`_reward_a2_pull_v6_workspace_margin_progress`。
- reset抽样：`gr00t/rl/envs/base_task/staged_task_base.py::_sample_reset_stages`；full loader：`gr00t/rl/trl/trainer/ppo_trainer_a2_base_api.py::load_checkpoint`；env保存：`gr00t/rl/envs/legged_base_task/legged_robot_base.py::get_env_state_dict`。

证据等级：源码/配置为INSPECTED；§2数值来自已有runtime/正式实验artifact的只读再分析；v7 runtime、正式实验与hardware均NOT_RUN。方案落盘不代表P0已经完成，也不代表新实验获得授权。
