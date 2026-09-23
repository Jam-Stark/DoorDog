# B08：Stage0 机械臂动作覆盖修复与公共分支同步

更新：2026-09-21 14:36 HKT。V29-D075；Owner要求“补充完成B08的修复，同时一并更新到N01，N02，B05-ablation 分支”，并要求参考N01、保持公共逻辑一致。

**实现完成，四个开发worktree已同步同一份公共补丁；均为本地未提交改动，未push。** Stage0现在与其他阶段一样接受policy的六维arm增量，逐步积分后形成关节目标。真实episode reset继续初始化累计target及动作历史。当前只证明源码实现与CPU动作链，未运行新增仿真、训练或评估，尚无策略收益结论。

## 改动

- `DeltaActionBase.step`删除无用的override hook及调用；保留原增量记录、积分、限幅和关节目标映射。
- `DoorPregrasp`删除按Stage0覆盖六维累计arm target的实现，以及canonical step中的同类调用。
- `a2_v26_4_accumulate_physical_delta`删除`stage0_mask`参数及在线写回physical origin；普通与canonical路径共享相同执行合同，RIGHT仍使用原镜像映射。
- 现有`v26_4_r2_c_identity_proof.py`删除已经失效的Stage0清零断言，保留累计、映射、限幅及reset原点检查。没有新增测试框架或配置开关。

N01当前计划已要求共享stage-blind动作接口；同步前检查到其公共源码仍有Stage0覆盖，没有另一份已完成实现可复用。本次统一公共底座，不引入N01专用分支逻辑。Stage0默认姿态reward和晋级条件保持；B08不等于整个N01 stage-blind方案已经实现。

## 开发目录

| 方向 | 分支 | 修复后的开发worktree |
|---|---|---|
| baseline B08 | `codex/v29-b08-stage0-arm` | [DoorDog-A2_Piper_v29_b08](/home/baoquanc/workspace/DoorDog-A2_Piper_v29_b08) |
| N01 | `codex/v29-n01` | [DoorDog-A2_Piper_v29_n01](/home/baoquanc/workspace/DoorDog-A2_Piper_v29_n01) |
| N02 | `codex/v29-n02` | [DoorDog-A2_Piper_v29_n02](/home/baoquanc/workspace/DoorDog-A2_Piper_v29_n02) |
| B05-ablation | `codex/v29-handle-ablation` | [DoorDog-A2_Piper_v29_handle_ablation_b08](/home/baoquanc/workspace/DoorDog-A2_Piper_v29_handle_ablation_b08) |

N01原有未提交C002改动与N02已有工作保留。由于原baseline和B05-ablation任务仍会从各自cwd启动后续评估，本次没有原地替换这些运行输入：

- GPU0 C002/D074继续使用`/home/baoquanc/workspace/DoorDog-A2_Piper`原源码；baseline修复在上表独立worktree。
- GPU1 HA-C001/D067继续使用`/home/baoquanc/workspace/DoorDog-A2_Piper_v29_handle_ablation`原源码。该旧worktree已在同一版本detach；`codex/v29-handle-ablation`开发分支转到上表`_b08`目录。
- 原`v29-c002-baseline`、`v29-handle-ablation-c001`标签及运行/最终评估配方不变；现有结果不得称为B08修复后的效果。没有新GPU任务、预算或等待器。

## 有界验证

执行时间：2026-09-21 14:28 HKT；worker在baseline B08 worktree用CPU提取实际生产step及reset的arm段执行一次。测试parent/config为fixture，未实例化完整Isaac环境。

| 项目 | 实际结果 |
|---|---|
| 普通Stage0，两环境、连续3步、六维输入0.2、delta scale 0.3 | 每步增加约0.06，三步累计约0.18，不再被清零 |
| canonical Stage0，LEFT/RIGHT | LEFT累计约0.18；RIGHT按原符号镜像保留累计值 |
| 选择性真实reset的arm代码 | 被选环境恢复普通零值或RIGHT原点`[0,0,0,-2,0,-12.56]`，另一个环境累计值保留 |
| 原identity proof的arm mapping/clamp/reset段 | PASS；未声称完整历史proof执行 |
| 分支整合检查 | 四份`DoorPregrasp.step` AST相同；公共DeltaActionBase/helper/proof文件字节相同，四个改动文件在各开发目录均可解析 |
| 活跃运行目录保持 | 两个运行目录的四个相关文件分别与原C002/HA-C001标签完全相同 |

CPU证明为限定fixture证据，不是完整reset lifecycle、Isaac runtime或训练结论。已有CPU证明通过后，没有逐分支重复运行或扩大测试。详细整合记录：[integration_readout.json](/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/v29_b08_shared/integration_readout.json)。
