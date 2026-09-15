#!/usr/bin/env python3
"""CPU-only v7 P0. Stream each of the five registered traces once.

Run: python scriptsFORhuman/pull_v7/analyze_p0.py
Writes event rows and sufficient per-episode statistics; later interpretation
uses these small outputs, never rereads the traces. No simulator imports.
"""
import argparse
import csv
import gzip
import json
import math
from pathlib import Path
from collections import Counter

import yaml

ROOT = Path(__file__).resolve().parents[2]
WAVE = 'a2_piper_pull_v26_8_backbone/pull_v26_8_backbone_20260905_natural1_r2/wave2'
OLD = 'logs_eval/a2_piper_pull_v6/p2_render_F0_r6ap_r6an_seed3_env14/eval'
EVENTS = ['E2_TENSILE_CAPTURE', 'E3_LATCH_RELEASE', 'E4_POSITIVE_HINGE_RETAINED',
          'E5_CLEARANCE_DECISION', 'E6_PATH_REVERSAL_ENTRY', 'E7_WHOLE_BODY_CLEAR']
THRESHOLDS = dict(handle_y=('a2_pull_v6_release_handle_y_m', '<='),
                  pivot=('a2_pull_v6_base_relief_radius_m', '<='),
                  share=('a2_pull_v6_release_min_arm_tangent_share', '>='),
                  hinge=('a2_pull_v6_release_hinge_rad', '>='),
                  velocity=('a2_pull_v6_release_min_hinge_velocity_radps', '>='),
                  clearance=('a2_pull_v6_release_min_clearance_m', '>='),
                  margin=('a2_pull_v6_release_min_arm_margin', '>='))


def stream(path):
    # Files are the evaluator's indent=4 top-level JSON arrays. The standard
    # decoder sees one complete record at a time; memory is bounded by a record.
    with (gzip.open(path, 'rt') if path.suffix == '.gz' else path.open()) as f:
        assert next(f).strip() == '['
        lines = []
        for line in f:
            if line == ']':
                assert not lines
                return
            lines.append(line)
            if line.startswith('    }') and line.strip() in ('},', '}'):
                yield json.loads(''.join(lines).rstrip().rstrip(','))
                lines.clear()
        assert not lines


def number(x):
    return None if x is None or x == 'N/A' else x


def window_update(stats, key, passed, step):
    w = stats.setdefault(key, {'steps': 0, 'unknown_steps': 0, 'longest': 0, 'windows': [], '_start': None, '_last': None})
    if passed is None:
        w['unknown_steps'] += 1
    if passed is True:
        w['steps'] += 1
        if w['_start'] is None or step != w['_last'] + 1:
            if w['_start'] is not None:
                w['windows'].append([w['_start'], w['_last']])
            w['_start'] = step
        w['_last'] = step
        w['longest'] = max(w['longest'], step - w['_start'] + 1)
    elif w['_start'] is not None:
        w['windows'].append([w['_start'], w['_last']])
        w['_start'] = w['_last'] = None


def finish_windows(stats):
    for w in stats.values():
        if w['_start'] is not None:
            w['windows'].append([w['_start'], w['_last']])
        del w['_start'], w['_last']


def all_known(values):
    if any(x is False for x in values):
        return False
    return None if any(x is None for x in values) else True


def compact(r, source, side, cfg):
    p = r['pull_v0']; v = p['pull_v6']; t = p['pull_v3_traversal']
    out = dict(source=source, side=side, env=r['env_id'], episode=r['episode_index'],
               trace_step=r['step_index'], episode_counter=r['episode_length_buf'], stage=r['stage_buf'],
               event_state=p['event_state'], phase=v['stage4_subphase'],
               margin=v['workspace_margin'], clearance=v['panel_clearance_m'],
               hinge=p['hinge_position_rad'], velocity=p['hinge_velocity_radps'],
               handle_y=v['handle_y_current_m'] if source == 'r6an' else v['handle_send_y_current_m'],
               pivot=number(v['pivot_displacement_m']), share=v['arm_tangent_share'],
               pivot_valid=v['pivot_valid'], bilateral=p['bilateral_handle_contact'], panel_clear=t['panel_clear'],
               release_ready=v['release_ready'], release_event=v['release_event'], clean=v['clean_release'],
               persistence=v['release_persistence_steps'], frame=t['frame_passage'],
               tcp_position_error=p['target_tcp_position_error_m'], tcp_orientation_error=p['target_tcp_orientation_error_rad'])
    for k in ['root_pos_rel', 'root_lin_vel_w', 'root_ang_vel_w', 'root_yaw', 'policy_arm_action_raw',
              'policy_base_action_raw', 'actual_post_delta_post_warp_arm_action', 'post_delta_post_warp_base_action',
              'physical_base_command', 'policy_gripper_primitive_raw', 'post_delta_post_warp_gripper_primitive',
              'arm_soft_limit_normalized_margin', 'arm_soft_joint_pos_limits', 'door_scenario']:
        out[k] = r[k]
    margins = []
    robot = cfg['robot']
    for name, q, target in zip(r['arm_joint_names'], r['arm_joint_pos'], r['arm_joint_pos_target'], strict=True):
        i = robot['dof_names'].index(name)
        lo, hi = float(robot['dof_pos_lower_limit_list'][i]), float(robot['dof_pos_upper_limit_list'][i])
        m = min((q-lo)/(hi-lo), (hi-q)/(hi-lo))
        out[name+'_q'] = q; out[name+'_target'] = target; out[name+'_release_margin'] = m
        margins.append(m)
        mid=(lo+hi)/2; half=(hi-lo)*0.95/2
        out[name+'_penalty095_margin'] = min((q-(mid-half))/(2*half), ((mid+half)-q)/(2*half))
        out[name+'_penalty095_violation_rad'] = max(mid-half-q, 0)+max(q-mid-half, 0)
    out['min_joint'] = r['arm_joint_names'][margins.index(min(margins))]
    out['margin_recomputed'] = min(margins)
    cond = {k:out[k] for k in ['pivot_valid', 'bilateral', 'panel_clear']}
    for key,(setting, op) in THRESHOLDS.items():
        value = out[key]; threshold=float(cfg['env']['config'][setting])
        cond[key] = None if value is None else (value <= threshold if op=='<=' else value >= threshold)
    out.update({'ready_'+k:x for k,x in cond.items()})
    out['geometric_joint_ready'] = all_known(list(cond.values()))
    out['ready_condition_count'] = sum(x is True for x in cond.values())
    out['only_missing'] = next((k for k,x in cond.items() if x is False), None) if sum(x is False for x in cond.values()) == 1 and all(x is not None for x in cond.values()) else None
    return out, cond


