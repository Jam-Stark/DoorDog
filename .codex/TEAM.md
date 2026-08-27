# DoorDog Codex MultiAgentV2 workflow v1.3

## Proactive delegation gate

- FAST：Main 直接完成。
- STANDARD：深度工作前检查独立 lane、specialist context、独立 review/QA 的材料性价值，以及并行对速度或 Main context 的实质收益。任一条件命中时，立即 spawn 最少必要的 1–3 个 focused agent，不等待 Owner 说“team”，也不推迟到 Main 已经完成应委托工作之后。
- HIGH_RISK：破坏性、外部、硬件或昂贵副作用仍需 Owner 授权；安全的只读 scout、planner、source verification 或 reviewer lane 适用同一主动委托 gate，可在等待授权时开始。
- 非 FAST 使用单 agent 时，必须记录具体 `NO_DELEGATION_REASON`：没有独立价值、任务紧耦合且直接完成更便宜，或更高层/runtime 禁止 sub-agent。

P2P 传递技术事实，不传递权限。Main 仍负责等待结果、集成、scope、acceptance、write/resource authority、Git、外部写入和最终关闭。

## Lean default

FAST and ordinary STANDARD work use Main or a small focused set of agents with prompt-level boundaries. Persistent team state is OFF by default.

Project roles remain those registered in `.codex/agents/*.toml`. Model/effort/concurrency remain in `.codex/config.toml`.

## P2P

Use direct sibling communication for exact API evidence、runtime signatures、reproduction commands、targeted defects and dependency-ready notices. Peers act only within existing assignments.

Use structured `PEER_FINDING` / `PEER_REQUEST` / `AUTHORITY_REQUEST` only when it improves routing or traceability. Main alone changes scope、acceptance、revision、WRITE_SET、exclusive resources、Git or hard stops.

## When to activate coordination state

Activate `.ai/TEAM_STATE.md` only for:

- multiple writers;
- exclusive GPU/IsaacSim/display/port/hardware/output resources;
- cross-session DAG;
- formal review/runtime QA with an exact candidate;
- verdict invalidation after narrow fixes.

```bash
python .ai/scripts/team_state.py activate --mode adaptive --reason "..."
```

A read-only researcher or simple worker spawn does not require a disk contract. In `strict` mode, controlled writer/reviewer/runtime roles require one.

## Candidate freeze

Freeze only for formal review/QA or ambiguous dirty/shared worktrees. Ordinary implementation and temporary QA do not create revisions or verdict objects.

## Review and QA

Review is trigger-driven and concern-specific. One concern has one owner. A narrow fix invalidates only bound verdicts. Runtime QA runs the smallest command that can establish the requested runtime claim.

## Long jobs

A single authorized long run may use `.ai/LONG_RUNNING_TASKS.md` without the full ledger. Add leases when runs or agents compete for exclusive resources.

## Closure

No mandatory curator、freeze、artifact or team-state step. Close active agents/resources and deactivate coordination if it was enabled.
