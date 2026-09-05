# Pull v26-8 backbone closure — 2026-09-05

**结论：P0/G0通过；G1为`NOT_ADMITTED`，按计划硬停止。Wave 1、Wave 2、opening与E7全部`NOT_RUN`。双侧能力目标仍为`UNRESOLVED`，没有新policy成功或失败结论。**

本轮完成了函数级镜像移植、plain backbone配置和评估/receipt脚本。真实G1评估暴露了此前未列入计划的pull初始化约束：`door_open_a2_pull.py:2424`的`_register_a2_pull_staged_reset_buffers`拒绝`enable_staged_reset=false`。这是当前full-pull初始化合同与计划natural eval合同的冲突；发生在第一份old/bilateral评估的环境构造阶段，早于eval actor加载和策略读数。不能把它解读成镜像公式失败。

## Gates与receipt

工作树：`/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0`，branch `codex/a2-piper-pull-v0-20260803`。起始revision `d48793c`；主线只读参考为`A2_Piper@cb15678`（parent `aa8a05f`）。没有merge或整文件覆盖。

| Gate / attempt | 实际执行 | Child / wrapper | 结果 |
|---|---|---|---|
| P0/static | 三格resolved config、完整reward与source baseline逐项相同；镜像7项CPU测试 | CPU exit0 | `STATIC_PASS` / `TEST_PASS` |
| G0/2048初次 | Main在场景构造期间主动中断以诊断GPU/显示警告；无policy读数 | 0 / 1，checkpoint缺失 | `CONTROLLED_INTERRUPTION_BEFORE_POLICY_READOUT`；计入第一次relaunch |
| G0/2048 `_r2` | 场景和actor构造成功；首轮rollout LSTM hidden-state buffer申请256MiB时OOM | 0 / 1 | 未通过显存门；采样峰值24066MiB，无policy读数 |
| G0/1024 `_r2` | 5/5 batches，327680 transitions，checkpoint存在 | 0 / 0 | `G0_PASS`；峰值16062MiB、余量8514MiB |
| G1/train `_r2` | 64-env bilateral，5/5 batches，checkpoint存在 | 0 / 0 | 短训练runtime通过；不代表G1几何通过 |
| G1/old `_r2` | `enable_staged_reset=false`在环境构造时被source拒绝 | 0 / 1 | `NOT_ADMITTED` / `PULL_V26_8_WIRING_NOT_CONFIRMED` |
| G1/fixed及all-RIGHT | 未执行 | — | `NOT_RUN` |

Isaac在OOM和环境构造异常后均返回0；wrapper通过缺失预期checkpoint或评估artifact正确返回1，没有把child exit0误判为通过。

全部receipt位于`.ai/runtime/runs/`：`pull_v26_8_g0_2048`、`pull_v26_8_g0_2048_r2`、`pull_v26_8_g0_1024_r2`、`pull_v26_8_g1_r2`，状态分别为`FAIL/FAIL/PASS/FAIL`。其中每份`RUN_RECEIPT.json`记录实际command、source lock、revision、GPU和预期产物。实际代理为`http://127.0.0.1:18889`，两个Isaac资产均HTTP200。重启的headless进程显式unset DISPLAY/XAUTHORITY。

同样的MIT-MAGIC/GPUFoundation警告存在于历史成功H16运行中；独立CUDA分配与Vulkan枚举成功。因此首轮中断只按Main主动诊断中断记录，不能归因为驱动损坏或已证明的hang。第二次2048的OOM才是真实显存结论。

## Source与plan差异

| 项目 | 实际证据 | 本轮处理 |
|---|---|---|
| 观测维度 | 当前主线与pull的同plain名单均为**133/138**；旧winner actor实际135，含2维release-mode | 按source/resolved优先，使用133/138，不补虚假维度。G0 checkpoint输入矩阵实际为actor`(1024,133)`、critic`(1024,138)`。 |
| RMS | plain `RecurrentActor`不接受`freeze_running_mean_std`参数；native RMS本来可更新 | 不修改actor/loader；`running_mean_std=true`。G0 actor共20个state tensors、RMS count2031041。 |
| Stage2→3 gate | E2 proof可在Stage3通过hold-contact streak形成，并非离开Stage2后永久归零 | 不触发plan§2.7例外；使用`grasp_completion`，保留handle/hinge live-proof masks。 |
| W阈值 | full-pull已有near-closed threshold`.25`，plan假定`.1→.25` | Wave1候选保留`.25`。即使未来触发W，也不能把`.25/.25`当作干预。 |
| Natural eval | full-pull `_register_a2_pull_staged_reset_buffers`要求flag为true；plan要求false | G1立即停止；未改guard、未把eval flag静默改回true。 |
| Source lock | Owner项目规则禁止新增hash/SHA-256 | 保存revision/status与逐文件原始副本；窄harness修复用字节比较记录contract diff。 |

