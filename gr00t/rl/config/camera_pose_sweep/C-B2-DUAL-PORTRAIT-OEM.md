# C-B2-DUAL-PORTRAIT-OEM

## Status and identity

This document is the repository design record for the C-B2 camera ablation. It
adds a new identity and does not overwrite C-B or its runtime evidence.

C-B2 is a simulation and physical-mount proposal. A Teacher camera render can
validate sensor creation, transforms, intrinsics, same-render capture, video
sealing, and simulated visibility. It cannot validate CAD interference, USB
bandwidth, real-camera synchronization, distortion, rolling shutter, exposure,
vibration, or physical calibration.

## Optical correction

The D435i values near `87 deg H x 58 deg V` describe the depth/IR stereo system.
The RGB color camera is approximately `69.4 deg H x 42.5 deg V`. C-B2 uses RGB,
so one mechanically portrait and software-uprighted D435i has approximately
`42.5 deg H x 69.4 deg V` in the robot/world directions.

References:

- Intel D435i specification: <https://www.intel.cn/content/www/cn/zh/products/sku/190004/intel-realsense-depth-camera-d435i/specifications.html>
- RealSense D435i product page: <https://www.realsenseai.com/cn/products/d435i/>

## Frozen nominal geometry

All positions are RGB optical centers in the A2 `trunk` frame. Quaternions use
`wxyz` and `world` camera convention.

| View | Position m | Effective optical RPY deg | Quaternion wxyz |
|---|---|---|---|
| Left D435i | `[0.215,+0.095,0.165]` | `[0,-60,-15]` | `[0.858616436,-0.065263096,-0.495722431,-0.113038999]` |
| Right D435i | `[0.215,-0.095,0.165]` | `[0,-60,+15]` | `[0.858616436,+0.065263096,-0.495722431,+0.113038999]` |
| A2 OEM Head | `[0.3381,+0.0336,0.0525]` | `[0,0,0]` | `[1,0,0,0]` |

Both D435i housings use the same physical `+90 deg` portrait roll. Software
uprighting removes that roll from the effective optical frame. The pair has a
`190 mm` baseline, symmetric `15 deg` toe-in, approximate `72.5 deg` combined
horizontal FoV, and approximate `12.5 deg` overlap. A2 Head stays an independent
wide context stream and is never stitched into the manipulation panorama.

The A2 OEM pose comes from the official URDF fixed joint:
`xyz="0.3381 0.0336 0.0525" rpy="0 0 0"` from `base_link`/`trunk` to
`camera_link`.

## Simulation rendering contract

The Hydra identity is
`camera_pose_sweep=d435i_dual_portrait_up60_a2_head_oem`.

The three high-level IsaacLab `TiledCamera` sensors are updated after exactly one
`sim.render()` at one unchanged physics step. Left and right output RGB,
`distance_to_image_plane`, and raw fast instance IDs. A2 Head outputs RGB and raw
fast instance IDs.

The virtual panorama is `416 W x 384 H`, cylindrical, `72.5 deg H x 69.4 deg V`:

1. Unproject finite D435i depth using each runtime intrinsic matrix.
2. Transform points using the fixed calibrated camera-to-virtual extrinsics.
3. Project into the cylindrical virtual camera.
4. Resolve occlusion with a deterministic Z-buffer.
5. For pixels without valid depth in `[0.28,20] m`, select the geometrically
   best single raw view; never average two RGB values in a depth hole.
6. Emit a per-frame depth-valid mask and fallback mask in runtime statistics.

Outputs are left raw, right raw, A2 Head raw, the depth-aware panorama, and one
four-panel process video. The panorama is diagnostic-only and is not wired into
the existing Student observation/model contract.

## Current visual verdict

The first `base_v16_B` Teacher render completed all sensor, same-render,
intrinsic, frame-sync, video-sealing, and decode gates, but the panorama is
**visually rejected** as of `2026-07-30 16:13 HKT`. The third panel shows
material ghosting, tearing, and holes. Runtime completion and non-empty depth
statistics do not make this panorama acceptable.

Treat the present panorama implementation as a diagnostic prototype and do not
wire it into the Student observation or use it as a physical-camera acceptance
artifact. The next revision must diagnose the projection/extrinsic convention,
depth representation, forward-warp sampling/Z-buffer behavior, occlusion seams,
and hole policy, then pass explicit visual and quantitative seam-quality gates.

## Physical boundaries

The nominal STEP point-cloud estimate suggests camera housings remain near the
connector envelope with roughly `17 mm` static clearance. This is not a solid
Boolean result. Before fabrication, the nominal/aggressive/conservative mounts
must still pass connector collision, full Piper joint sweep, policy trajectory
sweep, USB plug/cable swept volume, and A2 body-height checks.

The front-facing pair and OEM Head do not solve post-passage stage-5 visibility
when the handle is behind the robot. A wrist or side/rear view remains a separate
design problem.
