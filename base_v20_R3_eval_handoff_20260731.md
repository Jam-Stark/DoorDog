# base_v20 R3 → v20 R2/R3 Eval Handoff

**Date:** 2026-07-31 HKT
**Branch:** `A2_Piper`（工作树干净，HEAD=`d620edc`）
**交接目标：** 另一个 session 接续，按 **v20 R2/R3 方案对已完成 formal 训练的 7 组 checkpoint 做 eval**。
**一句话状态：** R2 admission（P0）已通过、R3 正式训练（7 组 G1–G7 × 2500 batch）已全部 `exit 0` 完成、源码改动已提交并有溯源文档、source lock 已重冻结到与训练源码一致。**Eval 是唯一未完成的阶段**，当前卡在一个已定位的 R2 evidence finalizer bug 上。

---

## 0. 你（下一 session）的第一步

先读这两个文件，再上任何 eval：

1. **改动溯源文档（必读）：** `scriptsFORhuman/a2_piper_base_v20_R3_change_log_20260731.md`
   - §1–§2：R2/R3 改动按「是否影响 reward 语义」分级（A 级 reward 语义 / B 级 telemetry / C 级工具链）。
   - **§10（本次 eval 交接的核心）：** eval 路径已修的 3 处 bug + **未决的 finalizer bug（你的入口）** + 可复用的 eval smoke 命令。
2. **Memory：** `memory/a2-piper/push-open-door-optimization/description.md` 首条（2026-07-31）。

**严格约束（不可违反）：**
- **GPU 仅用物理 `cuda:0..6`；GPU7 绝对禁止**（任何 argv/env/config/receipt 出现 `cuda:7`/`GPU7` 即 fail-fast）。非 render 用 `ACCELERATE_TORCH_DEVICE=cuda:N` 且**不设** `CUDA_VISIBLE_DEVICES`；render 用 `CUDA_VISIBLE_DEVICES=N` + 逻辑 `cuda:0`。
- **fail-fast**：不加多余 guard/fallback/silent catch/type suppression；invalid state 直接 raise。
- **smoke-first（用户硬性要求）：** 改任何 env/reward/evidence/eval 代码后，先跑 `num_envs=64 + num_total_batches=10` 的单组单卡 smoke（或单 checkpoint 16env eval smoke）确认无 runtime 错误，再铺全量。
- **wandb 用 online 模式**（用户实时监控）。
- Python：`/home/baoquanc/anaconda3/envs/isaaclab/bin/python`（`-B`）；`PYTHONPATH=/home/baoquanc/workspace/DoorDog-A2_Piper`。

---

## 1. 已完成（不要重做）

| 项 | 状态 | 位置/证据 |
|---|---|---|
| R2 static admission（P0 27 命令） | PASS（`d343b24`，27/27） | `logs_eval/base_v20_R2/locks/{R2_REVISION_1_SOURCE_FREEZE,P0_STATIC_PASS,ACTIVE_SOURCE_LOCK}.json` |
| **R3 formal 训练** | **7 组全部 `exit 0` + step2500 checkpoint** | `logs_rl/a2_piper_full_stage_a2_base/base_v20_R3_G{1..7}-20260731_*/model_step_002500.pt`（每组另有 step250..2500 共 10 个 checkpoint） |
| 源码改动 | 已提交 | `git log`，最新 `d620edc`；溯源文档 `scriptsFORhuman/a2_piper_base_v20_R3_change_log_20260731.md` |
| source lock 一致性 | 已解决 | lock 重冻结到 `d343b24`（含运行时修复），与训练/评估源码一致；`815d2d8` 旧 lock 归档 `_stale_*` |
| 崩溃残留 | 已清理 | 36 个失败训练目录 + 失败 launcher log 已删 |

**7 组训练 config（eval 时逐组用）：** `gr00t/rl/config/ablation/wbmanip/base_v20_R2_{G1_g2_continuation,G2_economics_only,G3_send_curriculum_only,G4_send_curriculum_economics,G5_send_curriculum_arm_tie,G6_full,G7_full_seed1}.yaml`（P2 是 learnability pilot，非 formal 组）。

---

## 2. 你的任务：按 v20 R2/R3 做 eval

R2 方案的 post-formal 评估链：`formal_completion → M22（70 checkpoint = 7 组 × 10 step）→ pooled48 → holdout64 → render → final analysis`。

**重要：** 我们**跳过了** R2 pre-formal 的 DAG 门（B0/forced/zero-shot/P1/pilot/smoke/promotion，直接跑了 formal），所以 `formal_completion.py` 依赖的 `FORMAL_WAVE_ATTEMPT_CONSUMED` / `PROMOTION_PASS` 等 marker **不存在**。你有两条路：

- **路线 A（推荐，务实）：** 绕过 DAG marker，直接对 70 个 checkpoint 做 M22 式 eval，量出每组 goal/crossing/held 指标。先修 §3 的 finalizer bug 让单 checkpoint eval 出 record，再铺 70 组。
- **路线 B（严格）：** 补齐 DAG marker 链（formal_completion 等），但若要严格走 `formal_completion.py` 需补 `FORMAL_WAVE_ATTEMPT_CONSUMED`（或改造它接受已有的 formal 训练目录）。

