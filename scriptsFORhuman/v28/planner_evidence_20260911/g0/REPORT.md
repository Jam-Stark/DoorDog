# v28 `base_v28` G0-UPDATE lane 报告

编写：G0-UPDATE lane（只读）；scratch 仅在 `/tmp/v28_team2/g0/`。未修改任何仓库文件、未运行 GPU/Isaac、未 commit。
证据等级：INSPECTED（读源文件）、COMPUTED（本 lane CPU 几何计算）、RUNTIME（既有 receipt）、STATIC（既有 CPU/USD 读回）。
分类标记：**[已批准]** Owner 已批准决定；**[提议]** 讨论建议，需 Owner 裁决；**[证据不足]** 当前无法判定。

## 0. 结论摘要

1. **需要调整**，但只需章节级措辞与判据编辑，不需改训练预算、reward 逻辑或路由。
2. 分期冻结在实现上可行（Teacher 不渲染相机，新奖励只依赖关节运动/接触/回位：`door_open_a2_base.py:15937-15954`、`27826-27853`），但有一个硬约束被 D-029 漏掉：**冻结姿态与 θ 是耦合的**，θ 后移会让 §3.1 的行走前视/地面指标在冻结姿态下失效（§4）。
3. **“180 mm 包络包含 140/120 变体”是错的**（COMPUTED，§4）：最大外伸 11.99 mm（140）/10.33 mm（120）/8.53 mm（100）。
4. 两条 asset 路线的最小改动比 worker 预估的小：**两者的 `body_names` 都仍是 28、`penalize_contacts_on` 都仍是 20 元组**；差别集中在 native/contact-sensor 计数（28 vs 31）、G0-A1 质量惯量判据、以及 mount 接触归属语义（§2）。
5. 新增 COMPUTED 证据：**裁切版把 trunk↔mount 的全部重叠消除，最小间隙变为 +1.00 mm**；合并版按构造消除（同一刚体无自接触）。这是 R2 阻塞的直接候选解，但两者都未跑物理。

---

## 1. Teacher 碰撞/动力学合同 vs Student 光学安装合同

**[提议] 建议分期冻结**，理由：Teacher 侧 `enable_cameras=False`（`v28_g0_contact_probe.py:36`），可见率为 report-only（plan §6.4，`:296-298`），三项新奖励分别读 `dof_vel`、`contact_forces[tower]`、`dof_pos` 偏差（`door_open_a2_base.py:15937-15954`、`15930-15934`），与光学参数零耦合。

### 1.1 必须留在 Teacher 训练前（Teacher Collision/Dynamics Contract, C_T）

| 项 | 来源 | 留下的理由 |
|---|---|---|
| 塔架碰撞包络：截面 90×25 mm、支架长 114.700015242 mm、外壳盒 25×90×25、两盒相对 F 的完整位姿 | plan §3.1、§4.2（`:168,202`）；`a2_piper.urdf` cut:1208-1243 | 决定 R2/G0-C3 与整个 Stage2–4 学到的抓握姿态 |
| 塔架质量/质心/惯量（0.15 kg，COM `(-0.00107, 0.14674, 0.01329)`，完整张量） | cut URDF:1239-1243 | 动力学合同；蒸馏时改变即非“仅图像变化” |
| `wrist_camera_tower` 作为独立刚体 + fixed joint 拓扑 | cut URDF:1245-1249 | `body_names` 28、contact 索引、塔架惩罚均由此成立 |
| trunk 上 base 相机支架/外壳碰撞盒（按 15° 生成的 10 个盒） | plan §4.2（`:203`） | 与 `metal_plate_5mm` 的最小间隙**恰为 +1.00 mm**（COMPUTED），任何后移的 base 支架重设计都可能重新制造重叠 |
| 冻结姿态 `[0,0.10,−0.10,0,−0.52,1.57]` | plan §5.1（`:229-231`）；`a2_piper_vpiper.yaml:135-142` | 同时是动作零点、`dof_pos` 观测零点、Stage0/4/5 姿态锚点与 Stage0→1 门 |
| D-17 夹紧 `delta_action_clamp_to_dof_limits` | `delta_action_base.py:67-80` | 动作语义 |
| reward bundle 与权重表（`penalty_a2_wrist_motion_l2 −0.4`、`penalty_a2_wrist_tower_contact −1.0`、`penalty_a2_stage4_arm_default_pose_l1 −0.5`、6×3 两张权重表） | `base_v28_common.yaml:97-145` | 训练目标 |
| §6.4 telemetry 字段与 §7 安全门 `wrist_tower_contact_episodes_gt_5N ≤ 2/64` | plan §6.4、§7（`:297,306`） | 训练期读数与选种 |
| **G0-C3**（塔架包络对门板/门框 SDF 扫掠） | plan §3.2（`:183`） | 纯碰撞，且是 D-07 的依据 |

