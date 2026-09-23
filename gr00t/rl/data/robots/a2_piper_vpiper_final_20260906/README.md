# A2 + PiPER + Vpiper：头部窄宽金属板最终几何交付版

**版本：`A2-PIPER-VPIPER-5MM-HEAD100-FINAL-GEOMETRY-20260906`**  
**主入口：`a2_piper.urdf`。本包只有一套默认装配坐标，不再要求在 CAD 孔系版与 Z-only 版之间选择。**

## 2026-09-06 材料质量更新

默认 URDF、ROS URDF、浮动/固定 MJCF 已加入安装件质量、质心和惯量；新增 `a2_piper.usd` 与 `configuration/` 相对引用层。三种格式使用同一材料估算。

- PETG 实体密度 1250 kg/m³，采用 Owner 接受的 **50% 等效实心体积分数**，模型等效密度 **625 kg/m³**。不等同于含实心外壁/顶底层的切片填充率模型。
- 铝合金牌号未知，按 6061 名义密度 **2700 kg/m³**；金属板仍为无孔槽矩形包络。螺栓质量未包含。
- 主件 **0.310684432 kg**，支撑件 **0.105623833 kg**，金属板 **0.3375 kg**，新增合计 **0.753808265 kg**；保留原 27 link 惯量后整机 **45.494808265 kg**。
- `m=Vρ_eff`，COM 使用 CAD 体积中心，COM 处 link 轴系惯量为 CAD 单位质量惯量乘质量。全部非对角项保留。

