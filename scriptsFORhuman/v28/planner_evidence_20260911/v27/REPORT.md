# V27-CLOSURE lane — 报告（READ-ONLY，2026-09-11）

证据等级：全部 **INSPECTED**（文件/代码原文）或 **COMPUTED**（本 lane 用标准库 json 从 reducer.json 重算，脚本输出 `/tmp/v28_team2/v27/recompute.txt`）。无 GPU、无 runtime、无 hardware 证据。

---

## 1. typed outcome 复核（对照预注册规则）

规则来源：`scriptsFORhuman/v27/a2_piper_base_v27_plan_20260905.md:95-99`（64 样本门 complete≥60、clean_complete≥56、low_height+overspeed≤2）与 `:219-223`（Wave C typed outcome）；实现 `scriptsFORhuman/v27/v27_reduce.py:368-376`（`passes_gate`）、`:477-482`（`_wave_c_guard`）、`:484-493`（`_first_wave_c_gate`）、`:496-520`（`wave_c_outcome`）。
数据来源：`logs_eval/base_v27/v27_bilateral_hardening_20260905/wave_c/step6000/reducer.json`（endpoint，`status=V27_COMPLETE`、`expected_n=64`、`endpoint=true`、`invalid_cells={}`、由 `part1/2/3` 汇总）。

### 1.1 step6000 逐格逐侧（COMPUTED）

| Cell | 侧 | D | S3+ | S4+ | open_hold | S5+ | complete | clean | lh+overspeed | terminations | gate |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| SC_S201 | left | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | stage_overtime 64 | ✗ |
| SC_S201 | right | 64 | 64 | 64 | 64 | 63 | 63 | 63 | 0 | complete 63 / stage_overtime 1 | ✓ |
| SC_S202 | left | 50 | 64 | 64 | 64 | 64 | 64 | 23 | 0 | complete 64 | ✗ |
| SC_S202 | right | 64 | 64 | 64 | 64 | 64 | 64 | 1 | 0 | complete 64 | ✗ |
| SC_S203 | left | 35 | 64 | 60 | 56 | 60 | 60 | 0 | 4 | overspeed 4 / complete 60 | ✗ |
| SC_S203 | right | 63 | 63 | 63 | 63 | 63 | 63 | 0 | 1 | overspeed 1 / complete 63 | ✗ |
| SK_S211 | left | 64 | 64 | 64 | 64 | 64 | 64 | 64 | 0 | complete 64 | ✓ |
| SK_S211 | right | 63 | 64 | 64 | 64 | 63 | 63 | 34 | 0 | complete 63 / stage_overtime 1 | ✗ |
| SK_S212 | left | 60 | 64 | 64 | 64 | 59 | 0 | 0 | 0 | stage_overtime 64 | ✗ |
| SK_S212 | right | 64 | 64 | 64 | 64 | 2 | 0 | 0 | 0 | stage_overtime 64 | ✗ |
| SK_S213 | left | 61 | 63 | 62 | 62 | 62 | 62 | 62 | 2 | overspeed 2 / complete 62 | ✓ |
| SK_S213 | right | 2 | 64 | 63 | 63 | 63 | 63 | 63 | 1 | overspeed 1 / complete 63 | ✓ |

首次双侧过门 milestone（COMPUTED，扫 1000–6000）：SC_S201/202/203 = None，SK_S211/212 = None，**SK_S213 = 6000**。与 `wave_c_decision.json.first_pass_milestone`、manifest v2 完全一致。

### 1.2 结论与 guard

- `sc_passed_seeds = 0` → **SCRATCH_NOT_ESTABLISHED**（0/3）：与规则一致 ✅
- `sk_passed_seeds = 1 > 0` 且三对 pair guard 全真 → **K_SCRATCH_SUPERIOR** 由第一分支（seed 数更多 + guard）触发，不需要 "≥2 seed 早 1000" 分支：与规则一致 ✅

guard 明细（SK 的 S4+/open_hold ≥ 同号 SC − 8，COMPUTED）：

