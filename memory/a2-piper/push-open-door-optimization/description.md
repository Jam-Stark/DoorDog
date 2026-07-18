---
name: push-open-door-optimization
scope: A2+Piper full-stage push-open-door RL optimization from base_v9 onward
status: active
last_updated: 2026-07-19 07:07 HKT
owned_paths:
  - memory/a2-piper/MEMORY.md
  - memory/a2-piper/push-open-door-optimization/description.md
  - memory/a2-piper/push-open-door-optimization/TODO.md
  - memory/a2-piper/push-open-door-optimization/DONE.md
read_when:
  - 开始设计、训练、eval、render 或复盘 base_v9 之后的 A2+Piper full-stage 推门 policy 时
  - 需要确认 `v13` endpoint diagnosis、`base_v13_1_main` formal endpoint、matched eval/render 口径或 `logs_eval` co-location contract 时
---

# Push-Open-Door Optimization

## Purpose

本 entry 从 `base_v9` 起独立负责 A2+Piper full-stage 推门/开门 RL optimization 的当前状态、训练/eval/render 口径与下一步 TODO。Reward function 的构建历史继续保留在 [`reward-implementation-goal`](../reward-implementation-goal/description.md)，stage0–2-only quick test 继续保留在 [`stage0-2-grasp-terminal`](../stage0-2-grasp-terminal/description.md)；两者都不再拥有 full-stage `base_v9+` 的 active experiment TODO。

完整的 `replay_v2`、`base_v0→v11` 因果时间线、诊断 findings、artifact map 与可复现命令见 [`scriptsFORhuman/a2_piper_push_open_door_optimization_base_v0_to_v9_20260713.md`](../../../scriptsFORhuman/a2_piper_push_open_door_optimization_base_v0_to_v9_20260713.md)。Memory 只保存可复用结论，不复制 raw trace 或长日志。

## Current State

