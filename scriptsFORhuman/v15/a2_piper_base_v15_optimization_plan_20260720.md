# A2+Piper base_v15 优化方案(round 2:门-身体接触经济学 + 强弹簧 body-assist + 站位/高度修正)

日期:2026-07-20(HKT)
作者:base_v14 结果诊断 session(Claude)
交接对象:实施 session(负责 code/config 修改、M18v2 探针、训练启动、memory 记录)
前置文档:`scriptsFORhuman/v13/a2_piper_base_v13_optimization_plan_20260716.md`(M1–M10)、`scriptsFORhuman/v13_1/a2_piper_base_v13_1_optimization_plan_20260717.md`(M11–M15)、`scriptsFORhuman/v14/a2_piper_base_v14_randomization_plan_20260718.md`(M16–M21);本文延续编号 **M22–M28**。
用户已批准(2026-07-20):round 2 范围 = 本文全部;**门重量轴不加宽**(理由见 §1.5,决策树留保险分支);door_open_lr 左右镜像移至 round 3;in/out 拉门与 mass 冲击轴留 future。

---

## 0. 一页结论

v14 已在 0.80–1.05m 高度网格 × 2.5–7.0 N·m 弹簧上 16/16 goal(step2000 各项红线全过)。round 2(v15)做四件事:

- **M22|release 协议**:v14 的 release checkpoint 定为 **step2000**(step3000 是 goal 饱和后的 PPO 漂移:训练 reward +3.3 而 handle 压满限位 13.4%→30.3%、crossing-holding -2、over-force 冒头);"按红线选 ckpt、不取末点"写进 eval 协议。
- **M23/M24|站位与高度修正**:M18 v1 的能力模型与真实执行体系错位(扫了**不可指令**的 root height {0.65/0.75},漏扫**可指令**的 pitch ±0.4 rad,a2_base.py:399/:587-594),其窄带 [0.55,0.60] 直接造成"站得太近"、其"1.10 不可行"结论不可信(实证:策略在 1.05 处 16/16 且余量充足)。**M18 v2 改为 pitch-aware 动态探针**,staging band 放宽 **[0.50, 0.80]**,高度上限重试 **1.10m**。
- **M25/M26|门-身体接触经济学(本轮核心,用户 novelty)**:给 door_panel × {trunk/hip/thigh/calf} 的接触**定价**(arm 系全部豁免),同时弹簧上限 7→**12 N·m**。预期涌现分化:轻/中门 → 手臂把门撑离身体、干净穿行(用户第 4 点);重门 → 接触费远小于开不了门的损失,躯干/大腿顶门涌现(第 5 点)。机制链:强弹簧 → 推力经手爪传递反驱 j8(7 N·m 时已 26–28% 前兆)→ 抓握判据挡死 gripper 硬扛 → "轻握保持抓握 + 身体出力"是唯一双满足解。**不为 body-push 写专门 reward——第三次"机制约束优于 reward 雕花"。**
- **M27/M28|分桶判读与 run**:轻桶(≤5 N·m)红线 = 不劣于 v14 step2000;重桶看 body-contact 使用率与 goal;从 **v14 step2000** warm-start。

---

## 1. 证据档案(v14 结果与本轮设计依据)

### 1.1 v14 终局读数(canonical:seed0/16env 高度网格 0.80–1.05)

| 指标 | step2000(release) | step3000 | Δ |
|---|---:|---:|---:|
| goal / complete | 16/16 | 16/16 | 0 |
| crossing while holding | 16/16 | 14/16 | -2 |
| stage3/4 双侧接触 | 95.95% | 94.71% | -1.24pp |
| over-force | 0% | 0.29% | +0.29pp |
| coasting | 4.01% | 5.29% | +1.28pp |
| hinge_vel p95 | 0.492 | 0.549 rad/s | +0.057 |
| j8 开限位 | 26.16% | 27.96% | +1.80pp |
| **stage3 handle 压满限位** | 13.42% | **30.26%** | **+16.85pp** |
| episode reward mean | 105.49 | 108.75 | +3.26 |