| pair | left S4+ | left open_hold | right S4+ | right open_hold | 通过 |
|---|---|---|---|---|---|
| 211↔201 | 64 ≥ −8 | 64 ≥ −8 | 64 ≥ 56 | 64 ≥ 56 | ✓ |
| 212↔202 | 64 ≥ 56 | 64 ≥ 56 | 64 ≥ 56 | 64 ≥ 56 | ✓ |
| 213↔203 | 62 ≥ 52 | 62 ≥ 48 | 63 ≥ 55 | 63 ≥ 55 | ✓ |

**无 rule/label mismatch。** 但要记两条规则质量 caveat（不是 closure 的错，是预注册规则本身的弱点）：

1. **guard 退化。** 211↔201 LEFT 的 SC 基线是 0，阈值 −8 恒真；其余五项 SC 基线已饱和在 63/64，SK 也在 62–64，−8 容差从未被触及。该 guard 在本轮对任何 SK 结果都不会否决——正是 v27 plan `:78-79` 自己记录的 v26-8 "规则 19" 教训（guard 用了机制本要改变的量）的另一种形态。
2. **guard 对 SK_S212 完全不敏感。** SK_S212 双侧 complete = 0（彻底失败），但 S4+/open_hold 都是 64/64，guard 全过。"K 优于 SC" 因此建立在 1 个成功 seed + 1 个饱和但零完成 seed + 1 个零完成 seed 之上。closure 正文 `:132` 已明确写了这点，标签本身合规。

另一条 INSPECTED 观察：六个 milestone 的 72 条 lane 全部用 eval seed `270001`（`runtime_contract.seed`），即复用了 plan `:102` 注册的 DEV seed；plan 没有为 Wave C milestone 注册专属 seed，所以不构成违规，但属于欠规定。v28 §7 已经用 milestone `280001` / DEV `280101` / CONF `280201` 修掉了这个缺口。

---

## 2. scratch 到底怎么失败的

分类用任务给的 (a) 可达性 / (b) 质量 / (c) 早期阶段卡死；质量分量取自 `a2_piper_base_v27_wave_c_step6000_full_readout_20260911.json` 的 `quality_failure_components`（INSPECTED）。

| Cell/侧 | 类型 | 说明 |
|---|---|---|
| SC_S201 left | **(c)** | D=0、S3+=0、stage_overtime 64/64，1000–6000 六个 milestone 全部 0。LEFT 卡在 Stage2，与 v26-7 Q05_S0 / Q20_S0 的 LEFT Stage2 停滞同型（`v26_7 final_summary:96,104,113`）。 |
| SC_S201 right | 过门 | 5000 起过门（4000 时 S4+ 才 20）。 |
| SC_S202 left | **(b)** | complete 64，clean 23；失败 41 集中 crossing hinge < 1.0472 占 39、body force > 5 N 占 2。 |
| SC_S202 right | **(b)** | complete 64，clean 1；hinge 不足 63、body force 0。纯 crossing 质量失败。 |
| SC_S203 left | **(a)+(b)** | complete 60（刚好压线）但 overspeed 4 > 2 已独立否决；clean 0，hinge 不足 60 **且** body force > 5 N 60。 |
| SC_S203 right | **(b)** | complete 63，clean 0；hinge 不足 63、force > 5 N 43，`post_release_body_force_p95 = 715.8 N`。 |
| SK_S211 left | 过门 | 64/64/64 clean，是全 v27 唯一一个满分侧。 |
| SK_S211 right | **(b)** | complete 63，clean 34；29 集 body force > 5 N，p95 = 1016.9 N。hinge 全部合格。 |
| SK_S212 双侧 | **新失败型** | S4+/open_hold = 64/64，但 complete = 0、stage_overtime 64/64；LEFT S5+ 59 而 complete 0，RIGHT S5+ 只有 2。`arm_j4_limit_residence` = 0.158 / 0.655（臂顶限位）。即"能开门保持、开不完"。SC 三 seed 没有出现这种模式。 |
| SK_S213 双侧 | 过门 | LEFT 62/62、RIGHT 63/63。 |

### 轨迹（complete / clean，per side，COMPUTED）

