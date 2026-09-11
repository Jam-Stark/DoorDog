#!/usr/bin/env python3
"""Task 2: candidate mount JSONs derived from U3_F0.json (package conventions), written ONLY under
/tmp/v28_team/camera/variants/.

* wrist: U3_F{theta}: wrist housing rotated in place (about its own bar / image-x axis, housing centre
  fixed at F+[−0.14, 179.32, 15.68] mm) by theta degrees down toward the gripper, via the package's own
  build_u3_forward.make_variant(source, TF, pid, down_deg) at the reference posture [0,0,0,0,0,1.57].
* base: both base cameras at the same up-tilt (package rpy_deg [0, -tilt, 0]) with the saddle/post/rail
  envelopes rebuilt with the same construction as the shipped file (verified against U3_F0.json).
"""
import sys, json, math, copy
sys.path.insert(0, '/tmp/v28_team/camera/pkgcode')
from geometry import *          # noqa
from mount_shapes import design_box, beam
from build_u3_forward import make_variant

OUT = Path('/tmp/v28_team/camera/variants'); OUT.mkdir(parents=True, exist_ok=True)
CROSSBAR_Z = 0.155431554755
CROSSBAR_X = 0.045


def rebuild_base_camera(cam, pitch_deg):
    c = copy.deepcopy(cam)
    xyz = np.array(c['xyz_m']); rpy = np.array([0.0, float(pitch_deg), 0.0])
    TM = tf(xyz, np.radians(rpy)); R = TM[:3, :3]
    c.update(rpy_deg=rpy.tolist(), rpy_rad=np.radians(rpy).tolist(), T_parent_M=TM.tolist(), quat_parent_M_wxyz=quat(R).tolist())
    for st, s in c['streams'].items():
        mo = np.eye(4); mo[:3, :3] = R_M_O; mo[:3, 3] = s['offset_M_m']; TO = TM @ mo; TU = TO.copy(); TU[:3, :3] = TO[:3, :3] @ R_O_USD
        s.update(T_parent_optical=TO.tolist(), position_parent_m=TO[:3, 3].tolist(), quat_parent_ros_wxyz=quat(TO[:3, :3]).tolist(),
                 T_parent_usd=TU.tolist(), quat_parent_usd_wxyz=quat(TU[:3, :3]).tolist())
    return c, TM


def base_brackets(name, TM):
    R = TM[:3, :3]; centre = TM[:3, 3]; y = centre[1]
    mountB = centre + R @ np.array([0, 0, -0.0165])
    rail = beam(f'{name}_crossbar_rail', 'trunk', [CROSSBAR_X, y, CROSSBAR_Z], [mountB[0], y, CROSSBAR_Z], .010)
    post = beam(f'{name}_post', 'trunk', [mountB[0], y, CROSSBAR_Z], mountB, .010)
    saddle = design_box(f'{name}_saddle', 'trunk', centre + R @ np.array([0, 0, -0.0145]), [.022, .08, .004], R, contact=name)
    return [rail, post, saddle]


def apply_base_tilt(plan, tilt_up_deg):
    """Both base cameras at rpy_deg [0, -tilt_up_deg, 0] (negative package pitch = optical axis tilted UP)."""
    p = copy.deepcopy(plan)
    keep = [b for b in p['brackets'] if not (b['parent'] == 'trunk' and b['name'] not in ('base_foot', 'base_crossbar'))]
    new_br = []
    for i, cam in enumerate(p['cameras']):
        if cam['parent'] != 'trunk':
            continue
        c, TM = rebuild_base_camera(cam, -float(tilt_up_deg))
        p['cameras'][i] = c
        new_br += base_brackets(cam['name'], TM)
    wrist_br = [b for b in p['brackets'] if b['parent'] != 'trunk']
    p['brackets'] = keep + new_br + wrist_br
    return serial(p)


def verify_base_rebuild(f0):
    """Rebuilding the shipped asymmetric base (L -32 / R -12) must reproduce U3_F0.json exactly."""
    worst_cam = 0.0; worst_br = 0.0
    for cam, pitch in ((f0['cameras'][0], -32.0), (f0['cameras'][1], -12.0)):
        c, TM = rebuild_base_camera(cam, pitch)
        for k in ('T_parent_M', 'quat_parent_M_wxyz'):
            worst_cam = max(worst_cam, np.abs(np.array(c[k]) - np.array(cam[k])).max())
        for st in cam['streams']:
            for k in ('T_parent_optical', 'T_parent_usd', 'quat_parent_ros_wxyz', 'quat_parent_usd_wxyz'):
                worst_cam = max(worst_cam, np.abs(np.array(c['streams'][st][k]) - np.array(cam['streams'][st][k])).max())
        for b in base_brackets(cam['name'], TM):
            ref = next(x for x in f0['brackets'] if x['name'] == b['name'])
            worst_br = max(worst_br, np.abs(np.array(b['T_parent_item']) - np.array(ref['T_parent_item'])).max(), np.abs(np.array(b['size_m']) - np.array(ref['size_m'])).max())
    return worst_cam, worst_br


def tcp_row(plan, stream='rgb'):
    s = plan['cameras'][2]['streams'][stream]; T = np.array(s['T_parent_optical']); K = np.array(s['K'])
    p = inv(T, np.array([[0, 0, 0.085]]))[0]
    return float(K[1, 1] * p[1] / p[2] + K[1, 2]) / s['height'], float(p[2])


