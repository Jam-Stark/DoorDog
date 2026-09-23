### A. Handle visibility per lane/stage (share of trace frames; base: pinhole+MinZ+arm-capsule clear; wrist: pinhole+MinZ, no mesh occlusion)
| lane | stage | n | L-RGB clear asym/B12/B15/B20 | R-RGB clear asym/B12/B15/B20 | L-D asym/B12/B15/B20 | R-D asym/B12/B15/B20 | W-RGB th40/th45 | W-D th40/th45 | W-D TCP th40/th45 |
|---|---|---:|---|---|---|---|---|---|---|
| C_S2/left | stage2 | 1644 | 52/53/53/52 | 60/60/60/60 | 100/100/100/100 | 100/100/100/100 | 79/99 | 100/100 | 100/100 |
| C_S2/left | stage3 | 8066 | 22/22/23/23 | 17/17/17/17 | 100/100/100/100 | 100/100/100/100 | 12/45 | 98/100 | 100/100 |
| C_S2/left | stage4 | 11898 | 48/30/39/47 | 14/14/21/36 | 96/74/87/97 | 73/73/86/98 | 33/90 | 95/95 | 100/100 |
| C_S2/left | stage5 | 5713 | 0/5/5/4 | 12/12/11/8 | 4/10/10/9 | 17/17/17/16 | 0/0 | 0/0 | 100/100 |
| C_S2/right | stage2 | 1653 | 93/94/93/93 | 49/49/49/49 | 100/100/100/100 | 100/100/100/100 | 87/100 | 100/100 | 100/100 |
| C_S2/right | stage3 | 7602 | 12/85/85/79 | 47/47/47/40 | 53/100/100/100 | 100/100/100/100 | 16/65 | 100/100 | 100/100 |
| C_S2/right | stage4 | 6532 | 11/53/53/48 | 39/39/38/32 | 51/60/62/64 | 46/46/46/46 | 4/68 | 100/100 | 100/100 |
| C_S2/right | stage5 | 3039 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 2/1 | 4/3 | 100/100 |
| C_S21/left | stage2 | 907 | 66/67/66/66 | 46/46/46/46 | 100/100/100/100 | 100/100/100/100 | 92/100 | 100/100 | 100/100 |
| C_S21/left | stage3 | 3843 | 5/4/5/5 | 2/2/2/2 | 100/100/100/100 | 100/100/100/100 | 14/34 | 88/100 | 100/100 |
| C_S21/left | stage4 | 1402 | 81/46/69/81 | 51/51/68/75 | 100/99/100/100 | 99/99/100/100 | 44/98 | 100/100 | 100/100 |
| C_S21/left | stage5 | 2919 | 14/15/15/15 | 26/26/26/26 | 20/21/21/21 | 29/29/29/30 | 5/6 | 8/7 | 100/100 |
| C_S21/right | stage2 | 942 | 86/86/86/86 | 48/48/48/47 | 100/100/100/100 | 100/100/100/100 | 78/99 | 100/100 | 100/100 |
| C_S21/right | stage3 | 3971 | 13/89/89/79 | 62/62/62/51 | 61/100/100/100 | 100/100/100/100 | 17/72 | 100/100 | 100/100 |
| C_S21/right | stage4 | 4492 | 13/62/62/55 | 70/70/70/63 | 67/84/84/85 | 75/75/75/74 | 22/63 | 99/99 | 100/100 |
| C_S21/right | stage5 | 2065 | 11/7/8/9 | 4/4/4/3 | 13/9/10/11 | 8/8/8/9 | 5/4 | 7/6 | 100/100 |

