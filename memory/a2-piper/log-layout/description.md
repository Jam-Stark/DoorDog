---
name: a2-piper-log-layout
scope: canonical logs_rl/logs_eval artifact layout for A2_Piper training, smoke, launcher, eval, render, and reports
status: active
last_updated: 2026-07-28 16:50 HKT
owned_paths:
  - memory/a2-piper/MEMORY.md
  - memory/a2-piper/log-layout/description.md
  - memory/a2-piper/log-layout/TODO.md
  - memory/a2-piper/log-layout/DONE.md
read_when:
  - writing or moving A2_Piper train, smoke, eval, render, launcher, or report artifacts
  - constructing checkpoint, experiment_dir, eval_output_dir, or artifact-reference paths
---

# A2_Piper Log Layout

## Purpose

本 entry 是 A2_Piper 新产物路径管理的高层约束。实验行为、评价结论与训练命令仍由对应 optimization entry 拥有；这里仅拥有目录结构、迁移原子性与路径引用规则。

## Canonical Layout

- Formal training：`logs_rl/a2_piper_full_stage_a2_base/base_vN/<run-dir>/`。
- Smoke：`logs_rl/a2_piper_full_stage_a2_base_smoke/base_vN/rN/<run-dir>/`；非轮次 smoke diagnostics 可放在同版本下的 descriptive family，例如 `device_diagnostics/`。
- Launcher：`logs_rl/launchers/base_vN/<launcher-dir>/`。
- Eval：`logs_eval/base_vN/<experiment-family>/<result-folder>/`。
- 同一实验族必须聚合到 stable family；例如 v19 的各组 M22 分别使用 `G1_m22`–`G7_m22`，跨组 queue/recovery 使用 `m22_shared`。`render`、`final_analysis`、`wandb`、`preflight` 使用各自 family。

## Required Invariants

- 一个 eval/result folder 是不可拆分的 evidence unit；其 `.hydra`、logs、metrics、traces、diagnostics、reports 与 renderings 必须整体共置，不得按文件类型拆散。
- 新 launcher、training、smoke、eval 与 render script 必须直接写入 canonical layout，不能先写旧路径再事后依赖整理。
- 路径迁移必须原子更新 configs、tests、docs 与 text artifact 中的 exact relative/absolute references；旧路径必须消失并 fail fast，不创建 legacy alias symlink 或 silent fallback。
- 路径迁移不得重写 checkpoint、video、image、W&B binary 或其他 binary artifact 内容；只允许 exact text-path replacement，并在迁移后验证关键 hashes、JSON parse、symlink resolution 与 stale-reference count。
- 版本内先按 experiment family 聚合，再保留原 result-folder 名称及 retry/failure suffix，以维持 provenance。
- 任何范围外版本默认不动；扩大迁移版本范围需要单独授权与清单。

## Current Migration Baseline

2026-07-28 已完成仅 v17–v19 的 186 项 same-filesystem rename：共 4,356 files、1,131 directories、72 symlinks；1,419 JSON parse PASS，72/72 symlink resolution PASS，9/9 checkpoint configs resolve，targeted tests `27 passed`，旧 relative/absolute source-prefix match 为 0。text path 变长造成总字节数 `56,623,695,639 → 56,624,030,936`，binary artifact 未改写，关键 checkpoint SHA-256 保持不变。

迁移 source-of-truth 为 `logs_eval/_layout/a2_piper_v17_v19_layout_migration_20260728.json`，human summary 为同目录 `.md`。清单为 provenance 唯一允许保留旧 source paths 的位置。
