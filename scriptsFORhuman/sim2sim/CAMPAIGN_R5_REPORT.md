# READY GRPO Student — r5 full-action-warp paired MuJoCo campaign report

Completed: 2026-08-18 23:57 HKT  
Branch: `sim2sim/a2-mujoco-shadow-evaluator-20260817`  
Final typed conclusion: `IN_CONTRACT_0_OF_8_BASE_STILL_STUDENT_UNDER_GAP_EVIDENCE`  
P2 discriminative probe: `COMMAND_DYNAMICS_NEVER_CONVERGE_FROM_CLEAN_IN_BAND_START`

## Outcome

r5 executes the r4 owner adjudication: the recurring `BASE_COMMAND_CLIP` contract defect is repaired by routing every action through the resolved production warp (`FullActionWarpR5`, thresholds loaded from the config snapshot, never hardcoded), the full actor→simulator transform chain is audited `NONE_MISSING` with a scripted full-path probe, and the unchanged eight-case manifest is re-run under in-contract commands.

The result is now behavioral evidence rather than a pipeline artifact: the GRPO-finetuned Student walks toward the door in 8/8 cases on the clipped 0.5/0.5/0.5 command envelope, saturates the x/z (and most y) command caps for the large majority of every episode, and never once issues a base-still command (first-three norm `<= 0.1`) — the minimum in-contract command norm per case ranges 0.379–0.436. Stage1 therefore never enables and the arm correctly stays in stage-0 hold. The pre-authorized staging-band probe then initializes the robot stationary inside the band with zeroed command history and naturally evolving LSTM state: command dynamics still never converge (0/1000 base-still steps, minimum norm 0.495), and the robot walks out of the band (+1.15 m net x). This splits the attribution away from "did not visually recognize the arrival configuration during approach": even a clean in-band rest start does not produce converging commands. Formal visual attribution remains blocked on the mandatory paired `t=0` Isaac frames; nothing here relaxes that requirement.

The 8/8 hinge open-threshold crossings (up from 4/8 in the void r4 run) remain collision-driven: zero unlatch events, zero purposeful post-stage arm use.

## P0 — base command warp restored

- Production truth: `gr00t/rl/envs/base_task/a2_base.py:1163-1188` scales the raw 5D base action (0.25 xyz / 0.4 pitch-roll), clamps posture to `[-1,1]*0.4`, then applies the resolved 5D clamp `±[0.5,0.5,0.5,0.4,0.4]` from `clip_homie_command` (config_snapshot.yaml:1564-1567) before writing `_homie_commands`.
- r5: `ResolvedActionWarpContractR5` refuses any config without `clip_homie_command: true`; the clipped physical command feeds the gait clock, the A2 base frame builder, the observation echo (multipliers 2/2/0.25/1/1 + 0.1 deadband, unchanged), the stage predicate, `stage_trace.jsonl`, and every receipt norm field.
- The defect fix is confined to sim2sim-new files; `door_open_a2_base.py` and all shared production paths are untouched.

## P0b — full action-warp audit (`NONE_MISSING`)

Eleven transform nodes between actor output and simulator write are enumerated with file:line production anchors in `action_warp_r5/action_warp_contract_receipt.json`: delta accumulate/clip/stage gate, base warp (k=0,s=0 identity), v22/v23 interventions (disabled), base scale+posture clamp+final 5D clamp, echo+deadband, gripper primitive, leg name map, FINAL_20D clip (action_clip_value=100), control delay (disabled), position target + name-resolved write, and action/delta observation echo. The scripted probe feeds raw high-level actions (±4 raw base, ±150 leg) through the complete path and verifies the physical caps `[0.5,-0.5,0.5,0.4,-0.4]`, the stage-0 arm hold, the 12-joint final clip, the staging advance after a clipped-zero command, and the first stage1 delta at 0.3.

## P1 — standing vitals gate re-run (runner binary changed)

| Gate | Result |
|---|---|
| passive landing 2 s | PASS; final base 0.49242 m; tail span 0.00458 m |
| frozen A2 5 s through full warp | PASS; final base 0.44315 m; tail span 0.00386 m; max roll/pitch 0.03577 rad; 0 final-clip steps |
| mapping/effort | PASS; write error 0; generalized-force error 0; effort over-limit 0 |

