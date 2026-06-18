# TODO

- 2026-06-17 16:47 HKT - 对已标 PASS 的 stage0/global/stage1 carrier reward 继续做 A2 footprint review：凡是沿用 G1 root-to-door/root-to-handle 距离、heading、standing-still、door contact 或 base height/orientation 假设的 term，都需要在 full GUI smoke 中检查是否因 A2 四足长 base 与 trunk reference 产生碰门、过近、过度站正或误触发。
- 2026-06-17 16:47 HKT - A2 footprint review priority：优先检查 `walk_to_door` 是否继续把 A2 root 推向 door root、`penalty_face_door` 是否过度要求正对门、`penalty_not_standing_still` 是否阻止 stage1 micro-adjustment、door frame/panel 与 `penalty_undesired_contact` 是否高频触发；仅在 smoke 证明问题后再调 target/threshold/scale。
- 2026-06-17 22:34 HKT - Stage2 static PASS 后的剩余 TODO：跑 bounded smoke，确认 stage2 dwell、completion route、door-open bypass ratio、stage3/open entry timing，以及是否存在 contact spike 误判；并开始 stage3/open reward completion/A2 adaptation review。
- 2026-06-17 22:41 HKT - Stage3/open 下一步：让 user 审核 `scriptsFORhuman/g1_doorman_stage3_reward_completion_a2_adaptation.md`；随后静态确认 door handle/hinge joint index 与 reward 正方向，并决定 `push_door_force` 是否继续 disabled 或设计 A2 source/door-frame force projection。
- 2026-06-17 00:00 HKT - Stage1+ reward adaptation 已建立 mapping docs；后续进入 open/swing/through reward implementation 或 grasp completion semantics 时继续沿用表格记录 G1 term、A2 replacement、数据源、scale、stage gating、direct workflow update timing 与验证方式，并同步更新 human docs 的 `A2适配状态` 列。
- 2026-06-15 22:33 HKT - 后续若新增来自 LMP manager-based 的 reward term，仍需先提取原始计算逻辑，再决定 direct path 迁移方案；本轮 `orientation_control` 已按 LMP source logic 完成 direct buffer 实现。
- 2026-06-14 21:48 HKT - 对来自 G1 Doorman 的 reward/stage semantics，先让 Ava 给出带 code reference 的核查意见；破坏性修改必须经 Ava 和 user 同意。
- 2026-06-15 14:32 HKT - `walk_to_door` 未来如 stage0 target 与 A2/Piper reach envelope 不匹配，将 reward target 参数化为 `door_root` / `grasp_target` / `approach_anchor`。
- 2026-06-15 14:32 HKT - `penalty_face_door` 未来如 full-quat penalty 对 A2 trunk roll/pitch 或必要侧向站姿过强，将改为 yaw-only heading error 或加入 desired heading offset。
- 2026-06-15 14:59 HKT - 后续迁移 reward scale 时同步核对 origin `reward_penalty_reward_names` membership；不要仅根据 reward scale 正负决定是否加入 penalty curriculum。
- 2026-06-15 16:59 HKT - 后续单独做 homie compatibility naming cleanup：`_homie_commands`、`get_physical_homie_commands`、`b_homie_commands` 等仍是历史兼容名，本轮只完成 reward-facing `penalty_base_command_limit` rename。
- 2026-06-15 21:29 HKT - 后续若 gripper action 改为 continuous aperture primitive，同步更新 `limits_gripper_primitive_action` 为 raw range penalty：`relu(abs(raw) - 1.1)`；runtime control 先 clamp raw 到 `[-1, 1]`，再用 `alpha = (clipped + 1) * 0.5` 映射 aperture。该 term 只约束 policy raw action 幅度，不根据 actual gripper joint pose/contact 判定。
- 2026-06-15 21:24 HKT - 后续 grasp-stage reward 设计应从“完全闭合 target”转向 aperture/contact/force/stability：避免奖励 gripper 把 handle 硬夹到 fully closed target，改为奖励合适开合度、双侧接触、不过大的 contact force、handle 与 gripper 相对稳定。
