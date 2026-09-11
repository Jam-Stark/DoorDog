# v28 G0 决策日志

更新：2026-09-10 HKT；修改：-codex worker。Owner指示以每项authority字段标记；已批准决定与待planner判断的讨论分开记录。

| ID | 决定 | 修改者 / 依据 | 状态 | 重审触发 |
|---|---|---|---|---|
| V28-D018 | 先仿真、后硬件设计；真实腕机支架CAD尚未设计，G0-C1′记NOT_RUN，不冒充CAD通过。 | -codex worker / -owner（本次任务明确回复） | ACCEPTED | 真实CAD到位 |
| V28-D019 | 腕机单长方体支架截面90×25mm，与D435i等宽等厚；外壳另一个盒；替代8×8mm细杆。 | -codex worker / -owner（本次任务明确建议） | ACCEPTED | 几何或runtime验收失败 |
| V28-D020 | 保持相机中心和θ45；宽支架安装端按原gripper碰撞表面定位，沿轴移27.158370732mm，最终支架长114.700015242mm，静态间隙1mm。支架及外壳各估0.075kg，总0.15kg。 | -codex worker / v28 §4.2 / Owner宽支架设计 | ACCEPTED | CAD/实测质量到位或runtime接触 |
| V28-D021 | 按预授权R2分支把金属板碰撞高度5→4mm、顶部下降1mm；visual/质量及安装位姿不变。arm_body0最大接触由11.56N降为0，trunk异常接触未解决。 | -codex worker / v28 §4.2 / §9.6 | ACCEPTED | R2仍未通过，继续定位源asset碰撞 |
| V28-D022 | 不生成hash/SHA；CPU compose明确键差异，mesh使用字节比较，运行记录保留路径/命令/原始读数。 | -codex worker / -owner（当前任务AGENTS明确禁令） | ACCEPTED | Owner显式变更要求 |
| V28-D023 | R5旧预测0.40m与D-03a姿态不一致；当前URDF FK为0.432637003m，runtime为0.432636678–0.432637036m。保留原区间匹配=false和实际读数，不把数值改写成0.40m。 | -codex worker / 当前source与runtime事实优先于计划预测 | ACCEPTED | G0决定解释R5报告项及R3高度门 |

详细证据路径见 `runtime_logs/v28_camera_aware_rebaseline_20260909/decision_log.jsonl`。

当前 G0 尚未通过；没有第一个本地 commit，未启动 G1、正式训练或更新 Teacher/G7。

## V28-D024：G0 高度判据修订

Owner批准R3稳定1s后检查50控制步，root z[.45,.51]m且臂|dq|<.5rad/s；R5期望改为当前FK .432637±.01m。 修改：-codex worker；依据：-owner。

## V28-D025：Owner暂停

Owner拒绝采用compound-trunk候选，保留原独立刚体并暂停G0；不做首个commit，不启动G1。 修改：-codex worker；依据：-owner。

## V28-D026：制作两个候选

Owner要求同时制作合并路线与裁切路线，分别置robots目录等待判断；不选择活动asset，不恢复G0，不commit。 修改：-codex worker；依据：-owner。

## V28-D027：整块水平裁切

Owner指出早先局部裁切不符合意图：若仅蓝色底部脚板冲突则只切脚板；若橙色support也冲突则统一水平截去整个下部。当前几何证据已定位support参与冲突，因此最终对main、support全XY范围在trunk z=0.130m作单一水平裁切，visual与collision同步删除下部，保留原joint/inertial。此规则取代早先局部碰撞分块裁切与局部长方体凹口。两版仍为待Owner选择的独立候选，G0保持暂停。修改：-codex worker；依据：-owner。

证据与入口：`gr00t/rl/data/robots/v28_asset_comparison_20260909.md`、cut目录的`validation/cut_geometry.json`和`validation/horizontal_cut_comparison.png`。仅CPU几何/参数比对与USD静态读回；本候选未运行物理/G0。

## V28-D028：降低腕机高度与俯角（PROPOSED，2026-09-10）

Owner提出降低腕机安装高度，并相应减小俯角。核对来源后确认：180mm是参考姿态下相机外壳中心相对法兰的抬高量，沿用旧U3方案；v28此前比较角度，没有优化高度。当前实体支架长约114.7mm，两者不是同一个尺寸。

Worker使用当前`camera/U3_F45_B15.json`名义内外参作几何估算：只降低中心高度、不改变前后/左右位置，保持TCP原有RGB投影行位置，不计遮挡。180mm/45°对应TCP光轴距离173.62mm；140mm/38.76°对应140.74mm；120mm/34.49°对应125.25mm；100mm/29.13°对应110.75mm。当前424×240深度合同Min-Z为105mm。这不是最优构图、真实有效深度或夹爪无遮挡的证明，现有上指遮挡问题不能由该表判定已解决。

状态：仅讨论与CPU几何计算，未选择新高度/角度、未修改rig或asset。修改：-codex worker；降低高度的提议：-owner；数值与解释：-codex worker。

## V28-D029：Teacher保守包络、光学安装延后（PROPOSED，2026-09-10）

Owner提出：Teacher先按当前较大腕机碰撞包络训练，实际相机高度/俯角到蒸馏阶段再调整。Worker核对当前实现：Teacher关闭相机渲染；新增奖励依赖腕部关节运动、塔架接触及默认姿态回位；光学可见率为report-only。因此该分阶段安排在实现上可行，但尚未作为plan变更批准。

