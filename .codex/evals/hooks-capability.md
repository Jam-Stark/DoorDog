# Hooks Capability Assessment

## Status

`NOT_RUN`；当前 project **没有配置 hooks**。Capability evidence与 separate user approval之前，不创建 hook file、不修改 hook config。

## Decision Question

Codex project hook是否能可靠、fail-closed地机械执行 Main-only Git与dynamic write lease，而不会给出虚假的安全保证？

## Required Capability Evidence

Assessment 必须基于当前官方 schema与受控 runtime，逐项证明：

1. Event payload包含不可伪造的 agent/thread identity与Main/child distinction。
2. Payload包含 TASK_ID、REVISION或可安全关联 current task contract的 stable key。
3. Hook能访问 Main授权的 dynamic `WRITE_SET`/resource lease，并处理 concurrent atomic update。
4. Pre-command/pre-write event提供规范化 command、cwd、resolved target path；覆盖 shell、apply-patch、file tools与Git mutation。
5. Hook可以 atomic deny并向正确 agent返回明确 error；hook failure默认 fail-closed，而非 bypass。
6. Project trust、Desktop/CLI/IDE、sandbox、login/non-login shell与subagent surface覆盖范围明确。
7. Symlink、relative path、rename/delete、untracked/ignored file、multi-path patch与race不会绕过检查。
8. Audit log不泄露 secret，不允许 child篡改 lease state或log。

## Eval Plan

- 先做 docs/schema static review，不修改 config。
- 若所有 required fields受支持，再向 user提交 exact hook design、files、events、deny rules、rollback与test plan。
- User批准后只在 disposable fixture验证 allowed write、out-of-lease denial、child Git denial、Main Git allowance、hook error fail-closed与concurrent race。

## Verdict

- `SUPPORTED`：所有 identity/revision/dynamic lease/path/atomic deny/trust/shell coverage均有证据。
- `UNSUPPORTED`：明确缺少任一 mandatory enforcement capability；不创建 hook。
- `INCONCLUSIVE`：文档或runtime evidence不足；保持 no-hooks。

Prompt contract、Main ledger、candidate manifest与post-write audit继续是当前控制面。Hook只有在能提高mechanical enforcement且不削弱现有 fail-fast gate时才有正当性。

## Stopping Condition

输出逐项 evidence matrix与 verdict。只有 `SUPPORTED` + separate user approval 才进入 hook implementation；否则 `.codex/config.toml` 与 project tree保持无 hook配置。
