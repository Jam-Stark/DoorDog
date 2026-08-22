# DoorDog A2_Piper — Jam Coding Role v1.2.0 本地替换包

本包用于把 DoorDog `A2_Piper` worktree 的 AI workflow 升级到 Jam Coding Role v1.2.0。
它只替换 agent/workflow/memory/artifact 配置，不修改机器人、IsaacLab、RL、训练或评估代码。

## 包内结构

```text
README.md                  使用说明
APPLY_PROMPT.md            交给本地 AI 的完整替换提示词
apply_doordog_v1_2.py      安全替换脚本
CHANGELOG.md               v1.2.0 版本日志
PACKAGE_MANIFEST.txt       完整文件清单
VERIFICATION.md            本包生成与验证记录
overlay/                    要复制到 DoorDog 仓库根目录的全部文件
```

## 快速执行

先预演：

```bash
python apply_doordog_v1_2.py --repo /path/to/DoorDog --dry-run
```

正式替换：

```bash
python apply_doordog_v1_2.py --repo /path/to/DoorDog
```

脚本默认执行两次本地 commit：

1. 把迁移前所有 Git 可见修改提交为回退点；
2. 应用 overlay、验证后提交 v1.2.0 迁移。

脚本不会执行 `reset`、`stash`、`clean`、`push`、force push，也不会强行把 ignored 训练产出加入 Git。

## 明确保留、不覆盖的路径

```text
.codex/config.toml
.codex/agents/
MEMORY.md
memory/a2-piper/
机器人与 RL 源码
logs_rl/、logs_eval/、checkpoint、render 等产出
```

## 回退

脚本结束时会打印：

```text
PRE_MIGRATION_COMMIT=<sha>
MIGRATION_COMMIT=<sha>
```

要回到迁移前状态，可在确认没有新工作后创建回退分支，或执行：

```bash
git revert <MIGRATION_COMMIT>
```

不建议直接 `reset --hard`，因为可能覆盖迁移后新增的工作。
