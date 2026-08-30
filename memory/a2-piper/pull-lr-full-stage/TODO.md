# TODO

- full-resume H13 r2四seed从global75到200，保留optimizer/trainer/reset bank；step200 fixed-side screen必须双侧进入hinge≥0.105并产生E4，否则关闭H13。
- 在同一 accepted checkpoint 上分别核对 raw LEFT/RIGHT 的 Stage3 press/unlatch、Stage5 与 E7，确认左右镜像 randomization 下的 bilateral goal；不得把 screen 结果外推为 held-out 或 hardware 证据。
- 当前只追踪H13 global200 clean shared Stage3 controller→bilateral E4→Stage4/5 successor链路；其余改动待新证据或明确决策。
