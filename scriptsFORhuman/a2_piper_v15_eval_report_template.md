# A2+Piper v15 M22 evaluation/release report template

This template is the release gate for the v15 round. It records the v14
reference checkpoint and requires a side-by-side midpoint/endpoint redline.
A report MUST select a release checkpoint from the redline metrics; it MUST
NOT default to the last checkpoint or to the numerically highest step.

## Reference release

- v14 release checkpoint: logs_rl/a2_piper_full_stage_a2_base/base_v14_main-20260719_103629/model_step_002000.pt
- Release identity: base_v14_main-20260719_103629 / model_step_002000.pt
- v14 release evidence: seed0, 16 environments, height-stratified matched scalar/trace eval.
- Reference outcome: 16/16 goal and 16/16 complete; 16/16 crossing-while-holding;
  bilateral positive-motion 95.947605%; coasting 4.011461%; hinge velocity p95
  0.491563 rad/s; over-force 0%.
- v14 step3000 is an endpoint comparator, not the default release:
  goal 16/16, crossing-while-holding 14/16, bilateral 94.710327%, coasting
  5.289673%, hinge velocity p95 0.548683 rad/s, over-force 0.293871%.
  The step2000 release was selected because the redline behavior was better
  despite step3000's higher mean reward.

## Run provenance

- Experiment/config:
- Seed and environment count:
- Midpoint checkpoint(s):
- Endpoint checkpoint(s):
- Matched eval artifact paths:
- Runtime exit/evidence status:
- Runtime NOT RUN / PASS / FAIL (choose one; do not infer from static tests):

## Mandatory midpoint/endpoint redline

Fill every row for every candidate. “N/A”, missing telemetry, or a non-finite
value is an evidence failure and cannot produce a release selection.

| Candidate checkpoint | goal / complete | crossing while holding | bilateral positive-motion | coasting | hinge velocity p95 (rad/s) | over-force | Runtime/artifact |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| v15 midpoint (step ___) | ___ / ___ | ___ / ___ | ___ % | ___ % | ___ | ___ % | ___ |
| v15 endpoint (step ___) | ___ / ___ | ___ / ___ | ___ % | ___ % | ___ | ___ % | ___ |
| v14 reference step2000 | 16 / 16 | 16 / 16 | 95.947605 % | 4.011461 % | 0.491563 | 0 % | matched PASS |
| v14 comparator step3000 | 16 / 16 | 14 / 16 | 94.710327 % | 5.289673 % | 0.548683 | 0.293871 % | matched PASS |

### Redline decision

- Candidate selected:
- Selection rationale: compare goal, crossing-holding, bilateral,
  coasting, hinge velocity p95, and over-force side by side. State every
  threshold and any observation-only metric separately.
- Why the selected candidate is not simply the last checkpoint:
- Unresolved guardrails/observations:
- Release artifact path and checkpoint hash:

## Required interpretation

1. Goal/complete is necessary but not sufficient.
2. Crossing-while-holding, bilateral contact, coasting, hinge velocity p95,
   and over-force must all be reported for midpoint and endpoint.
3. If endpoint quality regresses after a saturated goal midpoint, keep the
   best redline candidate and stop/release there; do not chase reward or
   use the final saved step by default.
4. Static source tests are not runtime evidence. A release claim without
   matched runtime artifacts is NOT RUN or INCONCLUSIVE.

## M23 reachability attachment

Attach the complete M23 pitch-aware dynamic reachability report:

- 3 mandatory anchors first: pitch 0 rad, standoff 0.60 m, handle heights
  0.95/1.00/1.05 m. Any anchor failure blocks grid success artifacts.
- 108 cells: physical pitch 0/0.20/0.40 rad (raw pitch = physical/0.4),
  standoff 0.45–0.85 m in 0.05 m steps, handle heights 0.95/1.00/1.05/1.10 m.
- Every cell must include finite evidence, physical pitch match, TCP error
  <0.03 m, no self-collision, minimum arm joint margin >0.1 rad, and
  base stability/no fall/no terminal.

## Closure

- Release selected by this redline:
- Report author/date:
- Reviewer/runtime QA:
- Follow-up decision (M24+):
