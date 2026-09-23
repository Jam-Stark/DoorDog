# 实际结果索引

全部数值来自本次CPU离线模型，不是Isaac、策略rollout或硬件测量。

| 文件 | 粒度／单位／使用边界 |
|---|---|
| directional_force.csv | 104条工作点×姿态×世界方向；力N，力矩Nm；限矩、重力、四足支撑层 |
| pd_target_limited_force.csv | 相同104键；进一步加入arm静态PD目标角限位，必须与上一表一起读 |
| ik_status.csv / states.json | 全部42姿态组合，26解出／16未解；未解不是全局不可达证明 |
| parameters.json | 坐标、工作点、姿态与模型假设 |
| solver_details.json / pd_envelope_details.json | 足地力、关节力矩、有效约束与求解残差 |
| sensitivity.csv | 单独摩擦、限矩、理想夹持情景，不是置信区间或已核验实机能力 |
| separate_base_translation.csv | 中性姿态base前后5cm；不混入固定base的姿态比较 |
| inertial_sensitivity.csv | 零速度单时刻TCP加速度±0.5m/s²，未时间积分，不是甩门验证 |
| validation.csv / independent_balance_checks.json | 数值差分与独立力／力矩平衡核对 |
| mid105_neutral_model.npz | 浮动基座M、g、J等可复核数组 |
| execution_summary.json / *.log | 实际执行状态、环境与输出；PD为后续补算，日志独立保存 |
| 01–04 PNG | 分别展示arm与支撑界、同20N扭矩、独立base平移、PD排序反转 |

所有表的力均为机器人在TCP施于门的力，门对机器人取相反号；具体方向向量见数据。力矩／几何／支撑边界均不包含已验证的B05真实抓握和冻结低层可实现性。图中未解姿态不填零。重现命令见根目录README。
