# A2+Piper base_v13 优化方案(stable grasp → push door open)

日期:2026-07-16(HKT)
作者:base_v12 结果探索 session(Claude)
交接对象:实施 session(负责 code/config 修改、训练启动、memory 记录)
读者前提:已读过 `scriptsFORhuman/a2_piper_push_open_door_optimization_base_v0_to_v9_20260713.md` 或熟悉 v8–v12 历史。

---

## 0. 一页结论

v12 的探索把 v8→v12 的僵局("能动门的不会抓,会抓的不动门")定位到**三个可修的根因**,并给出一个**先零成本验证、再单主线训练**的 v13 方案:

- **根因 A(gate 时间尺度错误)**:stage2→3 完成判据要求 *5 个连续 physics step*(25ms@200Hz)的双侧≥1N 反向挤压;policy 以 50Hz 行动,每个 5 帧窗口必然横跨一次 action 边界。v12_C step3000 matched eval 中,单帧条件满足率 92–97%,**5 帧 AND 恰好 0 次**(6274 采样帧)。整个 hold 路线在 stage2 被结构性卡死。
- **根因 B(夹持力-负载不匹配)**:j7/j8 prismatic、Kp=80 N/m → 最大静态夹持力 2.8N/爪(160 → 5.6N;effort limit 10N 用不到)。门板 80–120kg + hinge 常闭弹簧 2.5–4.5 N·m → 把手处需 ~5–10N 持续切向力。摩擦传力不够 → "边握边动"物理上近似不可行,v9 反驱 j8、v11 冻结、repair-A 压把手顶开 j8 都是同一约束的表现。
- **根因 C(unlatch 奖励形态错误,T1 诊断新增 + 勘误)**:训练门**带 latch**(§1.9 勘误,scenario config `build_latch=True`)——压 handle 是开门的机械必要步骤,方向上 `push_door_handle` 没错;错的是**形态**:handle_pos 项在 45° 限位处饱和白拿满分、且不要求任何抓握。A3000 进入 stage3 的 env 全部在 10 步内变成"j7 脱接触、arm 经 body8 以 9–40N 把把手压死在 0.785 rad 限位"的单侧杠杆压(v9/repair-A 的 j8 反驱同形态)——解锁了却不推门、还顺手摧毁了双侧抓握。
- **v13 主线**:gate/stability 改 control-step 去抖(M1) + 指端 Kp 提到 effort 饱和(M2) + stage3 base unlock(M3) + 从 v12_C step3000 warm-start(M4) + handle 奖励改为 grasp-gated unlatch 项、新增"边握边动"乘积 reward、带抓握条件的 stage3→4(M5/M6)。**用户已确认最终任务就是带锁舌门的"先压 handle 解锁→再推门、全程稳握不甩门"**——v13 的任务语义与最终目标一致,无需改门。
- **训练前先做 M10**:只改 eval 侧 gate 定义,对 C3000 重跑 matched eval。counterfactual 已从 trace 验证:**K=5 去抖下 16/16 env 通过,中位首过步 20**(附录 T4)。这一步 0 训练成本,直接证实根因 A。

---

## 1. 证据档案(全部可复查)

### 1.1 v12 step3000/2750 matched eval 读数

| Cell | 配置 | 结果 | 定性 |
|---|---|---|---|
| A(80/3,H=0.5) | scratch | goal 0/16,stage3 **2/16**(trace env12/14,episode 553=452+101,耗满 stage3 100 步 overtime,hinge 未过 0.25;metrics_eval 数组不按 env-id 排序) | 半抓握 basin |
| B(160/6,H=0.5) | scratch | goal 0/16,16/16 stage2 | open-command 回避 basin(close 0%,j7 100% 顶开限位,TCP 0.30m) |
| C(80/3,H=1.0) | scratch | goal 0/16,**16/16 stage2** | 史上最佳 stage2 抓握:close 77%,双侧 57%(训练);eval 单帧双侧 92% |
| D(160/6,H=1.0) | scratch | goal 0/16,16/16 stage2 | 同 B |

- eval 目录:`logs_eval/base_v12/base_v12_{A,C}_ckpt3000_matched_scalar_trace_16env_seed0_20260716/`、`{B,D}_ckpt2750_...`
- C 的悖论:episode reward ~130(A ~92)——**抓得越好越不推进**,因为 gate 不可过时,在 stage2 刷 hold reward 是收益最优。

### 1.2 根因 A 的直接证据(v12_C step3000,env 自算指标)

`eval_to_log_metrics.json`,382 个 stage2 多数步的均值:

```
both_contact 92.0% | opposite_squeeze 93.1% | sufficient_squeeze 93.1% | squeeze_window 92.0%
close_gate 96.7%   | stable_close 97.0%     | close_progress 95.9%
a2_stage2_contact_stability = 0.0000(max 亦为 0.0000)
a2_stage2_grasp_complete    = 0.0000 → stage3 entry 0/16
```

trace 逐帧重建(control-step 粒度,16 env):
- 每 env 满足"连续 5 control-step 挤压三条件 + close 三条件"的帧数 **157–373**;单次连续双侧接触最长 **396 步**;
- 267 次 streak 断裂 **100% 归因于单爪接触力瞬时 <1N**,从不是挤压方向/力度;
- 弱侧爪 |squeeze_y| p50=1.46N、强侧 p50=2.66N——**已达 Kp80 理论上限(2.8N)的 50–95%,是执行器天花板,不是 policy 不想用力**。

### 1.3 根因 B 的物理账

- `gr00t/rl/config/robot/A2_Piper/a2_piper.yaml`:j7 行程 [0,0.035]、j8 [-0.035,0],effort limit **10N**,vel limit 1 m/s。静态夹持力 = Kp×|误差| ≤ Kp×0.035 → **2.8N(Kp80)/ 5.6N(Kp160)**。
- `gr00t/rl/isaac_utils/playground/env_rand/door.py:479-491`:hinge drive target=-10°、maxForce 2.5–4.5 N·m(封顶即常闭偏置);`:506-514`:handle drive maxForce 1–2 N·m 回位。门板质量 **80–120kg**(`DoorSpawnerCfg.door_weight`,door.py:50),绕铰链惯量 ~27 kg·m²;把手臂长 ~0.7m → 2s 内开 0.25 rad 需把手处 **~9–11N 持续切向力**。
- 把手 capsule 半径 0.011–0.015m(直径 22–30mm),50% 概率带端部 hook(door.py:409)。
- 交叉证据:repair-r1-A(handle=6,Kp160)policy 确实动了把手(0.5 rad),代价 **j8 被反作用力反驱、60.5% 时间顶开限位**——160/6 也扛不住操作负载。

