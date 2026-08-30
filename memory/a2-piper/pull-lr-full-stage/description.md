---
name: pull-lr-full-stage
scope: pull branch current handle 左右镜像 randomization 下的 full Stage3–5 training/eval 与 Stage5/E7 goal qualification
status: active
last_updated: 2026-08-30 14:35 HKT
read_when:
  - 继续 full pull Stage3–5 的 n1024 retry、screen 或 held-out fixed-side/bilateral eval 前
  - 诊断稳定抓握后 LEFT 下压/解锁失败，或判断 bilateral Stage5/E7 是否达标时
source_of_truth:
  - logs_eval/a2_piper_pull_lr_full_stage/r1g_zero_r6an_summary.json
  - logs_eval/a2_piper_pull_lr_full_stage/r1g_zero_winner_summary.json
  - gr00t/rl/config/ablation/wbmanip/pull_lr_full_base.yaml
  - gr00t/rl/config/ablation/wbmanip/pull_lr_full_gate_a.yaml
  - gr00t/rl/config/ablation/wbmanip/pull_lr_full_gate_b.yaml
related_entries:
  - ../pull-lr-bilateral-grasp/description.md
  - ../pull-open-door-task/description.md
---

# Pull LR full stage

本 entry 记录当前 handle 左右镜像 randomization 下，从已完成的 Stage0–2 acquisition 向 full Stage3–5 goal qualification 的实验状态。当前仍为 `active`，尚无 bilateral full-goal 或 hardware 通过结论。

## Current evidence (2026-08-30 14:23 HKT)

- r1g fixed-side16、seed0、full gate-A/banks-off 的两个 summary 是当前 full-stage 证据边界。r6an L/R funnel K5,E2,E3,E4,E5,E6,E7 为 `2/11,2/11,1/11,0/10,0/10,0/0,0/0`；bilateral winner 为 `15/16,15/16,2/15,0/14,0/13,0/0,0/0`。
- bilateral winner 的 raw LEFT handle≥0.3 为 `11/16`，但 handle≥0.6/latch/E3 仅 `2/16`；RIGHT handle≥0.6/latch/E3 为 `15/16`。因此当前主要不对称是 LEFT Stage3 press/unlatch，不是 acquisition/E2；full goal 尚未达成。
- source/full config 已实现 side-canonical handle command（`handle_send_y=-door_open_lr*raw_y`）、gate A/B、banks off、full r6ap、LR `1e-4`、output actor、runner/reducer。此前 actor contract/artifact reducer 已修复，n1024 retry 已登记。
- 4096-env gate A/B 四个 runs 均精确达到 `2048 LEFT / 2048 RIGHT`，随后在 v6 staged-reset buffer 单次申请 `29.66 GiB` 时 OOM（当前 4×RTX3090、每卡 24 GB）；没有 actor/batch1，也没有 policy verdict。
- 首轮 n1024 四格均达到 exact `512/512`、strict-load output actor 与 iteration1–2，随后共同暴露 online staged snapshot 保留 donor `first_event_step/time`、在新 episode 时间基准下违反 dependency ordering。当前 fresh rebase retry 只把 snapshot 中已达事件的 step/time 归零，未改 event graph、policy 或 reward，尚无结果。

## Evidence boundary

以上是 `INSPECTED`/`RUNTIME_PASS` 的实现与运行事实；训练结果仅按已生成 summary 记录，未将 4096-env OOM 推断为 policy 失败。当前 completion 为 `NOT_SUPPORTED/NOT_RUN`：bilateral E7/goal 与 hardware 均未完成或未运行。旧条目中关于 “P not started” 的表述与 pull-v6.1 的 “P population integration was not started” 语义容易混淆；本 entry 只保留当前 n1024 retry 与 held-out qualification TODO，不修改历史条目。
