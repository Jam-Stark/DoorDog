---
name: pull-lr-full-stage
scope: pull branch current handle 左右镜像 randomization 下的 full Stage3–5 training/eval 与 Stage5/E7 goal qualification
status: active
last_updated: 2026-08-30 20:32 HKT
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
related_entries:
  - ../pull-lr-bilateral-grasp/description.md
  - ../pull-open-door-task/description.md
---

# Pull LR full stage

本 entry 记录当前 handle 左右镜像 randomization 下，从已完成的 Stage0–2 acquisition 向 full Stage3–5 goal qualification 的实验状态。当前仍为 `active`，尚无 bilateral full-goal 或 hardware 通过结论。

## Current evidence (2026-08-30 20:32 HKT)

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

## Evidence boundary

以上是 `INSPECTED`/`RUNTIME_PASS` 的实现与运行事实；训练结果仅按已生成 summary 记录，未将 infrastructure failure 推断为 policy 失败。当前 completion 为 `NOT_SUPPORTED/NOT_RUN`：bilateral E7/goal 与 hardware 均未完成或未运行。旧条目中关于 “P not started” 的表述与 pull-v6.1 的 “P population integration was not started” 语义容易混淆；本 entry 只保留当前 H9 与 held-out qualification TODO，不修改历史条目。
