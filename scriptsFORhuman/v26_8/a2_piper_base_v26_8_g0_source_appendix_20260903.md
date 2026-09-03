# base_v26-8 G0 source appendix

日期：2026-09-03 HKT  
状态：`INSPECTED_PENDING_G0_EXECUTION`

本附录满足冻结 plan §6.1 的 source-consumer 与加载路径核查要求；不修改冻结判据。

## W 阈值的实际消费者

`env.config.a2_stage3_unlatch_near_closed_hinge_threshold` 在当前 source 中有以下消费路径：

1. `a2_grasp_gated_door_reward_components` 用 `hinge_pos < threshold` 生成 `unlatch_hold`，并由
   `_reward_a2_stage3_unlatch_hold` 实际支付。因此 W 的主要语义确实是把 Stage3 hold 收入延续到 0.25。
2. v22 failure-routing latch 用 `hinge_pos >= threshold` 定义 `unlatched`。W 同时改变这一诊断/路由
   latch 的分界；该读数必须作为伴随影响报告，不能写成单一 reward 消费者。
3. v26-2 telemetry 读取并校验阈值只能为 0.1 或 0.25；其历史 `unlatch_band` 仍固定为
   `0.1 < hinge < 0.25`。该 band 是报告项，不随 W 改写。
4. Stage3→4 advance 继续消费独立的 `a2_stage3_to4_door_hinge_threshold=0.25`。W 不修改 stage
   判据，也不把 near-closed 阈值当成入场判据。

## Source checkpoint 与 reward 名单

- `SRC_S1` step3000 存在，SHA-256 为
  `a683257213aaba82b583924d841235f772182f53113e513e16c8d27bcb394df1`。
- `SRC_S2` step3000 存在，SHA-256 为
  `0b2f739f020b056adb2fb47105fdb5bc00d1d1189ef331d42332b3e0740e54ec`。
- 冻结的 16 个 `reward_penalty_reward_names` 在两个 source 的 resolved `reward_scales` 中全部非零，
  且两个 source 的数值逐项一致。

## 加载与 eval 合同的 source reconciliation

当前普通 legacy actor 的 `policy_only_load_actor_rms=true` 路径使用
`model.policy.load_state_dict(actor_state, strict=True)`，会严格加载 actor MLP/std/LSTM 与 actor RMS。
现有 v26-5 官方 train load-receipt writer 随后无条件要求 residual-only optimizer partition，因此不能
用于本阶段的 legacy actor；这是冻结 plan 对现行 source 的一处假设偏差。v26-8 不修改 trainer，也不切换
loader 分支，而由 stream wrapper 只在实际 strict-load 成功行出现后写
`v26_8_policy_load_receipt.json`。resolved config、checkpoint digest 与该 runtime receipt 三者共同裁定。

Eval 入口从 checkpoint-adjacent `config.yaml` 合成训练配置，再应用 CLI override。v26-8 eval 固定
`checkpoint_load_mode=full`、`enable_staged_reset=false`、first-episode exact64，并显式应用
`++rewards.reward_penalty_curriculum=false`；因此 K/C/W 的 eval reward telemetry 可比。

证据等级：`INSPECTED`。最终 `STATIC_PASS`、`TEST_PASS` 与 `RUNTIME_PASS` 由 G0/G1 artifact 单独给出。
