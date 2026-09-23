# v29 baseline worker决策日志

Worker任务为01a0b592-48e3-7ad0-9263-4cb605862ed6，已通过queue向planner登记；入队不代表已验收或批准。后续条目由worker维护，planner决定仍引用主D日志。

每条使用V29-W001、V29-W002等连续编号，保留历史，不把提案覆盖成已批准。

```text
## V29-Wxxx：具体决定
时间：YYYY-MM-DD HH:MM HKT
决策方：WORKER
worker thread ID：实际ID
候选/运行：Cxxx / 实际run
依据：Owner/planner决定编号、source/runtime事实
决定：本次实际选择或请求planner裁定的提案
影响：文件/资产/配置/运行及相关行为
状态：PROPOSED / DECIDED_IN_SCOPE / IMPLEMENTED / SUPERSEDED
验证：真实证据路径与结论边界
通信：发送给planner的事件/消息文件及其回复引用
```

既定参数与语义内的实现细节可以自主决定；变更方案、实际训练配方/预算和开训请求交planner。收到planner批准时引用其D编号/消息，不将批准改标为worker独立决定。

## V29-W001：完整baseline实现分工与统一接线

时间：2026-09-19 01:35 HKT
决策方：WORKER；worker thread ID：01a0b592-48e3-7ad0-9263-4cb605862ed6
候选：C001准备中；运行：无。
依据：Owner目标文件及V29-D029–D031，当前A2_Piper工作区已有基础改动，B01/B04/B05尚待生产实现。
决定：在当前工作区继续，不commit/push；B05 worker独占env_rand/door.py与handle_v29.py，B01/B04 worker独占scenario_cfg/isaacsim.py与door_v29_parameters.py，Main负责door_open_a2_base.py与v29 yaml及整合。已有team_state登记写入边界；无GPU lease/运行。统一a2_v29_baseline_enabled选择新资产/目标/动力学链。
影响：v29目标由生成器给proper frame；消费端identity offset及局部-Z .10m pregrasp。native摩擦复用既有backend，首次写入前安装本门metadata参数，reset保持本门profile；hinge target单独设置为已批准-10°，不改handle effort/target。
状态：DECIDED_IN_SCOPE / IMPLEMENTING。尚无运行验证或候选冻结。
验证：已trace本机IsaacLab Articulation friction setter、position target和reset；reset不清position target。官方接口核对：https://isaac-sim.github.io/IsaacLab/main/source/api/lab/isaaclab.assets.html 。实现后按planner协调执行有界运行验证。
通信：WORKER_READY queue message 01a0b593-5b34-7ba2-a658-764fb52043f6已入队，已请求planner绑定和协调GPU0验证时段，未收到TRAIN_APPROVED。

## V29-W002：真实GPU碰撞表示与首个接线运行

时间：2026-09-19 01:57 HKT
决策方：WORKER；worker thread ID：01a0b592-48e3-7ad0-9263-4cb605862ed6
候选/运行：C001准备 / v29-c001-smoke64-a1
依据：D029全部域、D032有界预算、D033明确允许先64env接线；本机PhysX convex默认hullVertexLimit64与minThickness1mm。
已执行决定：B05端帽分6个polar带，F2截面28顶点；对超过GPU64限制的曲杆凸体进行保持外表面的平面分割，显式hullVertexLimit64/minThickness0避免隐式形状简化/加厚。没有缩小参数域或换collision模型。固定每hook名义质量及分割前后的质量矩一致（子worker代表两例最大差4.66e−21）；实际GPU导入待本运行。Main另将deterministic重建按metadata v29字段分派，可用空模板恢复新资产；v29模板缺必需新字段仍明确失败，不迁移旧metadata。
影响：env_rand/handle_v29.py、door.py；new metadata/domain、family、G及奖励语义不变。
状态：IMPLEMENTED；首个runtime RUNNING，尚无runtime或policy质量结论。
运行：按D033_SMOKE64_APPROVAL.json原命令，在已确认空闲的GPU0启动64env/1batch，未增加尚待核对callback。独立tmux jam-v29-c001-smoke64-a1，receipt .ai/runtime/runs/v29-c001-smoke64-a1/RUN_RECEIPT.json，原始log scriptsFORhuman/v29/candidates/C001/ppo_smoke.log。已保存316文件输入快照到C001/smoke_input_snapshot；一次启动检查确认进程运行、graphics表GPU0 Active。逻辑等待截止02:01:40 HKT，由supervisor wait同一receipt承接。
通信：VALIDATION_COMMANDS_READY queue 01a0b5a4-7f77-7630-8a8d-c761ea07193e；VALIDATION_STARTED queue 01a0b5a9-d0e4-7070-a3b4-8cf10792fcea；reference动作补充queue 01a0b5aa-4d98-75d3-a78e-62c75a24e8ef。自定义probe/采证callback仍等planner明确回复；无TRAIN_APPROVED。

