# base_v26-8 r2 execution closure

日期：2026-09-04 00:14 HKT  
run_id：`v26_8_bilateral_opening_scaffold_decay_20260903_r2`  
终态：`V26_8_NOT_ADMITTED_G1_R2_K_NATURAL_PAIRING_GATE_FAILURE`

## Result

Owner 授权的 §13 G1 r2 已按冻结协议执行。`P0_ASSETS` 对两个冻结 Isaac 资产均得到 HTTP 200，
receipt command 明确记录六项 proxy 环境，r2 使用全新 `_r2` root；旧 G1 failure artifact 未被修改。
K_S1 smoke 随后成功构造 64 env、strict policy-only 加载 actor 与 actor RMS、执行 5 batches 并写出
step5 checkpoint 和 35 行 K trace，但 G1 reducer 因从未在同一次 curriculum update 同时观察到
LEFT/RIGHT natural sample 而 fail-fast，外层 G1 receipt 为 `FAIL/1`。

本次失败发生在 policy load 与 policy step 之后，明确不属于
`INFRA_FAILURE_BEFORE_POLICY_LOAD`，因此 §13 不允许继续 relaunch。按 Owner 的 K 格 fail-fast 硬规则，
Wave 1 未启动；没有修改 config、K code、threshold、reward scale、stage 判据或 trainer loader，也没有
重跑、放宽阈值或追加预算。

typed outcomes：

| 问题/分支 | Outcome | 原因 |
|---|---|---|
| G0 | `STATIC_PASS / TEST_PASS` | 复用已验收 G0；r2 source lock 与逐文件 contract lock 均 PASS |
| P0_ASSETS | `P0_ASSETS_PASS` | `default_environment.usd` 与 `Ash.mdl` 均 HTTP 200 |
| G1 r2 | `G1_FAIL_K_NATURAL_PAIRING_GATE` | 35/35 update skipped；任一 update 的双侧 natural sample 从未同时非零 |
| Q_A / W | `NOT_RUN` | G1 未准入，Wave 1 未启动 |
| Q_K / K | `NOT_RUN` | G1 只产生 wiring failure，不能给 Wave 1 curriculum outcome |
| Wave 2 B1 | `NOT_RUN` | Wave 1 endpoint/typed K outcome 不存在 |
| Wave 2 B2 | `NOT_RUN` | `W_STAGE34_SUPPORTED` 与 `K_SUPPORTED` 均不存在 |

## G0 and r2 contract evidence

- 已验收 G0：`logs_eval/base_v26/v26_8_bilateral_opening_scaffold_decay_20260903/G0_static_unit/g0_unit.json`
  为 `G0_PASS`；CPU test 为 `6 passed`。
- r2 static lock：
  `scriptsFORhuman/v26_8/runtime_logs/v26_8_bilateral_opening_scaffold_decay_20260903_r2/source_lock.json`，
  `STATIC_PASS`，Git HEAD `aa8a05fbbba62600ee2ac87cd1ad16f1bffa03e5`。
- r2 contract lock：同目录 `r2_contract_lock.json`，`R2_CONTRACT_PASS`。17 个 baseline-locked
  experiment 文件逐字节不变；允许差分逐文件列明为 plan §13、orchestrator、child-process receipt
  wrapper。六格 config、K core、test、train/eval/reducer、source checkpoint 选择均未改变。
- `SRC_S1` SHA-256：`a683257213aaba82b583924d841235f772182f53113e513e16c8d27bcb394df1`；匹配。
- `SRC_S2` SHA-256：`0b2f739f020b056adb2fb47105fdb5bc00d1d1189ef331d42332b3e0740e54ec`；匹配。
- 两个获批本地 commit 已完成：`e3d496b`（v26-6/v26-7）与 `aa8a05f`（v26-8）；未 push。

证据等级：`STATIC_PASS`、`TEST_PASS`。

## P0_ASSETS and receipt evidence

- P0 artifact：
  `scriptsFORhuman/v26_8/runtime_logs/v26_8_bilateral_opening_scaffold_decay_20260903_r2/p0_assets/v26_8_g1_wiring_r2.json`。
- 两项请求均为精确 `curl -sI --max-time 20 <URL>`，return code 0、最终 HTTP status 200。
- P0 与 receipt command 都固定：
  `http_proxy/https_proxy/HTTP_PROXY/HTTPS_PROXY=http://127.0.0.1:18889`，
  `no_proxy/NO_PROXY=localhost,127.0.0.1`。
- supervisor receipt：`.ai/runtime/runs/v26_8_g1_wiring_r2/RUN_RECEIPT.json`，最终 `FAIL`，
  `process_returncode=1`；其 command 含完整 `env KEY=VALUE` 前缀。

证据等级：`RUNTIME_PASS`（asset reachability）与 `RUNTIME_FAIL`（G1 outer gate）。

## G1 r2 runtime evidence

resolved contract：`K_S1`、seed1、64 env、5 batches、save5、staged reset、SRC_S1、
`policy_only + policy_only_load_actor_rms=true`、K driver target Stage4、0.5/0.7 hysteresis，均匹配。

