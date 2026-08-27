# A2+Piper Pull-v6 “送门过身”实现计划

- Plan ID: `a2_piper_pull_v6_send_door_past_body`
- 日期: `2026-08-22 01:36 HKT`
- 状态: `P1_ORACLE_PASS`（实现与 P0/P1 已完成；P2 policy training 待启动）
- 当前任务域: 轻门场景；right-hinge、out-opening pull
- 可用算力: 当前机器 GPU0–3，均获用户授权
- 行为起点参考: `pull_v4_B_wave1_seed1/model_step_000750.pt`
- 可视证据: `logs_eval/a2_piper_pull_v4/render_v4_B_seed1_step750_door_failure_20260821_pullside_5cams_retry1/`

## 0. North Star

v6 不再把“门开得更大”本身当作终点。核心能力是：

> 抓住同一侧 handle，在门约 60° 后停止持续后退；允许 base heading 为手臂工作空间和避碰自由调整，由 arm 主导把 handle/门扇从 trunk 左侧送向中线并尽可能送到 trunk 右侧；在通道已形成且门具有继续打开的正角速度时，可以在近中线提前主动 release，让门靠已有动量继续打开，随后立即收臂并 through。

“送门过身”描述的是 **handle 相对 trunk 从左侧向中线/右侧的有向运输 + 门扇扫过 body 的受控拓扑变化**，不是要求 robot 原地、不是硬锁 heading，也不要求为满足一个几何阈值而把困难握持拖到失稳。

## 1. 现有 winner 暴露的具体问题

参考 checkpoint 已会完成以下连续技能：定位 handle、抓握、下压解锁、配合 base retreat 拉门。失败发生在门已经明显打开之后：

- 约 57.3° 进入现有 E5；之后 robot 继续以 base 横移/后退扩大门角度。
- 门长期停留在 trunk 左侧，base 路径约 3.49 m，出现 7 次 reversal；没有形成可直接 through 的 body-door-frame 相对拓扑。
- episode 最终门角约 116°，但仍是 bilateral handle contact；没有 E6/E7，因 stage overtime 结束。
- 当前 E5 clearance 使用约 0.40 m 的圆形 trunk footprint，heading 不影响该 predicate。因此既不能用它证明 heading 正确，也不应从它反推固定 yaw target。

v6 的主瓶颈定义为：**E5 后动作职责没有从 base-dominant pulling 切换到 arm-dominant tangential door transport；release 也没有与门动量和 passage readiness 联动。**

## 2. 当前 scope：先解决轻门，不把动力学泛化混入首轮

这里的“轻门”是本项目 v6 的训练分层名称，不是对现实门质量的通用定义。

| Stratum | 用途 | 门物理/几何 |
|---|---|---|
| F0 canonical | 首个端到端行为创建 | right-hinge、out-opening；width≈0.925 m、height≈2.05 m、handle height≈0.80 m；mass=90 kg；closer max force=4 N·m、damping=50、stiffness=5.5；hook absent；finger effort=45 N；`add_walls=False` |
| F1 lightweight family | F0 成功后的轻门小范围泛化 | mass 80–100 kg；closer max force 2.5–5 N·m；其余几何与 F0 固定 |

明确排除：重门、强 closer、左右开门混训、hook/finger-effort factorial、墙体 hardening、release 后换握另一侧 handle/撑门。这些留在 pull longterm TODO，不进入 v6 首轮 reward 或 curriculum。

## 3. Stage 拓扑：保留 0–5，只细分现有 Stage 4

不扩 actor action 维度，不重编号历史 Stage。现有 Stage 4 增加有明确 ownership 的 subphase：

### Stage 4A — retreat / collision clearance

- 起点：门已解锁并持续打开。
- 目标：base 后退到门板扫掠不会碰撞 trunk 的最小安全区，同时保持 handle grasp。
- heading：自由；只受碰撞、稳定性与 arm workspace 的自然约束，不奖励“正对门”。
- 结束：现有 E5 clearance 成立，并在短 dwell 内稳定。

### Stage 4B — arm-dominant send-past-body

