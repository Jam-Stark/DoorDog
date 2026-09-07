# Pull v26-8 backbone closure — 2026-09-08

**双侧 durable unlatch 与 opening 已建立；E6/E7 尚未建立。** 首次总体unlatch endpoint是step4500，首次两seed双侧opening是step5250。Wave1三格6000 batches与Wave2两格新增3000 batches均完整执行并正常退出；最终按预注册口径为`PULL_FULL_CHAIN_PARTIAL`，四侧E6/E7均为0/64。该标签不代表出现了E7成功样本。

关闭时间：2026-09-08 07:21 HKT。Run：`pull_v26_8_backbone_20260905_natural1_r2`。本阶段仅支持这套backbone迁移组合的实验结论；没有Teacher、handoff或hardware交付。

## Wave1结果

三格均1024 env、scratch/full、固定reset ratios `[0.5,0.1,0.1,0.1,0.1,0.1]`，无课程切换。每个里程碑每侧exact64，原始结果位于[run目录](/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/logs_eval/a2_piper_pull_v26_8_backbone/pull_v26_8_backbone_20260905_natural1_r2)。下面L/R是两侧各自的成功计数，每侧分母64。

| Step | P_S0 D(L/R) | P_S1 D(L/R) | P_S2 D(L/R) | 已达到的报告门 |
|---:|---:|---:|---:|---|
| 750 | 0 / 0 | 0 / 0 | 0 / 0 | 尚无opening |
| 1500 | 0 / 0 | 27 / 5 | 0 / 0 | 尚无opening |
| 2250 | 0 / 0 | 62 / 64 | 0 / 0 | PULL_OPENING_EMERGED |
| 3000 | 2 / 0 | 64 / 64 | 0 / 0 | PULL_OPENING_EMERGED |
| 3750 | 9 / 0 | 64 / 64 | 4 / 48 | PULL_OPENING_EMERGED |
| 4500 | 62 / 0 | 63 / 64 | 63 / 41 | unlatch支持；PULL_OPENING_EMERGED |
| 5250 | 64 / 0 | 64 / 64 | 62 / 60 | unlatch支持；PULL_OPENING_EMERGED, PULL_OPENING_BILATERAL |
| 6000 | 64 / 0 | 59 / 64 | 62 / 64 | unlatch支持；PULL_OPENING_EMERGED, PULL_OPENING_BILATERAL |

step4500的P_S1 D=63/64、P_S2 D=63/41满足注册门（LEFT≥8，RIGHT≥32，至少两个seed），已在[WAVE1_ENDPOINT.json](/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/scriptsFORhuman/pull_v26_8/WAVE1_ENDPOINT.json)冻结。三格继续到6000，没有提前停止。

最终step6000：

| Cell | Side | D | S3+ | S4+ | open_hold | S5+ | complete |
|---|---|---:|---:|---:|---:|---:|---:|
| P_S0 | LEFT | 64 | 64 | 64 | 64 | 0 | 0 |
| P_S0 | RIGHT | 0 | 62 | 0 | 0 | 0 | 0 |
| P_S1 | LEFT | 59 | 59 | 59 | 59 | 0 | 0 |
| P_S1 | RIGHT | 64 | 64 | 64 | 64 | 0 | 0 |
| P_S2 | LEFT | 62 | 64 | 63 | 63 | 0 | 0 |
| P_S2 | RIGHT | 64 | 64 | 64 | 64 | 0 | 0 |

| Cell | Side | K5 | E2 | E3 | E4 | E5 | E6 | E7 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| P_S0 | LEFT | 64 | 64 | 64 | 64 | 62 | 0 | 0 |
| P_S0 | RIGHT | 62 | 62 | 0 | 0 | 0 | 0 | 0 |
| P_S1 | LEFT | 59 | 59 | 59 | 59 | 59 | 0 | 0 |
| P_S1 | RIGHT | 64 | 64 | 64 | 64 | 64 | 0 | 0 |
| P_S2 | LEFT | 64 | 63 | 64 | 63 | 63 | 0 | 0 |
| P_S2 | RIGHT | 64 | 64 | 64 | 64 | 64 | 0 | 0 |

P_S0最终为`LEFT_RECOVERED_RIGHT_REGRESSED`；P_S1、P_S2为`BILATERAL_UNLATCH_SUPPORTED`。从LEFT解锁困难到两个seed双侧unlatch/opening，是本阶段与历史方向相反的新读数；P_S0 RIGHT仍未恢复，成功不能推广到全部seed。

## Wave2结果

