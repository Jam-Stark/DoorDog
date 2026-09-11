# `base_v28`：camera-aware bilateral Teacher re-baseline（新 asset、新姿态、三相机几何合同）预注册计划

日期：2026-09-09 HKT
状态：`G0_RESUMED_BY_OWNER`（2026-09-11 23:06 HKT：Owner 选定 MERGED asset、140 mm/38.76° 塔架、reset j5 −0.415、分期冻结 D-30、K driver 备选 D-31、选种门拆层 D-32，并授权 R2/R3/R5 复跑与候选物理验收；修改：-planner；依据：-owner。此前 `G0_PAUSED_BY_OWNER` 2026-09-09；修改：-codex worker）
Owner 授权：GPU0–7 可用于 v28（受外部占用约束，见 §10）；G0/G1/Wave A/Wave B 按 §9 自主推进；四个本地 commit 点预授权；push、Teacher/Student G7 binding 更新、hardware 动作未授权。
上游：v27 plan（`scriptsFORhuman/v27/a2_piper_base_v27_plan_20260905.md`）及其 Wave A/B 冻结结论；Wave C endpoint 是 v28 的条件输入（§8.3）。
路线依据：`scriptsFORhuman/a2_piper_longterm_TODO.md` R 节（2026-09-05）与本文件 §1 决策记录（2026-09-09）。
规划证据：`scriptsFORhuman/v28/planner_evidence_20260909/`（五个只读调查 lane 的报告与 CPU 计算输出；全部为 INSPECTED / STATIC / COMPUTED 级，未运行 Isaac）。
run_id：`v28_camera_aware_rebaseline_20260909`

修改标记：`-codex worker` / `-owner`。由 worker 根据 Owner 指示修改时，同时标注“修改：-codex worker；依据：-owner”。（标记规则：-owner；落笔：-codex worker）

本文件是 v28 的 authority。Codex 开工 prompt 与本文件冲突时以本文件为准；本文件与当前 source / resolved config 冲突时，以 source 为准并回报，不得静默改判。

---

## 0. 结论与范围

### 0.1 v28 是什么

v28 是一次 **re-baseline**：三项基建同时变更——训练 robot asset 换为 `a2_piper_vpiper_final_20260906`（含相机安装件质量、碰撞体，并新增腕机塔架碰撞 link）、PiPER reset/默认姿态换为 `[0,0.10,−0.10,0,−0.415,1.57]`、以及一个最小的 camera-aware reward bundle——然后在新底座上从零重建双侧 Teacher，并按 v27.0 的资格程序做一次 sim 资格认定。v27 的任何数字在 v28 之后都不再是 baseline。同一套基建同步到 pull 分支（`scriptsFORhuman/pull_v28_alignment/a2_piper_pull_v28_baseline_sync_plan_20260909.md`），两分支在 v28 之后共享 asset、姿态、动作语义、相机合同与 harness。

规划阶段已经得到两个改变设计的硬结论（§2.5、§2.6）：
1. 腕机塔架在 F+Y（手指开合轴）上时，任何倾角都看不到 TCP 与指垫，只能看到把手条伸出指宽之外的两端；“腕机看到 gripper”在现有塔架上只能实现为“看到把手条两端与门板近场”。
2. v27 的 RIGHT 门抓握姿态会让 180 mm 塔架穿过门板（Stage4 帧的 41–65%），与 θ 无关。塔架碰撞体因此不是可选项：v28 Teacher 必须在带塔架碰撞体的 asset 上从零学出不同的抓握姿态。这同时也是对硬件方案的一次检验。

### 0.2 v28 不是什么（non-goals）

- 不承载 R 节的 N-01（恢复环多 seed）与 N-02（交互历史 latent）；二者顺延至 v29，理由是基建变更会使它们的差异无法归因。
- 不做“带 / 不带相机 bundle”的配对消融；Owner 决定只训练带 bundle 的版本，消融登入待办登记 X-02。
- 不改 reward 函数逻辑（新增两个独立小函数除外，§6）、stage 判据、trainer loader、`clean_complete` 的 hinge 判据（≥1.0472 rad 保留）。
- 不引入控制器级动作低通或动作保持；平滑由 policy 通过 reward 学会；控制接口变更归 sim2sim lane（X-10）。
- 不替换 A2_Base locomotion policy（§5.2，D-14）；替换预注册为 v29 或“候选在 Wave A 前到位则作为 opt-in 分支”。
- 不更新 Teacher/Student G7 binding；不做 hardware。

### 0.3 四个问题

| 问题 | 内容 | 性质 | 阶段 |
|---|---|---|---|
| Q_G | 新 asset + 新姿态 + 三相机/塔架碰撞体在几何、碰撞、覆盖、locomotion 上是否成立 | 工程门 | G0（离线 + 一次 smoke） |
| Q_S | 在新底座上 from-scratch 3 seed 是否重建双侧 complete / clean_complete 能力 | 工程可靠性 | Wave A |
| Q_V | camera-aware bundle 下 Teacher 的相机运动、观察姿态与塔架安全是否达到预注册目标，且不损失 Q_S | 工程可靠性（report + 门） | Wave A |
| Q_Q | 选中 seed 是否通过 exact128 DEV/CONF 资格门 | 资格认定 | Wave B |

---

## 1. 决策记录（ADR）

每条：决定、被否决的替代、依据、状态、重审触发。v28 期间新增决策追加到本表并同步 memory（§11）。

