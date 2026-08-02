# C-B2H Dual-Raw Shared-Encoder Feature Fusion

## Implementation Guidance for Dual D435i Manipulation Views plus the OEM A2 Head Context View

**Repository:** `Jam-Stark/DoorDog`
**Source branch:** `codex/a2-v13-student-distillation-20260717_2103`
**Reviewed commit:** `57b8eda3d500d5778eb9394d7fbc49c5aa3b8a63`
**Recommended architecture ID:** `C-B2H-DUALRAW-SHAREDENC-TOEIN20-V19`
**Teacher target:** an explicitly sealed, user-selected `base_v19` checkpoint from the mainline `A2_Piper` branch
**Scope:** Student observation, encoder, feature fusion, runtime, distillation admission, and evaluation design. Stage 5 handle visibility is intentionally outside this document.

---

## 1. Revised Decision

The OEM A2 Head camera should **not** be removed from the Student architecture.

The earlier dual-D435i-only recommendation was intended to isolate the smallest possible experiment and avoid mixing the panorama problem with a third camera. That isolation is useful as an ablation, but it is not the strongest production architecture for A2+Piper.

The three views have complementary roles:

| Camera               | Primary role                                                                                                             |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| Left portrait D435i  | Manipulation workspace, handle retention, left-side recovery from arm occlusion                                          |
| Right portrait D435i | Manipulation workspace, handle retention, right-side recovery from arm occlusion                                         |
| OEM A2 Head          | Level forward context, door-frame orientation, floor and obstacle context, base heading, approach direction and recovery |

The dual D435i pair is pitched upward by 60 degrees and yawed outward symmetrically by 20 degrees. That makes it suitable for retaining the handle and Piper workspace over a wide lateral range, but it is not an ideal sole source for level forward navigation context. The OEM Head camera is level, fixed to the official A2 frame, and has a substantially wider horizontal field of view.

Unitree documents that A2 has one head optical camera with a published field of view of approximately `132° H × 77° V` and a maximum stream mode of `2568×1448 at 15 fps`. A2 also has a lidar as part of its standard perception hardware.

Therefore:

> The two D435i cameras should form the manipulation branch, while the OEM A2 Head camera should form a separate context branch. All three views should be fused at the feature level. None of them should be panorama-stitched for the Student.

The A2 Head RGB stream can help the policy reason about collision context and direction, but it must not be treated as a safety-certified collision sensor. Low-level collision prevention, emergency stopping, and obstacle safety should remain outside the Student policy and continue to use the A2 platform’s lidar and safety stack.

---

## 2. Evidence Boundary

### 2.1 Source facts

The committed TOEIN20 configuration uses:

```text
Left D435i:
  xyz  = [0.215, +0.095, 0.165] m
  RPY  = [0, -60, -20] deg

Right D435i:
  xyz  = [0.215, -0.095, 0.165] m
  RPY  = [0, -60, +20] deg
```

The pair retains the `190 mm` baseline, changes the optical-axis separation to `40°`, and reduces the nominal far-field overlap to approximately `2.5°`.

The committed OEM A2 Head diagnostic configuration uses:

```text
xyz  = [0.3381, +0.0336, 0.0525] m
RPY  = [0, 0, 0] deg
wxyz = [1, 0, 0, 0]
```

The current TOEIN20 panorama remains visually rejected. Its wider canvas increased the empty-pixel fraction and did not remove ghosting, tearing, or holes. That result rejects the current panorama renderer, not the raw camera geometry or a feature-level architecture.

### 2.2 Derived conclusion

The D435i pair and OEM Head camera solve different observability problems:

* D435i pair: handle, fingers, Piper arm, door-panel interaction.
* OEM Head: level forward corridor, frame alignment, gross yaw, floor and obstacle relation.

The pair should therefore not compete for a single image canvas. Their features should be fused hierarchically.

### 2.3 Inference requiring ablation

It is reasonable to expect the OEM Head feature to reduce:

* door-frame and wall contact;
* base heading error;
* unnecessary lateral correction;
* loss of global orientation when the D435i images are dominated by Piper and the handle.

That benefit is not yet proven by a Student policy. It must be verified against a dual-D435i-only ablation using the same v19 Teacher, initialization, seed set, and training budget.

---

# 3. Final Camera Architecture

## 3.1 Physical and simulated camera contract

### Left D435i manipulation view

```yaml
parent: trunk
position_m: [0.215, 0.095, 0.165]
rotation_wxyz:
  [0.852868532, -0.086824089, -0.492403877, -0.150383733]
effective_rpy_deg: [0.0, -60.0, -20.0]
convention: world
physical_orientation: portrait_plus90_deg
policy_resolution: [384, 216]   # height, width
rgb_fov_hv_deg: [42.5, 69.4]   # portrait effective world coverage
```

### Right D435i manipulation view

```yaml
parent: trunk
position_m: [0.215, -0.095, 0.165]
rotation_wxyz:
  [0.852868532, 0.086824089, -0.492403877, 0.150383733]
effective_rpy_deg: [0.0, -60.0, 20.0]
convention: world
physical_orientation: portrait_plus90_deg
policy_resolution: [384, 216]
rgb_fov_hv_deg: [42.5, 69.4]
```

### OEM A2 Head context view

