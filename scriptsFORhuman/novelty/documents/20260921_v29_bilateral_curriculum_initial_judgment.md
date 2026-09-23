# v29 LEFT/RIGHT动态分配：初步独立判断

**最终更新（2026-09-22 11:08 HKT，D077）：** 同配方8000自然64已全部goal/complete，左右各32/32，staged load0；本轮验收关闭，无续训授权。6000→7000→8000总goal0→31→64，原左右卡点在本次8000人口中已不再阻止完成。下文保留早期checkpoint的诊断及当时建议，针对旧周期的干预不再作为当前8000继续工作的前置。[canonical最终结果](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v29/a2_piper_base_v29_C002_resume8000_final_readout_20260922.md)。

**后续证据更新（2026-09-21 20:04 HKT，D076）：** 同配方7000自然64中LEFT31/32goal且全部32到Stage5；RIGHT31例Stage3＋1例Stage2、仍无Stage4。六个可用门字段与6000逐env一致；继续原8000授权。以下6000/早期训练窗口的诊断是历史证据，不能继续当成7000当前状态；本轮未归约7000动作trace，因此不宣称开爪周期完全消失。[正式登记](/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/v29_baseline_team/D076_C002_RESUME7000_NATURAL_MILESTONE.json)。

2026-09-21 14:53 HKT；Codex v29 planner。状态：**研究建议，未批准实施**。Owner要求基于baseline与B05-ablation当前结果，独立判断领先方向是否随机，以及是否引入动态LEFT/RIGHT分配。本轮只读源码、既有日志和一手论文，保存讨论记录；未改变训练、配置、资源或原持久化等待。

**初判：动态课程有价值，但目前不建议直接采用“弱侧就增加环境数量”。更值得先研究按侧别和阶段分配练习；当前证据显示某些弱侧已有大量卡点练习，却缺乏有效突破。领先方向反转还不能归因于随机性。**

## 当前证据

一次有界日志读数于2026-09-21T14:46:34+08:00完成；沿既有read_window.py解析规则选每组100个字段完整batch，不持续查询。原始窗口、35字段均值及末值见[current_windows.json](evidence/20260921_v29_bilateral_curriculum/current_windows.json)。

| 数据组 | LEFT | RIGHT | 口径 |
|---|---|---|---|
| 原baseline，3576–3675 | Stage2 70.90%、Stage3 5.28%，无Stage4 | Stage2 70.61%、Stage3 4.95%，无Stage4 | 与B同batch、同seed的训练窗口 |
| B05-ablation，3576–3675 | Stage3 71.19%；Stage4约0.002%；Stage4可恢复env数均值2 | Stage4 52.57%、Stage5 16.60%；训练累计goal计数已非零 | 含staged reset，不是自然成功率 |
| baseline续训，6253–6352 | Stage4 54.30%、Stage5 13.18% | Stage2 35.23%、Stage3 38.28%，无Stage4 | 时间不同，只描述当前各自状态 |
| baseline6000自然评估 | 32例中27到Stage4、3到Stage5、2止Stage2；goal0 | 32例全部止Stage2；goal0 | D072已验收的64自然首episode |

B当前窗口RIGHT goal_count的时间均值为8686.398902。它是累计episode记录的状态量、包含staged reset起点，不能解释为窗口内8686个成功、成功率或自然全流程成功。B的最终自然评估尚未获得。snapshot available count也是可恢复env/槽位状态，不是独立成功轨迹数。所有训练占比为打印batch数值均值，非独立episode比例。

所以，“baseline偏LEFT、B偏RIGHT”是已观察现象；“两侧都卡Stage3、都没有下压成功”过于宽泛。A自然RIGHT在Stage2就终止，而A自然LEFT已有30/32通过Stage3。B训练RIGHT已有后段与goal记录，LEFT也有极少Stage4可恢复状态。

## 为什么不能判定为随机

两次均为seed291，但环境干预不同。B05消融一起改变几何、质量表达、抓握G、FixedJoint和相关consumer；同一个seed不使接触、轨迹或随机数消费成为相同的配对过程。现有结果不能分离：

1. 早期探索/偶然成功及PPO更新路径造成的差异；
2. 把手几何与左右操作姿态、PiPER运动学和接触条件的相互作用；
3. 一侧先获得后段snapshot，后续课程开始反复访问这些状态，对领先优势的放大；
4. 共享policy/value与全局advantage处理下的多任务相互影响。

第3项有源码上的机制基础，第1/2/4项也是可能解释；本轮未隔离因果，不把任何一项写成已证实瓶颈。更准确的描述是：领先方向依环境与训练历程而变，当前没有证据说明哪一侧始终更容易。无需先做完整多seed工程才能讨论课程，但现有单seed对照不允许宣称优势由纯随机决定。

