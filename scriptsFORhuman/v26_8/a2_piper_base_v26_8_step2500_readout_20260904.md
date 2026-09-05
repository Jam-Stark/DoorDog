# v26-8 r3a Wave 1 — step2500 readout

As of：2026-09-04 19:36 HKT。Milestone evidence，不提前替代step3000 endpoint。

## 结果与边界

- `V26_8_MILESTONE_REPORTED`；12×exact64、integrity全0、eval receipt PASS/0，无失败/停格。
- K_S2 LEFT S5+/complete从step2000的0/0恢复到63/63，不能沿用“下游未形成”的旧描述；
  但两侧D降至37/31，相对C均−26，形成下游高计数与D负差并存。
- W_S2 LEFT D相对C−18，而双侧S5+/complete均64；W_S1 LEFT D相对C−9。
  这些仍超过冻结NO_REGRESS的8计数容差，不以complete覆盖或修改guard。
- K_S1 min-side S5+比C多18，RIGHT complete比C多27；不能忽略这些正读数，也不能绕过跨source的NO_REGRESS条件。
- `typed_outcomes=null`，无提前成功或失败裁定。六格继续至3000，原配置、阈值与预算不变。

## 逐格逐侧计数

每侧exact64；顺序 **D / S3+ / S4+ / open_hold / S5+ / complete**。D为handle≥0.6连续≥25步；
Sx+为max_stage≥x；open_hold为hinge≥0.25且both_contact连续≥25 control steps。都是计数，不是通过率。

| Cell | LEFT | RIGHT |
|---|---|---|
| C_S1 | 64/64/64/64/64/64 | 40/63/63/63/38/29 |
| W_S1 | 55/64/64/64/64/64 | 64/64/64/64/47/47 |
| K_S1 | 63/64/64/63/64/64 | 57/63/63/62/56/56 |
| C_S2 | 63/64/63/63/63/63 | 57/63/63/63/63/63 |
| W_S2 | 45/64/64/64/64/64 | 61/64/64/64/64/64 |
| K_S2 | 37/64/63/63/63/63 | 31/64/64/64/64/64 |

## 同source的arm−C

顺序 **D / S4+ / open_hold / S5+ / complete**；所有差值已独立复算，与reducer一致。

| Arm/source | LEFT Δ | RIGHT Δ |
|---|---|---|
| W_S1 | −9/0/0/0/0 | +24/+1/+1/+9/+18 |
| K_S1 | −1/0/−1/0/0 | +17/0/−1/+18/+27 |
| W_S2 | −18/+1/+1/+1/+1 | +4/+1/+1/+1/+1 |
| K_S2 | −26/0/0/0/0 | −26/+1/+1/+1/+1 |

D与S5+/complete明显不是同一个量。本阶段仍按预注册guard裁定，不能把D负差泛化为所有开门指标都下降；
也不能因full-chain计数高而删除D负差。未做新的因果诊断来解释这种分离。

## 与历史源及上一milestone的全部差值

历史源为v26-7 Q05同seed step3000；历史open_hold沿用已验证的原始trace只读回算，历史artifact未改。
两表顺序均为 **D / S3+ / S4+ / open_hold / S5+ / complete**，所有负值包括非路由项均保留。

| Cell−同seed source | LEFT Δ | RIGHT Δ |
|---|---|---|
| C_S1 | +2/0/+2/+2/+2/+2 | −24/−1/−1/−1/+20/+25 |
| W_S1 | −7/0/+2/+2/+2/+2 | 0/0/0/0/+29/+43 |
| K_S1 | +1/0/+2/+1/+2/+2 | −7/−1/−1/−2/+38/+52 |
| C_S2 | +3/+4/+63/+63/+63/+63 | 0/−1/−1/−1/+42/+63 |
| W_S2 | −15/+4/+64/+64/+64/+64 | +4/0/0/0/+43/+64 |
| K_S2 | −23/+4/+63/+63/+63/+63 | −26/0/0/0/+43/+64 |

| Cell：step2500−step2000 | LEFT Δ | RIGHT Δ |
|---|---|---|
| C_S1 | 0/0/0/0/0/0 | −13/−1/−1/−1/+2/−5 |
| W_S1 | +1/+1/+1/+1/+1/+1 | +10/+2/+2/+2/+1/+2 |
| K_S1 | 0/+1/+1/0/+1/+1 | +15/−1/−1/−2/+2/+4 |
| C_S2 | +5/+1/0/0/0/0 | −2/−1/−1/−1/−1/−1 |
| W_S2 | −6/0/0/0/+1/+1 | −1/+1/+1/+2/+1/+1 |
| K_S2 | −25/0/+1/+1/+63/+63 | −12/0/+1/+1/+1/+1 |

相对源，C_S1 RIGHT D−24、W_S1 LEFT D−7、W_S2 LEFT D−15、K_S1 RIGHT D−7，
K_S2 LEFT/RIGHT D−23/−26；S1及C_S2部分侧格的S3+/S4+/open_hold也低于源。
相对step2000，C_S1 RIGHT complete再降5，K_S2 LEFT下游大幅恢复，但其两侧D进一步下降。
源Q05_S1 LEFT的62 complete在三格中均为64，只记录、不路由；未宣称Teacher、统计普遍性或hardware能力。

## K scale与双侧driver轨迹