### B. Door frame / floor / lintel in base RGB (asym/B12/B15/B20), per lane/stage; W-RGB floor+1m th40/th45
| lane | stage | L frame(handle side) | R frame(handle side) | L frame(hinge side) | R frame(hinge side) | L doorway floor | R doorway floor | L floor+1m | R floor+1m | L lintel | R lintel | W-RGB floor+1m | W-D doorway floor th40/45 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| C_S2/left | stage2 | 100/100/100/100 | 100/100/100/100 | 0/0/0/0 | 1/1/1/1 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 100/100 | 31/54 |
| C_S2/left | stage3 | 100/50/66/96 | 54/54/71/97 | 0/0/0/0 | 3/3/3/3 | 0/0/0/0 | 0/0/0/0 | 0/1/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 43/40 | 3/9 |
| C_S2/left | stage4 | 10/0/0/3 | 0/0/1/3 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/3/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 48/53 | 1/1 |
| C_S2/left | stage5 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 39/41 | 0/0 |
| C_S2/right | stage2 | 85/88/89/90 | 100/100/100/100 | 96/94/95/96 | 14/14/15/16 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 2/0/0/0 | 0/0/0/0 | 100/100 | 3/18 |
| C_S2/right | stage3 | 38/72/72/71 | 100/100/100/100 | 28/93/93/93 | 7/7/6/5 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 88/0/0/0 | 0/0/0/0 | 27/21 | 1/8 |
| C_S2/right | stage4 | 0/0/0/0 | 24/24/27/30 | 12/16/16/17 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 8/0/0/0 | 0/0/0/0 | 57/59 | 1/18 |
| C_S2/right | stage5 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0 | 0/0 |
| C_S21/left | stage2 | 100/100/100/100 | 100/100/100/100 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 100/100 | 15/31 |
| C_S21/left | stage3 | 100/48/55/76 | 49/49/57/79 | 0/0/0/0 | 6/6/7/7 | 0/0/0/0 | 0/0/0/0 | 0/1/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 74/53 | 2/5 |
| C_S21/left | stage4 | 17/0/0/1 | 0/0/0/1 | 0/0/0/0 | 1/1/1/1 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 84/94 | 0/0 |
| C_S21/left | stage5 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 25/33 | 0/0 |
| C_S21/right | stage2 | 95/97/98/98 | 100/100/100/100 | 90/89/90/91 | 8/8/9/9 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 1/0/0/0 | 0/0/0/0 | 100/100 | 9/24 |
| C_S21/right | stage3 | 55/85/86/85 | 100/100/100/100 | 17/69/68/61 | 4/4/4/3 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 85/0/0/0 | 0/0/0/2 | 56/50 | 3/16 |
| C_S21/right | stage4 | 1/3/3/2 | 31/31/37/46 | 8/22/22/22 | 2/2/1/1 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 14/0/0/0 | 0/0/0/0 | 84/81 | 13/40 |
| C_S21/right | stage5 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 14/16 | 0/0 |

