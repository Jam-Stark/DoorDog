# A2+Piper Pull v4 — 年金移除 + Frame-Approach 创建收入:执行方案

**Plan ID:** `a2_piper_pull_v4_annuity_removal_and_frame_approach`
**Date:** 2026-08-11 HKT
**Authority chain:** 本文件 > v3 方案 > v2 方案 > v1 方案。冲突以本文件为准。
**GPU 授权:** GPU 4、5、6、7 专用;其余禁用。
**执行模式:** worker session 全自主(用户离线);预案 §5。
**v4 临时文件边界:** 所有 v4 的 runner/receipt/分析/报告放**新建目录 `scriptsFORhuman/pull_v4/`**。

**North Star 不变(v3 裁决):** release-then-cross,从门框内穿过,全身清出至 −X。

---

## 0. 绑定本轮的 v3 取证结论(全部已核实)

1. **release 灭绝曲线**:seed0 release rate 7/16→2/16→0/16,seed1 1/16→0/16→0/16——v3 训练对 release 施加了单调负选择。
2. **凶手是 corridor_door_wide(v3 C5 设计缺陷,规划者自认)**:该项 = clamp(hinge/1.5)×4.2667×aperture×未清出,在 pull 里是"扶门年金"——release → closer 关门 → hinge 衰减 → 年金流失;converged cell 实测 episode-sum med 45.3,为第二大收入流,终态 hinge 从 1.21 涨到 2.35(扶得更满)。push 侧不发病因为 (a) root_x<0.8 随推进自动关断,(b) crossing 行为在 push basin 里 v13 时代就存在。
3. **升格为 pull 线一般规律(本轮写入 memory)**:push 成熟机构默认全是 maintenance-grade;凡目标行为在 warm basin 不存在,必须先给一阶稠密 creation 收入 + 对旧稳态的驱逐压力,行为出现后 maintenance 机构才接管。已三次验证(pull_door_handle 6.0、near_closed 截断、corridor port)。
4. 有效资产保留:clean_passage 塑形有效(contact→0、clearance margin 单调上升);时间预算 804 步充足(G6 未触发);C3 frame_passage/防绕门谓词、C4 open-command 遮罩、六项 invariant 全部正常工作。
5. **v3 checkpoint 全部不可用作 warm**(release 已灭绝、扶门被强化)——relay 链回退到 v2。
6. G10 已有第一份实测(recontact max 18,恰在还有 release 的 cell)——本轮 release 增多后 recontact 遥测是 longterm TODO #1 的关键输入,仍只记录不实现。

## 1. 冻结决定

| 项 | 值 |
|---|---|
| Warm-start actor(两臂共用) | `logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/pull_v2_W_wave2_relay_seed1/model_step_000750.pt`(回退 v2,理由 §0.5) |
| 训练拓扑 | 256 env × 750 batches,save 250,`policy_only`;**一波 4 cell 并行**(§3) |
| 共同基线 | = v3 T 配置全套(时间预算 [250,100,100,100,250,300]/24s、frame_passage 语义、C4 遮罩、near_closed 0.25、E3 latch 阈值等)**减去** L5 改动 |
| **L5(两臂共同)** | `a2_corridor_door_wide: 4.2666667 → 0.0`;`a2_corridor_clean_passage: 1.0` 保留 |
| **L1(仅 B 臂)** | 新增 `a2_pull_frame_approach: 6.0`(§2 C2) |
| 其余 reward/阈值 | 一律不动 |
| 时长先验 | v3 实测 ~3h07m/cell(804 步 episode);评估 ~10 min/格 |

## 2. 改动 C1–C4(最小 diff,fail-fast)

**C1 — guard v4 分支(第一步)。** plan id `a2_piper_pull_v4_annuity_removal_and_frame_approach`;接受 A 臂(door_wide=0)与 B 臂(door_wide=0 + frame_approach=6.0)两份精确契约(沿用 v1 A/B/R 的 per-config 契约模式);v0–v3 分支不动。

