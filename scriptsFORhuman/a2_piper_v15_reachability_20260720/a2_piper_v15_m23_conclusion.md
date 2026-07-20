# A2_Piper v15 M23 可达性结论(policy-driven probe,取代静态/脚本化探针)

日期:2026-07-20(HKT)
作者:M23 接管 session(Claude)
状态:**M23 完成。1.10m 放行。M24 可以开工(含一条必要修正,见 §4)。**

---

## 1. 结论(M24 直接消费)

| 决策项 | 结论 | 依据 |
|---|---|---|
| **handle 高度上限** | **1.10m 放行** | v14 release policy(step2000)在 1.05–1.10m 的 16 点 inclusive 网格上 **16/16 goal、16/16 stage5、15/16 crossing-while-holding**,zero-shot、未重训(§2) |
| staging band | [0.50, 0.80] 维持 v15 plan 目标,**但必须先做 §4 的 stage0 推进条件修正**,否则 band 会塌缩到外缘 | §4 机理 + v14 anchor standoff 全部聚在外缘 0.57–0.60 的实证 |
| 高把手站姿事实 | 策略用 **roll −0.30~−0.42(近指令限幅)+ 小 pitch + yaw −0.08~−0.67** 的全身侧倾解决高把手,不是站高(height 不可指令)也不主要靠 pitch | probe trace,16 env 站姿一致(§2.2) |

## 2. Policy-driven probe(本次的正式 M23 证据)

### 2.1 方法

不再用脚本化控制器逼近策略能力,直接以 **v14 release policy 本体**作为可达性仪器:标准 matched eval 管线(eval_agent_trl,seed0、16 env、each-env-first-episode、forced-close/oracle 关闭),仅两处改动:

- `env.config.a2_eval_door_handle_height_linspace=[1.05, 1.10]`(既有 deterministic 高度网格钩子);
- `scenario_cfg/isaacsim.py` 的 `door_handle_tblr` 顶 1.05→**1.10**(此改动=M24 的高度 diff,已就位,若最终否决 1.10 则回退)。

其余(staging band [0.55,0.60]、弹簧 2.5–7.0、handle 1–3)保持 v14 原样。

产物:`logs_eval/base_v15/base_v15_m23_policyprobe_h105_110_16env_seed0_20260720/`
(metrics_eval.json、stage2_5_step_trace.json、per-env records、eval logs)

### 2.2 结果

- **goal 16/16、max_stage 全 5**,高度 1.0500–1.1000(步长 1/300 m)全覆盖;
- crossing-while-holding 15/16(env13 @1.093 为 False,孤例);
- 门全部推到 2.59–2.618 rad(铰链上限);
- 进入 pregrasp(stage2 首帧)站姿:roll −0.298~−0.423、pitch −0.037~+0.089、yaw −0.079~−0.673、root_x(原点系)−0.547~−0.675——**与 v14 已知站姿同一族,无退化迹象**。

### 2.3 anchor 语义的最终处理

"probe 必须复现 v14 实测三点"的 anchor 要求,由 policy-probe **构造性满足**(仪器即策略本身,1.05 及以下另有 v14 heightgrid eval 的 16/16 原始证据)。脚本化探针的 anchor 失败被证明是仪器限制,不是能力缺失(§3)。

## 3. 脚本化探针的处置(37+ 轮修复的终局)

### 3.1 已修复并保留的代码(可复用,49/49 tests pass)

`gr00t/rl/scripts/a2_piper_v15_dynamic_reachability.py` + tests,本次改动:

1. **Projected DLS**:IK 每步 q_des 夹入 soft-limit 盒(投影下降,搜索卫生);限位类逐步校验降级为诊断,可行性只由末态 gate(tcp<0.03、margin>0.1、无自碰、base 稳定)判定。修复了 R36 的 arm_j2 边界抖动崩溃(其默认位 0.0 本就在 soft 下限 0.157 之外)。
2. **anchor 姿态回放**:anchors 改为回放 v14 实测 (pitch, roll)(来自 ckpt2000 trace env9/12/15);新增 roll 指令轴(ProbeSpec/evidence/CSV/assess/`--batch-roll`);posture 指令在 base_settled 后再生效(复刻策略时序)。
3. **anchor gate 语义**:合同违规仍 raise;可行性 miss 如实上报(stderr WARNING + evidence),不再炸批。

