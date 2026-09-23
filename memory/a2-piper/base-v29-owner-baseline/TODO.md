# TODO

- **8000质量与B08下一步待Owner选择**：两例render及原64终态已见身体接触，complete不能覆盖clean/持续回臂保持。见[补充分析与两卡方案](../../../scriptsFORhuman/v29/a2_piper_base_v29_8000_quality_followup_20260922.md)；建议先补实际arm姿态诊断，再同8000起点等预算C002/B08续训对照。当前无新运行授权。

- **D074本轮已由D077关闭，等待Owner下一范围**：[8000自然64](../../../scriptsFORhuman/v29/a2_piper_base_v29_C002_resume8000_final_readout_20260922.md)左右各32/32goal，不能据此自动延长训练或启动独立seed/新方法。后续若验证泛化或样本效率，另定问题与预算；原D072/D076保留历史。

- **B08实现已完成**：公共补丁已同步baseline B08、N01、N02、B05-ablation开发目录；CPU定向证明通过、未commit/push。实际训练效果未验证；本次已完成的GPU0及仍活跃的GPU1采用原冻结输入。目录与证据从[实施记录](../../../scriptsFORhuman/v29/a2_piper_v29_B08_implementation_20260921.md)读取。

- D065新增GPU1 v29−B05对照由独立worker team接手，计划/Git版本/候选待办见`../base-v29-handle-ablation/`；不要与原GPU0运行状态混写。
- D072已验收并关闭D060的一次C002 seed291/4096/6000训练及64自然首episode评估；0/64 goal，LEFT后段超时、RIGHT均Stage2超时。下一轮修复/诊断需明确范围，不能从此次执行完成自动扩为续训、额外seed或Teacher放行。
- 早期左右失败机制属于6000/7000 checkpoint历史；[D077](../../../scriptsFORhuman/v29/a2_piper_base_v29_C002_resume8000_final_readout_20260922.md)显示同人口8000已双侧完成，不再把旧卡点列为当前8000必须修复的问题。B08接口改动、跨seed稳定性和泛化收益仍未由本次结果证明；loss仍NOT_OBSERVED。
- B02按D020保持后置：共同baseline后单开apply B02分支ablation，目前未创建/未运行；对照沿用共同B01/B04域和训练/评估设置，届时明确改动组。B03倾角仍15°，后续微调。
- N01/N02与pull/额外seed须各有实际授权；D074只新增同一push seed291配方的6000→8000及指定两次评估。D023的重新抓把手扶门及奖励/回臂协调仍在N02讨论，不是本次续训的并行改动。
- 需要三路相机图像交付时使用对应renderer路径；本次headless PPO、结构可见性与contact图不构成三路成像验收。
- 决策归属保持：Owner授权/Planner裁定写主D日志，Worker实现及运行记录写W日志；过程完成、实现验收和策略评估分别报告。
