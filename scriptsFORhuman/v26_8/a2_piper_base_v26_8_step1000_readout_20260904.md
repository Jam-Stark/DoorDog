# v26-8 r3a Wave 1 — step1000 readout

As of：2026-09-04 09:21 HKT。Milestone evidence，不是 endpoint closure。

## 结果与边界

- `V26_8_MILESTONE_REPORTED`；12×exact64、integrity全0，两条 eval receipt `PASS/0`，无失败/停格。
- C_S1 的 warm-start sanity 从 step500 `TRANSIENT` 恢复为 `WARM_START_RETAINED`：RIGHT D=64，
  源为64、step500为43。C_S2在step500已 retained，冻结 reducer 按合同不重复给它 warm-start 标签。
- W_S2出现很大的下游正读数：LEFT/RIGHT S5+=60/63、complete=59/63。C_S2同时已有双侧entry，
  不能把 W 的 downstream 读数替换成 W_STAGE34_SUPPORTED 的 entry 判据。
- K_S1 RIGHT D 比 C 少9；K_S2 LEFT S5+/complete 比 C 少39/37。driver正常不等于无行为回退。
- `typed_outcomes=null`；不提前作 W/K endpoint 或 Wave2 选择。六格继续原定3000，无重跑/改config/扩预算。

## 逐格逐侧计数

每侧exact64，顺序 **D / S3+ / S4+ / open_hold / S5+ / complete**。D为handle≥0.6连续≥25步；
Sx+为max_stage≥x；open_hold为hinge≥0.25且both_contact连续≥25 control steps。均是计数，非通过率。

| Cell | LEFT | RIGHT |
|---|---|---|
| C_S1 | 63/63/63/63/63/63 | 64/64/64/64/32/32 |
| W_S1 | 56/63/63/63/63/63 | 59/60/60/60/27/26 |
| K_S1 | 64/64/64/64/63/63 | 55/61/60/60/38/38 |
| C_S2 | 63/64/64/64/58/40 | 57/64/64/64/4/0 |
| W_S2 | 64/64/64/64/60/59 | 63/63/63/63/63/63 |
| K_S2 | 60/64/60/60/19/3 | 64/64/64/64/1/1 |

## 同 source 的 arm−C

顺序 **D / S4+ / open_hold / S5+ / complete**；逐项已独立复算，与 reducer 一致。

| Arm/source | LEFT Δ | RIGHT Δ |
|---|---|---|
| W_S1 | −7/0/0/0/0 | −5/−4/−4/−5/−6 |
| K_S1 | +1/+1/+1/0/0 | −9/−4/−4/+6/+6 |
| W_S2 | +1/0/0/+2/+19 | +6/−1/−1/+59/+63 |
| K_S2 | −3/−4/−4/−39/−37 | +7/0/0/−3/+1 |

K_S1 RIGHT D 当前超过 NO_REGRESS 的8计数容差；其min-side S5+虽比C多6，但未达到+8。
这些只是本 milestone 与冻结规则的数值对应，不给提前 endpoint 标签。C_S1当前min-side S5+=32、
min-side open_hold=63且双侧D≥32；C_S2满足ENTRY_MET数值条件，正式C报告标签也留到endpoint。

## 历史反向读数：全部差值

历史源为 v26-7 Q05 同seed step3000；历史open_hold使用前次已验证的原始trace只读回算，原v26-7
reducer/artifact未改动。顺序 **D / S3+ / S4+ / open_hold / S5+ / complete**。

| Cell−同seed source | LEFT Δ | RIGHT Δ |
|---|---|---|
| C_S1 | +1/−1/+1/+1/+1/+1 | 0/0/0/0/+14/+28 |
| W_S1 | −6/−1/+1/+1/+1/+1 | −5/−4/−4/−4/+9/+22 |
| K_S1 | +2/0/+2/+2/+1/+1 | −9/−3/−4/−4/+20/+34 |
| C_S2 | +3/+4/+64/+64/+58/+40 | 0/0/0/0/−17/0 |
| W_S2 | +4/+4/+64/+64/+60/+59 | +6/−1/−1/−1/+42/+63 |
| K_S2 | 0/+4/+60/+60/+19/+3 | +7/0/0/0/−20/+1 |

相对已冻结step500的变化也全部保留，同样顺序：

| Cell：step1000−step500 | LEFT Δ | RIGHT Δ |
|---|---|---|
| C_S1 | +7/−1/−1/−1/−1/−1 | +21/0/0/0/+6/+6 |
| W_S1 | −3/−1/−1/−1/0/0 | +26/−4/−4/−4/+1/+1 |
| K_S1 | +10/0/+2/+2/+1/+1 | −1/−2/−3/−3/+13/+15 |
| C_S2 | +18/+1/+17/+17/+49/+40 | −4/+2/+2/+2/+3/0 |
| W_S2 | +3/0/0/0/+23/+59 | +6/0/0/0/+49/+62 |
| K_S2 | −4/0/−4/−4/+3/+3 | +1/0/0/0/−1/+1 |

