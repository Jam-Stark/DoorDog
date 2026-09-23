# v29 baseline handle ablation plan

更新：2026-09-22 HKT。计划决策：V29-D065；执行授权：D067；最终关闭：D078。状态：**D067_DELIVERY_CLOSED**。

已完成HA-C001的6000训练及一次final64，均exit0。B成功32/64（RIGHT32/32、LEFT0/32），A同6000进度0/64；单seed、整组B05干预及最终评估未完整配对的边界保留。源侧共享GPU1预约已释放。结果见[最终报告](/home/baoquanc/workspace/DoorDog-A2_Piper_v29_handle_ablation/scriptsFORhuman/v29/handle_ablation/results_seed291/REPORT.md)，关闭记录见[D078](/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/v29_handle_ablation_team/D078_HA_C001_FINAL_DELIVERY_CLOSURE.json)。以下为原计划与历史授权，不构成新的运行许可；结果分支为`codex/v29-handle-ablation-results-seed291`，原开发分支现位于B08工作区。

Owner要求新增一个GPU1对照组：去掉B05把手变化，恢复原Doorman门把手路径，由新worker team实施。本计划将它具体定义为 **v29 − B05**，保留其余已验收v29 baseline。Planner负责范围与候选验收，新worker team负责隔离实施、必要短验证、获批后的训练监督及结果交付。

## 1. 问题、对照和结论边界

问题：在相同v29非B05设置下，撤回B05整组变化，是否改善连续抓稳、Stage2→3学习与后续开门进展？

| 组 | 输入与用途 |
|---|---|
| A：现有v29 | C002已验收输入；GPU0、seed291、4096env、scratch、6000 batches。继续原运行，作为直接对照。 |
| B：本次对照 | 从同一C002输入构建，仅撤回B05；GPU1、同seed、同规模、同PPO配方、同训练预算。 |
| 历史v28 | 用于理解旧Doorman-derived实现与历史表现；不替代A，因为v28还与v29存在高度、动力学、起点、时间等差别。 |

B05整组包括几何族与连续几何域、截面/方向、离门间距、return/rose、相应质量属性，以及统一grasp target/FixedJoint/consumer改动。该实验不把“七族数量”单独识别出来，也不是仅将新生成器固定到F0。

若B明显恢复抓稳与阶段推进，只支持“B05整组在当前v29与本seed下增加了学习难度”的判断；不能进一步把原因分配给族数量、碰撞分段、目标帧或某个尺寸。若B仍差，也不能据此证明B05完全无影响，或直接认定高度/Stage0是原因。单seed结果不宣称跨seed稳定性。

Owner提供的v28/v29窗口分析是实验动机，不预先写成因果结论。已经由planner核对的A组3000里程碑见[D064](/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/v29_baseline_team/D064_BATCH3000_MILESTONE_REVIEW.json)：双指接触增加、双方已有Stage3历史，但尚无Stage4/5 snapshot或goal记录。

## 2. 源版本与隔离工作区

只读源工作区：`/home/baoquanc/workspace/DoorDog-A2_Piper`。

独立目标工作区：`/home/baoquanc/workspace/DoorDog-A2_Piper_v29_handle_ablation`；ablation分支：`codex/v29-handle-ablation`。本次planner为Owner保存baseline版本并准备该工作区，worker接手现有分支，不重新从旧HEAD搭建。

先读源项目MEMORY路由及下列输入：

- [v29 baseline plan](a2_piper_base_v29_baseline_plan.md)、[B05规格](a2_piper_base_v29_b05_handle_design.md)。
- [C002索引](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v29/candidates/C002/CANDIDATE.json)、[C001冻结输入索引](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v29/candidates/C001/final_input_snapshot/SNAPSHOT.json)、[C001源码差异](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v29/candidates/C001/selected_source_changes.patch)。
- [D056逐项验收](/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/v29_baseline_team/D056_C001_PER_ITEM_ACCEPTANCE.md)、[D060实际训练/评估配方](/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/v29_baseline_team/D060_C002_ACCEPTANCE_AND_TRAIN_APPROVAL.json)、[D061 loss观测限制](/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/v29_baseline_team/D061_INITIALIZATION_AND_LOSS_OBSERVABILITY.json)。baseline tag内另存于`scriptsFORhuman/v29/versioning/C002/`，便于在独立工作区读取。

