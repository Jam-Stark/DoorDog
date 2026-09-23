# W3 layout coverage (COMPUTED; pinhole + Min-Z + arm-capsule screen; no mesh / door-panel occlusion)

## reconstruction check vs planner_evidence_20260909/camera/variants/U3_F45_B15.json
- base_left_B15/rgb: |dp| = 0.000 mm, drot = 0.0000 deg
- base_left_B15/depth: |dp| = 0.000 mm, drot = 0.0000 deg
- base_right_B15/rgb: |dp| = 0.000 mm, drot = 0.0000 deg
- base_right_B15/depth: |dp| = 0.000 mm, drot = 0.0000 deg
- wrist_F45_180/rgb: |dp| = 0.000 mm, drot = 0.0000 deg
- wrist_F45_180/depth: |dp| = 0.000 mm, drot = 0.0000 deg

Shares are per-pose UNIONs over the cameras of a layout (a pose counts if at least one camera of that layout has the point inside its frustum beyond Min-Z and, for trunk-mounted cameras looking at handle/TCP/fingers, not behind an arm capsule).

## (b) trajectory-independent canonical postures (task geometry only)
### approach_left @ 0.8 (n=9)
| set | handle R | handle D | frame_handle_side_z1.0 R | frame_handle_side_z1.0 D | frame_hinge_side_z1.0 R | frame_hinge_side_z1.0 D | doorway_floor_centre R | doorway_floor_centre D | panel_free_edge_z1.0 R | panel_free_edge_z1.0 D |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| V0_dual_B15_W45_180 | 100 | 100 | 100 | 100 | 44 | 56 | 0 | 0 | 100 | 100 |
| V1a_centre_B15_W45_180 | 100 | 100 | 89 | 100 | 33 | 44 | 0 | 0 | 89 | 100 |
| V1b_centre_B0_W45_180 | 100 | 100 | 89 | 100 | 22 | 44 | 0 | 0 | 89 | 100 |
| V2_head_d435i_B0_W45_180 | 89 | 100 | 89 | 89 | 22 | 33 | 0 | 0 | 89 | 100 |
| V2b_head_d435i_B15_W45_180 | 89 | 100 | 89 | 89 | 22 | 33 | 0 | 0 | 89 | 100 |
| V2c_head_studentRGB_W45_180 | 89 | 100 | 89 | 89 | 33 | 33 | 0 | 0 | 89 | 100 |
| V3_wrist_only_W45_180 | 89 | 100 | 89 | 89 | 22 | 33 | 0 | 0 | 89 | 100 |
| V4a_centre_B15_W39_140 | 100 | 100 | 89 | 100 | 33 | 44 | 0 | 0 | 89 | 100 |
| V4b_centre_B15_W345_120 | 100 | 100 | 89 | 100 | 33 | 44 | 0 | 0 | 89 | 100 |

### approach_left @ 1.0 (n=9)
| set | handle R | handle D | frame_handle_side_z1.0 R | frame_handle_side_z1.0 D | frame_hinge_side_z1.0 R | frame_hinge_side_z1.0 D | doorway_floor_centre R | doorway_floor_centre D | panel_free_edge_z1.0 R | panel_free_edge_z1.0 D |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| V0_dual_B15_W45_180 | 100 | 100 | 100 | 100 | 56 | 67 | 0 | 0 | 100 | 100 |
| V1a_centre_B15_W45_180 | 100 | 100 | 100 | 100 | 44 | 67 | 0 | 0 | 100 | 100 |
| V1b_centre_B0_W45_180 | 100 | 100 | 89 | 100 | 33 | 56 | 0 | 0 | 100 | 100 |
| V2_head_d435i_B0_W45_180 | 100 | 100 | 89 | 100 | 33 | 56 | 0 | 0 | 89 | 100 |
| V2b_head_d435i_B15_W45_180 | 100 | 100 | 89 | 100 | 33 | 56 | 0 | 0 | 89 | 100 |
| V2c_head_studentRGB_W45_180 | 100 | 100 | 89 | 100 | 67 | 56 | 22 | 0 | 89 | 100 |
| V3_wrist_only_W45_180 | 100 | 100 | 89 | 100 | 33 | 56 | 0 | 0 | 89 | 100 |
| V4a_centre_B15_W39_140 | 100 | 100 | 100 | 100 | 44 | 67 | 0 | 0 | 100 | 100 |
| V4b_centre_B15_W345_120 | 100 | 100 | 100 | 100 | 44 | 67 | 0 | 0 | 100 | 100 |

### approach_left @ 1.2 (n=9)
| set | handle R | handle D | frame_handle_side_z1.0 R | frame_handle_side_z1.0 D | frame_hinge_side_z1.0 R | frame_hinge_side_z1.0 D | doorway_floor_centre R | doorway_floor_centre D | panel_free_edge_z1.0 R | panel_free_edge_z1.0 D |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| V0_dual_B15_W45_180 | 100 | 100 | 100 | 100 | 56 | 78 | 0 | 22 | 100 | 100 |
| V1a_centre_B15_W45_180 | 100 | 100 | 100 | 100 | 44 | 67 | 0 | 22 | 100 | 100 |
| V1b_centre_B0_W45_180 | 100 | 100 | 100 | 100 | 44 | 67 | 0 | 22 | 100 | 100 |
| V2_head_d435i_B0_W45_180 | 100 | 100 | 89 | 100 | 44 | 67 | 0 | 22 | 100 | 100 |
| V2b_head_d435i_B15_W45_180 | 100 | 100 | 89 | 100 | 44 | 67 | 0 | 22 | 100 | 100 |
| V2c_head_studentRGB_W45_180 | 100 | 100 | 100 | 100 | 78 | 67 | 100 | 22 | 100 | 100 |
| V3_wrist_only_W45_180 | 100 | 100 | 89 | 100 | 44 | 67 | 0 | 22 | 100 | 100 |
| V4a_centre_B15_W39_140 | 100 | 100 | 100 | 100 | 44 | 67 | 0 | 0 | 100 | 100 |
| V4b_centre_B15_W345_120 | 100 | 100 | 100 | 100 | 44 | 67 | 0 | 0 | 100 | 100 |

