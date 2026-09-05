# v26-8 r3a Wave 1 — step500 readout

As of：2026-09-04 05:54 HKT。Milestone evidence，不是 endpoint closure。

## 结果与边界

- `V26_8_MILESTONE_REPORTED`；12 lane × exact64，所有 integrity 为 0；无失败、无停格。
- C_S1 为 `WARM_START_TRANSIENT`：RIGHT D 从源 64 降至 43，未满足 source−16；step1000 复查。
  C_S2 为 `WARM_START_RETAINED`。
- K_S1、K_S2 均已 ENGAGED，scale 到 float32 floor `0.20000000298023224`。K_S2 与原惰性预期相反，
  但本 milestone LEFT S4+=64，`k_driver_mismatch_cells_ever=[]`，没有本次 driver mismatch。
- `typed_outcomes=null`，不提前给 W/K endpoint 标签。C_S2 已满足 ENTRY_MET 的数值条件，不能因此把
  W 的正配对差解释成 W 的独有 entry 贡献；endpoint 仍按 step3000 冻结规则裁定。
- 六格继续原定 3000 batches；无重跑、阈值调整、训练 config 变更或追加预算。Wave 2 尚未裁定/运行。

## 逐格逐侧计数

每侧分母 exact64；D 为 handle≥0.6 连续≥25 control steps；Sx+ 为 max_stage≥x 到达计数；
open_hold 为 hinge≥0.25 且 both_contact 连续≥25 control steps 的保持计数；complete 仅报告。
表中顺序均为 **D / S3+ / S4+ / open_hold / S5+ / complete**，不是通过率。

| Cell | LEFT | RIGHT |
|---|---|---|
| C_S1 | 56/64/64/64/64/64 | 43/64/64/64/26/26 |
| W_S1 | 59/64/64/64/63/63 | 33/64/64/64/26/25 |
| K_S1 | 54/64/62/62/62/62 | 56/63/63/63/25/23 |
| C_S2 | 45/63/47/47/9/0 | 61/62/62/62/1/0 |
| W_S2 | 61/64/64/64/37/0 | 57/63/63/63/14/1 |
| K_S2 | 64/64/64/64/16/0 | 63/64/64/64/2/0 |

## 同 source 的 arm−C

顺序为 **D / S4+ / open_hold / S5+ / complete**。已独立复算每个差值与 reducer 一致。

| Arm/source | LEFT Δ | RIGHT Δ |
|---|---|---|
| W_S1 | +3/0/0/−1/−1 | −10/0/0/0/−1 |
| K_S1 | −2/−2/−2/−2/−2 | +13/−1/−1/−1/−3 |
| W_S2 | +16/+17/+17/+28/0 | −4/+1/+1/+13/+1 |
| K_S2 | +19/+17/+17/+7/0 | +2/+2/+2/+1/0 |

W_S1 RIGHT D 比 C 少10，超出当前 NO_REGRESS 的8计数容差；这里只记录 milestone 事实，不提前给
`W_REGRESSED` endpoint 标签。K_S1 min-side S5+ 为25，C_S1 为26，本次未见下游提升。

## 与历史源基线的全部差值

历史基线为 v26-7 Q05 同 seed step3000，非同批次训练对照；arm 归因只使用上表。历史原 reducer
没有 open_hold 字段，下表所用历史 open_hold 是按 v26-8 定义对 immutable 原始 trace 的只读回算：
S1 LEFT/RIGHT=62/64，S2 LEFT/RIGHT=0/64；未修改 v26-7 文件。

顺序为 **D / S3+ / S4+ / open_hold / S5+ / complete**；负值全部保留，不因不参与路由而省略。

| Cell−同 seed source | LEFT Δ | RIGHT Δ |
|---|---|---|
| C_S1 | −6/0/+2/+2/+2/+2 | −21/0/0/0/+8/+22 |
| W_S1 | −3/0/+2/+2/+1/+1 | −31/0/0/0/+8/+21 |
| K_S1 | −8/0/0/0/0/0 | −8/−1/−1/−1/+7/+19 |
| C_S2 | −15/+3/+47/+47/+9/0 | +4/−2/−2/−2/−20/0 |
| W_S2 | +1/+4/+64/+64/+37/0 | 0/−1/−1/−1/−7/+1 |
| K_S2 | +4/+4/+64/+64/+16/0 | +6/0/0/0/−19/0 |

重要反向读数：S1 六个侧格 D 均低于源；S2 RIGHT S5+ 从21降到 C/W/K 的1/14/2；C_S2 LEFT D
下降15，但三条 arm 的 LEFT opening/hold 均从0上升。D 与下游计数不单调，不能用 complete 增加
抹掉 D 下降，也不能仅凭 D 下降宣称策略已失去开门能力。源 Q05_S1 LEFT 的62 complete 在
C/W/K 中变为64/63/62，始终只是非路由观察。

## K scale 与两侧 driver 轨迹

严格只使用 `common_step <= 500×64 = 32000` 的训练 trace，不读未来训练结果。
scale 取各100-batch边界之前最后一个 trace row；float32 floor 下表简写为0.200000。

| 边界 batch | K_S1 scale | K_S2 scale |
|---:|---:|---:|
| 0 | 1.000000 | 1.000000 |
| 100 | 0.622443 | 1.000000 |
| 200 | 0.377755 | 0.726604 |
| 300 | 0.226475 | 0.442339 |
| 400 | 0.200000 | 0.269231 |
| 500 | 0.200000 | 0.200000 |

