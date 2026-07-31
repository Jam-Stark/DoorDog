# base_v20 R2/R3 改动溯源文档（Change Log for Git Traceability）

**Date:** 2026-07-31 HKT
**Branch:** `A2_Piper`
**目的：** v20 R2/R3 改动复杂且**改动了训练源码**。若正式训练效果（reward 曲线、行为、checkpoint 质量）被这些源码改动影响，本文档配合 git 用于**溯源 / 定位可疑 commit / 修复 / 回溯**。
**阅读顺序：** §1 总览 → §2 按「是否影响学习」分级 → §3 reward 语义改动详录 → §4 telemetry 改动 → §5 工具链改动 → §6 commit 总表 → §7 git 溯源/回溯操作手册 → §8 当前产物状态。

---

## 1. 总览：改动的两大组成部分

R2/R3 工作分两层，**只有第一层可能影响训练效果**：

| 层 | 内容 | 是否影响 policy 学习 |
|---|---|---|
| **A. 训练源码层** | `gr00t/rl/envs/**`、`gr00t/rl/train_agent_trl.py`、`gr00t/rl/eval_agent_trl.py`、`gr00t/rl/utils/average_meters.py` | **可能**（其中 reward 语义改动直接影响；telemetry 改动不影响） |
| **B. 准入工具链层** | `scriptsFORhuman/v20_R2/**`（freeze/P0/adjudicator/workflow）、plan `.md`、plan-lock | **不影响**（只决定"候选是否可受理"，不进 reward） |

**冻结科学方向未被 R3 改变：** 8 个 R2 config（`gr00t/rl/config/ablation/wbmanip/base_v20_R2_{G1..G7,P2}_*.yaml`）的科学取值（`seed`/`num_envs`/`num_total_batches`/`send_curriculum`/`economics`/`arm_tie`/`crossing_mode`/reward scales/stage thresholds）自 `17c7fa7`+`3255cf4` 定义后**字节级未被 R3 触碰**。R3 只改了训练/评估**源码**，没改这些 config 的科学取值。

---

## 2. 按「是否影响学习」三级分类（溯源第一入口）

> **若训练效果异常，优先怀疑 A 级。**

### A 级：REWARD/行为语义改动 —— 直接改变 env 给 policy 的 reward 或 episode 行为

| Commit | 文件:位置 | 改动 | 对学习的影响 |
|---|---|---|---|
| `3255cf4` | `door_open_a2_base.py`（527 行）+ `a2_v20_r2_evidence.py`（118 行）+ `legged_robot_base.py`（7 行） | R2 env 集成：R2 evidence/telemetry 嵌入 env | 大（引入 v20 evidence 路径；若其中有 bug 会影响训练） |
| `14e0668` | `door_open_a2_base.py:8162-8219` | **G1 crossing-mode 守卫**：disabled crossing 时不再调 `a2_v20_r1_durable_crossing_event`，改为 `_a2_v20_pre_send_crossing_event.zero_()` | 中（G1 crossing event 语义：从"崩溃"→"按 norm-control 意图禁用"） |
| `14e0668` | `door_open_a2_base.py:8493` | **staged-reset streak 恢复顺序**：仅对 `just_resetted 且 stage∈{OPEN,SWING}` 的 env 保留恢复的 `stage3_stage4_streak` | 中（M45 parity：恢复 streak 不再被 post-reset 回调清零；**仅 staged reset 激活时有影响**，from-scratch formal 可能不触发） |
| `f7190d7` | `legged_robot_base.py:1995` | `_reward_termination()` 返回 `.float()`（原 `reset_buf * ~time_out_buf` 为 bool） | **数值等价**（bool True=1.0/False=0.0 → float 1.0/0.0），reward 幅值不变，仅 dtype 修正 |

### B 级：Telemetry/Evidence 改动 —— 改变 R2 证据如何累积，但**不改变**给 policy 的 reward

