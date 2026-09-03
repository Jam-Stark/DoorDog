# Claude Code `v26` session recovery handoff

生成时间：2026-09-01 12:02 HKT  
Repository：`/home/baoquanc/workspace/DoorDog-A2_Piper`  
Branch：`codex/v26-5-bilateral-stage5`  
当前 HEAD：`b228bb0`  
性质：原 session 记录、原 session 更新文档/memory 与当前 runtime artifact 的事实交接；本文不启动新实验，不改写预注册阈值，不给出新的 scientific interpretation。

## 1. Session identity and termination state

- Claude Code session name：`v26`
- Session ID：`3c059a71-a063-41ce-9713-fc396467ce8d`
- 原始 transcript：`/home/baoquanc/.claude/projects/-home-baoquanc-workspace-DoorDog-A2-Piper/3c059a71-a063-41ce-9713-fc396467ce8d.jsonl`
- Transcript 规模：752 条 JSONL、2,032,349 bytes。
- 工作目录：`/home/baoquanc/workspace/DoorDog-A2_Piper`
- Transcript 中最后一个人工输入：2026-09-01 11:04 HKT，再次要求不要创建循环任务，并在训练完成后继续。
- 2026-09-01 12:01 HKT 核查时，`claude --resume v26` 进程 PID `900822` 仍存在，进程无子进程；session metadata 仍为 `status=busy`。没有对应 Isaac Sim、training 或 evaluation 子进程。
- Session 曾创建 recurring job `86da5799`，schedule 为每小时 `:23`，内容为检查 Wave B、训练完成后启动 24 次评估并 reduce。工具返回说明该 job 为 session-only、Claude 退出即消失、最多保留 7 天。Transcript 中没有 `CronDelete` 记录；最后一次 fire 是 2026-09-01 11:04 HKT，并被人工输入中断。

## 2. Session received state

Session 的入口请求是继续解决“当前 policy 学不会稳定抓握、下压 handle 解锁”的问题。入口 handoff 为：

`scriptsFORhuman/v26_5/a2_piper_base_v26_5_wave2_r1_r15_execution_handoff_20260831.md`

入口 handoff 的冻结终态：

- R15 typed route：`KILL_RESIDUAL_ACQUISITION_REGRESSION`；
- R15 两个 formal training cell 与四个 retry1 evaluation cell 均执行完成；
- 全部 endpoint 均有高 K5/Stage3 admission，但 Stage4 全为 0；
- Owner 当时未批准 R15 后续实验；
- R15 source 已有提交，原 handoff 声明未 push。

## 3. Root-cause record produced by this session

Session 从 R15 reducer、per-step trace、resolved config 和历史 v19/v25 artifact 开始核查，记录的结论如下。

### 3.1 R15 policy 已出现下压，不是完全没有下压行为

`R15_S1/model_step_000250` 的 RIGHT exact64 natural eval 中：

- 16/64 episode 的 handle 达到 `0.785398 rad` 硬限位；
- handle 随后回弹，latch 重新咬合；
- hinge 全部停在 `≤0.0024 rad`；
- 按 `door_handle_drive_max_force` 分层，`≤1.6 N·m` 为 `15/21` 达到 handle `>0.3 rad`，`>1.6 N·m` 为 `1/43`。

### 3.2 Resolved-config difference

Session 核对并写入 Wave A plan/memory 的差异：

| 项 | v18–v25 与 pull | v26 至 v26-5 |
|---|---:|---:|
| arm_j7/j8 effort | `45/45 N` | `10/10 N` |
| arm_j7/j8 Kp/Kd | `1300/32` | `80/3`，后为 `800/25` |
| M39 gripper material | enabled | disabled |
| squeeze force max | `30` | `20` |
| over-force threshold | `55` | `40` |

Session 登记的 source/resolved-config 证据为：

- `logs_rl/a2_piper_full_stage_a2_base/base_v25/formal/V25_FULL_S0/config.yaml`
- `logs_rl/by_batch/base_v26_acquisition_supplement_20260823/formal/V26A_LR_S1/config.yaml`
- `gr00t/rl/config/robot/A2_Piper/a2_piper.yaml`