```yaml
parent: trunk
position_m: [0.3381, 0.0336, 0.0525]
rotation_wxyz: [1.0, 0.0, 0.0, 0.0]
effective_rpy_deg: [0.0, 0.0, 0.0]
convention: world
policy_resolution: [136, 384]
published_fov_hv_deg: [132.0, 77.0]
role: level_forward_context
```

The A2 Head must remain at the official level pose. It is not part of the D435i pose search.

The head representation in IsaacLab remains a pinhole approximation of the published FoV. Real deployment requires an actual intrinsic/distortion calibration and a deterministic rectification map. The Unitree quick-start “calibration” procedure concerns joint-limit calibration rather than camera intrinsic or extrinsic calibration, so it cannot substitute for a camera calibration procedure.

---

## 3.2 Camera roles by task phase

| Phase              | Left/right D435i                               | OEM A2 Head                                             |
| ------------------ | ---------------------------------------------- | ------------------------------------------------------- |
| Reset and approach | Handle search and upper manipulation region    | Main door, frame, floor, approach heading and obstacles |
| Staging            | Handle lateral position, Piper alignment       | Base-to-door orientation and frame centering            |
| Pregrasp           | Handle, gripper and arm geometry               | Global position and collision context                   |
| Finger close       | Primary observation                            | Secondary context                                       |
| Unlatch/open       | Handle, fingers, local panel motion            | Door-frame and whole-body movement direction            |
| Swing              | Arm/handle retention from complementary angles | Base motion, frame clearance and forward path           |

A2 body height can be adjusted over approximately `0.3–0.5 m`, so camera validation and randomization must cover that range rather than assuming one fixed trunk height.

---

# 4. Student Observation Contract

## 4.1 Low-dimensional observation

The existing deployable proprioceptive observation remains unchanged:

```text
actor_obs: 81D
```

No door pose, stage, handle transform, privileged collision geometry, or object state is added.

## 4.2 Manipulation image tensor

The two raw D435i views are transported as one channel-stacked tensor:

```text
vision_obs:
  rollout shape:  [B, 384, 216, 6]
  training shape: [B, T, 384, 216, 6]
  dtype in observation/storage: float32
```

Channel order is frozen:

```text
channels 0:3 = left D435i RGB
channels 3:6 = right D435i RGB
```

Flattened dimension:

[
384 \times 216 \times 6 = 497,664
]

This happens to equal the existing C-B composite-image dimension:

[
216 \times 768 \times 3 = 497,664
]

The equality is useful for storage capacity, but the tensors are not semantically compatible.

## 4.3 Head context tensor

```text
context_vision_obs:
  rollout shape:  [B, 136, 384, 3]
  training shape: [B, T, 136, 384, 3]
  dtype: float32
```

Flattened dimension:

[
136 \times 384 \times 3 = 156,672
]

## 4.4 Camera timing metadata

Add a separate non-privileged observation:

```text
camera_meta:
  rollout shape:  [B, 6]
  training shape: [B, T, 6]
```

Exact order:

```text
0: left_age_s_normalized
1: right_age_s_normalized
2: head_age_s_normalized
3: left_valid
4: right_valid
5: head_valid
```

Suggested normalization:

```python
age_normalized = clamp(age_seconds / 0.1, 0.0, 1.0)
```

`camera_meta` is used only by the feature-fusion module. It is not appended to the 81D proprioception, so the recurrent policy input can remain `81 + 128 = 209D`.

## 4.5 Resulting observation dimensions

```python
{
    "actor_obs": 81,
    "vision_obs": 497664,
    "context_vision_obs": 156672,
    "camera_meta": 6,
    "teacher_obs": 133,
    "critic_obs": 138,
    "a2_base_obs": 1620,
}
```

---

# 5. Recommended Network

## 5.1 High-level design

```text
Left D435i ─┐
            ├─ Shared D435i ResNet18 ── left/right features ─┐
Right D435i ┘                                               │
                                                            ├─ manipulation fusion ─┐
OEM A2 Head ─── Separate Head ResNet18 ── context feature ──┘                       │
                                                                                     ├─ context fusion → 128D
Camera age/validity metadata ────────────────────────────────────────────────────────┘
                                                                                     ↓
                                                            81D proprio + 128D fused feature
                                                                                     ↓
                                                                2-layer LSTM, hidden 256
                                                                                     ↓
                                                                         12D high-level action
```

The phrase **shared encoder** refers to the D435i pair: both D435i views must use exactly one set of ResNet18 weights.

The A2 Head should use a separate context encoder because it differs from the D435i pair in:

* optics and distortion;
* aspect ratio;
* FoV;
* frame rate;
* physical role;
* real-device preprocessing.

Trying to force the head image into the same spatial tensor or the same BatchNorm statistics would create an unnecessary sensor-domain conflict.

---

## 5.2 D435i shared encoder

For `M` valid rollout or recurrent timesteps:

```text
input:
  [M, 384, 216, 6]

split:
  left  [M, 384, 216, 3]
  right [M, 384, 216, 3]

permute:
  left  [M, 3, 384, 216]
  right [M, 3, 384, 216]

pack:
  [2M, 3, 384, 216]

one shared ResNet18:
  [2M, 128]

reshape:
  [M, 2, 128]
```

The implementation must contain only one D435i encoder object and one set of D435i encoder state-dict keys.

Do not:

* change the first convolution to six channels;
* instantiate separate left and right ResNet18 modules;
* concatenate the two views spatially;
* use panorama or depth as an intermediate;
* average RGB pixels across the cameras.

