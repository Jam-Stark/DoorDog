# N01：合力方向与 v28 实际失抓 quick test

2026-09-21 HKT，Codex N01 planner按Owner本轮独立诊断授权执行。当前状态：两轮剂量诊断共32个首episode及独立8 env视频运行均完成，GPU2上的本任务进程和等待已结束；GPU3未启动进程。正式N01方法与训练尚未启动。

## 当前结论

退出与沿柄力可以同时施加。采用`F=A(sinθ·X_G−cosθ·Z_G)`、θ∈[−90°,90°]，A表示总力幅值；85 N、45°对应两个约60.1 N分量。三条轴向射线由此扩为退出一侧的连续方向面，仍排除+Z与±Y。方向在触发时转到世界系，这次短脉冲内保持恒定。

v28强档已实际造成抓持破坏：11个到窗的非零案例中，8个在短观察窗内出现持续双指零接触与相对滑出，另外3个为单指/挤压约束失效。各方向幅值减半后，11个到窗非零案例中持续脱离0个、较宽约束失效1个。两轮各4个0 N对照在同一窗口内均无两类事件。这个诊断支持“有限掌部外力可以造成失抓，当前强档无需继续增大”；不证明N01恢复学习、Student传递或完整B05域的效果。

## 输入、施力与读数

- checkpoint：[v28 Wave A S282 step6000](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/attempts/wave_a_s282/attempt1/model_step_006000.pt)，使用其相邻config与自然起点评估覆盖。该模型此前有成熟LEFT握持/通行记录，本轮未重新训练。
- source：从N01未变的初始HEAD导出v28 closure原生`gr00t`到`.ai/runtime/n01_force_probe/v28_source/`；来源提交主题为“Close v28 qualification and reuse existing render evidence”、日期2026-09-17。实际module路径与Hydra config显式绑定该快照。场景配置的文件导入改为相对快照位置，避免意外从当前cwd导入v29场景。
- 域：LEFT、seed2921、16 env，各自第一个自然episode。保留v28原始动作/阶段行为；无强制开爪、姿态恢复、q/qdot写入或额外policy覆盖。它不是当前v29 C002+B05域，也不是N01未来stage-blind执行器。
- 触发：当前双指接触、相向挤压与足够挤压、几何接近、闭合意图，连续5 control tick；处于Stage2/3/4且正常释放未开始。只在首次资格后安排一次脉冲，未到窗者记未施力。
- 原生G核对：旧v28 FrameTransformer旋转为(0.5,0.5,0.5,0.5)，body中的pregrasp(-0.10,0,0)对应有效G的−Z，X为沿柄方向；没有将v29 identity旋转直接套到v28。
- 力接点：[quick_force_probe.py](../../v29/n01/quick_force_probe.py)在真实physics hook中使用`instantaneous_wrench_composer.add_forces_and_torques`，body name=`arm_body6_to_gripper`、`positions=None`、world force，每0.005s重新添加。原策略继续执行，撤力后状态连续。
- 时长：固定0.35s，70个physics step；50Hz control、decimation4。到窗的0 N对照同样走70次定时零请求，但不计非零外力暴露。
- 比较窗口：两轮统一为t0至t0+0.55s，即0.35s脉冲＋0.20s短响应；该描述性窗口在看到首轮后固定用于减半比较，不冒称预注册统计终点。保留每个事件的实际首次时间。
- “持续脱离”操作读数：双指handle接触力同时为零、TCP/G相对位移至少2cm，连续至少3个control读数，同时查看正常释放状态。较宽的“约束失效”允许单指/相向或挤压破坏，并要求相对位移≥2cm或实际q变化≥5mm；两者分别报告。几何阈值不是B05通用脱离距离。

## 剂量结果

