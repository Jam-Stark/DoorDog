# Pull v28 本轮closure（m5，2026-09-13）

**合法终态：`BLOCKED_G0_INFRA_REPAIR_LIMIT`。P2诊断已封存，G0部分证明通过，但PPO初始化失败；PA三格未启动。**

## Owner需要决定的具体事项

本机计划§8规定，policy读数前的infra/harness修复“最多2次/格”。G0的两次探针修复已经用完，未按子探针重新计算额度。随后PPO初始化暴露了第三个实际接线问题，因此暂停相关执行并完成本轮收尾。

根因已通过现有代码和日志定位：扁平化配置把原`env.config.robot: ${robot}`拆成独立节点。预处理把root robot更新为actor133/critic138，但环境的副本仍是0/0，真实日志构造了`LSTM(0,256,num_layers=2)`，在CUDA迁移时触发`CUDNN_STATUS_BAD_PARAM`。这不是已证实的硬件/驱动故障或显存不足。

已准备但**未应用**的一行修复：

```diff
-    env["robot"] = robot
+    env["robot"] = "${robot}"
```

Owner可授权额外这一次修复，并以新attempt接续原计划256env×5batch smoke、其full-checkpoint双侧natural评估；G0全链完成后才继续原三格PA。补丁只恢复既有引用关系，不改变133/138合同、模型、物理资产、reward/event/ready或门限。当前没有执行第三次修复，也没有新增测试、fallback或兼容路径。提案及事实链分别见`OWNER_PROPOSED_FIX_NOT_APPLIED.patch`和`OWNER_REPAIR_REQUEST_20260913.md`。

## P2旧配方已完整封存

三格旧训练没有重跑；9500/10000/10500各三格双侧natural exact64，共18条全部完成，64 births与64 traced episodes/条，三份中介归约及raw trace保留。T trace含旧D2，C trace不含。

10500描述性读数：

| 格 | target overshoot中位 L/R | E5 L/R | ready / clean release |
|---|---:|---:|---:|
| T_S1 | 3.7500 / 3.7908 | 63/64、64/64 | 两侧均0 |
| T_S2 | 2.0872 / 2.0300 | 64/64、64/64 | 两侧均0 |
| C_S2 | 5.7800 / 9.0056 | 64/64、64/64 | 两侧均0 |

18条K5均64/64，ready、clean release、high-margin B、E6/E7均0。T_S2/C_S2共享seed lineage；T_S1没有C_S1匹配对照，不能把全部跨格差异当作匹配因果估计。结论仅为旧配方未建立ready/释放能力，不证明几何无解，不路由新baseline。

三条旧训练legacy receipt仅按process/checkpoint收口并明确限定旧PASS含义；三条新eval事件按完成的后续诊断处理。C_S1仍DECLARED，未补跑；没有D2重试或旧资产门A矩阵。

## S1–S8应用和G0实际证据

在P2封存commit之后，按接收manifest/receipt直接复制并逐文件比较S1/S2：MERGED28 bodies/20 joints、140mm/38.76°、reset `[0,.10,-.10,0,-.415,1.57]`；未替换现有A2_Base。仅应用pull范围D17、腕运动、独立tower、持久release C/D回位与camera字段。保持pull事件/ready/Stage4语义，无主线K/A284/DEVCONF。

P_S2实际resolved合同扁平化保留1024/6000、原reset比例及gripper1300/32/45；初次错误raw robot全量替换已在GPU前修正并留证。CPU compose只能证明静态值，此次运行进一步暴露了动态robot引用缺陷，不能把CPU完成提升为PG4运行通过。

| G0项 | 实际状态 |
|---|---|
| PG1 | 直接内容、28/20及按名body/dof/contact映射通过 |
| PG2 | reset/obs锚点和上下界D17生产hook检查通过 |
| PG3 | 固定权重、tower raw及零事件持久release门映射通过；无晚阶段事件 |
| PG4 | CPU compose完成；真实运行发现robot引用缺陷，待额外修复 |
| PG5 | 新资产同姿态LEFT180°、RIGHT本侧定义通过 |
| PG6 | 50步零高层指令接触通过；PPO初始化失败，无checkpoint，未做对应natural评估 |
| PG7 | m5匹配旧/MERGED三姿态全部D37通过，无tracking failure，0摔倒 |
| PG8 | 执行链/watcher/reducer已实现；缺少G0检查点，未验证端到端 |

接触探针实际调用冻结A2_Base腿部policy，高层pull命令为0。50步内trunk/arm_body0..6/tower监测接触均0N。release/E6未出现；零事件真值表与名义投影不代表晚阶段行为或无遮挡/有效深度。相机最终光学仍属G2；X24随机校准仍OPEN。

失败证据全部保留：contact_a1被SimulationApp.close掩盖原异常，仅有exit0不能PASS；修复退出落盘后，a2暴露natural注册冲突；按现有natural evaluator的注册开启、比例`[1,0,0,0,0,0]`修复后a3通过。随后G0 PPO attempt1在学习前失败，子进程返回0但runner因缺`model_step_000005.pt`正确返回1，peak5240MiB/headroom19336MiB。

## Opening、预算及后续议题

- PA_S1/PA_S2/PA_S3均`NOT_RUN`，有效6000终点0个，**k=null，denominator=3**。状态为`NOT_ASSESSED_G0_INCOMPLETE`，不是0/3，不贴`OPENING_NOT_ESTABLISHED`标签。
- 没有新baseline历史checkpoint、最早opening时点或可转交候选。PA margin/ready/camera/E6/E7均未观测；不以旧P2或G0零事件替代。
- P2新增评估18/18；旧训练0次重跑。G0完成PPO batches **0**（原计划5，上限32）。PA完成 **0/18000** batches，warm `NOT_RUN`，未超18500上限。
- 后续P3–P5先解决G0接线、完成原三seed opening证据，再另行立项；send-past-body、clearance、handle-Y、hinge速度、释放时间预算、E6/E7均未形成新结论。
- N01/N02恢复/感知/门域、N03 push/pull合一、G2光学、X24随机校准保留后续需求。此次没有几何干涉证据可申请硬件调整，不提出硬件变化来绕过接线失败。
- Teacher/硬件/外部写入/push均未运行；无P3–P5自动续训。

## 收尾和接续

本任务tmux、waiter/coordinator/supervisor及GPU1/2/3 compute均已退出，Main租约已释放。无关tmux`0`和GPU0外部进程未触碰。只确认本任务已处理的P2/G0事件，不批量修改其他legacy状态。

本地commit节点：P2封存`9246460`；G0实现/合法终态`cad573c`；本closure另作本地提交。PA endpoint未到达，不伪造该节点提交。没有push。预先存在的旧D2 62行和其他无关工作树改动保留未提交。

m5 canonical仓库：`/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0`。运行证据在`logs_eval/a2_piper_pull_v28/pull_v28_baseline_sync_20260913/g0/`与`logs_rl/a2_piper_pull_v28/pull_v28_baseline_sync_20260913/G0/`；小证据归档在`scriptsFORhuman/pull_v28/evidence/`。输出采用用户自有SSD任务目录，canonical路径不变，旧raw输出未移动。plan、decision log及`memory/a2-piper/pull-v28-baseline-sync/`已指向此Owner门。
