# 本地复核与接入

从ZIP解压得到的 `a2_piper_vpiper_final_20260906/` 目录进入。不要将URDF单独复制而遗漏相对路径的meshes。

## 先做不涉及仿真的检查

```bash
python -m pip install -r requirements-static.txt
python tools/verify_models.py
python tools/verify_resources.py
```

两项预期分别为STATIC_PASS和RESOURCE_AND_SECONDARY_FORMAT_PASS。此时不含引擎验收，不会连接机器人。

用已安装的CadQuery重新计算承托面和板尺寸：

```bash
python tools/verify_mount_geometry.py
```

输出承托面92.431555 mm、金属板100 mm宽、最终Z=147.431555 mm。该脚本也保留源trunk BRep警告；不要把该警告静默改成PASS。

## 需要重建时

```bash
python tools/verify_mount_geometry.py
python tools/rebuild_plate_and_config.py
python tools/build_models.py
python tools/verify_models.py
python tools/verify_resources.py
```

重建脚本生成唯一默认坐标。不要编辑原来的 `source/previous_*.json` 以控制新模型；它们是可追溯参考，不是当前authority。实际配置为 `config/mount_parameters.json`，尺寸依据为 `validation/final_geometry_audit.json`。

## MuJoCo实际检查

当地已有MuJoCo时：

```bash
python tools/verify_models.py --mujoco
python tools/preview_mujoco.py --model scene.xml
```

第一条真正调用 `MjModel.from_xml_path`、`mj_forward` 并对照URDF FK；依赖缺失或编译失败会直接返回非零状态。第二条只显示检查姿态，不进行mj_step。检查姿态不是照片的关节反解，也不是实机动作命令。

## Isaac / 项目资源接入

主模型是 `a2_piper.urdf`；ROS路径版只改变资源URI。新模型不能仅覆盖旧USD的同名文件后假设缓存已刷新，应按本地资产流程重新导入并核对：trunk→arm_body0为 `[0.145,0,0.147431554755] m`；板碰撞全尺寸为 `[0.25,0.1,0.005] m`；arm_j0 parent仍为trunk；活动关节仍为20个。

核对导入器如何处理无inertial的固定安装件。URDF中的MuJoCo compiler扩展不能被认为会约束Isaac。不得无记录地通过默认材料密度给安装件自动加质量；同时不得把质量未补全的模型当作完整实机动力学模型。

原link名称、关节参数保留，但新增固定link可能使某些引擎body索引重排或合并。按名称校验，不应把先前body index数字直接当作不变。

## 补充质量参数

`config/mass_properties_to_complete.json` 的null是未知，不是已测得的零。取得各新增件质量、COM/惯量后，可使用：

```bash
python tools/apply_mount_masses.py \
  --mass-file measured_mount_masses.json \
  --confirm-not-already-in-source
```

JSON键为 `vpiper_main`、`vpiper_support`、`metal_plate_5mm`，各键下至少提供正的 `mass_kg`，以及 `measured_center_of_mass_link_m` 和 `measured_inertia_about_com_link_axes_kgm2`。只有显式接受均匀密度CAD近似时才加 `--accept-uniform-density`；工具不覆盖本轮名义模型。

## 范围

不选择Teacher、不改policy、不启动训练、不修改阈值、控制增益或源trunk collision。原源URDF在source中保留，仅供差分，不是可直接加载的另一套默认模型。