密度来源：[PolyLite PETG TDS](https://polymaker.com/wp-content/uploads/lana-downloads/PolyLite_PETG_TDS_EN_V5.4.pdf)、[NASA 6061 手册](https://ntrs.nasa.gov/api/citations/19720022808/downloads/19720022808.pdf)。输入在 `config/mount_materials.json`，完整 COM 和 3×3 惯量在 `validation/mass_configuration.json`。重建命令：`python tools/build_models.py`。

USD 已由本机 Isaac Sim 5.1 / IsaacLab 转换器生成。保持浮动根、固定关节不合并、joint stiffness/damping 为 0。`validation/usd_import_readback.json` 记录了 30 rigid bodies、20 active joints，以及三个部件质量/COM/完整惯量张量和相对引用读回通过。未运行仿真步进或策略评估。CPU 导入进程 exit 0；由于不暴露 CUDA 设备，日志含渲染器无 GPU 错误，不作为渲染验证。转换命令（在仓库根目录执行）：

```bash
CUDA_VISIBLE_DEVICES='' LIVESTREAM=0 ENABLE_CAMERAS=0 \
/home/baoquanc/anaconda3/envs/isaaclab/bin/python \
/home/baoquanc/workspace/IsaacLab/scripts/tools/convert_urdf.py \
gr00t/rl/data/robots/a2_piper_vpiper_final_20260906/a2_piper.urdf \
gr00t/rl/data/robots/a2_piper_vpiper_final_20260906/a2_piper.usd \
--headless --device cpu --joint-stiffness 0.0 --joint-damping 0.0
```

下方几何交付记录及原 validation 文件记录最初的无新增惯量版本；本次质量变更以本节和 `mass_configuration.json` 为准。原交付校验清单不覆盖本次更新，未重新生成。

## 本轮最终修改

金属板由上轮 `250 × 173.104290 × 5 mm` 改为 **`250 × 100 × 5 mm`**，沿 trunk 的 Y 方向居中收窄；长度与 5 mm 厚度保持。Vpiper 主件与支撑件没有裁切、缩放或增高。

这里将 Owner 的“Vpiper 头部较短宽边”解释为**头部窄段的整体外宽**。STEP 中该窄段两侧位于局部 `Y=−50/+50 mm`，故整体宽 100 mm；最前端直线边本身长 80 mm，其两端接 R10 圆角。**100 mm 是 CAD 的整体窄头宽，不是照片测量值，也不是 Owner 新报的尺量数值。** [宽度基准图](figures/plate_width_datums.png) 明确区分 100、80 和旧的 173.104 mm。金属板仍为无孔槽的矩形名义包络，实际槽、孔、倒角未测，不作为加工图。

PiPER 安装原点相对 **trunk link 原点**：

```xml
<joint name="arm_j0" type="fixed">
  <parent link="trunk" />
  <child link="arm_body0" />
  <origin xyz="0.145 0 0.147431554755" rpy="0 0 0" />
</joint>
```

单位为米、弧度。最终选择 **`[145, 0, 147.431555] mm`，RPY=`[0,0,0]`**。保留原 X/Y；仅将原 Z=154 mm 修正为 CAD 尺寸链给出的 147.431555 mm。没有强行采用上轮的 X=148.212711 mm 孔系对齐假设，因为实物长槽的锁紧位置仍未量取。

## 本次对“碰撞箱上表面”和“导轨抬升”的复核

原 URDF 的 trunk **第一个主碰撞箱**是：

```xml
<origin xyz="0 0 0.007" rpy="0 0 0" />
<box size="0.24 0.28 0.17" />
```

因此其上表面不是 99 mm，而是 **`7 + 170/2 = 92 mm`**。上轮“若连接件为50 mm，则原基准可能是99 mm”的反推，不应再作为对你实际测量方法的解释。

这次重新从上传的原始 STEP 提取 trunk 与安装件，独立配准到原 trunk.STL，并同时查询精确 BRep 表面和三角网格。结果如下（全部相对 trunk 原点）：

| 位置或尺寸 | 数值，mm | 含义 |
|---|---:|---|
| 主碰撞箱上表面 | 92.000000 | 简化碰撞代理，非真实统一背部平面 |
| 导轨下部参考面 | 89.631553 | 查询点位于导轨承托边条下方；邻近背壳约同高 |
| 导轨承托边条上表面 | **92.431555** | Vpiper 下支脚的实际 CAD 承托基准 |
| 承托边条相对下部参考面的抬升 | 2.800002 | 已包含在 92.431555 中，不能再加一次 |
| 承托面比主碰撞箱上表面高 | **0.431555** | 不是 2.8 mm，也不是 6.568 mm |
| Vpiper 下支脚到上承托面 | 50.000000 | 安装件精确平面间距 |
| 额外金属板 | 5.000000 | Owner 确认厚度 |
| PiPER 原点最终 Z | **147.431555** | 92.431555 + 50 + 5 |

也可完全沿用你原来的“以碰撞体上表面为起点”的写法，但必须加入该起点到实际承托面的差：

```text
92.000000 + 0.431555 + 50.000000 + 5.000000 = 147.431555 mm
```

导轨在原 **visual mesh / STEP** 中有显式细节；原 **collision** 只有简化 box，并没有分别刻画轨道边条与凹槽。因此不能说碰撞箱精确建模了导轨，但也不能认为“从碰撞箱顶部还需要再加完整2.8 mm导轨高”。那会重复计算已经被碰撞代理包络覆盖的大部分高度。

原 154 mm 相当于在 `92 mm + 5 mm` 之外还使用了 **57 mm**，与本 CAD 的 `0.431555 + 50 mm` 不符。现有材料不能确认你当时的这部分数值来自哪一次量取；不能把整段 6.568 mm 差异仅归因于碰撞箱简化。

## 文件入口

| 文件 | 用途 |
|---|---|
| `a2_piper.urdf` | 唯一默认装配模型，相对 mesh 路径 |
| `a2_piper_ros.urdf` | 同一几何与关节，使用 `package://a2_piper_vpiper_description/` 路径 |
| `a2_piper.xml` | 同一装配的浮动根 MJCF，供几何/FK核对；不是生产控制 plant |
| `a2_piper_fixed.xml` | 同一装配的固定根 MJCF，便于观察 |
| `scene.xml` | 显示用场景；通过 `preview_mujoco.py` 只做 mj_forward，不做 mj_step |
| `meshes/` | 原机器人27个mesh + Vpiper主/支撑visual与51个凸碰撞分块 + 新金属板 |
| `cad/` | 安装件局部STEP（mm）、金属板STEP（mm）、检查姿态GLB（m） |
| `config/mount_parameters.json` | 唯一坐标/尺寸配置及事实、假设边界 |
| `source/` | 原始URDF、重新提取的STEP子集、照片、来源与哈希；不是运行入口 |
| `docs/FINAL_GEOMETRY_REVIEW.md` | 详细尺寸、核对方法与已知限制 |
| `docs/LOCAL_VERIFY.md` | 本地复核与导入步骤 |
| `validation/` | 实际运行得到的静态、CAD、资源验证结果及源CAD警告 |

[安装局部效果](figures/mount_closeup.png) · [整机检查姿态](figures/assembly_inspection.png)

## 验证状态

**已完成：** 原始输入URDF及27个机器人mesh与Worker包逐字节一致；原27个link的惯量、原20个活动关节及原collision保留；新增link树、全部资源路径、板visual/collision尺寸、51个凸碰撞分块的封闭性与凸性检查；257组URDF/MJCF正运动学比较；另256组固定根MJCF比较；ROS路径版等价检查。16个实际支脚位置的STEP轨道上表面与Vpiper局部下表面重合，并与trunk.STL独立核对。

**未完成：** MuJoCo实际编译、Isaac导入、动态接触仿真、全姿态无碰撞证明、实机外参及结构刚度测量。这里没有安装MuJoCo；依赖获取失败，未把自写FK核对冒充引擎验收。当地可执行真正的引擎检查：

```bash
python tools/verify_models.py
python tools/verify_resources.py
python tools/verify_models.py --mujoco
```

最后一条需要当地已安装MuJoCo；缺失时会失败退出，不会给出假PASS。

**源CAD警告：** 提取的原STEP trunk实体存在一个不可定向的侧壁面，未通过整体BRep有效性检查；未对其做隐式修补。此次16个承托面查询对应的面均通过面级检查，并与原trunk.STL吻合。这不等于整个A2 STEP实体已经修复；详见 `validation/source_trunk_brep_warning.json`。

**质量/动力学边界：** 当前安装件已采用本页顶部所列材料与 50% PETG 等效体积分数估算。原 27 link 惯量保留；新增质量不代表实测重量，未验证结构刚度和实机动力学。详细惯量、质心与密度见 `validation/mass_configuration.json`。

**本包是本轮最终几何修订版，不是已经完成实机标定与动力学验收的认证模型。** 数字的小数位用于复算，不代表物理测量精度。
