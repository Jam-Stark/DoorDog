# TODO

- 2026-07-17 20:05 HKT - 启动`base_v13_1_main` formal training：A3000 `policy_only` warm-start、4 ranks × `1024 env/rank`、global batch `4096`、`2000` batches、save every`250`。每250 batch监控release ratio、stage4/5 activity、hold/hinge income、grasp/redline telemetry；对checkpoint执行matched 16-env scalar/trace eval，必要时执行2-env×3-camera render。formal policy-quality结论只能来自后续formal training/eval；r3 `4×64×50` smoke不是该证据，Kit natural exit仍unverified。`v13_1_noM13`与其他后续ablation保持conditional。
