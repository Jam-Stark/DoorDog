# DoorDog A2+PiPER `base_v25` Execution Plan R2

## Left/Right Push-Door Teacher Adaptation and Matched Posture Causality

**Status:** `PROPOSED_PENDING_OWNER_APPROVAL`  
**Date:** 2026-08-20  
**Base branch:** `A2_Piper`  
**Primary Teacher anchor:** `A1_G7_seed0_step1500`  
**Default compute:** GPU0-3, A6000 48 GB, one formal cell per GPU  
**Document role:** this is the canonical execution document for the worker AI session. It is intentionally close to implementation and leaves repository-specific choices to the worker that can inspect the local worktree, installed IsaacLab/Isaac Sim source, runtime logs, and actual GPU environment.

---

# 0. Intended outcome

v25 has two separate outcomes.

```text
Product outcome:
  Train or qualify a push-door Teacher that covers both handle sides.
  Replace G7 only when the new FULL policy is clearly better overall.

Science outcome:
  In stable-grasp, near-closed-door states, determine whether roll/pitch
  contributes immediate opening mechanics, only improves reach/grasp,
  or can be substituted by planar base motion.
```

These outcomes are independent. A useful causality result does not automatically qualify a new Teacher. A new Teacher can be useful even when the posture experiment remains inconclusive.

The simplest valid v25 end state is:

```text
LEFT/RIGHT simulation path works
+ four adaptation cells complete
+ matched posture experiment is executed and honestly interpreted
+ G7 is retained if no new FULL checkpoint is clearly better
```

---

# 1. Owner engineering policy for this worktree

These rules control execution unless local repository facts make one clearly inapplicable.

## 1.1 Memory first

Before implementation, debugging, review, or documentation updates:

1. read the project file-based memory entry points;
2. read the most relevant v23/v24 door-randomization and friction entries;
3. read the current v25 ledger if it already exists;
4. then inspect source.

Do not treat memory as source truth when code disagrees. Memory is routing and history; current source and runtime are implementation authority.

After a context compaction or worker restart, do not answer old guidance again. Re-read the current v25 ledger, the latest memory update, and the most recent run status, then continue from the newest unfinished action.

Update memory only at meaningful milestones, not after every command.

## 1.2 Implement the smallest working path first

The worker must first prove an end-to-end left-handle path using the existing door-generation and environment structure. Do not begin by designing a generalized handedness framework, schema system, compatibility layer, large test suite, or extensive audit harness.

Order of preference:

```text
existing project capability
→ small direct modification
→ small reusable helper when duplication is real
→ new module only when separation is useful
```

Use existing IsaacLab/project dependencies and established local patterns. Before assuming an API is missing, inspect the installed package source, type definitions, or an existing project use site once.

## 1.3 Fail fast

Do not silently continue through invalid scene state, missing checkpoint, wrong tensor shape, unsupported configuration, NaN, or failed restore.

Do not add fallback behavior whose purpose is merely to keep simulation or training running. A broken code path should fail at the point where the assumption is violated.

Avoid broad defensive programming for cases that are not credible in this repository. Validate the assumptions actually used by v25 and no more.

## 1.4 No general backward-compatibility project

v25 only needs the compatibility required to:

- load and evaluate the selected G7 Teacher;
- warm-start the v25 policies from G7;
- optionally read existing v24 friction artifacts or checkpoints when they are locally available.

Do not build compatibility layers for all v22-v24 paths. Do not add migrations, old-key aliases, or fallback loaders unless they are directly required by the approved v25 path.

Prefer an environment/config change that leaves the policy architecture untouched. If an unnecessary architectural change would break G7 loading, do not make that change.

Do not rewrite or delete historical v23/v24 artifacts. Inside the new v25 worktree, obsolete v25 prototypes may be removed rather than preserved behind switches.

## 1.5 No hashes

Do not generate or use SHA-256, file digests, signed manifests, or hash-based gates. Record identity with:

```text
git commit
absolute path
resolved config path
checkpoint path
run name
seed
```

## 1.6 Review and testing discipline

Before the owner has reviewed the first working left/right implementation:

- implement functionality;
- run only the minimal smoke commands needed to prove it;
- inspect the focused diff once;
- do not add a broad regression suite, mutation tests, legacy compatibility tests, or generalized guardrails.

