# v28 plan 规划者自省（供第三方审计交叉判断）

日期：2026-09-11 HKT。作者：v28 plan 的规划者（Claude planner）。对象：`scriptsFORhuman/v28/a2_piper_base_v28_plan_20260909.md`（状态 `G0_RESUMED_BY_OWNER`，D-01…D-35）及其派生文件（决策日志、待办登记、pull 同步计划）。本文只陈述我认为的弱点、依据与可核对处，不为已做决定辩护；"建议"标为建议，Owner 未批准的不生效。

---

## 1. v28 的目标与目的（一段话）

把开门 Teacher 放到**实机将要存在的那台机器人**上重建：新安装件 asset（含相机安装件质量与碰撞、腕机塔架碰撞体）、新 reset 姿态、动作目标夹到物理限位；在这个底座上从零重建双侧 Teacher，并按 v27.0 的 sim 资格程序选出一个可交给蒸馏分支的 checkpoint。目的有两个：让后续蒸馏出来的 Student 面对的是与 Teacher 行为相容的相机硬件（塔架不撞门、姿态可观测），以及让推门主线与 pull 分支共享同一套基建。v28 不承载方法 novelty。

---

## 2. 是否过于复杂——我的判断是：**基建部分不臃肿，训练设计部分有"一口吃成胖子"的实质风险，流程部分偏重但是 Owner 要求的**

### 2.1 同时变更的清单（相对 v27 控制配方）

| # | 变更 | 是否可选 | 性质 |
|---|---|---|---|
| 1 | asset 换 MERGED（+0.754 kg、臂座 −6.57 mm、mount 并入 trunk） | 否（实机事实） | plant |
| 2 | `wrist_camera_tower` 碰撞 link + 塔架接触惩罚 | 否（v27 RIGHT 抓握姿态穿板 41–65%） | plant + reward，**改变抓握行为** |
| 3 | trunk 上 base 相机支架并集包络 | 否（相机存在） | plant（保守） |
| 4 | reset 姿态 j2/j3/j4/j5 全变（动作零点与观测零点漂移） | 否（相机前视需要） | 动作/观测语义 |
| 5 | D-17 累积臂目标夹紧 | 可选但已批准 | 动作语义 |
| 6 | 两个新 reward + 一项释放门控（腕部运动 6×3×2 权重表；塔架接触；Stage4 回位） | 部分可选 | reward |
| 7 | K scaffold-decay（17 项、driver） | 由 Wave C 预注册路由触发 | reward 随时间变化 |
| 8 | 选种门拆层 | 评估口径 | 不影响训练 |
| 9 | harness/telemetry 扩展 | 工程 | 不影响训练 |

1–4 是硬件事实，分开做只会多花几轮训练而不换来归因；同时采纳是最便宜的排期。**风险不在归因（D-01 已明确放弃归因），而在"Wave A 是否能产出任何一个过门 seed"**：v27 在更简单的底座上，同一配方从零 3 seed × 6000 是 0/3，唯一过门的是 K 版且发生在 5000→6000。v28 在更难的底座上叠加 5–7 项行为相关变更，仍用 6000 预算、3 seed，没有任何一格把"最大风险"（塔架碰撞迫使 RIGHT 抓握改姿态）与其余变更隔开。

### 2.2 "胖"的具体症状