| Commit | 文件:位置 | 改动 | 对 reward 的影响 |
|---|---|---|---|
| `f7190d7` | `door_open_a2_base.py:7053` | `_r2_reward_component_sums` 初始化改用 `reward_scales` config 兜底 | 无（仅 R2 evidence 累积器的 key 集合） |
| `f7190d7` | `door_open_a2_base.py:7231-7239` | evidence `step_index` clamp + `step_mask` 屏蔽 reset 边界 env | 无（决定 evidence 样本写哪个时间槽，不进 reward） |
| `f7190d7` | `door_open_a2_base.py:7275` | `valid_hinge` AND `step_mask`（reset 边界 env 不计入 M48 smoothness） | 无（M48 evidence 样本有效性） |
| `f7190d7` | `door_open_a2_base.py:10155-10197` | `_after_reward_components`：expected 跟随 `raw_components` 动态扩展；`scaled_value` bool→float；dtype 校验放宽（float 才校验 finite） | 无（R2 evidence 累积；reward 由 env `_compute_reward` 独立计算，不变） |
| `14e0668` | `eval_agent_trl.py`（152 行）+ `_r2_workflow.py`（108 行） | eval 消费绑定的 R2 config + 完整 provenance | 无（eval 证据路径） |

### C 级：准入工具链改动 —— 只决定候选受理，不进训练 reward

| Commit | 文件 | 改动 |
|---|---|---|
| `3437325` | `source_freeze.py`, `test_a2_v20_staged_reset_state.py` | R2 P0 gate 修复（parity 字面值、hidden 扫描范围、staged_reset 测试 17→19） |
| `53ee534` | `_r2_common.py` | rebind `R2_PLAN_SHA256`（whitespace 后 plan hash 漂移） |
| `e186ddd` | plan `.md`, `_r2_common.py` | 去行尾空格 + EOF 空行（满足 diff_check） |
| `815d2d8` | `test_a2_v20_R2_executable_dag.py` | 测试 stub source-lock provenance |
| `f7190d7` | `train_agent_trl.py:81-86` | 训练启动校验解包 `ACTIVE_SOURCE_LOCK` 包装器 |
| `f7190d7` | `average_meters.py:55` | bool tensor → float before `mean()` |

### D 级：文档/配置（非源码逻辑）

| Commit | 内容 |
|---|---|
| `15011cf` | R2 admission plan `.md` + plan-lock JSON |
| `17c7fa7` | **8 个 R2 config** + `door_open_a2_base.yaml` + `reward_door_open_a2_base.yaml` + `staged_task_base.py` + `a2_v20_r2_evidence.py`（R2 evidence 初版） |
| `ed03931` | 测试 source coverage 动态化 |
| `7833fff` | memory 记录（R2 blocker） |

---

## 3. A 级 reward 语义改动详录（重点审查对象）

### 3.1 G1 crossing-mode 守卫（`14e0668`，`door_open_a2_base.py:8162-8219`）

**背景缺陷：** G1 config `a2_v20_pre_send_crossing_mode: disabled`，但 `_update_a2_v20_state`（telemetry 激活，G1 恒真）在 `:8201` 无条件调用 `a2_v20_r1_durable_crossing_event(mode="disabled")`，helper(`:72`,`:484`)只认 `penalty|terminal` → 运行时必 `ValueError`。R2 从未真跑训练，故潜伏。

