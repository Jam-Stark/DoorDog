# A2+Piper Pull v2 — 收入墙移除 + 解锁角标定:执行方案

**Plan ID:** `a2_piper_pull_v2_wall_removal_and_unlatch_calibration`
**Date:** 2026-08-09 HKT
**Authority chain:** 本文件 > v1 执行方案(20260809)> 云端审计稿(20260806)。冲突以本文件为准。
**GPU 授权:** GPU 6、GPU 7 专用;其余禁用。
**执行模式:** worker session 全自主(用户离线);预案见 §6。
**v2 临时文件边界:** 所有 v2 的 runner/探针/receipt/报告一律放**新建目录 `scriptsFORhuman/pull_v2/`**(对应用户要求的 "pull-v2 文件夹",沿用 pull_v0/pull_v1 下划线命名惯例)。不得散落他处。

---

## 0. 绑定本轮的三条诊断结论(v1 数据 + 主线史实,均已核实)

1. **创建期奖励史(v13 定论)**:压把手行为由 v0–v12 的 `push_door_handle: 6.0` 创建、v13 改造成 grasp-gated 维持形态(`unlatch_hold 3.0` + `hold_and_drive 8.0`,`push_door_handle→0`),此后代际 warm-start 继承。pull 侧 V1-R(`pull_door_handle: 6.0`,自带 load-bearing gate)已在 seed0 重建该行为:13/16 episode 把手压满 45° 且双侧稳定接触。**创建级奖励保留,本轮不再动任何教学奖励。**
2. **latch 是 pull 的真实机械约束**:latch 通道正常(R0-750 终态 latch = handle × 0.03/45° 完美线性,满行程满缩回);v0/V1-A/B 的 hinge 天花板 0.0018–0.0022 rad 与 v13 文档记载的 latch 咬合空隙 0.0022 rad 精确吻合——不解锁的门拉不开;push 侧可压缩暴力凸轮过框(attempt20),pull 摩擦拉握不可复制。
3. **0.1 rad 收入墙**:R0-750 最好两条 episode 的 hinge 峰值 0.1006/0.0921 恰压在 `unlatch_hold` 的 `near_closed`(hinge<0.1)截断线上,轨迹 0 步越过 0.105,峰值时双侧接触完好;静力学上 0.1 rad 处闭门器阻力 ~1 N·m 不构成边界;收益算术显示越线净亏 ≈0.055/步。该截断是 v13 为 push 设计的防 farming 护栏,在 pull(开门慢、dwell 长)变成墙。**本轮主刀 = 拆墙。**

## 1. 冻结决定

| 项 | 值 |
|---|---|
| Warm-start actor | `logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/pull_v1_R_seed0-20260809_110901_retry2/model_step_000750.pt`(checkpoint relay:继承已习得的解锁+初步拉门技能;R1 谱系弃用) |
| 训练拓扑 | 256 env × 750 batches,save 250,`policy_only`,与 v1 同(全程可比) |
| Reward 基线 | = V1-R 配置(unlatch_hold 3.0 / hold_and_drive 8.0 / pull_door_handle 6.0 / pull_door_hinge 6.0 / dont_push 3.0 / target_root 12.0) |
| 本轮唯一 reward 侧改动 | `a2_stage3_unlatch_near_closed_hinge_threshold: 0.1 → 0.25`(与 Stage3→4 gate 对齐) |
| 明确不动 | `a2_stage3_unlatch_handle_position_norm 0.6`、hold_and_drive 速度 norm、dont_push、target_root 门控、stage gate 本体——单轴纪律 |
| 物理/PPO/gate | 全冻结(v1 的 hard_gate + panel_clear 谓词不变) |
| 时长先验 | 750-batch cell ≈ 3h10m/GPU;U-probe 分钟级;smoke 64×50 ≈ 11 min |

## 2. 代码/配置改动(C1–C4,最小 diff)

**C1 — guard v2 分支(第一步)。** `a2_pull_v0_guard.py` 加 plan id `a2_piper_pull_v2_wall_removal_and_unlatch_calibration` 分支:接受 R 级 scale 组合 + `near_closed=0.25` + C3 的 E3 阈值键。v0/v1 分支逐字节不动。既有测试最小修正,不新增测试。

