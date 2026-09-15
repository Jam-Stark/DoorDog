# Pull v28：2048合同确认与GPU1故障交接

更新时间：2026-09-15 05:49 HKT。

Owner D017 的条件已满足：2048通过三格正式启动验证，plan已改为每seed2048env。当前S2/S3继续运行；没有回退1024，没有commit/push。

## 配置与输出

PA_S1/2/3分别GPU1/2/3，seed1/2/3；各6000batches、save250、null scratch/full/auto_load_latest=false，H64、5 PPO epochs、4 minibatches、lr1e-4。pull named reset快照显式CPU存储，live状态仍GPU，原shape/dtype/200容量/reset采样、reward、事件、ready与Stage4均不变。GPU0串行执行4milestone双侧exact64共24lane；不终止无关ForceControl进程。

活动组：`pull_v28_rebuild_2048_20260914`。三训练和队列均attempt1；详见ACTIVE_RUN.json及PA_STARTUP_AGGREGATE.json。

## GPU1真实故障与可恢复状态

PA_S1实际完成1050batch后，于2026-09-14T19:04:21Z报CUDA unspecified launch failure。`nvidia-smi -i1`返回6，PCI82:00.0的设备句柄Unknown Error；lspci仍列出设备。尚不能确定物理或驱动根因，不当作2048容量OOM。

S1失败后卡在Isaac退出，supervisor仍显示RUNNING，直到Main在预计M1500决策时间检查到日志与GPU错误。已仅取消S1并清理其残留PID706323，未resetGPU/重启m5，未影响S2/S3或外部GPU0任务。

本组明确路径`logs_rl/a2_piper_pull_v28/pull_v28_rebuild_2048_20260914/PA_S1/last.pt`在CPU加载确认：global_step=1050，完整policy/value/optimizer/lr_scheduler/env_state/trainerstate。恢复设备后可从同一2048lineage继续剩4950batch，不用旧1024checkpoint。编号checkpoint到1000，last为1050。后续partial另记，不冒充已完成。

核对过程的worker曾误选历史1024的1250checkpoint，Main已用上方明确2048路径纠正GPU1_HARDWARE_FAILURE_20260915.json；当前S1恢复点是1050。

## 仍在运行与边界

S2/S3上次决策检查到1432/1444，均正常继续，估计距6000约29小时；GPU0队列仍运行并等待外部资源。S1的ETA在设备恢复前不可给出。原三seed6000 opening未形成，不发布0/3或NOT_ESTABLISHED；缺失/INVALID独立报告。P2 18/18与G0累计10/32继续复用。

4096撤回组1完整batch及后续partial、旧1024组3860均保留历史，不混入本组终点。此次只暂停GPU1相关工作；原prompt明确将硬件/外部资源决定交Owner，因而未自行reset或重启有其它任务的m5。下一步需要Owner恢复GPU1或明确替代硬件安排。
