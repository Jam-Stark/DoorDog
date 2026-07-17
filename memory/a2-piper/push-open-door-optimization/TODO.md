# TODO

- 2026-07-17 15:39 HKT - A/B formal training与endpoint eval已完成，A 2-env×3-camera render/抽帧目视也已完成；两env持续带把手开门、无明显detach或拍门飞走，但均以别扭姿态停在门口并stage4 overtime。下一步做bounded `v13.1` diagnosis：解释A的12/16 stage4与4/16 stage5为何均未goal，核对stage4→5 predicate、`dont_push_door_handle`、`target_root_distance`、base/doorframe event与终点姿态；同时定位j8 open-limit `14.151%`与stage3 handle hard-limit `27.416%`。M7/M8/v13_C/v13_D仍保持conditional。
