# C002@8000：过门质量、回臂与B08下一步建议

2026-09-22 HKT。状态：**只读证据分析与运行建议，未批准或启动新训练/评估**。Owner提出两段render中的回臂与clean问题，并询问续训、B08新baseline及正式eval的优先级；本文将其“N08”按同一消息后文理解为B08。

建议先给当前8000补充以clean和手臂保持为目标的评估，再以同一8000起点、相同新增更新数做原C002与B08的并行续训对照。暂不从零启动长baseline；先区分继续学习能否改善Stage5，以及B08解除Stage0动作覆盖后的适配情况。

## 已有证据

- D077接受的8000自然64确为LEFT/RIGHT各32/32 complete。它没有把clean、持续回臂保持或跨seed泛化列为已通过。Stage5完成条件仍仅为root相对x>1.5，没有arm姿态或持续保持条件。
- 两段边界视频都是complete；RIGHT/F5/160kg/闭门器12Nm案例的release gate后身体接触力峰值为249.8533N。按各env首episode长度670/1115截取已有trace，从Stage3开始的身体接触力最大值分别0/249.8533N，越门hinge分别1.481926/1.320712rad。因此按既有clean的hinge≥1.0472rad且Stage3起身体力≤5N口径，LEFT满足、RIGHT不满足。这里只作既有口径的描述，不为v29新设放行门。
- 8000自然64的既有终态记录中，LEFT32例均有release gate事件，1例gate后身体力>5N，峰值84.2669N；RIGHT28例有该事件，其中14例>5N，峰值685.3591N，另4例事件未记录、相关值为null，不能当作零接触。LEFT另有5例记录的越门hinge<1.0472rad。以上并非对64例完整clean的重新归约；只用终态记录已足以确认质量问题不只发生在那一段视频。
- `post_release_body_contact`从逻辑gate后stage≥4累计，阈值1N；它不等于实际双指完全脱离，也不证明手臂未收回造成了身体接触。身体/arm/塔架接触应分别解释。

来源：[8000逐env记录](/home/baoquanc/workspace/DoorDog-A2_Piper/logs_eval/base_v29/push_baseline_C002_seed291/natural_resume_8000/a2_v14_per_env_records.json)、[边界render记录](/home/baoquanc/workspace/DoorDog-A2_Piper/logs_eval/base_v29/render8000_edges_20260922/delivery/a2_v14_per_env_records.json)、同目录`stage2_5_step_trace.json`及[既有clean reducer](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/v28_reduce.py:66)。

## B08和reward的实际关系

- B08只移除Stage0每步对六维累计arm target的覆盖，保留真实reset初始化。原C002@8000的Stage0姿态好，不能证明policy通过reward学会hold。
- Stage0和Stage5已有相同的六关节default-pose L1 penalty，配置权重−5.0，实际乘dt；不在训练K调节的reward名单内。目标为`[0,.10,−.10,0,−.52,1.57]`。它惩罚位置偏差，没有直接命令手臂回位或保证持续保持。
- Stage0晋级还要求每个arm joint偏差<.1rad及base command静止条件；这只约束晋级瞬间，不证明整个行走阶段持续hold。
- Stage4另有−.5的arm回位项，在release gate且非双指接触时生效。Stage5的−4 heading/−8 upright约束root，不是arm。B08没有修改上述Stage5奖励、完成条件或加入新的回臂机制。
- 现有8000与render的trace有default pose、末端姿态和累计奖励，但未开启expanded diagnostic，缺少六关节实际q/dq/target，无法直接量化回位误差与保持时间。已有`algo.config.eval.a2_diagnostic_trace_enabled`和`a2_diagnostic_reward_terms`支持这些字段，下一次评估可复用，强制动作干预保持关闭。

来源：[B08实施记录](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v29/a2_piper_v29_B08_implementation_20260921.md)、[arm奖励](/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/envs/door/door_open_a2_base.py:15963)、[Stage0晋级](/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/envs/door/door_open_a2_base.py:29732)、[Stage5完成](/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/envs/door/door_open_a2_base.py:29941)、[8000实际展开配置](/home/baoquanc/workspace/DoorDog-A2_Piper/logs_eval/base_v29/push_baseline_C002_seed291/natural_resume_8000/.hydra/runtime_config.yaml)、[既有diagnostic入口](/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/trl/trainer/ppo_trainer_a2_base_api.py:2203)。

## 建议的有界安排

1. 先评估固定C002@8000。建议新eval seeds下合计256个自然首episode、左右各128，full loader、staged/K关闭；保存实际门域、family和起点，作为后续固定比较集。两例指定边界场景另列为诊断，不混进随机总体分母。复用expanded trace记录实际arm q/dq/target及相关逐步reward。
2. 同时报告complete与clean分量；Stage0关节误差与容差内时间占比；实际松手后的回位时间、回位后保持占比/速度；Stage5身体/arm/塔架接触。分别记录逻辑release gate、失去双指接触和Stage5进入事件。无release或未回位者保留对应分母/未完成状态，不用零值填充。阈值采用现有姿态容差作为读数参照，是否构成新baseline接受条件仍由Owner决定。
3. GPU1可并行做同8000权重在B08下的短起点评估，观察Stage0动作与姿态变化。这是动作接口改变后的零更新适配测量，不能把它的失败直接判为B08训练失败。
4. 然后GPU0原C002、GPU1仅应用B08，两组均从同一8000 full checkpoint开始，新增1000更新到9000；保持seed、4096、PPO/reward及其他输入一致，按相同fresh-reset/bank重建流程启动，终点使用同一评估集。按上一轮约16.7小时/2000更新估计，1000更新约8小时/组，双卡并行；实际耗时需据启动后的吞吐确认。这是待Owner选择的预算，不是开跑授权。
5. 原C002臂回答继续训练能否改善Stage5质量；B08臂回答在相同预训练起点下解除Stage0覆盖能否适配并保持完成能力。若B08 Stage0适配良好但两臂Stage5保持仍差，应进一步检查奖励与实际松手/回位事件的匹配，再单独设计Stage5干预；不把所有问题归给B08或自动无限续训。

此对照仅识别当前预训练policy的适配，不能证明从scratch使用B08的学习难度/最终表现。若后续需要新的从零baseline或跨训练seed结论，等动作与奖励配方确定后另做固定预算的scratch训练。直接把旧8000续训与B08 scratch的差异称作B08因果消融并不成立，因为初始化与训练历史同时改变。

本次仅读取既有源码、配置、终态与两例trace；未改变reward/完成条件、未启动GPU任务、未commit/push，也未重启已关闭的D074/D067等待。
