# TODO

- G0、v27.0、Wave A已完成；CONF因NO_QUALIFIED_CANDIDATE未运行。
- Wave A冻结QUALITY_UNRESOLVED、RECIPE_A=C、CARRIER_A=C_S21 step3000；第二个预授权本地提交1fa2b1e已完成。
- Wave B两分支已关闭；L1两格实际root为*_r1，首轮actor加载前ListConfig缺陷已修复。
- R1被reader误判停于644，原step500数据经CPU修正读取有效；保持STOPPED，不恢复训练或替代endpoint。
- R0/R2已完成1500 endpoint；Q_R冻结UNRESOLVED（R1 endpoint缺失），不阻塞Wave C。
- L3000冻结DOMAIN_NOT_CONVERGED、RECIPE_B=current；完成Wave B第三个预授权本地commit。
- Wave C 固定六格 scratch 与 K 对照跑满，按冻结规则结算。
- v27.5 最终确认、manifest 第二版、closure、memory；第四个预授权本地 commit。
- 关闭本轮 writer/tmux/lease，向 Owner 请求 Teacher 与 G7 binding 裁决。

首次预授权本地 commit 已完成：`52933a3`（v27.0 完成且 Wave A G0 完成）。不得 push。
