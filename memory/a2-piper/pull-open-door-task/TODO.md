# TODO

- 2026-07-14 00:43 HKT - 用户拥有的 runtime checks：在 IsaacSim 中验证 pull scenario import 与 env construction；确认 `right`/`in` metadata；确认 robot reset 在 `+X` 侧且 yaw≈pi；检查 Piper pregrasp/grasp reachability、collision 与 handle contact；确认 hinge angle 正向增长代表 opening；实测 stage4 approach-side clearance `0.30` 是否足够；确认 stage5 沿 signed `-X` through direction 的 completion `> 1.5`。如需要训练结果，再执行 PPO training 和 eval；此前不得写 runtime PASS。
