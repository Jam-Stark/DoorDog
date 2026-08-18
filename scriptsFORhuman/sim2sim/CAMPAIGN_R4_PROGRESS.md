# Sim2sim campaign r4 progress

Last updated: 2026-08-18 11:35 HKT

## State

| Phase | State | Evidence |
|---|---|---|
| P1 stage contract | PASS | exact thresholds/ordering plus scripted approach |
| P2 qacc localization | COMPLETE | first huge-qacc arm_j4 at step 11 / 0.055 s |
| P2 true 100/45 standing | PASS / AUTHORIZED | native position + implicitfast; landing/frozen/mapping pass |
| P3 visibility | PASS | sites/debug group 5 masked on exact policy render path |
| P3 structure/appearance | PASS_WITH_FORMAL_CAMERA_PENDING | inset door; luma/hue envelope pass; camera unchanged |
| P4 full MuJoCo campaign | COMPLETE | 8 cases, 8,000 policy, 32,000 physics steps |
| E5 comparator | TYPED_BLOCKED | `BLOCKED_INPUT_ISAAC_PAIRED_TRACE` |

Final typed conclusion: `UNRESOLVED_PENDING_E5`.

## Phase merges

| Phase | Commit | `git merge A2_Piper` | Behind afterward |
|---|---|---|---:|
| pre-r4 synchronization | `a3ace7e` | merged A2_Piper | 0 |
| P1 stage contract | `ab65398` | already up to date | 0 |
| P2 true 100/45 | `ca8abe7` | already up to date | 0 |
| P3 visual parity | `536e6b0` | already up to date | 0 |
| P4 campaign | `ab82c51` | already up to date | 0 |
| retained-classification correction | `5389ef6` | already up to date | 0 |

## Runtime record

The first launcher attempt exited immediately at the IsaacLab wrapper's non-interactive terminal setup and produced no campaign directory. The second direct-Python attempt failed before simulation because the command named a nonexistent robot path. Its p00-only partial builder directory was preserved at `/tmp/doordog_campaign_r4_bad_robot_path_20260818`. The successful launch used the conda environment Python, `PYTHONPATH=.`, `MUJOCO_GL=glx`, `LIBGL_ALWAYS_SOFTWARE=1`, `xvfb-run`, and `gr00t/rl/data/mujoco/A2_Piper/a2_piper.xml`.

Gradient checks: at 60 s the process was live, p00 trace was advancing, and no error/NaN was present; at the next check p00/p01 were complete; the 600 s interval completed six cases; the final interval completed all eight. Successful runtime log: `artifacts/e5/runtime_logs_r4/campaign_r4.log`.

## Next admissible action

Receive schema-aligned Isaac traces plus exact policy-input `t=0` left/right/head frames for at least p00, then run the existing comparator and first-discrete-point attribution. Do not change MuJoCo extrinsic/FOV before that evidence arrives. Missing Isaac values remain typed and are never filled with zero.

No GPU was used. No push was performed.
