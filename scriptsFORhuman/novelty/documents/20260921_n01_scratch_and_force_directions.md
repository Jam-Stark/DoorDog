# N01：实际把手上的方向覆盖与scratch修订

本文件保留v1.1当时的三射线图与scratch决定。后续Owner要求斜向合力并授权GPU2/3；当前方向、资源和实测状态以[plan v1.2](../../v29/a2_piper_v29_n01_plan.md)及[v28 quick test readout](20260921_n01_force_probe_readout.md)为准。下文历史记录不回写。

2026-09-21 HKT。作者：N01 planner。依据[Owner本轮问题/建议](../conversations/20260921_codex_n01_force_visual_and_scratch_request.md)。当前合同已更新为[plan v1.1](../../v29/a2_piper_v29_n01_plan.md)和[worker handoff](../../v29/a2_piper_v29_n01_worker_handoff.md)。本轮只有几何可视化、设计讨论及文档修改，没有训练或物理rollout。

![实际B05把手与掌部施力方向概览](20260921_n01_force_directions.png)

## 方向覆盖的准确含义

当前每次只从下列三条射线中等概率选择一条，角度散布为0°：

| G局部方向 | 世界系请求力 | 物理含义 | 幅值 |
|---|---|---|---|
| −Z_G | `A · R_G(t0) · (0,0,−1)` | 朝实时pregrasp的退出方向 | 40–100 N |
| +X_G | `A · R_G(t0) · (1,0,0)` | 沿当前抓取点的把手中心线切向 | 25–60 N |
| −X_G | `A · R_G(t0) · (−1,0,0)` | 沿把手切向的反方向 | 25–60 N |

它们在G的X–Z平面内，覆盖的是三条射线，不包括两射线之间的斜向、+Z_G和±Y_G。图中箭头统一使用示意长度，幅值读取标签；箭头不是位移或已测得的滑脱轨迹。

力从掌部`arm_body6_to_gripper`质心C施加，G只是定义方向的抓取坐标原点；P为`G−0.10m·Z_G`的pregrasp参考点。沿柄侧向不等于撑开手指，也不保证沿长杆滑动后就能脱离。G随门/把手姿态改变；真正注入时读取实时G并在t0转换到世界系，一次脉冲内保持该世界方向不变。图中旋转观察视角只改变观看角度，不改变课程定义。

## 实际几何与示意姿态

可交互画面使用[源参数记录](20260921_n01_force_visual_geometry.json)中的七个真实C002采样实例；由当前`handle_v29.py`重新构造形状，并使用当前URDF引用的掌部/手指STL。没有用概念圆杆替代全部B05。

| B05族 | C002实例env_id |
|---|---:|
| F0 | 0 |
| F1 | 6 |
| F2 | 13 |
| F3 | 7 |
| F4 | 14 |
| F5，带回钩 | 19 |
| F6 | 2 |

参数来自既存C002 `runtime_capture/begin.json`，不是新运行。F0按源代码的多面体构造显示圆杆/端帽；runtime中该无回钩族使用原生capsule。门板显示局部截面，材质颜色只服务辨认。

夹爪CAD是真实项目文件，但画面中的握持姿态为`TCP=G`、姿态与G对齐、指间位移按该样本closing half-extent摆放的**几何示意**，没有声称该姿态已在物理中稳定夹住。C取当前URDF的inertial CoM。文件记录源路径、样本参数和姿态假设，可据此复建。

## v1.0确实使用了warm-start

v1.0规划为：C002 step6000 actor＋RMS → 500 update共同名义适应T_shared → 分出T_nom/T_force，各1000 update。这样有利于较早得到交互样本，但会包含旧策略对新执行接口的适应过程。

本轮采用从头训练高层Teacher，主要考虑：N01从第一步就在共同stage-blind执行与恢复目标下学习；两组直接比较完整名义课程和外力课程；不把未合格C002的既有策略偏好作为必要起点。这是实验设计取舍，不是已经证明scratch学习速度或最终效果更好。

## v1.1的固定安排

- T_nom/T_force从同一随机actor/critic开始，seed291；fresh RMS、optimizer、scheduler、课程与计数。`checkpoint=null`、`auto_load_latest=false`，不加载任何C002高层训练状态。
- 两臂使用完整C002＋B05物理域、相同N01控制/奖励/计时和自然reset；T_nom无外力，T_force从update0起按episode分配50%计划扰动，但只在真实握持后施力。
- 尚未学会握持时，受扰组自然不会注入力；不另建共同名义预训练再fork，不补齐失抓数，也不给一组额外更新量。
- 既有冻结A2_Base腿部策略保留。从头训练腿部运动不是本次N01目标。
- Student从自身模型初始化开始，通过**新的合格T_force**示范启动，之后比较Teacher执行示范和Student实际执行的shadow监督。Student示范启动与高层Teacher从头训练没有冲突。

如为P1外力功能校准单独使用已有C002策略，该run仅作工具诊断；其权重、RMS、optimizer和轨迹不流入正式scratch训练，也不计入方法成绩。

## 预算随初始化一起修订

原500＋1000＋1000 update不能直接换一个“scratch”名称继续使用。本版以C002既存规模作为首轮参考：**4096 env×64 control tick×6000 PPO update/臂**，固定终点，不保证收敛。

[C002实际6000 update耗时45.46h](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v29/a2_piper_base_v29_C002_final_readout_20260921.md)，因此GPU2顺序两臂粗估约90.9h，另计功能校准、评估和Student。新代码及GPU2实际吞吐以启动观察为准；如果申请第二张GPU，两臂可独立并行，资源需按Owner要求另行申请。当前没有启动训练或占用GPU2。

展示检查：交互画面已在软件渲染浏览器中打开，实际切换F5、俯视和退出方向选择成功；未出现脚本错误。预览程序已关闭，没有保留浏览器进程或本地服务。此检查仅证明画面可用，不是物理运行或恢复能力证据。
