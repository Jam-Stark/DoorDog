---
name: base-v29-handle-ablation
status: ha_c001_d067_delivery_closed
scope: v29−B05旧Doorman-derived把手对照、6000训练与自然final64结果
last_verified: 2026-09-22
evidence: D078已关闭D067交付；6000训练及一次final64均exit0，B RIGHT32/32、LEFT0/32，A6000为0/64；源侧GPU1预约已释放
read_when:
  - 实施或接续v29旧把手对照
  - 判断B05消融范围、共同随机量与baseline版本
source_of_truth:
  - .ai/runtime/v29_handle_ablation_team/D078_HA_C001_FINAL_DELIVERY_CLOSURE.json
  - /home/baoquanc/workspace/DoorDog-A2_Piper_v29_handle_ablation/scriptsFORhuman/v29/handle_ablation/results_seed291/REPORT.md
  - scriptsFORhuman/v29/a2_piper_base_v29_handle_ablation_plan.md
  - scriptsFORhuman/v29/a2_piper_base_v29_decision_log.md
  - .ai/runtime/v29_handle_ablation_team/D071_HA_C001_BATCH1000_MILESTONE_REVIEW.json
  - .ai/runtime/v29_handle_ablation_team/D073_HA_C001_BATCH3000_MILESTONE_REVIEW.json
  - /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/v29_handle_ablation_team/STATE.json
  - /home/baoquanc/workspace/DoorDog-A2_Piper_v29_handle_ablation/scriptsFORhuman/v29/versioning/C002/VERSION_BINDING.json
supersedes: null
---

# v29 handle ablation

2026-09-22，D078已接受D067执行交付并关闭源侧共享`gpu:1`预约，任务标记completed。HA-C001在原48h内完成seed291/4096/scratch/6000/save100（43h26m56s、exit0），一次final64用精确6000 full loader、staged/K关闭（560.02s、exit0）。Main核对实际命令和终态与D067/归档一致；checkpoint有限参数及逐episode读回采用worker已保存证据，loss仍NOT_OBSERVED。完整结果见[最终报告](/home/baoquanc/workspace/DoorDog-A2_Piper_v29_handle_ablation/scriptsFORhuman/v29/handle_ablation/results_seed291/REPORT.md)，关闭记录见[D078](../../../.ai/runtime/v29_handle_ablation_team/D078_HA_C001_FINAL_DELIVERY_CLOSURE.json)。以下里程碑为历史记录，不再代表活动训练或等待。

同6000进度A为0/64；B为32/64，RIGHT32/32 complete、LEFT0/32且全部maxStage3/stage_overtime。B LEFT已压柄至约.785398rad，但最大hinge仅.069529–.121646rad、中位.097690rad，低于Stage3→4的.25rad；这定位了停滞阶段，未识别根因。本seed撤回B05整组改善RIGHT成功，不支持双侧全面改善或单独归因七族数量。A实际final64缺少完整COMMON_FIELDS，采用D067预授权independent64/null-table；最终评估未逐门完整配对，训练frame/cover/material/reset RNG也未配对。B训练average_goal_reached=.476912是最近完成episode buffer的时间平均，不是窗口独立episode成功率。A8000/D077的64/64属于另一训练进度结果，不替换本对照的A6000。

结果文档由worker报告已本地提交至`codex/v29-handle-ablation-results-seed291`，未push；candidate/baseline tags不变。开发分支`codex/v29-handle-ablation`仍在B08工作区。本D067逻辑等待已关闭，不发ACK链，不追加seed、B续训、评估、视频或硬件运行；后续须有Owner新范围。

2026-09-21 14:36 HKT，B08公共修复已同步`codex/v29-handle-ablation`开发分支工作区`/home/baoquanc/workspace/DoorDog-A2_Piper_v29_handle_ablation_b08`（本地未提交）。原`/home/baoquanc/workspace/DoorDog-A2_Piper_v29_handle_ablation`在同一版本detach并保持HA-C001源码，仍由D067任务用于训练及最终评估。不要将开发目录用于当前冻结评估；详情见[B08实施记录](../../../scriptsFORhuman/v29/a2_piper_v29_B08_implementation_20260921.md)。

