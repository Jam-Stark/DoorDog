# Pull LR full-stage research handoff — 2026-09-01

## Status

Owner requested termination after the current training batch. All train/eval tmux sessions have exited and GPUs 0–3 are idle.

The scientific goal is **not achieved**. No single policy has demonstrated Stage5/E7 on both raw LEFT and raw RIGHT handle randomization. Hardware was not run.

Repository state at handoff:

- branch: `codex/a2-piper-pull-v0-20260803`
- latest H18 implementation checkpoint commit: `b2983be`
- durable experiment memory: `memory/a2-piper/pull-lr-full-stage/`
- command registry: `experiments/COMMAND_BATCHES.md`
- unrelated Owner changes intentionally excluded from all commits: `.codex/config.toml`, `Codex-Cashier/`

## Best retained assets

| Purpose | Artifact | Evidence |
|---|---|---|
| Bilateral Stage0–2 winner | `logs_rl/a2_piper_pull_lr_grasp/pull_lr_grasp_h450_xseg_resume_seed2/model_step_000250.pt` | fixed LEFT/RIGHT strict K5 each 125/128 across eval seeds0/1001 |
| Successful RIGHT full teacher | `logs_rl/a2_piper_pull_lr_full_stage/h14_teacher_source/model_step_000025.pt` | fixed RIGHT E3/E4/E5=14/14/14 |
| Best clean shared Stage3 intermediate | H13 seed checkpoints at step75 | bilateral pose/contact dwell improved, but all E4=0 |
| Best native scratch policy | `logs_rl/a2_piper_pull_lr_full_stage/pull_lr_full_h16_long_acq_gate_r_seed2/model_step_001500.pt` | RIGHT E3=11/16 with long stable contact; LEFT E3=0, both E4=0 |
| H18 absolute teacher data | `logs_eval/a2_piper_pull_lr_full_stage/h18b0_teacher_right16_r7/right/eval/stage2_5_step_trace.json` | 1664 valid observed-Stage3 rows, absolute target support1.0 |
| H18 raw-absolute BC | `logs_rl/a2_piper_pull_lr_full_stage/warmstarts_h18/h18_b0_right_teacher_fit_final.pt` | parent23 exact, train/heldout MSE .0158/.0230; formal admission failed |

Do not promote any of these as a bilateral full-stage winner.

## What was learned

### Clean options requested by Owner

Both were executed rather than left as proposals.

1. Fresh shared canonical Stage3 controller on the bilateral Stage0–2 winner (H13):
   - Stage0–2 remained exact.
   - LEFT/RIGHT contact dwell rose to roughly 104–166 / 147–400 steps.
   - hinge improved into roughly .03–.07 rad at step75.
   - global200 still produced zero E4 on both sides, so H13 closed.

2. Native bilateral policy from random initialization (H15–H17):
   - H15 early Stage3 curriculum eventually produced partial acquisition but no bilateral E3/E4.
   - H16 kept acquisition occupancy through batch750. Only seed2 escaped the zero basin; at M1500 RIGHT reached E3=11/16 while LEFT remained E3=0 and both E4=0.
   - H17 increased Stage1 occupancy for failed seeds1/3. Both still had LEFT/RIGHT E2=0 across two M750 eval seeds. H17 closed.

### Stable press is not enough

H16 seed2 RIGHT post-E3 had 3884/3942 rows with bilateral finger contact and typical continuous dwell of 268–431 steps, yet hinge stayed near .002 rad. The policy learned a stable press equilibrium, not an opening action.

The same rows had severely saturated cumulative arm targets: representative q2/q3/q4 were about `[-2.50,+2.19,+4.00]`, with median maximum soft-limit excess about 2.89 rad. The successful teacher was around `[+2.52,-1.94,+.95]` with much smaller excess and a strong opening-side base command.

### Rejected causal directions

- LEFT-only residual/reward/snapshot/task-space variants H4–H12: no LEFT E4.
- H13 shared task-space controller: improved valid pose/contact but no E4 by global200.
- H14 twist-projected teacher BC: only RIGHT E4/E5=2/2, below admission 8/5.
- H18-D base lateral override: RIGHT E3=11/16, 1032 active valid-contact rows, hinge max .0111, E4=0. Base-only is insufficient.
- H18-B0 one-shot raw-absolute MLP BC: executor/action semantics passed independent review, but formal RIGHT E4/E5=0/0 for eval seeds1001 and0. Do not enter mirror/PPO from this checkpoint.

## H18 implementation contract

Commit `b2983be` adds:

- raw-absolute Stage3 actor: `gr00t/rl/trl/modules/pull_v6_bilateral_stage3_absolute_actor.py`
- bounded executor and teacher capture: `gr00t/rl/envs/door/door_open_a2_pull.py`
- prepare/fit scripts under `scriptsFORhuman/pull_lr_full/`
- H18-B0 and H18-D configs plus reproducible command files.

