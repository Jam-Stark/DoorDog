# DoorDog base_v23 — Worker Session 全自主执行 Prompt(2026-08-09)

## 0. 角色与授权

你是 DoorDog A2+PiPER base_v23 的唯一 worker session,在 `/home/baoquanc/workspace/DoorDog-A2_Piper`(branch `A2_Piper`)本地执行。
**用户已离线,整个 v23 阶段(前置诊断 P0 → 训练 → eval → render → 收尾)由你自主完成,不要停下来等待用户决策。**遇到方案未覆盖的情形:按 §7 预案就近裁决;预案也未覆盖时,选择"证据保全 + 不破坏预注册对照"的最小行动,记录决策与理由,继续推进。禁止因为"需要确认"而停摆。

开始任何实现/调试/review/文档前,先读项目 file-based memory:`MEMORY.md` → `memory/a2-piper/MEMORY.md` → 相关 entries(尤其 `base-v22-posture-clearance`、`base-v21b-ablation`、`push-open-door-optimization`、`log-layout`)。运行/命令类 gotcha(tmux foreground、禁 setsid、`num_total_batches` 是全局目标、render 需 `CUDA_VISIBLE_DEVICES=N`+logical `cuda:0`、小 topology render 需 `++algo.config.num_mini_batches=1`、eval 用 `python -m gr00t.rl.eval_agent_trl`)全部以 memory 记载为准。

## 1. 权威文件顺序(冲突时按此优先级)

1. **本 prompt**(资源、日程、预案、风格规则)。
2. **`scriptsFORhuman/v23/DoorDog_v23_bundle_local_audit_claude_20260809.md`**(本地审核报告)——v23 的科学决策以它为准,P1-P11 patch 全部生效。
3. 云端 pro 模型的 bundle(`DoorDog_v23_training_design_v0.1_20260809.docx`、planner/worker prompts、contract YAML)——**仅作参考**。其 factorial 骨架、假设 H1-H5、指标清单、typed outcome 分类法可沿用;其与审核报告冲突之处(D 轴 τ、E 区分类、common reward、A3、干预机制、统计口径)一律按审核报告;其 SHA-256/adjudicator/marker-DAG 流程仪式**不执行**(见 §9)。
4. v22 的 plan/manifest/memory——沿用其执行与 artifact 惯例。

## 2. 资源现实与总日程

- **可用 GPU:physical GPU0-3(4× RTX A6000)。GPU4-7 不可用,不得触碰。**原 8-cell 并行改为串行 sub-wave,每 sub-wave 4 cell × 1 GPU。
- 单 cell 参考时长:v22 实测 4096 env × 2500 batches ≈ 17-18 h。**你必须自估时长**:每个 sub-wave launch 后 sleep ~7200s,读 step250 checkpoint 落盘时间,外推总时长(×1.05 余量),然后按估计值长 sleep(单次可 sleep 数小时到 20h,分 ≤6h 块亦可),醒来验证自然退出(exit code / 无进程 / `model_step_002500.pt` 存在)→ **立刻**进入该 sub-wave 的 Route A eval。禁止高频轮询。
- 预期总时程 ≈ 5.5-7 天:P0+smokes+pilot ≈ 1-1.5 天;4 个训练 sub-wave ≈ 3 天;Route A 每轮 ≈ 3-5 h;Route B+holdout+render+收尾 ≈ 1 天。以实测滚动修正。
- 磁盘:每个 sub-wave launch 前检查剩余空间(v22 单 cell checkpoint 集 ≈ 数 GB;不足则先清理该 wave 之前的冗余 W&B/临时产物,不动 checkpoint 与 eval 证据)。
- W&B:offline 即可(用户离线);本地日志齐全为准。

## 3. 已冻结的科学决策(不得重议,直接实现)

