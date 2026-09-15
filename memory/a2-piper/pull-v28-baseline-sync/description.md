---
name: pull-v28-baseline-sync
status: paused_for_migration
scope: m5 pull v28 2048 three-seed opening rebuild
last_verified: 2026-09-15
read_when:
  - 接续m5 pull v28重建或解释旧1024消耗
source_of_truth:
  - scriptsFORhuman/pull_task/a2_piper_pull_v28_baseline_sync_plan_20260909.md
  - scriptsFORhuman/pull_task/a2_piper_pull_v28_decision_log_20260913.md
  - .ai/runtime/pull_v28_rebuild_2048_20260914/ACTIVE_RUN.json
  - scriptsFORhuman/pull_v28/evidence/pull_v28_rebuild_2048_20260914/REBOOT_RESUME_TRANSITION_20260915.json
related_entries:
  - pull-lr-full-stage
---

## 当前状态 — D019 / 2026-09-15 迁移暂停

Owner明确停止m5本轮pull，授权commit/push、GoogleDrive归档和新机器迁移脚本。m5无训练/评估/本轮wait，Main资源lease已释放，不再在此机器启动。D018 attempt2仅submit成功，三格实际在resume_config错误的raw substring计数检查处失败，0新增batch；queue只生成MISSING，0实际eval。恢复点仍是当前2048的1050/1400/1450完整checkpoint，非旧1024。

当前交付：保留2048/PPO/reward/reset/events/ready/Stage4合同；修复resume YAML解析与portable路径，提供migrate.py默认只prepare、--resume才在新机器启动attempt3。当前恢复包与历史原始日志/checkpoint包上传GoogleDrive `DoorDog/DoorDog-A2_Piper_pull_v0/pull_v28_migration_20260915`，manifest记录精确文件ID/大小/恢复路径，无hash。最终clone分支codex/a2-piper-pull-v0-20260803；具体commit与Drive链接以迁移receipt为准。

当前状态入口：`.ai/runtime/pull_v28_rebuild_2048_20260914/ACTIVE_RUN.json`。故障前完成3942，持久步数3900；迁移后余14100，必要重放42单列。Opening尚未形成，停止原因是Owner迁移要求。P2 18/18、G0累计10/32直接复用，不回4096/旧1024、不另跑smoke/扫描/warm/P3–P5。

## 先前交接记录（历史，不是当前执行指令）



# Pull v28 baseline 同步

2026-09-14 19:17 HKT当前为HANDOFF_READY_ALL_TRAINING_STOPPED：Owner要求由pull机器AI执行，当前任务只交付prompt。P2 18/18封存，G0=PULL_G0_PASS、累计10/32；不重跑P2/contact/PG7/G0。D007–D015保留真实远端历史，此次4096决定使用D016；D013工程配置/保存/调度自主修复权限保持。

旧PA1024三格最终1284/1280/1296 batches，共3860、252,968,960 transitions；编号checkpoint均1250，last.pt与原始日志保留。三个train、三个watch和旧wait已停止，Isaac残留已定向清理。约22.36 GPU小时在supervisor取消前消耗，退出尾段与partial batch另记，均排除新组终点分母。

新组pull_v28_rebuild_4096_20260914的配置与launcher已更新：每seed4096、6000/save250、H64/5epochs/4minibatches/lr1e-4；seed1/2/3分别GPU1/2/3、GPU0单队列做四milestone双侧exact64。reward/asset/reset/事件/ready/门未改。4096 PA_S1 attempt1只初始化38秒后按Owner最新要求取消，0 completed batch/无checkpoint；PA_S2/3与队列未启动，4096显存吞吐和ETA尚未建立。新组已取消初始化输出仍在原目录，接手者按prompt保留归档，再以新attempt从null/full/auto_load_latest=false启动。

当前资源lease已释放；GPU0无关ForceControl-lightnav任务不处置。无新commit/push，无主线v28运行改动。下一步只按重启prompt由m5 AI执行；RUNNING/UNASSESSED、自然评估有效性和opening结果分开，原三seed6000报告k/3。

