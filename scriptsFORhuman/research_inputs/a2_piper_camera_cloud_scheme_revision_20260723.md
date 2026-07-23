# A2 Piper 摄像头方案调研

**User:** Anonymous  
**Created:** 7/22/2026 1:25:32  
**Updated:** 7/23/2026 15:39:39  
**Exported:** 7/23/2026 16:21:25  
**Link:** [https://chatgpt.com/g/g-p-6a5fa04b1b588191bc51d34da6e5de18/c/6a5fab8a-77e8-83ea-95a0-df708822064b](https://chatgpt.com/g/g-p-6a5fa04b1b588191bc51d34da6e5de18/c/6a5fab8a-77e8-83ea-95a0-df708822064b)  

## Prompt:
2026/7/23 15:03:13

@GitHub 我是落地这个配置了发现太过靠近门的时候，handle会跑出图像外。我有以下几个idea，帮我针对当前A2 trunk配置思考每个方案的camera安装方式：
1 你可以考虑多camera配置，我的想法是arm腕部可以有一个，正面保持一个，左右两侧各一个，这样可以拼出一个base高度宽视角的大画面？ 或者base上的摄像头可以竖放，这样三个拼一起的话，竖向横向的FOV都会非常好。这需要你仔细思考如何安装在base上，多camera如何拼接？
2 当前这个camera 光路继续上抬+A2 原装 head camera，现在camer配置的问题就是垂直fov不够，不能兼顾前方和上方视野
3 我上传了A2加上piper和A2间连接件的STEP文件：A2足端版简化模型Vpiper.step。所以camera安装位置要考虑这个连接件的体积的。同时我希望A2 trunk上的camera安装位置能尽量贴近trunk，不要额外伸出去
4 camera型号改成用的比较多的Intel RealSense D435i

## Response:
2026/7/23 15:03:16

> **检查STEP文件和可用的CAD工具**
>
>
> **检查文件、安装库并解析几何信息与点云数据**
>
> 
>
> **搜索FreeCAD和OpenCascade相关下载链接**
>
> [FreeCAD | Download](https://freecad.github.io/Website/download/)
> [Download FreeCAD Free — 3D Parametric CAD Software](https://freecad-app.com/download/)
> [FreeCAD-asm3 – AppImages](https://appimage.github.io/FreeCAD-asm3/)
> [Releases · FreeCAD/FreeCAD · GitHub](https://github.com/FreeCAD/FreeCAD/releases)
> [FreeCAD: Installing FreeCAD on Linux - XSim](https://www.xsim.info/articles/FreeCAD/en-US/HowTo/Install-on-Linux.html)
> [FreeCAD: Your own 3D parametric modeler](https://www.freecad.org/downloads.php/blog.php)
> [FreeCAD Community Mirror · FreeCAD Community Mirror](https://freecadmirror.org/)
> [Getting Started – FreeCAD.info](https://www.freecad.info/getting-started/)
>
> **已搜索 8 个网站**
>
> 
>
> **检查GitHub API状态**
>
>
> **检查GitHub API状态并渲染图像数据**
>
> 
>
> **Searching D435i官方规格和文档**
>
> [D435i - RealSense](https://www.realsenseai.com/cn/products/d435i/)
>
> **已搜索 1 个网站**
>
> 
>
> **搜索GitHub分支并检查相关问题**
>
> 
>
> **搜索D435i多摄像头RGB同步信息**
>
> [Issue in hardware synchronization of two d435 Realsense camera · Issue #14131 · realsenseai/librealsense](https://github.com/IntelRealSense/librealsense/issues/14131)
>
> **已搜索 1 个网站**
>
> 
>
> **生成相机布局示意图**
>
>
> **生成相机布局示意图并分析图像**
>
> 
>
> **搜索官方D435i硬件规格和文档**
>
> [Issue in hardware synchronization of two d435 Realsense camera · Issue #14131 · realsenseai/librealsense](https://github.com/IntelRealSense/librealsense/issues/14131)
> [D435i - RealSense](https://www.realsenseai.com/cn/products/d435i/)
>
> **已搜索 2 个网站**
>
> 
>
> **获取当前仓库单摄像头支持代码**
>
> 
>
> **列出用户目录文件**
>
>
> **列出了用户目录文件**
>
> 
>
> **计算当前相机朝向与垂直视场**
>
>
> **计算相机朝向与垂直视场**
>
> 
>
> **检查文件路径和权限**
>
>
> **检查文件路径、权限和CAD工具环境**
>
> 
>
> **计算相机视野和高度要求**
>
>
> **计算相机视野和高度要求**
>
> 
>
> **正在搜索网页**
>
> [RealSense Stereo Series Product Family Datasheet - RealSense](https://dev.realsenseai.com/docs/realsense-stereo-series-product-family-datasheet/)
>
> **已搜索 1 个网站**
>
> 
>
> **正在搜索网页**
>
>
> **正在搜索网页**
>
> 
>
> **考虑布局选择**
>
> 在选择布局时，紧凑的风扇布局可能在马赛克拼接和壳体接合上表现较好；但分散的布局能够减少自遮挡，尤其在中心臂区域。为左右两侧提供不同模式可能是更理想的选择。
>
> **考虑了布局选择**
>
> 
>
> **考虑配置选择**
>
> 对于用户的需求，我推荐使用标准30fps的通用配置，并避免过度规格化。对于摄像头设计，可考虑使用外部工业集线器供电，避免假设所有摄像头都能从一个未供电的集线器中供电。
>
> **考虑了配置选择**
>
> 
>
> **细化安装建议**
>
> 我建议避免使用过于冗长的描述，同时保持足够的细节。如果涉及到硬件说明，确保引用官方产品数据表和推荐的扭矩值。
>
> **调整摄像头位置**
>
> 调整摄像头的位置时，需避免过度依赖特定坐标，确保侧面摄像头的视野覆盖并优化基线布局。关于15fps的摄像头，建议不重复当前帧。
>
> **调整了摄像头位置**
>
> 
>
> 思考了 36m 19s

# 基于当前 A2 trunk、连接件 STEP 与 D435i 的 Camera 安装方案修订

## 结论先行

这次有四个关键结论：

1. **仅把型号换成 D435i，不会解决当前垂直 FoV 问题。** 当前仿真 camera 约为 `69.4° H × 42.5° V`，而 D435i 的 RGB 正好约为 `69° H × 42° V`。也就是说，横放 D435i 几乎复现当前问题；必须依靠**竖装、上仰或多视角**。当前配置见固定 commit。 D435i 官方规格为 RGB `69°×42°`、最高 `1920×1080@30 fps`，RGB 使用 rolling shutter，机身约 `90×25×25 mm`。([RealSense](https://www.realsenseai.com/cn/products/d435i/))

2. **当前 `[0.25,0,0.14]` 不能作为实体 camera 安装点。** 我解析了上传的 `A2足端版简化模型Vpiper.step` 的 AP214 装配层级和 B-rep 顶点包围盒；与 DoorDog trunk 坐标对齐后，连接件简化包围盒约为：

   ```text
   x = 0.018 ～ 0.268 m
   y = -0.117 ～ +0.117 m
   z = 0.092 ～ 0.142 m
   ```

   当前 camera 点 `[0.25,0,0.14]` 落在连接件的前上边缘附近：距前缘约 `18 mm`，距顶面约 `2 mm`。这说明当前 pose 可作为仿真视点，但不能直接解释成实体镜头中心。

3. **A2 正前方不是一块空的安装面。** STEP 中前部中央模组的简化包围盒约为：

   ```text
   x = 0.284 ～ 0.386 m
   y = -0.048 ～ +0.048 m
   z = 0.036 ～ 0.128 m
   ```

   官方资料同时给出前雷达中心约为 `[0.33767,0,0.08134]`，且 A2 头部已经有一台光学 camera。因此，再把一台 D435i 正中贴在前脸上，会与原装 head camera、前雷达或其视场发生冲突。A2 原装 camera 为最高 `2568×1448@15 fps`、`132° H × 77° V`。`01-about_a2.html`

4. **最合理的总体结构不是“四台 camera 全部做全景拼接”，而是：**

   ```text
   A2 原装 head camera：低频、超宽 context
   左右 trunk D435i：高垂直 FoV、近距离 handle/gripper 观察
   Piper forearm/wrist D435i：近场抓取补充
   ```

   其中固定在 trunk 上的 camera 可以组成固定多视角输入；**wrist camera 不应与 trunk cameras 做几何全景拼接**，因为它的外参随关节运动持续变化。

---

# 1. STEP 几何对安装位置的约束

以下坐标均是将上传 STEP 的简化几何与 DoorDog `trunk`、Piper mount 和 A2 整体方向对齐后的近似结果。它们适合做 camera pose-search 和安装空间筛选，不应代替制造 CAD 公差。

## 1.1 连接件与 Piper 基座占用区

DoorDog URDF 中 Piper 固定在：

```text
parent: trunk
xyz: [0.145, 0, 0.154] m
```

STEP 解析得到的连接件主体约为：

| 方向 | 几何范围 |
|---|---:|
| X，前后 | `0.018-0.268 m` |
| Y，左右 | `±0.117 m` |
| Z，高度 | `0.092-0.142 m` |

加入至少 `10 mm` 静态安装余量后，建议把下面区域视为 **trunk camera keep-out zone**：

```text
x = 0.008 ～ 0.278 m
|y| ≤ 0.127 m
z = 0.082 ～ 0.152 m
```

此外，Piper base 位于 `x≈0.145, z≈0.154`，连接件正上方还必须留出 arm_j1 和后续 link 的动态 sweep 空间。**不建议把 D435i 平放在连接件顶面，也不建议在其上增加高立柱。**

## 1.2 前部 head / lidar 模组占用区

STEP 前部中央模组大约占用：

```text
x = 0.284 ～ 0.386 m
|y| ≤ 0.048 m
z = 0.036 ～ 0.128 m
```

扩大 `10 mm` 后建议视为：

```text
x = 0.274 ～ 0.396 m
|y| ≤ 0.058 m
z = 0.026 ～ 0.138 m
```

这产生一个重要的机械结论：

> 连接件前缘约为 `x=0.268 m`，前部 head 模组后缘约为 `x=0.284 m`，两者之间只有约 `16 mm`。D435i 厚度约 `25 mm`，因此无法把一台 D435i 正中嵌入两者之间。

正中 D435i 只有三个选择：

- 放到 head 模组前方，整体向前突出约 `25-35 mm`；
- 放到 head 模组上方，进入 Piper sweep 风险区；
- 横向移到 head 模组左右两侧。

第三种最符合“贴近 trunk、不额外伸出去”的要求。

## 1.3 推荐的低轮廓安装区

| 安装区 | Optical center 候选范围 | 适合用途 |
|---|---|---|
| 前左/前右 cheek | `x=0.285-0.305`，`|y|=0.070-0.090`，`z=0.060-0.095` | 主 manipulation camera，避开正中 head 模组 |
| 左右 side cheek | `x=0.200-0.250`，`|y|=0.135-0.155`，`z=0.055-0.095` | 侧向互补、arm 遮挡恢复 |
| 连接件顶面中央 | 不推荐 | 与 Piper 基座和 arm sweep 冲突 |
| 正中 head 前方 | 条件性使用 | 会前突，且必须验证对原装 camera 和雷达的遮挡 |
| trunk 后部 | 不推荐作为开门主视角 | Piper、trunk 和 head 容易遮住 handle |

这些值是**光学中心搜索范围**，不是 D435i 外壳中心，也不是可直接写入 IsaacLab 的 quaternion。RealSense ROS 中 `camera_link` 以左 IR/depth frame 为基准，RGB optical center 与之有固定偏移；最终 URDF 和仿真必须以 `color_optical_frame` 为 camera pose，而不是拿外壳中心代替。([GitHub](https://github.com/realsenseai/realsense-ros))

---

# 2. 方案 1：正面 + 左右侧 + wrist 的多 Camera 架构

## 2.1 这个方向总体可行，但应拆成两个子系统

```text
固定 trunk rig：
  front / left / right
  外参固定，可构成 base multi-view

Piper camera：
  forearm / wrist
  外参随关节运动，不属于同一个静态 panorama
```

RealSense 官方多 camera 文档本身就演示过将多台 D4xx camera 竖向安装成半环，以获得更宽的组合 FoV；文档同时明确指出，由于各 camera optical center 并不重合，组合视野中必然存在非重合和视差区域。([RealSense](https://dev.realsenseai.com/docs/multiple-depth-cameras-configuration))

所以你的“竖放三个 camera 拼成 base 高度大画面”这个方向是有工业先例的，但对于门把手这种 `0.2-0.6 m` 近场对象，应该做**多视角 mosaic**，而不是传统 panorama blending。

---

## 2.2 Base 上三台 D435i 的安装方式

### 方案 1A：三台 D435i 全部竖装

D435i 横放时 RGB FoV 为：

```text
69° horizontal × 42° vertical
```

竖装并在软件中旋转图像后，世界中的有效覆盖近似变为：

```text
42° horizontal × 69° vertical
```

这正好针对当前“靠近时 handle 从图像上方跑出去”的问题。

### 推荐安装姿态

| Camera | 安装位置 | Housing | Optical axis |
|---|---|---|---|
| Front-primary | 前左或前右 cheek，避开正中 head 模组 | 90 mm 长边竖直 | 上仰 `15°` 左右；轻微转向 handle workspace |
| Left | trunk/连接件左侧面 | 长边竖直 | 相对前方左转约 `28-32°`，上仰 `10-15°` |
| Right | trunk/连接件右侧面 | 长边竖直 | 相对前方右转约 `28-32°`，上仰 `10-15°` |

Front-primary 不建议放在 `y=0`。当前 `right/out` door 配置下，可以优先把它放在机器人右侧，即约：

```text
x ≈ 0.295 m
y ≈ -0.075 m
z ≈ 0.075-0.085 m
```

它的 25 mm 宽度在 Y 上约覆盖 `[-0.088,-0.063] m`，与正中 head 模组 `|y|≤0.048 m` 之间仍有约 `15 mm` 间隙。这个位置同时接近连接件前缘，不需要长悬臂。

### 组合 FoV

若三台都竖放：

- 单台约 `42° H × 69° V`；
- 左右相对前方偏转约 `±30°`；
- 每个侧视角和 front 约有 `12°` 水平重叠；
- 总水平覆盖约为 `102°`；
- 整个 base rig 的垂直覆盖约为 `69°`。

相比当前约 `69°×42.5°`，水平覆盖增加约 `33°`，垂直覆盖增加约 `26.5°`。

若把 front camera 上仰 `15°`，它的垂直角范围大致变为：

```text
下方约 -19.5°
上方约 +49.5°
```

在 camera 到 handle 水平距离为 `0.3 m` 时，对应大致覆盖：

```text
向下约 0.106 m
向上约 0.351 m
```

这比当前约 `±21°` 的垂直视场更适合 base camera 低于 handle 的几何关系。A2 机身高度还可在约 `0.3-0.5 m` 范围内调节，因此最终 pitch 必须覆盖不同 body height，而不能只按单一站姿选定。`05-a2_remote_control.html`

### 全竖装的不足

侧 camera 向外偏转越大，中央 handle 越可能只出现在 front camera 中。若目的是在 front 被 Piper 遮挡时让 side camera 仍看到 handle，不应把 side camera 转到 `±45°` 或 `±90°`。

建议：

```text
全景优先：yaw ±28-32°
中央 handle 冗余优先：yaw ±15-22°
```

当前任务更应优先中央 handle 冗余，而不是追求接近 180° 的环境 panorama。

---

## 2.3 更推荐的混合方向：front 竖装，左右横装

另一种更平衡的布局是：

| Camera | Orientation | RGB FoV |
|---|---|---|
| Front | portrait | `42° H × 69° V` |
| Left | landscape | `69° H × 42° V` |
| Right | landscape | `69° H × 42° V` |

左右 camera 约偏转 `±25-30°`。以 `±30°` 为例：

```text
Left:  -4.5° ～ +64.5°
Front: -21°  ～ +21°
Right: -64.5° ～ +4.5°
```

总水平覆盖约 `129°`，而且左右 camera 都能看到接近中央的区域。Front portrait 专门保证 handle 的纵向覆盖，左右 landscape 则保证 door panel、door edge 和 lateral base motion。

**这套混合布局从任务角度通常优于“三台全部竖放”：**

- front 解决垂直不足；
- sides 解决横向覆盖和 arm 遮挡；
- side D435i 的 90 mm 长边可沿连接件 X 方向布置，仍然贴近 side face；
- 不需要让左右 camera 向外转得过大。

若最终目标是“handle 不出画 + door swing context”，我更倾向该混合布局。

---

# 3. 多 Camera 应如何拼接

## 3.1 不建议做传统 panorama stitch

下面这些方法不适合作为 policy 输入：

- SIFT/ORB 特征匹配后实时 homography；
- 自动找 seam 并 feather blend；
- 假设三台 camera 共用一个 optical center；
- 把 wrist camera 也纳入 cylindrical panorama。

原因是 camera baseline 相对工作距离太大。

例如相邻 camera 光心相距约 `0.14 m`，handle 距 camera 约 `0.3 m`，仅由基线产生的观察角差约为：

```text
atan(0.14 / 0.30) ≈ 25°
```

door panel 可以近似平面，但 gripper、handle、arm 和旋转中的 door edge 都不在同一平面上。传统 homography 会在最关键的 handle/gripper 区域产生：

- 双影；
- 拉裂；
- seam 跳动；
- 一台 camera 被 arm 遮挡时的错误融合；
- 不同时间帧造成的运动重影。

## 3.2 推荐：固定多面板 mosaic

对三台 D435i，可以在不改变当前 `384×216` 视觉 tensor 大小的情况下拼接：

```text
Left 126×216
3 px separator
Front 126×216
3 px separator
Right 126×216

126×3 + 3×2 = 384
```

处理顺序：

```text
每台 camera RGB
→ 各自去畸变
→ portrait camera 旋转 90°
→ 固定 crop
→ resize 到 126×216
→ 固定顺序 L | F | R
→ 组成 384×216
→ ImageNet normalization
→ 现有 ResNet18
```

这不是几何意义上的单一 panorama，而是一个**视角身份固定的多视图 canvas**。对于 CNN 来说，固定 seam 比每帧变化的 panorama seam 更容易学习。

建议：

- 使用固定黑色或中性灰 separator；
- 所有 camera 固定 manual exposure、gain 和 white balance；
- 训练时随机 drop 一块 panel；
- 分别随机化三个 panel 的 exposure、blur、frame delay；
- 永远保持相同的 L/F/R 排列；
- 不对左右图做镜像。

DoorMan 使用 D435i 的 RGB-only 输入，并依靠 recurrent policy、camera randomization 和 motion-blur randomization处理 legged robot 上的部分可观测性；它也以 50 Hz 运行，而 D435i RGB 本身最高为 30 fps。`Xue 等 - 2025 - Opening the Sim-to-Real Door for Humanoid Pixel-to-Action Policy Transfer.pdf`

## 3.3 Wrist camera 不放进这个 base mosaic

Wrist camera 的 pose 会随 `arm_j5/j6` 和 gripper 运动改变。把它与固定 base cameras 放在同一个“全景坐标系”里，会让同一个图像区域在不同时间代表完全不同的空间方向。

推荐模型结构：

```text
Base 3-camera mosaic → ResNet18 → 128D
Wrist RGB            → shared ResNet18 → 128D
81D proprio          → MLP
                         ↓
                 fusion + LSTM
                         ↓
                      12D action
```

第一阶段 wrist camera 可以只录制，不进入 Student。只有当 base mosaic 在 pregrasp/finger-close 阶段仍然存在不可恢复遮挡时，再启用第二视觉分支。

不建议为了保持单 tensor 而做四格 `2×2 × 192×108` mosaic；那会明显降低每一路 handle/finger 的有效像素密度。

---

# 4. Wrist D435i 的安装方式

## 4.1 不建议直接横跨 gripper base

D435i 长 `90 mm`，不适合横跨 Piper 两指或装在 gripper 正上方。更合理的是将其作为**forearm-mounted wrist view**：

```text
parent link: arm_body5 或 arm_body6
housing long edge: 沿 forearm 方向
orientation: landscape
optical axis: 指向 virtual TCP / handle workspace
```

DoorDog URDF 中 `arm_body6_to_gripper` 是 gripper base，两个 finger 从该 frame 的 local `+Z` 方向约 `0.1358 m` 处展开。

### 推荐几何关系

不先给具体 link-local xyz，而是要求满足：

| 参数 | 建议 |
|---|---:|
| Camera 到 virtual TCP 的距离 | `0.22-0.30 m` |
| Camera 相对 finger closing plane 的偏置 | `40-60 mm` |
| Optical axis target | 两指之间、handle grasp point 前后约 `0-50 mm` |
| Housing | 紧贴 arm_body5/6 dorsal side |
| Dynamic clearance | 对 fingers、handle、door panel ≥`20 mm` |
| Cable service loop | 位于 arm_body5 附近，不进入 finger 区 |

D435i 最大分辨率下 depth Min-Z 约为 `0.28 m`，因此这种 wrist 安装若距离 handle 小于约 `0.28 m`，**只能把它当 RGB camera 使用，不能指望稳定近场 depth**。([RealSense](https://www.realsenseai.com/cn/products/d435i/))

这与 DoorMan 的使用方式一致：D435i 但关闭 depth。`Xue 等 - 2025 - Opening the Sim-to-Real Door for Humanoid Pixel-to-Action Policy Transfer.pdf`

## 4.2 为什么优先挂在 arm_body5 而不是 gripper

- 减少末端附加惯量；
- 避免 camera 随 arm_j6 高频旋转；
- 降低 rolling-shutter RGB 的运动畸变；
- USB-C 线缆不需要在 gripper 附近形成大 service loop；
- camera guard 不容易撞到门板或 handle；
- 仍能以斜后方视角观察两指和 handle。

代价是 wrist rotation 后 camera 与 fingers 的相对视角会变化，需要全 joint sweep 检查。

上传的 STEP 主要足以约束 trunk、连接件和静态外包络，不能替代 Piper 全关节 sweep。因此 wrist bracket 仍需要完整 Piper CAD 或在仿真中对所有 j1-j6 轨迹做 swept-volume 检查。

---

# 5. 方案 2：上抬光路 + A2 原装 Head Camera

这是硬件复杂度最低、最值得先做的原型，但应该把“上抬”理解为：

> **camera optical axis 上仰 + D435i 竖装，而不是把 camera 整体架高。**

连接件顶面和 Piper base 已经占据 `z≈0.09-0.15 m`，继续向上抬实体 camera 会进入 arm sweep。更合理的是把 D435i 放在 front cheek 或 side cheek，并把光路上仰。

## 5.1 推荐安装

```text
A2 head camera：
  保持原装
  负责 approach、door frame、door panel、wide-open context

D435i：
  安装在 front-right / handle-side cheek
  长边竖直
  optical center 约：
    x = 0.285-0.305 m
    y = -0.070--0.090 m
    z = 0.060-0.095 m
  optical axis：
    向 handle workspace 上仰约 15-25°
    向机器人中轴内转约 5-15°
```

当前场景固定为 right/out，因此先将 manipulation D435i 放在机器人右侧，较有机会绕开居中的 Piper 观察右侧 handle。这个结论属于 **INFERENCE**，需要与左侧镜像位置做同轨迹比较，不能仅靠静态图片决定。

## 5.2 两个 camera 的职责不能互换

A2 原装 head camera：

- `132° H × 77° V`，上下文非常好；
- 最高只有 `15 fps`；
- raw latency、timestamp、exposure 和 shutter 均尚未验证。`01-about_a2.html`

因此它适合：

- reset；
- approach；
- staging；
- door frame；
- door swing；
- base方向和开口位置。

D435i：

- 30 fps RGB；
- 竖装后 `42° H × 69° V`；
- 负责 handle、gripper 和近距离闭合；
- 仍需针对 rolling shutter 使用短曝光。([RealSense](https://www.realsenseai.com/cn/products/d435i/))

## 5.3 输入融合

低风险版本：

```text
Student 仍只用 D435i
A2 head camera 只录像和可见性评估
```

正式双视角版本：

```text
A2 head → context encoder
D435i   → manipulation encoder
异步 feature fusion
```

不建议先把 A2 head 和 D435i 硬拼成传统 panorama，因为：

- 一个是超宽 head optics；
- 一个是普通 pinhole RGB；
- frame rate 为 15 vs 30 fps；
- lens distortion 和 frame age 不同；
- optical center 分离。

如果为了静态 observation tensor 必须做 canvas，应把它理解成两个 panel，而非连续画面。

---

# 6. 方案 3：紧贴 trunk、避开连接件的 Bracket 形式

## 6.1 推荐一体式“下挂环抱” rig

不要为每台 camera 单独设计长臂。推荐做一块围绕连接件前缘和两侧的一体 bracket：

```text
俯视：

            A2 head / lidar
                 │
       ┌─────────┴─────────┐
       │ front-cheek mount │
  left │                   │ right
  wing │  connector/Piper  │ wing
       └───────────────────┘
```

结构特征：

- 主横梁固定在连接件前下沿；
- 左右翼贴着连接件或 trunk 两侧；
- camera 背面距结构面约 `2-5 mm`；
- camera optical face 仅比现有结构外包络突出约 `25-30 mm`；
- 不在 top surface 设置竖杆；
- 不把力加载到塑料外壳；
- 优先复用 A2 背部负载孔或 Piper 连接件已有紧固点。

A2 官方页面提供背部负载孔位图，但具体用户这套连接件覆盖了哪些孔位，仍需以 STEP 和实机测量为准。A2 站立外宽约 `440 mm`；若 side camera 最外侧控制在 `|y|≈0.16-0.17 m`，三 camera rig 仍可保持在约 `320-340 mm` 总宽度内，不会超过 A2 整体站立宽度，但仍需检查腿部高速运动包络。`01-about_a2.html`

## 6.2 机械限制

| 项目 | 要求 |
|---|---:|
| Camera/body 静态间隙 | ≥`5-10 mm` |
| Piper 动态 sweep 间隙 | ≥`20 mm` |
| Camera 前向额外突出 | 目标≤`30 mm` |
| Camera 侧向额外突出 | 目标≤`20-30 mm` |
| Bracket 悬臂长度 | 尽量≤`30 mm` |
| Camera 相对 trunk 动态摆动 | <`1 mm` / <`0.5°` |
| 线缆与 arm/door动态间隙 | ≥`20 mm` |

Bracket 应采用刚性铝板或碳板。薄阻尼垫可以隔离高频振动，但不能用厚泡棉把 camera 变成低频摆锤。

## 6.3 线缆

- Base cameras 使用短 USB3 线进入连接件下方；
- 在 bracket 上做独立 strain relief；
- camera connector 处不承担线缆拉力；
- Wrist camera 使用高柔线，直接走 arm；
- Wrist camera 最好独占一个主机 USB3 口；
- Base cameras 可共用经过实测的外接供电 USB3 hub。

A2 官方资料列出了 PC1 的 USB3 Type-C 端口、PC2 的 USB3/USB2端口和 `12 V/24 V` 电源输出，但文档同时提示不同方案配置可能有差异。因此最终必须实机确认各端口是否属于独立 host controller。`01-about_a2.html`

RealSense 官方多 camera 文档建议：

- 使用外部供电 USB3 hub；
- 短且高质量的线缆；
- 直接连接 PC 通常比共享 hub 更稳定；
- 高带宽多 camera 需要核对 USB controller，而不能只数接口数量；
- 单台 D4xx 功耗可接近或超过约 `2 W`。([RealSense](https://dev.realsenseai.com/docs/multiple-depth-cameras-configuration))

---

# 7. D435i 用于多 Camera 时的特别限制

## 7.1 30 fps 对 50 Hz Policy

D435i RGB 最高 30 fps，而当前高层 policy 是 50 Hz。DoorMan 同样使用 D435i RGB-only 和 50 Hz policy，因此这个组合本身有成功先例，但意味着：

```text
部分 policy step 必须重复上一帧
```

`Xue 等 - 2025 - Opening the Sim-to-Real Door for Humanoid Pixel-to-Action Policy Transfer.pdf`

必须训练或验证：

- frame repetition；
- 0-2 control-step image delay；
- independent camera delay；
- dropped frames；
- rolling-shutter blur；
- manual exposure。

## 7.2 RGB 多机同步

RealSense 的 D400 多机硬件同步主要围绕 depth/IR imager。RealSense 官方仓库的支持说明指出，D435 类设备的普通 slave mode 通常只同步 depth，而 RGB 全同步模式原本主要面向 D415，且在 D435 类设备上不能作为可靠默认。([GitHub](https://github.com/IntelRealSense/librealsense/issues/14131))

因此多台 D435i 的 policy RGB 应按以下方式设计：

```text
每台 camera 独立采集线程
每帧保存 hardware/system timestamp
policy tick 选择各路最新完整帧
max timestamp skew 超阈值时复用上一组完整 tuple
```

初始门限建议：

| 指标 | 建议门限 |
|---|---:|
| Base cameras tuple skew p95 | ≤`15 ms` |
| Frame age p95 | ≤`50-60 ms` |
| 连续丢帧 | ≤`2 frame intervals` |
| 30分钟 drop ratio | <`0.1%` |

## 7.3 Rolling shutter

D435i 的 depth imagers 是 global shutter，但 RGB sensor 是 rolling shutter。([RealSense](https://www.realsenseai.com/cn/products/d435i/))

因此：

- trunk camera 需要限制 RGB exposure；
- wrist camera 风险更高，因为有额外 joint angular velocity；
- 优先利用 A2 头部照明灯补光；
- 自动曝光不能允许在白门板前突然拉长；
- wrist D435i 不应成为唯一 close-loop camera。

## 7.4 Depth

建议第一阶段与 DoorMan 一样：

```text
RGB enabled
depth disabled
IR projector disabled
```

`Xue 等 - 2025 - Opening the Sim-to-Real Door for Humanoid Pixel-to-Action Policy Transfer.pdf`

Depth 只用于：

- camera rig 标定；
- 可见性 ground truth；
- camera 到 handle 的离线距离统计；
- collision/occlusion诊断。

如果将来启用多个 D435i depth，还需要重新验证近场 Min-Z、IR重叠、金属handle和同步。

---

# 8. 三种落地方案的排序

## 方案 A：A2 Head + 两侧竖装 D435i + Wrist D435i

**这是机械上最推荐的最终目标。**

```text
Front context：A2 原装 head camera
Left close-up：D435i portrait
Right close-up：D435i portrait
Wrist close-up：D435i landscape，先 shadow
```

优势：

- 不在 A2 head/lidar 正前方再堆一台 camera；
- 两侧 D435i 可贴着连接件侧面；
- A2 head 已有 `132°×77°` wide context；
- 两侧 camera 都能从不同角度绕开 Piper；
- wrist camera 只在必要时加入 policy。

风险：

- A2 head 只有15 fps；
- head camera raw latency和外参未知；
- 需要异步多 encoder，而不是简单单 panorama。

## 方案 B：三台 Base D435i + Wrist D435i

**这是保持同型号、便于做固定 `384×216` mosaic 的方案。**

```text
Base D435i L/F/R → 3-panel 384×216
Wrist D435i → separate branch / shadow
A2 head → logging only
```

优势：

- 所有 base view 同型号、同帧率、类似颜色响应；
- 三 panel 可以完全保持当前图像 tensor shape；
- 不依赖 A2 head stream接口。

风险：

- front D435i 必须离开 `y=0`，或外置到 A2 head前方；
- 需要严格检查原装camera和前雷达遮挡；
- 3-4 台 D435i 的USB、线缆和功耗更复杂。

## 方案 C：一台竖装 D435i 上仰 + A2 Head

**这是最推荐先做的低成本 prototype。**

```text
Front-right cheek D435i portrait
+
A2 head camera
```

优势：

- 直接测试“纵向 FoV不足是否是主因”；
- 只增加一台D435i；
- 连接件和线缆最简单；
- 可以先完全不改 Student，让 A2 head 只记录。

风险：

- 仍只有一个高帧率 manipulation angle；
- Piper 完全遮挡时，A2 head可能只提供低频wide view；
- 若自遮挡是主因，后续仍需第二侧 D435i。

---

# 9. 建议实施顺序

## R1：单台竖装 D435i + A2 Head shadow

安装在 front-right/handle-side cheek：

```text
x ≈ 0.295 m
y ≈ -0.075 m
z ≈ 0.075-0.085 m
portrait
pitch up ≈ 15-25°
```

只做：

- CAD clearance；
- RGB录制；
- handle/gripper visibility；
- frame age；
- motion blur；
- A2 head和D435i同步日志。

不直接写最终 quaternion。

## R2：增加 opposite-side D435i

两侧 camera 均瞄准同一个 nominal manipulation workspace：

```text
trunk-relative target：
x ≈ 0.55-0.70 m
y ≈ 0
z ≈ 0.25-0.35 m
```

这时判断：

- 两侧是否真的在 front被arm遮挡时看到handle；
- 是否需要三panel mosaic；
- A2 head是否值得进入policy。

## R3：构建三 Base Camera mosaic

只有当三台均为 D435i 时，优先采用：

```text
126 | 3 | 126 | 3 | 126 = 384
```

而不是 panorama warp。

## R4：Wrist D435i shadow

挂在 `arm_body5/6`，录制但不进 Student。只有当 base views 在 finger-close/unlatch 阶段硬性失败，才加入第二视觉encoder。

---

# 最终建议

当前最合理的修订方案是：

> **实体架构按“A2原装head + 左右两台贴身竖装D435i + 一台forearm/wrist D435i预留”设计。第一阶段只启用一台handle-side D435i作为Student输入，A2 head与wrist做shadow记录；根据遮挡数据再增加第二侧camera和视觉融合。**

如果你希望保持现有 `384×216` 单视觉 tensor 且所有 base camera 使用同型号，则采用：

> **三台 base D435i 固定 mosaic，front camera放在正中head模组侧面的off-center cheek，而不是放在 `[0.25,0,0.14]` 或正中前脸；wrist camera保持独立，不参与全景拼接。**

当前最不推荐的是：

```text
D435i 正中装在连接件顶面
+
四路图像做实时homography panorama
```

前者与连接件/Piper/head几何冲突，后者会在最关键的近场handle与gripper处产生严重视差和重影。

---

**Sources:**

- [https://www.realsenseai.com/cn/products/d435i/](https://www.realsenseai.com/cn/products/d435i/)
- [https://github.com/realsenseai/realsense-ros](https://github.com/realsenseai/realsense-ros)
- [https://dev.realsenseai.com/docs/multiple-depth-cameras-configuration](https://dev.realsenseai.com/docs/multiple-depth-cameras-configuration)



---
Powered by [ChatGPT Exporter](https://www.chatgptexporter.com)