你是 DoorDog v28 本地审计解析员。请读取本次 pro_delivery__full_review.zip 中的 FULL_REVIEW.md，完成只读核对和建议整理。本 prompt 不授权改代码、配置、实验门槛或选择规则，不授权训练、评估运行、Teacher/G7 更新、硬件操作、commit/push 或上传 Drive；不得借旧 plan 的运行预授权自动执行这些动作。

审计基准：
仓库：Jam-Stark/DoorDog
分支：codex/v28-pro-audit-g0-complete-20260912
审计 commit：84358588e2da12a9fae5748cd9da39ac2d9f5a6c
G0 worker 直接父节点：8811c484729b1e9be017c30dcf46d922d1ad5f52
本轮 Drive 目录 ID：1bmymz2ijOesd_Yr0cIHOr4iwcEMl9nUJ
不得混用旧目录 1gKH6DA3KUf6rYGMZY2bV1bzBHHy2j30- 的状态、commit 或 prompt。

先读完整报告，包括固定初判 A、三方交叉 B、最终建议 C、证据边界 D。初判与后续修正必须分别保留，不能把第二包意见倒灌为独立初判。然后用只读 Git 命令确认所在 worktree、当前分支、HEAD、未提交/未跟踪状态，以及相对审计 commit 的已提交和未提交差分；不要 checkout、reset、stash、clean、pull 或覆盖任何文件。本机已发生的新进展应单列，不把审计时的“G1未启动”当作永久现状。

只针对会影响建议的部分读取当前 source/config、plan、acceptance/readout、deferred register、长期 TODO、memory 和已有本地记录。重点核对：G0数值准入与随机校准、遥测接线、晚阶段事件、Teacher资格、硬件能力的边界；select_wave_a 的 endpoint 可靠性与历史候选标签；Wave B 否定范围及固定选种目标；G1失败的既有STOP权限与其科学解释；A_S284资格、原三seed分母及其非同seed因果配对；固定 staged_reset 比例的授权边界；N01/N02、X24/X25和重复/陈旧待办的未来承接。对每项意见独立判为“当前仍成立、被后续证据取代、证据不足或不采纳”，不要按三方多数票执行。

优先按报告 M1–M5 整理最小修订草案。默认不新增风险梯、8000-batch延长、随机校准、全面测试、护栏、workflow设施或实验矩阵，不自动启动可选长臂。不重写历史FAIL/D36/D37，不因X24 OPEN、未附完整trace或后移G2而新增生产STOP。未知的完整trace、source快照/二进制、本机环境、GPU和硬件事实标 LOCAL_CHECK_NEEDED；只读已有材料能解决的才核对，不能以补验证为由启动实验。

仅在回复中交付：当前HEAD/diff摘要；逐项建议取舍及依据；最小修订表（文件路径、现有问题、建议文本、证据、是否需要Owner授权）；现在与条件触发后分别需要Owner决定的事项。尤其说明是否继续保留“固定最早reach候选、接受可能无Teacher”的目标，以及A_S284等备用分支何时需明确资格。默认保留现行实验合同；未经Owner进一步明确授权，不应用草案，不改选择身份或门值，不启动训练。