def main():
    robot = Robot(BUNDLE / 'robot')
    q = json.load(open(BUNDLE / 'config/reference_joint_pose.json'))
    TF = robot.fk(q)['arm_body6_to_gripper']
    source = json.load(open(BUNDLE / 'source/U3_V_previous.json'))
    f0 = json.load(open(BUNDLE / 'config/U3_F0.json'))
    wc, wb = verify_base_rebuild(f0)
    print(f'base rebuild check vs shipped U3_F0.json: max abs diff cameras {wc:.2e}, brackets {wb:.2e}')
    assert wc < 1e-9 and wb < 1e-9
    # make_variant(0) must reproduce the shipped U3_F0 wrist
    v0 = make_variant(source, TF, 'U3_F0', 0)
    d0 = max(np.abs(np.array(v0['cameras'][2]['streams'][st]['T_parent_optical']) - np.array(f0['cameras'][2]['streams'][st]['T_parent_optical'])).max() for st in ('rgb', 'depth', 'right_ir'))
    print(f'make_variant(0) vs shipped U3_F0 wrist optical transforms: max abs diff {d0:.2e}')
    assert d0 < 1e-9
    summary = {'base_rebuild_maxabs': wc, 'variants': {}}
    v0_row = tcp_row(v0)
    for th in (35, 40, 45):
        v = make_variant(source, TF, f'U3_F{th}', th)
        v['name_cn'] = f'U3 腕相机下俯{th}°候选（v28 规划，未验收）'
        v['hardware_status'] = 'PLANNING_CANDIDATE_v28; not qualified; derived by CAMERA lane from U3_F0 geometry'
        r_rgb, z_rgb = tcp_row(v, 'rgb'); r_d, z_d = tcp_row(v, 'depth')
        v['v28_variant'] = {
            'derived_from': 'config/U3_F0.json (wrist housing centre unchanged, rotated in place about the housing bar axis = image x axis)',
            'wrist_tilt_down_deg_at_reference_posture': th,
            'wrist_optical_axis_B_at_reference': v['design_revision']['reference_forward_axis_B'],
            'tcp_F_0_0_0p085_row_frac': {'rgb': r_rgb, 'depth': r_d, 'U3_F0_rgb': v0_row[0]},
            'sign_check': 'TCP image row fraction decreases vs U3_F0 => rotation is toward the gripper',
            'base_cameras': 'unchanged from U3_F0 (asymmetric L -32 / R -12 deg package pitch)',
            'reset_posture_hint_rad': [0, 0, 0, 0, round(-math.radians(th) + math.radians(th) - {35: 0.35, 40: 0.44, 45: 0.52}[th], 3), 1.57],
        }
        assert r_rgb < v0_row[0]
        save_json(OUT / f'U3_F{th}.json', v)
        summary['variants'][f'U3_F{th}'] = {'wrist_rpy_deg_RzRyRx': v['cameras'][2]['rpy_deg'], 'wrist_xyz_mm_F': v['cameras'][2]['xyz_mm'],
                                          'tcp_row_frac_rgb': r_rgb, 'tcp_row_frac_depth': r_d, 'tcp_z_rgb_m': z_rgb,
                                          'depth_T_parent_optical': v['cameras'][2]['streams']['depth']['T_parent_optical'],
                                          'wrist_brackets': {b['name']: {'size_m': b['size_m'], 'T_parent_item': b['T_parent_item']} for b in v['brackets'] if b['parent'] != 'trunk'}}
        for tilt in (12, 15):
            vb = apply_base_tilt(v, tilt)
            vb['plan_id'] = f'U3_F{th}_B{tilt}'
            vb['v28_variant'] = dict(vb['v28_variant'], base_cameras=f'both base cameras symmetric, package rpy_deg [0, -{tilt}, 0] (optical axis {tilt} deg UP in trunk frame), saddle/post/rail rebuilt')
            save_json(OUT / f'U3_F{th}_B{tilt}.json', vb)
            summary['variants'][f'U3_F{th}_B{tilt}'] = {'base_left_rpy_deg': vb['cameras'][0]['rpy_deg'], 'base_right_rpy_deg': vb['cameras'][1]['rpy_deg'],
                                                       'base_left_depth_axis_B': list(np.array(vb['cameras'][0]['streams']['depth']['T_parent_optical'])[:3, 2]),
                                                       'base_brackets': {b['name']: {'size_m': b['size_m'], 'T_parent_item': b['T_parent_item']} for b in vb['brackets'] if b['parent'] == 'trunk'}}
    # also base-symmetric variants of the untilted F0 for reference
    for tilt in (12, 15):
        vb = apply_base_tilt(f0, tilt); vb['plan_id'] = f'U3_F0_B{tilt}'; save_json(OUT / f'U3_F0_B{tilt}.json', vb)
    save_json(OUT / 'variants_summary.json', summary)
    for k, v in summary['variants'].items():
        if 'wrist_rpy_deg_RzRyRx' in v:
            print(k, 'wrist rpy_deg', np.round(v['wrist_rpy_deg_RzRyRx'], 4).tolist(), 'xyz_mm', np.round(v['wrist_xyz_mm_F'], 3).tolist(), 'tcp row rgb/depth', round(v['tcp_row_frac_rgb'], 3), round(v['tcp_row_frac_depth'], 3))
        else:
            print(k, 'base rpy', v['base_left_rpy_deg'], v['base_right_rpy_deg'], 'depth axis B', np.round(v['base_left_depth_axis_B'], 4).tolist())


if __name__ == '__main__':
    main()
