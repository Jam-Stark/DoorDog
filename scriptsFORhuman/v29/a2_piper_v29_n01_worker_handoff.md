# v29 N01 worker team交接

2026-09-21 HKT。状态：**READY FOR WORKER TEAM；独立v28强档/减半剂量读数已回填**。依据[finalize授权](../novelty/conversations/20260921_codex_n01_finalize_and_gpu2.md)与[合力/GPU2/3/quick test新指令](../novelty/conversations/20260921_codex_n01_force_plane_gpu23_quick_test.md)。唯一当前设计合同是[N01 plan v1.2](a2_piper_v29_n01_plan.md)；保持v1.1 scratch决定，增加连续合力与双GPU安排；旧Pro和旧版只作历史/来源。

## 接手位置和授权

- 工作目录：`/home/baoquanc/workspace/DoorDog-A2_Piper_v29_n01`；分支：`codex/v29-n01`。分支已经创建，完整C002＋B05及设计文件作为未提交内容带入，继续在当前文件上工作。不要重新checkout旧HEAD或覆盖这些工作文件。
- Owner授权N01使用**物理GPU2/3**；正式Teacher安排GPU2=T_force、GPU3=T_nom。执行Main只对实际占用登记资源，不接管GPU0/1或其他任务的等待。
- 本交接包含v1.2范围内的实现、功能运行及首轮训练/评估，由新worker team接手执行。planner本轮按新指令单独完成v28 quick test；该例外不扩展为完整N01实现或正式训练监督。
- 没有Git commit/push、云发布或硬件操作授权。新产物不生成hash/SHA256；常规路径/配置记录足以本轮交接。

## 首先要知道的事实

1. 两个高层Teacher从同一随机actor/critic初始化独立训练，取消C002权重加载及T_shared。RMS/optimizer/课程均从头；冻结A2_Base腿部策略保留。C002 step6000只作历史参考或单列功能诊断，不能把其模型/数据带入scratch训练。
2. 外力走原生IsaacLab逐physics step写入；旧wrapper仍是空实现。receiver为掌部质心，`F=A(sinθ·X_G−cosθ·Z_G)`、θ∈[−90°,90°]，A是合力模长，范围按plan §3.3线性插值。每次固定t0世界方向与时程。[v28诊断](../novelty/documents/20260921_n01_force_probe_readout.md)的强档持续脱离8/11、减半0/11（宽口径11/11与1/11），两轮0 N均0/4；证明原生施力可破坏握持，不等于已验证C002+B05或恢复学习。
3. N01所有Teacher和Student共用stage-blind的12D高层命令；不能靠真值stage清arm target、强制闭爪或替Student执行pregrasp导航。外力不改变动作history。
4. 当前Student只接一台trunk/ego_camera，81D＋216×384 RGB；v29三路rig不是已实现的多路Student输入。先用固定现有仿真视路证明N01传递，不宣称硬件光学校准。
5. 现有Teacher manifest工具强制摘要字段。按Owner规则简化直接加载合同，保留明确路径、resolved config、语义维度与strict actor加载；不要为满足旧校验而生成摘要或增加兼容层。

## 最少必要分工

这里是推荐的技术边界，不是已经启动的agent。实施Main拥有scope、最终WRITE_SET、资源、Git和整合权；共享路径一个writer，独立事实可直接P2P沟通。team state只在实际多writer/资源需要时启用。

| 工作线 | 主要文件边界 | 依赖与交付 |
|---|---|---|
| 环境/控制语义worker | `gr00t/rl/envs/door/door_open_a2_base.py`；可将N01专用逻辑放入同目录一个小模块；需要时窄改`gr00t/rl/envs/base_task/staged_task_base.py`、`delta_action_base.py` | 共同动作、原生force hook、hold/loss/L0/L1、单调时间信用与局部奖励；按plan §3/5交付真实功能片段 |
| Student/标签worker | `gr00t/rl/trl/trainer/distill_trainer_a2_base_api.py`，必要的共享distill trainer调用；`gr00t/rl/scripts/validate_a2_teacher_checkpoint.py`；N01 Student观察/网络配置 | 可以并行做接口接线；最终集成依环境事件/时序。交付81D/RGB/12D、真实Student执行、shadow标签、BC mask与跨rollout连续事件 |
| 实施Main/运行负责人 | N01 overlays、launchers、resolved config与输出；共享`isaacsim.py`如需改动由Main明确交给一个writer | 配置整合、GPU2/3各自的运行与依赖、checkpoint资格、最少定向运行检查和结果汇总；不另开重复审阅队列 |

