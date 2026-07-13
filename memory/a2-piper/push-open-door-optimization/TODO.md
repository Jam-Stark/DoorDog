# TODO

- 2026-07-13 17:36 HKT - 运行已确定的 `base_v10` A/B/C/D cumulative ablation，并在四组 step1000 完成后执行 matched eval。A=`base_v9_B` extra-training control；B=A+hold-reward rebalance；C=B+gripper Kp/Kd `160/6`；D=C+stage3 base unlocked。四组共同使用 `base_v9_B` ckpt1000 `policy_only`、threshold `0.25`、seed0、1000 batches、2 ranks × 2048 env/rank。启动必须为四个独立 foreground terminal、不同 port、约 10 秒 stagger；禁止 `setsid`/detached background wrapper。仍不恢复 `base_v9` oracle/O±/matched-clean diagnostics。
