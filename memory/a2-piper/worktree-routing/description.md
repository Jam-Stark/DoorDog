---
name: worktree-routing
scope: A2_Piper primary/pull implementation worktrees and doorman reference worktree routing
status: active
last_updated: 2026-07-14 00:43 HKT
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

记录 A2_Piper primary/pull workspace routing 与 branch/worktree 使用约定，避免把并行实现写入错误 worktree 或 doorman baseline/reference worktree。

Workspace facts:

- Primary push/shared implementation worktree: `/home/baoquanc/workspace/DoorDog-A2_Piper`
- Primary implementation branch: `A2_Piper`
- Pull-only implementation worktree: `/home/baoquanc/workspace/DoorDog-A2_Piper_pull`
- Pull-only implementation branch: `codex/a2-piper-pull-door`
- Pull branch base SHA: `496ea4fd2ef88de23995458badff5cb78e6a3701`
- Remote target: `origin/A2_Piper` under `https://github.com/Jam-Stark/DoorDog.git`
- Doorman baseline/reference worktree: `/home/baoquanc/workspace/GR00T-VisualSim2Real`
- `/home/baoquanc/workspace/GR00T-VisualSim2Real` 平时只读参考，不在那里改代码。
- Push/shared/Student work 继续在 `/home/baoquanc/workspace/DoorDog-A2_Piper`；pull-only scenario/env/experiment 与方向语义在 `/home/baoquanc/workspace/DoorDog-A2_Piper_pull`。两边共享 Git object/refs，但 checkout、index 与 dirty files 隔离。
- Pull worktree 从 committed SHA 创建，没有复制 primary worktree 中未提交的 Student Distillation WIP；禁止用 stash/reset/clean 把那批 WIP 搬入 pull worktree。
- 当 AI 需要参照原 doorman code 时，应读取 `/home/baoquanc/workspace/GR00T-VisualSim2Real` 的对应 source/config，再按本 entry 路由到 primary 或 pull implementation worktree 实施变更。

## Pull Integration Boundary

- 当 pull branch 需要吸收 primary 的新进展时，先让 primary worktree 的相关 WIP 被有意 review/commit，再由 Main 在 pull/integration worktree 执行 merge；不能从 dirty working tree 隐式复制文件。
- 最终合回 `A2_Piper` 前，应在 clean integration worktree 验证 frozen primary + pull candidate。merge/rebase/cherry-pick、conflict resolution、stage 与 commit 仍是 Main-only Git 操作。

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
- pull-only worktree: `/home/baoquanc/workspace/DoorDog-A2_Piper_pull`
- doorman baseline/reference worktree: `/home/baoquanc/workspace/GR00T-VisualSim2Real`
- IsaacLab source checkout: `/home/baoquanc/workspace/IsaacLab`
- primary IsaacLab Python: `/home/baoquanc/anaconda3/envs/isaaclab/bin/python`
- Context7 IsaacLab docs ID: `/websites/isaac-sim_github_io_isaaclab_main`
- local git source: `git worktree list`, `git status --short --branch`, `git remote -v`

## TODO Summary

- 2026-06-12 16:54 HKT - 当 A2_Piper implementation worktree、branch、remote target 或 doorman baseline/reference worktree 路由改变时，更新本 entry 与相关 `MEMORY.md` route。
- 2026-06-12 18:49 HKT - 当 IsaacLab docs route、primary IsaacLab Python、local IsaacLab source path 或 shell tooling 背景改变时，更新本 entry 的 subagent background notes。
- 2026-07-14 00:43 HKT - Pull branch 需要吸收 primary 新进展或最终合回 `A2_Piper` 时，先提交相关 primary WIP，再使用 clean integration worktree 做 merge 与验证；不得从 dirty worktree 隐式复制。

## DONE Summary

- 2026-06-12 16:54 HKT - 初始化 A2_Piper worktree routing entry，明确 `/home/baoquanc/workspace/DoorDog-A2_Piper` 用于实现，`/home/baoquanc/workspace/GR00T-VisualSim2Real` 作为 doorman baseline/reference worktree 且默认只读。
- 2026-06-12 18:49 HKT - 补充 A2_Piper subagent background notes：派发任务时告知 IsaacLab official docs 可用 Context7 `/websites/isaac-sim_github_io_isaaclab_main` 查询、local source 在 `/home/baoquanc/workspace/IsaacLab`、IsaacSim runtime 优先使用 `/home/baoquanc/anaconda3/envs/isaaclab/bin/python`、当前 shell 无 `rg` 需用 `find` + `grep`。
- 2026-07-14 00:43 HKT - 创建并确认 pull-only linked worktree `/home/baoquanc/workspace/DoorDog-A2_Piper_pull` 与 branch `codex/a2-piper-pull-door`，起点为 committed SHA `496ea4f`；primary worktree 的未提交 Student Distillation WIP 保持原位且未被复制。

## Recommended Next Files To Read

- `memory/origin-reference/door-workflows/description.md`
- `memory/origin-reference/repo-baseline/description.md`
