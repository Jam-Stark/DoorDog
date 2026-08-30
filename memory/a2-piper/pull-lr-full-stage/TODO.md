# TODO

- 完成H12两个H9-b75 parent×primary/replica四格1024 env×75-batch训练与natural screen；训练/eval均使用同一task-space executor且hold oracle关闭。
- H12 science gate：两个lineage first-E3 distance≤0.04、opening alignment≥0.85、dwell median≥5；每parent至少一seed hinge≥0.10且pooled E4≥2，否则75关闭。
- 在同一 accepted checkpoint 上分别核对 raw LEFT/RIGHT 的 Stage3 press/unlatch、Stage5 与 E7，确认左右镜像 randomization 下的 bilateral goal；不得把 screen 结果外推为 held-out 或 hardware 证据。
- 当前只追踪H12 task-space policy→held-out fixed-side/bilateral eval→LEFT/RIGHT Stage5/E7链路；其余改动待新证据或明确决策。
