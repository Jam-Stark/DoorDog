---
name: assets-and-data
scope: local model artifacts, motion/data references, and door asset generation
status: active
last_updated: 2026-06-11 22:40 HKT
owned_paths:
  - memory/origin-reference/assets-and-data/description.md
  - memory/origin-reference/assets-and-data/TODO.md
  - memory/origin-reference/assets-and-data/DONE.md
read_when:
  - 运行 door workflow 前需要确认 required models/data/assets
  - 遇到 missing model, LAFAN-G1 path, generated door asset, or object/robot asset issue 时
---

## Purpose

记录 origin reference 级别的 assets/data 状态与路径索引。这里不记录 future migration、dataset migration progress 或 experiment outputs。

Assets/data facts:

- Required HOMIE model artifacts verified loadable: `models/model_walk.pt`, `models/model_stand.pt` both exist, size `9785586`, are not Git LFS pointer files, and `torch.load` keys include `model_state_dict`。
- Other ONNX/PT artifacts are indexed only;不要把它们视为 verified workflow prerequisites unless source/config explicitly points to them。
- Current local indexed model artifacts include `models/model_model.pt`, `models/dec_loco_model.onnx`, `models/dec_loco_stand_waist_height_4150.onnx`, `models/decoupled_locomotion_stand_multi_amass_obsnoise_lr-20250601_173154_last.onnx`。
- Repo `.gitattributes` tracks `*.pt`, `*.onnx`, `*.npz`, USD/assets via Git LFS.
- Local Git LFS files are real binaries, not pointer files, for existing tracked models/checkpoints.
- LAFAN-G1 is external Hugging Face dataset `ember-lab-berkeley/LAFAN-G1`; it is not bundled in this repo, but local path `/home/baoquanc/projects/LAFAN-G1` is present/verified and matches current config `gr00t/rl/config/env/door_open_homie.yaml` expectation `${HOME}/projects/LAFAN-G1`。Top README may describe sibling `LAFAN-G1`; use current config path as source-of-truth for this workflow.
- Current `HEAD` and `origin/doorman` tree include no door/wbmanip `model_step_*.pt`; historical tracked checkpoints known from origin are `loco_manip/walk_stand_place_grasp_turn_homie`, not current DoorPregrasp eval checkpoints.
- Official/eval-quality DoorPregrasp checkpoint 仍未发现/官方未上传；smoke-only teacher PPO checkpoint now exists at `logs_rl/g1_open_door_homie/door_open_homie_lstm_smoke5-20260611_223318/model_step_000005.pt` and may be used for eval/runtime wiring smoke if desired, but do not claim policy quality.
- 2026-06-11 22:14 HKT 已从当前 working tree 清理 confirmed old `loco_manip/walk_stand_place_grasp_turn_homie` teacher/student checkpoint directories: `logs_rl/bfv7.t.2.a1.qben-teacher`, `logs_rl/walk_stand_place_grasp_turn_homie_predrop_project_name-wsdpt_teacher_BTFv8q9_qben_exppredrop_leanz_hand_predrop_pos_distance-10.0_penalty_bottle_lean_during_pick--3500.0_penalty_bottle_non_z_up_velocity_during_pick--1000.0-20251105_004910`, `logs_rl/wsdpt_student_for_teacher_bfv7.t.2.a1.qben_resnet_resume_rgb_delay_test_project_name-wsdpt_student_rgb_delay_rgb_image_delay_step-3_rgb_image_delay_random-False-20251103_011035`。
- 这些 cleaned old checkpoints 仍是 origin commit/branch 的 LFS tracked historical artifacts；以后如需调查 old `loco_manip` baseline 可从 git/LFS 恢复，但不要把它们当作 current DoorPregrasp evaluate/play checkpoint。
- `logs_rl/g1_open_door_homie/` 保留为 current door task 相关 recent attempt and smoke output；不要与 old `walk_stand_place_grasp_turn_homie` artifacts 混淆。
- Therefore `git lfs pull` for this repo cannot restore a missing official/eval-quality door checkpoint unless a different branch/commit/release adds it.
- Door asset generation scripts exist under `gr00t/rl/scripts/` and should be treated as source index, not executed from memory.
- 2026-06-11 22:40 HKT verified door asset generation/load fact: preview generated files exist at `data/door_assets_preview/door_0000.usd` size `10216` bytes and `data/door_assets_preview/metadata.json` size `868` bytes; user confirmed the door asset loads normally via Isaac Sim/WebRTC preview.