def analyze(source, side, path, config):
    cfg = yaml.load(config.read_text(), Loader=yaml.BaseLoader)
    metrics = json.loads((path.parent/'metrics_eval.json').read_text())
    records = json.loads((path.parent/'a2_v14_per_env_records.json').read_text())
    terminals = {r['env_id']: r for r in metrics['episode_terminal_diagnostics']}
    expected = 16 if source == 'r6an' else 64
    assert len(terminals) == len(records) == metrics['completed_episodes'] == expected
    states={}; landmarks={}; births=[]; excluded=Counter(); max_error=0.; counters=Counter()
    for r in stream(path):
        counters['input_records']+=1
        if r.get('record_type') == 'episode_start':
            births.append(r); continue
        if r['episode_index'] != 0 or not r['first_episode_active']:
            excluded['not_first_episode']+=1; continue
        env=r['env_id']; step=r['episode_length_buf']
        c,conditions=compact(r,source,side,cfg)
        max_error=max(max_error,abs(c['margin']-c['margin_recomputed']))
        if env not in states:
            states[env] = dict(env=env, first_counter=step, first_trace_step=r['step_index'], rows=0,
                               missing_control_steps=0, first_low=None, first_low_left_censored=False,
                               post_e5={}, all_observed={}, phases=Counter(), event_steps={},
                               min_margin=c['margin'], max_margin=c['margin'], post_e5_margin_max=None,
                               ready_reconstruction_mismatch=0)
            landmarks[env]={'first_observed': c}
        s=states[env]; s['rows']+=1; s['phases'][str(c['phase'])]+=1
        if 'last_counter' in s:
            assert step>s['last_counter']
            s['missing_control_steps']+=step-s['last_counter']-1
        s['last_counter']=step
        s['min_margin']=min(s['min_margin'],c['margin']); s['max_margin']=max(s['max_margin'],c['margin'])
        if s['first_low'] is None and c['margin']<float(cfg['env']['config'][THRESHOLDS['margin'][0]]):
            s['first_low']=step; s['first_low_left_censored']=s['rows']==1
            landmarks[env]['first_low_margin']=c
        for event,value in r['pull_v0_episode']['first_event_step'].items():
            if event in EVENTS and number(value) is not None:
                s['event_steps'][event[:2]]=value
                if step==value:
                    landmarks[env][event[:2]]=c
        if c['pivot_valid'] and 'B_capture' not in landmarks[env]: landmarks[env]['B_capture']=c
        if c['release_ready'] and 'first_ready' not in landmarks[env]: landmarks[env]['first_ready']=c
        if c['clean'] and 'first_clean' not in landmarks[env]: landmarks[env]['first_clean']=c
        e5=s['event_steps'].get('E5')
        if e5 is not None and step-e5 in (25,50,100): landmarks[env]['E5+'+str(step-e5)]=c
        post=e5 is not None and step>=e5
        if post:s['post_e5_margin_max']=c['margin'] if s['post_e5_margin_max'] is None else max(s['post_e5_margin_max'],c['margin'])
        for stats in [s['all_observed']] + ([s['post_e5']] if post else []):
            for key,value in conditions.items():window_update(stats,key,value,step)
            window_update(stats,'joint',c['geometric_joint_ready'],step)
            window_update(stats,'actual_ready',c['release_ready'],step)
            window_update(stats,'all_except_margin',all_known([x for k,x in conditions.items() if k!='margin']),step)
            for key in conditions:window_update(stats,'only_missing_'+key,c['only_missing']==key,step)
        if (c['phase']==2 and c['geometric_joint_ready']) != c['release_ready']:s['ready_reconstruction_mismatch']+=1
        landmarks[env]['last_observed']=c
    assert set(states) <= set(terminals)
    output=[]
    for env,term in sorted(terminals.items()):
        if env not in states:
            states[env] = dict(env=env, rows=0, first_counter=None, first_trace_step=None, last_counter=None,
                missing_control_steps=None, first_low=None, first_low_left_censored=None,
                post_e5={}, all_observed={}, phases={}, event_steps={}, min_margin=None, max_margin=None,
                post_e5_margin_max=None, ready_reconstruction_mismatch=0)
            landmarks[env] = {}
        s=states[env]
        s['terminal_counter']=term['episode_length_buf']
        s['terminal_reason']=term['terminal_reasons']
        s['terminal_matches_last_trace']=s['last_counter']==s['terminal_counter']
        s['events']={e[:2]:number(term['pull_v0_episode']['first_event_step'][e]) for e in EVENTS}
        s['event_row_missing']=[k for k,v in s['events'].items() if v is not None and k not in landmarks[env]]
        if s['terminal_matches_last_trace']:landmarks[env]['terminal']=landmarks[env]['last_observed']
        finish_windows(s['post_e5']);finish_windows(s['all_observed'])
        for label in ['first_observed','first_low_margin','E2','E3','E4','E5','B_capture','E5+25','E5+50','E5+100','first_ready','first_clean','terminal','last_observed']:
            c=landmarks[env].get(label)
            if c is None:output.append(dict(source=source,side=side,env=env,episode=0,landmark=label,missing=True))
            else:output.append(dict(c,landmark=label,missing=False))
    summary=dict(source=source,side=side,denominator=expected,trace=str(path.relative_to(ROOT)),trace_bytes=path.stat().st_size,
                 config=str(config.relative_to(ROOT)),thresholds={k:float(cfg['env']['config'][v[0]]) for k,v in THRESHOLDS.items()},
                 metrics=str((path.parent/'metrics_eval.json').relative_to(ROOT)),records=str((path.parent/'a2_v14_per_env_records.json').relative_to(ROOT)),
                 trace_timing=json.loads((path.parent/'a2_eval_diagnostic_metadata.json').read_text())['trace_timing'],
                 birth_count=len(births),birth_stages=dict(Counter(str(r['stage_buf']) for r in births)),
                 read_counts=dict(counters),excluded=dict(excluded),margin_recompute_max_abs_error=max_error,episodes=list(states.values()))
    summary['events']={e[:2]:sum(s['events'][e[:2]] is not None for s in states.values()) for e in EVENTS}
    summary['post_e5']={key:dict(episodes_ever=sum(s['post_e5'].get(key,{}).get('steps',0)>0 for s in states.values()),
                                    steps=sum(s['post_e5'].get(key,{}).get('steps',0) for s in states.values()),
                                    longest=max(s['post_e5'].get(key,{}).get('longest',0) for s in states.values()))
                        for key in next(s['post_e5'] for s in states.values() if s['post_e5'])}
    print(source,side,'rows',sum(s['rows'] for s in states.values()),'events',summary['events'],'margin error',max_error,flush=True)
    return summary,output


