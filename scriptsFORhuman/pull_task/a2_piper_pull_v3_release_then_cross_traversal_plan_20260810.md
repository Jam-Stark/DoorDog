# A2+Piper Pull v3 — Release-then-Cross Traversal:执行方案

**Plan ID:** `a2_piper_pull_v3_release_then_cross_traversal`
**Date:** 2026-08-10 HKT
**Authority chain:** 本文件 > v2 方案 > v1 方案 > 云端审计稿。冲突以本文件为准。
**GPU 授权:** GPU 2、GPU 3 专用;其余禁用(用户在执行前的最新 update 覆盖初稿编号)。
**执行模式:** worker session 全自主(用户离线);预案 §5。
**v3 临时文件边界:** 所有 v3 的 runner/receipt/分析/报告放**新建目录 `scriptsFORhuman/pull_v3/`**。

**North Star(用户裁决,simple 版):** 门开至 aperture_ready → **主动松手** → **从门框内穿过** → 全身清出至 −X。不做 hold-through-crossing;门回弹时 arm 重新伸出抵门的行为不在本轮范围(见 `a2_piper_pull_longterm_TODO.md` 第 1 条)。

---

## 0. 绑定本轮的 v2 终态事实(全部已核实)

1. Wave2 seed1 step750:E0–E5 全 16/16,**E6/E7 = 0/16**;16/16 `stage_overtime` 于 stage 4,episode 一律 654 步(13.1 s,来自累计制 `max_stage_time [250,100,100,100,100,200]`)。
2. 终态:root_x = +1.02(未跨门平面),hinge med 1.88 / max 2.618(150° 上限),handle 已回弹(med 0.0)但 **bar 仍双侧握持**;E5 中位于 step 354(7.1 s),**其后仅剩 ~6 s**。
3. 收入交接已自发完成:`pull_door_handle` sums 6.0(创建奖励自然退休),`dont_push` 18.8 接管,`target_root` 已付费(med 17.6)但站立时 raw ~0.13。
4. 物理窗口:closer 关门速度 = max_force/damping = 0.05–0.24 rad/s,全关需 11–52 s ≫ 过门所需 4–6 s → release-then-cross 从容可行。
5. `orientation_control` 为 pitch/roll 指令跟踪,不罚 yaw/转身;`penalty_standing_still`(stage4, −1.0)方向上有利于走动。
6. v2 panel 接触基线:med 0 steps/episode,单 episode max 21——当前开门避让已基本干净。
7. `add_walls=False`:E6/E7 若只查 root_x 平面,从 −Y 侧绕过门框同样"crossing"——**必须防绕门**。

## 1. 冻结决定

| 项 | 值 |
|---|---|
| Warm-start actor | `logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/pull_v2_W_wave2_relay_seed1/model_step_000750.pt`(16/16 真 Stage4 那只,relay 纪律顺延) |
| 训练拓扑 | 256 env × 750 batches,save 250,`policy_only`,GPU2/3 双 seed 并行 |
| Reward 基线 | = V2-W 全套(unlatch_hold 3.0 / hold_and_drive 8.0 / pull_door_handle 6.0 / pull_door_hinge 6.0 / dont_push 3.0 / target_root 12.0 / near_closed 0.25) |
| 本轮新增 | corridor 两项(C5)+ 时间预算(C2)+ through-frame 语义(C3)+ release 路径遮罩审计(C4);此外一律不动 |
| 完整性 invariant | 承袭四项 + 新增两项(§4) |
| 时长先验 | 750-batch cell v2 实测 ~3h05m;时间预算扩容后 episode 变长、吞吐下降,先验上调至 **~4h/cell**,launch 后实测外推为准 |

## 2. 改动 C1–C7(最小 diff,fail-fast)

**C1 — guard v3 分支(第一步)。** plan id `a2_piper_pull_v3_release_then_cross_traversal`;接受 C2 预算、C5 corridor scale、C3/C4 新键;v0/v1/v2 分支不动。

**C2 — 时间预算扩容(测量依据:E5 med 7.1 s + 过门 4–6 s + stage5 清出 3–4 s + 余量)。**
`max_stage_time` stage4 `100→250`、stage5 `200→300`,`max_episode_length_s 20→24`。worker 按 D0-lite 实测复核一次即可。**预算扩容是 diagnostic-neutral 的使能条件,永远不得作为 winner 选择依据**(v21 教训)。

