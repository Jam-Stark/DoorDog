# Sim2sim campaign r3 progress

Last updated: 2026-08-18 01:03 HKT

## State

| Phase | State | Evidence |
|---|---|---|
| payload correction | COMPLETE | GRPO 467/512 versus baseline 459/512 overlay |
| door constraint gate | PASS | equality lock, threshold release, post-release motion |
| L1 | COMPLETE_WITH_WARNING | 1000-step r2 81D boundary reconstruction; golden is synthetic fixture |
| L2 | PASS | exact actor-tensor inverse, zero uint8 error, channel/flip/packing proof |
| L3 | TYPED_PENDING | actual Isaac frames present, but same-state p00 RGB unavailable |
| L4 | DIAGNOSTIC_COMPLETE_INVALID_CONTROL | four 1000-step rollouts; stage-0 fixed; 40 N·m non-resolved |
| resolved-control standing gate | FAIL | 100/45 face produces `INVALID_NUMERICS`; campaign denied |
| L5 | TYPED_BLOCKED | `BLOCKED_INPUT_ISAAC_PAIRED_TRACE` |

Final typed conclusion: `PIPELINE_DEFECT_FOUND_ACTION_CONTROL_CONTRACT`.

## Phase merges

| Phase | Commit | `git merge A2_Piper` | Behind afterward |
|---|---|---|---:|
| r3 door gate | `0c35453` | already up to date | 0 |
| payload correction | `9bb3c7c` | already up to date | 0 |
| L1–L4 and resolved-effort diagnosis | `732fced` | already up to date | 0 |

## Next admissible action

Do not run another closed-loop campaign until an additive MuJoCo robot dynamics/control realization satisfies all of these simultaneously: READY resolved PD/effort surface, 200 Hz per-step clipped external PD, name-resolved control placement, finite numerics, 2 s landing PASS, and 5 s frozen-A2 PASS. After that, rerun the unchanged p00 L4 matrix and consume the transferred paired Isaac trace/RGB for L5.

No absent Isaac value is filled with zero. No GPU was used. No push was performed.
