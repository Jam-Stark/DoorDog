# TODO

- H15 native bilateral 256-env×5-batch runtime smoke已通过null-checkpoint、全actor/RMS可训练、exact 128/128 side与batch5 checkpoint门；登记并四卡并行训练4个acquisition seeds到global250。
- 在同一 accepted checkpoint 上分别核对 raw LEFT/RIGHT 的 Stage3 press/unlatch、Stage5 与 E7，确认左右镜像 randomization 下的 bilateral goal；不得把 screen 结果外推为 held-out 或 hardware 证据。
- 当前只追踪H15 native bilateral全策略→双侧E4→Stage4/5链路；H13/H14不再续训，其余改动待新证据或明确决策。
