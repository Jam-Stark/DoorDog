# `base_v28` 待办登记（deferred register）

用途：登记 v28 明确不做、但在规划或执行中已识别的事项。每项给出来源决策、入场条件、归属 lane 与长期 TODO 的对应条目。每个预授权 commit 点同步一次：open 项镜像到 `scriptsFORhuman/a2_piper_longterm_TODO.md` D 节，closed 项入归档。
创建：2026-09-09 HKT（plan 冻结时）。状态取值：OPEN / HANDED_OFF / CLOSED / SUPERSEDED。
更新：2026-09-12 17:18 HKT；修改：-codex planner；依据：-owner（D038–D040）。本次只修活动入口与回收条件，不重做已关闭事项。重复 X17 合为一项；历史朝向 X18 的活动内容归入 X19，X18 仅指 CAD/STL 路线，不设置兼容 alias。

| ID | 事项 | 来源 | 入场条件 | 归属 | longterm_TODO_ref | 状态 |
|---|---|---|---|---|---|---|
| X-01 | 腕机塔架侧移（沿 F x ≥ 0.081 m @开度 35 mm / ≥ 0.108 m @20 mm）或后移，使腕机能看到 TCP/指垫并降低对门板的倾入 | D-04、D-07；射线核查与间隙扫掠（`planner_evidence_20260909/camera/`） | Wave A 出现 RIGHT 侧 `REACH_NOT_ESTABLISHED` 伴随塔架接触；或 Owner 决定改硬件 | 硬件 lane | D 节 N-07a | OPEN |
| X-02 | “带 / 不带相机 bundle”配对消融，并接上 Student 配对蒸馏以回答“observability-aware Teacher shaping 是否提高蒸馏成功率” | D-08 | v28 Teacher 资格通过且 Student lane 有两条蒸馏预算 | 主线 + Student lane | D 节 N-07b | OPEN |
| X-03 | A2_Base 替换为 LMP Stage2 导出策略（`44:50` = TCP 球坐标） | D-14 | Owner 交付 TorchScript `policy.pt` + metadata `gripper_position` 字段 + 训练覆盖说明；通过 plan §5.2 G0-L-swap | 主线（接口）+ LMP（训练/导出） | D 节 N-08 | OPEN |
| X-04 | j2/j3 默认值移离限位（现 0/0 落在 j2 下限、j3 上限，Stage5 `limits_dof_pos` 常驻） | D-03a | — | 主线 | E 节 | CLOSED（2026-09-09：Owner 授权，定为 j2=+0.10、j3=−0.10，进 plan D-03a） |
| X-05 | N01/N02在G1停止点已完成复核：两项继续有界立项设计、实验执行DEFER；N01先建立可解释失抓暴露，N02先明确传感/可辨识性与未收敛门域。方法条目继续开放 | D-01、D-38、D045 | 本次closure回收完成；新pilot须独立范围与预算 | 下一阶段planner | D节N-01/N-02；E节回收归档 | CLOSED（2026-09-14；仅关闭本次复核义务） |
| X-06 | base_right（或双侧）上仰角降到 0° 换取 1.8 m 外地面视野 | §3 覆盖表 | Student lane 证明地面/门槛可见性是失败因 | Student lane + 硬件 | D 节 | OPEN |
| X-07 | 按最终 C_S rig/CAD 核查自身支柱与 Min-Z 内像素；当前名义包络为 140 mm/38.76°。旧 θ45 下 6.7% 为历史设计包络读数，不是当前实 CAD 验收 | D-18/D-30/D-35/D-38；G2-C1′ | 蒸馏前 G2，真实 CAD 到位后 | Student + 硬件 lane | D 节 C_S/G2 承接 | OPEN |
| X-08 | 关闭 `DoorDog-camera-baseline-20260908` / `DoorDog-camera-ablation-20260908` 两个 worktree | Owner 2026-09-09 | — | Student lane 仓库 | E 节 | CLOSED（2026-09-09 18:30 HKT：diff/status/HEAD 归档到 student worktree `logs_eval/d435_camera_regression_20260908/worktree_diffs_20260909/`（848+964 行，SHA256SUMS），`git worktree remove --force` ×2 + `prune` 完成） |
| X-15 | 共享层 `DeltaActionBase` 累积臂目标夹到物理限位（D-17），主线与 pull 同步开启 | D-17；pull v7 P0/P1 posture trap | — | 主线 + pull | D 节 | CLOSED（2026-09-09 18:40 Owner 批准，进两分支 G0） |
| X-17 | Student 相机条件化：按 Jiang et al. 2025（arXiv 2510.02268，"Do You Know Where Your Camera Is?"，ICRA 2026）用逐像素 Plücker 射线图（单位方向 d + 矩 m=p×d，6 通道）把每台相机的内外参（机器人基座系）显式喂给 Student；Video2DoorTraversal（arXiv 2608.20251）已在 A2-W 双 depth 开门任务中采用（late fusion：射线图经小 conv 编码后与 ResNet-18 depth 特征拼接），并配合相机外参随机化采集。对 DoorDog 的价值：(a) 对支架公差与手眼标定误差鲁棒；(b) 让"Teacher 按碰撞包络训练、光学安装在蒸馏时定"成立——Student 可在一组安装位姿分布上训练；(c) 与 DepthADD v3 的 `camera_meta` 6 维（age/valid）不冲突。蒸馏 plan 冻结前讨论：是否加入、每相机 6 通道与现有 8 通道 vision_obs 的拼接方式、随机裁剪需与射线图联动（原文强调）。 | Owner 2026-09-11 | 蒸馏 plan 起草时 | Student lane | D 节 DIST-02 | HANDED_OFF |
| X-16 | 门 asset 空洞面板（`door.py:1174 build_frame`，`randint(0,5)` 非零时门板 purpose=`guide`、只留边框、碰撞体保留；理论占比 80%，历史 315/384）：目标采样比例、是否补可见填充、或修复 Depth 不识别碰撞填充、并同步训练/验证/sim2sim 配置。v28 主线不负责；蒸馏分支在下一轮蒸馏数据生成/训练配置冻结前主动向 Owner 确认四点 | Owner 2026-09-11 | 下一轮蒸馏前 | Student lane（蒸馏分支） | D 节 DIST-01 | HANDED_OFF |
| X-09 | Student proprio 的夹爪 qpos 与可部署 effort 代理在 C_S 冻结（非仿真 6D hand_force）；Student 使用最终 C_S rig 与新 asset 生成数据，当前名义 rig 为 `U3_F39_H140`，base 单/双仍待定，不沿用旧 `U3_F45_B15` 作为最终合同 | D-11/D-30/D-35/D-38 | 蒸馏 plan 与传感合同冻结；Teacher 标签使用 Wave B 合格候选 manifest | Student lane | D 节 C_S/G2 承接 | HANDED_OFF |
| X-10 | 动作低通 / 控制延迟随机化 (`randomize_ctrl_delay`) 的部署侧决定 | D-09 | sim2sim lane 评估实机控制率与延迟 | sim2sim lane | E 节 | HANDED_OFF |
| X-11 | 修正 LMP `export_stage2_policy.py:319-320` 与 `contract.md` 的旧球心常量（0.135/0.687）；Stage2 导出 TorchScript | §2.7 | X-03 之前 | LMP | — | HANDED_OFF |
| X-12 | sim2sim MuJoCo 侧 54 维 A2_Base 观测构造与新 asset 同步 | §8.5 | v28 Wave B 后 | sim2sim lane | — | HANDED_OFF |
| X-13 | `isaacsim.py:791-804` `disable_gravity_for_arms` 分支按 config 顺序索引 physx view（未启用的潜在错位） | §2.3 | 若启用该分支 | 主线 | E 节 | OPEN |
| X-14 | 工具默认 USD 路径仍指旧 asset：`smoke_a2_base_flat_walk.py:18`、`preview_a2_piper_door_scene.py:18-19`、`a2_piper_v14_reachability_map.py:26` | §2.3 | v28 G0 顺带或轮间窗口 | 主线 | E 节 | OPEN |
| X-18 | 独立 CAD/STL 路线：修正源装配 trunk↔vpiper_support 三角面干涉。MERGED 已通过当前狭义 G0；本项不是当前训练阻塞，也不是本轮另选 asset 的授权 | 历史 G0 R2；D-34/D-38 | Owner 另行授权且有 CAD 能力 | 硬件 lane | D 节 C_S/G2 承接 | OPEN（未授权） |
| X-19 | 朝向/可观测性 shaping：当前只报告 Stage0–2 把手方位、Stage5 门口方位、越门 yaw 与横向指令顶限份额；保留现有 `penalty_face_door`，不增加 heading reward 或删除 vy。结合前视视场与 X22/X25 读数再决定后续 shaping，不能中途改变原三 seed 配方 | Owner 2026-09-11 讨论；D-38；合并历史朝向 X18 | Wave A 既定 milestone 出现相关事件后提交读数；具体 shaping 与阈值须新决定 | 主线 | D 节行为问题 | OPEN（先测量，不加约束） |
| X-20 | base 相机最终布局：单中置 `[0.025,0,0.19]` +15°（几何推荐）vs 双 ±0.155 对称 15°；C_T 已冻结两布局并集包络，尚无本轮 Teacher 训练结果。最终布局按 C_S 冻结并通过包含关系、G2-C2/渲染和安装件交换检查 | D-06/D-30/D-33/D-38 | 蒸馏 plan 起草时 | Student lane + 硬件 lane | D 节 C_S/G2 承接 | HANDED_OFF |
| X-21 | `clean_complete` 的 crossing hinge ≥ 1.0472 代理判据重审：塔架碰撞已提供物理安全信号，v27 中该分量单独否决了身体力为 0 的格（SC_S202 RIGHT 63/64）；Wave A endpoint 后用"塔架接触 vs 越门 hinge"实测关系决定 v29 是否改判据（v28 内不改，D-10） | 自省 S5；v27 closure | Wave A endpoint | 主线 | D 节 | OPEN |
| X-22 | 越门偏航与窄门通过性：v27 越门 root yaw 中位 12.5°（LEFT）/19.8°（RIGHT），整机扫掠宽 0.60–0.67 m；W p5=0.82 m 门在 60° 时净开口 0.70 m，机身–门框碰撞份额 23–28%（上界）；与相机无关（相机代价 0 mm） | `planner_evidence_20260911/camera/REPORT.md` §1.3 | Wave A `crossing_yaw_deg_*` 读数；与 X-19 合并考虑是否加 shaping | 主线 | D 节 | OPEN |
| X-23 | LEFT Stage2 发现失败的 seed 型（v26-7 Q05_S0/Q20_S0、v27 SC_S201 LEFT：D=0 六个 milestone）：若再现则报告并单独诊断。该模式本身不触发 A_S284（其触发为 D31 的 Stage4 到达但不完成），也不授权改 staged reset 比例 | v27 closure；v26-7；D-38/D-40 | v28 Wave A 任一 seed 同型 | 主线 | D 节行为问题 | OPEN |
| X-24 | 固定 seed 的旧 asset 单关节扰动 65 项比值为 0.970277–1.008755；seed282 自比精确相同但冻结 harness 无新的随机消费者，只有确定性复现。下次立项时复核具有真实随机暴露的校准需求，不能据当前零散布关闭本项或声称统计标定 | D-37/D-38；Owner 2026-09-12 | 下一次 asset/A2_Base 变更立项时复核；具体校准运行另行授权，不成为当前新增 STOP | 主线 locomotion lane | D 节 N-09 | OPEN |
| X-25 | 臂前伸姿态下base的pitch/roll/yaw耦合残余较旧asset增16–23%，绝对量级在任务死区内有4.5–7倍余量；Stage2–3正是臂前伸且精度要求最高的阶段。若Wave A telemetry出现Stage2/3 base位姿不稳，此项是已知贡献因素，并与X-19朝向/可观测性shaping联动解释。 | D-37；三姿态离线重判 | Wave A Stage2/3 telemetry出现base位姿不稳 | 主线 + X-19 | D节 N-10 | OPEN（修改：-codex worker；依据：-owner） |
