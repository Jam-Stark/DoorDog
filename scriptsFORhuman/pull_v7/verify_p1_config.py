"""Verify P1's resolved semantic config against its actual Wave2 source."""
import json
import sys
from pathlib import Path
import yaml

path=Path(sys.argv[1]);cell=sys.argv[2]
root=Path(__file__).resolve().parents[2]
source=root/'logs_rl/a2_piper_pull_v26_8_backbone/pull_v26_8_backbone_20260905_natural1_r2/wave2/train'/cell/'resolved_config.yaml'
a=yaml.safe_load(path.read_text());b=yaml.safe_load(source.read_text())
# Output paths occur recursively inside env config. Only declared diagnostic,
# output and budget fields may differ; report all differences before launch.
def differences(x,y,p=''):
    if isinstance(x,dict) and isinstance(y,dict):
        return [z for k in x.keys()|y.keys() for z in differences(x.get(k),y.get(k),p+'.'+k)]
    return [] if x==y else [(p,x,y)]
diff=differences(a,b)
allowed={'.checkpoint','.algo.trl.num_total_batches','.callbacks.model_save.save_frequency',
         '.env._target_','.env.config.a2_pull_p1_output','.project_name','.experiment_name',
         '.experiment_dir','.output_dir','.save_dir','.log_task_name','.wandb.name','.wandb.project',
         '.env.config.experiment_dir','.env.config.output_dir','.env.config.save_dir',
         '.callbacks.model_save.save_dir','.timestamp'}
# Resolved paths may reference the changed experiment output in existing fields.
bad=[d for d in diff if d[0] not in allowed and not (
    isinstance(d[1],str) and isinstance(d[2],str) and str(path.parent) in d[1] and str(source.parent) in d[2])]
if bad:raise RuntimeError(f'P1 unexpected source config changes: {bad}')
assert a['algo']['trl']['num_total_batches']==9100 and a['num_envs']==1024
assert a['checkpoint_load_mode']=='full' and a['algo']['config']['num_steps_per_env']==64
assert a['env']['config']['staged_reset_ratios']==[.5,.1,.1,.1,.1,.1]
(path.parent/'config_comparison.json').write_text(json.dumps(dict(source=str(source),differences=diff,unexpected=bad),indent=2)+'\n')
print('P1 resolved config matches source semantics; only diagnostic/output/budget differences',flush=True)
