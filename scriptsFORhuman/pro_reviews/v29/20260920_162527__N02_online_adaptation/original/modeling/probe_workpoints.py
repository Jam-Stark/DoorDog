from pathlib import Path
import json,numpy as np
from robot_model import Robot
p=Path(__file__).parent/'inputs';r=Robot(p/'a2_piper.urdf',p/'JOINT_LIMITS_AND_ACTUATORS.csv');m=json.load(open(p/'ROBOT_MODEL_INPUTS.json'));q=np.array([m['init_state']['default_joint_angles'][n] for n in r.names]);b=np.array([0.,0.,.55*np.cos(.5)+.032]);R=np.column_stack(([0,1,0],[0,0,1],[1,0,0]));rng=np.random.default_rng(29)
for target in [[.5,.12,.9],[.55,.12,1.05],[.5,.12,1.2],[.7,.12,.9],[.5,-.12,1.05],[.65,0,1.05]]:
 best=None
 for si in range(5):
  seed=q.copy()
  if si:seed[r.arm]=[0.1, rng.uniform(.1,1.8),-rng.uniform(.5,2.3),0.,rng.uniform(-.8,.8),1.57]
  qs,pe,re=r.ik(seed,b,np.eye(3),'arm_body6_to_gripper',np.array(target),R,r.arm,np.array([0,0,.085]))
  if best is None or pe+re<best[0]+best[1]:best=pe,re,qs
  if pe<1e-7 and re<1e-7:break
 print(target,'res',best[:2],'q',np.round(best[2][r.arm],4),flush=True)
