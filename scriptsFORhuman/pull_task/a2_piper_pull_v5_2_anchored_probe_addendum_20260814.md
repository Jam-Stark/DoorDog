# A2+Piper Pull v5.2 — Anchored Narrow Probe + Override-Assisted Starts:Addendum

**Plan ID:** `a2_piper_pull_v5_2_anchored_probe_and_assisted_starts`
**Date:** 2026-08-14 HKT
**性质:** 本文件是 v5 方案与 v5.1 addendum 之后的第二份 addendum。v5 科学契约(P3 定义、DV、invariant 1–10、G1–G13、停止条件、warm-start、reward 冻结)**原文有效**;v5.1 的 F1–F5 修复成果与 G8 bank(191 态)为既有资产。冲突时本文件优先。
**GPU 授权:** GPU 4、5、6、7;其余禁用。
**产出落点:** 延用 `scriptsFORhuman/pull_v5/`,新报告 `PULL_V5_2_ROUND_REPORT.md`(英文)。

---

## 0. 绑定本轮的 v5.1 r2 结论(全部已核实)

1. **P2 三层结果:** release persistence 绑定(3/16→16/16,p=1.22e-4);强制松手后 base 仍不进框(距离仅 0.741→0.650 m);**松手后可通行窗口 ~2–4 s**(+2 s 时仅 5/16 保持 hinge≥1.6)。
2. **Anchor 的 per-primitive 二分:** `straight_minus_x` 与 `side_step` 三次尝试全过(waypoint+yaw),`turn_then_forward` 与 `arc` 全挂(HOMIE yaw 通道过冲:−0.55→−0.98、+0.35→+1.54,反极性无效)。**Anchor 收紧为"四 primitive 全过"超出了任务需要**——从 bank 态(yaw≈π 已面朝 −X)进框的自然路线由已 PASS 的两个 primitive 构成。
3. **Rule 5 实施细则(本轮起 binding,并写入 memory):anchor 只需认证门侧探针实际使用的 primitive/序列集合**,库存 primitive 不在认证范围。
4. **Bank 缺 constructed 类的替代:** bank 持杆态 + 开局 1 s release+tuck override(P2 runtime 已证)= 动力学一致的已松手起点;Source B 永久退役。
5. HOMIE yaw 过冲表征记入 `a2_piper_pull_longterm_TODO.md`(locomotion interface 条目,本轮不修)。

## 1. P1-narrow — 门侧三桶探针(本轮第一裁决)

**命令序列集(全部由已 anchored primitive 构成):**
```text
S1 straight_minus_x(多速档)
S2 side_step(±Y)
S3 side_step → straight_minus_x(先横移对中,再直进)
S4 straight_minus_x → side_step(先逼近,再横移对中)
```

**Narrow anchor(先行,rule 5):** S1–S4 逐序列在远离门的开阔地各 16 行,waypoint 到达 + yaw 保持(注意:S1/S2 的 yaw 判据沿用 v5.1 已过口径;S3/S4 为新序列,必须实测)。PASS 判据 = 每个序列 16/16 waypoint 到达。anchor 不过的序列从门侧集合剔除;若 S1/S2 也过不了(与 v5.1 证据矛盾)→ 探针实现缺陷,修复重跑(3 次上限)。

**门侧执行:** 从 G8 bank 按三 closer 桶各采 ≥16 态 → 开局 1 s release+tuck override(P2 同一 evaluator 级契约:base 切片保真)→ 执行各 anchored 序列 → 量测 frame passage、panel 接触、执行时门角轨迹(reclosure race 读数)、命令跟踪误差。按 桶 × 序列 报告,分母 = 实际执行行数。

**判读(升级版,因前提已变):**
- 任一桶任一序列 passage>0 → 占据/探索假说坐实,P3 放行(G1);
- **全零** → 此时"松手已保证 + 路线已 anchored + 起点动力学一致"三前提齐备,全零是真实的可行性警报 → G2 lattice,聚焦点명 yaw/横移通道在门区(含门扇接触扰动)的 requested/realized 表征;lattice 后仍不可行 → 停轮报告(residual policy 属用户决策)。

