# 给 Pro：v29 baseline 独立判断、现实参数调研，以及 v28 验收

你是 DoorDog A2+PiPER 项目的独立云端 Pro 研究与审阅者。请完成本次请求，不只提出研究计划。中文回答；用一手来源做联网调研。本地 team 的结论不是你的答案，也不是已批准的 Owner 决定。

## 材料位置

- Git 仓库：https://github.com/Jam-Stark/DoorDog
- 专用审阅分支：`codex/v29-baseline-pro-20260918`
- 分支链接：https://github.com/Jam-Stark/DoorDog/tree/codex/v29-baseline-pro-20260918
- 提交主题：`Prepare v29 baseline research and v28 review handoff`
- 提交时间：`2026-09-18T00:39:09+08:00`；本地已验证该review HEAD与fetch后的远端tracking branch一致。按Owner约定不提供哈希清单；用本次专用分支与release目录定位。
- 本次唯一 Drive 任务目录：https://drive.google.com/drive/folders/11DvqGjIBMeRXdWYM2uVOBt9E-4KpUazy
- 目录：`Pro_Space/DoorDog/A2_Piper/base_v29_baseline_and_v28_review/20260918_003823__v29_baseline_review/`

该目录已有并经上传后读回验证的六个文件：

1. `worker_delivery__BUNDLE_INDEX.md`
2. `worker_delivery__BUNDLE_MANIFEST.json`
3. `worker_delivery__PRO_HANDOFF.md`
4. `worker_delivery__source_and_configs.zip`（18.54 MiB）
5. `worker_delivery__logs_and_metrics.zip`（1.64 MiB）
6. `worker_delivery__plots_and_evidence.zip`（15.62 MiB）

三个ZIP都是可分别打开的普通ZIP，不需要拼接。先读INDEX，按MANIFEST找包内路径。包里保留的`/home/baoquanc/workspace/DoorDog-A2_Piper/`绝对路径是本地历史记录，云端应去掉该前缀定位包内同名相对路径。review分支发布了选定source/config/docs与当前v29资产，运行证据和视频以ZIP为准；不要假定分支所有其他继承文件等于当前本地工作区。材料获取受限时明确列出未读取部分，不假装已核对。

## 先独立判断 baseline 的六项

先读取source包内：

- `scriptsFORhuman/v29/pro_handoff/20260918/OWNER_REQUEST.md`
- `scriptsFORhuman/v29/a2_piper_base_v29_decision_log.md`
- 所需当前source/config与metrics包内最终smoke的`config.yaml`

形成你自己的B01–B06初步判断，然后再读完整`a2_piper_base_v29_baseline_TODO.md`比较本地team意见。允许推翻或改写本地建议，不机械重复“保留现状”“25°”“两个形状族”等候选。

六项分别是：door mass/hinge drive等随机化；latch行程/解闩与转轴动力学；base双D435i仰角覆盖0.90–1.20m把手；门机械最大开角90°至当前上限的随机化及松手行为；保持两指夹握的形状族/概率回钩；相机光路、reset参考系和MERGED几何精度。

每项给当前事实、独立建议、关键理由/取舍和必要未知量；随后说明与本地建议的异同。先给自己的判断，再做以下现实数据调研，最后清楚标出哪些初判被新数据修正。不输出内部推理过程，只给可检验的理由和依据。

## 必须实际完成的三类数据调研

完整具体问题在`RESEARCH_BRIEF.md`，请全部承接：

1. **现实门的质量与动力学**：轻质室内门到重型防盗/防火门，尺寸、单扇质量、绕铰链惯量、铰链摩擦/起动阻力、闭门器力矩-角度/速度关系、阻尼、机械开角等。中国常见建筑门优先，国际原厂资料补充；给可用于randomization的合理范围/门型分层、参数关联和sim映射。不要把额定承载能力当门重、把把手处力当铰链力矩，或把规范上限当真实分布。
2. **常用latch/lever及随机化方法**：下压机械行程、开始/完成解闩角、latch缩回量、回位负载、门框几何关系，及这些参数如何协调采样。对照当前45°/30mm/mimic模型，说明reward/阶段/telemetry/观察量需要同步的最小修改；独立判断“压不动就是解锁”的可用部分与误判来源。
3. **合理的把手形状族**：以产品图纸为依据选择能保持现有两指夹握的圆/椭圆、扁圆/圆角截面、轻弯/L/J/S等候选，明确尺寸/曲率/门板间隙与主抓握段。曲杆grasp位置、局部方向及approach/closing frame必须随真实几何变化；说明visual/collision、handle刚体接触归属、质量/惯量以及回钩如何一致建模。

