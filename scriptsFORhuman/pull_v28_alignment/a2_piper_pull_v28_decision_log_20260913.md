# Pull v28 同步修订决策记录

日期：2026-09-13 HKT；修改：-codex planner；依据：-owner 要求更新 pull v28 新 baseline 同步 plan，并提供 m5 Codex team 启动 prompt。
当前状态：HANDOFF_READY_ALL_TRAINING_STOPPED。P2/G0已完成；D007–D015为真实历史，D016按Owner决定切换到新4096组三scratch，旧1024单列保留。本次不commit/push，D013继续有效。

## 初始交付时的输入与权限（历史）

本次已读取原planner同步方案、主线当前plan/决策/G0材料、m5 memory、P2合同/runner/evaluator、P_S2真实resolved配置与pull释放事件源码。m5于01:13–01:20 HKT核对的事实：P2三格child_returncode均0但18条natural lane未运行，legacy receipts仍RUNNING，C_S1仅DECLARED；新v28 plan/资产/执行链未落地。GPU0外部占用，GPU1–3可用情况只是快照。

本次施工为文档和必要的非活动参考输入交付；不实施D17/资产绑定/奖励，不跑P2/G0/训练，不处理外部进程，不commit/push。执行权限由Owner转交同目录启动prompt后在m5任务中成立。

## 本轮决定

| ID | 决定 | 旧规则与理由 | 影响范围 |
|---|---|---|---|
| V28P-D001 | 本轮闭环到P2诊断封存、pull G0、三seed opening重建与closure；P3–P5只回收立项 | 旧plan一方面称继续P3–P5，另一方面未冻结矩阵/预算；避免把后续议题当默认执行权。主线所有ADR不再无条件约束pull | plan §0/§7/§8；无新增训练预算 |
| V28P-D002 | C_T采用主线实际MERGED、140mm/38.76°、j5=-0.415、base并集、D17与当前rig；按清单直接交付/比对文件内容 | 替代旧U3_F45_B15、等待主线G0和摘要校验路径。主线G0已完成，但不代表pull运行通过 | S1–S4/S6；活动代码由执行team在P2封存后应用 |
| V28P-D003 | PG7采用D37命令/耦合轴p50、全轴p95、零摔倒与slope，使用m5匹配旧asset基线；proxy/null/归因按主线D38收窄 | 旧纯p50×1.15已过期。本次在pull新数据产生前固定口径；不复制主线事后修订流程/seed282假随机校准，不把学习失败判成几何无解 | PG7、S6、closure解释；不新增随机校准门 |
| V28P-D004 | pull保留Stage4 Wv(.5,.5,.25)设计先验、其余主线固定表；释放回位使用pull持久release latch，scale-.5；无K、固定reset | 旧“G0再用trace校准”容易变成无预算调参；真实source的release latch与clean-release单步脉冲不同。主线K是专属Wave C路由，m5真实基线curriculum=false/driver=null | S5、§3；不改pull事件/ready/Stage4语义 |
| V28P-D005 | PA_S1/PA_S2/PA_S3全部scratch，原三seed6000分母独立；可选500 warm只作诊断，不替换PA_S3或自动增warm长臂 | 旧可选warm替换第三scratch会破坏Q_PS分母。pull不做Teacher资格，不复制D039主备、A284和exact128。margin无E5时记NOT_OBSERVED/null | §6/§9；18000默认，18500封顶 |
| V28P-D006 | P2旧配方先结清，再应用共享代码；有限修复、一次匹配验证、v1.4持久等待；维护新entry并保留v7历史 | 旧P2 handoff仍要求C_S1/资产A/下一D2分支，已被本轮scope取代；不重装已同步workflow，不新增全面测试/兼容层或批量确认legacy事件 | §4/§5/§8–§10；不重跑旧训练 |

## 证据定位

- m5 P2：`logs_rl/a2_piper_pull_v7/p2_20260909/{T_S1,T_S2,C_S2}/runtime_result.json`、`model_step_010500.pt`；当时eval根为空，现已由D008完成18/18封存。
- m5 base resolved：`logs_rl/a2_piper_pull_v26_8_backbone/pull_v26_8_backbone_20260905_natural1_r2/wave2/train/P_S2/resolved_config.yaml`：1024、curriculum=false、driver=null、固定reset比例。
- m5 `gr00t/rl/envs/door/door_open_a2_pull.py:5947–5964`：`_a2_pull_v6_release_event`按OR持久记录，`_a2_pull_v6_clean_release_event`为单步clean_event，释放后subphase为D。
- 主线来源：参考目录manifest列出的asset/robot/rig/D17源码、camera/walk helper与G0材料。只复制明确输入，不包含训练checkpoint或凭据；现有A2_Base不替换。