def enrich_rows(summaries, rows):
    configs={(g['source'],g['side']):yaml.load((ROOT/g['config']).read_text(),Loader=yaml.BaseLoader) for g in summaries}
    terminals={(g['source'],g['side']):{r['env_id']:r for r in json.loads((ROOT/g['metrics']).read_text())['episode_terminal_diagnostics']} for g in summaries}
    for row in rows:
        cfg=configs[(row['source'],row['side'])]; robot=cfg['robot']
        if row['landmark']=='terminal' and row.get('trace_step') in (None,''):
            t=terminals[(row['source'],row['side'])][int(row['env'])]
            row.update(episode_counter=t['episode_length_buf'],stage=t['stage_buf'],terminal_reason=t['terminal_reasons'],
                       missing=True,missing_detail='terminal metrics present; expanded joint/action trace absent')
        for j in range(1,7):
            name=f'arm_j{j}'
            if row.get(name+'_q') in (None,''):continue
            q=float(row[name+'_q']);i=robot['dof_names'].index(name)
            lo=float(robot['dof_pos_lower_limit_list'][i]);hi=float(robot['dof_pos_upper_limit_list'][i])
            mid=(lo+hi)/2;half=(hi-lo)*0.95/2
            row[name+'_penalty095_margin']=min((q-mid+half)/(2*half),(mid+half-q)/(2*half))
            row[name+'_penalty095_violation_rad']=max(mid-half-q,0)+max(q-mid-half,0)


