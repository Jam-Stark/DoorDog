# Workflow 1.4.0 本机修复与未解决事项

更新：2026-09-12；适用宿主 codex-cli 0.153.0，DoorDog-A2_Piper linked worktree。

## 当前替换结论（以最新复测为准）

v1.4.0文件与本机接入已完成，保留一个已知宿主缺陷：角色context/compact不生效，Owner已要求暂停修复。
四项hooks加载/信任PASS，真实SessionStart调用PASS；其他hook事件与独立hook完成退出状态未逐项验证。
当前任务原生sleep360完成exit0，一次empty write_stdin实际353.210386087秒，无300秒截断或二次轮询；原先将默认范围视为硬上限的结论被实测推翻。未验证24h等待、Desktop配置热加载或idle wake。
最新证据：`.ai/runtime/workflow-v140/HOOKS_RETEST.md`。以下“待信任”“sleep360未执行”“消息未送达”是当时的历史记录，不是当前验收状态；目标测试任务已完成后续复测。

## Hooks 发现：已修复接入，执行待信任

**问题**：项目 config.toml 正常读取，hooks/list 却为空。系统调用证明只查主 checkout `GR00T-VisualSim2Real/.codex/hooks.json`。四个 hook 本身没有 JSON 解析错误，hooks feature 已开启。

**根因**：0.153.0 的 linked-worktree loader 有意通过 `hooks_config_folder_override` 从 root checkout 取 hooks，并在 `merge_root_checkout_project_hooks()` 中移除 worktree 自己的 inline hooks。因此最初“内联到当前 config 即可”的判断不成立；实际迁移无效后已撤回。CLI `-c hooks...` 成功只证明 session-flags 来源可用，不能证明 project 来源可用。

源码：[loader/mod.rs](https://github.com/openai/codex/blob/rust-v0.153.0/codex-rs/config/src/loader/mod.rs#L1830-L1853)。本机路径证据与旧验证见 `.ai/runtime/workflow-v140/HOST_VALIDATION.md`。

**修复**：保留 `.codex/hooks.json` 为本项目声明源；新增 `.ai/scripts/install_codex_hooks.py`，将四个入口同步到 `~/.codex/hooks.json`。每个命令先比较 `git rev-parse --show-toplevel` 与本工作区绝对路径，仅本工作区执行脚本，其他项目跳过。保留无关 user hooks，不改主 checkout 或全局 config.toml；更新已有本工作区注册时按明确 statusMessage 标记替换。

```bash
python3 .ai/scripts/install_codex_hooks.py
```

更改本项目 hooks 或移动 worktree 后需重新登记；若移动路径，先删除旧路径对应的注册。不维护两份手工修改的声明。该用户级登记是本机适配，未来版本若改变 linked-worktree 规则再重新决定来源。

**证据**：严格 app-server 初始化成功；hooks/list 真实返回 preToolUse、postToolUse、sessionStart、postCompact 四项，enabled=true、trustStatus=untrusted，无 warnings/errors。见 `.ai/runtime/workflow-v140/hooks-fixed.json`。识别已通过，尚未证明真实事件执行。

**待用户操作**：在 Codex `/hooks` 审阅并信任这四个入口，再验证实际 SessionStart/工具生命周期。未代写信任、未绕过信任、未用直接执行 helper 冒充宿主触发。[官方 hook 信任规则](https://learn.chatgpt.com/docs/hooks)。

## 全局模型字段位置错误：已修复

`~/.codex/config.toml` 的 `[shell_environment_policy]` 下误放了 `model` 和 `model_reasoning_effort`。0.153.0 strict-config 拒绝这两个未知字段。Owner 已授权删除，严格初始化已通过；项目 Main model/effort 仍由 App/用户选择，未移动或重设模型。该问题已修复，不应再列为 blocker。

备份：`/home/baoquanc/.cache/codex-config-cleanup-z1dq6ynb/config.toml`。

## 子任务 context/compact 继承：未修复，实测不符

测试任务 `01a09513-a8b1-7af3-a0e0-107f791c99b2` 的 explorer/Luna/high/fork_turns=none 实际 model、effort、Total 生效；有效窗口490200、compact464400，未使用角色196608/163840。有效窗口不是原始model_context_window；490200恰为Main516000的95%。不能仅看角色TOML就宣称隔离成功。本次hooks修复不解决宿主的角色预算继承。证据：`child-budget-telemetry.json` 与 HOST_VALIDATION.md。

## 长等待与 idle wake：未验收/未实现

配置读取支持86400000ms，但任务工具schema仍声明300000ms，上层另限制长阻塞等待；sleep360未执行。配置可解析不等于当前Desktop transport支持24h；也不能由tmux完成或outbox推断idle wake。

## 其他边界

- bubblewrap user namespace警告独立存在，未证明它导致hooks发现失败；执行阶段若遇到具体错误再处理。
- v1.4 supervisor不兼容旧receipt/CLI；已关闭v26/v27历史callers未迁移，当前v28无此依赖，不可拿旧命令直接重启。
- 包内哈希写入已按Owner要求移除；升级工具未用于本机迁移。memory去重直接比较规范化字段。
- 本轮未commit/push、训练或硬件操作。hooks原定义与项目config备份在 `/home/baoquanc/.cache/doordog-hooks-fix-1xiuk1q2/`；用户hooks此前不存在，回滚只移除本工作区四项，保留后来新增的其他入口。

## 指定测试任务交接

目标：`codex://threads/01a09513-a8b1-7af3-a0e0-107f791c99b2`。
当前工具没有send_message_to_thread；通过官方`codex exec resume <id> -`尝试发送原任务续测说明，但宿主报`thread-store conflict ... already has an active writer`，消息未送达。未抢占writer、未修改其持久化状态。
续测说明已落盘：`.ai/runtime/workflow-v140/HOOKS_RETEST_REQUEST.md`；发送失败原文：`hooks-worker-dispatch-error.log`。目标worker只需确认当前四项发现状态，待用户信任后再验证实际事件，不重跑模型矩阵或长等待。此次CLI续接失败，没有启动新的测试模型任务。