- 2026-07-18 22:13 HKT - `base_v13_1_main-20260717_202500` resolved run 为seed0、4 ranks × `1024 env/rank`、global batch `4096`、global cap `3000`、save250；该saved override supersede plan中的2000-batch预期。endpoint `model_step_003000.pt` state为global/max `3000/3000`，SHA-256 `e836427e...167945`。
- 2026-07-19 07:07 HKT - `base_v14_main`已完成training-ready implementation：warm-start为`base_v13_1_main` step3000 `policy_only`；Option A保持`12D actor / 5D [vx, vy, yaw, pitch, roll]`，无spring observation；4 ranks×1024 env/rank、global batch4096、3000 batches、save250。
- 2026-07-19 07:07 HKT - M16为right/out、hinge `[2.5,7.0]`、handle `[1.0,3.0]`、final handle height `[0.80,1.05]`；M17 stage0 x `[0.55,0.60]`、`|dy|<0.15`；M19 release latch `1.04 < 1.0472` stage4→5；M20 strict telemetry/three-seed bucket report/high cap`1.05`。
- 2026-07-19 07:07 HKT - M18 runtime PASS：`scriptsFORhuman/a2_piper_v14_reachability_20260719/`有7×10×3=`210` exact cells、12 feasible；严格规则`tcp_error<0.03`、无self-collision、joint margin`>0.1`。选择x `[0.55,0.60]`、cap1.05，1.10无feasible；high handles1.00/1.05仅diagnostic root height0.75（`>=0.70`）feasible。root height是static diagnostic placement，不是action/command dimension；M18 door collisions disabled且仅final static contact evidence，不证明dynamic policy reachability或hardware certainty。
- 2026-07-19 07:07 HKT - initial focused `45 passed`、post-review impacted `31 passed`、py_compile/Hydra compose/diff PASS；strict outcome types、M20 cap1.05、exact raw-grid coordinates三项fail-fast修复后CODE_QUALITY、IsaacLab semantics、runtime QA PASS。v14 formal training/smoke/eval/checkpoint runtime/policy quality均NOT RUN。
- 2026-07-18 22:13 HKT - endpoint matched artifact `logs_eval/base_v13_1/base_v13_1_main_ckpt3000_matched_scalar_trace_16env_seed0_20260718_r3/` exit0：seed0、16 env、per-env first episode，`16/16 goal`、`16/16 stage5`、`16/16 complete`；length min/mean/max `388/455.0625/502`，reward min/mean/max `103.3703/112.3147/119.3493`。forced-close/oracle均关闭，scalar/trace/diagnostic metadata完整。
- 2026-07-18 22:13 HKT - 2-env render artifact `logs_eval/base_v13_1/base_v13_1_main_ckpt3000_render_2env_3cam_seed0_20260718/` exit0：env0 len502、env1 len497，均goal/stage5/complete；default/handle_top/handle_side共6个MP4，无`.writing.mp4`，OpenCV逐帧解码PASS，均`1280×720@20fps`，env0/env1分别503/498帧。
- 2026-07-18 22:13 HKT - eval首次暴露single-process `accelerator.device=cuda` 与telemetry tensor `cuda:0`的strict comparison mismatch；`_canonicalize_a2_metric_device`仅将indexless CUDA解析为`torch.cuda.current_device()`，保留explicit index/CPU与全部shape/dtype/finite/exact-device fail-fast。13个targeted tests、py_compile、CODE_QUALITY及matched GPU eval runtime PASS。
- 2026-07-17 20:05 HKT - `base_v13_1_main` 已完成 training-ready implementation，formal training/eval/render 尚未启动：A3000 `policy_only` warm-start、4 ranks × `1024 env/rank`、global batch `4096`、`2000` batches、save every `250`、Kp/Kd `800/25`、velocity iterations `2`。M11 为hinge `>=1.2rad` per-env release latch/reset；latch后suppress hold×5、open-command penalty、grasp-mild、hinge-pos，保留hinge-velocity。M12 released target-root `0.5→1.0`；M13 stage4/5 frame penalty `.2`、panel不变；M14为rank-global/sample-weighted ratios、global count、quantiles、eval zero denominator→`null`。
- 2026-07-17 20:05 HKT - compile、targeted `20/20`、related suite `101/101`、CODE_QUALITY、IsaacLab/fail-fast static PASS；r3为A3000 `policy_only`、4×`64 env/rank`×`50` batches，release ratio与stage4/5非零、step50/last CPU-load与237 finite tensors PASS。Kit checkpoint后hang由Ctrl-C释放，故natural exit未验证；r3不构成formal policy-quality evidence。
- 2026-07-17 20:05 HKT - `v13_A` final diagnosis：A3000 `0/16 goal`、`16/16 stage4`、`4/16 stage5`、hinge p50 `1.28rad`、positive-motion bilateral `99.949%`、coasting `.045%`；2-env render无明显detach/free-flying door，j8 `14.151%`仍为guardrail fail。trap1：12个stage4的`root_x_max=-0.001..-0.054m`、仅差1–5cm、仍holding且income约`12/step`；trap2：4个stage5前向`0.043–0.085m/s`、frame force max`41–197N`（三次主要spike`123–197N`），x=1.5m前overtime。`v13_pre` 16/16 stage3确认control-streak runtime；Kp80 B仅streak3–4只支持exact warm-start/single-seed下low force margin不可训练，不是普遍单因素因果。
- 2026-07-17 20:05 HKT - Reusable lesson：additive stage rewards可在每个stage boundary形成stationary “rent”；v11 stationary hold与v13_A door-hold同形。每个新stage/reward都要审计stationary income相对transition action，并验证gate后旧收入归零。
- 正式4-rank训练已完成：A run 为 `logs_rl/a2_piper_full_stage_a2_base/base_v13_A_main-20260716_225345/`、endpoint `model_step_003000.pt`；B run 为 `logs_rl/a2_piper_full_stage_a2_base/base_v13_B_gate_only-20260716_225413/`、endpoint `model_step_001500.pt`。两者 checkpoint ZIP/CPU load、finite policy tensor 与 saved-config identity PASS；A/B endpoint SHA-256 分别为 `d576ca4b...057a36`、`f201eb9c...ada5`。
- Endpoint matched scalar/trace 使用 seed0、16 env、每 env first episode。A artifact 为 `logs_eval/base_v13/base_v13_A_ckpt3000_matched_scalar_trace_16env_seed0_20260717_r2/`：`0/16 goal`、`16/16 stage3`、`16/16 stage4`、`4/16 stage5`，其余12个停在stage4，全部 `stage_overtime`；terminal hinge p50/p95 为 `1.276/1.631rad`，16/16 都超过 `.4rad`。B artifact 为 `logs_eval/base_v13/base_v13_B_ckpt1500_matched_scalar_trace_16env_seed0_20260717/`：`0/16 goal`、`0/16 stage3`、全部停在stage2；per-env stage2 squeeze-streak max仅 `3–4`，未达到 K=5。
- A 达到 plan 的 intermediate-success behavior，但不是全 guardrail PASS：stage3/4 positive-motion bilateral `99.949%`、over-force `0.181%`、stage3 body8 single-contact `0.069%`、hinge velocity p95 `.21149rad/s`、coasting `0.045%`、j7 open-limit `1.258%` 均过线；j8 open-limit `14.151%` 超过 `<10%` 阈值，stage3 handle hard-limit 为 `27.416%`。因此它证明门运动/持续双侧夹持已突破，不构成 final goal、全 guardrail 或单seed因果 winner。
- A endpoint qualitative render 为 `logs_eval/base_v13/base_v13_A_ckpt3000_render_2env_3cam_seed0_20260717_r2/`：2 env × default/handle_top/handle_side 共6个 MP4，均 `1280×720@20fps`、655 frames/32.75s、首尾帧可解码且无 `.writing.mp4`；两 env 都为 stage4 overtime/len654，与16-env scalar 的 env0/1 episode outcome一致。Render只作定性证据；hinge终值不要求与 non-render rollout bitwise相同。
- stage2/3/4/terminal sampled-frame目视复核显示两env均随门持续运动、夹爪保持围绕handle，无明显“单次拍门后脱手/门自由飞走”；终点机器人仍以别扭姿态停在门口并卡stage4，故当前定性bottleneck已从unlatch/hold转到stage4 completion/through-door target。该结论受2-env qualitative subsample限制。
- `v13_A` main 与 `v13_B` gate-only 已按 plan 实施为独立 ablation config。正式 4-rank contract 为每 rank `num_envs=1024`，故每组 global rollout batch 为 `4096`；A global cap `3000`、B `1500`、save every `250`，都从 v12_C step3000 `policy_only` warm-start。A 启用 Kp/Kd `800/25`、PhysX velocity iterations `2`、stage3 base unlock、`push_door_handle=0`、grasp-gated unlatch/hold-and-drive `3/8` 与 grasp-conditioned stage3→4；B 保持 v12_C 的 `80/3`、velocity iterations `1`、base locked、handle reward `6`，新 reward 为零且不启用 M6。
- M5/M6/M9 source 已完成：新增 grasp-gated `unlatch_hold`/`hold_and_drive` reward、A2-only explicit stage3→4 grasp switch、per-stage stability 分子/分母、hold-and-drive/unlatch/coasting、handle p50/p95/hard-limit 与 hinge-velocity telemetry。`eval_to_log_metrics.json` 自动继承全部 `log_dict`；新增 `scriptsFORhuman/a2_piper_v13_gate_zero_warning.py`，按输入 checkpoint 顺序对 gate metric 连续 exact-zero 打显式 WARNING，并支持 fail-on-warning。
- v13_A/B validation 为 78 个 targeted tests、Python compile、Hydra compose、diff check、reward/config/API static review PASS。4-rank concurrent smoke 使用 A GPU0–3/port29513、B GPU4–7/port29514，各 `64 env/rank × 50 batches`；两组都完成 iteration50、写出 `model_step_000050.pt` 与 `last.pt`，step50 checkpoint CPU load PASS，runtime telemetry 无 NaN/shape/config failure。Kit 在 trainer 完成后停于 shutdown hang，checkpoint落盘后由Ctrl-C释放，因此只对 smoke training/checkpoint声明PASS；正式 run 与 endpoint evidence见本节首四条。
- `base_v12` A/B/C/D 已完成训练与 matched eval，不再是“尚未启动”的 config anchor。四组 matched 终局均 `0/16 goal`、无 stage4；A step3000 仅 2/16 进入 stage3，C step3000 保持最佳 stage2 grasp 但旧 gate 下 0/16 stage3，B/D step2750 均停在 stage2 open-command/no-contact basin。single-seed 2×2 受 learned basin/stage exposure 支配，不能给出稳定 factorial causality 或 winner。
- v12_C step3000 的旧 gate 直接证据：stage2 current-frame both contact `92.0%`、opposite/sufficient squeeze 各约 `93.1%`，但 5 个连续 physics-frame all-history stability/completion 恰为 `0`。ContactSensor history 在 200Hz physics loop 更新，而 policy control 为 50Hz；旧 5-frame window 仅约 25ms 且跨 action boundary，故 gate 时间尺度是结构性 blocker。
- `v13_pre` 已实施 M1：required config `a2_grasp_gate_mode` 支持显式 `control_streak|physics_history`，`a2_grasp_streak_control_steps=5`；control mode 每个 control step 取 sensor latest frame `[:,0]`，stage2 squeeze 与 stage3/4 bilateral streak 只更新一次，reset/stage switch 清零，completion/stability getters 无副作用。未知 mode、缺失/非法 K、shape/dtype/device 或 duplicate full update 直接 fail-fast；legacy physics-history path 只用于历史复现/消融。
- M10 最终 matched runtime artifact 为 `logs_eval/base_v13/base_v13_pre_gatepatch_C3000_matched_scalar_trace_16env_seed0_20260716_r2/`：v12_C step3000、seed0、16 env、per-env first episode，且相对 v12_C 原 eval 只新增 `control_streak/K=5`。结果 `16/16 stage3 entry`、`0/16 stage4`、`0/16 goal`；stage2 首过 control-step min/median/max `16/20.5/27`，达到 plan `>=14/16` gate。stage3 pooled bilateral `99.815%`、control-streak stability `98.692%`，但 hinge max mean 仅 `.000918rad`，支持“根因 A 已解除、B/C 仍待 v13_A”的分离结论。
- `v13_pre` validation：72 个 targeted no-sim tests、Python compile、YAML parse、Hydra compose、diff check、matched runtime 与 artifact/config consistency PASS。Black/Ruff 在当前 env 未安装，保持 NOT_RUN；IsaacSim 启动有 `CUDA_VISIBLE_DEVICES`/GLFW enumeration warnings，但 scene/checkpoint/16 episodes 均成功且进程 exit0，不升级为 blocker。
- `base_v11` A/B/C 都在计划 global step2000 前停止；可用 full-state checkpoint 为 A/B `500/1000/last=1150`、C `1250/1500/last=1550`。九个 payload 的 ZIP integrity 与 CPU load 都 PASS，但训练停止原因及训练到 step2000 的行为均未证实，故仅构成 incomplete-budget comparison。
- Matched module scalar/trace eval（seed0、16 env、per-env first episode）在九个可用 state 全部为 `0/16 goal`、`0/16 stage4 entry`、`stage_overtime`；A/B 均 max-stage2，C 均 max-stage3。它是 single-seed/incomplete-budget evidence，不产生 full-budget 或 statistical winner。
- A/B 三个 aligned per-env hinge 完全相同，且两组均无 stage3 exposure；`push_door_hinge=12` 只在 stage3/4 gate 生效，所以 B 没有实际测试 exposure 下的 H+。C 最新 step1550 mean max hinge 约 `.001110rad`，保留 bilateral `100%`、stability `99.159%`、close `100%`、over-force `0%`、j7/j8 open-limit proximity `0%`；stable hold 不是 door progress。
- C 的 realized hold bundle 约 `.1813`、hinge reward 约 `.00007`，支持当前轨迹存在 reward-magnitude imbalance 的观察；hold-dominant causality 仍是 inference，未经 reward intervention 证实。没有新增 render：无新的定性事件，scalar/trace 仍是 primary evidence。
- 当前关键 source mtime 晚于 v10_D training launch、早于 v11；A 是 exact saved-config control，但不是已证明的 exact-source control。现有 observation-order diff 是 plausible confound，因果未证实；下一轮训练前必须 freeze/record exact source。
- Durable resume gotcha：当前 trainer 中 `algo.trl.num_total_batches` 是全局 iteration 上限，不是 resume 后的 remaining iterations。Full-state checkpoint 会恢复 `state.global_step`，trainer 将 `state.max_steps` 设为 `num_total_batches`，`DefaultFlowCallback` 在 `global_step >= max_steps` 时终止。因此从 step1000 续训到 step2000 必须传 `num_total_batches=2000`；传 `1000` 会在 resume 后立即命中终止条件。不得只根据外层 `for range(...)` 误判为“额外训练 1000 batches”。
- `base_v10_A/B/C/D` 是四个独立 scratch policy：saved config/overrides 与 checkpoint integrity 已证明 `checkpoint=null`、`auto_load_latest=false`、seed0、命令字面值 `num_envs=4096`、2 ranks、1000 batches；四个 `model_step_001000.pt` 均存在。训练时未能逐字冻结的 source equivalence 仍未证实。
- Matched scalar/trace runtime PASS：四组均为 seed0、16 env、each-env first episode；全部 `0/16 goal`、`stage_overtime`，没有 stage4。A/C 只到 stage2；B/D 全部到 stage3。
- D 是当前 behavioral reference，不是 task winner：stage3/4 pooled bilateral contact `100%`、contact stability `99.147%`、j7/j8 open-limit proximity `0%/0%`，但 hinge max mean 仅 `.001073rad`，远低于 `.25rad` stage3→4 threshold。单 seed 不能给出统计 winner。
- A→B、B→C、C→D 的比较都被 learned route/stage exposure 限制：B/D 的 high-quality hold 不可由 A/C 的无 stage3 exposure 单独隔离；C 是 open/no-contact basin，workspace signal 为 j3 dominant/argmin bottleneck（不是 only-j3 root cause）。D 的 stationary bilateral hold 与 strong hold reward / low progress motion 一致，但 reward dominance 仍是待 intervention 验证的推测。
- D matched render 有 48 个有效 MP4，定性显示 stationary bilateral hold、没有可见持续 door rotation。strict no-trace output QA 为 FAIL：即使 diagnostic flag=false 仍写出 base trace；source diagnosis 证明这是 unconditional base trace output，发生在 physics/reward 后且不改 policy action。render 的 numeric exit code unverified，不能把整条 render QA 写为 PASS。
- `base_v9` oracle、static clamp、O± 与 matched-clean 诊断继续停止。`base_v11_repair_r1` A/B 都从 staged v11_C step1550 policy-only 启动，seed0、literal `num_envs=4096`、500 batches/save125；唯一语义 A/B 差异是 `push_door_handle: 6→0`，两组 hinge 均为6。
- repair_r1 的 step125/250/375/500 共八个 matched eval（seed0、16 env、per-env first episode）均为 `0/16 goal`、`0 stage4`、`stage_overtime`。A500 mean max hinge `.002081rad`，仅为 `.25rad` threshold 的 `.832%`，并与 j8/base/workspace/doorframe regression co-occur；B 保留 stable hold/j8 guardrail，但 hinge flat。没有 promotable checkpoint、statistical winner 或 causal root cause。
- `base_v12` 四个 current-source、v10_A-style scratch factorial run（A/B/C/D）均为 `checkpoint=null`、`auto_load_latest=false`、seed0；它们不是 historical `base_v9` reproduction，因为 v9 使用 v8_A policy-only warm-start，且 historical source byte equivalence 未证实。
- v12 的实际 launch contract 保持每 rank literal `num_envs=4096`、2 ranks、global rollout batch8192、global cap3000/save250，不得除成2048。common config 包括 threshold `.25`、stage3 base locked、effort `10/10`、handle/hinge `6/6`、fixed penalty scale、cameras/render false、PhysX velocity iterations1。
- Matrix：A=`80/3 + stability .5`，B=`160/6 + .5`，C=`80/3 + 1.0`，D=`160/6 + 1.0`。四组 static/config checks 均 PASS，训练与 matched eval 终局见本节首条；由于 learned basin/stage exposure 不同，H 的 `.5→1.0` 与 gain 的 `80/3→160/6` 都没有形成稳定 factorial causality。

