# CAMPAIGN R6 PROGRESS

增量写;任何时刻中断以此文件为最新可读状态。

## 用户补充契约(2026-08-19 00:5x HKT, Phase A 生效)

执行 agent 无视觉功能:mp4 产出后由用户事后做视觉判断(非阻塞,agent 继续后续 phase);agent 的验收面 = 数据级验证——回放/重跑与已存 trace 的逐行确定性对拍、视频容器有效性(帧数/时长/fps)、receipt 数值。视觉结论一律标注 PENDING_USER_VISUAL_REVIEW。

## 2026-08-19 01:2x HKT — Phase A 完成(PASS, 视觉判断待用户)

- 交付: 3 case 回放 mp4(p00/p01/p07, 各 overview+tiled 20s@25fps) + staging probe 带录制同 seed 重跑 mp4。
- 忠实性: probe 重跑 vs 已存 trace 逐行确定性对拍 1000/1000 全同(max diff 0.0);case 视频为存档 trace 逐行状态回放,无 policy 重跑。
- 关节体征: **JOINT_KINEMATICS_SANE**(臂 |qvel| max 1.01<2.0;腿 11.29 在包络;qacc 1947<1e5;全有限)。臂偏差 max ≤0.047 rad。实测/命令速度比≈0.27。
- Receipt: `artifacts/e5/r6_behavior_deliverables/phase_a_receipt.json`(视频路径首屏)。视觉结论 PENDING_USER_VISUAL_REVIEW。
- 下一步: Phase B(r5-L1 obs 取证)。

## 2026-08-19 00:54 HKT — Phase 0 预检 PASS

- GPU: 8×A6000 全空闲(测量时),授权 0-3,standing 排除 5/6,`CUDA_VISIBLE_DEVICES=0` 圈定。receipt: `artifacts/e5/r6_preflight/preflight_receipt.json`
- EGL 1 帧冒烟 PASS;isaacsim import PASS;视频工具链(imageio-ffmpeg v7.0.2 + cv2) PASS。
- 下一步: Phase A 行为可视化(campaign p00/p01/p07 从已存 trace 回放渲染;staging probe 需同 seed 41001 带录制重跑——probe trace 未存全量状态,重跑已在 receipt 声明)。

## 2026-08-19 01:4x HKT — Phase B 完成(NONVISUAL_OBS_SURFACE_CLOSED)

- 同 seed(41001)同循环 llvmpipe 重跑,逐步 dump 构造层 81D actor_obs(running_mean_std 之前)→ `artifacts/e5/r6_obs_forensics/actor_obs_surface.npz`。
- t=0 锚全中:projected_gravity=解析值(diff 0.0);ang_vel×0.5=0;dof_vel×0.05=0;dof_pos−default=keyframe−default(恰为零);四段 echo 全零。
- 坐标惯例已锚:生产 legged_robot_base.py:171/199(body-frame)≡ MuJoCo 取法;缩放 0.5/0.05/1.0 于构造层(obs yaml:137-141)。
- 全程范围有限合理;第三次逐行确定性对拍 1000/1000 全同。receipt: `r6_obs_forensics/obs_surface_receipt.json`。
- 无 proprio 异常 → D 不让位,C 优先。下一步: C0(蒸馏分支冻结代码 a1972552 scratch 克隆 + eval_agent_trl 1env 冒烟,硬帽 1h)。

## 2026-08-19 01:5x HKT — C0 可行性 PASS(ISAAC_SELF_EVAL_FEASIBLE)

- 冻结代码: 蒸馏 ws 克隆→scratch 检出 a1972552;checkpoint 只读加载;全部输出落 scratch。ws find -newer 验证零写入。
- 三次 config 级失败已修(+num_envs/PYTHONPATH/num_mini_batches 整除);一次 SIGKILL(137) 发生在 co-tenant DepthADD(GPU5/6, 01:36 启动)拉起前窗口,typed CO_TENANT_LAUNCH_WINDOW_SUSPECTED;GPU0 重试存活。
- attempt1 保持运行作 nominal 聚合参照(200 episodes)。receipt: `artifacts/e5/r6_isaac_self_eval/c0_feasibility_receipt.json`。
- scratch 待清理登记: /home/baoquanc/workspace/sim2sim_scratch_r6/{distill_frozen,c0_out}。

## 2026-08-19 02:5x HKT — Phase C 主体完成 + Phase D2 完成

