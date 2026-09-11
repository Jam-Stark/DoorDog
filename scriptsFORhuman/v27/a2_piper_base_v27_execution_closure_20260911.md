# base_v27 execution closure — 2026-09-11

**终态：V27_COMPLETED_SCIENTIFIC_NO_RELEASE。** 全部注册阶段已完成或按预注册规则记为未运行；没有新的Teacher/G7绑定。

## 科学结论与路由

| 问题 | 终态 | 后续路由 |
|---|---|---|
| v27.0 | NO_QUALIFIED_CANDIDATE | CONF与v27.5旧候选确认NOT_RUN |
| Q_A | QUALITY_UNRESOLVED | RECIPE_A=C，固定C_S21 step3000载体 |
| Q_B | DOMAIN_NOT_CONVERGED | RECIPE_B=current |
| Q_R | UNRESOLVED | R1被harness误停，缺1500 endpoint；不补选、不恢复 |
| Q_C / SC | SCRATCH_NOT_ESTABLISHED | endpoint 0/3 seed双侧过门 |
| K vs SC | K_SCRATCH_SUPERIOR | endpoint 1/3 vs 0/3，满足注册S4+/open_hold guard；仅SK_S213过门 |

这些是各阶段权威决策，不使用Wave C reducer里其他阶段的占位UNRESOLVED覆盖已冻结A/B结论。K的相对优势不等于三seed可靠性；不能据此授予Teacher资格。

## v27.5 最终确认

SC201/202/203在1000、2000、3000、4000、5000、6000均无双侧过门。v27.0也无选中候选。因此两个exact128/side确认均NOT_RUN；没有用SK213替换SC、没有中途best替换固定endpoint。

冻结选择规则：`scriptsFORhuman/v27/runtime_logs/v27_bilateral_hardening_20260905/wave_c_final_selection_contract.json`；最终裁决：`scriptsFORhuman/v27/runtime_logs/v27_bilateral_hardening_20260905/wave_c_final_confirmation_decision.json`。

候选manifest v1：[a2_piper_base_v27_teacher_candidate_manifest_v1](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/a2_piper_base_v27_teacher_candidate_manifest_20260905.json)；[manifest v2](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/a2_piper_base_v27_teacher_candidate_manifest_v2_20260911.json)。

## v27.0 DEV（每侧128）

| Cell | 层 | 侧 | D/S3+/S4+/open_hold/S5+/complete/clean | 握门穿过 | 身体力p95 N | arm_j4驻留占比 | 终止原因 | integrity |
|---|---|---|---|---:|---:|---:|---|---:|
| C_S2 | DEV | left | 113/128/128/128/128/128/75 | 0 | 729.034912109375 | 0.0037984421578997982 | {"complete": 128} | 0 |
| C_S2 | DEV | right | 109/128/128/128/128/128/69 | 128 | 0.0 | 0.0 | {"complete": 128} | 0 |
| W_S2 | DEV | left | 120/128/125/125/125/125/100 | 0 | 745.18603515625 | 0.02621231979030144 | {"complete": 125, "stage_overtime": 3} | 0 |
| W_S2 | DEV | right | 104/128/127/127/127/127/112 | 127 | 0.0 | 0.0 | {"complete": 127, "stage_overtime": 1} | 0 |
| K_S2 | DEV | left | 106/127/127/127/127/122/71 | 126 | 961.720947265625 | 0.0 | {"upper_dof_overspeed": 6, "complete": 122} | 0 |
| K_S2 | DEV | right | 92/126/125/124/124/122/119 | 120 | 0.0 | 0.0 | {"upper_dof_overspeed": 5, "stage_overtime": 1, "complete": 122} | 0 |

18个预定render QA回合、54个视频已在v27.0保留；不把视觉QA当作资格统计。

## Wave A endpoint（每侧64）