### C. Mirror symmetry: handle-side camera (L cam on LEFT door vs R cam on RIGHT door) and hinge-side camera, RGB handle arm-clear / depth handle / RGB frame(handle side) / RGB floor+1m; value = LEFT-door lane vs RIGHT-door lane, |diff| in pp
| cell | stage | metric | camera role | asym L-door/R-door (|d|) | B12 L/R (|d|) | B15 L/R (|d|) |
|---|---|---|---|---|---|---|
| C_S2 | stage2 | RGB handle clear | handle-side | 52/49 (3) | 53/49 (3) | 53/49 (3) | 52/49 (3) |
| C_S2 | stage2 | RGB handle clear | hinge-side | 60/93 (32) | 60/94 (33) | 60/93 (34) | 60/93 (34) |
| C_S2 | stage2 | depth handle | handle-side | 100/100 (0) | 100/100 (0) | 100/100 (0) | 100/100 (0) |
| C_S2 | stage2 | depth handle | hinge-side | 100/100 (0) | 100/100 (0) | 100/100 (0) | 100/100 (0) |
| C_S2 | stage2 | RGB frame handle-side | handle-side | 100/100 (0) | 100/100 (0) | 100/100 (0) | 100/100 (0) |
| C_S2 | stage2 | RGB frame handle-side | hinge-side | 100/85 (15) | 100/88 (12) | 100/89 (11) | 100/90 (10) |
| C_S2 | stage2 | RGB floor+1m | handle-side | 0/0 (0) | 0/0 (0) | 0/0 (0) | 0/0 (0) |
| C_S2 | stage2 | RGB floor+1m | hinge-side | 0/0 (0) | 0/0 (0) | 0/0 (0) | 0/0 (0) |
| C_S2 | stage2 | RGB lintel | handle-side | 0/0 (0) | 0/0 (0) | 0/0 (0) | 0/0 (0) |
| C_S2 | stage2 | RGB lintel | hinge-side | 0/2 (2) | 0/0 (0) | 0/0 (0) | 0/0 (0) |
| C_S2 | stage3 | RGB handle clear | handle-side | 22/47 (25) | 22/47 (25) | 23/47 (24) | 23/40 (17) |
| C_S2 | stage3 | RGB handle clear | hinge-side | 17/12 (5) | 17/85 (68) | 17/85 (68) | 17/79 (62) |
| C_S2 | stage3 | depth handle | handle-side | 100/100 (0) | 100/100 (0) | 100/100 (0) | 100/100 (0) |
| C_S2 | stage3 | depth handle | hinge-side | 100/53 (47) | 100/100 (0) | 100/100 (0) | 100/100 (0) |
| C_S2 | stage3 | RGB frame handle-side | handle-side | 100/100 (0) | 50/100 (50) | 66/100 (34) | 96/100 (4) |
| C_S2 | stage3 | RGB frame handle-side | hinge-side | 54/38 (15) | 54/72 (18) | 71/72 (1) | 97/71 (26) |
| C_S2 | stage3 | RGB floor+1m | handle-side | 0/0 (0) | 1/0 (1) | 0/0 (0) | 0/0 (0) |
| C_S2 | stage3 | RGB floor+1m | hinge-side | 0/0 (0) | 0/0 (0) | 0/0 (0) | 0/0 (0) |
| C_S2 | stage3 | RGB lintel | handle-side | 0/0 (0) | 0/0 (0) | 0/0 (0) | 0/0 (0) |
| C_S2 | stage3 | RGB lintel | hinge-side | 0/88 (88) | 0/0 (0) | 0/0 (0) | 0/0 (0) |
| C_S2 | stage4 | RGB handle clear | handle-side | 48/39 (9) | 30/39 (9) | 39/38 (1) | 47/32 (15) |
| C_S2 | stage4 | RGB handle clear | hinge-side | 14/11 (3) | 14/53 (39) | 21/53 (32) | 36/48 (13) |
| C_S2 | stage4 | depth handle | handle-side | 96/46 (50) | 74/46 (28) | 87/46 (41) | 97/46 (51) |
| C_S2 | stage4 | depth handle | hinge-side | 73/51 (21) | 73/60 (12) | 86/62 (24) | 98/64 (34) |
| C_S2 | stage4 | RGB frame handle-side | handle-side | 10/24 (14) | 0/24 (24) | 0/27 (26) | 3/30 (26) |
| C_S2 | stage4 | RGB frame handle-side | hinge-side | 0/0 (0) | 0/0 (0) | 1/0 (1) | 3/0 (3) |
| C_S2 | stage4 | RGB floor+1m | handle-side | 0/0 (0) | 3/0 (3) | 0/0 (0) | 0/0 (0) |
| C_S2 | stage4 | RGB floor+1m | hinge-side | 0/0 (0) | 0/0 (0) | 0/0 (0) | 0/0 (0) |
| C_S2 | stage4 | RGB lintel | handle-side | 0/0 (0) | 0/0 (0) | 0/0 (0) | 0/0 (0) |
| C_S2 | stage4 | RGB lintel | hinge-side | 0/8 (8) | 0/0 (0) | 0/0 (0) | 0/0 (0) |
| C_S2 | stage5 | RGB handle clear | handle-side | 0/0 (0) | 5/0 (5) | 5/0 (5) | 4/0 (4) |
| C_S2 | stage5 | RGB handle clear | hinge-side | 12/0 (12) | 12/0 (12) | 11/0 (11) | 8/0 (8) |
| C_S2 | stage5 | depth handle | handle-side | 4/0 (4) | 10/0 (10) | 10/0 (10) | 9/0 (9) |
| C_S2 | stage5 | depth handle | hinge-side | 17/0 (17) | 17/0 (17) | 17/0 (17) | 16/0 (16) |
| C_S2 | stage5 | RGB frame handle-side | handle-side | 0/0 (0) | 0/0 (0) | 0/0 (0) | 0/0 (0) |
| C_S2 | stage5 | RGB frame handle-side | hinge-side | 0/0 (0) | 0/0 (0) | 0/0 (0) | 0/0 (0) |
| C_S2 | stage5 | RGB floor+1m | handle-side | 0/0 (0) | 0/0 (0) | 0/0 (0) | 0/0 (0) |
| C_S2 | stage5 | RGB floor+1m | hinge-side | 0/0 (0) | 0/0 (0) | 0/0 (0) | 0/0 (0) |
| C_S2 | stage5 | RGB lintel | handle-side | 0/0 (0) | 0/0 (0) | 0/0 (0) | 0/0 (0) |
| C_S2 | stage5 | RGB lintel | hinge-side | 0/0 (0) | 0/0 (0) | 0/0 (0) | 0/0 (0) |
| C_S21 | stage2 | RGB handle clear | handle-side | 66/48 (18) | 67/48 (19) | 66/48 (19) | 66/47 (19) |
| C_S21 | stage2 | RGB handle clear | hinge-side | 46/86 (40) | 46/86 (40) | 46/86 (40) | 46/86 (40) |
| C_S21 | stage2 | depth handle | handle-side | 100/100 (0) | 100/100 (0) | 100/100 (0) | 100/100 (0) |
| C_S21 | stage2 | depth handle | hinge-side | 100/100 (0) | 100/100 (0) | 100/100 (0) | 100/100 (0) |
| C_S21 | stage2 | RGB frame handle-side | handle-side | 100/100 (0) | 100/100 (0) | 100/100 (0) | 100/100 (0) |
| C_S21 | stage2 | RGB frame handle-side | hinge-side | 100/95 (5) | 100/97 (3) | 100/98 (2) | 100/98 (2) |
| C_S21 | stage2 | RGB floor+1m | handle-side | 0/0 (0) | 0/0 (0) | 0/0 (0) | 0/0 (0) |
| C_S21 | stage2 | RGB floor+1m | hinge-side | 0/0 (0) | 0/0 (0) | 0/0 (0) | 0/0 (0) |
| C_S21 | stage2 | RGB lintel | handle-side | 0/0 (0) | 0/0 (0) | 0/0 (0) | 0/0 (0) |
| C_S21 | stage2 | RGB lintel | hinge-side | 0/1 (1) | 0/0 (0) | 0/0 (0) | 0/0 (0) |
| C_S21 | stage3 | RGB handle clear | handle-side | 5/62 (56) | 4/62 (58) | 5/62 (56) | 5/51 (45) |
| C_S21 | stage3 | RGB handle clear | hinge-side | 2/13 (11) | 2/89 (86) | 2/89 (86) | 2/79 (76) |
| C_S21 | stage3 | depth handle | handle-side | 100/100 (0) | 100/100 (0) | 100/100 (0) | 100/100 (0) |
| C_S21 | stage3 | depth handle | hinge-side | 100/61 (39) | 100/100 (0) | 100/100 (0) | 100/100 (0) |
| C_S21 | stage3 | RGB frame handle-side | handle-side | 100/100 (0) | 48/100 (52) | 55/100 (45) | 76/100 (24) |
| C_S21 | stage3 | RGB frame handle-side | hinge-side | 49/55 (6) | 49/85 (36) | 57/86 (28) | 79/85 (6) |
| C_S21 | stage3 | RGB floor+1m | handle-side | 0/0 (0) | 1/0 (1) | 0/0 (0) | 0/0 (0) |
| C_S21 | stage3 | RGB floor+1m | hinge-side | 0/0 (0) | 0/0 (0) | 0/0 (0) | 0/0 (0) |
| C_S21 | stage3 | RGB lintel | handle-side | 0/0 (0) | 0/0 (0) | 0/0 (0) | 0/2 (2) |
| C_S21 | stage3 | RGB lintel | hinge-side | 0/85 (85) | 0/0 (0) | 0/0 (0) | 0/0 (0) |
| C_S21 | stage4 | RGB handle clear | handle-side | 81/70 (11) | 46/70 (25) | 69/70 (1) | 81/63 (18) |
| C_S21 | stage4 | RGB handle clear | hinge-side | 51/13 (38) | 51/62 (11) | 68/62 (6) | 75/55 (20) |
| C_S21 | stage4 | depth handle | handle-side | 100/75 (25) | 99/75 (24) | 100/75 (25) | 100/74 (26) |
| C_S21 | stage4 | depth handle | hinge-side | 99/67 (31) | 99/84 (14) | 100/84 (16) | 100/85 (15) |
| C_S21 | stage4 | RGB frame handle-side | handle-side | 17/31 (14) | 0/31 (31) | 0/37 (37) | 1/46 (44) |
| C_S21 | stage4 | RGB frame handle-side | hinge-side | 0/1 (1) | 0/3 (3) | 0/3 (3) | 1/2 (1) |
| C_S21 | stage4 | RGB floor+1m | handle-side | 0/0 (0) | 0/0 (0) | 0/0 (0) | 0/0 (0) |
| C_S21 | stage4 | RGB floor+1m | hinge-side | 0/0 (0) | 0/0 (0) | 0/0 (0) | 0/0 (0) |
| C_S21 | stage4 | RGB lintel | handle-side | 0/0 (0) | 0/0 (0) | 0/0 (0) | 0/0 (0) |
| C_S21 | stage4 | RGB lintel | hinge-side | 0/14 (14) | 0/0 (0) | 0/0 (0) | 0/0 (0) |
| C_S21 | stage5 | RGB handle clear | handle-side | 14/4 (11) | 15/4 (11) | 15/4 (12) | 15/3 (12) |
| C_S21 | stage5 | RGB handle clear | hinge-side | 26/11 (15) | 26/7 (19) | 26/8 (18) | 26/9 (17) |
| C_S21 | stage5 | depth handle | handle-side | 20/8 (13) | 21/8 (13) | 21/8 (13) | 21/9 (12) |
| C_S21 | stage5 | depth handle | hinge-side | 29/13 (17) | 29/9 (20) | 29/10 (19) | 30/11 (18) |
| C_S21 | stage5 | RGB frame handle-side | handle-side | 0/0 (0) | 0/0 (0) | 0/0 (0) | 0/0 (0) |
| C_S21 | stage5 | RGB frame handle-side | hinge-side | 0/0 (0) | 0/0 (0) | 0/0 (0) | 0/0 (0) |
| C_S21 | stage5 | RGB floor+1m | handle-side | 0/0 (0) | 0/0 (0) | 0/0 (0) | 0/0 (0) |
| C_S21 | stage5 | RGB floor+1m | hinge-side | 0/0 (0) | 0/0 (0) | 0/0 (0) | 0/0 (0) |
| C_S21 | stage5 | RGB lintel | handle-side | 0/0 (0) | 0/0 (0) | 0/0 (0) | 0/0 (0) |
| C_S21 | stage5 | RGB lintel | hinge-side | 0/0 (0) | 0/0 (0) | 0/0 (0) | 0/0 (0) |

