# v23 P0 Blocker Owner 决策(2026-08-10,经 owner 授权由 main session 裁决)

```text
DECISION            = OPTION_2_PLUS_3_COMBINED(修订 D1 协议 + 重定义 P0.8 preformal gate)
OPTION_1_NO_GO      = REJECTED(blocker 是自建协议 artifact,非物理/科学阻塞)
OPTION_4_D0_ONLY    = REJECTED(修订后 D1 可冻结,无需改科学矩阵)
FORMAL_8x2          = AUTHORIZED——完成下列修订后立即启动,之后不再有任何新增审批 gate
GOAL_STATUS         = unblock(取消 blocked 标记;无需独立 planner 进程,单 worker 继续)
```

## 裁决理由

1. R54 的 "FULL 与 ACUTE 双 16/16 有效窗口" 判据不在任何权威文件里(worker prompt §3.6、审核报告 P2 早已裁定:E 区分类 **physics-first**,acute 探针只作辅助)。ACUTE 仅 1/16 有效不是数据缺失,而是已知结论复现——v22 P0-B 独立标签 37/40 POSTURE_NEEDED、v18 P2 pitch-zero goal 2/16:对 0.4 饱和的 warm policy 做 acute 姿态移除本来就几乎处处失败。该判据结构上不可满足,予以撤销。
2. P0.8 的循环依赖来自把"四种 intervention runtime 全部执行"纳入 preformal gate;prompt §3.9/§6 的原语义即"干预套件只跑 Route B selected checkpoints"。恢复原语义即闭环消失。

## 修订 1:D1 协议(取代 R54 reducer 语义)

1. D1 freeze 的唯一必要输入 = 门侧 physics 探针 + arm 能力标定:
   - atlas free-return + fixed-torque **scripted 探针**(不需要任何 policy 参与)估计 τ_required(θ) per 门参数 tuple;
   - `τ_boundary-calibrated`(P0.2 产出;若 P0.2 尚未收口,先按 prompt 预案 F2 收口并冻结,全矩阵统一同一 profile);
   - E0/E1/near-E2/confirmed-E2 按 τ_required vs arm 可用能力初标,标 **provisional**,G4'/G8'(HR-RP0)训完后 post-hoc re-adjudicate。
2. **显式撤销"两个 mode 均须 16/16 有效窗口"要求。**policy 探针降为 auxiliary evidence:FULL ≥12/16 有效即可入档;ACUTE 无任何 completeness 要求,其接近全无效本身就是 policy-relative 姿态依赖的证据,按 typed 状态记录(`ACUTE_WINDOWS_SPARSE_EXPECTED`)。env5 缺窗记 auxiliary gap,不阻塞。
3. 授权(不强制)fresh producer/telemetry:raw action dims 3/4 进 step trace——formal 阶段 posture 指标反正需要;改动后跑 warm-FULL + 一个 RP0 型 `64×10` smoke 验证一次即可。**D1 freeze 不等待该项。**
4. 产出 D1 zones/mixture/freeze + D1-lite(F3 备用)写入 plan R1。旧 R54 receipt 保留不改,新写 `p04_d1_physics_first` receipt,依据栏引用本决策文件。

## 修订 2:P0.8 preformal gate(v2 定义)

1. preformal 只要求:
   - (a) state bank source plumbing(A0/D0 已完成即满足;可选补 A0-on-D1 rollout states,不阻塞);
   - (b) 四种 intervention mode(ACUTE_RP0 / BASE0_AT_GRASP / HIGHER_EFFORT_RESCUE / ORACLE_TANGENTIAL_ASSIST)代码实现 + 每种一次 1-2 env 短 runtime 触发验证(mode 接通、record 打标即可);
   - (c) 四种 runtime 完整套件显式 defer 至 Route B selected checkpoints(plan §6 原文)。
2. 满足 (a)(b) 即出具 `P0.8_PREFORMAL_COMPLETE`(v2 receipt);旧 `PARTIAL_INCOMPLETE` 保留为历史,不重标、不改写。

## 附带指令

1. P0.5 certificate 阈值:改从 physics-first atlas 数据定标并冻结(若原依赖 R54 流程,一并迁移)。
2. formal 前最后一个动作:任选一个 **D1-FULL 型 config 跑一次 `64×10` smoke**(D1 manifest/bucket plumbing 首次真跑;本项目此类接线历史上最易在 runtime 爆)。通过即启动 A1,不再请示。
3. A1 组成(F1 已触发,init 轴 = warm vs head-reset):G1(warm-D0-FULL)、G3'(HR-D0-FULL)、G5(warm-D1-FULL)、G7'(HR-D1-FULL),GPU0-3;其后 A2/B1/B2、Route A/B、holdout、render、final analysis 按 worker prompt §5-§8 与 F 预案自主跑完。H1 语义按 F1 已调整为"输出头继承"。
4. `d1_admission` / `formal_admission` receipts 按修订后 gate **新文件重新出具**,历史 receipt 一律不改。
5. 流程纪律重申(prompt §9):今后任何 reducer/gate 只能执行 plan R1 已写明的判据;不得自行发明对称性/completeness 要求;做出"terminal/不可满足"类终局判定前,必须先对照权威文件确认该判据本身是否被授权。
6. 不 push;继续本地 commit。plan R1 与 memory entry 同步本决策。