## Stage3失败需要怎样解释

当前Stage2→3要求连续5个control步满足双指接触、足够且方向相反的squeeze等握持条件。Stage3→4要求**hinge>0.25rad且当前双接触streak满足要求**；实际配置highwater=false。它不是单独检查handle压下角。[stage gate](/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/envs/door/door_open_a2_base.py:29894)。

B窗口Stage3把手角的**逐步中位数之窗口均值**为0.758194rad（约43.44°），p95字段均值约45°。该telemetry仅在Stage3 active环境上统计，[定义](/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/envs/door/door_open_a2_base.py:19300)。结合LEFT占据大多数Stage3人口，这提示“已经压柄、但不能保持抓握并有效开门”值得优先考虑；因为缺逐侧、逐事件联合数据，不能据总体quantile确认LEFT普遍已经解闩。

最有用的下一项观察是区分：尚未压下、压下后门轴不动、门已运动但握持streak不能持续。三者对应的课程需要不同；并不需要先扩成全仓审计或测试工程。

## 动态分配的实际落点与建议

当前场景创建时固定2048 LEFT＋2048 RIGHT，各env每个rollout执行同样步数；原始env-step份额本来就各半。LEFT/RIGHT不是每次reset重新随机选择的标签。[场景构造](/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py:1813)。

现有staged reset权重为`[.5,.1,.1,.1,.1,.1]`，两组实际训练config.yaml均如此。selector先按`(stage, env)`过滤没有snapshot的阶段，再抽样stage和该env内snapshot。因此不同侧/不同env虽使用同一权重，实际可访问阶段与练习分布仍可能不同；LEFT成功状态不会自动变成RIGHT训练状态。[selector](/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/envs/base_task/staged_task_base.py:716)。PPO使用共同batch及全局advantage标准化，无现成逐侧权重；仅改reset比例不会把左右env-step从50/50变成70/30。

建议按以下优先级推进讨论：

- **先按侧别定位阶段瓶颈。** 对稳定抓握不足的一侧增加可学的Stage2接续；对已抓稳、尚不能有效开门的一侧，围绕该物理条件的Stage3接续分配练习。不能仅按总reward或最终goal给两侧评分。
- **区分访问不足与无效尝试很多。** B LEFT已经约71%时间在Stage3。简单增加LEFT环境，可能只增加同一种失败；先确认入口抓握质量、动作是否产生正确物理进展。若确实存在可学习、却访问不足的有效状态，再倾斜份额。
- **轻量动态课程候选：保留当前左右固定env组，在stage selector按side调整练习分布。** 依据最近阶段条件达成/晋级的进展，保留两侧持续练习及自然起点串联；暂不同时引入左右环境热切换、额外网络、复杂采样器或PPO loss加权。
- **比较合同保持一致。** 将来评估仍采用固定左右各半的自然起点，不按训练动态份额平均结果；主要看弱侧条件晋级与双侧自然任务表现，而非训练阶段占比上涨。若以B08新底座比较，固定/动态两组都应使用B08，避免把动作修复与采样改进混在一起。当前旧输入运行继续原合同。

这是一项可讨论的改进方向，尚不是本项目动态机制有效的实验结论。对于是否立即实施，当前更支持先获得弱侧Stage3失败类型与有效阶段暴露的简明读回，再决定是否需要调整总side份额。

## 一手研究依据

