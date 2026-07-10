# Base v8 → Base v9 Hold-Handle Diagnostic（2026-07-10）

## Technical Summary

结论先行：后续应走 B hold-handle route，但第一优先级不是继续加 forced-close / gripper Kp / effort，而是让 base 在 stage3 随开门过程移动，并把 stage3→4 transition 放在“已有门进度、尚未耗尽 arm workspace”的区间。

同一个 frozen `base_v8 A` ckpt1000 的三组 controlled eval 给出一致证据：

- `D0` 在 threshold `0.174533` 时 8/8 提前进入 stage4，door 随后回弹；stage4 全程只有 `arm_body8` 单侧接触，base 几乎不动。
- `D1` 在训练时 threshold `0.6` 下 8/8 留在 stage3，door 能稳定推到约 `0.257 rad`，但 `arm_j6` 在 8/8 成为 limiting joint，直接暴露 arm-only workspace bottleneck。
- `D2` 在 D0 上强制 gripper close 没有增加 bilateral/stable contact，只带来很小 door 增益并恶化 TCP slip，证明“下发 close target”不是“握住 handle”。

因此推荐 `base_v9` 首轮做 2×2：threshold `{0.174533, 0.25}` × stage3 base `{locked current, unlocked}`。四组共享 B hold bundle，并使用相同 policy-only initialization、重置 optimizer/curriculum/snapshots、对齐 seeds。workspace-margin shaping 保留为第二轮 single-variable ablation。

## Provenance and Scope