### 1.2 可后移到蒸馏前（Student Optical Mount Contract, C_S；建议命名 G2-C*）

§3.1 的：腕机光学中心高度（当前 180 mm）、倾角 θ（45/40）、base 相机上仰角（15/12）、近场可见需求、前视/地面需求、自遮挡预算（depth 支柱 ≤7%、Min-Z 内 ≤9%）以及“仿真渲染必须包含支柱 visual”这条域一致性要求。
§3.2 的：**G0-C1 → G2-C1**、**G0-C1′ → G2-C1′**（仍按 D-018 记 `NOT_RUN` 直到真实 CAD 存在）、**G0-C2 → G2-C2**、**G0-C4 → G2-C4**。
§8.5 的：Student lane 全部（新 rig JSON、`plan_id` 硬检查、rig asset 路径、proprio 加夹爪 qpos/effort，X-09）→ 蒸馏前；`sim2sim` lane（X-10）时点不变；硬件 lane **拆两段**——(a) 训练前只交付**包络约束**（“最终支架+外壳必须落在 E_T 内、质量 ≤0.15 kg”），(b) 蒸馏前交付 θ/base 角/塔长/侧移（§3.3）。
注：Student rig 代码在 student worktree，本仓库不可见（`v28_u3f0_geometry_precheck.py:34` 只引用其 JSON），`plan_id` 检查的改动无法在此核对。**[证据不足]**

### 1.3 containment rule（几何包含判据）

坐标系：`wrist_camera_tower` 的 link frame **等于** 法兰系 F（fixed joint origin xyz=0 rpy=0，cut URDF:1245-1249），因此包含关系直接在 F 中判定。

- 定义 `E_T` := 训练所用 `wrist_camera_tower` 全部 `<collision>` 凸形状的并集（F 系）。
- 定义 `B_f` := 最终光学安装件的支架盒 + 外壳盒（同样在 F 系，用 `T_F_M`、`T_F_support`，不用“180 mm/45°”这种参考姿态语义——见 `camera/U3_F45_B15_mechanical_extrinsics_20260911.md:59-66`）。
- 判据：对 `∂B_f` 以 ≤5 mm 网格采样并含全部角点，要求每个采样点在 `E_T` 内且 `SDF_{E_T}(p) ≤ −3 mm`。工具复用 `planner_evidence_20260909/asset/mount_clearance_check.py` 的 `Hull` / `intersect_depth` / `distance`（凸-凸 LP+QP，精确）。
- 动力学包含（同样必须满足，否则不能只当图像变化）：`m_f ≤ 0.15 kg`；质心到 F 原点距离 ≤ 训练值；绕 F 的三个主惯量逐项 ≤ 训练值。
- 不满足时的分支（**不允许**静默继续）：① 训练前把 `E_T` 扩成族包络并重跑 G0-A4/R2/G0-C3；② 按 §3 的 eval-time 交换检查判定是否可直接复用；③ 需 Owner 授权的短 fine-tune。三者都要写入决策日志。

---

## 2. MERGED vs CUT：最小改动与决策表

两个候选的 native 刚体分别为 28 / 31（`validation/usd_import_readback.json`，STATIC），活动关节均 20，全机质量均 45.64480826480732 kg。

### 2.1 最小改动清单（逐项）

