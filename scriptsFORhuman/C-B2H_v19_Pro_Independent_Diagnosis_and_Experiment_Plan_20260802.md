# C-B2H v19 视觉 Student 蒸馏退化：独立根因诊断与下一阶段实验方案

## 0. 证据完整性

证据包已按要求核验：

* ZIP SHA-256：`d59d7615a90ef65bca33ebc31bed283712f44d0cb203af6c55aee6183f36c2a0`
* 在解压目录执行 `sha256sum -c MANIFEST.sha256`，所有条目均为 `OK`
* 审计代码固定在 `Jam-Stark/DoorDog@8ccba8e3b1d85886466f7b5df66a1fada87e903a`
* 没有使用默认 `main` 或当前 `A2_Piper` 工作树替代上述代码

核验记录：

* [完整 MANIFEST 校验输出](sandbox:/mnt/data/cb2h_manifest_check.txt)
* [README_FIRST.md](sandbox:/mnt/data/cb2h_extract/README_FIRST.md)
* [独立派生证据附录](sandbox:/mnt/data/C-B2H_v19_independent_derived_evidence.md)
* [最终 step10000 checkpoint 独立结构与有限值检查](sandbox:/mnt/data/cb2h_final_checkpoint_validation.json)
* [packed / sequential BN 探针](sandbox:/mnt/data/cb2h_bn_probe.json)
* [Head 与双 D435i feature 探针](sandbox:/mnt/data/cb2h_feature_probe.json)

---

# 1. Executive conclusion

**当前证据不支持把“64 env 太少”或“10k iteration 太少”列为首要答案，也不支持直接追加到 20k。**

最重要的诊断是：

1. **这次所谓 DAgger 实际上是 100% Teacher-rollout online behavior cloning。**
   配置为 `enforce_teacher_rollout=true`、`ratio_teacher_rollout=1.0`；trainer 在每一步先计算 Student action，随后把所有64个环境的高层动作全部替换为 Teacher action。因此 Student 在整个5.12M env-step训练期间从未控制状态分布。
   DoorMan 对 DAgger 的关键定义正是：监督应覆盖 Student 自己访问的输入分布，而普通 BC 只覆盖 Teacher 分布。当前 DoorDog 路径没有获得这一性质。

2. **H3 是当前绝对 closed-loop 失败的高置信度贡献因素，但它不能单独解释“v19 比 v16 更差”。**
   v16 C-B 训练同样使用 `ratio_teacher_rollout=1.0`。因此 Teacher-only covariate shift 能解释两者都在 formal eval 中 `0/16 goal`，却不足以单独解释 v19 的 stage0 比例更高。

3. **历史 v16 与 v19 formal eval 不是 matched comparison。**
   v19 的16个case覆盖了更宽、更困难的随机化区间：handle高度到 `1.0805 m`、门重到 `155.28 kg`、hinge drive max force到 `11.42`；v16分别只到 `0.9435 m`、`117.64 kg`、`4.38`。因此 `mean stage 0.50 vs 0.75` 和 `reward -174.9 vs -85.2` 不能被直接解释为 C-B2H architecture regression。来源分别为 [v19 formal metrics](sandbox:/mnt/data/cb2h_extract/repo/logs_eval/cb2h_v19_student_step10000_seed0_16env_gpu7-20260802_031735/formal_student_metrics.json) 和 [v16 formal metrics](sandbox:/mnt/data/cb2h_extract/repo/logs_eval/a2_piper_student_v16_cb_ckpt5000_seed0_16env_gpu7-20260729_132948/results/metrics_eval.json)。

4. **C-B2H 存在一个已证实的设计—实现偏差：双 D435i 没有 packed single forward。**
   设计要求：

   ```text
   [left, right]
       → pack [2M,3,384,216]
       → one shared ResNet forward
   ```

   实现却是：

   ```python
   f_left = encoder(left)
   f_right = encoder(right)
   ```

   同一个 ResNet 被转换为 `SyncBatchNorm`，所以训练时左右图分别使用自己的 minibatch statistics，而评估时两路共用一份混合 running statistics。
   这比“右路后调用，所以直接改变右路输出”更准确：独立探针显示反转调用顺序不会改变当次 train-mode feature，但会改变 running-stat update；sequential 与 packed feature 则存在可测差异。

5. **当前 fusion 的 Head 使用方式值得怀疑，但尚不能定罪。**
   一个独立的36帧诊断中，learned Head scalar gate 的均值约 `9.98e-5`，几乎关闭；然而固定 `head_base_weight=0.25` 路径仍然持续注入，贡献norm约为 manipulation feature 的24%。这说明当前网络不是“完全忽略Head”，而是“几乎关闭 learned residual，却保留不可门控的固定Head路径”。该结果只来自一个 retained render，不是 formal causal proof。

因此，最划算的下一步是：

> **先做 matched Teacher ceiling、checkpoint sweep、open-loop imitation、Head-mask和BN诊断；然后只用200–500 iteration做 packed-vs-sequential 与 B0/B1/B2。确认表示结构后，再执行真正的 mixed-rollout DAgger。**

---

# 2. 对现有 handoff 的独立修正

## 2.1 实际 Teacher 是 v19 G2 step2000

本次正式训练绑定的是：