**改动（before → after）：**
```
# before: 无条件调用（G1 崩溃）
self._a2_v20_pre_send_crossing_event[:] = a2_v20_r1_durable_crossing_event(
    pre_send_event, hard_pending, mode=self._get_a2_v20_pre_send_crossing_mode())

# after: 按 R1 crossing lifecycle 守卫
crossing_mode = self._get_a2_v20_pre_send_crossing_mode()
r1_crossing_lifecycle_enabled = r1_send_curriculum_enabled and (crossing_mode in A2_V20_R1_CROSSING_MODES)
if r1_crossing_lifecycle_enabled:
    self._a2_v20_pre_send_crossing_event[:] = a2_v20_r1_durable_crossing_event(..., mode=crossing_mode)
elif crossing_mode in A2_V20_R1_CROSSING_MODES:  # penalty/terminal 但 curriculum off
    self._a2_v20_pre_send_crossing_event[:] = pre_send_event
else:  # disabled
    self._a2_v20_pre_send_crossing_event.zero_()
```

**对 G1 的净效果：** G1（disabled + curriculum off）→ crossing event **置零**（no-op）。这与 v19 G2 norm-control 的"crossing 禁用"意图一致。**若 G1 训练本应保留某种 crossing 行为，此处是可疑点**；但按科学计划 G1 就是 disabled，故为零是正确的。

**回溯：** `git revert 14e0668` 会连带回滚同 commit 的 staged-reset/eval/tooling 改动，**不可整 commit revert**。如需单独回滚此 hunk：`git checkout 14e0668^ -- ` 后用 `git show 14e0668 -- gr00t/rl/envs/door/door_open_a2_base.py` 取出该 hunk 手工反向。

### 3.2 staged-reset streak 恢复顺序（`14e0668`，`door_open_a2_base.py:8493`）

**背景缺陷：** staged-reset 恢复的 `a2_stage3_stage4_both_contact_streak` 被 post-reset partial observation 回调立即清零，喂不到 stage-4（M45 parity 意图被架空）。

**改动：** reset 时不再无条件 `stage3_stage4_streak[env_ids]=0`；改为仅对 `just_resetted_buf & stage∈{OPEN,SWING}` 的 env **保留**恢复值，其余才清零。

**对学习的净效果：** 仅当 staged reset 激活（`enable_staged_reset`）时有影响——恢复的 streak 存活。**From-scratch formal 训练若不在中途 staged reset，此改动可能不被触发；若 curriculum 使用 staged reset，则会影响。** stage-5 continuation 本就存活（未改）。

**回溯：** 同 3.1，不可整 commit revert，需 hunk 级反向。

### 3.3 termination float（`f7190d7`，`legged_robot_base.py:1995`）

**改动：** `_reward_termination()` 从 `self.reset_buf * ~self.time_out_buf`（bool）改为 `.float()`。
**数值等价性：** bool→float 是恒等映射（True→1.0, False→0.0）。`scaled = raw * reward_scales["termination"]` 的数值结果**完全相同**。**不影响训练效果**，纯 dtype 修正以通过 R2 校验。
**回溯：** 无需回溯；如极端谨慎可 `git revert f7190d7` 但该 commit 还含必要 telemetry 修复。

---

## 4. B 级 telemetry 改动说明（不影响 reward）

这些改动全部服务于 **R2 evidence**（`a2_v20_R2_evidence_enabled=true` 时激活的证据累积/record/trace），用于 admission/eval 的严格裁决。它们**不改变** `env._compute_reward()` 输出给 PPO 的 reward 张量：

- `_r2_reward_component_sums`（`:7053`）：R2 evidence 的 per-component 累积器，只读 reward_scales 做 key 集合。
- `_update_a2_v20_r2_evidence_accumulators`（`:7231`+）：把 hinge 速度/加速度/jerk 按 step 写入 evidence 数组。
- `_after_reward_components`（`:10155`+）：R2 evidence 的 reward component 累积与校验。

**验证「不改 reward」的方法：** 对比同一 checkpoint 在改动前后 `env._compute_reward()` 的输出（`raw_components`/`scaled_components` 数值）——这些由 env 的 reward 函数独立产生，上述 telemetry 只是**消费**它们做证据，不回写。

---

## 5. C 级工具链改动说明（不影响训练）

