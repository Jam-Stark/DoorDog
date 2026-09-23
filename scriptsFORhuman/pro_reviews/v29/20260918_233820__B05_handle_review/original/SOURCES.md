# SOURCES｜v29 B05 独立审阅

访问日期：**2026-09-18**。只使用本次指定输入和下列一手产品/API来源支持关键技术结论。网页无可靠版本日期时不补造日期。

## 阅读与获取状态

两个普通ZIP共35个选定文件，逐项核对路径与字节数，与Worker manifest一致；读取范围为本题相关设计、参数、生成/消费/观察路径和三件局部mesh。远端另外读取审阅分支的七族设计、Teacher观察YAML及common配置片段。没有自行证明远端、本地和tracking全仓相等；该发布核对来自Worker。没有获取或依赖manifest外的checkpoint、训练日志或阶段产物。

**包内没有因读取失败而遗漏的文件；不等于对所有大文件做了全量代码审计。** 完整机器人其余资产不在输入范围，不能补推为存在。所有外部几何图纸读取失败项如下逐项保留，不引用未经本轮核对的历史图纸数值。

`FACTORY_TEXT`：厂家明示文字/尺寸字段；`FACTORY_IMAGE_QUAL`：厂家图只能支持定性形态；`DERIVED`：显式计算；`ENGINEERING`：拟议工程设计；`UNKNOWN`：缺证据；`LOCAL_ONLY`：需要本地运行/实物证据才能回答。本轮没有独立厂家实物测量，所谓“厂家标注”不是本轮拿卡尺实测。

官方页面的检索正文可以承载厂家字段，但不等于下载并复核了尺寸箭头。本轮没有成功读出的官方技术PDF/CAD，因而没有假造PDF页截图或CAD测量结果。

## 一手产品与API

### W01｜FSB 1147 官方产品页

- 原厂URL：<https://www.fsb.de/en/products/collections/fsb-1147>
- 状态与支持范围：已读正文。圆杆、锥形过渡、球形末端；没有读取到主握段直径、中心线或曲率图纸。
- 访问日期：2026-09-18。

### W02｜FSB 1108 官方产品页

- 原厂URL：<https://www.fsb.de/en/products/collections/fsb-1108>
- 状态与支持范围：已读正文和官方产品图。圆颈、斜接的椭圆握段、1178 return 版本；截面轴长与站距 UNKNOWN。
- 访问日期：2026-09-18。

### W03｜FSB Designed By 英文页：1226 / 1230 / 1294

- 原厂URL：<https://www.fsb.de/en/products/designed-by>
- 状态与支持范围：已读对应产品段。1226 平面及圆边；1230 形态；1294 英文称向外展开。没有数值几何。
- 访问日期：2026-09-18。

### W04｜FSB Designed By 德文页：1226 / 1230 / 1294

- 原厂URL：<https://www.fsb.de/produkte/designed-by>
- 状态与支持范围：已读对应产品段。1230 明确有 verkröpfte（偏置）版本；1294 德文称向外渐细，与英文冲突，不据此确定锥度方向。
- 访问日期：2026-09-18。

### W05｜FSB 1144 官方产品页

- 原厂URL：<https://www.fsb.de/en/products/collections/fsb-1144>
- 状态与支持范围：已读正文及官方产品图。只能支持流线/曲面握段，不能确认等径圆截面的浅 S。
- 访问日期：2026-09-18。

### W06｜FSB 1144：Jasper Morrison 官方访谈

- 原厂URL：<https://www.fsb.de/en/magazine/interview-jasper-morrison-fsb-1144>
- 状态与支持范围：已读设计历史。早期方案包含 S 形描述；不是现售型号的中心线、截面或制造图。
- 访问日期：2026-09-18。

### W07｜HOPPE Trondheim E1430Z/42FI，3058558

- 原厂URL：<https://www.hoppe.com/se-en/product/1000391521/trondheim-entrance-door-sets?FARBE=F69>
- 状态与支持范围：已读产品页与下载文件列表：8 mm 方轴、适用门厚 55–65 mm。PDF/DWG/产品图本轮未成功读出几何；不确认杆径、曲率、站距。
- 访问日期：2026-09-18。

### W08｜FSB 1107 官方德文产品页

- 原厂URL：<https://www.fsb.de/produkte/produktfamilien/fsb-1107>
- 状态与支持范围：读取官方检索正文：1107/1108 采用高椭圆握段，1107 为曲线造型，另有 1177 return。支持“曲线×椭圆”组合，不支持具体 R 或轴长。
- 访问日期：2026-09-18。

