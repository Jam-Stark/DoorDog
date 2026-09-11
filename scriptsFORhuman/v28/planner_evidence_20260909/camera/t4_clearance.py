#!/usr/bin/env python3
"""Task 4: tower/housing vs door clearance sweep along the archived v27 traces (pure geometry, CPU).

Envelopes (F frame, from the variant JSON brackets + wrist housing box) are placed with T_D_F = T_D_B @ T_B_F
from each trace row; the door is rebuilt in the trace's door frame D from the env_rand/door.py construction
(panel: box half-thickness 0.02, hinge line x=0.02, y=-side*W/2; frame/covers: x in [-0.08, 0.04]).
W (door width) is FITTED per env from the handle trajectory (hinge rotation of the grasp target) when enough
opened frames exist, else the precheck W_est convention is used.  H (door height) nominal 1.9 m (lowest of the
1.9-2.2 range -> lowest lintel).  Handle: lever capsule (L nominal 0.125, r 0.013) + axle (0.195) + hook (0.05).
Sampled trace frames only (dense 50 Hz for Stage 2/3, sparser for Stage 4/5) -> min clearance is an upper bound.
"""
import csv, json, math, sys, time, collections
from pathlib import Path
import numpy as np

TRAJ = Path('/home/baoquanc/workspace/DoorDog-A2-Piper-v13-student-distillation-20260717_2103/camera_setup/A2-Rail-Dual-D435i/data/camera_trajectories.csv')
VAR = Path('/tmp/v28_team/camera/variants')
F0 = Path('/home/baoquanc/workspace/DoorDog-A2-Piper-v13-student-distillation-20260717_2103/camera_setup/Vpiper-Plate-Dual-D435i/config/U3_F0.json')
OUT = Path('/tmp/v28_team/camera/t4'); OUT.mkdir(parents=True, exist_ok=True)
CELLS = {'C_S2', 'C_S21'}
H_NOM, L_NOM, R_NOM, AXLE_NOM, HOOK_NOM, COVER_NOM, GAP = 1.9, 0.125, 0.013, 0.195, 0.05, 0.04, 0.002