**C2 — L1 frame-approach 收入(仅 B 臂,creation-grade,严禁做成年金)。**
新 reward `_reward_a2_pull_frame_approach`(registry 注册默认 0.0,B 臂 ablation 开 6.0):

```text
raw = clamp( v_toward_aperture / 0.3 , −1, 1 )
v_toward_aperture = root 水平速度在"指向门框中点"方向上的投影
门框中点 = 与 C3 frame_passage 同源的几何推导(door_x, 门框开口中心 y),勿硬编码
激活 = (stage 4/5) ∧ aperture_ready 已锁存 ∧ frame_passage 未锁存
```

设计要点(违反即 bug):
- **带符号线性,不用 tracking-exp 形态**——站立 = 0(无年金尾巴),后退 = 负(防振荡刷分:来回走净额为零);
- **frame_passage 锁存后必须关断**——过框后门框中点在身后,继续付费会往回拽;交棒给既有 target_root/complete/save_time;
- 不依赖抓握状态——持杆移动同样付费,平滑 release 决策边界。

**C3 — 两份 ablation yaml。** fork `pull_v3_T_traversal.yaml`:
- `pull_v4_A_annuity_removal.yaml`:door_wide 0.0,warm ckpt 指 §1;
- `pull_v4_B_frame_approach.yaml`:= A + `a2_pull_frame_approach: 6.0`。

**C4 — invariant 扩展。** 承袭 v3 六项(invariant 5 对 clean_passage 继续生效;door_wide 归零后自然满足)+ 新增两项(结构性,任何非零 = bug 修复重跑):
7. `frame_approach` 在 aperture_ready 前激活 = 0;
8. `frame_approach` 在 frame_passage 锁存后激活 = 0。

## 3. 排程(GPU 4–7,一波全并行)

```text
T0  C1–C4 实现 → D0-lite(B 臂 env,冻结 v2 actor 重放 16 episodes,单 GPU 分钟级):
      八项 invariant 全零;door_wide raw 恒零;frame_approach 在站立 actor 上净额 ≈ 0
      (逐步有正有负、episode 净和近零 = 带符号形态的负基线证明);E6/E7 = 0
    → smoke 64×50 跑 B 臂一次
T1  Wave1(4 cell 并行):GPU4 = A-seed0,GPU5 = A-seed1,GPU6 = B-seed0,GPU7 = B-seed1
      (~3.2h,launch 后实测外推)
T2  12 格全 checkpoint eval(4 GPU 并行,~40min)→ §5 判读
T3  条件性 Wave2(G1 时):胜出臂最佳 ckpt relay 750×2 seed(2 GPU),
      空余 2 GPU 可并行做胜出 checkpoint 渲染 QA(可选)
T4  报告 + memory(含 §0.3 规律条目)+ longterm TODO 勾稽 + commit/push
```

等待纪律:launch 后 +600s 查 batch 进度外推,一次性 sleep 至预计完成(典型 `sleep 11000`);醒后一次核对,未完 `sleep 1800` 递补。训练结束立刻 eval。禁止轮询;等待期间派子 agent 值守、主线写 eval 编排与报告骨架。

## 4. DV 与判读口径