After owner confirmation, add only tests that are directly justified by:

- a bug encountered during implementation;
- a fragile mapping the owner asks to preserve;
- a small critical configuration path that would otherwise be easy to break.

Do not repeatedly review the same unchanged paths. Do not repeatedly compile or run path-boundary checks. One focused review per milestone is enough unless a failure changes the code.

## 1.7 Long-running task discipline

Any task expected to exceed 30 minutes must run in its own named `tmux` session.

Use coarse waiting intervals. A suitable progression is:

```text
sleep 30
sleep 200
sleep 600
sleep 1800
then several hours or up to the estimated completion time
```

Do not poll every few seconds or repeatedly reopen unchanged logs. After the process is confirmed healthy, leave it alone.

When independent file reads, repository searches, or run-status checks can be batched into one tool call, batch them.

---

# 2. Fixed v25 scope

## 2.1 Core scope

1. keep `door_open_io="out"`; v25 is push-door only;
2. add a deterministic LEFT-handle configuration for rapid simulation and real-site preparation;
3. enable `door_open_lr` LEFT/RIGHT mixed training, default 50:50;
4. verify read-only that the currently running Student distillation uses the G7 seed0 step1500 checkpoint;
5. keep G7 as the active Student Teacher while v25 is being trained;
6. reuse the v24 native hinge-friction implementation as the primary load axis;
7. train FULL/RP0 × seed0/1 from G7;
8. run the matched stable-grasp posture/planar intervention;
9. qualify a v25 FULL Teacher or explicitly retain G7.

## 2.2 Not core scope

- pull/in-opening doors;
- Student training changes;
- GRPO;
- coupling/handoff critics;
- low-level A2 policy unfreezing;
- trunk/thigh/body-assist policy work;
- a general door canonicalization framework;
- a new physically calibrated fire-door/closer model;
- exhaustive historical checkpoint replay;
- broad legacy compatibility;
- extensive test infrastructure.

## 2.3 Optional lanes

The following are optional and must not delay the core path:

### Optional load extension

Only when v24 friction cannot produce a useful stable-grasp boundary and the local IsaacLab API offers a simple established implementation pattern, the worker may add one small sustained closer/load component. Otherwise use friction only.

### Optional reward curriculum experiment

The primary four-cell matrix keeps reward penalty curriculum disabled. After the mixed LEFT/RIGHT path and baseline training are healthy, the worker may run a small separate exploratory curriculum ablation if:

- the current curriculum semantics can be established quickly from source;
- no invasive reward rewrite is required;
- it does not alter or contaminate the primary four cells.

This optional lane is descriptive unless the owner later promotes it to formal scope.

### Optional v24 large-N replay

Run only when the required checkpoints are local and the evaluation is cheap enough to help choose the v25 load. It is non-blocking and must not become a separate audit campaign.

---

# 3. Worker decision authority

The worker is expected to make local engineering decisions without requesting approval for routine details.

The worker may decide:

- exact file placement based on current repository conventions;
- whether the existing `DoorSpawnerCfg` path is sufficient;
- whether a side sign belongs in the asset layer, environment layer, or both;
- exact left/right metadata representation;
- the smallest stable-grasp condition using signals that already exist;
- pilot episode counts and intervention horizon;
- which v24 friction value or small set of values forms the useful boundary;
- whether exact simulator state cloning is available;
- whether the causal experiment uses exact state restore or matched-prefix replay;
- checkpoint evaluation sample counts;
- whether `4096 env` must be reduced because of actual memory or simulator behavior;
- whether the run needs 1000, 1250, or 1500 batches after the early learning curve is visible, provided all formal cells remain comparable;
- which lightweight plots and summaries best explain the result.

Record meaningful decisions in the execution ledger with one or two sentences. Do not create a rubric for every choice.

Escalate to the owner only when one of the following is true:

1. the real-site door is confirmed to be pull/in-opening and the approved task semantics must change;
2. LEFT-handle behavior appears physically unreachable with the current A2+PiPER mounting and reasonable base repositioning;
3. the policy observation/action architecture or checkpoint format must change;
4. a change would affect the running Student or pull-door worktree;
5. the proposed compute/time budget changes substantially;
6. the core reward definition must change rather than merely reuse the existing configuration;
7. a result requires lowering a product-quality criterion to call a new Teacher successful.