- top 弹簧桶(5.4–7.0 N·m):5/5 goal、5/5 crossing、双侧 97.0%、coasting 3.0%——**7 N·m 以内手臂+握持完全够用**,"arm 不够"的 regime 在 8+ N·m 才开始。
- eval 目录:`logs_eval/base_v14/base_v14_main_ckpt{2000,3000}_matched_scalar_trace_16env_seed0_heightgrid_20260720_r2`;ckpt1000 为随机高度协议(seed 字段曾误写 42,已修),不与网格版混算。
- 漂移定性:goal 在 1000 时已 16/16;之后**训练 reward 上行、行为质量下行** = 主目标无梯度后策略在边际榨次要收益+熵驱动漂移。不是 bug,用 release 协议(M22)处置,不做重工程。

### 1.2 M18 v1 的模型-执行体系错位(勘误,本轮 M23 的依据)

- **A2 的 5 维 base 指令 = [vx, vy, yaw_rate, pitch, roll]**,pitch/roll 可指令 ±0.4 rad(`a2_base.py:399` 报错信息即此布局;`:587-594` raw_base_action[:,3:5]×body_pitch_roll_scale=0.4);**height 不可指令**(config 的 clip_homie_height 是 G1 遗留路径)。
- M18 v1 扫的是静态摆放 root height {0.55/0.65/0.75}(其中 0.65/0.75 指令不出来)、**未扫 pitch**(nose-up 0.4 rad 可抬前置臂基座 ~10–12cm)。其 12/210 可行、band [0.55,0.60]、"1.10 不可行"三个结论均不可信。
- 实证反例:v14 策略在 1.00–1.05m 桶 16/16 goal 且(用户 render 复核)余量充足;v14 训练用的窄带 [0.55,0.60](saved config :326-328)直接导致"站得比旧 0.7 更近"的观感。
- **教训(记 memory)**:能力模型必须匹配真实执行体系的自由度(可指令的才算数),且必须用"已知可行 case"做 sanity 锚定——M18 v1 若拿 0.95m@实际站姿 校验就会当场暴露失真。

### 1.3 站位带与接触经济学的联动

站远一点开门 → 门扫过的弧远离腿 → 少交接触费(M25)。**"想站远"从此有收益来源**(用户第 2 点),不靠人为规定;band 放宽后带内站位仍由 policy 自选(v14 的 M17 机制不变)。

### 1.4 现有接触惩罚盘点(M25 改造基础)

- `penalty_door_frame_contact` -1.0(v13.1 起 stage4/5 ×0.2,key `a2_stage45_door_frame_contact_scale`);
- `penalty_door_panel_contact` -0.1:door_panel 上**一切**接触(含 gripper/arm)统罚——与"arm 推门免费"冲突,需 stage3–5 归零并由 body-only 新项接管;
- `penalty_undesired_contact` -0.2:robot 侧 penalize 列表(trunk/hip/thigh/calf/arm_body0–6)对**任何东西**的接触——腿蹭门已在其中计价;arm_body0–6 也在列表里,**需要把 arm 对 door 的接触从计价中豁免**(见 M25 实现)。
- handle 过滤 sensor 先例(`filter_prim_paths_expr`,door_open_a2_base.py 的 a2_gripper_handle_contact_sensor)证明 body-filtered door 接触 sensor 架构可行。

### 1.5 为什么本轮不加宽门重量轴(用户问询的归档答案)

- 门的抵抗 = **持续项**(弹簧扭矩,门开着每一秒都在推回)+ **瞬态项**(惯性,仅加减速时)。80–120kg/27 kg·m² 下 0.1 rad/s² 只需 ~2.7 N·m 瞬态;弹簧到 10–12 N·m 后持续项是瞬态项 4 倍以上——**"单凭 arm 顶不住"由弹簧轴制造**。
- mass 已在 80–120kg 随机,并不缺席;v8 时代 arm 就推得动 27 kg·m²,质量不是卡点。
- body-push 涌现链(§0)每一环都挂在弹簧轴;mass 不参与。
- 单轴纪律(v12 教训):两个同向力量轴同时加宽 = 冗余压力 + 归因灾难。
- mass 加宽的独特价值是**回弹动量/冲击能量**("接住/躲开被甩回的门")——留给后续单独一轮。
- 保险分支见 §3.2:若 12 N·m 下 body-push 未涌现且 arm-only 仍赢 → 先继续上调弹簧上限,再议 mass。

