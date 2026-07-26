# DoorDog opencode/omo Pipeline

本文件是 **opencode/omo runtime** 在本 repo 的 canonical pipeline。它只在 opencode(具备 `task()`、`team_*`、`skill` 工具的 runtime)下生效;Codex CLI 走 root `AGENTS.md` §1–12 + `.codex/TEAM.md`。

## 0. 规范来源与优先级

- root `AGENTS.md` 的 **§2(fail-fast)、§3(file-based memory)、§12(不可违反的结论)** 是唯一规范源,本文件引用其生效,不复制、不弱化、不与之竞争;冲突时 root 优先。
- 本文件只管 omo 的执行形态:委托方式、角色触发、IsaacLab 工作指引、验证与证据纪律。
- 本文件是**护栏 + 菜单**,不是流水线:不规定固定阶段顺序,不强制每个角色都被使用。

## 1. 委托哲学:目标式委托 + 自主执行者

实现工作默认以**目标式委托**交给自主执行者(`deep` category 或 `hephaestus`),而不是重型合同 + 逐步指令:

- 给**目标、约束、验收标准、证据要求**,不给逐步操作手册;执行者自己探索、决策、验证。
- 琐碎/单行改动用 `quick`;lead 已有完整上下文的极小改动可 lead 直接做。
- 委托 prompt 必须携带第 4 节的约束摘要块(fail-fast + IsaacLab 提醒),因为执行者是 fresh session。
- 只有 **≥2 个并行 writer** 时才要求显式 `WRITE_SET` 互斥;单 writer 时写出工作范围即可。
- Lead 保留且不出让:scope 变更、lease 分配、review 仲裁、memory 落盘权威、git add/commit/push、宣布任务完成。

## 2. 护栏(不可违反,6 条)

**G1 fail-fast**(root §2):不为"所谓的 code 健壮性"添加不必要的 guard、fallback、silent downgrade 或错误吞噬;不强行让仿真/训练在 invalid state 下继续;缺失配置、shape/type/device mismatch、unsupported API、invalid state 必须清晰报错,让问题在运行/训练中暴露;禁 `as any`/`@ts-ignore` 类压制。

**G2 memory 门**(root §3):开始任何实现、调试、review 或文档更新前,先按 route 做最小 memory 读取(PF1),检索任务关键词命中既有经验(PF2);涉及 IsaacLab API 时必须完成 PF3(见 §3)。开工时必须列出实际读取路径。当前项目无相关 memory 机制时忽略。

**G3 证据纪律**:`STATIC_PASS`(编译/解析/静态检查)、`RUNTIME_PASS`(真实运行)、`INCONCLUSIVE`、`NOT_RUN` 必须明确区分;**subagent/worker 自报不构成证据**,只有 lead 亲自看到的文件系统状态与命令输出才算;禁虚假 PASS、禁 silent downgrade。

**G4 多 writer 纪律**:并行 writer 的 `WRITE_SET` 两两不相交;writer 交付后 lead 必须做文件系统审计(`git status`/diff/grep 实证),不接受"已完成"汇报本身;越权写入由 lead 回退并纠偏。

**G5 review 节制**:一个 concern 只有一个 owner(默认 oracle 承载代码质量 + IsaacLab 语义 review);narrow fix 只重跑受影响的检查,不 full rerun;不为流程完整性重复 review;无 durable memory delta 不起 memory 流程。

**G6 Git**:只有 lead 能 `git add/commit`;默认不 push,用户明确要求才 push;child/subagent 禁止一切 git 写操作。

## 3. IsaacLab 工作指引(本项目强依赖)

涉及 scene、object/camera/robot spawn、observation、reward、env config、training semantics 或其他 IsaacLab API 时:

1. **Local source 优先**:`/home/baoquanc/workspace/IsaacLab` 是本机 IsaacLab 源码,核 API signature/语义/行为时先读它。
2. **Context7 查官方文档**:IsaacLab 的 library ID 是 `/websites/isaac-sim_github_io_isaaclab_main`(先用 `resolve-library-id` 确认);其他外部库(npm/pip/cargo 包、框架、SDK)也灵活用 Context7 查当前文档,不凭训练记忆猜 API。
3. **librarian agent**:需要 OSS 使用范例、多 repo 分析、remote 实现参考时派 librarian(可后台并行)。
4. **High-level API 优先**(root §2):能用 IsaacLab high-level API 完成,禁止用 `pxr.UsdGeom`、`stage.DefinePrim`、`omni.usd` 等 low-level USD API 绕过 framework contract;确需 low-level 时必须说明 high-level 不适用的具体原因。
5. **仿真/训练代码尤其要 fail-fast**:invalid state 必须在运行时立刻暴露,严禁用保护性操作把仿真/训练"救"下去。

