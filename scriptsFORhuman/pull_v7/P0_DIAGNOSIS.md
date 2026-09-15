# Pull v7 P0：入口轨迹与联合 readiness 诊断

2026-09-08 HKT。**P0 离线分析已完成；建议申请 P1 原配置曝光诊断，暂不提出 P2 处理变量。** 当前 margin 缺口在首次可观测 Stage2 已存在，且四侧没有“只缺 margin”的同一步窗口。当前自然轨迹无法提供有余量的 B 入口；训练是否通过 staged reset 获得不同入口仍缺直接计数。不能据此恢复 scale30、改 reset ratio 或否定 plain LSTM。

本报告是既有 runtime artifact 的离线再分析（CPU 执行完成），源码/配置为 INSPECTED；不是新增策略实验、v7 能力验收或 promotion。0 新训练 batches，Isaac Sim/GPU eval/render/训练全部 NOT_RUN。

## 1. 输入、总体与时间基准

| 总体 | 能力分母 | 详细轨迹episode / rows | E2/E3/E4/E5 | E6/E7 | 无详细trace env |
| --- | --- | --- | --- | --- | --- |
| P_S1 LEFT | 64 | 64 / 46022 | 64/64/64/64 | 0/0 | 无 |
| P_S1 RIGHT | 64 | 62 / 44389 | 62/62/62/62 | 0/0 | 21,63 |
| P_S2 LEFT | 64 | 64 / 46492 | 64/64/64/64 | 0/0 | 无 |
| P_S2 RIGHT | 64 | 64 / 46443 | 64/64/64/64 | 0/0 | 无 |
| r6an RIGHT | 16 | 10 / 7675 | 10/10/10/10 | 1/1 | 3,5,6,11,13,15 |

当前四侧共 256 个首 episode，254 个有 Stage2–5 详细轨迹。P_S1 RIGHT env21/63 在 Stage0、episode counter250 stage_overtime，E1–E7 均缺失；它们继续占能力分母64，不能混入254条条件轨迹或被当成零margin观测。旧文件是一次16-env natural render，只有10个进入详细trace；6个上游失败也保留。旧 strict-natural64 的 E5/clean/frame/E6/E7=41/5/3/2/1 是独立历史总体，见 [PULL_V6_1_P_POPULATION_REPORT.md](/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/scriptsFORhuman/pull_v6_1/PULL_V6_1_P_POPULATION_REPORT.md:15)；本报告没有用render16替代它，也没有重新扫描该历史总体。

- `trace_step` 是文件的零基 evaluator step；`episode_counter` 是 `episode_length_buf`。这些首episode里相差1；事件 `first_event_step` 采用后者，不能混用。control_dt=0.02s，200Hz physics/decimation4；窗口长度为控制步，端点包含，秒数=长度×0.02。
- CSV保留首次观测、首次低margin、E2/E3/E4/E5、B捕获、E5+25/+50/+100、首次ready/clean、terminal和最后观测。不存在或未存的时点为空，不取邻近行。terminal事件来自metrics；没有expanded trace的terminal仍保留counter/stage，关节和动作缺失。JSON保存每episode事件、所有观测范围以及逐步E5后窗口。
- 有详细trace的264个episode内控制步缺口均0，事件E2–E5对应行均找到；无trace的8个episode是明确缺失。当前出生记录64/侧且Stage0；旧文件没有独立出生row，natural来源由旧eval保存配置和运行日志支持，不能伪造出生证据。
- trace在physics刷新、事件/状态更新、reward计算之后，reset与stage advancement之前采集。raw action来自pre-step observation；target是刚完成的physics step使用值。base command前三项是body-frame vx/vy/yaw-rate，root位移为world axes相对门，不能逐轴当成同一坐标系。
- 当前Stage2→3由grasp_completion控制，E2仍是tensile proof事件，可以在Stage3形成。hard_gate E3为latch threshold+stable contact，E4要求prior E2、hinge>0.25、stable contact与panel clear；E5要求已锁存aperture（stable contact且hinge≥send threshold）与panel clear并遵循E4前置。E3并不保证晚于E2，表内保留实际时间，不按事件编号重新排序。

