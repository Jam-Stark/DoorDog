# A2+Piper Pull v5.1 — v5 修复重启 Addendum

**Plan ID:** `a2_piper_pull_v5_1_bridge_occupancy_repair`
**Date:** 2026-08-12 HKT
**性质:** 本文件是 `a2_piper_pull_v5_bridge_occupancy_plan_20260812.md` 的 **addendum**——v5 方案的科学契约(P1/P2/P3 定义、DV、十项 invariant、G1–G12、停止条件、warm-start、reward 冻结)**全部原文有效,一字不改**;本文件只修复执行拓扑。冲突时本文件优先。
**GPU 授权:** GPU 4、5、6、7;其余禁用。
**产出落点:** 延用 `scriptsFORhuman/pull_v5/`(同一阶段目录),新报告文件 `PULL_V5_1_ROUND_REPORT.md`(英文);state bank 延用 `logs_rl/.../pull_v5_state_bank/`。
**复用原则:** v5 的 r5 代码资产(census 工具、Source-A 捕获、P0-c、干预 harness 的静态契约、64 态 Source-A payload)全部复用修补,禁止推倒重写。

---

## 0. v5 失败链结论(binding,不重复论证)

环形依赖死锁:guard 把 bank 注入定为 v5 全配置强制 → load-receipt/P1/P2 的 env 构造全部被"bank 不存在"卡死;P2 被不必要地绑上 v5 env;Source B 走 staged-reset ratio hack 撞基座断言 `ratios[0]>0`;Source A 缺 per-state closer 元数据与贴框态覆盖。census 与 P0-c 为有效资产。

## 1. 五个修复(F1–F5,精确契约)

**F1 — 注入改为逐配置可选键(解锁一切)。**
`a2_pull_v5_stage4_bank_injection_enabled` 成为 per-config 键,guard v5/v5.1 分支**同时接受 true/false**;`DoorOpenA2Pull._load_a2_pull_v5_state_bank` 仅在 true 时要求 bank 文件存在。约定:census / load-receipt / 捕获 / P1 anchor 与 door probe 配置 = **false**;P3 的 M/C 训练 cell = **true**。

**F2 — P2 与 v5 env 彻底解耦。**
干预实验在 **v4 plan id + v4-B 配置**下执行,动作 override 实现在 **eval-runner 的 action 层**(agent 输出后、下发前替换 arm/gripper 切片),**不进 env、不进 guard、不引用任何 v5 键**。v5 期间已写好的 override 静态契约(base 切片保真、默认位收臂、阈值外不激活)沿用。

**F3 — Source B 改直写路线。**
在 injection=false 的 env(eval 模式)中**直接写 sim 状态**(door 关节 + robot root + dof)→ settle ≥50 步 → 稳定性校验(倒地/穿模即弃)→ 按 Source-A 相同的 86-buffer payload schema 导出。**禁止触碰 `staged_reset_ratios`。**

**F4 — Source A 补采与元数据。**
(a) 每态导出 per-state `hinge_drive_max_force`(door metadata 现成字段)及 provenance 标签;(b) 捕获窗口扩为 **E5 / E5+2s / E5+4s** 三档,+2s/+4s 档标签 `bank_natural_e5_plus`(覆盖"持杆贴框"态);既有 64 态 payload 保留并补齐元数据(可重放导出)。

**F5 — load receipt 重跑 + 归一化记录。**
用 F1 后 injection=false 的合法配置重跑 load-only,产出真实 receipt(actor/critic/optimizer/scheduler 实际 loaded/reset);把"eval wrapper 将 policy_only 归一化为 full"写入 receipt 与报告方法学节,**本轮只记录不修改该 wrapper**。

## 2. Bank 合成门(新 G13)

最终 `pull_v5_state_bank.pt` 合法条件:总数 ≥64;**每态**带 closer 元数据且三桶各非空;`bank_natural_e5_plus`(贴框)≥8 态;`bank_constructed`(已 release)≥16 态。若 F3/F4 补采后仍缺某类,走 v5 方案 G8(降级为纯 natural bank)但 **per-state 元数据不可豁免**;缺口如实写入报告。

## 3. 串行流水线(显式依赖,禁止越序)

```text
S1  F1(guard/注入键)∥ F2(P2 解耦改造)          —— 无相互依赖,并行
S2  F5 load receipt(GPU6)∥ P2 正式执行(GPU5,v4-B paired fixtures)
      ∥ F4 Source-A 补采(GPU7)∥ F3 Source-B 直写捕获(GPU4)
      [S2 全员只依赖 S1,不依赖 bank]
S3  bank 合成 + G13 校验(无 GPU)
S4  P1:anchor 先行(开阔地 waypoint,rule 5)→ door probe 三桶分层(GPU4)
S5  判读(v5 §6 G1/G2/G3 原文)→ P3 2×2(GPU4–7 一波,256×250,save 50)
S6  双源 eval → G5/G6/G7/G12 判读 →(条件)P4
S7  英文报告 + memory + 两级 TODO + commit/push
```

**P2 的结果在 S2 就落地**——即使后续再次受阻,G11 最小闭环升级为:F1+F2+F5+**P2 完整结果**+P1 所到边界+报告。

## 4. 排程与预算

S1–S3 合计 ≤3 h(实现为主);S4 ≤1 h;S5 训练 ~65 min;S6 ~1 h;全轮 6–9 h。
等待纪律:launch 后 sleep 600 查进度外推,一次性 sleep 至预计完成(训练 sleep 3600、探针/捕获 sleep 1800),醒后一次核对,未完 sleep 600 递补;禁止轮询;等待期间派子 agent 值守、主线写分析/报告骨架。
review:本轮(v5.1)允许一轮 review,**审查重点点名为依赖拓扑与配置契约**(上轮逃逸的正是这类问题),不做第二轮。

## 5. 交付物

1. F1–F5 代码/配置 commit(`feat(a2): …` 小步)+ push。
2. `scriptsFORhuman/pull_v5/PULL_V5_1_ROUND_REPORT.md`(英文):F1–F5 修复证据、load receipt 结论、G13 bank 清单(逐态 provenance/桶)、P2 完整结果、P1 三桶判读、(若达)P3 双源 DV 表含 v4-B 基线行、十项 invariant、G 表日志。不写哈希。
3. bank + provenance 清单;训练 `logs_rl/.../pull_v5_1_*`;eval `logs_eval/a2_piper_pull_v5/`(延用命名空间,cell 前缀 `v5_1_`)。
4. memory 更新(v5.1 修复结论 + load 语义两条债的现状)+ 两级 TODO 勾稽。

## 6. 执行纪律(coding role,全程有效)

- fail-fast:isaaclab/训练代码禁止为"健壮性"加保护性 fallback 强行让仿真跑下去;问题必须在运行中暴露;崩溃读 traceback 修根因,不吞异常。
- 先功能后护栏:先证明操作路径;不新增测试/护栏/兼容层,除非该功能已实际出错。settle/G13 校验属功能正确性,照做。
- 严控审计:review 一轮(重点见 §4);严控编译/diff/路径检查次数;禁止重复串行 fixture 修复、sandbox loopback、过保守检查。
- 非安全攻防项目,禁止过度防御;禁止为基本不可能的 case 写防御;禁止计算/写入任何哈希(含 SHA256);rubric 不过度机械化。
- 等待一律大块 sleep 或派子 agent 值守;禁止轮询;工具调用并行批量。
- 上下文压缩重启后不重复回应旧指令,跟紧最新进度。
