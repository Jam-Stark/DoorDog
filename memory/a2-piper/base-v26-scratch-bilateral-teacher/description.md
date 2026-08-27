---
name: base-v26-scratch-bilateral-teacher
scope: scratch-born bilateral A2+PiPER Teacher acquisition, far-start navigation, staged reset, and load consolidation
status: v26_2_complete_not_admitted
last_updated: 2026-08-25 10:54 HKT
owned_paths:
  - memory/a2-piper/MEMORY.md
  - memory/a2-piper/base-v26-scratch-bilateral-teacher/description.md
  - memory/a2-piper/base-v26-scratch-bilateral-teacher/TODO.md
  - memory/a2-piper/base-v26-scratch-bilateral-teacher/DONE.md
  - scriptsFORhuman/v26/V26_REWARD_LINEAGE_REVIEW.md
  - scriptsFORhuman/v26/a2_piper_base_v26_execution_ledger_20260821.md
  - scriptsFORhuman/v26/a2_piper_base_v26_final_analysis_20260822.md
  - scriptsFORhuman/v26/a2_piper_base_v26_acquisition_supplement_20260823.md
  - scriptsFORhuman/v26/a2_piper_base_v26_teacher_handoff_manifest_20260822.json
  - scriptsFORhuman/v26_2/a2_piper_base_v26_2_unlatch_reward_plan_20260825.md
  - scriptsFORhuman/v26_2/a2_piper_base_v26_2_pull_derived_plan_20260825.md
  - scriptsFORhuman/v26_2/a2_piper_base_v26_2_handoff_prompt_20260825.md
read_when:
  - implementing, training, evaluating, or resuming base_v26
  - selecting the scratch bilateral Teacher or load-robust continuation
---

# base_v26 Scratch Bilateral Teacher

## Purpose

本 entry 路由 v26：高层 Teacher 从随机初始化出生，LEFT/RIGHT 从 batch 0
共同训练；保留 frozen A2_Base low-level policy、FULL posture、active planar base、
strict Stage2 grasp 与 current release/handoff。R0 成功后才进入 moderate load
consolidation。

## Authority and current state

- Canonical plan: `scriptsFORhuman/v26/a2_piper_base_v26_execution_plan_R1_20260821.md`。
- Execution ledger: `scriptsFORhuman/v26/a2_piper_base_v26_execution_ledger_20260821.md`。
- Reward lineage: `scriptsFORhuman/v26/V26_REWARD_LINEAGE_REVIEW.md`。
- Final analysis: `scriptsFORhuman/v26/a2_piper_base_v26_final_analysis_20260822.md`。
- Acquisition supplement: `scriptsFORhuman/v26/a2_piper_base_v26_acquisition_supplement_20260823.md`。
- v26-2 pull-derived unlock plan:
  `scriptsFORhuman/v26_2/a2_piper_base_v26_2_pull_derived_plan_20260825.md`。
- Superseded v26-2 raw-removal-only plan:
  `scriptsFORhuman/v26_2/a2_piper_base_v26_2_unlatch_reward_plan_20260825.md`。
- Teacher handoff: `scriptsFORhuman/v26/a2_piper_base_v26_teacher_handoff_manifest_20260822.json`。
- 2026-08-21 18:37 HKT - 已完成 required memory/source 回溯与真实 runtime
  binding。GPU0–3 空闲；GPU4–7 的独立 Student 不属于 v26。
- 2026-08-21 19:09 HKT - 1-env LEFT/RIGHT、64-env LR 10-batch smoke 与
  4096-env LR 10-batch short-learning gate 均已完成真实 Isaac Sim rollout、
  optimizer update 与 checkpoint save。4096 runtime 固定为 2048/2048，约
  12.9k steps/s；R0 formal matrix 已准入。
- 2026-08-21 19:15 HKT - 四格 4096-env / 4000-batch R0 matrix 已在独立
  tmux 启动并分别绑定 GPU0–3；launcher 将 CUDA visibility 限定为 0–3，
  GPU4–7 只保留独立 Student PID。
- 2026-08-21 21:01 HKT - 四格均写出 step250 checkpoint，exact side count
  未漂移；各格 Stage2 occupancy 约 66–73%，LR seed1 RIGHT 有 Stage3
  high-water，hinge/goal 仍为 0。按 scratch long-horizon contract 继续至后续
  milestones，不改 reward。
