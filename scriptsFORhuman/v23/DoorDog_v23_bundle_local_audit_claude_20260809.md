# DoorDog v23 Bundle 本地独立审核(Claude,2026-08-09)

审核对象:`DoorDog_v23_training_design_v0.1_20260809.docx` + planner/worker prompts + execution contract YAML(以及其前置讨论 `Base v22效果诊断&v23前置讨论.md`)。
审核方法:所有实质性论断均对照本地生产环境核实(source、configs、`logs_eval/base_v22` locks/artifacts、v21B artifacts、memory ledger)。云端 pro 模型只能读远程 git repo,无法访问 `logs_eval`/`logs_rl` 运行证据与 W&B——本审核重点补这一块。

---

## 0. 总裁决

**骨架采纳,细节必须修**:2×2×2 factorial(初始化 × 门阻力 × 姿态可用性)+ E0/E1/E2 反事实救援 + P0 前置链 + 预注册裁决,方向与项目既有 force-feasibility 路线(`scriptsFORhuman/force_feasible/`,`u_base = u_user + gate(s)·u_assist`)完全对齐,是正确的下一轮。
对应 planner 决议建议:**`APPROVE_WITH_BOUNDED_PATCH`** —— 有 11 项 patch(P1-P11),其中 P1/P2/P3/P4 若不修,factorial 的可归因性或 H3/H4 的可证伪性会直接受损。

前置基础事实(全部本地验证过,对 bundle 是正面的):

- worker prompt §4.1 列出的 11 个文件路径全部真实存在;本地 HEAD `4b26651` 与 origin 完全同步(0 ahead/0 behind)——云端看到的源码就是生产源码。
- 8× RTX A6000 空闲,与 contract `legal_physical_gpus: 0-7` 一致;v22 单 cell(4096 env × 2500 batches)实测约 17-18 h,两波 + P0 时间可行。
- RP0 结构可实现:actor 为对角高斯 `Normal(mean, std)`(`actor_critic_modules_recurrent.py:205`),per-dim state-independent `self.std`,log_prob 为 per-dim 求和(`actor_critic_modules.py:229`)→ 分布级 mask(masked dims 不进 log-prob/entropy/KL/ratio)干净可做。
- staged reset 存在且配置化:`enable_staged_reset: True`,`staged_reset_ratios: [0.5, 0.1×5]`(`config/env/door_open_a2_base.yaml:220-222`)+ `reset_from_dataset`——scratch cells 可依赖。
- 5D base command `[x,y,yaw,pitch,roll]` 在代码里 fail-fast 校验(`envs/base_task/a2_base.py:396-400`),pitch/roll = `clamp(-1,1)×0.4`;P0-A 已实测 command/achieved 索引顺序相反。
- v22 的 episode 级 forward 干预基础设施已存在并可复用:`scriptsFORhuman/v22/posture_intervention.py`(interventions = `legacy/zero/clamp/height_nominal`,scenario-manifest CRN 配对)。

---

## 1. 云端事实性论断 verification 表