| 对象 | MERGED | CUT |
|---|---|---|
| `robot.body_names` / `num_bodies`（`a2_piper_vpiper.yaml:6,48-56`） | **不变**（28，名字完全相同） | **不变**（28；vpiper_* 不入表，与当前活动 asset 同构） |
| `penalize_contacts_on`（`:107-113`，20 元组） | **不变**（`door_open_a2_base.py:5451-5454` 的严格相等断言 `:17907-17914` 仍成立） | **不变** |
| `A2_M23_SELF_COLLISION_BODY_NAMES`（27，`:5615-5643`） | 27 名恰为 URDF 前 27 个 link（COMPUTED），G0-A5 的“前缀/子集”措辞可用 | 同样成立 |
| `test_a2_v15_dynamic_reachability.py:770-773`（读旧 `A2_Piper/a2_piper.urdf`，切换后陈旧通过） | 必须按 G0-A5 改为读 resolved asset | 同上（与候选无关） |
| contact sensor 计数断言（`v28_g0_contact_probe.py:52`、plan §4.3 R1 `:217`） | `31 → 28` **必须改** | **不变**（28/31） |
| G0-A1 质量惯量判据（plan `:211`：27 共享 link inertial 与旧 asset 一致） | **必须改**：trunk 质量 19.651→20.40480826480731 kg、collision 15→67、visual 11→14（COMPUTED）；改为“零关节下全机质量差 0、COM 误差 1.74e-18 m、完整惯量张量误差 2.78e-17 kg·m²”（merged `README.md:9-13`） | **不变**：`all_inertial_definitions_unchanged: true`（`validation/mass_pose_contract.json`）；但需追加一句“vpiper_main/support 的 collision 15→9、36→12，visual 体积 −30%/−83%，质量惯量刻意保留为近似” |
| 资产路径 allowlist（`v28_verify.py:53-58`、`:84`）与 walk 脚本硬编码（`v28_run_cell.py:44-46`） | 改路径；加 `--asset` 选项 | 同样改路径；同样加选项 |
| G0-A4 / R2 | 重叠对按构造消失（同一刚体内无自接触） | 重叠对被几何删除，**最小间隙 +1.00 mm**（COMPUTED） |
| 碰撞语义 | mount 接触归 trunk → 进 `penalize_contacts_on` 与 `A2_DOOR_BODY_PANEL_FILTER_NAMES`；mount–门板接触被 dedup 排除、mount–其它物体接触吃 −0.2；**副作用：`arm_body0`↔mount 变成父子对被 importer 过滤，D-021 的 plate 5→4 mm 修正失去意义，同时该接触永久不可见** | 与当前语义完全一致：vpiper_* 不在 `body_names`，其接触从不进入 `contact_forces`（`isaacsim.py:2376-2378,2728-2731`），被丢弃 |

### 2.2 决策表（不代 Owner 决定）

| 判据 | 倾向 MERGED | 倾向 CUT |
|---|---|---|
| 物理保真 | ✔ 不删任何几何；精确复合惯量 | ✘ 删掉 support 83%/main 30% 的体积却保留原质量惯量，质量-几何不一致 |
| 接触归属 | ✔ mount 接触可见并被惩罚；✘ 与 body-panel 语义混同，且 `arm_body0`↔mount 永久不可见 | ✔ 语义与 v27 零变化、无新惩罚通道；✘ mount 接触永远静默 |
| 测试/asset 简单度 | ✘ R1 计数、G0-A1、trunk 质量/COM（→ D-14 的 LMP trunk 质量随机化论证需复核，+0.754 kg 仍在 +[0,5] kg 内） | ✔ 除 asset 路径外几乎零改动 |
| sim-to-real 含义 | ✔ 保留真实装配几何 | ✘ 对臂在底座附近的自由度偏乐观 |
| 共同前提 | 两者都只是绕过“trunk 与 vpiper_support 源 STL 三角面相交”（plan `:417`），都不是修正源几何 | |

**[仍需 Owner 决定]** 第三条路线——修正源装配 CAD/STL 的干涉——当前未被授权，也没有人做过；它是唯一能同时满足物理保真与接触归属的选项。

---

## 3. §8.2 硬件反馈分支的收窄措辞

现文（plan `:322`）把 `REACH_NOT_ESTABLISHED` + 高塔架接触直接判为“180 mm F+Y 塔架与 RIGHT 门抓握不兼容”。在保守大包络下这个推论过强。**[提议] 替换为：**

