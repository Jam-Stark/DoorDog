# 转交planner：v28进度与plan调整判断

编写：-codex worker；Owner已批准决定与最新讨论分别标记。

请根据以下进度和Owner最新讨论，判断v28 plan是否需要调整，并给出最小章节变更建议。本次只做规划判断，G0保持暂停，不启动训练、切换asset或执行Git提交。

## 当前进度与已批准决定

- 已实现v28 robot/扁平配置、delta动作限位、腕部运动/塔架接触/释放后回位奖励及相机trace字段。CPU compose通过36项登记差异，六项CPU语义检查曾通过；其后新增trace尚未做runtime验证。旧asset平地行走基线为3姿态×64env，无观察到的摔倒；新asset对照及完整G0、PPO smoke、C4渲染、G1/正式训练未完成。没有首个commit。
- Owner决定先仿真后硬件；真实腕机支架CAD尚不存在。腕机采用90×25×114.7mm支架包络＋外壳盒，合属独立的wrist_camera_tower刚体，总质量暂估0.15kg；相机中心仍为参考姿态下相对法兰高180mm、俯角45°。
- 金属板collision高度5→4mm后，arm_body0与腕机塔架接触力均为0，但trunk/Vpiper support异常接触仍存在，G0未通过。Owner批准R3改为稳定1s后检查50步、root z∈[0.45,0.51]m、臂速度绝对值<0.5rad/s；R5改为FK预测0.432637±0.01m。修订后最终验收尚未重跑。
- Owner仅批准制作两个待选asset：合并版将main/support/plate按原变换及完整惯量合入trunk，28刚体；裁切版保留31刚体，将main/support全部visual与collision在trunk z=130mm以下整体删除，距已定位冲突盒顶面1mm，原inertial保留为仿真近似。两版均20活动关节、全机质量45.644808kg、arm/camera安装位姿不变，URDF/USD与静态读回已完成；未运行两候选物理验收、未绑定活动配置。早期局部三角块/凹口裁切已被统一水平裁切取代。

## 新讨论，尚未定案

- Owner希望降低腕机高度并减小俯角。180mm来自旧U3固定输入，并非已证明的Depth必要高度。Worker名义几何估算：保持TCP当前投影位置、不计遮挡，140mm≈39°、TCP光轴距离141mm；120mm≈34.5°、距离125mm；当前深度Min-Z为105mm。尚未选尺寸或改模型，上指遮挡及真实成像仍未由这些数字解决。
- Owner提出：Teacher先按较大碰撞包络训练，实际光学高度/俯角留到蒸馏开始时确定。当前Teacher关闭相机渲染，新增奖励是关节运动/接触/回位，可见率为report-only，因此worker认为有条件可行。需区分真实包络包含关系、动力学/动作合同，以及最终视角能否支持Student学习；最高版本不自动等于所有候选的最大包络。蒸馏须按最终相机重新生成图像，Teacher标签可复用。

## 请判断

1. 是否将“Teacher碰撞/动力学合同”与“Student光学安装合同”分阶段冻结？具体哪些§3相机约定、§4 G0-C检查与§8.5接口可以后移，哪些仍须在Teacher训练前完成？
2. 合并/裁切待选路线会要求哪些最小body计数、质量惯量或G0验收合同变更？最终选型仍由Owner决定。
3. 若Teacher采用保守大包络，§8.2中“训练失败→硬件方案不兼容”的解释是否应收窄，避免用大包络失败否定较小的最终安装方案？

请输出“是否需要调整＋最小修改清单＋仍需Owner决定的事项”，区分已批准决定、讨论建议与证据不足项，不扩展到额外训练或全面审计。

## 依据文件

- [v28 plan](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/a2_piper_base_v28_plan_20260909.md)
- [独立决策日志，D018–D029；D028/D029为PROPOSED](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/a2_piper_base_v28_decision_log.md)
- [G0状态与证据边界](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/g0_decision.json)
- [两个asset候选对比](/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/data/robots/v28_asset_comparison_20260909.md)
