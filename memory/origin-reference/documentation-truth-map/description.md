---
name: documentation-truth-map
scope: source-of-truth, stale documentation, and known documentation/config conflicts
status: active
last_updated: 2026-06-11 21:53 HKT
owned_paths:
  - memory/origin-reference/documentation-truth-map/description.md
  - memory/origin-reference/documentation-truth-map/TODO.md
  - memory/origin-reference/documentation-truth-map/DONE.md
read_when:
  - 需要判断 README、Hydra config、source code 哪个更可信
  - 发现 documentation 与 config/source 行为冲突时
---

## Purpose

记录 documentation truth map，帮助 future agents 优先读取 current source/Hydra/top README，并识别 stale/legacy docs。此 entry 不编辑 README，也不记录 migration implementation progress。

Truth map:

- Current source-of-truth: `gr00t/rl/` source code、Hydra config under `gr00t/rl/config/`、top `README.md` 的 current door workflow sections。
- Stale/legacy marker: `gr00t/rl/README.MD` references older Isaac Gym style and `groot/rl/train_agent.py`; treat it as legacy unless source confirms。
- Known conflict: top README describes LAFAN-G1 as sibling directory; config/runtime expectation uses `${HOME}/projects/LAFAN-G1`。Do not edit README as part of origin reference memory creation。
- Runtime caveat marker: top README DoorPregrasp direct import smoke may conflict with IsaacLab `AppLauncher` ordering; see runtime entry。

## When Codex/AI Should Read This Entry

- 需要回答“哪个文档可信”或处理 README/config/source mismatch。
- 开始修改 docs 前需要避免把 stale `gr00t/rl/README.MD` 当作 current workflow。
- 需要解释 LAFAN-G1 path conflict 或 `DoorPregrasp` smoke caveat。

## Source Paths

- top current docs: `README.md`
- current Hydra config root: `gr00t/rl/config/`
- current train/eval source: `gr00t/rl/train_agent_trl.py`, `gr00t/rl/eval_agent_trl.py`
- current door source: `gr00t/rl/envs/door/door_open_homie.py`
- stale/legacy docs: `gr00t/rl/README.MD`
- conflict evidence routes: `README.md`, `gr00t/rl/config/env/door_open_homie.yaml`, `gr00t/rl/envs/door/reset_from_dataset.py`

## TODO Summary

- 2026-06-11 21:53 HKT - 当 README、Hydra config、source routing 或 stale/legacy markers 改变时，更新 truth map。

## DONE Summary

- 2026-06-11 21:53 HKT - 初始化 documentation truth map，记录 source/Hydra/top README priority、stale `gr00t/rl/README.MD` marker、LAFAN-G1 conflict 与 README edit guard。

## Recommended Next Files To Read

- `memory/origin-reference/repo-baseline/description.md`
- `memory/origin-reference/runtime-environment/description.md`
- `memory/origin-reference/assets-and-data/description.md`
- `README.md`
