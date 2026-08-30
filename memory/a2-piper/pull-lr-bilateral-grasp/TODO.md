# TODO

- 将 exact LR asset distribution 接入 full pull Stage3–5 training/eval，验证两侧开门、送门过身、release 和 through；当前为 `NOT_RUN`。
- 在不牺牲 strict K5 的前提下降低 raw LEFT overforce，并提高 raw RIGHT clean-K；这是 quality 优化，不是当前 winner admission blocker。
- push branch 若复用 selector，必须在其真实 resolved config/runtime 下单独验证，不从 pull 结果外推。