| Cell | 1000 | 2000 | 3000 | 4000 | 5000 | 6000 |
|---|---|---|---|---|---|---|
| SC_S201 L/R | 0/0 · 0/0 | 0/0 · 0/0 | 0/0 · 0/0 | 0/0 · 0/0 | 0/0 · 63/59 | 0/0 · 63/63 |
| SC_S202 L/R | 0/0 · 0/0 | 0/0 · 0/0 | 0/0 · 63/11 | 64/0 · 60/18 | 59/0 · 63/10 | 64/23 · 64/1 |
| SC_S203 L/R | 0/0 · 0/0 | 0/0 · 0/0 | 64/0 · 63/0 | 61/0 · 64/0 | 61/0 · 60/0 | 60/0 · 63/0 |
| SK_S211 L/R | 0/0 · 0/0 | 0/0 · 0/0 | 0/0 · 0/0 | 0/0 · 0/0 | 0/0 · 0/0 | 64/64 · 63/34 |
| SK_S212 L/R | 0/0 · 0/0 | 0/0 · 0/0 | 0/0 · 0/0 | 0/0 · 0/0 | 0/0 · 0/0 | 0/0 · 0/0 |
| SK_S213 L/R | 0/0 · 0/0 | 0/0 · 0/0 | 0/0 · 64/1 | 0/0 · 63/58 | 1/1 · 64/64 | 62/62 · 63/63 |

**SC 在 6000 没有"还在改善"。** 可达性在 3000–4000 就到顶并开始回落（S203 complete 64/63→60/63；S202 LEFT 64→59→64，RIGHT clean 11→18→10→1 非单调下降，closure `:132` 已作为反向结果保留）。唯一还在上升的是 SC_S201 RIGHT（4000→5000 跨过），以及 SC_S202 LEFT 的 clean 0→23。质量维度上 SC_S203 六个 milestone 的 clean 恒为 0。相反 SK_S213 与 SK_S211 的跃升发生在 5000→6000，说明 6000 处在学习曲线的边缘而不是平台内部。

---

## 3. 与 warm-start 血统 / v26-7 的对比，以及对 v28 的含义

**血统（INSPECTED）**：`base_v27_C_S21.yaml:7,10` = 从 `C_S2/model_step_003000.pt` warm + 再 3000 batches；C_S2 本身是 v26-8 从 v26-7 `Q05_*/model_step_003000.pt` warm 3000（`v26_8 closure_wave1_r3a:34,45-46`）；Q05 是 scratch 3000。即 **C_S21 ≈ 9000 累积 batch、经两次 warm 重启**。它的 endpoint 是 complete 64/64，clean 51/41（closure `:44-45`）；C_S22 更差（61/62，clean 0/39，closure `:49-50`）。v26-7 纯 scratch 在 2000/3000 只拿到部分双侧 unlatch，且 3 个 seed 里 2 个的 LEFT 停在 Stage2。

由此得到两条对 v28 最重要的判断：

1. **6000 从零 ≠ 9000 warm。** SC 用的 recipe 与 C_S21 相同、base 相同（更简单，没有塔架/新姿态/clamp），预算 6000 仍 0/3。v28 计划在**更难**的 base 上用同样的 6000 从零跑 3 seed，先验上应当预期 `REACH_NOT_ESTABLISHED` 概率不低。
2. **质量门从来没被 warm 血统通过过。** 逐一核对 v27 全部 64 样本格（COMPUTED）：C_S21 clean 51/41、C_S22 0/39、L1_S32 63/52、R0_S41 52/47、R2_S41 7/41 —— 全部 clean < 56 至少一侧。**整个 v27 里唯一通过双侧 64 样本门的是 SK_S213@6000，而它是 from-scratch + K。** 所以"scratch 不行、warm 行"是错误的概括；正确的概括是"crossing-hinge / body-contact 质量门几乎谁都没过，唯一一次过是靠 K"。

**§8.3 路由本身正确**：`SCRATCH_NOT_ESTABLISHED` → G1 必做、G1 失败 STOP（v28 plan `:330`）；`K_SCRATCH_SUPERIOR` → 加 16 项 K + wrist 项（`:331`）。ADR D-12 的重审触发条件写的正是 `SCRATCH_NOT_ESTABLISHED`（`:66`），现在已经命中，所以"是否改设计"本来就该在这里讨论。