### 1.4 sensor / 时序机制定位

- `gr00t/rl/simulator/isaacsim/isaacsim.py:2428-2440`:`simulate_at_each_physics_step()` 每个 physics step 调 `scene.update()` → ContactSensor `force_matrix_w_history` 以 **200Hz** 滚动。
- `door_open_a2_base.py:11947-11955`:handle contact sensor `history_length=5`(yaml `stage2_grasp_contact_history_length: 5`),未设 `update_period` → 默认每 physics step 更新。fps 200 / decimation 4(run config `simulator.sim`)→ **5 帧=25ms,必然跨一次 50Hz action 边界**。
- gate:`door_open_a2_base.py:4381-4438`(`_get_a2_stage2_grasp_completion_masks`,all-history AND;`close_gate_required=false`,所以 5 帧挤压就是全部条件);stability mask:stage2 `:4249-4281`、stage3/4 `:4289-4333`(同一 5 帧 both_contact AND)。
- stage 机:`_stage_2_to_3_advance_condition` `:11800`(A2 路线**无 door-open bypass**,v8/v9 时代的推门捷径已封死,`stage2_to3_bypass_blocked` 只是诊断);`_stage_3_to_4_advance_condition` `:11821`(仅 hinge>0.25,**不查抓握**)。

### 1.5 血统与 basin 事实(方法论)

- 翻存档 config 确认:**成功抓握唯一血统 v10_D→v11_C→repair 全程 Kp/Kd=160/6**、`a2_stage3_base_unlocked: true`、staged reset [0.5,0.1×5]、stage3/4 hold=2/1/2/4/-2。"v10_A-style" 的 80/3 从未成功过。
- 160/6 scratch 共尝试 4 次(v11_A、v11_B、v12_B、v12_D),**3 次落 open-command 回避 basin**;v10_D 是彩票。
- v12 的 H 因子(stage3/4 contact_stability 0.5→1.0)奖励的正是那个 5 物理帧 mask:stage2 发放率 ~0.01–0.06%、全步占比 ~1.7% → **该因子基本没生效**;A/C 巨大行为分化是同 seed 多卡非确定性下的 basin 漂移。
- **结论:basin 主导的问题里,单 seed 2×2 factorial 没有因果解释力。v13 改为"先验证假设、再单主线+定向消融"。**

### 1.6 staged reset 机制(v13 会用到)

`gr00t/rl/envs/base_task/staged_task_base.py`:
- 快照仅在 **advance 时刻** 采集(`_take_snapshot_of_buffered_states`,:516),**按 env 索引存取**(shape [num_stages, max_samples, num_envs, ...])——某 env 从未过 gate 就永远不能 staged-reset 进 stage3(:680 将无样本 stage 权重置 0)。
- door articulation 与 delta_actions 均已注册跟踪(`door_open_a2_base.py:2658-2665`)→ **合成快照播种在架构上可行**(直接写 `staged_reset_buf` 张量 + `staged_reset_num_samples`)。

### 1.7 stage3 真实行为:单侧压把手吸引子(T1,诊断新增)

A3000 eval 中 2 个 env 出现 stage3 帧(env12/14),形态完全一致:

- 进入 stage3 时是双侧接触(如 env12 t=412:f=[0.9, 2.0]);**10 步内 j7 侧完全脱接触**;
- 此后整段 stage3:f=[0.0, 9–40N]——arm 经 body8 把把手**压死在 0.785 rad(45°)硬限位**,j8 被反作用力钉在 -0.035 开限位(97–100% 帧),close command 却 100% 全程为 close;
- hinge 峰值仅 0.009–0.0115 rad;base 物理指令 ~0.01–0.02(stage3 locked);
- 收益账:handle_pos/0.785 在限位处=1.0 → `push_door_handle` ×6 = **6/step,躺着拿满**,超过 stage3 其他一切可得收益(hold ≤2.5,hinge ≈0.01)。

结论:**`push_door_handle=6` 的当前形态是 stage3 的最优吸引子,且与双侧抓握直接冲突**(repair-r1 A/B 对照给出同向证据:handle=6 → j8 60% 顶限位;handle=0 → 稳定双侧)。由于门带 latch(§1.9),压 handle 本身是必要的——需要修的是奖励形态(见 M5),不是把行为删掉。

### 1.8 v10_D 全程也从未动过门(T3,诊断新增)

v10_D 训练趋势(输出见附录 T3):iter~700 advance 率升至 0.2%/step 后,staged-reset 飞轮把 stage3 占比推到 **82%**,average_stage 2.97——但 **stage4 恒为 0、hinge 恒 ≈0.0007 rad 直到 step1000**。在 2/1/2/4 的强 hold bundle(≤9.1/step)下,深抓握+冻结就是收益最优。含义:(a) "深预紧可以过物理帧 gate"成立(0.2% 的低频足以喂飞轮);(b) **force-only 路线的终点是冻结**,v13_C 消融的历史先验已经存在;(c) v11_C matched eval 的"stability 99.16%"是 settle 后的帧级稳定,不是 gate 通过率。

### 1.9 勘误:训练门带 latch(本方案早期版本与探索报告曾误判为无 latch)

