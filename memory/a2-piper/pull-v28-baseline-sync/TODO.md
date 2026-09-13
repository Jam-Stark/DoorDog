# TODO

- **当前Owner门**：G0 attempt2已产生policy读数并完成5迭代，但没有checkpoint，runner返回1；依计划§8不得自动重跑。等待Owner授权仅修复smoke保存间隔为5及一次新5batch attempt。
- `OWNER_PROPOSED_SMOKE_SAVE_FIX_NOT_APPLIED.patch`尚未应用；原env.robot引用补丁已应用且133/138运行验证成功，不要重复应用旧patch。
- 若获得授权，使用新attempt与新输出目录；累计G0将10 batches≤32。完成checkpoint natural双侧和G0归约，再按原计划PA_S1/2/3各6000及24条natural接续。
- P2/contact/PG7已有证据不重跑；PA当前均NOT_RUN、k=null/3，warm默认NOT_RUN；P3–P5/Teacher/硬件/push不自动执行。
- 本任务资源和事件已收尾。保留全部旧失败输出、D2及无关工作树修改。
