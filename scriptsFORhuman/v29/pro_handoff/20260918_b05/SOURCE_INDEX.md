# 本次材料与source路径

包内文件保留repo相对路径。依据优先级：当前Owner D026范围→当前选定source/config→标称设计计算→厂家资料→旧Pro意见。仅有INSPECTED/静态设计证据，没有多族导入、物理、抓取或泛化结果。

| 位置 | 用途 |
|---|---|
| `scriptsFORhuman/v29/a2_piper_base_v29_b05_handle_design.md` | 已批准七族、精确标称参数、I/J/G及姿态；尺寸和权重的证据边界 |
| `scriptsFORhuman/v29/b05_designs_20260918/families.json`、`geometry_readout.json`、PNG/SVG与绘图脚本 | 中心线、截面、自由段与G的同源设计数据；不是USD资产 |
| `scriptsFORhuman/v29/a2_piper_base_v29_baseline_plan.md` §7、TODO与D026 | 七族全部纳入；规划结案与代码实施分开 |
| `gr00t/rl/isaac_utils/playground/env_rand/door.py`，尺寸约305行、handle构建、grasp约635行 | 原圆杆/回钩、左右手性、完整axle、目标位置及FixedJoint |
| `gr00t/rl/isaac_utils/playground/utils/usd_utils.py` | capsule/质量/collider与变换写入 |
| `gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py` | 当前v29实际selector、spawner cfg、door actuator |
| `gr00t/rl/envs/door/door_open_a2_base.py::_compute_grasp_target`（约28550行）、`scene_creation_callback`（约29945行）、LEFT offset处理（约4935行） | 当前目标consumer、固定旋转、pregrasp/左右处理及contact设置；按函数名定位优先 |
| 同文件`_get_obs_privileged_door_info`与obs YAML | Teacher几何真值及观察接线，不能当Student视觉能力 |
| `gr00t/rl/config/env/door_open_a2_base.yaml`与robot/v29 YAML | TCP偏置与当前指关节配置；只审本题相关字段 |
| `gr00t/rl/data/robots/a2_piper_v29_merged_20260917/a2_piper.urdf`及`meshes/piper/{link7,link8,gripper_base}.STL` | 原始指/夹爪几何和关节。仅打包三件相关mesh，不是完整机器人资产，不能据此运行整机仿真 |
| `dependency_evidence/frame_transformer_cfg.py` | 当前本机IsaacLab完整FrameTransformerCfg/OffsetCfg源文件，保留原路径来源；用于核对offset语义 |
| `scriptsFORhuman/pro_reviews/v29/20260918_102906__baseline_and_v28_pro_review/original/`下HANDLE_FAMILIES、SOURCES与REAL_WORLD_PARAMETER_TABLES | 旧形状建议与产品锚点；工程候选不能倒签为现实测量或Owner批准 |

本次不附checkpoint、训练日志或策略视频；旧one-batch不涉及七族，不能用作多族可学性证据。父review分支可能保留其他阶段资料，不属于本次审阅任务；以本次manifest为材料选择边界。

官方依赖入口：[OpenUSD Capsule](https://openusd.org/release/api/class_usd_geom_capsule.html)、[IsaacLab FrameTransformerCfg](https://isaac-sim.github.io/IsaacLab/main/_modules/isaaclab/sensors/frame_transformer/frame_transformer_cfg.html)。依赖快照来自本机 `/home/baoquanc/workspace/IsaacLab/source/isaaclab/isaaclab/sensors/frame_transformer/frame_transformer_cfg.py`，云端最新文档与本机差异应明确标记。
