#!/usr/bin/env bash
set -euo pipefail
[[ $# -eq 4 ]] || { echo "usage: $0 GPU K1_S0|K1_S1 OUTPUT_ROOT SEED" >&2; exit 2; }
for side in left right; do
  for view in dual control; do
    bash "$(dirname "$0")/v26_5_wave2_r1_k1_eval_side.sh" "$1" "$view" "$2" "$3" "$4" "$side"
  done
done
