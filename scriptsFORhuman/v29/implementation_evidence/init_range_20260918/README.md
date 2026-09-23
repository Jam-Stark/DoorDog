# v29 B07自然起点扩域：实施证据

2026-09-18 11:48 HKT。状态：STATIC_PASS / CPU_SAMPLER_PASS；Owner确认与范围见V29-D008–D010。

- [resolved_config.yaml](resolved_config.yaml)：使用真实入口`python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v29_baseline --cfg job --resolve`解析，只输出配置，没有进入训练/仿真。
- [implementation_readout.json](implementation_readout.json)：对当前source中新增yaw分支直接执行CPU采样，覆盖当前几何域的两侧/距离/横移边界组合；1218个样本均在把手bearing±10°和门法向±35°交集中。source通过AST解析；没有新增测试套件。
- USD闭门grasp缓存沿用项目`door.py::_update_joint_transform`使用的`UsdGeom.XformCache.ComputeRelativeTransform`路径；该API和reset生命周期已检查，本轮未进行完整simulator运行。
- 时间配置来自side window已完成改动，本轮解析确认30s与`[525,150,150,150,150,300]`、dt=.02s和结转逻辑。旧smoke不能用作本次新范围的运行验证。

Owner转述的三相机静态网格及约10%边缘余量作为既有设计依据记录，本轮没有重新生成其图像/网格证据。没有新增Student输入、改动Stage0远距目标速度或启动训练。B07 PASS表示范围决定与实施完成，不表示新起点定位或任务成功率已经验证。
