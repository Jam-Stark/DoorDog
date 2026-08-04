---
name: pull-open-door-task
scope: A2+Piper pull-door v0 round (pull-side P1 scripted probe + push-side anchor)
status: active
last_updated: 2026-08-05 02:30 HKT
owned_paths:
  - memory/a2-piper/MEMORY.md
  - memory/a2-piper/pull-open-door-task/description.md
  - memory/a2-piper/pull-open-door-task/TODO.md
  - memory/a2-piper/pull-open-door-task/DONE.md
read_when:
  - 继续 pull-door v0 的 anchor probe / P1 matrix / P2 工作前
  - 需要确认 R17 evidence tooling 状态、Attempt19 PROBE_INVALID / Attempt20 anchor-FAIL 边界、或 GPU lease 口径时
---

# Pull-Open-Door Task (v0 round)

## Purpose

记录 A2+Piper pull-door v0 round 的 direction contract、static-vs-runtime evidence boundary、reproducible commands、当前 TODO/DONE。不复制 raw trace 或长日志；只保存可复用结论。

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

- 2026-08-05 00:20 HKT - Anchor FAIL `BASE_RELIEF_DISPLACEMENT_LIMIT` 需新 scope 调查（base relief 参数 / probe stage 4 行为 / 物理 fixture）。非 R17 问题（R17 是 evidence/runner tooling）。
- 2026-08-05 00:20 HKT - Anchor PASS 后才可 freeze candidate → code_reviewer → isaaclab_reviewer → unlock P1 pull matrix。
- 2026-08-05 00:20 HKT - P2 locked until P1 + explicit GPU allocation。

## DONE Summary

- 2026-08-05 00:20 HKT - R17 repair complete: helper attempt-label threading + Attempt20 enumeration classification + runner Attempt20 support + lifecycle-signal receipt + Attempt19 PROBE_INVALID receipts + focused tests (152 passed)。R17 receipt sha `73d0e218…`。
- 2026-08-05 00:20 HKT - Attempt20 executed: admission PASS (R17 fix validated at runtime), anchor FAIL (BASE_RELIEF_DISPLACEMENT_LIMIT, zero proof samples)。scientific_verdict_consumed false。Receipt sha `b1b2fa0d…`。