## Current Baseline

| Item | Value |
|---|---|
| Current behavior / warm-start reference | `base_v13_1_main` step3000 `policy_only` |
| Current training-ready config | `gr00t/rl/config/ablation/wbmanip/base_v14_main.yaml` |
| v14 warm-start | v13.1 step3000 `policy_only`; Option A `12D actor / 5D base command`，无spring observation |
| Training seed | `0` |
| TCP source local-Z | `0.085m` |
| Gripper Kp/Kd | v13_A `800/25`; v13_B/v13_pre `80/3` |
| Gripper effort limit | `10/10N` |
| Grasp gate | `control_streak`, K=`5` control steps; `physics_history` is explicit legacy ablation |
| Stage3 base | v13_A unlocked; v13_B/v13_pre locked |
| Stage3→4 threshold | `.25rad` |
| v13 reward | A: handle `0`, unlatch/hold-drive `3/8`, stability `.5`; B/pre: v12_C handle `6`, new terms `0`, stability `1` |
| Explicit friction override | none (`null`) |
| Formal v13.1 resource | saved runtime为4 ranks × `1024 env/rank`、global batch `4096`、`3000` batches/save250；已完成 |
| Matched eval | seed0、16 env、each-env first episode；scalar/trace primary |

当前training-ready config是`base_v14_main`；formal behavior/warm-start reference仍是`base_v13_1_main` step3000。v14尚无training/smoke/eval/checkpoint runtime或policy-quality evidence；所有训练/eval解释以保存的resolved runtime config为准，single-seed结果不能拆成单因素因果结论。

