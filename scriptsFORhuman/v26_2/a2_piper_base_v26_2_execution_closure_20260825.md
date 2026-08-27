# A2+PiPER base_v26-2 pull-derived execution closure

更新时间：2026-08-25 10:54 HKT  
阶段状态：`v26_2_complete_not_admitted`  
最终 typed stop：`HANDLE_CREATION_NOT_SUPPORTED`  
conditional relay：未执行

## 1. Scope 与 lineage

本阶段只执行
`a2_piper_base_v26_2_pull_derived_plan_20260825.md`；同目录标记
SUPERSEDED 的 raw-removal-only 方案未执行。

所有 C/A/R/W cell 从同一 checkpoint 启动：

```text
logs_rl/by_batch/base_v26_acquisition_supplement_20260823/
continuation/V26A_LR_S1_POLICY800/model_step_002000.pt
```

加载合同是 `checkpoint_load_mode=policy_only` 且
`policy_only_load_actor_rms=true`：actor MLP/std/LSTM/RMS inherited；critic、
optimizer、scheduler、trainer step、environment 与 staged-reset state fresh。
本阶段未改 pull tensile/hook/event graph、gripper effort、arm gains、TCP、door
physics/friction/load、actuator、K5、stage transition、forced-close、R1 或 Student
binding。

新增 reward 的 raw semantics 为：

```text
clamp(handle_vel + clamp(handle_pos, 0, 0.785398) / 0.785398, -1, 1)
* (current stage == Stage3)
* (current control-step authoritative bilateral-contact streak >= K5)
```

实现复用 `_a2_stage3_stage4_both_contact_streak`，不重算接触历史。C/A 的 term
scale 为 0 时不进入 reward registry，但 `v26_2` terminal/step telemetry 仍记录同一
Stage3∧K5 denominator，income 明确为 0。

## 2. Static/resolved proof

正式 alias 为 `wbmanip/base_v26_2_pull_derived`；四个 thin configs 为：

| Cell | raw handle | gated depression | near-closed |
|---|---:|---:|---:|
| C | 6 | 0 | 0.1 |
| A | 0 | 0 | 0.1 |
| R | 0 | 6 | 0.1 |
| W | 0 | 6 | 0.25 |

Runner-equivalent resolved configs 与证明在：

- `logs_eval/base_v26/v26_2_pull_derived_20260825/resolved_wave1/{C,A,R,W}.yaml`
- `logs_eval/base_v26/v26_2_pull_derived_20260825/resolved_wave1/resolved_matrix_proof.json`

Verifier 证明 A→R 的 causal seam 只有 gated reward scale、env reward mirror 与
runtime binding；R→W 只有 near-closed `0.1→0.25`；C↔R 仅作 ungated/gated
descriptive comparison；A→W 明确不是单因素比较。共同训练配置为 seed1、side
permutation seed1、4096 env、bilateral 2048/2048、750/save250、800/25、velocity
iterations2、4 minibatches、actor RMS inherited。

## 3. U-probe 与 W smoke

当前仓 door fixture 的确定性 U-probe 已完成：

`logs_eval/base_v26/v26_2_pull_derived_20260825/u_probe_receipt.json`

fixture 为 0.95×2.05 m、handle height 0.9 m、100 kg、right/out、hinge drive
7.25 Nm。handle theta 0–0.4 rad 时 hinge noise 约 0.002 rad；0.5 rad 时 hinge
response 0.0478 rad，0.6 rad 时 0.1443 rad。该结果只校准 current asset latch
mechanism并确认冻结 handle norm 0.6 的量级，不参与 winner selection。

64-env W smoke 完成 10 次真实 rollout/PPO update并写出：

`logs_rl/by_batch/base_v26_2_pull_derived_20260825/smoke/V26_2_W_SMOKE/model_step_000010.pt`

saved config 证明 W `(0,6,0.25)`、policy-only actor RMS true、velocity
iterations2、4 minibatches；runtime 日志中 gated depression raw/scaled income 非零。

## 4. Wave1 training

C/A/R/W 均在独立 tmux、GPU0–3 和 supervisor receipt 下完成 750/750、exit0：

| Cell | receipt | checkpoints |
|---|---|---|
| C | `.ai/runtime/runs/v26_2_wave1_c/RUN_RECEIPT.json` | 250/500/750 |
| A | `.ai/runtime/runs/v26_2_wave1_a/RUN_RECEIPT.json` | 250/500/750 |
| R | `.ai/runtime/runs/v26_2_wave1_r/RUN_RECEIPT.json` | 250/500/750 |
| W | `.ai/runtime/runs/v26_2_wave1_w/RUN_RECEIPT.json` | 250/500/750 |

四份 receipt 均为 `PASS`、`process_returncode=0`；每个 checkpoint 为
30,016,299 bytes。R/W 训练日志确认 gated-depression reward 实际支付。

启动过程保留了两类可复核失败证据：首次 launcher 的 shell local expansion 在进入
rollout 前 fail-fast；随后 sole-visible 多进程 GPU binding 在 Kit/Vulkan 枚举阶段
失败。失败训练/log/receipt 被移动到 `failed_startup_attempt1` 命名路径，未删除。
正式 r4 改用已验证的 all-visible GPU0–3 + physical `cuda:N` binding 后完成上述
Wave1；失败启动不构成训练证据。

## 5. All-checkpoint bilateral natural Route A

四条 eval lane 对 C/A/R/W 的 250/500/750 全部运行 LEFT64 + RIGHT64 natural，
共 24 个 checkpoint-side、1536 episodes。每组都有：

