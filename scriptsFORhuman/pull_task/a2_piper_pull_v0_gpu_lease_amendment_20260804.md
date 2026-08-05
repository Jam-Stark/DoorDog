# Pull-v0 — GPU Lease Re-issue & Vulkan-Context Authorization (Amendments 4–6)

**Document ID:** `a2_piper_pull_v0_gpu_lease_amendment_20260804`
**Date:** 2026-08-04 HKT
**Amends:** `scriptsFORhuman/pull_task/a2_piper_pull_v0_worker_execution_split_20260803.md` — §4 hard constraints (GPU clause) and §4.3 stop conditions. Amendments 1–3 of that document are unchanged and remain in force.
**Authority:** user (arbiter), 2026-08-04, in response to the worker's `BLOCKED_BY_GPU_RESOURCE_TOPOLOGY` stop.
**Scope:** this document resolves the GPU-topology block **only**. It authorizes no new science, clears no review gate, and changes no threshold.

---

## 1. Fact basis (verified on the worker host, 2026-08-04)

| Fact | Evidence |
|---|---|
| v21-B formal training completed all 7 cells | `logs_rl/a2_piper_full_stage_a2_base/base_v21B/formal/B1..B7/` each hold `model_step_002500.pt` |
| v21-B formal evaluation closed on mainline | `A2_Piper` HEAD `89c6538` "feat(a2): close v21-B formal evaluation" |
| v21-B tmux session gone | `base_v21B_formal_v1` no longer in `tmux ls` |
| All 8 GPUs idle | `nvidia-smi`: index 0–7 all `1 MiB` / `0 %`; `--query-compute-apps` returns no rows |
| Pull worktree intact at the expected base | `/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0` HEAD `4aec9fe`, product changes uncommitted |

**Consequence.** The clause the worker refused to violate — *"never the v21-B GPUs while v21-B runs"* — protected work that has finished. The block is dissolved by a fact change, not by a scope concession. **The worker's stop was correct behavior and is not being overridden as an error.**

---

## 2. Amendment 4 — GPU compute lease re-issued

The pull-v0 branch's compute lease is now, and until further notice:

```text
AUTHORIZED FOR COMPUTE:   GPU2, GPU3   (physical indices)
NOT AUTHORIZED:           GPU0, GPU1, GPU4, GPU5, GPU6, GPU7
```

Notes:

- This **revokes** the previous GPU4–6 lease. The worker had been binding GPU4; it must re-bind to GPU2 or GPU3.
- The v21-B protection clause is void (v21-B complete). It is not replaced by a new protection clause; the restriction to GPU2/3 is an administrative permission boundary set by the arbiter, and applies regardless of whether other GPUs appear idle.
- **An idle reading on a non-authorized GPU is not authorization.** Do not schedule compute there on the basis of a `nvidia-smi` spot check.
- Re-binding from GPU4 to GPU2/3 requires re-running the single-renderer proof (Kit marks only the leased device Active; physics/tensor on the leased `cuda:N`) for the new device. Per Amendment 6 this is **infrastructure**, not an anchor attempt.

## 3. Amendment 5 — incidental Vulkan enumeration contexts authorized

**Authorized:** IsaacSim/Kit processes launched under this lease may create inactive Vulkan enumeration contexts on **all visible physical devices, including GPU0–1, GPU4–7**, as a side effect of Vulkan device enumeration.

**Basis:**

1. **Physically unavoidable on bare metal.** `CUDA_VISIBLE_DEVICES` governs CUDA runtime enumeration only; the Vulkan loader/ICD enumerates physical devices independently. Official Kit documentation states that `CUDA_VISIBLE_DEVICES` cannot hide or select Vulkan devices. The worker demonstrated this in Attempt16 after the single-renderer configuration was already proven correct — this is therefore a platform property, not a configuration defect.
2. **Negligible cost.** MiB-scale VRAM, zero compute, no interference with CUDA kernels on other devices.
3. **Existing project practice.** The project's own v19 / v20 / v21-B formal rounds have been launching bare-metal IsaacSim continuously for months and are subject to the identical platform behavior, with no observed harm across dozens of multi-day runs.

**Conditions:**

- No compute work — no env stepping, no training, no eval — may be scheduled on a non-leased device. The authorization covers enumeration side effects only.
- Every run receipt must record, per device: whether it is the leased device, and the observed memory footprint at steady state.
- If another tenant occupies a non-leased GPU, the enumeration context is still authorized (it does not disturb them), but the receipt must record that GPU's occupancy state at launch.

**Explicitly not authorized, and explicitly not required:** container isolation, NVIDIA Container Toolkit device masking, cgroup device-controller work, mount-namespace `/dev/nvidiaN` masking, or any other process-level isolation. The project launches IsaacLab from a conda environment per handoff §5; containerizing would invalidate the launch, smoke, and canonical-eval conventions and the receipt chain that depends on them. **Do not build it.** If true multi-tenant isolation is needed later, it is a separate infrastructure ticket and not a pull-round dependency.

## 4. Amendment 6 — retry accounting: infrastructure vs. anchor attempt