| # | 云端论断 | 本地裁定 | 证据 |
|---|---|---|---|
| 1 | `privileged_door_info` 8D 已进 actor(含 mass/100),无 damping/stiffness/max-force | **TRUE** | `config/obs/wbmanip/door_open_a2_base.yaml:17,36`;`door_open_a2_base.py:22313-22326` |
| 2 | arm 每关节 100 N·m 无硬件依据 | **TRUE** | `config/robot/A2_Piper/a2_piper.yaml:83`(100×6);ARM_V20 = `[100]*6` + gripper 45/45(`base_v21B_B1...yaml:121`) |
| 3 | v22 formal:`push_door_handle=0`、`push_door_force=0`、posture L1=0 | **TRUE** | `base_v22_G1_posture_seed0.yaml:133-150`(L1 被六个 conditional 项替代——见 P4) |
| 4 | Wave-2 H0/H1/H2 数值范围 | **TRUE(逐字准确)** | `logs_eval/base_v22/locks/V22_HINGE_RANGE_FREEZE.json` |
| 5 | H3/H4 unrealized;25/30 N·m below resolution | **TRUE** | 同上 `unrealized_buckets`;`V22_FINAL_ANALYSIS.json` `higher_torque_probe: HINGE_TORQUE_RESOLUTION_INCONCLUSIVE_BELOW_RESOLUTION` |
| 6 | `arm_failure` 是低 margin proxy 而非不可行检测 | **TRUE** | `door_open_a2_base.py:7490-7504`:OR(effort_util>0.90, tracking>p90, joint_margin<0.10) & hinge_vel<0.03 & streak≥15 |
| 7 | "warm-start 时代早期 basic reward 被移除,scratch 需恢复" | **FALSE(关键前提错误)** | 见 P4 |
| 8 | torque telemetry 需从零建 | **不完整** | 见 P5(v21B 已接 `computed_torque`/`applied_torque`,authority=ESTIMATE_ONLY) |
| 9 | 摩擦/breakaway 可作 atlas 轴(A3) | **今天无旋钮** | 见 P6 |
| 10 | posture gate `REPORT_ONLY_INSUFFICIENT_DENOMINATOR`、§17 五标签 | TRUE | `V22_FINAL_ANALYSIS.json` |

---

## 2. Agreement(我背书的设计决策,含本地证据强化)

1. **否决 height-conditioned posture reward**——除双方已有理由外,本地证据更直接:v16 实测 0.4 饱和与 handle 高度无关(低桶 79.0% vs 高桶 81.4%),height prior 连观测到的病理都对不上。
2. **姿态价格路线不再加码是对的**——ledger 2026-07-24 已预注册否决价格弹性("λ×10 付 12% 收入仍 98-100% 使用");v22 又追加了 `-16` saturation 价格仍未压平。v23 转向"测量 + 参数化/gate(POST-v23)"正确。
3. **scratch 轴的立项现在有依据**——ledger 预注册规则"scratch 重训仅在'习惯性'判定后立项";v22 posture atlas 给出阶段分解证据(抓稳后 neutral 已近最优)= "习惯性"判定部分到位,scratch 立项与项目自身规则衔接成立。
4. **RP0 ≠ arm-only 的改名与 FULL/RP0/BASE0 三层分解**——正确;且 acute 版基础设施已存在(v18 P2:pitch-zero 2/16、roll-zero 9/16;v22 P0-B)。
5. **E2 不进训练分布**——正确(PPO 无解任务 → 回避/终止投机,与 v11/v13 stationary-rent 教训同源)。
6. **E1 用行为对照定义而非分类器**——直接吸取 v22 `posture_need = max(四条件)` 饱和失败(`OVERACTIVE_OR_VACUOUS`)的教训,是对 v22 机制的正确修正(但分类的 policy-relative 陷阱见 P2)。
7. **coupling critic 只做 shadow、三分支 actor/counterfactual PPO 全推 POST-v23**——正确;joint log-prob 单 ratio 确实无法做 branch credit;设计 §11.2"无法 clone 就只留 acute mask"这条自我约束很好(建议直接当默认,见 P9)。
8. **worker prompt 的 torque authority 类型系统**(NOMINAL_PD/CLIPPED/SOLVER/ESTIMATE/UNAVAILABLE)——恰好命中 v21B 的 authority 现实,是 bundle 里最"接地"的设计。
9. **process 纪律**(No fake RP0 / no missing-to-zero / no hidden control / 阈值先冻结后看数 / raw producer 不写 PASS / attempt limits)——与本项目 v20-v22 演化出的证据纪律一致。
10. **LT-23-08(learned sparse posture gate)= ledger C 路线第 3 步**,v23 恰好是给它造 E0/E1/E2 testbed——研究主线连续性成立。

