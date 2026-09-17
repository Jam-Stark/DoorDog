# DONE

- 2026-09-17 16:58 HKT：D058按Owner指示实际终止A284及旧watcher/6000等待，清除本任务遗留Isaac子进程。已观察5167迭代、保存至5000；取消6000并披露完整历史未达成，按原排序冻结A282@6000主、A284@5000备；主候选双侧exact128 DEV已启动。

- 2026-09-17 15:54 HKT：完成A284@5000双侧有效exact64；complete64/63、clean26/12，hinge失败38/51、RIGHT1集超速、tower0/0。相机失败、回位观测1/0及删失63/63、K末值.2已记录D057。持久wait因实际readout提前返回；继续6000，候选未冻结。

- 2026-09-17 08:46 HKT：完成A284@4000双侧有效exact64，首次双侧complete64、clean13/12；hinge失败50/52与body1/0、相机失败、回位19/17观测及45/47删失、K末值.294086已记录D056。持久wait因实际readout提前返回；继续5000/6000，候选未冻结。

- 2026-09-17 01:42 HKT：完成A284@3000双侧有效exact64；LEFT complete0、RIGHT complete64/clean32，RIGHT不clean为hinge32集，双侧tower0。相机失败、回位删失0/64和K过程量已记录D055；原3000到期后实际readout在本次follow-up处理。继续既定6000，候选未冻结。

- 2026-09-16 18:26 HKT：完成A284@2000双侧有效exact64；S4各64、S5为9/1、complete0，身体/hinge/camera删失与K=1.0已记录。D054保持既定6000合同；实际续期参数遗漏已纠正并由readout验证等待路径。原三seed终点1/3单列，候选未冻结。

- 2026-09-16 11:06 HKT：完成A284@1000双侧有效exact64，早期Stage3/4与无完成、camera null、K=1.0均记录；D053维持原6000合同，首个独立等待路径实际验证。原三seed终点1/3单列，资格尚未执行。

- 2026-09-16 10:30 HKT：完成原三seed6000六条有效exact64及终点可靠性1/3（REACH_SEED_UNSTABLE）判定；质量/camera/K分量与删失已记录。D052确认A284已在GPU5从scratch实际启动，候选冻结待其完整六milestone，未提前运行资格或新增commit。

- 2026-09-16 00:11 HKT：D051触发后的A284独立milestone等待目标已接入；逐个匹配watcher既有readout路径，实际等待验证留待首个A284 milestone。原6000等待与训练配置未改；未新增测试或实验。

- 2026-09-15 21:59 HKT：完成原三seed step5000六条有效exact64与readout；281超速、282身体接触/hinge、283塔架与无完成分量及camera/K证据已记录。D051确认283在4000/5000触发D31，A284按原合同排队，原三seed继续6000；候选冻结待实际A284完整证据。未新增commit节点。

- 2026-09-15 14:45 HKT：完成原三seed step4000双侧共6条exact64与readout，全部有效。281完成64/64、clean47/38，282完成36/33、clean3/2，283无完成；塔架、身体接触、相机逐stage与回位删失、K trace分量已报告。D050记录相邻条件未满足、不启动A284、继续原6000及下一等待依据；未新增commit节点。

- 2026-09-15 07:41 HKT：完成原三seed step3000双侧共6条exact64与readout，全部有效。281完成5/64、clean1/40，282/283无完成；塔架、身体接触、相机逐stage与回位删失、K trace分量已报告。D049记录相邻条件未满足、不启动A284、继续原6000及下一等待依据；未新增commit节点。

- 2026-09-15 00:48 HKT：完成原三seed step2000双侧共6条exact64与readout，全部有效。281双侧到Stage4但所有seed complete/clean仍0；相机、塔架/身体接触、回位删失及K trace已报告。D048记录A284尚未满足相邻两时点条件、继续原6000及下一等待依据；未新增commit节点。

- 2026-09-14 18:14 HKT：完成原三seed step1000双侧共6条exact64与readout；全部有效，实际scratch/4096/Ktarget4/reset合同成立。早期D/S4+/complete为0，按D046继续6000，不提前给终点结论；D047记录预算、A284未触发和下一等待依据。

- 2026-09-14 10:54 HKT：记录Owner D046明确批准原三seed scratch续行；G1不改判、warm取消、500纳入总账。完成一次G1科学source/config/asset与当前字节连续性比对；授权与STATIC事实不等于Wave A已运行。

