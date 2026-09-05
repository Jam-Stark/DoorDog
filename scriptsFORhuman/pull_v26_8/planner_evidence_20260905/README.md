# Pull v26-8 planner evidence — 2026-09-05

这份Git可见副本用于把训练机`ai-precog-machine5`的当前结果交给plan机器。Owner已明确授权本轮Git同步；它不改变上一轮closure的实验结论，也不授权继续训练。

先读上一级的[closure](../a2_piper_pull_v26_8_backbone_closure_20260905.md)、[执行合同](../CONTRACT.md)与[reducer合同](../REDUCER_CONTRACT.md)。实现commit为`2033049`，本次新增的证据与索引随其后的同步commit传输。

## 当前结论

- G0：2048 env首轮rollout OOM；1024 env×5 batches通过，327680 transitions，峰值16062MiB，余量8514MiB。
- G1：短训练通过，但第一份old/bilateral natural eval因pull源码要求`enable_staged_reset=true`而在构造阶段失败；plan要求false。`NOT_ADMITTED`，没有几何对照或新policy评估结果。
- Wave1、Wave2、opening、E7为`NOT_RUN`，指标为null，不能按0/64处理。
- 当前mainline/pull plain观测实际133/138；既有full-pull near-closed阈值已经是`.25`。两项plan差异已写入closure。

## 文件入口

| 要核对的事实 | 本目录中的证据 |
|---|---|
| 三格未运行、typed outcome | `artifacts/closure.json` |
| G0预算与实际显存 | `artifacts/frozen_wave1_contract.json`、`artifacts/G0_memory_smoke/num_envs1024/g0_smoke.json` |
| 成功smoke的完整resolved配置 | `artifacts/G0_memory_smoke/num_envs1024/resolved_config.yaml` |
| 2048 OOM的原始异常 | `excerpts/G0_2048_OOM.txt`及对应`runtime_result.json` |
| G1实际构造配置与异常 | `artifacts/G1_wiring/old/runtime_config.yaml`、`excerpts/G1_constructor_failure.txt` |
| G1裁决与未运行项 | `artifacts/G1_wiring/g1_wiring.json` |
| 实际commands、proxy/GPU、exit状态 | `receipts/`与各阶段`runtime_result.json` |
| P0维度/gate分析、harness变更 | `artifacts/P0/source_trace.json`、`provenance/` |

`MANIFEST.json`逐项记录原始训练机相对路径、传输路径、字节数和原文节选行号。JSON/YAML/receipt副本保持原始字节；两个log节选仅去除ANSI颜色。receipt中的绝对路径仍指训练机；plan机器阅读时使用本目录的对应副本。`source_lock.json`所引用的完整source_snapshot保留在训练机，没有重复放入Git。

未传checkpoint二进制、完整log、GPU采样CSV和live team数据库。这里的receipt是训练机历史证据，不能拿来恢复plan机器上的进程。

## Planner需要裁决

1. Natural eval是否采用pull现有协议：保留`enable_staged_reset=true`，令`staged_reset_ratios=[1,0,0,0,0,0]`，并关闭外部bank；或另行授权实现真正的staged-reset关闭路径。当前没有替换协议或修改guard。
2. 更新plan对观测维度的135/140误记，保留实际主线133/138 plain列表。
3. 若后续进入W分支，先解决已有`.25`基线与`.1→.25`干预假定之间的冲突。

这次同步仅让planner取得源码与证据；G1准入、矩阵与policy能力都不能因文件已传输而升级为通过。