```text
base_v19_G2_norm_control
model_step_002000.pt
SHA-256 b331c9a3...866d
```

不是先前讨论中的 G3 fallback。Teacher manifest 与训练命令均明确绑定 G2：

* [Teacher manifest](sandbox:/mnt/data/cb2h_extract/repo/logs_rl/cb2h_v19_runtime/g2_step2000_c18_reconstruction_candidate6168e6a2/teacher_manifest.json)
* [exact_command.sh](sandbox:/mnt/data/cb2h_extract/repo/logs_rl/cb2h_v19_distill/cb2h_v19_g2s2000_gpu7_64e_10k_fix0f9c11e_retry1/exact_command.sh)

## 2.2 bundled checkpoint validation 不是 final checkpoint validation

证据包内的：

```text
checkpoint_validation.txt
```

检查的是早期 `last.pt`：

```text
global_step=50
episode=3200
SHA c8445ba0...
```

它不能证明 step10000 checkpoint 完整。

我对 `model_step_010000.pt` 做了独立CPU载入与递归有限值检查，结果为：

```text
global_step       10000
max_steps         10000
episode           640000
tot_timesteps     5120000
policy tensors    293
value tensors     19
optimizer states  169
non-finite        0
```

来源：

* [原 checkpoint_validation.txt](sandbox:/mnt/data/cb2h_extract/repo/logs_rl/cb2h_v19_distill/cb2h_v19_g2s2000_gpu7_64e_10k_fix0f9c11e_retry1/checkpoint_validation.txt)
* [最终 checkpoint 独立验证](sandbox:/mnt/data/cb2h_final_checkpoint_validation.json)

## 2.3 “checkpoint 是1.89倍，所以10k可能仍不够”不是强证据

v19 checkpoint 变大主要因为：

* 增加第二个 ResNet18 Head encoder；
* 增加 fusion MLP、view embeddings和LayerNorm；
* Adam optimizer为新增参数保存一、二阶状态；
* 保留critic/value state。

文件大小与有效样本复杂度不是线性关系。它只能说明模型和optimizer state更大，不能推出训练iteration至少也要按1.89倍放大。

## 2.4 handoff 对 SyncBN “顺序偏差”的描述部分正确，但不够精确

独立探针结果：

```text
sequential vs packed cosine:
  left  0.9917
  right 0.9907

sequential vs packed mean L2:
  left  5.81
  right 6.91

反转调用顺序导致的当前batch输出差：
  exactly 0
```

最终checkpoint中：

```text
D435 SyncBN num_batches_tracked = 80000
Head SyncBN num_batches_tracked = 40000
```

这恰好对应：

```text
10000 iteration × 4 minibatch × D435 two calls
10000 iteration × 4 minibatch × Head one call
```

因此真实风险是：

> **左右视图在训练时分别进行BN归一化，但评估时两路共用一份混合running distribution。**

不是“右路每次前向因为后调用而直接使用了左路更新后的batch statistics”。

---

# 3. 四层证据表

