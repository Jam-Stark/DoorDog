# TODO

- 2026-07-16 22:39 HKT - `v13_A` main 与 `v13_B` gate-only 已完成 code/config/review 及 4-rank concurrent smoke；下一步在两个独立 foreground terminal 按 GPU0–3/port29513 与 GPU4–7/port29514 启动正式训练，每 rank `num_envs=1024`（每组 global batch4096），A 到 global step3000、B 到1500。约10秒 stagger 后并行，监控 iter250/500/1000 的 stage2→3、stage3/4 stability、hold-and-drive、handle hard-limit、coasting 与 over-force，随后做 matched seed0/16-env/first-episode eval。`UNLATCH_NORM=0.6rad` 与 friction/latch physical calibration 仅在 A hinge/hold-and-drive 持续近零时触发；M7/M8/v13_C/v13_D 仍保持 conditional。
