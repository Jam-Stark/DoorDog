# Package verification

本包是对先前空 ZIP 的重新打包版本。验证基于包内真实文件，不代表已经写入用户的生产工作树。

## Archive

- 包内普通文件：39 个；
- ZIP 使用 DEFLATE 压缩；
- `zipfile.testzip()`：无坏文件；
- `unzip -t`：全部条目通过；
- 解压后不存在空 overlay，也不包含 `__pycache__` 或 `.pyc`。

## Static validation

- `apply_doordog_v1_2.py` 与 `.ai/scripts/*.py`：Python syntax compile 通过；
- `.codex/hooks.json`、`opencode.json`、`.claude/settings.json`、`.omo/omo.jsonc`：JSON 解析通过；
- `.ai/team-state.toml`、`.ai/artifact-targets.toml`、`.ai/artifact-sync.toml`：TOML 解析通过。

## Synthetic migration rehearsal

在临时 Git 仓库中建立以下条件：

- 一个已有提交；
- tracked dirty file；
- visible untracked file；
- ignored `logs_rl` artifact；
- 现有 `.codex/config.toml`；
- 现有 `.codex/agents/worker.toml`。

随后执行 dry-run 和正式迁移，结果：

- 创建迁移前 checkpoint commit；
- 创建独立 v1.2.0 migration commit；
- `.codex/config.toml` 与 `.codex/agents/worker.toml` 字节保持不变；
- ignored `logs_rl` artifact 仍存在且未被纳入提交；
- 迁移后 worktree clean；
- team ledger 初始化与 snapshot 通过；
- task contract validation 通过；
- candidate freeze、verdict、P2P message metadata 写入通过；
- 绑定路径变化后 verdict 被标记为 `INVALID`；
- `git push`、IsaacLab、训练、评估、Drive 上传和硬件动作均未运行。
