---
name: runtime-environment
scope: local runtime environment, Isaac Sim, IsaacLab, and known compatibility caveats
status: active
last_updated: 2026-06-12 18:49 HKT
owned_paths:
  - memory/origin-reference/runtime-environment/description.md
  - memory/origin-reference/runtime-environment/TODO.md
  - memory/origin-reference/runtime-environment/DONE.md
  - memory/origin-reference/runtime-environment/references/isaaclab-docs-index.md
read_when:
  - 运行 train/eval/smoke 前需要确认 Isaac Sim 或 IsaacLab 环境
  - 遇到 AppLauncher、dependency resolution、DoorPregrasp import smoke 问题时
---

## Purpose

记录当前 local runtime origin-reference facts 与已知 caveats。这里仅描述环境基线和维护点，不记录 future migration 或 target implementation progress。

Runtime facts:

- Conda env: `isaaclab`
- Primary IsaacSim/IsaacLab runtime command on this machine: `/home/baoquanc/anaconda3/envs/isaaclab/bin/python`. Prefer this interpreter for IsaacLab/IsaacSim smoke, preview, and standalone scripts. `isaaclab.sh -p` can be used only when the shell has the expected Python/PATH setup; in this workspace it may fail if plain `python` is unavailable.
- Python: `3.11.15`
- Isaac Sim: `5.1`
- IsaacLab editable checkout: `/home/baoquanc/workspace/IsaacLab`
- IsaacLab official docs route: use Context7 with resolved library ID `/websites/isaac-sim_github_io_isaaclab_main` when current official IsaacLab docs are needed; the local source checkout at `/home/baoquanc/workspace/IsaacLab` is also available for exact installed behavior.
- GPU/driver: `NVIDIA RTX A6000`, driver `580.159.03`
- OS: local Ubuntu `24.04.2`; top README expectation/文档基线写的是 Ubuntu `22.04`
- Shell tool caveat: this environment does not have `rg`; use `find` + `grep` for local source/text search unless `rg` becomes available.
- Starlette intentional policy: local `starlette==0.45.3` conflicts with `isaaclab==0.54.4` metadata requirement `starlette==0.49.1`, but this is expected/intentional because the environment was configured from another branch and `SimulationApp` smoke has passed. Prefer keeping `starlette==0.45.3` for the IsaacSim/FastAPI path that requires `<0.46`; do not recommend upgrading to `0.49.1` unless this policy is revisited or a new smoke test proves otherwise.
- IsaacLab launcher rule: Isaac Sim / IsaacLab apps should initialize through `AppLauncher` before importing simulation-dependent modules.
- README DoorPregrasp direct import smoke caveat: top README includes direct import smoke for `DoorPregrasp`; if that import touches simulation-side modules before `AppLauncher`, treat failure as launcher-order caveat rather than immediate task logic proof.

## When Codex/AI Should Read This Entry

- 需要跑 `gr00t/rl/train_agent_trl.py`、`gr00t/rl/eval_agent_trl.py` 或 any Isaac Sim smoke。
- 需要判断 Python/IsaacLab/Isaac Sim compatibility。
- 需要查询 IsaacLab official docs、确认 AppLauncher/standalone workflow 或给子 agent 提供 IsaacLab 背景时。
- 需要解释 README smoke 与 actual standalone launcher workflow 的差异。

## Source Paths

- top install/runtime notes: `README.md`
- IsaacLab editable checkout: `/home/baoquanc/workspace/IsaacLab`
- local IsaacLab docs entry: `/home/baoquanc/workspace/IsaacLab/docs/README.md`
- Context7 IsaacLab official docs ID: `/websites/isaac-sim_github_io_isaaclab_main`
- runtime config: `gr00t/rl/config/simulator/isaacsim.yaml`
- Isaac Sim app kit files: `gr00t/rl/apps/`
- local shell facts: `command -v rg`, `find`, `grep`
- docs index: `memory/origin-reference/runtime-environment/references/isaaclab-docs-index.md`

## TODO Summary

- 2026-06-11 21:53 HKT - 当 conda env、Python、Isaac Sim、IsaacLab checkout/version、GPU driver、OS 或 runtime compatibility 改变时，刷新本 entry。
- 2026-06-11 22:06 HKT - `starlette==0.45.3` intentional policy 只有在 policy 被重新决策，或新的 `SimulationApp` / IsaacSim/FastAPI smoke test 证明应改变时才更新；不要仅因 `isaaclab==0.54.4` metadata requirement 建议升级到 `0.49.1`。
- 2026-06-11 21:53 HKT - 当 IsaacLab official docs route/version 改变时，更新 `references/isaaclab-docs-index.md`。
- 2026-06-12 18:49 HKT - 当 primary IsaacLab Python path、`isaaclab.sh -p` 可用性、Context7 IsaacLab library ID、local IsaacLab source path 或 shell search tool availability 改变时，刷新本 entry，并在 A2_Piper subagent background notes 中同步。

## DONE Summary

- 2026-06-11 21:53 HKT - 初始化 runtime environment origin reference entry，记录 local Isaac Sim/IsaacLab/AppLauncher/dependency caveats。
- 2026-06-11 22:06 HKT - 记录 `starlette==0.45.3` intentional policy：虽与 `isaaclab==0.54.4` metadata requirement `starlette==0.49.1` 冲突，但当前 prefer 保持 IsaacSim/FastAPI `<0.46` path，不默认建议升级。
- 2026-06-12 18:49 HKT - 记录 IsaacLab docs/source/runtime/tooling 背景：official docs 可通过 Context7 `/websites/isaac-sim_github_io_isaaclab_main` 查询，local source 在 `/home/baoquanc/workspace/IsaacLab`，机器上的 IsaacSim runtime 使用 conda env `isaaclab` 的 `/home/baoquanc/anaconda3/envs/isaaclab/bin/python`，当前 shell 没有 `rg`，搜索应使用 `find` + `grep` fallback。

## Recommended Next Files To Read

- `memory/origin-reference/runtime-environment/references/isaaclab-docs-index.md`
- `memory/origin-reference/door-workflows/description.md`
- `README.md`
- `/home/baoquanc/workspace/IsaacLab/docs/README.md`