以下 driver 轨迹按100-batch区间 `(lo×64, hi×64]` 汇总 **consumed=true** 的 natural
reached/sample；缺侧 skipped 行保留 pending，故绝不能重复计入分母。左右侧独立列出。
这是区间描述，实际 scale 决策仍使用每个 pending window 的 min-side rate，不能用区间汇总值
替换原更新公式。

| K | batch区间 | LEFT reached/sample（rate） | RIGHT reached/sample（rate） |
|---|---|---|---|
| K_S1 | 0–100 | 12907/13903（0.928361） | 13455/14470（0.929855） |
| K_S1 | 100–200 | 13224/13318（0.992942） | 13790/13828（0.997252） |
| K_S1 | 200–300 | 14472/14547（0.994844） | 13547/13574（0.998011） |
| K_S1 | 300–400 | 15271/15332（0.996021） | 13413/13452（0.997101） |
| K_S1 | 400–500 | 16039/16081（0.997388） | 13205/13236（0.997658） |
| K_S2 | 0–100 | 1314/17154（0.076600） | 13218/14068（0.939579） |
| K_S2 | 100–200 | 11987/14893（0.804875） | 13352/13380（0.997907） |
| K_S2 | 200–300 | 13825/14066（0.982866） | 13592/13636（0.996773） |
| K_S2 | 300–400 | 13103/13159（0.995744） | 13494/13525（0.997708） |
| K_S2 | 400–500 | 13373/13448（0.994423） | 13386/13434（0.996427） |

| 指标 | K_S1 | K_S2 |
|---|---:|---:|
| trace rows | 31984 | 31988 |
| consumed / skipped | 25725 / 6259 | 25716 / 6272 |
| first update below0.95（0-based） | 944 | 8617 |
| first common_step below0.95 | 957 | 8626 |
| scale_min | 0.20000000298023224 | 0.20000000298023224 |
| share of updates below0.5 | 0.7129814907453726 | 0.44804301613104913 |
| reversal_count | 0 | 0 |

K_S2 的 LEFT natural Stage4 轨迹从低水平升高后才出现明显 decay，与本次 exact64 LEFT S4+=64
方向一致。这是机制/评估一致性观察，不证明 K 导致 entry；C_S2 本次也已出现 entry。

## 完整性、receipt、资源与证据

- 两条 `v26_8_eval_step500_gpu{0,1}_r3a` receipt 均 `PASS/0`；12 lane 均成功完成64个 first episode。
- reducer 检查了 exact64 唯一 env_id、side/seed、natural first-episode trace、连续 step_index、
  integrity=0、六格 resolved training contract、source checkpoint 路径/SHA 与 strict actor+RMS load receipt。
- 另外直接检查12份 runtime config：每条 checkpoint 均为对应 cell 的 `model_step_000500.pt`，
  `reward_penalty_curriculum=false` 且 `a2_v26_8_penalty_driver=null`。eval-only 接线修复得到
  `RUNTIME_PASS`，未改变已运行训练的 source/config/plan binding。
- 05:52 HKT：C_S1/W_S1/K_S1/C_S2/W_S2/K_S2 为 batch623/620/652/659/639/655，六个训练 tmux
  均 live、无 exit_code。batch=`Total timesteps/(4096×64)`，不能除以4096冒充 batch。
- 05:50 HKT GPU0/1 各1 MiB、0%（评估结束）；GPU2–7 分别13032/19990/13838/13308/13030/14498 MiB，
  utilization 为37/0/33/36/48/14%的瞬时快照。没有停止或更改其他 session 的任务。
- 证据等级：完整性与接线 `RUNTIME_PASS`；本 milestone 为注册协议下的 experiment evidence，
  不代表 W/K 假设通过。尚未运行 step1000–3000、endpoint、Wave2、hardware 或 Teacher/Student handoff。
- 活跃 writer：六格训练；Main 持有 Wave1 output/GPU lease。两条 step500 eval writer/tmux 已退出。

## 证据索引与下一步

- [step500 reducer](/home/baoquanc/workspace/DoorDog-A2_Piper/logs_eval/base_v26/v26_8_bilateral_opening_scaffold_decay_20260903_r3a/milestones/step500/reducer.json)
- [历史 source reducer](/home/baoquanc/workspace/DoorDog-A2_Piper/logs_eval/base_v26/v26_7_bilateral_native_unlatch_20260902/milestones/step3000/reducer.json)
- [eval-only addendum](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v26_8/a2_piper_base_v26_8_eval_driver_off_addendum_20260904.md)
- [eval source supplement](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v26_8/runtime_logs/v26_8_bilateral_opening_scaffold_decay_20260903_r3a/eval_driver_off_lock.json)
- [K_S1 trace](/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v26/v26_8_bilateral_opening_scaffold_decay_20260903_r3a/train/K_S1/a2_v26_8_penalty_curriculum_trace.jsonl)
- [K_S2 trace](/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v26/v26_8_bilateral_opening_scaffold_decay_20260903_r3a/train/K_S2/a2_v26_8_penalty_curriculum_trace.jsonl)

下一步长等待到六格 step1000 checkpoint，再按既定命令启动12-lane评估；复查 C_S1 warm-start transient。
不按中间 training log 改判、不新增测试/护栏、不修改冻结 reducer。两次获准 commit 已在前序完成；
本次及 r3/r3a 后续改动仍未 commit，未 push。
