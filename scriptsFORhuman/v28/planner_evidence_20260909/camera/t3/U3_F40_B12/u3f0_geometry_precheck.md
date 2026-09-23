# U3_F0 geometry precheck (pinhole + Min-Z + arm-capsule screen; not rendered)

FK check vs exported flange pose: pos err p50/p95/max = 0.0000/0.0000/0.0000 m; rot err p50/p95/max = 0.00/0.00/0.00 deg

## Static arm poses (wrist camera pointing)
- training_default_[0,0,0,0.25,0.5,1.57]: flange axis pitch 30.21°, wrist RGB axis pitch -14.75° yaw 0.08°, TCP in wrist RGB=False depth=True, on-axis point enters wrist RGB at 0.1 m, depth at 0.075 m
- u3_reference_[0,0,0,0,0,1.57]: flange axis pitch 5.0°, wrist RGB axis pitch -39.96° yaw 0.1°, TCP in wrist RGB=False depth=True, on-axis point enters wrist RGB at 0.1 m, depth at 0.075 m

## C_S2/left
| stage | frames | L-RGB handle | L-RGB handle clear | R-RGB handle | R-RGB handle clear | L-D handle | R-D handle | W-RGB handle | W-D handle | L-RGB tcp clear | R-RGB tcp clear | L-RGB f7 clear | R-RGB f7 clear | L-RGB f8 clear | R-RGB f8 clear | W-RGB fingertip | W-D fingertip | W-RGB panel | L-RGB free edge | R-RGB free edge | L-RGB frame(handle side) | R-RGB frame(handle side) | L-RGB frame(hinge side) | R-RGB frame(hinge side) | L-RGB floor+1m | R-RGB floor+1m | R-D floor+1m | W-RGB floor+1m |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| stage2 | 1644 | 100% | 53% | 100% | 60% | 100% | 100% | 79% | 100% | 20% | 46% | 100% | 100% | 18% | 100% | 100% | 100% | 0% | 100% | 100% | 100% | 100% | 0% | 1% | 0% | 0% | 0% | 100% |
| stage3 | 8066 | 99% | 22% | 100% | 17% | 100% | 100% | 12% | 98% | 45% | 56% | 100% | 100% | 74% | 100% | 100% | 100% | 0% | 88% | 93% | 50% | 54% | 0% | 3% | 1% | 0% | 81% | 43% |
| stage4 | 11898 | 34% | 30% | 40% | 14% | 74% | 73% | 33% | 95% | 25% | 18% | 47% | 55% | 34% | 42% | 100% | 100% | 1% | 16% | 22% | 0% | 0% | 0% | 0% | 3% | 0% | 58% | 48% |
| stage5 | 5713 | 5% | 5% | 12% | 12% | 10% | 17% | 0% | 0% | 93% | 21% | 98% | 94% | 98% | 92% | 100% | 100% | 0% | 4% | 10% | 0% | 0% | 0% | 0% | 0% | 0% | 0% | 39% |

| stage | wrist axis vs B+X p50/p95 (deg) | wrist axis world elev p5/p50/p95 | q6 p5/p50/p95 (rad) | q6 dev>0.3 share | wrist ang speed p50/p95 (deg/s) | wrist axis sweep p50/p95 | share sweep>60 | az reversals/s | trunk-cam ang speed p50/p95 | dq6 p50/p95 (rad/s) | dq_arm max p95 |
|---|---|---|---|---:|---|---|---:|---:|---|---|---|
| stage2 | 45/52 | -52/-43/-36 | 1.41/1.50/1.62 | 0% | 84/159 | 61/127 | 52% | 10.49 | 27/47 | 0.59/1.78 | 5.06 |
| stage3 | 41/50 | -53/-37/-27 | 1.48/1.87/2.05 | 49% | 86/403 | 70/258 | 61% | 4.65 | 31/56 | 0.81/2.92 | 3.86 |
| stage4 | 34/52 | -55/-42/-25 | -0.13/1.06/2.03 | 75% | n/a (sampled 10 Hz) | | | | | |  |
| stage5 | 66/71 | -74/-61/-49 | 1.29/1.58/1.72 | 4% | n/a (sampled 10 Hz) | | | | | |  |

