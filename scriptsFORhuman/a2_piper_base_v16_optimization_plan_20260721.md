# A2+Piper base_v16 优化方案(姿态经济 + 穿行送门 + 门重轴)

日期:2026-07-21(HKT)
作者:base_v15 结果诊断 session(Claude)
交接对象:实施 session。前置:v15 plan(M22–M28)、`a2_piper_v15_reachability_20260720/a2_piper_v15_m23_conclusion.md`。本文编号 **M29–M33**。
用户已批准方向(2026-07-21):v16a 三件套 + mass 轴;远期项见 `a2_piper_longterm_TODO.md`。

---

## 0. 一页结论

v15 已 47/48 goal(release=ckpt2500,M22/M24 修正均验证有效)。v16 修三个已定量确认的行为缺陷,并启动 mass 轴:

- **缺陷 1(姿态无差别饱和)**:pitch/roll 双指令 ~80% 帧钉在 +0.4 限幅,与把手高度无关(低桶 79%/高桶 81%)。免费动作经济学,非任务难度问题。→ **M29 姿态经济正则**。
- **缺陷 2(穿行剐蹭)**:门 100% 由 arm 经 handle 打开(过线前 body 接触 0/10066 帧),但松手时 hinge 仅 1.07–1.25 rad,40/48 env 松手后门被弹簧压回撞上机器人(力 p90 451N),靠身体扛开到 1.75–2.62。→ **M30 非线性计价 + M31 走廊送门**。
- **持握时长已达运动学天花板**:松手 root_x p50=0.38(arm 前置 + 把手弧线随开角远离,上限即 ~0.3–0.5),"更晚松手"无空间,"送门更开再松手"有空间。M31 的核心是**撤销 v13 反甩门规则对松手段的误伤**(分相速度策略)。
- **M32 门重轴**:共享场景保持历史 **80–120 kg**;v16 通过高层 task-object hook 显式选择 **80–160 kg**(round-3 原定冲击轴;注:它不治缺陷 1,立论是回摆动量/冲击鲁棒性)。
- 不进 v16:弹簧 >12(sim 手臂超人,死轴)、左右镜像、真实 Piper 限位、拉门、force-feasible 机制——全部在 `a2_piper_longterm_TODO.md` 排期。

## 1. 证据档案(v15 ckpt2500 × 3 seed,48 门)

- goal 47/48;heavy 弹簧桶 [8.5,12] 18/18;staging standoff p50 0.64–0.71(M24 base-still 修正生效,未塌向 0.80);
- body-panel 接触:1.59% 帧,全部在 stage4/5、root_x 0.25–0.45、hinge 0.94–1.23;**arm-panel 接触 0 帧**;过线前 body 接触 **0/10066**;
- 松手统计:root_x p10/50/90 = 0.28/0.38/0.49;hinge@release 1.07/1.13/1.25;hinge_max 1.75/2.14/2.62(松手后身体扛出);**40/48 env 松手后 body 接触,力 p50/p90 = 37.5/451N**;
- 姿态:pitch>0.1 使用率 低桶 79.0%/高桶 81.4%,pitch/roll p50 均 = +0.400(限幅);
- j8 开限位 ~11% 三桶平坦(推门=形封闭,手指几乎不受载;v15 的"重门 body-assist 涌现"假说被证伪);
- 力学:弹簧回摆 α=maxF/I;I(120kg,0.9m)≈27 kg·m² → 12 N·m 时 0.44 rad/s²;从 1.5 rad+外摆速度松手,回追 ≥2s,足够通过。

## 2. 修改清单(M29–M33)

### M29|姿态经济正则【必做,缺陷 1】

```yaml
penalty_a2_posture_command_l1: -0.15    # 新 reward:-0.15 × (|pitch_raw| + |roll_raw|),全 stage 生效
```
- raw 域(各 ∈[-1,1]),满幅双通道成本 0.3/step——足以打掉"白嫖限幅",不足以压制高把手真实需求(高把手抓取收益 ≫ 0.3);
- 注册默认 0,ablation 开启;λ 备选档 0.10/0.20;
- 这是 force_feasible 研究主线("最小 base 干预 tie-breaker")在门任务的第一次实例化,v15 的 80% 饱和数据即天然 baseline 对照。

### M30|body-panel 计价改非线性【必做,缺陷 2】

```yaml
penalty_a2_door_body_contact: -2.0      # 形态改为 -2.0 × min(F/40N, 1)^2(20N→-0.5,40N+→-2.0/step)
```
- 替换 v15 的线性 `-0.3×min(F/20,1)`(实测对 27–451N 的挤靠太便宜);arm-panel/handle 继续免费;
- 与 M31 联动:让"扛着挤过去"明确劣于"送门+干净走"。

### M31|穿行走廊送门(分相速度策略)【必做,缺陷 2 与旧规则修正】

