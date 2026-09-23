# 给Pro：B02解锁机制二选一＋B04最大开角限制设计

你是DoorDog A2+PiPER项目的独立Pro决策与设计者。请完成下面的选择和设计，不只列研究计划。中文回答，用源码与一手API/产品资料支持关键判断；不输出内部推理过程，只给可检验理由。

## 最新Owner范围

1. **B02：A软件约束虚拟锁闩 / B保留当前物理解锁，二选一。** 列优劣，明确选一个，并给所选方案的最小完整设计。此前Owner和本地team偏好软件，现在已经重新开放选择；20–60°解锁、+5°机械余程只是候选，不是必须服从的参数。
2. **B04：同时判断门最大张开角随机化应使用哪种限制方式。** 先区分每步强制角度裁剪/重写状态、原生joint limit、实体门挡碰撞。原生joint limit虽由软件设置，仍是物理求解约束；不要把它和直接改状态混称“软件限制”。给出明确推荐及设计。
3. **B03已后置。** 保留当前base双D435i上仰15°，等v29 baseline出来后再微调；不得重新把25°候选、相机研究或新增render作为本轮前置。

## 已发布并上传的材料

- 仓库：[Jam-Stark/DoorDog](https://github.com/Jam-Stark/DoorDog)
- 专用审阅分支：[codex/v29-b02-b04-pro-20260918](https://github.com/Jam-Stark/DoorDog/tree/codex/v29-b02-b04-pro-20260918)
- 提交主题：`Prepare v29 B02 and B04 Pro decision handoff`
- 提交时间：`2026-09-18T17:14:54+08:00`。本地已验证review分支、远端tracking与远端分支一致；按Owner约定不提供哈希清单。
- 本次唯一[Drive目录](https://drive.google.com/drive/folders/1RfrGhpw4hsi-FElR7Fc9L4UIrWjuuOBt)
- 路径：`Pro_Space/DoorDog/A2_Piper/base_v29_b02_b04_decision/20260918_170419__b02_b04_decision/`

五个文件均已上传并按名称、字节数及父目录读回核对：

1. `worker_delivery__BUNDLE_INDEX.md`
2. `worker_delivery__BUNDLE_MANIFEST.json`
3. `worker_delivery__PRO_HANDOFF.md`
4. `worker_delivery__source_and_configs.zip`（438863 bytes，35个文件）
5. `worker_delivery__reference_and_evidence.zip`（63988 bytes，10个文件）

两个ZIP是可独立解压的普通ZIP，不需要拼接。项目文件保留repo相对路径；本机IsaacLab方法节选在`dependency_evidence/ISAACLAB_LIMIT_API.md`。review分支继承的其他文件不自动等于当前工作区，优先使用manifest列出的本次材料。若材料读取受限，明确列出未读部分，不假称核验完成。

先读source包中`scriptsFORhuman/v29/pro_handoff/20260918_b02_b04/OWNER_REQUEST.md`、`REVIEW_BRIEF.md`与`SOURCE_INDEX.md`，查看当前source/config并形成独立初判，再读`LOCAL_CONTEXT_AND_OPTIONS.md`、baseline plan和旧Pro相关原文。旧报告只作为B02/B04参考，不承接其v28验收或六项全量研究任务。

## B02必须完成的判断

当前链路是handle转动→mimic滑块→高位cone与门框碰撞/脱离→hinge可转。它确实由latch物理阻挡，不是现成Boolean解锁开关。handle当前0–45°，latch0–30mm；0.6rad是reward尺度，另一活跃creation路径还固定45°截断/归一化，均不是精确物理解锁阈值。

比较A/B的解锁可控性、接触/受力反馈、实现与维护成本、并行环境成本及未知项、角度随机化可行性、自然/staged恢复、观察信息与N02关系。B保留当前代理结构并做必要有限改动，不默认要求精细重建实际锁体；A若用原生物理约束也不能称作直接瞬移门状态。

最终必须选A或B，给出：

- 锁住、解锁、门打开后handle回位、关门复锁的状态/事件；允许游隙与实际物理约束接口。
- 解锁角、机械止挡、回位负载及联合采样规则；独立判断0–45°、20–60°和其他有限候选，不生成阈值超过行程的门。
- baseline能否允许“压到底再试推”作为统一策略；推不动如何与重门/闭门器/摩擦区分。不要给actor/Student直接加入解锁阈值/锁态答案，也不默认写脚本替代policy试推。
- 所选方案在具体source中的接入/删除路径、物理步时序、reward/telemetry与reset/staged bank处理。A需处理第三DOF和`build_latch`与self-collision的耦合；B需协调mimic/stroke/几何脱扣。
- 少量关键local-only验证点，不把两套都实现、庞大测试矩阵或新增神经网络设为先决条件。

本机IsaacLab有batched joint limit setter，但普通PhysX articulation limit要求lower<upper；不能把`[0,0]`当作已证明可用的锁定。A的`[0,epsilon]↔[0,theta_max]`仅是候选，尚无运行证据。B的精确脱扣角/余量也未测定。缺少运行证据时仍给出有依据的推荐选择，并列出可能改变选择的关键未知，不虚构验证结果。

## B04必须完成的判断

当前150°上限直接写入USD RevoluteJoint，由solver处理。90–150°是待决工程覆盖域。请明确选择强制状态裁剪、原生joint limit或实体stopper中的推荐方式，给角度域/分布、采样时机、API及degree/rad口径、左右侧和reset/staged规则。

尤其说明与B02如何配合：如果解锁方案临时收紧门轴约束，必须保存并恢复本门真正的最大开角，不能拿锁住时的窄限位当正常上限。

当前Stage3→4为hinge>0.25rad＋握持；release gate约1.2rad；Stage4→5还需hinge>1.0472rad、handle<.2rad及root_x>0。hinge位置reward在约90°饱和只是奖励计算，并非物理限位。90°高于门槛不证明实际通行成功。随机最大角不自动解决“开到各自挡止才松手”；请分清限位、允许释放gate、实际断触和过门行为，指出必要的最小联动修改。

## 共同背景与证据边界

B01已批准三档门重30–80/80–120/120–160kg各1/3、有/无闭门器各半及门轴松紧，但新物理域尚未实施；current config仍是旧80–120kg/drive/native摩擦off。当前Teacher有LSTM、门角/把手角/交互反馈，并接收质量与几何真值，不含closer/friction/解锁阈值真值。不能把Teacher观察等同部署Student感知。

当前30s时限、新自然起点和Stage0平滑速度已经实现，只有静态/CPU证据。9月17日64-env/one-batch是旧接线记录，不证明新B01/B02/B04可学性。没有本次A/B训练对比或新最大角运行。不要声称读了未入包的checkpoint、GPU状态、硬件或重跑仿真。B05另议，N01/N02方法实验和v28重新验收不在范围，不制定训练预算。

## 最终输出

对话中先用两行明确写“B02选择A/B”和“B04选择何种限制”，然后给紧凑优劣表、关键设计参数与必要未知。不要以“都可以/以后再决定”代替所要求的选择。

同时在Pro对话附普通ZIP **`pro_delivery__full_review.zip`**（压缩后≤95MiB），至少包含：

- `FULL_REVIEW.md`：完整比较、选择与理由、source/API依据、证据/推断/未知/local-only区分。
- `DESIGN_SPEC.md`：所选B02/B04的统一设计，参数、状态、事件、reset、reward/observation和具体source改动一致。
- `LOCAL_WORKER_PARSE_PROMPT.md`：与下面复制给本地Worker的文本逐字一致。

Owner会下载附件并传回本地；**不要将Pro结果上传Drive**。若不能附ZIP，明确`NOT_ATTACHED`并提供可取得的文件，不虚构URL。不生成哈希清单。

### 复制给本地Worker的接手prompt

请按项目AGENTS与memory入口接手Owner在当前对话上传的`pro_delivery__full_review.zip`。这是v29 B02/B04独立决策回包：来源仓库`https://github.com/Jam-Stark/DoorDog`，review分支`codex/v29-b02-b04-pro-20260918`，提交主题`Prepare v29 B02 and B04 Pro decision handoff`，提交时间`2026-09-18T17:14:54+08:00`。对应Worker输入目录为`https://drive.google.com/drive/folders/1RfrGhpw4hsi-FElR7Fc9L4UIrWjuuOBt`，但Pro回包以本次附件为准，不去Drive找答案。

在`scriptsFORhuman/pro_reviews/v29/`下建立新的B02_B04独立目录，保存原ZIP并解压FULL_REVIEW、DESIGN_SPEC与LOCAL_WORKER_PARSE_PROMPT。先读Pro对B02的A/B选择、B04限位选择与联合设计，再对照当前source/config、本机IsaacLab及已有runtime做定向可行性核对，保留原文、出处与证据等级，不覆盖本地较新的改动。重点核对锁态/复锁、原生限位API、角度与单位、实体latch/mimic拓扑、三DOF/natural/staged恢复、固定0.6rad与45°reward尺度，以及正常最大角和临时锁定限位的区分。

按最新Owner范围：B03保持15°并后置到v29 baseline出来后，不重新设相机/render前置；B01三档等权及closer有无各半沿用。将Pro选择、采用/调整意见与必要未知写入baseline plan/TODO及决策记录；旧软件偏好不能预设最终答案。云端静态结论不能冒充运行或训练PASS。当前接手限于解析与定向核对，不自动实施、启动训练、添加大规模测试、划掉未确认项、更新Teacher/G7或重开v28验收；实现按Owner后续指示推进。
