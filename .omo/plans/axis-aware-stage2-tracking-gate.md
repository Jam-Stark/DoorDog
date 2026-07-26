# axis-aware-stage2-tracking-gate - Work Plan

## TL;DR (For humans)
<!-- Fill this LAST, after the detailed plan below is written, so it summarizes the REAL plan. -->
<!-- Plain English for a non-engineer: NO file paths, NO todo numbers, NO wave/agent/tool names. -->

**What you'll get:** Stage2 grasp tracking 从纯 L2 distance 改为按 gripper 开合轴 (Y) 和 approach 轴 (X/Z) 分解的 axis-aware reward + close gate。Policy 会在 close 前先被引导把 handle 居中到两指中间，而不是只追 L2 距离。

**Why this approach:** FacePos70 证据显示 gripper 到 handle L2 距离仅 2.5cm 但 Y/opening-axis 偏 2.2cm，导致单指接触、close gate 永远不触发。L2 reward 无法区分"沿 approach 还没到"和"opening-axis 偏一侧"，所以 policy 停在 handle 旁边。分解成 axis-aware 后，Y 偏差会被单独约束。

**What it will NOT do:** 不放松 close gate 的总阈值（不回到 0.03）；不改 stage transition / complete predicate / observation / grasp_target geometry / pregrasp offset；不改 stage0-2 exp config。

**Effort:** Short (4 todos, 3 files)
**Risk:** Low — 纯 reward/gate 逻辑改动，不改物理/阶段/观测；阈值可调，reversible
**Decisions to sanity-check:** y_tol=0.012 / z_tol=0.015 / x_tol=0.02（基于 handle_radius）；reward scale=3.0 / std=0.05

Your next move: approve to start execution, or request changes. Full execution detail follows below.

---

> TL;DR (machine): <1 line - effort, risk, deliverables>

## Scope
### Must have
1. Two new stage2 axis-aware tracking reward functions in `door_open_a2_base.py`:
   - `_reward_a2_stage2_handle_center_y()`: drives `abs(target_pos_source[:, 0, 1])` → 0 (opening-axis centering)
   - `_reward_a2_stage2_handle_approach_xz()`: drives `abs(target_pos_source[:, 0, 0])` and `abs(target_pos_source[:, 0, 2])` → 0 (approach + other lateral)
   - Both gated: `STAGE_GRASP` AND NOT close_gate (handle outside close-gate region)
2. Axis-aware close gate: replace `norm(target_pos_source[:, 0, :]) < 0.015` with per-axis `abs` checks in `_get_a2_stage2_close_reward_gate()`
3. Config keys for axis thresholds in `door_open_a2_base.yaml` (tunable without code change)
4. Reward scale + curriculum entries in `reward_door_open_a2_base.yaml`
5. `py_compile` + Hydra compose + no-sim formula sanity verification
6. Memory update for `stage0-2-grasp-terminal` and `reward-implementation-goal` entries

### Must NOT have (guardrails, anti-slop, scope boundaries)
- Do NOT relax or remove the existing `a2_stage2_close_command` / `a2_stage2_close_progress` rewards or their gate
- Do NOT change `_stage_2_to_complete_condition()` (contact history gate stays as-is)
- Do NOT change stage1→2 advance condition or stage transition logic
- Do NOT change observation config (`gripper_handle_transform` already contains both targets)
- Do NOT change `A2_PREGRASP_OFFSET` or grasp_target geometry
- Do NOT change reset, camera, render timing, or action semantics
- Do NOT add fallback / default values that silently mask missing config keys (fail-fast)
- Do NOT change stage0-2 exp config (`door_open_a2_base_stage0_2_grasp_terminal_lstm.yaml`) — new rewards auto-active via shared reward YAML

## Verification strategy
> Zero human intervention - all verification is agent-executed.
- Test decision: tests-after (py_compile + Hydra compose + no-sim formula sanity; no IsaacSim runtime in this round)
- Evidence: .omo/evidence/task-3-axis-aware-stage2-tracking-gate.<ext>

