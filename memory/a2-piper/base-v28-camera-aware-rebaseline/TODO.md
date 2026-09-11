# TODO

- G0 launch门和首个本地commit已完成（未push）；下一阶段为G1。实际commit状态由v28 runtime的g0_decision与first_commit_receipt路由。修改：-codex worker；依据：-owner。
- G1 warm probe仍必做：完整MERGED/140mm/新姿态/夹紧/bundle/K，500batch；失败STOP交Owner。尚未启动G1/Wave A/B。
- X24保留：冻结walk harness的seed282没有引入随机实现，不能据此关闭随机校准；后续需要有真实随机暴露的校准设计，不能静默修改已冻结harness。
- X25与X19关联：臂前伸时pitch/roll/yaw耦合残余增16–23%，Wave A Stage2/3若位姿不稳需结合此已知因素解释。
- PPO/eval已完成26字段接线，但短策略只到Stage0；Stage2–4可见率、释放回位、越门yaw、Stage5方位的真实事件覆盖待后续正式评估。无样本必须保留null。
- G2-C1/C1′/C2/C4、base单/双布局、最终光学安装与安装件交换检查留到蒸馏前；旧v27 C3 FAIL保留，Wave A后检查v28真实轨迹。
- A_S284(target_stage=5)已预注册；是否取得选种资格未明确前，不扩大A_S281–283路由。
- 后续Wave A/B、readout/closure与其余commit按plan；不push、不改G7或进行硬件动作。X08 camera worktree授权属独立lane。