## Current Experiment

`base_v14_main`是当前training-ready experiment；M16–M20与M18 static reachability boundary已验证到批准范围。v14 formal training、smoke、matched eval、checkpoint runtime、policy quality与launcher natural exit均NOT RUN。

`base_v13_1_main` eval/render进程均natural exit0；其formal training launcher natural-exit状态未在本轮重新核验。下一步由用户启动formal `v14_main`，按iter500/1000/2000执行matched eval，并在endpoint完成canonical+seed1/2 bucket report与render；v14 training natural exit、checkpoint runtime与policy quality在实际run前均未验证。

## Inherited Base v0→v8 Lessons

- `replay_v2` 的视觉 grasp-like close 没有满足 formal bilateral force/history predicate；视频不能代替 success metric。
- `base_v0` effort `10→30` 与 `base_v2` gripper Kp/Kd `40/1→80/3` 都可能把 from-scratch RL 推入 open-gripper/no-contact basin；不要把 actuator sweep 当 sufficient fix。
- `base_v1` arm-only Kp/Kd 保留 replay behavior，说明负向分叉不是一般 retrain 必然漂移，但它仍未解决 bilateral grasp。
- `base_v3/v4` 证明 route/completion 与安全语义必须分开检查：history/threshold 可以放行错误 route，高 completion 也可能来自 `250N+` violent false-success。Hard predicate 应与 `squeeze_window` 和 `over_force` 对齐。
- `base_v5` 教训是不能按 filename 归因 run；必须核对 saved config、checkpoint、mtime 与 code state。
- `base_v6` 同时改变 TCP `.105→.085` 和 effort `10→40` 且停在 stage1，不能当成 effort-only 证据。
- `base_v7` 的 factor separation 支持当前 `.085/10` baseline；A `2/2 complete` 不代表后续 v9 hold route 已解决。
- `base_v8 A/A'` 显示 threshold `.6` 会先耗尽 j6 workspace；arm 仍需推门时不应恢复 stage4 arm-default-pose shaping。Scratch `base_v8 B` 从未进入 stage3/4，不能评价 hold retention。