- 加载链:`gr00t/rl/simulator/isaacsim/isaacsim.py:1381-1389` 按 task_name 加载 **`gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py`**,其中 `DoorSpawnerCfg(build_latch=True, ...)` 且 articulation `enabled_self_collisions=True`——`door.py` 的 `build_latch=False` 只是 dataclass 默认值,训练场景实际开启。
- latch 机构(`door.py:517-565`):panel 顶部 handle 侧边缘有一个锥形 latch(半径 0.025m、长 0.05m,prismatic 行程 [0, 0.03m]),经 **PhysxMimicJointAPI 与 handle joint 联动**(gearing = 0.03m/45°):handle 转到 45° 时 latch 完全收回。handle 由 drive(target -15°、maxForce 1–2 N·m)回位——**用户在 eval 视频中看到的"下压后回弹"就是它**。
- 历史行为全部与"latch 生效"自洽:v8_A/v9/repair-A 的开门都伴随把手被压(单侧压);v12_B/D 从不碰把手 → hinge 1.5e-7;v12_D 的 39.6N door-frame 碰撞样本只把 hinge 顶到 0.0022 rad(2mm 级,latch 咬合内的空隙);A3000 env14 把 handle 压满 45°(解锁)但没人推 → hinge 仍只 0.01 rad。
- 含义:(a) "压 handle"是任务的机械必要步骤,`push_door_handle` 的存在合理,但其形态造成单侧压+限位 farming(§1.7);(b) 纯 body-push 不再是"免 handle"的捷径,但 v8/v9 证明"身体/手背单侧压把手+推"依然可行——M6 的防作弊条件仍然必要;(c) 用户最终任务(带锁舌门:压 handle 解锁→稳握推门)与当前场景一致,**无需改门资产**。
- 【实施验证项】latch 的有效解锁角未标定(几何上接近满行程才完全让位):建议在 smoke/GUI 里用 `a2_hold_*` static clamp 把 handle 固定在不同角度、推 panel,测出 hinge 可动的最小 handle 角,回填 M5 的 `UNLATCH_NORM`(暂用 0.6 rad)。

---

## 2. v13 设计

### 2.0 目标与成功定义

目标:**policy 用 gripper 抓住 handle,在保持双侧夹持的同时把门推开**(out-opening 门)。

新增核心指标(同时作为 acceptance):`hold_and_drive_frac` = 帧级 `(双侧接触去抖成立) & (hinge_vel > 0.05 rad/s)` 的占比。这是"边握边动"合取的直接度量——现有指标(stage、hinge、stability)都只度量单侧。

### 2.1 修改清单(M1–M10)

#### M1|gate 与 stability 改 control-step 去抖【必做,根因 A】

**语义**:把"5 个连续 physics 帧"改为"K 个连续 control step(每步取该步最后一个 physics 帧的 current-frame mask,即现有 `masks[...][:, 0]`)"。K=5 → 100ms。

**实现要点**(`gr00t/rl/envs/door/door_open_a2_base.py`):
1. `_init_a2_door_pregrasp_state`(:2603)新增两个 streak buffer:
   - `self._a2_stage2_squeeze_streak`(long, num_envs):current-frame `both_contact & sufficient_squeeze & opposite_squeeze` 连续计数;
   - `self._a2_stage3_stage4_both_contact_streak`(long, num_envs):current-frame `both_contact` 连续计数(stage3/4 用)。
2. **每 control step 恰好更新一次**:放在 `_pre_compute_observations_callback`(:2778,已被 door env override,且先于 staged_task_base 的 advance 判定执行)。注意:`_get_a2_stage2_grasp_completion_masks` 每步会被多处调用(:4479、:11803、trace),**streak 更新绝不能放进它**,否则重复计数。
3. reset/stage 切换清零:`just_resetted_buf` 为 True 或 `actual_time_in_stage_buf==0` 的 env streak 置 0(与 `set_to_stage`/staged reset 兼容)。
4. 判据替换(fail-fast,不留旧路径的 silent fallback):
   - stage2→3 completion(:4416-4420):`base_completion = (stage==GRASP) & (squeeze_streak >= K)`;close_command/close_progress 等 current-frame 条件保持不变(`close_gate_required` 仍为 false)。
   - `_get_a2_stage2_contact_stability_mask`(:4249)与 `_get_a2_stage3_stage4_contact_stability_mask`(:4289):改读对应 streak ≥ K(reward 语义随之变为"可学习的去抖稳定")。
5. 新 config key(required,加进 `gr00t/rl/config/env/door_open_a2_base.yaml`):
   ```yaml
   a2_grasp_streak_control_steps: 5      # K;去抖窗口(control steps,50Hz → 100ms)
   a2_grasp_gate_mode: control_streak    # control_streak | physics_history;未知值直接 raise
   ```
   `physics_history` 保留旧的 all-history AND 路径(v13_C 消融与历史复现需要),两条路径都是显式分支,不是 silent fallback;`stage2_grasp_contact_history_length: 5` 保留(sensor history 供诊断与旧模式)。
6. 训练日志新增:`a2_stage2_squeeze_streak_p50/p90`、`a2_stage2_streak_ge_K_frac`、stage3/4 同理;`eval_to_log` 同步(见 M9)。

**依据/预期**:trace 重建显示 C3000 在此定义下 16/16 env 于 stage2 第 15–26 步(中位 20)通过(附录 T4)。

#### M2|指端力量抬到 effort 饱和 + 力窗口重校【必做,根因 B】

- `robot.control.stiffness/damping`(ablation yaml 覆写 j7/j8 叶子,同 v12 写法):
  ```yaml
  stiffness: { arm_j7: 800.0, arm_j8: 800.0 }
  damping:   { arm_j7: 25.0,  arm_j8: 25.0 }
  ```
  账:effort 饱和误差 = 10/800 = 12.5mm ≈ 把手半径(11–15mm)→ 全闭指令下夹持力 ~8–10N/爪,μ·ΣN ≈ 16–20N ≥ 门的 9–11N 需求。Kd=25 ≈ 2√(Kp·m_jaw)(m_jaw~0.2kg)近临界阻尼。**若观测到指端颤振/接触爆炸,回退档 Kp=400/Kd=18(~5N,复现 v10_D 力量级但更稳)**。
  T2 标定(附录):**接触稳定只需 ~3N/爪**(repair-B@Kp160 弱爪 p50=3.21N → 整个 episode 一条 470+ 步零断裂 streak;v12_C@Kp80 的 1.5N 则必断);**拖动门需 ~10N**。即 Kp160 足够"握稳"(v13_B 若加 160 档可验证),Kp800 是为"握着动"。
