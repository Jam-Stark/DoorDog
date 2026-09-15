# TODO

- m5 Owner暂停持续有效：不得恢复本机pull训练/评估。D019迁移交付已完成：代码已push，三个归档云端bytes/ID核实；见scriptsFORhuman/pull_v28/migration_manifest.json和同目录新机器AI提示。
- 新机器clone/pull指定分支，准备匹配IsaacLab环境，下载当前恢复包，按manifest还原相对repo目录和配置路径；无需先下载历史包即可resume。
- 明确新机器--resume后：2048三seed从1050/1400/1450 fullcheckpoint到6000，新attempt3；GPU1/2/3训练、GPU0串行补24条exact64自然lane。旧MISSING归档，P2/G0不重跑。
- 保留42个必要checkpoint重放和所有历史/partial消耗，不填0/3。原三seed6000后完成opening closure，无warm/Teacher/P3–P5。
