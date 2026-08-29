# A2+PiPER base_v26-3 event-time creation execution closure

更新时间：2026-08-28 03:25 HKT  
阶段状态：`v26_3_complete_not_admitted`  
main typed outcome：`MONOTONE_CREATION_SEED_OR_SIDE_UNSTABLE`  
Teacher boundary：`V26_3_MECHANISM_PASS_NO_TEACHER`

## 1. Scope 与冻结 lineage

本阶段只执行
`scriptsFORhuman/v26_3/a2_piper_base_v26_3_event_time_creation_plan_20260827.md`
和对应 handoff；没有执行任何标记 `SUPERSEDED` 的旧方案。

四个 main cell 从同一 checkpoint 启动：

```text
logs_rl/by_batch/base_v26_acquisition_supplement_20260823/
continuation/V26A_LR_S1_POLICY800/model_step_002000.pt
```

加载合同为 `policy_only` + actor RMS inherited，其余 critic、optimizer、scheduler、
trainer/env/staged-reset state fresh。共同训练合同为 4096 env、bilateral
exact2048/2048、750 iterations、save125、800/25、velocity iterations2、
`near_closed=0.1` 和 gripper effort 10/10。M0→M1 唯一 causal seam 是 Stage3
old velocity+position credit scale6 与 monotone high-water creation credit scale6。

没有使用 GPU4–7，没有 reset/stash/discard、commit 或 push。

## 2. Implementation 与 static proof

v26-3 新 creation state 在 completed physics/control step 后、reward 与 stage advance
前更新。high-water 跨所有 pre-advance stages 演化；reward 只读取本控制步缓存，并由
current Stage3 与 authoritative strict K5 mask 激活：

```text
relu(highwater_t - highwater_{t-1}) / (0.785398 * control_dt)
```

reward registry 的 `scale × dt` 使 episode scaled sum 保持为
`scale × normalized monotone creation`。natural reset 从实际写入的 handle state
初始化；staged snapshot 保留 prev/high-water，同时在 restore 后清除 one-step transient
cache，避免 pseudo-creation。旧 depression term 未改写。

Evaluator 另增 Stage2∧current close-gate 的 E1 selector；它只覆盖 deterministic
actor `action_mean` 的 gripper 维，raw/post action 与 selector mask 均进入 trace。现有
Stage3/4 E2 selector 保持独立。actual implicit-drive force不可读，computed/applied
effort只按 estimate 报告。

focused pure update test 为 5/5 PASS；bash syntax、Python compile、resolved matrix、
reward scale/control-dt 与 changed-leaf verifier均通过。no-hash source lock 在 formal
启动后捕获 path/size/mtime 与四份实际命令：

- `scriptsFORhuman/v26_3/evidence/static/resolved_matrix_proof_final.json`
- `scriptsFORhuman/v26_3/evidence/static/source_lock.json`
- `scriptsFORhuman/v26_3/evidence/static/source_lock_exit_verification.json`

exit verification确认八个locked source/config/runner的path/size/mtime在四格正式训练
期间未改变，四份formal receipt均为PASS/exit0；本阶段按Owner约束未计算内容哈希。

## 3. Construction 与 runtime admission

natural exact1 LEFT/RIGHT retry、staged snapshot smoke retry、64-env/12-update
post-diagnostic M1 checkpoint smoke均完成真实 IsaacSim/PPO runtime：

- construction receipt：
  `logs_eval/base_v26/v26_3_event_time_creation_20260827/construction/construction_receipt.json`
- natural outputs：
  `logs_eval/base_v26/v26_3_event_time_creation_20260827/construction/natural_1env_retry1`
- staged checkpoint：
  `logs_rl/by_batch/base_v26_3_event_time_creation_20260827/construction/staged_smoke_retry1/model_step_000012.pt`
- common-cap checkpoint：
  `logs_rl/by_batch/base_v26_3_event_time_creation_20260827/construction/post_diagnostics_m1_smoke/model_step_000012.pt`

