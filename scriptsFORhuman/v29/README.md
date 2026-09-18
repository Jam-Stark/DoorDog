# base_v29：Owner 基础改动

当前决定（2026-09-18 15:27 HKT）：[baseline plan](a2_piper_base_v29_baseline_plan.md)的B01已更新为30–80/80–120/120–160kg三档各1/3，与有/无闭门器各半组成六个等权组合；联合配方补充重档惯量影响，闭门器/摩擦仍跨三档覆盖。B01讨论PASS，物理代码待实施。B06/B07已PASS；Stage0在门法向1.8–2.2m间平滑过渡0.3→0.5m/s，Stage4/5仍0.3；30s时限与结转逻辑沿用。见[决策D008–D014](a2_piper_base_v29_decision_log.md)。B02–B05继续讨论，尚无新训练。

最新范围（2026-09-18 17:04 HKT，D016–D017）：B02重新开放“软件约束/当前物理解锁”二选一，与B04最大开角限位方案同包交Pro独立选择及设计；旧软件偏好不预设结论。B03保持base15°，后置到v29 baseline出来后微调，不作前置。[本次任务与材料入口](pro_handoff/20260918_b02_b04/OWNER_REQUEST.md)；B02/B04尚未实施。

Pro回传（2026-09-18 10:41 HKT）：已保存原包/原文并完成定向本地解析。[归档与核对入口](../pro_reviews/v29/20260918_102906__baseline_and_v28_pro_review/README.md)；原文中的未决状态保留为当时记录，后续决定见上方当前入口。原[交付入口](pro_handoff/20260918/README.md)保留。

当前讨论入口：[v29 总体安排](a2_piper_base_v29_overall_arrangement.md)记录八卡分工、push/pull各2 seed与N01/N02独立工作时机；[baseline TODO](a2_piper_base_v29_baseline_TODO.md)保留各项讨论。按Owner最新指示，plan先收录确认部分，整体clean后完成全文与执行安排。

更新：2026-09-17（HKT）。三项基础改动已实施到 source、配置及实体 URDF/USD，并完成一次 64-env / 1-batch PPO 运行。完整决定与证据边界见 [决策记录](a2_piper_base_v29_decision_log.md)。

上述one-batch运行对应9月17日基础配置；9月18日时间/自然起点的新改动仅有配置解析和CPU采样核对，尚无新仿真/训练/成像验证。

| 决定 | 已实现行为 |
|---|---|
| V29-D001 | goal 保持 `[2,0,0.5]`；Stage5 增加目标方位 yaw 误差平方惩罚 `-4.0`，增加实际 roll/pitch 平方惩罚 `-8.0`，与原 `-2.0` 合计为 `-10.0` |
| V29-D002 | 双侧门的 handle 高度 uniform 范围改为 `[0.90,1.20] m`；自然起点评估继承该范围 |
| V29-D003 | MERGED 腕机物理/光学为 `180 mm / 45°`；arm init/reset 为 `[0,.10,-.10,0,-.52,1.57]`；隐藏外壳显示盒，保留碰撞与质量 |

相机数量为 **3 台：base 左右双 D435i + 腕机**。三台相机外壳显示盒隐藏，支架可见。按 Owner 追加要求，旧 `base_center_housing` 中央包络已从 URDF/USD 的 visual、collision 及 rig 几何记录中完整删除；它原本没有质量/惯量贡献，因此 trunk 的实际惯性参数保持不变。

使用入口：

- baseline：[`base_v29_baseline.yaml`](../../gr00t/rl/config/ablation/wbmanip/base_v29_baseline.yaml)，从零配置，seed 291。
- 共用配置：[`base_v29_common.yaml`](../../gr00t/rl/config/ablation/wbmanip/base_v29_common.yaml)；自然起点评估 overlay：[`base_v29_eval_natural_start.yaml`](../../gr00t/rl/config/ablation/wbmanip/base_v29_eval_natural_start.yaml)。
- robot：[`a2_piper_v29.yaml`](../../gr00t/rl/config/robot/A2_Piper/a2_piper_v29.yaml)；实体资产：[`a2_piper_v29_merged_20260917/`](../../gr00t/rl/data/robots/a2_piper_v29_merged_20260917/)，包含 `config/camera_rig.json`。
- 资产生成来源：[`v29_build_asset.py`](v29_build_asset.py)，复用 v28 的 MERGED 层和 180/45 几何计算；训练加载生成后的独立资产，不依赖 v28 临时 side-eval 目录。生成工具使用本机 Isaac Sim 的 USD Python 库及既有 v28 几何工具。

实际训练入口是 `python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v29_baseline`，本次显式限制 `num_envs=64`、`algo.trl.num_total_batches=1`、`callbacks.model_save.save_frequency=1`、headless、关闭 wandb，并使用独立输出目录。删除中央碰撞包络后复核的完整命令及进程结果见 [process receipt](runtime_logs/baseline_no_center_smoke_20260917/process_receipt.json)。

证据：[资产与配置核对](asset_and_config_verification_20260917.json)、[运行读数](runtime_logs/baseline_no_center_smoke_20260917/runtime_readout.json)。最终资产于 2026-09-17 19:59:05–20:00:02 HKT 完成复核，exit=0、step=1、4096 timesteps。默认姿态的腕机光轴相对 trunk 向下约 `15.206°`。接线运行不证明 Stage5 行走质量、高把手成功率或成像质量。headless 日志出现 renderer GPU Foundation 初始化错误，因此不将本次算作渲染验证。初版删除中央包络前的单批运行保留在 `baseline_smoke_20260917/`，与当前资产复核分开记录。

完整训练方案、预算与资格规则尚未制定。common 中保留的 6000-batch 默认值是继承配置，不是本轮启动预算；本轮没有正式训练或资格评估。上游 [v28 closure](../v28/a2_piper_base_v28_execution_closure_20260917.md)保持已关闭。Owner 现已将 N01/N02 纳入 v29 总体方向，待 baseline 落地后分别进入独立 branch/worktree；具体实验设计尚未确定。
