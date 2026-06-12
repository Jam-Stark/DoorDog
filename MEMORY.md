# DoorDog / A2_Piper Memory 入口

本项目的 file-based memory 包含 origin reference memory 与 A2_Piper development memory。

Origin reference memory 用于记录 upstream baseline、runtime 环境、door workflows、assets/data 与 documentation truth map。A2_Piper development memory 用于记录本 branch/worktree 的 robot migration、reward design、workspace routing、experiment progress 与当前 TODO/DONE。

## Route

- 读取项目 origin/baseline 参考事实时，从 [memory/origin-reference/MEMORY.md](memory/origin-reference/MEMORY.md) 开始。
- 读取 A2_Piper branch/worktree 开发约定、robot/reward 迁移状态或 workspace routing 时，从 [memory/a2-piper/MEMORY.md](memory/a2-piper/MEMORY.md) 开始。

## Update Rules

- Future migration、target implementation progress、experiment progress、bugfix 施工状态必须放到 A2_Piper 或其他独立 memory subsystem，不要写入 origin reference memory。
- 每次完成某个 memory entry 的 TODO 时，同步更新该 entry 的 `TODO.md`、`DONE.md` 和 `description.md` summary。
- Timestamp 使用 `YYYY-MM-DD HH:MM HKT`。
- 文档保持中文叙述 + English technical terms，不复制长源码或长文档。
