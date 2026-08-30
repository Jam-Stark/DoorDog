# TODO

- 以H7 seed0/1 step25为parent，完成两组same-parent/same-seed的gate-H control与gate-J treatment，各1024 env×25 batches。
- H9两个treatment必须各至少1 LEFT E4，且pooled E4至少比controls多2才admit；pooled E4=0立即停止该curriculum，snapshot数量或E3 occupancy不能替代E4。
- H9通过后才做seed2/3 replication或Stage4/E5→E7层；仅单parent E4只记录behavior hint，不promotion。
- 在同一 accepted checkpoint 上分别核对 raw LEFT/RIGHT 的 Stage3 press/unlatch、Stage5 与 E7，确认左右镜像 randomization 下的 bilateral goal；不得把 screen 结果外推为 held-out 或 hardware 证据。
- 当前只追踪上述 H9 matched pair→screen→held-out fixed-side/bilateral eval→LEFT/RIGHT Stage5/E7 链路；其余改动待新证据或明确决策。