| 方向 | 强档总力 | 强档到窗/分配 | 强档持续脱离/到窗 | 减半总力 | 减半持续脱离/到窗 |
|---|---:|---:|---:|---:|---|
| 0°退出 | 100 N | 4/4 | 3/4 | 50 N | 0/4 |
| +90°沿柄 | 60 N | 2/2 | 2/2 | 30 N | 0/2 |
| −90°沿柄 | 60 N | 1/2 | 0/1 | 30 N | 0/1 |
| +45°斜向 | 85 N | 2/2 | 2/2 | 42.5 N | 0/2 |
| −45°斜向 | 85 N | 2/2 | 1/2 | 42.5 N | 0/2 |
| 0 N对照 | 0 N | 4/4 | 0/4 | 0 N | 0/4 |

两轮分别都是非零11/12到窗、0 N为4/4；所有到窗者均完成连续70次请求，世界向量在脉冲内保持恒定，模长仅有浮点舍入误差。env7均没有满足资格，0次请求，不能算施力后保持。强档与减半运行分别耗时230.7s、301.3s，包含初始化与全部首episode；没有额外训练。

减半轮唯一的宽口径约束失效为−90°/30 N env6，于t0+0.18s确认；短窗最大相对位移约1.69cm、q变化约9.16mm，未达到持续双指脱离。其余10个非零案例没有短窗内确认的宽口径loss，但不能据此宣称整个脉冲始终理想稳定或所有姿态都不会失抓。已形成两档区间，本轮不继续减半或扩大力度。

强档env0的退出脉冲：触发时实际gripper q约(+6.80,−12.78)mm，双指handle接触模长约8.71/16.13 N；首个完整撤力后的control读数q约(+0.31,−0.14)mm，接触0/0 N，相对位置从(17.98,5.13,5.83)mm变为(−32.27,−30.83,−89.97)mm，相对滑出约11.4cm。较宽loss于t0+0.28s确认，此时release gate=false；正常释放读数要到约t0+5.14s。此例有明确物理脱离证据。

外力也传递到base与门：该例脉冲前后base移动约4.3cm、门铰链角变化约0.106rad。其他强档案例短期相对位移超过20cm，因此“能失抓”不等于“全都处在L0/L1局部范围”。减小剂量的目的正是观察较温和的保持/局部滑脱分布。

整episode累计loss latch不能作为脉冲失抓率：首轮0 N案例在约t0+2.3–2.8s的后续自然交互也会满足宽口径。主表只使用共同短窗；小样本与同seed不代表匹配物理状态的因果估计。

−90°（−X_G）在两档中都没有持续完整脱离，不能把其宽口径loss当作这个方向已经标定成功。独立视频运行的0 N env6也出现短窗内宽口径loss、没有完整脱离，进一步表明该指标包含自然约束变化；相同env编号本身不证明相同物理状态。该方向保留为保持/滑移样本，后续B05实际结果再决定是否需要调整，不要求每个方向都制造loss。

## 实际脱离视频

![独立v28运行：100 N退出脉冲，0.4倍仿真实时播放](../../../logs_eval/base_v29_n01/force_probe_v28/20260921_render_left_s2921/attempt1/env0_exit100N_0p35s_top_0p4x.mp4)

这是独立8 env运行的env0，不是上表强档env0的同一条轨迹。片段4秒，原生每control tick写一帧（50Hz），按20fps播放，所以速度为仿真实时的0.4倍。视频1.25–2.125秒对应实际0.35秒施力；视频2.05秒对应t0+0.32s持续脱离确认。力停后未重置姿态或补动作。

本视频案例的双指接触约8.80/16.34 N→0/0 N，短窗最大相对位移约12.5cm；正常释放约在t0+5.46s，晚于片段。顶视画面能直接看见夹住→间隙→脱离；侧视前段被门遮挡，因此选顶视。视频运行受力组持续脱离3/4，0 N组0/3到窗（另1个未到窗）；这些不并入两轮剂量比较。该运行耗时705.3s，随后进程退出。

