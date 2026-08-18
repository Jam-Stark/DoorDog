# READY GRPO Student — r6 归因闭环与行为交付报告

Completed: 2026-08-19 03:0x HKT
Branch: `sim2sim/a2-mujoco-shadow-evaluator-20260817`

## 首屏 — 用户验收入口

**视频（视觉判断归用户，agent 仅数据级验证；全部 25fps mp4）**

| 内容 | 路径 |
|---|---|
| Isaac 参考视频（main+handle_top ×8集,真实策略行为） | `artifacts/e5/r6_isaac_self_eval/c1_nominal/isaac_reference_videos/` |
| MuJoCo campaign 回放 p00/p01/p07（存档 trace 逐行回放） | `artifacts/e5/r6_behavior_deliverables/{p00_baseline,p01_mass80,p07_drive_k10_cap25}_{overview,policy_tiled}.mp4` |
| MuJoCo staging-band 探针（同 seed 重跑，1000/1000 逐行全同） | `artifacts/e5/r6_behavior_deliverables/staging_band_probe/staging_band_probe_{overview,policy_tiled}.mp4` |

**关键 receipt**

| 结论 | 路径 |
|---|---|
| 关节体征 `JOINT_KINEMATICS_SANE` | `artifacts/e5/r6_behavior_deliverables/joint_kinematics_vitals.json` |
| 非视觉 obs 面 `NONVISUAL_OBS_SURFACE_CLOSED` | `artifacts/e5/r6_obs_forensics/obs_surface_receipt.json` |
| 跨引擎命令对拍（本轮核心） | `artifacts/e5/r6_isaac_self_eval/c3_cross_backend_commands.json` |
| Isaac 自评估可行性 | `artifacts/e5/r6_isaac_self_eval/c0_feasibility_receipt.json` |
| D1 帧替换 / D2 外观扫掠 | `artifacts/e5/r6_visual_probes/d1_frame_replacement/d1_receipt.json`、`{appearance_sweep_receipt,brightness_ladder_receipt}.json` |

## 三行结论

1. **行为体征健康**：臂 stage0 保持（偏差≤0.047 rad、|qvel|≤1.01 rad/s）、腿在步态包络、qacc 1947（对照 r3 事故 2.7e6）、全有限——"关节乱摆"已排除；实测/命令速度比 ≈0.27（命令贴帽≠物理疾走）。
2. **归因闭环**："贴帽疾走不停"是**策略属性而非 MuJoCo 伪影**——该 Student 在其自身 Isaac 环境同样 ~99.6% 贴帽、0/1000 真实 base-still（4 个边界零已识别为 reset 伪影并撤回）；视觉通道对命令**幅度**有真实系统性效应（Isaac 帧替换 −52%、亮度阶梯单调 2.2×），但单视觉不足以翻转到 base-still。
3. **E5 状态**：C2 精确配对按契约 typed 降级（`ATTEMPTED_SCOPED_DOWN`），formal paired 判定仍等配对生产器；本轮已交付非配对但对拍一致的行为证据链。

## 逐 Phase typed 结论

