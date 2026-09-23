# 最小证据路径与源码落点

本文件是待采纳设计，不授权本地实现/新实验/GPU。原C002运行、预算与持久化等待不变。输入不含checkpoint；本次不能做policy/Isaac验证。

## P0：本次已完成的CPU模型

运行入口 `modeling/run_analysis.py`、`extra_checks.py`、`pd_envelope.py`。实际得到104方向记录、足地/腿/PD约束和夹持参数敏感性，并发现姿态收益可能被支撑/抓握淹没、被PD目标限位反转。首先将它当候选姿态/工作点的机械学证据，不移植成在线force oracle。

## P1：先判断有没有可执行且值得选择的行为

最有信息量的下一步是**同一接触起点比较“中性继续/hold重配置/有界释放”实际后果，并用oracle后果判别是否本应选择不同动作**，不是先训练force estimator。

可从12个C002门实例开始覆盖质量3×closer2×side2，分配覆盖F0–F6；不要求它成为正式统计样本规模或全部几何交叉矩阵。每门少量可靠hold/临近释放起点。当前Teacher不足以自然到达的起点用受控准备，但独立标记；不能写入自然成功率。失败准备、接触建立失败也计入准备人口。

通过现有12D接口发动作，不改物理门状态追求好结果。记录实际arm目标与误差、base命令及实际姿态、接触/滑移、门角门速、完整身体净空和通行事件。小幅姿态取±5–8°只是初值，先验证冻结A2_Base跟踪，不直接上±15°或模型边界力。

若三个行为的实际后果没有可利用差异，或oracle也不能改善选择：检查行为/rate/工作空间/gate/reward，不继续加网络。若候选能稳定地产生可区分后果，才进入P2。oracle用于诊断选动作，不作为部署输入，也不能给方法组额外动作能力。

## P2：数据与最小监督功能

采集自然＋受控起点、Teacher＋Student实际执行的数据；包含未接触/短/失败和不同policy版本。先随机化少量候选获得factual labels，后果未采到的候选保留unknown，不要求先实现高保真snapshot工程。

先用同输入的帧模型/历史摘要probe检查低成本信号，再做原LSTM强基线与同LSTM辅助头；不同输入的Teacher与Student分别比较。核对p_useful语义、Δθ预测与距离/风险定义、时间戳和删失处理。若Student在有接触历史时有效但视觉遮挡后风险不稳，优先补匹配的人口/时间对齐；若仍信息不足，简化为“保持/不释放”的保守候选集或开展专门的安全小探测设计，而不是硬输出k/d。

不规定一组未经验证的R²/毫米硬门槛。是否继续取决于：误差是否足以改变正确候选的排序；风险高低区是否校准；有效覆盖是否包括短/失败/无接触；收益是否出现在实际Student轨迹，而非只有Teacher长成功窗口。

## P3：在线使用收益，与行为和数据增益拆开

顺序对照，而非庞大矩阵：

A. 原C002可获得baseline；B. 相同行为支持＋相应暴露的原LSTM；C. B＋小辅助头及明确控制连接。A→B只能称行为/暴露组合的收益；B→C才检验辅助信息/监督的额外收益。需要进一步拆行为与暴露时，仅增加一个有针对性的对照，不预先扩充全部组合。

Teacher133D与Student81D＋RGB内分别保证输入一致；C不额外读sim effort/θdot。网络优化步数、自然/受控/branch交互步数、专家查询数与成功准备成本分别报告。oracle全真值选择只是上界诊断，不能作为公平baseline。

自然完整episode和条件化恢复/late-stage测试分别报告，最终Student必须全程自身动作，不Teacher接管、不根据oracle筛掉难样本。跨门/episode相关性采用door-level区间，不把窗口数放大成独立试验数。达到最小有效证据后才决定增加seed/样本，不先创建大型回归工程。

## 实际源码落点