Mean |L-door minus R-door| over all rows above (pp): asym(L32/R12): 10.3 (max 88), B12 sym: 10.5 (max 86), B15 sym: 9.6 (max 86), B20 sym: 9.2 (max 76)

### D. Synthetic Stage0/1 approach (LEFT door W0.95/H2.05/handle 0.90; trunk z 0.48; 3 lateral x 3 yaw poses per distance; arm at NEW reset posture j5=-0.44 (th40) / -0.52 (th45)); share of 9 poses
| variant | dist | L-RGB handle | R-RGB handle | L-D handle | R-D handle | L-RGB frame_handle_side | R-RGB frame_hinge_side | L-RGB lintel | R-RGB lintel | L-D doorway_floor | R-D doorway_floor | W-RGB handle | W-D handle | W-RGB frame_handle_side | W-RGB panel_mid | W-RGB doorway_floor | W-D doorway_floor | W-RGB lintel |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| U3_F40 | 1.5 | 0 | 100 | 100 | 100 | 100 | 67 | 100 | 0 | 0 | 0 | 100 | 100 | 100 | 89 | 11 | 100 | 0 |
| U3_F40 | 1.2 | 89 | 100 | 100 | 100 | 100 | 56 | 78 | 0 | 0 | 0 | 100 | 100 | 100 | 78 | 0 | 33 | 0 |
| U3_F40 | 1.0 | 89 | 100 | 100 | 100 | 100 | 44 | 22 | 0 | 0 | 0 | 100 | 100 | 89 | 78 | 0 | 0 | 0 |
| U3_F40 | 0.8 | 89 | 89 | 100 | 100 | 100 | 33 | 0 | 0 | 0 | 0 | 89 | 100 | 89 | 56 | 0 | 0 | 0 |
| U3_F40 | 0.7 | 89 | 89 | 100 | 100 | 100 | 33 | 0 | 0 | 0 | 0 | 89 | 100 | 89 | 56 | 0 | 0 | 0 |
| U3_F40_B12 | 1.5 | 100 | 100 | 100 | 100 | 100 | 67 | 0 | 0 | 0 | 0 | 100 | 100 | 100 | 89 | 11 | 100 | 0 |
| U3_F40_B12 | 1.2 | 100 | 100 | 100 | 100 | 100 | 56 | 0 | 0 | 0 | 0 | 100 | 100 | 100 | 78 | 0 | 33 | 0 |
| U3_F40_B12 | 1.0 | 89 | 100 | 100 | 100 | 100 | 44 | 0 | 0 | 0 | 0 | 100 | 100 | 89 | 78 | 0 | 0 | 0 |
| U3_F40_B12 | 0.8 | 89 | 89 | 100 | 100 | 100 | 33 | 0 | 0 | 0 | 0 | 89 | 100 | 89 | 56 | 0 | 0 | 0 |
| U3_F40_B12 | 0.7 | 89 | 89 | 100 | 100 | 100 | 33 | 0 | 0 | 0 | 0 | 89 | 100 | 89 | 56 | 0 | 0 | 0 |
| U3_F40_B15 | 1.5 | 100 | 100 | 100 | 100 | 100 | 67 | 0 | 0 | 0 | 0 | 100 | 100 | 100 | 89 | 11 | 100 | 0 |
| U3_F40_B15 | 1.2 | 100 | 100 | 100 | 100 | 100 | 56 | 0 | 0 | 0 | 0 | 100 | 100 | 100 | 78 | 0 | 33 | 0 |
| U3_F40_B15 | 1.0 | 89 | 100 | 100 | 100 | 100 | 44 | 0 | 0 | 0 | 0 | 100 | 100 | 89 | 78 | 0 | 0 | 0 |
| U3_F40_B15 | 0.8 | 89 | 89 | 100 | 100 | 100 | 33 | 0 | 0 | 0 | 0 | 89 | 100 | 89 | 56 | 0 | 0 | 0 |
| U3_F40_B15 | 0.7 | 89 | 89 | 100 | 100 | 100 | 33 | 0 | 0 | 0 | 0 | 89 | 100 | 89 | 56 | 0 | 0 | 0 |
| U3_F45 | 1.5 | 0 | 100 | 100 | 100 | 100 | 67 | 100 | 0 | 0 | 0 | 100 | 100 | 100 | 89 | 22 | 100 | 0 |
| U3_F45 | 1.2 | 89 | 100 | 100 | 100 | 100 | 56 | 78 | 0 | 0 | 0 | 100 | 100 | 100 | 78 | 0 | 67 | 0 |
| U3_F45 | 1.0 | 89 | 100 | 100 | 100 | 100 | 44 | 22 | 0 | 0 | 0 | 100 | 100 | 89 | 78 | 0 | 0 | 0 |
| U3_F45 | 0.8 | 89 | 89 | 100 | 100 | 100 | 33 | 0 | 0 | 0 | 0 | 89 | 100 | 89 | 56 | 0 | 0 | 0 |
| U3_F45 | 0.7 | 89 | 89 | 100 | 100 | 100 | 33 | 0 | 0 | 0 | 0 | 89 | 100 | 89 | 56 | 0 | 0 | 0 |
| U3_F45_B12 | 1.5 | 100 | 100 | 100 | 100 | 100 | 67 | 0 | 0 | 0 | 0 | 100 | 100 | 100 | 89 | 22 | 100 | 0 |
| U3_F45_B12 | 1.2 | 100 | 100 | 100 | 100 | 100 | 56 | 0 | 0 | 0 | 0 | 100 | 100 | 100 | 78 | 0 | 67 | 0 |
| U3_F45_B12 | 1.0 | 89 | 100 | 100 | 100 | 100 | 44 | 0 | 0 | 0 | 0 | 100 | 100 | 89 | 78 | 0 | 0 | 0 |
| U3_F45_B12 | 0.8 | 89 | 89 | 100 | 100 | 100 | 33 | 0 | 0 | 0 | 0 | 89 | 100 | 89 | 56 | 0 | 0 | 0 |
| U3_F45_B12 | 0.7 | 89 | 89 | 100 | 100 | 100 | 33 | 0 | 0 | 0 | 0 | 89 | 100 | 89 | 56 | 0 | 0 | 0 |
| U3_F45_B15 | 1.5 | 100 | 100 | 100 | 100 | 100 | 67 | 0 | 0 | 0 | 0 | 100 | 100 | 100 | 89 | 22 | 100 | 0 |
| U3_F45_B15 | 1.2 | 100 | 100 | 100 | 100 | 100 | 56 | 0 | 0 | 0 | 0 | 100 | 100 | 100 | 78 | 0 | 67 | 0 |
| U3_F45_B15 | 1.0 | 89 | 100 | 100 | 100 | 100 | 44 | 0 | 0 | 0 | 0 | 100 | 100 | 89 | 78 | 0 | 0 | 0 |
| U3_F45_B15 | 0.8 | 89 | 89 | 100 | 100 | 100 | 33 | 0 | 0 | 0 | 0 | 89 | 100 | 89 | 56 | 0 | 0 | 0 |
| U3_F45_B15 | 0.7 | 89 | 89 | 100 | 100 | 100 | 33 | 0 | 0 | 0 | 0 | 89 | 100 | 89 | 56 | 0 | 0 | 0 |