### 3.2 为什么最终弃用它作为裁决仪器

三轮实测(r38/r39)链条:posture 从第 0 步下发 → staging 链被扰乱、arm 不激活;改为就位后下发 → roll 一挂上 standoff 保持就漂移(vx 单通道修不住)。根因:**大侧倾下"保持站位+伸臂"是 v14 策略学出的全身协调技能,任何手搓 vx+posture 控制器都在重造这个技能**——38 轮修复失败的共同本质。脚本化探针只能给出"手搓控制器的下界",对高把手 cell 系统性低估(静态版 M18 v1 更是双重失真:漏扫 roll、扫了指令不出的 root height)。r39 anchors 证据存档于本目录 `scripted_probe_anchors_r39_supplementary.json`;**108-cell 网格未运行(决策上不需要,不再花 GPU)**。

**方法论沉淀(记 memory)**:可达性/能力类问题,当存在已训成的策略时,策略本体就是最高保真的探针;脚本化仪器必须先通过"已知可行 case 锚定",锚定不过说明仪器错,不是能力错。

**运维注记(复用脚本探针者必读)**:本环境下脚本探针子进程在 evidence JSON 完整落盘**之后**、IsaacSim teardown 阶段以 exit 139(SIGSEGV)退出(r38/r39 两次复现;headless 关闭的已知行为)。父编排 `_run_child_batch` 目前按子进程退出码判成败,会把"已成功写出证据"误判为失败——若复活脚本探针跑网格,应改为以 `_validate_child_batch_output` 的输出文件校验为准、对 teardown 段错误容错(显式白名单该退出码并记录,不做静默吞噬)。

## 4. M24 必要修正:stage0 推进条件加 base-still(否则 band 塌缩)

**机理**:当前 `_stage_0_to_1_advance_condition` 是"进带即推进"。机器人从远处走近,standoff 首次进入 band 必然发生在**外缘**,随即被 stage1/2 的 base-forward-creep 惩罚钉住 → band 退化为"外缘值"。实证:v14(band [0.55,0.60])的 anchor standoff 全部是 0.57–0.60。若 M24 直接放宽到 [0.50,0.80],所有 env 将站在 ~0.80——高把手必然够不着。

**修正**:推进条件增加 base-still(`get_physical_homie_commands()[:,:3]` 范数 ≤0.1,与 stage1 gate 同式)——机器人**停在带内**才推进,停哪由策略选,这才兑现 M17"带内零偏好、站位交还 policy"的设计意图。v15 plan 的 M24 实施时必须包含此项;判读时用"staging 标距分布"遥测验证站位真的分散(而非钉在某一边)。

## 5. 交接清单(给 M24+ 的 work session)

- [x] M23 结论:1.10 放行(§1);probe 产物在 `logs_eval/base_v15/.../policyprobe.../`。
- [x] `scenario_cfg/isaacsim.py` tblr 顶已置 1.10(即 M24 高度 diff 的一半)。
- [x] 脚本化探针与测试已修复至 49/49(§3.1),留作日后仪器,不阻塞。
- [x] 四个 `.orig/.rej` patch 残渣已确认为垃圾并清理。
- [ ] M24:staging band [0.50,0.80] + **§4 base-still 修正** + walk_to_door 带内最近点跟踪(v15 plan M17 原文)。
- [ ] M25–M27 按 v15 plan 原文;M28 训练照旧从 v14 step2000 warm-start。
- [ ] memory 记录:§1 结论、§3.2 方法论、§4 机理与实证(v15 plan 的 checklist 第 9 条框架内)。
