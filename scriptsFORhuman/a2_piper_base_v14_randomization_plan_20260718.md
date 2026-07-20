# A2+Piper base_v14 优化方案(round 1 door randomization:回弹动力学 + handle 高度 + 自学站位)

日期:2026-07-18(HKT)
作者:base_v13.1 结果诊断 session(Claude)
交接对象:实施 session(负责 code/config 修改、可达性图、训练启动、memory 记录)
前置文档:`a2_piper_base_v13_optimization_plan_20260716.md`(M1–M10)、`a2_piper_base_v13_1_optimization_plan_20260717.md`(M11–M15);本文延续编号 **M16–M21**。
用户已批准(2026-07-18):round 1 范围 + handle 高度 0.80–1.10m + "staging 点改带 + 可达性图先行"的站位设计。

---

## 0. 一页结论

v13.1 已 16/16 完成 goal,任务闭环首次打通。v14 的目标是**鲁棒化**,并顺带修复 v13.1 的质量回退:

- **v13.1 终点行为勘正**(§1.1,与交付 report 的解读不同):门最终全部开到 **2.618 rad(150°,铰链上限)**;"stage4 max hinge 1.05"只是 stage 切换点。真实策略是**"扶着门穿过"**:开到 ~45°(hinge 0.72–0.88)时握着把手跨线(16/16 过线帧 both_contact=True),边走边推,stage5 内推满。这比 v13.1 设计的"开大→松手→冲刺"更接近用户要的鲁棒形态。
- **v14 round 1 randomization**:hinge 常闭力 2.5–4.5 → **2.5–7.0 N·m**、handle 回位力 1–2 → **1–3 N·m**、handle 高度 0.85–0.95 → **0.80–1.10m**。回弹力变成训练分布后,"45° 窄缝挤门"的薄余量策略会被物理压力自然逼成"开更大、握更稳"——**用机制修行为,不再做 reward 雕花**(与 latch 的教训同构)。
- **站位自适应(用户核心担忧)**:全链路只有 stage0 硬编码了站位("handle 前 0.7m 半径 0.1m 的球");stage1→2 本来就是能力判据(TCP 到 pregrasp)。**把球改成环带 [0.45, 0.85]×|Δy|<0.15,带内 reward 无偏好,精细站位交给 stage1/2 既有梯度去学**;训练前先跑**静态可达性图**定带参并确认 1.10m 在臂展包络内。
- 顺带修 M11 死区(release 阈值 1.2→1.05)、补 v13.1 缺失的中点 eval、新增按 door 参数分桶的鲁棒性报告。
- 明确一个取舍:**round 1 不把弹簧参数加进 privileged obs**(会改 obs 维度、废掉 warm-start);依赖 LSTM 在 episode 内从交互中辨识门的动力学,不行再做输入层扩展手术(§M20)。

---

## 1. 证据档案

### 1.1 v13.1 终点行为勘正(逐 env trace 复核)

canonical eval:`logs_eval/base_v13_1/base_v13_1_main_ckpt3000_matched_scalar_trace_16env_seed0_20260718_r3`

- goal 16/16,max_stage 全 5;**全 16 env 的门在 episode 内开到 2.605–2.618 rad(铰链上限)**;
- stage4 内 hinge 最大 1.048–1.059 = stage4→5 在 1.047 触发的切换点,不是"只肯开 60°";
- **过线瞬间(root_x 首次 >0):hinge 仅 0.72–0.88 rad,16/16 both_contact=True,handle 已回位**——"扶着门穿"而非"松手冲刺";
- stage5 前向速度 p50 0.495 m/s;
- **M11 release gate 归因勘正**:终点 0% 是**结构性够不着**(stage4 在 1.047 结束,gate 阈值 1.2 在死区)。训练日志显示 gate 发放率开局冲到 ~20%(对着 warm-start 继承的 v13_A 扶门站桩行为切租)后衰减——**脚手架完成使命后自拆**。交付 report 的"终点成功不能归因 M11/M12"对终点策略成立,对训练轨迹大概率不成立(严格归因需消融,不值得花)。
- **设计规则(记 memory)**:stage 内 gate 的阈值必须低于该 stage 的退出阈值,否则是死区。