| Cell | 层 | 侧 | D/S3+/S4+/open_hold/S5+/complete/clean | 握门穿过 | 身体力p95 N | arm_j4驻留占比 | 终止原因 | integrity |
|---|---|---|---|---:|---:|---:|---|---:|
| C_S21 | nominal | left | 54/64/64/64/64/64/51 | 4 | 0.0 | 0.0 | {"complete": 64} | 0 |
| C_S21 | nominal | right | 50/64/64/64/64/64/41 | 64 | 0.0 | 0.0 | {"complete": 64} | 0 |
| Q1_S21 | nominal | left | 49/64/64/64/63/63/5 | 0 | 495.334716796875 | 0.0 | {"complete": 63, "stage_overtime": 1} | 0 |
| Q1_S21 | nominal | right | 64/64/64/64/64/64/40 | 64 | 0.0 | 0.0 | {"complete": 64} | 0 |
| Q2_S21 | nominal | left | 55/64/64/64/64/64/18 | 11 | None | 0.02500092186290055 | {"complete": 64} | 0 |
| Q2_S21 | nominal | right | 26/64/64/63/64/64/21 | 0 | None | 0.0 | {"complete": 64} | 0 |
| C_S22 | nominal | left | 56/61/61/61/61/61/0 | 1 | None | 0.0 | {"stage_overtime": 3, "complete": 61} | 0 |
| C_S22 | nominal | right | 52/62/62/62/62/62/39 | 62 | 0.0 | 0.0 | {"stage_overtime": 2, "complete": 62} | 0 |
| Q1_S22 | nominal | left | 54/64/64/64/64/64/17 | 60 | 0.0 | 0.0 | {"complete": 64} | 0 |
| Q1_S22 | nominal | right | 53/63/63/63/63/62/20 | 45 | 0.0 | 0.1655883137673426 | {"upper_dof_overspeed": 1, "stage_overtime": 1, "complete": 62} | 0 |
| Q2_S22 | nominal | left | 34/64/63/62/63/63/16 | 0 | 39.362632751464844 | 0.0 | {"upper_dof_overspeed": 1, "complete": 63} | 0 |
| Q2_S22 | nominal | right | 48/63/63/63/63/63/39 | 63 | 0.0 | 0.0 | {"upper_dof_overspeed": 1, "complete": 63} | 0 |

完整配对差、反向读数与telemetry：[Wave A report](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/a2_piper_base_v27_wave_a_step3000_readout_20260906.md)。

## Wave B domain endpoint（各层每侧64）

| Cell | 层 | 侧 | D/S3+/S4+/open_hold/S5+/complete/clean | 握门穿过 | 身体力p95 N | arm_j4驻留占比 | 终止原因 | integrity |
|---|---|---|---|---:|---:|---:|---|---:|
| L0_S31 | nominal | left | 21/59/59/59/59/59/0 | 47 | None | 0.0 | {"stage_overtime": 5, "complete": 59} | 0 |
| L0_S31 | nominal | right | 44/56/56/56/56/56/40 | 56 | 0.0 | 0.07731072271327441 | {"stage_overtime": 8, "complete": 56} | 0 |
| L0_S31 | P02 | left | 21/59/59/59/59/59/0 | 49 | None | 0.0 | {"stage_overtime": 5, "complete": 59} | 0 |
| L0_S31 | P02 | right | 47/56/56/56/56/56/38 | 56 | 0.0 | 0.07731490621915103 | {"stage_overtime": 8, "complete": 56} | 0 |
| L0_S31 | P05 | left | 21/59/59/59/59/59/0 | 49 | None | 0.0 | {"stage_overtime": 5, "complete": 59} | 0 |
| L0_S31 | P05 | right | 46/56/56/56/56/56/36 | 56 | 0.0 | 0.07697427665322423 | {"stage_overtime": 8, "complete": 56} | 0 |
| L1_S31 | nominal | left | 62/63/63/63/63/63/17 | 5 | 476.1720275878906 | 0.0 | {"stage_overtime": 1, "complete": 63} | 0 |
| L1_S31 | nominal | right | 51/64/64/64/64/60/43 | 64 | 0.0 | 0.0 | {"upper_dof_overspeed": 4, "complete": 60} | 0 |
| L1_S31 | P02 | left | 59/63/63/63/59/59/11 | 0 | None | 0.0 | {"upper_dof_overspeed": 4, "stage_overtime": 1, "complete": 59} | 0 |
| L1_S31 | P02 | right | 48/64/64/64/64/57/41 | 64 | 0.0 | 0.0 | {"upper_dof_overspeed": 7, "complete": 57} | 0 |
| L1_S31 | P05 | left | 59/63/63/63/62/62/8 | 0 | None | 0.0 | {"upper_dof_overspeed": 1, "stage_overtime": 1, "complete": 62} | 0 |
| L1_S31 | P05 | right | 53/64/64/64/64/61/44 | 64 | 0.0 | 0.0 | {"upper_dof_overspeed": 3, "complete": 61} | 0 |
| L1_S32 | nominal | left | 62/63/63/63/63/63/63 | 0 | 0.0 | 0.29919566775503703 | {"stage_overtime": 1, "complete": 63} | 0 |
| L1_S32 | nominal | right | 49/62/62/62/62/62/52 | 61 | 0.0 | 0.0 | {"complete": 62, "stage_overtime": 2} | 0 |
| L1_S32 | P02 | left | 61/63/63/63/63/63/63 | 1 | 0.0 | 0.3052876097484153 | {"stage_overtime": 1, "complete": 63} | 0 |
| L1_S32 | P02 | right | 49/62/62/62/62/62/53 | 62 | 0.0 | 0.0 | {"stage_overtime": 2, "complete": 62} | 0 |
| L1_S32 | P05 | left | 61/63/63/63/63/63/63 | 2 | 0.0 | 0.3168135381735943 | {"stage_overtime": 1, "complete": 63} | 0 |
| L1_S32 | P05 | right | 50/62/62/62/62/62/52 | 62 | 0.0 | 0.0 | {"stage_overtime": 2, "complete": 62} | 0 |

