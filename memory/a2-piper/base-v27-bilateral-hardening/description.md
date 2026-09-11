---
name: base-v27-bilateral-hardening
status: closed
scope: v26 qualification, bilateral behavior quality, door domain, one-loss recovery pilot, scratch reliability
last_verified: 2026-09-11
read_when:
  - implementing or resuming base_v27
  - interpreting bilateral Teacher qualification or v27 recovery evidence
source_of_truth:
  - gr00t/rl/envs/door/door_open_a2_base.py
  - scriptsFORhuman/v27/a2_piper_base_v27_plan_20260905.md
related_entries:
  - base-v26-scratch-bilateral-teacher
---

# base_v27 bilateral hardening

**当前终态（2026-09-11）：V27_COMPLETED_SCIENTIFIC_NO_RELEASE。** 六格Wave C均6000 PASS/0，72/72 lanes exact64、integrity0。Q_C=SCRATCH_NOT_ESTABLISHED（SC0/3）；K_SCRATCH_SUPERIOR（SK1/3，仅SK213），不等于三seed可靠性或Teacher资格。v27.0无合格候选；所有SC seed在全部milestone均未双侧过门，v27.5确认按冻结规则NOT_RUN。A=QUALITY_UNRESOLVED/C；B=DOMAIN_NOT_CONVERGED/current；R=UNRESOLVED（R1误停644），不得补齐或外推。

Closure：`scriptsFORhuman/v27/a2_piper_base_v27_execution_closure_20260911.md`；候选manifest v2同目录。临时隔离目录/候选副本已删除，历史source快照、checkpoint、原始eval、receipt与失败记录保留，active source指针已撤销。v27无活跃进程/tmux/lease。建议保留现有Teacher/G7，等待Owner绑定裁决；无push、hardware或binding更新。后文为历史执行记录。

v26 已由 Owner 裁定 `V26_SCOPED_TARGET_ACHIEVED` 并收尾。v27.0 在本轮完成资格认定；
旧 v26 artifact 保持不可变。当前 authority 为 source/resolved config → runtime artifact →
`scriptsFORhuman/v27/a2_piper_base_v27_plan_20260905.md` → memory；同目录 Astra 文件不是 authority。

获准顺序为 G0 → v27.0 与 Wave A 并行 → Wave B 门域/恢复 pilot 并行 → Wave C → closure。
GPU0/1 评估、GPU2–7 训练；四个本地 commit 已预授权，不 push；Teacher/Student/G7 binding 和硬件仍需 Owner 裁决。
正式训练上限 67,500 batches；每 wave 另有一次不超过 32 batches 接线 smoke。

研究父策略固定 v26-8 r3a `C_S2/model_step_003000.pt`；资格候选顺序 C_S2 → W_S2 → K_S2，
DEV 选择后不得按 CONF 换候选。Q_A 未决默认 C，Q_B 未收敛默认当前域，Q_R 不阻塞 Wave C。

2026-09-05 source 核对：eval 入口会写 checkpoint 相邻的 exported 目录；v27 为历史候选复制
checkpoint 与相邻 config 到新 v27 inputs，并核对字节身份，避免改写 v26 artifact。
Q1/Q2 的实际逐键值见新 runtime `g5_overlay_contract.json`；G5 中的 Stage4→5=1.25 与
Stage5 income-continuity 不属于 §4 明列允许修改的键，维持当前 1.0472/false。

2026-09-05 20:15 HKT — v27.0 已完成为 `NO_QUALIFIED_CANDIDATE`。DEV 三候选均 exact128/侧、
integrity=0；C/W/K LEFT clean_complete 为 75/100/71，RIGHT 为 69/112/119；K 超速终止为 6/5。
三者均未同时通过两侧质量门，CONF 未运行；18 个预定 QA 回合与 54 个视频齐全。
候选 manifest 第一版：`scriptsFORhuman/v27/a2_piper_base_v27_teacher_candidate_manifest_20260905.json`。
这属于注册模拟评估结论，不是 hardware 或 Teacher/G7 binding 更新。

