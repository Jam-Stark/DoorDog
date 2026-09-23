# v28 审计材料：planner finalize 入口

落盘：2026-09-12 15:45 HKT。修改：本地 Codex；依据：Owner 要求保存 Pro 审计和本地更新审计，交 v28 planner 对照 finalize。

当前承接（2026-09-12 17:18 HKT；修改：-codex planner；依据：-owner）：Owner 已同意 planner 裁决并授权方案/决策记录更新。M1–M5 已按裁决落实到活动文档；候选选择与 A_S284 资格作为独立新决定 V28-D039/D040 记录。当前合同见 [v28 plan](../../../v28/a2_piper_base_v28_plan_20260909.md)，逐项取舍、替代关系与实现差距见 [决策日志 D038–D040](../../../v28/a2_piper_base_v28_decision_log.md)。采用资格导向的预定主/备候选，取代本地审计建议的默认最早 reach；reducer/调度代码待同步。本次未执行训练、评估或 Git 操作。

FULL_REVIEW、LOCAL_AUDIT_UPDATE、解析 prompt 和原 planner 自省均保留原文及原时点；其中“草案未应用/未决”是归档时状态，不覆盖上述新决定。

## 阅读材料

| 材料 | 位置 | 性质 |
|---|---|---|
| Pro 完整审计 | [FULL_REVIEW.md](FULL_REVIEW.md) | 附件原文，完整保留固定初判 A、三方交叉 B、最终建议 C、证据边界 D；未改写 |
| 本地更新审计 | [LOCAL_AUDIT_UPDATE.md](LOCAL_AUDIT_UPDATE.md) | Pro 回传后的只读核对、M1–M5 最小草案，以及“固定候选/可用 Teacher”目标澄清；不是 Pro 前的独立初判 |
| v28 planner 自省 | [原位自省文档](../../../v28/a2_piper_base_v28_planner_self_review_20260911.md) | 2026-09-11 材料；与后续 G0 证据按时间区分，不因归档而更新其事实时点 |
| Pro 附带的本地解析 prompt | [LOCAL_WORKER_PARSE_PROMPT.md](LOCAL_WORKER_PARSE_PROMPT.md) | 附件原文，保留来源；其中的建议不自动增加执行授权 |

来源附件：`/home/baoquanc/.codex/attachments/461f1821-73d6-44ce-b44b-a8bc9b0902e9/pro_delivery__full_review (1).zip`。按 Owner 要求，仓库只保留已解压文档，不另存重复 ZIP。

## 版本与证据时点

- 仓库：`Jam-Stark/DoorDog`。
- Pro 审计分支：`codex/v28-pro-audit-g0-complete-20260912`。
- Pro 审计 commit：`84358588e2da12a9fae5748cd9da39ac2d9f5a6c`。
- G0 worker 直接父节点：`8811c484729b1e9be017c30dcf46d922d1ad5f52`。
- 本次文档落盘时所在分支仍为 `A2_Piper`，HEAD 仍为上述 G0 commit。
- 本轮 Pro 使用的 Drive 目录 ID：`1bmymz2ijOesd_Yr0cIHOr4iwcEMl9nUJ`。旧目录 `1gKH6DA3KUf6rYGMZY2bV1bzBHHy2j30-` 仅是历史交付，不混用其 STOP 状态或 prompt。
- 运行现状从 [G0 acceptance](../../../v28/a2_piper_base_v28_g0_acceptance_20260912.json)、[runtime decision](../../../v28/runtime_logs/v28_camera_aware_rebaseline_20260909/g0_decision.json) 和新的实际记录读取。审计时的“G1 未启动”不是永久现状。

## 2026-09-12 15:45 交给 planner 的问题（现已由 D038–D040 承接）

1. 逐项处理本地更新审计中的 M1–M5：接受、修改后接受、延期或不采纳，并指明对应 plan/文档位置。
2. 明确是否继续保持现行“固定最早 reach 候选、接受本轮可能没有合格 Teacher”的目标。它是当前合同及本地建议，不应将其改写成“已证明无法稳定产出 Teacher”。
3. 如希望提高获得合格 Teacher 的机会，选择/替补合同应在查看 v28 结果前另行明确；修终点标签不能顺便改候选身份、门值或 Wave B 路由。
4. A_S284 等备用臂的资格在启动/查看结果前明确。无新决定时保持单列报告、原三 seed 分母与固定 staged reset。
5. 保留原 FAIL/D36/D37，保持 X24 与晚阶段事件的证据边界。X25 已有触发条件，不重复添加；不因未完成随机校准、未附完整 trace 或后移 G2 增加当前生产 STOP。

15:45 归档时仅保存审计材料和索引，M1–M5 尚未应用；该次没有修改 v28 plan、源码、配置、门值或选择规则，没有训练/评估、Teacher/G7 更新、硬件操作、commit/push 或 Drive 上传。17:18 的 finalize 范围与结果见本页当前承接及决策日志，不回写 Pro 或本地审计原文。
