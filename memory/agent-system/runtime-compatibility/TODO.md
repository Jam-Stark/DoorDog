# TODO

- 2026-07-11 01:29 HKT - 当 runtime 能显式暴露 effective child role/model/effort 且 child read-only command runner 可正常执行时，重跑 fresh project-scoped `role_probe` 并补齐 child-owned before/after snapshot；任一 mismatch 必须 fail fast，production activation 在完整 PASS 前保持 disabled。
