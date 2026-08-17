# C-B2H v19 Student Distillation Diagnosis Handoff

**Date:** 2026-08-02 HKT

**Repository:** `Jam-Stark/DoorDog`

**Branch:** `codex/a2-v13-student-distillation-20260717_2103`

**Runtime reconstruction:** `c18aea8bdc1c76ce850b5223663d0ad8a7474c0a` (`v19`, explicitly user-approved reconstruction)

**Distillation route:** `C-B2H-DUALRAW-SHAREDENC-TOEIN20-V19`

## 1. Question to diagnose

The completed C-B2H v19 Student distillation produced a technically valid checkpoint and a valid Student-only evaluation run, but the learned policy quality was worse than expected. The main question is whether the degradation is primarily caused by:

1. `64 env` and `10,000 iterations` being insufficient;
2. the dual-D435i + OEM Head fusion architecture or its implementation;
3. 100% Teacher-controlled rollout causing closed-loop covariate shift;
4. a weaker Teacher/runtime ceiling;
5. evaluation/render nondeterminism or another confounder.

The required output is an evidence-ranked next-step plan, not an assumption that more training is automatically the answer.

## 2. Frozen training identity

### Teacher

```text
checkpoint:
  /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/a2_piper_full_stage_a2_base/base_v19/base_v19_G2_norm_control-20260727_012027/model_step_002000.pt
sha256:
  b331c9a343c71dccf6cce31f71c1727a24298d72808c25763a0f702c369a866d
size:
  29,996,147 bytes

config:
  /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/a2_piper_full_stage_a2_base/base_v19/base_v19_G2_norm_control-20260727_012027/config.yaml
sha256:
  65c1537b38d670097bc8498428e0aad1705c3fd66eeef41a93d63e3b6da4cf96

teacher manifest:
  logs_rl/cb2h_v19_runtime/g2_step2000_c18_reconstruction_candidate6168e6a2/teacher_manifest.json
sha256:
  479f4460d4dc05feea9d87d3189fa0617b21078f91b6f5176f4a9c41b141d1b7
```

The ZIP contains the Teacher checkpoint/config under `external_teacher_input/` and the manifest under its repository-relative path.

### Student formal run

```text
output:
  logs_rl/cb2h_v19_distill/cb2h_v19_g2s2000_gpu7_64e_10k_fix0f9c11e_retry1

checkpoint:
  model_step_010000.pt
sha256:
  005705dc033605a24bc231b18fbfaabe3288a699130a7ce2e423eac736963a45
size:
  294,256,699 bytes

config sha256:
  24f94faeca0270928c9c3ff33568e50371dc4f2f3feb767f6fe0607bb084351f
resolved config sha256:
  97663fb8f6072eff0b074744abd29a14be4f0815c150f1ed5c426a078b58a5e3
exact command sha256:
  34a717de741b361378d8847587ff6e05b71075fa38491abfbd8d89b07ccb51e3
```

Training was bound to physical GPU7 / logical `cuda:0`, `num_envs=64`, `num_steps_per_env=8`, `num_mini_batches=4`, `num_learning_epochs=1`, and `num_total_batches=10000`.

The trainer reported:

```text
Total episodes: 640000
Total timesteps: 5120000
Total time: 71563.05s  # 19h 52m 43s accumulated trainer time
```

Filesystem wall time from `run.log` creation to final checkpoint creation was approximately `25h 48m`. The run reached checkpoint completion, then Kit did not provide a natural post-close completion marker; this lifecycle issue does not invalidate the checkpoint but must not be called a clean lifecycle PASS.

An exact 128-env admission attempt previously OOMed before the optimizer step, with observed GPU memory near `47,959 MiB`. The formal long run therefore used exact 64 env. Do not silently lower resolution/env or use CPU fallback in future experiments; if an approved resource configuration does not fit, report it as blocked.

## 3. Formal Student evaluation evidence

### v19 C-B2H

```text
path:
  logs_eval/cb2h_v19_student_step10000_seed0_16env_gpu7-20260802_031735/formal_student_metrics.json
protocol:
  Student-only, seed0, 16 env, one completed episode per env
goal:
  0 / 16
max-stage distribution:
  stage0: 12
  stage1: 2
  stage3: 2
mean max stage:
  0.50
mean reward:
  -174.8953719139099
terminal reason:
  16 / 16 stage_overtime
```

Canonical formal selection was env13 / episode0, `stage3`, `goal=false`, reward `-214.9512176513672`.

### v16 C-B comparison

```text
path:
  logs_eval/a2_piper_student_v16_cb_ckpt5000_seed0_16env_gpu7-20260729_132948/results/metrics_eval.json
protocol:
  Student-only, seed0, 16 env
goal:
  0 / 16
max-stage distribution:
  stage0: 8
  stage1: 4
  stage2: 4
mean max stage:
  0.75
mean reward:
  -85.1707735657692
```

