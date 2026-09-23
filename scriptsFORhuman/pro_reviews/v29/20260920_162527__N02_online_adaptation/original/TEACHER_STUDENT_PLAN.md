# Teacher／Student：信息、结构、数据与真正闭环使用

DESIGN / 未实施。不存在本次已训练checkpoint；A3000不是成熟Teacher凭证。本计划不更改原GPU0/GPU1训练。[S8]

## 1．结构收敛与公平比较

| 方案 | 本次处置 | 公平比较条件 | 采用/拒绝的理由 |
|---|---|---|---|
| 原LSTM＋改进暴露/行为支持 | **必须先做的强基线** | Teacher133D组、Student81D＋同RGB组分别比较；同history/reset、总交互与优化预算 | 可能已足够，不能把“已有RNN没学会”误作“没有记忆” |
| 同LSTM＋当前交互/动作后果辅助头 | **推荐方法组** | 相同LSTM层数/宽度/输入/视觉、数据来源、reward、候选动作空间；小头参数额外量单列 | 最小验证任务监督是否让历史被用于控制，而非为参数识别建独立网络 |
| 独立历史编码器＋小头 | 必要备选 | 输入、历史窗、训练样本/交互一致，另报计算/参数差异 | 只有actor特征受动作优化干扰、或确需跨policy复用时采用；不能靠更长历史/更多sim信息取胜 |
| 重新设计视觉融合或复杂预测网络 | 暂不选 | 相同相机信息、图像分辨率/帧率、训练量、延迟 | 先证明遮挡/视觉状态缺失或多峰后果确为瓶颈；不由UniFP/SixthSense名字决定fusion/diffusion/CFM |

Teacher与Student共享**目标语义**，不共享oracle输入或hidden。可共享部分代码和同维度的头定义，权重不要求相同；133D→81D投影不同，不能简单复制LSTM并假称可迁移。视觉特征来自现有`VisionRecurrentActor`的视觉＋proprio拼接后LSTM；无需额外再建第二个时序模块。[S2,S3]

动作后果头既要输出供训练监督，也必须接入决策：actor先产生小候选集合，后果用于选择/约束；或把候选后果摘要显式拼到现有action MLP。不能仅在actor旁边训练一个不被读取的probe，再把policy改善都解释成使用了预测。

最小先用1个MLP头预测Δθ、1个风险输出与p_useful，采用校准的分位数/概率表达不确定性。只有残差确实多峰且影响决策，再用2–3个小头/ensemble作为备选；不预付100M模型和多次生成推理成本。置信度是需验证输出，不是模型自动给出的安全证明。

## 2．Teacher训练，从暴露与行为开始

Teacher当前可以见到质量和门几何，不能将其离线重建成功叫作新能力。Teacher先在完整C002域＋同一最小行为reward支持上训练，保留自然完整episode。另有有限受控起点补足Stage3后段：可靠握持、静态抵抗closer、开向速度建立、释放风险、工作空间边界；通过部分夹持、扰动后滑移等补充失效，但必须报告全部注入人口而非只保留可恢复样本。

Oracle候选后果可用于P1判断动作选择是否有价值；不直接成为Teacher actor永久新增真值。Teacher方法组和强基线组使用相同133D输入，额外模拟变量仅作监督/critic或离线评估。训练当前头可用当前label，未来头需积累到H之后再形成标签；不能在t步action里泄漏未来state。

Teacher若在Student遇到的状态上仍不可靠，Teacher BC监督要有来源/能力标记。不能用“Teacher比Student强”的笼统信念掩盖错误动作；这些状态可保留sim后果/接触监督，并从受控可执行行为补充示范，或在单独授权后做Student RL。当前并没有任一方案已成功的证据。

## 3．Student的数据必须由Student参与产生

当前A2 DAgger路径每步查询Teacher和Student，但默认`enforce_teacher_rollout=True, ratio_teacher_rollout=1.0`；按batch前缀选择执行者，没有自动anneal和跨batch聚合池。storage记录Student hidden及Teacher动作，而不是Teacher hidden。12D BC是当前直接学习目标。[S7]

建议显式调度例：有限冷启动全Teacher，接着Teacher占比0.5、0.2，最终0；只是设计起点，不按此数字直接启动训练。执行者在episode/门域内随机抽样并平衡，不固定前缀；对切换的真实轨迹，Teacher和Student始终各自用实际观察推进hidden。

跨batch库至少以episode为单元存：
`door_id, episode_id, policy_version, executor_mask, reset_source, timestamps, student_obs81, rgb_ref, teacher_action12, executed_high_action12, effective_joint_targets, controller_state_ref, done, terminal_reason, label_validity, p_useful_label, factual_future_labels, candidate/continuation_id`。

Teacher原始133D可另存用于重新查询/teacher研究，但从Student输入管线隔离。预测头的A是实际/候选未来action，不是把历史Teacher动作当作未来Student必然执行的轨迹。已知目标缩放/命令可入Student；未核验的effort不入主输入。

