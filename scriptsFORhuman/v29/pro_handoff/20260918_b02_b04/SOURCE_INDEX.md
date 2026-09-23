# 定向source阅读索引

包内项目文件保留repo相对路径。函数名优先于可能漂移的行号；不用通读无关版本路径。

| 文件/位置 | 关联问题 |
|---|---|
| `gr00t/rl/isaac_utils/playground/env_rand/door.py::DoorSpawnerCfg`、handle/hinge/latch构建（约517–651行） | handle45°、hinge150°、raw USD drive参数、cone/prismatic/mimic、自碰撞开关、grasp目标 |
| `gr00t/rl/isaac_utils/playground/utils/usd_utils.py::add_mass/add_collider` | 当前质量与碰撞写入方式 |
| `gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py::get_TaskObjCfgDict_for_door_config`、`door_spawner_cfg`、door actuator | 当前v29 selector、左右手性、build_latch、三joint及drive配置 |
| `gr00t/rl/envs/door/door_open_a2_base.py::_reset_door_states/reset_envs_idx/_reset_object_states_callback/_apply_force_in_physics_step` | 三DOF reset、自然/分阶段恢复、物理步前更新 |
| 同文件 `a2_grasp_gated_door_reward_components`、creation初始化/更新、hard-limit getter | 活跃0.6rad尺度、45°截断和telemetry消费者 |
| `gr00t/rl/envs/door/a2_v26_3_creation.py::a2_v26_3_update_handle_creation` | 活跃handle进度reward固定45°常量；不能只改common中的一个字段 |
| `door_open_a2_base.py::_stage_3_to_4_advance_condition/_stage_4_to_5_advance_condition` | 阶段门槛与物理解锁/最大开角的区分 |
| 同文件 `a2_update_stage4_release_and_root_latches/_reward_push_door_hinge/_get_a2_stage34_hold_income_mask/_get_a2_door_income_hold_mask` | release事件、位置/速度收入与继续持握 |
| 同文件 `_get_obs_privileged_door_info/_get_obs_door_dof_pos/_get_obs_hand_force`及`config/obs/wbmanip/door_open_a2_base.yaml` | Teacher真值、门角/反馈、未提供的锁态/门角速度 |
| `gr00t/rl/envs/base_task/staged_task_base.py`、`legged_base_task/legged_robot_base.py` | bank直接恢复door root/joint/buffer，物理simulate之前回调 |
| `gr00t/rl/simulator/isaacsim/isaacsim.py::set_task_dof_state_tensor/get_task_dof_pos/apply_torques_at_task_dof` | tensor写入边界和door topology |
| `gr00t/rl/config/ablation/wbmanip/base_v29_common.yaml`、baseline/eval overlay、env/rewards/exp YAML及当前resolved | 实际活跃配置优先于历史默认reward值 |

外部依赖事实在包内`dependency_evidence/ISAACLAB_LIMIT_API.md`，来自本机IsaacLab（extension version0.54.4）的完整setter节选与原路径/行号；不是第三方文档替代当前source。

官方核对入口：

- [IsaacLab Articulation API](https://isaac-sim.github.io/IsaacLab/main/source/api/lab/isaaclab.assets.html)
- [PhysX articulation limits：lower必须小于upper](https://nvidia-omniverse.github.io/PhysX/physx/5.8.0/_api_build/structPxArticulationLimit.html)
- [USD DriveAPI单位与力矩上限](https://docs.omniverse.nvidia.com/kit/docs/omni_physics/latest/dev_guide/schemas/usdphysics.html)
- [PDQ GT产品操作角](https://www.pdqlocks.com/products/gt-cylindrical-lock)

上一份Pro参考：`scriptsFORhuman/pro_reviews/v29/20260918_102906__baseline_and_v28_pro_review/original/`下FULL_REVIEW、SOURCES、参数CSV、PRELIMINARY_JUDGMENTS及release语义附件；本次只读B02/B04相关段落。原文是历史资料，不覆盖最新Owner范围。