## Execution strategy
### Parallel execution waves
> Wave 1: config changes (2 files, independent). Wave 2: code changes (1 file, depends on wave 1 config keys). Wave 3: verify + memory.

### Dependency matrix
| Todo | Depends on | Blocks | Can parallelize with |
| --- | --- | --- | --- |
| 1 (env config thresholds) | — | 2, 3 | 2 (reward YAML) |
| 2 (reward YAML entries) | — | 3 | 1 (env config) |
| 3 (code: gate + rewards) | 1, 2 | 4 | — |
| 4 (verify + memory) | 3 | — | — |

## Todos
<!-- APPEND TASK BATCHES BELOW THIS LINE WITH edit/apply_patch - never rewrite the headers above. -->

- [ ] 1. Add axis-aware close-gate threshold config keys to env YAML
  What to do: Add three new config keys to `gr00t/rl/config/env/door_open_a2_base.yaml` under the `env.config` section (near existing `stage2_grasp_contact_history_length: 5` at line 98). Keys:
  ```yaml
  stage2_close_gate_y_tol: 0.012
  stage2_close_gate_z_tol: 0.015
  stage2_close_gate_x_tol: 0.02
  ```
  These are the per-axis tolerances (in meters) for the axis-aware close gate. y_tol=0.012 ≈ handle_radius (0.011-0.015m), ensuring handle is centered between gripper fingers before close rewards activate. z_tol=0.015 = approach depth tolerance. x_tol=0.02 = other lateral tolerance.
  Must NOT do: Do NOT change existing config values. Do NOT add comments explaining rationale (keep YAML clean). Do NOT add these to stage0-2 exp config overrides.
  Parallelization: Wave 1 | Blocked by: — | Blocks: 3 | Can parallelize with: 2
  References: `gr00t/rl/config/env/door_open_a2_base.yaml:98` (existing `stage2_grasp_contact_history_length`), `gr00t/rl/envs/door/door_open_a2_base.py:642-678` (gate consumer)
  Acceptance criteria: `grep -n "stage2_close_gate_" gr00t/rl/config/env/door_open_a2_base.yaml` returns 3 lines with the specified values.
  QA scenarios: `python3 -c "import yaml; d=yaml.safe_load(open('gr00t/rl/config/env/door_open_a2_base.yaml')); c=d['env']['config']; assert c['stage2_close_gate_y_tol']==0.012; assert c['stage2_close_gate_z_tol']==0.015; assert c['stage2_close_gate_x_tol']==0.02; print('OK')"` — Evidence: .omo/evidence/task-1-axis-aware-stage2-tracking-gate.txt
  Commit: Y | feat(reward): add axis-aware close-gate threshold config keys

- [ ] 2. Add new reward scales and curriculum entries to reward YAML
  What to do: Add two new reward scale entries and two `reward_penalty_reward_names` entries to `gr00t/rl/config/rewards/wbmanip/reward_door_open_a2_base.yaml`.
  In `reward_scales` section (after `a2_stage2_close_progress: 0.5` at line 40), add:
  ```yaml
  a2_stage2_handle_center_y: 3.0
  a2_stage2_handle_approach_xz: 3.0
  ```
  In `reward_penalty_reward_names` list (after `"a2_stage2_close_progress"` at line 121), add:
  ```yaml
  "a2_stage2_handle_center_y",
  "a2_stage2_handle_approach_xz",
  ```
  Must NOT do: Do NOT change existing reward scales. Do NOT remove any existing entries from `reward_penalty_reward_names`. Do NOT add to stage0-2 exp config.
  Parallelization: Wave 1 | Blocked by: — | Blocks: 3 | Can parallelize with: 1
  References: `gr00t/rl/config/rewards/wbmanip/reward_door_open_a2_base.yaml:39-40` (existing stage2 close rewards), `gr00t/rl/config/rewards/wbmanip/reward_door_open_a2_base.yaml:120-121` (existing curriculum entries)
  Acceptance criteria: `grep -n "a2_stage2_handle" gr00t/rl/config/rewards/wbmanip/reward_door_open_a2_base.yaml` returns 4 lines (2 in reward_scales, 2 in reward_penalty_reward_names).
  QA scenarios: `python3 -c "import yaml; d=yaml.safe_load(open('gr00t/rl/config/rewards/wbmanip/reward_door_open_a2_base.yaml')); s=d['rewards']['reward_scales']; assert s['a2_stage2_handle_center_y']==3.0; assert s['a2_stage2_handle_approach_xz']==3.0; n=d['rewards']['reward_penalty_reward_names']; assert 'a2_stage2_handle_center_y' in n; assert 'a2_stage2_handle_approach_xz' in n; print('OK')"` — Evidence: .omo/evidence/task-2-axis-aware-stage2-tracking-gate.txt
  Commit: Y | feat(reward): add axis-aware stage2 tracking reward scales and curriculum entries