按最终6000的D选择P_S2、P_S1：优先满足双侧门，再比较较弱侧D、两侧D总和、较小seed。选择规则在最终读数前说明，实际两个源也恰好是最终唯一通过双侧门的seed；没有按中途E7挑checkpoint。[WAVE2_SELECTION.json](/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/scriptsFORhuman/pull_v26_8/WAVE2_SELECTION.json)记录了源与排序。

两格分别在GPU3/2加载自己的`model_step_006000.pt`，`checkpoint_load_mode=full`、absolute budget9000。日志确认均`Loaded checkpoint from step 6000`，首个更新6001；实际新增3000 batches。6750/7500/8250/9000四次双侧exact64均完成。

最终step9000：

| Cell | Side | D | S3+ | S4+ | open_hold | S5+ | complete |
|---|---|---:|---:|---:|---:|---:|---:|
| P_S2 | LEFT | 64 | 64 | 64 | 64 | 0 | 0 |
| P_S2 | RIGHT | 64 | 64 | 64 | 64 | 0 | 0 |
| P_S1 | LEFT | 64 | 64 | 64 | 64 | 0 | 0 |
| P_S1 | RIGHT | 62 | 62 | 62 | 62 | 0 | 0 |

| Cell | Side | K5 | E2 | E3 | E4 | E5 | E6 | E7 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| P_S2 | LEFT | 64 | 64 | 64 | 64 | 64 | 0 | 0 |
| P_S2 | RIGHT | 64 | 64 | 64 | 64 | 64 | 0 | 0 |
| P_S1 | LEFT | 64 | 64 | 64 | 64 | 64 | 0 | 0 |
| P_S1 | RIGHT | 62 | 62 | 62 | 62 | 62 | 0 | 0 |

最终四侧arm_j4限位占比均0，integrity violations均0；所有terminal reason均为`stage_overtime`。全部12个正式milestone reducer通过resolved config、natural出生trace、exact64与当前pull event完整性校验。历史最高arm_j4限位占比为step5250 P_S2 RIGHT的0.2257%，其余细项（force、over-force、p95与terminal reasons）完整保存在[SUMMARY.json](/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/scriptsFORhuman/pull_v26_8/SUMMARY.json)与各reducer中。

**Wave2裁决：`PULL_FULL_CHAIN_PARTIAL`；`PULL_FULL_CHAIN_BILATERAL`未达到。** E5维持高计数，E6/E7没有观察到；没有扩大预算或增加新轴。W基线本来就是0.25，W轴按Owner裁决删除，未运行。

## 协议差异

主线v26-7 natural eval为`enable_staged_reset=false`；pull保留`enable_staged_reset=true`并使用精确Stage0-only概率`[1,0,0,0,0,0]`（Hydra序列化为浮点数）。`a2_pull_v6_stage4_bank_enabled`与`a2_pull_v61_late_state_bank_enabled`均false。pull初始化路径未修改。

两者的natural起点等价由两层实际证据支持：每份eval resolved runtime config逐项通过上述概率、bank、first-episode-only、exact64断言；每个env的首个落盘row来自reset后、策略动作前，`stage_buf=episode_index=a2_v26_episode_start_stage=0`。缺失或不符会硬判`PULL_V26_8_INVALID`。出生行只用于协议证明，不进入D、K5、力或关节统计；后续trace保留起始stage字段。

G1四份eval均通过上述门：LEFT32目标相对旋转范围179.994579938–179.999023380°，满足180°±0.05°；bilateral RIGHT32与all-RIGHT64配对均bit-identical，integrity0。[G1结果](/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/logs_eval/a2_piper_pull_v26_8_backbone/pull_v26_8_backbone_20260905_natural1_r2/G1_wiring/g1_wiring.json)。

最初方案1 eval在reset采样前因整数概率产生Long tensor被`multinomial`拒绝，未产生eval策略/几何读数；仅改为数值相同的浮点序列化并在新root重跑。更早的flag=false构造阻塞和2048-env OOM等历史已保留在[20260905 closure](/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/scriptsFORhuman/pull_v26_8/a2_piper_pull_v26_8_backbone_closure_20260905.md)。没有借此改变初始化、reward、E事件或门槛。

另一个full-reload限制：当前环境只将log_dict写入env state，online staged-reset样本不在checkpoint内。Wave1进程内样本持续积累；Wave2新进程重新积累这些样本。full loader仍恢复policy、critic、optimizer、scheduler与TrainerState；没有新增序列化或更改loader。

## 观测维度与N-03

