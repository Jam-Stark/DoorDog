# 输入阅读顺序与来源地图

本页是静态审阅导航。最终Worker目录中的BUNDLE_INDEX/MANIFEST说明每份材料所在ZIP及原来源。未打包本机绝对路径不等于Pro可访问；不要据此声称读过内容。

## 优先阅读

1. 当前Owner完整请求：`scriptsFORhuman/novelty/conversations/20260921_codex_n02_independent_review_request.md`；再读同目录两项裁定与四问，分清目标、planner设计及最新质疑。
2. `scriptsFORhuman/v29/a2_piper_v29_n02_plan.md`（v1.0候选），本目录REVIEW_BRIEF、BASELINE_CONTEXT。FINAL标签不是要求接受该架构。
3. 9/20原始研究问题、原N02路线与旧Pro的“先目标/行为/原LSTM，再判断小头”。按下方历史顺序比较，不把历史排期当方法合同。
4. 只为关键判断追踪下方current source/config；再核对baseline证据及原Pro模型/更正。源码文件保留完整内容，不只提供有利摘录。

## Current source：source_and_configs ZIP，repo相对路径

| 问题 | 路径/符号 |
|---|---|
| Teacher/Student信息 | `gr00t/rl/config/obs/wbmanip/door_open_a2_base.yaml`、`door_open_a2_base_dagger.yaml`；env的observation getters |
| 实际组合 | `config/ablation/wbmanip/base_v29_baseline.yaml`、`base_v29_common.yaml`、`config/robot/A2_Piper/a2_piper_v29.yaml`，路径均在gr00t/rl下；实际运行config另在证据ZIP |
| 当前LSTM/视觉记忆 | `gr00t/rl/trl/modules/actor_critic_modules_recurrent.py`、`vision_actor_critic_modules_recurrent.py`、`memory.py` |
| 高层与冻结腿 | `gr00t/rl/envs/base_task/a2_base.py`、`delta_action_base.py`；PPO/DAgger的A2_Base trainer组合路径 |
| B08 | 上述delta文件、`gr00t/rl/envs/door/a2_v26_4_canonicalization.py`、`DoorPregrasp.step`；不再存在Stage0在线target覆盖 |
| 控制可执行性 | `door_open_a2_base.py`的`a2_hold_absolute_target_to_cumulative_action`、hold oracle pose/IK/world-frame helpers。真值G/世界pose helper不能作为Student默认部署输入 |
| stage/reward/done | `gr00t/rl/envs/base_task/staged_task_base.py`；door env的`_stage_4_to_5_advance_condition`、`_stage_5_reward_condition`、`_stage_5_to_complete_condition`及hold/arm/gripper/handle reward |
| 真实接触与几何 | door env的handle-filtered及door body/arm/frame contact helpers；现有v22 clearance telemetry不是全身清离 |
| 门与B05域 | `gr00t/rl/isaac_utils/playground/env_rand/door_v29_parameters.py`、`handle_v29.py`、`door.py`、`gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py` |
| robot几何/模型 | `gr00t/rl/data/robots/a2_piper_v29_merged_20260917/` 的URDF/USD及依赖；相机/安装结构按实际asset，不假定旧trunk光学已对齐 |
| Student真实执行/监督 | `gr00t/rl/trl/trainer/distill_trainer_a2_base_api.py`及generic trainer/data utils；`config/exp/wbmanip/door_open_a2_base_dagger-lstm.yaml` |

## 历史路线：plots_and_evidence ZIP中的novelty/与prior_pro/

按日期读：

- 2026-09-05 Claude原讨论/裁定与Astra独立路线：交互历史状态估计、重抓循环的关系，不能预设架构。
- 2026-09-10 novelty status与2026-09-07 v27 shadow readout/脚本/结果：只支持有限离线信息，排除短episode的限制必须保留，不证明actor在线使用。
- 2026-09-14、09-17 v28 closure N01/N02：设计CONTINUE、实验DEFER，先传感/可辨识性和有效人口。
- 2026-09-18 Owner D023原话与regrasp讨论：强回弹后重抓把手属于N02，候选未实施，不要求调用N01。
- 2026-09-20 Owner N02研究要求与brief：能力缺口→目标/控制用途→信息/网络，允许原LSTM成为有效方法。
- 2026-09-20 Pro全文、目标/可观测性、闭环、Teacher–Student、模型报告及结果；同时读OWNER_BRIEF、LOCAL_RECONCILIATION。原Pro建议与CPU结果各有范围，不成为当前方法合同。
- 2026-09-20至09-21本planner设计、裁定、最终架构与Owner最新concern：审查哪里是必要具体化、哪里是缺证据的增加。

归档文档内旧“执行prompt/模型计算要求/上传方式”等只是历史材料，不能取代本轮REVIEW_BRIEF与最终PRO_REVIEW_PROMPT。

## Baseline证据：logs_and_metrics ZIP

`baseline/6000/`、`baseline/7000/`保存各自实际config、metrics和per-env记录；`baseline/acceptance/`保存既有接受/里程碑与B05接触记录，`baseline/B08/`保存公共修复说明及CPU整合记录。原6000/7000均属于未含B08的冻结C002；B08不能借这些结果宣布收益。

先从BASELINE_CONTEXT读取证据结论，再按需看原JSON；不要为流程完整重新审阅所有旧source或数百个配置。
