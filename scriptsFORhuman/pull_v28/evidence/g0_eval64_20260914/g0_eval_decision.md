# Pull v28 G0 STEP5 evaluator wiring

Status: `G0_EVAL_WIRING_PASS`.

本结果仅说明双侧 natural64 与 telemetry 接线；不判 opening 或原三 seed 终点。

| Side | Integrity | K5 | D | E4 | E5 | E6 | E7 | Tower >5N | Camera | Margin |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| left | VALID | 0/64 | 0/64 | 0/64 | 0/64 | 0/64 | 0/64 | 0/64 | CAMERA_PARTIAL | NOT_OBSERVED |
| right | VALID | 0/64 | 0/64 | 0/64 | 0/64 | 0/64 | 0/64 | 0/64 | CAMERA_PARTIAL | NOT_OBSERVED |

**left**：natural births=64，原trace读取=1遍；camera字段=26，样本={'all': 16606, 'stage0_2': 16606, 'stage5': 0, 'stage2_4': 0, 'stage0_5': 14542, 'crossing_episodes': 0}。

Ready=0/64，4A/4B={'handoff_reached': 0, 'tangent_share_ge_0_6': 0, 'handle_crossed': 0}；E5后样本=0，margin≥.07份额=None。

Bundle/runtime checkpoint 字段保存在 decision 的 `left.bundle_runtime_config`；camera完整字段与null保存在 `left.camera`。

**right**：natural births=64，原trace读取=1遍；camera字段=26，样本={'all': 16808, 'stage0_2': 16808, 'stage5': 0, 'stage2_4': 0, 'stage0_5': 14029, 'crossing_episodes': 0}。

Ready=0/64，4A/4B={'handoff_reached': 0, 'tangent_share_ge_0_6': 0, 'handle_crossed': 0}；E5后样本=0，margin≥.07份额=None。

Bundle/runtime checkpoint 字段保存在 decision 的 `right.bundle_runtime_config`；camera完整字段与null保存在 `right.camera`。

相机投影/min-Z是几何代理；E6 yaw沿pull事件，缺少晚阶段样本不证明释放回位或opening能力。