---

# 4. Execution overview

```text
A. memory/source/start-state read
B. deterministic LEFT-handle end-to-end implementation
C. owner visual confirmation of LEFT/RIGHT behavior
D. mixed LEFT/RIGHT sampler and G7 zero-shot evaluation
E. v24-friction boundary selection
F. four parallel G7-warm-start training cells
G. checkpoint selection and Teacher comparison
H. matched stable-grasp posture/planar experiment
I. final Teacher and science adjudication
```

The core path is layered. Do not begin formal training before a deterministic LEFT-handle episode has been demonstrated.

---

# 5. Phase A — establish the actual local starting point

## Objective

Establish only the facts needed to implement v25. This is not a historical compatibility audit.

## Actions

Batch-read the relevant memory and source files. At minimum inspect the local equivalents of:

```text
MEMORY.md
memory/a2-piper/MEMORY.md
memory/a2-piper/door-asset-randomization-baseline/description.md
memory/a2-piper/door-asset-openio-sign/description.md
memory/a2-piper/base-v24-friction-force-boundary/description.md
scriptsFORhuman/v24/a2_piper_base_v24_final_analysis_*.md

gr00t/rl/isaac_utils/playground/env_rand/door.py
gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py
gr00t/rl/envs/door/door_open_a2_base.py
relevant v23/v24/v25 Hydra configs
```

Then record:

```text
worktree path
branch and commit
G7 checkpoint path
G7 saved/resolved config path
current v24 friction implementation path
available GPUs
running Student distillation tmux/process/log/config, read-only
```

For the Student distillation check:

- do not restart or modify it;
- verify the checkpoint from the actual command, resolved config, or log;
- record `CONFIRMED_G7_STEP1500`, `CONFIRMED_OTHER`, or `NOT_VERIFIABLE_FROM_CURRENT_ARTIFACTS`;
- do not infer success from a filename in a planning document.

Load G7 once through the actual evaluation or warm-start path that v25 will use. A full cross-version parity suite is unnecessary.

## Minimum evidence to proceed

A short start note containing exact paths and any unresolved local fact. No hash, no signed manifest, no elaborate schema.

## Contingencies

- **G7 missing locally:** stop the Teacher-training lane and report the missing path. Continue only source work that does not pretend the checkpoint exists.
- **Student checkpoint cannot be verified read-only:** record uncertainty; do not disturb the running job.
- **repository source differs materially from memory:** use source, update the v25 ledger, and continue.

---

# 6. Phase B — deterministic LEFT-handle path first

## Objective

Create the smallest end-to-end configuration in which the simulated push door has the handle on the real-site target side.

## Implementation order

1. create or modify one deterministic LEFT-only config;
2. use the existing `door_open_lr` scaffold before writing new geometry code;
3. start one environment in GUI/render mode;
4. verify visually and numerically that:
   - hinge and handle appear on opposite sides as expected;
   - the grasp/pregrasp target follows the actual handle;
   - stage-0 staging moves to the correct lateral side;
   - opening progress still increases with the existing positive hinge convention;
   - through-door direction remains the push/out direction;
5. run G7 for a small number of LEFT-only episodes to reveal obvious policy or task-routing failures.

Do not build a generalized `DoorCanonicalFrameV1` framework unless the existing code genuinely requires one. A per-environment side sign or a direct handle-relative computation is preferable when it fully solves the task.

## Implementation guidance

Likely one-sided assumptions to inspect, but not to audit repeatedly:

```text
door asset hinge/handle placement
grasp and pregrasp frames
stage-0 lateral target
stage transition conditions
face-door / yaw target
crossing target and success direction
side labels in evaluation output
staged-reset state restoration
```

Inspect each once while tracing the actual data path. Patch only assumptions that are wrong.

## Minimal proof

Provide:

- one RIGHT-handle visual;
- one LEFT-handle visual;
- a focused diff;
- a short note explaining raw `door_open_lr` to robot-view handle-side mapping;
- the LEFT-only config intended for quick real-site preparation.