### approach_left @ 1.5 (n=9)
| set | handle R | handle D | frame_handle_side_z1.0 R | frame_handle_side_z1.0 D | frame_hinge_side_z1.0 R | frame_hinge_side_z1.0 D | doorway_floor_centre R | doorway_floor_centre D | panel_free_edge_z1.0 R | panel_free_edge_z1.0 D |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| V0_dual_B15_W45_180 | 100 | 100 | 100 | 100 | 67 | 89 | 11 | 100 | 100 | 100 |
| V1a_centre_B15_W45_180 | 100 | 100 | 100 | 100 | 67 | 78 | 11 | 100 | 100 | 100 |
| V1b_centre_B0_W45_180 | 100 | 100 | 100 | 100 | 67 | 78 | 11 | 100 | 100 | 100 |
| V2_head_d435i_B0_W45_180 | 100 | 100 | 100 | 100 | 56 | 78 | 11 | 100 | 100 | 100 |
| V2b_head_d435i_B15_W45_180 | 100 | 100 | 100 | 100 | 56 | 78 | 11 | 100 | 100 | 100 |
| V2c_head_studentRGB_W45_180 | 100 | 100 | 100 | 100 | 100 | 78 | 100 | 100 | 100 | 100 |
| V3_wrist_only_W45_180 | 100 | 100 | 100 | 100 | 56 | 78 | 11 | 100 | 100 | 100 |
| V4a_centre_B15_W39_140 | 100 | 100 | 100 | 100 | 67 | 78 | 0 | 67 | 100 | 100 |
| V4b_centre_B15_W345_120 | 100 | 100 | 100 | 100 | 67 | 78 | 0 | 0 | 100 | 100 |

### approach_right @ 0.8 (n=9)
| set | handle R | handle D | frame_handle_side_z1.0 R | frame_handle_side_z1.0 D | frame_hinge_side_z1.0 R | frame_hinge_side_z1.0 D | doorway_floor_centre R | doorway_floor_centre D | panel_free_edge_z1.0 R | panel_free_edge_z1.0 D |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| V0_dual_B15_W45_180 | 100 | 100 | 100 | 100 | 44 | 67 | 0 | 0 | 100 | 100 |
| V1a_centre_B15_W45_180 | 100 | 100 | 89 | 100 | 33 | 56 | 0 | 0 | 89 | 100 |
| V1b_centre_B0_W45_180 | 100 | 100 | 78 | 100 | 33 | 44 | 0 | 0 | 78 | 100 |
| V2_head_d435i_B0_W45_180 | 89 | 100 | 78 | 89 | 33 | 44 | 0 | 0 | 78 | 100 |
| V2b_head_d435i_B15_W45_180 | 89 | 100 | 78 | 89 | 33 | 44 | 0 | 0 | 78 | 100 |
| V2c_head_studentRGB_W45_180 | 89 | 100 | 78 | 89 | 33 | 44 | 0 | 0 | 78 | 100 |
| V3_wrist_only_W45_180 | 89 | 100 | 78 | 89 | 33 | 44 | 0 | 0 | 78 | 100 |
| V4a_centre_B15_W39_140 | 100 | 100 | 89 | 100 | 33 | 56 | 0 | 0 | 89 | 100 |
| V4b_centre_B15_W345_120 | 100 | 100 | 89 | 100 | 33 | 56 | 0 | 0 | 89 | 100 |

### approach_right @ 1.0 (n=9)
| set | handle R | handle D | frame_handle_side_z1.0 R | frame_handle_side_z1.0 D | frame_hinge_side_z1.0 R | frame_hinge_side_z1.0 D | doorway_floor_centre R | doorway_floor_centre D | panel_free_edge_z1.0 R | panel_free_edge_z1.0 D |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| V0_dual_B15_W45_180 | 100 | 100 | 100 | 100 | 56 | 78 | 0 | 0 | 100 | 100 |
| V1a_centre_B15_W45_180 | 100 | 100 | 89 | 100 | 44 | 67 | 0 | 0 | 89 | 100 |
| V1b_centre_B0_W45_180 | 100 | 100 | 89 | 100 | 44 | 67 | 0 | 0 | 89 | 100 |
| V2_head_d435i_B0_W45_180 | 100 | 100 | 89 | 100 | 33 | 56 | 0 | 0 | 89 | 100 |
| V2b_head_d435i_B15_W45_180 | 100 | 100 | 89 | 100 | 33 | 56 | 0 | 0 | 89 | 100 |
| V2c_head_studentRGB_W45_180 | 100 | 100 | 89 | 100 | 67 | 56 | 22 | 0 | 89 | 100 |
| V3_wrist_only_W45_180 | 100 | 100 | 89 | 100 | 33 | 56 | 0 | 0 | 89 | 100 |
| V4a_centre_B15_W39_140 | 100 | 100 | 89 | 100 | 44 | 67 | 0 | 0 | 89 | 100 |
| V4b_centre_B15_W345_120 | 100 | 100 | 89 | 100 | 44 | 67 | 0 | 0 | 89 | 100 |

