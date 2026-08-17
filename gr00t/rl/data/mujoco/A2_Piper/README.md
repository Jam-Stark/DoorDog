# A2+Piper MuJoCo shadow asset

`a2_piper.xml` is generated from `gr00t/rl/data/robots/A2_Piper/a2_piper.urdf` by the additive sim2sim builder. It is a floating-base, torque-actuated realization with 20 named motors. `robot_contract.json` is the executable name/order/default/PD/camera receipt.

The runtime must apply the external position PD and torque clip on every 200 Hz physics step. The actuator `ctrlrange` is a second expression of the same torque face, not a substitute for the external clip.

Build command:

```bash
PYTHONPATH=. python gr00t/rl/sim2sim/cli/build_a2_piper_mjcf.py \
  --urdf gr00t/rl/data/robots/A2_Piper/a2_piper.urdf \
  --bundle-dir scriptsFORhuman/sim2sim/assets/student_bundle_grpo_step10_ready_r2 \
  --output-xml gr00t/rl/data/mujoco/A2_Piper/a2_piper.xml \
  --output-contract gr00t/rl/data/mujoco/A2_Piper/robot_contract.json \
  --output-report scriptsFORhuman/sim2sim/artifacts/e1/robot_build_report.json
```

The camera quaternions are transformed algebraically using the local IsaacLab `world` camera-basis contract. See the axis-marker receipt before making any pixel-parity claim.
