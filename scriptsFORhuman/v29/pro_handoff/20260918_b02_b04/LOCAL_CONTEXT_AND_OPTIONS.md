# 本地事实、候选与证据边界

2026-09-18 HKT。这是本地INSPECTED/静态判断，非Pro结论。旧软件偏好已由Owner重新开放为A/B选择。

## 当前实现与已决定的目标域

| 项目 | 当前source/config | 已决定或待讨论的变化 |
|---|---|---|
| 门重/闭门器/摩擦 | 80–120kg；hinge drive cap2.5–12N·m，raw USD k=1–10/d=50；native摩擦off | B01三档30–80/80–120/120–160各1/3、closer有无各半、摩擦加入；联合SI配方仅plan，未实施 |
| handle/latch | handle0–45°；target−15°、raw k50/d.5、cap1–3N·m；cone滑块0–30mm，mimic−.03/45 m/deg | B02机制本轮二选一；20–60°阈值/+5°止挡仅本地提案 |
| hinge机械上限 | 原生RevoluteJoint限位0–150° | B04讨论90–150°及实现方式，尚未随机化 |
| 时间/起点/速度 | 30s；stage[525,150,150,150,150,300]，dt=.02；法向1.2–4m、横移±.5m、联合yaw；Stage0门距1.8–2.2m平滑.3→.5m/s | 已实施，仅静态/CPU证据；Stage4/5速度仍.3 |
| 相机 | base15°、MERGED wrist H180/F45；arm reset[0,.10,−.10,0,−.52,1.57] | B03已由Owner后置，baseline出来后再微调；B06当前setup已接受 |

## B02并排事实（供独立决策，不打总分）

| 维度 | A软件虚拟锁闩 | B当前碰撞锁舌+mimic |
|---|---|---|
| 规则 | 可直接定义handle阈值与锁态 | 解锁由完整碰撞几何退出间接决定 |
| 当前基础 | 需要新增状态/约束切换与恢复逻辑 | 已有generator与三DOF路径 |
| 反馈 | 原生约束可产生反力；与实际扣板接触不同 | 有代理接触，但高位cone不是精细真实锁体 |
| 角度随机化 | 容易直接采样；止挡必须与阈值协调 | 传动比/行程/搭接须联合，实际脱扣角尚未求出 |
| reset | 删除第三DOF、同步bank及状态 | 保留拓扑；随机后的几何/参数仍须一致 |
| 开门/回关 | 必须明确handle回位与复锁时序 | 由现有几何决定，但完整真实闭锁行为未验证 |
| 运行证据 | 尚未实现/验证限位切换 | 旧one-batch包含该拓扑，仅证明接线，不证明策略质量/准确脱扣量 |

实体代理在door_height−.1m、x=−.083m，cone半径25mm、高50mm；handle高度变化不会同步移动它。`build_latch`还控制articulation self-collision属性，不能删除锁舌时无意改变门板/门框碰撞语义。

本地曾建议软件阈值20–60°、机械止挡+5°；保守替代是解锁20–40°且止挡45°。这是供Pro比较的候选，不是已经批准的角度分布，也不是“当前软件已这样做”。采用软件方案后无需再保留实体stroke/mimic接口；保留物理方案则不能只删几何检查而按角度假报解锁。

## B04事实

| 量 | 当前值/含义 |
|---|---|
| 原生hinge upper limit | 150°，generator直接写入，并非每步重写门角 |
| Stage3→4 | hinge>0.25rad且满足握持条件 |
| release gate | hinge≥1.2rad≈68.75°；逻辑gate不要求实际松手 |
| Stage4→5 | hinge>1.0472rad≈60°、handle<.2rad、root_x>0 |
| hinge位置reward饱和 | 1.5708rad≈90°；仅奖励数值裁剪，不限制真实关节角 |

gate后hinge位置收入关闭，正门速/有效握持的hold-and-drive仍可能有收入。随机终点不自动消除“开到各自挡止才松手”。不要混用逻辑release gate、失去双指同时接触、全部断触和过门事件。

## 观察、学习与证据

当前Teacher actor/critic为2层256维LSTM；actor有door_dof_pos（hinge/handle角）、机器人状态/动作和双指接触反馈，没有显式door角速度或latch进度。privileged_door_info包含门重及几何，不含closer/friction/k/d/cap真值。`history_long/short`虽在配置定义，未列为当前actor输入；不要把底层步态history说成上层显式历史拼接。软件内部bool不等于可以把答案喂给policy。

上一份Pro已指出操作角≠精确解锁角、机械挡止≠解闩、停滞≠成功；这些原则可保留。旧报告的实体机构细节不是本次不可更改要求。当前没有A/B训练比较、没有新最大角域运行或sim-to-real收益证据；65°handle可达性、软件限位切换反力、当前几何的精确脱扣角仍是local-only未知。

本次提供当前resolved config（只解析）和9月17日64-env/one-batch的config/readout/receipt作为边界证据。旧运行不覆盖新起点/速度，也不覆盖计划中的B01/B02/B04。无checkpoint、无新的GPU运行或视频；不要以缺失这些材料为理由重开已关闭的v28验收或B03相机前置条件。
