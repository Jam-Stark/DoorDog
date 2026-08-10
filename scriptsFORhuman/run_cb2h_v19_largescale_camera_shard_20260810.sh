#!/usr/bin/env bash
set -euo pipefail

if (( $# < 2 )); then
  echo "usage: $0 GPU CONTROLLER:SEED [...]" >&2
  exit 2
fi

eval_gpu="$1"
shift

repo_root="/home/baoquanc/workspace/DoorDog-A2-Piper-v13-student-distillation-20260717_2103"
output_root="${repo_root}/logs_eval/by_batch/cb2h_v19_toeout6_pitch50_largescale_camera_eval_20260810"
checkpoint="${repo_root}/logs_rl/by_batch/cb2h_v19_toeout6_pitch50_20260805/formal_4x64_8k_gpu4-7_timeoutfix_retry/model_step_008000.pt"
python_bin="/home/baoquanc/anaconda3/envs/isaaclab/bin/python"
runner="${repo_root}/gr00t/rl/scripts/run_a2_toeout6_student_eval.py"
failure_file="${output_root}/shard_gpu${eval_gpu}.failures.txt"

cd "${repo_root}"
rm -f "${failure_file}"

for eval_spec in "$@"; do
  lane="${eval_spec%%:*}"
  seed="${eval_spec##*:}"
  case "${lane}" in
    student|teacher)
      controller="${lane}"
      eval_mode=formal
      output_lane="${lane}"
      ;;
    customdata)
      controller=student
      eval_mode=diagnose
      output_lane=customdata
      ;;
    *) echo "unsupported lane in shard spec: ${eval_spec}" >&2; exit 2 ;;
  esac
  if [[ ! "${seed}" =~ ^[0-9]+$ ]]; then
    echo "invalid seed in shard spec: ${eval_spec}" >&2
    exit 2
  fi

  lane_root="${output_root}/${output_lane}_gpu${eval_gpu}"
  mkdir -p "${lane_root}"
  completed=false

  for attempt in 1 2; do
    seed_name="$(printf 'seed_%02d' "${seed}")"
    if (( attempt == 2 )); then
      seed_name="${seed_name}_retry02"
    fi
    run_root="${lane_root}/${seed_name}"
    runner_log="${lane_root}/${seed_name}.runner.log"
    timing_file="${lane_root}/${seed_name}.timing.txt"

    echo "[SHARD_START] gpu=${eval_gpu} lane=${lane} controller=${controller} seed=${seed} attempt=${attempt}"
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
          --mode "${eval_mode}" \
          --controller "${controller}" \
          --seed "${seed}" \
          --checkpoint "${checkpoint}" \
          --expected-global-step 8000 \
          --output-root "${run_root}" \
          > "${runner_log}" 2>&1
    run_status=$?
    set -e

    if (( run_status == 0 )); then
      echo "[SHARD_PASS] gpu=${eval_gpu} lane=${lane} controller=${controller} seed=${seed} attempt=${attempt}"
      completed=true
      break
    fi
    echo "[SHARD_RETRY] gpu=${eval_gpu} lane=${lane} controller=${controller} seed=${seed} attempt=${attempt} status=${run_status}" >&2
  done

  if [[ "${completed}" != true ]]; then
    printf 'gpu=%s lane=%s controller=%s seed=%s attempts=2\n' "${eval_gpu}" "${lane}" "${controller}" "${seed}" >> "${failure_file}"
    echo "[SHARD_SKIP] gpu=${eval_gpu} lane=${lane} controller=${controller} seed=${seed} attempts=2" >&2
  fi
done

if [[ -s "${failure_file}" ]]; then
  echo "[SHARD_COMPLETE_WITH_GAPS] gpu=${eval_gpu} failures=${failure_file}" >&2
  exit 1
fi

rm -f "${failure_file}"
echo "[SHARD_COMPLETE] gpu=${eval_gpu}"