[片段时间与物理数据](../../../logs_eval/base_v29_n01/force_probe_v28/20260921_render_left_s2921/attempt1/representative_clip.json)、[片段逐tick记录](../../../logs_eval/base_v29_n01/force_probe_v28/20260921_render_left_s2921/attempt1/env0_clip_control.csv)、[视频运行receipt](../../../.ai/runtime/n01_force_probe/20260921_render_left_s2921_attempt1/receipt.json)保留完整对应关系。

## v1.2 的计划安排

`T_nom/T_force`对照仍保留。两者从相同随机actor/critic初始化、使用同一stage-blind执行/目标/奖励/预算，仅课程不同，才能回答外力课程是否有效。既有C002或v28模型不能替代这个对照。GPU2安排T_force，GPU3安排T_nom；每臂6000 update不变，粗估Teacher墙钟约45.5h、总90.9 GPU·h，实际吞吐待正式实施后测量。

本次v28模型、RMS、optimizer与诊断数据均不进入正式scratch训练。完整N01的功能片段仍需在C002+B05上验证；两Teacher取得实际后缀能力后再推进Student。

初始轴向范围保留退出40–100 N、沿柄25–60 N；低端允许保持，高端已有破坏握持的证据。连续角度用最简单的总幅值范围插值：u=|θ|/90°，A_min=40−15u，A_max=100−40u，A在该范围内均匀抽样。0°仍40–100 N、±90°仍25–60 N、±45°为32.5–80 N。插值是当前课程抽样默认值，不是拟合出的物理失抓阈值；本次实际斜向测试为42.5/85 N，未逐角度校准。0.2–0.5s仍为原计划时长范围，本次只验证0.35s。已回填[plan v1.2](../../v29/a2_piper_v29_n01_plan.md)与[handoff](../../v29/a2_piper_v29_n01_worker_handoff.md)。

## 可视化与证据入口

合力图沿用[实际B05七族/CAD来源](20260921_n01_force_visual_geometry.json)，增加连续θ、总幅值、分量与半平面；夹爪姿态为G对齐示意。交互检查已确认F5/−45°/100 N显示分量−70.7与70.7 N，浏览器无异常；几何图不当作v28实际试验录像。幅值滑块仅演示合成关系。

![实际B05上的合力示意，三维视角](20260921_n01_force_composition.png)

- [Owner原始请求](../conversations/20260921_codex_n01_force_plane_gpu23_quick_test.md)
- [强档receipt](../../../.ai/runtime/n01_force_probe/20260921_initial_left_s2921_attempt5/receipt.json)
- [两档统一汇总](../../../logs_eval/base_v29_n01/force_probe_v28/dose_comparison_0p55s.json)
- [强档0.55s统一读数](../../../logs_eval/base_v29_n01/force_probe_v28/20260921_initial_left_s2921/attempt5/dose_readout_0p55s.json)
- [强档control读数](../../../logs_eval/base_v29_n01/force_probe_v28/20260921_initial_left_s2921/attempt5/control.csv)、[逐physics step读数](../../../logs_eval/base_v29_n01/force_probe_v28/20260921_initial_left_s2921/attempt5/physics.jsonl)
- [减半receipt](../../../.ai/runtime/n01_force_probe/20260921_half_left_s2921_attempt1/receipt.json)
- [减半0.55s统一读数](../../../logs_eval/base_v29_n01/force_probe_v28/20260921_half_left_s2921/attempt1/dose_readout_0p55s.json)、[减半control读数](../../../logs_eval/base_v29_n01/force_probe_v28/20260921_half_left_s2921/attempt1/control.csv)、[逐physics step读数](../../../logs_eval/base_v29_n01/force_probe_v28/20260921_half_left_s2921/attempt1/physics.jsonl)

运行前的失败均未产生施力结果：Hydra模块路径、Kit收到多余配置参数、v29 reward与v28 config混用、场景文件导入仍从cwd取v29配置。最终由明确v28源码/config绑定及动态导入路径定位解决；未向生产环境添加兼容默认或silent fallback。退出0本身不算诊断完成，须有实际probe summary与原始物理数据。