建议新增配置放`gr00t/rl/config/ablation/wbmanip/`的`v29_n01_*`系列，Student实验入口放现有`gr00t/rl/config/exp/wbmanip/`；从C002 common复用完整物理域，再明确N01的控制、课程、自然reset和Student覆盖。使用独立N01 run identity，不冒用C002 baseline cell。

runner集中在`scriptsFORhuman/v29/n01/`，仍调用现有train/eval入口及TRL trainer。该目录目前只有独立v28诊断脚本，正式N01训练命令尚未实现。输出使用本工作树`logs_rl/a2_piper_full_stage_a2_base/base_v29_n01/<run_name>/`、`logs_eval/base_v29_n01/<run_name>/`，区分Teacher、Student与诊断，各自独立目录。

## 执行顺序和最小回报

1. **先把一条功能路径做出来。** 从current source/config/API走通共同动作→有限掌部force→真实接触/滑脱→L0/L1尝试→同episode后缀。用16 env、最多64自然episode展示首次功能；不等一个“好看成功”无限复跑。
2. **先给Owner看实际片段。** Actor RGB与全景、精简tick表说明命令、force、实际q/接触、loss/新hold、目标/预算/剩余时间和执行者。能力失败如实展示；不要先写护栏、回归/变异或遗留兼容测试体系。
3. **按plan §6的依赖和固定规模执行。** T_nom/T_force各6000 PPO update、4096 env×64 tick，两组在GPU3/2并行；T_force从开始分配课程，但真实抓稳前不施力。合格新T_force后Student示范启动1000 BC update，再S_demo/S_online各2000。Teacher训练粗估45.5h墙钟、90.9 GPU·h，执行前以实际吞吐登记ETA；各组保持匹配，Student定量评估全Student执行。数字是固定结束点，不是能力保证。
4. **运行入口显式绑定GPU2或GPU3及进程内cuda索引。** 每个并行进程独立输出/receipt/tmux，使用项目已验证环境。首次实际显存/吞吐可确定并行env数，同组同步配平总交互与优化量；receipt写准确命令、输入、输出、结束点与ETA。
5. **超过30分钟使用独立tmux和run_supervisor。** 一次必要启动确认后，按真实ETA持久化一个逻辑等待，完成/失败早返回；不反复让模型轮询日志。不要重置已有等待截止，也不要处理其他任务未派给本team的事件。
6. **分层交付结果。** 功能路径、Teacher资格、Student自主能力、两组对照收益分别报告。若Teacher尚不合格，在固定运行终点交付其具体缺口；不要换成旧Teacher凑标签，不自动加seed/新训练组。

第一版不需要额外通用调度框架、snapshot/replay库、长prefix、恢复专家混合网络或整仓审计。只对实际暴露的问题作必要修正；首轮之外的范围和额外GPU按plan §9处理。

## 可直接转交的任务文本

> 你是v29 N01的实施Main，组织最少必要worker team，在`/home/baoquanc/workspace/DoorDog-A2_Piper_v29_n01`的`codex/v29-n01`分支工作。先读项目memory和`scriptsFORhuman/v29/a2_piper_v29_n01_plan.md` v1.2及本handoff，查看独立v28 quick test的readout，再实现局部L0/L1、真实掌部合力、共同stage-blind Teacher/Student接口及能力传递。Owner已授权物理GPU2/3；T_force用GPU2、T_nom用GPU3并行，其他GPU、commit/push、外部发布和硬件未授权。先展示完整C002+B05上的功能路径，再按首轮固定规模和依赖取得Teacher/Student证据。高层Teacher同一随机初始化，不加载旧高层权重/RMS或使用v28诊断数据；冻结A2_Base保留。遵守先功能、fail-fast、少量必要检查和长任务tmux/ETA逻辑等待；不重复审阅、制造测试体系或生成hash。回报实际结果、限制和剩余活动资源。