`scriptsFORhuman/v20_R2/**` 全部改动只影响 **admission**（source freeze / P0 / adjudicator / workflow）与 **eval evidence 管线**。训练 reward 完全不经过这些文件。`train_agent_trl.py` 的改动只在**训练启动前的绑定校验**（读 lock、校验 schema/commit），不进训练循环。

---

## 6. Commit 总表（hash → 级别 → 文件 → 一句话）

| Hash | 级别 | 文件 | 摘要 |
|---|---|---|---|
| `15011cf` | D | plan `.md`, plan-lock | R2 admission plan 文档 |
| `17c7fa7` | D+A | 8 configs, env/reward config, `staged_task_base.py`, `a2_v20_r2_evidence.py` | R2 admission workflow 实现（**v20 科学取值在此定义**） |
| `3255cf4` | A | `door_open_a2_base.py`(527), `a2_v20_r2_evidence.py`, `legged_robot_base.py`, `eval_agent_trl.py` | R2 env 集成（**最大 env 改动**） |
| `ed03931` | D | `test_a2_v20_R2_p0_binding.py` | 测试 coverage 动态化 |
| `e186ddd` | C | plan `.md`, `_r2_common.py` | whitespace/EOF（满足 diff_check） |
| `53ee534` | C | `_r2_common.py` | rebind `R2_PLAN_SHA256` |
| `3437325` | C | `source_freeze.py`, staged_reset 测试 | R2 P0 gate 修复 |
| `7833fff` | D | memory | R2 blocker 记录 |
| `14e0668` | A+B+C | `door_open_a2_base.py`, `eval_agent_trl.py`, `_r2_workflow.py`, `_r2_common.py`, `source_freeze.py`, `p0_adjudicator.py`, p0_binding 测试 | **R3 rebuild**（crossing 守卫 + staged-reset + eval/provenance + immutable-hash + parity + hidden + lint） |
| `815d2d8` | C | `test_a2_v20_R2_executable_dag.py` | 测试 stub provenance |
| `f7190d7` | A(等价)+B+C | `door_open_a2_base.py`, `legged_robot_base.py`, `train_agent_trl.py`, `average_meters.py` | R3 运行时训练源码修复 |
| `79a28f9` | C | `eval_agent_trl.py`, `_r2_workflow.py` | R3 eval 路径运行时修复（解包 ACTIVE_SOURCE_LOCK ×2 + `_canonical_config_sha256` default=str） |

---

## 7. git 溯源 / 回溯操作手册

### 7.1 快速定位「训练效果异常」的可疑级别
```
# 训练 reward/行为异常 → 先看 A 级（env/reward 语义）
git log --oneline 17c7fa7..f7190d7 -- gr00t/rl/envs/
# 仅 telemetry/证据异常（reward 正常但 evidence/record 错）→ B 级
git log --oneline 14e0668..f7190d7 -- gr00t/rl/envs/door/door_open_a2_base.py
# admission/eval 受理失败（训练正常）→ C 级
git log --oneline -- scriptsFORhuman/v20_R2/
```

### 7.2 git bisect（若不确定哪个 commit 引入问题）
```
git bisect start
git bisect bad f7190d7            # 有问题
git bisect good 3255cf4          # 已知良好点（按实际调整）
# bisect 会自动二分；每步跑 smoke test（num_envs=64, num_total_batches=10）判定
```

### 7.3 精确回滚单个 hunk（A 级改动不可整 commit revert，因 commit 混入多级改动）
```
# 取出某 commit 对某文件的全部改动
git show <hash> -- gr00t/rl/envs/door/door_open_a2_base.py > /tmp/change.diff
# 反向应用单个 hunk（用 git apply -R 配合手工截取目标 hunk）
git checkout <hash>^ -- gr00t/rl/envs/door/door_open_a2_base.py   # 回滚该文件到改前
```

