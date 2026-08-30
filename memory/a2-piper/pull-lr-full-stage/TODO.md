# TODO

- 完成已登记的 H7 recurrent-state nonlinear adapter seeds0–3 初始25-batch并screen。
- step25若LEFT E4仍0，仅当至少2 seeds的valid-hold hinge max达到0.10 rad才允许full-resume至75；否则停止H7。
- step75要求至少2/4 seeds出现LEFT E4且pooled≥4/64并通过K5/E2/RIGHT保护，才继续Stage4/E5→E7层与held-out fixed-side/bilateral eval。
- 在同一 accepted checkpoint 上分别核对 raw LEFT/RIGHT 的 Stage3 press/unlatch、Stage5 与 E7，确认左右镜像 randomization 下的 bilateral goal；不得把 screen 结果外推为 held-out 或 hardware 证据。
- 当前只追踪上述 n1024→screen→held-out fixed-side/bilateral eval→LEFT/RIGHT Stage5/E7 链路；其余改动待新证据或明确决策。