## C_S2/right
| stage | frames | L-RGB handle | L-RGB handle clear | R-RGB handle | R-RGB handle clear | L-D handle | R-D handle | W-RGB handle | W-D handle | L-RGB tcp clear | R-RGB tcp clear | L-RGB f7 clear | R-RGB f7 clear | L-RGB f8 clear | R-RGB f8 clear | W-RGB fingertip | W-D fingertip | W-RGB panel | L-RGB free edge | R-RGB free edge | L-RGB frame(handle side) | R-RGB frame(handle side) | L-RGB frame(hinge side) | R-RGB frame(hinge side) | L-RGB floor+1m | R-RGB floor+1m | R-D floor+1m | W-RGB floor+1m |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| stage2 | 1653 | 100% | 94% | 100% | 49% | 100% | 100% | 87% | 100% | 12% | 26% | 100% | 100% | 34% | 53% | 100% | 100% | 0% | 99% | 100% | 88% | 100% | 94% | 14% | 0% | 0% | 0% | 100% |
| stage3 | 7602 | 100% | 85% | 100% | 47% | 100% | 100% | 16% | 100% | 75% | 49% | 100% | 100% | 100% | 89% | 100% | 100% | 0% | 100% | 100% | 72% | 100% | 93% | 7% | 0% | 0% | 0% | 27% |
| stage4 | 6532 | 53% | 53% | 40% | 39% | 60% | 46% | 4% | 100% | 52% | 38% | 47% | 33% | 49% | 36% | 100% | 100% | 0% | 53% | 41% | 0% | 24% | 16% | 0% | 0% | 0% | 0% | 57% |
| stage5 | 3039 | 0% | 0% | 0% | 0% | 0% | 0% | 2% | 4% | 81% | 12% | 86% | 44% | 86% | 52% | 100% | 100% | 0% | 0% | 0% | 0% | 0% | 0% | 0% | 0% | 0% | 0% | 0% |

| stage | wrist axis vs B+X p50/p95 (deg) | wrist axis world elev p5/p50/p95 | q6 p5/p50/p95 (rad) | q6 dev>0.3 share | wrist ang speed p50/p95 (deg/s) | wrist axis sweep p50/p95 | share sweep>60 | az reversals/s | trunk-cam ang speed p50/p95 | dq6 p50/p95 (rad/s) | dq_arm max p95 |
|---|---|---|---|---:|---|---|---:|---:|---|---|---|
| stage2 | 45/51 | -48/-41/-35 | 1.56/1.69/1.79 | 0% | 95/179 | 59/127 | 50% | 11.44 | 23/37 | 0.55/1.74 | 5.04 |
| stage3 | 67/75 | -49/-37/-25 | 0.11/0.45/1.64 | 84% | 75/365 | 57/204 | 47% | 2.61 | 30/59 | 1.46/3.17 | 3.54 |
| stage4 | 88/100 | -79/-66/-36 | 0.45/0.79/1.27 | 95% | n/a (sampled 10 Hz) | | | | | |  |
| stage5 | 74/93 | -78/-62/-42 | 1.13/1.65/1.85 | 10% | n/a (sampled 10 Hz) | | | | | |  |

## C_S21/left
| stage | frames | L-RGB handle | L-RGB handle clear | R-RGB handle | R-RGB handle clear | L-D handle | R-D handle | W-RGB handle | W-D handle | L-RGB tcp clear | R-RGB tcp clear | L-RGB f7 clear | R-RGB f7 clear | L-RGB f8 clear | R-RGB f8 clear | W-RGB fingertip | W-D fingertip | W-RGB panel | L-RGB free edge | R-RGB free edge | L-RGB frame(handle side) | R-RGB frame(handle side) | L-RGB frame(hinge side) | R-RGB frame(hinge side) | L-RGB floor+1m | R-RGB floor+1m | R-D floor+1m | W-RGB floor+1m |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| stage2 | 907 | 100% | 67% | 100% | 46% | 100% | 100% | 92% | 100% | 9% | 26% | 93% | 100% | 13% | 82% | 100% | 100% | 0% | 100% | 100% | 100% | 100% | 0% | 0% | 0% | 0% | 2% | 100% |
| stage3 | 3843 | 92% | 4% | 94% | 2% | 100% | 100% | 14% | 88% | 0% | 79% | 98% | 99% | 37% | 97% | 100% | 100% | 0% | 62% | 66% | 48% | 49% | 0% | 6% | 1% | 0% | 59% | 74% |
| stage4 | 1402 | 59% | 46% | 66% | 51% | 99% | 99% | 44% | 100% | 26% | 61% | 94% | 95% | 62% | 76% | 100% | 100% | 0% | 28% | 39% | 0% | 0% | 0% | 1% | 0% | 0% | 25% | 84% |
| stage5 | 2919 | 15% | 15% | 26% | 26% | 21% | 29% | 5% | 8% | 95% | 25% | 99% | 92% | 99% | 97% | 100% | 100% | 0% | 16% | 26% | 0% | 0% | 0% | 0% | 0% | 0% | 0% | 25% |