---

## 3. 必须修正项(Disagreement / Patch,按优先级)

### P1【factorial 完整性】D 轴混入 arm effort,必须拆开
设计 §6.2 把 `τ_boundary-calibrated` 写进 D1 定义("提高 stiffness/resistance…并使用 τ_boundary-calibrated"),D0 未提 effort;contract `formal.groups` 里没有任何 effort 字段。若 D0 cells 用 ARM_V20、D1 cells 用降后 τ,则 G1↔G5 等"Door regime 主效应"混入 arm 能力变化,2×2×2 变成隐性 2×2×2×(τ),不可归因。
**修正**:effort profile 是全 8 cell 统一冻结常量,写进 contract(`formal.arm_effort_profile: P0_FREEZE_REQUIRED`);D0/D1 只允许 door 参数不同。我进一步建议这个统一值就是 τ_boundary-calibrated(理由见 P3)。

### P2【科学 gate】E0/E1 分类若用 acute 探针会近乎失效(本地证据)
v22 P0-B 独立干预标签:**37 POSTURE_NEEDED / 3 NOT_NEEDED / 8 AMBIGUOUS**;v18 P2 pitch-zero 2/16。对一个 0.4 饱和的 warm policy 做 acute 姿态移除几乎处处失败 → 用 A0 + acute FULL-vs-RP0 分类,E0 近空、E1≈全集,标签测的是 **policy 习惯**,不是门属性。设计 §6.1 的 E0/E1 定义(以 FULL vs RP0 差为准)未指明用哪个 policy 判——这是云端看不到运行证据造成的最大科学 gate 缺陷。
**修正**:P0 期分类必须 physics-first:用 door atlas 的 free-return/fixed-torque 响应探针(v22 `characterize_hinge_dynamics.py`/`dynamics_probe` 已有先例)估计 τ_required 曲线,与 τ_calibrated 下的 arm 可用切向能力比较,得到 E 区初标;acute 探针只作辅助证据。E 区标签声明为 provisional,G4/G8(chronic RP0)训完后做 post-hoc re-adjudication。裁决规则引用的 E 区条件同步改为"P0 physics 初标 + chronic 复核"。

### P3【可证伪性】E2 走 door-side 加码,本地证据表明大概率撞模型分辨率墙
三条本地证据链:v22 `higher_torque_probe` 25/30 N·m **BELOW_RESOLUTION**、hinge max_force 全局上界 24 N·m、ledger v15"推门=形封闭,12 N·m 内 arm 全覆盖 + 弹簧上限>12 仅在真实限位改造之后(否则死轴)"。ARM_V20(100 N·m×6)下靠继续放大 door 参数造 E2,最可能落 `V23_DOOR_MODEL_INSUFFICIENT_FOR_E2`,H4 不可证伪。
**修正**:(a) 全矩阵统一用 τ_boundary-calibrated(降 arm 而非无限抬门——这正是 ledger 自 v15 排期至今的"真实限位轮"该做的事);(b) 把"E2 在 τ_calibrated 下是否可实现"设为 P0 的显式 GO/NO-GO gate,只挂 H4,不阻塞矩阵其余部分;(c) A0 在 τ_calibrated 下重评,量化 effort 变化对 warm 行为的冲击(全 cell 共享该冲击,内部对照不受损)。

