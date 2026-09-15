# TODO

- m5 Owner暂停：不得恢复本机pull训练/评估。当前任务只完成code commit/push、有效未追踪恢复文件GoogleDrive上传、migration manifest/脚本/新机器AI说明。
- 新机器clone/pull指定分支，准备匹配IsaacLab环境，下载当前恢复包，按manifest还原相对repo目录和配置路径；无需先下载历史包即可resume。
- 明确新机器--resume后：2048三seed从1050/1400/1450 fullcheckpoint到6000，新attempt3；GPU1/2/3训练、GPU0串行补24条exact64自然lane。旧MISSING归档，P2/G0不重跑。
- 保留42个必要checkpoint重放和所有历史/partial消耗，不填0/3。原三seed6000后完成opening closure，无warm/Teacher/P3–P5。