- 2026-08-22 23:33 HKT - 四格均完成 4000 batches/exit0；Route A 2,176
  episodes、holdout 256 episodes与双侧三视角 render 全部完成。formal staged
  reset 中 LR S1 左右 Stage3 occupancy 约 29%，但 natural-start holdout LEFT
  0/128 到 Stage3、RIGHT 仅 1/128 到 Stage3，双侧 goal 均 0。阻塞定位为
  natural Stage2 strict-grasp→Stage3/unlatch transition，而非 far-start 或单纯
  bilateral interference。R1 未准入；无 v26 Teacher，Student G7 binding 不变。
- 2026-08-23 01:19 HKT - Owner 将历史 stand-off acquisition 路线裁决为 v26
  增补任务，不创建新 phase。文档固定 `0.70 m` 窄 staging anchor、scratch
  `80/3` + velocity iterations 1、strict control-step K5；双侧 natural repeated
  grasp 后才 policy-only 切 `800/25` + velocity iterations 2。当时尚未实施。
- 2026-08-25 02:07 HKT - acquisition supplement 已完整执行：四格 scratch
  4000/4000 与 2,176-episode Route A 恢复 repeated bilateral natural K5；
  `LR_S1_STEP3000` LEFT `3/64`、RIGHT `2/64` 到 Stage3。其 policy-only
  `800/25` continuation 完成 3000/3000；896-episode Route A 的
  `CONT_STEP2000` 达 LEFT `64/64`、RIGHT `61/64` Stage3，但所有 goal
  为 0。最终边界为 Stage3 unlatch exploration，R1/Teacher/Student 均未准入。
- 2026-08-25 03:20 HKT - Owner 将已完成 supplement 正式命名为 `v26-1`，并
  要求规划 `v26-2` Stage3 unlatch reward 实验。实际日志表明 1000 是重要判读点
  但不是通用终点：v13_A 到约 2000 才出现 Stage4，v13.1 在 500–1000 已快速
  收敛，v26-1 natural bilateral Stage3 到 2000 才稳定出现且后续非单调。v26-2
  因此规划 C0 raw-handle6 与 T0 raw-handle0 的 matched two-cell、每格最多
  2000/save250；formal training 只需 GPU0–1，尚未实现或运行。
- 2026-08-25 03:37 HKT - Owner 提供同机 pull-v1/v2/v4 完整证据，03:20 的
  raw-removal-only 计划已 supersede。实际 pull 并非 random actor scratch，而是从
  base-v20→pull-v0→v1-R→v2-W 的 policy-only warm lineage；`pull_door_handle=6`
  在 v1-R 创建稳定 handle depression，随后 `near_closed 0.1→0.25` 在 v2-W
  拆除 reward wall并形成真实 Stage4。pull handle reward 还受 tensile/load-bearing
  mask，不能与当前 ungated `push_door_handle` 等同。新 v26-2 从
  `CONT_STEP2000` 设计 C/A/R/W 四格：A→R 隔离 K5-gated depression scale6，
  R→W 隔离 threshold0.25；Wave1 GPU0–3 各750，conditional W relay双seed各750，
  最长 lineage1500，尚未实现或运行。
- 当前机器无 GPU-backed X display；interactive GUI preview 不可用。已用真实
  headless runtime 的 asset metadata、root pose、rollout 与训练日志完成对应
  几何/初始化证明，不把该边界写成 GUI PASS。

## Frozen acquisition decisions

- `checkpoint=null`, `checkpoint_load_mode=full`, `auto_load_latest=false`。
- bilateral process 精确 half LEFT / half RIGHT，按 seed 对 env_id 做一次固定
  permutation；snapshot 保持 per-env，因此不会跨 side。
- natural start 使用 door-relative normal `0.90–1.40m`、lateral `±0.25m`、
  yaw `±0.30rad`；Stage0 timer 350 control steps。
- handedness privileged observation 两槽为 LEFT `[1,0]`、RIGHT `[0,1]`；
  observation dimension 不变，Student 不增加 privileged side label。
- R0 friction off、handle height `0.85–0.95m`、door mass `80–120kg`；
  R1 load mixture 只有在 bilateral repeated goal 后才准入。

## Validation boundary

Static/config/runtime/training evidence必须按实际层级记录。v25 的 G7 或 matched
causality evidence不能替代 v26 scratch acquisition 结果。

## Durable runtime findings

- 新 door selector 不仅要实现于 task scenario module，还必须在
  `gr00t/rl/simulator/isaacsim/isaacsim.py::_get_task_obj_cfg_dict_for_door_eval`
  注册入口；否则会落回旧随机 `TaskObjCfgDict`。v26 runtime count check 会在
  optimizer 前明确失败。