**C2 — ablation yaml。** fork `pull_v1_R_*.yaml` → `gr00t/rl/config/ablation/wbmanip/pull_v2_W_wall_removal.yaml`:改 warm ckpt 路径、plan id、`a2_stage3_unlatch_near_closed_hinge_threshold: 0.25`。此外无任何差异。

**C3 — E3 谓词升级(遥测,不进 gate/reward)。** `door_open_a2_pull.py` 的 `latch_released` 由 `latch > 0.0`(严格正,微噪即假触发)改为 `latch ≥ a2_pull_e3_latch_threshold_m`(新配置键;U-probe 标定后回填,占位 0.015 = 半行程)。`stable_unlatch` 漏斗指标同时导出 handle-based(≥0.3)与 latch-based 两版;`relock` 类指标恢复物理意义(latch 从 ≥阈值回落到 <阈值且 hinge<gate)。

**C4 — 无其他 env 改动。** v1 的事件图(E4 基于物理 gate、E5 基于 aperture_ready)不动。

## 3. U-probe:解锁角标定(v13 §1.9 遗留验证项,首次执行)

**性质:门资产标定,无机器人参与,不属于被 Amendment 7 退役的 scripted policy probe 类。** runner 放 `scriptsFORhuman/pull_v2/run_u_probe_unlatch_calibration.py`,实现选最省路径(可复用 env 但把机器人 spawn 到远处不接触门;或用既有 door 预览设施)。

流程:标准 fixture 门,对每个 handle 角 θ ∈ {0, 0.1, 0.2, …, 0.785}(rad):
1. 每步将 handle 关节位置钳制在 θ;
2. 对 hinge 施加开门方向驱动(如临时 drive target +150°、maxForce ≈20 N·m,量级远超闭门器上限 12 N·m 但非暴力级);
3. 跑 ~200 步,记录 latch 位置与 hinge 峰值。

**判据:θ\*(有效解锁角)= hinge 峰值 > 0.05 rad(逃出 0.0022 咬合空隙 20 倍)的最小 θ。** 输出 receipt `PULL_V2_U_PROBE_UNLATCH_CALIBRATION.json`:θ→(latch_m, hinge_max) 全表、θ\*、回填 C3 的 `a2_pull_e3_latch_threshold_m = latch(θ*)`。
可选附加(时间允许):θ=0 时扫 hinge 驱动力 {5,10,20,40} N·m,量化"凸轮硬过框"的力阈值——解释 attempt20 并给 pull 摩擦拉握的不可绕锁结论定量下界。

## 4. 排程(GPU 6/7)

```text
T0  C1–C4 实现 → U-probe(分钟级,GPU6)→ 回填 E3 阈值
    → smoke 64×50 跑 V2-W 一次(GPU6):训练路径 + resolved config 里 0.25 生效即过
T1  Wave1(并行):GPU6 = V2-W seed0,GPU7 = V2-W seed1(~3.2h)
T2  Wave1 全 checkpoint(250/500/750)漏斗 eval → 按 §6 判读
T3  条件性 Wave2(~3.2h):
    - 墙假说证实(G1)→ 从 Wave1 最佳 ckpt 再 relay 750 batches × 2 seed,冲真 Stage4 占据
    - 墙假说证伪(G3)→ 不再训练;A0 归因分析(零 GPU):R0/V2-W trace 的
      handle-local slip、手指利用率、base-臂位移分解,产出 binding-constraint 分类
T4  报告 + memory + commit/push
```

等待纪律:launch 后 +600s 查一次 batch 进度外推,一次性 sleep 至预计完成(典型 `sleep 10800`),醒后一次核对(进程退出 + `model_step_000750.pt` 在),未完 `sleep 1800` 递补。禁止轮询。等待期间可派子 agent 值守,主线写 eval 编排/报告骨架。

## 5. DV 与验证项

**主 DV(与 v1 相同,全程可比):** `true_stage3_to4_rate`(物理谓词直判)、`positive_hinge_while_valid_hold_rate`、`hinge_delta_while_valid_hold_rad`(med/max)。