> **硬件反馈分支（修订）**：若 `REACH_NOT_ESTABLISHED` 且失败集中在 RIGHT 侧、伴随 `wrist_tower_contact_step_share` 高或 Stage2→3 停滞，closure 必须写明“**训练所用包络 E_T（截面 90×25 mm、外壳中心距法兰 180 mm、θ=45）与 RIGHT 门抓握不兼容**”。该结论只指控 E_T，**不指控任何几何上被 E_T 包含的更小最终安装件**，也不构成对 140/120 mm 变体的负面证据；X-01（侧移塔架）升级为硬件决策请求；不追加预算。
> **蒸馏前 eval-time 交换检查（新增）**：选中 Teacher checkpoint 在**仅换 asset 的 eval overlay**（`robot.asset.usd_file/urdf_file` 指向带最终安装件包络的 asset，link 拓扑与 `body_names` 不变；其余按 §7 冻结合同 + `++experiment_dir`，D-16）上做 LEFT/RIGHT exact64。通过判据：`wrist_tower_contact_episodes_gt_5N ≤ 2/64/侧`、`wrist_tower_contact_step_share ≤ 训练包络读数 + 0.01`（绝对）、complete/clean 不低于 §7 的 64 样本门。产出 `g2_mount_swap_decision.json`，typed outcome `MOUNT_SWAP_OK / MOUNT_SWAP_DEGRADED / MOUNT_SWAP_FAIL`。
> 判读规则：E_T 上失败但交换检查通过 → 结论是“E_T 过保守”，可继续蒸馏；交换检查失败 → 结论指控最终安装件，回到硬件决策，不得改阈值。

注意：交换会同时改变塔架质量/惯量，必须在 receipt 里显式记录并归为 RUNTIME（非 EXPERIMENT）证据。

---

## 4. 塔高 140/120（D-028）的包络与动力学

**包含性：否。**（COMPUTED，`/tmp/v28_team2/g0/containment.py`；假设=保持 F 系 x/z 不变只降低中心、倾角绕外壳 90 mm 横条轴旋转、支架起端固定按 D-020 的 1 mm 间隙不变、支架随高度缩短。）

| 变体 | 支架长（mm） | 落在 E_T(180) 之外的最大外伸 | 采样点外伸比例 |
|---|---:|---:|---:|
| h=140, θ=38.76° | 74.70 | **11.99 mm** | 19.9% |
| h=120, θ=34.49° | 54.70 | **10.33 mm** | 16.4% |
| h=100, θ=29.13° | 34.70 | **8.53 mm** | 16.4% |

原因：外壳盒在较低轴向站位上带 θ 倾角，其 25×25 截面的对角尺寸超出支架 25 mm 厚度，而 E_T(180) 在该站位只有支架那 25 mm。**同足迹、更低 ≠ 被包含。**

**族包络代价很小。** 在支架自身坐标系下取单一长方体（COMPUTED，`/tmp/v28_team2/g0/family.py`）：仅 180 → `91.11 × 40.13 × 140.81 mm`；覆盖 h∈[140,180] → `92.42 × 40.13 × 140.81`；覆盖 h∈[100,180] → `93.73 × 41.76 × 140.81`（中心 `(1.07, −6.76, 13.05) mm`）。即**族包络只比单点包络大 +2.6 mm 宽、+1.6 mm 厚、长度不变**。代价在别处：单一实心盒的体积 ≈ 当前两盒并集（314,325 mm³）的 2.2 倍，会让门板间隙问题更难（§2.6 已有 RIGHT 门 Stage4 穿板 41–65%）。

**动力学差异很小、且几何差异才是主项。** 0.15 kg 在 0.18 m vs 0.14 m：绕 F 的转动惯量 4.86e-3 vs 2.94e-3 kg·m²，重力矩 0.265 vs 0.206 N·m，相对 arm_j6 力矩上限 100 N·m（`a2_piper_vpiper.yaml:88`）为 0.27% vs 0.21%；D-14 已论证 +0.754 kg / ≤2.2 mm CoM 远在 LMP 随机化内，0.15 kg 移动 40 mm 更在其内。**把质量/COM/惯量固定在 180 站位即对全族保守。**