### approach_right @ 1.2 (n=9)
| set | handle R | handle D | frame_handle_side_z1.0 R | frame_handle_side_z1.0 D | frame_hinge_side_z1.0 R | frame_hinge_side_z1.0 D | doorway_floor_centre R | doorway_floor_centre D | panel_free_edge_z1.0 R | panel_free_edge_z1.0 D |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| V0_dual_B15_W45_180 | 100 | 100 | 100 | 100 | 67 | 78 | 0 | 22 | 100 | 100 |
| V1a_centre_B15_W45_180 | 100 | 100 | 89 | 100 | 56 | 67 | 0 | 22 | 100 | 100 |
| V1b_centre_B0_W45_180 | 100 | 100 | 89 | 100 | 56 | 67 | 0 | 22 | 100 | 100 |
| V2_head_d435i_B0_W45_180 | 100 | 100 | 89 | 100 | 44 | 67 | 0 | 22 | 89 | 100 |
| V2b_head_d435i_B15_W45_180 | 100 | 100 | 89 | 100 | 44 | 67 | 0 | 22 | 89 | 100 |
| V2c_head_studentRGB_W45_180 | 100 | 100 | 100 | 100 | 78 | 67 | 100 | 22 | 100 | 100 |
| V3_wrist_only_W45_180 | 100 | 100 | 89 | 100 | 44 | 67 | 0 | 22 | 89 | 100 |
| V4a_centre_B15_W39_140 | 100 | 100 | 89 | 100 | 56 | 67 | 0 | 0 | 100 | 100 |
| V4b_centre_B15_W345_120 | 100 | 100 | 89 | 100 | 56 | 67 | 0 | 0 | 100 | 100 |

### approach_right @ 1.5 (n=9)
| set | handle R | handle D | frame_handle_side_z1.0 R | frame_handle_side_z1.0 D | frame_hinge_side_z1.0 R | frame_hinge_side_z1.0 D | doorway_floor_centre R | doorway_floor_centre D | panel_free_edge_z1.0 R | panel_free_edge_z1.0 D |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| V0_dual_B15_W45_180 | 100 | 100 | 100 | 100 | 78 | 89 | 11 | 100 | 100 | 100 |
| V1a_centre_B15_W45_180 | 100 | 100 | 100 | 100 | 67 | 78 | 11 | 100 | 100 | 100 |
| V1b_centre_B0_W45_180 | 100 | 100 | 100 | 100 | 67 | 78 | 11 | 100 | 100 | 100 |
| V2_head_d435i_B0_W45_180 | 100 | 100 | 100 | 100 | 67 | 78 | 11 | 100 | 100 | 100 |
| V2b_head_d435i_B15_W45_180 | 100 | 100 | 100 | 100 | 67 | 78 | 11 | 100 | 100 | 100 |
| V2c_head_studentRGB_W45_180 | 100 | 100 | 100 | 100 | 100 | 78 | 100 | 100 | 100 | 100 |
| V3_wrist_only_W45_180 | 100 | 100 | 100 | 100 | 67 | 78 | 11 | 100 | 100 | 100 |
| V4a_centre_B15_W39_140 | 100 | 100 | 100 | 100 | 67 | 78 | 0 | 67 | 100 | 100 |
| V4b_centre_B15_W345_120 | 100 | 100 | 100 | 100 | 67 | 78 | 0 | 0 | 100 | 100 |

### passage_left @ 1.0472 (n=9)
| set | handle R | handle D | frame_handle_side_z1.0 R | frame_handle_side_z1.0 D | frame_hinge_side_z1.0 R | frame_hinge_side_z1.0 D | doorway_floor_centre R | doorway_floor_centre D | panel_free_edge_z1.0 R | panel_free_edge_z1.0 D |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| V0_dual_B15_W45_180 | 67 | 67 | 11 | 22 | 11 | 22 | 0 | 0 | 100 | 100 |
| V1a_centre_B15_W45_180 | 67 | 67 | 11 | 11 | 11 | 11 | 0 | 0 | 100 | 100 |
| V1b_centre_B0_W45_180 | 67 | 67 | 11 | 11 | 0 | 11 | 0 | 0 | 100 | 100 |
| V2_head_d435i_B0_W45_180 | 67 | 67 | 11 | 11 | 0 | 11 | 0 | 0 | 100 | 100 |
| V2b_head_d435i_B15_W45_180 | 67 | 67 | 11 | 11 | 0 | 11 | 0 | 0 | 100 | 100 |
| V2c_head_studentRGB_W45_180 | 67 | 67 | 11 | 11 | 0 | 11 | 0 | 0 | 100 | 100 |
| V3_wrist_only_W45_180 | 67 | 67 | 11 | 11 | 0 | 11 | 0 | 0 | 100 | 100 |
| V4a_centre_B15_W39_140 | 67 | 67 | 11 | 11 | 11 | 11 | 0 | 0 | 100 | 100 |
| V4b_centre_B15_W345_120 | 67 | 67 | 11 | 11 | 11 | 11 | 0 | 0 | 100 | 100 |

### passage_left @ 1.5708 (n=9)
| set | handle R | handle D | frame_handle_side_z1.0 R | frame_handle_side_z1.0 D | frame_hinge_side_z1.0 R | frame_hinge_side_z1.0 D | doorway_floor_centre R | doorway_floor_centre D | panel_free_edge_z1.0 R | panel_free_edge_z1.0 D |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| V0_dual_B15_W45_180 | 78 | 89 | 11 | 22 | 11 | 22 | 0 | 0 | 67 | 89 |
| V1a_centre_B15_W45_180 | 56 | 78 | 11 | 11 | 11 | 11 | 0 | 0 | 56 | 78 |
| V1b_centre_B0_W45_180 | 56 | 67 | 11 | 11 | 0 | 11 | 0 | 0 | 56 | 67 |
| V2_head_d435i_B0_W45_180 | 56 | 67 | 11 | 11 | 0 | 11 | 0 | 0 | 56 | 67 |
| V2b_head_d435i_B15_W45_180 | 56 | 67 | 11 | 11 | 0 | 11 | 0 | 0 | 56 | 67 |
| V2c_head_studentRGB_W45_180 | 67 | 67 | 11 | 11 | 0 | 11 | 0 | 0 | 67 | 67 |
| V3_wrist_only_W45_180 | 56 | 67 | 11 | 11 | 0 | 11 | 0 | 0 | 56 | 67 |
| V4a_centre_B15_W39_140 | 56 | 78 | 11 | 11 | 11 | 11 | 0 | 0 | 56 | 78 |
| V4b_centre_B15_W345_120 | 56 | 78 | 11 | 11 | 11 | 11 | 0 | 0 | 56 | 78 |

