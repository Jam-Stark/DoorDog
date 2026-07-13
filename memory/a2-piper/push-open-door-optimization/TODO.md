# TODO

- 2026-07-13 16:37 HKT - 提出并审批 `base_v10` RL optimization/retraining plan：限定最小 A/B factors，说明每个 factor 要改变的 learnable behavior，定义 bilateral hold、door progress、rebound、workspace、doorframe/base stability 等 primary/guardrail metrics，并保持 matched seed/checkpoint/budget/env 与 scalar/render contract。任何 `.py/.yaml/config` 修改或长训练都需先获得用户明确 approval；不再默认追加 `base_v9` oracle、static clamp、O-/O0/O+、matched-clean 等 scripted diagnostic。