## V29-W003：运行暴露的问题与同域修正

时间：2026-09-19 02:28 HKT
决策方：WORKER；worker thread ID：01a0b592-48e3-7ad0-9263-4cb605862ed6
候选：C001 preparation；所有正式开训仍未批准。

- D033 smoke-a1的实际USD quatd/float冲突已改为double writer；a2按原命令fresh suffix完成1batch/4096timesteps、完整checkpoint，证据smoke_a2_readout.json，plannerD037保留其接线范围。
- asset-a1有实际PNG但部分plain不可见；asset-a2仅修正静态几何采证harness（不逐视图推进physics，渲染后强制刷新RGB），当前atlas所有28结构可见，参数case与a1逐值一致。48.610s、68PNG，未据静态视图排除动态问题。生产geometry没改。
- reference-a1只留下两步但Kit在finally immediate shutdown将exception变成exit0；修正probe顶层异常边界：先写traceback、显式失败退出，只有成功才close。a2据此真实exit1，定位pregrasp step2的17个LEFT arm_j3目标略超过原0上限；数据reference_contact_a2/invalid_dls_target.json。没有裁剪或改变joint域。
- D034/D036要求的原参数真实读回可保留：native质量/friction/drive/M/q0、G、自然root及133/138观察维度见initial_runtime_readback.json；不把这些部分证据升级为reference闭合/动力学通过。
- 按D034记录full-loader已有facts，新增v29_checkpoint_load.json纯读导出；plannerD040核准并登记WRITE_SET。scratch smoke未走loader，原接线证据仍适用。

请求planner裁定：仅probe用SciPy已有BVLS求带native joint bounds的DLS，原delta/阻尼/fixture/域不变。具体公式与代码bounded_dls_proposal.md；状态PROPOSED（尚未运行），不把本提案改写成worker已获准的控制协议。

当前运行：v29-c001-reload-a1，D034批准的实际a2 checkpoint full reload+64env首自然回合，receipt在.ai/runtime/runs对应目录；观察等待600s或提前完成/失败。仍无scale或正式训练运行。

## V29-W004 — Execute D046 target integration diagnostic and conditional full contact

2026-09-19T03:12:00+08:00. Worker01a0b592-48e3-7ad0-9263-4cb605862ed6. PlannerD046 approves persistent native-bounded drive targets, two F0 diagnostic cases and conditional34case contact. Worker executed exact two-case command;550steps/exit0/80.714s, pregrasp<0.06mm and both fingers contact both handles. Read candidates/C001/reference_control2_a1_readout.json. Therefore launched exactD046 full34case command in namedtmux jam-v29-c001-contact34-a1, GPU0, ETA240s. Independent dynamics/reset facts retained; no production control/domain changes or formal training. Planner notified queue01a0b5ee-43d9-7172-a8f7-999181d0ef4e.

## V29-W005 — Scale result, terminal capture, and staged fixture correction

2026-09-19. Worker 01a0b592-48e3-7ad0-9263-4cb605862ed6. Scale command executed under D032/D034 after D048 accepted contact, explicitly retained by D049. At40min, reported actual CPU-active initialization and obtained D051 extension. Run completed3647.832s, one PPO batch262144timesteps/23.00s, actualcheckpoint and all4096 fixedphysicalparameters read back. This is wiring/scale evidence, not policyquality. See candidates/C001/scale4096_readout.json.