**C3 — through-frame 语义(北极星 + 防绕门,一个谓词族)。**
新增每-env 锁存事件 `frame_passage`:在 `|root_x − door_x| < 0.3 m` 且 root_y 位于门框开口跨度内(从 door builder 几何/metadata 推导半宽,勿硬编码)且 panel_clear 的步锁存。语义收紧:
- **E6** := E5 ∧ signed_crossing > 0 ∧ travel_dir 速度 > 0 ∧ panel_clear ∧ **frame_passage 已锁存**;
- **E7 / stage5→complete** := 原谓词 ∧ frame_passage;
- 绕行者(−Y 大迂回)拿不到 E6/E7/complete,detour 作为独立遥测计数。

**C4 — release 路径收入连续性审计(rule 1,松手瞬间的断崖)。**
逐项核对 aperture_ready 之后仍激活、且会惩罚"主动松手"的项。已知重点:`penalty_a2_stage3_stage4_open_command`(−1.0, stage3/4)——查其实现是否已被 release_gate/hold-income mask 遮罩;**若否,在 pull env 里 override 为 aperture_ready 锁存后不罚 open 指令**(最小 diff)。squeeze/grasp bundle 在松手后归零是预期行为,不是 bug,不补。松手后的收入桥 = dont_push(3.0,已验证接管)+ target_root(12,aperture 后)+ C5 corridor。

**C5 — corridor 最小移植(V1-C 域,pull env 内新写 override,不解锁 push v20 机构)。**
- `a2_corridor_door_wide` := clamp(hinge/1.5, 0, 1) × aperture_ready 锁存 × 未全身清出,stage4/5 活跃,scale **4.2666667**(v20 成熟值);
- `a2_corridor_clean_passage` := aperture_ready 锁存 × 无 body/arm-panel 接触,stage4/5 活跃,scale **1.0**。
`penalty_a2_v20_pre_send_crossing` **不移植**(pull 里门未开则无洞可穿,E6 已被 E5 门控,罚项无对象)。

**C6 — base 避让门扇(用户要求,与防绕门同族处理)。**
v2 实测接触 med 0 → **不加新罚项**(rule 2:无 decomposition 依据不定 scale)。做三件事:
1. panel_clear 合取保持在 E6/E7/stage gate 内(现状确认);
2. 新增 report-only 遥测:swept-arc clearance margin(机器人足迹到门扇当前位置的带符号最小距离)+ base path length / reversal count(force_feasible DV-4 口径:最小 base 干预是论文 DV,先测不塑形);
3. 预登记 fork G5:若 v3 训练后接触率显著超 v2 基线(med 0),按测量 decomposition 启用 `penalty_a2_door_body_contact`,scale 由 worker 按"engaged 时占收入 5–15%"计算,不拍脑袋。

**C7 — ablation yaml `pull_v3_T_traversal.yaml`。** fork `pull_v2_W_*.yaml`:warm ckpt 指向 §1、C2 预算、C5 scale、v3 plan id。其余逐键不动。

## 3. 排程(GPU 2/3)

```text
T0  C1–C7 实现 → D0-lite:冻结 Wave2 actor 于 v3 env 重放 16 episodes(单 GPU,分钟级)
      通过判据:四+二 invariant 全零;corridor 两项仅在 aperture_ready 后付费;
      episode 长度突破 654(预算生效证明);E6/E7 仍为 0(负基线,冻结 actor 不会过门)
    → smoke 64×50 一次
T1  Wave1(并行):GPU2 = V3-T seed0,GPU3 = V3-T seed1(~4h,实测外推)
T2  Wave1 全 checkpoint eval → §5 判读
T3  条件性 Wave2(G1 触发时):最佳 ckpt relay 750×2 seed,冲 E7/complete
T4  报告 + memory + longterm TODO 勾稽 + commit/push
```

等待纪律:launch 后 +600s 查 batch 进度线性外推,一次性 sleep 至预计完成(典型 `sleep 14400`);醒后一次核对(进程退出 + `model_step_000750.pt`),未完 `sleep 1800` 递补。训练结束立刻 eval。禁止轮询;等待期间可派子 agent 值守、主线写 eval 编排与报告骨架。

## 4. DV 与 invariant