Vitals-before-metrics was not waived; the gate receipt authorizes the campaign.

## P1 — campaign

Manifest, seeds, scene, and paired schema are unchanged from r4 (r4 artifacts byte-preserved; supersession receipt `r4_supersession_receipt.json`).

| Metric | r5 result |
|---|---:|
| cases / policy steps / physics steps | 8 / 8,000 / 32,000 |
| terminal reason | 8 HORIZON; 0 BASE_HEIGHT; 0 INVALID_NUMERICS |
| cases moving toward door | 8 |
| cases reaching stage1 | 0 |
| base-still steps (norm `<= 0.1`) | 0 in every case |
| min in-contract command norm by case | 0.3789 – 0.4356 |
| command clip steps by axis (x,y,yaw,roll,pitch; totals / 8000) | 7552 / 3528 / 7912 / 0 / 0 |
| command at-cap steps by axis (totals / 8000) | 7552 / 3528 / 7912 / 7829 / 4562 |
| final-20D action clip steps (total) | 0 |
| unlatch events | 0 |
| hinge threshold crossings | 8 (collision-driven) |
| max abs qacc | 1946.83 |

Stage predicate diagnostics (`stage_predicate_diagnostics.json`): arm-default check passes at all 1,000 policy steps in every case; x-band residence occurs (45–255 steps/case) but the full x+y band condition holds at zero steps and base-still at zero steps — the command norm is the binding blocker, and under the contract it never comes close.

Posture axes reach the ±0.4 cap through the production `[-1,1]` posture clamp (at-cap without an additional final-5D clip), which is why their clip counters are 0 while at-cap counters are high — this matches production semantics exactly.

## P2 — staging-band discriminative probe (pre-authorized, after campaign)

`staging_band_probe_r5/`: robot stationary at dx=0.65, dy=0, arm at default, zero velocities, zeroed command history, LSTM reset then naturally evolved, full camera rig and full warp.

- base-still steps: 0 / 1000; minimum command norm 0.495; median 0.781.
- stage1: never; in-band residence only 37/1000 steps; net root motion +1.15 m x.
- Typed: `COMMAND_DYNAMICS_NEVER_CONVERGE_FROM_CLEAN_IN_BAND_START`.

Interpretation bound: this rules out "approach-phase history/visual-transient" as the sole cause and shows the Student's command generation itself never converges to base-still in this MuJoCo shadow, even when started in-band at rest. It does not by itself clear or condemn the visual channel (the probe still uses MuJoCo renders); the formal visual verdict stays blocked on paired `t=0` Isaac frames (E5 unchanged).

## Comparator

Evidence level E5; classification `EXPLORATORY_NON_COMPARABLE`; input status `BLOCKED_INPUT_ISAAC_PAIRED_TRACE`; numeric error null; all 32,000 rows schema-valid.

## Preserved prior classifications

- r2 campaign: `INVALID_PIPELINE_SUPERSEDED_BY_R3`; door-learning result VOID.
- r3 diagnostics retained verbatim (owner-accepted).
- r4 campaign: `INVALID_PIPELINE_SUPERSEDED_BY_R5` (BASE_COMMAND_CLIP recurrence + missing FINAL_20D clip); r4 structural items (stage contract, true 100/45 surface, scene/manifest/schema, visual envelope) retained as valid.

## Primary evidence

- Campaign receipt and traces: `scriptsFORhuman/sim2sim/artifacts/e5/paired_mujoco_campaign_r5/`
- Action-warp audit: `scriptsFORhuman/sim2sim/artifacts/e5/action_warp_r5/`
- Standing gate: `scriptsFORhuman/sim2sim/artifacts/e5/standing_vitals_gate_r5/`
- Staging-band probe: `scriptsFORhuman/sim2sim/artifacts/e5/staging_band_probe_r5/`
- Owner adjudication: `scriptsFORhuman/sim2sim/artifacts/e5/r4_owner_adjudication.json`

CPU/Xvfb/llvmpipe only; no GPU lease; no push. A2_Piper behind=0 (merged at `b000ecf`).
