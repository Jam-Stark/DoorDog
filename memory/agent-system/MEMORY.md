# Codex Agent System Memory

本 subsystem 记录 repository-wide Codex multi-agent foundation、runtime compatibility 与 role rollout evidence。它不属于 A2_Piper product implementation，也不记录 live task ledger、heartbeat 或 mailbox message。

## Entries

- [architecture/description.md](architecture/description.md): canonical policy、Phase 2 role routing、lease/candidate/review/memory/Git gates。
- [runtime-compatibility/description.md](runtime-compatibility/description.md): project config/TOML、model catalog、strict startup 与 runtime observability evidence。
- [role-evaluations/description.md](role-evaluations/description.md): `ROLE_PROBE_V1` 与十角色 contract/runtime eval 状态。
- [production-role-rollout/description.md](production-role-rollout/description.md): Phase 2 direct registration、model/permission matrix、parallel waves 与后续 rollout gates。

## Evidence Rule

- `STATIC PASS` 只证明 files 可解析且内部一致。
- Runtime role/model/effort/sandbox/no-write evidence 不完整时只能记录 `NOT_RUN` 或 `INCONCLUSIVE`。
- Production profiles 已按 user 明确决定直接注册；effective runtime metadata 未暴露时仍必须保持 `UNKNOWN/INCONCLUSIVE`。
- Deep invocation、write-safety runtime eval 与 hook implementation 各自保留 separate user approval gate。
- Timestamp 使用 `YYYY-MM-DD HH:MM HKT`；entry 更新必须同步 `description.md`、`TODO.md` 与 `DONE.md`。