## 验收与记录边界

文件接收/内容一致仅为交付证据；源码接线须执行team另证，pull opening须三seed natural结果。主线G0、旧进程exit0、legacy PASS、checkpoint存在均不能提升为pull新baseline已通过。初始交付时P2/pull G0/P-A尚未执行；此后真实完成记录见D007–D015，不以本历史说明重复运行。

## V28P-D007：执行接续、P2接线与PG7输入补齐

2026-09-13 21:11 HKT，依据本轮Owner启动授权，Main完成一次启动状态核对：三格旧训练child0、18条natural输出仍全部缺失，无新commit；GPU1/2/3空闲，GPU0两外部进程不处置。按v1.4组织Main、P2 runtime_qa、语义worker与独立pipeline worker，各路径单owner。实际宿主为Mac，通过m5-codex SSH执行，不能将Mac或GPU1镜像当作m5运行证据。

P2真实接线修复：eval显式eval_output_dir作为experiment_dir，防止写训练目录；T格诊断列表补D2项，C格原列表不变。三cell各六lane于同名tmux启动；不重训、不改D2/资产/门/分母。新共享代码先暂存patch，P2封存前不应用。旧lease仅接管资源，不确认legacy事件或升级科研验收。

已交付manifest缺PG7 commands/postures及trace replay输入，从GPU1主线只读补齐到mainline_reference/20260913/supplement_pg7，逐文件直接内容比对。commands仅重定向replay路径，保留env39/stage2,3/58steps原始物理指令；三姿态保持主线已批准值。详见补充RECEIPT.json。原110文件接收记录不改写，不复制训练checkpoint，不改变D37合同。

长等待：P2三receipt绝对wait_until_epoch=1789312071（2026-09-13 23:07:51 HKT），根据计划同类吞吐先估2h；使用同一supervisor waiter，完成/失败提前返回。当前宿主write_stdin工具schema上限300000ms，本轮通用工具指导要求避免长时间阻塞且进度可见，不能声称m5配置的24h transport已被本宿主加载；传输续接不作为业务轮询。

## V28P-D008：P2诊断封存与资源落盘

2026-09-13 22:29 HKT，18条缺失natural exact64全部child0，三个milestone各一次归约。10500 T格overshoot低于C格，但18条ready/clean-release/E6/E7均0；不成立旧配方释放能力，不推导几何无解。T_S1无C_S1匹配对照。见pull_v7/P2_CLOSURE_20260913.md及pull_v28/evidence/p2。只收口三条已完成旧训练receipt及三条新eval事件，legacy PASS注明仅进程/检查点；C_S1保持DECLARED。

根卷仅24GB空闲，而18条trace约30GB；未移动旧输出，仅将未启动10000/10500的12条lane父目录和新v28输出路由到用户自有SSD任务目录，canonical路径不变。P2完整保留，允许应用S1–S8进入G0。

## V28P-D009：G0探针退出可见性修复

contact_a1在64env初始化后child0但缺少contact_probe.json，按INVALID_OUTPUT_CONTRACT处理，不能当作PG PASS/FAIL。安装版SimulationApp.close直接退出framework，原finally掩盖了待抛异常/返回码；仅修复短命探针为先落盘原始traceback或结果、再明确exit1/0/2。第一次有限harness修复，a1保留，原底层异常不可从既有日志恢复。PG7匹配比较独立运行，门限不变。

contact_a2明确暴露natural配置注册冲突（policy构造前），第二次修复按现有P2 natural入口保留enable_staged_reset=true、比例[1,0,0,0,0,0]并关闭两bank。contact_a3全部有界门PASS，50步监测接触均0N，D17 upper/lower、动作/obs锚点与LEFT180°/RIGHT定义通过。冻结A2_Base实际驱动腿部，pull高层命令为0；release/E6未出现，不证明晚阶段回位。PG7 walk_a1三姿态D37均PASS、无tracking failure，X24仍OPEN。已开始256env×5batch PPO smoke，P-A仍未启动。