## Evaluation and Command Contract

- `v13_A`/`v13_B` 的 user-approved formal topology 为每组4 GPUs / 4 processes、每 rank `num_envs=1024`，即每组 global rollout batch `4096`。该资源合同显式 supersede plan 附录里的2-rank/4096-env 示例与先前错误的4-rank/2048-env换算。A/B 使用独立 foreground terminal 与 distinct port，约 10 秒 stagger 后保持并行；禁止 detached wrapper、`setsid` 或单 shell `&`。
- Formal v9 matched resource contract：每组 2 GPUs / 2 processes，每 rank `num_envs=2048`，每组 total env 4096；四组保持相同 seed、source checkpoint、batch budget 与 environment count。
- 旧 `base_v11` launch 沿用 v10 resource contract：独立 foreground terminal、GPU pair、distinct port、约 10 秒 stagger。禁止 `setsid`、单 shell `&` 或 detached wrapper 管理 IsaacSim；2026-07-13 的 setsid 尝试曾产生 orphan parent/rank 与 Vulkan/GPU Foundation initialization failure。
- `base_v12` superseded the old repair_r2 proposal：四组 current-source scratch launch 使用 literal `num_envs=4096` per rank、2 ranks（global rollout batch8192）、global cap3000/save250、committed exact source freeze 与四个独立 foreground terminals/distinct ports；后续训练与 matched eval 已完成，终局见 Current State。
- Resume command 的 `num_total_batches` 必须写全局 target step：从 restored step1000 到 step2000 传 `2000`，不是传 remaining count `1000`；此 global-cap gotcha 继续适用于任何 future full-state resume。
- `base_v11` matched scalar/trace 使用 module invocation、seed0、16 env、每 env first episode；scalar/trace 是 primary evidence。比较 hinge max/terminal 与 stage4 entry，bilateral/stability、over-force、j7/j8 limit 作为 guardrail。
- 2-env render 必须显式覆盖 `++algo.config.num_mini_batches=2`；保存训练配置的默认值4会在trainer初始化时因 `batch_size=2` 不能整除而fail-fast。`v13_A` 的 `push_door_handle=0`，eval diagnostic reward list也必须显式移除该inactive term并加入active `a2_stage3_unlatch_hold`/`a2_stage3_stage4_hold_and_drive`，不得绕过active-reward validation。
- Render 保持相同 checkpoint/seed/episode semantics，只用于解释 contact、detach、jam、doorframe event 与动作自然性，不参与 success-rate 统计。默认从 matched eval env 中随机选取2个 env，只渲染这2个 env；每个 env 生成 default、handle-side、handle-top 3个 camera video，总计 `2 env × 3 camera = 6 videos`。除非用户明确要求，不再默认对16个 env 做全量 render；2-env qualitative subsample 不能替代16-env scalar/trace primary evidence。
- 原始完整 shell command 未保留；human report 中的 train/eval/render blocks 明确是从 saved Hydra overrides/config 重建的模板。
- Sibling worktree eval 使用 `python -m gr00t.rl.eval_agent_trl`，避免 direct-script invocation 命中另一 worktree 的 editable-install source。
- Future base-specific A2 eval 必须把完整 result folder 写到 `logs_eval/base_vN/<eval-run>/`：folder 直接包含 `.hydra/`、eval logs、metrics/traces/diagnostics 与可选 `renderings/`。`eval_output_dir` 是 canonical path，`eval_name` 仅为 leaf label；`base_eval.yaml` 的 `eval_log_dir` alias 与 rendering default 都跟随 `eval_output_dir`。该 co-location contract 已由 v13_pre/v13 endpoint scalar/trace 与A 2-env render runtime验证。现有base trace仍会在 `a2_diagnostic_trace_enabled=false` 时写出，不得据此误报strict no-trace PASS。
- Historical `logs_eval` migration：首批129个 version-named eval dirs 已归入 `base_v0..base_v11`；另有48个旧 top-level Hydra dirs whole-tree 迁移，36个 exact-paired 到 canonical result 的 `.hydra_provenance/<old-top-dir>`，12个 versioned/unpaired 到 `base_vN/_unpaired_hydra/<old-top-dir>`。`_eval_inputs` 与 `replay_v2` 保留 top-level，迁移后 top-level 共14项；无 symlink/collision，但未收集 content hash，故仅有 layout/static evidence。

