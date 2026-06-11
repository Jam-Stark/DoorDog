# DONE

- 2026-06-11 21:53 HKT - 初始化 runtime environment origin reference entry，记录 `isaaclab` env、Python `3.11.15`、Isaac Sim `5.1`、IsaacLab editable checkout、GPU/driver、Ubuntu version、`starlette` caveat、`AppLauncher` rule 与 README DoorPregrasp direct import smoke caveat。
- 2026-06-11 22:06 HKT - 记录 intentional `starlette` policy：local `starlette==0.45.3` 虽与 `isaaclab==0.54.4` metadata requirement `starlette==0.49.1` 冲突，但因 another-branch env 与 `SimulationApp` smoke pass，当前 prefer 保持 IsaacSim/FastAPI `<0.46` path，不默认建议升级。
