# base_v26-8 execution closure — Wave 1 r3a / Wave 2 NOT_RUN

日期：2026-09-04 23:17 HKT
Run：`v26_8_bilateral_opening_scaffold_decay_20260903_r3a`
执行终态：Wave 1 complete；Wave 2 B1/B2 均未准入，未启动。
本文件同时是step3000的Owner readout。为保留同日r2/r3失败closure及其source-lock，文件名使用
`_20260904_wave1_r3a`后缀，不覆盖已有closure。

## 1. 结论先行：冻结typed outcomes

| 对象 | 最终结果 | 决定性证据 |
|---|---|---|
| W | W_NOT_DIFFERENT | NO_REGRESS(W)成立；C_S2已满足entry；W_S2 LEFT S4+−C=0 |
| K | K_REGRESSED | K_S1 RIGHT D=45 vs C61（−16）；K_S2 RIGHT D=45 vs C54（−9），均低于C−8 |
| C | C_ENTRY_EMERGED | C_S2 LEFT S4+/open_hold=64/64、RIGHT S4+=64 |
| C | C_CONSOLIDATED | C_S1 min-side S5+=46、min-side open_hold=62、D=62/61 |
| Wave2 B1 | NOT_RUN | K_REGRESSED使§9 B1条件不成立 |
| Wave2 B2 | NOT_RUN | 缺少W_STAGE34_SUPPORTED与K_SUPPORTED |

独立只读endpoint数值核对PASS：上述结果与当前source、§8/§9及不可变endpoint JSON一致，
未发现影响本endpoint的source/plan冲突；该核对没有重跑reducer、eval或任何训练。

K_S1的min-side S5+相对C **+8**，RIGHT complete **+17**；W_S1相应为 **+11 / +17**。
这些正读数完整保留，但不能替代跨source的D/S4+ NO_REGRESS条件，也不能把W的downstream读数
替换为entry路由。K_REGRESSED表示预注册unlatch-retention guard未满足，不代表所有开门指标都变差。
C的普通continuation已达到本阶段entry/consolidation计数目标，W没有获得额外entry支持。

六格均自然完成3000 batches、exit0；六份train与十二份eval队列receipt全部PASS/0。
6个milestone、72个lane、4608个评估episode均exact64且integrity=0；无停格、无重跑、无额外训练预算。
这些episode按cell×checkpoint×side分组，不把重复评估的门集当作4608个独立door样本作统计泛化。

## 2. 固定实验合同与来源

- source：Q05_S1/Q05_S2各自v26-7 step3000；C/W/K按source与seed配对。
- warm load：policy_only + policy_only_load_actor_rms=true；actor MLP/std/LSTM与actor RMS strict加载；
  critic、optimizer、scheduler、trainer/environment/staged-reset state fresh；未改trainer加载路径。
- 六格：4096 env、bilateral、seed1/2、horizon64、3000 batches、save250；每500作双侧natural exact64。
- C：控制；W：near_closed 0.1→0.25；K：natural-start min-side Stage≥4 driver，0.5/0.7 hysteresis，
  degree−0.0001、scale范围[0.2,1.0]及冻结16项名单。reward term scale数值、reward函数与stage判据不变。
- eval：checkpoint-adjacent config + full load，staged reset=false，first-episode-only，
  curriculum=false且driver=null；12份endpoint runtime config逐一核对对应cell的step3000 checkpoint。

| Source | 原checkpoint | 冻结SHA-256 |
|---|---|---|
| SRC_S1 | [Q05_S1 step3000](/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v26/v26_7_bilateral_native_unlatch_20260902/train/Q05_S1/model_step_003000.pt) | a683257213aaba82b583924d841235f772182f53113e513e16c8d27bcb394df1 |
| SRC_S2 | [Q05_S2 step3000](/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v26/v26_7_bilateral_native_unlatch_20260902/train/Q05_S2/model_step_003000.pt) | 0b2f739f020b056adb2fb47105fdb5bc00d1d1189ef331d42332b3e0740e54ec |