Actual normal-budget trainer stop bypasses on_train_end. Moved only v29 passive terminal capture to the existing on_step_end stop flag; no productiontraining logic change. Existing final firstbatchreadback retained without rerun; new terminalevent wiring awaits actual execution.

D050 staged a1 failed afterthree ticks: all34 remainedStage0. Pendingnaturalreset writeback overwrote the manually placedfixture. Source and initial/final roots establish overwrite, not drift or actionwarp. Implemented one realnaturalflushstep before originalfixture/three steps, and final publicreset_all to apply selectedrobotstates aswellasdoor. No manualflag/bank/stage changes. Submitted exactfresh a2 command and sequence change for planner confirmation; not yet run.

## V29-W006 — Freeze C001 and submit implementation for planner acceptance

2026-09-19. Worker 01a0b592-48e3-7ad0-9263-4cb605862ed6. D053 staged a2 completed267.896s: all34 real stage1 snapshots and restores; fixed metadata/native parameters match, and recorded restored roots/joints match the production snapshot. No bank, stage or reset flags were manually populated. B02 inherited target/effort semantics and B06 proxy-resolved USD visibility/collision inventory are now documented.

Froze candidates/C001/CANDIDATE.json and its evidence index,320 source/config/asset snapshot files, and selected text changes relative to HEAD. Sent IMPLEMENTATION_READY through queue01a0b652-5a87-7f93-9f3a-9e7691f1dd09. Completed bounded validation5685.959s, no active v29 run. Formal proposal remains unapproved: GPU0,seed291,4096env,6000batches,save100; provisional39.34h based on one measured batch, requested48h budget and final64env natural evaluation. Planner owns acceptance and TRAIN_APPROVED. New passive terminal capture event is statically traced but not falsely labelled runtime-proved. Further material fixes require a new candidate; C001 inputs remain stable.

## V29-W007 — Focused successor for D056

2026-09-19. Worker 01a0b592-48e3-7ad0-9263-4cb605862ed6. Planner D056 accepts C001 item scopes with one missing directed Stage5 runtime sample. C001 remains frozen. Assigned runtime_route only a new small Stage5 reward fixture probe, without production edits or GPU execution; exact command will be submitted before launch. C002 prospective train/eval proposals now use the D056 canonical logs_rl/logs_eval locations and co-located runtime capture. Recipe and48h/20min budgets remain unapproved proposals. Unrelated accepted evidence is retained without reruns.

## V29-W008 — Directed Stage5 completion and C002 freeze

2026-09-18T21:39:02.287660+00:00. Worker01a0b592-48e3-7ad0-9263-4cb605862ed6. D057a1 failed output forwarding; D058a2 failed duplicate fullcallback lifecycle update. Both explicit failures retained. D059a3 completed123.125s with actual4reward cases; readout candidates/C002/stage5_a3_readout.json. Production inputs unchanged versus all320 C001snapshotfiles. C002 frozen as layered snapshot plus new probe and focused runtime evidence; prior accepted evidence retained. Actual cumulativevalidation5895.656s; no active GPU. Formal proposals remain pending planner approval.

## V29-W009 — D060 formal training launch

TRAIN_STARTED
worker_thread=01a0b592-48e3-7ad0-9263-4cb605862ed6 candidate=C002 decision=D060
Exact approvedargv launched; physicalGPU0 idleverified/GPU-f593e489-014b-eed5-4331-b01447615b6e.
Receipt=/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v29-c002-push-seed291-train/RUN_RECEIPT.json
Binding=/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v29-c002-push-seed291-train/D060_BINDING.json
Started=2026-09-18T21:47:43.110976+00:00 provisionalETA=2026-09-20T13:08:07.942683+00:00 hard48hdeadline=2026-09-20T21:47:43.110976+00:00.
Namedtmux=jam-v29-c002-push-seed291-train; output=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/a2_piper_full_stage_a2_base/base_v29/push_baseline_C002_seed291. One initializationevent then actual1000/3000/6000 milestones, earlyfailure/completion; no periodicLLMlogpoll. Final64naturaleval preapproved byD060 conditional onactual6000completion/exactcheckpoint.


