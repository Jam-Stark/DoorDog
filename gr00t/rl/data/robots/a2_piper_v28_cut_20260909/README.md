# v28 水平裁切候选

状态：`CANDIDATE_WAITING_OWNER_SELECTION`。修改：-codex worker；依据：-owner（2026-09-09：support也有冲突时，按同一水平面截去整个下部）。

入口：`a2_piper.urdf` 与 `a2_piper.usd`。模型使用本目录的 `meshes/` 和 `configuration/`；相机合同保存在 `config/camera_rig.json`。

## 最终裁切规则

在 **trunk坐标 z=0.130 m** 处作单一水平截面，覆盖 `vpiper_main` 与 `vpiper_support` 的全部XY范围，删除截面以下的全部visual与collision。已定位的support/trunk冲突盒顶面为z=0.129m，截面留1mm间隙。该最终版本取代早先局部碰撞块裁切与局部长方体凹口版本。

- main剩余高度：z=130.000–142.432mm；底部脚板及下方竖腿已删除。
- support剩余高度：z=130.000–132.032mm；其上方剩余几何为两个连通部分，仍属同一固定link。
- metal plate在截面上方，保持原样。
- 51个原mount碰撞块：30个完全位于截面以下而删除，18个用同一平面裁切，3个完全在上方而保留；每个被裁切的凸块只保留一个上部凸块。
- visual通过Manifold布尔运算使用相同截面；实际STL对比图见 `validation/horizontal_cut_comparison.png`。

| visual几何体积 | 来源 mm³ | 裁切后 mm³ |
|---|---:|---:|
| vpiper_main | 497097.795 | 345725.632 |
| vpiper_support | 171240.426 | 28430.277 |

## 质量与位姿

保留31个独立刚体、20个活动关节；全部joint定义和inertial参数与来源相同，arm/camera安装位置不变。全机质量保持 **45.64480826480732 kg**。删除几何后仍保留原质量、质心和惯量，这是本候选有意采用的仿真近似；没有按裁切后体积重新计算密度或质量。

来源：`../a2_piper_vpiper_final_20260906/a2_piper.urdf`（宽腕机支架、金属板碰撞高4mm版本）。合并候选见 `../a2_piper_v28_merged_20260909/README.md`。

## 证据与复现

几何记录：`validation/cut_geometry.json`；原参数对照：`validation/mass_pose_contract.json`；USD读回：`validation/usd_import_readback.json`。证据限于CPU几何构建与USD静态读回；未对本候选运行物理步进、策略或G0验收。

构建脚本：`scriptsFORhuman/v28/v28_build_cut_asset.py`。依赖当前IsaacLab环境中的NumPy、SciPy、trimesh，以及Manifold3D 3.5.3。本次Manifold安装在任务临时目录 `/tmp/v28_mesh_boolean`，未修改共享环境。构建命令（在仓库根目录执行，会重建指定候选目录）：

```bash
PYTHONPATH=/tmp/v28_mesh_boolean /home/baoquanc/anaconda3/envs/isaaclab/bin/python scriptsFORhuman/v28/v28_build_cut_asset.py --source gr00t/rl/data/robots/a2_piper_vpiper_final_20260906 --output gr00t/rl/data/robots/a2_piper_v28_cut_20260909
```

当前训练配置尚未选择任一候选；G0继续暂停，等待Owner判断。

USD MassAPI与本版URDF惯量参数的数值对照见 `validation/usd_mass_inertia_comparison.json`（包含每体质量、COM与完整惯量张量误差，USD浮点存储存在微小舍入）。