### grasp_left @ hinge 0.0 (n=1200) — per CAMERA
| set | handle R | handle D | frame_handle_side_z1.0 R | frame_handle_side_z1.0 D | panel_free_edge_z1.0 R | panel_free_edge_z1.0 D |
|---|---:|---:|---:|---:|---:|---:|
| base_left_B15 | 36 | 65 | 34 | 84 | 40 | 93 |
| base_right_B15 | 36 | 57 | 26 | 69 | 37 | 83 |
| base_centre_B15 | 15 | 23 | 32 | 83 | 40 | 93 |
| base_centre_B0 | 1 | 7 | 0 | 7 | 0 | 10 |
| head_d435i_B0 | 0 | 0 | 0 | 0 | 0 | 0 |
| head_d435i_B15 | 0 | 0 | 0 | 0 | 0 | 0 |
| head_student_rgb | 0 | - | 0 | - | 0 | - |
| wrist_F45_180 | 100 | 100 | 7 | 16 | 10 | 22 |
| wrist_F39_140 | 100 | 100 | 6 | 13 | 8 | 17 |
| wrist_F345_120 | 100 | 100 | 6 | 12 | 7 | 16 |

### grasp_left @ hinge 0.5 (n=1200) — per CAMERA
| set | handle R | handle D | frame_handle_side_z1.0 R | frame_handle_side_z1.0 D | panel_free_edge_z1.0 R | panel_free_edge_z1.0 D |
|---|---:|---:|---:|---:|---:|---:|
| base_left_B15 | 36 | 65 | 0 | 0 | 79 | 100 |
| base_right_B15 | 36 | 57 | 0 | 0 | 83 | 99 |
| base_centre_B15 | 15 | 23 | 0 | 0 | 79 | 100 |
| base_centre_B0 | 1 | 7 | 0 | 0 | 0 | 18 |
| head_d435i_B0 | 0 | 0 | 0 | 0 | 0 | 0 |
| head_d435i_B15 | 0 | 0 | 0 | 0 | 0 | 0 |
| head_student_rgb | 0 | - | 0 | - | 0 | - |
| wrist_F45_180 | 100 | 100 | 0 | 0 | 14 | 31 |
| wrist_F39_140 | 100 | 100 | 0 | 0 | 12 | 25 |
| wrist_F345_120 | 100 | 100 | 0 | 0 | 12 | 24 |

### grasp_right @ hinge 0.0 (n=1200) — per CAMERA
| set | handle R | handle D | frame_handle_side_z1.0 R | frame_handle_side_z1.0 D | panel_free_edge_z1.0 R | panel_free_edge_z1.0 D |
|---|---:|---:|---:|---:|---:|---:|
| base_left_B15 | 36 | 65 | 19 | 64 | 26 | 80 |
| base_right_B15 | 36 | 57 | 39 | 80 | 48 | 90 |
| base_centre_B15 | 15 | 23 | 30 | 82 | 38 | 93 |
| base_centre_B0 | 1 | 7 | 0 | 7 | 0 | 10 |
| head_d435i_B0 | 0 | 0 | 0 | 0 | 0 | 0 |
| head_d435i_B15 | 0 | 0 | 0 | 0 | 0 | 0 |
| head_student_rgb | 0 | - | 0 | - | 0 | - |
| wrist_F45_180 | 100 | 100 | 6 | 23 | 8 | 26 |
| wrist_F39_140 | 100 | 100 | 4 | 19 | 5 | 22 |
| wrist_F345_120 | 100 | 100 | 5 | 18 | 6 | 20 |

### grasp_right @ hinge 0.5 (n=1200) — per CAMERA
| set | handle R | handle D | frame_handle_side_z1.0 R | frame_handle_side_z1.0 D | panel_free_edge_z1.0 R | panel_free_edge_z1.0 D |
|---|---:|---:|---:|---:|---:|---:|
| base_left_B15 | 36 | 65 | 0 | 0 | 66 | 99 |
| base_right_B15 | 36 | 57 | 0 | 0 | 89 | 100 |
| base_centre_B15 | 15 | 23 | 0 | 0 | 79 | 100 |
| base_centre_B0 | 1 | 7 | 0 | 0 | 0 | 18 |
| head_d435i_B0 | 0 | 0 | 0 | 0 | 0 | 0 |
| head_d435i_B15 | 0 | 0 | 0 | 0 | 0 | 0 |
| head_student_rgb | 0 | - | 0 | - | 0 | - |
| wrist_F45_180 | 100 | 100 | 0 | 1 | 9 | 32 |
| wrist_F39_140 | 100 | 100 | 0 | 0 | 8 | 25 |
| wrist_F345_120 | 100 | 100 | 0 | 0 | 8 | 25 |

grasp postures kept from IK-free sampling: 400