### 3.3 Historical positive control used by the session

Session 读取的 v19 G3 step2500 artifact 中，16/16 env 到 Stage5，包含 `door_handle_drive_max_force` 为 `2.77/2.75/2.50/2.43 N·m` 的门。下压期间 handle contact resultant p50 为 `28.6 N`；R15 对应值为 `16.8 N`，受力手指约 `10.5 N`。

## 4. v26-6 Wave A — completed

Canonical contract：

`scriptsFORhuman/v26_6/a2_piper_base_v26_6_waveA_gripper_capacity_plan_20260831.md`

Wave A 是固定 R15_S1 step250 policy 的 eval-only matched A/B：

| cell | side | capability |
|---|---|---|
| `control/right` | RIGHT | R15 原配置 |
| `restored/right` | RIGHT | `GRIPPER_CAPABILITY_BUNDLE` |
| `restored/left` | LEFT | `GRIPPER_CAPABILITY_BUNDLE`，exploratory |

`GRIPPER_CAPABILITY_BUNDLE`：arm_j7/j8 effort `45/45 N`、Kp/Kd `1300/32`、M39 enabled、squeeze max `30`、over-force `55`。Reward、threshold、policy、checkpoint、seed、door 分布和 K5 未改。

### 4.1 Wave A result

Canonical reducer：

`logs_eval/base_v26/v26_6_waveA_gripper_capacity_20260831/reducer.json`

Typed route：`GRIPPER_CAPACITY_CONFIRMED`。

| cell | `[1.0,1.6)` | `[1.6,2.2)` | `[2.2,3.0]` | handle ≥0.3 | handle ≥0.6 | Stage3 |
|---|---:|---:|---:|---:|---:|---:|
| `control/right` | 15/21 | 1/27 | 0/16 | 16/64 | 16/64 | 60/64 |
| `restored/right` | 20/21 | 23/27 | 5/16 | 48/64 | 44/64 | 63/64 |
| `restored/left` | 0/21 | 0/27 | 0/16 | 0/64 | 0/64 | 62/64 |

完整性记录：

- 三格 door parameter vector exact matched；
- `control/right` 复跑与冻结 R15 artifact 的 per-env `max_handle_rad` bit-exact，`max_abs_delta=0.0`；
- 三格 integrity violations 均为 0；
- 三份 supervisor 均为 `PASS/0`。

### 4.2 Wave A remaining observations recorded by the session

- Stage4、goal、`hinge≥0.1` 三格均为 0；
- restored/right `max_hinge≤0.0111 rad`，64/64 `stage_overtime`；
- 44/64 episode 将 handle 保持在 `>0.6 rad`，持续长度 p50 `64`、max `187` control steps；
- restored/left 三个 drive-force strata 仍为 0/64；
- per-step income 记录为 Stage2 loiter `0.28939`、Stage3 handle-held `0.19655`，差值 `-0.09283/step`；
- `a2_stage3_unlatch_hold` 为 `0.05991/step`，条件是 `hinge<0.1`；`push_door_hinge + hold_and_drive` 合计 `0.00901/step`。

Wave A plan 已在 §9 写入 execution closure；project memory 和 Claude local memory 也已写入 Wave A 结论。

## 5. v26-6 Wave B — training completed, evaluation not run

Canonical preregistration：

`scriptsFORhuman/v26_6/a2_piper_base_v26_6_waveB_gripper_capability_plan_20260831.md`

Wave B 从 `CONT_STEP2000` 以 `policy_only`、`policy_only_load_actor_rms=true` 启动，使用 plain recurrent actor 的 `base_v26_4_C0_CANONICAL_OFF` 基座。四格均启用 `GRIPPER_CAPABILITY_BUNDLE`；B0→B1 只改变 `a2_stage3_unlatch_near_closed_hinge_threshold`。

| cell | GPU | seed | near-closed threshold |
|---|---:|---:|---:|
| `B0_S0` | 4 | 0 | `0.1` |
| `B0_S1` | 5 | 1 | `0.1` |
| `B1_S0` | 6 | 0 | `0.25` |
| `B1_S1` | 7 | 1 | `0.25` |

