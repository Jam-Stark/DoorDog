# Owner repair request: observed G0 robot alias defect

Status: proposed, NOT APPLIED. The active materializer remains the failed version so the failed run is reproducible. Contact repair1 and repair2 have consumed the plan §8 two-repairs-per-cell allowance; a third automatic repair was not made.

Observed chain:
- Original `gr00t/rl/config/env/legged_base.yaml:11`: `robot: ${robot}`.
- `config_materialize.py` writes root and env robot as independent OmegaConf nodes after flattening. Their initial algo_obs_dim_dict values are actor0/critic0.
- `gr00t/rl/utils/helpers.py:82` computes actor133/critic138 but writes only `config.robot.algo_obs_dim_dict`.
- `gr00t/rl/train_agent_trl.py:472` constructs the env with the stale env robot node.
- `gr00t/rl/trl/modules/actor_critic_modules_recurrent.py` reads the env robot dimension; isaac.log explicitly shows RunningMeanStd(0) and LSTM(0,256,num_layers=2).
- Moving this zero-input LSTM to CUDA triggers `_cudnn_rnn_flatten_weight` / CUDNN_STATUS_BAD_PARAM, before any learning batch.

Proposed minimal repair in OWNER_PROPOSED_FIX_NOT_APPLIED.patch: set `env["robot"] = "${robot}"`, restoring the established dynamic reference. No source model, observation contract, physics, event, reward, GPU library or fallback changes are proposed.

Requested Owner decision: allow one additional G0 materializer repair and a fresh attempt of the already authorized256env×5batch smoke, then its checkpoint natural evaluation; continue original PA plan only if G0 completes. Existing0 completed PPO batches do not consume extra training batches. No broader alias audit/test suite or contract changes are requested. This patch has not been executed, so successful runtime resolution remains to be demonstrated.
