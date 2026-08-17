# DONE

- 2026-06-11 21:53 HKT - 初始化 runtime environment origin reference entry，记录 `isaaclab` env、Python `3.11.15`、Isaac Sim `5.1`、IsaacLab editable checkout、GPU/driver、Ubuntu version、`starlette` caveat、`AppLauncher` rule 与 README DoorPregrasp direct import smoke caveat。
- 2026-06-11 22:06 HKT - 记录 intentional `starlette` policy：local `starlette==0.45.3` 虽与 `isaaclab==0.54.4` metadata requirement `starlette==0.49.1` 冲突，但因 another-branch env 与 `SimulationApp` smoke pass，当前 prefer 保持 IsaacSim/FastAPI `<0.46` path，不默认建议升级。
- 2026-06-12 18:49 HKT - 补充 IsaacLab docs/source/runtime/tooling 背景：official docs 可通过 Context7 `/websites/isaac-sim_github_io_isaaclab_main` 查询，local source 在 `/home/baoquanc/workspace/IsaacLab`，机器上的 IsaacSim runtime 使用 conda env `isaaclab` 的 `/home/baoquanc/anaconda3/envs/isaaclab/bin/python`，当前 shell 没有 `rg`，搜索应使用 `find` + `grep` fallback。