- 在 E5 首次稳定时记录 `pivot_xy`，只记录 XY，不记录/锁定 yaw。
- base 允许小范围 translation/yaw relief，但不再靠持续 retreat 或大幅 lateral travel 获取主要 hinge progress。
- arm 保持 handle grasp，沿门扇 opening tangent 推进，使 handle 在 trunk frame 中从左侧穿过中心并到达右侧。
- 核心观测不是一个绝对世界坐标，而是：handle-in-trunk position、门角/角速度、door tangent、arm workspace margin、panel/trunk clearance 和 passage readiness。

### Stage 4C — accelerate and clean release

- 允许在 handle 已完成换侧、通道已形成时，用最后一段 arm tangent motion 给门正向角速度。
- release 不是固定 90° 的单阈值事件，而是由 `near-center side progress + angle + positive hinge velocity + clearance + arm margin + passage readiness` 联合决定；若继续握持稳定，也允许完成严格的 left→right crossing 后再 release。
- 第一轮用小型 oracle grid 找轻门可学习窗口：
  - release angle: 65° / 75° / 85°
  - minimum hinge velocity: 0.15 / 0.20 / 0.25 rad/s
  - base XY relief radius: 0.05 / 0.10 / 0.15 m
- oracle 只用于确认几何/动力学可达性并选训练窗口，不成为 actor 的 scripted rollout 依赖。

P1 实测校准说明：旧的 `0.30 / 0.45 / 0.60 rad/s` release grid 超出了当前轻门保持稳定握持的窗口。校准后的 27-cell grid 已完整运行，`8/27` 完成 E7：`angle∈{65°,75°}`、`minimum velocity∈{0.15,0.20}`、`relief∈{0.10,0.15}` 的笛卡尔积全部成功；`relief=0.05`、`minimum velocity=0.25` 或 `angle=85°` 均无成功点。

代表成功点为 `75° / 0.15 rad/s / 0.15 m`：实际 release 发生在约 81.2°、hinge velocity 约 0.217 rad/s；E5 后 integrated arm-tangent share 为 `0.761`，clean-release quality 同为 `0.761`，release persistence 为 528 steps、handle recontact 为 0，随后完成 frame passage、E6 与 E7。F0 训练入口因此使用该已证明窗口，不把更高 release 速度或更晚角度当作必要目标。

### Stage 4D / Stage 5 — release → immediate through

- release 后立即恢复 through-frame progress，不安排额外的 heading-recovery phase。
- heading 继续自由调整；只可使用与 passage direction、collision clearance 或 locomotion stability 相关的 soft objective。
- success 仍由 whole-body frame passage/clear 判定，不能用“大门角”替代。

## 4. Actor / critic 契约

### 4.1 Action

- 保持 canonical 12D action contract，不增加 phase selector 或 scripted action channel。
- phase 切换由 env state machine 计算；policy 通过现有动作共同控制 base、arm、gripper。

### 4.2 Observation：actor/critic 首轮完全冻结

v6 首轮是 observation-frozen、policy-architecture-frozen 的 reward/state-machine engineering。严格 warm-start winner，保持 actor 与 critic observation 的 shape、order、normalization 和 history 全部不变；尤其保留现有 `door_dof_pos` 15-frame history，不追加 `door_dof_vel` 或任何 v6 phase/geometry 字段。

现有 actor 已通过 `relative_to_door`、`door_dof_pos` history、`gripper_handle_transform` history、arm/base state、hand force 与 action history 获得生成该行为所需的原始状态。门角速度趋势可由 history 推断；不为方便 reward 计算而扩 actor 输入。

以下 simulator-derived state **只用于 reward、state transition、gate 和 telemetry，不进入 actor/critic observation**：

- hinge position/velocity；
- handle pose/velocity in trunk frame；
- door opening tangent；
- root displacement from `pivot_xy`；
- trunk/panel and arm/panel clearance；
- grasp/contact state；
- arm workspace/joint-limit margin；
- frame passage readiness。

只有在 oracle 已证明行为物理可达、reward attribution 正确，而多 seed 仍系统性无法根据现有 history 选择 release 时机时，observation adequacy 才作为 v6 失败后的独立诊断；它不属于首轮实现。

