# Origin Reference Memory

本 subsystem 是 origin reference memory only。它记录当前 repository baseline、runtime 环境事实、door workflow 入口、assets/data 索引与 documentation truth map，帮助后续 agent 在不反复扫描全仓的情况下快速定位 source-of-truth。

Future migration、target implementation progress、bugfix 施工状态、experiment tracking 必须写到其他 memory subsystem，不要混入这里。

## Entries

- [repo-baseline/description.md](repo-baseline/description.md): repository baseline、package/core path、origin commit。
- [runtime-environment/description.md](runtime-environment/description.md): local runtime、Isaac Sim/IsaacLab、known dependency caveats。
- [door-workflows/description.md](door-workflows/description.md): DoorPregrasp teacher PPO、student DAgger vision、eval workflow 路由。
- [assets-and-data/description.md](assets-and-data/description.md): local models、motion/data、door asset generation 索引。
- [documentation-truth-map/description.md](documentation-truth-map/description.md): README/source/config truth map 与 stale/conflict markers。

## Update Rules

- 先读对应 entry 的 `description.md`。
- 需要判断 maintenance 状态时，再读同 entry 的 `TODO.md` 和 `DONE.md`。
- entry 的 TODO 只记录 origin reference 维护事项，不记录 migration implementation。
- Timestamp 使用 `YYYY-MM-DD HH:MM HKT`。
