import json
d = json.load(open('/tmp/v28_team2/camera/out/w1_width.json'))
for k in ('final_20260906/v28_reset', 'v28_cut_20260909/v28_reset', 'v28_merged_20260909/v28_reset'):
    links = d[k]
    print('==', k)
    for n in ('trunk', 'metal_plate_5mm', 'vpiper_main', 'vpiper_support', 'FL_foot'):
        c = links.get(n, {}).get('collision')
        print('  ', n, None if c is None else (round(c['y_min'], 4), round(c['y_max'], 4)))