完整配对/历史差、原生摩擦readback及训练桶证据：[Wave B L report](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/a2_piper_base_v27_wave_b_l_step3000_readout_20260907.md)。

## Wave B recovery endpoint（各模式每侧64）

R1_S41：训练停止于644，1500 endpoint NOT_RUN。下表仅为R0/R2实际结果；没有以R1 step500补齐。

| Cell | 层 | 侧 | D/S3+/S4+/open_hold/S5+/complete/clean | 握门穿过 | 身体力p95 N | arm_j4驻留占比 | 终止原因 | integrity |
|---|---|---|---|---:|---:|---:|---|---:|
| R0_S41 | nominal | left | 58/64/64/64/64/64/52 | 0 | 675.9775390625 | 0.0 | {"complete": 64} | 0 |
| R0_S41 | nominal | right | 29/64/64/64/64/64/47 | 64 | 0.0 | 0.0 | {"complete": 64} | 0 |
| R0_S41 | injected | left | 26/64/62/62/62/62/49 | 2 | 539.7586059570312 | 0.0 | {"upper_dof_overspeed": 2, "complete": 62} | 0 |
| R0_S41 | injected | right | 40/64/64/64/64/64/48 | 64 | 0.0 | 0.0 | {"complete": 64} | 0 |
| R0_S41 | sham | left | 58/64/64/64/64/64/52 | 0 | 675.9775390625 | 0.0 | {"complete": 64} | 0 |
| R0_S41 | sham | right | 29/64/64/64/64/64/47 | 64 | 0.0 | 0.0 | {"complete": 64} | 0 |
| R2_S41 | nominal | left | 27/63/63/63/63/63/7 | 58 | 0.0 | 0.0 | {"upper_dof_overspeed": 1, "complete": 63} | 0 |
| R2_S41 | nominal | right | 28/63/62/62/62/62/41 | 62 | 0.0 | 0.0 | {"upper_dof_overspeed": 2, "complete": 62} | 0 |
| R2_S41 | injected | left | 22/63/63/63/63/63/7 | 56 | None | 0.0 | {"upper_dof_overspeed": 1, "complete": 63} | 0 |
| R2_S41 | injected | right | 27/63/62/62/62/62/43 | 61 | 0.0 | 0.0 | {"upper_dof_overspeed": 2, "complete": 62} | 0 |
| R2_S41 | sham | left | 27/63/63/63/63/63/7 | 58 | 0.0 | 0.0 | {"upper_dof_overspeed": 1, "complete": 63} | 0 |
| R2_S41 | sham | right | 28/63/62/62/62/62/41 | 62 | 0.0 | 0.0 | {"upper_dof_overspeed": 2, "complete": 62} | 0 |

