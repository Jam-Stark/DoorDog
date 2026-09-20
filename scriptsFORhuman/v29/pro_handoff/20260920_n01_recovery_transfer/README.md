# N01 Pro预研输入包

2026-09-20 HKT。研究范围：完整v29 C002保留B05，独立重设计恢复图、抗干扰Teacher与恢复能力向Student的传递。当前只交付研究资料，未实施N01或运行新实验。

- [Owner五项原始要求](OWNER_REQUEST.md)
- [完整研究brief](../../../novelty/documents/20260920_n01_v29_c002_pro_research_brief.md)
- [当前源码与证据事实](LOCAL_FACTS.md)
- [source/evidence导航](SOURCE_INDEX.md)
- [补充源码与baseline tag的直接比较](SUPPLEMENTAL_SOURCE_BINDING.json)
- [Pro回包后的本地接手文本](LOCAL_WORKER_PARSE_PROMPT.md)

交付遵循三个独立ZIP：C002完整冻结输入及必要依赖；本次问题/事实/已存runtime证据；历史novelty参考。先独立形成恢复与传递方案，再读历史参考。不要把C002实现已接受等同成熟Teacher，也不要把GPU1旧把手消融当主底座。

基座tag `v29-c002-baseline`；审阅分支 `codex/v29-n01-pro-20260920`。发布、上传及可直接复制的Pro prompt由完成后的本地交付记录给出；不得从本页预先推断已上传。源包不含checkpoint/策略权重或本机Isaac环境，供源码阅读和方案研究。
