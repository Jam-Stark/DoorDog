#!/usr/bin/env bash
set -euo pipefail

if (( $# != 3 )); then
  echo "usage: $0 GPU START_SEED END_SEED" >&2
  exit 2
fi

eval_gpu="$1"
start_seed="$2"
end_seed="$3"
repo_root="/home/baoquanc/workspace/DoorDog-A2-Piper-v13-student-distillation-20260717_2103"
output_root="${repo_root}/logs_rl/by_batch/cb2h_v19_toeout6_pitch50_grpo_20260811/large_eval"
checkpoint="${repo_root}/logs_rl/by_batch/cb2h_v19_toeout6_pitch50_grpo_20260811/pilot_2x32_lr375e8_syncreset/model_step_000010.pt"
python_bin="/home/baoquanc/anaconda3/envs/isaaclab/bin/python"
runner="${repo_root}/gr00t/rl/scripts/run_a2_toeout6_student_eval.py"
lane_root="${output_root}/student_gpu${eval_gpu}"
failure_file="${output_root}/shard_gpu${eval_gpu}.failures.txt"

mkdir -p "${lane_root}"
rm -f "${failure_file}"
cd "${repo_root}"

for seed in $(seq "${start_seed}" "${end_seed}"); do
  completed=false
  for attempt in 1 2; do
    seed_name="$(printf 'seed_%02d' "${seed}")"
    if (( attempt == 2 )); then
      seed_name="${seed_name}_retry02"
    fi
    run_root="${lane_root}/${seed_name}"
    runner_log="${lane_root}/${seed_name}.runner.log"
    timing_file="${lane_root}/${seed_name}.timing.txt"
    echo "[SHARD_START] gpu=${eval_gpu} seed=${seed} attempt=${attempt}"
    set +e
    env \
      PYTHONPATH="${repo_root}" \
      CUDA_VISIBLE_DEVICES="${eval_gpu}" \
      ACCELERATE_TORCH_DEVICE=cuda:0 \
      HYDRA_FULL_ERROR=1 \
      WANDB_MODE=disabled \
      PYTHONUNBUFFERED=1 \
      /usr/bin/time \
        -f 'elapsed_seconds=%e max_rss_kb=%M exit_status=%x' \
        -o "${timing_file}" \
        "${python_bin}" "${runner}" \
          --mode formal \
          --controller student \
          --seed "${seed}" \
          --checkpoint "${checkpoint}" \
          --expected-global-step 10 \
          --output-root "${run_root}" \
          > "${runner_log}" 2>&1
    run_status=$?
    set -e
    if (( run_status == 0 )); then
      echo "[SHARD_PASS] gpu=${eval_gpu} seed=${seed} attempt=${attempt}"
      completed=true
      break
    fi
    echo "[SHARD_RETRY] gpu=${eval_gpu} seed=${seed} attempt=${attempt} status=${run_status}" >&2
  done
  if [[ "${completed}" != true ]]; then
    printf 'gpu=%s seed=%s attempts=2\n' "${eval_gpu}" "${seed}" >> "${failure_file}"
  fi
done

if [[ -s "${failure_file}" ]]; then
  echo "[SHARD_COMPLETE_WITH_GAPS] gpu=${eval_gpu} failures=${failure_file}" >&2
  exit 1
fi

rm -f "${failure_file}"
echo "[SHARD_COMPLETE] gpu=${eval_gpu}"