- 力窗口(env.config 覆写):
  ```yaml
  a2_stage2_squeeze_force_min: 2.0     # 0.5 → 2.0(新力量级下"有效预紧"门槛)
  a2_stage2_squeeze_force_max: 20.0    # 保持
  a2_stage2_over_force_threshold: 40.0 # 保持;总 norm 会包含推门法向分量,勿收紧
  ```
- physx(ablation yaml,同 v12 位置):`num_velocity_iterations: 2`(仿真启动 log 自己在警告 velocity 噪声;v10–v12 均为 1)。若 wrapper 已 plumb `enable_external_forces_every_iteration` 则一并开 true;未 plumb 就不要为它加管道,记 TODO。
- 【验证项】handle/finger 的 physics material friction 当前用默认值;实施时用 `a2_hold_diagnostic_friction_override` 的读法确认实际 μ,若 <0.8 考虑在 asset/material 层面设 0.9–1.1(sim2real:真实 Piper 夹爪额定夹力几十 N,当前 2.8N 才是 gap)。

#### M3|stage3 base unlock【必做】

```yaml
a2_stage3_base_unlocked: true
```
armlocked 下手臂独自对抗 100kg 门既超力又超工作空间(v8 限制关节 arm_j6)。v10_D(唯一同时抓+动过的 run)就是 unlocked。防作弊由 M6 兜底。

#### M4|warm-start:v12_C step3000,policy_only【必做】

```yaml
checkpoint: logs_rl/a2_piper_full_stage_a2_base/base_v12_C_v10A_scratch_stability1-20260716_004404/model_step_003000.pt
checkpoint_load_mode: policy_only   # 【验证项】确认 loader 接受的字符串(v9 先例用过 policy_only)
```
理由:C3000 是有史以来最佳 stage2 抓握行为(训练 close 77%/双侧 57%,eval 单帧双侧 92%),离 gate 只差 M1 一个定义;warm-start 同时消掉 scratch 的 basin 彩票(160/6 scratch 4 次里 3 次翻车)。critic/optimizer/curriculum 重新初始化(policy_only 语义)。

注意:warm-start 权重来自 Kp80 工况,M2 改了执行器动力学,前 ~100 iter 会有适配期——正常,盯 `a2_stage2_over_force_frac` 与 j7/j8 velocity 即可。

#### M5|handle 奖励改形态 + 新增"边握边动"乘积 reward【必做】

门带 latch(§1.9),任务序列是**压 handle 解锁 → 稳握推门**。现有问题:(a) `push_door_handle` 不要求抓握、handle_pos 在限位饱和 → 单侧压+farming(§1.7);(b) hold 与 hinge 是加法关系,policy 可以只专精其一(v11 冻结、A3000 压把手的收益学根源)。v13 用两个 **grasp-gated 乘积项** 替代:

```python
def _get_a2_hold_streak_ok(self):
    K = self._get_a2_grasp_streak_control_steps()
    return (self._a2_stage3_stage4_both_contact_streak >= K).float()

@StagedTaskBase.effective_in_stage(STAGE_OPEN)
def _reward_a2_stage3_unlatch_hold(self):
    handle_pos = self.simulator.scene.articulations["door"].data.joint_pos[:, 1]
    hinge_pos  = self.simulator.scene.articulations["door"].data.joint_pos[:, 0]
    press = (handle_pos / 0.6).clamp(0.0, 1.0)      # UNLATCH_NORM=0.6 rad,待 §1.9 验证项标定后回填
    near_closed = (hinge_pos < 0.1).float()          # 门一旦离开门框,解锁不再有价值 → 停止发放
    return self._get_a2_hold_streak_ok() * press * near_closed

@StagedTaskBase.effective_in_stage([STAGE_OPEN, STAGE_SWING])
def _reward_a2_stage3_stage4_hold_and_drive(self):
    hinge_vel = self.simulator.scene.articulations["door"].data.joint_vel[:, 0]
    drive = (hinge_vel / 0.1).clamp(0.0, 1.0)        # 0.1 rad/s 饱和;负速(回弹/关门)不给分
    return self._get_a2_hold_streak_ok() * drive
```

要点:两项都乘 `hold`(去抖双侧接触)——**松手压把手拿不到一分钱**,这直接编码用户需求"过程中 gripper 稳稳握着";`unlatch_hold` 用 `hinge<0.1` 截断,防止开门后继续吊在把手上 farming;`dont_push_door_handle`(stage4/5 已有,scale 3.0)负责后段松开把手的语义,保持不动。

scale 建议(v13 全套 stage3/4 报酬结构):

```yaml
push_door_handle: 0.0                       # 6.0 → 0.0:旧形态废弃,由 a2_stage3_unlatch_hold 接管
push_door_hinge: 6.0                        # 保持(vel+pos 混合,门动起来后是主收入之一)
a2_stage3_unlatch_hold: 3.0                 # 新增;握住+压满把手+门未离框 ≈ 3/step
a2_stage3_stage4_hold_and_drive: 8.0        # 新增;满速开门且保持抓握 ≈ 8/step
a2_stage3_stage4_keep_close_command: 0.5    # 以下 hold bundle 维持 v12 水平,不回 v10_D 的 9.1/step
penalty_a2_stage3_stage4_open_command: -1.0
a2_stage3_stage4_both_contact: 0.5
a2_stage3_stage4_opposite_squeeze: 0.5
a2_stage3_stage4_squeeze_force_window: 0.5
a2_stage3_stage4_contact_stability: 0.5     # M1 后变为去抖版、可学习;不再需要 1.0(H 因子实验作废)
penalty_a2_stage3_stage4_over_force: -1.0
```

账:冻结收益 ≤ 2.5/step;握住+解锁但不推 ≈ 2.5+3 = 5.5/step;握住+解锁+满速推门 ≈ 2.5+6+8 ≈ 16.5/step;单侧压把手(丢 hold)≈ 0。梯度一路指向"稳握推门",且不奖励甩门(hold 断了 hinge_vel 再大也是 0,见 §2.3 甩门监控)。
新 reward 需在 `gr00t/rl/config/rewards/wbmanip/reward_door_open_a2_base.yaml` 注册默认值 0.0,ablation yaml 里再开。

