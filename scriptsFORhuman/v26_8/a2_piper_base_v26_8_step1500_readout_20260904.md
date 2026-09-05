# v26-8 r3a Wave 1 — step1500 readout

As of：2026-09-04 12:45 HKT。Milestone evidence，不是 endpoint closure。

## 结果与边界

- `V26_8_MILESTONE_REPORTED`；12×exact64、integrity全0，两条eval receipt PASS/0；无失败/停格。
- C_S2 RIGHT下游从step1000的S5+/complete=4/0升至63/63，W_S2也维持高计数；不能把entry或下游进展归为W独有。
- K_S2 LEFT S5+/complete=5/1，相对C为−52/−55；RIGHT D相对C为−24，相对源为−19，
  尽管RIGHT S5+/complete=64/64。driver正常不能抵消这些负读数。
- W_S1 min-side S5+=33，C_S1=41，差值−8触及W_HARMFUL_DOWNSTREAM附加标签数值线；
  K_S1 min-side S5+比C多6，仍未达到+8。这里只报告数值，标签仍留至step3000。
- `typed_outcomes=null`，Wave2未裁定。六格继续原定3000，无重跑、改config、改阈值或追加预算。

## 逐格逐侧计数

每侧exact64；顺序 **D / S3+ / S4+ / open_hold / S5+ / complete**。D为handle≥0.6连续≥25步；
Sx+为max_stage≥x；open_hold为hinge≥0.25且both_contact连续≥25 control steps。均为计数，不是通过率。

| Cell | LEFT | RIGHT |
|---|---|---|
| C_S1 | 64/64/64/64/64/64 | 62/64/64/64/41/41 |
| W_S1 | 62/63/63/63/63/63 | 57/62/62/62/33/33 |
| K_S1 | 63/63/63/63/63/63 | 57/63/63/63/47/45 |
| C_S2 | 57/64/58/58/57/56 | 62/63/63/63/63/63 |
| W_S2 | 62/64/64/64/64/63 | 64/64/64/64/64/64 |
| K_S2 | 56/64/56/56/5/1 | 38/64/64/64/64/64 |

## 同source的arm−C

顺序 **D / S4+ / open_hold / S5+ / complete**；所有差值已独立复算，与冻结reducer一致。

| Arm/source | LEFT Δ | RIGHT Δ |
|---|---|---|
| W_S1 | −2/−1/−1/−1/−1 | −5/−2/−2/−8/−8 |
| K_S1 | −1/−1/−1/−1/−1 | −5/−1/−1/+6/+4 |
| W_S2 | +5/+6/+6/+7/+7 | +2/+1/+1/+1/+1 |
| K_S2 | −1/−2/−2/−52/−55 | −24/+1/+1/+1/+1 |

C_S2继续满足ENTRY_MET数值条件，W的正下游读数不替换W的entry路由。K_S2 RIGHT D的−24超过
NO_REGRESS的8计数容差；这不是提前停止条件，仍按既定预算到endpoint。

## 历史与上一milestone的全部差值

历史源为v26-7 Q05同seed step3000；历史open_hold沿用已验证的原始trace只读回算，未改历史文件。
两张表顺序均为 **D / S3+ / S4+ / open_hold / S5+ / complete**，负值全部保留，包括非路由指标。

| Cell−同seed source | LEFT Δ | RIGHT Δ |
|---|---|---|
| C_S1 | +2/0/+2/+2/+2/+2 | −2/0/0/0/+23/+37 |
| W_S1 | 0/−1/+1/+1/+1/+1 | −7/−2/−2/−2/+15/+29 |
| K_S1 | +1/−1/+1/+1/+1/+1 | −7/−1/−1/−1/+29/+41 |
| C_S2 | −3/+4/+58/+58/+57/+56 | +5/−1/−1/−1/+42/+63 |
| W_S2 | +2/+4/+64/+64/+64/+63 | +7/0/0/0/+43/+64 |
| K_S2 | −4/+4/+56/+56/+5/+1 | −19/0/0/0/+43/+64 |

| Cell：step1500−step1000 | LEFT Δ | RIGHT Δ |
|---|---|---|
| C_S1 | +1/+1/+1/+1/+1/+1 | −2/0/0/0/+9/+9 |
| W_S1 | +6/0/0/0/0/0 | −2/+2/+2/+2/+6/+7 |
| K_S1 | −1/−1/−1/−1/0/0 | +2/+2/+3/+3/+9/+7 |
| C_S2 | −6/0/−6/−6/−1/+16 | +5/−1/−1/−1/+59/+63 |
| W_S2 | −2/0/0/0/+4/+4 | +1/+1/+1/+1/+1/+1 |
| K_S2 | −4/0/−4/−4/−14/−2 | −26/0/0/0/+63/+63 |

相对历史源，S1三格RIGHT D均下降；W/K_S1有S3+/S4+低于源的侧格；C_S2 LEFT D及RIGHT
S3+/S4+也低于源；K_S2双侧D低于源。相对step1000，C_S2 LEFT D/S4+/open_hold下降，
K_S2 LEFT S5+/complete继续下降。完整正读数同样保留，不能用单一负指标抹去下游到达。
源Q05_S1 LEFT的62 complete在C/W/K中为64/63/63，始终仅记录、不路由。
不宣称跨seed普遍效果、统计显著性、Teacher或hardware能力。

## K scale与双侧driver轨迹