Common training contract：4096 env、750 PPO batches、checkpoint steps 250/500/750、PhysX velocity iterations 2、staged reset enabled；Stage2→Stage3 income cliff 未改。

### 5.1 Smoke

- `v26_6_waveB_smoke.sh` 在 GPU4 完成 64-env × 2-batch smoke；
- receipt：`PASS/0`；
- `model_step_000002.pt` 存在；
- saved config 为 effort `45/45`、Kp/Kd `1300/32`、M39 true、window `30/55`；
- runtime log 注册 `m39_gripper_material` startup event。

### 5.2 Four training cells — post-session inspection

训练根：

`logs_rl/by_batch/base_v26/v26_6_waveB_gripper_capability_20260831/train/`

| cell | completion time HKT | log total time | exit | checkpoints |
|---|---|---:|---:|---|
| `B0_S0` | 2026-09-01 01:58:02 | `15896.60 s` | 0 | 250/500/750 |
| `B0_S1` | 2026-09-01 02:05:53 | `16154.99 s` | 0 | 250/500/750 |
| `B1_S0` | 2026-09-01 02:03:50 | `16055.24 s` | 0 | 250/500/750 |
| `B1_S1` | 2026-09-01 02:26:03 | `16851.84 s` | 0 | 250/500/750 |

2026-09-01 12:01 HKT 的只读核查结果：

- 四份 `exit_code.txt` 均为 `0`；
- 四份日志都到 `ETA: 0.0s`，并保存 `model_step_000750.pt` 与 `last.pt`；
- 四份日志中 `Traceback=0`、CUDA OOM=0、NaN pattern=0；
- 四份 `model_step_000250.pt`、`model_step_000500.pt`、`model_step_000750.pt` 均存在，每份 checkpoint size 为 `30,018,531 bytes`；
- 无对应 training/Isaac Sim 进程；GPU0–7 均为 `1 MiB / 0%`；
- 四个 tmux training session 已不存在。

四份 receipt 文件仍保留 launch 时的 `state: RUNNING`，尚未 finalize；但是 `run_supervisor.py status` 均返回 `PROCESS_EXITED rc=0`。Receipt 与实际进程状态的差异来自 session 未继续执行 finalize。

### 5.3 Wave B work not completed in the session

- Wave B 24 次 formal evaluation 未运行：4 cells × 3 checkpoints × LEFT/RIGHT exact64；
- 当前 `logs_eval/base_v26/` 下只有 `v26_6_waveA_gripper_capacity_20260831`，没有 Wave B eval root；
- `v26_6_waveB_reduce.py` 未运行，没有 Wave B reducer；
- Wave B typed route 未产生，状态为 `UNRESOLVED`；
- Wave B plan 文件仍写 `状态：PREREGISTERED`；
- project memory 的 v26 entry 仍停在 `v26_6_waveA_gripper_capacity_confirmed`，TODO 仍写“待批准 Wave B”，未反映 Wave B 已启动并完成训练；
- session 没有落盘 Wave B eval orchestration wrapper、eval receipt namespace 或固定 eval output root；只落盘了单个 `(GPU, CELL, STEP)` 执行脚本和 reducer。

## 6. Explicit continuation left in the transcript

Session 创建的 scheduled prompt 对训练完成后的动作写得明确：

1. 对四个 training receipt 运行 `run_supervisor.py status`；
2. 对 `PROCESS_EXITED` 的 receipt 先 finalize；
3. 四格均 PASS 后，按 Wave B plan §4，使用 `v26_6_waveB_eval_cell.sh` 在 GPU4–7 运行 24 次 exact64 evaluation；
4. 使用 `v26_6_waveB_reduce.py` 生成 reducer；
5. 报告 preregistered typed route；
6. 任一格失败则保留失败证据，不重跑。

Per-cell eval script 的实际接口：

```text
v26_6_waveB_eval_cell.sh GPU CELL STEP TRAIN_ROOT OUTPUT_ROOT
CELL = B0_S0 | B0_S1 | B1_S0 | B1_S1
STEP = 250 | 500 | 750
```

