---
name: pull-open-door-task
scope: A2+Piper pull-door v0 foundations + pull-v1/v2 Stage3→4 + pull-v3 traversal closure
status: active
last_updated: 2026-08-11 00:03 HKT
owned_paths:
  - memory/a2-piper/MEMORY.md
  - memory/a2-piper/pull-open-door-task/description.md
  - memory/a2-piper/pull-open-door-task/TODO.md
  - memory/a2-piper/pull-open-door-task/DONE.md
read_when:
  - 继续 pull-v4 frame-neighborhood traversal 或复用 pull-v3 release-then-cross 证据前
  - 需要区分 v3 G2(c) traversal negative、v2 wall-removal runtime closure 与 v1/v0 历史边界时
---

# Pull-Open-Door Task (v0 foundations + v1/v2/v3 closure)

## Purpose

记录 A2+Piper pull-door v0 foundations、pull-v1 physical-gate negative closure、pull-v2 wall-removal/Stage4 occupancy closure 与 pull-v3 release-then-cross traversal negative closure 的 direction contract、static-vs-runtime evidence boundary、reproducible commands、当前 TODO/DONE。不复制 raw trace 或长日志；只保存可复用结论。

## Pull-v3 Closure (2026-08-11 00:03 HKT)

- North Star 固定为 `aperture_ready → deliberate release → through-frame → whole-body clear to -X`，不做 hold-through。C1–C7 已落地：v3 guard、Stage4/5 时间预算 `250/300` 与 `24 s` episode、frame-passage 门框谓词、aperture 后 open-command penalty 遮罩、仅两项 corridor reward（`4.2666667/1.0`）、signed trunk-footprint-to-current-panel clearance/base path/reversal/recontact telemetry，以及 `pull_v3_T_traversal.yaml`。`penalty_a2_v20_pre_send_crossing` 未移植，其余 reward scale/threshold 未改。
- Frozen pull-v2 Wave2 actor 的 canonical D0-lite 为 16×804 steps：E6/E7 均为 `0/16`，六项 invariant 全零，corridor 在 aperture 前激活为零；单次 64×50 smoke natural exit。Wave1 两 seed 均为 256 env×750 batches，step250/500/750 checkpoint 齐备；六个 checkpoint 各 eval 16 episodes，Stage4 admission 为 seed0 `16/15/15`、seed1 `16/16/16`，六项 invariant 每格全零。
- Wave1 六格 E6/E7/complete 全为零，双 seed 同判 `G2`，不触发 Wave2 或 seed2。具体为 G2(c)：deliberate release 依次为 seed0 `7/16,2/16,0/16`、seed1 `1/16,0/16,0/16`，发生 release 的 episode 均观测到 −X motion，但所有格 frame-approach/frame-passage/planar-crossing/detour 仍为零。结论是 traversal approach/path-distribution 的科学负结果；本轮未追加或修改 reward scale，下一候选仅预登记 v4 frame-neighborhood/path shaping。
- G10 触发：seed0 step500 的 post-release recontact 最大 `18`（median `0`）；只在 pull longterm TODO 第 1 条勾稽 arm brace 期货，本轮不实现。G5 未触发（六格 panel-contact median 均为 `0`），G6 未触发。
- Durable trace contract：`stage2_5_step_trace` 只覆盖 terminal `stage_buf∈{2,3,4,5}`；terminal diagnostics 仍必须完整覆盖 16 episodes 并作为 E0–E7/complete 分母。stage0/1 terminal 无 trace row 是合法域外，不得误判为丢行，也不得把真正的 stage2–5 缺行降级为零。
- Review evidence boundary：唯一一轮 code/IsaacLab review 的正式 verdict 为 FAIL；C6 signed clearance 与 analyzer/orchestration/report findings 已定向修复，修复后由 targeted static checks、canonical D0、smoke、formal train/eval 与 fail-closed analysis 验证。依用户“一轮 review 上限”未生成第二轮 reviewer PASS，不得把它表述为 review PASS。

