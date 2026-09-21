---
name: novelty-research
status: active
scope: novelty选题、跨版本路线裁定、讨论来源与文档维护
last_verified: 2026-09-21
evidence: INSPECTED — 原会话、人类可读导出、现有plan与实验readout
read_when:
  - 讨论或裁定novelty、恢复图、交互历史适应、coupling critic或Teacher shaping
  - 查找原始Owner想法、Claude与Codex独立判断
  - 产生相关对话、方案、文献比较或方法结论
source_of_truth:
  - scriptsFORhuman/novelty/README.md
  - scriptsFORhuman/novelty/conversations/
  - scriptsFORhuman/v29/pro_handoff/20260921_n02_independent_audit/README.md
  - scriptsFORhuman/v29/a2_piper_v29_n02_plan.md
  - scriptsFORhuman/novelty/documents/20260920_n02_minimal_continuous_adaptation_design.md
  - scriptsFORhuman/novelty/documents/20260910_novelty_status.md
  - scriptsFORhuman/a2_piper_longterm_TODO.md
  - scriptsFORhuman/v28/a2_piper_base_v28_plan_20260909.md
related_entries:
  - base-v27-bilateral-hardening
  - base-v28-camera-aware-rebaseline
---

# Novelty 讨论与路线

2026-09-21：Owner要求把当前N02 plan按workflow交Pro独立审核，附baseline与原novelty路线，明确提出六项concern和多改动归因问题；[原文](../../../scriptsFORhuman/novelty/conversations/20260921_codex_n02_independent_review_request.md)与[交付入口](../../../scriptsFORhuman/v29/pro_handoff/20260921_n02_independent_audit/README.md)已保存。v1.0 FINAL现为待审议技术候选，三类行为目标不等于必须离散模式/分层学习，Pro可替换路线。当前进行有界审阅提交/发布和资料打包，上传完成以receipt为准；GPU4授权保留，无N02实施/运行或模型复算。先前定稿不覆盖本次重新审议要求。

2026-09-21 20:12 HKT：Owner要求逐点回答四问并finalize，明确授权GPU4；[请求原文](../../../scriptsFORhuman/novelty/conversations/20260921_codex_n02_finalize_request.md)与[v29 N02 plan v1.0 FINAL](../../../scriptsFORhuman/v29/a2_piper_v29_n02_plan.md)已保存。三行为共享条件LSTM/decoder，mode one-hot与自phase接在LSTM后，外部1/3指派交错学习；临时skill shaping只教执行器。自主selector为独立categorical PPO，候选固定枚举，return/value只读统一物理r_task，回臂/闭爪等通用mask不得按mode免罚；按真实持续K使用gamma**K，RELEASE尾段成本归首次选择。先可用c→冻结整条表示/归一化/执行链→无头selector→必要时factual后果/冻结头→带预测selector，只更新selector/value；c更新需新版本采集，旧标签不改名，重算hidden不生成反事实未来。Teacher/Student各自闭环和版本。GPU4无需重复申请，额外GPU按具体ablation提出；本轮未实施/运行/测试/提交。

B08现已修复并同步：本轮定向读取[N02共享记录](../../../scriptsFORhuman/v29/B08_SHARED_BASELINE.md)与主任务实施记录，并核对普通/canonical路径删除Stage0在线覆盖的四文件补丁。真实reset、原Stage0默认姿态reward/晋级保留；主任务已有CPU提取路径证明，本轮未复跑，不推出仿真/策略收益。有效开发底座C002+B05+B08，旧冻结运行仍不含B08。较早的B08 OPEN条目是历史。已发布baseline入口另记录7000里程碑LEFT31/32goal、RIGHT31/32到Stage3无Stage4，故6000的0/64不再称最新成绩；本轮只引用已归档入口，不监督或轮询既有运行。

2026-09-21 12:57 HKT：Owner已接受N02首段已握柄push后三候选（N02-D001）与Stage5/完成按身体通过重定义（N02-D002）；[原话](../../../scriptsFORhuman/novelty/conversations/20260921_codex_n02_owner_decisions.md)与[v29 N02 plan v0.1](../../../scriptsFORhuman/v29/a2_piper_v29_n02_plan.md)已保存。完成要求root终点＋真实释放＋全身清离，共同支持握持/撤臂/回柄；stage收入仍逐tick。下一实施包P0先接共同任务和真实动作路径，再原LSTM暴露、有价值时固定c小头、Student自身闭环。两项决定不再待确认；时窗/包络/奖励数值、实现及运行预算尚未批准，本轮仅计划与文档。

计划起点已更新为[已归档C002最终读回](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v29/a2_piper_base_v29_C002_final_readout_20260921.md)：64自然首episode为0/64 goal，LEFT有后段暴露、RIGHT32例均Stage2；不视作合格整任务Teacher，不重跑或诊断归因。共同baseline B08仍OPEN；[N01 plan](/home/baoquanc/workspace/DoorDog-A2_Piper_v29_n01/scriptsFORhuman/v29/a2_piper_v29_n01_plan.md)虽已接受其分支stage-blind合同，方法仍未实施，N02不可假设可用代码。局部后段可以先做，独立Student自然任务前须落实共享执行接口。未监控或接管既有GPU任务/等待，无实施、模型重算、测试、训练/评估、Git提交或外部发布。

