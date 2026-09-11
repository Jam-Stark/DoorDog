#!/usr/bin/env python3
"""W4: mesh ray-cast near-field occlusion for LOWER wrist towers (V28-D028 candidates).

Re-uses the read-only Vpiper-Plate-Dual-D435i package tooling exactly as
planner_evidence_20260909/camera/t1_occlusion.py does (scratch copy under
/tmp/v28_team/camera/pkgcode; BUNDLE points at the read-only package).  The only change is
that the wrist camera mount frame is translated along the tower axis (B +Z at the reference
posture) from 180 mm to 140 / 120 mm, with the tilt set to the D028 pairing.

Scope note: the *bracket* envelopes are left at the 180 mm design, so the 'supports share'
column is not valid for the lowered towers; the finger / handle-bar columns are, because the
first blockers there are arm_body6_to_gripper and arm_body8 (t1 REPORT.md:23).
"""
import sys, json, math, time
sys.path.insert(0, '/tmp/v28_team/camera/pkgcode')
from geometry import *            # noqa
from build_u3_forward import make_variant
import trimesh

OUT = Path('/tmp/v28_team2/camera/out'); OUT.mkdir(parents=True, exist_ok=True)
CONFIGS = [(45.0, 0.180), (38.76, 0.140), (34.49, 0.120), (29.13, 0.100)]
OPENINGS = [0.0, 0.013, 0.020, 0.035]


def projection(T, s, points):
    p = inv(T, points); K = np.asarray(s['K']); z = p[:, 2]
    den = np.where(abs(z) > 1e-12, z, np.nan)
    uv = np.column_stack([K[0, 0] * p[:, 0] / den + K[0, 2], K[1, 1] * p[:, 1] / den + K[1, 2]])
    inside = np.isfinite(uv).all(1) & (z > 0) & (uv[:, 0] >= 0) & (uv[:, 0] <= s['width']) & (uv[:, 1] >= 0) & (uv[:, 1] <= s['height'])
    return p, uv, inside, inside & (z >= s['min_z_mask_m'])


def lower_tower(plan, TF, height):
    """Move the wrist camera mount frame from 180 mm to `height` along the tower axis (B +Z)."""
    c = plan['cameras'][2]
    TM = np.array(c['T_parent_M'], float)
    RBF = TF[:3, :3]
    dF = RBF.T @ np.array([0.0, 0.0, height - 0.180])
    TM[:3, 3] = TM[:3, 3] + dF
    c['T_parent_M'] = TM.tolist()
    c['xyz_m'] = TM[:3, 3].tolist()
    for st, s in c['streams'].items():
        mo = np.eye(4); mo[:3, :3] = R_M_O; mo[:3, 3] = s['offset_M_m']
        TO = TM @ mo
        s['T_parent_optical'] = TO.tolist()
    return plan


def main():
    t0 = time.time()
    robot = Robot(BUNDLE / 'robot')
    q0 = json.load(open(BUNDLE / 'config/reference_joint_pose.json'))
    q0.update({f'arm_j{i+1}': x for i, x in enumerate([0, 0, 0, 0, 0, 1.57])})
    source = json.load(open(BUNDLE / 'source/U3_V_previous.json'))
    TF = robot.fk(q0)['arm_body6_to_gripper']

    bar_x = np.linspace(-0.05, 0.05, 21)
    bar_F = np.column_stack([bar_x, np.zeros(21), np.full(21, 0.085)])
    rows = []
    for o in OPENINGS:
        q = dict(q0); q['arm_j7'] = o; q['arm_j8'] = -o
        P, parts = robot.scene(q)
        fing = {}
        for name, seed in (('arm_body7', 310), ('arm_body8', 311)):
            part = next(p for p in parts if p.name == name)
            m = trimesh.Trimesh(part.vertices, part.faces, process=False)
            samples, fidx = trimesh.sample.sample_surface(m, 1500, seed=seed)
            sF = inv(TF, samples)
            tip = sF[:, 2] > (sF[:, 2].max() - 0.010)
            fing[name] = {'tip': samples[tip]}
        bar_B = apply(TF, bar_F)
        for theta, h in CONFIGS:
            plan = lower_tower(make_variant(source, TF, f'U3_F{theta}', theta), TF, h)
            cam = camera_scene(plan, P)['wrist']
            pp = [p for p in parts if p.group != 'leg']
            bvh = BVH(pp)
            for st, s in cam['streams'].items():
                if st == 'right_ir':
                    continue
                T, origin = s['T_B_O'], s['origin']
                p, uv, inside, gate = projection(T, s, bar_B)
                d = bar_B - origin
                end = bar_B - d * (0.004 / np.linalg.norm(d, axis=1))[:, None]
                ts, ix = bvh.trace(np.broadcast_to(origin, end.shape), end)
                clear = ix < 0
                row = {'theta_deg': theta, 'tower_mm': int(1000 * h), 'opening_m': o, 'stream': st,
                       'bar_in_frustum_minz': float(gate.mean()),
                       'bar_visible': float((gate & clear).mean()),
                       'bar_centre_v_frac': float(uv[10, 1] / s['height']),
                       'bar_centre_z_m': float(p[10, 2]),
                       'blockers': sorted({bvh.parts[i].name for i in ix if i >= 0})}
                for name in ('arm_body7', 'arm_body8'):
                    pts = fing[name]['tip']
                    p2, uv2, ins2, g2 = projection(T, s, pts)
                    d2 = pts - origin
                    e2 = pts - d2 * (0.00015 / np.linalg.norm(d2, axis=1))[:, None]
                    ts2, ix2 = bvh.trace(np.broadcast_to(origin, e2.shape), e2)
                    row[f'{name}_tip_visible'] = float((g2 & (ix2 < 0)).mean())
                rows.append(row)
            print(f'theta {theta} h {h} o {o} done {time.time()-t0:.0f}s', flush=True)
    (OUT / 'w4_tower_height_occl.json').write_text(json.dumps(rows, indent=1))
    lines = ['| theta | tower mm | opening m | stream | bar in-frustum+MinZ | bar visible (ray) | bar centre row | f7 tip vis | f8 tip vis | blockers |',
             '|---:|---:|---:|---|---:|---:|---:|---:|---:|---|']
    for r in rows:
        lines.append(f"| {r['theta_deg']} | {r['tower_mm']} | {r['opening_m']} | {r['stream']} | {100*r['bar_in_frustum_minz']:.0f}% | "
                     f"{100*r['bar_visible']:.0f}% | {r['bar_centre_v_frac']:.2f} | {100*r['arm_body7_tip_visible']:.0f}% | "
                     f"{100*r['arm_body8_tip_visible']:.0f}% | {','.join(r['blockers']) or '-'} |")
    (OUT / 'w4_tower_height_occl.md').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