---

## 5.3 Head context encoder

```text
input:
  [M, 136, 384, 3]

permute:
  [M, 3, 136, 384]

separate ResNet18:
  [M, 128]
```

The Head encoder should use:

```text
ImageNet initialization
trainable = true
output feature dimension = 128
```

DoorMan similarly processes RGB with a learned vision encoder, concatenates the resulting latent with proprioception, and uses a two-layer LSTM before the action MLP. The paper also emphasizes temporal context and joint fine-tuning of the visual encoder during DAgger.

---

# 6. Hierarchical Feature Fusion

A two-stage fusion is recommended.

## 6.1 Stage A: manipulation-view fusion

Let:

```text
fL, fR ∈ R^128
```

Add fixed learned view embeddings:

[
\tilde f_L = LN(f_L + e_L)
]

[
\tilde f_R = LN(f_R + e_R)
]

Compute freshness values:

[
c_L = v_L \exp(-a_L/\tau_D)
]

[
c_R = v_R \exp(-a_R/\tau_D)
]

where:

```text
vL, vR = validity flags
aL, aR = frame ages in seconds
τD initial value = 0.05 s
```

The deterministic base feature is:

[
f_{\text{base}}
===============

\frac{c_L\tilde f_L+c_R\tilde f_R}
{c_L+c_R+\epsilon}
]

The ordered interaction feature is:

[
f_{\text{pair-residual}}
========================

MLP_D
\left(
[\tilde f_L,\tilde f_R,|\tilde f_L-\tilde f_R|]
\right)
]

MLP shape:

```text
Linear(384, 256)
SiLU
LayerNorm(256)
Linear(256, 128)
```

The last layer should be zero-initialized.

Final manipulation feature:

[
f_M = LN(f_{\text{base}} + f_{\text{pair-residual}})
]

This initialization starts close to an age-weighted mean but retains ordered left/right semantics and can learn asymmetric interactions.

If both D435i views are invalid, the model must fail fast. It must not silently copy one view, insert the A2 Head image, or fabricate a zero image.

---

## 6.2 Stage B: OEM Head context fusion

Let:

```text
fH ∈ R^128
```

Add a learned head-view embedding:

[
\tilde f_H = LN(f_H + e_H)
]

Head freshness:

[
c_H = v_H \exp(-a_H/\tau_H)
]

with an initial:

```text
τH = 0.10 s
```

Construct:

[
q =
[f_M,\tilde f_H,|f_M-\tilde f_H|,m]
]

where `m` is the 6D camera metadata.

Context residual:

```text
Linear(390, 256)
SiLU
LayerNorm(256)
Linear(256, 128)
```

The last layer is zero-initialized.

A scalar learned gate is computed from the same input:

```text
Linear(390, 64)
SiLU
Linear(64, 1)
Sigmoid
```

Final fused feature:

[
f_{\text{final}}
================

LN
\left(
f_M
+
c_H
\left(
0.25,\tilde f_H
+
g_H f_{\text{context-residual}}
\right)
\right)
]

Output:

```text
f_final: [M, 128]
```

The fixed `0.25` head base contribution gives the level context view a meaningful initial path while keeping the manipulation pair dominant. It should be configurable and ablated later, but it is preferable to initializing the head branch at exactly zero and risking permanent underuse.

---

# 7. Recurrent Policy and Action Contract

The fused output remains `128D`. Therefore the current recurrent dimensions can remain unchanged:

```text
81D actor proprio
+
128D fused vision
=
209D LSTM input
```

Recommended recurrent policy:

```text
LSTM:
  input_size: 209
  hidden_size: 256
  num_layers: 2

Action MLP:
  256 → 512 → 256 → 128 → 12
```

The action boundary remains:

```text
Student high-level action: 12D
Teacher action:            12D
Frozen A2_Base action:     12D
Environment rollout:       24D
```

The current branch already uses a ResNet18 visual feature of `128D`, an `81D` actor observation, a two-layer `256D` LSTM and a `12D` output.

---

# 8. Camera Timing and Realistic Frame Repetition

## 8.1 Real sensor rates

The intended deployment rates are approximately:

```text
D435i RGB: up to 30 fps
A2 Head:  up to 15 fps
Policy:   50 Hz
```

Therefore every control step cannot contain three newly captured images.

The Student must be trained using sample-and-hold rather than unrealistically fresh 50 Hz camera frames.

## 8.2 Simulation timing contract

Production simulation should use:

```text
Left D435i update period:  1/30 s
Right D435i update period: 1/30 s
A2 Head update period:     1/15 s
Policy period:              1/50 s
```

At each 50 Hz policy tick:

1. use the latest completed left/right D435i pair;
2. use the latest completed A2 Head frame;
3. calculate per-view frame age;
4. populate `camera_meta`;
5. do not call additional `sim.render()`, `sim.step()` or `camera.update()` from the observation getter.

The existing C-B path already demonstrates the correct architectural pattern: multiple high-level `TiledCamera` sensors are registered in the scene, and `get_rgb_image()` only reads their outputs and composes the policy tensor without advancing simulation or issuing another render.

## 8.3 Real deployment pairing

Recommended timing gates:

| Signal                              | Pass threshold |
| ----------------------------------- | -------------: |
| Left/right D435i timestamp skew p95 |         ≤10 ms |
| Left/right maximum skew             |         ≤20 ms |
| D435i frame age p95                 |         ≤50 ms |
| Head frame age p95                  |        ≤100 ms |
| Head maximum accepted age           |         150 ms |
| Long-run dropped-frame ratio        |          <0.1% |

The D435i pair is treated as the required manipulation observation. If a synchronized pair cannot be formed, the external supervisor should stop or hold the robot.

The Head camera is a required context sensor for normal operation. A transient invalid head frame may mathematically set `cH=0`, but the event must be surfaced in telemetry. Persistent head invalidity should trigger a reduced-speed or stop state outside the policy.

---

# 9. Safety and Collision-Avoidance Boundary

The OEM Head camera is valuable for learned direction and collision context, but an RGB Student must not become the only collision-protection mechanism.

The deployment stack should remain:

```text
A2 lidar / low-level platform safety
        ↓
hard collision and emergency constraints

Tri-view Student
        ↓
learned door approach, direction, manipulation and local avoidance
```

A2 officially includes both lidar and a head camera in its perception configuration.

The Student may learn:

* door-frame clearance;
* gross obstacle awareness;
* floor direction;
* base yaw alignment;
* recovery from an arm-dominated manipulation view.

It must not be described as guaranteeing obstacle avoidance from a 15 fps monocular RGB view.

---

# 10. Simulator and Observation Implementation

## 10.1 New architecture identity

Use a new identity rather than modifying the existing C-B or C-B2 panorama routes:

```text
C-B2H-DUALRAW-SHAREDENC-TOEIN20-V19
```

The panorama utilities must not be imported by this Student path.

## 10.2 Recommended camera configuration skeleton

```yaml
simulator:
  config:
    cameras:
      enable_cameras: true
      architecture_id: C-B2H-DUALRAW-SHAREDENC-TOEIN20-V19

      # Left D435i remains the primary IsaacLab ego_camera.
      camera_parent: trunk
      camera_prim_suffix: d435i_left_portrait_policy_camera
      camera_pos: [0.215, 0.095, 0.165]
      camera_rot_wxyz:
        [0.852868532, -0.086824089, -0.492403877, -0.150383733]
      camera_convention: world
      camera_focal_length: 1.0
      camera_focus_distance: 0.5
      camera_horizontal_aperture: 0.7777574637059793
      camera_vertical_aperture: 1.3826799354772965
      camera_clipping_range: [0.1, 20.0]
      camera_update_period: 0.03333333333333333
      camera_types:
        - rgb: true
      camera_resolutions: [384, 216]

      image_mean: [0.485, 0.456, 0.406]
      image_std: [0.229, 0.224, 0.225]

      policy_multiview:
        enabled: true
        architecture_id: C-B2H-DUALRAW-SHAREDENC-TOEIN20-V19

        manipulation:
          layout: channel_stacked_raw_rgb
          view_order: [left, right]
          per_view_resolution: [384, 216]
          output_shape: [384, 216, 6]

          right:
            sensor_name: d435i_right_portrait_policy
            parent: trunk
            prim_suffix: d435i_right_portrait_policy_camera
            position_m: [0.215, -0.095, 0.165]
            rotation_wxyz:
              [0.852868532, 0.086824089, -0.492403877, 0.150383733]
            convention: world
            resolution: [384, 216]
            focal_length: 1.0
            focus_distance: 0.5
            horizontal_aperture: 0.7777574637059793
            vertical_aperture: 1.3826799354772965
            clipping_range: [0.1, 20.0]
            update_period: 0.03333333333333333

        context:
          sensor_name: a2_head_oem_policy
          role: level_forward_context
          parent: trunk
          prim_suffix: a2_head_oem_policy_camera
          position_m: [0.3381, 0.0336, 0.0525]
          rotation_wxyz: [1.0, 0.0, 0.0, 0.0]
          convention: world
          resolution: [136, 384]
          focal_length: 1.0
          focus_distance: 0.5
          horizontal_aperture: 4.492073547808433
          vertical_aperture: 1.59094271484882
          clipping_range: [0.1, 20.0]
          update_period: 0.06666666666666667

        camera_meta:
          enabled: true
          order:
            - left_age_normalized
            - right_age_normalized
            - head_age_normalized
            - left_valid
            - right_valid
            - head_valid
```

---

## 10.3 Image composition helpers

Retain the existing C-B helper:

```python
compose_horizontal_letterboxed_rgb(...)
```

Add a new helper:

```python
compose_channel_stacked_dual_rgb(...)
```

Contract:

```python
left_rgb:
    uint8 [N,384,216,3]

right_rgb:
    uint8 [N,384,216,3]

return:
    float32 [N,384,216,6]
```

Processing:

```python
left = normalize(left_rgb)
right = normalize(right_rgb)
output = torch.cat((left, right), dim=-1)
```

Add a separate helper:

```python
normalize_head_context_rgb(...)
```

Contract:

```python
head_rgb:
    uint8 [N,136,384,3]

return:
    float32 [N,136,384,3]
```

Both helpers must reject:

* wrong dtype;
* wrong shape;
* constant or uninitialized frames;
* different devices;
* non-finite normalization;
* unsupported channel order;
* implicit resizing;
* panorama output;
* missing-view duplication;
* RGB averaging.

---

# 11. New Actor Class

Recommended file:

```text
gr00t/rl/trl/modules/
  vision_actor_critic_modules_triview_recurrent.py
```

Recommended class:

```python
TriViewContextSharedEncoderVisionRecurrentActor
```

Recommended configuration:

```yaml
actor:
  _target_: >
    gr00t.rl.trl.modules.vision_actor_critic_modules_triview_recurrent.
    TriViewContextSharedEncoderVisionRecurrentActor

  input_key: actor_obs
  manipulation_vision_key: vision_obs
  context_vision_key: context_vision_obs
  camera_meta_key: camera_meta

  running_mean_std: true
  rnn_type: lstm
  rnn_hidden_dim: 256
  rnn_num_layers: 2

  view_contract:
    manipulation_shape: [384, 216, 6]
    context_shape: [136, 384, 3]
    camera_meta_dim: 6
    d435i_view_order: [left, right]
    d435i_feature_dim: 128
    head_feature_dim: 128
    fused_feature_dim: 128

  backbone:
    d435i_vision_module:
      _target_: gr00t.rl.agents.modules.modules.BaseModule
      process_output_dim: true
      module_config_dict:
        input_dim: [vision_obs]
        output_dim: [128]
        layer_config:
          type: ResNet
          resnet_type: resnet18
          pretrained: true
          trainable: true

    head_vision_module:
      _target_: gr00t.rl.agents.modules.modules.BaseModule
      process_output_dim: true
      module_config_dict:
        input_dim: [context_vision_obs]
        output_dim: [128]
        layer_config:
          type: ResNet
          resnet_type: resnet18
          pretrained: true
          trainable: true

    mlp_module:
      _target_: gr00t.rl.agents.modules.modules.BaseModule
      process_output_dim: true
      module_config_dict:
        input_dim: [actor_obs]
        output_dim: ["${algo.config.student_action_dim}"]
        layer_config:
          type: MLP
          hidden_dims: [512, 256, 128]
          activation: SiLU
```

---

## 11.1 Forward pseudocode

```python
def forward(
    self,
    obs_dict,
    masks=None,
    hidden_states=None,
    episode_attnmask=None,
    **kwargs,
):
    actor_obs = self._normalize_actor_obs(obs_dict["actor_obs"], masks)

    dual_rgb = obs_dict["vision_obs"]
    head_rgb = obs_dict["context_vision_obs"]
    camera_meta = obs_dict["camera_meta"]

    valid_mask, flat_actor_obs = self._prepare_recurrent_masks(
        actor_obs,
        masks,
    )

    dual_valid = self._select_valid_frames(dual_rgb, valid_mask)
    head_valid = self._select_valid_frames(head_rgb, valid_mask)
    meta_valid = self._select_valid_rows(camera_meta, valid_mask)

    left = dual_valid[..., 0:3].permute(0, 3, 1, 2)
    right = dual_valid[..., 3:6].permute(0, 3, 1, 2)

    packed_d435i = torch.cat((left, right), dim=0)
    encoded_pair = self.d435i_vision_module(packed_d435i)

    count = left.shape[0]
    f_left = encoded_pair[:count]
    f_right = encoded_pair[count:]

    head_chw = head_valid.permute(0, 3, 1, 2)
    f_head = self.head_vision_module(head_chw)

    f_manip = self.manipulation_fusion(
        f_left,
        f_right,
        meta_valid,
    )

    f_final = self.context_fusion(
        f_manip,
        f_head,
        meta_valid,
    )

    latent = self._restore_padding(
        f_final,
        valid_mask,
        fused_dim=128,
    )

    recurrent_input = torch.cat((actor_obs, latent), dim=-1)
    memory_out = self._run_memory(
        recurrent_input,
        masks,
        hidden_states,
    )
    return self.mlp_module(memory_out)
```

---

# 12. Fail-Fast Model Requirements

Construction must fail unless:

```text
vision_obs shape         = [384,216,6]
context_vision_obs shape = [136,384,3]
camera_meta dimension    = 6
D435i view order         = [left,right]
D435i feature dim        = 128
Head feature dim         = 128
fused feature dim        = 128
actor_obs                = 81
LSTM input               = 209
Student output           = 12
```

State-dict inspection must prove:

```text
one D435i encoder
one Head encoder
no left_encoder/right_encoder duplication
fusion parameters present
```

The Student route must fail if it imports or calls:

```text
a2_dual_portrait_panorama.py
distance_to_image_plane
instance_id_segmentation_fast
panorama reprojection
RGB feathering
```

---

# 13. Trainer and Rollout Storage

The current trainer derives one camera tensor shape from `camera_resolutions + [3]`. The tri-view route requires explicit storage shapes.

Recommended configuration:

```yaml
policy_observation_shapes:
  vision_obs: [384, 216, 6]
  context_vision_obs: [136, 384, 3]
  camera_meta: [6]
```

Storage registration:

```python
self.storage.register_key(
    "vision_obs",
    shape=(384, 216, 6),
    dtype=torch.float32,
)

self.storage.register_key(
    "context_vision_obs",
    shape=(136, 384, 3),
    dtype=torch.float32,
)

self.storage.register_key(
    "camera_meta",
    shape=(6,),
    dtype=torch.float32,
)
```

The underlying `RolloutStorage` already supports arbitrary explicitly registered tensor shapes and flattens only the time and environment axes during minibatch generation.

---

## 13.1 Memory implications

Raw float32 visual elements per environment per policy step:

```text
Dual D435i:
  384 × 216 × 6 = 497,664

A2 Head:
  136 × 384 × 3 = 156,672

Total:
  654,336 values
```