Runtime code基于`aa8a05fbbba62600ee2ac87cd1ad16f1bffa03e5`加登记的r3/r3a差分。
最终核对28个锁定文件：除首次评估前登记的eval driver-null补充外，均与r3a source lock一致；
canonical plan及六份load receipt的plan binding未变。

## 3. Endpoint逐格逐侧计数

每侧exact64；顺序 **D / S3+ / S4+ / open_hold / S5+ / complete**。
D为handle≥0.6连续≥25 control steps；Sx+为max_stage≥x；open_hold为hinge≥0.25且both_contact
连续≥25 control steps；complete仅报告。这里都是计数，不是通过率。

| Cell | LEFT | RIGHT |
|---|---|---|
| C_S1 | 62/63/62/62/62/62 | 61/63/63/63/46/36 |
| W_S1 | 63/64/64/64/64/64 | 60/63/60/60/57/53 |
| K_S1 | 64/64/64/64/64/64 | 45/60/60/57/54/53 |
| C_S2 | 57/64/64/64/64/64 | 54/64/64/64/64/64 |
| W_S2 | 63/64/64/64/64/64 | 50/64/64/64/64/64 |
| K_S2 | 52/64/64/64/63/60 | 45/63/63/63/63/63 |

## 4. 同source的arm−C

顺序 **D / S4+ / open_hold / S5+ / complete**；全部差值已独立复算。

| Arm/source | LEFT Δ | RIGHT Δ |
|---|---|---|
| W_S1 | +1/+2/+2/+2/+2 | −1/−3/−3/+11/+17 |
| K_S1 | +2/+2/+2/+2/+2 | −16/−3/−6/+8/+17 |
| W_S2 | +6/0/0/0/0 | −4/0/0/0/0 |
| K_S2 | −5/0/0/−1/−4 | −9/−1/−1/−1/−1 |

K的全部NO_REGRESS失败只有两项：S1 RIGHT D−16、S2 RIGHT D−9；其他K D/S4+差值均≥−8。
W所有D/S4+差值均在容差内。K_S2已engaged，故INERT identity分支不适用；
其LEFT S4+=64，不触发K_DRIVER_INVALID。所有milestone的K min-side S4+均≥56，无DRIVER_MISMATCH。
两个K的reversal_count均0，无K_OSCILLATING；W_S1 min-side S5+高于C11，无W_HARMFUL_DOWNSTREAM标签。

## 5. 所有历史反向读数与终段变化

历史源为v26-7 Q05同seed step3000，非同预算continuation对照；arm归因只使用上节C配对。
历史原reducer未存open_hold；其值由immutable历史trace按本阶段定义只读回算：
S1 LEFT/RIGHT=62/64，S2 LEFT/RIGHT=0/64。未修改v26-7任何artifact。

两表顺序均为 **D / S3+ / S4+ / open_hold / S5+ / complete**，负值含非路由项，全部保留。

| Cell−同seed source | LEFT Δ | RIGHT Δ |
|---|---|---|
| C_S1 | 0/−1/0/0/0/0 | −3/−1/−1/−1/+28/+32 |
| W_S1 | +1/0/+2/+2/+2/+2 | −4/−1/−4/−4/+39/+49 |
| K_S1 | +2/0/+2/+2/+2/+2 | −19/−4/−4/−7/+36/+49 |
| C_S2 | −3/+4/+64/+64/+64/+64 | −3/0/0/0/+43/+64 |
| W_S2 | +3/+4/+64/+64/+64/+64 | −7/0/0/0/+43/+64 |
| K_S2 | −8/+4/+64/+64/+63/+60 | −12/−1/−1/−1/+42/+63 |

| Cell：step3000−step2500 | LEFT Δ | RIGHT Δ |
|---|---|---|
| C_S1 | −2/−1/−2/−2/−2/−2 | +21/0/0/0/+8/+7 |
| W_S1 | +8/0/0/0/0/0 | −4/−1/−4/−4/+10/+6 |
| K_S1 | +1/0/0/+1/0/0 | −12/−3/−3/−5/−2/−3 |
| C_S2 | −6/0/+1/+1/+1/+1 | −3/+1/+1/+1/+1/+1 |
| W_S2 | +18/0/0/0/0/0 | −11/0/0/0/0/0 |
| K_S2 | +15/0/+1/+1/0/−3 | +14/−1/−1/−1/−1/−1 |