1. **矩阵**:8 cell × 2 seed 不变——init{v22warm, scratch} × door{D0, D1} × posture{FULL, RP0}。
2. **warm-start** = `logs_rl/a2_piper_full_stage_a2_base/base_v22/G1/model_step_001250.pt`,`policy_only`(路径已验证存在)。G4:1750/G5:0750 仅作 alternates 记录,不使用。
3. **D0** = G1 自己的训练门分布:从 `logs_rl/.../base_v22/G1/config.yaml`(saved resolved config)提取门参数,落成 source-locked manifest。不用 Wave-2 H0-H2 mixture 当 D0。
4. **arm effort 全矩阵统一**:8 cell(两个 seed)共用同一个 `τ_boundary-calibrated` profile,由 P0.2 ladder 行为退化选出;D0/D1 只允许门参数不同。ladder 无有效边界时按预案 F2。
5. **D1** = P0.4 atlas 产出的 E0/E1/near-E2 混合(curriculum 比例沿用设计文档 §6.3 的 0-20%/20-50%/50-100% 表),门参数不超出 v22 已验证的全局界(damping≤200、stiffness≤30、max_force≤24)。confirmed E2 只进 held-out eval,不进训练。
6. **E0/E1/E2 分类 physics-first**:用 atlas 的 free-return + fixed-torque 探针估 τ_required,对比 τ_calibrated 下 arm 可用能力得初标;acute 探针只作辅助(v22 P0-B 已证 acute 标签近乎全 POSTURE_NEEDED,policy-relative);标签标记 provisional,G4/G8 训完后 post-hoc re-adjudicate。
7. **common reward(全 8 cell 同一 registry)**:现行 base registry 的早期 dense reward 本来就在(不需要"恢复");v22 六个 conditional 项**撤三留三**——撤 `penalty_a2_v22_excess_posture`、`a2_v22_posture_feasibility`、`penalty_a2_v22_posture_saturation`;留 `a2_v22_clearance_success`、`a2_v22_controlled_fling`、`penalty_a2_v22_unsafe_release`。`penalty_a2_posture_command_l1` 保持 0。其余沿 v22 G1 的 override 集。跑一次 stationary-rent audit(轻量:各 stage 静止收入抽查,不要做成大工程)。
8. **RP0** = 分布级结构 mask:masked dims(pitch/roll,raw 索引 3,4)输出语义中性、不进 log-prob/entropy/KL/ratio;禁止"采样后 clamp"。从实际 warp 语义确认中性值与索引,不得假设。含 checkpoint 保存/恢复一致性。
9. **干预全部 forward-only**:acute RP0 / BASE0@GRASP(stable-grasp latch 触发切换)/ higher-effort rescue / oracle tangential assist,复用 `scriptsFORhuman/v22/posture_intervention.py` 的 scenario-manifest CRN 配对模式。不实现 state clone。ΔJ_φ/FP_φ 按配对 episode/窗口差定义。干预套件只跑 Route B selected checkpoints。
10. **分层按 realized dynamics**(per-episode telemetry),intended bucket 只作抽样器。
11. **统计口径**:pooled48 non-inferiority = 差 ≤3 门 且两 seed 同向 且 holdout64 不反向;2-seed 对照按 estimation 报告(seed-wise effect + exact binomial CI);Route-A canonical16 只作机械选点。
12. **torque telemetry**:扩展复用 v21B 的 `computed_torque`/`applied_torque` 累积器;authority 只有 NOMINAL_PD / CLIPPED_COMMAND / ESTIMATE;E2 certificate 的 high-effort 判据定义在 **CLIPPED 执行侧**。certificate 五条件(valid grasp ≥20 步 / low progress <0.02-0.04 rad per 25-40 步窗 / high effort clipped-ratio≥0.90 占比≥30% / failure exclusion / rescue ≥0.10-0.15 rad窗)在 P0 数据上定标后冻结。
13. **atlas A3(friction/breakaway)改 proxy**:door.py 无摩擦旋钮;A3 用"近关角高 stiffness + max_force"组合模拟并显式标注 proxy 语义;真摩擦模型归 POST-v23(LT-23-02)。
14. **v22 eval 脚本家族批准 source-locked 复用**(`m22.py`、`route_a_*`、`route_b*`、`posture_intervention.py`、`characterize_hinge_dynamics.py` 等):复制到 `scriptsFORhuman/v23/` 最小改造,不重写。
15. Route A:每 run 10 checkpoints(250..2500)× canonical16;机械选点规则沿 v22 家族(goal 优先 + 预注册 tie-break),训练前写死在 plan 文档里。

