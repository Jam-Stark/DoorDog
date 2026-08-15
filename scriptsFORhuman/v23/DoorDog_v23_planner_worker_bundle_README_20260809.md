# DoorDog v23 Planner/Worker Bundle

This bundle converts the v23 research-design DOCX into two copy-ready session prompts and one machine-readable execution contract.

## Files

1. `DoorDog_v23_training_design_v0.1_20260809.docx`  
   Scientific design and rationale.

2. `DoorDog_v23_local_planner_audit_prompt_20260809.md`  
   Give this file, the DOCX, and repository access to the local planner first.

3. `DoorDog_v23_worker_implementation_prompt_20260809.md`  
   Give this to the worker only after the planner has produced the required approved plan, manifests, source audit, and patch table.

4. `DoorDog_v23_planner_worker_execution_contract_20260809.yaml`  
   Machine-readable starting contract. Fields marked `PLANNER_MUST_FREEZE` or `P0_FREEZE_REQUIRED` must not be guessed.

## Recommended workflow

```text
Step 1:
  Local planner reads source first and audits the DOCX.

Step 2:
  Planner returns one formal decision and writes the repository-ready R1 plan,
  scientific manifest, source audit, selection rule, and patch table.

Step 3:
  Worker reads the approved planner outputs and implements P0 only.

Step 4:
  Strict adjudicators freeze torque authority, effort profile, D0/D1,
  reward registry, RP0 semantics, state bank, and formal config hashes.

Step 5:
  Worker launches the two 8-GPU waves and completes Route A/Route B.

Step 6:
  Worker updates the POST-v23 long-term TODO without implementing those items
  in the v23 core branch.
```

## Critical separation

```text
planner = audit, resolve source facts, freeze scientific contract
worker  = implement, test, execute, produce evidence
```

The worker must not silently resolve an ambiguity that the planner was required to freeze.