重要边界：W_S1/K_S1的RIGHT admission/opening仍低于源；C_S2/K_S2 RIGHT S5+分别4/1，仍低于源21，
而W_S2为63。K_S2 LEFT opening相对step500从64降到60，downstream也明显落后同源C/W。
S1 LEFT complete三格均63（源62；C的step500为64），始终只记录，不作为source选择或route依据。
这些是当前matched-source计数与轨迹，不宣称跨seed普遍效果、统计显著性或hardware能力。

## K scale 与双侧 driver 轨迹

所有统计限定 `common_step <= 1000×64 = 64000`。600/700/800/900/1000五个边界，两格K的
最后 `scale_after` 均为float32 floor `0.20000000298023224`；不把边界快照误写成每个update绝对恒定。
先前0–500轨迹见step500 readout。

以下为各区间 `(lo×64, hi×64]`、仅consumed=true的natural reached/sample；左右独立汇总，
skipped保留的pending不重复计数。区间rate用于描述轨迹，实际更新仍用每个pending window的min-side。

| K | batch区间 | LEFT reached/sample（rate） | RIGHT reached/sample（rate） |
|---|---|---|---|
| K_S1 | 500–600 | 16289/16337（0.997062） | 13293/13312（0.998573） |
| K_S1 | 600–700 | 16490/16507（0.998970） | 13240/13255（0.998868） |
| K_S1 | 700–800 | 16527/16548（0.998731） | 13252/13264（0.999095） |
| K_S1 | 800–900 | 16755/16772（0.998986） | 13085/13126（0.996876） |
| K_S1 | 900–1000 | 16854/16918（0.996217） | 13044/13071（0.997934） |
| K_S2 | 500–600 | 13381/13452（0.994722） | 13435/13525（0.993346） |
| K_S2 | 600–700 | 13361/13417（0.995826） | 13563/13643（0.994136） |
| K_S2 | 700–800 | 13380/13423（0.996797） | 13667/13746（0.994253） |
| K_S2 | 800–900 | 13203/13269（0.995026） | 13672/13780（0.992163） |
| K_S2 | 900–1000 | 13318/13392（0.994474） | 13670/13772（0.992594） |

| 累计至1000指标 | K_S1 | K_S2 |
|---|---:|---:|
| trace rows | 63980 | 63980 |
| consumed / skipped | 52001 / 11979 | 51090 / 12890 |
| first update below0.95（0-based） | 944 | 8617 |
| scale_min | 0.20000000298023224 | 0.20000000298023224 |
| share of updates below0.5 | 0.8565176617693029 | 0.7240387621131603 |
| reversal_count | 0 | 0 |

`k_driver_mismatch_cells_ever=[]`。K_S2已engaged的事实不变，本次LEFT S4+=60，未触发driver invalid；
不能由driver已达到mastery直接推出Stage5/complete会改善。

## 完整性、receipt、资源与证据

- 两条 `v26_8_eval_step1000_gpu{0,1}_r3a` receipt 均 `PASS/0`；P0两项资产均HTTP200，六键proxy显式进入命令。
- reducer完成exact64唯一coverage、自然首episode、side/seed、trace连续性、integrity=0、六格resolved
  config与source checkpoint路径/SHA/strict actor+RMS receipt核验；未改变source lock或canonical plan。
- 12份runtime config另行确认对应cell的`model_step_001000.pt`、curriculum=false、driver=null。
- 09:17 HKT，C_S1/W_S1/K_S1/C_S2/W_S2/K_S2的batch为1145/1140/1181/1189/1155/1186；
  六格没有exit_code。batch口径为Total timesteps/(4096×64)。
- 同时GPU0/1各1 MiB、0%；GPU2–7显存依次13322/13322/13324/14114/13342/13346 MiB，
  utilization为16/48/17/7/39/24%的瞬时快照。step1000两个eval tmux已退出，六格训练writer继续。
- 证据为注册协议下milestone experiment evidence，完整性/接线为RUNTIME_PASS；未宣称W/K假设通过。
  未运行step1500–3000、endpoint、Wave2、Teacher/Student handoff或hardware。
- Main仍持有Wave1 output/GPU leases；没有对其他session的任务做停止/修改，没有新commit或push。

## 证据与下一步

- [step1000 reducer](/home/baoquanc/workspace/DoorDog-A2_Piper/logs_eval/base_v26/v26_8_bilateral_opening_scaffold_decay_20260903_r3a/milestones/step1000/reducer.json)
- [step500 readout及历史source索引](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v26_8/a2_piper_base_v26_8_step500_readout_20260904.md)
- [eval-only source supplement](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v26_8/runtime_logs/v26_8_bilateral_opening_scaffold_decay_20260903_r3a/eval_driver_off_lock.json)
- [K_S1 trace](/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v26/v26_8_bilateral_opening_scaffold_decay_20260903_r3a/train/K_S1/a2_v26_8_penalty_curriculum_trace.jsonl)
- [K_S2 trace](/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v26/v26_8_bilateral_opening_scaffold_decay_20260903_r3a/train/K_S2/a2_v26_8_penalty_curriculum_trace.jsonl)

继续长等待到六格step1500，再做12-lane评估；不基于中间训练log提前路由或修调实验变量。
