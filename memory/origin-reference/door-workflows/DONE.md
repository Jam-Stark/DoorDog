# DONE

- 2026-06-11 21:53 HKT - 初始化 door workflows origin reference entry，索引 teacher PPO、student DAgger vision、eval、DoorPregrasp、train/eval entrypoints、HOMIE model paths 与 student-before-teacher checkpoint prerequisite。
- 2026-06-11 22:40 HKT - 记录 5-iteration teacher PPO smoke training passed：`+exp=wbmanip/door_open_homie_lstm`、`num_envs=1`、`algo.trl.num_total_batches=5` 与 small rollout/epoch/minibatch overrides 成功生成 `logs_rl/g1_open_door_homie/door_open_homie_lstm_smoke5-20260611_223318/model_step_000005.pt`；该结果验证 AppLauncher/Isaac Sim startup、DoorPregrasp env creation/reset、HOMIE model load、LAFAN-G1 reset data、PPO rollout/update/save 的 smoke chain，不声明 policy quality。
