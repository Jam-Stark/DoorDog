# TODO

- 以相同H9-b75 warm parents和seed0/1/2/3重新并行训练RNG-fixed H10 1024 env×75 batches；旧H10四格为confounded，不得用于任何policy比较。
- RNG-fixed natural screen首先认post-E3 contact dwell≥5、hinge≥0.10，再认E4；RIGHT与pre-E3 sampled actions必须保持parent exact。
- H10若失败：live-handle SE(3) DLS只能作为短程causal mechanics probe，结果必须标为oracle-assisted、不可作为policy verdict。
- 在同一 accepted checkpoint 上分别核对 raw LEFT/RIGHT 的 Stage3 press/unlatch、Stage5 与 E7，确认左右镜像 randomization 下的 bilateral goal；不得把 screen 结果外推为 held-out 或 hardware 证据。
- 当前只追踪上述 H10→screen→held-out fixed-side/bilateral eval→LEFT/RIGHT Stage5/E7 链路；其余改动待新证据或明确决策。
