# v26-8 r3a Wave 1 — step2000 readout

As of：2026-09-04 16:11 HKT。Milestone evidence，endpoint仍为step3000。

## 结果与边界

- `V26_8_MILESTONE_REPORTED`；12×exact64、integrity全0、两条eval receipt PASS/0，无失败/停格。
- K_S2 LEFT已有62个S4+/open_hold，却为S5+/complete=0/0；相对C两项均−63，不能用driver正常掩盖。
- K_S1 min-side S5+比C多18，但RIGHT D少11；W_S1 LEFT D比C少10，K_S2 RIGHT D比C少16。
  当前存在超出NO_REGRESS的8计数容差的负差，不能只用正下游指标宣称支持。
- W_S1 min-side S5+的配对差从step1500的−8变为+10，说明该读数并非持续不变。
- C_S2继续形成entry与高下游计数；W的entry支持仍按冻结规则，而非按complete挑选结论。
- `typed_outcomes=null`；这些数值不构成提前endpoint判决。六格继续2500/3000，无改config、重跑或扩预算。

## 逐格逐侧计数

每侧exact64；顺序 **D / S3+ / S4+ / open_hold / S5+ / complete**。D为handle≥0.6连续≥25步；
Sx+为max_stage≥x；open_hold为hinge≥0.25且both_contact连续≥25 control steps。均为计数，不是通过率。

| Cell | LEFT | RIGHT |
|---|---|---|
| C_S1 | 64/64/64/64/64/64 | 53/64/64/64/36/34 |
| W_S1 | 54/63/63/63/63/63 | 54/62/62/62/46/45 |
| K_S1 | 63/63/63/63/63/63 | 42/64/64/64/54/52 |
| C_S2 | 58/63/63/63/63/63 | 59/64/64/64/64/64 |
| W_S2 | 51/64/64/64/63/63 | 62/63/63/62/63/63 |
| K_S2 | 62/64/62/62/0/0 | 43/64/63/63/63/63 |

## 同source的arm−C

顺序 **D / S4+ / open_hold / S5+ / complete**。逐项已独立复算，与reducer一致。

| Arm/source | LEFT Δ | RIGHT Δ |
|---|---|---|
| W_S1 | −10/−1/−1/−1/−1 | +1/−2/−2/+10/+11 |
| K_S1 | −1/−1/−1/−1/−1 | −11/0/0/+18/+18 |
| W_S2 | −7/+1/+1/0/0 | +3/−1/−2/−1/−1 |
| K_S2 | +4/−1/−1/−63/−63 | −16/−1/−1/−1/−1 |

D下降与下游到达上升可以同时出现；仍保留预注册D guard，既不以complete增加抹掉D负差，
也不把一个D标签外推为所有行为指标都变差。K_S2 LEFT的下游0/0则是独立、直接的负读数。

## 历史与上轮的全部差值

历史源为v26-7 Q05同seed step3000，open_hold沿用已验证的历史trace只读回算，历史文件未改。
顺序均为 **D / S3+ / S4+ / open_hold / S5+ / complete**；负值包括非路由指标，全部列出。

| Cell−同seed source | LEFT Δ | RIGHT Δ |
|---|---|---|
| C_S1 | +2/0/+2/+2/+2/+2 | −11/0/0/0/+18/+30 |
| W_S1 | −8/−1/+1/+1/+1/+1 | −10/−2/−2/−2/+28/+41 |
| K_S1 | +1/−1/+1/+1/+1/+1 | −22/0/0/0/+36/+48 |
| C_S2 | −2/+3/+63/+63/+63/+63 | +2/0/0/0/+43/+64 |
| W_S2 | −9/+4/+64/+64/+63/+63 | +5/−1/−1/−2/+42/+63 |
| K_S2 | +2/+4/+62/+62/0/0 | −14/0/−1/−1/+42/+63 |

| Cell：step2000−step1500 | LEFT Δ | RIGHT Δ |
|---|---|---|
| C_S1 | 0/0/0/0/0/0 | −9/0/0/0/−5/−7 |
| W_S1 | −8/0/0/0/0/0 | −3/0/0/0/+13/+12 |
| K_S1 | 0/0/0/0/0/0 | −15/+1/+1/+1/+7/+7 |
| C_S2 | +1/−1/+5/+5/+6/+7 | −3/+1/+1/+1/+1/+1 |
| W_S2 | −11/0/0/0/−1/0 | −2/−1/−1/−2/−1/−1 |
| K_S2 | +6/0/+6/+6/−5/−1 | +5/0/−1/−1/−1/−1 |

相对源，S1三格RIGHT D均下降；W_S1双侧D、W_S2 LEFT D、C_S2 LEFT D、K_S2 RIGHT D下降。
W_S1/K_S1部分S3+、W_S1/W_S2/K_S2部分S4+/open_hold也低于源。相对step1500，C_S1 RIGHT
S5+/complete回落，W_S1/K_S1 RIGHT下游上升；K_S2 LEFT S5+/complete继续降至0/0。
源Q05_S1 LEFT的62 complete在C/W/K中为64/63/63，始终只报告，不作source选择或route依据。
不宣称跨seed普遍效果、统计显著性、Teacher或hardware能力。

## K scale与双侧driver轨迹