- `metrics_eval.json`
- `a2_v14_per_env_records.json`
- `stage2_5_step_trace.json`
- `a2_eval_diagnostic_metadata.json`

四份 `.ai/runtime/runs/v26_2_wave1_routea_{c,a,r,w}/RUN_RECEIPT.json` 均为
`PASS`、exit0；每侧 completed/natural-start/episode count 均为 64。训练态 staged
reset 未用于 Route A。

第一次 eval 在首个 LEFT episode 完成后因 active denominator 为 0 时把
per-active income 写成 NaN，被 artifact finite check fail-fast。该轮四份 FAIL receipt、
logs 与 partial Hydra outputs 已移动到 `*_failed_telemetry_nan_attempt1` 路径。
source 随后把空 denominator 的日志语义明确定义为有限 0.0；reward、K5、阈值和
非零 denominator 计算未变。r5 从头重跑全部 24 组，未复用失败轮 evidence。

## 6. Mechanism trace 与结果

归约 artifact：

`logs_eval/base_v26/v26_2_pull_derived_20260825/wave1_mechanism.json`

归约只使用 first active episode（`episode_index=0`、`first_episode_active=true`）的
expanded rows，并与每个 terminal `v26_2` accumulator 对账。control timebase 为
0.02 s；articulation/contact/reward 取 completed physics step、reset 与 stage advance
之前的值。active denominator 是本控制步 Stage3∧strict K5，不用 raw!=0 推断。
scaled income 是 `raw × scale6 × dt0.02`。四项 integrity counter
`active_outside_stage3`、`active_without_k5`、`raw_nonzero_while_inactive`、
`stage4_below_threshold_on_first_admission` 在全部 24 组均为 0。

Stage3 readout：

| Cell | step250 L/R | step500 L/R | step750 L/R |
|---|---:|---:|---:|
| C | 11/6 | 0/5 | 1/12 |
| A | 0/0 | 0/0 | 0/0 |
| R | 0/0 | 0/0 | 32/36 |
| W | 0/0 | 0/0 | 32/36 |

所有 cell/checkpoint/side 的 Stage4、Stage5、goal、stable handle>=0.3、
handle>=0.6、hinge>=0.1、hinge>=0.25 与 `(0.1,0.25)` dwell 都为 0；terminal
reason 全为 `stage_overtime`。

W_STEP0750 的 direct mechanism totals：

| Side | K5/stability steps | bilateral/opposite/window | raw income | scaled income | active-step raw/scaled mean | unlatch-active | global max handle/hinge rad |
|---|---:|---:|---:|---:|---:|---:|---:|
| LEFT | 3782 | 3942/3942/3942 | 1903.0994 | 228.3719 | 0.50320 / 0.06038 | 245 | 0.000164 / 0.001926 |
| RIGHT | 4343 | 4523/4523/4523 | 1380.6428 | 165.6771 | 0.31790 / 0.03815 | 4343 | 0.002868 / 0.001965 |

这证明 gated term 在严格 K5 denominator 内获得了非零 velocity-driven income，且
contact retention 保持；但它没有创造 stable handle displacement。R 与 W 的
step750 readout相同，hinge 从未进入 0.1 rad band，因此 threshold0.1→0.25 没有机会
表现 wall-removal effect。

因果结论分开记录：

- A→R：`HANDLE_CREATION_NOT_SUPPORTED`；
- R→W：`WALL_REMOVAL_NOT_SUPPORTED_IN_PUSH`；
- C↔R：仅 `UNGATED_VS_K5_GATED_SCALE6_DESCRIPTIVE_COMPARISON_ONLY`；
- A→W：`NOT_A_SINGLE_FACTOR_COMPARISON`。

W_STEP0750 保留 bilateral Stage3（LEFT 32/64、RIGHT 36/64），所以不是
acquisition regression；但每侧 Stage4>=2 或 handle>=0.6∧hinge>=0.1>=2 的第二
admission gate 都为 0。最终 typed stop 是 `HANDLE_CREATION_NOT_SUPPORTED`，
`relay_allowed=false`。按冻结 conditional contract，W relay seed0/seed1 未启动，
没有 relay runtime artifact，也没有把预算扩到 1500/2000/3000/4000。

## 7. Selected natural render

描述性最佳 `W_STEP0750` 使用唯一可见 physical GPU0、进程内 `cuda:0`，按
LEFT→RIGHT 各 1 个 matched natural episode 完成：

- receipt：`.ai/runtime/runs/v26_2_render_w_step0750/RUN_RECEIPT.json`，PASS/exit0；
- output：`logs_eval/base_v26/v26_2_pull_derived_20260825/selected_render/W_STEP0750`；
- LEFT：length552、reward165.0921、max Stage2、no goal；
- RIGHT：length552、reward160.3312、max Stage2、no goal；
- 两侧 main/handle-top/handle-side 共 6 个 MP4，均已登记到 receipt。

render 只证明 selected checkpoint 的真实 IsaacSim matched visual runtime，不替代
64-env mechanism/admission evidence。

## 8. Closure

v26-2 在冻结 stop 条件上关闭，不追加 reward/actuator/physics sweep，不降低 K5，
不启用 forced-close，不进入 R1。没有双侧 repeated natural goal，因此现有 Teacher/
Student handoff manifest 与 binding 保持不变；本阶段不产生 v26 Teacher release。

证据等级：formula/config/matrix 为 static/resolved evidence；U-probe、smoke、render
为真实 IsaacSim runtime evidence；四格 750 与 24 组 natural Route A/mechanism
对账为 training/experiment evidence。未 commit、未 push、未生成 artifact bundle。
