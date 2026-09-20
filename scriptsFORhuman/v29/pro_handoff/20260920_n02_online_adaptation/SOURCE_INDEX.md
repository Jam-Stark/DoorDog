# N02 source/evidence 导航

source ZIP与N01包复用同一完整C002版本，文件保持repo相对路径；332文件版本记录见manifest中的来源与 `BASELINE_SOURCE_BINDING.json`。不重新冻结/修改运行中的训练源码。

| 议题 | 实际source/config定位 |
|---|---|
| Teacher/Student观察差异 | `gr00t/rl/config/obs/wbmanip/door_open_a2_base.yaml`；`door_open_a2_base_dagger.yaml:7/21/39` |
| 质量/几何oracle、门角、指力 | `gr00t/rl/envs/door/door_open_a2_base.py:28498` hand_force；`:28520` privileged_door_info；`:28535` door_dof_pos |
| C002门域 | `gr00t/rl/isaac_utils/playground/env_rand/door_v29_parameters.py`；`door.py`；`gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py` |
| B05几何与目标/接触语义 | `gr00t/rl/isaac_utils/playground/env_rand/handle_v29.py`；`door.py`；`door_open_a2_base.py` 的gripper frame与contact helpers |
| 接触/有效握持区分 | `door_open_a2_base.py:18558`、`:18636`、`:18747`；control streak配置在实际training config |
| high-level动作和base姿态通道 | `gr00t/rl/envs/base_task/a2_base.py:1174`及`:1193`命令缩放/映射；`:1303`物理命令读回 |
| 释放后收入与回臂 | `door_open_a2_base.py:2214` hold-income mask；`:15964/15977`回臂；`:16420/16452`接近handle |
| 回柄与开门进展 | `door_open_a2_base.py:17591`、`:17600`；stage条件29725起 |
| 姿态和旧fling功能 | `door_open_a2_base.py:17847` controlled_fling（C002 scale0）；`:17901` roll/pitch；`:17926` Stage5 upright |
| Teacher循环网络 | `gr00t/rl/trl/modules/actor_critic_modules_recurrent.py`；`memory.py`；实际config actor/critic两层256 |
| Student视觉与历史 | `vision_actor_critic_modules_recurrent.py`；`gr00t/rl/envs/legged_base_task/legged_robot_base.py:2440` RGB；`a2_base.py:1497`独立下层历史 |
| Student真实采样/监督 | `gr00t/rl/trl/trainer/distill_trainer_a2_base_api.py:340/391/417/438`；generic `distill_trainer.py:264/340/482`；`data_utils.py` |
| 默认Teacher执行比例 | `gr00t/rl/config/exp/wbmanip/door_open_a2_base_dagger-lstm.yaml:28/64` |
| 旧shadow特征与人口 | historical/reference包 `scriptsFORhuman/v27/v27_shadow_estimator.py` 的FEATURES/collect/run及endpoint_result |

实际C002训练config、D056/D060接受记录、D061/D064有限运行证据放在brief/evidence ZIP。B05 atlas/native/readout属于已完成的有限候选证明；不是N02新实验。未打包的绝对本机路径不能被云端声称已读。

N02重点源码位置已在本次只读查看；共用C002 source包使用上一次直接冻结输入及同tag补充依赖，无新的代码/compile/GPU检查。旧plan/candidate状态字段与当前接受结论的区别见LOCAL_FACTS。
