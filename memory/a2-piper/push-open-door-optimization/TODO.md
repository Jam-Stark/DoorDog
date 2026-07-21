# TODO

- 2026-07-21 22:56 HKT - 下一步启动matched base_v16 A/B：A=M29+M30+M31、显式mass`80–120kg`；B=完整M29–M32、mass`80–160kg`。两组均使用v15 selected step2500 `policy_only`、seed0、4 ranks×1024 env/rank、global batch4096、2500 batches、save250；除`experiment_name`与`env.config.a2_door_weight_range`上界外resolved contract必须一致。该A/B仅隔离M32 mass轴，不产生M29/M30/M31单因素因果结论。
- 2026-07-21 22:56 HKT - A/B中点eval在500/1000/1500/2000执行；endpoint对候选release跑canonical + 3-seed 48门 + render（至少一个≥150kg env与一个低把手env），用schema-v2 M33 reporter判读：canonical goal≥15/16、pooled≥46/48、低桶`|pitch|>0.1`使用率<30%、高桶能力不退、hinge@release p50≥1.4、post-release body contact≤10/48且force p95<80N、pre-crossing bilateral/coasting/over-force、mass重桶goal≥2/3、crossing-while-holding≥15/16。
- 2026-07-21 22:56 HKT - 首次live run必须保存实际door mass histogram与launcher exact exit status/finished marker；现有v16 smoke目录不能独立证明这两项。远期项继续以`scriptsFORhuman/a2_piper_longterm_TODO.md`为准：左右镜像、真实Piper限位、in/out与student均保持separate future scope；M23 scripted 108-cell grid仍NOT RUN。
