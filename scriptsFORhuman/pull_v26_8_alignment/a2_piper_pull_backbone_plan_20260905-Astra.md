# Pull 迁入 v26-8 C 同构 backbone 的计划 — Astra

## 1. 目标与状态

目标是复用 push 已验证的 bilateral acquisition/scaffold 工程范式，重新建立 pull 的双侧自然起点全链路；不是把 push checkpoint 当 pull Teacher，不重启 H18 one-shot head 扫描，也不继承已判 K_REGRESSED 的自适应惩罚路线。

状态：2026-09-05，PROPOSAL_FOR_OWNER_COMPARISON。Owner 当前请求交付方案与开工 prompt；本轮只读 pull worktree，没有修改、训练、commit 或向远端发出执行指令。执行入口见[配套 prompt](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/pull_v26_8_alignment/a2_piper_pull_backbone_start_prompt_20260905-Astra.md)。

本地 pull：/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0。参考 push：/home/baoquanc/workspace/DoorDog-A2_Piper。远端负责会话：codex://threads/01a05113-6e6d-70e0-a017-a733d25d1641；已读到其历史收尾，未获得当前远端 runtime artifact。

## 2. 当前困难不应归结为“LEFT/RIGHT 必然学不会”

pull 已有 Stage0–2 grasp winner：pull_lr_grasp_h450_xseg_resume_seed2/model_step_000250.pt，历史自然固定两侧 strict K5 各 125/128；这不证明 opening 或 complete。H16 存在 acquisition 入场但 press-equilibrium 不开门的运行；H17 后续两 seed screen 失败；H18-B0 两次 RIGHT16 的 E4/E5 为 0。远端最后明确停止新实验，Gate-A B0 后续没有运行。[grasp memory](/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/memory/a2-piper/pull-lr-bilateral-grasp/description.md:23)、[full-stage memory](/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/memory/a2-piper/pull-lr-full-stage/description.md:149)、[远端 handoff 的本地副本](/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/scriptsFORhuman/pull_lr_full/PULL_LR_FULL_HANDOFF_20260901.md)

因此需要先拆开三个问题：物理夹持能力及镜像目标是否一致；Stage2→3 的接管有没有改变动作语义/状态分布；解锁后是否有正确的 pull opening 奖励和几何路径。push v26 的 45N capability、物理目标帧修正与 native bilateral acquisition 是可迁移资产；不能据此宣称已找到 pull 失败的唯一原因。

## 3. 共享什么，在哪里分叉

两边 native 主干的输入形状相同并不保证语义相同；必须逐字段核对顺序、坐标系、单位、RMS、历史状态和动作执行。

| 层 | 共同目标合同 | pull 必须保留的差异 |
|---|---|---|
| Actor/critic | native 135-D actor / 140-D critic，2-layer LSTM 256，MLP 512/256/128 | 不混入 release-mode、canonical absolute、taskspace 专用 head |
| Action | 5 个 A2 command + 6 个 arm action + 1 个 gripper；同顺序/尺度/DeltaAction 执行 | 不在 Stage3 把相同 raw vector 改读 absolute joint target |
| 观测 | 相同字段顺序、坐标系/单位、side/IO 语义，teacher privilege 明确 | pull 的 IO、相对几何数值自然不同；相同 schema 不要求相同值 |
| Capability | v26 C 的 finger 45N、Kp/Kd=1300/32、M39 对应的手部材料/接触设置 | 远端 asset/actor readback 才证明生效；不是实机规格认证 |
| LEFT/RIGHT | native per-env side，物理 handle/pregrasp target 镜像 | 禁止仅反射 actor 输入而物理目标仍用 RIGHT offset |
| Stage0–2 | approach/pregrasp/stable grasp 的语义、自然起点评估 | IO=in、fixture、入手方向、站位、切向与 tension 方向从 reset 就必须正确 |
| Stage2→3 | 持续有效抓握的入场证据 | 已有 tensile_proof 是 pull 专属强准入；保留并另报 common K5，不悄悄删掉 |
| Stage3–5 | unlatch/open/clearance/traverse 的任务骨架和 telemetry 词义 | 受拉接触、hinge 开向、绕门路线、持门与释放不同，不能给 push reward 简单乘负号 |