每个关键数值标清单位、来源链接、产品/标准名称和页码/表号（可取得时）；区分实测、原厂值、规范限值、推算与工程初值。缺数据就标未知，不编造“典型范围”。优先原厂datasheet/图纸、标准原文、可复核论文；标准版本/地区范围须注明。不要求每一参数另开大实验，不以最终CAD或完美Teacher作为无限前置条件。

## 同时独立验收 v28，并建议 v29 方向

阅读v28 plan、decision log、deferred register、最终closure、candidate manifest及实际readouts/逐回合数据。不要仅复述closure；也不要把此前Owner豁免的render补跑重新设成收尾条件。

已知必须承接但可核验的结果：

- v28已关闭。原三seed在6000的reach为1/3，可靠性未建立；历史checkpoint和条件A284不能混入这个分母。
- 固定主A282@6000 DEV clean为LEFT123/128、RIGHT47/128；备A284@5000为69/128、52/128。两者均未双侧通过，CONF未运行，新Teacher资格未确认，Teacher/G7未更新。
- 三条未过门lane主要缺crossing hinge≥1.0472rad；complete、clean、姿态、相机可用性分开解释。不能外推未评估checkpoint全部不合格或几何无解。
- A284按Owner提前停止，render按Owner复用，资源已收尾；包内含候选冻结、DEV启动、原始四侧128-episode records、metrics/process receipts、render复用与cleanup记录。
- N01旧pilot有效失抓暴露不足且有endpoint缺失，N02仅有限离线shadow信息；这些不构成有效方法确认，也不支持关闭方向。

分别给出“执行与交付收尾”“实验结论可信范围”“Teacher资格”“未验证能力”的验收意见。可以提出v29重审指标的理由，不回写v28裁定；没有checkpoint和完整DEV步级trace时，不能声称你重跑或完整重算过行为/相机指标。

然后结合六项TODO、调研、v28实际瓶颈、novelty与长期TODO，给少量有优先级的v29独立建议，说明工程baseline与恢复/适应研究的关系。当前Owner安排是push baseline GPU0/1两seed，N01 GPU2，N02 GPU3，pull同步baseline GPU4/5两seed，GPU6动态、GPU7监控/eval等；N01/N02等baseline落地后分到独立worktree。旧Astra排期不自动成为当前合同。

v29已有三项基础改动及64-env/1-batch接线；无正式训练和资格评估。六项TODO都待讨论。你本次不制定正式训练矩阵、预算或执行脚本，不批准代码实施、实验、G7更新或硬件操作。

## 交付要求

在对话中先给一份简短但完整的Owner答复，顺序为：

1. 六项独立判断/建议的紧凑总览；
2. 现实参数调研的高价值发现，尤其会改变baseline方向的事实；
3. v28分项验收意见及v29优先建议；
4. 必要时指出被忽视的方法/工程价值，避免为了novelty制造复杂度；
5. 附件文件名和一段可直接复制给本地Worker的接手prompt。

同时创建并**在Pro对话中附上**普通ZIP `pro_delivery__full_review.zip`（压缩后≤95MiB），至少包含：

- `FULL_REVIEW.md`：六项完整独立判断、三类调研与来源、v28验收、v29建议；区分证据/推断/未知/local-only检查。
- `LOCAL_WORKER_PARSE_PROMPT.md`：与简短回复第5项逐字一致的Worker prompt。
- 可另附参数CSV、把手形状说明/示意、来源表，供本地继续讨论。

Worker prompt应要求：按项目AGENTS和memory入口接手Owner上传的Pro附件，保存并解析到`scriptsFORhuman/pro_reviews/v29/`下本次独立目录；对照当前本地source/config/runtime核对可行性，把意见与数据出处写入v29 baseline TODO供Owner逐项决定，保留未决状态。不得自动实施、启动训练、划掉未确认议题或覆盖v28科学结论。

**Pro不要上传结果到Google Drive。** Owner会下载附件并传回本地任务。若无法生成附件，明确写`NOT_ATTACHED`并提供可取得的文件，不虚构下载链接。不生成哈希清单。
