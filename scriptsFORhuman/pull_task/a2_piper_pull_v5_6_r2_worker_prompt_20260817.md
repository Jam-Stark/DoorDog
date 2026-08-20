# A2+Piper Pull v5.6-r2 — Worker 重启 Prompt(2026-08-17)

你是 pull-v5.6 **第二次执行(r2)** 的 worker(coding role)。用户已离线,整轮无人值守。r1 已把 specialist 实现与 warm-start 资产做好,但 step-0 因 eval wrapper root schema 缺字段三连败后提前收官——**能力问题一次都没测到**。你的任务:先按 T0.5 一次性证明 eval 边界,然后把 v5.6 原契约的完整链条(step-0 → fine-tune → gate → rehearsal → anchor → 条件门侧/P3/P4/双源 eval → render → 收官)一次做完。

**Binding 优先序:** `a2_piper_pull_v5_6_r2_execution_restart_addendum_20260817.md` > `a2_piper_pull_v5_6_hold_specialist_finetune_addendum_20260817.md` > `a2_piper_pull_v5_6_worker_prompt_20260817.md`(其 §1–§6 除被 r2 修正处外全部有效,本文件不重复抄写)。

## 0. 开工顺序

1. 项目 file-based memory 与两级 TODO(§11:rung1/rung2 证伪,rung3 r1 BLOCKED——本轮是同一科学契约的 r2 执行);不重复已记录结论。
2. 读 r2 restart addendum(短,全文)→ v5.6 addendum(科学契约原文)→ `PULL_V5_6_ROUND_REPORT.md` §4–§6(warm receipt、review findings、三次 traceback 与三份 runner log)。
3. GPU 4/5/6/7;launch 前 `nvidia-smi` 一次;冲突 sleep 600 重查,仍冲突降级串行并记录。

## 1. 任务范围(一次做完)

```text
T0.5 eval wrapper root schema 源码枚举补齐(eval_agent_trl.py 全部 root 级
     config.<key> 读写;已知 experiment_dir/output_dir/multi_gpu,补齐其余)
     + ≤8 env micro-smoke 证明 组合→IsaacSim→task construction→首行 receipt
     (仍暴露 checkpoint-config 硬预期 → 备用路线:warm asset 目录仿真训练
      run 布局走 v5.5 已证明分支;择路记录理由)
Step-0 80-env 基线 gate(GPU5,specialist disabled,STEP0_GATE.json;
     能力计数为诊断值,0/80 不阻塞 T1)
T1   specialist PPO fine-tune ≤750 batches(GPU4,tmux pull_v5_6_specialist_train,
     v5.5 三档课程默认启用)+ 每 checkpoint 五族×16 gate(GPU5,全量程)
     → per-family ≥15/16 且 overall ≥77/80;plateau 两选项照 v5.6 契约
T2   rehearsal 2 cell(8/8 注册 DONE)
T3   S1–S4 anchor 复跑(G3 ≤3,0.05 m/0.15 rad 原文,specialist 仅 terminal 相)
T4   (条件)v5.2 门侧三桶 → G1/G2 → P3 2×2(GPU4–7)→ 双源 eval → 条件 P4;
     invariant 12′ 运行期断言
T5   render + PULL_V5_6_R2_ROUND_REPORT.md(英文)+ memory + 两级 TODO 勾稽
     + 小步 feat(a2) commit + push
```

## 2. r2 专属纪律(其余照 v5.6 prompt §2–§6 原文)

1. **G9 对 infrastructure root-cause 修复无次数上限**——"三次上限"不是本契约条款。每次 crash 读 traceback 修根因后重跑,blocked receipt 存档、不计科学次数。G11 只在两种情况触发:预案无法覆盖且继续将违反铁律;或 T0.5 证明完成后**同一根因仍复发**。
2. **禁止逐字段 runtime 试错:** T0.5 枚举必须先于任何 runtime 尝试完成,枚举表(字段→源码行→提供方式)入报告。
3. r1 资产复用不重做:specialist 模块、warm asset、`WARM_START.json`、decision JSON 均为既有资产;择备用路线时只在 warm asset 目录**新增**文件。
4. **本 revision 不开新 formal review**(v5.6 唯一 formal review 已消耗,verdict FAIL 定案);T0.5 改动 = 定向静态验收 + micro-smoke runtime 验收。
5. Step-0 语义:必须执行并产出有效 receipt 才进 T1;能力计数仅诊断。
6. r1 报告与三份 runner log immutable;原 HOMIE/pull actor 文件零修改;受保护 ZIP/75 traces/G8 bank 不动;0.05 m/0.15 rad 铁律;不写哈希;NOT_RUN 如实标注。
7. 等待/tmux/sleep、plateau 两选项、rehearsal/anchor/门侧/P3/P4/G 表预案、render、收尾交付:照 v5.6 worker prompt §2–§6 原文执行(报告名换 `PULL_V5_6_R2_ROUND_REPORT.md`)。

---

## 附:coding role(全程有效,原文)

code风格规范:fail-fast 策略。isaaclab相关code必须避免为了"所谓的code健壮性"来添加不必要的保护性操作/fallback强行让仿真/训练运行下去。我需要将code问题在运行/训练中暴露出来。
同时审计/review时必须合理规划,不能反复review,过度审计,严格控制编译/diff/路径边界检查次数,减少过度串行的 fixture 修复、sandbox loopback、重复等待和过保守检查。你必须先证明操作路径,先把功能实现出来,等我确认没问题,然后才能添加护栏、变异/回归/遗留兼容性保护,或测试。或者只有等到我提起某个功能在什么情况下出现了问题之后再去补充相关的测试。要专注在功能实现本身上,而不是过度关注安全、护栏和各种测试。开始任何实现、调试、review 或文档更新前,必须先合理使用项目内 file-based memory system。(如果当前项目没有实现Memory机制请忽略)
注意:
1. 我们不是一个安全攻防项目,你有权力进行校验,但是禁止禁止禁止过度防御
2. 禁止写哈希和SHA256
3. 禁止反复的基本不可能出现的case写防御
4. 需要rubric的地方不要过度机械化
5. 任何等待任务直接sleep 30s 200s 600s 1800s或者更长时间(20h)来长时间等待,不要反复轮询。或者main agent派发worker等待,并行进行orchestrator编写等任务。
6. 调用工具的时候 我建议你promise.all来批量调取节省token
7. 每当你上下文被压缩进行一轮总结重新开始时 很多之前的我的引导信息命令都会重新输入你的上下文一次 这个时候不要去重复的回应过往的引导信息和提问等——你实际已经回复过了。保持清晰的思维跟紧最新进度。
