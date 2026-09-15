# P1 已批准测量合同

2026-09-08 HKT，Owner在P0验收后批准两来源各100新batches，所有GPU可用。P2未选择。

核心问题：训练是否实际获得自然评估没有展示的有余量B入口、C/D状态及对应奖励曝光？

- 来源为各自Wave2 `model_step_009000.pt`，P_S1 seed1、P_S2 seed2，native full；各1024env×64steps×100batches=6,553,600 transitions，合计13,107,200。绝对终点9100；9050/9100保存诊断checkpoint。
- 使用独立`DoorOpenA2PullP1`观测子类，所有原方法委托super一次，不修改actor/critic/observation/reward/E门/reset概率/plant/loader、RNG或训练mask。原PPO照常更新。源配置与实际resolved config逐项比较；仅输出目录、诊断类/输出字段、batch上限和保存频率等已登记差异。
- 原配置`init_at_random_ep_len=true`保留。`age_control_steps`记录reset后真实执行步数；`episode_counter`记录原计时，两者分开。full不恢复online snapshot pool或LSTM rollout历史，前100batches属于新进程初期曝光。
- 核心窗口：每10batches×side×natural(Stage0)/staged出生，覆盖全部1024env。B/C/D控制步数与实际reset数分别作分母。记录联合ready条件、ready episode数与连续窗口；窗口内最长与跨窗口同episode最长分开。
- 上游：actual q与刚完成physics step的target按stage逐步聚合；每episode首次控制步、Stage0/1→2转段、各关节首次恢复margin≥0.07和六关节min首次恢复均保存q/target/margin/counter。reset初始q单列，loaded时已高margin不算后续恢复。近限位且target指向限位外的步数逐关节统计；默认j2/j3近限位、持续向外发命令和后续未恢复分开解释。
- release/clean/E2–E7/persistence25/frame首次新发生计数与flag真控制步数分开。loaded snapshot继承flag记录在reset文件，不计为新事件。ready暴露episode按窗口去重，跨窗口求和不作为全程唯一episode数。
- reset记录真实selected stage/sample、可用性mask、loaded phase/q/margin及继承flags，不创建requested-stage。snapshot在真实写入完成处记录stage/slot/phase/kind/margin；累计写入、有效库存、实际加载分开。Stage0初始化库存不冒充运行写入。
- 完整raw/scaled reward按side/origin累计非零、正负收益与步数；后段v6 reward按当前源码公式保存对应active mask步数。mask存在不等于reward非零。不开启eval/render，不用0.0000推断绝对零。

每格输出：resolved_config.yaml、config_comparison.json、run receipt、exposure_by_side_origin_window.jsonl、压缩upstream/reset/snapshot记录、exposure_metadata.json、9050/9100 checkpoint、退出码。统一生成P1_EXPOSURE_REPORT.md。

初始输出根`logs_rl/a2_piper_pull_v7/p1_20260908/`；GPU1=P_S1、GPU2=P_S2，各独立tmux。约1.2 GPU小时为旧速度估计而非保证。禁止重复已执行batches来补测；若真实异常或Owner停止则保留预算消耗和失败记录，不新增fallback。达到9100停止，无E7也不延长，不推广诊断checkpoint，不运行额外natural eval。