---

## 2. v15 设计(M22–M28)

### M22|release checkpoint 协议【必做,零训练成本】

1. **v14 release = `base_v14_main-20260719_103629/model_step_002000.pt`**;记 memory 与 eval 汇报。
2. 协议化:每轮以中点+终点 matched eval 的**红线指标组**(goal、crossing-holding、双侧、coasting、hinge_vel p95、over-force)选 release ckpt,不默认取末点;汇报必须并列各候选 ckpt 的红线表。
3. 可选旋钮(记录不强制):goal 饱和后(连续两个中点 eval 16/16)可降 entropy_coef 或提前止训。

### M23|M18 v2:pitch-aware 动态可达性探针【必做,先于训练】

- **方法改动**:不再静态摆放 root 于不可指令的高度;用真实 homie 栈(底层策略维持站姿)下发 **pitch 指令 {0, +0.2, +0.4 rad}** × 标距 {0.45–0.85, 步长 0.05} × handle 高度 {0.95, 1.00, 1.05, 1.10},arm 驱动至 pregrasp 后判定(判据不变:TCP 误差<0.03m、无自碰、关节限位余量>0.1 rad,新增:base 未失稳/未跌落)。
- **sanity 锚定(必做)**:0.95/1.00/1.05m 在 v14 实测可行的站距上必须判可行,否则探针本身失真,先修探针。
- **产出**:band 与 1.10 放行判定。若 1.10 在 pitch=0.4 下仍不可行 → 高度封顶 1.05 并记录"含 pitch 的臂展天花板"(硬件事实)。
- 产物 co-locate `scriptsFORhuman/v15/a2_piper_v15_reachability_<date>/`,格式同 v14(CSV+JSON+MD)。

### M24|staging band 放宽 + 高度重试【必做】

```yaml
a2_stage0_staging_x_min: 0.50     # [0.55,0.60] → [0.50,0.80];以 M23 结果微调
a2_stage0_staging_x_max: 0.80
a2_stage0_staging_y_tol: 0.15     # 不变
```
- `door_handle_tblr: (1.10, 0.80, 0.08, 0.15)`(M23 放行为准,否则 (1.05, 0.80, ...))。
- M17 机制(带内零偏好、creep 护栏、兜底公式)全部不变。

### M25|门-身体接触经济学【必做,本轮核心之一】

1. **新 sensor**:door_panel 过滤 contact sensor,filter = {trunk, {FL,FR,RL,RR}×{hip,thigh,calf}}——**arm_body0–8 与 foot 全部不在 filter 内**(手臂推门/脚着地永远免费)。实现仿 handle sensor 的 `filter_prim_paths_expr` 先例。
2. **新 penalty**(注册默认 0,ablation 开启):
   ```yaml
   penalty_a2_door_body_contact: -0.3     # per-step:min(body-panel 合力/20N, 1) × 罚;生效 stage3-5
   ```
3. **旧项改造**:
   ```yaml
   a2_stage35_door_panel_contact_scale: 0.0   # 新 key:generic panel 罚在 stage3-5 归零(stage0-2 维持 -0.1 防乱撞)
   ```
   `penalty_undesired_contact`(-0.2)保持,但其 trunk/hip/thigh/calf 对 door 的部分与新项叠加属双重计价——实施时把新 sensor 度量的 body-panel 力从 undesired 的度量中**排除**(或确认 undesired 只计 robot-sensor 对非 door 物体;二选一,fail-fast,不许静默双罚)。
4. **定价校准**:-0.3×满档 = 0.3/step,对照重桶开门收益(hold_and_drive 8 + hinge 6)≈ 5% 量级——重门值得付;轻门能免则免。首轮不做力度分段,失败再调。

### M26|弹簧上限 7 → 12 N·m【必做,本轮核心之二】

