# DONE

- 2026-06-29 15:56 HKT - 完成静态核查：`doorOpenIO` 在 origin G1 与 A2 door.py 中只赋值、写 metadata、读取到 env，不参与任何 hinge joint 构造、joint axis/sign/limit、reward routing 或 stage condition；hinge joint 对 in/out 门物理构造完全相同（axis Z、lower 0、upper 150、target -10）；`door_open_io` 在 origin/A2 env 中只用于 privileged obs stack；所有 left/right reward routing 只按 `door_open_lr`。`push_door_hinge` / `push_door_handle` / stage3→4 advance condition 对 in/out 门天然对称，维持 PASS baseline。`push_door_force` 维持 PASS disabled / TODO design，后续若启用必须做 door-frame 或 source-frame force projection。