#### M6|stage3→4 advance 加抓握条件【必做,防作弊】

`_stage_3_to_4_advance_condition`(:11821)A2 分支改为:

```python
door_opened & (self._a2_stage3_stage4_both_contact_streak >= K)
```

否则 M3 解锁 base 后,"单侧压把手解锁 + body-push"(v8/v9 的老路,§1.9 证明 latch 挡不住它)会重新成为最优路径。threshold 保持 0.25。

#### M7|forced-close 课程【可选,仅当放弃 warm-start 走 scratch 时】

前 100–200 iter 在 close_gate 成立时把 gripper primitive 强制为 close(eval 侧已有 `forced_gripper_close_applied` 机制可搬到训练侧)。M4 采纳时本项跳过。

#### M8|合成快照播种 staged reset【backlog,不进 v13 首轮】

若 v13 首轮 stage4 曝光仍稀薄:用脚本化夹持(现成 `a2_hold_*` static clamp machinery)构造"已夹持+门微开"状态,直接写入 `staged_reset_buf`(robot+door+delta_actions 三案齐写,`staged_reset_num_samples` 相应 +1,注意 per-env 索引语义,见 1.6)。架构支持,工作量中等。

#### M9|观测与报警【必做,防止 v10 式盲区重演】

- 训练 log + `eval_to_log` 增加:streak 分位数、`streak_ge_K_frac`、per-stage stability 分子/分母、`hold_and_drive_frac`(§2.0 定义)、stage3 内 handle_pos 分布(p50/p95/钉 0.785 占比)、`unlatch_hold` 发放率、coasting 帧占比(hinge_vel>0.1 且无双侧接触,甩门监控)。
- eval 汇报脚本对"gate 类指标连续 N 个 checkpoint 恰为 0"打显式 WARNING——`contact_stability=0.0000 exactly` 这种信号在 v10–v12 被 both_contact 57% 掩盖了三个版本。

#### M10|训练前的零成本验证(先于一切训练)【必做】

1. 实施 M1(env 代码 + config key)。
2. 对 **v12_C step3000** 重跑 matched eval(seed0/16env/first-episode,协议不变):
   - **预期:≥14/16 进 stage3**(trace 重建为 16/16,首过步 15–26,中位 20);
   - stage3 内会看到 hold 维持但 hinge 仍≈0(Kp 还是 80 力不够,且 C3000 未学过压 handle 解锁)——这**不是**失败,恰好把根因 A 与根因 B/C 的贡献切开。
3. 若 stage3 entry 仍为 0:M1 实现有 bug(streak 更新时机/清零逻辑),先修再谈训练。

### 2.2 v13 run 矩阵(顺序执行,不是并行 2×2)

| Run | 内容 | 目的 | 预算 |
|---|---|---|---|
| **v13_pre** | M1 + M10 eval-only(C3000) | 证实根因 A;0 训练成本 | ~10min GPU |
| **v13_A(主线)** | M1+M2(Kp800/25)+M3+M4+M5+M6+M9 | 拿到"抓握推门"行为 | 3000 iter,2 ranks(v12 同规模 ~14h) |
| **v13_B(gate-only 消融)** | M1+M4+M9,其余=v12_C(Kp80、base locked、v12 reward 原样含 handle=6) | 分离根因 A 单独贡献;预计会复现 §1.7 的单侧压吸引子——这本身就是 M5 必要性的对照证据 | 1500 iter 即可判 |
| **v13_C(force-only 消融,优先级最低)** | M2+M4+M9,`a2_grasp_gate_mode: physics_history`(不启用去抖) | v10_D 已示 force-only@Kp160 → 0.2% 低通过率+冻结(§1.8);本 run 回答"Kp800 的深预紧是否让老 gate 通过率本身变高",以及弱 hold scales 下是否仍冻结 | 视 A/B 结果决定是否跑 |
| v13_D(可选) | v13_A 减 M3(base 仍锁) | 若 A 成功,归因 base 贡献;若 A 卡工作空间,此项定位 | 视 A 结果 |

- GPU:当前 2/3/6/7 空闲,可同时跑 A + B/C 之一;先 A+B,C 视 B 结果补。
- seed:主线若资源允许加 seed1(basin 敏感性);消融单 seed 可接受(有 warm-start 去彩票)。
- 所有 run 保存 `save_frequency: 250`,eval co-locate 在 `logs_eval/base_v13/<eval-run>/`(遵循 memory 中的 eval 目录约定;qualitative render 默认随机 2 env × 3 camera)。

### 2.3 判读标准(matched eval,协议与 v12 完全一致)

| 时点 | 指标 | v13_A 期望 | 触发动作 |
|---|---|---|---|
| iter 250 | `stage2_to3_advance_frac` | >1%(v12_A 是 0.06%) | 低于 → 查 M1 实现 |
| iter 250 | `stage3_active_frac` | >20% | — |
| iter 1000 | stage4 entry(eval) | ≥4/16 | 为 0 → 看 hinge 曲线与 j7/j8 反驱,考虑 Kp 回退档或 M8 |
| iter 1000 | `hold_and_drive_frac`(stage3 内) | >5% | ≈0 且 hinge≈0 → 力仍不够,查摩擦/Kp |
| 终点 | goal_reached | >0/16 即里程碑 | — |
| 终点 | 中间成功档 | 16/16 stage3、≥8/16 stage4、hinge_end ≥0.4 rad 且运动期间双侧接触 ≥60% | — |
| 全程 | `a2_stage3_stage4_over_force_frac` | <2% | 持续高 → Kd 或 Kp 回退 |
| 全程 | j7/j8 open-limit proximity(stage3/4) | <10%(v9 是被反驱的标志) | 高 → 力量仍不足以扛负载 |
| 全程 | `door_handle_joint_pos` 分布 | 解锁期(hinge<0.1)应达 ~0.6+,但**不该长期钉死 0.785 限位**(§1.7 farming 标志) | 钉限位且 hinge 不动 → 单侧压回归,查 hold gating 实现 |
| 全程 | stage3 内 `single_contact_arm_body8_frac` | <20% | 高 → 单侧压杠杆形态回归 |
| 全程 | 甩门监控:stage3/4 内 `hinge_vel` p95 | <0.4 rad/s,且 "coasting"(hinge_vel>0.1 且无双侧接触)帧占比 <10% | 高 → policy 在甩门;确认 hold_and_drive 的 hold gating 生效,必要时加 door-overspeed penalty |
| 终点 render | 2 env × 3 cam(含 handle_side 机位) | 目视确认:压 handle→回弹前门已被推动;开门全程 gripper 在把手上;无"拍一下让门飞出去" | — |