Do not require a full paired fixture suite at this point.

## Owner milestone M1

After the first working LEFT/RIGHT demonstration, stop before adding broad tests, generalized guards, or launching formal training. Present the visuals, focused diff, and observed semantics to the owner.

While waiting, the worker may prepare read-only analysis scripts or summarize the implementation, but must not turn the first working path into a large framework.

## Contingencies

- **Existing scaffold works directly:** keep the change mostly in configuration; do not add unnecessary abstraction.
- **Handle moves but target does not:** fix the target-routing assumption directly.
- **Task stages use a fixed lateral sign:** introduce the smallest per-environment handedness sign needed by those expressions.
- **Negative scale appears tempting:** do not use it; use the asset's semantic left/right construction or explicit geometry placement.
- **LEFT geometry is correct but G7 cannot reach it:** this is expected zero-shot evidence, not proof the asset is broken.

---

# 7. Phase C — mixed LEFT/RIGHT training path

Begin after M1 owner confirmation.

## Objective

Turn the deterministic path into a mixed training distribution without changing push/out task semantics.

## Default configuration

```yaml
door_open_io: out
door_open_lr:
  left: 0.5
  right: 0.5
```

The worker may use the repository's native list/random-choice representation instead of this literal YAML shape.

## Actions

1. enable mixed LEFT/RIGHT asset selection;
2. ensure the side is visible in per-episode evaluation output;
3. start with fresh staged-reset caches for v25;
4. run a small mixed smoke, default `64 env × 5-10 updates`;
5. check that both sides appear and that the run reaches the expected early stages without scene corruption, NaNs, or obvious target mismatch.

A separate manifest system is not required unless the current training/evaluation code already depends on one.

## Minimum evidence to proceed

- both sides appear in runtime output;
- LEFT and RIGHT episodes can at least approach the correct handle;
- no obvious side leakage or reset corruption;
- training updates execute.

This is a practical go/no-go, not a strict mirrored-numerics certification.

## Testing policy after M1

Add at most one or two targeted checks if implementation exposed a real fragile point, for example:

- raw side label maps to the expected handle side;
- stage-0 target follows the handle lateral coordinate.

Do not add a broad handedness regression matrix unless requested later.

---

# 8. Phase D — G7 LEFT/RIGHT zero-shot and friction boundary

## 8.1 G7 zero-shot

Run the frozen G7 policy on LEFT and RIGHT push doors before adaptation.

Start with a modest matched sample count. A reasonable default is 64-128 natural-start episodes per side; the worker may use fewer for an early diagnosis and expand only when the result is noisy.

Report separately by side:

```text
pregrasp/reach
stable grasp or existing equivalent signal
maximum stage
door-angle progress
goal/crossing
clearance/body contact
release or no-release
arm clipping/saturation if already logged
```

Do not create a new metric stack when current evaluation already exposes adequate signals.

This evaluation has two purposes:

1. quantify how out-of-distribution LEFT is for G7;
2. establish the right-only behavior that v25 should not unnecessarily lose.

## 8.2 Select the v25 load from the existing v24 friction axis

The default v25 causal load model is the existing v24 native hinge friction. Do not rewrite it.

Use a small exploratory pilot around the previously useful values, likely from the existing `2/5/10/20 N·m` axis. The exact values must come from local v24 memory/source, not from this plan alone.

Select one primary boundary value, or at most two values, that satisfy the practical intent:

```text
G7 or the warm-start policy can establish a stable grasp
AND the door remains near closed long enough to observe effort/progress
AND the condition is not universal failure
```

The pilot is exploratory. After choosing the formal load, record it once and keep it fixed for the causal dataset.

## Load contingencies

1. **Friction is too easy:** move to the next existing v24 value.
2. **Friction is too hard:** move down one existing value or use a staged-reset stable-grasp start.
3. **No value creates a useful boundary:** first adjust only the existing v24 friction range. Add a closer model only if the worker finds a simple, established IsaacLab implementation and the owner does not need to approve a scope expansion.
4. **The useful value differs by side because of an implementation bug:** fix the side semantics. Do not encode different scientific loads for LEFT and RIGHT as a workaround.

---

# 9. Phase E — four parallel warm-adaptation cells