但 G1 有一个结构性错配：G1 的通过线是 500 batch 时双侧 D≥40、clean≥36、终止≤2、塔架接触≤2（`:316-317`），**远低于** 64 样本门（complete≥60、clean≥56）。而 warm 血统在 v27 的 3000 batch 后 clean 只有 51/41。因此 `WARM_PASS` 不能推出 warm arm 在 6000 能过门；它只能推出"warm 起点不是死盆地"。把 G1 当成"scratch 失败后的救援证明"会 over-claim。

### 可选项（证据支撑，不做决定）

| 选项 | 支撑证据 | 代价 / 反证 |
|---|---|---|
| **O1 提高 scratch 预算 6000→8000/9000** | SK_S213/S211 的跃升在 5000→6000；warm 血统累积 ≈9000；SC 的可达性 3000–4000 到顶但质量分量仍在动 | 22.15 s/iter → 每格 +12–18 GPU-h；3×9000+G1 = 27,500，v28 §10 的 36,500 上限下只剩 9,000，等于同时放弃备用 seed + warm arm + A2_Base opt-in |
| **O2 门拆成 reachability(complete≥60) vs quality(clean≥56)** | v27 中可达性被 4/6 Wave C 格与全部 warm 格达到，质量只有 1/6；合取门把"卡在哪"完全遮住，SC_S202 与 SC_S203 的失败原因（hinge vs hinge+force）本质不同却同标签 | 放宽选种门会削弱 Teacher 合同；折中是 Wave A **选种**用 reachability + 质量分量分级报告，Wave B **资格认定**仍用合取门。注意 v28 §7 还新增塔架安全门，合取只会更难 |
| **O3 默认带 K** | 预注册表已经要求带（K_SCRATCH_SUPERIOR）；SK_S213 是 v27 唯一过门格，SK_S211 LEFT 是唯一 64/64 clean 侧 | 1/3 seed；SK_S212 的"open_hold 64/64 + complete 0"是 SC 从未出现的失败型，且恰恰由 K 的 driver 语义诱发（见 §4）；K 让 reward scale 随时间变化，会与 v28 新增 reward 项混淆归因（D-01 反对三项变更叠加）。可行折中：带 K，但把 SK_S212 型停滞（连续两个 milestone S4+≥56 且 complete≤4）预注册为具名失败并落 driver trace |
| **O4 warm arm 升为主线** | v27 中达到 complete 64/64 双侧的只有 warm 的 C_S21 | D-12 的动作零点漂移在 v28 是实打实的（j4/j5 默认角整体移动 + 新 tower link + 新 asset）；warm 从未过质量门。若采用，应是**追加**arm、用同一个 64 门判定，而不是用 G1 的弱标准 |
| **O5 条件延长（最省）** | 只在 `REACH_SEED_UNSTABLE` 或"6000 时仍单调上升"时预注册一次 7000/8000 延长 | 不触发就零成本；但需要在 launch 前冻结"仍在上升"的判据，否则变成事后挑 checkpoint（v27 plan `:226` 明确禁止） |

---

## 4. K block 的 v28 落地细节

### 4.1 `base_v27_SK_S211.yaml:13-45` 的精确键（INSPECTED）

| 行 | 键 | 值 |
|---|---|---|
| 13 | `env.config.a2_v26_side_permutation_seed` | `211` |
| 14 | `env.config.a2_v26_8_penalty_driver` | `side_min_natural_stage_reach_rate` |
| 15 | `..._driver_target_stage` | `4` |
| 16 | `..._driver_level_down_rate` | `0.5` |
| 17 | `..._driver_level_up_rate` | `0.7` |
| 18 | `..._penalty_curriculum_trace_enabled` | `true` |
| 19–20 | `checkpoint_load_mode` / `policy_only_load_actor_rms` | `full` / `false` |
| 22–28 | `rewards.reward_penalty_curriculum` / `initial` / `min` / `max` / `degree` / 两个 legacy `*_ave_goal_reached_rate` | `true` / `1.0` / `0.2` / `1.0` / `-0.0001` / `null`、`null` |
| 29–45 | `rewards.reward_penalty_reward_names`（16 项） | `walk_to_door`, `gripper_handle_orientation`, `pregrasp_gripper_dof_pos_l1`, `pregrasp_target_distance`, `grasp_target_distance`, `grasp`, `a2_stage2_close_command`, `a2_stage2_close_progress`, `a2_stage2_handle_center_y`, `a2_stage2_handle_approach_xz`, `a2_stage2_both_contact`, `a2_stage2_opposite_squeeze`, `a2_stage2_squeeze_force_window`, `a2_stage2_contact_stability`, `a2_stage3_handle_creation`, `a2_stage3_unlatch_hold` |