### 2.4 风险与对策

| 风险 | 对策 |
|---|---|
| K=5 去抖过松,垃圾抓握混进 stage3 | stage3 hold reward + M6 带抓握的 stage3→4 兜底;必要时 K→8(160ms,T4 附录给了 K=3/5/8 的通过率) |
| Kp800 接触颤振/穿透爆炸 | Kd=25 近临界;`num_velocity_iterations: 2`;回退档 400/18;盯 over_force 与 j7/j8 vel |
| base unlock 后 body-push 作弊 | M6;同时盯 `a2_stage2_single_contact_arm_body8_frac` 与 doorframe contact |
| warm-start 权重不适配新执行器 | 前 100 iter 允许指标回撤;若 500 iter 未恢复 C 的 stage2 水平,改用 v13_B 的 checkpoint 续 |
| streak 更新时机错误(重复计数/漏清零) | M10 eval-only 验证先行;单元:同一 step 多次调用 completion masks 不得改变 streak |
| 甩门(shove-release:拍门后松手滑行) | hold_and_drive/unlatch_hold 都乘 hold,松手即零收入;M6 使无抓握的 hinge 穿越不能进 stage4;§2.3 有 coasting 监控;若仍出现,加 `penalty_door_hinge_overspeed`(hinge_vel>0.5 rad/s 罚) |
| UNLATCH_NORM=0.6 标定不准(过松→未解锁就饱和;过紧→重现限位压) | §1.9 验证项先标定;上下界都在 handle 行程内,风险有限 |
| 训练与 eval 的 gate 定义漂移 | K 与所有阈值只放 `door_open_a2_base.yaml` 单源;matched eval 读同一 config |

### 2.5 任务语义(用户已决策,2026-07-16)

用户确认:**最终任务就是带门锁的门——先下压/旋转 handle 解锁,再推门,全程 gripper 稳稳握住,不允许把门甩开。**且经 §1.9 勘误,当前训练场景 `build_latch=True` 本来就与此一致(用户在既往成功 eval 视频中看到的"下压→回弹"即 latch 机构)。因此:

- **不改门资产**;grasp-forced 路线(bypass 封死)与最终任务对齐,维持;
- "稳握不甩门"由 M5 的 hold-gated 乘积项 + M6 的带抓握 stage3→4 + §2.3 甩门监控三层编码;
- stage4/5 已有 `dont_push_door_handle`(scale 3.0)与 stage4→5 的 `handle_up<0.2` 条件,负责"门开后松开把手回弹"的后段语义,v13 不动;
- 后续(v14+)的门形态 randomization(left/right、in/out、latch 参数)见 memory `door-asset-randomization-baseline` 的既有决策,不在 v13 范围。

### 2.6 结果→下一步决策树(给带结果回来的诊断 session)

| 观察 | 结论 | 下一步 |
|---|---|---|
| v13_pre:stage3 entry 仍≈0 | M1 实现 bug | 查 streak 更新时机/清零;修复前不训练 |
| v13_pre 达标(≥14/16) | 根因 A 证实 | 启动 v13_A、v13_B |
| v13_A:iter250 advance>1% 但 stage2 抓握指标较 C3000 大幅回撤且 500 iter 不恢复 | warm-start 不适配新执行器 | 用 v13_B 的 checkpoint 换血再跑 A 配置 |
| v13_A:stage3 好、stage4 恒 0、hold_and_drive≈0、j7/j8 反驱高 | 力仍不够(摩擦或 Kp) | 查 μ(§M2 验证项)、Kd 档、必要时 M8 播种 stage4 快照 |
| v13_A:stage4 有、goal 0、卡 stage4→5 | 前段已通,后段(边走边扶门/松把手)问题 | 分析 stage4/5 轨迹,调 `dont_push_door_handle`/`target_root_distance` 权重,另立 v13.1 |
| v13_A:handle 钉 0.785+hinge 不动 | 单侧压回归(M5 gating 失效) | 查 unlatch_hold 的 hold/near_closed gating 实现 |
| v13_A 成功、v13_D(base 锁)也成功 | base unlock 非必要 | 未来可锁 base 简化 sim2real |
| v13_B:进 stage3 并复现单侧压吸引子 | M5 必要性的对照证据 | 记 memory,无需续跑 |
| v13_B:居然能稳握开门 | Kp80+去抖已够,M2 非必要 | 主线可回退 Kp,缩小 sim2real gap |
| v13_C:advance 率比 v10_D 的 0.2% 明显高 | Kp800 深预紧确实能"救活"老 gate | gate 语义仍推荐去抖版(可学习 reward);记录事实即可 |

---

## 3. 实施 checklist(建议顺序)

