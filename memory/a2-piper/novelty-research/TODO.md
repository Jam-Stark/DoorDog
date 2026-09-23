# TODO

- **左右差异后续研究须按D077重设问题**：[8000](../../../scriptsFORhuman/v29/a2_piper_base_v29_C002_resume8000_final_readout_20260922.md)已在同seed自然64中双侧完成，6000/7000机制诊断仅为历史。动态分配/归一化/bank若继续研究，应服务样本效率、跨seed可靠性或新域，而非默认修复当前8000仍存在的失衡；没有新实施/实验授权。GPU1 B05消融仍按原合同等待。

- 共同baseline B08实现与分支同步已完成；后续N01/N02接口工作直接复用[公共实现及目录](../../../scriptsFORhuman/v29/a2_piper_v29_B08_implementation_20260921.md)，不要重复删除或引入专用Stage0 bypass。方法其余范围仍由各planner当前计划负责。

- N01于2026-09-20收到Pro回包并完成定向核对，planner最小设计已交付、待Owner裁定；N01/N02方法实现仍需各自范围与实验合同。原GPU方向不等于当前空闲或已获本次运行预算，审阅交付分支也不等于方法实验worktree。

- 后续novelty讨论有实质产出时，按讨论区README保存对话与文档、更新索引，并同步本entry三文件；仅记录真实新决定与证据。
- N-01：按[最小设计](../../../scriptsFORhuman/novelty/documents/20260920_n01_minimal_recovery_transfer_design.md)等待Owner裁定两项：首轮正常释放前L0＋L1范围，以及Teacher/Student共享stage-blind接口并由Teacher适应后提供12D标签。实施前尚需明确Teacher及可信后缀区域、v29 Student resolved/实际相机视路与时序；扰动实效和短展开是否足够由后续证据决定。完整C002保留B05，D023不变；prefix/事件库/L2/L3未成为前置。Owner明确要求实施后再制定WRITE_SET和功能路径、必要验证；训练/评估及预算另按授权，不重审整个C002。
- N-02：Pro回包及CPU执行材料已归档/定向核对，按[研究结论](../../../scriptsFORhuman/novelty/documents/20260920_n02_pro_review_and_next_step.md)由planner收敛首轮行为/奖励、动作候选与续接控制c、部署输入/历史、分离比较四组选择。先确认行为及有用后果差异，再决定原LSTM/小头；完整C002保留B05，短/失败/无接触与Student自身轨迹必须覆盖。沿用模型前注意156行压柄夹持界更正；当前未修脚本/重算，仿真限值不作硬件能力。旧shadow、UniFP/SixthSense只作参考；D023与N01接口变化待Owner采纳。Owner明确下一阶段后再落实最小功能路径与必要验证，无当前实施、在线实验、GPU或预算授权。
- N-07b：Teacher资格与配对训练／蒸馏预算满足后，再研究camera bundle对Student的收益。
- N-06等条件路线继续从长期TODO读取入场条件；没有新授权，不启动训练或扩大实验范围。