**v2 专属诊断:**
- **hinge dwell 直方图**,band {<0.02, 0.02–0.08, 0.08–0.105, 0.105–0.25, ≥0.25}——v1 的墙签名(0.105–0.25 恒 0)是否消失是本轮最直接读数;
- **拆墙生效证明**:`unlatch_hold` 在 hinge∈(0.1, 0.25) 区间的 active-step 数 > 0(v1 中该区间构造性为 0);
- latch-based stable_unlatch 与 relock 计数(C3 阈值标定后首次有意义)。

**完整性 invariant(承袭 v1 四项,任何非零 = bug,修复重跑):** 假 E4 = 0;低于 gate 的 Stage4 快照 = 0;dont_push 真 Stage4 前激活 = 0;target_root aperture_ready 前激活 = 0。

## 6. 预案(worker 全权,判读窗口 = 每个 wave eval 后)

| # | 触发 | 响应 |
|---|---|---|
| G1 | 任一 seed hinge Δ max ≥ 0.2 rad 或 true S3→4 > 0 | 墙假说证实。Wave2 = 最佳 ckpt relay 750×2 seed 冲真 Stage4;若 Wave2 出现真 Stage4 占据,报告并标注 v3 进入 traversal(V1-C 域) |
| G2 | 提升但新平台落在 0.105–0.25 内(如 ~0.2) | 部分证实:墙已拆但 0.25 前仍有阻碍。对新平台位置做收益/力双侧检查(平台贴 0.25-ε → 下一道收入接缝,预登记给 v3,不现场加 reward;平台随机 → 转 G3 的 A0) |
| G3 | 两 seed 均无改善(hinge Δ max ≤ 0.11) | 墙假说证伪,力/协调为主瓶颈。停训练,执行 A0 归因(slip/手指利用率/base-臂分解),报告 binding-constraint 分类,v2 以负结果收官(合法结论) |
| G4 | 两 seed 结论相反 | 空闲 GPU 补第 3 seed;报告按多数+不确定度 |
| G5 | U-probe:θ\* > 0.7 rad(近满行程才解锁) | 照常回填 E3 阈值;在报告中标注"部分松把手即回锁"风险,relock 指标优先级升高 |
| G6 | U-probe:θ=0 时 20 N·m 内 hinge 即可 >0.05(latch 不挡拉门) | 与咬合空隙证据矛盾 → 复查探针实现;若确认,则"latch 必要性"结论修订并写入报告,训练照常进行 |
| G7 | 训练崩溃 | 读 traceback 修根因,重启;同 cell 3 次弃,记录 |
| G8 | GPU6/7 被外部占用 | 用空闲者串行,顺序不变 |
| G9 | 超时(单 cell >6h 或总进度落后) | 砍 Wave2/可选项,保 Wave1+eval+报告最小闭环 |

## 7. 交付物

1. 代码/配置 commit(`feat(a2): …` 小步)+ push 到 `codex/a2-piper-pull-v0-20260803`。
2. `scriptsFORhuman/pull_v2/`:U-probe runner + receipt、eval 编排脚本、`PULL_V2_ROUND_REPORT.md`(主对比表含 v1-R 基线行与 dwell 直方图;U-probe 标定表;走过的预案分支;invariant 全零;若 G3 则 A0 归因结论)。表内不写哈希。
3. 训练 `logs_rl/.../pull_v2_*`;eval `logs_eval/a2_piper_pull_v2/`。
4. `memory/a2-piper/pull-open-door-task/` 更新 + `a2_piper_longterm_TODO.md` 一行同步。

## 8. 执行纪律(coding role,全程有效)

- fail-fast:isaaclab/训练代码禁止为"健壮性"加保护性 fallback 强行让仿真跑下去;问题必须在运行中暴露;崩溃读 traceback 修根因,不吞异常。
- 先功能后护栏:先证明操作路径;不新增测试/护栏/兼容层,除非该功能已实际出错。
- 严控审计:review 至多一轮;严控编译/diff/路径检查次数;禁止重复串行 fixture 修复、sandbox loopback、过保守检查。
- 禁止计算/写入任何哈希(含 SHA256);禁止为基本不可能的 case 写防御;非安全攻防项目,禁止过度防御;rubric 不过度机械化。
- 等待一律大块 sleep(600s/1800s/10800s/更长)或派子 agent 值守;禁止轮询。
- 工具调用并行批量;上下文压缩重启后不重复回应旧指令,跟紧最新进度。