待planner判断：哪些光学冻结与G0-C检查可移至蒸馏开始前；Teacher保留哪些碰撞、质量/惯量、默认姿态与动作合同。当前最高版本尚不能直接宣称覆盖所有较低/不同角度安装件，需用最终外壳与支架的几何包含关系判断。蒸馏应使用最终相机重新渲染并确认关键观测，Teacher动作标签可复用；若动力学或动作约定改变，则不能只当作图像变化。较大包络训练失败也不能自动否定更小的最终硬件方案，需检查plan §8.2的结论范围。

G0继续PAUSED_BY_OWNER；trunk/Vpiper异常接触仍是独立的训练前问题。本次没有恢复训练、选择asset、改变相机参数或更新plan执行合同。修改：-codex worker；分阶段提议：-owner；条件性分析：-codex worker。

## 2026-09-11 23:06 HKT — Owner 决定（planner 落笔；依据：-owner）

| ID | 决定 | 状态 |
|---|---|---|
| V28-D030 / plan D-30 | 合同分两段冻结：C_T（碰撞包络含塔架与 trunk 并集支架盒、质量/惯量、冻结姿态、D-17 夹紧、reward bundle、telemetry、G0-C3）训练前冻结；C_S（成像意义上的光学项、base 相机单/双与上仰角、G2-C1/C1′/C2/C4、Student 裁剪、渲染域一致性）蒸馏前冻结；containment 判据（最终盒 ⊂ E_T，SDF ≤ −3 mm；质量/质心/主惯量 ≤ 训练值）与蒸馏前 eval-time 安装件交换检查（plan §8.2） | ACCEPTED |
| V28-D031 / plan D-31 | K driver：保持 `target_stage=4`；预注册具名失败 `K_REACH_WITHOUT_COMPLETE`（连续两个 milestone 双侧 S4+ ≥ 56 且 complete ≤ 4）；触发时第 4 个 seed `A_S284` 用 `target_stage=5` | ACCEPTED |
| V28-D032 / plan D-32 | Wave A 选种用 reachability 门（complete ≥ 60、终止 ≤ 2、塔架接触 ≤ 2、`post_release_body_force_p95 ≤ 5 N`）；Wave B 资格仍用合取门（含 `clean_complete`，hinge ≥ 1.0472 保留） | ACCEPTED |
| V28-D033 / plan D-33 + D-06 | base 相机单中置 vs 双 ±0.155 **后移到蒸馏前**；Teacher 的 trunk 包络取两布局并集（双 ±0.155 支架/外壳盒 + 中置外壳盒，15°），质量取双相机值 | DEFERRED（C_S） |
| V28-D034 / plan D-34 | asset 采用 **MERGED**（`a2_piper_v28_merged_20260909/`，mount 并入 trunk，精确复合惯量，28 native 刚体）；CUT 保留为参考；D-021 板高修正在 MERGED 下不再必要 | ACCEPTED |
| V28-D035 / plan D-35 | 腕机塔：外壳中心离法兰 **140 mm**、θ **38.76°**；reset j5 改 **−0.415 rad**（行走光轴 −14.9°）；R5 期望改为法兰 z 0.424514 ±0.01 m；E_T 用该设计两盒，不用族包络 | ACCEPTED（取代 D-028 PROPOSED 与 D-020 的 180 mm/θ45） |
| G0 | 恢复：R2/R3/R5 在 MERGED + 新塔架 + j5 −0.415 上复跑；两候选物理验收授权（MERGED 为绑定 asset，CUT 只作对照记录）；MERGED 仍有 >1 N 异常接触则 STOP 交 Owner | AUTHORIZED |

D-028 → 由 D035 取代；D-029 → 由 D030 取代。


## D-34/D-35 执行记录（2026-09-11，修改：-codex worker；依据：-owner）

MERGED已绑定并重生成140mm/38.76°腕机；D20对新轴向实际求解得1mm间隙、支架长76.227187mm。支架沿用D20单位长度质量估算，质量0.075×L/0.11470001524266443=0.049843403kg，外壳0.075kg，总0.124843403kg；COM/I按新几何重算。中置base外壳为并集proxy，不另计第三台相机质量。稳定复合惯量对照mass差0、COM 4.60e-19m、I 5.38e-17kg·m²。

R1/R2/R3/R5已runtime通过，R2监测体全部0N；A4静态通过。其余状态由g0_decision.json记录。§4中旧A1/板高修正分支、§8/§9旧无K/G1失败转scratch条文已按Owner本次明确指令同步；G1失败STOP。相机归约已接入SDK内参/相对外参及新增朝向字段，不增加reward。

## 2026-09-12 G0-L触发STOP（执行规则，非阈值变更）

默认姿态匹配的新旧asset均0/64摔倒，vx050斜率通过；stand块vx/vy/yaw三项p50残余速度比分别1.2706/1.1990/1.2375，超过冻结1.15倍门。按Owner明确指令停止，未跑其余姿态/PPO/G1，未commit。极小绝对误差与完整读数见`a2_piper_base_v28_g0_resume_readout_20260912.md`，是否调整零指令判据交Owner；没有自行放宽。修改：-codex worker；停止依据：-owner。
