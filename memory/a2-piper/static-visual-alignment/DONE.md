# DONE

- 2026-06-12 19:48 HKT - 新建 static visual alignment memory entry，记录 full Isaac Sim GUI experience 命令规范、preview script 调整边界、placement corners 用法与 reward tuning 可视化用途。
- 2026-06-22 23:53 HKT - 补充 WebRTC/training 可视化边界：static import/full GUI preview 与 stage0-2 PPO training livestream 是两条 workflow，训练可视化建议使用独立 single-process visual run，不直接叠加到 multi-rank long training。
- 2026-06-23 00:24 HKT - 清理旧 visual/WebRTC 残留进程，保留 4-rank long training 组 `820453/820562-820565`。被清理的进程包括 orphan single-process visual run `843774`、其 `wandb` 子进程 `844546/844587`、旧 livestream log tail `839708` 和 orphan Omni telemetry `809435`；清理后 `nvidia-smi` 只显示 long training worker。
- 2026-06-23 13:41 HKT - 完成 xpra display validation：`xpra :100` live session 与 HTML endpoint `14500` 可用，但 `DISPLAY=:100 glxinfo -B` 显示 Xvfb/llvmpipe software renderer；该 display 不适合作为 Isaac Sim full GUI/Vulkan 调试目标。
