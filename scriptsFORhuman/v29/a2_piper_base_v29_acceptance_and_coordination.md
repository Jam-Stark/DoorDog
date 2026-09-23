# v29完整baseline：planner验收、双向协调与GPU0开训合同

Owner于D030授权离线期间planner与worker自主沟通推进。本文由planner在D031制定，覆盖本工作区完整v29 push baseline实现和首轮训练监督；不能把B05技术附件当作总任务。

## 1. 角色、状态与权限

Planner：`01a0af49-b5e0-75f2-8fdd-ad5c3e20744b`，[任务入口](codex://threads/01a0af49-b5e0-75f2-8fdd-ad5c3e20744b)，本机App host为`remote-ssh-discovered:gpu1-codex`。Worker任务已按D032绑定为`01a0b592-48e3-7ad0-9263-4cb605862ed6`，由Owner创建、以真实WORKER_READY登记。当前C001准备与有界验证已授权，尚无TRAIN_APPROVED。

流程：**worker接手 → 完整实现及自查 → 具体候选报告 → planner逐项验收 → 必要修正与增量复核 → planner明确批准 → worker使用GPU0训练并监督 → 结果交付/验收**。

planner可以在Owner离线期间自主裁定方案内技术问题、要求修复、选择必要验证并批准/拒绝开训。worker可自主处理既定范围内实现与内部委托。worker自评、子agent审阅、方案TODO完成和消息入队均不替代planner最终裁定。

生产source/config/asset由worker负责实现；planner主要读取、验收、维护计划/主决策/批准记录，不与worker抢写同一路径。跨任务开始后按`.ai/TEAM_STATE.md`记录真实任务、写入边界、候选和GPU资源；复用已有工具，不新建另一套协调系统，不清理无关旧任务。

## 2. 候选提交与证据身份

每轮使用C001/C002等明确编号及独立证据目录。提交目录应包含逐项实现报告、实际source/config/资产快照或可定位差异、真实resolved config、采样seed/参数、运行命令/退出状态、原始读回及B05图像/关键帧。使用路径、时间、分支及实际文件快照识别候选，不写哈希清单。

提交验收期间冻结本候选的相关输入；可另做不影响候选的文档整理。修正形成下一候选并说明变化及受影响证据。planner对明确无关的旧证据可保留，对受影响或不确定项重新核实，不机械重复全套。

验收结论与候选/实际配置/资产绑定。planner批准后如改变影响训练的输入，先由planner判断需要重新验证的范围；不能沿用旧批准启动改变后的训练。

## 3. 逐项验收内容

planner必须逐行给出事实、证据和结论；不因旧版本PASS或worker一句“已完成”跳过。起训验收目标是实现正确、资产组合可用、端到端训练接线成立；策略效果在训练后评估。

| 项目 | 必须核实的实际行为 | 主要证据 |
|---|---|---|
| B01质量/惯量 | 三档各1/3、closer有无各半，质量/几何/惯量一致，rose未额外叠加总门重；每门参数固定 | 真实生成分组、metadata与PhysX质量/COM/惯量读回，实际计数 |
| B01 drive/friction | SI→USD转换一次，T/k/d/q0正确，有/无closer分支真实生效；native静/动/粘性摩擦落到正确env/joint，后续writer未覆盖 | 生成、reset后及步进中的参数读回；有限代表门的释放/驱动响应，弱closer被摩擦抵消可为真实物理结果 |
| B04 | 每门M90–150真实native upper、degree/rad一致、episode/staged恢复不重抽，不通过写q/qdot模拟限位 | 原始USD+runtime硬限位读回、边界门步进、metadata/恢复对照 |
| B05 | 新几何与完整随机组合可生成、可导入、可按既定参考接近/闭合，目标/碰撞/质量/重建一致 | 见§4，必须看新资产与运行读回 |
| Stage5 | goal[2,0,.5]、heading -4及新增roll/pitch -8与原-2正确合成、仅Stage5/不随K衰减；原完成条件保持 | 实际resolved权重/调用路径与定向reward读数/运行stage样本 |
| D023与阶段条件 | 三处原公式保留，gate后不是新持续门角收入；原Stage3→4、release、Stage4→5/回臂语义未被B05接线改写 | 当前source与解析配置/实际事件读回；不用D021历史probe裁定 |
| 高度/B07 | 双侧高度.90–1.20，起点位置与联合yaw正确；读取本门新几何的闭门G，reset顺序不读上轮目标 | 真实样本、reset前后G与root/yaw、自然评估路径 |
| 时限/速度 | 30s、各stage步数与dt/结转正确，Stage0远近平滑速度及Stage4/5目标正确 | resolved值、实际时间/速度命令与边界样本 |
| B06与B03边界 | 加载正确MERGED H180/F45、三相机、arm reset；外壳visual/碰撞与中央包络状态正确，base15°保持 | 实际导入路径、joint/rig/collision读回与必要视图；不重开未批准的硬件标定/倾角优化 |
| B02边界 | 实体latch/mimic三DOF和现有handle路径保持，没有混入软件锁闩/新恢复方法 | topology、joint映射、source/配置读回 |
| 全链路 | obs/action形状dtype/device、sensor更新、reset/staged、奖励及PPO、保存/加载与自然评估入口一致 | 一次真实端到端接线运行与checkpoint读回；目标训练规模的资源/吞吐记录 |

所有必要项必须以匹配其主张的证据通过。无法证明的项明确记为未完成并给最小下一步；不能把STATIC提升为RUNTIME，不能靠调整成功指标、减少域或隐藏异常过验收。

## 4. B05重点验收：实际新资产和随机组合

### 4.1 资产生成与形状

检查实际生成并导入的USD/碰撞体，而非仅看Pro图或名义参数JSON。覆盖七族、LEFT/RIGHT、hook有无这些结构组合；可一批组织28种结构样本，不要求28次独立启动。查看F1/F2截面和roll、F3/F4轻曲率、F5直腹/过渡、F6渐变、圆滑return和rose是否在visual/collision中一致实现。X1应有独立可重建配置且训练采样数为0。

planner亲自查看worker提交的真实资产总览与代表性接近/闭合关键帧，并独立抽查资产/metadata/运行读回。检查整体凸包是否填掉内空隙、分段接缝是否产生假卡点、端帽/总长度是否按规格处理。0.25mm离散参考不是“只要填这个数字即通过”。

### 4.2 随机化及联合可用性

检查实际sampler和生成样本：七族1/7、hook1/2、h55–85、所有尺寸/roll/λ域，R/H/r_tip的条件构造及X1排除。报告真实频数与参数范围，区分设计概率和有限样本频数，不用可视化里的手工摆放代替生产sampler。

必须包含新域关键边界组合：h55与最大法向截面、F2最大支撑宽度/roll、λ下界、带return/rose、F3/F4曲杆和F6两端粗细等。B01质量/closer/摩擦、B04小/大M、左右侧与B05形状要有代表性联合覆盖，不能只逐项单独通过后宣称组合可用。采用有理由的分层/成对覆盖，不穷举连续域的所有笛卡尔积。

逐门保存的参数要能确定性重建真实几何，reset/staged/recovery不换门、不混旧缓存。边界失败应定位几何、接线、碰撞近似或物理参数原因，交planner决定修正；不能静默重抽困难门来保持表面成功。

### 4.3 PiPER、目标与接触

验证当前TCP85mm、真实夹爪mesh与行程、G/I/J/有向轴、proper镜像、FixedJoint及consumer offset。检查闭门G缓存、natural yaw、pregrasp、creation/reward/观察目标同源；保持actor输入维度，不新增族ID或参数真值答案。

在导入后的实际collision/contact设置下验证代表性全开接近和闭合，包括低h、全roll、return/rose组合。分别记录允许的指—杆接触与不希望的门板/rose/return碰撞、位置误差及关节响应；验证仍由arm_body7/8对同一door_handle形成正确接触语义。静态4.2mm平面余量、34.07mm截面和非空J不能替代这一步。

此处证明的是实现后的参考几何/接触操作路径可用，不要求未训练policy先达到任务高成功率，也不把短时参考动作当成已学会泛化。

## 5. planner反馈和批准

收到WORKER_READY并绑定任务后，planner先确认写入边界和有界验证所需的命令/GPU时段，worker继续自主实施；不要求每个日常实现细节等待审批。收到IMPLEMENTATION_READY后，planner先读完整报告/原始证据，按§3逐项核实，重点完成§4。可委托必要的只读specialist，但最终裁定由planner本人记录。

- `FIX_REQUIRED`：注明候选、具体问题、证据、期望行为、需要worker修改的边界及应补哪项证据。worker修正后提交新候选。
- `IMPLEMENTATION_ACCEPTED`：说明全部必要实现项已通过，仍需锁定正式启动配方时不得等同开训批准。
- `TRAIN_APPROVED`：由planner明确发出并保存，必须写候选/配置/资产、GPU0、精确命令、seed、env规模、batch预算、输出、ETA、checkpoint/eval和停止条件。

批准写入planner控制的运行批准记录并引用主决策编号，消息同步发worker。worker不能通过自己修改批准文件生成授权。修改仅明确无关的文档时可保留批准；训练相关变更须由planner判断是否失效/补验。

当前已有entry以`/home/baoquanc/anaconda3/envs/isaaclab/bin/python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v29_baseline`为起点。现有seed291/4096env/6000batches是拟提交默认；最终由planner根据当前完整配置与资源证据批准，不能从历史one-batch或v26_formal_launchable直接获得开训权。

有界验收仿真/接线任务由planner协调具体命令和GPU0时段；正式训练必须等TRAIN_APPROVED。GPU冲突不得抢占或杀其他任务。首轮批准不自动扩为GPU1第二seed、pull或N01/N02/B02消融。

## 6. 通信与可靠交接

**D066 Owner补充，覆盖planner、baseline worker和handle ablation worker：减少message频率，非重大progress/待决策不轻易发送。** 候选验收、需介入的实质异常、约定重大里程碑和最终交付才通知；一次合并事实、结论、证据及所需动作，不发送“收到/继续执行/仍在等待”式往返确认。普通实施进度、文件变更与不变状态只记本地。无需新动作的审阅存档即可，不另回“继续原计划”。

启动与首次初始化尽量合并；1000/3000/6000以整合报告为单位，不逐checkpoint发送。正常终止与已批准的紧接eval尽量合并交付；若底层已有原始terminal消息，人工不重复同一状态。实质失败或待决策事项及时通知，不为减少消息而延误。

当前已有共享文件事件监听的接收者，沿D062只通知一次，不再投递queue副本。纯记录更新不发布新消息指针、不触发反复唤醒；只有新指令、验收裁定或需要行动时通知。无该监听的接收者采用实际可用通道；queue不等于即时steer，已有同类待处理消息时合并，不继续堆叠。

2026-09-19只读核实：本机`/home/baoquanc/.local/bin/codex`及daemon为0.153.0；`turn/steer`是App Server协议，有活动turn及正确expectedTurnId才适用，空闲用turn/start。当前没有对应CLI子命令，也没有本任务可直接调用的发送工具，因此采用Owner已验证的`codex queue --thread UUID --message TEXT`通道。协议说明见[官方App Server文档](https://learn.chatgpt.com/docs/app-server)；本机实际接口优先，不新建旁路server。

双方启动和每次重要报告带实际thread ID、候选/运行ID、事件及绝对证据路径；通道返回的accepted/enqueued与任务执行/审批分开。优先已有turn接口，不可调用时queue；不同时向两通道重复轰炸。投递失败保存待发消息和错误，等待可恢复事件，不自动越权开训。

App读取进度时优先使用带host/cursor的wait_threads事件等待；不要反复read_thread重读无变化内容。运行超过30分钟使用独立tmux与现有run_supervisor、真实ETA、一次持久化逻辑等待。训练完成/失败由worker通过通信通道通知planner；本地pending文件本身不当作可靠任务唤醒。

## 7. 决策归属与持久化

| 决策方 | 记录位置 | 例子 |
|---|---|---|
| Owner | 主decision_log的明确Owner条目 | 本次离线自主协调授权、GPU0与最终planner批准要求 |
| Planner | 主decision_log的Planner条目＋验收/批准记录 | 方案裁定、要求修正、保留/失效某项证据、预算/配方和开训批准 |
| Worker | `a2_piper_base_v29_worker_decision_log.md`，V29-W编号 | 在批准参数内选用的实现方式、排除的具体故障、内部资源/工作分工 |

每条至少写时间、角色和任务ID、触发依据、决定、影响路径/行为、候选或运行、状态及对端通信引用。worker提议与planner批准分开记录；仅收到消息不算批准。不要把planner指导记成worker自行设计，也不要把工程选择冒写成Owner原话。

跨任务活动状态保存在`.ai/runtime/v29_baseline_team/STATE.json`及已有team_state/run_supervisor记录中；此处只保存当前绑定、候选和批准引用，不另造轮询框架。D032已绑定真实worker ID并开始事件驱动协调；当前有界验证授权不等于实现验收或正式训练批准。
