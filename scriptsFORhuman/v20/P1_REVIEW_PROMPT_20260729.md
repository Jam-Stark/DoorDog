# Prompt: review the base_v20 P1 blocker

You are reviewing the current \`A2_Piper\` branch of the DoorDog repository and
the preregistered plan
\`scriptsFORhuman/v20/a2_piper_base_v20_optimization_plan_20260728.md\`.

Your task is to make one explicit scientific/engineering decision:

1. preserve P1 and provide one bounded fix that can realistically satisfy it;
   or
2. recommend skipping/replacing P1, with an explicit plan revision and a clear
   statement of which physical-feasibility claim is being abandoned.

Do not describe a skipped or weakened P1 as \`P1 PASS\`. Under the current plan,
P1 is a hard pre-training gate: select \`theta_send >= 0.90 rad\` using F0 first,
or F1 bounded relief (\`0.10 m\` planar translation and \`0.15 rad\` yaw), with at
least \`46/48\` strict-valid feasible episodes. Formal base_v20 training is
currently forbidden.

## Current implementation snapshot

The branch contains the base_v20 I/E/A task semantics, reward/config changes,
reporting/launcher scripts, seven formal configs, CPU tests, and an eval-only
live-grasp DLS arc probe. Important files are:

- \`gr00t/rl/envs/door/door_open_a2_base.py\`
- \`gr00t/rl/trl/trainer/ppo_trainer_a2_base_api.py\`
- \`gr00t/rl/config/base_eval.yaml\`
- \`scriptsFORhuman/v20/a2_piper_v20_arc_feasibility.py\`
- \`gr00t/rl/tests/test_a2_v20_arc_feasibility.py\`
- \`gr00t/rl/tests/test_a2_v20_taskspace_carry.py\`

The current CPU-only base_v20 suite passes (\`87 passed\`), Python compilation
passes, and \`git diff --check\` passes. These are static results only and do not
establish P1 runtime feasibility.

## P1 runtime evidence

- No completed smoke produced an \`ARC_PROBE_REACHED\` episode.
- R14 F0: three \`JOINT_LIMIT\`, one \`ARC_PROBE_TIMEOUT\`. Three environments
  nevertheless reached about \`2.618 rad\` hinge motion, but with invalid
  joint/root state; this argues against declaring simple geometric
  impossibility from the present evidence.
- R21 F0 task-space settle: \`4/4 JOINT_LIMIT\` before formal capture.
- R22 F1: two \`JOINT_LIMIT\`, one \`ARC_PROBE_OVERSPEED\`, one
  \`ARC_PROBE_ROOT_BOUND\`; only two captures were valid, and the captured root
  reference included substantial pre-capture motion.
- R23 changed handoff to activation-time canonical capture after a continuous
  bilateral-hold/stable-root streak, but the run was interrupted before it
  produced a strict-valid summary or trace. Treat R23 as \`INCONCLUSIVE\`.

## Highest-priority suspected control defect

The current arc-target computation advances the persistent hinge reference
before the caller decides whether the proposed DLS arm command is legal. If the
proposal violates a joint limit, F1 executes base relief instead of the arm
command, but the reference has already advanced. Repeated relief steps can
therefore accumulate an unexecuted arc target and increase the residual.

The preferred bounded repair is transactional reference advancement:

- compute a proposal without mutating persistent reference state;
- commit the next reference only for \`arm_mask\` environments whose arm action
  is actually applied;
- freeze the reference during \`relief_mask\` steps;
- synchronize the held arm target to physical joint state during relief;
- resume arc advancement only after relief restores a legal DLS proposal;
- retain the exact P1 thresholds and F1 motion bounds.

The file also contains investigation-era settle state whose active mask is now
hard-zeroed. Decide whether it must be removed before the next candidate so
that there is only one handoff/capture semantic.

## Required response

Return the following sections:

1. \`DECISION\`: \`FIX_P1\`, \`REVISE_AND_SKIP_P1\`, or \`P1_PHYSICAL_BLOCKER\`.
2. \`EVIDENCE\`: decide whether the failures come from capture bookkeeping,
   reference transaction, DLS/control design, or demonstrated geometry.
3. \`EXACT_CHANGES\`: list functions/config keys/files to change. Do not suggest
   open-ended gain sweeps, threshold relaxation, silent fallback, realistic-arm
   limit changes, or force-feasibility/base-assist work unless you explicitly
   revise the scientific scope.
4. \`BOUNDED_VALIDATION\`: define one 4-env smoke and the canonical pooled test.
   Recommended go/no-go: the first F1/0.90-rad/seed0/4-env smoke must be \`4/4\`
   canonical captures and \`4/4 ARC_PROBE_REACHED\`, without joint-limit,
   IK/action, overspeed, root-bound, crossing, collision, or contact failure.
   If it fails after the single repair, stop rather than starting another
   iterative control revision.
5. \`PLAN_IMPACT\`: if skipping P1, list the exact plan claims/gates that must be
   removed or downgraded and explain whether base_v20 can still be called a
   release or only an exploratory training matrix.
6. \`TRAINING_READINESS\`: explicitly state whether G1-G7 may launch. Any future
   run must use physical GPUs 0-6 only; physical GPU7 is unavailable.

Use fail-fast semantics and IsaacLab high-level APIs. Distinguish \`STATIC PASS\`,
\`RUNTIME PASS\`, \`POLICY PASS\`, \`STRICT_INVALID\`, and \`INCONCLUSIVE\`. Do not
infer physical feasibility from hinge motion alone, and do not infer
impossibility from invalid probe-control trajectories.
