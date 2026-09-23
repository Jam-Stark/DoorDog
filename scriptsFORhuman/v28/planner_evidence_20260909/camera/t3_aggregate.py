#!/usr/bin/env python3
"""Aggregate the six precheck runs (t3/<variant>/u3f0_geometry_precheck.json) into comparison tables."""
import json
from pathlib import Path
import numpy as np

T3 = Path('/tmp/v28_team/camera/t3')
RUNS = {k: json.load(open(T3 / k / 'u3f0_geometry_precheck.json')) for k in ('U3_F40', 'U3_F40_B12', 'U3_F40_B15', 'U3_F40_B20', 'U3_F45', 'U3_F45_B12', 'U3_F45_B15')}
BASE = {'asym(L32/R12)': 'U3_F40', 'B12 sym': 'U3_F40_B12', 'B15 sym': 'U3_F40_B15', 'B20 sym': 'U3_F40_B20'}
LANES = ['C_S2/left', 'C_S2/right', 'C_S21/left', 'C_S21/right']
STAGES = ['stage2', 'stage3', 'stage4', 'stage5']
out = []


def pct(x):
    return '-' if x is None else f'{100*x:.0f}'


def v(run, lane, st, key):
    return RUNS[run]['lanes'][lane][st]['in_frustum_share'].get(key)


out.append('### A. Handle visibility per lane/stage (share of trace frames; base: pinhole+MinZ+arm-capsule clear; wrist: pinhole+MinZ, no mesh occlusion)')
out.append('| lane | stage | n | L-RGB clear asym/B12/B15/B20 | R-RGB clear asym/B12/B15/B20 | L-D asym/B12/B15/B20 | R-D asym/B12/B15/B20 | W-RGB th40/th45 | W-D th40/th45 | W-D TCP th40/th45 |')
out.append('|---|---|---:|---|---|---|---|---|---|---|')
for lane in LANES:
    for st in STAGES:
        n = RUNS['U3_F40']['lanes'][lane][st]['frames']
        cols = []
        for key in ('base_left/rgb/handle/arm_clear', 'base_right/rgb/handle/arm_clear', 'base_left/depth/handle', 'base_right/depth/handle'):
            cols.append('/'.join(pct(v(r, lane, st, key)) for r in BASE.values()))
        cols.append('/'.join(pct(v(r, lane, st, 'wrist/rgb/handle')) for r in ('U3_F40', 'U3_F45')))
        cols.append('/'.join(pct(v(r, lane, st, 'wrist/depth/handle')) for r in ('U3_F40', 'U3_F45')))
        cols.append('/'.join(pct(v(r, lane, st, 'wrist/depth/tcp')) for r in ('U3_F40', 'U3_F45')))
        out.append(f'| {lane} | {st} | {n} | ' + ' | '.join(cols) + ' |')

out.append('')
out.append('### B. Door frame / floor / lintel in base RGB (asym/B12/B15/B20), per lane/stage; W-RGB floor+1m th40/th45')
out.append('| lane | stage | L frame(handle side) | R frame(handle side) | L frame(hinge side) | R frame(hinge side) | L doorway floor | R doorway floor | L floor+1m | R floor+1m | L lintel | R lintel | W-RGB floor+1m | W-D doorway floor th40/45 |')
out.append('|---|---|---|---|---|---|---|---|---|---|---|---|---|---|')
for lane in LANES:
    for st in STAGES:
        cols = []
        for key in ('frame_handle_side_z1.0', 'frame_hinge_side_z1.0', 'doorway_floor_centre', 'floor_1m_beyond', 'lintel_centre'):
            for cam in ('base_left', 'base_right'):
                cols.append('/'.join(pct(v(r, lane, st, f'{cam}/rgb/{key}')) for r in BASE.values()))
        # reorder to L,R pairs per key already in order
        cols.append('/'.join(pct(v(r, lane, st, 'wrist/rgb/floor_1m_beyond')) for r in ('U3_F40', 'U3_F45')))
        cols.append('/'.join(pct(v(r, lane, st, 'wrist/depth/doorway_floor_centre')) for r in ('U3_F40', 'U3_F45')))
        out.append(f'| {lane} | {st} | ' + ' | '.join(cols) + ' |')

out.append('')
out.append('### C. Mirror symmetry: handle-side camera (L cam on LEFT door vs R cam on RIGHT door) and hinge-side camera, RGB handle arm-clear / depth handle / RGB frame(handle side) / RGB floor+1m; value = LEFT-door lane vs RIGHT-door lane, |diff| in pp')
out.append('| cell | stage | metric | camera role | asym L-door/R-door (|d|) | B12 L/R (|d|) | B15 L/R (|d|) |')
out.append('|---|---|---|---|---|---|---|')
sym_summary = {}
for cell in ('C_S2', 'C_S21'):
    for st in STAGES:
        for label, key in (('RGB handle clear', 'rgb/handle/arm_clear'), ('depth handle', 'depth/handle'), ('RGB frame handle-side', 'rgb/frame_handle_side_z1.0'), ('RGB floor+1m', 'rgb/floor_1m_beyond'), ('RGB lintel', 'rgb/lintel_centre')):
            for role in ('handle-side', 'hinge-side'):
                camL = 'base_left' if role == 'handle-side' else 'base_right'   # LEFT door: handle at +y => base_left is handle-side
                camR = 'base_right' if role == 'handle-side' else 'base_left'
                cols = []
                for bname, r in BASE.items():
                    a = v(r, f'{cell}/left', st, f'{camL}/{key}'); b = v(r, f'{cell}/right', st, f'{camR}/{key}')
                    if a is None or b is None:
                        cols.append('-'); continue
                    cols.append(f'{100*a:.0f}/{100*b:.0f} ({100*abs(a-b):.0f})')
                    sym_summary.setdefault(bname, []).append(abs(a - b))
                out.append(f'| {cell} | {st} | {label} | {role} | ' + ' | '.join(cols) + ' |')