完整ITT loss/regrasp/recovered_complete/clean/NOT_TRIGGERED、bank采样及配对差：[Wave B R report](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/a2_piper_base_v27_wave_b_r_step1500_readout_20260907.md)。

## Wave C endpoint（nominal，每侧64）

| Cell | 层 | 侧 | D/S3+/S4+/open_hold/S5+/complete/clean | 握门穿过 | 身体力p95 N | arm_j4驻留占比 | 终止原因 | integrity |
|---|---|---|---|---:|---:|---:|---|---:|
| SC_S203 | nominal | left | 35/64/60/56/60/60/0 | 47 | None | 0.0 | {"upper_dof_overspeed": 4, "complete": 60} | 0 |
| SC_S203 | nominal | right | 63/63/63/63/63/63/0 | 60 | 715.8224487304688 | 0.0 | {"upper_dof_overspeed": 1, "complete": 63} | 0 |
| SK_S211 | nominal | left | 64/64/64/64/64/64/64 | 64 | 0.0 | 0.018030469608920997 | {"complete": 64} | 0 |
| SK_S211 | nominal | right | 63/64/64/64/63/63/34 | 50 | 1016.862060546875 | 0.0 | {"complete": 63, "stage_overtime": 1} | 0 |
| SK_S212 | nominal | left | 60/64/64/64/59/0/0 | 59 | 1104.95556640625 | 0.1578308242535141 | {"stage_overtime": 64} | 0 |
| SK_S212 | nominal | right | 64/64/64/64/2/0/0 | 61 | 0.0 | 0.655411237617658 | {"stage_overtime": 64} | 0 |
| SK_S213 | nominal | left | 61/63/62/62/62/62/62 | 37 | 0.0 | 0.05869478710704337 | {"upper_dof_overspeed": 2, "complete": 62} | 0 |
| SK_S213 | nominal | right | 2/64/63/63/63/63/63 | 2 | 0.0 | 0.0 | {"upper_dof_overspeed": 1, "complete": 63} | 0 |
| SC_S201 | nominal | left | 0/0/0/0/0/0/0 | 0 | None | 0.0 | {"stage_overtime": 64} | 0 |
| SC_S201 | nominal | right | 64/64/64/64/63/63/63 | 64 | 0.0 | 0.0 | {"complete": 63, "stage_overtime": 1} | 0 |
| SC_S202 | nominal | left | 50/64/64/64/64/64/23 | 64 | 0.0 | 0.0 | {"complete": 64} | 0 |
| SC_S202 | nominal | right | 64/64/64/64/64/64/1 | 64 | 0.0 | 0.008898230863548783 | {"complete": 64} | 0 |

六格正式训练均6000、wrapper退出0；六milestone共72 lanes/4608评估episodes，exact64，integrity0。C无恢复环；K使用已冻结16项配置与既有driver，未改reward函数。完整报告包括K训练trace、所有配对差和对上一milestone的负向变化。

| Milestone | 完整报告 |
|---|---|
| 1000 | [完整六格](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/a2_piper_base_v27_wave_c_step1000_full_readout_20260909.md) |
| 2000 | [完整六格](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/a2_piper_base_v27_wave_c_step2000_full_readout_20260911.md) |
| 3000 | [完整六格](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/a2_piper_base_v27_wave_c_step3000_full_readout_20260911.md) |
| 4000 | [完整六格](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/a2_piper_base_v27_wave_c_step4000_full_readout_20260911.md) |
| 5000 | [完整六格](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/a2_piper_base_v27_wave_c_step5000_full_readout_20260911.md) |
| 6000 | [完整六格](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/a2_piper_base_v27_wave_c_step6000_full_readout_20260911.md) |

必须保留的反向结果：SC_S203 complete在3000为64/63，6000为60/63，clean一直0/0；SC_S202 RIGHT clean在4000为18，6000降至1。SK211/212早期长期无complete，SK212到6000仍0/0；不能仅展示SK213的正向结果。