**[提议] 建议（二选一，不代 Owner 决定）：**
- **A（推荐，最省）**：训练前就定下 h 与 θ，`E_T` 仍用两盒结构、不膨胀。理由见下一条耦合约束。
- **B**：`E_T` = 单一族包络盒（建议 `100 × 48 × 147 mm`，在上表 h∈[100,180] 结果上各留 ≥3 mm margin），质量/惯量取 180 站位；接受一个偏保守的塔架，并重跑 G0-A4 / R2 / G0-C3。
- **不可取**：用当前 180 两盒设计训练，再声称它覆盖更低变体。

**耦合约束（D-029 未覆盖，必须提请 Owner）**：D-03 的 `j5 = −(θ − 15°)` 使冻结姿态 `j5 = −0.52` 只对 θ=45 给出行走光轴 −15.2°。姿态属于 Teacher 合同、**蒸馏时不可改**（改动作零点=重训）。若 θ 后移到 38.76°，冻结姿态下行走光轴变为约 −8.97°；按 depth 下缘角一阶估算（COMPUTED），地面可见起点从 ≈1.5 m 推到 ≈1.9 m，直接违反 §3.1 的“depth 地面起点 ≤ 1.5 m”。θ=34.49° 时光轴约 −4.70°，更差。**结论：θ 可以后移，但必须同时接受 §3.1 的行走前视/地面指标改为“在冻结姿态下按最终 θ 重新推导并如实记录，可能 UNMET”，或者在训练前定 θ。** 这是一个 Owner 决策，不是 worker 可默认的分支。

---

## 5. 输出：是否需要调整 + 最小修改清单 + 仍需 Owner 决定

### 5.1 是否需要调整

需要。全部为章节措辞/判据编辑 + 两处脚本常量，**不改**预算、路由、reward 逻辑、trainer loader。

### 5.2 最小修改清单（按章节，给出改动语句要点）

| 章节 | 最小改动 |
|---|---|
| §0.1 / §1 新增 D-030 | 加入“合同分两段冻结：C_T（碰撞/动力学/姿态/动作/奖励/telemetry）在 Teacher 训练前冻结；C_S（光学高度、θ、base 角、可见性预算、渲染域一致性）在蒸馏前冻结”，状态 PROPOSED 直到 Owner 批准；重审触发=containment 判据失败 |
| §3.1 | 把“腕机塔 / θ / base 相机 / 近场需求 / 前视地面需求 / 自遮挡预算”六行各加一列“冻结阶段 = C_T | C_S”；“腕机塔”行拆为“碰撞包络（C_T）”与“光学中心高度 180 mm（C_S，D-028 待定）”；在“行走/reset 姿态”行加注：该向量属 C_T 且与 θ 耦合，θ 改变后行走光轴按 `−(θ−|j5|)` 重新推导，前视/地面指标随之重判 |
| §3.2 | G0-C1 / C1′ / C2 / C4 改名 G2-C1 / C1′ / C2 / C4 并标注“蒸馏前执行，不阻塞 Teacher 训练”；G0-C3 保留在 G0 并加一句“判据针对 E_T，不针对最终安装件” |
| §3.3 | 拆成 §3.3a“训练前交付硬件的包络约束（E_T 定义 + 质量上限 0.15 kg + containment 判据与 3 mm margin）”与 §3.3b“蒸馏前交付 θ/base 角/塔长/侧移”，并注明 §3.3b 的数值来源为 `camera/U3_F45_B15_mechanical_extrinsics_20260911.md` 的 `T_F_M`/`T_F_support`，不用“180 mm/45°”口语值 |
| §4.1 / §4.2 | 加“候选选定后只改 `robot.asset.urdf_file/usd_file`；`body_names`（28）、`num_bodies`（28）、`penalize_contacts_on`（20）在两候选下均不变”；合并版分支补一句“mount 接触归 trunk，`arm_body0`↔mount 成为被过滤的父子对，D-021 的 plate 修正失效” |
| §4.3 | G0-A1 加候选分支（merged 用复合等价判据，cut 用“27 共享 link inertial 不变 + 裁切量登记”）；R1 的 `contact_sensor.num_bodies` 写成“= 所选 asset 的 native 刚体数（merged 28 / cut 31）”；G0-A4 加“候选 asset 的 trunk↔mount 最小间隙 ≥ 1.0 mm”（当前 CUT COMPUTED = +1.00 mm） |
| §7 | 安全门后追加一句“`wrist_tower_contact_*` 阈值定义在 E_T 上；最终安装件按 §8.2 的 eval-time 交换检查另行判定” |
| §8.2 | 按本报告 §3 替换硬件反馈分支段落，并追加 eval-time 交换检查与 `g2_mount_swap_decision.json` |
| §8.5 | Student lane 一行标注“全部移至蒸馏前（C_S）”；硬件 lane 一行拆为 §3.3a/§3.3b 两段 |
| §11.4 | 权威 JSON 列表加 `g2_mount_swap_decision.json` |
| §13 | 加一句“E_T 上的 Teacher 失败不构成对 E_T 内更小安装件的负面证据” |
| 脚本 | `v28_g0_contact_probe.py:52` 的 `31` 与 `v28_verify.py:53-58` 的资产路径随候选改；`v28_run_cell.py:44-46` 增加候选 asset 选项（用于新 asset 平地行走对照） |