“分叉在 Stage3 之后”适用于大部分行为目标，不适用于门的物理几何和输入信息。尤其 IO 是已有 privileged bundle 的第八个字段；从 episode 开始就存在。未来部署 actor 是否可直接看到 IO 是另一个观测问题，不在此次迁移中冒充已解决。[push obs](/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/config/obs/wbmanip/door_open_a2_base.yaml)、[pull obs slicing 历史示例](/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/gr00t/rl/trl/modules/pull_v6_bilateral_stage3_canonical_actor.py:18)

## 4. 最小修改面

执行团队先在远端确认当前 checkout、本地未提交改动、有效入口与依赖。以函数/配置项为单位移植共同能力，禁止整文件覆盖 door_open_a2_base.py；两边都有必须保留的实际路径。

建议新增 pull_v26_aligned 命名空间，文件清单在开工时写入一份短 execution contract：

- gr00t/rl/config/ablation/wbmanip/pull_v26_aligned_common.yaml 与 seed/stage/eval overlays：native bilateral、4096 env、共同 capability、C scaffold、pull IO/fixture。
- gr00t/rl/envs/door/door_open_a2_base.py 中缺失的 capability/镜像目标 wiring；pull-only mechanics 继续留在其现有最小实现路径，不重构整个大文件。
- 对齐 env/obs/reward 配置的共同部分，保留 pull Stage3 物理符号及 tensile consumer；共用配置在远端缺失时移植必要依赖，不引入无关 v26 K driver。
- 新建 scriptsFORhuman/pull_v26_aligned/ 的 orchestrate/train/eval/reduce；从 v26-8 receipt/exact natural eval 模板改，增加 pull-specific E2/E4/E5/E7 映射。不得修改旧 H 系列或 v26-8 artifact。

v26 的成熟 body/crossing 等质量 reward 有不少为零，不能称为“成熟行为配方”。这轮先迁 acquisition 框架；pull 全链路通过后再按共同 v27 质量合同整顿行为。不得把 actuator 变强与奖励变化混成单因素结论。

## 5. Checkpoint 与状态合同

首选主实验为 **native C 同构从零训练**，不是 warm-start push C。v26 C 本身是 Q05 continuation，迁移其范式不能同时宣称继承了成功率。

旧 pull grasp winner 是诊断对照与可选 acquisition teacher。仅在 obs 顺序/含义、action transform、actor 参数、RMS 完整匹配后，才能注册独立 continuation 研究；strict-load 成功或同为 135-D 不够。本计划默认不把这个可选 continuation 加入主矩阵，不现场补第三条 warm-start 路线。

scratch：无 checkpoint，policy/critic/optimizer/RMS 与 process-local staged bank 重新初始化。后续 episode curriculum 切换尽量在同一训练进程里完成；若分进程 policy_only 接续，记录 fresh bank，不称 full curriculum resume。历史 checkpoint 没保存 staged_reset_buf。[bank 路径](/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/envs/base_task/staged_task_base.py:556)

如果保留旧 actor 作只读复现，actor/capture/executor 必须消费同一 observed-stage gate。远端 H18 已暴露 env stage 领先 observation 一拍、latent Gaussian 与 tanh executor 不一致的风险；新 native 主链不再使用这类 Stage3 动作重解释。

## 6. 执行次序与有限预算（Owner 采纳后）

### P0：远端现状与物理接线

先读项目规则和 pull 两个 memory 条目，再读本计划、push v26-8 closure/common/C 配置、远端实际 source。若两机 source 有差异，列差异并以当前远端执行路径为事实；不把本地阅读当作远端验证。

固定 LEFT/RIGHT 各 1 个 geometry/oracle trace：核实把手下压正向、开门正向、接近姿态、物理 target、tensile 方向和 finger capability。再做 native learner 32-batch smoke（预算上限，不进入正式统计），解析有效 135/140/12 及 RMS/action 路径。不要求 smoke 学会开门。

旧 winner 的自然 LEFT/RIGHT 各 exact32 只做远端体征复现；若缺文件，标 REMOTE_ARTIFACT_UNAVAILABLE，不伪造也不拿 push checkpoint 替代。旧 winner 不可用不禁止新 scratch，但必须保留此证据缺口。

### P1：先证明双侧 acquisition，不继续堆 head