- **C0/C1(聚合+插桩)**: Isaac 自评估 150 集(0 goal, 2/150 stage1, 全 stage_overtime@5s) + 16 集插桩 dump(step_actions/_homie_commands clipped+unclipped/81D obs/root/stage)。
- **C3 对拍(钱结果)**: Isaac 命令 p50 0.526/贴帽 99.6%/真实 base-still 0/1000(4 个边界零已识别为 reset 伪影并撤回) ↔ MuJoCo min 0.38-0.50/贴帽 ~95%/0 base-still。**贴帽疾走=策略属性,两侧一致,MuJoCo shadow 忠实**。receipt: `r6_isaac_self_eval/c3_cross_backend_commands.json`。
- **C2**: typed `ATTEMPTED_SCOPED_DOWN`(reset_from_dataset 为随机运动重置,配对钉死+200Hz schema 生产器为数小时级子项目,非本轮预算;C1 插桩已回答本轮问题)。
- **D2 外观扫掠**: 27 变体+8 阶梯深化, min_norm 随 panel 亮度单调降(0.45→0.21), 无一触发 base-still → 外观有真实系统性效应(~2.2x)但单外观不充分。receipt: `r6_visual_probes/appearance_sweep_receipt.json` + `brightness_ladder_receipt.json`。
- **C1c 视频补跑中**(render_results 总开关);D1 待 C1c 帧提取后跑。
- 插桩声明: scratch 克隆 env-gated dump 补丁(只 scratch,默认行为零变化)。

## 2026-08-19 03:0x HKT — Phase F 收口

- D1 收口(SINGLE_VISUAL_CHANNEL_NOT_SUFFICIENT; Isaac帧 -52% min norm, live≡frozen) + C1c 24 个 Isaac 参考 mp4。
- CAMPAIGN_R6_REPORT.md 落盘(首屏视频/receipt 路径+三行结论+owner 待决清单);ledger merge commit 更正为 2ab9f7f;memory r6 条目落盘。
- 最终: 全部 commit + merge A2_Piper + behind=0 证明。E 支线 NOT_STARTED(铁序让位)。

## 2026-08-20 01:2x HKT — 重大更正(用户挑战成立)

- **训练协议复现: success_rate 0.96875 (31/32), episode 长度 615 步** —— Student 在 IsaacLab 训练协议下 ~92-97% 完整开门,与 GRPO metrics.jsonl (0.90-0.98/batch) 一致。
- **我此前的 Isaac eval 参照系双重错误**: (1) eval_agent_trl + base_eval 默认跑在 250 步 stage_overtime 契约(训练为 ~615 步);(2) policy 视觉输入在我的 eval 路径下逐字节冻结(12 个 policy-view 视频全同)——0/150 是 harness 伪影,不是策略行为。
- **作废声明**: C3 `COMMAND_PROFILE_CONSISTENT_CAP_PINNED_IN_BOTH_BACKENDS` 撤回;Isaac eval 视频(白场)typed INVALID;D1"Isaac 帧"实为近白噪声帧。
- **真实的 MuJoCo gap 重新成立且很大**: Isaac 92%+ vs MuJoCo 0/8——r7 目标( MuJoCo 自主到 stage5)是真问题,r6 归因方向(视觉外观效应)保留但基准重置。

## 2026-08-20 02:5x HKT — r7 关键突破与路线修正

- **真参照剖面(训练协议 rollout dump, 21440 步)**: 63 集中 31 集 stage5、40 集有真 base-still;成功集 stage 链 0→1@44 →2@89 →3@168 →4@274 →5@436(~9s 全链);命令 norm 平滑衰减,min 0.017-0.026。存于 scratch grpo_repro_dump3(时代锚 a1972552)。
- **决定性切分实验**: MuJoCo 物理 + **Isaac 视觉逐步回放** → 策略在 600 步内产出 base-still(min 0.0711, 2 步 ≤0.1)——**视觉时间序列是解锁钥匙**;静态真帧单独不行(0.257 地板),纯外观梯度和 LSTM 零历史也不够。证据: `artifacts/e5/r7_appearance_push/vision_replay/d1_receipt.json`。
- **含义**: MuJoCo 实况视觉序列缺少让策略减速的触发——候选: 外观(白门亮地)、接近轨迹几何、取景。正在跑: isaaclike 外观 + 0.9m campaign 式起始的 102 集 fishing(6 worker 并行)。
- 时代纪律: Isaac 侧一切运行仅冻结克隆(a1972552);MuJoCo student_source_root 待切冻结克隆(验证过 actor 类文件 era-identical);蒸馏 ws HEAD 被 co-tenant 活跃推进(DepthADD,且对方在建配对 trace 生产器)。