统计仅纳入 `common_step <= 1500×64 = 96000`；首个超界row不参与任何计算。
两格K在1100/1200/1300/1400/1500边界的最后scale均约0.2（float32 floor），
不把边界快照误写成每个update绝对恒定；0–1000轨迹见此前readout。

区间为`(lo×64, hi×64]`，仅consumed=true的natural reached/sample，左右独立汇总；
skipped保留的pending不重复计数。区间rate仅用于描述，实际决策仍使用每个window的min-side。

| K | batch区间 | LEFT reached/sample（rate） | RIGHT reached/sample（rate） |
|---|---|---|---|
| K_S1 | 1000–1100 | 17085/17117（0.998131） | 13002/13019（0.998694） |
| K_S1 | 1100–1200 | 17142/17178（0.997904） | 12996/13053（0.995633） |
| K_S1 | 1200–1300 | 17434/17479（0.997425） | 12884/12910（0.997986） |
| K_S1 | 1300–1400 | 17576/17642（0.996259） | 12808/12840（0.997508） |
| K_S1 | 1400–1500 | 17726/17767（0.997692） | 12832/12852（0.998444） |
| K_S2 | 1000–1100 | 13235/13323（0.993395） | 13575/13661（0.993705） |
| K_S2 | 1100–1200 | 13328/13435（0.992036） | 13691/13774（0.993974） |
| K_S2 | 1200–1300 | 13258/13355（0.992737） | 13721/13810（0.993555） |
| K_S2 | 1300–1400 | 13313/13417（0.992249） | 13064/13162（0.992554） |
| K_S2 | 1400–1500 | 13223/13306（0.993762） | 13936/14026（0.993583） |

| 累计至1500指标 | K_S1 | K_S2 |
|---|---|---|
| trace rows | 95979 | 95974 |
| consumed / skipped | 78384 / 17595 | 76514 / 19460 |
| first_update_below_0.95 | 944 | 8617 |
| scale_min | 0.20000000298023224 | 0.20000000298023224 |
| share_of_updates_below_0.5 | 0.9043540774544432 | 0.8160335090753745 |
| reversal_count | 0 | 0 |

`k_driver_mismatch_cells_ever=[]`；K_S2本次LEFT S4+=56，未触发driver invalid。
同一前缀的独立trace汇总与reducer的row/skipped/reversal计数一致；下游回退不能用这些机制检查PASS覆盖。

## 完整性、receipt与活跃资源

- 两条`v26_8_eval_step1500_gpu{0,1}_r3a`均PASS/0；P0两项资产均HTTP200，显式六键proxy进入receipt command。
- reducer核对exact64唯一env覆盖、自然first episode、side/seed、trace连续性、integrity=0、六格
  resolved config、源checkpoint路径/SHA与strict actor+RMS load receipt。canonical plan/source lock未变。
- 另行核对12份runtime config：对应cell的`model_step_001500.pt`、curriculum=false、driver=null。
- 以下为2026-09-04 12:41 HKT的真实运行快照；六格receipt均RUNNING、无exit_code，六个tmux均live。
  batch=Total timesteps/(4096×64)。显存/利用率仅代表该时刻，不是峰值或持续占用。

| Cell | GPU | PID | batch | 显存MiB | GPU利用率 |
|---|---|---|---|---|---|
| C_S1 | 2 | 3801995 | 1657 | 13398 | 42% |
| W_S1 | 3 | 3802060 | 1646 | 12930 | 17% |
| K_S1 | 4 | 3802104 | 1698 | 13058 | 18% |
| C_S2 | 5 | 3802148 | 1711 | 12928 | 18% |
| W_S2 | 6 | 3802226 | 1659 | 14418 | 15% |
| K_S2 | 7 | 3802422 | 1706 | 13592 | 42% |

GPU0/1各1 MiB、0%，两个step1500 eval tmux已退出；训练writer继续。
11:55 HKT磁盘剩余约4.3 TB。未停止/修改其他session任务。
Main保留Wave1 output/GPU leases；当前不是“无活跃writer”的最终closure。

## 证据等级、未运行事项与索引

- 完整性/接线为RUNTIME_PASS；本次为冻结协议下milestone experiment evidence，不代表W/K假设通过。
- step2000/2500/3000、endpoint、Wave2、Teacher/Student handoff与hardware尚未运行。
- 本milestone未修改实验实现、配置、阈值或reducer；只新增readout并同步memory三文件。无新commit/push。

[step1500 reducer](/home/baoquanc/workspace/DoorDog-A2_Piper/logs_eval/base_v26/v26_8_bilateral_opening_scaffold_decay_20260903_r3a/milestones/step1500/reducer.json)；
[step1000 readout](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v26_8/a2_piper_base_v26_8_step1000_readout_20260904.md)；
[step500/source基线索引](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v26_8/a2_piper_base_v26_8_step500_readout_20260904.md)；
[eval source supplement](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v26_8/runtime_logs/v26_8_bilateral_opening_scaffold_decay_20260903_r3a/eval_driver_off_lock.json)。

[K_S1 trace](/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v26/v26_8_bilateral_opening_scaffold_decay_20260903_r3a/train/K_S1/a2_v26_8_penalty_curriculum_trace.jsonl)；
[K_S2 trace](/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v26/v26_8_bilateral_opening_scaffold_decay_20260903_r3a/train/K_S2/a2_v26_8_penalty_curriculum_trace.jsonl)。

下一步长等待到六格step2000 checkpoint，再做12-lane评估；不按中间training log路由或修改实验变量。

