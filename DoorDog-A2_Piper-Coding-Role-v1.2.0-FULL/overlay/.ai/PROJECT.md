# DoorDog A2_Piper project overlay

## Project identity

- Repository: `Jam-Stark/DoorDog`
- Primary branch/worktree family: `A2_Piper`
- Domain: A2 quadruped + PiPER manipulator, IsaacLab/Isaac Sim, teacher/student RL, sim-to-real door opening
- Source truth order: current local source and resolved config -> runtime artifacts -> file-based memory -> plans/history

## Protected workflow paths

The workflow migration must preserve:

```text
.codex/config.toml
.codex/agents/*.toml
MEMORY.md
memory/a2-piper/
```

Model names, reasoning effort, concurrency and role-specific TOML remain project-owned runtime configuration. The generic role must not overwrite them.

## Real execution discipline

- Inspect the current local equivalents of environment, config, trainer, actor/critic, reward, observation, evaluator and checkpoint-loading paths before changing behavior.
- Do not infer implementation from `scriptsFORhuman` plans when code differs.
- Any run longer than 30 minutes uses a named `tmux` session, exact command, source revision, resolved config, resource lease, output root and stopping condition.
- GPU, IsaacSim process, display, port, hardware and output directory are exclusive resources.
- Never assume local `logs_rl`, `logs_eval`, checkpoints or renders exist unless observed.

## IsaacLab and RL

- Verify API use against `/home/baoquanc/workspace/IsaacLab` and the installed version.
- Preserve tensor shape, dtype, device, batched indexing, manager lifecycle, action/observation ordering, reward sign/scale, reset/termination semantics and control/physics timebase.
- Runtime behavior changes require runtime evidence; policy-quality claims require registered evaluation or experiment evidence.
- Simulation limits, commands or force proxies are not hardware safety evidence.

## Memory routing

Read the minimum relevant route:

```text
MEMORY.md
memory/MEMORY.md
memory/a2-piper/MEMORY.md
relevant subsystem description.md
TODO.md / DONE.md only when current execution state matters
```

Memory routes and entries may be actively reorganized under `.ai/MEMORY_GOVERNANCE.md`, but current verified facts must not be lost or silently rewritten.

## Stage decisions and cloud handoff

Owner chooses whether a stage uses local Claude planner, cloud GPT Pro, both independently, or another roster. At a stage closure, inspect eligible untracked/ignored artifacts and prepare an allowlisted bundle when the next planning round needs them. `Pro_Space` is the standing create-only target; overwriting or deleting existing cloud artifacts is not authorized.
