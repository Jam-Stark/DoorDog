# Pull v26-8 backbone execution contract

Run: `pull_v26_8_backbone_20260905`. Plan: `scriptsFORhuman/pull_task/a2_piper_pull_v26_8_backbone_migration_plan_20260905.md`.

Status: `CLOSED_AT_G1_HARD_STOP`. G0 selected 1024 env; G1 natural-eval construction was rejected by the current pull staged-reset requirement. No Wave1/2 launch is admitted. See `a2_piper_pull_v26_8_backbone_closure_20260905.md`.

Workflow: STANDARD implementation with authorized long GPU runs. Main owns integration, Git and GPUs0–3; focused agents independently trace source, port mirror wiring, and implement scripts/reducers. GPU0 evaluates; GPUs1–3 train. G0 memory smoke uses GPU1; the plan's G1 short training probe uses GPU0. All long jobs have their own tmux and receipt.

Outcome: scratch training of one shared plain LSTM actor on pull/in LEFT and RIGHT doors. Acceptance follows plan G0/G1, exact64 first natural episodes at every milestone, typed bilateral durable-unlatch outcomes, and separate opening/E7 labels. Teacher, handoff, hardware, reward/event/loader changes and K-driver migration are outside this contract.

## P0 source decisions, 2026-09-05

Pull start revision: `d48793c`. Remote reference: `A2_Piper` revision `cb15678`, parent `aa8a05f`; the referenced r3/r3a changes are now committed upstream. The downloaded reference plan is byte-identical to the local plan. Only named functions/config/scripts are ported; no merge or base-file replacement.

| Plan statement | Verified source / artifact | Execution decision |
|---|---|---|
| Plain actor/critic 135/140; old winner 137/142 | Both mainline `base_v26_7_Q05_S0` and pull resolve the identical plain observation list to **133/138**. The old winner's `policy_state_dict.memory.rnn.weight_ih_l0` is `(1024,135)`; its 2-D release-mode addition accounts for 135/140. | Use the exact mainline list and **133/138**, without extra fields or padding, under the Owner's explicit source/resolved-config authority. |
| `freeze_running_mean_std=false` in actor kwargs | Current `RecurrentActor.__init__` has no such parameter. Native forward/rollout uses the existing updating RMS; override subclasses own the freeze flag. | Retain the unmodified plain actor, `running_mean_std=true`; no unsupported constructor kwarg. The verifier records effective freeze=false. |
| Wave2 W changes near-closed hinge threshold 0.1 to 0.25 | Current full-pull `pull_lr_full_gate_a` → `pull_v6_F0_r6ap` → `pull_v6_F0` resolves **0.25**. | Wave1 retains 0.25. If W becomes the required Wave2 branch, it is unresolved as written; do not execute an identical 0.25/0.25 comparison or silently alter reward semantics. |
| Source lock includes SHA-256 | Owner's project instructions prohibit adding hashes/SHA-256. | Record Git revision/status plus immutable copies of the exact source files; compare bytes when binding later runs. No new digest logic. |

The observation fields are: dof position20, relative pose9, dof velocity20, actions19, gravity3, door dofs2, base linear/angular velocity3+3, hand force6, stage6, privileged door info8, delta actions6, gripper-handle transform18, raw/processed base command5+5. Sum=133. Critic adds five scalar fields, sum=138. Pull-only dimension/scale declarations unused by either list do not create observation groups or change the actor.

Stage2→3 gate is **grasp_completion**. `DoorOpenA2Pull._update_a2_pull_control_state` starts and advances tensile proof without a Stage2 restriction; its stable-contact predicate can use Stage3/4 hold streaks. Thus E2 can form after Stage3 entry. `_reward_pull_door_handle` and `_reward_pull_door_hinge` retain their existing live-proof masks, but the plan §2.7 premise of permanently zero Stage3 income is not established. The gate exception is not invoked.

The near-closed-hinge key is consumed by the base getter/config validator and `_get_a2_grasp_gated_door_reward_components`, which calls `a2_grasp_gated_door_reward_components`. It gates `unlatch_hold` via `hinge_pos < threshold`. The same component computation exposes hold-streak and drive components used by reward/diagnostics; the threshold does not alter their formula. Earlier pull-v2/v4 guard contracts also freeze 0.25. No consumer is modified.

## Frozen Wave1 axes

New exp defaults to `door_open_a2_pull_lstm`; new common reuses the current full `pull_lr_full_gate_a` config lineage without editing it. The complete resolved reward configuration of all three new cells is exactly equal to that source baseline. The explicit changes are mirror offsets, capability window 0.5/30/55, plain observation/actor, scratch/null/full loading, bilateral seed selector, fixed reset ratios `[.5,.1,.1,.1,.1,.1]`, and the registered budget/save cadence. No `schedule_dict` is inherited.

P_S0/P_S1/P_S2 use seeds0/1/2 and GPU1/2/3. G0 freezes 2048 environments only after 5 batches, exit0 and at least 2048 MiB observed headroom; otherwise test 1024 once. Budgets/milestones are exactly plan §5. The first supported milestone freezes the unlatch endpoint but does not stop training. Full-checkpoint continuity remains uninterrupted so online reset banks persist.

Metrics and the explicit E-event/stage mapping are in `REDUCER_CONTRACT.md`. Pull does not emit the mainline v26 integrity counters: the reducer applies the current `validate_a2_pull_episode` dependency/time-order validator and checks exact coverage, side and first-episode provenance. It does not substitute missing counters with a default.

G1 uses the same fresh 64-env checkpoint for old/fixed bilateral and old/fixed all-RIGHT evaluations. Each is a one-control-step timeout construction probe (`max_episode_length_s=0.02`), with natural resets and no staged banks; it is only geometry/initialization evidence. The current v6 guard permits this diagnostic episode duration. No core test hook is added. LEFT relative target rotation must be 180±0.05 degrees; RIGHT must be bit-identical.

## Evidence provenance

Isaac runtime: `/home/baoquanc/anaconda3/envs/isaaclab/bin/python`. Local FrameTransformer contract: `/home/baoquanc/workspace/IsaacLab/source/isaaclab/isaaclab/sensors/frame_transformer/frame_transformer.py`; its target offsets use env-major `(N*frames,4)` storage. Official reference: https://isaac-sim.github.io/IsaacLab/main/source/api/lab/isaaclab.sensors.html#isaaclab.sensors.FrameTransformer .

Receipts record commands with six explicit proxy variables, source lock, revision, paths, physical GPU, and expected artifacts. Each actual Isaac invocation performs the two-asset preflight in that same proxy environment. Runtime receipts retain child and wrapper exit codes, observed training-readout status, and sampled GPU peak memory. Isaac exit0 without its expected artifact is a failed invocation.
