# DoorDog A2_Piper project overlay

## Project identity

- Repository: `Jam-Stark/DoorDog`
- Primary branch/worktree family: `A2_Piper`
- Domain: A2 quadruped + PiPER manipulator, IsaacLab/Isaac Sim, teacher/student RL, sim-to-real door opening
- Source truth order: current local source and resolved config -> runtime artifacts -> file-based memory -> plans/history

## Protected workflow paths

Workflow migration must preserve:

```text
.codex/config.toml
.codex/agents/*.toml
MEMORY.md
memory/a2-piper/
```

Model names、reasoning effort、concurrency 和 role-specific TOML 属于项目 runtime 配置，通用 role 不覆盖它们。

## Real execution discipline

- Inspect current local environment、config、trainer、actor/critic、reward、observation、evaluator 和 checkpoint-loading paths before changing behavior.
- Do not infer implementation from `scriptsFORhuman` plans when code differs.
- Never assume local `logs_rl`、`logs_eval`、checkpoints 或 renders exist unless observed.
- A single bounded QA or temporary test does not require team state. Use coordination facilities only when the trigger is real.

## Resource ownership

Lease only actual exclusive resources: overlapping writer paths、GPU、IsaacSim process、display、port、hardware 或 output root. Read-only agents do not receive leases. A single already-authorized long run may use a run receipt without activating the full team ledger.

## IsaacLab and RL

- Verify API use against `/home/baoquanc/workspace/IsaacLab` and the installed version.
- Preserve tensor shape、dtype、device、batched indexing、manager lifecycle、action/observation ordering、reward sign/scale、reset/termination semantics 和 control/physics timebase.
- Runtime behavior changes require runtime evidence; policy-quality claims require registered evaluation or experiment evidence.
- Simulation limits、commands 或 force proxies 不是 hardware safety evidence.

## Memory routing

For non-trivial implementation、debugging、review 或 stage planning, read only the minimum relevant route:

```text
MEMORY.md
memory/MEMORY.md
memory/a2-piper/MEMORY.md
relevant subsystem description.md
TODO.md / DONE.md only when current execution state matters
```

A self-contained typo、prose edit 或 isolated syntax check may skip deep memory reads when no historical fact can affect the result. Memory restructuring is candidate-triggered, not a mandatory final phase.

## Stage decisions and cloud handoff

Owner chooses whether a stage uses local Claude planner、cloud GPT Pro、both independently，or another roster. Artifact packaging and Pro_Space upload happen only when Owner requests them or the current stage contract explicitly enables handoff. Ordinary task completion does not create a bundle.

### Cloud Pro delivery configuration

- Git remote used by cloud reviewer: `origin`
- Branch or review branch: current approved task branch
- Owner-requested Cloud Pro handoff authorizes in-scope commit and push unless Owner explicitly says otherwise
- Drive task folder: stores only `worker_delivery__*` input artifacts
- Pro delivery transfer: Owner uploads `pro_delivery__full_review.zip` in the local Worker conversation; Cloud Pro does not upload it to Drive
- Pro review document root: `scriptsFORhuman/pro_reviews`
- Placement rule: `scriptsFORhuman/pro_reviews/<stage-or-release>/<commit-short>/`
- Cloud conclusions do not replace local source、resolved config、IsaacLab/GPU runtime、logs or hardware evidence