| stage | wrist axis vs B+X p50/p95 (deg) | wrist axis world elev p5/p50/p95 | q6 p5/p50/p95 (rad) | q6 dev>0.3 share | wrist ang speed p50/p95 (deg/s) | wrist axis sweep p50/p95 | share sweep>60 | az reversals/s | trunk-cam ang speed p50/p95 | dq6 p50/p95 (rad/s) | dq_arm max p95 |
|---|---|---|---|---:|---|---|---:|---:|---|---|---|
| stage2 | 41/52 | -49/-38/-29 | 1.36/1.50/1.60 | 0% | 98/211 | 75/150 | 63% | 12.04 | 25/39 | 1.00/2.52 | 5.03 |
| stage3 | 33/43 | -39/-31/-22 | 1.44/1.90/2.09 | 54% | 71/292 | 54/168 | 44% | 5.60 | 29/52 | 0.74/2.93 | 2.94 |
| stage4 | 40/47 | -52/-47/-34 | 0.83/0.99/1.55 | 88% | n/a (sampled 10 Hz) | | | | | |  |
| stage5 | 66/73 | -60/-53/-47 | 0.95/1.34/1.61 | 39% | n/a (sampled 10 Hz) | | | | | |  |

## C_S21/right
| stage | frames | L-RGB handle | L-RGB handle clear | R-RGB handle | R-RGB handle clear | L-D handle | R-D handle | W-RGB handle | W-D handle | L-RGB tcp clear | R-RGB tcp clear | L-RGB f7 clear | R-RGB f7 clear | L-RGB f8 clear | R-RGB f8 clear | W-RGB fingertip | W-D fingertip | W-RGB panel | L-RGB free edge | R-RGB free edge | L-RGB frame(handle side) | R-RGB frame(handle side) | L-RGB frame(hinge side) | R-RGB frame(hinge side) | L-RGB floor+1m | R-RGB floor+1m | R-D floor+1m | W-RGB floor+1m |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| stage2 | 942 | 100% | 86% | 100% | 48% | 100% | 100% | 78% | 100% | 18% | 23% | 100% | 93% | 68% | 33% | 100% | 100% | 4% | 100% | 100% | 97% | 100% | 89% | 8% | 0% | 0% | 0% | 100% |
| stage3 | 3971 | 98% | 89% | 100% | 62% | 100% | 100% | 17% | 100% | 72% | 58% | 97% | 93% | 99% | 71% | 100% | 100% | 1% | 98% | 100% | 85% | 100% | 69% | 4% | 0% | 0% | 0% | 56% |
| stage4 | 4492 | 62% | 62% | 70% | 70% | 84% | 75% | 22% | 99% | 59% | 68% | 60% | 65% | 69% | 67% | 100% | 100% | 0% | 69% | 71% | 3% | 31% | 22% | 2% | 0% | 0% | 0% | 84% |
| stage5 | 2065 | 7% | 7% | 5% | 4% | 9% | 8% | 5% | 7% | 86% | 39% | 93% | 87% | 92% | 88% | 100% | 100% | 0% | 6% | 5% | 0% | 0% | 0% | 0% | 0% | 0% | 0% | 14% |

