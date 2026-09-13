你是m5上的Codex Main，工作目录为 /home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0，分支 codex/a2-piper-pull-v0-20260803。

我授权你组织最少必要team，独立完成本轮 pull v28：P2诊断封存→pull G0→三scratch seed opening重建→closure。不要止于计划或启动训练；命中下面保留的Owner门才暂停相关工作。

先按本机AGENTS/v1.4入口使用memory，读取：
/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/scriptsFORhuman/pull_task/a2_piper_pull_v28_baseline_sync_plan_20260909.md
/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/scriptsFORhuman/pull_task/a2_piper_pull_v28_decision_log_20260913.md
/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/memory/a2-piper/pull-v28-baseline-sync/
参考输入从 scriptsFORhuman/pull_v28/mainline_reference/20260913/ 的manifest和receipt读取。目录是参考输入，尚未应用到活动源码；不要直接整树覆盖。

当前交接：P2三格T_S1/T_S2/C_S2的10500训练已结束且child returncode为0，18条natural评估尚缺；三份legacy receipt仍RUNNING。先看是否已有后来结果并接续，不重复训练/评估。GPU0有外部进程，仅用GPU1/2/3。m5是普通checkout，已有v1.4；不套用主线linked-worktree hook安装，不重装工作流。没有rg时用Python/grep即可。

一、团队与权限
Main管理scope、write set、GPU、Git和整合；按任务用语义worker、普通worker、runtime_qa和窄检索角色，遵循本机模型路由，子agent最高high、fork_turns="none"，不复制Main历史或默认排审阅队列。一条路径/资源一个owner；保留已有未提交改动。
授权必要的共享项函数级移植、pull_v28配置/runner/watcher/reducer/readout/receipt实现，以及合同不变的真实接线修复。语义复杂处直接给语义worker，先完成功能再做一次相匹配的窄验证；不新增永久测试套件、兼容层、fallback、假数据或摘要校验文件。
授权本轮GPU1–3的P2剩余18条exact64、G0计划内小运行、PA_S1/2/3各6000及24条milestone exact64。默认不做warm probe，三格始终scratch；500可选额度只有我另行要求才启用。总训练不超过18500，G0 smoke不超过计划32batch额度。P3–P5/Teacher资格/额外长臂不在本轮。
本地commit预授权：P2 closure后、pull G0后、P-A endpoint后、最终closure后，已完成节点不重复，仅Main提交本任务文件；不push，不merge主线，不处理外部进程。

二、先封存P2
保持P2旧asset、旧D2/source与原natural合同；补T_S1/T_S2/C_S2的9500/10000/10500双侧exact64，使用真实eval_p2_cell.sh/analyze_p2.py入口。只修影响实际执行的harness缺陷，不改D2/门/样本数。不补C_S1、不重跑训练、不触发旧v7下一D2或独立资产门A。
真实处理完缺失评估与结果后收口对应receipt，写诊断closure。P2结果不路由v28；旧legacy PASS不是科研验收。完成P2封存后才把D17、robot/bundle等共享改动应用到活动路径，避免污染旧读数；期间可准备独立的新调度文件。

三、应用S1–S8并完成pull G0
从交付清单采用MERGED资产、a2_piper_vpiper.yaml、140mm/38.76° rig、reset [0,.10,-.10,0,-.415,1.57]、D17目标夹紧。资产/YAML直接内容比对，不在m5重生成资产；A2_Base保留m5原policy。base单/双及真实光学仍归C_S/G2。
共享base/env已分叉，只移植需要的函数/语义，不整文件覆盖。pull Stage4 Wv(.5,.5,.25)、持久release latch回位门控等按plan §3；所有pull事件、ready、Stage4 A–D、E4–E7保持。不复制主线K、A284、强制G1、D039主备/DEVCONF或36500预算。
配置以P_S2真实resolved合同为输入，明确1024/6000、checkpoint=null/full、固定staged reset、curriculum=false/driver=null。实现实际可运行的pull_v28调度链，active cell milestone独立推进，eval输出不污染训练目录。
合并执行PG1–PG8的必要证明：一次compose/相关CPU检查，256env×5batch及配套小评估，按名body/joint/contact读回、镜像与实际目标限位；PG7在m5同命令/同姿态的新旧asset上使用已批准D37分层p50/p95/CAP、零摔倒与slope。主线G0只作输入依据，不替代m5证据；不复制seed282假随机校准。

四、Wave P-A与closure
G0通过后直接启动PA_S1/2/3，均scratch，1024env、6000batch、save250，1500/3000/4500/6000各双侧exact64自然评估。按plan以6000原三seed报告精确k/3及opening标签，历史过门checkpoint另列，不拿最好时点替代endpoint。margin/overshoot与CAMERA独立报告；无E5或其他事件保持NOT_OBSERVED/null，不能填0冒充已解决。
按合同完成opening/margin readout、原始结果、S1–S8应用记录、checkpoint清单和closure，不做exact128 Teacher资格或自动继续P3–P5。失败只陈述本配方/预算未建立，tower接触只能提出待区分解释，不证明几何无解。

五、长任务与停止
解释器用 /home/baoquanc/anaconda3/envs/isaaclab/bin/python；具体GPU绑定、CUDA可见性、输出与eval参数从m5真实入口确认。launch读取实际GPU余量；P-A评估按plan放置，显存不够则顺延，不挤占外部或18GB级训练格。
超过30分钟用命名tmux与现有supervisor；一次启动检查后依据真实ETA登记绝对截止，恢复同一个安静waiter，完成/失败/取消/实际决策点提前返回。不每30分钟唤醒模型，不派agent反复看日志，不用日志静默判死锁。旧任务不迁移，未完成指定后续处理的事件不确认；process和acceptance分开。
policy读数前的infra失败最多自主修复2次/格，新attempt且合同不变；读数后的非零退出停该格、其余继续，不自动重跑；reducer INVALID不自动杀训练。
PG接触/映射/步行门失败、改变事件/ready/stage/reward/门值、超预算、改变C_T/A2_Base、硬件/Teacher绑定/push等交我裁决。已授权阶段转换通知后继续，不逐milestone等批准。

完成时同步plan实际状态、决策日志、memory三文件及主线同步依赖，报告证据等级、changed paths、未运行项、活跃进程/tmux/writer/资源。closure成功或失败都回收P3–P5与恢复/传感/门域议题，明确后续立项而不自动开新实验。保留旧checkpoint、日志和FAIL；本任务完成的资源及时释放。