- [ ] 3. Implement axis-aware close gate + two new stage2 tracking reward functions
  What to do: In `gr00t/rl/envs/door/door_open_a2_base.py`, make three changes:

  **Change A — Modify `_get_a2_stage2_close_reward_gate()` (lines 642-678):**
  Replace the L2 norm gate:
  ```python
  handle_distance = torch.linalg.norm(target_pos_source[:, 0, :], dim=-1)
  return (
      (stage_buf == self.STAGE_GRASP)
      & (handle_distance < 0.015)
      & (opening_alignment >= 0.9)
      & (approach_alignment >= 0.9)
  )
  ```
  With axis-aware gate:
  ```python
  handle_pos_source = target_pos_source[:, 0, :]
  y_tol = float(self.config.stage2_close_gate_y_tol)
  z_tol = float(self.config.stage2_close_gate_z_tol)
  x_tol = float(self.config.stage2_close_gate_x_tol)
  return (
      (stage_buf == self.STAGE_GRASP)
      & (handle_pos_source[:, 1].abs() < y_tol)
      & (handle_pos_source[:, 2].abs() < z_tol)
      & (handle_pos_source[:, 0].abs() < x_tol)
      & (opening_alignment >= 0.9)
      & (approach_alignment >= 0.9)
  )
  ```
  Add fail-fast for missing config keys: if any of `stage2_close_gate_y_tol`, `stage2_close_gate_z_tol`, `stage2_close_gate_x_tol` is not in `self.config`, raise `RuntimeError` with the missing key name. Do NOT use `.get()` with defaults.

  **Change B — Add `_reward_a2_stage2_handle_center_y()` after `_reward_a2_stage2_close_progress()` (~line 1046):**
  ```python
  @StagedTaskBase.effective_in_stage(STAGE_GRASP)
  def _reward_a2_stage2_handle_center_y(self):
      """Axis-aware centering: drive handle Y (opening axis) to 0 in gripper source frame.
      Only active in stage2 outside the close gate; inside the gate, a2_stage2_close_* take over.
      """
      if not self._use_a2_base:
          raise RuntimeError("a2_stage2_handle_center_y is only defined for A2 Piper configs.")
      data = self._get_a2_gripper_handle_frame_transformer().data
      target_pos_source = getattr(data, "target_pos_source", None)
      if (target_pos_source is None or target_pos_source.ndim != 3
              or tuple(target_pos_source.shape) != (self.num_envs, 2, 3)):
          shape = None if target_pos_source is None else tuple(target_pos_source.shape)
          raise RuntimeError(
              "a2_stage2_handle_center_y requires target_pos_source shape "
              f"({self.num_envs}, 2, 3); got {shape}."
          )
      gate = self._get_a2_stage2_close_reward_gate()
      handle_y = target_pos_source[:, 0, 1].abs()
      reward = self._tracking_reward_util(
          handle_y, std=0.05, target=0.0, scale=1.0, offset=0.0
      )
      return reward * (~gate).float()
  ```

  **Change C — Add `_reward_a2_stage2_handle_approach_xz()` after Change B:**
  ```python
  @StagedTaskBase.effective_in_stage(STAGE_GRASP)
  def _reward_a2_stage2_handle_approach_xz(self):
      """Axis-aware approach: drive handle X (lateral) and Z (approach depth) to 0.
      Only active in stage2 outside the close gate; inside the gate, a2_stage2_close_* take over.
      """
      if not self._use_a2_base:
          raise RuntimeError("a2_stage2_handle_approach_xz is only defined for A2 Piper configs.")
      data = self._get_a2_gripper_handle_frame_transformer().data
      target_pos_source = getattr(data, "target_pos_source", None)
      if (target_pos_source is None or target_pos_source.ndim != 3
              or tuple(target_pos_source.shape) != (self.num_envs, 2, 3)):
          shape = None if target_pos_source is None else tuple(target_pos_source.shape)
          raise RuntimeError(
              "a2_stage2_handle_approach_xz requires target_pos_source shape "
              f"({self.num_envs}, 2, 3); got {shape}."
          )
      gate = self._get_a2_stage2_close_reward_gate()
      handle_x = target_pos_source[:, 0, 0].abs()
      handle_z = target_pos_source[:, 0, 2].abs()
      x_reward = self._tracking_reward_util(
          handle_x, std=0.05, target=0.0, scale=1.0, offset=0.0
      )
      z_reward = self._tracking_reward_util(
          handle_z, std=0.05, target=0.0, scale=1.0, offset=0.0
      )
      return ((x_reward + z_reward) / 2.0).clamp(max=1.0) * (~gate).float()
  ```

  Must NOT do: Do NOT change `_stage_2_to_complete_condition()`, stage transition logic, observation config, or action semantics. Do NOT add `as any` / type suppression. Do NOT use `.get()` with silent defaults for the new config keys — fail-fast. Do NOT change the existing `a2_stage2_close_command` / `a2_stage2_close_progress` rewards. Do NOT change the `@StagedTaskBase.effective_in_stage` decorator pattern. Do NOT use try/except to mask errors.
  Parallelization: Wave 2 | Blocked by: 1, 2 | Blocks: 4 | Can parallelize with: —
  References:
  - `gr00t/rl/envs/door/door_open_a2_base.py:642-678` (`_get_a2_stage2_close_reward_gate` — modify)
  - `gr00t/rl/envs/door/door_open_a2_base.py:944-1046` (`_reward_a2_stage2_close_command` / `_reward_a2_stage2_close_progress` — pattern reference for new rewards)
  - `gr00t/rl/envs/door/door_open_a2_base.py:611-640` (`_get_a2_gripper_handle_orientation_metrics` — orientation metrics pattern)
  - `gr00t/rl/envs/door/door_open_a2_base.py:230-238` (stage constants, `A2_PREGRASP_OFFSET`)
  - Axis semantics confirmed from FacePos70: target_pos_source[:, 0, 0]=X lateral, [:, 0, 1]=Y opening, [:, 0, 2]=Z approach
  Acceptance criteria: `python3 -m py_compile gr00t/rl/envs/door/door_open_a2_base.py` exits 0. `grep -n "_reward_a2_stage2_handle_center_y\|_reward_a2_stage2_handle_approach_xz" gr00t/rl/envs/door/door_open_a2_base.py` returns 2 def lines. `grep -n "stage2_close_gate_y_tol\|stage2_close_gate_z_tol\|stage2_close_gate_x_tol" gr00t/rl/envs/door/door_open_a2_base.py` returns lines reading the config keys.
  QA scenarios:
  - happy: `python3 -m py_compile gr00t/rl/envs/door/door_open_a2_base.py` → exit 0. Evidence: .omo/evidence/task-3a-axis-aware-stage2-tracking-gate.txt
  - failure: verify no `try/except` or `.get()` with default on the three new config keys by `grep -n "get.*stage2_close_gate" gr00t/rl/envs/door/door_open_a2_base.py` returning empty (no silent fallback). Evidence: .omo/evidence/task-3b-axis-aware-stage2-tracking-gate.txt
  Commit: Y | feat(reward): implement axis-aware stage2 close gate and tracking rewards