- Trainer 的 episode metric accumulator 要求浮点张量；内部 exact count 保留
  `torch.long`，只在写入 `log_dict` 时转 float。
- 4096 个确定性 door variants 首次 scene creation 约 439 秒；后续每个 PPO
  update 约 20.3 秒。正式 4000-batch run 必须独立 tmux 长跑。
- 多个 IsaacSim 单卡进程若取消 `CUDA_VISIBLE_DEVICES`，会在所有可见 GPU
  建立辅助 context；与独立任务共享机器时，应将 visibility 限定到获批 GPU
  集合，再用 `ACCELERATE_TORCH_DEVICE` 选择集合内的单卡。
- 正式日志由 `scriptsFORhuman/v26/summarize_v26_r0_progress.py` 按精确
  iteration 抽取，累计输出为 `logs_eval/base_v26/r0_progress.json`；不要用
  latest table 冒充已冻结 milestone。
- Staged-reset Stage3 occupancy 不能替代 natural-start complete-chain evidence；
  v26 的 LR S1 在后段 reset 状态可占据 Stage3，但 Route A/holdout 几乎不能
  从 natural Stage2 进入 Stage3。
- USDRT headless render 要求进程内 device ordinal 为 `cuda:0`。使用非零物理
  GPU 时，将该物理卡设为唯一 `CUDA_VISIBLE_DEVICES`，并将
  `ACCELERATE_TORCH_DEVICE` 设为 `cuda:0`。
- v26 plan 虽写明 Stage0 staging target 约 `0.70 m`，正式 common config 未显式
  覆盖，saved config 实际继承 `[0.55,0.60] m`；LR S1 holdout Stage0→1
  standoff p50 约 `0.591 m`。后续不能把计划文字当成 runtime binding。
- v13.1 的 `800/25` + velocity iterations 2 是 v12_C mature grasp actor
  policy-only warm-start 后的 retention/full-chain 能力，不是 batch-0 scratch
  discovery 的历史正证据。
- 原 `policy_only` loader 会把 actor observation RMS 作为 policy submodule
  一起加载。v26 supplement 新增显式 `policy_only_load_actor_rms: false`；
  strict-load actor MLP/std/LSTM，同时保持 actor RMS、critic、optimizer、
  scheduler、trainer state、environment 与 staged-reset buffers fresh。
- `CONT_STEP2000` natural trace 已证明 close persistence 不是剩余阻塞：
  Stage3 bilateral contact 为 1.0，contact stability 为 `0.9689/0.9666`，
  但 handle-joint max 仅 `0.0001305/0.036833 rad`，hinge max 仅
  `0.002131/0.002110 rad`，全部 Stage3 episode overtime。
- Pull-v1/v2 的 durable transfer boundary：`pull_door_handle=6` 相对 no-handle
  control 创建稳定 depression，`near_closed 0.1→0.25` 再创建 Stage4；但其 actor
  是 policy-only warm lineage，gripper为45N/1300/32，且 handle/hinge reward受
  pull-only load-bearing mask。v26-2 只能移植 creation/wall-removal 原理，不能声称
  current raw push term 或 random scratch 已由 pull 证明。
- v26-2 first causal ladder从同一 `CONT_STEP2000`、相同 policy-only + actor-RMS
  contract 启动：A→R 只切 K5-gated handle-depression `0→6`，R→W 只切
  `near_closed 0.1→0.25`。Wave1 750、conditional relay 750；checkpoint selection
  只依据 bilateral natural evidence。
- 2026-08-25 10:54 HKT - v26-2 pull-derived Wave1 C/A/R/W 均以
  `CONT_STEP2000` policy-only + inherited actor RMS 完成 750 iterations、exit0。
  四格共 24/24 个 natural Route A evaluation（每 checkpoint 每侧 exact 64）均
  完成；W `STEP0750` 为 LEFT `32/64`、RIGHT `36/64` Stage3，Stage4 为
  `0/64`、两侧 `handle>=0.6 & hinge>=0.1` 均为 0，integrity counters 为 0。
  因而 Stage3 retention passed，但第二个 admission/creation gate failed，整体
  typed outcome 为 `HANDLE_CREATION_NOT_SUPPORTED`；R→W 为
  `WALL_REMOVAL_NOT_SUPPORTED_IN_PUSH`。conditional relay 未运行；选定的
  `W_STEP0750` bilateral render 仅达 Stage2、无 goal。Teacher/Student handoff
  不更新，当前状态为 `v26_2_complete_not_admitted`。