## (a) replay of archived v27 trajectories (CONDITIONAL on how the OLD Teacher moved)
### C_S2/left stage2 (n=1644)
| set | handle R | handle D | frame_handle_side_z1.0 R | frame_handle_side_z1.0 D | frame_hinge_side_z1.0 R | frame_hinge_side_z1.0 D | doorway_floor_centre R | doorway_floor_centre D | panel_free_edge_z1.0 R | panel_free_edge_z1.0 D |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| V0_dual_B15_W45_180 | 99 | 100 | 100 | 100 | 1 | 15 | 21 | 54 | 100 | 100 |
| V1a_centre_B15_W45_180 | 99 | 100 | 100 | 100 | 0 | 2 | 21 | 54 | 100 | 100 |
| V1b_centre_B0_W45_180 | 99 | 100 | 14 | 100 | 0 | 1 | 21 | 54 | 30 | 100 |
| V2_head_d435i_B0_W45_180 | 99 | 100 | 13 | 42 | 0 | 0 | 21 | 54 | 27 | 53 |
| V2b_head_d435i_B15_W45_180 | 99 | 100 | 13 | 56 | 0 | 0 | 21 | 54 | 27 | 68 |
| V2c_head_studentRGB_W45_180 | 99 | 100 | 13 | 42 | 1 | 0 | 21 | 54 | 27 | 53 |
| V3_wrist_only_W45_180 | 99 | 100 | 13 | 42 | 0 | 0 | 21 | 54 | 27 | 53 |
| V4a_centre_B15_W39_140 | 99 | 100 | 100 | 100 | 0 | 2 | 4 | 30 | 100 | 100 |
| V4b_centre_B15_W345_120 | 99 | 100 | 100 | 100 | 0 | 2 | 0 | 15 | 100 | 100 |

### C_S2/left stage3 (n=8066)
| set | handle R | handle D | frame_handle_side_z1.0 R | frame_handle_side_z1.0 D | frame_hinge_side_z1.0 R | frame_hinge_side_z1.0 D | doorway_floor_centre R | doorway_floor_centre D | panel_free_edge_z1.0 R | panel_free_edge_z1.0 D |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| V0_dual_B15_W45_180 | 52 | 100 | 73 | 99 | 3 | 43 | 0 | 9 | 100 | 100 |
| V1a_centre_B15_W45_180 | 47 | 100 | 66 | 99 | 1 | 9 | 0 | 9 | 100 | 100 |
| V1b_centre_B0_W45_180 | 47 | 100 | 13 | 39 | 0 | 5 | 0 | 9 | 47 | 78 |
| V2_head_d435i_B0_W45_180 | 47 | 100 | 13 | 32 | 0 | 0 | 0 | 9 | 47 | 70 |
| V2b_head_d435i_B15_W45_180 | 47 | 100 | 13 | 33 | 0 | 1 | 0 | 9 | 47 | 71 |
| V2c_head_studentRGB_W45_180 | 47 | 100 | 13 | 32 | 2 | 0 | 14 | 9 | 47 | 70 |
| V3_wrist_only_W45_180 | 47 | 100 | 13 | 32 | 0 | 0 | 0 | 9 | 47 | 70 |
| V4a_centre_B15_W39_140 | 40 | 100 | 66 | 99 | 1 | 9 | 0 | 2 | 100 | 100 |
| V4b_centre_B15_W345_120 | 36 | 100 | 66 | 99 | 1 | 9 | 0 | 1 | 100 | 100 |

### C_S2/left stage4 (n=11898)
| set | handle R | handle D | frame_handle_side_z1.0 R | frame_handle_side_z1.0 D | frame_hinge_side_z1.0 R | frame_hinge_side_z1.0 D | doorway_floor_centre R | doorway_floor_centre D | panel_free_edge_z1.0 R | panel_free_edge_z1.0 D |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| V0_dual_B15_W45_180 | 97 | 100 | 1 | 4 | 0 | 20 | 0 | 1 | 62 | 94 |
| V1a_centre_B15_W45_180 | 94 | 99 | 0 | 4 | 0 | 1 | 0 | 1 | 55 | 94 |
| V1b_centre_B0_W45_180 | 95 | 99 | 0 | 0 | 0 | 0 | 0 | 1 | 28 | 59 |
| V2_head_d435i_B0_W45_180 | 92 | 98 | 0 | 0 | 0 | 0 | 0 | 1 | 26 | 54 |
| V2b_head_d435i_B15_W45_180 | 93 | 98 | 0 | 0 | 0 | 0 | 0 | 1 | 27 | 56 |
| V2c_head_studentRGB_W45_180 | 96 | 95 | 0 | 0 | 0 | 0 | 0 | 1 | 30 | 51 |
| V3_wrist_only_W45_180 | 91 | 95 | 0 | 0 | 0 | 0 | 0 | 1 | 25 | 51 |
| V4a_centre_B15_W39_140 | 92 | 99 | 0 | 4 | 0 | 1 | 0 | 0 | 47 | 90 |
| V4b_centre_B15_W345_120 | 91 | 99 | 0 | 4 | 0 | 1 | 0 | 0 | 46 | 90 |

### C_S2/right stage2 (n=1653)
| set | handle R | handle D | frame_handle_side_z1.0 R | frame_handle_side_z1.0 D | frame_hinge_side_z1.0 R | frame_hinge_side_z1.0 D | doorway_floor_centre R | doorway_floor_centre D | panel_free_edge_z1.0 R | panel_free_edge_z1.0 D |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| V0_dual_B15_W45_180 | 100 | 100 | 100 | 100 | 94 | 100 | 0 | 18 | 100 | 100 |
| V1a_centre_B15_W45_180 | 100 | 100 | 100 | 100 | 67 | 98 | 0 | 18 | 100 | 100 |
| V1b_centre_B0_W45_180 | 100 | 100 | 78 | 100 | 17 | 91 | 0 | 18 | 84 | 100 |
| V2_head_d435i_B0_W45_180 | 100 | 100 | 14 | 44 | 0 | 0 | 0 | 18 | 17 | 42 |
| V2b_head_d435i_B15_W45_180 | 100 | 100 | 17 | 90 | 1 | 49 | 0 | 18 | 21 | 97 |
| V2c_head_studentRGB_W45_180 | 100 | 100 | 21 | 44 | 8 | 0 | 0 | 18 | 27 | 42 |
| V3_wrist_only_W45_180 | 100 | 100 | 14 | 44 | 0 | 0 | 0 | 18 | 17 | 42 |
| V4a_centre_B15_W39_140 | 100 | 100 | 100 | 100 | 67 | 98 | 0 | 2 | 100 | 100 |
| V4b_centre_B15_W345_120 | 100 | 100 | 100 | 100 | 67 | 98 | 0 | 0 | 100 | 100 |