## Default matrix

| GPU | Cell | Posture | Seed | Init |
|---:|---|---|---:|---|
| 0 | `V25_FULL_S0` | FULL | 0 | G7 policy/RMS/LSTM using the existing warm-start path |
| 1 | `V25_FULL_S1` | FULL | 1 | same |
| 2 | `V25_RP0_S0` | RP0 | 0 | same |
| 3 | `V25_RP0_S1` | RP0 | 1 | same |

Default run shape:

```text
4096 environments per cell
up to 1500 batches
save every 250 batches
fresh v25 staged-reset cache
door_open_io = out
LEFT/RIGHT = 50/50
primary v24-friction load mixture
reward penalty curriculum = off
```

The worker may change environment count or maximum batches based on actual local throughput, OOM behavior, and learning curves. When changing the formal budget, keep all four cells comparable and document the decision once.

Do not add a general compatibility layer to load G7. Use the existing successful warm-start route and keep the v25 policy architecture unchanged unless there is a compelling local reason.

## Minimal pre-launch proof

Before launching all four long runs:

1. run one FULL mixed-LR smoke;
2. run one RP0 mixed-LR smoke;
3. verify a real optimizer update and checkpoint write;
4. inspect the resolved reward config once to confirm curriculum is off;
5. verify both door sides appear.

No additional preflight suite is required unless the smoke exposes a failure.

## Launch and wait

Use four named tmux sessions. Record the command and log path in the ledger.

Suggested monitoring:

```text
30 s: process launched, no immediate traceback
200 s: simulator/training initialized and updates begin
600 s: logs advance and GPU memory is stable
1800 s: checkpoint timing estimate
then sleep for several hours or until the estimated checkpoint/completion time
```

Do not repeatedly poll healthy jobs.

## Failure handling

- **Immediate deterministic code/config error:** fix the root cause and restart that cell.
- **OOM:** reduce env count consistently for all four formal cells or relaunch the affected cells with one common revised budget.
- **Transient process failure before useful progress:** one clean restart is reasonable.
- **Failure after useful checkpoints exist:** keep artifacts, diagnose once, and resume or run a bounded makeup; do not erase the history to make the run look clean.
- **One cell learns much slower:** do not alter its distribution or reward independently. Let the evidence stand unless there is a concrete implementation fault.

---

# 10. Optional reward-curriculum lane

This is not part of the primary causal matrix.

After the core mixed-LR implementation is stable, the worker may inspect the current reward curriculum implementation once. If its direction and resolved configuration are clear and enabling it requires only a simple config change, run a small separate experiment such as:

```text
FULL seed0 baseline checkpoint warm-start
same LEFT/RIGHT and friction distribution
short curriculum-on adaptation
matched curriculum-off comparison
```

This lane must have separate run names and artifacts. Do not mix its checkpoints into the primary FULL/RP0 selection unless the owner later approves that change.

If the curriculum implementation is ambiguous, inverted, or requires a reward rewrite, skip it and record why. Do not build a fallback curriculum implementation in v25.

---

# 11. Phase F — checkpoint selection and Teacher qualification

## 11.1 Selection approach

Evaluate saved checkpoints on a common LEFT/RIGHT suite. The worker should use engineering judgment rather than a rigid point system.

Priorities:

1. LEFT-handle grasp/open/crossing improves substantially over G7;
2. RIGHT-handle behavior remains usable and does not show an obvious regression;
3. clearance, body contact, and release behavior are acceptable;
4. the policy does not rely on pathological arm clipping, foot slip, or unstable posture;
5. behavior is repeatable across more than one scenario and preferably both FULL seeds.

Use side-stratified results first. A pooled success number is not enough.

Route-A evaluation does not need to run every possible metric on every checkpoint. Start with save250 checkpoints, remove clearly weak ones, and spend larger evaluation budget only on the strongest candidates.

## 11.2 Teacher candidates

Teacher candidates come from FULL only. RP0 is a science/control condition unless its role is changed by the owner.

Compare:

```text
G7 frozen anchor
selected V25_FULL_S0 checkpoint
selected V25_FULL_S1 checkpoint
```

Keep G7 when the new candidates are mixed, only marginally better, or improve LEFT by damaging RIGHT/clearance/release.

