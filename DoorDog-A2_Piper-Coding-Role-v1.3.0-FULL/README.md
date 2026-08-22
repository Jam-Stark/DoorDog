# DoorDog A2_Piper — Jam Coding Role v1.3.0

v1.3.0 的主题是：**轻内核、按需启用控制设施**。

它保留 v1.2.0 的 Codex P2P、主动 memory governance、long-run continuity 和 artifact handoff，但不再让 ledger、task contract、lease、candidate freeze、memory curator 或 artifact bundle 成为普通任务的默认前置/收尾步骤。

## 核心变化

- FAST：简单 QA、临时测试和明确小改动由 Main 直接完成；
- STANDARD：普通实现保持 lean，可按需使用少量 agent 和 P2P；
- HIGH_RISK：只作为需要 Owner 授权的风险覆盖层；
- team state 默认 inactive，只有多 writer、排他资源、跨 session 或 formal review/QA 才启用；
- artifact handoff 必须显式确认；
- migration script 默认不 commit，Git 行为必须通过命令行旗标获得明确授权；
- root `AGENTS.md` 是条件路由表，不是十一份文档的全量阅读清单。

## 安全预演

```bash
python apply_doordog_v1_3.py \
  --repo /path/to/DoorDog \
  --dry-run \
  --checkpoint-commit \
  --migration-commit
```

`--dry-run` 不会修改或提交任何内容，只显示在当前授权选择下会发生什么。

## 当前 Owner 已授权的迁移方式

本包附带的 `APPLY_PROMPT.md` 明确授权本次迁移创建两个本地 commit，但不授权 push：

```bash
python apply_doordog_v1_3.py \
  --repo /path/to/DoorDog \
  --apply \
  --checkpoint-commit \
  --migration-commit \
  --confirm-user-authorized-commit
```

通用情况下，脚本默认不 commit。没有当前任务中的明确授权时，不得添加上述 commit flags。

## 保留路径

```text
.codex/config.toml
.codex/agents/
MEMORY.md
memory/a2-piper/
robot / IsaacLab / RL source
logs_rl / logs_eval / checkpoints / renders
```

脚本不执行 reset、stash、clean、push 或 force-add ignored artifacts，也不会初始化 team ledger。
