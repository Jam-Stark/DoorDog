---
name: base-v26-scratch-bilateral-teacher
scope: scratch-born bilateral A2+PiPER Teacher acquisition, far-start navigation, staged reset, and load consolidation
status: r0_formal_running
last_updated: 2026-08-21 21:01 HKT
owned_paths:
  - memory/a2-piper/MEMORY.md
  - memory/a2-piper/base-v26-scratch-bilateral-teacher/description.md
  - memory/a2-piper/base-v26-scratch-bilateral-teacher/TODO.md
  - memory/a2-piper/base-v26-scratch-bilateral-teacher/DONE.md
  - scriptsFORhuman/v26/V26_REWARD_LINEAGE_REVIEW.md
  - scriptsFORhuman/v26/a2_piper_base_v26_execution_ledger_20260821.md
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
  milestones，不改 reward。尚无 Route A、holdout、render 或 Teacher handoff
  PASS。
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
