# 本次当前源码导航

函数名优先于历史行号；下列行号来自本次发布准备时的实际文件。完整相关源文件随source包提供。

| 文件 | 入口 | 行 |
|---|---|---|
| `gr00t/rl/envs/door/door_open_a2_base.py` | `_parse_a2_v27_recovery_config` | 6942 |
| `gr00t/rl/envs/door/door_open_a2_base.py` | `_update_a2_v27_recovery_state` | 14365 |
| `gr00t/rl/envs/door/door_open_a2_base.py` | `_capture_a2_v27_recovery_bank` | 14421 |
| `gr00t/rl/envs/door/door_open_a2_base.py` | `_restore_a2_v27_recovery_bank` | 14490 |
| `gr00t/rl/envs/door/door_open_a2_base.py` | `_stage_1_reward_condition` | 29735 |
| `gr00t/rl/envs/door/door_open_a2_base.py` | `_stage_2_to_3_advance_condition` | 29820 |
| `gr00t/rl/envs/door/door_open_a2_base.py` | `_stage_3_to_4_advance_condition` | 29841 |
| `gr00t/rl/envs/door/door_open_a2_base.py` | `_stage_4_reward_condition` | 29866 |
| `gr00t/rl/envs/door/door_open_a2_base.py` | `_reward_a2_stage3_unlatch_hold` | 17010 |
| `gr00t/rl/envs/base_task/staged_task_base.py` | `_post_compute_observations_callback` | 164 |
| `gr00t/rl/envs/base_task/staged_task_base.py` | `set_to_stage` | 399 |
| `gr00t/rl/envs/base_task/staged_task_base.py` | `_register_task_state_to_track` | 486 |
| `gr00t/rl/envs/base_task/staged_task_base.py` | `_register_buffer_to_track` | 529 |
| `gr00t/rl/envs/legged_base_task/legged_robot_base.py` | `_reset_buffers_callback` | 1575 |
| `gr00t/rl/envs/legged_base_task/legged_robot_base.py` | `_physics_step` | 1114 |
| `gr00t/rl/trl/modules/memory.py` | `reset` | 93 |

Student采集/动作选择完整段见`distill_trainer_a2_base_api.py`约256–431行；读取其父trainer与recurrent模块理解done和rollout边界。
当前C002覆盖为`gr00t/rl/config/ablation/wbmanip/base_v29_common.yaml`，固定resolved config另见证据包。
门域与几何见`door_v29_parameters.py`、`handle_v29.py`、`door.py`及`scenario_cfg/isaacsim.py`；当前v29 robot/URDF/mesh随包提供。
代码目录仍保留旧版本支持路径，它们不代表本次已启用。以当前显式配置与LOCAL_SOURCE_FACTS的证据边界为准。
