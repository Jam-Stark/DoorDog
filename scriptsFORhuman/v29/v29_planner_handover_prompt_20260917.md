你现在接任 DoorDog A2_Piper 项目的 v29 阶段 planner，与我（Owner）共同讨论后续方向，再逐步制定 v29 plan。

工作目录：`/home/baoquanc/workspace/DoorDog-A2_Piper`。

当前任务仅为只读接手和开场讨论。先理解已有结果、实现和我的意图，等我明确要求后再编写正式 plan 或进入实施。首轮不要产出完整方案、实验矩阵、预算或执行脚本。

先按项目 AGENTS.md 使用 file-based memory，沿当前入口定向阅读，不做全仓扫描或重复审计：

- `/home/baoquanc/workspace/DoorDog-A2_Piper/AGENTS.md`
- `/home/baoquanc/workspace/DoorDog-A2_Piper/MEMORY.md`
- `/home/baoquanc/workspace/DoorDog-A2_Piper/memory/a2-piper/MEMORY.md`，沿其中 v28、v29、novelty 三个 entry 获取必要上下文。
- `/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/a2_piper_base_v28_execution_closure_20260917.md`
- `/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v29/README.md`
- `/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v29/a2_piper_base_v29_decision_log.md`
- `/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/novelty/README.md`
- `/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/novelty/documents/20260917_v28_closure_N01_N02.md`
- `/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/a2_piper_longterm_TODO.md`
- `/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/a2_piper_longterm_TODO-Astra.md`

原始对话、v28 plan/decision/deferred register、具体 readout 和 source/config 按讨论问题再追溯。Memory 用于路由；实际 source、resolved config、运行证据与 Owner 后续决定优先。长期 TODO 中旧排期及 Astra 历史提案需要结合最新 closure 判断，不自动成为 v29 合同。

必须承接的 v28 结果：

- v28 已关闭。原三 seed 在 6000 batch 的 reach 为 1/3，可靠性未建立。
- 固定主候选 A282@6000 的 DEV clean 为 LEFT 123/128、RIGHT 47/128；备选 A284@5000 为 LEFT 69/128、RIGHT 52/128。两者均未通过双侧 DEV，CONF 未运行，未确认新合格 Teacher，未更新 Teacher/G7。
- 三条未过门 lane 的 clean 缺口主要来自 crossing 时 hinge<1.0472 rad。区分 complete、clean、姿态表现及相机可用性；不能用“到达完成状态”概括全部质量问题，也不能据此断言未评估 checkpoint 都不合格或几何无解。
- A284 按 Owner 要求提前停止；v28 已有结果和资源已收尾，不需要恢复旧训练或补齐此前豁免的 render。

v29 当前已有以下 Owner 决定和实际实现，请以此为讨论起点，不要再当作尚未实施的建议：

1. Stage5 goal 保持 `[2,0,0.5]`。新增朝 goal 方位的 yaw 平方误差惩罚，scale=-4；新增实际 roll/pitch 相对 0/0 的平方误差惩罚，scale=-8，与原 -2 合计 -10。新增项仅 Stage5 生效、不随 K 衰减。完成条件仍为 root_x>1.5。这些是初始实现值，行为改善尚未训练验证。
2. handle 高度 uniform 范围已改为 `[0.90,1.20] m`，自然起点评估继承该范围。旧 `[0.85,0.95]` 是 v26 初始窄域沿用至 v28。
3. MERGED 腕机物理与光学已改为 180 mm / 45°，arm init/reset=`[0,0.10,-0.10,0,-0.52,1.57]`，默认光轴约向下 15.2°、朝前。仅有 base 左右两台 D435i 加腕机，共三台相机；三台外壳 visual 隐藏、collision 保留，支架可见。多余中央包络的 visual、collision 和 rig 几何已完整删除；它原本未贡献质量/惯量，因此没有虚构质量扣减。

以上 source/config/URDF/USD 已落地，最终资产完成 64-env / 1-batch PPO 接线验证。该结果不证明 Stage5 行走改善、新高度范围成功率或成像质量。v29 尚无正式训练与资格评估；配置继承的 6000-batch 默认值、seed291 入口都不代表已批准的阶段预算或实验矩阵。

制定后续方向时，要主动参照 novelty 与长期 TODO，结合 v28 的实际瓶颈讨论工程改进与方法研究的关系，不只围绕新加的几项 reward 调参：

- N01：恢复图、非计划失抓后的恢复，以及失效边界采样。旧 pilot 仍未决，存在 endpoint 缺失和有效失抓暴露不足；不能直接当作有效方法扩大多 seed，也不能据此关闭方向。
- N02：交互历史状态估计与适应。已有 shadow 结果只支持有限离线信息量，短窗口/失败集、可部署输入与在线收益仍待讨论。
- 最新处置是两项“设计继续、实验延期”，尚未决定纳入 v29。既要认真考虑，也不要自动排入；不能把完美 Teacher 或最终相机/CAD 当成无限推迟讨论的前提。长期 TODO 中其他相关议题也应按证据和我的目标取舍，避免照搬旧版本排期。

首轮回复请简短确认你理解的 v28 结论和 v29 起点，指出最值得与我共同厘清的目标、矛盾或取舍，并提出少量聚焦问题。先听我说 v29 想解决什么，再继续讨论；现在不要输出 plan，也不要修改项目文件或启动实验。
