# Handoff prompt: execute revised `base_v26-2`

在 `/home/baoquanc/workspace/DoorDog-A2_Piper` 自主完成 pull-derived `base_v26-2`。

先遵循根 `AGENTS.md` 的最小读取与 scientific evidence 要求，再完整读取：

- `scriptsFORhuman/v26_2/a2_piper_base_v26_2_pull_derived_plan_20260825.md`
- `memory/a2-piper/base-v26-scratch-bilateral-teacher/description.md`
- `memory/a2-piper/base-v26-scratch-bilateral-teacher/TODO.md`
- `scriptsFORhuman/v26/a2_piper_base_v26_acquisition_supplement_20260823.md`
- `.ai/LONG_RUNNING_TASKS.md`
- `/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/scriptsFORhuman/pull_v1/PULL_V1_ROUND_REPORT.md`
- `/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/scriptsFORhuman/pull_v2/PULL_V2_ROUND_REPORT.md`
- `/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/gr00t/rl/envs/door/door_open_a2_pull.py`

不要执行同目录已标记 `SUPERSEDED` 的 raw-removal-only plan。当前 supplement 已命名
为 v26-1，无需重跑。

实际 pull lineage 是 policy-only warm continuation，不是随机 actor scratch；v26-1
scratch 也直到约 step3000 才有 repeated bilateral natural Stage3。因此 v26-2 必须从：

```text
logs_rl/by_batch/base_v26_acquisition_supplement_20260823/
continuation/V26A_LR_S1_POLICY800/model_step_002000.pt
```

以 `policy_only + policy_only_load_actor_rms=true` 启动；critic/optimizer/scheduler/
trainer/env fresh。

先实现最小 push-side `a2_stage3_handle_depression`：Stage3 handle velocity + normalized
position，乘当前 strict control-step K5 mask。加入 raw/scaled/active-step telemetry；
treatment 关闭 ungated `push_door_handle`。再把 pull-v2 的 `near_closed 0.1→0.25`
作为独立第二因素。不要整体移植 pull-only tensile event graph/hook/friction。

Wave1 使用 GPU0–3 并发四格，各 4096 env、seed1、750 batches、save250：

- GPU0 C：raw6 / gated0 / threshold0.1；
- GPU1 A：raw0 / gated0 / threshold0.1；
- GPU2 R：raw0 / gated6 / threshold0.1；
- GPU3 W：raw0 / gated6 / threshold0.25。

A→R 只验证 handle creation；R→W 只验证 reward-wall removal；C↔R 比较现有 ungated
与 pull-derived K5-gated semantics。Resolved config 必须证明 pairwise diff；不要把
A→W 写成单因素结论。

每个 checkpoint 运行 LEFT/RIGHT 各 64 natural episodes，报告 Stage3/4/goal、K5/
contact retention、stable handle>=0.3、handle>=0.6、hinge>=0.1/0.25、
`(0.1,0.25)` dwell/unlatch-active steps 与 handle reward active-step income。

只有 W 达到 plan 中 bilateral admission 才从最佳 W checkpoint relay：GPU0/1、
seed0/1、各 750 batches；GPU2/3 跑 eval。最长 lineage 1500，禁止扩到
2000/3000/4000。若 W 不准入或 relay 不稳定，按 typed negative/unstable outcome
关闭，不自行加 reward、actuator、physics、forced-close、降 K5 或进入 R1。

长跑分别用独立 tmux 与 `.ai/scripts/run_supervisor.py` receipt。开始前确认 GPU0–3
无冲突；保留当前 dirty worktree，声明窄 WRITE_SET，不回退他人改动，不 commit/push。

最终落地：implementation/config/launcher、U-probe receipt、smoke、Wave1、conditional
relay、全 checkpoint Route A、mechanism trace、selected render、plan execution closure、
memory TODO/DONE。只有双侧 repeated natural goal 才能更新 Teacher/Student handoff。