### W09｜ASSA ABLOY Nordic L，95450300031

- 原厂URL：<https://www.assaabloy.com/uk/en/solutions/products/door-furniture/scandanavian-lever-and-pull-handles/scanflex-range/lever-handles/nordic-l-lever-on-rose>
- 状态与支持范围：官方页面检索正文可读：杆径19、Handle length135、Handle projection62、rose直径54/突出6 mm。直接打开超时，尺寸箭头未复核；projection 不直接换算为 h。
- 访问日期：2026-09-18。

### W10｜ASSA ABLOY Nordic U，95449500031

- 原厂URL：<https://www.assaabloy.com/uk/en/solutions/products/door-furniture/scandanavian-lever-and-pull-handles/scanflex-range/lever-handles/nordic-u-lever-on-rose>
- 状态与支持范围：官方页面检索正文可读：round return to door；杆径19、Handle length142、Handle projection64、rose直径54/突出6 mm。原路径直接打开404；未读取尺寸箭头/CAD。
- 访问日期：2026-09-18。

### W11｜ASSA ABLOY 696 unsprung lever，47003151213

- 原厂URL：<https://www.assaabloy.com/uk/en/solutions/products/door-furniture/scandanavian-lever-and-pull-handles/classic-range/lever-handles/696-unsprung-lever-handle>
- 状态与支持范围：官方检索正文可读：Handle length106、Handle projection55、rose直径52/突出6.5 mm。截面尺寸/自由段 UNKNOWN。只作为较短、较小突出量的实例，不把106当中心线长。
- 访问日期：2026-09-18。

### W12｜GEZE LH103 oval，168534

- 原厂URL：<https://www.geze.com.cn/en/products-solutions/access_control_and_safety/door_hardware/door_handle_sets/handle_lh_103_oval/p_91480>
- 状态与支持范围：已读完整官方页：Diameter19、8 mm方轴；oval 指饰盖，不是椭圆杆。标题L与图片alt文字U、门厚40–55与表中40–50存在不一致，不据此证明回钩或适配门厚。
- 访问日期：2026-09-18。

### W13｜HEWI 111.23R 官方目录

- 原厂URL：<https://catalog.hewi.com/en-DE/product/6811699>
- 状态与支持范围：官方检索正文可读，直接访问受robots限制：U形、圆径23 mm。用于第二品牌的圆管return先例；精确return半径/净空 UNKNOWN。
- 访问日期：2026-09-18。

### W14｜OpenUSD UsdGeomCapsule

- 原厂URL：<https://openusd.org/release/api/class_usd_geom_capsule.html>
- 状态与支持范围：已读官方API。height/spine不含两端半球，支撑L与L+2r的区分；不等同PhysX导入/接触已验收。
- 访问日期：2026-09-18。

### W15｜Isaac Lab FrameTransformerCfg 官方源文档

- 原厂URL：<https://isaac-sim.github.io/IsaacLab/main/_modules/isaaclab/sensors/frame_transformer/frame_transformer_cfg.html>
- 状态与支持范围：已读官方文档；OffsetCfg位置为父框架局部、四元数wxyz。实际版本以包内dependency_evidence快照为准，不能以main在线版本替代本机。
- 访问日期：2026-09-18。

### W16｜FSB 北美官方下载入口

- 原厂URL：<https://www.fsbna.com/service-information/downloads>
- 状态与支持范围：已读入口，Catalog / Price Book 链接可识别；下列PDF下载/解析失败，不将历史摘录倒签为本轮核验。
- 访问日期：2026-09-18。

### W17｜FSB 2025 Catalog / Price Book（未读成功）

- 原厂URL：<https://fsb-website.fra1.digitaloceanspaces.com/website/documents/download-area/03_preisinformationen/neue-preislisten-ab-mai-2025/fsb-na-2025-catalog-price-book-compressed-meta.pdf>
- 状态与支持范围：尝试打开超时/读取失败。未复核任何图纸页或尺寸箭头；旧Pro的1076/1108/1144等数值不作为本轮独立确认尺寸。
- 访问日期：2026-09-18。

### W18｜HOPPE Trondheim 原厂数据表（未读成功）

- 原厂URL：<https://www.hoppe.com/hoppe_media.php?path=DOK_DS_3058558_SEN-SE_AOF_V1.pdf&t=1771117554>
- 状态与支持范围：尝试读取失败。另尝试页面列出的DRW_CAT_E1430Z-42FI_SALL_APRW_V1.pdf仍失败；DWG未解析。文件存在于官方列表不代表已读图。
- 访问日期：2026-09-18。

