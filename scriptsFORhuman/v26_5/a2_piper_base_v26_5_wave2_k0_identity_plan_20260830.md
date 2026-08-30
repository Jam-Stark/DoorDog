# base_v26-5 Wave2 K0 — CONT_STEP2000 identity source control

## Question and boundary

K0 establishes whether the unchanged `CONT_STEP2000` policy remains a valid
bilateral natural-start acquisition source under the Wave2 evaluator.  It is a
source control only: no actor, observation, action, reward, geometry-target,
or curriculum change is included.

The policy is loaded with `checkpoint_load_mode=full` from the exact
`CONT_STEP2000` checkpoint.  The sole selector is O0A0: canonicalization,
geometry-derived target, and Stage3 delta rebase are all disabled.  Each
evaluation is one natural first episode in exactly 64 environments, with
seed 0 and seed 1, independently on LEFT and RIGHT.  `enable_staged_reset`
is false.

## Registered population and gate

The four strata are `seed0×LEFT`, `seed0×RIGHT`, `seed1×LEFT`, and
`seed1×RIGHT`.  K0 is admitted only when every stratum has all of:

- Stage3 admission count at least 16/64;
- strict K5 episode count at least 16/64;
- Stage3 contact-stability rate at least 0.90;
- zero summed v26-2/v26-3 integrity violations.

Stage4, Stage5, and goal remain reported outcomes only; they do not alter the
K0 admission decision.  The reducer rejects missing, non-exact, staged-reset,
or non-O0A0 evidence instead of inventing a denominator.

## Identity and future dual-view boundary

K0 identifies the source-control evaluator contract, not a dual-view actor.
`dual_view_identity` is explicitly `NOT_RUN`: this phase defines neither an
actor implementation nor a mapping between views.  Any later dual-view work
must register its own actor implementation, view mapping, and identity proof;
it must not reinterpret this O0A0 source control as such evidence.

## Execution and artifacts

The output root is independent of Wave1:
`logs_eval/base_v26/v26_5_wave2_k0_identity_20260830_r3/`.

`v26_5_wave2_k0_orchestrate.sh preregister` writes the registry and statically
composed selector configs.  The two `eval-cell` commands each launch one
tmux-backed supervisor process and evaluate LEFT before RIGHT.  `reduce`
requires both PASS receipts and writes `K0/source_control_reducer.json`.

No GPU work is performed by preregistration or static composition.
