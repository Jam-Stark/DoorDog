# DoorDog A2+PiPER base_v24 P2 最终裁决（2026-08-17）

## 结论

P2 最终 typed result 为：

`V24_E1_DENOMINATOR_INSUFFICIENT`

该结果为已注册终点：`terminal=true`、`P3_ADMITTED=false`、`owner_decision_required=false`。因此 P3 历史零样本扫描、Wave 1 与全部后续条件工作均不执行。本次没有进入 Phase 3，故不触发唯一真正的 Owner decision point `V24_FRICTION_AXIS_NONDISCRIMINATIVE`。

这份裁决是 additive 新文件。历史 R1、D-v2 与 P2 r1–r8 receipts 均保持不变。

## 准入与运行

- D-v2 已以 `V24_FRICTION_MODEL_VALID_BEHAVIORAL` 准入 P2。
- P2 parameter-range freeze 已执行；physical GPU0 smoke exit `0`（`175.36 s`），calibration exit `0`（`2860.99 s`）。
- Calibration 共 288 rows：6 个 arm caps × 3 个 friction profiles × 16 个 paired scenarios。
- 后续 freeze → heldout → adjudicate → QA 为 CPU-only，四阶段均 exit `0`，耗时分别为 `0.11 s`、`0.10 s`、`0.11 s`、`0.09 s`。
- 产品与 canonical evidence commit 为 `f0a3a44`。

## P2 裁决事实

| 项目 | 结果 |
|---|---|
| foot source | `AVAILABLE` 288/288 |
| stable grasp | 0/288 |
| valid model/capacity rows | 42/288 |
| finite tau/lambda | 42/42 valid rows |
| valid loaded-foot slip windows | 0 |
| E0 anchor / E1 denominator | 0 / 0 |
| command path binding | `true` |
| tau_hi / tau_boundary / tau_rescue | null / null / null |
| contingency | not triggered |
| heldout | zero-row `NOT_ADMITTED_BY_P2_TERMINAL` |

E1 所需 denominator 为 0，无法达到冻结的最小值 8。因此 ladder/threshold lifecycle 进入注册的 denominator terminal；不生成 `foot_slip_q99_m_s` 或 `tau_hi_nm`，也不伪造 heldout 样本。

正常 `>=8` / Q99 / full-heldout E-region 路径没有执行，不能声明该路径 runtime PASS。这里的 runtime closure 仅覆盖实际发生的 GPU0 smoke/calibration 与 CPU terminal lifecycle。

## Authority

- Door friction/model torque authority：`MODELED_FROM_PARAMS`。
- `solver_applied=false`；不声称 solver-applied friction torque。
- Capacity/lambda 保持 estimate authority；不将 command、actuator 或 modeled torque 改称 solver 内部量。

## Canonical evidence

- `logs_eval/base_v24/p2/force_boundary/r10/V24_P2_PARAMETER_RANGE_FREEZE.json`
- `logs_eval/base_v24/p2/force_boundary/r10/smoke/P2_SMOKE_RECEIPT.json`
- `logs_eval/base_v24/p2/force_boundary/r10/calibration/P2_CALIBRATION_RECEIPT.json`
- `logs_eval/base_v24/p2/force_boundary/r10/calibration/P2_CALIBRATION_ROWS.jsonl`
- `logs_eval/base_v24/p2/force_boundary/r10/V24_P2_LADDER_FREEZE.json`
- `logs_eval/base_v24/p2/force_boundary/r10/V24_P2_CERTIFICATE_THRESHOLD_FREEZE.json`
- `logs_eval/base_v24/p2/force_boundary/r10/heldout/P2_HELDOUT_RECEIPT.json`
- `logs_eval/base_v24/p2/force_boundary/r10/V24_P2_E_REGION_CERTIFICATE.json`
- `logs_eval/base_v24/p2/force_boundary/r10/V24_P2_FINAL_ADJUDICATION.json`
- `logs_eval/base_v24/p2/force_boundary/r10/QA_SEMANTIC_VALIDATION.json`

## 停止边界

P3 未准入；没有运行历史零样本扫描、Wave 1、Route A/B、RQ3/RQ4、shadow critic 或 Wave 2。无训练、因果价值或 release PASS 声明；无 push。