### C_S2/right stage3 (n=7602)
| set | handle R | handle D | frame_handle_side_z1.0 R | frame_handle_side_z1.0 D | frame_hinge_side_z1.0 R | frame_hinge_side_z1.0 D | doorway_floor_centre R | doorway_floor_centre D | panel_free_edge_z1.0 R | panel_free_edge_z1.0 D |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| V0_dual_B15_W45_180 | 92 | 100 | 100 | 100 | 93 | 100 | 0 | 8 | 100 | 100 |
| V1a_centre_B15_W45_180 | 86 | 100 | 100 | 100 | 52 | 97 | 0 | 8 | 100 | 100 |
| V1b_centre_B0_W45_180 | 86 | 100 | 98 | 100 | 47 | 95 | 0 | 8 | 100 | 100 |
| V2_head_d435i_B0_W45_180 | 85 | 100 | 5 | 52 | 1 | 22 | 0 | 8 | 18 | 94 |
| V2b_head_d435i_B15_W45_180 | 99 | 100 | 61 | 91 | 3 | 45 | 0 | 8 | 95 | 100 |
| V2c_head_studentRGB_W45_180 | 100 | 100 | 80 | 38 | 81 | 0 | 0 | 8 | 98 | 62 |
| V3_wrist_only_W45_180 | 70 | 100 | 5 | 38 | 0 | 0 | 0 | 8 | 10 | 62 |
| V4a_centre_B15_W39_140 | 86 | 100 | 100 | 100 | 52 | 97 | 0 | 0 | 100 | 100 |
| V4b_centre_B15_W345_120 | 88 | 100 | 100 | 100 | 52 | 97 | 0 | 0 | 100 | 100 |

### C_S2/right stage4 (n=6532)
| set | handle R | handle D | frame_handle_side_z1.0 R | frame_handle_side_z1.0 D | frame_hinge_side_z1.0 R | frame_hinge_side_z1.0 D | doorway_floor_centre R | doorway_floor_centre D | panel_free_edge_z1.0 R | panel_free_edge_z1.0 D |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| V0_dual_B15_W45_180 | 92 | 100 | 26 | 42 | 16 | 21 | 0 | 18 | 55 | 63 |
| V1a_centre_B15_W45_180 | 90 | 100 | 5 | 23 | 5 | 14 | 0 | 18 | 48 | 58 |
| V1b_centre_B0_W45_180 | 90 | 100 | 3 | 14 | 5 | 12 | 0 | 18 | 47 | 55 |
| V2_head_d435i_B0_W45_180 | 75 | 100 | 0 | 0 | 0 | 1 | 0 | 18 | 13 | 40 |
| V2b_head_d435i_B15_W45_180 | 85 | 100 | 0 | 0 | 0 | 3 | 0 | 18 | 38 | 48 |
| V2c_head_studentRGB_W45_180 | 89 | 100 | 0 | 0 | 6 | 0 | 0 | 18 | 45 | 9 |
| V3_wrist_only_W45_180 | 72 | 100 | 0 | 0 | 0 | 0 | 0 | 18 | 1 | 9 |
| V4a_centre_B15_W39_140 | 88 | 100 | 5 | 23 | 5 | 14 | 0 | 1 | 48 | 57 |
| V4b_centre_B15_W345_120 | 85 | 98 | 5 | 23 | 5 | 14 | 0 | 0 | 48 | 57 |

### C_S21/left stage2 (n=907)
| set | handle R | handle D | frame_handle_side_z1.0 R | frame_handle_side_z1.0 D | frame_hinge_side_z1.0 R | frame_hinge_side_z1.0 D | doorway_floor_centre R | doorway_floor_centre D | panel_free_edge_z1.0 R | panel_free_edge_z1.0 D |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| V0_dual_B15_W45_180 | 100 | 100 | 100 | 100 | 0 | 6 | 8 | 31 | 100 | 100 |
| V1a_centre_B15_W45_180 | 100 | 100 | 100 | 100 | 0 | 1 | 8 | 31 | 100 | 100 |
| V1b_centre_B0_W45_180 | 100 | 100 | 15 | 99 | 0 | 0 | 8 | 31 | 28 | 99 |
| V2_head_d435i_B0_W45_180 | 100 | 100 | 12 | 43 | 0 | 0 | 8 | 31 | 23 | 50 |
| V2b_head_d435i_B15_W45_180 | 100 | 100 | 12 | 50 | 0 | 0 | 8 | 31 | 23 | 56 |
| V2c_head_studentRGB_W45_180 | 100 | 100 | 12 | 43 | 0 | 0 | 8 | 31 | 23 | 50 |
| V3_wrist_only_W45_180 | 100 | 100 | 12 | 43 | 0 | 0 | 8 | 31 | 23 | 50 |
| V4a_centre_B15_W39_140 | 100 | 100 | 100 | 100 | 0 | 1 | 0 | 14 | 100 | 100 |
| V4b_centre_B15_W345_120 | 100 | 100 | 100 | 100 | 0 | 1 | 0 | 6 | 100 | 100 |

