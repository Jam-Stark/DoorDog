# A2+Piper Pull v5.3 — HOMIE Yaw 接口独立表征 + 定向修复 + Anchor 复跑:Addendum

**Plan ID:** `a2_piper_pull_v5_3_locomotion_interface_probe`
**Date:** 2026-08-15 HKT
**性质:** 本文件是 v5 方案、v5.1/v5.2 addendum 之后的第三份 addendum。v5 科学契约(P3 定义、DV、invariant 1–11、G1–G13、停止条件、warm-start、reward 冻结)**原文有效**;v5.1 的 F1–F5 与 G8 bank(191 态)、v5.2 的 T0 门侧/override/双源实现(static-accepted、未运行)均为既有资产。冲突时本文件优先。
**GPU 授权:** GPU 4、5、6、7;其余禁用。
**产出落点:** 延用 `scriptsFORhuman/pull_v5/`,新报告 `PULL_V5_3_ROUND_REPORT.md`(英文)。

---

## 0. 绑定本轮的 v5.2 结论(全部已核实)

1. **v5.2 按 G3/G11 如实收官于 T1 natural open-field anchor:** 三次尝试共 192 terminal episodes,每序列每轮 command_solvable=16/16,但 yaw admission 最好仅 1/0/1/5(attempt 3,yaw-π 初始化后)。无门侧分母、无 passage 主张、P3/P4/双源 NOT_RUN——收官正确,本轮予以追认。
2. **v5.1 的 "S1/S2 yaw PASS" 已被证实是 initialization latch 假象。** 即:HOMIE terminal yaw-hold **从未真实通过**,v5.2 §0.2 "已 anchored primitive 资产"的前提作废。这不是探针序列逻辑缺陷(r4/r5 已修并复测),而是更底层的命令接口问题。
3. **阻塞点定位:HOMIE world-coordinate waypoint + terminal yaw-hold 接口。** 现探针实现为 P 控制式误差映射(`door_open_a2_pull.py` `applied[:, 2] = yaw_command / base_command_scale`,yaw_command = −sign(err)·min(|err|, limit));v5.1 表征证据:target −0.55 → realized −0.98、target +0.35 → realized +1.54,反极性后更糟。**该通道的语义(rate vs offset)、坐标系(world vs base)、标定(scale/latency)从未被独立测量过。** 在语义未知的通道上做闭环校正,过冲/发散是必然结果。
4. **长期 TODO 绑定条款(不可违背):** 新的门侧 occupancy round 前,先做独立接口表征;**不得靠放宽阈值(0.05 m / 0.15 rad)救 PASS**。
5. **资产清单:** G8 pure-A bank 191 态;v5.2 门侧三桶探针、P3 canonical override、双源 eval、invariant 11 实现全部 static-accepted 且未运行,**本轮原样复用,不重写**;P2 release-persistence 结论(binding);受保护 evidence ZIP 与 75 条 projected traces 保持未跟踪未修改。

## 1. P0 — HOMIE yaw 通道独立表征(本轮第一裁决)

**性质:诊断性运行,非科学 episode。** 所有表征行打标 `interface_characterization`,永不进入任何科学分子/分母;不占 G3 次数。

**设计(open-field,无门,GPU4):**
- Natural reset,初始 yaw = π(与 bank 侧朝向一致),XY 命令通道置零。
- **开环恒值命令**:绕过闭环校正,直接令 `applied[:, 2] = u` 恒值,扫 u ∈ ±{0.05, 0.1, 0.2, 0.4, 0.8, 注册上限}(post-scale 语义,以实际写入值记录),每档保持 T ∈ {1, 2, 4} s,每 cell ≥8 env;以控制频率记录 realized yaw 轨迹。
- **归零保持段**:每次命令段结束后 u=0 保持 ≥2 s,量测零命令下 yaw 漂移(terminal yaw-hold 能力的直接读数)。
- **耦合 cell**:选 u 子集,叠加 `straight_minus_x` 与 `side_step` 的 XY 命令(S1–S4 实际使用的仅有这两个 primitive),量测平移对 yaw 的耦合扰动。

**裁决(互斥假说,择一):**
- **H-A rate 语义:** realized yaw 随保持时长近线性增长,斜率∝u → 通道是 yaw-rate;修复 = 按测得增益做模型化 rate 命令 + 到达即停 + 零保持。
- **H-B 坐标系/符号:** 响应符号随 base yaw 变化或正负不对称 → world/base frame 或符号契约错误;修复 = 修正 frame 变换/符号。
- **H-C 标定/饱和/延迟:** 单调但增益失配、有死区或显著延迟 → 修复 = 实测增益标定 + deadband + 延迟裕量。
- **H-D 能力缺口:** 零命令下 2–4 s 内 yaw 漂移 >0.15 rad,或最优开环命令亦无法把 yaw 稳定收敛进 0.15 rad → **接口层不可修**,停轮报告;residual policy / HOMIE 微调属用户决策,本轮不得启动。