仅纳入`common_step<=2500×64=160000`；首个超界row不进入统计。
两格K在2100/2200/2300/2400/2500边界的最后scale均约0.2（float32 floor），不声明每个update恒定。

各区间`(lo×64,hi×64]`只累计consumed=true的natural reached/sample，左右独立；
skipped保留的pending不重复计数。区间rate仅描述轨迹，实际scale仍按每个window的min-side更新。

| K | batch区间 | LEFT reached/sample（rate） | RIGHT reached/sample（rate） |
|---|---|---|---|
| K_S1 | 2000–2100 | 18848/18917（0.996352） | 12818/12900（0.993643） |
| K_S1 | 2100–2200 | 18969/19053（0.995591） | 12797/12882（0.993402） |
| K_S1 | 2200–2300 | 18999/19097（0.994868） | 12819/12868（0.996192） |
| K_S1 | 2300–2400 | 19013/19072（0.996906） | 13066/13118（0.996036） |
| K_S1 | 2400–2500 | 19029/19085（0.997066） | 13371/13432（0.995459） |
| K_S2 | 2000–2100 | 13173/13246（0.994489） | 17247/17337（0.994809） |
| K_S2 | 2100–2200 | 13195/13246（0.996150） | 17436/17492（0.996799） |
| K_S2 | 2200–2300 | 13064/13112（0.996339） | 17527/17580（0.996985） |
| K_S2 | 2300–2400 | 13152/13206（0.995911） | 17560/17635（0.995747） |
| K_S2 | 2400–2500 | 13359/13397（0.997164） | 17515/17567（0.997040） |

| 累计至2500指标 | K_S1 | K_S2 |
|---|---|---|
| trace rows | 159977 | 159968 |
| consumed / skipped | 131559 / 28418 | 129269 / 30699 |
| first_update_below_0.95 | 944 | 8617 |
| scale_min | 0.20000000298023224 | 0.20000000298023224 |
| share_of_updates_below_0.5 | 0.9426167511579789 | 0.889627925585117 |
| reversal_count | 0 | 0 |

`k_driver_mismatch_cells_ever=[]`；K_S2 LEFT S4+=63，未触发driver invalid。
独立trace统计与reducer的row/skipped/reversal一致。机制检查和行为效果分开报告。

## 完整性、receipt与活跃资源

- 两条`v26_8_eval_step2500_gpu{0,1}_r3a`均PASS/0，12份metrics齐全，两个eval tmux已退出。
- P0两资产均HTTP200，六键proxy显式进入receipt命令；沿用既定eval source supplement。
- reducer核对exact64唯一env覆盖、自然first episode、side/seed、trace连续性、integrity=0、六格
  resolved config、源checkpoint路径/SHA和strict actor+RMS receipt；canonical plan/source lock未改。
- 12份runtime config另行确认对应cell的`model_step_002500.pt`、curriculum=false、driver=null。
- 以下为2026-09-04 19:32 HKT的只读QA快照：六格state=RUNNING、process_returncode=null、exit_code.txt未生成、
  六个tmux均live；batch=Total timesteps/(4096×64)。显存/利用率只是瞬时快照。

| Cell | GPU | PID | batch | 显存MiB | GPU利用率 |
|---|---|---|---|---|---|
| C_S1 | 2 | 3801995 | 2679 | 21826 | 95% |
| W_S1 | 3 | 3802060 | 2650 | 14176 | 15% |
| K_S1 | 4 | 3802104 | 2733 | 13918 | 22% |
| C_S2 | 5 | 3802148 | 2733 | 15930 | 25% |
| W_S2 | 6 | 3802226 | 2666 | 13082 | 10% |
| K_S2 | 7 | 3802422 | 2722 | 13082 | 17% |

GPU0/1各1 MiB、0%。未停止/修改其他session；六格writer与Main的Wave1 output/GPU leases继续有效。
这不是最终“无活跃writer”closure。

## 证据等级、未运行事项与索引

完整性/接线为RUNTIME_PASS，本次为冻结协议下milestone experiment evidence，不代表W/K假设通过。
step3000 endpoint、Wave2、Teacher/Student handoff与hardware尚未运行。
本milestone只新增readout并同步memory三文件，未改实验代码/config/threshold/reducer，无新commit/push。

[step2500 reducer](/home/baoquanc/workspace/DoorDog-A2_Piper/logs_eval/base_v26/v26_8_bilateral_opening_scaffold_decay_20260903_r3a/milestones/step2500/reducer.json)；
[step2000 readout](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v26_8/a2_piper_base_v26_8_step2000_readout_20260904.md)；
[step500/source基线索引](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v26_8/a2_piper_base_v26_8_step500_readout_20260904.md)；
[eval source supplement](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v26_8/runtime_logs/v26_8_bilateral_opening_scaffold_decay_20260903_r3a/eval_driver_off_lock.json)。

[K_S1 trace](/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v26/v26_8_bilateral_opening_scaffold_decay_20260903_r3a/train/K_S1/a2_v26_8_penalty_curriculum_trace.jsonl)；
[K_S2 trace](/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v26/v26_8_bilateral_opening_scaffold_decay_20260903_r3a/train/K_S2/a2_v26_8_penalty_curriculum_trace.jsonl)。

下一步长等待六格3000终点，再做12-lane endpoint评估、train receipt finalize、typed outcomes与closure。
Wave2只在冻结endpoint与closure后，按plan §9条件通知Owner并启动。

