# A2+Piper base_v13.1 优化方案(wide-open 交棒:过线穿行完成 goal)

日期:2026-07-17(HKT)
作者:base_v13 结果诊断 session(Claude)
交接对象:实施 session(负责 code/config 修改、训练启动、memory 记录)
前置文档:`scriptsFORhuman/v13/a2_piper_base_v13_optimization_plan_20260716.md`(v13 设计与 M1–M10;本文延续其编号,新增 M11–M15)
用户已批准本方案(2026-07-17)。

---

## 0. 一页结论

v13_A 已解决 v8→v12 的核心难题:**16/16 stage4、hinge p50 1.28 rad、运动期双侧接触 99.949%、零甩门、开门速度受控**。goal 0/16 的卡点被逐 env 定位为一个新的收益陷阱 + 一个穿行阻力问题:

- **陷阱 1(门挡房租)**:12/16 env 末态满足 stage4→5 的 hinge>1.047 与 handle<0.2,**只差 root_x>0——且 root_x_max 全部在 -0.001~-0.05m(差 1~5cm)**,末帧仍双侧握把手,base 指令中位数 ≈0(主动站住)。站桩收入 ≈12/step(hinge 位置项 4.9 + hold bundle 2.5 + grasp_mild 1.0 + dont_push_handle 3.0 + stage 1.0),而松手过线要先亏光这些还吃 open-command -1。**这是 v11 冻结在 stage4 的转世,是收敛的均衡,不是探索不足。**
- **陷阱 2(穿行阻力)**:4/16 env 已做对前半段(过线瞬间松手,stage5 内握持率 1–4%),但 stage5 内前向速度仅 0.06–0.08 m/s(指令 p50 0.13/上限 0.5),doorframe 接触力尖峰 123–197N 被 `penalty_door_frame_contact: -1.0` 反复惩罚,265–393 步只走到 x=0.45–0.70m(需 1.5m),全部 overtime。**即使解决陷阱 1,按当前奖励也走不完。**
- **v13.1 手术**:stage4 引入 **release gate(hinge≥1.2 锁存)**——置位后停发全部扶门房租、停征 open-command 惩罚、hinge 只留速度项(M11),过线收益恢复全额(M12),stage4/5 撞框惩罚降为 0.2 倍(M13)。从 **A3000 warm-start**,预期 250–500 iter 内 stage5 entry 大面积普及、1000 iter 内 goal>0。
- 附带结论(记入 memory):v13_pre 16/16 证明 M1 gate 实现正确;v13_B 在开训 250 iter 内退化(advance 率 1e-4,eval streak 只剩 3–4)证明 **Kp80 的 1.5N 级抓握经不起训练噪声——M2 的力量余量是"可训练性"的前提**。v13_C(force-only)不必再跑。

---

## 1. 证据档案(v13 A/B 训练与 eval,全部可复查)

### 1.1 产物与总览

| Run | checkpoint | matched eval | 结果 |
|---|---|---|---|
| v13_A step3000 | `logs_rl/.../base_v13_A_main-20260716_225345/model_step_003000.pt`(SHA256 d576ca…7a36) | `logs_eval/base_v13/base_v13_A_ckpt3000_matched_scalar_trace_16env_seed0_20260717_r2` | goal 0/16;stage3/4 entry 16/16;stage5 entry 4/16;16/16 stage_overtime |
| v13_B step1500 | `logs_rl/.../base_v13_B_gate_only-20260716_225413/model_step_001500.pt` | `logs_eval/base_v13/base_v13_B_ckpt1500_matched_scalar_trace_16env_seed0_20260717` | 16/16 stage2;stage2 squeeze-streak max 3–4 |
| v13_pre(C3000+gate patch) | — | `logs_eval/base_v13/base_v13_pre_gatepatch_C3000_..._20260716_r2` | **16/16 stage3** |

v13_A 质量指标全部达标(除 j8):双侧接触(运动期)99.949%、over-force 0.181%、body8 单侧 0.069%、hinge_vel p95 0.212 rad/s、coasting 0.045%、j7 开限位 1.26%;**j8 开限位 14.15%(超 10% 阈值,观察项,不阻塞)**;stage3 handle 压满限位 27.4%(解锁必经,可接受)。