| 层级        | 结论                                                                        | 证据                                                                                                                                                                                                        |
| --------- | ------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **已验证事实** | v19完成64 env、10000 iteration、5.12M env-step和最终checkpoint保存                 | [run.log](sandbox:/mnt/data/cb2h_extract/repo/logs_rl/cb2h_v19_distill/cb2h_v19_g2s2000_gpu7_64e_10k_fix0f9c11e_retry1/run.log)、[最终checkpoint验证](sandbox:/mnt/data/cb2h_final_checkpoint_validation.json) |
| **已验证事实** | formal eval是pure Student、seed0、16 env、0/16 goal、stage `{0:12,1:2,3:2}`    | [v19 formal metrics](sandbox:/mnt/data/cb2h_extract/repo/logs_eval/cb2h_v19_student_step10000_seed0_16env_gpu7-20260802_031735/formal_student_metrics.json)                                               |
| **已验证事实** | v16 formal也是0/16，而不是stage5整体成功                                            | [v16 formal metrics](sandbox:/mnt/data/cb2h_extract/repo/logs_eval/a2_piper_student_v16_cb_ckpt5000_seed0_16env_gpu7-20260729_132948/results/metrics_eval.json)                                           |
| **已验证事实** | v16 stage5 success来自一次非确定性render replay                                   | [v16 render metadata](sandbox:/mnt/data/cb2h_extract/repo/logs_eval/a2_piper_student_v16_cb_best_env13_sixcam_gpu7-20260729_185257/selected_env13_render_metadata.json)                                   |
| **已验证事实** | v19 env13 formal stage3在三次replay中均退化到stage1                               | [v19 retained render metadata](sandbox:/mnt/data/cb2h_extract/repo/logs_eval/cb2h_v19_student_step10000_env13_render_trial01_gpu7-20260802_041312/selected_render_metadata.json)                          |
| **已验证事实** | v19和v16 formal case envelope不匹配                                           | [独立派生证据](sandbox:/mnt/data/C-B2H_v19_independent_derived_evidence.md)                                                                                                                                     |
| **已验证事实** | v19 12个stage0 failure中，10个terminal doorframe force>0                      | 同上                                                                                                                                                                                                        |
| **已验证事实** | ratio=1.0时所有64个环境均由Teacher action控制                                       | 配置与trainer实现。                                                                                                                                                                                             |
| **已验证事实** | 实现是sequential shared encoder，而不是packed single forward                     |                                                                                                                                                                                                           |
| **已验证事实** | ResNet使用SyncBatchNorm和global adaptive average pooling                     |                                                                                                                                                                                                           |
| **强推断**   | Teacher-only occupancy导致Student-only closed-loop误差累积                      | 配置直接证明Student未控制训练状态；表现为stage0 lateral drift/contact                                                                                                                                                      |
| **强推断**   | v19 stage0 collapse主要是approach/heading/contact失败，不只是handle manipulation失败 | stage0 group的terminal lateral error、yaw和doorframe penalty                                                                                                                                                 |
| **强推断**   | historical v16/v19 metric gap中有显著case/runtime confounding                 | 两组门参数区间明显不同                                                                                                                                                                                               |
| **强推断**   | sequential BN产生train/eval view-domain mismatch                            | train时每路独立batch stats，eval时共用running stats                                                                                                                                                                |
| **弱推断**   | 128D per-view GAP bottleneck丢失handle位置和左右非对称关系                            | 无token、无spatial map、无B0/B1/B2                                                                                                                                                                             |
| **弱推断**   | 固定Head base path在错误时机稀释manipulation feature                               | 单render probe支持，但尚无Head-mask formal eval                                                                                                                                                                  |
| **弱推断**   | 10k仍处于持续提升区间                                                              | 没有checkpoint sweep或BC loss曲线支持                                                                                                                                                                            |
| **未知项**   | matched v19 Teacher在完全相同16case上的正式ceiling                                 | 未运行                                                                                                                                                                                                       |
| **未知项**   | step1000–10000 Student formal curve                                       | 中间checkpoint未正式评估                                                                                                                                                                                         |
| **未知项**   | stage-stratified Student/Teacher action error                             | 训练log未记录                                                                                                                                                                                                  |
| **未知项**   | B0/B1/B2因果差异                                                              | 未运行                                                                                                                                                                                                       |
| **未知项**   | packed encoder是否显著改善closed-loop                                           | 未运行                                                                                                                                                                                                       |
| **未知项**   | Head是否在formal case中真正有益                                                   | 未运行                                                                                                                                                                                                       |
| **未知项**   | 多seed formal policy分布                                                     | 只有seed0                                                                                                                                                                                                   |

---

# 4. 根因候选排序

以下概率是“该因素对当前失败有实质贡献的主观概率”，不是互斥统计posterior。

| 排名 | 假设                                                       |       置信度 / 概率 | 判断                                                           |
| -: | -------------------------------------------------------- | -------------: | ------------------------------------------------------------ |
|  0 | **额外发现：v16/v19 case与runtime不匹配**                         |    很高 / `0.90` | 对“表面相对退化”是一级confounder；必须先做matched comparison                |
|  1 | **H3：100% Teacher rollout造成closed-loop covariate shift** |     高 / `0.75` | 是绝对policy failure的重要机制；但不能单独解释v19相对v16更差                     |
|  2 | **H5：sequential shared SyncBN偏离packed设计**                |    中高 / `0.60` | 偏差已证实；主要风险是separate train stats与shared eval stats，不是直接右路顺序输出 |
|  3 | **H4：global 128D fusion丢失空间或非对称线索**                      |    中高 / `0.55` | 三路在GAP后才融合，低重叠视图缺少spatial-token routing；尚无因果消融               |
|  4 | **H6：Head fixed weight / scalar gate使用错误**               |     中 / `0.45` | 单case probe显示learned gate塌缩，但fixed Head path仍强制存在            |
|  5 | **H2：10k仍不足**                                            |    中低 / `0.30` | 现有log无BC loss或checkpoint policy curve；不能排除，但不值得直接下注20k       |
|  6 | **H8：nondeterminism / case sampling造成表面退化**              |    低中 / `0.25` | 对单条deep-tail结论影响很大；不足以解释12/16 broad stage0 failure           |
|  7 | **H7：Teacher/runtime ceiling差**                          | 低但未关闭 / `0.20` | Teacher-controlled训练window不差；缺matched formal Teacher eval    |
|  8 | **H1：64 env本身不足**                                        |     低 / `0.15` | v16同样64 env；v19样本量翻倍；没有受控env-count证据                         |

## H1 的资源结论

128-env exact admission在optimizer前已经到约 `47,959 MiB` 并OOM，没有checkpoint。64-env长训总GPU memory实测峰值约 `32,586 MiB`，主训练进程峰值约 `30,457 MiB`。来源：[GPU telemetry](sandbox:/mnt/data/cb2h_extract/repo/logs_rl/cb2h_v19_distill/cb2h_v19_g2s2000_gpu7_64e_10k_fix0f9c11e_retry1/gpu_telemetry.log)。

因此当前48GB单卡上：

```text
128-env test = BLOCKED
```

在不改变分辨率、env或执行路径的前提下，至少需要一张 **80GB单GPU**。当前runner还绑定单进程、单visible GPU；多GPU不是可直接替代项。

---

# 5. 为什么有两个 stage3 深尾，但整体 stage0 更差

这两个现象并不矛盾。

## 5.1 Student形成了很窄的成功吸引域

少量初始case恰好满足：