1. **没有风险梯（risk ladder）。** 若 Wave A 0/3，plan 的唯一响应是 STOP，届时无法区分是塔架、姿态、夹紧、bundle 还是 K 造成的。D-08 否决了"无 bundle 对照"，理由是消融不是 v28 目标；但一格便宜的**梯子**（1 seed × 2000–3000 batches：asset + 姿态 + 夹紧 + 塔架，不带 bundle 与 K）目的不是归因，而是在 46 h 的 Wave A 之前用 15–20 h 知道"新底座本身能不能到 Stage4"。我当时没有以这个理由再提，是遗漏。**建议**：作为 G1 的并行格加入（`V28_G1_LADDER`），预注册判据只看 D/S4+，不看质量。
2. **预算与先验不符。** v27 SC 在 3000–4000 到顶、质量分量在 6000 仍在动；SK 的跃升在 5000→6000。v28 保留 6000 而底座更难，且没有采纳"条件延长"规则（O5）。**建议**：在 launch 前冻结一条延长规则——6000 时任一 seed 双侧 complete ≥ 60 但 clean 分量在最后两个 milestone 单调上升，则该 seed 延长一次到 8000；否则不延长。不冻结则等于接受较高的 STOP 概率。
3. **36 个权重数字来自单 cell。** §6.3 的两张 6×3 表由 C_S2 DEV 一条 deterministic trace 在旧底座上校准，Stage0/1 收入是公式估计；实际只有三档区分（严/中/Stage3 j6=0）。过度指定会给审计者一种"精确校准"的错觉。**建议**：保留实现，但在 plan 注明这是三档设计、单 cell 校准、新底座上未验证，并把 G0 R5 的 Stage0/1 收入读数作为唯一的重校准点。
4. **G1 作为 scratch 的门在逻辑上弱。** G1 是 warm probe，其通过线（500 batch 时 D ≥ 40、clean ≥ 36）远低于 Wave A/B 门；`WARM_PASS` 不预测过门，`WARM_FAIL` 更可能反映动作零点漂移（j5 −0.935 rad）而非 scratch 可行性。把 G1 失败作为整个 v28 的 STOP 条件，是把一个弱信号当成强门。**建议**：G1 与第一个 scratch seed（或 2.1 的梯子）并行启动；G1 只决定是否追加 warm arm，不决定 scratch 是否启动。这需要 Owner 改 §8.3 的 STOP 语句。
5. **决策密度。** 三天内 35 条决策、两位写者（planner 与 worker）编辑同一 authority 文件、两套编号（plan D-xx 与 log V28-Dxxx）、worker 在文末追加运行记录。审计者会遇到：§8.6 排在 §8.5 之前（我插入时的次序错误，本次已修）；D-04 被 D-35 取代但表中仍保留原依据文字；§2.5 表仍是 θ40/45 的历史计算。**建议**：首个 commit 时由 worker 做一次整理：plan 只留 authority 文本，运行记录移到 `runtime_logs` 与决策日志，附一张 D-xx ↔ V28-Dxxx 映射表。

### 2.3 哪些复杂度是合理的

- 分期冻结（D-30）与 containment 判据：它把"蒸馏时再定光学"从口头承诺变成可检验的几何规则，成本只是 G0 多写一组盒参数。
- 选种门拆层（D-32）：v27 的证据表明合取门几乎无人可过、且遮蔽失败原因；拆层不放松资格，只改选种。
- K 纳入：预注册路由触发，不是临场决定；`K_REACH_WITHOUT_COMPLETE` 与第 4 seed 备选给了它一个失败出口。
- harness 修订：v27 三次停摆全是 harness 层，不修会重演。

---

## 3. novelty / 基建 / Teacher 行为改进的平衡与取舍去向

### 3.1 v28 的实际配比

| 方向 | 占比（按训练预算与实现工作量粗估） | 说明 |
|---|---|---|
| 新 baseline 基建 | ≈ 80% | asset、姿态、夹紧、塔架、harness、pull 同步 |
| Teacher 行为改进 | ≈ 20% | 腕部运动/塔架接触/Stage4 回位、K、（间接）塔架迫使新抓握 |
| novelty 验证 | 0% | D-01 明确顺延 |

### 3.2 一个必须说清的缺口

v27 暴露的 Teacher 行为缺陷里，v28 **直接**针对的只有释放后甩腕（Stage4 回位项）与积分器饱和（夹紧）。**最主要的质量缺陷——越门时 hinge 只有 ~62°（RIGHT）与 LEFT 松手顶门——没有任何一项机制直接针对**，只寄望于塔架碰撞（60° 门缝挤过会撞塔架）与 K 间接改变它。这是一个假设，不是证据。后果是 Wave B 可能再次 `NO_QUALIFIED_CANDIDATE`（v27.0 与 v27.5 都是）。审计者应把"v28 对 Q_Q 的预期是不确定偏悲观"记为已知状态。D-10 保留 hinge ≥ 1.0472 这一代理判据，而塔架碰撞已经提供了物理安全信号——是否在 Wave A 后用"塔架接触 vs 越门 hinge"的实测相关性重审这个代理，已登记为 X-21。

