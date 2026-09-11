# v28 G0恢复执行：STOP_G0_L_FAILED

日期：2026-09-12 HKT。修改：-codex worker；停止依据：-owner（G0-L失败STOP，阈值/路由变更按plan §9.8）。

MERGED、140mm/38.76°腕机、j5=-0.415、base并集包络和K配方已落地。R1/R2/R3/R5及A4通过；G0-L默认姿态匹配比较未过，因此按指令停止。没有继续其它姿态、PPO smoke、G1或Wave A/B，没有commit/push。

## G0-L失败读数（RUNTIME）

新旧asset均使用[0,0.10,-0.10,0,-0.415,1.57]，64env、相同13个指令块与seed281。两组全程均0摔倒。以每个块的五个物理指令分量p50误差逐项执行candidate≤1.15×baseline，未加绝对下限。

| 失败项（均为stand零指令块） | 旧asset p50 | MERGED p50 | 1.15倍上限 | 比值 |
|---|---:|---:|---:|---:|
| vx残余速度，mm/s | 0.573011 | 0.728073 | 0.658963 | 1.2706 |
| vy残余速度，mm/s | 0.747493 | 0.896274 | 0.859617 | 1.1990 |
| yaw残余角速度，mrad/s | 0.904333 | 1.119121 | 1.039983 | 1.2375 |

其余62/65项p50比较通过。vx=0.5块的实现/指令斜率：旧0.940937、新0.931902，下限0.890937，通过。失败集中在零指令站立的极小残余速度比值，不据此声称行走能力崩溃；但冻结的1.15倍门确实未过。未自行更改阈值、滤除stand项或重跑挑结果。是否调整零指令判据须Owner决定。

原始结果：`runtime_logs/v28_camera_aware_rebaseline_20260909/resume_20260911/walk/{baseline_default,v28_default}/metrics.json`；逐项比较：`walk/default_comparison.json`。两进程exit0，FAIL是验收结果，不是执行失败。

## 已完成

- D34/D35：MERGED 28刚体/20活动关节；同新几何独立输入的复合惯量差mass=0、COM=4.60e-19m、I=5.38e-17kg·m²；USD已转换并读回。
- 腕机实际1mm安装间隙已重求：支架长76.227187mm、估算质量0.049843403kg＋外壳0.075kg，总0.124843403kg；质心/惯量重算。trunk为8支架+双外壳+中央外壳并集，中央不另计第三台相机质量。
- K块17项、G1完整配方、备用A_S284(target_stage=5)、K_REACH_WITHOUT_COMPLETE、reachability/qualification分层reducer已实现。CPU compose通过53项登记差异；7项v28语义/姿态检查通过，resolved-asset/M23子集检查通过。
- R1/R2/R3/R5 RUNTIME_PASS：trunk、arm_body0..6、tower在R2窗口全部0N；R3 root z为0.465865–0.477995m、臂|dq|max=0.050957rad/s；R5为0.424513m。
- A4 COMPUTED_PASS，无非过滤刚体对穿透。
- C3旧v27轨迹扫掠已完成，3个lane/stage未过20mm条件，panel min约-20mm、frame min约-2.64mm。按plan §3.2保留旧轨迹FAIL；不是v28 policy结果，更不代表较小最终硬件方案不可行。
- 新朝向raw字段及首次越门yaw锁存已接入；R2自然零指令trace和离线归约已走通。SDK内参与RGB/depth相对外参已接入。未观测的crossing/release/Stage5统计保留null，不能冒充这些事件已在PPO中验证。

## 未完成与状态

默认姿态G0-L失败后，未运行新asset的hold/Stage2比较、5-batch PPO smoke与完整PPO/eval遥测验证、G1及后续训练。G2-C1/C1′/C2/C4仍按D30后移，非本次阻塞原因。A_S284是否参与选种在plan尚未明确，当前仅预注册备用配对报告，不擅自扩大A_S281–283选种范围。

当前权威状态为`runtime_logs/v28_camera_aware_rebaseline_20260909/g0_decision.json`。保留R2运行时字节快照`resume_20260911/source_lock_g0/`和停止时完整源码快照`source_lock_stop/`；后者包含后处理SDK归约、步行判据脚本及执行记录，不声称这些后处理改动重新运行了R2。没有硬件操作或Teacher/G7 binding更新。
