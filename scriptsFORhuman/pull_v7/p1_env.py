"""P1 measurement-only subclass of the production pull environment.

All inherited methods execute once. No action/state/reward/RNG mutation.
CPU aggregation covers every env and every completed rollout control step.
"""
import gzip
import json
from collections import Counter
from pathlib import Path

import numpy as np
import torch

from gr00t.rl.envs.door.door_open_a2_pull import DoorOpenA2Pull


def cpu(tensor):
    return tensor.detach().cpu().numpy().copy()


def margins(q, lo, hi):
    return np.minimum((q-lo)/(hi-lo), (hi-q)/(hi-lo))


class Exposure:
    def __init__(self, env):
        self.env = env
        self.path = Path(env.config.a2_pull_p1_output)
        self.path.mkdir(parents=True, exist_ok=True)
        self.n = env.num_envs
        self.arm = list(env._upper_non_gripper_dof_idx)
        self.joint_ids = [env.simulator.dof_ids[i] for i in self.arm]
        self.lo = cpu(env.dof_pos_humanly_lower_limit)[0, self.arm]
        self.hi = cpu(env.dof_pos_humanly_upper_limit)[0, self.arm]
        self.t = 0
        self.episode = np.full(self.n, -1, dtype=np.int64)
        self.origin = np.full(self.n, -1, dtype=np.int64)
        self.age = np.zeros(self.n, dtype=np.int64)
        self.seen_events = np.zeros((self.n, 10), dtype=bool)
        self.recovered = np.zeros(self.n, dtype=bool)
        self.joint_recovered = np.zeros((self.n, 6), dtype=bool)
        self.last_stage = np.full(self.n, -1, dtype=np.int64)
        self.ready_run = np.zeros(self.n, dtype=np.int64)
        self.records = gzip.open(self.path/'upstream_and_entry_landmarks.jsonl.gz', 'xt')
        self.slot_state = {}
        self.snapshot_records = gzip.open(self.path/'snapshot_writes.jsonl.gz', 'xt')
        self.reset_records = gzip.open(self.path/'reset_samples.jsonl.gz', 'xt')
        self.summaries = (self.path/'exposure_by_side_origin_window.jsonl').open('x')
        self.clear_window()
        metadata = dict(schema='pull_v7_p1_exposure_v1', num_envs=self.n, control_dt_s=env.dt,
            start_batch=9000, stop_batch=9100, control_steps_per_batch=64, window_batches=10,
            joint_names=[env.simulator.dof_names[i] for i in self.arm], lower=self.lo.tolist(), upper=self.hi.tolist(),
            margin_threshold=0.07, reset_ratios=cpu(env.staged_reset_ratios).tolist(),
            initial_inventory=cpu(env.staged_reset_num_samples).tolist(),
            timing='state/reward after physics and before reset/stage advance; reset q is target_robot_dof_state, first action target is recorded on first completed control step',
            event_first='false-to-true once per born episode, excluding flags inherited from loaded snapshots',
            ready_windows='window-local longest and longest ongoing episode run seen are separate; reset breaks both',
            snapshot_kind='observed phase/persistence at actual write, E5 matched by event counter; no inferred write from candidate',
            upstream='first actual step, stage entry, first per-joint and joint-min recovery, E2-E5/C/D entry; stage-conditioned all-step q/target/outward-command aggregates',
            initial_timer='production init_at_random_ep_len=true retained; age_control_steps counts actual steps independently of episode_length_buf')
        (self.path/'exposure_metadata.json').write_text(json.dumps(metadata, indent=2)+'\n')

    def clear_window(self):
        self.groups = {i:dict(counts=Counter(), rewards={}, upstream={}, reset=Counter(), snapshot=Counter(), snapshot_margin={}, load_margin={}, inventory=None) for i in range(4)}
        self.window_ready_seen = np.zeros(self.n, dtype=bool)
        self.window_ready_run = np.zeros(self.n, dtype=np.int64)

    def group_ids(self):
        # LEFT natural/staged=0/1, RIGHT natural/staged=2/3.
        return (cpu(self.env.door_open_lr) < 0).astype(np.int64)*2 + (self.origin != 0)

    def flags(self):
        e=self.env
        return np.column_stack([cpu(e._a2_pull_event_reached)[:,2:8], cpu(e._a2_pull_v6_release_event),
            cpu(e._a2_pull_v6_clean_release), cpu(e._a2_pull_v6_release_persistence)>=25, cpu(e._a2_pull_frame_passage)])

    def reset(self, ids, stages, samples, valid):
        e=self.env; ids=cpu(ids).astype(int); stages=cpu(stages).astype(int);samples=cpu(samples).astype(int)
        self.episode[ids]+=1; self.origin[ids]=stages; self.age[ids]=0
        self.seen_events[ids]=self.flags()[ids]
        self.recovered[ids]=False; self.joint_recovered[ids]=False
        self.last_stage[ids]=-1;self.ready_run[ids]=0;self.window_ready_run[ids]=0;self.window_ready_seen[ids]=False
        q=cpu(e.target_robot_dof_state)[ids][:,self.arm,0];m=margins(q,self.lo,self.hi)
        self.recovered[ids]=m.min(axis=1)>=.07;self.joint_recovered[ids]=m>=.07
        phases=cpu(e._a2_pull_v6_subphase)[ids];groups=self.group_ids()[ids]
        masks=cpu(valid).T
        for k,env_id in enumerate(ids):
            g=self.groups[int(groups[k])];g['reset']['selected_stage_'+str(stages[k])]+=1
            if stages[k]!=0:g['reset']['loaded_sample_'+str(samples[k])]+=1
            g['reset']['availability_'+''.join(str(int(x)) for x in masks[k])]+=1
            g['reset']['loaded_phase_'+str(phases[k])]+=1
            key=f"stage{stages[k]}_phase{phases[k]}"
            hist=g['load_margin'].setdefault(key,Counter());hist['n']+=1;hist['margin_ge_007']+=int(m[k].min()>=.07)
            row=dict(control_step=self.t,env=int(env_id),episode=int(self.episode[env_id]),side='left' if groups[k]<2 else 'right',
                origin='natural' if stages[k]==0 else 'staged',selected_stage=int(stages[k]),
                drawn_sample_index=int(samples[k]),sample_index=int(samples[k]) if stages[k]!=0 else None,
                availability_mask=masks[k].tolist(),loaded_phase=int(phases[k]),loaded_q=q[k].tolist(),margin=m[k].tolist(),
                inherited_flags=self.seen_events[env_id].tolist(),is_initial_reset=self.t==0,
                observed_slot_write=self.slot_state.get((int(stages[k]),int(samples[k]),int(env_id))))
            self.reset_records.write(json.dumps(row, separators=(',',':'))+'\n')

    def snapshot(self, ids, stages, slots):
        e=self.env;ids=cpu(ids).astype(int);stages=cpu(stages).astype(int);slots=cpu(slots).astype(int)
        if not len(ids):return
        phase=cpu(e._a2_pull_v6_subphase)[ids];persist=cpu(e._a2_pull_v6_release_persistence)[ids]
        counters=cpu(e.episode_length_buf)[ids];e5=cpu(e._a2_pull_first_event_step)[ids,5]
        q=cpu(e.simulator.dof_pos)[ids][:,self.arm];m=margins(q,self.lo,self.hi).min(axis=1)
        groups=self.group_ids()[ids]
        for k,env_id in enumerate(ids):
            kind='stage_entry'
            if stages[k]==4:
                kind='E5' if e5[k]==counters[k] else ('ready' if phase[k]==2 else (f'D{persist[k]}' if phase[k]==3 else 'B_other'))
            key=f'{kind}_stage{stages[k]}_phase{phase[k]}'
            g=self.groups[int(groups[k])];g['snapshot'][key]+=1
            hist=g['snapshot_margin'].setdefault(key,Counter());hist['n']+=1;hist['margin_ge_007']+=int(m[k]>=.07)
            entry=dict(kind=kind,phase=int(phase[k]),margin=float(m[k]),writer_origin='natural' if self.origin[env_id]==0 else 'staged')
            self.slot_state[(int(stages[k]),int(slots[k]),int(env_id))]=entry
            self.snapshot_records.write(json.dumps(dict(control_step_being_completed=self.t+1,env=int(env_id),episode=int(self.episode[env_id]),
                stage=int(stages[k]),slot=int(slots[k]),side='left' if groups[k]<2 else 'right',**entry),separators=(',',':'))+'\n')

    def reward_gates(self, stage, phase, panel_clear):
        e=self.env; sw=(stage==4); late=sw|(stage==5);send=(phase==1)|(phase==2)
        c=lambda name:cpu(getattr(e,'_a2_pull_v6_'+name)).astype(bool)
        persistence=cpu(e._a2_pull_v6_release_persistence)
        income=c('clean_release')&(phase==3)&c('persistence_income_active')&(persistence>0)&(persistence<=int(e.config.a2_pull_v6_release_persistence_steps))
        handoff=(c('handoff_reached')&(phase==1)&c('pivot_valid')&c('prev_bilateral_contact')&panel_clear&
            (cpu(e._a2_pull_v6_pivot_displacement_m)<=float(e.config.a2_pull_v6_base_relief_radius_m))&
            (cpu(e._a2_pull_v6_arm_tangent_share)>=float(e.config.a2_pull_v6_release_min_arm_tangent_share)))
        gates=dict(arm_tangent_progress=send,handle_side_bonus=c('handle_cross_bonus'),arc_tracking=send,
            pivot_excess_penalty=send,hinge_momentum=phase==2,clean_release_quality=c('clean_release_event'),
            premature_release_penalty=c('premature_release_event'),post_release_persistence=income,
            handoff_side_progress=c('handoff_reward_window'),handoff_hinge_momentum=handoff,
            handoff_hinge_angle_deficit=c('handoff_reached')&(phase==1)&c('release_side_qualified'),
            post_release_arm_default_target_quality=c('clean_release')&(phase==3)&c('release_event'),
            post_release_open_command_quality=income,post_release_recontact_penalty=c('persistence_recontact_event'),
            release_open_command_quality=c('release_action_started_ready')|c('clean_release_event'),
            post_release_lateral_command_alignment=c('post_release_lateral_command_alignment_active'),
            post_release_arm_tuck_progress=c('post_release_arm_tuck_progress_active'))
        return {'a2_pull_v6_'+k:v&(sw if k=='post_release_arm_tuck_progress' else late) for k,v in gates.items()}

    def observe(self, raw, scaled, actor_action):
        e=self.env; self.t+=1;self.age+=1
        assert np.all(self.origin>=0), 'P1 requires recorded actual reset origin for every env'
        stage=cpu(e.stage_buf);phase=cpu(e._a2_pull_v6_subphase);groups=self.group_ids()
        q=cpu(e.simulator.dof_pos)[:,self.arm]
        target=cpu(e.simulator.scene.articulations['robot'].data.joint_pos_target)[:,self.joint_ids]
        m=margins(q,self.lo,self.hi);margin=m.min(axis=1);good=margin>=.07
        recovery=good&~self.recovered; jr=(m>=.07)&~self.joint_recovered
        self.recovered|=good;self.joint_recovered|=m>=.07
        flags=self.flags();first=flags&~self.seen_events;self.seen_events|=flags
        ready=cpu(e._a2_pull_v6_release_ready).astype(bool)
        ready_episode=ready&~self.window_ready_seen;self.window_ready_seen|=ready
        self.ready_run=np.where(ready,self.ready_run+1,0);self.window_ready_run=np.where(ready,self.window_ready_run+1,0)
        _,body=e._get_a2_door_body_panel_contact_forces();_,arm=e._get_a2_door_arm_panel_contact_forces()
        panel_clear=cpu(body+arm)==0
        bilateral=cpu(e._a2_pull_v6_prev_bilateral_contact).astype(bool)
        hinge=cpu(e._get_door_joint_pos('P1 measured hinge',1))[:,0]
        velocity=cpu(e._get_door_joint_vel('P1 measured hinge',1))[:,0]
        clearance=cpu(e._get_a2_pull_minimum_panel_robot_clearance())
        conditions=dict(pivot_valid=cpu(e._a2_pull_v6_pivot_valid).astype(bool),bilateral=bilateral,panel_clear=panel_clear,
            handle_y=cpu(e._a2_pull_v6_handle_y_prev)<=.06,pivot=cpu(e._a2_pull_v6_pivot_displacement_m)<=.15,
            share=cpu(e._a2_pull_v6_arm_tangent_share)>=.6,hinge=hinge>=float(e.config.a2_pull_v6_release_hinge_rad),
            velocity=velocity>=.15,clearance=clearance>=.02,margin=good)
        pass_count=np.stack(list(conditions.values())).sum(axis=0)
        raw_names=list(raw);raw_values=cpu(torch.stack([raw[k].float() for k in raw_names],dim=1));scaled_values=cpu(torch.stack([scaled[k] for k in raw_names],dim=1))
        gates=self.reward_gates(stage,phase,panel_clear)
        primitive=cpu(e._get_a2_gripper_primitive_raw_column('P1 applied gripper'))
        outward=((q<=self.lo+.07*(self.hi-self.lo))&(target<self.lo))|((q>=self.hi-.07*(self.hi-self.lo))&(target>self.hi))
        events=['E2','E3','E4','E5','E6','E7','release','clean','persistence25','frame']
        for gi in range(4):
            mask=groups==gi;n=int(mask.sum());g=self.groups[gi];counts=g['counts']
            counts['control_steps']+=n
            for st in range(6):counts[f'stage{st}_steps']+=int((mask&(stage==st)).sum())
            for ph,name in [(1,'B'),(2,'C'),(3,'D')]:
                active=(phase==ph)&(stage>=4)
                counts[name+'_steps']+=int((mask&active).sum());counts[name+'_margin_ge_007_steps']+=int((mask&active&good).sum())
            for k in range(10):
                counts[events[k]+'_first_occurrences']+=int(first[mask,k].sum());counts[events[k]+'_flag_steps']+=int(flags[mask,k].sum())
            counts['B_entry_margin_ge_007']+=int((mask&first[:,3]&good).sum())
            counts['ready_steps']+=int((mask&ready).sum());counts['ready_exposed_episodes_in_window']+=int((mask&ready_episode).sum())
            counts['ready_longest_in_window']=max(counts['ready_longest_in_window'],int(self.window_ready_run[mask].max()) if n else 0)
            counts['ready_longest_episode_run_seen']=max(counts['ready_longest_episode_run_seen'],int(self.ready_run[mask].max()) if n else 0)
            counts['first_margin_recovery_episodes']+=int((mask&recovery).sum())
            counts['raw_open_steps']+=int((mask&(actor_action[:,11]>0)).sum());counts['applied_open_steps']+=int((mask&(primitive>0)).sum())
            for name,cnd in conditions.items():counts['ready_condition_'+name+'_steps']+=int((mask&(stage>=4)&cnd).sum())
            for count in range(11):counts[f'ready_pass_count_{count}_steps']+=int((mask&(stage>=4)&(pass_count==count)).sum())
            for name,cnd in conditions.items():counts['only_missing_'+name+'_steps']+=int((mask&(stage>=4)&(pass_count==9)&~cnd).sum())
            for st in range(6):
                sm=mask&(stage==st);sn=int(sm.sum())
                if not sn:continue
                u=g['upstream'].setdefault(str(st),dict(n=0,q_sum=np.zeros(6),target_sum=np.zeros(6),q_min=np.full(6,np.inf),q_max=np.full(6,-np.inf),
                    margin_ge_007_steps=0,joint_margin_ge_007_steps=np.zeros(6,dtype=np.int64),outward_target_near_limit_steps=np.zeros(6,dtype=np.int64),first_recovery=0))
                u['n']+=sn;u['q_sum']+=q[sm].sum(axis=0);u['target_sum']+=target[sm].sum(axis=0)
                u['q_min']=np.minimum(u['q_min'],q[sm].min(axis=0));u['q_max']=np.maximum(u['q_max'],q[sm].max(axis=0))
                u['margin_ge_007_steps']+=int(good[sm].sum());u['joint_margin_ge_007_steps']+=(m[sm]>=.07).sum(axis=0)
                u['outward_target_near_limit_steps']+=outward[sm].sum(axis=0);u['first_recovery']+=int(recovery[sm].sum())
            for j,name in enumerate(raw_names):
                r=g['rewards'].setdefault(name,Counter());rv=raw_values[mask,j];sv=scaled_values[mask,j]
                r['raw_nonzero_steps']+=int(np.count_nonzero(rv));r['scaled_positive_steps']+=int((sv>0).sum());r['scaled_negative_steps']+=int((sv<0).sum())
                r['raw_sum']+=float(rv.sum(dtype=np.float64));r['scaled_positive_sum']+=float(sv[sv>0].sum(dtype=np.float64));r['scaled_negative_sum']+=float(sv[sv<0].sum(dtype=np.float64))
                if name in gates:r['active_mask_steps']+=int(gates[name][mask].sum())
        chosen=(self.age==1)|((stage<=2)&(stage!=self.last_stage))|recovery|jr.any(axis=1)|first.any(axis=1)|ready_episode
        counters=cpu(e.episode_length_buf)
        source_event_steps=cpu(e._a2_pull_first_event_step)
        for i in np.flatnonzero(chosen):
            row=dict(control_step=self.t, batch=9000+(self.t-1)//64+1,env=int(i),episode=int(self.episode[i]),
                side='left' if groups[i]<2 else 'right',origin='natural' if self.origin[i]==0 else 'staged',birth_stage=int(self.origin[i]),
                age_control_steps=int(self.age[i]),episode_counter=int(counters[i]),stage=int(stage[i]),phase=int(phase[i]),
                first_step=bool(self.age[i]==1),stage_entry=bool(stage[i]!=self.last_stage[i]),first_margin_recovery=bool(recovery[i]),
                first_joint_recovery=jr[i].tolist(),first_events=[events[j] for j in np.flatnonzero(first[i])],
                source_first_event_step=source_event_steps[i].tolist(),
                observer_first_flag_control_step={events[j]:self.t for j in np.flatnonzero(first[i])},ready=bool(ready[i]),
                q=q[i].tolist(),target=target[i].tolist(),margin=m[i].tolist(),hinge=float(hinge[i]),clearance=float(clearance[i]))
            self.records.write(json.dumps(row,separators=(',',':'))+'\n')
        self.last_stage=stage.copy()

    def flush(self):
        e=self.env;stock=cpu(e.staged_reset_num_samples);side=cpu(e.door_open_lr)>0
        observed_stock={0:Counter(),1:Counter()}
        for (st,slot,env_id),entry in self.slot_state.items():
            c=observed_stock[int(not side[env_id])]
            c[f'stage{st}_phase{entry["phase"]}_slots']+=1
            if entry['margin']>=.07:c[f'stage{st}_phase{entry["phase"]}_margin_ge_007_slots']+=1
        for gi,g in self.groups.items():
            ids=side if gi<2 else ~side
            # Effective ring occupancy is min(cumulative stores, configured capacity).
            occupancy=np.minimum(stock[:,ids],e.staged_reset_max_samples_per_stage)
            g['inventory']=dict(side='left' if gi<2 else 'right',available_envs_by_stage=(stock[:,ids]>0).sum(axis=1).tolist(),
                cumulative_store_counter_by_stage=stock[:,ids].sum(axis=1).tolist(),effective_slots_by_stage=occupancy.sum(axis=1).tolist(),
                observed_written_slot_composition=dict(observed_stock[gi//2]),
                note='side inventory is repeated across origin groups; do not sum duplicate inventories; Stage0 initialized slots are not runtime writes')
            row=dict(schema='pull_v7_p1_window_v1',batch_start=9001+(self.t-640)//64,batch_end=9000+self.t//64,
                side='left' if gi<2 else 'right',origin='natural' if gi%2==0 else 'staged',**g)
            self.summaries.write(json.dumps(row,default=lambda x:x.tolist(),separators=(',',':'))+'\n')
        self.summaries.flush();self.records.flush();self.reset_records.flush();self.snapshot_records.flush()
        self.clear_window()
        if self.t==6400:
            self.summaries.close();self.records.close();self.reset_records.close();self.snapshot_records.close()
            (self.path/'exposure_complete.json').write_text(json.dumps(dict(control_steps=self.t,transitions=self.t*self.n,windows=10,final_batch=9100))+'\n')


class DoorOpenA2PullP1(DoorOpenA2Pull):
    def __init__(self, config, device):
        self._p1=None
        super().__init__(config,device)
        self._p1=Exposure(self)

    def step(self, actor_state):
        self._p1_actor_action=cpu(actor_state['actions'])
        result=super().step(actor_state)
        if self._p1.t%640==0:self._p1.flush()
        return result

    def _after_reward_components(self,raw_components,scaled_components):
        result=super()._after_reward_components(raw_components,scaled_components)
        if self._p1 is not None:self._p1.observe(raw_components,scaled_components,self._p1_actor_action)
        return result

    def _sample_reset_stages(self,env_ids):
        selected=super()._sample_reset_stages(env_ids)
        if self._p1 is not None:
            self._p1_selected_stages=selected.detach().clone()
            self._p1_valid=(self.staged_reset_num_samples[:,env_ids]>0).detach().clone()
        return selected

    def _sample_reset_sample_indices(self,env_ids,selected_stages):
        selected=super()._sample_reset_sample_indices(env_ids,selected_stages)
        if self._p1 is not None:self._p1_selected_samples=selected.detach().clone()
        return selected

    def reset_envs_idx(self,env_ids,target_states=None,target_buf=None):
        result=super().reset_envs_idx(env_ids,target_states,target_buf)
        if self._p1 is not None and len(env_ids):self._p1.reset(env_ids,self._p1_selected_stages,self._p1_selected_samples,self._p1_valid)
        return result

    def _take_snapshot_of_buffered_states(self,advance_mask):
        ids=torch.where(advance_mask)[0]
        stages=self.stage_buf[advance_mask].detach().clone()
        slots=(self.staged_reset_num_samples[stages,ids]%self.staged_reset_max_samples_per_stage).detach().clone()
        result=super()._take_snapshot_of_buffered_states(advance_mask)
        if self._p1 is not None:self._p1.snapshot(ids,stages,slots)
        return result