## 2. A：margin缺口、关节target与base运动

**254/254可观测当前episode在首次Stage2 row已低于0.07，整个已存轨迹也从未达到0.07。** 因此缺口不是只在E5后的opening才形成；上游首次出现时刻全部左截断，Stage0/1的实际关节轨迹无法观察。E3/E4处已存在近限位姿态。不能用出生Stage0行补造关节值，也不能据此定位更早的策略更新原因。

| 总体/时点 | n | margin中位数 | 最小margin关节计数 | j3实际/target中位(rad) | j5实际/target中位(rad) | clearance中位(m) |
| --- | --- | --- | --- | --- | --- | --- |
| P_S1 LEFT first_observed | 64 | -2.60025e-05 | {"arm_j3": 62, "arm_j5": 2} | 7.65824e-05/3.75 | -1.21989/-2.35613 | 0.255356 |
| P_S1 LEFT E3 | 64 | -5.98927e-05 | {"arm_j3": 64} | 0.000177702/3.75 | -0.893735/-0.906289 | 0.0931922 |
| P_S1 LEFT E4 | 64 | 1.64208e-05 | {"arm_j3": 64} | -4.87206e-05/3.75 | -0.833872/-0.790129 | 0.104629 |
| P_S1 LEFT E5 | 64 | -3.17396e-06 | {"arm_j3": 64} | 9.41715e-06/3.75 | -0.75999/-0.675593 | 0.0168513 |
| P_S1 RIGHT first_observed | 62 | -2.45681e-05 | {"arm_j3": 62} | 7.28935e-05/3.75 | -1.21989/-2.20329 | 0.258033 |
| P_S1 RIGHT E3 | 62 | 1.14635e-05 | {"arm_j3": 55, "arm_j6": 7} | -6.26182e-05/3.75 | -0.889247/-0.918379 | 0.0763284 |
| P_S1 RIGHT E4 | 62 | -0.00011811 | {"arm_j5": 59, "arm_j3": 3} | -5.1383e-05/3.75 | -1.22029/-2.01637 | 0.0925823 |
| P_S1 RIGHT E5 | 62 | -0.000169214 | {"arm_j5": 62} | 3.33206e-05/3.75 | -1.22041/-3.2278 | 0.0871515 |
| P_S2 LEFT first_observed | 64 | -2.94059e-05 | {"arm_j6": 9, "arm_j3": 55} | 8.13506e-05/1.07325 | -1.21988/-1.40557 | 0.205294 |
| P_S2 LEFT E3 | 64 | -4.3651e-05 | {"arm_j5": 39, "arm_j3": 25} | 8.87829e-06/2.82739 | -1.22007/-3.25 | 0.102004 |
| P_S2 LEFT E4 | 64 | -8.05186e-06 | {"arm_j5": 40, "arm_j3": 24} | -4.68744e-05/3.75 | -1.22/-3.25 | 0.103993 |
| P_S2 LEFT E5 | 64 | -3.8743e-05 | {"arm_j5": 41, "arm_j3": 23} | -2.8302e-05/3.75 | -1.22007/-3.25 | -0.0454857 |
| P_S2 RIGHT first_observed | 64 | -2.88946e-05 | {"arm_j3": 64} | 8.57302e-05/1.03727 | -1.00925/-1.06704 | 0.220522 |
| P_S2 RIGHT E3 | 64 | -2.96876e-05 | {"arm_j6": 12, "arm_j3": 14, "arm_j5": 38} | -0.000121392/2.92809 | -1.22/-3.25 | 0.0794343 |
| P_S2 RIGHT E4 | 64 | -0.000101865 | {"arm_j5": 46, "arm_j3": 17, "arm_j6": 1} | 8.36429e-05/3.75 | -1.22021/-3.25 | 0.063298 |
| P_S2 RIGHT E5 | 64 | -0.000119078 | {"arm_j5": 47, "arm_j3": 17} | 0.000191759/3.75 | -1.22025/-3.25 | -0.00943457 |
| r6an RIGHT first_observed | 10 | 0.132284 | {"arm_j6": 10} | -0.949353/-1.10929 | -0.496912/-0.589399 | 0.34243 |
| r6an RIGHT E3 | 10 | 0.0370916 | {"arm_j6": 8, "arm_j2": 2} | -1.78014/-2.0227 | -0.0299326/0.0416105 | 0.341498 |
| r6an RIGHT E4 | 10 | -6.63096e-05 | {"arm_j6": 10} | -2.32145/-2.17525 | 0.487274/0.598587 | 0.369917 |
| r6an RIGHT E5 | 10 | 0.103148 | {"arm_j6": 4, "arm_j3": 6} | -2.62131/-2.55237 | 0.698682/0.69546 | 0.308801 |