def save(output, summaries, rows):
    enrich_rows(summaries, rows)
    for g in summaries:
        source=g['source']; side=g['side']
        g['source_checkpoint'] = (f'logs_rl/{WAVE}/train/{source}/model_step_009000.pt' if source!='r6an'
            else 'logs_rl/a2_piper_pull_v6/pull_v6_F0_r6an_seed3/model_step_000025.pt')
        g['training_config'] = (f'logs_rl/{WAVE}/train/{source}/resolved_config.yaml' if source!='r6an' else g['config'])
        g['training_log'] = (f'logs_rl/{WAVE}/train/{source}/isaac.log' if source!='r6an' else None)
        g['diagnostic_metadata'] = str(Path(g['trace']).parent/'a2_eval_diagnostic_metadata.json')
        g['pass_count_histogram_post_e5'] = {}
        total_hist=Counter()
        for e in g['episodes']:
            hist=Counter(); edges=Counter()
            if e['post_e5']:
                for key in ['pivot_valid','bilateral','panel_clear',*THRESHOLDS]:
                    for lo,hi in e['post_e5'][key]['windows']:
                        edges[lo]+=1;edges[hi+1]-=1
                edges[e['events']['E5']]+=0;edges[e['last_counter']+1]+=0
                count=0;points=sorted(edges)
                for lo,hi in zip(points,points[1:]):
                    count+=edges[lo];hist[str(count)]+=hi-lo
            e['pass_count_histogram_post_e5']=dict(hist);total_hist.update(hist)
        g['pass_count_histogram_post_e5']=dict(sorted(total_hist.items(),key=lambda kv:int(kv[0])))
    output.mkdir(parents=True,exist_ok=True)
    with (output/'P0_ENTRY_TRAJECTORY.csv').open('w',newline='') as f:
        fields=list(dict.fromkeys(k for row in rows for k in row));writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for row in rows:writer.writerow({k:json.dumps(v,separators=(',',':')) if isinstance(v,(dict,list)) else v for k,v in row.items()})
    (output/'P0_READINESS_FUNNEL.json').write_text(json.dumps(dict(schema='pull_v7_p0_v1',control_dt_s=.02,
        scope='four current natural64 first episodes plus 16 episodes in one old render, not old strict-natural64',
        missing='null/blank remains missing; first_observed Stage2 is left truncated; window endpoints are inclusive episode counters',
        groups=summaries),indent=2)+'\n')


