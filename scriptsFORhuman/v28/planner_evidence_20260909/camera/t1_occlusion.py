#!/usr/bin/env python3
"""Task 1: wrist-camera finger/gripper occlusion check for tilted U3 wrist mounts.

Read-only re-use of the Vpiper-Plate-Dual-D435i package tooling (geometry.Robot URDF FK + trimesh
meshes + numba BVH ray cast, build_u3_forward.make_variant) from a scratch copy under
/tmp/v28_team/camera/pkgcode.  Nothing is written inside any git worktree.

Static posture: package reference q = [0,0,0,0,0,1.57] (arm), legs from reference_joint_pose.json,
gripper joint arm_j7 = +o, arm_j8 = -o for o in {0, 0.020, 0.035} m (URDF limit 0.035).
"""
import sys, json, math, time, os
sys.path.insert(0, '/tmp/v28_team/camera/pkgcode')
from geometry import *            # noqa  (BUNDLE patched to the read-only package path)
from build_u3_forward import make_variant
import trimesh

OUT = Path('/tmp/v28_team/camera/t1'); OUT.mkdir(parents=True, exist_ok=True)
GRIPPER = {'arm_body6_to_gripper', 'arm_body7', 'arm_body8'}
THETAS = [0, 15, 35, 40, 45]
OPENINGS = [0.0, 0.020, 0.035]