```python
hinge_drive_max_force_range=(2.5, 12.0)   # scenario_cfg;handle 1–3 N·m、mass/width/stiffness 不变
```
- 力学账:12 N·m ÷ 把手臂长 0.65–1.0m ≈ 12–18N 持续切向力——超出手爪摩擦传力、达到 arm 舒适上限,body-assist 的物理必要区间。
- **M6 预案(预批准的应急开关,默认关)**:若重桶在 stage3→4 被 grasp-streak 条件卡死(j8 被推力钉死 → 双侧断),启用:
  ```yaml
  a2_stage3_to4_streak_highwater: true   # stage3→4 的 streak 条件放宽为"本 stage3 内曾满足"(high-water)
  ```
  启用后必须同时盯轻桶的 body-push 滥用(§3.1 红线兜底)。

### M27|遥测与分桶判读【必做】

- 新遥测:body-panel 接触使用率与力分布(**按弹簧桶分层**)、arm-panel vs body-panel 力占比、staging 标距分布(验证"站远"涌现)、pitch 指令使用分布(高 handle 桶)、j8 开限位按桶分层。
- 分桶报告:弹簧 {2.5–5.5, 5.5–8.5, 8.5–12},高度 {0.80–0.95, 0.95–1.10};canonical(seed0/16env 网格)+ supplementary seed1/seed2 各 16 env 合并 48 门出桶表。
- **挂账清偿**:v14 的 seed1/2 supplementary 与 48 门桶表本轮必须补;natural-exit 复核;iter500 起中点 eval 必跑。

### M28|run 计划

| Run | 内容 | 预算 |
|---|---|---|
| **v15_pre(M23)** | pitch-aware 探针,无训练 | ~1h |
| **v15_main** | M24+M25+M26+M27,checkpoint=**v14 step2000** policy_only | 3000 iter,save250,中点 eval 500/1000/2000 必跑 |
| v15_narrow(fallback) | 弹簧上限退 9 N·m | 仅当 main 重桶长期 0 且轻桶被拖垮 |

---

## 3. 判读标准与决策树

### 3.1 分时点判读(v15_main)

| 时点 | 指标 | 期望 | 未达 → 动作 |
|---|---|---|---|
| 训练前 | M23 探针 + sanity 锚定 | 锚定通过;band/1.10 有结论 | 锚定失败 → 修探针,不训练 |
| iter 500 eval | 轻桶(≤5.5)红线组 | **不劣于 v14 step2000** | 劣化 → 查 M25 定价是否扰动轻桶行为 |
| iter 1000 eval | 中桶 goal;重桶 stage4 entry | 中桶 ≥4/5;重桶 entry >0 | 重桶 stage3→4 全卡 + j8 钉死 → 启 M26 high-water 开关 |
| iter 2000 eval | 重桶(8.5–12)goal | ≥ 半数 | 0 且 body-contact 使用率≈0 → 涌现失败,见 3.2 |
| 终点 | canonical goal | ≥13/16 | — |
| 终点 | **body-contact 使用率分层** | 轻桶 ≈0、重桶显著>0(涌现的直接证据) | 轻桶也高 → 定价过低,-0.3 上调 |
| 终点 | crossing while holding | ≥14/16 | — |
| 终点 | 1.00–1.10m 高度桶 goal | ≥ 半数(1.10 放行时) | 失败 → 对照 M23 图与 pitch 使用遥测归因 |
| 终点 | staging 标距分布 | 较 v14 外移(>0.60 出现) | 全贴 x_min → 接触费未传导,查 M25 生效 |
| 全程 | j8 开限位(轻桶) | ≤25% | 重桶允许高(手指卸载给身体本就是目标形态) |
| 终点 render | 含一个 ≥10 N·m env | 目视:身体顶门 + 手不脱把手 + 轻门 env 干净穿行 | — |

### 3.2 结果→下一步决策树