重要反向读数：

- K_S1 RIGHT相对源D/S3+/S4+/open_hold=−19/−4/−4/−7；终段相对step2500还出现
  D−12、S3+−3、S4+−3、open_hold−5、S5+−2、complete−3。
- K_S2两侧D均低于源；其LEFT在step2000的S5+/complete=0/0已于2500恢复63/63，
  endpoint为63/60，不能把中途0/0写成永久未形成。RIGHT的D虽由31回升45，仍未过C−8 guard。
- W_S1 RIGHT相对源D/S3+/S4+/open_hold=−4/−1/−4/−4；W_S2 RIGHT D相对源−7。
  C_S1 RIGHT及C_S2双侧D也低于源。D与下游高计数并存，未作额外因果诊断解释这一分离。
- 源Q05_S1 LEFT的62 complete在endpoint C/W/K为62/64/64；始终是非路由观察，不作选源、
  Teacher或G7更新依据。

## 6. K机制轨迹与reducer字段合同

### 全程摘要

| 全程指标 | K_S1 | K_S2 |
|---|---|---|
| trace rows | 191977 | 191968 |
| consumed / skipped | 159029 / 32948 | 157723 / 34245 |
| first_update_below_0.95 | 944 | 8617 |
| scale_min | 0.20000000298023224 | 0.20000000298023224 |
| share_of_updates_below_0.5 | 0.9521817717747438 | 0.9080263377229538 |
| reversal_count | 0 | 0 |
| 首次<0.95的common_step | 957 | 8626 |
| 最终scale_after | 0.20002000033855438 | 0.20000000298023224 |

K_S2并未如起始预期那样一直惰性：LEFT natural Stage4轨迹升高后进入decay，且每个milestone
LEFT S4+均≥56，因此这一预期反转被记录，但不构成driver invalid。C_S2也自行形成entry，
不能把K engagement解释成K独有的entry因果贡献。

K_S1最终row：common_step=192000、update_index=191976；LEFT 1/1、RIGHT 0/1，
按既定恢复公式将scale从0.20000000298023224升至0.20002000033855438，属于合法单次恢复，不是振荡。
K_S2最终row双侧5/5与2/2，scale保持float32 floor。

### 最后500 batches的双侧driver

2600/2700/2800/2900边界两格scale均约0.2；3000边界为K_S1≈0.20002、K_S2≈0.2。
以下只计consumed=true的natural reached/sample，区间`(lo×64,hi×64]`；左右不混池。
区间rate用于描述轨迹，实际决策仍使用每个pending window的min-side。

| K | batch区间 | LEFT reached/sample（rate） | RIGHT reached/sample（rate） |
|---|---|---|---|
| K_S1 | 2500–2600 | 19014/19057（0.997744） | 13541/13641（0.992669） |
| K_S1 | 2600–2700 | 19245/19308（0.996737） | 13898/14025（0.990945） |
| K_S1 | 2700–2800 | 19075/19105（0.998430） | 14082/14274（0.986549） |
| K_S1 | 2800–2900 | 19171/19254（0.995689） | 14392/14587（0.986632） |
| K_S1 | 2900–3000 | 19058/19390（0.982878） | 14492/15112（0.958973） |
| K_S2 | 2500–2600 | 14944/14997（0.996466） | 17727/17797（0.996067） |
| K_S2 | 2600–2700 | 15790/15893（0.993519） | 18083/18249（0.990904） |
| K_S2 | 2700–2800 | 16971/18305（0.927124） | 18539/19647（0.943605） |
| K_S2 | 2800–2900 | 16859/18371（0.917696） | 18743/19834（0.944993） |
| K_S2 | 2900–3000 | 16573/18436（0.898948） | 18985/20164（0.941529） |