* 视觉目标处于较熟悉位置；
* 初始base yaw和lateral offset较容易；
* Teacher-distribution下学到的approach action误差足够小；
* 没有早期撞door frame。

这些case可以进入stage1、stage2甚至stage3。

其余多数case中，微小视觉/action误差会引起：

```text
base lateral drift
→ doorframe contact
→ camera pose进一步偏离
→ 后续视觉进入Teacher训练分布之外
→ error compounding
```

当前训练从未包含由Student动作造成的这种恢复状态。

## 5.2 stage3只表示“进入了open阶段”，不表示会开门

两个stage3 terminal case的门状态约为：

```text
hinge joint position ≈ 0.001 rad
handle joint position ≈ 0
```

也就是说，它们完成了部分接近/抓取stage transition，但没有形成有效开门动作。stage3 tail的深度不能按完整能力解释。

## 5.3 深尾非常脆弱

正式env13为stage3，但相同case三次独立render replay全部变成stage1。

因此当前分布更像：

```text
少量脆弱的深尾
+
大多数case无法稳定进入正确approach basin
```

而不是“整体能力稳定，只是最终stage失败”。

---

# 6. 是否应直接再训到20k

## 结论：当前不合理

直接从10k继续Teacher-only训练到20k只会继续增加：

```text
Teacher occupancy上的image → Teacher action样本
```

不会直接增加：

```text
Student偏离后状态
Student碰门框后的恢复状态
Student camera drift后的纠正状态
```

训练log没有记录：

* `dagger_bc_loss`
* per-action MSE
* stage-stratified imitation error
* feature norm
* gradient norm
* action disagreement
* Head-mask delta

因此无法从现有log判断Student在10k时仍在学习，还是早已plateau。来源：[v19 run.log](sandbox:/mnt/data/cb2h_extract/repo/logs_rl/cb2h_v19_distill/cb2h_v19_g2s2000_gpu7_64e_10k_fix0f9c11e_retry1/run.log)。

## 只有以下证据同时出现，才支持追加Teacher-only iteration

1. step1000/2500/5000/7500/10000在相同fixed cases上持续改善；
2. step10000是paired evaluation中的最佳点；
3. 5000→10000期间：

   * mean max stage至少提高 `0.20–0.25`；
   * stage0失败至少减少 `3/16`；
4. open-loop stage0 base-command NRMSE仍显著下降；
5. packed BN、Head mask和B1/B2均没有给出更强的改善方向。

## 以下任一结果都应否定“直接20k”

* checkpoint curve在5000或7500已经plateau；
* open-loop误差已经较低，但closed-loop仍差；
* packed-only 200 iteration显著优于sequential continuation；
* B1明显优于B2；
* mixed rollout 0.75在500 iteration内已改善stage0；
* matched Teacher ceiling很高，而Student对Teacher轨迹拟合已足够好。

---

# 7. 最小成本、最大信息量实验 DAG

```text
Integrity verified
        │
        ├── N1 Matched Teacher ceiling
        ├── N2 Checkpoint sweep
        └── N3 Sealed Teacher-trajectory dataset
                    │
                    ├── N4 Open-loop / Head / view diagnostics
                    └── N5 Packed-BN recalibration
                              │
                              ▼
                  200–500 iteration tests
                    P1 packed vs sequential
                    P2 B1 vs B2
                    P3 B0 system baseline
                              │
                              ▼
                    Architecture gate
                              │
                              ▼
        True mixed-rollout DAgger 1.0→0.75→0.50→0.25
                              │
                              ▼
                     Long-run decision
```

---

# 8. 无需重新训练的实验

## N1 — Matched v19 Teacher ceiling

| 项目              | 设计                                                               |
| --------------- | ---------------------------------------------------------------- |
| 唯一变量            | controller：Teacher而不是Student                                     |
| Frozen inputs   | exact G2 step2000 triplet、c18 runtime、16个v19 formal case、物理/相机配置 |
| 规模              | 16 cases × 3 replay seeds = 48 episodes                          |
| GPU             | 同一物理GPU7，1×48GB；16 env                                           |
| 预计耗时            | 现有16-env formal约4分钟；总计约15–25分钟                                   |
| 指标              | goal、max stage、stage0→1、doorframe contact、root Y/yaw、reward      |
| Ceiling PASS    | goal `≥40/48`，stage0 overtime `≤2/48`                            |
| INCONCLUSIVE    | goal `32–39/48`；增加32个fixed cases                                 |
| Ceiling blocker | goal `<32/48` 或stage0 failure `>6/48`                            |
| 停止条件            | 48 episodes sealed；禁止挑选render替代                                  |
| 证伪              | Teacher本身若在同case频繁stage0，则H7上升，不能优先怪Student fusion               |

---

## N2 — Student checkpoint sweep

需要本地已有：

```text
step1000
step2500
step5000
step7500
step10000
```