当前主要是arm_j3接近上限0rad、arm_j5接近下限−1.22rad；最小值的关节会随轨迹换位。P_S1 LEFT的E5最小关节64/64为j3；RIGHT为j5 62/62；P_S2 LEFT j5/j3=41/23，RIGHT=47/17。j3 target常为+3.75rad而实际q约0；P_S2 j5 target常为−3.25rad而实际q约−1.22。它们是trace中的实际Articulation target，不是用raw action推测出来的target，也不是有余量的实际关节姿态。CSV同时保留六关节q/target、raw/applied arm/base动作及实际base速度。

| 总体 | paired n | E3→E5 root相对门位移中位 x/y/z(m) | E5 physical base cmd中位 vx/vy/yaw |
| --- | --- | --- | --- |
| P_S1 LEFT | 64 | 0.530841, -0.601082, -0.014917 | -0.338989, 0.140984, -0.161861 |
| P_S1 RIGHT | 62 | 0.497745, 0.662487, -0.0117438 | -0.5, 0.278458, 0.300806 |
| P_S2 LEFT | 64 | 0.555554, -0.497023, -0.0152584 | -0.495626, 0.414026, 0.068965 |
| P_S2 RIGHT | 64 | 0.391335, 0.601584, -0.00990446 | -0.5, -0.207603, 0.5 |
| r6an RIGHT | 10 | 0.654853, 0.538184, 0.00905038 | -0.165265, -0.474928, 0.149707 |

以上是同episode E3→E5的配对位移摘要。当前opening伴随base向门外+x退移与左右不同的横移；旧轨迹也退移，但旧j3在负角区域运动、j5没有当前同样的下限target模式，E5 clearance更大。能支持的是联合轨迹差异，不能把base某分量或单关节target认定为已证明的因果干预。

三个限位口径必须分开：

1. release margin：六个实际q，逐关节`min((q-l)/(u-l),(u-q)/(u-l))`再取最小，l/u来自A2 robot配置的dof_pos_lower/upper_limit_list；无clipping。j3为[−2.967,0]、j5为[−1.22,1.22]。重算与原trace最大绝对误差当前≤1.70e−8，旧≤3.66e−8。
2. `arm_soft_limit_normalized_margin`：trace原样保存的IsaacLab articulation 0.9 soft interval；不是release门，也不是reward实际边界。
3. `limits_dof_pos` penalty：simulator hard interval按当前0.95缩窄，六非夹爪关节越界量求和，单位rad，scale−5。CSV另列`*_penalty095_margin`与`*_penalty095_violation_rad`用于区分边界；它是离线重算的penalty几何量，不冒充逐步reward支付。源码见 [door_open_a2_pull.py](/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/gr00t/rl/envs/door/door_open_a2_pull.py:5815)、[door_open_a2_base.py](/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/gr00t/rl/envs/door/door_open_a2_base.py:7071)、[door_open_a2_base.py](/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/gr00t/rl/envs/door/door_open_a2_base.py:11981)。

