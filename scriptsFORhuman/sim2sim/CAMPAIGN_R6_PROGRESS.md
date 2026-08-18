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