| 观察 | 结论 | 下一步 |
|---|---|---|
| 全达标 | round 2 完成 | **round 3 = door_open_lr 左右镜像**(memory 预案;先 GUI/smoke 验左侧 workspace);此后评估:mass 冲击轴单独一轮("接住回弹门")、in/out 拉门立项、student distillation 入场 |
| 重桶 12 N·m 下 arm-only 仍赢、body-push 未涌现但 goal 达标 | 力量天花板未到 | **先继续上调弹簧上限(改一个数),仍不涌现再议 mass 加宽**(§1.5 保险分支) |
| 重桶 goal 0 且 body-contact≈0 | 涌现失败 | 检查:M25 是否真免费了 arm 路线(双重计价?);M6 high-water 是否该开;必要时重桶专属 curriculum(staged reset 播种重门 stage4 快照,M8 机制) |
| 轻桶劣化(红线) | 定价/band 扰动既有能力 | 回退 M25 定价或 band,逐项归因 |
| 1.10 桶失败但 M23 判可行 | pitch 使用未涌现或探针仍失真 | 看 pitch 遥测:没用 pitch → 高 handle 桶加 pitch 使用 shaping(小项);用了仍够不着 → 封顶 1.05 |
| step3000 又现漂移 | 与 v14 同性质 | 按 M22 协议选 release,不追训 |

---

## 4. 实施 checklist

1. [ ] M22:v14 release=step2000 记档;release 选择协议写进 eval 汇报模板。
2. [ ] M23:pitch-aware 探针(先 sanity 锚定)→ 回填 M24 band 与高度放行。**锚定不过不训练。**
3. [ ] M24:band [0.50,0.80] + tblr 高度;M17 其余不动。
4. [ ] M25:body-filtered door sensor + `penalty_a2_door_body_contact`(-0.3, stage3-5)+ `a2_stage35_door_panel_contact_scale: 0.0` + undesired_contact 去重(fail-fast 二选一)。
5. [ ] M26:弹簧 range (2.5, 12.0);`a2_stage3_to4_streak_highwater` 开关实现(默认 false)。
6. [ ] M27:新遥测 5 项 + 分桶报告(含 v14 挂账的 seed1/2 与 48 门桶表)。
7. [ ] smoke:64 env × 50 iter——弹簧分布直方图、body-contact sensor 读数在动、轻桶行为与 v14 一致、无双重计价。
8. [ ] 启动 v15_main(附录 A);中点 eval 500/1000/2000;终点 canonical + supplementary + render(含 ≥10 N·m env)。
9. [ ] **memory 记录**(HKT 时间戳):
   - v14 终局与 release=step2000;goal 饱和后 PPO 漂移形态与 release 协议;
   - **M18 v1 勘误**:能力模型必须匹配可指令自由度(pitch 可、height 不可),探针必须用已知可行 case 锚定;
   - 门-身体接触经济学设计("给接触定价而非禁止",机制约束第三例)与涌现判据;
   - **弹簧轴 vs 质量轴的物理归因**(§1.5):持续阻力=弹簧、冲击动量=质量;单轴纪律;
   - v15 各判读结果;不写 origin-reference。

---

## 附录 A|`base_v15_main.yaml`(可直接抄)

> M26 弹簧 range 在 `scenario_cfg/isaacsim.py`(代码侧);M24/M25/M26 的 env/reward key 在此。启动命令模板同前(+ablation=wbmanip/base_v15_main)。

