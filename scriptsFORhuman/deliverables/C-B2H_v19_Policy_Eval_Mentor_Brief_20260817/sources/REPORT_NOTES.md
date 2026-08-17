# Report notes

- Audience: product stakeholders / 导师汇报。
- Scope: fixed-G2 C-B2H v19 true-Teacher eval、baseline Student eval、后续 GRPO step10 Student eval，以及一条 outcome 已验证的 baseline Student 成功视频。
- Chart map: `Policy Eval 成功率比较` asks how the true Teacher, baseline Student and GRPO step10 Student compare under the fixed-G2 protocol. It uses a native categorical `bar` chart over three reviewed policy-level rows (`policy`, `rate`, `success`, `total`) returned by the package-local SQLite query recorded in the artifact, a single blue palette root with direct category labels and no redundant legend, and supports the takeaway that Teacher is near ceiling while GRPO narrows but does not close the Student gap. Exact configuration and failure-stage values remain in tables; the embedded rollout video is the primary qualitative visual.
- The video is a single successful case and is not used to estimate aggregate success.
- Direct visibility metrics remain unavailable; camera/perception attribution is therefore UNKNOWN/INCONCLUSIVE.