### 1.2 陷阱 1 的逐 env 证据(A3000 trace,first episode)

12 个卡 stage4 的 env:

- hinge_end 1.06–1.62,**全部 >1.047**;handle_end 全部 ≈0(≤0.124);
- **root_x_max = -0.001 ~ -0.05m,无一过线**;末帧 both_contact 全 True、TCP 0.02–0.05m(仍握);
- 末 100 步 base 指令 p50 = -0.078~+0.028、实际速度 ≈0、gripper primitive p50 ≈ -2.1(死握)——**站住是策略选择**。

站桩收入账(hinge=1.28 时):`push_door_hinge` 位置项 (1.28/1.5708)×6≈4.9 + hold bundle(0.5×5)2.5 + `a2_stage4_grasp_target_distance_mild` ≈1.0 + `dont_push_door_handle`(handle 已回位)≈3.0 + stage 1.0 ≈ **12/step**;过线动作需先放弃全部 + 承受 `penalty_a2_stage3_stage4_open_command` -1。

### 1.3 陷阱 2 的逐 env 证据(4 个 stage5 env)

| env | stage5 步数 | root_x 轨迹 | stage5 内握持率 | 前向指令 p50/max | 实际 vel p50 | doorframe 力 max |
|---|---|---|---|---|---|---|
| 11 | 299 | 0→0.48 | 2% | 0.127/0.486 | 0.057 | 123N |
| 13 | 265 | 0→0.45 | 2% | 0.150/0.486 | 0.085 | 177N |
| 14 | 393 | 0→0.70 | 1% | 0.142/0.421 | 0.071 | 197N |
| 15 | 271 | 0→0.47 | 4% | 0.088/0.419 | 0.043 | 41N |

stage5 内 hinge 反而上升(如 1.16→1.50):松手后**身体顶着被闭门弹簧压回的门板**往里钻,蹭框尖峰被 -1.0 惩罚——走得又怕又慢。goal 需要 root_x>1.5,无一到达。

### 1.4 训练曲线与 B 的教训

- A 两段式:iter 250–1750 平台期(stage≈2.9,s4act=0,hinge 0.0004——staged reset 喂 stage3 曝光、巩固抓握);**iter 2000 突破**(s4act 0→0.118,hinge 0→0.066);2250–3000 收敛到 stage 4.00 后趋平(3.92→4.00/750 iter)。**stage4→5 没有等在前方的正收益,与 stage3→4 突破前的形势本质不同——纯续训是下策。**
- B:v13_pre 已证 gate 代码正确(C3000 原策略 16/16 过);但 B 开训后 250 iter 内 advance 率即掉到 ~1e-4,终态 eval streak 只剩 3–4。结论:**Kp80 的 ~1.5N 抓握余量经不起 warm-start 后的训练扰动(critic 重置+探索噪声);Kp800 的 ~7N 余量才是 A 存活的原因。** v13_C(force-only)问题已被 pre+B+A 三点回答,不跑。
- 用户假设复核:"iteration 不够"——不成立为主因(§1.2 站住是收敛均衡;§1.3 已过线者也完不成);"base 不灵活/arm 极限伸展"——现象属实但归因修正:开门到 1.3–1.6 rad 需把手划 ~1m 弧线,**base 在开门期是一路跟进的**;末态伸满是房租最优姿势。stage5 的 base 畏缩(0.13/0.5)才是 base 侧真问题,由 M13 解决。

---

## 2. v13.1 设计(M11–M15)

### 2.0 成功定义

matched eval(协议不变):**goal_reached > 0/16** 为里程碑;满分档:≥12/16 goal、全程保持 v13_A 的抓握质量指标(§1.1 那组阈值)。

### M11|stage4 release gate + 房租断供【必做,核心】

**机制**:per-env bool `_a2_stage4_release_gate`,在 `stage_buf==STAGE_SWING 且 hinge > a2_stage4_release_hinge_threshold(=1.2)` 时置位,**episode 内锁存**(防 hinge 回摆抖动),env reset 时清零。更新点与 M1 streak 相同(`_pre_compute_observations_callback`,每 control step 恰一次;staged-reset 进 stage4 的快照若门已 >1.2 会在首步置位,语义正确)。