旧pull runner的natural评估使用`staged_reset_ratios=[1,0,0,0,0,0]`，同时保留`enable_staged_reset=true`。是否采用这个既有协议，或授权修改pull对关闭staged reset的支持，需要在继续前明确；本轮没有替换计划中的natural协议。

## 三格逐侧读数

G0冻结的候选预算为每格1024 env×6000 batches，milestones每750；预定GPU1/2/3对应P_S0/P_S1/P_S2，GPU0评估。矩阵实际未启动。下表`—`均表示`NOT_RUN`，不代表0/64。

| Cell | Side | D | S3+ | S4+ | open_hold | S5+ | complete |
|---|---|---:|---:|---:|---:|---:|---:|
| P_S0 | LEFT | — | — | — | — | — | — |
| P_S0 | RIGHT | — | — | — | — | — | — |
| P_S1 | LEFT | — | — | — | — | — | — |
| P_S1 | RIGHT | — | — | — | — | — | — |
| P_S2 | LEFT | — | — | — | — | — | — |
| P_S2 | RIGHT | — | — | — | — | — | — |

| Cell | Side | K5 | E2 | E3 | E4 | E5 | E6 | E7 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| P_S0 | LEFT | — | — | — | — | — | — | — |
| P_S0 | RIGHT | — | — | — | — | — | — | — |
| P_S1 | LEFT | — | — | — | — | — | — | — |
| P_S1 | RIGHT | — | — | — | — | — | — | — |
| P_S2 | LEFT | — | — | — | — | — | — | — |
| P_S2 | RIGHT | — | — | — | — | — | — | — |

六个cell-side的arm_j4限位占比、力分布、over-force、terminal reasons与integrity读数均未产生，结构化closure中为`null`；没有填0。E标签与stage编号的独立映射见`REDUCER_CONTRACT.md`。

与历史相反的policy读数：**没有新policy评估读数可比较**。已核实的反向事实是plan维度误记、已有`.25`阈值、以及natural eval flag与pull初始化不兼容；均已显式报告。历史H4–H18负结果未被本轮静态或smoke证据推翻。

## Typed outcomes与未运行事项

- Migration admission：`NOT_ADMITTED`，G1 runtime几何为`UNRESOLVED`。
- P_S0/P_S1/P_S2：`NOT_RUN`；没有unlatch endpoint。
- Wave2：`NOT_RUN`，因为G1失败且Wave1未启动。W轴另有上述source/plan阈值冲突。
- Opening、E7、optional G2、完整milestone reducer：`NOT_RUN`。
- Teacher、handoff、hardware、push和主线K driver：未运行。
- 证据上限：mirror代数`TEST_PASS`；1024-env plain-backbone训练与G1构造失败`RUNTIME_PASS`；没有`EXPERIMENT_PASS`或`HARDWARE_PASS`。

## Artifacts与changed paths

运行产物根：`logs_eval/a2_piper_pull_v26_8_backbone/pull_v26_8_backbone_20260905_r2/`，包含`P0/source_trace.json`、`G0_memory_smoke/`、`G1_wiring/g1_wiring.json`、`frozen_wave1_contract.json`及`closure.json`。`g1_wiring.json`明确标记由Main根据真实构造异常裁决，几何reducer未运行。

源码/config改动：

- `gr00t/rl/envs/door/door_open_a2_base.py`：仅镜像helper接入、逐env offset函数、开关与scene wiring。
- `gr00t/rl/envs/door/a2_v26_6_handle_offset_mirror.py`。
- `gr00t/rl/tests/test_a2_v26_6_handle_offset_mirror.py`。
- `gr00t/rl/config/exp/wbmanip/door_open_a2_pull_v26_backbone_lstm.yaml`。
- `gr00t/rl/config/ablation/wbmanip/pull_v26_8_backbone_common.yaml`与三个`P_S0/P_S1/P_S2` cell yaml。
- `scriptsFORhuman/pull_v26_8/`的train/eval/orchestrate/runner/preflight/verify/reducer脚本与合同/closure文档。
- 既有`memory/a2-piper/pull-lr-full-stage/{description,TODO,DONE}.md`及路由`memory/a2-piper/MEMORY.md`。

冻结迁移plan原文随任务记录；历史`pull_lr_*`、`pull_v6*`脚本、旧artifact、reward数值、E事件和loader没有修改。Owner既有`.codex/config.toml`与`Codex-Cashier/`不纳入本轮提交。

没有达到G0/G1后的第一个commit点，也没有Wave1 endpoint commit点；使用已授权的closure本地commit点保存当前候选与失败证据，不push。未产生stage artifact handoff。

Closure资源检查：全部本轮进程/tmux已退出，GPU0–3无compute进程；本轮writer结束，GPU leases已释放。