## 3. B：单项ever、同一步联合与连续窗口

独立条件为pivot_valid、双指接触、panel_clear、handle-send-Y≤0.06m、pivot displacement≤0.15m、累计arm tangent share≥0.6、hinge≥1.134464rad、速度≥0.15rad/s、clearance≥0.02m、margin≥0.07。handle_crossed为锁存历史，不代替当前Y门。几何联合要求这些条件同一步全真；actual ready还要求C。E5当步捕获B不能同时转C（`~capture`）；后续C失去pre-ready可退回B。ready不要求frame passage/crossing。见 [door_open_a2_pull.py](/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/gr00t/rl/envs/door/door_open_a2_pull.py:5786)、[door_open_a2_pull.py](/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/gr00t/rl/envs/door/door_open_a2_pull.py:5920)。

| E5后单项ever | P_S1 L /64 | P_S1 R /62 | P_S2 L /64 | P_S2 R /64 | 旧 /10 |
| --- | --- | --- | --- | --- | --- |
| pivot_valid | 64 | 62 | 64 | 64 | 10 |
| bilateral | 64 | 62 | 64 | 64 | 10 |
| panel_clear | 64 | 62 | 64 | 64 | 10 |
| handle_y | 64 | 62 | 64 | 0 | 10 |
| pivot | 64 | 62 | 64 | 64 | 10 |
| share | 58 | 21 | 64 | 36 | 10 |
| hinge | 1 | 61 | 45 | 47 | 10 |
| velocity | 2 | 6 | 11 | 0 | 10 |
| clearance | 37 | 62 | 0 | 63 | 10 |
| margin | 0 | 0 | 0 | 0 | 10 |

| 总体 | E5后记录步数 | 几何联合episode/steps/最长 | actual ready episode/steps/最长 | 仅缺margin episode/steps/最长 |
| --- | --- | --- | --- | --- |
| P_S1 LEFT | 11377 | 0/0/0 | 0/0/0 | 0/0/0 |
| P_S1 RIGHT | 12439 | 0/0/0 | 0/0/0 | 0/0/0 |
| P_S2 LEFT | 15457 | 0/0/0 | 0/0/0 | 0/0/0 |
| P_S2 RIGHT | 13845 | 0/0/0 | 0/0/0 | 0/0/0 |
| r6an RIGHT | 4983 | 1/1/1 | 1/1/1 | 0/0/0 |

| 总体 | E5后同一步通过条件数: 控制步数 |
| --- | --- |
| P_S1 LEFT | {"4": 6714, "5": 3944, "6": 717, "7": 2} |
| P_S1 RIGHT | {"3": 13, "4": 2075, "5": 3372, "6": 6132, "7": 847} |
| P_S2 LEFT | {"3": 1, "4": 1211, "5": 7566, "6": 6540, "7": 139} |
| P_S2 RIGHT | {"3": 1352, "4": 10550, "5": 1848, "6": 95} |
| r6an RIGHT | {"3": 52, "4": 169, "5": 781, "6": 527, "7": 1554, "8": 1688, "9": 211, "10": 1} |

**当前四侧所有“仅缺某一个独立条件”的episode、步数与最长窗口均0；“其余全过仅缺margin”同样为0。** JSON为每个条件分别保存episodes_ever、steps、longest及每episode连续窗口；CSV每个观测时点保留条件bool与通过数。单项ever不能解释为联合可达。P_S2 LEFT还有全程clearance不足；RIGHT的Y门和速度门全程未过。负clearance只是trunk到门板线段的几何包络距离减门板半厚与footprint半径，不等同真实碰撞。

旧render的联合/ready只有env14的一步：episode counter357（trace356），持续0.02s，下一步clean。旧“仅缺Y”10个episode/152步/最长19步，“仅缺pivot”6个/53步/最长13步，“仅缺bilateral”1个/6步/最长6步；其余单缺为0。这些是全E5后**几何条件**窗口，可包含释放后状态，不能自动称为可再次转C的窗口；actual ready单独按原phase/state计数。当前全部E5后处于B，无该阶段混淆。

