# pro_delivery__full_review.zip

完整v29 C002保留B05的N02预研回包。先读FULL_REVIEW.md；物理数值见DYNAMICS_AND_FORCE_ANALYSIS.md；实施仅按PILOT_AND_IMPLEMENTATION_PLAN.md讨论，未授权启动本地训练。

## 文件

- FULL_REVIEW.md：六问、实际出力问题与收敛决策。
- TARGET_AND_OBSERVABILITY.md：最小目标、信号/人口/因果标签。
- CLOSED_LOOP_CONTROL_PLAN.md：几何、动作、持握释放、reward接口与流程。
- TEACHER_STUDENT_PLAN.md：结构、实际Student轨迹、记忆与训练。
- PILOT_AND_IMPLEMENTATION_PLAN.md：顺序pilot与源码落点。
- REFERENCE_COMPARISON_AND_SOURCES.md、SOURCE_EVIDENCE.md：文献和可检索源码证据。
- DYNAMICS_AND_FORCE_ANALYSIS.md、modeling/、results/：实际运行方法、输入、结果及图。
- LOCAL_WORKER_PARSE_PROMPT.md：Owner指定的逐字接手文本。

## 重现CPU结果

从解压后的根目录执行。无需原项目、权重、mesh、GPU或Isaac。

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -r modeling/requirements.txt
export OPENBLAS_NUM_THREADS=1
python modeling/run_analysis.py --out results > results/run.log
python modeling/extra_checks.py > results/extra_checks.log
python modeling/pd_envelope.py > results/pd_envelope.log
MPLBACKEND=Agg python modeling/plot_results.py
MPLBACKEND=Agg python modeling/plot_pd_results.py
# 可选：复现初始IK探索，不属于正式42姿态采样
python modeling/probe_workpoints.py > results/probe_workpoints.log
```

测试环境Python3.13.5；依赖版本见requirements。main脚本有`--out`，补充脚本与绘图按交付根目录的results读取；使用自定义结果目录时需同步调整补充脚本路径。环境/求解器版本可能造成IK分支细微差异；保留位置/旋转/约束残差，不要求bitwise结果相同。

## 结果解释

`directional_force.csv`是重力＋限矩及支撑约束结果；`pd_target_limited_force.csv`增加名义arm PD目标限制，不能漏看。`sensitivity.csv`中摩擦/夹持/缩放是情景假设，不是置信区间。`inertial_sensitivity.csv`只是在零速度下的瞬时加速度计算，不是动态开门视频或Isaac结果。`ik_status.csv`、`states.json`保留全部未解点。`separate_base_translation.csv`必须与固定base的roll/pitch对照分开。

`execution_summary.json`、`independent_balance_checks.json`和日志记录实际执行。首次绘图写入遇到目录权限错误，修复权限后实际重新运行成功；该问题不影响已完成的数值模型。未运行项在各报告明确说明，没有伪造策略或硬件结果。

所有源版本字段沿用Owner输入，不生成哈希清单；未上传任何Pro结果到Drive。原GPU0/GPU1及本地实施授权不因本包改变。