## V28P-D010：G0有限修复额度门与本轮终态

2026-09-13 23:02:48 HKT，G0 scratch256env×5batch在首次学习前失败，runner正确以缺失model_step_000005.pt返回1（Isaac子进程关闭路径返回0不能作成功）。只读证据：flat config失去原env.config.robot=${robot}引用，pre_process_config只更新root维度133/138，env副本仍0/0，真实日志为RunningMeanStd(0)、LSTM(0,256,num_layers=2)，随后CUDA/cuDNN flatten BAD_PARAM。不是已证明的驱动或硬件问题，也没有OOM证据。

contact_a1/a2的两次harness修复已消耗本G0格§8额度，不按子探针重新计数。第三次一行引用恢复补丁已形成OWNER_PROPOSED_FIX_NOT_APPLIED.patch，但未应用/运行；须Owner决定是否授权这一额外修复及原计划smoke/eval接续。未新增测试、fallback或兼容层，没有改变133/138合同、事件/ready、物理资产、奖励或门。

终态BLOCKED_G0_INFRA_REPAIR_LIMIT：P2共18/18；接触a3与三姿态PG7通过；PG4 CPU compose被真实运行发现的引用缺陷收窄，PG6 PPO/PG8全链未完成。G0已完成PPO batches0，PA三格NOT_RUN，k=null/3而非0/3，warm/P3–P5/Teacher/hardware/push均NOT_RUN。P2 commit9246460；G0终态/实现commitcad573c。PA endpoint节点未到达，不伪造该节点commit；最终closure另作本地commit。

已核对本任务tmux/waiter/训练进程均退出，GPU1/2/3无本任务compute，Main leases释放；保留无关tmux0与GPU0外部进程。只确认本任务已处理的事件，不改legacy C_S1或其他活动任务。后续P3–P5、恢复/感知/门域、push/pull合一均记为独立待立项；当前没有可转交的新baseline checkpoint。

## V28P-D011：Owner额外修复授权后接续

2026-09-14 Owner明确“授权，然后按照原计划继续”。应用既有一行补丁恢复env.config.robot=${robot}，保留全部旧失败attempt。使用全新g0_resume_20260914/G0输出与train_g0_attempt2 receipt执行原256env×5batch，随后full-checkpoint双侧natural与归约；不重跑P2/contact/PG7。通过G0才按原三seed各6000/24条natural继续，无warm/扩预算/改门/push。原9月13日closure是当时Owner门快照，当前状态为G0_RESUMED。

## V28P-D012：真实5batch完成后保存接线门

Owner额外授权的一行修复已实证成功：G0 attempt2的actor/critic输入133/138，5学习迭代全部完成，81920timesteps，迭代耗时18.97/17.63/16.68/17.20/16.82s。子进程exit0，runner因model_step_000005.pt缺失exit1，policy_readings_observed=true。

只读核对确认ModelSaveCallback的实际save_frequency=250，last.pt每50步；5步smoke不触发保存，没有异地检查点。按原§8“policy读数后的非零退出停该格…不自动重跑”暂停相关执行。已准备未应用补丁，仅smoke频率5、PA仍250；需Owner授权新的5batch attempt，届时G0累计10≤32。没有改变actor/reward/门/资产/预算，没有新fallback或测试。

G0累计5batch，PA三格均NOT_RUN、k=null/3；G0 natural及PG8尚无端到端证据。contact/PG7/P2未重复。资源/对应事件已收尾；保留原失败及旧closure快照。当前closure为OPENING_CLOSURE_20260914.md。

## V28P-D013：Owner明确工程故障自主推进权限

Owner于2026-09-14授权smoke保存频率修复并原计划继续，明确“这种简单外部因素就不要随意stop了…自主解决推进方案”。据此，配置引用、保存和调度等已定位工程接线故障，在合同/物理门/预算不变下自主修复，不再机械套用先前次数或post-policy wrapper失败停止；真实训练异常不得掩盖，真实G0门失败、合同改变、超预算、硬件/外部写入仍Owner门。全部attempt/预算如实记录，无fallback或重复全面审计。

已应用smoke save_frequency=5、PA保持250，启动新train_g0_attempt3，独立g0_attempt3_20260914目录。G0此前实际5batch，本次完成后累计10≤32；P2/contact/PG7不重跑。