## 4. C：B入口与snapshot机会

当前B捕获均与E5同counter，254/254 margin<0.07，**未观察到有余量的B入口**；不是“已观察到好入口但未被采集”。源码中，banks off仍会在E5 pending、stage=SWING且pivot_valid时调用普通online snapshot。CSV的B_capture各行具有该状态机会，但没有实际snapshot写入计数/slot/加载记录，不能把机会写成已证明写入或训练采样。

ready snapshot要求pending、C、current ready和prev ready；clean后的D1/D5/D25还有无接触、persistence income等条件。当前自然trace没有ready/clean，所以没有相应状态候选。near-C capture mode=none。源码：[door_open_a2_pull.py](/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/gr00t/rl/envs/door/door_open_a2_pull.py:6044)–6118；真正buffer写入在 [staged_task_base.py](/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/gr00t/rl/envs/base_task/staged_task_base.py:572)。这些条件用于解释当前采集机会，不把当前源码反推成旧成功运行的exact snapshot历史。

## 5. D：训练曝光能证明什么、缺什么

两份Wave2 resolved config及各自step9000 checkpoint均已只读核对。当前与旧r6an保存配置的71个非零reward scale相同，均未启用workspace-progress；这不是整个历史reward函数语义相同的证明。当前ratio保持[0.5,0.1,0.1,0.1,0.1,0.1]、1024env、每batch64控制步、两项外部bank关闭。

| 证据 | P_S1 | P_S2 | 能说明/不能说明 |
| --- | --- | --- | --- |
| checkpoint Stage4 active fraction | 0.615234375 | 0.6171875 | 保存时的诊断聚合，非累计B/C/D曝光 |
| isaac.log末面板Stage4 | 0.6223 | 0.6163 | 时间聚合且四位小数，不能当实际reset比例 |
| checkpoint raw-open fraction | 0.001953125 | 0.005859375 | 存在动作聚合读数，不定位v6 ready或自然/staged来源 |
| checkpoint env_state_dict | 150 keys | 150 keys | log_dict及样本/掩码诊断，非完整physics/reset pool |

`env_state_dict`中没有stage_buf、staged_reset_num_samples、v6 subphase/events、snapshot pending/data或实际reset source/slot。不能从诊断名里的“release gate”认定它等于v6联合ready；不能从四舍五入0.0000推断后段训练从未发生。现存日志/checkpoint不能还原：实际reset数与选中stage/sample、B/C/D控制步数、ready episode/步数/连续窗口、snapshot累计写入与有效库存/加载、分side和natural/staged来源的后段reward raw/scaled激活与正负收益。

`_sample_reset_stages`直接按每env库存可用性mask配置权重后multinomial，不存在requested-stage再reject的步骤。ratio、实际reset比例和控制步曝光有不同分母。full loader恢复policy/critic/optimizer/scheduler/TrainerState及保存诊断；online样本在新进程重新积累，不是physics、bank和LSTM history的exact restore。见 [staged_task_base.py](/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/gr00t/rl/envs/base_task/staged_task_base.py:732)、[legged_robot_base.py](/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/gr00t/rl/envs/legged_base_task/legged_robot_base.py:1792)、[ppo_trainer_a2_base_api.py](/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/gr00t/rl/trl/trainer/ppo_trainer_a2_base_api.py:5246)。

## 6. E：旧成功与失败参照

