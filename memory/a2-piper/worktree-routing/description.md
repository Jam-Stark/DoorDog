---
name: worktree-routing
scope: A2_Piper active implementation worktrees and doorman reference worktree routing
status: active
last_updated: 2026-08-03 14:31 HKT
owned_paths:
  - memory/a2-piper/MEMORY.md
  - memory/a2-piper/worktree-routing/description.md
  - memory/a2-piper/worktree-routing/TODO.md
  - memory/a2-piper/worktree-routing/DONE.md
read_when:
  - 开始 A2_Piper robot migration、reward design、env config、training/eval workflow 或相关文档更新前
  - 需要确认哪个 worktree 用于实现、哪个 worktree 只作 doorman baseline/reference 前
  - 给 code worker、reviewer 或 explorer 子 agent 派发 A2_Piper/IsaacLab 相关任务前
---

## Purpose

记录 A2_Piper 的 workspace routing 与 branch/worktree 使用约定，避免把主线、pull-v0 与 doorman baseline/reference 的改动写入错误 worktree。

Workspace facts:

- Mainline implementation worktree: `/home/baoquanc/workspace/DoorDog-A2_Piper`
- Mainline implementation branch: `A2_Piper`
- Pull-v0 implementation worktree: `/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0`
- Pull-v0 implementation branch: `codex/a2-piper-pull-v0-20260803`
- Pull-v0 base SHA: `4aec9fe76043c3bb85d8bcdd1c2cd9210086dc09`
- Pull-v0 purpose: 按 `scriptsFORhuman/pull_task/a2_piper_pull_v0_worker_execution_split_20260803.md` 实施 pull-door v0；pull-v0 code、config、evidence 与 task memory 只写入该 worktree/branch。
- Remote targets: `origin/A2_Piper` 与 `origin/codex/a2-piper-pull-v0-20260803` under `https://github.com/Jam-Stark/DoorDog.git`
- Retired pull worktree `/home/baoquanc/workspace/DoorDog-A2_Piper_pull` 已移除；旧 branch `codex/a2-piper-pull-door` 的 tip 由 tag `archive/pull-door-v10-static-20260714` 保留。
- Doorman baseline/reference worktree: `/home/baoquanc/workspace/GR00T-VisualSim2Real`
- `/home/baoquanc/workspace/GR00T-VisualSim2Real` 平时只读参考，不在那里改代码。
- 主线 A2_Piper 的 robot asset/config、env config、reward function、training/eval workflow、experiment progress 与相关 memory 更新，应在 `/home/baoquanc/workspace/DoorDog-A2_Piper` 中完成；pull-v0 scope 的对应改动例外地只在 `/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0` 中完成。
- 当 AI 需要参照原 doorman code 时，应读取 `/home/baoquanc/workspace/GR00T-VisualSim2Real` 的对应 source/config，再按任务 scope 在 mainline 或 pull-v0 implementation worktree 中实施变更。

## Subagent Background Notes

给 code worker、implement reviewer 或 explorer 子 agent 派发 A2_Piper/IsaacLab 相关任务时，应同步以下背景，避免重复踩环境坑：

- IsaacLab official docs 可通过 Context7 查询，resolved library ID 为 `/websites/isaac-sim_github_io_isaaclab_main`；local IsaacLab source checkout 在 `/home/baoquanc/workspace/IsaacLab`，可用于确认当前安装行为。
- 机器上的 IsaacSim/IsaacLab runtime 配置在 conda env `isaaclab` 中，优先使用 `/home/baoquanc/anaconda3/envs/isaaclab/bin/python` 运行 IsaacLab/IsaacSim smoke、preview 或 standalone script。`/home/baoquanc/workspace/IsaacLab/isaaclab.sh -p` 只有在 shell 有预期 Python/PATH 时才作为替代。
- 当前 shell 没有 `rg`；子 agent 搜索本地源码/文本时应使用 `find` + `grep` fallback。

## When Codex/AI Should Read This Entry

- 任何 A2_Piper 实现、调试、review 或文档更新前。
- 需要 side-by-side 对照 doorman baseline 与 A2_Piper 改动时。
- 需要确认不要修改 baseline/reference worktree 时。
- 派发子 agent 任务前，需要把 A2_Piper worktree、baseline worktree、IsaacLab docs/runtime 与 shell tooling 背景写入 prompt。

## Source Paths

- A2_Piper worktree: `/home/baoquanc/workspace/DoorDog-A2_Piper`
- pull-v0 worktree: `/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0`
- doorman baseline/reference worktree: `/home/baoquanc/workspace/GR00T-VisualSim2Real`
- IsaacLab source checkout: `/home/baoquanc/workspace/IsaacLab`
- primary IsaacLab Python: `/home/baoquanc/anaconda3/envs/isaaclab/bin/python`
- Context7 IsaacLab docs ID: `/websites/isaac-sim_github_io_isaaclab_main`
- local git source: `git worktree list`, `git status --short --branch`, `git remote -v`

## TODO Summary

- 2026-06-12 16:54 HKT - 当 A2_Piper implementation worktree、branch、remote target 或 doorman baseline/reference worktree 路由改变时，更新本 entry 与相关 `MEMORY.md` route。
- 2026-06-12 18:49 HKT - 当 IsaacLab docs route、primary IsaacLab Python、local IsaacLab source path 或 shell tooling 背景改变时，更新本 entry 的 subagent background notes。

## DONE Summary

- 2026-06-12 16:54 HKT - 初始化 A2_Piper worktree routing entry，明确 `/home/baoquanc/workspace/DoorDog-A2_Piper` 用于实现，`/home/baoquanc/workspace/GR00T-VisualSim2Real` 作为 doorman baseline/reference worktree 且默认只读。
- 2026-06-12 18:49 HKT - 补充 A2_Piper subagent background notes：派发任务时告知 IsaacLab official docs 可用 Context7 `/websites/isaac-sim_github_io_isaaclab_main` 查询、local source 在 `/home/baoquanc/workspace/IsaacLab`、IsaacSim runtime 优先使用 `/home/baoquanc/anaconda3/envs/isaaclab/bin/python`、当前 shell 无 `rg` 需用 `find` + `grep`。
- 2026-08-03 14:31 HKT - 归档并移除旧 pull worktree/branch，新增 pull-v0 worktree `/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0`、branch `codex/a2-piper-pull-v0-20260803` 与 base `4aec9fe76043c3bb85d8bcdd1c2cd9210086dc09` 的 routing 约定。

## Recommended Next Files To Read

- `memory/origin-reference/door-workflows/description.md`
- `memory/origin-reference/repo-baseline/description.md`