| ID | 决定 | 替代方案（否决） | 依据 | 状态 | 重审触发 |
|---|---|---|---|---|---|
| D-01 | v28 定位为 re-baseline，N-01/N-02 顺延 v29 | 在 v28 同时做恢复环或 history latent | 三项基建变更叠加，差异无法归因；v26 六轮教训 | 冻结 | 无 |
| D-02 | 切换 asset 到 `a2_piper_vpiper_final_20260906` | 保留旧 asset 只加相机 | 实机即新装配；旧 asset 无安装件质量与碰撞体；新 asset 为旧 asset 的严格超集（§2.3） | 冻结 | G0-A/R 门失败 |
| D-03 | reset/默认姿态 `[0,0.10,−0.10,0,−0.415,1.57]`（j5* = −(θ − 15°)，θ=38.76° → −0.415 rad，行走时腕机光轴 −14.9°） | `[0,0,0,0,0,1.57]`（安装包前视参考姿态）；解耦姿态锚点与动作零点 | Owner 确认原参考姿态无硬件约束；动作零点、Stage0/5 姿态锚点、观察姿态、Stage0→1 门四者重合（§5.1）；2026-09-11 随 D-35 由 −0.52 改为 −0.415 | 冻结（2026-09-11 更新） | θ 变更 |
| D-03a | j2=+0.10、j3=−0.10（原 0/0 落在 j2 下限与 j3 上限） | 维持 0/0（官方机械范围内合法） | `limits_dof_pos` 用 0.95 软限位：j2 软下限 0.0785、j3 软上限 −0.0742，0/0 每步付 0.153 rad×5×dt=−0.0153，并与 −5 的姿态惩罚在默认点互相拉扯；+0.10/−0.10 各留 0.02 rad 余量。j2/j3 轴平行，前臂/相机光轴姿态不变（−15.16°），TCP 仅上移 28 mm（trunk 系 z 0.460→0.488）；Stage0→1 门相对默认定义，不受影响 | 冻结（Owner 2026-09-09 授权由 planner 定） | 无 |
| D-04 | ~~腕机 mount 倾角 θ = 45°，40° 为回退值~~ **SUPERSEDED by D-35（2026-09-11：140 mm / 38.76°）**；近场需求定义保留：“把手条两端与上指尖外侧在腕机 depth 中可见，RGB 报告” | 保持 F0/F15；“TCP/指垫入 RGB”为标准 | 射线核查（真实手指 mesh）：任何 θ 下 TCP/指垫都被上指遮挡，只有把手条两端 24–52% 可见；θ45 的 Stage2/3 RGB 把手份额 99%/45% 优于 θ40 的 79%/12%；depth 两角都 88–100% | 冻结（G0-C1' CAD 核查可切 40） | 设计包络 `wrist_u3_upright` 在 depth 画面占 6.7%（θ45）/3.7%（θ40）若被 CAD 证实且不可接受 |
| D-05 | 腕机前视/地面视野由 j5 姿态提供，不由 mount 角折中 | 单一固定倾角折中 | 固定倾角下“看近场”(≥40°) 与“0.8 m 外看把手”(≤30°) 互斥 | 冻结 | 无 |
| D-06 | base 相机布局（单中置 vs 双 ±0.155）与上仰角 **后移到蒸馏前决定**（Owner 2026-09-11，随 D-30）；若为双相机则左右对称上仰 15° 仍是几何推荐；Teacher 的 trunk 碰撞包络取两种布局的**并集**（双 ±0.155 支架/外壳盒 + 中置外壳盒），质量取双相机值 | 训练前定单/双 | 通过性代价为 0 mm（`planner_evidence_20260911/camera/REPORT.md` §1），双相机只多 LEFT 门铰链侧门框通道与 base RGB 冗余，这两项没有冻结验收判据，可留到渲染验收后再定 | 后移（C_S） | 蒸馏前 G2-C2 覆盖表与渲染验收 |
| D-07 | 腕机塔架与外壳作为独立固定 link `wrist_camera_tower` 进入 asset 碰撞模型，从 Wave A 起生效，并配接触惩罚 | 只报告间隙；把盒子并入 `arm_body6_to_gripper` | 间隙扫掠：v27 RIGHT 门 Stage4 塔架穿板 65%/41%，LEFT 释放后 3.7%，与 θ 无关；`penalty_undesired_contact` 严格要求 20 体元组且排除门板接触，塔架接触必须单独建体与惩罚（§4.2、§6） | 冻结 | 无 |
| D-08 | 只训练带相机 bundle 的 Teacher | 配对无 bundle 对照 | Owner 决定；消融进 X-02 | 冻结 | 无 |
| D-09 | 动作平滑由 reward 学会，不加控制器低通 | 控制器低通 / 2 步保持 | Owner 决定；接口变更归 sim2sim lane（X-10） | 冻结 | sim2sim lane 引入接口变更 |
| D-10 | `clean_complete` 保留 crossing hinge ≥ 1.0472 rad | 放宽到零接触即干净 | 塔架使 60° 门缝挤过成为真实碰撞风险 | 冻结 | 无 |
| D-11 | Student 在 Stage2–4 的抓握/接触信息同时依赖视觉（腕机近场 depth、base 相机手指）与本体量（夹爪 qpos + effort 代理） | 仅视觉 / 仅本体 | Owner 决定“both”；射线核查表明腕机看不到指垫，本体量不可省 | 冻结 | Student lane 传感合同变化（X-09） |
| D-12 | v28 训练默认 from-scratch；warm-start 仅在 G1 probe 通过时作为附加 arm | 直接 warm-start v27 checkpoint | 动作零点（j4 −0.25、j5 −1.02 rad）与 `dof_pos` 观测零点同时漂移；v26-8/v27 两次 warm-start 带旧盆地 | 冻结 | Wave C `SCRATCH_NOT_ESTABLISHED` |
| D-13 | K scaffold-decay 是否进入 v28 配方由 Wave C SK 对 SC 的 typed outcome 决定 | 人为决定 | v27 §6 的 K 二次检验正是为此设计 | 冻结 | 无 |
| D-14 | 保留当前 A2_Base（`gr00t/rl/data/policies/A2_Base/policy.pt`），加 locomotion 验收门 G0-L；替换预注册为 v29，或候选在 Wave A launch 前通过 G0-L-swap 则作为 opt-in 分支 | 等待新 A2_Base 再开 v28 | 新 asset/新姿态的质量与 CoM 变化（+0.754 kg、≤2.2 mm）远在 LMP Stage1 随机化（trunk +[0,5] kg、CoM ±0.1 m）之内；候选 policy 尚不存在（LMP `44:50` 改动仅语法检查，Stage2 导出为 npz，metadata 常量陈旧）；DoorDog 行走相 TCP 球坐标 l 0.14–0.33 m 落在 Stage2 arm-goal 盒（l ≥ 0.4）之外 97–100% | 冻结 | 候选 policy 到位且通过 §5.2 G0-L-swap |
| D-15 | 配置采用扁平冻结 `base_v28_common.yaml` + CPU compose-diff allowlist 校验 | 继承 `base_v27_common` | v27 配方经 8 层 Hydra 继承，load-mode/夹爪增益/预算在多达 7 层被改写；`base_v27_SC_*.yaml` 未跟踪 | 冻结 | 无 |
| D-16 | 评估用 `++experiment_dir=<eval artifact dir>`，训练 root 保持不可变 | 沿用 v27 的 inputs 复制法 | v27 缺陷 f：eval 在 checkpoint 旁写 `exported/` | 冻结 | 无 |
| D-17 | 共享类 `DeltaActionBase` 增加配置键 `delta_action_clamp_to_dof_limits`（默认 false，bit-identical），为 true 时把累积臂目标 `default + 0.25·d` 逐关节夹到物理限位内；v28 主线与 pull 同时开启 | 只在 pull 侧加越界惩罚（pull v7 D2）；不处理 | 累积增量 `d` 的 clip ±15 对应 ±3.75 rad，超过每个臂关节半程；目标越界后要靠约 50 步反向输出才能回到范围内，形成零梯度平台。pull v7 P0/P1 证明它是 release-ready 全为 0 的结构性原因（j3 target 钉在 +3.75、99% 步越界）；主线 v27 trace 里 Stage5 j2/j3 被饱和积分器钉在限位（a_raw RMS 1.05–3.6、\|dq\| p50≈0.01）是同一现象。实机 PiPER 对越界目标本来就拒绝/截断。v28 两分支都从零训练，是同步修共享层的唯一低成本时点 | 冻结（Owner 2026-09-09 18:40 批准） | pull Wave P-A `MARGIN_TRAP_PERSISTS` |
| D-18 | 先仿真、后硬件设计；G0-C1′ 记录 `NOT_RUN`，不以不存在的腕机真实 CAD 阻塞仿真 G0；碰撞与自遮挡使用显式估算包络验收 | 把设计包络称为真实 CAD，或等待硬件图纸才做仿真 | Owner 在 G0 执行中确认腕机支架尚未设计，要求诚实记录 | ACCEPTED（2026-09-09；修改：-codex worker；依据：-owner） | 腕机 CAD 到位后重新做实 CAD 遮挡/间隙核查 |
| D-19 | 腕机支架用单个与 D435i 等宽、等厚的长方体，截面 90×25 mm，连接 Piper 末端 body 与 D435i；外壳单独一个盒；相机中心与 θ45 不变 | 四段支架包络；8×8 mm 细杆（本次先前中间版本） | Owner 指出宽厚长方体更接近可能的腕机支架；细杆版几何证据不再用于最终 G0 | ACCEPTED（2026-09-09；修改：-codex worker；依据：-owner） | 新包络出现自身碰撞或相机覆盖失败，回报真实结果 |
| D-30 | 合同分两段冻结——C_T（碰撞包络含塔架与 base 支架盒、质量/惯量、冻结姿态、D-17 夹紧、reward bundle、telemetry、G0-C3）在 Teacher 训练前冻结；C_S（腕机光学中心高度/θ 的成像含义、base 上仰角的成像含义、近场/前视可见预算、渲染域一致性、Student 裁剪、G0-C1/C1′/C2/C4 → G2-C*）在蒸馏前冻结；加 containment 判据（最终支架+外壳盒 ⊂ E_T，SDF ≤ −3 mm；质量 ≤ 训练值、质心距 F 原点 ≤ 训练值、主惯量逐项 ≤ 训练值）与蒸馏前 eval-time 安装件交换检查（§8.2） | 全部光学项训练前冻结；或全部后移 | Teacher 不渲染相机，三项新奖励只依赖关节运动/接触/回位（`door_open_a2_base.py:15937-15954`）；但 θ 与冻结姿态耦合：j5=−0.52 只对 θ=45 给出行走光轴 −15°，θ 后移到 38.8°/34.5° 时光轴 −9°/−4.7°，depth 地面起点从 ≈1.5 m 退到 ≥1.9 m（`planner_evidence_20260911/g0/REPORT.md` §4） | 冻结（Owner 2026-09-11 批准；base 相机数量随 D-06 后移） | containment 判据失败 |
| D-31 | K driver 备选——保持 v27 已检验的 `target_stage=4`，但把 `K_REACH_WITHOUT_COMPLETE`（连续两个 milestone 双侧 S4+ ≥ 56 且 complete ≤ 4）预注册为具名失败并落 driver trace；若触发且有预留 seed，第 4 个 seed 用 `target_stage=5` | 直接改 `target_stage=5`（未被 Wave C 检验） | SK_S212：Stage4 到达率 100% 而 complete 0；driver 只测到达不测完成，v28 塔架碰撞与新姿态会放大该落差 | 冻结（Owner 2026-09-11 批准） | 无 |
| D-32 | Wave A 选种门拆层——reachability 门（双侧 complete ≥ 60、low_height+overspeed ≤ 2、塔架接触 ≤ 2、`post_release_body_force_p95 ≤ 5 N`）用于选种；`clean_complete`（含 hinge ≥ 1.0472，D-10 不变）继续作为 Wave B 资格门与逐 milestone 分级报告 | 沿用合取门选种 | v27 中可达性被 4/6 Wave C 格与全部 warm 格达到，合取门只有 1/6 通过；SC_S202 RIGHT 63/64 集因 hinge 判不干净而身体力为 0，与 SC_S203 的 hinge+接触失败同标签，选种门遮住了失败原因 | 冻结（Owner 2026-09-11 批准） | 无 |
| D-33 | ~~建议 base 相机改为单台中置~~ **后移到蒸馏前决定（并入 D-06，Owner 2026-09-11）**；几何推荐仍是单台中置 `[0.025, 0, 0.19]`、上仰 15°（`U3_F45_C15`），trunk 支架碰撞盒由 8+2 缩为 4+1、横梁 ≤ 0.09 m，trunk 侧向半宽回到 0.140；D-06 随之 SUPERSEDED | 保留双 ±0.155（V0） | 通过性：相机总成外缘 ±0.200 m 落在腿/足 ±0.2348 m 凸包内，128 条 v27 穿门 episode 的侧向间隙带/不带相机逐行相同，因相机碰撞或 <3 cm 的份额 0.0%——通过性是 Teacher 偏航（越门 yaw p50 12.5°/19.8°）问题，不是相机问题；覆盖：单中置 +15° 保住把手侧门框 99–100%、自由边 94–100%，只丢 LEFT 门铰链侧门框（43→9%）与 base RGB 冗余；上仰 0° 或旧 head 位（抓握期门框 0%）不可接受（`planner_evidence_20260911/camera/REPORT.md`） | 后移（C_S） | 渲染验收显示 Student 需要铰链侧门框通道 |
| D-34 | asset 候选选 **MERGED**（mount 并入 trunk，精确复合惯量，28 刚体）；第三条路线（修正源 STL 干涉）登记但未授权 | CUT（31 刚体，删几何保惯量，+1.00 mm 间隙） | MERGED 不删几何、mount 接触归 trunk 并被 body 类惩罚覆盖、按构造消除 trunk↔support 自接触；CUT 质量-几何不一致且 mount 接触永久静默；两者 `body_names`(28)/`penalize_contacts_on`(20) 都不变，差别在 contact sensor 计数与 G0-A1 判据（`planner_evidence_20260911/g0/REPORT.md` §2） | 冻结（Owner 2026-09-11 批准） | R2 复跑仍有异常接触 |
| D-35 | 训练前定腕机塔高与 θ 为 **140 mm / 38.76°**，reset j5 相应改为 −0.415 rad（行走光轴仍 −15°）；E_T 用该设计的两盒，不用族包络 | 180 mm / 45°（现值）；族包络盒 | 180 包络不包含 140/120（外伸 12.0/10.3 mm）；140 mm 通过近场 depth 门（把手条两端 29%/48% @开度 0.013/0.035）而 120 mm 不通过（19%）；远场只掉 7–15 pp；塔顶低 40 mm 减小穿门板风险与力矩 | 冻结（Owner 2026-09-11 批准） | 无 |

---

## 2. 输入事实（INSPECTED / STATIC / COMPUTED，2026-09-09）

### 2.1 v27 状态与 v28 的条件输入

- Wave A 冻结 `RECIPE_A=C`（v17 计价/走廊制度未改善 LEFT clean）；Wave B 冻结 `RECIPE_B=current`（mass 80–120、friction off；域扩展未损失 complete）；`Q_R=UNRESOLVED`（R1 harness 误停；注入扰动太弱，loss 事件 5/64、2/64）。
- Wave C（2026-09-11 closure，`scriptsFORhuman/v27/a2_piper_base_v27_execution_closure_20260911.md`；复核见 `planner_evidence_20260911/v27/REPORT.md`）：六格 6000、72/72 lane、integrity 0。**`sc_outcome = SCRATCH_NOT_ESTABLISHED`（0/3）、`sk_outcome = K_SCRATCH_SUPERIOR`（1/3 对 0/3，guard 全过）**，与预注册规则一致。失败类型：SC_S201 LEFT 卡 Stage2（D=0，与 v26-7 S0 同型）；SC_S202 双侧 complete 64/64 但 clean 23/1（失败分量几乎全是 crossing hinge < 1.0472，身体力 0）；SC_S203 complete 60/63、clean 0/0（hinge + 身体接触 + 超速 4）。SK_S213 是**全 v27 唯一双侧过 64 样本门的格**（clean 62/63，跃升在 5000→6000）；SK_S211 LEFT clean 64/64、RIGHT 34（身体接触）；SK_S212 双侧 open_hold 64/64 而 complete 0（到达 Stage4 却从不完成，`arm_j4` 限位驻留 0.16/0.66）。warm 血统格（C_S21 clean 51/41、C_S22 0/39、L1_S32 63/52、R0 52/47）全部未过质量门。guard 本轮退化（SC 基线为 0 或饱和，−8 容差未被触及，对 SK_S212 型失败不敏感）。
- v27.0 资格：`NO_QUALIFIED_CANDIDATE`；v27.5 最终确认按冻结规则 `NOT_RUN`；manifest v2 无任一候选 `binding_eligible`；Teacher/Student G7 binding 仍为 v23 单 RIGHT（本 plan 建议维持，§8.6）。

### 2.2 v27 控制配方（v28 的继承基线）

resolved 自 `wave_c_contract.json → cells.SC_S201.resolved_contract`（1555 键；dump 见 `planner_evidence_20260909/recipe/sc_s201_resolved_keys.txt`，G0 重新生成并入 source lock）。决策相关键：