## 5. Reward ownership：每个 subphase 只支付它负责创造的行为

### 5.1 4A 保留

- 保留 unlatch、stable grasp、必要的 collision clearance 与有限 retreat progress。
- E5 之前不改变 winner 已经学会的 grasp/unlatch/initial pull 主链。

### 5.2 4B 新增/重分配

- `arm_tangent_progress`: 奖励 TCP 在 door opening tangent 上的正向速度/位移。
- `handle_arc_tracking`: 奖励握持点贴合当前门扇圆弧，而不是离开 handle 追求虚假 TCP progress。
- `pivot_xy_hold`: E5 后惩罚 root 离开 captured XY 的位移；只限制 translation，不设 absolute yaw target。
- `handle_side_change`: 只对 trunk-frame lateral coordinate 的正确有向过零/进入右侧给 creation income，避免在左侧持续拉门即可累积 annuity。
- `arm_workspace_margin`: 只在 4B/4C 防止通过 joint-limit 极端姿态换取短时门角。

E5 后停止或 mask：

- 单纯 hinge-position maintenance annuity；
- 鼓励继续远离门的 `target_root_distance`；
- release 前的 frame-approach income（避免 robot 一边握持一边把 trunk 送入门板扫掠区）。

### 5.3 4C / release

- `release_quality` 为一次性 transition reward，不按帧支付。
- 正项：handle 已换到 trunk 右侧、hinge velocity 为正且达到窗口、panel/trunk clearance 成立、passage corridor ready。
- 负项：过早 release、负/近零 hinge velocity release、arm margin 极低、release 后快速 reclose、release 后重新碰撞门板。
- release 后重新启用 signed frame-approach / frame-passage / whole-body-clear progress。

### 5.4 “arm 主导”必须可测

用 door opening tangent `t` 分解 TCP motion：

```text
arm_tangent_share =
  integral(max(0, t · v_arm_at_tcp))
  / integral(max(0, t · v_tcp_world))
```

其中 `v_arm_at_tcp` 是扣除 root rigid motion 后的 TCP 速度。该量用于 attribution/gate，不直接要求 robot 完全静止。必须同时报告 root XY displacement、root yaw change、handle side crossing 和 hinge progress，防止 policy 用 base 旋转伪装成 arm sweep。

## 6. 预期实现路径

1. `gr00t/rl/envs/door/door_open_a2_pull.py`
   - 增加 Stage4 subphase state、E5 pivot capture、handle-in-trunk/door-tangent/passage-ready/release-quality telemetry。
   - 将 E5 后现有 reward ownership 切换为 send/release/through。
2. `gr00t/rl/config/env/`
   - 新增 v6 F0/F1 env config；不覆盖 v4/v5 evidence config。
3. `gr00t/rl/config/reward/`
   - 新增 v6 reward config，参数名与 subphase ownership 一一对应。
4. `gr00t/rl/config/ablation/` 与 `gr00t/rl/config/exp/`
   - 只建立本轮实际会运行的 oracle、F0 specialist、F1 family 和 natural-integration 配置。
5. `scriptsFORhuman/pull_v6/`
   - oracle/eval/render launcher、trace analyzer、round report；不复制 v5 的历史 gate ceremony。

实际实施前先按真实调用路径核对当前 IsaacLab/local source API；fail-fast，不为 shape/config 错误添加 fallback。

## 7. 实验顺序与 GPU0–3 调度

所有 GPU0–3 均获授权。资源调度目标是训练、gate 与 render 重叠执行，但同一 GPU 同时只承载一个 Isaac Sim/训练进程。

### P0 — attribution trace（短跑）

- GPU0：winner natural replay + full kinematic attribution。
- GPU1：E5-state replay / oracle infrastructure smoke。
- GPU2–3：保留给独立 oracle cell；P0 路径成立后立即填满。
- 出口：确认 handle side coordinate、arm/base tangent decomposition、pivot capture 与 release telemetry 在真实 rollout 中有值且语义正确。

### P1 — F0 deterministic oracle