**置位后(仅影响 stage4;stage3 一概不动)**:

1. hold bundle 五项(`keep_close_command`、`both_contact`、`opposite_squeeze`、`squeeze_force_window`、`contact_stability`)的 stage4 部分停发:各 reward 函数内乘 `hold_income_mask = stage3_mask | (stage4_mask & ~release_gate)`;建议加 helper `_get_a2_stage34_hold_income_mask()` 统一实现。
2. `penalty_a2_stage3_stage4_open_command` 同乘该 mask——**gate 后松手不再受罚**。
3. `a2_stage4_grasp_target_distance_mild` 乘 `~release_gate`(该项本就 stage4-only)。
4. `push_door_hinge` 在 stage4 gate 后只留速度项:
   ```python
   # 原:(vel*10 + pos/1.5708).clamp(-1,1)
   pos_term = pos_term * hold_income_mask.float()   # stage3 与未置位的 stage4 保持原样
   return (hinge_vel_term + pos_term).clamp(-1.0, 1.0)
   ```
   门已达标后不再为"扶着"付费;速度项保留(继续推更开仍有报酬)。
5. `hold_and_drive`、`unlatch_hold` 不动(unlatch_hold 本有 hinge<0.1 截断;hold_and_drive 在 gate 后自然趋零,无需改)。
6. `dont_push_door_handle`(stage4/5,scale 3.0)**保持不动**:gate 后它成为纯"handle 回位"确认项,与松手方向一致,不构成扶门激励(它不要求接触)。

**新 config key**(required,进 `door_open_a2_base.yaml`):
```yaml
a2_stage4_release_hinge_threshold: 1.2   # release gate 置位角;12 个卡住 env 的 hinge_end p50≈1.24
```

### M12|过线收益恢复全额【必做】

`_reward_target_root_distance`(door_open_a2_base.py:3816-3838)现在对 STAGE_SWING 乘 0.5;改为:

```python
swing = self.stage_buf == DoorPregrasp.STAGE_SWING
reward[swing] *= torch.where(self._a2_stage4_release_gate[swing], 1.0, 0.5)
```

gate 置位后 stage4 的走向 target([2.0, 0, 0.5])收益恢复 ×12 全额(速度 tracking 项即刻生效)。不新增 reward 项——12 个 env 只差 1~5cm,断租+全额走路钱应足够翻转。

### M13|stage4/5 撞框惩罚降档【必做】

`_reward_penalty_door_frame_contact` 内对 stage4/5 的 env 乘系数:

```yaml
a2_stage45_door_frame_contact_scale: 0.2   # stage0-3 维持全额(防 v12_D 式撞框),stage4/5 × 0.2
```

理由:§1.3 的 123–197N 尖峰来自"挤过被弹簧压回的门板"这一必要动作;`penalty_door_panel_contact`(-0.1)不动——身体顶门板是合法手段,4 个 stage5 env 已在用。

### M14|遥测与 eval 汇报修正【必做】

- 训练 log + `eval_to_log` 新增:`a2_stage4_release_gate_frac`(stage4 步内置位占比)、首次过线(root_x>0)env 计数、stage5 内前向速度 p50、doorframe 接触力 p95。
- 修 eval 汇报:denominator=0 的比率必须报 **N/A**,不得写 0%(v13_B 汇报中已出现该问题)。
- 保留 v13 的全部 M9 遥测与 §2.3 甩门监控——**v13.1 的所有改动都不得以牺牲抓握质量指标为代价**(回归红线见 §3 判读表)。

### M15|run 计划

| Run | 内容 | 预算 |
|---|---|---|
| **v13_1_main(主线)** | M11+M12+M13+M14,checkpoint=A3000 policy_only,其余=v13_A 配置 | 2000 iter,save 250 |
| v13_1_noM13(可选消融) | 主线去掉 M13(撞框惩罚保持 -1.0 全程) | 1000 iter;若主线顺利可不跑,若主线 stage5 仍慢则它帮助归因 |

- 不再续跑 v13_B / 不跑 v13_C(§1.4 已回答)。
- eval 协议不变(seed0/16env/first-episode,forced close=false,oracle=false),产物 co-locate `logs_eval/base_v13_1/`;终点 render 2 env × 3 cam,重点目视:**松手时机、过线步态、挤门穿行是否流畅、门回摆是否拍到机器人**。

