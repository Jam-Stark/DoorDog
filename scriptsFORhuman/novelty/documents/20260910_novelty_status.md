# Novelty 路线与证据状态

日期：2026-09-10 HKT。整理：Codex；依据：Owner 要求集中维护讨论、产出和 memory。
状态：既有记录整理；本次证据等级 INSPECTED，未运行新实验或新增文献检索，不重新判定学术原创性。

## 当前选择

| 方向 | 既有定位 | 已有进展／限制 | 登记的后续入口 |
|---|---|---|---|
| N-01：恢复图＋失效边界采样 | 近期方法切口 | v27 三臂 pilot 的 Q_R 为 `UNRESOLVED`；R1 被读取器误停于644，缺少1500 endpoint。R2注入评估左右侧仅5/64、2/64次loss，重抓5/64、2/64，恢复后clean为0/64、1/64 | v29在新底座上重设计扰动强度与loss定义，再判断多seed确认；不能把当前pilot当作有效性确认 |
| N-02：交互历史／在线适应 | 后续科学主线 | 离线固定shadow estimator的window-weighted heldout friction/mass R²为0.15557/0.33127；actor未接入，不证明实时适应 | 冻结可部署观测；确认有信息量的交互域；同传感预算recurrent DR、history latent与oracle比较，含episode内变化 |
| N-06：arm–base coupling critic | 带条件暂缓 | 当前未建立足够的联动监督与因果证据 | 先确认arm-only失败层与可预测interaction residual，再考虑shadow与干预监督 |
| N-07b：camera-aware Teacher shaping | 待研究候选 | v28仅训练带bundle版本；Teacher关闭图像输入，尚无配对消融／蒸馏结论 | Teacher资格通过并有配对预算后，检验是否改善Student蒸馏 |

来源：[v27 恢复正式决策](../../v27/runtime_logs/v27_bilateral_hardening_20260905/wave_b_recovery_decision.json)、[恢复 readout](../../v27/a2_piper_base_v27_wave_b_r_step1500_readout_20260907.md)、[shadow estimator](../../v27/a2_piper_base_v27_shadow_estimator_readout_20260907.md)、[长期 TODO](../../a2_piper_longterm_TODO.md)。以上实验数字是对已有证据的引用，不是本次重新运行。

## 排期与取代关系

2026-09-05 的 Claude／Astra 文档曾将恢复确认与交互历史方法实验放在 v28。2026-09-09 的 v28 计划 D-01 已明确：新asset、默认姿态、相机约束同时变化，v28先做camera-aware re-baseline，N-01/N-02顺延v29。历史文档中的旧排期保留为历史，不是当前执行指令。

依据：[v28 plan](../../v28/a2_piper_base_v28_plan_20260909.md)、[deferred register X-05](../../v28/a2_piper_base_v28_deferred_register.md)。当前G0仍为 `PAUSED_BY_OWNER / G0_NOT_PASSED`，见 [G0 decision](../../v28/runtime_logs/v28_camera_aware_rebaseline_20260909/g0_decision.json)。

“Teacher先用较大碰撞包络，最终光学安装延后到Student阶段”仍在 [D028/D029](../../v28/a2_piper_base_v28_decision_log.md) 中标为PROPOSED。不能用大包络训练失败直接否定更小的最终硬件方案，也不能将这次讨论当成已批准的计划变更。

## 原讨论与范围

- [Claude Code 原对话](../conversations/20260905_claude_novelty_route.md)：提出三条想法、交叉参考要求及最终裁定。
- [Codex / Astra 原对话](../conversations/20260905_codex_astra_novelty_route.md)：独立路线判断及对应产出。
- [2026-09-10 回顾](../conversations/20260910_codex_novelty_status_and_provenance.md)：状态解释与出处查找。

推拉合一、重复打断、hold/swing选择仍在长期队列；按LEFT/RIGHT各自长独立策略树已在既有裁定中否决。原讨论没有证明任何方法取得论文级贡献。本文件不新增实验预算、验收门或实现任务。