v21 §7.2 already establishes this principle for training: *"A process failure before the first optimizer update is infrastructure and may be fixed and repeated unchanged; poor performance is never retryable."* It is hereby extended to probes.

```text
INFRASTRUCTURE FAILURE  = any failure before the first simulation step
                          (Hydra/transport, device binding, renderer/Vulkan
                           topology, launcher, disk, process teardown)
                        -> unlimited fix-and-retry
                        -> does NOT consume an anchor attempt number
                        -> logged in the receipt chain under a separate
                           INFRA_* sequence

ANCHOR ATTEMPT          = any run that reaches the first simulation step
                        -> produces an anchor verdict
                        -> consumes an attempt number
                        -> its verdict is immutable
```

Attempts 15 and 16 are hereby reclassified as **infrastructure**: neither reached the anchor physics. The worker should renumber accordingly in the receipt chain (preserving the original artifacts and their hashes, with a mapping note — do not delete or rewrite existing receipts).

Rationale: the anchor gate exists to validate probe physics. Burying its evidence under launch-plumbing noise, and creating false attempt-count pressure, degrades exactly the signal the gate was built to protect.

## 5. Attempt17 — acceptance definition

Attempt17 is the **first attempt that can reach the anchor physics**: R13/R14 narrow repairs are complete, 130 targeted tests pass, the Hydra transport defect is fixed, and single-renderer binding is proven (to be re-proven on the new leased device per Amendment 4).

Its required output is an **anchor verdict**, one of:

- **`ANCHOR_PASS`** — on the mirrored push-side `out` fixture, same actuator profile: stable bilateral capture, latch release, ≥0.25 rad hinge progress, no body-panel contact. (Amendment 1 of the split document; unchanged.)
- **`ANCHOR_FAIL_PHYSICS`** — reached the simulation, did not meet the anchor criteria. **The report must name the physical root cause and map it to one of the six R13/R14 findings** (push/root-only transition semantics; final-target `-X` at E4; missing E2 continuous loaded-contact proof; E5–E7 funnel not wired; E7 not a completion gate; pull-cell command mapping to `-X` compression instead of `+X` tension). If the root cause maps to none of them, that is a **new** finding and must be reported as such rather than folded into the existing six.
- **`INFRA_*`** — did not reach the first simulation step; per Amendment 6 this is not an attempt and the worker proceeds to fix and retry without authorization.

A third consecutive `ANCHOR_FAIL_PHYSICS` without a named, findings-mapped root cause is a stop-and-escalate condition: it indicates the repair loop is running blind.

## 6. One bounded evidence task (do this once, then never re-litigate)

From the existing Attempt16 stdout log (`logs_eval/a2_piper_pull_v0/p1_push_anchor/attempt16/stdout_stderr.log`), extract and record **once**, in a small standalone receipt:

- per-device Vulkan enumeration context footprint (MiB) created by a single IsaacSim process;
- confirmation that non-leased devices show zero compute utilization.

Purpose: convert Amendment 5 from an authorization into a measured, citable fact, so this can never block a future round. If the per-process footprint is materially larger than MiB-scale (say >1 GiB per non-leased device), **stop and report** — that would falsify the basis of Amendment 5 and requires re-decision.

Context for interpretation, offered as **inference, not proof**: while v21-B ran 7 cells on GPUs 0–6 with no other tenant, GPU7 showed a stable `1018 MiB / 0 %`, which dropped to `1 MiB` when v21-B ended. `1018 / 7 ≈ 145 MiB` per process is the right order of magnitude for a Vulkan enumeration context. Per-process attribution was not captured at the time and those processes are gone, so this is not evidence — the Attempt16 log is. If it corroborates, record the coincidence as supporting context; if it does not, discard the inference without further comment.

## 7. What remains locked (nothing else changes)

- `P1 pull matrix` — **LOCKED** until push anchor `ANCHOR_PASS`.
- `P2 initialization experiment` — **LOCKED** until P1.
- `code_reviewer` and `isaaclab_reviewer` — **still FAIL from the pre-R13/R14 round**. This amendment clears neither. Durable memory, `git stage`, and `git commit` remain prohibited until both reviewers PASS, per repo policy.
- Amendments 1–3 of the split document (push-side anchor gate; 120 kg fixture from the resolved `a2_door_weight_range [80,160]`; freeze-guard at build step 3) — unchanged and in force.
- All task thresholds remain `report_only`. No new science, no new scope, no new cells.
- The five open human decisions (split document §5) remain open and continue to block nothing in P0–P1.

---

*One-sentence brief: v21-B completed all seven cells to step 2500 and released every GPU, so the clause the worker refused to violate no longer protects anything; the pull-v0 compute lease is re-issued as GPU2 and GPU3 only, incidental Vulkan enumeration contexts on non-leased devices are explicitly authorized as an unavoidable and empirically harmless platform property rather than solved with container isolation, pre-simulation failures are reclassified as unlimited-retry infrastructure rather than anchor attempts, and Attempt17 is required to produce a findings-mapped anchor verdict — with every other gate, lock, and threshold left exactly as it was.*