out.append('')
out.append('Mean |L-door minus R-door| over all rows above (pp): ' + ', '.join(f'{k}: {100*np.mean(vv):.1f} (max {100*np.max(vv):.0f})' for k, vv in sym_summary.items()))

out.append('')
out.append('### D. Synthetic Stage0/1 approach (LEFT door W0.95/H2.05/handle 0.90; trunk z 0.48; 3 lateral x 3 yaw poses per distance; arm at NEW reset posture j5=-0.44 (th40) / -0.52 (th45)); share of 9 poses')
keys = ['base_left/rgb/handle', 'base_right/rgb/handle', 'base_left/depth/handle', 'base_right/depth/handle', 'base_left/rgb/frame_handle_side_z1.0', 'base_right/rgb/frame_hinge_side_z1.0', 'base_left/rgb/lintel_centre', 'base_right/rgb/lintel_centre', 'base_left/depth/doorway_floor_centre', 'base_right/depth/doorway_floor_centre', 'wrist/rgb/handle', 'wrist/depth/handle', 'wrist/rgb/frame_handle_side_z1.0', 'wrist/rgb/panel_mid_z1.0', 'wrist/rgb/doorway_floor_centre', 'wrist/depth/doorway_floor_centre', 'wrist/rgb/lintel_centre']
out.append('| variant | dist | ' + ' | '.join(k.replace('base_left', 'L').replace('base_right', 'R').replace('wrist', 'W').replace('/rgb/', '-RGB ').replace('/depth/', '-D ').replace('_z1.0', '').replace('_centre', '') for k in keys) + ' |')
out.append('|---|---|' + '|'.join('---:' for _ in keys) + '|')
for run in ('U3_F40', 'U3_F40_B12', 'U3_F40_B15', 'U3_F45', 'U3_F45_B12', 'U3_F45_B15'):
    sa = RUNS[run]['synthetic_approach']
    for d in ('1.5', '1.2', '1.0', '0.8', '0.7'):
        out.append(f'| {run} | {d} | ' + ' | '.join(pct(sa[d].get(k)) for k in keys) + ' |')

out.append('')
out.append('### E. Wrist axis / motion telemetry from the replay (identical across base variants): wrist axis world elevation p5/p50/p95 (deg), wrist ang speed p50/p95 (deg/s), axis sweep p50/p95, share sweep>60, az reversals/s, dq6 p50/p95, base-left ang speed p50/p95')
out.append('| lane | stage | th40 elev p5/p50/p95 | th45 elev p5/p50/p95 | wrist ang speed p50/p95 | axis sweep p50/p95 | share sweep>60 | az reversals/s | dq6 p50/p95 (rad/s) | base cam ang speed p50/p95 |')
out.append('|---|---|---|---|---|---|---|---|---|---|')
for lane in LANES:
    for st in STAGES:
        e40 = RUNS['U3_F40']['lanes'][lane][st]; e45 = RUNS['U3_F45']['lanes'][lane][st]
        el40 = e40['axis_elev_world_deg']['wrist']; el45 = e45['axis_elev_world_deg']['wrist']
        m = e40.get('motion_dense50hz')
        if m:
            ws, sw, bs, dq = m['wrist_ang_speed_deg_s'], m['wrist_axis_sweep_deg_s'], m['base_left_ang_speed_deg_s'], m['dq6_abs_rad_s']
            mcol = f"{ws['p50']:.0f}/{ws['p95']:.0f} | {sw['p50']:.0f}/{sw['p95']:.0f} | {100*m['wrist_share_axis_sweep_gt_60']:.0f}% | {m['wrist_az_reversals_per_s']:.2f} | {dq['p50']:.2f}/{dq['p95']:.2f} | {bs['p50']:.0f}/{bs['p95']:.0f}"
        else:
            mcol = 'n/a (10 Hz) | | | | | '
        out.append(f"| {lane} | {st} | {el40['p5']:.0f}/{el40['p50']:.0f}/{el40['p95']:.0f} | {el45['p5']:.0f}/{el45['p50']:.0f}/{el45['p95']:.0f} | {mcol} |")

out.append('')
out.append('### F. Static poses at the new reset posture (from the runs; label in JSON still says training_default)')
for run in ('U3_F40', 'U3_F45'):
    sp = RUNS[run]['static_poses']
    for label, d in sp.items():
        out.append(f"- {run} {label} q={RUNS[run]['synthetic_arm_q'] if 'training_default' in label else '[0,0,0,0,0,1.57]'}: flange pitch {d['flange_axis_pitch_deg']}, wrist RGB axis pitch {d['wrist_rgb_axis_pitch_deg']} yaw {d['wrist_rgb_axis_yaw_deg']}, wrist RGB origin B {d['wrist_rgb_origin_B']}, TCP in RGB={d['tcp_in_wrist_rgb']} depth={d['tcp_in_wrist_depth']}, on-axis enters RGB {d['on_axis_point_enters_wrist_rgb_at_m']} m depth {d['on_axis_point_enters_wrist_depth_at_m']} m")

Path('/tmp/v28_team/camera/t3/t3_tables.md').write_text('\n'.join(out) + '\n')
print('\n'.join(out))