## Pull-v2 Closure (2026-08-10 09:32 HKT)

- Canonical deterministic U-probe（无机器人）测得 `theta*=0.6 rad`，回填 `a2_pull_e3_latch_threshold_m=0.02292371541261673`；θ=0 时 hinge max `0.001943 rad`，G5/G6 均未触发。第一次 sampled-fixture receipt 已标记 invalid，不作为标定证据。
- V2-W 从 v1-R seed0 step750 `policy_only` warm start。唯一 reward 改动是 `a2_stage3_unlatch_near_closed_hinge_threshold 0.1→0.25`；`UNLATCH_NORM=0.6`、速度 norm、`dont_push_door_handle`、`target_root_distance` 与 Stage3→4 hard gate 均未改。E3 改用 calibrated latch threshold + stable contact，handle/latch 双口径 stable-unlatch/relock 进入 telemetry。
- 单次 64×50 smoke 验证 v2 plan-id、训练路径与 resolved `near_closed=0.25`；它发生在 canonical probe 回填之前，resolved latch threshold 为 sampled attempt 值，因此只构成 smoke acceptance，不构成 canonical E3 runtime calibration PASS。Wave1/Wave2 formal resolved config 使用 canonical threshold。
- Wave1 双 seed 触发 G1：step750 true Stage3→4 为 seed0 `10/16`、seed1 `6/16`，valid-hold hinge Δ max 为 `0.749745/0.492656 rad`；dwell `0.105–0.25` 为 `1997/1193`，不再是 v1 恒零墙。最佳 Wave1 seed0 step750 relay 进入 Wave2。
- Wave2 六格 true Stage4 依次为 seed0 `13/16,14/16,15/16`、seed1 `11/16,16/16,16/16`；step750 hinge Δ max `2.527259/2.617994 rad`。Wave1+Wave2 共 12 cell、192 terminal episode，四项 integrity invariant 每格均为零；A0 因 G3 false 而 `NOT_TRIGGERED`。下一 round 转 traversal/V1-C，不在 v2 继续追加 reward seam。
- Review evidence boundary：唯一一轮 code/IsaacLab review 的正式 verdict 为 FAIL；其 seed forwarding、E3 predicate、analyzer、U-probe fixture/GPU binding 与 orchestration findings 已定向修复。依用户“一轮 review 上限”未生成第二轮 reviewer PASS；修复后的 acceptance evidence 来自 Hydra/static check、canonical U-probe、smoke、两轮训练/eval 与 fail-closed analysis。不得把它表述为第二轮 review PASS。

## Pull-v1 Closure (2026-08-09 15:19 HKT)

- C1–C6 的 Stage3→4 hard gate、event semantics 与 V1-A/B/R configs 已完成；static validation 为 Python compile PASS、YAML/Hydra composition PASS。namespace suite 为 `148 passed / 4 failed`，四项为缺失历史 Kit logs 的无关 fixture，未修复。
- D0 frozen replay runtime PASS：16/16 终止 episode 均停在 Stage3，E4/E5 均为 0，四项 semantic/integrity invariant 均为零。V1-B 64 env × 50 batch smoke natural exit。
- V1-A/V1-B/R 双 seed formal training 与 checkpoint eval 均完成。18 个 accepted v1 cell×checkpoint、288 terminal episodes 的 true Stage3→4（`hinge>0.25 ∧ grasp-streak ∧ panel_clear`）均为 0；每行四项 integrity invariant 均为 0，不能宣称真实 Stage4 capability PASS。
- A/B 的 valid-hold hinge Δ max ≤0.002201 rad，双 seed stable unlatch 均为 0。R 的 `pull_door_handle` reward port 行为上 active：step750 stable unlatch 为 seed0 13/16、seed1 2/16；R0 hinge Δ max 0.100607 rad 仍低于 0.25 gate，R1 保持 baseline scale。预注册“reward 迁移不是主要瓶颈”negative 未触发。
- R 的两次 construction-guard defect 都在 batch1 前按 root cause 修复；最终 A/B/R exact config/runtime contracts fail fast，第三次 R launch 每 seed natural exit。下一 scope 仅比较 R0/R1 与 matched A/B 的 handle-frame force direction、arm/base trajectory、grasp stability 与 hinge torque transfer；不要先启动 V1-C 或另一轮 broad reward sweep。

