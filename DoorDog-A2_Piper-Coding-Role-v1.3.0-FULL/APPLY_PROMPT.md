# 给本地 DoorDog AI 的 v1.3.0 替换 Prompt

你正在把 DoorDog `A2_Piper` worktree 的 AI workflow 从 v1.2.0/现有版本迁移到 Jam Coding Role v1.3.0。

## Owner 明确授权

本 prompt 本身是本次迁移的明确授权。只授权：

1. 在迁移前将所有 **Git 可见** 修改提交为一个本地 checkpoint commit；
2. 应用并验证 v1.3.0 overlay；
3. 将 workflow migration 提交为第二个本地 commit。

不授权：push、force push、reset、stash、clean、rebase、merge、删除训练产出、force-add ignored artifacts、IsaacLab 运行、训练、正式 eval、Drive 上传或硬件动作。

## 必须执行

1. 解压本包，在包根目录工作。
2. 确认目标是正确的 DoorDog Git worktree，且没有 merge/rebase/cherry-pick/conflict 正在进行。
3. 先执行 dry run：

```bash
python apply_doordog_v1_3.py \
  --repo /path/to/DoorDog \
  --dry-run \
  --checkpoint-commit \
  --migration-commit
```

4. 检查 dry-run 只会覆盖 workflow 路径，并明确保护：

```text
.codex/config.toml
.codex/agents/
MEMORY.md
memory/a2-piper/
```

5. 正式执行：

```bash
python apply_doordog_v1_3.py \
  --repo /path/to/DoorDog \
  --apply \
  --checkpoint-commit \
  --migration-commit \
  --confirm-user-authorized-commit
```

6. 读取脚本输出的 `PRE_MIGRATION_COMMIT` 与 `MIGRATION_COMMIT`，运行一次：

```bash
git status --short
git show --stat --oneline HEAD
```

7. 不做 push。向 Owner 报告：两个 commit SHA、changed paths、解析/编译结果、protected paths 是否逐字节保持、team state 是否仍为 inactive、任何未完成事项。

## v1.3.0 目标行为

- FAST/普通 STANDARD 继续使用 lean workflow；
- 不要求每次 spawn 创建 task contract；
- team ledger 默认 inactive；
- candidate freeze 只用于 formal review/QA 或 ambiguous candidate；
- lease 只用于真实 writer/排他资源冲突；
- memory curator 只由 durable candidate 触发；
- artifact handoff 只由 Owner/stage 显式触发；
- `AGENTS.md` 是条件路由表；
- Codex P2P 保留，Main 仍拥有权限决策。