def rx(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def projection(T, s, points):
    p = inv(T, points); K = np.asarray(s['K']); z = p[:, 2]
    den = np.where(abs(z) > 1e-12, z, np.nan)
    uv = np.column_stack([K[0, 0] * p[:, 0] / den + K[0, 2], K[1, 1] * p[:, 1] / den + K[1, 2]])
    inside = np.isfinite(uv).all(1) & (z > 0) & (uv[:, 0] >= 0) & (uv[:, 0] <= s['width']) & (uv[:, 1] >= 0) & (uv[:, 1] <= s['height'])
    return p, uv, inside, inside & (z >= s['min_z_mask_m'])


def scene_bvh(plan, P, parts, own='wrist'):
    pp = [p for p in parts if p.group != 'leg'] + [item_part(b, P) for b in plan['brackets']]
    pp += [item_part({'name': c['name'], 'parent': c['parent'], 'T_parent_item': c['T_parent_M'], 'size_m': plan['housing_size_M_m']}, P, 'camera')
           for c in plan['cameras'] if c['name'] != own]
    return BVH(pp)


def ray_clear(bvh, origin, pts, shorten):
    d = pts - origin
    end = pts - d * (shorten / np.linalg.norm(d, axis=1))[:, None]
    ts, ix = bvh.trace(np.broadcast_to(origin, end.shape), end)
    return ix < 0, ix


def main():
    t0 = time.time()
    robot = Robot(BUNDLE / 'robot')
    q0 = json.load(open(BUNDLE / 'config/reference_joint_pose.json'))
    q0.update({f'arm_j{i+1}': x for i, x in enumerate([0, 0, 0, 0, 0, 1.57])})
    source = json.load(open(BUNDLE / 'source/U3_V_previous.json'))
    f0 = json.load(open(BUNDLE / 'config/U3_F0.json'))
    TF = robot.fk(q0)['arm_body6_to_gripper']
    plans = {th: make_variant(source, TF, f'U3_F{th}', th) for th in THETAS}
    # --- sanity: make_variant(0) must reproduce the shipped U3_F0.json wrist optical transforms
    w0 = plans[0]['cameras'][2]; wF0 = f0['cameras'][2]
    dT = np.abs(np.array(w0['streams']['depth']['T_parent_optical']) - np.array(wF0['streams']['depth']['T_parent_optical'])).max()
    # --- sign / convention check vs the tilt-sweep wrapper (rotate depth optical frame in place about image x by -theta)
    conv = {}
    Td0 = np.array(wF0['streams']['depth']['T_parent_optical'])
    for th in THETAS:
        Tw = Td0 @ tf()  # placeholder identity
        Tw = Td0.copy(); R = rx(-math.radians(th)); Tw[:3, :3] = Td0[:3, :3] @ R
        Tv = np.array(plans[th]['cameras'][2]['streams']['depth']['T_parent_optical'])
        conv[th] = {'rot_diff_deg': float(math.degrees(math.acos(min(1.0, (np.trace(Tw[:3, :3].T @ Tv[:3, :3]) - 1) / 2)))),
                    'origin_diff_mm': float(np.linalg.norm(Tw[:3, 3] - Tv[:3, 3]) * 1000),
                    'rpy_deg_RzRyRx': plans[th]['cameras'][2]['rpy_deg'],
                    'xyz_mm_F': plans[th]['cameras'][2]['xyz_mm']}
    report = {'shipped_U3_F0_depth_T_reproduced_maxabs': float(dT), 'variant_vs_inplace_rotation': conv, 'rows': [], 'grid': [], 'bar_rows': []}

    # handle-bar proxy in F: 100 mm bar along F x at F+Z 0.085 (TCP), 21 points; plus radius offsets (+-13 mm in F y and z)
    bar_x = np.linspace(-0.05, 0.05, 21)
    bar_F = np.column_stack([bar_x, np.zeros(21), np.full(21, 0.085)])
    for o in OPENINGS:
        q = dict(q0); q['arm_j7'] = o; q['arm_j8'] = -o
        P, parts = robot.scene(q); TFo = P['arm_body6_to_gripper']
        assert np.allclose(TFo, TF)
        # finger surface samples (area weighted), classified in F frame
        fing = {}
        for name, seed in (('arm_body7', 310), ('arm_body8', 311)):
            part = next(p for p in parts if p.name == name)
            m = trimesh.Trimesh(part.vertices, part.faces, process=False)
            samples, fidx = trimesh.sample.sample_surface(m, 1500, seed=seed)
            nB = m.face_normals[fidx]
            sF = inv(TF, samples); nF = nB @ TF[:3, :3]
            inner = np.array([0, 1, 0]) if name == 'arm_body7' else np.array([0, -1, 0])
            pad = (nF @ inner > 0.9) & (sF[:, 2] > 0.075) & (sF[:, 2] < 0.130)
            tip = sF[:, 2] > (sF[:, 2].max() - 0.010)
            fing[name] = {'all': samples, 'pad': samples[pad], 'tip': samples[tip], 'zF_max': float(sF[:, 2].max()),
                          'inner_face_yF': float(sF[pad, 1].mean()) if pad.any() else None}
        bar_B = apply(TF, bar_F)
        for th in THETAS:
            plan = plans[th]; cam = camera_scene(plan, P)['wrist']; bvh = scene_bvh(plan, P, parts)
            for st, s in cam['streams'].items():
                if st == 'right_ir':
                    pass
                T = s['T_B_O']; origin = s['origin']
                row = {'theta_deg': th, 'opening_joint_m': o, 'inner_gap_mm': round(2000 * o, 1), 'stream': st}
                # bar
                p, uv, inside, gate = projection(T, s, bar_B)
                clear, ix = ray_clear(bvh, origin, bar_B, 0.004)
                row['bar_in_frustum_minz_frac'] = float(gate.mean())
                row['bar_visible_frac'] = float((gate & clear).mean())
                row['bar_centre_v_frac'] = float(uv[10, 1] / s['height']); row['bar_centre_u_frac'] = float(uv[10, 0] / s['width'])
                row['bar_centre_z_m'] = float(p[10, 2])
                blockers = [bvh.parts[i].name for i in ix if i >= 0]
                row['bar_first_blockers'] = sorted(set(blockers))
                # finger pads / tips
                for name in ('arm_body7', 'arm_body8'):
                    for cls in ('pad', 'tip', 'all'):
                        pts = fing[name][cls]
                        if len(pts) == 0:
                            row[f'{name}_{cls}_visible_frac'] = None; continue
                        p, uv, inside, gate = projection(T, s, pts)
                        clear, ix = ray_clear(bvh, origin, pts, 0.00015)
                        row[f'{name}_{cls}_n'] = int(len(pts))
                        row[f'{name}_{cls}_in_frustum_minz_frac'] = float(gate.mean())
                        row[f'{name}_{cls}_visible_frac'] = float((gate & clear).mean())
                        if cls == 'tip':
                            vv = uv[gate, 1] / s['height'] if gate.any() else np.array([np.nan])
                            row[f'{name}_tip_v_frac_median'] = float(np.nanmedian(vv)) if gate.any() else None
                report['rows'].append(row)
                # pixel-lattice ray grid (numerical ray sampling, not rendering)
                w, h = 212, 120
                u = (np.arange(w) + .5) * s['width'] / w; v = (np.arange(h) + .5) * s['height'] / h
                uu, vv = np.meshgrid(u, v); K = np.array(s['K']); z = 3.0
                endsO = np.column_stack([(uu.ravel() - K[0, 2]) / K[0, 0] * z, (vv.ravel() - K[1, 2]) / K[1, 1] * z, np.full(w * h, z)])
                ends = apply(T, endsO)
                ts, ix = bvh.trace(np.broadcast_to(origin, ends.shape), ends)
                names = np.array([bvh.parts[i].name if i >= 0 else 'NONE' for i in ix]).reshape(h, w)
                zhit = (ts * z).reshape(h, w)
                grip = np.isin(names, list(GRIPPER)); anyhit = names != 'NONE'
                br = np.isin(names, [b['name'] for b in plan['brackets']])
                lower_half = np.zeros((h, w), bool); lower_half[h // 2:, :] = True
                lower_third = np.zeros((h, w), bool); lower_third[2 * h // 3:, :] = True
                rows_with_grip = np.flatnonzero(grip.any(1))
                g = {'theta_deg': th, 'opening_joint_m': o, 'stream': st, 'grid': [w, h],
                     'gripper_first_hit_frac_full': float(grip.mean()),
                     'gripper_first_hit_frac_lower_half': float(grip[lower_half].mean()),
                     'gripper_first_hit_frac_lower_third': float(grip[lower_third].mean()),
                     'supports_first_hit_frac_full': float(br.mean()),
                     'any_robot_first_hit_frac_full': float(anyhit.mean()),
                     'hit_before_minz_frac_full': float((anyhit & (zhit < s['min_z_mask_m'])).mean()),
                     'gripper_topmost_row_frac': float(rows_with_grip.min() / h) if rows_with_grip.size else None,
                     'gripper_row_span_frac': [float(rows_with_grip.min() / h), float((rows_with_grip.max() + 1) / h)] if rows_with_grip.size else None,
                     'gripper_nearest_hit_z_m': float(zhit[grip].min()) if grip.any() else None}
                report['grid'].append(g)
                np.savez_compressed(OUT / f'U3_F{th}_{st}_opening{int(o*1000):02d}_ray_grid.npz', first_hit_link=names, hit_Z_m=zhit)
            print(f'theta {th} opening {o} done {time.time()-t0:.0f}s', flush=True)
        report['finger_geometry_F'] = {n: {'zF_max_m': fing[n]['zF_max'], 'inner_face_yF_m': fing[n]['inner_face_yF'],
                                           'n_pad': int(len(fing[n]['pad'])), 'n_tip': int(len(fing[n]['tip']))} for n in fing}
    report['runtime_s'] = time.time() - t0
    save_json(OUT / 't1_occlusion.json', report)
    # compact markdown
    lines = ['| theta | joint o (m) / gap (mm) | stream | bar in-frustum+minz | bar visible (ray) | bar centre v | f7 pad vis | f8 pad vis | f7 tip vis | f8 tip vis | tip v (f7/f8) | blockers |', '|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|']
    for r in report['rows']:
        if r['stream'] == 'right_ir':
            continue
        def f(x):
            return '-' if x is None else f'{100*x:.0f}%'
        tv = f"{r.get('arm_body7_tip_v_frac_median')}/{r.get('arm_body8_tip_v_frac_median')}"
        lines.append(f"| {r['theta_deg']} | {r['opening_joint_m']} / {r['inner_gap_mm']} | {r['stream']} | {f(r['bar_in_frustum_minz_frac'])} | {f(r['bar_visible_frac'])} | {r['bar_centre_v_frac']:.2f} | "
                     f"{f(r['arm_body7_pad_visible_frac'])} | {f(r['arm_body8_pad_visible_frac'])} | {f(r['arm_body7_tip_visible_frac'])} | {f(r['arm_body8_tip_visible_frac'])} | {tv} | {','.join(r['bar_first_blockers']) or '-'} |")
    lines += ['', '| theta | o (m) | stream | gripper share full | lower half | lower third | topmost gripper row | supports share | hit<minZ share |', '|---|---|---|---:|---:|---:|---:|---:|---:|']
    for g in report['grid']:
        if g['stream'] == 'right_ir':
            continue
        top = '-' if g['gripper_topmost_row_frac'] is None else f"{g['gripper_topmost_row_frac']:.2f}"
        lines.append(f"| {g['theta_deg']} | {g['opening_joint_m']} | {g['stream']} | {100*g['gripper_first_hit_frac_full']:.1f}% | {100*g['gripper_first_hit_frac_lower_half']:.1f}% | {100*g['gripper_first_hit_frac_lower_third']:.1f}% | {top} | {100*g['supports_first_hit_frac_full']:.1f}% | {100*g['hit_before_minz_frac_full']:.1f}% |")
    (OUT / 't1_occlusion.md').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))
    print(json.dumps(serial(report['variant_vs_inplace_rotation']), indent=1))
    print('shipped U3_F0 depth T reproduced, max abs diff', dT)


if __name__ == '__main__':
    main()