| 组 | 键 = 值 |
|---|---|
| 加载 | `checkpoint=null`；`checkpoint_load_mode=full`；`auto_load_latest=false`；`num_envs=4096` |
| 预算/保存 | `algo.trl.num_total_batches=6000`；`callbacks.model_save.save_frequency=250`；`algo.config.save_interval=500` |
| PPO | `num_steps_per_env=64`；`num_learning_epochs=5`；`num_mini_batches=4`；actor/critic lr `1e-4`；`entropy_coef=0.01`；`desired_kl=0.005`；`gamma=0.9975`；`lam=0.985`；`init_noise_std=0.8`、`max_noise_std=0.8`、`clamp_noise_std=true` |
| 网络 | actor/critic LSTM 256×2 + MLP [512,256,128] |
| A2_Base | `policy_path=./gr00t/rl/data/policies/A2_Base/policy.pt`；`obs_dim=1620`；`command_scale=0.25`；`command_multipliers=[2,2,0.25,1,1]`；`base_command_dim=5`；`manipulation_action_dim=7` |
| 夹爪能力 | `dof_effort_limit_list[arm_j7/j8]=45.0`；stiffness `1300`、damping `32`；`a2_m39_gripper_material_enabled=true`；`a2_stage2_squeeze_force_min=0.5`、`max=30.0`、`over_force_threshold=55.0` |
| 侧别/几何 | `a2_v26_door_open_lr=bilateral`；`a2_v26_6_side_mirrored_handle_offset_enabled=true`；`a2_v26_4_side_canonicalization_enabled=false`；`a2_v26_5_shared_residual_observation_enabled=false`；`a2_gripper_source_tcp_offset_z=0.085` |
| 门域 | `a2_v26_door_weight_range=[80,120]`；`a2_v26_door_handle_height_range=[0.85,0.95]`；`a2_v24_friction_enabled=false`；natural start on：normal `[0.9,1.4]`、lateral `[-0.25,0.25]`、yaw `[-0.3,0.3]` |
| Stage | `max_episode_length_s=20`；`max_stage_time=[350,100,100,100,100,200]`；Stage3→4 `0.25`；`near_closed 0.1`；Stage4→5 `1.0472`；release `1.2`；`a2_grasp_gate_mode=control_streak`、streak `5`；`a2_stage3_base_unlocked=true`；`a2_corridor_enabled=false`；`a2_stage0_arm_default_max_deviation=0.1` |
| Reset | `enable_staged_reset=true`；`staged_reset_ratios=[0.5,0.1,0.1,0.1,0.1,0.1]`；`staged_reset_max_samples_per_stage=200` |
| Reward（scale） | `walk_to_door 5`、`pregrasp_target_distance 6`、`a2_stage2_handle_center_y 6`、`a2_stage3_handle_creation 6`、`push_door_hinge 6`、`a2_stage3_unlatch_hold 3`、`a2_stage3_stage4_hold_and_drive 8`、`target_root_distance 12`、`complete 4`、`termination -1000`、`penalty_not_standing_still -15`、`penalty_upper_body_non_gripper_deviation_l1 -5`、`penalty_base_roll_pitch_l2 -2`、`orientation_control -5`、`penalty_undesired_contact -0.2`、`penalty_base_command_limit -1`、`penalty_dof_overspeed -0.1`、`penalty_delta_action_rate -0.01`、`penalty_dof_vel -0.001`、`penalty_dof_acc -1e-5`、`penalty_a2_stage4_arm_default_pose_l1 0`、`penalty_a2_door_body_contact 0`、`penalty_unused_dof_deviation_l1 0`；`rewards.reward_penalty_curriculum=false` |
| 物理 | physx position iters `4`、velocity `2`；`control_decimation=4`（50 Hz 控制，200 Hz 物理）；`max_depenetration_velocity=300`；`robot.asset.self_collisions=0` → 运行时 `enabled_self_collisions=True`（`isaacsim.py:1293`） |
| v28 要改的 | `robot.asset.usd_file="A2_Piper/a2_piper.usd"`；`default_joint_angles.arm_j4=0.25`、`arm_j5=0.5`；`body_names`（27→28，加 `wrist_camera_tower`） |

配方继承链：`base_v27_SC_*` → `base_v27_common` → `base_v26_7_common` → `base_v26_6_waveB_B0` → `base_v26_4_C0_CANONICAL_OFF` → `base_v26_4_bilateral_grasp_foundation` → `base_v26_lr_policy_continuation` → `base_v26_common_scratch_lr`（独自携带 `override /rewards: wbmanip/reward_door_open_a2_v26_acquisition`）。load-mode、夹爪增益、`num_total_batches` 在多达七层被改写；`base_v27_SC_*.yaml` 至今未跟踪（D-15）。

### 2.3 新 asset（`a2_piper_vpiper_final_20260906`）

- 与当前 asset 相比：27 个共享 link 的 inertial/collision/visual 元素与 mesh SHA 全部 bit-identical；26 个 joint 名称、顺序、限位一致；唯一运动学变化 `arm_j0` 原点 z `0.154 → 0.147431554755`（臂座下移 6.57 mm）。
- 新增三个固定 link：`vpiper_main` 0.310684 kg、`vpiper_support` 0.105624 kg、`metal_plate_5mm` 0.3375 kg（合计 +0.7538 kg，整机 45.4948 kg），均为材料估算值（`config/mass_properties_to_complete.json`），带 convex 碰撞 mesh；无任何 camera frame。
- 训练只加载 `robot.asset.usd_file`（`isaacsim.py:1261-1262,1307-1312`；URDF 路径是注释掉的死代码；`sim_type: isaacgym` 是无人读取的死字段）。USD 内嵌 mesh，`a2_piper.usd` 只引用 `configuration/*.usd`，两者必须一起移动。
- body/dof 合同按**名称**选择（`isaacsim.py:2370-2374` `find_bodies(config.body_names, preserve_order=True)`），`num_bodies=len(body_ids)`，断言 `isaacsim.py:2430-2435` 对 30 体 articulation 成立；contact sensor 覆盖全部 body（`isaacsim.py:1577-1582`），经 `contact_to_body_idx` 按名映射。仓库内无按整数位置索引机器人 body 的执行路径（`isaacsim.py:791-804` 的 `disable_gravity_for_arms` 分支未启用）。
- 整机 CoM（trunk 系，STATIC）：旧 asset/旧姿态 (0.0020, 0, 0.0099) → 新 asset/旧姿态 (0.0042, 0, 0.0113) → 新 asset/新姿态 (0.0041, −0.0003, 0.0130) m。
- 自碰撞：运行时 `enabled_self_collisions=True`，importer 只过滤父子对；`arm_body0`–`metal_plate_5mm` 在两种 reset 姿态下都是**零间隙接触对**（臂座平放板顶），无内部穿透；其余臂–mount 对 ≥5.0 mm。`arm_body0` 在 `penalize_contacts_on` 内，`penalty_undesired_contact` 阈值 |F|>1 N；固定关节约束力理论上 ≈0，必须在 G0 R2 中测量。
- 884 组臂构型扫描：新 asset 相对旧 asset 只多 4 组穿透（j2≥1.57 且 j3=0 时夹爪扫入板/主件）。

### 2.4 相机安装包（student worktree，`Vpiper-Plate-Dual-D435i`）

- 三台 D435i 实机 SDK 内参/外参已导出（`d435_native_calibration/20260907/`）；`NativeD435Rig` 的 world-pose 缺陷已于 2026-09-08 修复并验证；只存在于 student worktree，主仓库无相机渲染代码。
- U3_F0：base_left/base_right 父体 `trunk`，xyz `[0.025, ±0.155, 0.19]`，rpy `[0, −32, 0]` / `[0, −12, 0]`（**上仰** 32°/12°）；wrist 父体 `arm_body6_to_gripper`，xyz `[−0.000143, 0.179316, 0.015677]`，rpy `[−0.0067, −85.0036, −89.9475]`，参考姿态下光轴水平前视。塔 = foot + upright 0.132 m + head，相机中心离法兰 180 mm。
- 近场几何：TCP（F+Z 0.085）在 F0 下位于腕机光轴下 66.1°；两台 base 相机因上仰看不到 4 m 内地面。
- `robot/a2_piper_U3_F0_clearance_only.urdf` 已建在新 30-link asset 上：trunk 加 8 个、法兰加 4 个碰撞盒（foot 40×4×24、upright 8×8×132、short head 8×8×16、saddle 22×80×4 mm）加 3 个 25×90×25 外壳盒；倾角变化需用 `code/reproduce.py`（`reference_down_pitch_B_deg`）重生成，不能手改。安装包的参考姿态是 `[0,0,0,0,0,1.57]`，v28 的 θ 定义为**相对法兰 F**。

### 2.5 相机几何计算（COMPUTED；`planner_evidence_20260909/camera/`、`tilt_sweep_outputs/`）

倾角与取景（针孔 + Min-Z）：

| θ | TCP 入 RGB / depth | 法兰轴线可见窗口 RGB / depth | 行走 j5（光轴 −15°） | Stage2 腕机 RGB 把手 | Stage3 腕机 RGB / depth 把手 |
|---:|---|---|---:|---:|---|
| 40° | 否 / 是 | 0.105–0.44 / 0.075–0.645 m | −0.44 rad（−14.7°） | 79% | 12% / 98% |
| 45° | 是（v=0.99）/ 是 | 0.085–0.355 / 0.06–0.49 m | −0.52 rad（−15.2°） | 99% | 45% / 100% |

射线遮挡核查（真实 link7/link8/gripper_base mesh，160×90 → 212×120 网格，θ∈{35,40,45}，开度 {0,20,35} mm）：**倾角只改取景，不改遮挡**。塔架在 F+Y 即手指开合轴，相机到 TCP 的视线在 z_F≈0.068 处穿过上指外侧面，TCP/把手条中心在任何 θ、任何开度下都被 `arm_body8` 遮挡；只有把手条伸出 56 mm 指宽之外的两端可见（开度 0 / 20 / 35 mm：52% / 29% / 24%）；指垫 0–8%，上指尖外侧面 13%，下指尖 0–1%。要在上指之外看到 TCP，塔架需沿 F x 侧移 ≥0.108 m（开度 20 mm）/ ≥0.081 m（35 mm）。设计包络的 `wrist_u3_upright` 会进入 depth 画面右下角（θ40 3.7%、θ45 6.7%；RGB 0%），gripper 底座位于 depth Min-Z 0.105 m 之内（θ40 5.0%、θ45 8.9% 像素）。

三机覆盖（v27 轨迹 C_S2/C_S21 双侧 + 新 reset 姿态合成 Stage0/1）：对称 base 消除现方案在 RIGHT 门的观测缺口（Stage3 base_left depth 把手 53→100%、RGB clear 12→85%）；15° 相对 12° 在 LEFT 门 Stage4 多 +13 pp depth 把手（74→87）、+9 pp RGB clear、+16/17 pp 门框，在 RIGHT 门差 ≤2 pp，Stage0–2 相同。base 相机在所有变体下都看不到门口地面/门槛（下缘 −14°～−17°，地面从 ≥2.2 m 起可见）。行走姿态下腕机 RGB 在 0.8–1.5 m 看到把手 89–100%、把手侧门框 89–100%；腕机 depth 在 1.5 m 处看到门口地面 100%。左右门镜像差（80 项指标均值）：现方案 10.3 pp、B12 10.5、B15 9.6；相机导致的不对称项（铰链侧 depth 把手 100/53、门楣 0/88）在对称方案下消失，剩余差来自两侧轨迹的臂遮挡差异。

塔架–门板间隙扫掠（clearance-only 包络 5 mm 采样，门按 trace 铰链角与逐 env 拟合门宽 W p50 0.957 重建）：