- Isaac train child：return code 0；capture wrapper：return code 0；strict load line observed。
- load receipt：`POLICY_LOAD_CONFIRMED`，`actor_rms_loaded=true`、`strict=true`、
  `state_key=policy_state_dict`，source SHA-256 匹配。
- checkpoint：`K_S1_smoke/model_step_000005.pt`，存在。
- K trace：35 rows，`common_step=0..309`；`scale_min=scale_max=1.0`。
- natural sample rows：LEFT positive `12`，RIGHT positive `22`，both positive `0`；总 sample 同为
  LEFT `12`、RIGHT `22`。全部 35 rows 为 `skipped=true`。
- G1 reducer 未写 `g1_wiring.json`，而是精确抛出
  `RuntimeError: G1 never observed natural samples on both sides`；因此外层 G1 gate return code 1。
- machine-readable adjudication：
  `logs_eval/base_v26/v26_8_bilateral_opening_scaffold_decay_20260903_r2/G1_k_wiring/g1_failure.json`。

这证明 proxy/asset 与 strict load 问题已排除，也证明 scale 没有在缺侧样本时错误变化；但没有满足
G1 §6.2 的双侧同更新接线门，不能把单侧各自曾出现样本改写为 PASS。

证据等级：`RUNTIME_FAIL_AFTER_POLICY_LOAD_AND_5_BATCHES`；不是 Wave 1 experiment evidence。

## Milestone table and historical reversal

step500–3000 均未运行，因此不存在逐格逐侧 D/S3+/S4+/open_hold/S5+/complete、同 source
arm−C、K scale trajectory、integrity 或 train receipt 表。这些值统一为 `NOT_RUN`，不能写成 0/64。
Q05_S1 source 的 LEFT `complete=62/64` 仍只作为既有非路由观察；本阶段没有反向或延续读数。

## Source / plan reconciliation

1. 当前 `v26_8_reduce.py` 对 resolved config、source SHA、exact64 或 trace schema 失败会直接
   fail-fast，而不是先写含 per-cell `V26_8_INVALID` 的 reducer JSON；integrity 非零才会写 invalid JSON。
   这是当前 source 与 prompt 期望 artifact 形态的差异。因 Wave 1 未运行而未触发；按照 source authority
   如实记录，未在 §13 的零实验改动 relaunch 中修改 reducer。
2. 当前 generic supervisor receipt 不自动嵌入 source SHA/load receipt/source lock；原计划在 Wave 1
   launch 后、finalize 前由 Main 把这些 provenance 字段结构化写入六格 receipt。因 Wave 1 未启动，
   没有训练 receipt，也没有伪造该交付物。
3. r2 child-process receipt 将 Isaac train child 与 capture wrapper return code 分开记录；外层 G1 shell
   的 return code 1 来自 reducer gate，三者不能混写。

## Changed paths and commits

已提交实现：

- Core：`gr00t/rl/envs/door/door_open_a2_base.py`
- Configs：`gr00t/rl/config/ablation/wbmanip/base_v26_8_common.yaml` 与六个 cell YAML
- Tests：`gr00t/rl/tests/test_a2_v26_8_penalty_curriculum.py`
- Scripts/docs：`scriptsFORhuman/v26_8/`（含 plan、G0 appendix、attempt1 closure、r2 P0/contract support）
- Memory：`memory/a2-piper/base-v26-scratch-bilateral-teacher/{description,TODO,DONE}.md`

本 closure 后新增或更新、尚未提交：

- `scriptsFORhuman/v26_8/a2_piper_base_v26_8_execution_closure_20260904.md`
- `memory/a2-piper/base-v26-scratch-bilateral-teacher/{description,TODO,DONE}.md`
- r2 runtime roots、G1 artifact 与 `.ai/runtime/runs/v26_8_g1_wiring_r2/`

明确未修改 v26-7 artifact/script、reward 函数或 scale、stage 判据、trainer 加载路径、Teacher/Student
handoff、G7 或 hardware 路径。`scriptsFORhuman/knowledge_recap/` 与 `scriptsFORhuman/pro_reviews/` 是既有
无关 untracked 内容，未纳入两个 commit，也未修改。

## Not run and resource closure

- Wave 1 六格训练：全部 `NOT_RUN`。
- milestone 500/1000/1500/2000/2500/3000 与 endpoint reducer：全部 `NOT_RUN`。
- Wave 2 B1/B2：全部 `NOT_RUN`；无可满足的 §9 前置结果，禁止启动。
- hardware / sim-to-real / Teacher/Student handoff / G7 update：全部 `NOT_RUN`。
- push：未执行。

v26-8 r2 的 Isaac process 与 tmux 已退出；GPU0 上仍有 Owner 已说明可共存的独立 sim2sim process，
不属于 v26-8，未干预。收尾时释放全部 v26-8 leases，并确认无 v26-8 writer、tmux 或排他资源。

## Commit request

Owner 授权的两次 commit 已用完。请 Owner 审阅本 r2 closure 后，决定是否另行授权提交 2026-09-04
closure 与最终 memory 更新；本任务不会自行创建第三个 commit，也不会 push。
