# DONE

- 2026-08-21 00:04 HKT - 完成 v25 memory/ledger 起步：记录 worktree/branch/commit/dirty state、GPU/tmux 边界、G7 anchor、v24 friction route，并从独立 Student 的实际 resolved config read-only 确认 `CONFIRMED_G7_STEP1500`。尚无 Isaac Sim/runtime/training PASS。
- 2026-08-21 00:09 HKT - 完成 M1 static implementation：新增 deterministic LEFT-only Hydra preset，经现有 simulator task-config hook 用高层 `DoorSpawnerCfg.replace(...)` 固定 `left/out`；未修改 env reward/stage。CPU/light smoke compose config、执行 selector function body并加载 G7 static policy contract，结果 `V25_M1_CPU_LIGHT_SMOKE_PASS`，边界 `NO_ISAAC_SIM_NO_CUDA`。
- 2026-08-21 01:35 HKT - 完成 M1 Isaac Sim runtime/visual proof。单环境 preset 增加 `num_mini_batches=1` 以满足真实 eval trainer 的 batch contract；RIGHT/GPU0 446-step episode `complete` 且正 hinge/+X crossing 成功，LEFT/GPU1 正确镜像 handle/hinge/target 并进入 stage 2，但 452 steps `stage_overtime`。证据边界为每侧 seed0 单 episode；尚未做 mixed-LR、formal training 或 Teacher qualification。
- 2026-08-21 01:43 HKT - Owner 明确确认 M1，解除 Phase C gate；不改变 push/out、Student 或 pull-door 边界。
- 2026-08-21 02:16 HKT - 完成 Phase C mixed-LR runtime：64×8 G7 policy-only warm-start 自然 exit0，32 LEFT/32 RIGHT，8 次真实更新并写出 `model_step_000008.pt`；mixed8 eval 产出 per-env numeric/semantic side 字段，G7 RIGHT 6/6 goal、LEFT 0/2。
- 2026-08-21 02:16 HKT - 完成 P02/P10/P20 native-friction mixed16 pilot，三个 eval 均自然 exit0；选定 P10 `10/7.5/0 N.m` 为 v25 formal 与 causality 的固定主负载。CVD 失败根因被定位为 Isaac Sim 5.1 Vulkan/CUDA 枚举冲突，后续统一使用 unset CVD + 原生 `cuda:N`。
- 2026-08-21 02:34 HKT - M2 pre-launch gate 完成：FULL/RP0 P10 均 64×8 natural exit0、32 LEFT/32 RIGHT、curriculum-off，各有 step8。GPU0-3 四个 4096×1500 formal cells 已进入真实第 1 次 update，物理卡 readback 分别为 cuda:0/1/2/3，初始 ETA 约 10.2 h。
- 2026-08-21 04:26 HKT - 四个 formal cells 均写出 step250 checkpoint 并继续运行；不存在 OOM/traceback 或单格预算变更。
- 2026-08-21 16:06 HKT - 四个 FULL/RP0×seed0/1 P10 formal cells 全部自然完成 1500/1500 batches，每格 6,144,000 episodes、393,216,000 timesteps，并保存 step250-1500 checkpoints。
- 2026-08-21 16:06 HKT - 完成 G7/FULL side-stratified Teacher comparison 与 FULL/RP0 chronic comparison。FULL S0 step500 将 LEFT crossing-while-holding 提升到 22/32 且保持 RIGHT 32/32 goal，但无 clean LEFT goal；最终产品裁决为 retain G7，Student worktree/process 未改。
- 2026-08-21 16:06 HKT - 完成 P10 50-step matched-prefix 2×2 intervention：30 LEFT/32 RIGHT paired states，planar 主效应稳定为正而 posture 即时 hinge 主效应中性/轻微负向；chronic FULL/RP0 与 LEFT contact retention 支持 posture 的 reach/grasp/contact-geometry 作用。JSON、paired PNG、Teacher/causal videos 与 final analysis 均已落盘。
