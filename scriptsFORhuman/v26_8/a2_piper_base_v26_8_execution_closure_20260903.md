# base_v26-8 execution closure

日期：2026-09-03 21:59 HKT  
run_id：`v26_8_bilateral_opening_scaffold_decay_20260903`  
终态：`V26_8_NOT_ADMITTED_G1_RUNTIME_ASSET_FAILURE`

## Result

v26-8 的最小实现与 G0 已完成；G1 `K_S1` 64-env/5-batch wiring smoke 在 Isaac scene
construction 阶段非零退出。按冻结 plan §6/§8.3 与 Owner 硬规则，本阶段在第一次 K 格 fail-fast
后立即停止，没有重跑、修改 config、放宽阈值或追加预算。Wave 1 六格、全部 milestone eval、endpoint
reducer 与 Wave 2 均未启动。

typed outcomes：

| 问题/分支 | Outcome | 原因 |
|---|---|---|
| G0 | `STATIC_PASS / TEST_PASS` | source lock、六格 compose、source digest、16 项名单与 5 类 CPU 单元门通过 |
| G1 | `NOT_ADMITTED` | `K_S1` 在 policy load 前的 Isaac scene construction 非零退出 |
| Q_A / W | `NOT_RUN` | G1 未通过，Wave 1 未准入 |
| Q_K / K | `NOT_RUN` | G1 未产生 driver runtime trace，不能给 curriculum outcome |
| Wave 2 B1 | `NOT_RUN` | Wave 1 closure 条件不可判定 |
| Wave 2 B2 | `NOT_RUN` | `W_STAGE34_SUPPORTED` 与 `K_SUPPORTED` 均未产生 |

## G0 evidence

- Git source commit：`b228bb0c81380618160a61166d4be208d1eb1b45`；dirty worktree 全量状态已写入
  `scriptsFORhuman/v26_8/runtime_logs/v26_8_bilateral_opening_scaffold_decay_20260903/source_lock.json`。
- source lock：20 个 v26-8 source/config/script/test 文件；状态 `STATIC_PASS`。
- `SRC_S1` SHA-256：`a683257213aaba82b583924d841235f772182f53113e513e16c8d27bcb394df1`；匹配。
- `SRC_S2` SHA-256：`0b2f739f020b056adb2fb47105fdb5bc00d1d1189ef331d42332b3e0740e54ec`；匹配。
- 六格均解析为 `policy_only + policy_only_load_actor_rms=true`、4096 env、3000 batches、save250、
  正确 source/seed/GPU；K 两格显式清空继承的 legacy goal-rate driver。
- 冻结 16 项在两个 source resolved `reward_scales` 中全部非零且逐项一致。
- CPU tests：`gr00t/rl/tests/test_a2_v26_8_penalty_curriculum.py`，`6 passed`。覆盖 hysteresis
  decay/restore/clip、同 episode start/max 配对、zero/unknown 名单 fail-fast、缺 driver 时 legacy
  delegate、scale 1.0 reward bit identity。

证据等级：`STATIC_PASS`、`TEST_PASS`。

## G1 failure evidence

- tmux / run receipt：`v26_8_g1_wiring`；receipt 最终为 `FAIL`，`process_returncode=1`。
- root cause：Isaac scene construction 调用本机 IsaacLab `spawn_ground_plane` 时无法打开
  `https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/5.1/Isaac/Environments/Grid/default_environment.usd`，
  抛出 `FileNotFoundError`。
- scene creation 用时约 160 秒；失败发生在 `custom_instantiate(config.env, ...)` 内，早于 trainer
  construction 与 policy load。没有 policy step、step5 checkpoint、K JSONL trace、load receipt 或
  `g1_wiring.json`。
- 原始 stdout/stderr：
  `logs_eval/base_v26/v26_8_bilateral_opening_scaffold_decay_20260903/G1_k_wiring/K_S1_smoke/train_runtime.log`。
- supervisor log：
  `scriptsFORhuman/v26_8/runtime_logs/v26_8_bilateral_opening_scaffold_decay_20260903/g1/g1.log`。
- machine-readable adjudication：
  `logs_eval/base_v26/v26_8_bilateral_opening_scaffold_decay_20260903/G1_k_wiring/g1_failure.json`。

证据等级：`RUNTIME_FAIL`（construction only）；不构成 policy、training 或 experiment evidence。

## Source / plan reconciliation

1. W threshold 除了延长 `a2_stage3_unlatch_hold`，还改变 v22 `unlatched` failure latch；v26-2
   historical telemetry band 仍固定为 `[0.1,0.25)`，Stage3→4 入场线仍由独立 0.25 key 控制。
2. 现行 v26-5 官方 train load-receipt writer 强制读取 residual-only optimizer partition，无法用于本阶段
   legacy actor。v26-8 没有修改 trainer 或切换 loader；实现了仅在普通 strict policy-only 成功行出现后
   写 receipt 的 v26-8 stream wrapper。G1 在到达该路径前已失败，因此没有伪造 receipt。
3. source artifact `Q05_S1 LEFT complete=62/64` 仅保留为非路由观察；本阶段没有 continuation 读数，
   不对其趋势作结论。

## Milestone tables

没有 step500–3000 milestone。因而不存在逐格逐侧 D/S3+/S4+/open_hold/S5+/complete、同 source
paired arm−C、K scale/driver trajectory、integrity 或 milestone receipt 表。将这些项写成 0 会伪造
denominator，故统一记为 `NOT_RUN`，而不是 0/64。

## Changed paths

- Core：`gr00t/rl/envs/door/door_open_a2_base.py`
- Tests：`gr00t/rl/tests/test_a2_v26_8_penalty_curriculum.py`
- Configs：`gr00t/rl/config/ablation/wbmanip/base_v26_8_common.yaml` 与
  `base_v26_8_{C,W,K}_S{1,2}.yaml`
- Scripts：`scriptsFORhuman/v26_8/v26_8_{orchestrate,train_cell,eval_cell,eval_lane,g1_wiring_gate}.sh`，
  `v26_8_{capture_train,g1_reduce,reduce,verify}.py`
- Docs：本 closure 与 `a2_piper_base_v26_8_g0_source_appendix_20260903.md`
- Memory：`memory/a2-piper/base-v26-scratch-bilateral-teacher/{description,TODO,DONE}.md`
- Runtime artifacts：上述 G0 source lock/unit gate、G1 logs/failure JSON、supervisor receipt。

没有修改 v26-7 artifact/script、reward 函数或 scale、stage 判据、trainer 加载路径、Teacher/Student
handoff、G7 或任何 hardware 路径。

## Not run / resources

- Wave 1 train：六格全部 `NOT_RUN`。
- milestone 500/1000/1500/2000/2500/3000：全部 `NOT_RUN`。
- endpoint reducer / typed W/K experiment outcomes：`NOT_RUN`。
- Wave 2 B1/B2：`NOT_RUN`。
- hardware / sim-to-real：`NOT_RUN`。
- Git commit/push：未授权，未执行。

收尾后应无活跃 v26-8 writer、tmux、IsaacSim 或 GPU lease。代码与 G0 证据可保留；若 Owner 后续另行
授权重新执行，必须使用新 run/output root，不能覆写本次 G1 failure artifact。

## Commit request

当前未 commit。请 Owner 在审阅本 closure 与 G1 failure 后决定是否授权提交 v26-8 实现、G0 文档与
memory 更新；本任务不会自行 commit 或 push。