K 初版 reducer 错误要求每个 episode 都有 Stage2–5 trace；LEFT env119 在 Stage1 超速终止、RIGHT
env107 在 Stage0 overtime，属于合法早期失败。Owner 明确授权后只对现有 K artifact 做 CPU 重判；
原 INVALID 保留，训练/DEV 均未重跑。当前 reducer 只要求已达 Stage2 的 episode 具备 trace，
早期终止仍计入完整分母。修正副本 9 项 CPU 测试通过，live reducer 与其字节一致。

G0 已有 STATIC/TEST/RUNTIME 证据：15 项组合 CPU 测试，64-env/5-batch Q2 smoke 与双侧 exact64。
一次 inactive transition 诊断请求的 rollout 前失败按授权修复重启；旧失败保留。
Wave A 六格均跑满3000 batches并正常退出；6个milestones共72 lanes、4608 episodes，全部exact64/侧、integrity0。
2026-09-06 endpoint为 `QUALITY_UNRESOLVED`，按预注册默认分支冻结 `RECIPE_A=C`；
`CARRIER_A` 固定为本轮 `C_S21/model_step_003000.pt`，不采用中途best或seed22替换。
endpoint LEFT/RIGHT clean：C_S21=51/41、C_S22=0/39、Q1_S21=5/40、Q1_S22=17/20、
Q2_S21=18/21、Q2_S22=16/39；没有单侧达到56/64 clean门。Q1/Q2 LEFT两seed clean均值
相对C分别为−14.5/−8.5；endpoint无`Q_HARMFUL_RIGHT`标签。
训练中曾出现正常退出但大量超速终止的milestone，已完整记录，未重跑或更改配方。
权威决策与端点锁：runtime下 `wave_a_decision.json`、`wave_a_endpoint_lock.json`；
完整读数见 `a2_piper_base_v27_wave_a_step3000_readout_20260906.md`。这是模拟实验结论，
不构成Teacher/G7资格授予。第二个预授权本地提交为`1fa2b1e`。

Wave B已启动：L0_S31/L1_S31/L1_S32在GPU2/3/4，各3000 batches，source为CARRIER_A；
R0_S41/R1_S41/R2_S41在GPU5/6/7，各1500 batches，source为固定v26 C_S2。CPU、32-batch R2
接线与双侧注入评估已完成；训练中实际发生bank capture、双侧promotion与两侧reset。
P02/P05四个exact32 probe的native readback分别为(2,1.5,0)/(5,3.75,0)，integrity0。
注入smoke LEFT64、RIGHT61集执行6步，RIGHT3集NOT_TRIGGERED；两侧loss_events=0，
不能据此宣称恢复收益。训练bank指标复用现有Env日志，计数是PPO batch内累计快照的均值。

L1首轮在actor加载前失败：parser误拒绝OmegaConf ListConfig。修复只接受实际框架列表类型，
三桶值、source、seed、budget不变；两格各在`L1_S31_r1`/`L1_S32_r1`新root重启一次。
`active_attempts.json`是实际root路由；`wave_b_l1_parser_r1_contract_diff.json`保留零实验合同差异。
两格现已strict actor/RMS加载并产生训练读数，4096个env的native readback已观测到0/2/5三桶、
dynamic范围0–3.75与viscous=0。其余四格继续运行，未重启。后续非零退出按policy读数后规则停格。
R组step500出现读取器误判：R1 nominal LEFT的合法706502006-byte JSON（32774 rows）在旧自写
分块reader的对象/逗号边界被判INVALID，自动停R1于训练644。Isaac进程正常退出，但wrapper因
缺少后续checkpoint退出1；这是harness误停，不是策略崩溃。已移除自写reader，改用标准库json.load；
10项reducer CPU测试通过。对原18条artifact仅做CPU重读后全部exact64、integrity0，原文件与原
INVALID保留，未重跑policy或评估。修正结果位于`wave_b_r/step500_cpu_reader_corrected/reducer.json`。
R1仍STOPPED，不擅自恢复或以step500替代1500 endpoint；其余五格继续，GPU6空闲。
当前source锁为`source_lock_wave_b_stdlib_json.json`。
2026-09-07 R0/R2完整1500 endpoint均PASS/0，Q_R冻结`UNRESOLVED`，原因是R1 endpoint缺失；
不以中途结果补齐。可用R2 injected ITT重抓5/64、2/64，recovered_clean为0/64、1/64。
权威结论为`wave_b_recovery_decision.json`；仅L三格继续训练，Q_R不阻塞下一阶段。

