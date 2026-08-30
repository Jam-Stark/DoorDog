# TODO

- full-resume H9两组same-parent/same-seed control/treatment到global batch75，保留optimizer、trainer与per-env E3 snapshot bank，再做natural fixed-side screen。
- batch75若两个treatment仍保持valid-hold hinge `<0.02 rad`且`0.02–0.105 rad` dwell无paired改善才停止；进入`0.105–0.25 rad` band则同步续到batch200。
- batch200正式科学门：两个treatment各至少1 LEFT E4，且pooled E4至少比controls多2才admit；snapshot数量或E3 occupancy不能替代E4。
- H9通过后才做seed2/3 replication或Stage4/E5→E7层；仅单parent E4只记录behavior hint，不promotion。充分预算后仍失败才进入H10 post-E3 phase-separated actor主轴。
- 在同一 accepted checkpoint 上分别核对 raw LEFT/RIGHT 的 Stage3 press/unlatch、Stage5 与 E7，确认左右镜像 randomization 下的 bilateral goal；不得把 screen 结果外推为 held-out 或 hardware 证据。
- 当前只追踪上述 H9 matched pair→screen→held-out fixed-side/bilateral eval→LEFT/RIGHT Stage5/E7 链路；其余改动待新证据或明确决策。