| 项目            | 设计                                                                |
| ------------- | ----------------------------------------------------------------- |
| 唯一变量          | Student checkpoint step                                           |
| Frozen inputs | exact16 cases、same c18、same eval code、same Student-only protocol  |
| 第一阶段          | 5 checkpoints × 16 cases × 1 trial                                |
| 第二阶段          | top2 checkpoints × 16 cases × 2额外replay seeds                     |
| GPU           | 1×48GB，16 env                                                     |
| 预计耗时          | 约45–75分钟                                                          |
| 指标            | paired max stage、stage0 count、reward、doorframe contact、root Y/yaw |
| 支持H2          | step10000明确最佳；5000→10000 mean stage `+≥0.20`，stage0 `-≥3/16`      |
| 否定H2          | 5000/7500已达峰值，或7500→10000无改善/退化                                   |
| 停止条件          | 若连续三个checkpoint paired mean-stage差 `<0.10` 且stage0数量不变，停止继续扫描     |
| 结果用途          | 决定longer Teacher-only是否还有信息价值                                     |

所有checkpoint必须：

```text
存在
hash记录
strict load
global_step与文件名一致
finite
```

缺任一checkpoint时应显式 `MISSING_EVIDENCE`，不能自动跳过并改变集合。

---

## N3 — Sealed open-loop Teacher trajectory dataset

| 项目            | 设计                                                                         |
| ------------- | -------------------------------------------------------------------------- |
| 唯一变量          | 无模型训练；采集Teacher-controlled轨迹                                               |
| Frozen inputs | N1相同16case × 3 trials                                                      |
| 保存内容          | 81D proprio、三路raw RGB、camera_meta、Teacher12D、stage、done、case ID、frame ID   |
| 规模            | 48 episodes                                                                |
| GPU           | 1×48GB                                                                     |
| 预计耗时          | capture 20–40分钟；offline evaluation 30–60分钟                                 |
| 指标            | per-action MSE/NRMSE、base5D与arm7D分组、stage-stratified误差、transition-window误差 |
| 定义            | `NRMSE_j = RMSE_j / (std(Teacher_action_j)+1e-6)`                          |
| “拟合足够”参考门     | 12D median NRMSE `≤0.25`；stage0 base-command NRMSE `≤0.20`                 |
| “拟合不足”参考门     | median NRMSE `>0.40` 或stage0某base command `>0.50`                          |
| 证伪            | 若open-loop很准而closed-loop差，强支持H3；若stage0 open-loop已很差，优先H4/H5/H6/H2         |

这套dataset应成为后续所有checkpoint和fusion probe的固定输入，避免每个诊断重新生成不同case。

---

## N4 — View utilization 与 Head-mask 诊断

同一Student checkpoint、同一N3数据，运行：

```text
FULL
HEAD_INVALID
LEFT_INVALID
RIGHT_INVALID
LEFT_RIGHT_SWAP
```

不改变权重、不修改图片内容，只通过显式validity或输入顺序形成诊断。

记录：

```text
||f_left||
||f_right||
||f_head||
manipulation residual norm
context gate
Head fixed contribution
full-vs-masked action delta
per-action disagreement
```

诊断带：

| 现象                                      | 解释                         |
| --------------------------------------- | -------------------------- |
| Head gate p95 `<0.01`                   | learned Head residual基本关闭  |
| Head-mask action delta接近0               | Head实际未被使用                 |
| Head-mask action delta极大且主要破坏arm action | Head可能错误主导                 |
| 左或右mask在所有stage中delta接近0                | 对应D435视图被忽略                |
| view swap引起极端action跳变                   | view identity/fusion可能过度脆弱 |

这些是诊断，不是policy-quality PASS gate。

当前单render probe已发现：

```text
Head gate mean 9.98e-5
Head gate p95  2.72e-4
```

但必须在N3的正式48轨迹上复核。[现有 feature probe](sandbox:/mnt/data/cb2h_feature_probe.json)

---

## N5 — Packed BN recalibration，无optimizer

目的：最低成本地测试H5中的 **eval running-stat mismatch**。

流程：

1. 复制step10000 checkpoint；
2. 所有权重冻结；
3. D435 encoder改用packed forward；
4. 在N3 Teacher frames上只更新D435 SyncBN running mean/var；
5. 不执行backward，不更新fusion/LSTM/MLP；
6. 保存为新的明确identity；
7. 对相同16case运行Student-only formal eval。

| 支持H5  | mean stage提高 `≥0.20` 或stage0减少 `≥2/16` |
| ----- | -------------------------------------- |
| 强支持H5 | 3 trials中stage0合计减少 `≥5/48`            |
| 弱化H5  | action/open-loop/formal均无有意义变化         |
| 停止条件  | 一次完整BN pass + 3次formal；不迭代调参           |

该实验只能验证running-stat部分，不能代替packed训练。

---

# 9. 200–500 iteration诊断

## P1 — Packed vs sequential，共同step10000起点

先从同一个step10000 checkpoint复制两条branch：

```text
P1-S: existing sequential forward
P1-P: packed single forward
```

| 项目                      | 设计                                                                                |
| ----------------------- | --------------------------------------------------------------------------------- |
| 唯一变量                    | D435 encoder调用方式                                                                  |
| Frozen                  | 权重、optimizer、runtime、Teacher、ratio1.0、64 env、所有camera/fusion                      |
| 第一阶段                    | 200 iterations                                                                    |
| 模糊时扩展                   | 两路都扩展到500，禁止只延长表现较差的一路                                                            |
| GPU                     | 1×48GB；当前64-env峰值32.6GB                                                           |
| 预计耗时                    | 200约30–45分钟/路；500约75–90分钟/路                                                       |
| 新增日志                    | BC loss、per-action NRMSE、D435 grad norm、BN count、feature norm、VRAM、iteration time |
| packed directional PASS | open-loop NRMSE改善≥10%，或mean stage `+≥0.20`，或stage0 `-≥2/16`                       |
| 资源门                     | 峰值 `<46 GiB`；若OOM或超过资源预算，标记BLOCKED                                                |
| 停止                      | 500后无差异则H5显著弱化                                                                    |

