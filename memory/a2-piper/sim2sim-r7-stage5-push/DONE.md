---
name: sim2sim-r7-stage5-push-done
last_updated: 2026-08-20 16:31 HKT
---

# DONE

- Reproduced the Isaac training protocol three times: success 0.96875 (31/32), episode length ~615 steps — the user's 90% claim verified.
- Extracted the true reference profile from a full rollout dump (21,440 steps): stage chain timing and base-still statistics for 63 episodes.
- Proved the unlock: replaying the Isaac vision sequence into MuJoCo physics produces genuine base-still (min 0.071).
- Mapped and documented every failed live-vision correction path (appearance, markers, FOV, statistics matching, horizon, prime-release, channel split).
- Verified MuJoCo dynamics fidelity: tracking ratio 0.69 vs 0.70; open-loop drift 2.2 cm at the stop point.
- Retracted the broken eval-side Isaac reference (frozen vision + wrong episode contract) and the r6 C3 conclusion.
- Recorded the owner adjudication: C-B2H student has no visual randomization; the visual domain gap is policy-recipe-borne, not MuJoCo-pipeline-borne.
