# A2+PiPER `base_v26-5` Wave2 R1/R15 execution handoff

Closed: 2026-08-31 06:45 CST  
Repository: `/home/baoquanc/workspace/DoorDog-A2_Piper`  
Branch: `codex/v26-5-bilateral-stage5`  
Pilot/K1/smoke/formal-train contract revision: `3fd6482`  
Formal retry1/final-reducer contract revision: `c8203ac`

## 1. Outcome first

R15 completed its shared-observation implementation, cold-process identity gates,
two-seed formal training, bilateral fixed-step evaluation, and frozen reducer. The
final typed route is:

```text
KILL_RESIDUAL_ACQUISITION_REGRESSION
```

The route is an experiment result, not an execution failure. All four retry1 formal
evaluation cells are supervisor `PASS/0`, all eight side outputs contain exact64
completed episodes, and the reducer status is `EXPERIMENT_COMPLETE` with zero
telemetry integrity violations.

The step250 endpoint gate requires every seed/side endpoint to have at least 16 K5
episodes, at least 16 Stage3 admissions, contact-stability rate at least `0.9`, and
zero integrity violations. `R15_S0/LEFT` failed only the contact-stability band at
`0.7583052479`; the other three endpoint rates were `0.9493231905–0.9687743950`.
All four endpoints had strong K5/Stage3 counts, but none reached Stage4. The frozen
priority therefore kills this residual experiment and does not admit a Stage5 relay.

Per the Owner update, no follow-on experiment, extra training, threshold change, or
route reinterpretation was started after this reducer.

## 2. Why R15 existed and what changed

R14's immutable pilot outcome was `KILL_R14_CROSS_PROCESS_TRAJECTORY`:

- reset snapshot maximum absolute delta: `0`;
- tick-zero policy/action path matched;
- later 50-tick observation/action maximum absolute delta: `2.6536242962`;
- terminal discrete identity: false;
- integrity violations: `0`.

The first divergence was localized at step 1 to the noisy DOF position/velocity
portion of the actor observation. The dual view had independently evaluated a second
observation group, consuming additional CUDA RNG. The evidence supports this as the
identity-break mechanism; it does not demonstrate a PhysX or kernel divergence.

R15 changes only the observation realization:

- legacy raw `actor_obs[133]` is built once;
- `residual_actor_obs[133]` shares all noisy non-target terms from that same build;
- only the 18D target-pose term is replaced by the primary-cache gauge;
- the frozen base actor still consumes raw O0;
- rewards, thresholds, stages, physics, target source, action transforms, and critic
  semantics are unchanged.

The pilot trace schema was extended to record the authoritative post-delay physical
`actions_after_delay[20]`, allowing the identity gate to compare the actual physical
input as well as the 12D high-level action.

## 3. Admission gates and formal training

### R15 pilot

Canonical artifact:
`logs_eval/base_v26/v26_5_wave2_r1_policy_residual_20260831_r15/pilot/reducer.json`.

```text
typed_outcome                         R15_SHARED_O0_PILOT_ADMITTED
reset_snapshot_max_abs                0
first_base_or_physical_max_abs        0
fifty_tick_continuous_max_abs         0
terminal_discrete_identity            true
stage2_5_trace_topology_identical     true
integrity_violations                  0
```

This is sequential cold-process, seed0 LEFT, exact64, 50-control-tick runtime
evidence. No prefix alignment, pooling, or threshold relaxation was used.

### Natural K1 identity gate

Canonical artifact:
`logs_eval/base_v26/v26_5_wave2_r1_policy_residual_20260831_r15/K1/identity_reducer.json`.

All four `seed={0,1} × side={LEFT,RIGHT}` control/dual pairs passed with:

- reset snapshot delta `0`;
- policy-mean/raw-action delta `0`;
- identical full trace topology and terminal discrete evidence;
- retained raw O0 main target source;
- integrity violations `0`.

Typed outcome: `K1_R15_IDENTITY_ADMITTED`.

### Smoke and training

The 64-env, one-batch PPO smoke completed with supervisor `PASS/0` and wrote
`model_step_000001.pt`. Formal training then ran:

```text
R15_S0  seed0  GPU4  4096 envs × 250 PPO batches  PASS/0
R15_S1  seed1  GPU5  4096 envs × 250 PPO batches  PASS/0
```

Both cells produced the registered step125 and step250 checkpoints under
`logs_rl/by_batch/base_v26/v26_5_wave2_r1_policy_residual_20260831_r15/train/`.
Formal train and full-checkpoint evaluation kept post-construction reseed disabled.

## 4. Formal bilateral results

Canonical reducer:
`logs_eval/base_v26/v26_5_wave2_r1_policy_residual_20260831_r15/formal_eval_retry1/reducer.json`.

Each row is one exact64 natural side evaluation. `Sustained` is the registered
five-control predicate `stage_buf==3 and handle>=0.1 and strict_k5`.

| Step | Cell | Side | K5 | Stage3 | Contact stability | Sustained | Stage4 | Goal | Integrity |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| 125 | S0 | LEFT  | 63 | 63 | 0.9662845583 | 0  | 0 | 0 | 0 |
| 125 | S0 | RIGHT | 62 | 62 | 0.9669781270 | 0  | 0 | 0 | 0 |
| 125 | S1 | LEFT  | 64 | 64 | 0.9688139558 | 0  | 0 | 0 | 0 |
| 125 | S1 | RIGHT | 59 | 59 | 0.9663760897 | 11 | 0 | 0 | 0 |
| 250 | S0 | LEFT  | 63 | 63 | **0.7583052480** | 0  | 0 | 0 | 0 |
| 250 | S0 | RIGHT | 62 | 62 | 0.9669570761 | 0  | 0 | 0 | 0 |
| 250 | S1 | LEFT  | 64 | 64 | 0.9687743950 | 0  | 0 | 0 | 0 |
| 250 | S1 | RIGHT | 60 | 60 | 0.9493231905 | 16 | 0 | 0 | 0 |