### C_S21/left stage3 (n=3843)
| set | handle R | handle D | frame_handle_side_z1.0 R | frame_handle_side_z1.0 D | frame_hinge_side_z1.0 R | frame_hinge_side_z1.0 D | doorway_floor_centre R | doorway_floor_centre D | panel_free_edge_z1.0 R | panel_free_edge_z1.0 D |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| V0_dual_B15_W45_180 | 36 | 100 | 59 | 88 | 6 | 42 | 0 | 5 | 95 | 100 |
| V1a_centre_B15_W45_180 | 34 | 100 | 55 | 88 | 0 | 14 | 0 | 5 | 92 | 100 |
| V1b_centre_B0_W45_180 | 34 | 100 | 6 | 40 | 0 | 5 | 0 | 5 | 39 | 79 |
| V2_head_d435i_B0_W45_180 | 34 | 100 | 6 | 27 | 0 | 0 | 0 | 5 | 39 | 66 |
| V2b_head_d435i_B15_W45_180 | 34 | 100 | 6 | 27 | 0 | 0 | 0 | 5 | 39 | 67 |
| V2c_head_studentRGB_W45_180 | 34 | 100 | 6 | 27 | 0 | 0 | 2 | 5 | 39 | 66 |
| V3_wrist_only_W45_180 | 34 | 100 | 6 | 27 | 0 | 0 | 0 | 5 | 39 | 66 |
| V4a_centre_B15_W39_140 | 31 | 100 | 55 | 87 | 0 | 14 | 0 | 2 | 89 | 100 |
| V4b_centre_B15_W345_120 | 29 | 100 | 55 | 87 | 0 | 14 | 0 | 0 | 88 | 100 |

### C_S21/left stage4 (n=1402)
| set | handle R | handle D | frame_handle_side_z1.0 R | frame_handle_side_z1.0 D | frame_hinge_side_z1.0 R | frame_hinge_side_z1.0 D | doorway_floor_centre R | doorway_floor_centre D | panel_free_edge_z1.0 R | panel_free_edge_z1.0 D |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| V0_dual_B15_W45_180 | 99 | 100 | 0 | 3 | 1 | 11 | 0 | 0 | 84 | 100 |
| V1a_centre_B15_W45_180 | 98 | 100 | 0 | 3 | 0 | 1 | 0 | 0 | 78 | 100 |
| V1b_centre_B0_W45_180 | 98 | 100 | 0 | 0 | 0 | 0 | 0 | 0 | 22 | 53 |
| V2_head_d435i_B0_W45_180 | 98 | 100 | 0 | 0 | 0 | 0 | 0 | 0 | 22 | 52 |
| V2b_head_d435i_B15_W45_180 | 98 | 100 | 0 | 0 | 0 | 0 | 0 | 0 | 22 | 52 |
| V2c_head_studentRGB_W45_180 | 98 | 100 | 0 | 0 | 0 | 0 | 0 | 0 | 22 | 52 |
| V3_wrist_only_W45_180 | 98 | 100 | 0 | 0 | 0 | 0 | 0 | 0 | 22 | 52 |
| V4a_centre_B15_W39_140 | 97 | 100 | 0 | 3 | 0 | 1 | 0 | 0 | 74 | 100 |
| V4b_centre_B15_W345_120 | 97 | 100 | 0 | 3 | 0 | 1 | 0 | 0 | 73 | 100 |

### C_S21/right stage2 (n=942)
| set | handle R | handle D | frame_handle_side_z1.0 R | frame_handle_side_z1.0 D | frame_hinge_side_z1.0 R | frame_hinge_side_z1.0 D | doorway_floor_centre R | doorway_floor_centre D | panel_free_edge_z1.0 R | panel_free_edge_z1.0 D |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| V0_dual_B15_W45_180 | 100 | 100 | 100 | 100 | 89 | 100 | 4 | 24 | 100 | 100 |
| V1a_centre_B15_W45_180 | 100 | 100 | 100 | 100 | 48 | 97 | 4 | 24 | 100 | 100 |
| V1b_centre_B0_W45_180 | 100 | 100 | 60 | 100 | 33 | 88 | 4 | 24 | 65 | 100 |
| V2_head_d435i_B0_W45_180 | 100 | 100 | 5 | 32 | 0 | 0 | 4 | 24 | 13 | 41 |
| V2b_head_d435i_B15_W45_180 | 100 | 100 | 5 | 69 | 4 | 41 | 4 | 24 | 14 | 79 |
| V2c_head_studentRGB_W45_180 | 100 | 100 | 8 | 32 | 33 | 0 | 4 | 24 | 20 | 41 |
| V3_wrist_only_W45_180 | 100 | 100 | 5 | 32 | 0 | 0 | 4 | 24 | 13 | 41 |
| V4a_centre_B15_W39_140 | 99 | 100 | 100 | 100 | 48 | 97 | 0 | 8 | 100 | 100 |
| V4b_centre_B15_W345_120 | 99 | 100 | 100 | 100 | 48 | 97 | 0 | 2 | 100 | 100 |