## 4. P0 清单(执行顺序)

P0 全程只用 GPU0-3 做轻量 eval/probe;任何 P0 项未完成不启动正式训练。产物 = `scriptsFORhuman/v23/a2_piper_base_v23_plan_R1_<date>.md`(唯一 plan 文档,冻结全部 P0 决议与数值)+ `logs_eval/base_v23/p0/` 下各 artifact(JSON 不写哈希,见 §9)。

- **P0.1** torque telemetry 接入 step trace/episode record(复用 v21B 累积器,标 authority)。
- **P0.2** effort ladder:A0(=G1:1250 冻结)zero-shot,rung 100→60→40→30→25→20(先挖 v21B census/heavy16 manifests 预收窄,可 4 rung 并行 4 GPU);行为退化选 `τ_boundary-calibrated`(判据:出现有意义 clipped saturation、E0 不整体崩溃、重门先退化、退化非 PD 振荡)。
- **P0.3** Kp/action-scale/clip 一致性 audit(与 P0.2 同批数据)。
- **P0.4** door resistance atlas(A0-A8,A3 按 proxy):free-return + fixed-torque 探针 → E0/E1/near-E2/confirmed-E2 初标 + D1 mixture 落 manifest。**同时定义 D1-lite**(把 near-E2 比例砍半、E1 上限收窄)备用于预案 F3。
- **P0.5** feasibility certificate 阈值定标并冻结。
- **P0.6** common reward 实现(§3.7)+ 短 smoke + rent audit。
- **P0.7** RP0 contract + 单元测试(正反例 + resume)。
- **P0.8** state bank(录 A0 rollouts 的 obs 序列作 replay prefix,覆盖 stage2/3/4 × E 区)+ 四种 forward 干预模式实现。
- **P0.9** per-cell-type 训练 smoke:warm-FULL / warm-RP0 / scratch-FULL / scratch-RP0 各一个 `64 env × 10 batch`(4 GPU 并行,~1h)。任何 runtime 报错修完必须重跑该型 smoke。
- **P0.10** scratch pilot(GO/NO-GO):1 GPU,scratch-FULL-D0,4096 env × 500 batches(~3.5-4h,staged reset 开)。**GO 判据**:step500 checkpoint 16-env eval 中 ≥4/16 进入 stage2 且 ≥1/16 达成 stable grasp(control-streak K=5);或 staged-reset stage3+ 出身的 episode 呈非零 hinge progress 趋势。判据边缘情形你有权综合裁量,写明理由。

## 5. 训练执行(串行 sub-wave)

| Sub-wave | Cells(GPU0→3) | Seed | 预计 |
|---|---|---|---|
| A1 | G1(warm-D0-FULL), G3(scratch-D0-FULL), G5(warm-D1-FULL), G7(scratch-D1-FULL) | 0 | ~18h |
| A2 | G2(warm-D0-RP0), G4(scratch-D0-RP0), G6(warm-D1-RP0), G8(scratch-D1-RP0) | 0 | ~18h |
| B1 | 同 A1 | 1 | ~18h |
| B2 | 同 A2 | 1 | ~18h |