### 5.3 仍需 Owner 决定

1. **asset 路线**：MERGED / CUT / 修正源 STL 干涉（第三条未授权）。
2. **腕机高度与 θ**：训练前定（方案 A）还是训练族包络（方案 B）；若后移 θ，是否接受 §3.1 行走前视/地面指标可能 UNMET。
3. **是否批准分期冻结**（D-030）并把 D-028/D-029 从 PROPOSED 推进。
4. **是否批准恢复 G0**（当前 `PAUSED_BY_OWNER`，`g0_decision.json`）以及候选 asset 的物理验收授权。
5. eval-time 交换检查的阈值是否采用本报告数值（这是新增预注册阈值，按 §9.8 需 Owner 批准）。
6. base 相机支架碰撞包络是否一并冻结（当前与 `metal_plate_5mm` 仅 +1.00 mm 间隙）。

### 5.4 当前 G0 阻塞顺序

1. **trunk / vpiper_support 异常自接触**：RUNTIME `trunk` 最大接触力 165539.0 → 162729.7 N、50 步持续，`undesired_contact_raw_mean = 1.0`（`g0/contact_wide_plate4/contact_probe.json:103-108,1524-1548`）；根因 CPU 定位为 `trunk#1` 与 `vpiper_support#19/22/25/28/20/23` 重叠 −2.67…−0.78 mm（COMPUTED，本 lane 复算，与 `g0/persistent_trunk_contact_geometry.json` 一致）。
2. **候选选型**：MERGED / CUT（二者都能消除该重叠：CUT 最小间隙 +1.00 mm COMPUTED；MERGED 按同刚体构造消除）——G0 无法在选型前继续。
3. **R2/R3/R5 按 D-024 重跑**：现存 `contact_probe.json` 只有 step 0–49，`R3` 的“稳定 1 s 后 50 步”窗口无数据；当前脚本已改为 100 步 + `root z∈[0.45,0.51]`、`|dq|<0.5`、FK 0.432637±0.01（`v28_g0_contact_probe.py:89-91,100`），未运行。R5 的 FK 读数本身已满足（0.43263668–0.43263704 m）。
4. **G0-A4 / G0-C3 / 新 asset 平地行走对照 / G0-L**（旧 asset 基线已 3 姿态 × 64 env、零摔倒，RUNTIME）。
5. **5-batch PPO smoke + 新 telemetry 的 runtime 验证**（`a2_v28_camera_telemetry_enabled` 路径至今只在 contact probe 里被调用过一次，字段未经 reducer 验证）。
6. **第一个本地 commit**（plan §9.7 预授权，需 G0 全通过；当前 `git_commit_performed: false`）。

---

## 6. 证据边界

- 本报告的所有几何数字为 CPU 凸包/盒体计算（`/tmp/v28_team2/g0/{pairs,containment,family,envelope,cutcheck}.py`），**不是** PhysX 接触读数、不是渲染证据、不是硬件 CAD。
- 两个候选 asset **均未跑过任何物理步进**；“CUT 消除重叠”是 COMPUTED 级，需 R2 复跑确认。
- 140/120 变体的外伸数值依赖上文列出的放置假设；最终安装件规则未定前，这是**对“180 包含一切”这一断言的反证**，不是对某个具体最终设计的合格性判定。**[证据不足]**
- Student rig / `plan_id` 检查在另一个 worktree，未核对。
