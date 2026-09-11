# DONE

- 2026-09-11 HKT：按Owner要求生成180mm/45°与140mm/38.76°腕机局部四视图SVG、PNG预览、精确绘图变换和生成脚本，入口见`camera/wrist_comparison_20260911/README.md`。采用原U3视角和当前URDF原始网格，统一参考姿态/比例；140mm支架标为未验收示意包络。仅CPU绘图及视觉检查，未修改rig、asset或训练配置。

- 2026-09-09 HKT — v28 plan 冻结（`scriptsFORhuman/v28/a2_piper_base_v28_plan_20260909.md`）、待办登记建立、五个只读规划 lane 的证据归档到 `scriptsFORhuman/v28/planner_evidence_20260909/`。全部为 INSPECTED/STATIC/COMPUTED 证据，未运行 Isaac、未改 source/config，未 commit。

- 2026-09-09 HKT（-codex worker）：已实现robot/扁平scratch配置、动作夹紧与camera reward；compose STATIC_PASS、六项CPU语义测试通过。Owner明确真实CAD缺失、宽长方体支架与R3/R5修订。memory路由已登记。尚未完成完整G0，不能称runtime PASS或已commit。

- 2026-09-09 HKT（修改：-codex worker；依据：-owner）：已交付robots目录下合并版与z=130mm统一水平裁切版；URDF/USD均已生成，28/31刚体与20活动关节USD静态读回完成。安装位姿与质量合同记录在各目录validation，候选等待Owner选择，G0保持暂停。

- 2026-09-12 HKT（-codex worker）：执行D030–D035，完成MERGED/140mm/新姿态/K配置、USD读回、R1/R2/R3/R5与A4；C3保留旧轨迹FAIL。匹配默认姿态G0-L因stand三项相对误差失败后按Owner规则STOP，未继续PPO/G1或commit。
