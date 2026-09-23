# 一手文献、代码与源码证据索引

访问与审阅日期：2026-09-20。文献使用指定版本HTML，未把论文摘要/历史novelty当结论。以下为可访问链接；仓库行号以本次冻结输入为准，动态分支以后可能变化。没有生成哈希清单。

## P1．UniFP

[论文v2](https://arxiv.org/html/2505.20829v2)；[作者项目](https://unified-force.github.io/)；[官方代码](https://github.com/unified-force/UniFP)。准确题名：*Learning a Unified Policy for Position and Force Control in Legged Loco-Manipulation*；Peiyuan Zhi等；2505.20829v2，2025-10-04。

核对§3.1–3.3、§4与附录。它连接历史状态/外力估计与低层力位命令控制；上层视觉模仿是另一层，不等于低层架构。当前/历史输入包括动作与命令，H=32；估计不是门释放的反事实预测。低层输出PD关节目标，训练有外力激励；B2-Z1与G1的任务/末端条件不同。

**对本项目的推论**：可以学习“估计服务具体控制”的设计，不能假设冻结A2_Base已具备它的力命令响应。静态握柄/快速甩门与其简化接触假设不完全相同；不从“用了视觉模仿”推导必须换diffusion。未从已读原文获得可直接迁移的端到端硬件控制延迟保证。

实际读取[README](https://github.com/unified-force/UniFP/blob/main/README.md)及[环境配置前100行](https://github.com/unified-force/UniFP/blob/main/legged_gym/envs/b2/b2z1_pos_force_config.py)。README区分已发布训练与尚列TODO的sim2real/其他管线；没有运行其代码。项目页在本次浏览解析中没有可读正文，入口已核对，不假称读到其全部网页内容。

## P2．SixthSense

[论文v1](https://arxiv.org/html/2605.01427v1)；[作者Haodong Zhang主页](https://0aqz0.github.io/)。题名：*SixthSense: Task-Agnostic Proprioception-Only Whole-Body Wrench Estimation for Humanoids*；Xingzhou Chen等；2605.01427v1，2026-05-02。作者主页可核对论文身份；本次未找到可核验的专属官方代码入口，不断言不存在。

核对§IV、§V-A/B/F：q、qd、归一化torque、IMU输入；50帧/50Hz对应同窗接触序列；CFM重建接触区域与wrench。文中实机配置约100M、10 refinement，报告0.5s forward；力传感器用于实机真值核验。它不是“给定未来动作的门趋势预测”。

**对本项目的推论**：当前Student没有已确认torque合同，不能照搬输入；0.5s远大于C002单个20ms tick，但不能擅自再乘10推断5s。窗口末端估计也受推理延迟，窗口较早帧还可能利用后面的观察；必须区分同窗重建与因果、及时的在线输出。接触多解应体现不确定性，但不推出当前任务必须使用全身场或CFM。

## P3．DAgger

[Ross、Gordon、Bagnell，2011，PMLR原文入口](https://proceedings.mlr.press/v15/ross11a.html)：*A Reduction of Imitation Learning and Structured Prediction to No-Regret Online Learning*。借鉴的是学习者诱导状态分布与聚合数据，不是把默认全Teacher采样叫作充分覆盖。当前A2的teacher查询/执行比例基础已存在，但跨batch库、明确annealing与相关记忆处理是本报告提出的新增设计。

## P4．执行器与接触可行性

[Orsolino等，arXiv:1712.06833](https://arxiv.org/abs/1712.06833)，*Application of Wrench based Feasibility Analysis to the Online Trajectory Optimization of Legged Robots*；[作者机构记录/期刊DOI入口](https://www.research.ed.ac.uk/en/publications/application-of-wrench-based-feasibility-analysis-to-the-online-tr/)。其执行器wrench可行集与接触约束相交的思想支持本次分层计算；本次没有声称实现了该论文完整优化器，实际程序是明确的小型URDF/Jacobian/LP实现。

## 少数替代方案如何挑战初判

“已有LSTM＋更好暴露”挑战独立估计器必要性；“同LSTM辅助头”挑战重型历史/生成网络必要性；“当前可达/PD模型＋任务后果”挑战全身wrench必要性；“随机factual动作数据”挑战必须先建完美反事实快照的工程前提。它们是本报告设计推论，不冒充上述论文已经在C002验证的结论。

## SOURCE索引

所有包内路径均相对source ZIP根目录；runtime路径相对brief ZIP。源码摘录另见SOURCE_EVIDENCE.md。

### S1．本次本地事实与发布身份

[LOCAL_FACTS，指定审阅分支](https://github.com/Jam-Stark/DoorDog/blob/codex/v29-n02-pro-20260920/scriptsFORhuman/v29/pro_handoff/20260920_n02_online_adaptation/LOCAL_FACTS.md)。通过GitHub connector实际读取；R2三ZIP、顶层index/handoff/manifest从用户唯一Drive目录读取。三ZIP条目数332/45/19、字节数与manifest相符，CRC检测均通过。没有要求远端同名tag。

### S2．观察

`gr00t/rl/config/obs/wbmanip/door_open_a2_base.yaml`、`door_open_a2_base_dagger.yaml`；`gr00t/rl/envs/door/door_open_a2_base.py`28498–28542。133D Teacher与81D＋RGB Student不同信息合同。

### S3．记忆/网络

`gr00t/rl/trl/modules/actor_critic_modules_recurrent.py`、`vision_actor_critic_modules_recurrent.py`、`memory.py`；`config/exp/wbmanip/door_open_a2_base_dagger-lstm.yaml`；runtime/config.yaml。两层256 LSTM；Student视觉拼接后进入Memory；下层A2历史独立。

### S4．C002门域/B05

`gr00t/rl/isaac_utils/playground/env_rand/door_v29_parameters.py`、`door.py`529–568、`handle_v29.py`195–240；`gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py`。数值分布、native drive/friction与B05 G坐标语义。

### S5．动作/TCP/力语义

`envs/base_task/a2_base.py`1174–1220；`envs/legged_base_task/legged_robot_base.py`1142–1159、1781起；`envs/door/door_open_a2_base.py`3880–3953、18558起及28498起。85mm TCP、PD估计不等于硬件力矩、12D高层位置/姿态链。

### S6．reward与阶段

`door_open_a2_base.py`2214起、15964–16011、16420–16460、17591–17609、17847起、17901起、29725起；`brief/evidence/C002_runtime/config.yaml`实际reward_scales。不能从函数存在推断scale已启用。

### S7．蒸馏与storage

`gr00t/rl/trl/trainer/distill_trainer_a2_base_api.py`330–480；`distill_trainer.py`、`data_utils.py`；`config/exp/wbmanip/door_open_a2_base_dagger-lstm.yaml`64–65。执行选择/Teacher查询/hidden/done与BC接口。

### S8．已存runtime边界

`evidence/C002_runtime/D061_INITIALIZATION_AND_LOSS_OBSERVABILITY.json`；`D064_BATCH3000_MILESTONE_REVIEW.json`；A1000/A3000 readout/console与config。复用已存材料，无新轮询，未访问其中机器绝对路径的checkpoint。数值来自D064 console_comparison，不自行重算自然episode率。

### S9．历史参考

history包的 `scriptsFORhuman/v27/v27_shadow_estimator.py`、`a2_piper_base_v27_shadow_estimator_readout_20260907.md`、`historical_shadow/endpoint_result.json`；`20260917_v28_closure_N01_N02.md`、`20260918_n02_regrasp_rebound_discussion.md`。在形成任务/源码/模型判断之后阅读相关段落。未逐字审阅全部旧conversations，不将它们的指令/排期用作本轮权威。

### S10．额外补读的累积动作依赖

[delta_action_base.py](https://github.com/Jam-Stark/DoorDog/blob/codex/v29-n02-pro-20260920/gr00t/rl/envs/base_task/delta_action_base.py)，通过指定分支读取1–210行。source ZIP不含该文件，已如实补读；runtime确认delta_action_clamp_to_dof_limits=true、delta_action_clip15、delta_scale.3。当前branch文件用于核对接口，不声称它已在云端和整套冻结C002运行过。

## MODEL与未知证据

MODEL文件为本回包`modeling/`及`results/`，不来自论文或历史训练结果。模型包含URDF质量/惯量与配置限矩，不含已确认实机持续能力。所有姿态方向结论仅适用于所列工作点、坐标、约束。

未运行：Isaac物理跟踪、原policy、Student闭环、硬件。未完成：全B05真实接触wrench可行集、mesh碰撞、动态步态支撑、非零速度完整Coriolis/长期甩门仿真、硬件电流/torque同步校准。原USD为输入资源，未由物理引擎加载核对其运行惯量/碰撞等价性。