## Shadow estimator（固定一次CPU运行）

| 指标 | friction R² / RMSE N·m | mass R² / RMSE kg |
|---|---|
| heldout window | 0.15557 / 1.91948 | 0.33127 / 19.15647 |
| train-mean baseline | −0.00051 / 2.08936 | −0.00163 / 23.44461 |
| equal-episode | 0.21428 / 1.84151 | 0.43365 / 17.41115 |

固定window/stride64、ridge1、split_seed270202；heldout 279 episodes/1171 windows，51集因不足完整window排除。支持模拟数据中的有限离线可辨识性；不证明actor改善、实时适应、部署传感器合同或实机能力。运行工具未返回精确退出码，证据如实保留null与80–110秒观测时长。

[完整shadow报告](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/a2_piper_base_v27_shadow_estimator_readout_20260907.md)。

## 预算与失败记录

记录的正式PPO iteration总量66,644，不超过67,500上限；差额来自R1停止。A/B/C接线smoke分别5/32/5 batches。无追加seed或训练救援；policy前基础设施失败在新root重试，原始失败证据保留。

1. L1首次OmegaConf ListConfig解析错误发生在actor加载前，接受框架列表类型后新root重启；物理合同不变。
2. R1 step500大JSON被旧reader误判INVALID，误停训练于644。改标准库reader后仅CPU重判原artifact有效；R1不恢复，Q_R保留UNRESOLVED。
3. Wave C首次六格远程USD读取失败均在policy前；四格先重试，其余两格在Owner重新分配GPU后启动。
4. v28修改共享源码触发source锁，评估暂停；Owner授权后用bbd98db代码加v27冻结overlay独立执行。首次隔离漏scriptsFORhuman.v21B依赖，policy前失败；补齐同提交依赖后新part2_r1恢复。旧失败未混入72条有效lane。
5. 原watcher因主动替换退出143，以及source锁退出1，均与训练policy失败分开记录。

预算明细：`scriptsFORhuman/v27/runtime_logs/v27_bilateral_hardening_20260905/training_budget_closure_20260911.json`。运行原始receipt、失败manifest、新root映射和source快照均保留。

## 证据等级、未运行事项与后续决定

RUNTIME：各训练/评估的真实执行路径与receipt。EXPERIMENT：注册模拟条件下逐格计数和typed outcomes。CPU：固定shadow estimator。无HARDWARE证据。

未运行：v27.0 CONF、v27.5两候选确认（均无合格候选）；R1停止后的1000/1500 endpoint；hardware、binding更新、push。Q_R未达到需要附v28恢复pilot提案骨架的条件，本轮不附、不启动；现有v28工作不在本closure控制范围。

**向Owner提出的绑定裁决请求：建议保留现有Teacher与G7绑定。SK213仅为单seed模拟研究结果，没有本轮128样本确认，不作为自动替换依据。**

## Changed paths、隔离清理与资源

本轮代码主要为gr00t/rl/envs/door/door_open_a2_base.py中的v27能力、base_v27配置、v27脚本与针对真实失败的测试；A/B已提交，C调度/隔离入口及收尾产物进入最后一次预授权提交。当前主目录后来新增的v28源码和配置不纳入本次提交。

详细changed paths与资源清理记录：`scriptsFORhuman/v27/runtime_logs/v27_bilateral_hardening_20260905/closure_changed_paths_20260911.json`、`scriptsFORhuman/v27/runtime_logs/v27_bilateral_hardening_20260905/closure_resource_cleanup_20260911.json`。

临时隔离执行目录和v27候选副本已按Owner授权删除；历史source快照、checkpoint、eval artifact、报告、失败记录与receipt保留。已停用的active_source_lock指针移除，历史snapshot中的旧执行路径只作provenance。

本地提交点：52933a3（G0/v27.0）、1fa2b1e（A）、bbd98db（B），第四次为本closure提交；不push。

v27无活跃writer、训练/eval进程、tmux或lease；共享team ledger仍供v28任务使用，未强制关闭其他任务。