Important semantics:

- policy/PPO action is a latent Gaussian;
- environment applies `tanh(latent)` once, maps it to cumulative delta target `15*tanh(latent)`, then converts it to the exact DeltaAction increment;
- teacher capture and executor use the same observed Stage3 one-hot gate, including the normal Stage3→4 exit-lag action;
- checkpoint online staged-reset banks are **not serialized**. A stopped/resumed run retains optimizer/trainer but loses online rare-state banks.

## Why H18-B0 failed

The final action contract was not the failure.

1. B0 currently inherits Gate-B (`grasp_completion`), while H16 parent evidence used Gate-A (`tensile_proof`). Gate-B lets the Stage3 head take over before E2 is locked.
2. H16 Stage3-entry arm states were far outside the successful teacher distribution (median maximum deviation about 14.7 standard deviations). The first fitted absolute-target jump was about 2.12 rad median versus .193 rad for the natural teacher.
3. The 58-D MLP is an iid one-step model and ignores the teacher recurrent hidden state; low heldout MSE did not prevent closed-loop covariate shift.
4. It clones base planar3+arm6 but retains parent pitch/roll/gripper, which also differs from the successful teacher sequence.

A Gate-B H16-parent control retained E2/E3=16/15, confirming that the fitted head—not the executor—caused the collapse.

## Recommended resume sequence

No item below was launched after the Owner stop request.

### 1. B0 Gate-A seam control

Create a new config rather than overwriting the historical Gate-B B0 config. Change only the Stage2→3 gate to `tensile_proof`.

Admission:

- before observed Stage3, parent action/event sequence must match H16 Gate-A parent;
- fixed RIGHT16 E2 must recover to at least 11/16;
- E4≥4/16 is required to keep the static MLP direction alive;
- E4=0 closes the H16-parent one-shot BC cell.

### 2. In-domain parent swap

Use the bilateral Stage0–2 winner as parent23, refit the same H18 head with the r7 teacher trace, and keep Gate-A. Its RIGHT Stage3-entry arm posture lies inside the teacher range, unlike H16.

Run fixed RIGHT16 for eval seeds1001 and0. Required per seed:

- no acquisition regression;
- first target jump median ≤.29 rad, max ≤.50 rad;
- at least 12/16 environments retain contact for ≥5 steps after takeover;
- E4≥8/16 and E5≥5/16.

Only after this gate may LEFT mirror work begin.

### 3. Exact recurrent teacher carrier, then sequence DAgger

If the in-domain one-shot head still has E4=0:

- shadow-run the successful RIGHT teacher recurrent state from episode reset;
- parent controls Stage0–2; after true E2, the shadow teacher supplies its complete action, including pitch/roll/gripper;
- require RIGHT E2≥14, E3≥12, E4≥8, E5≥5.

If that hybrid passes, clone a recurrent Stage3 student and perform at most two trajectory-level DAgger rounds. Split by full trajectories, not rows. Do not use iid MSE as a promotion metric.

### 4. Mirror only after RIGHT admission

Do not guess Piper joint sign parity. Validate or solve mirror targets with local FK/Jacobian plus posture/nullspace constraints. Required mirror admission:

- TCP position p90 ≤.01 m;
- orientation p90 ≤.10 rad;
- opening-tangent cosine p10 ≥.95;
- ≥90% mapped targets satisfy cumulative-action and joint-progress contracts;
- fixed LEFT E4≥4 while RIGHT preserves E4≥8.

Only then run bilateral PPO. Final goal still requires the same checkpoint to produce Stage5/E7 from both raw LEFT and raw RIGHT, plus mixed bilateral successes contributed by both sides.

## Resume checklist

1. Read `memory/a2-piper/pull-lr-full-stage/description.md`, `DONE.md`, and `TODO.md`.
2. Confirm `git status --short`; preserve `.codex/config.toml` and `Codex-Cashier/` as unrelated Owner state.
3. Confirm all GPUs and tmux sessions are idle before acquiring resources.
4. Keep `pull_lr_grasp_h450_xseg_resume_seed2` as the command-manager active base until a true bilateral full-stage winner exists.
5. Register every new train/eval batch in `experiments/COMMAND_BATCHES.md` and commit source/config/memory before long runs.
6. Never claim Stage5 from average-stage telemetry, reset occupancy, one-sided E3, or screen-only hinge motion.

## Closure evidence

- H17 seed1 current batch completed at step750; training stopped at saved step775.
- H17 seed1 M750 eval seeds1001 and0: LEFT/RIGHT E2–E5 all 0/16.
- H17 seed3 stopped at saved step850 after the same M750 hard failure.
- H18-B0 formal RIGHT16: E4/E5=0/0 for both eval seeds.
- H18-D formal RIGHT16: E4=0/16.
- no active tmux sessions;
- GPUs0–3 idle;
- no hardware evidence.
