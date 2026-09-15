# 新机器 AI 接续提示（2026-09-15）

请直接接续 DoorDog A2_Piper pull v28 原实验。Owner 已授权迁移和新机器按原合同恢复，无需再问一次启动批准。D019 明确停止 m5 上的本轮训练、评估和等待；不要在 m5 重启任务。先按仓库 AGENTS.md 和 file-based memory 路由读取当前状态，优先 memory/a2-piper/pull-v28-baseline-sync/description.md、TODO.md、原 baseline sync plan 和 decision log 的最新 D019；其中历史停止门不能覆盖最新迁移授权。

代码 origin 为 git@github.com:Jam-Stark/DoorDog.git，分支 codex/a2-piper-pull-v0-20260803。精确交付 commit 以迁移 receipt 为准。Drive 目录：
https://drive.google.com/drive/folders/1h1Z3gNXrX_JhtEv3s4N8shCL9ULeSYjX

下载 migrate.py、migration_manifest.json，以及 resume_core.tar.zst 完整包或 manifest 指定的全部分片。history.tar.zst 是可选历史证据包，不是恢复训练前置。manifest 的文件 ID、顺序和 bytes 是下载依据；不要添加哈希。完整包优先；分片由脚本按 manifest 顺序拼接。可用浏览器预下载到 --archive-dir（不需 Drive 凭证），或使用已配置 rclone remote，或通过环境变量 GOOGLE_DRIVE_ACCESS_TOKEN 做认证下载；不把凭证写入代码/报告。

请保留恢复事实：
- 当前有效组是 pull_v28_rebuild_2048_20260914，2048 environments，每 seed 总目标 6000，save_frequency=250，checkpoint_load_mode=full，auto_load_latest=false；保持当前 PPO H64、5 epochs、4 minibatches、lr1e-4 和 reward/reset/events/ready/Stage4 合同。
- PA_S1/PA_S2/PA_S3 分别从同 seed 的完整 checkpoint 1050/1400/1450 恢复，文件路径用 manifest 的 resume_input_step*.pt。不要拿旧 1024/4096 checkpoint，不要 scratch 重训或只载权重。
- 中断前完成 3942 batches，持久 checkpoint 合计 3900；后续到三格 6000 尚需 14100，42 个必要 checkpoint 重放单列，并保留历史/partial 消耗。attempt 2 因 YAML 字符串计数错误在训练前失败，新增 0 batch、实际 eval 0，不能重复计为训练。当前代码已改成解析 YAML 根字段。
- 新训练 attempt 3：PA_S1/2/3 使用 GPU 1/2/3；GPU 0 单队列补齐 1500/3000/4500/6000 × 三 seed × 左右侧，共 24 条 exact64 natural lane。旧 queue/MISSING/decision 全部保留到归档目录，不当作有效评估。
- P2 18/18 与 G0 PASS（累计 10/32）直接复用，不重跑 P2/G0/contact/PG7，不加 GPU smoke、额外测试、扫描、warm、Teacher、P3–P5。

先做环境和文件准备：
1. 新机器使用 Linux，安装 Git/SSH、Git LFS、tar+zstd、tmux，并激活匹配项目的 IsaacLab Python 环境。参考 scriptsFORhuman/pull_v28/evidence/pull_v28_rebuild_2048_20260914/MIGRATION_ENVIRONMENT_20260915.json 核对现有安装：记录中的 Python 3.11.15、IsaacLab 0.54.2、IsaacSim 5.1.0.0、torch 2.7.0+cu128 是源机器实测，不代表新机器已验证。检查 GPU 型号/可用显存/驱动与四卡资源，按现有环境信息定位真实差异，不新增仿真测试套件。
2. 把 migrate.py 与 manifest 放到目标 repo 外，执行默认 prepare。脚本 clone/pull 指定分支时跳过全仓 LFS 自动下载；恢复包包含 A2_Base policy 和 metadata、原 P_S2 resolved config、当前组 checkpoint/config/log、runtime evidence。不要全仓下载无关历史模型。
3. 配置 asset_root 的 robots 路径已核实。至少选择拉取 MERGED robot，并据恢复 config 拉取其它实际运行依赖：
   git -C /new/workspace/DoorDog lfs pull --include='gr00t/rl/data/robots/a2_piper_v28_merged_20260909/**' --exclude=''
   确认所引用的运行资产是实际文件而不是 LFS pointer；A2_Base 已由 core 提供，无需为它下载所有历史 policy。
4. 使用激活环境的 Python（pipeline 使用 sys.executable）：

```sh
python /path/to/migrate.py --repo /new/workspace/DoorDog --manifest /path/to/migration_manifest.json --archive-dir /path/to/downloads
```

默认只 prepare，不启动 GPU。它恢复相对 repo 路径，把旧 repo/SSD 前缀替换为新 repo 的活动 YAML 路径（包括供 eval 使用的 checkpoint 邻接配置），保留历史 runtime receipt 的原始信息。旧 eval_root 整目录归档为 _before_migration_attempt3；旧 runner 文件也保留。查看 .ai/runtime/migrations/pull_v28_2048_attempt3/prepare.json 中的四条命令和路径。不要把旧 PID/receipt 当作新机器进程。 恢复的 ACTIVE_RUN.json 是 m5 的 D019 暂停证据，prepare.json 是新机待执行命令清单。新机实际续训启动检查后，先归档源 ACTIVE_RUN，再将新主机、attempt3 实际 receipt、checkpoint lineage 和真实状态写入 ACTIVE_RUN；单有 submit 成功不等于已恢复训练。

准备完成后直接按已授权合同执行，无需等待 Owner 重复批准：

```sh
python /path/to/migrate.py --repo /new/workspace/DoorDog --manifest /path/to/migration_manifest.json --archive-dir /path/to/downloads --resume
```

由现有 pipeline 与 .ai/scripts/run_supervisor.py v1.4 创建新 receipt，并通过持久 tmux 提交三个 full resume 和 GPU0 queue。长任务不要绑定当前交互终端；遵循仓库 LONG_RUNNING_TASKS/runtime 流程。启动后只取一次实际 batch 进度和吞吐建立 ETA，再按实测 ETA 进入持久等待，不频繁轮询、不用源机速度声称新机 ETA。记录真实完成/partial/失败；工程配置或调度错误按既有自主修复授权处理，真实合同、物理门、预算或硬件异常如实报告，不能擅改环境数/PPO/阶段/阈值来使任务继续。

最终继续原 opening closure：使用现有 reducer/readout 与原 plan，区分运行状态、自然评估有效性、camera/bundle 观察和 opening 结果；缺失事件保持 null/NOT_OBSERVED。三原 seed 的完整 6000 endpoint 齐备后才报告 k/3，历史单列；不得把 MISSING、未运行或单格结果写成 0/3 或三 seed 终点。新机器准备成功不等于训练/物理/科学门已通过。