| 旧env | E7 | E5 trace_step | margin | clearance(m) | ready steps / longest |
| --- | --- | --- | --- | --- | --- |
| 0 | 0 | 398 | 0.0548552 | 0.285187 | 0/0 |
| 1 | 0 | 410 | -3.21587e-05 | 0.333157 | 0/0 |
| 2 | 0 | 308 | 0.0967173 | 0.324017 | 0/0 |
| 4 | 0 | 439 | 0.123624 | 0.292035 | 0/0 |
| 7 | 0 | 317 | 0.124977 | 0.292307 | 0/0 |
| 8 | 0 | 398 | 0.111048 | 0.310882 | 0/0 |
| 9 | 0 | 378 | 0.107817 | 0.268616 | 0/0 |
| 10 | 0 | 337 | 0.0774668 | 0.318542 | 0/0 |
| 12 | 0 | 309 | 0.09848 | 0.30672 | 0/0 |
| 14 | 1 | 318 | 0.121978 | 0.315599 | 1/1 |

旧16总体内：10到E5，8个E5入口margin≥0.07，其中7个仍失败；其余6个未进入详细trace。10个E5到达者在E5后都曾单项达到margin，但只有env14形成ready/clean/E7。这排除了只看winner的解释：好margin入口有帮助的机制关联，并不等于充分条件。

旧env14在trace318进入B时margin=0.121978、clearance=0.315599m；trace356 ready时0.102693/0.296395m；trace357 clean时0.105285/0.294199m。旧轨迹在更早阶段也会短时低margin（env14首次低于门槛counter68），随后在E5入口恢复余量；当前则在整个可观测区间持续缺margin。这个差异比“旧从未靠近限位”更准确。

旧learned override是有效策略组成部分，成功是有效机制参考。旧训练是r6am seed0 step25→r6an seed3、256env、24s、99%Stage4/专用bank与冻结carrier；旧render为16env Stage0 natural、36s/长Stage5。当前是双侧plain LSTM、1024env混合reset、全参数更新。policy、scene、history与训练来源都不同，不构成matched causal comparison；本次未加载旧policy到当前训练，也未将任何来源标记为Teacher。r6r scale4独立结果仍UNRESOLVED，不重跑；撤回的scale30建议不恢复。

## 7. 一次集中裁决：申请P1，不启动

**建议P1，暂不准备P2处理变量。** P0已排除“只差一个E5后margin条件”的简化解释；上游近限位target、运动和多门条件存在描述性差异，但尚无实际训练曝光证据支撑选择单一reward或采样干预。最关键缺失测量是：**按side、真实出生来源分层的训练rollout B/C/D及联合ready曝光，并关联实际snapshot写入/加载。** 以下为同一曝光测量的具体接线，不是多轴扫描。

| 真实执行位置 | 直接计数 | 分母/时序 |
| --- | --- | --- |
| staged_task_base `_sample_reset_stages`返回与`reset_envs_idx`选sample后（622–627、732–782） | 配置权重、有效性mask、实际stage/sample；加载后subphase/margin | 实际reset数；不创造requested-stage |
| `_take_snapshot_of_buffered_states`完成写入（572–606） | E5/ready/D原因、累计写入数、有效槽位数与实际加载数 | 写入数≠环形buffer库存；保持原采样，不额外随机抽样 |
| DoorOpenA2Pull `_after_reward_components`（6839–6904）与现有control-step telemetry（8408–8427） | B/C/D、ready步数/episode/连续窗口、raw/applied开爪、release/clean/persistence25/E6/E7；本步raw/scaled reward与原激活mask、正负收益 | 全部1024env有效rollout步；physics/reward后、reset前，side×Stage0/staged出生×10-batch窗口 |
| trainer env.step后到现有episode聚合（4032–4050、4863–4924） | 导出小型exposure_by_side_origin_window.jsonl | 消费env已捕获记录，不在reset后反读terminal状态 |

申请预算：P_S1、P_S2各从本身Wave2 step9000 full续训；1024env，各100新batches、绝对上限9100，共13,107,200 transitions。9050/9100保存诊断checkpoint；actor/critic/PPO照常更新，不冻结，不更改reward/obs/E事件/ratio/plant/loader语义，不增加随机采样。旧约22秒/batch推算约1.2 GPU小时，启动开销另计；不包含eval/render或自动延长。预期超过30分钟时每格独立tmux；**尚未批准，遥测接线和launcher均未实施，新运行均未启动。**

