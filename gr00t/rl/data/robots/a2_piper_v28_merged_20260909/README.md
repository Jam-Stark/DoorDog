# v28 MERGED训练asset（D-34 / D-35）

Owner于2026-09-11选择MERGED并恢复G0。修改：-codex worker；依据：-owner。当前robot配置已绑定本目录；G0 launch门于2026-09-12按D37数值分支、5-batch PPO与全字段接线验收通过；G1尚未启动。

入口：`a2_piper.urdf`与`a2_piper.usd`，依赖的meshes与USD configuration层均在本目录。

- main、support、metal plate的原visual/collision按固定变换并入trunk；28个刚体、20个活动关节，配置body_names 28与penalize_contacts_on 20保持合同。
- 腕机为独立wrist_camera_tower：相机外壳中心在参考姿态下离法兰140mm，俯角38.76°；支架截面90×25mm、长76.227187mm。
- D-20安装端按新轴向对原gripper collision凸包重新求解；实际静态间隙1.000000mm，轴向偏移25.355564mm。不是沿用旧F45偏移。
- 支架估算质量0.049843403kg = 0.075kg × 新长度 / 0.11470001524266443m；外壳估算0.075kg；合计0.124843403kg。质心和完整惯量按新两盒位置/旋转重算，均为仿真估算。
- 全机质量约45.61965166732444kg。MERGED与同一新几何的独立体输入比较：质量差0、COM误差4.60e-19m、惯量张量误差5.38e-17kg·m²。
- trunk相机并集：双±0.155布局8支架盒+2外壳盒，另含中置[0.025,0,0.19]的一个外壳包络盒，均15°。中央盒是未选最终布局的包络proxy，不是第三台base光学相机，不额外增加第三台相机质量。
- 默认arm姿态由robot YAML指定为[0,0.10,-0.10,0,-0.415,1.57]；相机布局与内参最终验收属于后续G2。

## 证据

- `config/camera_rig.json`：U3_F39_H140。
- `validation/source_inputs/a2_piper_independent_d35.urdf`：可解析相对mesh的同几何31体输入。
- `a2_piper.proposal.json`：复合惯量等价计算；以aggregate_difference为准（扩展精度稳定聚合）。
- `validation/d35_tower_estimate.json`：D20几何求解、估算质量与两盒COM/I。
- `validation/usd_import_readback.json`、`validation/usd_mass_inertia_comparison.json`：新版USD原生28体读回与参数对照；USD浮点误差单独报告。
- G0实时状态：仓库`scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/g0_decision.json`。

当前R1/R2/R3/R5已RUNTIME_PASS：监测trunk、arm_body0..6、tower的R2接触力均0N；R3 root z为0.465865–0.477995m，臂速度max0.050957rad/s；R5为0.424513m。G0-A4静态通过。后续G0 launch门已通过；这不构成Teacher质量或硬件验收。

构建入口：`scriptsFORhuman/v28/v28_camera_geometry.py build`、`v28_build_asset.py`、`v28_merge_mount_bodies.py`；USD按plan §4.2的本机convert_urdf.py命令生成。CUT保持旧对照用途，未绑定。

G0-L当前停止原因：D36默认离线PASS（原stand相对门FAIL保留），hold PASS；类Stage2的vx050/pitch、vy_pos/roll、vy_pos/yaw p50比分别1.208313/1.230491/1.164372，均非floor比较，未过1.15倍门。三个姿态新旧均0摔倒，p95与前向斜率全部通过。按D36停止，PPO/G1未运行；详见v28目录20260912 G0恢复readout。

D37后续：三姿态离线及冻结harness的seed282确认数值门通过；seed282无实际随机输入变化，X24仍OPEN。64env×5batch PPO与左右各64环境评估均exit0，26个遥测字段接线完成；晚阶段7项因仅观察到Stage0而为null。首commit验收汇总见`scriptsFORhuman/v28/a2_piper_base_v28_g0_acceptance_20260912.json`；上方D36 STOP段为历史记录。