This is `31.5%` more raw image storage than the existing C-B composite input.

Approximate raw rollout image storage for:

```text
32 env × 8 steps
```

is:

[
654,336 \times 32 \times 8 \times 4
\approx 639\ \text{MiB}
]

before model activations, gradients, renderer buffers and Teacher state.

The existing C-B 32-env/10-batch capacity pilot reached approximately `18,241 MiB` peak GPU memory.

Recommended tri-view capacity gate:

```text
32-env peak VRAM ≤ 26 GiB
no OOM
no CPU rendering fallback
training time ≤ C-B baseline × 1.35
```

If capacity fails, reduce the Head policy resolution first, for example to `272×96`, while preserving its full calibrated FoV. Do not reduce D435i resolution before testing the close-range handle and finger impact.

---

# 14. Video and Debug Output

The current trainer cannot treat a six-channel tensor as one RGB frame.

The tri-view route should output:

```text
left_d435i.mp4
right_d435i.mp4
a2_head.mp4
three_panel_process.mp4
```

Three-panel layout:

```text
Left portrait D435i | Right portrait D435i | OEM A2 Head
```

Do not produce a Student panorama.

Before video encoding:

1. split left and right channels;
2. invert ImageNet normalization;
3. clamp to `[0,1]`;
4. convert to `uint8`;
5. resize only for the debug panel, never for the policy tensor.

---

# 15. v19 Teacher Integration

## 15.1 Exact artifact identity

The current mainline memory records that v19 trained seven groups and selected the G3 no-carry fallback under the preregistered selection rule, with a pooled selected checkpoint at step 750. It also records that the complete scientific judgement remained failed, so the selected checkpoint should not be described as a universally successful release policy.

The Student launcher must not infer the v19 Teacher from:

```text
branch name
“best” filename
latest checkpoint
last.pt
directory sorting
```

It must require:

```text
teacher_actor_path
teacher_config_path
teacher_manifest_path
teacher_runtime_commit
```

The exact user-selected v19 checkpoint may be G3 step750 or another reviewed artifact, but the choice must be explicit and hash-sealed.

## 15.2 Teacher manifest

The existing Teacher validator enforces:

```text
133D privileged Teacher observation
12D Teacher output
20-DOF A2_Piper joint order
2-layer recurrent actor state shapes
A2_Base compatibility
immutable checkpoint/config/manifest triplet
```

It explicitly rejects automatic checkpoint discovery and mutable `last.pt` fallback.

The same validator should be used for the v19 Teacher. Do not weaken it to accommodate an unsealed artifact.

## 15.3 Exact v19 runtime

Create:

```text
gr00t/rl/scripts/run_a2_student_distillation_v19.py
```

It must pin:

```python
EXPECTED_RUNTIME_COMMIT = "<audited exact v19 runtime commit>"
```

and lazily overlay the exact v19 versions of:

```text
door_open_a2_base.py
scenario_cfg/isaacsim.py
env_rand/door.py
any reward/task module required by the saved v19 config
```

Do not run:

```text
v19 Teacher checkpoint
+
v16 task runtime
```

unless a separate compatibility audit proves they are identical for every Teacher observation, action and transition term.

---

# 16. Student Initialization

## 16.1 Primary recommendation: fresh Student

```text
D435i encoder: ImageNet ResNet18
Head encoder:  ImageNet ResNet18
Fusion:        new initialization
LSTM:          fresh
Action MLP:    fresh
Optimizer:     fresh
```

This is the cleanest experiment for measuring the tri-view architecture.

## 16.2 Optional selective initialization from the completed C-B Student

The existing complete C-B Student result can be used as a separate warm-start ablation because:

```text
old fused vision dim = 128
new fused vision dim = 128
old LSTM input       = 209
new LSTM input       = 209
```

An explicit selective loader may copy:

```text
old vision encoder → new D435i shared encoder
old vision encoder → new Head encoder
old LSTM
old action MLP
actor running mean/variance
action standard deviation
```

It must not load:

```text
old optimizer state
old scheduler state
old global step
old visual tensor contract
old camera config
```

New fusion parameters remain newly initialized.

Do not use unrestricted:

```python
load_state_dict(..., strict=False)
```

The loader must compare the exact expected missing and remapped key sets against an allowlist and fail on any extra mismatch.

---

# 17. Training Plan

## 17.1 Admission sequence

### R0 — Static contract

Required:

```text
Hydra compose
py_compile
targeted tests
affected full CPU test suite
git diff --check
state-key manifest
parameter-count report
```

### R1 — Sensor smoke, no training

Suggested:

```text
2 env
all three RGB sensors
no Teacher update
no Student update
```

Required outputs:

```text
left raw  [2,384,216,3]
right raw [2,384,216,3]
head raw  [2,136,384,3]

vision_obs         [2,384,216,6]
context_vision_obs [2,136,384,3]
camera_meta        [2,6]
```

### R2 — Synthetic forward/backward

Required:

```text
finite 12D output
finite BC loss
nonzero D435i encoder gradient from left view
nonzero D435i encoder gradient from right view
nonzero Head encoder gradient
nonzero manipulation-fusion gradient
nonzero context-fusion gradient
finite LSTM and MLP gradients
```

### R3 — One-update distillation

Suggested:

```text
4 env
1 step per env
1 minibatch
1 total batch
teacher rollout ratio = 1.0
```

Required:

```text
global_step = 1
new checkpoint created
all tensors finite
fusion parameters changed
optimizer contains all new parameters
12D + 12D = 24D action chain preserved
```

### R4 — Capacity ladder

Run sequentially:

```text
8 env
16 env
24 env
32 env
```

Stop at the first failure. Do not jump directly to the nominal `4096` configuration used by state-only Teacher training.

### R5 — Short DAgger pilot

Suggested:

```text
100–200 batches
teacher rollout ratio = 1.0
```

Then review:

```text
BC loss
Student/Teacher action disagreement
per-view encoder gradient
feature norms
collision/contact metrics
base heading metrics
handle retention
```

### R6 — Controlled mixed rollout

Only after R5:

```text
ratio = 0.75
ratio = 0.50
ratio = 0.25
```

Each ratio is a separate run identity. Do not automatically anneal without an adjudicated checkpoint between stages.

---

# 18. Visual and Timing Randomization

DoorMan reports that visual transfer benefited from randomized textures, lighting, camera intrinsics/extrinsics and motion blur, and that the RGB visual encoder was trained jointly with the recurrent policy.

## 18.1 Shared scene randomization

Apply consistently to all three cameras:

```text
door and handle material
wall and floor material
lighting
shadow
door geometry
handle height
door placement
body pose and height
```

## 18.2 Per-sensor randomization

Independently randomize:

```text
exposure
gain
white balance
gamma
motion blur
compression
small intrinsic error
principal-point error
frame age
frame repetition
```

## 18.3 Extrinsic randomization

Initial ranges:

| Camera             | Translation | Rotation |
| ------------------ | ----------: | -------: |
| D435i common rig   |       ±5 mm |      ±2° |
| D435i differential |       ±3 mm |    ±1.5° |
| OEM Head           |       ±5 mm |      ±2° |

The Head nominal pose must remain centered on the official OEM transform. Randomization represents calibration and mounting tolerance, not a new optimized head angle.

## 18.4 Timing randomization

Recommended training distribution:

```text
D435i repeated-frame interval: 20–40 ms
Head repeated-frame interval:  40–80 ms
D435i differential skew:       0–10 ms
Additional frame delay:        0–40 ms
```

---

# 19. Required Ablations

Use the same frozen v19 Teacher, runtime, seed set and training budget.

| ID     | Student views                                   | Fusion                                    |
| ------ | ----------------------------------------------- | ----------------------------------------- |
| B0     | Original C-B D435i + provisional/head composite | Existing spatial composite                |
| B1     | Dual D435i ±20° only                            | D435i shared encoder                      |
| **B2** | **Dual D435i ±20° + OEM Head**                  | **Hierarchical tri-view feature fusion**  |
| B3     | Dual D435i ±15° + OEM Head                      | Same tri-view fusion                      |
| B4     | OEM Head only                                   | Separate diagnostic baseline              |
| B5     | B2 with frozen Head branch                      | Tests whether Head adaptation is required |

The primary comparison is:

```text
B1 versus B2
```

It directly tests whether the level OEM Head improves direction and collision context beyond the dual manipulation pair.

---

# 20. Head-View Utilization Diagnostics

The Head encoder can be silently ignored unless utilization is measured.

Log:

```text
||f_left||
||f_right||
||f_head||
||f_manip||
||f_final - f_manip||
head freshness coefficient
Head encoder gradient norm
context-fusion gradient norm
action difference when Head is masked
```

Minimum structural gates:

```text
Head encoder gradient is finite and nonzero
context-fusion gradient is finite and nonzero
Head contribution is nonzero in at least one preregistered stage
```

Behavioral promotion requires that B2 improve at least one context-dependent metric without materially degrading manipulation.

Recommended metrics:

| Metric                                 | Desired B2 result                         |
| -------------------------------------- | ----------------------------------------- |
| Door-frame/body contact rate           | Lower than or equal to B1                 |
| Base yaw error during approach/staging | Lower than B1                             |
| Root lateral deviation                 | Lower than B1                             |
| Handle union visibility                | No more than 1 percentage point below B1  |
| Handle + both fingers visibility       | No more than 3 percentage points below B1 |
| BC loss                                | No worse than best dual-only baseline     |
| Student action smoothness              | No degradation                            |
| Overspeed/over-force                   | No degradation                            |

Stage 5 is excluded from these comparisons.

---

# 21. Unit Tests

## 21.1 Camera composition

Verify:

```text
left  uint8 [2,384,216,3]
right uint8 [2,384,216,3]
head  uint8 [2,136,384,3]
```

Produce:

```text
vision_obs         float32 [2,384,216,6]
context_vision_obs float32 [2,136,384,3]
camera_meta        float32 [2,6]
```

Reject:

```text
wrong dtype
wrong shape
constant frame
different device
NaN normalization
wrong left/right order
implicit resize
missing sensor
```

## 21.2 Shared D435i encoder

Prove:

```text
exactly one D435i ResNet18 instance
packed encoder input [2M,3,384,216]
encoded output [2M,128]
left/right reshape [M,2,128]
```

State dict must not contain:

```text
left_encoder.*
right_encoder.*
```

## 21.3 Head encoder

Verify:

```text
input [M,3,136,384]
output [M,128]
gradient finite and nonzero
```

## 21.4 Recurrent path

Verify:

```text
rollout:
  actor_obs [B,81]
  images
  output [B,12]

training:
  actor_obs [B,T,81]
  images [B,T,...]
  masks [B,T]
```

Padding timesteps:

* must not be encoded;
* must restore zero fused features;
* must not update camera-feature statistics;
* all-false masks must fail.

## 21.5 Fusion

Verify:

```text
manipulation fusion output [M,128]
context fusion output [M,128]
LSTM input [M,209]
```

At initialization:

```text
D435i residual ≈ 0
Head context residual ≈ 0
Head base contribution remains controlled and nonzero
```

## 21.6 Camera lifecycle

Verify:

```text
three high-level TiledCamera sensors
no render in observation getter
no physics step in observation getter
no direct USD pose polling
D435i pair frame synchronization
Head frame age metadata
no panorama imports
```

## 21.7 Checkpoint

Verify:

```text
strict fresh save/reload
fusion parameters included
both encoders included
optimizer includes both encoders and fusion
old C-B checkpoint fails strict full load
selective warm start accepts exact remap only
```

---

# 22. File-by-File Patch Plan

| File                                                                                      | Planned change                                                                                         |
| ----------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| **Add** `gr00t/rl/config/exp/wbmanip/door_open_a2_base_v19_cb2h_dualraw_dagger-lstm.yaml` | New v19 tri-view Student route                                                                         |
| **Add** `gr00t/rl/config/obs/wbmanip/door_open_a2_base_dagger_triview.yaml`               | 81D proprio plus dual D435i, Head and metadata keys                                                    |
| `gr00t/rl/utils/a2_policy_camera.py`                                                      | Add strict dual-channel composition and Head normalization helpers                                     |
| `gr00t/rl/simulator/isaacsim/isaacsim.py`                                                 | Add exact tri-view architecture branch and three sensor lifecycle                                      |
| `gr00t/rl/envs/legged_base_task/legged_robot_base.py`                                     | Expose manipulation RGB, Head RGB and camera metadata observation terms if required by current routing |
| **Add** `gr00t/rl/trl/modules/vision_actor_critic_modules_triview_recurrent.py`           | Two encoders, hierarchical fusion and recurrent actor                                                  |
| `gr00t/rl/trl/trainer/ppo_trainer_a2_base_api.py`                                         | Register two image tensors and metadata; fix tri-view video path                                       |
| `gr00t/rl/train_agent_trl.py`                                                             | Allow exact new actor target and explicit observation-shape contract                                   |
| **Add** `gr00t/rl/scripts/run_a2_student_distillation_v19.py`                             | Pin exact v19 runtime and lazy overlay                                                                 |
| **Add** `gr00t/rl/tests/test_a2_cb2h_triview_student.py`                                  | Camera, tensor, actor, storage and checkpoint tests                                                    |
| Existing C-B tests                                                                        | Preserve unchanged                                                                                     |
| Existing C-B2 panorama files                                                              | Preserve as rejected diagnostic evidence                                                               |
| Memory files                                                                              | Update only after actual runtime evidence exists                                                       |

---

# 23. Deployment Preprocessing

## D435i pair

```text
capture
→ rotate both portrait streams to the same upright convention
→ apply calibrated RGB rectification
→ resize/crop to 216 W × 384 H
→ ImageNet normalize
→ channel-stack left then right
```

Both physical D435i units must use the same image-up direction. Cable-driven housing rotations must be corrected in preprocessing.

## OEM A2 Head

```text
capture OEM stream
→ apply measured intrinsic/distortion correction
→ rectify to the fixed level forward virtual camera
→ output 384 W × 136 H
→ ImageNet normalize
```

The published `132°×77°` FoV does not provide a complete intrinsic or distortion model. The physical A2 Head stream must be calibrated rather than assumed to exactly match the simulator pinhole camera.

---

# 24. Final Frozen Recommendation

```text
Architecture:
  C-B2H-DUALRAW-SHAREDENC-TOEIN20-V19

Manipulation cameras:
  Left D435i:
    xyz  [0.215,+0.095,0.165]
    RPY  [0,-60,-20]

  Right D435i:
    xyz  [0.215,-0.095,0.165]
    RPY  [0,-60,+20]

  RGB:
    384H × 216W × 3 each
    30 fps target
    shared ResNet18
    128D per-view feature

Context camera:
  OEM A2 Head:
    xyz  [0.3381,+0.0336,0.0525]
    RPY  [0,0,0]
    132°H × 77°V published FoV
    384W × 136H policy representation
    15 fps target
    separate ResNet18
    128D context feature

Fusion:
  D435i ordered age-weighted mean-residual fusion
  then freshness-gated OEM Head context residual
  final fused feature = 128D

Recurrent policy:
  81D proprio + 128D fused vision
  two-layer LSTM, hidden 256
  12D high-level action

Additional observation:
  6D camera age/validity metadata

Teacher:
  exact sealed user-selected base_v19 artifact
  exact adjacent config
  exact manifest
  exact audited v19 runtime commit

Excluded:
  panorama
  depth input
  segmentation input
  privileged stage/object pose
  automatic missing-camera fallback
```

The OEM A2 Head should be retained because it supplies the level, wide forward context that the two upward-pitched D435i manipulation views cannot reliably provide. The correct architecture is not “three images stitched together,” but **two shared-encoder manipulation views plus one separately encoded context view, fused before the existing recurrent policy**.