| lane / stage | 门板最小 / p5 间隙（mm） | 门板穿透帧份额（F0 / F40 / F45） |
|---|---|---|
| C_S2 LEFT Stage3 | 56 / 74 | 0 |
| C_S2 LEFT Stage4 | −20 / 40 | 3.7%（释放后臂扫过门板） |
| C_S2 RIGHT Stage3 | 27 / 56 | 0 |
| **C_S2 RIGHT Stage4** | **−20 / −20** | **65.7 / 64.5 / 64.2%** |
| **C_S21 RIGHT Stage4** | **−20 / −20** | **41.7 / 41.5 / 41.3%** |

诊断：RIGHT 门 Stage4 穿透发生在**握把期间**（handle–TCP p50 0.029 m，128/128 与 62/63 env，终止 `complete`），`arm_j5` 顶在 1.22 rad 限位、法兰轴向下扎进门板约 39°，塔架轴（F+Y）有 0.62–0.85 的 x 分量朝向门板，外壳/鞍座/立柱在离铰链 0.57–0.85 m、z≈1.0 m 处穿板。θ 只改变外壳绕自身中心的转动，对间隙影响 ≤3 mm。法兰离门板 0.13 m 时塔架倾斜的 x 分量需 < ≈0.54（≈33°）。

### 2.6 当前 Teacher 的相机平台运动与 reward 收入结构（v27 trace，INSPECTED/COMPUTED）

Stage2 腕机角速度 p50/p95 ≈ 84–112 / 159–211 °/s；Stage3 71–89 / 228–403 °/s；方位反向 2–4.8 次/s；Stage5 有 3–39% 帧 q6 偏离默认 >0.3 rad。**Stage3 下压时 j6 |dq| p50 2.95–3.00 rad/s，贴着 3.0 rad/s 的关节速度上限**。现有四项平滑惩罚合计只占各 stage 收入的 1–3.5%，`penalty_dof_acc` 用最后一个物理子步（1/200 s）的有限差分、被接触瞬态主导。Stage4 释放后无双指接触的步（LEFT 5895 / RIGHT 1019）臂 L1 偏差 p50 7.1/8.4 rad、腕 Σdq² 11–19、无回位激励。

### 2.7 A2_Base locomotion 底座（INSPECTED/COMPUTED；`planner_evidence_20260909/locomotion/`）

- 接口：54 维 × 30 帧 = 1620；`[39:44]` 物理指令 × `[2,2,0.25,1,1]`（trainer 在最后一帧覆写为当前 Teacher 指令，`ppo_trainer_a2_base_api.py:3455-3484`）；**`[44:50]` 目前恒为零**（`a2_base.py:1391-1398`）；指令 = `[vx, vy, yaw_rate, body_pitch, body_roll]`，速度裁到 ±0.5、pitch/roll 裁到 ±0.4 rad；`leg_action_scale 0.25` 断言等于 `robot.control.action_scale`。
- 训练分布（LMP Stage1 `2026-06-05_16-12-09` iter 2000）：臂固定在 hold 姿态 `[0,1.48,−0.63,−0.84,0,1.57]`；trunk 质量随机 +[0,5] kg、trunk CoM ±0.1 m、夹爪 +[0,0.2] kg、pitch/roll ±0.4、推扰 ±0.3 m/s；与 DoorDog 同 asset（URDF SHA 相同）、同 0.02 s 控制周期。v28 的 +0.754 kg 与 ≤2.2 mm CoM 变化在该分布内一到两个量级。
- 跟踪证据：Teacher 在 Stage3–5 把 vx 钉在 +0.5 裁剪值的 ≈100% 步，pitch 在 ±0.4 的 19–61% 步；门接触下 vy/yaw 几乎不被实现（斜率 ≈0）；自由行走（R30 Student Stage0）实现/指令斜率 ≈0.5；base 类惩罚占负收入 22–29%、正收入 8–12%。sim2sim r22 `BASE_GAIN_CAUSAL`（stage0–2 前向增益 0.7 → st5 30→61，p=3e-4）说明 stage5 到达对 base 实现 stage0–2 指令的方式敏感，但那是 plant/gain 失配，不是 policy 比较。
- 候选新 A2_Base：LMP `44:50` 改为 TCP 球坐标 `[l, pitch, yaw, 0,0,0]`（TCP 偏移 0.105，球心 (0.145, 0, 0.704) 世界固定），当前只做过语法检查、未训练；Stage2 导出器写 `.npz`（非 TorchScript）；metadata 与 `contract.md` 仍写旧常量 0.135/0.687；DoorDog 行走相与 v28 姿态的 TCP 球坐标（l 0.14–0.33、p≈1.07–1.15）落在 Stage2 arm-goal 采样盒（l ≥ 0.4、p ≤ 1.0）之外 97–100%。

---

## 3. 相机几何合同（Q_G 的一部分）

### 3.1 冻结项

| 项 | 值 | 备注 |
|---|---|---|
| 腕机塔（C_T） | 沿 F+Y 直立，相机外壳中心离法兰 **140 mm**（D-35）；支架截面 90×25 mm（D-19），支架长按 D-20 规则重算（安装端按原 gripper 碰撞表面定位、1 mm 静态间隙）；E_T = 该设计的支架盒 + 外壳盒 | 侧移塔架（F x ≥ 0.08–0.11 m）登入 X-01 |
| 腕机 mount 倾角 θ（C_T，因外壳盒姿态属包络） | **38.76°**（D-35；140 mm 塔高下保持 TCP 投影行位置的名义值），绕外壳中心（图像 x 轴）就地向 gripper 方向；新出 `U3_F39_H140.json`（由 `v28_camera_geometry.py build` 生成，安装包 `reproduce.py` 不适用） | 相对法兰 F 定义；近场门在 140 mm 下 PASS（把手条两端 depth 29%/48% @开度 0.013/0.035），120 mm FAIL（19%） |
| 行走/reset 姿态（C_T） | `[0,0.10,−0.10,0,−0.415,1.57]`（θ=38.76） | 行走时腕机光轴 −14.9°；法兰上仰 28.8°；j2/j3 离软限位各 0.02 rad（D-03a） |
| base 相机（布局 C_S，包络 C_T） | 单中置 vs 双 ±0.155 **蒸馏前决定**（D-06/D-33）；Teacher 的 trunk 包络 = 两布局并集（双 ±0.155 支架/外壳盒 + 中置 `[0.025,0,0.19]` 外壳盒，均按上仰 15° 生成）；若双相机则对称 15° | 支架开印前必须定；单中置的几何推荐见 `planner_evidence_20260911/camera/REPORT.md` §3 |
| 近场需求（改写） | 开度 0.013（把手半径）与 0.035 m 下，把手条两端在腕机 depth 中可见 ≥ 20% 长度；上指尖外侧面在 depth 可见 ≥ 10%；RGB 份额报告 | “TCP/指垫入 RGB”几何上不可达，不作要求 |
| 前视/地面需求 | 行走姿态下：把手在 0.8–1.5 m 入腕机 RGB ≥ 75%、把手侧门框 ≥ 75%；depth 地面起点 ≤ 1.5 m | 上界指标 |
| 自遮挡预算（C_S） | depth 画面中自身支柱与 Min-Z 内像素预算按 140 mm/38.76° 包络在 G2-C1′ 重算；实 CAD 核查后更新 | 仿真渲染必须包含支柱 visual，避免域差 |

### 3.2 G0 离线验收（不占训练 GPU）

| ID | 内容 | 工具 | 通过判据 / 分支 |
|---|---|---|---|
| G2-C1（原 G0-C1，后移到蒸馏前） | 射线遮挡核查在开度 {0, 0.013, 0.020, 0.035} 下对 140 mm/38.76° 复跑（规划期 COMPUTED 已 PASS：`planner_evidence_20260911/camera/REPORT.md` §2.3） | `planner_evidence_20260909/camera/t1_occlusion.py` 与 `planner_evidence_20260911/camera/w4_tower_height_occl.py` | 按 §3.1 近场需求 |
| G2-C1'（原 G0-C1'，后移） | 真实支架 CAD 尚未设计，按 D-18 记 `NOT_RUN`；当前重算 D-19 仿真长方体的 depth/right_ir 自遮挡 | 同上 | 仿真仍报告 §3.1 自遮挡预算；实 CAD 判据留待硬件设计后，不能把当前包络结果称为 CAD PASS（修改：-codex worker；依据：-owner） |
| G2-C2（原 G0-C2，后移到蒸馏前，届时含单/双 base 相机两种布局） | 三机覆盖表复算：{θ45,θ40}×{B15,B12}，Stage0/1 用新 reset 姿态、Stage2–5 用 v27 轨迹 | `t3_coverage.py` + `t3_aggregate.py` | 选定组合满足 §3.1 前视/近场指标；LEFT/RIGHT 相机导致的覆盖差 ≤ 5 pp |
| G0-C3 | 塔架包络沿 v27 Stage2–5 轨迹对门板/把手/门框扫掠（已完成，结论 FAIL：RIGHT 门握把期穿板） | `t4_clearance.py` | 结论已用于 D-07；v28 Wave A 后用 v28 轨迹复跑，判据：Stage2–4 门板 SDF ≥ 20 mm 于 100% 帧、门框 ≥ 20 mm、Stage5 仅允许释放后臂收回前的接触 |
| G2-C4（原 G0-C4，后移） | Student lane 用已修复 `NativeD435Rig` 对 ≥8 集 v27 episode 重放渲染（含支柱 visual），出遮挡后的 `handle/pair/door_edge` 可见率 | student worktree | 报告项；作为 §6.4 几何指标的渲染真值对照 |

### 3.3 交付给硬件与 Student lane 的数值（按 D-30 分两段）

**3.3a 训练前（C_T，交硬件 lane 的包络约束）**：腕机支架 90×25 mm 截面、外壳中心离法兰 140 mm、θ=38.76°、支架长按 D-20 规则；最终支架 + 外壳必须 ⊂ E_T（SDF ≤ −3 mm），质量 ≤ 训练值、质心距 F 原点 ≤ 训练值、主惯量逐项 ≤ 训练值；base 相机支架/外壳必须 ⊂ trunk 并集包络。这些约束与 E_T 的 F 系盒参数由 G0 写入 `g0_decision.json` 并登入决策日志。
**3.3b 蒸馏前（C_S，交 Student 与硬件 lane）**：base 相机单/双与上仰角（D-06）、成像意义上的 θ/塔高确认、支架开印数值（`U3_F39_H140_*.json` 的 `T_F_M`/`T_F_support`，不用口语值）。Student lane 的 `load_d435_native_rig` 目前硬检查 `plan_id == "U3_F0"`（`d435_native_calibration.py:96-99`），需显式改为接受新 `plan_id` 并保持 fail-fast；其 rig 的 asset 路径同步到新 USD。

---

## 4. Asset 切换合同

### 4.1 配置层