## V29-W010 — Actual formal batch1000

V29_BATCH1000_OBSERVED worker_thread=01a0b592-48e3-7ad0-9263-4cb605862ed6 candidate=C002 D060/D061. Actual saved checkpoint CPU-read global_step1000; policy/value tensors finite. Mean reward61.54958 entropy8.93851; stage2 active0.6629; both-contact/grasp-complete0.0000 rounded; left historical maxstage3 with one stage3 snapshot, right2; both goals0. No policy success claim. Loss NOT_OBSERVED per D061. Three penalty-driver NaNs are source intentional zero-sample logging, not loss. Readout=/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v29-c002-push-seed291-train/batch1000_readout.json; exact console=/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v29-c002-push-seed291-train/batch1000_console.txt. Iteration mean22.85513s last10022.802s; wall init-to1000 /999=24.12217s includes overhead. GPU916 samples peak22845MiB, median utilization21percent. Next persisted logical wait batch3000 or terminal/planner/budget; until_epoch=1789848681.8935745 HKT=2026-09-20T04:11:21.893574+08:00 from2000 remaining*actualwall*1.1 allowance. Estimated6000 epoch=1789916223.9813225; hard deadline1789940863.1109755 unchanged. Continue exact frozen recipe and conditional final64 natural eval, no restart/tuning. Please record milestone review.


## V29-W011 — Actual formal batch3000

V29_BATCH3000_OBSERVED worker_thread=01a0b592-48e3-7ad0-9263-4cb605862ed6 candidate=C002 D060/D061/D063. Actual saved checkpoint CPU-read global_step3000; policy/value tensors finite. Readout=/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v29-c002-push-seed291-train/batch3000_readout.json exact console=/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v29-c002-push-seed291-train/batch3000_console.txt. Mean reward109.80628 entropy10.64041 stage2active0.7057 stage2bothcontact0.4098 graspcomplete0.0001 stage3active0.0462; both sides historical maxstage3 and thousands stage3 snapshots, no stage4/5 snapshot and goalcount0. These staged training metrics are not final natural evaluation or reliable whole-task success. Loss remains NOT_OBSERVED. Recent2000 iterations mean24.70518s last10025.2487s; actual milestone wall26.31348s/batch. Sampled GPU interval1747 samples max24079MiB median26percent. Unchanged frozen recipe, no restart/tuning/newprobe. Next same run event batch6000/terminal/budget; expected6000 2026-09-21T01:59:40.494262+08:00 epoch1789927180.4942615; decision wait 2026-09-21T04:11:14.537297+08:00 epoch1789935074.5372965 (actual recent2000 wall pace,3000remaining plus10percent). Harddeadline1789940863.1109755 unchanged, estimated margin3.80h. Will wait actualterminal and exact6000 checkpoint before D060 final64 natural eval. Please record milestone review.


## V29-W012 — Final training/evaluation delivery

Worker thread: 01a0b592-48e3-7ad0-9263-4cb605862ed6. Authority: D060, with D061 loss-observability exception and D066 communication policy. No recipe/source/assets changed, restart, extra seed, or other GPU used.

Training completed exit0 at 2026-09-21 03:15:17 HKT, elapsed163653.914s (45.4594h), within172800s budget. Exact model_step_006000.pt CPU-read global_step6000; all policy/value tensors finite. Runtime end capture actually executed at6000,4096 env, metadata identical to begin. Final logged mean reward93.26352, entropy12.92680; LEFT historical max5, RIGHT3, both logged goal counts0. These training aggregates include staged reset; they are not natural success rates. Loss remains NOT_OBSERVED under D061, no whole-run numerical-stability claim.

D060 exact final evaluation ran once, serial GPU0, at03:17:09–03:29:12 HKT, exit0 after723.228s (under1200s). Actual full loader restored actor strictly (including RMS), value strictly, optimizer, scheduler and trainer step6000. Environment loader dispatch followed by natural reset; not exact physical/staged episode restoration.

