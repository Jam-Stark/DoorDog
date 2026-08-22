# A2+Piper Pull 分支 Longterm TODO

更新: `2026-08-22 01:36 HKT`

本表只保留 **尚未实施、且属于 pull 分支** 的未来能力。v0–v5.6 的实验收口、负结果和历史证据统一保存在 `memory/a2-piper/pull-open-door-task/`，不再混入 TODO。

当前 active 方向是 lightweight pull-v6 “送门过身”，执行合同见：

- `scriptsFORhuman/pull_v6/A2_PIPER_PULL_V6_SEND_DOOR_PAST_BODY_IMPLEMENTATION_PLAN.md`

以下条目均为 deferred，不自动进入 v6 首轮。

## 1. 门质量 × closer 动力学的 release 策略泛化

- **动机:** 轻门、重门、弱 closer、强 closer 的最优 release angle、release velocity 与 arm impulse 不同；单一固定时机不能覆盖整个现实门域。
- **当前边界:** v6 先只在 lightweight stratum 创建“送门过身 → 带正角速度 release → through”行为，不混入重门/强 closer。
- **触发:** v6 在 F0 canonical 与 F1 lightweight family 上形成稳定 whole-body passage 后。
- **大致做法:** 将 mass 与 closer strength 分成可解释的二维 family；让 policy 从可观测的 hinge response/history 推断 release 状态，比较 angle-only、angle+velocity 与 learned release；按动力学桶报告，不用总体平均掩盖失败。

## 2. Release 后换握另一侧 handle，或用手撑住门通过

- **动机:** 对有明显回弹的门，人常在原侧 handle release 后换握门另一侧的 handle，或用手抵住门板远侧，保持 passage aperture 并穿过。
- **与简单 brace 的区别:** 目标不是在原侧被动重新伸臂挡一下，而是完成 contact-role transition：`original handle release → opposite-side handle/door contact acquisition → support while through → final release`。
- **触发:** v6 已稳定掌握同侧“送门过身”和 clean release，且强 closer 场景直接证明 release 后 aperture collapse 是主要失败源。
- **大致做法:** 新增门两侧 handle/contact surface 的可观测语义、cross-body reachability 与 contact transition stage；分别验证 opposite-handle regrasp 和 palm/forearm bracing，避免把普通 arm-panel collision 误记为 learned support。
- **状态:** 明确 deferred；复杂度高，不进入当前 lightweight v6。

## 3. `add_walls=True` 的受限空间 pull hardening

- **动机:** 当前 open-field 允许不现实的绕行和 base relief；真实门框/墙体会压缩送门与 through 的可行走廊。
- **触发:** v6 在无墙 F0/F1 上稳定完成 whole-body clear。
- **大致做法:** 单独开启墙体因子，保持门动力学与 reward contract 固定，测 swing-arc clearance、arm sweep workspace 和 through corridor；不与重门、hook 等因素同轮混跑。

## 4. Left-hinge pull 对称性

- **动机:** 当前有效证据集中在 right-hinge；handle-in-trunk 有向换侧、latch mimic 与 tangent direction 的 left 分支尚未实证。
- **触发:** right-hinge v6 收敛后。
- **大致做法:** 先做 left fixture 的 deterministic geometry/oracle，再对成熟 checkpoint 进行 zero-shot 分层 eval；只有观察到结构性不对称时才启动 bounded adaptation。

## 5. Hook、部分解锁与 finger-effort 的抓握真实性

- **动机:** hook geometry、把手未完全下压时的 relock，以及 10 N/45 N finger effort 会共同改变 tensile capture 和送门时的握持上限。
- **触发:** v6 的 arm sweep/release 已稳定，失败能够明确归因到 grasp/latch，而不是 base route。
- **大致做法:** 先用成熟 pull checkpoint 做 hook on/off、handle angle 与 effort 分层 zero-shot；再对已证实的 binding factor 做单因素适配。硬件 finger effort 真值由用户提供时优先锚定。

## 6. Pull 泛化 holdout / release-level claim

- **动机:** canonical/lightweight 成功只能证明 specialist capability，不能直接升级为门族泛化结论。
- **触发:** F1 lightweight family 稳定通过。
- **大致做法:** 建立 pull 专用 pooled/holdout 门集，按 hinge side、mass、closer、geometry 与 handle family 分层；阈值由 pull 实测重新确定，不继承 push 数值。

## 7. Pull teacher → RGB/student

- **动机:** pull 过程有 handle 遮挡、门板大幅旋转以及 camera/robot 相对运动，student 的视觉难度高于只看最终门角。
- **触发:** state teacher 在 canonical 与自然 reset 上稳定完成送门、release、whole-body clear。
- **大致做法:** 以 v6 telemetry 定义 teacher event labels，覆盖 handle side crossing、release dynamics 和 passage；camera contract 使用真实 pull-side 与 world ±X 观察，不沿用 push-side 镜像错误。

## 8. Pull 侧 force-feasible 正式测量

- **动机:** pull 同时受 finger force、arm workspace 与 base intervention 限制，适合测量“力可行性如何改变 base assistance”。
- **触发:** v6 E7/whole-body clear 稳定，且第 5 条 finger-effort profile 已有可信硬件或 simulator 分层。
- **大致做法:** 以固定几何下的 10 N/45 N 与轻/重门动力学分层，报告 arm tangent contribution、base relief、release quality 和 passage outcome，作为 pull 侧独立 DV。
