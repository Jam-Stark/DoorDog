# GR00T-VisualSim2Real Memory 入口

本项目的 file-based memory 当前只包含 origin reference memory，用于记录 upstream baseline、runtime 环境、door workflows、assets/data 与 documentation truth map。

## Route

- 读取项目 origin/baseline 参考事实时，从 [memory/origin-reference/MEMORY.md](memory/origin-reference/MEMORY.md) 开始。

## Update Rules

- Future migration、target implementation progress、experiment progress、bugfix 施工状态必须放到后续独立 memory subsystem，不要写入 origin reference memory。
- 每次完成某个 memory entry 的 TODO 时，同步更新该 entry 的 `TODO.md`、`DONE.md` 和 `description.md` summary。
- Timestamp 使用 `YYYY-MM-DD HH:MM HKT`。
- 文档保持中文叙述 + English technical terms，不复制长源码或长文档。