The v19 mean max stage is 33% lower (`0.50` versus `0.75`) and stage0 failures increased from `8/16` to `12/16`. However, v19 still had a deeper two-case tail at stage3. The degradation is therefore broad early failure, not complete removal of every deeper trajectory.

## 4. Render evidence must not replace formal evaluation

The v16 formal evaluation was also `0/16 goal`, but a later render replay produced one env13 `stage5 complete` outcome. Its metadata explicitly records replay nondeterminism and a successful semantic replay:

```text
logs_eval/a2_piper_student_v16_cb_best_env13_sixcam_gpu7-20260729_185257/selected_env13_render_metadata.json
```

The v19 formal env13 stage3 case was replayed three times. All three replays drifted to stage1 with rewards:

```text
-251.338623046875
-252.15257263183594
-254.18408203125
```

Only the canonical best trial01 was retained:

```text
logs_eval/cb2h_v19_student_step10000_env13_render_trial01_gpu7-20260802_041312/selected_render_metadata.json
```

The ZIP includes the retained six-camera videos for both the v16 lucky stage5 replay and the v19 best retained replay. Treat them as qualitative evidence only; formal multi-case metrics remain authoritative.

## 5. Training-budget comparison

Both v16 and v19 used:

```text
num_envs = 64
num_steps_per_env = 8
num_mini_batches = 4
num_learning_epochs = 1
actor_learning_rate = 1e-4
enforce_teacher_rollout = true
ratio_teacher_rollout = 1.0
image augmentation for BC = disabled
```

Budget comparison:

| Run | Iterations | Env-steps | Approx. optimizer minibatches | Checkpoint size |
| --- | ---: | ---: | ---: | ---: |
| v16 C-B | 5,000 | 2.56M | 20k | 155,668,923 bytes |
| v19 C-B2H | 10,000 | 5.12M | 40k | 294,256,699 bytes |

This falsifies the simple claim that v19 received less raw training than v16. It does not prove 10k is sufficient: v19 has a much larger checkpoint and a harder optimization problem. The correct discriminator is a fixed-case checkpoint sweep, not another unmeasured long run.

Intermediate v19 checkpoints exist locally every 500 iterations from step500 through step10000. They are intentionally excluded from the ZIP to avoid roughly 5.9GB of duplicate weights. Recommended sweep points are step1000/2500/5000/7500/10000.

## 6. Leading mechanism: Teacher-only rollout distribution shift

The common distillation config is:

```text
enforce_teacher_rollout: true
ratio_teacher_rollout: 1.0
```

The Student never controls the training trajectory. It learns image-to-action imitation only on states visited by the Teacher. During Student-only evaluation, a small visual/action error changes the next robot pose and next camera image; subsequent observations leave the Teacher state distribution and errors compound. This is standard behavior-cloning covariate shift.

More Teacher-only iterations increase samples from the same controlled distribution. They do not directly teach recovery from Student-induced errors. The C-B2H design itself proposed a 100–200-batch Teacher-only pilot followed by separately adjudicated mixed rollout ratios `0.75`, `0.50`, and `0.25`; that controlled mixed-rollout program was not executed.

## 7. Fusion architecture and implementation risks

Read in the remote repository:

```text
scriptsFORhuman/C-B2H_Dual-Raw_Shared-Encoder_Feature_Fusion.md
gr00t/rl/trl/modules/vision_actor_critic_modules_triview_recurrent.py
gr00t/rl/agents/modules/modules.py
gr00t/rl/config/exp/wbmanip/door_open_a2_base_v19_cb2h_dualraw_dagger-lstm.yaml
```

### Verified design/implementation deviation

The design requires:

```text
left/right -> pack [2M,3,384,216] -> one shared ResNet18 forward -> [2M,128]
```

The implementation instead performs two sequential calls:

```python
f_left = self.d435i_vision_module(left)
f_right = self.d435i_vision_module(right)
```

The ResNet is converted to `SyncBatchNorm`. Sequential left/right calls therefore use/update batch and running statistics separately, and the later right call can introduce order-dependent running-stat bias. This is a concrete deviation worth testing. It is not yet proven to be the sole causal regression.

### Representation risks

- Each view is globally compressed to 128D before fusion.
- Left/right use a freshness-weighted arithmetic base plus a residual MLP over `[left, right, abs(left-right)]`.
- The OEM Head branch is injected with fixed `head_base_weight=0.25` plus a single scalar gate.
- The final tri-view representation is still one 128D vector before the recurrent policy.
- The two D435i optical axes have only about `2.5°` nominal far-field overlap; there is no spatial-token alignment, cross-attention, stereo geometry, or learned correspondence.

This could average away asymmetric manipulation cues, discard spatial correspondence, or over/under-use the Head context view.

### Missing required adjudication

The design requires B0–B5 ablations. The primary comparison is:

```text
B0: original v16 C-B spatial composite
B1: dual D435i only with shared encoder
B2: current dual D435i + OEM Head hierarchical fusion
```