2026-09-21，D073完成同seed A/B 2901–3000窗口核对（各100 batch、35字段）。B较A有更高稳定抓握/Stage2→3估计、明显压柄（handle角p50每step均值.727161rad）及RIGHT Stage4/5推进；B LEFT仍最高Stage3，双方goal仍打印0。Stage2驻留人口差异大，双指接触active条件比下降不能单项解释为退步或因果；全部结论保留量化、非pooled quantile、时间平均bank、staged reset和未配对限制。精确step3000的worker CPU读回actor/value有限，loss仍NOT_OBSERVED。D072的A6000自然0/64属于另一终点评估，不与本训练窗口混用。完整数值及等待从[D073](../../../.ai/runtime/v29_handle_ablation_team/D073_HA_C001_BATCH3000_MILESTONE_REVIEW.json)与runtime读取；原D067配方/最终64合同不变，无新裁定或ACK。

2026-09-20，D071完成D067约定1000窗口的本地核对：A/B同为901–1000、各100完整batch和35字段。B较A更早形成稳定接触与Stage2→3推进，Stage3 bank可用env由A的LEFT1/RIGHT0变为B各2048；B的handle角p95每step均值仍仅.002483rad，双方Stage4/5 bank和goal打印0。结论限于seed291撤回B05整组后的早期训练观察，不单独归因七族数量、不当作自然episode或整任务成功。Console零有量化限制、quantile非pooled、bank为时间平均状态计数，staged reset及未配对随机量限制保留。精确step1000的worker CPU读回policy20/value19个state tensors有限，loss仍NOT_OBSERVED；Main未重复载入checkpoint或运行新检查。完整数值及等待路由见[D071](../../../.ai/runtime/v29_handle_ablation_team/D071_HA_C001_BATCH1000_MILESTONE_REVIEW.json)，无新裁定、预算或ACK通知。

2026-09-20 11:25 HKT，Owner要求GPU1新增旧Doorman把手对照、独立施工plan和Git记录。D065将其界定为v29−B05整组：旧几何/质量表示/G/FixedJoint/consumer一起恢复；高度.90–1.20、B01/B04、B07、时序/奖励/PPO与v29机器人保持。该设计不单独识别“七族数量”，也不等同回退整个v28。

源C002已验收实现；321份冻结输入已物化为本地tag`v29-c002-baseline`，对应`codex/v29-c002-baseline`。独立worktree`/home/baoquanc/workspace/DoorDog-A2_Piper_v29_handle_ablation`由该tag分出`codex/v29-handle-ablation`。其后worker完成HA-C001并以`v29-handle-ablation-c001`保存，D067接受实现及有限runtime证据并批准正式GPU1训练；正式启动/进度以runtime STATE与真实receipt为准，未push。

源码确认全局`a2_v29_baseline_enabled`同时控制dynamics和B05，不能关总开关做消融。当前legacy几何与原Doorman一致，但A2 pre-B05 target与handle cap已不同于最早upstream；使用本项目旧链，避免额外回退B02负载。C002实际door metadata可配对共同域；B05尺寸/return不可充当旧尺寸/hook，未记录frame/cover/material随机量不冒充逐门完全匹配。

具体配方、授权范围、短验证、一次聚焦候选审阅与评估只从plan/D065读取；memory不是启动许可。新worker绑定、候选与等待在独立runtime STATE维护，原GPU0任务不受影响。

D066通信约束对本worker与planner同样生效：只发送重大进展/待决策/实质异常/最终交付；普通进度存档，不发收到/继续确认链，不重复文件事件与queue。完整规则从plan§10及主验收合同§6读取。

D067确认：v29总开关保留，独立B05开关关闭，原pre-B05几何/G/FixedJoint/consumer与LEFT镜像恢复；所有非B05配方保持。4096表与A实际16个共同字段一致不等同B4096已运行。实际PPO16一批及4个held-base接近/闭合案例支持操作路径，不能升级为策略或长时稳定结论。frame/cover/material/reset轨迹未配对，数值loss未观测。最终64使用实际A64共同metadata配对时须绑定独立64表，否则明确独立分布，不能截取训练表。正式运行和评估合同只从D067读取。

D068补足此前4096实际初始化缺口：正式候选运行首批原始capture证实B05关闭而v29Dynamics保留，actor/critic分别[4096,133]/[4096,138]，worker逐门共同字段及legacy样本读回0差异。此证据限定在首次初始化，不扩展为全程配对、长时数值稳定或策略成功；实际进度/ETA只从runtime读取。