## Governing Design

- 三条 binding amendments（split doc §2 确认）：
  1. Pull-side P1 verdicts require a passing push-side known-good anchor first。Anchor FAIL → `PROBE_INVALID`，不算 mechanism finding；one-shot scientific verdict 不消耗。
  2. P1 central fixture mass = 120 kg（resolved v20 G4 `[80,160]` midpoint）。
  3. Pull plan-id freeze-guard + regression tests precede env/asset changes。
- Anchor/review order: repair → targeted tests → push anchor → freeze → code_reviewer → isaaclab_reviewer → unlock P1 pull matrix → P2（P2 需 explicit GPU allocation）。
- Anchor admission reruns 不消耗 one-shot scientific verdict；只有 admission 通过且 anchor 完成才消耗。
- Thresholds 保持 `report_only`；inapplicable metrics 用 N/A；implicit-actuator effort 标 `ESTIMATE_ONLY`。

## Direction Contract

- Production pull-cell handle command 必须产生 door-frame +X force（toward robot / tension），不是 world -X compression。
- Proof direction: world +X（door-frame tension），proof offset 0.006m，ramp 30 steps，hold 10 steps。
- Commandable DOFs only：DifferentialIKController DLS to arm_j1..j6 + high-level gripper primitive + bounded base planar velocity。No low-level USD runtime writes。

## Static-vs-Runtime Evidence Boundary

### R17 Repair (2026-08-04 22:29–23:45 HKT) — STATIC PASS

- Schema: `pull_v0_repair_r17_receipt_v1`，sha256 `73d0e2184980579b4664d260ab245647bf2d3f4189cc81d3bb0aee165c8dfaf9`。
- Status: `APPROVED_FOR_ATTEMPT20_PREPARATION_ONLY`，`runtime_validation: NOT_RUN`，`scientific_verdict_consumed: false`。
- Chain: parent R16.4 (`cf0d7107…`) + Attempt19 PROBE_INVALID receipt (`4f92eba0…`)。
- Root cause: Attempt19 steady capture failed closed under R16.4 G-only nonselected rule；observed footprint 是已知 NVIDIA driver/Kit enumeration behavior（eval PID 低显存 context 出现在所有可见 GPU，selected GPU2 独占 compute）。Evidence-admission defect，非 plant/pull verdict；physical plant `INCONCLUSIVE_NO_PROOF_SAMPLES`。
- Repair: helper attempt-label threading + Attempt20 enumeration classification（C/G/C+G same-PID acceptable, FB≤1024, NOT_REPORTED preserved, 0%-util-unless-OTHER_TENANT）；runner exact Attempt20 support + lifecycle-robust process_receipt（SIGINT/SIGTERM → 600s wait → SIGKILL only on timeout, unknown timestamps null/NOT_RECORDED）；Attempt19 capture-failure + PROBE_INVALID receipts；focused tests（152 passed）。
- Full namespace suite: **152 passed**（R16.4 baseline 142 → +10）。
- Prep-only closure: 确认无 Attempt20 artifact。

### Attempt19 (2026-08-04 22:18–22:19 HKT) — PROBE_INVALID (immutable)

- Reached evaluation boundary (stdout line 621) then evidence capture failed closed。
- Runner PID 2219008 / eval PID 2219040 reaped；no process_receipt.json。
- Receipts: `PULL_V0_P1_PUSH_ANCHOR_ATTEMPT19_CAPTURE_FAILURE.json` (sha `6fab55d0…`) + `PULL_V0_P1_PUSH_ANCHOR_ATTEMPT19_RECEIPT.json` (sha `4f92eba0…`)。
- Immutable artifacts: plan `cf23ee03…` / launch `03530324…` / stdout `2614844d…`。