末段K_S2 LEFT/RIGHT区间rate降至0.898948/0.941529，K_S1 RIGHT降至0.958973；
这些相对先前约0.99的反向变化同样报告，未追加预算或改driver。

### 字段与时间基准

- `update_index`为0-based curriculum callback序号；`common_step`为环境control-step计数；
  每个batch有64 control steps，milestone前缀为common_step≤batch×64。
- `natural_sample_left/right`是当前pending window分母，`natural_reached_left/right`是其中
  natural起始stage0、同一已结束episode的max_stage≥4分子；LEFT=+1、RIGHT=−1。
- `driver_left/right`为对应分子/分母，缺侧为null；`skipped=true`时保留两侧pending且不改scale；
  `consumed=!skipped`，双侧决策后原子清零。每个natural episode只消费一次。
- `scale_before/after`分别是更新前与torch.float32 hysteresis+clip后的值；log_dict记录clip后scale。
- `scale_min`、首次<0.95、低于0.5的share以所有trace row为分母，包含skipped row；
  driver区间汇总只计consumed row，避免重复pending。reversal_count为穿越0.5方向的翻转次数。
- 两个最终trace均正常EOF、last_common_step=192000；没有使用未来checkpoint/trace来补齐较早milestone。

## 7. 六个milestone与run receipts

| Milestone | lanes / episodes | integrity | route | Owner readout |
|---|---|---|---|---|
| 500 | 12 / 768 | 0 | V26_8_MILESTONE_REPORTED | [step500](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v26_8/a2_piper_base_v26_8_step500_readout_20260904.md) |
| 1000 | 12 / 768 | 0 | V26_8_MILESTONE_REPORTED | [step1000](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v26_8/a2_piper_base_v26_8_step1000_readout_20260904.md) |
| 1500 | 12 / 768 | 0 | V26_8_MILESTONE_REPORTED | [step1500](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v26_8/a2_piper_base_v26_8_step1500_readout_20260904.md) |
| 2000 | 12 / 768 | 0 | V26_8_MILESTONE_REPORTED | [step2000](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v26_8/a2_piper_base_v26_8_step2000_readout_20260904.md) |
| 2500 | 12 / 768 | 0 | V26_8_MILESTONE_REPORTED | [step2500](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v26_8/a2_piper_base_v26_8_step2500_readout_20260904.md) |
| 3000 | 12 / 768 | 0 | V26_8_ENDPOINT_READY | 本closure |

每个milestone均给Owner逐格/逐侧表、同源差、K双侧轨迹、完整性/receipt和进程/GPU快照；
详细中途逆转保留在上表链接，不重写为单调学习叙事。

| Cell | train receipt | budget / exit | source |
|---|---|---|---|
| C_S1 | [PASS](/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v26_8_train_c_s1_r3a/RUN_RECEIPT.json) | 3000 / 0 | SRC_S1 |
| W_S1 | [PASS](/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v26_8_train_w_s1_r3a/RUN_RECEIPT.json) | 3000 / 0 | SRC_S1 |
| K_S1 | [PASS](/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v26_8_train_k_s1_r3a/RUN_RECEIPT.json) | 3000 / 0 | SRC_S1 |
| C_S2 | [PASS](/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v26_8_train_c_s2_r3a/RUN_RECEIPT.json) | 3000 / 0 | SRC_S2 |
| W_S2 | [PASS](/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v26_8_train_w_s2_r3a/RUN_RECEIPT.json) | 3000 / 0 | SRC_S2 |
| K_S2 | [PASS](/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v26_8_train_k_s2_r3a/RUN_RECEIPT.json) | 3000 / 0 | SRC_S2 |

每份train receipt保留source checkpoint/hash、resolved config、strict load receipt、source lock、
r3a contract lock、P0资产检查的provenance；每个eval GPU队列有独立PASS/0 receipt。
每次launch前两项资产均HTTP200，六项proxy env显式写入receipt command。
训练/评估期间未重跑任何Wave1 cell或lane。

## 8. 实现、前置门与authority reconciliation