plan首页与冻结候选中的早期“待实施/待验收”状态不覆盖D060：C002生产实现已经验收，策略结果仍在形成。

**普通git worktree不会自动包含当前工作区未提交的C002改动。** 新工作区需要用C002指向的C001冻结输入补齐实际生产代码、配置、资产和必要依赖；不能只从Git HEAD创建一个旧版本便开跑。`selected_source_changes.patch`只是相对源HEAD的差异，不是整个可运行包。用已有快照和一次直接内容比较确认继承关系，不生成哈希清单。

源工作区代码、机器人资产、GPU0进程、原输出和已有checkpoint保持不动。新worker所有生产修改与运行产物写入独立工作区；只从源读取对照证据，不把本次控制开关回写进正在运行的A组。

### Git版本管理

Owner已明确要求保存baseline和ablation的Git记录，本次范围内允许本地提交，默认不push。

| 引用 | 用途 |
|---|---|
| `codex/v29-c002-baseline` 与固定tag `v29-c002-baseline` | 保存C001的320份冻结输入及C002新增probe，附候选/验收/运行配方来源；作为A组的代码与资产锚点。不是从当前脏工作区随意`add .`。 |
| `codex/v29-handle-ablation` | 从上述tag开始，首个提交保存本计划和版本约定；后续只提交本实验实现与必要配置/报告。 |
| `v29-handle-ablation-c001`，必要时递增 | 对应实际实现候选；通过planner验收后固定为该次运行版本。运行receipt引用该tag、完整命令和配置，不能只写不断移动的分支名。 |

按“已验收baseline → ablation计划 → B05差异实现/修正 → 已验收运行候选”留清楚的提交链。候选tag不force移动；同一正式run期间不修改其生产输入。后续变更形成新commit/候选并明确哪些证据受影响，不靠覆盖旧tag隐藏改动。训练日志、大checkpoint和完整capture保留独立输出，Git保存代码、配置、资产、必要小型manifest和结果索引，不将整个运行目录加入版本库。

已完成：321份冻结输入在独立工作区物化并逐字节一致；baseline本地commit和上述固定tag已建立，ablation分支由该tag分出。版本来源保存在目标工作区`scriptsFORhuman/v29/versioning/C002/VERSION_BINDING.json`。原工作区仍在`A2_Piper`，未执行远端push。

## 3. 干预范围：旧Doorman-derived把手整组

“原Doorman”在本实验中指**本项目B05之前、v28实际使用的Doorman-derived把手链**。当前`door.py`保留的legacy几何分支是主要复用入口。不是把最早上游的整份door.py覆盖回来：早期上游有不同grasp target偏置及handle drive范围，整体覆盖会额外改动B02/控制负载。

| B中恢复 | 具体范围 |
|---|---|
| 原始几何 | axle Cylinder、两侧Capsule lever、原hook Cylinder；旧尺寸/随机hook生成路径。 |
| 旧尺寸域 | axle长U(.18,.21)m、lever长U(.11,.14)m、hook长U(.04,.06)m、半径U(.011,.015)m；旧hook概率1/2。实际值写入metadata。 |
| 饰件 | 撤回B05两片rose；恢复旧keyhole显示路径，其本身没有新增collider/质量authoring。 |
| 质量属性 | 旧axle .2kg、两侧lever各.1kg、存在时两hook各.05kg；几何相关COM/惯量按旧表示生成并读回。门板质量仍按B01共同样本M，不引入新的mass抽样。 |
| 旧G/FixedJoint | 使用本项目pre-B05把手中点目标：x=−axle_length/2、z=handle_height及配套FixedJoint，而非最早上游的固定x=−.15、z=height+.02。 |
| consumer | 恢复旧target rotation、旧pregrasp offset与原LEFT镜像补偿，使旧资产和旧consumer成套使用。 |
| metadata/诊断 | 恢复legacy `handleRadius`及旧尺寸字段；B组不伪造`v29Handle`，但保留真实`v29Dynamics`。重建和诊断按明确的B05选择读取相应字段。 |

撤回几何导致的COM/惯量、G位置及其派生接近姿态变化属于B05整组干预。不要用新几何的惯量、旧mesh配新G或人工补偿姿态制造第三种混合资产。

