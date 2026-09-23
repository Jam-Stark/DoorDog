# v29 B02/B04 Pro决策包

2026-09-18 HKT。状态：**PUBLISHED_AND_UPLOADED / PRO_DECISION_PENDING**。

- [可直接复制给Pro的完整prompt](PRO_REVIEW_PROMPT.md)
- [Drive决策包目录](https://drive.google.com/drive/folders/1RfrGhpw4hsi-FElR7Fc9L4UIrWjuuOBt)
- [独立审阅分支](https://github.com/Jam-Stark/DoorDog/tree/codex/v29-b02-b04-pro-20260918)
- [Owner原话与范围](OWNER_REQUEST.md) · [研究说明](REVIEW_BRIEF.md) · [source索引](SOURCE_INDEX.md) · [事实与候选](LOCAL_CONTEXT_AND_OPTIONS.md)
- [本地交付索引](../../../../.ai/outgoing-artifacts/base_v29_b02_b04_decision/20260918_170419__b02_b04_decision/worker_delivery__BUNDLE_INDEX.md) · [上传核对凭据](../../../../.ai/outgoing-artifacts/base_v29_b02_b04_decision/20260918_170419__b02_b04_decision/UPLOAD_RECEIPT.json)

B02要求软件约束A/当前碰撞锁舌+mimic物理解锁B明确二选一，列优劣并给所选设计；B04要求区分强制状态裁剪、原生joint limit、实体stopper后选择随机最大角实现。B03已后置到baseline出来后，当前15°保持，不作前置。

发布提交主题`Prepare v29 B02 and B04 Pro decision handoff`，时间`2026-09-18T17:14:54+08:00`；review分支、远端tracking与远端分支已核对一致。使用独立Git index提交选定14个变化路径，原A2_Piper分支与原index未用于该提交，没有合并无关改动。

Drive包含两个普通ZIP（source/config 438863 bytes、参考/证据63988 bytes）与三个索引/manifest/handoff文件；五文件均完成名称、字节数、父目录读回核对。无checkpoint或新训练/渲染。当前resolved仅解析，旧one-batch明确标为9月17日历史证据；新B01/B02/B04物理方案尚未实施。

源码快照先发布，随后完成上传并生成本prompt和交付收据；后生成的本地交付记录不回写已上传的不可变输入包。Owner将prompt提交Pro，Pro以对话附件返回`pro_delivery__full_review.zip`，再由Owner传回本地任务。
