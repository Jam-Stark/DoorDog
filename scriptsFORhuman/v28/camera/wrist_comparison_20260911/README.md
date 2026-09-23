# 腕机两方案：局部四视图

2026-09-11 HKT。Owner要求比较180 mm／45°与140 mm／38.76°；此处仅绘制位置与角度，不选择训练方案。

- [180 mm／45° SVG](wrist_H180_F45p0_wrist_detail_four_views.svg) · [PNG预览](wrist_H180_F45p0_wrist_detail_four_views.png)
- [140 mm／38.76° SVG](wrist_H140_F38p76_wrist_detail_four_views.svg) · [PNG预览](wrist_H140_F38p76_wrist_detail_four_views.png)
- [精确绘图变换与参考姿态](drawing_geometry.json)
- [生成脚本](../../draw_wrist_comparison.py)

视角沿用原U3绘图代码 `Vpiper-Plate-Dual-D435i/code/geometry.py` 的 `VIEWS` 和 `draw_svg.py` 的排列：左上前视、右上右视、左下后视、右下俯视。该代码位于Student worktree的 `camera_setup/` 下，仅作为只读依赖。

两图统一使用参考臂姿态 `[0,0,0,0,0,1.57] rad`、两指关节±20 mm、同一比例和裁切范围。机器人局部来自当前 `a2_piper_vpiper_final_20260906` URDF中arm_body5/6、夹爪基座及两指的原始visual三角网格；不是凸包代替机器人形状。为便于局部比较，绘图坐标原点平移至F，轴仍平行于B=trunk。

180 mm方案直接使用 [当前rig](../U3_F45_B15.json)。140 mm方案将F→M位置缩为140/180，方向按原U3算法 `R_F_M = R_B_Fᵀ Ry(38.76°)` 构造。高度是参考姿态下F→M沿B+Z的抬高量，角度是镜头前向相对B水平的下俯角；不把140 mm当作支架杆长。

180 mm支架沿用当前90×25mm包络。140 mm支架保留同一个起端中心，用同截面连接新外壳底面，是新生成的示意包络，尚未做几何间隙或物理验收，不继承180 mm的1mm间隙结论。两图的半透明零件与虚线视锥用于读图，没有做隐藏线消除或光线遮挡求交，不表示有效深度或透视遮挡关系。

生成环境：项目isaaclab Python、原U3几何模块、Shapely；本次额外绘图库仅安装到 `/tmp/v28_wrist_svg_deps`，未更改项目依赖或环境配置。命令：

```bash
PYTHONPATH=/tmp/v28_wrist_svg_deps /home/baoquanc/anaconda3/envs/isaaclab/bin/python scriptsFORhuman/v28/draw_wrist_comparison.py
```

PNG为SVG的预览副本。SVG保留矢量轮廓、文本、尺寸线与视锥；不是打印件孔位加工图。未修改训练配置、rig、URDF或USD。