### E. Wrist axis / motion telemetry from the replay (identical across base variants): wrist axis world elevation p5/p50/p95 (deg), wrist ang speed p50/p95 (deg/s), axis sweep p50/p95, share sweep>60, az reversals/s, dq6 p50/p95, base-left ang speed p50/p95
| lane | stage | th40 elev p5/p50/p95 | th45 elev p5/p50/p95 | wrist ang speed p50/p95 | axis sweep p50/p95 | share sweep>60 | az reversals/s | dq6 p50/p95 (rad/s) | base cam ang speed p50/p95 |
|---|---|---|---|---|---|---|---|---|---|
| C_S2/left | stage2 | -52/-43/-36 | -57/-48/-41 | 84/159 | 61/127 | 52% | 10.49 | 0.59/1.78 | 27/47 |
| C_S2/left | stage3 | -53/-37/-27 | -58/-39/-29 | 86/403 | 70/258 | 61% | 4.65 | 0.81/2.92 | 31/56 |
| C_S2/left | stage4 | -55/-42/-25 | -60/-46/-30 | n/a (10 Hz) | | | | |  |
| C_S2/left | stage5 | -74/-61/-49 | -78/-66/-54 | n/a (10 Hz) | | | | |  |
| C_S2/right | stage2 | -48/-41/-35 | -53/-46/-40 | 95/179 | 59/127 | 50% | 11.44 | 0.55/1.74 | 23/37 |
| C_S2/right | stage3 | -49/-37/-25 | -53/-39/-26 | 75/365 | 57/204 | 47% | 2.61 | 1.46/3.17 | 30/59 |
| C_S2/right | stage4 | -79/-66/-36 | -80/-67/-38 | n/a (10 Hz) | | | | |  |
| C_S2/right | stage5 | -78/-62/-42 | -82/-67/-45 | n/a (10 Hz) | | | | |  |
| C_S21/left | stage2 | -49/-38/-29 | -54/-43/-34 | 98/211 | 75/150 | 63% | 12.04 | 1.00/2.52 | 25/39 |
| C_S21/left | stage3 | -39/-31/-22 | -43/-34/-25 | 71/292 | 54/168 | 44% | 5.60 | 0.74/2.93 | 29/52 |
| C_S21/left | stage4 | -52/-47/-34 | -57/-52/-38 | n/a (10 Hz) | | | | |  |
| C_S21/left | stage5 | -60/-53/-47 | -64/-58/-51 | n/a (10 Hz) | | | | |  |
| C_S21/right | stage2 | -51/-40/-30 | -56/-45/-35 | 112/174 | 73/135 | 64% | 8.76 | 0.98/2.64 | 30/58 |
| C_S21/right | stage3 | -56/-35/-25 | -61/-38/-28 | 89/228 | 71/161 | 58% | 2.53 | 1.45/3.05 | 29/59 |
| C_S21/right | stage4 | -74/-60/-47 | -76/-63/-47 | n/a (10 Hz) | | | | |  |
| C_S21/right | stage5 | -64/-52/-42 | -68/-57/-46 | n/a (10 Hz) | | | | |  |