只纳入`common_step<=2000×64=128000`；首个超界row不参与统计。
两格K在1600/1700/1800/1900/2000边界的最后scale均约0.2（float32 floor），
不把边界快照写成每个update恒定。先前轨迹见既有readout。

各区间`(lo×64,hi×64]`只累计consumed=true的natural reached/sample，左右分开；
skipped保留的pending不重复计数。区间rate仅描述轨迹，实际决策仍使用每个pending window的min-side。

| K | batch区间 | LEFT reached/sample（rate） | RIGHT reached/sample（rate） |
|---|---|---|---|
| K_S1 | 1500–1600 | 17951/17991（0.997777） | 12846/12897（0.996046） |
| K_S1 | 1600–1700 | 17939/17996（0.996833） | 12724/12793（0.994606） |
| K_S1 | 1700–1800 | 18343/18413（0.996198） | 12875/12919（0.996594） |
| K_S1 | 1800–1900 | 18417/18481（0.996537） | 12942/12993（0.996075） |
| K_S1 | 1900–2000 | 18745/18801（0.997021） | 12873/12919（0.996439） |
| K_S2 | 1500–1600 | 13270/13337（0.994976） | 15067/15134（0.995573） |
| K_S2 | 1600–1700 | 13253/13329（0.994298） | 15637/15715（0.995037） |
| K_S2 | 1700–1800 | 13245/13326（0.993922） | 16218/16290（0.995580） |
| K_S2 | 1800–1900 | 13219/13301（0.993835） | 16760/16845（0.994954） |
| K_S2 | 1900–2000 | 13205/13287（0.993829） | 16971/17076（0.993851） |

| 累计至2000指标 | K_S1 | K_S2 |
|---|---|---|
| trace rows | 127979 | 127970 |
| consumed / skipped | 104866 / 23113 | 102791 / 25179 |
| first_update_below_0.95 | 944 | 8617 |
| scale_min | 0.20000000298023224 | 0.20000000298023224 |
| share_of_updates_below_0.5 | 0.9282694817118433 | 0.862030163319528 |
| reversal_count | 0 | 0 |

`k_driver_mismatch_cells_ever=[]`；K_S2 LEFT S4+=62，未触发driver invalid。
独立trace的row/skipped/reversal统计与reducer一致。高Stage4 driver并不保证Stage5或complete改善。

## 完整性、receipt与活跃资源

- 两条`v26_8_eval_step2000_gpu{0,1}_r3a`均PASS/0，12份metrics齐全，两个eval tmux已退出。
- P0两资产均HTTP200；六键proxy显式记录在receipt command，eval接线与前轮一致。
- reducer核对exact64唯一env覆盖、自然首episode、side/seed、trace连续性、integrity=0、六格resolved
  config、源checkpoint路径/SHA与strict actor+RMS load receipt。canonical plan和source lock未变。
- 另行核对12份runtime config：各自cell的`model_step_002000.pt`、curriculum=false、driver=null。
- 下表为45分钟定时信号后、reducer执行前的只读QA快照。六格state=RUNNING、
  process_returncode=null、exit_code.txt尚未生成，六个tmux均live。batch=Total timesteps/(4096×64)。

| Cell | GPU | PID | batch | 显存MiB | GPU利用率 |
|---|---|---|---|---|---|
| C_S1 | 2 | 3801995 | 2172 | 13220 | 16% |
| W_S1 | 3 | 3802060 | 2155 | 14146 | 49% |
| K_S1 | 4 | 3802104 | 2217 | 13788 | 10% |
| C_S2 | 5 | 3802148 | 2236 | 12942 | 18% |
| W_S2 | 6 | 3802226 | 2166 | 13050 | 23% |
| K_S2 | 7 | 3802422 | 2229 | 12942 | 16% |

GPU0/1各1 MiB、0%。显存/利用率仅为快照；未停止或更改其他session任务。
Main仍持有Wave1 output/GPU leases，六格训练writer继续；不是最终“无活跃writer”closure。

## 证据等级、未运行事项与索引

完整性与接线为RUNTIME_PASS；本次为冻结协议下milestone experiment evidence，不等于W/K假设通过。
step2500/3000、endpoint、Wave2、Teacher/Student handoff与hardware尚未运行。
本milestone只新增readout并同步memory三文件，没有改实验实现/config/threshold/reducer，也没有新commit/push。

[step2000 reducer](/home/baoquanc/workspace/DoorDog-A2_Piper/logs_eval/base_v26/v26_8_bilateral_opening_scaffold_decay_20260903_r3a/milestones/step2000/reducer.json)；
[step1500 readout](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v26_8/a2_piper_base_v26_8_step1500_readout_20260904.md)；
[step500/source基线索引](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v26_8/a2_piper_base_v26_8_step500_readout_20260904.md)；
[eval source supplement](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v26_8/runtime_logs/v26_8_bilateral_opening_scaffold_decay_20260903_r3a/eval_driver_off_lock.json)。

[K_S1 trace](/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v26/v26_8_bilateral_opening_scaffold_decay_20260903_r3a/train/K_S1/a2_v26_8_penalty_curriculum_trace.jsonl)；
[K_S2 trace](/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v26/v26_8_bilateral_opening_scaffold_decay_20260903_r3a/train/K_S2/a2_v26_8_penalty_curriculum_trace.jsonl)。

下一步长等待到六格step2500 checkpoint，再做12-lane评估；不按中间training log提前路由或修改变量。