建议路线 A：先让 eval 出结果，再决定是否补严格 admission。

---

## 3. 当前卡点（你的第一优先级）：R2 evidence finalizer bug

**现象：** smoke eval（G1 step2500, 16env, canonical16）已过 init + 跑完 episode，但崩溃于
`RuntimeError: R2 finalizer requires topology/scenario/factor/phase mappings.`
（`gr00t/rl/envs/door/door_open_a2_base.py:7653`，`finalize_a2_v20_r2_episode_record`）

**根因：** finalizer（`:7644-7652`）需要 `topology/scenario/factor/phase` 四个 mapping——优先取参数，否则从 provenance 里 pop。我 smoke eval 手撸的 override 只给了基础 provenance（`source_lock_sha256`/`git_commit`/checkpoint 等），**没给这四个** → fail-fast。

**修法方向（不是 reward 问题，是 R2 evidence 的 provenance 契约缺口）：**
1. 读 `door_open_a2_base.py:7635-7680`（finalizer）与 `_r2_required_provenance`（搜 door_open_a2_base.py）弄清这四个 mapping 的确切 schema。
2. topology 的 setdefault 在 `:7655-7664`（`name=canonical16`、`environment_count=num_envs`、`expected_episode_count=num_envs`、`first_episode_only=True`、`single_process=True`、`render=False`、`physical_gpu∈0..6`）。
3. 让 `workflow.eval_command`（`scriptsFORhuman/v20_R2/_r2_workflow.py:300`）在 provenance 里注入这四个 mapping（或 eval 时以参数传入），使 finalizer 能取到。
4. 改完先 smoke（单 checkpoint 16env）确认 record 产出，再铺全量。

**已验证可复用的 eval 命令骨架**（`workflow.eval_command` 正确构建，source lock 解包后 provenance 含 `git_commit` 与 lock 一致）：
```
python -B -m gr00t.rl.eval_agent_trl \
  +checkpoint=<ckpt.pt> +num_envs=16 +seed=0 +headless=true \
  +r2_evidence_enabled=true \
  +r2_bound_config_path=<cfg.yaml> +r2_bound_config_sha256=<sha> +r2_resolved_config_sha256=<sha> \
  +env.config.a2_v20_R2_trace_root=<out>/traces \
  +env.config.a2_v20_R2_record_set_staging_path=<out>/record_set.staging.jsonl \
  +env.config.a2_v20_R2_provenance={...} \
  +env.config.a2_v20_R2_group=G1 +r2_command_sha256=<sha>
```
（用 `workflow.eval_command(...)` 生成 argv 最稳，勿手敲 provenance。）

---

## 4. 已修的 eval 路径 bug（`79a28f9`，不要重复踩）

1. `_source_lock_provenance`（`_r2_workflow.py:393`）解包 `ACTIVE_SOURCE_LOCK` 包装器（schema==`active_source_lock_v1` → `lock["source_lock"]`）。
2. `eval_agent_trl._validate_r2_runtime_bindings`（`eval_agent_trl.py:133`）同样解包。
3. `_canonical_config_sha256`（`eval_agent_trl.py:228`）加 `default=str`（PosixPath→str）。

---

## 5. 关键路径速查

- Checkpoints：`logs_rl/a2_piper_full_stage_a2_base/base_v20_R3_G{1..7}-20260731_*/model_step_{000250..002500}.pt`
- Source lock：`logs_eval/base_v20_R2/locks/ACTIVE_SOURCE_LOCK.json`（`d343b24`）
- eval 输出规范：写 `logs_eval/base_v20_R2/<eval-run>/`（co-location）
- 训练 config：`gr00t/rl/config/ablation/wbmanip/base_v20_R2_*.yaml`
- 溯源文档：`scriptsFORhuman/a2_piper_base_v20_R3_change_log_20260731.md`（§10 eval 交接）
- R2 计划：`scriptsFORhuman/a2_piper_base_v20_R2_admission_and_execution_plan_20260730.md`

**Git 状态：** 工作树干净（HEAD=`d620edc`）。注意：repo 根有 3 个 LFS 指针 zip（`base_v20_P1_*`/`base_v20_R1_static_admission_blocker_handoff_*.zip`）在工作树显示 deleted——**与本任务无关，不要提交它们的删除**。

---

## 6. 完成定义（eval 阶段的 DoD）

1. finalizer bug 修复，单 checkpoint eval（G1 step2500, 16env）产出合法 record_set。
2. 70 个 checkpoint（或至少 7 组 step2500）eval 完成，每组 goal/crossing/held 指标落盘。
3. 按 smoke-first：每次代码改动后先 smoke 再铺全量。
4. GPU0–6 only、GPU7 禁用、wandb online。
5. 结果与改动同步进 memory +（如改源码）追加到 change_log §10。

祝顺利。有溯源文档 §7 的 git 手册可助你定位任何回归。