### P4【工作量与科学定义】P0.6 "恢复早期 reward" 是伪命题;真正的决定是六个 v22 conditional 项的去留
本地事实:base registry(`reward_door_open_a2_base.yaml`)里早期 dense reward **从未被移除**——`walk_to_door 5.0`、`pregrasp_target_distance 6.0`、`gripper_handle_orientation 3.0`、stage2 grasp 全套(1.0×4 等)、`stage 1.0`、`complete 4.0` 全部健在;v13→v22 只 zero 了 `push_door_handle`(被 unlatch_hold/hold_and_drive 替代)与 `push_door_force`。**现行 registry 结构上已是 scratch-capable**。
Bundle 完全没讨论的才是难点:v22 新增的六个项——`penalty_a2_v22_excess_posture -2`、`penalty_a2_v22_posture_saturation -16`、`a2_v22_posture_feasibility +0.5`、`a2_v22_clearance_success +4`、`a2_v22_controlled_fling +2`、`penalty_a2_v22_unsafe_release -8`——在 v23 common reward 里留不留?
**修正建议**:撤三留三。撤 `excess_posture`/`posture_feasibility`(依赖已被裁定 OVERACTIVE_OR_VACUOUS 的 posture_need 分类器)与 `posture_saturation`(-16 的价格会污染 H1/H5 的"自然饱和倾向"测量;价格弹性假说已两次被否);留 `clearance_success`/`controlled_fling`/`unsafe_release`(outcome/安全项,不依赖分类器,维持 v22 行为连续性)。撤价格后 warm cells 的饱和可能反弹——这本身就是 H1 的测量对象,不是回归。此决定必须进 `V23_COMMON_REWARD_FREEZE` 并配 stationary-rent audit(P0.6 的 audit 要求保留)。

### P5【科学 gate 落地】torque telemetry 与 E2 "high effort" 判据必须绑定 authority 现实
v21B 已把 `data.computed_torque`(nominal PD)/`data.applied_torque`(clipped 估计)接进 evidence 累积器(`door_open_a2_base.py:7546-7548`),且终态 authority = `ESTIMATE_ONLY_ACTUAL_PHYSX_DRIVE_FORCE_UNAVAILABLE`;R10 census 在 heavy16 上 raw 未裁剪 PD 需求 **62.5% ≥100 N·m**(right-censored)。含义:(a) P0.1 大半管线已存在,应扩展复用而非重建;(b) "τ ratio ≥0.90" 在 ARM_V20 下的 heavy 门上**现在就近乎恒真**(commanded 侧),E2 certificate 的 high-effort 判据必须显式定义在 CLIPPED_COMMAND_TORQUE(执行侧)并与 P0.3 Kp/clip audit 联动,否则该条件无区分度;(c) P0.2 ladder 用行为退化选 τ 是对 v21B census 失败(right-censor)的正确修正——应先挖 v21B 既有 artifacts(census/heavy16 manifests)预收窄 rung。

### P6【可实现性】atlas cell A3(breakaway/friction proxy)没有旋钮
`env_rand/door.py` 全部可随机化轴 = hinge `damping/stiffness/max_force` + handle `max_force`;**无任何 Coulomb/stiction/breakaway 参数**(LT-23-02 正是要补这个)。A3 按字面不可实现。
**修正**:A3 重定义为 proxy(近关角高 stiffness + max_force 组合模拟起动阻力)并明确标注 proxy 语义,或从 atlas 删除、把"breakaway 轴"整体移入 LT-23-02。planner freeze 时不得给 A3 留字面参数位。

### P7【身份冻结】warm-start 候选 × D0 必须 co-freeze,且两者纠缠
v22 以 NO_RELEASE 收口,留三候选:G1:step1250(Wave-1 配置,**注释明确"keeps the v21 door distribution"**,固定 damping 50/stiffness U(1,10);pooled goal 46/48、clearance 29/48 最佳)、G4:step1750(Wave-2 H0-H2 mixture 训练;47/48、9/48)、G5:step0750(Wave-3 body-assist 配置;47/48、16/48)。选谁,"D0=当前门"的语义就完全不同。
**修正建议**:warm = **G1:step1250**(主线行为谱系、无 body-assist shaping、clearance 最好),D0 := G1 saved config 里它自己的训练门分布(source-locked manifest),把 G4/G5 记为 alternates。这样 H1"继承"测的才是行为继承而非门分布漂移。

