# Pull v28 4096重建交接（2026-09-14）

- [当前m5 team重启prompt](a2_piper_pull_v28_4096_team_restart_prompt_20260914.md)：交给pull机器AI实际执行；先识别已取消初始化输出，禁止重复运行已完成阶段。
- [同步plan](a2_piper_pull_v28_baseline_sync_plan_20260909.md)与[决策记录D001–D016](a2_piper_pull_v28_decision_log_20260913.md)：保留m5 D007–D015执行历史；D016固定三个独立4096 scratch seed、GPU1/2/3训练和GPU0评估队列。
- [真实切换记录](m5_handoff_4096_20260914/scriptsFORhuman/pull_v28/evidence/pull_v28_rebuild_4096_20260914/TRANSITION.json)：旧1024三格1284/1280/1296，共3860 batches，编号checkpoint均1250，原始输出保留。
- [交接状态](m5_handoff_4096_20260914/.ai/runtime/pull_v28_rebuild_4096_20260914/ACTIVE_RUN.json)：全部训练已停止，新4096 PA_S1初始化attempt1按Owner最新要求取消，0 completed batch；S2/S3与队列未启动，无4096吞吐/ETA。

m5 canonical：`/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/scriptsFORhuman/pull_task/`。配置与launcher已在m5准备，运行由接手AI按prompt完成；GPU0现有无关ForceControl-lightnav进程保留。P2 18/18和G0 10/32证据不重复，本次未commit/push，未操作主线v28运行。GPU1本地pull目录仅作相关文档与memory镜像。

[20260913输入清单](SHARED_INPUTS_MANIFEST_20260913.json)与[交付receipt](SHARED_INPUTS_RECEIPT_20260913.json)保留为历史接收证据，不代表此次4096 runtime通过。
