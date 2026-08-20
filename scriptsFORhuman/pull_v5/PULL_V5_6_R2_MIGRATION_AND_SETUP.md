# Pull-v5.6-r2 Migration and IsaacLab/Isaac Sim Setup

**Prepared:** 2026-08-20 19:53 HKT

**Branch:** `codex/a2-piper-pull-v0-20260803`

**Plan ID:** `a2_piper_pull_v5_6_terminal_hold_specialist_finetune`

**Runtime archive:** `a2_piper_pull_v5_6_r2_runtime_assets_20260820.zip`

## 1. Exact migration boundary

The repository candidate is ready to resume T1. T0.5 micro-smoke and the exact 80-environment step-0 have runtime PASS receipts. The first T1 launch produced no checkpoint; it failed after batch 1 on trainer `workflow_config` plumbing. That execution-layer defect is repaired and statically validated. No specialist checkpoint at steps 250/500/750 exists, and no rehearsal, formal anchor, door probe, P3/P4, dual-source evaluation, or render result exists.

The archive contains the ignored runtime assets that `git clone` cannot restore:

- the accepted specialist warm checkpoint and its receipt;
- the T0.5 and exact-80 step-0 receipts and concise runtime logs;
- the planner decision and v5.5 gate reference;
- the frozen v4-B primary pull checkpoint with its saved config;
- the admitted 191-row G8 state bank, manifest, and receipt;
- the first T1 G9 log for provenance.

The existing root evidence ZIP and the 75 projected traces are intentionally excluded. They are unrelated to resuming v5.6-r2 and remain untouched on the source host.

## 2. Destination host target

Use Ubuntu 22.04, NVIDIA production driver 580.65.06 or newer, at least 32 GB system RAM, and at least one GPU with 16 GB VRAM. The source host used RTX A6000 GPUs and driver 580.173.02. The authorized experiment device IDs remain physical GPUs 4, 5, 6, and 7 only.

Install the clone and conda environment at these exact paths:

```text
/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0
/home/baoquanc/workspace/IsaacLab
/home/baoquanc/anaconda3/envs/isaaclab
```

This is not cosmetic: the accepted `WARM_START.json` contains the first path, and the v5.6 launchers use the third path. If the destination account cannot use the exact clone path, create the documented path as a directory symlink to the real clone before extracting assets. Do not edit accepted receipts to hide a path mismatch.

## 3. Clone and restore runtime assets

```bash
mkdir -p /home/baoquanc/workspace
git clone --branch codex/a2-piper-pull-v0-20260803 \
  git@github.com:Jam-Stark/DoorDog.git \
  /home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0
cd /home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0
unzip -q a2_piper_pull_v5_6_r2_runtime_assets_20260820.zip -d .
```

The archive stores repository-relative paths. Do not extract it above or below the repository root.

## 4. Reproduce the source software stack

The source environment used:

| Component | Version |
|---|---|
| Python | 3.11.15 |
| PyTorch / torchvision | 2.7.0+cu128 / 0.22.0+cu128 |
| Isaac Sim | 5.1.0.0 |
| IsaacLab checkout | v2.3.2 |
| NumPy / SciPy | 1.26.0 / 1.15.3 |
| Hydra / OmegaConf | 1.3.2 / 2.3.0 |
| TensorDict | 0.12.4 |

Follow the [official IsaacLab installation guide](https://isaac-sim.github.io/IsaacLab/main/source/setup/installation/) and [official pip installation guide](https://isaac-sim.github.io/IsaacLab/main/source/setup/installation/pip_installation.html), while pinning the repository to the source-compatible v2.3.2 release:

```bash
conda create -n isaaclab python=3.11 -y
conda activate isaaclab

pip install torch==2.7.0 torchvision==0.22.0 \
  --index-url https://download.pytorch.org/whl/cu128
pip install "isaacsim[all,extscache]==5.1.0" "isaacsim-rl==5.1.0" \
  --extra-index-url https://pypi.nvidia.com

cd /home/baoquanc/workspace
git clone --branch v2.3.2 https://github.com/isaac-sim/IsaacLab.git
cd /home/baoquanc/workspace/IsaacLab
./isaaclab.sh --install

pip install numpy==1.26.0 scipy==1.15.3
cd /home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0
pip install -e .
```

The final editable install must run from the new clone. Do not reuse an editable package pointer to an older DoorDog worktree.

Confirm the package pointer explicitly:

```bash
/home/baoquanc/anaconda3/envs/isaaclab/bin/python - <<'PY'
import gr00t
print(gr00t.__file__)
assert gr00t.__file__.startswith("/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/")
PY
```

If a v5.6 runner reports that a tracked `gr00t` module is missing, this pointer is stale; rerun `pip install -e .` from the clone. Do not mask the problem with a permanent launcher-side path override.

## 5. Environment and asset acceptance

Run one static environment check and one IsaacLab headless smoke before any v5.6 job:

```bash
/home/baoquanc/anaconda3/envs/isaaclab/bin/python - <<'PY'
import numpy, scipy, torch, torchvision
print(torch.__version__, torchvision.__version__)
print(numpy.__version__, scipy.__version__)
assert torch.cuda.is_available()
PY

cd /home/baoquanc/workspace/IsaacLab
/home/baoquanc/anaconda3/envs/isaaclab/bin/python \
  scripts/tutorials/00_sim/create_empty.py --headless

cd /home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0
/home/baoquanc/anaconda3/envs/isaaclab/bin/python \
  scriptsFORhuman/pull_v5/verify_pull_v5_6_r2_migration.py
```

Expected final marker: `MIGRATION_ASSET_VALIDATION_PASS`. The verifier checks file presence, accepted receipt structure, exact absolute warm path, 8-row micro evidence, the 80-row five-family step-0, the warm checkpoint carrier, the v4-B actor, and the 191-row/86-buffer G8 bank. It does not launch IsaacSim and does not create scientific evidence.

## 6. GPU admission and migration micro-smoke

Before launch, inspect physical GPUs 4-7 once:

```bash
nvidia-smi --query-compute-apps=gpu_uuid,pid,process_name,used_memory \
  --format=csv,noheader
nvidia-smi --query-gpu=index,uuid,name,memory.used,memory.total \
  --format=csv,noheader
```

Do not preempt another user's process. Coordinate leases if another task shares GPUs 4-7. Once one authorized GPU is free, run a fresh migration-only micro-smoke into a new directory; do not overwrite the accepted source-host receipt:

```bash
cd /home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0
/home/baoquanc/anaconda3/envs/isaaclab/bin/python \
  scriptsFORhuman/pull_v5/run_pull_v5_6_hold_specialist.py \
  --run --level micro --gpu 4 \
  --micro logs_eval/a2_piper_pull_v5/v5_6_specialist_migration_smoke/MICRO_SMOKE.json
```

This must complete composition, IsaacSim startup, task construction, warm loading, returned-dones rows, and strict micro validation. If it crashes, apply G9 to the actual traceback. Do not reinterpret a machine/setup fault as a capability result.

## 7. Storage expectations

The runtime archive is intentionally small enough for ordinary transfer. Future training/evaluation outputs remain under ignored `logs_rl/` and `logs_eval/` paths. Do not commit new checkpoints, videos, or full simulator logs. The archive itself is the one approved migration carrier committed for this handoff.