## Evidence Boundaries

- 未证明 imported USD material override、exact collider/inner-pad geometry、closing axis/aperture 或 Cartesian reachability root cause。
- Target-side lever-center/X+Z recenter、source-side TCP local-Z `.105→.085` 与 source-local-Y O probes 是三个不同坐标变量，不能混写。
- Current C/D 失败不否定其他 base-follow reward/action design；A 的单 seed lead 也不是 final winner。
- 停止诊断表示当前路线信息增益不足，不表示 forced-close、gain、friction 或 geometry 在所有未来训练中永远无效。

## TODO Summary

- 2026-07-19 07:07 HKT - 用户启动formal `v14_main`；在500/1000/2000执行matched eval，并在endpoint完成canonical+seed1/2 bucket report/render。formal training natural exit、checkpoint runtime与v14 policy quality在实际run前均未验证。

## DONE Summary

- 2026-07-18 22:13 HKT - `base_v13_1_main` formal saved runtime完成到step3000；endpoint checkpoint SHA-256 `e836427e...167945`，resolved topology为4×1024、global batch4096、save250。
- 2026-07-18 22:13 HKT - step3000 matched eval exit0：16/16 goal、stage5、complete；完整scalar/trace/diagnostic artifacts位于`logs_eval/base_v13_1/..._r3/`。
- 2026-07-18 22:13 HKT - env0/1 render exit0并产出6个可逐帧解码的720p/20fps视频；indexless CUDA telemetry device mismatch已做最小fail-fast修复并通过13 tests、CODE_QUALITY与GPU runtime。
- 2026-07-17 20:05 HKT - `v13` final diagnosis、trap1/trap2、stage-boundary reward-rent audit与`base_v13_1_main` M11–M14/config/20/20+101/101/static/r3 smoke已同步；formal training/eval/render未启动，Kit natural exit未验证。
- 2026-07-17 15:39 HKT - A render sampled-frame目视复核：两env都持续带把手开门，无明显detach或拍门飞走；终点仍在门口以别扭姿态卡stage4。定性结果与positive-motion bilateral 99.949%/coasting .045%一致，但2-env render不替代16-env scalar/trace。
- 2026-07-17 15:18 HKT - v13 endpoint runtime完成：A step3000为0/16 goal、16/16 stage4、4/16 stage5，门运动与hold主指标通过但j8 open-limit超10%；B step1500为0/16 stage3，K=5 streak max仅3–4。A render成功产出6个可解码720p/20fps视频；2-env eval需把num_mini_batches从4覆盖为2，A diagnostic reward list需排除inactive push_door_handle。
- 2026-07-16 22:39 HKT - v13_A/B code/config/M5/M6/M9 与 4-rank concurrent smoke PASS；正式资源合同经用户纠正为1024 env/rank（global4096）：78 tests、compile、Hydra/static/diff checks PASS；A/B 各 `64 env/rank × 50` 完成并产出可 CPU load 的 step50/last checkpoint。正式 training 尚未启动，Kit post-checkpoint shutdown hang 由 Ctrl-C 释放，不声明 clean launcher exit。
- 2026-07-16 21:09 HKT - `v13_pre` M1 + M10 runtime PASS：control-step streak gate/config/telemetry 已实现，72 tests/compile/compose/diff checks PASS；v12_C step3000 matched r2 为 16/16 stage3 entry，首过 stage2 control-step `16/20.5/27`，stage3 bilateral/stability `99.815%/98.692%`，hinge 仍近零。根因 A 已证实，M2–M9/v13_A 尚未完成。
- 2026-07-16 00:29 HKT - 完成 `base_v12` A/B/C/D current-source v10_A-style scratch factorial configuration/static evidence sync：A `80/3+.5`、B `160/6+.5`、C `80/3+1.0`、D `160/6+1.0`；四组均 checkpoint null、planned 2 ranks、literal `num_envs=4096` per rank、global cap3000/save250。strict YAML/resolved compose/factorial/mapping、CODE_QUALITY、IsaacLab static/no-sim semantics 与 NO_SIM_QA PASS。`base_v12` 不是 v9 reproduction（v9 是 v8_A policy-only warm-start，historical source byte equivalence 未证实）；未启动 training/eval/IsaacSim/runtime，故没有 behavior、resource feasibility、checkpoint I/O 或 winner evidence。
- 2026-07-15 21:18 HKT - 新增 default render resource contract：从 matched eval env 中随机选2个 env，每个 env 只生成 default、handle-side、handle-top 3个 camera video，总计6个；16-env scalar/trace 继续作为 primary evidence，除非用户明确要求，不再默认16-env全量 render。
- 2026-07-15 20:56 HKT - `base_v11_repair_r1` A/B matched eval 完成：均从 staged v11_C step1550 policy-only 启动、seed0、literal `num_envs=4096`、500 batches/save125，唯一语义差异为 `push_door_handle: 6→0`（hinge均为6）。八个 step125/250/375/500 eval 均 `0/16 goal`、`0 stage4`、`stage_overtime`；A500 hinge 仅 `.002081rad`（`.25rad` threshold 的 `.832%`）且与 guardrail regression co-occur，B stable hold/j8 guardrail 但 hinge flat。因此没有 checkpoint promotion、statistical winner 或 causal root cause。
- 2026-07-15 20:56 HKT - 完成 historical `logs_eval` grouping/migration，并确立 future base-specific eval co-location：`eval_output_dir` 为 canonical grouped path、`eval_name` 为 leaf；config tests `3 passed` 与 resolved compose PASS。迁移无 symlink/collision，但未收集 content hash；新 eval runtime 未验证，以上不构成 runtime eval PASS。
- 2026-07-14 22:02 HKT - `base_v11` incomplete-budget matched eval 完成：九个 usable state 全为 `0/16 goal`、`0/16 stage4`、`stage_overtime`；A/B 仅 stage2、C 仅 stage3。A/B 无 stage3 exposure，不能评价 hinge12 H+；C 的 stable bilateral hold 没有转化为 hinge breakthrough，当前结果不是 full-budget/statistical winner。
- 2026-07-14 22:02 HKT - 确认 v11 的 source temporal confound 与 reward-evidence boundary：A 仅是 exact saved-config control，observation-order diff 是 plausible confound；hold/hinge realized magnitude imbalance 不构成 hold-dominant causality。旧的 stage3-exposed H+ resume 方向已由 repair_r1 执行证据 supersede，不启动训练。
- 2026-07-14 01:11 HKT - 完成 `base_v10` scratch A/B/C/D provenance、matched scalar/trace 与 D qualitative render 复盘；四组都未完成任务，当前仅形成 D stable-hold behavioral reference 与 approval-gated `base_v11` H+ proposal。详细 metrics、artifact 与命令见 human report。