**主 DV:** `E6_rate`、`E7_rate`、`complete_rate`(不变)。
**本轮关键次级 DV(A/B 对照的科学读数):**
- **release rate 沿 checkpoint 的走向**——L5 的直接检验:年金移除后灭绝曲线是否逆转(v3 基线:7→2→0);
- frame-approach 距离分布(min |root−门框中点| per episode)与 frame-approach rate——L1 的直接检验;
- release→first −X 延迟、detour rate、E5→E7 时间线;
- post-release recontact 计数/形态(G10/TODO #1 输入);
- 站桩收入对账表(converged cell 的 episode-sum 分解,对照 v3 的 143 结构)。
分母为零报 `N/A`。A/B 各自与 v3 Wave1 基线行并列呈现。

## 5. 预案(worker 全权;判读窗口 = Wave1 eval 后)

| # | 触发 | 响应 |
|---|---|---|
| G1 | 任一臂任一 seed E6 > 0 | 胜出臂最佳 ckpt relay 750×2 seed 冲 E7/complete;若两臂都点火,选 E6 rate 高者 relay,另一臂结果照报(对照价值已实现);E7>0 时可选渲染 QA 收尾 |
| G2 | 两臂 E6 均 = 0 | 分层定位:(i) release 灭绝曲线逆转但不近 frame → L5 有效 L1 不足/失准,报 frame-approach 距离分布,负结果收官;(ii) release 仍灭绝 → 年金假说不完整,出新的站桩收入对账表(逐项找残余年金),**本轮不加改 scale**,报告收官;(iii) A 臂 release 逆转而 B 臂灭绝 → 检查 frame_approach 负半轴是否在惩罚合法避让位移(实现审查,属 bug 类则修复重跑 B) |
| G3 | crossing 出现但全是绕行(frame_passage=0) | 防绕门谓词首次真实考验;detour 形态写入报告,谓词不放水;若 detour 与 frame-approach 收入并存 → 检查门框中点几何推导 |
| G4 | 臂内 seed 分裂 | 多数+不确定度;T3 空余 GPU 补第 3 seed |
| G5 | panel 接触率显著超基线 | 测 decomposition → 启用 body-contact 罚项(5–15% engaged share)→ 重跑受影响 cell |
| G6 | 时间预算 binding(overtime 时有向框位移) | 按测量再扩,重跑受影响 cell,标注 diagnostic-neutral |
| G7 | 训练崩溃 | 读 traceback 修根因;同 cell 3 次弃 |
| G8 | GPU4–7 部分被占 | 可用者上,优先保 A/B 各一 seed(对照优先于复制),其余串行补 |
| G9 | 总进度超时 | 砍 Wave2/渲染,保 Wave1 四格+eval+报告 |
| G10 | recontact 随 release 增多而上升 | 记录计数/形态/时序(门角 vs 机器人位置),勾稽 longterm TODO #1,**本轮不实现 brace** |
| G11 | frame_approach episode-sum 与实际净位移不成比(疑似刷分) | 带符号形态理论上免疫;若出现 = 实现 bug(如误用 clamp(·,0,1)),修复重跑 B 臂 |

## 6. 交付物

1. 代码/配置 commit(`feat(a2): …` 小步)+ push 到 `codex/a2-piper-pull-v0-20260803`。
2. `scriptsFORhuman/pull_v4/`:D0 receipt、runner、`PULL_V4_ROUND_REPORT.md`(A/B×seed×checkpoint 主对比表含 v3 基线行、release 灭绝曲线对照、frame-approach 距离分布、收入对账表、八项 invariant、预案日志)。不写哈希。
3. 训练 `logs_rl/.../pull_v4_{A,B}_*`;eval `logs_eval/a2_piper_pull_v4/`。
4. memory `pull-open-door-task` 更新——**必须包含 §0.3 的 creation-vs-maintenance 一般规律条目**;主 `a2_piper_longterm_TODO.md` 一行同步;`pull_task/a2_piper_pull_longterm_TODO.md` 勾稽(G10 数据追加到第 1 条)。

## 7. 执行纪律(coding role,全程有效)

- fail-fast:isaaclab/训练代码禁止为"健壮性"加保护性 fallback 强行让仿真跑下去;问题必须在运行中暴露;崩溃读 traceback 修根因,不吞异常。
- 先功能后护栏:先证明操作路径;不新增测试/护栏/兼容层,除非该功能已实际出错。
- 严控审计:review 至多一轮;严控编译/diff/路径检查次数;禁止重复串行 fixture 修复、sandbox loopback、过保守检查。
- 非安全攻防项目,禁止过度防御;禁止为基本不可能的 case 写防御;禁止计算/写入任何哈希(含 SHA256);rubric 不过度机械化。
- 等待一律大块 sleep(600s/1800s/11000s/更长)或派子 agent 值守;禁止轮询。
- 工具调用并行批量;上下文压缩重启后不重复回应旧指令,跟紧最新进度。