执行状态与 receipts 由
`scriptsFORhuman/v27/runtime_logs/v27_bilateral_hardening_20260905/` 路由，不将 heartbeat 写入 memory。

2026-09-07 Wave B两分支已关闭：L三格完成3000、R0/R2完成1500；R1维持STOP644。
L endpoint为DOMAIN_NOT_CONVERGED，冻结RECIPE_B=current；L1_S32 LEFT三层过门，RIGHT均未过门。
合并决策见wave_b_decision.json；Q_R=UNRESOLVED，不阻塞C。固定shadow estimator运行一次，
heldout friction/mass R²=0.15557/0.33127，仅支持模拟数据离线可辨识性，不证明actor或硬件能力。
Wave C将沿C+current执行六格scratch；全部checkpoint=null，终点6000。

Wave B第三个预授权本地commit为bbd98db。Wave C的SK_S211五batch/64env smoke为RUNTIME_PASS，
source=null、未加载policy、exit0；六格正式4096env/6000 batches与v27_watch_c已启动。
最终确认选种规则在policy数据前记录于wave_c_final_selection_contract.json：首个milestone过门，
并列最小seed，固定6000 endpoint确认；无合格seed或该endpoint缺失则NOT_RUN，无替换。

Wave C首轮六格均在policy执行前因远程default_environment.usd读取失败退出；失败记录保留。
同URL代理HTTP200后GPU4–7四格在*_r1新root重试一次，合同不变；GPU2/3两格暂候资源安排。
另一用户进程占用GPU0–3，未擅自停止。真实进程状态从active_attempts与receipts读取。

2026-09-09：SC203与SK211/212/213的*_r1已全部6000 PASS/0。Owner授权把剩余GPU0–3工作转到4–7并留两卡评估；SC201/202在GPU4/5的*_r1补跑，双侧eval队列改为6/7。配方、seed、预算无变化。GPU重分配与source逐字快照见wave_c_gpu_remap_20260909.json、source_snapshot_wave_c_gpu_remap_20260909.json，历史source lock不改写。

2026-09-09 Owner授权对已active格先评：以v27_watch_c_ready.py替换原Wave C全格等待watcher，
按完整cell和固定milestone就绪分批执行，GPU6/7双侧队列；part reducer仅为局部结果，
全milestone在其余格补齐后合并，endpoint使用完整历史重新结算typed outcomes。
首次step1000 part1为SC203/SK211/212/213，exact64/侧，未重跑训练或改变选种规则。
原watcher主动SIGTERM退出143是调度替换，不是实验失败；新tmux为v27_watch_c_ready。

2026-09-09晚：四格6000训练和六milestone评估均完成；SC201/202仍训练中，六格1000完整评估已合并。当前52/72 lanes exact64、integrity0；待评20 lanes取决于SC201/202后续checkpoint，未积压已有checkpoint。SC203 endpoint clean L/R=0/0，SK211=64/34、SK212=0/0、SK213=62/63；这些是四格局部结果，不提前结算Q_C。完整逐格读数见wave_c_step1000_full及step2000–6000_partial4_readout_20260909报告。

2026-09-10：v28共享源码改动触发v27 source锁，ready watcher在step2000 part2启动前退出。Owner授权隔离；独立.ai/runtime/v27_frozen_eval_20260910由bbd98db gr00t+scriptsFORhuman及v27冻结overlay构建，py/yaml只读。eval子进程cwd/PYTHONPATH均为隔离根；新v27_watch_c_isolated_r1已恢复GPU6/7双侧评估。初次隔离缺scriptsFORhuman.v21B在policy前失败，原artifact/manifest/receipt保留，补齐同提交依赖后新part2_r1双侧已进入policy evaluation。训练GPU4/5未重启；实验合同零改动。路由与证据见wave_c_isolation_20260910.json及dependency_repair记录。
