#!/usr/bin/env bash
set -euo pipefail
[[ $# -eq 5 ]] || { echo "usage: $0 GPU LABEL CHECKPOINT OUTPUT_ROOT SEED" >&2; exit 2; }
for side in left right; do bash "$(dirname "$0")/v26_5_wave2_r1_eval_side.sh" "$1" "$2" "$3" "$4" "$5" "$side"; done