测量完成条件：两来源覆盖规定窗口且上述实际计数可按side/origin核算，能区分natural/staged是否得到有余量B入口与ready。100batches只能描述新进程初期曝光，若库存继续漂移就报告瞬态，不宣称稳态。达到9100停止；实际异常/NaN/来源不符/Owner停止即停止，不因没有E7自动延长。9100不自动替代9000 source。P2预算不能挪用P1，须以后明确单变量、同期原配置C、直接中介及成功/停止条件后另批。

## 8. Provenance、复用与验证范围

- **P_S1 LEFT**：trace [stage2_5_step_trace.json](/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/logs_eval/a2_piper_pull_v26_8_backbone/pull_v26_8_backbone_20260905_natural1_r2/wave2/eval/milestones/step9000/P_S1_STEP9000/left/stage2_5_step_trace.json)（1,655,802,049 bytes）；config [runtime_config.yaml](/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/logs_eval/a2_piper_pull_v26_8_backbone/pull_v26_8_backbone_20260905_natural1_r2/wave2/eval/milestones/step9000/P_S1_STEP9000/left/.hydra/runtime_config.yaml)；terminal metrics [metrics_eval.json](/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/logs_eval/a2_piper_pull_v26_8_backbone/pull_v26_8_backbone_20260905_natural1_r2/wave2/eval/milestones/step9000/P_S1_STEP9000/left/metrics_eval.json)；per-env records [a2_v14_per_env_records.json](/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/logs_eval/a2_piper_pull_v26_8_backbone/pull_v26_8_backbone_20260905_natural1_r2/wave2/eval/milestones/step9000/P_S1_STEP9000/left/a2_v14_per_env_records.json)。
- **P_S1 RIGHT**：trace [stage2_5_step_trace.json](/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/logs_eval/a2_piper_pull_v26_8_backbone/pull_v26_8_backbone_20260905_natural1_r2/wave2/eval/milestones/step9000/P_S1_STEP9000/right/stage2_5_step_trace.json)（1,596,194,433 bytes）；config [runtime_config.yaml](/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/logs_eval/a2_piper_pull_v26_8_backbone/pull_v26_8_backbone_20260905_natural1_r2/wave2/eval/milestones/step9000/P_S1_STEP9000/right/.hydra/runtime_config.yaml)；terminal metrics [metrics_eval.json](/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/logs_eval/a2_piper_pull_v26_8_backbone/pull_v26_8_backbone_20260905_natural1_r2/wave2/eval/milestones/step9000/P_S1_STEP9000/right/metrics_eval.json)；per-env records [a2_v14_per_env_records.json](/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/logs_eval/a2_piper_pull_v26_8_backbone/pull_v26_8_backbone_20260905_natural1_r2/wave2/eval/milestones/step9000/P_S1_STEP9000/right/a2_v14_per_env_records.json)。
- **P_S2 LEFT**：trace [stage2_5_step_trace.json](/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/logs_eval/a2_piper_pull_v26_8_backbone/pull_v26_8_backbone_20260905_natural1_r2/wave2/eval/milestones/step9000/P_S2_STEP9000/left/stage2_5_step_trace.json)（1,670,989,621 bytes）；config [runtime_config.yaml](/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/logs_eval/a2_piper_pull_v26_8_backbone/pull_v26_8_backbone_20260905_natural1_r2/wave2/eval/milestones/step9000/P_S2_STEP9000/left/.hydra/runtime_config.yaml)；terminal metrics [metrics_eval.json](/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/logs_eval/a2_piper_pull_v26_8_backbone/pull_v26_8_backbone_20260905_natural1_r2/wave2/eval/milestones/step9000/P_S2_STEP9000/left/metrics_eval.json)；per-env records [a2_v14_per_env_records.json](/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/logs_eval/a2_piper_pull_v26_8_backbone/pull_v26_8_backbone_20260905_natural1_r2/wave2/eval/milestones/step9000/P_S2_STEP9000/left/a2_v14_per_env_records.json)。
- **P_S2 RIGHT**：trace [stage2_5_step_trace.json](/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/logs_eval/a2_piper_pull_v26_8_backbone/pull_v26_8_backbone_20260905_natural1_r2/wave2/eval/milestones/step9000/P_S2_STEP9000/right/stage2_5_step_trace.json)（1,668,027,542 bytes）；config [runtime_config.yaml](/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/logs_eval/a2_piper_pull_v26_8_backbone/pull_v26_8_backbone_20260905_natural1_r2/wave2/eval/milestones/step9000/P_S2_STEP9000/right/.hydra/runtime_config.yaml)；terminal metrics [metrics_eval.json](/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/logs_eval/a2_piper_pull_v26_8_backbone/pull_v26_8_backbone_20260905_natural1_r2/wave2/eval/milestones/step9000/P_S2_STEP9000/right/metrics_eval.json)；per-env records [a2_v14_per_env_records.json](/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/logs_eval/a2_piper_pull_v26_8_backbone/pull_v26_8_backbone_20260905_natural1_r2/wave2/eval/milestones/step9000/P_S2_STEP9000/right/a2_v14_per_env_records.json)。
- **r6an RIGHT**：trace [stage2_5_step_trace.json.gz](/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/logs_eval/a2_piper_pull_v6/p2_render_F0_r6ap_r6an_seed3_env14/eval/stage2_5_step_trace.json.gz)（49,387,562 bytes）；config [config.yaml](/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/logs_rl/a2_piper_pull_v6/pull_v6_F0_r6an_seed3/config.yaml)；terminal metrics [metrics_eval.json](/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/logs_eval/a2_piper_pull_v6/p2_render_F0_r6ap_r6an_seed3_env14/eval/metrics_eval.json)；per-env records [a2_v14_per_env_records.json](/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/logs_eval/a2_piper_pull_v6/p2_render_F0_r6ap_r6an_seed3_env14/eval/a2_v14_per_env_records.json)。