---

## 3. 判读标准与决策树

### 3.1 分时点判读(v13_1_main)

| 时点 | 指标 | 期望 | 未达 → 动作 |
|---|---|---|---|
| iter 250 | release_gate frac(stage4 步内) | >50% | 低 → 查 gate 置位/锁存实现 |
| iter 250 | 训练 s5act(stage5 active frac) | >2%(v13_A 终态≈0) | ≈0 → 查房租是否真断(看 episode reward 分解中 hinge/hold 项是否随 gate 归零) |
| iter 500 | matched eval stage5 entry | ≥8/16 | <4 → M11 未生效或有残留房租,审计 §1.2 收入账逐项 |
| iter 1000 | goal_reached | >0/16 | =0 且 stage5 entry 高 → 陷阱 2 未解,见 3.2 |
| iter 1000 | stage5 前向速度 p50 | ≥0.15 m/s(v13_A 是 0.06–0.08) | 低 → 跑 v13_1_noM13 对照;考虑 release 阈值 1.2→1.35(要求更大开门角再交棒) |
| 全程(红线) | 运动期双侧接触 / coasting / hinge_vel p95 / over-force | 不劣于 v13_A(99.9% / <10% / <0.4 / <2%) | 劣化 → M11 的 mask 泄漏进 stage3,查 hold_income_mask |
| 全程(观察) | j8 开限位、stage3 handle 压满限位 | ≤ v13_A 水平(14%/27%) | 恶化再议,不阻塞 |

### 3.2 结果→下一步决策树

| 观察 | 结论 | 下一步 |
|---|---|---|
| goal ≥12/16 | v13.1 完成 | v14 方向:seed 鲁棒性(≥2 seed 重训验证 basin)、门参数 randomization(先 left/right,见 memory door-asset-randomization-baseline)、student distillation 接入 |
| goal 1–11/16 | 通了但不稳 | 续训 1000 iter + 分析失败 env 的分岔点(松手过早门拍回?过线后绕门路径?) |
| stage5 entry 普及但 goal=0,速度仍 <0.1 | 穿行物理仍卡 | (a) release 阈值 →1.35 交棒前把门推更开;(b) 显式 stage5 shaping:`(root_x 进度) × (无框接触)` 乘积项;(c) 检查 panel 与机器人碰撞摩擦是否过高 |
| stage5 entry 没普及、release_gate 正常置位 | 有残留站桩收入 | 用 trace 的 reward 分解逐项审计末 100 步收入,找漏网房租(候选:stage reward 的 stage4 项 1.0/step——若确认是主力,把 `_stage_4_reward_condition` 从 hinge>0.25 收紧为 release_gate & 前向速度>0) |
| 松手后门拍回致 hinge<1.047、stage4→5 判定失败 | 交棒时机问题 | release 阈值提高,或 stage4→5 的 hinge 条件改为"曾达 1.2"(per-env 高水位),避免瞬时回摆卡判定 |
| 抓握质量红线劣化 | M11 mask 泄漏 | 停训修 mask;stage3 语义必须与 v13_A 完全一致 |

---

## 4. 实施 checklist

1. [ ] M11:release gate buffer + 置位/清零 + `hold_income_mask` helper + 六处 reward 函数接线(hold×5、open-command penalty)+ grasp_mild + push_door_hinge pos 项;config key `a2_stage4_release_hinge_threshold: 1.2`。
2. [ ] M12:`_reward_target_root_distance` 的 SWING 系数按 gate 切换。
3. [ ] M13:`penalty_door_frame_contact` 分段系数;config key `a2_stage45_door_frame_contact_scale: 0.2`。
4. [ ] M14:遥测 4 项 + eval N/A 修正。
5. [ ] smoke:64 env × 50 iter,确认 release_gate 遥测在动、gate 置位后 reward 分解中 hinge-pos/hold 项归零、stage3 各项与 v13_A smoke 一致。
6. [ ] 启动 v13_1_main(附录 B yaml);每 250 iter 对照 §3.1;终点 matched eval + render,co-locate `logs_eval/base_v13_1/`。
7. [ ] **memory 记录**(`memory/a2-piper/push-open-door-optimization/`,时间戳 HKT):
   - v13 终局:A 16/16 stage4(hinge p50 1.28、双侧 99.95%、零甩门)= 核心难题已解;B/pre/C 的因果三角(gate 实现正确;Kp80 抓握不可训练;force margin = trainability);
   - 陷阱 1/2 的定量事实(root_x_max -0.001~-0.05 差 1-5cm;站桩收入 ≈12/step;stage5 0.06-0.08 m/s + 123-197N 撞框);
   - "加法奖励结构在每个 stage 边界都会长出新的站桩房租"——v11 冻结、v13_A 门挡是同一形态,后续每加一个 stage 收益都要做租金审计;
   - v13.1 的 M11-M15 配置关系与判读结果;
   - 不写 origin-reference。