## When Codex/AI Should Read This Entry

- 需要确认 `model_walk.pt` / `model_stand.pt` 是否应该存在。
- 需要解释 LAFAN-G1 path conflict 或 missing dataset error。
- 需要找到 door asset generation scripts、robot/object assets、motion samples。

## Source Paths

- Git LFS tracking: `.gitattributes`
- HOMIE models: `models/model_walk.pt`, `models/model_stand.pt`
- indexed extra models: `models/model_model.pt`, `models/dec_loco_model.onnx`, `models/dec_loco_stand_waist_height_4150.onnx`, `models/decoupled_locomotion_stand_multi_amass_obsnoise_lr-20250601_173154_last.onnx`
- logs checkpoint examples: `logs_rl/`
- motion data examples: `gr00t/rl/data/motions/g1_wsg/`
- object assets: `gr00t/rl/data/objects/grab/`
- robot assets: `gr00t/rl/data/robots/g1/`
- door asset scripts: `gr00t/rl/scripts/generate_door_assets.py`, `gr00t/rl/scripts/generate_1000_doors.sh`, `gr00t/rl/scripts/README.md`
- LAFAN external dataset: `ember-lab-berkeley/LAFAN-G1`
- LAFAN/source path markers: `README.md`, `gr00t/rl/config/env/door_open_homie.yaml`, `gr00t/rl/envs/door/reset_from_dataset.py`

## TODO Summary

- 2026-06-11 22:40 HKT - 当 LAFAN-G1 path expectation / verified location、HOMIE model artifact inventory/loadability、Git LFS tracking、asset generation scripts、door preview asset generation/load status 或 current checkpoint inventory 改变时，更新本 entry；尤其是新增 DoorPregrasp evaluate/play checkpoint、官方 checkpoint/release 上传，或恢复 historical `loco_manip` artifacts。

## DONE Summary

- 2026-06-11 21:53 HKT - 初始化 assets/data origin reference entry，记录 HOMIE models present、other model artifacts indexed、LAFAN-G1 missing/conflict、door asset scripts。
- 2026-06-11 22:06 HKT - 记录 Git LFS/dataset/checkpoint availability facts：`.gitattributes` LFS tracking、local LFS real binaries、external LAFAN-G1、以及当前 `HEAD` / `origin/doorman` 无 door/wbmanip `model_step_*.pt`。
- 2026-06-11 22:14 HKT - 清理当前 working tree 中 confirmed old `loco_manip/walk_stand_place_grasp_turn_homie` teacher/student checkpoint directories，并记录它们仍是 git/LFS historical artifacts，不可作为 current DoorPregrasp evaluate/play checkpoint。
- 2026-06-11 22:27 HKT - 更新 asset verification facts：LAFAN-G1 已在 `/home/baoquanc/projects/LAFAN-G1` verified present 且匹配 current config，HOMIE `model_walk.pt` / `model_stand.pt` verified loadable，DoorPregrasp eval checkpoint 仍 absent，下一步是 run teacher PPO smoke train 生成 checkpoint。
- 2026-06-11 22:40 HKT - 记录 smoke-only DoorPregrasp checkpoint inventory update 与 door preview asset generated files exist：`data/door_assets_preview/door_0000.usd` size `10216` bytes、`data/door_assets_preview/metadata.json` size `868` bytes；user confirmed door asset loads normally via Isaac Sim/WebRTC preview。

## Recommended Next Files To Read

- `memory/origin-reference/door-workflows/description.md`
- `memory/origin-reference/documentation-truth-map/description.md`
- `README.md`
- `gr00t/rl/config/env/door_open_homie.yaml`