- 新建 `gr00t/rl/config/robot/A2_Piper/a2_piper_vpiper.yaml`（复制 `a2_piper.yaml`，改 `asset.usd_file/urdf_file` 指向 **MERGED 候选** `a2_piper_v28_merged_20260909/`（D-34；mount 并入 trunk，28 native 刚体）；`default_joint_angles.arm_j2=0.10`、`arm_j3=−0.10`、`arm_j4=0.0`、`arm_j5=−0.415`；`body_names` 追加 `wrist_camera_tower`（28，与 native 计数一致）；`dof_names` 不变），经 `override /robot: A2_Piper/a2_piper_vpiper` 选择；保留 `/robot: A2_Piper/a2_piper` 组名（`test_a2_student_distillation_contract.py:72,173` 断言该组名）。
- `base_v28_common.yaml`：**扁平冻结**，显式声明 §2.2 全部 ablation 级键 + `defaults: [override /rewards: wbmanip/reward_door_open_a2_v26_acquisition, override /robot: A2_Piper/a2_piper_vpiper, _self_]` + §6 的 bundle 键。验收：CPU compose 后与 `wave_c_contract.json` 的 SC_S201 `resolved_contract` 做 diff（排除 WORKFLOW_KEYS；`robot.*` 与 `env.config.robot.*`、`rewards.*` 与 `env.config.rewards.*` 两份副本都比），差集必须等于预注册 allowlist：seed/标签、asset 路径、`body_names`、`default_joint_angles.arm_j4/arm_j5`、§6 bundle 键、（若路由）K 块。
- cell 文件 `base_v28_A_S281/S282/S283.yaml`（只含 `v26_cell`、`seed`、`a2_v26_side_permutation_seed`、`checkpoint: null`、`full`、`policy_only_load_actor_rms: false`）与 `base_v28_G1_WARM.yaml`；eval overlay `base_v28_eval_natural_start.yaml`（`enable_staged_reset false`、`reward_penalty_curriculum false`、`a2_v26_8_penalty_driver null`）。cell 文件由 `v28_verify.py materialize` 生成并**在 launch 前提交**。
- 回滚（仅配置）：`usd_file/urdf_file` 指回 `A2_Piper/a2_piper.*`，`arm_j2/j3/j4/j5` 恢复 0/0/0.25/0.5，`body_names` 恢复 27；不删除旧 asset 目录。

### 4.2 碰撞体与质量

- **腕机塔架与外壳**：按 D-19，用 `v28_camera_geometry.py build` 生成截面 90×25 mm 的单个长方体支架与 D435i 外壳盒，作为独立固定 link `wrist_camera_tower`（父体 `arm_body6_to_gripper`，fixed joint）。使用 `v28_build_asset.py` 写入 `<collision>`、对应 visual 与 `<inertial>`（塔 + D435i 总质量暂估 0.15 kg；空心安装件的外包络不等于实心材料体积）。安装包 `reproduce.py` 只生成 F0/F15，不能直接生成 F45/B15；v28 生成器显式使用选定角度。理由：`penalty_undesired_contact` 的 A2 路径要求 `penalize_contacts_on` 严格等于 20 体元组 `A2_PENALIZED_CONTACT_BODY_NAMES`，且把门板接触排除；塔架–门板接触必须单独建体并用 §6 的专用惩罚。（修改：-codex worker；宽支架方案依据：-owner）
- **base 相机支架与外壳（并集包络，D-06）**：并入 `trunk` 的 `<collision>`：双 ±0.155 布局的 8 个支架盒 + 2 个外壳盒（按 15° 生成）**加**中置 `[0.025, 0, 0.19]` 的 1 个外壳盒；不新增 body；接触归于 trunk，沿用现有 body-panel 与 undesired-contact 语义。最终只装一种布局时按 D-30 的 containment 判据核对（最终盒 ⊂ 并集）。
- **MERGED 语义（D-34）**：`vpiper_main/support/metal_plate` 并入 trunk（精确复合惯量，trunk 19.651→20.405 kg）；mount 接触归 trunk；`arm_body0`↔mount 成为被 importer 过滤的父子对，D-021 的板 5→4 mm 修正不再必要（保留亦无害）。
- **塔架按 D-35 重生成**：140 mm 外壳中心高度、θ=38.76°，支架长按 D-20 规则（安装端按原 gripper 碰撞表面、1 mm 间隙）重算；质量/质心/惯量按新几何重算并登记为估算。
- USD 用 README 命令重生成：`convert_urdf.py <urdf> <usd> --headless --device cpu --joint-stiffness 0.0 --joint-damping 0.0`（不传 `--merge-joints`，固定 link 保留；`convert_urdf.py:42-47,110`）；`validation/usd_import_readback.json` 更新并入 source lock。visual 也要包含塔架与外壳（Student 渲染的域一致性）。
- 不改 `self_collisions`。MERGED 的 G0 R2 若仍有 >1 N 异常接触，STOP并保留读数交Owner，不做板高或其他几何修正。D-021既有4mm板碰撞可保留。修改：-codex worker；依据：-owner（2026-09-11明确指令）。

### 4.3 G0 静态与 runtime 门（asset 部分）

| ID | 内容 | 判据 |
|---|---|---|
| G0-A1 | MERGED 28 links/20活动关节；与同一140mm新几何的独立体输入比较复合惯量：全机质量差0、COM/完整惯量张量误差≤1e-16级；保留关节与mesh采用字节比较。USD浮点读回误差单独记录，不套用URDF双精度阈值。修改：-codex worker；依据：-owner（2026-09-11 D-34/D-35） | 复合惯量等价receipt与USD readback |
| G0-A2 | `body_names` 28 ⊂ USD link；`dof_names` 20 同序；USD 根 + `configuration/*.usd` 存在；readback rigid_body_count 与期望一致 | 同上 |
| G0-A3 | reset 姿态在 `dof_pos_*_limit_list` 内、等于冻结合同；`penalty_unused_dof_deviation_l1==0`（锚点 `resting_dof_pos` 陈旧） | `test_a2_v28_config_contract_default_posture` |
| G0-A4 | convex 间隙回归：reset 姿态无内部穿透（含塔架 link 对臂/夹爪/mount） | `mount_clearance_check.py` 逻辑入测试 |
| G0-A5 | 修正 `test_a2_v15_dynamic_reachability.py:770-773`（读旧 URDF 路径，切换后陈旧通过）为读取 resolved asset；`A2_M23_SELF_COLLISION_BODY_NAMES` 相关测试改为“27 名为 resolved 列表的前缀/子集” | 测试改动 |
| R1 | 64 env / 5 batch smoke：`simulator.num_bodies==28`、`body_names==config`、`contact_sensor.num_bodies==28`（MERGED native 计数）、`dof_names` 同序 | 现有断言 fail-fast |
| R2 | reset 后零指令站立 50 步：`arm_body0`/`trunk`/`arm_body1..6`/`wrist_camera_tower` 接触力范数 max < 1 N；Stage0 门接触前 `penalty_undesired_contact` 与 `penalty_a2_wrist_tower_contact` 均值 == 0 | MERGED异常接触则STOP交Owner，不改几何（修改：-codex worker；依据：-owner，2026-09-11） |
| R3 | 零指令稳定 1 s 后检查 50 个控制步：臂 `abs(dq) < 0.5 rad/s`；root z ∈ [0.45, 0.51] m | 旧 asset 基线站立 z p50=0.4745 m，原高度区间不成立；修改：-codex worker；依据：-owner（2026-09-09 明确批准） |
| R4 | 见 §5.2 G0-L（locomotion 门） | — |
| R5 | reset 时 `arm_body6_to_gripper` z − root z ≈ **0.424514 ±0.01 m**（j5=−0.415 冻结姿态/新 URDF FK；旧值 0.432637 对应 j5=−0.52）；Stage0/1 收入读数用于冻结 §6.3 的 W[0]、W[1] | 记录；原 0.40 m 预测未同步 D-03a 姿态；修改：-codex worker；依据：-owner（2026-09-09 明确批准） |

---

## 5. 姿态、动作零点与 locomotion 底座

### 5.1 姿态

`default_joint_angles` 同时决定 reset 关节位置（`door_open_a2_base.py:29234-29247`）、动作零点（`legged_robot_base.py:1150-1151`、`a2_base.py:596`）、`dof_pos` 观测零点（`legged_robot_base.py:2328-2331`）、Stage0/5 与 Stage4 姿态惩罚锚点（`8484-8510`）以及 Stage0→1 的 `a2_stage0_arm_default_max_deviation=0.1` 门。只改 yaml 即全部重定向；staged reset 与恢复 bank 是 per-run GPU 张量，不跨 run 携带旧姿态。

冻结姿态 `[0, 0.10, −0.10, 0, −0.415, 1.57]`（D-03/D-03a/D-35）：TCP 在 trunk 系 (0.270, 0.465)，世界高约 0.95 m（trunk 0.48）；法兰 z 0.4245；腕机光轴 −14.9°（θ=38.76）；gripper 上仰约 29° 行走。j2/j3 各离 0.95 软限位 0.02 rad，reset 姿态不再触发 `limits_dof_pos`。G0-A3 断言该向量并核对 `dof_pos_*_limit_list`。

### 5.1a 累积动作目标夹紧（D-17，已批准）

现状（INSPECTED，两分支 `delta_action_base.py` 字节相同）：`_delta_actions += raw·0.3`，`clamp(±delta_action_clip=15)`，臂目标 `default + 0.25·d`（`delta_action_base.py:59-66`；`legged_robot_base.py:1150-1151`）。±15 对应 ±3.75 rad，超过每个臂关节的半程；目标一旦越界，PhysX 把 q 压在硬限位，`limits_dof_pos` 按 q 计算封顶，策略要连续反向输出约 50 步才能把 d 拉回范围内，期间 q 与 reward 都不变。pull v7 P0/P1 已证明这是 release-ready 全为 0 的结构原因（j3 target 钉在 +3.75，Stage1 起 99% 步越界）；主线 v27 trace 的 Stage5 j2/j3 被饱和积分器钉在限位是同一现象（§2.6）。

实现（最小）：`DeltaActionBase.step` 在现有 clamp 之后、`_apply_delta_action_overrides` 之前，若 `config.delta_action_clamp_to_dof_limits` 为 true，则对臂索引逐关节 `d ← clamp(d, (l_j − default_j)/action_scale, (u_j − default_j)/action_scale)`（l/u 取 `hard_dof_pos_limits`，与 `_reward_limits_dof_pos` 同源；臂索引与默认角形状不符直接 raise）；键缺失或 false 时路径 bit-identical。观测 `actions` 的臂 6 维仍是夹紧后的 d，策略看到的与执行的一致。影响：动作语义变化，只在 from-scratch 的 v28 两分支同时开启；`base_v28_common.yaml` 置 true。CPU 测试 `test_a2_v28_delta_action_clamp_to_limits`（越界 raw 序列下目标恒在范围内；键缺失时与旧行为逐元素相等）。G1 warm probe 同样在夹紧开启下运行（旧策略的饱和习惯会立即撞到夹紧边界，这是 probe 要回答的问题之一）。

### 5.2 A2_Base locomotion 底座（D-14）

**结论：v28 保留当前 A2_Base。** 依据见 §2.7：新 asset/新姿态没有把它推出训练分布；locomotion 质量确有价值（sim2sim `BASE_GAIN_CAUSAL`、自由行走斜率 ≈0.5、base 惩罚占负收入 22–29%），但候选 policy 尚不存在，且其新观测槽在 DoorDog 行走相是分布外的。