### 3.3 被 v28 让出的项目及其登记处（供后续 planner 主动提醒）

| 让出项 | 登记 | 入场/提醒触发 |
|---|---|---|
| 恢复环多 seed（N-01；v27 注入过弱需重设计） | longterm D 节 N-01 前提；deferred X-05 | v29 立项 |
| 交互历史 latent / 在线适应（N-02） | longterm D 节 N-02；X-05 | v29 立项；需 v27.2 的门域证据（当前无 arm-only 失败层） |
| camera bundle 配对消融 + 配对蒸馏（"observability-aware Teacher 是否提高蒸馏成功率"） | X-02 / N-07b | v28 Teacher 资格通过且 Student lane 有两条预算 |
| 腕机塔架侧移/后移（看到指垫/TCP） | X-01 / N-07a | Wave A RIGHT 侧失败伴随塔架接触，或 Owner 改硬件 |
| A2_Base 替换（LMP Stage2 + TCP 球坐标观测） | X-03 / N-08、X-11 | Owner 交付 TorchScript + metadata，过 G0-L-swap |
| base 相机单/双与上仰角 | X-20（D-06/D-33 后移） | 蒸馏 plan 起草；G2-C2 覆盖表与渲染验收 |
| 朝向/可观测性 shaping（第五项 bundle） | X-19；§6.4 遥测 | Wave A 首个 milestone 的方位角/越门偏航读数越过 Owner 阈值 |
| Plücker 相机条件化 | X-17 / DIST-02 | 蒸馏 plan 起草 |
| 门 asset 空洞面板占比与 Depth 不识别问题 | X-16 / DIST-01 | 下一轮蒸馏数据生成前必须向 Owner 确认四点 |
| Student proprio 加夹爪 qpos + effort 代理 | X-09 | Wave B 候选 manifest 后 |
| 动作低通/控制延迟（部署侧） | X-10 | sim2sim lane |
| 修正源 STL 的 trunk↔support 干涉（第三条 asset 路线） | X-18 | Owner 授权且有 CAD 能力 |
| 工具默认 USD 路径、`disable_gravity_for_arms` 索引隐患 | X-13/X-14 | 轮间窗口 |
| **越门偏航与窄门通过性**（v27 越门 yaw 中位 12.5°/19.8°，p5 窄门机身–门框碰撞份额 23–28% 上界） | **X-22（本次新增）** | Wave A 的 `crossing_yaw_deg_*` 读数；与 X-19 合并考虑 |
| **LEFT Stage2 发现失败的 seed 型**（v26-7 S0、v27 SC_S201 同型，D=0 六个 milestone） | **X-23（本次新增）** | v28 Wave A 任一 seed 出现同型 → 第 4 seed 与 staged_reset 比例是仅有的预注册杠杆 |
| **`clean_complete` hinge 代理判据的重审** | **X-21（本次新增）** | Wave A endpoint：塔架接触与越门 hinge 的实测关系 |
| **K 对照 guard 的退化**（基线为 0 或饱和时 −8 容差恒真） | **规则 25（本次入册）** | 任何用"同号 seed 基线 − 容差"作 guard 的预注册 |

---

## 4. 供审计者逐项核对的弱点清单（按严重度）

