code风格规范：fail-fast 策略。isaaclab相关code必须避免为了 “所谓的code健壮性” 来添加不必要的保护性操作/fallback强行让仿真/训练运行下去。我需要将code问题在运行/训练中暴露出来。
复杂task code implement要求（简单修改任务直接自己去implement code，自己更新相关Memory/文档，不用交给子agent）：
你作为user需求主管(main agent)不需要自己去implement code。将code implement工作，阐述清晰背景，需求，计划交给一个子agent（code worker）去实现。等coder worker有第一次结果返回后启动另一个子agent（implement reviewer）进行double check,和更新相关Memory/文档（强调是reviewer去更新文档）。 main agent做最后的复核即可。
补充：不要轻易直接去修改code，每次修改code/启动code worker前应该将方案发送给user审核。

你正在当前项目根目录中工作。开始任何实现、调试、review 或文档更新前，必须先合理使用项目内 file-based memory system。（如果当前项目没有实现Memory机制请忽略）

Memory 使用规则：

1. 先读项目根目录的顶层入口：
   `MEMORY.md`

2. 根据任务类型选择最小必要 memory，不要一次性读完整个项目：
   - 项目整体结构、记忆系统规则、memory build history：
     `memory/MEMORY.md`
   - 子项目1 Memory.md
   - 子项目2 Memory.md
   - ...
3. 每个 memory entry 的读取顺序：
   - 先读 `description.md`
   - 需要施工或判断当前状态时，再读 `TODO.md` 和 `DONE.md`
   - 只有当 `description.md` 指向某个 source/doc 且当前任务需要时，才继续读 references 或源码

4. 不要把 memory 当聊天历史。memory 只记录可复用的项目事实、施工状态、设计决策、当前 blocker 和下一步 TODO。

5. 如果完成了某个 memory entry 中的 TODO，必须在同一次变更中：
   - 从对应 `TODO.md` 移除或改写该 item
   - 在对应 `DONE.md` 添加相同 timestamp 的完成记录
   - 更新对应 `description.md` 的 TODO/DONE summary
   - 如新增 entry 或改变路由，同步更新相关 `MEMORY.md`

6. Timestamp 使用：
   `YYYY-MM-DD HH:MM HKT`

7. 文档风格：
   使用中文叙述 + English technical terms。稳定技术概念保持英文，例如 `DualRunner`、`HistoryWrapper`、`reward routing`、`forced-hybrid smoke`、`ObservationManager`。

8. 避免无意义重写 memory：
   - 不要移动已有长文档，优先在 memory 中引用
   - 不要复制大段源码
   - 不要跨越当前任务无关的 memory subsystem
   - 不要覆盖用户或其他 agent 的未完成改动

9. 开始工作前，先简短说明你读取了哪些 memory entry，以及这些 entry 如何影响你的执行计划。