### Attempt20 (2026-08-04 23:45–23:56 HKT) — ADMISSION PASS / ANCHOR FAIL

- R17 枚举分类修复生效：runtime 完成自然退出 (returncode 0, natural_exit true)。
- Process receipt: runner_pid 2271508 / eval_pid 2271525，summary + metrics 全部产出。
- Receipt: `PULL_V0_P1_PUSH_ANCHOR_ATTEMPT20_RECEIPT.json` (sha `b1b2fa0d…`)。
- **Anchor verdict: FAIL** — `BASE_RELIEF_DISPLACEMENT_LIMIT`，zero proof samples，zero terminal bilateral streak。
  - Hinge at crossing 1.043 rad (>0.25 ✓)，crossing_while_holding ✓，latch released ✓，body-panel contact 0.0 N ✓。
  - Episode: length 804, stage 4, stage_overtime, goal_reached false。
- `scientific_verdict_consumed: false` — anchor 未通过，one-shot verdict 未消耗。
- Steady-state footprint 未捕获（eval 在 600s sleep 内完成自然退出，早于 steady capture window；process_receipt + summary + metrics 是更完整的证据集）。

## GPU Lease

- Selected physical GPU2；authorized `[2,3]`；GPU7 never as compute。
- NVIDIA driver auto-creates low-memory enumeration contexts of the eval PID on every visible GPU — acceptable under Attempt20 classification（FB≤1024 MiB, PMON NOT_REPORTED-or-zero, 0% device util unless OTHER_TENANT）。
- OTHER_TENANT evidence 永不归因于 attempt PID。
- Attempt20 运行时 GPU2 独占 compute；GPU4 有 OTHER_TENANT (v13-student-distillation camera eval)，未干扰。

## Reproducible Commands

```bash
# R17 validate-only (prep-only closure)
/home/baoquanc/anaconda3/envs/isaaclab/bin/python scriptsFORhuman/pull_v0/run_p1_push_anchor.py \
  --attempt 20 --repair-receipt scriptsFORhuman/pull_v0/PULL_V0_REPAIR_R17_RECEIPT.json \
  --repair-receipt-sha256 73d0e2184980579b4664d260ab245647bf2d3f4189cc81d3bb0aee165c8dfaf9 \
  --validate-only

# R17 prepare-only (generate immutable Attempt20 plan + input)
# (same args, --prepare-only instead of --validate-only)

# Attempt20 launch occupancy capture
/home/baoquanc/anaconda3/envs/isaaclab/bin/python scriptsFORhuman/pull_v0/capture_p1_anchor_gpu_evidence.py \
  --mode launch --attempt 20

# Attempt20 GPU eval (tmux, long run ~9min)
/home/baoquanc/anaconda3/envs/isaaclab/bin/python scriptsFORhuman/pull_v0/run_p1_push_anchor.py \
  --attempt 20 --repair-receipt scriptsFORhuman/pull_v0/PULL_V0_REPAIR_R17_RECEIPT.json \
  --repair-receipt-sha256 73d0e2184980579b4664d260ab245647bf2d3f4189cc81d3bb0aee165c8dfaf9

# Full namespace suite (once)
/home/baoquanc/anaconda3/envs/isaaclab/bin/python -m pytest gr00t/rl/tests/test_a2_pull_namespace.py -q
```

## Key Source Facts

- `capture_p1_anchor_gpu_evidence.py`: `ATTEMPT_GPU_CONTEXT_CLASSIFICATION_MODES` — `[19]=STRICT_G_ONLY_INACTIVE_VULKAN_ENUMERATION` (historical, preserved), `[20]=LOW_MEMORY_SAME_PID_ENUMERATION_CONTEXTS` (R17)。`attempt: int = ATTEMPT` 线程化所有 shared validators。
- `run_p1_push_anchor.py`: `_LifecycleSignal` + `_stop_child_after_lifecycle_signal` (600s wait, SIGKILL only on timeout)。`validate_preparation(20, ...)` / `prepare(20, ...)` / `run(20, ...)`。CLI `--validate-only` / `--prepare-only`。
- Attempt20 plan: `pull_v0_p1_push_anchor_plan_v1`，attempt 20，checkpoint base_v20_R3_G4 step2500，fixture 120kg / handle 0.95m，capacity 64 anchor-only。