Reducer 的实际接口：

```text
v26_6_waveB_reduce.py --train-root <path> --eval-root <path> --output <path>
```

预注册 endpoint 与 routes 以 Wave B plan §5 和 `v26_6_waveB_reduce.py` 为准：endpoint `step750`；durable depression 为连续至少 25 control steps 保持 handle `≥0.6 rad`；`DURABLE_MIN=32/64` 每侧；`STAGE4_MIN=2/64` 每侧。

## 7. Files created or updated by the session

### 7.1 Repository tracked modifications, not committed

- `memory/a2-piper/MEMORY.md`
- `memory/a2-piper/base-v26-scratch-bilateral-teacher/description.md`
- `memory/a2-piper/base-v26-scratch-bilateral-teacher/TODO.md`
- `memory/a2-piper/base-v26-scratch-bilateral-teacher/DONE.md`

### 7.2 Repository untracked files created by the session

- `gr00t/rl/config/ablation/wbmanip/base_v26_6_waveB_B0.yaml`
- `gr00t/rl/config/ablation/wbmanip/base_v26_6_waveB_B1.yaml`
- `scriptsFORhuman/v26_6/a2_piper_base_v26_6_waveA_gripper_capacity_plan_20260831.md`
- `scriptsFORhuman/v26_6/a2_piper_base_v26_6_waveB_gripper_capability_plan_20260831.md`
- `scriptsFORhuman/v26_6/v26_6_waveA_eval_side.sh`
- `scriptsFORhuman/v26_6/v26_6_waveA_reduce.py`
- `scriptsFORhuman/v26_6/v26_6_waveB_eval_cell.sh`
- `scriptsFORhuman/v26_6/v26_6_waveB_reduce.py`
- `scriptsFORhuman/v26_6/v26_6_waveB_smoke.sh`
- `scriptsFORhuman/v26_6/v26_6_waveB_train_cell.sh`

`scriptsFORhuman/knowledge_recap/` 和 `scriptsFORhuman/pro_reviews/` 也是当前 untracked，但 transcript 明确将它们作为 unrelated paths 保留，未纳入本 session 的 changed set。

### 7.3 Claude local memory outside the repository

- `/home/baoquanc/.claude/projects/-home-baoquanc-workspace-GR00T-VisualSim2Real/memory/MEMORY.md`
- `/home/baoquanc/.claude/projects/-home-baoquanc-workspace-GR00T-VisualSim2Real/memory/doordog-v26-gripper-capability-regression.md`
- `/home/baoquanc/.claude/projects/-home-baoquanc-workspace-GR00T-VisualSim2Real/memory/doordog-stage-income-cliff.md`

### 7.4 Runtime artifacts

- Wave A evaluation/reducer：`logs_eval/base_v26/v26_6_waveA_gripper_capacity_20260831/`
- Wave B smoke：`logs_rl/by_batch/base_v26/v26_6_waveB_gripper_capability_20260831/smoke/B0/`
- Wave B training：`logs_rl/by_batch/base_v26/v26_6_waveB_gripper_capability_20260831/train/`
- Wave B logs：`scriptsFORhuman/v26_6/runtime_logs/waveB/`
- Wave B receipts：`.ai/runtime/runs/v26_6_waveB_smoke/` 与 `.ai/runtime/runs/v26_6_waveB_train_*/`

## 8. Git and evidence boundary

- Session 的最终汇报明确写 `未 commit，未 push`；当前 Git status 与之相符。
- 本 session 没有 core env/trainer source edit；repo 内改动是 v26-6 configs、execution scripts/plans 与 v26 memory。
- Wave A 达到 registered experiment evidence，typed route 为 `GRIPPER_CAPACITY_CONFIRMED`。
- Wave B 当前只达到 four-cell training runtime completion；没有 exact64 evaluation/reducer，因此没有 Wave B experiment outcome。
- Teacher/Student handoff、Teacher manifest 和 Student G7 binding 未更新。
- 无 hardware、sim-to-real 或 external deployment evidence。
