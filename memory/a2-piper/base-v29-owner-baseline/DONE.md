# DONE

- 2026-09-17 21:22 HKT：完成六项baseline首轮只读team研究并整合进TODO；核对当前randomization、latch/max-angle/shape语义，解释相机旧reset角差并计算base仰角候选。只有INSPECTED与静态计算证据；六项仍未决，无source/config/asset修改或新运行。
- 2026-09-17 21:13 HKT：按Owner当前指示登记v29总体GPU/方向安排和baseline六项讨论TODO，补V29-D004/D005；仅阶段方向与讨论流程已确定，六项结论尚未确认，未修改实现、启动实验或创建worktree。
- 2026-09-17 19:31 HKT：按Owner明确授权建立v29入口及V29-D001–D003决定记录，区分已确认基础改进、当前source事实与未实施事项，并添加memory/长期TODO路由。仅文档记录，未改训练源码、配置或asset，未运行实验或执行Git提交。
- 2026-09-17（HKT）：完成Stage5两项reward、v29 common/baseline/natural eval配置、独立robot及MERGED H180/F45 URDF/USD；恢复arm init/reset并隐藏三台相机外壳visual及中央碰撞包络visual，保留碰撞/质量。
- 2026-09-17 19:48:23–19:49:20 HKT：GPU4一次64-env/1-batch PPO完成，exit0、step1、4096timesteps；资产/配置静态核对通过，默认腕机光轴pitch=-15.206°。策略质量及渲染未验收，无正式训练、Git提交或实机操作。详细证据从description路由。
- 2026-09-17（HKT）：按Owner追加要求删除中央包络的visual/collision/rig几何；追溯MERGED质量计算确认其未计入质量/惯量，trunk保留原20.404808kg。v29 builder同步，当前只保留三台真实相机的包络。
- 2026-09-17 19:59:05–20:00:02 HKT：最终资产64-env/1-batch PPO复核完成，exit0、step1、4096timesteps，证据见`baseline_no_center_smoke_20260917/`。本轮资源使用结束。