- 2026-07-13 17:42 HKT - 用户提供历史 verified launch template，明确 v10 每组即使使用 2 processes 也保持 trainer override `num_envs=4096`，并沿用 `WANDB_MODE=online`、fixed reward penalty scale、stage2 contact threshold `1.0` 与 PhysX velocity iterations `1`；不得自行换算成 2048。
- 2026-07-13 17:41 HKT - 用户明确版本语义：新 `base_v10` 必须是四个 random-init long-training policies，不允许从 v9/v8 checkpoint warm-start；该决定 supersede 17:36 HKT 的 `base_v9_B policy_only` 方案。
- 2026-07-13 17:36 HKT - 归档并清理一次 launcher-only failure：删除四个 `20260713_173141` partial run 与对应 `/tmp` logs，终止 12 个 orphan processes；该启动未产出 checkpoint，不是 `base_v10` 实验结果。Durable gotcha 是 IsaacSim multi-group training 不使用 `setsid`/detached wrapper。
- 2026-07-13 16:37 HKT - 建立独立 full-stage push-open-door optimization memory；归档 `base_v9` 四组 formal/matched 失败结论、j8/body8 backdrive、gain/friction evidence boundary、matched-clean scientific failure与停止诊断决定，并把详细 base_v0→v9 findings/commands route 到 human report。
- 2026-07-19 07:07 HKT - `base_v14_main` training-ready implementation/M16–M20完成：保持v13.1 step3000 `policy_only`与Option A `12D actor / 5D base command`，4×1024/global4096/3000/save250；M19 `1.04 < 1.0472`，M20 strict telemetry/three-seed buckets/high cap1.05。
- 2026-07-19 07:07 HKT - M18 runtime PASS：artifact有210 exact cells/12 feasible、x `[0.55,0.60]`、cap1.05、1.10无feasible；static diagnostic evidence（door collisions disabled）不证明dynamic policy/hardware。45+31 tests、py_compile/Hydra compose/diff、CODE_QUALITY/IsaacLab/runtime QA PASS；v14 training/smoke/eval/policy quality NOT RUN。