⚠️ §8.3 写的区间 "13-45" 含**行 13 的 `a2_v26_side_permutation_seed: 211`**，这是 seed 专属键，v28 的 A_S281/282/283 必须用各自的 seed，不能整段照抄。

### 4.2 v28 新 reward 键的取舍

机制（INSPECTED）：`legged_robot_base.py:1647-1649` 对名单内 reward 乘 `reward_penalty_scale`；`:527-529` 把 scale==0 的 reward 从 `reward_scales` 里 pop 掉；`door_open_a2_base.py:7996-8003` 要求名单内每个名字都还在 `reward_scales` 里，否则 init 直接 `RuntimeError`。

- **`penalty_a2_wrist_motion_l2` → 追加（17 项）。** 与 §6.2 一致：它在 Stage2 与 16 项 scaffold 同窗口生效，scaffold 衰减到 0.2 floor 而它不衰减时相对占比升 5×。scale −0.4 非零，不会触发上面的 fail-fast。附带风险：任何把它调成 0 的 v28 消融分支必须同步从名单删除，否则 init 崩。
- **`penalty_a2_wrist_tower_contact` → 排除。** 它是硬件损坏安全项（D-07），且 v28 §7 把 `wrist_tower_contact_episodes_gt_5N ≤ 2` 做成硬门。放进衰减名单会在 Stage4 reach rate 上升（= driver 抬高）时把安全惩罚降到 0.2 倍，与门的方向相反。§6.2 已明确写"不进衰减名单"，一致。
- **`penalty_a2_stage4_arm_default_pose_l1` → 建议明确排除（plan 目前是隐式排除）。** 三条理由：(i) 现有 16 项全是 Stage0–3 的正向 scaffold，wrist 项之所以破例是因为**同窗口**的相对占比论证；stage4 姿态项只在 Stage4 释放后生效，那时 16 项的收入基本为零，不存在相对占比问题。(ii) 它是 v27 缺陷（释放后臂 L1 7–8 rad 无回位激励）的**矫正项**；driver 恰恰由 Stage4 到达率驱动，把它放进名单等于"策略越常到 Stage4，矫正越弱"。(iii) 它同时是 §7 里 Stage0/5 姿态与释放后回位阈值能否达标的前提。

### 4.3 driver 对 Stage 语义的依赖（`door_open_a2_base.py`，INSPECTED）

driver 值 = **两侧取 min** 的（natural episode 中 `current_max_stage_buf ≥ target_stage(=4)` 的比例）；natural = `episode_start_stage == 0`（`:8038-8064`）。`> 0.7` → `scale *= 1+degree`（degree = −1e-4，即衰减）；`< 0.5` → `scale *= 1−degree`；clip 到 [0.2, 1.0]（`:8098-8113`）。前置硬约束：`a2_v26_bilateral_metrics_enabled=true`（`:7885-7888`）、`a2_v26_door_open_lr=="bilateral"`（`:7926-7927`）、`reward_penalty_curriculum=true`（`:7928-7931`）、不得同时配 legacy level 键（`:7933-7948`）。

v28 的姿态/asset 变更对它的影响：