## V28P-D014：G0真实eval暴露flat环境数与归约字段接线

attempt3 train成功保存step5，G0累计10batch。随后eval两侧child/wrapper0但各256terminal/record，而非64：root命令num_envs64未更新flat env/simulator字段。原256输出标INVALID，不裁剪、不当作科学失败。复用同checkpoint显式同步环境数到64，在新eval输出完成合同，无额外训练。另归约器直接读取不存在a2_v26_8_penalty_driver字段，改为真实source消费者的字段；不以缺失默认值掩盖，不改门。按D013自主处理工程接线，不重复Owner确认。

## V28P-D015：pull G0完成，进入原三格PA

修复后的eval64两侧actual completed/terminal/records均64，g0_eval_decision=G0_EVAL_WIRING_PASS；结合有效contact/PG7、实际133/138与256env×5batch完整checkpoint，PG1–PG8计划内有界接线完成。无晚阶段事件，G0结果不作opening判定。累计G0训练10≤32；旧256无效eval与所有失败保留。按Owner原授权直接启动PA_S1/2/3 scratch1024×6000，save250、四milestone双侧64，默认不warm、不P3–P5。

PA三train attempt1均启动后，submit-watch发现仅该CLI没有smoke参数，ETA表达式错误访问Namespace.smoke；修复条件分支，只在train分支读取smoke。三watcher随后成功启动，未重启任何训练/改变训练合同。代码改动留待下一任务commit节点，不扩展测试。

PA一次稳定启动证据：三格均已iteration29/1900544timesteps，1024env，ModelSaveCallback实际save_frequency250；无关TRL save_interval500不是保存消费者。吞吐约18.1s/iter、GPU各13.96GiB，估算首1500还约7.4h、6000约30h（尚未计并行eval）。GPU Foundation/GLFW初始化报文与成功G0相同，未据其措辞重启或判失败。按实际ETA等待真正watcher decision/失败/完成，不周期模型读log。

## V28P-D016：Owner决定三seed各4096，从scratch重建

2026-09-14 Owner明确m5 GPU0–3可用：PA_S1/2/3分别GPU1/2/3，每seed独立4096env、6000batches、save250；GPU0只承担本轮milestone评估队列，1500/3000/4500/6000双侧exact64逐lane执行。4096不是三格共享总数。side window暂用的D007已被占用，此决定改用D016，D007–D015保持原文。

新组`pull_v28_rebuild_4096_20260914`，checkpoint=null、full、auto_load_latest=false，从step0 scratch；所有实际num_envs路径同步4096。PPO仍H64、5epochs、4minibatches、lr1e-4，其余reward/asset/reset/事件/门不变。新预算三格各6000，共18000；旧1024的checkpoint、日志、completed/partial batches及GPU时长独立封存，不能进入新分母。

P2 18/18、contact_a3、PG7、G0累计10/32与PULL_G0_PASS直接复用，不重复。先记录再取消本轮旧三个train、三个watcher与旧辅助等待；保留所有原始输出。此次m5 GPU0实测有无关ForceControl-lightnav进程，队列等卡空闲，不终止无关任务、不把未来eval排队时间写成已测ETA。

首格正式前几个batch验证实际4096、显存和吞吐，再更新真实ETA；不另跑smoke/规模扫描/全面审计/测试，不回退1024。长任务独立tmux与既有supervisor/持久wait，进程完成和实验结论分开。D013的已定位工程故障自主修复权限保持；本次不新增commit/push，覆盖旧节点commit授权。详细进度与路径见`../pull_v28/evidence/pull_v28_rebuild_4096_20260914/TRANSITION.json`。

2026-09-14 19:17 HKT执行交接：旧PA1024最终1284/1280/1296，共3860 completed batches、252,968,960 transitions，编号checkpoint均1250；约22.36 GPU小时（supervisor取消前，退出尾段另记）。六个旧train/watch及辅助wait均停止，所有原始输出保留。4096 PA_S1 attempt1仅初始化约38秒，按Owner改为prompt交接的最新指令取消；0 completed batch/无checkpoint，S2/S3和评估队列未启动。因此没有4096吞吐或真实训练ETA。代码/配置已更新，GPU与写入leases已释放；下一步由m5 AI接手保留已取消初始化目录、使用新attempt从step0启动。本次未commit/push，未修改主线运行。