- 2026-09-14 08:56 HKT：真实G1完成500批及左右exact64，reducer V28_COMPLETE、门判WARM_FAIL（RIGHT塔架6>2），按Owner成本门停止。D16实际eval目录通过，双侧CAMERA_UNMET属report-only；完整回位删失已报告。交付停止点记录、NOT_RUN WaveA/B、空候选manifest与OWNER_DECISION_REQUIRED closure、N01/N02回收。实际预算500；代码同步/CPU与真实路径证据区分，未启动scratch、DEV/CONF或新方法。证据D044/D045及execution_20260913。

- 2026-09-13 01:47 HKT：按新的阶段执行授权同步D038–D040、G1 full续训/条件warm arm、supervisor调度/独立格watcher、固定DEV→CONF、readout/render/closure和持久waiter。修复D16 eval顶层目录覆盖与checkpoint旁别名复制，metadata只读路径保持。10个Python文件AST、实际A_W281 Hydra compose及原G0 camera readout检查通过；无事件保持null。证据STATIC_PASS/已保存runtime观测，未产生新G1或训练验收。runtime入口execution_20260913，决策D041/D042。

- 2026-09-12 17:18 HKT：Owner批准planner裁决，完成plan与决策日志D038–D040、M1–M5活动入口及memory更新。原三seed6000可靠性独立报告；最多两个资格导向主/备候选、A284条件入池和固定DEV→CONF顺序已写明，预算/门值不变。证据等级INSPECTED/文档落盘；执行代码同步仍为TODO，未训练、评估、改配置或commit/push。

- 2026-09-12 15:45 HKT：按 Owner 要求，将 FULL_REVIEW.md、原解析 prompt、本地更新审计及索引落到 `scriptsFORhuman/pro_reviews/v28/8435858/`，供 v28 planner 对照 finalize。重复 Pro ZIP 已按 Owner 后续要求删除。Pro 初判 A 与后续 B/C/D 原样保留；本地草案未应用，实验合同、源码、配置与运行状态未改。

- 2026-09-11 HKT：按Owner要求生成180mm/45°与140mm/38.76°腕机局部四视图SVG、PNG预览、精确绘图变换和生成脚本，入口见`camera/wrist_comparison_20260911/README.md`。采用原U3视角和当前URDF原始网格，统一参考姿态/比例；140mm支架标为未验收示意包络。仅CPU绘图及视觉检查，未修改rig、asset或训练配置。

- 2026-09-09 HKT — v28 plan 冻结（`scriptsFORhuman/v28/a2_piper_base_v28_plan_20260909.md`）、待办登记建立、五个只读规划 lane 的证据归档到 `scriptsFORhuman/v28/planner_evidence_20260909/`。全部为 INSPECTED/STATIC/COMPUTED 证据，未运行 Isaac、未改 source/config，未 commit。

- 2026-09-09 HKT（-codex worker）：已实现robot/扁平scratch配置、动作夹紧与camera reward；compose STATIC_PASS、六项CPU语义测试通过。Owner明确真实CAD缺失、宽长方体支架与R3/R5修订。memory路由已登记。尚未完成完整G0，不能称runtime PASS或已commit。

- 2026-09-09 HKT（修改：-codex worker；依据：-owner）：已交付robots目录下合并版与z=130mm统一水平裁切版；URDF/USD均已生成，28/31刚体与20活动关节USD静态读回完成。安装位姿与质量合同记录在各目录validation，候选等待Owner选择，G0保持暂停。

- 2026-09-12 HKT（-codex worker）：执行D030–D035，完成MERGED/140mm/新姿态/K配置、USD读回、R1/R2/R3/R5与A4；C3保留旧轨迹FAIL。匹配默认姿态G0-L因stand三项相对误差失败后按Owner规则STOP，未继续PPO/G1或commit。

- 2026-09-12 HKT（修改：-codex worker；依据：-owner）：落实D36 p50 floor+p95、保留legacy判定与原FAIL，默认离线PASS；新hold PASS，类Stage2三项p50FAIL，按规则再次STOP。原数据与readout历史保留，X-24/N-09已登记；未默认GPU重跑、未seed282校准、未PPO/G1/commit。

- 2026-09-12 HKT（修改：-codex worker；依据：-owner）：D37分层门与三代判定落地，既有三姿态只离线重判；按冻结harness执行282类Stage2旧/MERGED各一次，数值确认PASS，识别seed无随机消费者并保留X24。64env×5batch PPO与左右各64环境评估exit0，26字段接线与null口径通过，G0 launch门完成。

- 2026-09-12 HKT：§9.7首个本地commit已完成，标题`Complete v28 G0 asset and telemetry integration`，135个v28/G0文件，未push；原始日志、source快照、无关共享改动保留。GPU/本任务runtime均释放。实际receipt见`resume_20260911/first_commit_receipt.json`。