1. **Stage 阈值本身不变。** v28 §2.2 保留 Stage3→4 `0.25`、Stage4→5 `1.0472`、release `1.2`，`num_stages` 不变，所以 `target_stage=4` 的语义是稳定的。这是好消息。
2. **危险耦合在于 target_stage 衡量的是"到达"不是"完成"。** SK_S212 就是活例：open_hold 64/64（Stage4 到达率≈1）→ driver 持续 > 0.7 → scaffold 一路衰到 0.2 floor，而 complete 始终 0、stage_overtime 64/64。v28 新增塔架碰撞 + 动作 clamp + 新姿态都会**扩大** Stage4 到达与完成之间的落差，正好是这个失败模式的放大器。预注册的备选（`target_stage=5`，或改成完成率驱动）值得写进 v28 的 fallback 而不是临场决定。
3. **反方向是良性退化。** `initial = max = 1.0` 且 degree < 0，scale 只能从 1.0 往下走。若更难的 base 把 Stage4 到达率压到 0.7 以下，K 就永不衰减、静默退化成普通配方——不会炸，但也等于没做 K 实验。所以 driver trace 必须是 v28 的必看量而不是可选量。
4. **trace 与 D-16 的交互。** `:8026-8036` 要求 `env.config.experiment_dir`，且 `trace_path.touch(exist_ok=False)`——同一个 experiment_dir 重启会直接 fail-fast。v28 的 `++experiment_dir` 约定（D-16）需要保证训练 root 每次 attempt 唯一，否则重启即崩。
5. 评估侧不受影响：v28 §7 沿用 `a2_v26_8_penalty_driver=null`，与 Wave C 的 12 条 endpoint lane 的 `runtime_contract` 实测一致（COMPUTED）。

---

## 5. Teacher / G7 绑定裁决

manifest v2（`a2_piper_base_v27_teacher_candidate_manifest_v2_20260911.json`，INSPECTED）：`status=V27_COMPLETED_SCIENTIFIC_NO_RELEASE`、`qualification=NO_QUALIFIED_CANDIDATE`、`selected_candidate=null`、`wave_c.sc_outcome=SCRATCH_NOT_ESTABLISHED`、`sk_outcome=K_SCRATCH_SUPERIOR`、`final_confirmation.status=NOT_RUN`（`sc_reason` = 无 SC seed 在任何 milestone 双侧过门；`q0_reason` = NO_QUALIFIED_CANDIDATE）、`SK_substitution=false`、`binding_changed=false`。6 个候选全部 `confirmation128="NOT_RUN"`、`binding_eligible=false`；**SK_S213 是唯一 `milestone64_pass=true` 但同样 `binding_eligible=false`**。

**没有任何 v27 checkpoint 达到 128 样本资格**（COMPUTED，复核 closure `:30-35` 的 v27.0 DEV 表对 128 门 120/112/4）：

- C_S2：clean 75 / 69 → 双侧 < 112，不过。
- W_S2：RIGHT 127/112、终止 0（stage_overtime 不计）→ **RIGHT 单侧过**；LEFT clean 100 < 112 → 双侧不过。
- K_S2：LEFT clean 71 不过；RIGHT clean 119 ≥ 112、complete 122 ≥ 120，但 overspeed 5 > 4 → 不过。

Wave C 六格从未跑 128（全部 exact64），所以连"单侧 128 数据"都不存在。

**建议裁决文本（Owner，MAINTAIN）：**

> 维持现有 Teacher 与 Student G7 绑定（v23 单 RIGHT），不更新。
> 理由：(1) v27.0 资格认定为 `NO_QUALIFIED_CANDIDATE`，三个 128 样本候选无一双侧过 128 门（C_S2 clean 75/69；W_S2 仅 RIGHT 过、LEFT clean 100；K_S2 RIGHT 因 overspeed 5>4 被否）；(2) Wave C 六格全部只有 exact64 数据，两个预注册的 exact128 确认按冻结选择规则记为 `NOT_RUN`，不做 SK 替换、不挑中途 best；(3) 唯一通过 64 样本双侧门的 SK_S213@6000 是 1/3 seed 的单 seed 模拟结果，同族 SK_S212 双侧 complete=0，不构成可靠性证据；(4) 全程无 hardware 证据。
> 重审触发：v28 Wave B 产出通过 128 样本门（含塔架安全门）并完成 CONF 的 `BILATERAL_TEACHER_QUALIFIED_SIM_V28` 候选；在此之前 SK_S213 只作为 v28 K 配方决策的依据，不作为绑定候选。

---

## 6. 交付与状态

- 产出文件：`/tmp/v28_team2/v27/REPORT.md`、`/tmp/v28_team2/v27/recompute.txt`（复算原始输出）。
- 仓库零改动（READ-ONLY），无 git 操作，无 GPU，无 writer、无 lease。
- 未运行：任何 128 样本评估、任何 v28 训练或 smoke；本报告的第 3 节选项为证据陈列，**不含决定**。