def rz(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def quat_R(q):
    w, x, y, z = q / np.linalg.norm(q)
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def box_surface_points(size, pitch=0.005):
    """Points on the surface of an axis-aligned box centred at 0 (corners, edges, faces at ~pitch)."""
    h = np.asarray(size) / 2
    axes = [np.unique(np.concatenate([np.linspace(-h[i], h[i], max(2, int(math.ceil(size[i] / pitch)) + 1))])) for i in range(3)]
    pts = []
    for ax in range(3):
        o = [i for i in range(3) if i != ax]
        g = np.array(np.meshgrid(axes[o[0]], axes[o[1]], indexing='ij')).reshape(2, -1).T
        for sgn in (-1, 1):
            p = np.zeros((len(g), 3)); p[:, o[0]] = g[:, 0]; p[:, o[1]] = g[:, 1]; p[:, ax] = sgn * h[ax]
            pts.append(p)
    return np.unique(np.round(np.concatenate(pts), 9), axis=0)


def sdf_box(p, half):
    """Signed distance of points p (..., 3) to an axis-aligned box with half extents (3,) at origin."""
    q = np.abs(p) - half
    outside = np.linalg.norm(np.maximum(q, 0.0), axis=-1)
    inside = np.minimum(np.max(q, axis=-1), 0.0)
    return outside + inside


def sdf_capsule(p, a, b, r):
    ab = b - a
    t = np.clip(np.einsum('...i,i->...', p - a, ab) / (ab @ ab), 0.0, 1.0)
    return np.linalg.norm(p - (a + t[..., None] * ab), axis=-1) - r


def load_items(plan_path):
    plan = json.load(open(plan_path))
    items = []
    for b in plan['brackets']:
        if b['parent'] == 'arm_body6_to_gripper':
            items.append((b['name'], np.array(b['T_parent_item']), np.array(b['size_m'])))
    w = plan['cameras'][2]
    assert w['name'] == 'wrist' and w['parent'] == 'arm_body6_to_gripper'
    items.append(('wrist_housing', np.array(w['T_parent_M']), np.array(plan['housing_size_M_m'])))
    pts = []; tags = []
    for name, T, size in items:
        p = box_surface_points(size, 0.005)
        pts.append(p @ T[:3, :3].T + T[:3, 3]); tags += [name] * len(p)
    return np.concatenate(pts), np.array(tags), [i[0] for i in items]


def fit_width(rows, side_sign):
    """Fit W from opened, released frames: G(a) = hinge + Rz(sgn*a)(G0 - hinge), hinge = (0.02, -side*W/2, 0)."""
    G = np.array([[float(r[f'handle_pos_D_{i}']) for i in range(3)] for r in rows])
    a = np.array([float(r['hinge_rad']) for r in rows]); hr = np.array([float(r['handle_rad']) for r in rows])
    closed = np.flatnonzero((np.abs(a) < 0.01) & (np.abs(hr) < 0.02))
    opened = np.flatnonzero((a > 0.25) & (np.abs(hr) < 0.02))
    if closed.size == 0 or opened.size < 3:
        return None
    G0 = G[closed].mean(0)
    best = None
    for sgn in (-1.0, 1.0):
        for W in np.arange(0.80, 1.1001, 0.001):
            hinge = np.array([0.02, -side_sign * W / 2, 0.0])
            pred = np.stack([hinge + rz(sgn * aa) @ (G0 - hinge) for aa in a[opened]])
            res = np.sqrt(np.mean(np.sum((pred[:, :2] - G[opened, :2]) ** 2, axis=1)))
            if best is None or res < best[0]:
                best = (res, W, sgn)
    return {'rms_m': best[0], 'W': best[1], 'sgn': best[2], 'n_opened': int(opened.size)}


def fit_lever_half(rows):
    h = np.array([float(r['handle_height_m']) for r in rows]); Gz = np.array([float(r['handle_pos_D_2']) for r in rows])
    hr = np.array([float(r['handle_rad']) for r in rows]); a = np.array([float(r['hinge_rad']) for r in rows])
    m = (hr > 0.3) & (np.abs(a) < 0.05)
    if m.sum() < 3:
        return None
    return float(np.median((h[m] - Gz[m]) / np.sin(hr[m])))


def main():
    t0 = time.time()
    plans = {'F0': F0, 'F40': VAR / 'U3_F40.json', 'F45': VAR / 'U3_F45.json'}
    items = {k: load_items(v) for k, v in plans.items()}
    rows_by_lane = collections.defaultdict(list)
    with open(TRAJ) as f:
        for r in csv.DictReader(f):
            if r['cell'] in CELLS:
                rows_by_lane[(r['cell'], r['side'])].append(r)
    report = {'plans': {k: str(v) for k, v in plans.items()}, 'items': {k: v[2] for k, v in items.items()},
              'points_per_plan': {k: int(len(v[0])) for k, v in items.items()}, 'lanes': {}, 'width_fits': {}, 'lever_fits': {}}
    for (cell, side), rows in sorted(rows_by_lane.items()):
        s = 1.0 if side == 'left' else -1.0
        rows.sort(key=lambda r: (int(r['env_id']), int(r['step_index'])))
        by_env = collections.defaultdict(list)
        for r in rows:
            by_env[int(r['env_id'])].append(r)
        fits = {e: fit_width(rr, s) for e, rr in by_env.items()}
        lever = [fit_lever_half(rr) for rr in by_env.values()]
        lever = [x for x in lever if x is not None]
        Ws = {e: (f['W'] if f and f['rms_m'] < 0.02 else None) for e, f in fits.items()}
        sgns = collections.Counter(f['sgn'] for f in fits.values() if f and f['rms_m'] < 0.02)
        rms = [f['rms_m'] for f in fits.values() if f]
        report['width_fits'][f'{cell}/{side}'] = {'envs': len(by_env), 'fitted': sum(w is not None for w in Ws.values()), 'rotation_sign_votes': dict(sgns),
                                                  'W_p5_p50_p95': [float(np.percentile([w for w in Ws.values() if w is not None], q)) for q in (5, 50, 95)] if any(w is not None for w in Ws.values()) else None,
                                                  'fit_rms_p50_max_m': [float(np.median(rms)), float(np.max(rms))] if rms else None}
        report['lever_fits'][f'{cell}/{side}'] = {'L_half_median_m': float(np.median(lever)) if lever else None, 'n_envs': len(lever)}
        sgn = -s  # precheck convention rz(-side*hinge); overridden if the fit says otherwise
        if sgns and sgns.most_common(1)[0][0] != -s:
            sgn = sgns.most_common(1)[0][0]
        # per-frame door geometry
        N = len(rows)
        T_D_F = np.zeros((N, 4, 4)); hinge_a = np.zeros(N); hr = np.zeros(N); G = np.zeros((N, 3)); Wf = np.zeros(N); stage = np.zeros(N, int); hh = np.zeros(N)
        W_est_prev = {}
        for i, r in enumerate(rows):
            e = int(r['env_id'])
            T_D_B = np.eye(4); T_D_B[:3, :3] = quat_R(np.array([float(r[f'base_quat_D_wxyz_{k}']) for k in range(4)])); T_D_B[:3, 3] = [float(r[f'base_pos_D_{k}']) for k in range(3)]
            T_B_F = np.eye(4); T_B_F[:3, :3] = quat_R(np.array([float(r[f'flange_quat_B_wxyz_{k}']) for k in range(4)])); T_B_F[:3, 3] = [float(r[f'flange_pos_B_{k}']) for k in range(3)]
            T_D_F[i] = T_D_B @ T_B_F
            hinge_a[i] = float(r['hinge_rad']); hr[i] = float(r['handle_rad']); G[i] = [float(r[f'handle_pos_D_{k}']) for k in range(3)]
            stage[i] = int(r['stage']); hh[i] = float(r['handle_height_m'])
            if Ws.get(e) is not None:
                Wf[i] = Ws[e]
            else:
                if e not in W_est_prev:
                    W_est_prev[e] = float(min(max(2.0 * (abs(G[i, 1]) + 0.115), 0.8), 1.1))
                Wf[i] = W_est_prev[e]
        lane_out = {}
        for pk, (ptsF, tags, names) in items.items():
            P = len(ptsF)
            d_panel = np.full(N, np.inf); d_handle = np.full(N, np.inf); d_frame = np.full(N, np.inf)
            arg_panel = np.zeros(N, int)
            for c0 in range(0, N, 1500):
                sl = slice(c0, min(N, c0 + 1500)); n = sl.stop - sl.start
                T = T_D_F[sl]
                pD = np.einsum('nij,pj->npi', T[:, :3, :3], ptsF) + T[:, None, :3, 3]          # (n,P,3)
                # panel frame: origin hinge, R = rz(sgn*a)
                W = Wf[sl]; a = hinge_a[sl]
                hinge = np.stack([np.full(n, 0.02), -s * W / 2, np.zeros(n)], 1)
                Rp = np.stack([rz(sgn * aa) for aa in a])                                       # (n,3,3) panel->D
                pP = np.einsum('nji,npj->npi', Rp, pD - hinge[:, None, :])                       # into panel frame
                centre = np.stack([np.full(n, -0.02), s * W / 2, np.full(n, H_NOM / 2)], 1)
                half = np.stack([np.full(n, 0.02), W / 2 - GAP, np.full(n, H_NOM / 2 - GAP)], 1)
                dp = sdf_box(pP - centre[:, None, :], half[:, None, :])
                d_panel[sl] = dp.min(1); arg_panel[sl] = dp.argmin(1)
                # handle in panel frame: grasp target G -> panel frame
                GP = np.einsum('nji,nj->ni', Rp, G[sl] - hinge)
                lever_dir = np.stack([np.zeros(n), -s * np.cos(hr[sl]), -np.sin(hr[sl])], 1)   # tip goes down when pressed (assumption, checked by lever fit)
                S = GP - lever_dir * (L_NOM / 2); Tip = GP + lever_dir * (L_NOM / 2)
                dh = np.full((n, P), np.inf)
                for k in range(n):
                    dh[k] = np.minimum.reduce([sdf_capsule(pP[k], S[k], Tip[k], R_NOM),
                                               sdf_capsule(pP[k], S[k], S[k] + np.array([AXLE_NOM, 0, 0]), R_NOM),
                                               sdf_capsule(pP[k], Tip[k], Tip[k] + np.array([HOOK_NOM, 0, 0]), R_NOM)])
                d_handle[sl] = dh.min(1)
                # static frame in D: jambs (wall+cover union) and lintel
                jamb_h_c = np.stack([np.full(n, -0.02), s * (W / 2 - GAP + 0.5), np.full(n, 1.5)], 1); jamb_half = np.stack([np.full(n, 0.06), np.full(n, 0.5), np.full(n, 1.5)], 1)
                jamb_g_c = np.stack([np.full(n, -0.02), -s * (W / 2 - GAP + 0.5), np.full(n, 1.5)], 1)
                lintel_c = np.stack([np.full(n, -0.02), np.zeros(n), np.full(n, H_NOM + 0.5)], 1); lintel_half = np.stack([np.full(n, 0.06), W / 2, np.full(n, 0.5)], 1)
                df = np.minimum.reduce([sdf_box(pD - jamb_h_c[:, None, :], jamb_half[:, None, :]), sdf_box(pD - jamb_g_c[:, None, :], jamb_half[:, None, :]),
                                        sdf_box(pD - lintel_c[:, None, :], lintel_half[:, None, :])])
                d_frame[sl] = df.min(1)
            per_stage = {}
            for st in sorted(set(stage)):
                m = stage == st
                def q(v):
                    return {'min': float(v.min()), 'p1': float(np.percentile(v, 1)), 'p5': float(np.percentile(v, 5)), 'p50': float(np.percentile(v, 50)),
                            'share_lt_0': float(np.mean(v < 0)), 'share_lt_20mm': float(np.mean(v < 0.02))}
                worst = collections.Counter(tags[arg_panel[m][d_panel[m] < 0.05]].tolist())
                per_stage[f'stage{st}'] = {'frames': int(m.sum()), 'panel': q(d_panel[m]), 'handle': q(d_handle[m]), 'frame': q(d_frame[m]),
                                           'panel_closest_item_when_lt_50mm': dict(worst)}
            lane_out[pk] = per_stage
            print(f'{cell}/{side} {pk} done {time.time()-t0:.0f}s', flush=True)
        report['lanes'][f'{cell}/{side}'] = {'frames': N, 'rotation_sign_used': sgn, 'per_plan': lane_out}
    report['runtime_s'] = time.time() - t0
    (OUT / 't4_clearance.json').write_text(json.dumps(report, indent=1))
    # markdown
    lines = ['| lane | stage | frames | plan | panel min / p1 / p5 (mm) | panel <20mm share | panel <0 share | handle min / p5 (mm) | frame min / p5 (mm) | closest item (panel<50mm) |', '|---|---|---:|---|---|---:|---:|---|---|---|']
    for lane, d in report['lanes'].items():
        for pk, ps in d['per_plan'].items():
            for st, e in ps.items():
                p, h, f = e['panel'], e['handle'], e['frame']
                lines.append(f"| {lane} | {st} | {e['frames']} | {pk} | {1000*p['min']:.0f} / {1000*p['p1']:.0f} / {1000*p['p5']:.0f} | {100*p['share_lt_20mm']:.1f}% | {100*p['share_lt_0']:.1f}% | {1000*h['min']:.0f} / {1000*h['p5']:.0f} | {1000*f['min']:.0f} / {1000*f['p5']:.0f} | {e['panel_closest_item_when_lt_50mm']} |")
    lines += ['', '## width / lever fits', '```', json.dumps(report['width_fits'], indent=1), json.dumps(report['lever_fits'], indent=1), '```']
    (OUT / 't4_clearance.md').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines[:60]))
    print(json.dumps(report['width_fits'], indent=1)); print(json.dumps(report['lever_fits'], indent=1))


if __name__ == '__main__':
    main()