### F. Static poses at the new reset posture (from the runs; label in JSON still says training_default)
- U3_F40 training_default_[0,0,0,0.25,0.5,1.57] q=[0.0, 0.0, 0.0, 0.0, -0.44, 1.57]: flange pitch 30.21, wrist RGB axis pitch -14.75 yaw 0.08, wrist RGB origin B [0.1205, 0.0323, 0.5658], TCP in RGB=False depth=True, on-axis enters RGB 0.1 m depth 0.075 m
- U3_F40 u3_reference_[0,0,0,0,0,1.57] q=[0,0,0,0,0,1.57]: flange pitch 5.0, wrist RGB axis pitch -39.96 yaw 0.1, wrist RGB origin B [0.2075, 0.0323, 0.5419], TCP in RGB=False depth=True, on-axis enters RGB 0.1 m depth 0.075 m
- U3_F45 training_default_[0,0,0,0.25,0.5,1.57] q=[0.0, 0.0, 0.0, 0.0, -0.52, 1.57]: flange pitch 34.79, wrist RGB axis pitch -15.16 yaw 0.08, wrist RGB origin B [0.1038, 0.0323, 0.5653], TCP in RGB=True depth=True, on-axis enters RGB 0.08 m depth 0.055 m
- U3_F45 u3_reference_[0,0,0,0,0,1.57] q=[0,0,0,0,0,1.57]: flange pitch 5.0, wrist RGB axis pitch -44.96 yaw 0.1, wrist RGB origin B [0.207, 0.0323, 0.5414], TCP in RGB=True depth=True, on-axis enters RGB 0.08 m depth 0.055 m