### 7.4 整 commit revert（仅限纯单一级别 commit）
```
git revert 815d2d8   # 纯测试 stub，可安全 revert
git revert 53ee534   # 纯常量 rebind，可安全 revert
# 不要 revert 17c7fa7/3255cf4/14e0668/f7190d7（多级改动混合，revert 会误伤）
```

### 7.5 验证「改动是否影响 reward」的金标准
对同一 warm-start checkpoint，在改动前后跑相同 smoke（64env×10batch），对比 `raw_components`/`scaled_components` 的 reward 数值与曲线。若一致 → 改动是 telemetry/tooling；若漂移 → 改动是 reward 语义。

---

## 8. 当前产物状态（2026-07-31）

- **正式训练：** 7 组 G1–G7 全部 `exit 0`、产出 `model_step_002500.pt`（2500 batch 最终 checkpoint），目录 `logs_rl/a2_piper_full_stage_a2_base/base_v20_R3_G{1..7}-20260731_*`；launcher `logs_rl/launchers/base_v20_R3_formal_20260730/G{1..7}.{sh,launch.log,exit_code}`；wandb online 可监控。
- **Source lock：** `logs_eval/base_v20_R2/locks/R2_REVISION_1_SOURCE_FREEZE.json`（commit `d343b24`，含 `f7190d7` 运行时修复，与训练/评估源码一致；`815d2d8` 旧 lock 已归档 `_stale_*`）。
- **P0：** `P0_STATIC_PASS.json` + `ACTIVE_SOURCE_LOCK.json` 已签发（`d343b24`，P0 27/27 全过）。
- **失败证据：** R2 各次失败 receipt 不可变保留于 `logs_eval/base_v20_R2/admission/_failed_*`、`locks/_failed_*`。

---

## 9. 重要一致性问题（source lock vs 训练源码）

当前 `ACTIVE_SOURCE_LOCK` 冻结于 `815d2d8`，但 `f7190d7` 的运行时训练源码修复（reward_scales 兜底、reward coverage、termination float、evidence step_index、mean bool）**在其后提交，未包含在 lock 内**。正式训练实际跑的是 `f7190d7`（工作树）代码。这符合「以训练为先」的指示，但意味着 lock 与训练源码存在一个 commit 的偏差。若后续要严格 admission（B0/eval 绑定 lock），需用 `f7190d7` 重新 freeze 生成新 lock，使 lock 与训练源码一致。**[已解决]：2026-07-31 已用 `d343b24`（含 `f7190d7` + 改动文档 + memory）重新 freeze + 重跑 P0(27/27) + adjudicator，新 `ACTIVE_SOURCE_LOCK.json` 现绑定 `d343b24`，与训练/评估源码一致。**

---

## 10. Eval 路径运行时修复与未决问题（2026-07-31，`79a28f9`）

R3 eval 管线（`eval_agent_trl.py` + `_r2_workflow.py`，eval-pipeline 在 `14e0668` 引入的 config-consumption/provenance 改造）**与训练一样从未真跑过**，smoke eval（G1 step2500, 16env, canonical16）暴露并已修 3 处 runtime bug；**仍有 1 处未决 bug 是下一 session 的入口**。

### 10.1 已修（`79a28f9`）
1. **`_source_lock_provenance` 解包 ACTIVE_SOURCE_LOCK**（`_r2_workflow.py:393`）：原用 `read_artifact(schema=source_lock_v1)` 直接读 `ACTIVE_SOURCE_LOCK.json`（包装器，schema=`active_source_lock_v1`）→ schema mismatch。改为 `load_json` + 若 schema==`active_source_lock_v1` 则解包到 `lock["source_lock"]`，再校验 `source_lock_v1 + SOURCE_FROZEN`。
2. **`eval_agent_trl._validate_r2_runtime_bindings` 解包**（`eval_agent_trl.py:133`）：同 `train_agent_trl` 的解包（schema==`active_source_lock_v1` → `lock["source_lock"]`）。
3. **`_canonical_config_sha256` 加 `default=str`**（`eval_agent_trl.py:228`）：composed config 含 `PosixPath` → `json.dumps` 崩。加 `default=str`（路径对象→字符串，确定性不变）。