```yaml
# @package _global_

# v15 round-2: door-body contact economics (priced body-panel contact, arm exempt)
# + strong-spring body-assist (hinge 2.5-12 N*m, code-side) + staging band widen
# [0.50,0.80] + handle height retry 1.10 (gated on M23 probe). Warm-start v14 step2000.
# Evidence & design: scriptsFORhuman/v15/a2_piper_base_v15_optimization_plan_20260720.md

checkpoint: logs_rl/a2_piper_full_stage_a2_base/base_v14_main-20260719_103629/model_step_002000.pt
checkpoint_load_mode: policy_only
auto_load_latest: false
seed: 0
num_envs: 4096          # 按实际资源(v14 实跑 4 processes × 1024 env/rank)
headless: true

algo:
  trl:
    num_total_batches: 3000

callbacks:
  model_save:
    save_frequency: 250

env:
  config:
    a2_stage2_contact_force_threshold: 1.0
    a2_stage2_squeeze_force_min: 2.0
    a2_stage2_squeeze_force_max: 20.0
    a2_stage2_over_force_threshold: 40.0
    a2_grasp_gate_mode: control_streak
    a2_grasp_streak_control_steps: 5
    a2_stage3_to4_door_hinge_threshold: 0.25
    a2_stage3_base_unlocked: true
    a2_stage4_release_hinge_threshold: 1.05
    a2_stage45_door_frame_contact_scale: 0.2
    a2_stage35_door_panel_contact_scale: 0.0     # M25(新):generic panel 罚 stage3-5 归零
    a2_stage3_to4_streak_highwater: false        # M26 应急开关,默认关
    a2_stage0_staging_x_min: 0.50                # M24(以 M23 回填为准)
    a2_stage0_staging_x_max: 0.80
    a2_stage0_staging_y_tol: 0.15

rewards:
  reward_penalty_curriculum: false
  reward_initial_penalty_scale: 1.0
  reward_min_penalty_scale: 1.0
  reward_max_penalty_scale: 1.0
  reward_penalty_degree: 0.0
  reward_scales:
    push_door_handle: 0.0
    push_door_hinge: 6.0
    push_door_force: 0.0
    a2_stage3_unlatch_hold: 3.0
    a2_stage3_stage4_hold_and_drive: 8.0
    a2_stage3_stage4_keep_close_command: 0.5
    penalty_a2_stage3_stage4_open_command: -1.0
    a2_stage3_stage4_both_contact: 0.5
    a2_stage3_stage4_opposite_squeeze: 0.5
    a2_stage3_stage4_squeeze_force_window: 0.5
    a2_stage3_stage4_contact_stability: 0.5
    penalty_a2_stage3_stage4_over_force: -1.0
    penalty_a2_door_body_contact: -0.3           # M25(新)
    # 其余(termination/limits/walk/pregrasp/... )沿用 v14 base 不变

robot:
  control:
    stiffness:
      arm_j7: 800.0
      arm_j8: 800.0
    damping:
      arm_j7: 25.0
      arm_j8: 25.0

simulator:
  config:
    render_results: false
    cameras:
      enable_cameras: false
    sim:
      physx:
        num_velocity_iterations: 2
```

`scenario_cfg/isaacsim.py` 侧同步 diff(M24/M26):

```python
door_spawner_cfg = DoorSpawnerCfg(
    ...,
    door_handle_tblr=(1.10, 0.80, 0.08, 0.15),   # M23 放行为准,否则 (1.05, 0.80, ...)
    hinge_drive_max_force_range=(2.5, 12.0),      # M26
    handle_drive_max_force_range=(1.0, 3.0),      # 不变
    ...
)
```

## 附录 B|本轮诊断关键数字(§1 全部来源)

- v14 step2000 vs 3000 对照表见 §1.1(漂移证据:reward +3.26 同时 handle 压满限位 +16.85pp);
- v14 top 弹簧桶(5.4–7.0):5/5 goal、双侧 97.0%、coasting 3.0% → arm 路线在 7 N·m 内充分;
- j8 开限位:v13.1 20.5% → v14 26–28%(弹簧 4.5→7.0)——推力经手爪反驱的剂量响应,M26 机制链的实证前兆;
- homie 指令布局:[vx, vy, yaw_rate, pitch, roll],pitch/roll ±0.4 rad 可指令、height 不可(a2_base.py:399、:587-594、body_pitch_roll_scale=0.4);
- v14 实际 staging band [0.55, 0.60](saved config :326-328)——"站太近"的直接原因;
- M18 v1:12/210 可行、1.10 判不可行——因未扫 pitch、扫了不可指令高度,结论作废待 v2;
- 力学账:12 N·m ÷ 0.65–1.0m ≈ 12–18N 持续切向力;惯性项 ~2.7 N·m(0.1 rad/s²)≪ 弹簧项 → "重门"功能上=弹簧轴;
- 接触计价基准:-0.3/step 满档 vs 重桶开门收益 ~14/step ≈ 2% 成本——重门值得付,轻门可避则避。