两个独立 scratch seed 11/12，4096 env，各 2000 batches；milestones 500/1000/2000。训练 curriculum 先覆盖 Stage0–2；最多运行到预注册 acquisition endpoint，不以早期选中 checkpoint 追加长训。每个 milestone 两侧 natural exact64，staged reset off，eval curriculum off，运行时 config 仍必须保留 pull geometry/tensile 语义。

新计划的 acquisition 门：每 seed、每侧 common Stage2 strict K5≥56/64，且 pull tensile/E2≥48/64；exact count 完整、integrity=0。两者含义必须在 reducer 分列。该门是此次提案的新工程准入，不声称它是旧 H 系列或 v26 的阈值。

两 seed 均过才进入 P2。若只有一 seed 过，输出 ACQUISITION_SEED_UNSTABLE 并结束主矩阵；不得只用胜 seed 宣布稳定。预算耗尽不补第三 seed。

### P2：最小 Stage3 opening，随后完整穿越

每 seed 从自身 P1 endpoint policy_only+actor RMS 接续，新的 root，fresh bank 如实登记；不加载 optimizer。各 3000 batches，milestones 1000/2000/3000。staged reset 启用 common 六阶段分布（以源 C 配方核实），只能从实际到达的状态填充；不得注入 oracle 成功快照。保持 pull-specific tensile、unlatch、hinge 方向与 traversal 条件。

每个 milestone 两侧 natural exact64；主表是 common K5 / pull tensile(E2) / physical unlatch / hinge-open(E4) / traverse / complete(E7)，同时保留旧 E5 的精确来源，不能猜 E 标签等价于 stage 序号。列最差侧、最差 seed、接触/速度/关节驻留。

终点目标：两个 seed 每侧 E4≥56/64、complete≥56/64；继续输出 D/S3+/S4+/open_hold/S5+/complete 的共用词义，但 pull 本地阈值若不相同必须显式命名而不能合并比较。若只有 E4 通过，裁定 OPENING_ONLY；禁止称全链路完成或无边界继续训。

### P3：自然确认

只在 P2 两 seed 全链路过门后执行：两个 endpoint 各 LEFT/RIGHT exact128，全新固定 eval seed、相同自然任务分布，不用它重新选 best checkpoint。每格 complete≥112/128 是 pull backbone 工程确认门。另选每侧 3 个事先登记的 episode 渲染，失败/尾部个案另列，不能用视频替代统计。

确认通过仅为 PULL_BILATERAL_BACKBONE_ESTABLISHED，不是 Teacher release 或硬件准入。接下来的 LEFT 质量、quiet/swing 选择与 recovery 进入共同 v27/v28 接口。

总训练上限：smoke 32 + 2×2000 + 2×3000 = 10032 batches（正式 10000）；P1 两侧 eval 共 768 episodes，P2 同样 768，P3 512。只运行满足前置的阶段。新任务不自动获得远端全 GPU；按执行时 Owner 指定分配，可与已协调任务共存，不终止他人的进程。

## 7. 失败、证据与收尾

- 非零退出保留 receipt/log，停止该 cell；不原 root 重跑、不缩 exact N、不用 fallback。修复需明确记录原因与新 root；有限预算之外另提申请。
- 正常学不会是实验失败，不等于代码坏。acquisition 失败先查已注册几何/能力/实际消费，不回到无限 reward/head sweep；press-equilibrium 且接线正确则交付可复现问题与轨迹。
- 只补此次语义改动需要的短测试；实际 IsaacLab API 改动核对本机库。一个 focused runtime smoke 和一次必要语义 review 足够，不轮番过度审计。
- 长跑放独立 tmux，由 orchestrator 自动 checkpoint/eval/receipt；Main 确认正常启动后按 milestone/失败事件醒来，不逐 iteration 手工轮询。共享 GPU 以实际显存余量判断，不把他人正常占用当异常。
- 交付 changed paths、resolved config、effective load mode、natural counts、未运行项、remote artifact 缺口、active writer/tmux/lease。收尾只清自己的资源；不碰并行任务。commit/push/hardware/Teacher/G7 均不包含在本计划授权中。

## 8. 证据级别与边界

当前为 source-level 审查与历史 runtime 文档引用；没有证明迁移会成功。另机日志不可见部分由执行团队在 P0 补足。与附件或旧 memory 冲突时优先当前 source/resolved config 和可审计 runtime；冲突写入 handoff，不静默改判。
