# TODO

- 完成H13 r1同一bilateral acquisition parent×seed0/1/2/3四格1024 env×75-batch训练与fixed-side natural screen；每格exact512 LEFT/512 RIGHT。
- H13 batch75 gate：至少3/4 seeds双侧同时first-E3 distance≤0.04、alignment≥0.85、dwell≥5，且LEFT/RIGHT都出现hinge≥0.105；canonical失败不续200。
- 在同一 accepted checkpoint 上分别核对 raw LEFT/RIGHT 的 Stage3 press/unlatch、Stage5 与 E7，确认左右镜像 randomization 下的 bilateral goal；不得把 screen 结果外推为 held-out 或 hardware 证据。
- 当前只追踪H13 clean shared Stage3 controller→bilateral E4→Stage4/5 successor链路；其余改动待新证据或明确决策。