首次 natural smoke 暴露 reset init 缺口；首次 staged smoke 暴露 metric meter 要求
Tensor 的真实类型错误。两次失败 artifact 均保留，修复同一路径后 retry PASS；没有
fallback 或 silent downgrade。staged store/load/restore-clear counters均现场非零。

## 4. D/E diagnostics 与 bounded F

diagnostic source 为 v26-2 W750 full-load natural。D0/E1/E2 每侧 exact64，D3
每侧 exact16，全部 receipt PASS。zero-command excursion 为 LEFT
`7.879901e-05 rad`、RIGHT `3.309042e-05 rad`，冻结 durable reference 为 LEFT
`0.0010427195811644197 rad`、RIGHT `0.050901446491479874 rad`。

D0 复现两侧 old income/high-water gap且 integrity=0。E1 在两侧恢复大量 Stage3∧K5，
typed outcome 为 `STAGE2_LIMIT_CYCLE_CAUSAL_CONFIRMATION`；E2 为
`STAGE3_CLOSE_NOT_CAUSAL`。E1 selected bilateral three-view render已完成。

D3 满足 bounded F 前置，故执行 F10/F20/F40 每侧 exact16。提高 cap 方向一致地改善
tracking/saturation，但三档均无 durable creation；无 over-force/bad terminal。
结果为 `ACTUATOR_CAPACITY_NOT_CAUSAL_AT_TESTED_RANGE`，未扩 exact64，main common
cap冻结为10/10。actual drive force与 per-contact handle-axis moment均
`INCONCLUSIVE`。F10 selected detailed bilateral replay已完成。

capacity ladder的最大handle high-water（LEFT/RIGHT）为：F10
`0.000351/0.020473 rad`、F20 `0.000628/0.019080 rad`、F40
`0.000669/0.019080 rad`。estimated saturation随cap升高从F10约
`0.540/0.509`降到F40 `0/0`，但state effect没有越过冻结的durable reference，
所以没有把tracking改善误写成handle-axis load-bearing或creation。

归约证据：

- `logs_eval/base_v26/v26_3_event_time_creation_20260827/diagnostics/diagnostic_decision.json`
- `logs_eval/base_v26/v26_3_event_time_creation_20260827/diagnostics/F/f_decision.json`

## 5. Formal main training

四格在 physical GPU0–3、all-visible + physical `cuda:N` binding 下并发；runtime
逐格验证 4096 env 与 LEFT/RIGHT exact2048/2048。M0_S0、M0_S1、M1_S0、M1_S1
均自然完成750/750、exit0；四份receipt均PASS：

- `.ai/runtime/runs/v26_3_main_m0_s0/RUN_RECEIPT.json`
- `.ai/runtime/runs/v26_3_main_m0_s1/RUN_RECEIPT.json`
- `.ai/runtime/runs/v26_3_main_m1_s0/RUN_RECEIPT.json`
- `.ai/runtime/runs/v26_3_main_m1_s1/RUN_RECEIPT.json`

每格125/250/500/750 canonical checkpoint齐全且均为30,018,531 bytes；save125还
按预期产生375/625，不纳入canonical eval selection。训练期间GPU0–3分别承载四个
physical process及all-visible辅助context，GPU4–7始终无compute process。

## 6. All-checkpoint bilateral natural evaluation

四条eval lane完成4 cells × 4 checkpoints × LEFT/RIGHT exact64，共32组、2048个
natural first episodes。每组的metrics、per-env records、expanded trace与metadata
四件套齐全；四份`v26_3_eval_*` receipt均PASS。全部reward trace与terminal accumulator
直接对账，integrity violation总数为0，未出现creation income而active denominator为0。

step750 natural funnel与机制readout：

| Cell | LEFT Stage3 / creation / high-water | RIGHT Stage3 / creation / high-water | Stage4 / goal |
|---|---|---|---|
| M0_S0 | 23/64 / 0 / 0.002529 | 17/64 / 0 / 0.055566 | 0 / 0 |
| M0_S1 | 32/64 / 0 / 0.001043 | 36/64 / 0 / 0.050901 | 0 / 0 |
| M1_S0 | 30/64 / 0 / 0.000849 | 50/64 / 8 / 0.785398 | 0 / 0 |
| M1_S1 | 32/64 / 0 / 0.002477 | 13/64 / 13 / 0.785398 | 0 / 0 |

