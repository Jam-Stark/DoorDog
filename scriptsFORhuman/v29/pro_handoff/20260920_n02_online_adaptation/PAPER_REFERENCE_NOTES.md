# 指定论文的一手入口与阅读边界

访问：2026-09-20 HKT。Codex与一个只读context researcher核对身份及关键段落；以下是简短阅读线索，不是N02架构推荐。没有复制论文全文/PDF，Pro需独立阅读全文并继续查找反例/替代。

## UniFP

准确题名：*Learning a Unified Policy for Position and Force Control in Legged Loco-Manipulation*，arXiv:2505.20829v2（2025-10-04）。[论文](https://arxiv.org/html/2505.20829v2)、[作者项目页](https://unified-force.github.io/)、[作者代码](https://github.com/unified-force/UniFP)。

§3.2将姿态、关节状态、上一动作、command和历史编码用于状态/外力估计与力位控制；§3.3还含使用估计力的上层视觉模仿。它既不是单独的未来力预测器，也不是只定义一个fusion网络。区分底层PPO力位策略与上层force-aware imitation的输入/输出；§4和附录给出B2-Z1、G1及接触操作实验，§6/附录讨论模型与交互范围限制。[方法与实验原文](https://arxiv.org/html/2505.20829v2)

对本项目的待研究问题：可借鉴哪些目标/数据/力位控制思想；现有A2高层动作不是同一command接口，门的持续抓柄、回关和通行是否满足其假设。不能把平台相近当成C002能力证据。

## SixthSense

准确题名：*SixthSense: Task-Agnostic Proprioception-Only Whole-Body Wrench Estimation for Humanoids*，arXiv:2605.01427v1（2026-05-02）。[论文](https://arxiv.org/html/2605.01427v1)、[作者主页](https://0aqz0.github.io/)。本次未找到可核验的专属官方代码仓库，不据此断言不存在其他未公开实现。

§IV/V-B使用q、qdot、归一化torque及IMU等信号，省去显式command/previous action；目标是身体区域contact mask与wrench。§V-A为观察窗对应的同一时间段接触序列，不应默认当成未来预测。采用conditional flow matching；§V-F报告G1实机50帧/50Hz输入、约100M参数、10次refinement、每次forward约0.5s，标签来自仿真及带力传感的实机采集。[输入、时间窗和实机段落](https://arxiv.org/html/2605.01427v1)

对本项目的待研究问题：torque的部署可用性、同窗重建与在线因果延迟、稀疏外部接触与持续抓柄/步态接触的差别。门操作是否需要完整分布式wrench应由控制目标决定；不要照搬G1区域数、CFM或把作者的实时表述当成本机控制时限已满足。

## 两项研究怎样参与选型

请比较目标、动作条件、监督、可部署输入与控制使用方式后，再讨论网络。也应比较当前LSTM、辅助监督和更简单目标。上述工程适用性问题是本地提出的待验证推断，不是论文已否定或肯定A2-PiPER的结论。引用数字时注明论文版本/条件，不把它们变成C002的实验结果。