### 1.2 质量回退(v14 要顺带修的)

| 指标 | v13_A | v13.1 | 说明 |
|---|---|---|---|
| stage3/4 双侧接触 | 99.95% | **90.43%** | 主要丢在窄缝挤门段与过线后甩门段 |
| hinge_vel p95 | 0.212 | **0.513 rad/s** | stage5 内身体把门抡到 150° |
| coasting | 0.045% | 9.57%(训练日志 20.34%) | 门自由滑行帧 |
| j8 开限位 | 14.15% | **20.52%** | 观察项,继续盯 |
| stage3 handle 压满限位 | 27.4% | 17.91% | 改善 |
| over-force | 0.18% | 0% | 达标 |

这些薄余量(45° 就过线、10% 单侧/滑行)在弱弹簧下是"高效",在强弹簧下会被压爆——**正是 M16 randomization 的训练梯度来源**,预期随分布加宽自然收敛回稳健形态。

### 1.3 stage0/1 站位机制的代码事实(用户担忧的定位)

- `_stage_0_to_1_advance_condition`(door_open_a2_base.py:12784):root 水平位置进入 `grasp_target - (a2_stage0_staging_x_offset=0.7, 0, ·)` 半径 0.1m 的圆(z 被置零忽略)+ arm default(偏差<0.1 rad)。**全链路唯一硬编码站位处**。
- `_reward_walk_to_door`(:3554):朝同一个点做速度跟踪(target_vel = 0.3×方向,tracking std 0.15)。
- `_get_a2_stage1_pregrasp_ready_mask`(:5211):TCP 距 pregrasp 点(handle 前 10cm,`A2_PREGRASP_OFFSET=(-0.10,0,0)`,随 handle 自动走)<0.1 + 对齐≥0.8 + base 静止 + gripper 在行程内——**能力判据,与站位无关**;pregrasp/grasp 全部 reward 走 frame transformer,天然高度自适应。
- `penalty_a2_stage1_stage2_base_forward_creep`(-1.5,deadband 0.05):stage1/2 禁止前爬(防 G1 式贴门)。
- 死锁机理:固定 0.7m 标距 + 事后不许挪 → handle 1.10m 时若 pregrasp 超包络,stage1→2 永不触发且无法自救。
- homie 5 维指令含 body height(clip 0.3–0.75m)——"站高"自由度已存在;obs 的 `gripper_handle_transform`/`relative_to_door` 在 stage0 即可见 handle 高度,**无需加 obs**。

### 1.4 randomization 管线事实

- 训练场景经 `gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py` 构造(isaacsim.py:1381-1389 加载);门参数采样在 `gr00t/rl/isaac_utils/playground/env_rand/door.py`,**范围硬编码在 `np.random.uniform(...)`**(hinge maxForce :481-485、handle maxForce :508-512、handle 高度 tblr 采样在 `_build_door` 头部),`DoorSpawnerCfg` 现有 `rand_*` 字段只支持定值覆盖。
- 门在 scene build 时一次采样(训练 4096 门/run;matched eval 16 门@seed0)→ 分布是跨 env 的,不随 episode 变;
- 力学账:7 N·m ÷ 把手臂长(最短 0.65m)≈ **10.8N** 把手切向力 = 指端 effort 上限,身体助推可覆盖——round 1 上限定 7.0,不上 10;handle 3 N·m ÷ 柄长 0.11–0.14m ≈ 21–27N 下压力,arm 经 body 压柄可达(repair 实测 9–40N),可行。

---

## 2. v14 设计(M16–M21)

### M16|门动力学与几何 randomization【必做】

**范围**:

| 参数 | 现值 | v14 round 1 |
|---|---|---|
| hinge drive maxForce(常闭回弹力) | uniform(2.5, 4.5) N·m | **uniform(2.5, 7.0)** |
| handle drive maxForce(把手回位力) | uniform(1.0, 2.0) N·m | **uniform(1.0, 3.0)** |
| handle 高度(door_handle_tblr 上/下) | (0.95, 0.85) m | **(1.10, 0.80)**(以 M18 可达性图放行为准) |
| hinge drive stiffness | uniform(1, 10)(已随机) | 保持 |
| door weight / width / height | 80–120kg / 0.8–1.1 / 1.9–2.2(已随机) | 保持 |
| door_open_lr / door_open_io | right / out | **保持**(lr=round 2;io=新任务,round 3+,见 §3.2) |

**实现**(fail-fast,禁止静默默认):

1. `DoorSpawnerCfg` 新增 range 字段:`hinge_drive_max_force_range: tuple = (2.5, 4.5)`、`handle_drive_max_force_range: tuple = (1.0, 2.0)`;`door.py` 的两处 `np.random.uniform` 改读 range 字段;既有 `rand_hinge_drive_max_force` 等定值覆盖优先级高于 range(供确定性测试)。
2. `scenario_cfg/isaacsim.py` 的 `door_spawner_cfg` 显式传入新 range 与新 tblr。
3. **把 hinge/handle maxForce 写进 door customData metadata**(同 doorWeight 模式),`_init_door_metadata` 读入 per-env buffer——供 M20 分桶报告与诊断;本 round 不进 obs(见 M20)。

### M17|stage0 staging 从"球"改"环带",站位交还 policy【必做,用户核心担忧】

**config(替换旧 key,旧 key `a2_stage0_staging_x_offset` 删除,残留引用应自然 raise)**:

```yaml
a2_stage0_staging_x_min: 0.45     # 初值;以 M18 可达性图回填为准
a2_stage0_staging_x_max: 0.85
a2_stage0_staging_y_tol: 0.15
```

**代码**:

1. `_stage_0_to_1_advance_condition`(:12784):`(grasp_x − root_x) ∈ [x_min, x_max]` 且 `|root_y − grasp_y| < y_tol` 且 arm default(不变);z 继续忽略。
2. `_reward_walk_to_door`(:3554):速度跟踪目标改为**带内最近点**——
   ```python
   dx = grasp_x - root_x
   target_x = grasp_x - dx.clamp(x_min, x_max)          # 带内 → target_x = root_x
   target_y = grasp_y - (grasp_y - root_y).clamp(-y_tol, y_tol)
   # target 与 root 重合(带内)时 target_vel = 0,其余同现有 tracking 公式
   ```
   **带内 reward 无偏好**:站哪由 stage1 `pregrasp_target_distance`(6.0)等既有梯度决定——高 handle 只有站近+站高才够得着 pregrasp,站位映射由此涌现。
3. 同步更新 :4729 处 route diagnostics 对旧 key 的引用。
4. `base_forward_creep` 惩罚**保持不动**(防贴门护栏;带的 x_min 已提供合法近站通道)。fallback 旋钮(不进首发):deadband 0.05→0.10。
5. **不动 homie height clip(0.3–0.75)**——那是 A2_Base 底层策略的训练范围。
6. 兜底方案(仅当学习式站位失败,判据见 §3.1):确定性公式 `x_offset(h)=clip(√(R_eff²−(h−z_shoulder)²), x_min, x_max)`,R_eff/z_shoulder 从 M18 数据拟合。

### M18|静态可达性图(训练前必做,零训练成本)【必做】

用现成 static preview/clamp 工具(memory `static-visual-alignment`;`a2_hold_*` offset-placement/static-clamp machinery)扫描:

```
handle 高度 {0.80, 0.85, ..., 1.10} × 标距 {0.40, 0.45, ..., 0.85} × body height {0.55, 0.65, 0.75}
每格:驱动 TCP 到 pregrasp 点(handle 前 10cm)后判定:
  可行 = TCP 误差 < 0.03m 且 无自碰 且 关节限位余量 > 0.1 rad(重点盯 arm_j6,v8 的限制关节)
```

