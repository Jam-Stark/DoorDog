# TODO

- H11只新增raw LEFT Stage3 coupled-SE(3) pose-quality reward，继续训练可修改pre-E3的H7 nonlinear adapter；不再使用H9 E3-only reset或post-E3 head。
- H11技术门：RIGHT reward恒0、LEFT非Stage3恒0、reward实际激活；natural science gate为first-E3 distance≤0.04m、opening alignment≥0.85、continuous contact≥5、hinge≥0.10/E4。
- 在同一 accepted checkpoint 上分别核对 raw LEFT/RIGHT 的 Stage3 press/unlatch、Stage5 与 E7，确认左右镜像 randomization 下的 bilateral goal；不得把 screen 结果外推为 held-out 或 hardware 证据。
- 当前只追踪上述 H11 learned pose-follow→held-out fixed-side/bilateral eval→LEFT/RIGHT Stage5/E7 链路；其余改动待新证据或明确决策。
