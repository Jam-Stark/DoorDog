---
name: pull-lr-full-stage
scope: pull branch current handle 左右镜像 randomization 下的 full Stage3–5 training/eval 与 Stage5/E7 goal qualification
status: active
last_updated: 2026-08-31 07:10 HKT
read_when:
  - 继续 full pull Stage3–5 的 n1024 retry、screen 或 held-out fixed-side/bilateral eval 前
  - 诊断稳定抓握后 LEFT 下压/解锁失败，或判断 bilateral Stage5/E7 是否达标时
source_of_truth:
  - logs_eval/a2_piper_pull_lr_full_stage/r1g_zero_r6an_summary.json
  - logs_eval/a2_piper_pull_lr_full_stage/r1g_zero_winner_summary.json
  - gr00t/rl/config/ablation/wbmanip/pull_lr_full_base.yaml
  - gr00t/rl/config/ablation/wbmanip/pull_lr_full_gate_a.yaml
  - gr00t/rl/config/ablation/wbmanip/pull_lr_full_gate_b.yaml
  - logs_eval/a2_piper_pull_lr_full_stage/r2c_screen_gate_a_s0_step025_evalseed1001_summary.json
  - logs_eval/a2_piper_pull_lr_full_stage/r2c_screen_gate_a_s1_step025_evalseed1001_summary.json
  - logs_eval/a2_piper_pull_lr_full_stage/r2c_screen_gate_b_s0_step025_evalseed1001_summary.json
  - logs_eval/a2_piper_pull_lr_full_stage/r2c_screen_gate_b_s1_step025_evalseed1001_summary.json
  - logs_eval/a2_piper_pull_lr_full_stage/r17_screen_gate_h_s0_step025_evalseed1001_summary.json
  - logs_eval/a2_piper_pull_lr_full_stage/r17_screen_gate_h_s1_step025_evalseed1001_summary.json
  - logs_eval/a2_piper_pull_lr_full_stage/r17_screen_gate_i_s0_step025_evalseed1001_summary.json
  - logs_eval/a2_piper_pull_lr_full_stage/r17_screen_gate_i_s1_step025_evalseed1001_summary.json
  - gr00t/rl/config/ablation/wbmanip/pull_lr_full_left_stage3_e3_snapshot.yaml
  - logs_rl/a2_piper_pull_lr_full_stage/h9_smoke5_load_gate_j_seed0/runner.log
  - scriptsFORhuman/pull_v2/PULL_V2_ROUND_REPORT.md
  - logs_eval/a2_piper_pull_lr_full_stage/r19_screen_gate_h_s0_step025_evalseed1001_summary.json
  - logs_eval/a2_piper_pull_lr_full_stage/r19_screen_gate_h_s1_step025_evalseed1001_summary.json
  - logs_eval/a2_piper_pull_lr_full_stage/r19_screen_gate_j_s0_step025_evalseed1001_summary.json
  - logs_eval/a2_piper_pull_lr_full_stage/r19_screen_gate_j_s1_step025_evalseed1001_summary.json
  - logs_eval/a2_piper_pull_lr_full_stage/r15_screen_gate_h_s0_step025_evalseed1001/left/eval/stage2_5_step_trace.json
  - logs_eval/a2_piper_pull_lr_full_stage/r15_screen_gate_h_s0_step025_evalseed1001/right/eval/stage2_5_step_trace.json
  - logs_eval/a2_piper_pull_lr_full_stage/r21_screen_gate_h_s0_step075_evalseed1001_summary.json
  - logs_eval/a2_piper_pull_lr_full_stage/r21_screen_gate_h_s1_step075_evalseed1001_summary.json
  - logs_eval/a2_piper_pull_lr_full_stage/r21_screen_gate_j_s0_step075_evalseed1001_summary.json
  - logs_eval/a2_piper_pull_lr_full_stage/r21_screen_gate_j_s1_step075_evalseed1001_summary.json
  - gr00t/rl/config/ablation/wbmanip/pull_lr_full_left_stage3_post_e3_adapter.yaml
  - logs_eval/a2_piper_pull_lr_full_stage/r26_rng_parent/right/eval/stage2_5_step_trace.json
  - logs_eval/a2_piper_pull_lr_full_stage/r26_rng_zero_fixed/right/eval/stage2_5_step_trace.json
  - logs_eval/a2_piper_pull_lr_full_stage/r30_screen_gate_k_s0_step075_evalseed1001_summary.json
  - logs_eval/a2_piper_pull_lr_full_stage/r30_screen_gate_k_s1_step075_evalseed1001_summary.json
  - logs_eval/a2_piper_pull_lr_full_stage/r30_screen_gate_k_s2_step075_evalseed1001_summary.json
  - logs_eval/a2_piper_pull_lr_full_stage/r30_screen_gate_k_s3_step075_evalseed1001_summary.json
  - logs_eval/a2_piper_pull_lr_full_stage/h10m_r12_probe16/left/eval/stage2_5_step_trace.json
  - logs_eval/a2_piper_pull_lr_full_stage/h10m_r12_probe16/left/eval/a2_hold_oracle_summary.json
  - logs_eval/a2_piper_pull_lr_full_stage/r36_screen_gate_m_s0_step075_evalseed1001_summary.json
  - logs_eval/a2_piper_pull_lr_full_stage/r36_screen_gate_m_s1_step075_evalseed1001_summary.json
  - logs_eval/a2_piper_pull_lr_full_stage/r36_screen_gate_m_s2_step075_evalseed1001_summary.json
  - logs_eval/a2_piper_pull_lr_full_stage/r36_screen_gate_m_s3_step075_evalseed1001_summary.json
  - gr00t/rl/config/ablation/wbmanip/pull_lr_full_left_stage3_taskspace.yaml
  - logs_eval/a2_piper_pull_lr_full_stage/h12_smoke5_eval4/left/eval/stage2_5_step_trace.json
  - gr00t/rl/config/ablation/wbmanip/pull_lr_full_bilateral_stage3_canonical.yaml
  - logs_eval/a2_piper_pull_lr_full_stage/h13_acq_parent_matched8/bilateral/eval/stage2_5_step_trace.json
  - logs_eval/a2_piper_pull_lr_full_stage/h13_acq_step5_8/bilateral/eval/stage2_5_step_trace.json
  - logs_eval/a2_piper_pull_lr_full_stage/h13_r9_tech8/bilateral/eval/stage2_5_step_trace.json
  - logs_eval/a2_piper_pull_lr_full_stage/r50_screen_gate_o_s0_step075_evalseed1001_summary.json
  - logs_eval/a2_piper_pull_lr_full_stage/r50_screen_gate_o_s1_step075_evalseed1001_summary.json
  - logs_eval/a2_piper_pull_lr_full_stage/r50_screen_gate_o_s2_step075_evalseed1001_summary.json
  - logs_eval/a2_piper_pull_lr_full_stage/r50_screen_gate_o_s3_step075_evalseed1001_summary.json
