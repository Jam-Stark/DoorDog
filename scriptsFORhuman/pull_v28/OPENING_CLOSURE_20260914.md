# Pull v28 接续closure — 2026-09-14 m5

**当前终态：`BLOCKED_G0_POST_POLICY_CHECKPOINT_FAILURE`。已授权的robot引用修复成功，G0完整跑完5个学习迭代，但保存接线没有产生检查点。PA三格仍未运行。**

## 本次实际完成

Owner授权“然后按照原计划继续”后，应用既有一行修复`env["robot"] = "${robot}"`，以全新`g0_resume_20260914/G0`目录和`pull_v28_train_g0_attempt2` receipt运行，未覆盖任何旧失败证据。

实际日志已证明actor/critic的RunningMeanStd及LSTM输入分别为133/138，原LSTM(0,256)问题已消失。256env scratch、checkpoint=null/full/auto-load=false，5个学习迭代全部完成：18.97/17.63/16.68/17.20/16.82秒，共81,920 timesteps；迭代总计87.30秒。冻结资产、事件/ready/Stage4、奖励与原训练合同均保持。

P2的18条natural诊断、contact_a3及三姿态PG7沿用既有有效证据，没有重跑。新增G0专属归约入口复用现有side_summary(seed0)，不把G0加入PA三seed分母；因检查点缺失，该入口尚未取得实际natural输出，不能宣称端到端已通过。

## 保存失败的具体证据

- 实际`config.yaml`和`resolved_config_verified.yaml`中，`callbacks.model_save.save_frequency=250`，save_dir正是本次G0目录。
- `gr00t/rl/trl/callbacks/model_save_callback.py:28–49`仅在global_step为保存间隔倍数时写`model_step_%06d.pt`；另一个`last.pt`路径也只每50步保存。
- 因此5步smoke不会触发任何保存。检查点没有写到其他配置路径，目录只有配置/meta/log/runtime等文件。
- 子进程正常返回0；现有runner因要求的`model_step_000005.pt`缺失正确返回1，`policy_readings_observed=true`。peak6210MiB、headroom18366MiB，无OOM证据。

这次不是训练数值崩溃或物理门失败，是已读policy后的检查点发出失败。原计划§8规定“policy读数后的非零退出停该格、其余继续，不自动重跑”，故没有自动再训练。其他PA格尚受G0前置依赖约束，不能启动绕过。

## 已准备但未应用的最小补丁

```diff
-    cfg["callbacks"]["model_save"]["save_frequency"] = 250
+    cfg["callbacks"]["model_save"]["save_frequency"] = 5 if a.smoke else 250
```

见`OWNER_PROPOSED_SMOKE_SAVE_FIX_NOT_APPLIED.patch`。仅对smoke改保存时点，正式PA保持250，不改变policy、reward、物理门或训练目标。

**Owner待决定：授权这次保存接线修复，并允许一次新的5batch smoke及其checkpoint natural评估。** 若授权，新attempt使G0累计10 batches，仍在32上限内；通过后继续原PA三格各6000及24条natural。旧5步未保存权重，无法在已经退出的进程中补发检查点。本次没有应用该提案、没有重跑或扩大训练预算。

## 终点与资源

G0累计完成PPO5 batches；PA0/18000，warm NOT_RUN，18500上限未触及。PA_S1/2/3均NOT_RUN；原分母保留，`k=null/3`，状态`NOT_ASSESSED_G0_INCOMPLETE`，不能填0/3或判opening失败。PA margin、ready、camera、历史checkpoint与E6/E7均没有新证据。P3–P5、Teacher、硬件、外部写入及push均未运行。

attempt2已终止，本任务无活动训练tmux/GPU进程，Main GPU1/2/3 leases已释放；无关tmux0保持。仅确认本次已处理的receipt完成事件。plan、decision、memory已更新；前一天的closure保留为当时快照。

m5仓库：`/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0`。本次小证据在`scriptsFORhuman/pull_v28/evidence/g0_resume_20260914/`；原始输出在`logs_rl/a2_piper_pull_v28/pull_v28_baseline_sync_20260913/g0_resume_20260914/G0/`。本次没有推送，预先存在的D2和其他无关工作树改动保持。
