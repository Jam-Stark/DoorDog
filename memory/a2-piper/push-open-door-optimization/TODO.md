# TODO

- 2026-07-13 17:41 HKT - 从随机初始化分别长训 `base_v10` A/B/C/D，并在四组 step1000 完成后执行 matched eval。A=v9-B-config scratch control；B=A+hold-reward rebalance；C=B+gripper Kp/Kd `160/6`；D=C+stage3 base unlocked。四组共同使用 `checkpoint=null`、`auto_load_latest=false`、threshold `0.25`、seed0、1000 batches、2 ranks × 2048 env/rank；不得加载 v9/v8 actor。启动必须为四个独立 foreground terminal、不同 port、约 10 秒 stagger；禁止 `setsid`/detached background wrapper。仍不恢复 `base_v9` oracle/O±/matched-clean diagnostics。
