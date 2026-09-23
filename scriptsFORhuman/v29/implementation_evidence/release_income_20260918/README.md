# D021 release income CPU核对

适用性更新：**HISTORICAL_D021_ONLY / REVERTED_BY_D023**。Owner已精确回退本probe所验证的三处改动；以下结果仅保存当时事实。不要将此脚本对当前源码执行的结果当作现版本验收；当前回退证据见[readout](../reward_revert_20260918/readout.json)。

2026-09-18 20:22 HKT。状态：**TEST_PASS（CPU production-method probe）**；IsaacSim/策略质量：**NOT_RUN**。

Owner指出release gate后仍有开门/握持收入并授权修复。本次只核对三处实际生产函数及其mask/latch逻辑，执行提取后的源码函数，使用本机IsaacLab的实际quaternion math与明确的CPU批量输入。没有启动环境、GPU或训练。

- [readout.json](readout.json)：输入情形、数值结果与证明边界。
- [cpu_reward_probe.py](cpu_reward_probe.py)：本次窄范围复现，非新增通用测试框架。
- [决策D021](../../a2_piper_base_v29_decision_log.md)：Owner授权、源码改动与其余baseline范围。

执行命令（项目根目录）：

```bash
/home/baoquanc/anaconda3/envs/isaaclab/bin/python scriptsFORhuman/v29/implementation_evidence/release_income_20260918/cpu_reward_probe.py
```

Stage3与gate前Stage4的hinge/hold仍为正；gate后正门速与负门速场景均归零。gate后grasp正值归零、负值保留，release门在1.2rad置位并在回关后锁存。输出是未乘配置scale/timebase的原始值；提取时去掉stage decorator，Stage5 raw grasp不作为实际Stage5奖励解读。

首次临时harness漏绑定`_get_a2_corridor_mask`，补入实际getter后完成核对；未通过修改生产代码回避该harness问题。本证据不证明真实接触、通行/回弹质量或训练策略会更早松手。