**G0-L（当前 A2_Base 在新 asset/新姿态上的验收门，GPU ≈10 min）**：扩展 `smoke_a2_base_flat_walk.py`（headless、`--num-envs 64`、`--usd-file <新 USD>`、`--arm-posture`、`--command-script`、`--metrics-json`；现版本要求 GUI cuda:0，`:180-185`），平地无门、臂 PD 保持。6 s 指令块、固定 seed：站立；vx 0.25；vx 0.5；vy ±0.25；wz ±0.5；vx 0.5 + pitch −0.32（Stage3 均值）；vx 0.5 + pitch ±0.4；roll ±0.2；C_S21 一条 lane Stage2–3 的 `physical_base_command` 逐步回放。姿态 {v28 默认、Stage1 hold、类 Stage2（l 0.6 / p 0.35）}。基线 = 同脚本在 v27 asset 上。通过：0 摔倒/64 env；各块 |e| p50 ≤ 基线 ×1.15；slope(vx@0.5) ≥ 基线 −0.05。未过 → 交 Owner（这是 asset 层面的 locomotion 兼容性问题，不是 v28 配方问题）。

**G0-L-swap（任何 A2_Base 替换的预注册验收）**：
1. 接口测试（CPU）：`torch.jit.load`；metadata `dog_frame_dim 54`、`history_length 30`、`flattened_dim 1620`、action 12、`leg_joint_names` 不变、`leg_action_scale 0.25`、`use_default_offset true`、`delay [0,1]`、latent 25、新增 `slot_44_50` 字段（`zeros` 或 `gripper_tcp_lpy_v1` + 训练时常量）；`zeros(1,1620)`→有限 `(1,12)`；`44:50` 写入器与 LMP 公式在三姿态（旧默认→(0.1956, 0.7238, 0.1594)；v28→(0.3325, 1.1530, 0)；hold→(0.3693, 0.3164, 0)）上误差 ≤1e-3。
2. 同 G0-L 脚本与 asset 上对比当前 policy：0 摔倒；各块/姿态 p50 与 p95 ≤ 当前；slope(vx@0.5) ≥ 0.8、slope(vy) ≥ 0.6、slope(wz) ≥ 0.7；v28/折叠姿态相对 hold 姿态退化 ≤ 20%（检验 `44:50` 分布外）；Teacher 回放块 p50 |e_vx| ≤ 当前。
3. 通过则作为 v28 的 opt-in 分支（一个额外 seed，同预算），或进入 v29；不通过则不进。
Owner 侧交付物：TorchScript `policy.pt`（`export_dog_policy.py` 自 Stage2 `checkpoints_dog`，或 DoorDog 增加 npz 加载）、`policy_metadata.json` 的 `gripper_position` 字段（训练时球心 xy/z、TCP 偏移、body、LMP commit）、Stage1/Stage2 迭代数、是否覆盖 TCP l∈[0.14,0.35]/pitch ≤1.15 rad 的说明；修正 `export_stage2_policy.py:319-320` 与 `contract.md` 的旧常量。DoorDog 侧改动清单见 `planner_evidence_20260909/locomotion/REPORT.md` §1。

---

## 6. Reward / telemetry 最小集（Q_V）

### 6.1 原则

新增两个独立小函数（腕部运动、塔架接触），其余为改 scale 或改门控；键缺失时默认路径 bit-identical（注册表在 `legged_robot_base.py:525-531,616-623` 丢弃零/缺失键）。不改 `penalty_dof_vel/acc/delta_action_rate/overspeed`（提高它们会税 Stage2 的 j2/j3 接近动作、接触瞬态或 σ=0.8 的探索噪声，而不是腕部行为）。

### 6.2 改动清单

| 键 | 旧 | 新 | 门控 | 依据 | CPU 测试 |
|---|---|---|---|---|---|
| `default_joint_angles.arm_j2/j3/j4/j5` | 0 / 0 / 0.25 / 0.5 | 0.10 / −0.10 / 0.0 / −0.415 | — | §3.1、D-03a、D-35 | `test_a2_v28_config_contract_default_posture` |
| `delta_action_clamp_to_dof_limits`（新 bool，D-17） | 无 | true | — | §5.1a | `test_a2_v28_delta_action_clamp_to_limits` |
| `penalty_a2_wrist_motion_l2`（新） | 无 | −0.4 | 逐 stage 权重表 | 唯一能只作用于 j4/j5/j6 且不税 j1–j3、不税 Stage3 j6 的杠杆 | `test_a2_v28_wrist_motion_raw_penalty_formula`、`_reversal_only_on_sign_flip`、`_stage3_j6_weight_zero` |
| `a2_wrist_motion_vel_weights`（新，6×3） | 无 | §6.3 | 按 `stage_buf` gather | Stage0/1/5 严、Stage2/4 中、Stage3 j6=0 | `test_a2_v28_wrist_motion_weights_contract_fail_fast` |
| `a2_wrist_motion_reversal_weights`（新，6×3） | 无 | §6.3 | 同上 | Stage3 只禁反向不限速 | 同上 |
| `penalty_a2_wrist_tower_contact`（新） | 无 | −1.0 | 全 stage | raw = (‖F_tower‖ > 1 N)；塔架对任何物体的接触都是硬件损坏风险；`penalize_contacts_on` 元组不可扩展（§4.2） | `test_a2_v28_tower_contact_raw_formula`、`_absent_key_bit_identical` |
| `penalty_a2_stage4_arm_default_pose_l1` | 0.0 | −0.5 | Stage4 ∧ `_a2_stage4_release_gate` ∧ ¬`both_contact` | 释放后臂 L1 7–8 rad 无回位激励；0.5·0.02·7.5=0.075/步，占释放后收入 25–37% | `test_a2_v28_stage4_post_release_mask` |
| `a2_stage4_arm_default_pose_release_gated`（新 bool） | 无 | true | — | false 时恢复现有 stage-only 门控 | `test_a2_v28_stage4_post_release_gate_false_is_stage_mask` |
| `penalty_upper_body_non_gripper_deviation_l1` | −5.0 | 不变 | Stage0/5 | 已占 Stage5 收入 17–39%；锚点自动重定向 | — |
| K 块 + `reward_penalty_reward_names` += `penalty_a2_wrist_motion_l2` | 无 | 仅当 Wave C `K_SCRATCH_SUPERIOR` | — | 否则 0.2 floor 下 Stage2 腕惩罚相对占比升 5×；塔架接触惩罚**不**进衰减名单 | `test_a2_v28_k_recipe_names_include_wrist_term`（分支） |

新函数规格：
- `a2_wrist_motion_raw_penalty(dof_vel_wrist, last_dof_vel_wrist, stage_buf, vel_weights, reversal_weights) -> (N,)`，raw = Σ_j Wv[stage,j]·dq_j² + Σ_j Wr[stage,j]·relu(−dq_j·dq_j,prev)；包装 `_reward_penalty_a2_wrist_motion_l2` 读 `simulator.dof_vel[:, idx]` 与 `self.last_dof_vel[:, idx]`（控制步频，`legged_robot_base.py:1372`），idx = `_upper_non_gripper_dof_idx[3:6]` 并断言名称 arm_j4..j6；表缺失或形状错误 fail-fast。
- `_reward_penalty_a2_wrist_tower_contact`：`(simulator.contact_forces[:, tower_idx, :].norm(-1) > 1.0).float()`，tower_idx 由 `body_names.index("wrist_camera_tower")` 求得，缺体则 fail-fast；不做门板排除。
- 测试沿用 `test_a2_v19_env_semantics.py:27-31` 的 AST 抽取模式，不依赖 IsaacLab。

### 6.3 权重表与校准（COMPUTED 自 C_S2 DEV trace；Stage0/1 收入为公式估计，G0 R5 后冻结）

单个腕关节持续 150°/s（2.618 rad/s）的每步代价 = 0.4·w·0.02·6.854 = 0.0548·w。

| Stage | Wv (j4,j5,j6) | Wr (j4,j5,j6) | 收入/步 | j4@150°/s 代价占比 | j6 占比 | 一次 2 rad/s 反向 |
|---|---|---|---|---|---|---|
| 0 | .35,.35,.35 | .5,.5,.5 | ≈0.08（估） | 24% | 24% | 0.016 |
| 1 | .5,.5,.5 | .5,.5,.5 | ≈0.12（估） | 23% | 23% | 0.016 |
| 2 | .75,.75,.75 | .5,.5,.5 | 0.288 | 14% | 14% | 0.016 |
| 3 | .5,.5,**0** | .5,.5,.25 | 0.565 | 4.9% | **0** | 0.016（j6@3 rad/s 一次 0.018） |
| 4 | 1,1,1 | .5,.5,.5 | 0.552 | 9.9% | 9.9% | 0.016 |
| 5 | 1.25,1.25,1.25 | .5,.5,.5 | 0.331 | 21% | 21% | 0.016 |

Stage3 核算：下压 j6 贴 3.0 rad/s 上限时新项为 0；一次“下压→释放”反向一次性 0.018，对比 `a2_stage3_handle_creation` ≈0.09/步；只有 j4 的 p95 尾部（4.1 rad/s，非下压关节）付 0.067/步（11.9%）。

### 6.4 Telemetry（report-only，进 reducer；FK 计算，不渲染）

来源：`arm_body6_to_gripper` 与 `trunk` 的 `body_pos_w/body_quat_w/body_ang_vel_w`（`articulation_data.py:1056-1076`）、`arm_joint_vel`、`tcp_to_handle_pos`、门板 `body_pos_w/quat_w`（`door_open_a2_base.py:10481-10494`）；相机光轴 `a = R(body_quat_w[flange]) @ T_parent_optical[:3,2]`；刚性安装相机的角速度 = 法兰 `body_ang_vel_w`（不做有限差分）。
字段（v27 命名风格，`_p50/_p95/_share` 后缀）：`wrist_cam_ang_speed_p50/p95_deg_s`、`wrist_cam_axis_sweep_p95_deg_s`、`wrist_cam_share_axis_sweep_gt_60`、`wrist_cam_axis_elev_p5/p50/p95_deg`、`base_cam_ang_speed_p95_deg_s`、`arm_j6_reversals_per_s`（阈值 0.3 rad/s）、`arm_j6_abs_dev_from_1p57_p95`、`arm_posture_l1_p50/p95_rad`（Stage0/5）、`post_release_return_time_p50/p95_s`（L1 < 0.5 rad）、`handle_in_wrist_depth_share_stage2_4`、`handle_in_wrist_rgb_share_stage2_4`（几何，SDK K 424×240、Min-Z 0.105）、`wrist_tower_panel_min_clearance_m`、`wrist_tower_contact_step_share`、`wrist_tower_contact_episodes_gt_5N`。
**朝向/可观测性遥测（2026-09-11 新增，report-only，为"是否需要朝向约束"提供证据，不加 reward）**：`handle_bearing_deg_p50/p95_stage0_2`（把手相对 trunk +X 的方位角）、`handle_bearing_gt_30deg_share_stage0_2`、`doorway_bearing_deg_p95_stage5`（门口中心相对 trunk +X）、`crossing_yaw_deg_p50/p95`（越门时 root 相对门法向的偏航；v27 为 12.5°/19.8° 中位）、`stage0_2_vy_cmd_at_clip_share`（Stage0–2 横向速度指令顶裁剪值的步份额）。预注册阈值留待 Wave A 第一个 milestone 读数后由 Owner 决定是否升级为 shaping 项（第五项 bundle）。

---

## 7. 统一评估合同

