# base_v27 fixed shadow estimator

固定64-control-step window/stride、ridge=1、split_seed=270202；按配对episode group切分，未调参或重跑。

训练窗口3397，heldout窗口1171；heldout episodes=279，因不足完整窗口排除51集。

| Metric | Friction R² | Friction RMSE (N·m) | Mass R² | Mass RMSE (kg) |
|---|---:|---:|---:|---:|
| Window-weighted | 0.15557 | 1.91948 | 0.33127 | 19.15647 |
| Train mean baseline | -0.00051 | 2.08936 | -0.00163 | 23.44461 |
| Equal-episode | 0.21428 | 1.84151 | 0.43365 | 17.41115 |

结果高于均值基线，但解释方差有限，仅支持已观测模拟数据的离线可辨识性。未改变actor，未证明实时适应、部署传感器合同或hardware能力。

原始结果：`logs_eval/base_v27/v27_bilateral_hardening_20260905/shadow_estimator/endpoint_result.json`。
执行证据：`runtime_logs/v27_bilateral_hardening_20260905/shadow_estimator_cpu_evidence.json`。执行器未返回精确退出码，保留null；观测运行时间80–110秒。
