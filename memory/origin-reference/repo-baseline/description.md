---
name: repo-baseline
scope: origin repository baseline and package layout
status: active
last_updated: 2026-06-11 21:53 HKT
owned_paths:
  - MEMORY.md
  - memory/MEMORY.md
  - memory/origin-reference/MEMORY.md
  - memory/origin-reference/repo-baseline/description.md
  - memory/origin-reference/repo-baseline/TODO.md
  - memory/origin-reference/repo-baseline/DONE.md
read_when:
  - 需要确认 upstream origin、branch、commit baseline
  - 开始会影响 repository structure 或 package routing 的工作前
---

## Purpose

记录 origin reference baseline，作为后续实现、review、文档判断的最小入口。这里不记录 future migration 或 target implementation progress。

Baseline facts:

- Remote: `https://github.com/NVlabs/GR00T-VisualSim2Real.git`
- Branch: `main`
- Commit: `016c70c1e4e76f521963c36691ee69a6ab3ac9cd`
- Python package: `gr00t`
- Core subsystem: `gr00t/rl`

## When Codex/AI Should Read This Entry

- 需要确认当前 worktree 是否仍对齐 origin baseline。
- 需要判断某个路径属于 package root、RL core、还是 repo-level documentation。
- 准备新增其他 memory subsystem 时，用它确认 route 不应混入 origin reference。

## Source Paths

- source-of-truth: `README.md`
- package root: `gr00t/__init__.py`, `gr00t/version.py`
- RL core root: `gr00t/rl/`
- packaging metadata snapshot: `gr00t.egg-info/`
- repository metadata source: `git remote -v`, `git branch --show-current`, `git rev-parse HEAD`

## TODO Summary

- 2026-06-11 21:53 HKT - 未来当 origin remote、default branch、baseline commit 或 package/core path 改变时，更新本 entry 的 baseline facts。

## DONE Summary

- 2026-06-11 21:53 HKT - 初始化 repo baseline origin reference entry，并确认 remote/branch/commit 与请求 baseline 一致。

## Recommended Next Files To Read

- `memory/origin-reference/documentation-truth-map/description.md`
- `memory/origin-reference/runtime-environment/description.md`
- `README.md`