| Phase | typed 结论 | 证据 |
|---|---|---|
| 0 预检 | PASS（8×A6000,授权 0-3,EGL/isaacsim/视频链路 OK） | `r6_preflight/preflight_receipt.json` |
| A 行为可视化 | JOINT_KINEMATICS_SANE + 8 mp4 容器全有效；视觉判断 PENDING_USER_VISUAL_REVIEW | `r6_behavior_deliverables/phase_a_receipt.json` |
| B obs 取证 | NONVISUAL_OBS_SURFACE_CLOSED（t=0 锚全中 diff=0.0；坐标惯例锚 file:line；第三次逐行对拍全同） | `r6_obs_forensics/obs_surface_receipt.json` |
| C0 可行性 | ISAAC_SELF_EVAL_FEASIBLE（冻结 a1972552 scratch 克隆；co-tenant SIGKILL 事件 typed 并在重试中越过） | `r6_isaac_self_eval/c0_feasibility_receipt.json` |
| C1 nominal | 150 集聚合（0 goal、2/150 stage1、150 stage_overtime@5s）+ 16 集插桩 dump + 24 参考视频 | `r6_isaac_self_eval/c1_nominal/` |
| C2 配对 | ATTEMPTED_SCOPED_DOWN（reset_from_dataset 为随机运动重置；钉死 reset+门参+seed+200Hz schema 生产器为数小时级子项目） | 本报告 |
| C3 对拍 | COMMAND_PROFILE_CONSISTENT_CAP_PINNED_IN_BOTH_BACKENDS | `r6_isaac_self_eval/c3_cross_backend_commands.json` |
| D1 帧替换 | SINGLE_VISUAL_CHANNEL_NOT_SUFFICIENT_NO_CONVERGENCE_UNDER_ISAAC_FRAMES（min norm 0.495→0.235,仍 0 base-still；live≡frozen delta=0.0） | `r6_visual_probes/d1_frame_replacement/d1_receipt.json` |
| D2 外观扫掠 | 27+8 变体：min_norm 随亮度单调 0.45→0.21，无一触发 base-still（EXPLORATORY） | `r6_visual_probes/{appearance_sweep_receipt,brightness_ladder_receipt}.json` |
| E depth 支线 | NOT_STARTED（A-D 收口后余量用于 F 强制收口；按铁序让位） | — |

## 归因证据链（"贴帽疾走不停"缺陷）

- **策略层主导**：Isaac 自身环境 0/1000 真实 base-still、99.6% 贴帽（16 集插桩）；MuJoCo 0/9000+。两侧一致 → 非域伪影。
- **视觉层真实但非充分**：真 Isaac 帧（crude 三元组，已披露）替换 → min norm −52%；亮度阶梯单调（0.45→0.21）；两者幅度一致（~2×）→ 命令幅度对外观敏感，收敛翻转不受单一视觉通道驱动。
- **proprio 层排除**：81D 全锚核验 + 全程范围合理（Phase B）。
- **罕见例外**：Isaac 聚合 2/150 集进 stage1 → 非零概率事件，MuJoCo 8 集样本未命中，与"稀有事件+小样本"一致。

## 给 Owner 的待决清单

1. **formal E5 配对生产器是否立项**：C2 已探明路径（target_states 重置 + rand_* 门参钉死 + 200Hz schema 发射器），预计数小时级工程；本轮按预算降级，需要 owner 决定投入。
2. **91.2%/512 出处校准**：本 eval 协议（5s stage_overtime）下 goal_reached=0；与训练时 91.2% 协议不同源，两数字不可互替——owner 决定是否需要复跑训练时协议对齐。
3. **视觉归因正式化**：D1/D2 的 ~2× 命令幅度效应建议进入 DR（domain randomization）外观增广考虑（Isaac 侧亮色/白门变体），属训练侧决策。
4. **scratch 清理**：`/home/baoquanc/workspace/sim2sim_scratch_r6/`（distill_frozen 克隆含声明过的 env-gated 插桩 + c0/c1_out）可整体删除；co-tenant DepthADD（GPU5/6）非本任务资产,未触碰。
5. **视频目检**：8 个 Isaac 参考 + 8 个 MuJoCo 回放/探针 mp4 待用户视觉判断（本 agent 无视觉）。

## 纪律自检

- 主仓/蒸馏 ws 只读验证（find -newer 空）；写入仅 sim2sim 仓 + scratch + /tmp。
- r4/r5 artifacts 字节未动；r6 全部新增。
- typed 缺失未填零；D1 边界伪影主动撤回；失败均有原始报错落盘。
- 不 push；每 phase 收口即 commit;反空转(视频两轮空跑后在 30min 规则内以 render_results 开关收口)。
- GPU 纪律：仅 GPU0（Isaac/EGL）；GPU5/6 co-tenant 全程未触碰;一次 137 事件 typed 记录。
