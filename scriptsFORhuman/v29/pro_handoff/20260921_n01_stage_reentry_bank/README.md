# N01 Stage重入与bank独立Pro输入

2026-09-21 HKT。Owner已要求按workflow正式打包上传，并明确设计偏好：**效果优先，简单高效、避免过于复杂的状态机是可以让步的偏好。** primitive不预设动作原语架构。

本目录保存发布前可审阅的输入说明；实际Git发布、上传结果和最终Pro prompt由交付完成后的本地`PUBLICATION.json`、`RELEASE_POINTER.json`与`PRO_REVIEW_PROMPT.md`记录，不从准备文件推断已经上传。

- [Owner问题与准确偏好](OWNER_REQUEST.md)
- [独立审阅问题](REVIEW_QUESTIONS.md)
- [当前源码与证据事实](LOCAL_SOURCE_FACTS.md)
- 源导航：`SOURCE_INDEX.md`
- [Pro回包后的本地接手文本](LOCAL_WORKER_PARSE_PROMPT.md)

选定源码来自当前N01工作树，保留完整C002+B05，另纳入已经存在的Stage0 delta覆盖移除；本次打包不修改生产实现。N01恢复路由、主动bank和Student传递仍未实施。

输入按当前source/config、当前问题/直接证据、历史参考三份普通ZIP分组；每份压缩后≤95MiB。Pro先读问题和当前源码，独立判断后再读本地建议与旧Pro答案。Pro将`pro_delivery__full_review.zip`附在对话，由Owner传回本地；不将Pro答案上传Drive。
