# D056：C001 逐项验收

决策方：PLANNER。输入为 `scriptsFORhuman/v29/candidates/C001/CANDIDATE.json` 指定的冻结快照；320 个文件与当前执行输入逐字节一致，无缺失或差异，未生成摘要或哈希。两个独立只读 reviewer 分别核对 B01/B04 与 reward/reset/time，Main 核对 B05、资产边界和整体证据。

**结论：FIX_REQUIRED，仅缺一项 Stage5 定向运行证据。未发现需要修改生产代码的阻断缺陷；正式训练尚未批准。**

## 逐项结果

| 项目 | 结论及证据边界 |
|---|---|
| B01 抽样 | 接受。每侧六个质量×closer组合循环后打散，逐门参数固定；三档质量各1/3、有无closer各半。D052提供真实4096门计数。有限计数不等同独立Bernoulli抽样检验。 |
| B01 质量、COM、惯量 | 接受作者几何近似范围。panel与两片rose按共同密度分配，合计仍为抽样门板质量M；独立handle为.4/.5kg，原latch .1kg、G刚体.001kg另计。显式handle质量矩与native读回一致；参考mass_frame_readback及D052。 |
| B01 drive/friction | 接受。仅在USD边界将k、d、粘滞摩擦乘π/180并把q0转degree；力矩及静/动摩擦保持N·m。runtime按SI安装固定行和q0，未启用后续覆盖分支。D045释放窗口、D052全量读回、D055恢复证据保留。 |
| B04 | 接受。逐门固定M90–150°对应真实native upper；D045实际触限与natural/Stage1参数保持支持该实现，不外推全部恢复阶段或长期响应。 |
| B05 域与几何 | 接受规定生成域及已演示路径。Main核对七族、截面/roll/λ、I/J、实际r_tip条件return及训练外X1；连续门法向框架、局部凸体/caps和保持原多面体的64顶点分割符合规格。未用整形凸包填平return。D038/D048的实际资产总览和接近/闭合帧已由Main亲自查看。保留离散质量积分及分段碰撞近似的限制，不声称任意动作下均无接缝效应。 |
| B05 G、consumer、重建 | 接受。proper frame、FixedJoint局部端点、consumer identity、局部Z−.10 pregrasp和85mm TCP一致；旧LEFT目标镜像关闭。metadata删除不再适用的handleRadius，诊断读取v29几何。重建从必需参数确定生成，无随机几何回退。D048全28386原始接触点位于各门自由主握段，34门双指接触及已记录panel法向力结果保留。 |
| Stage5 | 源码/配置接受，**定向运行证据待补**。实际注册步权重−.08/−.16/−.04符合−4/−8/−2及dt=.02，但现有运行没有非零Stage5读数。需补实际环境中heading、roll/pitch的raw/scaled贡献及非Stage5零输出。 |
| D023及阶段条件 | 接受保留的source＋resolved证据。原hinge门角gate/门速收入、hold×正门速、grasp及3→4、release、4→5、回臂条件保持。合同的source与解析配置路径足以核对这些未改公式；不追加物理过渡重演，也不据此声称策略已完成后期阶段。 |
| 高度/B07 | 接受。双侧.90–1.20m及真实64门高度；closed G在自然root reset前缓存，明确的前后natural reset样本支持位置与联合yaw域。scale begin属于首次natural reset前，不能当作B07样本。 |
| 时限、结转、速度 | 接受实现/配置及已有运行范围。30s、dt=.02、[525,150,150,150,150,300]和结转；Stage0在1.8–2.2m以smoothstep从.3过渡到.5，Stage4/5目标.3。64个自然首episode均实际525步Stage0超时；未将目标速度称为已达到速度。 |
| B06/B03 | 接受选定资产/init/rig边界。实际导入MERGED H180/F45与正确arm默认值；composed USD含instance-proxy碰撞体，三处housing visual隐藏、支架可见、无中央包络，base15°和三相机rig保留。没有三路图像或硬件结论。 |
| B02 | 接受保留的topology/writer边界。D055确认handle位置目标0及+.261799N·m effort是继承行为；当前与HEAD的reset/effort方法相同，v29 q0只写hinge。无软件latch或恢复策略改动。 |
| 同门生命周期 | 接受actual natural reset及Stage1 fixture范围。D045/D055固定metadata、G和native参数保持；34门真实Stage1样本/恢复，详细29门root/robot q与全部34门door q/qdot符合真实snapshot。没有全阶段恢复结论。 |
| PPO、obs、checkpoint、reload | 接受接线范围。D037/D042/D052覆盖64 smoke、真实full reload与自然首episode、4096单batch262144timesteps、actor133/critic138 float32 cuda0、step1 checkpoint读取。env load分派不等于完整physical/staged状态恢复；策略质量待正式训练后评估。 |
| terminal callback | D054接受事件接线的INSPECTED结论；新end路径尚未实际执行。原单batch after_first_batch保留为当次terminal证据，无需重复GPU运行。 |

## 唯一补证

Worker准备一个小型真实环境Stage5 reward probe：2个或少量env、无render、保持生产域/控制。明确使用fixture设定输入，记录实际root、goal、rpy、stage、dt以及当前reward函数的raw和scaled贡献。覆盖Stage5对齐、非零heading、非零roll/pitch与旧−2/新−8合成，以及相同姿态下Stage4的新项为零；同时说明实际K处理路径。不能用复制公式的独立计算替代实际函数输出。

为此独立reward主张，允许一次性公开stage/pose fixture；它不代表自然stage advance或policy成功。先以真实step完成pending natural reset刷新；不写假bank、不改生产reward/gates/domain。实现后提交一次具体命令核对，再使用剩余1514.041274s验证额度执行。无关的64/4096、contact、dynamics、staged证据保留。

保持冻结C001；完成后提交C002的probe/证据增量，明确继承未改的生产输入与既有结论。

## 正式命令的路径调整

6000 batches、seed291、GPU0、4096 env、save100、scratch、48h上限和20min/64自然首episode评估仍是提案。39.34h是单batch外推，不能当作稳定吞吐保证。

依据现有log-layout约定，后续新产物直接写入：

- 训练：`logs_rl/a2_piper_full_stage_a2_base/base_v29/push_baseline_C002_seed291/`，runtime capture放在该run内。
- 评估：`logs_eval/base_v29/push_baseline_C002_seed291/natural_final/`，配置、日志、metrics、trace及renderings作为一个结果单元共置。

同步更新checkpoint和所有output引用；这是新运行路径选择，不是迁移，不创建旧路径别名。最终批准须绑定实际最终候选。