原handle动力学、实体latch/mimic三DOF、handle角度/effort writer保持v29已验收B02边界。尤其不因读取上游参考把handle drive cap改回上游1–2N·m；配对保留A组的实际负载参数。

## 4. 保持不变的共同设置

| 项目 | 保持的v29语义 |
|---|---|
| B01 | 三档30–80/80–120/120–160kg各1/3；closer有/无各半；联合k/d/cap、q0、native静/动/粘滞摩擦；逐门固定、跨natural/staged保持。 |
| B04 | 逐门固定native M90–150°；角度/单位/限位writer不变。 |
| 高度 | **.90–1.20m保持**，不回到v28的.85–.95m。 |
| B07及Stage0 | 距离1.2–4.0m、横移±.5m、联合yaw算法及闭门G缓存；1.8–2.2m内近.3/远.5m/s平滑速度保持。 |
| 时序/阶段 | dt=.02、30s、[525,150,150,150,150,300]及结转；5个control-step连续抓稳门、阶段条件、staged比例与容量保持。 |
| 奖励/PPO | D023现有公式、Stage5 −4/−8及原−2、K与penalty driver、obs/action、LSTM、PPO超参保持。 |
| 机器人 | v29 MERGED H180/F45、base15°、arm reset、TCP85mm、三相机/中央包络状态保持；实际手指45N、Kp1300/Kd32与M39保持。 |
| 方向/分组 | push/out、左右2048/2048、side permutation seed291保持。 |

保持B07算法意味着它仍读取本组合法闭门G；旧G引起的派生bearing/pregrasp变化是干预的一部分，不另强行复制A组root姿态。两组都从scratch和空的自然建立snapshot bank开始，不能将A组后段bank复制给B。

## 5. 已确认代码落点和最小实现

| 当前源路径/符号 | 施工要求 |
|---|---|
| `gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py::get_TaskObjCfgDict_for_door_config` | 保留v29 dynamics、左右及共同域；只有B05采样与`v29_handle`赋值可切到legacy。 |
| `gr00t/rl/isaac_utils/playground/env_rand/door.py` | 复用`v29_handle is None`的legacy几何、旧G与metadata/rebuild；继续传入`v29_dynamics`。 |
| `gr00t/rl/envs/door/door_open_a2_base.py::_init_a2_v24_friction_runtime` | 原`a2_v29_baseline_enabled`仍打开，以保留v29Dynamics/native参数安装。 |
| 同文件scene creation与pregrasp显示 | target rotation、pregrasp、debug geometry目前也由全局v29开关选择，需要只按B05选择拆出。 |
| 同文件`get_a2_hold_diagnostic_runtime_metadata` | 当前全局开关要求`v29Handle`；改为明确的几何选择，legacy读取真实`handleRadius`。 |
| v29 ablation/eval配置 | 新增一个明确对照配置，继承v29共用设置，只列本实验差异、标识和输出。 |

**不得将`a2_v29_baseline_enabled=false`当作本次ablation**：它会同时关闭B01/B04接入。最小实现是在新工作区为v29 profile显式增加B05选择，例如`a2_v29_b05_enabled`；A型配置true，B型配置false。它只决定把手几何/G/consumer/诊断。不要以缺失metadata触发“自动退回旧资产”，也不建设通用兼容框架。

旧consumer当前参考：target rotation `(0.5,0.5,0.5,0.5)`、`A2_PREGRASP_OFFSET=(-.10,0,0)`及 `a2_v26_6_side_mirrored_handle_offset_enabled=true`。B05则是生成proper G、consumer identity、局部Z−.10。以实际source/config/native读回验证完整链，不能只改其中一个数。

新实验配置建议名：`base_v29_doorman_handle.yaml`。实现后分别给出resolved配置的预期差异和实际加载asset/模式，不要求重新审计全部已验收baseline。

## 6. 共同随机量：同seed不等于同一批门

A组已实际记录全部4096门metadata：

`/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/a2_piper_full_stage_a2_base/base_v29/push_baseline_C002_seed291/runtime_capture/after_first_batch.json`

旧hook、keyhole等会改变全局NumPy随机调用顺序。因此B组从上述真实`door_metadata`提取一次逐env共同参数表，保留env_id绑定，并在生成时显式固定：