不要在packed OOM时自动回退sequential。

---

## P2 — B1 vs B2：Head 的严格因果测试

先接受packed实现，然后比较：

```text
B1 = dual D435i only
B2 = dual D435i + OEM Head
```

### 冻结条件

* exact G2 step2000 Teacher triplet
* exact c18 runtime
* ±20° D435i geometry
* packed shared D435 encoder
* 同一64 env / 8 steps / 4 minibatches / LR
* 同一common initialization
* 同一16 fixed cases
* 同一训练seed
* ratio1.0，仅作为representation diagnostic

### 500-iteration判定

B2相对B1需要满足至少一项有效性门，并满足全部安全门：

有效性门：

```text
48-case stage0 failures减少 ≥4
或
paired mean max stage增加 ≥0.20
或
doorframe-contact episode count降低 ≥20%
```

安全门：

```text
stage2+ count不得降低超过2/48
overspeed不得增加
over-force不得增加
root yaw / lateral error不得恶化超过10%
```

若B2不优于B1：

* 不能继续声称OEM Head“必然帮助方向/避障”；
* 应保留Head作为硬件/诊断stream；
* Student首个长训选择B1，或先重构Head fusion。

---

## P3 — B0 / B1 / B2严格对照

| ID     | 输入/网络                                                                         | 解释边界                                                |
| ------ | ----------------------------------------------------------------------------- | --------------------------------------------------- |
| **B0** | 原v16 C-B spatial composite：D435i + letterboxed Head拼成`216×768×3`，单ResNet→128D | system baseline；camera geometry和表示都不同，不是纯fusion因果实验 |
| **B1** | 两台±20° D435i，packed shared ResNet；无Head                                       | 操作视角基础组                                             |
| **B2** | B1 + OEM Head separate ResNet + hierarchical fusion                           | Head增量组                                             |

B0必须使用：

```text
同一个v19 G2 Teacher
同一个c18 runtime
同一训练预算
同一case集合
```

不能拿历史v16训练结果直接作为B0训练结果，因为历史B0的Teacher、runtime和随机化范围不同。

### Common initialization

B1与B2应建立共同的step0 core：

```text
D435 encoder
LSTM
action MLP
running_mean_std
```

这些参数hash必须一致。B2只额外增加：

```text
Head encoder
context fusion
Head embedding
```

否则随机初始化差异会污染Head因果判断。

### 可选 B0′

若B0胜出，需要再做：

```text
B0′ = 使用当前C-B2H三路图，但做固定spatial mosaic后单ResNet
```

B0′才更接近“spatial composite vs feature fusion”的纯表示比较。

---

## P4 — Head fusion micro-ablation，仅条件触发

只有当N4/P2显示Head有害或利用异常时运行：

```text
H0: head_base_weight = 0.00
H1: head_base_weight = 0.25
```

其他全部冻结，200 iterations起步。

首轮不要同时修改：

* scalar gate为vector gate；
* feature维度；
  -Head encoder；
* normalization；
* camera age公式。

一次只改变一个机制。

---

# 10. Packed shared encoder 最小代码修正

当前代码：

```python
left = dual_flat[..., :3].permute(0, 3, 1, 2).contiguous()
right = dual_flat[..., 3:6].permute(0, 3, 1, 2).contiguous()

f_left = self.d435i_vision_module(left).reshape(left.shape[0], 128)
f_right = self.d435i_vision_module(right).reshape(right.shape[0], 128)
```

建议改为：

```python
left = dual_flat[..., :3].permute(0, 3, 1, 2).contiguous()
right = dual_flat[..., 3:6].permute(0, 3, 1, 2).contiguous()

if left.shape != right.shape:
    raise RuntimeError(
        f"C-B2H left/right packed encoder shapes differ: "
        f"left={tuple(left.shape)} right={tuple(right.shape)}"
    )
if left.ndim != 4 or left.shape[1:] != (3, 384, 216):
    raise RuntimeError(
        f"C-B2H D435 packed input must be [M,3,384,216], "
        f"got {tuple(left.shape)}"
    )
if left.dtype != right.dtype or left.device != right.device:
    raise RuntimeError("C-B2H left/right packed inputs must share dtype and device")

count = left.shape[0]
if count <= 0:
    raise RuntimeError("C-B2H packed D435 encoder received no valid frames")

packed = torch.cat((left, right), dim=0)
if tuple(packed.shape) != (2 * count, 3, 384, 216):
    raise RuntimeError(
        f"C-B2H packed D435 shape drifted: {tuple(packed.shape)}"
    )

encoded = self.d435i_vision_module(packed)
if tuple(encoded.shape) != (2 * count, 128):
    raise RuntimeError(
        f"C-B2H packed D435 output must be [2M,128], "
        f"got {tuple(encoded.shape)}"
    )
if not torch.all(torch.isfinite(encoded)):
    raise RuntimeError("C-B2H packed D435 features contain non-finite values")

f_left, f_right = encoded.split(count, dim=0)
```