| 阶段 | 事实与证据 |
|---|---|
| G0 | R3A_CONTRACT_PASS、STATIC_PASS、G0_PASS；10个CPU tests；五类要求及pending消费/float32 transition检查完成 |
| 初次G1 | policy load前远程资产不可达，FAIL/1；保留原artifact，不作为策略结果 |
| G1 r2 | proxy/P0/strict load/5 batches成功，但每次reset-cohort缺侧，35/35 skipped；outer FAIL/1保留 |
| G1 r3 | 获批pending跨侧聚合后35行有10次consume；update31合法decay，旧all-scale1断言使outer FAIL/1；原失败保留 |
| r3a准入 | §15将G1改为精确transition verifier；对同一r3 artifact做CPU-only重裁，PASS/0 + G1_READJUDICATION_PASS；没有再跑Isaac G1 |
| eval补充 | 首次eval前修复K继承driver与单侧/curriculum-off冲突；所有arm显式driver=null，12×6个runtime config均验证 |

Authority差异均明确记录，未静默改判：

1. W阈值不只有reward消费者：还影响v22 failure-routing latch的unlatched分界，并被v26-2
   telemetry校验；历史unlatch_band仍固定0.1<hinge<0.25。Stage3→4使用独立0.25阈值，未改stage判据。
   这些伴随消费者在G0前已登记于[source appendix](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v26_8/a2_piper_base_v26_8_g0_source_appendix_20260903.md)。
2. v26-5既有train receipt writer要求residual-only optimizer partition，不能证明legacy actor加载。
   v26-8保留原strict policy-only+actor-RMS loader，仅由stream wrapper在观察到实际成功行后写自有load receipt；
   没有修改trainer或切换加载路径。
3. §14/§15与[eval addendum](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v26_8/a2_piper_base_v26_8_eval_driver_off_addendum_20260904.md)
   分别记录pending语义、旧G1断言/source公式冲突及eval driver-null补充。Wave1 eval/reducer阈值未改。
4. 原r2/r3 FAIL/1、旧closure与缺失的原r3 g1_wiring.json均保持历史事实；
   新准入仅引用g1_readjudication.json。冻结前置文档保留其原时点状态文字，当前执行状态以runtime和本closure为准。

## 9. Wave2裁定与未运行事项

已将endpoint与B1/B2不准入决定通知Owner。由于条件不满足，没有启动Wave2、没有创建scratch/KW训练，
额外Wave2预算使用为0。不得从中途checkpoint或高complete计数重新选路由。

- B1 scratch S0/S1/S2×6000：NOT_RUN（K_REGRESSED）。
- B2 KW continuation SRC_S1/SRC_S2×3000：NOT_RUN（W与K均非所需SUPPORTED）。
- Teacher/Student handoff、G7绑定更新、hardware/sim-to-real/部署：NOT_RUN且未授权。
- 额外seed、额外训练预算、reward/stage/loader改动、render或新增因果probe：NOT_RUN。
- Cloud bundle/upload、push：NOT_RUN；没有把本地closure扩大为云端handoff。
- 已获准的两次commit已完成：`e3d496b`（v26-6/v26-7已验收改动）、
  `aa8a05f`（v26-8初版/r2实现）；r3/r3a后续实现与执行文档尚未commit。本closure向Owner请求新的scoped commit授权，不自行提交或push。

## 10. 证据等级与资源清理

- INSPECTED / STATIC_PASS / TEST_PASS：source/config消费者、28文件锁定核对、G0与10个CPU tests。
- RUNTIME_PASS：G1真实5-batch路径及获批重裁、六格3000自然exit0、72条exact64 lane、严格load/receipt/config。
- EXPERIMENT证据：冻结step3000计数与typed outcomes。协议完成不等于W/K假设获支持，不作统计普遍化。
- HARDWARE_PASS：没有；不改变Teacher/Student/G7状态。

