# TODO

- 2026-07-03 16:16 HKT - 后续 door asset randomization 方案设计前，先决定 randomization scope：geometry/dynamics/material only、left/right handedness、还是真正 in/out push/pull mixed task；不同 scope 对 env/reward/obs/transition 的施工量不同。
- 2026-07-03 16:16 HKT - 若计划启用 `door_open_lr` 或 `door_open_io` randomization，必须先做 static plan + user approval，再实现并用 GUI/runtime smoke 验证 spawn pose、handle side、grasp target、stage transitions 与 reward direction。
- 2026-07-03 16:24 HKT - `door_open_lr=["left", "right"]` randomization 的推荐 gate：先把当前 `right-only` stage0-2 调到稳定，再做 mixed retrain；验证重点是 base staging 是否随 handle Y 镜像、Piper reachability、stage1 pregrasp route、stage2 close gate/contact 指标。
