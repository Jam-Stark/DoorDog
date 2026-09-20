# C002 baseline Git anchor

固定本地tag：`v29-c002-baseline`；保留分支：`codex/v29-c002-baseline`。

本版本物化C001的320份冻结运行输入和C002新增Stage5 probe；源代码/配置/机器人资产位于正常仓库路径，不需要从正在训练的工作区动态加载。当前目录保存薄manifest及验收/配方来源，不复制整个训练输出或checkpoint。

`C002_CANDIDATE.json`中的待审状态属于提交时历史；后续`D060_C002_ACCEPTANCE_AND_TRAIN_APPROVAL.json`记录实现验收及原GPU0训练授权。该授权不随Git tag自动扩展到新的运行。

B05对照从本tag建立`codex/v29-handle-ablation`，在独立worktree实施。不要移动或覆盖本tag来混入ablation代码。
