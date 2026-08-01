# base_v20 R1 static-admission blocker handoff

Date: 2026-07-30 HKT

## Frozen inputs and candidate

- Plan: `scriptsFORhuman/v20_R1/a2_piper_base_v20_R1_optimization_plan_20260729.md`
- Plan SHA256: `6827290631feea15497fe76cd64116c30a1343d5bd6c1cb83ba09c35bc247e3c`
- Base Git SHA: `338cacfb6757d37eac7d82768b49514a6aa9ab34`
- Final reviewed candidate ID: `e719ea28fde644c870532e2bb698940abbb9d187ea413f9ac815d628a5e2417a`
- B0 JSON SHA256: `98654a976be8b6593e796d89291b4dc6ebdf530d078c625db7130d7a1622c826`
- B0 CSV SHA256: `209b33a1fa9d79d60f715518cc2798f96b13d71aea8fb2aac0f520a516f4585a`
- Warm-start checkpoint SHA256: `b331c9a343c71dccf6cce31f71c1727a24298d72808c25763a0f702c369a866d`
- GPU contract: non-render uses physical `cuda:N` without `CUDA_VISIBLE_DEVICES`; render uses `CUDA_VISIBLE_DEVICES=N` plus logical `cuda:0`; GPU7 is forbidden.

The exact B0 companion files are retained under `scriptsFORhuman/v20_R1/`.

## Evidence that passed

- Exact B0 companions: 2/2 hashes PASS.
- Exact historical B0 sources: 6/6 hashes PASS.
- Source R1 Hydra matrix: G1-G7/P2 composition PASS.
- Promoted frozen Hydra group dry composition PASS.
- Full CPU suite before final review: 150 tests PASS; focused R1 suite: 54 tests PASS.
- Final CPU preflight command exited 0 and emitted `STATIC PASS`; manifest coverage was source/script/test `6/18/9`, Hydra count 8.
- `git diff --check` PASS.

These static results do not override the substantive reviewer failures below.

## Binding reviewer outcome

Frozen candidate `e719ea28...417a` received:

- `CODE_QUALITY: FAIL`
- `ISAACLAB_SEMANTICS: FAIL`
- `CANDIDATE_GATE: FAIL`
- CPU QA was runner-limited, but its missing execution evidence is not the blocker because the confirmed source/contract defects independently fail admission.

No R1-P0/P1 GPU runtime, pilot, smoke, formal training, M22, holdout, or render attempt was authorized or consumed.

## Confirmed blockers

### 1. M45/M47 runtime semantics

- Stage-5 snapshot compatibility is wrong: every stage-5 snapshot is rejected instead of rejecting only unsent/incompatible entries.
- Task-space helper validates finite inputs but does not validate finiteness of computed cross-products, sums, and ratios.

### 2. M48 production evidence is internally unusable

- Live endpoint normalizer emits scalar `trace.step_index`; reporter requires a non-empty contiguous list.
- Required smoothness/income metrics are emitted as all-N/A, while aggregation rejects all-N/A core metrics.
- Production records omit or weakly bind plan-required provenance, checkpoint/config/URDF hashes, phase/transition, safety, send, task-space, income, and trace facts.
- Tests do not send production-generated records through the actual reporter and aggregation path.

### 3. R1-P1 semantic admission is self-attested

- Command builders exist, but the admission CLI does not execute them.
- Caller-authored JSON with declared status/check booleans/counts can emit `RUNTIME SEMANTIC PASS`.
- Exact Appendix E.3 parity, forced one-environment assertions, seven canonical16 artifacts, command exits, record schemas, and artifact hashes are not mechanically consumed end to end.

### 4. Pilot/smoke/promotion/formal DAG is not executable

- Smoke wrappers require attempt markers that their exposed CLI never creates.
- Smoke adjudication incorrectly requires identical config hashes across distinct G1-G7 configs.
- Promotion CLI omits required chain arguments and depends on a pre-promotion `POLICY PASS` artifact with no non-circular producer.
- Formal admission permits missing commit binding, passes the admission hash to an incorrect Hydra key, and labels unexecuted launch manifests as runtime PASS.

### 5. M22/pooled/holdout/render/final chain is incomplete or bypassable

- M22 rows are not uniquely matched to all 70 manifest entries; duplicate/substituted rows can pass.
- M22 CLI exposes only a single-group path and does not load the promoted frozen Hydra group end to end.
- Render queue does not execute a renderer; adjudication trusts self-declared result JSON and does not validate videos/topology/overlays.
- No complete selected-pooled48 or holdout64 producer/adjudicator exists.
- Final selection can violate the preregistered simplest-passing-group rule and trusts shallow generic artifacts.

### 6. P0 coverage remains below the full plan contract

- The final preflight improved source/config coverage, but the candidate gate still found missing full base-v20 test coverage, required `py_compile`, `git diff --check`, parity/dimension/hidden-action checks, and canonical timestamp/output enforcement inside the admission artifact itself.

## Required decision

Do not patch individual booleans or labels again. Return one complete, acyclic and executable R2 admission/evaluation design that specifies:

1. The single production M48 schema and every live accumulator/source field.
2. Exact runner -> raw artifact -> strict adjudicator contracts for P0, B0, forced semantics and seven zero-shot cells.
3. An acyclic `P0 -> P1 -> pilot -> smoke -> promotion -> formal` artifact DAG with canonical marker/output locations.
4. Exact 70-row M22 manifest matching, selected pooled48, holdout64, matched render execution/QA, and mechanical single-winner/no-release logic.
5. Concrete CLI signatures, required arguments, schemas, typed statuses, hash bindings and negative tests for every stage.
6. Explicit statement whether existing revision-4 code is to be repaired, replaced, or discarded.

Until such a design is approved, the formal readiness state is `R1_STATIC_ADMISSION_BLOCKER`.
