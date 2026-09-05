# v26-8 eval curriculum-off wiring addendum

日期：2026-09-04 HKT

## Scope and authority

Owner 已授权自主合理修复以推进 v26-8。本 addendum 只修正既定 §4.3/§7 的 evaluation curriculum-off
接线，不改变任何训练变量、policy、reward/stage、threshold、source checkpoint 或评估计数/route 判据。
正在运行的六格 training source lock 与 canonical plan 文件保持原样，避免改变 load receipt 的 plan binding。

## Proven source path

`eval_agent_trl.py` 从 checkpoint-adjacent `config.yaml` 读取训练配置，再以
`OmegaConf.merge(train_config, override_config)` 合并 eval overrides。K config 的
`env.config.a2_v26_8_penalty_driver` 因而会继承；原 eval script 只覆盖
`rewards.reward_penalty_curriculum=false`，却没有清空 driver。

`DoorPregrasp._init_a2_v26_8_penalty_curriculum` 对设置了 driver 的单侧环境或关闭 curriculum 的环境
均 fail-fast；同时 driver 开启会尝试创建训练目录的 K trace。因此 eval 必须显式关闭 driver，不能只关闭
reward scaling。

## Minimal correction

`v26_8_eval_cell.sh` 对 C/W/K 所有 eval lane 同时使用：

```text
++rewards.reward_penalty_curriculum=false
++env.config.a2_v26_8_penalty_driver=null
```

driver 为 null 时 core 走既有关闭路径，不初始化 pending counters/trace；reward curriculum 为 false 时
reward telemetry 不乘 K scale。C/W 原本无 driver，显式 null 不改变其行为。LEFT/RIGHT exact64、natural
start、full checkpoint load、seed、checkpoint 与全部 metric/route 阈值均保持原样。

补充 machine-readable evaluator lock 位于 r3a runtime root 的 `eval_driver_off_lock.json`，记录原训练
source lock、唯一 eval-script 差分、当前 plan binding 与六格静态 merge 结果。没有启动失败的 eval attempt，
不涉及重跑或覆盖 artifact。