**产出与决策规则**:
- CSV + 汇总表存 `scriptsFORhuman/`(或 eval 产物目录),记 memory;
- `[x_min, x_max]` = 在**全部目标高度**上(允许选最优 body height)可行的最大连续标距带,回填 M17 config;
- **1.10m 放行判定**:若 1.10 在任何(标距×body height)组合下不可行 → round 1 高度封顶到最高可行值,并在 memory 里记录"臂展天花板"(这是硬件事实,不是训练失败);
- 记录高 handle 是否必须 body height ≥0.7(决定 §3.1 是否盯 height 指令使用率)。

### M19|M11 死区修复【必做,一行】

```yaml
a2_stage4_release_hinge_threshold: 1.05   # 1.2 → 1.05(≈ stage4→5 阈值)
```
语义变为"门一达标房租即停"。强弹簧下 v13_A 式扶门站桩可能复发,一个活着的 gate 是安全网(§1.1 设计规则)。

### M20|遥测、分桶报告与 obs 取舍【必做】

1. **分桶鲁棒性报告**(eval 汇总脚本):按 per-env metadata 分桶输出 goal/stage 达成——hinge maxForce 三分位、handle 高度 {0.80-0.90, 0.90-1.00, 1.00-1.10}、handle maxForce 两桶。16 env 每桶 ~5 个,粗但够方向判断;**补充协议**:canonical eval(seed0/16env)不变,另跑 seed1、seed2 各 16 env 作 supplementary,三次合并 48 门再出分桶表(标注 supplementary,不与历史 canonical 混算)。
2. 新指标:`crossing_while_holding`(过线帧 both_contact,现 16/16)、hinge-at-crossing 分布、body height 指令分布(stage0/1)、staging 标距分布(过 stage0→1 时的 dx,验证站位-高度映射是否涌现)。
3. 保留 M9/M14 全部遥测与 N/A 规则;**本轮必须跑 iter500/1000/2000 中点 matched eval**(v13.1 漏掉了)。
4. **obs 取舍(已决策)**:round 1 **不把**弹簧参数加进 `privileged_door_info`——它同时在 actor/critic obs 里,加维度 = v13_1 warm-start 权重作废。依赖 LSTM 在 episode 内从接触反馈辨识门动力学(门 per-env 恒定,首次接触后即可辨识)。若 §3.2 判读显示强弹簧桶系统性失败且 hinge-at-crossing 不随弹簧自适应 → round 1.5 做输入层扩展手术(新 obs 槽零初始化拼接,保留旧权重),届时再议。
5. 顺带:复核 formal training launcher 的 natural-exit(v13.1 遗留 ops 项)。

### M21|run 计划

| Run | 内容 | 预算 |
|---|---|---|
| **v14_pre(M18)** | 可达性图,eval-only | ~0.5h,无训练 |
| **v14_main** | M16+M17+M19+M20,checkpoint=v13_1_main step3000 policy_only | **3000 iter**(分布位移大于 v13.1,给足),save250,资源同 v13.1(4×1024) |
| v14_narrow(fallback,仅当 main 训崩) | 同 main 但 hinge maxForce 2.5–5.5、高度 0.80–1.00 | 课程化收窄;main 顺利则不跑 |

checkpoint:`logs_rl/a2_piper_full_stage_a2_base/base_v13_1_main-20260717_202500/model_step_003000.pt`(SHA256 e836427e…167945)。

---

## 3. 判读标准与决策树

### 3.1 分时点判读(v14_main)

