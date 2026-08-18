---
name: sim2sim-r6-attribution
scope: r6 behavior deliverables, Isaac self-eval, and cap-pinned attribution closure
status: r6_complete_e5_formal_pairing_still_open
last_updated: 2026-08-19 03:05 HKT
read_when:
  - interpreting the cap-pinned locomotion attribution or planning the formal Isaac paired producer
  - running any Isaac self-eval of the READY Student bundle
  - planning appearance/DR work based on the visual-magnitude effect
---

# Sim2sim r6 attribution round

The READY GRPO Student's "cap-pinned run without stopping" is a policy property, not a MuJoCo artifact: in its own Isaac environment (frozen commit a1972552, scratch clone with a declared env-gated dump patch) the clipped base-command norm is clip-saturated on 99.6% of steps with 0/1000 genuine base-still steps (4 exactly-zero rows at episode boundaries are post-reset zeroed buffers and were retracted). MuJoCo r5 shows the same profile (min 0.38-0.50, 0 base-still in 9000+ steps). Cross-backend verdict: `COMMAND_PROFILE_CONSISTENT_CAP_PINNED_IN_BOTH_BACKENDS`. Isaac aggregate: 150 episodes all `stage_overtime` at the 5 s stage-0 window, 2/150 reached stage1; goal_reached 0 — the 91.2%/512 training-time figure is a different protocol and must not be conflated.

Visual channel has a real systematic effect on command magnitude but is not sufficient to flip convergence: substituting real Isaac terminal frames (crude rotated triplet, typed EXPLORATORY_NON_PAIRED) cuts min command norm 0.495→0.235 with still 0 base-still steps; a flat-color brightness ladder is monotone (L0.60→0.453 ... L0.96→0.209, 400 steps, no stop). Nonvisual 81D obs surface is anchor-verified closed (`NONVISUAL_OBS_SURFACE_CLOSED`, t=0 analytic anchors exact, coordinate conventions anchored at distillation legged_robot_base.py:171/199). Joint kinematics sane (arm stage-0 |qvel| max 1.01 rad/s, deviation ≤0.047 rad; qacc ≤1947; measured/commanded speed ≈0.27).

Isaac self-eval recipe (reusable): git-clone the distillation ws into scratch, checkout bundle source_commit, `PYTHONPATH=<clone> CUDA_VISIBLE_DEVICES=<0-3> eval_agent_trl.py +checkpoint=<abs> +num_envs=4 ++env.config.save_rendering_dir=<scratch> ++simulator.config.render_results=true ++algo.config.eval.save_videos=true ++algo.config.eval.save_goal_reached_only=false` (+R6_ACTION_DUMP env var on the patched scratch for per-step action/command/obs dumps). num_envs must divide num_mini_batches=4; repo root must be on PYTHONPATH (scriptsFORhuman import); outputs land in clone `logs_eval/` and scratch. The formal paired producer (pin reset+door+seed, 200 Hz schema) remains unbuilt: `ATTEMPTED_SCOPED_DOWN`.

GPU discipline: co-tenant DepthADD DDP owns GPU5/6; one SIGKILL(137) of an r6 process coincided with its launch window (typed CO_TENANT_LAUNCH_WINDOW_SUSPECTED, retry survived). Scratch `/home/baoquanc/workspace/sim2sim_scratch_r6/` is registered for cleanup.

This entry is intentionally not added to `memory/a2-piper/MEMORY.md`; add routing only during owner merge.