| # | 严重度 | 弱点 | 核对处 | 我的建议 |
|---|---|---|---|---|
| S1 | 高 | 无风险梯；7 项行为相关变更叠加在 from-scratch 上，失败时只能 STOP | §0.2 D-08、§8 | 加 `V28_G1_LADDER`（不带 bundle/K 的新底座梯子，1 seed × 2000–3000） |
| S2 | 高 | 预算 6000 与 v27 先验（SC 0/3、SK 跃升在 5000→6000）不符，无条件延长规则 | §8.2、§10 | launch 前冻结一次性延长规则或明示接受高 STOP 概率 |
| S3 | 中 | 36 个权重数字来自单 cell 旧底座 trace，Stage0/1 收入为估计 | §6.3 | 标注为三档设计 + 单点校准；G0 R5 为唯一重校准点 |
| S4 | 中 | G1（warm probe）通过线弱，却是 scratch 启动的门；`WARM_FAIL` 更可能反映零点漂移 | §8.1、§8.3、§9.6 | G1 与 scratch 并行；G1 只决定 warm arm |
| S5 | 中 | 无机制直接针对越门 hinge 与 LEFT 顶门；Q_Q 预期偏悲观；hinge 代理与塔架物理信号重叠 | §7 D-10、§8.4 | X-21：Wave A 后重审代理判据（不在中途改） |
| S6 | 中 | trunk 并集包络包含永不共存的盒；E_T 参数必须在 G0 写入才有 containment 可查 | §3.3a、§4.2 | 审计时核对 `g0_decision.json` 是否含 E_T 与并集盒的 F 系/trunk 系参数 |
| S7 | 中 | pull 同步依赖主线 G0 交付 S1/S2；pull Wave P-A 同样无梯子、1024 env、6000 预算 | pull plan §2、§6 | pull 侧同样加梯子或降为 2 seed + 梯子 |
| S8 | 低 | 两位写者、两套编号、运行记录混入 authority 文件；§2.5 历史表与 D-04 取代文字并存 | 全文 | 首个 commit 时整理并附映射表 |
| S9 | 低 | 多数几何数字是针孔/凸包上界，不是成像或物理测量；已标注 | §2.5、§3 | 审计时不作测量值使用 |
| S10 | 低 | 相机布局决策依据 v27 轨迹（条件性）与几何标准姿态集（无关轨迹）两套证据；前者会随新 Teacher 失效 | `planner_evidence_20260911/camera/REPORT.md` §2.4 | G2-C2 必须用 v28 轨迹重算 |

---

## 5. 我对自己流程的批评

1. 我在 D-08（否决无 bundle 对照）时只用了"消融不是目标"的框架回应 Owner，没有从**风险梯**角度再提一次；这是本文 S1 的来源。
2. 我把 G1 从"可选 probe"升级为"必做门"（因 Wave C `SCRATCH_NOT_ESTABLISHED`）时，没有同时检查它作为门的预测力（S4）。
3. 权重表（S3）是我接受 policy lane 的产出后直接冻结的，没有要求简化到与证据分辨率相称的粒度。
4. 我在 pull 同步计划里复用了主线的 3 seed × 6000 设计，没有针对 1024 env 与 v26-8 需要 4500–6000 才到 opening 的事实重估预算（S7）。
5. 文档纪律方面：多次用脚本批量替换编辑 authority 文件，产生了 §8.6/§8.5 次序错误与残留历史表述（S8）；本次已修次序，其余留给首个 commit 的整理。

---

## 6. 不需要审计者重新推导的已验证事实（可直接引用）

- 加载器只读 USD 且按名称选 27/28 个 body；30/31 体 USD 不需要新的顺序表（`isaacsim.py:2370-2374,2430-2435`）。
- 运行时 `enabled_self_collisions=True`（`isaacsim.py:1293`）；trunk↔vpiper_support 源几何干涉是 G0 R2 阻塞的根因（RUNTIME 16 万 N 级持续接触）。
- v27 全部 64 样本格里唯一双侧过门的是 SK_S213@6000；所有 warm 血统格都未过质量门；失败分量集中在 crossing hinge。
- 腕机塔架在手指开合轴上，任何倾角都看不到 TCP/指垫（真实 mesh 射线）；180 mm 包络不包含 140/120 变体（外伸 12.0/10.3 mm）。
- 板上双相机对门口净宽的代价为 0 mm（相机外缘 ±0.200 m 在腿/足 ±0.2348 m 凸包内）。
- 两分支 `delta_action_base.py`、`a2_piper.yaml`、A2_Base `policy.pt` 字节相同；actor/critic 均 133/138。