related_entries:
  - ../pull-lr-bilateral-grasp/description.md
  - ../pull-open-door-task/description.md
---

# Pull LR full stage

本 entry 记录当前 handle 左右镜像 randomization 下，从已完成的 Stage0–2 acquisition 向 full Stage3–5 goal qualification 的实验状态。当前仍为 `active`，尚无 bilateral full-goal 或 hardware 通过结论。

## Current evidence (2026-08-31 07:10 HKT)

- r1g fixed-side16、seed0、full gate-A/banks-off 的两个 summary 是当前 full-stage 证据边界。r6an L/R funnel K5,E2,E3,E4,E5,E6,E7 为 `2/11,2/11,1/11,0/10,0/10,0/0,0/0`；bilateral winner 为 `15/16,15/16,2/15,0/14,0/13,0/0,0/0`。
- bilateral winner 的 raw LEFT handle≥0.3 为 `11/16`，但 handle≥0.6/latch/E3 仅 `2/16`；RIGHT handle≥0.6/latch/E3 为 `15/16`。因此当前主要不对称是 LEFT Stage3 press/unlatch，不是 acquisition/E2；full goal 尚未达成。
- source/full config 已实现 side-canonical handle command（`handle_send_y=-door_open_lr*raw_y`）、gate A/B、banks off、full r6ap、LR `1e-4`、output actor、runner/reducer。此前 actor contract/artifact reducer 已修复，n1024 retry 已登记。
- 4096-env gate A/B 四个 runs 均精确达到 `2048 LEFT / 2048 RIGHT`，随后在 v6 staged-reset buffer 单次申请 `29.66 GiB` 时 OOM（当前 4×RTX3090、每卡 24 GB）；没有 actor/batch1，也没有 policy verdict。
- 首轮 n1024 四格均达到 exact `512/512`、strict-load output actor 与 iteration1–2，随后共同暴露 online staged snapshot 保留 donor `first_event_step/time`、在新 episode 时间基准下违反 dependency ordering。当前 fresh rebase retry 只把 snapshot 中已达事件的 step/time 归零，未改 event graph、policy 或 reward，尚无结果。
- event-time rebase 后四格均完成25/25、每格 `1,638,400` timesteps/`25,600` episodes并保存 step25。r3 fixed-side16 screen pooled：gate A LEFT K5/E2/E3/E4/E5=`32/32/6/0/0`、RIGHT=`31/31/27/25/24`；gate B LEFT=`31/30/4/0/0`、RIGHT=`30/30/30/29/27`。Gate B 只改善 RIGHT、损害 LEFT，已拒绝为主轴。
- H3 四seed screen：LEFT pooled64 K5/E2/E3/E4/E5=`59/59/4/0/0`、handle≥0.6/latch=`7/7`，低于 Gate-A LEFT pooled32 的 E3=`6`、handle/latch=`7/7`；RIGHT E5略升但acquisition下降。H3按 stopping condition 失败，不续batch。
- H4 使用 Gate-A seed0/1 step25 parent，只新增 raw LEFT+Stage3 gated、zero-init `Linear(135,6)` arm residual。carrier/RMS/std/base/gripper和RIGHT/非Stage3 mean冻结；smoke3完成1/1且23个original actor tensors逐项exact equal，optimizer actor侧仅residual weight/bias。H4四个正式cell已登记，尚无结果；base+arm variant保持 `NOT_RUN`。
- H4四seed screen：LEFT pooled64 K5/E2/E3/E4/E5=`62/62/18/0/0`、handle≥0.6/latch=`22/22`，说明窄residual能改变press概率，但seed2倒退且仍无任何LEFT E4；RIGHT pooled E5=`36/64`低于lineage-weighted Gate-A `48/64`。H4不promotion、不续batch；base+arm仍 `NOT_RUN`。
- H5从H4较好的seed0/3 parent继续，只在 raw LEFT Stage3 的 E3-latched current K-hold 下延续原 scale6 hinge income；RIGHT reward、actor gate与Stage3→4物理门不变。H5四cell已登记，尚无结果。
- H5四seed screen：LEFT pooled64 K5/E2/E3/E4/E5=`62/62/22/0/0`、handle≥0.6/latch=`31/31`；RIGHT逐H4 parent保持，但LEFT仍无E4。post-E3分析确认H5 historical-E3 hinge income主要落在已relock rows，H5按stopping condition关闭。
- H6保留并冻结每个H5 parent的carrier+arm6 residual，恢复Gate-A live-proof hinge reward，只新增 raw LEFT+Stage3+E3-latched gated、zero-init base planar3 residual。smoke3完成1/1，H5 parent25 keys和arm residual exact，optimizer actor侧仅base residual；H6四cell已登记，尚无结果。
- H6四seed screen：LEFT pooled64 K5/E2/E3/E4/E5=`60/58/15/0/0`、handle≥0.6/latch=`27/27`，0/4 parents出现E4；RIGHT E4/E5提高但LEFT全面低于H5。H6按stopping condition关闭。
- H7回到H5-s0 parent与live-proof reward，冻结其25 keys，新增raw LEFT Stage3 gated、zero-final `concat(current135,frozen LSTM hidden256)=391→16→9` SiLU adapter；显式 `desired_kl:null` 固定actor/critic LR `1e-4`。smoke完成1/1，parent25 exact、optimizer actor侧仅4个adapter tensors、LR fixed；H7四seed25-batch已登记，尚无结果。
- H7四seed screen：LEFT pooled64 K5/E2/E3/E4/E5=`64/64/43/0/0`、handle≥0.6/latch=`57/57`，press/E3稳定但valid-hold hinge max仅0.003–0.009 rad，0/4 seeds达到0.10 rad，故不续75并关闭H7。
- H8两组matched pairs已经完成。control seed0/1 的LEFT K5/E2/E3/E4/E5均为`16/16/10/0/0`，treatment seed0/1均为`16/16/9/0/0`；RIGHT各pair均为`15/15/14/12/7`。tangent reward确实在训练中激活，但没有产生任何LEFT E4且E3略降，按门槛关闭H8。
- H9回到H7 seed0/1 step25 parent、H7 live-proof reward与同一29-key actor，唯一改变是LEFT Stage3 reset curriculum：抑制普通E2→Stage3 entry snapshot，仅在post-physics最终E3 commit与slip更新后，用`new_E3 & Stage3 & LEFT & ~E4`保存同env状态；RIGHT保留原自动snapshot。加载LEFT Stage3 snapshot时强制验证E3 evidence与归零后的event step/time。256-env×5-batch smoke完成81920 timesteps，聚合日志capture=`55.1719`、loaded=`3.2188`、RIGHT manual=`0`且无validator错误；这是curriculum runtime证据，不是policy/E4证据。matched-pair结果尚未形成。
- 历史pull-v2同类成功方向在256 env×250/500 batch（4.096M/8.192M timesteps）仍可两个seed均E4=0，到batch750（12.288M）才出现10/16与6/16 E4。当前1024 env×25 batch仅1.6384M，因此H9采用25 interim→75 trend gate→必要时200正式E4门；batch25零E4不再单独构成因果拒绝。
- H9 batch25四格均完成1.6384M timesteps。control seed0/1 LEFT K5/E2/E3/E4/E5均=`16/16/10/0/0`；E3-snapshot treatment为`16/16/8/0/0`与`16/16/9/0/0`。RIGHT四格均=`15/15/14/12/7`，证明干预side-safe。seed1 treatment有1个episode在0.02–0.105rad band累计13 trace steps、max hinge 0.0288rad，seed0无趋势；按历史预算门将matched pairs保留optimizer/trainer/snapshot bank同步full-resume到global batch75。
- 独立mechanics分析定位了更窄的中介缺口：H7 seed0首次E3时LEFT/RIGHT的TCP→handle距离中位约`0.0762/0.0162m`、opening alignment约`0.571/0.964`、E3后连续双指接触约`1/308.5` steps、post-E3 hinge max中位约`0.00194/1.0129rad`。LEFT在Stage3 entry尚约`0.0435m/0.926`，说明退化发生在压把手到E3的约9 control steps内；H8 +X tangent reward未修复这一SE(3)偏离。
- H10内部裁决区分两类证据：live-handle SE(3) DLS若运行，只回答“修正pose-follow是否恢复contact/hinge”的oracle-assisted mechanics问题，不可promotion；正式policy候选才是冻结parent、仅post-E3激活的zero-final独立learned head。两者都只有在H9充分预算失败后才触发。
- H9 global batch75 screen：control seed0/1 LEFT K5/E2/E3/E4/E5=`16/16/8/0/0`与`16/16/10/0/0`；treatment=`16/16/10/0/0`与`16/16/7/0/0`。RIGHT四格仍=`15/15/14/12/7`。treatment pooled hinge≥0.02rad episode=`1`、control=`3`，四格均无≥0.105rad；H9没有产生paired中介改善，按门关闭且不续batch200。
- H10首轮四格虽完成75 batches，但其natural RIGHT funnel与parent不一致；checkpoint核对证明parent29仍exact。根因是新增`left_stage3_post_e3_gate_obs` group在`parse_observation`里即使noise scale0仍执行`torch.rand_like`，从而在gate激活前平移CUDA action-sampling RNG。该轮全部标记`INVALID/CONFOUNDED`，LEFT E3/E4结果不得引用。
- RNG-fixed H10不再增加obs group：用与parent相同的8-D gate+6-D stage调用形状，把E3写入parent actor未读取的IO slot，并以`torch.random.fork_rng()`隔离新增head的CPU/CUDA构造随机数。RIGHT parent/zero-head natural A/B达到10230/10230 trace rows完全对齐，policy/base/arm/gripper raw actions、stage、handle/latch/hinge和event均逐项exact、max diff0。固定版activation smoke也完成81920 timesteps，snapshot/load非零、RIGHT manual0、parent29 exact且新head4全更新；正式四格重跑尚无结果。
- RNG-fixed H10四格正式重跑均完成75 batches。parent0 primary/replica LEFT E3=`10/16`、parent1均=`7/16`，与各自H9 parent pre-E3结果exact；RIGHT四格均parent-exact=`15/15/14/12/7`。然而E3后continuous bilateral-contact中位仍为1 step，四格max hinge仅`0.03798/0.02521/0.02854/0.00580rad`，无episode达到0.10/E4。故post-E3 parameter separation被有效否定。
- 当前转入H10-M：复用现有DifferentialIK/hold-oracle机制做fixed-LEFT Stage3 live-handle SE(3) causal probe，严格标记oracle-assisted且不可promotion；它只判断恢复pose-follow是否能延长contact并产生≥0.10rad hinge，为下一learned-policy结构提供因果依据。
- H10-M最终运行16 episodes并生成完整trace，DLS capture/correction实际激活1600 rows，raw condition只作telemetry且correction/limit/raw均受硬门。realized position/orientation residual中位仍`0.07695m/0.62983rad`，每步bounded pose request打满`0.008m/0.08rad`，16/16 outcome=`PUSH_TIMEOUT`；E3=`8/16`、hinge max=`0.00712rad`、E4=0。它没有实现预注册pose中介，因此判`NOT_ADMITTED`，不能据此否定pose-follow假说。
- H10-M还显示简单oracle residual会持续与policy arm相抵消；下一H11不覆盖action，而让H7 nonlinear adapter从Stage3 entry起直接优化raw LEFT coupled-SE(3) pose quality。256-env×5-batch smoke完成81920 timesteps，reward从batch3起非零，carrier25 exact、adapter4全更新、optimizer仅adapter4+critic16；正式四格尚无结果。
- H11四格正式训练均完成75 batches，reward持续非零。parent0 primary/replica LEFT E3=`11/16,9/16`，parent1=`8/16,9/16`，但first-E3 distance仍约`0.0735–0.0771m`、opening alignment约`0.532–0.588`、contact dwell中位`1/1/1/2` steps；四格max hinge=`0.01974/0.00367/0.00360/0.01505rad`且E4全0。RIGHT均parent-exact=`15/15/14/12/7`。coupled reward没有进入pose/hinge中介，H11关闭。
- H12选择structured action decomposition：冻结parent29并新增同规模zero-final`391→16→6` head，仅raw LEFT Stage3输出normalized handle-frame translation/axis-angle；固定DLS executor把policy自主选择的twist转为joint raw并完全replace legacy arm slice。它不读取grasp/E3/E4目标、不用teacher或eval oracle，训练/eval合同一致，base/gripper/RIGHT/非Stage3保持parent。
- H12 256-env×5-batch smoke完成81920 timesteps，parent29 exact、新taskspace head4全更新、optimizer仅新head4+critic16。smoke checkpoint fixed-LEFT4 natural eval有1649 active/nonzero rows，twist realization relative residualmedian=`0.4421`、p90=`0.6590`，converted joint raw finite且无reject；按预注册median≤0.5通过技术门，正式四格尚无结果。
- Owner在H12刚启动batch1–2时选择更clean方案：保留双侧Stage0–2 acquisition、重新初始化左右canonical共享Stage3 controller。H12四格已优雅停止且无step25 checkpoint，禁止把短跑写成policy evidence。
- H13唯一parent为bilateral Stage0–2 winner seed2 step250（fixed LEFT/RIGHT strict K5均125/128）；冻结其23 actor tensors与RMS/std，fresh shared`58→256→256→9` head不读取parent memory或side bit。58-D feature从真实sorted 135-D layout构造，side one-hot实际为112/113、stage为127:133；head只在Stage3接管base-planar3+arm-twist6，pitch/roll/gripper保持parent，Stage0–2/4+回到parent。
- H13 action采用实际FrameTransformer handle frame本身作为canonical twist frame，不再做重复LR reflection；base仍按mirror decanonical。bilateral专用scale为0.004m/0.04rad、raw cap12。256-env×5 smoke完成81920 timesteps，parent23 exact、新head6更新、optimizer仅head6+critic16，L/R active约115/112。matched full-state completion2 A/B达到567/567 rows policy/base/arm/gripper/stage/event bitwise exact；step5 bilateral executor residual medianLEFT=`0.00142`、RIGHT=`0.00715`。H13四seed正式训练尚无结果。
- H13首轮四seed正式训练分别在约batch3/1/2/7共同触发task-space converted raw admission：j6约`-13.50`至`-14.82`，而finite、joint-limit、delta均valid。四格均无step25 checkpoint，故只记infrastructure failure。r1保持所有policy/reward/scale不变，仅把bilateral task-space raw经验cap从12提高到15；delta clip15与joint-limit硬门仍在，尚无r1结果。
- H13 r1四seed又在约batch3/1/2/7以同一形式触发raw cap15，converted raw约`-15.50`至`-17.99`，但每次finite、最终delta与joint-limit仍valid。raw幅值只是旧joint cumulative buffer到新task-space absolute target的一步坐标转换，独立cap与最终plant validity重复。r2删除bilateral raw幅值门，只保留finite、delta clip15和joint-limit；LEFT-only旧实验合同不变，尚无r2结果。
- H13 r2四seed均完成75 batches。fixed-side16 LEFT E2/E3=`16/(9,8,8,7)`，RIGHT=`16/(3,3,5,6)`，两侧E4仍0。关键中介已与所有LEFT-specialist路线不同：LEFT first-E3 distance降至`0.0529–0.0591m`、opening alignment升至`0.8496–0.8715`、continuous contact中位`104–166` steps；RIGHT distance约`0.012m`、alignment`0.917–0.960`、dwell`147–400`。LEFT/RIGHT max hinge分别`0.0276–0.0543/0.0447–0.0708rad`，两侧均从噪声盆抬升但未到0.105。因clean双侧pose/contact/hinge趋势成立，四seed保留full state续到global200，尚无结果。

## Evidence boundary

以上是 `INSPECTED`/`RUNTIME_PASS` 的实现与运行事实；训练结果仅按已生成 summary 记录，未将 infrastructure failure 推断为 policy 失败。当前 completion 为 `NOT_SUPPORTED/NOT_RUN`：bilateral E7/goal 与 hardware 均未完成或未运行。旧条目中关于 “P not started” 的表述与 pull-v6.1 的 “P population integration was not started” 语义容易混淆；本 entry 只保留当前 H9 与 held-out qualification TODO，不修改历史条目。
