# Source / evidence 导航

以下路径在source ZIP中保持repo相对路径。行号用于当前交付版本的定位，不要求整文件顺序阅读；源文件优先于本表摘要。

| 问题 | 文件与定位 |
|---|---|
| C002完整底座与B05开关/时间/机器人 | `gr00t/rl/config/ablation/wbmanip/base_v29_common.yaml`；`base_v29_baseline.yaml`；实际训练config在evidence ZIP |
| 门域/质量/closer/friction | `gr00t/rl/isaac_utils/playground/env_rand/door_v29_parameters.py`；`door.py`；`gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py` |
| B05几何与G | `gr00t/rl/isaac_utils/playground/env_rand/handle_v29.py`；`door.py`；`door_open_a2_base.py::_init_scene`与frame consumer（约30025起） |
| stage常量 | `gr00t/rl/envs/door/door_open_a2_base.py:5406` |
| 前向stage/时间/高水位/reward | `gr00t/rl/envs/base_task/staged_task_base.py:166`、`:309`；snapshot/reset约556–711 |
| 现有stage进入条件 | `door_open_a2_base.py:29725`起六个stage方法；pregrasp条件18701，grasp完成条件18747 |
| 旧恢复是否启用 | `door_open_a2_base.py:6943` `_parse_a2_v27_recovery_config`；实际C002 config中不含此组字段 |
| 旧扰动、失抓与退Stage2 | `door_open_a2_base.py:14371` `_a2_v27_prepare_actor_state`；`:14415` `_update_a2_v27_recovery_state` |
| 旧失败状态bank与reset | `door_open_a2_base.py:14471` capture、`:14540` restore、`:29067` reset |
| 旧恢复高水位收入屏蔽 | `door_open_a2_base.py:17393` `_after_reward_components` |
| Teacher观测 | `gr00t/rl/config/obs/wbmanip/door_open_a2_base.yaml`；env里`_get_obs_hand_force`约28498、`_get_obs_privileged_door_info`约28520 |
| Student与Teacher不同view | `gr00t/rl/config/obs/wbmanip/door_open_a2_base_dagger.yaml:7`、`:21`、`:39` |
| 默认Teacher rollout=1、手动课程、required artifacts | `gr00t/rl/config/exp/wbmanip/door_open_a2_base_dagger-lstm.yaml:28`、`:35`、`:64` |
| Teacher查询、Student forward、环境动作选择 | `gr00t/rl/trl/trainer/distill_trainer_a2_base_api.py:340`、`:349`、`:391` |
| Teacher done reset / rollout边界 | 同文件`:417`、`:426` |
| 实际BC目标 | 同文件`:438`；generic `gr00t/rl/trl/trainer/distill_trainer.py:482`，不是A2文件的482行 |
| 当前rollout数据和minibatch | `distill_trainer.py:264`、`:340`；`gr00t/rl/agents/modules/data_utils.py:27`、`:119` |
| recurrent memory与actor lifecycle | `gr00t/rl/trl/modules/actor_critic_modules_recurrent.py`；`vision_actor_critic_modules_recurrent.py`；`actor_critic_modules.py:337`；`memory.py:93` |
| PPO父循环与A2动作拼接 | `gr00t/rl/trl/trainer/ppo_trainer.py:1453`；`ppo_trainer_a2_base_api.py` |
| Student RGB producer | `gr00t/rl/envs/legged_base_task/legged_robot_base.py:2440`起 |
| 冻结腿策略独立历史 | `gr00t/rl/envs/base_task/a2_base.py:394`、`:538`、`:1497` |
| 训练/eval入口及loader | `gr00t/rl/train_agent_trl.py`；`gr00t/rl/eval_agent_trl.py`；`ppo_trainer_a2_base_api.py` |

## 证据阅读顺序

1. `LOCAL_FACTS.md`与实际C002训练config：当前已实现内容和未证明的结论。
2. `evidence/C002_acceptance/D056_C001_PER_ITEM_ACCEPTANCE.md`与`D060_C002_ACCEPTANCE_AND_TRAIN_APPROVAL.json`：候选实现验收及其范围。
3. `evidence/C002_runtime/D061_INITIALIZATION_AND_LOSS_OBSERVABILITY.json`、`D064_BATCH3000_MILESTONE_REVIEW.json`与相应保存console/readout：A组已审阅运行事实，不是新轮询。
4. 有需要才读B05接触/几何、native physics、Stage1和一次自然full-loader证据；文件范围由manifest明确。
5. 完成初步独立设计后，读历史novelty ZIP中的旧提案、v27 pilot和v28 closure。旧结论属于对应旧实验，不能替代本次设计。

## 版本解释

321份冻结文件直接来自C001最终快照和C002增量快照，不从当前GPU1消融目录取源码。补充stage/DAgger/actor/camera依赖与同一baseline tag内容相同，详见`SUPPLEMENTAL_SOURCE_BINDING.json`。完整候选输入清单与打包清单使用文件路径、大小、tag和提交主题/时间标识，不生成哈希清单。

既有source可能含历史配置字段名或校验代码；原样携带是为准确阅读，不是要求在N01新增此类机制。云端不具备本机IsaacLab、GPU、过程状态或硬件证据，不能把静态建议升级为本地实验PASS。