### W19｜GEZE LH103 原厂数据表（未读成功）

- 原厂URL：<https://www.geze.com.cn/en/download/file/GEZE_Product-data-sheet_EN_mw697800091480.pdf>
- 状态与支持范围：由产品页下载链接定位，读取失败；没有图纸尺寸结论。
- 访问日期：2026-09-18。

### W20｜GEZE Door Fittings 原厂产品册（未读成功）

- 原厂URL：<https://www.geze.com.cn/en/download/file/GEZE_Product-brochure_EN_mw836070.pdf>
- 状态与支持范围：由产品页下载链接定位，读取失败；没有图纸尺寸结论。
- 访问日期：2026-09-18。

### P01｜FSB 1108 官方产品图片

- 原厂URL：<https://res.cloudinary.com/franzschneiderbrakel/image/upload/c_fill%2Cdpr_auto%2Cg_auto%2Cw_664%2Cf_auto/q_auto/f_auto/website/products/1108/fsb-1108-door-handle-hartmut-weise-aluminum-natural-color-glossy-top-view.png>
- 状态与支持范围：网页工具已显示并人工视觉核对；未从照片估算尺寸。容器下载失败，交付文档仅引用远程原图，不宣称离线打包了图片。
- 访问日期：2026-09-18。

### P02｜FSB 1144 官方产品图片

- 原厂URL：<https://res.cloudinary.com/franzschneiderbrakel/image/upload/c_fill%2Cdpr_auto%2Cg_auto%2Cw_664%2Cf_auto/q_auto/f_auto/website/products/1144/fsb-1144-door-handle-jasper-morrison-aluminum-pure-top-view.png>
- 状态与支持范围：网页工具已显示并人工视觉核对；支持流线、宽扁握段的定性判断，未测量尺寸。容器下载失败，仅引用远程原图。
- 访问日期：2026-09-18。

## 项目证据索引

以下行号仅用于定位此次快照，较新本地文件应按函数名核对，不覆盖新改动。

### SRC-01｜范围/交付入口

- 文件：`scriptsFORhuman/v29/pro_handoff/20260918_b05/OWNER_REQUEST.md`
- 范围：同时读取REVIEW_BRIEF.md、SOURCE_INDEX.md、之后读取REAL_WORLD_SEEDS.md；Owner D026优先于历史Pro。
- 审阅分支链接：<https://github.com/Jam-Stark/DoorDog/blob/codex/v29-b05-pro-20260918/scriptsFORhuman/v29/pro_handoff/20260918_b05/OWNER_REQUEST.md>

### SRC-02｜已批准七族设计

- 文件：`scriptsFORhuman/v29/a2_piper_base_v29_b05_handle_design.md`
- 范围：§1–5：标称参数、I/J/G、有向轴、站距、回钩与质量语义。远端同分支此文件亦已读取。
- 审阅分支链接：<https://github.com/Jam-Stark/DoorDog/blob/codex/v29-b05-pro-20260918/scriptsFORhuman/v29/a2_piper_base_v29_b05_handle_design.md>

### SRC-03｜同源标称几何

- 文件：`scriptsFORhuman/v29/b05_designs_20260918/families.json`
- 范围：同时读取geometry_readout.json、visualization_readout.json、build_design_figures.py和README；PNG视觉核对，SVG XML结构读取。
- 审阅分支链接：<https://github.com/Jam-Stark/DoorDog/blob/codex/v29-b05-pro-20260918/scriptsFORhuman/v29/b05_designs_20260918/families.json>

### SRC-04｜当前门生成器

- 文件：`gr00t/rl/isaac_utils/playground/env_rand/door.py`
- 范围：305–321尺寸；407–491杆/轴/回返；635–657目标/FixedJoint；同时读取usd_utils.py几何/质量/collider帮助函数。
- 审阅分支链接：<https://github.com/Jam-Stark/DoorDog/blob/codex/v29-b05-pro-20260918/gr00t/rl/isaac_utils/playground/env_rand/door.py>

### SRC-05｜Teacher观察列表

- 文件：`gr00t/rl/config/obs/wbmanip/door_open_a2_base.yaml`
- 范围：actor/critic均列入privileged_door_info、gripper_handle_transform、door_dof_pos、hand_force。远端同分支亦已读取。
- 审阅分支链接：<https://github.com/Jam-Stark/DoorDog/blob/codex/v29-b05-pro-20260918/gr00t/rl/config/obs/wbmanip/door_open_a2_base.yaml>

