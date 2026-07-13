# Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0


from gr00t.rl.data.tasks.door.scenario_cfg.factory import (
    build_door_spawner_cfg,
    build_task_obj_cfg_dict,
)


door_spawner_cfg = build_door_spawner_cfg(["in"])
TaskObjCfgDict = build_task_obj_cfg_dict(["in"])
multi_spawner_cfg = TaskObjCfgDict["door"].spawn