---

## 附录 A|v13_1_main 完整 ablation 配置(可直接抄)

`gr00t/rl/config/ablation/wbmanip/base_v13_1_main.yaml`;启动命令模板同 v13(accelerate launch,+exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v13_1_main)。

```yaml
# @package _global_

# v13.1 main: wide-open handoff. Release gate at hinge>=1.2 stops stage4 hold rents
# (hold bundle, grasp_mild, open-command penalty, hinge pos-term), restores full
# target_root_distance in stage4, softens door-frame contact penalty in stage4/5.
# Warm-start from v13_A step3000. Evidence & design:
# scriptsFORhuman/v13_1/a2_piper_base_v13_1_optimization_plan_20260717.md

checkpoint: logs_rl/a2_piper_full_stage_a2_base/base_v13_A_main-20260716_225345/model_step_003000.pt
checkpoint_load_mode: policy_only
auto_load_latest: false
seed: 0
num_envs: 4096          # 按实际资源分配(v13 实跑为 4 processes × 1024 env/rank)
headless: true

algo:
  trl:
    num_total_batches: 2000

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
    a2_stage4_release_hinge_threshold: 1.2       # M11(新)
    a2_stage45_door_frame_contact_scale: 0.2     # M13(新)

rewards:
  reward_penalty_curriculum: false
  reward_initial_penalty_scale: 1.0
  reward_min_penalty_scale: 1.0
  reward_max_penalty_scale: 1.0
  reward_penalty_degree: 0.0
  reward_scales:                 # 与 v13_A 完全一致;M11/M12 的切换在 reward 函数内部按 gate 实现
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

v13_1_noM13(可选):同上,仅 `a2_stage45_door_frame_contact_scale: 1.0`、`num_total_batches: 1000`。

## 附录 B|本轮诊断关键数字(§1 全部来源)

- A3000 卡 stage4 的 12 env:hinge_end 1.064–1.617(全>1.047)、handle_end ≤0.124、root_x_max −0.001~−0.054、末帧 both_contact 全 True、TCP 0.020–0.050、末 100 步 base 指令 p50 −0.078~+0.028、prim p50 ≈−2.1;
- A3000 stage5 的 4 env(11/13/14/15):stage5 步数 265–393、root_x 终点 0.45–0.70、握持率 1–4%、前向指令 p50 0.088–0.150、实际 vel p50 0.043–0.085、doorframe 力 max 41–197N、stage5 内 hinge 上升(身体顶门);
- A 训练:iter2000 突破(s4act 0→0.118),2250–3000 stage 3.92→4.00 趋平;终态 s4act 0.679、s34both 0.764、hinge 均值 0.650;
- v13_pre:C3000+gate patch → **16/16 stage3**(M1 实现正确);
- v13_B:开训 250 iter 内 advance 率 ≈1e-4(C3000 原策略应为 ≈2e-3),终态 eval 16/16 stage2、streak max 3–4 → Kp80 抓握不可训练;
- 站桩收入账(hinge=1.28):hinge 位置项 4.9 + hold 2.5 + grasp_mild 1.0 + dont_push_handle 3.0 + stage 1.0 ≈ 12/step;
- stage4→5 条件(door_open_a2_base.py:11838-11845):root_x>0 & hinge>1.0472 & handle<0.2;stage5 complete:root_x>1.5。
