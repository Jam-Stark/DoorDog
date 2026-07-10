# Memory Index

当前包含 origin reference、A2_Piper development 与 repo-wide agent-system memory。

## Routes

- [origin-reference/MEMORY.md](origin-reference/MEMORY.md): upstream/origin baseline、runtime environment、door workflows、assets/data、documentation truth map。
- [a2-piper/MEMORY.md](a2-piper/MEMORY.md): A2_Piper branch/worktree 开发约定、robot migration、reward design、workspace routing、experiment progress。
- [agent-system/MEMORY.md](agent-system/MEMORY.md): Codex multi-agent architecture、runtime compatibility、role discovery/evaluation 与 rollout gate。

## Scope Guard

origin reference memory 只保存可复用的 origin/source-of-truth 事实与已知 caveat。Future migration、target implementation progress、debug 施工日志、实验结果应创建并维护在 A2_Piper 或其他独立 memory subsystem。Agent-system 只保存 verified architecture/compatibility/evaluation evidence，不记录 transient agent progress。