2026-09-20 17:02 HKT：N02 planner 在完整 `v29-c002-baseline` 上建立独立 `codex/v29-n02` / `/home/baoquanc/workspace/DoorDog-A2_Piper_v29_n02`，交付[最小设计](../../../scriptsFORhuman/novelty/documents/20260920_n02_minimal_continuous_adaptation_design.md)，待 Owner 裁定。推荐已握柄 push 后段三候选；同一执行者/固定版本 c 的反馈续接，先原 LSTM 行为支持与暴露，再冻结 c 判断 p_useful/身体通过后果读出价值；不混用 Teacher/Student 未来或隐藏真值。新增 body_clear/fully_clear 与 assistance 共同解释握持、撤臂/回柄、Stage5逐 tick 收入和最终完成；Stage5进入语义改变明确列为待决。倾斜搜索和 post-release 重抓建议随后增加，D023仍归N02，N01恢复图未实施。

本轮只补查上述未决接口：Stage5 hold income 在 C002 关闭、夹爪收纳偏好闭合、complete 在 delayed reset 期间为持续收入；现有 v22 clearance 不是全身清离。证据仅 INSPECTED，无实现、模型重算、测试、训练/评估、GPU、预算、Git提交或外部发布；原GPU任务与等待仍归原任务。[原 Pro 材料及更正](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/pro_reviews/v29/20260920_162527__N02_online_adaptation/README.md)仍在主工作目录：42姿态/26解/104方向与PD是Pro CPU材料，本机未复跑；156行压柄夹持界须按45N/18.2N必要界解读而非90N/36.4N容量，仿真限值不作硬件能力。本文没有重算或改原件。

2026-09-20的跨分支上下文（历史）：[N01 最小设计](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/novelty/documents/20260920_n01_minimal_recovery_transfer_design.md)已交付但未实施，当时共享stage-blind接口待采纳；后续决定以本页2026-09-21段及N01 plan为准。下方更早条目保留历史时点状态，不覆盖当前Owner决定。

2026-09-17：v28恢复执行后的closure已完成N01/N02增量复核（D059/X05）。原三seedreach1/3，固定主备DEV均未双侧过门；两方法仍设计CONTINUE、实验DEFER，Owner更急切后续改动优先，未自动定义v29方法排期。[增量复核](../../../scriptsFORhuman/novelty/documents/20260917_v28_closure_N01_N02.md)。

2026-09-14：v28 G1停止点已按D045完成N01/N02回收；两项CONTINUE仅指有界立项设计，实验执行DEFER。N01先建立扰动/失抓有效暴露与完整endpoint，N02先明确可部署输入及含短集/失败集的可辨识门域。X05本次复核义务关闭，方法条目仍开放；无新实验或收益确认。[证据与下次动作](../../../scriptsFORhuman/novelty/documents/20260914_v28_g1_closure_N01_N02.md)。

2026-09-10 Owner建立并要求持续维护 [novelty讨论区](../../../scriptsFORhuman/novelty/README.md)。后续相关AI session须保存对话至`conversations/`、产出至`documents/`或按需新建主题目录，更新README索引，并同步本entry的description/TODO/DONE；跨阶段计划仍在原位维护。历史原话、提议、Owner决定和实验结论分别标明，不把归档变成新实验授权。

## 已核对的讨论来源

- Claude Code：`e09e9a1e-287d-44ec-8975-3e4afdc682c4`，原名Main，后为base_v26-7总结continuation的Branch标题；2026-09-05 03:19起提出三条想法，08:27给出裁定。`592fc504-dd4b-49f2-9996-843c39c4fc68`含同段分支记录，不重复归档。
- Codex：[执行 base_v26-8 训练评估流程](codex://threads/01a06769-5a89-7780-8705-c7035834dd29)，2026-09-05 03:28–03:49，Owner要求独立比较并使用`-Astra`后缀。
- 两份人类可读原文和2026-09-10回顾已存讨论区；每份注明来源与范围，不含内部推理、工具输出或系统指令。

## 当前可复用结论

近期方法切口为N-01恢复图＋失效边界采样；N-02交互历史状态估计为后续科学主线；N-06 coupling critic暂缓；N-07b Teacher shaping的配对蒸馏仍待研究。

v27恢复pilot为UNRESOLVED（R1缺endpoint、可用R2注入loss稀少）；shadow estimator只支持有限的模拟数据离线可辨识性，不代表actor在线适应。详细证据与数字从[状态文档](../../../scriptsFORhuman/novelty/documents/20260910_novelty_status.md)路由。

2026-09-09 v28 D-01已将N-01/N-02顺延v29；旧Astra/Claude文档的“v28方法实验”是历史排期。Teacher碰撞包络C_T与Student光学C_S分阶段冻结已由Owner于2026-09-11按D30批准，base单/双和真实光学/CAD仍在蒸馏前决定；不再标为PROPOSED。

2026-09-12 17:18 HKT（修改：-codex planner；依据：-owner，v28 D038）：v28 closure成功或失败均触发下一planner主动复核N01/N02。N01先决定是否重新立项pilot、重设计扰动/loss，取得新证据后再讨论多seed；N02复核可部署传感、可辨识性与适用门域（含v27未收敛门域），记录继续/延期/关闭，不把完美Teacher或最终相机无限前置。此处更新的是回收入口，未证明方法收益，也不授权新实验；当前跨阶段合同见[v28决策日志](../../../scriptsFORhuman/v28/a2_piper_base_v28_decision_log.md)。