pull plain与本次引用主线`cb15678`的实际名单都为133/138，主线plan的135/140计数没有对应的额外2维term。逐项为：

| Actor term | 维数 |
|---|---:|
| `dof_pos` | 20 |
| `relative_to_door` | 9 |
| `dof_vel` | 20 |
| `actions` | 19 |
| `projected_gravity` | 3 |
| `door_dof_pos` | 2 |
| `base_lin_vel` | 3 |
| `base_ang_vel` | 3 |
| `hand_force` | 6 |
| `stage` | 6 |
| `privileged_door_info` | 8 |
| `delta_actions` | 6 |
| `gripper_handle_transform` | 18 |
| `a2_base_command_raw` | 5 |
| `a2_base_command` | 5 |
| 合计 | **133** |

Critic再加`transition`、`complete`、`time_in_stage`、`actual_time_in_stage`、`total_time`五个标量，合计138。旧pull override actor追加的`z_a2_pull_v6_release_mode`是2维，因此其实际输入为135/140；它不是主线相对pull plain的差异。新backbone没有该term，也没有override模块或补维度。N-03的观测维数已经一致，push/pull合一的训练与全链路语义仍未在本阶段验证。

## E6前置条件的有限诊断

E6源码要求先有E5、跨门方向位置与速度、panel clear、frame passage，以及clean release持续至少25步；E7再依赖E6。最终终端记录显示release event和clean release在四侧均为0：

| Cell / side | release event | clean release | terminal release ready |
|---|---:|---:|---:|
| P_S2 / LEFT | 0 | 0 | 0 |
| P_S2 / RIGHT | 0 | 0 | 0 |
| P_S1 / LEFT | 0 | 0 | 0 |
| P_S1 / RIGHT | 0 | 0 | 0 |

[一次已有trace诊断](/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/logs_eval/a2_piper_pull_v26_8_backbone/pull_v26_8_backbone_20260905_natural1_r2/wave2/post_e5_diagnostic_step7500_P_S1_left.json)仅覆盖step7500 P_S1 LEFT：64个env、11259个E5后row中，release_ready和clean_release均未出现，原始与实际开夹爪命令次数都为0，eval强制闭合次数也为0。当前`a2_base.py`将正gripper primitive映射为open target。该证据定位了尚未满足的release前提，不证明plain actor在结构上不可能完成E7，也没有据此修改实验。

Stage3→4收入代码保持原样：`unlatch_hold`在hinge≥0.25后归零；hold-and-drive及受live-proof约束的handle/hinge项在0.25两侧仍可能支付。已在正式eval记录六项reward诊断。本次opening已经出现，Owner指定的“无opening则交回该几何诊断”分支未触发。

## 执行与证据边界

| Phase / cell | GPU | 实际 batch | 峰值显存 MiB | Child/wrapper |
|---|---:|---|---:|---|
| wave1 / P_S0 | 1 | 1–6000 | 16770 | 0 / 0 |
| wave1 / P_S1 | 2 | 1–6000 | 18632 | 0 / 0 |
| wave1 / P_S2 | 3 | 1–6000 | 16741 | 0 / 0 |
| wave2 / P_S2 | 3 | 6001–9000 | 16547 | 0 / 0 |
| wave2 / P_S1 | 2 | 6001–9000 | 18551 | 0 / 0 |

Wave1每格393,216,000 transitions，Wave2每格新增196,608,000；总计1,572,864,000，均按注册64 control steps/batch计算。G0以1024 env PASS冻结规模，2048 OOM没有进入正式矩阵。完整receipts在`.ai/runtime/runs/`，source snapshots在`scriptsFORhuman/pull_v26_8/runtime_logs/pull_v26_8_backbone_20260905_natural1_r2/`。G1为RUNTIME_PASS；双侧unlatch/opening为注册实验支持；E6/E7未观察到；hardware为NOT_RUN。

未运行：被删除的W轴、可选G2旧winner体征对照、Teacher、handoff、hardware。旧winner没有用于warm-start。

改动范围：镜像helper/base接线；新plain backbone exp/common/三seed配置；base与trainer的出生trace；`scriptsFORhuman/pull_v26_8/`的启动、验证、reducer、监督器与合同；迁移plan与现有pull-lr-full-stage memory。pull初始化、reward数值/函数、E事件与loader语义未改。

本任务全部train/eval/watch进程和writer已结束，GPU leases已释放，coordination已关闭。三个授权本地提交点已执行（G0/G1：`fd38b36`；首次unlatch endpoint：`4f99358`；closure：本文件所属提交）；未push。没有新artifact handoff bundle。
