#!/usr/bin/env bash
# All-checkpoint event-funnel eval for one P4 formal seed.
# Usage: p4_eval_all_checkpoints.sh <seed> <gpu_index>
set -euo pipefail

SEED="$1"
GPU="$2"
WORKTREE="/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0"
PYTHON="/home/baoquanc/anaconda3/envs/isaaclab/bin/python"
SEED_DIR=$(ls -d "$WORKTREE"/logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/pull_v0_p4_formal_seed${SEED}-* | head -1)
STEPS="250 500 750 1000 1250 1500 1750 2000 2250 2500"

for STEP in $STEPS; do
  CKPT="$SEED_DIR/model_step_$(printf '%06d' "$STEP").pt"
  OUTDIR="$WORKTREE/logs_eval/a2_piper_pull_v0/p4_event_funnel/seed${SEED}_step${STEP}"
  if [ -f "$OUTDIR/eval/metrics_eval.json" ]; then
    echo "[skip] seed${SEED} step${STEP} already evaluated"
    continue
  fi
  if [ ! -f "$CKPT" ]; then
    echo "[skip] seed${SEED} step${STEP} checkpoint missing: $CKPT"
    continue
  fi
  echo "[eval] seed${SEED} step${STEP} on GPU${GPU}: $CKPT"
  mkdir -p "$OUTDIR"
  CUDA_VISIBLE_DEVICES="$GPU" "$PYTHON" -B -m gr00t.rl.eval_agent_trl \
    checkpoint="$CKPT" \
    checkpoint_load_mode=full \
    ++auto_load_latest=false \
    +num_envs=16 \
    +algo.config.num_mini_batches=1 \
    +seed="$SEED" \
    +headless=true \
    +use_wandb=false \
    algo.config.eval.num_eval_episodes=1 \
    +algo.config.eval.eval_num_envs_episodes=true \
    +algo.config.eval.dump_to_log_metrics=true \
    algo.config.eval.save_goal_reached_only=false \
    algo.config.eval.save_trajectories=false \
    algo.config.eval.save_videos=false \
    algo.config.eval.num_save_episodes=16 \
    algo.config.eval.a2_diagnostic_trace_enabled=false \
    algo.config.eval.a2_forced_gripper_close_enabled=false \
    eval_output_dir="$OUTDIR/eval" \
    eval_log_dir="$OUTDIR/hydra" \
    env.config.save_rendering_dir="$OUTDIR/renderings" \
    +device=cuda:0 \
    hydra.run.dir="$OUTDIR/hydra"
  echo "[done] seed${SEED} step${STEP}"
done
echo "ALL_CHECKPOINTS_EVALUATED seed${SEED}"