1. [ ] 读本文档;诊断 T1–T4 已全部跑完,结果在附录 A,无需复跑。
2. [ ] M1 env 代码(streak buffers、更新点、判据替换、config key、日志)。
3. [ ] M10:C3000 eval-only 验证,产出 `logs_eval/base_v13/base_v13_pre_gatepatch_C3000_.../`,与 §2.3 预期比对。**不达标不往下走。**
4. [ ] M5/M6 reward 与 advance 代码(unlatch_hold、hold_and_drive 在 reward yaml 注册默认 0);M9 遥测。
5. [ ] 新 ablation yaml ×3:`base_v13_A_main.yaml`、`base_v13_B_gate_only.yaml`、`base_v13_C_force_only.yaml`——**完整内容见附录 B,可直接抄**。
6. [ ] smoke:每 run 先 64 env × 50 iter 空跑,确认无 shape/NaN、streak 日志在动、over_force 不爆;同时完成两个验证项:latch 有效解锁角标定(§1.9,回填 UNLATCH_NORM)、handle/finger 实际摩擦系数 μ(M2)。
7. [ ] 启动 v13_A(GPU 空闲对),随后 v13_B;v13_C 视 B 结果。
8. [ ] 每 250 iter 对照 §2.3;终点跑 matched eval + render(2 env × 3 cam),co-locate `logs_eval/base_v13/`。
9. [ ] **memory 记录**(遵循 repo `MEMORY.md`/`AGENTS.md` 约定,写 `memory/a2-piper/push-open-door-optimization/` 的 `description.md`/`TODO.md`/`DONE.md`,时间戳 HKT):
   - 三个根因作为可复用事实(gate 时间尺度;夹持力天花板公式 F=Kp×0.035 与 effort 饱和条件;unlatch 奖励形态/单侧压吸引子);
   - **勘误:训练门带 latch(build_latch=True,scenario_cfg)**——此前 session 曾误判无 latch,必须显式纠正,防止后续 session 继承错误;
   - "单 seed factorial 在 basin 主导问题上无因果解释力"的方法论教训;
   - v12 四 cell 终局 + H 因子未生效的结论;
   - v13 各 run 的配置关系与 M10 验证结果;用户的任务语义决策(§2.5);
   - 不要写入 origin-reference。

---

## 附录 A|诊断数据(T1–T4,均已跑)

> 生成脚本:`scriptsFORhuman/a2_piper_base_v13_diagnostics_20260716.py`(用法:`python3 <脚本> all`,T2 需追加 trace 路径参数;逻辑=按 first_episode 分 env、以 control-step current-frame 重建 squeeze 三条件与 streak)。

### T1|v12_A step3000 stage3 timeline(已跑)

**2 个 env** 有 stage3 帧(env12 n=141、env14 n=384),与 metrics_eval 的 2/16 一致(metrics 数组不按 env-id 排序),形态一致(完整叙述见 §1.7):
- env12:both% 0.0(进入后即失),j8_open 97.2%,handle_max 0.539,hinge_max 0.0008;
- env14:both% 0.3,j8_open 100%,handle 被压死 0.785 限位,f=[0.0, 9–40N],hinge_max 0.0115(base 前爬 0.02 时短暂出现),tcp_med 0.048;
- 全程 close command 100%(prim -0.3~-1.2)——**"想抓"与"物理上抓不住"同框**。

### T2|repair-B500 深抓握力学标定(已跑)

`base_v11_repair_r1_B_handle0_ckpt500_..._holdterms` trace,stage≥3 共 7587 帧:
- 帧级 contact_stability 99.2%;
- 弱爪 |squeeze_y| p10/50/90 = **2.77/3.21/3.64N**,强爪 3.41/3.85/4.45N(=Kp160×jaw 误差,j7 p50=0.0237m);
- **16 env 各一条连续 squeeze3 streak,p50=470 步、max=527 步,全程零断裂**。
- 对照 v12_C(Kp80,弱爪 p50=1.46N):控制步级 streak 中位数十步级、25ms 物理窗口内必断。
- **标定结论:接触稳定阈值 ≈3N/爪;拖门需求 ≈10N/爪(§1.3 物理账)。**

### T3|v10_D 训练趋势(已跑)

```
iter   stage   adv2to3  s2both  s2stab  s3act   s4act   hinge
100    1.10    0.0000   0.0000  0.0000  0.0002  0.0     0.0000
600    2.12    0.0001   0.0328  0.0001  0.0536  0.0     0.0003
700    2.94    0.0022   0.0243  0.0022  0.6811  0.0     0.0006
1000   2.97    0.0020   0.0056  0.0020  0.8189  0.0     0.0007
```
iter~700 advance 率到 0.2%/step 后 staged-reset 飞轮点火(s3act 5%→82%),但 **s4act 恒 0、hinge 恒 0.0007**——force-only 的终点是冻结(§1.8)。

### T4|C3000 counterfactual 去抖 gate(已跑)

对 C step3000 的 16 env stage2 trace,以 control-step current-frame 重建 squeeze 三条件:

```
K=3: 16/16 通过,首过步 min/med/max = 13/17/19
K=5: 16/16 通过,首过步 min/med/max = 15/20/26
K=8: 16/16 通过,首过步 min/med/max = 18/23/31
```
**M10 的预期由此从"预测"升级为"已验证 counterfactual"**;K 在 3–8 间不敏感,取 5。

### 已固化的关键数字(§1 全部来源)
- C3000 eval:单帧 both 92.0% / opp 93.1% / suff 93.1% / gate 96.7% / cmd 97.0% / prog 95.9%;5 物理帧 stability = **0.0000**;
- C3000 trace:弱爪 |sy| p10/50/90 = 1.20/1.46/2.81N,强爪 1.47/2.66/3.68N;streak 断裂 100% 归因单爪掉接触;
- A3000 eval:stage3 2/16(trace env12/14),episode 553=452+101;
- A 训练终点(iter2908):adv 0.06%,s3act 12.2%,s34 stability/全步 1.7%,hinge 0.0002 rad;
- C 训练终点(iter2887):adv 0.01%,s2both 57.2%,s2stab 0.01%,hinge 0.0002 rad;
- v10_D config:Kp160/6、base unlocked、hold 2/1/2/4/-2、close_gate_required false、staged reset [0.5,0.1×5];
- 门:80–120kg、hinge maxForce 2.5–4.5 N·m(target -10°)、handle maxForce 1–2 N·m(target -15°,限位 [0,45°])、把手半径 11–15mm、50% hook;**带 latch**(scenario_cfg `build_latch=True`;锥形 latch 经 mimic joint 随 handle 收回,0.03m/45°,见 §1.9);
- physx:fps200/decimation4、pos_iters 4、vel_iters 1(v10–v12 相同)。

---

## 附录 B|v13 各 run 完整 ablation 配置(可直接抄)