| Item | Control |
|---|---|
| Policy | [`base_v8 A` ckpt1000](../logs_rl/a2_piper_full_stage_a2_base/base_v8_A_release_after_open-20260708_215459/model_step_001000.pt)，三组完全相同、frozen |
| Sampling | D0/D1/D2 各 8 env，单 seed，每 env 1 episode，no-render |
| D0 | [A' threshold diagnostic](../logs_eval/base_v8_A_ckpt1000_D0_diag_Aprime_8env_20260710)：threshold `0.174533`，forced-close off |
| D1 | [A training-threshold diagnostic](../logs_eval/base_v8_A_ckpt1000_D1_diag_AtrainThreshold_8env_20260710)：threshold `0.6`，forced-close off |
| D2 | [Forced-close intervention](../logs_eval/base_v8_A_ckpt1000_D2_diag_forcedClose_8env_20260710)：threshold `0.174533`，stage3/4 gripper primitive 强制 `-1.0` |
| D3 | [Default-off regression](../logs_eval/base_v8_A_ckpt1000_D3_defaultOffRegression_2env_20260710)：2 env，diagnostics/forced-close 均 off |

指标口径：`hinge max/end` 是先取每个 env 的 episode 最大值/terminal 值再跨 env 求 mean；`base physical linear command` 是 action routing 后的 base linear command norm，不等同于 measured root velocity；`normalized arm margin` 是 joint 到 soft limit 的最小归一化余量，小于 0 表示越界；`bilateral/stability` 使用当前 handle-contact force 与 history predicate；`TCP slip` 指 TCP/source 相对 handle target 的距离恶化。

Diagnostic implementation 把 stage3→4 threshold 收敛为 env config single source of truth，并为 legacy A2 checkpoint 做显式 migration；expanded trace 与 forced-close 都是 eval-only opt-in，修正了 first-episode isolation 和 action timing。Static/config tests、Oracle review 与 D0-D3 runtime 均 PASS。D3 2/2 正常结束并到达 max stage4，且未生成 `a2_eval_diagnostic_metadata.json`，验证 default-off path 没有污染普通 eval。

## D0 / D1 / D2 Controlled Comparison

| Run | Changed factor | Stage outcome | Door hinge | Base / arm | Handle grasp signal |
|---|---|---|---|---|---|
| D0 | threshold `0.174533` | 8/8 stage4 overtime | mean max/end `0.1872/0.1282 rad`，明显回弹 | stage3/4 base command 约 `0.0026/0.0060 m/s`；root 为 millimeter-level | stage4 1616/1616 frames 为 `arm_body8`-only single contact；bilateral/stability 为 0 |
| D1 | threshold `0.6` | 8/8 留在 stage3 | mean max/end `0.2570/0.2568 rad`，无回弹 | root 仍为 millimeter-level；stage3 min arm margin `<0.05` 占 `34.3%`、越出 soft limit 占 `4.49%`；8/8 limiting joint=`arm_j6` | 未进入 stage4，不能检验 stage4 retention |
| D2 | D0 + forced close `-1.0` | 8/8 stage4 overtime | 相对 D0，mean max/end 仅 `+0.0147/+0.0187 rad` | root motion 不变；TCP distance/slip 更差 | 全 trace bilateral ratio 与 D0 同为 `0.137%`；stability=0、stage4 bilateral=0；2 env 脱离 handle 后仍空 close |

D0 还有一个关键 reward-design signal：stage3 在几乎全是单侧接触时，当前 diagnostic reward decomposition 仍约为 `+0.336/step`。也就是说，policy 不需要形成 bilateral stable grasp，也能持续得到较高 stage3 shaping；仅强化同类 keep-close scale 可能继续放大错误 proxy。

## Findings by Evidence Strength

### Descriptive

D0 复现了用户关心的 precursor：gripper/handle 可持续接触，但 gripper 没有真正闭合，base 也没有随门运动。进入 stage4 后发生 reward/stage distribution switch，现有 frozen A policy 丢失 door progress。

### Diagnostic

D1 把 transition 延后后，door 不再回弹，并继续推到约 `0.257 rad`；与此同时 `arm_j6` 系统性逼近 soft limit。最合理的诊断是：当前 stage3 policy 依赖 arm 单独完成门运动，base locomotion 没有承担扩大 workspace 的职责。`0.6` 本身也不适合作为 v9 默认，因为它让 policy 在 transition 前先耗尽 arm workspace。

### Causal Intervention

D2 直接覆盖 gripper primitive，但 bilateral contact、stability 和 root motion不变。它只证明 forced-close command 在当前几何/contact 状态下不充分；不能据此声称经过重新训练的 continuous aperture 或 hold reward 永远无效。当前足以排除的是：把 forced-close、Kp、effort 或 keep-close scale 当作 v9 首轮主变量。

## Limitations

- D0/D1/D2 只有 8 env、单 seed、每 env 1 episode；它们是 bounded diagnosis，不是 success-rate estimate。
- 三组复用 frozen A policy。特别是 D0/D2 把在 threshold `0.6` 训练过的 policy 提前切到 stage4，包含明确的 out-of-training-distribution stage switch；这正适合诊断回弹，但不能替代 v9 retraining。
- 本轮快速 causal runs 是 no-render；视觉表述来自已有 A-on-A' reference，新的量化结论来自 scalar/trace。最终候选仍应补同 seed rendering。
- Soft-limit margin 是 joint-space proxy，不等于完整 Cartesian manipulability、torque reserve 或 self-collision margin。

## Recommended Base v9 2×2

四组共同 invariants：保留 B hold-handle bundle，即 stage3/4 的 handle orientation、target distance、grasp/contact-retention 语义持续 active，不走 A 的 stage4 release/default-arm route；gripper primitive、actuator gain/effort、stage2 completion 与 workspace-margin shaping 均不改。全部从同一个 A ckpt1000 做 policy-only initialization，并重置 optimizer、curriculum 与 snapshots，训练/eval budget 和 seeds 严格一致。

| Config | Stage3→4 threshold | Stage3 base | Purpose |
|---|---:|---|---|
| `base_v9_A` | `0.174533` | locked current | 早 transition control；复现 D0 路由但允许 retraining 适应 B hold bundle |
| `base_v9_B` | `0.25` | locked current | threshold main effect；尽量在 D1 的 workspace plateau 前 transition |
| `base_v9_C` | `0.174533` | unlocked | stage3 base main effect，检验早 transition 下 base mobility 是否改善 retention |
| `base_v9_D` | `0.25` | unlocked | 联合候选：延后 transition，同时让 base 随门移动 |

`unlocked` 的单变量定义应保持窄：移除 stage3 `penalty_not_standing_still=-15`，并移除 `_stage_3_reward_condition()` 中 `base physical command norm <= 0.1` 的 base-still gate；stage1/2 stillness gates 与 B hold reward terms 保持不变，不要同时改 arm pose 或 gripper dynamics。

解释方式：A↔B 与 C↔D 是 threshold effect；A↔C 与 B↔D 是 base-unlock effect；若 D 只在两者同时存在时改善，则存在 interaction。Primary metrics 应是 terminal hinge、rebound `max-end`、stage3/4 bilateral stability、stage progression/goal；guardrails 是 min arm margin、door-frame contact、base roll/pitch、TCP slip 与 root displacement。

## Explicit Non-Recommendations

- 不把 forced-close、gripper Kp/effort 或更大 keep-close scale 作为首轮 factor。
- 不直接采用 threshold `0.6`；D1 已显示它把 arm 推到 workspace boundary。
- 不直接把 `0.174533` 当最终答案；D0 显示 frozen policy 的 early stage switch 会回弹。
- 不恢复 stage4 arm default-pose reward；它与继续推门/握持目标冲突。
- 不把 workspace-margin shaping 混进首轮 2×2。若 base-unlock 后 `arm_j6` saturation 仍存在，再做第二轮 single-variable A/B。
- 不把 scratch B ckpt1000 的 stage2 acquisition failure 与本轮 stage3/4 hold ablation 混为同一因素。

## Next Steps

1. User 审批 2×2 定义后，再实施四个 config；code/config 修改和长训练仍需按审批门执行。
2. 先做 config diff、Hydra compose、default-off smoke，确认四组只含目标 factor。
3. 用相同 training budget 与 seeds 训练/评估四组；先依据 scalar/trace 排序，再给领先组补同 seed multi-camera rendering。
4. 若 base-unlock 有效，优先在 C/D 中按 retention、door progress 与 arm margin 选 winner；若无效，先检查 policy 是否实际输出/执行 base command，再决定 locomotion shaping。
5. 只有首轮 winner 仍持续出现 `arm_j6` margin `<0.05` 时，才进入 workspace-margin second-round ablation。
