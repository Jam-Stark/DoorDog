# Semantic patch（P2封存后应用）

仅修改 delta_action_base.py、door_open_a2_base.py、door_open_a2_pull.py，保留当前全部其他源码（包括未提交D2）。使用统一diff，不触碰 evaluator、配置或资产。已对三份内存副本做一次 AST parse；未运行GPU或永久测试。

Main配置接线：delta_action_clamp_to_dof_limits=true；a2_v28_camera_telemetry_enabled=true；a2_eval_diagnostic_trace_enabled由既有evaluator开启first-episode trace；reward penalty_a2_wrist_motion_l2=-0.4、penalty_a2_wrist_tower_contact=-1、penalty_a2_stage4_arm_default_pose_l1=-0.5。六行Wv为 [.35,.35,.35]/[.5,.5,.5]/[.75,.75,.75]/[.5,.5,0]/[.5,.5,.25]/[1.25,1.25,1.25]；Wr除Stage3 [.5,.5,.25]外均[.5,.5,.5]。新robot/asset由Main另接。

camera helper位于pull类，使用持久release_event且无双指接触的Stage4 C/D回位门；crossing yaw在现有E6首次newly_reached时捕获。v28_crossing_event明确为E6_PATH_REVERSAL_ENTRY，不能解读成主线首次root-X crossing。无E6输出null，reset清空。本patch不增加/改变E6或release事件。

camera metrics归约脚本、rig、reward/config、runner/evaluator全链由Main集成；本patch只产出既有stage2_5_step_trace.json所需的额外字段并扩大到all-stage。D17保留既有override执行顺序，v28普通actor应保持bank/oracle/absolute/taskspace关闭。