聚合池按door/episode配额及最近Student版本分层，避免旧Teacher长成功片段淹没近期Student失效状态。训练可重采样稀少接触/风险，统计必须保留原始抽样概率和真实人口分母。数据收集阶段提前终止、相机缺帧、无有效接触都有记录，不等于可随意丢掉整个episode。

## 4．RNN reset、burn-in、回放与分支

真实episode reset时分别清h_T、h_S和相应低层/累积控制状态；rollout/batch边界只detach图，不强制失忆。当前mask语义先复用`Memory`/`VisionRecurrentActor`，不要再建一套不一致的done逻辑。[S3]

首版训练unroll64步与C002控制dt=.02s相配；burn-in可从16–32步试起。**没有足够历史的短episode仍训练**：使用真实已发生prefix，从reset初始hidden开始，padding只用于张量对齐，不能把padding看成真实无接触。报告短集误差/任务结果，不仅报告64步以上窗口。

对跨batch旧数据，当前网络的hidden需要从episode前缀重算；旧参数产生的hidden只能作为近似缓存，不能宣称与当前参数完全一致。零burn-in、真实前缀burn-in、长前缀三者的小对照可判别历史使用问题。Teacher动作若已在采集当时正确查询并存储，可直接用；若要事后重查或branch，则必须从真实prefix重建Teacher hidden，不能只reset后给当前孤立观察。

精确反事实branch要同时恢复机器人、door物理状态、累积arm action、base command滤波/下层历史、gait相位、stage/release gate、RNG、RNN与视觉时间戳。Isaac接触solver暖启动等状态未必能完整克隆，当前未运行验证。备选是公共前缀重放并检查branch时刻状态接近度；无法满足时只做随机factual采集，不伪称exact paired counterfactual。

## 5．训练循环伪代码

```python
# Proposed loop, not production patch. Inputs and rewards stay equal across matched groups.
D = EpisodeReplay(stratify_by=["door", "length", "contact_state", "policy_version"])
for round_id in approved_rounds:
    beta = explicit_teacher_fraction(round_id)  # finite warm start, then .5/.2/0 as a starting plan
    for env in collection_envs:
        reset_real_episode(env)
        hT, hS = zero_teacher_state(), zero_student_state()
        episode = []
        while not env.done:
            oS = get_81D_and_rgb_with_timestamp(env)       # deployment inputs only
            oT = get_teacher_133D(env)                    # privileged, never in oS
            aT, hT = teacher_step(oT, hT)                 # sees actual student-influenced history
            candidates, p_useful, hS = student_propose(oS, hS)
            aS = select_with_outcome_head(hS, candidates) # current belief, no future GT
            executor = randomized_episode_or_block_assignment(beta, env.stratum)
            aExec = aT if executor == "T" else aS
            # Small explicitly logged randomized candidate interventions only during training.
            pre = record_current_labels_and_execution_context(env)
            transition = env.step(existing_12D_interface(aExec))
            episode.append(record(oS, aT, aExec, executor, pre, transition))
        attach_factual_future_labels(episode, horizons=[.2, .5, 1.0], handle_censoring=True)
        D.add(episode)
    for batch in D.sample_prefix_sequences(include_short=True):
        h = reconstruct_burn_in_with_current_student(batch.real_prefix)
        prediction = student_forward(batch.oS, h, masks=batch.real_frame_mask)
        L = masked_BC(prediction.actions, batch.aT, teacher_label_validity)
        L += auxiliary_current_interaction_loss(prediction, batch)
        L += factual_action_conditioned_outcome_loss(prediction, batch)
        update_student(L)  # target normalization/weights tuned on dev only
# Independent evaluation: beta=0; no teacher takeover or oracle action selection.
```

具体loss初值：先把Δθ按训练集稳定尺度归一化、risk用BCE/分位数loss、p_useful用校准分类loss；辅助梯度相对BC/PPO做量级记录，避免某个单位较大而支配。权重不是已验证配方，dev上选择少量值即可，不先造大网格。对不可信Teacher动作只mask该BC项，保留该帧的sim监督与人口计数。

Student PPO finetune是备选而非必经步骤：若正确Student输入下已能预测，却被Teacher BC动作分布限制，才讨论。必须同reward、同新增交互预算比较有无辅助目标的Student。不能把Teacher在线接管率下降本身当Student独立成功。

## 6．怎样证明真的使用了信息

分别报告三层证据：后果估计误差/校准及覆盖；匹配场景下动作是否朝正确方向变化；独立闭环任务、净空/接触及姿态代价是否改善。

对同一门与起点，使用真实后果、条件均值、合理范围内同人口置换的head输出；检查release概率、base重配置、roll/pitch和门速是否变化。干预不能只做巨大噪声注入；那可能仅证明网络对OOD脆弱。另用相似当前画面但不同先前交互的配对情形，检查历史是否改变决策且改变与实际后果一致。

辅助头预测准确但行为不变：是控制连接/奖励问题，不是需要更大encoder。原LSTM任务同样好：无需独立估计模块。Teacher有效、Student只在自身轨迹失败：优先查执行分布、视觉/时间对齐、reset与标签覆盖，不直接归因“Student容量不足”。
