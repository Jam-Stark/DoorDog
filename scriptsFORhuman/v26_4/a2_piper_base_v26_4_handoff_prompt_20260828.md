# Handoff prompt: autonomously execute complete `base_v26-4`

在 `/home/baoquanc/workspace/DoorDog-A2_Piper` 组建 team 并自主闭环完成 `base_v26-4`
全阶段。Owner 只验收最终结果，不在中间 gate 停下等确认。已获批使用 physical GPU0–3，
可自主安排并发 probe、实现、test、训练、eval 与长跑等待。不得使用 GPU4–7。

## 先读

严格遵循根 `AGENTS.md` 与项目 file-based memory，随后完整读取：

- `scriptsFORhuman/v26_4/a2_piper_base_v26_4_bilateral_grasp_foundation_plan_20260828.md`（本阶段唯一权威计划）
- `memory/a2-piper/base-v26-scratch-bilateral-teacher/description.md`
- `scriptsFORhuman/v26_3/a2_piper_base_v26_3_execution_closure_20260827.md`
- `scriptsFORhuman/pro_reviews/20260827-162429-HKT__e6310042348d/e6310042348d/FULL_REVIEW.md`（§11.3 canonical representation 与 §6 bottleneck 分类）
- `.ai/SCIENTIFIC_ENGINEERING.md`、`.ai/LONG_RUNNING_TASKS.md`、`.ai/TEAM_STATE.md`

只读对照（不写入）：`/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0`，
branch `codex/a2-piper-pull-v0-20260803` commit `5a31f1acc5528c5697abc357fe8b2a861a692fdd`。

开工 source lock：`A2_Piper` HEAD `e6310042348d24fbe8bb8bdc6ecd70e226fc3e32`。
工作区已有未提交修改与未跟踪目录（含本计划）；重新记录实际 HEAD、diff、checkpoint、
GPU/process/tmux/lease 状态，**不得 reset、stash、discard 或覆盖本地较新/未跟踪内容**。

## Team

Owner 已明确要求组建 team，delegation gate 视为已触发，直接 spawn 最少必要的
focused agent（建议 3–4 条 lane），不要先自己把该委托的工作做完：

- Wave K 运动学 probe；
- Wave C 表示层实现；
- Wave M 训练/eval 编排与长跑 supervisor；
- 独立 reviewer，专责复核 §6.1 恒等证明与 §7 预注册判据。

其中 reviewer 是本阶段最高价值的独立检查：canonical 变换只要有一个符号错，
下游全部结果作废。Main 保留唯一控制面（scope、acceptance、WRITE_SET、排他资源、
Git、最终整合）。多 writer 与 GPU/IsaacSim/output-root 排他资源触发
`.ai/TEAM_STATE.md` ledger 与 lease；>30min 作业用独立 tmux 与
`.ai/scripts/run_supervisor.py` receipt。若当前 runtime 禁止 sub-agent，
退化为 single-agent 并在 task plan 写明 `NO_DELEGATION_REASON`。

## Owner 已裁决（不要再问）

1. **共享基座先只落在 A2_Piper。** 本阶段不合并 pull 分支、不 rebase、不在 pull
   worktree 写入。canonical seam 要设计成可关闭的独立开关，便于后续合并，但合并本身
   属 v26-5 及以后。
2. **本阶段不以 Stage4/goal 作为准入。** 这是相对 v26-2/v26-3 的显式降速，用一整轮
   换一个可复用的对称基座。若过程中出现 goal，如实记录，但**不得据此修改 §7 判据**。

## 执行顺序（K 是硬 gate）

**Wave K 必须先完成并产出 typed outcome，才允许冻结 Wave C 的实现形态。** 不得在
K 之前按假设实现 canonicalization。计划 §3.2 提出的
`default_joint_angles.arm_j6 = 1.57` 手性假设由 K 判定，未判定前不得写成结论。

- K：单门 fixture 加载机器人，脚本化位姿扫描 LEFT/RIGHT grasp target 与下压把手所需
  朝向，记录可达性、各关节限位余量、`arm_j6` 相对 default 的行程、把手轴力臂、
  所需保持的动作向量范数。输出 `K/k_kinematics.json` 与三选一 typed outcome。
  注意 `door_open_lr == -1` 时 handle joint LocalRot0 绕 Z 翻转 180°。
- C：按 K 结论选形态（计划 §6.1 或 §6.2）。**恒等证明未过不得上 GPU**：
  逐元素验证 `canonical(LEFT_obs) ≈ canonical(mirror(RIGHT_obs))` 与
  `mirror(mirror(a)) == a`，超容差 fail fast，不做 fallback。保留
  `door_open_a2_base.py:26686-26688` 的 left/right one-hot 与观测维度不变。
- M：`C0_CANONICAL_OFF`（复现 v26-3 M1）与 `C1_CANONICAL_ON`，各 2 seed，四卡并发。
  同一 source checkpoint、policy-only + actor RMS true、4096 env、bilateral
  exact2048/2048，reward scale 与 v26-3 M1 完全一致。唯一 causal seam 是
  canonicalization 开关。跑满后按每 checkpoint 每侧 exact64 natural first episode 评估。

训练用 GPU0–3 all-visible + physical `cuda:N` binding；render 用单卡 sole-visible +
进程内 `cuda:0`。让独立 cell/eval 尽量并发，避免高频轮询。

## 准入判据（看到结果后不得修改）

按计划 §7 预注册：两侧 K5 admission rate 之差 ≤ 0.15、contact stability 之差 ≤ 0.05、
handle high-water 的 LEFT/RIGHT 比值 ∈ [0.5, 2.0]，且三项在 2 条 seed 上同向。
typed outcome 树见计划 §9。

## 权限

**覆盖**：本阶段所需的本地 source/config/script/test/docs 改动、IsaacLab smoke、
GPU0–3 probe/训练/eval/render、artifact analysis、typed closure、memory 同步。

**不覆盖**：GPU4–7、hardware、外部写入、删除历史 artifact、reset/stash/discard、
commit/push、合并 pull 分支、更新 Teacher manifest 或 Student G7 binding。

**本阶段禁止自行加入**：修改任何 reward scale、改 `near_closed` 阈值、改 gripper
effort cap 或 kp/kd、移植 pull 的 hook/friction/45N/kp1300/tensile mask、降 K5、
加 hysteresis、跑 W wave、扩 relay 或无界 budget。这些要么已被 v26-3 判为
非因果，要么属后续阶段。

遇到计划外 invalid state，先用真实 source/runtime 定位并修复同一路径，不得用
fallback 或 silent downgrade 强行跑。确实无法继续时仍完成 closure，写清
`INCONCLUSIVE`、已完成证据、block 与所有 `NOT_RUN` 分支，不把半成品称为 PASS。

## 交付

implementation/config/launchers/tests、verified command registry、全部实际 run
receipts/checkpoints/raw evals/analyzers、`a2_piper_base_v26_4_execution_closure_<date>.md`、
计划 closure 段、memory TODO/DONE/router 同步、资源释放状态。

最终向 Owner 返回结果优先的验收摘要：K/C/M 三个 typed outcome、两侧对称性指标实测值
与是否过预注册判据、C1 相对 C0 的单因素结论、实际执行与 `NOT_RUN` 分支、changed
paths、证据等级、仍 active 的 writer/排他资源、是否 commit/push（默认否）。