`creation`是超过side-specific frozen reference并连续保持至少5 control steps的episode
数。M1两条seed都在RIGHT形成repeated durable creation，但两条seed的LEFT均为0；
`side_seed_support={seed0_left:false, seed0_right:true, seed1_left:false,
seed1_right:true}`。因此不是双seed双侧支持，main归约为
`MONOTONE_CREATION_SEED_OR_SIDE_UNSTABLE`。所有M1/M0的Stage4与goal为0；main最大
hinge仅M1_S1 RIGHT `0.008890 rad`，远未访问0.08–0.105 wall band。

完整归约：
`logs_eval/base_v26/v26_3_event_time_creation_20260827/main_mechanism.json`。

## 7. Conditional F/P/W 与 selected render

conditional closure为：

- F：`RUNTIME_COMPLETE / ACTUATOR_CAPACITY_NOT_CAUSAL_AT_TESTED_RANGE`；保留10/10，
  未扩exact64；actual drive force与handle-axis effect为`INCONCLUSIVE`。
- P：`NOT_RUN / PUSH_LOAD_BEARING_SIGNAL_INCONCLUSIVE`；没有具备identified
  anchor/axis/frame的逐接触side-canonical axis-work信号，故不创建P reward/wave。
- W：`NOT_RUN / WALL_REMOVAL_NOT_REACHED`；selected bilateral repeated creation、
  两侧0.08–0.105访问和两侧old0.1 income cliff三项均为false，故不消耗W预算。

selected checkpoint为`M1_S1_STEP0750`。sole-visible physical GPU0、process-local
`cuda:0`完成matched LEFT/RIGHT natural render：

| Side | max stage | goal | handle high-water | max hinge | creation raw / active | terminal |
|---|---:|---:|---:|---:|---:|---|
| LEFT | 3 | 0 | 0.000208 | 0.000538 | 0 / 126 | stage_overtime |
| RIGHT | 3 | 0 | 0.597800 | 0.001772 | 38.02097 / 128 | stage_overtime |

两侧各653 steps、integrity0，各有main/handle-top/handle-side三个MP4。render与population
的RIGHT-only creation/LEFT failure方向一致，但不替代exact64 evidence。

首次selected render在episode前因launcher继承inactive `push_door_handle` diagnostic
term而fail-fast；该FAIL receipt、partial output与log按attempt1保留。launcher补齐M1
creation-term binding后retry1 PASS；policy/checkpoint/scenario/action均未改变。失败进程
在抛错后的Isaac teardown中未响应INT/TERM，按精确PID发送KILL后receipt记录exit137；
没有删除其artifact，也没有影响后续sole-visible GPU0 retry。

## 8. Teacher boundary 与 closure

Teacher/Student binding只有在至少两个独立 seed lineage 的两侧都有 repeated natural
full goals、selected checkpoint另过 exact128/side holdout、provenance/integrity完整且
bilateral render一致时才允许更新。本阶段两条seed都缺LEFT creation，所有natural goal
均为0，所以不运行exact128/side Teacher holdout，不更新manifest/Student binding；G7
保持不变，Teacher boundary关闭为`V26_3_MECHANISM_PASS_NO_TEACHER`。

最终closure evidence：
`logs_eval/base_v26/v26_3_event_time_creation_20260827/closure_evidence.json`。
本阶段以有效负/不稳定结果关闭，不追加reward、friction、hook、45N、1300/32、降K5、
R1、Student或无界relay。证据等级为：formula/config/matrix/source-lock属static/resolved；
construction、D/E/F与render属IsaacSim runtime；四格750与2048-episode natural reducer
属training/experiment。未生成artifact bundle，未commit、未push。

closure时所有`v26_3_*` tmux与相关process均已退出，GPU0–7均为1 MiB idle且无compute
process；`v26_3_root`的GPU0–3、IsaacSim与output-root leases全部release，task state置为
COMPLETED，team coordination ledger已archive并deactivate。
