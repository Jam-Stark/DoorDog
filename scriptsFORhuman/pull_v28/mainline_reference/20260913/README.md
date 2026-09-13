# Pull v28 主线参考输入（2026-09-13）

此目录是已选择的参考输入，不是m5活动源码。SHARED_INPUTS_MANIFEST.json列出来源、相对路径、大小与用途；SHARED_INPUTS_RECEIPT.json记录实际接收/内容比对。

- files/gr00t/rl/data/robots/a2_piper_v28_merged_20260909/：本轮MERGED运行资产与必要依赖，供S1直接复制；不是让m5重新生成。
- files/gr00t/rl/config/robot/A2_Piper/a2_piper_vpiper.yaml：S2 robot配置。
- files/scriptsFORhuman/v28/camera/U3_F39_H140.json：名义rig；实际资产config/camera_rig.json一并提供。
- 其余Python为函数/语义参考；不得整文件覆盖pull env，不导入主线K、A284、D039选种或Teacher资格。步行helper/合同中的姿态命令须按pull真实依赖适配。
- 主线plan/decision/G0材料是来源依据；不证明pull运行或opening。文件清单不含训练checkpoint、凭据或工作流配置。A2_Base不在本次替换范围。

执行入口为仓库scriptsFORhuman/pull_task中的pull v28 plan、决策记录和启动prompt。先封存P2旧配方评估，再将S1–S8应用到活动路径。最终base布局/光学仍在C_S/G2。
