# v29 baseline / v28 Pro 交付

2026-09-18（HKT）。状态：**PUBLISHED_AND_UPLOADED / PRO_RECEIVED / OWNER_DISCUSSION_OPEN**。

Owner已回传Pro附件；[原包/原文与本地核对](../../../pro_reviews/v29/20260918_102906__baseline_and_v28_pro_review/README.md)已归档，六项未决。下方保留原交付信息。

- [可复制给Pro的完整prompt](PRO_REVIEW_PROMPT.md)
- [Owner问题与范围](OWNER_REQUEST.md) · [详细研究说明](RESEARCH_BRIEF.md)
- [Drive任务目录](https://drive.google.com/drive/folders/11DvqGjIBMeRXdWYM2uVOBt9E-4KpUazy)
- [独立Git审阅分支](https://github.com/Jam-Stark/DoorDog/tree/codex/v29-baseline-pro-20260918)
- [本地交付索引](../../../../.ai/outgoing-artifacts/base_v29_baseline_and_v28_review/20260918_003823__v29_baseline_review/worker_delivery__BUNDLE_INDEX.md) · [上传读回凭据](../../../../.ai/outgoing-artifacts/base_v29_baseline_and_v28_review/20260918_003823__v29_baseline_review/UPLOAD_RECEIPT.json)

Git发布为单独review分支，只收选定source/config/docs与v29资产；原A2_Piper工作分支和其他未提交改动未被提交或合并。本次review提交主题为`Prepare v29 baseline research and v28 review handoff`，时间`2026-09-18T00:39:09+08:00`；已验证远端tracking与review HEAD一致。按Owner约定不写哈希清单。

Drive包含三个普通ZIP（source/config约18.54MiB、logs/metrics约1.64MiB、visual evidence约15.62MiB）和三个索引/manifest/handoff文件；六文件均已按目标目录读回核对名称与字节数。未包含checkpoint，未运行新的训练/评估/render。

Owner已将Pro附件传回本地任务，完成只读核对并追加baseline TODO。Pro判断、参数来源、工程候选与local-only边界分列，继续等待Owner逐项决定；未自动实施或启动实验。
