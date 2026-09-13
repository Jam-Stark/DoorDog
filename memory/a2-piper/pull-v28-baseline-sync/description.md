---
name: pull-v28-baseline-sync
status: executing_p2_evaluation
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

2026-09-13 Owner要求更新同步plan并交付m5 Codex team启动prompt。已依据m5真实source/旧runtime记录写明V28P-D001–D006；plan与必要主线输入由同目录manifest/receipt路由。接收不等于集成，当前活动代码、pull G0与P-A仍待执行。

当前P2三格T_S1/T_S2/C_S2的step10500训练child_returncode均0，18条natural尚缺，legacy receipts仍RUNNING；C_S1仅DECLARED。本轮先封存P2旧配方读数，再应用新共享代码，不补C_S1或另做资产门A矩阵，不触发D2后续重试。

共享项为MERGED/28body、140mm/38.76°、reset[0,.10,-.10,0,-.415,1.57]、D17、camera/tower/回位bundle、当前U3_F39_H140与证据/等待规则；base最终布局和真实光学/CAD仍归C_S/G2。pull保留Stage4 A–D、E4–E7/ready/tensile语义、1024env与无K基线。

本轮PA_S1/2/3全部scratch×6000，1500/3000/4500/6000双侧exact64；原三seed6000分母独立，历史opening另列。默认不跑warm，最多500诊断额度不替换PA_S3；不复制主线A284、D039主备/DEVCONF、强制G1或36500预算。本轮到opening closure，P3–P5另行立项。

PG7使用m5匹配旧asset对照和D37分层p50/p95/CAP/零摔倒/slope。无事件=null；接线/进程完成不等于opening、Teacher或hardware；失败不证明E_T几何无解。源端G0不替代pull运行证据。

证据级别：INSPECTED（已有source与runtime记录）及文档/输入交付；没有本次训练/评估、代码应用、commit/push或硬件。

2026-09-13 01:31 HKT 输入交付完成：110份主线文件（62,519,259 bytes）与plan/决策/prompt/memory已在m5直接内容比对通过；现有A2_Base与主线内容一致、未替换。仅接收非活动参考输入，代码/配置/训练未应用；详见参考目录SHARED_INPUTS_RECEIPT.json。GPU1同路径为文档镜像，运行和参考输入事实以m5为准。

2026-09-13 21:11 HKT 执行接续：已再次确认18条缺失，GPU1/2/3的旧P2评估队列已启动；两个harness接线修复，PG7缺失输入已按原命令补齐。共享代码仅staging patch，未应用；G0/P-A/closure仍待完成。证据为INSPECTED与运行已启动，不是评估/实验PASS。