| 时点 | 指标 | 期望 | 未达 → 动作 |
|---|---|---|---|
| 训练前 | M18 可达性图 | [x_min,x_max] 非空覆盖全高度;1.10 放行或明确封顶 | 空带 → 站位设计复议(body height 上限?) |
| iter 250 | stage1 entry / pregrasp_ready frac(按高度桶) | 各桶均不为 0,高桶允许偏低 | 高桶=0 → 对照可达性图查 policy 实际标距/身高(M20 新指标),考虑 M17 兜底公式 |
| iter 500 eval | goal(canonical) | ≥8/16 | <4 → 分布过宽,启 v14_narrow |
| iter 500 eval | 0.80–0.95m + 弱弹簧桶 | **不劣于 v13.1**(红线:已有能力不得学坏) | 劣化 → 查 M17 是否扰动了低桶站位 |
| iter 1000/2000 eval | goal 趋势 + 强弹簧桶 | 单调改善;强桶 ≥ 半数 | 强桶恒 0 → 看 hinge-at-crossing 是否随弹簧增大(自适应缺失 → M20.4 obs 手术预案) |
| 终点 | goal(canonical) | ≥12/16;supplementary 48 门 ≥70% | — |
| 终点 | crossing_while_holding | ≥14/16 | — |
| 终点 | 双侧接触(stage3/4) | ≥90% 且强弹簧桶不塌 | — |
| 终点 | 甩门组(hinge_vel p95 / coasting) | **≤ v13.1(0.51/9.6%),期望显著改善**(强弹簧物理抑制甩门) | 恶化 → 反常,查 trace |
| 全程 | j8 开限位 | ≤25% 观察 | >30% 或伴双侧下滑 → 指端力量议题重开(effort/Kd) |
| 终点 render | 2 env×3 cam(挑一强弹簧 env) | 目视:强回弹下扶门穿行不被拍回 | — |

### 3.2 结果→下一步决策树

| 观察 | 结论 | 下一步 |
|---|---|---|
| 终点达标 | round 1 完成 | **v15 = door_open_lr 左右镜像**(memory 已预分析 plumbing;先 GUI/smoke 验左侧 workspace);此后 in/out 拉门立项(新任务:出生侧/staging 符号/穿行方向/doorOpenIO 进 obs,见 memory door-asset-randomization-baseline);student distillation 可与 v15 并行评估入场 |
| 高 handle 桶 pregrasp 失败,可达性图说可行 | 站位学习未涌现 | 看 staging 标距分布:若 policy 不站近 → 启 M17 兜底公式;若站近了仍够不着 → 图与实机差异,复核图的判定余量 |
| 强弹簧桶 crossing 后被门拍回 | 自适应"开更大再过"未涌现 | 先查 hinge-at-crossing 按桶分布;无自适应迹象 → M20.4 obs 手术(spring 进 privileged,输入层扩展保权重) |
| handle 3 N·m 桶 stage3 entry 掉 | 解锁压不动/压不住 | 查 stage3 handle 角分布与 j8 反驱;必要时 handle maxForce 上限回 2.5 过渡 |
| 训练整体崩(goal 长期 0) | 分布位移过大 | v14_narrow 课程化:先窄带收敛再 resume 放宽 |
| 弱桶劣化(红线) | 灾难性遗忘 | 降 LR 或改 full-state resume 重跑;检查 staged reset 快照是否被新分布污染 |

---

## 4. 实施 checklist

1. [ ] M18 可达性图先行;回填 M17 的 [x_min, x_max] 与高度放行结论。**不出图不训练。**
2. [ ] M16:DoorSpawnerCfg range 字段 + door.py 采样改造 + scenario_cfg 传参 + metadata 写读(hinge/handle maxForce)。
3. [ ] M17:staging 带条件 + walk_to_door 最近点跟踪 + 旧 key 移除(含 :4729 diagnostics)+ 新 config keys。
4. [ ] M19:release 阈值 1.05。
5. [ ] M20:分桶报告脚本 + 新遥测 4 项 + supplementary eval(seed1/2)流程;natural-exit 复核。
6. [ ] smoke:64 env × 50 iter,确认新门参数分布生效(metadata 直方图)、stage0→1 在各高度桶均有通过、walk_to_door 无 NaN。
7. [ ] 启动 v14_main(附录 A yaml);iter 500/1000/2000 中点 matched eval **必跑**;终点 canonical + supplementary + render(含强弹簧 env)。
8. [ ] **memory 记录**(`memory/a2-piper/push-open-door-optimization/` 等,HKT 时间戳):
   - v13.1 终局勘正:**扶着门穿过**(过线时 16/16 仍握持、门最终 150°)、M11 脚手架自拆、"gate 阈值必须低于 stage 退出阈值"设计规则;
   - v13.1 质量回退数字与 v14 用物理分布修行为的路线("机制约束优于 reward 雕花"第二例,первый是 latch);
   - stage0 站位设计变更:**可行域环带替代人为 target pos**,站位交还 policy + 可达性图定参模式;
   - obs 维度 vs warm-start 的取舍决策(round 1 不加 spring obs,靠 LSTM 辨识);
   - M16 各 range、M18 图结论、v14 各判读结果;
   - 不写 origin-reference。

