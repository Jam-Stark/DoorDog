# N01 Pro预研输入包

2026-09-20 HKT。研究范围：完整v29 C002保留B05，独立重设计恢复图、抗干扰Teacher与恢复能力向Student的传递。状态：**PRO_RETURN_RECEIVED_AND_FOCUSED_RECONCILED**。输入已发布/上传；Owner随后在本对话提供Pro回包，已保存[原ZIP、六份原件与本地核对](../../../pro_reviews/v29/20260920_153418__N01_recovery_transfer/README.md)。[研究结论与待定选择](../../../novelty/documents/20260920_n01_pro_review_and_next_step.md)进入novelty。此处仅更新本地路由，不回写已交付输入。未实施N01或运行新实验。

- [可直接复制给Pro的完整prompt](PRO_REVIEW_PROMPT.md)
- [Drive输入目录](https://drive.google.com/drive/folders/1TYMXvIKohP6-IlrhYa6hXFn4qjZqWvIo) · [已发布审阅分支](https://github.com/Jam-Stark/DoorDog/tree/codex/v29-n01-pro-20260920)
- [Owner五项原始要求](OWNER_REQUEST.md)
- [完整研究brief](../../../novelty/documents/20260920_n01_v29_c002_pro_research_brief.md)
- [当前源码与证据事实](LOCAL_FACTS.md)
- [source/evidence导航](SOURCE_INDEX.md)
- [补充源码与baseline tag的直接比较](SUPPLEMENTAL_SOURCE_BINDING.json)
- [Pro回包后的本地接手文本](LOCAL_WORKER_PARSE_PROMPT.md)

交付遵循三个独立ZIP：C002完整冻结输入及必要依赖；本次问题/事实/已存runtime证据；历史novelty参考。先独立形成恢复与传递方案，再读历史参考。不要把C002实现已接受等同成熟Teacher，也不要把GPU1旧把手消融当主底座。

基座tag `v29-c002-baseline`；审阅分支 `codex/v29-n01-pro-20260920`。发布、上传及可直接复制的Pro prompt由完成后的本地交付记录给出；不得从本页预先推断已上传。源包不含checkpoint/策略权重或本机Isaac环境，供源码阅读和方案研究。

完成后记录：三个ZIP共390份选定文件，压缩大小19,411,932 / 6,320,911 / 76,803 bytes，均低于95MiB。三份ZIP与三份index/manifest/handoff已上传并核对名称、字节数、父目录。新增review commit使用独立index从baseline tag构造，原A2_Piper分支/index与训练源码未变。发布上传后生成的prompt/收据只留本地，不回写已上传输入。