### SRC-06｜观察getter和目标consumer

- 文件：`gr00t/rl/envs/door/door_open_a2_base.py`
- 范围：函数定位优先：_get_obs_gripper_handle_transform约28383；_get_obs_hand_force；_get_obs_privileged_door_info约28484；_compute_grasp_target约28550；scene_creation_callback约29945；旧LEFT处理约4935。只审本题相关路径，不声称逐行审计整个大文件。
- 审阅分支链接：<https://github.com/Jam-Stark/DoorDog/blob/codex/v29-b05-pro-20260918/gr00t/rl/envs/door/door_open_a2_base.py>

### SRC-07｜v29生效配置

- 文件：`gr00t/rl/config/ablation/wbmanip/base_v29_common.yaml`
- 范围：连同base_v29_baseline.yaml、exp/wbmanip/door_open_a2_base_lstm.yaml、env/door_open_a2_base.yaml、robot/A2_Piper/a2_piper_v29.yaml读取相关字段。TCP .085；指关节effort45；cameras disabled。
- 审阅分支链接：<https://github.com/Jam-Stark/DoorDog/blob/codex/v29-b05-pro-20260918/gr00t/rl/config/ablation/wbmanip/base_v29_common.yaml>

### SRC-08｜scenario/spawner

- 文件：`gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py`
- 范围：定向检查A2/v29 selector、DoorSpawner cfg、handle drive、axle override；没有查到v29将rand_axle_length覆盖为较短值。
- 审阅分支链接：<https://github.com/Jam-Stark/DoorDog/blob/codex/v29-b05-pro-20260918/gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py>

### SRC-09｜URDF与三件指部mesh

- 文件：`gr00t/rl/data/robots/a2_piper_v29_merged_20260917/a2_piper.urdf`
- 范围：同时程序读取meshes/piper/link7.STL、link8.STL、gripper_base.STL，转换到gripper-base核对边界与截面；不是整机可运行资产。
- 审阅分支链接：<https://github.com/Jam-Stark/DoorDog/blob/codex/v29-b05-pro-20260918/gr00t/rl/data/robots/a2_piper_v29_merged_20260917/a2_piper.urdf>

### SRC-10｜本机FrameTransformer依赖快照

- 文件：`dependency_evidence/frame_transformer_cfg.py`
- 范围：包内快照；出处由SOURCE_INDEX记录。本路径为交付证据路径，不假称一定存在于远端仓库。

### SRC-11｜plan/TODO/决策

- 文件：`scriptsFORhuman/v29/a2_piper_base_v29_baseline_plan.md`
- 范围：同时定向读取v29 README、baseline_TODO、decision_log（D020/D023–D026）、overall_arrangement。按讨论结案与实施分开解释。
- 审阅分支链接：<https://github.com/Jam-Stark/DoorDog/blob/codex/v29-b05-pro-20260918/scriptsFORhuman/v29/a2_piper_base_v29_baseline_plan.md>

### SRC-12｜历史Pro形状建议

- 文件：`scriptsFORhuman/pro_reviews/v29/20260918_102906__baseline_and_v28_pro_review/original/HANDLE_FAMILIES.md`
- 范围：独立几何初判后再读，连同SOURCES.md与REAL_WORLD_PARAMETER_TABLES.csv；历史工程值不是厂家测量，也不是本轮批准值。
- 审阅分支链接：<https://github.com/Jam-Stark/DoorDog/blob/codex/v29-b05-pro-20260918/scriptsFORhuman/pro_reviews/v29/20260918_102906__baseline_and_v28_pro_review/original/HANDLE_FAMILIES.md>

## 额外检索但未作为技术证据的材料

图片搜索中的经销商/聚合站照片、转售站尺寸、Scribd目录复制件没有用于确定几何尺寸、曲率或站距。Carlisle Brass的CSL1190官方页面检索文本可识别19 mm及图纸名，但直接访问403，本回包不再增加一行重复的19 mm样本。旧FSB图册摘录不因出现在历史Pro中而提升为本轮已验证的厂家图纸数据。

`REAL_HANDLE_COMPARISON.md`中的两张原厂照片采用远程引用，需要联网加载；图片权利属于FSB，仅供型号/形态审阅。`figures/worker_nominal_seven_family_atlas.png`是原Worker标称设计图，未修改，不是现实产品图也不是sim截图。