---

## 附录 A|`base_v14_main.yaml`(可直接抄)

> 注意:M16 的门参数范围在 `scenario_cfg/isaacsim.py` + `door.py`(代码侧),不在本 yaml;M17/M19 的新 env key 在此。启动命令模板同 v13(+ablation=wbmanip/base_v14_main)。

```yaml
# @package _global_

# v14 round-1 door randomization: rebound dynamics (hinge 2.5-7.0 N*m, handle 1-3 N*m,
# code-side in scenario_cfg/door.py) + handle height 0.80-1.10m + stage0 staging band
# (learned stance) + M11 dead-zone fix. Warm-start from v13_1_main step3000.
# Evidence & design: scriptsFORhuman/a2_piper_base_v14_randomization_plan_20260718.md

checkpoint: logs_rl/a2_piper_full_stage_a2_base/base_v13_1_main-20260717_202500/model_step_003000.pt
checkpoint_load_mode: policy_only
auto_load_latest: false
seed: 0
num_envs: 4096          # 按实际资源(v13.1 实跑 4 processes × 1024 env/rank)
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
    a2_stage4_release_hinge_threshold: 1.05      # M19(1.2 → 1.05,修死区)
    a2_stage45_door_frame_contact_scale: 0.2
    a2_stage0_staging_x_min: 0.45                # M17(初值;以 M18 可达性图回填)
    a2_stage0_staging_x_max: 0.85                # M17
    a2_stage0_staging_y_tol: 0.15                # M17
    # 旧 key a2_stage0_staging_x_offset 已删除,不得再出现

rewards:
  reward_penalty_curriculum: false
  reward_initial_penalty_scale: 1.0
  reward_min_penalty_scale: 1.0
  reward_max_penalty_scale: 1.0
  reward_penalty_degree: 0.0
  reward_scales:                 # 与 v13.1 完全一致,零改动
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

`scenario_cfg/isaacsim.py` 侧同步 diff(M16):

```python
door_spawner_cfg = DoorSpawnerCfg(
    ...,
    door_handle_tblr=(1.10, 0.80, 0.08, 0.15),      # 高度 0.80–1.10(以 M18 放行为准)
    hinge_drive_max_force_range=(2.5, 7.0),          # 新字段
    handle_drive_max_force_range=(1.0, 3.0),         # 新字段
    ...
)
```

## 附录 B|本轮诊断关键数字(§1 全部来源)

- v13.1 endpoint(canonical r3):goal 16/16;per-env hinge 全程最大 2.605–2.618;stage4 内最大 1.048–1.059;过线帧 hinge 0.725–0.882、both_contact 16/16 True、handle ≤0.139;stage5 前向 p50 0.495 m/s;
- release gate 训练轨迹:开局 0→~0.20,随后衰减(0.15→0.11→~0.08-0.11@iter~700),endpoint eval 0%——脚手架自拆;
- 质量对照表见 §1.2;doorframe force max 152N(挤门段);
- 站位机制代码锚点:advance :12784、walk_to_door :3554、pregrasp_ready :5211、staging key :2588/2924/4729、creep penalty(-1.5, deadband 0.05);homie height clip 0.3–0.75;
- randomization 管线锚点:scenario 加载 isaacsim.py:1381-1389;door.py hinge maxForce :481-485、handle maxForce :508-512、tblr 采样于 `_build_door` 头部;门 scene-build 一次采样(训练 4096 门、eval 16 门@seed0);
- 力学账:7 N·m/0.65m ≈ 10.8N(指端 effort 上限,身体助推覆盖);handle 3 N·m/0.11–0.14m ≈ 21–27N 下压(可达,repair 实测 9–40N)。