## 历史执行记录（保留原文，不代表当前状态）

2026-09-13 01:31 HKT 输入交付完成：110份主线文件（62,519,259 bytes）与plan/决策/prompt/memory已在m5直接内容比对通过；现有A2_Base与主线内容一致、未替换。仅接收非活动参考输入，代码/配置/训练未应用；详见参考目录SHARED_INPUTS_RECEIPT.json。GPU1同路径为文档镜像，运行和参考输入事实以m5为准。

2026-09-13 21:11 HKT 执行接续：已再次确认18条缺失，GPU1/2/3的旧P2评估队列已启动；两个harness接线修复，PG7缺失输入已按原命令补齐。共享代码仅staging patch，未应用；G0/P-A/closure仍待完成。证据为INSPECTED与运行已启动，不是评估/实验PASS。

2026-09-13 22:29 HKT：P2全部18条完成；ready/clean-release均0。封存后应用MERGED/S2及语义patch，启动G0 contact_a1，Main持有GPU1–3。raw读数与process-only边界见pull_v7/P2_CLOSURE_20260913.md；真实G0失败须Owner处理。

2026-09-13 23:02:48 HKT最新终态：BLOCKED_G0_INFRA_REPAIR_LIMIT。contact_a3和PG7均有界PASS；flat env.robot引用断裂导致LSTM(0,256)，G0 PPO0batch，无checkpoint。第三次修复一行补丁仅提案未应用，等待Owner额外修复授权。PA全部NOT_RUN、k=null/3，不能判opening失败。资源及对应事件已收尾，P2 commit9246460/G0 commitcad573c；详见OPENING_CLOSURE_20260913.md和OWNER_REPAIR_REQUEST_20260913.md。

2026-09-14当前接续：Owner已授权额外一行修复并按原计划继续；补丁现已应用，G0新train attempt2、输出g0_resume_20260914/G0。P2/contact_a3/PG7证据复用；PA仍待G0。旧Owner门closure保留为历史，不再当作当前暂停令。

2026-09-14最新终态：env.robot引用修复已在G0 attempt2实证成功，LSTM输入133/138；完成5个学习迭代，但save_frequency250/last每50使5步smoke不写checkpoint，runner返回1且policy_readings_observed=true。按计划§8停止，不自动重跑。新提案OWNER_PROPOSED_SMOKE_SAVE_FIX_NOT_APPLIED.patch仅将smoke save_frequency设5，未应用；需Owner授权新5步attempt（累计将10≤32）。PA仍NOT_RUN，k=null/3。资源已释放，见OPENING_CLOSURE_20260914.md。

最新Owner指令2026-09-14：简单配置/保存/调度工程故障自主修复推进，不机械stop；真实G0物理门/合同/预算/硬件门保留。smoke save5补丁已应用、PA仍250，G0 attempt3独立目录g0_attempt3_20260914。此前累计5batch；旧blocked记录仅历史。

当前2026-09-14：G0_ACCEPTANCE_20260914.json=PULL_G0_PASS（有界工程接线），eval实际左右各64 VALID，G0累计10/32。无opening/release声明。原三PA格开始执行，Owner D013自主工程修复权限保留，真实科学门与预算不变。

PA_S1/2/3 train/watch attempt1已全部启动，默认canonical输出根在用户SSD；三卡对应seed1/2/3，scratch1024×6000，save250。Main持lease，等待一次启动吞吐记录后进入真实ETA持久等待。

## D019迁移交付完成（2026-09-15）

当前合法终态是m5暂停且迁移交付完成，不是opening closure完成。当前code已推送，三整包GoogleDrive云端ID及精确bytes已核实，恢复入口见scriptsFORhuman/pull_v28/migration_manifest.json、migrate.py及NEW_MACHINE_AI_PROMPT_20260915.md。只由新机器按原2048合同resume同seed1050/1400/1450到6000和补24lane；m5不得续训。