- [ ] 4. Static verification + memory update
  What to do: Run three verification checks, then update memory.
  **Verification:**
  1. `py_compile`: `/home/baoquanc/anaconda3/envs/isaaclab/bin/python -m py_compile gr00t/rl/envs/door/door_open_a2_base.py`
  2. Hydra compose (both configs): verify the new reward scales resolve and the new config keys appear:
     - Full 6-stage: compose `door_open_a2_base_lstm` and grep for `a2_stage2_handle_center_y` in resolved scales
     - Stage0-2: compose `door_open_a2_base_stage0_2_grasp_terminal_lstm` and verify same
  3. No-sim formula sanity: write a small Python script that creates synthetic `target_pos_source` tensors and verifies:
     - `_tracking_reward_util(abs([0.0]), std=0.05, target=0)` ≈ max reward (handle centered)
     - `_tracking_reward_util(abs([0.022]), std=0.05, target=0)` < max reward (FacePos70 terminal Y=2.2cm → partial reward)
     - axis-aware gate: `[0.0, 0.0, 0.0]` → True (all within tol); `[0.001, 0.022, 0.0]` → False (Y exceeds y_tol)
  **Memory update:** Update two memory entries:
  - `memory/a2-piper/stage0-2-grasp-terminal/description.md`: add entry under Current Decision recording the axis-aware close gate + tracking rewards change, with rationale (FacePos70 showed L2 norm gate + L2 reward couldn't distinguish lateral offset from approach offset)
  - `memory/a2-piper/stage0-2-grasp-terminal/DONE.md`: add DONE entry with timestamp
  - `memory/a2-piper/reward-implementation-goal/description.md`: add entry under Current Decision recording the two new reward terms
  - `memory/a2-piper/reward-implementation-goal/DONE.md`: add DONE entry
  Must NOT do: Do NOT run IsaacSim runtime (no GPU/training in this round). Do NOT change reward YAML or env config in this todo. Do NOT git commit.
  Parallelization: Wave 3 | Blocked by: 3 | Blocks: — | Can parallelize with: —
  References: All files from todos 1-3. Memory files: `memory/a2-piper/stage0-2-grasp-terminal/{description.md,DONE.md}`, `memory/a2-piper/reward-implementation-goal/{description.md,DONE.md}`
  Acceptance criteria: py_compile exits 0; Hydra compose resolves new keys; no-sim script prints expected values; memory files updated with new entries.
  QA scenarios:
  - happy: all 3 verification checks pass; memory files have new timestamped entries. Evidence: .omo/evidence/task-4-axis-aware-stage2-tracking-gate.txt
  - failure: py_compile or compose fails → report error, do not proceed to memory update. Evidence: .omo/evidence/task-4-fail-axis-aware-stage2-tracking-gate.txt
  Commit: Y | docs(memory): record axis-aware stage2 tracking reward and gate change

## Final verification wave
> Runs in parallel after ALL todos. ALL must APPROVE. Surface results and wait for the user's explicit okay before declaring complete.
- [ ] F1. Plan compliance audit
- [ ] F2. Code quality review
- [ ] F3. Real manual QA
- [ ] F4. Scope fidelity

## Commit strategy
- Each todo commits independently with conventional commit format
- Todo 1: `feat(reward): add axis-aware close-gate threshold config keys`
- Todo 2: `feat(reward): add axis-aware stage2 tracking reward scales and curriculum entries`
- Todo 3: `feat(reward): implement axis-aware stage2 close gate and tracking rewards`
- Todo 4: `docs(memory): record axis-aware stage2 tracking reward and gate change`
- Todos 1+2 can be squashed if same author prefers; todo 3 must be separate (code change); todo 4 must be separate (memory only)
- Do NOT push

## Success criteria
1. `_get_a2_stage2_close_reward_gate()` uses per-axis `abs()` checks instead of L2 norm
2. Two new reward functions registered and active in stage2 outside close gate
3. Config keys tunable via YAML without code change
4. `py_compile` passes; Hydra compose resolves new keys in both full and stage0-2 configs
5. No-sim formula sanity confirms: centered handle → max reward; FacePos70-like Y=2.2cm offset → partial reward; gate rejects offset exceeding y_tol
6. Memory entries updated with timestamped records