定义走廊:`corridor = (root_x ≥ 0) | (hinge ≥ 1.0 & stage ≥ 4)`(per-env,锁存至 episode 结束)。

1. `hold_and_drive` 的速度饱和分相:走廊外维持 0.1 rad/s,**走廊内放宽到 0.4 rad/s**(临别一推合法化);
2. 新增走廊开度收益:
   ```yaml
   a2_corridor_door_wide: 2.0            # corridor 内 min(hinge/1.5, 1) × 2.0(root_x<0.8 时生效)
   ```
3. **甩门红线改为 pre-crossing scoped**:coasting/hinge_vel p95 只统计过线前段(v13 的"不甩门"本意即开门段;松手段的定向猛推是期望行为);
4. 遥测:hinge@release、release root_x、松手后 body 接触 env 计数与力分布(§3 判读主指标)。
5. 【预批准应急旋钮,默认关】若中点 eval 显示计价+开度收益仍不足:`a2_corridor_door_wide` 2.0→4.0。

### M32|门重轴【必做,round-3 原定】

```text
# shared scenario_cfg (historical Python default)
door_weight=(80.0, 120.0)
# v16 env.config (YAML selector via the high-level task-object hook)
a2_door_weight_range: [80.0, 160.0]
```
- shared `DoorSpawnerCfg.door_weight` remains `(80.0, 120.0)`; v16 `a2_door_weight_range` applies `(80.0, 160.0)` via high-level task-object replacement;
- doorWeight 已在 metadata → v16 schema-v2 M32+M33 endpoint reporter 输出 mass 桶 {80–110, 110–135, 135–160} 与 M33 endpoint metrics;
- 立论:回摆动量/被砸冲击的鲁棒性(重门回摆更慢、砸上动量更大);**不作为姿态钉死的解药**;
- 弹簧维持 (2.5, 12.0)、drive stiffness 维持 (1, 10)。

### M33|run 计划与判读

| Run | 内容 | 预算 |
|---|---|---|
| **v16_main** | M29+M30+M31+M32,checkpoint=**v15 ckpt2500**(sha 3b55e3e2…)policy_only | 2500 iter,save250,中点 eval 500/1000/1500/2000 必跑 |

判读(endpoint,canonical + 3-seed 48 门;release 按 M22 红线选点):

| 指标 | 期望 | 来源基线 |
|---|---|---|
| goal | canonical ≥15/16 且 pooled ≥46/48 | v15:16/16、47/48 |
| 低桶 pitch 使用率 | **<30%**(p50 离开限幅) | v15:79%、p50=0.400 |
| 高桶 pitch/roll | 保留使用(高把手能力不得回退,高度桶 goal 不降) | 高桶 23/24 |
| hinge@release p50 | **≥1.4 rad** | v15:1.13 |
| 松手后 body 接触 env 数 | **≤10/48**,力 p95 <80N | v15:40/48、451N |
| 过线前段红线 | 双侧 ≥99%、coasting <2%、over-force <2%(scoped 后口径) | v15:99.9/0/0.08 |
| mass 重桶(≥135kg) | goal ≥ 2/3 | 新轴,首轮宽容 |
| crossing-while-holding | ≥15/16 | v15:16/16 |

风险与对策:M29 压垮高把手能力 → λ 降 0.10 或高把手桶豁免(按 handle 高度 obs 可见,策略应自行取舍,先不豁免);M31 走廊放宽引发开门段甩门回潮 → scoped 红线盯住 pre-crossing 段;M30+M31 同时作用导致"绕远路不碰门"的怪解 → render 复核 + episode 长度监控(v15 均值 ~455)。

## 3. 实施 checklist

1. [ ] M29/M30/M31 reward 与 corridor 机制(corridor 锁存 buffer 复用 release-gate 模式);甩门指标 scoped 化(训练 log + eval 同步);
2. [ ] M32 scenario diff + v16 schema-v2 M32+M33 endpoint reporter(显式 mass 桶 + M33 endpoint metrics;不是把 mass 追加进 v15 reporter);
3. [ ] smoke:64 env × 50 iter,确认新罚项发放、corridor 锁存、mass 直方图;
4. [ ] v16_main 启动;中点对照 §2-M33;endpoint canonical + 3-seed 48 门 + render(挑一个 ≥150kg env 与一个低把手 env:验证"低把手不抬头"与"送门后干净通过");
5. [ ] memory:缺陷 1/2 的定量事实、"持握时长天花板"几何结论、v13 反甩门规则的分相修正(设计规则:行为约束要分相表述,全程一刀切会禁掉相邻 phase 的合法解)、M29 作为 force-feasible 主线第一实例的对照数据;
6. [ ] 远期项以 `scriptsFORhuman/a2_piper_longterm_TODO.md` 为准,每轮 plan 落成时核对一次。
