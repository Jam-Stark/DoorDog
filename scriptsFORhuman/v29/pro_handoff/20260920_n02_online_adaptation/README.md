# N02 Pro预研输入包

2026-09-20 HKT。主底座为完整C002，保留B05。研究顺序：能力缺口→估计/预测目标→可用信息/数据→控制使用→网络→Student训练与独立行为效果。允许不用独立估计器、物理参数预测或全身wrench；UniFP/SixthSense只供借鉴，不预选fusion/flow-matching。

- [Owner六项原始要求](OWNER_REQUEST.md)
- [完整研究brief](../../../novelty/documents/20260920_n02_v29_c002_pro_research_brief.md)
- [当前观察/历史/行为source事实](LOCAL_FACTS.md)
- [源码与证据导航](SOURCE_INDEX.md)
- [新增：Pro实际动力学/方向力计算要求](DYNAMICS_AND_FORCE_EXECUTION_BRIEF.md)
- [指定论文的一手入口](PAPER_REFERENCE_NOTES.md)
- [共用C002 source版本绑定](BASELINE_SOURCE_BINDING.json)
- [Pro回包后的本地接手文本](LOCAL_WORKER_PARSE_PROMPT.md)

源包直接复用上一份完整C002＋同tag依赖；本次brief/已存证据与历史novelty/shadow分别打包。已有v27离线结果不证明C002可辨识，Teacher结果不能外推Student。原GPU0/GPU1任务按已有合同继续，没有N02方法实现或新实验。

基座tag `v29-c002-baseline`；审阅分支 `codex/v29-n02-pro-20260920`。只增加研究资料，不改变生产底座。发布/上传完成状态与最终Pro prompt在交付后的本地记录中给出，不从本页预先推断上传已完成。

Owner同轮追加A2＋PiPER动力学建模与roll/pitch方向力验证，已纳入修订输入；Pro须尝试执行并回传脚本/数值/图。最初上传的未含此项版本将保留为历史，最终以新修订目录/提示词为准。
