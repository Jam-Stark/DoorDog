# DoorDog A2_Piper project overlay

## Project identity

- Repository: `Jam-Stark/DoorDog`
- Primary branch/worktree family: `A2_Piper`
- Domain: A2 quadruped + PiPER manipulator, IsaacLab/Isaac Sim, teacher/student RL, sim-to-real door opening
- Source truth order: current local source and resolved config -> runtime artifacts -> file-based memory -> plans/history

## Protected workflow paths

Workflow migration must preserve:

```text
.codex/config.toml
.codex/agents/*.toml
MEMORY.md
memory/a2-piper/
```

Model names、reasoning effort、concurrency 和 role-specific TOML 属于项目 runtime 配置，通用 role 不覆盖它们。

## Real execution discipline

- Inspect current local environment、config、trainer、actor/critic、reward、observation、evaluator 和 checkpoint-loading paths before changing behavior.
- Do not infer implementation from `scriptsFORhuman` plans when code differs.
- Never assume local `logs_rl`、`logs_eval`、checkpoints 或 renders exist unless observed.
- A single bounded QA or temporary test does not require team state. Use coordination facilities only when the trigger is real.

## Resource ownership

Lease only actual exclusive resources: overlapping writer paths、GPU、IsaacSim process、display、port、hardware 或 output root. Read-only agents do not receive leases. A single already-authorized long run may use a run receipt without activating the full team ledger.

## IsaacLab and RL

- Verify API use against `/home/baoquanc/workspace/IsaacLab` and the installed version.
- Preserve tensor shape、dtype、device、batched indexing、manager lifecycle、action/observation ordering、reward sign/scale、reset/termination semantics 和 control/physics timebase.
- Runtime behavior changes require runtime evidence; policy-quality claims require registered evaluation or experiment evidence.
- Simulation limits、commands 或 force proxies 不是 hardware safety evidence.

### Verified base_v26-3 command registry (2026-08-27)

The canonical v26-3 entry is `scriptsFORhuman/v26_3/orchestrate_base_v26_3.sh` with
the registered `diagnostics`, `main`, `main-eval`, `conditional`, `final-eval`,
`render`, and `closure` subcommands.  Its concrete workers are:

```text
scriptsFORhuman/v26_3/run_base_v26_3_train_cell.sh
scriptsFORhuman/v26_3/run_base_v26_3_eval_lane.sh
scriptsFORhuman/v26_3/run_base_v26_3_diagnostic_lane.sh
scriptsFORhuman/v26_3/run_base_v26_3_main_eval_cell.sh
scriptsFORhuman/v26_3/run_base_v26_3_f_eval_lane.sh
scriptsFORhuman/v26_3/launch_base_v26_3_e1_render.sh
scriptsFORhuman/v26_3/launch_base_v26_3_selected_render.sh
```

Runtime proof on physical GPU0–3: policy-only training uses all four visible
devices plus `ACCELERATE_TORCH_DEVICE=cuda:<physical>`; natural evaluation uses
the same binding; render exposes only the selected physical GPU and uses
process-local `cuda:0`.  Construction produced a 64-env PPO checkpoint, and the
D0/E1/E2/D3 evaluator workers completed their exact bilateral outputs through
tmux-backed supervisor receipts.  Launchers fail on an existing output root and
never select GPU4–7.

## Memory routing

### Verified base_v27 entrypoints (2026-09-06)

2026-09-11 当前状态：v27已关闭为V27_COMPLETED_SCIENTIFIC_NO_RELEASE；六格C均6000、72/72 eval lanes完成。
临时隔离副本与active_source_lock指针已清理，以下是历史执行记录，不能直接视为可重启命令授权。
结论、manifest及保留证据从base-v27-bilateral-hardening memory与execution_closure_20260911路由。

`bash scriptsFORhuman/v27/v27_orchestrate.sh` 的 `smoke-launch --wave A`、
`train-launch --wave A`、`q0-dev-launch`、`q0-render-launch` 与 `eval-finalize --manifest ...`
已走通本机 runtime。Python 使用 `/home/baoquanc/anaconda3/envs/isaaclab/bin/python`；
每个 Isaac 进程只暴露其物理 GPU，并使用进程内 `cuda:0`。GPU2–7 训练、GPU0/1 评估；
当前六项 proxy env 显式进入 receipt command。具体 paths/合同从 `v27_contract.py` 与对应 runtime
source/config lock 读取。v27.0 终态是 NO_QUALIFIED_CANDIDATE，不能据此更新 Teacher/G7。
Wave A endpoint已冻结QUALITY_UNRESOLVED与RECIPE_A=C。`smoke-launch --wave B` 的64-env/32-batch
R2路径、P02/P05固定摩擦probe与注入评估已完成runtime证明；`train-launch --wave B` 六格均已进入训练。
L1首次ListConfig解析失败发生于actor加载前，按新root修复；实际root由runtime `active_attempts.json`
路由。L1原生0/2/5摩擦桶已在训练日志中观测到。Wave C尚未启动。
2026-09-09 Owner重新分配资源：Wave C剩余SC201/202使用GPU4/5，后续eval使用GPU6/7；
此前SC203与SK211/212/213已完成6000。当前入口仍为上述v27脚本，source快照与GPU变更
见runtime `source_snapshot_wave_c_gpu_remap_20260909.json`、`wave_c_gpu_remap_20260909.json`。
这记录已验证命令，不向其他任务授予GPU或实验预算。

For non-trivial implementation、debugging、review 或 stage planning, read only the minimum relevant route:

```text
MEMORY.md
memory/MEMORY.md
memory/a2-piper/MEMORY.md
relevant subsystem description.md
TODO.md / DONE.md only when current execution state matters
```

A self-contained typo、prose edit 或 isolated syntax check may skip deep memory reads when no historical fact can affect the result. Memory restructuring is candidate-triggered, not a mandatory final phase.

## Stage decisions and cloud handoff

Owner chooses whether a stage uses local Claude planner、cloud GPT Pro、both independently，or another roster. Artifact packaging and Pro_Space upload happen only when Owner requests them or the current stage contract explicitly enables handoff. Ordinary task completion does not create a bundle.

### Cloud Pro delivery configuration

- Git remote used by cloud reviewer: `origin`
- Branch or review branch: current approved task branch
- Owner-requested Cloud Pro handoff authorizes in-scope commit and push unless Owner explicitly says otherwise
- Drive task folder: stores only `worker_delivery__*` input artifacts
- Pro delivery transfer: Owner uploads `pro_delivery__full_review.zip` in the local Worker conversation; Cloud Pro does not upload it to Drive
- Pro review document root: `scriptsFORhuman/pro_reviews`
- Placement rule: `scriptsFORhuman/pro_reviews/<stage-or-release>/<commit-short>/`
- Cloud conclusions do not replace local source、resolved config、IsaacLab/GPU runtime、logs or hardware evidence