## 必须更新的测试

1. D435 encoder调用次数从2改为1；

2. fake encoder收到的shape必须为 `[2M,3,384,216]`；

3. 前半batch精确对应left，后半精确对应right；

4. one optimizer minibatch后D435 `num_batches_tracked`只增加1；

5. Head encoder仍只增加1；

6. state dict仍只有一套：

   ```text
   d435i_vision_module.*
   ```

7. 不允许出现：

   ```text
   left_encoder.*
   right_encoder.*
   ```

8. packed forward异常时直接失败，不调用旧sequential路径。

首轮不建议同时把SyncBN替换成GroupNorm。先隔离packed变量；若packed无改善，再单独比较：

```text
packed SyncBN
packed frozen BN
packed GroupNorm
```

---

# 11. Mixed rollout 是否应执行

## 应执行，但不是现在立刻执行

前置条件：

1. N1证明Teacher ceiling足够；
2. packed/sequential完成选择；
3. B1/B2完成选择；
4. 已加入BC loss、action disagreement、feature/gradient日志；
5. 64-env 500-iteration稳定运行；
6. fixed-case formal adjudicator可重复执行。

当前run不是严格意义上的interactive DAgger。DoorMan明确把DAgger的价值定义为在Student输入分布上直接监督，而不是只在Teacher分布上BC。

## 当前 ratio<1 实现还需要一个修正

trainer当前使用：

```python
count = int(num_envs * ratio)
selected_high[:count] = teacher_actions[:count]
```

在64 env下：

```text
ratio 0.75:
  env0–47 永远Teacher
  env48–63 永远Student
```

这会把环境ID、随机case和rollout source耦合起来。

### 推荐确定性循环mask

每个8-step rollout固定一个source mask：

```python
teacher_count = int(round(num_envs * ratio))
if not math.isclose(teacher_count, num_envs * ratio):
    raise ValueError("teacher rollout ratio must yield an exact integer env count")

offset = global_step % num_envs
student_count = num_envs - teacher_count

student_mask = cyclic_block_mask(
    num_envs=num_envs,
    start=offset,
    count=student_count,
)
teacher_mask = ~student_mask
```

要求：

* 每个rollout内mask不变；
* 不同rollout按env循环；
* 64个batch窗口中每个env获得相同比例的Student控制；
* 每batch记录mask hash、Teacher count、Student count；
* Teacher仍对所有状态计算label；
* 不允许随机失败后回退全Teacher。

---

## Mixed rollout阶段和gate

### M0 — ratio 1.0 warm-up

```text
500–1000 iterations
```

目的：建立选定architecture的Teacher-distribution基础。若从已通过的500-iteration checkpoint继续，可不重复。

### M1 — ratio 0.75

```text
500 iterations
每batch 48 Teacher env + 16 Student env
```

前进到0.50的gate：

* 技术：无OOM、finite、mask比例精确；
* 48-case paired mean stage比M0提高 `≥0.15`，**或** stage0 failures减少 `≥3/48`；
* doorframe contact不增加；
* Student-visited BC NRMSE不得恶化超过20%；
* 无新增overspeed/over-force硬失败。

不满足则停止在M0/M1，不自动降ratio。

### M2 — ratio 0.50

```text
1000 iterations
32 Teacher + 32 Student
```

进入0.25的gate：

* 继续满足全部安全门；
* stage0 failure相对M1进一步下降，或mean stage进一步提高；
* Student-controlled轨迹中Teacher/Student action disagreement不发散；
* 不出现Student env集中在特定case失败的分布偏差。

### M3 — ratio 0.25

```text
2000 iterations
16 Teacher + 48 Student
```

验收：

* 三次fixed-case replay中改善可重复；
* 至少出现非零goal或稳定stage3/4分布；
* stage0 failure rate显著低于当前 `75%`；
* action/doorframe safety不退化。

当前不建议直接进入ratio0.0。先证明0.25下能够维持稳定Student occupancy和Teacher supervision。

---

# 12. 正式长训前 gate

在任何新的多千iteration长训前，必须全部满足：

| Gate                  | 要求                                                 |
| --------------------- | -------------------------------------------------- |
| Teacher ceiling       | matched 48-case结果通过或已解释                            |
| Encoder               | packed/sequential已经由实验选择                           |
| Head                  | B1/B2因果结论明确                                        |
| Loss observability    | BC loss、12D action error、stage-stratified error已记录 |
| Feature observability | per-view feature/gradient、Head gate、Head mask已记录   |
| Rollout mask          | ratio<1采用平衡mask，环境覆盖审计PASS                         |
| 64-env runtime        | 至少500 iteration自然完成训练循环，无OOM                       |
| VRAM                  | peak `<46 GiB`                                     |
| Checkpoint            | strict load、finite、optimizer完整                     |
| Eval                  | fixed16×3 formal protocol可重复                       |
| Lifecycle             | 可继续保持独立UNRESOLVED，但不得写成natural lifecycle PASS      |
| 128 env               | 仍为BLOCKED，不得自动尝试或降级                                |

---

# 13. 满足gate后的长训方案

