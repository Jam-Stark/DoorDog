# C002同配方续训至8000：最终验收与自然评估结果

2026-09-22 11:08 HKT；PLANNER，D077。**D074授权的6000→8000续训及7000/8000两次自然评估交付已接受并关闭。8000本次自然评估LEFT32/32、RIGHT32/32，共64/64 goal。** 保留冻结C002实现验收；这是同seed有限样本的实际任务结果，未新增Teacher/G7绑定或跨seed/硬件资格。

| 累计iteration | LEFT goal | RIGHT超过Stage2 | RIGHT到Stage4+ | RIGHT goal | 总goal |
|---|---:|---:|---:|---:|---:|
| 6000 | 0/32 | 0/32 | 0/32 | 0/32 | 0/64 |
| 7000 | 31/32 | 31/32 | 0/32 | 0/32 | 31/64 |
| 8000 | 32/32 | 32/32 | 32/32 | 32/32 | 64/64 |

## 已核对的交付证据

Main一次核对实际train/eval8000 receipt的argv、cwd、worker与Owner计划一致，均exit0；训练包含初始化和7000暂停评估共60094.097s（16.693h），在原20h上限内；最终eval619.306s，在1200s上限内。实际训练end capture为global_step8000、4096env；实际full loader为exact8000、actor/RMS与value严格加载，并恢复optimizer/scheduler/trainer。worker单次CPU读回actor20/value19个tensor有限，Main未重复加载模型；PPO数值loss仍NOT_OBSERVED。

一个独立只读reviewer核对原始64条per-env、metrics、terminal diagnostics与runtime config：env_id恰为0–63、各侧32、全部seed291；64 goal/complete，max/final stage均5。全部terminal `v26_3.staged_load_count_total=0`，staged store/restore-cache-clear也均0；natural enabled、staged disabled、exact64协议支持首回合自然评估。episode长度431–982控制步，均值654.40625；详细reset前序未独立重建。

六个导出门字段按env_id与6000逐项一致：side sign/label、hinge drive cap、handle drive cap、handle height、door weight。未导出family/最大开角标签，不能作相应分组验证或宣称完整物理/RNG配对。7000的同trainer PID暂停/继续及其自然评估已由D076登记，本轮保留。

## 对此前左右失衡判断的更新

这条同配方续训轨迹中，LEFT先改善，RIGHT随后从Stage2到Stage3再到完整goal；6000时观察到的左右差距没有在本次8000人口中永久保留。6000 RIGHT周期性开爪打断K5的逐步证据仍有效，但它是旧checkpoint的失败模式，不能继续作为8000的当前阻断。

目前不需要为解决“本次8000仍左右失衡”而立即加入动态LEFT/RIGHT配额、逐侧PPO归一化或v27 recovery bank，因为这个前提已被本次结果更新。若以后研究样本效率、seed可靠性或扩域，需另定比较目标。未做相应单因素干预，也不能将改善严格归因于迭代数这一单独变量；初始full resume曾natural reset并重建staged bank。

B08修复没有进入这次实验，不能把64/64归给B08；也不能由此证明B08对其他接口/任务无影响。单seed的64例不等于总体成功率100%、跨seed稳定性、全部把手族通过或硬件成功；未自动增加训练额度。

## 关闭与下一范围

训练03:42:35 HKT结束，最终eval03:52:55结束。worker已于03:55:38释放本任务GPU0租约并将team task标completed；Main只读ledger确认，没有重复释放。worker报告实际GPU0进程查询为空，Main未重复查询。当前逻辑等待关闭，按D062/D066通过现有STATE与文件事件发布D077，无queue副本或routineACK要求。

GPU1 HA-C001保持D067原范围和等待。其同6000对照仍使用原A6000，不能静默换成A8000。任何额外训练、独立seed评估、方法实施或绑定调整由Owner决定。

正式决定：[D077](/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/v29_baseline_team/D077_C002_RESUME8000_FINAL_ACCEPTANCE.json)；worker原报告：[FINAL_REPORT](/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/v29_resume8000/FINAL_REPORT.md)与[最终归约](/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/v29_resume8000/final8000_readout.json)。原始[per-env](/home/baoquanc/workspace/DoorDog-A2_Piper/logs_eval/base_v29/push_baseline_C002_seed291/natural_resume_8000/a2_v14_per_env_records.json)、[metrics](/home/baoquanc/workspace/DoorDog-A2_Piper/logs_eval/base_v29/push_baseline_C002_seed291/natural_resume_8000/metrics_eval.json)、[full loader](/home/baoquanc/workspace/DoorDog-A2_Piper/logs_eval/base_v29/push_baseline_C002_seed291/natural_resume_8000/v29_checkpoint_load.json)。最终checkpoint：[model_step_008000.pt](/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/a2_piper_full_stage_a2_base/base_v29/push_baseline_C002_seed291_resume8000/model_step_008000.pt)。
