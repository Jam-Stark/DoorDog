---
name: base-v27-bilateral-hardening
status: active
scope: v26 qualification, bilateral behavior quality, door domain, one-loss recovery pilot, scratch reliability
last_verified: 2026-09-05 20:15 HKT
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
Wave A 六格已正常 strict actor/RMS 加载并训练，endpoint 尚未产生。恢复启用路径将在 Wave B 前接线。

执行状态与 receipts 由
`scriptsFORhuman/v27/runtime_logs/v27_bilateral_hardening_20260905/` 路由，不将 heartbeat 写入 memory。
