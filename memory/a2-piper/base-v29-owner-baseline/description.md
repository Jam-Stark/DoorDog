---
name: base-v29-owner-baseline
status: active
scope: v29总体方向、baseline逐项讨论及已实施的Stage5/高度/腕机基础改进
last_verified: 2026-09-17
evidence: source/config/URDF/USD已实施；STATIC_PASS几何与配置；RUNTIME_PASS 64-env/1-batch PPO；策略质量未评估
read_when:
  - preparing or implementing base_v29
  - changing Stage5 heading/posture, door handle height or the wrist camera asset
source_of_truth:
  - scriptsFORhuman/v29/README.md
  - scriptsFORhuman/v29/a2_piper_base_v29_decision_log.md
  - scriptsFORhuman/v29/a2_piper_base_v29_overall_arrangement.md
  - scriptsFORhuman/v29/a2_piper_base_v29_baseline_TODO.md
  - gr00t/rl/envs/door/door_open_a2_base.py
  - gr00t/rl/config/ablation/wbmanip/base_v29_baseline.yaml
  - gr00t/rl/config/robot/A2_Piper/a2_piper_v29.yaml
  - gr00t/rl/data/robots/a2_piper_v29_merged_20260917/config/camera_rig.json
related_entries:
  - base-v28-camera-aware-rebaseline
  - novelty-research
---

# base_v29 Owner 基础改进

2026-09-18：Owner要求将baseline六项交Pro独立判断并调研现实门/latch/把手参数，同时验收v28并建议v29方向；V29-D006记录本次交付授权与边界。[Pro任务说明](../../../scriptsFORhuman/v29/pro_handoff/20260918/RESEARCH_BRIEF.md)。Pro意见未返回，六项仍待Owner确认。

2026-09-17 21:13 HKT：Owner 已确定 v29 总体方向与八卡分工：push baseline GPU0/1、pull同步GPU4/5各2 seed，N01 GPU2、N02 GPU3，GPU6动态、GPU7监控/eval等。N01/N02待baseline落地后进入独立branch/worktree；当前先研究并逐项讨论六项baseline议题。canonical入口为[总体安排](../../../scriptsFORhuman/v29/a2_piper_base_v29_overall_arrangement.md)与[baseline TODO](../../../scriptsFORhuman/v29/a2_piper_base_v29_baseline_TODO.md)，Owner确认整体clean后才落地正式baseline文档；未启动实验或创建worktree。

2026-09-17 21:22 HKT：三路只读研究已将六项初步事实/建议写入上述TODO，均待Owner确认。当前mass/hinge drive仍有随机化、native hinge friction关闭；generator已有50%末端回钩。相机旧表的21.22°由当前资产配旧j5=−0.415精确复现，当前j5=−0.52为15.206°，均相对trunk；两者非光学定义冲突。base仰角20–25°仅为基于历史有效render姿态的静态投影候选，不是已批准配置或v29成像通过。详细source和计算限定只从TODO读取。

2026-09-17（HKT），按 Owner“直接改，然后将基础改动记录”完成三项基础实现。canonical 决定与参数见 [V29-D001–D003](../../../scriptsFORhuman/v29/a2_piper_base_v29_decision_log.md)。

- Stage5 goal 保持 `[2,0,0.5]`；新增 goal heading 平方误差 scale=-4 与实际 roll/pitch 平方误差 scale=-8，后者和原 -2 合计 -10。新项仅在 Stage5 生效，不随 K 衰减；完成条件仍为 root_x>1.5。
- v29 bilateral uniform handle 高度为0.90–1.20m；natural eval 从 checkpoint 相邻 config 继承。v26 selector 不走另一路 linspace 的1.10m默认上限，且继续拒绝 v26+linspace 组合。
- MERGED腕机物理/光学180mm/45°，arm init/reset=`[0,.10,-.10,0,-.52,1.57]`；新资产几何核对默认光轴pitch=-15.206°。rig只有base_left/base_right/wrist三台相机；三台外壳visual隐藏、collision保留，支架可见。Owner追加要求后，旧中央包络的visual/collision/rig几何已完整删除；中央盒原先没有质量/惯量贡献，trunk保留原机身+三固定安装件合并的20.404808kg。

初版64-env/1-batch PPO在GPU4完成，exit0、step1、4096timesteps；中央碰撞包络删除后又按同规模复核最终资产。最新证据见 [运行读数](../../../scriptsFORhuman/v29/runtime_logs/baseline_no_center_smoke_20260917/runtime_readout.json)和[资产/配置核对](../../../scriptsFORhuman/v29/asset_and_config_verification_20260917.json)。接线运行未证明Stage5姿态改善、高把手成功率或成像质量；headless renderer有GPU Foundation初始化错误，未计为渲染通过。

v28已关闭，结论不回写。v29完整方案/正式预算随后制定；common继承的6000-batch默认值不是已启动预算。N01/N02已获Owner明确阶段归属决定，实施时机与研究证据边界见上述当前入口。