- 将 27 个 `angle × velocity × relief` cell 按预计时长动态分给 GPU0–3；每个 cell 独立输出目录。
- 不等待整张 grid 全部结束才分析：任一卡完成后，空闲卡继续领取尚未运行 cell；分析器只读已自然结束的 cell。
- 目标：找到至少一个能完成 `left→right handle transfer → release → passage` 的轻门窗口，并排除纯 base-motion 假阳性。

### P2 — F0 behavior creation specialist

- 4 个独立 seed 同时运行：GPU0/1/2/3 各一 seed。
- 初始预算：每 seed `256 env × 250 batches`，step50 保存；先观察是否创造 4B/4C 行为，不先扩到大规模。
- 每张卡完成训练后立即在该卡或最早空闲卡运行本 seed checkpoint gate；render 只对 admitted candidate 运行。
- warm start 默认只比较 strict-load winner；scratch 不是首轮 factorial。

### P3 — F1 lightweight family

- 仅 P2 至少一个 seed 通过 F0 gate 后启动。
- GPU0–3 按 `mass/closer` family 或 seed 拆成四个无共享输出的 cell；保持几何固定。
- 目标是轻门域内 release window 的鲁棒性，不外推重门/强 closer claim。

### P4 — natural integration and render

- 最优 checkpoint 的 canonical + natural reset eval 分到两张卡；另一张卡做 five-camera render；剩余卡用于必要的同 checkpoint 复核或保持空闲，避免和共享输出冲突。
- 最终 render 必须同时包含 pull-side、handle-bound、world +X front、world -X front 视角，能看清 handle 换侧、release 和 through。

超过 30 分钟的训练统一使用独立命名 tmux session，记录 GPU、命令和输出目录。调度器以 GPU 独占和输出路径独占为硬边界，不用重复轮询提高“利用率”。

## 8. Gate 与停止条件

### 8.1 F0 behavior-creation gate

一个 episode 必须同时满足：

1. E5 后保持同侧 handle contact，handle-in-trunk lateral coordinate 必须从左侧有向移动到近中线；之后满足以下任一分支：继续握持并穿越到右侧，或以正 hinge velocity 干净 release、K-step 无 handle recontact，且门靠动量继续打开；
2. 4B 段 hinge progress 为正，且 `arm_tangent_share` 达到 oracle 标定后的预注册下限；
3. root XY 位移在所选 relief radius 内；heading 不设硬阈值，但完整记录；
4. release 时 hinge velocity 为正并达到所选窗口，release 后立即收臂，且 K-step 无 handle recontact；
5. release 后出现 frame passage，最终 whole-body clear。

不得用 final hinge angle、门保持打开、单次 handle crossing 或 root heading 接近 180°单独替代成功。

### 8.2 停止规则

- oracle 无任何可达 cell：停止训练，回到几何/动力学设计，不用 PPO 搜索不可能行为。
- P2 四 seed 均未产生 handle 有向换侧：停止扩 budget，检查 reward ownership/actor observability。
- 换侧成功但 release/through 全零：只归因 4C/4D，不回头破坏已学会的 4A/4B。
- F0 达标后才进入 F1；F1 失败不否定 F0 lightweight specialist。

## 9. 必须落盘的最小 telemetry

- Stage / Stage4 subphase transition step；
- hinge position、velocity、opening tangent；
- root pose、`pivot_xy`、XY displacement、yaw delta；
- TCP world velocity、root-induced TCP velocity、arm-relative TCP velocity；
- handle pose/velocity in trunk frame、lateral side-crossing step；
- handle/body/panel contacts and release step；
- arm tangent share、arc tracking error、workspace margin；
- passage-ready、frame-passage、whole-body-clear；
- termination reason。

每个 metric 都服务于行为 attribution；不新增 manifest、hash 或与当前决策无关的防御字段。

## 10. 本轮交付边界

本文件只批准 v6 的实现与实验合同。当前文档轮不声称 code、runtime、training 或 capability PASS。实际实施按 `P0 → P1 → P2 → P3 → P4` 逐层推进；任何重门/强 closer 或 release 后换握/撑门行为必须另行从 longterm TODO 立项。