- 左右、in/out、door width/height、handle安装高度/横向位置、door type、total wall height和门板质量。
- 完整`v29Dynamics`，包含本门closer、摩擦、M与SI drive参数。
- 原handle drive cap等不属于B05的负载参数。

`doorOpenLR/OpenIO`的数值符号需映射到既有字符串枚举。`hingeDriveStiffness/Damping`是已author到USD的degree口径，`v29Dynamics`内是SI；保留既有v29单位转换路径，不把两者混写。

**不复制**A的`axleLength/handleLength/hookLength/spawnHook`作为legacy参数：它们是B05轴颈/弧长/return的结果。B自己的旧尺寸与hook样本单独生成一次并保存，保持旧分布。`handleRadius`须来自该旧采样，不能拿B05 neck radius代替。

短验证及正式首次初始化各记录实际共同字段，和A表对照一次。C002 metadata未保存全部frame/cover/material随机值；这些保留原共同生成范围并明确哪些未逐env配对，不能据已有字段一致声称整个USD除handle外逐字节相同。无需为了该限制重跑A或复制一套全场景冻结系统。

64-env自然评估也要记录对应共同参数与实际域。若A最终评估metadata可用于配对，按该64门的env_id配对；不能直接截取训练4096表前64行并假定左右/域配比仍正确。无法逐门配对的项明确列出，仍保持相同评估分布与协议。

## 7. 功能落地、一次聚焦验收与启动

1. Worker回报实际task ID、独立cwd/branch、拟WRITE_SET与GPU1资源；普通读取和隔离实施继续推进。
2. 实现明确B05选择、legacy整链和共同参数表；提供简短source/config差异说明，不改其余配方。
3. 复用现有harness完成一次小规模实际操作路径证明：LEFT/RIGHT × legacy plain/hook，包含实际资产/target-frame图、关节/native参数读回、明确fixture下的接近/闭合双指接触；再用少量env完成一个PPO batch及保存。可合并相容采证，不照搬B05的34例全族campaign，也不重新跑4096单batch资格审计。
4. 准备验证预算为GPU1累计20分钟、单次10分钟上限；worker记录具体命令与独立输出后在该范围执行，不另设日常短验证审批循环。实际故障按证据修复，不追加无关测试、护栏或重复审查。fixture接触不当作策略成功。
5. 在ablation分支提交本次实现，向当前planner提交候选tag、上述必要证据、共同字段对照、精确训练/eval argv和输出目录。Planner只做一次B05撤回边界与命令绑定，保留无关既有验收；通过后发GPU1 `TRAIN_APPROVED`，无需再次请求Owner批准同一对照目标。

Owner已指定GPU1与新worker team；此计划不是已经运行的候选回执。当前新worker未绑定，没有GPU1训练启动记录。GPU1在实际启动时确认可用并登记租约，不因旧记录空闲而抢占其他运行；不占用或停止GPU0。

## 8. 锁定训练/评估配方

| 项目 | 对照B |
|---|---|
| GPU | 物理GPU1；`CUDA_VISIBLE_DEVICES=1`、`CUDA_DEVICE_ORDER=PCI_BUS_ID`、进程内`ACCELERATE_TORCH_DEVICE=cuda:0`。 |
| 模型/初态 | 与A相同LSTM/PPO和seed291；scratch、`checkpoint=null`、`auto_load_latest=false`；不加载v28/v29已有策略或bank。 |
| 采样预算 | 4096env、6000 batches、64 rollout steps/batch，按相同batch与environment-step比较；每100保存。 |
| 其余运行设置 | 沿D060实际resolved配置及argv，保持headless、原logging/renderer设置；只改变B05选择、实验ID、GPU及独立路径。 |
| 正式单次上限 | 从实际launch计48小时，含初始化；ETA依据实际初始化/吞吐更新，48小时不是从每次报告重算。 |
| 最终评估 | 实际完成6000并保存精确final checkpoint后，在GPU1串行执行64个自然首episode；full loader、新自然reset、staged/K driver关闭，协议与A一致，上限20分钟。 |

拟独立输出，均相对B工作区：

- 训练：`logs_rl/a2_piper_full_stage_a2_base/base_v29/push_doorman_handle_seed291/`。
- 评估：`logs_eval/base_v29/push_doorman_handle_seed291/natural_final/`。
- 候选/共同参数表/对照readout：`scriptsFORhuman/v29/handle_ablation/`。