- 沿用 v27 §2：固定侧、`enable_staged_reset=false`、first-episode-only、`reward_penalty_curriculum=false`、`a2_v26_8_penalty_driver=null`、checkpoint-adjacent config、`full` load、exact N/side；**新增** `++experiment_dir=<eval artifact dir>`（D-16）。
- 计数与质量字段沿用 `v27_reduce.py`（D、S3+/S4+/S5+、open_hold、complete、`clean_complete`、hold_through、post_release_body_force_p95、first_crossing_hinge_p50、episode_length_p50、arm_j4_limit_residence、terminal_reasons、integrity）；trace 只对 `max_stage ≥ 2` 的 episode 强制（早期终止计入分母）；`v28_reduce.py` 新增 §6.4 字段与 `passes_gate` 复用；标准库 `json.load`。
- 门槛（D-32 拆层）：**Wave A 选种用 reachability 门**——每侧 complete ≥ 60、low_height+overspeed ≤ 2、`wrist_tower_contact_episodes_gt_5N ≤ 2`、`post_release_body_force_p95 ≤ 5 N`；**Wave B 资格用 64/128 样本合取门**——complete ≥ 60/120、`clean_complete` ≥ 56/112、终止 ≤ 2/4、塔架接触 ≤ 2/4。`clean_complete` 的 crossing hinge ≥ 1.0472 保留（D-10），并在每个 milestone 按分量（hinge / 身体接触 / 终止）分级报告。依据：v27 中可达性被 4/6 Wave C 格与全部 warm 格达到而合取门只 1/6 通过，且 hinge 分量单独否决了身体力为 0 的格。
- 安全门（新增，进 `passes_gate`）：`wrist_tower_contact_episodes_gt_5N` ≤ 2/64/侧（128 样本 ≤ 4）。
- 相机行为阈值（report-only，来源 v27 基线的一半）：Stage2 腕机角速度 p95 ≤ 105°/s、Stage4 ≤ 150°/s、Stage5 ≤ 90°/s、Stage3 ≤ 250°/s（下压地板 172°/s）；反向 ≤ 1.5/s（Stage0/5）、≤ 2.5/s（Stage2/4）；Stage0/5 臂 L1 p95 ≤ 0.5 rad 且 q6 偏离 >0.3 rad 帧 ≤ 5%；释放后回位 p50 ≤ 2.0 s、p95 ≤ 4.0 s → `CAMERA_MET / PARTIAL / UNMET`，v28 内不阻塞选种。
- 固定 eval seed：milestone `280001`、DEV `280101`、CONF `280201`、render `280303`；训练不读取任何 eval manifest。render：每候选每侧按预定 episode id 取 3 集，只做 QA。

---

## 8. 训练设计

### 8.1 G1：warm-start probe

cell `V28_G1_WARM`：checkpoint `logs_rl/by_batch/base_v26/v26_8_bilateral_opening_scaffold_decay_20260903_r3a/train/C_S2/model_step_003000.pt`，`policy_only` + `policy_only_load_actor_rms: true`，其余为完整 v28 配方（MERGED新asset/140mm塔架、新姿态、D-17夹紧、bundle、§8.3 K块；修改：-codex worker；依据：-owner，2026-09-11），seed 281，500 batches，save 250/500，step500 双侧 exact64。约 3.1 h + 15 min。
预注册规则：`WARM_PASS` ⇔ 双侧 D ≥ 40/64、clean ≥ 36/64、终止 ≤ 2、塔架接触 ≤ 2 → Wave A 追加一个 warm arm（seed 281）；`WARM_PARTIAL` ⇔ 双侧 S4+ ≥ 32/64 但 D < 40 → 延长一次到 1000 再判；否则 `WARM_FAIL` → STOP交Owner（修改：-codex worker；依据：-owner，2026-09-11明确指令）。若 Wave C step1000 数据存在且 D(warm,500) < D(最佳 SC seed,1000) − 4（任一侧），warm arm 取消。

### 8.2 Wave A：from-scratch 3 seed（Q_S、Q_V）

cells `A_S281/A_S282/A_S283`：`checkpoint: null`、`full`、4096 env、6000 batches、save 250、milestones 1000/2000/3000/4000/5000/6000 各双侧 exact64 natural（nominal 单层，`RECIPE_B=current`）。
路由（endpoint 6000）：`REACH_3SEED`（3/3 seed 双侧过 **reachability 门**（§7，D-32））/ `REACH_SEED_UNSTABLE`（1–2/3）/ `REACH_NOT_ESTABLISHED`（0/3）；选种 = 最早在双侧过 reachability 门的 milestone，并列取最小 seed，并列仍相同时取 `clean_complete` 双侧和更高者；无过门 seed → Wave B `NOT_RUN`。`clean_complete` 分量与相机行为标签独立并列报告，不参与选种；Wave B 的资格门仍是合取门。
**硬件反馈分支（2026-09-11 收窄）**：若 `REACH_NOT_ESTABLISHED` 且失败集中在 RIGHT 侧、伴随 `wrist_tower_contact_step_share` 高或 Stage2→3 停滞，closure 必须写明“**训练所用包络 E_T**（截面、外壳中心高度、θ 按 §3.1 冻结值）与 RIGHT 门抓握不兼容”的证据。该结论只指控 E_T，不指控任何几何上被 E_T 包含的更小最终安装件，也不构成对其他塔高变体的负面证据；X-01（侧移塔架）升级为硬件决策请求；不追加预算。
**蒸馏前 eval-time 安装件交换检查（D-030 生效时新增）**：选中的 Teacher checkpoint 在**只换 asset 的 eval overlay**（`robot.asset.usd_file/urdf_file` 指向带最终安装件包络的 asset；link 拓扑与 `body_names` 不变；其余按 §7 合同 + `++experiment_dir`）上做 LEFT/RIGHT exact64。通过判据：`wrist_tower_contact_episodes_gt_5N ≤ 2/64/侧`、`wrist_tower_contact_step_share ≤ 训练包络读数 + 0.01`、complete/clean 不低于 §7 的 64 样本门。产出 `g2_mount_swap_decision.json`，typed outcome `MOUNT_SWAP_OK / DEGRADED / FAIL`。E_T 上失败但交换检查通过 → “E_T 过保守”，可继续蒸馏；交换检查失败 → 指控最终安装件，回硬件决策，不得改阈值。交换同时改变塔架质量/惯量，receipt 显式记录，归 RUNTIME 证据。

### 8.3 Wave C 条件路由（预注册）与实际触发（2026-09-11）

| Wave C 读数 | v28 动作 |
|---|---|
| `SCRATCH_3SEED_ESTABLISHED` | Wave A 三 scratch seed；G1 可选 |
| `SCRATCH_SEED_UNSTABLE` | 三 scratch seed；G1 **必做**；预留第 4 个 seed |
| **`SCRATCH_NOT_ESTABLISHED`（实际）** | **G1 必做；G1 失败则 STOP 交 Owner** |
| **`K_SCRATCH_SUPERIOR`（实际）** | **配方加入 scaffold-decay K 块**（见下） |
| `K_SCRATCH_NONINFERIOR / INFERIOR / UNRESOLVED` | 不含 K |
| Wave C endpoint 在 v28 launch 时缺失 | 按 `UNRESOLVED`：不含 K，scratch 先验记 UNRESOLVED，G1 必做 |

**K 块落地合同（由 `base_v27_SK_S211.yaml:14-45` 逐键取，INSPECTED）**：`env.config.a2_v26_8_penalty_driver = side_min_natural_stage_reach_rate`、`..._driver_target_stage = 4`、`..._driver_level_down_rate = 0.5`、`..._driver_level_up_rate = 0.7`、`..._penalty_curriculum_trace_enabled = true`；`rewards.reward_penalty_curriculum = true`、`reward_initial/min/max_penalty_scale = 1.0/0.2/1.0`、`reward_penalty_degree = −0.0001`、两个 legacy `*_ave_goal_reached_rate = null`；`reward_penalty_reward_names` = 原 16 项 + **`penalty_a2_wrist_motion_l2`**（17 项）。**不复制**该文件第 13 行的 `a2_v26_side_permutation_seed: 211`（seed 专属键，各 cell 用自己的 seed）。**排除** `penalty_a2_wrist_tower_contact`（安全项，衰减方向与 §7 安全门相反）与 `penalty_a2_stage4_arm_default_pose_l1`（只在释放后生效，与 16 项 scaffold 无同窗口占比问题，且是 v27 缺陷的矫正项；driver 由 Stage4 到达率驱动，放入名单等于"越常到 Stage4 矫正越弱"）。名单内任一项 scale 为 0 会在 init fail-fast（`door_open_a2_base.py:7996-8003`），消融分支必须同步删名。driver 的 trace 要求 `experiment_dir` 每个 attempt 唯一（`trace_path.touch(exist_ok=False)`，`:8026-8036`），与 D-16 的 `++experiment_dir` 约定联动。
**K 的具名风险（SK_S212 型）**：driver 只测 Stage4 到达率，不测完成；到达率 >0.7 时 scaffold 衰到 0.2 floor 而策略可能从不完成。v28 的塔架碰撞与新姿态会放大"到达 ≠ 完成"的落差。预注册具名失败 `K_REACH_WITHOUT_COMPLETE`：连续两个 milestone 双侧 S4+ ≥ 56 且 complete ≤ 4；driver trace（`a2_v26_8_penalty_curriculum_trace.jsonl`）是每个 milestone readout 的必看量。driver 备选（D-31，已批准）：保持 v27 已检验的 `target_stage=4`；若 `K_REACH_WITHOUT_COMPLETE` 在任一格触发且 §10 预留的第 4 个 seed 可用，则第 4 个 seed（`A_S284`）以 `target_stage=5` 启动，其余键不变，并在 readout 中与触发格配对报告；不因该触发停格或改已运行格的 driver。

### 8.4 Wave B：资格认定（Q_Q）

选中 seed 在选种 milestone 与 6000 各做 LEFT/RIGHT exact128 DEV（seed 280101）；DEV 过 128 样本门（含安全门）则 CONF（seed 280201）→ `BILATERAL_TEACHER_QUALIFIED_SIM_V28` 或 `QUALIFICATION_NOT_CONFIRMED`；产出 `scriptsFORhuman/v28/a2_piper_base_v28_teacher_candidate_manifest_<date>.json`（路径、字节比对记录、DEV/CONF、相机与安全指标、render 路径；D-022）。它不是 Teacher binding。

### 8.5 v28 与其他 lane 的接口

- Student lane（全部在蒸馏前，C_S）：base 相机单/双与上仰角决定（D-06）、新 rig JSON（`U3_F39_H140_*`）、新 asset、`plan_id` 检查更新、proprio 加夹爪 qpos 与 effort 代理（X-09）、G2-C1/C1′/C2/C4、eval-time 安装件交换检查（§8.2）；Wave B 后按候选 manifest 蒸馏。
- sim2sim lane：动作低通/延迟决定（X-10）；MuJoCo 侧 asset 与 54 维 A2_Base 观测构造同步。
- 硬件 lane：θ/base 角/支架（§3.3）、X-01。

### 8.6 Teacher/G7 binding 裁决建议（v27 closure 后）

建议维持 v23 单 RIGHT 绑定，不更新：v27.0 三候选无一双侧过 128 样本门（C_S2 clean 75/69；W_S2 仅 RIGHT 过、LEFT clean 100；K_S2 RIGHT 因超速 5>4 被否）；Wave C 只有 exact64 数据，两个预注册的 exact128 确认按冻结规则 `NOT_RUN`，不做 SK 替换、不挑中途 best；唯一过 64 门的 SK_S213@6000 是 1/3 seed 的单 seed 模拟结果，同族 SK_S212 双侧 complete=0。重审触发：v28 Wave B 产出 `BILATERAL_TEACHER_QUALIFIED_SIM_V28`。


---

## 9. 自主决策权与失败预案（继承 v27 §9，含修订）

