# 源码 / API / 输入覆盖索引

## 本次权威与限制

仓库 `Jam-Stark/DoorDog`，分支 `codex/v29-b02-b04-pro-20260918`，主题 `Prepare v29 B02 and B04 Pro decision handoff`，时间 `2026-09-18T17:14:54+08:00`。本索引不提供哈希清单。

源码事实以本次两个ZIP及manifest为准。远端成功抽查：S01关节/latch段、S04全文、S08 effort接口、S11静态读回JSON。大型主环境文件远端内容接口返回空，raw接口因大小/支持范围拒绝；其原始字节从source ZIP成功读取，已完成下表范围的定向审阅。不能说在线全文核验该大文件或整棵远端树完成。

`source_evidence/SELECTED_SOURCE_EXCERPTS.md`包含以下主要代码段并逐行标明原文件行号，便于不依赖联网核对。该节选不是补丁。原始完整文件仍由Owner的Worker输入包持有。

## 关键源码依据

| 编号 | 仓库相对路径与函数/行号 | 支撑内容 |
|---|---|---|
| S01 | `gr00t/rl/isaac_utils/playground/env_rand/door.py`，83–112、513–632 | DoorSpawnerCfg、self-collision/build_latch耦合、150°/45°原生限位、drive、cone、0–30mm prismatic、mimic |
| S02 | `gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py`，活跃selector链及1976–2044 | 旧物理域、build_latch=True、资产复制、三DOF init、ImplicitActuator |
| S03 | `gr00t/rl/config/ablation/wbmanip/base_v29_common.yaml`，30–113、174–185 | 30s、自然起点、质量80–120、摩擦off、0.6/45°、release1.2、creation活跃、staged和回位pose gate |
| S04 | `gr00t/rl/envs/door/a2_v26_3_creation.py`，1–78 | 活跃creation的固定45°截断和归一化、高水位增量合同 |
| S05 | `gr00t/rl/envs/door/door_open_a2_base.py`，类名`DoorPregrasp` | 大型主环境；下表列关键函数 |
| S06 | `gr00t/rl/envs/base_task/staged_task_base.py`，200–243、reset加载链593–697 | staged绕过普通callback、原始root/DOF恢复、buffer注册及验证hook |
| S07 | `gr00t/rl/envs/legged_base_task/legged_robot_base.py`，`_physics_step`1114起 | 每physics substep的force、simulate和post-hook时序 |
| S08 | `gr00t/rl/simulator/isaacsim/isaacsim.py`，2818–2840、2910起 | task state写入、effort而非position接口、scene写入/step/update |
| S09 | `gr00t/rl/config/obs/wbmanip/door_open_a2_base.yaml`，1–43、201–224及norm项 | Teacher的door_dof_pos/hand_force/privileged_door_info观察；禁止偷加答案 |
| S10 | `gr00t/rl/config/exp/wbmanip/door_open_a2_base_lstm.yaml`，51–85 | actor/critic现有LSTM配置，不需要新增网络 |
| S11 | `scriptsFORhuman/v29/pro_handoff/20260918_b02_b04/CURRENT_RESOLVED_CONFIG.yaml`与`STATIC_CONFIG_READOUT.json` | 200Hz/decimation4、randomize_door_init_state=false；新B01/B02/B04未实施、仅CONFIG_PARSE_ONLY |
| S12 | 同目录`OWNER_REQUEST.md`、`REVIEW_BRIEF.md`、`SOURCE_INDEX.md` | 本轮范围和首轮阅读顺序；优先于旧意见 |
| S13 | 同目录`LOCAL_CONTEXT_AND_OPTIONS.md`、v29 baseline plan/TODO/decision log | 本地候选及已有讨论；在独立初判后阅读，不作已批准最终选择 |
| S14 | reference包旧Pro `FULL_REVIEW.md`、`PRELIMINARY_JUDGMENTS.md`、`REAL_WORLD_PARAMETER_TABLES.csv`、`RELEASE_EVENT_SEMANTICS.json`、`SOURCES.md`及LOCAL_RECONCILIATION | 只读取/引用B02/B04相关意见及来源边界，不承接v28验收/相机前置 |
| S15 | reference包`baseline_no_center_smoke_20260917`的runtime_readout/process_receipt | 旧64-env/one-batch证据范围；无本次A/B或新最大角运行 |
| LOCAL API | `dependency_evidence/ISAACLAB_LIMIT_API.md`；extension0.54.4，原安装文件710–768 | 本机完整batched setter静态节选；缓存/default/soft与CPU传输副作用 |

