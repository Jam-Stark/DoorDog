# C-B2H Camera 方案备份

这是当前已验证的 `C-B2H-DUALRAW-SHAREDENC-TOEOUT6-V19-P2` camera setup 快照，用于在测试其他方案后快速恢复。

![C-B2H 效果图](./C-B2H效果图.png)

## 核心配置

| Camera | trunk-frame position (m) | RPY (deg) | 作用 |
| --- | --- | --- | --- |
| Left D435i | `[0.215, +0.065, 0.165]` | `[0, -50, +6]` | 左侧 manipulation view，朝 `+Y` toe-out |
| Right D435i | `[0.215, -0.065, 0.165]` | `[0, -50, -6]` | 右侧 manipulation view，朝 `-Y` toe-out |
| A2 OEM Head | `[0.3381, 0.0336, 0.0525]` | `[0, 0, 0]` | 独立 level forward context |

- D435i baseline：`130 mm`，即 `y = ±65 mm`。
- D435i pitch：`-50°`。
- D435i toe-out：左右各 `6°`，不是向中心 toe-in。
- 左右 D435i：各 `384 × 216`，按 `[left RGB, right RGB]` channel-stack 为 `[384, 216, 6]`。
- D435i pair：一次 packed shared-encoder forward。
- OEM Head：`136 × 384`，使用独立 context encoder。
- 不做 panorama；feature-level fusion 保留三路分工。
- `camera_meta` 顺序：`left_age, right_age, head_age, left_valid, right_valid, head_valid`。

## 目录内容

- `camera_config.yaml`：可直接覆盖/合并到 experiment 的 `simulator.config.cameras`。
- `observation_contract.yaml`：三路输入 observation snapshot。
- `restore_camera_setup.py`：一条命令恢复 camera subtree 与 observation config。
- `C-B2H效果图.png`：上传 SVG 的 `1210 × 718` PNG 渲染版。

## 快速恢复

恢复当前正式 C-B2H experiment：

```bash
/home/baoquanc/anaconda3/envs/isaaclab/bin/python \
  camera_setup/C-B2H/restore_camera_setup.py
```

恢复到另一份 experiment config：

```bash
/home/baoquanc/anaconda3/envs/isaaclab/bin/python \
  camera_setup/C-B2H/restore_camera_setup.py \
  --target-exp gr00t/rl/config/exp/wbmanip/<target>.yaml
```

恢复脚本只替换目标文件的 `simulator.config.cameras`，并把本目录的 observation snapshot 恢复到：

```text
gr00t/rl/config/obs/wbmanip/door_open_a2_base_dagger_triview.yaml
```

它不会恢复 Teacher、checkpoint、GPU topology、训练步数或日志路径。目标 experiment 仍需使用：

```yaml
defaults:
  - /obs: wbmanip/door_open_a2_base_dagger_triview

algo:
  config:
    actor:
      _target_: gr00t.rl.trl.modules.vision_actor_critic_modules_p2_recurrent.DualD435HeadVisionRecurrentToeOut6Actor
      view_contract:
        camera_meta_dim: 6
        d435i_forward_mode: packed
```

## 当前生效来源

- Camera geometry / Student experiment：`gr00t/rl/config/exp/wbmanip/door_open_a2_base_v19_p2_b2h_toeout6_mgpu.yaml`
- GRPO config：`gr00t/rl/config/exp/wbmanip/door_open_a2_base_v19_b2h_toeout6_grpo.yaml`，继承上面的 camera contract。
- Observation：`gr00t/rl/config/obs/wbmanip/door_open_a2_base_dagger_triview.yaml`
- Sensor consumer：`gr00t/rl/simulator/isaacsim/isaacsim.py`
- Student actor：`gr00t/rl/trl/modules/vision_actor_critic_modules_p2_recurrent.py`

后续新方案应使用新的 architecture/config 名称，不要覆盖本目录中的 C-B2H snapshot。