表征 harness 崩溃属 G9(实现修复,不计次)。预算 ~30–45 min。

## 2. P1-fix — 单次证据定向接口修复(若 H-A/H-B/H-C)

- **修改范围严格限定**:仅探针侧到 `applied[:, 2]` 的映射(H-B 时含 frame 变换)。waypoint/yaw tolerance、目标定义、XY 命令生成(`a2_hold_base_relief_command`)、reward scale、stage topology、optimizer policy、训练动作一律不动。
- 修复必须逐项引用 P0 实测数(增益、延迟、漂移),禁止投机性多旋钮调参;一次定向修复 + 静态验收即进入 P2。

## 3. P2 — Narrow anchor 复跑与下游恢复

1. **复跑 S1–S4 narrow anchor**,判据原文不变:每序列 16/16 waypoint(0.05 m)+ yaw(0.15 rad)。新开 G3 计数,上限 3 次;每次修正必须由 receipt 证据定向。
2. **任一序列 PASS** → 按 rule 5 实施细则,admitted subset 进入门侧:**原样恢复 v5.2 addendum §1–§2 全部下游**(三桶门侧探针 → G1/G2 → P3 2×2 → 条件 P4、双源 eval、invariant 11),所有 gate 按 v5.2 预注册语义执行,代码不重写、只运行。
3. **三次仍 FAIL** → 按 G3/G11 如实收官;不得重新解释为门侧结论;连同 P0 表征报告一并上报,residual policy 属用户决策。

## 4. 排程

```text
T0  表征 harness(复用探针机械,加开环模式旗标)+ 静态验收
T1  P0 表征(GPU4,~45 min)→ H-A/H-B/H-C/H-D 裁决;H-D → 直接 T5 停轮报告
T2  P1-fix 定向修复 + 静态验收
T3  Anchor 复跑(GPU4,G3 上限 3 次)
T4  (条件)v5.2 门侧三桶 → G1/G2 → P3(GPU4–7)→ P4 → 双源 eval,照 v5.2 排程
T5  英文报告 + memory(yaw 通道语义为 durable fact)+ 两级 TODO 勾稽 + commit/push
```
预算:仅 T0–T3+T5 约 2.5–4 h;若 T4 解锁,全轮 6–9 h。等待纪律照旧:launch 后大块 sleep(训练 3600、探针/表征 1800),醒后一次核对,未完 sleep 600 递补;禁止轮询;等待期派子 agent 值守。

## 5. Review 纪律

本轮允许一轮 review,重点点名:表征 harness 确为开环(无残留闭环写入)、`interface_characterization` 行与科学分母的隔离、P1-fix 的修改范围限定(仅 `applied[:, 2]` 映射)。**FAIL findings = 定向修复 + runtime 验收,不停轮、不二轮**(durable 契约,已入 memory)。

## 6. 交付物

1. 代码/配置 commit(`feat(a2): …` 小步,runtime-proven 即提交)+ push。
2. `scriptsFORhuman/pull_v5/PULL_V5_3_ROUND_REPORT.md`(英文):P0 逐 cell 传递曲线表(u × T × realized 轨迹摘要 + 零命令漂移)、假说裁决与依据、P1-fix diff 范围声明、anchor 逐序列 receipt;若 T4 运行,按 v5.2 报告格式续接门侧/P3/P4/双源表。不写哈希。
3. Eval 落点 `logs_eval/a2_piper_pull_v5/`(表征前缀 `v5_3_char_`,anchor 前缀 `v5_3_`);训练(若跑)`logs_rl/.../pull_v5_3_*`。
4. Memory 更新(HOMIE yaw 通道实测语义为 durable fact;若 H-D,记录升级决策语义)+ 两级 TODO 勾稽(长期 TODO line-42 条目状态更新)。

## 7. 执行纪律(coding role,全程有效)

- fail-fast:isaaclab/训练代码禁止为"健壮性"加保护性 fallback;问题必须在运行中暴露;崩溃读 traceback 修根因,不吞异常。
- 先功能后护栏:不新增测试/护栏/兼容层,除非该功能已实际出错;settle/anchor/invariant 校验属功能正确性。
- 严控审计:review 一轮(§5);严控编译/diff/路径检查次数;禁止重复串行 fixture 修复、sandbox loopback、过保守检查。
- 非安全攻防项目,禁止过度防御;禁止为基本不可能的 case 写防御;禁止计算/写入任何哈希(含 SHA256);rubric 不过度机械化。
- 等待一律大块 sleep 或派子 agent 值守;禁止轮询;工具调用并行批量。
- 上下文压缩重启后不重复回应旧指令,跟紧最新进度。