| 改动 | 现有落点与用途 | 首版最小变更 |
|---|---|---|
| 当前/未来标签 | `gr00t/rl/envs/door/door_open_a2_base.py` 接触helpers约18558起，door状态观察28498起 | 增加单一label collector，输出simulation-only监督；不增加Student actor oracle |
| TCP与方向/PD模型 | 同文件 `a2_hold_apply_source_offset_to_jacobian`3898、`a2_hold_rotate_jacobian_to_root`3917、`a2_hold_absolute_target_to_cumulative_action`3935 | 复用85mm TCP与坐标合同；候选目标经累积动作转换，避免把link原点当TCP |
| body净空/需要辅助 | 同文件hold-income mask2214、grasp距离16420/16452、回臂15964/15977、回柄17591、stage条件29725起 | 统一need_assistance及完整通过语义，Stage4/5一致；保留原gate作历史日志，禁重复进度套利 |
| 现有动作执行 | `gr00t/rl/envs/base_task/a2_base.py`1174–1220；`legged_robot_base.py`1142–1159 | 不改12D布局，记录raw/cumulative/effective目标与命令；可核对实际未兑现动作 |
| 累积动作限制 | 指定审阅分支`delta_action_base.py`step；包内door step约8835起 | 保留delta scale.3、arm target scale.25、clip15、hard target clamp；不绕过控制链 |
| Teacher小头 | `gr00t/rl/trl/modules/actor_critic_modules_recurrent.py`及`memory.py` | 从现有LSTM latent接辅助头；动作读取输出/候选结果；保留原LSTM强对照 |
| Student小头 | `vision_actor_critic_modules_recurrent.py`：vision＋proprio后Memory | 不先换vision backbone；单独h_S，输出定义与Teacher一致 |
| Teacher/Student执行与数据 | `trl/trainer/distill_trainer_a2_base_api.py`340/391/417/438；`distill_trainer.py`、`data_utils.py` | 显式ratio调度、随机分配、episode聚合；保持Teacher在真实Student路径上逐步查询 |
| 配置入口 | `config/obs/wbmanip/door_open_a2_base*.yaml`；`config/exp/wbmanip/door_open_a2_base_dagger-lstm.yaml`64–65 | 不静默扩展81D/133D；新增实验配置只在Owner授权后创建 |
| C002域信息 | `env_rand/door_v29_parameters.py`、`door.py`、`handle_v29.py` | 不改变生产B05和门分布；原参数仅作分组/监督/评估 |

具体类构造、batch字典和checkpoint兼容需本地planner再次核对当前文件；本报告没有声称提交了能直接合入的生产patch。缺失在source ZIP中的`delta_action_base.py`已从指定研究分支读取；它是额外只读依据，不据此宣称整包所有依赖都已完整运行。

## 最小需要记录的指标

| 层面 | 指标与分母 |
|---|---|
| 信息 | p_useful校准、Δθ误差、风险Brier/漏报与覆盖、距离分位数覆盖；按短/失败/接触人口报告 |
| 信息使用 | 同状态候选排序正确率、hold/release改变、合理head置换下动作变化及后果；不只看feature相关性 |
| 整体任务 | 自然全任务成功/超时/失败、阶段到达；条件化测试另表；Student独立执行比例应为1 |
| 姿态/动作代价 | ∫(roll²+pitch²)dt、倾斜峰值/速率、arm目标误差/限位时间、base路径长度、任务时间 |
| 释放与净空 | 每次释放θ/θdot、身体包络剩余暴露时间、预测/实际最小净空、关向速度、门–trunk/腿非授权接触冲量、是否撞upper limit |
| 抓握与支撑 | 有效握持保持时长、滑移/失抓、恢复人口与未准备成功人口；sim effort/支撑诊断不当部署传感 |

## 继续／换方向条件

辅助估计准而不改变动作：修控制连接或reward，不扩大网络。改变动作却更危险：检查反事实覆盖、置信度/延迟、几何定义与执行误差。原LSTM匹敌：选择更简单版本，不强行保留模块。不同结构只有更长历史/更多输入时胜：先归因信息预算，不能宣传架构优越。实际姿态主要改善reach而非输出力：将N02目标转为工作空间/进展，不把它包装成force增强。

仅当主线在等输入/等数据下确有历史编码不足，才考虑独立encoder；仅当torque硬件合同确认且当前负载确实是关键未观测变量，才加入方向负载辅助；仅当纯BC在正确监督下仍阻碍Student动作分布，才讨论单独预算的闭环finetune。