64 first natural episodes /64 unique env IDs,32 per side;0 goals. LEFT max-stage counts: Stage2=2,Stage4=27,Stage5=3. RIGHT: Stage2=32. All64 stage_overtime; episode lengths827×34,1129×27,1430×3. Six LEFT crossing-while-holding observations and ten LEFT release observations are separate descriptive events, not goals. The side difference has no isolated causal explanation in this run.

Actual evaluated height0.900659–1.199442m, mass33.9657–158.6098kg; all six mass×closer combinations occurred5–6 times per side. Natural exports do not include family labels/max-opening values, so no actual per-family outcome claim; actual4096 training full-family coverage is in prior initialization evidence. Raw1.34GB stage2_5 trace retained; not expanded into an unsolicited diagnostic study.

Evidence:
- Training receipt: /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v29-c002-push-seed291-train/RUN_RECEIPT.json
- Training readout and actual terminal runtime capture reference: /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v29-c002-push-seed291-train/final_train_readout.json
- Final training console: /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v29-c002-push-seed291-train/batch6000_console.txt
- Evaluation receipt: /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v29-c002-push-seed291-natural-final/RUN_RECEIPT.json
- Evaluation readout, full-load facts and raw-file pointers: /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v29-c002-push-seed291-natural-final/final_eval_readout.json

Requested planner decision: explicitly close implementation and training/evaluation delivery acceptance, distinguishing successful execution from observed0/64 policy success. No further run or tuning proposed. GPU0 execution is finished; release lease under planner authority. Please publish the final decision via shared STATE/file as D062/D066; no routine acknowledgement needed.



## V29-W013 — Owner授权同配方续训至8000及7000/8000自然评估

2026-09-21 HKT。决策角色：Owner直接授权；worker执行与监督，thread=01a0b592-48e3-7ad0-9263-4cb605862ed6。D072已关闭原6000交付；本次是新的明确授权，覆盖旧“无追加运行授权”状态。

Owner原指令：
1. 保留当前配方，resume到累计8000 iteration，用于回答同一配方是否训练不足；不同时改奖励或动作接口。
2. 累计7000、8000各做相同设置64个自然首回合；重点看LEFT goal是否出现并增加、RIGHT是否突破Stage2并到Stage4，不用reward或训练阶段占比替代。
3. 自然指标持续改善后再考虑延长；本次不自动越过8000。

已执行：单次直接字节比较320份生产输入与C002基础冻结快照一致。生产reward/action/assets无改动，含B08原行为仍保留。本次只新增控制用callback和运行协调脚本：7000保存完成并CUDA同步后暂停同一训练PID，GPU0串行eval7000，成功后原地继续；8000正常结束后eval8000。训练暂停期间保留其VRAM及sim/staged bank，eval另进程。初次6000 full-resume仍按现有loader恢复model/RMS/value/optimizer/scheduler/trainer后naturalreset，不能声称逐比特物理续接。

实际启动GPU0，seed291/4096，累计max_steps8000（恢复global6000后新增2000更新）；本机DefaultFlowCallback按global_step>=state.max_steps停止，所以不能把num_total_batches写2000。constant LR保持。原save100保留，最终目标model_step_008000.pt。开始2026-09-21T11:01:01.743274+08:00；初始化决策2026-09-21T12:06:01.743274+08:00；续训含7000eval预计2026-09-22T03:57:41.743274+08:00，worker操作性20h上限2026-09-22T07:01:01.743274+08:00。每次eval沿用原1200s上限。ETA基于原后3000实际wall约27.8s/batch及3900s初始化、900s评估。loss仍NOT_OBSERVED，分别报告checkpoint有限性。

实际receipt：/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v29-c002-resume8000-seed291/RUN_RECEIPT.json
精确命令/评估合同：/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/v29_resume8000/OWNER_AUTHORIZED_PLAN.json
独立tmux：jam-v29-c002-resume8000-seed291；v29-c002-resume8000-coordinator。GPU租约v29_baseline_resume8000已取得。只用GPU0，不改其他任务资源，无Git commit/push。按实际初始化/7000自然结果/8000自然结果持久化事件等待，不周期唤醒读日志。



## V29-W014 — 累计7000自然评估与原进程继续

