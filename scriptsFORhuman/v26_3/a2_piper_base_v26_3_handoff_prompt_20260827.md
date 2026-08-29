# Handoff prompt: autonomously execute complete `base_v26-3`

在 `/home/baoquanc/workspace/DoorDog-A2_Piper` 自主完成 `base_v26-3` 全阶段。
Owner 将离线等待最终验收；不要在每个中间 gate 停下来请求确认。你已获批使用 physical
GPU0–3，并可自主安排并发训练、eval、diagnostic、render与长跑等待，以最短墙钟完成
方案。不得使用GPU4–7。

先严格遵循根 `AGENTS.md`，使用项目file-based memory，随后完整读取并执行：

- `scriptsFORhuman/v26_3/a2_piper_base_v26_3_event_time_creation_plan_20260827.md`
- `scriptsFORhuman/pro_reviews/20260827-162429-HKT__e6310042348d/e6310042348d/FULL_REVIEW.md`
- `memory/a2-piper/base-v26-scratch-bilateral-teacher/description.md`
- `memory/a2-piper/base-v26-scratch-bilateral-teacher/TODO.md`
- `scriptsFORhuman/v26_2/a2_piper_base_v26_2_execution_closure_20260825.md`
- `.ai/SCIENTIFIC_ENGINEERING.md`
- `.ai/LONG_RUNNING_TASKS.md`
- `.ai/TEAM_STATE.md`
- `/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/scriptsFORhuman/pull_v1/PULL_V1_ROUND_REPORT.md`
- `/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/scriptsFORhuman/pull_v2/PULL_V2_ROUND_REPORT.md`
- `/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/gr00t/rl/envs/door/door_open_a2_pull.py`

Cloud package已由Owner上传并保存在当前仓，不要去Google Drive找交付包。主仓云端source
lock是 `A2_Piper` commit `e6310042348d24fbe8bb8bdc6ecd70e226fc3e32`；pull对照是
branch `codex/a2-piper-pull-v0-20260803` commit
`5a31f1acc5528c5697abc357fe8b2a861a692fdd`。开工时重新记录实际HEAD、diff、checkpoint、
GPU/process/tmux/lease状态，但不要reset、stash、discard或覆盖本地较新/未跟踪内容。
Pull repo只读对照，除非Owner另行明确授权，不在其中写入。

本阶段目标不是再调0.25 wall，而是修复v26-2已证实的velocity-credit farming：新增独立
`a2_stage3_handle_creation`，按本控制步monotone handle high-water increment支付，
严格Stage3∧current control-step K5。当前reward registry会乘control dt，因此raw必须用
`delta_highwater/(0.785398*control_dt)`；不要原样使用Cloud的裸normalized delta。
保留旧depression term作为M0，不就地改语义。high-water/prev/cache必须natural reset正确，
并注册到staged-reset snapshot store/load；restore后无新high-water就不得支付。

先实现功能，再做plan中限定的focused tests、Hydra resolved proof、1-env和staged-reset
smoke；随后D/E四卡诊断、按证据决定F，并用最终冻结的common actuator做64-env
PPO/checkpoint smoke。复用现有detailed contact/effort telemetry和Stage3/4 forced-close；
只新增Stage2∧close-gate evaluator selector。Eval实际使用deterministic
actor `action_mean`，不要把gripper flip归因于sampling。实际implicit-drive torque不可读时
写INCONCLUSIVE，不制造actual torque claim。

D/E、必要F与最终common-config smoke通过后，四卡并发完整M wave：

- GPU0 `M0_OLD_S0`；
- GPU1 `M0_OLD_S1`；
- GPU2 `M1_CREATE_S0`；
- GPU3 `M1_CREATE_S1`。

四格同一 `CONT_STEP2000`，policy-only + actor RMS true，fresh critic/optimizer/scheduler/
trainer/env，4096 env、bilateral exact2048/2048、750 batches，save125/250/500/750，
near_closed固定0.1。M0→M1只能改变old/new credit semantics。不要在250停下来等Owner；
跑满后用四条eval lane完成所有checkpoint LEFT/RIGHT exact64 natural Route A和mechanism
analysis。

按canonical plan自动执行预案：F effort capacity只在D3前置证据成立时做；P只在M1清除
alias但无creation且axis-work信号可识别时做；W只在已有bilateral creation、hinge访问
0.08–0.105且旧0.1 income cliff真实暴露时做。实际执行的P/W正式training wave都是
matched 2×2、四卡并发、750 batches并完成
all-checkpoint bilateral natural eval。前置不满足就写
`NOT_RUN`和typed原因，不自行加入45N、1300/32、pull tensile/hook/friction、降K5、
hysteresis、R1、Student、额外relay或无界budget。

GPU排程遵循plan §15。训练使用已由v26验证的GPU0–3 all-visible + physical `cuda:N`
binding；render用单卡sole-visible +进程内`cuda:0`。每个>30min作业独立tmux和
`.ai/scripts/run_supervisor.py` receipt，领取并释放真实GPU/IsaacSim/output-root lease。
让独立cell/eval尽量并发，避免高频轮询；可在长等待期间完成analyzer、closure模板和下一
条件分支准备，但不得提前根据未知结果改变因果seam。

自主权限覆盖：本阶段所需本地source/config/script/test/docs改动、IsaacLab smoke、GPU0–3
训练/eval/render、artifact analysis、typed closure和memory同步。权限不覆盖：GPU4–7、
hardware、外部写入、删除历史artifact、reset/stash/discard、commit/push。遇到已定义的
negative/inconclusive分支自主收口；遇到计划外invalid state先用真实source/runtime定位并
修复同一路径，不能用fallback/silent downgrade强行跑。若确实无法继续，仍完成closure，
写清`INCONCLUSIVE`、已完成证据、block和所有`NOT_RUN`分支，不把半成品称为PASS。

最终必须交付：implementation/config/launchers/tests、verified command registry、所有实际
run receipts/checkpoints/raw evals/analyzers、selected LEFT/RIGHT natural render、
`a2_piper_base_v26_3_execution_closure_20260827.md`、plan closure、memory TODO/DONE/router、
资源释放状态。只有至少两个独立seed lineage在两侧都有repeated natural full goals，并完成
selected exact128/side holdout，才可更新Teacher manifest/Student binding；只有Stage4或
handle creation时保持G7 binding不变。

不要执行任何标记 `SUPERSEDED` 的旧v26-2方案。不要把A→W或跨wave比较写成单因素。
最终向Owner返回一个结果优先的验收摘要：最终typed outcome、selected checkpoint、两侧
natural funnel、creation/wall证据、实际执行/未执行分支、render、changed paths、evidence
等级、NOT_RUN/INCONCLUSIVE、active资源、是否commit/push。
