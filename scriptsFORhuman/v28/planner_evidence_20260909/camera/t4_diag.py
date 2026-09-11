#!/usr/bin/env python3
"""Diagnose the Stage-4 right-door panel penetrations found by t4_clearance.py (plan F40)."""
import csv, json, math, collections
from pathlib import Path
import numpy as np
import sys
sys.path.insert(0, '/tmp/v28_team/camera')
from t4_clearance import TRAJ, VAR, rz, quat_R, load_items, sdf_box, fit_width, GAP, H_NOM

items = load_items(VAR / 'U3_F40.json')
ptsF, tags, names = items
out = {}
for cell, side in (('C_S2', 'right'), ('C_S2', 'left'), ('C_S21', 'right')):
    rows = [r for r in csv.DictReader(open(TRAJ)) if r['cell'] == cell and r['side'] == side]
    s = 1.0 if side == 'left' else -1.0
    by_env = collections.defaultdict(list)
    for r in rows:
        by_env[int(r['env_id'])].append(r)
    W = {e: fit_width(rr, s)['W'] for e, rr in by_env.items()}
    sgn = -s
    rec = []
    for r in rows:
        if int(r['stage']) != 4:
            continue
        e = int(r['env_id'])
        T_D_B = np.eye(4); T_D_B[:3, :3] = quat_R(np.array([float(r[f'base_quat_D_wxyz_{k}']) for k in range(4)])); T_D_B[:3, 3] = [float(r[f'base_pos_D_{k}']) for k in range(3)]
        T_B_F = np.eye(4); T_B_F[:3, :3] = quat_R(np.array([float(r[f'flange_quat_B_wxyz_{k}']) for k in range(4)])); T_B_F[:3, 3] = [float(r[f'flange_pos_B_{k}']) for k in range(3)]
        T = T_D_B @ T_B_F
        a = float(r['hinge_rad']); hinge = np.array([0.02, -s * W[e] / 2, 0.0]); Rp = rz(sgn * a)
        pD = ptsF @ T[:3, :3].T + T[:3, 3]
        pP = (pD - hinge) @ Rp
        centre = np.array([-0.02, s * W[e] / 2, H_NOM / 2]); half = np.array([0.02, W[e] / 2 - GAP, H_NOM / 2 - GAP])
        d = sdf_box(pP - centre, half)
        fP = (T[:3, 3] - hinge) @ Rp
        df = sdf_box(fP - centre, half)
        towerP = Rp.T @ T[:3, :3] @ np.array([0, 0, 1.0])   # F+Y (tower axis) in panel frame -- placeholder replaced below
        towerP = Rp.T @ (T[:3, :3] @ np.array([0, 1.0, 0]))
        fz = Rp.T @ (T[:3, :3] @ np.array([0, 0, 1.0]))
        q = [float(r[f'arm_joint_pos_{i}']) for i in range(6)]
        htcp = np.array([float(r[f'handle_pos_TCP_{i}']) for i in range(3)])
        i = int(np.argmin(d))
        rec.append({'env': e, 'step': int(r['step_index']), 'hinge_deg': math.degrees(a), 'handle_rad': float(r['handle_rad']), 'min_sdf_mm': 1000 * d[i], 'item': tags[i],
                    'pt_panel_frame': pP[i].round(3).tolist(), 'flange_panel_frame': fP.round(3).tolist(), 'flange_sdf_mm': 1000 * df,
                    'tower_axis_panel_frame': towerP.round(2).tolist(), 'flange_z_axis_panel_frame': fz.round(2).tolist(), 'q': np.round(q, 2).tolist(),
                    'handle_dist_tcp_m': float(np.linalg.norm(htcp)), 'base_pos_D': [float(r[f'base_pos_D_{k}']) for k in range(3)], 'reason': r['sample_reason'], 'terminal': r['terminal_reason']})
    pen = [x for x in rec if x['min_sdf_mm'] < 0]
    print(f'== {cell}/{side} stage4 frames {len(rec)} penetrating {len(pen)} ({100*len(pen)/max(1,len(rec)):.0f}%)')
    if pen:
        hd = np.array([x['hinge_deg'] for x in pen]); tcp = np.array([x['handle_dist_tcp_m'] for x in pen]); fl = np.array([x['flange_sdf_mm'] for x in pen])
        fx = np.array([x['flange_panel_frame'][0] for x in pen]); pz = np.array([x['pt_panel_frame'][2] for x in pen]); py = np.array([x['pt_panel_frame'][1] for x in pen])
        tx = np.array([x['tower_axis_panel_frame'][0] for x in pen]); q5 = np.array([x['q'][4] for x in pen]); q6 = np.array([x['q'][5] for x in pen])
        print('  hinge deg p5/p50/p95', np.percentile(hd, [5, 50, 95]).round(0), ' handle-TCP dist p5/50/95', np.percentile(tcp, [5, 50, 95]).round(3))
        print('  flange origin SDF to panel mm p5/50/95', np.percentile(fl, [5, 50, 95]).round(0), ' flange x in panel frame p5/50/95', np.percentile(fx, [5, 50, 95]).round(3))
        print('  penetrating point: panel-frame z p5/50/95', np.percentile(pz, [5, 50, 95]).round(2), ' y along panel from hinge p5/50/95', np.percentile(py, [5, 50, 95]).round(2))
        print('  tower axis x-comp in panel frame (toward +x = into door) p5/50/95', np.percentile(tx, [5, 50, 95]).round(2), ' q5 p5/50/95', np.percentile(q5, [5, 50, 95]).round(2), ' q6', np.percentile(q6, [5, 50, 95]).round(2))
        print('  envs with penetration', len(set(x['env'] for x in pen)), 'of', len(set(x['env'] for x in rec)), ' items', collections.Counter(x['item'] for x in pen).most_common(3))
        print('  sample reasons', collections.Counter(x['reason'] for x in pen).most_common(3), ' terminals', collections.Counter(x['terminal'] for x in pen).most_common(3))
        ex = sorted(pen, key=lambda x: x['min_sdf_mm'])[0]
        print('  worst example', json.dumps(ex))
    out[f'{cell}/{side}'] = {'frames': len(rec), 'penetrating': len(pen), 'examples': sorted(pen, key=lambda x: x['min_sdf_mm'])[:3]}
Path('/tmp/v28_team/camera/t4/t4_diag.json').write_text(json.dumps(out, indent=1))