The result should not be paraphrased as failure to reach Stage3: K5 and Stage3
admission remained high in every endpoint. The highest-priority registered kill is
caused by the single step250 stability-band failure. Independently, all four Stage4
counts being zero prevents the Stage5-relay branch, while sustained counts of zero in
S0-LEFT, S0-RIGHT, and S1-LEFT prevent the sustained-relay branch.

## 5. Formal-evaluation retry provenance

The original step125 launch under `formal_eval/` is preserved as failed execution
evidence for both seeds. Each full checkpoint loaded successfully, after which the
diagnostic initializer failed fast because it requested `push_door_handle`; the full
training state had restored the active non-zero term
`a2_stage3_handle_creation` instead.

This was repaired as a diagnostic selector only:

```text
formal diagnostic terms =
  a2_stage3_handle_creation
  a2_stage3_unlatch_hold
  push_door_hinge
  a2_stage3_stage4_hold_and_drive
```

Policy-only pilot/K1 retain their original `push_door_handle` diagnostic list. No
reward scale, checkpoint, experiment axis, reducer threshold, or decision priority
changed.

The retry was preregistered before launch in the fresh contract:
`logs_eval/base_v26/v26_5_wave2_r1_policy_residual_20260831_r15/M/static_retry1/execution_amendment_registry.json`.
It binds the retry output/log roots, diagnostic terms, supervisor-name template,
reseed-off flags, unchanged R1 route, and final reducer path. Original `M/static/`
and `formal_eval/` were not overwritten.

Retry supervisor outcomes:

```text
..._eval_retry1_r15_s0_125  PASS/0
..._eval_retry1_r15_s1_125  PASS/0
..._eval_retry1_r15_s0_250  PASS/0
..._eval_retry1_r15_s1_250  PASS/0
```

## 6. Evidence map and confidence boundary

Runtime/experiment evidence:

- pilot reducer: exact 50-tick cross-process trajectory identity;
- K1 reducer: four independent exact64 natural identity pairs;
- smoke and two training supervisor receipts: real PPO execution/checkpoints;
- retry1 formal outputs: 8 side directories and 512 completed first episodes;
- final reducer: fixed-step metrics, integrity checks, and typed route.

Static/resolved-config evidence:

- shared noisy-term construction and gauge-only replacement;
- frozen base-path input, actor/RMS load contracts, trace-v2 physical-action field;
- retry1 registry/verifier alignment and formal diagnostic-term provenance.

The experiment provides simulator policy evidence only. It provides no hardware,
sim-to-real, safety, actuator-limit, or Teacher/Student deployment evidence.

## 7. Source delivery

Immediate R14/R15 commits:

```text
5c905b7  preregister R14
9560832  reduce R14 short-pilot evidence
da12e38  share R15 residual observation noise
ee6a25a  capture trace-v2 physical pilot actions
3fd6482  preregister R15
c8203ac  align formal diagnostics and retry contract
```

Phase provenance is intentionally split: pilot, K1, smoke, and formal training are
ledger-bound to `3fd6482`; only the preserved-failure repair, formal retry1
evaluations, and final reducer are ledger-bound to `c8203ac`.

Tracked changes are grouped under:

- `gr00t/rl/config/ablation/wbmanip/base_v26_5_wave2_R14*.yaml`;
- `gr00t/rl/config/ablation/wbmanip/base_v26_5_wave2_R15*.yaml`;
- `gr00t/rl/config/env/door_open_a2_base.yaml`;
- `gr00t/rl/envs/base_task/a2_base.py`;
- `gr00t/rl/envs/legged_base_task/legged_robot_base.py`;
- `gr00t/rl/envs/door/door_open_a2_base.py`;
- `gr00t/rl/trl/trainer/ppo_trainer_a2_base_api.py`;
- `scriptsFORhuman/v26_5/v26_5_wave2_r1_r14_*`;
- `scriptsFORhuman/v26_5/v26_5_wave2_r1_r15_*`;
- `scriptsFORhuman/v26_5/a2_piper_base_v26_5_wave2_r1_policy_residual_plan_20260830.md`.

Independent focused review passed the shared-observation implementation, physical
trace field, pilot/K1 reducer semantics, formal retry contract, and final evidence
reduction. No P0/P1 remained at handoff.

## 8. Closure state for the next owner/task

- R15 experiment: complete; typed route frozen to
  `KILL_RESIDUAL_ACQUISITION_REGRESSION`.
- Follow-on experiment: `NOT_RUN` by explicit Owner stop instruction.
- Task-owned GPU4/5, IsaacSim, and output-root leases: released.
- Active task-owned writer or exclusive resource: none.
- Hardware or external write: none.
- Cloud artifact bundle/upload: none requested or produced.
- Git push: not performed.
- Unrelated untracked `scriptsFORhuman/knowledge_recap/` and
  `scriptsFORhuman/pro_reviews/`: preserved untouched.

Durable memory candidates exist: the second noisy observation-group RNG consumption
as the R14 identity-break mechanism, the R15 shared-O0 realization, and the frozen R15
kill result. Project memory files were intentionally not expanded during this
Owner-directed termination; this handoff indexes the authoritative source, runtime
artifacts, and reducer for a future task.

If a later task resumes research, it must start from the final reducer rather than
relabeling R15. The two concrete open scientific questions are the seed0-LEFT
step125→250 contact-stability collapse and the universal absence of Stage4 despite
high K5/Stage3 counts. They are handoff questions only, not an active experiment plan.
