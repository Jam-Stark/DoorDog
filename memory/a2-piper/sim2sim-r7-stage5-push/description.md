---
name: sim2sim-r7-stage5-push
scope: r7 push for autonomous stage5 in MuJoCo and the owner-adjudicated root cause
status: closed_owner_adjudicated_no_visual_dr_in_student_distillation
last_updated: 2026-08-20 16:31 HKT
read_when:
  - planning any MuJoCo shadow work for the C-B2H ToeOut6/v19 GRPO Student
  - re-distilling a student for sim2sim or interpreting r5-r7 evidence
  - running Isaac-side eval of a bundled student checkpoint
---

# Sim2sim r7 stage5 push — owner-adjudicated closure

Owner adjudication (2026-08-20): the C-B2H student was distilled with **no visual domain randomization** (`domain_rand.image_augmentation.enabled: False` in the exp configs, and the frozen code hard-raises if enabled). The policy therefore only recognizes the exact Isaac visual stream; the MuJoCo visual gap is not scene-fixable. The task "autonomous stage5 in MuJoCo with this checkpoint" is closed as **blocked by policy training recipe, not by the MuJoCo pipeline**.

Verified good (the MuJoCo shadow itself is faithful): full resolved action warp (r5), locomotion tracking ratio 0.69 vs Isaac ~0.70, open-loop replay of Isaac commands reproduces the trajectory to 2.2 cm at the stop point, nonvisual 81D obs surface anchor-verified closed, camera periods and age normalization match production. Standing vitals and joint kinematics sane; 8/8 episodes walk and push doors open by collision.

The decisive evidence chain: Isaac training-protocol reproduction success 0.96875 (31/32, three runs); in successful episodes base-still is common (40/63 episodes, min norm 0.017-0.026, stage chain 0→1@44→2@89→3@168→4@274→5@436 ≈ 9 s). MuJoCo physics + replayed Isaac vision sequence unlocks genuine base-still in MuJoCo (min 0.071). Live MuJoCo vision never unlocks across the full correction map: appearance sweep (monotone 0.45→0.21 floor), Isaac-true-look flat colors (0.18), unmasked target markers, FOV scaling, per-channel statistics affine, 40 s horizon, prime-then-release (re-accelerates instantly on switching back to live frames), camera channel split (single channels insufficient; only the full three-view Isaac sequence works). Consolidated verdict: `scriptsFORhuman/sim2sim/artifacts/e5/r7_consolidated_verdict.json`.

RETRACTION (r6): the eval-side Isaac reference (eval_agent_trl + base_eval) fed the policy frozen vision and a 250-step stage_overtime contract; its 0/150-goal and the C3 cross-backend-consistency claim are INVALID. Working Isaac recipe: train_agent_trl GRPO exp with policy_only checkpoint load reproduces the training protocol.

Era anchors: bundle source commit a197255212fa65dd9e02337b7971daac71c944fe (scratch clone at /home/baoquanc/workspace/sim2sim_scratch_r6/, registered for cleanup); distillation ws HEAD moves fast (DepthADD line; co-tenant is building run_a2_paired_isaac_trace.py + door_paired task data — do not duplicate).

This entry is intentionally not added to `memory/a2-piper/MEMORY.md`; add routing only during owner merge.