1. policy 读数产生前的失败（基础设施、代理、资产、harness 断言、接线缺陷）：Codex Main 自主修复并重启，上限 2 次/格，只需通知；修复带 contract lock diff，实验合同零改动。
2. policy 读数产生后的非零退出：停该格、其余继续、不重跑、不等待。reducer 判 `INVALID` 只能停评估，不得自动停训练；训练停格需第二次独立重读或 Owner 确认（v27 R1 教训）。
3. milestone 读数只汇报不审批；typed outcome、RECIPE 选择与 wave 转换按预注册条件自动执行；启动下一 wave 前通知 Owner，未被否决即继续。
4. **watcher 对“已 active 的格”独立推进 milestone 评估**，不因任何格 pending 或等待 GPU 而整体挂起；聚合 reducer 等覆盖齐后再出。
5. **外部 GPU 占用是常态事实**：launch 前按实际余量选择 GPU（≥20 GB 空闲且无外部 compute 进程）并写入 receipt `resources` 与 `gpu_occupancy.json`；对外部进程只记录不处置；某格因无 GPU pending 超过 12 小时，通知 Owner 并顺延到空闲 GPU。
6. 默认分支：G1失败 → STOP交Owner（修改：-codex worker；依据：-owner，2026-09-11明确指令）；`K_REACH_WITHOUT_COMPLETE` 触发 → 第 4 seed 用 `target_stage=5`（D-31）；G0-L 未过 → STOP 交 Owner；MERGED asset 的 R2 仍有 >1 N 异常接触 → STOP 交 Owner（不再做板高修正）；G2-C* 与 base 相机布局 → 蒸馏前由 Student lane 与 Owner 决定。
7. 预授权四个本地 commit 点：G0 全部通过后（配置、robot yaml、asset 追加、harness、CPU 测试、smoke receipt）；Wave A step1000 reducer 后（训练 receipt 与首个 milestone）；Wave A endpoint 冻结后；Wave B 与 closure 后。不 push。
8. 必须等 Owner 的：改预注册阈值或路由；超出 §10 预算；改 reward/stage/loader 语义超出 §6 与 §5.1a；Teacher/Student/G7 binding、hardware、C_T 内的硬件几何（塔截面/塔高/θ 包络、trunk 并集包络）变更；A2_Base 替换；base 相机布局的最终选择（D-06）。
9. 向 Owner 提问后若 12 小时内无回复且 plan 有默认分支，按默认分支继续并记录。

---

## 10. 资源与时间

观测值：22.15 s/iter，39.5–41.8 h / 6000 batches / cell；exact64 lane 4.3–5.6 min；exact128 5.5–11.5 min；训练进程 ≈13 GB、评估 ≈3.2 GB。

```text
G0    : CPU 为主 + 一次 64-env/5-batch smoke（≤32 batch）+ G0-L 步行 smoke ≈ 30 min GPU
G1    : 1 格 500 batches + 评估 ≈ 3.5 h
Wave A: 3 格 × 6000 ≈ 42 h 各（计划 46 h）；6 milestones × 6 lanes ≈ 3.3 GPU-h
Wave B: 4–8 lanes exact128 ≈ 1.3 h；render ≤ 1 h
总训练上限：G1 500 + Wave A 18,000 (+ 备用 seed 6,000 + warm arm 6,000 + A2_Base opt-in 6,000) = 36,500 batches；另每 wave 一次 ≤32 batch 接线 smoke
```

GPU 事实（2026-09-09）：GPU0–3 外部占用（41 GB 各）；GPU4/5 Wave C 至 9 月 11 日上午；GPU6/7 Wave C 评估队列。G0 现在即可进行（CPU 为主；两个 smoke 在 GPU6/7 空隙或 Wave C 结束后）；训练在 Wave C endpoint 之后启动。任一格非零退出即停格保留证据：不重跑、不放宽阈值、不中途改 config、不追加预算。

---

## 11. 文档与 memory 管理（v28 强制项）

v28 是带大量取舍与待办的 re-baseline，记录纪律是交付物的一部分。

1. **决策日志**：本文件 §1 为 v0；G0 起以 `scriptsFORhuman/v28/a2_piper_base_v28_decision_log.md` + `runtime_logs/<run_id>/decision_log.jsonl` 承接（列：id、日期 HKT、决定、替代、证据路径、状态 PROPOSED/ACCEPTED/SUPERSEDED、重审触发）；每个 `wave_*_decision.json` 携带 `decision_log_id`；Codex 的自主决定同样入表。
2. **待办登记**：`scriptsFORhuman/v28/a2_piper_base_v28_deferred_register.md`（已建，X-01 起），列：id、来源决策、入场条件、归属 lane、`longterm_TODO_ref`；每个 commit 点把 open 项镜像到 `a2_piper_longterm_TODO.md` D 节、closed 项入归档。
3. **每 milestone readout**：`a2_piper_base_v28_wave_<w>_step<N>_readout_<date>.{md,json}`（`v28_readout.py`），新增相机运动、姿态、塔架安全段；readout 不改变 reducer 结论。
4. **权威决策 JSON**：`runtime_logs/<run_id>/{g0_decision,g1_probe_decision,wave_a_decision,wave_a_endpoint_lock,wave_b_decision,g2_mount_swap_decision}.json`，固定 schema（`schema, status, outcome, recipe keys, source_reducer, endpoint_lock, route_authority, selection_rule, frozen_at, decision_log_id`），先于 readout 写入。
5. **memory**：`memory/a2-piper/base-v28-camera-aware-rebaseline/{description,TODO,DONE}.md`（已建骨架，status `planned`）；G0 时在 `memory/a2-piper/MEMORY.md` 增加路由行、v27 entry 在其 closure 后置 `closed`。只写已验证事实与决策，不写 heartbeat。
6. **命令注册表**：`.ai/PROJECT.md` 只登记本机 receipt `state PASS` 的 v28 入口命令及日期。
7. **长期 TODO**：plan 冻结时已更新 R/A/D 节；closure 时再同步一次。
8. **证据等级标注**：所有 readout/closure 中的数字标注 INSPECTED / STATIC / TEST / RUNTIME / EXPERIMENT；几何上界（针孔无遮挡）与渲染验收分开写。
9. **规划者自省**：`scriptsFORhuman/v28/a2_piper_base_v28_planner_self_review_20260911.md`（S1–S10 弱点清单与让出项去向），供第三方审计交叉判断；审计结论回写决策日志。

---

## 12. 实现范围（最小充分）与交付物

实现：
1. `gr00t/rl/config/robot/A2_Piper/a2_piper_vpiper.yaml`；`gr00t/rl/config/ablation/wbmanip/base_v28_common.yaml`、`base_v28_A_S28{1,2,3}.yaml`、`base_v28_G1_WARM.yaml`、`base_v28_eval_natural_start.yaml`。
2. asset：新 URDF 追加 `wrist_camera_tower` link 与 trunk 支架碰撞盒（按定值 θ/base 角重生成）、USD 重生成、readback 更新（HIGH_RISK asset 变更，按 §4.2 执行并记决策日志）。
3. `door_open_a2_base.py`：`_reward_penalty_a2_wrist_motion_l2`、`_reward_penalty_a2_wrist_tower_contact`、`penalty_a2_stage4_arm_default_pose_l1` 的 release 门控、§6.4 telemetry 进 trace；键缺失 bit-identical。`delta_action_base.py` 增加 `delta_action_clamp_to_dof_limits` 分支（D-17；两分支同一 patch，文件当前字节相同）。
4. `scriptsFORhuman/v28/`：`v28_contract.py`、`v28_verify.py`（materialize/resolve/freeze + compose-diff allowlist）、`v28_orchestrate.py`（GPU 余量选择、proxy env、P0_ASSETS）、`v28_run_cell.py`（`++experiment_dir`）、`v28_watch_wave.py`（按 `v27_watch_c_ready.py` 的分段逻辑）、`v28_reduce.py`、`v28_readout.py`、扩展的 `smoke_a2_base_flat_walk.py`；以 v27 脚本为模板。
5. `gr00t/rl/tests/test_a2_v28_*.py`：§4.3/§5.2/§6.2 列出的全部 CPU 测试 + harness 测试（watcher 分段、receipt schema、GPU 选择器 mock、reducer 早期终止、eval `experiment_dir`）。
6. 禁止：改 v26-x/v27 脚本或 artifact；改 trainer loader；改现有 reward 函数逻辑；为测试在核心路径加 hook；fallback/宽容分支。

交付：训练与评估 receipt（source lock、字节比对记录、proxy env、GPU 余量、preflight；D-022）；G0 几何/碰撞/覆盖/locomotion 验收报告；G1 结论；每 milestone reducer 与 readout；Wave A endpoint lock 与 decision；候选 manifest；closure `scriptsFORhuman/v28/a2_piper_base_v28_execution_closure_<date>.md`；决策日志与待办登记；memory 三文件；四个本地 commit；changed paths 清单。

---

## 13. 结论边界

- v28 对 Q_S/Q_V/Q_Q 给 experiment 证据；对相机“可见性”只给几何上界与仿真渲染验收，不构成实机成像证据。
- 塔架安全只在仿真碰撞模型下成立；不构成 hardware、sim-to-real 或部署证据；Teacher/G7 binding 由 Owner 裁决。
- `REACH_SEED_UNSTABLE`、`CAMERA_UNMET`、`QUALIFICATION_NOT_CONFIRMED` 都是合法结果，不是追加预算的理由；`REACH_NOT_ESTABLISHED` 伴随塔架接触是对硬件方案的负面证据，按 §8.2 处理。
- 本轮不回答“camera bundle 是否提高 Student 蒸馏成功率”（X-02），也不回答 A2_Base 替换是否有益（X-03）。
- E_T（训练包络）上的 Teacher 失败不构成对 E_T 内更小安装件的负面证据；相机可见率的几何上界不构成成像证据。

## G0 暂停记录（2026-09-09）

Owner选择“保留原独立刚体，G0暂停”。不应用 compound-trunk 候选，不改变既有独立安装件拓扑；未执行第一个commit，未启动G1或正式训练。修改：-codex worker；依据：-owner。

当前阻塞：plate碰撞5→4mm已使arm_body0接触归零，腕机塔架接触力为0；trunk异常接触仍存在。CPU几何定位到trunk旧碰撞盒与vpiper_support重叠，并发现两者源STL三角面相交（不是STEP/BRep或hardware证据）。保留原始失败读数。详细状态见 `runtime_logs/v28_camera_aware_rebaseline_20260909/g0_decision.json`。修改：-codex worker。

## 两条 asset 路线对比（2026-09-09 20:19 HKT）

Owner最新指示：合并、裁切各制作一个独立版本，分别放在`gr00t/rl/data/robots/`下，等待Owner判断。当前活动asset与G0暂停状态保留，不做commit。合并版保留全部几何并按各组件质量/质心/惯量合成trunk；裁切版保留独立刚体与原惯量；Owner进一步明确support参与冲突时统一截去整个下部，因此最终对vpiper_main、vpiper_support的全部visual/collision以trunk z=0.130m作单一水平截断，距已定位冲突盒顶面1mm。裁切后原质量/质心/惯量继续保留，作为仿真比较近似。修改：-codex worker；依据：-owner。

两版入口与证据：`gr00t/rl/data/robots/v28_asset_comparison_20260909.md`；合并版28刚体/20活动关节、裁切版31刚体/20活动关节。候选状态均为`CANDIDATE_WAITING_OWNER_SELECTION`；本次仅CPU几何与USD静态读回，不代表G0通过。修改：-codex worker；制作/最终裁切规则依据：-owner。
