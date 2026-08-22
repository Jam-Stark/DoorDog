<!-- managed-by: jam-coding-role; file: WORKFLOW.md -->
# DoorDog adaptive workflow v1.3

## 1. 基本原则：轻内核，按需启用控制设施

默认使用 prompt 内的最小协调。Ledger、contract、lease、freeze、curator、long-run supervisor 和 artifact handoff 只有在解决真实风险时启用，不作为普通任务的完成仪式。

## 2. 路由

### FAST

适用于：简单 QA、只读定位、prose、typo、明确 config tweak、临时实现/测试、单文件或边界清楚的小改动。

```text
minimal context -> inspect/modify -> one matching proof -> report
```

默认：Main 直接完成；不 spawn team；不创建 ledger、contract、freeze、curator 或 artifact bundle。

### STANDARD

适用于：普通跨文件实现、debug、IsaacLab 小范围改动、需要一到三个专门角色的 focused work。

```text
minimal memory -> trace real path -> short acceptance plan
-> smallest end-to-end implementation -> claim-matched evidence -> integrate
```

默认仍是 lean workflow：

- 0–3 个 agent，仅在独立价值明确时使用；
- 一个 writer；
- P2P 可直接传递技术事实；
- 不要求每次 spawn 落盘合同；
- 不要求 persistent ledger 或 candidate freeze；
- review、runtime QA、memory 和 artifact 都由实际触发条件决定。

### HIGH_RISK

HIGH_RISK 是审批覆盖层，不是“文件多就升级”的固定流水线。适用于 destructive/external action、硬件、安全边界、数据迁移、材料性跨子系统设计、未经授权的昂贵长跑或难回滚变更。

Main 先向 Owner 说明 scope、成本/资源、停止条件和回退方式，得到明确授权后执行。获得授权后仍使用最低充分的实现和验证路径。

## 3. 控制设施触发表

| 设施 | 仅在以下情况启用 |
|---|---|
| Team ledger / task contract | 多 writer、跨 session DAG、复杂依赖、正式 review/QA 链或 Main 明确需要持久状态 |
| WRITE_SET / resource lease | 实际并发 writer，或 GPU/IsaacSim/display/port/hardware/output root 等排他资源 |
| Candidate freeze | 正式 code/IsaacLab review、formal runtime QA、dirty shared worktree 中需要精确审查对象，或跨 session candidate |
| Verdict dependency | 已经存在 scope-bound PASS/FAIL，且窄修复需要判断哪些 verdict 保留 |
| Memory curator | 出现已验证且未来会复用的 durable candidate，或 memory 分类/路由确实需要重构 |
| Long-run supervisor | 运行预计 >30 分钟、需要断线连续性、checkpoint/eval finalizer 或 pending event |
| Artifact handoff | Owner 明确要求，或 stage contract 明确声明需要 cloud/local planner 交接 |

只启用必要的一项或几项，不因其中一项触发而自动开启全部设施。

## 4. P2P：信息面与权限面分开

Codex MultiAgentV2 支持 sibling 间直接通信。技术信息应直接到达消费者，不必全部由 Main 人工复制。

在普通 STANDARD 中可以使用自然、简短的直接消息。只有协调链较长或需要可追溯性时，才使用结构化类型：

- `PEER_FINDING`：精确 source/API/runtime evidence；
- `PEER_REQUEST`：不改变 scope/lease 的有限诊断或只读请求；
- `AUTHORITY_REQUEST`：scope、acceptance、revision、WRITE_SET、排他资源、Git、hard stop 或外部写入，只能发给 Main。

P2P 传递事实，不传递权限。只有材料性 blocker、candidate-ready、review/runtime verdict、dependency change 或 authority request 需要同步给 Main。

## 5. Escalation 与 de-escalation

执行中发现 writer 冲突、排他资源竞争、跨 session continuity 或正式 gate 时，Main 可以只激活对应控制设施。风险消失后应停用，不让临时设施变成项目的永久前置步骤。

## 6. Evidence 与 closure

Evidence 必须匹配 claim：inspect/static/test/runtime/experiment/hardware。不要为安心重复同类证明。

普通任务完成前只需：

- 一次相关 diff/path boundary 检查；
- 实际需要的 proof；
- 关闭或停止仍活跃的 writer/排他资源；
- 报告未运行事项。

没有 durable candidate 时不启动 curator；没有 stage handoff trigger 时不打包 artifact；没有正式 review/QA 时不 freeze candidate。