## 2. P3 — 照 v5 契约 + 两处适配(若 P1-narrow 放行)

1. **Canonical 起点 = bank 态 + 开局 override:** 被 bank 注入的 env 在 reset 后前 ~50 控制步由 env 侧对 arm/gripper 动作切片施加 release+tuck override(base 切片永不触碰),新 provenance 标签 `bank_natural_e5_override`。配置键进 guard v5.2 契约;natural reset 的 env 永不 override。
2. **DV 增补:** `K25 persistent_release_rate` 升入次级 DV(双源分列);新增遥测"passage 尝试时刻门角"(reclosure race 读数)。
3. 其余照 v5 §4–§5 原文:2×2(M p=0.5 / C p=0.9 × seed 0/1,GPU4–7 一波,256×250,save 50)、双源 eval(canonical 16 + natural 16)、G5/G6/G7/G12 判读、停止条件不变。

**Invariant 11(新增,结构性,非零即 bug):** override 仅在 canonical-start episode 的前 K 步激活;natural episode 中 override 激活次数 = 0。与 invariant 9 同源于 reset_source 标注。

## 3. 排程

```text
T0  实现:narrow-anchor/门侧探针序列 + P3 训练期 override(env 侧,guard v5.2 键)
T1  Narrow anchor(GPU4,~30 min)→ 门侧三桶探针(GPU4,~1 h)
T2  判读:G1 → T3;全零 → G2 lattice(GPU4,~1 h)→ 停轮或按发现修一次探针
T3  P3 一波 4 cell(GPU4–7,~65 min)→ 双源 eval(~1 h)→ G5/G6/G7/G12 判读
T4  (条件)P4 续训/退火 → 英文报告 + memory(rule-5 细则、yaw 表征、v5.2 结论)
    + 两级 TODO 勾稽 + commit/push
```
全轮预算 5–8 h。等待纪律照旧:launch 后 sleep 600 外推,一次性 sleep 至预计完成(训练 3600、探针 1800),醒后一次核对,未完 sleep 600 递补;禁止轮询;等待期派子 agent 值守。

## 4. Review 纪律

本轮允许一轮 review,重点点名:override 的训练期作用域(invariant 11)、narrow-anchor 与门侧序列的一致性、bank 采样的桶分母。**FAIL findings = 定向修复 + runtime 验收,不停轮、不二轮**(此语义本轮起为 durable 契约,写入 memory)。

## 5. 交付物

1. 代码/配置 commit(`feat(a2): …` 小步,runtime-proven 即提交)+ push。
2. `scriptsFORhuman/pull_v5/PULL_V5_2_ROUND_REPORT.md`(英文):narrow anchor 逐序列证据、门侧 桶×序列 判读表、(若跑)P3 双源 DV 表含 v4-B 基线行 + K25 双源、十一项 invariant、G 表日志、reclosure race 读数。不写哈希。
3. 训练 `logs_rl/.../pull_v5_2_*`;eval `logs_eval/a2_piper_pull_v5/`(cell 前缀 `v5_2_`)。
4. memory 更新(rule-5 实施细则、review-FAIL 处置语义、yaw 表征、v5.2 结论)+ 两级 TODO 勾稽(HOMIE yaw 条目新增)。

## 6. 执行纪律(coding role,全程有效)

- fail-fast:isaaclab/训练代码禁止为"健壮性"加保护性 fallback;问题必须在运行中暴露;崩溃读 traceback 修根因,不吞异常。
- 先功能后护栏:不新增测试/护栏/兼容层,除非该功能已实际出错;settle/anchor/invariant 校验属功能正确性。
- 严控审计:review 一轮(§4);严控编译/diff/路径检查次数;禁止重复串行 fixture 修复、sandbox loopback、过保守检查。
- 非安全攻防项目,禁止过度防御;禁止为基本不可能的 case 写防御;禁止计算/写入任何哈希(含 SHA256);rubric 不过度机械化。
- 等待一律大块 sleep 或派子 agent 值守;禁止轮询;工具调用并行批量。
- 上下文压缩重启后不重复回应旧指令,跟紧最新进度。