V29_RESUME7000_NATURAL_MILESTONE worker_thread=01a0b592-48e3-7ad0-9263-4cb605862ed6 C002 same recipe/GPU0 Owner authorization W013. Actual eval7000 exit0 in720.633s;64 unique first natural episodes/full exact7000 loader. LEFT goal0/32→31/32, all32 maxStage5. RIGHT31/32 maxStage3 and1Stage2; Stage4+ still0/32. Overall31complete/33stage_overtime. Six available per-env door fields exactly equal6000; no family-label attribution. Actual same trainer PID3055669 paused at7000 then resumed aftereval; no second trainer restart or recipe change. Evidence /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/v29_resume8000/milestone7000_readout.json and /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/v29_resume8000/eval7000_completed.json. Continue already authorized8000; no furtherextension. Measured6001→7000 wall27.703256s/batch; final8000eval ETA2026-09-22 03:55:47HKT, sameeventwaitdeadline04:46:58HKT epoch1790023618.2716725; originaltrain20h ceiling07:01:01 unchanged. This supports substantialLEFT improvement from addedtraining and genuineRIGHTStage2breakthrough, not yetRIGHTStage4 or sustainedtrend over7000→8000. Please retain in mainlog; no routineACK needed.


## V29-W015 — 累计8000完成，左右自然首回合64/64成功

2026-09-22 03:55 HKT。Owner授权的GPU0累计6000→8000训练及7000/8000两次自然评估已完成。生产配方不变，未引入B08修复。

| 累计iteration | LEFT goal | RIGHT超过Stage2 | RIGHT到Stage4+ | RIGHT goal | 总goal |
| --- | --- | --- | --- | --- | --- |
| 6000 | 0/32 | 0/32 | 0/32 | 0/32 | 0/64 |
| 7000 | 31/32 | 31/32 | 0/32 | 0/32 | 31/64 |
| 8000 | 32/32 | 32/32 | 32/32 | 32/32 | 64/64 |

三个checkpoint均为seed291、64个唯一env的自然首回合。六个已导出的门参数逐env与6000一致；未导出family及最大开角，不能据此声称各family分别验证。8000全部maxStage5、终止原因为complete；episode长度431–982步，均值654.40625。terminal diagnostics的staged_load_count_total全部0，结果不是staged起点成功率。

7000→8000自然指标继续改善，尤其RIGHT从31例Stage3、1例Stage2到32例完整成功。这支持当前配方在6000时尚未达到本次自然评估的最终表现；单次seed291有限样本不等于跨seed成功率，也不隔离具体机制成因。

训练实际终止于2026-09-22 03:42:35 HKT，exit0；包含初始化及7000暂停评估的wall为60094.097s（16.693h）。实际end capture为global_step8000、4096env。8000 full loader实际严格加载actor/RMS、value及optimizer/scheduler/trainer，global_step8000；一次CPU读回actor20/value19个tensor全部finite，不能代替未观测的PPO loss。最终eval于03:52:55 HKT结束，619.306s、exit0。

训练与评估进程均结束，GPU0进程查询为空；未启动8000以后训练。planner最终交付确认待处理，队列入队不等于接受。

证据：
- [汇总与逐侧计数](final8000_readout.json)
- [最终checkpoint有限性](final_checkpoint_readout.json)
- [8000实际loader及评估事件](eval8000_completed.json)
- [原始逐env记录](/home/baoquanc/workspace/DoorDog-A2_Piper/logs_eval/base_v29/push_baseline_C002_seed291/natural_resume_8000/a2_v14_per_env_records.json)
- [原始metrics](/home/baoquanc/workspace/DoorDog-A2_Piper/logs_eval/base_v29/push_baseline_C002_seed291/natural_resume_8000/metrics_eval.json)
- [8000 checkpoint](/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/a2_piper_full_stage_a2_base/base_v29/push_baseline_C002_seed291_resume8000/model_step_008000.pt)

下一决定：自然指标已持续改善，但本次64例达到上限，本轮没有自动延长授权；若目标是确认泛化，独立seed自然评估比单凭此64例继续增加训练更能回答剩余问题。任何新运行由Owner决定。
