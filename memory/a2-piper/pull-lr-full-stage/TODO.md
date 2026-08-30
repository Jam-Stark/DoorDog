# TODO

- 完成已登记的 H4 arm-only n1024 cells并做 fixed-side screen；按parent lineage分别报告，不得用pooled结果掩盖某个parent失败。
- H4必须严格保护RIGHT、LEFT Stage0–2、base/gripper和所有非Stage3 carrier mean；step25若LEFT handle≥0.6/E3不超过Gate-A parent或仍无E4，停止arm residual，不扩base或reward scale。
- H4若通过保护与creation指标，再继续 held-out fixed-side eval 与 bilateral eval。
- 在同一 accepted checkpoint 上分别核对 raw LEFT/RIGHT 的 Stage3 press/unlatch、Stage5 与 E7，确认左右镜像 randomization 下的 bilateral goal；不得把 screen 结果外推为 held-out 或 hardware 证据。
- 当前只追踪上述 n1024→screen→held-out fixed-side/bilateral eval→LEFT/RIGHT Stage5/E7 链路；其余改动待新证据或明确决策。