- 当前训练来源与日志：`logs_rl/a2_piper_pull_v26_8_backbone/pull_v26_8_backbone_20260905_natural1_r2/wave2/train/{P_S1,P_S2}/`中的`model_step_009000.pt`、`resolved_config.yaml`、`isaac.log`。这两份checkpoint只在CPU读取保存结构，未启动仿真。
- 旧eval保存override：[config.yaml](/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/logs_eval/a2_piper_pull_v6/p2_render_F0_r6ap_r6an_seed3_env14/hydra/.hydra/config.yaml)；其七项ready阈值与旧训练保存config相同，robot部分为局部override，release限位重算使用旧完整训练保存config并与逐步workspace原值核对。旧runner记录policy_only请求被规范化为full；不将请求字段当实际loader路径。
- 每组metadata的trace_timing原文保存于JSON。当前runtime receipt记录checkpoint路径、命令与退出码；当前eval `.hydra/runtime_config.yaml`优先于计划。
- 入口：[analyze_p0.py](/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/scriptsFORhuman/pull_v7/analyze_p0.py)。普通执行读取固定五份trace；`--reuse-existing`复用完成组，仅提取缺组；`--report-only`仅使用小表/小型metrics/config重生成三产物，不解析大trace。
- 实际验证：能力分母64×4与旧16、缺失env、首事件counter精确对齐、trace内步连续性、release margin逐关节重算、phase-C/ready重算均已核对；ready不一致计数0。初版曾错误要求Stage0失败env也有Stage2 trace，修正后保留缺失总体并完成提取；没有新测试矩阵、compile循环或GPU验证。
- Main为唯一writer；两条只读lane已交付。只新增P0入口与三个产物，增量更新对应memory；不改训练语义、全局配置、已有用户改动，不commit/push。P0完成不代表v7全链路能力达标。
