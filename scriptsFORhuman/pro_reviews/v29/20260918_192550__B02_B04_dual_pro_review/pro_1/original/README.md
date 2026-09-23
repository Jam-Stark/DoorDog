# v29 B02 / B04 Pro决策回包

**B02=A：虚拟锁闩＋原生物理限位；B04=原生joint limit，正常最大角每门U(90°,150°)。**

先读FULL_REVIEW.md的选择，再读DESIGN_SPEC.md的统一参数/状态/恢复规范。当前仅为设计，不是已实施补丁或新的运行验收。

文件：

- `FULL_REVIEW.md`：完整比较、明确选择、证据边界、关键未知。
- `DESIGN_SPEC.md`：参数、隐藏FSM、两DOF迁移、物理时序、reset/staged、reward/observation及源文件接入。
- `LOCAL_WORKER_PARSE_PROMPT.md`：与对话内复制文本一致的Worker接手prompt。
- `SOURCE_MAP.md`、`source_evidence/`：路径/原始行号、选中源码节选与本机IsaacLab方法原文。
- `PARAMETERS.json`：便于核对的机器可读设计参数；不表示项目已读取或应用这些新字段。
- `DESIGN_STATIC_CHECKS.json`：纯Python参数/离散FSM/奖励公式检查，完全不涉及物理仿真。

只交付附件，不上传Drive。未修改仓库或Worker原件，未生成哈希清单。Owner后续授权前，Worker仍限解析与定向核对，不自动实施/训练或勾选未确认项。