It also requires:

```text
per-view feature norms
per-view/shared encoder gradients
manipulation/context fusion gradients
action difference when Head is masked
view freshness coefficients
collision/contact and base-heading metrics
```

These diagnostics were not recorded in the 10k run, so the Head/fusion utilization claim remains unverified.

The design explicitly excludes Stage5 handle visibility from its scope. It therefore cannot be cited as a complete Stage5 solution.

## 8. Teacher ceiling evidence

The final Teacher-controlled training window did not look obviously worse than the v16 window:

```text
v16 final window:
  average_stage_reached = 4.5000
  average_goal_reached  = 0.8281

v19 final window:
  average_stage_reached = 4.6406
  average_goal_reached  = 0.8594
```

These are training-window metrics under Teacher-controlled rollout, not a sealed apples-to-apples formal Teacher evaluation. They make “v19 Teacher is simply worse” a low-confidence explanation, but a matched fixed-case Teacher-only eval is still required.

## 9. Current evidence-ranked diagnosis

| Rank | Candidate cause | Confidence | Reason |
| ---: | --- | --- | --- |
| 1 | 100% Teacher rollout / closed-loop covariate shift | High | Directly verified config; mechanism matches broad stage0/1 collapse. |
| 2 | Tri-view fusion or implementation deviation | Medium-high | Missing ablations/utilization; sequential shared SyncBN deviation is concrete. |
| 3 | Larger v19 model undertrained at 10k | Medium | Checkpoint is about 1.89× v16, but v19 already had 2× data and updates. |
| 4 | 64 env itself | Low-medium | v16 also used 64 env; 128 changes both parallel diversity and total data unless controlled. |
| 5 | Weaker v19 Teacher ceiling | Low/unresolved | Training-window Teacher metrics do not support obvious degradation; formal matched Teacher eval missing. |
| 6 | Render nondeterminism | High for explaining one lucky case only | Explains v16 stage5 replay and v19 replay drift, not the formal distribution gap. |

## 10. Recommended decision sequence

1. **No-retraining checkpoint sweep:** evaluate v19 step1000/2500/5000/7500/10000 on identical fixed cases and at least three seeds. If performance is still rising at 10k, longer training is supported; plateau/decline points elsewhere.
2. **Matched Teacher-only eval:** same fixed cases under v19 Teacher to establish the reachable ceiling and separate runtime/task differences.
3. **Open-loop imitation diagnostics:** on sealed Teacher trajectories compute per-action-dimension MSE, stage-stratified MSE, temporal drift, and Student/Teacher disagreement, especially for stage0→1.
4. **Fusion diagnostics:** packed-vs-sequential shared encoder/BN, Head mask action delta, feature/gradient norms, and view-swap sensitivity.
5. **Short controlled ablations:** B0/B1/B2 under the same Teacher, seed set, case set, and 200–500-iteration budget. Do not spend another 10k before this comparison.
6. **Mixed rollout only after selecting the encoding:** adjudicated `1.0 -> 0.75 -> 0.50 -> 0.25` runs, with fail-fast separation of each run identity.
7. **Only then decide scaling:** longer iterations and/or 128 env require a measured benefit and enough GPU memory. If 128 admission fails, block and request additional GPU resources rather than silently changing env, resolution, or device fallback.

## 11. ZIP layout

```text
README_FIRST.md                         # copy of this diagnosis
MANIFEST.sha256                         # checksum for every bundled evidence file
FILE_INVENTORY.tsv                      # byte size and path
repo/                                   # repository-relative tracked and ignored evidence
  scriptsFORhuman/
  memory/a2-piper/phase2-student-distillation-a2-piper/
  logs_rl/cb2h_v19_runtime/...
  logs_rl/cb2h_v19_distill/...
  logs_eval/cb2h_v19_student_step10000_.../
  logs_eval/cb2h_v19_student_step10000_env13_render_trial01_.../
  logs_rl/a2_piper_student_distillation_v16_B_.../  # selected config/log only
  logs_eval/a2_piper_student_v16_.../                 # formal/render comparison
external_teacher_input/
  model_step_002000.pt
  config.yaml
```

Verify the ZIP with `sha256sum -c MANIFEST.sha256` from the extracted bundle root before using any result.

## 12. Constraints for the next plan

- Keep IsaacLab code fail-fast; no unnecessary guards, silent fallback, automatic env/resolution reduction, CPU fallback, or error swallowing.
- Use IsaacLab high-level APIs where applicable.
- Do not call static source inspection a runtime PASS.
- Do not call checkpoint completion or eval protocol PASS an open-door policy-quality PASS.
- Treat formal multi-case evaluation as authoritative; use render videos as qualitative evidence.
- Preserve the exact Teacher/runtime/case/seed identity in every comparison.
- The next recommendation should specify acceptance criteria, stopping conditions, resource assumptions, and which result would falsify each hypothesis.