推荐不是“失败的10k再延长到20k”，而是从选定的fresh/common initialization进行一条明确的mixed-DAgger schedule：

| 阶段     | Ratio | Iterations |  Env-steps |
| ------ | ----: | ---------: | ---------: |
| L0     |  1.00 |       1000 |     0.512M |
| L1     |  0.75 |       1000 |     0.512M |
| L2     |  0.50 |       2000 |     1.024M |
| L3     |  0.25 |       4000 |     2.048M |
| **总计** |       |   **8000** | **4.096M** |

基于本次实测约 `7.16 s/iteration`：

```text
trainer accumulated time ≈ 15.9 h
预计wall time ≈ 20–21 h
```

每500 iteration保存checkpoint；每个ratio阶段末做：

```text
fixed16 cases × 3 trials
open-loop NRMSE
view utilization
safety report
```

## Seed0进入重复训练的最低promotion gate

建议至少：

```text
goal > 0 / 48
stage0 failures ≤ 12 / 48
mean max stage ≥ 1.5
无新增安全失败
```

这不是最终policy-quality PASS，只是说明Student已经获得非零closed-loop能力，值得投入seed1/seed2。

只有seed0通过后，才运行两个独立训练seed。最终policy-quality结论必须基于多seed formal eval，而不是最佳render。

DoorMan的后续GRPO/bootstrapping也建立在基础Student具有非零成功率之上；当前 `0/16` 不适合作为直接GRPO起点。

---

# 14. 当前状态严格区分

| 状态                             | 当前结论                        | 含义                                                                |
| ------------------------------ | --------------------------- | ----------------------------------------------------------------- |
| **Training runtime PASS**      | **PASS到训练循环和checkpoint保存**  | 10000 iteration真实完成，无OOM/traceback                                |
| **Checkpoint completion**      | **PASS**                    | step10000、640000 episodes、5.12M timesteps、全部finite                |
| **Eval protocol PASS**         | **PASS**                    | pure Student、seed0、16 env、一episode/env、artifact sealed            |
| **Policy-quality PASS**        | **FAIL**                    | 0/16 goal，12/16停在stage0                                           |
| **Render completion**          | **PASS / qualitative only** | 视频完整，但不能替代formal分布                                                |
| **Natural Kit lifecycle PASS** | **NOT PASS / UNRESOLVED**   | log停止于`simulation_app_close_start`，没有close-complete和app exit seal |
| **128-env capacity PASS**      | **FAIL / BLOCKED**          | optimizer前OOM，约47,959 MiB                                         |
| **Multi-seed stability**       | **NOT RUN**                 | 只有一个training seed和一个formal eval seed                              |
| **Open-door Student success**  | **FAIL / NOT ESTABLISHED**  | checkpoint完成不等于开门能力                                               |

仓库memory自身也区分了：

```text
C_B2H_FORMAL_10K_CHECKPOINT_COMPLETE
C_B2H_STUDENT_EVAL_RUNTIME_PASS_POLICY_QUALITY_FAIL
C_B2H_LIFECYCLE_UNRESOLVED
```

---

# 15. 推荐执行顺序

## A. 无需重新训练

1. Matched v19 Teacher 48-case ceiling。
2. step1000/2500/5000/7500/10000 fixed-case sweep。
3. 生成sealed Teacher-trajectory dataset。
4. 计算stage-stratified 12D imitation error。
5. 正式Head-mask / left-mask / right-mask / swap诊断。
6. Packed BN-only recalibration。
7. 生成统一diagnosis report，决定H2/H5/H6的去留。

预计总GPU占用时间：约2–3小时。

## B. 200–500 iteration诊断

1. 从同一step10000分叉 sequential continuation与packed continuation，各200。
2. 必要时延长到500。
3. 采用packed后，fresh common-init B1与B2各500。
4. 运行B0 v19-matched system baseline 500。
5. 只有Head诊断明确异常时再做weight0/0.25 micro-ablation。

预计总GPU占用时间：约4–7小时，取决于是否延长和是否触发Head micro-ablation。

## C. 正式长训前gate

1. 选择B0/B1/B2 winner。
2. 封存exact architecture和initialization hash。
3. 通过64-env 500-iteration稳定性与VRAM门。
4. 完成balanced mixed-rollout mask。
5. 完成0.75短段并通过fixed-case improvement gate。
6. 若任一项失败，停止，不把训练预算扩大解释为解决方案。

## D. Gate通过后的长训

执行：

```text
1.00 / 1000
0.75 / 1000
0.50 / 2000
0.25 / 4000
```

先单seed；达到非零success和早期分布改善后，再复制两个training seed。

---

## 最终判断

**最可能的主问题不是“64 env太少”，也没有证据证明“再加10k就会好”。**

当前最具解释力且可直接证伪的组合是：

```text
100% Teacher occupancy
+
sequential per-view SyncBN / shared eval stats
+
per-view global 128D spatial bottleneck
+
未经验证的Head fixed-path fusion
+
历史v16/v19 case distribution不匹配
```

优先级应是：

```text
matched evidence
→ packed encoder
→ B1/B2 Head因果测试
→ true mixed-rollout DAgger
→ 才决定长训
```

而不是：

```text
当前实现 + 当前Teacher-only occupancy + 直接20k
```
