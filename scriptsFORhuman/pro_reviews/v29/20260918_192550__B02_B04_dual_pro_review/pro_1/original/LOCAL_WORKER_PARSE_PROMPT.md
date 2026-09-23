请按项目AGENTS与memory入口接手Owner在当前对话上传的`pro_delivery__full_review.zip`。这是v29 B02/B04独立决策回包：来源仓库`https://github.com/Jam-Stark/DoorDog`，review分支`codex/v29-b02-b04-pro-20260918`，提交主题`Prepare v29 B02 and B04 Pro decision handoff`，提交时间`2026-09-18T17:14:54+08:00`。对应Worker输入目录为`https://drive.google.com/drive/folders/1RfrGhpw4hsi-FElR7Fc9L4UIrWjuuOBt`，但Pro回包以本次附件为准，不去Drive找答案。

在`scriptsFORhuman/pro_reviews/v29/`下建立新的B02_B04独立目录，保存原ZIP并解压FULL_REVIEW、DESIGN_SPEC与LOCAL_WORKER_PARSE_PROMPT。先读Pro对B02的A/B选择、B04限位选择与联合设计，再对照当前source/config、本机IsaacLab及已有runtime做定向可行性核对，保留原文、出处与证据等级，不覆盖本地较新的改动。重点核对锁态/复锁、原生限位API、角度与单位、实体latch/mimic拓扑、三DOF/natural/staged恢复、固定0.6rad与45°reward尺度，以及正常最大角和临时锁定限位的区分。

按最新Owner范围：B03保持15°并后置到v29 baseline出来后，不重新设相机/render前置；B01三档等权及closer有无各半沿用。将Pro选择、采用/调整意见与必要未知写入baseline plan/TODO及决策记录；旧软件偏好不能预设最终答案。云端静态结论不能冒充运行或训练PASS。当前接手限于解析与定向核对，不自动实施、启动训练、添加大规模测试、划掉未确认项、更新Teacher/G7或重开v28验收；实现按Owner后续指示推进。
