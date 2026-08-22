# 交给本地 AI 的 DoorDog v1.2.0 替换 Prompt

你正在本地生产机器上更新 `Jam-Stark/DoorDog` 的 `A2_Piper` worktree。请从本压缩包根目录执行工作。

## 目标

把 `overlay/` 中的 Jam Coding Role v1.2.0 文件安全地应用到 DoorDog 仓库根目录，同时：

- 迁移前先提交当前所有 Git 可见修改，建立明确回退点；
- 不覆盖 `.codex/config.toml` 与 `.codex/agents/*.toml`；
- 不修改机器人、IsaacLab、RL、训练、评估和硬件代码；
- 不删除、移动、清理或强行提交 ignored 训练产出；
- 完成解析、脚本编译、team-state 初始化和路径边界检查；
- 只在本地提交，不 push。

## 必须执行的顺序

1. 定位实际 DoorDog `A2_Piper` worktree，并确认 `git rev-parse --show-toplevel` 指向目标仓库。
2. 检查是否存在 unresolved conflict、merge、rebase、cherry-pick 或 revert。存在时停止，不自动修复。
3. 记录迁移前：
   - branch 与 HEAD；
   - `git status --short`；
   - `.codex/config.toml` 和 `.codex/agents/` 的文件清单。
4. 执行 `git add -A`，把所有 Git 可见修改提交为：

   ```text
   chore: checkpoint before AI workflow v1.2.0 migration
   ```

   如果工作树本来干净，不制造空提交，直接把当前 HEAD 作为回退点。ignored 文件保持原状。
5. 先运行：

   ```bash
   python apply_doordog_v1_2.py --repo /path/to/DoorDog --dry-run
   ```

6. 预演没有阻断项后运行：

   ```bash
   python apply_doordog_v1_2.py --repo /path/to/DoorDog
   ```

   脚本会自行完成第 4 步；若你已经手工提交，它会识别工作树干净，不再生成空提交。
7. 替换后必须确认：
   - `.codex/config.toml` 未发生字节变化；
   - `.codex/agents/` 原有文件未被删除或覆盖；
   - `MEMORY.md`、`memory/a2-piper/` 未被覆盖；
   - 只出现 workflow/agent/memory-governance/artifact 相关修改；
   - JSON、TOML 与 `.ai/scripts/*.py` 验证通过；
   - `.ai/runtime/team/team-snapshot.json` 已生成，但 `.ai/runtime/` 被 Git 忽略；
   - 最终 migration commit 存在；
   - 没有 push。
8. 最终报告：

   ```text
   Result
   PRE_MIGRATION_COMMIT
   MIGRATION_COMMIT
   Changed paths
   Protected paths verified
   Static verification
   Not run
   ```

## 禁止事项

- 不使用 `git reset --hard`、`git stash`、`git clean`；
- 不修改全局 `~/.codex/config.toml`；
- 不修改 `.codex/config.toml` 的模型、effort 或并发设置；
- 不重新生成或替换 `.codex/agents/*.toml`；
- 不运行 IsaacLab、训练、formal eval 或硬件动作；
- 不上传 Google Drive，除非 Owner 在本次任务中另行明确要求；
- 不把“静态解析通过”写成 runtime/training pass。