def report(output):
    import statistics
    data=json.loads((output/'P0_READINESS_FUNNEL.json').read_text())
    groups=data['groups']
    assert len(groups)==5
    with (output/'P0_ENTRY_TRAJECTORY.csv').open() as f: rows=list(csv.DictReader(f))
    def selected(g,label):
        return [r for r in rows if r['source']==g['source'] and r['side']==g['side'] and r['landmark']==label and r['trace_step']!='']
    def med(rs,key):return statistics.median(float(r[key]) for r in rs)
    def fmt(x):return f'{x:.6g}'
    def table(headers, body):
        return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(map(str,r))+' |' for r in body])
    def label(g):return g['source']+' '+g['side'].upper()
    def link(path,line=None):
        return f'[{Path(path).name}]({ROOT/path}{":"+str(line) if line else ""})'
    current=groups[:4]; old=groups[4]
    coverage=table(['总体','能力分母','详细轨迹episode / rows','E2/E3/E4/E5','E6/E7','无详细trace env'],[
        [label(g),g['denominator'],f"{sum(e['rows']>0 for e in g['episodes'])} / {sum(e['rows'] for e in g['episodes'])}",
         '/'.join(str(g['events'][e]) for e in ['E2','E3','E4','E5']),f"{g['events']['E6']}/{g['events']['E7']}",
         ','.join(str(e['env']) for e in g['episodes'] if not e['rows']) or '无'] for g in groups])
    entry=table(['总体/时点','n','margin中位数','最小margin关节计数','j3实际/target中位(rad)','j5实际/target中位(rad)','clearance中位(m)'],[
        [label(g)+' '+ev,len(rr:=selected(g,ev)),fmt(med(rr,'margin')),json.dumps(dict(Counter(r['min_joint'] for r in rr))),
         f"{fmt(med(rr,'arm_j3_q'))}/{fmt(med(rr,'arm_j3_target'))}",
         f"{fmt(med(rr,'arm_j5_q'))}/{fmt(med(rr,'arm_j5_target'))}",fmt(med(rr,'clearance'))]
        for g in groups for ev in ['first_observed','E3','E4','E5']])
    base_rows=[]
    for g in groups:
        e3={r['env']:r for r in selected(g,'E3')}; e5={r['env']:r for r in selected(g,'E5')}
        delta=[[json.loads(e5[e]['root_pos_rel'])[i]-json.loads(e3[e]['root_pos_rel'])[i] for i in range(3)] for e in e3.keys()&e5.keys()]
        cmd=[[statistics.median(json.loads(r['physical_base_command'])[i] for r in e5.values()) for i in range(3)]]
        base_rows.append([label(g),len(delta),', '.join(fmt(statistics.median(d[i] for d in delta)) for i in range(3)),', '.join(fmt(v) for v in cmd[0])])
    base=table(['总体','paired n','E3→E5 root相对门位移中位 x/y/z(m)','E5 physical base cmd中位 vx/vy/yaw'],base_rows)
    names=['pivot_valid','bilateral','panel_clear','handle_y','pivot','share','hinge','velocity','clearance','margin']
    funnel=table(['E5后单项ever','P_S1 L /64','P_S1 R /62','P_S2 L /64','P_S2 R /64','旧 /10'],[
        [k]+[g['post_e5'][k]['episodes_ever'] for g in groups] for k in names])
    joint=table(['总体','E5后记录步数','几何联合episode/steps/最长','actual ready episode/steps/最长','仅缺margin episode/steps/最长'],[
        [label(g),sum(e['post_e5'].get('pivot_valid',{}).get('steps',0) for e in g['episodes']),
         *['/'.join(str(g['post_e5'][k][field]) for field in ['episodes_ever','steps','longest']) for k in ['joint','actual_ready','only_missing_margin']]] for g in groups])
    pass_counts=table(['总体','E5后同一步通过条件数: 控制步数'],[[label(g),json.dumps(g['pass_count_histogram_post_e5'])] for g in groups])
    old_entries=table(['旧env','E7','E5 trace_step','margin','clearance(m)','ready steps / longest'],[
        [r['env'],int(next(e for e in old['episodes'] if str(e['env'])==r['env'])['events']['E7'] is not None),r['trace_step'],fmt(float(r['margin'])),fmt(float(r['clearance'])),
         '/'.join(str(next(e for e in old['episodes'] if str(e['env'])==r['env'])['post_e5']['actual_ready'][k]) for k in ['steps','longest'])]
        for r in selected(old,'E5')])
    sources='\n'.join(f"- **{label(g)}**：trace {link(g['trace'])}（{g['trace_bytes']:,} bytes）；config {link(g['config'])}；terminal metrics {link(g['metrics'])}；per-env records {link(g['records'])}。" for g in groups)
    text=f'''# Pull v7 P0：入口轨迹与联合 readiness 诊断

2026-09-08 HKT。**P0 离线分析已完成；建议申请 P1 原配置曝光诊断，暂不提出 P2 处理变量。** 当前 margin 缺口在首次可观测 Stage2 已存在，且四侧没有“只缺 margin”的同一步窗口。当前自然轨迹无法提供有余量的 B 入口；训练是否通过 staged reset 获得不同入口仍缺直接计数。不能据此恢复 scale30、改 reset ratio 或否定 plain LSTM。

本报告是既有 runtime artifact 的离线再分析（CPU 执行完成），源码/配置为 INSPECTED；不是新增策略实验、v7 能力验收或 promotion。0 新训练 batches，Isaac Sim/GPU eval/render/训练全部 NOT_RUN。

## 1. 输入、总体与时间基准

{coverage}

当前四侧共 256 个首 episode，254 个有 Stage2–5 详细轨迹。P_S1 RIGHT env21/63 在 Stage0、episode counter250 stage_overtime，E1–E7 均缺失；它们继续占能力分母64，不能混入254条条件轨迹或被当成零margin观测。旧文件是一次16-env natural render，只有10个进入详细trace；6个上游失败也保留。旧 strict-natural64 的 E5/clean/frame/E6/E7=41/5/3/2/1 是独立历史总体，见 {link('scriptsFORhuman/pull_v6_1/PULL_V6_1_P_POPULATION_REPORT.md',15)}；本报告没有用render16替代它，也没有重新扫描该历史总体。

- `trace_step` 是文件的零基 evaluator step；`episode_counter` 是 `episode_length_buf`。这些首episode里相差1；事件 `first_event_step` 采用后者，不能混用。control_dt=0.02s，200Hz physics/decimation4；窗口长度为控制步，端点包含，秒数=长度×0.02。
- CSV保留首次观测、首次低margin、E2/E3/E4/E5、B捕获、E5+25/+50/+100、首次ready/clean、terminal和最后观测。不存在或未存的时点为空，不取邻近行。terminal事件来自metrics；没有expanded trace的terminal仍保留counter/stage，关节和动作缺失。JSON保存每episode事件、所有观测范围以及逐步E5后窗口。
- 有详细trace的264个episode内控制步缺口均0，事件E2–E5对应行均找到；无trace的8个episode是明确缺失。当前出生记录64/侧且Stage0；旧文件没有独立出生row，natural来源由旧eval保存配置和运行日志支持，不能伪造出生证据。
- trace在physics刷新、事件/状态更新、reward计算之后，reset与stage advancement之前采集。raw action来自pre-step observation；target是刚完成的physics step使用值。base command前三项是body-frame vx/vy/yaw-rate，root位移为world axes相对门，不能逐轴当成同一坐标系。
- 当前Stage2→3由grasp_completion控制，E2仍是tensile proof事件，可以在Stage3形成。hard_gate E3为latch threshold+stable contact，E4要求prior E2、hinge>0.25、stable contact与panel clear；E5要求已锁存aperture（stable contact且hinge≥send threshold）与panel clear并遵循E4前置。E3并不保证晚于E2，表内保留实际时间，不按事件编号重新排序。

## 2. A：margin缺口、关节target与base运动

**254/254可观测当前episode在首次Stage2 row已低于0.07，整个已存轨迹也从未达到0.07。** 因此缺口不是只在E5后的opening才形成；上游首次出现时刻全部左截断，Stage0/1的实际关节轨迹无法观察。E3/E4处已存在近限位姿态。不能用出生Stage0行补造关节值，也不能据此定位更早的策略更新原因。

{entry}

当前主要是arm_j3接近上限0rad、arm_j5接近下限−1.22rad；最小值的关节会随轨迹换位。P_S1 LEFT的E5最小关节64/64为j3；RIGHT为j5 62/62；P_S2 LEFT j5/j3=41/23，RIGHT=47/17。j3 target常为+3.75rad而实际q约0；P_S2 j5 target常为−3.25rad而实际q约−1.22。它们是trace中的实际Articulation target，不是用raw action推测出来的target，也不是有余量的实际关节姿态。CSV同时保留六关节q/target、raw/applied arm/base动作及实际base速度。

{base}

以上是同episode E3→E5的配对位移摘要。当前opening伴随base向门外+x退移与左右不同的横移；旧轨迹也退移，但旧j3在负角区域运动、j5没有当前同样的下限target模式，E5 clearance更大。能支持的是联合轨迹差异，不能把base某分量或单关节target认定为已证明的因果干预。

三个限位口径必须分开：

1. release margin：六个实际q，逐关节`min((q-l)/(u-l),(u-q)/(u-l))`再取最小，l/u来自A2 robot配置的dof_pos_lower/upper_limit_list；无clipping。j3为[−2.967,0]、j5为[−1.22,1.22]。重算与原trace最大绝对误差当前≤1.70e−8，旧≤3.66e−8。
2. `arm_soft_limit_normalized_margin`：trace原样保存的IsaacLab articulation 0.9 soft interval；不是release门，也不是reward实际边界。
3. `limits_dof_pos` penalty：simulator hard interval按当前0.95缩窄，六非夹爪关节越界量求和，单位rad，scale−5。CSV另列`*_penalty095_margin`与`*_penalty095_violation_rad`用于区分边界；它是离线重算的penalty几何量，不冒充逐步reward支付。源码见 {link('gr00t/rl/envs/door/door_open_a2_pull.py',5815)}、{link('gr00t/rl/envs/door/door_open_a2_base.py',7071)}、{link('gr00t/rl/envs/door/door_open_a2_base.py',11981)}。

## 3. B：单项ever、同一步联合与连续窗口

独立条件为pivot_valid、双指接触、panel_clear、handle-send-Y≤0.06m、pivot displacement≤0.15m、累计arm tangent share≥0.6、hinge≥1.134464rad、速度≥0.15rad/s、clearance≥0.02m、margin≥0.07。handle_crossed为锁存历史，不代替当前Y门。几何联合要求这些条件同一步全真；actual ready还要求C。E5当步捕获B不能同时转C（`~capture`）；后续C失去pre-ready可退回B。ready不要求frame passage/crossing。见 {link('gr00t/rl/envs/door/door_open_a2_pull.py',5786)}、{link('gr00t/rl/envs/door/door_open_a2_pull.py',5920)}。

{funnel}

{joint}

{pass_counts}

**当前四侧所有“仅缺某一个独立条件”的episode、步数与最长窗口均0；“其余全过仅缺margin”同样为0。** JSON为每个条件分别保存episodes_ever、steps、longest及每episode连续窗口；CSV每个观测时点保留条件bool与通过数。单项ever不能解释为联合可达。P_S2 LEFT还有全程clearance不足；RIGHT的Y门和速度门全程未过。负clearance只是trunk到门板线段的几何包络距离减门板半厚与footprint半径，不等同真实碰撞。

旧render的联合/ready只有env14的一步：episode counter357（trace356），持续0.02s，下一步clean。旧“仅缺Y”10个episode/152步/最长19步，“仅缺pivot”6个/53步/最长13步，“仅缺bilateral”1个/6步/最长6步；其余单缺为0。这些是全E5后**几何条件**窗口，可包含释放后状态，不能自动称为可再次转C的窗口；actual ready单独按原phase/state计数。当前全部E5后处于B，无该阶段混淆。

## 4. C：B入口与snapshot机会

当前B捕获均与E5同counter，254/254 margin<0.07，**未观察到有余量的B入口**；不是“已观察到好入口但未被采集”。源码中，banks off仍会在E5 pending、stage=SWING且pivot_valid时调用普通online snapshot。CSV的B_capture各行具有该状态机会，但没有实际snapshot写入计数/slot/加载记录，不能把机会写成已证明写入或训练采样。

ready snapshot要求pending、C、current ready和prev ready；clean后的D1/D5/D25还有无接触、persistence income等条件。当前自然trace没有ready/clean，所以没有相应状态候选。near-C capture mode=none。源码：{link('gr00t/rl/envs/door/door_open_a2_pull.py',6044)}–6118；真正buffer写入在 {link('gr00t/rl/envs/base_task/staged_task_base.py',572)}。这些条件用于解释当前采集机会，不把当前源码反推成旧成功运行的exact snapshot历史。

## 5. D：训练曝光能证明什么、缺什么

两份Wave2 resolved config及各自step9000 checkpoint均已只读核对。当前与旧r6an保存配置的71个非零reward scale相同，均未启用workspace-progress；这不是整个历史reward函数语义相同的证明。当前ratio保持[0.5,0.1,0.1,0.1,0.1,0.1]、1024env、每batch64控制步、两项外部bank关闭。

| 证据 | P_S1 | P_S2 | 能说明/不能说明 |
| --- | --- | --- | --- |
| checkpoint Stage4 active fraction | 0.615234375 | 0.6171875 | 保存时的诊断聚合，非累计B/C/D曝光 |
| isaac.log末面板Stage4 | 0.6223 | 0.6163 | 时间聚合且四位小数，不能当实际reset比例 |
| checkpoint raw-open fraction | 0.001953125 | 0.005859375 | 存在动作聚合读数，不定位v6 ready或自然/staged来源 |
| checkpoint env_state_dict | 150 keys | 150 keys | log_dict及样本/掩码诊断，非完整physics/reset pool |

`env_state_dict`中没有stage_buf、staged_reset_num_samples、v6 subphase/events、snapshot pending/data或实际reset source/slot。不能从诊断名里的“release gate”认定它等于v6联合ready；不能从四舍五入0.0000推断后段训练从未发生。现存日志/checkpoint不能还原：实际reset数与选中stage/sample、B/C/D控制步数、ready episode/步数/连续窗口、snapshot累计写入与有效库存/加载、分side和natural/staged来源的后段reward raw/scaled激活与正负收益。

`_sample_reset_stages`直接按每env库存可用性mask配置权重后multinomial，不存在requested-stage再reject的步骤。ratio、实际reset比例和控制步曝光有不同分母。full loader恢复policy/critic/optimizer/scheduler/TrainerState及保存诊断；online样本在新进程重新积累，不是physics、bank和LSTM history的exact restore。见 {link('gr00t/rl/envs/base_task/staged_task_base.py',732)}、{link('gr00t/rl/envs/legged_base_task/legged_robot_base.py',1792)}、{link('gr00t/rl/trl/trainer/ppo_trainer_a2_base_api.py',5246)}。

## 6. E：旧成功与失败参照

{old_entries}

旧16总体内：10到E5，8个E5入口margin≥0.07，其中7个仍失败；其余6个未进入详细trace。10个E5到达者在E5后都曾单项达到margin，但只有env14形成ready/clean/E7。这排除了只看winner的解释：好margin入口有帮助的机制关联，并不等于充分条件。

旧env14在trace318进入B时margin=0.121978、clearance=0.315599m；trace356 ready时0.102693/0.296395m；trace357 clean时0.105285/0.294199m。旧轨迹在更早阶段也会短时低margin（env14首次低于门槛counter68），随后在E5入口恢复余量；当前则在整个可观测区间持续缺margin。这个差异比“旧从未靠近限位”更准确。

旧learned override是有效策略组成部分，成功是有效机制参考。旧训练是r6am seed0 step25→r6an seed3、256env、24s、99%Stage4/专用bank与冻结carrier；旧render为16env Stage0 natural、36s/长Stage5。当前是双侧plain LSTM、1024env混合reset、全参数更新。policy、scene、history与训练来源都不同，不构成matched causal comparison；本次未加载旧policy到当前训练，也未将任何来源标记为Teacher。r6r scale4独立结果仍UNRESOLVED，不重跑；撤回的scale30建议不恢复。

## 7. 一次集中裁决：申请P1，不启动

**建议P1，暂不准备P2处理变量。** P0已排除“只差一个E5后margin条件”的简化解释；上游近限位target、运动和多门条件存在描述性差异，但尚无实际训练曝光证据支撑选择单一reward或采样干预。最关键缺失测量是：**按side、真实出生来源分层的训练rollout B/C/D及联合ready曝光，并关联实际snapshot写入/加载。** 以下为同一曝光测量的具体接线，不是多轴扫描。

| 真实执行位置 | 直接计数 | 分母/时序 |
| --- | --- | --- |
| staged_task_base `_sample_reset_stages`返回与`reset_envs_idx`选sample后（622–627、732–782） | 配置权重、有效性mask、实际stage/sample；加载后subphase/margin | 实际reset数；不创造requested-stage |
| `_take_snapshot_of_buffered_states`完成写入（572–606） | E5/ready/D原因、累计写入数、有效槽位数与实际加载数 | 写入数≠环形buffer库存；保持原采样，不额外随机抽样 |
| DoorOpenA2Pull `_after_reward_components`（6839–6904）与现有control-step telemetry（8408–8427） | B/C/D、ready步数/episode/连续窗口、raw/applied开爪、release/clean/persistence25/E6/E7；本步raw/scaled reward与原激活mask、正负收益 | 全部1024env有效rollout步；physics/reward后、reset前，side×Stage0/staged出生×10-batch窗口 |
| trainer env.step后到现有episode聚合（4032–4050、4863–4924） | 导出小型exposure_by_side_origin_window.jsonl | 消费env已捕获记录，不在reset后反读terminal状态 |

申请预算：P_S1、P_S2各从本身Wave2 step9000 full续训；1024env，各100新batches、绝对上限9100，共13,107,200 transitions。9050/9100保存诊断checkpoint；actor/critic/PPO照常更新，不冻结，不更改reward/obs/E事件/ratio/plant/loader语义，不增加随机采样。旧约22秒/batch推算约1.2 GPU小时，启动开销另计；不包含eval/render或自动延长。预期超过30分钟时每格独立tmux；**尚未批准，遥测接线和launcher均未实施，新运行均未启动。**

测量完成条件：两来源覆盖规定窗口且上述实际计数可按side/origin核算，能区分natural/staged是否得到有余量B入口与ready。100batches只能描述新进程初期曝光，若库存继续漂移就报告瞬态，不宣称稳态。达到9100停止；实际异常/NaN/来源不符/Owner停止即停止，不因没有E7自动延长。9100不自动替代9000 source。P2预算不能挪用P1，须以后明确单变量、同期原配置C、直接中介及成功/停止条件后另批。

## 8. Provenance、复用与验证范围

{sources}

- 当前训练来源与日志：`logs_rl/{WAVE}/train/{{P_S1,P_S2}}/`中的`model_step_009000.pt`、`resolved_config.yaml`、`isaac.log`。这两份checkpoint只在CPU读取保存结构，未启动仿真。
- 旧eval保存override：{link('logs_eval/a2_piper_pull_v6/p2_render_F0_r6ap_r6an_seed3_env14/hydra/.hydra/config.yaml')}；其七项ready阈值与旧训练保存config相同，robot部分为局部override，release限位重算使用旧完整训练保存config并与逐步workspace原值核对。旧runner记录policy_only请求被规范化为full；不将请求字段当实际loader路径。
- 每组metadata的trace_timing原文保存于JSON。当前runtime receipt记录checkpoint路径、命令与退出码；当前eval `.hydra/runtime_config.yaml`优先于计划。
- 入口：{link('scriptsFORhuman/pull_v7/analyze_p0.py')}。普通执行读取固定五份trace；`--reuse-existing`复用完成组，仅提取缺组；`--report-only`仅使用小表/小型metrics/config重生成三产物，不解析大trace。
- 实际验证：能力分母64×4与旧16、缺失env、首事件counter精确对齐、trace内步连续性、release margin逐关节重算、phase-C/ready重算均已核对；ready不一致计数0。初版曾错误要求Stage0失败env也有Stage2 trace，修正后保留缺失总体并完成提取；没有新测试矩阵、compile循环或GPU验证。
- Main为唯一writer；两条只读lane已交付。只新增P0入口与三个产物，增量更新对应memory；不改训练语义、全局配置、已有用户改动，不commit/push。P0完成不代表v7全链路能力达标。
'''
    (output/'P0_DIAGNOSIS.md').write_text(text)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path(__file__).parent)
    parser.add_argument('--reuse-existing', action='store_true', help='Reuse completed group summaries and CSV; read only missing groups')
    parser.add_argument('--report-only', action='store_true', help='Enrich and report existing small tables, never read traces')
    args=parser.parse_args(); summaries=[];rows=[]
    if args.reuse_existing or args.report_only:
        summaries=json.loads((args.output/'P0_READINESS_FUNNEL.json').read_text())['groups']
        with (args.output/'P0_ENTRY_TRAJECTORY.csv').open() as f: rows=list(csv.DictReader(f))
    if args.report_only:
        save(args.output,summaries,rows)
        report(args.output)
        return
    inputs=[]
    for source in ['P_S1','P_S2']:
        for side in ['left','right']:
            directory=ROOT/'logs_eval'/WAVE/'eval/milestones/step9000'/f'{source}_STEP9000'/side
            inputs.append((source,side,directory/'stage2_5_step_trace.json',directory/'.hydra/runtime_config.yaml'))
    inputs.append(('r6an','right',ROOT/OLD/'stage2_5_step_trace.json.gz',ROOT/'logs_rl/a2_piper_pull_v6/pull_v6_F0_r6an_seed3/config.yaml'))
    for source,side,path,config in inputs:
        if any(g['source']==source and g['side']==side for g in summaries): continue
        s,r=analyze(source,side,path,config);summaries.append(s);rows.extend(r)
        save(args.output,summaries,rows)
    report(args.output)

if __name__=='__main__':main()