### S05关键定位

| 行号 | 函数/位置 | 审阅重点 |
|---|---|---|
| 2089–2146 | `a2_grasp_gated_door_reward_components` | handle/0.6式旧尺度与near-closed mask |
| 2214–2299 | `a2_stage34_hold_income_mask`、`a2_update_stage4_release_and_root_latches` | gate是OR锁存，非物理释放 |
| 5846起 | `_get_a2_stage3_handle_hard_limit_position` | 区分hard-stop与解锁角 |
| 8247–8337 | creation init/register staged buffers | 新归一化与银行状态一致 |
| 9133–9139 | `door_dof_state_buf` | 原三列 |
| 12713起 | `_validate_loaded_staged_reset_sample` | 新配方/两DOF/FSM兼容性校验接入 |
| 14562–14618 | creation natural reset与update | 不在reset发creation，改固定尺度 |
| 15140–15162 | `_get_a2_door_income_hold_mask` | Stage4 gate后仍可能hold-and-drive |
| 15949–15983 | `_reward_penalty_a2_stage4_arm_default_pose_l1` | `~both_contact`不代表双指均断触 |
| 16929起、17027起 | 旧handle奖励及活跃creation/unlatch/hold函数 | 避免只改未活跃路径 |
| 17562–17582 | 回柄与push_door_hinge | 45°魔法尺度；正速度项未被release gate关闭 |
| 18341–18401 | hold收入mask与reward helper调用 | 正确联动实际执行的hold-and-drive路径 |
| 18455–18564 | handle-specific contact history/masks | 两指定向force与contacting/both/single区别 |
| 28462–28505 | hand_force、privileged_door_info、door_dof_pos | 实际观察来源；Teacher≠Student；两维顺序 |
| 29031–29100 | `reset_envs_idx` | 所有恢复写完后的统一同步位置 |
| 29299起、29444–29466 | reset callback与`_reset_door_states` | 普通路径、三DOF、旧15–100°初始化、正effort写入 |
| 29855–29906 | stage3→4、stage4→5、完成条件 | .25rad/K5，1.0472/.2/root_x，root_x>1.5不等于全身净空 |
| 30045–30081 | contact sensor建立 | handle只filter arm_body7/8；body/panel和arm/panel另有sensor |
| 30196起 | `_apply_force_in_physics_step` | 物理锁态更新hook；不放在仅control-rate的reward |

## 官方API/产品来源

| 编号 | 一手来源 | 本文只据此确认 |
|---|---|---|
| API01 | https://nvidia-omniverse.github.io/PhysX/physx/5.8.0/_api_build/structPxArticulationLimit.html | lower<upper；articulation转角单位rad；等值需另一locked motion机制 |
| API02 | https://openusd.org/dev/api/class_usd_physics_revolute_joint.html | USD转动关节上下限单位degree |
| API03 | https://isaac-sim.github.io/IsaacLab/v2.3.0/_modules/isaaclab/assets/articulation/articulation.html | 官方setter形状/副作用与目标传播供交叉核对；本机仍以LOCAL API为准 |
| API04 | https://docs.omniverse.nvidia.com/kit/docs/omni_usd_schema_physics/latest/physxschema/class_physx_schema_physx_mimic_joint_a_p_i.html | mimic公式、degree/length单位、双向冲量及动态改拓扑代价 |
| API05 | https://openusd.org/dev/api/class_usd_physics_drive_a_p_i.html | angular target、raw K/D单位和maxForce扭矩意义 |
| PRODUCT01 | https://www.pdqlocks.com/products/xgt-cylindrical-lock | 41°与特定65°操作转角；不等于θ_u或机械余程统计 |

访问日期：2026-09-18。一个较大的Omniverse schemas聚合页面读取超长失败，改用上述较小的官方类API页；没有把失败页面冒充已读全文。未读取产品PDF，不使用未打开的PDF图表。未用非一手网页证明技术事实。

## 非全文审阅与不使用的材料

五个顶层输入均成功取回，不存在未下载的ZIP分片。本次没有全文审阅机器人URDF、camera_rig、全部机器人配置、各基类所有无关函数，或旧Pro全部v28/相机章节；这些也没有被当作当前B02/B04运行证据。相机维持15°来自最新Owner范围，不由旧25°候选反推。旧runtime配置/receipt只用于时间与范围界定，不用于证明新物理机制可学。