### C_S21/right stage3 (n=3971)
| set | handle R | handle D | frame_handle_side_z1.0 R | frame_handle_side_z1.0 D | frame_hinge_side_z1.0 R | frame_hinge_side_z1.0 D | doorway_floor_centre R | doorway_floor_centre D | panel_free_edge_z1.0 R | panel_free_edge_z1.0 D |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| V0_dual_B15_W45_180 | 97 | 100 | 100 | 100 | 67 | 99 | 0 | 16 | 100 | 100 |
| V1a_centre_B15_W45_180 | 96 | 100 | 99 | 100 | 24 | 79 | 0 | 16 | 100 | 100 |
| V1b_centre_B0_W45_180 | 96 | 100 | 92 | 99 | 24 | 77 | 0 | 16 | 100 | 100 |
| V2_head_d435i_B0_W45_180 | 81 | 100 | 2 | 45 | 1 | 12 | 0 | 16 | 24 | 89 |
| V2b_head_d435i_B15_W45_180 | 96 | 100 | 49 | 83 | 2 | 20 | 0 | 16 | 85 | 100 |
| V2c_head_studentRGB_W45_180 | 98 | 100 | 58 | 37 | 85 | 0 | 0 | 16 | 90 | 69 |
| V3_wrist_only_W45_180 | 74 | 100 | 2 | 37 | 0 | 0 | 0 | 16 | 15 | 69 |
| V4a_centre_B15_W39_140 | 96 | 100 | 99 | 100 | 24 | 79 | 0 | 2 | 100 | 100 |
| V4b_centre_B15_W345_120 | 96 | 100 | 99 | 100 | 24 | 79 | 0 | 0 | 100 | 100 |

### C_S21/right stage4 (n=4492)
| set | handle R | handle D | frame_handle_side_z1.0 R | frame_handle_side_z1.0 D | frame_hinge_side_z1.0 R | frame_hinge_side_z1.0 D | doorway_floor_centre R | doorway_floor_centre D | panel_free_edge_z1.0 R | panel_free_edge_z1.0 D |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| V0_dual_B15_W45_180 | 89 | 99 | 36 | 53 | 21 | 37 | 7 | 40 | 80 | 86 |
| V1a_centre_B15_W45_180 | 87 | 99 | 18 | 47 | 7 | 18 | 7 | 40 | 75 | 81 |
| V1b_centre_B0_W45_180 | 87 | 99 | 8 | 21 | 7 | 17 | 7 | 40 | 74 | 79 |
| V2_head_d435i_B0_W45_180 | 69 | 99 | 0 | 0 | 0 | 3 | 7 | 40 | 14 | 47 |
| V2b_head_d435i_B15_W45_180 | 71 | 99 | 1 | 3 | 1 | 4 | 7 | 40 | 52 | 73 |
| V2c_head_studentRGB_W45_180 | 77 | 99 | 2 | 0 | 12 | 0 | 7 | 40 | 67 | 16 |
| V3_wrist_only_W45_180 | 66 | 99 | 0 | 0 | 0 | 0 | 7 | 40 | 2 | 16 |
| V4a_centre_B15_W39_140 | 86 | 99 | 18 | 47 | 7 | 18 | 1 | 12 | 75 | 81 |
| V4b_centre_B15_W345_120 | 85 | 99 | 18 | 47 | 7 | 18 | 0 | 5 | 75 | 81 |

### per-camera detail, C_S2/left and C_S2/right, stage3
### C_S2/left stage3 per CAMERA (n=8066)
| set | handle R | handle D | frame_handle_side_z1.0 R | frame_handle_side_z1.0 D | frame_hinge_side_z1.0 R | frame_hinge_side_z1.0 D | doorway_floor_centre R | doorway_floor_centre D | panel_free_edge_z1.0 R | panel_free_edge_z1.0 D |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| base_left_B15 | 23 | 21 | 66 | 99 | 0 | 1 | 0 | 0 | 100 | 100 |
| base_right_B15 | 17 | 18 | 73 | 98 | 3 | 43 | 0 | 0 | 100 | 100 |
| base_centre_B15 | 1 | 0 | 66 | 99 | 1 | 9 | 0 | 0 | 100 | 100 |
| base_centre_B0 | 0 | 0 | 0 | 13 | 0 | 5 | 0 | 0 | 1 | 24 |
| head_d435i_B0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| head_d435i_B15 | 0 | 4 | 0 | 2 | 0 | 1 | 0 | 0 | 0 | 3 |
| head_student_rgb | 0 | - | 0 | - | 2 | - | 14 | - | 0 | - |
| wrist_F45_180 | 47 | 100 | 13 | 32 | 0 | 0 | 0 | 9 | 47 | 70 |
| wrist_F39_140 | 40 | 100 | 5 | 19 | 0 | 0 | 0 | 2 | 35 | 55 |
| wrist_F345_120 | 36 | 100 | 2 | 13 | 0 | 0 | 0 | 1 | 30 | 51 |

### C_S2/right stage3 per CAMERA (n=7602)
| set | handle R | handle D | frame_handle_side_z1.0 R | frame_handle_side_z1.0 D | frame_hinge_side_z1.0 R | frame_hinge_side_z1.0 D | doorway_floor_centre R | doorway_floor_centre D | panel_free_edge_z1.0 R | panel_free_edge_z1.0 D |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| base_left_B15 | 85 | 84 | 73 | 100 | 93 | 100 | 0 | 0 | 100 | 100 |
| base_right_B15 | 47 | 46 | 100 | 100 | 7 | 72 | 0 | 0 | 100 | 100 |
| base_centre_B15 | 63 | 61 | 100 | 100 | 52 | 97 | 0 | 0 | 100 | 100 |
| base_centre_B0 | 65 | 63 | 98 | 100 | 47 | 95 | 0 | 0 | 100 | 100 |
| head_d435i_B0 | 44 | 79 | 0 | 30 | 1 | 22 | 0 | 0 | 8 | 76 |
| head_d435i_B15 | 91 | 100 | 60 | 91 | 3 | 45 | 0 | 0 | 92 | 100 |
| head_student_rgb | 94 | - | 79 | - | 81 | - | 0 | - | 97 | - |
| wrist_F45_180 | 70 | 100 | 5 | 38 | 0 | 0 | 0 | 8 | 10 | 62 |
| wrist_F39_140 | 70 | 100 | 2 | 26 | 0 | 0 | 0 | 0 | 5 | 47 |
| wrist_F345_120 | 73 | 100 | 1 | 21 | 0 | 0 | 0 | 0 | 4 | 40 |

