# TODO

- H15四个随机初始化seed已在GPU0–3/tmux中并行运行；每个单进程不中断到global1500并保存25-step checkpoints，禁止把中途checkpoint resume误写成bank-preserving continuation。
- 在同一 accepted checkpoint 上分别核对 raw LEFT/RIGHT 的 Stage3 press/unlatch、Stage5 与 E7，确认左右镜像 randomization 下的 bilateral goal；不得把 screen 结果外推为 held-out 或 hardware 证据。
- 当前只追踪H15 native bilateral全策略→双侧E4→Stage4/5链路；H13/H14不再续训，其余改动待新证据或明确决策。