### 10.2 未决 bug（下一 session 入口）
**`RuntimeError: R2 finalizer requires topology/scenario/factor/phase mappings.`**（`door_open_a2_base.py:7653` `finalize_a2_v20_r2_episode_record`）。eval 已过 init + 跑完 episode，但 R2 evidence 定稿器要求 `topology/scenario/factor/phase` 四个 mapping（`:7644-7652`：优先用参数，否则从 provenance pop）。smoke eval（canonical16、手撸 override）只传了基础 provenance，未传这四个 mapping → 定稿器 fail-fast。**修法方向：** 这四者应由 workflow 在 eval_command/provenance 里注入（topology 见 `:7655-7664` 的 setdefault：name=canonical16、environment_count、single_process、physical_gpu；scenario/factor/phase 需查 `_r2_required_provenance` 与 m22/canonical16 的 provenance 契约补齐），或在 m22_runner 的 canonical16/m22 路径里提供。这是 R2 evidence finalizer 的 provenance 契约缺口，不是 reward 问题。

### 10.3 eval smoke 验证过的路径（可复用）
`workflow.eval_command(repo_root, checkpoint, config, gpu, seed, num_envs, output_root, mode="canonical16", group)` 能正确构建 eval argv（source lock 解包后 provenance 正确，含 `git_commit` 与 lock 一致）。`/tmp/smoke_eval_g1_run.py`（本 repo 外用）演示 build+run+读 record。eval 命令形如 `python -B -m gr00t.rl.eval_agent_trl +checkpoint=<ckpt> +num_envs=16 +seed=0 +headless=true +r2_evidence_enabled=true +r2_bound_config_path=<cfg> +r2_bound_config_sha256=<sha> +r2_resolved_config_sha256=<sha> +env.config.a2_v20_R2_trace_root=<out>/traces +env.config.a2_v20_R2_record_set_staging_path=<out>/record_set.staging.jsonl +env.config.a2_v20_R2_provenance={...} +env.config.a2_v20_R2_group=G1 +r2_command_sha256=<sha>`。

## 11. Route A eval/render 完成（2026-08-01 05:31 HKT）

- Eval evidence/runtime 修复提交为 fe090a7、7a0835f、e9a8957、df90ab8、823f2b6、f8e3197；属于 B/C 级 evidence/eval 工具链改动，不改变 PPO reward 科学取值。最终 P0 对 f8e3197 为 27/27 STATIC_PASS，G1 step2500 smoke 的 16-record set 为 runtime STRICT_VALID。
- Route A artifact root 为 logs_eval/base_v20_R2/m22_r3_route_a_f8e3197_offline_20260801/。70/70 checkpoints 均 natural exit 0 且 record set STRICT_VALID；1120 episodes 的 goal/crossing/held-crossing 为 1055/1097/1093，group goal G1–G7 为 157/155/150/145/153/143/152（各 160）。
- 代表性 render 为 G1-2500、G4-750、G6-2500、G7-2500。成功 root renders_retry2/ 含 4 个 natural exit-zero receipts、7 records、21 个 1280×720@20fps MP4；OpenCV full decode 共 13,203 帧 PASS。
- Render durable gotcha：1/2/3-env topology 不能继承 num_mini_batches=4，否则 trainer 初始化 exact_div fail-fast；异常 teardown 可能忽略 SIGINT/SIGTERM。Hydra append +algo.config.num_mini_batches=1 后自然完成。
- 资源边界：eval GPU0–6、render GPU0–3、GPU7 未使用；本轮全部 WANDB_MODE=offline。仅关闭推荐 Route A；pre-formal DAG marker、pooled48、holdout64、Route B final analysis 未运行。
