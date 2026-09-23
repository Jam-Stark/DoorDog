# Pull v28 当前启动入口（2026-09-14更新）

旧1024启动内容已由V28P-D016替代。请完整读取同目录的：
[a2_piper_pull_v28_4096_team_restart_prompt_20260914.md](a2_piper_pull_v28_4096_team_restart_prompt_20260914.md)

当前合同为三seed各4096env×6000，GPU1/2/3训练、GPU0串行评估；已完成P2/G0不重跑。旧1024已取消并单列保留；若新4096组已启动则接续，禁止重复重启。本次不commit/push，D013工程接线自主修复权限保持。实际状态以m5的TRANSITION、ACTIVE_RUN和receipt为准。
