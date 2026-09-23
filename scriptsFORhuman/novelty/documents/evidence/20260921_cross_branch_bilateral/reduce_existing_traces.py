"""Read the three existing eval traces once; collect first-episode evidence."""
import gc
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path('/home/baoquanc/workspace/DoorDog-A2_Piper')
PULL = ROOT.parent / 'DoorDog-A2_Piper_pull_v0/logs_eval/a2_piper_pull_v29/step4000_lr_exact64_20260921'
SOURCES = {
    'push_C002_6000': ROOT / 'logs_eval/base_v29/push_baseline_C002_seed291/natural_final',
    'pull_4000_left': PULL / 'left_a4',
    'pull_4000_right': PULL / 'right_a1',
}
OUT = Path(__file__).parent
FIELDS = (
    'door_handle_joint_pos', 'door_hinge_joint_pos', 'door_hinge_joint_vel',
    'both_contact', 'squeeze_window', 'contact_stability',
    'a2_stage2_squeeze_streak', 'a2_stage3_stage4_both_contact_streak',
    'target_pos_source_handle_distance', 'handle_opening_alignment',
    'handle_approach_alignment', 'over_force',
)


def reduce(name, directory):
    trace = directory / 'stage2_5_step_trace.json'
    print(f'Loading existing trace: {name}', flush=True)
    with trace.open() as stream:
        rows = json.load(stream)
    outcomes = json.loads((directory / 'a2_v14_per_env_records.json').read_text())
    by_id = {r['env_id']: r for r in outcomes}
    histories = defaultdict(lambda: defaultdict(list))
    last_length = {}
    finished = set()
    starts = {}
    later_rows = 0
    for row in rows:
        env = row['env_id']
        if row.get('record_type') == 'episode_start':
            if row['episode_index'] == 0:
                starts[env] = row['stage_buf']
            continue
        if name.startswith('pull'):
            if not row['first_episode_active'] or row['episode_index'] != 0:
                later_rows += 1
                continue
        length = row['episode_length_buf']
        if env in finished:
            later_rows += 1
            continue
        if env in last_length and length < last_length[env]:
            finished.add(env)
            later_rows += 1
            continue
        last_length[env] = length
        stage = row['stage_buf']
        entry = {key: row[key] for key in FIELDS}
        entry.update(
            step=row['step_index'], episode_length=length,
            hinge_gate=row['door_hinge_joint_pos'] > row['stage3_to4_door_hinge_threshold'],
            hold_gate=row['a2_stage3_stage4_both_contact_streak'] >= row['a2_grasp_streak_control_steps'],
            grip=row['gripper_primitive_raw'][0],
        )
        histories[env][stage].append(entry)
    del rows
    gc.collect()
    per_env = []
    for env, stages in sorted(histories.items()):
        result = {
            'env_id': env, 'side': by_id[env]['door_handle_side'],
            'goal': by_id[env]['goal_reached'], 'max_stage': by_id[env]['max_stage'],
            'last_first_episode_length': last_length[env], 'stages': {},
        }
        for stage, samples in sorted(stages.items()):
            stats = {'steps': len(samples)}
            for key in FIELDS:
                values = np.asarray([r[key] for r in samples], dtype=float)
                stats[key] = {'mean': float(values.mean()), 'min': float(values.min()),
                              'max': float(values.max()), 'median': float(np.median(values))}
            stats['negative_close_fraction'] = float(np.mean([r['grip'] < 0 for r in samples]))
            if stage == 3:
                stats['joint_gate_step_counts'] = dict(Counter(
                    f"hinge_{int(r['hinge_gate'])}_hold_{int(r['hold_gate'])}" for r in samples))
                both = [r for r in samples if r['hinge_gate'] and r['hold_gate']]
                stats['first_both_gates'] = both[0] if both else None
            result['stages'][str(stage)] = stats
        per_env.append(result)
    side_summary = {}
    for side in sorted({r['side'] for r in per_env}):
        group = [r for r in per_env if r['side'] == side]
        summary = {'episodes': len(group), 'goals': sum(r['goal'] for r in group),
                   'max_stages': dict(Counter(r['max_stage'] for r in group)), 'stages': {}}
        for stage in ('2', '3', '4', '5'):
            members = [r['stages'][stage] for r in group if stage in r['stages']]
            if not members:
                continue
            agg = {'envs_with_rows': len(members),
                   'steps_per_env_median': float(np.median([s['steps'] for s in members]))}
            for key, operation in (
                ('door_handle_joint_pos', 'max'), ('door_hinge_joint_pos', 'max'),
                ('a2_stage2_squeeze_streak', 'max'), ('a2_stage3_stage4_both_contact_streak', 'max'),
                ('both_contact', 'mean'), ('squeeze_window', 'mean'), ('contact_stability', 'mean'),
                ('target_pos_source_handle_distance', 'median'),
                ('handle_opening_alignment', 'median'), ('handle_approach_alignment', 'median'),
                ('over_force', 'mean'),
            ):
                values = [s[key][operation] for s in members]
                agg[f'{key}_per_env_{operation}'] = {
                    'min': min(values), 'median': float(np.median(values)), 'max': max(values)}
            agg['envs_max_stage2_streak_ge5'] = sum(s['a2_stage2_squeeze_streak']['max'] >= 5 for s in members)
            agg['envs_any_both_contact'] = sum(s['both_contact']['max'] > 0 for s in members)
            if stage == '3':
                totals = Counter()
                for s in members:
                    totals.update(s['joint_gate_step_counts'])
                agg['joint_gate_step_counts'] = dict(totals)
                agg['envs_both_gates_observed'] = sum(s['first_both_gates'] is not None for s in members)
            summary['stages'][stage] = agg
        side_summary[side] = summary
    report = {
        'source': str(trace), 'outcome_source': str(directory / 'a2_v14_per_env_records.json'),
        'method': 'One standard-library json.load per source; first-episode records only; per-env stage summaries.',
        'later_episode_rows_excluded': later_rows, 'episode_start_stage_counts': dict(Counter(starts.values())),
        'per_env': per_env, 'side_summary': side_summary,
        'limitations': ['Stage3 hinge/hold gate conjunction is a trace readout, not new simulation or intervention.',
                        'Handle angles remain physical measurements, not assumed unlock truth.',
                        'Per-env summaries are summarized across envs; means are not independent episode success probabilities.'],
    }
    target = OUT / f'{name}_trace_readout.json'
    target.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'source': name, 'sides': side_summary}, indent=2), flush=True)


if __name__ == '__main__':
    for label, folder in SOURCES.items():
        reduce(label, folder)