## TODO Summary

- 2026-08-11 00:03 HKT - Primary next candidate is a separately planned pull-v4 frame-neighborhood/path-distribution round after v3 G2(c): preserve v3 frame-passage predicates, C4 release mask, corridor scales, latch threshold `0.02292371541261673`, `near_closed=0.25`, hard gate and six invariants; do not retrofit another scale inside v3.
- 2026-08-11 00:03 HKT - G10 brace future is now evidence-triggered by one v3 cell with post-release recontact max `18`; keep it in `scriptsFORhuman/pull_task/a2_piper_pull_longterm_TODO.md` and do not implement until a separately authorized round.
- 2026-08-06 14:30 HKT - v0 E6/E7 capability boundary remains a separate historical problem: the policy never attempts path reversal (first_path_reversal_step=N/A for all episodes), ends at E5 with stage_overtime at 654 steps, and has tiny outward excursion (0.013-0.099m). Possible causes remain clear-phase reward, stage-time budget, or base-motion action space; investigate only under separately authorized scope.
- 2026-08-06 14:00 HKT - v0 seed1 E2-E5 instability remains historical context: checkpoints oscillated between 2/16 and 16/16 uniformly across strata, not explained by spawnHook or hinge force. Matched replicates or longer training remain a separate option.

## DONE Summary

- 2026-08-11 00:03 HKT - pull-v3 closure: C1–C7, canonical D0-lite, single smoke, dual-seed Wave1 train and six checkpoint evals completed. All six invariants were zero; all cells had E6/E7/complete `0/16`, so G2(c) closed as a traversal approach/path-distribution negative and no Wave2/seed2 ran. G10 triggered on recontact max `18`; one review wave remained formally FAIL with bounded fixes runtime/target validated and no second reviewer PASS.
- 2026-08-10 09:32 HKT - pull-v2 closure: canonical U-probe measured `theta*=0.6 rad` and latch threshold `0.02292371541261673`; only reward change was `near_closed 0.1→0.25`. Wave1 step750 true Stage3→4 reached `10/16` and `6/16`, triggering G1. Wave2 relay produced true Stage4 `13/16,14/16,15/16` and `11/16,16/16,16/16`; all four invariants were zero across 12 accepted cells/192 terminal episodes. A0 was NOT_TRIGGERED; next scope is traversal/V1-C.
- 2026-08-09 15:19 HKT - pull-v1 closure: C1–C6 implemented; Python compile and YAML/Hydra composition static PASS. D0 frozen replay runtime PASS (16/16 terminal Stage3, E4/E5 0, four integrity invariants 0) and V1-B 64×50 smoke natural exit. V1-A/B/R dual-seed training/eval completed: 18 accepted rows / 288 terminal episodes have true Stage3→4 0/288 and all four invariants zero. A/B hinge Δ max ≤0.002201 rad with zero stable unlatch; R reward port is behaviorally active at step750 (stable unlatch R0 13/16, R1 2/16), but R0 hinge Δ max 0.100607 rad remains below 0.25 and R1 is baseline scale. Two pre-batch1 construction-guard root fixes landed; final A/B/R contracts fail fast. The preregistered negative statement was not triggered.
- 2026-08-05 00:20 HKT - R17 repair complete: helper attempt-label threading + Attempt20 enumeration classification + runner Attempt20 support + lifecycle-signal receipt + Attempt19 PROBE_INVALID receipts + focused tests (152 passed)。R17 receipt sha `73d0e218…`。
- 2026-08-05 00:20 HKT - Attempt20 executed: admission PASS (R17 fix validated at runtime), anchor FAIL (BASE_RELIEF_DISPLACEMENT_LIMIT, zero proof samples)。scientific_verdict_consumed false。Receipt sha `b1b2fa0d…`。
