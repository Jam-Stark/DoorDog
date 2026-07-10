# Codex Agent System Memory

本 subsystem 记录 repository-wide Codex multi-agent foundation、runtime compatibility 与 role rollout evidence。它不属于 A2_Piper product implementation，也不记录 live task ledger、heartbeat 或 mailbox message。

## Entries

- [architecture/description.md](architecture/description.md): canonical policy、team architecture、lease/candidate/review/memory/Git gates 与 Phase 0A/1 boundary。
- [runtime-compatibility/description.md](runtime-compatibility/description.md): project config/TOML static evidence、Codex startup evidence 与 runtime activation blocker。
- [role-evaluations/description.md](role-evaluations/description.md): `ROLE_PROBE_V1` sentinel、role-discovery eval contract 与 production activation gate。

## Evidence Rule

- `STATIC PASS` 只证明 files 可解析且内部一致。
- Runtime role/model/effort/sandbox/no-write evidence 不完整时只能记录 `NOT_RUN` 或 `INCONCLUSIVE`。
- Production roles、deep-research TOML、hooks 与 parallel writers 只有在 runtime activation PASS 且取得 separate user approval 后才能 rollout。
- Timestamp 使用 `YYYY-MM-DD HH:MM HKT`；entry 更新必须同步 `description.md`、`TODO.md` 与 `DONE.md`。
