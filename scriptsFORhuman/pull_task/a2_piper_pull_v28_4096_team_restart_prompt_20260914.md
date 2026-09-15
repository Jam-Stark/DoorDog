你是m5上的Codex Main，执行仓库：
/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0

我授权你组织最少必要team，接续V28P-D016的pull v28 4096重建与计划内评估，直到三seed各6000及opening closure。先按本机AGENTS/v1.4使用memory，读取以下当前入口：
- scriptsFORhuman/pull_task/a2_piper_pull_v28_baseline_sync_plan_20260909.md
- scriptsFORhuman/pull_task/a2_piper_pull_v28_decision_log_20260913.md
- memory/a2-piper/pull-v28-baseline-sync/{description,TODO,DONE}.md
- scriptsFORhuman/pull_v28/evidence/pull_v28_rebuild_4096_20260914/TRANSITION.json
- .ai/runtime/pull_v28_rebuild_4096_20260914/ACTIVE_RUN.json

以m5当前source、resolved config、receipt、实际进程为准。先检查新组是否已启动：若三个4096进程和GPU0队列已在运行，直接接续同一组和既有等待，不执行第二轮重启。不要按旧启动说明重复P2/G0或恢复旧1024。

已确认的历史：P2 18/18自然exact64封存；pull G0=PULL_G0_PASS，累计10/32，contact_a3与PG7证据保留。旧PA1024最终completed batches为PA_S1=1284、PA_S2=1280、PA_S3=1296，共3860；各自编号checkpoint均到model_step_001250.pt，last.pt及所有日志保留。旧三个train、三个watcher和辅助等待已取消；Isaac残留进程已定向清理。旧输出组pull_v28_baseline_sync_20260913禁止自动续训，旧消耗/结果不进入新4096终点分母。此处数值以TRANSITION的最终记录为准，可能中断的partial batch已另注。

当前交接状态（2026-09-14 19:17 HKT）：HANDOFF_READY_ALL_TRAINING_STOPPED。上一个任务已按Owner最新要求停止执行、只交付本prompt。4096 PA_S1 attempt1曾在19:15:12提交，19:15:50在场景初始化阶段取消；无completed learning batch、无checkpoint。PA_S2/3与GPU0队列从未提交，4096吞吐/ETA尚未测得。所有原始文件保留，不把该次初始化叫作成功的4096训练。

本消息授权你在m5完成后续实际启动。先确认当前仍为上述状态；将新组内已取消的PA_S1初始化目录保留到同组独立cancelled目录，记录原路径与归档位置，不能覆盖或删除证据。canonical PA_S1重新空出后，三格统一使用新的attempt2（S2/S3此前无attempt1），queue也使用--attempt 2，以对应这三份receipt；仍全部null scratch，不从任何旧checkpoint恢复。根组名称不变。若你接手时已有后来正式运行，则按其真实receipt继续，不重复启动。

新组固定合同：
- group=pull_v28_rebuild_4096_20260914；train/eval canonical分别在logs_rl/a2_piper_pull_v28/和logs_eval/a2_piper_pull_v28/下同名目录，实际存储沿既有SSD路径。
- PA_S1/seed1→GPU1、PA_S2/seed2→GPU2、PA_S3/seed3→GPU3。每个独立策略4096env、6000batches、save250，checkpoint=null、checkpoint_load_mode=full、auto_load_latest=false，从step0 scratch；不能加载旧1024 checkpoint。
- GPU0一个串行milestone评估队列，1500/3000/4500/6000各左右exact64 natural，共24条lane；按已就绪checkpoint推进，任一时刻只跑一条lane。GPU0若仍被无关ForceControl-lightnav任务占用就排队，不能终止该任务或挤占训练卡。
- 新训练预算仅18000 batches；每seed H64，5 PPO epochs、4 minibatches、lr1e-4保持。reward/asset/reset、Stage4 A–D、ready/event、D17、actor/critic、natural分母及opening门均不变；无warm/规模扫描/额外测试/Teacher/P3–P5。
- 先启动PA_S1正式训练，用前几个batch完成唯一一次规模核对：记录四处实际num_envs、4096×64每batch transitions、显存、吞吐与首1500/6000 ETA，然后启动PA_S2/3并确认配置。首格这些batch计入6000，不另开smoke、规模扫描或测试，不自动降回1024。

使用现有scriptsFORhuman/pull_v28/pipeline.py、config_materialize.py、pull_v28_common.yaml和run_supervisor；默认root为canonical新组、训练GPU由cell固定，eval_queue固定GPU0。启动示意（按上述清理已取消初始化输出后）：
/home/baoquanc/anaconda3/envs/isaaclab/bin/python scriptsFORhuman/pull_v28/pipeline.py submit-train --cell PA_S1 --attempt 2 --expected-seconds 3600 --eta-source '4096 first formal startup decision; replace after measured batches'
得到首格吞吐后，同入口submit-train提交PA_S2、PA_S3，--attempt 2，expected-seconds与eta-source用实测结果；再submit-eval-queue --attempt 2并持久等待。首格原3600仅启动决策窗口，不是6000训练ETA，也不会自动kill。已有输出不能重用成新scratch attempt。Main持有scope、写入、GPU及整合权，子agent按本机角色最少委托，不复制长历史或组织全面审计。

D013继续有效：已定位且合同/物理门/预算不变的配置、保存、调度工程故障自主修复并记录；不机械套用旧两次限制或post-policy wrapper非零就停。真实训练异常显式报告，不能用fallback、假数据、clipping或规模/配方更改掩盖。实际科学门失败、合同改变、超预算、硬件/外部资源决定交Owner。INVALID只影响对应评估，不自动杀训练；其他就绪评估继续。

超过30分钟使用独立命名tmux和既有supervisor，按实测ETA登记绝对wait_until并恢复同一个安静waiter；完成/失败/取消/真实决策点提前返回，不频繁唤醒模型看日志。保留原始失败与checkpoint，不以进程exit0宣称opening通过。6000三原seed双侧门报告精确k/3；缺失/INVALID不填0，无E5 margin为NOT_OBSERVED/null，历史最好checkpoint另列。

本次明确不新增commit/push，覆盖旧启动prompt的节点commit预授权。只操作m5本轮pull，不动主线正在运行的v28、不重装workflow。完成closure时同步真实plan状态、D016后续记录、memory、readout及资源收尾；交接时报告仍活跃的训练/队列/tmux和实际ETA。