Possible product conclusions:

```text
V25 Teacher upgrade
retain v23 G7
Teacher result inconclusive
```

No criterion needs to be lowered to force an upgrade.

## 11.3 Minimal Teacher handoff artifact

For the selected Teacher or retained G7, provide:

```text
checkpoint path
resolved config path
run/seed/checkpoint step
LEFT/RIGHT training distribution
friction/load distribution
known weaknesses
student action/observation contract status
```

No hash or signed manifest.

---

# 12. Phase G — matched stable-grasp posture/planar experiment

This is the core science experiment and should be implemented as a small, understandable evaluation script rather than a new training framework.

## 12.1 Policies used

Primary acute intervention:

- use the selected v25 FULL policy when available;
- otherwise use G7 or the strongest available FULL checkpoint and state the limitation.

Secondary chronic comparison:

- compare selected FULL and RP0 checkpoints on the same scenario set;
- keep this separate from the acute within-state intervention.

## 12.2 State-bank construction

Collect states in which:

```text
the gripper has reached the existing stable-grasp/contact condition
the door is still near closed
the episode has not fallen or entered an obvious invalid state
the selected friction load is active
```

Use existing stage/contact variables where possible. Do not invent a complex new grasp classifier unless current signals are unusable.

A practical starting point is 16-32 states per side at the primary load. Expand only if the paired effects are noisy or too few states have nonzero posture/planar commands.

The exact near-closed threshold and grasp dwell may be chosen from current control frequency and existing stage logic. Record the chosen values in the script or run note; no separate registration bureaucracy is needed.

Staged reset may be used to efficiently create stable-grasp states. It is an exploration/state-initialization tool, not part of the outcome definition.

## 12.3 Four intervention branches

Starting from the same snapshot or matched prefix, run a short horizon under:

| Branch | Roll/Pitch commands | Planar `vx/vy/yaw` commands |
|---|---|---|
| `P1_M1` | active | active |
| `P0_M1` | zeroed | active |
| `P1_M0` | active | zeroed |
| `P0_M0` | zeroed | zeroed |

The arm and gripper remain controlled by the selected task policy. The default implementation is:

1. evaluate the policy normally at each control step;
2. mask only the specified base-command channels before passing them to the frozen A2 policy;
3. leave arm/gripper outputs untouched.

This measures the closed-loop effect of disabling the command channels while allowing the task policy to react to the changed state.

For a tighter mechanical control, the worker may add an optional replay-arm variant in which the full branch's arm/gripper sequence is replayed across branches. Do this only if it is simple and the first result is ambiguous. It is not required for the core experiment.

## 12.4 Restore authority

Preferred:

```text
robot and door physical state
stage/time state
policy recurrent hidden state
previous action/history
same door side and friction parameters
```

If the simulator cannot exactly restore contact solver internals, use a deterministic matched-prefix replay to reach the selected state, then branch. Label the result `matched-prefix` rather than blocking the experiment.

Do not build a simulator-state serialization subsystem solely for this experiment.

## 12.5 Horizon

Start with approximately 1-2 seconds of policy control. Shorten it when branches diverge too far to remain interpretable. Extend it only when the door does not move enough to expose a difference.

Use control steps, not raw physics frames.

## 12.6 Minimal measurements

Collect the measurements already available with the least new instrumentation:

```text
hinge-angle change and/or maximum hinge progress
hinge velocity or simple progress rate
whether grasp/contact is maintained
arm command clipping/saturation if available
base displacement and achieved roll/pitch
foot slip, fall, or major body/door-frame contact
```

Use hinge work only when the current code already exposes a credible quantity. Do not delay the experiment to create a perfect torque observer.

## 12.7 Analysis

Analyze within-state paired differences by side and load.

At minimum show:

- per-state or paired scatter/lines for hinge progress;
- median/mean paired difference;
- grasp-retention difference;
- command dose: how much posture or planar command was actually removed;
- representative videos.

A paired bootstrap or confidence interval is useful if an existing analysis utility makes it easy, but there is no hard p-value or minimum-E1 gate. The worker may increase sample count once when the effect is genuinely ambiguous.

Interpretation categories:

```text
posture has immediate force/mechanics value
posture mainly helps reach/grasp geometry
planar motion substitutes for posture after training
posture appears neutral or harmful in this setting
insufficient evidence
```

Do not infer real-world torque capability from simulation command limits.

## 12.8 Intervention contingencies

| Situation | Default response |
|---|---|
| Exact state restore is unavailable | use matched-prefix replay and state that limitation |
| Roll/pitch command is already near zero in many states | select states with nonzero command dose or report that the policy did not use the channel |
| Branches diverge immediately | shorten the horizon |
| Door barely moves in all branches | choose the next validated v24 friction value or use a slightly later stable-grasp state |
| All branches fail instantly | lower the friction or exclude invalid grasp states; do not add policy-specific loads |
| LEFT state bank is sparse | use LEFT-only staged-reset generation or more LEFT episodes |
| Arm clipping dominates | optionally run a small existing 20→25/40 cap rescue subset; keep it separate from the main result |
| Metrics are noisy | expand matched states once; do not repeatedly redefine the state criterion |

---

# 13. Code organization guidance

Prefer the repository's current layout. A reasonable shape, not a requirement, is:

```text
gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py
  deterministic LEFT-only and mixed LEFT/RIGHT configuration

gr00t/rl/envs/door/door_open_a2_base.py
  only the minimal per-env side routing that the current code actually needs

gr00t/rl/envs/door/a2_v25_intervention.py
  optional small helper for channel masking/state-bank evaluation

scriptsFORhuman/v25/
  execution ledger
  zero-shot evaluator
  causal intervention runner
  checkpoint comparison/final analysis

memory/a2-piper/base-v25-mirrored-teacher-force-causality/
  description.md
  TODO.md
  DONE.md
```

Do not create separate handedness/load/evidence modules merely because the R1 plan suggested them. Create modules when they reduce real coupling in the actual code.

Do not retain obsolete v25 implementations behind fallback flags. Once the working path is approved, remove unused experimental branches inside the v25 worktree.

---

# 14. Review checkpoints

## M1 — LEFT/RIGHT implementation proof

Owner sees:

- LEFT and RIGHT visuals;
- focused diff;
- raw-label-to-semantic-side explanation;
- LEFT-only preset;
- known limitations.

No broad tests before this confirmation.

## M2 — before formal four-cell launch

Worker performs one focused review of changed runtime/config paths and shows:

- mixed LEFT/RIGHT smoke;
- G7 warm-start smoke;
- selected friction load;
- exact four launch commands;
- resolved reward curriculum-off evidence.

This does not require a second full repository audit.

## M3 — before Teacher replacement

Show side-stratified comparison of G7 and selected FULL candidates plus representative videos. Owner approval is required to change the Student Teacher checkpoint.

---

# 15. Final deliverables

Keep artifacts useful and compact.

```text
scriptsFORhuman/v25/a2_piper_base_v25_execution_ledger_*.md
scriptsFORhuman/v25/a2_piper_base_v25_final_analysis_*.md

LEFT-only and mixed-LR resolved configs
four formal run commands and log/checkpoint paths
G7 LEFT/RIGHT zero-shot summary
selected friction/load note
checkpoint comparison summary
matched posture/planar result with data and videos
Teacher handoff note

memory/a2-piper/base-v25-mirrored-teacher-force-causality/
```

The final analysis must clearly separate:

```text
observed facts
worker interpretation
remaining unknowns
Teacher decision
posture-causality decision
real-site relevance
```

Do not create a large typed-outcome tree unless the repository already depends on one.

---

# 16. Final completion standard

v25 is complete when the worker has produced a usable answer to the following questions:

1. Does the simulator and task logic work with the handle on both sides?
2. Is G7 already adequate on LEFT, or was LEFT clearly out of distribution?
3. Did warm adaptation produce a FULL Teacher that is better than G7 without obvious regression?
4. Under stable grasp and a useful v24 friction load, what changes when roll/pitch and planar commands are disabled?
5. What should the Student worktree use next: G7 or a specific v25 checkpoint?

No artificial hard metric is required when the local evidence cannot support one. The worker should make the strongest defensible conclusion, retain uncertainty where necessary, and avoid turning an inconclusive science result into an execution failure.