### P8【process gate】admission 缺训练级 smoke 与 scratch pilot
Phase 7 只有"1-env end-to-end + 8-env mixed semantic runner",低于本地 durable lesson(v20 R3:5 个 runtime bug 全部只在真训练暴露;此后规约=铺开前必跑 `64 env × 10 batch` smoke)。且 scratch 史严峻:v10(4×scratch,1000 批)、v12(4×scratch,3000 批)全 0/16 goal(均在 grasp-gate 修复前;修复后 scratch 从未试过),ledger 记"scratch 3/4 落错 basin"。contract 只允许 1 次事后 scratch extension wave。
**修正**:(a) admission 增加 per-cell-type(warm-FULL/warm-RP0/scratch-FULL/scratch-RP0)`64 env × 10 batch` 训练 smoke,写入 DAG;(b) Wave S0 前加 1-GPU scratch pilot(D0 FULL,~500 batches,staged-reset 开),以 stage-reach 里程碑(stable-grasp 率、stage3 进入率)作 GO/NO-GO——比事后烧掉 4 cell × 2 wave 再补 extension wave 便宜得多。若 pilot 失败,矩阵可先退化为 warm/HR × D0/D1 × FULL/RP0,common reward 修完再上 scratch。

### P9【可实现性】matched mid-episode intervention 默认降级为 forward-only;ΔJ_φ/FP_φ 需按此重写
PhysX/IsaacLab 富接触抓握态的 exact state clone + recurrent clone 在本仓库不存在,v22 全部因果探针(P0-B)都是 episode 级 forward 干预 + scenario CRN 配对。设计 §9.2 的 ΔJ_φ(s)、FP_φ 按 mid-episode state branching 定义,§5.8 又要求"对所有 checkpoint 运行全部干预"(与 contract 的 route_b 限定 selected checkpoints 矛盾)。
**修正**:把设计 §11.2 的 fallback 升级为 plan of record——干预 = stage-triggered forward switching(如 BASE0@GRASP 在 stable-grasp latch 处切换)+ CRN scenario 配对;ΔJ_φ 重定义为配对 episode/窗口差;干预套件只跑 Route B selected checkpoints + 小规模每波抽样;`STATE_CLONE_NOT_SUPPORTED` 直接预填,LT-23-05 承接完整版。

### P10【统计功效】5pp non-inferiority on pooled48 是伪精度
5pp ≈ 2.4/48 门;本项目从 v19 起明确记录"48-door 不构成 statistical proof";v20 同配置 seed 差已达 1.8pp 量级。
**修正**:margin 写成门数并配 exact binomial CI(如"pooled48 差 ≤3 门 且两 seed 同向 且 holdout64 不反向");2-seed cell 对照一律按 estimation 报告(seed-wise effects + CI),任何要驱动 v24 设计的 decisive claim 触发 Wave C 第 3 seed。Route-A canonical16 仅作机械选点,不做假设检验(现行定位正确)。

### P11【分层口径】按 realized dynamics 分层,不按 intended bucket
v22 `bucket_reproduction`:H0 抽样 16 → realized 响应类 CORE 7 / FAST_REBOUND 6 / HIGH_DAMPING 3(MISMATCH 状态)。bucket ID 不能控制响应类。
**修正**:v23 所有 E 区/桶条件分析以 per-episode realized dynamics telemetry(per-asset damping/stiffness/max-force + 响应测量)分层;intended bucket 只作抽样器。schema(step trace/episode record)已含 scenario/dynamics 组,补 realized-response 字段即可。

