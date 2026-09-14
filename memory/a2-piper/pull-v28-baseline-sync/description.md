---
name: pull-v28-baseline-sync
status: pa_starting
scope: pull v28 C_T infrastructure sync, m5 G0 and three-scratch-seed opening baseline
last_verified: 2026-09-13
read_when:
  - 接续m5 pull v28或P2诊断封存
  - 解释主线共享C_T与pull专属训练合同的边界
source_of_truth:
  - scriptsFORhuman/pull_task/a2_piper_pull_v28_baseline_sync_plan_20260909.md
  - scriptsFORhuman/pull_task/a2_piper_pull_v28_decision_log_20260913.md
  - scriptsFORhuman/pull_v28/mainline_reference/20260913/SHARED_INPUTS_MANIFEST.json
related_entries:
  - pull-lr-full-stage
---

# Pull v28 baseline 同步

2026-09-13 Owner要求更新同步plan并交付m5 Codex team启动prompt。已依据m5真实source/旧runtime记录写明V28P-D001–D006；plan与必要主线输入由同目录manifest/receipt路由。P2已封存，新S1–S8已应用，当前G0因robot动态引用断裂在batch1前失败；两次修复额度已用完，P-A未启动。

P2三格T_S1/T_S2/C_S2的step10500训练child_returncode均0；18条natural已补完且归约，legacy receipts已按process-only收口；C_S1仍仅DECLARED。本轮先封存P2旧配方读数，再应用新共享代码，不补C_S1或另做资产门A矩阵，不触发D2后续重试。

共享项为MERGED/28body、140mm/38.76°、reset[0,.10,-.10,0,-.415,1.57]、D17、camera/tower/回位bundle、当前U3_F39_H140与证据/等待规则；base最终布局和真实光学/CAD仍归C_S/G2。pull保留Stage4 A–D、E4–E7/ready/tensile语义、1024env与无K基线。

本轮PA_S1/2/3全部scratch×6000，1500/3000/4500/6000双侧exact64；原三seed6000分母独立，历史opening另列。默认不跑warm，最多500诊断额度不替换PA_S3；不复制主线A284、D039主备/DEVCONF、强制G1或36500预算。本轮到opening closure，P3–P5另行立项。

PG7使用m5匹配旧asset对照和D37分层p50/p95/CAP/零摔倒/slope。无事件=null；接线/进程完成不等于opening、Teacher或hardware；失败不证明E_T几何无解。源端G0不替代pull运行证据。

当前证据级别：P2运行/诊断已完成，S1/S2已直接内容比对应用，PG4 CPU compose完成；G0运行中。P2本地commit9246460；无PA/push/硬件。

2026-09-13 01:31 HKT 输入交付完成：110份主线文件（62,519,259 bytes）与plan/决策/prompt/memory已在m5直接内容比对通过；现有A2_Base与主线内容一致、未替换。仅接收非活动参考输入，代码/配置/训练未应用；详见参考目录SHARED_INPUTS_RECEIPT.json。GPU1同路径为文档镜像，运行和参考输入事实以m5为准。

2026-09-13 21:11 HKT 执行接续：已再次确认18条缺失，GPU1/2/3的旧P2评估队列已启动；两个harness接线修复，PG7缺失输入已按原命令补齐。共享代码仅staging patch，未应用；G0/P-A/closure仍待完成。证据为INSPECTED与运行已启动，不是评估/实验PASS。

2026-09-13 22:29 HKT：P2全部18条完成；ready/clean-release均0。封存后应用MERGED/S2及语义patch，启动G0 contact_a1，Main持有GPU1–3。raw读数与process-only边界见pull_v7/P2_CLOSURE_20260913.md；真实G0失败须Owner处理。

2026-09-13 23:02:48 HKT最新终态：BLOCKED_G0_INFRA_REPAIR_LIMIT。contact_a3和PG7均有界PASS；flat env.robot引用断裂导致LSTM(0,256)，G0 PPO0batch，无checkpoint。第三次修复一行补丁仅提案未应用，等待Owner额外修复授权。PA全部NOT_RUN、k=null/3，不能判opening失败。资源及对应事件已收尾，P2 commit9246460/G0 commitcad573c；详见OPENING_CLOSURE_20260913.md和OWNER_REPAIR_REQUEST_20260913.md。

2026-09-14当前接续：Owner已授权额外一行修复并按原计划继续；补丁现已应用，G0新train attempt2、输出g0_resume_20260914/G0。P2/contact_a3/PG7证据复用；PA仍待G0。旧Owner门closure保留为历史，不再当作当前暂停令。

2026-09-14最新终态：env.robot引用修复已在G0 attempt2实证成功，LSTM输入133/138；完成5个学习迭代，但save_frequency250/last每50使5步smoke不写checkpoint，runner返回1且policy_readings_observed=true。按计划§8停止，不自动重跑。新提案OWNER_PROPOSED_SMOKE_SAVE_FIX_NOT_APPLIED.patch仅将smoke save_frequency设5，未应用；需Owner授权新5步attempt（累计将10≤32）。PA仍NOT_RUN，k=null/3。资源已释放，见OPENING_CLOSURE_20260914.md。

最新Owner指令2026-09-14：简单配置/保存/调度工程故障自主修复推进，不机械stop；真实G0物理门/合同/预算/硬件门保留。smoke save5补丁已应用、PA仍250，G0 attempt3独立目录g0_attempt3_20260914。此前累计5batch；旧blocked记录仅历史。

当前2026-09-14：G0_ACCEPTANCE_20260914.json=PULL_G0_PASS（有界工程接线），eval实际左右各64 VALID，G0累计10/32。无opening/release声明。原三PA格开始执行，Owner D013自主工程修复权限保留，真实科学门与预算不变。