**主 DV:** `E6_rate`(in-frame crossing entry)、`E7_rate`、`complete_rate`。
**机制漏斗(次级):** deliberate release rate(aperture 后 bar 接触由有到无且姿态稳定)、release→first −X motion 延迟、frame-approach rate、detour rate(平面 crossing 但无 frame_passage)、time E5→E7、panel contact steps(对照 v2 基线 med 0)、swept-arc clearance margin 分布、base path/reversal count、门回弹 recontact 计数(G10 输入)。分母为零报 `N/A`。

**invariant(任何非零 = bug,修复重跑该 cell):** 承袭四项(假 E4;低于 gate 的首次 Stage4 准入;dont_push 提前激活;target_root 提前激活)+ 新增:
5. corridor 两项在 aperture_ready 前激活 = 0;
6. complete 而无 frame_passage = 0。

## 5. 预案(worker 全权;判读窗口 = 每个 wave eval 后)

| # | 触发 | 响应 |
|---|---|---|
| G1 | 任一 seed E6 > 0 | 主假说成立。Wave2 = 最佳 ckpt relay 750×2 seed 冲 E7/complete;若 E7>0,报告并把 Route-A 式渲染 QA(单 GPU ~30min)作为可选收尾 |
| G2 | E6 = 0 | 按漏斗定位:(a) release 从不发生 → 复查 C4 遮罩遗漏(实现类,修复重跑);(b) release 发生但无 −X 位移 → 出站桩收入对账表(站立 vs 行走逐项),如实报告为收入设计负结果,**本轮不再加/改 scale**;(c) 有 −X 位移但不近 frame → 记录 detour/路径分布,frame 邻域收入预登记给 v4 |
| G3 | crossing 全是绕行(frame_passage=0) | 防绕门谓词按设计工作;detour 行为写入报告,frame 邻域塑形留 v4;不临时改谓词放水 |
| G4 | seed 结论相反 | 空闲 GPU 补第 3 seed,多数+不确定度报告 |
| G5 | panel 接触率显著超 v2 基线 | 按 C6-3:测 decomposition → 启用 body-contact 罚项(5–15% engaged share 定 scale)→ 单独重跑受影响 seed 一次 |
| G6 | 时间预算仍 binding(overtime 时有位移进展) | 按测量再扩一次(仍 diagnostic-neutral),重跑受影响 cell;报告标注 |
| G7 | 训练崩溃 | 读 traceback 修根因;同 cell 3 次弃,记录 |
| G8 | GPU2/3 被占 | 空闲者串行,顺序不变 |
| G9 | 总进度超时 | 砍 Wave2/渲染,保 Wave1+eval+报告最小闭环 |
| G10 | 门回弹撞机器人成为可见失败模式(post-release recontact > 偶发) | 记录计数与形态,引用 `a2_piper_pull_longterm_TODO.md` 第 1 条(arm 重伸抵门),**本轮不实现**,如实报告 |

## 6. 交付物

1. 代码/配置 commit(`feat(a2): …` 小步)+ push 到 `codex/a2-piper-pull-v0-20260803`。
2. `scriptsFORhuman/pull_v3/`:D0-lite receipt、训练/eval/分析 runner、`PULL_V3_ROUND_REPORT.md`(主对比表含 v2 Wave2 基线行、E5→E7 时间线、release/detour/避让遥测、invariant 全零、预案日志)。不写哈希。
3. 训练 `logs_rl/.../pull_v3_T_*`;eval `logs_eval/a2_piper_pull_v3/`。
4. memory `pull-open-door-task` 更新 + 主 `a2_piper_longterm_TODO.md` 一行同步 + `scriptsFORhuman/pull_task/a2_piper_pull_longterm_TODO.md` 勾稽(G10 触发时在第 1 条下追加实测证据)。

## 7. 执行纪律(coding role,全程有效)

- fail-fast:isaaclab/训练代码禁止为"健壮性"加保护性 fallback 强行让仿真跑下去;问题必须在运行中暴露;崩溃读 traceback 修根因,不吞异常。
- 先功能后护栏:先证明操作路径;不新增测试/护栏/兼容层,除非该功能已实际出错。
- 严控审计:review 至多一轮;严控编译/diff/路径检查次数;禁止重复串行 fixture 修复、sandbox loopback、过保守检查。
- 非安全攻防项目,禁止过度防御;禁止为基本不可能的 case 写防御;禁止计算/写入任何哈希(含 SHA256);rubric 不过度机械化。
- 等待一律大块 sleep(600s/1800s/14400s/更长)或派子 agent 值守;禁止轮询。
- 工具调用并行批量;上下文压缩重启后不重复回应旧指令,跟紧最新进度。