2026-09-04 23:10 HKT终态检查：六个train及十二个eval队列全部终结，v26-8 tmux为空，
无活跃训练/eval/background writer；Main的全部lease已释放，open_leases=0。
GPU0–7均1 MiB、0%。旧的、非本任务tmux不触碰。read-only子任务已返回，未留下writer。
23:19 HKT，Main已将coordination ledger归档并置为INACTIVE（coordination-20260904-231952.json）；
不删除任何科学artifact。

## 11. Changed paths与提交边界

以下列出本阶段source/config/script/memory路径（包含已提交初版与未提交r3/r3a增补）。
实际Git pending改动主要是core pending语义、对应tests、G1 verifier、r3a orchestrator、eval driver-null、
plan附录、r3/r3a verifiers与本次执行文档/memory。

### Core与测试

- [gr00t/rl/envs/door/door_open_a2_base.py](/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/envs/door/door_open_a2_base.py)
- [gr00t/rl/tests/test_a2_v26_8_penalty_curriculum.py](/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/tests/test_a2_v26_8_penalty_curriculum.py)
- [gr00t/rl/tests/test_a2_v26_8_g1_reduce.py](/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/tests/test_a2_v26_8_g1_reduce.py)

### Config（已包含在aa8a05f）

- [gr00t/rl/config/ablation/wbmanip/base_v26_8_common.yaml](/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/config/ablation/wbmanip/base_v26_8_common.yaml)
- [gr00t/rl/config/ablation/wbmanip/base_v26_8_C_S1.yaml](/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/config/ablation/wbmanip/base_v26_8_C_S1.yaml)
- [gr00t/rl/config/ablation/wbmanip/base_v26_8_W_S1.yaml](/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/config/ablation/wbmanip/base_v26_8_W_S1.yaml)
- [gr00t/rl/config/ablation/wbmanip/base_v26_8_K_S1.yaml](/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/config/ablation/wbmanip/base_v26_8_K_S1.yaml)
- [gr00t/rl/config/ablation/wbmanip/base_v26_8_C_S2.yaml](/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/config/ablation/wbmanip/base_v26_8_C_S2.yaml)
- [gr00t/rl/config/ablation/wbmanip/base_v26_8_W_S2.yaml](/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/config/ablation/wbmanip/base_v26_8_W_S2.yaml)
- [gr00t/rl/config/ablation/wbmanip/base_v26_8_K_S2.yaml](/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/config/ablation/wbmanip/base_v26_8_K_S2.yaml)

### 运行/验证脚本

- [scriptsFORhuman/v26_8/v26_8_orchestrate.sh](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v26_8/v26_8_orchestrate.sh)
- [scriptsFORhuman/v26_8/v26_8_train_cell.sh](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v26_8/v26_8_train_cell.sh)
- [scriptsFORhuman/v26_8/v26_8_eval_cell.sh](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v26_8/v26_8_eval_cell.sh)
- [scriptsFORhuman/v26_8/v26_8_eval_lane.sh](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v26_8/v26_8_eval_lane.sh)
- [scriptsFORhuman/v26_8/v26_8_reduce.py](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v26_8/v26_8_reduce.py)
- [scriptsFORhuman/v26_8/v26_8_verify.py](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v26_8/v26_8_verify.py)
- [scriptsFORhuman/v26_8/v26_8_g1_reduce.py](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v26_8/v26_8_g1_reduce.py)
- [scriptsFORhuman/v26_8/v26_8_g1_wiring_gate.sh](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v26_8/v26_8_g1_wiring_gate.sh)
- [scriptsFORhuman/v26_8/v26_8_capture_train.py](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v26_8/v26_8_capture_train.py)
- [scriptsFORhuman/v26_8/v26_8_p0_assets.py](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v26_8/v26_8_p0_assets.py)
- [scriptsFORhuman/v26_8/v26_8_r2_verify.py](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v26_8/v26_8_r2_verify.py)
- [scriptsFORhuman/v26_8/v26_8_r3_verify.py](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v26_8/v26_8_r3_verify.py)
- [scriptsFORhuman/v26_8/v26_8_r3a_verify.py](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v26_8/v26_8_r3a_verify.py)

### Memory（三文件）

