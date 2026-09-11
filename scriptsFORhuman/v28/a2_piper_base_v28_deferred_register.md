# `base_v28` 待办登记（deferred register）

用途：登记 v28 明确不做、但在规划或执行中已识别的事项。每项给出来源决策、入场条件、归属 lane 与长期 TODO 的对应条目。每个预授权 commit 点同步一次：open 项镜像到 `scriptsFORhuman/a2_piper_longterm_TODO.md` D 节，closed 项入归档。
创建：2026-09-09 HKT（plan 冻结时）。状态取值：OPEN / HANDED_OFF / CLOSED / SUPERSEDED。

| ID | 事项 | 来源 | 入场条件 | 归属 | longterm_TODO_ref | 状态 |
|---|---|---|---|---|---|---|
| X-01 | 腕机塔架侧移（沿 F x ≥ 0.081 m @开度 35 mm / ≥ 0.108 m @20 mm）或后移，使腕机能看到 TCP/指垫并降低对门板的倾入 | D-04、D-07；射线核查与间隙扫掠（`planner_evidence_20260909/camera/`） | Wave A 出现 RIGHT 侧 `REACH_NOT_ESTABLISHED` 伴随塔架接触；或 Owner 决定改硬件 | 硬件 lane | D 节 N-07a | OPEN |
| X-02 | “带 / 不带相机 bundle”配对消融，并接上 Student 配对蒸馏以回答“observability-aware Teacher shaping 是否提高蒸馏成功率” | D-08 | v28 Teacher 资格通过且 Student lane 有两条蒸馏预算 | 主线 + Student lane | D 节 N-07b | OPEN |
| X-03 | A2_Base 替换为 LMP Stage2 导出策略（`44:50` = TCP 球坐标） | D-14 | Owner 交付 TorchScript `policy.pt` + metadata `gripper_position` 字段 + 训练覆盖说明；通过 plan §5.2 G0-L-swap | 主线（接口）+ LMP（训练/导出） | D 节 N-08 | OPEN |
| X-04 | j2/j3 默认值移离限位（现 0/0 落在 j2 下限、j3 上限，Stage5 `limits_dof_pos` 常驻） | D-03a | — | 主线 | E 节 | CLOSED（2026-09-09：Owner 授权，定为 j2=+0.10、j3=−0.10，进 plan D-03a） |
| X-05 | N-01 恢复环多 seed 确认（需重设计扰动强度与 loss 定义，v27 注入只产生 5/64、2/64 次 loss）与 N-02 交互历史 latent | D-01 | v28 closure 后，新底座上 | 主线 v29 | D 节 N-01/N-02 | OPEN |
| X-06 | base_right（或双侧）上仰角降到 0° 换取 1.8 m 外地面视野 | §3 覆盖表 | Student lane 证明地面/门槛可见性是失败因 | Student lane + 硬件 | D 节 | OPEN |
| X-07 | 设计包络 `wrist_u3_upright` 侵入 depth 画面（θ45 6.7%）的实 CAD 核查与修正（移 depth imager 或改支柱） | G0-C1' | G0 期间 | 硬件 lane | — | OPEN |
| X-08 | 关闭 `DoorDog-camera-baseline-20260908` / `DoorDog-camera-ablation-20260908` 两个 worktree | Owner 2026-09-09 | — | Student lane 仓库 | E 节 | CLOSED（2026-09-09 18:30 HKT：diff/status/HEAD 归档到 student worktree `logs_eval/d435_camera_regression_20260908/worktree_diffs_20260909/`（848+964 行，SHA256SUMS），`git worktree remove --force` ×2 + `prune` 完成） |
| X-15 | 共享层 `DeltaActionBase` 累积臂目标夹到物理限位（D-17），主线与 pull 同步开启 | D-17；pull v7 P0/P1 posture trap | — | 主线 + pull | D 节 | CLOSED（2026-09-09 18:40 Owner 批准，进两分支 G0） |
| X-17 | Student 相机几何条件化：per-pixel Plücker 射线图（Jiang et al., "Do You Know Where Your Camera Is?", arXiv 2510.02268, ICRA 2026；Video2DoorTraversal arXiv 2608.20251 在双 depth 门任务上采用）。价值：对安装外参变化鲁棒、允许蒸馏时随机化相机外参、支撑"Teacher 先按包络训练、光学安装后定"的分阶段冻结；代价：Student 架构加 6 通道射线图（每台相机）与 late fusion，需运行时内外参（SDK K + mount JSON 已有），随机裁剪须与射线图同步 | Owner 2026-09-11 | 蒸馏 plan 冻结前讨论 | Student lane | D 节 DIST-02 | HANDED_OFF |
| X-18 | Teacher 朝向/视场约束：先不加新的 heading 惩罚（现有 `penalty_face_door −1.0` 已在 Stage0–2 惩罚 root–door 全姿态偏差，Stage5 有意不罚）；v28 Wave A 加 report-only telemetry `handle_bearing_deg`（Stage0–2，相对 trunk +X）与 `doorway_bearing_deg`（Stage5），若 milestone 读数显示把手/门口超出前视相机水平半视场（RGB 34.5°、depth 43.5°）的份额 >10%，再预注册一个视场归属项（宽容差），不用 heading 误差项 | Owner 2026-09-11 讨论 | Wave A step1000/2000 读数 | 主线 | — | OPEN |
| X-17 | Student 相机条件化：按 Jiang et al. 2025（arXiv 2510.02268，"Do You Know Where Your Camera Is?"，ICRA 2026）用逐像素 Plücker 射线图（单位方向 d + 矩 m=p×d，6 通道）把每台相机的内外参（机器人基座系）显式喂给 Student；Video2DoorTraversal（arXiv 2608.20251）已在 A2-W 双 depth 开门任务中采用（late fusion：射线图经小 conv 编码后与 ResNet-18 depth 特征拼接），并配合相机外参随机化采集。对 DoorDog 的价值：(a) 对支架公差与手眼标定误差鲁棒；(b) 让"Teacher 按碰撞包络训练、光学安装在蒸馏时定"成立——Student 可在一组安装位姿分布上训练；(c) 与 DepthADD v3 的 `camera_meta` 6 维（age/valid）不冲突。蒸馏 plan 冻结前讨论：是否加入、每相机 6 通道与现有 8 通道 vision_obs 的拼接方式、随机裁剪需与射线图联动（原文强调）。 | Owner 2026-09-11 | 蒸馏 plan 起草时 | Student lane | D 节 DIST-02 | HANDED_OFF |
| X-16 | 门 asset 空洞面板（`door.py:1174 build_frame`，`randint(0,5)` 非零时门板 purpose=`guide`、只留边框、碰撞体保留；理论占比 80%，历史 315/384）：目标采样比例、是否补可见填充、或修复 Depth 不识别碰撞填充、并同步训练/验证/sim2sim 配置。v28 主线不负责；蒸馏分支在下一轮蒸馏数据生成/训练配置冻结前主动向 Owner 确认四点 | Owner 2026-09-11 | 下一轮蒸馏前 | Student lane（蒸馏分支） | D 节 DIST-01 | HANDED_OFF |
| X-09 | Student proprio 加夹爪 qpos 与 effort 代理（PiPER CAN effort，非 6D hand_force）；Student 按 `U3_F45_B15` 与新 asset 重训 | D-11 | Wave B 候选 manifest | Student lane | A 表 | HANDED_OFF |
| X-10 | 动作低通 / 控制延迟随机化 (`randomize_ctrl_delay`) 的部署侧决定 | D-09 | sim2sim lane 评估实机控制率与延迟 | sim2sim lane | E 节 | HANDED_OFF |
| X-11 | 修正 LMP `export_stage2_policy.py:319-320` 与 `contract.md` 的旧球心常量（0.135/0.687）；Stage2 导出 TorchScript | §2.7 | X-03 之前 | LMP | — | HANDED_OFF |
| X-12 | sim2sim MuJoCo 侧 54 维 A2_Base 观测构造与新 asset 同步 | §8.5 | v28 Wave B 后 | sim2sim lane | — | HANDED_OFF |
| X-13 | `isaacsim.py:791-804` `disable_gravity_for_arms` 分支按 config 顺序索引 physx view（未启用的潜在错位） | §2.3 | 若启用该分支 | 主线 | E 节 | OPEN |
| X-14 | 工具默认 USD 路径仍指旧 asset：`smoke_a2_base_flat_walk.py:18`、`preview_a2_piper_door_scene.py:18-19`、`a2_piper_v14_reachability_map.py:26` | §2.3 | v28 G0 顺带或轮间窗口 | 主线 | E 节 | OPEN |
| X-18 | 第三条 asset 路线：修正源装配 CAD/STL 的 trunk↔vpiper_support 三角面干涉（唯一同时满足物理保真与接触归属的方案） | G0 R2 阻塞；D-34 | Owner 授权且有 CAD 能力 | 硬件 lane | E 节 | OPEN（未授权） |
| X-19 | 朝向/可观测性 shaping（第五项 bundle：把手/门口在前视视锥内的平滑项；或约束 Stage0–2 横向指令） | Owner 2026-09-11 讨论；单前视相机前提 | Wave A 首个 milestone 的 `handle_bearing_*`/`doorway_bearing_*`/`stage0_2_vy_cmd_at_clip_share` 读数越过 Owner 预注册阈值 | 主线 | D 节 | OPEN（先测量，不加约束） |
| X-20 | base 相机最终布局：单中置 `[0.025,0,0.19]` +15°（几何推荐）vs 双 ±0.155 对称 15°；Teacher 已按两布局并集包络训练，最终布局须 ⊂ 并集并通过 G2-C2 覆盖表与渲染验收 | D-06/D-33（Owner 2026-09-11 后移） | 蒸馏 plan 起草时 | Student lane + 硬件 lane | D 节 | HANDED_OFF |
| X-21 | `clean_complete` 的 crossing hinge ≥ 1.0472 代理判据重审：塔架碰撞已提供物理安全信号，v27 中该分量单独否决了身体力为 0 的格（SC_S202 RIGHT 63/64）；Wave A endpoint 后用"塔架接触 vs 越门 hinge"实测关系决定 v29 是否改判据（v28 内不改，D-10） | 自省 S5；v27 closure | Wave A endpoint | 主线 | D 节 | OPEN |
| X-22 | 越门偏航与窄门通过性：v27 越门 root yaw 中位 12.5°（LEFT）/19.8°（RIGHT），整机扫掠宽 0.60–0.67 m；W p5=0.82 m 门在 60° 时净开口 0.70 m，机身–门框碰撞份额 23–28%（上界）；与相机无关（相机代价 0 mm） | `planner_evidence_20260911/camera/REPORT.md` §1.3 | Wave A `crossing_yaw_deg_*` 读数；与 X-19 合并考虑是否加 shaping | 主线 | D 节 | OPEN |
| X-23 | LEFT Stage2 发现失败的 seed 型（v26-7 Q05_S0/Q20_S0、v27 SC_S201 LEFT：D=0 六个 milestone）：v28 scratch seed 可能再现；仅有的预注册杠杆是第 4 seed 与 staged_reset 比例；未针对性处理 | v27 closure；v26-7 | v28 Wave A 任一 seed 同型 | 主线 | D 节 | OPEN |
| X-24 | 固定seed下小扰动散布已测得±3%（旧asset `arm_j5`−0.52→−0.415、65项0.970277–1.008755），本次seed282旧asset自比两类median/max均1.0，但冻结harness在设seed后无随机消费者，不能构成换seed随机实现或标定。X24保留，后续需实际随机暴露的校准；此次仅确定性复现。 | D-37；Owner 2026-09-12 | seed282类Stage2确认中完成旧asset281/282自比 | 主线 locomotion lane | D节 N-09 | OPEN（修改：-codex worker；依据：-owner） |
| X-25 | 臂前伸姿态下base的pitch/roll/yaw耦合残余较旧asset增16–23%，绝对量级在任务死区内有4.5–7倍余量；Stage2–3正是臂前伸且精度要求最高的阶段。若Wave A telemetry出现Stage2/3 base位姿不稳，此项是已知贡献因素，并与X-19朝向/可观测性shaping联动解释。 | D-37；三姿态离线重判 | Wave A Stage2/3 telemetry出现base位姿不稳 | 主线 + X-19 | D节 N-10 | OPEN（修改：-codex worker；依据：-owner） |
