# Prompt for the v20/R1 plan author

You are reviewing a failed implementation of `a2_piper_base_v20_R1_optimization_plan_20260729.md`.

Read all files in the supplied handoff ZIP, especially:

- `base_v20_R1_static_admission_blocker_summary_20260730.md`
- `base_v20_R1_candidate_manifest_revision4.json`
- `R1_SCIENTIFIC_MANIFEST.json`
- the authoritative R1 plan, exact B0 companions, and revision-4 candidate sources/tests.

The frozen candidate ID is `e719ea28fde644c870532e2bb698940abbb9d187ea413f9ac815d628a5e2417a`. Static tests and Hydra composition passed, but independent CODE_QUALITY, IsaacLab and candidate-acceptance reviews all failed on substantive execution/admission defects. Do not recommend bypassing a gate, accepting caller-declared PASS JSON, or starting pilot/formal training.

Return exactly one decision:

1. `FIX_R1_ADMISSION`: provide a complete replacement/repair plan; or
2. `AMEND_R1_PLAN`: explicitly revise specific scientific gates with evidence and new frozen hashes; or
3. `STOP_R1`: declare the policy-training plan blocked and explain why.

If choosing `FIX_R1_ADMISSION`, produce a repository-ready R2 Markdown plan with no generic placeholders. It must include:

- the exact files/functions to retain, replace, add or delete;
- the complete M45/M47 snapshot/task-space semantics;
- one production M48 record schema and exact live accumulator mapping;
- an executable P0/B0/forced/seven-cell semantic runner and strict adjudicator;
- an acyclic pilot/smoke/promotion/formal artifact DAG;
- exact marker paths, output roots, CLI parameters, schemas, typed statuses and hashes;
- strict 7x10 M22 matching, selected pooled48, holdout64, real matched render execution/QA, and final simplest-passing-group/no-release logic;
- the verified device contract: non-render physical `cuda:N` without visibility mask; render visibility mask plus logical `cuda:0`; GPU7 forbidden;
- positive and negative acceptance tests that prove each bypass is rejected;
- a bounded implementation order and a stopping rule that prevents another open-ended revision loop.

For every proposed gate, name the raw evidence producer, artifact schema, strict consumer/adjudicator, and exact condition that advances the DAG. If a required metric has no existing runtime accumulator, explicitly specify where and how it is accumulated; do not use generic N/A or default zero.
