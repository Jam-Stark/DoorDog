# TODO

- 2026-08-05 09:35 HKT - 监控 Wave 1（G1/G2）2500 batch 训练至自然退出；liveness 判据为 checkpoint 持续推进、metrics 有限、GPU 进程存活、无 evidence error（overrun 本身不算失败）。
- 2026-08-05 09:35 HKT - Wave 1 结束后按 §14 跑 Route A（每 cell step250..2500 共 10 个 checkpoint，canonical16）。
- 2026-08-05 09:35 HKT - P0-B（frozen posture 因果干预，提供 §7.6.6 独立标签）与 P0-F（clearance replay）尚未执行；在它们完成前 `posture_need` precision 保持 report-only。
- 2026-08-05 09:35 HKT - P0-E（trunk/front-thigh 安全接触探针）未执行；Wave 3 body assist 在其完成前不得开启。
- 2026-08-05 09:35 HKT - §6.2 fixed-torque probe 判定为 `FIXED_TORQUE_PROBE_INCONCLUSIVE_BELOW_RESOLUTION`；H3/H4 未实现。Wave 2 materialize 前需在 Window A 内以更高 torque ladder 或改用 velocity-response 探针重做。
- 2026-08-05 09:35 HKT - Wave 2 使用 H0-H4 mixture 前，需验证冻结 range 的 marginal 独立采样确实复现所属 response class（当前三个 bucket 的 damping/stiffness 区间互相重叠）。

# 待用户确认

- 2026-08-05 09:35 HKT - posture gates 以 `POSTURE_GATES_REPORT_ONLY` waiver 放行（§7.6.4/§7.6.5 授权路径）。若用户希望改为先修复 `posture_need` 过激再开训，需要停掉 Wave 1 并重新标定 §7.3 workspace 判据。
- 2026-08-05 09:35 HKT - `penalty_a2_v22_excess_posture` 与 `a2_v22_posture_feasibility` 的 income share 低于 §7.5 guidance band，已记录原因而未强行拉大 scale。
