# Pull 开工 prompt — Astra

以下正文供 Owner 选择 Astra 方案并在 pull 训练机交给 Codex Main；文件存在本身不是启动授权。不要把另一方案的不同阶段、奖励或预算混进此轮。

---

你是 pull 训练机 /home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0 的 Codex Main。执行 Owner 采纳的 a2_piper_pull_backbone_plan_20260905-Astra.md，目标是迁到 push v26-8 C 同构 native bilateral backbone，并按门完成双侧 acquisition、opening、traverse 的有限矩阵。

先读 AGENTS.md、.ai/ROLE.md、.ai/PROJECT.md、.ai/WORKFLOW.md、.codex/AGENTS.md；再读 .ai/SCIENTIFIC_ENGINEERING.md、.ai/LONG_RUNNING_TASKS.md、MEMORY.md、memory/a2-piper/MEMORY.md、pull-lr-bilateral-grasp 与 pull-lr-full-stage 的 description/TODO、PULL_LR_FULL_HANDOFF_20260901.md，随后通读本计划。委托前读 .codex/TEAM.md，使用最少必要 agent；默认不用 ultra。

主 plan 在推门机器的路径：scriptsFORhuman/pull_v26_8_alignment/a2_piper_pull_backbone_plan_20260905-Astra.md。如果文件尚未传到本机，请向 Owner 请求 plan 与配套参考文件，不凭本 prompt 复原缺失合同。必须确认远端实际 source、dirty changes、依赖、checkpoint、GPU 分配；本地审计不代表远端已验证。

实现采用新 pull_v26_aligned 命名空间，保留既有 artifact。共享 135-D actor / 140-D critic / 12-D native action、LSTM/RMS、45N/1300/32 capability 与镜像物理 target；不能整文件覆盖 push/pull 的 door_open_a2_base.py。任务差异包括从 reset 起正确的 IO=in、fixture、pregrasp/tangent，以及 pull tensile proof 和 Stage3–5 mechanics。不能把“尽量 Stage3 后分叉”误作删除早期几何条件。

默认 scratch 主矩阵，不迁 push C checkpoint，不接 H18 absolute/taskspace/release-mode head，不启 K curriculum。旧 pull grasp winner只作自然体征对照；严格区分相同维度与相同语义。禁止在 Stage3 把 raw incremental action 重解释成 absolute target。

执行预算：P0 双侧 geometry/oracle、32-batch native smoke、旧 winner exact32/side（缺文件如实登记）；P1 scratch seeds11/12各2000，milestones500/1000/2000；两 seed 双侧 common K5≥56/64且pull E2≥48/64后进入 P2；P2自身endpoint policy_only+actor RMS各3000，milestones1000/2000/3000；fresh staged bank必须明确，不能称 full curriculum resume。两 seed 双侧 E4与complete均≥56/64才做各128/side确认。exact64/128 evaluator按计划新建，不篡改历史固定64 reducer。

P1/P2/P3 所有门以 plan 的完整定义为准。任何 E2/E4/E5/E7 与 stage 名称先建立映射；不能把历史 strict K5 125/128当 opening 证据。指标按逐 seed、逐侧报告，包含接触/速度/关节驻留；任何逆向结果也报告。

长训练在独立 tmux，receipt保存命令、显式必要 proxy env、有效 config、loader、pid、退出码、checkpoint、评估位置；敏感凭据不写入公开报告。orchestrator自动 milestone/eval，确认健康后采用长间隔/事件唤醒，不做逐 iteration 手工轮询。GPU按本机 Owner 当前授权使用，不影响他人的并行任务。

非零退出停止该 cell并保留证据；不原 root 重跑、不悄悄降门槛、不追加 seed或预算。正常失败按typed outcome收口，不无限搜索。若真正发现代码问题，只实施已注册范围的最小修复，用新root保留前后证据；超计划修改或重训需新授权。

本轮授权范围为采纳计划中的本地实现、有限模拟训练/eval和必要memory更新；不包括commit/push、Teacher/G7更新、硬件动作、改旧产物或改其他任务。完成后交付带-Astra后缀closure、证据等级、changed paths、未运行事项；确认自己的writer/tmux/lease已关闭，其他任务进程单列不处置。
