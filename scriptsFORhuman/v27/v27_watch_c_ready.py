"""Evaluate ready Wave C cells, then assemble complete milestone readouts."""
from __future__ import annotations

import time
from pathlib import Path

from v27_contract import RUNTIME, EVAL, SEEDS, cells, read_json, write_json, train_checkpoint, require
from v27_orchestrate import eval_manifest, eval_launch, eval_finalize
from v27_reduce import typed_outcomes
from v27_watch_wave import training_states, checkpoint_ready, eval_busy, event, WAIT_SECONDS

STEPS = (1000, 2000, 3000, 4000, 5000, 6000)


def parts(step):
    return sorted((RUNTIME / 'eval_manifests' / 'wave_c' / f'step{step}').glob('part*.json'))


def manifests(step):
    return [p for p in parts(step) if p.stem.removeprefix('part').isdigit()]


def reduced_path(manifest):
    return EVAL / read_json(manifest)['name'] / 'reducer.json'


def finish_parts():
    for step in STEPS:
        for path in manifests(step):
            if reduced_path(path).exists():
                continue
            receipts_path = path.with_name(f'{path.stem}_receipts.json')
            if not receipts_path.exists():
                eval_launch(path)
                return
            receipts = read_json(receipts_path)
            if all((Path(p).parent / 'exit_code.txt').exists() for p in receipts.values()):
                eval_finalize(path)
                event(f'wave_c_step{step}_{path.stem}_ready', {
                    'kind': 'PARTIAL_MILESTONE_REDUCED', 'manifest': str(path),
                    'reducer': str(reduced_path(path))})


def assemble(step, active, pending):
    output = EVAL / 'wave_c' / f'step{step}' / 'reducer.json'
    if output.exists():
        return True
    paths = manifests(step)
    if pending or not paths or any(not reduced_path(p).exists() for p in paths):
        return False
    payloads = [read_json(reduced_path(p)) for p in paths]
    covered = {lane['cell'] for p in payloads for lane in p['lanes']}
    if not set(active).issubset(covered):
        return False
    previous = [EVAL / 'wave_c' / f'step{s}' / 'reducer.json' for s in STEPS if s < step]
    if any(not p.exists() for p in previous):
        return False
    combined, invalid, lanes, raw_lanes = {}, {}, [], []
    for path, payload in zip(paths, payloads, strict=True):
        require(not (set(combined) | set(invalid)) & (set(payload['cells']) | set(payload['invalid_cells'])),
                'duplicate cell across Wave C parts')
        combined.update(payload['cells'])
        invalid.update(payload['invalid_cells'])
        lanes.extend(payload['lanes'])
        raw_lanes.extend(read_json(path)['lanes'])
    history = [read_json(p) for p in previous] + [{'step': step, 'cells': combined}]
    result = {**payloads[0], 'step': step, 'endpoint': step == 6000,
              'cells': combined, 'invalid_cells': invalid, 'lanes': lanes,
              'status': 'V27_INVALID' if invalid else 'V27_COMPLETE',
              'route': 'V27_INVALID' if invalid else 'V27_REDUCED',
              'typed_outcomes': typed_outcomes(combined, history) if step == 6000 and not invalid else None,
              'part_reducers': [str(reduced_path(p)) for p in paths],
              'not_run_cells': sorted(set(cells('C')) - covered)}
    if invalid and step == 6000:
        result['typed_outcomes'] = {'qualification': {'outcome': 'UNRESOLVED'},
            'wave_a': {'outcome': 'UNRESOLVED'}, 'wave_b_domain': {'outcome': 'UNRESOLVED'},
            'recovery': {'outcome': 'UNRESOLVED'},
            'wave_c': {'sc_outcome': 'UNRESOLVED', 'sk_outcome': 'UNRESOLVED'}}
    canonical = RUNTIME / 'eval_manifests' / 'wave_c' / f'step{step}.json'
    write_json(canonical, {**read_json(paths[0]), 'name': f'wave_c/step{step}',
        'endpoint': step == 6000, 'lanes': raw_lanes, 'wave_c_history': history[:-1]})
    write_json(output, result)
    event(f'wave_c_step{step}_ready', {'kind': 'MILESTONE_REDUCED',
        'reducer': str(output), 'manifest': str(canonical)})
    return True


def main():
    while True:
        active, pending = training_states('C')
        finish_parts()
        complete = [assemble(step, active, pending) for step in STEPS]
        if all(complete):
            write_json(RUNTIME / 'wave_c_watch_done.json', {'status': 'WATCH_COMPLETE',
                'jobs': [[step, 'all'] for step in STEPS], 'schedule': 'ready_cells'})
            return
        if not eval_busy():
            for step, done in zip(STEPS, complete, strict=True):
                if done:
                    continue
                existing = manifests(step)
                scheduled = {lane['cell'] for p in existing for lane in read_json(p)['lanes']}
                ready = [c for c, p in active.items() if c not in scheduled and checkpoint_ready(c, step, p)]
                if not ready:
                    continue
                strata = ['nominal'] if read_json(RUNTIME / 'wave_b_decision.json')['RECIPE_B'] == 'current' else ['nominal', 'P02', 'P05']
                path = eval_manifest(f'wave_c/step{step}/part{len(existing)+1}',
                    {c: train_checkpoint(c, step) for c in ready}, strata, 64, SEEDS['DEV'], step=step)
                eval_launch(path)
                event(f'wave_c_step{step}_{path.stem}_launched', {
                    'kind': 'READY_CELLS_EVAL_LAUNCHED', 'cells': ready, 'manifest': str(path)})
                break
        time.sleep(WAIT_SECONDS)


if __name__ == '__main__':
    main()