> 文件放 `gr00t/rl/config/ablation/wbmanip/`。骨架与 v12 系列一致;所有新 env/reward key 的实现见 §2.1。
> 启动命令模板(v12 实测同款;`<GPUS>` 用空闲对如 `2,3` / `6,7`,port 各 run 唯一):
> ```bash
> CUDA_VISIBLE_DEVICES=<GPUS> accelerate launch --multi_gpu --num_processes 2 \
>   --main_process_port <PORT> gr00t/rl/train_agent_trl.py \
>   +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/<ABLATION_NAME> \
>   project_name=a2_piper_full_stage_a2_base experiment_name=<ABLATION_NAME>
> ```
> matched eval 沿用 v12 流程(config staged 进 `logs_eval/_eval_inputs/<name>/`、eval_agent_trl、seed0/16env/first-episode),产物 co-locate `logs_eval/base_v13/<eval-run>/`。

### B.1 `base_v13_A_main.yaml`(主线)

```yaml
# @package _global_

# v13_A main line: debounced gate + saturated-effort fingers + stage3 base unlock
# + policy_only warm-start from v12_C step3000 + grasp-gated unlatch/drive rewards.
# Evidence & design: scriptsFORhuman/a2_piper_base_v13_optimization_plan_20260716.md

checkpoint: logs_rl/a2_piper_full_stage_a2_base/base_v12_C_v10A_scratch_stability1-20260716_004404/model_step_003000.pt
checkpoint_load_mode: policy_only   # 验证 loader 接受的字符串
auto_load_latest: false
seed: 0
num_envs: 4096
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
    a2_stage2_squeeze_force_min: 2.0          # M2
    a2_stage2_squeeze_force_max: 20.0
    a2_stage2_over_force_threshold: 40.0
    a2_grasp_gate_mode: control_streak        # M1
    a2_grasp_streak_control_steps: 5          # M1
    a2_stage3_to4_door_hinge_threshold: 0.25
    a2_stage3_base_unlocked: true             # M3

rewards:
  reward_penalty_curriculum: false
  reward_initial_penalty_scale: 1.0
  reward_min_penalty_scale: 1.0
  reward_max_penalty_scale: 1.0
  reward_penalty_degree: 0.0
  reward_scales:                              # M5
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
      arm_j7: 800.0                           # M2(回退档 400)
      arm_j8: 800.0
    damping:
      arm_j7: 25.0                            # M2(回退档 18)
      arm_j8: 25.0

simulator:
  config:
    render_results: false
    cameras:
      enable_cameras: false
    sim:
      physx:
        num_velocity_iterations: 2            # M2
```

### B.2 `base_v13_B_gate_only.yaml`(gate-only 消融)

与 v12_C 唯一差异 = M1 去抖 + M4 warm-start。**reward、Kp80/3、base locked、vel_iters 1 全部保持 v12_C 原样**(含 `push_door_handle: 6.0`、`a2_stage3_stage4_contact_stability: 1.0`——预计复现 §1.7 单侧压,即 M5 的对照组):

```yaml
# @package _global_
checkpoint: logs_rl/a2_piper_full_stage_a2_base/base_v12_C_v10A_scratch_stability1-20260716_004404/model_step_003000.pt
checkpoint_load_mode: policy_only
auto_load_latest: false
seed: 0
num_envs: 4096
headless: true
algo:
  trl:
    num_total_batches: 1500
callbacks:
  model_save:
    save_frequency: 250
env:
  config:
    a2_stage2_contact_force_threshold: 1.0
    a2_grasp_gate_mode: control_streak        # 唯一的机制变化
    a2_grasp_streak_control_steps: 5
    a2_stage3_to4_door_hinge_threshold: 0.25
    a2_stage3_base_unlocked: false
rewards:
  reward_penalty_curriculum: false
  reward_initial_penalty_scale: 1.0
  reward_min_penalty_scale: 1.0
  reward_max_penalty_scale: 1.0
  reward_penalty_degree: 0.0
  reward_scales:
    push_door_handle: 6.0
    push_door_hinge: 6.0
    push_door_force: 0.0
    a2_stage3_unlatch_hold: 0.0
    a2_stage3_stage4_hold_and_drive: 0.0
    a2_stage3_stage4_keep_close_command: 0.5
    penalty_a2_stage3_stage4_open_command: -1.0
    a2_stage3_stage4_both_contact: 0.5
    a2_stage3_stage4_opposite_squeeze: 0.5
    a2_stage3_stage4_squeeze_force_window: 0.5
    a2_stage3_stage4_contact_stability: 1.0
    penalty_a2_stage3_stage4_over_force: -1.0
robot:
  control:
    stiffness: { arm_j7: 80.0, arm_j8: 80.0 }
    damping:   { arm_j7: 3.0,  arm_j8: 3.0 }
simulator:
  config:
    render_results: false
    cameras:
      enable_cameras: false
    sim:
      physx:
        num_velocity_iterations: 1
```

### B.3 `base_v13_C_force_only.yaml`(force-only 消融,视 A/B 结果决定跑不跑)

= B.1 减去 M1/M3/M5:`a2_grasp_gate_mode: physics_history`、`a2_stage3_base_unlocked: false`、reward_scales 用 B.2 的 v12_C 原样(handle 6.0、stability 1.0、两个新项 0.0),其余(checkpoint、Kp800/25、squeeze_min 2.0、vel_iters 2、num_total_batches 1500)同 B.1。关注指标:`a2_stage2_to3_advance_frac` 对比 v10_D 的 0.002。

### B.4 `base_v13_D_baselocked.yaml`(可选,v13_A 出结果后再定)

= B.1 仅改 `a2_stage3_base_unlocked: false`,`num_total_batches: 1500`。

### B.5 v13_pre(M10 eval-only,不需要新训练 yaml)

对 C3000 的 matched eval 输入 config 做两处 patch:`a2_grasp_gate_mode: control_streak`、`a2_grasp_streak_control_steps: 5`(实现 M1 后这两个 key 会从 env yaml 默认带出;eval 侧确认生效即可),eval 输出目录 `logs_eval/base_v13/base_v13_pre_gatepatch_C3000_matched_scalar_trace_16env_seed0_<date>/`。