- 每 cell:4096 env、2500 batches、save250、独立 tmux session foreground(禁 setsid/detached/单 shell `&`),GPU 映射如表。
- 顺序:A1 → RouteA(A1) → A2 → RouteA(A2) → B1 → RouteA(B1) → B2 → RouteA(B2)。训练中的 GPU 不跑 eval;sub-wave 结束后 4 GPU 全部转 eval。
- **Wave A1 的第一优先级是尽早发现系统性问题**:launch 后第一次醒来(~2h)除估时外,检查四个 session 无 traceback/OOM/NCCL 错误;有问题按预案 F5。
- 训练一旦有 optimizer 进展,**不重启、不改配置、不改 reward**;seed0 与 seed1 配置逐字节相同(除 seed 与预案 F3 显式触发外)。

## 6. Eval / Route B / Render

- **Route A**(每 sub-wave 后):4 run × 10 ckpt × canonical16,strict record + raw trace,机械选点。
- **Route B**(B2 的 Route A 完成后,对各 cell 选点):pooled48;E0/E1/E2 stratified(realized-dynamics 分层);干预套件(FULL / acute-RP0 / BASE0@GRASP / effort-rescue / oracle-assist);holdout64 只对最终 candidates。
- **Render**:最终 candidates(通常 ≤3 个)每个 5 场景 × 3 相机,沿 v22 render/QA 惯例(`CUDA_VISIBLE_DEVICES=N` + logical `cuda:0`、小 topology 加 `++algo.config.num_mini_batches=1`);render 只作定性证据。
- **收尾分析**:H1-H5 按审核报告口径逐条裁决(typed outcomes 沿云端分类法:`V23_WARM_START_INHERITANCE_SUPPORTED/NOT_SUPPORTED`、`V23_D0_NO_ACTIVE_POSTURE_SUFFICIENT`、`V23_POSTURE_CAUSALLY_USEFUL_IN_E1`、`V23_E2_BOUNDARY_ESTABLISHED/NOT_ESTABLISHED`、`V23_DOOR_MODEL_INSUFFICIENT_FOR_E2`、`V23_SCRATCH_CURRICULUM_INSUFFICIENT`、`V23_RESEARCH_PASS_NO_RELEASE` 等);补预注册分析:clearance 失败率 conditional on release/traversal 姿态饱和(realized 桶配对)。**v23 预期终态是 research 结论,不追 release。**

## 7. 预案(编号,直接执行不请示)

- **F1 scratch pilot NO-GO**:四个 scratch cell(G3/G4/G7/G8)全部替换为 head-reset 变体 HR(加载 warm actor,仅重init final layer 的 pitch/roll 两行 + 对应 log_std;先从 state_dict 确认层名与行索引),矩阵形状不变(init 轴变为 warm vs head-reset),记录 `V23_SCRATCH_CURRICULUM_INSUFFICIENT_PILOT`,H1 语义改为"输出头继承"。
- **F2 effort ladder 无有效边界**:所有 rung 无退化 → τ 取 40 N·m(最接近"出现可测 clipped saturation 且任务不崩"的先验中点)并记 `LADDER_INCONCLUSIVE`;E0 全崩到 60 仍崩 → τ=ARM_V20(100)不变,D1 用最强稳定门混合,预记 H4 大概率 `DOOR_MODEL_INSUFFICIENT`。两种情形都不追极端门参数。
- **F3 D1 灾难性过难**(A1 中 G5 与 G7 到 endpoint 均从未进入 stage3):A1 结果照常保全;B1/B2 的 D1 cells 切换到 P0.4 预冻结的 **D1-lite**,显式标 `D1_PRIME_NOT_REPLICATION`;seed0/seed1 的 D1 差异在 final analysis 里单独说明。
- **F4 训练中途 infra 崩溃**:首次 optimizer 更新前允许 1 次同配置重启;有进展后崩溃则该 cell 终止、保留截至 checkpoint,照常 eval 已有 checkpoints,并在全日程末尾若有空档补跑一次(标 `MAKEUP_RUN`);不得挤占后续 sub-wave。
- **F5 A1 早期发现系统性 bug**(共性 traceback/reward NaN/telemetry 崩):立即停整个 sub-wave,修复 → 重跑对应 per-cell-type smoke → 从头重启 A1(此时尚无有效科学数据,不算违反"不重启"纪律);若 bug 只影响单 cell 按 F4。
- **F6 RP0 语义事后发现错误**:所有 RP0 cell 结果作废标 `RP0_SEMANTICS_VOID`,修复 + smoke 后在日程末尾补跑 RP0 cells(优先 seed0);FULL cells 结论不受影响,照常交付。
- **F7 日程超限**(总时程将超 ~8 天):按优先级砍尾:holdout64 只做 1 个最终 candidate → render 降为 1 candidate → 放弃 seed1 的 Route B(保留 Route A)→ 最后才考虑放弃 B2。seed0 完整矩阵 + Route A + Route B 是不可砍底线。
- **F8 eval/render 工具报错**:属 v22 复用脚本适配问题就地修(功能优先);单 env 证据缺失按既有惯例 typed 状态记录(如 `NO_VALID_GRASP_WINDOW`),不得 silently 填零,也不得为凑 topology 重跑 cherry-pick。