## 4. 委托约束摘要块(粘贴进每个实现委托 prompt)

```text
约束(必须遵守):
- fail-fast:不加多余 guard/fallback/silent catch/类型压制;invalid state 直接 raise。
- IsaacLab:优先 high-level API;改 API 用法前先核 local source(/home/baoquanc/workspace/IsaacLab)或 Context7。
- 只写本任务范围内的文件;禁 git add/commit/push;不改既有测试(除非 lead 显式授权)。
- 交付汇报:STATUS / files touched / 执行的命令与原始输出 / 未验证声明;自报需可被文件系统复核。
```

## 5. 角色触发速查表(菜单,非工位;lead 按需自由选配)

| 触发条件 | 调用 |
|---|---|
| "X 在哪个文件/哪段逻辑在哪" | `explore`(后台,1–3 个并行;独立角度可至 5) |
| 外部库文档、API 行为、最佳实践、OSS 范例 | `librarian` + Context7 |
| 需求模糊/有隐藏意图/多种解读 | `metis` |
| 计划文件落在 `.omo/plans/*.md` 需要评审 | `momus`(prompt 即文件路径) |
| 实现:hairy、需自主探索攻坚 | `deep` category 或 `hephaestus`(目标式委托) |
| 实现:琐碎、单行、明确位置 | `quick` category 或 lead 直接 |
| hard logic、架构取舍、算法 | `ultrabrain`(只给清晰目标) |
| 常规模式解不了的题 | `artistry` |
| 文档、prose、技术写作 | `writing` |
| 图像/视频/PDF、render 复核 | `multimodal-looker` |
| review、疑难调试、重大实施后复检 | `oracle`(read-only;一次调用可分区多 concern) |
| runtime 调试(崩溃/悬挂/静默失败) | `debugging` skill(假设驱动循环) |
| commit(仅当用户要求) | `git-master` skill |
| 多模块大改、需要并行多 writer 协调 | team-mode(见 §6) |

无触发则不调用;不为"更稳妥"加码角色或 review 轮次。

## 6. team-mode 使用备注(仅多 writer/多并行时需要)

- Team 是 ephemeral:任务终态全达成即按 closure sequence 关闭(shutdown_request + approve × 成员 → team_delete),不闲置。
- 并行 writer ≤4,`WRITE_SET` 两两不相交;冲突串行。
- 成员通过 `team_send_message` 协调;lead 不做高频 polling,等完成通知。
- Two-strike:同一任务同一 root cause 异常中断两次,lead 才接管其最小剩余工作;user/lead 主动取消不计入。
- 成员禁止 `delegate-task`(budget 为零),禁止嵌套 team。

## 7. 验证与证据

- 验证命令可由 lead 直接跑,或委托 `quick`/junior 执行并回贴原始输出;**判定权在 lead**。
- GPU/IsaacSim/smoke 等资源 lease 归 lead 分配与监控;smoke 类长跑用 tmux 前台,不用 setsid/detached。
- 交付前底线:相关测试真实通过、`lsp_diagnostics`/py_compile 干净、有 runnable 入口的行为变更必须真实跑过一次;"should pass"不是验证。
- Pre-existing 问题:记录,不修(除非用户要求)。

## 8. Route 自判(轻量)

- **FAST**:bounded、低风险、可逆(问答、typo、单行修复、明确 config tweak)→ lead 直接做 + 一次 targeted validation + 一次 diff 审计,不委托、不加码。
- **STANDARD**:普通 product work(默认)→ §1 委托哲学 + §2 护栏。
- **HIGH_RISK**:大爆炸半径/难回滚(跨子系统架构、数据迁移、昂贵长训练、安全边界)→ 先向用户提交简短 brief(为什么 STANDARD 不够、scope、资源、停止条件),拿到明确同意才开工。

执行中风险升级则向上换 route;不得把复杂任务拆成伪 simple 任务,也不得为多用 agent 向上升级。