### 次要项(P12,不阻塞)
- **head-reset 对照被静默丢弃**:云端第一轮自评"成本更低、因果解释更清晰"的 B 组(只重置 final layer 的 pitch/roll 两行 + 对应 log_std)在正式 bundle 消失。8-cell factorial 现已把 G2/G6 用进 §7.1 对照与 H3(G5vsG6),不必动矩阵;建议 head-reset×D0/D1 作为 Wave C 优先 cell(先于第 3 seed),补 H1 的机制定位(输出头习惯 vs recurrent 表征习惯)。
- **训练目录布局** `base_v23/seed0/G1` 与 log-layout memory 契约核对一次(v22 用 `base_v22/G1` 无 seed 层)。
- **v22 评测脚本复用**:worker prompt 默认禁止 import v22 posthoc 脚本;建议 planner 显式批准 source-locked 复用(`m22.py`/`route_a_*`/`pooled48` 家族),重写反而引入新 bug 面。
- **D1 novelty 不对称**:warm(G1)没见过 hinge randomization,scratch 也没见过——对 H1 公平;但 G5/G7 的 D1 适应差异要在解释时记住 warm 的 distribution novelty。
- **补一条预注册分析**:clearance 失败率 conditional on release/traversal 时的 posture 饱和状态(按 realized 桶配对)——v22 真正挡 release 的是 clearance(29/9/16 of 48),v23 虽是诊断轮,这条零成本 telemetry 分析能把姿态问题与 release 主线连起来。v23 应显式声明预期终态是 `V23_RESEARCH_PASS_NO_RELEASE` 家族,不追 release。

---

## 4. 对用户五点原始问题的最终立场(与云端结论的差分)

1. **加 stiffness/max-force/摩擦/真实力矩余量**:同意为主线,但本地证据(P3/P5/P6)表明可行路径是"**降 arm 到 τ_calibrated + door 参数在已验证分辨率内扫**",而非继续抬 door;摩擦轴今天没有旋钮,只能 proxy。
2. **scratch 对照**:同意立项(与 ledger 预注册规则衔接成立),但必须加 pilot gate(P8);预期最可能结果是 `V23_SCRATCH_CURRICULUM_INSUFFICIENT` 与 H1 conditional——这不是失败,是预注册分支。
3. **scratch + RP0 证明 arm alone**:同意云端的改名(no-active-posture)与 BASE0 补层;补充:G4 成立只对 D0 分布成立,且"policy-relative vs task-relative"边界要靠 chronic(G4/G8)而非 acute 判(P2)。
4. **动力学综合判断替代 height reward**:同意否决 height prior;v23 只测量不治疗是对的;机制(gate/residual)在 LT-23-08 与 ledger C 路线重合。
5. **coupling critic + counterfactual**:同意方向、同意推迟;比云端更进一步——Δ_C 的 R10/R00 分支(抓握态换 neutral arm)会被 grasp 崩塌主导,v23 内连 shadow 版都应以 forward-only 边际量为限(P9)。

---

## 5. 建议的 planner 决议输出(模板)

```text
DECISION = APPROVE_WITH_BOUNDED_PATCH
FORMAL_TRAINING_READY = false
WORKER_IMPLEMENTATION_MAY_START = yes(P1-P7 冻结进 manifest 后)
SCIENTIFIC_MATRIX = retain(8-cell 不动;head-reset 进 Wave C)
LEGAL_PHYSICAL_GPUS = {0,1,2,3,4,5,6,7}(8× RTX A6000 已验证空闲)
WARM_START = logs_rl/.../base_v22/G1 step1250(建议;SHA-256 待 planner 冻结)
PRIMARY_BLOCKER = arm effort profile 未定义为全矩阵常量(P1);E0/E1 分类未 physics-first(P2)
```

Patch 表 = 本文 P1-P11;P0 顺序建议:P0.1(复用 v21B telemetry)→ P0.3(Kp/clip)→ P0.2(ladder,预收窄自 v21B)→ P0.4(atlas,A3 改 proxy)→ E 区 physics-first 初标(P2)→ P0.6(common reward,六项 v22 term 决议)→ P0.7(RP0)→ P0.8(state bank/forward interventions)→ per-cell-type 训练 smoke + scratch pilot(P8)→ admission。
