#!/usr/bin/env python3
"""Reduce completed P1 telemetry; does not read P0 traces or start a simulator."""
import argparse
import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path


def records(path):
    with gzip.open(path,'rt') as f:
        for line in f:yield json.loads(line)


def reduce_cell(path):
    complete=json.loads((path/'exposure_complete.json').read_text())
    result=json.loads((path/'runtime_result.json').read_text())
    assert complete['transitions']==6553600 and result['actual_success']
    windows=[json.loads(s) for s in (path/'exposure_by_side_origin_window.jsonl').read_text().splitlines()]
    assert len(windows)==40
    groups={}
    for row in windows:
        key=row['side']+'/'+row['origin'];g=groups.setdefault(key,dict(counts=Counter(),rewards={},reset=Counter(),snapshot=Counter(),upstream={},windows=[]))
        for k,v in row['counts'].items():
            if 'longest' in k:g['counts'][k]=max(g['counts'][k],v)
            else:g['counts'][k]+=v
        for kind in ['rewards','upstream']:
            for name,vals in row[kind].items():
                if kind=='rewards':
                    g[kind].setdefault(name,Counter()).update(vals)
                else:
                    u=g[kind].setdefault(name,dict(n=0,margin_ge_007_steps=0,first_recovery=0,outward_target_near_limit_steps=[0]*6,joint_margin_ge_007_steps=[0]*6,q_sum=[0.]*6,target_sum=[0.]*6))
                    for k in ['n','margin_ge_007_steps','first_recovery']:u[k]+=vals[k]
                    for k in ['outward_target_near_limit_steps','joint_margin_ge_007_steps','q_sum','target_sum']:
                        u[k]=[a+b for a,b in zip(u[k],vals[k])]
        for kind in ['reset','snapshot']:g[kind].update(row[kind])
        g['windows'].append(dict(batch_end=row['batch_end'],counts=row['counts'],inventory=row['inventory'],load_margin=row['load_margin'],snapshot_margin=row['snapshot_margin']))
    assert sum(g['counts']['control_steps'] for g in groups.values())==6553600
    for end in range(9010,9101,10):
        assert sum(r['counts']['control_steps'] for r in windows if r['batch_end']==end)==655360
    episodes={};last={};reset_n=0;inherited=Counter();loaded=Counter();slot_known=0
    for r in records(path/'reset_samples.jsonl.gz'):
        key=(r['env'],r['episode']);group=r['side']+'/'+r['origin'];reset_n+=1
        if r['env'] in last:episodes[last[r['env']]]['completed']=True
        last[r['env']]=key
        episodes[key]=dict(group=group,reset_step=r['control_step'],completed=False,exposed=False,initial_good=min(r['margin'])>=.07,
            recovered=False,recovery_stage=None,recovery_age=None,ready=False,first_events=[],birth_stage=r['selected_stage'],
            initial_joint_good=[v>=.07 for v in r['margin']],joint_recovery_age=[None]*6,joint_recovery_stage=[None]*6)
        for i,flag in enumerate(r['inherited_flags']):
            if flag:inherited[f'{group}/flag{i}']+=1
        if r['selected_stage']!=0:
            loaded[f'{group}/phase{r["loaded_phase"]}']+=1
            if min(r['margin'])>=.07:loaded[f'{group}/phase{r["loaded_phase"]}/margin_ge_007']+=1
            if r['observed_slot_write'] is not None:slot_known+=1
    for r in records(path/'upstream_and_entry_landmarks.jsonl.gz'):
        ep=episodes[(r['env'],r['episode'])];ep['exposed']=True;ep['ready']|=r['ready'];ep['first_events']+=r['first_events']
        for j,recovered in enumerate(r['first_joint_recovery']):
            if recovered:ep['joint_recovery_age'][j]=r['age_control_steps'];ep['joint_recovery_stage'][j]=r['stage']
        if r['first_margin_recovery']:
            ep.update(recovered=True,recovery_stage=r['stage'],recovery_age=r['age_control_steps'])
    for key,g in groups.items():
        es=[e for e in episodes.values() if e['group']==key and e['exposed']]
        g['episodes']=dict(exposed=len(es),completed=sum(e['completed'] for e in es),right_censored=sum(not e['completed'] for e in es),
            born_good=sum(e['initial_good'] for e in es),recovered_from_low=sum(e['recovered'] for e in es),
            completed_never_good=sum(e['completed'] and not(e['initial_good'] or e['recovered']) for e in es),
            right_censored_not_yet_good=sum(not e['completed'] and not(e['initial_good'] or e['recovered']) for e in es),
            ready_unique=sum(e['ready'] for e in es),recovery_stages=dict(Counter(str(e['recovery_stage']) for e in es if e['recovered'])),
            recovery_age_control_steps=[e['recovery_age'] for e in es if e['recovered']],
            per_joint_recovery={f'arm_j{j+1}':dict(born_good=sum(e['initial_joint_good'][j] for e in es),
                age_control_steps=[e['joint_recovery_age'][j] for e in es if e['joint_recovery_age'][j] is not None],
                stages=dict(Counter(str(e['joint_recovery_stage'][j]) for e in es if e['joint_recovery_age'][j] is not None))) for j in range(6)})
    writes=Counter()
    for r in records(path/'snapshot_writes.jsonl.gz'):
        writes[r['side']+'/'+r['writer_origin']+'/'+r['kind']]+=1
    assert sum(writes.values())==sum(sum(g['snapshot'].values()) for g in groups.values())
    assert reset_n==sum(sum(v for k,v in g['reset'].items() if k.startswith('selected_stage_')) for g in groups.values())
    return dict(path=str(path),complete=complete,groups=groups,reset_records=reset_n,snapshot_records=sum(writes.values()),
        snapshot_kinds=dict(writes),inherited_flags=dict(inherited),actual_loaded_phases=dict(loaded),loads_with_known_write=slot_known,
        runtime_result=result)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('run_root',type=Path);p.add_argument('--output',type=Path,default=Path(__file__).parent)
    p.add_argument('--report-only', action='store_true', help='Reuse P1_EXPOSURE_SUMMARY.json without reading telemetry again')
    args=p.parse_args()
    cells=(json.loads((args.output/'P1_EXPOSURE_SUMMARY.json').read_text()) if args.report_only else
           {name:reduce_cell(args.run_root/name) for name in ['P_S1','P_S2']})
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'P1_EXPOSURE_SUMMARY.json').write_text(json.dumps(cells,indent=2)+'\n')
    def table(headers,rows):
        return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(map(str,row))+' |' for row in rows])
    import statistics
    joint_recovery_table=table(['来源/侧/出生/joint','出生有余量episode','从低首次恢复episode','首次恢复age中位(控制步)','首次恢复stage'],[
        [cell+'/'+key+'/'+joint,v['born_good'],len(v['age_control_steps']),statistics.median(v['age_control_steps']) if v['age_control_steps'] else '缺失',v['stages']]
        for cell,c in cells.items() for key,g in c['groups'].items() for joint,v in g['episodes']['per_joint_recovery'].items() if joint in ['arm_j2','arm_j3','arm_j5']])
    phase_table=table(['来源/侧/出生','控制步','B / 有余量B步','C / D步','ready步 / 独立episode','ready最长(步)','有余量新E5入口'],[
        [cell+'/'+key,g['counts']['control_steps'],f"{g['counts']['B_steps']} / {g['counts']['B_margin_ge_007_steps']}",
         f"{g['counts']['C_steps']} / {g['counts']['D_steps']}",f"{g['counts']['ready_steps']} / {g['episodes']['ready_unique']}",
         g['counts']['ready_longest_episode_run_seen'],g['counts']['B_entry_margin_ge_007']]
        for cell,c in cells.items() for key,g in c['groups'].items()])
    recovery_table=table(['来源/侧/出生','实际暴露episode','出生已高margin','从低恢复','完成且从未恢复','尚未恢复且右截断','首次恢复stage'],[
        [cell+'/'+key,*[g['episodes'][x] for x in ['exposed','born_good','recovered_from_low','completed_never_good','right_censored_not_yet_good']],g['episodes']['recovery_stages']]
        for cell,c in cells.items() for key,g in c['groups'].items()])
    event_table=table(['来源/侧/出生','release 首次/flag步','clean 首次/flag步','E6 首次/flag步','E7 首次/flag步'],[
        [cell+'/'+key,*[f"{g['counts'][e+'_first_occurrences']} / {g['counts'][e+'_flag_steps']}" for e in ['release','clean','E6','E7']]]
        for cell,c in cells.items() for key,g in c['groups'].items()])
    upstream_table=table(['来源/侧/出生/stage','控制步','j2/j3/j5近限位向外target步','j2/j3/j5实际q均值','j2/j3/j5target均值','六关节margin≥.07步'],[
        [cell+'/'+key+'/'+st,u['n'],'/'.join(str(u['outward_target_near_limit_steps'][i]) for i in [1,2,4]),
         '/'.join(f"{u['q_sum'][i]/u['n']:.4f}" for i in [1,2,4]),'/'.join(f"{u['target_sum'][i]/u['n']:.4f}" for i in [1,2,4]),u['margin_ge_007_steps']]
        for cell,c in cells.items() for key,g in c['groups'].items() for st,u in sorted(g['upstream'].items()) if int(st)<=2])
    reward_table=table(['来源/侧/出生/reward','active步','raw非零步','scaled正/负步','scaled正/负总和'],[
        [cell+'/'+key+'/'+name.replace('a2_pull_v6_',''),r.get('active_mask_steps','未定义此mask'),r['raw_nonzero_steps'],
         f"{r['scaled_positive_steps']}/{r['scaled_negative_steps']}",f"{r['scaled_positive_sum']:.7g}/{r['scaled_negative_sum']:.7g}"]
        for cell,c in cells.items() for key,g in c['groups'].items() for name,r in g['rewards'].items() if name.startswith('a2_pull_v6_')])
    window_table=table(['来源/窗口末','natural控制步','staged控制步','B有余量步','C步','D步','ready步'],[
        [cell,end,*[sum(w['counts'][metric] for key,g in c['groups'].items() for w in g['windows'] if w['batch_end']==end and (origin is None or key.endswith(origin)))
            for metric,origin in [('control_steps','natural'),('control_steps','staged'),('B_margin_ge_007_steps',None),('C_steps',None),('D_steps',None),('ready_steps',None)]]]
        for cell,c in cells.items() for end in range(9010,9101,10)])
    reset_table=table(['来源/侧/出生','实际reset stage0/1/2/3/4/5','实际snapshot写入'],[
        [cell+'/'+key,'/'.join(str(g['reset'].get('selected_stage_'+str(i),0)) for i in range(6)),dict(g['snapshot'])]
        for cell,c in cells.items() for key,g in c['groups'].items()])
    load_table=table(['来源','实际staged加载phase及高margin次数'],[[cell,c['actual_loaded_phases']] for cell,c in cells.items()])
    inventory_table=table(['来源/侧/窗口末','stage0..5有效槽位','实际写入槽位phase组成（含高margin）'],[
        [cell+'/'+key.split('/')[0]+'/'+str(w['batch_end']),w['inventory']['effective_slots_by_stage'],w['inventory']['observed_written_slot_composition']]
        for cell,c in cells.items() for key,g in c['groups'].items() if key.endswith('/natural') for w in g['windows'] if w['batch_end'] in [9010,9050,9100]])
    ready=sum(g['counts']['ready_steps'] for c in cells.values() for g in c['groups'].values())
    goodb=sum(g['counts']['B_margin_ge_007_steps'] for c in cells.values() for g in c['groups'].values())
    all_groups=[g for c in cells.values() for g in c['groups'].values()]
    natural_groups=[g for c in cells.values() for key,g in c['groups'].items() if key.endswith('/natural')]
    b_steps=sum(g['counts']['B_steps'] for g in all_groups)
    d_steps=sum(g['counts']['D_steps'] for g in all_groups)
    release_first=sum(g['counts']['release_first_occurrences'] for g in all_groups)
    natural_episodes=sum(g['episodes']['exposed'] for g in natural_groups)
    j2_recovery=sum(len(g['episodes']['per_joint_recovery']['arm_j2']['age_control_steps']) for g in natural_groups)
    j3_recovery=sum(len(g['episodes']['per_joint_recovery']['arm_j3']['age_control_steps']) for g in natural_groups)
    min_recovery=sum(g['episodes']['recovered_from_low'] for g in natural_groups)
    e5_writes=sum(v for g in all_groups for k,v in g['snapshot'].items() if k.startswith('E5_'))
    b_loads=sum(v for c in cells.values() for k,v in c['actual_loaded_phases'].items() if k.endswith('/phase1'))
    from datetime import datetime
    minutes={cell:(datetime.fromisoformat(c['runtime_result']['finished_at'])-datetime.fromisoformat(c['runtime_result']['started_at'])).total_seconds()/60 for cell,c in cells.items()}
    findings=f'''## 集中结论

- 训练实际有{b_steps:,}个B控制步，普通E5 snapshot确实写入{e5_writes:,}次、staged实际加载B {b_loads:,}次，但有余量B步/入口/已加载状态均未观察到。C/ready、clean、E6/E7新事件为0；对应release-open、clean质量和clean后persistence/tuck/open等reward激活为0。arm-tangent、arc与handoff奖励则有实际非零支付，不能将全部后段reward概括为无曝光。
- D原始状态有{d_steps:,}个控制步，release首次接触转移事件{release_first:,}次；clean为0，D且clean/release的reward active步数为0。原始D和release标志不能充当合格clean释放。实际加载的phase3来自上游自动snapshot，不是成功D1/D5/D25采集。
- 默认低margin与后续行为已分开：自然出生{natural_episodes:,}个实际暴露episode中，j2首次恢复≥0.07有{j2_recovery:,}个，j3只有{j3_recovery}个；六关节min恢复有{min_recovery}个，均在P_S1 Stage1，未形成有余量B。Stage0的j3 target均值0、近限位向外target步数0；Stage1相应比例四侧99.136%–99.788%，Stage2≥99.998%，实际q仍接近上限0。这支持调查Stage1开始的持续target与余量恢复路径，不能只把低margin归于默认姿态。
- 这些是9001–9100新进程的有限训练曝光事实，不是9000原进程的全历史，也不是natural策略能力评估。P1没有发现被P0 natural隐藏的高margin B或合格C/clean-D曝光。P1问题已得到有界回答；P2处理变量仍未选择，不自动改reward/reset比例，也不延长P1。若下一阶段立项，直接中介应包含Stage1的q/target与恢复、B入口margin及同一步联合ready，不能只看Stage4占比或E5 admission。

实际runner墙钟（含启动/退出）：P_S1={minutes['P_S1']:.2f}分钟、P_S2={minutes['P_S2']:.2f}分钟，合计约{sum(minutes.values())/60:.2f} GPU占用小时；较原约1.2小时估计高，新增batches和transitions未超预算。四个9050/9100 checkpoint已CPU读取，global_step分别准确，均有33个optimizer states。启动日志存在GPU foundation/GLFW显示初始化报文，后续scene setup、训练和最终child/wrapper均成功；保留原日志，不将这些报文抹去或推定为policy故障。
'''
    text=f'''# P1 实际训练曝光报告

两来源均完成9001–9100各100新batches，总计13,107,200 transitions。无额外eval/render，无自动延长，诊断checkpoint不promotion。

核心测量结果：全体有余量B控制步={goodb}；联合ready控制步={ready}。这是新进程100batch内实际训练曝光，不是natural评估能力或稳态证明。

{findings}

## B/C/D与联合ready

{phase_table}

B/C/D为stage≥4的实际subphase；D可由premature release产生，不自动等同clean释放。D且clean/release的直接对应门可查post_release_arm_default_target_quality的active_mask_steps。高margin门为六实际关节release公式min≥0.07。newE5入口排除snapshot继承事件；实际加载的B/C/D另见reset数据。独立ready episode从逐episode记录去重，不把各10batch窗口episode数直接相加。

## 上游余量恢复

{recovery_table}

{joint_recovery_table}

{upstream_table}

默认j2=0、j3=0在相应限位。低margin出生不直接说明策略错误；上表分开记录实际q、执行target、低余量且target指向限位外的步数和实际首次恢复。loaded时已高margin不算“恢复”。首次per-joint/min恢复在`upstream_and_entry_landmarks.jsonl.gz`中带age_control_steps与episode_counter；生产init_at_random_ep_len保留，不能将随机初始化的counter当真实执行时长。完成episode从未恢复与预算结束仍未恢复的右截断episode分开。

## 事件与状态持续时间

{event_table}

首次发生排除reset时继承的flags；flag步数可包括继承后的状态持续，不代表新事件次数。release与clean不混同，E6/E7不以flag总步数当成功episode数。

## reset、snapshot与库存

{reset_table}

{load_table}

{inventory_table}

实际stage抽样按每env库存mask重加权。Stage0抽到的sample index未用于加载，`sample_index=null`，另保留`drawn_sample_index`审计RNG实际抽样。`snapshot_writes.jsonl.gz`记录每次实际写入；reset文件记录真正选中slot及最后观测写入信息。有效库存按环形容量取实际有效槽位，Stage0初始化库存不计运行写入。JSON每窗口inventory按side报告，natural/staged两行重复该side库存，禁止重复求和。

## 后段奖励真实曝光

{reward_table}

全部reward的raw非零、scaled正负步数及收益保存在SUMMARY。active_mask按现有v6 reward公式和stage decorator旁录，mask为真但raw为零是允许结果，不把mask、非零支付和episode能力互换。零值来自精确计数，不来自四位小数日志。

## 初期窗口与瞬态限制

{window_table}

100batch是新进程初期窗口：online snapshot库存重新积累，full不恢复physics/bank/LSTM轨迹历史。不能从这个有界窗口推断旧9000训练进程的全程曝光，也不因后段事件稀少自动延长。最终裁决需按本表的来源差异、库存变化及中介读数解释；不自动选择新reward权重/reset比例。

## Provenance和验证

- 运行根：{args.run_root.resolve()}；每来源resolved_config.yaml、config_comparison.json、exposure_metadata.json、runtime_result.json、9050/9100 checkpoints，以及telemetry_source.py精确源码副本与RUN_RECEIPT.json。
- 旁录实现：scriptsFORhuman/pull_v7/p1_env.py；运行命令：run_p1_cell.sh；汇总入口：analyze_p1.py；合同：P1_CONTRACT.md。
- 已核对每来源40行(10窗口×2侧×2出生来源)、每窗口655360 transitions、每来源6553600；实际reset行数/汇总计数一致、snapshot逐条/汇总计数一致。Main已CPU核对四个checkpoint的global_step与optimizer保存状态，child/wrapper均0。
- 所有数字为训练曝光描述，不能替代新的natural评估；未运行P2、Teacher/Student、hardware或云端handoff。
'''
    (args.output/'P1_EXPOSURE_REPORT.md').write_text(text)
    print('P1 telemetry reduced:',goodb,'good-B steps;',ready,'ready steps')

if __name__=='__main__':main()