[ALP-GMM / Teacher algorithms for curriculum learning](https://proceedings.mlr.press/v100/portelas20a.html)以学习进展选取训练环境，明确考虑困难与不可学习环境；[Prioritized Level Replay](https://proceedings.mlr.press/v139/jiang21b.html)按估计学习潜力选择下一次重新交互的level，并加入久未访问level的采样。两者支持关注当前可获得的学习收益，而非单纯“失败越多分配越多”。PLR重新采集当前policy轨迹，不是把旧transition任意混进on-policy PPO。

这些论文提供课程设计原则，没有A2＋PiPER或本门任务的有效性证据；本次不直接选用其完整算法、超参数或TD-error作为本项目调度规则。

## 来源

- [原始Owner请求](../conversations/20260921_codex_bilateral_curriculum_request.md)
- [D072自然评估](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v29/a2_piper_base_v29_C002_final_readout_20260921.md)
- [D073既有匹配3000窗口](/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/v29_handle_ablation_team/D073_HA_C001_BATCH3000_MILESTONE_REVIEW.json)
- [本次日志窗口](evidence/20260921_v29_bilateral_curriculum/current_windows.json)，原log绝对路径在JSON内。
- 各侧身份、per-env bank、stage gate与PPO路径由一次只读source子任务核对；Main定向核对实际训练config.yaml、stage selector、Stage3 gate和quantile定义。本轮无新的仿真/训练、源代码修改或Git操作。

## 后续：Owner同意失败拆分，recovery bank与PPO作用澄清

2026-09-21 15:06 HKT。Owner同意先区分弱侧Stage3的未压柄、压柄后门不动、门动但握持不满足晋级三类，并询问v27 recovery bank未启用、PPO没有per-side normalization/weighting是否可能导致左右差异。本轮没有启用这些机制。

### 两种bank服务不同场景

v29现有的普通staged reset bank保存阶段入口状态，供之后从已经到达的阶段继续练习。v27 recovery路径另外处理曾在Stage3/4握稳K5、尚未过门/达到正常释放gate、随后连续失去双接触的事件；enabled时把任务stage回到Stage2继续抓握，物理现场当时不因此重新初始化。bank_reset_share>0时，另将失手时的机器人/门位置速度、关节及相关buffer保存，未来部分reset从这些现场重新练恢复。[loss触发](/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/envs/door/door_open_a2_base.py:14418)、[capture](/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/envs/door/door_open_a2_base.py:14471)、[restore](/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/envs/door/door_open_a2_base.py:14540)。

“失抓后退回抓握阶段”与“把失抓现场存起来供以后重练”是两个作用：v27 R1启用前者但bank share=0，R2另设share=.2。它们不是一份PPO旧transition回放库，也不提供下压成功动作示范。现场仍按原env保存；pending promotion只是左右各开放相同数量的记录，不复制/镜像一个side的状态到另一side，也不保证后续实际reset次数始终相同。

因此，未启用v27 recovery bank不等于v29没有阶段样本库。若Stage3一直抓着但压不下或门推不动，不会仅因此产生这个loss bank所需的失抓事件；对于曾抓稳后丢失接触的失败，它才有直接帮助重练的路径。不能把未启用列为已确认根因。

### PPO：数据数量平衡与更新影响不同

当前实际trainer为TRLPPOTrainer。它先用GAE计算`returns-values`，再对整个rollout的advantage统一减均值、除标准差；两侧没有分别归一化。[实现](/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/trl/trainer/ppo_trainer_a2_base_api.py:7367)。actor loss对非padding样本用masked_mean，没有side-specific系数，[loss](/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/trl/trainer/ppo_trainer_a2_base_api.py:6796)。这是共享任务使用普通批PPO的实现方式；[Spinning Up的PPO实现](https://spinningup.openai.com/en/latest/_modules/spinup/algos/pytorch/ppo/ppo.html)也采用批advantage统一归一化。源码没有证实开发者曾评估过并否决逐侧策略，不能替其补写历史动机。

advantage可理解为“这次动作及后续结果，比value网络对当前局面的预期好/差多少”；它不是原始reward。LEFT总reward高不自动意味着LEFT advantage更大或RIGHT动作全部受罚。固定左右各半使有效样本数量对半，普通平均loss已有隐含等样本系数；并不保证两侧advantage幅度、critic误差或梯度方向/大小相同。

per-side normalization分别调整左右advantage的尺度；如果一侧有效信号过小，可能放大它，但也可能放大噪声、改变组内相对评价。per-side weighting另外人为改变某侧loss的贡献，可倾斜优化重点；只把等量两侧各取0.5平均，在全batch层面没有新增倾斜。两者都不会创造不存在的下压成功案例，也不自动解决相互冲突的更新方向。实际逐侧advantage分布/critic误差/梯度尚未观测，当前只能列为可能机制。

引用中的非recurrent随机打乱不是当前LSTM路径：当前recurrent保留env轨迹索引顺序来对齐hidden/切片；共享batch不等于打乱时间序列。[当前分支](/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/trl/trainer/ppo_trainer_a2_base_api.py:7064)。

### 已存数据对三类失败的可辨识范围

一次窄只读核对后：A6000自然评估RIGHT32例全部max_stage=2，不能据这些样本分析RIGHT进入Stage3后的失败；这不否定训练staged reset中RIGHT确实有Stage3驻留。逐env摘要没有handle/hinge/K5联合字段。B固定3576–3675窗口只有side阶段占比与全side的角度/接触等聚合，现有目录未找到对应自然eval逐env导出；不能计算弱LEFT三类占比。未遍历1.34GB原trace或新增运行。

后续若取得新读回，关键是**同一env、同一时刻**的side、stage、handle角、hinge角/速度、current contact/hold streak以及hinge_gate/hold_gate/advance。独立max_handle和max_hinge只能补充，不能证明门开到阈值时同时握稳。handle奖励归一化尺度也不能直接当真实解闩角。优先利用已有trace schema；缺失的联合观测需在具体有界读回中补齐，不从聚合值编造比例。