训练入口仍是 `python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm`；使用实现后的新ablation配置，补齐D060匹配override及本组输出。该行是实施模板，不把尚不存在的配置写成已执行命令。实际完整argv由worker提交并绑定候选。

超过30分钟使用独立named tmux与既有run_supervisor。一轮初始化检查后，按实际1000/3000/6000 checkpoint、terminal/failure和硬截止登记绝对时间，保持一个逻辑等待。不得周期性唤醒模型看同样日志。正式失败或需要改配方/预算时保存现场交planner裁定；不自动重启或用“暂时没学会”判代码失败。

## 9. 预先确定的比较读数

在1000、3000、6000 batches比较A/B各自末100个batch窗口：901–1000、2901–3000、5901–6000。每格注明实际窗口、缺失项及日志精度。主要以A/B为对照，v28仅另列背景。

优先记录已有直接指标：

- Stage2 active占比；双指接触、contact stability、streak≥5与grasp-complete/2→3 advance。
- Stage2连续计数p50/p90，Stage3 handle angle p50/p95与开门进展。
- 左右历史max stage、Stage3/4/5 snapshot可用性、goal计数。
- 最终自然评估的左右各自到达阶段、抓稳/解锁/通行结果及有效episode分母；已有逐env数据足够时再按高度分层。

先核对每字段的实际实现分母。若只有训练聚合日志，`稳定步占比 / Stage2 active占比`只能在相同窗口与权重下作为条件占比估计；它不是自然episode成功率。console四位显示零不能当精确零；snapshot日志的小数计数不是独立成功episode数。分位数的跨batch平均也不能改称整个窗口的原始 pooled 分位数。

Mean reward、entropy、吞吐、checkpoint张量有限性作为辅助读数。当前A没有数值loss导出，沿D061明确`NOT_OBSERVED`；三项已解释的penalty-driver空样本NaN不是loss。不得从其他有限值补写“loss有限/完整数值稳定”。不为本实验增设一整套训练logging框架。

本次不设看结果后才选择的“最好checkpoint”；按约定milestone报告学习过程，以6000 final的自然评估收口。B明显更早到达后段仍不意味着已通过整任务；B相近/更差时如实记录有限seed与共同随机量配对限制，不自动扩为下一组实验。

## 10. 交付与职责

Worker最终交付：实际候选/差异、真实配置与资产读回、参数配对说明、训练receipt/精确checkpoint、匹配窗口比较、final自然评估及失败/未观测事项。实施完成、进程完成和策略结论分别报告。

当前planner任务ID：`01a0af49-b5e0-75f2-8fdd-ad5c3e20744b`。新worker应报告自己的实际任务ID，而不是继续使用GPU0 worker身份。对照协调入口独立为`/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/v29_handle_ablation_team/STATE.json`，由planner维护；新worker把候选/运行证据写入自己的工作区并报告路径。GPU0 worker原任务、原STATE与其等待不受本计划影响。

**Owner补充约束（D066，适用于planner、原baseline worker及本ablation worker）**：减少相互message发送频率，非重大progress或待决策事项不轻易发送。

- 发送时机：需要验收/裁定的完整候选、需要介入的实质异常、约定重大里程碑、最终训练/评估交付。常规实现进度、文件已写、命令准备中、未变化状态只记本地。
- 同一事件合并事实、结论、证据路径和需要对方做的事，发一次；不发送“收到/已继续/仍在等待”的往返确认。无需新动作的milestone审阅存档即可，planner不另回一条“继续原计划”。
- 启动与首次初始化尽量合并报告；1000/3000/6000按已约定节点整合checkpoint/指标，不将每100保存都变成消息。需要决策或真正失败可提前通知，不等满ETA。
- 正常终止与紧随其后的已批准eval尽量合并为完整结果；底层若已发送原始terminal通知，人工不要复述同一过程状态，后续只补真正新增的结果/待决策信息。
- 已有共享文件事件监听时，不再queue同一副本。纯记录更新不发布新的消息指针、不反复唤醒worker；只有新指令、验收裁定或需要对方行动时使用通知事件。queue入队不等于即时steer，发现已有待处理同类消息时合并，不继续堆叠。

常规工程问题在已授权范围内自行处理，不把每个修复步骤转为planner请求。旧GPU0批准不授权本组，消息已收到也不等同候选已批准。