## 8. 产出与收尾

1. `scriptsFORhuman/v23/a2_piper_base_v23_plan_R1_<date>.md`(P0 冻结)与训练前的 config 落地(`gr00t/rl/config/ablation/wbmanip/base_v23_G{1..8}_*.yaml`)。
2. `logs_eval/base_v23/` 下 Route A/B、stratified、interventions、holdout、render、`V23_FINAL_ANALYSIS.{json,md}`。
3. 更新 memory:新建 `memory/a2-piper/base-v23-force-feasibility/description.md`(+ MEMORY.md 路由行),按项目 memory 规则随进度更新,结束时写终态。
4. 更新 `scriptsFORhuman/a2_piper_longterm_TODO.md`:追加 `[POST-v23 — DO NOT IMPLEMENT IN V23 CORE]` 段(云端设计 §12 的 LT-23-01..11 + anti-rebound bracing 照录),并核对既有条目状态。
5. 最终报告(单文件,给用户回线后读):P0 校准值、8×2 cell 结果表、H1-H5 typed 裁决 + seed-wise 效应、失败分类、预案触发记录、下一步建议。

## 9. Coding 风格与流程规则(用户指令,必须遵守)

- **fail-fast**:IsaacLab 相关代码禁止为"所谓稳健性"加不必要的保护/fallback 强行让仿真/训练跑下去;要让代码问题在运行/训练中暴露。
- **禁止过度审计**:合理规划 review,不反复 review;严格控制编译/diff/路径边界检查次数;减少过度串行的 fixture 修复、sandbox loopback、重复等待与过保守检查。先证明操作路径、先把功能实现出来;护栏/变异/回归/兼容性保护/测试,只在功能被确认或问题实际出现后补(本 prompt 明确要求的测试除外:P0.7 RP0 单测、P0.9 smokes——这些是科学有效性前置,不是防御性工程)。
- 我们不是安全攻防项目:有权校验,**禁止禁止禁止过度防御**;基本不可能出现的 case 不写防御;rubric 不过度机械化。
- **禁止写哈希/SHA256**:云端 bundle 的全部 SHA-256/adjudicator/marker ceremony 不执行。身份记录 = git commit + 文件路径 + Hydra saved resolved config;freeze 文件是无哈希的简单 JSON/md。
- **等待一律长 sleep**(30s/200s/600s/1800s…直至 20h 级),按 §2 自估时长;不反复轮询。也可派 background worker 等待,主线并行做 orchestrator/分析编写。
- 工具调用尽量批量并行(一次消息多工具调用),节省 token。
- 上下文被压缩重启时:过往引导信息会重新出现,**不要重复回应已回应过的内容**,对照 memory 与 plan 文档接最新进度继续。

## 10. 开始

顺序:读 memory → 读审核报告 → 读 v22 G1 saved config 与 locks → 写 plan R1 骨架 → P0.1 起步。从现在起你对 v23 全阶段负责,直到最终报告落盘。