| stage | wrist axis vs B+X p50/p95 (deg) | wrist axis world elev p5/p50/p95 | q6 p5/p50/p95 (rad) | q6 dev>0.3 share | wrist ang speed p50/p95 (deg/s) | wrist axis sweep p50/p95 | share sweep>60 | az reversals/s | trunk-cam ang speed p50/p95 | dq6 p50/p95 (rad/s) | dq_arm max p95 |
|---|---|---|---|---:|---|---|---:|---:|---|---|---|
| stage2 | 43/52 | -51/-40/-30 | 1.63/1.79/1.95 | 23% | 112/174 | 73/135 | 64% | 8.76 | 30/58 | 0.98/2.64 | 5.02 |
| stage3 | 69/78 | -56/-35/-25 | 0.14/0.45/1.70 | 85% | 89/228 | 71/161 | 58% | 2.53 | 29/59 | 1.45/3.05 | 3.06 |
| stage4 | 87/101 | -74/-60/-47 | 0.15/0.36/1.36 | 95% | n/a (sampled 10 Hz) | | | | | |  |
| stage5 | 68/82 | -64/-52/-42 | 1.33/1.51/1.62 | 3% | n/a (sampled 10 Hz) | | | | | |  |

## Synthetic Stage0/1 approach (trunk z 0.48, arm default pose, nominal LEFT door W 0.95 / handle 0.90; share over 3 lateral x 3 yaw poses)
| dist (m) | base_left/depth/doorway_floor_centre | base_left/depth/frame_handle_side_z1.0 | base_left/depth/frame_hinge_side_z1.0 | base_left/depth/handle | base_left/depth/lintel_centre | base_left/depth/panel_mid_z1.0 | base_left/rgb/doorway_floor_centre | base_left/rgb/frame_handle_side_z1.0 | base_left/rgb/frame_hinge_side_z1.0 | base_left/rgb/handle | base_left/rgb/lintel_centre | base_left/rgb/panel_mid_z1.0 | base_right/depth/doorway_floor_centre | base_right/depth/frame_handle_side_z1.0 | base_right/depth/frame_hinge_side_z1.0 | base_right/depth/handle | base_right/depth/lintel_centre | base_right/depth/panel_mid_z1.0 | base_right/rgb/doorway_floor_centre | base_right/rgb/frame_handle_side_z1.0 | base_right/rgb/frame_hinge_side_z1.0 | base_right/rgb/handle | base_right/rgb/lintel_centre | base_right/rgb/panel_mid_z1.0 | wrist/depth/doorway_floor_centre | wrist/depth/frame_handle_side_z1.0 | wrist/depth/frame_hinge_side_z1.0 | wrist/depth/handle | wrist/depth/lintel_centre | wrist/depth/panel_mid_z1.0 | wrist/rgb/doorway_floor_centre | wrist/rgb/frame_handle_side_z1.0 | wrist/rgb/frame_hinge_side_z1.0 | wrist/rgb/handle | wrist/rgb/lintel_centre | wrist/rgb/panel_mid_z1.0 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.7 | 0% | 100% | 33% | 100% | 0% | 78% | 0% | 100% | 0% | 89% | 0% | 44% | 0% | 89% | 44% | 100% | 0% | 89% | 0% | 78% | 33% | 89% | 0% | 78% | 0% | 89% | 33% | 100% | 0% | 78% | 0% | 89% | 0% | 89% | 0% | 56% |
| 0.8 | 0% | 100% | 33% | 100% | 0% | 78% | 0% | 100% | 11% | 89% | 0% | 56% | 0% | 100% | 56% | 100% | 0% | 100% | 0% | 89% | 33% | 89% | 0% | 89% | 0% | 100% | 33% | 100% | 0% | 78% | 0% | 89% | 11% | 89% | 0% | 56% |
| 1.0 | 0% | 100% | 44% | 100% | 0% | 89% | 0% | 100% | 33% | 89% | 0% | 67% | 0% | 100% | 67% | 100% | 0% | 100% | 0% | 89% | 44% | 100% | 0% | 89% | 0% | 100% | 44% | 100% | 0% | 89% | 0% | 89% | 33% | 100% | 0% | 78% |
| 1.2 | 0% | 100% | 67% | 100% | 0% | 89% | 0% | 100% | 33% | 100% | 0% | 78% | 0% | 100% | 78% | 100% | 0% | 100% | 0% | 89% | 56% | 100% | 0% | 100% | 33% | 100% | 67% | 100% | 0% | 100% | 0% | 100% | 33% | 100% | 0% | 78% |
| 1.5 | 0% | 100% | 67% | 100% | 0% | 100% | 0% | 100% | 44% | 100% | 0% | 78% | 0% | 100% | 89% | 100% | 0% | 100% | 0% | 100% | 67% | 100% | 0% | 100% | 100% | 100% | 67% | 100% | 0% | 100% | 11% | 100% | 56% | 100% | 0% | 89% |
