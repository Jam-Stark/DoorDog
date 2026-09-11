# v28 安装件建模：两个候选

当前状态（2026-09-11）：Owner已选择MERGED、恢复G0，并将MERGED腕机更新为140mm/38.76°；CUT保留9月9日对照，不绑定。修改：-codex worker；依据：-owner D-34/D-35。下表及旧对比图描述9月9日同一180mm腕机条件下的两候选，不能作为当前MERGED几何/质量合同。当前合同见MERGED目录README与validation/d35_tower_estimate.json。

| 比较项 | 合并版 | 水平裁切版 |
|---|---|---|
| 目录 | `a2_piper_v28_merged_20260909/` | `a2_piper_v28_cut_20260909/` |
| 入口 | `a2_piper.urdf` / `a2_piper.usd` | `a2_piper.urdf` / `a2_piper.usd` |
| native刚体 / 活动关节 | 28 / 20 | 31 / 20 |
| 安装件处理 | main、support、metal plate全部形状按原固定变换并入trunk | main、support全部visual/collision按trunk z=130mm水平截去下部 |
| 全机质量 | 45.64480826480732kg | 45.64480826480732kg |
| 惯量处理 | 原质量、质心、完整张量经坐标旋转和平行轴定理合成 | 保留全部来源inertial，裁切后的质量分布作为仿真近似 |
| arm/camera安装位姿 | 保持 | 保持 |
| 腕机塔架 | 独立刚体 | 独立刚体 |
| 证据 | CPU质量/位姿等价计算、USD静态读回 | CPU水平裁切、1mm截面间隙、原质量/位姿参数比对、USD静态读回 |
| 本候选物理/G0运行 | 未运行 | 未运行 |

合并版以各组件原始质量/质心/惯量合成，未假设trunk和Vpiper为同一密度。零关节坐标下，全机质量差0kg、COM最大误差1.74e-18m、完整惯量张量最大误差2.78e-17kg·m²。

裁切版按Owner最终条件处理：已定位到橙色support也参与冲突，因此统一水平截断整个下部。已定位冲突盒顶面z=129mm，裁切平面z=130mm。main剩余一个连通体，support在平面上方剩余两个连通部分。

- [合并版说明](a2_piper_v28_merged_20260909/README.md)
- [水平裁切版说明](a2_piper_v28_cut_20260909/README.md)
- [实际mesh对比图](a2_piper_v28_cut_20260909/validation/horizontal_cut_comparison.png)

两版都自带mesh与USD组合层。上述旧候选状态由2026-09-11 D-34/D-35取代：MERGED已绑定，G0恢复并处于验收中；CUT与原始asset保持对照用途。
