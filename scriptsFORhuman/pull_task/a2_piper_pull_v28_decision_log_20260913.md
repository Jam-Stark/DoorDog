# Pull v28 同步修订决策记录

日期：2026-09-13 HKT；修改：-codex planner；依据：-owner 要求更新 pull v28 新 baseline 同步 plan，并提供 m5 Codex team 启动 prompt。
状态：方案已修订；m5活动源码/配置与训练未执行。输入交付状态以SHARED_INPUTS_RECEIPT为准。

## 输入与权限

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

- m5 P2：`logs_rl/a2_piper_pull_v7/p2_20260909/{T_S1,T_S2,C_S2}/runtime_result.json`、`model_step_010500.pt`；eval根为空。
- m5 base resolved：`logs_rl/a2_piper_pull_v26_8_backbone/pull_v26_8_backbone_20260905_natural1_r2/wave2/train/P_S2/resolved_config.yaml`：1024、curriculum=false、driver=null、固定reset比例。
- m5 `gr00t/rl/envs/door/door_open_a2_pull.py:5947–5964`：`_a2_pull_v6_release_event`按OR持久记录，`_a2_pull_v6_clean_release_event`为单步clean_event，释放后subphase为D。
- 主线来源：参考目录manifest列出的asset/robot/rig/D17源码、camera/walk helper与G0材料。只复制明确输入，不包含训练checkpoint或凭据；现有A2_Base不替换。

## 验收与记录边界

文件接收/内容一致仅为交付证据；源码接线须执行team另证，pull opening须三seed natural结果。主线G0、旧进程exit0、legacy PASS、checkpoint存在均不能提升为pull新baseline已通过。P2/pull G0/P-A都尚未执行，不能在本次修改中关闭这些TODO。

## V28P-D007：执行接续、P2接线与PG7输入补齐

2026-09-13 21:11 HKT，依据本轮Owner启动授权，Main完成一次启动状态核对：三格旧训练child0、18条natural输出仍全部缺失，无新commit；GPU1/2/3空闲，GPU0两外部进程不处置。按v1.4组织Main、P2 runtime_qa、语义worker与独立pipeline worker，各路径单owner。实际宿主为Mac，通过m5-codex SSH执行，不能将Mac或GPU1镜像当作m5运行证据。

P2真实接线修复：eval显式eval_output_dir作为experiment_dir，防止写训练目录；T格诊断列表补D2项，C格原列表不变。三cell各六lane于同名tmux启动；不重训、不改D2/资产/门/分母。新共享代码先暂存patch，P2封存前不应用。旧lease仅接管资源，不确认legacy事件或升级科研验收。

已交付manifest缺PG7 commands/postures及trace replay输入，从GPU1主线只读补齐到mainline_reference/20260913/supplement_pg7，逐文件直接内容比对。commands仅重定向replay路径，保留env39/stage2,3/58steps原始物理指令；三姿态保持主线已批准值。详见补充RECEIPT.json。原110文件接收记录不改写，不复制训练checkpoint，不改变D37合同。

长等待：P2三receipt绝对wait_until_epoch=1789312071（2026-09-13 23:07:51 HKT），根据计划同类吞吐先估2h；使用同一supervisor waiter，完成/失败提前返回。当前宿主write_stdin工具schema上限300000ms，并受本轮developer单次等待≤60s约束，不能声称m5配置的24h transport已被本宿主加载；传输续接不作为业务轮询。

## V28P-D008：P2诊断封存与资源落盘

2026-09-13 22:29 HKT，18条缺失natural exact64全部child0，三个milestone各一次归约。10500 T格overshoot低于C格，但18条ready/clean-release/E6/E7均0；不成立旧配方释放能力，不推导几何无解。T_S1无C_S1匹配对照。见pull_v7/P2_CLOSURE_20260913.md及pull_v28/evidence/p2。只收口三条已完成旧训练receipt及三条新eval事件，legacy PASS注明仅进程/检查点；C_S1保持DECLARED。

根卷仅24GB空闲，而18条trace约30GB；未移动旧输出，仅将未启动10000/10500的12条lane父目录和新v28输出路由到用户自有SSD任务目录，canonical路径不变。P2完整保留，允许应用S1–S8进入G0。
