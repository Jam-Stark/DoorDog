# TODO

- G0、v27.0、Wave A已完成；CONF因NO_QUALIFIED_CANDIDATE未运行。
- Wave A冻结QUALITY_UNRESOLVED、RECIPE_A=C、CARRIER_A=C_S21 step3000；按第二个预授权本地commit点归档。
- Wave B先整合已验证的恢复候选修正，完成启用路径接线smoke与P02/P05 readback probe；再运行L三格与R三格、分层评估、RECIPE_B/Q_R；第三个预授权本地commit。
- Wave C 固定六格 scratch 与 K 对照跑满，按冻结规则结算。
- v27.5 最终确认、shadow estimator、manifest 第二版、closure、memory；第四个预授权本地 commit。
- 关闭本轮 writer/tmux/lease，向 Owner 请求 Teacher 与 G7 binding 裁决。

首次预授权本地 commit 已完成：`52933a3`（v27.0 完成且 Wave A G0 完成）。不得 push。
