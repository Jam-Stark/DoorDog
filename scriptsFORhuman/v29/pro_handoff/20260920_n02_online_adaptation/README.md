# N02 Pro预研输入包

2026-09-20 HKT。状态：**PRO_RETURN_RECEIVED_AND_FOCUSED_RECONCILED**。R2输入已发布/上传，Owner随后在本对话提供[Pro回包及CPU模型材料](../../../pro_reviews/v29/20260920_162527__N02_online_adaptation/README.md)，已完整归档并作一次定向核对；[研究结论与局部模型更正](../../../novelty/documents/20260920_n02_pro_review_and_next_step.md)已进入novelty。本地未复跑模型或实施N02。此处只更新本地路由，不回写已发布输入。主底座完整C002保留B05；研究顺序仍为能力缺口→目标→信息/数据→控制→网络→Student。UniFP/SixthSense只供借鉴，不预选fusion/flow-matching。

- [可直接复制给Pro的完整R2 prompt](PRO_REVIEW_PROMPT.md)
- [唯一完整R2输入目录](https://drive.google.com/drive/folders/1m7C_mk9bFPxGcQK0RTUFwl3J8rPHjE7g) · [已发布审阅分支](https://github.com/Jam-Stark/DoorDog/tree/codex/v29-n02-pro-20260920)
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

完整修订输入交付记录：三个独立ZIP共396份选定文件，压缩大小19,411,932 / 6,336,390 / 77,645 bytes，均低于95MiB；六文件已核对名称/大小/父目录。旧首版保留为历史，最终使用R2。该次交付只完成资料与模型输入提取；后续收到的Pro结果以本页顶部回包链接为准。本地prompt/收据在上传后生成，不回写已上传ZIP。
