# C002 implementation delta

C002 retains C001 production source, configuration and assets unchanged. One direct byte comparison of all 320 frozen C001 inputs found no differences. The layered snapshot is delta_input_snapshot/SNAPSHOT.json plus its referenced C001 snapshot. The only new executable is the directed Stage5 reward probe. No Git commit or push was made.

Planner D056 accepted the remaining baseline items in their stated scope; those original evidence files and limitations are retained through ../C001/CANDIDATE.json. This successor supplies only the missing new Stage5 runtime evidence and D056 prospective output-path normalization.

## Actual Stage5 evidence

D057–D059 authorized the 2-env GPU0 probe. After one real natural-reset step, it writes explicit native root pose and stage inputs, derives RPY from actual simulator quaternion using the production conversion, then calls the actual registered _compute_reward and captures the original component hook's raw/scaled values. These instantaneous fixtures are not policy success, natural stage advancement or dynamics stability.

Both environments produced: aligned Stage5 zero; yaw .35rad raw heading .12249994 and scaled −.00979999; roll .10/pitch .08 raw .0164, old roll/pitch −.000656 plus new upright −.002624 = −.00328. Same pose Stage4 retains old −.000656 and zeros both new Stage5 terms. Registered coefficients are −.04/−.08/−.16 at dt=.02, corresponding to −2/−4/−8; all three terms are outside the actual K list (observed K=1). Raw state/goal/rpy/stage/config/readout are preserved in stage5_reward_a3 and stage5_a3_readout.json.

The first two attempts failed explicitly in the probe: missing environment output-directory forwarding, then duplicate full observation-callback lifecycle update. Both original logs and failure readouts remain. The corrected probe forwards output paths and derives RPY directly without replaying contact streak updates. Production code was not modified to make the fixture run.

## Formal proposal

formal_training_proposal.json binds seed291,4096env,6000batches,save100,scratch to physicalGPU0; output logs_rl/a2_piper_full_stage_a2_base/base_v29/push_baseline_C002_seed291 and its runtime_capture. Requested48h ceiling;39.34h is only a one-batch extrapolation. formal_evaluation_proposal.json binds final step6000 checkpoint and64 first natural episodes to logs_eval/base_v29/push_baseline_C002_seed291/natural_final, requested20min. Both remain proposals requiring planner TRAIN_APPROVED. Existing actual4096 resolved config and selectedassets remain the C001 evidence base; exact formal overrides are explicit in these commands.

No active v29 GPU run remains. Planner acceptance and formal training/evaluation delivery are outstanding.