- [memory/a2-piper/base-v26-scratch-bilateral-teacher/description.md](/home/baoquanc/workspace/DoorDog-A2_Piper/memory/a2-piper/base-v26-scratch-bilateral-teacher/description.md)
- [memory/a2-piper/base-v26-scratch-bilateral-teacher/TODO.md](/home/baoquanc/workspace/DoorDog-A2_Piper/memory/a2-piper/base-v26-scratch-bilateral-teacher/TODO.md)
- [memory/a2-piper/base-v26-scratch-bilateral-teacher/DONE.md](/home/baoquanc/workspace/DoorDog-A2_Piper/memory/a2-piper/base-v26-scratch-bilateral-teacher/DONE.md)

### 文档与实验artifact

- [冻结plan及§13–15](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v26_8/a2_piper_base_v26_8_bilateral_opening_scaffold_decay_plan_20260903.md)
- [G0 source appendix](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v26_8/a2_piper_base_v26_8_g0_source_appendix_20260903.md)
- [eval driver-off addendum](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v26_8/a2_piper_base_v26_8_eval_driver_off_addendum_20260904.md)
- 同目录step500/1000/1500/2000/2500 readout及本closure；前序20260903、20260904、20260904_r3失败closure保留。
- [r3a runtime logs/source locks/branch decision](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v26_8/runtime_logs/v26_8_bilateral_opening_scaffold_decay_20260903_r3a)
- [六格train artifacts](/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v26/v26_8_bilateral_opening_scaffold_decay_20260903_r3a/train)
- [六个milestone reducers与raw eval](/home/baoquanc/workspace/DoorDog-A2_Piper/logs_eval/base_v26/v26_8_bilateral_opening_scaffold_decay_20260903_r3a/milestones)
- [r3 immutable G1与readjudication](/home/baoquanc/workspace/DoorDog-A2_Piper/logs_eval/base_v26/v26_8_bilateral_opening_scaffold_decay_20260903_r3/G1_k_wiring)
- [run receipts目录](/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs)：仅本任务v26_8前缀的登记receipt；r2/r3 runtime roots保留。

不纳入本次提交请求：`scriptsFORhuman/knowledge_recap/`、`scriptsFORhuman/pro_reviews/`、
`scriptsFORhuman/v26_8/claudeHistory/`及其他不属于本任务的改动。未修改v26-7脚本或artifact。

## 12. 核心证据索引

- [endpoint reducer](/home/baoquanc/workspace/DoorDog-A2_Piper/logs_eval/base_v26/v26_8_bilateral_opening_scaffold_decay_20260903_r3a/milestones/step3000/reducer.json)
- [Wave2 branch decision](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v26_8/runtime_logs/v26_8_bilateral_opening_scaffold_decay_20260903_r3a/wave2_branch_decision.json)
- [r3a source lock](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v26_8/runtime_logs/v26_8_bilateral_opening_scaffold_decay_20260903_r3a/source_lock.json)
- [r3a contract lock](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v26_8/runtime_logs/v26_8_bilateral_opening_scaffold_decay_20260903_r3a/r3a_contract_lock.json)
- [eval source supplement](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v26_8/runtime_logs/v26_8_bilateral_opening_scaffold_decay_20260903_r3a/eval_driver_off_lock.json)
- [G0 gate](/home/baoquanc/workspace/DoorDog-A2_Piper/logs_eval/base_v26/v26_8_bilateral_opening_scaffold_decay_20260903_r3a/G0_static_unit/g0_unit.json)
- [G1 readjudication](/home/baoquanc/workspace/DoorDog-A2_Piper/logs_eval/base_v26/v26_8_bilateral_opening_scaffold_decay_20260903_r3/G1_k_wiring/g1_readjudication.json)
- [K_S1 final trace](/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v26/v26_8_bilateral_opening_scaffold_decay_20260903_r3a/train/K_S1/a2_v26_8_penalty_curriculum_trace.jsonl)
- [K_S2 final trace](/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v26/v26_8_bilateral_opening_scaffold_decay_20260903_r3a/train/K_S2/a2_v26_8_penalty_curriculum_trace.jsonl)
